/*
 * test-audio-detect.js — the regression test the Audio Admin never had.
 *
 * Synthesises a chanting recording: six 12-second "shlokas" separated by
 * 2-second pauses, over a CONTINUOUS accompaniment (a tanpura-like drone plus
 * periodic tabla strokes) that never stops — including through the pauses.
 * That is exactly the recording that broke the tool.
 *
 * The test asserts both halves of the story:
 *   - the old broadband method returns 1 segment (the bug, reproduced)
 *   - the new voice method returns 6 (the fix)
 *
 *   node test-audio-detect.js
 */
'use strict';
const assert = require('assert');
const D = require('../../dge/js/audio-detect.js');

const SR = 16000;

function synth({ nShlokas = 6, shlokaSec = 12, gapSec = 2,
                 droneDb = -12, tablaDb = -10, voiceDb = -6 } = {}) {
  const total = nShlokas * shlokaSec + (nShlokas - 1) * gapSec;
  const n = Math.round(total * SR);
  const x = new Float32Array(n);
  const amp = db => Math.pow(10, db / 20);

  // Continuous accompaniment, present for the WHOLE recording, pauses included.
  const dA = amp(droneDb), tA = amp(tablaDb);
  for (let i = 0; i < n; i++) {
    const t = i / SR;
    // tanpura-ish: a few steady partials, slow beating
    x[i] += dA * (0.6 * Math.sin(2 * Math.PI * 130.8 * t) +
                  0.4 * Math.sin(2 * Math.PI * 196.0 * t) +
                  0.3 * Math.sin(2 * Math.PI * 261.6 * t));
    // tabla: a decaying stroke every 0.5 s, low-pitched with a click
    const phase = t % 0.5;
    if (phase < 0.12) {
      const env = Math.exp(-phase * 30);
      x[i] += tA * env * (Math.sin(2 * Math.PI * 90 * t) + 0.5 * Math.sin(2 * Math.PI * 320 * t));
    }
  }

  // Voice: a harmonic stack in the vocal band, amplitude-modulated at a
  // syllable rate, present only during the shlokas.
  const vA = amp(voiceDb);
  const spans = [];
  for (let s = 0; s < nShlokas; s++) {
    const start = s * (shlokaSec + gapSec);
    spans.push([start, start + shlokaSec]);
    for (let i = Math.round(start * SR); i < Math.round((start + shlokaSec) * SR); i++) {
      const t = i / SR;
      const syll = 0.5 + 0.5 * Math.sin(2 * Math.PI * 5.5 * t);       // ~5.5 Hz
      const f0 = 150 + 12 * Math.sin(2 * Math.PI * 0.7 * t);
      let v = 0;
      for (let h = 1; h <= 12; h++) {
        const f = f0 * h;
        if (f < 200 || f > 3500) continue;
        v += (1 / h) * Math.sin(2 * Math.PI * f * t);
      }
      x[i] += vA * syll * v * 0.5;
    }
  }
  return { audio: x, spans, total };
}

let passed = 0;
function test(name, fn) {
  try { fn(); passed++; console.log('  ok   ' + name); }
  catch (e) { console.error('  FAIL ' + name + '\n       ' + e.message); process.exitCode = 1; }
}

console.log('\nthe regression: continuous accompaniment');
const { audio, spans, total } = synth();

test('broadband detection collapses the whole recording into one segment', () => {
  const r = D.detect(audio, SR, { method: 'broadband', minLenSec: 8, minGapSec: 1.5 });
  assert.strictEqual(r.segments.length, 1,
    `expected the old method to find 1, got ${r.segments.length}`);
});

test('voice detection recovers all six shlokas', () => {
  const r = D.detect(audio, SR, { minLenSec: 8, minGapSec: 1.5 });
  assert.strictEqual(r.segments.length, spans.length,
    `expected ${spans.length}, got ${r.segments.length}`);
});

test('boundaries land within 0.6 s of the true ones', () => {
  const r = D.detect(audio, SR, { minLenSec: 8, minGapSec: 1.5 });
  r.segments.forEach((seg, i) => {
    assert.ok(Math.abs(seg.start - spans[i][0]) < 0.6,
      `segment ${i + 1} starts at ${seg.start.toFixed(2)}, expected ~${spans[i][0]}`);
    assert.ok(Math.abs(seg.end - spans[i][1]) < 0.6,
      `segment ${i + 1} ends at ${seg.end.toFixed(2)}, expected ~${spans[i][1]}`);
  });
});

console.log('\nrobustness');

test('still works when the accompaniment is as loud as the voice', () => {
  const s = synth({ droneDb: -6, tablaDb: -6 });
  const r = D.detect(s.audio, SR, { minLenSec: 8, minGapSec: 1.5 });
  assert.strictEqual(r.segments.length, 6, `got ${r.segments.length}`);
});

test('a clean recording with no accompaniment is unaffected', () => {
  const s = synth({ droneDb: -120, tablaDb: -120 });
  const r = D.detect(s.audio, SR, { minLenSec: 8, minGapSec: 1.5 });
  assert.strictEqual(r.segments.length, 6, `got ${r.segments.length}`);
});

test('an in-verse breath shorter than the minimum gap does not split a shloka', () => {
  const s = synth({ nShlokas: 2, shlokaSec: 20, gapSec: 3 });
  // punch a 0.4 s hole in the middle of the first shloka
  for (let i = Math.round(9.8 * SR); i < Math.round(10.2 * SR); i++) s.audio[i] *= 0.001;
  const r = D.detect(s.audio, SR, { minLenSec: 8, minGapSec: 1.5 });
  assert.strictEqual(r.segments.length, 2, `got ${r.segments.length}`);
});

test('segments never overlap and stay inside the recording', () => {
  const r = D.detect(audio, SR, { minLenSec: 8, minGapSec: 1.5 });
  let prev = -1;
  r.segments.forEach(s => {
    assert.ok(s.start >= 0 && s.end <= total + 1e-6, 'segment outside the file');
    assert.ok(s.start > prev, 'segments out of order or overlapping');
    prev = s.start;
  });
});

console.log('\nunits');

test('fft round-trips a pure tone to the right bin', () => {
  const N = 1024, re = new Float64Array(N), im = new Float64Array(N);
  for (let i = 0; i < N; i++) re[i] = Math.sin(2 * Math.PI * 64 * i / N);
  D._internals.fft(re, im);
  let best = 0, bestMag = -1;
  for (let b = 1; b < N / 2; b++) {
    const m = Math.hypot(re[b], im[b]);
    if (m > bestMag) { bestMag = m; best = b; }
  }
  assert.strictEqual(best, 64);
});

test('decimation reports the rate it actually produced', () => {
  const d = D.decimate(new Float32Array(48000), 48000, 16000);
  assert.strictEqual(d.rate, 16000);
  assert.strictEqual(d.data.length, 16000);
});

test('toMono averages channels', () => {
  const m = D.toMono([new Float32Array([1, 1]), new Float32Array([-1, 3])]);
  assert.deepStrictEqual(Array.from(m), [0, 2]);
});

console.log('\n' + passed + ' passed' + (process.exitCode ? ', SOME FAILED' : ', all green'));
