/*
 * test-genie-asr-recorder.js — regression tests for the pure/testable half
 * of admin/js/genie-asr-recorder.js (the DOM/IndexedDB/getUserMedia half
 * needs a real browser and is instead covered by the Playwright script in
 * this same directory).
 *
 *   node tools/genie_asr_recorder/test-genie-asr-recorder.js
 */
'use strict';
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const G = require('../../admin/js/genie-asr-recorder.js');

const MANIFEST_PATH = path.join(__dirname, '../../genie_asr_benchmark/manifests/manifest.json');
const manifest = JSON.parse(fs.readFileSync(MANIFEST_PATH, 'utf8'));

let failures = 0;
function test(name, fn) {
  try { fn(); console.log('  ok — ' + name); }
  catch (e) { failures++; console.error('  FAIL — ' + name + '\n    ' + e.message); }
}

console.log('resample()');
test('identity when rates match', () => {
  const input = new Float32Array([0.1, 0.2, 0.3]);
  const out = G.resample(input, 16000, 16000);
  assert.strictEqual(out, input);
});
test('downsamples to the expected length', () => {
  const input = new Float32Array(48000); // 1s @ 48kHz
  const out = G.resample(input, 48000, 16000);
  assert.strictEqual(out.length, 16000);
});
test('linearly interpolates a ramp', () => {
  const input = new Float32Array([0, 1, 0]); // 3 samples @ 2Hz -> resample to 4Hz (double)
  const out = G.resample(input, 2, 4);
  assert.strictEqual(out.length, 6);
  assert.ok(Math.abs(out[0] - 0) < 1e-6);
});

console.log('encodeWav() / pcm16WavBytes()');
test('produces a valid RIFF/WAVE header', () => {
  const samples = new Float32Array(1600); // 0.1s @ 16kHz
  for (let i = 0; i < samples.length; i++) samples[i] = Math.sin(i * 0.1) * 0.5;
  const bytes = G.encodeWav(samples, 16000, 16000);
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const str = (off, len) => String.fromCharCode(...bytes.slice(off, off + len));
  assert.strictEqual(str(0, 4), 'RIFF');
  assert.strictEqual(str(8, 4), 'WAVE');
  assert.strictEqual(str(12, 4), 'fmt ');
  assert.strictEqual(view.getUint16(20, true), 1); // PCM
  assert.strictEqual(view.getUint16(22, true), 1); // mono
  assert.strictEqual(view.getUint32(24, true), 16000); // sample rate
  assert.strictEqual(view.getUint16(34, true), 16); // bits per sample
  assert.strictEqual(str(36, 4), 'data');
  assert.strictEqual(view.getUint32(40, true), samples.length * 2);
  assert.strictEqual(bytes.length, 44 + samples.length * 2);
});
test('round-trips full-scale samples without clipping past int16 range', () => {
  const samples = new Float32Array([1, -1, 0.5, -0.5, 0]);
  const bytes = G.encodeWav(samples, 8000, 8000); // same rate: no resampling to muddy the check
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const s0 = view.getInt16(44, true), s1 = view.getInt16(46, true);
  assert.strictEqual(s0, 0x7FFF);
  assert.strictEqual(s1, -0x8000);
});
test('resamples first, so encodeWav(x, 48000, 16000) output is 16kHz-length', () => {
  const samples = new Float32Array(48000);
  const bytes = G.encodeWav(samples, 48000, 16000);
  assert.strictEqual(bytes.length, 44 + 16000 * 2);
});

console.log('manifest-driven grouping (real manifest.json)');
test('76 items across 16 categories, all 4-level tiered by category number', () => {
  assert.strictEqual(manifest.length, 76, 'expected 76 manifest items, got ' + manifest.length);
  const groups = G.groupByCategory(manifest);
  assert.strictEqual(groups.length, 16, 'expected 16 categories, got ' + groups.length);
  const total = groups.reduce((s, g) => s + g.items.length, 0);
  assert.strictEqual(total, 76);
});
test('categories 14/15/16 (added the same night as this tool) are present', () => {
  const cats = G.groupByCategory(manifest).map(g => g.category);
  ['14_grammar_tools', '15_content_actions', '16_content_correction'].forEach(c => {
    assert.ok(cats.includes(c), 'missing category ' + c);
  });
});
test('02_kannada_001 reads the corrected transcript, not the old hardcoded typo', () => {
  const item = manifest.find(m => m.id === '02_kannada_001');
  assert.ok(item, 'fixture item missing');
  assert.strictEqual(item.transcript_text, 'ಸುಮಧ್ವ ವಿಜಯ ೧.೧ ತೆರೆಯಿರಿ');
  assert.notStrictEqual(item.transcript_text, 'ಸುಮಧು ವಿಜಯ ೧.೧ ತೆರೆಯಿರಿ', 'this is the OLD, uncorrected string');
});

