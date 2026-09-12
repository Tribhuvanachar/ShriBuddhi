#!/usr/bin/env python3
"""
build_batch2.py -- second batch, 24 Aug: the Tier A items from the DCS
taxonomy-placement proposal (see dge/PENDING.md) that a plain exact-name
match couldn't find, because they land inside existing empty sub-leaves
one level deeper than library.json's top-level path (vedanga/kalpa's
per-shakha shrautasutra/grihyasutra/dharmasutra structure), or because a
single DCS text splits across several existing leaves by book/kanda
number (Vishnu/Linga/Kurma Purana's amshas/bhagas, Paippalada
Atharvaveda's kandas).

Every target path below was checked against library.json directly
(populated: false) before being listed here -- not assumed from the name.
"""
import os
import shutil

from dcs_common import build_generic_import, build_split_import

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DCS_MIRROR = os.environ.get(
    "DCS_MIRROR",
    "/tmp/claude-0/-home-user-bhumandala/e8a5c83c-760f-5d7b-9fbc-3df8440bd264/scratchpad/sanskrit_check/dcs/data/conllu/files",
)
VENDOR_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor")

SOURCE_NAME = "Digital Corpus of Sanskrit (DCS), Oliver Hellwig, 2010-2024"
LICENCE = "CC-BY 4.0"


def source_url(dcs_name):
    return f"https://github.com/OliverHellwig/sanskrit/tree/master/dcs/data/conllu/files/{dcs_name}"


def vendor_for(dcs_name, slug):
    src_dir = os.path.join(DCS_MIRROR, dcs_name)
    if not os.path.isdir(src_dir):
        print(f"SKIP {dcs_name}: source dir not found")
        return None
    vendor_dir = os.path.join(VENDOR_ROOT, slug)
    os.makedirs(vendor_dir, exist_ok=True)
    n = 0
    for fname in os.listdir(src_dir):
        if fname.endswith(".conllu"):
            shutil.copy(os.path.join(src_dir, fname), os.path.join(vendor_dir, fname))
            n += 1
    return vendor_dir, n


