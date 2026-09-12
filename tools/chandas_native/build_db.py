# -*- coding: utf-8 -*-
"""
Independent, from-scratch compilation of a classical (laukika) Sanskrit
vrutta database, built directly from the standard gana system -- NOT
transcribed or adapted from hrishikeshrt/chanda or any other software
project's data files.

Every fact used here (the eight three-syllable ganas and the individual
metre formulas) is centuries old, appears in substance in every Sanskrit
prosody primer (the Pingala/Vrittaratnakara/Chandomanjari tradition), and
is firmly public domain -- this file is a clean-room re-derivation from
that shared traditional knowledge, not a copy of anyone's specific
compilation or code.

SCOPE, STATED HONESTLY: still a deliberately smaller core than the
282-entry hrishikeshrt/chanda catalogue, not padded to match it. As of
21 Aug this covers 21 sama-vrutta and 3 ardhasama-vrutta, each checked
either against a real verse, by internal gana/matra arithmetic, or (for
the upajati proper names) against an independent source's raw prosodic
symbols -- see PENDING.md for the full verification trail, including one
place where two outside sources flatly disagreed and had to be resolved
by hand rather than picked on authority. Vishama-vrutta, the
Vaitaliya/Aupacchandasika family (their rules go beyond a simple
matra-per-pada count), and akshara-jaati names above 20 (three
independently-found sources disagreed on these) are still not included.
"""
import json

GANA = {
    "य": "LGG",  # ya-gana
    "म": "GGG",  # ma-gana
    "त": "GGL",  # ta-gana
    "र": "GLG",  # ra-gana
    "ज": "LGL",  # ja-gana
    "भ": "GLL",  # bha-gana
    "न": "LLL",  # na-gana
    "स": "LLG",  # sa-gana
}
SINGLE = {"ल": "L", "ग": "G"}


def expand(units):
    """units: string of gana letters (य म त र ज भ न स) and/or single
    laghu/guru letters (ल ग). Returns the full L/G pattern."""
    out = ""
    for u in units:
        if u in GANA:
            out += GANA[u]
        elif u in SINGLE:
            out += SINGLE[u]
        else:
            raise ValueError(f"unknown unit {u!r}")
    return out


def to_dev(pattern):
    return "".join("ग" if c == "G" else "ल" for c in pattern)


def matra(pattern):
    return sum(2 if c == "G" else 1 for c in pattern)


SAMA_VRUTTA = []


def sama(names, units):
    # No yati (caesura) field: the AGPL vendor data uses a segment-length
    # convention that doesn't match plain recall well enough to reproduce
    # independently and confidently -- omitted rather than guessed.
    pat = expand(units)
    SAMA_VRUTTA.append({
        "vrutta_names": names,
        "gana": units,
        "lakshana": to_dev(pat),
        "akshara_sankhya": len(pat),
        "matra": matra(pat),
        "examples": [],
    })


# 11 syllables -- Indravajra/Upendravajra family (base for upajati below)
sama(["इन्द्रवज्रा"], "ततजगग")
sama(["उपेन्द्रवज्रा"], "जतजगग")
sama(["शालिनी"], "मततगग")  # ma-ta-ta-ga-ga; arithmetic independently re-verified,
# specific Chandomanjari verse/edition citation not independently confirmed -- see PENDING.md, 21 Aug entry
sama(["रथोद्धता"], "रनरलग")
sama(["स्वागता"], "रनभगग")

# 12 syllables
sama(["वंशस्थ"], "जतजर")
sama(["इन्द्रवंशा"], "ततजर")
sama(["द्रुतविलम्बित"], "नभभर")
sama(["तोटक"], "सससस")
sama(["भुजङ्गप्रयात"], "यययय")
sama(["स्रग्विणी"], "रररर")

# 13 syllables
sama(["प्रहर्षिणी"], "मनजरग")
sama(["रुचिरा"], "जभसजग")

# 14 syllables
sama(["वसन्ततिलका"], "तभजजगग")

# 15 syllables
sama(["मालिनी"], "ननमयय")

# 17 syllables
sama(["मन्दाक्रान्ता"], "मभनततगग")
sama(["शिखरिणी"], "यमनसभलग")
sama(["पृथ्वी"], "जसजसयलग")
sama(["हरिणी"], "नसमरसलग")

# 19 syllables
sama(["शार्दूलविक्रीडित"], "मसजसततग")

# 21 syllables
sama(["स्रग्धरा"], "मरभनययय")


# --- Ardhasama-vrutta: odd and even padas differ. New category, not
# present in the first pass. Same discipline as sama(): gana formula in,
# lakshana/counts derived mechanically, not hand-copied from anywhere.
ARDHASAMA_VRUTTA = []


