#!/usr/bin/env python3
"""
fetch_archive_djvu.py -- an archive.org item's own OCR, staged as one more
engine to vote with.

Archive.org runs OCR over everything it holds and publishes the result as
<identifier>_djvu.txt. For Sanskrit that text is weak -- conjuncts are where
it fails, and conjuncts are where the meaning is: पादचतुष्टय comes back as
पादचतुटय, उत्कृष्टां as उत्कृष्ठां, विख्याताश्व as विख्याताइब, श्लिष्ट as
र्लिष्ट. It is not a reading of the book.

It is still worth having. It costs nothing, it arrives in seconds, and a
third engine turns a two-way disagreement into a vote. Where Sarvam and
Vision differ, this breaks the tie more often than not; where all three
agree, the reading is as good as settled.

Staged in the pages[] shape the review page already opens, split on the
edition's own running header so the page numbers are the book's.

    python3 tools/fetch_archive_djvu.py <archive.org-identifier> \
        --running-head "रुग्मिणीशविजयः" --out staged.json
"""
from __future__ import annotations

import argparse
import json
import re
import urllib.parse
import urllib.request

METADATA = "https://archive.org/metadata/%s"
DOWNLOAD = "https://archive.org/download/%s/%s"


def fetch(url: str, timeout: int = 120) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.read()


def item(identifier: str) -> dict:
    return json.loads(fetch(METADATA % identifier).decode("utf-8"))


def djvu_text(identifier: str, meta: dict) -> str:
    name = next((f["name"] for f in meta.get("files", [])
                 if f.get("format") == "DjVuTXT"), None)
    if not name:
        raise SystemExit("%s has no DjVuTXT -- archive.org ran no OCR on it" % identifier)
    return fetch(DOWNLOAD % (identifier, urllib.parse.quote(name))).decode("utf-8", "replace")


def split_pages(text: str, running_head: str) -> list[dict]:
    """Cut on the edition's running header, so page numbers are the book's."""
    if not running_head:
        return [{"page": 1, "ok": True, "text": text}]
    pattern = re.compile(r"\n\s*(\d{1,4})\s+%s\s*\n" % re.escape(running_head))
    marks = list(pattern.finditer(text))
    if not marks:
        return [{"page": 1, "ok": True, "text": text}]
    pages = []
    for n, mark in enumerate(marks):
        start = mark.end()
        stop = marks[n + 1].start() if n + 1 < len(marks) else len(text)
        body = text[start:stop].strip()
        if body:
            pages.append({"page": int(mark.group(1)), "ok": True, "text": body})
    return pages


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 2)[1])
    ap.add_argument("identifier")
    ap.add_argument("--running-head", default="",
                    help="the edition's running title, used to find page breaks")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    meta = item(args.identifier)
    md = meta.get("metadata", {})
    pages = split_pages(djvu_text(args.identifier, meta), args.running_head)
    doc = {
        "_readme": ("archive.org's OWN OCR of this item, staged as a third engine to "
                    "vote with -- NOT a reading of the book. It fails on conjuncts, "
                    "which is where Sanskrit carries its meaning. Use it to break ties "
                    "between Sarvam and Vision, never on its own."),
        "engine": "archive.org djvu",
        "source": "https://archive.org/details/%s" % args.identifier,
        "item_title": md.get("title", ""),
        "item_licence": md.get("licenseurl") or md.get("rights") or "(none stated)",
        "pages": pages,
    }
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(doc, handle, ensure_ascii=False, indent=1)
        handle.write("\n")
    chars = sum(len(p["text"]) for p in pages)
    print("%s\n  %d page(s), %s chars -> %s"
          % (md.get("title", args.identifier)[:70], len(pages), f"{chars:,}", args.out))
    print("  licence as stated by the item: %s" % doc["item_licence"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
