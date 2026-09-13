# Three focused Prātiśākhya/phonology questions — for Gemini, ChatGPT, or a Sanskritist

Written 11 Sep 2026. Two rounds of AI review (a spec critique, then a code-level review) have
been applied to this project's Ṛgveda Krama-pāṭha generator, and one round of THAT review
included sample code with claims about specific sūtra numbers and sandhi behaviour. This packet
does **not** ask for another general review — it asks three narrow, checkable philological
questions where this project's own sourced sūtra text conflicts with (or is silent on) a
specific claim, plus one open phonological gap. Everything needed to answer is quoted below;
no repo access is required. Full provenance and an overall-review invitation are in §4.

---

## 1. Paste-able prompt

```
I'm working on a computational Krama-patha (Vedic word-repetition recitation) generator for
the Rigveda Sakala tradition, built from Saunaka's Rgveda-Pratisakhya (Krama-Patala, ch. 10)
with Uvata's Bhasya. I have three specific, narrow questions -- please answer each with your
reasoning and, where possible, a source (edition, commentary, or your own training knowledge).

QUESTION 1 -- sutra numbering for sthita/upasthita/sthitopasthita
My own sourcing (via VedaVishtaram's digitized Uvata Bhasya, cross-checked against the
Sanskrit Library's Peter Scharf edition) gives:
  10.12: "upasthitam setikaranam" -- defines UPASTHITA = word + iti (example: "baahuu iti")
  10.13: "kevalam tu padam sthitam" -- defines STHITA = the bare word alone (example: "agnim")
  10.14: "tat sthitopasthitam naama yatra ubhe aaha samhite" -- defines STHITOPASTHITA = BOTH
         sthita and upasthita uttered TOGETHER (example: "vibhaavaso iti vibhaavaso")
A different AI-generated code sample I was given assigns these the OTHER way around: 10.12 =
sthita-formation, 10.13 = upasthita-with-sandhi. Which assignment is correct? Is there a
textual-variant reason (different editions numbering these two sutras differently) that could
explain the discrepancy, or is one of these simply wrong?

QUESTION 2 -- is there EVER sandhi between the word and "iti" in sthitopasthita?
The one worked example I have (10.14's own: "vibhaavaso iti vibhaavaso") shows NO sandhi
between "vibhaavaso" and "iti" -- but "vibhaavaso" ends in "o", which doesn't combine with a
following vowel under classical sandhi rules anyway (o + vowel is a well-known hiatus
exception), so this example doesn't actually prove the GENERAL case. The same AI-generated code
sample assumed savarna-dirgha SHOULD apply here in general (e.g. "asi" + "iti" -> "asiiti"
fused). Is that assumption correct for a word ending in a vowel that WOULD ordinarily sandhi
(like short "i" or "a"), or does "iti" in this specific Parigraha construction behave as if
prosodically separate (no external sandhi at all, regardless of what the word ends in)? A
citation to Uvata's Bhasya, Vishnumitra's Vrtti, or any other commentary/edition covering a
Parigraha word that does NOT end in "o" would settle this.

QUESTION 3 -- RV 1.1.7's visarga-before-aa: "bharantaH" + "aa" -> "bharanta emasi"
Rgveda 1.1.7's Pada-patha has: "... namaH | bharantaH | aa | imasi ||"
Its attested Samhita-patha has: "... namo bharanta emasi ||"
The general classical a-class-visarga-before-voiced rule (visarga -> "o" before any voiced
sound including a vowel) would predict "bharanto aa" -- but the ACTUAL text shows the visarga
dropping ENTIRELY ("bharanta", no visarga, no "o"), with "aa"+"imasi" then combining normally
into "emasi" (guna). Is there a SPECIFIC Pratisakhya sutra (Rgveda-Pratisakhya, likely Patala 2
or 4, or Panini's own sutras on visarga-lopa) that licenses full visarga elision before this
"aa" specifically (as opposed to the ordinary o-conversion), or is this an instance of genuine
free Vedic variation ("bahulam chandasi") with no single derivable rule? If there IS a specific
sutra, please give its number and text.

Please answer each question separately and say plainly if you're not confident.
```

---

## 2. Why these three, and only these three

This project has already been through two rounds of review that correctly found real gaps
(hardcoded pair strings, an undifferentiated Parigraha formula, unaudited counts, a flawed
attestation check). Both are recorded in `dge/RV_PRATISHAKHYA_KRAMA_ARCHITECTURE.md` (§6.6,
§6.7) along with what was fixed and what remains open. The three questions above are the
specific remaining items where **this project's own sourced primary text conflicts with, or is
silent on, a claim made about it** — not requests to re-review already-settled ground:

- Q1 exists because a code sample handed to this session asserted 10.12/10.13 the opposite way
  from what this project's own sourcing says, and getting Krama-Paṭala's own definitional
  vocabulary wrong would propagate into every future Parigraha unit.
- Q2 exists because the ONE attested example this project has (`vibhāvaso iti vibhāvaso`)
  happens to use a word ending in "o", which is independently exempt from vowel sandhi in
  classical Sanskrit — so it cannot by itself prove "no sandhi with iti" as a *general* rule,
  and getting this wrong would corrupt every Parigraha unit for a word ending in any other
  vowel.
