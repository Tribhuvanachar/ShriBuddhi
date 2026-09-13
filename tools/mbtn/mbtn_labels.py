"""Canonical MBTN commentary matcher — maps an OCR'd "Name-" label token to a
canonical commentary, tolerant of the edition's heavy Devanagari OCR variance
(ब↔व, द्↔ट्↔द्र↔ट्र, ग्र↔म्र, dropped halants). Ordered most-specific first;
returns (key, label) or None (mula verse / section header / noise)."""
import re

# canonical key -> (display label, [signature substrings that survive OCR])
# order matters: earlier rules win.
COMMENTARIES = [
    ("vadiraja",      "वादिराजतीर्थीया (श्रीवादिराजतीर्थ)",   ["दिराज"]),
    ("varadaraja",    "वरदराजीया (श्रीवरदराजाचार्य)",         ["रदराज", "रद्राज"]),
    ("janardana",     "जनार्दनीया (श्रीजनार्दनभट्ट)",         ["नार्दन", "जनार्द"]),
    ("vyasatirtha",   "व्यासतीर्थीया — भावपञ्चिका (श्रीव्यासतीर्थ)", ["यासतीर्थ", "ासतीर्थीय"]),
    ("anantabhatta",  "अनन्तभट्टीया (श्रीअनन्तभट्ट)",          ["अनन्तभ", "अनन्तम"]),
    ("madhusudana",   "मधुसूदनीया (श्रीमधुसूदन)",             ["ुसूदन", "ुसुदन"]),
    ("tamraparni",    "ताम्रपर्णीया",                          ["्रपर्ण", "पर्णीय", "पर्णया", "ग्रपण", "म्रपण", "पणीय", "प्णीय"]),
    ("satyabhinava",  "सत्याभिनवतीर्थीया — दुर्घटार्थप्रकाशिका", ["त्याभिन"]),
    ("satyadharma",   "सत्यधर्मीया",                           ["त्यधर्म"]),
    ("kanthakoddhara","कण्ठकोद्धारः",                          ["ण्ठकोद्ध", "कण्ठको"]),
    ("bhavachandrika","भावचन्द्रिका",                          ["भावचन्द"]),
    ("bhavavivrti",   "भावविवृतिः",                            ["भावविवृ"]),
    ("bharatshri",    "भारतश्री",                              ["भारतश्री", "भारतश्रि"]),
    ("sangraha",      "टीकासङ्ग्रहः",                           None),   # vol1 abbrev only
    ("vedangatirtha", "वेदाङ्गतीर्थीया",                       None),   # special: वेदा…तीर्थ
    ("chatti",        "चट्टी / जम्बुखण्डी (श्रीलक्ष्मीनृसिंहाचार्य)", None),   # special: short च-cluster
]

# Vol-1 uses SHORT abbreviations + "--" boundaries (जना/वरद/व्यास/वादि/ताप्र/
# जम्बु/अभिनव), where vols 2-4 spell the names in full. Exact-token map for
# those. जम्बुखण्डी is Śrī Lakṣmīnṛsiṃhācārya's ṭīkā-saṅgraha — the same
# author as चट्टी in vols 2-4 — so both fold into one `chatti` layer.
ABBREV = {
    "जना": "janardana", "वरद": "varadaraja", "व्यास": "vyasatirtha",
    "वादि": "vadiraja", "अभिनव": "satyabhinava", "भार": "bharatshri",
    "ताप्र": "tamraparni", "ताग्र": "tamraparni", "ताम्र": "tamraparni", "ताभ्र": "tamraparni",
    "जम्बु": "chatti",
    "सङ्क": "sangraha", "सद्क": "sangraha", "सद्भ": "sangraha", "सद्ध": "sangraha", "सङ्ग्र": "sangraha",
}
# short tokens that are prose words, never a commentary label
NOT_LABELS = {"आह", "राम", "इति", "अत", "तत", "अथ", "सर्व"}

# section / apparatus headers that are NOT commentaries — never a layer
SECTION_MARKERS = ["गूढ", "प्रमाण", "अतिवि", "विषयानुक्रमणिका",
                   "अनुक्रमणिका", "श्लोकसंख्या"]


def canon(tok):
    """Return the canonical commentary key for an OCR'd label token, or None."""
    t = tok.strip()
    if not t or len(t) > 22 or t in NOT_LABELS:
        return None
    for mk in SECTION_MARKERS:
        if mk in t:
            return None
    if t in ABBREV:            # vol-1 short abbreviations (exact)
        return ABBREV[t]
    for key, _label, sigs in COMMENTARIES:
        if sigs is None:
            continue
        if any(s in t for s in sigs):
            return key
    # वेदाङ्गतीर्थीया — OCR mangles the middle badly (वेदाद्ग/वेदाद्भ/वेदाङ्भ/
    # वेदाङ्क…), so match on the stable ends: starts वे/बे + दा … तीर्थ.
    if re.match(r'^[वब]ेदा', t) and 'तीर्थ' in t:
        return "vedangatirtha"
    # चट्टी: a short token starting च + (द/ट/ष/ध…) — the Chaṭṭī gloss, whose
    # name the OCR mangles the most (चद्टी/चद्री/चट्री/चष्टि/चदि/चटी/चटरी…).
    if re.match(r'^च[्दटषध]', t) and len(t) <= 6:
        return "chatti"
    return None


LABEL_OF = {k: lbl for k, lbl, _ in COMMENTARIES}
