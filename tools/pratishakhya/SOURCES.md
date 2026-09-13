# Rgveda-Pratishakhya — where the digitized text actually came from

Written 11 Sep 2026 after `import_rv_pratishakhya.py` ran for real. Read
`dge/RV_PRATISHAKHYA_KRAMA_ARCHITECTURE.md` sec.4a/4a.1 first for why this
source was chosen over the archive.org PDF scan originally logged in
`dge/PENDING.md`; this file is the narrower, script-facing record.

## The source

The Sanskrit Library, *"Rgveda-Pratisakhya: First XML Edition"*, ed. Peter
M. Scharf, Providence RI, 2010, **Version 0.1**. Catalog card:
`sanskritlibrary.org/catalogsText/fgveda_prAtiSAKya.html`. Underlying
digital text credited there to George Cardona's *"The Rgveda-pratisakhya:
First digital edition,"* Philadelphia, 1993-94. Licence: **CC BY-NC-SA
3.0** (`creativecommons.org/licenses/by-nc-sa/3.0/`) — non-commercial
reuse with attribution, derivatives under the same licence. Śaunaka is
the traditional author; the catalog card itself does not name him.

## There is no download link — how the endpoint was actually found

"First XML Edition" describes the source's internal TEI markup process,
not a file offered to the public. The catalog page's "Text" button calls
`sl.view.gotoText('fgveda_prAtiSAKya')`, which stores the abbreviation in
`localStorage` and navigates to `textTranslation.html`. That page's
scripts (`sl.js`, `sl.model.js` — fetched directly and read; nothing here
came from published API docs) resolve to:

```
GET https://sanskritlibrary.org/LoadText?text=fgveda_prAtiSAKya&texttype=forTranslation
```

which returns the **entire work in one response**: `{"lines": [...]}`,
1,067 entries, each one numbered sutra (`sN.M<br/>...`) followed by a
scholarly apparatus (Cross ref./Allusions in/Allusions to/Parallels/
Comments — cross-references to the Taittiriya- and Vajasaneyi-
Pratisakhyas and to Rgveda verses) all in **SLP1 transliteration**, not
Devanagari and not TEI tags — the TEI markup itself is not exposed
through this endpoint.

**Access-ethics note, carried over from the architecture doc:** this is
not a documented public API, so bulk automation against it should not be
routine. Two fetches have been made against it in this project so far —
one inspection pull (recorded in the architecture doc's Part III), one
real ingestion pull (this one, done with the project lead's explicit
go-ahead: "bulk pull it," 11 Sep 2026). Re-running the importer re-fetches
the same endpoint again; don't script it into a loop or a scheduled job.
If the data needs refreshing later (the source is marked "Version 0.1"
and may be revised), that is a deliberate, one-off re-run, not something
to automate.

## What's actually in the resulting data.json, and what still needs a human

- 1,067 sutras across all 18 patalas. Patala 10 (Krama) = 22 sutras,
  patala 11 (Kramahetu) = 71 — matches the secondary sources cross-checked
  in the architecture doc's sec.2.1 exactly. Other patalas' counts diverge
  somewhat from those secondary sources (notably patala 2: 82 here vs. 41
  there) — an edition/sub-sutra-counting difference, not investigated
  further since it doesn't affect patalas 10-11.
- **258 of 1,067 sutras (24%) carry the source's own `[?]` OCR-uncertainty
  marker** somewhere in the main text. The importer does **not** guess
  what `[?]` stands for — even though it is overwhelmingly `ū` by pattern
  (`p[?]rva`→likely `pūrva`, `s[?]kta`→likely `sūkta`, `br[?]yāt`→likely
  `brūyāt`) — those items are written with `has_uncertain_reading: true`
  and empty `text_devanagari`/`text_iast`, keeping only the raw
  `text_slp1` (with `[?]` intact) as ground truth. **This includes two of
  the sutras already quoted in this document's earlier draft — 10.20 and
  10.22 — which an earlier, less careful pass had silently transliterated
  by guessing `[?]` = ū. That guess is not in the shipped data; it was
  wrong to make even informally, and is called out here so it isn't
  quietly repeated.** Resolving these needs an actual look at Layer B
  (vedavishtaram.in) or Layer C (the RV-Pratishakhya project), not pattern
  matching.
- The scholarly apparatus (`allusions_in`/`allusions_to`/`parallels`/
  `comments`) is kept as **raw SLP1**, not transliterated — it contains
  Vedic-verse citations with their own accent notation (e.g. `y/am`,
  `sk/aBIyAn`) that a plain SLP1→Devanagari pass would mangle. A `true`
  `has_cross_reference_content` flag marks which items have more than the
  `"[?]Pr."` boilerplate, for anyone who wants to go through them by hand
  later.
- `crosscheck` is empty on every item, deliberately — it's meant to record
  once a sutra has actually been checked against Layer B or C, not to be
  pre-filled with an assumption that it has been.
- `patala_name` comes from the secondary sources in the architecture doc's
  sec.2.1, not from this source itself (which carries no chapter-title
  strings at all, only sutra numbers).

## Re-running

```
python3 tools/pratishakhya/import_rv_pratishakhya.py
```

Overwrites `dge/data/vedanga/shiksha/pratishakhya/rigveda_pratishakhya/data.json`.
Needs `requests` and `indic_transliteration` (`pip install requests
indic_transliteration`), same as the rest of `dge/veda_toolkit/`. Does not
touch `shaunakiya_chaturadhyayika/data.json` — that is the Atharvaveda-
Pratishakhya, a different work.
