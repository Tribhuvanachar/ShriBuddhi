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
You are NOT an editor, a translator, or a commentator. The book is the
authority. Your job is to decide which engine read the page correctly.

Engine A (Sarvam) preserves layout and returns HTML. Engine B (Google Vision)
returns flat text and often displaces verse markers. Neither is reliably better.

THE BINDING RULE
Every word you output must be a word one of the two engines read. Where they
agree, keep it. Where they differ, pick whichever is the better reading of what
was printed. You may rejoin a word an engine split, and split one it ran
together. You may not do anything else to the text.

In particular, you must NOT:
- complete a verse, a compound, or a sentence that looks unfinished
- emend a reading to what correct Sanskrit or Kannada would require
- insert a word, a particle, or an ending that neither engine read
- translate, gloss, explain, summarise, modernise or normalise spelling
- resolve or add sandhi, or regularise a metre
- answer, continue, or comment on anything the text says

A garbled reading left garbled is CORRECT behaviour and costs nothing. A
plausible conjecture is the worst outcome available to you: an OCR error looks
wrong and gets found, a good conjecture looks right and never does. Corpora are
ruined this way.

If both engines are unreadable for a stretch, keep the likelier reading
VERBATIM, set confidence below 0.5, and say "unreadable" in the note. Do not
guess the words.

WHERE THE ENGINES DISAGREE STRUCTURALLY
If one returned a table and the other ran the cells together, follow the table:
its structure is evidence about the page. Do not reorder rows or columns.

WHAT TO DROP
Running headers, page numbers, scanner watermarks ("Rarest Archiver"), and
printed advertisements are furniture, not text. Drop them. Keep everything else,
including errata tables, colophons and editorial notes printed in the book.

Preserve danda and double danda, verse numbers and avagraha exactly as read.

In `note`, say which engine you followed and why, in a few words. If you changed
anything neither engine read -- even a single letter -- say so explicitly there.
Your output is checked mechanically against both readings, and any stretch
neither engine read is reported for human review.
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
                },
                "required": ["page", "text", "confidence"],
            },
        }
    },
    "required": ["pages"],
}


def ask(batch, model, api_key, usage, max_output_tokens):
    payload = json.dumps(
        [{"page": c["page"], "engine_a_sarvam": c.get("sarvam", ""),
          "engine_b_vision": c.get("vision", "")} for c in batch],
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
    resolved = list(done.values())
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
        try:
            pages = ask(batch, args.model, api_key, usage, args.max_output_tokens)
        except Exception as exc:  # noqa: BLE001
            print("  call failed: %s" % str(exc)[:160])
            save()
            return 1
        calls += 1
        # Priced against what was SERVED, not what was asked for.
        spent = cost_inr(usage, served_model(usage, args.model), args.inr_per_usd)
        per_call_inr = spent / calls
        by_page = {p.get("page"): p for p in pages if isinstance(p, dict)}
        for c in batch:
            g = by_page.get(c["page"])
            if not g:
                continue
            resolved.append({"work": c["work"], "page": c["page"],
                             "text": g.get("text", ""), "confidence": g.get("confidence"),
                             "note": g.get("note", ""), "ratio": c.get("ratio")})
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
    if this_run:
        print("actual cost per page THIS RUN: Rs%.3f  (%d page(s) paid for here)"
              % (spent / this_run, this_run))
        print("tokens: in %d, out %d" % (usage.get("prompt_tokens", 0),
                                         usage.get("output_tokens", 0)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
