# What is still outstanding in the OCR backlog

Written 20 Sep 2026. Companion to `docs/OCR_RUNBOOK.md`, which says how to run
a batch; this says what is left to run.

## 1 · Works staged but never landed in `data/`

Re-measured 27 Sep 2026 against `data/library.json`. **104** staging branches
now exist under `origin/ocr-staging/` (94 of them `ocr-staging/*`, plus 10
`buddhi-archive/*`), of which 31 are the `hks__*` parts of one work and 22 the
`sudha_25_tippani_v*` volumes of another.

**The earlier "these five do not resolve" was wrong**, and wrong in both
directions. It came from matching a branch name against library paths by
substring, which reports a hit whenever any path happens to contain the
letters: `usha` matches `nyaya_bhushana`, `dipika` matches
`hathayogapradipika`, and `sudha` matches nine unrelated works. Checked
properly, three of those five have landed and ten works it never mentioned
have not. A loose match is worse than no inventory, because it reports
comfort.

### Landed since that draft

| staging branches | where it now lives |
|---|---|
| `manimanjari` | `Tattvavada/Itara/Kavya/manimanjari` — 306 verses, 8 sargas, both ṭīkās |
| `rukminisha_vijaya` | `Tattvavada/Itara/Kavya/rukminisha_vijaya` — **1,171 verses, 19 sargas**, 1,092 with the Gurubhāvaprakāśikā, 68 declared lacunae |
| `venkatesha__venkatesha_mahatmya_vyakyana_sahita` | `purana/maha_purana/bhavishya_purana/uttara_parva/venkatesha_mahatmya` — **1,523 verses, 11 adhyāyas**, 801 with a commentary and 407 with both, 64 declared lacunae |
| `sudha_25_tippani_v1..v22` | `…/anuvyakhyana_sudha` — mūla 2,524 + Nyāya Sudhā 7,826 + six ṭippaṇīs = **27,413 units** |
| all three `aitereya_upanisad_bh__*` branches | `…/aitareyopanishad_bhashya/` — **all 1,406 blocks placed**, seven layers totalling 2,100,535 characters. The Bhagavantarāya ṭippaṇī is `tika_bhavapradipa`, 38 items and 555,029 characters; I listed it as pending twice after landing it |
| `hks__1..31` | `Tattvavada/Itara/DasaSahitya/harikathamrutasara` |
| `vaidika_svara_prakaranam_prabhakara_adiga_kadri` | `vedanga/shiksha/pratishakhya/vaidika_svara_prakarana` — **99 sūtras in four sections plus 7 prose passages**, 77 with the ಅರ್ಥ gloss, 86 with a topic from the book's own contents page, 0 lacunae |
| `pasandakhandanam_vad__mentary_surottama_tirtha` | `Tattvavada/Itara/pasandakhandana` — **129 verses**, all with Surottama Tīrtha's vyākhyā, 0 lacunae |
| `brahma_sutra_dipika_jagannatha_tirtha_panchamukhi` | `…/DvaitaVedantaIn/sutra_prasthana/brahmasutra_dipika` — **500 sūtras across 15 pādas**, 29 declared lacunae |
| `usha_harna_trivikram__irtha_vadirajacharya_l_s` | `Tattvavada/Itara/Kavya/ushaharana` — **726 verses in nine sargas** with the Rasikarañjanī, 18 declared lacunae |
| `brhatisahasram_tattvasara_raghunatha_tirtha` | `Tattvavada/Itara/brhatisahasra` — **986 verses** with the Tattvasāra; the work's own numbering reaches 1000, 14 declared lacunae |
| `108_upanishad_sarvas__narasimha_1_ttd_kannada` | `vedas/upanishad_sarvasva_kannada` — **25 Upaniṣads, 1,308 mantras**, 1,273 with the Kannada tātparya. Bhārgava Narasiṃha's compilation; boundaries confirmed against the volume's own contents page |

### Still not landed

Three works, eleven branches — all of them multi-volume. Each was checked
against every spelling of its name that occurs in `data/`, not by substring.

