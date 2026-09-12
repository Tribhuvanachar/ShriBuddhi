// Unit tests for entity-linker.js's cross-reference detector/resolver, run
// against the REAL dge_entities.json registry (not a mock), same convention
// as dge-search.js/genie_asr_benchmark/scripts/resolver.test.js (Node-testable
// pure logic, DOM-only bits skipped outside a browser).
// Run with: node --test dge/js/entity-linker.test.js
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');
const EL = require('./entity-linker.js');

const registry = JSON.parse(fs.readFileSync(
  path.join(__dirname, '..', 'data', 'dge_entities.json'), 'utf8'));
const ix = EL.buildIndex(registry.entities);

test('registry is non-trivial and covers the required test-case works', () => {
  assert.ok(Object.keys(registry.entities).length >= 5);
  ['brahmasutra', 'ashtadhyayi', 'rigveda', 'bhagavata_purana'].forEach((id) => {
    assert.ok(registry.entities[id], `expected entity "${id}" in the registry`);
  });
});

// -- Level 1: explicit verse-numbered citations ------------------------------

test('ब्रह्मसूत्रे १.१.२ resolves to Brahma Sūtra 1.1.2 (Level 1, high confidence)', () => {
  const m = EL.findMatches('अत्रोच्यते ब्रह्मसूत्रे १.१.२ इति वचनात्', ix);
  assert.equal(m.length, 1);
  assert.equal(m[0].id, 'brahmasutra');
  assert.equal(m[0].level, 1);
  assert.deepEqual(m[0].target, { adhyaya: 1, pada: 1, sutra: 2 });
});

test('अष्टाध्याय्याम् १.१.१ resolves to Ashtadhyayi 1.1.1 (Level 1)', () => {
  const m = EL.findMatches('यथोक्तम् अष्टाध्याय्याम् १.१.१ वृद्धिरादैच् इति', ix);
  assert.equal(m.length, 1);
  assert.equal(m[0].id, 'ashtadhyayi');
  assert.equal(m[0].level, 1);
  assert.deepEqual(m[0].target, { adhyaya: 1, pada: 1, sutra: 1 });
});

test('ऋग्वेद १.१.१ resolves to Rigveda mandala 1, sukta 1, rik 1 (Level 1)', () => {
  const m = EL.findMatches('ऋग्वेद १.१.१ इत्यत्र अग्निमीळे इति मन्त्रः', ix);
  assert.equal(m.length, 1);
  assert.equal(m[0].id, 'rigveda');
  assert.equal(m[0].level, 1);
  assert.deepEqual(m[0].target, { mandala: 1, sukta: 1, rik: 1 });
});

test('भागवते १०.१४.८ resolves to Bhagavata Purana skandha 10, adhyaya 14, shloka 8 (Level 1)', () => {
  const m = EL.findMatches('इति भागवते १०.१४.८ श्लोके उक्तम्', ix);
  assert.equal(m.length, 1);
  assert.equal(m[0].id, 'bhagavata_purana');
  assert.equal(m[0].level, 1);
  assert.deepEqual(m[0].target, { skandha: 10, adhyaya: 14, shloka: 8 });
});

test('ASCII-digit locator ("brahma sutra 1.1.2" via IAST alias) also resolves Level 1', () => {
  const m = EL.findMatches('as stated in brahma sutra 1.1.2 of the text', ix);
  assert.equal(m.length, 1);
  assert.equal(m[0].id, 'brahmasutra');
  assert.equal(m[0].level, 1);
  assert.deepEqual(m[0].target, { adhyaya: 1, pada: 1, sutra: 2 });
});

// -- Level 2: named work, no verse number ------------------------------------

test('अष्टाध्याय्याम् with no trailing number is a Level 2 (named-work) match', () => {
  const m = EL.findMatches('इति व्याकरणसिद्धान्तः अष्टाध्याय्याम् प्रतिपादितः', ix);
  assert.equal(m.length, 1);
  assert.equal(m[0].id, 'ashtadhyayi');
  assert.equal(m[0].level, 2);
  assert.equal(m[0].target, null);
});

test('विष्णुपुराणे with no number is a Level 2 named-work match', () => {
  const m = EL.findMatches('विष्णुपुराणे एतद् वर्णितम्', ix);
  assert.equal(m.length, 1);
  assert.equal(m[0].id, 'vishnu_purana');
  assert.equal(m[0].level, 2);
});

