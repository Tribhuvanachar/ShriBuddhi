# Working notes for Claude — ShriBuddhi

## Read this first: this repository IS the site, and you can serve it

```bash
cd shribuddhi && python3 -m http.server 8901
# then open http://localhost:8901/index.html
```

Every route works from here: `/`, `index.html`, `render.html?path=<grantha>`,
`css/`, `js/core.js`, `data/library.json`, `admin/*.html`. Verified 19 Sep 2026
by serving the repository and requesting each one.

**This note used to say the opposite**, and said it for weeks after it stopped
being true. It was written when the repo held only `js/` and `data/`; the commit
"Bring the site itself into the repository that is meant to be its source" then
moved the whole front end here, and nobody came back to the note. At least one
session read it, believed it, and built an elaborate two-repository splice --
clone bhumandala, delete its `data/` and `js/`, graft ShriBuddhi's in, serve
that -- to accomplish what `python3 -m http.server` does from this directory.

The lesson is not about this file. An orientation note that describes a layout
is a claim that expires the moment someone changes the layout, and a stale one
costs more than no note at all, because it is believed. If you change what this
repository contains, change this paragraph in the same commit.

## The three repositories, and which way work flows

```
Parabuddhi  →  ShriBuddhi  →  Jagat
 (private)      (private)      (public)
```

**BrahmaBuddhi no longer exists.** The lead deleted it on 30 Sep 2026; ShriBuddhi
publishes straight to Jagat, with nothing in between. Any workflow, doc or note
that still says "BrahmaBuddhi", "promote" or `BRAHMABUDDHI_TOKEN` is stale:
`publish-to-jagat.yml` is the only publish path, and the token for it is
**`JAGAT_TOKEN`** (renamed from `BUDDHI_TOKEN`). The pipelines that used to end in
a BrahmaBuddhi PR now open the PR, or commit, against this repository; see
`docs/HANDOFF.md` for the one repository setting that needs.

**`Jagat`'s default branch is `data`, not `main`.** `data` holds only the old search-index shards
(the Kavya corpus moved into ShriBuddhi `data/kavya_alankara/` on 30 Sep 2026);
the site tree itself is on `main`. (WordNet and sandhi used to be there too; since 30 Sep 2026
they live in ShriBuddhi `data/_wordnet/` and `data/_sandhi/` and ship with the site.) An
`actions/checkout` of `Tribhuvanachar/Jagat` with no `ref:` silently pulls `data`, not the site.
Always state `ref: main` explicitly on a Jagat checkout. `publish-to-jagat.yml` avoids this by
never checking Jagat out: it force-pushes a freshly built tree straight to `HEAD:main`, and skips
the push when Jagat `main` already has exactly that tree.

| | holds | |
|---|---|---|
| **Parabuddhi** | raw input | the PDF, page images, each OCR engine's output kept separately, `provenance/` |
| **ShriBuddhi** | the workshop | `tools/`, `data/`, `js/`, `admin/`, the workflows. **Source of truth.** |
| **Jagat** | the reading room | ShriBuddhi with provenance, `admin/`, `tools/` and the private shelves stripped, published as ONE commit with no parent by `publish-to-jagat.yml` |

**Work flows down, never up.** If you find yourself editing at one stage what
should have been decided at the stage above, the pipeline is wrong, not the
edit. Content that has flowed backwards is how `js/site-footer.js` here ended up
two names out of date while the public copy was current.

Where a given job belongs:

* **OCR a PDF** — the PDF and every engine's raw output go to Parabuddhi, each
  engine kept apart and never overwritten. Merge, vote and review happen here,
  into `data/ocr_staging/<work>/` and then `data/<shelf>/.../data.json`.
  Keep the raw output. "What did Vision actually see on page 431" is answerable
  only while it still exists.
* **Pratīka tagging, sandhi splitting, paragraph formatting, layer splitting** —
  here. They need `tools/`, they need judgement, and they must be re-runnable.