| staging branch | what it holds | blocked on |
|---|---|---|
| `ruksamhita__…_bhaga_1` … `_bhaga_5` | Ṛksaṃhitā, 9 vyākhyānas, 5 volumes | segmentation; no counterpart anywhere under `data/vedas/rigveda` |
| `giia_vyakhyana_sangr__…_v1` … `_v4` | Gītā Vyākhyāna Saṅgraha, commentaries on the Bhagavad Gītā, 4 volumes | segmentation |
| `sangraha_ramayanam_n__…_dipi_v1`, `_v2` | Saṅgraha Rāmāyaṇam with the Bhāvārtha Dīpikā | segmentation |

Every one of these is blocked on the same thing: a segmenter. The OCR exists.
What does not exist is the reading of how that particular edition prints its
divisions, and the two landed this week are a fair measure of what that costs —
each needed four or five structural facts that were invisible from any single
page and silent when got wrong. See the commit messages for
`tools/rukminisha/segment.py` and `tools/venkatesha/segment.py`.

### Three things worth carrying to the next one

**Check both danda forms.** The Veṅkaṭeśa Māhātmya closes 1,280 verses with
॥ N ॥ (U+0965) and 584 with ।। N ।। — two U+0964 single dandas. Reading only
the first lost 31% of the markers and did not look like loss: one adhyāya
simply appeared to carry little commentary.

**Count it across the book before believing it.** `data-layout="section-title"`
means the commentary heading in the Veṅkaṭeśa Māhātmya and means nothing at all
in Rukmiṇīśa Vijaya, where there are 78 of them against ~2,480 verse markers.
Sampling one page and generalising would have produced a 37-verse mahākāvya.

**Never search for a Sanskrit word by its citation form.** Three works running,
the same trap: the word is joined to what precedes it and its first vowel is
gone. `अधिकरणम्` had to be matched as `धिकरणम्`, `ಸೂತ್ರಾರ್ಥ` needed its own
alternative beside `ಅರ್ಥ`, and in the 108 Upaniṣad Sarvasva searching for
`ಉಪನಿಷ` found **not one** of the twenty-five colophons, because every name ends
in a vowel that swallows the उ — ಮಾಂಡೂಕ್ಯ + ಉಪನಿಷತ್ is written ಮಾಂಡೂಕ್ಯೋಪನಿಷತ್.
Match from inside the word. The failure is silent and total: a regex that
matches nothing reports the same "0 found" as a book that genuinely has none.

### Maṇimañjarī — landed 21 Sep

Now at `data/Tattvavada/Itara/Kavya/manimanjari/sarga_1..8/data.json`, beside
`sumadhva_vijaya` — same author, Nārāyaṇa Paṇḍitācārya — in the
`{metadata, shlokas}` shape that shelf uses, and registered as eight entries in
`data/library.json` (1,708 → 1,716 granthas). **306 verses across 8 sargas,
each carrying both commentaries: 612 commentary units, no verse missing
either.** Built by `tools/build_manimanjari.py`, which refuses to write unless
all three layers land on the canonical sarga counts.

Both commentaries, Sanskrit and Kannada, are by **Śrī Rāyapalya
Rāghavendrācārya** — read off the edition's own title page (Sri Trilokyacharya
Sevaka Vrinda, Bangalore, 1st edn 2003), not inferred.

Two defects in the staged split had to be repaired first. Both were verified
against the page images of the scan, not guessed:

**The Kannada ṭīkā had one block with no verse number**, labelled sarga 4, on
PDF p173 — which is exactly the gap between Kannada sarga 3 (ends p172) and
sarga 4 (begins p174). Its text glosses mūla 3.31 word for word and tracks the
Sanskrit ṭīkā on 3.31 phrase for phrase. Relabelled 3.31, which brings sarga 3
from 30 to its canonical 31 and leaves sarga 4 complete at 1..39.

