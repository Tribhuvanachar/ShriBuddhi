#!/usr/bin/env python3
"""
ocr_batch.py — the gate every paid OCR batch goes through.

docs/OCR_RUNBOOK.md is the prose. This is the part that cannot be skipped.

The distinction matters. On 13 Sep 2026 a commit step lost OCR that had already been
paid for, and the cause was written into a comment directly above that step. On
18 Sep 2026 that comment was read and 130 jobs were dispatched anyway; the same class
of failure discarded 3,474 billed pages. A note describing how work gets lost is not a
control. So the checks live here, they return a non-zero exit code, and the dispatch
path calls them first.

    python3 tools/ocr_batch.py --preflight  --plan plan.tsv --engine sarvam
    python3 tools/ocr_batch.py --record-pilot <slug>
    python3 tools/ocr_batch.py --reconcile  --plan plan.tsv --staged staged.tsv

A plan row is:   <work_slug>\t<pdf_url>\t<first>-<last>
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys

PAGE_CAP = {"sarvam": 200, "vision": 2000}
RECEIPTS = "admin/config/ocr_pilot_receipts.json"

# GitHub Actions is FREE AND UNLIMITED on public repositories and metered on private
# ones: 2,000 minutes a month on GitHub Free, then it stops (a free account's spending
# limit is $0, so it blocks rather than bills). Measured on this project, one OCR run
# costs about six billable minutes whatever the engine, since the time goes on checkout,
# apt, the download and the commit rather than on the pages.
#
# This is here because I costed Sarvam per page, Vision per page and Gemini per token,
# and treated CI as free because "GitHub is free" -- true for public repos, false for
# private. 230 runs in September consumed about 1,370 of the 2,000 minutes and stopped
# every workflow in the account: OCR, deploys, nightly sync. The arithmetic that would
# have caught it is one multiplication, and it now happens before every batch.
MINUTES_PER_RUN = 6.0
FREE_PRIVATE_MINUTES = 2000

# Faults that have already cost money once. Each is a property of the workflow file
# rather than of the batch, so each is checked against the file itself.
WORKFLOW_REQUIREMENTS = {
    "sarvam": (
        ".github/workflows/ocr-sarvam.yml",
        [
            ("inputs.pages }}",
             "concurrency key must include the page range",
             "Without it every chunk of one book shares a group, GitHub keeps only ONE "
             "pending run per group, and queuing chunk 3 cancels chunk 2. 39 of 129 runs, "
             "7,800 pages, vanished this way on 18 Sep 2026 while the batch looked sent."),
            ("push rejected",
             "commit step must retry a rejected push",
             "Two chunks finishing together both fetch, both commit, and the second push "
             "is a non-fast-forward. Rejected, job fails, and the pages already paid for "
             "are discarded. 3,474 billed pages on 18 Sep 2026."),
        ],
    ),
    "vision": (
        ".github/workflows/ocr-vision-pages.yml",
        [
            ("PyMuPDF counts 0 pages",
             "download must verify the PDF parses, not just its magic bytes",
             "`file` reads the header only, so a truncated download passes and the "
             "renderer then dies on 'page 1 not in document'."),
        ],
    ),
}


def read_plan(path):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 3:
                raise SystemExit("plan line %d has %d fields, need 3" % (n, len(parts)))
            slug, url, pages = parts[0], parts[1], parts[2]
            m = re.match(r"^(\d+)-(\d+)$", pages)
            if not m:
                raise SystemExit("plan line %d: page range %r is not <first>-<last>" % (n, pages))
            rows.append({"slug": slug, "url": url, "first": int(m.group(1)),
                         "last": int(m.group(2)), "pages": pages})
    return rows


def load_receipts():
    try:
        with open(RECEIPTS, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {"_readme": "Proof that the paid path was run end to end on a small "
                           "volume. ocr_batch.py --preflight requires one dated today.",
                "pilots": []}


def preflight(rows, engine, today=None, repo_root=".", runner="private"):
    """[] when it is safe to spend money, else the reasons it is not."""
    problems = []
    today = today or datetime.date.today().isoformat()

    seen = set()
    for r in rows:
        key = (r["slug"], r["pages"])
        if key in seen:
            problems.append("duplicate chunk: %s %s appears twice in the plan"
                            % (r["slug"], r["pages"]))
        seen.add(key)

    # Slug collisions across DIFFERENT works are the dangerous kind: same staging
    # branch, silent overwrite. Same slug with different ranges is normal chunking.
    by_slug = {}
    for r in rows:
        by_slug.setdefault(r["slug"], set()).add(r["url"])
    for slug, urls in sorted(by_slug.items()):
        if len(urls) > 1:
            problems.append("slug %r maps to %d different PDFs — they would share one "
                            "staging branch and overwrite each other" % (slug, len(urls)))

    cap = PAGE_CAP.get(engine)
    if cap:
        for r in rows:
            n = r["last"] - r["first"] + 1
            if n > cap:
                problems.append("%s %s is %d pages, over the %s cap of %d"
                                % (r["slug"], r["pages"], n, engine, cap))
            if n <= 0:
                problems.append("%s %s is an empty range" % (r["slug"], r["pages"]))

    path, checks = WORKFLOW_REQUIREMENTS.get(engine, (None, []))
    if path:
        full = os.path.join(repo_root, path)
        try:
            text = open(full, encoding="utf-8").read()
        except OSError:
            problems.append("cannot read %s to check it is safe to run" % path)
            text = ""
        for needle, what, why in checks:
            if needle not in text:
                problems.append("%s: %s\n      %s" % (path, what, why))

    # Actions is free and unlimited on a PUBLIC repository. Where the batch will run
    # decides whether the minute budget is a wall or a note, so it is an input rather
    # than an assumption -- and it defaults to private, the answer that costs money if
    # you get it wrong.
    minutes = len(rows) * MINUTES_PER_RUN
    if runner == "private" and minutes > FREE_PRIVATE_MINUTES * 0.10:
        problems.append(
            "this batch is %d runs, about %.0f GitHub Actions minutes. A private repo gets "
            "%d free minutes a MONTH and then every workflow in the account stops -- OCR, "
            "deploys, nightly sync. This batch alone is %.0f%% of that.\n"
            "      Tell the lead the minute cost before dispatching, not only the page cost. "
            "Actions on a PUBLIC repo is free and unlimited; a private repo is not."
            % (len(rows), minutes, FREE_PRIVATE_MINUTES,
               100.0 * minutes / FREE_PRIVATE_MINUTES))

    pilots = load_receipts().get("pilots", [])
    if not any(p.get("date") == today and p.get("engine") == engine for p in pilots):
        problems.append(
            "no %s pilot recorded for %s. Run ONE small volume as a real run, confirm the "
            "staged pages equal the pages requested, then --record-pilot. A dry run does "
            "not count: it never calls the paid API and never commits." % (engine, today))
    return problems


def reconcile(rows, staged):
    """What was asked for, what landed, and what the gap cost.

    staged: {slug: set of page numbers actually on the staging branch}
    """
    want = {}
    for r in rows:
        want.setdefault(r["slug"], set()).update(range(r["first"], r["last"] + 1))
    report, missing_total, want_total = [], 0, 0
    for slug in sorted(want):
        w = want[slug]
        g = staged.get(slug, set())
        miss = w - g
        want_total += len(w)
        missing_total += len(miss)
        if miss:
            report.append({"slug": slug, "requested": len(w), "staged": len(w & g),
                           "missing": len(miss),
                           "missing_pages": sorted(miss)[:10]})
    return {"requested": want_total, "staged": want_total - missing_total,
            "missing": missing_total, "incomplete": report}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 2)[1])
    ap.add_argument("--plan")
    ap.add_argument("--engine", default="sarvam", choices=sorted(PAGE_CAP))
    ap.add_argument("--preflight", action="store_true")
    ap.add_argument("--record-pilot", default="")
    ap.add_argument("--reconcile", action="store_true")
    ap.add_argument("--staged", default="", help="TSV: slug<TAB>first-last, what actually landed")
    ap.add_argument("--runner", default="private", choices=["private", "public"],
                    help="where the batch runs. public = Actions is free and unlimited.")
    args = ap.parse_args(argv)

    if args.record_pilot:
        data = load_receipts()
        data.setdefault("pilots", []).append(
            {"slug": args.record_pilot, "engine": args.engine,
             "date": datetime.date.today().isoformat()})
        os.makedirs(os.path.dirname(RECEIPTS), exist_ok=True)
        with open(RECEIPTS, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
        print("pilot recorded: %s (%s)" % (args.record_pilot, args.engine))
        return 0

    if args.preflight:
        if not args.plan:
            print("--preflight needs --plan", file=sys.stderr)
            return 2
        problems = preflight(read_plan(args.plan), args.engine, runner=args.runner)
        if problems:
            print("REFUSING TO DISPATCH — %d problem(s):" % len(problems))
            for p in problems:
                print("  * %s" % p)
            return 1
        rows = read_plan(args.plan)
        mins = len(rows) * MINUTES_PER_RUN
        print("preflight clear: %d chunk(s), %d page(s), engine %s"
              % (len(rows), sum(r["last"] - r["first"] + 1 for r in rows), args.engine))
        print("  cost to state to the lead BEFORE dispatch:")
        print("    %d OCR pages billed by %s" % (sum(r["last"] - r["first"] + 1 for r in rows), args.engine))
        if args.runner == "public":
            print("    ~%.0f GitHub Actions minutes — free, the runner is a public repo" % mins)
        else:
            print("    ~%.0f GitHub Actions minutes = %.0f%% of a private repo's %d free minutes/month"
                  % (mins, 100.0 * mins / FREE_PRIVATE_MINUTES, FREE_PRIVATE_MINUTES))
        return 0

    if args.reconcile:
        staged = {}
        if args.staged:
            for line in open(args.staged, encoding="utf-8"):
                line = line.rstrip("\n")
                if not line:
                    continue
                slug, rng = line.split("\t")[:2]
                m = re.match(r"^(\d+)-(\d+)$", rng)
                if m:
                    staged.setdefault(slug, set()).update(
                        range(int(m.group(1)), int(m.group(2)) + 1))
        out = reconcile(read_plan(args.plan), staged)
        print("requested %d  staged %d  missing %d  (%.1f%% complete)"
              % (out["requested"], out["staged"], out["missing"],
                 100.0 * out["staged"] / out["requested"] if out["requested"] else 0.0))
        for row in out["incomplete"]:
            print("  %-46s %5d/%-5d  missing %d" % (row["slug"][:46], row["staged"],
                                                    row["requested"], row["missing"]))
        return 1 if out["missing"] else 0

    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
