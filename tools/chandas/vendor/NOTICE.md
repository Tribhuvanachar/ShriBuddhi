# Vendored data — Chandojñānam

The CSV files and `examples.json` in this directory are copied verbatim from
[`hrishikeshrt/chanda`](https://github.com/hrishikeshrt/chanda) ("Chandojñānam"),
by Hrishikesh Terdalkar, pinned at commit `3a9607c6e7a23d60c03d10f839913d01f8bd7ee2`
(2026-04-11), path `chanda/data/`.

**Licence: GNU AGPL-3.0-or-later** (see `LICENSE` in this directory, also
copied verbatim from upstream). Approved for this project on a case-by-case
basis by the project lead (18 Aug 2026) — this is the first AGPL-licensed
content DGE carries; everything else pulled in so far is MIT, CC-BY-*, or
unlicensed-with-permission. Worth remembering if this data (or the `chanda`
library that reads it) ever ends up behind a live network-facing feature
rather than build-time tooling: the AGPL's network-use clause (§13) requires
offering the combined program's source to anyone interacting with it over a
network, not just to people who receive a copy of the files. As pure build-
time data + an offline CLI tool, nothing here currently triggers that; it
would if this became a live "identify my verse" server-side endpoint.

`build_vrutta_db.py` in the parent directory reads these files and writes
`dge/data/vedanga/chandas/data.json`. Re-run it after updating this vendor
copy from upstream (pin a new commit hash in this file when you do).
