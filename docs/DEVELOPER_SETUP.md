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
python3 tools/dev_server.py          # or plain: python3 -m http.server 8777
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

### Why the key is not pasted into the page, the way convert/ does it

`convert/` holds a Gemini or Vision key in `localStorage` and calls
`googleapis.com` straight from the page, and that works. Sarvam cannot be used
the same way, and the reason is one missing response header rather than a
policy decision:

```
$ curl -X OPTIONS https://api.sarvam.ai/doc-ai/v1/job \
    -H 'Origin: http://localhost:8778' \
    -H 'Access-Control-Request-Method: POST' \
    -H 'Access-Control-Request-Headers: api-subscription-key'
access-control-allow-origin: *
(no access-control-allow-headers, no access-control-allow-methods)
```

Sarvam authenticates with a **custom header**, `api-subscription-key`. A custom
header makes the request non-simple, so the browser preflights it, and the
preflight must name that header in `Access-Control-Allow-Headers` or the
browser refuses to send the real request. It does not. Google's preflight
returns `access-control-allow-headers: content-type` and takes its key in the
query string, which is why the same pattern works there.

So `tools/dev_server.py` serves the pages *and* proxies `/sarvam/…` to
`api.sarvam.ai`, adding the key on the way out. The key comes from the shell
you start it in: never sent to the browser, never written to disk, never
committed. It binds `127.0.0.1` only — anything that can reach it can spend
money.

If Sarvam ever adds `api-subscription-key` to their `Access-Control-Allow-
Headers`, the proxy stops being necessary and the `convert/` pattern works
unchanged. Worth asking them; it is a one-line change on their side.

For scans run in CI the key stays a repository secret and `tools/ocr_auto.py`
drives it.

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
