# Krama-pāṭha generated output — verification packet

Written 11 Sep 2026. This is the reviewer-facing bundle for the RV 1.1
Krama-pāṭha output this session generated — for Gemini, ChatGPT, a human
Sanskritist, or a fresh Claude session (paste the block in §3 directly into
a new chat) to check independently. Nothing in this project has verified
this output against a published Krama-pāṭha edition; that's exactly what
this packet is for.

---

## 1. What was generated, and how

All 9 verses of RV 1.1 (maṇḍala 1, sūkta 1 — "agním īḷe puróhitam...").
`tools/pratishakhya/generate_krama_rv_1_1.py` applied the rule logic in
`krama_kramahetu_rules.json` (built from Śaunaka's Ṛgveda-Prātiśākhya,
Krama-Paṭala, with Uvaṭa's Bhāṣya) to DGE's own Pada-pāṭha and Saṃhitā-pāṭha
for these verses:

- **Base pairing** (sūtra 10.2): consecutive overlapping word-pairs within
  each ardharca (half-verse).
- **Parigraha** — special "grasp and confirm" treatment (sūtras 10.7–10.9,
  10.12–10.14, 10.16) — applied to: (a) *avagṛhya* words, i.e. compounds
  DGE's own Pada-pāṭha already marks with an avagraha internally (e.g.
  पुरःऽहितम्), and (b) the last word of every ardharca. Rendered as
  `word iti word` (the combined form first, the avagraha-split form second
  for compounds — sūtra 10.16), following Uvaṭa's own worked example for
  10.14 (`vibhāvaso iti vibhāvaso`, no sandhi between the three parts).
- **Sandhi within each pair** is taken verbatim from DGE's own attested
  Saṃhitā-pāṭha for that verse, not independently computed — this project
  has no validated Sanskrit sandhi engine (see §4), and sandhi is a purely
  local, adjacent-word phenomenon, so this is exact for what it covers.

## 2. What is explicitly NOT resolved — check these first

- **Six pairs are flagged `"confidence": "low"`** in the JSON, all
  involving the monosyllable **आ** (a preverb, RV 1.1.2, 1.1.5, 1.1.7).
  Sūtra 10.3 explicitly says such single-syllable words behave specially —
  they stop the pairing chain (*avasyanti*) rather than continuing forward
  in the ordinary way, per Uvaṭa's own example (`आ मन्द्रम् । मन्द्रमा
  वरेण्यम्`). The output gives the ordinary pairwise rendering instead of a
  guessed reconstruction of that special mechanic. **This is the single
  most important thing to check.**
- **10.3 itself has an unresolved reading** (one of only two sūtras in
  paṭala 10–11 not fully cross-checked — see the architecture doc §4c) — a
  genuine apparent edition variant between the two sources checked, not an
  OCR gap.
- **The exact placement of each Parigraha `word iti word` unit** (right
  after the pair that introduces the word) is this session's own reading
  of the sūtras, not copied from an attested Krama edition.
- Two of paṭala 10's more intricate procedural sūtras (10.15's optional
  disambiguation, 10.19's samaya-pause placement) are not exercised by
  these particular 9 verses, so they're untested by this batch.

## 3. Paste-able prompt (for Gemini, ChatGPT, or a fresh Claude session)

Copy everything between the lines into a new chat with any of those, no
repo access needed:

```
I have a candidate Krama-pāṭha (word-repetition recitation form) reconstruction for
RV 1.1.1-1.1.9 (Ṛgveda, maṇḍala 1, sūkta 1, Śākala recension), generated from Śaunaka's
Ṛgveda-Prātiśākhya (Krama-Paṭala, sūtras 10.1-10.22) plus Uvaṭa's Bhāṣya. Please check it
against your own knowledge of attested Krama-pāṭha editions and flag anything wrong.

The core rule: for a run of Pada-pāṭha words in one ardharca (half-verse), form consecutive
overlapping pairs (W1,W2),(W2,W3),(W3,W4)... A word gets extra "Parigraha" treatment --
rendered as "word iti word" -- if it is (a) a Pada-pāṭha compound-split (avagṛhya) word, or
(b) the last word of the ardharca. No sandhi crosses an ardharca boundary.

RV 1.1.1 ("agním īḷe puróhitam yajñásya devám ṛtvíjam | hótāram ratnadhā́tamam"):
Generated: अग्निमीळे । ईळे पुरोहितम् । पुरोहितम् इति पुरःऽहितम् । पुरोहितं यज्ञस्य ।
यज्ञस्य देवम् । देवमृत्विजम् । ऋत्विजम् इति ऋत्विजम् । होतारं रत्नधातमम् ।
रत्नधातमम् इति रत्नऽधातमम्

