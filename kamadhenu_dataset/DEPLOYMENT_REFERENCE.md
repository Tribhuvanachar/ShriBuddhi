# Kamadhenu deployment reference — copy Vāgdhenu's serving model, not a GPU server

Written 6 Sep 2026 (IST) after inspecting the live deployment, not from the project page alone. Every fact
below was read from the Hugging Face API, the public Space's own `app.py`, or the Vāgdhenu repository
at commit `c18927a8` (19 Jul 2026); the two things we could not verify are listed at the end.

## 1. What Dr. Prathosh actually runs

| item | verified value | where |
|---|---|---|
| Live demo | Hugging Face Space `prathoshap/vagdhenu-demo`, Gradio SDK, stage RUNNING, 1 replica | `GET /api/spaces/prathoshap/vagdhenu-demo` |
| Hardware | **ZeroGPU** (label `zero-a10g`, requested = current); HF's docs say ZeroGPU today allocates half or a full NVIDIA RTX Pro 6000 Blackwell (48 / 96 GB) per call | same API + `hf.co/docs/hub/spaces-zerogpu` |
| GPU lifetime | `@spaces.GPU(duration=120)` around **model load + synthesis**; the GPU is attached for that call only and released after | Space `app.py` |
| Public API | Gradio endpoint `/synthesize(text, meter_choice, seed) → (Audio, Markdown)`; the Space's `demo.launch()` leaves the API on | `GET https://prathoshap-vagdhenu-demo.hf.space/gradio_api/info` |
| Guards | one śloka per request (≤ 100 akṣaras, < 2 `॥`), **10 renders per IP per day**, in-memory | `src/limits.py` |
| Weights | model repo `prathoshap/vagdhenu`, **3,001 MB**: `voice_steer_ema_2026-06-17.pt` 1.35 GB, `voice_armA_ema_2026-06-11.pt` 1.35 GB, `voc_bigvgan_EMA_2026-06-11.pth` 450 MB, `vocab.txt` 11 KB; Apache-2.0 | `GET /api/models/prathoshap/vagdhenu?blobs=true` |
| What the Space downloads | only `voice_steer` + BigVGAN (≈ 1.8 GB) via `hf_hub_download`, cached in the Space; `armA` is not used for serving | `app.py _ensure_assets()` |
| Model | IndicF5 fork of F5-TTS, 337 M DiT + BigVGAN 112 M ≈ 449 M params, ≈ 900 MB fp16; peak inference VRAM 2.5 GB | `docs/TECH_REPORT.md` E60 |
| Speed | **RTF 0.63 at nfe 32** (serving), 1.24 at nfe 64 fp32; CPU ≈ 22 min per hemistich, so GPU is mandatory | TECH_REPORT E60 |
| Cold start | first call downloads weights and loads DiT + BigVGAN: 30–60 s (the Space's own footer) | `app.py` FOOTER |
| Reference bank | 16 metres + gadya, one hemistich clip each, shipped inside the Space (`src/reference_bank/`) | Space file list |
| Also exists | `demo/server.py`: a warm single-GPU server for a dedicated A6000 box (the IISc machine) — loads once, no ZeroGPU quota wall | repo |

Vāgbodhinī (the pronunciation-feedback web app) is a separate application in the `sushrota-sanskrit-asr`
project: Vāgdhenu produces the reference chant, Su-śrotā (ASR) scores the learner. Not needed for Kamadhenu's
first stage.

## 2. ZeroGPU economics (from HF docs, 6 Sep 2026)

**Quota accounting (measured 7 Sep 2026):** the `spaces` client (0.51.3) multiplies `@spaces.GPU(duration=N)` by the
hardware's `duration_factor` before asking the quota server — 1.5 on the sm_120 Blackwell cards this Space gets — so
`duration=120` showed up to visitors as *"180s requested vs. 166s left"* and refused calls that would have used 5–14 GPU s.
Since the 7 Sep deploy `app.py` asks for `KAMADHENU_GPU_SECONDS` (default 60 → a 90 s request); the worst measured cold
start is 23 GPU s. Visitors calling from the DGE site are on the anonymous per-IP quota; signing in to Hugging Face on
the Space page itself uses the visitor's own quota.

| | |
|---|---|
| Hosting | free personal accounts (email verified, > 30 days old) may host **2 ZeroGPU Spaces**; PRO: 10 |
| Included daily GPU time for callers | unauthenticated 2 min · free account 5 min · PRO 40 min · Team 40 min · Enterprise 60 min |
| Beyond quota | PRO/Team/Enterprise only, **$1 per 10 GPU-minutes** ≈ ₹528 per GPU-hour at ₹88/$ |
| Sizes | `large` (48 GB) counts 1×, `xlarge` (96 GB) counts 2× quota; Vāgdhenu needs 2.5 GB, so `large` |
| Timeout | default 60 s per call, raise with `duration=`; Vāgdhenu uses 120 s |

The quota is charged per *caller* (the HF account or IP that invokes the Space), not per Space owner. An
anonymous visitor of a DGE page therefore gets 2 GPU-minutes a day, a logged-in free HF user 5. That is
plenty for "generate this verse" clicks, and it is why Vāgdhenu also adds its own 10/IP/day guard.

## 3. What one verse costs, measured not guessed

Vāgdhenu's bank shows one hemistich ≈ 4–12 s of audio (anuṣṭubh 4.7 s, vasantatilakā 6.6 s,
śārdūlavikrīḍita 9.4 s, sragdharā 11.8 s). A whole verse is two hemistichs, so:

| metre | audio per verse | GPU seconds at RTF 0.63 |
|---|---|---|
| anuṣṭubh | ≈ 10 s | ≈ 6 s |
| vasantatilakā / upajāti | ≈ 12–13 s | ≈ 8 s |
| śārdūlavikrīḍita | ≈ 19 s | ≈ 12 s |
| sragdharā | ≈ 24 s | ≈ 15 s |

