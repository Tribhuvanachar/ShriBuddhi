# Vedavani (Hugging Face) — Rigveda recitation clips, mapped to DGE ṛk ids

**Source** `sanganaka/Vedavani-Dataset` on Hugging Face (IIT Kharagpur, ACL 2025,
arXiv:2506.00145), licence Apache-2.0. The audio is Veda Prasara Samiti's complete Rigveda /
Atharvaveda chanting from archive.org (`RigvedaChanting`, `atharvaveda_202107`, Public Domain
Mark 1.0), cut by the paper's authors into 30,779 clips (16 kHz mono 16-bit WAV, ~6.8 GB) with
a Devanagari text per clip. Not related to the VedaVaNi Android app (`tools/vedavani/`).

**What is committed here** (audio is never committed):

| file | what |
|---|---|
| `manifest.csv.gz` | one row per clip: `hf_path` (append to `https://huggingface.co/datasets/sanganaka/Vedavani-Dataset/resolve/main/`), LFS `sha256`, `bytes`, `length_s`, `text`, `match`, `rik_ids` (DGE `mandala.sukta.rik`, `;`-joined when a clip spans two ṛks) |
| `summary.json` | counts, hours, match statistics, provenance |
| `verify_sample.json` | the random-clip verification run (HTTP 200, RIFF/WAVE, size, sha256, duration) |

**Match kinds** `exact` (text is a unique substring of the accent-stripped DGE saṃhitā),
`exact_span` (unique, crosses a ṛk boundary), `resolved` (text occurs in several ṛks — refrains —
resolved by the neighbouring clips of the same recording, which run in text order), `fuzzy`
(≥ 0.85 character overlap with a candidate window), `ambiguous` (unresolvable; `rik_ids` lists the
candidates `|`-separated), `unmatched`, `too_short` (< 8 letters).

**Tool** `tools/vedavani_hf/vedavani_corpus.py` — `build-manifest`, `verify`, `fetch`, `mirror`.
Workflow `.github/workflows/vedavani-hf-corpus.yml`. Local downloads go to
`kamadhenu_dataset/incoming_audio/vedavani_hf/` (gitignored).

**Caveats for Kamadhenu training** the recordings are group recitation (several voices in
unison) at 16 kHz; the texts carry no svara marks; clips are pādas / half-ṛks, not whole ṛks.
Good for a Vedic-accent *style* reference bank and for ASR checks, not a single-speaker voice.
