#!/usr/bin/env python3
"""
NOTE (23 Aug, later same session): "upaveda" was moved from a top-level
taxonomy.json key to nested under "vedas" (vedas.upaveda) after this
script ran, per the project lead's explicit structural feedback --
"under Veda you can have Upaveda... Sastra is a different parent folder
just like itihasa and Purana". The rel_out paths below (dge/data/upaveda/...)
are historical -- what this script actually wrote at the time -- and are
NOT the current on-disk location (now dge/data/vedas/upaveda/...). Left
unedited as a record of what ran; see dge/PENDING.md for the move itself.

build_batch5_upaveda_shastra.py -- Tier B, 23 Aug continued: two brand new
top-level taxonomy branches, per the project lead's explicit framework
(not this session's invention): a "shastra" (शास्त्राणि) catch-all for
Natya/Kama/Niti-shastra and Buddhist literature, and "upaveda" (उपवेदाः)
for Ayurveda (+ its Rasashastra/Nighantu sub-genres) and Dhanurveda.
Gandharvaveda and Sthapatyaveda are added as empty stub nodes -- no DCS
match found for either, left for a future pass rather than guessed at.

Every placement below was checked against each text's own DCS chapter
header, not assumed from its DCS-given name -- this caught two real
misattributions before they happened: "Ayurvedarasayana" and "Ratnadipika"
both looked like Ayurveda/Rasashastra texts by name but their own chapter
lines ("zu AHS" for the former's is ambiguous/unclear, ambiguous
invocation register for the latter) didn't confirm it cleanly enough, so
both are EXCLUDED here rather than guessed in. "Ratnatika" looked like a
rasashastra commentary by name but its chapter line reads "zu GanaKar"
(Ganakarika, a Pashupata Shaiva text) -- a real near-miss, excluded
entirely as out of scope for this batch (Tantra/Shaiva cluster is
deliberately still deferred). "Nighantushesha" opens with an invocation
to the Arhat (a Jain text) -- kept under ayurveda.nighantu as a judgment
call (it's the same synonym-lexicon genre as the other nighantus, not a
strictly Ayurvedic clinical text), flagged in dge/PENDING.md rather than
asserted with full confidence.

Checking Carakasamhita's own chapter headers before importing also found
a 5th DCS chapter-numbering convention (see dcs_common.py's
_parse_chapter_path) -- a non-numeric section name, e.g. "Ca, Su., 1" vs
"Ca, Cik., 1", interleaved with the numeric fields. Fixed there, not
worked around here.
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


# --- taxonomy.json tree to merge under new top-level keys "upaveda", "shastra" ---

TAXONOMY_ADDITIONS = OD([
    ("upaveda", OD([
        ("ayurveda", OD([
            ("samhita", OD([
                ("caraka_samhita", OD([
                    ("mula", leaf("grantha_mula_text", "Agnivesha (redacted by Charaka)")),
                    ("tika_ayurvedadipika", leaf("grantha_tika_text", "Chakrapanidatta")),
                    ("tika_tattvapradipika", leaf("grantha_tika_text")),
                ])),
                ("sushruta_samhita", OD([
                    ("mula", leaf("grantha_mula_text", "Sushruta")),
                ])),
                ("ashtanga_hridaya_samhita", OD([
                    ("mula", leaf("grantha_mula_text", "Vagbhata")),
                    ("tika_sarvangasundara", leaf("grantha_tika_text", "Arunadatta")),
                    ("tika_padarthacandrika", leaf("grantha_tika_text")),
                    ("tika_indu", leaf("grantha_tika_text", "Indu")),
                ])),
                ("ashtanga_sangraha", OD([
                    ("mula", leaf("grantha_mula_text", "Vagbhata")),
                ])),
                ("bhavaprakasha", OD([
                    ("mula", leaf("grantha_mula_text", "Bhavamishra")),
                ])),
                ("nadi_pariksha", OD([
                    ("mula", leaf("grantha_mula_text")),
                ])),
            ])),
            ("nighantu", OD([
                ("ashtanga_nighantu", OD([("mula", leaf("grantha_mula_text"))])),
                ("bija_nighantu", OD([("mula", leaf("grantha_mula_text"))])),
                ("dhanvantari_nighantu", OD([("mula", leaf("grantha_mula_text"))])),
                ("kaiyadeva_nighantu", OD([("mula", leaf("grantha_mula_text", "Kaiyadeva"))])),
                ("madanapala_nighantu", OD([("mula", leaf("grantha_mula_text", "Madanapala"))])),
                ("raja_nighantu", OD([("mula", leaf("grantha_mula_text", "Narahari Pandita"))])),
                ("nighantushesha", OD([("mula", leaf("grantha_mula_text", "Hemachandra"))])),
            ])),
            ("rasashastra", OD([
                ("rasahridaya_tantra", OD([("mula", leaf("grantha_mula_text", "Govinda Bhagavatpada"))])),
                ("rasakamadhenu", OD([("mula", leaf("grantha_mula_text"))])),
                ("rasamanjari", OD([("mula", leaf("grantha_mula_text", "Shalinatha"))])),
                ("rasaprakashasudhakara", OD([("mula", leaf("grantha_mula_text", "Yashodhara Bhatta"))])),
                ("rasaratnasamuccaya", OD([
                    ("mula", leaf("grantha_mula_text", "Vagbhata (rasashastra author)")),
                    ("tika_bodhini", leaf("grantha_tika_text")),
                    ("tika_dipika", leaf("grantha_tika_text")),
                    ("tika", leaf("grantha_tika_text")),
                ])),
                ("rasaratnakara", OD([("mula", leaf("grantha_mula_text", "Nityanatha Siddha"))])),
                ("rasasanketakalika", OD([("mula", leaf("grantha_mula_text"))])),
                ("rasatarangini", OD([("mula", leaf("grantha_mula_text", "Sadananda Sharma"))])),
                ("rasendracintamani", OD([("mula", leaf("grantha_mula_text", "Dhundhukanatha"))])),
                ("rasendracudamani", OD([("mula", leaf("grantha_mula_text", "Somadeva"))])),
                ("rasendrasarasangraha", OD([("mula", leaf("grantha_mula_text", "Gopalakrishna Bhatta"))])),
                ("rasarnava", OD([("mula", leaf("grantha_mula_text"))])),
                ("rasarnavakalpa", OD([("mula", leaf("grantha_mula_text"))])),
                ("rasadhyaya", OD([
                    ("mula", leaf("grantha_mula_text")),
                    ("tika", leaf("grantha_tika_text")),
                ])),
            ])),
        ])),
        ("dhanurveda", OD([
            ("mula", leaf("grantha_mula_text")),
        ])),
        ("gandharvaveda", OD()),
        ("sthapatyaveda", OD()),
    ])),
    ("shastra", OD([
        ("natya_shastra", OD([
            ("mula", leaf("grantha_mula_text", "Bharata Muni")),
            ("tika", leaf("grantha_tika_text")),
        ])),
        ("kama_shastra", OD([
            ("mula", leaf("grantha_mula_text", "Vatsyayana")),
        ])),
        ("niti_shastra", OD([
            ("artha_shastra", OD([("mula", leaf("grantha_mula_text", "Kautilya"))])),
            ("hitopadesha", OD([("mula", leaf("grantha_mula_text", "Narayana Pandita"))])),
        ])),
        ("bauddha_sahitya", OD([
            ("sutra", OD([
                ("saddharma_pundarika_sutra", OD([("mula", leaf("grantha_mula_text"))])),
                ("lankavatara_sutra", OD([("mula", leaf("grantha_mula_text"))])),
            ])),
            ("shastra", OD([
                ("abhidharma_kosha", OD([
                    ("mula", leaf("grantha_mula_text", "Vasubandhu")),
                    ("bhashya", leaf("grantha_tika_text", "Vasubandhu")),
                ])),
                ("mula_madhyamaka_karika", OD([
                    ("mula", leaf("grantha_mula_text", "Nagarjuna")),
                    ("tika_prasannapada", leaf("grantha_tika_text", "Chandrakirti")),
                ])),
                ("vimshatika", OD([
                    ("mula", leaf("grantha_mula_text", "Vasubandhu")),
                    ("vritti", leaf("grantha_tika_text", "Vasubandhu")),
                ])),
                ("bodhicaryavatara", OD([("mula", leaf("grantha_mula_text", "Shantideva"))])),
                ("shikshasamuccaya", OD([("mula", leaf("grantha_mula_text", "Shantideva"))])),
                ("ashtasahasrika_prajnaparamita", OD([("mula", leaf("grantha_mula_text"))])),
            ])),
            ("pramana", OD([
                ("nyayabindu", OD([("mula", leaf("grantha_mula_text", "Dharmakirti"))])),
            ])),
            ("avadana", OD([
                ("avadanashataka", OD([("mula", leaf("grantha_mula_text"))])),
                ("divyavadana", OD([("mula", leaf("grantha_mula_text"))])),
                ("sanghabhedavastu", OD([("mula", leaf("grantha_mula_text"))])),
            ])),
        ])),
    ])),
])


# --- library.json entries + DCS import targets: (dcs_name_or_None, rel_out_path, slug, title_devanagari) ---

ENTRIES = [
    ("Carakasaṃhitā", "dge/data/upaveda/ayurveda/samhita/caraka_samhita/mula/data.json", "caraka_samhita_mula", "चरकसंहिता"),
    ("Carakatattvapradīpikā", "dge/data/upaveda/ayurveda/samhita/caraka_samhita/tika_tattvapradipika/data.json", "caraka_tattvapradipika", "चरकसंहिता (तत्त्वप्रदीपिका)"),
    ("Āyurvedadīpikā", "dge/data/upaveda/ayurveda/samhita/caraka_samhita/tika_ayurvedadipika/data.json", "caraka_ayurvedadipika", "चरकसंहिता (आयुर्वेददीपिका — चक्रपाणिदत्तः)"),
    ("Suśrutasaṃhitā", "dge/data/upaveda/ayurveda/samhita/sushruta_samhita/mula/data.json", "sushruta_samhita_mula", "सुश्रुतसंहिता"),
    ("Aṣṭāṅgahṛdayasaṃhitā", "dge/data/upaveda/ayurveda/samhita/ashtanga_hridaya_samhita/mula/data.json", "ashtanga_hridaya_mula", "अष्टाङ्गहृदयसंहिता"),
    ("Sarvāṅgasundarā", "dge/data/upaveda/ayurveda/samhita/ashtanga_hridaya_samhita/tika_sarvangasundara/data.json", "ashtanga_hridaya_sarvangasundara", "अष्टाङ्गहृदयसंहिता (सर्वाङ्गसुन्दरा — अरुणदत्तः)"),
    ("Padārthacandrikā", "dge/data/upaveda/ayurveda/samhita/ashtanga_hridaya_samhita/tika_padarthacandrika/data.json", "ashtanga_hridaya_padarthacandrika", "अष्टाङ्गहृदयसंहिता (पदार्थचन्द्रिका)"),
    ("Indu (ad AHS)", "dge/data/upaveda/ayurveda/samhita/ashtanga_hridaya_samhita/tika_indu/data.json", "ashtanga_hridaya_indu", "अष्टाङ्गहृदयसंहिता (इन्दुटीका)"),
    ("Aṣṭāṅgasaṃgraha", "dge/data/upaveda/ayurveda/samhita/ashtanga_sangraha/mula/data.json", "ashtanga_sangraha_mula", "अष्टाङ्गसङ्ग्रहः"),
    ("Bhāvaprakāśa", "dge/data/upaveda/ayurveda/samhita/bhavaprakasha/mula/data.json", "bhavaprakasha_mula", "भावप्रकाशः"),
    ("Nāḍīparīkṣā", "dge/data/upaveda/ayurveda/samhita/nadi_pariksha/mula/data.json", "nadi_pariksha_mula", "नाडीपरीक्षा"),

    ("Aṣṭāṅganighaṇṭu", "dge/data/upaveda/ayurveda/nighantu/ashtanga_nighantu/mula/data.json", "ashtanga_nighantu", "अष्टाङ्गनिघण्टुः"),
    ("Bījanighaṇṭu", "dge/data/upaveda/ayurveda/nighantu/bija_nighantu/mula/data.json", "bija_nighantu", "बीजनिघण्टुः"),
    ("Dhanvantarinighaṇṭu", "dge/data/upaveda/ayurveda/nighantu/dhanvantari_nighantu/mula/data.json", "dhanvantari_nighantu", "धन्वन्तरिनिघण्टुः"),
    ("Kaiyadevanighaṇṭu", "dge/data/upaveda/ayurveda/nighantu/kaiyadeva_nighantu/mula/data.json", "kaiyadeva_nighantu", "कैयदेवनिघण्टुः"),
    ("Madanapālanighaṇṭu", "dge/data/upaveda/ayurveda/nighantu/madanapala_nighantu/mula/data.json", "madanapala_nighantu", "मदनपालनिघण्टुः"),
    ("Rājanighaṇṭu", "dge/data/upaveda/ayurveda/nighantu/raja_nighantu/mula/data.json", "raja_nighantu", "राजनिघण्टुः"),
    ("Nighaṇṭuśeṣa", "dge/data/upaveda/ayurveda/nighantu/nighantushesha/mula/data.json", "nighantushesha", "निघण्टुशेषः"),

    ("Rasahṛdayatantra", "dge/data/upaveda/ayurveda/rasashastra/rasahridaya_tantra/mula/data.json", "rasahridaya_tantra", "रसहृदयतन्त्रम्"),
    ("Rasakāmadhenu", "dge/data/upaveda/ayurveda/rasashastra/rasakamadhenu/mula/data.json", "rasakamadhenu", "रसकामधेनुः"),
    ("Rasamañjarī", "dge/data/upaveda/ayurveda/rasashastra/rasamanjari/mula/data.json", "rasamanjari", "रसमञ्जरी"),
    ("Rasaprakāśasudhākara", "dge/data/upaveda/ayurveda/rasashastra/rasaprakashasudhakara/mula/data.json", "rasaprakashasudhakara", "रसप्रकाशसुधाकरः"),
    ("Rasaratnasamuccaya", "dge/data/upaveda/ayurveda/rasashastra/rasaratnasamuccaya/mula/data.json", "rasaratnasamuccaya_mula", "रसरत्नसमुच्चयः"),
    ("Rasaratnasamuccayabodhinī", "dge/data/upaveda/ayurveda/rasashastra/rasaratnasamuccaya/tika_bodhini/data.json", "rasaratnasamuccaya_bodhini", "रसरत्नसमुच्चयः (बोधिनी)"),
    ("Rasaratnasamuccayadīpikā", "dge/data/upaveda/ayurveda/rasashastra/rasaratnasamuccaya/tika_dipika/data.json", "rasaratnasamuccaya_dipika", "रसरत्नसमुच्चयः (दीपिका)"),
    ("Rasaratnasamuccayaṭīkā", "dge/data/upaveda/ayurveda/rasashastra/rasaratnasamuccaya/tika/data.json", "rasaratnasamuccaya_tika", "रसरत्नसमुच्चयः (टीका)"),
    ("Rasaratnākara", "dge/data/upaveda/ayurveda/rasashastra/rasaratnakara/mula/data.json", "rasaratnakara", "रसरत्नाकरः"),
    ("Rasasaṃketakalikā", "dge/data/upaveda/ayurveda/rasashastra/rasasanketakalika/mula/data.json", "rasasanketakalika", "रससङ्केतकलिका"),
    ("Rasataraṅgiṇī", "dge/data/upaveda/ayurveda/rasashastra/rasatarangini/mula/data.json", "rasatarangini", "रसतरङ्गिणी"),
    ("Rasendracintāmaṇi", "dge/data/upaveda/ayurveda/rasashastra/rasendracintamani/mula/data.json", "rasendracintamani", "रसेन्द्रचिन्तामणिः"),
    ("Rasendracūḍāmaṇi", "dge/data/upaveda/ayurveda/rasashastra/rasendracudamani/mula/data.json", "rasendracudamani", "रसेन्द्रचूडामणिः"),
    ("Rasendrasārasaṃgraha", "dge/data/upaveda/ayurveda/rasashastra/rasendrasarasangraha/mula/data.json", "rasendrasarasangraha", "रसेन्द्रसारसङ्ग्रहः"),
    ("Rasārṇava", "dge/data/upaveda/ayurveda/rasashastra/rasarnava/mula/data.json", "rasarnava", "रसार्णवः"),
    ("Rasārṇavakalpa", "dge/data/upaveda/ayurveda/rasashastra/rasarnavakalpa/mula/data.json", "rasarnavakalpa", "रसार्णवकल्पः"),
    ("Rasādhyāya", "dge/data/upaveda/ayurveda/rasashastra/rasadhyaya/mula/data.json", "rasadhyaya_mula", "रसाध्यायः"),
    ("Rasādhyāyaṭīkā", "dge/data/upaveda/ayurveda/rasashastra/rasadhyaya/tika/data.json", "rasadhyaya_tika", "रसाध्यायः (टीका)"),

    ("Dhanurveda", "dge/data/upaveda/dhanurveda/mula/data.json", "dhanurveda_mula", "धनुर्वेदः"),

    ("Nāṭyaśāstra", "dge/data/shastra/natya_shastra/mula/data.json", "natya_shastra_mula", "नाट्यशास्त्रम्"),
    ("Nāṭyaśāstravivṛti", "dge/data/shastra/natya_shastra/tika/data.json", "natya_shastra_tika", "नाट्यशास्त्रम् (विवृतिः)"),
    ("Kāmasūtra", "dge/data/shastra/kama_shastra/mula/data.json", "kama_sutra_mula", "कामसूत्रम्"),
    ("Arthaśāstra", "dge/data/shastra/niti_shastra/artha_shastra/mula/data.json", "artha_shastra_mula", "अर्थशास्त्रम्"),
    ("Hitopadeśa", "dge/data/shastra/niti_shastra/hitopadesha/mula/data.json", "hitopadesha_mula", "हितोपदेशः"),

    ("Saddharmapuṇḍarīkasūtra", "dge/data/shastra/bauddha_sahitya/sutra/saddharma_pundarika_sutra/mula/data.json", "saddharma_pundarika_sutra", "सद्धर्मपुण्डरीकसूत्रम्"),
    ("Laṅkāvatārasūtra", "dge/data/shastra/bauddha_sahitya/sutra/lankavatara_sutra/mula/data.json", "lankavatara_sutra", "लङ्कावतारसूत्रम्"),
    ("Abhidharmakośa", "dge/data/shastra/bauddha_sahitya/shastra/abhidharma_kosha/mula/data.json", "abhidharma_kosha_mula", "अभिधर्मकोशः"),
    ("Abhidharmakośabhāṣya", "dge/data/shastra/bauddha_sahitya/shastra/abhidharma_kosha/bhashya/data.json", "abhidharma_kosha_bhashya", "अभिधर्मकोशः (भाष्यम्)"),
    ("Mūlamadhyamakārikāḥ", "dge/data/shastra/bauddha_sahitya/shastra/mula_madhyamaka_karika/mula/data.json", "mula_madhyamaka_karika", "मूलमध्यमककारिकाः"),
    ("Prasannapadā", "dge/data/shastra/bauddha_sahitya/shastra/mula_madhyamaka_karika/tika_prasannapada/data.json", "prasannapada", "मूलमध्यमककारिकाः (प्रसन्नपदा)"),
    ("Viṃśatikākārikā", "dge/data/shastra/bauddha_sahitya/shastra/vimshatika/mula/data.json", "vimshatika_karika", "विंशतिका"),
    ("Viṃśatikāvṛtti", "dge/data/shastra/bauddha_sahitya/shastra/vimshatika/vritti/data.json", "vimshatika_vritti", "विंशतिका (वृत्तिः)"),
    ("Bodhicaryāvatāra", "dge/data/shastra/bauddha_sahitya/shastra/bodhicaryavatara/mula/data.json", "bodhicaryavatara", "बोधिचर्यावतारः"),
    ("Śikṣāsamuccaya", "dge/data/shastra/bauddha_sahitya/shastra/shikshasamuccaya/mula/data.json", "shikshasamuccaya", "शिक्षासमुच्चयः"),
    ("Aṣṭasāhasrikā", "dge/data/shastra/bauddha_sahitya/shastra/ashtasahasrika_prajnaparamita/mula/data.json", "ashtasahasrika", "अष्टसाहस्रिका प्रज्ञापारमिता"),
    ("Nyāyabindu", "dge/data/shastra/bauddha_sahitya/pramana/nyayabindu/mula/data.json", "nyayabindu", "न्यायबिन्दुः"),
    ("Avadānaśataka", "dge/data/shastra/bauddha_sahitya/avadana/avadanashataka/mula/data.json", "avadanashataka", "अवदानशतकम्"),
    ("Divyāvadāna", "dge/data/shastra/bauddha_sahitya/avadana/divyavadana/mula/data.json", "divyavadana", "दिव्यावदानम्"),
    ("Saṅghabhedavastu", "dge/data/shastra/bauddha_sahitya/avadana/sanghabhedavastu/mula/data.json", "sanghabhedavastu", "सङ्घभेदवस्तु"),
]


def merge_taxonomy():
    path = os.path.join(REPO, "dge/data/taxonomy.json")
    with open(path, encoding="utf-8") as f:
        d = json.load(f, object_pairs_hook=collections.OrderedDict)
    for key, subtree in TAXONOMY_ADDITIONS.items():
        assert key not in d, f"taxonomy.json already has top-level key {key!r}"
        d[key] = subtree
    with open(path, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"taxonomy.json: added top-level keys {list(TAXONOMY_ADDITIONS.keys())}")


def add_library_entries(populated_paths):
    path = os.path.join(REPO, "dge/data/library.json")
    with open(path, encoding="utf-8") as f:
        d = json.load(f, object_pairs_hook=collections.OrderedDict)
    existing = {g["path"] for g in d["granthas"]}
    added = 0
    for _, rel_out, _, title in ENTRIES:
        assert rel_out not in existing, rel_out
        d["granthas"].append(collections.OrderedDict([
            ("path", rel_out),
            ("populated", rel_out in populated_paths),
            ("title", title),
        ]))
        added += 1
    with open(path, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"library.json: added {added} entries ({len(populated_paths)} populated)")


def run_imports():
    populated_paths = set()
    for dcs_name, rel_out, slug, _ in ENTRIES:
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
                "entry (batch 5, Tier B Upaveda/Shastra), for how the new "
                "upaveda/shastra taxonomy branches were drafted and matched."
            ),
            tag="dcs-import",
        )
        populated_paths.add(rel_out)
        print(f"{dcs_name}: {n} files -> {count} items -> {rel_out}")
    return populated_paths


def main():
    merge_taxonomy()
    populated_paths = run_imports()
    add_library_entries(populated_paths)
    print(f"\n{len(populated_paths)}/{len(ENTRIES)} leaves populated from DCS")


if __name__ == "__main__":
    main()
