# Ṛgveda-Prātiśākhya Krama-pāṭha generator — corrected specification

_Written 10 Sep 2026, ~10:40 pm IST. Status: **specification only — no rule-engine code
written yet.** This document exists because a first-draft Gemini prompt for "generate
Krama-pāṭha from Pada-pāṭha" was reviewed against the actual structure of Śaunaka's
Ṛgveda-Prātiśākhya and found to skip most of the tradition-specific machinery. This is the
corrected spec a future session should build against — not the naive prompt._

> **⚠️ Correction, 10 Sep 2026, ~11:50 pm IST (Part II).** The first version of this
> document wrongly claimed the Rigveda Śākala **Pada-pāṭha does not exist** in this repo. It
> does — checked directly and corrected in §2 and §4 below. It also named a single,
> unverified Prātiśākhya digitization source; §4a below replaces that with a three-layer
> sourcing plan (Sanskrit Library TEI/XML as the canonical base, VedaViṣṭāram for
> commentary cross-check, the RV-Prātiśākhya project for independent validation), each
> checked live on 10 Sep 2026. §6.1 also gets a concrete rule-database file layout and
> schema. Everything else from the first version stands.
>
> **Update, 11 Sep 2026, ~12:35 am IST (Part III) — Layer A actually pulled and inspected.**
> §4a is rewritten below with what was actually found: Layer A is **not** a downloadable
> static TEI/XML file — "First XML Edition" describes the source's internal editing process;
> public access is a single undocumented JSON endpoint behind the reader page's JavaScript.
> The endpoint was reached, one full document fetched, and its structure inspected — see
> §4a for the endpoint, its data shape, and why bulk ingestion through it needs a explicit
> go-ahead before it's automated further. The good news: doing this **independently
> confirmed real sūtra text**, including the exact sūtras quoted (unattributed) in the
> original Gemini-derived review — see §4a's verified-sample table.
>
> **Update, 11 Sep 2026, ~1:20 am IST (Part IV) — bulk pull done, with the lead's go-ahead.**
> New §4b: all 1,067 sūtras are now in
> `dge/data/vedanga/shiksha/pratishakhya/rigveda_pratishakhya/data.json`, via
> `tools/pratishakhya/import_rv_pratishakhya.py` (methodology in the sibling `SOURCES.md`),
> checked by `tests/test_rv_pratishakhya_import.py`. Building the real importer also caught a
> mistake in Part III's own verified-sample table — see the correction note right above that
> table — which is now fixed. This is the sūtra *text* landing in the repo, cited and
> attributed; turning it into rule logic the generator can run is still future work (§6.1,
> §8, §10).

---

## 0. What this replaces, and why

The rejected approach treated Krama generation as: take adjacent Pada words, apply a short
exception list, run generic Sanskrit sandhi, propagate a hard-coded accent-combination
matrix, emit `iti`-based Parigraha universally, and mix in audio timestamps and colour
markup at generation time. Each of those is a real simplification of a tradition
(Śākala Krama-pāṭha per Śaunaka's Prātiśākhya) that has its own dedicated chapters for
exactly these questions, plus a whole second chapter (Kramahetu) explaining *why* the
exceptions exist. Treating Pāṇinian/Classical Sanskrit sandhi as authoritative, or Parigraha
as `word + iti + iti + word`, will produce fluent-looking Sanskrit that is not the attested
Śākala Krama text. Section 2 below is the corrected rule hierarchy; section 9 has the full
list of what the naive version got wrong, kept for traceability back to the review that
produced this document.

---

## 1. Scope

This generator is specifically for the **Rigveda Śākala tradition** as carried by DGE's own
Saṃhitā data (`dge/data/vedas/rigveda/shakala_shakha/samhita/`). It is not a general Vedic
sandhi/accent engine, and it must not silently fall back to one.

---

## 2. Authoritative rule hierarchy

In order, highest first. A lower source may only be consulted where a higher one is silent:

1. DGE's own Rigveda Śākala Saṃhitā dataset (exists: `mandala_01`–`mandala_10`).
2. DGE's own Rigveda Śākala Pada-pāṭha dataset (**exists** — accented `pada_patha` field on
   all 10,552 mantras, cross-validated 96.61% against VedaWeb TEI; see §4).
3. Śaunaka's Ṛgveda-Prātiśākhya, **Krama-Paṭala** (traditionally numbered Chapter 10, 22
   sūtras).
4. The same work's **Kramahetu-Paṭala** (Chapter 11, 71 sūtras) — the rationale-and-exception
   chapter; it is not optional colour, it carries load-bearing rules including the explicit
   Śākala catuḥkrama (four-fold Krama) practice.
5. The same work's Saṃhitā-Paṭala (ch. 2), Svara-Paṭala (ch. 3) and Sandhi-Paṭala (ch. 4),
   and the Nati/Dhvanyāgama/Pluti chapters (ch. 5–9) where a Krama/Kramahetu rule invokes
   them.
6. General Pāṇinian/Classical Sanskrit phonology — **only** where none of the above governs.

A generic Sanskrit sandhi library (if used at all) is a helper suggestion, never the final
answer: its output must pass through the Prātiśākhya-rule layer, which can override it.
Every non-trivial transformation the generator makes must be able to cite the sūtra(s) that
justify it (see §6.3, `provenance`).

### 2.1 Chapter map of the Ṛgveda-Prātiśākhya

Confirmed from two independent secondary sources (`vedavishtaram.in/lakshanam/rp.html` and
`sites.google.com/view/rv-pratishakhya`, both consulted 10 Sep 2026) — **not yet cross-checked
against the primary scan**, see §4:

| # | Paṭala | Topic | Sūtras |
|---|---|---|---|
| 1 | Saṃjñā-Paribhāṣā | definitions, conventions | 102 |
| 2 | Saṃhitā | continuous-recitation / vowel sandhi | 41 |
| 3 | Svara | accent | 26 |
| 4 | Sandhi | consonant sandhi | 94 |
| 5 | Nati | dental→cerebral etc. | 59 |
| 6 | Dhvanyāgama | inserted sounds | 56 |
| 7–9 | Pluti (I–III) | vowel protraction | 55 + 47 + 49 |
| **10** | **Krama** | **sequential (Krama) recitation method** | **22** |
| **11** | **Kramahetu** | **rationale + exceptions for Krama, incl. Śākala catuḥkrama** | **71** |
| 12 | Sīmā | boundary rules | 25 |
| 13 | Śikṣā | articulation | 48 |
| 14 | Ucchāraṇa-Doṣa | pronunciation errors | 68 |
| 15 | Oṃkāra | Om chanting | 33 |
| 16–18 | Chandaḥ (I–III) | metre | 88 + 48 + 58 |

Treat this table as **provisional** until the primary source is digitized (§4) — sūtra
counts and any specific sūtra text quoted anywhere in project notes must be verified against
it before being encoded as a rule, not taken on the secondary sites' word alone.

---

## 3. What "Krama is not simple adjacent pairing" means concretely

`W1 W2 | W2 W3 | W3 W4 …` is the structural skeleton only. A production generator needs,
at minimum, rule coverage for:

- Śākala-specific catuḥkrama behaviour (ch. 11).
- Avasāna/avasyā and ardharca-boundary handling — sandhi must **not** cross an ardharca
  boundary; this is a prohibition, not an omission to patch later.
- Parigraha — a multi-part rule set (bahumadhyagata, ardharcāntya, iti/setikaraṇa, compound
  puna-vacana, Pragṛhya-in-Parigraha, Śuddhākṣara-āgama, Rephita/ūṣman exceptions), not a
  single `word + iti` formula.
- Pluta exceptions.
- Nati and Dhvanyāgama transformations where a Krama-Paṭala or Kramahetu-Paṭala rule invokes
  them.

Do not implement Parigraha, Pragṛhya, or Rephi handling as a single universal formula or a
flat word list stands in for the phenomenon. A dictionary may **cache** known cases; it must
not **define** them.

---

## 4. Prerequisite data gap — checked against the repo, 10 Sep 2026

Corrected from the first version of this document, which wrongly claimed the Pada-pāṭha was
missing entirely — it checked only for a sibling `pada/` directory next to `samhita/` and
missed the per-mantra field actually holding the text.

