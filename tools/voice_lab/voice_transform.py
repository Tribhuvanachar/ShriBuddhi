#!/usr/bin/env python3
"""
voice_transform.py  —  lightweight female->male (or any) voice re-timbre.

Pure numpy + scipy. No GPU, no model downloads. CPU-only, runs a 1-minute
clip in a few seconds. It does TWO things that together change the perceived
voice/gender while KEEPING the words and the tempo:

  1. formant shift  — warps the spectral envelope down the frequency axis
                       (lowers the vocal-tract resonances -> deeper/male timbre)
  2. pitch shift    — lowers the fundamental (phase-vocoder, tempo preserved)

This is a signal-processing transform, not AI cloning: it will not copy a
specific person's voice, but a female recitation with --pitch -5 --formant 1.15
sounds clearly deeper / more male, and it is copyright-clean.

Usage:
  python voice_transform.py in.wav out.wav --pitch -5 --formant 1.15
  python voice_transform.py in.wav out.wav --preset male
  python voice_transform.py in.wav out.wav --preset male --pitch -6   # override

Presets:  male (-5 st, 1.15) | deepmale (-7, 1.22) | slightly (-3, 1.08) | higher (+3, 0.92)
"""
import argparse, sys, numpy as np
from scipy.io import wavfile

# ---------- io ----------
def read_wav(path):
    sr, x = wavfile.read(path)
    if x.dtype == np.int16:   x = x.astype(np.float32)/32768.0
    elif x.dtype == np.int32: x = x.astype(np.float32)/2147483648.0
    elif x.dtype == np.uint8: x = (x.astype(np.float32)-128)/128.0
    else:                     x = x.astype(np.float32)
    if x.ndim == 2: x = x.mean(axis=1)   # mono
    return sr, x

def write_wav(path, sr, x):
    x = np.clip(x, -1, 1)
    wavfile.write(path, sr, (x*32767).astype(np.int16))

