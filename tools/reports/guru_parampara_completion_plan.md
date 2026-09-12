# Guru Paramparā — plan to 100% completion

*4 Sep 2026 · for the project lead. Editable — corrections in place are welcome.*

## Where we stand (audit of the 215 committed figures)

| Field | Filled | Gap |
|---|---|---|
| period / succession dates | 215 / 215 | — |
| sources (traceability) | 215 / 215 | — |
| contribution text | 117 / 215 | 98 missing; **112 are one-liners (<60 chars)** |
| brindāvana | 110 / 215 | 105 |
| place | 113 / 215 | 102 |
| pūrvāśrama name | 87 / 215 | 128 |
| works | 50 / 215 | **165** |
| titles | 21 / 215 | 194 |
| geo (lat/lng) | 0 / 215 | 215 — no place is geocoded yet |

Thin lines by works-gap: Śrīpādarāja 35, Vyāsarāja 29, Rāghavendra 22,
Kāśī 20, Uttarādi 16. (Mūla-trunk figures legitimately have no "works".)

## The machinery is now in place

1. **One central store** — `dge/guru-parampara/data/parampara.json`. All
   three reader layouts (guru1/2/3) and the tracker feed from it via
   `guru-data.js`; `people/mathas/places.json` are regenerated from it by
   `tools/build_guru_parampara_entities.py`. No page carries its own copy.
2. **Admin editor** — `admin/guru.html`: every field editable; guru /
   maṭha / place / works are dropdown-backed entities so a name can never
   be entered twice with different spellings; gps with a live Google-Maps
   preview; sources per figure; every save appends to a visible change
   log; superadmins see drafts overlaid in all three layouts before the
   export is committed.
3. **Tracking** — each figure carries `sources[]` + `confidence`, each
   admin edit is logged with timestamp + changed fields, and both are
   displayed in the readers ("Sources (tracking)" row).

## Filling the gaps — three streams

### Stream A · site harvest (Claude does it, ₹0)

Per-line authoritative sources, harvested server-side and merged:

| Line | Primary source | What it fills |
|---|---|---|
| All lines | sumadhwaseva.com (guru-charitra pages) | bios, pūrvāśrama, works, brindāvana |
| All lines | madhwayati.blogspot.com (lead-added) | yati mahime, matha paramparas incl. smaller/Aṣṭa-maṭha lines (Kundapura Vyāsarāja, Odampalli, …) — a lead into the paryāya successions no other free source carried |
| Uttarādi 35 | uttaradimath.org parampara pages | dates, works, brindāvana, titles |
| Rāghavendra 30 | raghavendramutt.org / srsmatha.org | bios, brindāvana, works |
| Vyāsarāja 34 | vyasarajamatha.org | succession, brindāvana |
| Sode + Udupi aṣṭa | sodemutt / udupi maṭha sites | paryāya data, works |
| Kāśī / Gokarṇa 23 | kashimath.org, partagali.org | succession, seats |

Method, per guru: fetch every source page that mentions them → extract the
facts as bullet points → **merge and re-express in fresh wording** (facts
are not copyrightable; the phrasing will be original — I do the rephrasing
in-session, so this costs no Gemini credits at all) → write into
`parampara.json` with each contributing site recorded in `sources[]` and
`confidence` set (`high` when ≥2 sources agree, `traditional` otherwise) →
run the entities rebuild + a Playwright sanity pass → safe-merge. Where
sources disagree (dates differ, succession disputed), both readings go
into `note` rather than silently choosing.

Geo: brindāvana towns are a small, public list (Mantralaya, Malkhed, Nava
Brindāvana, Sode, Mulbagal, Kumbakonam…). I geocode the ~60 distinct
places once from public coordinates, attach `gps` per node, and every
layout's "map ↗" link lights up.

Batches (each merged + screenshot-verified separately):
1. Rāghavendra line 30 (richest sources) → 2. Uttarādi 35 → 3. Vyāsarāja
34 → 4. Śrīpādarāja 36 → 5. Udupi aṣṭa + Sode → 6. Kāśī/Gokarṇa →
7. Haridāsa 10 + peripherals. Estimate: one to two batches per working
session; the whole harvest is a few sessions of work, zero API cost.

### Stream B · the human filler (your volunteer)

The admin page is their tool — no JSON knowledge needed:
1. They open `admin/guru.html` (superadmin flag), pick a guru, fill what
   they know (Kannada or English), add their source in the Sources box,
   Save. They can immediately see it in any reader layout.
2. When done, **Export merged JSON** downloads the full file + changelog —
   they mail it to you or drop it into `tasks/WEEKLY_INSTRUCTIONS.md` ("apply
   the attached parampara export"), and the Sunday session (or I) commit it.
3. To direct their effort, the tracker page can show a per-figure
   completeness score; simplest signal now: filter the admin list and look
   for blanks. I can add a "least complete first" sort on request.
4. Priority for them = what harvesting can't get: family/oral traditions,
   pūrvāśrama details, uncommon titles, corrections to disputed dates.

### Stream C · interlinking with the Library

- Works chosen in the admin already come from a central works datalist
  (parampara works ∪ library titles). Next increment: when a guru's work
  exists in the Library, the readers link the work chip straight to the
  reader (`index.html?path=…`), and the Library's author facet links back
  to the guru's card. The shared key is the person id in
  `parampara.json` — one spelling, everywhere.
- `dge_entities.json` gains person entries generated from parampara ids
  so kosha/search can also resolve guru names.

## Copyright stance

Only facts (names, dates, places, work titles) are taken as facts; all
descriptive prose is freshly written by merging multiple accounts, never
copied from any single site; every figure lists the sites consulted in
`sources[]`, both as scholarly honesty and as attribution. Photos are NOT
copied — the readers link to Wikimedia Commons searches; actual images
only from Commons (license-checked) or your own photographs via the admin
image field.

## Definition of 100%

Every one of the 215 figures has: period ✓ (done), brindāvana + place +
gps, ≥3-sentence contribution, works list (or explicit "no known works"),
pūrvāśrama + titles where recorded, ≥2 sources, confidence set — and the
tracker shows a 215/215 completeness bar.

**Next step on your go-ahead:** I start Stream A batch 1 (Rāghavendra
line, 30 figures) + the one-time geocoding pass, and deliver it merged
with screenshots.
