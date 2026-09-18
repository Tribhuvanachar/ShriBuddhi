# What has gone wrong here, and what each one teaches

Kept because the project lead asked for it after a week was lost to one of
them. Each entry is a real failure with the rule it produced. `CLAUDE.md`
carries the operational subset; this is the full record.

## 1. I told the lead I could not dispatch workflows. I could.

**Cost: about a week of the lead running every OCR job by hand.**

I read a proxy response as "Dispatching … not permitted for this session
type" and reported it as a hard limitation. When I finally retried properly,
the failure was a missing `Content-Type: application/json` header — GitHub
answered 415 and *named the header in the message*. With it, the same call
returned 422 "Required input 'pages' not provided", which is GitHub
accepting and validating the request.

I then dispatched 41 jobs in one batch with no difficulty at all.

**Rule.** Read the error text before classifying it. 415, 403, 422 and a
policy refusal mean four different things. Reproduce with the fault corrected
before concluding it is a wall. When something blocks the lead's own time,
re-test it rather than repeating the earlier diagnosis from memory.

**Second-order rule.** I repeated that claim across several sessions without
re-testing. A limitation asserted once becomes background truth. Re-test
anything that is costing a human manual work, every time it comes up.

## 2. I asserted a negative that my own evidence contradicted

I reported a repository had "zero Actions secrets configured", from an empty
API listing. A workflow log I had read minutes earlier printed
`SARVAM_API_KEY: ***`. The listing was proxy-filtered; the run log was proof.

**Rule.** Before asserting something does not exist, check it against what is
already in hand. Direct evidence outranks an empty listing.

## 3. `pages=1-2000` against a 200-page cap

40 of 41 dispatches failed on `375 pages asked for; cap is 200`. The cap is
deliberate and documented in `tools/sarvam_docai.py`.

**Rule.** Read a tool's limits before a batch, not after. (The failure was
recoverable: the error line reports the true page count, so all 41 totals
were harvested from the failures without re-running anything.)

## 4. Reformatting data files buried the real change

`audit_library.py --fix` pretty-printed `library.json` — a 26,611-line diff,
+24% size. Separately, stripping credit fields produced 3.7 million
insertions because format detection reflowed one-unit-per-line files.

**Rule.** Never `json.load` then `json.dump` a corpus file. Raw string
replacement, or `tools/format_data_json.canonical()`. Check line counts.

## 5. A `--fix` that replaced where it should have merged

`derive_source` rebuilt the `source` block from the payload alone, deleting
`source_url` from 214 entries and `licence` from 197 — CC-BY 4.0 among
them — and reported "234 sources synced". 225 of those were pure loss.

**Rule.** A derived field is merged with what is there, never replaced. A
summary line that counts writes without counting deletions is not a summary.

## 6. I proposed a rename when the lead wanted no history

Asked for a repository nobody could trace, I suggested renaming. A rename
carries every commit with it. The lead corrected me.

**Rule.** When a requirement is about what someone can LEARN from an
artefact, ask what the artefact still carries, not what it is called.

## 7. The scan passed while the tree was not clean

`publish_clean_repo.py --scan` reported clean while `sitemap.xml` held 1,245
absolute URLs under the old host and sixty pages linked their footer at the
old repository. The scanner looked only for the PRIVATE side, so the
repository's own former name was never in the list.

**Rule.** A checker only ever finds what someone already thought to look for.
When asked whether something is clean, spend part of the effort asking what
class of thing nobody has checked for, and say so even with no finding.

## 8. A slug that truncated three works into one

Three Aitareya Upaniṣad items share a 44-character prefix and differ only in
the commentary named at the end. Truncation gave all three the same staging
folder and branch. Caught before dispatch, by asserting uniqueness.

**Rule.** Derive identifiers from the distinguishing part, and assert
uniqueness across the batch before acting on any of it.

## 9. A page range copied from a stale value

A Vision run went `19-648` when the book ran to `19-712`, losing sargas 17-19
and the colophon, because an old end page was carried forward.

**Rule.** Re-derive ranges from the document each time.

## 10. I answered "is it backed up?" from one repository

I said `firebase/functions` was missing from ShriBuddhi and implied that
settled it. It was missing from every private repository — a stronger and
more urgent fact that I only established on the second pass.

**Rule.** "Is this backed up anywhere?" is a question about everywhere.

## 11. A batch that reported 55 successes and had run 47% of the work

The first real Sarvam batch: 130 runs, 21,187 pages. 55 succeeded, 39 were
cancelled, 35 failed. Two faults of mine, and they are different in kind.

**The cancellations cost nothing and hid the problem.** Every chunk of one book
went into `concurrency.group: ocr-sarvam-<work_slug>`, and GitHub keeps at most
ONE pending run per group -- so queuing chunk 3 cancelled chunk 2 while it
waited. 7,800 pages never ran. Cancelled-while-queued never starts a job, so no
money moved, but the batch looked dispatched when a third of it was gone.

**The failures cost real money.** The commit step fetched the branch, committed,
and pushed with no conflict handling. Two chunks of one book finishing close
together both fetch, both commit, and the second push is a non-fast-forward:
rejected, job fails, and the pages it had already paid Sarvam for are discarded.
3,474 billed pages, no text.

The step's own comment already recorded the same shape of loss on 13 Sep --
"which is exactly what happened on 13 Sep, after the OCR had already been paid
for". A note describing how work got lost is not a fix for it.

