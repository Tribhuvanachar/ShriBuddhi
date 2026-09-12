#!/usr/bin/env python3
"""
build_batch8_tantra_and_misc.py -- 23 Aug: the Tantra/Saiva-Sakta cluster,
deliberately deferred every batch until now ("include Pashupata Sutra and
Saiva/Sakta texts" -- explicit go-ahead this round), plus several loose
ends from the same request: the missing Pancha Mahakavya, the genre
research on 6 previously-unplaceable singles, and a structural fix.

STRUCTURAL FIX: agama.pancharatra.shaiva_agama and .shakta_agama are
reparented to agama.shaiva_agama / agama.shakta_agama directly -- they
were nested under "pancharatra" (a specifically VAISHNAVA term) despite
holding Shaiva/Shakta content, a naming mismatch flagged since the
original placement-proposal artifact. shaiva_agama already has real
content (Sivasutra, imported earlier this session) -- moved as a whole
leaf, not restructured internally, to avoid disrupting already-live
content/URLs more than necessary.

TANTRA/SAIVA-SAKTA: every placement checked against the text's own DCS
chapter header before filing, not assumed from its name -- this caught
a real one: "Satvatatantra" reads like a Sakta/generic tantra by name,
but its content is unambiguously Vaishnava (daśavatara doctrine, "iti
sri Satvatatantre Sivanaradasamvade", vaikunthaloka, purushottama
throughout) -- it is the Sattvata Samhita, one of the three ratna-traya
Pancharatra agamas, and fills the EXISTING empty sattvata_samhita leaf
instead of going anywhere near the Sakta cluster.

Two more corrections from checking headers rather than names:
- "Sphutarthavyakhya" sounds Saiva/generic but its chapter line is
  "zu AbhidhKo" -- a commentary on Abhidharmakosha (Buddhist), almost
  certainly Yashomitra's famous Sphutartha sub-commentary. Filed there,
  not here.
- "Yogaratnakara" sounds like a Hatha-yoga text by name, but its
  content and chapter tag ("YRa, Dh.") are Ayurvedic (a medical
  formulary/compendium, not Patanjali-style yoga) -- filed under
  Ayurveda instead.

New agama.pashupata / agama.pratyabhijna / agama.shaiva_siddhanta /
agama.shakta_agama(now populated as a container) / agama.natha_sampradaya
branches hold the rest. Two attributions are inferred from a DCS text's
standard scholarly name rather than DCS's own metadata (same caveat
pattern as batch 5/6's Gaudapada/vritti cases) -- Pancharthabhashya
attributed to Kaundinya, Mrigendratika to Narayanakantha -- flagged, not
asserted as fact.

PANCHA MAHAKAVYA: checked library.json first -- Raghuvamsha,
Kumarasambhava, Kiratarjuniya and Shishupalavadha are ALL already
populated:true. Only Naishadhiyacarita (Sriharsha) is missing, and DCS
does not carry it at all (checked by listing) -- flagged in
dge/PENDING.md as a genuine gap needing a non-DCS source, not filled
here.

UNPLACEABLE SINGLES: genre/author research (wisdomlib + secondary
sources) resolved 5 of 6 with reasonable confidence -- Krishiparashara
(agriculture), Syainikashastra (falconry, Rudradeva of Kumaon),
Agastiyaratnapariksha (Hindu gemology, not Jain), Ayurvedarasayana
(Hemadri's own AHS commentary -- resolves the earlier "zu AHS" puzzle),
Grihastharatnakara (Chandeshvara's dharmashastra nibandha, part of his
Smritiratnakara). Ratnadipika stays flagged low-confidence (gemology
genre reasonably solid, author/sect genuinely unconfirmable from open
sources) but is filed as gemology anyway rather than left out entirely,
since genre confidence alone is enough to place it sensibly.

SKANDAPURANA (REVAKHANDA): a separate research pass (web search against
wisdomlib/GRETIL/the Skandapurana Project) found this is a clean,
citable 1:1 whole-text match (DCS's 232 chapters = wisdomlib's complete
Revakhanda) -- unlike plain "Skandapurana" (a different, uncitable
recension entirely) and "Sivapurana" (a single chapter labelled with a
saMhita name outside the standard 7-saMhita scheme, unverifiable and
too little content to matter). Only Revakhanda imported; the other two
stay unmapped, per that research's own verdict. Note carried into the
title/notes: GRETIL flags that print editions may have misattributed
this material from the Vayupurana -- carried forward honestly, not
smoothed over.
"""
import collections
import json
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
OD = collections.OrderedDict