# --- single-target imports: (dcs_name, out_path relative to repo, slug) ---
SINGLE = [
    ("Kauśikasūtra", "dge/data/vedanga/kalpa/atharvaveda/kaushika/grihyasutra/data.json", "kausikasutra"),
    ("Vaitānasūtra", "dge/data/vedanga/kalpa/atharvaveda/vaitana/shrautasutra/data.json", "vaitanasutra"),
    ("Vasiṣṭhadharmasūtra", "dge/data/vedanga/kalpa/independent_dharmasutras/vasishtha_dharmasutra/data.json", "vasishtha_dharmasutra"),
    ("Āpastambadharmasūtra", "dge/data/vedanga/kalpa/krishna_yajurveda/apastamba/dharmasutra/data.json", "apastamba_dharmasutra"),
    ("Āpastambagṛhyasūtra", "dge/data/vedanga/kalpa/krishna_yajurveda/apastamba/grihyasutra/data.json", "apastamba_grihyasutra"),
    ("Āpastambaśrautasūtra", "dge/data/vedanga/kalpa/krishna_yajurveda/apastamba/shrautasutra/data.json", "apastamba_shrautasutra"),
    ("Baudhāyanadharmasūtra", "dge/data/vedanga/kalpa/krishna_yajurveda/baudhayana/dharmasutra/data.json", "baudhayana_dharmasutra"),
    ("Baudhāyanagṛhyasūtra", "dge/data/vedanga/kalpa/krishna_yajurveda/baudhayana/grihyasutra/data.json", "baudhayana_grihyasutra"),
    ("Baudhāyanaśrautasūtra", "dge/data/vedanga/kalpa/krishna_yajurveda/baudhayana/shrautasutra/data.json", "baudhayana_shrautasutra"),
    ("Bhāradvājagṛhyasūtra", "dge/data/vedanga/kalpa/krishna_yajurveda/bharadvaja/grihyasutra/data.json", "bharadvaja_grihyasutra"),
    ("Bhāradvājaśrautasūtra", "dge/data/vedanga/kalpa/krishna_yajurveda/bharadvaja/shrautasutra/data.json", "bharadvaja_shrautasutra"),
    ("Hiraṇyakeśigṛhyasūtra", "dge/data/vedanga/kalpa/krishna_yajurveda/hiranyakeshin/grihyasutra/data.json", "hiranyakeshi_grihyasutra"),
    ("Kāṭhakagṛhyasūtra", "dge/data/vedanga/kalpa/krishna_yajurveda/kathaka/grihyasutra/data.json", "kathaka_grihyasutra"),
    ("Mānavagṛhyasūtra", "dge/data/vedanga/kalpa/krishna_yajurveda/manava/grihyasutra/data.json", "manava_grihyasutra"),
    ("Vaikhānasadharmasūtra", "dge/data/vedanga/kalpa/krishna_yajurveda/vaikhanasa/dharmasutra/data.json", "vaikhanasa_dharmasutra"),
    ("Vaikhānasagṛhyasūtra", "dge/data/vedanga/kalpa/krishna_yajurveda/vaikhanasa/grihyasutra/data.json", "vaikhanasa_grihyasutra"),
    ("Vaikhānasaśrautasūtra", "dge/data/vedanga/kalpa/krishna_yajurveda/vaikhanasa/shrautasutra/data.json", "vaikhanasa_shrautasutra"),
    ("Āśvalāyanagṛhyasūtra", "dge/data/vedanga/kalpa/rigveda/ashvalayana/grihyasutra/data.json", "asvalayana_grihyasutra"),
    ("Āśvālāyanaśrautasūtra", "dge/data/vedanga/kalpa/rigveda/ashvalayana/shrautasutra/data.json", "asvalayana_shrautasutra"),
    ("Śāṅkhāyanagṛhyasūtra", "dge/data/vedanga/kalpa/rigveda/shankhayana/grihyasutra/data.json", "shankhayana_grihyasutra"),
    ("Śāṅkhāyanaśrautasūtra", "dge/data/vedanga/kalpa/rigveda/shankhayana/shrautasutra/data.json", "shankhayana_shrautasutra"),
    ("Drāhyāyaṇaśrautasūtra", "dge/data/vedanga/kalpa/samaveda/drahyayana/shrautasutra/data.json", "drahyayana_shrautasutra"),
    ("Gobhilagṛhyasūtra", "dge/data/vedanga/kalpa/samaveda/gobhila/grihyasutra/data.json", "gobhila_grihyasutra"),
    ("Jaiminigṛhyasūtra", "dge/data/vedanga/kalpa/samaveda/jaiminiya/grihyasutra/data.json", "jaiminiya_grihyasutra"),
    ("Khādiragṛhyasūtra", "dge/data/vedanga/kalpa/samaveda/khadira/grihyasutra/data.json", "khadira_grihyasutra"),
    ("Kātyāyanaśrautasūtra", "dge/data/vedanga/kalpa/shukla_yajurveda/katyayana/shrautasutra/data.json", "katyayana_shrautasutra"),
    ("Pāraskaragṛhyasūtra", "dge/data/vedanga/kalpa/shukla_yajurveda/paraskara/grihyasutra/data.json", "paraskara_grihyasutra"),
    ("Vaiśeṣikasūtra", "dge/data/darshana/vaisheshika/sutra_and_bhashya/vaisheshika_sutra/mula/data.json", "vaisheshika_sutra"),
    ("Nyāyasūtra", "dge/data/darshana/nyaya/prachina_nyaya/nyaya_sutra/mula/data.json", "nyaya_sutra"),
    ("Nyāyabhāṣya", "dge/data/darshana/nyaya/prachina_nyaya/nyaya_sutra/bhashya_vatsyayana/data.json", "nyaya_bhashya"),
    ("Kāṭhakasaṃhitā", "dge/data/vedas/yajurveda/krishna_yajurveda/katha_shakha/samhita/katha_samhita/data.json", "kathaka_samhita"),
    ("Garuḍapurāṇa", "dge/data/purana/garuda_purana/purva_khanda/data.json", "garuda_purana"),
]

