# KAMADHENU_STATUS

Updated 7 Sep 2026, 10:50 pm IST. Legend: 🟢 DONE · 🟡 PARTIAL · 🟠 IN PROGRESS · 🔴 BLOCKED · ⚪ NOT REQUIRED

CURRENT PHASE: 12 Experiment A DONE (attempt 4, bf16, 9:56 pm IST) — the lead listens to the 13 A/B pairs; total spend ≈ ₹154 of the ₹185 cap

COMPLETED:
- 🟢 Phase 0 audit — `kamadhenu/KAMADHENU_AUDIT.md`
- 🟢 Phase 1 audio inventory — `kamadhenu/data/audio_inventory.csv` + `docs/AUDIO_INVENTORY.md` (3,892 files, 37.83 h; pairs ≥0.9: 2,530 = 11.0 h; usable now 1,721 = 6.5 h)
- 🟢 Phase 2 DGE data located — `kamadhenu_dataset/metadata.jsonl` / `text_index.json`; Sāroddhāra recordings now mapped (364 of 436, grade A)
- 🟢 Phase 3 schema — `kamadhenu/data/schema/kamadhenu_schema.json`, `docs/KAMADHENU_DATASET.md`
- 🟢 Phase 4 validator — `kamadhenu/scripts/kamadhenu_validate_dataset.py` → `kamadhenu/reports/kamadhenu_dataset_report.{json,md}`
- 🟢 Phase 5 Chandas — `docs/CHANDAS_FOR_KAMADHENU.md` (DGE engine is the analysis layer; 8-akṣara sama metres fixed today)
- 🟢 Phase 6 pilot — `kamadhenu/data/pilot/{manifest,train,validation}.jsonl`: 136 grade-A examples (126 Sāroddhāra + 10 Tīrthaprabandha), 0.65 h, all speaker 3BHU1, reproducible (`scripts/build_pilot.py`)
- 🟢 Phase 7 model selection — `docs/MODEL_SELECTION.md`: **BASE MODEL = IndicF5 (MIT)**, Vāgdhenu as benchmark
- 🟢 Phase 15 ledger — `docs/INDEPENDENCE_FROM_VAGDHENU.md` · 🟢 Phase 18 — `docs/RECORDING_PLAN.md`
- 🟢 Phase 16 architecture decided AND deployed — ZeroGPU Space live (`kamadhenu_dataset/DEPLOYMENT_REFERENCE.md`, `kamadhenu_dataset/space_measurements.json`)

