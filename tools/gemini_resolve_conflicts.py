#!/usr/bin/env python3
"""
gemini_resolve_conflicts.py -- adjudicate the pages where Sarvam and Vision
disagree, under a hard rupee budget that the script enforces itself.

Two OCR engines read every page. Where they agree, that agreement is the
evidence and nothing is sent. Where they differ -- 1,501 pages of 20,442, 7.3%
-- a third reading decides. This sends only those, in batches, and after every
single call it adds up what Gemini itself reported spending and compares that
against the budget. When the next batch could take it over, it stops and writes
what it has.

The budget is checked in code rather than watched by a person, because the last
two top-ups were consumed by runs that nobody was watching at the time.

    python3 tools/gemini_resolve_conflicts.py \
        --conflicts data/ocr_staging/<work>/conflicts.json \
        --budget-inr 1000 --model gemini-2.5-flash

Resumable: pages already resolved in --out are skipped, so a run that stops on
budget continues where it left off when the budget is raised.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gemini_client import call_gemini  # noqa: E402

# USD per 1,000,000 tokens. Checked against ai.google.dev/gemini-api/docs/pricing
# on 18 Sep 2026. A wrong number here is a wrong budget, so it is named per
# model rather than defaulted.
PRICES = {
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gemini-flash-latest": (0.75, 3.75),
    "gemini-flash-lite-latest": (0.10, 0.40),
}

PROMPT = """You are a proofreader reconciling two OCR readings of one printed page.
The book is the authority. You are not editing it, translating it, or improving
it. You are deciding what it says.

Engine A (Sarvam) keeps layout and returns HTML. Engine B (Google Vision) returns
flat text and often displaces verse markers. Neither is reliably better.

Each page also carries `context_previous_page_end` and `context_next_page_start`:
the settled text of the pages either side, where the two engines already agreed.
READ them -- a sentence or a commentary running across a page break is exactly
where a reading is hardest to judge, and this is what tells you what it was
saying. DO NOT return them, do not correct them, and do not let text from them
leak into the page you return. Your output covers THIS page only. The context
may be empty when a neighbour is missing or was itself in dispute.

You have exactly three things you may do, and they are not equally free.

TIER 1 -- CHOOSE. Free, no declaration needed.
Pick whichever engine read a passage correctly. Rejoin a word one engine split;
split one it ran together. Follow a table over a flattened reading of the same
cells. Drop running headers, page numbers, scanner watermarks and printed
advertisements. This is your normal work and most of a page should be this.

TIER 2 -- CORRECT, AND SAY SO. Allowed only with a warrant ON THE PAGE.
You may correct a reading neither engine got right, but only when the page
itself proves the correction. Acceptable warrants:
  arithmetic  the page prints "2x5x1000 = 16,000"; the stated total proves the
              5 is a misread 8
  internal    a running title, a name or a term that appears correctly elsewhere
              on this same page
  structural  a table column whose other rows fix the pattern
  script      a character from the WRONG SCRIPT sits inside a word -- a Bengali
              digit in a Devanagari reference, a Kannada letter in a Devanagari
              block. The script itself is the proof; no judgement is involved
  grammatical the form is not a possible word, and the correct one follows from
              morphology alone: uttva for uktva, yavanti for cyavanti,
              bhattya for bhaktya. Use this ONLY where the printed form cannot
              exist in the language, never where it merely reads oddly, and
              never to complete or improve something that is already a word
Every such correction goes in `emendations` with the warrant named.

Name the warrant you ACTUALLY used. The earlier version of these rules offered
only the first three, so corrections resting on grammar were filed as
"internal" with a `why` that said "grammar requires it" -- which made the
honest internal ones untrustworthy too. A truthful `grammatical` is reviewed
and often kept. A `grammatical` dressed as `internal` is a finding about you,
not about the page. Your output
is machine-checked against both readings: ANY stretch neither engine read that
you have not declared is reported as a fault.

What is NOT a warrant, even now that `grammatical` exists: that a verse looks
unfinished; that a compound wants an ending; that the metre limps; that you
recognise the quotation and can supply the rest. `grammatical` covers a form
that CANNOT EXIST, never a form that exists but reads oddly, and never adding
something absent. Adding a final -m to a word that is already a word is not a
correction, it is an edit. Those are conjecture. A conjecture that reads
well is the most damaging thing you can produce here, because an OCR error looks
wrong and gets found while a good conjecture looks right forever.

