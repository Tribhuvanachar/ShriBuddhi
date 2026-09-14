# Cloning this repository on Windows or macOS

A plain `git clone` — including GitHub Desktop's Clone button — **fails on
Windows and silently corrupts data on macOS**. This is not a bug in your
machine, your network, or GitHub Desktop. Read the two paragraphs under
"Why" before deciding to work around it; the failure is protecting you.

## The short version

Use Git Bash (Windows) or Terminal (macOS). Once, per machine:

```bash
git clone --no-checkout https://github.com/Tribhuvanachar/shribuddhi
cd shribuddhi
git sparse-checkout set --no-cone '/*' '!/data/kosha/' '!/search_index/'
git checkout main
```

Then add the folder to GitHub Desktop with **File → Add local repository**.
From that point on Desktop works normally — branches, commits, pushes, pulls
— and never tries to write the paths it cannot.

Verify with `bash tools/check_checkout.sh`.

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
