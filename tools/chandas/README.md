# Chandas — classical vrutta (metre) database and identification

**Licence note first:** everything under this directory (`vendor/`,
`build_vrutta_db.py`, `identify_vrutta.py`) is **AGPL-3.0-or-later**, not
this repo's usual Apache-2.0 — see `vendor/NOTICE.md`. Approved case-by-case
by the project lead, 18 Aug 2026.

## What's here

- `vendor/` — the metre-lakshana CSVs and `examples.json`, copied verbatim
  from [`hrishikeshrt/chanda`](https://github.com/hrishikeshrt/chanda)
  ("Chandojnanam"), pinned at a specific commit (see `vendor/NOTICE.md`).
- `build_vrutta_db.py` — converts the vendor CSVs into
  `dge/data/vedanga/chandas/data.json`: 190 sama-vrutta, 8 ardhasama-vrutta,
  5 vishama-vrutta, 42 upajati combinations, 10 matra-vrutta and 27
  akshara-count jaati names, 282 entries total. Re-run after refreshing the
  vendor copy.
- `identify_vrutta.py` — a thin CLI/library wrapper around the upstream
  `chanda` PyPI package (same project, same licence) that actually
  identifies the metre of a given verse, rather than just looking one up by
  name. Needs `pip install -r requirements.txt` first (pulls in
  `indic_transliteration`, `sanskrit_text`, `python-Levenshtein`).

## Scope: classical (laukika) vrutta only, not Vedic chandas

This solves a different problem than `dge/veda_toolkit/superseded/
05_chandas_autodetect_FAILED.py`, which tried (and gave up on) automatic
Vedic-metre detection for the Rigveda's 10,552 mantras using this same
underlying library -- Vedic chandas is markedly more irregular (syllable
counts vary, resolution/epenthesis rules differ) than the fixed-syllable
classical vrttas this data models well. Verified against real classical
verses before being written down here, not assumed:

```
$ python3 tools/chandas/identify_vrutta.py "धर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः"
धर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः  ->  अनुष्टुभ्

$ python3 tools/chandas/identify_vrutta.py "विद्या नाम नरस्य रूपमधिकं प्रच्छन्नगुप्तं धनम्"
विद्या नाम नरस्य रूपमधिकं प्रच्छन्नगुप्तं धनम्  ->  शार्दूलविक्रीडित
```

(The Gita's opening pada correctly identified as Anustubh; a Bhartrhari
verse correctly identified as Shardulavikridita.)

## Suggested next step, not done here

Batch-tag the already-ingested Kavya corpus (`kavya-dist` branch, ~67,000
entries) with detected metre per shloka, the way `chandas` field already
exists per-mantra in the Vedic schema (`dge/data/schemas.json`, `vedic_text`
-> `chandas`). Not started -- scoped separately since it touches a corpus
that lives on a different branch/CDN than `main`.
