#!/usr/bin/env python3
"""
update_archive_pdf_catalog.py -- append or strike one entry in
data/catalogs/archive_pdf_catalog.json, the ledger of every PDF/chapter-set
.github/workflows/archive-upload-pdf.yml has sent to archive.org.

Why this file exists rather than editing the ledger inline in the workflow:
the ledger is a brand-new file this project owns outright (no pre-existing
one-row-per-line format to preserve, unlike a data/*.json grantha file), but
it should still only ever be written ONE way, so a hand-run invocation and
the workflow's own invocation can never drift into two different shapes.
That is the whole job of this script -- load, modify exactly one entry,
write back with a stable, deterministic format (sorted entries by
uploadedAt, indent=2, ensure_ascii=False).

    python3 tools/update_archive_pdf_catalog.py --append \
        --identifier dge_tattvavada_itara_kavya_raghavendra_vijaya \
        --taxonomy-path Tattvavada/Itara/Kavya/raghavendra_vijaya \
        --title "Raghavendra Vijaya" --author "Narayana Panditacharya" \
        --files raghavendra_vijaya.pdf --sample false --run-id 123456

    python3 tools/update_archive_pdf_catalog.py --strike dge_some_identifier
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = ROOT / "data/catalogs/archive_pdf_catalog.json"

README = [
    "APPEND-ONLY ledger of every PDF/chapter-set .github/workflows/",
    "archive-upload-pdf.yml has sent to archive.org. Written by tools/",
    "update_archive_pdf_catalog.py -- do not hand-edit; re-run that script.",
    "",
    "identifier is derived from taxonomyPath by the workflow itself",
    "(dge_<taxonomy path, lowercased, '/' and spaces -> '_'>), so this",
    "ledger is a record of what WAS uploaded, not the source of truth for",
    "what a path resolves to -- a future session can always recompute the",
    "identifier from taxonomyPath without reading this file at all. What",
    "this file is for: knowing what already exists on archive.org before",
    "uploading it again, and a human-readable log of every upload.",
    "",
    "struck:true marks an entry whose archive.org item was deleted (mode=",
    "delete) -- kept, not removed, so the ledger also records retractions.",
]


def _load() -> dict:
    if not CATALOG_PATH.exists():
        return {"_readme": README, "entries": []}
    with CATALOG_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def _save(doc: dict) -> None:
    doc["entries"].sort(key=lambda e: e.get("uploadedAt", ""))
    text = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
    # Round-trip check before writing, same discipline as every other
    # data-file edit in this project: never write something that doesn't
    # parse back to exactly what was intended.
    assert json.loads(text) == doc
    CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CATALOG_PATH.open("w", encoding="utf-8") as f:
        f.write(text)


def cmd_append(args: argparse.Namespace) -> None:
    doc = _load()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    files = [f for f in (args.files or "").split(",") if f]
    entry = {
        "identifier": args.identifier,
        "taxonomyPath": args.taxonomy_path,
        "title": args.title,
        "author": args.author or None,
        "files": files,
        "sample": str(args.sample).lower() == "true",
        "uploadedAt": now,
        "runId": args.run_id,
        "detailsUrl": f"https://archive.org/details/{args.identifier}",
        "struck": False,
    }
    doc["entries"] = [e for e in doc["entries"] if e.get("identifier") != args.identifier]
    doc["entries"].append(entry)
    _save(doc)
    print(f"recorded {args.identifier} ({'sample' if entry['sample'] else 'real'}, {len(files)} file(s))")


def cmd_strike(identifier: str) -> None:
    doc = _load()
    found = False
    for e in doc["entries"]:
        if e.get("identifier") == identifier:
            e["struck"] = True
            found = True
    if not found:
        print(f"no ledger entry for {identifier} — nothing to strike")
        return
    _save(doc)
    print(f"struck {identifier}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--append", action="store_true")
    p.add_argument("--strike", metavar="IDENTIFIER")
    p.add_argument("--identifier")
    p.add_argument("--taxonomy-path")
    p.add_argument("--title")
    p.add_argument("--author", default="")
    p.add_argument("--files", default="")
    p.add_argument("--sample", default="false")
    p.add_argument("--run-id", default="")
    args = p.parse_args()

    if args.strike:
        cmd_strike(args.strike)
        return 0
    if args.append:
        missing = [n for n in ("identifier", "taxonomy_path", "title") if not getattr(args, n)]
        if missing:
            p.error(f"--append requires: {', '.join('--' + m.replace('_', '-') for m in missing)}")
        cmd_append(args)
        return 0
    p.error("pass --append or --strike")
    return 2


if __name__ == "__main__":
    sys.exit(main())
