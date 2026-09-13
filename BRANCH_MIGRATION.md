# Branches brought over from Tribhuvanachar/bhumandala (Buddhi) — 13 Sep 2026

The file moves (tools, importers, workflows → here; admin pages → BrahmaBuddhi; docs,
tasks, archive, provenance sources → ParaBuddhi) had been done by the migration sessions,
but the old repository's **branches** had not moved anywhere, and it is about to be
deleted. Every branch that carried unique content now lives here. Each snapshot branch
carries a `_MIGRATION.md` saying what it is and where it came from.

## Runtime data branches — copied exactly (same commits)

| Branch | What | Served how |
|---|---|---|
| `search-dist` | the built corpus search index (~330 MB) | jsDelivr, pinned in `js/config.js` `searchIndexBase` and `js/global-search.js` |
| `kavya-dist` | the built Kāvya corpus (43 works) | jsDelivr, `kavyaDataBase` |
| `wordnet-dist` | the Sanskrit WordNet | jsDelivr, `wordnetDataBase` and `js/intellisense.js` |
| `sandhi-dist` | the sandhi-vicheda index | jsDelivr |
| `dasa-sahitya-local-dist` | Dāsa Sāhitya built from local app exports | nothing reads it yet |
| `dv-cache-dist` | raw dvaitavedanta.in crawl (tarball) | was already here |

**jsDelivr can only serve a public repository.** Every pin today reads
`cdn.jsdelivr.net/gh/Tribhuvanachar/bhumandala@<sha>`. When the old repository is deleted
those URLs die (jsDelivr's cache may linger for a while). The four dist branches must be
pushed to the new public Buddhi and the pins rewritten to `Tribhuvanachar/Buddhi@<sha>`;
`reindex.yml` and `publish-wordnet.yml` / `import-kavya.yml` push to `${{ github.repository }}`,
so they must run in (or target) the public repo for the CDN to see them.

## OCR staging — snapshots in the flattened layout

`ocr-staging/<work>` × 10 (isha, kena, katha, mundaka, mandukya, prashna, taittiriya
Upaniṣad bhāṣya-ṭippaṇīs, tantrasara_sangraha a/b, raghavendra_vijaya): the paid Vision
page OCR, at `data/ocr_staging/<work>/`. `admin/ocr-review.html` and `ocr-sarvam.yml`
expect this branch name and path.

## Unmerged work — `buddhi-archive/*`, unique files plus `git format-patch` output

| Branch | Origin | Note |
|---|---|---|
| `buddhi-archive/puranas-loading` | `claude/puranas-loading-qa0ymy`, PR #137 open | needs a side-by-side decision vs main's later Purāṇa import |
| `buddhi-archive/puranas-bhagavata-duplicates` | 4 commits | Purāṇa/Bhāgavata duplicate fixes |
| `buddhi-archive/rv-pratishakhya-krama-spec` | 25 commits | Ṛgveda Prātiśākhya krama spec + data |
| `buddhi-archive/session-start` | 13 commits | Madhva acquisition architecture, dasa/vedanga data |
| `buddhi-archive/whatsapp-integration` | 7 commits | Firebase Functions deploy/secrets, WhatsApp setup docs |
| `buddhi-archive/library-view-sync` | 1 commit | `js/corpus-fetch.js` |
| `buddhi-archive/gemini-enrich-32395365588` | PR #98 open | recommended close on 9 Sep |
| `buddhi-archive/gemini-enrich-32394277438` | 1 run | recommended delete on 9 Sep |
| `genie-asr-audio-seed` | 3 commits | 62 Genie ASR benchmark recordings; the recorder page pushes here |
| `buddhi-archive/unplaced-files` | — | HANDOFF.md, the Dāsa Sāhitya `_dump/` the capture page reads, folder `_meta.json`s, favicons/icons — files that reached none of the new repos |

Not migrated: `recover/dv-structure` (1,658 cached pages — the same cache `dv-cache-dist`
already holds), `nightly/library-sync` (a generated rolling PR; the next nightly run
recreates it), and `main` itself (its content is what the four repos now hold).

## Still pointing at the old name

`Tribhuvanachar/bhumandala` is hardcoded in: the jsDelivr pins above; `OWNER`/`REPO` in
BrahmaBuddhi's `admin/repo-map.html` and `admin/ocr-review.html`; `admin/config/repo-map.json`
(the branch inventory describes the old repo); the Sunday routine's prompt; `docs/*` in
ParaBuddhi. ParaBuddhi's `docs/MIGRATION_LOG.md` lists the rest.
