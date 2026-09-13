/* Same real, unmodified dge-search.js/dge-normalize.js, same pilot lexical
 * index as before -- just pointed at the 18 new natural-language
 * questions instead of queries_large.json, to compute the confidence-aware
 * override's input for this experiment. */
'use strict';
const path = require('path');
const fs = require('fs');

const REPO_JS = '/home/user/bhumandala/dge/js';
const DGESearch = require(path.join(REPO_JS, 'dge-search.js'));

const PILOT = path.join(__dirname, '..', 'pilot');
const INDEX_BASE = path.join(PILOT, 'lexical_index');
const questions = JSON.parse(fs.readFileSync(path.join(__dirname, 'questions.json'), 'utf8'));

function foldKannadaToDevanagari(s) {
  const KANNADA_BASE = 0x0C80, DEVA_BASE = 0x0900;
  let out = '';
  for (const ch of s) {
    const cp = ch.codePointAt(0);
    if (cp >= KANNADA_BASE && cp < KANNADA_BASE + 0x80) out += String.fromCodePoint(cp - KANNADA_BASE + DEVA_BASE);
    else out += ch;
  }
  return out;
}

async function main() {
  const idx = await DGESearch.create(INDEX_BASE);
  const results = [];
  for (const q of questions) {
    const qtext = q.lang === 'kn' ? foldKannadaToDevanagari(q.question) : q.question;
    const exact = await idx.searchExact(qtext, { limit: 10 }).catch(() => []);
    const norm = (arr) => Array.isArray(arr)
      ? arr.map((h) => ({ grantha: h.grantha, unit: h.unit, score: h.score, via: h.via }))
      : [];
    results.push({ id: q.id, exact: norm(exact) });
  }
  fs.writeFileSync(path.join(__dirname, 'lexical_for_questions.json'), JSON.stringify(results, null, 1));
  console.log(`Ran ${results.length} questions through real lexical searchExact().`);
}

main().catch((e) => { console.error(e); process.exit(1); });
