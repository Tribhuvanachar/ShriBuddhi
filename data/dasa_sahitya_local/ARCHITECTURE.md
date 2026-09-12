# Dasa Sahitya — two folders, one eventual corpus

Two independent sources of Dasa Sahitya (Dasara Padagalu / Suladi / Ugabhoga
/ ...) now exist side by side under `dge/data/`:

| | `dge/data/DvaitaVedanta/Itara/DasaSahitya/` | `dge/data/dasa_sahitya_local/` |
|---|---|---|
| Source | Web crawl (madhwafestivals, dasasahithyamahithi, dasasahitya.net, ...) | Local Android-app SQLite assets (e.g. `dasa1.db`) |
| Built by | `tools/DvaitaVedanta/Itara/DasaSahitya/import_DvaitaVedanta/Itara/DasaSahitya.py` | `tools/DvaitaVedanta/Itara/DasaSahitya/import_dasa_sahitya_local_db.py` |
| Composers | 34 files, ~1396 compositions | 135 dasaru (`dasa1` alone), 13540 keerthanas |
| Composer names | Latin/English (romanized by the scraper) | Kannada (native, from the app's own `dasaru` table) |
| Attribution quality | 453 of 1396 (32%) filed as `untitled` — no composer known | Every row has a `dasaru_id` FK — no untitled bucket |
| Form/genre tagging | Parsed from page structure, fairly reliable | Guessed from a numeric `category` column (0-5), **unconfirmed** — see below |

They are kept separate on purpose, not because a merge is hard to write, but
because a merge done now would silently commit to guesses that haven't been
checked by a human yet (composer identity, category→form mapping). Everything
new lives under its own folder, tagged `pending`, until that review happens.

## Why "local" isn't one file — four sources now, a fifth expected next month

Turned out "local Android app assets" was one of **four independently-shaped
sources**, not one: an Android SQLite DB, a Firestore-style personal-
collection export, and a plain flat-JSON text dump, each needing its own
importer since none share a schema. Every source lands in its own subfolder
(`dasa_sahitya_local/<asset-name>/...`) so nothing overwrites a sibling:

```
dge/data/dasa_sahitya_local/
  dasa1/                       -- Android SQLite asset (dasa1.db): 135 dasaru, 13540 keerthanas
    index.json                          -- manifest: counts, category guess, per-dasaru file list
    cross_source_duplicate_review.json  -- composer-level overlap vs DvaitaVedanta/Itara/DasaSahitya/ (web crawl), tagged pending
    dasaru/<slug>.json
  collection_padagalu/         -- Firestore-style personal-collection export: 4 dasaru, 145 compositions
    index.json                          -- only source with genuine parallel Kannada + English-transliteration text
    dasaru/<slug>.json
  raw_dump/                    -- flat JSON arrays, no titles/metadata: 4 files, 1043 items
    index.json                          -- includes one unattributed genre-only file (ugabhoga.json, 278 items)
    dasaru/<slug>.json
  ALL_SOURCES_composer_registry.json    -- composer-level counts across all 4 sources, for the 5 composers appearing in 3+
  ARCHITECTURE.md              -- this file
```

Each importer takes `--asset-name` so the next batch (one more source
expected next month) lands in its own subfolder the same way:
```
# SQLite asset (Android app DB)
python3 tools/DvaitaVedanta/Itara/DasaSahitya/import_dasa_sahitya_local_db.py \
    --db /path/to/dasaN.db --out dge/data/dasa_sahitya_local --asset-name dasaN

# Firestore-style {index.json + one <slug>.json per dasaru} export
python3 tools/DvaitaVedanta/Itara/DasaSahitya/import_dasa_sahitya_collection_json.py \
    --src-dir /path/to/export --out dge/data/dasa_sahitya_local --asset-name <name>

# Flat JSON-array-per-file dump, no per-record composer/metadata
python3 tools/DvaitaVedanta/Itara/DasaSahitya/import_dasa_sahitya_flat_json.py \
    --src-dir /path/to/files --out dge/data/dasa_sahitya_local --asset-name <name> \
    --composer-map file.json=ಕನ್ನಡಹೆಸರು ... --no-composer-files genre_dump.json --no-composer-form ugabhoga
```
Raw source files themselves are **not** committed (they're asset dumps, not
source code); only the generated JSON is. Re-run an importer whenever a
fresher copy of that asset shows up — it's a full regenerate, not additive.

## What "pending" means here, concretely

1. **Composer identity** — `dasa1/cross_source_duplicate_review.json` has
   three tiers:
   - `confirmed_duplicates` (12 composers): Kannada name and English name
     are unambiguously the same person, hand-checked after an automated
     fuzzy pass. Safe to merge once someone signs off on the record-level
     merge strategy (below).
   - `needs_human_review` (5 composers): name-root looks related (shared
     "Gopala"/"Prasanna"/"Jagannatha" stem) but Haridasa tradition reuses
     ankita names and honorifics across gurus and disciples, so a same-root
     match is not proof of the same person. Needs a Kannada-literate human
     call, not another regex.
   - Everything else (~117 of 135 app dasaru, ~4800+ keerthanas) has **no**
     plausible match — genuinely new to the corpus, not a duplicate at all.
   - The file also flags **`untitled.json`'s 370 attributable compositions**
     on the web side as a concrete merge opportunity: cross-matching their
     Kannada verse text against dasa1's fully-attributed 13540 keerthanas
     could recover a real composer name for a chunk of that 453-item pile.
   - `ALL_SOURCES_composer_registry.json` extends this across all four
     sources: **5 composers (Purandara, Kanaka, Vyasarayaru, Sripadarajaru,
     Gopala) now each appear in 3-4 sources independently**, with counts
     that don't obviously nest inside one another (e.g. Purandara: 306 web /
     983 dasa1 / 54 collection_padagalu / 305 raw_dump) — meaning composer
     identity is settled for these 5, but composition-level overlap isn't:
     the same fingerprint-based `dedupe()` already in
     `tools/DvaitaVedanta/Itara/DasaSahitya/import_DvaitaVedanta/Itara/DasaSahitya.py` needs to run across all
     four sources' records for these 5 names before merging, since a close
     count (raw_dump's 305 vs web's 306) could mean near-total overlap or
     two mostly-disjoint sets that happen to be similarly sized.
   - `raw_dump/ugabhoga.json` (278 items) is a **genre-only dump with no
     composer attribution at all** — imported with `composer:""` rather
     than guessed, specifically so it doesn't get silently mis-attributed
     to Purandara Dasaru just because ugabhogas are historically associated
     with him.

