# Handoff — Veda & Smṛti commentary import  (v4)

## STATE, as of 18 Aug 2026 — read this before the rest of the file

The sections below were written before any of this ran, and their "suggested
order" is now **stale**: it points at the wisdomlib route, which is dead
(wisdomlib 403s every datacenter IP, `/robots.txt` included). Sāyaṇa came from
Sanskrit Wikisource instead. `SOURCES.md` §5–§7 is the current, evidenced record.

### Done

| | |
|---|---|
| **Sāyaṇa on the Ṛgveda** | **10,388 / 10,552 (98.45%)**, from sa.wikisource, CC BY-SA. `wikisource_sayana.py`, 42 tests. |
| **Sāyaṇa on the Sāmaveda** | **1,733 / 1,875 (92%)** by propagation, no network. `propagate_samaveda.py`. |
| `core.js` Gītā `bhashya[]` patch | already in the repo — `core.js:331` iterates `v.bhashya[]`. Do **not** re-apply any patch snapshot. |
| Audio admin fix | already in the repo — `dge/js/audio-detect.js` + a 10-test Node suite. |

Both landed in PR #57 on branch `claude/new-session-65y87b`.

### Not done, in rough order of value

1. **`import_veda_phase2.py`** — Atharvaveda (5,977 items), Śukla Yajurveda
   (1,975) and Taittirīya Saṃhitā (696) all carry **zero** commentary layers.
   Deployed and tested, never run for real.
2. **`import_upanishads.py`** — all 29 Upaniṣad folders hold zero items. Same:
   deployed, tested, never run.
3. **Darśana Nyāya (91 files) and Mīmāṃsā (20)** — every one empty.
   `darshanas.yml` is wired and has never been dispatched.
4. **Smṛti bhāṣya** — Manu (2,685 ślokas), Viṣṇu (2,363), Yājñavalkya (1,011),
   Nārada (805) and Parāśara (580) hold complete **mūla** and **no bhāṣya**. The
   other 15 minor smṛtis are empty. Run `import_minor_smritis.py --probe-only`
   before writing anything.
5. **Wikisource Purāṇas — BLOCKED, not merely undone.** An older handoff sends
   you to `importers/wikisource.py` and `importers/test_wikisource.py`. **Neither
   file exists in this repo**; that package was never deployed. Nothing to run
   until it is.

### Traps, with the count of times each has now bitten

1. **Never apply `patches/core.js` or `core.js.patch`.** Snapshots of main from
   17 Aug; applying one reverts the kosha citations, the tour and the inline
   editor. The edits live in `dge/js/core.js`. **Four times.**
2. **Indent width.** `taxonomy.json` is indent 1; the Ṛgveda and Sāmaveda
   saṃhitā files are indent **2**. Guessing reformats 233,667 lines to make a
   21,949-line change. `common.sniff_indent` now reads it off the file and
   `save_json` preserves it — use `save_json` and don't hand-roll a writer.
   **Five times.**
3. **Never raise a threshold or drift guard to get past it.** They exist because
   a misaligned import looks completely plausible.
4. **A green run that imported nothing is the failure mode.** Check counts, not
   the exit code.
5. **`main` moves fast.** Merge before starting and again before pushing.
   `library.json` is generated — take main's copy, re-derive with
   `audit_library.py --fix`.

### How to verify an alignment, since coverage is not evidence

A systematic off-by-one leaves every score untouched: each mantra still sits
above *some* commentary. Two checks that do work, and both found real defects:

- **Ask which mantra the gloss quotes** — its own, or the next one. Not "does it
  *start with* the mantra's first words": that answers *no* for correct pairings,
  because Sāyaṇa quotes in his own order. Measure how much of the mantra's
  vocabulary the opening quotes, against the next mantra's, in a window scaled to
  the mantra's length. `wikisource_sayana.check_offbyone` does this.
- **Read the pairings.** Every one of the four real defects in the Wikisource run
  was found this way, and the worst of them — the next mantra's printed text
  trailing the previous gloss — made *correct* cuts look one-late. No score
  distinguishes those two cases.

