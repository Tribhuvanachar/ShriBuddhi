#!/usr/bin/env python3
"""Kamadhenu Phase 8 — CPU dry run of Experiment A: no model, no GPU, no money.

    python3 kamadhenu/training/dry_run.py [--no-export] [--quiet] [--epochs-for 24GB]

1. Exports the pilot set with export_f5_dataset.py (unless --no-export) and checks it the way the F5 trainer will
   read it: metadata.csv parses with F5's own reader rules, duration.json lines up, vocab.txt starts with the
   space, every character of every text is in the vocab, raw.arrow (if present) loads with `datasets`.
2. Audio sanity on the 24 kHz exports: duration window, peaks, clipping, edge silence, characters-per-second.
3. Simulates f5_tts.model.dataset.DynamicBatchSampler exactly (sort by frames, fill to the threshold, max 64
   samples) for each VRAM class in experiment_a.yaml → batches per epoch → epochs for the target updates →
   wall-clock and ₹ at the planning assumptions in this file (marked as assumptions; the launcher's first 50
   updates replace them).
4. Writes kamadhenu/reports/experiment_a_dry_run.json and kamadhenu/docs/EXPERIMENT_A_CARD.md (the cost card the
   lead approves or declines). Exit status 1 if any blocking check fails.

--epochs-for <VRAM> prints only the epoch count (used by launch_experiment_a.sh).
"""
import argparse, csv, json, math, sys, time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from kamadhenu_text import load_vocab, unknown_chars  # noqa: E402

CFG = yaml.safe_load(open(HERE / "experiment_a.yaml", encoding="utf-8"))
SR, HOP = 24000, 256
DUR_MIN, DUR_MAX = 4.0, 45.0

# ---- planning assumptions (NOT measurements) -----------------------------------------------------------------
# seconds per optimiser update for F5TTS_Base (337 M) in fp16 at the batch the VRAM class allows, scaled from
# community fine-tune reports on 3090/4090-class cards (F5-TTS discussion #57: roughly 1–2 s per step at
# 3,200–12,800 frames) by nominal fp16 tensor throughput. Treat as ±2×. Rental rates are on-demand marketplace
# prices as of early Sep 2026 (RunPod/Vast/Lambda-class), to be verified at booking; ₹ at 88 per USD.
GPUS = [
    # name, vram class, s/update (assumed), USD/hour low, USD/hour high
    ("T4 16 GB", "16GB", 2.5, 0.20, 0.40),
    ("L4 24 GB", "24GB", 1.4, 0.40, 0.60),
    ("A10G 24 GB", "24GB", 1.1, 0.50, 0.75),
    ("RTX 4090 24 GB", "24GB", 0.6, 0.35, 0.70),
    ("A100 40 GB", "40GB", 0.7, 1.00, 1.50),
]
INR_PER_USD = 88.0
SETUP_MIN = 20            # clone + pip + 1.4 GB weights + export + starting checkpoint
EVAL_MIN = 8              # 13 verses × 3 models × ~10 s each on a 24 GB card, plus model loads
UNCERTAINTY = 2.0         # multiply the point estimate by this for the budget cap


def now_ist():
    return datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%-d %b %Y, %-I:%M %p IST")


def frame_len(duration):
    return duration * SR / HOP          # f5_tts CustomDataset.get_frame_len


def dynamic_batches(durations, frames_threshold, max_samples=64):
    """The trainer's DynamicBatchSampler, verbatim in spirit: ascending frame length, fill until the threshold."""
    indices = sorted(((i, frame_len(d)) for i, d in enumerate(durations)), key=lambda e: e[1])
    batches, batch, bf = [], [], 0.0
    for idx, fl in indices:
        if bf + fl <= frames_threshold and (max_samples == 0 or len(batch) < max_samples):
            batch.append(idx); bf += fl
        else:
            if batch: batches.append(batch)
            if fl <= frames_threshold: batch, bf = [idx], fl
            else: batch, bf = [], 0.0
    if batch: batches.append(batch)
    return batches