def leaf(schema, author=None):
    d = OD([("_schema", schema)])
    if author:
        d["_default_author"] = author
    return d


TAXONOMY_ADDITIONS = OD([
    ("pashupata", OD([
        ("pashupata_sutra", OD([
            ("mula", leaf("grantha_mula_text")),
            ("bhashya_kaundinya", leaf("grantha_tika_text", "Kaundinya (DCS metadata unconfirmed -- inferred from the text's standard scholarly name)")),
        ])),
        ("ganakarika", OD([
            ("mula", leaf("grantha_mula_text")),
            ("tika", leaf("grantha_tika_text")),
        ])),
    ])),
    ("pratyabhijna", OD([
        ("spanda_karika", OD([
            ("mula", leaf("grantha_mula_text", "Vasugupta (or Kallata)")),
            ("tika_nirnaya", leaf("grantha_tika_text", "Kshemaraja")),
        ])),
        ("shiva_sutra_vartika", OD([("mula", leaf("grantha_tika_text", "Bhaskara"))])),
        ("tantraloka", OD([("mula", leaf("grantha_mula_text", "Abhinavagupta"))])),
        ("tantrasara", OD([("mula", leaf("grantha_mula_text", "Abhinavagupta"))])),
        ("samvitsiddhi", OD([("mula", leaf("grantha_mula_text"))])),
    ])),
    ("shaiva_siddhanta", OD([
        ("mrigendra_tantra", OD([
            ("mula", leaf("grantha_mula_text")),
            ("tika", leaf("grantha_tika_text", "Narayanakantha (DCS metadata unconfirmed -- inferred from the text's standard scholarly name)")),
        ])),
    ])),
    ("natha_sampradaya", OD([
        ("amaraughashasana", OD([
            ("mula", leaf("grantha_mula_text")),
            ("tika", leaf("grantha_tika_text")),
        ])),
        ("gorakshashataka", OD([("mula", leaf("grantha_mula_text"))])),
        ("gheranda_samhita", OD([("mula", leaf("grantha_mula_text"))])),
        ("hathayogapradipika", OD([("mula", leaf("grantha_mula_text", "Svatmarama"))])),
        ("vatulanatha_sutras", OD([
            ("mula", leaf("grantha_mula_text")),
            ("vritti", leaf("grantha_tika_text")),
        ])),
    ])),
])

SHAKTA_AGAMA_ADDITIONS = OD([
    ("mahacina_tantra", OD([("mula", leaf("grantha_mula_text"))])),
    ("matrikabheda_tantra", OD([("mula", leaf("grantha_mula_text"))])),
    ("todala_tantra", OD([("mula", leaf("grantha_mula_text"))])),
    ("uddamareshvara_tantra", OD([("mula", leaf("grantha_mula_text"))])),
    ("devikalottara_agama", OD([("mula", leaf("grantha_mula_text"))])),
    ("shakta_vijnana", OD([("mula", leaf("grantha_mula_text"))])),
])

SHASTRA_MISC_ADDITIONS = OD([
    ("krishi_shastra", OD([("mula", leaf("grantha_mula_text", "attributed to Parashara (pseudepigraphic)"))])),
    ("shainika_shastra", OD([("mula", leaf("grantha_mula_text", "Raja Rudradeva of Kumaon"))])),
    ("ratna_pariksha", OD([
        ("agastiya", leaf("grantha_mula_text", "attributed to Agastya (pseudepigraphic); Hindu, not Jain -- see dge/PENDING.md")),
        ("ratnadipika", leaf("grantha_mula_text", "author/sect unconfirmed -- see dge/PENDING.md")),
    ])),
])

