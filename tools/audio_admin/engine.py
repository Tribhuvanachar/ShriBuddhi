#!/usr/bin/env python3
"""
engine.py — the audio processing core for the DGE Audio Admin.

Pipeline (this is the order that matters):
    1. SEPARATE : pull the singing voice out of the tabla/veena/drums (Demucs)
    2. DETECT   : find the silent gaps *in the voice only*
    3. SEGMENT  : turn those gaps into one [start,end] per shloka
    4. EXPORT   : write a JSON timestamp map + one WAV clip per shloka

Why separation must come first:
    A recording with continuous accompaniment never goes silent in the *mix*,
    so silence-detection on the raw file finds ~1 segment. It only goes silent
    in the *voice*. So we isolate the voice, find gaps there, then cut the
    ORIGINAL audio at those positions (clips keep the full music, timestamps are
    exact).

Runs anywhere PyTorch is available (Codespace / GitHub Action / Colab).
    pip install -r requirements.txt      # demucs, torch, soundfile, numpy
    ffmpeg must be on PATH.

Nothing here needs the internet except the one-time Demucs model download.
"""
from __future__ import annotations
import hashlib, json, os, re, shutil, subprocess, sys, tempfile
from dataclasses import dataclass, asdict, field
from typing import List, Optional, Tuple

# ----------------------------------------------------------------- helpers
def _run(cmd: list) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)

def ffprobe_duration(path: str) -> float:
    # ffprobe itself isn't reliably available everywhere ffmpeg is (this
    # sandbox's static ffmpeg build ships ffmpeg only) -- ffmpeg reports the
    # same duration on stderr when probing with no output, so prefer that
    # and only fall back to a real ffprobe binary if one happens to exist.
    if shutil.which("ffprobe"):
        r = _run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                  "-of", "default=nk=1:nw=1", path])
        out = r.stdout.strip()
        if out:
            return float(out)
    r = _run(["ffmpeg", "-i", path])
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", r.stderr)
    if not m:
        raise RuntimeError(f"Could not determine duration of {path}: {r.stderr[-500:]}")
    h, mnt, s = m.groups()
    return int(h) * 3600 + int(mnt) * 60 + float(s)

def file_hash(path: str) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]

def cached_voice_path(src: str, model: str, cache_dir: str) -> str:
    return os.path.join(cache_dir, f"{file_hash(src)}.{model}.vocals.wav")

# ----------------------------------------------------------------- config
@dataclass
class Params:
    """Everything the detector can be tuned by. Sensible defaults built in."""
    separate: bool = True          # remove background music first (keep ON)
    model: str = "htdemucs"        # demucs model name
    noise_db: Optional[float] = None   # silence threshold; None = auto from voice
    min_gap: float = 1.5           # shortest pause that separates two shlokas (s)
    min_len: float = 8.0           # shortest a shloka can be (s); shorter is merged
    pad: float = 0.10              # breathing room kept around each clip (s)
    prefix: str = "chunk_"
    start_no: int = 1
    width: int = 2

@dataclass
class Result:
    source: str
    duration: float
    count: int
    params: dict
    separated: bool
    chunks: List[dict] = field(default_factory=list)
    note: str = ""

# ------------------------------------------------------------- 1. separate
def separate_voice(src: str, workdir: str, model: str = "htdemucs",
                   enable: bool = True, cache_dir: Optional[str] = None
                   ) -> Tuple[str, bool]:
    """
    Return (path_to_voice_wav_16k_mono, separated?).
    Caches the separated vocals by file-hash so re-runs / tuning are instant
    (separation is by far the slow step — never redo it while sweeping params).
    """
    voice = os.path.join(workdir, "voice16k.wav")

    if enable:
        try:
            import torch  # noqa: F401  (demucs needs it)
        except ImportError:
            print("[engine] torch/demucs not installed — CANNOT remove background "
                  "music. Detection on the raw mix will under-split. Install "
                  "requirements.txt where PyTorch is available.", file=sys.stderr)
            enable = False

    if enable:
        # cache lookup
        cached = None
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)
            cached = cached_voice_path(src, model, cache_dir)
            if os.path.exists(cached):
                _to_16k_mono(cached, voice)
                return voice, True
        # run demucs (two-stems -> vocals.wav + no_vocals.wav)
        r = _run([sys.executable, "-m", "demucs", "-n", model,
                  "--two-stems", "vocals", "-o", workdir, src])
        stem = os.path.join(workdir, model,
                            os.path.splitext(os.path.basename(src))[0], "vocals.wav")
        if r.returncode == 0 and os.path.exists(stem):
            if cached:
                shutil.copyfile(stem, cached)
            _to_16k_mono(stem, voice)
            return voice, True
        print("[engine] demucs failed, falling back to raw mix:\n"
              + r.stderr[-1000:], file=sys.stderr)

    # fallback: raw mix
    _to_16k_mono(src, voice)
    return voice, False

