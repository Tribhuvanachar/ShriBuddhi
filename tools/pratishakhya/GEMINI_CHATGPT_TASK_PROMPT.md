# Self-contained task prompt for Gemini / ChatGPT

Everything needed is inline below — no repository access, no links to follow. Paste the whole
block between the `=== BEGIN PROMPT ===` / `=== END PROMPT ===` markers into Gemini or ChatGPT.

=== BEGIN PROMPT ===

I am building a computational Krama-pāṭha generator (a Vedic word-repetition recitation form)
for the Ṛgveda Śākala tradition, based on Śaunaka's Ṛgveda-Prātiśākhya (Krama-Paṭala, ch. 10)
with Uvaṭa's Bhāṣya. Below is the actual Python sandhi engine, the actual sūtra text it's based
on, and two concrete failing test cases. I want you to do THREE things, in order:

1. **Fix a real bug** in the code (Task A) — propose an actual patch, not just a description.
2. **Answer three narrow philological questions** (Task B) where my own sourcing conflicts with
   a claim made by a different AI system I consulted earlier.
3. **Give an overall critique** of the engine's design (Task C) — anything wrong, missing, or
   over-engineered, beyond what I've already flagged below.

---

## TASK A — fix a real, diagnosed bug (technical, not philological)

The `indic_transliteration` Python library's SLP1 transliteration scheme cannot distinguish:
- "र्ऋ" (a BARE consonant र्, immediately followed by an INDEPENDENT vowel ऋ — e.g. produced
  by a visarga-to-र insertion before a vocalic-r word), from
- "रृ" (that same consonant र WITH ऋ as its own DEPENDENT vowel-matra, i.e. one syllable रृ)

Both forms round-trip to the identical SLP1 string `"rf"`. Proof (this is real, reproducible
Python using that library):
```python
from indic_transliteration import sanscript
def deva_to_slp1(s): return sanscript.transliterate(s, sanscript.DEVANAGARI, sanscript.SLP1)
def slp1_to_deva(s): return sanscript.transliterate(s, sanscript.SLP1, sanscript.DEVANAGARI)

print(deva_to_slp1('र्ऋषि'))   # -> 'rfzi'
print(deva_to_slp1('रृषि'))    # -> 'rfzi'   <-- SAME as above, information already lost forward
print(slp1_to_deva('rfzi'))    # -> 'रृषि'   <-- round-trips to the WRONG one when ambiguous
```

My engine works around this for a SINGLE join by keeping two chunks as separate strings and
transliterating each independently (this correctly avoids the collision once):
```python
def _finish_consonant_then_vowel(prefix_slp1, suffix_slp1, rule, w1_deva, w2_deva):
    if suffix_slp1[0] not in ("f", "F"):
        return _finish(prefix_slp1 + suffix_slp1, rule, w1_deva, w2_deva)
    deva = slp1_to_deva(prefix_slp1) + slp1_to_deva(suffix_slp1)
    return {"surface": deva, "rule": rule, "confidence": "high", "note": "",
            "w1": w1_deva, "w2": w2_deva}
```
But when this CORRECT Devanagari output is fed back into the SAME join function a second time
(as part of building up a longer chain of words), it gets converted back to SLP1 as one flat
string, collapsing the distinction again, and the SECOND `slp1_to_deva` call (a plain one, not
the special-cased one above) renders it wrong. Concretely, with the real word sequence
`["अग्निः", "पूर्वेभिः", "ऋषिभिः", "ईड्यः"]`, chaining left to right:

```
अग्निः + पूर्वेभिः -> "अग्निः पूर्वेभिः"        (ordinary, correct)
"अग्निः पूर्वेभिः" + ऋषिभिः -> "अग्निः पूर्वेभिर्ऋषिभिः"   (correct! the special-case fires here)
"अग्निः पूर्वेभिर्ऋषिभिः" + ईड्यः -> "अग्निः पूर्वेभिरृषिभिरीड्यः"   <-- WRONG. Should be
                                      "अग्निः पूर्वेभिर्ऋषिभिरीड्यः" (virama before ऋ lost)
```

The attested correct form (from the real Ṛgveda 1.1.2 Saṃhitā-pāṭha) is:
`अग्निः पूर्वेभिर्ऋषिभिरीड्यो नूतनैरुत` — note "पूर्वेभिर्ऋषिभिः" keeps its विराम.

**Your task**: propose a concrete code fix. Options I can think of but haven't verified:
(a) a private marker/sentinel character inserted at the SLP1 level immediately after a
"bare consonant before independent vowel" boundary, which survives round-tripping through this
scheme and is stripped/interpreted only by my own code, never passed to the library itself;
(b) bypass `indic_transliteration`'s SLP1 entirely for vocalic-r/rr (f/F) and hand-roll the
Devanagari rendering for just that one character class; (c) something better I haven't thought
of. Give me actual Python, not just a description of the approach, and explain why it survives
being fed through this join function an arbitrary number of times in a row (not just twice).