2. **Category → form mapping** — the app DB's `category` int (0-5) was
   reverse-engineered from ~30 sampled rows per bucket, not documented
   anywhere:
   - `0` → `pada` (default bucket, 88% of rows — not a positive signal)
   - `1` → `ugabhoga`, `5` → `suladi` (consistent header keyword found)
   - `2` → `mundige` (riddle-padas, mostly Kanakadasa; **not yet in the
     existing `dasa_pada_text` form enum** — needs a schema addition)
   - `3` → `pada` (no consistent header keyword found — least confident)
   - `4` → `devaranama` (rows carry an explicit structured trailing block:
     song name / singer / raga / tala / style / music director / studio —
     reads like modern recorded renditions, not classical compositions;
     worth a second look at whether these belong in `dasa_pada_text` at all
     or need their own record type)

   Each imported record carries `form_confidence` explaining which case it
   is, and the manifest (`index.json` → `category_confidence`) has the same
   breakdown at the bucket level.

3. **Verse-body parsing** — `txt` mixes a variable metadata header (composer
   name repeat, a one-line description, a genre word) with the verse body,
   `<br>`-joined, no stanza markers. The importer strips only lines it can
   positively identify (exact composer-name match, known genre keywords, the
   structured trailing block for category 4) and leaves everything else
   as-is — under-stripping on purpose, since a stray header line sitting in
   the body is easy for a human to spot and fix, while over-stripped verse
   text is silently gone. 154 of 13540 records (1.1%) are flagged
   `_needs_review: true` — either genuinely empty verse text or leftover
   punctuation-only artifacts from the source.

## Publishing-size flag — resolved: mirrors the wordnet pattern

Decided and implemented (19 Aug 2026): `dasa1/`, `collection_padagalu/` and
`raw_dump/` are `.gitignore`d from `main` and published instead to this
repo's own `dasa-sahitya-local-dist` branch — same reasoning and mechanism
as `dge/data/_wordnet/` → `wordnet-dist`, and the same repo's own
`SEARCH_ARCHITECTURE.md` rule ("a data branch of the same repository," not a
new repo, for something this size class). `.github/workflows/
publish-dasa-sahitya-local.yml` republishes it; `tools/DvaitaVedanta/Itara/DasaSahitya/
dasa_sahitya_local_dist_README.md` (mirrored onto the dist branch as its own
README) documents what's on it and how a new asset flows through, since —
unlike wordnet/kavya/search-dist — there's no live external source this can
rebuild from on each CI run: each asset is a one-off upload imported once in
a session, so the flow is import locally → commit to a branch → run the
publish workflow to move it off `main`.

This file (`ARCHITECTURE.md`) and `ALL_SOURCES_composer_registry.json` stay
on `main` regardless — small, human-authored, and worth reading without a
checkout of the dist branch, same as `dge/search_index_dist_README.md` stays
on `main` while the 330MB it describes doesn't.

## Path to one folder — done (21 Aug 2026)

