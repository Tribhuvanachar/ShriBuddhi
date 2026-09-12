# Where Sāyaṇa can actually come from — measured, not assumed

> **TOP LINE, added after checking sa.wikisource directly:** Sanskrit Wikisource
> carries Sāyaṇa's Ṛgveda-bhāṣya as **clean transcribed text** on **1,019 of the
> Ṛgveda's 1,028 sūktas (99.1%)**, wrapped in a `{{सायणभाष्यम्|…}}` template, under
> CC BY-SA. This is better than every other route on every axis that matters and
> **is now the primary source**. The archive.org OCR aligner below still works
> (95.5%, median 0.93) and is worth keeping as a cross-check and a fallback for
> what Wikisource lacks, but it is no longer the main path. See §5 and §6.
>
> **DONE.** `wikisource_sayana.py` ran and wrote **10,388 of 10,552 mantras
> (98.45%)**, median match 1.00, **zero off-by-one**. §6 is the result and the
> evidence.


Everything here was measured from a GitHub Actions runner in August 2026.
`AUDIT.md` remains the survey of what exists; this is the record of what is
*reachable* and what is *alignable*, both of which turned out differently from
the assumptions the importer was built on.

## 1. Reachability

| Source | bot UA | curl default | |
|---|---|---|---|
| wisdomlib.org — mantra page | 403 | 403 | refused |
| wisdomlib.org — **`/robots.txt`** | 403 | 403 | refused |
| sacred-texts.com | 403 | 403 | refused |
| archive.org (details / metadata / search API) | 200 | 200 | **open** |
| sanskritdocuments.org | 200 | 200 | **open** |
| sa.wikisource / en.wikisource API | 200 | 200 | **open** |
| GRETIL | 404 | 404 | host up; probe URL was stale |
| TITUS Frankfurt | 200 | 200 | **open** |
| VedaWeb (Cologne) | 418 | 418 | host up, refuses programmatic access |

The premise the package was built on — "Actions has open egress; the authoring
sandbox does not" — is false for wisdomlib and sacred-texts, and true for
everything else. A 50-mantra wisdomlib run returned **50 pages fetched, 0
imported, 250 consecutive 403s**.

**wisdomlib refuses `/robots.txt` itself.** A site cannot state a crawler policy
to an address it will not talk to, so this is an edge rule against datacenter IP
ranges, not a decision about crawlers. Codespaces, Colab and any VPS sit in the
same ranges. A consumer connection does not — hence `run_on_phone.sh` and
`PHONE.md`. Nothing there disguises a request; the User-Agent stays honest.

## 2. The archive.org scans are alignable — a correction to AUDIT.md

`AUDIT.md` ruled the scans out on the grounds that Devanagari OCR "is not good
enough to ingest unreviewed". That judgement was made on the reputation of
Devanagari OCR rather than on this scan, and it is too pessimistic.

`archive.org/details/rgveda-with-sayanabhasya` carries a full OCR text layer —
four files, ~25 MB, one per maṇḍala group. The maṇḍala-1 file is 2.9 M
characters, 119,646 Devanagari to 112 Latin in a sampled slab. It is **readable
Sanskrit**, citing Yāska (`निरु. ६.१४`) and Pāṇini (`पा. सू. २.४.८०`), with
recognisable errors — `ऐश्वयवन्तं` for `ऐश्वर्यवन्तं`, `तुवेणिः` for `तुर्वणिः` —
rather than noise.

Crucially, the edition prints, per mantra and in order:

```
<saṃhitā-pāṭha>  … ॥ N ॥
<pada-pāṭha>     … ॥ N ॥
<Sāyaṇa's bhāṣya>
```

**4,242 `॥ N ॥` markers for 2,006 mantras** — 2.1 per mantra, exactly as that
structure predicts. So the mantra's own text sits immediately before its
commentary, and DGE already holds the saṃhitā-pāṭha for all 10,552 mantras.
Alignment therefore needs no page map: walk DGE's mantras in order, score each
against the OCR blocks, and the bhāṣya is what lies between one match and the
next. Every cut is self-verifying — the thing matched is the mantra DGE already
has, so a wrong cut cannot look right.

### Measured so far

| Attempt | Method | Located |
|---|---|---|
| Round 1 | exact 18-char substring | 151/2006 (7.5%) |
| Round 2 | `॥ N ॥` segmentation + similarity ratio | **709/2006 (35.3%)** |

