#!/usr/bin/env python3
"""Turn the segmented Veṅkaṭeśa Māhātmya into the shelf's adhyāya files.

श्रीवेङ्कटेशमाहात्म्यम् of the Bhaviṣyottara Purāṇa, 11 adhyāyas, with the two
commentaries the edition prints. Output takes the shape the Kāvya shelf uses,
because that shape carries named commentaries per verse and is the one the
reader renders with a chip per ṭīkā:

    data/purana/maha_purana/bhavishya_purana/uttara_parva/
        venkatesha_mahatmya/adhyaya_N/data.json
    {metadata: {...}, shlokas: {"1": {sa, commentaries}, ...}}

It sits under bhavishya_purana/uttara_parva because that is what the text is --
the Bhaviṣyottara names itself on the title page -- and that scaffold was
standing empty.

ON THE GAPS. 64 verse numbers are not recoverable from the scan. They are NOT
quietly dropped: every adhyāya's metadata carries `lacunae`, the numbers it is
missing, and `totalShlokas` is the highest number the edition itself reaches,
so verse 25 is labelled 25 whether or not 24 survived. A declared hole is a
different thing from a silent one, and no text is invented to fill one.

    python3 tools/venkatesha/write_layers.py --staged-dir <dir>
    python3 tools/venkatesha/write_layers.py --staged-dir <dir> --write
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

TARGET = pathlib.Path("data/purana/maha_purana/bhavishya_purana/uttara_parva/"
                      "venkatesha_mahatmya")
ORDINALS = {
    1: "प्रथमः", 2: "द्वितीयः", 3: "तृतीयः", 4: "चतुर्थः", 5: "पञ्चमः",
    6: "षष्ठः", 7: "सप्तमः", 8: "अष्टमः", 9: "नवमः", 10: "दशमः",
    11: "एकादशः",
}
# Bibliographic only. No scan URL and no origin breadcrumb: credits belong in
# the site footer, given once and on the whole, not stamped on every record.
SOURCE = {
    "edition": "श्रीवेङ्कटेशमाहात्म्यम् — the Veṅkaṭeśa Māhātmya of the "
               "Bhaviṣyottara Purāṇa, with the Kalyāṇakāṇḍadīpa of "
               "Nṛpañcānana and the Gūḍhakartṛka Vyākhyāna",
    "series": "विश्वमध्वमहापरिषत् ग्रन्थमाला २०७",
    "ocr": "Sarvam Document AI, 854 pages, with a Google Vision pass over the "
           "same book; segmented by tools/venkatesha/segment.py",
}


def build(pages: dict[int, str]) -> tuple[dict, collections.Counter]:
    rep = seg.segment(pages)
    files, stats = {}, collections.Counter()
    for a in rep["adhyayas"]:
        n_adh, high = a["adhyaya"], a["highest"]
        shlokas = {}
        for v in range(1, high + 1):
            rec = rep["verses"].get((n_adh, v))
            if rec is None:
                stats["lacuna"] += 1
                continue
            entry = {"sa": rec["text"]}
            comms = rec.get("commentaries") or {}
            if comms:
                entry["commentaries"] = dict(comms)
                stats["with_commentary"] += 1
                if len(comms) == 2:
                    stats["with_both"] += 1
            else:
                stats["without_commentary"] += 1
            shlokas[str(v)] = entry
            stats["verses"] += 1
        files[f"adhyaya_{n_adh}"] = {
            "metadata": {
                "title": f"Veṅkaṭeśa Māhātmya अध्यायः {n_adh}",
                "author": "Bhavisyottara Purana",
                "stotraCode": f"adhyaya_{n_adh}",
                "totalShlokas": high,
                "sargaName": f"{ORDINALS.get(n_adh, n_adh)} अध्यायः",
                "availableCommentaries": dict(seg.COMMENTARY_TITLES),
                "lacunae": a["missing"],
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
                            "venkatesha__venkatesha_mahatmya_vyakyana_sahita")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)

    pages = seg.load_pages(args.staged_dir)
    if not pages:
        print(f"no delivered pages under {args.staged_dir}", file=sys.stderr)
        return 1
    files, stats = build(pages)
    for name, payload in sorted(files.items(),
                                key=lambda kv: int(kv[0].split("_")[1])):
        m = payload["metadata"]
        gap = f"  lacunae {len(m['lacunae'])}: {m['lacunae'][:6]}" if m["lacunae"] else ""
        print(f"  {name:<12} {len(payload['shlokas']):>4}/{m['totalShlokas']:<4} verses{gap}")
    print(f"\n{stats['verses']} verses, {stats['lacuna']} declared lacunae, "
          f"{stats['with_commentary']} with a commentary "
          f"({stats['with_both']} with both)")
    if not args.write:
        print("\n(dry run -- pass --write to emit)")
        return 0
    for name, payload in files.items():
        d = TARGET / name
        d.mkdir(parents=True, exist_ok=True)
        text = canonical(payload) or (
            json.dumps(payload, ensure_ascii=False, indent=1) + "\n")
        (d / "data.json").write_text(text, encoding="utf-8")
    print(f"\nwrote {len(files)} adhyaya file(s) to {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
