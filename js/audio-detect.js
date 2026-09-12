/*
 * audio-detect.js — shloka boundary detection for the DGE Audio Admin.
 *
 * WHY THIS FILE EXISTS
 * --------------------
 * The browser tool detected boundaries from the BROADBAND ENERGY of the raw
 * mix. On a recording with continuous tabla or veena that cannot work, and it
 * fails in the most confusing way possible: the accompaniment never stops, so
 * no frame ever drops below the silence threshold, and the whole recording
 * comes back as ONE segment. Turning the dB knob does not help — there is no
 * threshold that separates "voice + drone" from "drone", because the drone is
 * the same loudness in both.
 *
 * The Python engine solves this by separating the voice with Demucs first and
 * looking for gaps in the clean vocal track. That is the right pipeline and it
 * is preserved (tools/audio_admin/engine.py) — but Demucs cannot run in a
 * browser, which is why the web tool regressed to the raw mix in the first
 * place.
 *
 * WHAT THIS DOES INSTEAD
 * ----------------------
 * Not source separation — background *suppression*, which is enough to find
 * gaps and runs in a browser in a few seconds:
 *
 *   1. STFT of the mono signal.
 *   2. Keep only the vocal band (default 200–3500 Hz). The tabla's body is
 *      mostly below it; cymbal-ish transients mostly above.
 *   3. Per frequency bin, estimate the STATIONARY background as a low
 *      percentile over a long rolling window (default 3 s) and subtract it.
 *      This is the key step, and the reason the original approach failed:
 *      a drone is stationary, so its own rolling floor equals itself and it
 *      cancels; a voice fluctuates on a syllable timescale, so it survives.
 *      (Classic minimum-statistics noise estimation, à la Martin 2001.)
 *   4. Sum the residual across the band -> an envelope in dB where the voice
 *      pauses are visible again.
 *   5. Feed that envelope into the SAME adaptive threshold + Otsu gap logic
 *      the tool already used. That logic was fine; it was being fed the wrong
 *      signal.
 *
 * Runs in the browser (attaches window.DGEAudioDetect) and in Node
 * (module.exports), so the regression is covered by a test rather than by
 * reloading a page and squinting at it.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.DGEAudioDetect = factory();
}(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  var DEFAULTS = {
    frameSize: 512,         // STFT window, samples @ working rate
    hopSize: 256,           // 16 ms @ 16 kHz
    workRate: 16000,        // decimate to this before analysis
    bandLowHz: 300,
    bandHighHz: 3500,
    noisePercentile: 5,     // low percentile across the WHOLE file = the drone
    minLenSec: 8.0,
    minGapSec: 1.5,
    padSec: 0.10,
    method: 'voice'         // 'voice' (default) | 'broadband' (the old behaviour)
  };

  function extend(base, over) {
    var o = {}, k;
    for (k in base) if (Object.prototype.hasOwnProperty.call(base, k)) o[k] = base[k];
    for (k in (over || {})) if (over[k] !== undefined && over[k] !== null) o[k] = over[k];
    return o;
  }

  // ------------------------------------------------------------------ dsp

  function toMono(channels) {
    if (channels.length === 1) return channels[0];
    var n = channels[0].length, out = new Float32Array(n), c, i;
    for (i = 0; i < n; i++) {
      var s = 0;
      for (c = 0; c < channels.length; c++) s += channels[c][i];
      out[i] = s / channels.length;
    }
    return out;
  }

  /* Decimate by an integer factor with a short box pre-filter. Analysis only —
     the exported clips are always cut from the ORIGINAL audio, so this never
     touches output quality. */
  function decimate(x, srcRate, dstRate) {
    var factor = Math.max(1, Math.floor(srcRate / dstRate));
    if (factor === 1) return { data: x, rate: srcRate };
    var n = Math.floor(x.length / factor), out = new Float32Array(n);
    for (var i = 0; i < n; i++) {
      var acc = 0;
      for (var j = 0; j < factor; j++) acc += x[i * factor + j];
      out[i] = acc / factor;
    }
    return { data: out, rate: srcRate / factor };
  }

  function hann(n) {
    var w = new Float32Array(n);
    for (var i = 0; i < n; i++) w[i] = 0.5 - 0.5 * Math.cos(2 * Math.PI * i / (n - 1));
    return w;
  }

  /* Iterative in-place radix-2 FFT. n must be a power of two. */
  function fft(re, im) {
    var n = re.length, i, j, k;
    for (i = 1, j = 0; i < n; i++) {
      var bit = n >> 1;
      for (; j & bit; bit >>= 1) j ^= bit;
      j ^= bit;
      if (i < j) {
        var tr = re[i]; re[i] = re[j]; re[j] = tr;
        var ti = im[i]; im[i] = im[j]; im[j] = ti;
      }
    }
    for (var len = 2; len <= n; len <<= 1) {
      var ang = -2 * Math.PI / len;
      var wr = Math.cos(ang), wi = Math.sin(ang);
      for (i = 0; i < n; i += len) {
        var cr = 1, ci = 0;
        for (k = 0; k < len / 2; k++) {
          var ur = re[i + k], ui = im[i + k];
          var vr = re[i + k + len / 2] * cr - im[i + k + len / 2] * ci;
          var vi = re[i + k + len / 2] * ci + im[i + k + len / 2] * cr;
          re[i + k] = ur + vr; im[i + k] = ui + vi;
          re[i + k + len / 2] = ur - vr; im[i + k + len / 2] = ui - vi;
          var ncr = cr * wr - ci * wi;
          ci = cr * wi + ci * wr; cr = ncr;
        }
      }
    }
  }

  function nextPow2(n) { var p = 1; while (p < n) p <<= 1; return p; }

  /* Magnitude spectrogram restricted to [binLo, binHi). */
  function spectrogram(x, rate, opts) {
    var N = nextPow2(opts.frameSize), hop = opts.hopSize, w = hann(N);
    var frames = Math.max(0, 1 + Math.floor((x.length - N) / hop));
    var binLo = Math.max(1, Math.floor(opts.bandLowHz / rate * N));
    var binHi = Math.min(N / 2, Math.ceil(opts.bandHighHz / rate * N));
    var bins = Math.max(1, binHi - binLo);
    var mag = new Float32Array(frames * bins);
    var re = new Float64Array(N), im = new Float64Array(N);
    for (var f = 0; f < frames; f++) {
      var off = f * hop, i;
      for (i = 0; i < N; i++) { re[i] = x[off + i] * w[i]; im[i] = 0; }
      fft(re, im);
      for (i = 0; i < bins; i++) {
        var b = binLo + i;
        mag[f * bins + i] = Math.sqrt(re[b] * re[b] + im[b] * im[b]);
      }
    }
    return { mag: mag, frames: frames, bins: bins, hop: hop, rate: rate };
  }

  function percentileOf(sortedAsc, p) {
    if (!sortedAsc.length) return 0;
    var idx = (p / 100) * (sortedAsc.length - 1);
    var lo = Math.floor(idx), hi = Math.ceil(idx);
    if (lo === hi) return sortedAsc[lo];
    return sortedAsc[lo] + (sortedAsc[hi] - sortedAsc[lo]) * (idx - lo);
  }

  /* Per-bin stationary-background estimate, then subtract.

     The background is a LOW PERCENTILE OF THE WHOLE FILE, per frequency bin —
     not a short rolling window. That choice matters and was arrived at the hard
     way: a rolling window has to be longer than the longest stretch of voice to
     ever see the background alone, and a shloka runs 10–20 seconds. With a 3 s
     window the "background" inside a shloka is measured from the shloka itself,
     the residual goes to zero everywhere, and the detector collapses to one
     segment again — the very bug being fixed.

     Over a whole recording the drone and the tabla are present in essentially
     every frame at a near-constant level, so a low percentile across all frames
     lands on them. The voice is absent during the pauses, which is exactly the
     minority of frames a low percentile is measuring. Subtract that per-bin
     floor and the pauses reappear.

     `noisePercentile` therefore wants to be smaller than the fraction of the
     recording that is pause. 5% is a safe default for chanting; raise it if a
     recording has unusually long gaps. */
  function subtractStationary(spec, opts) {
    var out = new Float64Array(spec.frames);
    var col = new Float64Array(spec.frames);

    for (var b = 0; b < spec.bins; b++) {
      var f;
      for (f = 0; f < spec.frames; f++) col[f] = spec.mag[f * spec.bins + b];
      var sorted = Array.prototype.slice.call(col).sort(function (x, y) { return x - y; });
      var bg = percentileOf(sorted, opts.noisePercentile);
      for (f = 0; f < spec.frames; f++) {
        var resid = col[f] - bg;
        if (resid > 0) out[f] += resid * resid;
      }
    }

    var db = new Float32Array(spec.frames);
    for (var i = 0; i < spec.frames; i++) {
      db[i] = 10 * Math.log10(out[i] / spec.bins + 1e-12);
    }
    var hopSec = spec.hop / spec.rate;
    // Smooth BEFORE any morphology. Chanting is amplitude-modulated at the
    // syllable rate (~5 Hz), so the raw envelope dips to near-nothing every
    // ~0.18 s; a percussive stroke is a ~0.12 s burst. By DURATION the two are
    // indistinguishable -- an erosion wide enough to wipe the tabla also wipes
    // the voice, which is a mistake worth recording because it silently
    // reproduces the original one-segment bug.
    //
    // Averaging over 0.3 s separates them by LEVEL instead: continuous chanting
    // averages to a high value, a 25%-duty-cycle stroke pattern averages low.
    var sm = smooth(db, Math.max(1, Math.round(0.30 / hopSec)));
    // Now that the voice is a plateau rather than a train of pulses, a short
    // opening is safe and removes what is left of isolated strokes.
    return morphOpen(sm, Math.max(1, Math.round(0.20 / hopSec)));
  }

  function morphOpen(db, win) {
    return dilate(erode(db, win), win);
  }

  function erode(db, win) {
    var n = db.length, out = new Float32Array(n), half = Math.floor(win / 2);
    for (var i = 0; i < n; i++) {
      var lo = Math.max(0, i - half), hi = Math.min(n, i + half + 1), m = Infinity;
      for (var j = lo; j < hi; j++) if (db[j] < m) m = db[j];
      out[i] = m;
    }
    return out;
  }

  function dilate(db, win) {
    var n = db.length, out = new Float32Array(n), half = Math.floor(win / 2);
    for (var i = 0; i < n; i++) {
      var lo = Math.max(0, i - half), hi = Math.min(n, i + half + 1), m = -Infinity;
      for (var j = lo; j < hi; j++) if (db[j] > m) m = db[j];
      out[i] = m;
    }
    return out;
  }

  /* Moving average over the envelope — a single loud tabla stroke inside a
     pause should not read as a syllable. */
  function smooth(db, win) {
    if (win < 2) return db;
    var n = db.length, out = new Float32Array(n), half = Math.floor(win / 2);
    var cum = new Float64Array(n + 1);
    for (var i = 0; i < n; i++) cum[i + 1] = cum[i] + db[i];
    for (i = 0; i < n; i++) {
      var lo = Math.max(0, i - half), hi = Math.min(n, i + half + 1);
      out[i] = (cum[hi] - cum[lo]) / (hi - lo);
    }
    return out;
  }

  function broadbandDb(x, rate, opts) {
    var frame = Math.round(rate * 0.03), hop = Math.round(rate * 0.01);
    var n = Math.max(0, 1 + Math.floor((x.length - frame) / hop));
    var cum = new Float64Array(x.length + 1);
    for (var i = 0; i < x.length; i++) cum[i + 1] = cum[i] + x[i] * x[i];
    var db = new Float32Array(n);
    for (var k = 0; k < n; k++) {
      var p = (cum[k * hop + frame] - cum[k * hop]) / frame;
      db[k] = 10 * Math.log10(p + 1e-12);
    }
    return { db: db, hopSec: hop / rate };
  }

  /* 1-D Otsu split on log gap lengths — unchanged from the existing tool. */
  function otsuSplit(vals) {
    var v = vals.map(function (x) { return Math.log(x + 1e-6); });
    var bins = 64, lo = Math.min.apply(null, v), hi = Math.max.apply(null, v);
    if (hi <= lo) return null;
    var hist = new Float64Array(bins), mids = new Float64Array(bins), b;
    for (b = 0; b < bins; b++) mids[b] = lo + (hi - lo) * (b + 0.5) / bins;
    v.forEach(function (x) {
      hist[Math.min(bins - 1, Math.floor((x - lo) / (hi - lo) * bins))]++;
    });
    var tot = v.length, muT = 0, i;
    for (i = 0; i < bins; i++) muT += hist[i] * mids[i];
    var best = -1, bestK = -1, wAcc = 0, muAcc = 0;
    for (var k = 0; k < bins; k++) {
      wAcc += hist[k]; muAcc += hist[k] * mids[k];
      var wF = tot - wAcc;
      if (wAcc === 0 || wF === 0) continue;
      var mB = muAcc / wAcc, mF = (muT - muAcc) / wF;
      var sigma = wAcc * wF * (mB - mF) * (mB - mF);
      if (sigma > best) { best = sigma; bestK = k; }
    }
    return bestK < 0 ? null : Math.exp(mids[bestK]);
  }

  // ---------------------------------------------------------------- public

  function envelope(mono, sampleRate, options) {
    var opts = extend(DEFAULTS, options);
    var dec = decimate(mono, sampleRate, opts.workRate);
    if (opts.method === 'broadband') {
      var bb = broadbandDb(dec.data, dec.rate, opts);
      return { db: bb.db, hopSec: bb.hopSec, method: 'broadband' };
    }
    var spec = spectrogram(dec.data, dec.rate, opts);
    return {
      db: subtractStationary(spec, opts),
      hopSec: spec.hop / spec.rate,
      method: 'voice'
    };
  }

  /* Returns the segments; if `report` is passed, fills in the values the UI
     shows the user (the threshold actually used, the gap actually required)
     rather than the ones they typed. */
  function segmentsFromDb(db, hopSec, totalSec, options, report) {
    var opts = extend(DEFAULTS, options);
    var n = db.length, i, j, k;

    var thr;
    if (opts.silenceDbOverride !== undefined && opts.silenceDbOverride !== null) {
      thr = opts.silenceDbOverride;
    } else {
      var sorted = Array.prototype.slice.call(db).sort(function (a, b) { return a - b; });
      var floorDb = percentileOf(sorted, 10), peakDb = percentileOf(sorted, 90);
      thr = Math.max(floorDb + 6.0, floorDb + 0.35 * (peakDb - floorDb));
      thr = Math.min(thr, peakDb - 3.0);
    }

    if (report) report.threshold = thr;

    var active = new Uint8Array(n);
    for (k = 0; k < n; k++) active[k] = db[k] > thr ? 1 : 0;

    var gaps = [];
    i = 0;
    while (i < n) {
      if (!active[i]) { j = i; while (j < n && !active[j]) j++; if (i > 0 && j < n) gaps.push((j - i) * hopSec); i = j; }
      else i++;
    }
    var og = gaps.length >= 3 ? otsuSplit(gaps) : null;
    var minGap = Math.max(opts.minGapSec, og || opts.minGapSec);
    if (report) report.minGap = minGap;

    var merged = active.slice();
    var minGapFr = Math.round(minGap / hopSec);
    i = 0;
    while (i < n) {
      if (!merged[i]) {
        j = i; while (j < n && !merged[j]) j++;
        if (i > 0 && j < n && (j - i) < minGapFr) for (var f = i; f < j; f++) merged[f] = 1;
        i = j;
      } else i++;
    }

    var segs = [];
    i = 0;
    while (i < n) {
      if (merged[i]) {
        j = i; while (j < n && merged[j]) j++;
        segs.push({ start: i * hopSec, end: Math.min(totalSec, j * hopSec) });
        i = j;
      } else i++;
    }

    // A shloka follows a vṛtta, so it has a real minimum duration: anything
    // shorter is a fragment and belongs to its neighbour.
    var out = [];
    for (i = 0; i < segs.length; i++) {
      if (out.length && (segs[i].end - segs[i].start) < opts.minLenSec) out[out.length - 1].end = segs[i].end;
      else out.push(segs[i]);
    }
    while (out.length > 1 && (out[0].end - out[0].start) < opts.minLenSec) {
      out[1].start = out[0].start; out.shift();
    }

    return out.map(function (s) {
      return {
        start: Math.max(0, s.start - opts.padSec),
        end: Math.min(totalSec, s.end + opts.padSec)
      };
    });
  }

  function detect(mono, sampleRate, options) {
    var opts = extend(DEFAULTS, options);
    var env = envelope(mono, sampleRate, opts);
    var total = mono.length / sampleRate;
    var report = { threshold: null, minGap: opts.minGapSec };
    var segs = segmentsFromDb(env.db, env.hopSec, total, opts, report);
    return {
      segments: segs, method: env.method, totalSec: total,
      threshold: report.threshold, minGap: report.minGap
    };
  }

  return {
    DEFAULTS: DEFAULTS,
    toMono: toMono,
    decimate: decimate,
    envelope: envelope,
    segmentsFromDb: segmentsFromDb,
    detect: detect,
    _internals: { fft: fft, spectrogram: spectrogram, otsuSplit: otsuSplit, percentileOf: percentileOf }
  };
}));