def plan(durations, vram, target_updates=None):
    tr = CFG["training"]
    threshold = tr["batch_size_per_gpu"][vram]
    target = target_updates or tr["target_updates"]
    batches = dynamic_batches(durations, threshold, tr["max_samples"])
    per_epoch = len(batches)
    epochs = math.ceil(target / per_epoch)
    updates = per_epoch * epochs
    pad = sum(max(frame_len(durations[i]) for i in b) * len(b) for b in batches)
    used = sum(frame_len(durations[i]) for b in batches for i in b)
    return {"vram": vram, "frames_per_batch": threshold, "batches_per_epoch": per_epoch, "epochs": epochs,
            "updates": updates, "warmup_updates": tr["num_warmup_updates"], "largest_batch": max(len(b) for b in batches),
            "smallest_batch": min(len(b) for b in batches), "padding_efficiency": round(used / pad, 3) if pad else None,
            "too_long_for_batch": sum(1 for d in durations if frame_len(d) > threshold)}


def costs(p):
    rows = []
    for name, vram, spu, lo, hi in GPUS:
        if vram != p["vram"]: continue
        train_min = p["updates"] * spu / 60
        total_h = (SETUP_MIN + train_min + EVAL_MIN) / 60
        rows.append({"gpu": name, "s_per_update_assumed": spu, "train_minutes": round(train_min), "total_hours": round(total_h, 2),
                     "usd_low": round(total_h * lo, 2), "usd_high": round(total_h * hi, 2),
                     "inr_low": round(total_h * lo * INR_PER_USD), "inr_high": round(total_h * hi * INR_PER_USD),
                     "inr_cap": round(total_h * hi * INR_PER_USD * UNCERTAINTY)})
    return rows


def check_export(out, vocab, log):
    blocking, warnings = [], []
    man = json.load(open(out / "manifest.json", encoding="utf-8"))
    files = man["train"]["files"]
    if not files: blocking.append("no training files exported")
    # metadata.csv exactly as prepare_csv_wavs.read_audio_text_pairs reads it
    with open(out / "metadata.csv", encoding="utf-8-sig", newline="") as f:
        rd = csv.reader(f, delimiter="|"); header = next(rd); rows = [r for r in rd if len(r) >= 2]
    if header != ["audio_file", "text"]: blocking.append(f"metadata.csv header {header}")
    if len(rows) != len(files): blocking.append(f"metadata.csv rows {len(rows)} ≠ manifest files {len(files)}")
    durs = json.load(open(out / "duration.json", encoding="utf-8"))["duration"]
    if len(durs) != len(rows): blocking.append(f"duration.json {len(durs)} entries ≠ {len(rows)} rows")
    vs = set(vocab)
    if vocab[0] != " ": blocking.append("vocab.txt index 0 is not the space")
    if len(vocab) != CFG_VOCAB_SIZE: warnings.append(f"vocab size {len(vocab)} (expected {CFG_VOCAB_SIZE})")
    for wav, text in rows:
        if not (out / wav).exists(): blocking.append(f"missing {wav}")
        unk = unknown_chars(text, vs)
        if unk: blocking.append(f"{wav}: characters not in vocab {unk}")
        if "\n" in text or "|" in text: blocking.append(f"{wav}: newline/pipe in text")
    for m in files:
        if m["sample_rate"] != SR: blocking.append(f"{m['id']}: {m['sample_rate']} Hz")
        if not DUR_MIN <= m["duration"] <= DUR_MAX: blocking.append(f"{m['id']}: duration {m['duration']} s outside {DUR_MIN}–{DUR_MAX}")
        if m["clipped_samples"] > 0: warnings.append(f"{m['id']}: {m['clipped_samples']} clipped samples")
        if m["leading_silence"] > 1.0 or m["trailing_silence"] > 1.0:
            warnings.append(f"{m['id']}: edge silence {m['leading_silence']}/{m['trailing_silence']} s")
        if m["chars_per_sec"] and not 2.0 <= m["chars_per_sec"] <= 20.0:
            warnings.append(f"{m['id']}: {m['chars_per_sec']} chars/s (text↔audio mismatch?)")
        if abs(m["source_duration"] - m["duration"]) > 0.25 if m.get("source_duration") else False:
            warnings.append(f"{m['id']}: exported {m['duration']} s vs inventory {m['source_duration']} s")
    arrow = None
    if (out / "raw.arrow").exists():
        try:
            from datasets import Dataset
            ds = Dataset.from_file(str(out / "raw.arrow"))
            arrow = {"rows": len(ds), "columns": ds.column_names}
            if len(ds) != len(rows): blocking.append(f"raw.arrow rows {len(ds)} ≠ {len(rows)}")
            if set(ds.column_names) != {"audio_path", "text", "duration"}: blocking.append(f"raw.arrow columns {ds.column_names}")
        except Exception as e:  # noqa: BLE001
            warnings.append(f"raw.arrow not checked: {e}")
    return man, blocking, warnings, arrow


