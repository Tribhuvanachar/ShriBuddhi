# Grantha data architecture — current state and the proposed overhaul

*Prepared 3 Sep 2026 (IST) at the project lead's request, prompted by the
difficulty of tracking mūla / bhāṣya / ṭīkā / upa-ṭīkā inside the
Tattvaprakāśikā and Nyāyasudhā imports. Part 1 documents exactly what is
stored where today. Part 2 is the proposed DGE-native architecture.
Nothing is migrated yet — this document is for the lead's decision.*

---

## Part 1 — How it is stored TODAY

### Where

Every work lives under `dge/data/`, one directory per work, one
subdirectory per layer, each holding a single `data.json`:

```
dge/data/darshana/vedanta/dvaita/DvaitaVedantaIn/
  sutra_prasthana/
    brahma_sutra_bhashya/
      mula/data.json                    ← 571 units
      tika_tattvaprakashika/data.json   ← 224 units
      tika_tattvaprakashikavivriti/…    ← (23 more tika_* siblings)
  later_acharyas/
    nyaya_sudha/
      mula/data.json                    ← 2,715 units (Anuvyākhyāna verses)
      tika_sudha/ … tika_nyayasudha/ … tika_anuvyakhyanam/
                                        ← the Sudhā itself, mis-split by the
                                          source site into 3 sibling layers
      tika_parimala/ … tika_vakyartharatnamala/ … (upa-ṭīkās)
```

`dge/data/library.json` registers each layer directory as a library node;
the reader stitches sibling `tika_*` layers onto mūla cards on demand
(`layer-stitch.js`), matching units by shared `id`.

### What one unit looks like (schema `grantha_mula_text` / `grantha_tika_text`)

```json
{
  "id": "DV_1187",
  "reference": "सूत्रप्रस्थानम् > 1. ब्रह्मसूत्रभाष्यम् > प्रथमाध्यायः > प्रथमः पादः > जिज्ञासाधिकरणम् > ॐ अथातो ब्रह्मजिज्ञासा ॐ",
  "section": "जिज्ञासाधिकरणम्",
  "unit_title": "ॐ अथातो ब्रह्मजिज्ञासा ॐ",
  "sanskrit_text": "ॐ अथातो ब्रह्मजिज्ञासा ॐ\nसूत्रभाष्यम्\n‘ब्रह्म’शब्दश्च विष्णावेव। …30,000 more chars…",
  "artha": "", "notes": "", "tags": [], "references": [], "audio": [],
  "breadcrumb": ["सूत्रप्रस्थानम्", "…"],
  "source": { "site": "dvaitavedanta.in", "url": "…", "content_id": 1142,
              "work_id": 562, "layer": "मूलम्", "anchor": "article1187",
              "fetched": "2026-09-01" },
  "source_html": "<div class=\"lazy-1\" id=\"article1187\">…"
}
```

### Why it is hard to track mūla vs bhāṣya vs ṭīkā — the five real defects

1. **The "mūla" file is not mūla.** For the Brahmasūtra chain, the sūtra
   line, the label "सूत्रभाष्यम्", and Madhva's entire bhāṣya passage sit
   concatenated in ONE `sanskrit_text` string (unit DV_1187 above is
   30,965 characters). The Brahmasūtras do not exist as their own layer at
   all — they are the first line of each blob.
2. **No paragraph identity.** The unit is the source site's "article"
   (roughly one adhikaraṇa view). A single Nyāyasudhā ṭīkā unit runs to
   24,000+ characters with no addressable subdivisions — so "the Sudhā's
   3rd paragraph on this verse" cannot be referenced, edited, or linked.
3. **Foreign, flat IDs.** `DV_1187` is dvaitavedanta.in's HTML anchor
   number. It encodes nothing (no adhyāya/pāda/sūtra), sorts arbitrarily,
   and is meaningless the day the source site changes. Layer alignment
   works only because sibling files happen to reuse the same anchor ids.