test('a trailing number with the wrong component count degrades to Level 2, not a wrong Level-1 guess', () => {
  // Rigveda's scheme is mandala.sukta.rik (3 components) -- a bare "1" here
  // must NOT be guessed as a target; it should just link the work name.
  const m = EL.findMatches('ऋग्वेदे १ इति संख्या', ix);
  assert.equal(m.length, 1);
  assert.equal(m[0].id, 'rigveda');
  assert.equal(m[0].level, 2);
  assert.equal(m[0].target, null);
});

// -- negative controls: no false positives -----------------------------------

test('कान्ताय (the plain-search test case) is not itself a cross-reference match', () => {
  // कान्ताय is the opening word of Sumadhvavijaya 1.1 -- a real search hit,
  // not a citation naming another work, so entity-linker must not fire on it.
  const m = EL.findMatches('कान्ताय कल्याणगुणैकधाम्ने', ix);
  assert.equal(m.length, 0);
});

test('ordinary prose with no work name at all produces zero matches', () => {
  const m = EL.findMatches('रामो राजमणिः सदा विजयते रामं रमेशं भजे', ix);
  assert.equal(m.length, 0);
});

test('two citations in one string both resolve, in order, without overlap', () => {
  const m = EL.findMatches('ब्रह्मसूत्रे १.१.१ तथा अष्टाध्याय्याम् २.३.४५', ix);
  assert.equal(m.length, 2);
  assert.equal(m[0].id, 'brahmasutra');
  assert.deepEqual(m[0].target, { adhyaya: 1, pada: 1, sutra: 1 });
  assert.equal(m[1].id, 'ashtadhyayi');
  assert.deepEqual(m[1].target, { adhyaya: 2, pada: 3, sutra: 45 });
  assert.ok(m[0].end <= m[1].start, 'matches must not overlap');
});

// -- routing: resolved target -> a real, correctly-shaped DGE URL -----------

test('Brahma Sūtra 1.1.2 opens the mula grantha at the real BS_C01_S01_V02 unit id', () => {
  // The real data.json's own unit ids are 'BS_C01_S01_V02'-shaped, not a
  // plain dotted number -- see dge_entities.json's note on this entity.
  const url = EL.buildOpenUrl(registry.entities.brahmasutra, { adhyaya: 1, pada: 1, sutra: 2 });
  assert.match(url, /\?path=darshana\/vedanta\/dvaita\/SarvaMula\/sutra_prasthana\/brahma_sutra_bhashya\/mula/);
  assert.match(url, /jumpVedicId=BS_C01_S01_V02/);
});

test('Rigveda 1.1.1 opens the zero-padded mandala_01 folder at vedicId 1.1.1', () => {
  const url = EL.buildOpenUrl(registry.entities.rigveda, { mandala: 1, sukta: 1, rik: 1 });
  assert.match(url, /\?path=vedas\/rigveda\/shakala_shakha\/samhita\/mandala_01/);
  assert.match(url, /jumpVedicId=1\.1\.1/);
});

test('Bhagavata 10.14.8 builds the exact chapter.reference string the real corpus data uses', () => {
  const url = EL.buildOpenUrl(registry.entities.bhagavata_purana, { skandha: 10, adhyaya: 14, shloka: 8 });
  assert.match(url, /\?path=purana\/maha_purana\/bhagavata_purana\/skandha_10/);
  // Verified against dge/data/purana/maha_purana/bhagavata_purana/skandha_10/data.json's
  // own chapter.reference field ("Skandha 10, Adhyaya 1") -- see dge_entities.json's note.
  assert.match(decodeURIComponent(url), /jumpVedicId=Skandha 10, Adhyaya 14 · 8/);
});

test('Ashtadhyayi (custom route_type) opens its own dedicated page with a #adhyaya.pada.sutra hash', () => {
  const url = EL.buildOpenUrl(registry.entities.ashtadhyayi, { adhyaya: 1, pada: 1, sutra: 1 });
  assert.match(url, /ashtadhyayi\.html#1\.1\.1$/);
});

test('a Level-2 (no target) match on a templated-route work falls back to part 1 as a real, navigable entry point', () => {
  const url = EL.buildOpenUrl(registry.entities.vishnu_purana, null);
  assert.match(url, /\?path=purana\/maha_purana\/vishnu_purana\/amsha_01$/);
});