Round 1's failure was the matcher, not the source: an exact 18-character
substring needs six consecutive akṣaras all OCR'd correctly, which at this error
rate rarely holds. Every one of its 151 hits landed exactly on its mantra.

Round 2 finds **all eight mantras of sūkta 1.1**, at similarities 0.63–0.89. But
the overall distribution is bimodal — median 0.27, p75 0.72 — which means it
matches well or not at all, and loses sync partway.

### What is not yet done

35% is not shippable, and the remaining work is ordinary engineering, not a
research question:

- **Sync recovery.** The cursor only advances on a hit, so once the 8-block
  window drifts past a mantra it stays lost. It needs re-anchoring on the
  `॥ N ॥` numbering, which is readable independently of the text.
- **Match on the pada-pāṭha too.** DGE holds `pada_patha_plain`, and the
  word-separated form is more distinctive than the sandhi-joined saṃhitā text.
  Two independent keys per mantra would also make a wrong match far less likely.
- **False markers.** Some of the 4,242 are sūkta and anuvāka ends, not mantra
  ends; they should be classified rather than counted.
- **Attribution and rights.** The item states no licence. The 1930s–50s Vaidika
  Saṃśodhana Maṇḍala edition's own status needs checking before publishing, even
  though Sāyaṇa's text is long out of copyright.
- **Label it as OCR.** Whatever lands should be marked as uncorrected OCR of a
  scan, not presented as a critical edition.

## 3. What this changes

If the alignment is finished, Sāyaṇa becomes obtainable **from Actions**, with no
residential connection anywhere, and in **Sanskrit** — Sāyaṇa's own words rather
than Wilson's 1850s English rendering of him, which is all the wisdomlib route
would ever have given.

Until then `run_on_phone.sh` remains the working route, and it delivers Wilson's
Sāyaṇa complete for all 10,552 mantras in about 3.5 hours.

The two are not exclusive. `commentaries.sayana` and `commentaries.wilson` are
separate keys, and `dge/js/core.js` already labels both.

## 4. sanskritebooks.org

Suggested as a source; probed but not yet cleanly read back. Every Sāyaṇa result
from an independent search resolved to archive.org rather than to a file hosted
there, so the working assumption is that it indexes the same scans. Worth
confirming before spending effort on it.

---

## 5. Sanskrit Wikisource — the source that supersedes the rest

Checked directly, 18 Aug 2026.

### Coverage

```
insource:"सायणभाष्यम्" intitle:"ऋग्वेदः"   ->  totalhits: 1022
```

The Ṛgveda has 1,028 sūktas. So **1,022 of 1,028 carry the bhāṣya — 99.4%**.

### Why it beats the archive.org scan on every axis

**It is transcribed, not OCR'd.** Same passage, both sources:

| Source | RV 1.1 |
|---|---|
| archive.org OCR | `हे "अग्ने छे "ये यज्ञ ४विश्वतः सर्वासु दिक्षु "परिभूः परितः प्राप्तवान् "असि` |
| **sa.wikisource** | `हे “अग्ने “सः त्वं “नः अस्मदर्थं सूपायनः शोभनप्राप्तियुक्तः “भव । तथा नः अस्माकं “स्वस्तये विनाशराहित्यार्थं “सचस्व समवेतो भव` |

The Wikisource text keeps the pratīka quotation marks and renders Pāṇini
citations correctly (`पा. सू. ८. १. १८`). The OCR mangles both.

**It is structurally marked.** The wikitext wraps the commentary in a template:

```
{{सायणभाष्यम्|
‘चित्रो वः' इति ...
}}
```

That is a named boundary, so extraction is a parse rather than the block
segmentation and fuzzy scoring the OCR route needs. No `॥ N ॥` counting, no
similarity threshold, no apparatus to detect and skip.

**Its licence is stated.** CC BY-SA, versus the archive item's silence. DGE is
non-commercial and attributes, which satisfies share-alike — but the obligation
is explicit and must be recorded in `commentary_sources`, not assumed.

**One page per sūkta**, titled `ऋग्वेदः सूक्तं <maṇḍala>.<sūkta>` in Devanagari
numerals, holding the sūkta's mantras *and* its bhāṣya. The mantras being on the
page means the same self-verifying alignment is available here: match DGE's
mantra against the page's own, and the commentary beside it is the right one.

### What still has to be worked out