# ---------- stft ----------
def stft(x, n=2048, hop=512):
    w = np.hanning(n).astype(np.float32)
    frames = 1 + max(0, (len(x)-n)//hop)
    S = np.empty((frames, n//2+1), np.complex64)
    for i in range(frames):
        seg = x[i*hop:i*hop+n]*w
        S[i] = np.fft.rfft(seg)
    return S, w

def istft(S, w, hop=512):
    n = (S.shape[1]-1)*2
    out = np.zeros((S.shape[0]-1)*hop+n, np.float32)
    win = np.zeros_like(out)
    for i in range(S.shape[0]):
        seg = np.fft.irfft(S[i]).astype(np.float32)
        out[i*hop:i*hop+n] += seg*w
        win[i*hop:i*hop+n] += w*w
    win[win < 1e-6] = 1e-6
    return out/win

# ---------- formant (spectral-envelope) warp ----------
def spectral_envelope(mag, lifter=30):
    logm = np.log(mag + 1e-6)
    cep = np.fft.irfft(logm, axis=-1)
    L = cep.shape[-1]
    win = np.zeros(L); win[:lifter] = 1.0; win[-lifter+1:] = 1.0 if lifter>1 else 0.0
    env = np.exp(np.fft.rfft(cep*win, axis=-1).real)
    return np.maximum(env, 1e-6)

def formant_shift(S, alpha):
    """alpha>1 => formants move DOWN (more male). alpha<1 => up."""
    if abs(alpha-1.0) < 1e-3: return S
    mag = np.abs(S); env = spectral_envelope(mag)
    K = S.shape[1]; f = np.arange(K)
    src = np.clip(f*alpha, 0, K-1)          # new_env[f] = env[f*alpha]
    i0 = np.floor(src).astype(int); frac = (src-i0).astype(np.float32); i1 = np.minimum(i0+1, K-1)
    warped = env[:, i0]*(1-frac) + env[:, i1]*frac
    gain = warped/env                       # apply envelope ratio, keep harmonics/phase
    return S*gain.astype(np.float32)

# ---------- pitch shift (phase vocoder time-stretch + resample) ----------
def phase_vocoder_stretch(x, R, n=2048, hop=512):
    S, w = stft(x, n, hop)
    frames, K = S.shape
    hop_s = int(round(hop*R))
    out_len = (frames-1)*hop_s + n
    out = np.zeros(out_len, np.float32); win = np.zeros(out_len, np.float32)
    last = np.zeros(K); acc = np.angle(S[0]) if frames else np.zeros(K)
    omega = 2*np.pi*hop*np.arange(K)/n
    for i in range(frames):
        mag = np.abs(S[i]); ph = np.angle(S[i])
        if i == 0:
            acc = ph.copy()
        else:
            d = ph - last - omega
            d = d - 2*np.pi*np.round(d/(2*np.pi))
            acc = acc + (omega + d)*R
        last = ph
        frame = np.fft.irfft(mag*np.exp(1j*acc)).astype(np.float32)
        so = i*hop_s
        out[so:so+n] += frame*w; win[so:so+n] += w*w
    # At the very start/end of the buffer, only a partial (tapered-near-zero)
    # slice of the Hann window has been accumulated into `win`, so dividing
    # by it there amplifies noise by orders of magnitude -- a single such
    # sample can dominate the whole clip's peak and (via transform()'s
    # peak-normalize) crush everything else to near-silence. Floor `win`
    # relative to its own typical (interior) value, not an absolute
    # epsilon, and let those few under-covered edge samples fall to zero
    # instead of exploding -- inaudible at the very edge, unlike the
    # alternative.
    typical = np.median(win[win > 1e-6]) if np.any(win > 1e-6) else 1.0
    out[win < typical * 0.1] = 0.0
    win[win < typical * 0.1] = typical
    return out/win

def resample_linear(x, target):
    idx = np.linspace(0, len(x)-1, target)
    i0 = np.floor(idx).astype(int); frac = idx-i0; i1 = np.minimum(i0+1, len(x)-1)
    return (x[i0]*(1-frac) + x[i1]*frac).astype(np.float32)

def pitch_shift(x, semitones):
    if abs(semitones) < 1e-3: return x
    factor = 2**(semitones/12.0)
    stretched = phase_vocoder_stretch(x, factor)     # duration * factor
    return resample_linear(stretched, len(x))        # back to length -> pitch * factor

# ---------- driver ----------
PRESETS = {
    "male":     (-5.0, 1.15),
    "deepmale": (-7.0, 1.22),
    "slightly": (-3.0, 1.08),
    "higher":   ( 3.0, 0.92),
    "none":     ( 0.0, 1.00),
}

def transform(x, sr, semitones, formant):
    # 1) formant warp (timbre)
    if abs(formant-1.0) > 1e-3:
        S, w = stft(x); S = formant_shift(S, formant); x = istft(S, w)
    # 2) pitch shift
    x = pitch_shift(x, semitones)
    # A raw np.max here is one bad sample away from crushing the whole
    # clip's loudness (exactly what the phase-vocoder edge case above did
    # before it was fixed) -- normalize against a high percentile instead
    # of the true max, then hard-clip the rare outlier above it, so one
    # freak sample can no longer dictate the volume of everything else.
    p999 = np.percentile(np.abs(x), 99.9) + 1e-9
    if p999 > 0.98:
        x = x / p999 * 0.98
    x = np.clip(x, -1.0, 1.0)
    return x

def main():
    ap = argparse.ArgumentParser(description="Lightweight female->male voice re-timbre (numpy/scipy).")
    ap.add_argument("input"); ap.add_argument("output")
    ap.add_argument("--preset", choices=list(PRESETS), default=None)
    ap.add_argument("--pitch", type=float, default=None, help="semitones (negative = deeper)")
    ap.add_argument("--formant", type=float, default=None, help=">1 lowers formants (more male)")
    a = ap.parse_args()
    semi, form = PRESETS.get(a.preset, (-5.0, 1.15)) if a.preset else (-5.0, 1.15)
    if a.pitch   is not None: semi = a.pitch
    if a.formant is not None: form = a.formant
    sr, x = read_wav(a.input)
    print(f"in: {a.input}  sr={sr}  dur={len(x)/sr:.1f}s  -> pitch {semi:+.1f} st, formant x{form:.2f}")
    y = transform(x, sr, semi, form)
    write_wav(a.output, sr, y)
    print(f"wrote: {a.output}  dur={len(y)/sr:.1f}s")

if __name__ == "__main__":
    main()