### The full test sweep

```
python tools/sayana_smriti/tests/test_parsers.py          # 15
python tools/sayana_smriti/tests/test_phase2.py           # 49
python tools/sayana_smriti/tests/test_archive_sayana.py   # 28
python tools/sayana_smriti/tests/test_wikisource_sayana.py # 42
node   tools/sayana_smriti/tests/test_core_patch.js       # 10
node   tools/audio_admin/test-audio-detect.js             # 10
python importers/test_gretil_bulk.py
python tools/darshanas/test_darshanas.py
python tools/dvaitavedanta/test_import_offline.py
python tools/validate_data.py
python tools/sayana_smriti/verify_import.py --dge-root dge
python tools/audit_library.py
```

`test_parsers.py` and `test_phase2.py` need `pip install beautifulsoup4`, which
is not in the sandbox by default.

---

## New in v4 — the Upaniṣads, and two corrections

### `import_upanishads.py`

Thirteen principal-Upaniṣad folders exist in `taxonomy.json` and **every one holds
zero items** — the most-read texts in the corpus, and the shelf is bare. This fills
them from two sources whose references ARE the ids, so nothing is inferred:

* **GRETIL corpustei** — `ChUp_1,1.1` is prapāṭhaka 1, khaṇḍa 1, verse 1, and
  `ChUpBh_1,1.1` is Śaṅkara on it, in the same file. One fetch yields mūla *and*
  bhāṣya. Available for Chāndogya, Bṛhadāraṇyaka, Īśā, Kaṭha, Māṇḍūkya, Praśna,
  Śvetāśvatara, Taittirīya, Aitareya.
* **Müller, SBE 1 and 15** — one file per khaṇḍa, in order. The section counts are
  fixed and known (Chāndogya's eight prapāṭhakas run 13, 24, 19, 17, 24, 16, 26, 15
  = 154 khaṇḍas = exactly the 154 files SBE 1 gives it), so file → id is arithmetic.

Two traps found and handled, both of which would have produced plausible-looking
scripture at the wrong references:

* **`sbe15054` holds two sections** — the second *and* third brāhmaṇa of
  Bṛhadāraṇyaka I. Count files instead of sections and every later id shifts by
  one. The parser splits on headings and the importer counts sections.
* **`sbe15098` is Hume's translation, not Müller's** — a duplicate of VI,4. It is
  skipped explicitly.

If a range's section count does not match the declared structure, that Upaniṣad is
**skipped rather than written**. A unit test asserts every shipped range matches,
so the config is right and not merely safe.

No GRETIL mūla exists for Kena, Muṇḍaka, Kauṣītaki or Maitrāyaṇīya (GRETIL lists
them, hosts nothing) — those get the English layer only.

### Correction 1 — Śaṅkara's bhāṣya is NOT missing

My deployables list said the `shankara_bhashya` job never ran. Wrong: it ran, and
landed under `data/darshana/vedanta/advaita/shankara_bhashya/`, not the top-level
path I checked. **Brahmasūtra-bhāṣya (556 units, 864k chars) and Gītā-bhāṣya (1,175
units) are already in the repo.** What is actually missing is nine of the ten
Upaniṣad bhāṣyas — only Aitareya (59 units) landed, though the six other GRETIL
URLs in `importers/shankara_bhashya.py` are live (I fetched
`sa_chAndogyopaniSad-comm.htm` and it is there, with the tags the importer
expects). So that job wants a **re-run**, not a rewrite. And v4's Upaniṣad importer
picks up the same bhāṣya text as a by-product.

### Correction 2 — the empty shelves are much bigger than the Vedas

While auditing I counted the rest of the corpus. Empty grantha folders:
`darshana` 187 of 237 · `vedanga` 93 of 102 · `purana` 90 of 114 · `agama` 17 of 18
· `kavya_alankara` 26 of 30, plus 79 empty folders under `vedas`. The Upaniṣads are
the first slice of that, not the whole of it.