4. **No commentary chain.** Every commentary is a flat `tika_*` sibling of
   `mula`. Tattvaprakāśikā (on the bhāṣya), Bhāvabodha (on the TP), and
   Vivṛtti (also on the TP) all look alike — the data does not say WHAT
   each layer comments on. The Nyāyasudhā node is the extreme case: the
   Sudhā (itself the ṭīkā) is stored as three accidental sibling layers
   next to its own upa-ṭīkās.
5. **Provenance bloats every unit.** The full `source` object and
   `source_html` are repeated on all ~50k DV units — useful for audit,
   dead weight for reading and editing.

One thing is genuinely good and must be kept: `source_html` preserves the
site's real `<p>` boundaries and `<h2>` layer labels — which means the
overhaul below can be done **mechanically from data we already hold**,
with no re-crawl.

---

## Part 2 — Proposed DGE-native architecture

Design goals, from the lead's brief: separate node per text-layer;
paragraph-level unique IDs; commentary paragraphs tied to the exact
paragraphs they gloss; one naming convention everywhere; original source
references retained, but in a separate mapping file; easy manual editing
(`data.json` opens and you can find things).

### 2.1 One work-family, one manifest, one node per layer

```
sutra_prasthana/brahma_sutra/
  work.json                        ← the family manifest (see 2.4)
  sutra/data.json                  ← the 564 sūtras, nothing else
  bhashya/data.json                ← Madhva's bhāṣya
  tika_tattvaprakashika/data.json  ← Jayatīrtha, ON the bhāṣya
  tippani_bhavabodha/data.json     ← Raghūttama, ON the Tattvaprakāśikā
  tippani_vivritti/data.json       ← ON the Tattvaprakāśikā
  _sources/dv_map.json             ← provenance sidecar (see 2.5)
```

