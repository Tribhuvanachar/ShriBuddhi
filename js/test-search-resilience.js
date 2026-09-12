/*
 * test-search-resilience.js — plain-Node regression test for dge-search.js's
 * fetchJSON error handling. Run with: node dge/js/test-search-resilience.js
 *
 * A real query fans out to dozens of small requests through a third-party
 * CDN (jsDelivr) -- see SEARCH_ARCHITECTURE.md. Before this test existed,
 * fetchJSON's browser branch only resolved to null on a 404; a genuine
 * network-level failure (a real risk on mobile, or against a flaky CDN
 * edge) instead REJECTED, and since every caller in dge-search.js fetches
 * many of these through Promise.all (up to ~33 postings, up to 120 shards
 * per query), one bad request took the ENTIRE search down with it. This
 * test forces dge-search.js's browser (fetch-based) code path in Node by
 * stubbing `window`/`fetch`, simulates exactly one rejected request among
 * several successful ones, and asserts the search still completes with the
 * results the successful requests could produce -- not an unhandled
 * rejection.
 *
 * No test framework -- plain assertions, exits non-zero on failure, same
 * convention as this repo's Python tests use for anything simple enough
 * not to need one.
 */
'use strict';

global.window = {}; // forces dge-search.js's browser (fetch-based) branch, not its Node/fs one

const path = require('path');
const ROOT = path.join(__dirname);
const DGENorm = require(path.join(ROOT, 'dge-normalize.js'));
global.DGENorm = DGENorm; // dge-search.js's browser branch reads root.DGENorm, not require()

function assert(cond, msg) {
  if (!cond) throw new Error('FAIL: ' + msg);
}

