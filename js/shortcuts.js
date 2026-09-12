/* =========================================================================
   DGE short URLs and quick-jump grammar — ONE table, three uses (7 Sep 2026).

     https://tribhuvanachar.github.io/bhumandala/?rv1.1.3      (the landing page forwards a bare token to the reader)
     https://tribhuvanachar.github.io/bhumandala/?rv1.1.3  (the reader resolves it itself)
     Library › Quick jump box:  rv1.1.3                        (config.js's dgeParseQuickSearchQuery delegates here)
     Share / Copy link:         the reader writes the SHORT form back into the address bar and into every
                                shared text, so a link people pass around never carries the folder layout

   A shortcut is <key><numbers separated by dots>, nothing else: rv1.1.3, av20.143.9, smv1.5, bhp10.14.8,
   mbh12.3.7. Fewer numbers name a larger unit and land on its first verse (rv1.1 → sūkta 1.1, rv1 → maṇḍala 1).
   The key is stable; the `path` column is the only thing that changes when the library is reorganised.

   kinds
     vedic   the data's own dotted ids (mandala.sukta.mantra …): numbers → path (first number, when the path
             has a {1}) + jumpVedicId = all numbers joined (a prefix is fine, core.js matches prefixes)
     shloka  plain numbered verses: path from the first number (sarga_{1}), the next number is the verse
     unit    chapter files nested as items[].shlokas (itihāsa, purāṇa): path from the first number, the chapter
             unit id from the second (adhyaya_{2:3}), the verse within it as jumpVedicId "<unit>#<n>"
   Path templates: {1} = first number, {1:2} = zero-padded to 2. `parts` = a list to index by the first number
   (Mahābhārata parvas, Rāmāyaṇa kāṇḍas). `pick(nums)` = a function for anything else (Sāmaveda's two ārcikas).
   No dependencies; safe to load on the landing page and on every reader page.
   ========================================================================= */