- Q3 is a real, already-documented, still-open gap (see `sanskrit_phonology.py`'s module
  docstring) blocking one of the two remaining chain-reconstruction mismatches in RV 1.1 (see
  §3 below for the exact current count).

---

## 3. Current status, for context (not something to review again)

Chain-reconstruction validation (folding this project's sandhi engine across a whole ardharca
and diffing against DGE's own attested Saṃhitā-pāṭha) currently matches on **16 of 18** RV 1.1
ardharcas. The 2 mismatches are: RV 1.1.7 (Q3 above) and a separate, purely technical
transliteration-library limitation in RV 1.1.2 (not a philological question — the
`indic_transliteration` library's SLP1 scheme cannot distinguish "र्ऋ" from "रृ"; see
`sanskrit_phonology.py`'s module docstring for the exact repro if curious, but this is not
something Q1–Q3's kind of answer can help with).

---

## 4. Full provenance, and an open invitation to review anything else

All at commit `2e97745c63d6ae788cadf8acd2350e6d2047bfa4` on branch
`claude/rv-pratishakhya-krama-spec-0v7nnc` of `Tribhuvanachar/bhumandala` (GitHub). Replace
`blob` with `raw` in any URL for the raw file content.

**The sandhi engine (where Q1–Q3 would get fixed if answered):**
`https://github.com/Tribhuvanachar/bhumandala/blob/2e97745c63d6ae788cadf8acd2350e6d2047bfa4/tools/pratishakhya/sanskrit_phonology.py`

**The Krama-Paṭala rule logic (where the 10.12–10.14/10.16 entries above came from, in full,
with `basis`/`caveat` fields per entry):**
`https://github.com/Tribhuvanachar/bhumandala/blob/2e97745c63d6ae788cadf8acd2350e6d2047bfa4/dge/data/vedanga/shiksha/pratishakhya/rigveda_pratishakhya/krama_kramahetu_rules.json`

**The Krama generator itself (predicates + pairing + Parigraha logic):**
`https://github.com/Tribhuvanachar/bhumandala/blob/2e97745c63d6ae788cadf8acd2350e6d2047bfa4/tools/pratishakhya/krama_engine.py`
`https://github.com/Tribhuvanachar/bhumandala/blob/2e97745c63d6ae788cadf8acd2350e6d2047bfa4/tools/pratishakhya/pratishakhya_classify.py`

**The regenerated Krama-pāṭha output + chain-reconstruction validation results (all 9 verses):**
`https://github.com/Tribhuvanachar/bhumandala/blob/2e97745c63d6ae788cadf8acd2350e6d2047bfa4/dge/data/vedanga/shiksha/pratishakhya/rigveda_pratishakhya/krama_regenerated_output.json`

**Pada-pāṭha + Saṃhitā-pāṭha input (RV maṇḍala 1, items 1.1.1–1.1.9):**
`https://github.com/Tribhuvanachar/bhumandala/blob/2e97745c63d6ae788cadf8acd2350e6d2047bfa4/dge/data/vedas/rigveda/shakala_shakha/samhita/mandala_01/data.json`

**The full architecture/decision record** (every correction so far, sec.6.6/6.7 cover the two
AI-review rounds specifically):
`https://github.com/Tribhuvanachar/bhumandala/blob/2e97745c63d6ae788cadf8acd2350e6d2047bfa4/dge/RV_PRATISHAKHYA_KRAMA_ARCHITECTURE.md`

**All 1,067 Ṛgveda-Prātiśākhya sūtras with Uvaṭa's Bhāṣya attached** (source for the 10.12–10.16
texts quoted in the prompt above):
`https://github.com/Tribhuvanachar/bhumandala/blob/2e97745c63d6ae788cadf8acd2350e6d2047bfa4/dge/data/vedanga/shiksha/pratishakhya/rigveda_pratishakhya/data.json`

**Original external sources (primary, not this repo):**
- Sanskrit Library, Ṛgveda-Prātiśākhya, ed. Peter M. Scharf, 2010 (CC BY-NC-SA 3.0):
  `https://sanskritlibrary.org/catalogsText/fgveda_prAtiSAKya.html`
- VedaViṣṭāram (Uvaṭa's Bhāṣya + Viṣṇumitra's Vṛtti):
  `https://vedavishtaram.in/lakshanam/rp.html`

**If you'd rather do a broader pass instead of just these three questions**: everything in
`dge/RV_PRATISHAKHYA_KRAMA_ARCHITECTURE.md` sec.6.6–6.7 and
`tools/pratishakhya/KRAMA_VERIFICATION_PACKET.md` is fair game, including double-checking this
project's OWN prior AI-review responses — nothing here should be taken as settled just because
a previous AI (including the one that wrote this packet) said so. If you find a specific error
in this project's reasoning (not just a general "add more rigor" comment), name the exact file,
sūtra, or line it concerns.

## 5. What to do with a reply

A sūtra-number correction or a citation resolving Q2/Q3 goes straight into
`sanskrit_phonology.py` / `pratishakhya_classify.py` (with the citation recorded in the code
comment, per this repo's existing convention) and `krama_kramahetu_rules.json`'s corresponding
entries if the rule text itself was misread. Nothing here should be hand-edited without also
updating whichever script produces it.
