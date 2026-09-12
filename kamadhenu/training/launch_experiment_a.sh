#!/usr/bin/env bash
# Kamadhenu Experiment A — run on a rented GPU box (one 16–24 GB card). DO NOT run before the lead approves
# kamadhenu/docs/EXPERIMENT_A_CARD.md. Every step is idempotent, so re-running after a crash or the wall-clock cap
# RESUMES (the trainer picks up ckpt/model_last.pt with its step).
#
#   export HF_TOKEN=hf_…            # account that accepted the ai4bharat/IndicF5 gate
#   export KAMADHENU_VRAM=24GB      # 16GB | 24GB | 40GB  → batch_size_per_gpu from experiment_a.yaml
#   bash kamadhenu/training/launch_experiment_a.sh [--dry-run]   # --dry-run: everything except training/rendering
#
# Needs: git, python3 ≥ 3.10, pip, an NVIDIA driver; ~6 GB disk for code+weights+one checkpoint chain.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(cd "$HERE/../.." && pwd)"
DRY=0; [ "${1:-}" = "--dry-run" ] && DRY=1
: "${HF_TOKEN:?set HF_TOKEN (must have accepted the ai4bharat/IndicF5 gate)}"
VRAM="${KAMADHENU_VRAM:-24GB}"
WORK="${KAMADHENU_WORK:-$HOME/kamadhenu_exp_a}"; mkdir -p "$WORK"
CFG="$HERE/experiment_a.yaml"
yq() { python3 - "$CFG" "$1" <<'PY'
import sys, yaml
d = yaml.safe_load(open(sys.argv[1]))
for k in sys.argv[2].split('.'): d = d[k]
print(d)
PY
}
COMMIT="$(yq base_model.code_commit)"; REPO="$(yq base_model.code_repo)"; HFREPO="$(yq base_model.repo)"
VOCAB_SHA="$(yq base_model.vocab_sha1)"; LR="$(yq training.learning_rate)"; BATCH="$(yq training.batch_size_per_gpu.$VRAM)"
WARM="$(yq training.num_warmup_updates)"; SAVE="$(yq training.save_per_updates)"; LAST="$(yq training.last_per_steps)"
MAXMIN="${KAMADHENU_MAX_MINUTES:-$(yq training.max_minutes)}"; SEED="$(yq experiment.seed)"; DSNAME="$(yq dataset.name)"
T_START=$(date +%s)
echo "== Experiment A: $VRAM → batch $BATCH frames, lr $LR, warmup $WARM, training cap $MAXMIN min, work $WORK"

# 1. IndicF5 code at the pinned commit (the same the Space serves), installed editable.
if [ ! -d "$WORK/IndicF5/.git" ]; then git clone --quiet "$REPO" "$WORK/IndicF5"; fi
git -C "$WORK/IndicF5" checkout --quiet "$COMMIT"
python3 -m pip install -q --upgrade pip
python3 -m pip install -q "torch==2.8.0" "torchaudio==2.8.0" "numpy<=1.26.4" accelerate==0.34.2 transformers==4.46.3 \
  vocos==0.1.0 x-transformers==2.19.7 librosa==0.11.0 soundfile safetensors huggingface_hub datasets tensorboard \
  imageio-ffmpeg pyyaml "cached_path" ema_pytorch jieba pypinyin
python3 -m pip install -q -e "$WORK/IndicF5"

