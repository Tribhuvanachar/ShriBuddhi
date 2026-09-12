# Darśanas — Nyāya, Vaiśeṣika, Mīmāṃsā

The tree under `dge/data/darshana/` is a **build product**. Nothing in it is
hand-authored. Edit `darshana_works.json` and re-run the scaffolder.

```bash
python tools/darshanas/test_darshanas.py                      # offline, no network
python tools/darshanas/scaffold_darshanas.py --dry-run        # see what would change
python tools/darshanas/scaffold_darshanas.py --data dge/data  # write
python importers/dispatch.py tarkasangraha_dipika             # ingest one GRETIL text
```

Or use the **Darshanas — scaffold and ingest** workflow, which defaults to
`dry_run: true` and never pushes to main.

---

## Files

| File | Role |
|---|---|
| `darshana_works.json` | **The dump.** Bibliographic source of truth: works, authors, commentary edges, verification status, corrections. |
| `curriculum.json` | Cross-cutting curriculum index (Tenali + marked substitutes). Never the bibliographic hierarchy. |
| `darshana_sources.json` | Acquisition registry — every source checked, tiered, with its licence. |
| `scaffold_darshanas.py` | Generates the tree, `_works_index.json`, `_graph.json`; syncs `taxonomy.json` + `library.json`. |
| `test_darshanas.py` | Offline tests for both the scaffolder and the GRETIL parser. |
| `../../importers/darshana_gretil.py` | GRETIL ingestion for the śāstra texts (prose, section-segmented). |

---

## Shape of the tree

```
dge/data/darshana/
  _works_index.json        flat leaf lookup with verification status
  _graph.json              commentary edges — the real genealogy
  nyaya/
    prachina_nyaya/nyaya_sutra/{mula,bhashya_vatsyayana,varttika_uddyotakara,
                                tatparya_tika,tatparya_parishuddhi}/data.json
    prakarana/tarkasangraha/{mula,tika_dipika,tika_nyayabodhini,tika_padakritya,
                             tika_sarvasva,tika_nilakanthi,tika_bhaskarodaya}/
    bhasha_pariccheda/karikavali/{mula,tika_siddhanta_muktavali,tika_dinakari,
                                  tika_ramarudri,tika_kiranavali}/
    navya_nyaya/tattvacintamani/<khanda>/{mula,aloka,mathuri,didhiti,jagadishi,gadadhari}/
    navya_nyaya/tattvacintamani/anumana_khanda/vadas/<vada>/<layer>/
    navya_nyaya/{vyutpattivada,shaktivada,badhanta}/mula/
    pramukha_prakarana/nyaya_kusumanjali/{mula,tika_bodhini,tika_prakasha,tika_makaranda}/
  vaisheshika/sutra_and_bhashya/{vaisheshika_sutra,prashastapada_bhashya}/
  mimamsa/
    sutra_and_bhashya/mimamsa_sutra/{mula,shabara_bhashya}/
    bhatta/{shlokavarttika,tantravarttika,tuptika}/
    prabhakara/{brihati,prakarana_panchika}/
    prakarana/{arthasangraha,mimamsa_nyaya_prakasha,shastra_dipika,nyaya_ratnamala,
               jaiminiya_nyayamala,bhatta_dipika,bhatta_rahasya,mimamsa_paribhasha}/
```

114 layer files, 59 directories, 92 commentary edges.

**The folder tree is deliberately flat.** All commentaries on a work sit as
sibling layer folders under it, so a fourth-order gloss does not produce a
four-deep directory. The true genealogy lives in `comments_on` / `_graph.json`.
Bhāskarodaya is a gloss on the Nīlakaṇṭhī which comments on the Dīpikā which
comments on the Tarkasaṅgraha — that's `layer: 3` in the graph, not
`tarkasangraha/tika_dipika/tika_nilakanthi/tika_bhaskarodaya/` on disk. This
matches the `mula` / `tika_jayatirtha` / `tippani` convention already in
`dge/data/sarvamoola_grantha/`.