def ardhasama(names, odd_units, even_units):
    odd_pat = expand(odd_units)
    even_pat = expand(even_units)
    ARDHASAMA_VRUTTA.append({
        "vrutta_names": names,
        "odd_pada": {
            "gana": odd_units, "lakshana": to_dev(odd_pat),
            "akshara_sankhya": len(odd_pat), "matra": matra(odd_pat),
        },
        "even_pada": {
            "gana": even_units, "lakshana": to_dev(even_pat),
            "akshara_sankhya": len(even_pat), "matra": matra(even_pat),
        },
    })


ardhasama(["पुष्पिताग्रा"], "नन" + "रय", "नभजरग")
ardhasama(["वियोगिनी", "सुन्दरी"], "ससजग", "सभरलग")
ardhasama(["अपरवक्त्र"], "ननरलग", "नजजर")

# --- Upajati: mechanical combination of Indravajra-type (I) and
# Upendravajra-type (U) padas across the 4 lines of a verse. Lakshana is
# correct by construction (concatenated known ganas); the pada_pattern
# string (e.g. "U-I-I-I") is therefore certain regardless of naming.
#
# The traditional Sanskrit proper name for each of the 14 mixed
# combinations is a separate question from the pattern, and this is where
# two independently-checked sources genuinely disagreed (see PENDING.md,
# 21 Aug entry, for the full account): a name/pattern table supplied
# externally gave e.g. Kirti = I-U-U-U, while
# https://ancient-buddhist-texts.net/Textual-Studies/Metre-Tables/Tables-14.htm
# (explicitly citing Vrittaratnakara) gives Kirti = U-I-I-I -- the exact
# complement. Rather than pick one on authority, 4 of the 14 names below
# (Kirti, Vani, Ardra, Buddhi) were checked by decoding that page's raw
# laghu/guru symbols by hand against this file's own gana table -- both
# padas of each matched Indravajra/Upendravajra exactly, unambiguously.
# The other 10 names are taken from the same page on the strength of that
# 4/14 agreement, not independently symbol-checked one by one -- treat
# those 10 as good-confidence, not certain.
NAMED_UPAJATI = {
    (1, 0, 0, 0): "कीर्ति",   # symbol-verified
    (0, 1, 0, 0): "वाणी",     # symbol-verified
    (1, 1, 0, 0): "माला",
    (0, 0, 1, 0): "शाला",
    (1, 0, 1, 0): "हंसी",
    (0, 1, 1, 0): "माया",
    (1, 1, 1, 0): "छाया",
    (0, 0, 0, 1): "बाला",
    (1, 0, 0, 1): "आर्द्रा",  # symbol-verified
    (0, 1, 0, 1): "भद्रा",
    (1, 1, 0, 1): "प्रेमा",
    (0, 0, 1, 1): "रामा",
    (1, 0, 1, 1): "ऋद्धि",
    (0, 1, 1, 1): "बुद्धि",   # symbol-verified
}

INDRAVAJRA_PADA = expand("ततजगग")
UPENDRAVAJRA_PADA = expand("जतजगग")

UPAJATI_VRUTTA = []
for bits in range(16):  # 4 padas, each either Indravajra(0)/Upendravajra(1)
    key = tuple((bits >> i) & 1 for i in range(4))
    pattern_letters = []
    padas = []
    for i in range(4):
        is_upendra = key[i]
        letter = "U" if is_upendra else "I"
        pat = UPENDRAVAJRA_PADA if is_upendra else INDRAVAJRA_PADA
        pattern_letters.append(letter)
        padas.append({
            "pada": i + 1,
            "lakshana": to_dev(pat),
            "akshara_sankhya": len(pat),
            "matra": matra(pat),
        })
    label = "-".join(pattern_letters)
    if bits == 0:
        name = "इन्द्रवज्रा (शुद्ध)"
    elif bits == 15:
        name = "उपेन्द्रवज्रा (शुद्ध)"
    else:
        name = NAMED_UPAJATI[key]
    UPAJATI_VRUTTA.append({"vrutta_names": [name], "pada_pattern": label, "padas": padas})


# --- Anustubh: NOT a fixed lakshana -- a rule-governed jati. The common
# ("pathya") form: 4 padas of 8 syllables each; in the even padas (2nd and
# 4th), syllables 5-8 must scan laghu-guru-laghu-guru; odd padas are
# comparatively free (traditionally syllable 5 laghu, 6-7 not both laghu).
# This matches the Gita-verse test in scan.py exactly (see verify.py).
ANUSHTUBH_RULE = {
    "vrutta_names": ["अनुष्टुभ्", "श्लोक"],
    "type": "jati_rule",
    "pada_count": 4,
    "akshara_per_pada": 8,
    "rule": (
        "pathya form: positions 5-8 of padas 2 and 4 scan ल-ग-ल-ग; "
        "position 5 of every pada is laghu; positions 6-7 are not both laghu"
    ),
    "examples": [],
}


