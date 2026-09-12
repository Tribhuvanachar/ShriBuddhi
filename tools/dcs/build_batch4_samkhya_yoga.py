#!/usr/bin/env python3
"""
build_batch4_samkhya_yoga.py -- Tier B, 23 Aug: Samkhya and Yoga darshana
were confirmed as pre-planned taxonomy branches (dge/js/library.js's
DGE_PATH_LABELS already carries 'sankhya'/'yoga' Devanagari labels under
a comment naming an external "recommended DGE taxonomy" reference doc),
unlike Ayurveda/Buddhist-literature/Tantra, which have no such label and
were therefore NOT drafted here -- see dge/PENDING.md for the open
question this leaves.

taxonomy.json gained darshana.sankhya (sutra_and_karika: samkhya_karika,
samkhya_sutra) and darshana.yoga (sutra_and_bhashya: yoga_sutra) as new
nodes, mirroring the existing nyaya_sutra/vaisheshika_sutra sibling
mula+tika_* pattern. NOTE the folder is 'sankhya' (matching the
pre-existing DGE_PATH_LABELS key exactly), not 'samkhya' -- caught only
by grepping library.js before writing library.json, not assumed.

Of the 13 leaves drafted, only 3 have a DCS match: Samkhyakarika and
Samkhyasutra mula texts are NOT in the DCS mirror at all (checked by
listing, not assumed) -- only a commentary, Samkhyatattvakaumudi, is.
Yogasutra mula and its Vyasabhashya are both present. The other 10 leaves
are added to library.json as populated:false stubs, same as any other
planned-but-not-yet-sourced grantha in this taxonomy.
"""
import os
import shutil

from dcs_common import build_generic_import

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DCS_MIRROR = os.environ.get(
    "DCS_MIRROR",
    "/tmp/claude-0/-home-user-bhumandala/e8a5c83c-760f-5d7b-9fbc-3df8440bd264/scratchpad/sanskrit_check/dcs/data/conllu/files",
)
VENDOR_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor")
SOURCE_NAME = "Digital Corpus of Sanskrit (DCS), Oliver Hellwig, 2010-2024"
LICENCE = "CC-BY 4.0"

SINGLE = [
    ("Sāṃkhyatattvakaumudī", "dge/data/darshana/sankhya/sutra_and_karika/samkhya_karika/tika_tattva_kaumudi/data.json", "samkhya_tattva_kaumudi"),
    ("Yogasūtra", "dge/data/darshana/yoga/sutra_and_bhashya/yoga_sutra/mula/data.json", "yoga_sutra_mula"),
    ("Yogasūtrabhāṣya", "dge/data/darshana/yoga/sutra_and_bhashya/yoga_sutra/bhashya_vyasa/data.json", "yoga_sutra_bhashya_vyasa"),
]


def main():
    touched_paths = []
    for dcs_name, rel_out, slug in SINGLE:
        src_dir = os.path.join(DCS_MIRROR, dcs_name)
        if not os.path.isdir(src_dir):
            print(f"SKIP {dcs_name}: not found")
            continue
        vendor_dir = os.path.join(VENDOR_ROOT, slug)
        os.makedirs(vendor_dir, exist_ok=True)
        n = 0
        for fname in os.listdir(src_dir):
            if fname.endswith(".conllu"):
                shutil.copy(os.path.join(src_dir, fname), os.path.join(vendor_dir, fname))
                n += 1
        out_path = os.path.join(REPO, rel_out)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        count, chapters = build_generic_import(
            vendor_dir, out_path,
            source_name=SOURCE_NAME,
            source_url=f"https://github.com/OliverHellwig/sanskrit/tree/master/dcs/data/conllu/files/{dcs_name}",
            licence=LICENCE,
            note=(
                "{count} units across {chapters} -- see dge/PENDING.md, 23 Aug "
                "entry (batch 4, Tier B Samkhya/Yoga), for how the darshana.sankhya "
                "and darshana.yoga taxonomy nodes were drafted and matched."
            ),
            tag="dcs-import",
        )
        touched_paths.append(rel_out)
        print(f"{dcs_name}: {n} files -> {count} items -> {rel_out}")

    print("\n--- touched data.json paths (for library.json flip) ---")
    for p in touched_paths:
        print(p)


if __name__ == "__main__":
    main()
