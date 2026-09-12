/*
 * dge-normalize.js — query-time Sanskrit normalizer for DGE global search.
 *
 * This is the JS twin of the Python indexer's normalizer. It MUST produce the
 * same pkey/ckey as build_search_index.py, or the query won't match the index.
 * A Node parity test (test-parity.js) asserts exactly that against real data.
 *
 * Works in the browser (attaches window.DGENorm) and in Node (module.exports).
 * For non-Devanagari input the app should first convert to SLP1 with the
 * Sanscript engine already loaded in index.html:
 *     const slp1 = Sanscript.t(input, sourceScheme, 'slp1');
 * Devanagari input is handled directly here (devaToSlp1), so index & query use
 * the identical Devanagari->SLP1 mapping.
 */
(function (root) {
  'use strict';

  // ---- Devanagari -> SLP1 ----
  var INDEP = {'अ':'a','आ':'A','इ':'i','ई':'I','उ':'u','ऊ':'U','ऋ':'f','ॠ':'F',
    'ऌ':'x','ॡ':'X','ए':'e','ऐ':'E','ओ':'o','औ':'O','ऎ':'e','ऒ':'o','ऍ':'E','ऑ':'O'};
  var MATRA = {'ा':'A','ि':'i','ी':'I','ु':'u','ू':'U','ृ':'f','ॄ':'F','ॢ':'x','ॣ':'X',
    'े':'e','ै':'E','ो':'o','ौ':'O','ॆ':'e','ॊ':'o','ॅ':'E','ॉ':'O'};
  var CONS = {'क':'k','ख':'K','ग':'g','घ':'G','ङ':'N','च':'c','छ':'C','ज':'j','झ':'J',
    'ञ':'Y','ट':'w','ठ':'W','ड':'q','ढ':'Q','ण':'R','त':'t','थ':'T','द':'d','ध':'D',
    'न':'n','प':'p','फ':'P','ब':'b','भ':'B','म':'m','य':'y','र':'r','ल':'l','व':'v',
    'श':'S','ष':'z','स':'s','ह':'h','ळ':'L'};
  var SIGN = {'ं':'M','ः':'H','ँ':'~','ऽ':"'"};
  // Devanagari digits -> ASCII, mirroring translit.py's _DEVA_DIGITS.
  // Confirmed parity bug (Fable review, 30 Aug 2026): the Python indexer
  // has always mapped १->1 etc., so index keys carry ASCII digits, while
  // this file let Devanagari digits pass through untranslated -- a QUERY
  // containing one could never match what the index stored for it.
  var DIGITS = {'०':'0','१':'1','२':'2','३':'3','४':'4','५':'5','६':'6','७':'7','८':'8','९':'9'};
  var VIRAMA = '्';
  var VEDIC = /[॒॑᳐-᳿]/g;

  function cleanDeva(text) {
    if (!text) return '';
    return text.normalize('NFC')
      .replace(/<[^>]+>/g, ' ')
      .replace(/ꣳ/g, 'ं')
      .replace(VEDIC, '')
      .replace(/[​-‍﻿]/g, '')
      .replace(/[।॥\|]+/g, ' ')
      .replace(/\s+/g, ' ').trim();
  }

  function devaToSlp1(s) {
    s = cleanDeva(s);
    var out = [], i = 0, n = s.length;
    while (i < n) {
      var ch = s[i];
      if (CONS[ch] !== undefined) {
        var base = CONS[ch], nxt = i + 1 < n ? s[i + 1] : '';
        if (nxt === VIRAMA) { out.push(base); i += 2; }
        else if (MATRA[nxt] !== undefined) { out.push(base + MATRA[nxt]); i += 2; }
        else { out.push(base + 'a'); i += 1; }
      } else if (INDEP[ch] !== undefined) { out.push(INDEP[ch]); i++; }
      else if (MATRA[ch] !== undefined) { out.push(MATRA[ch]); i++; }
      else if (SIGN[ch] !== undefined) { out.push(SIGN[ch]); i++; }
      else if (DIGITS[ch] !== undefined) { out.push(DIGITS[ch]); i++; }
      else { out.push(ch); i++; }
    }
    return out.join('');
  }

  // ---- the fold (must mirror normalize.py) ----
  var NASALS = {'M':1,'N':1,'Y':1,'R':1,'n':1,'m':1,'~':1};
  var SIB = {'S':1,'z':1,'s':1};
  var LONG = {'A':'a','I':'i','U':'u','F':'f','X':'x'};
  var VOCALIC = {'f':'r','x':'l'};
  var RETRO = {'w':'t','W':'T','q':'d','Q':'D','R':'n','z':'s'};
  var DEASP = {'K':'k','G':'g','C':'c','J':'j','W':'w','Q':'q','T':'t','D':'d','P':'p','B':'b'};
  var DEVOICE = {'g':'k','j':'c','q':'w','d':'t','b':'p'};

  function collapse(s) { return s.replace(/(.)\1+/g, '$1'); }
  function mapChars(s, m) {
    var r = '';
    for (var i = 0; i < s.length; i++) r += (m[s[i]] !== undefined ? m[s[i]] : s[i]);
    return r;
  }

  function phoneticKey(slp1) {
    var s = slp1.replace(/'/g, '');
    s = mapChars(s, LONG);
    s = mapChars(s, VOCALIC);
    // nasal + sibilant folds
    var t = '';
    for (var i = 0; i < s.length; i++) {
      var c = s[i];
      if (NASALS[c]) t += 'n'; else if (SIB[c]) t += 's'; else t += c;
    }
    t = t.replace(/H/g, '');
    t = collapse(t);
    return t.replace(/[ \t]+/g, ' ').trim();
  }

  function coarseKey(slp1) {
    var s = phoneticKey(slp1);
    s = mapChars(s, RETRO);
    s = mapChars(s, DEASP);
    s = mapChars(s, DEVOICE);
    return collapse(s);
  }

  function trigrams(s, nn) {
    nn = nn || 3;
    s = s.replace(/ /g, '');
    if (!s) return [];
    var padded = '^' + s + '$', out = {};
    if (padded.length < nn) return [padded];
    for (var i = 0; i <= padded.length - nn; i++) out[padded.substr(i, nn)] = 1;
    return Object.keys(out);
  }

  // ---- query helper: any input -> {slp1, pkey, ckey, trigrams} ----
  // sourceScheme: 'devanagari' handled here; others expect caller to pass SLP1
  // (via Sanscript) or already-SLP1 text.
  function normalizeQuery(input, opts) {
    opts = opts || {};
    var slp1;
    if (opts.scheme === 'devanagari' || /[ऀ-ॿ]/.test(input)) {
      slp1 = devaToSlp1(input);
    } else {
      slp1 = opts.slp1 || input; // caller converts via Sanscript for other schemes
    }
    var pk = phoneticKey(slp1);
    return { slp1: slp1, pkey: pk, ckey: coarseKey(slp1), trigrams: trigrams(pk),
      words: pk.split(' ').filter(Boolean) };
  }

  var API = { devaToSlp1: devaToSlp1, cleanDeva: cleanDeva,
    phoneticKey: phoneticKey, coarseKey: coarseKey, trigrams: trigrams,
    normalizeQuery: normalizeQuery };

  if (typeof module !== 'undefined' && module.exports) module.exports = API;
  root.DGENorm = API;
})(typeof window !== 'undefined' ? window : this);
