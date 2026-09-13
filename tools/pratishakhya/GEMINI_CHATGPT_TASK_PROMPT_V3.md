# Round 3 — scoped, code-only task prompt (Krama-pāṭha generator, Ṛgveda-Prātiśākhya)

Paste everything between `=== BEGIN PROMPT ===` / `=== END PROMPT ===` into ChatGPT or Gemini.
No repository access needed — every file this prompt refers to is embedded in full below.

=== BEGIN PROMPT ===

I'm building a computational Krama-pāṭha (Vedic word-repetition recitation) generator for the
Ṛgveda Śākala tradition, driven by the Ṛgveda-Prātiśākhya's own sūtras (Paṭala 10 = Krama,
Paṭala 11 = Kramahetu/rationale), not a hardcoded word list. Two previous rounds with you (or a
similar model) went reasonably well — I verified every claim myself before using it, caught a
couple of wrong citations, and shipped what checked out. This round is three NEW, narrower,
better-sourced tasks. Same hard rule as last time:

**HARD RULE FOR THIS ENTIRE RESPONSE: every claim must come with either (a) runnable Python I
can paste in and run against the test cases I give you, or (b) an exact quotation from the sūtra
text/bhāṣya I give you below, with your reasoning tied to the literal words of that quotation —
not a general appeal to "Sanskrit grammar typically..." If you are not confident about
something, say UNRESOLVED and state exactly what evidence would settle it. "You should add a
rule for X" with no actual code is not an acceptable answer — if you don't have a concrete patch,
say so explicitly.**

The three full source files this all lives in are appended at the very end of this prompt
(`sanskrit_phonology.py`, `pratishakhya_classify.py`, `krama_engine.py`) — read those before
answering, since your code must integrate with the existing function signatures, not invent new
ones where an equivalent already exists (e.g. don't reinvent `samhita_join`'s visarga handling;
extend it or add a new function that calls it).

---

## TASK A — sūtra 11.23 "yathāpadam sandhim apetahetuṣu" (restore the pre-sandhi Pada form when

the sandhi-triggering word is no longer adjacent)

**Sūtra text (Devanāgarī):** यथापदम् सन्धिम् अपेतहेतुषु।
**IAST:** yathāpadam sandhim apetahetuṣu.

**Worked example, from a prior careful reading of Uvaṭa's Bhāṣya (already in my corpus, marked
`"confidence": "high", "basis": "Uvata's Bhasya (via VedaVishtaram), cross-checked against the
sutra text itself"`, but NOT independently validated against an attested Krama-pāṭha edition):**

> "pra NaH" (प्र णः — प्र causes ण-retroflexion of the Pada-pāṭha word "नः") vs. "na indraḥ" (न
> इन्द्रः — without प्र adjacent, the plain "न" form, no retroflexion). Uvaṭa's own note: this
> clause exists specifically to remove any doubt (विलोप-संशय) about whether the retroflexion
> might persist even once its cause is gone.

**What this means concretely:** "नः" (Pada-pāṭha, plain दन्त्य न) sandhi-combines with a
PRECEDING "प्र" to surface as "प्र णः" in continuous Saṃhitā (ण-त्व / retroflexion-at-a-distance
— a real, general Pāṇinian phenomenon: a preceding र्/ऋ/ष् can retroflex a following न् to ण्
across intervening vowels and specific consonant classes, per Pāṇini 8.4.1 ff., UNLESS a
"व्यवाय" — an intervening sound of certain classes — blocks it). When "नः" is instead RETAKEN in
the Krama-pāṭha next to a DIFFERENT word (e.g. "इन्द्रः", which is not "प्र" and supplies no
retroflexion trigger), the Pada-pāṭha's own plain "न" form must be used, not "ण".

**A second, related worked example from the SAME bhāṣya passage (sūtra 10.8, which I already
partially implemented last round — see `detect_bahumadhyagata` in the appended
`pratishakhya_classify.py`), that I could NOT confidently fit into the same mechanism and did
NOT implement:**

> "मो षु णः" (Pada-pāṭha, per the bhāṣya's own resolution: "मो इति मो। सु इति सु।" — i.e. two
> separate Parigraha citations, "मो" retaken as "मो", and "सु" retaken as "सु", the second one
> **reverting the retroflexed "षु" back to its Pada form "सु"**).

