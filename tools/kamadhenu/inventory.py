"""Stage 3 — audio inventory + QC over kamadhenu_dataset/incoming_audio/ (recursive).

For every audio file: container/codec (probed from the bytes, not the extension), duration, sample rate,
channels, bit depth (PCM only), peak / RMS / crude loudness, leading/trailing/internal silence, clipping,
low-volume, noise-floor / SNR estimate, duplicate detection (exact sha1 + acoustic fingerprint), and a
list of QC flags. Decoding uses the static ffmpeg shipped in the imageio-ffmpeg wheel (no system ffmpeg).

Results are cached per (path, size, mtime) in processed/audio_inventory_cache.json so re-runs only
touch new files. Originals are opened read-only; nothing is written next to them."""
import json, math, os, re, subprocess, sys, hashlib, time
from pathlib import Path
import numpy as np
from .common import DS, INCOMING, PROCESSED, AUDIO_EXT, write_json, read_json, write_csv, log, now_ist, rel, sha1_file

SR = 16000            # analysis rate (F0/speech band only needs 8 kHz bandwidth)
FRAME = 400           # 25 ms
HOP = 160             # 10 ms


def ffmpeg_exe():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def probe(path, exe):
    """Parse ffmpeg's stream line: codec, sample rate, channels, bit depth, bitrate, container."""
    r = subprocess.run([exe, "-hide_banner", "-i", str(path)], capture_output=True, text=True, errors="ignore")
    txt = r.stderr
    info = {"container": None, "codec": None, "sample_rate": None, "channels": None, "bit_depth": None, "bitrate_kbps": None, "probe_duration": None}
    m = re.search(r"Input #0, ([^,]+),", txt)
    if m: info["container"] = m.group(1).strip()
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", txt)
    if m: info["probe_duration"] = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    m = re.search(r"Stream #\d+:\d+.*?Audio: ([^,]+), (\d+) Hz, ([^,]+), ([^,]+)(?:, (\d+) kb/s)?", txt)
    if m:
        info["codec"] = m.group(1).strip()
        info["sample_rate"] = int(m.group(2))
        ch = m.group(3).strip()
        info["channels"] = 1 if ch == "mono" else 2 if ch == "stereo" else (int(re.sub(r"\D", "", ch) or 0) or ch)
        fmt = m.group(4).strip()
        bd = re.search(r"s(\d+)", fmt)
        info["bit_depth"] = int(bd.group(1)) if bd and fmt.startswith("s") else (32 if fmt.startswith("flt") else None)
        info["sample_fmt"] = fmt
        info["bitrate_kbps"] = int(m.group(5)) if m.group(5) else None
    return info, txt.strip().splitlines()[-1] if r.returncode and txt.strip() else None


