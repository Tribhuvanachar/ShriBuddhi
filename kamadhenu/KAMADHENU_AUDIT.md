# KAMADHENU — Phase 0 audit (repository and environment)

Written 6 Sep 2026, 5:20 pm IST, from the files as they are in this repository (`Tribhuvanachar/bhumandala`, branch
`main`). Nothing was modified for this audit. Numbers come from `kamadhenu/data/audio_inventory_stats.json`, which
`kamadhenu/scripts/build_audio_inventory.py` recomputes from the measurements in `kamadhenu_dataset/`.

**Where things live.** Kamadhenu is a sub-project of the DGE repository. Its working files are under `kamadhenu/`
(this audit, the status file, `data/`, `docs/`, `scripts/`). The raw measurements, manifests and the audio drop-zone
made by the earlier master audit stay in `kamadhenu_dataset/` (audio itself is git-ignored). The deployment scaffold
is `tools/kamadhenu/space/`, the analysis toolkit `tools/kamadhenu/`, and the reader-side client `js/kamadhenu.js`.

## 1. What already exists

| area | what | where | state |
|---|---|---|---|
| DGE library | 1,758 granthas as JSON, one item per verse/passage, with a taxonomy and reader | `data/**`, `render.html` | 🟢 live |
| Chandas engine | browser JS metre identifier: syllables, laghu/guru, gaṇas, pāda split, 245 vṛttas + 10 mātrā metres, anuṣṭubh pathyā/vipulā, yati; headless runner for Python | `js/chandas.js`, `data/vedanga/chandas/data.json`, `tools/kamadhenu/chandas_runner.js` | 🟢 tested (81 pytest cases) |
| Sanskrit text processing | speaker-line stripping, verse cleaning, SLP1 + phonetic keys per text unit; Indic-script folding | `tools/kamadhenu/texts.py`, `build_search_index.py` | 🟢 |
| Kamadhenu audit toolkit | inventory → sources → fetch → audio QC → text mapping → chandas → dataset subsets → reference bank → dashboard; one command | `tools/kamadhenu_audit.py`, `tools/kamadhenu/*.py` | 🟢 runs in ~10 s warm |
| Audio measurements | ffprobe/decode of every file: sample rate, channels, duration, peak, RMS, noise floor, SNR, silences, clipping, SHA-1, duplicates, grade A–D | `kamadhenu_dataset/audio_inventory.json/.csv` | 🟢 2,544 files |
| Text↔audio mapping | filename rules + phonetic matching, confidence 0–1, review queue | `kamadhenu_dataset/audio_text_mapping.json`, `metadata.jsonl` | 🟡 1,576 strong, 405 in review |
| Dataset subsets | all / verified / high-quality / reference-bank / training / validation / review / unmatched | `kamadhenu_dataset/subsets/` | 🟡 split made, never trained |
| Reference bank | per-metre best recording candidates, 147 entries, 0 human-verified | `kamadhenu_dataset/reference_bank.*` | 🟡 |
| Chandas coverage | per-metre audio coverage: 37 of 256 metres have any recording | `kamadhenu_dataset/chandas_coverage.*` | 🟢 measured |
| Vāgdhenu comparison | metre tables, frontend, text fixes, licence notes | `kamadhenu_dataset/chandas_comparison.md`, `frontend_gap_report.md` | 🟢 |
| Deployment reference | how Vāgdhenu is really served (ZeroGPU Space), quotas, costs, two-mode architecture | `kamadhenu_dataset/DEPLOYMENT_REFERENCE.md`, `tts/ARCHITECTURE.md` v1.2 | 🟢 |
| Space scaffold | API-first Gradio app, DGE metre → bank map, build/deploy script, GitHub Action, measurement script | `tools/kamadhenu/space/`, `.github/workflows/deploy-kamadhenu-space.yml` | 🟡 not deployed (needs HF_TOKEN; ZeroGPU available now — account PRO since 6 Sep 2026) |
| Reader client | "Generate this verse" call to the Space | `js/kamadhenu.js`, `appConfig.kamadhenuSpaceUrl` | 🟡 not wired to a page |
| Hugging Face account | `SarvamulaOrg`, created 6 Sep 2026 | — | 🟢 |
| Recording plan | 249 targeted recording requests by metre and priority | `kamadhenu_dataset/RECORDING_REQUESTS.csv` | 🟡 nothing recorded yet |
| Older TTS design | v1.0/1.1 architecture document (planning only) | `tts/ARCHITECTURE.md` | reference |
| Audio player | per-verse playback from the DGE audio repo / archive.org | `js/audio.js` | 🟢 live |
| Vāgdhenu code | clone in the session scratchpad only (not in the repo); Apache-2.0 | `$VAGDHENU` | reference |
| Model files | none in the repository | — | ⚪ by design |

Git history for the Kamadhenu files: master audit 5 Sep 2026; Viṣṇu Sahasranāma + 'vsn' mapping, Chandas engine
gap-closure, ZeroGPU deployment reference, Space scaffold and the HF account on 6 Sep 2026.

## 2. What is reusable as-is

