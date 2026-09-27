#!/usr/bin/env python3
"""Turn the segmented Vaidika Svara Prakaraṇam into the Prātiśākhya shelf files.

ವೈದಿಕ ಸ್ವರ ಪ್ರಕರಣಮ್ { ಶೌನಕೀಯಂ, ಪಾಣಿನೀಯಂ ಚ }. Output takes the shape the Kāvya
shelf uses, because that shape carries a named commentary per unit and the
reader renders it as a chip -- which is what the ಅರ್ಥ gloss needs:

    data/vedanga/shiksha/pratishakhya/vaidika_svara_prakarana/<section>/data.json
    {metadata: {...}, shlokas: {"1": {sa, commentaries}, ...}}

It sits under pratishakhya because that is what the book says it is: its first
part is headed ಅಥ ಶೌನಕೋಕ್ತಮ್ ಋಗ್ವೇದೀಯ-ಸ್ವರಪಟಲಮ್ ( ಋಕ್ ಪ್ರಾತಿಶಾಖ್ಯೋಕ್ತಮ್ ) --
the svara section of the Ṛk Prātiśākhya -- beside rigveda_pratishakhya and
shaunakiya_chaturadhyayika.

TWO THINGS TRAVEL WITH THE TEXT because the book supplies them and nothing
here should invent them:

  * Each sūtra's TOPIC, from the book's own ಅಥ ವಿಷಯಾನುಕ್ರಮಣಿಕಾ on pages 8-12.
    86 of the 99 are named there.
  * The PROSE BETWEEN the sūtras -- ಉಪಕ್ರಮ- runs six pages and ಭಾಗ-೩ thirteen.
    That is a fifth of the Kannada in the book, and dropping it would leave no
    trace, so it is emitted as its own section rather than discarded.

    python3 tools/vaidika_svara/write_layers.py
    python3 tools/vaidika_svara/write_layers.py --write
"""

from __future__ import annotations

import argparse
import collections
import importlib.util
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import segment as seg  # noqa: E402

TARGET = pathlib.Path("data/vedanga/shiksha/pratishakhya/vaidika_svara_prakarana")
COMMENTARY_KEY = "artha"
COMMENTARY_TITLE = "ಅರ್ಥ — ಕನ್ನಡ ವಿವರಣೆ"
PART_LABEL = {"saunakiya": "ಶೌನಕೀಯಮ್", "paniniya": "ಪಾಣಿನೀಯಮ್"}
# Bibliographic only, from the book's own imprint page. No scan URL and no
# origin breadcrumb: credits belong in the site footer, given once.
SOURCE = {
    "edition": "ವೈದಿಕ ಸ್ವರ ಪ್ರಕರಣಮ್ { ಶೌನಕೀಯಂ, ಪಾಣಿನೀಯಂ ಚ } — Vaidika Svara "
               "Prakaraṇam, edited and translated by Vidvān Kadri Prabhākara "
               "Aḍiga",
    "publisher": "ಶ್ರೀ ತತ್ವಸಂಶೋಧನ ಸಂಸತ್, ಶ್ರೀ ಪಲಿಮಾರು ಮಠ, ಉಡುಪಿ",
    "edition_year": 2011,
    "isbn": "978-81-909776-6-1",
    "language": "Kannada, expounding Sanskrit sūtras printed in Kannada script",
    "ocr": "Sarvam Document AI, 108 pages, with a Google Vision pass over the "
           "same book; segmented by tools/vaidika_svara/segment.py",
}


def build(pages: dict[int, str]) -> tuple[dict, collections.Counter]:
    rep = seg.segment(pages)
    files, stats = {}, collections.Counter()
    by_part: collections.Counter = collections.Counter()

    for sec in rep["sections"]:
        s = sec["section"]
        by_part[sec["part"]] += 1
        name = f"{sec['part']}_{by_part[sec['part']]}"
        shlokas = {}
        for n in range(1, sec["highest"] + 1):
            u = rep["units"].get((s, n))
            if u is None:
                stats["lacuna"] += 1
                continue
            entry = {"sa": u["sa"] or u["text"]}
            if u["artha"]:
                entry["commentaries"] = {COMMENTARY_KEY: u["artha"]}
                stats["with_gloss"] += 1
            if u["title"]:
                entry["unit_title"] = u["title"]
                stats["with_title"] += 1
            shlokas[str(n)] = entry
            stats["sutras"] += 1
        files[name] = {
            "metadata": {
                "title": f"Vaidika Svara Prakaraṇa — {PART_LABEL[sec['part']]} "
                         f"{by_part[sec['part']]}",
                "author": "Kadri Prabhakara Adiga",
                "stotraCode": name,
                "totalShlokas": sec["highest"],
                "sargaName": sec["heading"],
                "availableCommentaries": {COMMENTARY_KEY: COMMENTARY_TITLE},
                "lacunae": sec["missing"],
                "source": SOURCE,
            },
            "shlokas": shlokas,
        }

    # The prose between the sūtras, in its own section so nothing is lost.
    if rep["passages"]:
        shlokas = {}
        for i, ps in enumerate(rep["passages"], 1):
            shlokas[str(i)] = {"sa": ps["text"], "unit_title": ps["heading"]}
            stats["passages"] += 1
        files["gadya"] = {
            "metadata": {
                "title": "Vaidika Svara Prakaraṇa — ಗದ್ಯಭಾಗಾಃ",
                "author": "Kadri Prabhakara Adiga",
                "stotraCode": "gadya",
                "totalShlokas": len(rep["passages"]),
                "sargaName": "ಸೂತ್ರಗಳ ನಡುವಿನ ಗದ್ಯಭಾಗಗಳು",
                "lacunae": [],
                "source": SOURCE,
            },
            "shlokas": shlokas,
        }
    return files, stats


def canonical(payload: dict) -> str | None:
    spec = importlib.util.spec_from_file_location(
        "format_data_json",
        pathlib.Path(__file__).resolve().parents[1] / "format_data_json.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.canonical(payload)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--staged-dir",
                    default="data/ocr_staging/"
                            "vaidika_svara_prakaranam_prabhakara_adiga_kadri")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)

    pages = seg.load_pages(args.staged_dir)
    if not pages:
        print(f"no delivered pages under {args.staged_dir}", file=sys.stderr)
        return 1
    files, stats = build(pages)
    for name, payload in files.items():
        m = payload["metadata"]
        gap = f"  lacunae {m['lacunae']}" if m["lacunae"] else ""
        print(f"  {name:<14} {len(payload['shlokas']):>3}/{m['totalShlokas']:<3} "
              f"units{gap}   {m['sargaName'][:44]}")
    print(f"\n{stats['sutras']} sūtras, {stats['lacuna']} lacunae, "
          f"{stats['with_gloss']} with an ಅರ್ಥ gloss, "
          f"{stats['with_title']} with a topic from the contents page, "
          f"{stats['passages']} prose passages")
    if not args.write:
        print("\n(dry run -- pass --write to emit)")
        return 0
    for name, payload in files.items():
        d = TARGET / name
        d.mkdir(parents=True, exist_ok=True)
        text = canonical(payload) or (
            json.dumps(payload, ensure_ascii=False, indent=1) + "\n")
        (d / "data.json").write_text(text, encoding="utf-8")
    print(f"\nwrote {len(files)} section file(s) to {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
