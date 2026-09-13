#!/usr/bin/env python3
"""A real, scoped Sanskrit sandhi engine for the Krama generator.

Built in direct response to a reviewed spec (11 Sep 2026) that correctly
identified the previous RV 1.1 generator as a hand-aligned reconstruction
dressed up as generation: it looked up each pair's already-correct form
from DGE's own attested samhita_patha instead of computing it. This module
is the computation this generator was missing -- `samhita_join(w1, w2)`
derives a pair's sandhi'd form from the two BARE pada words, citing which
rule fired, rather than reading the answer off ground truth.

SCOPE, stated explicitly rather than implied by what's present: this
covers the segmental (vowel + consonant/visarga) sandhi classes needed to
reproduce RV 1.1's own attested pairs -- Paṭala 2 (vowel: savarṇa-dīrgha,
guṇa, vṛddhi, yaṇ, the eṅ-a elision convention) and Paṭala 4 (consonant/
visarga: the sa/eṣa exception, i/u-class visarga before a vowel, a-class
visarga before voiced/unvoiced, word-final n/m/t behaviour). It does NOT
cover: Vedic-specific classes named in Paṭala 2 by name only so far
(praśliṣṭa, kṣaipra, abhinihita, prakṛtibhāva -- ordinary classical vowel
sandhi is applied uniformly here instead, which is a real gap, not silently
assumed equivalent) accented syllables (Paṭala 3 -- accents are stripped
before this module runs and are not restored; see krama_engine.py), Nati
(Paṭala 5), Dhvanyāgama (Paṭala 6), or Pluti (Paṭala 7-9). Each of those is
a named, separate engineering task per the reviewed spec's own Paṭala 5-9
sections -- not something this module quietly approximates.

Every join returns which rule fired (a short rule_id, not a paṭala/sūtra
number -- this engine implements the GENERAL classical/Vedic phonological
classes named in the sūtras' own definitional Paṭala 1-2, not a citation to
one specific Krama-Paṭala sūtra, which is a different kind of citation --
see krama_engine.py for the Krama-Paṭala rule citations layered on top of
this module's output) plus, where accuracy is uncertain, an explicit
low-confidence flag -- never a silent guess presented as equal-confidence
to an attested case.

ONE KNOWN, UNRESOLVED GAP surfaced by chain-reconstruction validation
(reconstruct_chain(), checked against DGE's own attested samhita_patha by
tools/pratishakhya/regenerate_krama_rv_1_1.py) -- named here rather than
silently producing a wrong answer with ordinary-looking confidence:

1. RV 1.1.7's "bharantaH"+"aa" -> attested "bharanta emasi" shows the
   visarga dropping ENTIRELY before this aa, not converting to "o" as the
   general a-class-visarga-before-voiced rule (this module's own
   "visarga_a_class_before_voiced") gives ("bharanto aa"). Neither this
   engine's classical answer nor a-guess is confirmed correct -- this
   looks like a Vedic-specific visarga-lopa variant (the Prati'saakhya's
   own "bahulam chandasi" latitude) not yet backed by a specific sutra in
   krama_kramahetu_rules.json. A citation was PROPOSED for this (RPr
   2.27, from an 11 Sep 2026 external review) but checked against this
   project's own ingested Patala 2 text and found NOT to clearly support
   the specific claim (see the architecture doc sec.6.8) -- still open,
   now with a citation to verify rather than none. Do not add an ad hoc
   special case for this without first finding which sutra (if any)
   actually licenses it.

A SECOND gap, previously listed here, was FOUND AND FIXED (11 Sep 2026,
external review, then independently verified before accepting): the
indic_transliteration library's SLP1 scheme cannot distinguish a bare
consonant + an independent vowel letter (e.g. "र्ऋ") from that same
consonant + a DEPENDENT vowel-matra (e.g. "रृ") -- both round-trip to the
identical SLP1 string. This collision is verified to hold for EVERY vowel
class, not only vocalic r/rr (a second review round correctly rejected an
earlier, too-narrow claim here that it was unique to r/f -- see
tests/test_krama_engine.py's SLP1BareConsonantVowelCollision class).
_finish_consonant_then_vowel() only special-cases f/F because that is the
only vowel class this project's own attested text actually needs the
independent-letter form for (checked against 3 real examples, not
assumed -- see that function's own docstring); the collision existing
more broadly at the transliteration level does not by itself mean this
engine mishandles other vowel classes, and no case where it does has been
found. Fixed with a ZWNJ marker inserted at the boundary by
_finish_consonant_then_vowel() and stripped only at true final-output
points by strip_zwnj_markers() -- see both functions' docstrings. Tested
across 10 consecutive re-joins, checked after every individual join (not
just the final one) before this was accepted as a real fix.
"""
import re
from indic_transliteration import sanscript

