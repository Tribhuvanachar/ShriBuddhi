# DGE audit — Sāyaṇa Bhāṣya, and Smṛti commentaries

Measured directly against `github.com/Tribhuvanachar/bhumandala` @ main, 17 Aug 2026.

---

## 1. Is Sāyaṇa's Bhāṣya loaded for the Vedas?

**No. Not one line of it, anywhere in the corpus.**

I searched every `data.json` under `dge/data/vedas/` — 23,479 items across all four
Vedas — for a Sāyaṇa layer under any spelling (`sayana`, `sāyaṇa`, `सायण`). The only
hits were incidental: Russian translation text, and one line in `schemas.json` where
`vedic_text.bhashya[]` is *described* as being for "Sayana, Madhva's Rigbhashya, etc."
The field is defined. Nothing has ever been written into it.

What the Rigveda actually carries today, per mantra:

| Layer | Mantras | Kind |
|---|---|---|
| `elizarenkova` | 10,552 | Russian translation |
| `geldner` | 10,551 | German translation |
| `grassmann` | 10,519 | German translation |
| `griffith` | 10,477 | English translation |
| `oldenberg` | 1,142 | English translation |
| `macdonell` | 416 | English translation |
| **`sayana`** | **0** | — |

So the Ṛgveda is fully covered by five nineteenth- and twentieth-century *Western*
translations and has **no traditional bhāṣya at all**. That is the gap.

And outside the Ṛgveda it is starker — every other Vedic file has zero commentary
*and* zero translation:

| Corpus | Items | Commentary layers |
|---|---|---|
| Ṛgveda Śākala Saṃhitā | 10,552 | 5–6 (all Western) |
| Śukla Yajurveda, Mādhyandina Saṃhitā | 1,975 | none |
| Kṛṣṇa Yajurveda, Taittirīya | ~3,100 | none |
| Sāmaveda Kauthuma (Pūrva + Uttarārcika) | 1,875 | none |
| Atharvaveda Śaunaka Saṃhitā | 5,777 | none |
| Every Brāhmaṇa, Āraṇyaka, Upaniṣad folder | 0 | — (folders are stubs) |

Sāyaṇa wrote on nearly all of that — Ṛgveda, Taittirīya Saṃhitā/Brāhmaṇa/Āraṇyaka,
both Yajurveda śākhās, the Sāmaveda, the Atharvaveda, the Aitareya and Kauṣītaki
Brāhmaṇas. Loading him is the single largest content upgrade available to DGE.

### What I could not find, and what I did

There is **no full machine-readable Sanskrit text of the Ṛgveda-bhāṣya** on the open
web. Everything is page scans (archive.org has several complete sets) and Devanagari
OCR is not good enough to ingest unreviewed. I checked GRETIL, sanskritdocuments,
GitHub and the Cologne resources; none has it.

What *does* exist, complete and aligned mantra-by-mantra, is **Sāyaṇa's commentary as
rendered in H. H. Wilson's edition (1850–66)**, digitised by wisdomlib.org under the
heading `Commentary by Sāyaṇa: Ṛgveda-bhāṣya` on each of the 10,552 mantra pages.
That is what the importer in this package pulls. It is English, it is Sāyaṇa's
substance rather than his Sanskrit, and it is public domain twice over.

**A useful accident:** wisdomlib's page IDs for that book turned out to be perfectly
contiguous — one page per maṇḍala, per sūkta, per mantra, in order. I generated the
complete 10,552-entry URL map from DGE's *own* sūkta/mantra counts and verified it
against eight independently observed maṇḍala page IDs and three mantra anchors
(1.1.1 = doc828866, 1.164.1 = doc830744, 10.191.1 = doc840450). All exact. So the
import needs no crawl at all — `rigveda_docmap.json` ships with the package.

### Sāyaṇa, elsewhere in DGE

Sāyaṇa (as Sāyaṇa-Mādhava) also wrote the **Parāśara-Mādhavīya**, the standard
commentary on the Parāśara Smṛti — and that one *does* exist as Sanskrit e-text
(five volumes, UT-Austin transcription of the 1893 Bombay Sanskrit Series). It is
wired into the smṛti importer. Two different Sāyaṇa layers, one import run.

---

## 2. Do Manu, Parāśara and the other Smṛtis have their commentaries?

**Correction, issued after the first audit pass:** I originally counted *items*
in these files — which are adhyāyas, not verses — and reported the mūla as
missing. It isn't. Count the ślokas nested inside `items[].shlokas[]` and five
smṛtis turn out to hold **complete mūla Sanskrit, 7,444 verses in all**. What is
missing is every layer on top of it.