**Mūla 4.30 was missing outright** — sarga 4 ran 1..39 with a hole at 30, while
the Sanskrit ṭīkā carried all 39 and its 4.30 opens with the pratīka
`नीलामिति`, so the verse certainly existed. The page image of PDF p190 shows it
printed in **Devanāgarī** between 4.29 and the Kannada gloss; Sarvam read that
one line as Kannada, which is why the splitter never saw it. Vision read it
correctly except for `पुत्र` where the page prints `पुत्रीं` — the reading the
ṭīkā's own gloss (`पुत्री नीलां`) and the anuṣṭubh metre both require:

> नीलां नग्नजितःपुत्रीं मित्रविन्दां पितृष्वसुः ।
> भद्राञ्च कैकयसुतां लक्षणां स्वां च सोऽवहत् ॥ ३० ॥

Both repairs are recorded in the emitted unit's `provenance`, so a reader or a
later editor can see that those lines did not come from the OCR of that line.

**This is the general failure, not a Maṇimañjarī quirk.** Sarvam mis-scripting
a Devanāgarī line as Kannada in a bilingual edition drops it silently — the
splitter cannot miss what OCR never produced, and nothing downstream noticed a
306-verse work arriving with 305. Only comparing the layers against each other
caught it. Every bilingual work staged the same way should be counted layer
against layer before it is landed.

**Verified live, not just in the JSON.** Sampled first, last and two random
verses in every sarga — 32 pages — served locally and driven in a real browser:
each one carries its mūla and *both* ṭīkās. Verse 4.30 renders in place with
the numbering running 26→39 unbroken, and sarga 3 now reads "26–31 of 31".

Two failures in that sweep were the harness, not the site, and are worth
recording so the next person does not repeat them. Aborting the external CDN
requests — an attempt to stop a hanging request from holding up `networkidle`
— stopped the app booting at all and took down 29 of 32 pages. And `js/offline.js`
registers a service worker, so after the first navigation every later one goes
through it; in a sandbox with no external network it stalls them, which is why
exactly the first page of each run loaded. Block service workers in the test
context and wait on `window.stotraData` rather than on network quiet. Pages
that appeared to time out at 25s load in about 600ms when retried alone.

The sweep did surface one real defect, since fixed (b6534113e4): a grantha with
no recorded audio asked the server for `undefinedundefined30undefined`.

Maṇimañjarī 404s on four optional per-grantha side-indexes other works have —
`_padaccheda`, `_references`, `_commentary_sandhi` and
`vedanga/vyakarana/dhatu_prayoga/by_grantha`. The reader is fine without them;
the enrichment is simply absent until they are built.

### Maṇimañjarī — 152 pages of the same PDF were never OCRed

The source scan is 472 pages and its title page reads "Pages : 96 + 188 + 152".
Only the middle section was staged (PDF pp 122–312): the mūla with its two
ṭīkās. The other two are untouched — pp 1–121 a Kannada introductory essay, and
pp ~313–472 a separate Sanskrit work, whose running head at p331 reads
`माणिमञ्जरीखण्डनम्`. The title page names a third text,
**Maṇimañjarīvaibhavam of Śrī Bālagāru Śrīnivāsācārya**. That is ~160 pages of
unstaged content in a PDF already in hand, and it is not in the 5,342 figure
below, which counts only pages Sarvam refused.

### Vaidika Svara Prakaraṇam — landed 27 Sep

This section used to say two things and neither survived a check.

**"Sarvam refused all 108 pages."** It did on 20 Sep, with HTTP 402 Payment
Required — an empty prepaid balance, returned before any page is read and never
billed, not a refusal of the content. The re-dispatch then ran on 22 Sep at
09:54 IST and took all 108: `pages_succeeded: 108, pages_failed: 0`. This file
was written on the 20th and nobody came back to it.

**"Vision alone is not a sound basis... its own first page reads ನೈನಿಕ ಸ್ವರ
ಪ್ರಕರಣಮ್ for *Vaidika* and ಪಱಮಾರು for Palimāru."** Both misreadings are real and
both are on **page 1, the decorative cover**. The title page is p3, where the
same Vision pass reads `॥ ವೈದಿಕ ಸ್ವರ ಪ್ರಕರಣಮ್ ॥` and `ಶ್ರೀ ಪಲಿಮಾರು ಮಠ` correctly,
as does the imprint on p4. The evidence for distrusting the engine was three
pages from its own correction.

