#!/usr/bin/env python3
"""
work_forecast.py -- what is still to do, in pages, tokens and rupees, by task.

Answers the planning question the ledger cannot: the ledger records what was
spent, this projects what is left. Both matter, and they must agree on their
rates -- so the rates here are MEASURED from admin/config/cost_ledger.jsonl
wherever the ledger has enough evidence, and only fall back to a stated
assumption where it does not. Every line of output says which it used.

    python3 tools/work_forecast.py
    python3 tools/work_forecast.py --budget-inr 10000   # what that buys

Categories are the real shapes of work in this project, not a generic list:

  ocr.sarvam.redo     pages already requested that came back empty
  ocr.sarvam.first    works Vision has read and Sarvam has not
  gemini.conflicts    pages where the two engines disagree (~7% of a work)
  gemini.wholesale    text with only ONE reading, so no conflict filter exists
                      -- the expensive shape, and the one to avoid

A forecast that quietly reuses an estimate as if it were a measurement is how
the last two top-ups disappeared. Where this file guesses, it says so on the
same line as the number.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

LEDGER = "admin/config/cost_ledger.jsonl"
MISSING = "admin/config/ocr_sarvam_missing.json"
SOURCES = "admin/config/ocr_sources.json"

# Used only where the ledger has no evidence. Stated, never silently applied.
ASSUMED = {
    "sarvam_inr_per_page": 0.44,      # list price at Rs88/USD
    "vision_inr_per_page": 0.132,
    "gemini_inr_per_page": None,      # deliberately absent: measure it
    "chars_per_conflict_page": 4190,  # measured over the 1,501 real conflicts
    "tokens_per_char": (0.6, 1.4),    # closed by the calibration run
}


def measured_rate(rows, engine):
    """INR per page for an engine, from the ledger, or None if too thin."""
    pages = sum(r.get("pages", 0) for r in rows if r.get("engine") == engine)
    inr = sum(r.get("inr", 0.0) for r in rows if r.get("engine") == engine)
    if pages < 100:
        return None, pages
    return inr / pages, pages


def gemini_measured(rows):
    """INR per page and tokens per page for Gemini, from real runs only."""
    g = [r for r in rows if r.get("engine") == "gemini" and r.get("pages")]
    pages = sum(r["pages"] for r in g)
    if pages < 20:
        return None, None, pages
    inr = sum(r.get("inr", 0.0) for r in g)
    toks = sum(r.get("tokens_in", 0) + r.get("tokens_out", 0) for r in g)
    return inr / pages, toks / pages, pages


def staging_state(root="."):
    """Per work: vision pages present, sarvam pages that actually succeeded."""
    try:
        brs = [b.split("origin/ocr-staging/")[1]
               for b in subprocess.check_output(["git", "branch", "-r"], text=True,
                                                cwd=root).split()
               if b.startswith("origin/ocr-staging/")]
    except Exception:  # noqa: BLE001
        return {}
    out = {}
    for b in brs:
        try:
            names = subprocess.check_output(
                ["git", "ls-tree", "-r", "--name-only", "origin/ocr-staging/%s" % b,
                 "--", "data/ocr_staging/%s" % b], text=True, cwd=root).split()
        except Exception:  # noqa: BLE001
            continue
        v = s = 0
        for n in names:
            base = os.path.basename(n)
            if not (base.startswith("vision_") or base.startswith("sarvam_")):
                continue
            try:
                d = json.loads(subprocess.check_output(
                    ["git", "show", "origin/ocr-staging/%s:%s" % (b, n)], cwd=root))
            except Exception:  # noqa: BLE001
                continue
            if base.startswith("sarvam_"):
                s += (d.get("usage") or {}).get("pages_succeeded", 0)
            else:
                v += len([p for p in d.get("pages") or [] if (p.get("text") or "").strip()])
        if v or s:
            out[b] = {"vision": v, "sarvam": s}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 2)[1])
    ap.add_argument("--ledger", default=LEDGER)
    ap.add_argument("--root", default=".")
    ap.add_argument("--budget-inr", type=float)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    rows = []
    p = os.path.join(args.root, args.ledger)
    if os.path.exists(p):
        rows = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]

    sar_rate, sar_pages = measured_rate(rows, "sarvam")
    vis_rate, vis_pages = measured_rate(rows, "vision")
    gem_rate, gem_tpp, gem_pages = gemini_measured(rows)

    tasks = []

    # 1. Sarvam pages asked for that came back empty.
    mp = os.path.join(args.root, MISSING)
    if os.path.exists(mp):
        d = json.load(open(mp, encoding="utf-8"))
        n = d.get("total_pages_missing", 0)
        tasks.append(("ocr.sarvam.redo", "%d works" % len(d.get("works", {})), n,
                      sar_rate or ASSUMED["sarvam_inr_per_page"], bool(sar_rate), 0))

    # 2. Works Vision has read and Sarvam has not.
    st = staging_state(args.root)
    first = {k: v for k, v in st.items() if v["vision"] and not v["sarvam"]}
    if first:
        n = sum(v["vision"] for v in first.values())
        tasks.append(("ocr.sarvam.first", "%d works" % len(first), n,
                      sar_rate or ASSUMED["sarvam_inr_per_page"], bool(sar_rate), 0))

    # 3. Conflicts, for works that have BOTH readings.
    both = {k: v for k, v in st.items() if v["vision"] and v["sarvam"]}
    cmp_pages = sum(min(v["vision"], v["sarvam"]) for v in both.values())
    # 7.3% measured over 20,442 real page comparisons, not assumed.
    conflict_pages = int(round(cmp_pages * 0.073))
    tasks.append(("gemini.conflicts", "%d works, %d pages compared"
                  % (len(both), cmp_pages), conflict_pages,
                  gem_rate, bool(gem_rate), conflict_pages * (gem_tpp or 0)))

    # 4. Conflicts that will EXIST once the pending Sarvam runs land.
    future = sum(v["vision"] for v in first.values())
    if future:
        fc = int(round(future * 0.073))
        tasks.append(("gemini.conflicts.future", "after ocr.sarvam.first lands",
                      fc, gem_rate, bool(gem_rate), fc * (gem_tpp or 0)))

    print("PENDING WORK")
    print("%-26s %-34s %8s %11s %13s" % ("task", "scope", "pages", "INR/page", "INR"))
    total = 0.0
    unknown = []
    for name, scope, pages, rate, measured, toks in tasks:
        if rate is None:
            unknown.append(name)
            print("%-26s %-34s %8d %11s %13s" % (name, scope[:34], pages,
                                                 "unmeasured", "-- see below"))
            continue
        cost = pages * rate
        total += cost
        print("%-26s %-34s %8d %11.4f %13.2f%s"
              % (name, scope[:34], pages, rate, cost, "" if measured else "  (assumed)"))
    print("%-26s %-34s %8s %11s %13.2f" % ("TOTAL (priced lines)", "", "", "", total))

    print("\nrates used:")
    print("  sarvam  Rs%.4f/page  %s (%d pages of evidence)"
          % (sar_rate or ASSUMED["sarvam_inr_per_page"],
             "MEASURED from the ledger" if sar_rate else "ASSUMED list price", sar_pages))
    print("  vision  Rs%.4f/page  %s (%d pages of evidence)"
          % (vis_rate or ASSUMED["vision_inr_per_page"],
             "MEASURED from the ledger" if vis_rate else "ASSUMED list price", vis_pages))
    if gem_rate:
        print("  gemini  Rs%.4f/page, %.0f tokens/page  MEASURED over %d page(s)"
              % (gem_rate, gem_tpp, gem_pages))
    else:
        print("  gemini  NOT MEASURED -- %d page(s) of evidence, need 20." % gem_pages)
        print("          Run the calibration chunk and this line prices itself.")
        lo, hi = ASSUMED["tokens_per_char"]
        cp = ASSUMED["chars_per_conflict_page"]
        print("          Until then, only a range is honest: %.0f-%.0f tokens/page"
              % (cp * lo, cp * hi))

    if args.budget_inr and gem_rate:
        print("\nRs%.0f buys %d conflict page(s) at the measured rate."
              % (args.budget_inr, int(args.budget_inr / gem_rate)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
