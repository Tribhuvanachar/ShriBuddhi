#!/usr/bin/env python3
"""The actual Krama generator: computes Krama-patha from raw Pada-patha
words using sanskrit_phonology.samhita_join (a real sandhi engine) and
pratishakhya_classify's predicates, rather than looking up precomputed
pair strings. Built in direct response to the reviewed spec (11 Sep
2026) that identified the previous generator as a hand-aligned
reconstruction, not a generator.

Pipeline per ardharca (matches
dge/RV_PRATISHAKHYA_KRAMA_ARCHITECTURE.md sec.5's diagram, for the slice
of it this pass actually implements -- Patala 1-2/4 phonology plus
Patala 10's structural/Parigraha rules; Patala 3 accent, 5-9 Nati/
Dhvanyagama/Pluti, and most of Patala 11 remain future work, not silently
assumed done):

    Pada words
        -> sutra 10.3 monosyllable-exception detection (special pattern)
        -> sutra 10.2 base pairing, via samhita_join (real sandhi)
        -> sutra 10.7-10.9 Parigraha trigger detection (requires_parigraha)
        -> sutra 10.12-10.16 sthita/upasthita/sthitopasthita rendering
        -> Krama output, every unit citing which rule(s) fired

Every unit dict carries THREE independent, non-substitutable signals (per
the 11 Sep 2026 review of the first regenerated-output run, which found
"confidence" alone was being read as if it meant "verified correct" --
it never did, and conflating them is exactly the failure mode flagged):

  "status": "canonical" (produced by applying the general rule engine
      uniformly to this word sequence) vs "candidate_reconstruction"
      (this session's own generalization of a SINGLE cited worked example
      -- currently only sutra 10.3's units -- never independently
      confirmed against a second source). A consumer that wants only
      source-confirmed output filters on this field.
  "confidence" ("high"/"low", set by sanskrit_phonology.samhita_join):
      how sure the PHONOLOGICAL RULE CLASSIFIER is that it picked the
      right branch for this segmental context. This says nothing about
      whether the resulting Vedic form is independently attested.
  "chain_reconstruction" (added per-ARDHARCA, not per-unit, by
      tools/pratishakhya/regenerate_krama_rv_1_1.py as a VALIDATE-mode
      pass, not by this module): whether folding samhita_join across the
      WHOLE ardharca reproduces DGE's own attested continuous
      samhita_patha for it. This is a real, checkable fact about the
      phonology engine, but it is NOT proof of philological correctness
      either -- reproducing DGE's own Samhita only shows internal
      self-consistency with this repo's other data, not agreement with an
      attested Krama-patha edition (still an open question -- see the
      architecture doc sec.10). It is deliberately per-ardharca rather
      than per-unit: an individual Krama pair is computed against only
      its immediate neighbour, but that word's form in the continuous
      chain often depends on a LATER neighbour too, so per-unit
      substring-matching against continuous text produces false
      mismatches (a real mistake made and then fixed in this session --
      see regenerate_krama_rv_1_1.py's own module docstring).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sanskrit_phonology import samhita_join, resolve_compound, transliterate_word, strip_zwnj_markers  # noqa: E402
from pratishakhya_classify import (  # noqa: E402
    is_pragrhya, is_monosyllable_avasana, parse_compound,
    requires_parigraha, get_sthitopasthita, detect_bahumadhyagata,
)


# Manual overrides for split_into_ardharcas(), used only where checked
# directly against DGE's own attested samhita_patha and found to differ
# from the automatic (marginal-sandhi-length) detector's output -- not
# fabricated, and each is logged, not silently substituted. On RV 1.1
# specifically, the detector gets 7 of 9 verses right on its own (see
# tools/pratishakhya/validate_krama_rv1_1.py); these two are the
# exceptions, most likely because the samhita_join length delta for a
# consonant-cluster/compound-heavy pair here doesn't match the actual
# printed samhita's own choices closely enough for length-matching alone.
ARDHARCA_SPLIT_OVERRIDES = {
    "1.1.7": 7,
    "1.1.9": 7,
}


def split_into_ardharcas(verse_id, pada_words, samhita_patha_stripped):
    """Splits pada_words into [ardharca1_words, ardharca2_words] using
    DGE's own attested samhita_patha as an alignment oracle: the sandhi
    engine's own per-pair length deltas are summed to find which pada-
    word-boundary's cumulative samhita length is closest to the position
    of the first danda in the real samhita text. This uses the ATTESTED
    text only to find a STRUCTURAL boundary, not to look up the pair
    content itself (samhita_join still computes every pair independently
    -- see krama_engine.py's own docstring on this distinction)."""
    if verse_id in ARDHARCA_SPLIT_OVERRIDES:
        n1 = ARDHARCA_SPLIT_OVERRIDES[verse_id]
        return [pada_words[:n1], pada_words[n1:]], "manual_override"

    danda_pos = samhita_patha_stripped.index("।") if "।" in samhita_patha_stripped else len(samhita_patha_stripped)
    target_len = len(samhita_patha_stripped[:danda_pos].replace(" ", ""))
    cum = len(pada_words[0])
    cum_lens = [cum]
    for i in range(1, len(pada_words)):
        pair = samhita_join(pada_words[i - 1], pada_words[i])
        # strip_zwnj_markers: this length calc is a final consumer (not a
        # re-join), and ZWNJ is a real character for len() purposes even
        # though it renders zero-width -- left in, it would throw off the
        # length-alignment heuristic by one character wherever it occurs.
        surface = strip_zwnj_markers(pair["surface"])
        delta = len(surface.replace(" ", "")) - len(pada_words[i - 1])
        cum += delta
        cum_lens.append(cum)
    n1 = min(range(len(cum_lens)), key=lambda i: abs(cum_lens[i] - target_len)) + 1
    return [pada_words[:n1], pada_words[n1:]], "automatic_length_alignment"


# Named trigger reasons for 10.9's own citation list, so a consumer can
# ask "why did this word get Parigraha" without parsing the "rule" list's
# sutra-number strings -- a real gap the 11 Sep 2026 review pointed out
# (point 15: reasons were flattened into an undifferentiated rule-number
# list). One-to-one with pratishakhya_classify.requires_parigraha's own
# reasons vocabulary ("10.7"/"10.8"/"10.9"); kept as a separate mapping
# here rather than changing that module's return shape, since its reasons
# ARE the sutra citations and are correct as such -- this is presentation,
# not a second source of truth.
_TRIGGER_REASON_LABELS = {
    "10.7": "avagrhya_compound",
    "10.8": "bahumadhyagata",
    "10.9": "ardharca_final",
}


def _parigraha_unit(word_deva, reasons):
    compound = parse_compound(word_deva)
    combined_form = strip_zwnj_markers(resolve_compound(word_deva)[0]) if compound["is_compound"] else word_deva
    # apply_sandhi=False only when this module can independently confirm
    # pragrhya status from is_pragrhya()'s own (context-free) lexical
    # check -- see get_upasthita()'s docstring for why pragrhya words are
    # the one case that must NOT take ordinary word+iti sandhi. This is a
    # real, stated limitation: is_pragrhya() called without context misses
    # the morphological/contextual classes (dual, vocative), so a Parigraha
    # word that's pragrhya for one of THOSE reasons will still (incorrectly)
    # get sandhi applied here -- no case actually exercised by this engine
    # yet needs that context, so not silently working around it.
    word_pragrhya, _ = is_pragrhya(word_deva)
    text = get_sthitopasthita(word_deva, combined_form, apply_sandhi=not word_pragrhya)
    return {
        "type": "parigraha",
        "text": text,
        "for_word": word_deva,
        "rule": reasons + ["10.14"],
        "status": "canonical",
        "trigger_reasons": [_TRIGGER_REASON_LABELS.get(r, r) for r in reasons],
        # Every Parigraha unit this engine currently produces renders as
        # sthitopasthita (10.14: combined/sthita form + iti + split/upasthita
        # form together) -- Uvata's own worked example on 10.14. sthita
        # (10.12) and upasthita (10.13) alone, as DISTINCT renderings rather
        # than components of sthitopasthita, are not yet exercised by any
        # case this engine has actually needed -- get_sthita/get_upasthita
        # exist in pratishakhya_classify.py but nothing here calls them
        # standalone. Stated explicitly rather than left implicit in which
        # function happened to be called (11 Sep 2026 review point 3).
        "retake_state": "STHITOPASTHITA",
        "confidence": "medium",
        "note": "Word+iti+word given with no sandhi between the components, per Uvata's "
                "own worked example on 10.14 ('vibhaavaso iti vibhaavaso').",
    }


def generate_ardharca(words, bahumadhyagata_positions=None):
    """words: list of bare Devanagari pada words for one ardharca (no
    accents needed -- they're stripped by the phonology layer anyway).
    bahumadhyagata_positions: optional override; if omitted (None), this is
    computed automatically via pratishakhya_classify.detect_bahumadhyagata()
    (10.8's own closed particle class -- ca/vA/cit -- see that function's
    docstring for what it does and does not cover). Pass an explicit set,
    including the empty set, to bypass auto-detection.

    Returns a list of unit dicts, in recitation order.
    """
    if bahumadhyagata_positions is None:
        bahumadhyagata_positions = detect_bahumadhyagata(words)
    n = len(words)
    units = []
    i = 0
    while i < n - 1:
        w1, w2 = words[i], words[i + 1]

        # sutra 10.3: if the word we are ABOUT to retake (w1, at position i)
        # was itself the monosyllable-exception word from having just been
        # introduced as the SECOND element of the previous pair, the
        # ordinary retake-pair (w1, w2) is replaced by a tri-unit
        # (w1, AA, w2) plus a confirming pair (AA, w2), per Uvata's own
        # example on 10.3 ("aa mandram | mandram-aa vareNyam | aa
        # vareNyam" -- reconstructed from that example, not copied from
        # an attested edition of these specific verses; see
        # KRAMA_VERIFICATION_PACKET.md).
        if i > 0 and is_monosyllable_avasana(words[i - 1]) and not is_monosyllable_avasana(w1):
            aa = words[i - 1]
            tri_join = samhita_join(w1, aa)
            second_join = samhita_join(aa, w2)
            # samhita_join(w1,aa) already gives "w1-combined-with-aa"; append w2 plainly
            # (w2 keeps its own bare form here since it's the true next word, not yet
            # itself sandhi-joined to aa in this tri-unit's first component).
            units.append({
                "type": "monosyllable_retake_tri_unit",
                "text": f"{strip_zwnj_markers(tri_join['surface'])} {w2}",
                "rule": ["10.3", tri_join["rule"]],
                "confidence": "low",
                # Not canonical output: this is this session's own generalization
                # of a single worked example to whatever position it structurally
                # matches, never independently confirmed against an attested
                # Krama edition or a second commentarial source. A consumer that
                # wants only source-confirmed output must filter this status out
                # rather than treat "type" or "confidence" alone as the gate
                # (11 Sep 2026 review point 5: an unresolved philological question
                # must not silently become executable, unflagged behaviour).
                "status": "candidate_reconstruction",
                "note": "Reconstructed pattern for sutra 10.3's monosyllable exception "
                        "(this session's own reading of Uvata's example, not an attested "
                        "source for THIS verse) -- see KRAMA_VERIFICATION_PACKET.md.",
            })
            units.append({
                "type": "monosyllable_confirm_pair",
                "text": strip_zwnj_markers(second_join["surface"]),
                "rule": ["10.3", second_join["rule"]],
                "confidence": "low",
                "status": "candidate_reconstruction",
                "note": "Reconstructed pattern for sutra 10.3 -- see KRAMA_VERIFICATION_PACKET.md.",
            })
            # 10.3 replaces the ordinary retake-PAIR, but 10.9 (ardharca-final
            # Parigraha) is an independent condition on w2's position -- it must
            # still be checked here, or the last word of an ardharca that happens
            # to fall in this special-case branch silently loses its Parigraha.
            needs_parigraha, reasons = requires_parigraha(
                w2, i + 1, n, is_bahumadhyagata=(i + 1) in bahumadhyagata_positions
            )
            if needs_parigraha:
                units.append(_parigraha_unit(w2, reasons))
            i += 1
            continue

        w1_pragrhya, _ = is_pragrhya(w1)
        pair = samhita_join(w1, w2, w1_is_pragrhya=w1_pragrhya)
        units.append({
            "type": "pair",
            "text": strip_zwnj_markers(pair["surface"]),
            "rule": "10.2",
            "phonology_rule": pair["rule"],
            "status": "canonical",
            "confidence": pair["confidence"],
            "note": pair["note"],
        })

        needs_parigraha, reasons = requires_parigraha(
            w2, i + 1, n, is_bahumadhyagata=(i + 1) in bahumadhyagata_positions
        )
        if needs_parigraha:
            units.append(_parigraha_unit(w2, reasons))

        i += 1

    return units


def generate_verse(ardharcas, bahumadhyagata_positions=None):
    """ardharcas: list of word-lists (one per ardharca). No sandhi crosses
    an ardharca boundary (sutra 10.18) -- enforced structurally here by
    processing each ardharca independently and never joining across.
    bahumadhyagata_positions, if omitted, is auto-detected independently
    per ardharca (see generate_ardharca's docstring) since positions are
    indices into each ardharca's own word list."""
    return [generate_ardharca(words, bahumadhyagata_positions) for words in ardharcas]


if __name__ == "__main__":
    print("=== Test A: ordinary pairing ===")
    units = generate_ardharca(["अग्निम्", "ईळे"])
    for u in units:
        print(u["type"], "|", u["text"], "|", u["rule"])

    print("\n=== Test B+C: RV 1.1.1 ardharca 1 (compound Parigraha + ardharca-final) ===")
    units = generate_ardharca(["अग्निम्", "ईळे", "पुरःऽहितम्", "यज्ञस्य", "देवम्", "ऋत्विजम्"])
    for u in units:
        print(u["type"], "|", u["text"], "|", u["rule"])

    print("\n=== Test D: sutra 10.3 monosyllable (reconstructed pattern) ===")
    units = generate_ardharca(["आ", "मन्द्रम्", "वरेण्यम्"])
    for u in units:
        print(u["type"], "|", u["text"], "|", u["rule"])

    print("\n=== Test G: sutra 10.8 bahumadhyagata, auto-detected (Uvata's 'narA ca zaMsam') ===")
    units = generate_ardharca(["नरा", "च", "शंसम्", "दैव्यम्"])
    for u in units:
        print(u["type"], "|", u["text"], "|", u["rule"])
