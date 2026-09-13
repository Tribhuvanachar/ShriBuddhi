# Round 2 — strict, self-contained task prompt (code required, not suggestions)

Paste everything between `=== BEGIN PROMPT ===` / `=== END PROMPT ===` into ChatGPT or Gemini.
No repository access needed — code, sūtra text, and test cases are all inline.

=== BEGIN PROMPT ===

I sent you a similar prompt before. Your previous answer to "Task A" (fix the SLP1 र्ऋ/रृ
collision) gave a good APPROACH (a ZWNJ marker) but described it in prose rather than
demonstrating it actually working, and some of your Task C answers turned out to be wrong when
I checked them against my own primary sources, or to already be fixed by earlier work you
weren't shown. This round is stricter:

**HARD RULE FOR THIS ENTIRE RESPONSE: every claim must come with either (a) runnable Python
that I can paste in and run, or (b) an exact quotation from the sūtra text I give you below,
with your reasoning tied to the literal words of that quotation — not a general appeal to
"Sanskrit grammar typically..." For anything you are not confident about, write UNRESOLVED and
say what evidence would settle it. A sentence like "you should refactor X to be more robust" or
"this needs more research" with no code and no citation is not an acceptable answer to any task
below — if you don't have a concrete patch or a concrete citation, say so explicitly instead of
padding the answer.**

I already fixed the r/f collision myself (with a ZWNJ marker, tested across 4 consecutive joins
before I trusted it) and a second bug you didn't catch (a diphthong-glide error, confirmed
against Panini 6.1.78). The current code is below. Do NOT re-solve Task A — it's done. Your job
this round is Task D (verify my fix and hunt for siblings) and Task E (three sharpened
philology questions, one with a citation to check, not just answer from scratch).

---

## TASK D — verify my fix, then find (or rule out) similar bugs elsewhere in this file

My fix: insert U+200C (ZWNJ) at a "bare consonant before independent vowel" boundary, strip it
only where a string will never be re-joined. Code is in the full listing below
(`_finish_consonant_then_vowel`, `strip_zwnj_markers`, and every call site that now calls it).

**D1.** Write a Python test that feeds the SAME r/f pattern through 10 consecutive joins (not
my 4) and confirms the boundary survives every single one. If it does NOT survive 10, show me
exactly which join breaks it and why, with the actual failing output.

**D2.** A prior review of mine warned that other Devanāgarī round-trip ambiguities might exist
beyond r/f — anusvāra/candrabindu, other independent-vowel-after-consonant cases (not just
vocalic ṛ/ṝ), avagraha, vowel length. For EACH of those categories: either (a) construct an
actual Python test case that reproduces a real collision the way I did for r/f (a `deva_to_slp1`
round trip that loses real information), and show the failing output, or (b) show a Python test
case demonstrating that category is actually fine, with its output. Do not just assert "this
might also be a problem" without a concrete input/output demonstrating it either way.

---

## TASK E — three sharpened philology questions

**E1 — CONFIRMED, just restate for the record.** You (or another model) previously confirmed
10.12 = upasthita, 10.13 = sthita (my original sourcing was right). No new work needed here —
just confirm you agree, in one sentence, so this is on the record for this round too.

**E2 — sharpened, with a corrected citation.** Previously, a claim was made that ordinary
external sandhi (savarṇa-dīrgha, guṇa) applies between a Parigraha word and "iti" UNLESS the
word is pragṛhya, citing "RPr 1.74" for "vocative o is pragṛhya." I checked my own sūtra corpus
directly: **1.74 is wrong** — it reads "upottamaṃ nānudāttaṃ na padyam" (an accent-placement
rule, unrelated). The correct sūtra for "vocative o is pragṛhya" is **1.68**: "ओकार
आमन्त्रितजः प्रगृह्यः" (okāra āmantritajaḥ pragṛhyaḥ). Given that correction:

Is the underlying claim (ordinary sandhi applies to word+iti EXCEPT for pragṛhya words) still
correct? Both attested examples I have are pragṛhya (`vibhāvaso`, vocative-o per 1.68;
`bāhū`, dual per 1.73 "asme yuṣme tve amī" and the dual-in-ī/ū/e class implied around 1.71's
"ṣaṣṭhādayaś ca dvivaco'ntabhājas trayo dīrghāḥ") — so neither PROVES the general case, only
that these two happen to be exempt for an independent reason. **If your answer is "yes, ordinary
sandhi applies to non-pragṛhya words," give me the actual corrected Python for this function**
(currently it always concatenates with zero sandhi):

```python
def get_sthitopasthita(token_deva, combined_form_deva=None):
    """10.14: sthita + upasthita given together. If the word is an
    avagrhya compound (10.16: the repeat shows the avagraha split),
    combined_form_deva should be supplied as the already-samhita-joined
    (non-split) rendering."""
    compound = parse_compound(token_deva)
    first_form = combined_form_deva if combined_form_deva else token_deva
    second_form = token_deva  # bare pada form, split if it's a compound (10.16)
    return f"{first_form} इति {second_form}"
```
It has access to `samhita_join(w1, w2, w1_is_pragrhya=...)` and `is_pragrhya(word_deva)` from
the files below. If you're not confident enough to write this patch, say UNRESOLVED explicitly
— do not hand back prose describing what the function "should" do.

**E3 — a specific citation to verify or refute, not answer freehand.** RV 1.1.7:
Pada-pāṭha: `... नमः । भरन्तः । आ । इमसि ॥` — Attested Saṃhitā-pāṭha: `... नमो भरन्त एमसि ॥`
The general a-class-visarga-before-voiced rule predicts "भरन्तो आ"; the actual text shows the
visarga dropping entirely. A previous answer proposed **"RPr 2.27"** as the licensing sūtra. I
checked my own corpus directly. Here is the ACTUAL text of 2.24–2.28 (my corpus flags these as
`has_uncertain_reading: true`, not independently cross-checked the way Paṭala 10–11 were):

```
2.24  विसर्जनीयो'रिफितो दीर्घपूर्वः स्वरोदयः। आकारम्
      visarjanIyaH ariPitaH dIrGap[?]rvaH svarodayaH AkAram
2.25  उत्तमौ च द्वौ स्वरौ
      uttamO ca dvO svarO
2.26  ताः पदवृत्तयः
      tAH padavfttayaH
2.27  ह्रस्वपूर्वस्तु सो'कारम्
      hrasvap[?]rvaH tu saH akAram
2.28  पूर्वौ चोपोत्तमात्स्वरौ
      p[?]rvO ca upottamAt svarO
```
(`[?]` marks a character my source itself flags as uncertain — likely `U` from "pUrvaH".)

Does 2.24/2.27 (a contrastive pair: 2.24 = visarga preceded by a LONG vowel, 2.27 = preceded by
a SHORT vowel) actually describe a special FULL-ELISION rule specific to a following ā, or does
it look like it's describing the general derivation of the a-class visarga→o outcome (visarga
becomes an "a"/"ā" sound as an intermediate step, contributing to guṇa/o-formation) that a
general classical engine already implements as "visarga_a_class_before_voiced"? Base your
answer on the literal words of 2.24/2.27 above, not on what would be phonologically convenient.
If the text doesn't clearly decide it, say UNRESOLVED and name exactly what's missing (a
Bhāṣya gloss on these two sūtras, most likely) rather than picking the more plausible-sounding
reading.

---

## Full current code (for Task D; also has E2's helper functions for context)

