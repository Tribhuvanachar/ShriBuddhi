# Gap report — vishvAsa GitHub corpus vs the DGE library

*Prepared 3 Sep 2026 (IST). Method: blobless clones of the 13 text-bearing
repos of [github.com/vishvasa](https://github.com/vishvasa) (30 repos total;
the rest are tooling, notes, images, website), tree listings of their
markdown content files, compared against `dge/data/library.json`
(1,622 grantha files). File counts below are `.md` content files in the
source and grantha `data.json` files on our side — coarse but honest
proxies for depth.*

Everything of vishvAsa's we already hold (Rāmānujīyam, Śatapatha-brāhmaṇa
kāṇḍas with Sāyaṇa + Eggeling) was taken **with Vishwas Vasuki's
permission on a non-commercial, educational basis** — that precedent, not
a blanket licence, is what any further import rides on, and each new
import should be re-flagged in `admin/config/library-status.json` the same
way.

## The one-paragraph verdict

The Mādhva śāstra repo (`mAdhvam`) — the obvious first candidate — turns
out to be almost entirely **overlap**: of its ~30 tattva-granthas, all but
a handful are already in our library from dvaitavedanta.in, usually at
comparable or better depth. The real gaps are elsewhere: **the Vedic
saṁhitā/brāhmaṇa corpus** (their four Veda repos hold ~15,000 content
files against our 162), the **Kumbhakonam recension of the Mahābhārata**
with Nīlakaṇṭha's commentary, **Govindarāja's Rāmāyaṇa-bhūṣaṇa**, the
**Mīmāṁsā adhikaraṇa corpus**, and the **smṛti/nibandha library**. Those
are foundations a Mādhva digital library cites constantly and we barely
hold.

## 1. `mAdhvam` — mostly held already

| vishvAsa (tattvam/) | files | DGE holding |
|---|---|---|
| madhvaH/anu-vyAkhyAnam | 1,980 | ✔ `sutra_prasthana/anuvyakhyana` (DV, with Nyāya-sudhā stitched) |
| madhvaH/10-prakaraNAni | 669 | ✔ all 10 prakaraṇas (SarvaMūla + DV layers) |
| madhvaH/bhAShyam | 267 | ✔ `brahma_sutra_bhashya` |
| vyAsa-tIrthaH/tAtparya-chandrikA | 506 | ✔ `tatparya_chandrika` |
| vyAsa-tIrthaH/nyAyAmRtam, tarka-tANDavam, bhedojjIvanam | 368 | ✔ all three |
| jaya-tIrthaH/pramANa-paddhatiH, vAdAvalI | 221 | ✔ both |
| vAdirAjaH/yukti-mallikA | 151 | ✔ `yukti_mallika` |
| satya-pramodaH, satya-dhyAna-tIrthAH, vijayIndra, padma-nAbhaH… | ~250 | ✔ maṇḍana/khaṇḍana works all present |
| madhvaH/dvaita-dyumaNiH | 173 | ✔ `dvaita_dyumani` |

**Genuinely absent, small:** Jagannātha's Sūtra-dīpikā (~10 files),
Rāghavendra's Nyāya-muktāvalī (~9), the vAda-vArtA debate records
(Akṣobhya–Vidyāraṇya, śāṅkara-khaṇḍana, ~10), viShNu-pAramyam notes.
Worth a single small import pass someday; not a priority. The repo's
`kriyA/` (Mādhva ritual, Tantra-sāra-saṅgraha paddhati material, ~18
files) may interest the āchāra section.

## 2. The four Veda repos — the largest real gap

| Corpus | vishvAsa | DGE |
|---|---|---|
| Taittirīya saṁhitā (with svara, Sāyaṇa-vibhāga layout) | 1,584 | 7 files |
| Taittirīya brāhmaṇa / āraṇyaka / kāṭhaka sections | 1,121 | 2 files |
| Taittirīya sūtram (Āpastamba etc. kalpa) | 3,734 | none |
| Maitrāyaṇī saṁhitā | 771 | 1 file |
| Vājasaneyi Kāṇva saṁhitā | 406 | 1 file |
| Vājasaneyi Mādhyandina saṁhitā (+ visvarā) | 104 | 1 file |
| Īśāvāsya with commentary corpus | 97 | 2 files |
| Kāṭhaka āraṇyaka, visvara-saṁhitā, aśvamedha material | ~190 | 3 files |
| Ṛgveda Śākala saṁhitā (per-sūkta) | 2,226 | 10 files |
| Aitareya brāhmaṇa | 532 | ~2 files |
| Śāṅkhāyana/Kauṣītaka (Bāṣkala) | 145 | none |
| Jaiminīya brāhmaṇa | 1,120 | 3 files |
| Kauthuma saṁhitā/gāna/padapāṭha/sūtram | ~400 | ~11 files |
| Tāṇḍya (Pañcaviṁśa) + Chāndogya corpus | ~530 | ~9 files |

