/*
 * dge-search.js — client-side global fuzzy search over the static index built
 * by build_search_index.py. Loads manifest + only the per-trigram postings files
 * and unit shards a query actually touches (keeps a 300MB+ corpus feasible on
 * GitHub Pages / jsDelivr).
 *
 * Depends on DGENorm (dge-normalize.js). In the browser, `fetchJSON` uses fetch;
 * in Node it uses fs (so the same code is testable headless).
 *
 * Usage (browser):
 *   const idx = await DGESearch.create('search_index');   // base URL
 *   const hits = await idx.search('agnimILe', {scheme:'slp1', limit:20});
 */
(function (root) {
  'use strict';
  var N = (typeof require !== 'undefined') ? require('./dge-normalize.js')
                                           : root.DGENorm;

  var isNode = (typeof window === 'undefined');

  // Sentinel distinguishing "the request FAILED" (network drop, server
  // error, truncated body) from "the file legitimately does not exist"
  // (404 -- a grantha with no postings for a trigram, a bucket with no
  // file for a section: normal, and safe to remember). The two used to
  // collapse into one null, and the null got CACHED -- so one flaky
  // mobile request didn't just degrade THAT query, it silently poisoned
  // every later query in the session that touched the same file (reported
  // live, 31 Aug 2026: the same word searched twice minutes apart in two
  // scripts returned different result sets, because the first run's
  // dropped section fetches were cached as "nothing there"). A FETCH_ERR
  // result is never cached, so a retry actually refetches; the degraded
  // flag it propagates lets the UI say so instead of presenting a
  // partial sweep as the whole truth.
  var FETCH_ERR = { fetchError: true };

  var fetchJSON;
  if (isNode) {
    var fs = require('fs'), path = require('path');
    fetchJSON = function (base, rel) {
      // rel is a literal filesystem path (e.g. from safeTrigram()) -- joined
      // as-is, no URL decoding involved.
      var p = path.join(base, rel);
      if (!fs.existsSync(p)) return Promise.resolve(null);
      return Promise.resolve(JSON.parse(fs.readFileSync(p, 'utf8')));
    };
  } else {
    fetchJSON = function (base, rel) {
      // rel is a literal filename (e.g. from safeTrigram()); percent-encode
      // each path SEGMENT (not the whole rel, which would also escape the
      // '/' separators) so a literal '^'/'$' in a trigram's filename reaches
      // the server as the same byte it is on disk. Every caller of
      // fetchJSON hands it a literal path, never a pre-encoded one -- this
      // is the one place that turns literal into URL, so the two can't drift
      // out of sync the way a per-caller "%XX" escape once did (a browser's
      // fetch() percent-DEcodes "%XX" in a URL before requesting it, so a
      // filename that already contained a literal "%" 404'd).
      var url = base + '/' + rel.split('/').map(encodeURIComponent).join('/');
      // priority:'high' is a progressive-enhancement hint (ignored, not an
      // error, on a browser that doesn't recognise the option) -- every
      // fetch through this function is on the critical path of a search the
      // reader is actively waiting on, never a background/idle one (that
      // path is prefetchManifest() in global-search.js, a separate call).
      //
      // 24 Aug 2026: caught and resolved here, not just a non-ok response
      // -- a genuine network failure (a real risk against a third-party
      // CDN under real mobile conditions) used to REJECT this promise, and
      // since every caller in this file fetches many of these in one
      // Promise.all (up to ~33 postings, up to 120 shards), one flaky
      // request was taking down the ENTIRE search with it, not just the
      // piece that failed.
      // 31 Aug 2026: but "resolve to null like a 404" went too far the
      // other way -- see FETCH_ERR above. Now: 404 -> null (a real fact
      // about the index, cacheable), anything else -> FETCH_ERR (a fact
      // about THIS request only, never cacheable). Either way the rest of
      // an otherwise-successful fan-out still degrades gracefully instead
      // of erroring outright.
      return fetch(url, { priority: 'high' })
        .then(function (r) {
          if (r.ok) return r.json().catch(function () { return FETCH_ERR; });
          return r.status === 404 ? null : FETCH_ERR;
        })
        .catch(function () { return FETCH_ERR; });
    };
  }

  // Plain-text twin of fetchJSON, for the vocab/<i>.txt chunks (newline-
  // separated word list, deliberately not JSON -- see build_search_index.py's
  // vocab-writing comment). Same two branches, same URL-encoding rule, same
  // null-on-404 / FETCH_ERR-on-failure contract.
  var fetchText;
  if (isNode) {
    fetchText = function (base, rel) {
      var p = require('path').join(base, rel);
      if (!require('fs').existsSync(p)) return Promise.resolve(null);
      return Promise.resolve(require('fs').readFileSync(p, 'utf8'));
    };
  } else {
    fetchText = function (base, rel) {
      var url = base + '/' + rel.split('/').map(encodeURIComponent).join('/');
      return fetch(url)
        .then(function (r) {
          if (r.ok) return r.text().catch(function () { return FETCH_ERR; });
          return r.status === 404 ? null : FETCH_ERR;
        })
        .catch(function () { return FETCH_ERR; });
    };
  }

  // One posting file per TRIGRAM (not per 2-char prefix bucket) -- mirrors
  // build_search_index.py's safe_trigram_filename(). A 2-char bucket used to
  // put every "ram"/"ran"/"raj"/... trigram in one multi-MB file a query for
  // any of them had to download whole; this fetches exactly the trigram it
  // asked for.
  //
  // Returns the trigram's LITERAL filename (real trigrams are always
  // {A-Za-z^$}, all filesystem-safe as-is -- see safe_trigram_filename()'s
  // docstring) -- NOT URL-encoded here. Percent-encoding ^/$ for the URL is
  // fetchJSON's job (its browser branch encodes each path segment), because
  // its Node branch needs this same literal string as a real filesystem
  // path instead. Encoding it here once, for only one of the two branches
  // fetchJSON can take, was a real bug: it made the Node-local test (used to
  // validate this fix) pass while the browser path was silently broken.
  function safeTrigram(tg) {
    return tg.replace(/[^0-9A-Za-z^$]/g, '_') || '_';
  }

  // How many of a trigram set's members to actually fetch, rarest first (by
  // manifest.df -- document frequency, i.e. posting-file length). A common
  // trigram like an "na"-class one matches half the corpus and costs the
  // most to fetch while discriminating the least; a rare one narrows the
  // candidate set just as correctly for a fraction of the bytes. Measured
  // against the real index: राम went from 16.1 MB (every trigram) to 549 KB
  // (rarest 3) -- see SEARCH_ARCHITECTURE.md. A set with FEWER members than
  // this is fetched in full; there is nothing to save on a short word.
  var MAX_TRIS_PER_SET = 3;

  // A boundary trigram (^xy / yz$) only ever appears in the index at a
  // unit's own true start/end (see search()'s own comment on this), so it
  // never counts toward requiredCount/`need` below -- it's a bonus signal,
  // not part of what decides candidacy. A short, common query mixes both
  // kinds among its "rarest" trigrams (^ka and ya$ are individually rarer
  // than any interior 3-letter run just because they're anchored), and
  // picking rarest-N across BOTH kinds indiscriminately let boundary
  // trigrams crowd interior ones out of the fetched set entirely -- measured
  // live against the real index: "kAntAya" fetched ^ka/ya$/tay, leaving only
  // ONE interior trigram (tay, df 39,729) to decide candidacy at all. With
  // requiredCount collapsed to 1, `need` (60% of 1, floored to 1) became
  // "matches this one very common trigram anywhere" -- 39,729 units all
  // tied as equally "complete," and Sumadhva Vijaya's real exact-match verse
  // (which does contain कान्ताय, confirmed directly against the built
  // index) never survived the tie-break into the shard-open budget at all.
  var isBoundaryTrigram = function (tg) { return tg.indexOf('^') !== -1 || tg.indexOf('$') !== -1; };

  function rarestOf(set, df) {
    // A trigram absent from df has zero postings anywhere in the corpus
    // (nothing it could match) -- drop it before fetching, not after: no
    // file exists for it, so keeping it in would just be a wasted request.
    var withDf = set.filter(function (tg) { return df[tg] != null; });
    var byRarity = function (a, b) { return df[a] - df[b]; };
    var interior = withDf.filter(function (tg) { return !isBoundaryTrigram(tg); }).sort(byRarity);
    var boundary = withDf.filter(isBoundaryTrigram).sort(byRarity);
    // Interior trigrams get the full budget on their own -- they're what
    // requiredCount/`need` actually run on. Boundary trigrams are fetched
    // ON TOP, up to the same count, since a genuine start/end match is a
    // real, cheap (rare-by-construction) bonus signal worth having when it
    // exists, just never at the interior budget's expense.
    return interior.slice(0, MAX_TRIS_PER_SET).concat(boundary.slice(0, MAX_TRIS_PER_SET));
  }

  // Root/verse schemas vs. commentary schemas vs. genuinely ambiguous
  // independent-prose schemas (dge/data/schemas.json's own _description for
  // each name is the source of truth here, not a guess) -- lets the global
  // search UI offer an honest "shlokas only / commentary only" filter
  // without re-deriving schema semantics itself or guessing from a title.
  var SHLOKA_SCHEMAS = { vedic_text:1, itihasa_purana_text:1, smriti_dharmashastra_text:1,
    stotra_text:1, grantha_mula_text:1, dasa_sahitya_composition:1, dasa_pada_text:1 };
  var COMMENTARY_SCHEMAS = { grantha_tika_text:1, grantha_tippani_text:1 };
  function classifyContentType(schema) {
    if (SHLOKA_SCHEMAS[schema]) return 'shloka';
    if (COMMENTARY_SCHEMAS[schema]) return 'commentary';
    return 'prose'; // generic / grantha_prakarana_text -- independent treatises, neither a root verse nor a commentary on one
  }

  // Damerau-Levenshtein with early exit
  function editDist(a, b, maxd) {
    var la = a.length, lb = b.length;
    if (Math.abs(la - lb) > maxd) return maxd + 1;
    var prev = [], cur = [], i, j;
    for (j = 0; j <= lb; j++) prev[j] = j;
    for (i = 1; i <= la; i++) {
      cur[0] = i; var rowmin = cur[0];
      for (j = 1; j <= lb; j++) {
        var cost = a[i - 1] === b[j - 1] ? 0 : 1;
        cur[j] = Math.min(cur[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost);
        rowmin = Math.min(rowmin, cur[j]);
      }
      if (rowmin > maxd) return maxd + 1;
      for (j = 0; j <= lb; j++) prev[j] = cur[j];
    }
    return prev[lb];
  }

  function Index(base, manifest) {
    this.base = base;
    this.manifest = manifest;
    this.granthas = manifest.granthas;
    this.df = manifest.df || {};
    this.sections = manifest.sections || [];
    this._shardCache = {};
    this._postingCache = {};
    this._wordBucketCache = {};
  }

  // Does slug fall under any of the given slug-path prefixes? A prefix
  // matches its own exact slug or any deeper path under it ('kavya' never
  // matches 'kavya_alankara' -- segment-bounded, not raw startsWith).
  // Shared by the include-scope filter (opts.includeGranthaPrefixes, the
  // 31 Aug 2026 "search inside ANY node of the Library tree, several at
  // once" project-lead ask) and usable at every depth the slugs
  // themselves have: a whole section ('kavya_alankara'), one work
  // ('DvaitaVedanta/Itara/Kavya/raghavendra_vijaya'), a single sarga's own grantha.
  function slugInPrefixes(slug, prefixes) {
    for (var p = 0; p < prefixes.length; p++) {
      if (slug === prefixes[p] || slug.indexOf(prefixes[p] + '/') === 0) return true;
    }
    return false;
  }

  // The postings/words trees are partitioned by SECTION (top-level slug
  // segment). A scope of include-prefixes can only ever hit granthas in
  // the sections those prefixes start with -- so a search scoped to one
  // kavya work has no business fetching the vedas' or puranas' files at
  // all. Returns the (deduped) section subset the prefixes touch, or null
  // for "all sections" (no prefixes given, or a prefix whose head isn't a
  // known section -- fetching everything is the safe answer there).
  Index.prototype._sectionsForPrefixes = function (prefixes) {
    if (!prefixes || !prefixes.length) return null;
    var known = {};
    for (var i = 0; i < this.sections.length; i++) known[this.sections[i]] = 1;
    var out = {}, n = 0;
    for (var p = 0; p < prefixes.length; p++) {
      var head = String(prefixes[p]).split('/')[0];
      if (!known[head]) return null;
      if (!out[head]) { out[head] = 1; n++; }
    }
    return n ? Object.keys(out) : null;
  };

  // ---- EXACT word-level index (words/<bucket>/<section>.json) ----
  // Mirrors build_search_index.py's word_tokens()/bucket_key() EXACTLY --
  // the two sides MUST tokenize and bucket identically or a query word
  // looks in the wrong file and finds nothing (test-parity.js asserts the
  // tokenizer half). Tokens split on ANY char outside [0-9A-Za-z] plus ॐ
  // (punctuation baked into a token made 5.6% of corpus postings
  // unfindable under a whitespace-only split -- measured, Fable review
  // 30 Aug 2026); pure-digit tokens (verse numbers) drop. Bucket names
  // encode uppercase as lowercase+'-' ('Ba' -> 'b-a') so 'Ba'/'ba' can
  // never collide on a case-insensitive filesystem, and anything outside
  // [0-9A-Za-z] maps to '_'.
  function wordTokens(pk) {
    return String(pk || '').split(/[^0-9A-Za-zॐ]+/).filter(function (t) {
      return t && !/^[0-9]+$/.test(t);
    });
  }
  function bucketKey(word, depth) {
    var out = '';
    var prefix = word.slice(0, depth);
    for (var i = 0; i < prefix.length; i++) {
      var ch = prefix[i];
      if (ch >= '0' && ch <= '9' || ch >= 'a' && ch <= 'z') out += ch;
      else if (ch >= 'A' && ch <= 'Z') out += ch.toLowerCase() + '-';
      else out += '_';
    }
    return out || '_';
  }
  // Adaptive depth: manifest.wordBucketDeepen is a presence-set written by
  // the builder ({prefixKey: 1}); a word's 2-char key being present means
  // its bucket uses 3 chars, and that 3-char key also present means 4 --
  // only the few dozen genuinely oversized buckets deepen, everything else
  // stays at 2 (see WORD_BUCKET_DEEPEN_BYTES in build_search_index.py).
  Index.prototype._wordBucketOf = function (word) {
    var deepen = this.manifest.wordBucketDeepen || {};
    var k2 = bucketKey(word, 2);
    if (!deepen[k2]) return k2;
    var k3 = bucketKey(word, 3);
    return deepen[k3] ? bucketKey(word, 4) : k3;
  };

  // One file per (bucket, section): {word: [[gi,ui],...], ...}. Cached per
  // (bucket, scope) the same way _loadPosting caches per (trigram, scope);
  // an absent section file (404 -> null) is simply an empty contribution,
  // never fatal to the rest of the fan-out. A FAILED section fetch
  // (FETCH_ERR) also just goes missing from this run's maps -- but it
  // marks the result `degraded` and keeps it OUT of the cache, so the
  // next query over the same bucket refetches instead of inheriting this
  // run's hole for the whole session (see FETCH_ERR's own comment).
  // `scope` may be null (every section), one section name (back-compat
  // with the old single-section picker), or an ARRAY of section names
  // (computed by _sectionsForPrefixes for an include-scoped search) --
  // the fan-out and the cache key both honour exactly that subset.
  Index.prototype._loadWordBucket = function (bucket, scope) {
    var self = this;
    var secs = !scope ? this.sections : (Array.isArray(scope) ? scope : [scope]);
    var key = bucket + '::' + (!scope ? '*' : secs.slice().sort().join(','));
    if (this._wordBucketCache[key]) return Promise.resolve(this._wordBucketCache[key]);
    var p = Promise.all(secs.map(function (sec) {
      return fetchJSON(self.base, 'words/' + bucket + '/' + sec + '.json');
    })).then(function (parts) {
      var maps = [], degraded = false;
      parts.forEach(function (d) {
        if (d === FETCH_ERR) degraded = true;
        else if (d) maps.push(d);
      });
      if (degraded) maps.degraded = true;
      return maps;
    });
    return p.then(function (maps) {
      if (!maps.degraded) self._wordBucketCache[key] = maps;
      return maps;
    });
  };

  // Exact word search: the direct answer to "which units contain this
  // word", with none of the trigram path's candidate-tie problem (see
  // search()'s own comments on MAX_SHARDS -- a common word's 3-letter
  // fragments tie with tens of thousands of unrelated units corpus-wide,
  // and no reasonable shard budget can resolve that; a WORD is a bounded,
  // selective key, so its postings list IS the answer). Two passes over
  // each fetched bucket file:
  //   1. direct dict lookup of the query word itself (whole-word match);
  //   2. a prefix scan of the bucket's keys (indexOf === 0) so a word
  //      living INSIDE a longer compound-initial token still surfaces --
  //      real Sanskrit text joins words by sandhi/samasa far more often
  //      than it separates them with spaces, so whole-word-only would
  //      miss most genuine occurrences. Prefix (not full substring) keeps
  //      the scan meaningful: the bucket is keyed by first-2-chars, so
  //      only prefix matches are even findable in the right bucket.
  // Multi-word queries intersect (units containing EVERY query word),
  // falling back to the best partial overlap when the intersection is
  // empty -- exact-match semantics for the phrase, degrading gracefully
  // rather than to nothing.
  Index.prototype.searchExact = function (query, opts) {
    opts = opts || {};
    var self = this;
    var limit = opts.limit || 30;
    var section = opts.section || null;
    var q = N.normalizeQuery(query, opts);
    if (!q.pkey) return Promise.resolve([]);
    var qwords = wordTokens(q.pkey);
    if (!qwords.length) return Promise.resolve([]);
    var onProgress = opts.onProgress;

    // Scope: includeGranthaPrefixes (multi-select Library-tree targets, any
    // depth) narrows the sweep to matching granthas AND shrinks the section
    // fan-out to just the sections those targets live in; the admin-only
    // excludes then apply within that. `section` (the old single-section
    // scope) still works and wins when set.
    var excludePrefixes = opts.excludeGranthaPrefixes || [];
    var includePrefixes = opts.includeGranthaPrefixes || [];
    var isOutOfScope = function (gi) {
      var slug = self.granthas[gi] && self.granthas[gi].slug;
      if (!slug) return false;
      if (includePrefixes.length && !slugInPrefixes(slug, includePrefixes)) return true;
      return excludePrefixes.length ? slugInPrefixes(slug, excludePrefixes) : false;
    };
    var scope = section || self._sectionsForPrefixes(includePrefixes);

    var buckets = {};
    qwords.forEach(function (w) { buckets[self._wordBucketOf(w)] = 1; });
    var bucketNames = Object.keys(buckets);

    return allWithProgress(
      bucketNames.map(function (b) { return self._loadWordBucket(b, scope); }),
      onProgress && function (done, total) { onProgress('postings', done, total); }
    ).then(function (bucketMapsPerName) {
      // Any bucket whose section fan-out lost a request marks this whole
      // run degraded -- the caller must not present (or cache-compare)
      // this result as the index's full answer. See FETCH_ERR above.
      var degraded = false;
      bucketMapsPerName.forEach(function (m) { if (m && m.degraded) degraded = true; });
      // unitHits: "gi:ui" -> { words: {queryWord: 'exact'|'prefix'}, }
      var unitHits = {};
      qwords.forEach(function (w, wi) {
        var maps = bucketMapsPerName[bucketNames.indexOf(self._wordBucketOf(w))] || [];
        maps.forEach(function (wordMap) {
          // pass 1: whole-word
          var rows = wordMap[w];
          if (rows) rows.forEach(function (r) {
            if (isOutOfScope(r[0])) return;
            var key = r[0] + ':' + r[1];
            (unitHits[key] = unitHits[key] || {})[wi] = 'exact';
          });
          // pass 2: compound-initial (prefix) -- only for words long enough
          // that a prefix hit is a real signal, not noise.
          if (w.length >= 4) {
            for (var k in wordMap) {
              if (k.length > w.length && k.indexOf(w) === 0) {
                wordMap[k].forEach(function (r) {
                  if (isOutOfScope(r[0])) return;
                  var key = r[0] + ':' + r[1];
                  var h = (unitHits[key] = unitHits[key] || {});
                  if (h[wi] !== 'exact') h[wi] = 'prefix';
                });
              }
            }
          }
        });
      });

      // Rank: units matching MORE query words first; among equals, exact
      // beats prefix; among those, root/verse text (shloka) before
      // commentary/prose -- a reader looking for a verse wants the verse
      // itself above the ṭīkā quoting it.
      var keys = Object.keys(unitHits);
      var scored = keys.map(function (key) {
        var h = unitHits[key];
        var nWords = 0, nExact = 0;
        for (var wi in h) { nWords++; if (h[wi] === 'exact') nExact++; }
        return { key: key, nWords: nWords, nExact: nExact };
      });
      var maxWords = 0;
      scored.forEach(function (s) { if (s.nWords > maxWords) maxWords = s.nWords; });
      // Intersection first (every query word present); fall back to the
      // best partial tier only if nothing matches all words.
      var tier = scored.filter(function (s) { return s.nWords === maxWords; });
      tier.sort(function (a, b) {
        if (a.nExact !== b.nExact) return b.nExact - a.nExact;
        var ga = self.granthas[+a.key.split(':')[0]] || {};
        var gb = self.granthas[+b.key.split(':')[0]] || {};
        var sa = SHLOKA_SCHEMAS[ga.schema] ? 0 : 1;
        var sb = SHLOKA_SCHEMAS[gb.schema] ? 0 : 1;
        return sa - sb;
      });
      var picked = tier.slice(0, limit * 2); // headroom: some may lack shard rows

      var giSet = {};
      picked.forEach(function (s) { giSet[s.key.split(':')[0]] = 1; });
      return allWithProgress(
        Object.keys(giSet).map(function (gi) { return self._loadShard(+gi); }),
        onProgress && function (done, total) { onProgress('shards', done, total); }
      ).then(function (shardVals) {
        shardVals.forEach(function (v) { if (v && v.degraded) degraded = true; });
        var hits = [];
        picked.forEach(function (s) {
          var parts = s.key.split(':'), gi = +parts[0], ui = +parts[1];
          var shard = self._shardCache[gi]; if (!shard) return;
          var row = shard[ui]; if (!row) return;
          var g = self.granthas[gi];
          var allExact = s.nExact === qwords.length;
          hits.push({ grantha: g.slug, title: g.title, category: g.category,
            contentType: classifyContentType(g.schema),
            unit: row.u, snippet: row.s, _pkLen: (row.pk || '').length,
            score: allExact ? 0.99 : (0.9 * s.nWords / qwords.length + 0.05 * (s.nExact / qwords.length)),
            via: allExact ? 'word-index-exact' : 'word-index-partial' });
        });
        // Final tiebreak, only computable now that shards are open: among
        // equal-score hits, the SHORTER unit first -- a verse that contains
        // the query words beats a 300-word commentary paragraph mentioning
        // them ten lines apart. Stable sort preserves the earlier
        // exact-over-prefix / verse-schema-over-commentary ordering for
        // genuinely equal pairs.
        hits.sort(function (a, b) {
          if (a.score !== b.score) return b.score - a.score;
          return a._pkLen - b._pkLen;
        });
        hits.forEach(function (h) { delete h._pkLen; });
        var out = hits.slice(0, limit);
        // The word index IS exhaustive for whole words and compound-initial
        // prefixes -- a word buried mid/end-compound is searchCompound()'s
        // job (the vocabulary grep below), and a sandhi-transformed
        // occurrence the fuzzy trigram path's. partial=false: what was
        // swept, was swept completely.
        out.partial = false;
        // ...UNLESS a fetch actually failed mid-sweep. degraded says "this
        // run's answer is missing pieces through no fault of the query" --
        // the UI retries / says so instead of treating it as truth.
        out.degraded = degraded;
        return out;
      });
    });
  };

  // ---- compound-interior search: grep the VOCABULARY, not the corpus ----
  // searchExact() covers whole words and compound-INITIAL occurrences (the
  // prefix scan); a query word buried in the middle or at the end of a
  // compound (nilakAntAya, divyakAntAya for kAntAya) lives in the
  // compound's own bucket, which a prefix-keyed lookup can never fetch.
  // Substring-scanning the 300MB corpus is out of the question -- but the
  // complete VOCABULARY (~2M distinct words, vocab/<i>.txt, ~10MB gzipped
  // once over the CDN and then HTTP-cached forever against the immutable
  // commit-pinned URL) is small enough to grep client-side in one pass.
  // Matched compound words then resolve through the same bucket postings
  // as any exact lookup: exhaustive substring recall at exact precision.
  var MAX_COMPOUND_WORDS = 400;   // matched vocabulary words considered (shortest first)
  var MAX_COMPOUND_BUCKETS = 40;  // distinct bucket fan-out cap

  Index.prototype._loadVocabChunk = function (i) {
    if (!this._vocabCache) this._vocabCache = {};
    if (this._vocabCache[i]) return this._vocabCache[i];
    var self = this;
    // Cache the in-flight promise, but evict it if the fetch FAILED
    // (FETCH_ERR) so a later compound scan retries the chunk instead of
    // permanently treating a tenth of the vocabulary as empty.
    var p = fetchText(this.base, 'vocab/' + i + '.txt').then(function (txt) {
      if (txt === FETCH_ERR) delete self._vocabCache[i];
      return txt;
    });
    this._vocabCache[i] = p;
    return p;
  };
  // True once every chunk has been fetched at least once this session --
  // the UI uses this to decide whether a compound scan is "free" (all in
  // memory) or will cost the reader a real download they should opt into.
  Index.prototype.vocabLoaded = function () {
    var n = this.manifest.vocabChunks || 0;
    if (!n || !this._vocabCache) return false;
    for (var i = 0; i < n; i++) if (!this._vocabResolved || !this._vocabResolved[i]) return false;
    return true;
  };

  Index.prototype.searchCompound = function (query, opts) {
    opts = opts || {};
    var self = this;
    var limit = opts.limit || 30;
    var section = opts.section || null;
    var onProgress = opts.onProgress;
    var q = N.normalizeQuery(query, opts);
    var qwords = q.pkey ? wordTokens(q.pkey) : [];
    // Single-word queries only: a multi-word phrase already has
    // intersection semantics in searchExact, and crossing that with
    // per-word compound expansion multiplies cost for a case no reader
    // has asked for. A token under 4 chars is too unselective to scan
    // for (contained in a huge fraction of the vocabulary).
    if (qwords.length !== 1 || qwords[0].length < 4) return Promise.resolve([]);
    var token = qwords[0];
    var nChunks = this.manifest.vocabChunks || 0;
    if (!nChunks) return Promise.resolve([]); // pre-vocab index published

    // Same scope contract as searchExact: include-prefixes narrow both the
    // candidate granthas and the bucket-postings section fan-out below.
    var excludePrefixes = opts.excludeGranthaPrefixes || [];
    var includePrefixes = opts.includeGranthaPrefixes || [];
    var isOutOfScope = function (gi) {
      var slug = self.granthas[gi] && self.granthas[gi].slug;
      if (!slug) return false;
      if (includePrefixes.length && !slugInPrefixes(slug, includePrefixes)) return true;
      return excludePrefixes.length ? slugInPrefixes(slug, excludePrefixes) : false;
    };
    var scope = section || self._sectionsForPrefixes(includePrefixes);

    var chunkIdx = [];
    for (var i = 0; i < nChunks; i++) chunkIdx.push(i);
    if (!this._vocabResolved) this._vocabResolved = {};
    var degraded = false;
    return allWithProgress(
      chunkIdx.map(function (i) {
        return self._loadVocabChunk(i).then(function (txt) {
          // Only a chunk that actually ARRIVED counts as resolved --
          // vocabLoaded() drives the "scan is free now" auto-run, and a
          // dropped chunk must not be remembered as fetched.
          if (typeof txt === 'string') self._vocabResolved[i] = true;
          else if (txt === FETCH_ERR) degraded = true;
          return txt;
        });
      }),
      onProgress && function (done, total) { onProgress('vocab', done, total); }
    ).then(function (chunks) {
      // Grep pass: every vocabulary word CONTAINING the token, minus
      // whole-word/prefix matches (searchExact's own territory -- a word
      // starting with the token shares its first chars and therefore its
      // bucket, so those were already found). Scanning by indexOf over the
      // raw chunk text and expanding to line boundaries touches only the
      // match sites, never splitting 2M lines up front.
      var matched = [];
      chunks.forEach(function (txt) {
        if (typeof txt !== 'string' || !txt) return;
        var at = txt.indexOf(token);
        while (at !== -1) {
          var s = txt.lastIndexOf('\n', at) + 1;
          var e = txt.indexOf('\n', at);
          if (e === -1) e = txt.length;
          var w = txt.slice(s, e);
          if (w.indexOf(token) > 0) matched.push(w); // >0: interior/end only
          at = txt.indexOf(token, e);
        }
      });
      // Shortest first: the tightest compound around the word is the most
      // recognisable occurrence, and it also keeps the bucket fan-out cap
      // spending its budget on the best candidates.
      matched.sort(function (a, b) { return a.length - b.length; });
      matched = matched.slice(0, MAX_COMPOUND_WORDS);

      var buckets = {}, nBuckets = 0, byBucket = {};
      for (var m = 0; m < matched.length; m++) {
        var b = self._wordBucketOf(matched[m]);
        if (!buckets[b]) {
          if (nBuckets >= MAX_COMPOUND_BUCKETS) continue;
          buckets[b] = 1; nBuckets++; byBucket[b] = [];
        }
        byBucket[b].push(matched[m]);
      }
      var bucketNames = Object.keys(buckets);
      return allWithProgress(
        bucketNames.map(function (b) { return self._loadWordBucket(b, scope); }),
        onProgress && function (done, total) { onProgress('postings', done, total); }
      ).then(function (maps) {
        maps.forEach(function (m) { if (m && m.degraded) degraded = true; });
        var unitWord = {}; // "gi:ui" -> shortest matched compound containing it
        bucketNames.forEach(function (b, bi) {
          (maps[bi] || []).forEach(function (wordMap) {
            byBucket[b].forEach(function (w) {
              var rows = wordMap[w];
              if (!rows) return;
              rows.forEach(function (r) {
                if (isOutOfScope(r[0])) return;
                var key = r[0] + ':' + r[1];
                if (!unitWord[key] || w.length < unitWord[key].length) unitWord[key] = w;
              });
            });
          });
        });
        var keys = Object.keys(unitWord);
        keys.sort(function (a, b) { return unitWord[a].length - unitWord[b].length; });
        var picked = keys.slice(0, limit * 2);
        var giSet = {};
        picked.forEach(function (k) { giSet[k.split(':')[0]] = 1; });
        return allWithProgress(
          Object.keys(giSet).map(function (gi) { return self._loadShard(+gi); }),
          onProgress && function (done, total) { onProgress('shards', done, total); }
        ).then(function (shardVals) {
          shardVals.forEach(function (v) { if (v && v.degraded) degraded = true; });
          var hits = [];
          picked.forEach(function (key) {
            var parts = key.split(':'), gi = +parts[0], ui = +parts[1];
            var shard = self._shardCache[gi]; if (!shard) return;
            var row = shard[ui]; if (!row) return;
            var g = self.granthas[gi];
            hits.push({ grantha: g.slug, title: g.title, category: g.category,
              contentType: classifyContentType(g.schema),
              unit: row.u, snippet: row.s, _pkLen: (row.pk || '').length,
              // Just under word-index-exact's 0.99: a genuine occurrence,
              // inside a compound rather than freestanding.
              score: 0.95, via: 'word-index-compound' });
          });
          hits.sort(function (a, b) { return a._pkLen - b._pkLen; });
          hits.forEach(function (h) { delete h._pkLen; });
          var out = hits.slice(0, limit);
          out.partial = false;
          out.degraded = degraded;
          return out;
        });
      });
    });
  };

  // Postings are partitioned by section (postings/<trigram>/<section>.json --
  // see build_search_index.py). A scoped search (opts.section set) fetches
  // just that one section's file for the trigram; an unscoped/global search
  // fans out across every section IN PARALLEL and unions the results -- the
  // same total postings a single unpartitioned file used to hold, just as
  // several small requests instead of one that pays for sections the query
  // never asked about. Cached per (trigram, scope) since the same trigram
  // can be looked up both ways in one session. fetchJSON now resolves a
  // failed section fetch to null rather than rejecting (see its own
  // comment), so one bad section out of the fan-out is simply missing from
  // the union below, not fatal to the other ten.
  // `scope`: null / one section name / array of section names -- same
  // contract as _loadWordBucket above.
  Index.prototype._loadPosting = function (tg, scope) {
    var self = this;
    var secs = !scope ? this.sections : (Array.isArray(scope) ? scope : [scope]);
    var key = tg + '::' + (!scope ? '*' : secs.slice().sort().join(','));
    if (this._postingCache[key]) return Promise.resolve(this._postingCache[key]);
    var safe = safeTrigram(tg);
    // Each argument here is a LITERAL path segment, same rule as safeTrigram()
    // -- fetchJSON alone decides how (or whether) to URL-encode it, for
    // whichever of its two branches actually runs. Encoding a segment here
    // too, on top of that, is exactly the double-encoding bug documented on
    // fetchJSON above; section names happen to be plain lowercase words with
    // nothing for encodeURIComponent to change, which is why that mistake
    // would have gone unnoticed here rather than 404ing outright.
    var p = Promise.all(secs.map(function (sec) {
      return fetchJSON(self.base, 'postings/' + safe + '/' + sec + '.json');
    })).then(function (parts) {
      var out = [], degraded = false;
      parts.forEach(function (d) {
        if (d === FETCH_ERR) degraded = true;
        else if (d) out.push.apply(out, d);
      });
      if (degraded) out.degraded = true;
      return out;
    });
    // Same never-cache-a-failure rule as _loadWordBucket: a degraded union
    // is this run's best effort, not a session-wide fact about the index.
    return p.then(function (rows) {
      if (!rows.degraded) self._postingCache[key] = rows;
      return rows;
    });
  };

  // `d || []` covers "no shard file" (fetchJSON resolves null on a 404).
  // A DROPPED shard request (FETCH_ERR) resolves to an empty, `degraded`-
  // marked array that is deliberately NOT cached -- one grantha whose
  // request drops still never takes the rest of the batch (Promise.all in
  // search(), below) down with it, its candidates are simply skipped by
  // the scoring pass's existing no-cached-shard guard, and the next query
  // that needs this grantha refetches it instead of finding a poisoned
  // "empty shard" in the session cache.
  Index.prototype._loadShard = function (gi) {
    var self = this, g = this.granthas[gi];
    if (this._shardCache[gi]) return Promise.resolve(this._shardCache[gi]);
    return fetchJSON(this.base, g.shard).then(function (d) {
      if (d === FETCH_ERR) { var empty = []; empty.degraded = true; return empty; }
      self._shardCache[gi] = d || []; return self._shardCache[gi];
    });
  };

  // Runs a batch of promises exactly like Promise.all, but reports how many
  // have settled as it goes -- for a determinate progress readout instead of
  // an indeterminate spinner. The total is known and reported (done=0)
  // BEFORE any of them resolve, since every caller already has the full
  // request list in hand (Object.keys(...).map(...)) before firing it; only
  // the "how many are back yet" count is genuinely unknown ahead of time.
  function allWithProgress(promises, onStep) {
    if (!onStep || !promises.length) return Promise.all(promises);
    var total = promises.length, done = 0;
    onStep(0, total);
    return Promise.all(promises.map(function (p) {
      return p.then(function (v) { onStep(++done, total); return v; });
    }));
  }

  // How much of the corpus one query may open. Both are round trips, not
  // memory: each grantha is a separate file.
  var MAX_SHARDS = 40;      // distinct granthas opened per search
  var MAX_UNITS = 6000;     // candidate units scored
  // Wall-clock cap on the shard-OPENING phase specifically (measured live:
  // a common word tying its full MAX_EXACT_SHARDS budget of 120 granthas
  // took 68+ seconds on a real mobile connection -- the browser's own
  // per-origin connection limit (~6 concurrent in Chrome) serializes 120
  // "parallel" fetches into ~20 sequential batches, and each batch's real
  // round-trip cost on a mobile network is nowhere near this sandbox's).
  // Whatever hasn't resolved by this deadline is treated exactly like a
  // shard that never loaded at all -- the scoring pass below already skips
  // a candidate with no cached shard (the same guard that already covers a
  // genuinely failed fetch), and out.partial already exists to say the
  // sweep wasn't exhaustive. Bounds worst-case latency to something a
  // reader will actually wait through, at the cost of an occasional real
  // hit landing just past the deadline and not appearing this time.
  var SHARD_TIMEOUT_MS = 8000;

  Index.prototype.search = function (query, opts) {
    opts = opts || {};
    var self = this;
    var limit = opts.limit || 20;
    // A falsy/omitted section means unscoped -- every section, fanned out
    // in parallel by _loadPosting. See "Partition the postings tree" in
    // SEARCH_ARCHITECTURE.md.
    var section = opts.section || null;
    var q = N.normalizeQuery(query, opts);
    if (!q.pkey) return Promise.resolve([]);
    var qtris = q.trigrams;

    // Trigram sets to search candidates by: the whole query (handles a
    // single word, or a short phrase typed correctly) PLUS, for a multi-word
    // query, each word's own trigrams searched separately. Without this, one
    // garbled word in an otherwise-correct query sank the whole search —
    // "kantaya kadhamne" shares almost none of ITS combined trigrams with
    // the verse it is trying to name (कान्ताय कल्याणगुणैकधाम्ने), because the
    // second word is wrong, even though "kantaya" alone is an exact match
    // for the verse's first word. Searching per word lets a candidate earn
    // its way in on any ONE word it genuinely contains.
    var trigramSets = [qtris];
    if (q.words.length > 1) {
      q.words.forEach(function (w) {
        if (w.length >= 3) trigramSets.push(N.trigrams(w));
      });
    }

    // 1) candidate generation: fetch only the RAREST trigrams of each set
    // (see rarestOf/MAX_TRIS_PER_SET), not every trigram in it -- a common
    // trigram shared with most of the corpus costs the most to fetch and
    // discriminates the least. Correctness comes from the edit-distance
    // scoring pass below, which runs on every fetched candidate regardless
    // of which trigrams found it; this step only decides which candidates
    // get looked at, cheaply.
    var fetchedSets = trigramSets.map(function (set) { return rarestOf(set, self.df); });
    var allFetch = {};
    fetchedSets.forEach(function (set) { set.forEach(function (tg) { allFetch[tg] = 1; }); });
    var postingKey = function (tg) { return tg + '::' + (section || '*'); };
    var onProgress = opts.onProgress;
    // Same scope contract as searchExact (see its comment): include-
    // prefixes narrow the candidate granthas below and the posting
    // section fan-out here; the single-section opt still wins when set.
    var includePrefixes = opts.includeGranthaPrefixes || [];
    var scope = section || this._sectionsForPrefixes(includePrefixes);
    var fetchTgs = Object.keys(allFetch);
    return allWithProgress(
      fetchTgs.map(function (tg) { return self._loadPosting(tg, scope); }),
      onProgress && function (done, total) { onProgress('postings', done, total); }
    )
      .then(function (postingRowsList) {
        // Read THIS run's resolved rows, not the session cache -- a
        // degraded posting union (a section request dropped mid-fan-out)
        // is deliberately never cached (see _loadPosting), but the rows
        // that DID arrive are still this run's best effort and should
        // still count. The degraded flag rides along to the caller.
        var degradedPostings = false;
        var postingsNow = {};
        fetchTgs.forEach(function (tg, ti) {
          var rows = postingRowsList[ti];
          if (rows && rows.degraded) degradedPostings = true;
          postingsNow[postingKey(tg)] = rows;
        });
        // Rank candidates by how many of a (rarest-trimmed) trigram set's
        // members they share, then stop. Opening a grantha's unit shard is a
        // network round trip, and a common word shares its trigrams with
        // most of the corpus: searching "राम" used to open 444 of them and
        // take some ten seconds on a fast connection, which on a phone reads
        // as no results at all rather than as slow ones. A unit that really
        // contains a set's text shares nearly all of the (few) trigrams
        // fetched for it, so requiring most of them before its grantha is
        // opened is what keeps a long query from dragging in half the
        // library on the strength of one shared fragment — each set (whole
        // query, or one word) is judged against its OWN 60% bar, computed
        // over what was actually FETCHED for that set (not the set's full,
        // unfetched trigram count), independently, so a candidate only has
        // to clear the bar for the query as typed OR for a single word
        // within it.
        //
        // A trigram containing ^ or $ only appears in the index at the true
        // start/end of a UNIT'S WHOLE indexed text, not at each word's own
        // boundary within it -- so a query word sitting in the middle of a
        // verse/line (the overwhelmingly common case) can never match its
        // own ^xy/yz$ trigrams, even on an exact literal hit. Requiring 60%
        // of ALL trigrams including these meant a real match could
        // permanently fall short of the bar (this is exactly how कान्ताय,
        // an exact match in the middle of Sumadhva Vijaya's opening line,
        // never became a candidate at all). Only the interior trigrams are
        // required; boundary ones still count toward `count` as a bonus
        // when they DO match (a genuine signal for a query that really is
        // at a unit's edge).
        var cand = {};            // "gi:ui" -> { count: best total shared trigrams, complete: every non-boundary trigram of some set matched }
        fetchedSets.forEach(function (set) {
          if (!set.length) return;
          var boundary = {}, requiredCount = 0;
          set.forEach(function (tg) {
            if (tg.indexOf('^') !== -1 || tg.indexOf('$') !== -1) boundary[tg] = 1; else requiredCount++;
          });
          var counts = {}, reqCounts = {};
          set.forEach(function (tg) {
            var post = postingsNow[postingKey(tg)]; if (!post) return;
            var isBoundary = !!boundary[tg];
            for (var k = 0; k < post.length; k++) {
              var key = post[k][0] + ':' + post[k][1];
              counts[key] = (counts[key] || 0) + 1;
              if (!isBoundary) reqCounts[key] = (reqCounts[key] || 0) + 1;
            }
          });
          var need = Math.max(1, Math.ceil(Math.max(requiredCount, 1) * 0.6));
          Object.keys(reqCounts).forEach(function (key) {
            if (reqCounts[key] < need) return;
            var complete = requiredCount > 0 && reqCounts[key] === requiredCount;
            var total = counts[key];
            var prev = cand[key];
            if (!prev || (complete && !prev.complete) || (complete === prev.complete && total > prev.count)) {
              cand[key] = { count: total, complete: complete };
            }
          });
        });
        var keys = Object.keys(cand);
        // Complete matches (every trigram that could possibly match, did)
        // rank first, THEN by raw shared count. Sorting by raw count alone
        // favoured a long query's partial match (many shared trigrams
        // simply because the query is long) over a short query's COMPLETE
        // match (fewer trigrams only because the word itself is short) --
        // backwards, and part of why a short exact query could lose its
        // shard slot to a longer, weaker one below.
        keys.sort(function (a, b) {
          if (cand[a].complete !== cand[b].complete) return (cand[b].complete ? 1 : 0) - (cand[a].complete ? 1 : 0);
          return cand[b].count - cand[a].count;
        });
        var giSet = {}, nGi = 0, picked = [], skipped = false;
        // Reported live: कान्ताय's only genuine exact matches in the whole
        // corpus happen to sit under darshana/vedanta/dvaita/DvaitaVedantaIn,
        // which global-search.js's own render() already hides from a
        // non-admin reader post hoc (dgeSearchIsAdminOnlyHit -- a display
        // preference, not real access control, per that comment). Applying
        // that exclusion only AFTER the shard-open budget was already spent
        // meant those granthas' shards got opened anyway, using up slots a
        // genuinely visible match elsewhere in the corpus needed to compete
        // for -- the reader was shown "no exact matches" even though the
        // exact matches that DO exist were simply never given a chance to
        // be found. excludeGranthaPrefixes (passed by a caller that already
        // knows which granthas it won't render, same prefixes
        // dgeSearchIsAdminOnlyHit checks) drops those candidates BEFORE they
        // count against the budget, so it's spent only on granthas the
        // reader could actually see the result of.
        var excludePrefixes = opts.excludeGranthaPrefixes || [];
        var isOutOfScope = function (gik) {
          var slug = self.granthas[+gik] && self.granthas[+gik].slug;
          if (!slug) return false;
          if (includePrefixes.length && !slugInPrefixes(slug, includePrefixes)) return true;
          return excludePrefixes.length ? slugInPrefixes(slug, excludePrefixes) : false;
        };
        // A genuinely complete match always gets its grantha opened, past
        // the normal MAX_SHARDS budget -- up to a much higher ceiling so a
        // pathological query (present in most of the corpus) still can't
        // drag in everything. A common word/epithet can tie dozens of
        // granthas at "every possible trigram present," and admitting only
        // the first MAX_SHARDS of them by arbitrary sort-stability order
        // (not by which is actually right) is exactly how an exact match --
        // कान्ताय opening Sumadhva Vijaya -- went missing while a bunch of
        // equally-complete but less relevant granthas filled the budget
        // first. Partial (need-clearing but not complete) matches still
        // respect the original MAX_SHARDS budget unchanged.
        var MAX_EXACT_SHARDS = MAX_SHARDS * 3;
        for (var i = 0; i < keys.length && picked.length < MAX_UNITS; i++) {
          var gik = keys[i].split(':')[0];
          if (!giSet[gik] && isOutOfScope(gik)) continue;
          var isExact = cand[keys[i]].complete;
          if (!giSet[gik]) {
            if (isExact ? nGi >= MAX_EXACT_SHARDS : nGi >= MAX_SHARDS) { skipped = true; continue; }
            giSet[gik] = 1; nGi++;
          }
          picked.push(keys[i]);
        }
        if (picked.length >= MAX_UNITS) skipped = true;
        // The shard count isn't knowable before the postings phase above
        // resolves -- which granthas even need opening depends on the
        // candidate ranking that just ran -- but it IS fully known right
        // here, before a single shard fetch fires, so the progress readout
        // can jump straight to an honest "0 of 7", not stay silent then
        // jump to "done".
        var degradedShards = false;
        var shardsSettled = allWithProgress(
          Object.keys(giSet).map(function (gi) {
            return self._loadShard(+gi).then(function (v) {
              if (v && v.degraded) degradedShards = true;
              return v;
            });
          }),
          onProgress && function (done, total) { onProgress('shards', done, total); }
        );
        var timedOut = false;
        var deadline = new Promise(function (resolve) {
          setTimeout(function () { timedOut = true; resolve(); }, SHARD_TIMEOUT_MS);
        });
        // Whichever settles first. The losing side isn't cancelled -- a
        // shard fetch that's already in flight keeps running and still
        // warms self._shardCache for whoever asks next -- this race only
        // decides how long THIS query blocks on it.
        return Promise.race([shardsSettled, deadline])
          .then(function () {
            return { cand: cand, keys: picked, skipped: skipped || timedOut,
                     degraded: degradedPostings || degradedShards };
          });
      })
      .then(function (bag) {
        // 2) score each candidate unit with the fold + edit distance
        var hits = [];
        bag.keys.forEach(function (key) {
          var parts = key.split(':'), gi = +parts[0], ui = +parts[1];
          var shard = self._shardCache[gi]; if (!shard) return;
          var row = shard[ui]; if (!row) return;
          var sc = self._score(q, row);
          if (sc.score >= (opts.minScore || 0.18)) {
            var g = self.granthas[gi];
            hits.push({ grantha: g.slug, title: g.title, category: g.category,
              contentType: classifyContentType(g.schema),
              unit: row.u, snippet: row.s, score: sc.score, via: sc.via });
          }
        });
        hits.sort(function (a, b) { return b.score - a.score; });
        var out = hits.slice(0, limit);
        // so the UI can say the corpus was not swept end to end.
        // `partial` also matters at ZERO hits: a long single word made
        // entirely of common trigrams (राजनीतिसमुच्चयम्) can have hundreds
        // of big units "complete" on scattered trigrams, crowding the true
        // containment out of the shard budget before it is ever opened —
        // measured live: 469 complete candidates, the real hit ranked 374.
        // A second word in the query fixes it (each word's own trigram set
        // is judged independently), so the UI should say so instead of a
        // bare "No matches."
        out.partial = !!bag.skipped;
        out.degraded = !!bag.degraded;
        return out;
      });
  };

  Index.prototype._score = function (q, row) {
    var best = 0, via = 'trigram';
    if (q.pkey && row.pk) {
      if (q.pkey === row.pk) return { score: 1.0, via: 'pkey-exact' };
      // A whole word beats a fragment. Without this the score was
      // 0.8 + a bonus for the unit being SHORT, so searching "राम" put
      // विरमति (viramati, which merely contains the same letters once nasals
      // are folded together) above every verse that actually says राम.
      var padded = ' ' + row.pk + ' ';
      if (padded.indexOf(' ' + q.pkey + ' ') !== -1) {
        best = 0.97; via = 'word-exact';
      } else if (padded.indexOf(' ' + q.pkey) !== -1) {
        best = 0.9; via = 'word-start';
      } else if (row.pk.indexOf(q.pkey) !== -1) {
        var s = 0.6 + 0.1 * (q.pkey.length / Math.max(row.pk.length, 1));
        if (s > best) { best = s; via = 'pkey-substr'; }
      }
      if (best < 0.7 && row.pk.indexOf(q.pkey) === -1) {
        var words = row.pk.split(' ');
        for (var i = 0; i < words.length; i++) {
          var d = editDist(q.pkey, words[i], 2);
          if (d <= 2) { var sd = 0.78 - 0.18 * d; if (sd > best) { best = sd; via = 'pkey-ed' + d; } }
        }
      }
    }
    if (best < 0.7 && q.ckey && row.ck && row.ck.indexOf(q.ckey) !== -1) {
      var sc = 0.6 + 0.08 * (q.ckey.length / Math.max(row.ck.length, 1));
      if (sc > best) { best = sc; via = 'ckey-substr'; }
    }
    // Credit a multi-word query for the words it DOES contain even when the
    // whole phrase does not line up — every check above compares the full
    // query string against one span of row.pk, so one wrong or garbled word
    // ("kadhamne" for guṇaikadhāmne) made the other, correct word ("kantaya",
    // an exact match) count for nothing. Scored below a real phrase match
    // (best case 0.8, under word-exact's 0.97) so an exact hit still wins.
    if (best < 0.8 && q.words && q.words.length > 1 && row.pk) {
      var rowWords = row.pk.split(' ');
      // A long unit (a commentary paragraph, not a single verse) has enough
      // words that a short one will coincidentally sit within edit distance
      // 1 of almost anything — that is how an unrelated 300-word ṭīkā tied
      // the real verse for top score during testing. Fuzzy/substring credit
      // is only trustworthy for a short, verse-sized unit; a long one only
      // gets credit for a word it contains VERBATIM.
      var allowFuzzy = rowWords.length <= 25;
      var matchedLen = 0, totalLen = 0;
      for (var wi = 0; wi < q.words.length; wi++) {
        var qw = q.words[wi];
        totalLen += qw.length;
        if (qw.length < 4) continue;   // too short to be a signal on its own
        var hit = false;
        for (var ri = 0; ri < rowWords.length && !hit; ri++) {
          var rw = rowWords[ri];
          if (rw === qw) { hit = true; break; }
          if (!allowFuzzy || rw.length < 4) continue;
          if (rw.indexOf(qw) !== -1 || qw.indexOf(rw) !== -1) hit = true;
          else if (editDist(qw, rw, 1) <= 1) hit = true;
        }
        if (hit) matchedLen += qw.length;
      }
      // Weighted by matched LENGTH, not word count, so one long distinctive
      // word landing counts for more than a short common one would.
      var frac = totalLen ? (matchedLen / totalLen) : 0;
      if (frac >= 0.5) {
        var wscore = 0.35 + 0.45 * frac;
        if (wscore > best) { best = wscore; via = 'word-overlap'; }
      }
    }
    return { score: best, via: via };
  };

  var API = {
    create: function (base) {
      return fetchJSON(base, 'manifest.json').then(function (m) {
        // FETCH_ERR (a failed request) must throw here just like a 404 --
        // it is an object, so a bare truthiness check would have handed
        // the sentinel to new Index() as if it were a real manifest.
        if (!m || m === FETCH_ERR) throw new Error('manifest.json could not be loaded from ' + base);
        return new Index(base, m);
      });
    }
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
  root.DGESearch = API;
})(typeof window !== 'undefined' ? window : this);
