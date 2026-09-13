"""One-off partition of Narada Purana's Purvabhaga (Sanskrit Wikisource,
नारदपुराणम्- पूर्वार्धः) into the 4 pada taxonomy leaves this project already
tracks separately (purvabhaga/pada_01..04) -- Wikisource itself keeps all
125 adhyayas on one flat, unbroken index (no pada-level subpages), so the
split has to happen here rather than in the generic crawler. Chapter ranges
per pada (1-41 / 42-62 / 63-91 / 92-125) are the traditional four Sanaka/
Sanandana/Sanatkumara/Sanatana speaker divisions, cross-checked against the
project's own Wikisource survey (dge/PENDING.md, 11 Sep 2026).

purvabhaga/purana_mula is a SEPARATE, already-populated leaf sourced
elsewhere (GRETIL) and is deliberately left untouched here -- this script
only fills the 4 previously-empty pada_NN leaves.

Run: python importers/wikisource_narada_padas.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import write_grantha
from wikisource_purana import crawl, to_items, preserve_stub_extra, SOURCE, LICENCE

TITLE = "नारदपुराणम्- पूर्वार्धः"
PADAS = [
    ("pada_01", 1, 41, "Sanaka"),
    ("pada_02", 42, 62, "Sanandana"),
    ("pada_03", 63, 91, "Sanatkumara"),
    ("pada_04", 92, 125, "Sanatana"),
]


def main():
    print(f"crawling {TITLE} ...")
    chapters = crawl([(TITLE, None)])
    by_num = {}
    for num, shlokas in chapters:
        if num is not None and num.isdigit():
            by_num[int(num)] = shlokas
    print(f"{len(by_num)} numbered chapters found (of 125 expected)")

    for slug, lo, hi, speaker in PADAS:
        rel = f"purana/maha_purana/narada_purana/purvabhaga/{slug}"
        part_chapters = [(str(n), by_num[n]) for n in range(lo, hi + 1) if n in by_num]
        missing = [n for n in range(lo, hi + 1) if n not in by_num]
        items = to_items(part_chapters, f"Narada Purana, Purvabhaga, {slug} ({speaker}-parva)")
        n_shlokas = sum(len(it["shlokas"]) for it in items)
        print(f"[{slug}] adhyaya {lo}-{hi}: {len(items)} chapters, {n_shlokas} shlokas"
              + (f"  MISSING: {missing}" if missing else ""))
        if not items:
            continue
        extra = preserve_stub_extra(rel)
        write_grantha(
            rel, "itihasa_purana_text", "Maharshi Veda Vyasa", items,
            source_url="https://sa.wikisource.org/wiki/" + TITLE.replace(" ", "_"),
            source_note=f"{SOURCE}. Purvabhaga, adhyaya {lo}-{hi} ({speaker}-parva) -- "
                        "Wikisource keeps the whole Purvabhaga on one flat index; this "
                        "project's own pada split follows the traditional four "
                        "speaker-divisions. purvabhaga/purana_mula (a separate leaf, "
                        "sourced elsewhere) is untouched by this import.",
            licence=LICENCE,
            **extra,
        )


if __name__ == "__main__":
    main()