---

## The vāda texts — why they are not folders-per-work

Pañcalakṣaṇī, Caturdaśalakṣaṇī, Siddhāntalakṣaṇa, Sāmānyanirukti, Savyabhicāra,
Satpratipakṣa, Avayava, Bādha, Bādha-Vibhājaka, Pakṣatā, Avacchedakatānirukti,
Vyādhikaraṇa, Vyāptyanugama are **not independent works**. They are named topical
sections of Tattvacintāmaṇi's Anumāna-khaṇḍa that acquired titles because they
circulate as printed extracts bundled with Dīdhiti + Jāgadīśī / Gādādharī.

"Pañcalakṣaṇī of Jagadīśa" and "Pañcalakṣaṇī of Gadādhara" are the **same
section at two commentary layers**, not two works. So they are modelled as
topic × layer:

```
tattvacintamani/anumana_khanda/vadas/panchalakshani/
  mula/  didhiti/  jagadishi/  gadadhari/
```

Folder-per-work would duplicate the section under each commentator and detach it
from its parent khaṇḍa.

Three exceptions, filed as ordinary works:

- **Vyutpattivāda** and **Śaktivāda** — genuinely standalone Gadādhara treatises
- **Bādhānta** — Rucidatta's, and Rucidatta sits at the Prakāśa/Āloka layer, not
  the Gādādharī layer, so it belongs nowhere near the Dīdhiti branch

---

## Corrections encoded in `darshana_works.json`

Eight errors were found while verifying the proposed taxonomy. Each is recorded
in the `corrections` array so it does not get re-introduced:

| Claim | Verdict |
|---|---|
| Tarkasaṅgraha has a commentary "Āloka" | **False.** Āloka is Pakṣadhara's on Tattvacintāmaṇi. Removed. |
| Nīlakaṇṭhī and Bhāskarodaya comment on Tarkasaṅgraha | **Wrong level.** Nīlakaṇṭhī is on the Dīpikā; Bhāskarodaya is a gloss on the Nīlakaṇṭhī. |
| Kiraṇāvalī belongs in the Muktāvalī tree | **Two homonymous works.** Udayana's is on the Praśastapādabhāṣya; Kṛṣṇavallabhācārya's is on the Muktāvalī. Both encoded, separately. |
| Ṛjuvimalā is by Prabhākara | **False.** Bṛhatī is Prabhākara's; Ṛjuvimalā is Śālikanātha's, on the Bṛhatī. |
| Kusumāñjali's Prakāśa is by Varadarāja | **Conflation.** Bodhinī = Varadarāja, Prakāśa = Vardhamāna, Makaranda = Rucidatta. Haridāsa is not attested. |
| Rāmarudrī is the title | **Refinement.** The work is the Taraṅgiṇī; Rāmarudrī is the patronymic short name. |
| The vāda texts are independent works | **Mostly false** — see above. |
| Mādhava / Āpadeva / Laugākṣi are Prābhākara | **False.** All three are Bhāṭṭa; the impression comes from a Britannica page-layout artifact. |

Four items are listed under `unverified_do_not_encode` — Subodhinī / Mañjūṣā /
Gaṅgārāmī on the Muktāvalī, Bhāṭṭacintāmaṇi's authorship, Viśvanātha's exact
year, and Haridāsa on the Kusumāñjali. They stay out of the tree until a
manuscript catalogue settles them.

Every leaf carries `verification`: **110 verified, 4 plausible**. Nothing is
asserted without a status.

---

## Curriculum index

`curriculum.json` is a **cross-cutting index**, not the hierarchy. A work lives
once, under its textual tradition; the curriculum only says which level touches
it and for what portion.

The honest state of the Tenali material:

- **The official 14-level Tarka and Mīmāṃsā portion tables are not publicly
  indexed.** `tarka.levels` and `mimamsa.levels` are deliberately **empty**. They
  are not reconstructed.
