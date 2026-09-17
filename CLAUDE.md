# Working notes for Claude — ShriBuddhi

## Read this first: this repository cannot run as a website

There is no `index.html` here. No `css/`, no `vyakarana/`, no `guru-parampara/`,
no `config/`, no `content/`, no `wasm/`. This repo holds `js/` and `data/` — the
engine and the fuel — and nothing that loads them.

So: **you cannot browser-test a front-end change from this repository.** Serving
it 404s at the front door. If you have changed `js/` and want to see it work,
you need the site tree as well (see *Working across repositories* below). A
session that assumes otherwise will report a feature as done when no reader can
reach it. That has already happened once.

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