async function main() {
  // 'rAma' folds under nasal-class collapsing (m -> n, see dge-normalize.js's
  // NASALS table) to pkey 'rana', trigrams ['^ra','ran','ana','na$'] --
  // confirmed with a direct normalizeQuery() call before hardcoding this,
  // not assumed from the untransformed spelling.
  let fetchCount = 0, failureTriggered = false;
  global.fetch = function (url) {
    fetchCount++;
    if (url.includes('/postings/') && url.includes('/vedas.json') && url.includes('ran') && !failureTriggered) {
      failureTriggered = true;
      return Promise.reject(new Error('simulated network failure (e.g. ERR_CONNECTION_RESET)'));
    }
    if (url.endsWith('manifest.json')) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          granthas: [
            { gi: 0, slug: 'a', title: 'A', category: 'vedas', schema: 'vedic_text', units: 1, shard: 'units/a.json' },
            { gi: 1, slug: 'b', title: 'B', category: 'itihasa', schema: 'itihasa_purana_text', units: 1, shard: 'units/b.json' },
          ],
          df: { '^ra': 2, 'ran': 2, 'ana': 2 },
          sections: ['vedas', 'itihasa'],
        }),
      });
    }
    if (url.includes('/units/')) {
      const isA = url.includes('/a.json');
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve([{ u: 0, pk: 'rana', ck: 'rana', s: isA ? 'राम अ' : 'राम ब' }]),
      });
    }
    if (url.includes('/postings/')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve([[0, 0], [1, 0]]) });
    }
    return Promise.resolve({ ok: false });
  };

  const DGESearch = require(path.join(ROOT, 'dge-search.js'));
  const idx = await DGESearch.create('http://fake-cdn/index');
  const hits = await idx.search('rAma', { scheme: 'slp1', limit: 10 });

  assert(failureTriggered, 'the simulated failure never actually fired -- test setup is wrong, not the code under test');
  assert(Array.isArray(hits), 'search() should resolve to an array even when one underlying fetch rejected');
  assert(hits.length === 2, `expected both granthas to still be found via their surviving requests, got ${hits.length}`);
  assert(hits.every((h) => h.score === 1 && h.via === 'pkey-exact'), 'expected exact pkey matches for both hits');

  assert(hits.degraded === true, 'a search that lost a fetch must say so (hits.degraded)');

  // The failed posting union must NOT have been cached (dge-search.js's
  // FETCH_ERR contract, 31 Aug 2026): the same query again -- with the
  // network now healthy -- must refetch the trigram that failed and come
  // back clean. Before this contract, the first run's hole was cached for
  // the whole session, so the "same" search returned different results
  // depending on which run a reader happened to look at.
  const hits2 = await idx.search('rAma', { scheme: 'slp1', limit: 10 });
  assert(hits2.degraded === false, 'a healthy re-run must not inherit the failed run\'s degraded state from a cache');
  assert(hits2.length === 2, `healthy re-run should find both granthas, got ${hits2.length}`);

  console.log(`PASS: search() completed with ${hits.length} hits after ${fetchCount} fetch() calls, ` +
              'one of which was rejected -- the failure degraded gracefully instead of taking the whole query down, ' +
              'was reported via hits.degraded, and was NOT cached (the re-run came back clean).');

  // ---- scenario 2: searchExact under a transient word-bucket failure ----
  // The live report this models (31 Aug 2026): the same word searched twice
  // minutes apart returned different result sets, because a dropped section
  // fetch during the first run was CACHED as "no words here" and every later
  // run inherited the hole. Contract now: run 1 is degraded (and may be
  // empty), the failure is not cached, run 2 refetches and is complete.
  let wordFailuresLeft = 1, wordBucketCalls = 0, missingSectionCalls = 0;
  global.fetch = function (url) {
    if (url.endsWith('manifest.json')) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          granthas: [
            { gi: 0, slug: 'a', title: 'A', category: 'vedas', schema: 'vedic_text', units: 1, shard: 'units/a.json' },
          ],
          df: {},
          sections: ['vedas', 'itihasa'],
          wordBucketDeepen: {},
          vocabChunks: 0,
        }),
      });
    }
    if (url.includes('/words/')) {
      if (url.includes('/vedas.json')) {
        wordBucketCalls++;
        if (wordFailuresLeft > 0) {
          wordFailuresLeft--;
          return Promise.reject(new Error('simulated dropped word-bucket request'));
        }
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ rana: [[0, 0]] }) });
      }
      // the other section has no file for this bucket: a real 404, which
      // IS a cacheable fact about the index (not a transient failure).
      missingSectionCalls++;
      return Promise.resolve({ ok: false, status: 404 });
    }
    if (url.includes('/units/')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve([{ u: 0, pk: 'rana', ck: 'rana', s: 'राम अ' }]) });
    }
    return Promise.resolve({ ok: false, status: 404 });
  };

  const idxB = await DGESearch.create('http://fake-cdn/index2');
  const ex1 = await idxB.searchExact('rAma', { scheme: 'slp1', limit: 10 });
  assert(ex1.length === 0, `run 1: the only section holding the word dropped its request, so no hits, got ${ex1.length}`);
  assert(ex1.degraded === true, 'run 1 must be marked degraded, not presented as a clean "no matches"');

  const ex2 = await idxB.searchExact('rAma', { scheme: 'slp1', limit: 10 });
  assert(ex2.degraded === false, 'run 2 (network healed) must come back clean');
  assert(ex2.length === 1 && ex2[0].via === 'word-index-exact', 'run 2 must find the word the dropped fetch hid');
  assert(wordBucketCalls === 2, `the FAILED bucket fetch must not be cached (expected a refetch; saw ${wordBucketCalls} calls)`);

  const ex3 = await idxB.searchExact('rAma', { scheme: 'slp1', limit: 10 });
  assert(ex3.length === 1, 'run 3 should serve from cache and still find the word');
  assert(wordBucketCalls === 2, `run 3 must serve the SUCCESSFUL union from cache (saw ${wordBucketCalls} bucket calls)`);
  assert(missingSectionCalls <= 2, `a real 404 is a cacheable fact -- expected no third fetch of the missing section (saw ${missingSectionCalls})`);

  console.log('PASS: searchExact() marked a dropped word-bucket fetch degraded, did not cache it, ' +
              'recovered fully on the retry, and cached the healthy union (404s stayed cached as absence).');
}

main().catch((e) => {
  console.error(e.message || e);
  process.exit(1);
});