IN PROGRESS:
- 🟢 **Phase 8 training pipeline scaffold — done 7 Sep 2026, 6:05 pm IST** (`kamadhenu/training/`, README there): text convention (`kamadhenu_text.py` = Vāgdhenu model_text), IndicF5 vocab (2,545, sha1-pinned), exporter to the F5 layout (24 kHz mono wavs at −3 dBFS, metadata.csv, duration.json, vocab.txt, raw.arrow), checkpoint converter both ways (safetensors ⇄ trainer `model_last.pt`), `experiment_a.yaml`, resumable wall-clock-capped launcher, A/B evaluation renderer. **CPU dry run executed on the real pilot audio** (136 files re-fetched from Drive): 123 train verses = 35.1 min, 13 held out, every character in the vocab, arrow loads, sampler simulated (24 GB: 90 batches/epoch × 34 epochs = 3,060 updates). Card: `kamadhenu/docs/EXPERIMENT_A_CARD.md`; numbers: `kamadhenu/reports/experiment_a_dry_run.json`. Not exercised here: torch/GPU (the launcher's `--dry-run` does that in the first 20 min of the budget)
- 🟠 Phase 13 evaluation script + HUMAN_REVIEW.csv — not started

BLOCKED:
- 🟢 Speaker decided 6 Sep 2026: **3BHU1** (the project lead), consent to train the voice given; every one of the 3,892 recordings is attributed to him (`kamadhenu_dataset/speakers.json`)
- 🟡 Drive, evening batch 6 Sep 2026 (+1,173 files, +15.3 h), lead's answers applied 7:00 pm IST: `smv.zip` = 1,106 pāda-level Sumadhva Vijaya takes: 34 named (30 mapped exactly) + 1,058 numbered `New recording N` **identified by local Whisper transcription + the lead's sequential-pāda rule: 909 assigned** (471 at 0.9, 149 at 0.8, 226 at 0.7, 63 interpolated at 0.6) across sargas 10, 11, 14, 16 (+ a few 15/1); **149 need one listen** (`kamadhenu_dataset/smv_takes_listen_list.csv`); 51 dated files are hour-long sessions, not takes. Overrides in `mapping_overrides.json`, evidence in `smv_takes_check.json`; Harikathāmṛtasāra 31 verses — lead confirmed plain full recitations → accepted; Gītā files are pāda-wise with some words repeated (segmentation plan); Vedavyāsa Gadya text imported (Yādavārya, 100 epithet units) → the 9.7-min file needs per-epithet segmentation; **Aṣṭādhyāyī pārāyaṇa (32 files, 3.9 h) is NOT the lead's voice → excluded**; Kṣīrābhiṣeka video ignored; the two private folders were someone else's and are dropped. Earlier gaps stand: Tīrthaprabandha only Dakṣiṇa 1–19; Nāmāvali 110 clips + video have no text in DGE
- 🟢 **Kamadhenu trials page** `kamadhenu.html` (6 Sep, 8:30 pm IST): DGE chandas verdict + two engines side by side — *Kamadhenu trial* = **IndicF5 (MIT) zero-shot prompted with the lead's own recordings** (`tools/kamadhenu/space/refs/`), *Vāgdhenu baseline*. The lead's question answered honestly: the Space's first engine is Vāgdhenu's weights (built on IndicF5), nothing has been trained; the trial engine is the licensed base model in his voice. **Both engines verified live from a GitHub runner at 8:49 pm IST** (Vāgdhenu 9.6 s audio / 4–14 GPU s; IndicF5 zero-shot 11.5 s audio / 13.9 GPU s cold). IndicF5's gate was accepted for SarvamulaOrg by the deploy workflow and the Space holds `HF_TOKEN` as a secret
- 🟢 **Kamadhenu Space LIVE** 6 Sep 2026, 7:36 pm IST — https://sarvamulaorg-kamadhenu.hf.space on ZeroGPU (zero-a10g), deployed by the `Deploy — Kamadhenu Space` workflow (4th run; fixes: huggingface_hub 1.x API, README metadata length). Measured from a GitHub runner: anuṣṭubh verse 9.6 s audio, **4.3 GPU s warm (RTF 0.45)**, 23.2 GPU s on the cold first call. `appConfig.kamadhenuSpaceUrl` set; `js/kamadhenu.js` loaded by the reader (no visible button yet — the "Generate this verse" UI hook is the next step). Diagnostics: `Kamadhenu Space — logs + API probe` workflow
- 🔴 Any GPU training — none approved; none proposed yet
- 🟢 **Zero-shot diagnostics run 7 Sep 2026, 1:24 pm IST** (`Kamadhenu Space — zero-shot diagnostics` workflow, run 34097773688, artifact `kamadhenu-diagnostics`; the Space now has a `/diagnose` endpoint and IndicF5's own model-card prompt clip as a diagnostic reference). Four clips, seed 60, all rendered: A IndicF5 prompt + Hindi 6.17 s (15.98 GPU s cold) · B lead's chant + Hindi 10.19 s · C IndicF5 prompt + Gītā 1.1 6.96 s · D lead's chant + Gītā 1.1 11.51 s. Measured before listening: the same Hindi sentence comes out 65 % longer from the chanted reference (10.19 vs 6.17 s) — the chant clip forces chant tempo on read speech, which is the smearing mechanism. The lead's ear decides A–D; the reading key is in the workflow header. Lead's verdict on the original trial (6 Sep): voice ~70 % similar, words unintelligible.

NEXT ACTION: the lead's verdict on the 13 A/B pairs (attempt 4). If the fine-tuned voice is closer: Phase 13 evaluation sheet, then Experiment B on the full grade-A set (6.5 h) with a fresh cost card; wire `model.wrapper.safetensors` into the Space as a third engine. If not: more data before more steps (the pilot is 35 min of audio).

HUMAN ACTION REQUIRED:
0. **Experiment A ran (approved 6:20 pm IST, cap ₹185, 24 GB).** Four HF Jobs on `l4x1` ($0.80/h): 1 pip conflict (1 min); 2 EMA
   key layout (17 min); 3 trained but fp16 diverged — loss=nan from step 1, NaN weights by step ~320, renders were noise
   (72 min ≈ ₹85); **4 (bf16) healthy**: 3,060 updates in 20.5 min (0.4 s/update), loss 0.73 → window means 0.70/0.69/0.68/0.66,
   no NaN, EMA + online weights exported in both layouts, 13 held-out A/B renders (base zero-shot vs fine-tuned, same
   reference/seed) — real audio (rms ≈ 0.2, base↔fine-tuned correlation 0.01, i.e. genuinely different). Total spend upper
   bound ≈ ₹21 + ₹85 + ₹48 = **₹154** (HF bills RUNNING minutes only). Results: `SarvamulaOrg/kamadhenu-voice-a`
   (export/model.safetensors + model.wrapper.safetensors for the Space, eval/, train.log), GitHub artifact
   `kamadhenu-experiment-a` on run 34139626712 (expires 6 Dec), records in `kamadhenu/reports/experiment_a/`.
   **Lesson**: the duration ratio is not a discriminator for F5 — it fixes the output length from the reference/text
   ratio, so base and fine-tuned are identical on it (0.86 median, 11/13 on tempo); intelligibility is the lead's ear
   (Phase 13 HUMAN_REVIEW.csv next). **Human action**: listen to `eval/<verse>/base.wav` vs `finetuned.wav` vs
   `finetuned_online.wav` for the 13 verses and say which, if any, sounds like you reading intelligible Sanskrit.
1. Where are the other Tīrthaprabandha recordings (only Dakṣiṇa 1–19 were in the shared folder)? If they exist, share that folder too.
2. The Śrīpādarāja Aṣṭottara-śatanāmāvalī text (108 names, Devanagari) — then the 110 clips map by number.
3. **Listen-list for 149 smv takes** — `kamadhenu_dataset/smv_takes_listen_list.csv`: each row gives what Whisper heard, the best guess, and the identified neighbours; fill the last column (sarga.verse.pāda or `skip`). Also spot-check a few of the 63 interpolated ones (confidence 0.6 in `smv_takes_check.json`).
4. ~~`HF_TOKEN`~~ — done by the lead 6 Sep 2026 (verified: the deploy workflow found it).
5. Listen to 2 Gītā + 2 'vsn' files (see kamadhenu_dataset/WHAT_I_NEED_TO_DO.md §A).
6. ~~two private folders~~ — not the lead's; dropped.
7. ~~HKS content~~ — plain full recitation (lead, 6 Sep); accepted.

GPU REQUIRED: none pending. Measured on the L4: 3,060 updates in 20.5 min (bf16); a full-set Experiment B would be ~10× the data → order of 3–4 GPU hours, card to follow.
ESTIMATED COST: Experiment A spent ≈ ₹154 upper bound (four HF Jobs, cap ₹185, approved). No Gemini spend.

## Vedavani (Hugging Face) Rigveda clip corpus — manifest built, audio not yet mirrored (7 Sep 2026, 11:30 pm IST)

- The lead's phone capture (PCAPdroid) shows the VedaVaNi app streaming whole-sukta MP3s from the two
  Cloudflare R2 buckets already handled by `tools/vedavani/extract_audio.py`. The *dataset* the lead's
  ChatGPT thread describes is a different project with the same name: `sanganaka/Vedavani-Dataset`
  (IIT Kharagpur, ACL 2025, arXiv:2506.00145, Apache-2.0). Its audio is Veda Prasara Samiti's complete
  Rigveda / Atharvaveda chanting from archive.org (`RigvedaChanting`, Public Domain Mark), cut by the
  authors into 30,779 clips (20,782 Rigveda, 16 kHz mono WAV, avg 6.4 s, 6.8 GB in all).
- Built `tools/vedavani_hf/vedavani_corpus.py` (`build-manifest`, `verify`, `fetch`, `mirror`) and
  `.github/workflows/vedavani-hf-corpus.yml`. Committed manifest: 20,483 / 20,782 Rigveda clips mapped
  to DGE ṛk ids (exact 18,293, span 437, refrain-resolved 1,110, fuzzy 643; 197 unmatched, 101 too
  short, 1 ambiguous), 10,440 of 10,552 ṛks covered, 36.1 h mapped. The 54 recording groups run in
  text order, so refrains resolve by their neighbours. Three random clips verified from the sandbox
  (HTTP 200, `audio/wave`, RIFF header, size = manifest, sha256 = LFS oid, duration = CSV).
- **Decision for the lead**: mirror the whole dataset into `SarvamulaOrg/vedavani-dataset-mirror`
  (private, HF_TOKEN already in secrets) via the workflow's `mirror` mode, or keep pulling from the
  upstream repo at training time. Audio is never committed to git (2.7 GB repo, 1 GB Pages soft limit).
- Caveats: group recitation (several voices), 16 kHz (IndicF5 trains at 24 kHz), no svara marks in the
  texts, clips are pādas not whole ṛks. Use as a Vedic-accent style reference / ASR test set, not as a
  single-speaker Kamadhenu voice.

## Pilot transcripts checked by ear (Whisper) — a quarter of the pairs were the wrong verse (8 Sep 2026, 12:45 am IST)

The lead asked whether the audio fed to Experiment A carries the text we claim. It did not, for one pair in four.

- Run 1 (`kamadhenu-pilot-transcripts.yml`, Whisper small, 4 CI shards, 23 min): 136 pilot files; the CER
  verdict alone said ok 104 / suspect_repetition 17 / suspect_mismatch 9 / short 6, CER median 0.26.
- The CER only says "expected text not heard". The new cross-match (`verify_pilot_transcripts.py --crossmatch`)
  compares each ASR with *every verse of the same work* (`kamadhenu_dataset/text_index.json`) and says which
  verse the recording actually is. Result on the same run: **confirmed 78 + weak 2 = 80 (59 %), remap 34
  (25 %), inconclusive 22 (16 %)**. 18 of the 34 wrong pairs had passed the CER check as "ok".
- What the 34 wrong pairs are: **all 10 Tīrtha Prabandha files** (`tp1.N`) are Paścima-prabandha verse N,
  mapped as Dakṣiṇa-prabandha verse N — the whole folder is one prabandha off. **24 Bhāgavata Saroddhāra
  files** carry the next verse (+1) or the one after (+2), one carries the previous verse, and two carry the
  same verse number in the next part (P20→P21 V315, P05→P06 V102), so the recorder's numbering drifted at
  several points and the file name (`SBS20.70.SBS306`) was trusted over the content.
- Experiment A attempt 4 trained on these 136 pairs, so at least 25 % of its training text was wrong. Its
  A/B pairs stand, but the model is not a clean measurement of the recipe. Nothing else was spent.
- Gate, now in code: `export_f5_dataset.py --require-verified kamadhenu/reports/pilot_transcript_check/crossmatch.json`
  exports only confirmed pairs (80); `--accept-remap` also keeps the 34 remapped files with the verse actually
  heard as their text (114). The 22 inconclusive files wait for run 2 (Whisper medium, dispatched 12:35 am IST).
- Reports committed under `kamadhenu/reports/pilot_transcript_check/` (small-model run + crossmatch). The CI
  merge job now runs the cross-match itself and uploads it with the report.
- Next: rerun Experiment A on the verified set (needs the lead's cost approval, same ≈ ₹150–185 envelope),
  and apply the same check to the Gītā recordings before they enter any training set.

## Update — Whisper medium run settled most of the rest (8 Sep 2026, 1:55 am IST)

Run 2 (Whisper medium, 4 shards, 69 min) cross-matched and combined with run 1 (`--crossmatch small medium`;
the two runs never named different verses for the same file). Final gate file
`kamadhenu/reports/pilot_transcript_check/crossmatch.json`:

| decision | files | share |
|---|---|---|
| confirmed (+1 weak) | 93 | 68 % |
| remap — recording is a different verse | 38 | 28 % |
| inconclusive | 5 | 4 % |

The 38 remaps: all 10 Tīrtha Prabandha files (Paścima, not Dakṣiṇa) and 28 Bhāgavata Saroddhāra files
(+1 / +2 verses, or the same number in the next part). Export: `--require-verified crossmatch.json` → 93 pairs;
with `--accept-remap` → 131 pairs on the text actually heard. The 5 unresolved (SBS9.5, SBS20.30, SBS1.8,
SBS31.1, SBS1.16) need a human ear; two of them sound like full Bhāgavata verses the Saroddhāra text does not
contain. Attempt 4 therefore trained with **28 % wrong pairs**; the rerun waits on the lead's cost go-ahead.