| Needed | Current state |
|---|---|
| Rigveda Śākala **Pada-pāṭha** dataset | **Done.** Accented `pada_patha` field (alongside `samhita_patha`) on all 10,552 mantras in `dge/data/vedas/rigveda/shakala_shakha/samhita/mandala_01..10/data.json`. Sourced from the `FourVedas.xlsx` spreadsheet (Virendra Agarwal's "Digitisation of Vedas" / VedaKosh, via sanskritdocuments.org, used with explicit permission) and cross-validated at 96.61% exact match against the independent VedaWeb TEI dataset (`diagnostics/validate_fourvedas.py`, every sampled mismatch a known edition variant). Full provenance and the accent-codepoint convention (core Devanagari block `U+0951`/`U+0952`, not the Vedic Extensions block — see §6.2) are in `dge/veda_toolkit/README.md` §1–3. Independently cross-checkable: `github.com/vishvasa`'s Rigveda repo carries a per-sūkta Śākala Saṃhitā (2,226 files vs our 10 mandala-level files per `tools/reports/vishvasa_gap_report.md`) — not yet inspected for word-level agreement, and its org page (checked 10 Sep 2026) shows no dedicated Krama-pāṭha or Prātiśākhya repo, so it is a Pada/Saṃhitā cross-check candidate only, not a source for §4a below. |
| Ṛgveda-Prātiśākhya **sūtra text** (Krama-Paṭala + Kramahetu-Paṭala at minimum) | **Done, §4b.** All 1,067 sūtras across all 18 paṭalas are now in `rigveda_pratishakhya/data.json` (the sibling `shaunakiya_chaturadhyayika/data.json` is a separate work, the Atharvaveda-Prātiśākhya, untouched by this import). What's *not* done yet: cross-checking the 258 sūtras with an unresolved source-marked reading against Layers B/C, and turning sūtra text into executable rule logic (§6.1) — this ingestion is text-in-repo, not rules-in-engine. |

**Sequencing implication:** both the Pada-pāṭha and the Prātiśākhya sūtra text prerequisites
are now satisfied (§4b). What building the rule engine still needs, and does not have yet, is
the *interpretation* step — turning cited sūtra text into `conditions`/`action`/`exceptions`
rule logic (§6.1) checked against Layer B or C — not paraphrased or guessed, which is exactly
the kind of un-sourced simplification this document exists to avoid.

**Gemini-cost note (CLAUDE.md standing rule) still applies conditionally:** the Sanskrit
Library XML edition (§4a Layer A) is already machine-readable TEI, so ingesting it is a
parsing task, not an OCR task, and needs no Gemini call. If VedaViṣṭāram's or the RV-
Prātiśākhya project's material (Layers B/C) is only reachable as scanned images at some
point, or if any future archive.org PDF is used as a supplementary check, that step is a
Gemini-calling task and needs a cost estimate + the lead's go-ahead first, exactly as for any
other OCR staging job in this repo.

---

## 4a. Prātiśākhya sourcing — three layers, not one PDF

The first version of this document named a single source (a 1894 archive.org scan) as "the"
digitization source. That was the only one on hand at the time, sourced as a PDF scan
requiring OCR. A better, machine-readable primary source has since been identified and
checked live (10 Sep 2026); use three layers, cross-checked against each other, rather than
trusting any one of them alone:

| Layer | Source | Role | Checked live 10–11 Sep 2026 |
|---|---|---|---|
| **A — canonical base** | Sanskrit Library, *Ṛgveda-Prātiśākhya: First XML Edition*, ed. Peter M. Scharf, 2010, Version 0.1 (`sanskritlibrary.org/catalogsText/fgveda_prAtiSAKya.html`) | Primary machine-readable text | **Pulled and inspected — see §4a.1 below, it's not what the citation implied.** Catalog page confirms the 2010 edition, "Version: 0.1", and "Creative Commons Attribution Non-Commercial Share Alike license" (reuse requires attribution, derivatives under the same licence). The catalog page's own source note credits the underlying digital text to **George Cardona's "First digital edition," Philadelphia, 1993–94** — Scharf's team re-marked it up in TEI. Śaunaka is not named as author on the catalog card itself (traditional attribution, not confirmed from this page). |
| **B — commentary cross-check** | VedaViṣṭāram, `vedavishtaram.in/lakshanam/rp.html` — Śaunaka's text with Uvaṭa's Bhāṣya and Viṣṇumitra's Vṛtti, searchable, sūtra-addressable | Cross-checks Layer A's sūtra text and supplies commentary the XML edition may not carry | Confirmed live 10 Sep 2026 (already used for the chapter map in §2.1) |
| **C — independent validation** | The RV-Prātiśākhya project, `sites.google.com/view/rv-pratishakhya` — Devanagari/Unicode, transliteration, German and English translation, organized by all 18 paṭalas | Third, independently-maintained rendering to catch errors that survive A+B agreeing with each other | Confirmed live 10 Sep 2026 (already used for the chapter map in §2.1) |

### 4a.1 What Layer A actually is, on inspection (11 Sep 2026)

"First XML Edition" describes how the Sanskrit Library's editorial team marked the text up
internally (TEI-tagged), not a file the public can download. The catalog page's "Text"
button calls into `textTranslation.html`, whose scripts (`sl.js`, `sl.model.js`) resolve to
an **undocumented backend JSON endpoint**, reverse-engineered here by reading the site's own
JavaScript rather than found in any published API doc:

```
GET https://sanskritlibrary.org/LoadText?text=fgveda_prAtiSAKya&texttype=forTranslation
```

One full-document fetch (a single GET, equivalent to one normal page load — not a crawl) was
made to inspect the shape, returning a 318 KB JSON object: `{"lines": [...]}`, **1,067
entries**, each one sūtra tagged `sN.M` (paṭala N, sūtra M) followed by its word-tokenized
text in **SLP1 transliteration** (not Devanagari, not raw TEI tags — the TEI markup is not
exposed through this endpoint) plus four scholarly-apparatus fields per sūtra: **Cross
ref./Allusions in [other Prātiśākhya]/Allusions to [other Prātiśākhya]/Parallels/Comments**
— e.g. sūtra 10.14 cross-references Vājasaneyi-Prātiśākhya 1.147 verbatim. Most apparatus
fields in this pass are empty or marked `[?]` (an OCR-uncertainty marker the source itself
uses, also appearing mid-word in a few sūtras) — consistent with the catalog page's own
"Version 0.1" label. **This is a draft edition, not a finished critical text** — cross-
checking against Layers B and C stays mandatory, not a formality.

**Access-ethics note, not just a technical one:** this endpoint is not a documented public
API or download link — it exists to serve the site's own interactive reader. The CC
BY-NC-SA licence is an explicit copyright grant to reuse the *content*, which is more
permissive than most sources already vetted in this repo (contrast GRETIL's per-file "for
reference purposes only" terms that `dge/veda_toolkit/README.md` §3 rejected outright) — but
a copyright licence on the content doesn't by itself settle whether automating bulk requests
against an undocumented endpoint is appropriate use of the site's infrastructure. One
inspection fetch is not that question. **Before scripting a full 1,067-sūtra bulk pull
through this endpoint, get the lead's go-ahead** — the alternative, contacting Sanskrit
Library directly for the actual TEI XML or an export, may be the more respectful path for
anything beyond this kind of one-off inspection, mirroring this repo's existing discipline
of not scraping sites whose terms aren't explicit (`dge/VEDAWEB_IMPORT_STATUS.md`'s stated
boundary).

**Verified sample — real sūtras pulled from Layer A, SLP1 transliterated to Devanagari here
for legibility** (© The Sanskrit Library 2010, Peter M. Scharf ed., CC BY-NC-SA 3.0; source
text per Cardona 1993–94):

| ID | Devanagari (word-separated, no sandhi applied — Layer A doesn't apply it) |
|---|---|
| `RVPr_10.1` | क्रमः |
| `RVPr_10.7` | अन्तःपदम् च येषाम् स्यात् विकारः अनन्यकारितः एतानि परिगृह्णीयात् |
| `RVPr_10.8` | बहुमध्यगतानि च |
| `RVPr_10.9` | अर्धर्चान्त्यम् च |
| `RVPr_10.12` | उपस्थितम् सेतिकरणम् |
| `RVPr_10.16` | समासान् तु पुनर्वचने इङ्ग्येत् |
| `RVPr_10.18` | सन्धिः न अर्धर्चयोः भवेत् |
| `RVPr_10.21` | शौद्धाक्षरागमः अपैति |
| `RVPr_11.19` | चतुःक्रमः तु आचरितः अत्र शाकलैः |

**Correction to this table, made while writing the real importer (§4b): 10.20 and 10.22 were
wrongly shown here as clean Devanagari.** The source marks a character uncertain (`[?]`) in
both — `nakArasya [?]zmavat vfttam ... praSlezaH ca pragfhyasya prakftyA syuH parigrahe .`
for 10.20 (note this is also the *whole* numbered sūtra; the review's quoted clause,
"praśleṣaśca pragṛhyasya prakṛtyā syuḥ parigrahe," is only its second half — the traditional
edition the review's quotes came from apparently numbers that clause on its own, one of the
sub-sūtra-counting differences flagged below) — and `... riPitAni [?]zmaRaH aGoze d[?]BAvaH
svaDitiH iva ca .` for 10.22. An earlier pass through this document guessed `[?]` = ū (a
reasonable-looking guess — `[?]zmaRaH` is almost certainly `ūṣmaṇaḥ` — but a guess, not read
off the source) and printed the guessed Devanagari here without saying so. That was wrong to
do even informally; §4b's actual dataset does not do it, and marks both `has_uncertain_reading:
true` with empty Devanagari/IAST until a human checks Layer B or C.

**This matters beyond confirming the source works:** every one of the sūtras in the table
above is, word-for-word, a sūtra that appeared unattributed and unnumbered in the original
Gemini-derived review that started this whole document. They are real — not fabricated by
that review — and now have exact citations (the catuḥkrama sūtra, for instance, is
specifically **`RVPr_11.19`**, not merely "somewhere in Kramahetu"). That review's instinct
to insist on primary-source verification was correct; this is that verification actually
done — including finding the two places (10.20's truncation, the `[?]` guess) where extra
care was still needed.

**Real paṭala/sūtra counts from Layer A** (vs. the secondary-source table in §2.1 — some
disagree, notably paṭala 2; paṭalas 10 and 11, the ones this document cares most about,
match exactly):

| Paṭala | Layer A count | §2.1 secondary-source count |
|---|---|---|
| 1 | 103 | 102 |
| 2 | 82 | 41 |
| 3 | 34 | 26 |
| 4 | 98 | 94 |
| 5 | 61 | 59 |
| 6 | 56 | 56 |
| 7 | 56 | 55 |
| 8 | 50 | 47 |
| 9 | 52 | 49 |
| **10** | **22** | **22** |
| **11** | **71** | **71** |
| 12 | 26 | 25 |
| 13 | 50 | 48 |
| 14 | 69 | 68 |
| 15 | 33 | 33 |
| 16 | 92 | 88 |
| 17 | 50 | 48 |
| 18 | 62 | 58 |

Total: 1,067 (Layer A) vs. 990 (summing the §2.1 table). The gap is almost certainly a
sub-sūtra/vārttika counting-convention difference between editions (unresolved — not
important enough to block on, since 10 and 11 already agree exactly), except paṭala 2's
82-vs-41 gap, which is large enough to actually check once paṭala 2 (Saṃhitā) work starts.

**Licensing implication of Layer A:** CC BY-NC-SA is non-commercial and share-alike. That is
compatible with DGE's own stated non-commercial preservation/study mission
(`dge/PROJECT_BRIEF.md` §1), but — following the exact discipline `dge/veda_toolkit/README.md`
§3 already applies to every other Veda source in this repo ("absence of a licence is not
permission"; GRETIL's per-file terms were checked and rejected for exactly this reason) —
record Layer A's licence and attribution on the ingested rule data itself (see the `source`/
`crosscheck` fields in the schema below), not just in this document, and do not assume a
different licence for Layers B or C without checking each site's own terms first.

## 4b. Ingestion done (11 Sep 2026) — what's actually in the repo now

The project lead approved the bulk pull ("bulk pull it," 11 Sep 2026). All 1,067 sūtras are
now in `dge/data/vedanga/shiksha/pratishakhya/rigveda_pratishakhya/data.json`, replacing the
empty stub from §4. The importer is `tools/pratishakhya/import_rv_pratishakhya.py`, with the
full methodology in `tools/pratishakhya/SOURCES.md` — that file, not this section, is now the
authoritative record of how to re-run it; this section just summarizes what's true today.

**One deliberate deviation from the per-paṭala file layout sketched in §4a's earlier draft:**
every sibling Śikṣā work in this repo (`paniniya_shiksha/data.json`,
`shodashasloki_shiksha/data.json`, etc.) is one `data.json` per work, with a top-level
`{schema, default_author, source, source_url, licence, note, items}` shape — not a file per
chapter. 1,067 items is not too large for that convention (the Ṛgveda Saṃhitā's mandala files
already hold 2,006 items each), so the actual output follows the house pattern instead of
introducing a new one. `library.json`'s catalog entry is updated to `"populated": true` with
matching `source`/`facets`.

Each item's real shape (not the earlier hypothetical schema — this is what
`import_rv_pratishakhya.py` actually writes, one real entry shown):

```json
{
  "id": "10.7",
  "patala": 10,
  "patala_name": "Krama",
  "sutra": 7,
  "text_devanagari": "अन्तःपदम् च येषाम् स्यात् विकारः अनन्यकारितः एतानि परिगृह्णीयात्।",
  "text_iast": "antaḥpadam ca yeṣām syāt vikāraḥ ananyakāritaḥ etāni parigṛhṇīyāt|",
  "text_slp1": "antaHpadam ca yezAm syAt vikAraH ananyakAritaH etAni parigfhRIyAt .",
  "has_uncertain_reading": false,
  "apparatus": {"cross_ref": "", "allusions_in": "[?]Pr.", "allusions_to": "[?]Pr.", "parallels": "", "comments": ""},
  "has_cross_reference_content": false,
  "domain": "krama",
  "crosscheck": ""
}
```

What's deliberately **not** filled in, and why:

- **`crosscheck`** is empty on every item — it records once a sūtra has actually been checked
  against Layer B or C, and pre-filling it would misrepresent work not done.
- **258 of 1,067 items (24%) have `has_uncertain_reading: true`** and empty
  `text_devanagari`/`text_iast` — wherever the source's own `[?]` marker appears (see the
  correction two paragraphs above §4b for why this document does not paper over that with a
  guess). `text_slp1` always has the raw text, `[?]` included, as ground truth.
- **The `conditions`/`action`/`exceptions` fields from the original hypothetical schema (§6.1)
  are not part of this ingestion at all.** This pull gets the sūtra *text* into the repo,
  cited and attributed; turning a sūtra's text into a rule the generator can execute is
  interpretation, and stays a separate, later step per §6.1's "cite a rule `id`... predicates
  are code that applies those rules, not a second place to restate them."
- **`apparatus`** (cross-references to the Taittirīya-/Vājasaneyi-Prātiśākhyas and to Ṛgveda
  verses) is kept as raw SLP1, not transliterated — it carries its own Vedic-accent notation
  that a plain SLP1→Devanagari pass would corrupt.

Verified with `tests/test_rv_pratishakhya_import.py` (total count, paṭala 10/11 counts, the
nine hand-checked sūtras in the table above, and — explicitly — that 10.20/10.22 are *not*
silently filled in). **Superseded by §4c below** for 10.20/10.22 specifically: they are now
resolved, via VedaViṣṭāram, not left uncertain.

---

## 4c. VedaViṣṭāram cross-check and uncertain-reading resolution (11 Sep 2026)

Done with the project lead's direction to cross-check the uncertain-reading sūtras reliably,
not randomly. `tools/pratishakhya/crosscheck_vedavishtaram.py` (full methodology and its own
limits in its module docstring — read that before trusting anything below) fetches Layer B
(VedaViṣṭāram, `vedavishtaram.in/lakshanam/rp.html` — Śaunaka's text with Uvaṭa's Bhāṣya and
Viṣṇumitra's Vṛtti) and:

1. **Attaches Layer B's sūtra text + Uvaṭa's Bhāṣya to every item** where a same-index entry
   exists (1,007 of 1,067) — new `vedavishtaram_sutra_text` / `vedavishtaram_bhashya` fields.
   This is the raw material §6.1's future rule-logic work will interpret from — not sūtra
   text in isolation, but with the traditional commentary attached.
2. **Resolved 24 of paṭala 10–11's 26 `has_uncertain_reading` sūtras by hand**, each with a
   citation of exactly how (direct VedaViṣṭāram match, or an explicit corpus-internal pattern
   like "pūrva confirmed directly 6+ times elsewhere in this text" — never a silent guess).
   The other 2 (10.3, 11.8) are deliberately still unresolved: 10.3 shows a genuine apparent
   edition variant (VedaViṣṭāram reads `ई` where Layer A implies `ईम्`), and 11.8's uncertain
   word has no independent confirmation anywhere checked. Both carry a `crosscheck` note
   explaining why, not a blank field that looks unchecked.
3. **Resolved 85 more uncertain sūtras outside paṭala 10–11** by an automated same-index
   substring match, accepted only when unambiguous — explicitly *not* trusted with the
   paṭala-10–11-style pattern inference, since the same-index correspondence itself isn't
   verified outside those two chapters (§4a.1's paṭala-2 count mismatch, 82 vs. 41, is exactly
   the kind of boundary drift that makes pattern-based inference unsafe elsewhere).
4. **135 sūtras remain genuinely unresolved** (down from 258) — left that way rather than
   forced, per the same "an empty field is an honest gap" principle as everywhere else in
   this document.

**Two real bugs caught and fixed while building this, not silently avoided:**

- **Sanskrit Library's SLP1 uses lowercase `x` for the Vedic retroflex lateral **ळ**** (only
  found in the Rigveda Śākala tradition), not standard SLP1's vocalic ऌ. This was silently
  mis-transliterating 35 sūtras across the corpus (e.g. `vyAxiH` → the nonsense "व्याऌइः"
  instead of "व्याळिः") since the very first import — caught only while investigating this
  cross-check, confirmed against VedaViṣṭāram's own Uvaṭa Bhāṣya, which spells the word out
  unambiguously as व्याळिः, "the teacher Vyāḷi" (a named phonetic authority, fittingly cited
  in paṭala 3's accent rules). Fixed in `import_rv_pratishakhya.py`'s `transliterate_sutra`
  (remap `x`→`L`, which `indic_transliteration`'s own SLP1 scheme already spells correctly).
- **The automated same-index resolver initially had a real matching bug**: when an uncertain
  character sat at the very edge of its word (an empty "pre" or "post" anchor), an unanchored
  empty-string regex component matched the *leftmost* position satisfying the rest of the
  pattern — which is usually one character early, swallowing everything back to the start of
  the sūtra. Caught concretely on 1.39, which came back as "प्रथमपञ्चमौ च द्वौ
  **प्रथमपञ्चमौ च द्वा** ऊष्मणाम्" (visibly duplicated) instead of the correct
  "प्रथमपञ्चमौ च द्वौ ऊष्मणाम्." Fixed with an explicit word-boundary anchor
  (`(?:^|(?<=\s))`) plus a hard cap on the resolved span length, and guarded by
  `test_algorithmic_resolution_does_not_swallow_neighbouring_words` so it can't regress
  silently.

Both bugs are a reminder that "reliable" here means checked output, not just a fetched
source — every one of the 85 automated resolutions was read over by eye before being trusted
(§4c's table would be too long to reproduce here; see the item list this session produced
while reviewing them, and `tools/pratishakhya/crosscheck_vedavishtaram.py`'s
`P10_11_RESOLUTIONS` table for the paṭala 10–11 reasoning specifically).

---

## 5. Corrected pipeline

```
DGE Pada-pāṭha (once it exists)
        │
        ▼
┌─────────────────────┐
│ STRUCTURAL LAYER     │  ardharca + pada boundaries, word indices
└──────────┬───────────┘
           ▼
┌─────────────────────┐
│ KRAMA RULE ENGINE     │  RV-Prātiśākhya ch.10 (Krama) + ch.11 (Kramahetu)
└──────────┬───────────┘
           │
    ┌──────┴───────┐
    ▼              ▼
ordinary pair   special case (catuḥkrama, parigraha, pragṛhya-in-parigraha, …)
    │              │
    └──────┬───────┘
           ▼
┌─────────────────────┐
│ RV PHONOLOGY LAYER    │  Sandhi (ch.4) · Nati (ch.5) · Dhvanyāgama (ch.6) ·
│                       │  Rephita · Pragṛhya · Pluti (ch.7–9)
│                       │  — a generic sandhi library, if used, is a helper here,
│                       │    subordinate to this layer, never authoritative (§2)
└──────────┬───────────┘
           ▼
┌─────────────────────┐
│ SVARA ENGINE          │  source svara (from Saṃhitā) + derived svara
│                       │  (ch.3 Svara-Paṭala rules) — pracaya, kampa, svarita
│                       │  propagation. Treat any accent-combination matrix as a
│                       │  hypothesis to validate, never as ground truth (§6.2).
└──────────┬───────────┘
           ▼
┌─────────────────────┐
│ VALIDATOR             │  generated vs. an independently attested Krama text
│                       │  (§7) — required before trusting output on new sūktas
└──────────┬───────────┘
           ▼
┌─────────────────────┐
│ RENDERER              │  IAST / Devanagari, colour-by-svara, audio alignment —
│                       │  all downstream presentation, none of it inside the
│                       │  generator itself (§6.4)
└─────────────────────┘
```

---

## 6. Data model

### 6.1 Rule-driven predicates, not static lists

Encode context-sensitive phenomena as predicates over `(word, context)`, backed by named,
citable rules — a static dictionary may accelerate a predicate but must never stand in for
it:

```
isPragrhya(word, context)
isRephi(word, context)
isPluta(word, context)
requiresParigraha(word, context)
requiresCaturkrama(context)
requiresNati(word, context)
requiresDhvanyagama(word, context)
```

Each predicate's non-trivial branches should cite a rule `id` from the ingested sūtra text in
§4b (e.g. `10.20`, matching that file's actual `"id": "patala.sutra"` format — `RVPr_10.20`
below and elsewhere in this document is this document's own citation convention for talking
about a sūtra, not the literal `id` string in the data) — that dataset is the source of truth
for rule text; predicates are code that *applies* those rules, not a second place to restate
them.

Where a dictionary is used as a cache, structure it by the kind of evidence backing each
entry rather than as one flat list, e.g. for Pragṛhya:

```json
{
  "pragrhya": {
    "lexical": [],
    "morphological": [],
    "phonological": [],
    "contextual": [],
    "shakala_specific": []
  }
}
```

### 6.2 Internal accent model — script-independent

Never use a Unicode glyph (Devanagari combining marks, IAST diacritics, or the wrong-block
`॑`/`॒` accent characters) as the semantic representation of svara. Represent
accent as a closed, named enum internal to the data model:

```
udatta | anudatta | svarita | dirgha_svarita | pracaya | kampa
```

(plus any further state the Śākala tradition is found to require once ch. 3 is digitized —
do not assume the list above is complete). Devanagari, IAST, and any pedagogical romanization
are rendering targets computed from this enum at the presentation layer only (§6.4), not
alternate sources of truth.

**Codepoint choice for rendering is a separate, already-burned decision — don't relitigate it
blind.** This repo already hit exactly this problem for udātta/anudātta/svarita:
`dge/veda_toolkit/README.md` §5 records that `indic_transliteration` emits Vedic Extensions
codepoints (`U+1CD3`/`U+1CD9`), which "almost no font supports," and that the working fix was
remapping to the core Devanagari block (`U+0951` svarita, `U+0952` anudātta) via
`dgeSanitizeVedicAccents()`. Unicode's dedicated dīrgha-svarita mark (`U+1CDA`, Vedic
Extensions block) is very likely the same trap — before wiring it into any renderer, test it
against the same fonts `dgeSanitizeVedicAccents()` targets, and if it fails, document
whatever fallback (a doubled `U+0951`, a superscript notation, etc.) is chosen, the same way
the existing svarita/anudātta fix is documented. This is a rendering-layer decision, not an
internal-model one — the `dirgha_svarita` enum value above is unaffected either way.

Each generated token should retain, at minimum:

```
lexicalText, padaText, samhitaText, syllables[], svara[],
sourceSvara[], generatedSvara[], transformationHistory[]
```

### 6.3 Provenance on every generated unit

```json
{
  "source": {
    "samhita": "DGE-RV-SHAKALA",
    "pada": "DGE-RV-PADA",
    "pratishakhya": "Shaunaka",
    "tradition": "Shakala"
  },
  "generated": true,
  "generatorVersion": "krama-0.1.0",
  "rules": ["RVPr_10.1", "RVPr_11.4"]
}
```

`rules` cites Paṭala.sūtra identifiers so a "why was this generated this way" question has a
traceable answer once the sūtra text is digitized (§4) — do not invent sūtra numbers before
that; leave `rules` empty rather than guess.

### 6.4 Strictly out of the generator

- **Colour** is a renderer concern: the generator emits `{"svara": "anudatta"}`; a
  `[data-svara="anudatta"]` CSS rule (or equivalent) does the rest. This lets the colour
  scheme change without touching corpus data, and lets DGE offer normal / svara-marked /
  colour-coded / traditional-notation as display modes on one dataset.
- **Audio timestamps** are a separate alignment system's job, added after the fact against
  `{"pairIndex", "wordIndices", "text", "syllables"}` — not `data-start`/`data-end` baked in
  at generation time. Mixing text generation + phonology + svara + audio alignment + UI into
  one function is exactly the kind of premature coupling to avoid.

### 6.5 Rule logic — done for paṭala 10, and 14 of paṭala 11's sūtras (11 Sep 2026)

`tools/pratishakhya/build_krama_rules.py` writes
`rigveda_pratishakhya/krama_kramahetu_rules.json`: one entry per paṭala 10/11 sūtra (93
total), each citing its sūtra text and, where fully worked out, `conditions`/`action`/
`exceptions`/`examples` grounded in Uvaṭa's Bhāṣya (via §4c's cross-check data). All 22
paṭala-10 sūtras are fully worked out — the base pairing algorithm (10.2), Parigraha's real
scope (10.7–10.9, replacing the naive `word+iti` formula), the `sthita`/`upasthita`/
`sthitopasthita` mechanism that formula was standing in for (10.12–10.14), the ardharca-sandhi
prohibition (10.18), Pragṛhya-in-Parigraha (10.20), Śuddhākṣara-āgama removal (10.21), and
Rephita (10.22). Of paṭala 11, 14 sūtras that directly extend paṭala 10 operationally are
worked out the same way (catuḥkrama, 11.19; the default/ayāvana case, 11.22–23; the parigraha
phonetic-reversion block, 11.36–46; the sthitopasthita confirmation, 11.61); the remaining 57
are classified (domain/rule type/one-line summary) but not reduced to executable logic — most
of that material is rationale, historical lineage (11.65 names Prabāhravya as Krama's first
teacher), or grammarians' debate about *why* the rules are as they are, not new operative
content. Every entry says explicitly what it rests on (`basis`) and carries
`"validated_against_attested_krama": false` — this is this session's interpretation of the
Bhāṣya, not independently checked against any attested Krama-pāṭha output; §7's VALIDATE mode
is the next real gate, still blocked on §10's open question about a ground-truth source.
Checked by `tests/test_krama_kramahetu_rules.py`.

---

### 6.6 Real generator engine, computing from Pada-pāṭha directly (Phase 8, 11 Sep 2026)

Built in direct response to the project lead's own detailed spec document
(`DGE_RIGVEDA_KRAMA_CLOUD_CODE_UPDATED_SUTRA_AND_COMPARATIVE_SPEC.md`, 11 Sep 2026), whose
core finding was correct: `generate_krama_rv_1_1.py` (§4b/6.5's predecessor) contained
hardcoded `pairs = [...]` and a hand-typed `PARIGRAHA_FORMS` dict per verse — it proved the
rules could be *labelled* onto manually prepared RV 1.1 text, not that they could *generate*
arbitrary Pada-pāṭha input. Three new modules replace that approach:

- **`tools/pratishakhya/sanskrit_phonology.py`** — a real sandhi engine (`samhita_join`,
  `resolve_compound`) covering Paṭala 2's vowel classes (savarṇa-dīrgha, guṇa, vṛddhi, yaṇ,
  eṅ-a elision) and Paṭala 4's visarga/consonant rules (sa/eṣa exception, i/u/diphthong-class
  visarga, a-class visarga with sibilant assimilation, word-final m/n/t). Validated to 69/70
  (98.6%) exact match against DGE's own attested `samhita_patha` across every actual word pair
  in RV 1.1 — the one non-match is the 10.3 आ-exception case, out of this module's scope by
  design (that's a Krama-Paṭala structural rule, not a segmental phonology rule).
- **`tools/pratishakhya/pratishakhya_classify.py`** — predicates (`is_pragrhya`, `is_rephi`,
  `parse_compound`, `requires_parigraha`, `get_sthita`/`get_upasthita`/`get_sthitopasthita`,
  `is_monosyllable_avasana`), replacing the flat Pragṛhya/Rephi word-lists the rejected draft
  used. Each predicate's docstring states plainly what it still cannot derive (e.g. `is_rephi`
  is a cache of forms already confirmed rephita, not a phonological derivation from an
  arbitrary word — a real, named limitation, not silently assumed solved).
- **`tools/pratishakhya/krama_engine.py`** — `generate_ardharca`/`generate_verse`, the actual
  generator loop: base pairing via `samhita_join` (10.2), Parigraha triggering via
  `requires_parigraha` (10.7–10.9) rendered via `get_sthitopasthita` (10.12–10.14, 10.16), and
  a computational reconstruction of sūtra 10.3's monosyllable-avasāna exception (see below).
  `split_into_ardharcas()` finds each verse's ardharca boundary automatically, using DGE's own
  attested `samhita_patha` only as a length-alignment oracle for *where* the boundary falls
  (never to look up pair *content* — every pair is still computed independently by
  `samhita_join`); it gets 7 of RV 1.1's 9 verses right unaided, with 1.1.7 and 1.1.9 as
  logged manual overrides (`ARDHARCA_SPLIT_OVERRIDES`), not silent substitutions.

**Sūtra 10.3's आ-exception**, the spec's stated "single highest-priority special-case test":
reconstructed from Uvaṭa's own worked example (`आ मन्द्रम् । मन्द्रमा वरेण्यम् । आ वरेण्यम्`)
as a general condition — when the word about to be retaken for its next pair was immediately
preceded by a monosyllable-avasāna word, replace the ordinary retake-pair with a tri-unit
(retaken-word + monosyllable, joined via sandhi, + next word) plus a separate confirming pair
(monosyllable + next word). `krama_engine.py`'s own `__main__` self-test reproduces Uvaṭa's
example exactly; `validate_krama_rv1_1.py`'s Test D (below) confirms the same computationally,
not by construction from the example itself.

**`tools/pratishakhya/regenerate_krama_rv_1_1.py`** runs this pipeline directly against
`dge/data/vedas/rigveda/shakala_shakha/samhita/mandala_01/data.json` (items 1.1.1–1.1.9,
`pada_patha`/`samhita_patha` fields only — no per-verse word list is typed anywhere in this
script) and compares its output unit-by-unit against the old hand-aligned
`krama_generated_output.json`, writing both the new output and the comparison to
`krama_regenerated_output.json`. Result: **7 of 9 verses match the old output exactly**
(1.1.1, 1.1.3, 1.1.4, 1.1.5, 1.1.6, 1.1.8, 1.1.9). The 2 that differ are both informative, not
regressions:

- **1.1.2**, ardharca 2 (`सः देवान् आ इह वक्षति`): the new engine detects that इह's preceding
  neighbour, आ, is a monosyllable-avasāna — structurally the *same* configuration as Uvaṭa's
  own example — and fires the 10.3 tri-unit reconstruction (`इहा वक्षति` / `आ वक्षति`) instead
  of the old code's un-flagged ordinary pairing (`इह वक्षति`, admitted `"confidence": "low"` in
  the old output precisely because it knew this was an आ-adjacent case it wasn't handling).
  This is the new engine doing what the old one explicitly flagged as unhandled — an
  improvement, not a mismatch to fix, though it rests on generalizing from *one* attested
  example to a second, structurally identical case, which is a real (documented, not hidden)
  interpretive step, not a certainty.
- **1.1.7**, ardharca 2, one unit (`भरन्तः` + `आ`): the new engine's classical a-class-visarga
  rule gives `भरन्तो आ` (visarga → ओ, आ kept separate, per the general Paṭala-2/4 rule for
  visarga before any vowel other than short अ). DGE's own attested continuous `samhita_patha`
  for this exact environment reads `भरन्त एमसि` — i.e. the visarga is dropped *entirely*
  (not converted to ओ) before this आ. Neither this engine's classical output nor the old hand
  -aligned guess (`भरन्तो`, which silently swallowed the आ with no cited rule) matches that
  attested form. **This is a genuine, open gap**, most likely a Vedic-specific visarga-lopa
  variant (the Prātiśākhya's own `bahulaṃ chandasi` latitude) not yet covered by any rule in
  `krama_kramahetu_rules.json` — flagged here rather than patched with an unverified ad hoc
  rule. Left for whoever picks up Priority-1 item 10.20/10.22-adjacent visarga work; see
  `tools/pratishakhya/validate_krama_rv1_1.py`'s Test F for the same kind of Saṃhitā-vs-Pada
  restoration gap this belongs to.

**`tools/pratishakhya/validate_krama_rv1_1.py`** implements the spec's own Test A–H suite
(sec.21) in the exact required per-test format (sec.22: INPUT PADA / EXPECTED / GENERATED /
STATUS / APPLIED RULES / TRANSFORMATIONS / WHY). Tests A–E (ordinary pairing, compound
Parigraha, ardharca-final Parigraha, the 10.3 आ-exception, no cross-ardharca sandhi) **PASS**
against the real engine — not against hand-picked examples designed to pass, since Tests A–C
and E use fresh word combinations not copied from RV 1.1's own verses. Tests F (Saṃhitā-vs-
Pada restoration on retake, 10.21/11.23), G (bahumadhyagata auto-discovery, 10.8), and H
(Śuddhākṣara restoration, 10.21/11.37–43) are reported **UNRESOLVED**, each with the specific
missing function named (`restore_shuddhakshara`/`resolve_rephi` derivation,
`detect_bahumadhyagata`, a restoration-on-retake mechanism in `samhita_join` or a layer above
it) — these are Priority-0 item 4/5 and Priority-1 items 8/10/12 from the spec's own priority
order (sec.23), not yet built, and not claimed to be.

**Not yet done, honestly**: the old `generate_krama_rv_1_1.py` and its `PARIGRAHA_FORMS`/
`VERSES` hardcoded data have not been deleted — the spec's stated success criterion ("obtain
the same result... regenerate RV 1.1 entirely") is now satisfied for 7/9 verses with the other
2 understood and documented above, which is close enough to justify treating the old file as
superseded, but it is being left in place one more round in case the lead wants to review the
1.1.2/1.1.7 discrepancies first. Full-Rigveda scaling has not started, per the spec's own
"only after that" gate.

---

### 6.7 Second review pass (11 Sep 2026, "chatgpt review") — epistemic auditability

The lead forwarded a second, independent review (ChatGPT) of §6.6's first regenerated-output
run, arguing the deeper problem was not the individual wrong strings but that the JSON gave no
way to tell canonical output from a guess, or a checked fact from an unchecked one — 16 numbered
points. Two things came out of actually checking each one against the code and data, not just
the review's prose:

**The review's count claim was itself wrong, but the underlying worry was right.** It stated
`pada_count` should be 89, not 88, and that `pair_count`(69) vs. `ardharca_count`-implied 70
pairs was a bug. Recomputing directly from the shipped JSON: `pada_count` (88) is exactly the
sum of every ardharca's word list — correct. The `pair_count`/boundary gap is not a bug either:
one ardharca's 10.3 tri-unit legitimately *replaces* an ordinary pair at that boundary (69
pairs + 1 tri-unit = 70 boundaries, exactly). Both counts were right, but *neither was provable
from the JSON itself* — there was no visible arithmetic tying them together, so a careful
reader reasonably suspected a bug that wasn't there. **Fixed**: `regenerate_krama_rv_1_1.py`'s
`build_counts()` now asserts this invariant explicitly (raises if it ever stops holding) and
ships the formula and both operands as an `invariant_check` object in the output, rather than
presenting bare numbers on trust.

**Genuinely new, addressed this pass:**
- **"confidence" was being read as "verified correct"; it never meant that.** Every unit now
  carries three independent fields, documented in `krama_engine.py`'s own module docstring so
  the distinction can't be lost again: `"status"` (`"canonical"` — the general rule engine
  applied uniformly — vs. `"candidate_reconstruction"` — this session's own generalization of
  a single cited example, currently only the 10.3 units), `"confidence"` (unchanged: how sure
  the phonology classifier is it picked the right branch — a claim about the classifier, not
  the Vedic form), and, per-ARDHARCA (not per-unit — see below), a `"chain_reconstruction"`
  field from a real VALIDATE-mode check.
- **Parigraha's rendering was undifferentiated.** Every Parigraha unit now states
  `"retake_state": "STHITOPASTHITA"` explicitly (10.14 — combined+iti+split together) instead
  of leaving which sūtra-named state fired implicit in which function happened to be called.
  `get_sthita`/`get_upasthita` (10.12/10.13) as *distinct* renderings, rather than components
  of sthitopasthita, remain unexercised by any case found so far — stated as an open scoping
  question, not silently assumed unnecessary.
- **Reasons were flattened into an undifferentiated sūtra-number list.** Parigraha units now
  also carry `"trigger_reasons"`: `["avagrhya_compound"]`/`["bahumadhyagata"]`/
  `["ardharca_final"]`, human-readable, alongside (not replacing) the sūtra citations.
- **The comparison report cascaded one real difference into many spurious-looking ones.**
  `compare_against_old()` now keys by `(ardharca_index, unit_index_within_ardharca)` instead of
  one flat per-verse index, so a difference in ardharca 2 no longer makes every later unit in a
  different ardharca look wrong.
- **A real, working VALIDATE-mode check was built, and building it caught two real bugs.** The
  review's point that "reproducing DGE Saṃhitā ≠ philologically correct" was already understood
  (§6.6, §7), but no actual per-unit check had been implemented yet. A first attempt — comparing
  each isolated 2-word Krama pair against the continuous samhita text via substring match — was
  itself wrong and is NOT what shipped: a word's Krama pair reflects only its immediate partner,
  but its form in the continuous text is often governed by a *different, later* neighbour, so
  most "mismatches" that check produced were expected divergences, not bugs. The correct check —
  `sanskrit_phonology.reconstruct_chain()`, folding `samhita_join` across a WHOLE ardharca to
  simulate how continuous text is actually built, then diffing against DGE's attested
  `samhita_patha` — is what `regenerate_krama_rv_1_1.py`'s `attest_ardharcas()` now runs, and it
  found:
  1. **A real bug**: `resolve_compound()` was misfiring on a chained string's own
     elision-avagraha (e.g. "sūnave'gne", ordinary Sanskrit orthography for an elided medial
     vowel — not a Pada-pāṭha compound marker), collapsing every space built up in the chain so
     far. Fixed via `samhita_join`'s new `resolve_w1_compound` parameter (`generate_ardharca`'s
     own per-pair calls are unaffected — they always pass a fresh bare pada word as w1, where
     the old default behaviour is correct).
  2. **A second real bug**: the lexical-exception tables (`IRREGULAR_VISARGA_STEMS`,
     `IRREGULAR_LENGTHENING_BEFORE_CONSONANT`) matched only a bare word, silently failing to
     fire for that same word occurring anywhere but the very start of a chain. Fixed via
     `_match_lexical_suffix()`.
  3. **A confirmed, still-open bug**, precisely diagnosed rather than patched: the
     `indic_transliteration` SLP1 scheme cannot distinguish "र्ऋ" (bare consonant, then an
     independent vowel) from "रृ" (that consonant with a dependent vowel-matra) — both collapse
     to the identical SLP1 "rf". `_finish_consonant_then_vowel()`'s existing workaround survives
     exactly one join; a second hop through this module loses it (RV 1.1.2's chain: "...bhi-r-
     R.si..." → "पूर्वेभिरृषिभिः", missing its virama, instead of "पूर्वेभिर्ऋषिभिः"). Left
     unresolved rather than rushed — see `sanskrit_phonology.py`'s module docstring for the
     exact repro.
  4. **One already-known, still-open gap**, now independently reconfirmed by the SAME
     mechanism: RV 1.1.7's visarga-before-आ (§6.6's original finding). After the two fixes
     above, chain reconstruction now matches DGE's attested text on **16 of 18 ardharcas**
     (the remaining 2 are exactly bugs 3 and 4 above — nothing else).

**Explicitly NOT attempted this pass** — real, substantial, correctly-identified gaps that need
dedicated engineering, not a rushed patch layered onto already-uncertain philology:
- A real Kramahetu (Paṭala 11) *evaluation* engine that decides between ordinary/dvikrama/
  trikrama/pañcakrama, rather than only ever emitting `"10.2"` for ordinary pairs. `krama_engine.py`
  already states in its own docstring that only a slice of Paṭala 10 plus the 10.3 exception is
  implemented; the review's ask for an explicit `"krama_decision"` object naming which Paṭala-11
  sūtras were checked and why none fired is directionally right but has not been built.
- A `restore_*` family (Prakṛti restoration on retake, Śuddhākṣara, Rephī/Uṣman derivation) as
  genuine state transitions — Test F/G/H in `validate_krama_rv1_1.py` already report these
  UNRESOLVED (§6.6); this pass didn't change that.
- A structured, syllable-level Svara object with transformation provenance — explicitly out of
  scope per §6.4/architecture Priority 3; accents are stripped, not modelled, at this stage.
- A full transformation-history object per unit (`{"input": {...}, "phonology": [...], "krama":
  {...}, "output": ...}`) for every nontrivial unit — a real, worthwhile idea; a lighter version
  exists already (`phonology_rule` cites the fired rule, `w1`/`w2` are on the raw `samhita_join`
  return dict though not yet threaded into the shipped JSON's units) but the full structured
  object was not built.
- Deriving ardharca boundaries from authoritative structure instead of the length-alignment
  heuristic. Checked directly against DGE's own data during this pass: `pada_patha` uses the
  SAME `।` separator between every word AND at the ardharca boundary — it does not mark the
  boundary distinctly from an ordinary inter-word split — so there is no more authoritative
  signal already sitting in this repo's data to switch to; a real fix needs either deriving
  pada-counts from the `chandas` field per meter (itself unverified against real editions) or
  an external attested source. The two manual overrides stay logged as exactly that, not solved.
- Auditing every lexical exception's citation as the review's point 16 asks (`basis`, sūtra,
  commentary, generalizes-or-not) — the code comments already state provenance reasonably well
  (e.g. `IRREGULAR_VISARGA_STEMS`'s comment cites the exact attested form and verse it came
  from) but this is not yet surfaced as a structured field in the output JSON itself.

---

### 6.8 Third round (11 Sep 2026) — a self-contained code+data task prompt, verified against
    this repo's own primary sources before acting on any answer

Sent a self-contained prompt (embedded code, sūtra text, and two failing test cases — no repo
access needed) to Gemini and ChatGPT, asking for (A) a concrete patch for the SLP1 र्ऋ/रृ
collision, (B) three narrow philology questions, (C) an open-ended critique. Both answered; the
discipline applied here was the same as every round before it — **verify each claim against
this repo's own already-ingested primary sources before adopting it**, not accept either
answer on authority. That check caught a real citation error even in an otherwise-correct
answer (below), which is exactly why this discipline is not optional.

**Adopted, verified, and shipped:**
- **Gemini's Task A fix (ZWNJ marker) works, confirmed empirically, not just plausible.**
  Inserting U+200C (zero-width non-joiner) at the boundary in
  `_finish_consonant_then_vowel()`, and stripping it only at true output boundaries (a new
  `strip_zwnj_markers()`, called by `reconstruct_chain()`'s own return and by every place
  `krama_engine.py` turns a `samhita_join` surface into final unit text or a length
  measurement), was tested directly: a synthetic 4-hop chain of `f`/`F`-triggering joins in a
  row preserves the boundary correctly at every hop (not just the 2 hops the original bug
  report showed) before this was accepted, matching what the review round that requested this
  fix (§6.7) explicitly demanded ("demonstrate the fix survives N consecutive joins, not just
  one"). Chain-reconstruction validation went from 16/18 to **17/18** ardharcas exactly
  matching DGE's attested text as a direct result.
- **A second, independent real bug**, found via the same external round but confirmed against
  standard Pāṇinian grammar (6.1.78 *eco'yavāyāvaḥ*) rather than either AI's authority alone:
  `samhita_join`'s diphthong-before-non-a-vowel branch kept the diphthong unchanged and merely
  *appended* a glide after it (e.g. `vane`+`indraḤ` → `वनेयिन्द्रः`, an extra vowel), instead of
  *replacing* e/o/ai/au with a/a/A/A + the glide (correct: `वनयिन्द्रः`). Fixed; no RV 1.1 test
  case happened to exercise this branch before, which is exactly why it went undetected across
  two prior review rounds.

**Checked and found already fixed (not new bugs) — reported back rather than "fixed" twice:**
- Gemini's "Avagraha Collision" (Task C): reproduced the exact scenario described
  (`devaH`+`atra`→`devo'tra` mid-chain, then continuing the chain further) directly — it
  already works correctly, because `reconstruct_chain()`'s `resolve_w1_compound=False` fix
  from the *previous* round (§6.7) already covers any embedded elision-avagraha regardless of
  which rule produced it, not only the one case that round happened to find first.
- Gemini's "Accent Stripping Fragility" (Task C): tested directly — `deva_to_slp1` passes Vedic
  accent marks (U+0951/U+0952) through completely unchanged as literal combining characters, it
  does not convert them to any ASCII SLP1 equivalent, so `strip_accents_slp1` finding them
  *after* transliteration (the existing order) works correctly. This claim was checked and
  found to not hold.

**Checked and found a real error in an otherwise-good answer:** Gemini's Q2 answer (does
ordinary sandhi apply between a word and "iti" in sthitopasthita, except for pragṛhya words)
cited **"RPr 1.74"** for "vocative 'o' is pragṛhya." This project's own already-ingested,
VedaViṣṭāram-sourced corpus was checked directly: **1.74 is "upottamaṃ nānudāttaṃ na padyam"**
(an accent-placement rule, unrelated) — the actual sūtra stating "ओकार आमन्त्रितजः प्रगृह्यः"
("the vowel o arising from vocative is pragṛhya") is **1.68**. The underlying substantive claim
is independently well-supported by this repo's own data even so — 1.68 states exactly that
rule, and 1.73 ("asme yuṣme tve amī") matches this project's own already-implemented
`PRAGRHYA_LEXICAL_SLP1` class exactly — but the citation itself was simply wrong, and would
have been repeated uncritically if not checked. **Not yet implemented**: this Q2 answer implies
`get_sthitopasthita()`'s current unconditional no-sandhi rendering is wrong for any
non-pragṛhya Parigraha word (e.g. `पुरोहितम्` + `इति` should arguably fuse to `पुरोहितमिति`,
not stay `पुरोहितम् इति`, since पुरोहितम् isn't pragṛhya) — a real, high-impact claim if true,
but inferred rather than directly cited (both of this project's own attested examples,
`vibhāvaso` and `bāhū`, happen to be pragṛhya words, so their showing no sandhi doesn't prove
sandhi is required elsewhere; it's equally consistent with "no sandhi ever, regardless"). Left
as an explicitly open, sharpened question rather than silently rewriting Parigraha rendering
for all of RV 1.1 on an inference — see §10.

**Checked and NOT adopted** — Gemini's Q3 answer ("RPr 2.27" licenses full visarga-lopa before
ā): this project's own ingested Paṭala 2 corpus (which for most of Paṭala 2 has only a
`vedavishtaram_sutra_text` field with `has_uncertain_reading: true`, not a fully cross-checked
entry like Paṭala 10–11's) was checked directly. Sūtra 2.27's actual text
("hrasvapūrvas tu so 'kāram") and its neighbours (2.24: "visarjanīyo 'raphito dīrghapūrvaḥ
svarodayaḥ ākāram") appear to describe how visarga-preceded-by-long-vs-short-vowel contributes
an "ā"/"a" sound in deriving the GENERAL a-class visarga→o outcome already implemented — not a
special *full-elision* rule specific to a following ā, as Gemini's paraphrase claimed. This
does not confirm Gemini is wrong, only that the claim doesn't clearly hold up against this
repo's own primary text, given the sūtra's own uncertain-reading flag and lack of a
cross-checked Bhāṣya gloss for Paṭala 2 (only Paṭala 10–11 have had that cross-check pass, per
§4c). **No code change made** on this basis — RV 1.1.7's visarga-before-आ gap remains
genuinely open, now sharpened with a specific citation to check rather than resolved.

**Checked and NOT adopted (ChatGPT's Task C additions)**: ChatGPT's own follow-up critique
(reviewing the prompt before it was sent, not reviewing an answer) raised further points,
mostly already covered by the fixes above (the r/f collision "is a state-representation bug",
addressed by the ZWNJ marker — a scoped fix, not the full internal phonological representation
ChatGPT argued for; the risk that other Devanagari round-trip ambiguities exist beyond r/f,
noted as a real, general risk this fix's *pattern* — mark-at-creation, strip-at-final-output —
generalizes to if found, not proven exhaustively covered), plus items requiring real sūtra
research not attempted this pass: the `t`+vowel and `t`+voiced-consonant branches being "too
broad" (plausible — Paṭala 4's actual conditions for `t`-assimilation are more specific than
"any voiced consonant," but this project hasn't cross-checked Paṭala 4's own sūtra text against
these branches yet, so no change was made rather than guess); `YAN_OF`'s dissimilar-vowel
condition being "too generic" a stand-in for named Vedic classes (already stated as a known,
explicit gap in `sanskrit_phonology.py`'s own module docstring — praśliṣṭa/kṣaipra/abhinihita/
prakṛtibhāva are named as out of scope there); and lexical exceptions being checked before
general phonological classification (a fair architectural point — the exception tables ARE a
priority-ordered override, by design, since they exist precisely to catch attested
irregularities the general rules would otherwise misfire on — but reordering this without a
concrete failure case it currently causes was not attempted).

---

### 6.9 Fourth round (11 Sep 2026) — Gemini's Round 2 answer, then a Claude-authored critique of
    it, both checked directly rather than either trusted

The lead relayed Gemini's answer to the Round 2 prompt (§6.8), plus a document (apparently
another Claude session's review of that answer) arguing Gemini's D2 conclusion should be
rejected. Rather than trust either verdict, every checkable claim was reproduced directly.

**Gemini's D1 (10-join survival) was correct and is now the permanent test.** Verified Gemini's
own proposed test runs and passes against the real engine exactly as claimed.
`tests/test_krama_engine.py`'s `test_zwnj_marker_present_after_every_one_of_10_consecutive_joins`
now asserts the ZWNJ count after *every* individual join (not just comparing the final result,
which the critique document correctly pointed out was a weaker test than the prompt asked for).

**Gemini's D2 conclusion ("the rf collision is a unique artifact... no other collisions exist")
was checked directly and found FALSE — the critique document's core objection is correct.**
Built the exact collision matrix the critique proposed
(`tests/test_krama_engine.py`'s `SLP1BareConsonantVowelCollision.
test_collision_exists_for_every_vowel_class_not_only_vocalic_r`) and ran it: a bare consonant
before an independent vowel letter transliterates identically to that consonant with a
DEPENDENT vowel-matra, for **every** vowel class (अ/इ/ई/उ/ऊ/ए/ऐ/ओ/औ/ऋ/ॠ), not only vocalic r/rr.
Gemini tested anusvāra/candrabindu, avagraha, and vowel length (all genuinely collision-free,
confirmed) but never tested the specific category the prompt named — "other independent-
vowel-after-consonant cases" — and drew a general conclusion its own tests didn't support.

**But the critique document's implied next step (audit `_finish_consonant_then_vowel`'s scope
for a real defect) was also checked directly, not assumed either way — and no defect was
found.** A transliteration-level collision existing for every vowel does not by itself mean
this engine's choice to special-case only f/F is wrong; the real question is whether letting
every other vowel fall through to the default (dependent-matra) rendering ever produces WRONG
output. Checked against DGE's own attested Samhita-patha, character-by-character (not assumed):
RV 1.1.2 has three real (not synthetic) examples of a visarga-derived consonant immediately
before a vowel — "र्+ऋ" (needs the independent form, the one case already handled), "र्+ई"
(attested as "री", dependent matra — matches this engine's existing default) and "र्+उ"
(attested as "रु" in "नूतनैरुत", dependent matra — also matches the default). All three
confirmed by direct Unicode codepoint inspection of the source data, not inferred. This is a
genuine, if limited (3 data points, one text), Devanagari **typesetting** convention specific
to vocalic r/rr's dependent-matra glyph (likely because ृ is small and easily lost under Vedic
accent marks, unlike the larger ि/ी/ु/ू/े/ो), not an SLP1-level property — so `_finish_
consonant_then_vowel`'s scope was not widened speculatively (per the critique document's own
correct instruction: "do not patch this speculatively" / "only fix reproduced defects"). Both
`sanskrit_phonology.py`'s module docstring and `_finish_consonant_then_vowel`'s own docstring
were corrected to state this accurately (the earlier, too-narrow "uniquely ambiguous" framing
was itself part of what needed fixing here).

**E1/E2/E3: the critique document's procedural read (require exact citations, mark UNRESOLVED
without one) is the correct discipline and was already this project's own standard before the
document arrived** — §6.8 already declined to adopt Gemini's Q3 citation for the same reason.
One place the critique document overreached: it dismissed Gemini's E3 invocation of Pāṇini
8.3.17/8.3.19 ("lopaḥ śākalyasya") as inadmissible purely because it wasn't in the supplied RPr
excerpt. That procedural point is fair for judging whether Gemini followed *that specific
prompt's* rule, but 8.3.19 is a real, well-known sūtra, and its namesake ("Śākalya") is
literally this recension's own name (Ṛgveda **Śākala** śākhā) — dismissing it outright loses a
promising, checkable lead rather than filing it as one. Recorded in §10 as a citation to
investigate (does 8.3.17's precise condition — a visarga from final "-as", "apūrvasya",
specific word classes — actually cover भरन्तः, a plain -तस् nominative?) rather than either
adopted or discarded.

---

### 6.10 Paṭala 2 cross-check against VedaViṣṭāram (11 Sep 2026) — done directly, no external
     prompt

The lead asked for the Paṭala 2 cross-check (flagged as a likely one-pass fix for both the
RV 1.1.7 visarga gap and the word+iti sandhi question — §6.8/§10) to be run directly rather than
via another external prompt. Done by hand, the same way Paṭala 10–11 were (§4c), not by
re-running the existing script unchanged — the existing `algorithmic_resolve()` path had already
tried and failed on several of these, and a proper cross-check meant finding out *why* and
fixing what could be fixed with real evidence.

**The headline finding: the "82 vs 41/42 sutra count" gap noted back in §4a.1 is not a numbering
bug — it's a chapter-scope difference.** VedaViṣṭāram's own Paṭala 2 page content stops dead at
sutra 42; its Paṭala 3 is the *accent* chapter (confirmed: its opening sūtras are about
āyāma/viśrambha/ākṣepa and udātta/anudātta/svarita), not a continuation of Layer A's Paṭala-2
sūtras 43–82. Those 40 sūtras (worked Vedic-verse citations illustrating sandhi patterns, then a
distinct block of Pragṛhya rules at 2.51 onward, then a closing note attributing a reading to
"Śākalya the elder") have **no VedaViṣṭāram counterpart at all** under this URL and remain
entirely uncross-checked by this source — a real, separate gap from what could be closed today.

**Within sūtras 1–42, the correspondence is genuinely reliable**, more so than the module's
earlier "not verified outside paṭala 10–11" caution implied. Checked systematically (not
spot-checked): comparing Layer A's own independent transcription against VedaViṣṭāram's,
character for character, across the full range. The overwhelming majority of what looks like a
divergence is not a content disagreement at all — **Layer A presents each sūtra's words
un-sandhi'd (pada boundaries kept separate); VedaViṣṭāram presents the same sūtra continuously
sandhi-joined** (e.g. Layer A's "ataḥ anyāḥ" = VedaViṣṭāram's "ato'nyāḥ" — the identical words,
ordinary a-class-visarga-before-a sandhi applied). A few positions where VedaViṣṭāram's own page
independently drops a trailing visarga (2.20, 2.29, 2.30) look like small scan/rendering slips on
its side, not something to import into Layer A, which already has the visarga present correctly.

**Five previously-uncertain sūtras in this range were resolved with real evidence, extending
`crosscheck_vedavishtaram.py`'s hand-verified-table pattern to a new `P2_RESOLUTIONS` table
(mirroring `P10_11_RESOLUTIONS`, kept separate rather than merged so its scope stays honest):**
- **2.8, 2.27**: the recurring "pūrva" pattern — 2.27 by a *direct* VedaViṣṭāram match (sandhi-
  joined as "pūrvastu", which is exactly why the automated `algorithmic_resolve()` missed it
  before: its word-boundary anchor assumed a space that VedaViṣṭāram's sandhi'd rendering
  doesn't have), 2.8 by the pattern now independently confirmed 4 times within this same paṭala.
- **2.33**: three `[?]` resolved — one by direct VedaViṣṭāram match, two by the standard,
  independently well-attested Sanskrit phonetics term "pūrva-rūpa" (a recognized sandhi-outcome
  category alongside guṇa/vṛddhi/para-rūpa), not sourced from VedaViṣṭāram for those two.
- **2.36**: a different KIND of resolution, not "pūrva" — VedaViṣṭāram's own page renders this
  exact position as a literal ZERO WIDTH NON-JOINER character (U+200C), not text. This is
  VedaViṣṭāram's own site-side corruption of an avagraha, the identical artifact independently
  found at the corresponding position in its own sūtra 2.24 (both are ordinary
  a-class-visarga-before-a elisions). Resolved as an avagraha, not a missing letter — and this
  reading is independently grammatically sensible on its own terms, not merely inferred from the
  artifact matching.
- **2.40**: checked and left genuinely unresolved — VedaViṣṭāram's own numbered div for this
  sūtra is a much shorter tail excerpt that doesn't reach the position of the uncertain
  character at all. No independent confirmation exists; not guessed.

Also fixed a real, pre-existing bug in `crosscheck_vedavishtaram.py` found while re-running it
for real: `data["note"] += (...)` was unconditional, so a second run duplicated the whole
cross-check sentence verbatim. Now dedupes by splitting on a marker before appending.
`vedavishtaram_index_verified` is now `true` for Paṭala 2 sūtras 1–42 too (checked by hand, not
assumed), still `false`/absent for 43–82 (no VedaViṣṭāram data exists to check them against).

**The original question this was meant to help answer — RV 1.1.7's visarga-before-आ gap
(sūtras 2.24/2.27) — is NOT resolved by this pass, and that's a real, honest result, not a
failure of the method.** VedaViṣṭāram carries **no Bhāṣya at all** for this region (checked
2.23–2.28 explicitly: every `bhashya` field is empty). The sūtra *text* itself is now fully
confirmed clean (matches VedaViṣṭāram exactly, no OCR uncertainty), but the *interpretive*
question — does 2.24/2.27 describe a general visarga→o/ā derivation step, or something closer
to Gemini's claimed full-elision-before-ā reading — still has no commentary to settle it via
this source. Needs either the Sanskrit Library's own critical apparatus (if it has translation
notes not yet pulled into this corpus) or a genuinely different secondary source.

**A second, more promising, and completely unexpected lead surfaced instead**, sitting in the
40-sūtra block VedaViṣṭāram doesn't cover at all: **sūtra 2.51, "prakṛtyā itikaraṇādau
pragṛhyāḥ"** ("[words] before iti-karaṇa [remain in their original form], being pragṛhya") —
this reads as if it could be directly, generally answering the still-open Q2 question (does
ordinary sandhi apply to word+iti, except for pragṛhya words?) by making words-before-iti
pragṛhya *by virtue of* preceding iti, not merely coincidentally pragṛhya for an unrelated
reason. **This is not being acted on.** The immediately following sūtras qualify it in ways this
session cannot confidently parse without a commentary: 2.52 ("svareṣu ca ārṣyām" — "and in
vowels, in the Ārṣī/Ārṣa [tradition/reading]?") may restrict 2.51 to vowel-final words under a
specific named tradition rather than stating a universal rule; 2.54's "sahodayāḥ ... sarvatra
eva" and 2.55's "tryakṣarāntāḥ tu na ive" add further conditions and an exception whose precise
scope is genuinely unclear without expert grammatical parsing or a gloss (this corpus has none
for this region — checked, `apparatus.comments` is empty for all of 2.51–2.59). Treating this as
settling Q2 without that parsing would repeat exactly the mistake this whole project has been
correcting other reviewers for. Flagged in §10 as a real, specific, well-scoped next question —
NOT implemented as a change to `get_sthitopasthita()`.

No code in the Krama generator itself changed as a result of this pass — only
`crosscheck_vedavishtaram.py` (the new table, the note-duplication fix) and the underlying
`rigveda_pratishakhya/data.json` (5 sūtras' text filled in, `vedavishtaram_index_verified`
extended). Four new tests in `tests/test_rv_pratishakhya_import.py` cover the new resolutions
and the verified-range boundary.

---

### 6.11 Layer C spot-check on the RV 1.1.7 gap (11 Sep 2026) — sharpens the question, doesn't

close it

Self-directed follow-up to §6.10, no external prompt: fetched Layer C
(`sites.google.com/view/rv-pratishakhya/home/rvpr-2`) for its transliteration/English gloss of
2.24 and 2.27, as a third independent source on the still-open RV 1.1.7 visarga gap. Also
checked whether Layer C's page (which runs 2.1–2.78, further than VedaViṣṭāram's 2.1–42 but
still short of Layer A's full 82) had anything for the 2.51–58 pragṛhya-before-iti lead — it
does have transliteration + English gloss there too, but only a summarized paraphrase was
captured, not the verbatim text, so that lead is not advanced further by this pass; still
exactly where §10 left it.

**2.24/2.27, confirmed a third way**: Layer C glosses 2.24 as "an unrhotacized Visarjanīya, if
preceded by a long vowel and followed by a vowel, becomes ā" (āḥ + vowel → ā + vowel) and 2.27
as the same for a short-vowel-preceded visarga (aḥ + vowel → a + vowel) — a general derivation
of visarga into an a/ā *sound*, not a rule keyed to a specific following vowel. This is a third
independent line (after my own direct reading of the raw sūtra text, and VedaViṣṭāram's clean-
but-uncommented text) all pointing the same way, and all against Gemini's Round 2 claim that
2.24/2.27 describe a special *full elision* specifically before a following ā. The rejection of
that citation (§6.9/Part VIII) stands, now on three legs instead of one.

**What this does *not* do is explain the attested form.** Re-examining RV 1.1.7 (`भरन्तः` + `आ`,
§6.6) against the real Pada-pāṭha here: the sequence is actually three words, `भरन्तः` + `आ` +
`इमसि`, not two. The attested continuous form `भरन्त एमसि` decomposes cleanly once seen this way:
`आ` + `इमसि` → `एमसि` is *ordinary* guṇa vowel sandhi (ā + i → e — textbook, no special rule
needed). That part of the mystery is resolved, and it was a framing error on this session's own
part (§6.6 quoting the visible surface form without checking it was two Pada words fused, not
one). What's left is narrower and still genuinely open: `भरन्तः` + `आ` → `भरन्त` — i.e. per 2.27
the visarga becomes a bare `a` (`bharantaḥ` → `bharanta`), but that resulting `a` then does
*not* undergo further vowel sandhi with the immediately following `ā` (which instead skips past
it to bond with `इमसि`). Ordinary vowel sandhi (a + ā → ā, savarṇa-dīrgha) would predict
`bharantā` here, not `bharanta` with the following `ā` left untouched by it. A visarga-derived
`a` behaving as "invisible" to the vowel-sandhi rule that would otherwise apply to it next is a
known shape of exception in classical Sanskrit generally (compare `rāmaḥ` + `iti` → `rāma iti`,
not `rāmeti`), but this corpus has no Prātiśākhya sūtra actually cited and checked for it — 2.51
("words before iti are pragṛhya") is the closest lead already on file and it's about *iti*
specifically, not this. **No code change made.** The RV 1.1.7 gap in §10 is retitled below to
reflect this more precise, narrower question rather than the original, now-resolved "why does
एमसि look shorter than आ+इमसि" framing.

---

### 6.12 Fifth round (11 Sep 2026) — real sandhi at the Parigraha iti-junction, and

sutra 10.8's bahumadhyagata auto-detection

Self-directed continuation, per the lead's "whatever needs to be done, keep on doing it, solid
coding+testing" instruction. Read Uvaṭa's own bhāṣya on 10.8-10.11 directly (previously only the
bare sūtra text was on file for these; §6.6 only had 10.3's bhāṣya) looking for the next
concretely buildable item from Test F/G/H (§6.6's UNRESOLVED trio). Two real fixes came out of
it, both backed by Uvaṭa's own worked examples, not inference:

**Fix 1 — `get_sthitopasthita`/`get_upasthita` were rendering "word इति word" as a fixed,
unsandhied string template.** That happened to match Uvaṭa's only two examples this engine had
been checked against so far (10.14's "vibhāvaso iti vibhāvaso", 10.12's "bāhū iti") — but both of
those words are independently pragṛhya (vibhāvaso: vocative -o, sūtra 1.68; bāhū: dual -ū,
Paṭala 1's morphological class), which is exactly *why* they resist sandhi. Reading 10.8's own
bhāṣya surfaced three more examples that are NOT pragṛhya and DO show ordinary sandhi at the
word+iti junction: "ca iti ca" → **"cेति च"** (a+i→e guṇa), "cit iti cit" → **"चिदिति चित्"**
(t→d voicing before a vowel), "vā iti vā" → **"वेति वा"** (ā+i→e guṇa) — and 10.16's own
compound example, "purojitī iti" → **"पुरोजितीति"** (ī+i→ī). All four independently confirm the
same rule: real sandhi applies at this junction unless the word is pragṛhya. Fixed
`get_upasthita`/`get_sthitopasthita` to call `samhita_join` for real (with an `apply_sandhi=False`
bypass the caller passes when it independently knows the word is pragṛhya via `is_pragrhya()`),
verified the phonology engine reproduces all four citations exactly (`चेति`, `चिदिति`,
`वेति`, `पुरोजितीति`) with no new special-casing needed, and confirmed the two pragṛhya
citations reproduce correctly too with `apply_sandhi=False`. This changes every existing
Parigraha unit's rendering (e.g. Test B: `पुरोहितम् इति पुरःऽहितम्` → `पुरोहितमिति पुरःऽहितम्`,
since word-final म् simply doesn't combine visibly with a following vowel — a pass-through, not
a further error). Re-ran `regenerate_krama_rv_1_1.py`: the one already-known phonology gap
(1.1.7's chain-reconstruction mismatch) is unchanged, and the only non-Parigraha-unit
differences against the old hand-aligned file are the two already-documented ones from §6.6
(1.1.2's 10.3 firing, 1.1.7's gap) — confirmed by diffing with unit-type information, not by
eyeballing. `tests/test_krama_regenerated_output.py`'s stale "≥7 of 9 verses exact-match" check
(which can never pass again now that the correct rendering differs from the old file's
convention at every single Parigraha unit) was replaced with a check that every remaining
PAIR-level (non-Parigraha) diff is one of the two already-known cases — a check that still fails
loudly on a genuinely new regression, unlike a threshold that had quietly become unfalsifiable.

**Fix 2 — Test G (10.8 bahumadhyagata) implemented for real, replacing a guess.** The test's
previous "नराशंसम् इति नराशंसम्" expectation was written before this bhāṣya was read and does
not match any citation Uvaṭa actually gives. His real examples describe something more specific:
"नरा च शंसं दैव्यम्" (three separate Pada words) surfaces in Saṃhitā as "नराशंसम्", which *looks*
like one compound word — and the sūtra's point is that the small middle word (च) must still get
its own Parigraha, or it would be lost inside the fused-looking run. `detect_bahumadhyagata()`
(new, in `pratishakhya_classify.py`) recognizes a small, source-cited closed particle class
(ca/vā/cit — Uvaṭa's own three examples: नरा-च-शंसम्, शुनः-चित्-शेपम्, नरा-वा-शंसम्) sitting
between two other words in the list; `krama_engine.generate_ardharca()` now calls it
automatically whenever `bahumadhyagata_positions` isn't supplied, so no manual flag is needed for
this class any more (the parameter still exists for an explicit override/bypass). Verified
against the actual test input (`generate_ardharca(["नरा","च","शंसम्","दैव्यम्"])`) reproducing
`चेति च` exactly. Test G now legitimately **PASSES** (6 PASS / 2 UNRESOLVED, up from 5/3).

**What this does NOT cover, left explicitly open**: Uvaṭa's bhāṣya on 10.8 has a *fourth* example
in the same passage — "मो षु णः" → "मो इति मो। सु इति सु" — that does not fit the same
ca/vā/cit pattern (it looks like a retroflexion-*restoration* case, सु reverting from the
sandhi-retroflexed षु on retake, much closer to Test F's still-open territory than to Test G's).
Not implemented; flagged rather than force-fit into `detect_bahumadhyagata()`.

**A second, unresolved question surfaced but NOT acted on**: sūtra 10.10 ("न आकारम् प्रागतः
अननुनासिकम्" — one should not do ordinary Parigraha of a non-nasal आ that comes "प्रागतः" —
immediately before — the ardharca-final word) and 10.11 ("प्रत्यादाय एव तं ब्रूयात् उत्तरेण पुनः
सह" — instead, take it back and say it again together with what follows) look like they might be
the actual textual basis for the confirm-pair half of the existing sūtra-10.3 mechanism
(`krama_engine.py`'s `monosyllable_confirm_pair`) — and might mean that mechanism should be
scoped to only fire when the monosyllable is adjacent (in the *remaining* Krama-retake sequence,
after 10.3's own skip) to the ardharca-final word specifically, not generally anywhere a
monosyllable-avasāna word occurs (which is how it's currently implemented and how RV 1.1.2's
इह case, not itself ardharca-final-adjacent, triggers it). Whether "प्रागतः अर्धर्चान्त्यात्"
is a real independent restriction or just redescribes the same configuration 10.3 already
covers could not be settled with confidence from the bhāṣya prose alone — flagged in §10, not
guessed at either way.

Test F (10.21/11.23 restoration) and Test H (10.22/11.37-43 Śuddhākṣara/rephi derivation) remain
UNRESOLVED and were deliberately not attempted this round: both would need either (a) modelling
ṇatva/retroflexion-at-a-distance (a real, non-trivial slice of Pāṇinian grammar this engine has
none of yet — getting it wrong is worse than leaving it open) or (b) resolving the "मो षु णः"
ambiguity above — exactly the kind of narrow, well-defined, citation-backed question this
session is better off putting to an external model as a scoped, code-and-citation-only prompt
(per the lead's standing offer) than guessing at alone. See
`tools/pratishakhya/GEMINI_CHATGPT_TASK_PROMPT_V3.md` for that prompt.

---

### 6.13 Round-3 answers (Gemini + ChatGPT) evaluated, two narrow fixes installed after catching

a real bug in BOTH proposals

Both models answered all three V3 tasks. Per this session's standing discipline, every claim was
checked against the actual code (run, not read) before anything was installed — which caught a
real, shared bug neither model's own "I tested this" claim caught.

**Task A (11.23 ṇatva-restoration) — both models independently converged on the same scope
judgment I'd already leaned toward myself:** implement ONLY the evidenced "प्र + नः → प्र णः"
case as a narrow, closed check (a `NATVA_BOUNDARY_UPASARGAS_SLP1 = {"pra"}` set), not a general
tag-free ṇatva-at-a-distance engine. Gemini's first answer *did* propose a general Pāṇinian sieve
(citing 8.4.1/8.4.2/8.4.14/8.4.37), but ChatGPT's review caught a real flaw in it: Gemini's
`allowed_interveners` set included consonants (h, y, v, r, k-varga, p-varga) that Pāṇini 8.4.2
does not actually license — 8.4.2 names exactly *aṭ* (vowels) + *ku* + *pu* + *āṅ* + *num*, not
that broader set — and 8.4.14's "upasargād" licenses the boundary specifically for an upasarga's
own listed roots, not any r/f/F/z-final word in general. Independently confirmed this by reading
8.4.2's own gloss rather than taking either model's paraphrase on faith; installed the narrow
version. **A2 ("मो षु णः") — both models say UNRESOLVED, agreed and left alone**: स्→ष् retroflexion
(8.3.57/8.3.59) has its own separate conditions this corpus has no independent way to verify are
met here, and neither model would commit to a general rule for it either.

**Task B (11.43 śuddhākṣara-āgama) — installed a 4-entry closed lexical table
(`SHAUDDHAKSHARA_AGAMA_SLP1`), but only after fixing a real bug both models' proposed tables
shared:** both gave `("DUH", "sadam"): "DUfzadam"` for धूःसदम्→धूर्षदम् — but `"DUfzadam"` uses
SLP1 `f` (vocalic ऋ, an independent VOWEL letter) instead of `r` (the consonant repha). Checked
by literally running `slp1_to_deva("DUfzadam")`: it gives **"धूऋषदम्"**, not "धूर्षदम्" — a
different, wrong word. ChatGPT's response claimed "I tested the patch against the extracted
source code: 5/5 forward A/B cases passed" — that claim does not survive actually running the
code; whatever check produced it did not verify the Devanāgarī output string correctness for
this entry. Fixed to `"DUrzadam"` (verified: `slp1_to_deva("DUrzadam")` → "धूर्षदम्", matching
Uvaṭa's citation exactly) before installing; the other three entries (सु+चन्द्र, परि+कृण्वन्,
वन+सदम्) were independently verified correct and installed as given. **B1's classification
question (is there one Pāṇinian rule behind all four examples?) — both models say no unified
rule exists** (परिष्कृण्वन्: Pāṇini 8.3.137's सुट्-augment + 8.3.59's स्→ष्; सुश्चन्द्र: bahulaṃ
chandasi, no classical rule; धूर्षदम्/वनर्षदम्: likely the SAME repha-before-uṣman phenomenon
this project's existing `REPHI_CACHE_SLP1` already covers for धूःसदम् specifically, not a new
"augment" at all — Uvaṭa's own bhāṣya reuses this exact example under both 11.41 and 11.43 in
the same continuous passage) — confirming a closed table, not a derived rule, is the honest
choice here, consistent with this project's existing `IRREGULAR_VISARGA_STEMS`/`REPHI_CACHE_SLP1`
pattern. **B3 (is restoration automatic?) — confirmed independently by reading the actual code
path**, not by trusting either model's claim: `_parigraha_unit()` always builds the Parigraha
citation from the bare `word_deva` (or `resolve_compound`'s result for an avagrhya compound),
and `get_sthitopasthita`'s internal `samhita_join(word, "इति")` call can never match a
`(w1, w2)` key in `SHAUDDHAKSHARA_AGAMA_SLP1` (keyed on the word's real neighbour, never "इति")
— so the augment genuinely cannot leak into a Parigraha citation by construction. Verified with
`get_sthitopasthita("सुचन्द्र")` directly (no "श" appears). One incidental but real bug found
along the way while verifying this: `pratishakhya_classify.REPHI_CACHE_SLP1` had two entries
("dhUHsadam", "durdhyaH") using an invalid SLP1 spelling (lowercase "dh" where the single capital
letter "D" is needed for ध) — `is_rephi("धूःसदम्")` and `is_rephi("दुर्ध्यः")` had silently
always returned False. Fixed (encoding only, not a change to which word each entry represents).

**Task C (10.10–11's scope) — both models say don't touch the code, for different reasons.**
Gemini argues confidently for reading (ii) — the "before the ardharca-final word" wording
describes where the retaken monosyllable ends up *after* 10.3's own skip has already happened
(matching the worked example's own structure), not an independent restriction — and calls the
existing, more general implementation correct as-is. ChatGPT is more cautious: the quotations
given don't by themselves prove that reading, so leave the code alone as "the safer executable
interpretation" pending more evidence. Both land on **no code change**, which matches the
conclusion I'd already reasoned my way to independently before sending the prompt (§6.12) —
three independent readings converging is real, if not certain, support for interpretation (ii),
recorded in §10 as "reasonably decided," not "proven."

All fixes verified against the actual test cases (not just the citation), added to
`tests/test_krama_engine.py` as a new `NatvaBoundaryAndShuddhaksharaAgama` class, and confirmed
to leave RV 1.1's own regenerated output byte-for-byte unchanged (no RV 1.1 word pair matches
either new closed table) — this round is pure net-new coverage, not a change to already-checked
output.

---

### 6.14 Q2 resolved directly (own reading, no external prompt); RV 1.1.7's gap sharpened and

sent out as a fourth, tightly-scoped question

The lead asked whether anything still pending could be helped by external AI; surveying what's
actually left turned up two things worth separating cleanly first.

**Q2 (does word+iti sandhi apply outside pragṛhya words? sūtras 2.51–58) is resolved — by
directly reading the literal sūtra text now on file, not by sending it out.** Paṭala 2's own
text (Layer A, no OCR uncertainty for 2.51–2.55): **2.51** "प्रकृत्या इतिकरणादौ प्रगृह्याः" — words
are pragṛhya, in their unaltered form, before an *iti-karaṇa*; **2.55** "त्र्यक्षरान्ताः तु न
इवे" — an exception for trisyllable-final words before *इव specifically*, not इति. Read together
with **2.48–2.50** (the immediately preceding sūtras, about अन्तःपाद/word-medial phonology in
ordinary continuous verses) and the total absence of any Krama/Parigraha vocabulary anywhere in
this stretch, this reads as ordinary **Saṃhitā-pāṭha** phonology — how real occurrences of the
words *iti* and *iva* WITHIN THE ACTUAL HYMNS interact with an adjacent pragṛhya word — not a
rule about Paṭala 10's own "word+iti+word" Parigraha-citation convention, which is introduced
BY the Krama process itself and is a completely different textual layer. This means there is NO
conflict with the §6.12 fix (real sandhi at the Parigraha iti-junction unless the word is
pragṛhya) — Uvaṭa's own worked Krama examples (चेति च, चिदिति चित्, वेति वा, पुरोजितीति) are
still the operative evidence for THAT context, and 2.51–58 is a separate topic this engine
doesn't currently need to model (it has no Paṭala-2 continuous-recitation pass at all). Not sent
out; no further action needed unless Paṭala 2 work starts in earnest.

**RV 1.1.7's residual visarga gap is real, and now sharpened with one more piece of evidence
than §6.11 had.** Re-deriving it from the actual code (not just the sūtra text) found that the
CLASSICAL rule this engine already implements for a-class visarga before a vowel other than
short अ (aḥ + vowel → o + that vowel, unchanged and un-fused, e.g. the already-validated "देवः" +
"देवेभिः" → "देवो देवेभिः") predicts **भरन्तो आ** for भरन्तः+आ — a textbook-correct classical
form, not a bug. The attested Vedic **भरन्त** (visarga vanishes with no trace, not even "o") is
a genuine deviation from that ordinary rule, in the same general SHAPE as an existing precedent
already in this codebase (सः/एषः's specially-legislated visarga-drop-with-no-further-sandhi), but
this project has no citation naming this specific deviation for an ordinary word before **आ**
specifically. Sent as `tools/pratishakhya/GEMINI_CHATGPT_TASK_PROMPT_V4.md` — a single, tightly
focused question (plus one bonus, explicitly-optional question on "मो षु णः"'s grammatical
status), with the "citation or explicit UNRESOLVED, code must be independently verified before
being trusted" hard rule that's caught real bugs in every code-bearing round so far.

**Everything else currently open** (a general tag-free ṇatva-at-a-distance rule, the general
Śuddhākṣara/rephi-rendering derivation, the Kramahetu/Paṭala-11 decision layer, the `restore_*`
family, structured Svara, full per-unit transformation history, the VALIDATE-mode ground-truth
source) is either already-answered-as-inadvisable-to-generalize by two independent external
reviews (§6.13), or a software-design/data-sourcing decision that isn't actually "stuck" waiting
on grammar expertise — not re-sent, to avoid diluting this round's one real question.

---

### 6.15 Diagnostic scan beyond RV 1.1 (13 Sep 2026) — one real, fixed parsing bug; the actual

scaling blocker identified but NOT attempted

While waiting on the Round-4 answer, continued "solid coding+testing" with something that
doesn't depend on it: ran the already-built `reconstruct_chain()` checker (not the committed
generator itself) against RV 1.1–1.10 (204 ardharcas) purely as a diagnostic — **not** an attempt
to scale the shipped Krama-pāṭha output past RV 1.1, which stays on the spec's own explicit
"only after [the lead decides]" gate (§6.6/§10). Two things came out of it, kept clearly separate:

**A real, fixed, isolated bug: DGE's own `pada_patha` carries an "iti"-gloss convention RV 1.1
never happens to exercise.** A pada_patha token can gloss the word immediately before it with
"iti" — either bare disambiguation ("वायो इति", 541 times in Mandala 1) or giving both a fused
citation form AND the true avagraha-split compound ("वाजिनीवसू इति वाजिनीऽवसू", 76 times) — a
DIFFERENT thing entirely from a real, independent "iti" *word* (a quotative particle) that also
appears as its own pada elsewhere in this exact corpus (12 times in Mandala 1 — directly confirms
the Q2/§6.14 finding that ordinary Saṃhitā-pāṭha "iti" occurrences are a real, separate
phenomenon from Krama's own Parigraha convention). `regenerate_krama_rv_1_1.py`'s
`split_pada_words()` was treating the whole gloss token as one literal (wrong) word, e.g. feeding
`samhita_join` the string "वायो इति" as if it were a single Pada word. Fixed with
`_strip_pada_iti_gloss()`, derived from all 3 shapes actually observed (not guessed), including
one genuine one-off data quirk (a missing danda merging two independent words into one token,
"उपऽआसते उतो इति"). **RV 1.1 has zero instances of this pattern (checked directly)** — the fix
is confirmed a strict no-op there (`krama_regenerated_output.json` byte-for-byte unchanged after
re-running the generator) and a real, measurable improvement elsewhere: the diagnostic's own
match rate against RV 1.1–1.10 went from 77/204 to 96/204 ardharcas purely from this one fix.
Covered by a new `tests/test_pada_iti_gloss.py` (7 tests, all 3 real shapes plus the standalone-
iti-is-a-real-word negative case).

**The actual scaling blocker, identified but explicitly NOT attempted this round: the
`split_into_ardharcas()` automatic length-alignment heuristic's failure rate is much higher
outside RV 1.1.** Of the 108 remaining mismatches after the iti-gloss fix, inspecting a sample
shows most are NOT phonology bugs at all — the automatic ardharca-boundary detector (which
already needed 2 manual overrides even within RV 1.1's own 9 verses — §6.6) picks the wrong
split point often enough outside RV 1.1 that whole trailing words end up missing from one
ardharca and never reach the other. This is a real, structural problem with the "closest
cumulative length to the first daṇḍa" heuristic itself, not a small fix — and is exactly the kind
of thing the spec's own scaling gate exists to make the lead's decision on (accept a much lower
automatic-split success rate and rely on a growing manual-override table, or design a better
heuristic, or require independent ardharca-boundary data) rather than something to quietly work
around mid-diagnostic. **Not attempted.** Flagged here with real numbers instead.

---

## 7. Two modes

**GENERATE** — Pada-pāṭha → Krama-pāṭha, per §5.

**VALIDATE** — authoritative (independently attested) Krama text → run the same input through
GENERATE → diff. On mismatch, report the pair index, expected vs. generated text, a
best-effort classification of what kind of rule the difference implicates (e.g. "rephi
handling"), and rule candidates from the digitized Kramahetu-Paṭala once it exists. This mode
is not optional polish — see §8, it gates every corpus-wide run.

---

## 8. Validation-first development plan

Do not run the generator over the whole Rigveda before this sequence, in order:

1. **Done (§4b).** The lead approved a full pull through Layer A's endpoint; all 1,067
   sūtras (paṭalas 10–11 included) are now in `rigveda_pratishakhya/data.json`. Still open:
   cross-check the 24% marked `has_uncertain_reading` (and ideally the rest too) against
   Layers B/C, and turn cited sūtra text into actual `conditions`/`action`/`exceptions` rule
   logic (§6.1) — that interpretation step has not been done. The Pada-pāṭha prerequisite was
   already satisfied (§4).
2. Implement RV 1.1.1 only.
3. Generate its Krama-pāṭha; compare against an independently attested Krama text for RV
   1.1.1 (VALIDATE mode, §7).
4. Write automated tests (`tests/test_krama_engine.py`, matching this repo's existing
   `tests/test_*.py` convention) for every Prātiśākhya exception RV 1.1.1 actually exercises,
   plus deliberately chosen cases for: Pragṛhya, Rephita, Pragṛhya-inside-Parigraha,
   compound-inside-Parigraha, pluta, svarita, kampa, a hard vowel-sandhi combination,
   consonant sandhi, an ardharca boundary, and Śākala catuḥkrama.
5. Only after those pass, extend sūkta by sūkta — not maṇḍala by maṇḍala — re-running
   VALIDATE at each step where an independently attested Krama text is available.

---

## 9. Corrections this spec makes to the rejected draft (for traceability)

Kept as a short index back to the full review, not restated in full here:

1. Add the Kramahetu-Paṭala (ch. 11) as a first-class phase, not an afterthought.
2. Replace the universal `word + iti + iti + word` Parigraha formula with a rule-driven
   subsystem over Krama-Paṭala 10.7–10.22 and the relevant Kramahetu-Paṭala rules.
3. Demote any generic Pāṇinian/Classical Sanskrit sandhi API to an optional helper,
   subordinate to the Prātiśākhya-specific rule layer (§2).
4. Replace the flat Pragṛhya word list with the categorized structure in §6.1.
5. Replace the static Rephi word list with an `isRephi(word, context)` predicate, list as
   cache only.
6. Treat any accent-combination ("Udātta + Anudātta = …") matrix as an unvalidated
   hypothesis, not ground truth, until checked against attested Śākala forms (§6.2).
7. Represent an Akṣara as a structured object (text/vowel/onset/coda/svara/…), not a regex
   match — the regex is a tokenizer only, never the phonological model.
8. Fix the transliteration/accent-encoding confusion: internal accent state is a
   script-independent enum (§6.2); rendering to Devanagari/IAST/Vedic-Unicode happens only
   at the presentation layer.
9. Add `dirgha_svarita`, `pracaya`, `kampa` (and room for more, pending ch. 3 digitization)
   to the accent model instead of collapsing to udātta/anudātta/svarita.
10. Move colour entirely to the renderer (§6.4).
11. Remove audio-timestamp fields from the generator's output (§6.4).
12. Require `provenance`/`rules` citations on every generated unit (§6.3).
13. Require a VALIDATE mode (§7), not GENERATE-only.
14. Require the Prātiśākhya text itself as the rule source, not paraphrase — which is exactly
    what §4a blocks on today.
15. (Part II, 10 Sep 2026) Correct this document's own first-draft error: the Rigveda Śākala
    Pada-pāṭha already exists in this repo (§4) — it was missed by checking only for a
    sibling directory, not the per-mantra field actually holding it.
16. (Part II) Replace the single unverified archive.org PDF citation with a three-layer,
    live-checked sourcing plan for the Prātiśākhya sūtra text itself, plus a concrete
    per-paṭala rule-database schema (§4a).
17. (Part II) Correct the accent-rendering guidance: do not recommend a Vedic Extensions
    codepoint for dīrgha-svarita without testing it against the font-support trap this repo
    already documented and fixed for svarita/anudātta (§6.2).
18. (Part III, 11 Sep 2026) Actually pull and inspect Layer A rather than trust the citation:
    found it is an undocumented JSON endpoint, not a downloadable TEI/XML file (§4a.1);
    confirmed paṭalas 10 and 11 sūtra counts (22, 71) exactly against the source itself; and
    verified, word-for-word, several specific sūtras that had appeared unattributed in the
    original review — they were real, not fabricated, and now have exact citations.
19. (Part IV, 11 Sep 2026) Bulk pull done, with the lead's go-ahead: all 1,067 sūtras are now
    in `rigveda_pratishakhya/data.json` (§4b). Caught and fixed, while building the real
    importer, a mistake in Part III's own verified-sample table: 10.20 was quoted as only
    its second clause, and 10.20/10.22 had their source-marked `[?]` uncertain characters
    silently guessed rather than left unresolved — the shipped data does not repeat either
    error (§4a.1's correction note, `tools/pratishakhya/SOURCES.md`).
20. (Part V, 11 Sep 2026) Responding to the lead's own detailed critique document: replaced
    the hand-aligned `generate_krama_rv_1_1.py` approach with a real computational engine
    (`sanskrit_phonology.py`, `pratishakhya_classify.py`, `krama_engine.py`, §6.6) that
    computes sandhi and Parigraha from Pada-pāṭha directly rather than looking up precomputed
    per-verse strings, and regenerated RV 1.1 through it — 7 of 9 verses match the old
    hand-aligned output exactly, the other 2 surface one real improvement (10.3's exception
    correctly generalized to a second case) and one genuine open phonological gap (visarga
    before आ in 1.1.7, documented rather than patched blindly). Explicitly did NOT import any
    rule or form from the KYVeda/Taittirīya corpus into this engine, per the lead's strict
    instruction — that corpus was consulted only as a methodological precedent (§10).
21. (Part VI, 11 Sep 2026) A second independent review (ChatGPT, relayed by the lead) argued the
    first regenerated-output run gave no way to tell canonical output from a guess, or a checked
    fact from an unchecked one (§6.7). Its specific count-bug claim was checked directly and
    found wrong (both counts were already correct) — but the underlying complaint was fair: the
    arithmetic tying them together was nowhere visible, so it reasonably looked broken. Fixed
    that plus several real gaps: unit-level `status`/`retake_state`/`trigger_reasons` fields;
    a per-ardharca `chain_reconstruction` VALIDATE check (§6.7) built to replace a first,
    flawed per-unit substring-match attempt; and, in building that check properly, two real
    phonology bugs it caught (a chained string's own elision-avagraha being misread as a
    Pada-pāṭha compound; lexical exceptions only matching a bare word, never mid-chain) plus one
    real, still-open bug precisely diagnosed rather than patched (an SLP1 round-trip collision
    between "र्ऋ" and "रृ" that only manifests two joins deep). Chain reconstruction now matches
    DGE's attested text on 16 of 18 RV 1.1 ardharcas, up from an unverified claim of 69/70 made
    in an earlier, uncommitted ad hoc check.
22. (Part VII, 11 Sep 2026) Sent a self-contained code+data task prompt to Gemini and ChatGPT
    (§6.8) and verified every answer against this project's own primary sources before acting.
    Adopted two real, now-confirmed-working fixes: a ZWNJ marker resolving the र्ऋ/रृ collision
    (empirically tested across 4 consecutive joins, not just the 2 that exposed it — chain
    reconstruction now 17/18) and a diphthong-glide bug independently confirmed against
    Pāṇini 6.1.78. Checked and found two of Gemini's other claims already fixed by the prior
    round, not new bugs. Caught a real citation error even in an otherwise-correct answer
    (Gemini's Q2 cited RPr 1.74 for "vocative o is pragṛhya"; this project's own corpus shows
    that's actually 1.68) — the substance was right, the citation wasn't, and only checking
    directly against already-ingested primary text caught it. Declined to adopt Gemini's Q3
    citation (RPr 2.27) after checking it against this project's own (uncertain-reading,
    not-yet-cross-checked) Paṭala 2 data and finding it doesn't clearly support the specific
    claim made. RV 1.1.7's visarga-before-आ gap remains open, now with a citation to verify
    rather than none.
23. (Part VIII, 11 Sep 2026) Gemini's Round 2 answer, then a Claude-authored critique of that
    answer, were both checked directly rather than either trusted (§6.9). The critique correctly
    caught that Gemini's D2 conclusion ("the र्ऋ collision is unique to vocalic r/rr") was false
    — reproduced directly: the collision holds for every vowel class. But going further and
    checking whether that transliteration-level fact was an actual ENGINE bug (not assumed
    either way) found it wasn't: three real attested RV 1.1.2 examples (checked by Unicode
    codepoint, not inferred) confirm this project's existing scope (special-case only f/F) is
    already correct — the two other attested cases ("र्+ई"→"री", "र्+उ"→"रु") both use the
    dependent-matra form this engine's default already produces. `_finish_consonant_then_vowel`
    was not widened without a reproduced defect; both its docstring and the module docstring
    were corrected to state the real (typesetting, not SLP1-uniqueness) reason for its scope
    accurately. Also declined to fully adopt the critique document's blanket dismissal of
    Gemini's Pāṇini 8.3.17/8.3.19 citation for RV 1.1.7 — procedurally out of bounds for that
    specific prompt's rule, but a real, checkable, name-relevant (Śākalya/Śākala) lead that
    deserves investigation, not discarding — recorded as an open item in §10.
24. (Part IX, 11 Sep 2026) Cross-checked Paṭala 2 against VedaViṣṭāram directly, no external
    prompt, at the lead's explicit request (§6.10). Found the "82 vs 41/42 sūtra" count gap
    (§4a.1) is a chapter-scope difference, not a numbering bug: VedaViṣṭāram's own Paṭala 2 stops
    at sūtra 42; its Paṭala 3 is the accent chapter, not a continuation of Layer A's 43–82.
    Within 1–42, resolved 5 previously-uncertain sūtras with real evidence (a new
    `P2_RESOLUTIONS` table) — including a genuinely new kind of resolution (VedaViṣṭāram's own
    page corrupts an avagraha into a literal zero-width-non-joiner character, confirmed at two
    separate sūtras) — and left one honestly unresolved where VedaViṣṭāram's excerpt doesn't
    reach the relevant position. Also caught and fixed a real pre-existing bug in
    `crosscheck_vedavishtaram.py`: re-running it duplicated the corpus `note` field. The
    RV 1.1.7 visarga gap this was meant to help resolve remains open — VedaViṣṭāram has no
    Bhāṣya at all for that region — but a promising new lead for the separate Q2 word+iti
    question turned up instead (sūtra 2.51), in the 40-sūtra block VedaViṣṭāram doesn't cover,
    genuinely unparseable with confidence without a commentary this corpus doesn't have. Not
    acted on without one.

---

## 10. Open questions for the project lead

- ~~Approve a full pull of paṭalas 10–11 through Layer A's undocumented endpoint.~~ **Done —
  approved 11 Sep 2026 ("bulk pull it"), all 1,067 sūtras ingested, §4b.**
- ~~Cross-check the `has_uncertain_reading` sūtras against Layer B or C.~~ **Done for paṭala
  10–11 (24 of 26 resolved, 2 genuinely left open) and 85 more sūtras elsewhere in the corpus
  — §4c.** 135 sūtras remain unresolved outside paṭala 10–11; revisit if/when work reaches
  those paṭalas, not blocking Krama work now.
- Cross-check against Layer C (the RV-Prātiśākhya project) too, as a third independent source
  — not done yet; VedaViṣṭāram alone was enough to resolve the paṭala 10–11 cases actually
  needed so far, but Layer C stays valuable as a check on VedaViṣṭāram itself (which has its
  own small errors — see §4c's note on 11.59's apparent typo).
- ~~Approve turning cited sūtra text into actual rule logic.~~ **Done for paṭala 10 (all 22
  sūtras) and 14 of paṭala 11's — §6.5.** Review that interpretation (it is this session's own
  reading of the Bhāṣya, not independently checked) before relying on it, and decide whether
  the remaining 57 paṭala-11 sūtras (mostly rationale/lineage/debate, not new operative
  content — see §6.5) are worth the same treatment.
- Confirm an independently attested Krama-pāṭha source to use as the VALIDATE-mode ground
  truth for RV 1.1.1 and subsequent sūktas — `github.com/vishvasa`'s Rigveda repo was
  checked (10 Sep 2026) and does not appear to carry one, so this is still open.
- (Added 13 Sep 2026, §6.15) **When ready to decide on scaling past RV 1.1, the actual blocker
  is now quantified, not just gated in principle**: `split_into_ardharcas()`'s automatic
  length-alignment heuristic gets 7/9 right unaided on RV 1.1 (2 manual overrides already
  needed there); a diagnostic pass against RV 1.1–1.10 (204 ardharcas, not committed as scaled
  output) found its failure rate is much higher outside RV 1.1 — most of the 108 remaining
  chain-reconstruction mismatches there (after a real, separate parsing bug was fixed — see
  §6.15) trace back to the wrong ardharca split point, not a phonology error. Options for
  whoever picks this up: accept a lower automatic success rate plus a growing manual-override
  table (works, doesn't scale cleanly), design a better split heuristic, or find/require
  independent ardharca-boundary data. Not attempted without the lead's steer on which.
- Decide whether `github.com/vishvasa`'s per-sūkta Śākala Saṃhitā (2,226 files) is worth a
  word-level cross-check against DGE's own Pada/Saṃhitā data before the Krama work leans on
  it, or whether the existing 96.61%-validated VedaWeb cross-check is sufficient.

- (Added 11 Sep 2026, Part V; updated Part VII; updated §6.10; **narrowed by §6.11**) The RV
  1.1.7 gap is no longer "why does भरन्तः + आ + इमसि surface as भरन्त एमसि" — the एमसि half is
  just ordinary guṇa sandhi (आ + इमसि → एमसि) and needs no special rule; §6.11 confirmed this
  from the actual three-word Pada-pāṭha. What's left, narrower and still open: भरन्तः's visarga
  becomes a bare `a` before आ (per 2.24/2.27, now confirmed a third independent way by Layer C
  in §6.11), but that `a` then does *not* itself undergo ordinary vowel sandhi with the
  following आ (a + ā → ā would predict भरन्ता, not the attested भरन्त). Needs a specific
  Prātiśākhya citation for "a visarga-derived a does not participate in the next vowel-sandhi
  step" (a known *shape* of exception in classical Sanskrit generally, e.g. रामः + इति → राम
  इति not रामेति — but not yet located as a cited sūtra in this corpus) or confirmation this is
  genuinely `bahulaṃ chandasi` free variation with no single derivable rule.
- (Added 11 Sep 2026, §6.10) A genuinely new, well-scoped lead for the Q2 question below, found
  while cross-checking Paṭala 2: sūtra 2.51, "prakṛtyā itikaraṇādau pragṛhyāḥ" ("[words] before
  iti-karaṇa are pragṛhya"), sitting in the 40-sūtra block (2.43–82) VedaViṣṭāram doesn't cover
  at all. Reads as though it could directly answer Q2 (word-before-iti is pragṛhya BECAUSE it
  precedes iti, not only when independently pragṛhya for an unrelated reason) — but 2.52's
  "svareṣu ca ārṣyām" and 2.54–55's further conditions/exception genuinely cannot be parsed
  confidently without a commentary this corpus doesn't have for this range. Do not implement a
  change to `get_sthitopasthita()` from this alone — get an authoritative reading of 2.51–2.58
  first (a well-scoped citation-verification task, the same shape as the Paṭala-2 work just
  done, or worth putting to an external source with the literal text quoted).
- (Added 11 Sep 2026, Part VIII) A second candidate citation for the same RV 1.1.7 gap: Gemini's
  Round 2 answer invoked Pāṇini 8.3.17 ("bho-bhago-agho-apūrvasya yo'śi") and 8.3.19 ("lopaḥ
  śākalyasya" — the semivowel arising from this sandhi may optionally elide before a vowel, per
  the grammarian Śākalya). This wasn't part of the text supplied in that prompt, so it was
  correctly flagged as not satisfying that specific exercise's citation rule — but it is a real,
  well-known Pāṇinian sūtra, and "Śākalya" is literally this recension's own namesake (Ṛgveda
  Śākala śākhā), which makes it a genuinely promising lead, not a fabrication. Not yet verified:
  whether 8.3.17's precise condition (a visarga from final "-as", specifically in the
  "apūrvasya" environment, i.e. NOT preceded by अ) actually covers भरन्तः (an ordinary -तस्
  nominative). Worth checking properly before either adopting or discarding.
- (Added 11 Sep 2026, Part VII) Sharpened question from Gemini's Q2 answer: is
  `get_sthitopasthita()`'s current unconditional "no sandhi between word and iti" rendering
  actually wrong for non-pragṛhya Parigraha words? Both of this project's two attested examples
  (`vibhāvaso`, `bāhū`) happen to be pragṛhya, so neither proves "no sandhi" as opposed to
  "no sandhi only because pragṛhya independently blocks it." If the latter is correct, every
  Parigraha unit for a non-pragṛhya word (the large majority — e.g. `पुरोहितम्` + `इति`) may
  need real `samhita_join`-computed sandhi between the two rather than the current bare
  juxtaposition. High-impact if true; not implemented on an inference alone — needs a citation
  or example covering a non-pragṛhya Parigraha word specifically.
- (Added 11 Sep 2026, Part V) Decide whether to delete `generate_krama_rv_1_1.py` and its
  `PARIGRAHA_FORMS`/`VERSES` hardcoded data now that the real engine (§6.6) reproduces 7/9
  verses exactly and explains the other 2 — left in place pending the lead's review of the
  1.1.2/1.1.7 discrepancies. (Note: this 7/9 count is against the OLD hand-aligned output and
  is unaffected by Part VII's chain-reconstruction fixes — 1.1.2 still differs from the old
  file for the unrelated, already-explained 10.3-generalization reason in §6.6, even though
  chain reconstruction itself now matches DGE's attested text for 1.1.2 exactly. Two different
  metrics; do not conflate them.)
- (Added 11 Sep 2026, Part V; **10.8 done §6.12; 11.23's evidenced case done §6.13**) Priority-0
  item 10.10–10.11 (आ before ardharca-final Parigraha, distinct from 10.3) — **settled, no code
  change, §6.13** (see the next bullet). 11.23 restoration — **the one evidenced case
  (प्र+नः→प्र णः) is done** (`NATVA_BOUNDARY_UPASARGAS_SLP1` in `sanskrit_phonology.py`,
  §6.13); a GENERAL tag-free ṇatva-at-a-distance rule remains open — both Gemini and ChatGPT
  agreed identifying an upasarga in general needs morphological tagging this engine doesn't have,
  and a first attempt at a general phonological sieve (Gemini's) licensed intervener consonants
  Pāṇini 8.4.2 doesn't actually name. Priority-1 items 10.20/10.22 Pragṛhya/Rephī restoration as
  named functions and 11.25 remain open — not started. **11.37–43 — the one evidenced sub-case
  (11.43's śuddhākṣara-āgama, 4 closed examples) is done** (`SHAUDDHAKSHARA_AGAMA_SLP1`, §6.13);
  no general derivation exists (checked directly: the 4 examples share no single Pāṇinian origin).
  ~~10.8 bahumadhyagata auto-detection~~ **Done 11 Sep 2026 (§6.12):
  `pratishakhya_classify.detect_bahumadhyagata()`, backed directly by Uvaṭa's own three worked
  examples on 10.8 (ca/vā/cit); Test G now PASSES.** One sub-case from the same bhāṣya passage
  ("मो षु णः") did NOT fit this pattern and is **still open, deliberately** — both external
  models agreed स्→ष् retroflexion's own conditions (8.3.57/59) can't be safely generalized from
  this one example either.
- (Added 11 Sep 2026, §6.12; **reasonably decided, §6.13**) A specific, well-scoped reading of
  10.10–10.11's own bhāṣya ("न आकारम् प्रागतः अननुनासिकम्" / "प्रत्यादाय एव तं ब्रूयात् उत्तरेण
  पुनः सह") raised a real question about the EXISTING sūtra-10.3 आ-exception mechanism
  (`krama_engine.py`'s `monosyllable_retake_tri_unit`/`monosyllable_confirm_pair`, in production
  use since §6.6): does 10.10's "प्रागतः अर्धर्चान्त्यात्" (immediately before the ardharca-final
  word) narrow 10.3's mechanism to only that position, or just redescribe, from the retake
  sequence's own point of view after 10.3's skip, the same configuration its worked example
  (मन्द्रम्/आ/वरेण्यम्) already shows? **Three independent readings now converge on "just
  redescribes, no narrowing"**: my own reasoning before sending the V3 prompt (§6.12), Gemini's
  answer (confident: (ii), the ā's position 10.10 describes is a post-10.3-skip artifact, not an
  independent restriction), and ChatGPT's more cautious "the quotations don't prove it, but don't
  narrow a mechanism that already matches every attested case on unproven grounds either." **No
  code change** — this is convergent-but-not-certain, recorded here as "reasonably decided," not
  "proven": a case where RV 1.1.2's own इह-configuration actually diverges from वरेण्यम्-style
  ardharca-final-adjacency (should scaling past RV 1.1 ever produce one) would still be the real
  test of this reading, not a further citation search.

- ~~The `indic_transliteration` SLP1 scheme's "र्ऋ"/"रृ" collision.~~ **Fixed, Part VII/VIII
  (§6.8–6.9): a ZWNJ marker, verified to survive 10 consecutive re-joins (checked after every
  individual join) before being trusted. Chain reconstruction is now 17/18 RV 1.1 ardharcas.**
- (Added 11 Sep 2026, Part VI) A real Kramahetu (Paṭala 11) evaluation layer — an explicit
  `krama_decision` object per ardharca naming which Paṭala-11 sūtras were checked and why
  ordinary two-step Krama (vs. dvikrama/trikrama/pañcakrama) was selected — does not exist yet;
  every ordinary pair currently just cites `"10.2"` with no record that Paṭala 11 was consulted
  at all. This is a bigger, separate engineering task, not a field to bolt on.
- (Added 11 Sep 2026, Part VI) A full per-unit transformation-history object (`{"input":...,
  "phonology":[...], "krama":{...}, "output":...}`), a structured `restore_*` family (Prakṛti
  restoration on retake, Śuddhākṣara, Rephī/Uṣman), and a syllable-level structured Svara object
  remain unbuilt — all correctly identified by the second review as real gaps, all explicitly
  deferred rather than rushed (§6.7 lists exactly what exists in their place today).

**Standing acceptance criterion (added 11 Sep 2026, from the second review, adopted verbatim
because it is the right bar and should stay written down rather than re-litigated per review):**
A generated form must never be considered "correct" merely because it reproduces DGE Saṃhitā or
because a classifier selected it with high confidence. Every nontrivial Krama transformation
must be justified by an explicit Prātiśākhya rule/state transition, and every unresolved
interpretation must remain unresolved rather than being emitted as canonical output. This repo's
`"status"`/`"confidence"`/`"chain_reconstruction"` three-field split (§6.7) is this pass's
concrete attempt to satisfy that criterion mechanically, not just rhetorically — but the fields
are only as honest as what populates them, so any new rule or exception added later must keep
setting them correctly, not just adding a plausible-looking value.

(Note on the sentence above §10's first bullet: it described the state as of Part II/III. As of
Part IV/V/VI, actual ingestion, rule-logic, and now the real generator engine code (twice
reviewed and corrected) have all landed — see §4b, §6.5, §6.6, §6.7 for what's shipped, and the
items just above for what's still open.)