---

## TASK B — three narrow philological questions

My own sourcing (VedaViṣṭāram's digitized Uvaṭa Bhāṣya, cross-checked against the Sanskrit
Library's Peter Scharf edition) gives these exact sūtra texts:

```
10.12  उपस्थितम् सेतिकरणम्।       (upasthitam setikaraṇam)
       "Defines the technical term 'upasthita': a word given together with the particle 'iti'."
       Example: bāhū iti

10.13  केवलम् तु पदम् स्थितम्।     (kevalam tu padam sthitam)
       "Defines the technical term 'sthita': the bare word alone, without 'iti'."
       Example: agnim

10.14  तत् स्थितोपस्थितम् नाम यत्र उभे आह संहिते।   (tat sthitopasthitam nāma yatra ubhe āha saṃhite)
       "Defines 'sthitopasthita': where BOTH the sthita and upasthita forms are uttered
       together (word ... word+iti ... word again pattern)."
       Example: vibhāvaso iti vibhāvaso

10.16  समासान् तु पुनर्वचने इङ्ग्येत्।   (samāsān tu punarvacane iṅgyet)
       "When a compound undergoes Parigraha's second (repeated) utterance, it should be split
       at the avagraha rather than pronounced as one fused unit."
       Example: purojitī vaḥ -> repeat given as "purojitī iti puraḥ-jitī" (avagraha-split)
```

**Q1 — sūtra numbering.** A different AI-generated code sample I was given assigns 10.12 and
10.13 the OTHER way around (10.12 = sthita-formation, 10.13 = upasthita-with-sandhi) — the
opposite of what's quoted above. Which assignment is correct? Is there a known textual-variant
reason (different editions numbering these differently) that could explain this, or is one of
us simply wrong?

**Q2 — is there EVER sandhi between the word and "iti"?** The one worked example above (10.14's
own: "vibhāvaso iti vibhāvaso") shows NO sandhi between "vibhāvaso" and "iti" — but "vibhāvaso"
ends in "o", which independently doesn't combine with a following vowel under classical sandhi
anyway (o + vowel hiatus is a well-known exception), so this example alone can't prove the
GENERAL case. The same other AI-generated code sample assumed savarṇa-dīrgha SHOULD apply here
in general (e.g. "asi" + "iti" -> "asīti", fused). Is that correct for a word ending in a vowel
that would ordinarily sandhi (short "i" or "a"), or does "iti" in this specific construction
behave as prosodically separate — no external sandhi at all, regardless of the word's final
sound? A citation covering a Parigraha word that does NOT end in "o" would settle this.

**Q3 — RV 1.1.7's visarga-before-आ.** Pada-pāṭha: `... नमः । भरन्तः । आ । इमसि ॥`
Attested Saṃhitā-pāṭha: `... नमो भरन्त एमसि ॥`
The general classical a-class-visarga-before-voiced rule (visarga -> "o" before any voiced
sound, including a vowel) predicts "भरन्तो आ" — but the actual text shows the visarga dropping
ENTIRELY ("भरन्त", no visarga, no "o"), with "आ"+"इमसि" then combining normally into "एमसि"
(guṇa). Is there a SPECIFIC Prātiśākhya sūtra (likely Paṭala 2 or 4, or one of Pāṇini's own
sūtras on visarga-lopa) that licenses full visarga elision before this specific "आ", or is this
genuine free Vedic variation ("bahulaṃ chandasi") with no single derivable rule? If there IS a
specific sūtra, give its number and text.

---

## TASK C — overall critique

Beyond Task A/B: is anything else in the sandhi engine below wrong, overcomplicated, or
missing an important case? The engine deliberately does NOT cover Vedic-specific vowel classes
named only by name in Paṭala 2 (praśliṣṭa, kṣaipra, abhinihita, prakṛtibhāva), accent (Paṭala 3),
Nati (Paṭala 5), Dhvanyāgama (Paṭala 6), or Pluti (Paṭala 7–9) — that's known and intentional,
don't just tell me those are missing. I want mistakes or bad assumptions in what IS implemented.

```python
#!/usr/bin/env python3
"""A real, scoped Sanskrit sandhi engine for a Krama-patha generator.
Covers Patala 2 (vowel: savarna-dirgha, guna, vrddhi, yan, eng-a elision) and
Patala 4 (visarga: sa/esa exception, i/u-class before vowel, a-class before
voiced/unvoiced, word-final n/m/t)."""
from indic_transliteration import sanscript

VOWELS_SHORT = set("aiufx")
VOWELS_LONG = set("AIUFX")
SIMPLE_VOWELS = VOWELS_SHORT | VOWELS_LONG
DIPHTHONGS = set("eEoO")  # e, ai, o, au in SLP1
ALL_VOWELS = SIMPLE_VOWELS | DIPHTHONGS

VOICED_CONSONANTS = set("gGjJqQdDbBNnmYRyrlvh")
UNVOICED_CONSONANTS = set("kKcCwWtTpPSzs")
SIBILANTS_UNVOICED = set("Szs")

SAVARNA = {"a": "a", "A": "a", "i": "i", "I": "i", "u": "u", "U": "u", "f": "f", "F": "f"}
GUNA_OF = {"i": "e", "I": "e", "u": "o", "U": "o", "f": "ar", "F": "ar"}
VRDDHI_OF_A_PLUS = {"e": "E", "E": "E", "o": "O", "O": "O"}
YAN_OF = {"i": "y", "I": "y", "u": "v", "U": "v", "f": "r", "F": "r"}


def deva_to_slp1(s):
    s = s.replace("‌", "").replace("‍", "")
    return sanscript.transliterate(s, sanscript.DEVANAGARI, sanscript.SLP1)


def slp1_to_deva(s):
    return sanscript.transliterate(s, sanscript.SLP1, sanscript.DEVANAGARI)


def strip_accents_slp1(s):
    return s.replace("॒", "").replace("॑", "")


def join_vowel_vowel(v1, v2):
    """v1 = final vowel of word 1, v2 = initial vowel of word 2."""
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


# Lexically-specific irregular sandhi the general rules don't derive correctly.
IRREGULAR_VISARGA_STEMS = {
    "dozAvastaH": "dozAvastar",   # attested: RV 1.1.7 "doSaavastardhiyaa"
}
IRREGULAR_LENGTHENING_BEFORE_CONSONANT = {
    "sacasva": "sacasvA",         # attested: RV 1.1.9, before consonant-initial "naH"
}


def _match_lexical_suffix(s1, table):
    """table is keyed by a bare word's SLP1 form, but s1 may be a longer
    chained string ending in that word -- match a trailing " "+key too."""
    if s1 in table:
        return "", s1
    for key in table:
        suffix = " " + key
        if s1.endswith(suffix):
            return s1[: -len(key)], key
    return None


def resolve_compound(word_deva):
    """If word_deva contains the avagraha 'a-grha' marker (Pada-patha compound
    split), join its segments internally. Returns (combined_deva, segments, rules)."""
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
    """Folds samhita_join across a WHOLE word sequence to build one continuous
    string, simulating how continuous samhita-patha text is actually built."""
    if not words_deva:
        return "", []
    first = words_deva[0]
    combined = resolve_compound(first)[0] if "ऽ" in first else first
    rules = []
    for w in words_deva[1:]:
        r = samhita_join(combined, w, resolve_w1_compound=False)
        combined = r["surface"]
        rules.append(r["rule"])
    return combined, rules


def samhita_join(w1_deva, w2_deva, w1_is_pragrhya=False, resolve_w1_compound=True):
    """Compute the samhita-patha rendering of the pair (w1, w2)."""
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
                glide = {"e": "y", "E": "y", "o": "v", "O": "v"}[last1]
                return _finish(s1 + glide + s2, "eng_a_class_before_other_vowel", w1_deva, w2_deva)
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
    """prefix_slp1 ends in a BARE consonant (a visarga->r insertion); suffix_slp1
    is the next word. ONLY vocalic-r/rr (f/F) needs separate transliteration to
    avoid becoming a dependent matra on the preceding consonant -- see Task A."""
    if suffix_slp1[0] not in ("f", "F"):
        return _finish(prefix_slp1 + suffix_slp1, rule, w1_deva, w2_deva)
    deva = slp1_to_deva(prefix_slp1) + slp1_to_deva(suffix_slp1)
    return {"surface": deva, "rule": rule, "confidence": "high", "note": ""}


# --- Self-test cases (all currently pass) ---
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
]

# --- The two CURRENTLY FAILING chain-reconstruction cases (Task A/B target these) ---
FAILING_CHAIN_CASES = [
    {
        "words": ["अग्निः", "पूर्वेभिः", "ऋषिऽभिः", "ईड्यः", "नूतनैः", "उत"],
        "computed": "अग्निः पूर्वेभिरृषिभिरीड्यो नूतनैरुत",     # what reconstruct_chain() gives today
        "attested": "अग्निः पूर्वेभिर्ऋषिभिरीड्यो नूतनैरुत",     # real RV 1.1.2 Samhita-patha
        "diagnosis": "Task A's r/f collision -- fix this one",
    },
    {
        "words": ["नमः", "भरन्तः", "आ", "इमसि"],
        "computed": "नमो भरन्तो एमसि",
        "attested": "नमो भरन्त एमसि",
        "diagnosis": "Task B Q3 -- needs a sutra citation, not a code fix, before any code changes",
    },
]
```

Please answer Task A, B, and C as clearly separated sections. For Task A, give runnable Python.
For Task B, answer each question separately and say plainly if you're not confident. For Task C,
be specific — name the exact rule/branch and what's wrong with it, not general observations.

=== END PROMPT ===
