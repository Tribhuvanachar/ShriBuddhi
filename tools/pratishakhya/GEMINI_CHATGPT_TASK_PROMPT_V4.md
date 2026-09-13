# Round 4 — one focused, sharply-scoped question (RV 1.1.7's visarga-before-ā gap)

Paste everything between `=== BEGIN PROMPT ===` / `=== END PROMPT ===` into ChatGPT or Gemini.
No repository access needed — every citation and code snippet this needs is embedded below.

=== BEGIN PROMPT ===

This is a single, narrow philology question about the Ṛgveda-Prātiśākhya (Śaunaka/Śākala
tradition), sharpened over several earlier rounds with you (or a similar model) — most of what
was "unresolved" before has now been resolved one way or another; this is the one piece that
keeps surviving every check I've thrown at it. Same hard rule as every previous round:

**HARD RULE: every claim must come with either (a) an exact quotation from a real, named source
(a specific Prātiśākhya sūtra, a specific Pāṇini sūtra, a specific published grammar/commentary)
— not "Vedic Sanskrit often does X" — or (b) explicit confirmation that this is genuinely
`bahulaṃ chandasi` (unconditioned Vedic-meter free variation) with no further rule to find. If
you propose Python, I WILL run it before trusting it — the last two rounds both had a shared bug
(wrong SLP1 letter) that survived one of your own "I tested this, it passes" claims, so a
citation without runnable, verified code is more useful to me than confident-sounding code I
can't verify from your description alone.**

---

## THE QUESTION

RV 1.1.7's Pada-pāṭha (from DGE's own corpus, directly quoted, not summarized):

    उप । त्वा । अग्ने । दिवेऽदिवे । दोषाऽवस्तः । धिया । वयम् । नमः । भरन्तः । आ । इमसि

Its attested continuous Saṃhitā-pāṭha (also directly quoted):

    उप त्वाग्ने दिवेदिवे दोषावस्तर्धिया वयम् । नमो भरन्त एमसि ॥

Focus on the very end: Pada words **भरन्तः** (bharantaḥ) + **आ** (ā) + **इमसि** (imasi) surface
as **भरन्त एमसि** (bharanta emasi).

**The "आ + इमसि → एमसि" half is NOT the mystery** — that's ordinary guṇa vowel sandhi (ā + i →
e), no special rule needed, confirmed independently already.

**The real, narrow, remaining question is just भरन्तः + आ → भरन्त** (visarga disappears
entirely, with NO trace — not even the "o" that ordinary classical sandhi predicts).

### Why this is NOT explained by the ordinary classical Sanskrit rule (checked directly, not

assumed)

The Prātiśākhya's own text (my corpus, Layer A, exact quotation):

    2.24: विसर्जनीयः अरिफितः दीर्घपूर्वः स्वरोदयः आकारम्।
          ("An un-rhotacized visarjanīya, preceded by a LONG vowel, before a vowel, becomes the
          sound ā.")
    2.27: ह्रस्वपूर्वः तु सः अकारम्।
          ("But that [visarjanīya], preceded by a SHORT vowel, [becomes] the sound a.")

भरन्तः is short-a-preceded (bharant-a-ḥ), so 2.27 applies: the visarga becomes an "a" sound. This
is EXACTLY what my own phonology engine already implements. The rule below is validated by
folding it across whole verses and diffing against DGE's own attested continuous text: 16 of 18
RV 1.1 ardharcas reproduce the attested text exactly this way, and RV 1.1.7's ardharca (the one
with this exact भरन्तः+आ pair) is one of only two that don't — the other is an already-explained,
unrelated case. Here is the actual code (from `sanskrit_phonology.py`'s `samhita_join`, the
branch that fires for this exact word shape):

```python
if prev_vowel in ("a", "A"):
    # a/a-class visarga: aH -> o before voiced (incl. vowel) -- the "a" of
    # aH is REPLACED by "o", not kept alongside it; if the following vowel
    # is specifically 'a' it further elides (marked with an avagraha)
    base = stem[:-1]  # drop the "a"/"A" that combines with visarga into "o"
    if first2 == "a":
        rest2 = s2[1:]
        return _finish(base + "o'" + rest2, "visarga_a_class_before_a_elided", w1_deva, w2_deva)
    if first2 in ALL_VOWELS or first2 in VOICED_CONSONANTS:
        return _finish(base + "o " + s2, "visarga_a_class_before_voiced", w1_deva, w2_deva)
    ...
```

For भरन्तः + आ: `first2` is "A" (long ā), which hits the `first2 in ALL_VOWELS` branch, giving
**भरन्तो आ** (visarga → "o", kept SEPARATE from the following आ with a space — this is the
textbook classical form, e.g. रामः + आगतः → रामो आगतः, which is standard and correct). This
"o" is deliberately NOT put through any further vowel-sandhi with the following vowel (compare
"देवः" + "देवेभिः" → "देवो देवेभिः", already validated) — this engine treats a visarga-derived
"o" as sandhi-resistant to what follows it, similar to a documented precedent already in the
same file for the pronouns सः/एषः (visarga drops with NO further vowel merger: "saH" + "it" →
"sa it", not "set"):

