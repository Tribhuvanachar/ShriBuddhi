# The OCR runbook

One procedure for every paid OCR batch. Read it once; after that `tools/ocr_batch.py`
enforces it, because a procedure that depends on someone remembering to follow it is
not a procedure.

**Where the keys are:** `docs/CREDENTIALS.md`. Short version — there are
none in the container by design; every paid engine runs in a GitHub Actions
workflow with the key as a repository secret, dispatched over the REST API.


**Why this file is not the safeguard.** On 13 Sep 2026 a commit step lost OCR that had
already been paid for. Someone wrote the cause into a comment above that very step. On
18 Sep 2026 I read that comment and dispatched 130 jobs anyway; the same class of
failure discarded 3,474 billed pages. Prose you are supposed to remember to consult is
not a control. The control is `ocr_batch.py`, which will not dispatch until the checks
below pass.

## The one rule

> **Nothing may be billed until the path from API call to committed file has been
> proven end to end on one small volume, in this session, today.**

Not "it worked last week". Not "the dry run passed" — a dry run does not call the paid
API and does not commit. One real, small, complete run. Then the batch.

## Phases

### 1 · Inventory (free)

Every source resolves to a URL that downloads a readable PDF, with a page count taken
from the file itself. `mode=dry-run` reports the count and spends nothing.

**The source of a batch is `admin/config/ocr_sources.json`, not the session's memory.**
Build the plan with `tools/ocr_plan_from_sources.py --engine <engine>`; do not type page
ranges by hand. On 18 Sep 2026 a batch of 11 works could not be dispatched at all,
because no repo recorded which PDF any of them had been OCRed from — not the staging
JSON, not `data/ocr_staging/index.json`, not the branch commits, not ParaBuddhi. The
URLs had to be re-derived from the scanned title pages.

A source is not confirmed until its **page count matches what is already staged**. Title
matching is not enough: the obvious archive.org hit for Bhāgavata Sāroddhāra is a
different edition of the same work, 560 pages against the staged 459. Running Sarvam on
it would have produced a file that disagreed with Vision on every page, and the conflict
router would have sent the whole book to Gemini as if the OCR were bad. Re-OCRing a work
means re-billing it, so record the source at staging time, and never stage without a row
in `ocr_sources.json`.

Slugs must be unique across the batch, derived from the **distinguishing** part of an
identifier. Three Aitareya Upaniṣad items share a 44-character prefix; truncation gave
all three the same staging branch.

### 2 · Preflight (free, and blocking)

`ocr_batch.py --preflight` refuses to continue unless:

* every slug in the batch is unique
* every chunk is within the engine's page cap (200 for Sarvam)
* the concurrency key includes the page range — without it GitHub cancels every
  pending chunk of a book but one, silently, and the batch looks dispatched
* the commit step retries a rejected push — without it two chunks finishing together
  lose the second one's paid work
* a pilot receipt for today exists (phase 3)

**Both costs are stated before dispatch, never one of them.** A batch has a price in the
paid API and a price in the compute that calls it. GitHub Actions is free and unlimited
on public repositories and capped at 2,000 minutes a month on private ones; at about six
billable minutes per run, 330 runs exhausts a month and stops every workflow in the
account. In September 230 runs took ~1,370 of those minutes and the lead learned of it
from an error that reads like a failed payment.

### 3 · Pilot (costs one small volume)

One real run, smallest volume, `mode=real-run`. It passes only when the staged file is
on its branch AND `usage.pages_succeeded` equals the pages requested AND no page is
empty. Success is what landed, never the workflow's conclusion.

Write the receipt: `ocr_batch.py --record-pilot <slug>`.

### 4 · Batch

Dispatch. Record every run id against its work slug and page range as you go — a run id
you did not write down is a page you cannot account for.

### 5 · Reconcile (free, and mandatory)

`ocr_batch.py --reconcile` diffs **pages staged against pages requested**. Never count
successful runs: 55 of 130 runs succeeding was 47% of the pages, and only the page diff
said so.

It classifies every missing page as one of:

* **never attempted** — cancelled while queued; costs nothing; re-dispatch freely
* **billed and lost** — the job ran, called the API, and did not commit; re-dispatch
  costs a second time; report the number to the lead before re-running

### 6 · Improve

Any new failure gets an entry in `docs/MISTAKES.md`, a check in `--preflight`, and a
test. A fix without a check is a fix that lasts until the next batch.

## What is guaranteed, and what is not

Guaranteed, because it is mechanical:

* no batch dispatches without a same-day pilot receipt
* no batch dispatches with duplicate slugs or oversized chunks
* no batch dispatches while the workflow lacks push-retry or a range-scoped
  concurrency key
* every batch is reconciled page by page, and billed-but-lost pages are named

Not guaranteed, and I will not claim it: that no new kind of failure occurs. Sarvam can
change its API, a scan can be corrupt, a runner can die. What is promised is that a
failure is **detected, counted, and reported in pages and money** — and that the same
failure cannot happen twice, because each one becomes a check here.
