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

PROMPT = """You are proofreading Sanskrit/Kannada text scanned from a printed book.

Two OCR engines read the same page and disagree. Engine A (Sarvam) preserves
layout and returns HTML. Engine B (Google Vision) returns flat text and often
reorders verse markers. Neither is reliably better.

For each page, return the correct reading. Rules:
- Where the engines agree, keep that reading.
- Where they differ, choose by what makes sense as Sanskrit/Kannada: real words,
  real sandhi, plausible grammar, consistent verse numbering.
- Do NOT translate, explain, modernise or normalise spelling.
- Do NOT invent text to fill a gap. If a stretch is unreadable in both, keep the
  more plausible reading and lower your confidence for that page.
- Strip OCR furniture: running headers, page numbers, scanner watermarks.
- Preserve danda/double-danda and verse numbers exactly as the source has them.

Return ONLY JSON, no prose, no markdown fence:
{"pages":[{"page":<int>,"text":"<corrected reading>","confidence":<0..1>,
"note":"<short reason, only where you had to choose>"}]}
"""


def price(model):
    if model not in PRICES:
        raise SystemExit("no price on file for %r -- add it to PRICES and check "
                         "ai.google.dev/gemini-api/docs/pricing first" % model)
    return PRICES[model]


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


def ask(batch, model, api_key, usage):
    body = {
        "contents": [{"parts": [{"text": PROMPT + "\n\n" + json.dumps(
            [{"page": c["page"], "engine_a_sarvam": c.get("sarvam", ""),
              "engine_b_vision": c.get("vision", "")} for c in batch],
            ensure_ascii=False)}]}],
        "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
    }
    payload = call_gemini(body=body, api_key=api_key, model=model, usage_totals=usage)
    text = ""
    for cand in payload.get("candidates") or []:
        for part in (cand.get("content") or {}).get("parts") or []:
            text += part.get("text") or ""
    if not text.strip():
        return []
    try:
        return (json.loads(text) or {}).get("pages") or []
    except json.JSONDecodeError:
        return []


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
        pin, pout = price(args.model)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump({
                "_readme": "Gemini's reading of the pages where Sarvam and Vision "
                           "disagreed. Staged for review; merges nothing.",
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
            pages = ask(batch, args.model, api_key, usage)
        except Exception as exc:  # noqa: BLE001
            print("  call failed: %s" % str(exc)[:160])
            save()
            return 1
        calls += 1
        spent = cost_inr(usage, args.model, args.inr_per_usd)
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