1. ✅ Human sign-off given: all 12 `confirmed_duplicates` merged; all 5
   `needs_human_review` composers confirmed by the project lead to be
   **different people** from their web-side name-root candidates (Guru
   Jagannatha ≠ Jagannatha Dasaru, Prasanna Srinivasa ≠ Prasanna Venkata,
   Venugopala/Rajagopala/Gopalaryaru ≠ Gopala Dasaru/Dasa) — each became its
   own new composer file rather than being merged into anything.
2. ✅ Merge rule decided: side-by-side compositions under one composer for
   the 12 confirmed duplicates (`merge_confirmed_composers.py`, 19 Aug), with
   the existing fingerprint `dedupe()` still running to catch the rare
   actual same-pada-in-both-sources case.
3. ✅ `category`→`form` guesses confirmed by the project lead: 0 and 3 both
   fold into plain `pada` (kirtana-type songs — no separate bucket needed),
   1→`ugabhoga`, 2→`mundige`, 5→`suladi`. `mundige` and `dandaka` already
   have enum slots in `schemas.json`'s `dasa_pada_text.form` — no schema
   change was actually needed. Category 4 (singer/raga/tala/music-director/
   studio block — a modern recorded rendition, not classical text) stays
   folded into the corpus rather than a separate shelf, but every such
   record carries `tags: [..., "rendition:studio_recording"]` and
   `app_meta.is_recorded_rendition: true` so it can be filtered, relabeled,
   or removed independently later without re-deriving which records these
   were. Searched for "Narasimha Pradurbhava Dandaka" (Sripadaraja) — not
   present under that name in any of the four sources as of this pass.
4. ✅ Folded: `finalize_single_corpus.py` moved every remaining dasa1
   composer (123, all confirmed distinct — see above) into its own new file
   under `DvaitaVedanta/Itara/DasaSahitya/composers/`, and folded `raw_dump`'s unattributed
   `ugabhoga.json` (278 items) into the existing `untitled.json` bucket via
   the same dedupe (3 exact duplicates against the web crawl's own untitled
   pile collapsed). **`dasa_sahitya_local/` is retired** — every composition
   from every source now lives under `dge/data/DvaitaVedanta/Itara/DasaSahitya/composers/`.
   Final count: **15,863 compositions, 152 composer files, ~95 MB**.
5. Repeat this same review (composer-identity check, category confirmation,
   fold-in) for each future asset as it arrives — one at a time, not
   batched, so the backlog of undecided calls never grows into its own
   project. `tools/DvaitaVedanta/Itara/DasaSahitya/merge_or_relabel.py` (see its own docstring)
   is the reusable tool for folding a future confirmed-duplicate composer in,
   or moving/relabeling any composition, without hand-writing a one-off
   script each time.

This file, `ALL_SOURCES_composer_registry.json`, and
`dasa1/cross_source_duplicate_review.json` stay as the historical record of
that review — the 5-composer and category calls above are recorded there in
full, not just this summary.

## Taxonomy integration — done (25 Aug 2026)

The 152-composer corpus above was complete and correct but reachable only
through `DvaitaVedanta/Itara/DasaSahitya.html`'s own runtime fetch of `index.json` — it had no
real leaves in `taxonomy.json`/`library.json`, so it never showed up in the
Library folder browser, global search, or `tools/audit_library.py`'s
completion count, and the taxonomy-registered `DvaitaVedanta/Itara/DasaSahitya/dasakuta/`
scaffold it had actually superseded (empty `pada`/`suladi`/`ugabhoga`/...
stub folders per composer, predating this whole 4-source merge) was still
what visitors saw there instead.

Fixed by converting each `composers/<slug>.json` in place to
`composers/<slug>/data.json` (schema `dasa_pada_text`, `items` instead of
`compositions` — no duplication, same file moved not copied) and adding one
real taxonomy leaf per composer under `DvaitaVedanta/Itara/DasaSahitya.composers.<slug>`. The
empty `dasakuta` pada/keerthana stub was removed; its one genuinely
populated leaf (Jagannathadasa's Harikathamritasara, a distinct kavya, not a
pada) and the whole `vyasakuta` tree (real, separate Sanskrit-prakarana
scaffolding by Madhva-tradition ācāryas, unrelated to this corpus) were left
alone.

`tools/DvaitaVedanta/Itara/DasaSahitya/import_DvaitaVedanta/Itara/DasaSahitya.py` (fresh web imports) and
`tools/DvaitaVedanta/Itara/DasaSahitya/merge_or_relabel.py` (the reusable composer-merge/
relabel tool) both write the new `<slug>/data.json` layout now.
`finalize_single_corpus.py` and `merge_confirmed_composers.py` were
one-off scripts whose job is done (see the checklist above) and were left
as historical record, not updated to the new layout.
