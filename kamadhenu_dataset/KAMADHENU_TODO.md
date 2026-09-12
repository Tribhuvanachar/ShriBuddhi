# KAMADHENU — master TODO (dependency-ordered)

Regenerate every number quoted here with `python3 tools/kamadhenu_audit.py`; open `KAMADHENU_STATUS.html` for live state.
Legend: **[Claude]** = Claude Code does it automatically · **[You]** = needs the project lead (or a Sanskrit reviewer) · **[Both]** = you decide/provide, Claude executes.

## P0 — DO FIRST (everything below depends on these)

1. **Decide the Kamadhenu voice.** [You] — file: this doc / `WHAT_I_NEED_TO_DO.md` §A. Output: a name + consent for the reciter whose voice Kamadhenu will clone. Nothing in the fetched 22 h carries speaker metadata; Vāgdhenu's voice is Prof. Prathosh's own and cannot be reused for DGE.
2. **Unblock the 4 blocked sources.** [You] — `external_audio_sources.json` lists them: 3 Drive folders (share as "Anyone with the link" or unzip into `kamadhenu_dataset/incoming_audio/<name>/`), 1 Drive file, and download both YouTube tracks with `yt-dlp -x --audio-format wav` into `incoming_audio/youtube/`. Output: the Tīrthaprabandha (287) and stotra recordings appear in `audio_inventory.json` after the next run.
3. **Confirm the 'vsn' series** (106 files, `drive/Audio*`). [You] — now mapped to the imported Viṣṇu Sahasranāma (stotram verse N ↔ `vsn1.N`) at 0.55 confidence; listen to two files and confirm, then Claude raises them to verified. Output: 106 files leave the review queue.
4. **Work the review queue** (405 files, all Bhagavad Gītā at 46–120 s per verse — 5–8× a single rendition). [You, ~2 h] — file: `audio_text_mapping_review.html`. For each adhyāya folder, listen to 2 files and tell Claude what they contain (verse chanted N times? verse + meaning? teacher–student call-and-response?). Output: Claude writes a segmentation rule (or a per-folder note) and the queue collapses.
5. ~~**Extend the DGE Chandas engine**~~ ✅ done 6 Sep 2026 — vipulā classes, generic upajāti mixes, ardhasama splitting, Indic-script input, `tests/test_chandas_engine.py` + `tests/test_chandas_examples.py`; non-MBTN unknowns 579 → 384 (`chandas_comparison.md` §3). Remaining unknowns are text defects and metres the DB lacks: Gemini brief at `data/vedanga/chandas/GEMINI_CHANDAS_TASK.md`.
6. **Fix the 5 broken verse-audio links on the live site** [Both] — `fetch_manifest.json` status=failed: `smv5.8`, `smv5.14`, `smv5.16` (jsDelivr 404), `rv02.54`, `rv10.06` (archive.org 404); and the **23 pairs of byte-identical Sumadhva Vijaya files** (`audio_inventory.json` exact_duplicates, e.g. smv1.12 = smv1.16) — the player currently serves the wrong verse's audio for one of each pair. Output: corrected files in `bhumandala-audio-data` (you upload; Claude lists them).

## P1 — AFTER P0

7. **Human-verify the 38 structurally safe reference candidates** [You, ~1 h] — `reference_bank.html`: play the best file, confirm it speaks exactly the text shown, mark `verified: true` in `mapping_overrides.json` (Claude will pre-fill the file with the 38 entries on request). Output: `3b_reference_human_verified` in `chandas_coverage.json` rises from 0.
8. **Record the P0 reference set** [You] — `RECORDING_REQUESTS.csv` rows marked P0 (17 texts: इन्द्रवंशा, पृथ्वी, भुजङ्गप्रयात, मन्दाक्रान्ता, शिखरिणी, स्रग्धरा, हरिणी — the core metres whose only audio is 11 kHz/16 kbps or hot-peaked). 48 kHz / 24-bit WAV, one clean take each, into `incoming_audio/reference_takes/`. Output: grade-A references for the long metres.
9. **Add missing texts to DGE** [Both] — Hari Vāyu Stuti (41 verses, sragdharā; 12 pāda-level recordings already waiting), Bhāgavata Sāroddhāra (436 recordings waiting, 128 min), Prātaḥ Saṅkalpa Gadya. You provide/point to a clean source; Claude imports via the normal library pipeline. Output: `unmatched_audio` drops by ~450 files.
10. **Port the 4 text fixes into `tools/kamadhenu/texts.py` + unit tests** [Claude] — `frontend_gap_report.md` §"What Kamadhenu should do" items 1 and 3. Output: `kamadhenu_frontend.py`, tests green.
11. **ASR verification pass** [Claude, needs ~700 MB download + CPU hours] — IndicConformer ONNX (`genie_asr_benchmark/ai4bharat_local/infer_ctc.py` already runs it) over `dataset_verified`; compare phonetic keys with the mapped text. Output: `asr_check` column in `metadata.jsonl`; mismatches → review.
12. **Measure the real sec/syllable per metre** [Claude] — from verified clips, replacing Vāgdhenu's 0.26–0.44 band in `mapping.py`. Output: `pace_by_chandas.json`.

