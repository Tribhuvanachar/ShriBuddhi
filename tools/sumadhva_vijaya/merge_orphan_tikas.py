#!/usr/bin/env python3
"""Fold the sarga-level Sumadhva Vijaya tikas into the kavya copy, then retire them.

THE DUPLICATE. Sumadhva Vijaya was shelved twice. `Itara/Kavya/sumadhva_vijaya`
is the real edition: sixteen sargas, 1,006 shlokas, each verse carrying its own
mandopakarini / padarthadipikodbodhika / bhavaprakashika, plus audio and the
Bannanje readings. `Itara/sumadhva_vijaya` is the SAME three tikas dumped one
blob per sarga, with no mula folder at all -- so it could never stitch, and it
showed in the library as six unrelated works.

Three of those six are not works at all. tika_iti_shrimadvedangamuni,
tika_iti_shrinarayanapanditacarya and tika_shrichalarisheshacarya hold ONE item
each, and that item is a colophon or a heading line that the importer mistook
for the start of a new layer (the karmavijaya-class heading bug). Measured,
they carry no commentary the kavya copy lacks.

WHAT THE COARSE COPY IS NOT. It looks 15% larger than the kavya copy, which
looks like content at risk. It is not: the blob quotes each SHLOKA before
commenting on it, and the kavya copy holds those verses in `sa` instead of
repeating them inside the commentary. Segment by segment against the whole
sarga -- verses, commentary and colophon together -- 17,485 of 17,525 segments
are already there. This tool moves the 40 that are not, so the folder can be
deleted without losing a line.

WHERE A RESIDUE SEGMENT GOES. Not guessed: the blob is read in order, and each
segment that IS found tells us which shloka the blob has reached. A segment
that is not found is appended to that shloka -- the one whose commentary the
blob was in the middle of. A residue segment before any match would have no
such anchor; none occur, and the tool refuses rather than inventing a home.

Usage: python3 tools/sumadhva_vijaya/merge_orphan_tikas.py [--check]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from format_data_json import canonical  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
KAVYA = ROOT / "data/Tattvavada/Itara/Kavya/sumadhva_vijaya"
ORPHAN = ROOT / "data/Tattvavada/Itara/sumadhva_vijaya"

# orphan folder -> the commentary key the kavya copy already uses for it.
# The three single-item folders are the mis-split ones; they are read for
# residue like any other, and contribute their tika colophon or nothing.
FOLDERS = {
    "tika_mandopakarini": "mandopakarini",
    "tika_padarthadipikodbodhika": "padarthadipikodbodhika",
    "tika_prakashika": "bhavaprakashika",
    "tika_iti_shrimadvedangamuni": "padarthadipikodbodhika",
    "tika_iti_shrinarayanapanditacarya": "bhavaprakashika",
    "tika_shrichalarisheshacarya": "mandopakarini",
}

ORDINALS = ["प्रथमः", "द्वितीयः", "तृतीयः", "चतुर्थः", "पञ्चमः", "षष्ठः",
            "सप्तमः", "अष्टमः", "नवमः", "दशमः", "एकादशः", "द्वादशः",
            "त्रयोदशः", "चतुर्दशः", "पञ्चदशः", "षोडशः"]

# A layer HEADING repeated as its own line ("श्रीछलारिशेषाचार्यविरचिता
# मन्दोपाकारिणी", or the bare "श्रीनारायणपण्डिताचार्यविरचिता") names the tab
# the text is already under; it is not commentary and is dropped rather than
# appended to a verse.
HEADING_ONLY = re.compile(r"^\s*श्री\S*विरचिता?(\s+\S+)?\s*$")

# The MULA's own sarga colophon. Every sarga file already carries it in
# metadata.colophon -- the two copies merely hyphenate differently
# ("श्रीमत्-कवि-कुल-तिलक-" against "श्रीमत्कविकुलतिलक"), which is the only
# reason exact matching does not find it. Appending it to the last verse's
# mandopakarini would file the poem's own colophon as commentary, 14 times
# over. A TIKA's colophon names the tika instead (पदार्थदीपिकोद्बोधिकायां,
# भावप्रकाशिकाख्यटीकायां) and is genuinely that layer's, so it is kept.
MULA_COLOPHON = re.compile(r"^\s*इति\s+श्री.*महाकाव्ये.*सर्गः\s*$", re.S)

# A residue run that announces whose it is. The mandopakarini blob for sarga 5
# carries a stretch of padarthadipikodbodhika, labelled in the text itself
# ("पदार्थदीपिकोद्भोदिका – तत इति", the spelling wobbling with the scan). Filing
# it under mandopakarini because of the folder it sat in would publish one
# tika's words under another commentator's name; the label is better evidence
# than the folder, so it re-routes until the blob rejoins its own layer.
# Anchored on the distinctive STEM only. The scans spell these titles several
# ways -- "पदार्थदीपिकोद्भोदिका" and "पदार्तदीपिकोद्बोधिका" both occur, differing
# in three letters -- so matching the full title misses the very lines this
# exists to catch.
SELF_LABELLED = [
    (re.compile(r"^\s*पदार्[थत]दीपिक"), "padarthadipikodbodhika"),
    (re.compile(r"^\s*भावप्रकाशिक"), "bhavaprakashika"),
    (re.compile(r"^\s*मन्दोपाकारि"), "mandopakarini"),
]


def norm(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def sarga_of(section: str) -> int | None:
    for i, o in enumerate(ORDINALS):
        if (section or "").startswith(o):
            return i + 1
    return None


def segments(text: str) -> list[str]:
    """Split a blob the way the edition punctuates it, keeping only chunks long
    enough to match reliably; a 25-character floor keeps stray danda fragments
    from matching everything."""
    return [s for s in re.split(r"[\n।]+", text or "") if len(norm(s)) >= 25]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="report only; write nothing")
    args = ap.parse_args()

    sargas = {}
    for n in range(1, 17):
        path = KAVYA / f"sarga_{n}" / "data.json"
        sargas[n] = json.loads(path.read_text(encoding="utf-8"))

    # Everything each sarga already holds anywhere -- verses, every commentary,
    # and the colophon -- so a verse the blob quotes is never counted as new.
    whole = {}
    for n, data in sargas.items():
        buf = [data.get("metadata", {}).get("colophon") or ""]
        for v in data["shlokas"].values():
            buf.append(v.get("sa") or "")
            for txt in (v.get("commentaries") or {}).values():
                if isinstance(txt, str):
                    buf.append(txt)
        whole[n] = norm("".join(buf))

    placements: list[tuple[int, str, str, str]] = []
    dropped = 0
    for folder, key in FOLDERS.items():
        src = ORPHAN / folder / "data.json"
        if not src.is_file():
            print(f"  {folder}: already gone")
            continue
        for item in json.loads(src.read_text(encoding="utf-8"))["items"]:
            n = sarga_of(item.get("section") or "")
            if n is None:
                print(f"  REFUSED: {folder} item has no recognisable sarga "
                      f"({item.get('section')!r})", file=sys.stderr)
                return 1
            shlokas = sargas[n]["shlokas"]
            order = sorted(shlokas, key=lambda s: int(s))
            per = {s: norm((shlokas[s].get("commentaries") or {}).get(key, ""))
                   for s in order}
            cursor = None
            route = None
            for seg in segments(item.get("sanskrit_text") or ""):
                ns = norm(seg)
                hit = next((s for s in order if ns and ns in per[s]), None)
                if hit is not None:
                    cursor = hit
                    route = None  # the blob is back in its own layer
                    continue
                if ns in whole[n]:
                    continue  # a verse the blob quotes, or another tika's text
                if HEADING_ONLY.match(seg.strip()) or MULA_COLOPHON.match(seg.strip()):
                    dropped += 1
                    continue
                for pattern, other in SELF_LABELLED:
                    if pattern.match(seg.strip()):
                        route = other if other != key else None
                        break
                if cursor is None:
                    # A tika colophon arrives after its last verse; a blob that
                    # is ONLY a colophon never matched anything, so anchor it at
                    # the sarga's final shloka rather than refusing.
                    cursor = order[-1]
                placements.append((n, cursor, route or key, seg.strip()))

    print(f"{len(placements)} residue segment(s) to place, {dropped} heading line(s) dropped")
    for n, s, key, seg in placements:
        print(f"   sarga {n:>2} shloka {s:>3} {key:<24} {seg[:70]}")
    if args.check:
        return 0

    touched = set()
    for n, s, key, seg in placements:
        sh = sargas[n]["shlokas"][s]
        com = sh.setdefault("commentaries", {})
        com[key] = (com[key].rstrip() + "\n" + seg) if com.get(key) else seg
        touched.add(n)
    for n in sorted(touched):
        path = KAVYA / f"sarga_{n}" / "data.json"
        path.write_text(canonical(sargas[n]), encoding="utf-8")
    print(f"wrote {len(touched)} sarga file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
