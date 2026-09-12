# kamadhenu_dataset — DGE × Vāgdhenu Sanskrit TTS audit & dataset

**Open `KAMADHENU_STATUS.html`.** Then `WHAT_I_NEED_TO_DO.md` (for the lead), `KAMADHENU_TODO.md` (dependency-ordered plan) and `DEPLOYMENT_REFERENCE.md` (how Vāgdhenu is really served — a Hugging Face ZeroGPU Space — and how Kamadhenu copies it: `tools/kamadhenu/space/`).

## One command
```
python3 tools/kamadhenu_audit.py            # regenerate everything from what is on disk (≈10 s when caches are warm)
python3 tools/kamadhenu_audit.py --fetch    # also probe the external sources and download reachable audio (≈1.3 GB)
python3 tools/kamadhenu_audit.py --offline  # no network at all
```
Requirements: Python 3.11 + `numpy`, `imageio-ffmpeg` (static ffmpeg for decoding), `soundfile` (optional), `indic_transliteration` (only for the Vāgdhenu comparison), Node ≥18 (runs the unmodified DGE Chandas engine). A Vāgdhenu clone is expected at `$VAGDHENU` (default: the session scratchpad); without it the comparison stages are skipped, everything else runs.

## Workflow for new recordings
1. copy audio into `incoming_audio/<any folder>/` (wav/mp3/m4a/flac/aac/ogg…; sub-folders fine; never modified)
2. `python3 tools/kamadhenu_audit.py`
3. open `KAMADHENU_STATUS.html` and `audio_text_mapping_review.html`
Idempotent: per-file QC and per-text Chandas results are cached (`processed/*_cache*.json`); adding 10 files tomorrow analyses 10 files.

## Layout
| path | what | committed? |
|---|---|---|
| `incoming_audio/` | originals (drop-zone + fetched) | **no** (see `.gitignore`; re-download with `--fetch`) |
| `processed/` | caches (QC measures, Chandas results) | yes |
| `external_audio_sources.json` | every URL the lead gave, probed from this environment, with what to do if blocked | yes |
| `drive_manifest.json`, `fetch_manifest.json` | what is listable / what was actually downloaded (incl. failures) | yes |
| `audio_inventory.json/.csv` | measured properties + QC flags per file | yes |
| `text_index.json` | canonical DGE units (+ DGE Chandas analysis) for the works the recordings can belong to | yes |
| `audio_text_mapping.json/.csv`, `audio_text_mapping_review.html` | mapping with confidence bands and review queue | yes |
| `mapping_overrides.json` | *you* write this: `{ "<audio path>": {"text_id": "...", "confidence": 1.0, "verified": true, "note": "..."} }` | yes |
| `chandas_coverage.json/.csv/.html` | per-metre coverage + 7 tiers | yes |
| `reference_bank.json/.csv/.html` | best/alternative recording per metre | yes |
| `metadata.jsonl/.csv`, `subsets/` | master dataset + subsets with exclusion reasons | yes |
| `dataset_health_report.json/.html` | health numbers | yes |
| `RECORDING_REQUESTS.csv` | P0–P3 recording asks derived from coverage | yes |
| `kamadhenu_gap_matrix.csv/.html` | component comparison with the fixed status vocabulary | yes |
| `chandas_comparison.md/.json`, `frontend_gap_report.md/.json` | DGE vs Vāgdhenu analyses with evidence | yes |
| `last_run.json` | when the last audit ran and which stages failed | yes |

## QC thresholds (calibrated on the first 2,544 files)
clipping ≥0.3 % samples at full scale → grade D; hot peaks 0.03–0.3 % → B; SNR <15 dB → C; leading/trailing silence >2 s, internal >3 s → B; sample rate <22.05 kHz or bitrate <64 kb/s → B. Loudness is RMS dBFS (not LUFS). Duplicates: exact = same bytes; likely = same coarse energy-envelope fingerprint.

## Honesty notes
No speech recognition or forced alignment was run — every mapping is structural (DGE's own link, filename convention, duration plausibility). Nothing was trained or rendered. Blocked sources are marked `BLOCKED_EXTERNAL_ACCESS` and were not analysed.