CFG_VOCAB_SIZE = 2545


def card_md(rep):
    tr, p24 = CFG["training"], rep["plans"]["24GB"]
    lines = [f"# Experiment A — cost card (IndicF5 fine-tune on the pilot set)", "",
             f"Generated {rep['generated_at']} by `kamadhenu/training/dry_run.py` from the CPU dry run. **Nothing has been launched.** "
             "This card is for the project lead's approval; the launcher (`kamadhenu/training/launch_experiment_a.sh`) needs a "
             "rented GPU box and `HF_TOKEN`, and is not run by Claude without a written go-ahead.", "",
             "## What would run", "",
             f"- **Base**: `{CFG['base_model']['repo']}` (MIT), code at commit `{CFG['base_model']['code_commit'][:10]}` — the same weights and code the Space serves.",
             f"- **Data**: {rep['train']['n']} verses of the lead's recitation, {rep['train']['minutes']} min at 24 kHz (grade A, metre named, full verse), "
             f"{rep['eval']['n']} held out; {rep['train']['meters']} metres; {rep['train']['chars']:,} characters, all in IndicF5's vocabulary.",
             f"- **Recipe**: `finetune_cli.py`, lr {tr['learning_rate']}, {tr['target_updates']:,} target updates (warm-up {tr['num_warmup_updates']}), "
             f"batches by frames (the trainer's own sampler), fp16, checkpoint every {tr['save_per_updates']} updates, wall-clock cap {tr['max_minutes']} min, resumable.",
             "- **Output**: `model.safetensors` (EMA) + `model_online.safetensors` in IndicF5's own format, plus 13 A/B renders "
             "(base zero-shot vs fine-tuned, same reference clip, same seed) and their duration ratios.", "",
             "## Size of the run (from the dry run's batch simulation)", "",
             "| VRAM class | frames/batch | batches/epoch | epochs | updates | padding efficiency |", "|---|---|---|---|---|---|"]
    for v, p in rep["plans"].items():
        lines.append(f"| {v} | {p['frames_per_batch']:,} | {p['batches_per_epoch']} | {p['epochs']} | {p['updates']:,} | {p['padding_efficiency']} |")
    lines += ["", "## Time and money (planning assumptions, ±2×)", "",
              f"Assumed seconds per update are scaled from community F5-TTS fine-tune reports, not measured on this data; "
              f"the trainer's progress bar in `ckpt/train.log` shows the real rate within the first minutes — stop the run there if it projects past the cap "
              f"(the config's wall-clock cap stops it regardless, and a re-run resumes). "
              f"Rates are on-demand marketplace prices to verify at booking; ₹ at {INR_PER_USD:.0f}/USD. "
              f"Every total includes {SETUP_MIN} min of setup and {EVAL_MIN} min of evaluation renders.", "",
              "| GPU | s/update (assumed) | training | total | USD | ₹ | ₹ cap (×2) |", "|---|---|---|---|---|---|---|"]
    for v, p in rep["plans"].items():
        for c in rep["costs"][v]:
            lines.append(f"| {c['gpu']} | {c['s_per_update_assumed']} | {c['train_minutes']} min | {c['total_hours']} h | "
                         f"{c['usd_low']}–{c['usd_high']} | {c['inr_low']}–{c['inr_high']} | **{c['inr_cap']}** |")
    rec = min((c for c in rep["costs"]["24GB"]), key=lambda c: c["inr_high"])
    lines += ["", "## Recommendation", "",
              f"- **Card**: a 24 GB class (L4 / A10G / RTX 4090). Point estimate on the cheapest, {rec['gpu']}: about "
              f"₹{rec['inr_low']}–{rec['inr_high']}; **approve a cap of ₹{max(c['inr_cap'] for c in rep['costs']['24GB'])}** "
              "(the wall-clock cap in the config enforces it; a re-run resumes, it never restarts).",
              "- **Not** a T4: 16 GB halves the batch and the assumed rate is 2× slower, so it costs about the same for a worse gradient.",
              "- **Not** ZeroGPU: the Space's 60 s GPU slices cannot hold a training loop; it serves the result instead.",
              "- **Go / no-go after the run**: the 13 held-out verses at a median duration ratio inside 0.75–1.25 (zero-shot clip D ran ~1.65×) "
              "AND the lead judging the words intelligible in his voice → Phase 12 continues with the full grade-A set (6.5 h). "
              "Otherwise the ₹ is the price of knowing that the pilot set is too small, and the next lever is more data, not more steps.", "",
              "## What the dry run verified on CPU", ""]
    for k, v in rep["checks"].items():
        lines.append(f"- {k}: {v}")
    if rep["warnings"]:
        lines += ["", f"Warnings ({len(rep['warnings'])}, none blocking):", ""] + [f"- {w}" for w in rep["warnings"][:25]]
        if len(rep["warnings"]) > 25: lines.append(f"- … {len(rep['warnings']) - 25} more in `kamadhenu/reports/experiment_a_dry_run.json`")
    lines += ["", "## Decision", "", "- [ ] Approved by the project lead (date, cap in ₹, GPU class): ______", "- [ ] Declined / changes requested: ______", ""]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-export", action="store_true"); ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--epochs-for", default=None, help="print only the epoch count for this VRAM class (16GB/24GB/40GB)")
    ap.add_argument("--out", default=CFG["dataset"]["export_dir"])
    a = ap.parse_args(argv)
    log = (lambda *x: None) if (a.quiet or a.epochs_for) else print
    out = ROOT / a.out
    if not a.no_export and not a.epochs_for:
        import export_f5_dataset
        export_f5_dataset.main(["--out", a.out, "--arrow"] if _has_datasets() else ["--out", a.out])
    if not (out / "manifest.json").exists():
        sys.exit(f"no export at {out}; run without --no-export (needs the pilot audio under kamadhenu_dataset/incoming_audio)")
    vocab = load_vocab(HERE / "vocab_indicf5.txt")
    man, blocking, warnings, arrow = check_export(out, vocab, log)
    durs = [m["duration"] for m in man["train"]["files"]]
    plans = {v: plan(durs, v) for v in CFG["training"]["batch_size_per_gpu"]}
    if a.epochs_for:
        print(plans[a.epochs_for]["epochs"]); return 0
    # A sample longer than the frame threshold is silently DROPPED by the trainer's sampler (see dynamic_batches):
    # blocking for the recommended 24 GB class, a warning for the others (the card says why 16 GB is not advised).
    for v, p in plans.items():
        if p["warmup_updates"] >= p["updates"]: blocking.append(f"{v}: warm-up {p['warmup_updates']} ≥ total updates {p['updates']}")
        if p["too_long_for_batch"]:
            msg = f"{v}: {p['too_long_for_batch']} sample(s) longer than one batch ({p['frames_per_batch'] * HOP / SR:.1f} s) would be dropped by the sampler"
            (blocking if v == "24GB" else warnings).append(msg)
    meters = sorted({m["meter"] for m in man["train"]["files"] if m.get("meter")})
    rep = {
        "generated_at": now_ist(), "tool": "kamadhenu/training/dry_run.py", "config": "kamadhenu/training/experiment_a.yaml",
        "export_dir": a.out, "vocab": man["vocab"],
        "train": {"n": man["train"]["n"], "minutes": round(man["train"]["seconds"] / 60, 1), "hours": man["train"]["hours"],
                  "frames": man["train"]["frames"], "chars": man["train"]["chars"], "meters": len(meters), "meter_names": meters,
                  "duration_min": min(durs), "duration_max": max(durs), "duration_mean": round(sum(durs) / len(durs), 2)},
        "eval": {"n": man["eval"]["n"], "minutes": round(man["eval"]["seconds"] / 60, 1)},
        "checks": {
            "metadata.csv": f"{man['train']['n']} rows, F5 reader rules (utf-8-sig, `|`, header) — ok" if not any("metadata" in b for b in blocking) else "FAILED",
            "duration.json": "aligned with metadata.csv" if not any("duration.json" in b for b in blocking) else "FAILED",
            "vocab.txt": f"{len(vocab)} entries, space at index 0, sha1 {man['vocab']['sha1'][:10]}… (IndicF5's, verified against the Hub at launch)",
            "vocab coverage": "every character of every text is in the vocab" if not any("not in vocab" in b for b in blocking) else "FAILED",
            "audio": f"all {SR} Hz mono, {DUR_MIN}–{DUR_MAX} s, peaks at {man['peak_dbfs_target']} dBFS, {sum(1 for m in man['train']['files'] if m['clipped_samples'])} files with clipping",
            "raw.arrow": (f"{arrow['rows']} rows, columns {arrow['columns']} — loads with `datasets`" if arrow else "not built here (built by the launcher on the training machine)"),
            "batch sampler": "simulated with the trainer's DynamicBatchSampler rules for 16/24/40 GB",
            "torch / GPU": "not installed here — model construction, the checkpoint conversion and the training step are exercised only by the launcher's --dry-run on the GPU box",
        },
        "plans": plans, "costs": {v: costs(p) for v, p in plans.items()},
        "assumptions": {"gpus": GPUS, "inr_per_usd": INR_PER_USD, "setup_min": SETUP_MIN, "eval_min": EVAL_MIN, "uncertainty_factor": UNCERTAINTY},
        "blocking": blocking, "warnings": warnings, "export_problems": man["problems"],
    }
    (ROOT / "kamadhenu/reports").mkdir(exist_ok=True)
    json.dump(rep, open(ROOT / "kamadhenu/reports/experiment_a_dry_run.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    (ROOT / "kamadhenu/docs/EXPERIMENT_A_CARD.md").write_text(card_md(rep), encoding="utf-8")
    log(f"train {rep['train']['n']} × {rep['train']['minutes']} min, eval {rep['eval']['n']}; vocab ok; "
        f"{len(warnings)} warnings, {len(blocking)} blocking")
    for v, p in plans.items():
        log(f"  {v}: {p['batches_per_epoch']} batches/epoch × {p['epochs']} epochs = {p['updates']} updates; "
            + "; ".join(f"{c['gpu']} ≈ {c['train_minutes']} min, ₹{c['inr_low']}–{c['inr_high']}" for c in rep["costs"][v]))
    for b in blocking: log("  BLOCKING:", b)
    log("wrote kamadhenu/reports/experiment_a_dry_run.json and kamadhenu/docs/EXPERIMENT_A_CARD.md")
    return 1 if blocking else 0


def _has_datasets():
    try:
        import datasets  # noqa: F401
        return True
    except Exception:
        return False


if __name__ == "__main__":
    sys.exit(main())