Both engines cover the body and agree closely — 106 pages, Kannada characters
only, order-sensitive: median 0.976, mean 0.964, worst page 0.834.

Now at `data/vedanga/shiksha/pratishakhya/vaidika_svara_prakarana/`, beside
rigveda_pratishakhya and shaunakiya_chaturadhyayika, because that is what the
book says it is. **99 sūtras in four sections, 0 lacunae**, plus the seven prose
passages between them; 77 carry the ಅರ್ಥ gloss as a commentary and 86 carry
their own topic from ಅಥ ವಿಷಯಾನುಕ್ರಮಣಿಕಾ. 98% of the body's Kannada is under an
address. The first Kannada work on the shelf. See the commit message for the
four structural facts it cost.

### Aitareya — the earlier claim here was wrong

An earlier draft of this file said the SarvaMula copy being "live with 367 units
and not one commentary layer" was "the largest single gap". That is not a gap.
**All ten** SarvaMula `upanishat_prasthana` works are a single flat `data.json`
with no layer subdirectories — that is how that shelf is built. Commentary
layers live on the `DvaitaVedantaIn` shelf, and Aitareya has four of them there
(mūla, bhāṣya, bhāvapradīpa, upaniṣat) totalling 1,048,259 characters, the third
largest of the ten books. Aitareya is not underserved.

What the three staged volumes actually add, measured as 20-character shingles
sampled every 101 characters against every existing Aitareya layer:

| staged volume | Devanāgarī chars | new, whole volume | new, commentary only |
|---|---|---|---|
| `bhagavantaraya` | 980,202 | 41.3% | **16.6%** |
| `ratnamala` | 740,307 | 81.5% | **69.5%** |
| `visvesvara_tirtha` | 431,585 | 70.6% | not yet segmentable |

**Read the last column, not the third.** The whole-volume figure counts the
mūla and bhāṣya these editions reprint alongside their commentary — text the
shelf already holds — as though it were new. Segmenting the commentary out
(see below) drops `bhagavantaraya` from 41.3% to 16.6%: it is the Bhāvapradīpa
already on the shelf, in a cleaner edition, and it matches the existing
`tika_bhavapradipa` at 37.0%, far above its match to any other layer. Worth
landing for quality, not for content.

`ratnamala` is the volume that carries real new material.

**The blocker was segmentation, and it is now largely solved** —
`tools/aitareya/segment.py`, with `tests/test_aitareya_segment.py`. Output is
staged to `data/ocr_staging/aitareya/`, not written into the corpus.

`tools/upanishad_tippani/build_verify.py` could *not* be extended to cover
these, which is what an earlier draft assumed. It keys off a label convention
— `वे.श्रुत्यर्थः-`, `अ.सं.-` at line start — used by the multi-commentary
Viśvamadhva Mahāpariṣat volumes. Measured against these three: **one matching
line in 15,662**. They are single-commentary PPVP editions and carry no such
labels. Each needed its own rule.

**`bhagavantaraya` — two interleaved streams.** The scan interleaves two
separately-paginated texts, and the split is exact: of the pages whose running
head OCR'd, **all 370 carrying `श्रीमन्महैतरेयोपनिषद्भाष्यम्` are odd PDF pages
and all 359 carrying an `आ-२, अ-१, खं-१` coordinate are even ones**, with no
exceptions either way. That coordinate is āraṇyaka/adhyāya/khaṇḍa — *precisely
the address the target uses*. It yields **38 khaṇḍa spans, and the shelf's
`tika_bhashya` has exactly 38 distinct addresses**. They correspond one to one.

But the honest figure is worse than the one recorded above. Once the ṭippaṇī
stream is isolated from the bhāṣya stream printed alongside it, this volume is
only **16.6% new**, not 41.3%. The earlier number counted the bhāṣya pages —
text the shelf already holds — as though they were part of the commentary. This
volume is the Bhāvapradīpa the shelf already has, in a cleaner edition; it is
worth landing for quality, not for new content.