| Folder | Adhyāyas | Verses | With Sanskrit | Translation | Commentary |
|---|---|---|---|---|---|
| `manu_smriti` | 12 | **2,685** | 2,685 | 0 | 0 |
| `vishnu_smriti` | 97 | **2,363** | 2,363 | 0 | 0 |
| `yajnavalkya_smriti` | 3 | **1,011** | 1,011 | 0 | 0 |
| `narada_smriti` | 19 | **805** | 805 | 0 | 0 |
| `parashara_smriti` | 12 | **580** | 580 | 0 | 0 |
| `angiras`, `apastamba`, `atri`, `brihaspati`, `daksha`, `gautama`, `harita`, `likhita`, `pracetas`, `samvarta`, `shankha`, `shatatapa`, `ushanas`, `yama` | 0 | **0** | — | — | — |
| `mitakshara`, `dayabhaga`, `dharma_sindhu`, `nirnaya_sindhu`, `smriti_chandrika`, `kalpataru`, `chaturvarga_chintamani` | 0 | **0** | — | — | — |

So the smṛti job splits in two. For those five: **translation and commentary
only — do not touch the mūla.** For the other twenty-one: everything, from
nothing. `import_smriti.py` writes through `merge_into_existing()`, which never
replaces an existing `sanskrit_text` and refuses to write at all if a grantha's
verse count would drop.

Not one `bhashya[]` array is populated anywhere in `smriti_dharma/`, and not one
`artha`, though the schema has supported both from the start.

### What the importer can fill, and from where

Everything below was verified by fetching a real page from each source.

| Text | Mūla | Commentary / translation | Rights |
|---|---|---|---|
| **Manu** | GRETIL (IAST) | **Medhātithi's Manubhāṣya**, tr. Ganganath Jha 1920 — full English, verse by verse, on wisdomlib; plus Bühler SBE 25 | public domain |
| Manu (Sanskrit commentaries) | — | **Medhātithi, Kullūka, Govindarāja** — UT-Austin/Olivelle transcriptions, Google Docs, CC BY 4.0 | clean |
| **Parāśara** | GRETIL (Islāmpurkar 1893) | **Parāśara-Mādhavīya of Sāyaṇa-Mādhava**, 5 vols, Sanskrit | public domain |
| **Yājñavalkya** | GRETIL | **Mitākṣarā** (Sanskrit, standalone) and **Viśvarūpa's Bālakrīḍā** | public domain |
| Yājñavalkya (English) | — | Mitākṣarā + Vīramitrodaya, tr. Gharpure — on wisdomlib | ⚠️ 1936, **flagged** |
| **Nārada, Bṛhaspati** | — | Jolly, SBE 33 (1889), sacred-texts | public domain |
| **Viṣṇu** | GRETIL | Jolly, SBE 7 (1880), sacred-texts | public domain |
| **Gautama, Āpastamba** | GRETIL | Bühler SBE 2 (1879); **Haradatta's Mitākṣarā and Ujjvalā** in Sanskrit | public domain |
| **Vasiṣṭha, Baudhāyana** | GRETIL | Bühler SBE 14 (1882) | public domain — *new folders* |
| **Smṛticandrikā, Caturvargacintāmaṇi** | UT-Austin Sanskrit | — | public domain |
| **Dāyabhāga** | — | Colebrooke 1810 English, archive.org OCR | public domain |
| **Kṛtyakalpataru** | UT-Austin Sanskrit | — | ⚠️ GOS 1941–53, **flagged** |

Rights-flagged layers are in `sources.json` but **skipped by default**; pass
`--include-encumbered` once you've made the same case-by-case call you made for the
ashtadhyayi.com data.

### The honest gaps

Two things genuinely have no digital source, and I'd rather say so than paper over it:

1. **The eleven minor smṛtis** — Aṅgiras, Atri, Dakṣa, Hārīta, Likhita, Pracetas,
   Saṃvarta, Śaṅkha, Śātātapa, Uśanas, Yama. Scans only (the *Smṛti Sandarbha* set,
   and an archive.org "18 Smṛtis" collection). Devanagari OCR from those is not
   ingestible without human review. One untested lead: **sa.wikisource.org**, which
   is CC BY-SA and has a clean API — it was unreachable from this sandbox but should
   be tried from Actions. That is the single check that could close this gap.
2. **Manu's other commentators** — Rāghavānanda, Nandana, Rāmacandra,
   Sarvajñanārāyaṇa: no e-text anywhere, only Mandlik 1886 scans.
   Same for the full Sanskrit Vīramitrodaya, Nirṇaya Sindhu and Dharma Sindhu.

---

## 3. What lands where

Nothing needs a schema change. `vedic_text.bhashya[]`,
`smriti_dharmashastra_text.shlokas[].bhashya[]` and `.artha` already exist.

- Sāyaṇa goes into `items[].commentaries.sayana` on the ten Ṛgveda maṇḍala files —
  the same dict `core.js` already reads for Griffith and Geldner, so it renders with
  no app change (a label patch is in `patches/`).
- Smṛti commentaries go into `items[].shlokas[].bhashya[]`. These **will not render
  until** the four-line `core.js` fix in `patches/core-js-labels.md` is applied — the
  nested-śloka branch of the normaliser currently hard-codes `commentaries: {}` and
  throws them away. That same fix also unblocks the Itihāsa/Gītā commentary import.
- `patches/taxonomy_patch.py` adds the two new Dharmasūtra folders.