```python
if stem in ("sa", "eza", "eSa"):
    # Irregular, specially-legislated sandhi for these two pronouns: the
    # visarga drops WITHOUT triggering any further vowel sandhi with what
    # follows (unlike an ordinary a-final word) -- "saH" + "it" -> "sa it",
    # not "set" (which plain a+i guna would otherwise give).
    return _finish(stem + " " + s2, "visarga_sa_esa_elision_blocks_further_sandhi", w1_deva, w2_deva)
```

**So: "भरन्तो आ" is the CORRECT, textbook-classical, already-validated-elsewhere prediction.**
The attested Vedic form "भरन्त" (not "भरन्तो") is a genuine DEVIATION from that ordinary rule —
the visarga doesn't even become "o", it disappears with no trace at all before this specific
following आ.

### What I need from you

**Q1.** Is there a NAMED Prātiśākhya sūtra (Ṛgveda-Prātiśākhya, Śākala/Śaunaka — not a different
Prātiśākhya unless you can show the rule is shared verbatim) or a specific, citable Pāṇinian rule
that describes full visarga-elision (not the o-retaining classical form) specifically when a
SHORT-vowel-preceded visarga is followed by **long ā** specifically (as opposed to short a,
which 2.24's own sibling rules already cover via avagraha-elision, or other vowels, which the
ordinary o-retaining rule already covers correctly per my 69/70 validation)? If yes: quote the
exact sūtra text (Devanāgarī or IAST, your choice, but VERBATIM, not paraphrased) and explain
precisely how its wording licenses full elision before ā specifically.

**Q2.** If you cannot find such a sūtra: is this documented ANYWHERE (a specific published
Ṛgveda-Prātiśākhya commentary, a specific grammarian's named school, a specific footnote in a
critical edition) as a recognized `bahulaṃ chandasi` (Vedic meter licenses free variation here)
case — and if so, cite that source specifically, not just the general concept. If you cannot cite
even that, say so plainly: "I cannot find a specific source for this; it may be an uncatalogued
Vedic irregularity" is a completely acceptable, honest answer — much more useful to me than a
guess dressed up as a citation.

**Q3 (only if Q1 has a real answer).** If you found a real, citable rule, write the Python
change as a diff against the code block quoted above (the `if prev_vowel in ("a", "A"):` branch),
and show it passing BOTH of these cases without breaking the other:

```python
# Must start giving this (the one currently wrong):
samhita_join("भरन्तः", "आ")["surface"] == "भरन्त"   # NEW correct answer

# Must NOT break this (already correct, validated elsewhere, e.g. "रामः अत्र"-type environment):
samhita_join("देवः", "देवेभिः")["surface"] == "देवो देवेभिः"   # unrelated word-shape, must stay "o"
```

Tell me exactly what textual feature of your cited rule distinguishes "भरन्तः + आ" (elide fully)
from "देवः + देवेभिः" (keep the "o") — if your rule can't actually tell these apart, it's wrong,
say so rather than proposing it anyway.

---

## BONUS, LOWER-PRIORITY, OPTIONAL SECOND QUESTION — only answer if you have real confidence

left over from Q1-3 above; a plain "unresolved" is fine and expected here

Uvaṭa's own bhāṣya on Ṛgveda-Prātiśākhya sūtra 10.8 (Krama-pāṭha, already implemented for its
other 3 examples — ca/vā/cit) has a fourth example I have NOT implemented:

    मो षु णः। मो इति मो। सु इति सु।।

("mo ṣu ṇaḥ" [Saṃhitā form] — "mo" retaken as "mo iti mo"; **"षु" retaken as "सु इति सु"**,
i.e. the retroflexed "ष्" reverts to its plain Pada form "स्" when retaken in isolation.)

**Q4.** Is स्→ष् here (सु → षु, in "मो षु णः") actually licensed by Pāṇini 8.3.59
("आदेशप्रत्यययोः") read together with 8.3.57 ("इणः षः")? Those specifically require the
triggering "इ/उ/ऋ/लृ" vowel (here, the "ओ" of "मो", historically from "मा"+"उ") to be either an
"आदेश" (a grammatical substitute) or part of a "प्रत्यय" (a suffix) — **is "सु" here actually
either of those, in this specific Rigvedic phrase**, or is it an ordinary independent word (in
which case 8.3.59 would NOT apply and something else must be going on)? If you can find the
actual Rigvedic verse this phrase is from and check what "सु" grammatically is there, do so and
cite it. If not, UNRESOLVED is the expected, acceptable answer — I am not going to implement a
general स्→ष् rule from one example either way; I'm only asking in case you happen to know this
specific verse and its grammar already.

=== END PROMPT ===