- What *is* verified: the Tenali **Vedānta** and **Vyākaraṇa** 14-semester
  tables (both begin with tarka-saṅgraha-dīpikā then muktāvalī, which anchors the
  Tarka track's foot).
- What is *attested*: the Tarka paper ladder from published 2010 exam results —
  Tarkasaṅgraha-Dīpikā → Muktāvalī → Siddhāntalakṣaṇī → Gadādharī (three distinct
  Gadādharī levels). Positions in the numbered sequence are not given.
- Note the unreconciled conflict: Indica states Tarka is **6 years**; Medha
  Gurukulam states **14 semesters**.
- Substitutes with real portion detail (Ahobila Math B.A. / M.A. / Prāk-Śiromaṇi
  Nyāya) are included with `status: "substitute"` and must never be presented as
  Tenali.

**Highest-value next action**, recorded in `curriculum.json → acquisition`: two
PDFs — `TENALI EXAMS.pdf` and `समग्रपरीक्षापाठ्यक्रमः.pdf` — are attached to
Bhāratīya Vidvat Pariṣat thread `E-6sDghh7XE`. They are login-gated, so a human
has to fetch them. Fallbacks: the Sabhā's postal address, Medha Gurukulam
(they teach to this syllabus), and Indica.

---

## Sources

Registered with tier and licence in `darshana_sources.json`. Summary of what
survived checking:

| Tier | Source | Note |
|---|---|---|
| **ready** | **GRETIL** | The one substantial machine-readable Nyāya + Mīmāṃsā corpus. IAST, not Devanagari — transliteration is a pipeline step. This repo already had a GRETIL importer to extend. |
| ready | SanskritDocuments | Small (Tarkasaṅgraha only) but clean ITRANS. Licence requires attribution + backlink; email before bulk use. |
| images | OPenn (UPenn) | Manuscript facsimiles. **The only unambiguously reusable licence here** — Public Domain Mark on images, CC-BY-4.0 on metadata. |
| ocr | KSU / Sambhāṣā | 45 Tarkasaṅgraha-family PDFs, the densest commentary corpus found. Ingest the pre-1930 prints; MLBD/Chowkhamba reprints are likely in copyright. |
| ocr | CSU (sanskrit.nic.in) | Blocked by an incomplete TLS chain, fixable with a CA bundle. Likely born-digital text layers — test `pdftotext` before committing effort; if so it moves to **ready**. |
| ocr | archive.org / DLI | Where the Pañcalakṣaṇī-class scans actually live. |
| blocked | tarkasangraha.com | Unbuilt shell. No text in the served HTML, no per-section URLs, "under initial stages of development", all rights reserved. |
| blocked | e-BharatiSampat | robots.txt disallows everything; ids are non-sequential base64 anyway. |
| blocked | Bharatavani | Licence forbids adaptation, translation, alteration and summarization — incompatible with any text pipeline. No Nyāya content regardless. |
| **dead** | epustakalay.com | Domain hijacked; now serves gambling spam. Do not ingest. |

Licensing follows `dge/PROJECT_STATUS.md` convention #5 — absence of a licence
is not permission, and each unlicensed source needs a specific logged decision.

---

## GRETIL ingestion

`importers/darshana_gretil.py` is separate from `importers/gretil.py` because the
śāstra texts are structurally unlike the smṛti/kāvya corpora that module handles.
Those are verse texts with a `// ABBR_canto.verse //` marker on every śloka.
Nyāya and Mīmāṃsā are prose — sūtra, bhāṣya and vārttika running together,
segmented by adhikaraṇa / āhnika / stabaka headings. So the unit is a **section**,
not a verse, and the parser is heading-driven with three fallback patterns.

Text that matches no pattern is **kept and tagged `unsegmented`** rather than
dropped, so a missing pattern shows up as a review item instead of silent data
loss. Each item stores both `sanskrit_text` (Devanagari) and `iast_text` (the
GRETIL original), and the per-file attribution block goes into `source_note` —
GRETIL defers copyright to each contributor, so that block is the licence.

Ten texts are wired: `python importers/darshana_gretil.py --list`.