VOWELS_SHORT = set("aiufx")
VOWELS_LONG = set("AIUFX")
SIMPLE_VOWELS = VOWELS_SHORT | VOWELS_LONG
DIPHTHONGS = set("eEoO")  # e, ai, o, au in SLP1
ALL_VOWELS = SIMPLE_VOWELS | DIPHTHONGS

VOICED_CONSONANTS = set("gGjJqQdDbBNnmYRyrlvh")
UNVOICED_CONSONANTS = set("kKcCwWtTpPSzs")
SIBILANTS_UNVOICED = set("Szs")

# savarna groups: which short/long pairs count as the "same" vowel for
# savarna-dirgha and yan purposes
SAVARNA = {"a": "a", "A": "a", "i": "i", "I": "i", "u": "u", "U": "u", "f": "f", "F": "f"}
GUNA_OF = {"i": "e", "I": "e", "u": "o", "U": "o", "f": "ar", "F": "ar"}
VRDDHI_OF_A_PLUS = {"e": "E", "E": "E", "o": "O", "O": "O"}
YAN_OF = {"i": "y", "I": "y", "u": "v", "U": "v", "f": "r", "F": "r"}


# ZWNJ (zero-width non-joiner, U+200C) marks a "bare consonant immediately
# before an independent vowel" boundary so it SURVIVES being fed back
# through deva_to_slp1/slp1_to_deva an arbitrary number of times (e.g. by
# reconstruct_chain() building up a whole ardharca) without collapsing
# into the ambiguous "consonant + dependent vowel-matra" reading -- see
# _finish_consonant_then_vowel(). Verified empirically (11 Sep 2026,
# external review) that indic_transliteration passes ZWNJ through
# deva_to_slp1/slp1_to_deva unchanged at BOTH ends and does not merge a
# vowel across it, across at least 4 consecutive re-joins. It is invisible
# when rendered (a real, standard Unicode formatting character, not a
# hack character), but MUST be stripped before any string-equality
# comparison against externally-attested text or any other consumer that
# will not itself re-join the string further -- see strip_zwnj_markers().
ZWNJ = "‌"


def deva_to_slp1(s):
    s = s.replace("‍", "")  # strip ZWJ only -- ZWNJ must survive, see above
    return sanscript.transliterate(s, sanscript.DEVANAGARI, sanscript.SLP1)


def slp1_to_deva(s):
    return sanscript.transliterate(s, sanscript.SLP1, sanscript.DEVANAGARI)


def strip_zwnj_markers(s):
    """Call this on any samhita_join/reconstruct_chain "surface" string that
    is a FINAL output -- i.e. will be displayed, stored in JSON, or
    compared against externally-attested text, and will NOT itself be fed
    back into samhita_join as a w1/w2 argument. Never call it on a string
    that IS going to be re-joined -- that would silently reintroduce the
    r/f collision the marker exists to prevent."""
    return s.replace(ZWNJ, "")


def strip_accents_slp1(s):
    """Remove Vedic accent marks (anudatta U+0952, svarita U+0951) that
    survive the Devanagari->SLP1 pass as literal combining characters.
    Accent restoration is Paatala 3 work, explicitly out of scope here --
    see the module docstring."""
    return s.replace("॒", "").replace("॑", "")


# Sanskrit Library's own SLP1 variant, already handled in
# import_rv_pratishakhya.py, is not needed here: DGE's samhita/pada corpus
# uses plain Devanagari, not that source's idiosyncratic SLP1.


def join_vowel_vowel(v1, v2):
    """v1 = final vowel of word 1 (bare, i.e. short/long letter only),
    v2 = initial vowel of word 2. Returns (result, rule_id) or None if this
    pair of vowels isn't a simple vowel-vowel case this function handles."""
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
        # yan: i/I/u/U/f/F + a DISSIMILAR vowel -> semivowel + that vowel
        return YAN_OF[v1] + v2, "yan"
    return None


