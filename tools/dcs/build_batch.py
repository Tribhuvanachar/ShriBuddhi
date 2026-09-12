#!/usr/bin/env python3
"""
build_batch.py -- import every DCS text found to exactly match an existing,
previously-empty (populated:false) taxonomy leaf. Found by normalizing DCS's
texts.csv names and library.json leaf titles/path segments (strip diacritics,
lowercase, alnum-only) and taking exact matches -- deliberately conservative:
no fuzzy/partial matching, so a wrong match never lands silently. See
dge/PENDING.md, 24 Aug entry, for the matching method and its output.

Run from a shell that already has the DCS mirror's conllu files reachable
at DCS_MIRROR (adjust the path below) and skrutable installed.
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

# (dcs_text_dir_name, taxonomy data.json path relative to repo root, slug for vendor subdir)
BATCH = [
    ("Agnipurāṇa", "dge/data/purana/agni_purana/data.json", "agni_purana"),
    ("Matsyapurāṇa", "dge/data/purana/matsya_purana/data.json", "matsya_purana"),
    ("Kālikāpurāṇa", "dge/data/purana/upapuranas/kalika_purana/data.json", "kalika_purana"),
    ("Narasiṃhapurāṇa", "dge/data/purana/upapuranas/narasimha_purana/data.json", "narasimha_purana"),
    ("Varāhapurāṇa", "dge/data/purana/varaha_purana/data.json", "varaha_purana"),
    ("Gautamadharmasūtra", "dge/data/vedanga/kalpa/independent_dharmasutras/gautama_dharmasutra/data.json", "gautama_dharmasutra"),
    ("Nirukta", "dge/data/vedanga/nirukta/data.json", "nirukta"),
    ("Gopathabrāhmaṇa", "dge/data/vedas/atharvaveda/shaunaka_shakha/brahmana/gopatha_brahmana/data.json", "gopatha_brahmana"),
    ("Aitareya-Āraṇyaka", "dge/data/vedas/rigveda/shakala_shakha/aranyakas/aitareya_aranyaka/data.json", "aitareya_aranyaka"),
    ("Aitareyabrāhmaṇa", "dge/data/vedas/rigveda/shakala_shakha/brahmanas/aitareya_brahmana/data.json", "aitareya_brahmana"),
    ("Jaiminīyabrāhmaṇa", "dge/data/vedas/samaveda/jaiminiya_shakha/brahmanas/jaiminiya_brahmana/data.json", "jaiminiya_brahmana"),
    ("Sāmavidhānabrāhmaṇa", "dge/data/vedas/samaveda/kauthuma_shakha/brahmanas/samavidhana_brahmana/data.json", "samavidhana_brahmana"),
    ("Maitrāyaṇīsaṃhitā", "dge/data/vedas/yajurveda/krishna_yajurveda/maitrayani_shakha/samhita/maitrayani_samhita/data.json", "maitrayani_samhita"),
]


def main():
    results = []
    for dcs_name, rel_out, slug in BATCH:
        src_dir = os.path.join(DCS_MIRROR, dcs_name)
        if not os.path.isdir(src_dir):
            print(f"SKIP {dcs_name}: source dir not found at {src_dir}")
            continue
        vendor_dir = os.path.join(VENDOR_ROOT, slug)
        os.makedirs(vendor_dir, exist_ok=True)
        n_copied = 0
        for fname in os.listdir(src_dir):
            if fname.endswith(".conllu"):
                shutil.copy(os.path.join(src_dir, fname), os.path.join(vendor_dir, fname))
                n_copied += 1

        out_path = os.path.join(REPO, rel_out)
        count, chapters = build_generic_import(
            vendor_dir, out_path,
            source_name="Digital Corpus of Sanskrit (DCS), Oliver Hellwig, 2010-2024",
            source_url=(
                "https://github.com/OliverHellwig/sanskrit/tree/master/dcs/data/"
                f"conllu/files/{dcs_name}"
            ),
            licence="CC-BY 4.0",
            note=(
                "{count} units across {chapters} DCS carries of this text "
                "(may be an excerpt, not necessarily the complete classical "
                "work -- not independently checked against a full edition). "
                "See dge/PENDING.md, 24 Aug entry, for how this was matched."
            ),
            tag="dcs-import",
        )
        results.append((dcs_name, rel_out, n_copied, count, chapters))
        print(f"{dcs_name}: {n_copied} source files -> {count} items -> {rel_out}")

    print("\n--- summary ---")
    for dcs_name, rel_out, n_files, count, chapters in results:
        print(f"{dcs_name:25s} {count:6d} items  {rel_out}")


if __name__ == "__main__":
    main()