## P2 — AFTER P1

13. ✅ (deployed 6 Sep 2026, live on ZeroGPU; baseline measurement started) **Deploy the Kamadhenu Space and run the Stage 1 baseline on it** [Both] — no CUDA machine needed: Dr. Prathosh's own demo runs on a free Hugging Face **ZeroGPU** Space, and we copy that (`DEPLOYMENT_REFERENCE.md`). Account done: HF user `SarvamulaOrg` (6 Sep 2026; PRO enabled the same evening, so ZeroGPU hosting is allowed now). You: create a *write* token there, add it as the GitHub secret `HF_TOKEN`, run the `Deploy — Kamadhenu Space` workflow, then set Hardware → ZeroGPU on the Space; Claude sets `appConfig.kamadhenuSpaceUrl = https://sarvamulaorg-kamadhenu.hf.space`. Claude: `python3 tools/kamadhenu/space/measure.py <space-url>` → `space_measurements.json` (GPU s per verse per metre, cold start) and the 5-verse compare. Output: a working `/synthesize` endpoint + measured numbers; **no GPU VM is rented** until those numbers say Mode 2 demand needs one.
14. **Pāda-split reference texts in DGE** [Both] — for the 38+ reference verses store 4-line pāda text (human-checked) so `chandas.js toPadas()` never has to guess. Output: `pada_split` field on those units.
15. **Speaker-attributed dataset** [Both] — once the voice is decided, tag every clip `speaker = <name>|other`; `dataset_training` is rebuilt from the Kamadhenu voice only. Output: subsets recomputed.
16. **Player timing JSON** [Claude] — forced alignment (MFA or CTC segmentation) on verified clips → `ARCHITECTURE.md` §player format. Output: `timings/<audio_id>.json`; `audio.js` word-sync stops being an estimate.

## P3 — OPTIONAL / LATER

17. Vedic svara track (Stage 6) — nothing until Stages 1–5 exist.
18. Prosody bank (`extract_prosody.py` port) — after Stage 2.
19. Record the P2/P3 metres in `RECORDING_REQUESTS.csv` (rare vṛttas) — only if a grantha in those metres is scheduled for rendering.
20. LUFS loudness + a browser recorder at 48 kHz/24-bit (adapt `admin/js/genie-asr-recorder.js`, currently 16 kHz) — nice to have.

## Training readiness (do NOT train yet)

| stage | data required | data available now | missing | engineering | status | next step |
|---|---|---|---|---|---|---|
| 1 Basic Sanskrit TTS baseline | any clean Sanskrit voice + reference | Vāgdhenu weights (public, HF) + its 16-metre bank; 1,576 structurally verified DGE-text clips (lossy) | a free HF account to host the ZeroGPU Space (no GPU host) | Space scaffold + client written (`tools/kamadhenu/space/`, `js/kamadhenu.js`); measure script ready | 🟡 READY TO DEPLOY | P2 #13 |
| 2 Speaker adaptation | ≥30–60 min clean single-speaker clips with exact text, 24 kHz+ | 0 min attributed to a decided speaker; 22 h unattributed, 41% at 11 kHz/16 kbps, 20% clipped | the voice decision; 48 kHz masters; speaker tags | fine-tune script exists (Vāgdhenu `training/`) | 🔴 BLOCKED | P0 #1, then P1 #8 |
| 3 Chandas-aware reference selection | ≥1 verified reference per metre used | 38 structural candidates, 0 verified, 218 metres with no audio | human verification; long-metre clean takes | `reference_bank.py` done; bridge to Vāgdhenu `--meter` | 🟡 PARTIAL | P1 #7 |
| 4 Prosody improvement | aligned clips with F0/duration per akṣara | none aligned | MFA/CTC alignment | port `extract_prosody.py` | 🔴 NOT STARTED | after Stage 2 |
| 5 Explicit duration/prosody | Arch-B (duration predictor) — Vāgdhenu found text-side conditioning inert | — | different architecture | research | 🔴 NOT STARTED | do not attempt |
| 6 Vedic svara | accented recordings + accent annotation | Vedic text corpus only, marks stripped by every path | everything | new track | 🔴 NOT STARTED | do not attempt |