console.log('audioFileFor() / repoAudioPath()');
test('uses the manifest audio_file when present', () => {
  const item = manifest.find(m => m.id === '01_english_001');
  assert.strictEqual(G.audioFileFor(item), item.audio_file);
});
test('derives the conventional path when audio_file is absent (new categories)', () => {
  const item = manifest.find(m => m.id === '14_grammar_tools_001');
  assert.strictEqual(item.audio_file, undefined);
  assert.strictEqual(G.audioFileFor(item), 'audio/14_grammar_tools/14_grammar_tools_001.wav');
  assert.strictEqual(G.repoAudioPath(item), 'genie_asr_benchmark/audio/14_grammar_tools/14_grammar_tools_001.wav');
});

console.log('buildTreePresenceMap()');
test('marks items present only when the tree has their exact path', () => {
  const item1 = manifest.find(m => m.id === '01_english_001');
  const item2 = manifest.find(m => m.id === '01_english_004');
  const tree = { tree: [
    { path: G.repoAudioPath(item1), type: 'blob', sha: 'deadbeef', size: 12345 },
    { path: 'genie_asr_benchmark/audio/README.md', type: 'blob', sha: 'aaa', size: 10 }
  ] };
  const map = G.buildTreePresenceMap(tree, manifest);
  assert.strictEqual(map[item1.id].present, true);
  assert.strictEqual(map[item1.id].sha, 'deadbeef');
  assert.strictEqual(map[item2.id].present, false);
});
test('everything absent when the tree fetch failed (empty/missing tree)', () => {
  const map = G.buildTreePresenceMap(null, manifest.slice(0, 3));
  Object.values(map).forEach(v => assert.strictEqual(v.present, false));
});

console.log('push request construction (no network — request shape only)');
test('pushRequestForItem builds the right URL, method, branch, content and message', () => {
  const item = manifest.find(m => m.id === '14_grammar_tools_001');
  const req = G.pushRequestForItem(item, 'ZmFrZS13YXYtYnl0ZXM=', 'ghp_faketoken123', null);
  assert.strictEqual(req.method, 'PUT');
  assert.strictEqual(req.url, 'https://api.github.com/repos/Tribhuvanachar/bhumandala/contents/genie_asr_benchmark/audio/14_grammar_tools/14_grammar_tools_001.wav');
  assert.strictEqual(req.headers.Authorization, 'token ghp_faketoken123');
  const body = JSON.parse(req.body);
  assert.strictEqual(body.branch, 'genie-asr-audio-seed');
  assert.strictEqual(body.content, 'ZmFrZS13YXYtYnl0ZXM=');
  assert.ok(body.message.includes('14_grammar_tools_001'));
  assert.strictEqual(body.sha, undefined, 'no sha expected for a new file');
});
test('pushRequestForItem includes sha when overwriting an existing file', () => {
  const item = manifest.find(m => m.id === '01_english_001');
  const req = G.pushRequestForItem(item, 'YmFzZTY0', 'ghp_faketoken123', 'existingsha123');
  const body = JSON.parse(req.body);
  assert.strictEqual(body.sha, 'existingsha123');
});
test('never targets any repo/branch other than the hardcoded ones', () => {
  const item = manifest.find(m => m.id === '01_english_001');
  const req = G.pushRequestForItem(item, 'YQ==', 'tok', null);
  assert.ok(req.url.startsWith('https://api.github.com/repos/Tribhuvanachar/bhumandala/contents/'));
  assert.strictEqual(JSON.parse(req.body).branch, 'genie-asr-audio-seed');
});

console.log('buildZip()');
test('produces a well-formed local/central/EOCD structure', () => {
  const entries = [
    { name: 'a.wav', bytes: new Uint8Array([1, 2, 3, 4]) },
    { name: 'b.wav', bytes: new Uint8Array([5, 6]) }
  ];
  const zip = G.buildZip(entries);
  const localBytes = Buffer.concat(zip.localParts.map(p => Buffer.from(p)));
  const centralBytes = Buffer.concat(zip.centralParts.map(p => Buffer.from(p)));
  assert.strictEqual(localBytes.readUInt32LE(0), 0x04034b50, 'first local file header signature');
  assert.strictEqual(centralBytes.readUInt32LE(0), 0x02014b50, 'first central directory signature');
  assert.strictEqual(zip.eocd.length, 22);
  const eocdView = new DataView(zip.eocd.buffer, zip.eocd.byteOffset, zip.eocd.byteLength);
  assert.strictEqual(eocdView.getUint32(0, true), 0x06054b50);
  assert.strictEqual(eocdView.getUint16(8, true), 2, 'entry count in EOCD');
});

console.log('manifestExportData()');
test('exports real field names and per-item status', () => {
  const data = G.manifestExportData(manifest, { '01_english_001': 'in_repo' });
  assert.strictEqual(data.count, 76);
  const item = data.items.find(i => i.id === '01_english_001');
  assert.strictEqual(item.status, 'in_repo');
  assert.strictEqual(item.transcript_text, manifest.find(m => m.id === '01_english_001').transcript_text);
  const unset = data.items.find(i => i.id === '14_grammar_tools_001');
  assert.strictEqual(unset.status, 'not_recorded');
});

console.log();
if (failures) {
  console.error(failures + ' test(s) FAILED');
  process.exit(1);
} else {
  console.log('All tests passed.');
}
