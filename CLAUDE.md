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

## The four repositories, and which way work flows

```
Parabuddhi  →  ShriBuddhi  →  BrahmaBuddhi  →  Jagat
 (private)      (private)      (private)       (public)
```

| | holds | |
|---|---|---|
| **Parabuddhi** | raw input | the PDF, page images, each OCR engine's output kept separately, `provenance/` |
| **ShriBuddhi** | the workshop | `tools/`, `data/`, `js/`, `admin/`, all 57 workflows. **Source of truth.** |
| **BrahmaBuddhi** | release candidate | content with provenance stripped, plus the private admin overlay |
| **Jagat** | the reading room | BrahmaBuddhi minus that overlay, published as ONE commit with no parent |

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
* **Manual edits** — here. BrahmaBuddhi is downstream; an edit made there is an
  edit a promote will overwrite.

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

`./run_tests.sh` — pytest over `tests/`, 867 of them. It does not run
`firebase/tests/` (22 Node files, needing node and the Firebase emulators).

## Costs

Before running anything that calls the Gemini API, give the lead a cost
estimate and wait for their go-ahead.

## Secrets

You never see GitHub secrets; they are injected into workflow runs, not into
your session. Never ask for a token to be pasted into chat.
