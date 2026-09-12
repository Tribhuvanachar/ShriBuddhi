#!/usr/bin/env python3
"""
compare_separation.py -- run the SAME recording through multiple Demucs
separation models and export each one's voice-only track, so you can
listen side-by-side and pick whichever leaves the LEAST background
(vina/tabla/etc) bleeding through the pauses between shlokas.

    python compare_separation.py incoming/Sarga-9-sample.mp3 \
        --models htdemucs,htdemucs_ft,mdx_extra --out out/separation_compare/

Each model's separation is cached (same cache autotune.py uses), so
re-running with a different --models list only computes the new ones --
the slow part never gets redone for a model already tried.
"""
import argparse, os, shutil, sys, tempfile
import engine as E

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--models", default="htdemucs,htdemucs_ft,mdx_extra",
                    help="comma list of demucs models to compare")
    ap.add_argument("--cache", default=".voice_cache")
    ap.add_argument("--out", default="out/separation_compare")
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    for model in [m.strip() for m in a.models.split(",") if m.strip()]:
        print(f"[compare] separating with '{model}' (slow the first time, cached after)…")
        work = tempfile.mkdtemp(prefix="compare_")
        try:
            voice, separated = E.separate_voice(a.src, work, model, enable=True, cache_dir=a.cache)
            if not separated:
                print(f"[compare] '{model}' failed to separate -- skipping "
                      f"(check that this is a valid demucs model name)", file=sys.stderr)
                continue
            full_voice = E.cached_voice_path(a.src, model, a.cache)
            dest = os.path.join(a.out, f"{model}_voice_only.wav")
            if os.path.exists(full_voice):
                shutil.copyfile(full_voice, dest)
                print(f"[compare] wrote {dest}")
            else:
                print(f"[compare] WARNING: expected cache file missing for '{model}': "
                      f"{full_voice}", file=sys.stderr)
        finally:
            shutil.rmtree(work, ignore_errors=True)

    print(f"\n[compare] Done. Listen to the files in {a.out}/ -- pick whichever has "
          f"the least background bleed during the pauses between shlokas.")

if __name__ == "__main__":
    main()