def _to_16k_mono(src: str, dst: str):
    _run(["ffmpeg", "-y", "-v", "error", "-i", src, "-ac", "1", "-ar", "16000", dst])

# --------------------------------------------------------------- 2. detect
def auto_noise_floor(voice_wav: str) -> float:
    """Pick a silence threshold from the voice track's own loudness."""
    r = _run(["ffmpeg", "-i", voice_wav, "-af", "volumedetect", "-f", "null", "-"])
    m = re.search(r"mean_volume: (-?[0-9.]+) dB", r.stderr)
    mean = float(m.group(1)) if m else -25.0
    return round(mean - 8.0, 1)   # a real gap sits well below the mean voice level

def detect_silences(voice_wav: str, noise_db: float, min_sil: float
                    ) -> List[Tuple[float, float]]:
    r = _run(["ffmpeg", "-i", voice_wav, "-af",
              f"silencedetect=noise={noise_db}dB:d={min_sil}", "-f", "null", "-"])
    log = r.stderr
    starts = [float(x) for x in re.findall(r"silence_start: (-?[0-9.]+)", log)]
    ends = [float(x) for x in re.findall(r"silence_end: (-?[0-9.]+)", log)]
    return list(zip(starts, ends[:len(starts)]))

# -------------------------------------------------------------- 3. segment
def segments_from_silences(duration: float, silences: List[Tuple[float, float]],
                           min_gap: float, min_len: float, pad: float
                           ) -> List[List[float]]:
    # only silences at least `min_gap` long are real boundaries; cut at their middle
    cuts = sorted((s + e) / 2 for (s, e) in silences if (e - s) >= min_gap)
    bounds = [0.0] + cuts + [duration]
    segs = [[max(0.0, a - pad), min(duration, b + pad)]
            for a, b in zip(bounds[:-1], bounds[1:])]
    # fold anything shorter than min_len into its previous neighbour
    merged: List[List[float]] = []
    for s in segs:
        if merged and (s[1] - s[0]) < min_len:
            merged[-1][1] = s[1]
        else:
            merged.append(s)
    return merged

# ------------------------------------------------------ 3b. target solver
def solve_for_target(duration: float, voice_wav: str, target: int,
                     min_len: float, pad: float, base_floor: float,
                     min_sil: float = 0.30
                     ) -> Tuple[List[List[float]], float, float, bool, list]:
    """
    Sweep silence threshold + min_gap to land the segment count on `target`.
    Returns (segments, noise_db, min_gap, exact?, trials).
    Cheap: detection is fast, and it never re-separates.

    min_sil: the shortest pause ffmpeg's silencedetect will even register as
    silence. A real pause between two shlokas shorter than this is invisible
    to every other knob below -- no amount of noise/min_gap tuning can find
    a boundary that was never detected in the first place. Lower this (e.g.
    0.10-0.15) if two shlokas keep getting clubbed together with no fix.
    """
    trials = []
    best = None
    floors = [base_floor + d for d in (0, -3, 3, -6, 6, -9, 9)]
    gap_lo = int(round(min_sil * 100))
    gaps = [round(x / 100, 2) for x in range(gap_lo, 305, 5)]  # min_sil .. 3.00 s
    for noise in floors:
        sil = detect_silences(voice_wav, noise, min_sil)
        for gap in gaps:
            segs = segments_from_silences(duration, sil, gap, min_len, pad)
            n = len(segs)
            trials.append({"noise_db": noise, "min_gap": gap, "count": n})
            score = abs(n - target)
            if best is None or score < best[0] or (
                    score == best[0] and gap > best[3]):
                best = (score, segs, noise, gap)
            if score == 0:
                return segs, noise, gap, True, trials
    _, segs, noise, gap = best
    return segs, noise, gap, (abs(len(segs) - target) == 0), trials

