#!/usr/bin/env python3
"""Predicate classifiers for the Krama engine: is_pragrhya, is_rephi,
requires_parigraha, avagraha/compound segmentation, and the sutra 10.3
monosyllable-exception detector.

Built as functions taking (token, context), not flat lookup tables, per
the reviewed spec (11 Sep 2026): "the existing Gemini design used a flat
dictionary. That is insufficient because Pragrhya is partly contextual."
A dictionary is still used as a CACHE inside each function for the closed
lexical classes (Panini/Paatala-1 name specific words), never as the
definition itself.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sanskrit_phonology import (  # noqa: E402
    transliterate_word, ALL_VOWELS, DIPHTHONGS, samhita_join, strip_zwnj_markers,
)

# Paatala 1's closed pragrhya lexical class (asme, yuSme, tve, amii and
# their like) plus the dual-in-ii/uu/e morphological class -- see
# dge/RV_PRATISHAKHYA_KRAMA_ARCHITECTURE.md sec.6.1 for why this must stay
# a predicate, not a flat list: the morphological/contextual classes below
# are NOT lexical and cannot be enumerated.
PRAGRHYA_LEXICAL_SLP1 = {"asme", "yuzme", "tve", "amI", "amU"}


def is_pragrhya(token_deva, context=None):
    """context, when given, is a dict that may carry {"is_dual": bool,
    "is_amantrita": bool} for the morphological/contextual classes this
    predicate still needs a caller to supply (this module cannot itself
    parse full nominal morphology -- that is a real, separate gap, not
    silently assumed away: see the False-returning fallback's note)."""
    s = transliterate_word(token_deva)
    if s in PRAGRHYA_LEXICAL_SLP1:
        return True, "lexical (Paatala 1 closed class: asme/yuSme/tve/amI/amU)"
    if context:
        if context.get("is_dual") and s and s[-1] in ("I", "U", "e"):
            # dual nominal forms ending in -ii/-uu/-e are pragrhya
            # (Paatala 1's morphological class)
            return True, "morphological (dual ending in -ii/-uu/-e)"
        if context.get("is_amantrita") and s and s[-1] == "e":
            return True, "contextual (aamantrita vocative ending in -e)"
        if context.get("is_amantrita") and s and s[-1] == "o":
            # sutra 1.68 ("okAra AmantritajaH pragfhyaH" -- the vowel 'o'
            # arising from vocative is pragrhya), found missing from this
            # function entirely 11 Sep 2026 while fact-checking an external
            # citation (which itself cited the wrong sutra number, 1.74
            # instead of the correct 1.68, but the underlying substance
            # checked out against this project's own corpus). Gated on
            # is_amantrita, like the -e case above, because plenty of
            # non-vocative words also end in "o" (e.g. any a-class visarga
            # word after visarga_a_class_before_voiced) and are NOT
            # pragrhya for that reason -- this predicate still cannot
            # itself distinguish "vocative o" from "o that arose from
            # visarga sandhi" without the caller telling it which case it
            # is, same limitation as the existing amantrita-e check.
            return True, "contextual (aamantrita vocative ending in -o, sutra 1.68)"
    return False, "not matched (lexical/morphological/contextual checks all negative -- " \
                  "context-dependent classes not checked here return False if context " \
                  "wasn't supplied by the caller, not because they were ruled out)"


# Rephi: a cache of forms already confirmed rephita in this corpus (from
# krama_kramahetu_rules.json's 10.22/11.40-41 examples), NOT the
# definition -- the real condition (per 10.22) is phonological: a word
# whose visarga arose from an original word-final "r" (repha), tested
# against what FOLLOWS (an unvoiced sibilant keeps the repha-derived
# form; see krama_engine.py's use of this alongside samhita_join's own
# visarga rules, which don't independently know a given word's
# historical repha origin).
#
# Two entries had a real encoding bug (found 11 Sep 2026 while
# cross-checking sutra 11.43's own dhUHsadam/durdhyaH-style citations
# against transliterate_word()): "dh"/"DUH..." with a lowercase d is not
# valid SLP1 for dha (needs capital "D") -- "dhUHsadam"/"durdhyaH" could
# never match is_rephi("धूःसदम्")/is_rephi("दुर्ध्यः") and silently always
# returned False for them. Fixed to "DUHsadam"/"durDyaH" (verified against
# transliterate_word() directly, not just eyeballed) -- an encoding
# correction only, not a change to which word this entry represents.
REPHI_CACHE_SLP1 = {"svaScanAH", "DUHsadam", "pUHpatim", "duHnaSam", "durDyaH", "durlaBaH"}


def is_rephi(token_deva, left_context=None, right_context_slp1_first_char=None):
    """right_context_slp1_first_char: the first SLP1 character of the
    word that follows, needed because 10.22's rule is specifically about
    behaviour before an UNVOICED sibilant -- this predicate does not
    itself decide the phonological outcome (samhita_join does that); it
    only says whether the word belongs to the rephita class at all."""
    s = transliterate_word(token_deva)
    if s in REPHI_CACHE_SLP1:
        return True
    # Real phonological derivation of repha-origin from a bare surface
    # form alone is not reliable without etymological/paradigm
    # information this module doesn't have -- returning False here for
    # anything not in the cache is a known, stated limitation (see
    # module docstring), not a claim that the cache is exhaustive.
    return False


def parse_compound(token_deva):
    """Returns {"is_compound": bool, "segments": [...]} -- preserves
    structure rather than leaving an unexplained avagraha character in a
    plain string, per the reviewed spec sec.6.3."""
    if "ऽ" not in token_deva:
        return {"is_compound": False, "segments": [token_deva]}
    return {"is_compound": True, "segments": token_deva.split("ऽ")}


# sutra 10.3's monosyllable-exception class: single-syllable words that
# stop the ordinary Krama pairing chain rather than continuing forward in
# the usual way (Uvata's own examples: aa, aum). Kept as a small, named
# set -- this IS a closed lexical class per the sutra's own text (not a
# phonological pattern to derive), unlike is_pragrhya/is_rephi above.
MONOSYLLABLE_AVASANA_SLP1 = {"A", "oM", "auM"}


def is_monosyllable_avasana(token_deva):
    s = transliterate_word(token_deva)
    return s in MONOSYLLABLE_AVASANA_SLP1


def requires_parigraha(token_deva, position_in_ardharca, ardharca_length, is_bahumadhyagata=False):
    """position_in_ardharca: 0-based index. Returns (bool, reasons_list)
    where reasons_list cites which of 10.7 (avagrhya)/10.8 (bahumadhyagata,
    normally supplied by the caller via detect_bahumadhyagata() rather than
    parsed here)/10.9 (ardharca-final) fired."""
    reasons = []
    if parse_compound(token_deva)["is_compound"]:
        reasons.append("10.7")
    if is_bahumadhyagata:
        reasons.append("10.8")
    if position_in_ardharca == ardharca_length - 1:
        reasons.append("10.9")
    return bool(reasons), reasons


# sutra 10.8's own worked examples ("bahumadhyagata"): Uvata's bhaashya
# cites exactly three particles that sit "in the middle of many words" and
# each get their own Parigraha citation -- "ca iti ca" (narA ca zaMsam ->
# naraashaMsam), "cit iti cit" (zunaH cit zepam -> zunaHzepam), "vA iti vA"
# (narA vA zaMsam) -- plus a fourth example (mo Su NaH) this session could
# not confidently parse as the same pattern (see
# RV_PRATISHAKHYA_KRAMA_ARCHITECTURE.md's bahumadhyagata section) and is
# NOT included here. A small, named, source-cited closed class, like
# MONOSYLLABLE_AVASANA_SLP1 above -- not a general parse of "compound
# phrase membership" (this module still cannot do that; see
# detect_bahumadhyagata()'s own docstring).
BAHUMADHYAGATA_LEXICAL_SLP1 = {"ca", "vA", "cit"}


def detect_bahumadhyagata(words_deva):
    """Returns the set of 0-based indices in words_deva that sutra 10.8
    ("bahumadhyagatAni ca") requires Parigraha for: an occurrence of one of
    BAHUMADHYAGATA_LEXICAL_SLP1's particles that has a word on BOTH sides
    (Uvata's "bahUnAM padAnAM madhyagatAni" -- situated in the middle of
    several words -- is satisfied by having two neighbours at all, per the
    worked examples, which are all 3-word runs: narA ca zaMsam, zunaH cit
    zepam, narA vA zaMsam). A particle at either end of the word list has
    no "middle" position to occupy and is not covered by this sutra (it
    would be handled, if at all, by 10.7/10.9 like any other word).

    This is a real but NARROW derivation: it only recognizes the closed
    particle class Uvata's own examples name, not arbitrary multi-word
    compound-phrase membership in general (this module has no parser for
    that) -- see RV_PRATISHAKHYA_KRAMA_ARCHITECTURE.md for what's still
    open here (the "mo Su NaH" sub-case, which does not fit this pattern)."""
    positions = set()
    for i in range(1, len(words_deva) - 1):
        if transliterate_word(words_deva[i]) in BAHUMADHYAGATA_LEXICAL_SLP1:
            positions.add(i)
    return positions


def get_sthita(token_deva):
    """10.13: the bare word alone (its own pada-patha spelling, avagraha
    included if it's a compound -- 10.16's split-in-the-repeat form)."""
    return token_deva


def get_upasthita(token_deva, apply_sandhi=True):
    """10.12: word + iti. Ordinary sandhi (real samhita_join, not a fixed
    string template) applies between the word and iti UNLESS the word is
    pragrhya -- found 11 Sep 2026 by contrasting two of Uvata's own
    examples: 10.8's "ca iti ca" -> "cEti ca" (ordinary a+i->e guNa sandhi
    for the non-pragrhya particle ca) and 10.16's "purojitI iti" ->
    "purojitIti" (I+i->I sandhi for a non-pragrhya compound), against
    10.14's "vibhAvaso iti" (NO sandhi) and 10.12's "bAhU iti" (NO sandhi)
    -- both of those words ARE pragrhya (vibhAvaso: vocative -o, sutra
    1.68; bAhU: dual -U, Paatala 1's morphological class), which is
    exactly why pragrhya vowels are defined to resist external sandhi.
    Caller passes apply_sandhi=False when it has independently determined
    (via is_pragrhya(), usually with context this module can't supply on
    its own) that token_deva is pragrhya."""
    if not apply_sandhi:
        return f"{token_deva} इति"
    joined = samhita_join(token_deva, "इति")
    return strip_zwnj_markers(joined["surface"])


def get_sthitopasthita(token_deva, combined_form_deva=None, apply_sandhi=True):
    """10.14: sthita + upasthita given together. If the word is an
    avagrhya compound (10.16: the repeat shows the avagraha split),
    combined_form_deva should be supplied as the already-samhita-joined
    (non-split) rendering -- see krama_engine.py, which computes that via
    sanskrit_phonology.resolve_compound before calling this.

    Only the FIRST word+iti junction takes real sandhi (see
    get_upasthita()'s docstring for why, and apply_sandhi's meaning) --
    the second (repeated) occurrence is always the bare, unsandhied pada
    form, per 10.16's own point: the repeat is what SHOWS the split/pure
    form, so it must not itself be resandhied with the preceding iti (this
    matches every one of Uvata's own citations: "cEti ca" not "cEticaH",
    "purojitIti puraH-jitI" not a further-joined form)."""
    first_form = combined_form_deva if combined_form_deva else token_deva
    second_form = token_deva  # bare pada form, split if it's a compound (10.16)
    first_part = get_upasthita(first_form, apply_sandhi=apply_sandhi)
    return f"{first_part} {second_form}"


if __name__ == "__main__":
    tests = [
        ("अस्मे", True),
        ("अग्निम्", False),
        ("आ", None),  # not pragrhya; tested separately below for monosyllable
    ]
    for tok, expected in tests[:2]:
        ok, reason = is_pragrhya(tok)
        status = "OK" if ok == expected else "FAIL"
        print(f"{status} is_pragrhya({tok!r}) = {ok} ({reason})")
    print("is_monosyllable_avasana('आ') =", is_monosyllable_avasana("आ"))
    print("parse_compound('पुरःऽहितम्') =", parse_compound("पुरःऽहितम्"))
    print("requires_parigraha('पुरःऽहितम्', 2, 6) =", requires_parigraha("पुरःऽहितम्", 2, 6))
    print("requires_parigraha('ऋत्विजम्', 5, 6) =", requires_parigraha("ऋत्विजम्", 5, 6))
    print("get_sthitopasthita('पुरःऽहितम्', 'पुरोहितम्') =", get_sthitopasthita("पुरःऽहितम्", "पुरोहितम्"))
    print("get_sthitopasthita('च') [Uvata: 'cEti ca'] =", get_sthitopasthita("च"))
    print("get_sthitopasthita('विभावसो', apply_sandhi=False) [Uvata: 'vibhAvaso iti vibhAvaso'] =",
          get_sthitopasthita("विभावसो", apply_sandhi=False))
    print("detect_bahumadhyagata(['नरा', 'च', 'शंसम्']) =",
          detect_bahumadhyagata(["नरा", "च", "शंसम्"]))
