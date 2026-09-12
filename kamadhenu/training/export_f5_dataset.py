#!/usr/bin/env python3
"""Kamadhenu Phase 8 — export the pilot set in the F5-TTS fine-tune layout (24 kHz mono WAV + metadata).

    python3 kamadhenu/training/export_f5_dataset.py \
        [--train kamadhenu/data/pilot/train.jsonl] [--eval kamadhenu/data/pilot/validation.jsonl] \
        [--out kamadhenu_dataset/processed/audio/f5/kamadhenu_pilot_char] [--arrow] [--limit N]

Writes, exactly what f5_tts.model.dataset.load_dataset("CustomDatasetPath") reads:
    <out>/wavs/<id>.wav        24 kHz, mono, 16-bit, peaks at −3 dBFS (originals are never modified)
    <out>/metadata.csv         audio_file|text   (the F5 "csv_wavs" format; paths relative to <out>)
    <out>/duration.json        {"duration": [...]}  in metadata order — the DynamicBatchSampler's input
    <out>/vocab.txt            IndicF5's character vocabulary (kamadhenu/training/vocab_indicf5.txt)
    <out>/raw.arrow            with --arrow: the HF-datasets arrow file the trainer loads (absolute audio paths,
                               so it is rebuilt on the training machine — the launcher does that)
    <out>/eval/…               the held-out verses, same treatment, for the A/B renders after training
    <out>/manifest.json        per-file measurements + totals (the dry run reads this)

Decoding is the static ffmpeg from the imageio-ffmpeg wheel (same as tools/kamadhenu/inventory.py); levels,
clipping and edge silence are measured with numpy on the decoded 24 kHz signal. Needs: soundfile, numpy,
imageio-ffmpeg (pip), datasets only for --arrow. Idempotent: an existing wav is re-measured, not re-decoded.
"""
import argparse, csv, json, hashlib, os, subprocess, sys, time
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from kamadhenu_text import model_text, load_vocab, unknown_chars  # noqa: E402

SR, HOP = 24000, 256                 # F5 mel front end: 24 kHz, hop 256 → 93.75 frames/s
PEAK_DBFS = -3.0
SILENCE_DBFS = -45.0
VOCAB = Path(__file__).resolve().parent / "vocab_indicf5.txt"


def ffmpeg_exe():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def decode(src, dst, exe):
    cmd = [exe, "-nostdin", "-loglevel", "error", "-y", "-i", str(src), "-ac", "1", "-ar", str(SR),
           "-sample_fmt", "s16", "-f", "wav", str(dst)]
    subprocess.run(cmd, check=True)


def measure(path):
    x, sr = sf.read(path, dtype="float32", always_2d=False)
    if x.ndim > 1:
        x = x.mean(axis=1)
    n = len(x)
    peak = float(np.max(np.abs(x))) if n else 0.0
    rms = float(np.sqrt(np.mean(x ** 2))) if n else 0.0
    clip = int(np.sum(np.abs(x) >= 0.999))
    thr = 10 ** (SILENCE_DBFS / 20)
    loud = np.flatnonzero(np.abs(x) > thr)
    lead = float(loud[0] / sr) if len(loud) else n / sr
    trail = float((n - 1 - loud[-1]) / sr) if len(loud) else n / sr
    return {"sample_rate": sr, "samples": n, "duration": round(n / sr, 3),
            "peak_dbfs": round(20 * np.log10(peak), 2) if peak > 0 else None,
            "rms_dbfs": round(20 * np.log10(rms), 2) if rms > 0 else None,
            "clipped_samples": clip, "leading_silence": round(lead, 3), "trailing_silence": round(trail, 3)}


def normalize_peak(path, target_dbfs=PEAK_DBFS):
    x, sr = sf.read(path, dtype="float32")
    peak = float(np.max(np.abs(x))) if len(x) else 0.0
    if peak <= 0:
        return
    g = (10 ** (target_dbfs / 20)) / peak
    sf.write(path, np.clip(x * g, -1.0, 1.0), sr, subtype="PCM_16")