plus the cold load (30–60 s, only when the Space has been idle). So the ChatGPT figure of "10 s per
generation" is the right order of magnitude for the warm case. Illustrative totals at $1/10 min:

| workload | GPU time | cost |
|---|---|---|
| 1,000 on-demand verses (warm, mixed metres) | ≈ 2.5 h | ≈ $15 / ₹1,300 |
| pre-render Sumadhva Vijaya (992 verses) once | ≈ 2.5 h | ≈ $15, then ₹0 per play |
| pre-render the 7,896 Kamadhenu text units once | ≈ 20 h | ≈ $120 / ₹10,600 (or free in 5-min daily slices over time) |

Pre-rendered audio is stored (jsDelivr / archive.org, as today) and costs nothing per play; only Mode 2
below burns GPU minutes.

## 4. Architecture we adopt

```
GitHub Pages (static)                     Hugging Face (free tier)
──────────────────────                    ────────────────────────────────────
render.html                            Space  SarvamulaOrg/kamadhenu     (ZeroGPU, Gradio)
js/chandas.js   ── metre name ──┐        app.py           tools/kamadhenu/space/app.py
js/kamadhenu.js ── verse text ──┼──►     src/             Vāgdhenu src @ c18927a8 (Apache-2.0)
js/audio.js     ◄── wav url ────┘        reference_bank/  Vāgdhenu bank (later: Kamadhenu voice)
                                             weights ◄─ hf_hub_download(prathoshap/vagdhenu)
```

Two modes, both served by the same Space:

* **Mode 1 — pre-generated library.** `tools/kamadhenu/space/build_space.sh` deploys the Space; a batch
  driver calls `/synthesize` for every verse of a chosen grantha, stores M4A in the audio repo, and the
  reader plays it exactly as it plays today's recordings. No GPU at play time.
* **Mode 2 — "Generate this verse".** For a verse without audio, the reader sends the text plus the DGE
  chandas verdict (the browser already runs `chandas.js`, so the Space does not re-detect the metre) and
  plays the returned WAV. Guarded by the Space's per-IP limit and the caller's ZeroGPU quota.

Two things the DGE side does differently from the demo:

1. **The metre comes from DGE.** `meter_map.json` maps DGE chandas names (245 vṛttas, vipulā-aware
   anuṣṭubh) onto the 16 bank clips; unmapped metres fall back by syllable count, and prose to `gadya`.
   Vāgdhenu's own `tts_meter.py` (13 metres, 4 wrong templates — see `chandas_comparison.md`) is bypassed.
2. **The voice is a parameter.** The Space reads `VAGDHENU_HF`/`VAGDHENU_VOICE`; when Kamadhenu has its own
   fine-tuned voice (Stage 2) the same Space serves it by changing two environment variables.

## 4a. The DGE account (done 6 Sep 2026) — Space live the same evening

**Status 6 Sep 2026, 7:36 pm IST:** `SarvamulaOrg/kamadhenu` is deployed and running on ZeroGPU. First measurements in `space_measurements.json`: 4.3 GPU s per anuṣṭubh verse warm (RTF 0.45), 23 GPU s cold. Deploy = the `Deploy — Kamadhenu Space` workflow; diagnostics = `Kamadhenu Space — logs + API probe`.


Hugging Face user **`SarvamulaOrg`** (created 6 Sep 2026, 12:49 pm IST; **PRO since 6 Sep 2026 evening**). With PRO the
30-day wait for ZeroGPU does not apply: the Space can be created now and Hardware → ZeroGPU switched on immediately
(PRO also raises the ZeroGPU quota from 5 to 40 GPU-minutes a day). Synthesis only works once that hardware is on. Deploy from GitHub Actions:
`Deploy — Kamadhenu Space` (workflow_dispatch) with the `HF_TOKEN` repository secret (a write token from that
account). Space URL once live: `https://sarvamulaorg-kamadhenu.hf.space`.

## 5. What to measure before deciding anything bigger

Run these on the deployed Space with `tools/kamadhenu/space/measure.py` (writes `kamadhenu_dataset/space_measurements.json`):

* GPU seconds per verse, per metre (warm), and the cold-start time
* queue wait at 1, 3, 10 concurrent callers
* daily generations actually requested from the site (Mode 2 counter)
* whether the 5-minute free quota ever binds for a real reader

Only if Mode 2 demand exceeds a few hundred verses a day does a warm server (Vāgdhenu's `server.py` on a rented
GPU, ₹40–80k/month) become worth discussing. Until then: **no GPU VM.**

## 6. Not verified (do not quote as fact)

* The HF *dataset* `prathoshap/vagdhenu` ("1,467 clips, 5.34 h") — the datasets API returned nothing for
  that id on 6 Sep 2026; the training data may live under another name or be private.
* Dr. Prathosh's own billing/quota tier — private; the public Space runs within whatever his account allows.
* ZeroGPU backing hardware for *this* Space — the API label is `zero-a10g`; HF's docs describe the current
  fleet as RTX Pro 6000 Blackwell. Treat the label as legacy naming, not a guarantee of either card.

## 7. Licence and courtesy

Vāgdhenu code and weights are Apache-2.0; `THIRD_PARTY_NOTICES.md` in the weights repo lists IndicF5 (MIT
vocab) and BigVGAN (MIT). The voice in `voice_steer` is Prof. Prathosh's own: fine for a baseline and for
measuring, **not** for DGE's production audio (KAMADHENU_TODO P0 #1). Do not point DGE at his public Space —
it would spend his visitors' quota and hit his 10/IP/day guard; deploy our own copy under a DGE account and
credit the project in the Space README.