---

# Handoff — Veda & Smṛti commentary import  (v3)

## Also new in v3 — the last empty shelf: `import_minor_smritis.py`

Fourteen smṛti folders and all seven nibandha folders hold **zero items**. The
earlier survey found no e-text for the eleven minor smṛtis anywhere; the one
remaining lead was sa.wikisource.org, which is CC BY-SA, has a clean API, and
carries a category `वर्गः:स्मृतयः` that a search confirmed exists. What could not
be confirmed is *which* of these works it holds — Wikimedia domains are cache-only
from the authoring sandbox.

So the script leads with a probe, and that is the point of its design:

```bash
python import_minor_smritis.py --probe-only     # ~2 min, writes nothing
```

It walks the category tree (following subcategories), probes each expected title
plus its spelling variants — Wikisource is inconsistent about visarga-compounds,
so `अङ्गिरःस्मृतिः`, `अङ्गिरस्स्मृतिः` and `अङ्गिरसस्मृतिः` are all tried — falls
back to full-text search, and prints a table of what exists. **Decide from that
table whether the full run is worth it.** An importer that silently writes nothing
when a source turns out to be empty is indistinguishable from a broken one.

One thing the survey had wrong and the search corrected: the Sanskrit
**Vīramitrodaya** was written off as scan-only, but `वीरमित्रोदयः - श्राद्धप्रकाशः`
is on sa.wikisource. It is in the target list.

Writing goes through the same `merge_into_existing()` as the smṛti importer, so
an empty folder gets created and a populated one is never shrunk. The CC BY-SA
obligation is written into each file's `commentary_sources` — share-alike, not
public domain; DGE is non-commercial and attributes, which satisfies it, but the
obligation is recorded rather than assumed.

## New in v3 — the other four Vedas

v1 and v2 covered the Ṛgveda and the smṛtis. v3 adds the rest of the Vedic corpus,
which today carries **no commentary and no translation at all** — 12,927 items:

| Corpus | Items | What v3 adds |
|---|---|---|
| Atharvaveda Śaunaka | 5,977 | Griffith 1895–6, **and Whitney & Lanman 1905** — Whitney's apparatus is the layer that reports Sāyaṇa's readings |
| Sāmaveda Kauthuma | 1,875 | Sāyaṇa + Wilson **propagated from the Ṛgveda, no network** |
| Śukla Yajurveda Mādhyandina | 1,975 | Griffith 1899 |
| Taittirīya Saṃhitā | 696 | Keith 1914 (HOS 18–19) |

**The Sāmaveda trick is the nice one.** DGE's Sāmaveda data already records, per
mantra, which Ṛgveda mantra it reuses (`rigveda_ref`, in Devanagari numerals).
Measured against the live repo: 1,761 of 1,875 mantras carry a ref and **1,760 of
those resolve** once the numerals are converted (99.9%). So `propagate_samaveda.py`
copies Sāyaṇa and Wilson across for 94% of the Sāmaveda with zero fetching. Every
propagated entry is labelled in its own text — the reader is told they are reading
Sāyaṇa on the parallel Ṛgveda mantra, not a Sāmaveda bhāṣya — and each item records
`commentary_via: "rigveda:6.16.10"`.

Deliberately **not** done: Griffith's Sāmaveda. He follows Benfey's Rāṇāyanīya
arrangement (585 verses against DGE's 650 in the Pūrvārcika, because Benfey omits
the Āraṇyaka-gāna and the Mahānāmnī ārcika). Rather than guess an offset onto a
94%-covered corpus, it is left alone.

Still nothing for the Taittirīya Brāhmaṇa (1,768) and Āraṇyaka (636): no
public-domain English translation of either exists. And no Sanskrit Sāyaṇa for any
of these four — scans only, exactly as with the Ṛgveda.

```bash
python import_veda_phase2.py --dge-root dge --corpus av      # or syv, ts, av-whitney, all
python propagate_samaveda.py --dge-root dge                  # AFTER the Sāyaṇa job
```