def export_rows(rows, out, exe, vocab, tag, limit=None, log=print):
    out.mkdir(parents=True, exist_ok=True)
    (out / "wavs").mkdir(exist_ok=True)
    recs, problems = [], []
    for i, r in enumerate(rows if limit is None else rows[:limit]):
        src = ROOT / r["audio"]
        dst = out / "wavs" / (r["id"] + ".wav")
        text = model_text(r["text"])
        unk = unknown_chars(text, vocab)
        if not src.exists():
            problems.append({"id": r["id"], "problem": "source audio missing", "audio": r["audio"]})
            continue
        if not dst.exists():
            try:
                decode(src, dst, exe)
                normalize_peak(dst)
            except Exception as e:  # noqa: BLE001
                problems.append({"id": r["id"], "problem": f"decode failed: {e}", "audio": r["audio"]})
                continue
        m = measure(dst)
        m.update({"id": r["id"], "wav": f"wavs/{r['id']}.wav", "text": text, "chars": len(text),
                  "frames": int(np.ceil(m["duration"] * SR / HOP)), "chars_per_sec": round(len(text) / m["duration"], 2) if m["duration"] else None,
                  "meter": r.get("meter"), "work": r.get("work"), "text_id": r.get("text_id"), "source_audio": r["audio"],
                  "source_duration": r.get("duration"), "unknown_chars": unk})
        recs.append(m)
        if unk:
            problems.append({"id": r["id"], "problem": "characters not in vocab", "chars": unk})
        if (i + 1) % 25 == 0:
            log(f"  {tag}: {i + 1}/{len(rows)}")
    with open(out / "metadata.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="|", lineterminator="\n")
        w.writerow(["audio_file", "text"])
        for m in recs:
            w.writerow([m["wav"], m["text"]])
    json.dump({"duration": [m["duration"] for m in recs]}, open(out / "duration.json", "w", encoding="utf-8"))
    (out / "vocab.txt").write_text(VOCAB.read_text(encoding="utf-8"), encoding="utf-8")
    return recs, problems


def write_arrow(out, recs, log=print):
    """raw.arrow exactly as f5_tts/train/datasets/prepare_csv_wavs.py writes it (one row per sample:
    audio_path, text, duration), with absolute paths for THIS machine."""
    from datasets.arrow_writer import ArrowWriter
    p = out / "raw.arrow"
    with ArrowWriter(path=str(p), writer_batch_size=1) as w:
        for m in recs:
            w.write({"audio_path": str((out / m["wav"]).resolve()), "text": m["text"], "duration": m["duration"]})
    log(f"  wrote {p} ({p.stat().st_size / 1024:.0f} KB)")


def verified_ids(report):
    """{id: (decision, heard_text)} from a verify_pilot_transcripts.py report.

    A crossmatch.json (rows carry `decision`) is the stronger gate: it says which verse the recording IS.
    A plain transcript check (rows carry `verdict`) only says whether the expected text was heard."""
    d = json.load(open(report, encoding="utf-8"))
    out = {}
    for r in d.get("rows", []):
        if "decision" in r:
            out[r["id"]] = (r["decision"], r.get("heard_text"))
        else:
            out[r["id"]] = ("confirmed" if r.get("verdict") == "ok" else r.get("verdict", "missing"), None)
    return out


def split_verified(rows, verdicts, accept_remap=False):
    """Keep rows whose recording is confirmed to carry their text; return (kept, [dropped {id, decision}]).
    With accept_remap, a row the cross-match remapped keeps its audio and takes the heard verse's text."""
    kept, dropped = [], []
    for r in rows:
        dec, heard = verdicts.get(r["id"], ("not_checked", None))
        if dec in ("confirmed", "weak_confirm"):
            kept.append(r)
        elif dec == "remap" and accept_remap and heard:
            kept.append(dict(r, text=heard, remapped_from=r.get("text_id")))
        else:
            dropped.append({"id": r["id"], "decision": dec})
    return kept, dropped


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", default="kamadhenu/data/pilot/train.jsonl")
    ap.add_argument("--eval", default="kamadhenu/data/pilot/validation.jsonl")
    ap.add_argument("--out", default="kamadhenu_dataset/processed/audio/f5/kamadhenu_pilot_char")
    ap.add_argument("--arrow", action="store_true", help="also write raw.arrow (needs the `datasets` package)")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--require-verified", metavar="REPORT_JSON", default=None,
                    help="kamadhenu/reports/pilot_transcript_check/pilot_transcript_check.json from "
                         "verify_pilot_transcripts.py: export only rows whose ASR verdict is 'ok'; rows the report "
                         "flagged or never saw are dropped and listed in manifest.json['excluded']")
    ap.add_argument("--accept-remap", action="store_true",
                    help="with a crossmatch.json report: keep remapped rows, training them on the verse actually heard")
    a = ap.parse_args(argv)
    exe = ffmpeg_exe()
    if not exe:
        sys.exit("ffmpeg not found: pip install imageio-ffmpeg")
    vocab = load_vocab(VOCAB)
    assert vocab[0] == " ", "vocab.txt must start with the space character (index 0)"
    out = ROOT / a.out
    t0 = time.time()
    train_rows = [json.loads(l) for l in open(ROOT / a.train, encoding="utf-8")]
    eval_rows = [json.loads(l) for l in open(ROOT / a.eval, encoding="utf-8")] if a.eval and (ROOT / a.eval).exists() else []
    excluded, verified = [], None
    if a.require_verified:
        verified = verified_ids(ROOT / a.require_verified)
        train_rows, drop = split_verified(train_rows, verified, a.accept_remap)
        excluded += drop
        eval_rows, drop = split_verified(eval_rows, verified, a.accept_remap)
        excluded += drop
        print(f"--require-verified: {len(train_rows)} train + {len(eval_rows)} eval rows keep an 'ok' verdict, "
              f"{len(excluded)} dropped")
    recs, problems = export_rows(train_rows, out, exe, vocab, "train", a.limit)
    eval_recs, eval_problems = [], []
    if eval_rows:
        eval_recs, eval_problems = export_rows(eval_rows, out / "eval", exe, vocab, "eval", a.limit)
    if a.arrow and recs:
        write_arrow(out, recs)
    tot = sum(m["duration"] for m in recs)
    manifest = {
        "written_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "tool": "kamadhenu/training/export_f5_dataset.py",
        "sample_rate": SR, "hop_length": HOP, "peak_dbfs_target": PEAK_DBFS,
        "vocab": {"file": "vocab.txt", "size": len(vocab), "sha1": hashlib.sha1(VOCAB.read_bytes()).hexdigest()},
        "train": {"n": len(recs), "seconds": round(tot, 1), "hours": round(tot / 3600, 3),
                  "frames": int(sum(m["frames"] for m in recs)), "chars": int(sum(m["chars"] for m in recs)), "files": recs},
        "eval": {"n": len(eval_recs), "seconds": round(sum(m["duration"] for m in eval_recs), 1), "files": eval_recs},
        "problems": problems + eval_problems, "seconds_taken": round(time.time() - t0, 1),
        "verified_report": a.require_verified, "excluded": excluded,
    }
    json.dump(manifest, open(out / "manifest.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(recs)} train + {len(eval_recs)} eval wavs → {out.relative_to(ROOT)} "
          f"({tot / 60:.1f} min of training audio, {len(problems + eval_problems)} problems, {time.time() - t0:.0f}s)")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
