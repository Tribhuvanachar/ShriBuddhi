#!/usr/bin/env python3
"""
build_sivasutra.py -- DCS import, Sivasutra into agama/pancharatra/shaiva_agama.

Digital Corpus of Sanskrit (DCS), Oliver Hellwig, 2010-2024, CC-BY 4.0.
All 3 unmeshas DCS carries (77 sutras total) pulled from the primary mirror:
    https://github.com/OliverHellwig/sanskrit/tree/master/dcs/data/conllu/files/%C5%9Aivas%C5%ABtra

Landed in dge/data/agama/pancharatra/shaiva_agama/data.json -- an existing,
previously-empty ("Shaiva Agama") taxonomy leaf found while scoping how far
the DCS pilot could scale (see dge/PENDING.md, 23 Aug entry): no placement
decision needed, unlike most of DCS's other Agama/Tantra/Ayurveda texts.

    pip install skrutable
    python3 tools/dcs/build_sivasutra.py
"""
import os

from dcs_common import build_generic_import

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VENDOR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor", "conllu_sivasutra")
OUT = os.path.join(REPO, "dge", "data", "agama", "pancharatra", "shaiva_agama", "data.json")


def main():
    count, chapters = build_generic_import(
        VENDOR, OUT,
        source_name="Digital Corpus of Sanskrit (DCS), Oliver Hellwig, 2010-2024",
        source_url=(
            "https://github.com/OliverHellwig/sanskrit/tree/master/dcs/data/"
            "conllu/files/%C5%9Aivas%C5%ABtra"
        ),
        licence="CC-BY 4.0",
        note=(
            "{count} sutras across all 3 unmeshas ({chapters}) DCS carries "
            "of the Sivasutra -- the complete short text, not an excerpt. "
            "See dge/PENDING.md for the DCS integration scoping decision "
            "this import is part of."
        ),
        tag="dcs-import",
    )
    print(f"wrote {count} sutras (chapters {chapters}) to {OUT}")


if __name__ == "__main__":
    main()