```python
#!/usr/bin/env python3
"""A real, scoped Sanskrit sandhi engine. Covers Patala 2 (vowel: savarna-dirgha,
guna, vrddhi, yan, eng-a elision) and Patala 4 (visarga: sa/esa exception,
i/u-class before vowel, a-class before voiced/unvoiced, word-final n/m/t)."""
from indic_transliteration import sanscript

VOWELS_SHORT = set("aiufx")
VOWELS_LONG = set("AIUFX")
SIMPLE_VOWELS = VOWELS_SHORT | VOWELS_LONG
DIPHTHONGS = set("eEoO")
ALL_VOWELS = SIMPLE_VOWELS | DIPHTHONGS

VOICED_CONSONANTS = set("gGjJqQdDbBNnmYRyrlvh")
UNVOICED_CONSONANTS = set("kKcCwWtTpPSzs")
SIBILANTS_UNVOICED = set("Szs")

SAVARNA = {"a": "a", "A": "a", "i": "i", "I": "i", "u": "u", "U": "u", "f": "f", "F": "f"}
GUNA_OF = {"i": "e", "I": "e", "u": "o", "U": "o", "f": "ar", "F": "ar"}
VRDDHI_OF_A_PLUS = {"e": "E", "E": "E", "o": "O", "O": "O"}
YAN_OF = {"i": "y", "I": "y", "u": "v", "U": "v", "f": "r", "F": "r"}

ZWNJ = "‌"


def deva_to_slp1(s):
    s = s.replace("‍", "")  # strip ZWJ only -- ZWNJ must survive
    return sanscript.transliterate(s, sanscript.DEVANAGARI, sanscript.SLP1)


def slp1_to_deva(s):
    return sanscript.transliterate(s, sanscript.SLP1, sanscript.DEVANAGARI)


def strip_zwnj_markers(s):
    return s.replace(ZWNJ, "")


def strip_accents_slp1(s):
    return s.replace("॒", "").replace("॑", "")


def join_vowel_vowel(v1, v2):
    b1 = SAVARNA.get(v1)
    b2 = SAVARNA.get(v2)
    if b1 and b1 == b2:
        long_form = {"a": "A", "i": "I", "u": "U", "f": "F"}[b1]
        return long_form, "savarna_dirgha"
    if v1 in ("a", "A"):
        if v2 in GUNA_OF:
            return GUNA_OF[v2], "guna"
        if v2 in VRDDHI_OF_A_PLUS:
            return VRDDHI_OF_A_PLUS[v2], "vrddhi"
    if v1 in YAN_OF and v1 not in ("a", "A") and v2 not in (v1, SAVARNA.get(v1)):
        return YAN_OF[v1] + v2, "yan"
    return None


def transliterate_word(deva_word):
    return strip_accents_slp1(deva_to_slp1(deva_word))


IRREGULAR_VISARGA_STEMS = {"dozAvastaH": "dozAvastar"}
IRREGULAR_LENGTHENING_BEFORE_CONSONANT = {"sacasva": "sacasvA"}


def _match_lexical_suffix(s1, table):
    if s1 in table:
        return "", s1
    for key in table:
        suffix = " " + key
        if s1.endswith(suffix):
            return s1[: -len(key)], key
    return None


def resolve_compound(word_deva):
    if "ऽ" not in word_deva:
        return word_deva, [], []
    segments = word_deva.split("ऽ")
    combined = segments[0]
    rules = []
    for seg in segments[1:]:
        r = samhita_join(combined, seg, resolve_w1_compound=False)
        combined = r["surface"].replace(" ", "")
        rules.append(r["rule"])
    return combined, segments, rules


def reconstruct_chain(words_deva):
    """Folds samhita_join across a WHOLE word sequence, simulating how
    continuous samhita-patha text is built."""
    if not words_deva:
        return "", []
    first = words_deva[0]
    combined = resolve_compound(first)[0] if "ऽ" in first else first
    rules = []
    for w in words_deva[1:]:
        r = samhita_join(combined, w, resolve_w1_compound=False)
        combined = r["surface"]
        rules.append(r["rule"])
    return strip_zwnj_markers(combined), rules


def samhita_join(w1_deva, w2_deva, w1_is_pragrhya=False, resolve_w1_compound=True):
    if resolve_w1_compound and "ऽ" in w1_deva:
        w1_deva = resolve_compound(w1_deva)[0]
    if "ऽ" in w2_deva:
        w2_deva = resolve_compound(w2_deva)[0]
    s1 = transliterate_word(w1_deva)
    s2 = transliterate_word(w2_deva)
    if not s1 or not s2:
        return {"surface": w1_deva + w2_deva, "rule": "empty_input", "confidence": "low", "note": ""}

    lengthening_match = _match_lexical_suffix(s1, IRREGULAR_LENGTHENING_BEFORE_CONSONANT)
    if lengthening_match and s2[0] not in ALL_VOWELS:
        prefix, key = lengthening_match
        lengthened = prefix + IRREGULAR_LENGTHENING_BEFORE_CONSONANT[key]
        return _finish(lengthened + " " + s2, "irregular_lengthening_lexical_exception", w1_deva, w2_deva)

    visarga_match = _match_lexical_suffix(s1, IRREGULAR_VISARGA_STEMS)
    if visarga_match and s2[0] in VOICED_CONSONANTS:
        prefix, key = visarga_match
        base = prefix + IRREGULAR_VISARGA_STEMS[key]
        return _finish(base + s2, "irregular_visarga_lexical_exception", w1_deva, w2_deva)

    last1 = s1[-1]
    first2 = s2[0]

    if last1 == "H":
        stem = s1[:-1]
        prev_vowel = stem[-1] if stem else ""
        if stem in ("sa", "eza", "eSa"):
            return _finish(stem + " " + s2, "visarga_sa_esa_elision_blocks_further_sandhi", w1_deva, w2_deva)
        if prev_vowel in ("i", "I", "u", "U"):
            if first2 in ALL_VOWELS:
                return _finish_consonant_then_vowel(stem + "r", s2, "visarga_iu_class_before_vowel", w1_deva, w2_deva)
            if first2 in SIBILANTS_UNVOICED:
                return _finish(stem + "H " + s2, "visarga_iu_class_before_sibilant_unresolved", w1_deva, w2_deva, confidence="low")
            if first2 in UNVOICED_CONSONANTS:
                return _finish(stem + "H " + s2, "visarga_iu_class_before_unvoiced_consonant", w1_deva, w2_deva)
            return _finish(stem + "r" + s2, "visarga_iu_class_before_voiced_consonant", w1_deva, w2_deva)
        if prev_vowel in ("e", "E", "o", "O"):
            if first2 in ALL_VOWELS:
                return _finish_consonant_then_vowel(stem + "r", s2, "visarga_diphthong_class_before_vowel", w1_deva, w2_deva)
            if first2 in VOICED_CONSONANTS:
                return _finish(stem + "r" + s2, "visarga_diphthong_class_before_voiced_consonant", w1_deva, w2_deva)
            return _finish(stem + "H " + s2, "visarga_diphthong_class_before_unvoiced", w1_deva, w2_deva)
        if prev_vowel in ("a", "A"):
            base = stem[:-1]
            if first2 == "a":
                return _finish(base + "o'" + s2[1:], "visarga_a_class_before_a_elided", w1_deva, w2_deva)
            if first2 in ALL_VOWELS or first2 in VOICED_CONSONANTS:
                return _finish(base + "o " + s2, "visarga_a_class_before_voiced", w1_deva, w2_deva)
            if first2 in ("c", "C"):
                return _finish(stem[:-1] + "aS" + s2, "visarga_a_class_sibilant_assimilation_palatal", w1_deva, w2_deva)
            if first2 in ("w", "W"):
                return _finish(stem[:-1] + "az" + s2, "visarga_a_class_sibilant_assimilation_retroflex", w1_deva, w2_deva)
            if first2 in ("t", "T"):
                return _finish(stem[:-1] + "as" + s2, "visarga_a_class_sibilant_assimilation_dental", w1_deva, w2_deva)
            return _finish(stem + "H " + s2, "visarga_a_class_before_unvoiced_velar_labial", w1_deva, w2_deva)
        return _finish(s1 + " " + s2, "visarga_unhandled_context", w1_deva, w2_deva, confidence="low")

    if last1 == "m":
        if first2 in ALL_VOWELS:
            return _finish(s1 + s2, "m_before_vowel_unchanged", w1_deva, w2_deva)
        return _finish(s1[:-1] + "M " + s2, "m_before_consonant_anusvara", w1_deva, w2_deva)

    if last1 == "n":
        if first2 in ALL_VOWELS:
            stem = s1[:-1]
            return _finish(stem + "~ " + s2, "n_before_vowel_vedic_nasalization_approximated", w1_deva, w2_deva, confidence="low")
        return _finish(s1 + " " + s2, "n_before_consonant_unchanged", w1_deva, w2_deva)

    if last1 == "t":
        if first2 in ALL_VOWELS:
            return _finish(s1[:-1] + "d" + s2, "t_before_vowel_voiced", w1_deva, w2_deva)
        if first2 in ("d", "D", "g", "G", "b", "B", "j", "J"):
            return _finish(s1[:-1] + first2 + s2, "t_assimilates_to_following_voiced", w1_deva, w2_deva)
        return _finish(s1 + s2, "t_before_unvoiced_unchanged", w1_deva, w2_deva)

    if last1 in ALL_VOWELS:
        if w1_is_pragrhya:
            if first2 == "a":
                return _finish(s1 + "'" + s2[1:], "pragrhya_no_sandhi_a_elided", w1_deva, w2_deva)
            return _finish(s1 + " " + s2, "pragrhya_no_sandhi", w1_deva, w2_deva)
        if first2 in ALL_VOWELS:
            if last1 in DIPHTHONGS:
                if first2 == "a":
                    return _finish(s1 + "'" + s2[1:], "eng_a_class_before_a_elided", w1_deva, w2_deva)
                replacement = {"e": "ay", "E": "Ay", "o": "av", "O": "Av"}[last1]
                return _finish(s1[:-1] + replacement + s2, "eng_a_class_before_other_vowel", w1_deva, w2_deva)
            joined = join_vowel_vowel(last1, first2)
            if joined:
                result, rule = joined
                return _finish(s1[:-1] + result + s2[1:], rule, w1_deva, w2_deva)
            return _finish(s1 + " " + s2, "vowel_vowel_unhandled", w1_deva, w2_deva, confidence="low")
        return _finish(s1 + " " + s2, "vowel_before_consonant_unchanged", w1_deva, w2_deva)

    return _finish(s1 + " " + s2, "consonant_before_anything_default", w1_deva, w2_deva)


def _finish(slp1_result, rule, w1_deva, w2_deva, confidence="high", note=""):
    return {"surface": slp1_to_deva(slp1_result), "rule": rule, "confidence": confidence, "note": note}


def _finish_consonant_then_vowel(prefix_slp1, suffix_slp1, rule, w1_deva, w2_deva):
    """ONLY vocalic-r/rr (f/F) needs the separate-transliterate-then-concatenate
    workaround. The ZWNJ preserves this across repeated joins (see module notes above)."""
    if suffix_slp1[0] not in ("f", "F"):
        return _finish(prefix_slp1 + suffix_slp1, rule, w1_deva, w2_deva)
    deva = slp1_to_deva(prefix_slp1) + ZWNJ + slp1_to_deva(suffix_slp1)
    return {"surface": deva, "rule": rule, "confidence": "high", "note": ""}


PRAGRHYA_LEXICAL_SLP1 = {"asme", "yuzme", "tve", "amI", "amU"}


def is_pragrhya(token_deva, context=None):
    """1.73: asme/yuSme/tve/amI/amU (closed lexical class). Dual forms
    ending -ii/-uu/-e are pragrhya via context={"is_dual": True}.
    1.68 ("okAra AmantritajaH pragfhyaH" -- vocative 'o' is pragrhya) was
    ONLY ADDED 11 Sep 2026, found missing entirely while fact-checking an
    external citation for this exact sutra (which itself cited the wrong
    number, 1.74, but the underlying substance held up against this
    project's own corpus) -- this function had a vocative check for -e
    but none for -o, even though "vibhaavaso" (this project's own cited
    10.14 example) is exactly this case. Gated on is_amantrita context,
    like the -e case, because plenty of non-vocative words end in "o" via
    ordinary a-class visarga sandhi and are NOT pragrhya for that reason
    -- this predicate still cannot distinguish "vocative o" from
    "o that arose from visarga sandhi" without being told which case it is."""
    s = transliterate_word(token_deva)
    if s in PRAGRHYA_LEXICAL_SLP1:
        return True, "lexical (1.73)"
    if context:
        if context.get("is_dual") and s and s[-1] in ("I", "U", "e"):
            return True, "morphological dual (context-supplied)"
        if context.get("is_amantrita") and s and s[-1] == "e":
            return True, "contextual (aamantrita vocative ending in -e)"
        if context.get("is_amantrita") and s and s[-1] == "o":
            return True, "contextual (aamantrita vocative ending in -o, sutra 1.68)"
    return False, "not matched"


def get_sthita(token_deva):
    """10.13: the bare word alone."""
    return token_deva


def get_upasthita(token_deva):
    """10.12: word + iti, no sandhi (per current, possibly wrong per E2, assumption)."""
    return f"{token_deva} इति"


def get_sthitopasthita(token_deva, combined_form_deva=None):
    """10.14: sthita + upasthita given together. Currently assumes NO sandhi
    between word and iti in all cases -- see Task E2 above."""
    first_form = combined_form_deva if combined_form_deva else token_deva
    second_form = token_deva
    return f"{first_form} इति {second_form}"


# --- Self-test (all currently pass) ---
SELF_TEST_CASES = [
    ("अग्निम्", "ईळे", "अग्निमीळे"),
    ("पुरोहितम्", "यज्ञस्य", "पुरोहितं यज्ञस्य"),
    ("देवम्", "ऋत्विजम्", "देवमृत्विजम्"),
    ("यत्", "अङ्ग", "यदङ्ग"),
    ("अग्निः", "होता", "अग्निर्होता"),
    ("देवः", "देवेभिः", "देवो देवेभिः"),
    ("सः", "इत्", "स इत्"),
    ("इत्", "तत्", "इत्तत्"),
    ("सूनवे", "अग्ने", "सूनवेऽग्ने"),
    ("वने", "इन्द्रः", "वनयिन्द्रः"),
    ("तस्मै", "इति", "तस्मायिति"),
]

# --- The ZWNJ fix, already verified across 4 joins (Task D asks you to try 10) ---
CHAIN_TEST_WORDS = ["अग्निः", "पूर्वेभिः", "ऋषिऽभिः", "ईड्यः", "नूतनैः", "उत"]
CHAIN_TEST_EXPECTED = "अग्निः पूर्वेभिर्ऋषिभिरीड्यो नूतनैरुत"  # real RV 1.1.2 Samhita-patha

# --- The still-open RV 1.1.7 gap (Task E3) ---
STILL_OPEN_CASE = {
    "words": ["नमः", "भरन्तः", "आ", "इमसि"],
    "computed": "नमो भरन्तो एमसि",
    "attested": "नमो भरन्त एमसि",
}
```

Answer Task D and Task E as clearly separated sections, in the format required at the top of
this prompt: code or exact citation for every claim, UNRESOLVED where you don't have either.

=== END PROMPT ===
