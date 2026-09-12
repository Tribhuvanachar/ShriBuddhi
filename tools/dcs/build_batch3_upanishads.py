#!/usr/bin/env python3
"""
build_batch3_upanishads.py -- 5 mula-Upanishad texts, caught late: these
already had precise empty taxonomy leaves under their Veda/shakha
(dge/PENDING.md's proposal had wrongly listed Upanishad mula texts as a
Tier B gap -- corrected here). Brihadaranyakopanishad deliberately
excluded: DCS's own chapter headers ("BAU") don't distinguish the Kanva
vs Madhyandina recension, and the taxonomy has separate empty leaves for
each -- guessing which one would risk mislabeling a real textual variant.
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
    ("Chāndogyopaniṣad", "dge/data/vedas/samaveda/kauthuma_shakha/upanishad/chandogya_upanishad/data.json", "chandogya_upanishad"),
    ("Kaṭhopaniṣad", "dge/data/vedas/yajurveda/krishna_yajurveda/katha_shakha/upanishad/katha_upanishad/data.json", "katha_upanishad"),
    ("Taittirīyopaniṣad", "dge/data/vedas/yajurveda/krishna_yajurveda/taittiriya_shakha/upanishad/taittiriya_upanishad/data.json", "taittiriya_upanishad"),
    ("Aitareyopaniṣad", "dge/data/vedas/rigveda/shakala_shakha/upanishads/aitareya_upanishad/data.json", "aitareya_upanishad"),
    ("Muṇḍakopaniṣad", "dge/data/vedas/atharvaveda/shaunaka_shakha/upanishads/mundaka_upanishad/data.json", "mundaka_upanishad"),
]


def main():
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
        count, chapters = build_generic_import(
            vendor_dir, out_path,
            source_name=SOURCE_NAME,
            source_url=f"https://github.com/OliverHellwig/sanskrit/tree/master/dcs/data/conllu/files/{dcs_name}",
            licence=LICENCE,
            note=(
                "{count} units across {chapters} -- the mula Upanishad text, "
                "distinct from Madhva's bhashya on it elsewhere in this repo. "
                "See dge/PENDING.md, 24 Aug entry (batch 3), for the correction "
                "this represents to the original taxonomy-placement proposal."
            ),
            tag="dcs-import",
        )
        print(f"{dcs_name}: {n} files -> {count} items -> {rel_out}")


if __name__ == "__main__":
    main()
