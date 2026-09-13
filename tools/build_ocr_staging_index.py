#!/usr/bin/env python3
"""
build_ocr_staging_index.py — list the staged OCR files for the admin pages.

admin/ocr-studio.html and admin/ocr-review.html open their file dropdown by
fetching data/ocr_staging/index.json. Nothing has ever written it, so the
dropdown has always fallen back to "— no index; use ?file=… —" and a person had
to know a path by heart. This writes it.

Only files a page can actually open are listed. tools/ocr_review_merge.py reads
four staged shapes — pages[], blocks[], entries[], shlokas[] — and raises on
anything else, and the studio's pagesOf() is narrower still, so a file carrying
none of those keys is not offered. dge/data/ocr_staging also holds working
files (a verification queue, a chat batch, an answers map) that are not staged
readings at all; listing them would put entries in the dropdown that open to an
error, which is worse than a short list.

Each entry carries what the pages want to show before opening anything: the
work, the shape, the engine that produced it (or "" when the file does not say,
which is itself worth seeing), and a page count.

    python3 tools/build_ocr_staging_index.py            # writes the index
    python3 tools/build_ocr_staging_index.py --check    # CI: fail if stale
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.join("data", "ocr_staging")
INDEX = os.path.join(ROOT, "index.json")

# The shapes tools/ocr_review_merge.py accepts. Keep in step with it.
READABLE_KEYS = ("pages", "blocks", "entries", "shlokas")


def shape_of(d: dict) -> str:
    """Which key holds this file's readings.

    `pages` is only the content when it is a list of page OBJECTS — the same
    test admin/ocr-studio.html's pagesOf() makes. The Vasu Siddhānta Kaumudī
    files carry `pages: [9, 28]`, a first/last page RANGE, beside the real
    content in `entries`; reading that as the content would report a 20-page
    range as "2 pages". And upanishad_tippani's summary.json files carry
    `pages` as an integer count — they are statistics, not staged readings, so
    they are not offered at all.
    """
    for k in READABLE_KEYS:
        v = d.get(k)
        if not isinstance(v, list) or not v:
            continue
        if k == "pages" and not isinstance(v[0], dict):
            continue
        return k
    return ""


def declared_range(d: dict):
    """`pages: [first, last]` beside another content key — worth keeping, since
    it is how a reviewer names the slice of the book this file covers."""
    v = d.get("pages")
    if isinstance(v, list) and len(v) == 2 and all(isinstance(x, int) for x in v):
        return list(v)
    src = d.get("source")
    if isinstance(src, dict) and isinstance(src.get("pages"), list) and src["pages"]:
        p = [x for x in src["pages"] if isinstance(x, int)]
        if p:
            return [min(p), max(p)]
    return None


def engine_of(d: dict) -> str:
    """Which engine produced this file — mirrors stagedEngine() in
    admin/js/ocr-studio-core.js, including the rule that a Gemini model name
    means Vision text that Gemini proofread, never a fourth engine."""
    hay = " ".join(
        str(d.get(k) or "").lower() for k in ("engine", "ocr_engine", "model")
    )
    if "sarvam" in hay:
        return "sarvam"
    if "tesseract" in hay:
        return "tesseract"
    if "vision" in hay or "gemini" in hay:
        return "vision"
    return ""


def count_pages(d: dict, shape: str) -> int:
    v = d.get(shape)
    if not isinstance(v, list):
        return 0
    if shape == "pages":
        return len(v)
    pages = {e.get("page") for e in v if isinstance(e, dict) and e.get("page") is not None}
    return len(pages)


def scan(root: str = ROOT) -> list[dict]:
    out = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in sorted(filenames):
            if not name.endswith(".json") or name == "index.json":
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            try:
                with open(full, encoding="utf-8") as fh:
                    d = json.load(fh)
            except (ValueError, OSError):
                continue  # not our business to police unreadable files here
            if not isinstance(d, dict):
                continue
            shape = shape_of(d)
            if not shape:
                continue
            entry = {
                "path": rel,
                "work": rel.split("/")[0],
                "shape": shape,
                "engine": engine_of(d),
                "pages": count_pages(d, shape),
                "bytes": os.path.getsize(full),
            }
            rng = declared_range(d)
            if rng:
                entry["range"] = rng
            out.append(entry)
    out.sort(key=lambda e: e["path"])
    return out


def build(root: str = ROOT) -> dict:
    files = scan(root)
    return {
        "_readme": "Generated by tools/build_ocr_staging_index.py — do not hand-edit. "
                   "Lists the staged OCR files admin/ocr-studio.html and "
                   "admin/ocr-review.html can open. Re-run after staging a new file.",
        "count": len(files),
        # `files` is a list of paths for the dropdown, which is all the pages
        # read; `entries` carries the detail, for anything that wants more.
        "files": [f["path"] for f in files],
        "entries": files,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=ROOT)
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if the index on disk is not what this would write")
    a = ap.parse_args()

    index_path = os.path.join(a.root, "index.json")
    fresh = build(a.root)
    text = json.dumps(fresh, ensure_ascii=False, indent=1) + "\n"

    if a.check:
        try:
            with open(index_path, encoding="utf-8") as fh:
                on_disk = fh.read()
        except OSError:
            print(f"{index_path} is missing; run tools/build_ocr_staging_index.py", file=sys.stderr)
            return 1
        if on_disk != text:
            print(f"{index_path} is stale; re-run tools/build_ocr_staging_index.py", file=sys.stderr)
            return 1
        print(f"{index_path} is up to date ({fresh['count']} staged files)")
        return 0

    os.makedirs(a.root, exist_ok=True)
    with open(index_path, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"wrote {index_path}: {fresh['count']} staged files")
    for e in fresh["entries"]:
        print(f"  {e['work']:28s} {e['shape']:8s} {e['engine'] or '(engine unnamed)':16s} "
              f"{e['pages']:4d} page(s)  {e['path']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