# 2. Base weights + the gated vocab, then the vocab-identity check the whole recipe rests on.
python3 - "$HFREPO" "$WORK" "$VOCAB_SHA" "$HERE/vocab_indicf5.txt" <<'PY'
import sys, os, hashlib
from huggingface_hub import hf_hub_download
repo, work, want, ours = sys.argv[1:5]
w = hf_hub_download(repo, "model.safetensors", token=os.environ["HF_TOKEN"], local_dir=f"{work}/base")
v = hf_hub_download(repo, "checkpoints/vocab.txt", token=os.environ["HF_TOKEN"], local_dir=f"{work}/base")
got = hashlib.sha1(open(v, "rb").read()).hexdigest()
mine = hashlib.sha1(open(ours, "rb").read()).hexdigest()
print("base weights:", w, os.path.getsize(w) // 1_000_000, "MB"); print("vocab sha1:", got, "expected", want)
if got != want or mine != want:
    sys.exit("vocab.txt on the Hub differs from kamadhenu/training/vocab_indicf5.txt — stop, re-export with the Hub file and re-run the dry run")
PY

# 3. Dataset: source recordings (re-fetched if this box lacks them), 24 kHz wavs + raw.arrow with THIS machine's
#    absolute paths, then the same checks the CPU dry run made, and the epoch count for this VRAM class.
python3 "$HERE/fetch_pilot_audio.py"
python3 "$HERE/export_f5_dataset.py" --arrow
DATA="$ROOT/$(yq dataset.export_dir)"
python3 "$HERE/dry_run.py" --no-export --quiet
EPOCHS="${KAMADHENU_EPOCHS:-$(python3 "$HERE/dry_run.py" --epochs-for "$VRAM")}"
echo "== $EPOCHS epochs for $VRAM"

# 4. Starting checkpoint for the trainer (only when no run is in progress).
CKPT="$WORK/ckpt"; mkdir -p "$CKPT"
if [ ! -f "$CKPT/model_last.pt" ]; then python3 "$HERE/ckpt_convert.py" to-trainer "$WORK/base/model.safetensors" "$CKPT/model_last.pt"; fi
# Strict load into the real model + EMA before a single GPU-minute of training is spent (attempt 2 died here).
python3 "$HERE/ckpt_convert.py" verify "$CKPT/model_last.pt" --vocab "$DATA/vocab.txt"

if [ "$DRY" = 1 ]; then echo "== dry run complete: code, weights, vocab, dataset and starting checkpoint are in place; no training run"; exit 0; fi

# 5. Train (resumable; hard wall-clock cap; tensorboard log in $CKPT).
cd "$WORK/IndicF5"
T_TRAIN=$(date +%s)
set +e
PREC="${KAMADHENU_PRECISION:-bf16}"   # attempt 3 (fp16 + GradScaler) produced loss=nan from step 1 and NaN weights by step ~320; L4/A10G/A100 do bf16 natively
echo "== mixed precision: $PREC"
timeout "${MAXMIN}m" accelerate launch --mixed_precision="$PREC" f5_tts/train/finetune_cli.py \
  --exp_name F5TTS_Base --dataset_name "$DSNAME" --tokenizer custom --tokenizer_path "$DATA/vocab.txt" \
  --learning_rate "$LR" --batch_size_per_gpu "$BATCH" --batch_size_type frame --max_samples 64 \
  --grad_accumulation_steps 1 --max_grad_norm 1.0 --epochs "$EPOCHS" --num_warmup_updates "$WARM" \
  --save_per_updates "$SAVE" --last_per_steps "$LAST" --logger tensorboard \
  --ckpt_dir "$CKPT" --data_dir "$DATA" 2>&1 | tee -a "$CKPT/train.log"
RC=${PIPESTATUS[0]}; set -e
[ "$RC" = 124 ] && echo "== wall-clock cap reached ($MAXMIN min); re-run to resume from $CKPT/model_last.pt"
cd "$ROOT"

# 6. Export the latest checkpoint both ways and render the held-out A/B.
EXP="$WORK/export/kamadhenu_voice_a"; mkdir -p "$EXP"
LATEST="$(ls -t "$CKPT"/model_*.pt | head -1)"
python3 "$HERE/ckpt_convert.py" to-safetensors "$LATEST" "$EXP/model.safetensors" --wrapper-base "$WORK/base/model.safetensors"
python3 "$HERE/ckpt_convert.py" to-safetensors "$LATEST" "$EXP/model_online.safetensors" --online --wrapper-base "$WORK/base/model.safetensors"
cp "$DATA/vocab.txt" "$EXP/vocab.txt"
T_EVAL=$(date +%s)
python3 "$HERE/render_eval.py" --base "$WORK/base/model.safetensors" --finetuned "$EXP/model.safetensors" \
  --finetuned-online "$EXP/model_online.safetensors" --vocab "$EXP/vocab.txt" --out "$WORK/eval"
T_END=$(date +%s)
STEP="$(python3 -c "import torch;print(torch.load('$LATEST',map_location='cpu',weights_only=True).get('step','?'))")"
# Loss health from the trainer's own progress bar: how many updates reported a number, how many NaN, the last few.
python3 - "$CKPT/train.log" <<'PY' | tee "$WORK/loss.json"
import re, sys, json
s = open(sys.argv[1], encoding="utf-8", errors="ignore").read()
seen = {}
for m in re.finditer(r"loss=([0-9.]+|nan|inf), step=(\d+)", s):
    seen[int(m.group(2))] = m.group(1)
vals = [seen[k] for k in sorted(seen)]
nums = [(k, float(v)) for k, v in sorted(seen.items()) if v not in ("nan", "inf")]
print(json.dumps({"updates_seen": len(vals), "nan_updates": sum(1 for v in vals if v == "nan"), "numeric_updates": len(nums),
                  "first_loss": nums[0] if nums else None, "last_numeric": nums[-3:], "last_reported": vals[-1] if vals else None,
                  "healthy": bool(vals) and vals[-1] not in ("nan", "inf") and sum(1 for v in vals[-50:] if v == "nan") == 0}))
PY
python3 "$HERE/run_record.py" --out "$WORK/run.json" --vram "$VRAM" --batch "$BATCH" --epochs "$EPOCHS" --cap "$MAXMIN" \
  --rc "$RC" --step "$STEP" --t "$T_START" "$T_TRAIN" "$T_EVAL" "$T_END"
python3 - "$WORK/run.json" "$WORK/loss.json" "$PREC" <<'PY'
import json, sys
r = json.load(open(sys.argv[1])); r["loss"] = json.load(open(sys.argv[2])); r["mixed_precision"] = sys.argv[3]
json.dump(r, open(sys.argv[1], "w"), indent=1)
if not r["loss"]["healthy"]: print("!! TRAINING DIVERGED (NaN loss) — the exported weights are not usable; see loss.json")
PY
cp "$WORK/run.json" "$EXP/run.json"; cp "$ROOT/kamadhenu/reports/experiment_a_dry_run.json" "$EXP/dry_run.json" 2>/dev/null || true
echo "== done. Keep: $EXP, $WORK/eval, $CKPT/model_last.pt, $CKPT/train.log. Delete the rest of $CKPT to free disk."

# 7. Optional: publish the results to a private Hub repo (KAMADHENU_RESULTS_REPO=<org>/<name>), so a job on rented
#    hardware leaves nothing behind when its disk is reclaimed. Weights, renders, log, run record — no source audio.
if [ -n "${KAMADHENU_RESULTS_REPO:-}" ]; then
  python3 "$HERE/run_record.py" --publish "$KAMADHENU_RESULTS_REPO" --export "$EXP" --eval "$WORK/eval" --log "$CKPT/train.log"
fi