# (dcs_name, rel_out, slug, title, taxonomy_kind)
# taxonomy_kind: None = fills an existing empty leaf; "new_leaf" = library.json entry needed
ENTRIES = [
    # Ayurveda corrections/additions
    ("Yogaratnākara", "dge/data/vedas/upaveda/ayurveda/samhita/yogaratnakara/mula/data.json", "yogaratnakara", "योगरत्नाकरः", "new_leaf"),
    ("Ayurvedarasāyana", "dge/data/vedas/upaveda/ayurveda/samhita/ashtanga_hridaya_samhita/tika_hemadri/data.json", "ayurveda_rasayana_hemadri", "अष्टाङ्गहृदयसंहिता (आयुर्वेदरसायनम् — हेमाद्रिः)", "new_leaf"),
    # Buddhist correction
    ("Sphuṭārthāvyākhyā", "dge/data/shastra/bauddha_sahitya/shastra/abhidharma_kosha/tika_sphutartha/data.json", "abhidharmakosha_sphutartha", "अभिधर्मकोशः (स्फुटार्था — यशोमित्रः)", "new_leaf"),
    # Vaishnava correction -- fills existing sattvata_samhita stub
    ("Sātvatatantra", "dge/data/agama/pancharatra/pancharatra_samhitas/sattvata_samhita/data.json", "sattvata_samhita", "सात्वतसंहिता", None),
    # Pashupata
    ("Pāśupatasūtra", "dge/data/agama/pashupata/pashupata_sutra/mula/data.json", "pashupata_sutra_mula", "पाशुपतसूत्रम्", "new_leaf"),
    ("Pañcārthabhāṣya", "dge/data/agama/pashupata/pashupata_sutra/bhashya_kaundinya/data.json", "pancharthabhashya", "पाशुपतसूत्रम् (पञ्चार्थभाष्यम्)", "new_leaf"),
    ("Gaṇakārikā", "dge/data/agama/pashupata/ganakarika/mula/data.json", "ganakarika_mula", "गणकारिका", "new_leaf"),
    ("Ratnaṭīkā", "dge/data/agama/pashupata/ganakarika/tika/data.json", "ganakarika_ratnatika", "गणकारिका (रत्नटीका)", "new_leaf"),
    # Pratyabhijna
    ("Spandakārikā", "dge/data/agama/pratyabhijna/spanda_karika/mula/data.json", "spanda_karika_mula", "स्पन्दकारिका", "new_leaf"),
    ("Spandakārikānirṇaya", "dge/data/agama/pratyabhijna/spanda_karika/tika_nirnaya/data.json", "spanda_karika_nirnaya", "स्पन्दकारिका (निर्णयः — क्षेमराजः)", "new_leaf"),
    ("Śivasūtravārtika", "dge/data/agama/pratyabhijna/shiva_sutra_vartika/mula/data.json", "shiva_sutra_vartika", "शिवसूत्रवार्त्तिकम् (भास्करः)", "new_leaf"),
    ("Tantrāloka", "dge/data/agama/pratyabhijna/tantraloka/mula/data.json", "tantraloka", "तन्त्रालोकः", "new_leaf"),
    ("Tantrasāra", "dge/data/agama/pratyabhijna/tantrasara/mula/data.json", "tantrasara", "तन्त्रसारः", "new_leaf"),
    ("Saṃvitsiddhi", "dge/data/agama/pratyabhijna/samvitsiddhi/mula/data.json", "samvitsiddhi", "संवित्सिद्धिः", "new_leaf"),
    # Shaiva Siddhanta
    ("Mṛgendratantra", "dge/data/agama/shaiva_siddhanta/mrigendra_tantra/mula/data.json", "mrigendra_tantra_mula", "मृगेन्द्रतन्त्रम्", "new_leaf"),
    ("Mṛgendraṭīkā", "dge/data/agama/shaiva_siddhanta/mrigendra_tantra/tika/data.json", "mrigendra_tika", "मृगेन्द्रतन्त्रम् (टीका)", "new_leaf"),
    # Shakta
    ("Mahācīnatantra", "dge/data/agama/pancharatra/shakta_agama/mahacina_tantra/mula/data.json", "mahacina_tantra", "महाचीनतन्त्रम्", "new_leaf"),
    ("Mātṛkābhedatantra", "dge/data/agama/pancharatra/shakta_agama/matrikabheda_tantra/mula/data.json", "matrikabheda_tantra", "मातृकाभेदतन्त्रम्", "new_leaf"),
    ("Toḍalatantra", "dge/data/agama/pancharatra/shakta_agama/todala_tantra/mula/data.json", "todala_tantra", "तोडलतन्त्रम्", "new_leaf"),
    ("Uḍḍāmareśvaratantra", "dge/data/agama/pancharatra/shakta_agama/uddamareshvara_tantra/mula/data.json", "uddamareshvara_tantra", "उड्डामरेश्वरतन्त्रम्", "new_leaf"),
    ("Devīkālottarāgama", "dge/data/agama/pancharatra/shakta_agama/devikalottara_agama/mula/data.json", "devikalottara_agama", "देवीकालोत्तरागमः", "new_leaf"),
    ("Śāktavijñāna", "dge/data/agama/pancharatra/shakta_agama/shakta_vijnana/mula/data.json", "shakta_vijnana", "शाक्तविज्ञानम्", "new_leaf"),
    # Natha sampradaya / Hatha yoga
    ("Amaraughaśāsana", "dge/data/agama/natha_sampradaya/amaraughashasana/mula/data.json", "amaraughashasana_mula", "अमरौघशासनम्", "new_leaf"),
    ("Commentary on Amaraughaśāsana", "dge/data/agama/natha_sampradaya/amaraughashasana/tika/data.json", "amaraughashasana_tika", "अमरौघशासनम् (टीका)", "new_leaf"),
    ("Gorakṣaśataka", "dge/data/agama/natha_sampradaya/gorakshashataka/mula/data.json", "gorakshashataka", "गोरक्षशतकम्", "new_leaf"),
    ("Gheraṇḍasaṃhitā", "dge/data/agama/natha_sampradaya/gheranda_samhita/mula/data.json", "gheranda_samhita", "घेरण्डसंहिता", "new_leaf"),
    ("Haṭhayogapradīpikā", "dge/data/agama/natha_sampradaya/hathayogapradipika/mula/data.json", "hathayogapradipika", "हठयोगप्रदीपिका", "new_leaf"),
    ("Vātūlanāthasūtras", "dge/data/agama/natha_sampradaya/vatulanatha_sutras/mula/data.json", "vatulanatha_sutras_mula", "वातूलनाथसूत्राणि", "new_leaf"),
    ("Vātūlanāthasūtravṛtti", "dge/data/agama/natha_sampradaya/vatulanatha_sutras/vritti/data.json", "vatulanatha_sutras_vritti", "वातूलनाथसूत्राणि (वृत्तिः)", "new_leaf"),
    # Unplaceable singles, resolved
    ("Kṛṣiparāśara", "dge/data/shastra/krishi_shastra/mula/data.json", "krishiparashara", "कृषिपराशरः", "new_leaf"),
    ("Śyainikaśāstra", "dge/data/shastra/shainika_shastra/mula/data.json", "syainikashastra", "श्यैनिकशास्त्रम्", "new_leaf"),
    ("Agastīyaratnaparīkṣā", "dge/data/shastra/ratna_pariksha/agastiya/data.json", "agastiyaratnapariksha", "अगस्तीयरत्नपरीक्षा", "new_leaf"),
    ("Ratnadīpikā", "dge/data/shastra/ratna_pariksha/ratnadipika/data.json", "ratnadipika", "रत्नदीपिका", "new_leaf"),
    ("Gṛhastharatnākara", "dge/data/smriti_dharma/dharmashastra/grihastha_ratnakara/data.json", "grihastharatnakara", "गृहस्थरत्नाकरः (चण्डेश्वरः — स्मृतिरत्नाकरान्तर्गतः)", "new_leaf"),
    # Skandapurana (Revakhanda)
    ("Skandapurāṇa (Revākhaṇḍa)", "dge/data/purana/skanda_purana/revakhanda/data.json", "skandapurana_revakhanda", "स्कन्दपुराणम् (रेवाखण्डः — GRETIL के अनुसार सम्भवतः वायुपुराणस्य पाठः, मुद्रितसंस्करणे स्कन्दपुराणे अन्तर्भूतः)", "new_leaf"),
]