**`ratnamala` — section labels, and it is the valuable one.** One stream,
divided by standalone label lines ending in a dash: `टिप्पणी-` (269),
`भाष्यम्-` (260), `उपनिषत्-` (110), `खण्डार्थः-` (26). Those are the shelf's own
layer names, and two of them — the Bhāṣyārtha Ratnamālā ṭippaṇī and the
Khaṇḍārtha — the shelf lacks for Aitareya entirely. **665 blocks, 696,404
characters, 69.5% new.**

Its blocks are addressed by matching its own `भाष्यम्` runs against the shelf's
`tika_bhashya`, which states the address; the address then travels forward to
the ṭippaṇī that comments on it. **640 of 665 blocks addressed (96%)** from 75
confident matches, the remaining 25 being front matter before the first match.

The evidence that the addressing is *correct* and not merely populated is that
the 31 resulting spans come out **in the volume's own order, with zero
out-of-order transitions in 30**. Nothing in the matcher constrains that — each
block is matched independently against all 38 candidates — so monotonicity is a
result, not a construction. Dropping the 0.30 match floor to 0.02 destroys it,
which is what the test asserts.

**`visvesvara_tirtha` — segmented, but coarsely.** A third rule, added 22 Sep.
Its recto running head reads `द्वितीयप्रघट्टके प्रथमोऽध्यायः`: this edition
divides by **prāghaṭṭaka** rather than āraṇyaka, and prāghaṭṭaka 2 and 3 are
āraṇyaka 2 and 3, which is exactly the span the volume covers. 128 of its 320
pages carry that head — the rectos — giving eight transitions that come out in
the volume's own order. **298 blocks, 408,112 characters, 56.6% new.**

Two limits, both real and both recorded rather than papered over. The head
gives an **adhyāya, not a khaṇḍa**, so these blocks cannot be addressed as
finely as the shelf keys its units; they land on the first khaṇḍa of their
adhyāya and carry `coarse: True`. And the sequence jumps from adhyāya 4 to
adhyāya 6 — either adhyāya 5's head never OCR'd or it is very short — so pages
between them forward-fill to 4 and some may belong to 5.

### What remains before any of it can be attached

**The pipeline, corrected.** An earlier draft here said review in
`admin/ocr-review.html` should precede merging. That is not the order. It is:

> staging holds OCR'd **and Gemini-proofread** text → placed in the library →
> tested and screenshotted → merged to main → **review happens in BrahmaBuddhi**

`admin/ocr-review.html` is a tool, not a gate.

**The writer now exists** — `tools/aitareya/write_layers.py`, with
`tests/test_aitareya_write_layers.py`. It turns segmented blocks into the
shelf's `items` shape, borrowing each unit's `unit_title` from the shelf's own
`tika_bhashya` at the same address so new layers stack with the units already
there. A block addressed to a khaṇḍa the shelf lacks is skipped and counted,
never given an invented heading.

What it would write today:

| volume | layer | items | chars | |
|---|---|---|---|---|
| bhagavantaraya | `tika_bhavapradipa` | 36 | 583,338 | replaces existing |
| ratnamala | `tika_bhashyartha_ratnamala` | 31 | 451,383 | **new** |
| ratnamala | `tika_khandartha` | 17 | 104,207 | **new** |
| ratnamala | `tika_bhashya` | 31 | 165,685 | replaces existing |
| ratnamala | `tika_upanishat` | 31 | 44,132 | replaces existing |

**It refuses to run.** The staged files record no Gemini proofread pass, and
the tool will not put raw OCR on the shelf without `--allow-unproofread`.