Our Vedas branch is mostly single-file editions; theirs is per-sūkta /
per-anuvāka with svara and commentary layers. **Śatapatha (707 files) is
the one place we already match them — because we imported it from them.**
The same importer pattern (markdown tree → kāṇḍa/adhyāya units, mūla +
commentary layers) extends directly; Taittirīya saṁhitā and Ṛk saṁhitā
are the two I'd take first — they are what Mādhva commentaries cite on
every page, and our Rig-bhāṣya (SarvaMūla) currently floats with no full
saṁhitā under it.

## 3. Itihāsa — editions we lack

- **Mahābhārata (`mahAbhAratam/vyAsaH`)**: Kumbhakonam recension (~2,600
  files — the southern text the Mādhva tradition reads), Nīlakaṇṭha's
  Bhārata-bhāva-dīpa (~1,800), BORI/Sukthankar critical text (~1,500),
  śloka-level Bhagavad-gītā-parva (1,203). We hold 3 layers per parva
  (mūla + Kannada + one more). The Kumbhakonam pāṭha + Nīlakaṇṭha are the
  high-value adds; they'd slot into the existing parva tree as layers.
- **Rāmāyaṇa (`rAmAyaNam/vAlmIkIyam`)**: Govindarāja's Bhūṣaṇa
  (754 + 446 IITK files), the audīcya TīkA corpus (1,498), Tryambaka's
  Dharmākūta (14). We hold 2–3 layers per kāṇḍa, no southern
  commentary. Govindarāja first.

## 4. Bhāgavata — verify before importing

`purANam_vaiShNavam/bhAgavatam` carries **madhva-tAtparya-nirNayaH/
sarva-prastutiH (361 files)** — mūla with the Bhāgavata-tātparya
interleaved. We already hold `bhagavata_purana_madhva` (12 skandha
files). Before any import, diff a skandha against ours: if theirs is
per-adhyāya with tātparya inline and ours is coarser, replace/upgrade;
if same source, skip. The Gauḍīya prastuti layers there are out of scope
for us.

## 5. Mīmāṁsā, smṛti, pañcarātra — supporting śāstra

- **`mImAMsA`**: the 12-adhyāya corpus (579 grantha files — sūtra with
  bhāṣya/adhikaraṇa apparatus) + saṅkarṣa-kāṇḍa. Our whole Mīmāṁsā
  section is 20 files. Jaya-tīrtha and Vyāsa-tīrtha argue against and
  through Mīmāṁsā constantly; this is the natural next darśana import.
- **`kalpAntaram/dharmaH`**: Manu (150), Yājñavalkya (197), Viṣṇu-smṛti
  (102), Smṛti-candrikā (300), Dharma-sindhu-sāra (720),
  Kṛtya-kalpataru (146). Our smṛti section: 26 files. Smṛti-candrikā
  (Devaṇṇa-bhaṭṭa, South-Indian standard) is the best fit for our
  readers.
- **`AgamaH_vaiShNavaH/pAncharAtrAgamaH`**: Bhāradvāja-saṁhitā (23),
  Hayaśīrṣa Ādi-kāṇḍa (14), Prakāśa-saṁhitā (22), Kriyā-sāgara
  nitya-karma (17). Their Pādma-saṁhitā overlaps the one we already
  imported. Hayaśīrṣa-pañcarātra is dear to the Mādhva tradition
  (Hayagrīva) — small and worth it.
- **`purANam` / `purANam_vaiShNavam`**: mostly thin per-purāṇa trees like
  ours; Sūta-saṁhitā and the Harivaṁśa material are the notable extras.
  Low priority.

## 6. Not worth importing

`tipiTaka`/`pALi` (out of tradition), `english`/`bhAShAntaram`/`notes`
(personal notes), `kannaDa` (his Kannada notes, not Dāsa-sāhitya),
`jyotiSham` (thin), `AgamaH_shaivaH`/`shAktam` beyond what we hold
(deliberate scope choice), `book-pub`/`image-pub`/`devaH`/`sanskrit`
(tooling/assets), `kAvyam` (laxaNam/laxyam teaching notes — our
kāvya-alaṅkāra section is sourced elsewhere).

## Suggested order, if the lead approves further imports

1. Taittirīya saṁhitā + brāhmaṇa/āraṇyaka (foundations; biggest gap).
2. Ṛgveda Śākala saṁhitā per-sūkta (under our SarvaMūla Rig-bhāṣya).
3. Mahābhārata Kumbhakonam pāṭha + Nīlakaṇṭha as parva layers.
4. Mīmāṁsā 12-adhyāya corpus.
5. Govindarāja's Rāmāyaṇa-bhūṣaṇa.
6. Bhāgavata tātparya prastuti (after the overlap check in §4).
7. Small passes: Hayaśīrṣa/Bhāradvāja saṁhitās, Smṛti-candrikā, the
   `mAdhvam` leftovers (Sūtra-dīpikā, Nyāya-muktāvalī, vāda-vārtā).

Each import goes with a fresh permission note in `library-status.json`
per the Rāmānujīyam/Śatapatha precedent.