# --- Arya-family matra-vrutta. Only entries I'm confident of; "आर्या"
# below is independently cross-checked: it matches the matra_per_pada
# already recorded in the AGPL vendor's own data.json ([12,18,12,15]),
# which is reassuring but was not looked up there -- recalled independently
# from the standard textbook definition before comparing.
MATRA_VRUTTA = [
    {"vrutta_names": ["आर्या"], "matra_per_pada": [12, 18, 12, 15]},
    {"vrutta_names": ["गीति"], "matra_per_pada": [12, 18, 12, 18]},
    {"vrutta_names": ["उपगीति"], "matra_per_pada": [12, 15, 12, 15]},
    {"vrutta_names": ["उद्गीति"], "matra_per_pada": [12, 15, 12, 18]},
]
# Vaitaliya and Aupacchandasika deliberately NOT added here: they involve
# structural rules on the terminal ganas of each pada, not just a total
# matra count per pada, so a [matra_per_pada] entry would misrepresent
# them as simpler than they are. Needs a dedicated schema field
# (terminal_pattern / special_rules), not attempted this pass.


# --- Akshara-count jaati names, 1-20 syllables. Sequence per pada length,
# confident through 20; 21-26 omitted (memory not reliable enough there).
AKSHARA_JAATI_NAMES = [
    "उक्ता", "अत्युक्ता", "मध्या", "प्रतिष्ठा", "सुप्रतिष्ठा", "गायत्री",
    "उष्णिक्", "अनुष्टुभ्", "बृहती", "पङ्क्ति", "त्रिष्टुभ्", "जगती",
    "अतिजगती", "शक्वरी", "अतिशक्वरी", "अष्टि", "अत्यष्टि", "धृति",
    "अतिधृति", "कृति",
]
AKSHARA_JAATI = [
    {"akshara_sankhya": i + 1, "jaati": name}
    for i, name in enumerate(AKSHARA_JAATI_NAMES)
]

if __name__ == "__main__":
    print(f"sama-vrutta: {len(SAMA_VRUTTA)}, ardhasama-vrutta: {len(ARDHASAMA_VRUTTA)}, "
          f"upajati: {len(UPAJATI_VRUTTA)}, matra-vrutta: {len(MATRA_VRUTTA)}, "
          f"akshara-jaati: {len(AKSHARA_JAATI)}")
    db = {
        "schema": "vedanga_chandas_vrutta_database",
        "source": "independently compiled from the standard classical gana "
                   "system (Pingala/Vrittaratnakara/Chandomanjari tradition, "
                   "public domain); not derived from hrishikeshrt/chanda or "
                   "any other software project's data. Upajati proper names "
                   "sourced from https://ancient-buddhist-texts.net/Textual-"
                   "Studies/Metre-Tables/Tables-14.htm (citing Vrittaratnakara), "
                   "4 of 14 individually verified against its raw laghu/guru "
                   "symbols -- see PENDING.md, 21 Aug entry.",
        "licence": "Apache-2.0 (matches this repo's default -- no AGPL content)",
        "note": (
            "Deliberately smaller core than a full classical-metre catalogue: "
            "21 well-attested sama-vrutta, 3 ardhasama-vrutta, a rule-based "
            "Anustubh handler, mechanically-generated Indravajra/Upendravajra "
            "upajati combinations with sourced traditional names, a small "
            "Arya-family matra-vrutta set (4 entries), and akshara-jaati names "
            "1-20. Vishama vrutta, Vaitaliya/Aupacchandasika (need a richer "
            "schema than total matra count), and akshara-jaati 21-26 (three "
            "independently-found sources disagreed, none adopted) are NOT "
            "included -- see README and PENDING.md for why."
        ),
        "counts": {
            "sama_vrutta": len(SAMA_VRUTTA),
            "ardhasama_vrutta": len(ARDHASAMA_VRUTTA),
            "upajati_vrutta": len(UPAJATI_VRUTTA),
            "matra_vrutta": len(MATRA_VRUTTA),
            "akshara_jaati": len(AKSHARA_JAATI),
        },
        "sama_vrutta": SAMA_VRUTTA,
        "ardhasama_vrutta": ARDHASAMA_VRUTTA,
        "upajati_vrutta": UPAJATI_VRUTTA,
        "anushtubh": ANUSHTUBH_RULE,
        "matra_vrutta": MATRA_VRUTTA,
        "akshara_jaati": AKSHARA_JAATI,
    }
    out_path = "data.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
    print(f"wrote {out_path}")
