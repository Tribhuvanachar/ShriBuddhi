#!/usr/bin/env python3
"""
link_english_commentary.py — merges OCR'd English commentary/translation
text into a kavya's per-canto (sarga) data.json files.

Built for the "Raghavendra Vijayam" ingestion: a published book's English
translation (scanned + OCR'd, then transcribed and cleaned by an AI reading
pass -- not this script's job, done upstream) needs to be linked, verse by
verse, to the Sanskrit mula text this corpus already holds. Kept general
enough (via --sarga-dir/--ocr-dir/--commentary-key) to reuse for a similar
OCR'd-book ingestion later.

Input shape expected per canto, produced by whatever did the OCR/transcribe
pass (see dge/PENDING.md's Raghavendra Vijaya writeup for how this file's
was produced -- parallel reading agents, not Gemini, since this is plain
transcription/OCR-cleanup, not the kind of task the corpus needs verifying
against itself):
  {"canto": N, "verse_count_found": M, "verses": {"1": "text"|null, ...},
   "uncertain_boundaries": ["free-text notes on any verse split that took
   real judgment, e.g. one translated paragraph covering several stanzas"]}

Target shape (the "legacy" DGE stotra format -- see dge/data/schemas.json's
_readme -- {metadata, shlokas: {"<n>": {sa, commentaries: {}}}}), one file
per sarga:
  shlokas["<n>"]["commentaries"][commentary_key] = "<verse's English text>"
  metadata["availableCommentaries"][commentary_key] = "<display label>"

Never invents text for a verse the OCR pass returned null for (leaves it
unlinked) -- this project's "don't fabricate" rule (dge/PROJECT_BRIEF.md)
applies here as much as anywhere: a missing translation is honest; a guessed
one is not.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save_json(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
        fh.write("\n")


def merge_canto(sarga_path: Path, ocr_path: Path, commentary_key: str,
                 display_label: str, force: bool) -> dict:
    """Returns a small report dict: {linked, skipped_existing, skipped_null,
    mismatched_count: bool}."""
    data = load_json(sarga_path)
    ocr = load_json(ocr_path)

    shlokas = data.get("shlokas")
    if not isinstance(shlokas, dict):
        raise ValueError(f"{sarga_path}: no top-level 'shlokas' dict -- not the expected legacy shape")

    expected_total = data.get("metadata", {}).get("totalShlokas")
    ocr_verses = ocr.get("verses", {})
    if expected_total is not None and len(ocr_verses) != expected_total:
        raise ValueError(
            f"{sarga_path}: metadata.totalShlokas={expected_total} but "
            f"{ocr_path} has {len(ocr_verses)} verse entries -- refusing to "
            f"merge a mismatched canto rather than silently linking wrong verses"
        )

    linked = 0
    skipped_existing = 0
    skipped_null = 0
    for n_str, text in ocr_verses.items():
        shloka = shlokas.get(n_str)
        if shloka is None:
            raise ValueError(f"{sarga_path}: OCR has verse {n_str} but this sarga has no such shloka")
        if not text or not text.strip():
            skipped_null += 1
            continue
        commentaries = shloka.setdefault("commentaries", {})
        if commentary_key in commentaries and not force:
            skipped_existing += 1
            continue
        commentaries[commentary_key] = text.strip()
        linked += 1

    if linked:
        avail = data.setdefault("metadata", {}).setdefault("availableCommentaries", {})
        avail[commentary_key] = display_label
        save_json(sarga_path, data)

    return {
        "linked": linked,
        "skipped_existing": skipped_existing,
        "skipped_null": skipped_null,
        "uncertain_boundaries": ocr.get("uncertain_boundaries", []),
    }


def run(sarga_dir: Path, ocr_dir: Path, commentary_key: str, display_label: str,
        cantos, force: bool) -> int:
    total_linked = 0
    for n in cantos:
        sarga_path = sarga_dir / f"sarga_{n}" / "data.json"
        ocr_path = ocr_dir / f"canto_{n}.json"
        if not sarga_path.exists():
            print(f"error: {sarga_path} does not exist", file=sys.stderr)
            return 1
        if not ocr_path.exists():
            print(f"error: {ocr_path} does not exist", file=sys.stderr)
            return 1
        report = merge_canto(sarga_path, ocr_path, commentary_key, display_label, force)
        total_linked += report["linked"]
        print(f"canto {n}: linked {report['linked']}, "
              f"skipped {report['skipped_existing']} already-linked, "
              f"{report['skipped_null']} blank")
        for note in report["uncertain_boundaries"]:
            print(f"  note: {note}")
    print(f"Total: {total_linked} verses linked across {len(cantos)} canto(s)")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sarga-dir", required=True, type=Path,
                    help="Directory containing sarga_N/data.json subfolders")
    p.add_argument("--ocr-dir", required=True, type=Path,
                    help="Directory containing canto_N.json OCR-transcript files")
    p.add_argument("--commentary-key", default="pavamanacharya_english",
                    help="Key under shlokas[n].commentaries to write into")
    p.add_argument("--display-label", default="Huli V. Pavamanacharya (English Translation)",
                    help="Human-readable label written to metadata.availableCommentaries")
    p.add_argument("--cantos", default="1-10",
                    help="Canto range or comma list, e.g. '1-10' or '1,3,5'")
    p.add_argument("--force", action="store_true",
                    help="Overwrite a verse's commentary even if already present")
    args = p.parse_args(argv)

    cantos = []
    for part in args.cantos.split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = part.split("-")
            cantos.extend(range(int(lo), int(hi) + 1))
        else:
            cantos.append(int(part))

    return run(args.sarga_dir, args.ocr_dir, args.commentary_key,
               args.display_label, cantos, args.force)


if __name__ == "__main__":
    raise SystemExit(main())
