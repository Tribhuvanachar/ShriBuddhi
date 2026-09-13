#!/usr/bin/env python3
"""Generate Krama-patha for RV 1.1 (all 9 verses) -- a real, checkable
first output of the rule logic in krama_kramahetu_rules.json, not just
rule data.

WHAT THIS IS: a hand-aligned application of patala 10's rules to RV 1.1,
using DGE's own attested samhita-patha as ground truth for each word-pair's
sandhi (rather than an independent sandhi engine this project does not
have), with Parigraha/ardharca-final insertions applied per the rules this
session built. This is NOT validated against a published Krama-patha
edition -- see KRAMA_VERIFICATION_PACKET.md for exactly what still needs an
independent check (by Gemini, ChatGPT, a human Sanskritist, or a fresh
Claude session) and why.

WHY HAND-ALIGNED RATHER THAN CODE-COMPUTED SANDHI: this project has no
validated Sanskrit sandhi engine (dge/veda_toolkit's own notes flag deriving
one as a real, unsolved problem -- see dge/VEDAWEB_IMPORT_STATUS.md sec.5).
Each adjacent pair's sandhi is a substring of DGE's own already-correct,
accented samhita_patha for that verse (sandhi is a strictly local, adjacent-
word phenomenon, so this is exact, not approximate) -- verified by hand
against dge/data/vedas/rigveda/shakala_shakha/samhita/mandala_01/data.json's
items 1.1.1-1.1.9 during this session.

Two things are NOT simply "read off" the samhita text, and are handled by
explicit per-word data below rather than derived automatically (an earlier
version of this script tried to auto-derive the Parigraha "combined form"
by splitting the pair text on whitespace -- that silently breaks whenever
sandhi fuses two words with no visible space, e.g. "puurvebhir.rSibhiH",
and was caught and replaced with the explicit PARIGRAHA_FORMS table below):

1. Parigraha insertions (word + iti + word, applying rules 10.7-10.9,
   10.12-10.14, 10.16) -- these do not appear in the samhita-patha at all;
   PARIGRAHA_FORMS gives each flagged word's (first, repeat) rendering by
   hand, following Uvata's own worked example for 10.14 ("vibhaavaso iti
   vibhaavaso" -- given WITHOUT sandhi between the components, which is why
   no sandhi is applied within these inserted units either), and 10.16
   (the repeat of a compound shows the avagraha split).
2. A handful of individual pairs marked "confidence": "low" in the output,
   where the standalone monosyllable "aa" (the preverb, not just any short
   a) appears -- sutra 10.3 explicitly calls out single-syllable words
   like "aa" as stopping the pairing chain early (avasyanti) rather than
   continuing to pair forward in the ordinary way, per Uvata's own example
   ("aa mandram | mandram-aa vareNyam"). Reconstructing that exact
   mechanic for these specific verses (which don't share Uvata's cited
   wording) was judged too uncertain to guess at silently -- the ordinary
   pairwise rendering is given instead, flagged low-confidence, rather than
   a confident-looking but unverified special-case reconstruction.

Not a re-runnable pipeline in the usual "fetch and rebuild" sense (there is
no second source to fetch -- the alignment is this session's own reading) --
run to regenerate the JSON deterministically from the data below, not to
redo the alignment.
"""
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_PATH = (
    REPO_ROOT
    / "dge/data/vedanga/shiksha/pratishakhya/rigveda_pratishakhya/krama_generated_output.json"
)

RULE_REFS = {
    "base_pairing": "10.2",
    "avagrhya_parigraha": "10.7",
    "ardharca_final_parigraha": "10.9",
    "sthitopasthita": "10.14",
    "avagraha_split_in_repeat": "10.16",
    "ardharca_no_sandhi": "10.18",
    "monosyllable_avasana": "10.3",
}

# marker suffixes on words in VERSES: * = avagrhya (10.7), # = ardharca-final (10.9),
# ~ = the monosyllable "aa" (10.3 avasana zone, low-confidence flag on its pairs)

