#!/usr/bin/env python3
"""
recover_ocr_sources.py -- rebuild admin/config/ocr_sources.json from what the
staging branches already record.

Every staged OCR file written by tools/sarvam_docai.py (and the Vision and
Gemini runners) carries a "source" object naming the PDF it was OCRed from.
That object is the only surviving record of provenance for most works: the
hand-maintained ocr_sources.json covers 42 of the 96 staged works, and the
rest -- all 31 Harikathamrtasara volumes among them -- have no recorded URL
at all. Without it a work cannot be re-OCRed, page-checked against the scan,
or re-derived if its staging branch is lost. docs/OCR_PENDING.md calls this
out; this closes it.

Nothing is fetched. git ls-tree and git cat-file read the remote-tracking
refs that are already on disk, so this runs offline and touches no branch.

Existing hand-written entries win: a recovered URL is only added for a work
that has none, and recovered rows are tagged so the two can be told apart.

  python3 tools/recover_ocr_sources.py            # report only
  python3 tools/recover_ocr_sources.py --write    # merge into ocr_sources.json
"""
from __future__ import annotations

import argparse
import collections
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "admin/config/ocr_sources.json"
URL_FIELDS = ("pdf", "pdf_url", "url", "archive_url")


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args],
                          capture_output=True, text=True).stdout


def staging_branches() -> list[str]:
    return [b.strip() for b in git("branch", "-r").splitlines()
            if "ocr-staging/" in b and "->" not in b]


def scan(branch: str) -> dict[str, dict]:
    """Every work directory on one branch, with the source URL its staged
    files agree on. Files within a work can disagree -- a volume re-OCRed
    from a re-uploaded scan, say -- so the most common URL wins and the
    count of disagreeing files is reported rather than hidden."""
    found: dict[str, dict] = {}
    listing = git("ls-tree", "-r", "--name-only", branch, "--", "data/ocr_staging/")
    by_work: dict[str, list[str]] = collections.defaultdict(list)
    for path in listing.split():
        parts = path.split("/")
        if len(parts) >= 4 and path.endswith(".json"):
            by_work[parts[2]].append(path)

    for work, files in by_work.items():
        if work.startswith("_"):
            continue
        urls: collections.Counter = collections.Counter()
        pages: set = set()
        for path in files:
            try:
                blob = json.loads(git("cat-file", "-p", f"{branch}:{path}"))
            except (json.JSONDecodeError, ValueError):
                continue
            # Some staged shapes are a bare list of pages rather than an
            # object with a header; those carry no source block at all.
            if not isinstance(blob, dict):
                continue
            src = blob.get("source")
            if not isinstance(src, dict):
                continue
            for field in URL_FIELDS:
                if src.get(field):
                    urls[src[field]] += 1
                    break
            for p in src.get("pages") or []:
                pages.add(p)
        # A few staged files record a bare filename where a URL belongs.
        # That is not provenance -- it cannot be fetched -- so it is dropped
        # rather than written in as though the source were known.
        urls = collections.Counter(
            {u: n for u, n in urls.items() if u.startswith(("http://", "https://"))})
        if urls:
            top, n = urls.most_common(1)[0]
            found[work] = {
                "pdf_url": top,
                "pages_ocred": len(pages) or None,
                "recovered_from": f"{branch}",
                "note": "URL read back from the staged files' source field",
            }
            if len(urls) > 1:
                found[work]["conflicting_urls"] = len(urls) - 1
    return found


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true",
                    help="merge into admin/config/ocr_sources.json")
    args = ap.parse_args()

    recovered: dict[str, dict] = {}
    for br in staging_branches():
        for work, row in scan(br).items():
            recovered.setdefault(work, row)

    doc = json.loads(SOURCES.read_text())
    works = doc.setdefault("works", {})
    have = {k for k, v in works.items() if any(v.get(f) for f in URL_FIELDS)}

    new = {k: v for k, v in recovered.items() if k not in have}
    print(f"staged works with a recoverable URL : {len(recovered)}")
    print(f"already recorded by hand            : {len(have)}")
    print(f"would add                           : {len(new)}")
    for k in sorted(new):
        print(f"    {k:<48} {new[k]['pdf_url']}")

    still = sorted(set(recovered) | have)
    missing = [w for w in recovered if w not in have and w not in new]
    if missing:
        print(f"unresolved: {missing}")

    if args.write and new:
        for k, v in new.items():
            works[k] = {kk: vv for kk, vv in v.items() if vv is not None}
        doc["recovered_on"] = "2026-09-21"
        SOURCES.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
        print(f"\nwrote {SOURCES.relative_to(ROOT)} -- {len(works)} works now carry a URL")
    elif args.write:
        print("\nnothing to add")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