> **22 Sep 2026 — 825 of 1,406 blocks are now proofread**, so the refusal is
> partial rather than total:
>
> | volume | blocks | proofread |
> |---|---|---|
> | bhagavantaraya | 443 | 373 |
> | ratnamala | 665 | 452 |
> | visvesvara_tirtha | 298 | **0 — the run died before reaching it** |
>
> JagatTest run 35687670866 hit the 240-minute job ceiling because that repo
> was still running the pre-concurrency `proofread.py` (one call at a time,
> ~17 s a block); its push back to this repo was then rejected because
> `SHRIBUDDHI_TOKEN` can read ShriBuddhi but not write to it. The paid work
> survived in the run's artifact and was merged here by
> `tools/aitareya/land_proofread.py` — every one of the 825 matched on both
> its address and its raw text, nothing was refused.
>
> **Before rerunning, one setting must change** (either is enough):
> give `SHRIBUDDHI_TOKEN` Contents: Read **and write**, or — now that
> ShriBuddhi is public and its Actions minutes are free — add
> `GEMINI_API_KEY` here and run the workflow in the same checkout as the
> data. The workflow now refuses to start without a provable push, rather
> than spending first and finding out last. See `docs/RESOURCES.md` §4.
>
> Remaining: 581 blocks, roughly ₹30. A rerun skips anything already
> carrying `text_proofread`.
Three of those five layers replace text a reader can see today. Maṇimañjarī is
the argument: Sarvam read one Devanāgarī line as Kannada, a 306-verse work
landed as 305, and nothing downstream noticed.

So the remaining order is:

1. **Gemini-proofread what is left** — 581 blocks, about ₹30 (825 of 1,406
   are already done; see the note above). At the ledger's measured rate the
   three volumes together were ₹85. *Not* blocked on credentials: see `docs/CREDENTIALS.md`. The keys are
   GitHub Actions repository secrets and the paid engines run in workflows, so
   a container with no keys still dispatches them over the REST API. An earlier
   note here said this was blocked because the environment had no
   `GEMINI_API_KEY`. That was looking in the wrong place.
2. Run the writer, render, screenshot, merge to main.
3. **A third rule for `visvesvara_tirtha`** — still unsegmented.
4. **Sub-khaṇḍa addressing**, optional: blocks sit at khaṇḍa level, which
   matches the shelf, but the pratīkas would allow finer placement.

### Empty layer directories — 20 of them

Every one of the ten `Anandamakaranda/upanishad_prasthana` books carries a
`tika_jayatirtha` and a `tippani` directory whose `data.json` holds zero items.
That is 20 empty layers shelf-wide, not an Aitareya problem. Whether they
render as empty layers to a reader has not been checked.

## 2 · Pages billed to Sarvam that never came back

`admin/config/ocr_sarvam_missing.json` — **5,342 pages across 27 works**, all
under runs that reported success. Re-dispatching them is a paid re-run and
needs the lead's word on the money first. The heaviest:

| work | pages |
|---|---|
| rukminisha_vijaya | 694 |
| tantrasara_sangraha_tippani_b | 567 |
| tantrasara_sangraha_tippani_a | 566 |
| taittiriya_upanishad_bhashya_tippani | 546 |
| bhagavata_saroddhara | 459 |
| katha_upanishad_bhashya_tippani | 438 |
| mundaka_upanishad_bhashya_tippani | 417 |

## 3 · Harikathāmṛtasāra

Complete as a work: 1,010 padyas, all 33 sandhis, 935 carrying commentary
across nine layers, no sandhi empty. What remains is listed padya by padya in
`docs/HKS_COMMENTARY_GAPS.md`, regenerated by `tools/hks_commentary_gaps.py`.

~~No source URL is recorded for any of the 31 HKS volumes.~~ **Closed.** All 31
now sit in `admin/config/ocr_sources.json` with `pdf_url`, `view_url`,
`drive_file_id`, page count and the sandhi each covers, every one verified by
page count against the scan on 21 Sep.

## 4 · Maṇimañjarī, sarga 6 — settled

The 16 Sep handoff left this open: two independent sources counted the sargas
31, 32, 31, 39, 51, **52 / 51**, 29, 41, and sarga 6 was the one disagreement,
"worth one look at the page".

Looked. PDF page 261 (472-page source, page count confirmed against the staged
`pdf_pages`), read off the scan directly rather than through either engine:

* the verse is printed `॥ ೫೨ ॥`
* under it, `इति ... मणिमञ्जर्यां षष्ठः सर्गः ॥` closes the sixth sarga
* the Kannada gloss closes `॥ 52 ॥` too