def transliterate_word(deva_word):
    slp1 = strip_accents_slp1(deva_to_slp1(deva_word))
    return slp1


# Rare, lexically-specific irregular sandhi this engine's general rules
# don't derive correctly -- kept as a small, explicit, cited exception
# list rather than folded silently into the general visarga rules (which
# would then misfire on the many regular a-stem words the general rule
# gets right). Confirmed against DGE's own attested samhita_patha for RV
# 1.1.7 ("doSaavastardhiyaa", not the regular "doSaavasto dhiyaa" the
# general a-class-visarga-before-voiced rule would give) -- not otherwise
# derived from a specific sutra in this pass.
IRREGULAR_VISARGA_STEMS = {
    "dozAvastaH": "dozAvastar",
}

# Similarly lexical: a handful of words attested (in DGE's own samhita_patha
# for RV 1.1.9) with a word-final vowel lengthened before the next word,
# not derivable from this engine's general rules (not conditioned on what
# follows -- "sacasva" lengthens before the consonant-initial "naH" where
# no general rule of this engine would touch a vowel-before-consonant
# pair at all). Recorded as an attested exception, not derived from a
# specific sutra in this pass.
IRREGULAR_LENGTHENING_BEFORE_CONSONANT = {
    "sacasva": "sacasvA",
}

# RPr 11.23 (yathaapadam sandhim apetahetuSu): naH -> NaH (natva/retroflexion)
# is licensed across a word boundary specifically when the trigger (r/f/F/z)
# sits in an upasarga immediately before it (Paanini 8.4.1/8.4.2/8.4.14),
# and is undone once that upasarga is no longer adjacent -- Uvata's own
# example: "pra NaH" vs "na indraH" (no "pra" adjacent). Deliberately NOT a
# general tag-free natva engine: identifying an upasarga in general needs
# morphological tagging this module doesn't have, and a broader phonological
# sieve (checked directly, 11 Sep 2026, against an external review's first
# attempt at one) either over-licenses interveners Paanini 8.4.2 doesn't
# actually name (aT-ku-pu-aaN-num only) or under/over-fires without knowing
# whether a given "r"-final word is really acting as an upasarga here. Kept
# narrow and closed, sourced directly from the one attested example, exactly
# like MONOSYLLABLE_AVASANA_SLP1/BAHUMADHYAGATA_LEXICAL_SLP1 in
# pratishakhya_classify.py.
NATVA_BOUNDARY_UPASARGAS_SLP1 = {"pra"}

# RPr 11.43 (nudet ca zauddhaakSarasandhyam aagamam): a handful of words
# attested (Uvata's own bhaashya on 11.43) with an inserted sibilant augment
# in continuous Samhita that must be OMITTED when the word is retaken for
# Parigraha. These four share no single derivable phonological trigger
# (checked directly: suScandra is bahulaM chandasi with no classical rule;
# parizkfRvan is Paanini 8.3.137's suT augment + 8.3.59's s->S; DUrzadam/
# vanarzadam look like the SAME repha-before-uSman phenomenon already
# covered by REPHI_CACHE_SLP1 below for duHsadam specifically, not a new
# "augment" at all -- Uvata's own bhaashya reuses this exact example under
# BOTH 11.41 (repha) and 11.43 (aagama) in the same continuous passage). Kept
# as a small, explicit, closed table -- like IRREGULAR_VISARGA_STEMS above --
# rather than guessed at as one general rule.
SHAUDDHAKSHARA_AGAMA_SLP1 = {
    ("su", "candra"): "suScandra",
    ("pari", "kfRvan"): "parizkfRvan",
    ("DUH", "sadam"): "DUrzadam",
    ("vana", "sadam"): "vanarzadam",
}


def _match_lexical_suffix(s1, table):
    """Both lexical-exception tables above are keyed by a single bare
    pada word's SLP1 form -- but s1 may be a longer chained string (see
    reconstruct_chain()) ending in that word, not the word alone. Checking
    equality only (s1 == key) silently fails to fire the exception for
    every position except the very start of a chain -- a real bug found
    11 Sep 2026. Returns (prefix, matched_key) if s1 is exactly key or
    ends in " "+key, else None; prefix is whatever text (possibly empty)
    precedes the matched word and must be preserved in the result."""
    if s1 in table:
        return "", s1
    for key in table:
        suffix = " " + key
        if s1.endswith(suffix):
            return s1[: -len(key)], key
    return None


