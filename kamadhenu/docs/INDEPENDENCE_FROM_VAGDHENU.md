# Independence from Vāgdhenu (Phase 15)

Vāgdhenu (Prof. Prathosh A P, IISc; github.com/prathoshap/vagdhenu, weights huggingface.co/prathoshap/vagdhenu;
Apache-2.0) is Kamadhenu's **reference, benchmark and idea source**, not a dependency. This file records exactly
what is borrowed, so the ledger stays honest as the project grows.

## What Kamadhenu takes from Vāgdhenu, and how

| item | how it is used | licence handling |
|---|---|---|
| Serving pattern: ZeroGPU Gradio Space, model loaded inside `@spaces.GPU`, per-IP guard | copied as a *pattern*; our `tools/kamadhenu/space/app.py` is our own file derived from `demo/app.py` | Apache-2.0 attribution in the file header and in `THIRD_PARTY_NOTICES.md` of the Space bundle |
| Inference code `src/render_core.py`, `src/prep_text.py`, `src/limits.py`, reference bank | pulled into the Space bundle at a pinned commit by `build_space.sh`; never copied into this repository | Apache-2.0; NOTICES file lists it |
| Reference-audio-by-metre idea | adopted as a design: Kamadhenu will select a reference clip by the DGE metre verdict | idea, not code |
| Pronunciation transforms (visarga echo, ṝ → rū, hna metathesis, parenthetical stripping) | to be re-implemented as explicit, logged, DGE-side transforms (`frontend_gap_report.md`) | independent implementation |
| Training recipe (IndicF5 fine-tune, BigVGAN fine-tune in `training/`) | consulted for Experiment A; our pipeline follows the *upstream* F5-TTS/IndicF5 recipe first | consulted, not copied |
| Measurements (RTF 0.63, 2.5 GB VRAM, 900 MB fp16) | quoted with source in `DEPLOYMENT_REFERENCE.md` | facts |
| Voice weights `voice_steer` (the professor's own voice) | baseline and benchmark only; **never DGE production audio** | Apache-2.0 permits use; our own policy excludes it |
| Metre tables `tts_meter.py` / `chandas_labeler.py` | **not used** — the DGE Chandas engine is the analysis layer (`CHANDAS_FOR_KAMADHENU.md`) | — |
| Vāgdhenu's Sanskrit dataset | not used; our own recordings only | — |

## What is ours

The DGE Chandas engine and its 245-metre database (Chandojñānam data, AGPL-3.0, approved 18 Aug 2026), the
Kamadhenu audit toolkit, the dataset schema, validator, pilot builder, the reader integration, and every recording
in the dataset.

## Exit test

Kamadhenu is independent when the Space runs from IndicF5 (MIT) + a Kamadhenu-trained voice + our own frontend,
with Vāgdhenu's `src/` removed from the bundle. Until then the bundle carries the NOTICES file above.