**Rule.** When a step runs AFTER money has been spent, it may not have a single
point of failure. Retry it, and say in the error what was spent if it still
fails. And never verify a batch by counting successes: count the units of work
that actually landed. 55 of 130 runs succeeding was 47% of the pages, and only
the page diff said so.

## 12. I diagnosed a failure by mechanism instead of by evidence

Correction to entry 11. I reported that 35 runs "were billed and lost" to a push
race, and told the lead I had wasted 3,474 pages of his Sarvam balance.

That was wrong. All 35 carry the same annotation:

    The job was not started because recent account payments have failed
    or your spending limit needs to be increased.

**The jobs never started.** Nothing reached Sarvam; no OCR money was spent. The
12-minute durations I read as "it did real work before failing" were queue time.

How I got there: GitHub's log blobs were unreachable through this session's proxy
all day -- every `/logs` fetch returned BlobNotFound or an empty archive. Unable to
read a log, I reasoned from the code instead: the commit step had no push retry, two
chunks of a book could finish together, therefore a push race. The mechanism was
real, the failure was not.

What I never tried until the pilot failed: the **check-run annotations API**, which
was available the whole time and states the cause in one line. I had one diagnostic
channel blocked and concluded the evidence was unavailable, instead of looking for
another channel.

**Rule.** A plausible mechanism is not a diagnosis. Before naming a cause -- and
absolutely before telling someone what it cost them -- get a statement from the
system itself. When one channel is blocked, that is a reason to find another, not a
licence to infer. For GitHub Actions specifically: annotations
(`/check-runs/<job id>/annotations`) survive when `/logs` does not, and a job's
duration tells you queue time, not work done.

**Second rule.** Overstating what a mistake cost is its own error. It sends the lead
looking at the wrong balance and makes the real cause -- here, a GitHub billing
limit that will block every future run -- harder to see.

## 13. I costed the paid API and treated the machine it ran on as free

I gave the lead a page count and a billing warning for Sarvam, Vision and Gemini, and
said nothing at all about GitHub. 230 runs in September consumed roughly 1,370 of the
2,000 Actions minutes a private repository gets free per month, and every workflow in
the account stopped -- OCR, deploys, nightly sync. The lead found out from an error
message that reads like a failed payment.

Nothing was actually charged. Metered usage and included usage were both $85.27, next
payment due "-". $72.63 of that is Actions on a PUBLIC repo, which is free and
unlimited; the binding number was $11.68 of a $12.00 private-repo allowance.

Why I missed it: I checked the cost I was thinking about. "GitHub is free" is true for
public repositories and false for private ones, and I never converted "130 jobs" into
"1,300 minutes of a 2,000-minute budget" -- one multiplication, available before
dispatch, done only afterwards from a billing screenshot.

**Rule.** Price the whole run, not the part with an invoice attached. Every batch has a
cost in the paid API AND a cost in the compute that calls it, and a free tier is a
budget like any other. `ocr_batch.py --preflight` now states both before any dispatch
and refuses when the minutes exceed a tenth of the monthly allowance.

**The lever worth knowing:** Actions on a public repository is free and unlimited. A
workflow that fetches a public PDF, calls an API and pushes text into a private repo
does not itself need to live in the private one.

## 14. I staged OCR output for eleven works without recording where any of it came from

Asked to run Sarvam over 4,606 pages that Vision had already read, I could not start.
Eleven works sat in `data/ocr_staging/`, complete and committed, and no repository said
which PDF any of them had been OCRed from. Not the staging JSON, which records the
engine, the DPI and the language hints but not the source. Not
`data/ocr_staging/index.json`, which records path, work, shape, engine, pages and bytes.
Not the branch commit messages. Not ParaBuddhi -- the repository whose entire stated job
is to hold the source of truth, so that any output can be rebuilt from its input.

The URLs had lived in a chat transcript from an earlier session, and that session was
gone. I recovered them by reading the scanned title pages of the staged output and
searching archive.org for a book matching the title, the editor and the number of
sub-commentaries.

That recovery nearly introduced a worse error than the one it fixed. Nine of eleven
matched on title convincingly. Bhāgavata Sāroddhāra matched a 560-page archive.org item
by title and author -- and it is a different edition, Gajendragada Shyamaraya's, against
the staged 459 pages of Bāḷagāru Rucirācārya's. Sarvam run on it would have disagreed
with Vision on every page of the book. The conflict router would have read that as OCR
so bad the entire work needed Gemini, and billed accordingly.

What caught it was not judgement. It was downloading each PDF and comparing its page
count against the pages already staged: eight exact matches, and two that did not match
for reasons I then had to explain individually. Rukmiṇīśa Vijaya's 725 against 712 is the
back-matter verse index, correctly excluded. Sāroddhāra's 560 against 459 was the wrong
book.

**Rule.** Provenance is written at staging time or it is lost. Output that cannot name
its input is not reproducible, and re-deriving the input means re-billing the work.
`admin/config/ocr_sources.json` now holds one row per work -- item, file, URL, the PDF's
own page count, the OCRed range -- and `tools/ocr_plan_from_sources.py` builds batch
plans from it, so a plan cannot be typed from memory.

**Second rule.** A source is confirmed by a number, not by a title. Match the page count
against what is already staged, and account for every page of any difference.
