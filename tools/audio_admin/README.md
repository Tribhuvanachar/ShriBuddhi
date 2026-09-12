# DGE Audio Admin

Turn a chanting recording into **one clean audio clip per shloka** plus a
**timestamp map** — by first removing the tabla / veena / drums, then finding
the pauses in the voice.

## Why the old tool broke

The previous version listened for silence in the **raw mix**. But the
accompaniment never stops, so the mix never goes silent → it found *one* clip.
This version does the step that used to work: **separate the voice first**
(Demucs AI), find the gaps in the voice, then cut the original audio there.
Clips keep the full music; the timestamps are exact.

> ⚠️ This needs **PyTorch** (via Demucs), which installs in your Codespace /
> GitHub Action but not in a locked-down chat sandbox. Run it here.

## Quick start (GitHub Codespace)

1. Put these files at the root of your repo (or its own repo) and open a
   **Codespace**. The devcontainer auto-installs `ffmpeg` + Python deps.
   (Manual: `sudo apt-get install -y ffmpeg && pip install -r requirements.txt`)
2. Start the panel:
   ```bash
   python app.py
   ```
   Open the forwarded **port 5000**. Upload your audio, press
   **Split into shlokas**, listen to each detected shloka with ▶, then
   **Download** or **Save to DGE folder**.

## Get an exact count (the "keep trying till perfect" loop)

When you know how many shlokas the file has, let it tune itself:

```bash
python autotune.py incoming/Sarga-9.mp3 --target 62 --export out/
```

It separates the voice **once** (cached afterwards, so retries are seconds),
sweeps the silence threshold and pause length until the count hits 62, prints
every attempt, writes the winning settings to `params.json`, and exports the
clips. Not exact? It tells you and suggests trying another model
(`--models htdemucs,htdemucs_ft,mdx_extra`) or adjusting `--min-len`.

**This is the file Claude Code should run and iterate on** in the Codespace:
give it your audio + the count, and it converges automatically.

## Command-line (no target)

```bash
python engine.py incoming/Sarga-9.mp3 --out out/          # auto-detect count
python engine.py file.mp3 --out out/ --min-gap 1.2 --min-len 10
```

## GitHub Action path

Commit an audio file (e.g. `incoming/Sarga-9.mp3`), then **Actions →
"Process chanting audio" → Run workflow**, giving the path and the count. The
clips + `chunks_map.json` come back as a downloadable artifact.

## Sending results onward

- **Save to DGE folder** — writes into `output.local_dir` from `config.yaml`
  (defaults to `dge/data/audio` — point it at your real folder).
- **Push to the audio-data repo** (later) — from the Codespace terminal:
  ```bash
  ./scripts/push_to_repo.sh out/ chanting/sarga-9
  ```
  Reads `push.repo` / `push.branch` from `config.yaml`. Kept as a terminal
  script on purpose so your token never touches the browser.

## What you get

```
out/
  chunks_map.json     # {source, duration, count, chunks:[{index,name,start,end,dur}]}
  chunk_01.wav        # one file per shloka (padded by `pad` seconds)
  chunk_02.wav
  ...
```

## The knobs (all optional — auto by default)

| Setting        | Plain meaning                                   | Default |
|----------------|-------------------------------------------------|---------|
| Remove music   | isolate the voice before splitting              | on      |
| Target count   | aim for exactly N shlokas                        | off     |
| Min gap        | shortest pause that means "new shloka"          | 1.5 s   |
| Min length     | shortest a shloka can be (shorter is merged)    | 8 s     |
| Pad            | breathing room kept around each clip            | 0.1 s   |
| Silence level  | how quiet counts as a gap                       | auto    |

## Files

```
app.py            web admin panel (Flask)
engine.py         separate → detect → segment → export (the core)
autotune.py       converge to a known shloka count
templates/        the panel UI
config.yaml       output folder + push settings
scripts/          push_to_repo.sh
.devcontainer/    Codespace setup (ffmpeg + deps + port 5000)
.github/          the Action
```