VERSES = [
    dict(id="1.1.1", meter="gayatri",
         ardharcas=[
             dict(words=["अग्निम्", "ईळे", "पुरःऽहितम्*", "यज्ञस्य", "देवम्", "ऋत्विजम्#"],
                  pairs=["अग्निमीळे", "ईळे पुरोहितम्", "पुरोहितं यज्ञस्य", "यज्ञस्य देवम्", "देवमृत्विजम्"]),
             dict(words=["होतारम्", "रत्नऽधातमम्*#"],
                  pairs=["होतारं रत्नधातमम्"]),
         ]),
    dict(id="1.1.2", meter="gayatri",
         ardharcas=[
             dict(words=["अग्निः", "पूर्वेभिः", "ऋषिऽभिः*", "ईड्यः", "नूतनैः", "उत#"],
                  pairs=["अग्निः पूर्वेभिः", "पूर्वेभिर्ऋषिभिः", "ऋषिभिरीड्यः", "ईड्यो नूतनैः", "नूतनैरुत"]),
             dict(words=["सः", "देवान्", "आ~", "इह", "वक्षति#"],
                  pairs=["स देवान्", "देवाँ आ", "एह", "इह वक्षति"]),
         ]),
    dict(id="1.1.3", meter="gayatri",
         ardharcas=[
             dict(words=["अग्निना", "रयिम्", "अश्नवत्", "पोषम्", "एव", "दिवेऽदिवे*#"],
                  pairs=["अग्निना रयिम्", "रयिमश्नवत्", "अश्नवत्पोषम्", "पोषमेव", "एव दिवेदिवे"]),
             dict(words=["यशसम्", "वीरवत्ऽतमम्*#"],
                  pairs=["यशसं वीरवत्तमम्"]),
         ]),
    dict(id="1.1.4", meter="gayatri",
         ardharcas=[
             dict(words=["अग्ने", "यम्", "यज्ञम्", "अध्वरम्", "विश्वतः", "परिऽभूः*", "असि#"],
                  pairs=["अग्ने यम्", "यं यज्ञम्", "यज्ञमध्वरम्", "अध्वरं विश्वतः", "विश्वतः परिभूः", "परिभूरसि"]),
             dict(words=["सः", "इत्", "देवेषु", "गच्छति#"],
                  pairs=["स इत्", "इद्देवेषु", "देवेषु गच्छति"]),
         ]),
    dict(id="1.1.5", meter="gayatri",
         ardharcas=[
             dict(words=["अग्निः", "होता", "कविऽक्रतुः*", "सत्यः", "चित्रश्रवःऽतमः*#"],
                  pairs=["अग्निर्होता", "होता कविक्रतुः", "कविक्रतुः सत्यः", "सत्यश्चित्रश्रवस्तमः"]),
             dict(words=["देवः", "देवेभिः", "आ~", "गमत्#"],
                  pairs=["देवो देवेभिः", "देवेभिरा", "आ गमत्"]),
         ]),
    dict(id="1.1.6", meter="gayatri",
         ardharcas=[
             dict(words=["यत्", "अङ्ग", "दाशुषे", "त्वम्", "अग्ने", "भद्रम्", "करिष्यसि#"],
                  pairs=["यदङ्ग", "अङ्ग दाशुषे", "दाशुषे त्वम्", "त्वमग्ने", "अग्ने भद्रम्", "भद्रं करिष्यसि"]),
             dict(words=["तव", "इत्", "तत्", "सत्यम्", "अङ्गिरः#"],
                  pairs=["तवेत्", "इत्तत्", "तत्सत्यम्", "सत्यमङ्गिरः"]),
         ]),
    dict(id="1.1.7", meter="gayatri",
         ardharcas=[
             dict(words=["उप", "त्वा", "अग्ने", "दिवेऽदिवे", "दोषाऽवस्तः*", "धिया", "वयम्#"],
                  pairs=["उप त्वा", "त्वाग्ने", "अग्ने दिवेदिवे", "दिवेदिवे दोषावस्तः", "दोषावस्तर्धिया", "धिया वयम्"]),
             dict(words=["नमः", "भरन्तः", "आ~", "इमसि#"],
                  pairs=["नमो भरन्तः", "भरन्तो", "एमसि"]),
         ]),
    dict(id="1.1.8", meter="gayatri",
         ardharcas=[
             dict(words=["राजन्तम्", "अध्वराणाम्", "गोपाम्", "ऋतस्य", "दीदिविम्#"],
                  pairs=["राजन्तमध्वराणाम्", "अध्वराणां गोपाम्", "गोपामृतस्य", "ऋतस्य दीदिविम्"]),
             dict(words=["वर्धमानम्", "स्वे", "दमे#"],
                  pairs=["वर्धमानं स्वे", "स्वे दमे"]),
         ]),
    dict(id="1.1.9", meter="gayatri",
         ardharcas=[
             dict(words=["सः", "नः", "पिताऽइव*", "सूनवे", "अग्ने", "सुऽउपायनः*", "भव#"],
                  pairs=["स नः", "नः पितेव", "पितेव सूनवे", "सूनवेऽग्ने", "अग्ने सूपायनः", "सूपायनो भव"]),
             dict(words=["सचस्व", "नः", "स्वस्तये#"],
                  pairs=["सचस्वा नः", "नः स्वस्तये"]),
         ]),
]

