# Task for Claude Code — finish & tune the DGE Audio Admin in this Codespace

You're running inside the user's GitHub Codespace. The `audio-admin/` package is
already here (from `dge-audio-admin.zip`). Your job: get it fully working, let it
figure out the repo-specific paths itself, and tune it until it splits the sample
recording into the **exact** shloka count.

## Context (don't re-derive)
- The recording has continuous tabla/veena, so silence-detection on the raw mix
  finds ~1 segment. The fix is: **separate the voice with Demucs first**, then
  detect gaps in the voice. `engine.py` already does this. Do not undo it.
- Demucs needs PyTorch — it installs fine here (unlike the chat sandbox).

## Steps

1. **Setup**
   ```bash
   cd audio-admin
   sudo apt-get update && sudo apt-get install -y ffmpeg
   pip install -r requirements.txt
   ```

2. **Discover the paths yourself — don't ask the user.**
   - Find the real DGE audio output folder: inspect the repo tree for where
     per-shloka audio should live (look under `dge/data/`, existing audio dirs,
     or how other media is stored). Pick the best match and set
     `output.local_dir` in `config.yaml`. If none exists, create
     `dge/data/audio/` and note it.
   - Confirm the audio-data repo name for later pushing (the user referred to
     `bhumandala-audio-data`). Verify it exists (`gh repo view` or a clone
     attempt); set `push.repo` / `push.branch` / `push.subdir` in `config.yaml`.
     Leave `push.enabled: false` for now.

3. **Get the sample file.** Ask the user to drop `Sarga-9.mp3` into
   `audio-admin/incoming/` (or fetch it from wherever they point). It has
   **62 shlokas**.

4. **Tune to exactly 62.**
   ```bash
   python autotune.py incoming/Sarga-9.mp3 --target 62 --export out/
   ```
   - First run downloads the Demucs model + separates (slow, ~minutes on CPU);
     it's cached after, so retries are seconds.
   - If it doesn't hit 62 exactly, try more models:
     ```bash
     python autotune.py incoming/Sarga-9.mp3 --target 62 \
       --models htdemucs,htdemucs_ft,mdx_extra --export out/
     ```
   - Still off? Adjust `--min-len` (e.g. 6–12) — some reciters run verses
     together, or split a long verse mid-way. Report what count you *can* reach
     reliably and the settings that give it.

5. **Verify — don't trust the count blindly.**
   - Open `out/chunks_map.json`; sanity-check durations (each shloka should be
     roughly similar, no 1-second slivers or 200-second blobs).
   - Spot-check 3–4 clips by ear (start/middle/end of the file): does each clip
     begin and end at a real shloka boundary, with the whole verse intact?
   - If boundaries are cutting mid-verse, the pause threshold is too aggressive —
     nudge and re-run (it's cheap; separation is cached).

6. **Lock the good settings.** Copy the winning values from `params.json` into
   `config.yaml` `defaults:` so the web panel uses them by default.

7. **Test the panel.**
   ```bash
   python app.py
   ```
   Open the forwarded port 5000, upload the file, confirm the shloka list +
   ▶ playback + **Save to DGE folder** all work and land files in
   `output.local_dir`.

8. **Report back to the user:** the exact count achieved, the final settings,
   where files were saved, and anything about the recording that limits a clean
   split (if 62 isn't perfectly reachable, say why).

## Guardrails
- Keep separation ON. If a run says "background NOT removed", torch/demucs isn't
  installed — fix that, don't proceed on the raw mix.
- Don't commit `jobs/`, `out/`, `.voice_cache/`, or the audio files themselves
  (already in `.gitignore`).
- Don't enable pushing to the audio-data repo until the user says so.