* **Manual edits** — here. Jagat is downstream; an edit made there is an edit
  the next publish will overwrite. On a desktop, `python tools/sync_local.py`
  shows what would be pushed and `--go` pushes it.
* **Making folders appear on Jagat** — `admin/library.html` → 🌐 Go-live shelf.
  Tick the folders, then 🚀 Publish shelf to GitHub: that commits
  `config/library-overrides.json` to ShriBuddhi `main` and nothing more. **Nothing
  publishes automatically.** To send ShriBuddhi to Jagat, run Actions → "Publish —
  ShriBuddhi to Jagat" by hand and tick *push* (unticked is a dry run). A publish sends
  all of `main`, and the site is live the moment Jagat `main` changes.
* **Admin never reaches Jagat.** The publish strips every admin entry point from the
  staged copy (`tools/publish_strip_admin.py`) and refuses to build if one is left. Admin
  work happens only in ShriBuddhi.

## Raw data lands in ParaBuddhi first

Every import, OCR run, ingest and weekly sync puts its raw result in ParaBuddhi, unchanged, before
anything is built from it (the lead, 1 Oct 2026). ShriBuddhi is where origin tags are stripped and the
material is rearranged and stitched (SarvaMula combines SetuTila with tīkā/ṭippaṇī from dvaitavedanta.in
and anandamakaranda.in), so no ShriBuddhi folder equals any one upstream site. Which upstream section
goes to which ShriBuddhi path, and which origin label became which of ours, is recorded in
ParaBuddhi's `import_config/destinations.registry.json` (`docs/SOURCE_DESTINATIONS.md`). The weekly
watchers (`watch-sources.yml`, `watch-indowordnet.yml`, Sunday 02:00 IST) land and e-mail; they never
touch `data/` here. A new importer that writes straight into `data/` is the pipeline being wrong.

## Working across repositories

You are not limited to the repository you started in. Attach another with
`add_repo` — it takes effect in the running session, with no restart:

    add_repo(owner="Tribhuvanachar", repo="ParaBuddhi", access="read")

**Do this rather than asking the lead to switch repositories for you.** Being
handed a task and stopping to ask a human to change your working directory is
the thing this note exists to prevent.

`add_repo` can still fail on authorization — the repo may not be in the
session's allowed set. That is a grant a person makes once, not a per-task
interruption. Say plainly that you hit it and which repo; do not work around it.

## Before you tell the lead you cannot do something

`docs/MISTAKES.md` is the full record of what has gone wrong here and the rule
each failure produced. Read it before a batch operation, before reporting a
capability as unavailable, and before editing corpus files. The headlines:

This section exists because I cost the lead a week of running workflows by
hand, having told him I was not allowed to dispatch them. I was wrong. Read
this before reporting ANY capability as unavailable.

**You CAN dispatch workflows.** Use `tools/dispatch_workflow.py <file.yml>
--repo Tribhuvanachar/<Repo> -f key=value`. A raw curl needs
`Content-Type: application/json`; without it GitHub answers **415** with a
message naming the header. That is a malformed request, NOT a permission
denial. A 422 naming a missing input is GitHub accepting the call and
validating it — also not a denial.

The general rule: **read the error text before classifying it.** "Not
permitted", "415", "403" and "422" mean four different things. Reproduce a
failure with the fault corrected before you conclude it is a wall. If it
really is a wall, say exactly which call failed and how, so the lead can
judge it too.

**You do not need OCR keys in your session.** `SARVAM_API_KEY` and the Vision
credentials are Actions secrets, injected into workflow runs. That is why OCR
runs as a workflow. Their absence from `env` is the design, not a blocker.

**Check what you already know before asserting a negative.** I reported that
a repository had zero Actions secrets configured, when a workflow log I had
read minutes earlier showed `SARVAM_API_KEY: ***`. Listing secrets through
the proxy can fail or return empty; a run log proving one exists outranks it.

