/*
 * test-parity.js — cross-language regression test for dge-normalize.js.
 * Run with: node dge/js/test-parity.js
 *
 * dge-normalize.js's own docstring states the invariant this test exists to
 * guard: "This is the JS twin of the Python indexer's normalizer. It MUST
 * produce the same pkey/ckey as build_search_index.py, or the query won't
 * match the index." If the two ever drift -- someone fixes a folding rule
 * in one file and forgets the other -- queries would silently stop matching
 * text that's actually there, with no error anywhere to point at why. That
 * docstring already claimed this test existed; it did not (confirmed by a
 * full search of the repo before writing this). This is that test, built
 * for real rather than assumed.
 *
 * Spawns exactly one `python3 parity_compute.py` process, feeding it every
 * test word as one JSON array over stdin and reading its JSON array of
 * {slp1, pkey, ckey, trigrams} back over stdout -- one round trip, not one
 * process per word. Compares that against dge-normalize.js's own output for
 * the identical words, computed in this same process.
 *
 * The word list below is deliberately chosen to exercise every fold class
 * both normalizers claim to implement (see dge-normalize.js's own docstring
 * and search_toolkit_pkg/normalize.py's module docstring): vowel length,
 * anusvara/nasal-class folding, sibilant folding, vocalic r/l, avagraha,
 * gemination, visarga, retroflex-to-dental, aspiration, and voicing --
 * plus a short multi-word phrase to confirm whitespace handling agrees too.
 */
'use strict';

const { spawnSync } = require('child_process');
const path = require('path');

const DGENorm = require(path.join(__dirname, 'dge-normalize.js'));

// Real Sanskrit words/phrases, each annotated with the fold class it's
// meant to exercise -- not an exhaustive corpus, but real text covering
// every rule both files implement, not synthetic strings invented to look
// like Sanskrit.
const WORDS = [
  ['राम', 'vowel length (A->a)'],
  ['रामं', 'anusvara at word end'],
  ['शिव', 'sibilant श'],
  ['षष्ठ', 'sibilant + retroflex (ष, ष्ठ)'],
  ['सर्व', 'plain sibilant स, baseline'],
  ['कृष्ण', 'vocalic ऋ (f->r) + retroflex ण'],
  ['गणेश', 'retroflex ण'],
  ['भगवान्', 'aspiration भ'],
  ['धर्म', 'aspiration ध'],
  ['नमः', 'visarga'],
  ['सत्त्व', 'gemination (त्त्व)'],
  ['सोऽहम्', 'avagraha (ऽ)'],
  ['पण्डित', 'retroflex ण्ड'],
  ['कमल', 'no folding needed -- sanity baseline'],
  ['राम नाम', 'multi-word phrase, whitespace handling'],
  // Fable review, 30 Aug 2026 -- classes the list above missed, each a
  // confirmed or near-miss divergence between the two normalizers:
  ['श्लोकः १.२', 'Devanagari digits (१->1): was a REAL parity bug -- Python mapped them, JS passed them through'],
  ['ॐ कान्ताय', 'ॐ survives the fold on both sides, must stay identical'],
  ['कल्याण-गुणैक-धाम्ने', 'literal hyphens inside verse text'],
  ['[श्रियं] (देव्य,', 'punctuation flowing into pkey -- both sides must agree byte-for-byte on what survives'],
];

function jsSideFor(word) {
  const slp1 = DGENorm.devaToSlp1(word);
  const pkey = DGENorm.phoneticKey(slp1);
  const ckey = DGENorm.coarseKey(slp1);
  const tris = DGENorm.trigrams(pkey).slice().sort();
  return { slp1, pkey, ckey, trigrams: tris };
}

function pySideForAll(words) {
  const scriptPath = path.join(__dirname, '..', 'parity_compute.py');
  const result = spawnSync('python3', [scriptPath], {
    input: JSON.stringify(words),
    encoding: 'utf8',
  });
  if (result.status !== 0) {
    throw new Error('parity_compute.py failed (status ' + result.status + '):\n' + result.stderr);
  }
  return JSON.parse(result.stdout);
}

function main() {
  const words = WORDS.map((w) => w[0]);
  const pyResults = pySideForAll(words);
  const failures = [];

  WORDS.forEach(([word, foldClass], i) => {
    const js = jsSideFor(word);
    const py = pyResults[i];
    if (js.slp1 !== py.slp1) {
      failures.push(`"${word}" (${foldClass}): slp1 mismatch -- JS "${js.slp1}" vs Python "${py.slp1}"`);
    }
    if (js.pkey !== py.pkey) {
      failures.push(`"${word}" (${foldClass}): pkey mismatch -- JS "${js.pkey}" vs Python "${py.pkey}"`);
    }
    if (js.ckey !== py.ckey) {
      failures.push(`"${word}" (${foldClass}): ckey mismatch -- JS "${js.ckey}" vs Python "${py.ckey}"`);
    }
    const jsTris = js.trigrams.join(',');
    const pyTris = py.trigrams.join(',');
    if (jsTris !== pyTris) {
      failures.push(`"${word}" (${foldClass}): trigrams mismatch -- JS [${jsTris}] vs Python [${pyTris}]`);
    }
  });

  if (failures.length) {
    console.error(`FAIL: ${failures.length} parity mismatch(es) between dge-normalize.js and search_toolkit_pkg/normalize.py:\n`);
    failures.forEach((f) => console.error('  - ' + f));
    process.exit(1);
  }

  console.log(`PASS: ${WORDS.length} words/phrases -- dge-normalize.js and search_toolkit_pkg/normalize.py agree on slp1/pkey/ckey/trigrams for every fold class tested.`);
}

main();