Every layer declares its place in the chain in `work.json`:
`"commentary_on": "bhashya"` (or `"sutra"`, or `"tika_tattvaprakashika"`).
The directory prefix says the rank (`sutra`/`mula`, `bhashya`, `tika_`,
`tippani_`), the manifest says the exact parent. Nyāyasudhā becomes
honest: `anuvyakhyana/mula` (verses) → `tika_nyayasudha` (the Sudhā,
consolidated from today's three fragments) → `tippani_parimala`,
`tippani_vakyartharatnamala`, … each marked ON the Sudhā.

### 2.2 Canonical references and paragraph IDs

Two coordinates, both first-class on every unit:

- **`ref` — the traditional citation**, shared by ALL layers of a family:
  `1.1.1` (adhyāya.pāda.sūtra) for the Brahmasūtra chain; adhyāya.śloka
  for Gītā; kāṇḍa.adhyāya.… per work, declared once in `work.json`
  (`"ref_scheme": "adhyaya.pada.sutra"`). This is how humans find things.
- **`id` — the paragraph's own stable name**: `<ref>.<layer-letter><n>`,
  e.g. `1.1.1.s1` (sūtra), `1.1.1.b3` (3rd bhāṣya paragraph),
  `1.1.1.t7` (7th TP paragraph). Unique within its file; globally
  addressable as `<work>:<layer>:<id>` (e.g. `bs:tika_tattvaprakashika:1.1.1.t7`).
  IDs are **append-only**: once published, never renumbered — a paragraph
  split later becomes `b3a`/`b3b`; a deletion leaves a hole. Links must
  never rot.

### 2.3 The unit, redesigned

```json
{
  "id": "1.1.1.t2",
  "ref": "1.1.1",
  "text": "तत्रादिसूत्रस्येदं सङ्गत्यादि। …one paragraph only…",
  "pratika": "अथातो ब्रह्मजिज्ञासा",
  "on": ["1.1.1.b1", "1.1.1.b2"],
  "heading": "जिज्ञासाधिकरणम्",
  "artha": "", "notes": "", "tags": [], "audio": []
}
```

- `text` is **one paragraph, pure text** — no inline labels like
  "सूत्रभाष्यम्" (the layer IS the label), no HTML.
- `on` ties the paragraph to the exact paragraph(s) of its parent layer
  it comments upon. Coarse anchoring is legal and expected at first:
  `"on": ["1.1.1"]` (a bare ref = "somewhere in this sūtra's parent
  text") — refined to paragraph precision progressively. The reader
  renders whatever precision exists.
- `pratika` holds the quoted opening words where the commentary itself
  supplies them (Sanskrit ṭīkās almost always do) — it is both a display
  convention and the machine-checkable evidence for the `on` links.
- `heading` marks section starts (adhikaraṇa names) instead of repeating
  a breadcrumb on every unit.

### 2.4 `work.json` — the family manifest

```json
{
  "work": "brahma_sutra",
  "title": "ब्रह्मसूत्रम् (माध्वप्रस्थानम्)",
  "ref_scheme": "adhyaya.pada.sutra",
  "layers": [
    { "slug": "sutra",   "title": "सूत्रम्",  "author": "बादरायणः" },
    { "slug": "bhashya", "title": "भाष्यम्", "author": "श्रीमदानन्दतीर्थः", "commentary_on": "sutra" },
    { "slug": "tika_tattvaprakashika", "title": "तत्त्वप्रकाशिका", "author": "श्रीजयतीर्थः", "commentary_on": "bhashya" },
    { "slug": "tippani_bhavabodha", "title": "भावबोधः", "author": "श्रीरघूत्तमतीर्थः", "commentary_on": "tika_tattvaprakashika" }
  ],
  "licence_note": "…the case-by-case permission text, once, not per unit…"
}
```

Open `work.json` and the whole commentary tree is visible at a glance —
this is the "when I open data.json I should find it" requirement, solved
one level up so each layer's `data.json` stays a clean array of
paragraphs.

### 2.5 `_sources/dv_map.json` — provenance out of the text files

Exactly what the lead asked for: the original references retained,
separately.

```json
{
  "site": "dvaitavedanta.in", "fetched": "2026-09-01",
  "map": {
    "bhashya:1.1.1.b1": { "anchor": "article1187", "url": "…", "content_id": 1142, "work_id": 562 },
    "tika_tattvaprakashika:1.1.1.t1": { "anchor": "article1184", "url": "…" }
  }
}
```

Every local paragraph maps back to the source article it was cut from;
`source_html` archives move to a gitignored/cold path (or stay only in
this sidecar) instead of riding inside every reading unit. Nothing about
auditability is lost; the reading files shrink by roughly a third.

### 2.6 File sizing, editing, validation

- One `data.json` per layer while it stays under ~2 MB; larger layers
  split per adhyāya (`bhashya/adhyaya-1.json` …) with `work.json` listing
  the parts. Units stay in reading order; `ref` + append-only ids make
  diffs small and reviewable.
- `tools/validate_grantha.py` (new) enforces: ids unique and well-formed,
  every `on` target exists in the parent layer, every `ref` valid for the
  work's `ref_scheme`, every layer's `commentary_on` resolves, every unit
  present in `dv_map.json` for migrated works. Runs in CI beside the
  existing validators.

### 2.7 Migration path (additive — nothing breaks while it runs)

1. **Pilot: the Brahmasūtra family.** A compiler reads today's files and
   emits the new tree mechanically: `source_html`'s `<h2>` labels split
   sūtra from bhāṣya; `<p>` boundaries give the paragraphs; shared DV
   anchors give the coarse `on` links; pratīka matching refines them.
   Human review of the pilot before anything else moves.
2. **Nyāyasudhā second** — includes consolidating the three accidental
   Sudhā fragments into one `tika_nyayasudha` layer and typing the
   upa-ṭīkās.
3. The reader gains a `work.json`-aware path; the legacy schema stays
   supported until the last work migrates, so the site never breaks
   mid-migration.
4. Same recipe then rolls across the remaining DV works, then (as
   worthwhile) the rest of the library. Every migrated work's old
   directory is deleted only after its `dv_map.json` round-trip is
   verified.

### What this buys, concretely

- "Show me Jayatīrtha on this bhāṣya paragraph" is a lookup, not a
  scroll through 30k characters.
- Editors fix one paragraph in one small JSON object with a stable id;
  the Genie, search index, and deep links all cite `bs:bhashya:1.1.1.b3`
  forever.
- New commentaries (e.g. a future OCR import of another ṭīkā) declare
  `commentary_on` and drop in without touching existing files.
- Provenance survives, centralised and auditable, without weighing down
  every unit.
