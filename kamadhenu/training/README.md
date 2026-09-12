# Kamadhenu Phase 8 — IndicF5 fine-tune scaffold (written 7 Sep 2026; nothing trained)

Everything needed to run **Experiment A** (Phase 12) is in this directory; what is *not* here is the GPU, the money and
the lead's approval. The CPU dry run has been executed on the real pilot audio; `../docs/EXPERIMENT_A_CARD.md` is
the card to approve or decline.

| file | does |
|---|---|
| `kamadhenu_text.py` | the one text convention (Vāgdhenu `model_text`): daṇḍas/digits dropped, hyphen joins, one space per pāda break; vocab helpers |
| `vocab_indicf5.txt` | IndicF5's character vocabulary (2,545 entries, space at index 0) — copied from Vāgdhenu's public checkout, byte-identical in size to the gated `checkpoints/vocab.txt`; the launcher verifies the sha1 against the Hub before anything else |
| `export_f5_dataset.py` | pilot `train.jsonl` / `validation.jsonl` → `kamadhenu_dataset/processed/audio/f5/kamadhenu_pilot_char/` (24 kHz mono 16-bit wavs at −3 dBFS, `metadata.csv`, `duration.json`, `vocab.txt`, `raw.arrow` with `--arrow`, `eval/`, `manifest.json`). Originals untouched; gitignored output |
| `dry_run.py` | validates the export as the trainer reads it, simulates the trainer's frame-batch sampler for 16/24/40 GB, prices the run, writes `../reports/experiment_a_dry_run.json` + `../docs/EXPERIMENT_A_CARD.md` |
| `experiment_a.yaml` | every number of the run in one place (base, commit, architecture, lr, batches, updates, caps, evaluation) |
| `ckpt_convert.py` | `to-trainer` (IndicF5 `model.safetensors` → `ckpt/model_last.pt`, fine-tune start) and `to-safetensors` (`model_<step>.pt` → servable file, EMA or `--online`) |
| `launch_experiment_a.sh` | the GPU-box script: pin code, install, download + verify base, export, convert, train (resumable, wall-clock capped), export both weight sets, render the A/B. `--dry-run` does everything but train |
| `render_eval.py` | 13 held-out verses × {base zero-shot, fine-tuned EMA, fine-tuned online}, same reference and seed; duration ratios in `eval.json` |

## Run order

```bash
# here, CPU, any time (needs: pip install soundfile numpy imageio-ffmpeg pyyaml datasets; pilot audio fetched)
python3 kamadhenu/training/dry_run.py            # exports + checks + card

# on the rented GPU box, only after the card is approved
export HF_TOKEN=hf_…   KAMADHENU_VRAM=24GB       # 16GB | 24GB | 40GB
bash kamadhenu/training/launch_experiment_a.sh --dry-run    # everything except the training loop
bash kamadhenu/training/launch_experiment_a.sh              # train → export → A/B renders; re-run to resume
```

Bring back: `export/kamadhenu_voice_a/` (two safetensors + vocab), `eval/` (39 wavs + `eval.json`), `ckpt/train.log`.
The Space's second engine then loads `model.safetensors` + `vocab.txt` in place of the base (same loader, same keys).

## Facts the recipe rests on (checked in the pinned code, commit `13f7c4d6`)

- `finetune_cli.py` builds F5TTS_Base (DiT dim 1024 · depth 22 · heads 16 · ff 2 · text 512 · conv 4), vocos mel front
  end at 24 kHz / hop 256 (93.75 frames/s), tokenizer `custom` = a vocab.txt path. It does **not** copy a pretrain
  checkpoint itself: the trainer resumes from `<ckpt_dir>/model_last.pt`, and when that file has no `step` it
  initialises the online model from the EMA weights at step 0 — exactly what `ckpt_convert.py to-trainer` produces.
- IndicF5's `model.safetensors` is a flat EMA state dict (`ema_model.…` keys) — `utils_infer.load_checkpoint`
  reads it that way — so `to-safetensors` writes the same shape back.
- `DynamicBatchSampler` sorts by frame length and fills batches to `batch_size_per_gpu` frames (max 64 samples);
  a sample longer than the threshold is silently dropped — the dry run counts those per VRAM class.
- Scheduler: linear warm-up over `num_warmup_updates`, then linear decay to the end; `epochs` therefore sets the
  run length and the dry run derives it from batches-per-epoch (`--epochs-for 24GB`).
- F5's own training notes: EMA can hurt a short fine-tune, hence both weight sets are exported and A/B-rendered.

## Not done yet, on purpose

- No torch here: model construction, the conversion and one training step are exercised by the launcher's
  `--dry-run` on the GPU box (first 20 minutes of the approved budget).
- The two verses with >1 s of leading silence (dry-run warnings) are kept; trimming is a Phase 13 decision after
  the lead confirms that the recordings start with the verse and not with a breath the model should learn.