RV 1.1.5 ("agnír hótā kavíkratuḥ satyáścitraśravastamaḥ | devó devébhirā́ gamat"):
Generated: अग्निर्होता । होता कविक्रतुः । कविक्रतुः इति कविऽक्रतुः । कविक्रतुः सत्यः ।
सत्यश्चित्रश्रवस्तमः । चित्रश्रवस्तमः इति चित्रश्रवःऽतमः । देवो देवेभिः । देवेभिरा ।
आ गमत् । गमत् इति गमत्

RV 1.1.7 ("úpa tvāgne divé-dive dóṣāvastardhiyā vayam | námo bháranta émasi"):
Generated: उप त्वा । त्वाग्ने । अग्ने दिवेदिवे । दिवेदिवे दोषावस्तः । दोषावस्तः इति
दोषाऽवस्तः । दोषावस्तर्धिया । धिया वयम् । वयम् इति वयम् । नमो भरन्तः । भरन्तो ।
एमसि । इमसि इति इमसि  <- FLAGGED LOW CONFIDENCE: "भरन्तो" and "एमसि" involve the
monosyllable आ, which Ṛgveda-Prātiśākhya 10.3 says behaves specially (stops the pairing
chain) rather than combining normally -- is the ordinary rendering shown here wrong, and
if so what should replace it?

Questions:
1. Does this match, or plausibly approximate, a real published Krama-pāṭha for these verses
   (e.g. as printed in a traditional edition, or as you've encountered elsewhere)?
2. Is the "word iti word" Parigraha placement (right after the word's own pair) correct, or
   does it belong somewhere else in the sequence?
3. What should the आ-adjacent pairs actually look like?
4. Anything else that looks wrong.
```

## 4. Full provenance — every source, script, and file involved

All at commit `743878be` on branch `claude/rv-pratishakhya-krama-spec-0v7nnc` of
`Tribhuvanachar/bhumandala` (GitHub). Replace `blob` with `raw` in any URL below for the
raw file content instead of GitHub's viewer.

**Generated output (the thing being checked):**
`https://github.com/Tribhuvanachar/bhumandala/blob/743878bef455aa4f55fa0ad577f44c29cd047ce4/dge/data/vedanga/shiksha/pratishakhya/rigveda_pratishakhya/krama_generated_output.json`

**Generator script (how it was produced):**
`https://github.com/Tribhuvanachar/bhumandala/blob/743878bef455aa4f55fa0ad577f44c29cd047ce4/tools/pratishakhya/generate_krama_rv_1_1.py`

**Rule logic applied (conditions/action/exceptions per sūtra):**
`https://github.com/Tribhuvanachar/bhumandala/blob/743878bef455aa4f55fa0ad577f44c29cd047ce4/dge/data/vedanga/shiksha/pratishakhya/rigveda_pratishakhya/krama_kramahetu_rules.json`
Built by: `.../tools/pratishakhya/build_krama_rules.py`

**Raw Ṛgveda-Prātiśākhya sūtra text (all 1,067 sūtras, with Uvaṭa's Bhāṣya attached):**
`https://github.com/Tribhuvanachar/bhumandala/blob/743878bef455aa4f55fa0ad577f44c29cd047ce4/dge/data/vedanga/shiksha/pratishakhya/rigveda_pratishakhya/data.json`
Ingested by: `.../tools/pratishakhya/import_rv_pratishakhya.py` and
`.../tools/pratishakhya/crosscheck_vedavishtaram.py`

**Pada-pāṭha + Saṃhitā-pāṭha input (RV maṇḍala 1, items 1.1.1–1.1.9):**
`https://github.com/Tribhuvanachar/bhumandala/blob/743878bef455aa4f55fa0ad577f44c29cd047ce4/dge/data/vedas/rigveda/shakala_shakha/samhita/mandala_01/data.json`

**The full architecture/decision record (corrections, sourcing, everything checked and why):**
`https://github.com/Tribhuvanachar/bhumandala/blob/743878bef455aa4f55fa0ad577f44c29cd047ce4/dge/RV_PRATISHAKHYA_KRAMA_ARCHITECTURE.md`

**Original external sources (primary, not this repo):**
- Sanskrit Library, Ṛgveda-Prātiśākhya, ed. Peter M. Scharf, 2010 (CC BY-NC-SA 3.0):
  `https://sanskritlibrary.org/catalogsText/fgveda_prAtiSAKya.html`
- VedaViṣṭāram (Uvaṭa's Bhāṣya + Viṣṇumitra's Vṛtti):
  `https://vedavishtaram.in/lakshanam/rp.html`

## 5. What to do with a reply

If Gemini/ChatGPT/a Sanskritist flags something wrong: note the exact sūtra or pair it
concerns, and it can be fixed in `generate_krama_rv_1_1.py`'s per-verse data (the pairing
and Parigraha logic is generic; only the hand-aligned sandhi and word-flags are per-verse)
plus, if the rule itself was misread, in `krama_kramahetu_rules.json`'s corresponding entry.
Neither file should be hand-edited without also updating the script/build step that produces
it, per this repo's existing convention for every other file in this pipeline.
