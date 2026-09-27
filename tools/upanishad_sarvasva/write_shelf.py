#!/usr/bin/env python3
"""Turn the segmented 108 Upaniṣat Sarvasva into its shelf files.

೧೦೮ ಉಪನಿಷತ್ ಸರ್ವಸ್ವ, ಪ್ರಥಮ ಸಂಪುಟ -- Bhārgava Narasiṃha's Kannada
compilation and translation of the Upaniṣads, twenty-five of them in this
volume, each mantra followed by its tātparya.

    data/vedas/upanishad_sarvasva_kannada/<upanishad>/data.json

One file per Upaniṣad, which is what the volume's own contents page offers
and what a reader would ask for.  It sits beside the Upaniṣads already on
the shelf rather than among them: those are the Devanāgarī mūla, this is a
Kannada exposition of them by a named modern author, so it is a different
text and not a second copy of one.

**The units are numbered by position, not by the numbers on the page.**
The book prints ``॥ 8 (33)`` -- eighth of this khaṇḍa, thirty-third of the
Upaniṣad -- but only five of the twenty-five carry that second number at
all, and even they only start printing it around their ninth mantra.  It is
too sparse to key on.  The printed numbering is kept beside each unit
instead, in ``unit_title``, together with the khaṇḍa or vallī heading it
falls under.

**Where the book's own numbering reaches past what survived, the metadata
says so in words.**  Sequential keys cannot carry a hole the way numbered
ones can -- verse 25 is simply absent and the count silently becomes 24 --
so the shortfall is written down in ``source.extent`` for each Upaniṣad
that has one, rather than left for someone to notice.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "ocr_common"))
import segment as seg          # noqa: E402
import shelf_writer as W       # noqa: E402

TARGET = pathlib.Path("data/vedas/upanishad_sarvasva_kannada")
STAGED = "data/ocr_staging/108_upanishad_sarvas__narasimha_1_ttd_kannada"

WORK = "೧೦೮ ಉಪನಿಷತ್ ಸರ್ವಸ್ವ"
AUTHOR = "Bhargava Narasimha (ಭಾರ್ಗವ ನರಸಿಂಹ)"
COMMENTARY_KEY = "kannada"
COMMENTARY_TITLE = "ತಾತ್ಪರ್ಯ — ಕನ್ನಡ"

EDITION = ("೧೦೮ ಉಪನಿಷತ್ ಸರ್ವಸ್ವ, ಪ್ರಥಮ ಸಂಪುಟ — the Upaniṣads with the "
           "original mantra and its Kannada meaning, compiled and translated "
           "by ಭಾರ್ಗವ ನರಸಿಂಹ")
OCR = ("Sarvam Document AI, 599 pages, with a Google Vision pass over the "
       "same book; segmented by tools/upanishad_sarvasva/segment.py")


def unit_title(unit: dict) -> str:
    """The khaṇḍa or vallī heading, with the number the page printed.

    Empty where the Upaniṣad has no divisions -- Māṇḍūkya's twelve mantras
    run straight through -- because the printed number alone would only
    repeat the key it sits beside.
    """
    if not unit.get("heading"):
        return ""
    if unit.get("local"):
        return f"{unit['heading']} · {unit['local']}"
    return unit["heading"]


def extent(work: dict) -> str | None:
    """Say, in words, where the book counts higher than what survived."""
    got = len(work["units"])
    printed = max([u["cum"] for u in work["units"] if u.get("cum")] or [0])
    canon = seg.CANONICAL.get(work["name"])
    reaches = max(printed, canon or 0)
    if reaches <= got:
        return None
    whose = ("the edition's own running numbering" if printed >= (canon or 0)
             else "this Upaniṣad")
    return (f"{got} mantras are here; {whose} reaches {reaches}, so "
            f"{reaches - got} did not survive the scan")


def build(works: list[dict]) -> dict:
    files = {}
    for w in works:
        shlokas = {}
        for i, u in enumerate(w["units"], 1):
            entry = {"sa": u["mula"]}
            title = unit_title(u)
            if title:
                entry["unit_title"] = title
            if u.get("tatparya"):
                entry["commentaries"] = {COMMENTARY_KEY: u["tatparya"]}
            shlokas[str(i)] = entry
        source = {"edition": EDITION, "ocr": OCR}
        gap = extent(w)
        if gap:
            source["extent"] = gap
        files[w["slug"]] = {
            "metadata": {
                "title": f"{WORK} — {w['name']}",
                "author": AUTHOR,
                "stotraCode": w["slug"],
                "totalShlokas": len(w["units"]),
                "sargaName": w["name"],
                "lacunae": [],
                "availableCommentaries": {COMMENTARY_KEY: COMMENTARY_TITLE},
                "source": source,
            },
            "shlokas": shlokas,
        }
    return files


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--staged-dir", default=STAGED)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)

    works = seg.segment(args.staged_dir)
    problems = seg.check([{"units": w["units"]} for w in works])
    if problems:
        for p in problems:
            print(f"contents check: {p}", file=sys.stderr)
        return 1

    files = build(works)
    total = glossed = 0
    for w in works:
        f = files[w["slug"]]
        g = sum(1 for v in f["shlokas"].values() if v.get("commentaries"))
        total += len(f["shlokas"])
        glossed += g
        note = f["metadata"]["source"].get("extent", "")
        print(f"  {w['slug']:<30} {len(f['shlokas']):>4} mantras, "
              f"{g:>4} with a tātparya  {note[:52]}")
    print(f"\n{len(files)} Upaniṣads, {total} mantras, "
          f"{glossed} with a tātparya")

    if not args.write:
        print("\n(dry run -- pass --write to emit)")
        return 0
    print(f"\nwrote {W.write(files, TARGET)} file(s) to {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
