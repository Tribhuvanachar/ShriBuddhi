# scans/

Source PDFs the OCR workflows read directly out of the checkout, via the
`pdf_path` input on `.github/workflows/ocr-sarvam.yml`.

## Why they are here and not fetched over a URL

`pdf_url` was the only way to give Sarvam a book, which meant every scan had
to be reachable by anyone. The one we had been testing with was only reachable
because deleting a file from a public repository does not remove it from that
repository's history — not a property to build on, and it ends when the old
Buddhi is deleted. `pdf_path` reads the file from the checkout instead, so a
scan can stay private.

This repository is private. Nothing here is served, linked or published.

## What is here

| File | Pages | Source |
|---|---|---|
| `raghavendra_vijaya.pdf` | 611 | Rāghavendra Vijaya of Nārāyaṇa Paṇḍita with three ṭippaṇīs, ed. Raja Giri Acharya. Copied from `local_drive/Raghavendra_Vijaya/` in Parabuddhi, verified identical by md5. |

The mūla's first shloka — श्रीमल्लक्ष्मीनृसिंहस्य श्रियं दिशतु मे नखः — begins
on **PDF page 44**, under the heading श्रीलक्ष्मीनृसिंहनखप्रार्थनम्. Pages 44–53
are the ten already staged for the three-engine comparison, under
`data/ocr_staging/raghavendra_vijaya/`.

## A note on rights

`local_drive/` in Parabuddhi sits outside that repository's `source/` tree, so
the one-way rule written at the top of its CLAUDE.md — what may become public
is the output of a build, never the input — does not classify this file as
rights-unresolved. That rule still governs what happens downstream: OCR output
promoted from here to the public repository is a publication decision, and a
scan being private is not by itself permission for the text it holds.