def merge_taxonomy():
    path = os.path.join(REPO, "dge/data/taxonomy.json")
    with open(path, encoding="utf-8") as f:
        d = json.load(f, object_pairs_hook=collections.OrderedDict)

    # structural fix: reparent shaiva_agama / shakta_agama from pancharatra to agama
    pr = d["agama"]["pancharatra"]
    shaiva_agama = pr.pop("shaiva_agama")
    shakta_agama = pr.pop("shakta_agama")
    d["agama"]["shaiva_agama"] = shaiva_agama
    shakta_agama.update(SHAKTA_AGAMA_ADDITIONS)
    d["agama"]["shakta_agama"] = shakta_agama

    for key, subtree in TAXONOMY_ADDITIONS.items():
        assert key not in d["agama"], key
        d["agama"][key] = subtree

    for key, subtree in SHASTRA_MISC_ADDITIONS.items():
        assert key not in d["shastra"], key
        d["shastra"][key] = subtree

    d["shastra"]["bauddha_sahitya"]["shastra"]["abhidharma_kosha"]["tika_sphutartha"] = leaf(
        "grantha_tika_text", "Yashomitra (DCS metadata unconfirmed -- inferred from the text's standard scholarly name)")

    d["vedas"]["upaveda"]["ayurveda"]["samhita"]["yogaratnakara"] = OD([
        ("mula", leaf("grantha_mula_text"))])
    d["vedas"]["upaveda"]["ayurveda"]["samhita"]["ashtanga_hridaya_samhita"]["tika_hemadri"] = leaf(
        "grantha_tika_text", "Hemadri")

    d["purana"]["skanda_purana"]["revakhanda"] = leaf("grantha_mula_text")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("taxonomy.json: reparented shaiva_agama/shakta_agama, added Tantra/Saiva-Sakta, misc, Skandapurana nodes")


