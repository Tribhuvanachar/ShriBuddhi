# Base model selection (Phase 7)

Facts below were read from the Hugging Face API on 6 Sep 2026 (licence tag, gating, size, languages, last update)
and from the projects' own documentation. "Sanskrit suitability" is our judgement, stated as such.

## Candidates

| model | licence | size | languages | Sanskrit | training / fine-tune recipe | reference audio | GPU for fine-tune | notes |
|---|---|---|---|---|---|---|---|---|
| **IndicF5** (ai4bharat/IndicF5) | MIT · gated (auto-accept) | 1.4 GB (337 M DiT) | 11 Indian languages, no `sa` tag | proven: Vāgdhenu fine-tuned it for Sanskrit chant | F5-TTS trainer (official `train.py`, CFM + DiT) | needs a 3–10 s prompt clip + its transcript per voice | 1× 24 GB fits; 16 GB with small batch | Indic fork of F5-TTS; Vocos vocoder by default |
| **Vāgdhenu** (prathoshap/vagdhenu) | Apache-2.0 | 3.1 GB (2 voices 1.35 GB each + BigVGAN 450 MB) | `sa` | yes, metre-aware chant; 16-metre reference bank | IndicF5 fine-tune (`training/`), BigVGAN fine-tune | same as IndicF5 | same | voice = Prof. Prathosh's own; weights redistributable, voice not appropriate for DGE production |
| F5-TTS base (SWivid/F5-TTS) | **CC-BY-NC-4.0** (weights) | 1.3 GB | zh, en | no | official | yes | same | non-commercial weights — not for DGE deployment; code is MIT |
| Indic Parler-TTS (ai4bharat/indic-parler-tts) | Apache-2.0 · gated | 3.8 GB (≈ 0.9 B) | 21 Indian languages, no `sa` | untested; description-controlled voices, no chant prosody control | Parler trainer (official) | none (text description of the voice) | 1× 24–40 GB | heavier, slower; prosody by prompt, not by metre |
| VITS Rasa 13 (ai4bharat/vits_rasa_13) | CC-BY-4.0 · gated | 161 MB | 13 languages **including `sa`** | trained on Sanskrit read speech; expressive "rasa" tags | VITS (Coqui/espnet style), cheap | none | 1× 8–16 GB | small and fast; no reference-audio control; quality below flow-matching models |
| MMS-TTS (facebook/mms-tts-*) | CC-BY-NC-4.0 | 145 MB per language | 1,100 languages, `san` exists | crude read speech, single voice | VITS | none | small | non-commercial |
| XTTS-v2, Kokoro, Fish-Speech | other / Apache / CC-BY-NC-SA | — | no Sanskrit | no | — | — | — | excluded |
| hobby "Sanskrit TTS" uploads (SpeechT5, Rasa forks) | various | small | sa | 0 downloads, no docs | — | — | — | excluded |

Inference speed: F5-class models run at RTF ≈ 0.6 at 32 steps on a modern GPU (Vāgdhenu's measurement), VITS-class
< 0.05. Peak VRAM for F5 inference ≈ 2.5 GB.

## Recommendation

**BASE MODEL = IndicF5 (MIT), fine-tuned on Kamadhenu data, with Vāgdhenu used as the benchmark and as the source of
the training recipe.**

In simple words: IndicF5 is the only permissively licensed, already-Indian-language model that has been shown to
learn Sanskrit chant (that is what Vāgdhenu did), it can be trained on a single mid-range GPU, and it takes a short
reference recording, which is exactly how we will control metre and voice. Its base weights and the fine-tuned
result can be redistributed and used on the public DGE site. F5-TTS itself is out because its weights are
non-commercial; Parler is out because prosody is steered by text descriptions, not by a reference chant; VITS Rasa 13
is worth a cheap side experiment as a fast "reading voice" but cannot follow a metre reference.

Two decisions this leaves to the owner (Stop condition 2, licence): none blocking — MIT and Apache-2.0 both allow
our use. Attribution lines go into `docs/INDEPENDENCE_FROM_VAGDHENU.md` and the model card.

## What "fine-tune" will mean for Experiment A (Phase 12), for cost planning later

* Start from IndicF5 weights (not from Vāgdhenu's voice).
* Data: the pilot set (100–200 examples, 10–20 min of audio) in the F5 format (`wav | text` metadata, 24 kHz).
* Recipe: the upstream F5-TTS `train.py` with IndicF5's vocab; a few thousand steps.
* GPU: one 16–24 GB card is enough. Cost estimate will be given before anything is launched; ZeroGPU is for
  inference, not training.
