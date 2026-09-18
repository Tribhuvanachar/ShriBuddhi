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
