# DvaitaVedanta extraction

Pulls the [dvaitavedanta.in](https://dvaitavedanta.in/) corpus into
`dge/data/dvaitavedanta/`.

**Licensing.** The site publishes no licence. Per the convention in
`dge/PROJECT_STATUS.md` — *"absence of a licence is not permission"* — the
project lead authorised this specific source for this specific non-commercial,
educational use on 2026-08-15. That decision is recorded in `dv_sources.json`
and written into `source_note` on every emitted `data.json`, and every item
keeps its own `source.url`.

---

## Quick start

```bash
pip install -r tools/dvaitavedanta/requirements.txt

# offline self-tests — no network needed
python tools/dvaitavedanta/test_dv_parse.py
python tools/dvaitavedanta/test_import_offline.py

# smoke test: 5 leaves from one grantha, writes nothing
python tools/dvaitavedanta/import_dvaitavedanta.py \
  --granthas pramana_lakshana --limit-per-grantha 5 --dry-run

# real run for one section
python tools/dvaitavedanta/import_dvaitavedanta.py \
  --sections dasha_prakarana_granthas --write
```

Normally you don't run this locally — use the **Extract DvaitaVedanta**
workflow (`.github/workflows/extract-dvaitavedanta.yml`). The Cowork sandbox has
no network egress to this host, same as every other external source this project
uses, so fetching happens on the Actions runner.

---

## The lazy "Load More" layer (1 Sep 2026 — the harvest gap)

A category-details page's initial HTML contains only ONE `#article<id>`
block (`first_sutra_id`). Every further unit named in the RIGHT-hand nav
(`.explanation-text` entries, `total_sutra_count` in all) is served only by

    GET /load-data?book_id=<category_book_id>&id=<unit_id>&search=
    → {"html": "<div id=article<unit>>…", "tag": …, "sutraId": <unit>}

The original import never followed this endpoint, so every page contributed
exactly its first unit — verified live against
`category-details/977/975/...` (Nyāyasudhā maṅgalamācaraṇam): 9 units on the
site, 1 (`DV_978`) in `dge/data`, units 979–986 absent repo-wide (the
reported missing गुरुराजेन passages among them). The importer now exhausts
`/load-data` per page (see `extract_lazy_units` / `parse_load_fragment` in
`dv_parse.py` and the leaf loop); a re-run with the cache warm re-fetches
only the fragments. Fragment responses are ~1–2 s each even when full pages
take 40 s+.

## What the source site looks like

| | |
|---|---|
| Stack | Laravel, fully server-rendered. No API, no JS needed. |
| robots.txt / sitemap.xml | Both 404. Discovery is link-driven. |
| URL | `/category-details/{contentId}/{ancestorId}/{slug}…` |
| Load-bearing | `contentId` **only**. The ancestor id isn't validated; slugs are cosmetic. The route needs ≥3 params, so 2-segment URLs 404. |
| Container nodes | HTTP **200** + body `No record found!!` → skipped, counted. |
| Nonexistent ids | HTTP **500**, not 404. |
| TOC | None. Every leaf renders the grantha's whole sidebar as real `<a href>`s. |
| Scale | id space ~1–19,694; roughly 14k–17k leaf pages over ~40 granthas. |

**Crawl strategy.** Fetch the seed leaf → harvest every `contentId` from its
sidebar → fetch each one. Id brute-force would work but wastes requests and
generates 500s on every gap.

**The backend is the bottleneck, not bot defence.** No Cloudflare, no captcha, no
429s were seen. But the full sidebar re-renders on every leaf, so large granthas
are slow — `nyaya_sudha` timed out 3/3 during recon. Default timeout is 120s.

---

## Output layout

```
dge/data/dvaitavedanta/
  _extract_status.json                  ← progress tracker
  <section>/
    _meta.json
    <grantha>/
      _meta.json
      mula/data.json                    ← schema grantha_mula_text
      tika_jayatirtha/data.json         ← schema grantha_tika_text
      tika_sattarkadipavali/data.json
      …one folder per commentary layer
```

This is a **staging tree**: it mirrors the site 1:1 and touches nothing under
`dge/data/sarvamoola_grantha/`. That matters because the site routinely carries
3–5 named commentaries per leaf (ब्रह्मसूत्रभाष्यम् 1.1.1 has five) while the
sarvamoola convention has exactly three layer folders — mapping straight in would
flatten distinct commentaries into one `tippani` bucket *and* collide with the
47 leaves already populated from anandamakaranda.in. Promotion into
`sarvamoola_grantha/` is a separate, reviewable pass.

Each `data.json` follows the repo shape (`importers/common.write_grantha`):

```json
{
 "schema": "grantha_mula_text",
 "default_author": "श्रीमदानन्दतीर्थभगवत्पादाचार्यः",
 "source_url": "https://dvaitavedanta.in/category-details/13528/937/…",
 "source_note": "No published licence. Used with case-by-case permission…",
 "items": [
  {
   "id": "DV_13528",
   "reference": "दशप्रकरणानि > 1. प्रमाणलक्षणम् > मङ्गलाचरणम्",
   "section": "प्रमाणलक्षणम्",
   "unit_title": "मङ्गलाचरणम्",
   "sanskrit_text": "अशेषगुरुमीशेशं नारायणमनामयम् ।\n…",
   "breadcrumb": ["दशप्रकरणानि", "1. प्रमाणलक्षणम्", "मङ्गलाचरणम्"],
   "source": {"site": "dvaitavedanta.in", "url": "…", "content_id": 13528,
              "layer": "मूलम्", "anchor": "article13528", "fetched": "2026-08-15"}
  }
 ]
}
```

`ensure_ascii=False`, `indent=1`, Devanagari (never IAST) — matching the rest of
`dge/data`.

**Cross-layer linking.** The item id is `DV_<contentId>` in *every* layer, so a
tika item's id matches its mula item's id, which is what `grantha_tika_text`
asks for. `verify_extract.py` checks this.

**Verifying against the live source.** `verify_extract.py` only checks the
shape of what's already on disk -- it never touches the network, so it can't
tell you whether the site itself has since changed. `verify_source_content.py`
does: it re-fetches every item's own `source.url`, re-parses the live HTML
with the same `dv_parse.parse_page` that produced the stored data, and checks
that `sanskrit_text` is still genuinely there (verbatim, or a close match if
the page has been reorganised since the original scrape). One page backs many
items (a mula plus every commentary layer quoted on it), so it fetches each
unique URL once, using the same `.dv_cache` the importer uses, and is
resumable/spot-checkable the same way:

```bash
# Spot-check a random sample, reproducibly
python tools/dvaitavedanta/verify_source_content.py \
    --data dge/data/darshana/vedanta/dvaita/DvaitaVedantaIn/dasha_prakarana_granthas \
    --sample 25 --seed 1 --out /tmp/report.json

# Full sweep, CI-friendly (non-zero exit if anything drifted/vanished)
python tools/dvaitavedanta/verify_source_content.py --strict
```

The site occasionally answers a real request with a "One moment, please…"
bot-challenge page instead of content (HTTP 200, so a naive fetch would cache
it as if it were real and misreport genuinely-present content as removed);
the tool detects and retries through this rather than trusting it, and reports
it as its own `BLOCKED` verdict (rate-limiting, not a real finding) rather
than folding it into `MISSING`/`PAGE_EMPTY`.

---

## Files

| File | Role |
|---|---|
| `dv_sources.json` | 40 granthas: seed URL, slug, section. Also the Devanagari→folder map for commentary layers, and the licence record. |
| `dv_parse.py` | HTML parsing. Pure, no network — unit-testable. |
| `import_dvaitavedanta.py` | Crawler, emitter, status tracker. |
| `verify_extract.py` | Integrity checks on emitted JSON (no network -- shape only). |
| `verify_source_content.py` | Re-fetches each item's own `source.url` and checks the stored `sanskrit_text` is still genuinely on the live page (uses network, resumable via the same HTTP cache). |
| `sync_catalog.py` | Registers the tree in `taxonomy.json` + `library.json`. |
| `merge_status.py` | Folds per-shard status files into one after a matrix run. |
| `test_dv_parse.py` | Fixture tests for the parser. |
| `test_import_offline.py` | End-to-end test with a primed cache, zero network. |

---

## Parser design

Layers are found by `id="article<N>"` first — that's what the site emits. If the
markup shifts, it falls back to splitting the densest non-chrome container on its
headings, picked by *Devanagari characters minus anchor-text Devanagari* (the
sidebar is dense too, but almost all of its text sits inside `<a>`).

`<script>` and `<style>` elements are decomposed, not regex-stripped —
`importers/common.py` records the bug where leftover CSS text got transliterated
character-by-character into narada_smriti's first "verse".

Every emitted item is gated on a Devanagari ratio ≥ 0.55. Anything below is
reported in the run summary and by `verify_extract.py` rather than landing quietly.

If the selectors do drift, run the workflow with **probe = true**: it uploads the
raw HTML of a few pages as an artifact so the selectors can be re-anchored
against reality.

---

## Slugs

Folder names come from the *discovered Devanagari title*, transliterated. The
site's own slugs can't be used: they drop matras and truncate to four characters,
so माण्डूक्य and मुण्डक both render as `mana`. `dv_sources.json` pins the slug
where we're confident and leaves it `null` otherwise; the run prints what it
resolved.

`indic-transliteration` is used when present, with a correct built-in fallback
(a naive per-character map produces `paramaanalakashanama` — the inherent vowel
must be suppressed before a matra or virama).

---

## Resuming

The HTTP cache (`--cache`, default `.dv_cache`) is keyed by SHA1 of the URL, and
the workflow restores it via `actions/cache`. A re-run therefore resumes instead
of re-crawling, and a failed matrix shard never costs the other shards their
work. `--refresh-cache` forces a full refetch.

`_extract_status.json` is cumulative: a grantha's `first_run` is preserved across
runs, and `merge_status.py` keeps the newest record per grantha.

---

## Progress tracking

Three views of the same data:

1. `dge/data/dvaitavedanta/_extract_status.json` — committed, machine-readable.
   Per grantha: discovered / fetched / with_text / containers / failed / items /
   bytes / per-layer counts / timings / status.
2. The **GitHub step summary** on every run — table, unmapped layers, failures.
3. `dge/dvaitavedanta-status.html` — dashboard with per-section and per-grantha
   progress, filters, unmapped layers and the failure list.

**Unmapped layers** are the thing to watch. A commentary heading with no entry in
`dv_sources.json → layers` gets an auto-slugged folder and defaults to
`grantha_tika_text` with no author. That's a safe default, not a correct one —
add the mapping and re-run.

---

## Deliberately not done here

`dge/build_search_index.py` is **not** run by this workflow. The index is a
regenerable build product, `dge/search_index` is already 162 MB, and the repo is
near GitHub's practical 1 GB ceiling. Run `reindex.yml` once the corpus has
landed and been reviewed.
