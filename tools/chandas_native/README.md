# chandas_native — from-scratch classical metre engine, Apache-2.0

An independent, clean-room replacement path for the AGPL-3.0 content in
`tools/chandas/` (vendored from `hrishikeshrt/chanda`). **Licence: this
directory is plain Apache-2.0, this repo's default** — no AGPL code or
data anywhere in it.

## What's here

- `scan.py` — syllabifies Devanagari text and applies the standard
  laghu-guru (light-heavy) rule (long vowel, or followed by anusvara/
  visarga/a conjunct → guru; otherwise laghu; final syllable of a pada is
  a wildcard, since its weight is prosodically "anceps"). Written from the
  textbook rule itself, not read off anyone's implementation.
- `build_db.py` — generates `data.json` from the eight three-syllable
  ganas (the "yamataarajabhaanasalagaam" mnemonic) plus a small set of
  named classical metre formulas. Every formula is a standard, widely
  taught fact (Pingala/Vrittaratnakara/Chandomanjari tradition, centuries
  public domain) — this file states them directly rather than
  transcribing anyone's CSV.
- `identify.py` — scans a verse and matches it against `data.json`:
  exact pada-pattern match, a dedicated rule-check for Anustubh (which
  isn't a fixed pattern), and a `difflib`-based fuzzy fallback for
  near-misses.
- `verify.py` — regression test against three real, independently-recalled
  verses (Gita 1.1, two Bhartrhari verses), each checked against its
  well-known metre. Run: `python3 tools/chandas_native/verify.py`.

## Scope — read this before treating it as a drop-in replacement

This is **not** a full replacement for `tools/chandas/`'s AGPL data yet.
It's a deliberately smaller, honestly-scoped core, extended once (21 Aug)
after a fact-checking pass against real sources found several corrections
and additions worth keeping — see `dge/PENDING.md` for the full trail:

| category | this directory | AGPL vendor (`tools/chandas/`) |
|---|---|---|
| sama-vrutta | 21 | 190 |
| ardhasama-vrutta | 3 (Pushpitagra, Viyogini/Sundari, Aparavaktra) | 8 |
| vishama-vrutta | none | 5 |
| upajati | 16 (all Indravajra/Upendravajra combinations; 14 mixed forms carry a sourced traditional name, see below) | 42 |
| matra-vrutta | 4 (Arya, Giti, Upagiti, Udgiti) | 10 |
| akshara-jaati names | 20 (syllable counts 1-20; 21-26 deliberately not included) | 27 |
| yati (caesura position) | not included | included |

Verification methods used, in increasing order of how much they lean on
an outside source: (1) scanning a real verse and checking the
identification — Gita 1.1, two Bhartrhari verses, see `verify.py`; (2)
internal gana/matra arithmetic — every sama/ardhasama entry's syllable
and matra counts are derived mechanically from the gana table, not typed
in by hand, so a transcription slip would show up as an inconsistency;
(3) for the 13 original sama-vrutta, comparing the independently-derived
`lakshana` against the AGPL vendor's own values as a pure QA step (all
matched, expected for old public-domain facts, not evidence of copying);
(4) for the upajati proper names, decoding a cited source's raw
laghu/guru symbols by hand — see the note in `build_db.py` right above
`NAMED_UPAJATI` for a concrete case where two "scholarly-looking" sources
flatly disagreed and had to be resolved this way rather than trusted on
authority.

Not included, and why: vishama-vrutta and the Vaitaliya/Aupacchandasika
matra-vrutta family need a richer schema (terminal-gana rules, not just a
matra-per-pada count) than exists here yet. Akshara-jaati names above 20
were left out after three independently-found sources gave three
different, partly self-inconsistent mappings — better absent than wrong.

Extending this further means the same thing each time: check the new
entry against a real primary source or a real verse, the way everything
above was checked — not transcribing more of the AGPL vendor's CSVs,
which would defeat the point.

## Status relative to `tools/chandas/`

Both directories currently coexist. Retiring the AGPL vendor copy in
`tools/chandas/` in favour of this one is a coverage/completeness call for
the project lead to make, not something this tool should do unilaterally
— see `dge/PENDING.md`.