def decode(path, exe):
    r = subprocess.run([exe, "-hide_banner", "-loglevel", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                       capture_output=True)
    if r.returncode != 0 or len(r.stdout) < 4:
        return None, r.stderr.decode("utf-8", "ignore").strip()[-300:]
    return np.frombuffer(r.stdout, dtype=np.float32), None


def db(x):
    return 20 * math.log10(max(x, 1e-9))


def analyse(x):
    n = len(x)
    dur = n / SR
    peak = float(np.max(np.abs(x))) if n else 0.0
    rms = float(np.sqrt(np.mean(x ** 2))) if n else 0.0
    # frame energies
    if n < FRAME:
        return {"duration_seconds": round(dur, 3), "peak_dbfs": round(db(peak), 2), "rms_dbfs": round(db(rms), 2), "flags": ["too_short"]}
    nfr = 1 + (n - FRAME) // HOP
    idx = np.arange(FRAME)[None, :] + HOP * np.arange(nfr)[:, None]
    fr = x[idx]
    fe = np.sqrt(np.mean(fr ** 2, axis=1)) + 1e-9
    fe_db = 20 * np.log10(fe)
    floor = float(np.percentile(fe_db, 10))
    speech = float(np.percentile(fe_db, 90))
    snr = speech - floor
    sil_thr = max(floor + 6, -55)
    voiced = fe_db > sil_thr
    # leading / trailing silence
    lead = int(np.argmax(voiced)) * HOP / SR if voiced.any() else dur
    trail = int(np.argmax(voiced[::-1])) * HOP / SR if voiced.any() else dur
    # longest internal silent run
    longest = 0; run = 0
    for v in voiced:
        run = 0 if v else run + 1
        longest = max(longest, run)
    internal_sil = longest * HOP / SR
    sil_ratio = float(1 - voiced.mean())
    # clipping: samples at/above 0.985 in runs of >=3
    clip = np.abs(x) >= 0.985
    clip_samples = int(clip.sum())
    # runs
    d = np.diff(np.concatenate([[0], clip.astype(np.int8), [0]]))
    starts = np.where(d == 1)[0]; ends = np.where(d == -1)[0]
    clip_runs = int(np.sum((ends - starts) >= 3)) if len(starts) else 0
    # crude loudness (RMS of voiced frames, dBFS) — not LUFS (no K-weighting); labelled honestly
    voiced_rms_db = float(np.mean(fe_db[voiced])) if voiced.any() else -99.0
    # DC offset
    dc = float(np.mean(x))
    # spectral flatness of noise-floor frames (high = hiss/broadband noise)
    quiet = fr[fe_db <= floor + 3][:200]
    flat = None
    if len(quiet):
        spec = np.abs(np.fft.rfft(quiet * np.hanning(FRAME), axis=1)) + 1e-9
        flat = float(np.mean(np.exp(np.mean(np.log(spec), axis=1)) / np.mean(spec, axis=1)))
    # fingerprint: 32-band log-energy envelope at 4 fps, quantised — for near-duplicate detection
    step = SR // 4
    env = [db(float(np.sqrt(np.mean(x[i:i + step] ** 2)) + 1e-9)) for i in range(0, max(n - step, 1), step)][:64]
    env = np.array(env); env = env - env.max() if len(env) else env
    fp = hashlib.sha1(np.round(env / 3).astype(np.int16).tobytes()).hexdigest()[:16] if len(env) else None
    return {"duration_seconds": round(dur, 3), "peak_dbfs": round(db(peak), 2), "rms_dbfs": round(db(rms), 2),
            "speech_level_dbfs": round(voiced_rms_db, 2), "noise_floor_dbfs": round(floor, 2), "snr_db_est": round(snr, 1),
            "leading_silence_s": round(lead, 2), "trailing_silence_s": round(trail, 2), "longest_internal_silence_s": round(internal_sil, 2),
            "silence_ratio": round(sil_ratio, 3), "clipped_samples": clip_samples, "clip_runs": clip_runs, "dc_offset": round(dc, 4),
            "noise_flatness": None if flat is None else round(flat, 3), "fingerprint": fp, "clipped_fraction": round(clip_samples / max(n, 1), 6)}


def derive_flags(rec):
    """QC flags from the stored raw measures. Thresholds (calibrated on the 2,544 fetched files, see
    kamadhenu_dataset/README.md): clipping = ≥0.3% of samples at full scale (archive.org Rāghavendra Vijaya
    median is 0.65%); hot_peaks = 0.03–0.3% (loud, limiter-style masters — usable but not ideal)."""
    if rec.get("decode_error"):
        return ["decode_error"]
    if rec.get("duration_seconds") is None:
        return ["not_analysed"]
    f = []
    cf = rec.get("clipped_fraction") or 0
    if cf >= 3e-3: f.append("clipping")
    elif cf >= 3e-4: f.append("hot_peaks")
    if (rec.get("peak_dbfs") or 0) < -20: f.append("low_volume")
    if (rec.get("speech_level_dbfs") or 0) < -40: f.append("very_quiet_speech")
    if (rec.get("snr_db_est") or 99) < 15: f.append("noisy_low_snr")
    if (rec.get("leading_silence_s") or 0) > 2.0: f.append("long_leading_silence")
    if (rec.get("trailing_silence_s") or 0) > 2.0: f.append("long_trailing_silence")
    if (rec.get("longest_internal_silence_s") or 0) > 3.0: f.append("long_internal_silence")
    if (rec.get("silence_ratio") or 0) > 0.5: f.append("mostly_silence")
    if (rec.get("duration_seconds") or 0) < 1.0: f.append("too_short")
    if abs(rec.get("dc_offset") or 0) > 0.02: f.append("dc_offset")
    if rec.get("noise_flatness") is not None and rec["noise_flatness"] > 0.5 and (rec.get("snr_db_est") or 99) < 25: f.append("broadband_noise_floor")
    if rec.get("ext_mismatch"): f.append("extension_mismatch")
    return f


def quality_grade(rec):
    f = set(rec.get("flags", []))
    if rec.get("decode_error"): return "F"
    if "clipping" in f or "mostly_silence" in f or "too_short" in f: return "D"
    if "noisy_low_snr" in f or "very_quiet_speech" in f: return "C"
    if f & {"low_volume", "hot_peaks", "long_leading_silence", "long_trailing_silence", "long_internal_silence", "broadband_noise_floor"}: return "B"
    sr = rec.get("sample_rate") or 0
    if sr < 22050 or (rec.get("bitrate_kbps") or 999) < 64: return "B"   # lossy/low-rate source: usable for reference, weak for training
    return "A"


def run(limit=None):
    exe = ffmpeg_exe()
    cache_p = PROCESSED / "audio_inventory_cache.json"
    cache = read_json(cache_p, {}) or {}
    files = sorted(p for p in INCOMING.rglob("*") if p.is_file() and p.suffix.lower() in AUDIO_EXT and not p.name.endswith(".part"))
    if limit: files = files[:limit]
    log(f"inventory: {len(files)} audio files under {rel(INCOMING)} (ffmpeg: {'yes' if exe else 'MISSING — install imageio-ffmpeg'})")
    rows = []; new = 0; t0 = time.time()
    for i, p in enumerate(files):
        st = p.stat()
        key = rel(p)
        c = cache.get(key)
        if c and c.get("size") == st.st_size and abs(c.get("mtime", 0) - st.st_mtime) < 1:
            rows.append(c); continue
        rec = {"path": key, "file": p.name, "folder": rel(p.parent).replace("kamadhenu_dataset/incoming_audio/", ""), "ext": p.suffix.lower(),
               "size": st.st_size, "mtime": st.st_mtime, "sha1": sha1_file(p), "analysed_at": now_ist()}
        if exe:
            info, perr = probe(p, exe); rec.update(info)
            x, derr = decode(p, exe)
            if x is None:
                rec["decode_error"] = derr or perr or "decode failed"
            else:
                rec.update(analyse(x))
        else:
            rec["decode_error"] = "ffmpeg unavailable"
        rec["ext_mismatch"] = bool(rec.get("codec") and ((rec["ext"] in (".aac", ".m4a") and "mp3" in rec["codec"]) or (rec["ext"] == ".mp3" and "aac" in rec["codec"]) or (rec["ext"] == ".wav" and rec.get("container") not in (None, "wav"))))
        cache[key] = rec; rows.append(rec); new += 1
        if new % 100 == 0:
            log(f"  analysed {new} new files ({time.time()-t0:.0f}s)"); write_json(cache_p, cache)
    # drop cache entries for files that vanished
    present = {rel(p) for p in files}
    for k in list(cache):
        if k not in present and not limit: cache.pop(k)
    write_json(cache_p, cache)
    # duplicates: exact + fingerprint
    by_sha, by_fp = {}, {}
    for r in rows:
        by_sha.setdefault(r["sha1"], []).append(r["path"])
        if r.get("fingerprint"): by_fp.setdefault(r["fingerprint"], []).append(r["path"])
    for r in rows:
        r["flags"] = derive_flags(r)
        r["exact_duplicates"] = [p for p in by_sha[r["sha1"]] if p != r["path"]]
        r["likely_duplicates"] = [p for p in by_fp.get(r.get("fingerprint"), []) if p != r["path"] and p not in r["exact_duplicates"]]
        if r["exact_duplicates"]: r.setdefault("flags", []).append("exact_duplicate")
        elif r["likely_duplicates"]: r.setdefault("flags", []).append("likely_duplicate")
        r["quality_grade"] = quality_grade(r)
    summary = {"generated_at": now_ist(), "ffmpeg": exe, "files": len(rows), "new_this_run": new,
               "total_duration_seconds": round(sum(r.get("duration_seconds") or 0 for r in rows), 1),
               "decode_errors": sum(1 for r in rows if r.get("decode_error")),
               "by_folder": {}, "by_grade": {}, "flags": {}}
    for r in rows:
        f = r["folder"].split("/")[0] + ("/" + r["folder"].split("/")[1] if "/" in r["folder"] else "")
        b = summary["by_folder"].setdefault(f, {"files": 0, "seconds": 0.0}); b["files"] += 1; b["seconds"] += r.get("duration_seconds") or 0
        summary["by_grade"][r["quality_grade"]] = summary["by_grade"].get(r["quality_grade"], 0) + 1
        for fl in r.get("flags", []): summary["flags"][fl] = summary["flags"].get(fl, 0) + 1
    for b in summary["by_folder"].values(): b["seconds"] = round(b["seconds"], 1)
    out = {"_readme": "Measured properties of every audio file under kamadhenu_dataset/incoming_audio/. Produced by tools/kamadhenu/inventory.py. 'flags' are automatic QC findings; quality_grade A–F is derived from them (A = clean ≥22.05 kHz, B = usable with caveats, C = noisy/quiet, D = clipped/silent/too short, F = undecodable).",
           "summary": summary, "files": [{k: v for k, v in r.items() if k != "mtime"} for r in rows]}
    write_json(DS / "audio_inventory.json", out)
    write_csv(DS / "audio_inventory.csv", out["files"], ["path", "folder", "file", "ext", "codec", "container", "sample_rate", "channels", "bit_depth", "bitrate_kbps", "duration_seconds", "peak_dbfs", "rms_dbfs", "speech_level_dbfs", "noise_floor_dbfs", "snr_db_est", "leading_silence_s", "trailing_silence_s", "longest_internal_silence_s", "silence_ratio", "clip_runs", "quality_grade", "flags", "exact_duplicates", "likely_duplicates", "decode_error", "size", "sha1"])
    log(f"inventory: {summary['files']} files, {summary['total_duration_seconds']/60:.1f} min, grades {summary['by_grade']}, flags {summary['flags']}")
    return out


if __name__ == "__main__":
    run(limit=int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None)
