# DGE Voice Lab — turn a female recitation into a male (or custom) voice

Two ways to change the voice of an existing recitation, both runnable in a
CPU-only GitHub Codespace. Start with **Track A** (instant, no downloads);
move to **Track B** only if you want it to resemble a specific target voice.

The words and the timing/tempo are always preserved — only the voice changes.

---

## Track A — `voice_transform.py`  (lightweight, recommended first)

Pure **numpy + scipy**. No AI models, no GPU, no downloads. A 1-minute clip
processes in a few seconds. It lowers the **pitch** and shifts the **formants**
(vocal-tract resonances) down together, which is what actually makes a voice
sound male rather than just "pitched down".

### Setup (Codespace)
```bash
pip install numpy scipy
```

### Use
```bash
# quick start with the "male" preset
python voice_transform.py input.wav output.wav --preset male

# hand-tune (this is where you experiment on your 1-min sample):
python voice_transform.py input.wav output.wav --pitch -5 --formant 1.15
```

- `--pitch`   semitones; **negative = deeper** (male ≈ −4 to −7).
- `--formant` **>1 lowers** the formants (more male). Try 1.10–1.25.
- Presets: `male` (−5, 1.15) · `deepmale` (−7, 1.22) · `slightly` (−3, 1.08) · `higher` (+3, 0.92).

### Tuning guide for your experiment
1. Start `--preset male`. Listen.
2. Too "chipmunk / hollow"? increase `--formant` (e.g. 1.20) and/or lower `--pitch` (−6).
3. Too muffled/robotic? reduce `--formant` toward 1.08–1.10.
4. Sweet spot for most female→male is around `--pitch -5 --formant 1.15`.

Input can be wav (any sample rate, mono or stereo → mono). For mp3, convert
first: `ffmpeg -i in.mp3 in.wav`. Output is 16-bit wav; make mp3 with
`ffmpeg -i output.wav output.mp3`.

**What it is / isn't:** a signal-processing re-timbre. It gives a convincing
generic male voice and is copyright-clean, but it does **not** copy a specific
person's voice. For that, use Track B.

---

## Track B — `clone_knn_vc.py`  (optional, AI voice conversion)

Zero-shot **voice conversion** with [kNN-VC](https://github.com/bshall/knn-vc):
it re-voices the recitation to resemble a **reference voice you provide**
(e.g. your own recorded voice). No training. CPU works for short clips (slow,
a few minutes); GPU is much faster. First run downloads WavLM + HiFiGAN
(~hundreds of MB), so it needs internet once.

### Setup
```bash
pip install torch torchaudio soundfile numpy
```

### Use
```bash
python clone_knn_vc.py \
  --source recitation_1min.wav \
  --ref    my_voice_sample1.wav my_voice_sample2.wav \
  --out    converted.wav
```
- `--ref` = 30–60s of the **target** voice (use **your own** voice to avoid
  consent/copyright issues). More/varied reference = better match.
- Keep audio clean (minimal background music) and speech-only for best results.

### Resource notes for Codespaces
- Model download + load needs ~2–3 GB free disk and a few GB RAM.
- 2-core CPU: expect a couple of minutes per minute of audio. Fine for
  experiments; for batch-converting a whole corpus, do it on a GPU box.
- If a Codespace feels too tight, the same script runs in Google Colab
  (free GPU) unchanged.

### Alternatives (same idea, if you want to compare quality later)
- **seed-vc** — zero-shot VC, very good quality.
- **OpenVoice v2** — tone-color conversion / cloning.
- **RVC** — best quality but needs training a model per target voice (GPU).

---

## Suggested workflow for DGE
1. Cut a **1-minute** sample of one recitation (use the timestamp tool's clip
   download).
2. Run **Track A** with a few `--pitch/--formant` settings; pick what you like.
3. If you need it to sound like a *specific* male voice, record ~1 min of that
   voice and run **Track B** with it as `--ref`.
4. Once happy, batch-process the shloka clips and upload the converted audio
   back into DGE.

_Consent/copyright: cloning a real person's voice needs their permission. A
generic male target (or your own voice) keeps you clear._