**A1 — is this a special-case Pāṇinian rule I should implement narrowly (a closed function that
detects "word's Saṃhitā form differs from its Pada form due to a PRECEDING word's influence, and
that preceding word is absent in this specific Krama retake"), or does it require a general
ṇatva/retroflexion-at-a-distance implementation (Pāṇini 8.4.1–8.4.39-ish: त्, थ्, द्, ध्, न् 
after र्/ऋ/ष्, crossing over vowels and क-वर्ग/प-वर्ग consonants, but blocked by an intervening
palatal/retroflex/dental other than न् itself, and by a following pause)? If the latter, write
the general rule as Python (a function operating on the same kind of Devanāgarī bare-word inputs
`samhita_join` takes), cite the specific Pāṇini sūtra(s) for every clause of the rule (do not
approximate from memory — if you are not sure of the exact sūtra number or the exact blocking
conditions, say UNRESOLVED for that clause specifically, not for the whole task), and show it
passing ALL of these cases:**

```python
# Forward direction (ordinary Samhita, word this engine already HAS a plain n for):
# "pra" + "naH" -> should produce "pra NaH" (retroflexion fires)
# "na" alone retaken next to "indraH" (not "pra") -> should STAY "na indraH" (no retroflexion --
#   already true today since samhita_join has no natva rule of ANY kind yet, so nothing to
#   break, but this must remain true once you add the forward rule)

# Restoration direction (Krama Parigraha citing "naH" back after a DIFFERENT retake pairing):
# get_sthitopasthita("नः")  # in the context of being retaken next to "इन्द्रः", not "प्र"
# -> must give "न इति नः" or the correctly-sandhied equivalent (real sandhi per my Round-2 fix
#    below applies at the word+iti junction unless the word is pragrhya -- "नः" is NOT pragrhya)
#    -- NOT "ण इति नः" (the retroflexed form must not leak into the Parigraha citation once its
#    trigger is gone)
```

**A2 — the "मो षु णः" sub-case.** Is "सु"→"षु" here the SAME ण-त्व-type retroflexion
phenomenon (स्→ष् has an analogous, separate Pāṇinian rule — 8.3.59 "आदेशप्रत्यययोः" and the
"iṇkoḥ" environment, 8.3.57 ff. — also retroflexion-at-a-distance, but for स्→ष् not न्→ण्), or
something else entirely? If you can write the same kind of forward+restore Python for this case
too, with citations, do so. If not, say UNRESOLVED explicitly rather than guessing — I would
rather leave "मो षु णः" unimplemented than implement it wrong.

---

## TASK B — sūtra 11.43 "nudet ca śauddhākṣarasandhyam āgamam" (the śuddhākṣara-sandhi augment

is removed on Parigraha retake)

**Sūtra text:** नुदेत् च शौद्धाक्षरसन्ध्यम् आगमम्। ("nudet ca śauddhākṣarasandhyam āgamam" — "and
one should remove/expel the augment born of śuddhākṣara-sandhi [when doing Parigraha]")

**Uvaṭa's own worked examples (Bhāṣya on 11.43, my own corpus, direct quotation, not
paraphrased):**

> सुश्चन्द्र दस्म। सुचन्द्रेति सुचन्द्र। परिष्कृण्वन्ननिष्कृतम्। परिकृण्वन्निति परिकृण्वन्।
> धूर्षदं वनर्षदम्। धूःसदमिति धूःसदम्। वनसदमिति वनसदम्।।

Reading this: in continuous Saṃhitā recitation, "सुचन्द्र" surfaces with an inserted श् —
"सुश्चन्द्र दस्म" (an "augment born from śuddhākṣara-sandhi" at the सु+चन्द्र junction) — but its
Parigraha (Krama retake) citation must OMIT that augment: "सुचन्द्र इति सुचन्द्र", not
"सुश्चन्द्र इति सुचन्द्र". Same pattern for "परिकृण्वन्" (Saṃhitā "परिष्कृण्वन्", inserted ष्,
Parigraha "परिकृण्वन् इति परिकृण्वन्").

**B1 — what IS a "śuddhākṣara-sandhi āgama", precisely, in Pāṇinian terms?** Is this the same
phenomenon as **8.3.111 "śari"**-class स्/ष्-augment insertion (Ṛk-Prātiśākhya-specific,
sometimes glossed as an "s-āgama" inserted at certain vowel-stem + consonant-initial word
junctions in Vedic recitation specifically, distinct from Classical Sanskrit sandhi), or a
DIFFERENT rule? Give the exact sūtra citation (Pāṇini or a named Prātiśākhya sūtra — do not
guess a number if unsure).

**B2 — write Python for the FORWARD direction** (given two bare Pada-pāṭha words like "सु" and
"चन्द्र" — or however the actual word division works; tell me if my assumed division is wrong —
compute the Saṃhitā-pāṭha form WITH the augment, e.g. "सुश्चन्द्र"), citing the exact
conditioning environment (which vowel/consonant classes trigger it, and whether it's obligatory
or optional / bahulaṃ chandasi). This must integrate with `samhita_join` (see the appended
`sanskrit_phonology.py` — either extend that function or add a clearly-named function it calls).

**B3 — confirm the RESTORE direction is then automatic, or write it if not.** In this engine's
current architecture, Parigraha is always computed from the bare Pada-pāṭha word (see
`krama_engine._parigraha_unit` in the appended `krama_engine.py`) — meaning if B2's augment is
only ever inserted by the FORWARD (ordinary pair / chain-reconstruction) rule and never stored
back onto the word itself, the Parigraha rendering should already omit it "for free," with no
separate restoration function needed. Confirm this reasoning is correct with the actual code
path, or show me exactly where it would leak through if I'm wrong.