**Sarga 6 has 52 verses.** The count that said 51 missed the closing verse,
which is easy to miss because it changes metre -- it is upajāti where the
sarga's body is anuṣṭubh, which is exactly what a sarga-closing verse does.

Two small things in that verse, for whoever lands this work:

* staged `स्ववर्त्मबाह्यनपि`, printed `स्ववर्त्मबाह्यानपि`. The print is right:
  the pāda needs eleven syllables and the OCR reading gives ten.
* staged `तस्य`, printed `तंस्य`. Here the OCR is right and the anusvāra is the
  page's own slip.

## 5 · The Sarvam pages that "never came back" — settled

They were never done, so there is nothing to reclaim. Of the 5,342:

| recorded reason | chunks | pages |
|---|---|---|
| `HTTP Error 402: Payment Required` | 41 | **5,202** |
| `HTTP Error 500: Internal Server Error` | 12 | 140 |

A 402 is Sarvam refusing the job because the prepaid balance was empty. It is
returned **before** any page is read, so those 5,202 pages were never
processed and never billed. The cost ledger agrees: the eleven works that are
nothing but 402s -- rukminisha_vijaya, both tantrasara ṭippaṇīs, taittiriya,
katha, mundaka, isha, prashna, mandukya, kena, bhagavata_saroddhara,
vaidika_svara -- carry **₹0.00** between them. The works that DO carry a
charge are the ones that succeeded and lost only a 10-page chunk to a 500.

So no money went missing. What went missing was the truth: on 18 Sep every
slice of all 32 chunks kept calling after the first 402, 4,606 pages came back
refused, **and the runs reported success**. We believed we held OCR we did not
hold. `sarvam_docai.py` now aborts the chunk on the first 402 and exits 1 on
any failed page, so that particular lie cannot be told again.

### What to do

1. **Re-dispatch the 5,342.** At the rate the ledger actually shows --
   ₹8,998.88 for 20,452 pages, ₹0.44 a page -- that is about **₹2,350**.
2. **Check the balance before dispatching, not after.** The batch knows its
   own page count; refusing to start when the balance will not cover it turns
   a silent 402 storm into one line of output.
3. **The 140 pages lost to 500s are worth one email, not a claim.** Ask Sarvam
   whether a job that ends in a 500 is metered. At ₹0.44 a page the answer is
   worth about ₹62, so ask for the policy rather than the refund -- the value
   is knowing, for the next 20,000 pages, whether a server error costs us.
4. **Reconcile the ledger against a real invoice.** Every row says so itself:
   "per-page rate is the published list price, confirm against the invoice."
   ₹8,998.88 is our arithmetic, not Sarvam's. Until one invoice is checked
   against one month of rows, the ledger is an estimate.

## 6 · Source URLs — 42 of 96 recorded, now 71

The same failure §3 recorded for Harikathāmṛtasāra ran much wider: only 42 of
the 96 staged works had a recorded source, so most of the corpus could not be
re-OCRed, page-checked against the scan, or re-derived if its staging branch
were lost.

Most of it was never actually lost, only unindexed. Every staged file written
by `sarvam_docai.py` and the Vision runner carries a `source` block naming the
PDF it came from, sitting unread inside the staging branches.
`tools/recover_ocr_sources.py` reads them back — offline, via `git cat-file`
against refs already on disk, touching no branch — and merges what it finds
into `admin/config/ocr_sources.json`. Hand-written entries always win; only a
work with no URL at all gets a recovered one, and those rows are tagged
`recovered_from` so the two can be told apart. Re-running it adds nothing.

**42 → 71 works now carry a `pdf_url`.** It is idempotent and safe to re-run
after any new batch.

The remaining 25 staged works record no URL anywhere, in any of their files.
For those the provenance is genuinely gone and has to be supplied by hand.
One work, `raghavendra_vijaya`, records a bare filename rather than a URL;
that is dropped rather than written in as though the source were known.

**This should be enforced, not repeated.** A staged file with no fetchable
`source.pdf` is a work we cannot go back to. `sarvam_docai.py` should refuse
to write one.
