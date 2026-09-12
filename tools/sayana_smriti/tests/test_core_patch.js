/**
 * test_core_patch.js — exercises the PATCHED dgeNormalizeGranthaData() directly.
 *
 * core.js is a browser script, not a module, so we slice out the two pure
 * functions (dgeSanitizeVedicAccents + dgeNormalizeGranthaData) and eval them
 * with no DOM. That means the test runs against the real patched source, not
 * a copy that could drift from it.
 *
 *   node tests/test_core_patch.js
 */
'use strict';
const fs = require('fs');
const path = require('path');
const assert = require('assert');

// Points at the shipping dge/js/core.js rather than a bundled copy under
// patches/. The package keeps re-shipping its own snapshot of core.js, but
// core.js has moved on in main (kosha citations, the tour, inline content), so
// applying that snapshot wholesale would revert unrelated work. The normaliser
// change lives in the real file -- and this test guards the copy the browser
// actually loads, which is the only one whose behaviour matters.
const src = fs.readFileSync(
  path.join(__dirname, '..', '..', '..', 'dge', 'js', 'core.js'), 'utf8');
const start = src.indexOf('function dgeSanitizeVedicAccents');
const end = src.indexOf('function initApp');
assert.ok(start > 0 && end > start, 'could not slice the normaliser out of core.js');

const sandboxSrc = src.slice(start, end) +
  '\nmodule.exports = { dgeNormalizeGranthaData, dgeSanitizeVedicAccents };';
// The slice also contains a stray DOMContentLoaded listener; stub just enough
// browser surface for it to register and do nothing.
const noop = () => {};
const documentStub = { addEventListener: noop, querySelector: () => null,
                       createElement: () => ({ style: {}, appendChild: noop }),
                       body: { appendChild: noop } };
const windowStub = { addEventListener: noop, localStorage: { getItem: () => null, setItem: noop } };
const m = { exports: {} };
new Function('module', 'console', 'document', 'window', sandboxSrc)(
  m, { log: noop, warn: noop }, documentStub, windowStub);
const { dgeNormalizeGranthaData } = m.exports;

let passed = 0;
function test(name, fn) {
  try { fn(); passed++; console.log('  ok   ' + name); }
  catch (e) { console.error('  FAIL ' + name + '\n       ' + e.message); process.exitCode = 1; }
}

console.log('\nvedic_text — Sayana layer (what import_sayana_rigveda.py writes)');

const veda = {
  schema: 'vedic_text',
  default_author: 'Apaurusheya',
  items: [{
    id: '1.164.1',
    samhita_patha: 'अस्य वामस्य पलितस्य होतुस्तस्य भ्राता मध्यमो अस्त्यश्नः ।',
    commentaries: {
      griffith: 'I have beheld the Lord of men with seven sons.',
      sayana: 'The seven sons are the seven solar rays; Āditya is the seventh son of Aditi.',
      wilson: 'I have beheld the Lord of men with seven sons…'
    }
  }]
};

test('sayana text survives normalisation', () => {
  const out = dgeNormalizeGranthaData(veda, 'Rigveda');
  assert.match(out.shlokas[1].commentaries.sayana, /seven solar rays/);
});

test('sayana gets its proper label, not "Sayana"', () => {
  const out = dgeNormalizeGranthaData(veda, 'Rigveda');
  assert.strictEqual(out.metadata.availableCommentaries.sayana,
    'सायणभाष्यम् — Sāyaṇa (Ṛgveda-bhāṣya)');
  assert.match(out.metadata.availableCommentaries.wilson, /after Sāyaṇa/);
});

test('existing western layers untouched', () => {
  const out = dgeNormalizeGranthaData(veda, 'Rigveda');
  assert.strictEqual(out.metadata.availableCommentaries.griffith,
    'Griffith (1889 English Translation)');
});

console.log('\nsmriti_dharmashastra_text — nested shlokas (what import_smriti.py writes)');

const smriti = {
  schema: 'smriti_dharmashastra_text',
  default_author: 'Manu',
  items: [{
    id: 'adhyaya_01',
    reference: 'Manu Smṛti, Adhyāya 1',
    shlokas: [
      {
        number: 1,
        sanskrit_text: 'मनुमेकाग्रमासीनमभिगम्य महर्षयः',
        artha: 'The great sages approached Manu, who was seated with a collected mind.',
        bhashya: [
          { commentator: 'Medhātithi (Manubhāṣya), tr. Ganganath Jha',
            text: 'Salutation to the Supreme Brahman!', language: 'en', source: 'https://…' },
          { commentator: 'Kullūka (Manvarthamuktāvalī)',
            text: 'kullūka glosses pratipūjya as mutual salutation.', language: 'sa', source: 'https://…' }
        ]
      },
      { number: 2, sanskrit_text: 'भगवन् सर्ववर्णानां' }   // no commentary at all
    ]
  }]
};

test('bhashya[] is no longer discarded', () => {
  const out = dgeNormalizeGranthaData(smriti, 'Manu Smriti');
  const c = out.shlokas[1].commentaries;
  assert.ok(Object.keys(c).length >= 3, 'expected artha + two bhashya, got ' + JSON.stringify(Object.keys(c)));
  assert.match(c.artha, /great sages/);
});

test('IAST diacritics fold to a clean key', () => {
  const out = dgeNormalizeGranthaData(smriti, 'Manu Smriti');
  const keys = Object.keys(out.shlokas[1].commentaries);
  assert.ok(keys.includes('medhatithi_manubhasya_tr_ganganath_jha'),
    'got ' + JSON.stringify(keys));
  assert.ok(keys.some(k => k.startsWith('kulluka')), 'got ' + JSON.stringify(keys));
  assert.ok(!keys.some(k => /__|^_|_$/.test(k)), 'mangled key: ' + JSON.stringify(keys));
});

test('availableCommentaries keeps the readable commentator name', () => {
  const out = dgeNormalizeGranthaData(smriti, 'Manu Smriti');
  assert.strictEqual(out.metadata.availableCommentaries.medhatithi_manubhasya_tr_ganganath_jha,
    'Medhātithi (Manubhāṣya), tr. Ganganath Jha');
});

test('a shloka with no commentary stays empty, not undefined', () => {
  const out = dgeNormalizeGranthaData(smriti, 'Manu Smriti');
  assert.deepStrictEqual(out.shlokas[2].commentaries, {});
});

test('verse text and chapter reference still flatten correctly', () => {
  const out = dgeNormalizeGranthaData(smriti, 'Manu Smriti');
  assert.strictEqual(out.totalShlokas, 2);
  assert.match(out.shlokas[1].vedicId, /Adhyāya 1 · 1/);
});

console.log('\nregression — shapes that must be untouched');

test('PNS legacy shape passes straight through', () => {
  const pns = { shlokas: { 1: { sa: 'x', commentaries: {} } }, metadata: { title: 'PNS' } };
  assert.strictEqual(dgeNormalizeGranthaData(pns, 'PNS'), pns);
});

test('itihasa chapter with no artha/bhashya behaves as before', () => {
  const rama = { schema: 'itihasa_purana_text', items: [
    { id: 'sarga_01', reference: 'Bala Kanda, Sarga 1',
      shlokas: [{ number: 1, sanskrit_text: 'तपःस्वाध्यायनिरतं' }] }] };
  const out = dgeNormalizeGranthaData(rama, 'Ramayana');
  assert.deepStrictEqual(out.metadata.availableCommentaries, {});
  assert.strictEqual(out.totalShlokas, 1);
});

console.log('\n' + passed + ' passed' + (process.exitCode ? ', SOME FAILED' : ', all green'));