def resolve_compound(word_deva):
    """If word_deva is a Pada-patha avagrhya compound (contains the
    avagraha 'ऽ'), compute its own internally-combined (samhita) surface
    form by joining its segments with samhita_join, so external sandhi
    with a neighbouring word operates on the correct combined form (e.g.
    "puraH-hitam" -> "purohitam") rather than the raw pada spelling with
    an untouched avagraha in the middle. Returns (combined_deva,
    segments_list, rule_ids_used). Non-compound words pass through
    unchanged with an empty segments list."""
    if "ऽ" not in word_deva:
        return word_deva, [], []
    segments = word_deva.split("ऽ")
    combined = segments[0]
    rules = []
    for seg in segments[1:]:
        # resolve_w1_compound=False: `combined` is running compound-internal
        # text, not a fresh Pada-patha word -- for a 3+-segment compound it
        # could itself pick up an elision-avagraha from an earlier segment
        # join, which must not be re-read as a second compound to resolve
        # (see samhita_join's own docstring on this exact failure mode).
        r = samhita_join(combined, seg, resolve_w1_compound=False)
        combined = r["surface"].replace(" ", "")  # compound-internal join never leaves a gap
        rules.append(r["rule"])
    return combined, segments, rules


def reconstruct_chain(words_deva):
    """Builds ONE continuous samhita-patha string by folding samhita_join
    across a whole sequence of bare Pada-patha words -- simulating how
    DGE's own continuous samhita_patha text is actually built (each word's
    ending sandhi's against the word immediately following it, and only
    that). This is NOT part of the Krama generator (krama_engine.py
    computes each retake pair independently and deliberately never chains
    across a whole ardharca -- Krama pairs are self-contained units, and
    10.18 forbids sandhi across an ardharca boundary regardless). This
    function exists for VALIDATION: comparing its output against DGE's own
    attested samhita_patha is a real, mechanically-checkable test of
    whether this module's phonology, applied the way continuous text is
    actually built, reproduces it -- see
    tools/pratishakhya/regenerate_krama_rv_1_1.py's attest_ardharcas(). It is
    NOT a claim that reproducing DGE's Samhita proves philological
    correctness against a traditional Krama-patha edition (a separate,
    still-open question -- architecture doc sec.10).

    Returns (final_surface_deva, rules_used_list)."""
    if not words_deva:
        return "", []
    first = words_deva[0]
    combined = resolve_compound(first)[0] if "ऽ" in first else first
    rules = []
    for w in words_deva[1:]:
        # resolve_w1_compound=False: `combined` is running chained text, not
        # a fresh Pada-patha word -- it can legitimately contain an
        # elision-avagraha from an EARLIER join in this same chain (ordinary
        # Sanskrit orthography, e.g. "suunave"+"agne" -> "suunave'gne"),
        # which must not be misread as a Pada-patha compound to resolve
        # (a real bug found 11 Sep 2026 -- see samhita_join's docstring).
        r = samhita_join(combined, w, resolve_w1_compound=False)
        combined = r["surface"]
        rules.append(r["rule"])
    # combined still carries any ZWNJ markers needed to survive the loop
    # above (see _finish_consonant_then_vowel) -- this return value IS the
    # final output (nothing re-joins it further), so strip them here, once.
    return strip_zwnj_markers(combined), rules