# Hand-determined (first_form, repeat_form) for every word flagged * or #.
# first_form = the sandhi-combined depiction (10.6-style, or plain if the
# word is bare); repeat_form = the avagraha-split depiction for an avagrhya
# word (10.16) or the same bare form again for an ardharca-final-only word
# (10.9, no compound to split -- 10.12-14's sthita/upasthita just confirms
# the plain form). Keyed by bare word (marker suffixes stripped).
PARIGRAHA_FORMS = {
    "पुरःऽहितम्": ("पुरोहितम्", "पुरःऽहितम्"),
    "ऋत्विजम्": ("ऋत्विजम्", "ऋत्विजम्"),
    "रत्नऽधातमम्": ("रत्नधातमम्", "रत्नऽधातमम्"),
    "ऋषिऽभिः": ("ऋषिभिः", "ऋषिऽभिः"),
    "उत": ("उत", "उत"),
    "वक्षति": ("वक्षति", "वक्षति"),
    "दिवेऽदिवे": ("दिवेदिवे", "दिवेऽदिवे"),
    "वीरवत्ऽतमम्": ("वीरवत्तमम्", "वीरवत्ऽतमम्"),
    "परिऽभूः": ("परिभूः", "परिऽभूः"),
    "असि": ("असि", "असि"),
    "गच्छति": ("गच्छति", "गच्छति"),
    "कविऽक्रतुः": ("कविक्रतुः", "कविऽक्रतुः"),
    "चित्रश्रवःऽतमः": ("चित्रश्रवस्तमः", "चित्रश्रवःऽतमः"),
    "गमत्": ("गमत्", "गमत्"),
    "करिष्यसि": ("करिष्यसि", "करिष्यसि"),
    "अङ्गिरः": ("अङ्गिरः", "अङ्गिरः"),
    "दोषाऽवस्तः": ("दोषावस्तः", "दोषाऽवस्तः"),
    "वयम्": ("वयम्", "वयम्"),
    "इमसि": ("इमसि", "इमसि"),
    "दीदिविम्": ("दीदिविम्", "दीदिविम्"),
    "दमे": ("दमे", "दमे"),
    "पिताऽइव": ("पितेव", "पिताऽइव"),
    "सुऽउपायनः": ("सूपायनः", "सुऽउपायनः"),
    "भव": ("भव", "भव"),
    "स्वस्तये": ("स्वस्तये", "स्वस्तये"),
}


def strip_word(w):
    return w.rstrip("*#~")


