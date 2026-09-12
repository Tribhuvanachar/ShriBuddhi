#!/usr/bin/env python3
"""
build_jyotisha_pilot.py -- DCS pilot import, Suryasiddhanta into vedanga/jyotisha.

Digital Corpus of Sanskrit (DCS), Oliver Hellwig, 2010-2024, CC-BY 4.0.
Source files (2 chapters, 139 verses, an excerpt not the full 14-chapter
text) pulled from the primary mirror:
    https://github.com/OliverHellwig/sanskrit/tree/master/dcs/data/conllu/files/S%C5%ABryasiddh%C4%81nta
Licence is clean attribution-only (unlike AGPL chanda / CC-BY-SA skrutable
elsewhere in this project) -- no share-alike obligation, but attribution
is still recorded per-entry and at the top of the output file, matching
the sourcing convention in dge/kosha_toolkit/LICENSING.md.

This was the original PILOT: proved the DCS CoNLL-U -> DGE "generic"
schema mapping on one text. Parsing logic since factored out to
dcs_common.py, reused by build_sivasutra.py and later imports.

    pip install skrutable
    python3 tools/dcs/build_jyotisha_pilot.py
"""
import os

from dcs_common import build_generic_import

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VENDOR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor", "conllu")
OUT = os.path.join(REPO, "dge", "data", "vedanga", "jyotisha", "data.json")


def main():
    count, chapters = build_generic_import(
        VENDOR, OUT,
        source_name="Digital Corpus of Sanskrit (DCS), Oliver Hellwig, 2010-2024",
        source_url=(
            "https://github.com/OliverHellwig/sanskrit/tree/master/dcs/data/"
            "conllu/files/S%C5%ABryasiddh%C4%81nta"
        ),
        licence="CC-BY 4.0",
        note=(
            "Pilot import: {count} verses across chapters {chapters} of "
            "Suryasiddhanta, as excerpted in DCS -- not the full 14-chapter "
            "classical text. See dge/PENDING.md for the DCS integration "
            "scoping decision this pilot exists to inform, and "
            "tools/dcs/README.md for how to extend it."
        ),
        tag="dcs-pilot",
    )
    print(f"wrote {count} verses (chapters {chapters}) to {OUT}")


if __name__ == "__main__":
    main()