(function () {
  'use strict';
  var MBH = ['adi', 'sabha', 'vana', 'virata', 'udyoga', 'bhishma', 'drona', 'karna', 'shalya', 'sauptika', 'stri', 'shanti',
             'anushasana', 'ashvamedhika', 'ashramavasika', 'mausala', 'mahaprasthanika', 'svargarohana'];
  var RM = ['bala', 'ayodhya', 'aranya', 'kishkindha', 'sundara', 'yuddha', 'uttara'];
  var TABLE = [
    { key: 'rv',  label: 'ऋग्वेदः', kind: 'vedic', levels: 3, path: 'vedas/rigveda/shakala_shakha/samhita/mandala_{1:2}', range: [1, 10],
      example: 'rv1.1.3 → maṇḍala 1, sūkta 1, mantra 3' },
    { key: 'av',  label: 'अथर्ववेदः (शौनकशाखा)', kind: 'vedic', levels: 3, path: 'vedas/atharvaveda/shaunaka_shakha/samhita/kanda_{1:2}', range: [1, 20],
      example: 'av20.143.9 → kāṇḍa 20, sūkta 143, mantra 9' },
    { key: 'avp', label: 'अथर्ववेदः (पैप्पलादशाखा)', kind: 'vedic', levels: 3, path: 'vedas/atharvaveda/paippalada_shakha/samhita/kanda_{1:2}', range: [1, 20],
      example: 'avp1.1.1' },
    { key: 'ts',  label: 'तैत्तिरीयसंहिता', kind: 'vedic', levels: 3, path: 'vedas/yajurveda/krishna_yajurveda/taittiriya_shakha/samhita/kanda_{1:2}', range: [1, 7],
      example: 'ts1.8.22 → kāṇḍa 1, prapāṭhaka 8, anuvāka 22' },
    { key: 'vs',  label: 'वाजसनेयिसंहिता (माध्यन्दिन)', kind: 'vedic', levels: 2, path: 'vedas/yajurveda/shukla_yajurveda/vajasaneyi_madhyandina_shakha/samhita',
      example: 'vs1.1 → adhyāya 1, mantra 1' },
    { key: 'sv',  label: 'सामवेदः (कौथुमशाखा)', kind: 'vedic', levels: 1, range: [1, 1875],
      pick: function (n) { return n[0] <= 650 ? 'vedas/samaveda/kauthuma_shakha/samhita/purvarchika' : 'vedas/samaveda/kauthuma_shakha/samhita/uttararchika'; },
      unpick: function (slug) { return /samaveda\/kauthuma_shakha\/samhita\/(purvarchika|uttararchika)$/.test(slug) ? [] : null; },
      example: 'sv1 → mantra 1 (pūrvārcika 1–650, uttarārcika 651–1875)' },
    { key: 'smv', label: 'सुमध्वविजयः', kind: 'shloka', levels: 2, path: 'DvaitaVedanta/Itara/Kavya/sumadhva_vijaya/sarga_{1}', range: [1, 16], example: 'smv1.5 → sarga 1, śloka 5' },
    { key: 'rgv', label: 'राघवेन्द्रविजयः', kind: 'shloka', levels: 2, path: 'DvaitaVedanta/Itara/Kavya/raghavendra_vijaya/sarga_{1}', range: [1, 20], example: 'rgv1.5' },
    { key: 'pns', label: 'प्रह्लादकृतनृसिंहस्तोत्रम्', kind: 'shloka', levels: 1, path: 'DvaitaVedanta/Itara/Stotra/prahlada_kruta_narasimha', example: 'pns5 → śloka 5' },
    { key: 'bhp', label: 'श्रीमद्भागवतम्', kind: 'unit', levels: 3, path: 'purana/maha_purana/bhagavata_purana/skandha_{1:2}', unit: 'adhyaya_{2:2}', range: [1, 12],
      example: 'bhp10.14.8 → skandha 10, adhyāya 14, śloka 8' },
    { key: 'mbh', label: 'महाभारतम्', kind: 'unit', levels: 3, parts: MBH, path: 'itihasa/mahabharata/{part}_parva/mula', unit: 'adhyaya_{2:3}',
      example: 'mbh1.1.1 → ādi parva, adhyāya 1, śloka 1 (parvas 1–18 in order)' },
    { key: 'rm',  label: 'श्रीमद्रामायणम्', kind: 'unit', levels: 3, parts: RM, path: 'itihasa/ramayana/{part}_kanda/mula', unit: 'sarga_{2:3}',
      example: 'rm2.1.1 → ayodhyā kāṇḍa, sarga 1, śloka 1 (kāṇḍas 1–7 in order)' },
    { key: 'hv',  label: 'हरिवंशः', kind: 'unit', levels: 2, path: 'itihasa/harivamsha/mula', unit: 'adhyaya_{1:2}', example: 'hv1.1 → adhyāya 1, śloka 1' }
  ];
  var BY_KEY = {};
  TABLE.forEach(function (e) { BY_KEY[e.key] = e; });
  var KEYS_LONGEST_FIRST = TABLE.map(function (e) { return e.key; }).sort(function (a, b) { return b.length - a.length; });

  function pad(n, w) { var s = String(n); while (s.length < (w || 0)) s = '0' + s; return s; }
  function fill(template, nums, entry) {
    return template.replace(/\{(\d)(?::(\d))?\}/g, function (_, i, w) { return pad(nums[parseInt(i, 10) - 1], w ? parseInt(w, 10) : 0); })
                   .replace('{part}', entry && entry.parts ? (entry.parts[nums[0] - 1] || '') : '');
  }
  function templateToRegex(template) {
    // 'vedas/…/mandala_{1:2}' → /^vedas\/…\/mandala_(\d+)$/ ; '{part}' → a named alternative
    var re = template.replace(/[.*+?^${}()|[\]\\\/]/g, function (c) { return c === '{' || c === '}' ? c : '\\' + c; })
      .replace(/\{(\d)(?::\d)?\}/g, '(\\d+)').replace('{part}', '([a-z]+)');
    return new RegExp('^' + re + '$');
  }

  /** "rv1.1.3" → { key, entry, nums } or null. Case-insensitive; spaces around the numbers are allowed. */
  function split(text) {
    var m = String(text || '').trim().toLowerCase().match(/^([a-z]{1,4})\s*([\d.]+)$/);
    if (!m) return null;
    var key = m[1];
    if (!BY_KEY[key]) return null;
    var parts = m[2].split('.').filter(function (p) { return p !== ''; });
    if (!parts.length || parts.some(function (p) { return !/^\d+$/.test(p); })) return null;
    var nums = parts.map(function (p) { return parseInt(p, 10); });
    if (nums.some(function (n) { return n < 1; })) return null;
    return { key: key, entry: BY_KEY[key], nums: nums };
  }

  /** "rv1.1.3" → { key, label, granthaPath, vedicId | shlokaNumber, example } or null. */
  function parse(text) {
    var s = split(text);
    if (!s) return null;
    var e = s.entry, nums = s.nums;
    if (nums.length > e.levels) return null;
    if (e.range && (nums[0] < e.range[0] || nums[0] > e.range[1])) return null;
    if (e.parts && nums[0] > e.parts.length) return null;
    var hasPathNumber = !!(e.parts || (e.path && /\{1(?::\d)?\}/.test(e.path)) || e.pick);
    var path = e.pick ? e.pick(nums) : fill(e.path, nums, e);
    var out = { key: e.key, label: e.label, granthaPath: path, shortcut: e.key + nums.join('.') };
    if (e.kind === 'vedic') {
      out.vedicId = nums.join('.');
    } else if (e.kind === 'shloka') {
      var verse = hasPathNumber ? nums[1] : nums[0];
      if (verse) out.shlokaNumber = verse; else out.shlokaNumber = 1;
    } else if (e.kind === 'unit') {
      var unitNum = hasPathNumber ? nums[1] : nums[0];
      var verseNum = hasPathNumber ? nums[2] : nums[1];
      if (unitNum == null) { out.shlokaNumber = 1; }
      else {
        var unitTemplate = e.unit.replace(/\{\d(:\d)?\}/, function (t) { return t; });   // template already names its slot
        var unitId = fill(unitTemplate.replace(/\{[12]/, '{1'), [unitNum], e);            // the slot's own number
        out.vedicId = verseNum ? unitId + '#' + verseNum : unitId;
      }
    }
    return out;
  }

  /** The short form for a verse the reader is showing, or null when no key covers that grantha.
      shloka = { vedicId, unitId, unitNo }, id = the shloka's sequential number in the file. */
  function make(slug, shloka, id) {
    slug = String(slug || '').replace(/^\/+|\/+$/g, '');
    for (var i = 0; i < TABLE.length; i++) {
      var e = TABLE[i], nums = null;
      if (e.pick) {
        nums = e.unpick ? e.unpick(slug) : null;
        if (!nums) continue;
      } else {
        var m = slug.match(templateToRegex(e.path));
        if (!m) continue;
        nums = [];
        if (e.parts) { var pi = e.parts.indexOf(m[1]); if (pi < 0) continue; nums.push(pi + 1); }
        else if (m[1] !== undefined) nums.push(parseInt(m[1], 10));
      }
      var hasPathNumber = nums.length > 0;
      if (e.kind === 'vedic') {
        var vid = shloka && shloka.vedicId ? String(shloka.vedicId).trim() : '';
        if (!/^[\d.]+$/.test(vid)) continue;
        var vn = vid.split('.').map(function (p) { return parseInt(p, 10); });
        if (hasPathNumber && vn[0] !== nums[0]) continue;
        return e.key + vn.join('.');
      }
      if (e.kind === 'shloka') {
        if (!id) continue;
        return e.key + (hasPathNumber ? nums[0] + '.' : '') + id;
      }
      if (e.kind === 'unit') {
        var uid = shloka && shloka.unitId ? String(shloka.unitId) : '';
        var um = uid.match(/(\d+)$/);
        if (!um) continue;
        var parts = hasPathNumber ? [nums[0], parseInt(um[1], 10)] : [parseInt(um[1], 10)];
        if (shloka && shloka.unitNo && /^\d+$/.test(String(shloka.unitNo))) parts.push(parseInt(shloka.unitNo, 10));
        return e.key + parts.join('.');
      }
    }
    return null;
  }

  /** The address to share for a verse: the short form when one exists, else the explicit path form.
      base = the reader page's own path (location.pathname). */
  function canonical(base, slug, shloka, id) {
    var short = make(slug, shloka, id);
    if (short) return base + '?' + short;
    var q = '?path=' + (/^[a-z0-9_\/]+$/i.test(slug) ? slug : encodeURIComponent(slug));
    if (id) q += '&jumpShloka=' + id;
    return base + q;
  }

  /** A bare-token query string ("?rv1.1.3", also "?rv=1.1.3" and the legacy "?SMV=1.1") → parse() result or null. */
  function fromSearch(search) {
    var s = String(search || '').replace(/^\?/, '');
    if (!s || s.indexOf('&') !== -1) return null;
    var m = s.match(/^([A-Za-z]{1,4})(?:=|\s*)([\d.]+)$/);
    if (!m) return null;
    return parse(m[1] + m[2]);
  }

  window.DGEShortcuts = { table: TABLE, parse: parse, make: make, canonical: canonical, fromSearch: fromSearch, split: split,
    examples: function () { return TABLE.map(function (e) { return e.example; }); } };
})();