# --------------------------------------------------------------- 4. export
def export(src: str, duration: float, segs: List[List[float]], out: str,
           p: Params, want_json=True, want_clips=True,
           voice_src: Optional[str] = None) -> List[dict]:
    """
    voice_src: if given (the cached full-quality separated vocals file), also
    cuts the same boundaries out of the voice-only track into out/voice_only/
    -- so both versions can be compared by ear before picking one for real.
    """
    os.makedirs(out, exist_ok=True)
    voice_out = None
    if voice_src and want_clips:
        voice_out = os.path.join(out, "voice_only")
        os.makedirs(voice_out, exist_ok=True)
    chunks = []
    for i, (a, b) in enumerate(segs):
        name = f"{p.prefix}{str(p.start_no + i).zfill(p.width)}"
        chunks.append({"index": p.start_no + i, "name": name,
                       "start": round(a, 3), "end": round(b, 3),
                       "dur": round(b - a, 3)})
        if want_clips:
            _run(["ffmpeg", "-y", "-v", "error", "-ss", f"{a:.3f}", "-to", f"{b:.3f}",
                  "-i", src, "-c:a", "pcm_s16le", os.path.join(out, name + ".wav")])
            if voice_out:
                _run(["ffmpeg", "-y", "-v", "error", "-ss", f"{a:.3f}", "-to", f"{b:.3f}",
                      "-i", voice_src, "-c:a", "pcm_s16le", os.path.join(voice_out, name + ".wav")])
    if want_json:
        with open(os.path.join(out, "chunks_map.json"), "w") as f:
            json.dump({"source": os.path.basename(src), "duration": round(duration, 3),
                       "count": len(chunks), "chunks": chunks},
                      f, indent=2, ensure_ascii=False)
    return chunks

# ------------------------------------------------------- high-level entry
def process(src: str, out: str = "out", target: int = 0,
            params: Optional[Params] = None, cache_dir: str = ".voice_cache",
            want_json=True, want_clips=True) -> Result:
    p = params or Params()
    duration = ffprobe_duration(src)
    work = tempfile.mkdtemp(prefix="chant_")
    try:
        voice, separated = separate_voice(src, work, p.model, p.separate, cache_dir)
        floor = p.noise_db if p.noise_db is not None else auto_noise_floor(voice)
        note = ""
        if target > 0:
            segs, noise, gap, exact, _ = solve_for_target(
                duration, voice, target, p.min_len, p.pad, floor)
            p.noise_db, p.min_gap = noise, gap
            note = (f"aimed for {target}: got {len(segs)} "
                    + ("(exact)" if exact else "(closest — audio may not have that "
                       "many clean gaps; try a longer/cleaner recording or adjust min_len)"))
        else:
            sil = detect_silences(voice, floor, p.min_gap)
            segs = segments_from_silences(duration, sil, p.min_gap, p.min_len, p.pad)
            p.noise_db = floor
        full_voice = None
        if separated and cache_dir:
            candidate = cached_voice_path(src, p.model, cache_dir)
            if os.path.exists(candidate):
                full_voice = candidate
        chunks = export(src, duration, segs, out, p, want_json, want_clips, voice_src=full_voice)
        return Result(os.path.basename(src), round(duration, 3), len(chunks),
                      asdict(p), separated, chunks, note)
    finally:
        shutil.rmtree(work, ignore_errors=True)

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="DGE chanting audio → per-shloka clips + timestamps")
    ap.add_argument("src")
    ap.add_argument("--out", default="out")
    ap.add_argument("--target", type=int, default=0, help="known shloka count (0=auto)")
    ap.add_argument("--min-len", type=float, default=8.0)
    ap.add_argument("--min-gap", type=float, default=1.5)
    ap.add_argument("--pad", type=float, default=0.10)
    ap.add_argument("--no-separation", action="store_true")
    ap.add_argument("--no-clips", action="store_true")
    a = ap.parse_args()
    pr = Params(separate=not a.no_separation, min_len=a.min_len,
                min_gap=a.min_gap, pad=a.pad)
    res = process(a.src, a.out, a.target, pr, want_clips=not a.no_clips)
    print(json.dumps({"count": res.count, "separated": res.separated,
                      "note": res.note, "params": res.params}, indent=2))