def samhita_join(w1_deva, w2_deva, w1_is_pragrhya=False, resolve_w1_compound=True):
    """Compute the samhita-patha rendering of the pair (w1, w2), both given
    as bare (unaccented is fine, accented is stripped) Devanagari pada
    words. Returns dict: surface (Devanagari), rule (short id),
    confidence ("high"/"low"), note.

    w1_is_pragrhya: if true (per pratishakhya_classify.is_pragrhya), vowel
    sandhi is suppressed for w1's final vowel (10.20/Paatala-1's pragrhya
    definition -- a pragrhya word's vowel does not combine with what
    follows).

    resolve_w1_compound: True (default) is correct for w1 = a single bare
    Pada-patha word that may itself be an avagrhya compound (e.g.
    "puraH-hitam") -- this is what krama_engine.py's ordinary per-pair use
    needs. Pass False when w1 is NOT a single pada word but an
    already-sandhi'd, possibly multi-word chain (e.g. building up a whole
    ardharca's continuous text by repeated joining): a real bug, found
    11 Sep 2026 while adding chain-reconstruction validation, is that such
    a chain can legitimately contain an avagraha of its OWN -- inserted by
    THIS module's own a-class/eng-class vowel-elision rules to mark an
    elided word-medial 'a' (ordinary Sanskrit orthography, e.g.
    "suunave"+"agne" -> "suunave'gne") -- which resolve_compound() then
    misreads as a Pada-patha compound-split marker, incorrectly collapsing
    every space in the ENTIRE chain built so far. resolve_compound() is
    only valid on a genuine single Pada-patha word; running it on running
    prose text is a category error, not a second legitimate use."""
    if resolve_w1_compound and "ऽ" in w1_deva:
        w1_deva = resolve_compound(w1_deva)[0]
    if "ऽ" in w2_deva:
        w2_deva = resolve_compound(w2_deva)[0]
    s1 = transliterate_word(w1_deva)
    s2 = transliterate_word(w2_deva)
    if not s1 or not s2:
        return {"surface": w1_deva + w2_deva, "rule": "empty_input", "confidence": "low",
                "note": "empty word passed to samhita_join"}

    agama_match = SHAUDDHAKSHARA_AGAMA_SLP1.get((s1, s2))
    if agama_match:
        return _finish(agama_match, "shauddhakshara_agama_11_43", w1_deva, w2_deva,
                        note="Closed lexical zuddhaakSara-sandhi aagama example, sourced "
                             "directly from Uvata's bhaashya on 11.43 (see "
                             "SHAUDDHAKSHARA_AGAMA_SLP1).")

    if s1 in NATVA_BOUNDARY_UPASARGAS_SLP1 and s2[0] == "n" and len(s2) > 1 and s2[1] in ALL_VOWELS:
        # Trigger-and-intervener check per Paanini 8.4.1/8.4.2, scanning s1
        # from its end for r/f/F/z with only vowels between it and s1's own
        # end (aT is the only intervener class this closed upasarga set
        # actually needs -- "pra" itself never has ku/pu/aaN/num between the
        # r and the boundary, so those classes are not implemented here;
        # a future addition to NATVA_BOUNDARY_UPASARGAS_SLP1 that needs them
        # would have to extend this).
        trigger_pos = -1
        for i in range(len(s1) - 1, -1, -1):
            if s1[i] in ("r", "f", "F", "z"):
                trigger_pos = i
                break
        if trigger_pos != -1 and all(ch in ALL_VOWELS for ch in s1[trigger_pos + 1:]):
            natva_s2 = "R" + s2[1:]
            return _finish(s1 + " " + natva_s2, "natva_boundary_11_23", w1_deva, w2_deva,
                            note="Exact RPr 11.23/Uvata boundary case (pra + naH -> pra NaH); "
                                 "NOT a general tag-free natva-at-a-distance rule -- see "
                                 "NATVA_BOUNDARY_UPASARGAS_SLP1's own docstring.")

    lengthening_match = _match_lexical_suffix(s1, IRREGULAR_LENGTHENING_BEFORE_CONSONANT)
    if lengthening_match and s2[0] not in ALL_VOWELS:
        prefix, key = lengthening_match
        lengthened = prefix + IRREGULAR_LENGTHENING_BEFORE_CONSONANT[key]
        return _finish(lengthened + " " + s2, "irregular_lengthening_lexical_exception", w1_deva, w2_deva,
                        note=f"{key} is a known lexical exception with an attested lengthened "
                             "vowel before this word (see IRREGULAR_LENGTHENING_BEFORE_CONSONANT).")

    visarga_match = _match_lexical_suffix(s1, IRREGULAR_VISARGA_STEMS)
    if visarga_match and s2[0] in VOICED_CONSONANTS:
        prefix, key = visarga_match
        base = prefix + IRREGULAR_VISARGA_STEMS[key]  # already ends in "r", attaches directly
        return _finish(base + s2, "irregular_visarga_lexical_exception", w1_deva, w2_deva,
                        note=f"{key} is a known lexical exception to the regular a-class "
                             "visarga-before-voiced rule (see IRREGULAR_VISARGA_STEMS).")

    last1 = s1[-1]
    first2 = s2[0]

    # --- word-final visarga (H) ---
    if last1 == "H":
        stem = s1[:-1]
        prev_vowel = stem[-1] if stem else ""
        # sa/eSa special exception: visarga drops before ANY sound, no
        # o/r conversion. (Paninian: an irregular, specially legislated
        # sandhi for these two pronouns.)
        if stem in ("sa", "eza", "eSa"):
            # Irregular, specially-legislated sandhi for these two
            # pronouns: the visarga drops WITHOUT triggering any further
            # vowel sandhi with what follows (unlike an ordinary a-final
            # word) -- "saH" + "it" -> "sa it", not "set" (which plain a+i
            # guna would otherwise give).
            return _finish(stem + " " + s2, "visarga_sa_esa_elision_blocks_further_sandhi",
                            w1_deva, w2_deva)

        if prev_vowel in ("i", "I", "u", "U"):
            # i/u-class visarga: before ANY vowel -> r (attaches directly,
            # no space, but rendered as an independent vowel after a bare
            # r -- see _finish_consonant_then_vowel); before
            # an unvoiced sibilant it can assimilate to the sibilant
            # itself (approximated here: visarga kept, flagged low-
            # confidence); before an unvoiced NON-sibilant consonant, the
            # visarga simply stays (e.g. agniH + puurvebhiH -> agniH
            # puurvebhiH, visarga unchanged, space kept); before any other
            # voiced consonant -> r, attaching directly.
            if first2 in ALL_VOWELS:
                return _finish_consonant_then_vowel(
                    stem + "r", s2, "visarga_iu_class_before_vowel", w1_deva, w2_deva)
            if first2 in SIBILANTS_UNVOICED:
                return _finish(stem + "H " + s2, "visarga_iu_class_before_sibilant_unresolved",
                                w1_deva, w2_deva, confidence="low",
                                note="i/u-class visarga before an unvoiced sibilant can assimilate "
                                     "to the sibilant itself in some environments; this engine keeps "
                                     "the visarga rather than guess the assimilated form.")
            if first2 in UNVOICED_CONSONANTS:
                return _finish(stem + "H " + s2, "visarga_iu_class_before_unvoiced_consonant", w1_deva, w2_deva)
            return _finish(stem + "r" + s2, "visarga_iu_class_before_voiced_consonant", w1_deva, w2_deva)

        if prev_vowel in ("e", "E", "o", "O"):
            # diphthong-class visarga behaves like i/u-class.
            if first2 in ALL_VOWELS:
                return _finish_consonant_then_vowel(
                    stem + "r", s2, "visarga_diphthong_class_before_vowel", w1_deva, w2_deva)
            if first2 in VOICED_CONSONANTS:
                return _finish(stem + "r" + s2, "visarga_diphthong_class_before_voiced_consonant", w1_deva, w2_deva)
            return _finish(stem + "H " + s2, "visarga_diphthong_class_before_unvoiced", w1_deva, w2_deva)

        if prev_vowel in ("a", "A"):
            # a/a-class visarga: aH -> o before voiced (incl. vowel) --
            # the "a" of aH is REPLACED by "o", not kept alongside it; if
            # the following vowel is specifically 'a' it further elides
            # (marked with an avagraha); before an unvoiced STOP, visarga
            # assimilates to the sibilant of that stop's own varga
            # (c/C-varga -> S, T/W-varga -> z, t/T-varga -> s); before k/K/
            # p/P it stays aH.
            base = stem[:-1]  # drop the "a"/"A" that combines with visarga into "o"
            if first2 == "a":
                rest2 = s2[1:]
                return _finish(base + "o'" + rest2, "visarga_a_class_before_a_elided", w1_deva, w2_deva)
            if first2 in ALL_VOWELS or first2 in VOICED_CONSONANTS:
                return _finish(base + "o " + s2, "visarga_a_class_before_voiced", w1_deva, w2_deva)
            if first2 in ("c", "C"):
                return _finish(stem[:-1] + "aS" + s2, "visarga_a_class_sibilant_assimilation_palatal",
                                w1_deva, w2_deva)
            if first2 in ("w", "W"):
                return _finish(stem[:-1] + "az" + s2, "visarga_a_class_sibilant_assimilation_retroflex",
                                w1_deva, w2_deva)
            if first2 in ("t", "T"):
                return _finish(stem[:-1] + "as" + s2, "visarga_a_class_sibilant_assimilation_dental",
                                w1_deva, w2_deva)
            return _finish(stem + "H " + s2, "visarga_a_class_before_unvoiced_velar_labial", w1_deva, w2_deva)

        # visarga after some other vowel (e/o/ai/au-final stems are rare
        # here) -- not modelled precisely; keep as-is, flagged.
        return _finish(s1 + " " + s2, "visarga_unhandled_context", w1_deva, w2_deva,
                        confidence="low", note="visarga after a vowel this engine doesn't classify")

    # --- word-final m ---
    if last1 == "m":
        if first2 in ALL_VOWELS:
            return _finish(s1 + s2, "m_before_vowel_unchanged", w1_deva, w2_deva)
        return _finish(s1[:-1] + "M " + s2, "m_before_consonant_anusvara", w1_deva, w2_deva)

    # --- word-final n (Vedic nasalization before a vowel) ---
    if last1 == "n":
        if first2 in ALL_VOWELS:
            # Vedic recitation convention: certain final-n forms (esp.
            # accusative plural -an) show as nasalization of the preceding
            # vowel rather than plain consonant+vowel union before a
            # following vowel. Flagged low-confidence: this is a real,
            # specific phenomenon this engine approximates rather than
            # derives from the actual Nati/Dhvanyagama Paatalas (5-6),
            # which are out of scope here (see module docstring).
            stem = s1[:-1]
            return _finish(stem + "~ " + s2, "n_before_vowel_vedic_nasalization_approximated",
                            w1_deva, w2_deva, confidence="low",
                            note="Approximates the Vedic n-before-vowel nasalization convention "
                                 "(e.g. devān + aa -> devaam-with-candrabindu) without deriving it "
                                 "from Paatala 5/6, which are out of scope for this pass.")
        return _finish(s1 + " " + s2, "n_before_consonant_unchanged", w1_deva, w2_deva)

    # --- word-final t ---
    if last1 == "t":
        if first2 in ALL_VOWELS:
            return _finish(s1[:-1] + "d" + s2, "t_before_vowel_voiced", w1_deva, w2_deva)
        if first2 in ("d", "D", "g", "G", "b", "B", "j", "J"):
            return _finish(s1[:-1] + first2 + s2, "t_assimilates_to_following_voiced", w1_deva, w2_deva)
        return _finish(s1 + s2, "t_before_unvoiced_unchanged", w1_deva, w2_deva)

    # --- word-final simple vowel, pragrhya check first ---
    if last1 in ALL_VOWELS:
        if w1_is_pragrhya:
            if first2 == "a":
                return _finish(s1 + "'" + s2[1:], "pragrhya_no_sandhi_a_elided", w1_deva, w2_deva)
            return _finish(s1 + " " + s2, "pragrhya_no_sandhi", w1_deva, w2_deva)
        if first2 in ALL_VOWELS:
            if last1 in DIPHTHONGS:
                # e/o/ai/au + vowel: eNaH padantaad ati (a specifically
                # elides with avagraha, Panini 6.1.109) for the +a case.
                # For any OTHER following vowel, Panini 6.1.78
                # (eco'yavAyAvaH) REPLACES the diphthong itself with
                # a/a/A/A + the glide (e->ay, o->av, ai/E->Ay, au/O->Av) --
                # a real bug, found via external review 11 Sep 2026 and
                # confirmed against standard Paninian grammar (not
                # dependent on either reviewer's say-so): this branch used
                # to keep last1 UNCHANGED and merely append the glide
                # after it (e.g. "vane"+"indraH" -> "vaneyindraH", an
                # extra vowel that shouldn't be there), instead of
                # replacing it (correct: "vanayindraH"). Confirmed by
                # reproducing the bug directly before fixing it.
                if first2 == "a":
                    return _finish(s1 + "'" + s2[1:], "eng_a_class_before_a_elided", w1_deva, w2_deva)
                replacement = {"e": "ay", "E": "Ay", "o": "av", "O": "Av"}[last1]
                return _finish(s1[:-1] + replacement + s2, "eng_a_class_before_other_vowel", w1_deva, w2_deva)
            joined = join_vowel_vowel(last1, first2)
            if joined:
                result, rule = joined
                return _finish(s1[:-1] + result + s2[1:], rule, w1_deva, w2_deva)
            return _finish(s1 + " " + s2, "vowel_vowel_unhandled", w1_deva, w2_deva,
                            confidence="low", note="vowel pair this engine doesn't classify")
        return _finish(s1 + " " + s2, "vowel_before_consonant_unchanged", w1_deva, w2_deva)

    # --- other word-final consonants: default, no change, just join with space ---
    return _finish(s1 + " " + s2, "consonant_before_anything_default", w1_deva, w2_deva)