def move_shaiva_agama_files():
    old_dir = os.path.join(REPO, "dge/data/agama/pancharatra/shaiva_agama")
    new_dir = os.path.join(REPO, "dge/data/agama/shaiva_agama")
    old_shakta = os.path.join(REPO, "dge/data/agama/pancharatra/shakta_agama")
    new_shakta = os.path.join(REPO, "dge/data/agama/shakta_agama")
    if os.path.isdir(old_dir) and not os.path.isdir(new_dir):
        shutil.move(old_dir, new_dir)
        print(f"moved {old_dir} -> {new_dir}")
    if os.path.isdir(old_shakta) and not os.path.isdir(new_shakta):
        shutil.move(old_shakta, new_shakta)
        print(f"moved {old_shakta} -> {new_shakta}")


def update_library(populated_paths):
    path = os.path.join(REPO, "dge/data/library.json")
    with open(path, encoding="utf-8") as f:
        d = json.load(f, object_pairs_hook=collections.OrderedDict)
    by_path = {g["path"]: g for g in d["granthas"]}
    flipped = added = renamed = 0

    # reparent existing catalog rows for shaiva_agama/shakta_agama
    for g in d["granthas"]:
        if g["path"].startswith("dge/data/agama/pancharatra/shaiva_agama/") or g["path"].startswith("dge/data/agama/pancharatra/shakta_agama/"):
            g["path"] = g["path"].replace("dge/data/agama/pancharatra/", "dge/data/agama/", 1)
            renamed += 1
    by_path = {g["path"]: g for g in d["granthas"]}

    for _, rel_out, _, title, kind in ENTRIES:
        if rel_out in by_path:
            if rel_out in populated_paths and not by_path[rel_out]["populated"]:
                by_path[rel_out]["populated"] = True
                flipped += 1
        else:
            assert kind == "new_leaf", f"unexpected new library.json path {rel_out}"
            d["granthas"].append(OD([("path", rel_out), ("populated", rel_out in populated_paths), ("title", title)]))
            added += 1

    with open(path, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"library.json: reparented {renamed}, flipped {flipped}, added {added}")


def run_imports():
    populated_paths = set()
    for dcs_name, rel_out, slug, _, _ in ENTRIES:
        src_dir = os.path.join(DCS_MIRROR, dcs_name)
        if not os.path.isdir(src_dir):
            print(f"SKIP {dcs_name}: not found in DCS mirror")
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
                "entry (batch 8, Tantra/Saiva-Sakta + misc cleanup), for how "
                "this was matched."
            ),
            tag="dcs-import",
        )
        populated_paths.add(rel_out)
        print(f"{dcs_name}: {n} files -> {count} items -> {rel_out}")
    return populated_paths


def main():
    merge_taxonomy()
    move_shaiva_agama_files()
    populated_paths = run_imports()
    update_library(populated_paths)
    print(f"\n{len(populated_paths)}/{len(ENTRIES)} matched and imported")


if __name__ == "__main__":
    main()
