#!/usr/bin/env python3
"""Turn the segmented Brahmasūtradīpikā into the sūtra-prasthāna shelf files.

ब्रह्मसूत्रदीपिका of Śrī Jagannātha Yati, one file per pāda:

    data/darshana/vedanta/dvaita/DvaitaVedantaIn/sutra_prasthana/
        brahmasutra_dipika/adhyaya_A_pada_P/data.json

ON WHAT THIS VOLUME CONTAINS. It ends at 4.3.5 -- the PDF is 238 pages and the
last sūtra set is ॐ उभयव्यामोहात्तत्सिद्धः ॐ, running number 530 of the 564 the
work has. So 4.3.6 onward and the whole of 4.4 are not in this book, and are
recorded as absent rather than as a segmentation failure.

Each pāda's `lacunae` names the sūtras its own numbering reaches past but the
OCR did not deliver -- 29 across the volume.
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

TARGET = pathlib.Path("data/darshana/vedanta/dvaita/DvaitaVedantaIn/"
                      "sutra_prasthana/brahmasutra_dipika")
COMMENTARY_KEY = "sutradipika"
COMMENTARY_TITLE = "सूत्रदीपिका — श्रीजगन्नाथयतिः"
SOURCE = {
    "edition": "ब्रह्मसूत्रदीपिका — Brahmasūtradīpikā of Śrī Jagannātha Yati, "
               "edited with an English gist by Dr V. R. Panchamukhi",
    "series": "Rashtriya Sanskrit Vidyapeetha Series No. 94, Tirupati",
    "edition_year": 2002,
    "extent": "This volume ends at 4.3.5 (running sūtra 530); 4.3.6 onward and "
              "the whole of pāda 4.4 are not in it",
    "ocr": "Sarvam Document AI over pages 25-238 and Google Vision over 1-238; "
           "segmented by tools/sutradipika/segment.py",
}
ORD = {1: "प्रथमः", 2: "द्वितीयः", 3: "तृतीयः", 4: "चतुर्थः"}


def build(staged_dir: str) -> tuple[dict, collections.Counter]:
    rep = seg.segment(staged_dir)
    files, stats = {}, collections.Counter()
    for x in rep["padas"]:
        a, p = x["adhyaya"], x["pada"]
        name = f"adhyaya_{a}_pada_{p}"
        shlokas = {}
        for n in range(1, x["highest"] + 1):
            u = rep["sutras"].get((a, p, n))
            if u is None:
                stats["lacuna"] += 1
                continue
            entry = {"sa": u["sa"]}
            if u["commentary"]:
                entry["commentaries"] = {COMMENTARY_KEY: u["commentary"]}
                stats["with_commentary"] += 1
            if u["adhikarana"]:
                entry["unit_title"] = u["adhikarana"]
            # The number the page actually prints, kept where it disagrees with
            # the slot, so the disagreement is visible rather than smoothed away.
            if u["printed_number"] != n:
                entry["provenance"] = {
                    "printed_number": u["printed_number"],
                    "running_number": u["running"],
                    "note": "the page prints this number; the address follows "
                            "the pāda's own sequence",
                    "page": u["page"], "engine": u["engine"],
                }
                stats["printed_disagreed"] += 1
            if u["engine"] == "vision":
                stats["from_vision"] += 1
            shlokas[str(n)] = entry
            stats["sutras"] += 1
        files[name] = {
            "metadata": {
                "title": f"Brahmasūtradīpikā {a}.{p}",
                "author": "Jagannatha Yati",
                "stotraCode": name,
                "totalShlokas": x["highest"],
                "sargaName": f"{ORD[a]} अध्यायः, {ORD[p]} पादः",
                "availableCommentaries": {COMMENTARY_KEY: COMMENTARY_TITLE},
                "lacunae": x["missing"],
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
                            "brahma_sutra_dipika_jagannatha_tirtha_panchamukhi")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)
    files, stats = build(args.staged_dir)
    for name, payload in files.items():
        m = payload["metadata"]
        gap = f"  lacunae {len(m['lacunae'])}" if m["lacunae"] else ""
        print(f"  {name:<20} {len(payload['shlokas']):>3}/{m['totalShlokas']:<3} sūtras{gap}")
    print(f"\n{stats['sutras']} sūtras, {stats['lacuna']} lacunae, "
          f"{stats['with_commentary']} with the dīpikā, "
          f"{stats['from_vision']} read from Vision, "
          f"{stats['printed_disagreed']} carrying a printed number that disagrees")
    if not args.write:
        print("\n(dry run -- pass --write to emit)")
        return 0
    for name, payload in files.items():
        d = TARGET / name
        d.mkdir(parents=True, exist_ok=True)
        text = canonical(payload) or (
            json.dumps(payload, ensure_ascii=False, indent=1) + "\n")
        (d / "data.json").write_text(text, encoding="utf-8")
    print(f"\nwrote {len(files)} pāda file(s) to {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
