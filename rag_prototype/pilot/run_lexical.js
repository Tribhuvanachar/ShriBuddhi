/*
 * run_lexical.js — runs the REAL, unmodified production lexical search
 * (dge/js/dge-search.js + dge/js/dge-normalize.js, required as-is from the
 * repo) against the pilot's local index (built by the real, unmodified
 * dge/build_search_index.py). No production files are touched; this only
 * requires them as libraries.
 *
 * Kannada-script queries are block-folded to Devanagari before calling
 * into dge-search.js, mirroring the SAME codepoint-shift the production
 * indexer already documents (build_search_index.py fold_indic_to_devanagari)
 * as the correct transliteration for aligned scripts sharing Devanagari's
 * layout -- this replicates what global-search.js's Sanscript.t() call
 * would do in the browser, since Sanscript itself is a browser-CDN-only
 * dependency not available under plain Node.
 */
'use strict';
const path = require('path');
const fs = require('fs');

const REPO_JS = '/home/user/bhumandala/dge/js';
const DGESearch = require(path.join(REPO_JS, 'dge-search.js'));

const HERE = __dirname;
const INDEX_BASE = path.join(HERE, 'lexical_index');
const queries = JSON.parse(fs.readFileSync(path.join(HERE, 'queries_large.json'), 'utf8'));

function foldKannadaToDevanagari(s) {
  // Same block bases as build_search_index.py's _INDIC_FOLD_BLOCKS for Kannada.
  const KANNADA_BASE = 0x0C80, DEVA_BASE = 0x0900;
  let out = '';
  for (const ch of s) {
    const cp = ch.codePointAt(0);
    if (cp >= KANNADA_BASE && cp < KANNADA_BASE + 0x80) {
      out += String.fromCodePoint(cp - KANNADA_BASE + DEVA_BASE);
    } else {
      out += ch;
    }
  }
  return out;
}

function queryTextFor(q) {
  // script field: 'deva' | 'kannada' | 'latin' (see queries_large.json)
  if (q.script === 'kannada') return foldKannadaToDevanagari(q.query);
  return q.query;
}

async function main() {
  const idx = await DGESearch.create(INDEX_BASE);
  const results = [];
  for (const q of queries) {
    const qtext = queryTextFor(q);
    const [exact, fuzzy] = await Promise.all([
      idx.searchExact(qtext, { limit: 10 }).catch((e) => ({ error: String(e) })),
      idx.search(qtext, { limit: 10 }).catch((e) => ({ error: String(e) })),
    ]);
    const norm = (arr) =>
      Array.isArray(arr)
        ? arr.map((h) => ({ grantha: h.grantha, unit: h.unit, score: h.score, via: h.via }))
        : [];
    results.push({
      id: q.id,
      category: q.category,
      query: q.query,
      target_parent: q.target_parent,
      exact: norm(exact),
      fuzzy: norm(fuzzy),
    });
  }
  fs.writeFileSync(
    path.join(HERE, 'lexical_results.json'),
    JSON.stringify(results, null, 1),
    'utf8'
  );
  console.log(`Ran ${results.length} queries. Wrote lexical_results.json`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
