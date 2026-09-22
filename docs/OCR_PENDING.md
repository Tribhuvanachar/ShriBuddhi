# What is still outstanding in the OCR backlog

Written 20 Sep 2026. Companion to `docs/OCR_RUNBOOK.md`, which says how to run
a batch; this says what is left to run.

## 1 · Works staged but never landed in `data/`

**94** staging branches exist under `origin/ocr-staging/` (the "63" in an
earlier draft was stale), holding **96** distinct staged works plus three
scaffolding directories (`_gemini`, `_recovered`, `upanishad_tippani`). The
great majority resolve to a grantha the site already serves. These five do
not:

| staging branch | what it holds | blocked on |
|---|---|---|
| ~~`manimanjari`~~ | **landed 21 Sep** — 306 verses, 8 sargas, both ṭīkās | — |
| `aitereya_upanisad_bh__ommentary_bhagavantaraya` | Bhāvapradīpa ṭippaṇī of Bhagavantarāya, 994 pp | segmentation |
| `aitereya_upanisad_bh__tha_ratnamala_commentary` | Bhāṣyārtha Ratnamālā ṭippaṇī, 596 pp | segmentation |
| `aitereya_upanisad_bh__taries_visvesvara_tirtha` | Viśveśvara Tīrtha, with Rāghavendra Tīrtha's Mantrārthasaṅgraha, 320 pp | segmentation |
| `vaidika_svara_prakaranam_prabhakara_adiga_kadri` | Vaidika Svara Prakaraṇam, 108 pp | Sarvam refused all 108 — see below |

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

### Vaidika Svara Prakaraṇam — Vision only, and it is not good enough

This one is not blocked on a shelf. **Sarvam refused all 108 pages with HTTP
402 Payment Required**, and — to the tooling's credit — said so plainly:
`pages_succeeded: 0, pages_failed: 108`, every page carrying its own error.
Nothing here was silently lost; these 108 are part of the 5,342 in §2.

That leaves only the Vision pass, 101,199 characters. Vision alone is not a
sound basis for landing a text on svara, where the accents are the content:
its own first page reads `ನೈನಿಕ ಸ್ವರ ಪ್ರಕರಣಮ್` for *Vaidika* Svara Prakaraṇam
and `ಪಱಮಾರು` for the Palimāru maṭha. With no second engine there is nothing to
cross-check those against.

Landing it waits on the §2 re-dispatch. At 108 pages that is about ₹48.

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
Three of those five layers replace text a reader can see today. Maṇimañjarī is
the argument: Sarvam read one Devanāgarī line as Kannada, a 306-verse work
landed as 305, and nothing downstream noticed.

So the remaining order is:

1. **Gemini-proofread the two staged volumes** — ₹82 at the ledger's measured
   rate. *Not* blocked on credentials: see `docs/CREDENTIALS.md`. The keys are
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
