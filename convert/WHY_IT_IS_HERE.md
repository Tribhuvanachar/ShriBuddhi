# convert/ — the browser digitisation pipeline

Moved here from BrahmaBuddhi on 15 Sep 2026. It had no business being
there: the project rule is that BrahmaBuddhi is staging and **no actual
coding happens there**, and this is 25 files of application code.

## What it is

A self-contained browser tool that takes a PDF or a MediaWiki page and
walks it to a schema-mapped `data.json`:

    pdf.js / urlimport.js   get the source in
    vision.js               Google Cloud Vision OCR (key in localStorage)
    tesseract-check.js      a free second reading to disagree with it
    gemini.js               compares the two readings rather than
                            rewriting either, and must self-report a
                            confidence class per shloka
    review-classifier.js    folds that self-report together with Vision's
                            avgConfidence and the cross-engine similarity
                            into classes A–E
    review-ui.js            the queue: only C, D and E reach a human
    mapper.js / github.js   schema map, then a branch and a PR

## Why it matters now

This is already most of the "AI discrepancy queue" the lead asked for.
The five-class policy, the compare-don't-rewrite prompt and the reviewer
queue all exist and work. What it does NOT yet do:

- it knows two engines; the OCR Studio now has three, and Sarvam is the
  only one that keeps page layout
- it reads its own IndexedDB store rather than the staged files under
  `data/ocr_staging/`, so a reading reviewed here is invisible there

Those two are the join, and they are the work remaining.

`backups/` was not brought across — 14 MB of a scratch PDF blob, which is
the whole reason the folder looked large.