`import_veda_phase2.py` fails a corpus whose match rate falls below `--min-match`
(default 50%) — the signature of a parser that quietly stopped working.

---

# Handoff — Sāyaṇa Bhāṣya & Smṛti commentary import  (v2)

For Claude Code, to run in the `bhumandala` repo. Read `AUDIT.md` first: it is the
answer to "is Sāyaṇa loaded, and do the smṛtis have their commentaries" (no, and no).

## What changed in v2 — read this before running the smṛti job

**A correction, and a safety fix that came out of it.** The v1 audit counted
*items* in the smṛti files. Items are adhyāyas. Counting the ślokas nested inside
them shows five smṛtis already hold **complete mūla Sanskrit — 7,444 verses**
(Manu 2,685, Viṣṇu 2,363, Yājñavalkya 1,011, Nārada 805, Parāśara 580). The v1
`import_smriti.py` rebuilt each `data.json` from scratch and wrote it over the
target, so a thin GRETIL parse could have replaced real text with a worse copy.

v2 writes through `merge_into_existing()`: existing `sanskrit_text` always wins,
only missing `artha` and new commentators are added, and the run **refuses to
write at all** if a grantha's verse count would drop. `--allow-mula-overwrite`
exists but is off by default. Verified against the live repo — a Manu run reports
`2,685 existing verses -> 2,685; +0 verses, +3 artha, 6 mūla preserved`.

`import_sayana_rigveda.py` was never affected: it merges per mantra and never
rebuilds a file.

Also new in v2: `patches/core.js` (a drop-in patched file, not a diff to apply by
hand), `tests/test_core_patch.js` (10 tests over it), and `verify_import.py`
(post-run QA — run it before merging the PR).

## Why the dump isn't in this zip

The Cowork sandbox has no scraping egress — `curl` to wisdomlib, sacred-texts,
GRETIL and archive.org all fail at the proxy (`CONNECT tunnel failed, 403`). Only
`git clone` and the model's own fetch tool get out. So the data materialises when
the importer runs in **GitHub Actions**, exactly as the Dasa Sahitya, Ashtadhyayi
and Itihāsa imports did.

What *is* finished and verified here: the doc-ID map, the parsers, the alignment
guards, the merge logic, the workflow, the licence triage. The run is one button.

## Install

```
tools/sayana_smriti/          <- everything except the workflow
.github/workflows/ingest-sayana-smriti.yml
```

```bash
mkdir -p tools/sayana_smriti
cp -r dge-sayana-smriti-import/* tools/sayana_smriti/
mv tools/sayana_smriti/.github/workflows/ingest-sayana-smriti.yml .github/workflows/
pip install -r tools/sayana_smriti/requirements.txt
python tools/sayana_smriti/tests/test_parsers.py     # 15 tests, all green
```

## Run

Smoke test first — 50 mantras, ~1 minute, proves the alignment guard on live pages:

```bash
python tools/sayana_smriti/import_sayana_rigveda.py --dge-root dge --mandala 1 --limit 50 --dry-run
```

Then the real thing (Actions → *Ingest — Sāyaṇa Bhāṣya & Smṛti commentaries*, or):

```bash
python tools/sayana_smriti/import_sayana_rigveda.py --dge-root dge          # ~3.5 h, 10,552 pages
python tools/sayana_smriti/import_smriti.py       --dge-root dge --discover-gdocs
python tools/sayana_smriti/patches/taxonomy_patch.py --dge-root dge
python dge/build_search_index.py
```

The workflow caches HTTP responses by URL, so a timeout-and-rerun resumes rather than
refetching. It opens a PR; it never pushes to main.

## Verify before merging

```bash
python tools/sayana_smriti/verify_import.py --dge-root dge                  # structural
python tools/sayana_smriti/verify_import.py --dge-root dge --spot-check 25  # + refetch 25 random pages
```

