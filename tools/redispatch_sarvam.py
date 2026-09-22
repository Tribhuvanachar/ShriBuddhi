#!/usr/bin/env python3
"""
redispatch_sarvam.py -- re-send the pages Sarvam refused, under a spend cap.

admin/config/ocr_sarvam_missing.json lists 5,342 pages across 27 works that
were requested and never came back -- mostly HTTP 402 when the prepaid
balance ran out mid-run. They were never delivered, so they were never
billed; re-sending them is a fresh charge.

There is no API key here and there does not need to be: the engine runs in
.github/workflows/ocr-sarvam.yml with SARVAM_API_KEY as a repository
secret, and this dispatches that workflow over the REST API. See
docs/CREDENTIALS.md.

THE CAP IS THE POINT. --budget is in rupees and is enforced before each
dispatch, not after: a work whose pages would take the running total past
the cap is skipped, and because works are taken smallest-first the cap
buys whole works rather than leaving several half-done. Nothing is
dispatched at all without --real, which is the only way to spend money.

  python3 tools/redispatch_sarvam.py                      # plan only
  python3 tools/redispatch_sarvam.py --real --budget 500
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MISSING = ROOT / "admin/config/ocr_sarvam_missing.json"
REPO = "Tribhuvanachar/ShriBuddhi"
WORKFLOW_ID = 356671665          # ocr-sarvam.yml
RATE = 0.44                      # Rs/page, admin/config/spend_report.json


def plan() -> list[dict]:
    doc = json.loads(MISSING.read_text())
    rows = []
    for work, files in doc["works"].items():
        pages = sum(f["pages"] for f in files)
        ranges, url, lang = [], None, "sa-IN"
        for f in files:
            ranges += f.get("ranges") or []
            url = url or f.get("url")
            lang = f.get("language") or lang
        if not url:
            continue
        rows.append({"work": work, "pages": pages, "ranges": ",".join(ranges),
                     "url": url, "language": lang, "cost": pages * RATE})
    # smallest first: a fixed budget then finishes whole works instead of
    # starting a big one it cannot pay for.
    return sorted(rows, key=lambda r: r["pages"])


def dispatch(row: dict, token: str, mode: str) -> tuple[bool, str]:
    body = json.dumps({"ref": "main", "inputs": {
        "pdf_url": row["url"], "pages": row["ranges"], "work_slug": row["work"],
        "language": row["language"], "output_format": "html", "mode": mode}})
    out = subprocess.run(
        ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "-X", "POST",
         "-H", f"Authorization: Bearer {token}",
         "-H", "Accept: application/vnd.github+json",
         "-H", "Content-Type: application/json",   # omit it and GitHub 415s
         f"https://api.github.com/repos/{REPO}/actions/workflows/{WORKFLOW_ID}/dispatches",
         "--data-binary", body],
        capture_output=True, text=True).stdout.strip()
    return out == "204", out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=float, default=500.0, help="rupees")
    ap.add_argument("--real", action="store_true",
                    help="actually dispatch, in real-run mode; without it "
                         "nothing is sent and nothing is spent")
    ap.add_argument("--sleep", type=float, default=2.0)
    args = ap.parse_args()

    rows = plan()
    total = sum(r["cost"] for r in rows)
    print(f"backlog: {len(rows)} works, {sum(r['pages'] for r in rows)} pages, Rs{total:.2f}")
    print(f"budget : Rs{args.budget:.2f}\n")

    token = os.environ.get("GITHUB_TOKEN", "")
    if args.real and not token:
        print("no GITHUB_TOKEN -- cannot dispatch", file=sys.stderr)
        return 1

    spent, sent, skipped = 0.0, 0, []
    for r in rows:
        if spent + r["cost"] > args.budget:
            skipped.append(r)
            continue
        mark = "DISPATCH" if args.real else "would send"
        print(f"  {mark} {r['work'][:44]:<44} {r['pages']:>4} pp  "
              f"Rs{r['cost']:>7.2f}  cum Rs{spent + r['cost']:>7.2f}")
        if args.real:
            ok, code = dispatch(r, token, "real-run")
            if not ok:
                print(f"      FAILED http {code} -- stopping rather than "
                      f"dispatching the rest blind")
                break
            sent += 1
            time.sleep(args.sleep)     # 10 requests a minute is Sarvam's limit
        spent += r["cost"]

    print(f"\nwithin budget : {len(rows) - len(skipped)} works, Rs{spent:.2f}")
    print(f"left over     : {len(skipped)} works, "
          f"{sum(r['pages'] for r in skipped)} pages, "
          f"Rs{sum(r['cost'] for r in skipped):.2f}")
    if skipped:
        print("  largest left:")
        for r in sorted(skipped, key=lambda x: -x["pages"])[:5]:
            print(f"      {r['work'][:44]:<44} {r['pages']:>4} pp  Rs{r['cost']:>7.2f}")
    if args.real:
        print(f"\ndispatched {sent} runs")
    else:
        print("\n(plan only -- pass --real to dispatch)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
