#!/usr/bin/env python3
"""
tts_clone.py -- zero-shot TEXT-TO-SPEECH in a cloned voice, using Coqui
XTTS-v2. Different from clone_knn_vc.py: that one CONVERTS an existing
recording into a target voice (frame-matching, loses melody); this one
GENERATES new speech straight from typed text, in a voice built from a
short reference clip.

Expected to work much better than kNN-VC for plain (non-melodic) speech
like ordinary spoken narration -- there's no original pitch contour to
lose, since it's synthesizing from scratch rather than re-stitching
existing audio.

Language support: XTTS-v2 natively supports English (plus ~16 other
languages) but has NO dedicated Sanskrit checkpoint -- no mainstream
open TTS toolkit does, as of this writing. Sanskrit text can be tried
through the "hi" (Hindi) language mode as the closest practical
approximation (shared Devanagari script, related phonology). Treat that
as a real experiment to judge by ear, not an assumption it will sound
right -- Sanskrit's retroflex/aspirate distinctions and vowel length
don't map perfectly onto Hindi's phoneme set.

License note: XTTS-v2 ships under Coqui's CPML (non-commercial use,
attribution required) -- fine for a project like DGE's own site, but
worth knowing before any commercial use.

Install (in your Codespace -- this is a large download, budget time):
    pip install TTS

Run:
    python tts_clone.py --text "Hello, this is a test of the voice." \
        --lang en --ref incoming/ref/ --out out/tts_en_test.wav

    python tts_clone.py --text "क्षमस्व मम अपराधम्" \
        --lang hi --ref incoming/ref/ --out out/tts_sa_test.wav
"""
import argparse, os, sys

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

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", required=True, help="text to speak")
    ap.add_argument("--lang", default="en",
                    help="XTTS-v2 language code: en, hi, es, fr, de, it, pt, pl, tr, ru, "
                         "nl, cs, ar, zh-cn, hu, ko, ja -- use 'hi' as the closest "
                         "approximation for Sanskrit/Devanagari text")
    ap.add_argument("--ref", nargs="+", required=True,
                    help="reference voice clip(s), or a folder containing them")
    ap.add_argument("--out", default="out/tts.wav")
    a = ap.parse_args()

    ref_paths = expand_refs(a.ref)
    for p in ref_paths:
        if not os.path.isfile(p):
            sys.exit(f"--ref file not found: {p}")

    try:
        from TTS.api import TTS
    except ImportError:
        sys.exit("Install first:  pip install TTS")

    out_dir = os.path.dirname(os.path.abspath(a.out))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    print("Loading XTTS-v2 (first run downloads the model, ~1.8GB)…")
    tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to("cpu")

    print(f"Generating speech (lang={a.lang}) using {len(ref_paths)} reference clip(s): "
          + ", ".join(os.path.basename(p) for p in ref_paths))
    tts.tts_to_file(text=a.text, speaker_wav=ref_paths, language=a.lang, file_path=a.out)
    print(f"Wrote: {a.out}")

if __name__ == "__main__":
    main()