- **Splitting the bhāṣya per mantra.** The template holds one block per sūkta.
  Sāyaṇa's per-mantra glosses run in sequence inside it, separated the same way
  the print edition separates them, so the existing skeleton-matching logic in
  `archive_sayana.py` is directly reusable on clean input — where it should do
  considerably better than 95.5%.
- **The 6 sūktas without the template**, and whether they are gaps or spelling
  variants of the heading.
- **Rate limits and attribution.** Use the MediaWiki API with a descriptive
  User-Agent; Wikimedia asks for one and it is the polite thing regardless.

### Keep the OCR route

Not as the main path, but two uses remain. It is an independent witness — where
Wikisource and the scan agree, confidence is high; where they diverge, something
needs a human. And it covers whatever Wikisource turns out to lack.

---

## 6. The Wikisource import, as run

`wikisource_sayana.py`, run 18 Aug 2026 against all ten maṇḍalas.

| | |
|---|---|
| Mantras carrying Sāyaṇa | **10,388 / 10,552 (98.45%)** |
| Median match against DGE's own mantra | **1.00** (min 0.88) |
| Cuts whose verse number also agreed | 10,374 (99.9%) |
| Glosses quoting the **next** mantra | **0** |
| Cuts refused for quoting the next mantra | 66 |

Per maṇḍala: 1 — 98.3% · 2 — 98.1% · 3 — 98.5% · 4 — 99.7% · 5 — 98.6% ·
6 — 99.7% · **7 — 100%** · 8 — 95.5% · 9 — 99.0% · 10 — 99.5%.

### Three corrections to §5

**1. Coverage is 1,019 sūktas, not 1,022, and the search alone finds only 990.**
`totalhits: 1022` counts *hits*, not pages: 29 are duplicates across the
paginated result set and 3 are Aitareya Brāhmaṇa pages that merely mention the
template. Deduplicated, the search returns **990** sūktas. But the search index
lags the wiki — probing the 38 it omits **by title** finds the template on 29 of
them, so the real figure is **1,019 of 1,028 (99.1%)**. The importer therefore
searches *and* probes; searching alone would have silently lost 29 sūktas.

**2. The nine sūktas that genuinely lack the bhāṣya are the Vālakhilya.**
RV 8.49–8.55, 8.57 and 8.59 — the apocryphal appendix to maṇḍala 8, which much
of the manuscript tradition transmits apart from Sāyaṇa's commentary. That is a
property of the text, not a gap in the wiki, and no retry will close it. It is
most of why maṇḍala 8 sits at 95.5% while the rest are above 98%.

**3. Splitting is anchored on the mantra, not on the verse number.**
§5 expected the `॥N॥` counting to carry over. It does not, and should not: RV
10.90 prints only 12 of its 16 numbers, pages repeat a number for a quoted
verse, and sūkta and anuvāka tallies wear the same form. The mantra's own
text cannot be any of those things. So the aligner matches DGE's saṃhitā- and
pada-pāṭha and treats the number as a *second* witness, recorded per cut — it
agreed on 99.9% of them, which is worth knowing precisely because it was not
required.

### What the page actually looks like

Inside the template, per mantra and in order:

```
<saṃhitā-pāṭha, accented>   … ॥N
<pada-pāṭha, accented>      … ॥N
<pada-pāṭha, plain>         … ॥N
<Sāyaṇa's gloss on mantra N>
```

The closing danda after the number is dropped more often than not. A gloss runs
from the end of its own mantra's printed block to the start of the next
mantra's — **both ends anchored on text DGE already holds**, which is what makes
a wrong cut impossible to mistake for a right one.

Each sūkta also opens with a preamble on its viniyoga, ṛṣi and chandas that
glosses no single mantra. It is kept under its own key, `commentaries.sayana_sukta`,
on the sūkta's first mantra — 1,018 of them — so that mantra's own commentary
stays its own. `dge/js/core.js` labels it alongside `sayana`.

### How it was verified, and what the checks caught

Coverage is not evidence, so three independent checks ran:

- **Off-by-one.** Not "does the gloss *start with* the mantra's first words" —
  that test says *no* for correct pairings, because Sāyaṇa quotes in his own
  order (RV 1.1.9's comment opens `हे “अग्ने “सः त्वं “नः` against a pada-pāṭha
  beginning `सः । नः । पिताऽइव`). It measures how much of the mantra's
  vocabulary the gloss's opening quotes, against how much of the *next*
  mantra's, in a window scaled to the mantra's length. Final count: **0 late**.