TIER 3 -- SUSPECT, AND CHANGE NOTHING.
Both engines often make the SAME mistake, and then nothing downstream can catch
it. When the agreed reading still looks wrong to you -- a name you know is
usually spelled otherwise, a list whose members do not belong together, a number
that contradicts its neighbours, a word that is not a word -- leave the text
EXACTLY as read and record it in `suspects`: the passage, what you think it
should be, and why. Do not apply it. A human decides.

This tier is the point of the exercise. Use it freely -- a suspect costs nothing
and risks nothing, and it is the only way an error both engines share ever
surfaces. Silence here is not caution; it is the failure mode.

If both readings are unreadable for a stretch, keep the likelier one VERBATIM,
set confidence below 0.5, and note "unreadable". Do not guess the words.

Preserve danda, double danda, verse numbers and avagraha as read.
"""


def price(model):
    if model not in PRICES:
        raise SystemExit("no price on file for %r -- add it to PRICES and check "
                         "ai.google.dev/gemini-api/docs/pricing first" % model)
    return PRICES[model]


def served_model(usage, requested):
    """What actually ran, which is not always what was asked for.

    gemini_client falls back to FALLBACK_MODEL on quota, model_missing or
    overloaded, and says so only in usageMetadata's modelVersion. The
    calibration run asked for gemini-2.5-flash and was served
    gemini-3.5-flash-lite -- priced at the requested model it read Rs14.14,
    priced at the one that ran, Rs2.95. A ledger that records the request
    rather than the service is wrong by 5x and gives no hint of it.
    """
    v = (usage or {}).get("model_version") or ""
    if not v:
        return requested
    if "lite" in v:
        return "gemini-flash-lite-latest" if v not in PRICES else v
    return v if v in PRICES else requested


def cost_inr(usage, model, inr_per_usd):
    pin, pout = price(model)
    return ((usage.get("prompt_tokens", 0) / 1e6) * pin
            + (usage.get("output_tokens", 0) / 1e6) * pout) * inr_per_usd


def batches(conflicts, per_call, char_cap):
    """Group pages per call, capped on both count and characters.

    A page of dense commentary is ~4,000 characters across both readings, so a
    fixed page count alone can build a request several times larger than the
    one it was sized against, and the first sign of that is a truncated reply.
    """
    cur, cur_chars = [], 0
    for c in conflicts:
        n = len(c.get("sarvam", "")) + len(c.get("vision", ""))
        if cur and (len(cur) >= per_call or cur_chars + n > char_cap):
            yield cur
            cur, cur_chars = [], 0
        cur.append(c)
        cur_chars += n
    if cur:
        yield cur


# Gemini's structured-output schema. Declared rather than left to prose,
# because a reply that drifts from the shape is a page silently lost.
SCHEMA = {
    "type": "object",
    "properties": {
        "pages": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "page": {"type": "integer"},
                    "text": {"type": "string"},
                    "confidence": {"type": "number"},
                    "note": {"type": "string"},
                    # Tier 2: a change neither engine read, with its warrant.
                    # Declared so the machine check can tell a corrected
                    # reading from an invented one -- an undeclared departure
                    # is a fault, a declared one is a decision.
                    "emendations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "from": {"type": "string"},
                                "to": {"type": "string"},
                                "warrant": {"type": "string",
                                            "enum": ["arithmetic", "internal",
                                                     "structural", "script",
                                                     "grammatical"]},
                                "why": {"type": "string"},
                            },
                            "required": ["from", "to", "warrant", "why"],
                        },
                    },
                    # Tier 3: both engines agree and it still looks wrong.
                    # The text is NOT changed. This is the only channel through
                    # which an error both engines share can ever surface.
                    "suspects": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "passage": {"type": "string"},
                                "expected": {"type": "string"},
                                "why": {"type": "string"},
                            },
                            "required": ["passage", "why"],
                        },
                    },
                },
                "required": ["page", "text", "confidence"],
            },
        }
    },
    "required": ["pages"],
}


def ask(batch, model, api_key, usage, max_output_tokens):
    payload = json.dumps(
        [{"page": c["page"],
          # The settled text of the pages either side, so a passage running
          # across a page break can be judged. Read-only: see the prompt.
          "context_previous_page_end": c.get("context_before", ""),
          "engine_a_sarvam": c.get("sarvam", ""),
          "engine_b_vision": c.get("vision", ""),
          "context_next_page_start": c.get("context_after", "")}
         for c in batch],
        ensure_ascii=False)
    out = call_gemini(
        system_instruction=PROMPT,
        prompt=payload,
        response_schema=SCHEMA,
        api_key=api_key,
        model=model,
        temperature=0,
        max_output_tokens=max_output_tokens,
        usage_totals=usage,
    )
    return (out or {}).get("pages") or []


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 2)[1])
    ap.add_argument("--conflicts", nargs="+", required=True,
                    help="conflicts.json file(s), or globs")
    ap.add_argument("--out", required=True, help="resolved output json")
    ap.add_argument("--budget-inr", type=float, required=True)
    ap.add_argument("--model", default="gemini-2.5-flash")
    ap.add_argument("--inr-per-usd", type=float, default=88.0)
    ap.add_argument("--pages-per-call", type=int, default=4)
    ap.add_argument("--char-cap", type=int, default=24000)
    ap.add_argument("--max-output-tokens", type=int, default=32768,
                    help="the client defaults to 4096, which truncates a "
                         "multi-page reply and loses pages without saying so")
    ap.add_argument("--max-ratio", type=float, default=0.92,
                    help="only pages BELOW this similarity (the conflicts)")
    ap.add_argument("--already", action="append", default=[], metavar="GLOB",
                    help="resolved-*.json from earlier runs: treated as done, "
                         "never re-sent, never copied into --out")
    ap.add_argument("--dry-run", action="store_true",
                    help="count what would be sent and stop; calls nothing")
    args = ap.parse_args(argv)

    files = []
    for pat in args.conflicts:
        files.extend(sorted(glob.glob(pat)) or ([pat] if os.path.exists(pat) else []))
    if not files:
        print("no conflicts files matched", file=sys.stderr)
        return 2

    done = {}
    if os.path.exists(args.out):
        prev = json.load(open(args.out))
        done = {(p["work"], p["page"]): p for p in prev.get("pages", [])}
        print("resuming: %d page(s) already resolved" % len(done))

    # Pages resolved by EARLIER runs, living in their own files. They count as
    # done -- so they are neither re-sent nor re-billed -- but they are NOT
    # copied into this run's output, which stays a record of what this run
    # bought.
    #
    # Without this, --out is a fresh temp file on every workflow dispatch and
    # `done` starts empty, so every dispatch re-sends and re-pays for every
    # conflict in the works it names. Re-running twelve HKS volumes to pick up
    # 27 stragglers would have cost about Rs11 instead of Rs1.
    already = 0
    for pat in args.already or []:
        for f in sorted(glob.glob(pat)):
            try:
                prev = json.load(open(f))
            except Exception:
                continue
            for q in prev.get("pages", []):
                key = (q.get("work"), q.get("page"))
                if key not in done:
                    done[key] = None          # known, but not ours to re-emit
                    already += 1
    if already:
        print("%d page(s) already resolved by earlier runs -- not re-sent" % already)

    todo = []
    for f in files:
        d = json.load(open(f))
        work = d.get("work") or os.path.basename(os.path.dirname(f))
        for c in d.get("conflicts", []):
            if c.get("ratio", 0) >= args.max_ratio:
                continue
            if (work, c["page"]) in done:
                continue
            todo.append(dict(c, work=work))
    chars = sum(len(c.get("sarvam", "")) + len(c.get("vision", "")) for c in todo)
    print("%d page(s) to resolve across %d work(s), %.2fM characters"
          % (len(todo), len(files), chars / 1e6))
    if args.dry_run or not todo:
        return 0

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY is not set", file=sys.stderr)
        return 2

    usage = {}
    spent = 0.0
    resolved = [v for v in done.values() if v is not None]
    dropped = []
    this_run = 0          # pages resolved by THIS run, not counting a resume
    calls = stopped = 0
    per_call_inr = None

    def save():
        pin, pout = price(served_model(usage, args.model))
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump({
                "_readme": "Gemini's reading of the pages where Sarvam and Vision "
                           "disagreed. Staged for review; merges nothing.",
                "model_requested": args.model,
                "model_served": served_model(usage, args.model),
                "model": args.model, "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "budget_inr": args.budget_inr, "spent_inr": round(spent, 2),
                "usage": usage, "price_per_m_usd": {"in": pin, "out": pout},
                "inr_per_usd": args.inr_per_usd,
                "calls": calls, "pages_resolved": len(resolved),
                "pages_this_run": this_run,
                "inr_per_page_this_run": round(spent / this_run, 4) if this_run else None,
                "stopped_on_budget": bool(stopped),
                "pages": resolved,
            }, fh, ensure_ascii=False, indent=1)

    for batch in batches(todo, args.pages_per_call, args.char_cap):
        # Stop BEFORE the call that could exceed the budget, using what the
        # last calls actually cost rather than an estimate made beforehand.
        if per_call_inr is not None and spent + per_call_inr > args.budget_inr:
            stopped = 1
            print("stopping: Rs%.2f spent, next call ~Rs%.2f, budget Rs%.2f"
                  % (spent, per_call_inr, args.budget_inr))
            break
        # A transient network fault must not end a run that has already been
        # billed for. Call 34 of a 5-work batch timed out on 19 Sep 2026 and
        # took the whole run down after 117 pages and Rs6.19 of paid work.
        pages, err = None, None
        for attempt in range(1, 4):
            try:
                pages = ask(batch, args.model, api_key, usage, args.max_output_tokens)
                break
            except Exception as exc:  # noqa: BLE001
                err = exc
                transient = any(w in str(exc).lower() for w in
                                ("timed out", "timeout", "connection", "reset",
                                 "temporarily", "503", "502", "500", "429"))
                if not transient or attempt == 3:
                    break
                print("  attempt %d failed (%s) -- retrying" % (attempt, str(exc)[:70]))
                time.sleep(5 * attempt)
        if pages is None:
            # Stop cleanly rather than crashing: everything resolved so far is
            # already written, and the run must still reach the step that
            # pushes it.
            print("  call failed after retries: %s" % str(err)[:160])
            print("  stopping here; %d page(s) already resolved are kept." % this_run)
            result["stopped_early"] = str(err)[:200]
            break
        calls += 1
        # Priced against what was SERVED, not what was asked for.
        spent = cost_inr(usage, served_model(usage, args.model), args.inr_per_usd)
        per_call_inr = spent / calls
        by_page = {p.get("page"): p for p in pages if isinstance(p, dict)}
        for c in batch:
            g = by_page.get(c["page"])
            if not g:
                # The model answered the call but left this page out of its
                # reply. It used to vanish here in silence: the page was
                # never resolved, never retried, and the run still reported
                # "resolved N" as though N were everything asked for. 27 HKS
                # pages accumulated this way across five runs before anyone
                # noticed, and only because a separate count disagreed.
                #
                # Not retried here -- the page costs nothing to leave for the
                # next run, which skips what is already in --out and will pick
                # this up. What matters is that it is now COUNTED and named.
                dropped.append((c["work"], c["page"]))
                continue
            resolved.append({"work": c["work"], "page": c["page"],
                             "text": g.get("text", ""), "confidence": g.get("confidence"),
                             "note": g.get("note", ""), "ratio": c.get("ratio"),
                             "emendations": g.get("emendations") or [],
                             "suspects": g.get("suspects") or []})
            this_run += 1
        # Per-page cost must divide this run's spend by the pages THIS run
        # paid for. Dividing by the total after a resume charges this run for
        # pages a previous one already bought, and that number is what the
        # next estimate is built from.
        print("  call %-4d pages %-4d (+%d new)  spent Rs%8.2f  (Rs%.3f/new page)"
              % (calls, len(resolved), this_run, spent, spent / max(1, this_run)))
        save()
        time.sleep(1)

    save()
    print("\nresolved %d page(s) in %d call(s); Rs%.2f of Rs%.2f%s"
          % (len(resolved), calls, spent, args.budget_inr,
             " -- STOPPED ON BUDGET" if stopped else ""))
    if dropped:
        # Paid for and not returned. Say so: a run that reports only what came
        # back reads as complete, and these pages sat unresolved across five
        # runs precisely because nothing counted them.
        print("%d page(s) were sent and NOT returned by the model, so they are"
              " still unresolved:" % len(dropped))
        by_work = {}
        for w, n in dropped:
            by_work.setdefault(w, []).append(n)
        for w in sorted(by_work):
            ns = sorted(by_work[w])
            print("    %-24s %s%s" % (w, ns[:12], " ..." if len(ns) > 12 else ""))
        print("  Re-run to pick them up: pages already in --out are skipped.")
    if this_run:
        print("actual cost per page THIS RUN: Rs%.3f  (%d page(s) paid for here)"
              % (spent / this_run, this_run))
        print("tokens: in %d, out %d" % (usage.get("prompt_tokens", 0),
                                         usage.get("output_tokens", 0)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
