# Where upstream data goes, and what we call it (1 Oct 2026)

**The rule.** Every import, OCR run, ingest and weekly sync lands in **ParaBuddhi first**, untouched.
ShriBuddhi is where the origin's tags are stripped and the material is rearranged and *stitched*:
`Tattvavada/SarvaMula`, for one, is not the SetuTila site. It is SetuTila's text with tīkā and
ṭippaṇī pulled in from dvaitavedanta.in and anandamakaranda.in, under our own labels. So after
stitching, no ShriBuddhi folder equals any one upstream site, and that is exactly why the raw copy
has to be kept somewhere that never changes.

```
upstream site ──watch-sources.yml──▶ ParaBuddhi  source/_raw/<source>/   (unchanged, landed first)
                                     ParaBuddhi  import_config/destinations.registry.json  (the map)
                                          │
                       a person reads the Sunday report, runs a stitch step
                                          ▼
                                     ShriBuddhi  data/…   (our paths, our labels)  ──manual──▶  Jagat
```

## The map: `import_config/destinations.registry.json` (in ParaBuddhi)

One entry per upstream **section** (a work and its layer on that site):

| field | meaning |
|---|---|
| `origin_tags` | the site's own labels for it (`cls`/`chunk` on setutila, `layer`/`work_id` on dvaitavedanta, `type`/`chapter` on anandamakaranda, `work` on advaitasharada, `repo`/`layer` on vishvasa …) |
| `origin_sample`, `origin_url_sample` | an example breadcrumb and URL, so a person can recognise it |
| `destination` | the ShriBuddhi folder (under `data/`) it is stitched into |
| `status` | `mapped` (one folder), `ambiguous` (several candidates, pick one), `unresolved` (not stitched in yet, or renamed), `manual` (a person set it) |
| `decision` | `not_used` marks a section deliberately not taken; it stops being reported |
| `our_label`, `layer_kind`, `commentator`, `note` | optional, hand-written |
| `label_map` (per source) | which of **our** layer names each origin label became (`Sarvamula` → `mula`, …), counted from the provenance maps |

Seeded 1 Oct 2026 from ParaBuddhi's `provenance/source/**/map.jsonl` and ShriBuddhi's `data/`:
5,047 sections, 4,022 mapped, 269 ambiguous, 756 unresolved. Unresolved and ambiguous ones are listed,
**not guessed**. Edit the file (in ParaBuddhi) to settle them; a rebuild keeps hand edits.

```bash
python3 tools/watch/build_destinations.py --pb ../parabuddhi --sb . --write   # (re)seed, keeps hand edits
python3 tools/watch/build_destinations.py --pb ../parabuddhi --sb . --check   # exit 1 while any section is unsettled
```

A weekly sync that finds a *new* upstream section with no entry here has found something nobody has
decided about; it appears in the Sunday report as unmapped rather than being imported into the wrong place.

## The weekly watch

`watch-sources.yml` runs **Sunday 02:00 IST** (cron `30 20 * * 6`, UTC) and `watch-indowordnet.yml` at the
same time. Sources: GRETIL, Ambuda, sanskritsahitya, sa.wikisource, ashtadhyayi.com, DCS, Saṃsādhanī (SCL),
dvaitavedanta.in, setutila.in, anandamakaranda.in, srivaishnavan.com, advaitasharada, the 13 vishvAsa
repositories, and the smaller feeds the registry lists (`others`).

Per source: probe → land raw in ParaBuddhi (**must succeed**; a change that cannot be landed fails the run) →
one e-mail to the superadmins. It never writes ShriBuddhi's `data/`.

Needed once (Settings → Secrets and variables → Actions):

* `PARABUDDHI_TOKEN` (secret): Contents + Actions read/write on `Tribhuvanachar/ParaBuddhi`
* `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` (secrets): any SMTP account
* `SUPERADMIN_EMAILS` (variable): comma-separated. Roles live in Firestore, so the list cannot be read from the repository.

Without SMTP or recipients the report is filed as an issue labelled `watch-report` and says so.

## Stitch steps (ShriBuddhi side, manual, from the copy ParaBuddhi holds)

* `stitch-ashtadhyayi.yml`: reads the commit in `source/_raw/ashtadhyayi_com/LATEST.json`, refuses any other.
* The others (SetuTila → SarvaMula, dvaitavedanta → DvaitaVedantaIn, anandamakaranda, meghamala) are ParaBuddhi's
  `import.yml` + `tools/publish.py`; the registry above says where each section goes.
* Still to move behind the same rule: `import-kavya.yml`, `ingest-gretil-bulk.yml`, `darshanas.yml`,
  `import-dasa-sahitya.yml`, `ocr-*.yml`. They write to ShriBuddhi directly today and must dump their raw
  fetch/engine output into ParaBuddhi first (`tools/watch/land_raw.py` is the helper). See docs/HANDOFF.md.
