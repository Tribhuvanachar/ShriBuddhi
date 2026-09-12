# Experiment A — cost card (IndicF5 fine-tune on the pilot set)

Generated 7 Sep 2026, 5:58 PM IST by `kamadhenu/training/dry_run.py` from the CPU dry run. **Nothing has been launched.** This card is for the project lead's approval; the launcher (`kamadhenu/training/launch_experiment_a.sh`) needs a rented GPU box and `HF_TOKEN`, and is not run by Claude without a written go-ahead.

## What would run

- **Base**: `ai4bharat/IndicF5` (MIT), code at commit `13f7c4d627` — the same weights and code the Space serves.
- **Data**: 123 verses of the lead's recitation, 35.1 min at 24 kHz (grade A, metre named, full verse), 13 held out; 15 metres; 14,213 characters, all in IndicF5's vocabulary.
- **Recipe**: `finetune_cli.py`, lr 1e-05, 3,000 target updates (warm-up 300), batches by frames (the trainer's own sampler), fp16, checkpoint every 500 updates, wall-clock cap 150 min, resumable.
- **Output**: `model.safetensors` (EMA) + `model_online.safetensors` in IndicF5's own format, plus 13 A/B renders (base zero-shot vs fine-tuned, same reference clip, same seed) and their duration ratios.

## Size of the run (from the dry run's batch simulation)

| VRAM class | frames/batch | batches/epoch | epochs | updates | padding efficiency |
|---|---|---|---|---|---|
| 16GB | 2,000 | 121 | 25 | 3,025 | 1.0 |
| 24GB | 3,200 | 90 | 34 | 3,060 | 0.999 |
| 40GB | 6,400 | 36 | 84 | 3,024 | 0.992 |

## Time and money (planning assumptions, ±2×)

Assumed seconds per update are scaled from community F5-TTS fine-tune reports, not measured on this data; the trainer's progress bar in `ckpt/train.log` shows the real rate within the first minutes — stop the run there if it projects past the cap (the config's wall-clock cap stops it regardless, and a re-run resumes). Rates are on-demand marketplace prices to verify at booking; ₹ at 88/USD. Every total includes 20 min of setup and 8 min of evaluation renders.

| GPU | s/update (assumed) | training | total | USD | ₹ | ₹ cap (×2) |
|---|---|---|---|---|---|---|
| T4 16 GB | 2.5 | 126 min | 2.57 h | 0.51–1.03 | 45–90 | **181** |
| L4 24 GB | 1.4 | 71 min | 1.66 h | 0.66–0.99 | 58–87 | **175** |
| A10G 24 GB | 1.1 | 56 min | 1.4 h | 0.7–1.05 | 62–93 | **185** |
| RTX 4090 24 GB | 0.6 | 31 min | 0.98 h | 0.34–0.68 | 30–60 | **120** |
| A100 40 GB | 0.7 | 35 min | 1.05 h | 1.05–1.58 | 93–139 | **278** |

## Recommendation

- **Card**: a 24 GB class (L4 / A10G / RTX 4090). Point estimate on the cheapest, RTX 4090 24 GB: about ₹30–60; **approve a cap of ₹185** (the wall-clock cap in the config enforces it; a re-run resumes, it never restarts).
- **Not** a T4: 16 GB halves the batch and the assumed rate is 2× slower, so it costs about the same for a worse gradient.
- **Not** ZeroGPU: the Space's 60 s GPU slices cannot hold a training loop; it serves the result instead.
- **Go / no-go after the run**: the 13 held-out verses at a median duration ratio inside 0.75–1.25 (zero-shot clip D ran ~1.65×) AND the lead judging the words intelligible in his voice → Phase 12 continues with the full grade-A set (6.5 h). Otherwise the ₹ is the price of knowing that the pilot set is too small, and the next lever is more data, not more steps.

## What the dry run verified on CPU

- metadata.csv: 123 rows, F5 reader rules (utf-8-sig, `|`, header) — ok
- duration.json: aligned with metadata.csv
- vocab.txt: 2545 entries, space at index 0, sha1 b46bed8e96… (IndicF5's, verified against the Hub at launch)
- vocab coverage: every character of every text is in the vocab
- audio: all 24000 Hz mono, 4.0–45.0 s, peaks at -3.0 dBFS, 0 files with clipping
- raw.arrow: 123 rows, columns ['audio_path', 'text', 'duration'] — loads with `datasets`
- batch sampler: simulated with the trainer's DynamicBatchSampler rules for 16/24/40 GB
- torch / GPU: not installed here — model construction, the checkpoint conversion and the training step are exercised only by the launcher's --dry-run on the GPU box

Warnings (3, none blocking):

- km_40b0294e290e: edge silence 1.302/0.099 s
- km_8c8d3b869852: edge silence 1.003/0.034 s
- 16GB: 2 sample(s) longer than one batch (21.3 s) would be dropped by the sampler

## Decision

- [x] Approved by the project lead: 7 Sep 2026, 6:20 pm IST — cap ₹185, 24 GB class. Run on a Hugging Face Job (`l4x1`, $0.80/h, job timeout 150 min → worst case ₹176; training loop capped at 100 min inside it) via `.github/workflows/kamadhenu-experiment-a.yml`.
- [ ] Declined / changes requested: ______

## Data caveat added 8 Sep 2026, 12:45 am IST

A Whisper cross-match of the 136 pilot recordings against every verse of their works
(`kamadhenu/reports/pilot_transcript_check/crossmatch.md`) found 38 recordings (28 %) carrying a different
verse from the text they were trained on (all 10 Tīrtha Prabandha files one prabandha off; 28 Bhāgavata
Saroddhāra files one or two verses off or in the next part) and 5 the ASR could not settle. Attempt 4 was trained before this
check existed. Treat its outputs as proof of the pipeline, not of the recipe; the rerun exports with
`--require-verified crossmatch.json --accept-remap`.