It reports Sāyaṇa coverage per maṇḍala, re-checks every dump row against the doc
map independently of the importer's own guard, looks for heading text that leaked
into a commentary, flags duplicate commentary (the signature of an off-by-one),
and — the one people miss — **fails if `core.js` is still unpatched while smṛti
bhāṣya is present in the data**, because that combination looks finished and
renders nothing. Non-zero exit on any FAIL, so it can gate the workflow.

Run against the current unmerged repo it correctly reports
`FAIL [coverage] NO Sāyaṇa commentary found in any maṇḍala`.

## The one thing that will bite you

`import_sayana_rigveda.py` writes commentary keyed by mantra id. If wisdomlib's page
numbering ever shifts, every mantra after the shift gets the *wrong* commentary, and
the result looks completely plausible. So the importer checks two things per page —
the page's own title must report the maṇḍala.sūkta.ṛk we asked for, **and** its
Devanagari must match the mantra already in DGE — and aborts the whole run if more
than `--max-drift` (default 2%) fail. This is tested both ways: it passes on a
correct page and fires on a deliberately misaligned one, printing the two texts
side by side. Do not disable it.

## What you'll need to review

- **`patches/core-js-labels.md`** — two small `core.js` edits. The first is cosmetic
  (proper labels for `sayana`/`wilson`). The second is *required* for the smṛti
  commentaries to be visible at all: the nested-śloka branch of
  `dgeNormalizeGranthaData()` currently hard-codes `commentaries: {}`. That fix also
  unblocks the Itihāsa/Gītā commentary layers from the earlier import.
- **`sources.json`** — every layer has an explicit `rights` field. Layers marked
  `encumbered` (Gharpure's 1936 Yājñavalkya translation, GRETIL's Nārada from
  Lariviere 1989, Bṛhaspati from Aiyangar 1941, Kṛtyakalpataru from GOS 1941–53) are
  **skipped unless** `--include-encumbered` is passed. That's a call for the project
  lead, the same way the ashtadhyayi.com data was.
- **Attribution** — each data file gets a `commentary_sources` block naming the
  commentator, edition, digitiser and licence. Keep a visible credit to
  wisdomlib.org, sacred-texts.com, GRETIL and the UT-Austin transcriptions, as DGE
  already does for ashtadhyayi.com.

## Files

```
AUDIT.md                     what's loaded, what's missing, and from where it can come
verify_import.py             post-run QA: coverage, misalignment, contamination, renderability
rigveda_docmap.json          10,552 mantra id -> wisdomlib doc id (verified, no crawl needed)
common.py                    throttled+cached+retrying fetcher, atomic JSON writes
wisdomlib.py                 heading-driven page parser (survives a reskin; selectors wouldn't)
parsers/sacredtexts.py       SBE volumes 2/7/14/25/33
parsers/gretil.py            GRETIL e-texts, all five verse-tag conventions
parsers/gdocs.py             UT-Austin / Olivelle Google Doc transcriptions
import_sayana_rigveda.py     the headline: Sāyaṇa into all ten maṇḍalas
import_smriti.py             mūla + commentaries for 13 smṛti/dharmaśāstra granthas
sources.json                 source registry with per-layer rights triage
patches/core.js              drop-in patched core.js (both edits already applied)
patches/core.js.patch        the same, as a unified diff against current main
patches/core-js-labels.md    what the edits are and why
patches/taxonomy_patch.py    adds the two new Dharmasutra folders
tests/test_parsers.py        15 tests: wisdomlib, sacred-texts, GRETIL, Google Docs
tests/test_core_patch.js     10 tests: the patched normaliser, incl. regressions
.github/workflows/           the Actions runner
```

## Phase 2 (not in this package)

Sāyaṇa on the *other* Vedas, and the mūla for the empty Brāhmaṇa/Āraṇyaka folders.
Public-domain English sources exist for all of it: Keith's Taittirīya Saṃhitā and his
Aitareya/Kauṣītaki Brāhmaṇas, Griffith's Yajurveda and Sāmaveda, and Whitney's
Atharva-Veda (HOS 7–8), which discusses Sāyaṇa's commentary throughout. Same importer
shape, different page maps.