# --- split imports: one DCS text -> several existing leaves by book number ---
SPLIT = [
    ("Viṣṇupurāṇa", "vishnu_purana", {
        1: "dge/data/purana/vishnu_purana/amsha_01/data.json",
        2: "dge/data/purana/vishnu_purana/amsha_02/data.json",
        3: "dge/data/purana/vishnu_purana/amsha_03/data.json",
        4: "dge/data/purana/vishnu_purana/amsha_04/data.json",
        5: "dge/data/purana/vishnu_purana/amsha_05/data.json",
        6: "dge/data/purana/vishnu_purana/amsha_06/data.json",
    }),
    ("Liṅgapurāṇa", "linga_purana", {
        1: "dge/data/purana/linga_purana/purva_bhaga/data.json",
        2: "dge/data/purana/linga_purana/uttara_bhaga/data.json",
    }),
    ("Kūrmapurāṇa", "kurma_purana", {
        1: "dge/data/purana/kurma_purana/purva_bhaga/data.json",
        2: "dge/data/purana/kurma_purana/uttara_bhaga/data.json",
    }),
    ("Atharvaveda (Paippalāda)", "atharvaveda_paippalada", {
        1: "dge/data/vedas/atharvaveda/paippalada_shakha/samhita/kanda_01/data.json",
        4: "dge/data/vedas/atharvaveda/paippalada_shakha/samhita/kanda_04/data.json",
        5: "dge/data/vedas/atharvaveda/paippalada_shakha/samhita/kanda_05/data.json",
        10: "dge/data/vedas/atharvaveda/paippalada_shakha/samhita/kanda_10/data.json",
        12: "dge/data/vedas/atharvaveda/paippalada_shakha/samhita/kanda_12/data.json",
        19: "dge/data/vedas/atharvaveda/paippalada_shakha/samhita/kanda_19/data.json",
    }),
]


def main():
    touched_paths = []

    for dcs_name, rel_out, slug in SINGLE:
        r = vendor_for(dcs_name, slug)
        if not r:
            continue
        vendor_dir, n_copied = r
        out_path = os.path.join(REPO, rel_out)
        count, chapters = build_generic_import(
            vendor_dir, out_path,
            source_name=SOURCE_NAME, source_url=source_url(dcs_name), licence=LICENCE,
            note=(
                "{count} units across {chapters} DCS carries of this text "
                "(may be an excerpt, not the complete classical work). "
                "See dge/PENDING.md, 24 Aug entry (batch 2), for how this was matched."
            ),
            tag="dcs-import",
        )
        touched_paths.append(rel_out)
        print(f"{dcs_name}: {n_copied} files -> {count} items -> {rel_out}")

    for dcs_name, slug, book_map in SPLIT:
        r = vendor_for(dcs_name, slug)
        if not r:
            continue
        vendor_dir, n_copied = r
        abs_book_map = {b: os.path.join(REPO, p) for b, p in book_map.items()}
        results = build_split_import(
            vendor_dir, abs_book_map,
            source_name=SOURCE_NAME, source_url=source_url(dcs_name), licence=LICENCE,
            note=(
                "{{count}} units ({{chapters}}) of this book/kanda of " + dcs_name + " from DCS. "
                "See dge/PENDING.md, 24 Aug entry (batch 2), for the book-number "
                "to taxonomy-leaf mapping used to split this text."
            ).replace("{{count}}", "{count}").replace("{{chapters}}", "{chapters}"),
            tag="dcs-import",
        )
        skipped = results.pop("skipped", [])
        print(f"\n{dcs_name} ({n_copied} files):")
        for book, (count, chapters) in results.items():
            rel = book_map[book]
            touched_paths.append(rel)
            print(f"  book {book}: {count} items -> {rel}")
        if skipped:
            print(f"  skipped (no mapped leaf for book number): {skipped}")

    print("\n--- touched data.json paths (for library.json flip) ---")
    for p in touched_paths:
        print(p)


if __name__ == "__main__":
    main()
