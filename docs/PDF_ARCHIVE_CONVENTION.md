# PDF → archive.org: the hierarchy, the naming, and what's next

Written 1 Oct 2026, when `.github/workflows/archive-upload-pdf.yml` was
built. Read this before dispatching that workflow, and before building the
future desktop-side matching session this doc keeps referring to.

## Why this exists

The project holds, or will hold, source PDFs for far more works than are
digitized into `data/*.json`. A future session is expected to scan local
drives (described as "terabytes of data, PDFs, etc." across several
machines), match what it finds against the existing bibliography catalogue
(`data/catalogs/dvaita_grantha_anukramani.json` — 2,456 works, imported from
`sarvamula_headings.xlsx`), and get each matched PDF onto archive.org. The
goal stated for that future work: a reader browsing by author or work lands
on the real text — the rendered reader page if it's digitized, a PDF on
archive.org if it isn't yet.

None of that matching logic is built yet, and this doc does not build it.
What has to exist FIRST is a predictable, derivable place on archive.org for
each work to land — not a pile of uploads a human has to remember the names
of. That's what this doc and the workflow give.

## The hierarchy: taxonomy_path, not an invented scheme

The lead's own framing: `data/Tattvavada/` already has the hierarchy —
`SarvaMula` and `Itara`; `Itara` has `DasaSahitya`, `Kavya`, `Stotra`, and
others; the top level of `data/` itself has `vedas`, `vedanga`, `upaveda`,
`darshana`, `itihasa`, `purana`, and so on. **Reuse exactly that, don't
invent a parallel one.**

`archive-upload-pdf.yml`'s `taxonomy_path` input is a work's path relative to
`data/`, using the same folder names `data/` already uses for a digitized
work (e.g. `Tattvavada/Itara/Kavya/raghavendra_vijaya`), or the same
*naming convention* `data/` would use once the work is imported, for a work
that exists only as a PDF so far. This one input carries the whole
parent/child structure (which shelf, which sub-shelf, which work) in a form
that already matches this project's one real, lived-in taxonomy.

## The identifier: derived, not assigned

archive.org items don't nest — there's no real "put this item inside that
folder." An item has one flat identifier and one flat bag of files. So the
hierarchy has to be *encoded*, not *structured*, and it has to be derivable
by anyone (or any future script) without a lookup table.

The workflow computes:

    identifier = "dge_" + taxonomy_path.lower()
                              .replace(illegal chars, "_")
                              .replace("/", "_")
                              .collapse_repeated("_")

`Tattvavada/Itara/Kavya/raghavendra_vijaya` → `dge_tattvavada_itara_kavya_raghavendra_vijaya`

`dge_` namespaces every item this project uploads — the same short-name
convention already used throughout the reader's own CSS/JS (`dge-cbar`,
`dge-commentary-tab`, …) — and makes "every item we ever uploaded"
a plain identifier-prefix search on archive.org
(`https://archive.org/search?query=identifier%3Adge_*`), with no registry
required to enumerate them.

**A future matching session recomputes this from a taxonomy path directly.**
No state has to be read to know where a work's PDF *would* live if uploaded,
or *does* live if it already was.

## The metadata: subject tags carry the hierarchy a second way

archive.org has no nested folder browsing across items, but it does have
faceted subject search. Every taxonomy level becomes its own `subject` tag,
cumulatively:

    Tattvavada
    Tattvavada/Itara
    Tattvavada/Itara/Kavya
    Tattvavada/Itara/Kavya/raghavendra_vijaya

Browsing the `Tattvavada/Itara/Kavya` subject on archive.org then surfaces
every Kavya-shelf upload, at whatever depth. A custom `dge-taxonomy-path`
field also carries the exact, unexploded string, for a script that wants an
exact match rather than a facet.

## One item per work — same granularity as audio

`archive-upload.yml` (audio) already established the pattern: one
archive.org item per grantha (`rgv_audio` for Raghavendra Vijaya,
`smv_audio` in progress for Sumadhva Vijaya), not one giant item for
everything and not one item per file. The PDF workflow matches that
granularity on purpose — it's proven, and archive.org's own item-level
metadata (title, creator, subject) genuinely describes one work, not an
arbitrary bundle.

**Within one item:** a single-file work uploads as one PDF. A work split
into chapters (sarga/adhyaya/kanda — `data/`'s own leaf folders already use
this, e.g. `raghavendra_vijaya/sarga_1` … `sarga_10`) uploads as one PDF per
chapter, into the SAME item. The workflow doesn't auto-rename these — name
each chapter file clearly before handing it to `source_path`
(e.g. `sarga_01.pdf`, `sarga_02.pdf`); the item's own identifier already
carries the work, so the file names don't need to repeat it.

## The ledger: data/catalogs/archive_pdf_catalog.json

Every successful upload (and every deletion) is recorded by
`tools/update_archive_pdf_catalog.py` into
`data/catalogs/archive_pdf_catalog.json` — identifier, taxonomy path, title,
author, file list, when, which workflow run, and whether it was a `sample`
(proof-of-concept) upload. This is a record of what WAS done, not the
source of truth for what a path resolves to (the identifier is always
recomputable) — its job is: know what already exists before uploading it
again, and a human-readable log, the same role
`admin/config/spend_report.json` plays for paid-API spend.

It sits beside the Anukramani catalogue on purpose
(`data/catalogs/dvaita_grantha_anukramani.json`, `.overrides.json`), not
inside it — connecting a `dvaita_grantha_anukramani.json` row to an
archive.org upload (by title/author matching, most likely) is exactly the
"matching ones picked" step described as the future desktop session's job,
and isn't done here. When that's built, the natural shape is one more field
layered onto that catalogue's existing `.overrides.json` (same pattern
already used for scholar corrections — the generated master file is never
edited in place), pointing at an entry in this ledger.

## Running it

    mode=check    verifies the archive.org keys, uploads nothing.
    mode=upload   sends the file(s); requires taxonomy_path + title.
    mode=delete   removes an item this workflow created (ia delete --all)
                  and strikes its ledger entry.
    sample=true   (mode=upload only) generates one small synthetic
                  placeholder PDF instead of fetching a real source --
                  for exercising the whole identifier/metadata/ledger path
                  without a real file yet. Used for this workflow's own
                  1 Oct 2026 proof-of-concept run.

Credentials: `ARCHIVE_PDF_ACCESS_KEY` / `ARCHIVE_PDF_SECRET_KEY`
(`jagadgurumadhvacharyaadmin@gmail.com`), falling back to the same four
legacy generic aliases `archive-upload.yml` already recognized. See
`docs/RESOURCES.md` §1/§3.

## What this doc does NOT do

- It does not scan any drive for PDFs. That's the future desktop session.
- It does not match a PDF to a `dvaita_grantha_anukramani.json` row. Same.
- It does not add a "View PDF on archive.org" link anywhere in the reader.
  That depends on the matching step above existing first — building reader
  UI against data that doesn't exist yet would be guessing at both the data
  shape and the UX, not implementing something asked for.
- It does not create an archive.org *collection* (the formal grouping
  archive.org reviews and approves) — `collection:opensource` is the
  ordinary self-upload collection, same choice `archive-upload.yml` made
  for audio (`opensource_audio`). A dedicated collection is a bigger,
  separate ask if it's ever wanted.
