# HANDOFF — for the next Claude Code session (written 13 Sep 2026)

Session `claude/workflow-library-consolidation-6hludj` on the old repository
(Tribhuvanachar/bhumandala, renamed Buddhi, about to be deleted) ends here.
Everything it did is either on the old repo's main (merged 9 Sep) and carried
into the new repos by the migration sessions, or pushed here on 13 Sep as
branches. Read this, then `BRANCH_MIGRATION.md`, then ParaBuddhi's
`docs/MIGRATION_LOG.md` (the restructuring record) and `docs/REPO_INVENTORY.md`.

## Paste-ready opening prompt

> Read HANDOFF.md and BRANCH_MIGRATION.md at the root of Tribhuvanachar/ShriBuddhi,
> then ParaBuddhi docs/MIGRATION_LOG.md. Continue the pending items below in order.
> Standing rules: report times in IST; Gemini API calls need a ₹ estimate and my
> go-ahead; never fabricate content; Playwright screenshots before merging UI
> changes; commits end with the Claude Code attribution trailer; never put a model
> identifier in pushed files. Ask me only for decisions that are mine (money,
> deleting data, publishing, DNS).

## Where the work lives now

| What | Repo | Where |
|---|---|---|
| Tools, importers, all 54 workflows (targets rewritten to BrahmaBuddhi) | ShriBuddhi | `tools/`, `importers/`, `.github/workflows/` |
| Admin pages incl. Repository & Workflows (`repo-map.html`), OCR Review (`ocr-review.html`) | BrahmaBuddhi | `admin/` |
| Docs (REPO_INVENTORY, NAMING_CONVENTIONS, OCR_REVIEW, SOURCE_SYNC, …), tasks (Ask Claude inbox), retired-importers zip, provenance sources | ParaBuddhi | `docs/`, `bhumandala_tasks/`, `buddhi_archive_2026-09-12/`, `source/` |
| Public content only | Buddhi (old, to be replaced) | `data/`, `js/`, `pages/`, `content/` |
| Data branches (search/kavya/wordnet/sandhi/dasa-local dist), 10 OCR staging branches, 8 archive branches of unmerged work, ASR audio seed, unplaced files | ShriBuddhi | see `BRANCH_MIGRATION.md` |

## Pending, in order

1. **jsDelivr pins.** The reader loads search, Kāvya, WordNet and sandhi data from
   `cdn.jsdelivr.net/gh/Tribhuvanachar/bhumandala@<sha>`. jsDelivr serves public repos
   only. When the new public Buddhi exists: push `search-dist`, `kavya-dist`,
   `wordnet-dist`, `sandhi-dist` from here to it, then rewrite the pins in
   `js/config.js` (searchIndexBase, kavyaDataBase, wordnetDataBase), `js/global-search.js`
   (CDN_INDEX) and `js/intellisense.js`. `reindex.yml` / `publish-wordnet.yml` /
   `import-kavya.yml` must publish to the public repo for the CDN to see new builds.
2. **Old-name references.** `OWNER`/`REPO` in BrahmaBuddhi `admin/repo-map.html` and
   `admin/ocr-review.html`; `admin/config/repo-map.json` (its branch section describes the
   old repo — regenerate with `tools/build_repo_inventory.py` against this repo);
   `admin/config/sources.registry.json` importer names are fine.
3. **Sunday routine** (Claude Routine "Sunday instruction intake") still says
   Tribhuvanachar/bhumandala and reads `tasks/WEEKLY_INSTRUCTIONS.md`, which now lives in
   ParaBuddhi `bhumandala_tasks/`. Retarget once the lead says which repo it should read
   and where it should develop (probably ShriBuddhi).
4. **Ask Claude live replies** (`ask-claude.yml`, here) need a repository secret
   `CLAUDE_CODE_OAUTH_TOKEN` (from `claude setup-token` on a computer signed in to the
   lead's Max subscription) — in whichever repo the inbox lives. The website tab writes
   `tasks/inbox/<id>.json`; check the path the moved workflow expects.
5. **Progress streaming in Ask Claude** (asked 9 Sep, not built): run Claude Code in the
   workflow with `--output-format stream-json` and write progress lines into the inbox
   file every few seconds so the page shows what is happening. A self-hosted runner
   removes the 2-minute GitHub cold start.
6. **Sarvam Document AI**: `tools/sarvam_docai.py` + `ocr-sarvam.yml` need a
   `SARVAM_API_KEY` secret; dry-run without it. Pricing not published — record pages sent.
7. **Names backlog** (`docs/NAMING_CONVENTIONS.md` §9 in ParaBuddhi): grow
   `data/author_aliases.json`, then `audit_library.py --fix` writing author_id/kind/parent,
   then the catalogue page.
8. **Decisions still open from 9 Sep**: 7 workflows proposed for deletion, 2 to decide;
   PR #137 (Purāṇas) and PR #98 (Gemini enrich) — content preserved in
   `buddhi-archive/*` here; the PR threads die with the old repo.

## Standing rules that travel

CLAUDE.md of the old repo: IST times; Gemini cost rule (estimate first, record usage,
never re-run a paid stage whose output is committed); no model identifiers in pushed
files; never delete or overwrite data silently; every claim about audio/text comes from a
measurement or the lead's own words. The old `HANDOFF.md` (7 Sep, §3 rules in full) is on
branch `buddhi-archive/unplaced-files` here.
