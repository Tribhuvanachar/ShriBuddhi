---
title: Kamadhenu — DGE Sanskrit chant
emoji: 🐄
colorFrom: yellow
colorTo: red
sdk: gradio
sdk_version: 5.49.1
app_file: app.py
pinned: false
license: apache-2.0
short_description: Metre-aware Sanskrit chant TTS for the Sarvamula Library
---

# Kamadhenu Space (ZeroGPU)

The DGE serving layer for Sanskrit chant, deployed exactly the way Dr. Prathosh's public Vāgdhenu demo is
deployed (see `kamadhenu_dataset/DEPLOYMENT_REFERENCE.md`): a Hugging Face **ZeroGPU** Gradio Space that
attaches a GPU only while a verse is being synthesised. The static site stays static; the 3 GB of weights
stay on Hugging Face.

This folder holds only DGE's own files. The Vāgdhenu code it runs on (`src/`, Apache-2.0) is pulled at a pinned
commit by `build_space.sh`, never vendored into this repository.

```
app.py            Gradio app: /synthesize(text, dge_chandas, seed) → (wav, json)   [DGE]
meter_map.json    DGE chandas name → Vāgdhenu bank key                              [DGE]
requirements.txt  ZeroGPU deps (torch 2.8, IndicF5 fork at its production commit)  [copied from vagdhenu/demo]
build_space.sh    clone vagdhenu@c18927a8, assemble ./dist, upload to the Space     [DGE]
measure.py        call the deployed Space, record GPU seconds per metre             [DGE]
```

## Deploy (one-time, from any laptop; no GPU needed locally)

```bash
pip install huggingface_hub
huggingface-cli login                                   # the DGE account (free tier: 2 ZeroGPU Spaces)
bash tools/kamadhenu/space/build_space.sh SarvamulaOrg/kamadhenu     # or run the GitHub Action 'Deploy — Kamadhenu Space'
```

Then in the Space settings choose **Hardware → ZeroGPU** (the `SarvamulaOrg` account is PRO since 6 Sep 2026, so ZeroGPU is available immediately). The first call downloads
`voice_steer_ema_2026-06-17.pt` + `voc_bigvgan_EMA_2026-06-11.pth` from `prathoshap/vagdhenu` (≈ 1.8 GB,
cached afterwards) and loads them onto the GPU (30–60 s); later calls take a few seconds.

Environment variables (Space → Settings → Variables): `VAGDHENU_HF`, `VAGDHENU_VOICE`, `VAGDHENU_VOC` select
the weights — this is how Kamadhenu's own voice replaces the baseline later without touching code.
`KAMADHENU_DAILY_LIMIT` (default 10) is the per-IP guard.

## Call it

```
POST https://sarvamulaorg-kamadhenu.hf.space/gradio_api/call/synthesize   {"data": ["<verse>", "<dge chandas or ''>", 60]}
GET  https://sarvamulaorg-kamadhenu.hf.space/gradio_api/call/synthesize/<event_id>   (SSE; 'complete' carries [audio, meta])
```

`dge/js/kamadhenu.js` does exactly this from the reader once `appConfig.kamadhenuSpaceUrl` is set.
