/* =========================================================================
   samsadhani.js — read-time analysis from Saṃsādhanī (University of Hyderabad).

   Double-tap a word and the popover can ask the Saṃsādhanī Computational
   Linguistics toolkit what it is (morphological analysis) and where it divides
   (sandhi splitter). The servers are the department's own, sent permissive CORS
   headers (Access-Control-Allow-Origin: *), so the browser talks to them directly
   and this site runs no proxy.

   WHAT THE SERVICE DOES, verified 30 Sep 2026 and worth knowing before editing:
     * every call takes 1-4 seconds;
     * a failure comes back as HTTP 200 with a plain-text body ("No Output Found",
       or a segmentation starting with "?" meaning "not split"), never a status
       code and never JSON, so every reply is parsed defensively;
     * the Content-Type is malformed, so the body is read as text and parsed here;
     * outencoding differs per tool: D for the splitter, DEV for the analyser.

   BEING A GOOD GUEST. It is a university's server, not a product. So:
     * one request at a time, at least 600 ms apart;
     * every answer, including "no answer", is cached in the browser for 60 days, so
       a word is asked about once per reader, ever;
     * a request that does not answer in 8 s is given up and remembered as a miss
       for an hour, not retried;
     * after 3 failures in a row the feature switches itself off for the session.

   PRIVACY. The word a reader double-taps is sent to that server. The Credits page
   says so. Switch it off with window.SCL_LIVE = false (config.js: sclLive), or
   point sclBase elsewhere (a self-hosted copy, a mirror).

   Nothing here throws into the page: every function resolves, to [] when it has
   nothing.
   ========================================================================= */
