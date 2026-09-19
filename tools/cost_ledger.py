#!/usr/bin/env python3
"""
cost_ledger.py -- one permanent row for every rupee this project spends.

The question this exists to answer, exactly: "the 10,000 rupee top-up bought
how many PDFs, and which ones?" Today that cannot be answered at all. Sarvam
billed roughly 21,000 pages across September and the only record is the
per-file `usage` block inside each staged OCR file -- no dates, no rupees, no
link back to the book, nothing that survives a branch being tidied away.

Every append records: WHEN, WHICH ENGINE, WHICH WORK, WHICH SOURCE PDF, how
many pages, how many tokens where tokens apply, and what it cost in USD and
INR at the rate used on the day. Nothing is derived later from memory.

    python3 tools/cost_ledger.py --append --engine sarvam --work hks__10_hks \
        --pages 198 --usd 0.99
    python3 tools/cost_ledger.py --append --engine gemini --work brhatisahasram \
        --pages 40 --tokens-in 210000 --tokens-out 90000 --model gemini-2.5-flash
    python3 tools/cost_ledger.py --report            # by engine, by work, total
    python3 tools/cost_ledger.py --report --since 2026-09-01

The file is append-only JSONL: a ledger that rewrites its own history is not a
ledger, and one row per line means two runs finishing together cannot lose each
other's entry the way a re-serialised JSON array would.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys
import time

LEDGER = "admin/config/cost_ledger.jsonl"

# USD per 1,000,000 tokens, or per page for the page-billed engines. Checked
# against each vendor's published pricing on the date in PRICES_CHECKED. A
# wrong number here is a wrong invoice, so it is stated, never guessed.
PRICES_CHECKED = "2026-09-18"
TOKEN_PRICES = {
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gemini-flash-latest": (0.75, 3.75),
    "gemini-flash-lite-latest": (0.10, 0.40),
}


def append(row, path=LEDGER):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def read(path=LEDGER):
    if not os.path.exists(path):
        return []
    rows = []
    for n, line in enumerate(open(path, encoding="utf-8"), 1):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            print("ledger line %d is not JSON -- left alone, not repaired" % n,
                  file=sys.stderr)
    return rows


def report(rows, since=None):
    if since:
        rows = [r for r in rows if r.get("at", "") >= since]
    if not rows:
        print("no entries")
        return
    by_engine = collections.defaultdict(lambda: collections.Counter())
    works = collections.defaultdict(lambda: collections.Counter())
    for r in rows:
        e = r.get("engine", "?")
        by_engine[e]["pages"] += r.get("pages", 0)
        by_engine[e]["inr"] += r.get("inr", 0.0)
        by_engine[e]["tokens"] += r.get("tokens_in", 0) + r.get("tokens_out", 0)
        by_engine[e]["runs"] += 1
        w = r.get("work", "?")
        works[w]["pages"] += r.get("pages", 0)
        works[w]["inr"] += r.get("inr", 0.0)

    print("%-14s %7s %9s %14s %12s" % ("engine", "runs", "pages", "tokens", "INR"))
    tp = ti = 0.0
    for e in sorted(by_engine):
        v = by_engine[e]
        tp += v["pages"]; ti += v["inr"]
        print("%-14s %7d %9d %14d %12.2f"
              % (e, v["runs"], v["pages"], v["tokens"], v["inr"]))
    print("%-14s %7s %9d %14s %12.2f" % ("TOTAL", "", tp, "", ti))
    print("\ndistinct works billed : %d" % len(works))
    src = {r.get("source_pdf") for r in rows if r.get("source_pdf")}
    print("distinct source PDFs  : %d" % len(src))
    if tp:
        print("cost per page overall : Rs %.4f" % (ti / tp))
    if src:
        print("cost per PDF average  : Rs %.2f" % (ti / len(src)))
    print("\nmost expensive works:")
    for w, v in sorted(works.items(), key=lambda kv: -kv[1]["inr"])[:10]:
        print("  %-52s %6d pages  Rs %9.2f" % (w[:52], v["pages"], v["inr"]))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 2)[1])
    ap.add_argument("--append", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--ledger", default=LEDGER)
    ap.add_argument("--since")
    ap.add_argument("--engine", help="sarvam | vision | gemini | ...")
    ap.add_argument("--work")
    ap.add_argument("--source-pdf", default="", help="the URL the pages came from")
    ap.add_argument("--pages", type=int, default=0)
    ap.add_argument("--model", default="")
    ap.add_argument("--tokens-in", type=int, default=0)
    ap.add_argument("--tokens-out", type=int, default=0)
    ap.add_argument("--usd", type=float, help="cost in USD, for page-billed engines")
    ap.add_argument("--inr-per-usd", type=float, default=88.0)
    ap.add_argument("--run-url", default="", help="the workflow run, so a row can be audited")
    ap.add_argument("--note", default="")
    args = ap.parse_args(argv)

    if args.report:
        report(read(args.ledger), args.since)
        return 0

    if not args.append:
        ap.print_help()
        return 2
    if not args.engine or not args.work:
        print("--append needs --engine and --work", file=sys.stderr)
        return 2

    usd = args.usd
    if usd is None:
        if args.model not in TOKEN_PRICES:
            print("no --usd given and no price on file for model %r.\n"
                  "Add it to TOKEN_PRICES after checking the vendor's page -- a\n"
                  "guessed price in a ledger is worse than a missing row."
                  % args.model, file=sys.stderr)
            return 2
        pin, pout = TOKEN_PRICES[args.model]
        usd = (args.tokens_in / 1e6) * pin + (args.tokens_out / 1e6) * pout

    row = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "engine": args.engine, "work": args.work, "source_pdf": args.source_pdf,
        "pages": args.pages, "model": args.model,
        "tokens_in": args.tokens_in, "tokens_out": args.tokens_out,
        "usd": round(usd, 6), "inr": round(usd * args.inr_per_usd, 4),
        "inr_per_usd": args.inr_per_usd, "prices_checked": PRICES_CHECKED,
        "run_url": args.run_url, "note": args.note,
    }
    append(row, args.ledger)
    print("logged: %s %s -- %d page(s), Rs %.4f" % (args.engine, args.work,
                                                    args.pages, row["inr"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
