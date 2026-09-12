"""Regression suite for the DGE Chandas engine (dge/js/chandas.js).

The engine is browser JS; tools/kamadhenu/chandas_runner.js loads it unmodified
under node with three stubbed globals, so every assertion here is about the
exact behaviour the site shows. Cases pin the September 2026 gap-closure:
anuṣṭubh pathyā/vipulā classes, the ऋद्धि upajāti row, generic upajāti mixes,
candidate pāda splitting (single-line and two-line ardhasama input), nasal/
Vedic marks as guru, and Kannada-script input. A last group checks that
data.json is self-consistent (gaṇa string ↔ लघु/गुरु lakṣaṇa).
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
RUNNER = ROOT / "tools" / "kamadhenu" / "chandas_runner.js"
DB_PATH = ROOT / "dge" / "data" / "vedanga" / "chandas" / "data.json"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def analyse(*texts):
    r = subprocess.run(["node", str(RUNNER)], input=json.dumps(list(texts), ensure_ascii=False),
                       capture_output=True, text=True, cwd=str(ROOT), check=True)
    return json.loads(r.stdout)


def lg(res):
    return ["".join("G" if c == "ग" else "L" for c in p["pattern"]) for p in res["padas"]]


def names(res):
    return (res.get("match") or {}).get("names") or []


def has_name(res, name):
    # ardhasama rows carry several names in one comma-joined string
    return any(name in n for n in names(res))


# ---------------------------------------------------------------- anuṣṭubh
GITA_1_1 = "धर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः ।\nमामकाः पाण्डवाश्चैव किमकुर्वत सञ्जय ॥"
GITA_1_5 = "धृष्टकेतुश्चेकितानः काशिराजश्च वीर्यवान् ।\nपुरुजित्कुन्तिभोजश्च शैब्यश्च नरपुङ्गवः ॥"


def test_anushtubh_pathya():
    (r,) = analyse(GITA_1_1)
    assert [p["aksharas"] for p in r["padas"]] == [8, 8, 8, 8]
    assert names(r) == ["अनुष्टुप् (श्लोकः) — पथ्या"]
    assert r["match"]["kind"] == "छन्दः"
    assert r["match"]["vipula"] == []
    assert r["match"].get("irregular") is None


def test_anushtubh_ra_vipula_is_named_not_unknown():
    (r,) = analyse(GITA_1_5)
    assert lg(r)[0] == "GLGGGLGG"          # 5-7 = गलग in pāda 1 → र-विपुला
    assert names(r) == ["अनुष्टुप् (श्लोकः) — र-विपुला (पादे 1)"]
    assert r["match"]["vipula"] == ["र-विपुला (पादे 1)"]


def test_anushtubh_speaker_line_is_not_a_pada():
    # Speaker headers are stripped upstream (texts.py); the engine itself must
    # still treat a clean 2-line śloka as 4 pādas of 8.
    (r,) = analyse("धर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः\nमामकाः पाण्डवाश्चैव किमकुर्वत सञ्जय")
    assert len(r["padas"]) == 4


def test_eight_syllable_sama_vrutta_beats_irregular_anushtubh():
    # Chandomañjarī examples (Gemini, 6 Sep 2026): 4×8 that break the śloka rules but fit a sama table row
    (p, c) = analyse("न संशयो ममास्ति यत्\nभवन्त्यमी गुणास्तव\nअचिन्तनीयरूपधृग्\nहरे सदा प्रसीद मे",
                     "वासवदत्तनयेयं\nसा मयि संप्रति रक्ता\nपश्य सखे मम भाग्यं\nयाति दिशं दयिता मे")
    assert [x[:7] for x in lg(p)] == ["LGLGLGL"] * 4 and has_name(p, "प्रमाणिका") and p["match"]["kind"] == "समवृत्तम्"
    assert lg(c) == ["GLLGLLGG"] * 4 and has_name(c, "चित्रपदा")


# ------------------------------------------------------------------ upajāti
SMV_1_4 = ("तमोनुदानन्दमवाप लोकस्तत्वप्रदीपाकृतिगोगणेन ।\n"
           "यदास्यशीतांशुभुवा गुरूंस्तान् त्रिविक्रमार्यान् प्रणमामि वर्यान् ॥")


def test_upajati_rddhi_row_is_u_i_u_u():
    (r,) = analyse(SMV_1_4)
    assert lg(r) == ["LGLGGLLGLGG", "GGLGGLLGLGL", "LGLGGLLGLGG", "LGLGGLLGLGG"]
    assert names(r) == ["उपजाति (ऋद्धि)"]
    assert r["match"]["kind"] == "उपजातिः"


def test_upajati_named_table_gita_11_15():
    (r,) = analyse("पश्यामि देवांस्तव देव देहे सर्वांस्तथा भूतविशेषसङ्घान् ।\n"
                   "ब्रह्माणमीशं कमलासनस्थमृषींश्च सर्वानुरगांश्च दिव्यान् ॥")
    assert names(r) == ["उपजाति (बाला)"]


def test_upajati_vamshastha_indravamsha_mix():
    # वंशस्थ pādas 1,2,4 with an इन्द्रवंशा pāda 3 (pāda-final laghu is anceps).
    v = "कदा नु काले किमपि प्रसीदति"        # वंशस्थ
    i = "यत्रास्ति सर्वं परमं प्रसीदति"      # इन्द्रवंशा (synthetic)
    (r,) = analyse("\n".join([v, v, i, v]))
    assert lg(r) == ["LGLGGLLGLGLL", "LGLGGLLGLGLL", "GGLGGLLGLGLL", "LGLGGLLGLGLL"]
    assert r["match"]["kind"] == "उपजातिः"
    assert names(r)[0].startswith("उपजाति (वंशस्थ-इन्द्रवंशा")


def test_generic_upajati_fallback_for_unnamed_mix():
    # वंशस्थ + उपेन्द्रवज्रा (11/12 mix) has no row in the table → generic label.
    v = "कदा नु काले किमपि प्रसीदति"        # वंशस्थ 12
    u = "कदा नु काले किमपीह याति"          # उपेन्द्रवज्रा-shaped 11 (synthetic)
    (r,) = analyse("\n".join([v, u, v, u]))
    assert r["match"]["kind"] == "उपजातिः"
    assert "मिश्रम्" in names(r)[0]


# ---------------------------------------------------------- sama vṛttas
def test_vasantatilaka_bhagavata_4_9_6():
    (r,) = analyse("योऽन्तः प्रविश्य मम वाचमिमां प्रसुप्तां\nसञ्जीवयत्यखिलशक्तिधरः स्वधाम्ना ।\n"
                   "अन्यांश्च हस्तचरणश्रवणत्वगादीन्\nप्राणान्नमो भगवते पुरुषाय तुभ्यम् ॥")
    assert has_name(r, "वसन्ततिलका")
    assert r["match"]["kind"] == "समवृत्तम्"


def test_malini_four_lines_sumadhva_vijaya_10_44():
    (r,) = analyse("वितततमतमोऽन्तं साधयन्त्या नितान्तं\nसदसिसदसि रेजे व्याख्यया व्यासशिष्यः ।\n"
                   "सकलसमयिहस्ताम्भोजबन्धाभिनन्दी\nशरदिशरदि चन्द्रश्चन्द्रिका सम्पदेव ॥")
    assert lg(r)[:3] == ["LLLLLLGGGLGGLGG"] * 3
    assert lg(r)[3] == "LLLLLLGGGLGGLGL"       # final laghu = anceps
    assert has_name(r, "मालिनी")
    assert r["match"].get("yati") == [8, 7]


def test_mandakranta_two_line_input_sumadhva_vijaya_1_55():
    (r,) = analyse("विश्वं मिथ्या विभुरगुणवानात्मनां नास्ति भेदो दैत्या इत्थं व्यदधत गिरां दिक्षु भूयः प्रसिद्धिम् ।\n"
                   "आनन्दाद्यैर्गुरुगुणगणैः पूरितो वासुदेवो मन्दम्मन्दं मनसि च सतां हन्त नूनं तिरोऽभूत् ॥")
    assert [p["aksharas"] for p in r["padas"]] == [17, 17, 17, 17]
    assert has_name(r, "मन्दाक्रान्ता")


def test_shikharini_shakuntala():
    (r,) = analyse("अनाघ्रातं पुष्पं किसलयमलूनं कररुहै-\nरनाविद्धं रत्नं मधु नवमनास्वादितरसम् ।\n"
                   "अखण्डं पुण्यानां फलमिव च तद्रूपमनघं\nन जाने भोक्तारं कमिह समुपस्थास्यति विधिः ॥")
    assert has_name(r, "शिखरिणी")


def test_shardulavikridita_bhartrhari():
    (r,) = analyse("भोगे रोगभयं कुले च्युतिभयं वित्ते नृपालाद्भयं\nमाने दैन्यभयं बले रिपुभयं रूपे जराया भयम् ।\n"
                   "शास्त्रे वादिभयं गुणे खलभयं काये कृतान्ताद्भयं\nसर्वं वस्तु भयान्वितं भुवि नृणां वैराग्यमेवाभयम् ॥")
    assert has_name(r, "शार्दूलविक्रीडित")


# ------------------------------------------------ pāda assembly (ardhasama)
SMV_7_10_ONE_LINE = "अवलोकितलक्षणः स तैरिति सञ्चिन्त्य कुतूहलाकुलैः अविलम्बगतिर्व्यशामयत् तरुमारात् सुरपादपोत्तमम्"


def test_single_line_ardhasama_is_split_into_four_padas():
    (r,) = analyse(SMV_7_10_ONE_LINE)
    assert [p["aksharas"] for p in r["padas"]] == [10, 11, 10, 11]
    assert r["match"]["kind"] == "अर्धसमवृत्तम्"
    assert has_name(r, "वियोगिनी")


def test_two_line_ardhasama_pushpitagra_style_input():
    # Same verse given as two hemistichs (the common data layout).
    (r,) = analyse("अवलोकितलक्षणः स तैरिति सञ्चिन्त्य कुतूहलाकुलैः\nअविलम्बगतिर्व्यशामयत् तरुमारात् सुरपादपोत्तमम्")
    assert [p["aksharas"] for p in r["padas"]] == [10, 11, 10, 11]
    assert has_name(r, "वियोगिनी")


# ---------------------------------------------------------- script / marks
def to_kannada(s):
    return "".join(chr(ord(c) + 0x380) if 0x0900 <= ord(c) <= 0x097F and c not in "।॥" else c for c in s)


def test_kannada_input_is_folded_to_devanagari():
    (dev, knd) = analyse(GITA_1_1, to_kannada(GITA_1_1))
    assert lg(knd) == lg(dev)
    assert names(knd) == names(dev)


def test_candrabindu_and_jihvamuliya_are_guru():
    (a, b, c) = analyse("कँ", "कᳵ", "क")
    assert a["padas"][0]["pattern"] == "ग"
    assert b["padas"][0]["pattern"] == "ग"
    assert c["padas"][0]["pattern"] == "ल"


def test_ardhavisarga_variants_are_guru():
    (a, b, c) = analyse("कᳲ", "कᳳ", "कᳶ")
    assert [x["padas"][0]["pattern"] for x in (a, b, c)] == ["ग", "ग", "ग"]


def test_vocalic_ll_long_sign_is_guru():
    (r,) = analyse("कॣ")
    assert r["padas"][0]["pattern"] == "ग"


# ----------------------------------------------------- data.json integrity
GANA = {"य": "लगग", "म": "गगग", "त": "गगल", "र": "गलग", "ज": "लगल", "भ": "गलल", "न": "ललल", "स": "ललग",
        "ल": "ल", "ग": "ग", "-": "-"}   # '-' = free position (anuṣṭubh ardhasama row)


def expand(gana):
    return "".join(GANA[c] for c in gana)


@pytest.fixture(scope="module")
def db():
    return json.loads(DB_PATH.read_text(encoding="utf-8"))


def test_db_counts_match(db):
    assert db["counts"]["sama_vrutta"] == len(db["sama_vrutta"]) == 190
    assert db["counts"]["ardhasama_vrutta"] == len(db["ardhasama_vrutta"]) == 8
    assert db["counts"]["vishama_vrutta"] == len(db["vishama_vrutta"]) == 5
    assert db["counts"]["upajati_vrutta"] == len(db["upajati_vrutta"]) == 42


def test_sama_gana_matches_lakshana(db):
    bad = [v["vrutta_names"][0] for v in db["sama_vrutta"]
           if expand(v["gana"]) != v["lakshana"] or len(v["lakshana"]) != v["akshara_sankhya"]]
    assert bad == []


def test_multi_pada_gana_matches_lakshana(db):
    bad = []
    for key in ("ardhasama_vrutta", "vishama_vrutta", "upajati_vrutta"):
        for v in db[key]:
            for p in v["padas"]:
                if expand(p["lakshana"]) != p["lakshana_raw"] or len(p["lakshana_raw"]) != p["akshara_sankhya"]:
                    bad.append((v["vrutta_names"][0], p["pada"]))
    assert bad == []


def test_upajati_rows_are_distinct_and_rddhi_is_u_i_u_u(db):
    I, U = "गगलगगललगलगग", "लगलगगललगलगग"
    rows = {v["vrutta_names"][0]: "".join("I" if p["lakshana_raw"] == I else "U" if p["lakshana_raw"] == U else "?"
                                          for p in v["padas"]) for v in db["upajati_vrutta"]}
    iu = {k: v for k, v in rows.items() if set(v) <= {"I", "U"}}
    assert iu["उपजाति (ऋद्धि)"] == "UIUU"
    assert len(set(iu.values())) == len(iu), "duplicate indra/upendra mixes"
    assert len(iu) == 14 and set(iu.values()) == {a + b + c + d for a in "IU" for b in "IU" for c in "IU" for d in "IU"} - {"IIII", "UUUU"}
