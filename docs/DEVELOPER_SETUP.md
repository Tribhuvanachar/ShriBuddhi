# Working on this repository

## Cloning — a plain clone now works everywhere

```bash
git clone https://github.com/Tribhuvanachar/shribuddhi
```

GitHub Desktop's Clone button works too. Nothing special is needed on Windows
or macOS any more.

That was not true until 14 Sep 2026. This repository held **37,234 colliding
paths** and 7 named after reserved MS-DOS devices, so a clone failed on Windows
and silently overwrote half the dictionary on macOS. `tools/safe_paths.py` now
encodes every filesystem-facing name — an uppercase letter becomes lowercase +
`-`, a reserved name gets `~` — and the trees were migrated onto it. The count
today is 0 and 0.

`bash tools/check_checkout.sh` confirms any working copy is safe to commit
from; it probes the filesystem rather than guessing from the OS, so WSL2 and a
case-sensitive Mac volume both pass.

## Running the OCR Studio locally

```bash
python3 -m http.server 8777
```

Then <http://localhost:8777/admin/ocr-studio.html>. Pick a staged file from the
dropdown, or deep-link one:

    ?file=raghavendra_vijaya/sarvam_pages44-53.json

Loading a file now pulls in the **other engines' readings of the same pages**
automatically, so **⚖ Compare engines** shows all three with an agreement
figure against the chosen one. Rebuild the dropdown's index after staging
anything new:

```bash
python3 tools/build_ocr_staging_index.py
```

## Scanning a PDF from your own machine

`tools/sarvam_docai.py` is the local path — no workflow, no browser, and the
key never leaves your shell:

```bash
export SARVAM_API_KEY=...            # your shell only; never committed
python3 tools/sarvam_docai.py --pdf scans/raghavendra_vijaya.pdf \
        --pages 44-53 --work raghavendra_vijaya --dry-run
```

`--dry-run` slices and counts and calls nothing. Drop it to run for real —
Sarvam bills per page, and `--max-pages` (default 200) is the guard against a
mistyped range becoming an invoice.

**Do not put the key in the browser.** The studio makes no API calls of its
own, by design; a key in page JavaScript is readable by anyone with devtools,
and Sarvam's endpoint will not accept a browser origin anyway. For scans run in
CI the key stays a repository secret and `tools/ocr_auto.py` drives it.

## Cloning with the two generated trees excluded

Optional, and only worth it if you want a smaller checkout — `search_index/`
and `data/kosha/` are generated (by `tools/build_search_index.py` and
`kosha_toolkit/importers/`) and are 2 GB of the clone:

```bash
git clone --no-checkout https://github.com/Tribhuvanachar/shribuddhi
cd shribuddhi
git sparse-checkout set --no-cone '/*' '!/data/kosha/' '!/search_index/'
git checkout main
```

## Why

Filenames in this repo carry SLP1 transliteration, where **capitalisation is
meaning**. `D` is ड and `d` is द; `T` is ट and `t` is त. So
`data/kosha/sanskrit_english/apte-1957/e/gaD.json` and `.../gad.json` are two
different dictionary entries.

Windows NTFS and macOS APFS are **case-insensitive by default**. To them those
are one filename. **37,234 tracked paths in this repository collide that way.**
A checkout that "succeeds" on such a filesystem has written one file over the
other roughly 18,000 times, and nothing warns you: the tree looks complete, the
dictionaries look populated, and half the retroflex and aspirate entries are
gone. A commit made from that checkout would then delete them for everyone.

Separately, 7 paths are named `con`, `nul` or `prn` — Sanskrit syllable pairs
that happen to be reserved MS-DOS device names. Windows has refused those as
filenames since 1983. Git detects them and aborts the checkout, which is the
error dialog people hit first — and, luckily, before the silent damage above.

## Why excluding those two trees costs you nothing

`search_index/` and `data/kosha/` are **generated**, not authored:

- `search_index/` is built by `tools/build_search_index.py`, and the reader
  loads it from the CDN by default (`CDN_INDEX` in `js/global-search.js`) —
  a local copy is only needed to test index changes.
- `data/kosha/` is imported by `kosha_toolkit/importers/`.

Nobody hand-edits either one on a desktop. Every path that collides or is
reserved lives inside them; the remaining **24,445 files are clean on every
filesystem** — verified, not assumed.

## If you genuinely need the excluded data locally

You need a case-sensitive filesystem to hold it:

- **Windows**: work inside WSL2 (its ext4 filesystem is case-sensitive), or
  `fsutil file setCaseSensitiveInfo <dir> enable` on an empty directory before
  checking out into it.
- **macOS**: create a case-sensitive APFS volume in Disk Utility and clone
  into that.

Then drop the sparse settings: `git sparse-checkout disable`.

## The permanent fix, and where it stands

The repository already contains the right answer, applied in one place and not
the other two. `bucket_key()` in `tools/build_search_index.py` encodes each
uppercase letter as lowercase + `-` (`Ba` → `b-a`, `ba` → `ba`) precisely so
that no two buckets can collide case-insensitively, and its docstring names
this exact hazard — "the same latent landmine the trigram tree has always
carried, not repeated here". `js/dge-search.js`'s `bucketKey()` mirrors it
exactly.

What remains is to extend that same encoding to the two trees still using the
older schemes — `search_index/postings/` and `data/kosha/*/e/` — and to add
reserved-device-name escaping, which `bucket_key()` does not yet do (`nul`
survives it unchanged). That is a rename of ~37k files plus a rebuild of the
index and a matching change on both sides of the client/builder mirror. It is
tracked separately; until it lands, the sparse checkout above is the supported
way to work from a desktop.
