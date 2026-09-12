#!/usr/bin/env python3
"""
merge_staged_commentary.py — Stage 2 of the server-side OCR pipeline:
reads a staged JSON file (produced by tools/gemini_ocr_commentary.py) and
merges it into the target canto's data.json.

Kept separate from Stage 1 on purpose: a staged file can be inspected,
downloaded, emailed, or handed to a different reviewer before anything
touches the corpus. This script (or the browser admin tool's own "push"
button, which writes the same staged-file shape) is the only thing that
actually commits OCR'd commentary text into a kavya.

Classification-gated merge: Gemini's own "accept" / "review" / "unresolved"
self-classification (set during Stage 1's proofreading) decides what
merges automatically. "accept" always merges. "review" and "unresolved"
are held back by default (reported, not merged) -- pass --include-review /
--include-unresolved to merge them anyway.

Never invents a shloka: verse count is hard-validated against the target
canto's metadata.totalShlokas before anything is written, matching this
project's "don't fabricate" rule (PROJECT_BRIEF.md rule 4) and
link_english_commentary.py's existing convention.

Usage:
  python3 tools/merge_staged_commentary.py --staged data/ocr_staging/raghavendra_vijaya/tika_x_canto1_pages12-54.json \
      --sarga-dir data/DvaitaVedanta/Itara/Kavya/raghavendra_vijaya
  python3 tools/merge_staged_commentary.py --staged ... --sarga-dir ... --include-review --force
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from link_english_commentary import load_json, save_json  # noqa: E402


def merge_shlokas(sarga_path: Path, shlokas: list[dict], commentary_key: str, display_label: str,
                   include_review: bool, include_unresolved: bool, force: bool,
                   content_field: str = "commentary") -> dict:
    """Validates shloka count/numbering against the canto's own metadata
    before writing anything -- refuses a mismatched merge rather than
    silently attaching commentary to the wrong verse."""
    data = load_json(sarga_path)
    target_shlokas = data.get("shlokas")
    if not isinstance(target_shlokas, dict):
        raise ValueError(f"{sarga_path}: no top-level 'shlokas' dict -- not the expected legacy shape")

    expected_total = data.get("metadata", {}).get("totalShlokas")
    numbers = [s.get("number") for s in shlokas if s.get("number") is not None]
    if expected_total is not None and numbers and (min(numbers) < 1 or max(numbers) > expected_total):
        raise ValueError(
            f"{sarga_path}: metadata.totalShlokas={expected_total} but staged data has "
            f"shloka numbers {min(numbers)}-{max(numbers)} -- refusing to merge a mismatched "
            f"canto/page-range rather than silently linking wrong verses"
        )

    linked = held_review = held_unresolved = skipped_existing = skipped_blank = 0
    for s in shlokas:
        n = s.get("number")
        if n is None:
            continue
        n_str = str(n)
        shloka = target_shlokas.get(n_str)
        if shloka is None:
            raise ValueError(f"{sarga_path}: staged data has verse {n_str} but this canto has no such shloka")

        classification = s.get("classification", "unresolved")
        if classification == "review" and not include_review:
            held_review += 1
            continue
        if classification == "unresolved" and not include_unresolved:
            held_unresolved += 1
            continue

        text = (s.get(content_field) or "").strip()
        if not text:
            skipped_blank += 1
            continue
        commentaries = shloka.setdefault("commentaries", {})
        if commentary_key in commentaries and not force:
            skipped_existing += 1
            continue
        commentaries[commentary_key] = text
        linked += 1

    if linked:
        avail = data.setdefault("metadata", {}).setdefault("availableCommentaries", {})
        avail[commentary_key] = display_label
        save_json(sarga_path, data)

    return {
        "linked": linked, "held_review": held_review, "held_unresolved": held_unresolved,
        "skipped_existing": skipped_existing, "skipped_blank": skipped_blank,
    }


def merge_staged_file(staged_path: Path, sarga_dir: Path, include_review: bool, include_unresolved: bool,
                       force: bool) -> dict:
    with open(staged_path, encoding="utf-8") as fh:
        staged = json.load(fh)

    canto = staged.get("canto")
    if canto is None:
        raise ValueError(f"{staged_path}: no 'canto' field -- not a valid staged-commentary file")
    sarga_path = sarga_dir / f"sarga_{canto}" / "data.json"
    if not sarga_path.exists():
        raise FileNotFoundError(f"{sarga_path} does not exist")

    return merge_shlokas(
        sarga_path, staged.get("shlokas") or [], staged["commentary_key"], staged["display_label"],
        include_review, include_unresolved, force, staged.get("content_field", "commentary"),
    )


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--staged", required=True, type=Path, help="Staged JSON file from gemini_ocr_commentary.py")
    p.add_argument("--sarga-dir", required=True, type=Path)
    p.add_argument("--include-review", action="store_true")
    p.add_argument("--include-unresolved", action="store_true")
    p.add_argument("--force", action="store_true")
    args = p.parse_args(argv)

    if not args.staged.exists():
        print(f"error: {args.staged} does not exist", file=sys.stderr)
        return 1

    try:
        report = merge_staged_file(args.staged, args.sarga_dir, args.include_review,
                                    args.include_unresolved, args.force)
    except (ValueError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    print(f"linked {report['linked']}, held back {report['held_review']} review + "
          f"{report['held_unresolved']} unresolved (rerun with --include-review/--include-unresolved), "
          f"skipped {report['skipped_existing']} already-linked, {report['skipped_blank']} blank")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
