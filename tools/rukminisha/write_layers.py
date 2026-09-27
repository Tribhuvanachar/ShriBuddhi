#!/usr/bin/env python3
"""Turn the segmented Rukmiṇīśa Vijaya into the Kāvya shelf's sarga files.

Vādirāja Tīrtha's mahākāvya with the Gurubhāvaprakāśikā of Nārāyaṇa Bhaṭṭa,
19 sargas. Output matches the shape sumadhva_vijaya and maṇimañjarī use:

    data/Tattvavada/Itara/Kavya/rukminisha_vijaya/sarga_N/data.json
    {metadata: {...}, shlokas: {"1": {sa, commentaries}, ...}}

ON THE GAPS. 29 verse numbers are not in the scan. They are NOT quietly left
out: every sarga's metadata carries `lacunae`, the numbers it is missing, and
`totalShlokas` is the highest number the edition itself reaches, so verse 25
is labelled 25 whether or not 24 survived. Maṇimañjarī is the reason -- a
verse vanished there and the count silently became 305, which nothing noticed
because nothing was written down. A declared hole is a different thing from a
silent one, and no text is invented to fill it.

    python3 tools/rukminisha/write_layers.py --staged-dir <dir>
    python3 tools/rukminisha/write_layers.py --staged-dir <dir> --write
"""

from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import segment as seg  # noqa: E402

TARGET = pathlib.Path("data/Tattvavada/Itara/Kavya/rukminisha_vijaya")
COMMENTARY_KEY = "gurubhavaprakashika"
ORDINAL_NAMES = {
    1: "प्रथमः", 2: "द्वितीयः", 3: "तृतीयः", 4: "चतुर्थः", 5: "पञ्चमः",
    6: "षष्ठः", 7: "सप्तमः", 8: "अष्टमः", 9: "नवमः", 10: "दशमः",
    11: "एकादशः", 12: "द्वादशः", 13: "त्रयोदशः", 14: "चतुर्दशः",
    15: "पञ्चदशः", 16: "षोडशः", 17: "सप्तदशः", 18: "अष्टादशः",
    19: "एकोनविंशः",
}
# Bibliographic only, and shaped like maṇimañjarī's on the same shelf. The scan
# URL that was here is an origin breadcrumb: credits belong in the site footer,
# given once and on the whole, not stamped on every record.
SOURCE = {
    "edition": "श्रीरुग्मिणीशविजयः — Rugmiṇīśa Vijaya of Śrī Vādirāja Tīrtha, "
               "with the Gurubhāvaprakāśikā ṭīkā of Śrī Nārāyaṇa Bhaṭṭa; "
               "edited by Vidwan Sandeshacharya",
    "ocr": "Sarvam Document AI, 725 pages; segmented by tools/rukminisha/segment.py",
}


def commentary_index(stream: list[dict]) -> dict:
    """The whole gloss on each verse, keyed by the (sarga, verse) it glosses.

    Assembled from the gloss REGIONS, not from blocks carrying a number. The
    gloss on one verse runs over several blocks and across page breaks, and the
    ॥ N ॥ that closes it is on the last block only, so keying on the numbers a
    block happens to contain both split one gloss across several verses and
    attached it to whatever verses it quoted in passing.
    """
    out = collections.defaultdict(list)
    for opened, closed, n, sarga in seg.gloss_regions(stream):
        if sarga and n >= 1:
            out[(sarga, n)].extend(stream[opened:closed + 1])
    return out


def build(pages: dict[int, str]) -> tuple[dict, dict]:
    stream, _ = seg.read_blocks(pages)
    rep = seg.segment(pages)
    comms = commentary_index(stream)

    files, stats = {}, collections.Counter()
    for s in rep["sargas"]:
        sarga, high = s["sarga"], s["highest"]
        shlokas = {}
        for v in range(1, high + 1):
            rec = rep["verses"].get((sarga, v))
            if rec is None:
                stats["lacuna"] += 1
                continue
            entry = {"sa": rec["text"]}
            glosses = comms.get((sarga, v)) or []
            if glosses:
                entry["commentaries"] = {
                    COMMENTARY_KEY: "\n".join(g["text"] for g in glosses)}
                stats["with_commentary"] += 1
            else:
                stats["without_commentary"] += 1
            # How this verse was addressed travels with it, so a reader or a
            # later editor can see which ones rest on inference rather than a
            # printed number.
            if rec.get("how") != "marker":
                entry["provenance"] = {
                    "addressed_by": rec["how"],
                    "note": ("verse number not legible in the scan; placed by "
                             + {"gloss-close":
                                "the number its commentary closes with, the "
                                "commentary being printed directly beneath it",
                                "position":
                                "position between its numbered neighbours",
                                "pratika":
                                "the pratīka the commentary quotes",
                                }.get(rec["how"], rec["how"])),
                    "page": rec.get("page"),
                }
                stats["inferred"] += 1
            shlokas[str(v)] = entry
            stats["verses"] += 1

        files[f"sarga_{sarga}"] = {
            "metadata": {
                "title": f"Rugmiṇīśa Vijaya सर्गः {sarga}",
                "author": "Vadiraja Tirtha",
                "stotraCode": f"sarga_{sarga}",
                "totalShlokas": high,
                "sargaName": f"{ORDINAL_NAMES.get(sarga, sarga)} सर्गः",
                "availableCommentaries": {
                    COMMENTARY_KEY: "गुरुभावप्रकाशिका — श्रीनारायणभट्टः"},
                "lacunae": s["missing"],
                "source": SOURCE,
            },
            "shlokas": shlokas,
        }
    return files, stats


def canonical(payload: dict) -> str | None:
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "format_data_json",
        pathlib.Path(__file__).resolve().parents[1] / "format_data_json.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.canonical(payload)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--staged-dir", default="data/ocr_staging/rukminisha_vijaya")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)

    pages = seg.load_pages(args.staged_dir)
    if not pages:
        print(f"no delivered pages under {args.staged_dir}", file=sys.stderr)
        return 1
    files, stats = build(pages)

    for name, payload in sorted(files.items(), key=lambda kv: int(kv[0].split("_")[1])):
        m = payload["metadata"]
        gap = f"  lacunae {m['lacunae']}" if m["lacunae"] else ""
        print(f"  {name:<10} {len(payload['shlokas']):>3}/{m['totalShlokas']:<3} verses{gap}")
    print(f"\n{stats['verses']} verses, {stats['lacuna']} declared lacunae, "
          f"{stats['inferred']} addressed by inference, "
          f"{stats['with_commentary']} with commentary")

    if not args.write:
        print("\n(dry run -- pass --write to emit)")
        return 0
    for name, payload in files.items():
        d = TARGET / name
        d.mkdir(parents=True, exist_ok=True)
        text = canonical(payload) or (json.dumps(payload, ensure_ascii=False, indent=1) + "\n")
        (d / "data.json").write_text(text, encoding="utf-8")
    print(f"\nwrote {len(files)} sarga file(s) to {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