## Limits to read before a batch

* `tools/sarvam_docai.py` caps at **200 pages** per run unless `--max-pages`
  is raised deliberately. I dispatched 41 jobs with `pages=1-2000`; 40 failed.
* Sarvam **bills per page**. Always `mode=dry-run` first, quote the page
  total to the lead, and wait. 41 volumes measured 22,746 pages.
* Before running anything that calls the Gemini API, give a cost estimate
  and wait for the go-ahead.

## Anandamakaranda is closed

Nothing new goes into `data/darshana/vedanta/dvaita/Anandamakaranda/`
(27 Sep 2026, the lead). Only selected pieces of it will ever be pushed on
to Jagat, and the lead picks those; a new layer landed there is a layer
nobody asked for in a tree nobody is publishing from.

New Dvaita material goes to `DvaitaVedantaIn/` instead, and what is
already in Anandamakaranda and duplicated there — the Ṛgbhāṣya, the Gītā
prasthāna — belongs in `DvaitaVedantaIn/` too.
`tests/test_anandamakaranda_closed.py` holds the count so a new file
cannot arrive unnoticed.

## What reaches a reader is not an importer's decision

The go-live shelf (`admin/config/library-overrides.json`) and
`DGE_COPYRIGHT_GATED_COMMENTARY_KEYS` (`js/core.js`) are where publishing
decisions are recorded, and they are the lead's to make. Land the text,
make it live in ShriBuddhi, say what it is and what is questionable about
it — and leave the choice of what goes to Jagat, and what a reader sees,
to the lead. An import that gates its own material, however defensibly, has
made that call for them.

## Editing data files

Never `json.load` then `json.dump` a `data/*.json`. Use raw string
replacement, or `tools/format_data_json.canonical()`. Reformatting reflows
one-unit-per-line files: two separate attempts here produced a 26,611-line
diff and a 3.7-million-insertion diff, both burying the real change. Verify
line counts are unchanged before committing.

When a `--fix` writes a derived field, MERGE with what is there. `derive_source`
replaced instead, deleting `source_url` from 214 entries and `licence` from
197, CC-BY 4.0 among them, and reported it as "234 sources synced".

## Never publish provenance

No `source_url`, no `source` dict, no `source_html`, no origin `breadcrumb`, no
id derived from an origin's numbering. Credits belong in the site footer, given
once and on the whole, not per record. The provenance maps live in Parabuddhi
and only there.

`tools/publish_clean_repo.py --scan` is the gate. It exits non-zero and refuses
to build while anything names the private side or the old repository. Do not
work around it; fix what it names.

## Time and dates

Report every time in IST (Asia/Kolkata, UTC+05:30) — `10:30 am IST`, never a
`Z`. Cron in GitHub Actions is evaluated in UTC, so subtract 5:30 and shift the
day fields when that crosses midnight.

## Tests

`./run_tests.sh` — pytest over `tests/`, 979 of them. Two browser suites sit
beside it and are NOT part of it: `tools/e2e/opaque_ids_e2e.py` (19 checks) and
`tools/e2e/admin_token_e2e.py` (8), which need two local servers and Chromium.
See `tools/e2e/README.md`. It does not run
`firebase/tests/` (22 Node files, needing node and the Firebase emulators).

## Costs

Before running anything that calls the Gemini API, give the lead a cost
estimate and wait for their go-ahead.

## Secrets

You never see GitHub secrets; they are injected into workflow runs, not into
your session. Never ask for a token to be pasted into chat.

The full inventory — which secret, what it's for, which repo holds it, where
to re-issue the value — is `docs/RESOURCES.md` §1/§3, not here. As of 1 Oct
2026 it also covers two separate archive.org accounts/key pairs the lead set
up (`ARCHIVE_PDF_*` and `ARCHIVE_AUDIO_*`, ShriBuddhi) — one per upload
purpose, not aliases for the same credential.