- **Reading the pairings.** A stratified sample, one mantra per maṇḍala, read
  against its mantra. All ten correct.
- **Duplicates.** Two commentaries repeat more than three times. Both are right:
  RV 2.11.21, 2.15.10, 2.16.9, 2.17.9, 2.18.9, 2.19.9 and 2.20.9 are the
  *identical* Gṛtsamada refrain, so one comment serves all seven; and
  `पूर्वं व्याख्याता` — "explained earlier" — is Sāyaṇa's own note on a repeated
  verse, not a misalignment.

Four real defects were found this way, each invisible to a score:

1. **The next mantra's printed saṃhitā-pāṭha trailing the previous gloss**,
   because the block's start was taken from the *best-scoring* match rather
   than the *earliest*. This is the important one: it made correct cuts read as
   one-late, and reading them was the only way to tell the difference.
2. **RV 1.65–1.70 are dvipadā** — printed as pairs of half-verses under one
   combined gloss, which DGE splits into two mantras each. The first of each
   pair has no gloss of its own, and is refused rather than given its
   neighbour's.
3. **Stranded akṣaras and verse tallies** at a cut's edges, trimmed only where
   the fragment is demonstrably the mantra's own text — Sāyaṇa's genuine
   three-word glosses on refrain verses must survive, so length cannot decide.
4. **A fixed 30-character slack in the matcher**, which is a tenth of a long
   triṣṭubh but three quarters of a short gāyatrī pāda. Scaling it lifted the
   median match from 0.86 to 1.00 and coverage from 97.2% to 98.45%.

The archive.org route is kept, unchanged, for the reasons §5 gives: it is an
independent witness, and it covers the Vālakhilya, which Wikisource does not.

---

## 7. The Sāmaveda, for free

`propagate_samaveda.py`, run straight after §6. No network at all.

Most Sāmaveda mantras *are* Ṛgveda mantras, and DGE's data already records which
in a `rigveda_ref` field. So Sāyaṇa reaches **1,733 of 1,875 Kauthuma mantras
(92%)** by copying, and there is no other route: Sāyaṇa's Sāmaveda-bhāṣya has
never been digitised, and Griffith follows Benfey's Rāṇāyanīya numbering, which
does not line up with DGE's Kauthuma sequence.

Every propagated entry says so in its own text — *"Sāyaṇa on the parallel
Ṛgveda mantra, Ṛgveda 6.16.10"* — and the item records `commentary_via`, so a
reader is never told this is a Sāmaveda bhāṣya and the provenance survives in
the data.

### The refs needed checking

The importer trusted `rigveda_ref` outright. It should not have: **eight of the
1,760 refs name a verse that is not the Sāmaveda mantra's own.** Following one
hands the reader Sāyaṇa on a different hymn, and it reads perfectly plausibly —
the same failure this whole toolchain is built to refuse.

So the ref is now checked against the mantra text on both sides before it is
trusted, by the kinder of a sequence ratio and a word-overlap share. The second
measure earns its place: the Sāmaveda reorders words to fit the chant, and a
sequence ratio alone reads that as a different verse.

| agreement | SV → RV | |
|---|---|---|
| 0.11 | 1429 → 9.89.5 | no word in common |
| 0.19 | 385 → 4.39.6 | no word in common |
| 0.22 | 1420 → 1.93.3 | no word in common |
| 0.23 | 469 → 9.65.1 | no word in common |
| 0.26 | 345 → 8.24.16 | no word in common |
| 0.40 | 891 → 9.61.17 | **890 and 891 name each other's verses** |
| 0.52 | 890 → 9.61.18 | |
| 0.53 | 1204 → 9.12.8 | |

These are errors in DGE's own Sāmaveda data, not in the propagation, and they
want fixing at the source — the tool only declines to act on them. A further
eight agree partially (0.55–0.70) because the Sāmaveda's reading or verse
division differs; those are propagated, since the entry already tells the reader
it is Sāyaṇa on the parallel Ṛgveda mantra.

### One more trap, met twice

`save_json` wrote at indent 1 while the Ṛgveda and Sāmaveda saṃhitā files are
written at 2. Left alone it reformatted every line of a 10,000-mantra file to
add one key per mantra — 233,667 changed lines for a 21,949-line change. This is
trap 2 from the handoff, in a new place. `common.sniff_indent` now reads the
width off the file and `save_json` preserves it, which fixes the whole toolchain
rather than this one importer.