def build_units(ardharca):
    words = ardharca["words"]
    pairs = ardharca["pairs"]
    units = []
    for i, pair_text in enumerate(pairs):
        w1, w2 = words[i], words[i + 1]
        low_conf = "~" in w1 or "~" in w2
        unit = {
            "type": "pair",
            "text": pair_text,
            "rule": RULE_REFS["base_pairing"],
            "confidence": "low" if low_conf else "high",
        }
        if low_conf:
            unit["note"] = (
                "Contains the monosyllable 'aa' -- sutra 10.3 flags such "
                "monosyllables as stopping the pairing chain rather than "
                "continuing forward in the ordinary way; this pair is the "
                "ordinary rendering, not a reconstruction of that special "
                "mechanic. See KRAMA_VERIFICATION_PACKET.md."
            )
        units.append(unit)

        is_avagrhya = "*" in w2
        is_ardharca_final = "#" in w2
        if is_avagrhya or is_ardharca_final:
            bare = strip_word(w2)
            first_form, repeat_form = PARIGRAHA_FORMS[bare]
            rules = []
            if is_avagrhya:
                rules.append(RULE_REFS["avagrhya_parigraha"])
            if is_ardharca_final:
                rules.append(RULE_REFS["ardharca_final_parigraha"])
            rules.append(RULE_REFS["sthitopasthita"])
            units.append({
                "type": "parigraha",
                "text": f"{first_form} इति {repeat_form}",
                "for_word": bare,
                "rule": rules,
                "confidence": "medium",
                "note": ("Word+iti+word given with no sandhi between the components, "
                         "per Uvata's own worked example on 10.14 "
                         "('vibhaavaso iti vibhaavaso')."),
            })
    return units


def main():
    output_verses = []
    for verse in VERSES:
        ardharca_outputs = []
        for ardharca in verse["ardharcas"]:
            units = build_units(ardharca)
            ardharca_outputs.append({
                "pada_words": [strip_word(w) for w in ardharca["words"]],
                "units": units,
            })
        krama_text = " । ".join(
            u["text"] for ardharca in ardharca_outputs for u in ardharca["units"]
        )
        output_verses.append({
            "id": verse["id"],
            "meter": verse["meter"],
            "ardharcas": ardharca_outputs,
            "krama_patha_devanagari": krama_text,
        })

    data = {
        "schema": "generic",
        "note": (
            "Generated Krama-patha output for RV 1.1 (all 9 verses), produced by "
            "tools/pratishakhya/generate_krama_rv_1_1.py applying the rule logic in "
            "krama_kramahetu_rules.json. NOT validated against a published Krama-patha "
            "edition -- see tools/pratishakhya/KRAMA_VERIFICATION_PACKET.md for what to "
            "check and how. Each pair's sandhi is taken verbatim from DGE's own attested "
            "samhita_patha (dge/data/vedas/rigveda/shakala_shakha/samhita/mandala_01/"
            "data.json, items 1.1.1-1.1.9), not independently computed; Parigraha "
            "insertions are this session's own construction from the sutra text, cited "
            "per unit. Units marked confidence:'low' involve the monosyllable 'aa' "
            "(sutra 10.3's avasana exception zone) and are the ordinary rendering, not a "
            "reconstruction of that special mechanic -- flagged rather than guessed."
        ),
        "rule_source": "dge/data/vedanga/shiksha/pratishakhya/rigveda_pratishakhya/krama_kramahetu_rules.json",
        "pada_samhita_source": "dge/data/vedas/rigveda/shakala_shakha/samhita/mandala_01/data.json",
        "verification_packet": "tools/pratishakhya/KRAMA_VERIFICATION_PACKET.md",
        "items": output_verses,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    n_low = sum(
        1 for v in output_verses for a in v["ardharcas"] for u in a["units"]
        if u.get("confidence") == "low"
    )
    print(f"Wrote {len(output_verses)} verses to {OUT_PATH} ({n_low} low-confidence units)")


if __name__ == "__main__":
    main()
