# Bhāgavata Sāroddhāra importer (hybrid OCR → verified grantha)

Source: the lead's scanned PDF (459 pages, Acharya Vidyadhishthanam edition; Devanāgarī body with Viṣṇutīrtha's
svopajña ṭīkā + editor's footnotes; Kannada ಮುನ್ನುಡಿ and 30 ಸಾರಸಂಗ್ರಹ summaries in front).

```
A  OCR          Vision  : .github/workflows/ocr-vision-pages.yml  → branch ocr-staging/bhagavata_saroddhara (vision_pages_1-459.json)
                Tesseract: 300-dpi PNGs, `tesseract page.png out -l san+kan --psm 4 tsv` with tools/tessdata/fast
B  merge        python3 tools/saroddhara/ocr_merge.py --vision vision/pages.json --tess-dir tess --png-dir hi --out merged
                (Tesseract boxes = geometry; Vision = text; footnote rule; header/heading/verse/ref/footnote regions; agreement A–E)
C  build        python3 tools/saroddhara/build_saroddhara.py --work <dir> --write-data
                → dge/data/bhagavata_saroddhara/{mula,tika_vishnutirtha,tippani,sara_sangraha_kannada,parishishta}
                → <dir>/verify_input/verify_queue.json + verify_queue.html + crops/   (what a human / local Gemini must check)
                → <dir>/build_report.json
D  verify       open verify_queue.html (offline), answer, Export answers.json → verify_output/
E  apply        python3 tools/saroddhara/apply_verified.py verify_output/answers.json   (idempotent; then re-run validators + safe-merge)

D′ chat path   python3 tools/saroddhara/make_chat_batch.py --work <dir> --print 10
               → dge/data/ocr_staging/bhagavata_saroddhara/verify_input/batch_01_critical.json (+ _chunkN.json)
               the critical items only (verses the printed index has but OCR missed, mismatches and near-matches
               against the DGE Madhva mūla) with both OCR readings, the DGE candidate, PDF page and, for missing
               verses, the neighbours + raw OCR lines between them — sized for pasting into a Gemini *chat*
               (no API credits needed; works from a phone).
E′ chat apply  python3 tools/saroddhara/apply_chat_answers.py pasted_reply.txt [--sync-bhagavata]
               parses the chat's JSON (fences/prose tolerated), merges into verify_output/answers.json, runs E.
F  cross-check python3 tools/saroddhara/mula_crosscheck.py --batches 20 --exclude BS_V163,…
               → verify_input/mula_crosscheck.json (every verse whose PRINT differs from the DGE master, word by
               word) + diffs_batch_NN.json (compact word-diff items, no verse bodies, for a chat without URL access).
               decision=dge on an already-unified verse only confirms it; a note that names a print reading becomes
               a "पाठभेदः (मुद्रित-सारोद्धारः): …" line in the verse's `notes` (visible in the reader).
```

**One text, not two.** The DGE Madhva Bhāgavata (`purana/maha_purana/bhagavata_purana_madhva`) is the master
copy of every verse the Sāroddhāra quotes; a verified Sāroddhāra verse carries that text verbatim and keeps the
print's OCR in `ocr`. A human decision of `dge` re-confirms that; a decision of `printed` (a genuine variant
reading in Viṣṇutīrtha's edition) rewrites the Sāroddhāra verse and, with `--sync-bhagavata`, the master shloka
too (old text kept in `previous_text` + `revision`), so the two never drift apart. A `dge` decision whose note
names the print's reading leaves the text alone and records the variant as a पाठभेदः line on the Sāroddhāra verse.

Rules: every verse is matched to the Madhva Bhāgavata already in DGE (`bhagavata_purana_madhva`) by its printed
reference (±3) and, when that fails, by text search over the whole Bhāgavata; verified matches take the DGE text as
canonical and keep the OCR in `ocr`. Recovery of verses the tagger missed is limited to the deficit the printed index
shows per prakaraṇa (the commentary quotes Bhāgavata verses constantly). No Gemini call anywhere.
