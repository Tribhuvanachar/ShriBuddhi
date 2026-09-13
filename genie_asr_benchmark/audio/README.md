# Genie ASR benchmark — audio (kept off `main`)

This branch holds real recorded voice-command audio for the DGE Genie ASR
benchmark (see `genie_asr_benchmark/` on `main` for the harness, resolver,
and manifest these clips are scored against). Personal voice recordings —
same reasoning as `wordnet-dist`/`dasa-sahitya-local-dist`: kept off `main`
rather than published on the public site.

## Layout

Mirrors `genie_asr_benchmark/manifests/manifest.json`'s category structure
on `main`:

```
audio/
  01_english/
    sumadhwa_test.wav   -- MP4/AAC-LC container despite the .wav extension,
                            8kHz mono ~12kbps. "Open Sumadhwa Vijaya 1.1".
                            Sarvam Saaras v3 REST (en-IN): "Sumadhwa Vijaya 1.1"
                            -- matches manifest entry 01_english_002.
    sumadhwa_16k.m4a     -- MP4/AAC-LC, 16kHz mono, 64kbps. Same phrase,
                            noisier recording. Sarvam Saaras v3 REST (en-IN):
                            "Sumadha Open Sumadha Vijaya 1.1" -- matches
                            manifest entry 01_english_003's asr_noise_variant.
                            Both real transcripts verified 28 Aug 2026 and
                            fed through resolver.js end-to-end: both
                            correctly resolve to
                            open_text/kavya_alankara/sumadhva_vijaya/sarga_1,
                            reference "1.1".
```

Provided by the project lead 28 Aug 2026 (originally staged at
`_seed_uploads/` on this same branch by an earlier relay commit; folded
into the real category structure here). Two clips only — this is NOT the
full ~50-100 utterance benchmark corpus `genie_asr_benchmark/reports/
findings.md` on `main` still asks for. See that report for exactly what
categories/languages/counts are still needed.

To use: `git fetch origin genie-asr-audio-seed`, then read files out of it
(e.g. `git show origin/genie-asr-audio-seed:genie_asr_benchmark/audio/01_english/sumadhwa_test.wav > /tmp/x.wav`)
or check it out into a scratch worktree — do not merge this branch into
`main`.