**B4 — if you cannot confidently derive B1's general conditioning rule, say so explicitly and
tell me whether these 4 examples (सुचन्द्र, परिकृण्वन्, धूःसदम्/धूर्षदम्, वनसदम्/वनर्षदम्) are
better treated as a small CLOSED lexical table (like this project's existing
`REPHI_CACHE_SLP1` in `pratishakhya_classify.py`, appended below) rather than a derived rule —
and if so, just give me that table (Saṃhitā-augmented form -> Pada/Parigraha-restored form) with
nothing invented beyond these 4 citations.**

---

## TASK C — does sūtra 10.10–10.11 narrow the EXISTING sūtra-10.3 आ-exception mechanism to only

fire adjacent to the ardharca-final word?

This engine already implements sūtra 10.3's monosyllable-avasāna exception (see
`generate_ardharca`'s branch in the appended `krama_engine.py`, and the worked example it's
built from, Uvaṭa's own "आ मन्द्रम्। मन्द्रमा वरेण्यम्। [आ वरेण्यम्]" on sūtra 10.3). It currently
fires this mechanism whenever ANY word about to be retaken was immediately preceded by a
monosyllable-avasāna word (आ/ओं/औं), anywhere in the ardharca — not just near the ardharca's own
end. This reproduces a real case in my data (RV 1.1.2's "सः देवान् आ इह वक्षति", where "इह" is
NOT the ardharca-final word) correctly, per the general condition.

**But sūtra 10.10–10.11's own text and bhāṣya read narrower:**

> 10.10: न आकारम् प्रागतः अननुनासिकम्। — Uvaṭa: "अननुनासिकम् आकारम्, अर्धर्चान्त्यात् प्राङ् न
> परिगृह्णीयात्। मन्द्रमा वरेण्यम्।" ("One should NOT do [ordinary] Parigraha of the
> non-nasalized आ that comes immediately before the ardharca-FINAL [word].")
>
> 10.11: प्रत्यादाय एव तम् ब्रूयात् उत्तरेण पुनः सह। — Uvaṭa: "प्रत्यादाय, तत्, पुनः उत्तरेण एव
> सह ब्रूयात्। मन्द्रमा वरेण्यम्। आ वरेण्यम्।।" ("Having taken it back, one should say it again
> together with what follows. 'मन्द्रमा वरेण्यम्. आ वरेण्यम्.'")

**C1.** Given ONLY these quotations (Devanāgarī + Uvaṭa's own gloss, both given verbatim above —
do not use any other source), is "अर्धर्चान्त्यात् प्राङ्" ("immediately before the
ardharca-final word") describing:

  (i) a genuinely NARROWER condition than 10.3 alone establishes — meaning the
  `monosyllable_confirm_pair`/`monosyllable_retake_tri_unit` mechanism should ONLY fire when the
  monosyllable's remaining position (after 10.3's own "skip forward" has already happened) is
  immediately before the ardharca's actual final word — or

  (ii) the SAME configuration 10.3's own worked example already illustrates (in that example,
  "वरेण्यम्" does happen to be the sentence-final word quoted, so 10.10–11 could just be
  re-describing that same single example from the retake-Parigraha side, not adding a new
  restriction), meaning my current, more general implementation is fine.

**Answer with (i) or (ii) and quote back the SPECIFIC words in the bhāṣya text above that settle
it — not a general impression.** If the quotations given are genuinely insufficient to decide
(e.g. because "मन्द्रम्/आ/वरेण्यम्" is from a hymn I haven't identified and you don't know
whether वरेण्यम् is really ardharca-final there either), say UNRESOLVED and tell me exactly what
additional citation (which sūtra, which commentary) would settle it — don't guess at the source
hymn.

**C2. If your answer is (i):** write the narrowed Python condition (as a diff against the
`generate_ardharca` branch in the appended `krama_engine.py`) and show it still passing this
existing, already-verified test:

```python
# Must still pass (Uvata's own worked example, isolated -- vareNyam here IS the last word given):
generate_ardharca(["आ", "मन्द्रम्", "वरेण्यम्"])
# -> unit texts: "आ मन्द्रम्" | "मन्द्रमा वरेण्यम्" | "आ वरेण्यम्" | "वरेण्यमिति वरेण्यम्" (10.9)
```

**and tell me what it predicts INSTEAD for RV 1.1.2's real case** (ardharca = ["सः", "देवान्",
"आ", "इह", "वक्षति"] — आ is NOT immediately before the ardharca-final word "वक्षति"; "इह" is)
— does your narrowed rule now say this should be an ORDINARY pair ("आ इह") with no tri-unit at
all, or something else? I have not independently verified which behavior is philologically
correct here (RV 1.1.2 itself is not among Uvaṭa's own cited examples) — just tell me what your
reading of 10.10–11 predicts, and I'll decide from there.

---

---

## Appended source files (read these before answering — your code must integrate with them)

### `tools/pratishakhya/sanskrit_phonology.py`

```python
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
```

### `tools/pratishakhya/pratishakhya_classify.py`

```python
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
REPHI_CACHE_SLP1 = {"svaScanAH", "dhUHsadam", "pUHpatim", "duHnaSam", "durdhyaH", "durlaBaH"}


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
```

### `tools/pratishakhya/krama_engine.py`

```python
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
```

=== END PROMPT ===
