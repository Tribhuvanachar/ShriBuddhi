#!/usr/bin/env python3
"""
clone_knn_vc.py  —  OPTIONAL Track B: zero-shot voice CONVERSION toward a
target voice using kNN-VC (bshall/knn-vc). This actually re-voices the
recitation to resemble your reference speaker (your "sample voice"), unlike
the DSP transform which only re-timbres generically.

No training needed (zero-shot). CPU works for a ~1-minute clip (slow: a few
minutes); a GPU is much faster. First run downloads WavLM + HiFiGAN (~hundreds
of MB) via torch.hub, so you need internet the first time.

Install (in your Codespace):
    pip install torch torchaudio soundfile numpy

Run:
    python clone_knn_vc.py --source recitation_1min.wav \
        --ref target_voice1.wav target_voice2.wav --out converted.wav

    # or just point --ref at a folder -- every audio file inside is used:
    python clone_knn_vc.py --source recitation_1min.wav \
        --ref incoming/ref/ --out converted.wav

Tips:
  * --ref = one or more clips of the TARGET voice you want to sound like
    (30–60s total of clean speech is plenty; more/varied = better).
  * Use your OWN recorded voice as the reference to avoid consent/copyright issues.
  * Keep audio clean (little BGM). 16 kHz mono is used internally.
  * Prefer passing a --ref FOLDER (or a shell glob like incoming/ref/*.mp3)
    over typing individual filenames -- files that arrived via a browser/
    mobile upload can carry invisible characters (zero-width spaces etc.)
    that look identical to the eye but never match anything you type by
    hand. Letting the OS list the real filenames sidesteps that entirely.
"""
import argparse, os, subprocess, sys, tempfile

AUDIO_EXTS = (".mp3", ".wav", ".m4a", ".flac", ".ogg")

def expand_refs(paths):
    """Directories become every audio file inside (sorted); files pass through."""
    out = []
    for p in paths:
        if os.path.isdir(p):
            found = sorted(os.path.join(p, n) for n in os.listdir(p)
                           if n.lower().endswith(AUDIO_EXTS))
            if not found:
                sys.exit(f"No audio files found in --ref folder: {p}")
            out.extend(found)
        else:
            out.append(p)
    return out

def ensure_mono16k(path, tmp_name):
    """
    WavLM (via knn-vc's get_features) doesn't downmix stereo input itself --
    a stereo file's 2 channels get treated as 2 separate batch items, giving
    a feature tensor an extra leading dim of 2 that crashes match() later
    with a confusing tensor-shape error far from the real cause. Always
    downmix + resample before handing anything to knn_vc.
    """
    out_path = os.path.join(tempfile.gettempdir(), tmp_name)
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", path,
                        "-ac", "1", "-ar", "16000", out_path],
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"Failed to downmix {path} to mono:\n{r.stderr[-1000:]}")
    return out_path

def concat_refs(paths, out_path):
    """
    Join multiple reference clips into one file. kNN-VC's get_matching_set()
    has shown real tensor-shape mismatches when given several clips of
    different lengths (e.g. "Expected size 1050 but got size 848") -- rather
    than depend on that multi-file path, feed it a single combined clip,
    which is known to work and is functionally the same "more reference
    audio" the tool wants anyway.
    """
    cmd = ["ffmpeg", "-y", "-v", "error"]
    for p in paths:
        cmd += ["-i", p]
    n = len(paths)
    filt = "".join(f"[{i}:a]" for i in range(n)) + f"concat=n={n}:v=0:a=1[out]"
    cmd += ["-filter_complex", filt, "-map", "[out]", "-ar", "16000", "-ac", "1", out_path]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"Failed to combine --ref clips with ffmpeg:\n{r.stderr[-2000:]}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, help="the recitation to convert")
    ap.add_argument("--ref", nargs="+", required=True,
                    help="target-voice reference wav(s), or a folder containing them")
    ap.add_argument("--out", default="converted.wav")
    ap.add_argument("--topk", type=int, default=4)
    ap.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    a = ap.parse_args()
    try:
        import torch, torchaudio
    except ImportError:
        sys.exit("Install first:  pip install torch torchaudio soundfile numpy")

    ref_paths = expand_refs(a.ref)
    for p in ref_paths:
        if not os.path.isfile(p):
            sys.exit(f"--ref file not found: {p}")

    source_path = ensure_mono16k(a.source, "knn_vc_source.wav")

    if len(ref_paths) > 1:
        combined = os.path.join(tempfile.gettempdir(), "knn_vc_ref_combined.wav")
        print(f"Combining {len(ref_paths)} reference clips into one "
              f"({', '.join(os.path.basename(p) for p in ref_paths)})…")
        concat_refs(ref_paths, combined)
        ref_paths = [combined]
    else:
        ref_paths = [ensure_mono16k(ref_paths[0], "knn_vc_ref_single.wav")]

    print("Loading kNN-VC (first run downloads WavLM + HiFiGAN)…")
    knn_vc = torch.hub.load("bshall/knn-vc", "knn_vc",
                            prematched=True, trust_repo=True, device=a.device)
    print(f"Extracting features from source: {a.source}")
    query = knn_vc.get_features(source_path)
    print(f"Building matching set from {len(ref_paths)} reference clip(s): "
          + ", ".join(os.path.basename(p) for p in ref_paths))
    matching = knn_vc.get_matching_set(ref_paths)
    print(f"query shape: {tuple(query.shape)}  matching shape: {tuple(matching.shape)}")
    print(f"Converting (topk={a.topk})… this can take a few minutes on CPU")
    out = knn_vc.match(query, matching, topk=a.topk)
    torchaudio.save(a.out, out[None].cpu(), 16000)
    print(f"Wrote: {a.out}")

if __name__ == "__main__":
    main()
