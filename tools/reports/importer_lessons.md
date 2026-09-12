# Importer lessons — the playbook for bringing a new source site in

*Distilled from the dvaitavedanta.in pipeline, the anandamakaranda /
SarvaMula work, sringeri + srivaishnavan + vishvasa imports, and the
setutila.in importer (Sep 2026). Read this BEFORE writing the next
importer; add to it after every import.*

## 1 · Find the real corpus before writing a line of code

- **The rendered page is bait; the lazy-loaded payload is the corpus.**
  dvaitavedanta.in lost us a whole harvest round because articles loaded
  their bodies after first paint (task #63). setutila.in embeds only
  chunk 0 and lazy-fetches the rest (`window.__BOOK_CHUNKS__` manifest →
  `texts/<work>/chapter-NNN.chunk.html`). Always open one page in a real
  browser or read its inline JS for fetch()/manifest patterns first.
- **Prefer a machine API over scraping HTML shells.** WordPress sites
  (setutila.in) expose `wp-json/wp/v2/posts` with `modified_gmt`,
  categories, and full rendered content — enumeration, delta detection
  and metadata come free. Check `/wp-json/`, `/feed/`, `sitemap.xml`,
  archive.org metadata endpoints before scraping nav pages.
- **Probe scale before the full run** (chunk counts, one file's bytes) so
  repo-bloat surprises are caught before 200 MB lands in git.

## 2 · Preserve, don't just extract

- **Keep the raw HTML** (`_raw/<slug>/…`, verbatim): bold/italics,
  heading levels, CSS class vocabulary, colophons — cheap to store, and
  every later re-parse or restructure otherwise means a re-crawl (the DV
  `source_html` retrofit, task #75, was exactly this lesson).
- **Keep the source's own identifiers.** setutila's block UUIDs are the
  site's own permalink anchors — they survive into our items as
  `source.block_uuid`, so units can be re-keyed, deep-linked back, and
  diffed against future crawls. DV's article ids play the same role in
  `_sources/dv_map.json` for grantha_v2.
- **Keep the source's apparatus.** setutila ships pathantara JSON (its
  own variant readings vs TRK / BG pathas). That is cross-edition
  alignment data — imported into `references[]`, never flattened away.

## 3 · One reader schema, additive extras

- Emit the corpus in an EXISTING schema (`grantha_tika_text` items with
  `sanskrit_text` + `source_html` + `breadcrumb` + `source`) so the
  reader, validators, audit and search need zero changes on day one.
- New information rides in additive fields (`tags` = source block class,
  `references[].kind = "pathantara"`, top-level `attribution`), never in
  a new schema unless the structure truly demands one (grantha_v2 did).
- **Attribution object is mandatory** on every imported file:
  `{source_name, source_url, accessed_date, license_notes}` — the same
  shape everywhere, rendered by the reader's info drawer.

## 4 · Sync is a design requirement, not a follow-up

- A `_sync_state.json` beside the corpus: per-post `modified_gmt` (or
  the site's equivalent) + per-chunk content hash. Re-runs skip
  unchanged posts; the state file diff IS the change report.
- A `workflow_dispatch` GitHub Actions workflow per source (pattern:
  `extract-dvaitavedanta.yml`) so a re-sync is one button, run from
  `main`, never from a working tree.
- Name tools after the SOURCE (`tools/setutila/`), not the destination
  folder — destinations move (the Dvaita folder restructure), sources
  don't.

## 5 · Structure mapping

- Map source categories onto OUR taxonomy names where the same shelf
  exists (`दशप्रकरणानि` → `dasha_prakarana_granthas`, matching the
  DvaitaVedanta tree) so a future merge is a move, not a rename.
- ASCII work folders: source slug when it is ASCII, deterministic
  transliteration of the title otherwise — never percent-encoded
  Devanagari in paths.
- Register new works in library.json **hidden/admin-only first** (the
  DvaitaVedanta convention): the lead reviews on the live site before
  the shelf goes public.

## 6 · Verification bar (per import, before merge)

1. Pilot ONE work; hand-check counts against something known
   (setutila BS bhashya: exactly 564 Mula blocks = the scholar-ratified
   sutra count — that match is the smoke test).
2. Full run; `tools/validate_data.py` + full pytest.
3. Playwright: open one imported work in the real reader, screenshot.
4. Summary numbers in the commit message: works, items, errors, bytes.

## 7 · Conduct

- Read robots.txt; identify the importer in the User-Agent; sleep
  between requests (0.3–0.5 s); never parallel-hammer a small site.
- Licence honesty: record what the site says (or doesn't) in
  `license_notes`; non-commercial + attribution + preserved provenance
  is this project's floor, and anything doubtful goes admin-only until
  the lead clears it.