* The DGE Chandas engine as the authoritative analysis layer (syllables, laghu/guru, gaṇa, pāda split, metre, yati).
  It already covers 245 vṛttas; nothing needs to be hard-coded.
* `tools/kamadhenu_audit.py` as the data-preparation driver: it is idempotent and re-analyses only new files.
* The measured `audio_inventory.json` (no re-decoding needed) and `metadata.jsonl` (already one record per
  audio file with text, normalised text, metre, laghu/guru, pāda count, yati, quality grade, mapping confidence).
* The Vāgdhenu serving pattern (ZeroGPU Space) and its Sanskrit frontend ideas (pronunciation transforms), under
  Apache-2.0, credited in `THIRD_PARTY_NOTICES.md` of the Space bundle.

## 3. What is incomplete

* Speaker identity: decided 6 Sep 2026 — the Drive recordings and the Narasiṃha files are **3BHU1** (the project lead, consent given, `kamadhenu_dataset/speakers.json`); Sumadhva Vijaya / Rāghavendra Vijaya confirmed as 3BHU1 at 6:35 pm — every recording is his.
* Human verification: 0 reference recordings listened to; the review queue (405 Gītā files, 106 'vsn' files) is
  unanswered.
* 989 Sumadhva Vijaya files are 11 kHz / 16 kbps MP3 and 46 files are byte-identical pairs (wrong verse served).
* 486 Rāghavendra Vijaya files are grade D (clipped / noisy).
* The pilot dataset, validation script, model selection, training pipeline, evaluation, experiments: not started.

## 4. What is missing

* Any recording of 219 of the 256 metres in the database; only 16 metres have good coverage.
* Tīrthaprabandha recordings: the shared folder holds only Dakṣiṇa-prabandha 1–19 (19 files); the ~287 the lead remembers are elsewhere.
* 48 kHz masters of a decided voice; the recording protocol exists, nothing has been recorded to it.
* A pilot model, an evaluation harness, a HUMAN_REVIEW.csv workflow.

## 5. What data we already possess (verified from files)

| | |
|---|---|
| audio files reachable | 3,892 (2.5 GB, git-ignored, re-fetchable with `--fetch`; 16 Drive sources public, 2 still private) |
| total duration | 37.83 h |
| grade A (clean) | 8.78 h · grade A+B 33.12 h · grade C/D/F 4.71 h |
| text↔audio pairs, confidence ≥ 0.7 | 2,472 files, 19.22 h |
| text↔audio pairs, confidence ≥ 0.9 | 2,030 files, 8.95 h |
| **usable for training now** (grade A/B, confidence ≥ 0.9, plausible duration, not a duplicate) | **1,475 files, 6.07 h** |
| pairs with a named metre | 85.4 % of the ≥0.7 pairs |
| pairs with laghu/guru string | 100 % of the ≥0.7 pairs (engine output; the 14.6 % without a metre name still have scans) |
| unmatched audio (no confident text) | 1,420 files (1,072 unnamed `smv.zip` pāda takes, 110 Nāmāvali clips, 34 long-form pārāyaṇa files, the rest as before) |
| sample rates | 48 kHz 2,326 · 44.1 kHz 576 · 11.025 kHz 989 |

Sources: DGE-linked (Sumadhva Vijaya 989, Rāghavendra Vijaya 577, Prahlāda-Narasiṃha 11) 6.9 h; Drive (Bhāgavata
Sāroddhāra 436, Bhagavad Gītā 7 adhyāyas 406, Hari Vāyu Stuti 20, 'vsn' 106, Tīrthaprabandha 21, Prahlāda-stuti 43,
Nāmāvali 110 + video, `smv.zip` pāda takes 1,106, Aṣṭādhyāyī pārāyaṇa 32, Harikathāmṛtasāra 31, Brahmasūtra 2,
Vedavyāsa Gadya 1) 30.9 h.

Caveats the owner should know: the Gītā recordings run 46–120 s per verse (5–8× a single rendition) and must be
segmented before use; the Sāroddhāra recordings (2.1 h, grade A) are the best audio we have and their text was
imported and verified only today; Sumadhva Vijaya is the largest corpus but low-bitrate.

## 6. What data still needs preparation

1. Decide the voice → tag every file `speaker = <name> | other` (P0 in `KAMADHENU_TODO.md`).
2. Listen to 2 Gītā files and 2 'vsn' files and describe them → segmentation rule for 511 files.
3. Human-verify the 38 structurally safe reference candidates (`reference_bank.html`).
4. Share or upload the blocked Drive folders (Tīrthaprabandha).
5. Fix the 46 duplicate / 5 broken files in the audio repo.

## 7. What can be automated (and is)

Inventory, QC, mapping, chandas analysis, subsets, reference-bank ranking, dashboards, deployment of the Space,
measurement of GPU seconds, dataset validation (Phase 4, next), pilot selection (Phase 6), evaluation scripts.

## 8. What requires human action

The five items in §6, the HF write token as a GitHub secret (`HF_TOKEN`), and every paid step (none proposed yet).