(function () {
  'use strict';

  var DEFAULT_BASE = 'https://sanskrit.uohyd.ac.in/cgi-bin/scl';
  var PREFIX = 'dge_scl1:';
  var TTL = 60 * 24 * 3600 * 1000;
  var MISS_TTL = 3600 * 1000;
  var MAX_ENTRIES = 600;
  var GAP = 600, TIMEOUT = 8000, MAX_FAILS = 3;

  var fails = 0, off = false, chain = Promise.resolve(), lastAt = 0;
  var memo = {};

  function enabled() {
    if (off) return false;
    if (window.SCL_LIVE === false) return false;
    var f = window.FEATURE_FLAGS;
    return !(f && f.sclLive === false);
  }
  function base() {
    return String(window.SCL_BASE || (window.FEATURE_FLAGS && window.FEATURE_FLAGS.sclBase) || DEFAULT_BASE).replace(/\/+$/, '');
  }

  function cacheGet(k) {
    try {
      var raw = localStorage.getItem(PREFIX + k);
      if (!raw) return undefined;
      var e = JSON.parse(raw);
      if (Date.now() > e.t + (e.m ? MISS_TTL : TTL)) { localStorage.removeItem(PREFIX + k); return undefined; }
      return e.v;
    } catch (err) { return undefined; }
  }
  function cachePut(k, v, miss) {
    try {
      localStorage.setItem(PREFIX + k, JSON.stringify({ t: Date.now(), m: miss ? 1 : 0, v: v }));
      var keys = [];
      for (var i = 0; i < localStorage.length; i++) {
        var n = localStorage.key(i);
        if (n && n.indexOf(PREFIX) === 0) keys.push(n);
      }
      if (keys.length > MAX_ENTRIES) {
        keys.map(function (n) { try { return [n, JSON.parse(localStorage.getItem(n)).t]; } catch (e) { return [n, 0]; } })
            .sort(function (a, b) { return a[1] - b[1]; })
            .slice(0, keys.length - MAX_ENTRIES).forEach(function (p) { localStorage.removeItem(p[0]); });
      }
    } catch (err) { /* private window, quota: the answer just is not remembered */ }
  }

  // One request at a time, spaced out. `fn` returns a promise; the chain never rejects.
  function queued(fn) {
    var run = chain.then(function () {
      var wait = Math.max(0, lastAt + GAP - Date.now());
      return new Promise(function (r) { setTimeout(r, wait); });
    }).then(function () { lastAt = Date.now(); return fn(); });
    chain = run.catch(function () {});
    return run;
  }

  function get(path, params) {
    var q = Object.keys(params).map(function (k) { return k + '=' + encodeURIComponent(params[k]); }).join('&');
    var ctl = (typeof AbortController === 'function') ? new AbortController() : null;
    var timer = setTimeout(function () { if (ctl) ctl.abort(); }, TIMEOUT);
    return fetch(base() + path + '?' + q, ctl ? { signal: ctl.signal } : {})
      .then(function (r) { clearTimeout(timer); return r.ok ? r.text() : null; })
      .catch(function () { clearTimeout(timer); return null; });
  }

  function cached(key, fetcher) {
    if (!enabled()) return Promise.resolve([]);
    var hit = cacheGet(key);
    if (hit !== undefined) return Promise.resolve(hit);
    if (memo[key]) return memo[key];
    memo[key] = queued(fetcher).then(function (res) {
      if (res === null) {                       // network or timeout
        if (++fails >= MAX_FAILS) off = true;
        cachePut(key, [], true);
        return [];
      }
      fails = 0;
      cachePut(key, res, res.length === 0);
      return res;
    }).catch(function () { return []; });
    return memo[key];
  }

  // "{लिङ्गम्:पुं}{विभक्तिः:1}{वचनम्:एक}" -> { 'लिङ्गम्': 'पुं', ... }
  function parseAns(s) {
    var o = {}, re = /\{([^:{}]+):([^{}]*)\}/g, m;
    while ((m = re.exec(s || ''))) o[m[1]] = m[2];
    return o;
  }

  var VIBH = { '1': 'प्रथमा', '2': 'द्वितीया', '3': 'तृतीया', '4': 'चतुर्थी', '5': 'पञ्चमी', '6': 'षष्ठी', '7': 'सप्तमी', '8': 'सम्बोधनम्' };

  function describe(rec) {
    var a = parseAns(rec.ANS), bits = [];
    if (rec.APP === 'noun') {
      if (a['लिङ्गम्']) bits.push(a['लिङ्गम्']);
      if (a['विभक्तिः']) bits.push((VIBH[a['विभक्तिः']] || a['विभक्तिः']) + ' विभक्तिः');
      if (a['वचनम्']) bits.push(a['वचनम्'] + 'वचनम्');
    } else {
      ['प्रयोगः', 'लकारः', 'पुरुषः', 'वचनम्', 'गणः'].forEach(function (k) { if (a[k]) bits.push(a[k]); });
    }
    return { kind: rec.APP || '', lemma: rec.RT || rec.rt || '', parse: bits.join(' · ') };
  }

  /* morphological analysis: [{kind, lemma, parse}] (all readings, in service order) */
  window.dgeSclAnalyse = function (word) {
    var w = String(word || '').replace(/[^ऀ-ॿ]/g, '');
    if (!w) return Promise.resolve([]);
    return cached('m:' + w, function () {
      return get('/MT/prog/morph/morph.cgi', { morfword: w, encoding: 'Unicode', outencoding: 'DEV', mode: 'json' })
        .then(function (body) {
          if (body === null) return null;
          try {
            var arr = JSON.parse(body);
            if (!Array.isArray(arr)) return [];
            var seen = {}, out = [];
            arr.map(describe).forEach(function (d) {
              var k = d.lemma + '|' + d.parse;
              if (d.lemma && !seen[k]) { seen[k] = 1; out.push(d); }
            });
            return out;
          } catch (e) { return []; }            // "No Output Found" and friends
        });
    });
  };

  /* sandhi split: ['राम', 'आलयः'] or [] when the service declines ("?" prefix) */
  window.dgeSclSplit = function (word) {
    var w = String(word || '').replace(/[^ऀ-ॿ]/g, '');
    if (!w) return Promise.resolve([]);
    return cached('s:' + w, function () {
      return get('/MT/prog/sandhi_splitter/sandhi_splitter.cgi',
                 { word: w, encoding: 'Unicode', outencoding: 'D', mode: 'word', disp_mode: 'json' })
        .then(function (body) {
          if (body === null) return null;
          try {
            var seg = (JSON.parse(body).segmentation || [])[0] || '';
            if (!seg || seg.charAt(0) === '?') return [];
            var parts = seg.split(/[\s\-]+/).filter(Boolean);
            return parts.length > 1 ? parts : [];
          } catch (e) { return []; }
        });
    });
  };

  /* does the service recognise this as a word at all? (used to vet other engines' splits) */
  window.dgeSclKnows = function (word) {
    return window.dgeSclAnalyse(word).then(function (r) { return r.length > 0; });
  };

  window.dgeSclAvailable = enabled;
})();