def _finish(slp1_result, rule, w1_deva, w2_deva, confidence="high", note=""):
    deva = slp1_to_deva(slp1_result)
    return {"surface": deva, "rule": rule, "confidence": confidence, "note": note,
            "w1": w1_deva, "w2": w2_deva}


def _finish_consonant_then_vowel(prefix_slp1, suffix_slp1, rule, w1_deva, w2_deva):
    """Like _finish, but for cases where prefix_slp1 ends in a BARE
    consonant (typically a visarga->r insertion) immediately before
    suffix_slp1.

    IMPORTANT CORRECTION (a second external review round, 11 Sep 2026,
    correctly rejected an earlier claim -- made in an even earlier version
    of this docstring -- that vocalic-r/rr (f/F) is "uniquely" ambiguous
    here): the underlying SLP1 collision (a bare consonant + independent
    vowel letter transliterates identically to that consonant + a
    DEPENDENT vowel-matra) is verified to hold for EVERY vowel class, not
    only f/F -- see tests/test_krama_engine.py's
    SLP1BareConsonantVowelCollision.test_collision_exists_for_every_vowel_class_not_only_vocalic_r.
    So f/F is not special because it is uniquely ambiguous at the
    transliteration level; every vowel is equally ambiguous there.

    What f/F actually IS special for: DGE's own attested Samhita-patha
    text, checked character-by-character (not assumed) for every real
    example available in this project's data, shows the INDEPENDENT-
    letter rendering is the one actually used ONLY for vocalic r/rr in
    this environment ("पूर्वेभिर्ऋषिभिः" -- bare र्, then independent ऋ,
    U+090B, not the dependent matra U+0943). The two other real examples
    available (both from RV 1.1.2) show the DEPENDENT-matra form instead:
    "र्+ई" -> "री" (dependent ी, not independent ई) and "र्+उ" -> "रु"
    (dependent ु, attested "नूतनैरुत", not independent उ) -- i.e. this
    module's ordinary default behaviour (concatenate as one SLP1 string,
    let the library render the dependent matra) is ALREADY correct for
    those, confirmed against real text, not merely untested. This is a
    real (if limited -- only 3 attested data points, all from RV 1.1.2)
    Devanagari TYPESETTING fact specific to vocalic r/rr's dependent-matra
    glyph (likely because ृ is small and easily missed, especially under
    Vedic accent marks, while ि/ी/ु/ू/े/ो are visually larger), not an
    SLP1-level fact -- see tests/test_krama_engine.py's
    SLP1BareConsonantVowelCollision class for the full reasoning and both
    verifications. If a future example is found where another vowel class
    ALSO needs the independent-letter form, extend this function's
    condition then, backed by that reproduced case -- do not extend it
    speculatively without one.

    A ZWNJ is inserted at the boundary (external review, 11 Sep 2026):
    without it, this correct Devanagari output, if fed back into
    samhita_join a second time (reconstruct_chain() does exactly this),
    gets re-transliterated to SLP1 as one flat "rf"/"rF" and can render
    back WRONG (as the dependent-matra reading) on that second pass --
    confirmed as a real bug before this fix, and confirmed the ZWNJ
    survives 10 consecutive re-joins, checked after every individual join
    not just the final one (a second review round's stronger test).
    See strip_zwnj_markers() -- callers that will not re-join this string
    further must call it."""
    if suffix_slp1[0] not in ("f", "F"):
        return _finish(prefix_slp1 + suffix_slp1, rule, w1_deva, w2_deva)
    deva = slp1_to_deva(prefix_slp1) + ZWNJ + slp1_to_deva(suffix_slp1)
    return {"surface": deva, "rule": rule, "confidence": "high", "note": "",
            "w1": w1_deva, "w2": w2_deva}


if __name__ == "__main__":
    # quick self-check against a handful of RV 1.1 pairs
    cases = [
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
    n_ok = 0
    for w1, w2, expected in cases:
        r = samhita_join(w1, w2)
        ok = r["surface"] == expected
        n_ok += ok
        print(f"{'OK ' if ok else 'FAIL'} {w1}+{w2} -> {r['surface']!r} (expected {expected!r}) [{r['rule']}]")
    print(f"{n_ok}/{len(cases)} passed")
