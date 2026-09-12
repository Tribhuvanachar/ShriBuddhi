// js/kosha.js — DGE Kosha (multilingual dictionary) lookup.
// ADDITIVE + self-injecting. Adds a floating "कोश" button, an overlay search
// UI, fuzzy SLP1 headword lookup, per-dictionary result cards, per-language
// grouping, and a cross-language translate pivot (BYOK Gemini, reusing the
// app's existing 'gemini_api_key'/'gemini_model' localStorage keys).
// Loads its data from data/kosha/** produced by the importer. Touches no
// existing file or global beyond reading window.Sanscript.
(function () {
  'use strict';
  window.DGE_VERSIONS = window.DGE_VERSIONS || {};
  window.DGE_VERSIONS['kosha.js'] = 'v2.1 (3 Sep 2026: glossSearch — exact folded-token lookup in the _gloss inverted index, for kosha2\'s search-inside-meanings mode; licence badges removed from the legacy overlay cards, licensing lives only in admin/kosha.html) · v2.0 (आशितृ report, 3 Sep 2026: a failed index-shard fetch is retried once and then reported — empty-with-failures rejects so the UI says the index was unreachable instead of the false "No headword found"; partial results carry a degraded list. On top of v1.9) · v1.9 (the अब्ज/Śabdārthakaustubha report, 1 Sep 2026: pinned-but-hidden dictionaries now show a Show strip + hidden state/toggle in the pin panel instead of silently vanishing; the toolbar count says how many are hidden; failed shard fetches are no longer cached for the session (404s still are); %-named shard files are URI-encoded so bhutasankhya-kp-shukla\'s Devanagari-digit buckets fetch instead of 400ing; SAK joins the always-link sūtra list for its hyphenated निष्पत्तिः citations. On top of v1.8)';

  // Citation-form normalizer: strip a trailing visarga (H) / anusvara (M) from
  // an SLP1 headword so dictionaries that cite the nominative (रामः = rAmaH) or
  // accusative (रामं = rAmaM) group with the bare stem (राम = rAma). Vowel
  // length is preserved, so रम (rama) stays distinct from राम (rAma). This is
  // why Śabdakalpadruma/Vācaspatyam (which list रामः, not राम) now appear under
  // a "राम" search instead of looking absent.
  function gkey(s) { s = s || ''; var t = s.replace(/[HM]+$/, ''); return t || s; }

  // Data can live in-repo (data/kosha) or in a separate repo served over a CDN.
  // Set window.KOSHA_DATA_BASE (e.g. a jsDelivr /gh/…/data/koshas URL) to point
  // the app at the full external corpus once it outgrows the Pages repo.
  var BASE = (window.KOSHA_DATA_BASE || 'data/kosha').replace(/\/+$/, '');
  var V = '?v=1.6';   // bump on every corpus rebuild — jsDelivr caches ~12h
  var PREF_LANG = (localStorage.getItem('app_kosha_pref_lang') || 'kn'); // user's language (Kannada)
  var LANG_NAME = { sa: 'संस्कृतम्', kn: 'ಕನ್ನಡ', en: 'English', hi: 'हिन्दी',
                    bn: 'বাংলা', te: 'తెలుగు', ta: 'தமிழ்', fr: 'Français', de: 'Deutsch' };
  // How many "browse" shards a short query may pull. Exact lookups never go
  // through this cap — see the ancestor/descendant split in search().
  var BROWSE_SHARDS = 10;
  var cache = {}, manifest = null;

  // ---- admin-controlled visibility (respected at query time) ----------------
  // The Kosha admin dashboard (admin/kosha.html) writes a list of dictionary
  // slugs to hide from search WITHOUT deleting their data. We read it fresh on
  // every query so a change in the admin tab takes effect on the next search.
  function hiddenDicts() {
    try { var a = JSON.parse(localStorage.getItem('kosha_hidden_dicts') || '[]'); return Array.isArray(a) ? a : []; }
    catch (e) { return []; }
  }

  // ---- reader-controlled preferences ---------------------------------------
  // Separate from the admin's kosha_hidden_dicts above, deliberately: the admin
  // flag takes a dictionary out of search for everyone on this browser, whereas
  // these are one reader's own reading preferences and must not be clobbered by
  // an admin export. Order puts named dictionaries first (so a Kannada reader
  // can pin शब्दार्थकौस्तुभः, शब्दकल्पद्रुमः, वाचस्पत्यम् to the top); everything
  // else keeps its manifest order behind them.
  function lsList(key) {
    try { var a = JSON.parse(localStorage.getItem(key) || '[]'); return Array.isArray(a) ? a : []; }
    catch (e) { return []; }
  }
  // The project lead's explicit pick for a reader who has never touched the
  // ⚙ panel: these four pinned first rather than whatever order the
  // manifest happens to list dictionaries in — Shabdarthakaustubha and
  // Shabdakalpadruma/Vacaspatyam are exactly the three the comment above
  // already named as the intended default, plus Monier-Williams (Cologne,
  // the sanskrit→english direction — not mw-english-sanskrit, which is the
  // reverse). A reader's own saved order, once they set one, wins outright.
  var DEFAULT_KOSHA_ORDER = ['shabdArtha_kaustubha', 'shabdakalpadruma', 'vachaspatyam', 'mw-cologne'];
  function userOrder()   { var a = lsList('kosha_user_order'); return a.length ? a : DEFAULT_KOSHA_ORDER; }
  function userHidden()  { return lsList('kosha_user_hidden'); }
  function setUserOrder(a)  { localStorage.setItem('kosha_user_order', JSON.stringify(a)); }
  function setUserHidden(a) { localStorage.setItem('kosha_user_hidden', JSON.stringify(a)); }
  function toggleUserHidden(slug) {
    var h = userHidden(), i = h.indexOf(slug);
    if (i < 0) h.push(slug); else h.splice(i, 1);
    setUserHidden(h); return i < 0;
  }
  // Sort a per-dictionary result list by the reader's pinned order, keeping the
  // manifest order among the unpinned. Stable, so equal ranks never shuffle.
  function applyUserOrder(perDict) {
    var ord = userOrder();
    if (!ord.length) return perDict;
    var rank = {}; ord.forEach(function (s, i) { rank[s] = i; });
    return perDict.map(function (d, i) { return { d: d, i: i }; })
      .sort(function (a, b) {
        var ra = rank[a.d.slug], rb = rank[b.d.slug];
        if (ra == null && rb == null) return a.i - b.i;
        if (ra == null) return 1;
        if (rb == null) return -1;
        return ra - rb || a.i - b.i;
      }).map(function (x) { return x.d; });
  }

  // ---- Gemini quick actions -------------------------------------------------
  // Prefilled prompts so the reader never has to type one. {word}/{gloss}/{dict}
  // /{lang} are substituted at click time; the reader's own list (edited in the
  // ⚙ panel) overrides these and is stored per-browser.
  var DEFAULT_ACTIONS = [
    { id: 'simple',   label: 'Explain simply',   prompt: 'Explain the Sanskrit word "{word}" in simple {lang}, in 3-4 sentences, for a reader who is not a Sanskrit scholar. Base it only on this dictionary gloss and say so if the gloss is unclear:\n\n{gloss}' },
    { id: 'etymology',label: 'Etymology',        prompt: 'Give the etymology and derivation (व्युत्पत्ति / निष्पत्ति) of the Sanskrit word "{word}" — root, prefixes, suffixes, and how the sense follows from them. Answer in {lang}. Reference gloss from {dict}:\n\n{gloss}' },
    { id: 'usage',    label: 'Usage in texts',   prompt: 'Where does the Sanskrit word "{word}" occur in the Vedas, Itihasas and Puranas, and in what sense? Give specific citations where you are confident, and say plainly when you are not. Answer in {lang}.' },
    { id: 'related',  label: 'Related words',    prompt: 'List synonyms (पर्यायाः), near-synonyms and commonly confused words for the Sanskrit word "{word}", with a one-line distinction for each. Answer in {lang}. Reference gloss:\n\n{gloss}' },
    { id: 'puranic',  label: 'Puranic identity', prompt: 'If "{word}" names a person, deity, sage, place, river or dynasty in the Puranas or Itihasas, identify it: who or what, in which text, and the key episodes. If it is not such a name, say so in one line. Answer in {lang}.' }
  ];
  function quickActions() {
    var custom = lsList('kosha_quick_actions');
    return custom.length ? custom : DEFAULT_ACTIONS;
  }

  // ---- BYOK Gemini credentials (shared with the rest of the app) ------------
  // The key/model are set in the main app (⚙️ Settings → Gemini) as
  // user_gemini_key / user_gemini_model, or on the Ashtadhyayi page as
  // dge.ash.gkey / dge.ash.gmodel (JSON-encoded). Older builds used the bare
  // gemini_api_key / gemini_model names. We accept all three so the pivot works
  // no matter where the user saved their key. (Bug: the old code read ONLY the
  // bare names, which nothing in the app ever writes, so it always failed.)
  function lsRaw(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function lsJSON(k) { try { var v = localStorage.getItem(k); return v == null ? null : JSON.parse(v); } catch (e) { return null; } }
  function geminiKey() {
    return (lsRaw('user_gemini_key') || lsJSON('dge.ash.gkey') || lsRaw('gemini_api_key') || '').toString().trim();
  }
  function geminiModel() {
    return (lsRaw('user_gemini_model') || (window.appConfig && window.appConfig.geminiModel) ||
            lsJSON('dge.ash.gmodel') || lsRaw('gemini_model') || '').toString().trim();
  }

  function j(path) {
    if (cache[path]) return cache[path];
    var p = fetch(path + V).then(function (r) {
      if (r.ok) return r.json();
      // 404 = the shard genuinely doesn't exist, a cacheable answer. Any
      // OTHER failure (a jsDelivr hiccup, a proxy 4xx/5xx) must not be
      // cached, or one transient error makes a whole dictionary silently
      // vanish for the rest of the session -- same FETCH_ERR lesson
      // dge-search.js already learned (31 Aug 2026).
      if (r.status !== 404) delete cache[path];
      return null;
    }).catch(function () { delete cache[path]; return null; });
    cache[path] = p;
    return p;
  }
  // The importer names shard FILES with this same %XX scheme, so a
  // non-ASCII bucket ('१' in bhutasankhya-kp-shukla) is a file literally
  // called "%967.json" in the repo. In a URL that raw % is an escape
  // sequence -- jsDelivr answers 400 for ".../%967.json" -- so the
  // filename must be URI-encoded once more ("%25967.json", which serves).
  // Found live, 1 Sep 2026: this one dictionary was the missing 36th कोश
  // on every अब्ज-style lookup. ASCII bucket names pass through unchanged.
  function safeBucket(b) { return encodeURIComponent(b.replace(/[^0-9A-Za-z_]/g, function (c) {
    return '%' + c.charCodeAt(0).toString(16).padStart(2, '0'); }) || '_'); }

  // ---- SLP1 + fold (mirrors the importer / the app's search spine) ----------
  function fold(s) {
    s = s.replace(/'/g, '');
    s = s.replace(/A/g, 'a').replace(/I/g, 'i').replace(/U/g, 'u').replace(/F/g, 'f').replace(/X/g, 'x');
    s = s.replace(/S/g, 's').replace(/z/g, 's');
    s = s.replace(/M/g, 'n').replace(/~/g, 'n');
    return s.replace(/(.)\1+/g, '$1');
  }
  // Return the SLP1 candidate spellings for a raw query. For Latin-script
  // input we try IAST/HK/ITRANS/SLP1 AND a lower-cased pass, because a casual
  // user typing "Madh"/"Rama" title-cased does NOT mean the SLP1/HK special
  // meanings that capitals carry (capital M = anusvara ṃ, capital H = visarga,
  // etc.). We then DROP any candidate that begins with anusvara ('M') or
  // visarga ('H') in SLP1 — no Sanskrit word can start with either, so such a
  // candidate is always a mis-parse. That was the "Madh → न-words" bug: "Madh"
  // was read as ṃ+a+dh → folded to n-initial → searched the wrong shard.
  function toSLP1list(q) {
    q = (q || '').trim(); if (!q) return [];
    var S = window.Sanscript, out = [];
    if (!S) {
      // Sanscript is fetched from a CDN, and when it does not arrive -- a
      // blocked network, a bad connection, an offline phone -- Devanagari
      // input used to fall through as itself, match no shard, and answer
      // "No headwords found" for every word in the dictionary. The app's own
      // dge-normalize.js carries a Devanagari table needing nothing external,
      // so use it rather than fail. Other scripts still need Sanscript.
      var N = window.DGENorm;
      if (/[ऀ-ॿ]/.test(q) && N && N.devaToSlp1) {
        var slp = N.devaToSlp1(q);
        return slp ? [slp] : [q];
      }
      return [q];
    }
    try {
      if (/[ऀ-ॿ]/.test(q)) out.push(S.t(q, 'devanagari', 'slp1'));
      else if (/[ಀ-೿]/.test(q)) out.push(S.t(q, 'kannada', 'slp1'));
      else {
        var ql = q.toLowerCase();
        var variants = (ql === q) ? [q] : [q, ql];
        variants.forEach(function (qq) {
          ['iast', 'hk', 'itrans', 'slp1'].forEach(function (sc) {
            try { out.push(S.t(qq, sc, 'slp1')); } catch (e) {} });
        });
      }
    } catch (e) { out.push(q); }
    var seen = {}, res = [];
    out.forEach(function (x) {
      if (x && !seen[x] && !/^[MH]/.test(x)) { seen[x] = 1; res.push(x); }
    });
    return res;
  }

  // ---- search ---------------------------------------------------------------
  // Returns { list, exact, q }:
  //   list  — ranked result groups (each group = one headword across dicts)
  //   exact — true if at least one result's exact SLP1 spelling equals what the
  //           user typed (used to decide whether to show a "nearest match" note)
  function search(query) {
    return (manifest ? Promise.resolve(manifest) : j(BASE + '/_index/manifest.json')
        .then(function (m) { manifest = m; return m; }))
      .then(function (m) {
        if (!m) return { list: [], exact: false, q: query };
        var raw = toSLP1list(query);            // exact SLP1 spellings the user meant
        var rawSet = {}; raw.forEach(function (x) { rawSet[x] = 1; });
        var foldSet = {}, folds = [];
        raw.map(fold).forEach(function (f) { if (f && !foldSet[f]) { foldSet[f] = 1; folds.push(f); } });
        if (!folds.length) return { list: [], exact: false, q: query };
        var hidden = {}; hiddenDicts().forEach(function (s) { hidden[s] = 1; });
        // Buckets are variable-width now: the importer splits any prefix that
        // grows too large a character deeper, so the manifest holds a mix of
        // 1- to 5-character names ("sa" alone had been a 16.8MB shard).
        // Two kinds of match, and the difference matters:
        //   ancestors   — the bucket is a prefix of the query. At most one per
        //                 depth, and the exact headword can only live here, so
        //                 these are ALWAYS fetched.
        //   descendants — the query is a prefix of the bucket, i.e. browsing.
        //                 A one-character query matches 444 of them (59MB), so
        //                 these are capped; the exact lookup above is what has
        //                 to stay correct, not the breadth of a browse.
        var anc = {}, desc = {};
        folds.forEach(function (qf) {
          m.buckets.forEach(function (b) {
            if (qf.indexOf(b) === 0) anc[b] = 1;
            else if (b.indexOf(qf) === 0) desc[b] = 1;
          });
        });
        var descList = Object.keys(desc).sort();
        var truncated = descList.length > BROWSE_SHARDS;
        var buckets = {};
        Object.keys(anc).forEach(function (b) { buckets[b] = 1; });
        descList.slice(0, BROWSE_SHARDS).forEach(function (b) { buckets[b] = 1; });
        var need = Object.keys(buckets);
        if (!need.length) return { list: [], exact: false, q: query };
        return Promise.all(need.map(function (b) { return j(BASE + '/_index/' + safeBucket(b) + '.json'); }))
          .then(function (shards) {
            // Every needed bucket comes from the manifest, so a null here is
            // a FAILED FETCH, not an empty shard. Retry the misses once (j()
            // does not cache failures), because the worst outcome is silent:
            // the app used to answer "No headword found" for every word in a
            // bucket whose one file the CDN edge happened to be failing —
            // the आशितृ report, 3 Sep 2026.
            var missing = need.filter(function (b, i) { return !shards[i]; });
            if (!missing.length) return shards;
            return Promise.all(need.map(function (b, i) {
              return shards[i] || j(BASE + '/_index/' + safeBucket(b) + '.json');
            }));
          })
          .then(function (shards) {
            var failed = need.filter(function (b, i) { return !shards[i]; });
            var byFold = {};
            shards.forEach(function (sh) {
              if (!sh) return;
              Object.keys(sh).forEach(function (fk) {
                var hit = folds.some(function (qf) { return fk === qf || fk.indexOf(qf) === 0; });
                if (hit) (byFold[fk] = byFold[fk] || []).push.apply(byFold[fk], sh[fk]);
              });
            });
            // Group by citation-normalized key (gkey) so रामः/रामं fold in with
            // राम. Skip records from admin-hidden dictionaries. Each group keeps
            // its member index-records (with their own fold + headword) so the
            // detail view can fetch every form.
            var groups = {};
            Object.keys(byFold).sort().forEach(function (fk) {
              byFold[fk].forEach(function (rec) {
                if (hidden[rec.d]) return;
                var gk = gkey(rec.s);
                var g = groups[gk] || (groups[gk] = { gkey: gk, members: [], dictSet: {},
                                                       hwCounts: {}, slps: {}, langs: {} });
                rec.fold = fk;
                g.members.push(rec);
                g.dictSet[rec.d] = 1;
                g.hwCounts[rec.h] = (g.hwCounts[rec.h] || 0) + 1;
                g.slps[rec.s] = 1;
                (rec.l || []).forEach(function (l) { g.langs[l] = 1; });
              });
            });
            var arr = Object.keys(groups).map(function (k) {
              var g = groups[k];
              // Display headword: prefer the bare-stem form (slp1 === gkey), and
              // within that prefer a Devanagari spelling — a couple of
              // dictionaries (mw-english-sanskrit, spokensanskrit) key on ASCII,
              // and whichever happened to be built first was labelling the whole
              // group "agastya" instead of अगस्त्य. Falls back to the most-cited
              // spelling, then the shortest.
              var base = g.members.filter(function (m) { return m.s === g.gkey; });
              var deva = base.filter(function (m) { return /[ऀ-ॿ]/.test(m.h); });
              g.hw = (deva[0] || base[0] || {}).h
                   || Object.keys(g.hwCounts).sort(function (a, b) {
                       return g.hwCounts[b] - g.hwCounts[a] || a.length - b.length; })[0];
              g.slp1 = g.gkey;
              g.dicts = g.members;                       // for the "N कोश" count
              g.dictCount = Object.keys(g.dictSet).length;
              g.exactSLP1 = Object.keys(g.slps).some(function (s) { return rawSet[s]; });
              // A group reached only through synonyms ranks below one whose
              // headword matched, so searching a stem still leads with the stem.
              g.synOnly = g.members.every(function (mm) { return !!mm.w; });
              g.foldExact = g.members.some(function (m) { return foldSet[m.fold]; });
              return g;
            });
            // Ranking: exact-SLP1 (राम beats रम when you typed राम) → exact-fold
            // → shorter headword → alphabetical.
            arr.sort(function (a, b) {
              var sa = a.exactSLP1 ? 0 : 1, sb = b.exactSLP1 ? 0 : 1;
              if (sa !== sb) return sa - sb;
              var ea = a.foldExact ? 0 : 1, eb = b.foldExact ? 0 : 1;
              if (ea !== eb) return ea - eb;
              var ya = a.synOnly ? 1 : 0, yb = b.synOnly ? 1 : 0;
              if (ya !== yb) return ya - yb;
              return a.hw.length - b.hw.length || a.hw.localeCompare(b.hw);
            });
            // Honesty about failed shards: with no results at all this is an
            // infrastructure failure, not "no such word" — reject so the UI
            // shows its could-not-reach message. With partial results, let
            // the caller add a degraded note.
            if (failed.length && !arr.length) {
              throw new Error('index shard unreachable (' + failed.join(', ') + ')');
            }
            return { list: arr.slice(0, 60), exact: arr.some(function (g) { return g.exactSLP1; }),
                     q: query, truncated: truncated,
                     degraded: failed.length ? failed : null };
          });
      });
  }

  // ---- full entry (tier-2) --------------------------------------------------
  // A result group may span several headword-forms (राम, रामः, रामं) across
  // several dictionaries. Fetch each distinct (dict, fold, headword) member and
  // merge the items per dictionary.
  function loadEntry(group) {
    var dicts = manifest.dictionaries;
    var eLen = manifest.entry_shard_len || 3;
    var hidden = {}; hiddenDicts().forEach(function (s) { hidden[s] = 1; });
    var seen = {}, tasks = [];
    (group.members || []).forEach(function (m) {
      if (hidden[m.d] || !dicts[m.d]) return;
      // A synonym record displays the synonym but carries the headword's fold
      // (m.f) and text (m.w); the entry itself is only ever filed under those.
      m.efold = m.f || m.fold;
      m.ehw = m.w || m.h;
      var key = m.d + '|' + m.efold + '|' + m.ehw; if (seen[key]) return; seen[key] = 1;
      tasks.push(m);
    });
    return Promise.all(tasks.map(function (m) {
      // Entry shards are variable-width too: a bucket whose serialised size ran
      // over the cap was split a character deeper (pund-v1's "anu" was 14.87MB,
      // fetched in full every time a reader opened an entry it held). The
      // manifest lists only the prefixes that were split, so walk down from the
      // base length until the prefix is no longer one of them.
      var cat = dicts[m.d].category, bucket = m.efold.slice(0, eLen);
      var deep = dicts[m.d].deep;
      if (deep && deep.length) {
        while (deep.indexOf(bucket) >= 0 && bucket.length < m.efold.length) {
          bucket = m.efold.slice(0, bucket.length + 1);
        }
      }
      return j(BASE + '/' + cat + '/' + m.d + '/e/' + safeBucket(bucket) + '.json')
        .then(function (sh) {
          if (!sh || !sh[m.efold]) return null;
          var items = sh[m.efold].filter(function (it) { return it.headword === m.ehw; });
          return items.length ? { slug: m.d, items: items } : null;
        });
    })).then(function (a) {
      var bySlug = {}, order = [];
      a.filter(Boolean).forEach(function (r) {
        if (!bySlug[r.slug]) { bySlug[r.slug] = { slug: r.slug, meta: dicts[r.slug], items: [] }; order.push(r.slug); }
        bySlug[r.slug].items.push.apply(bySlug[r.slug].items, r.items);
      });
      return order.map(function (s) { return bySlug[s]; });
    });
  }

  // Quick, data-only lookup for embedding a few dictionary results directly
  // inside another surface (the Shabda word-tool modal, ai.js) without
  // opening the full कोश overlay -- same ranking/filtering/hiding the
  // overlay itself uses (search + loadEntry + applyUserOrder + the admin's
  // hiddenDicts), just returned as data instead of built into DOM. Resolves
  // to null when nothing matches at all.
  window.dgeKoshaQuick = function (word) {
    return search(word).then(function (r) {
      if (!r.list.length) return null;
      var g = r.list[0];
      return loadEntry(g).then(function (perDict) {
        var hidden = {}; hiddenDicts().forEach(function (s) { hidden[s] = 1; });
        var visible = perDict.filter(function (d) { return !hidden[d.slug]; });
        return { hw: g.hw, dictCount: g.dictCount, perDict: applyUserOrder(visible) };
      });
    });
  };

  // ---- BYOK Gemini translate pivot -----------------------------------------
  // Delegates to the shared window.DGEGemini client (js/gemini.js) for human
  // error messages (quota/permission/etc.) and a one-step lighter-model
  // fallback -- same reasoning as Ashtadhyayi's AI tutor.
  function translate(text, fromLang, toLang) {
    var key = geminiKey();
    if (!key) return Promise.reject(new Error(
      'No Gemini API key found. Add one in the main app under ⚙️ Settings → Gemini (or on the अष्टाध्यायी page), then reopen कोश.'));
    var model = geminiModel();
    var prompt = 'Translate this ' + (LANG_NAME[fromLang] || fromLang) + ' dictionary gloss of a Sanskrit word into ' +
      (LANG_NAME[toLang] || toLang) + '. Output only the translation, no notes:\n\n' + text;
    return window.DGEGemini.generate({ prompt: prompt, apiKey: key, model: model || undefined })
      .then(function (r) {
        if (!r.ok) throw new Error(r.error.title + ' — ' + r.error.message + ' ' + r.error.action);
        if (!r.text) throw new Error('No translation returned.');
        return (r.fellBack ? '[' + r.notice + ']\n' : '') + r.text.trim();
      });
  }

  // Run a quick action: the context is assembled here, so the reader clicks a
  // button and never types a prompt. Same BYOK key and error handling as the
  // translate pivot above.
  function runAction(action, ctx) {
    var key = geminiKey();
    if (!key) return Promise.reject(new Error(
      'No Gemini API key found. Add one in the main app under ⚙️ Settings → Gemini (or on the अष्टाध्यायी page), then reopen कोश.'));
    var prompt = String(action.prompt || '')
      .replace(/\{word\}/g, ctx.word || '')
      .replace(/\{gloss\}/g, ctx.gloss || '')
      .replace(/\{dict\}/g, ctx.dict || '')
      .replace(/\{lang\}/g, LANG_NAME[PREF_LANG] || PREF_LANG);
    return window.DGEGemini.generate({ prompt: prompt, apiKey: key, model: geminiModel() || undefined })
      .then(function (r) {
        if (!r.ok) throw new Error(r.error.title + ' — ' + r.error.message + ' ' + r.error.action);
        if (!r.text) throw new Error('No answer returned.');
        return (r.fellBack ? '[' + r.notice + ']\n' : '') + r.text.trim();
      });
  }

  // ---- rendering ------------------------------------------------------------
  function el(tag, cls, html) { var e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; }
  // Escapes quotes as well as angle brackets, because the output is
  // interpolated into attributes (title="…") as well as into text. Without the
  // quotes a licence note containing one would close the attribute early and
  // whatever followed would be parsed as markup — CodeQL caught exactly that on
  // the licence tooltip.
  function esc(s) {
    return (s == null ? '' : String(s)).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function tl(s) { // transliterate Devanagari to the app's active script, if available
    try { return (window.applyTransliteration && window.activeScript && window.activeScript !== 'devanagari')
      ? window.applyTransliteration(s, window.activeScript) : s; } catch (e) { return s; }
  }
  // Wraps occurrences of the searched headword inside a gloss's own text in
  // <mark> — the searched word appearing again inside its definition (a
  // self-reference, or the word used in an example) was otherwise
  // indistinguishable from the surrounding prose. hw must already be in the
  // same script as escapedText (i.e. already run through tl()) or nothing
  // will match.
  function highlightHw(escapedText, hw) {
    hw = (hw || '').trim();
    if (!hw) return escapedText;
    var pattern = esc(hw).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    return escapedText.replace(new RegExp('(' + pattern + ')', 'gi'), '<mark class="kosha-hl">$1</mark>');
  }

  function renderResults(result, resBox, detail) {
    var list = result.list || [];
    resBox.innerHTML = '';
    if (!list.length) { resBox.appendChild(el('div', 'kosha-empty', 'No headwords found.')); return; }
    // If nothing matches the exact spelling typed, say so rather than letting a
    // near-neighbour (e.g. रम for राम) look like the answer.
    if (result.truncated) {
      resBox.appendChild(el('div', 'kosha-nearest',
        'Showing the first part of “' + esc(tl(result.q)) + '” — type another letter or two to see the rest.'));
    }
    if (!result.exact && result.q) {
      resBox.appendChild(el('div', 'kosha-nearest',
        'No exact headword for “' + esc(tl(result.q)) + '”. Showing the nearest matches:'));
    }
    list.forEach(function (g) {
      var row = el('div', 'kosha-hit');
      var chips = Object.keys(g.langs).map(function (l) {
        return '<span class="kosha-chip">' + (LANG_NAME[l] || l) + '</span>'; }).join('');
      row.innerHTML = '<span class="kosha-hw">' + esc(tl(g.hw)) + '</span>' +
        '<span class="kosha-count">' + (g.dictCount || g.dicts.length) + ' कोश</span>' + chips;
      row.onclick = function () { openEntry(g, detail); };
      resBox.appendChild(row);
    });
  }

  // A dictionary card. Collapsed to a few lines by default — several of these
  // dictionaries carry a full page of prose per headword, and a stack of those
  // buries the short glosses the reader usually wants first.
  function renderCard(d, g, onHide) {
    var card = el('div', 'kosha-card');
    card.dataset.slug = d.slug;

    var head = el('div', 'kosha-src');
    // Licensing lives ONLY in admin/kosha.html (the Kosha Manager) — the
    // lead's 3 Sep 2026 call: no licence text on any reading surface, admin
    // or not.
    head.innerHTML = '<span class="kosha-src-name">' + esc(tl(d.meta.name)) + '</span>';
    var hide = el('button', 'kosha-hidebtn', '🚫');
    hide.title = 'Hide ' + (d.meta.name || d.slug) + ' from results';
    hide.onclick = function (ev) { ev.stopPropagation(); toggleUserHidden(d.slug); onHide(); };
    head.appendChild(hide);
    card.appendChild(head);

    var body = el('div', 'kosha-body-wrap');
    d.items.forEach(function (it) {
      if (it.headword && it.headword !== g.hw) body.appendChild(el('div', 'kosha-altform', esc(tl(it.headword))));
      it.senses.forEach(function (s) {
        var sd = el('div', 'kosha-sense');
        var glossLang = s.gloss_language || d.meta.gloss_language;
        var h = '<span class="kosha-lang">' + (LANG_NAME[glossLang] || glossLang) + '</span>';
        if (s.pos) h += ' <span class="kosha-pos">' + esc(tl(s.pos)) + '</span>';
        sd.appendChild(el('div', 'kosha-sense-head', h));
        sd.appendChild(el('div', 'kosha-gloss', highlightHw(esc(tl(s.gloss || '')), tl(g.hw)).replace(/\n/g, '<br>')));
        if (s.etymology) sd.appendChild(el('div', 'kosha-field',
          '<span class="kosha-flabel">व्युत्पत्तिः</span> ' + esc(tl(s.etymology))));
        if (s.note) sd.appendChild(el('div', 'kosha-field',
          '<span class="kosha-flabel">टिप्पणी</span> ' + esc(tl(s.note)).replace(/\n/g, '<br>')));
        (s.citations || []).forEach(function (c) {
          sd.appendChild(el('div', 'kosha-cite', esc(tl(c.text)))); });
        sd.appendChild(actionBar(s, d, g, glossLang));
        body.appendChild(sd);
      });
    });
    card.appendChild(body);

    // "Read more" only where there is actually more to read. Measured after
    // layout, because how many lines a gloss takes depends on the viewport.
    var more = el('button', 'kosha-more', 'Read more ▾');
    more.onclick = function () {
      var open = card.classList.toggle('open');
      more.textContent = open ? 'Show less ▴' : 'Read more ▾';
    };
    card.appendChild(more);
    // Clamp FIRST, then measure: with the clamp off, clientHeight always equals
    // scrollHeight and nothing ever looks overflowing. So put the max-height in
    // effect, ask whether the content still exceeds it, and unclamp the cards
    // that fit — the short koshas keep showing whole.
    card.classList.add('clamped');
    requestAnimationFrame(function () {
      if (body.scrollHeight <= body.clientHeight + 4) { card.classList.remove('clamped'); more.remove(); }
    });
    return card;
  }

  // Translate pivots + the prefilled Gemini quick actions, for one sense.
  function actionBar(s, d, g, glossLang) {
    var bar = el('div', 'kosha-actions');
    var out = el('div', 'kosha-ai');

    [PREF_LANG, 'en'].forEach(function (target) {
      if (glossLang === target || !s.gloss) return;
      var label = '→ ' + (LANG_NAME[target] || target);
      var btn = el('button', 'kosha-xl', label);
      btn.onclick = function () {
        btn.disabled = true; btn.textContent = '…';
        var loading = el('div', 'kosha-xl-out kosha-ai-loading',
          '<div class="kosha-ai-progress"><i></i></div><div class="kosha-ai-loading-label">Translating…</div>');
        out.appendChild(loading);
        translate(s.gloss, glossLang, target).then(function (t) {
          loading.className = 'kosha-xl-out';
          loading.innerHTML = '<span class="kosha-lang">' + (LANG_NAME[target] || target) + ' *</span> ' + esc(t);
          btn.remove();
          // draw()'s own scan already ran before this async result existed --
          // a sutra number in a fresh translation would otherwise never get
          // the tappable treatment. Real gap, not theoretical: found by
          // tracing exactly when draw() calls dgeScanForSutras relative to
          // when this content actually appears in the DOM. No {always:true}
          // here though, even for a Kāśikā/Anuvṛtti/Gaṇapāṭha card -- this is
          // a translated PROSE rendering of the gloss, not the gloss's own
          // "bare number right after the headword" shape, so the normal
          // cue-word gating (सूत्र/पाणिनि nearby) is the right call same as
          // any other prose.
          if (typeof window.dgeScanForEntities === 'function') { try { window.dgeScanForEntities(loading); } catch (e2) {} }
          if (typeof window.dgeScanForSutras === 'function') { try { window.dgeScanForSutras(loading); } catch (e2) {} }
        }).catch(function (e) {
          btn.disabled = false; btn.textContent = label;
          loading.className = 'kosha-xl-err';
          loading.textContent = '⚠ ' + (e && e.message ? e.message : 'Translation failed.');
        });
      };
      bar.appendChild(btn);
    });

    quickActions().forEach(function (a) {
      var btn = el('button', 'kosha-act', esc(a.label));
      btn.onclick = function () {
        btn.disabled = true; var old = btn.textContent; btn.textContent = '…';
        // A disabled button alone was easy to miss — a Gemini call can take
        // several seconds, and the result area stayed completely blank the
        // whole time, which read as "did my click even register?". A
        // visible progress bar in the result area itself fixes that.
        var loading = el('div', 'kosha-ai-out kosha-ai-loading',
          '<div class="kosha-ai-head">' + esc(a.label) + ' <span class="kosha-ai-tag">AI *</span></div>' +
          '<div class="kosha-ai-progress"><i></i></div>' +
          '<div class="kosha-ai-loading-label">Asking Gemini…</div>');
        out.appendChild(loading);
        runAction(a, { word: g.hw, gloss: s.gloss || '', dict: d.meta.name || d.slug })
          .then(function (t) {
            loading.className = 'kosha-ai-out';
            loading.innerHTML =
              '<div class="kosha-ai-head">' + esc(a.label) + ' <span class="kosha-ai-tag">AI *</span></div>' +
              '<div class="kosha-ai-body">' + (typeof parseMarkdown === 'function' ? parseMarkdown(t) : esc(t).replace(/\n/g, '<br>')) + '</div>';
            btn.disabled = false; btn.textContent = old;
            // Same real gap as the translation branch above: an "Ask AI"
            // answer (e.g. "as per 1.1.1...") is exactly the kind of content
            // that cites sutras, and draw()'s one-time scan can't have seen
            // this yet -- it didn't exist until this callback ran. Cue-gated,
            // not {always:true}, for the same reason as the translation
            // branch: free-form AI prose, not a dictionary's own bare
            // number-after-headword citation shape.
            if (typeof window.dgeScanForEntities === 'function') { try { window.dgeScanForEntities(loading); } catch (e2) {} }
            if (typeof window.dgeScanForSutras === 'function') { try { window.dgeScanForSutras(loading); } catch (e2) {} }
          })
          .catch(function (e) {
            btn.disabled = false; btn.textContent = old;
            loading.className = 'kosha-xl-err';
            loading.textContent = '⚠ ' + (e && e.message ? e.message : 'Failed.');
          });
      };
      bar.appendChild(btn);
    });

    var wrap = el('div', 'kosha-actwrap');
    wrap.appendChild(bar); wrap.appendChild(out);
    return wrap;
  }

  function openEntry(g, detail) {
    detail.innerHTML = '<div class="kosha-loading">…</div>';
    loadEntry(g).then(function (perDict) {
      var state = { filter: '', sort: 'pinned' };

      function draw() {
        detail.innerHTML = '';
        detail.appendChild(el('h2', 'kosha-title',
          esc(tl(g.hw)) + ' <span class="kosha-slp1">' + esc(g.slp1) + '</span>'));

        var hidden = userHidden();
        var shown = perDict.filter(function (d) { return hidden.indexOf(d.slug) < 0; });
        if (state.filter) {
          var q = state.filter.toLowerCase();
          shown = shown.filter(function (d) {
            return ((d.meta.name || '') + ' ' + d.slug + ' ' + (d.meta.gloss_language || '')).toLowerCase().indexOf(q) >= 0;
          });
        }
        if (state.sort === 'pinned') shown = applyUserOrder(shown);
        else if (state.sort === 'name') shown = shown.slice().sort(function (a, b) {
          return (a.meta.name || a.slug).localeCompare(b.meta.name || b.slug); });
        else if (state.sort === 'lang') shown = shown.slice().sort(function (a, b) {
          return (a.meta.gloss_language || '').localeCompare(b.meta.gloss_language || '')
              || (a.meta.name || a.slug).localeCompare(b.meta.name || b.slug); });

        detail.appendChild(toolbar(perDict, shown, state, draw));

        // A dictionary can be pinned AND hidden at once (the card's own 🚫
        // hides without unpinning) -- and until 1 Sep 2026 that state was a
        // trap: the pin panel listed it at #1 with no hidden marking and no
        // unhide control, while the entry showed no card and no explanation.
        // Exactly the project lead's live report: शब्दार्थकौस्तुभः pinned
        // first, present in the data, invisible in the results. So a
        // pinned-but-hidden dictionary that HAS an entry for this word now
        // leaves a one-line strip with a Show button in its place.
        if (state.sort === 'pinned' && !state.filter) {
          userOrder().forEach(function (slug) {
            if (hidden.indexOf(slug) < 0) return;
            var d = null;
            perDict.forEach(function (x) { if (x.slug === slug) d = x; });
            if (!d) return;
            var strip = el('div', 'kosha-hiddenpin',
              '🚫 <b>' + esc(tl(d.meta.name || d.slug)) + '</b> has an entry here but is hidden.');
            var showBtn = el('button', 'kosha-pbtn', 'Show');
            showBtn.onclick = function () { toggleUserHidden(slug); draw(); };
            strip.appendChild(showBtn);
            detail.appendChild(strip);
          });
        }

        if (!shown.length) {
          detail.appendChild(el('div', 'kosha-empty',
            perDict.length ? 'Every kosha here is hidden or filtered out.' : 'No full entry found.'));
          return;
        }
        shown.forEach(function (d) { detail.appendChild(renderCard(d, g, draw)); });
        detail.appendChild(el('div', 'kosha-foot',
          '* machine-generated (BYOK Gemini) — verify against the original gloss.'));

        // Scripture citations (ऋ.वे. 1.165, भा. IX.22.33, AV. 7,28,1) get the
        // floating verse card from js/kosha-citations.js, then sūtra numbers
        // get the reading view's popover (js/intellisense.js). Citations run
        // first so the sūtra pass cannot claim a number that belongs to a
        // Vedic reference.
        //
        // Marked per CARD, not over the whole pane, so each dictionary's own
        // citation conventions apply: "R. 17. 27" is Raghuvaṃśa in Apte but
        // the Rāmāyaṇa in Böhtlingk, and only the card knows which it is.
        if (typeof window.dgeMarkCitations === 'function') {
          detail.querySelectorAll('.kosha-card').forEach(function (c) {
            try { window.dgeMarkCitations(c, { source: c.dataset.slug }); } catch (e) {}
          });
        }
        if (typeof window.dgeScanForEntities === 'function') {
          try { window.dgeScanForEntities(detail); } catch (e) {}
        }
        if (typeof window.dgeScanForSutras === 'function') {
          // Most koshas only ever *mention* a sūtra in passing prose, where
          // intellisense.js's own cue-word check (सूत्र/पाणिनि/... nearby)
          // is exactly right -- and stays right regardless of which page
          // the reader opened Kosha from (currentGranthaSlug being e.g. a
          // Purāṇa's is not itself the bug: a Purāṇa's "1.1.1" usually IS a
          // verse number, not a sūtra, and blanket {always:true} over every
          // dictionary would relabel it as one). But a Kāśikā/Gaṇapāṭha/
          // Anuvṛtti entry doesn't mention a sūtra -- it IS one, cited as
          // bare "७.१.१८" right after the headword with nothing "sūtra-ish"
          // in between, so the cue window never sees a cue and every single
          // citation from these three was going unlinked. Verified against
          // the real corpus (github.com/Tribhuvanachar/bhumandala-kosha-data,
          // dist branch): 100% of their citations look like this. Scoped to
          // just these slugs, not every kosha, because some others mix real
          // Ashtadhyayi references with a different corpus's numbering that
          // happens to collide with the same d.d.d shape (dhatupatha-sa
          // cites Uṇādi sūtras the same way, which are not in this app's
          // Ashtadhyayi index and would silently resolve to the wrong rule)
          // or with their own internal verse locators (Amarakośa's
          // kāṇḍa.varga.śloka, Abhidhānaratnamālā's own numbering) -- a
          // blanket {always:true} over the whole pane would relink those as
          // wrong or nonexistent sūtras, trading a missing-link bug for a
          // wrong-link one.
          // shabdArtha_kaustubha (1 Sep 2026): a Paninian-derivation
          // dictionary -- its निष्पत्तिः field cites the deriving sūtra as
          // a bare hyphenated "(३-२-९७)" with no cue word in reach, so the
          // cue-gated pass never linked a single one. Verified on the live
          // corpus; the id-known check (only real 1-8/1-4 Aṣṭādhyāyī ids
          // link) keeps {always} safe here just as for the three above.
          var ALWAYS_SUTRA_KOSHAS = { kashika: 1, 'ashtadhyayi-anuvritti': 1, ganapatha: 1, shabdArtha_kaustubha: 1 };
          detail.querySelectorAll('.kosha-card').forEach(function (c) {
            try { window.dgeScanForSutras(c, { always: !!ALWAYS_SUTRA_KOSHAS[c.dataset.slug] }); } catch (e) {}
          });
        }
      }
      draw();
    });
  }

  // Filter + sort + the pin/unhide panel.
  function toolbar(perDict, shown, state, redraw) {
    var bar = el('div', 'kosha-tools');

    var f = document.createElement('input');
    f.type = 'search'; f.className = 'kosha-filter'; f.placeholder = 'Filter koshas…'; f.value = state.filter;
    f.oninput = function () { state.filter = f.value; var at = f.selectionStart; redraw();
      var nf = document.querySelector('.kosha-filter'); if (nf) { nf.focus(); nf.setSelectionRange(at, at); } };
    bar.appendChild(f);

    var sel = document.createElement('select');
    sel.className = 'kosha-sort';
    [['pinned', 'My order'], ['name', 'Name A–Z'], ['lang', 'Language']].forEach(function (o) {
      var op = document.createElement('option'); op.value = o[0]; op.textContent = o[1];
      if (state.sort === o[0]) op.selected = true; sel.appendChild(op);
    });
    sel.onchange = function () { state.sort = sel.value; redraw(); };
    bar.appendChild(sel);

    // Say WHY shown < total: "31 / 35" alone reads as a bug when the other
    // four are the reader's own hidden dictionaries.
    var hid = userHidden();
    var nHid = perDict.filter(function (d) { return hid.indexOf(d.slug) >= 0; }).length;
    var count = el('span', 'kosha-tcount',
      shown.length + ' / ' + perDict.length + ' कोश' + (nHid ? ' · ' + nHid + ' hidden (⚙)' : ''));
    bar.appendChild(count);

    var gear = el('button', 'kosha-gear', '⚙');
    gear.title = 'Pin koshas to the top, and unhide';
    gear.onclick = function () {
      var p = bar.parentNode.querySelector('.kosha-panel');
      if (p) { p.remove(); return; }
      bar.parentNode.insertBefore(orderPanel(perDict, redraw), bar.nextSibling);
    };
    bar.appendChild(gear);
    return bar;
  }

  // Pin/unpin and unhide. Pinned koshas lead the entry in the order listed —
  // that is how a Kannada reader gets शब्दार्थकौस्तुभः first, then
  // शब्दकल्पद्रुमः, then वाचस्पत्यम्, without hiding anything else.
  function orderPanel(perDict, redraw) {
    var p = el('div', 'kosha-panel');
    p.appendChild(el('div', 'kosha-panel-h',
      'Pinned koshas lead every entry, in this order. ▲▼ to move, ✕ to unpin, 🚫 to hide.'));

    function rows() {
      var list = el('div', 'kosha-panel-list');
      var ord = userOrder(), hid = userHidden();
      var byslug = {}; perDict.forEach(function (d) { byslug[d.slug] = d; });
      var name = function (s) { return (byslug[s] && byslug[s].meta.name) || s; };

      ord.forEach(function (s, i) {
        // Pinned rows used to show no hidden state and no unhide control at
        // all -- see the kosha-hiddenpin comment in draw() for the trap
        // that made. Same strikethrough + 👁/🚫 toggle as unpinned rows.
        var isHid = hid.indexOf(s) >= 0;
        var r = el('div', 'kosha-prow pinned' + (isHid ? ' hid' : ''), '<span class="kosha-pnum">' + (i + 1) + '</span><span class="kosha-pname">' + esc(tl(name(s))) + '</span>');
        [['▲', -1, 'Move up'], ['▼', 1, 'Move down']].forEach(function (mv) {
          var b = el('button', 'kosha-pbtn', mv[0]);
          b.title = mv[2];
          b.onclick = function () {
            var a = userOrder(), t = i + mv[1];
            if (t < 0 || t >= a.length) return;
            var x = a[i]; a[i] = a[t]; a[t] = x; setUserOrder(a); refresh();
          };
          r.appendChild(b);
        });
        var x = el('button', 'kosha-pbtn', '✕');
        x.title = 'Unpin ' + tl(name(s)) + ' (stays in results, just no longer pinned to the top)';
        x.onclick = function () { var a = userOrder(); a.splice(i, 1); setUserOrder(a); refresh(); };
        r.appendChild(x);
        var h = el('button', 'kosha-pbtn', isHid ? '👁' : '🚫');
        h.title = isHid ? 'Show again' : 'Hide from results (stays pinned)';
        h.onclick = function () { toggleUserHidden(s); refresh(); };
        r.appendChild(h);
        list.appendChild(r);
      });

      perDict.forEach(function (d) {
        if (ord.indexOf(d.slug) >= 0) return;
        var isHid = hid.indexOf(d.slug) >= 0;
        var r = el('div', 'kosha-prow' + (isHid ? ' hid' : ''),
          '<span class="kosha-pname">' + esc(tl(d.meta.name || d.slug)) + '</span>');
        var pin = el('button', 'kosha-pbtn', '📌');
        pin.title = 'Pin to the top';
        pin.onclick = function () { var a = userOrder(); a.push(d.slug); setUserOrder(a); refresh(); };
        r.appendChild(pin);
        var h = el('button', 'kosha-pbtn', isHid ? '👁' : '🚫');
        h.title = isHid ? 'Show again' : 'Hide from results';
        h.onclick = function () { toggleUserHidden(d.slug); refresh(); };
        r.appendChild(h);
        list.appendChild(r);
      });
      return list;
    }

    function refresh() {
      var old = p.querySelector('.kosha-panel-list');
      if (old) p.replaceChild(rows(), old);
      redraw();
      // redraw() rebuilds the detail pane, so re-attach this panel to the new one
      var bar = document.querySelector('.kosha-tools');
      if (bar && bar.parentNode && !bar.parentNode.querySelector('.kosha-panel')) {
        bar.parentNode.insertBefore(p, bar.nextSibling);
      }
    }

    p.appendChild(rows());
    return p;
  }
  // ---- overlay + styles -----------------------------------------------------
  function injectCSS() {
    if (document.getElementById('kosha-css')) return;
    var css = document.createElement('style'); css.id = 'kosha-css';
    // Fallbacks below map to the app's real design tokens (css/main.css) so
    // the Kosha overlay themes with the rest of the site instead of using
    // hard-coded colours. Overlay sits at modal level (11000).
    // 24 Aug 2026: this used to also define a #kosha-fab floating circle
    // (paired visually with global-search.js's own .dge-gs-fab, per an
    // earlier pass's fix for the two looking uncoordinated) -- that pass
    // deliberately kept both FABs, reasoning they were frequent enough
    // that folding them into a menu would cost real convenience. The
    // project lead's own direct follow-up overrides that call explicitly
    // ("let it not sit there... go into some menu item"): the FAB is gone,
    // #dge-qa-tab (index.html, main.css) is the one remaining entry point
    // for both कोश and search, and build() below no longer creates a
    // trigger button of its own -- window.dgeOpenKosha (further down this
    // file) is the real, already-exported API the tab's popup item calls.
    css.textContent = [
      '#kosha-ov{position:fixed;inset:0;z-index:11000;background:var(--bg-main,#fff);color:var(--text-primary,#111);display:none;flex-direction:column}',
      '#kosha-ov.open{display:flex}',
      '.kosha-bar{display:flex;gap:8px;padding:12px;border-bottom:1px solid var(--card-border,#ddd);align-items:center}',
      '.kosha-bar input{flex:1;font-size:18px;padding:10px 12px;border:1px solid var(--card-border,#ccc);border-radius:8px;background:var(--card-bg,#fff);color:inherit}',
      '.kosha-bar button{background:none;border:none;font-size:22px;cursor:pointer;color:inherit;padding:6px 10px}',
      '.kosha-body{flex:1;display:flex;min-height:0}',
      '.kosha-res{width:38%;max-width:340px;overflow:auto;border-right:1px solid var(--card-border,#eee)}',
      '.kosha-detail{flex:1;overflow:auto;padding:16px}',
      '@media(max-width:640px){.kosha-res{width:100%;max-width:none;border-right:none}.kosha-detail{display:none}#kosha-ov.showdetail .kosha-res{display:none}#kosha-ov.showdetail .kosha-detail{display:block}}',
      '.kosha-hit{padding:10px 12px;border-bottom:1px solid var(--card-border,#f0f0f0);cursor:pointer}',
      '.kosha-hit:hover{background:var(--card-active,#f6f1ea)}',
      '.kosha-hw{font-size:19px;font-weight:600;margin-right:8px}',
      '.kosha-count{font-size:12px;color:var(--muted-text,#888);margin-right:6px}',
      '.kosha-chip{display:inline-block;font-size:11px;background:var(--card-active,#efe7dc);border-radius:10px;padding:1px 7px;margin:1px 2px}',
      '.kosha-title{font-size:26px;margin:0 0 10px}',
      '.kosha-slp1{font-size:14px;color:var(--muted-text,#999);font-weight:400}',
      // One type scale for every dictionary. The corpus mixes 93 sources whose
      // own markup ranged from bare text to full HTML pages, so the renderer —
      // not the source — decides size, weight and colour; otherwise each card
      // looks like it came from a different app, which is exactly what it did.
      '.kosha-card{border:1px solid var(--card-border,#e6ddcf);border-radius:10px;padding:12px 14px;margin:0 0 14px;background:var(--card-bg,transparent)}',
      '.kosha-src{font-weight:600;margin-bottom:8px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}',
      '.kosha-src-name{font-size:15px;flex:1 1 auto;min-width:8em}',
      '.kosha-hidebtn{background:none;border:none;cursor:pointer;font-size:14px;opacity:.5;padding:2px 4px;line-height:1}',
      '.kosha-hidebtn:hover{opacity:1}',
      '.kosha-altform{font-size:14px;font-weight:600;color:var(--muted-text,#8a5a2b);margin:6px 0 0}',
      '.kosha-lic{font-size:11px;color:#a33;border:1px solid #d99;border-radius:8px;padding:0 6px;font-weight:400;white-space:nowrap}',
      '.kosha-lic.ok{color:#286;border-color:#8c9}',
      '.kosha-sense{padding:8px 0;border-top:1px dashed var(--card-border,#eee)}',
      '.kosha-sense-head{margin-bottom:4px}',
      '.kosha-lang{font-size:11px;background:var(--accent-red,#8a5a2b);color:#fff;border-radius:8px;padding:1px 7px}',
      '.kosha-pos{font-size:12px;color:var(--muted-text,#888);font-style:italic}',
      '.kosha-gloss{font-size:16.5px;line-height:1.65;margin:4px 0}',
      '.kosha-hl{background:rgba(232,178,77,.4);color:inherit;border-radius:3px;padding:0 1px;font-weight:700}',
      '.kosha-field,.kosha-cite{font-size:14px;line-height:1.6;color:var(--muted-text,#666);margin:4px 0}',
      '.kosha-flabel{font-weight:600;color:var(--accent-red,#8a5a2b)}',
      '.kosha-cite{font-style:italic;padding-left:10px;border-left:2px solid var(--card-border,#e6ddcf)}',
      // Collapse: ~7 lines of gloss, which is enough for the short koshas to
      // show whole and enough of the encyclopaedias to judge relevance.
      '.kosha-body-wrap{max-height:none;overflow:visible}',
      '.kosha-card.clamped .kosha-body-wrap{max-height:11.5em;overflow:hidden;-webkit-mask-image:linear-gradient(#000 70%,transparent)}',
      '.kosha-card.clamped.open .kosha-body-wrap{max-height:none;-webkit-mask-image:none}',
      '.kosha-more{background:none;border:none;color:var(--accent-red,#8a5a2b);font:inherit;font-size:13px;cursor:pointer;padding:6px 0 0}',
      '.kosha-card:not(.clamped) .kosha-more{display:none}',
      // Toolbar + pin panel
      '.kosha-tools{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:0 0 12px}',
      '.kosha-filter{flex:1;min-width:120px;font:inherit;font-size:14px;padding:6px 10px;border:1px solid var(--card-border,#ccc);border-radius:8px;background:var(--card-bg,#fff);color:inherit}',
      '.kosha-sort{font:inherit;font-size:13px;padding:6px 8px;border:1px solid var(--card-border,#ccc);border-radius:8px;background:var(--card-bg,#fff);color:inherit}',
      '.kosha-tcount{font-size:12px;color:var(--muted-text,#888)}',
      '.kosha-gear{background:none;border:1px solid var(--card-border,#ccc);border-radius:8px;cursor:pointer;font-size:14px;padding:5px 9px;color:inherit}',
      '.kosha-panel{border:1px solid var(--card-border,#e6ddcf);border-radius:10px;padding:10px;margin:0 0 14px;background:var(--card-active,#faf6ef)}',
      '.kosha-panel-h{font-size:12px;color:var(--muted-text,#888);margin-bottom:8px}',
      '.kosha-prow{display:flex;align-items:center;gap:6px;padding:4px 0;font-size:14px}',
      '.kosha-prow.pinned{font-weight:600}',
      '.kosha-prow.hid .kosha-pname{opacity:.45;text-decoration:line-through}',
      '.kosha-pname{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}',
      '.kosha-pnum{font-size:11px;color:var(--muted-text,#888);width:1.4em}',
      '.kosha-pbtn{background:none;border:1px solid var(--card-border,#ddd);border-radius:6px;cursor:pointer;font-size:12px;padding:2px 7px;color:inherit}',
      // Quick actions
      '.kosha-actwrap{margin-top:6px}',
      '.kosha-actions{display:flex;gap:6px;flex-wrap:wrap}',
      '.kosha-act{background:none;border:1px solid var(--card-border,#ddd);border-radius:14px;font:inherit;font-size:12px;padding:3px 10px;cursor:pointer;color:var(--muted-text,#666)}',
      '.kosha-act:hover{border-color:var(--accent-red,#8a5a2b);color:var(--accent-red,#8a5a2b)}',
      '.kosha-ai-out{border-left:3px solid var(--accent-red,#8a5a2b);padding:6px 0 6px 10px;margin:8px 0}',
      '.kosha-ai-head{font-size:12px;font-weight:600;color:var(--accent-red,#8a5a2b)}',
      '.kosha-ai-tag{font-weight:400;color:var(--muted-text,#999)}',
      '.kosha-ai-body{font-size:15px;line-height:1.6;margin-top:3px}',
      '.kosha-ai-body .md-p:first-child{margin-top:0}',
      // Indeterminate bar (width unknown — Gemini gives no progress
      // events) rather than a spinner, so it reads clearly next to the
      // "Asking Gemini…" label instead of competing with it for attention.
      '.kosha-ai-progress{height:4px;border-radius:999px;background:var(--card-border,#e6ddcf);overflow:hidden;margin:6px 0 4px;width:140px}',
      '.kosha-ai-progress i{display:block;height:100%;width:40%;border-radius:999px;background:var(--accent-red,#8a5a2b);animation:koshaAiProgress 1.1s ease-in-out infinite}',
      '@keyframes koshaAiProgress{0%{transform:translateX(-100%)}100%{transform:translateX(350%)}}',
      '.kosha-ai-loading-label{font-size:12px;color:var(--muted-text,#999)}',
      '@media(prefers-reduced-motion:reduce){.kosha-ai-progress i{animation:none;width:100%}}',
      '.kosha-xl{font-size:12px;margin:4px 6px 0 0;background:var(--card-active,#efe7dc);border:none;border-radius:8px;padding:3px 8px;cursor:pointer;color:inherit}',
      '.kosha-xl-out{font-size:15px;margin:4px 0;padding:6px 8px;background:var(--card-active,#f6f1ea);border-radius:8px}',
      '.kosha-xl-err{font-size:13px;margin:4px 0;padding:6px 8px;background:rgba(170,51,51,.08);border:1px solid #d99;border-radius:8px;color:#a33}',
      '.kosha-nearest{font-size:12.5px;padding:9px 12px;color:var(--muted-text,#8b7c66);background:var(--card-active,#f6f1ea);border-bottom:1px solid var(--card-border,#eee)}',
      '.kosha-hiddenpin{display:flex;align-items:center;gap:8px;font-size:13px;color:var(--muted-text,#8b7c66);border:1px dashed var(--card-border,#ddd);border-radius:10px;padding:8px 12px;margin:0 0 10px}',
      '.kosha-hiddenpin b{font-weight:600}',
      '.kosha-hiddenpin .kosha-pbtn{margin-left:auto}',
      '.kosha-empty,.kosha-loading,.kosha-foot{padding:14px;color:var(--muted-text,#999)}',
      '.kosha-foot{font-size:12px;border-top:1px solid var(--card-border,#eee);margin-top:12px}'
    ].join('\n');
    document.head.appendChild(css);
  }

  function build() {
    injectCSS();
    var ov = el('div'); ov.id = 'kosha-ov';
    ov.innerHTML =
      '<div class="kosha-bar"><input id="kosha-q" placeholder="Search a word (Devanagari / IAST / Kannada)…" autocomplete="off">' +
      '<button id="kosha-close" title="Close">✕</button></div>' +
      '<div class="kosha-body"><div class="kosha-res" id="kosha-res"></div><div class="kosha-detail" id="kosha-detail">' +
      '<div class="kosha-empty">Type a headword to look it up across every dictionary.</div></div></div>';
    document.body.appendChild(ov);
    var input = ov.querySelector('#kosha-q'), res = ov.querySelector('#kosha-res'), detail = ov.querySelector('#kosha-detail');

    // Every keystroke past the debounce starts its own lookup, and they do not
    // come back in the order they were sent: a one-character query browses
    // hundreds of shards and takes seconds, while the whole word hits one
    // shard and answers at once. Without a guard the slow early query lands
    // last and overwrites the right answer -- which is what searching अगस्त्य
    // on a phone actually showed: the box said अगस्त्य and the list underneath
    // was अ, आ, aa, ai, अक, अख…, the answer to its own first letter. Only the
    // most recent query is allowed to paint.
    var seq = 0;
    function show(result, mine) {
      if (mine !== seq) return;
      renderResults(result, res, detail);
      // on mobile, reveal detail pane when a hit is chosen
      res.querySelectorAll('.kosha-hit').forEach(function (r) {
        r.addEventListener('click', function () { ov.classList.add('showdetail'); }); });
    }
    /* Everything in this file lives in a closure, which was right while the
       कोश button was the only way in. The word popover in intellisense.js
       needs to hand a word straight across, so this is the one door out:
       open the overlay already looking the word up, rather than making the
       reader retype what they just tapped. */
    window.dgeOpenKosha = function (word) {
      ov.classList.add('open');
      ov.classList.remove('showdetail');
      input.value = word || '';
      if (word) {
        var mine = ++seq;
        search(word).then(function (result) { show(result, mine); });
      } else {
        input.focus();
      }
    };
    ov.querySelector('#kosha-close').onclick = function () {
      if (ov.classList.contains('showdetail')) ov.classList.remove('showdetail'); else ov.classList.remove('open'); };
    var t;
    input.oninput = function () {
      clearTimeout(t); var q = input.value;
      var mine = ++seq;
      t = setTimeout(function () {
        if (!q.trim()) { if (mine === seq) res.innerHTML = ''; return; }
        search(q).then(function (result) { show(result, mine); });
      }, 160);
    };
  }

  // ---- engine export (kosha2) --------------------------------------------
  // The v2 results page (kosha2.html) drives this same battle-tested engine
  // through a data-only surface instead of duplicating the two-tier shard
  // lookup. bucketFor mirrors loadEntry's deep-split walk so kosha2 can
  // fetch the ENRICHED twin (kosha_r) of exactly the shard an entry lives
  // in. Setting window.DGE_KOSHA_ENGINE_ONLY (before this script) skips the
  // floating-button/overlay build entirely — engine with no UI.
  // search inside the MEANINGS: exact folded-token lookup in the gloss
  // inverted index (data/koshas/_gloss, built by the data repo's Actions).
  // Returns { hits: [{d, h, n}], truncated } — d dictionary slug, h the
  // headword whose gloss carries the token, n occurrences.
  var glossManifest = null;
  function glossSearch(query) {
    return (glossManifest ? Promise.resolve(glossManifest)
      : j(BASE + '/_gloss/manifest.json').then(function (m) { glossManifest = m; return m; }))
      .then(function (gm) {
        if (!gm) throw new Error('gloss index not built yet');
        var folds = [], seen = {};
        toSLP1list(query).map(fold).forEach(function (f) {
          if (f && !seen[f]) { seen[f] = 1; folds.push(f); }
        });
        if (!folds.length) return { hits: [], truncated: false };
        var need = {};
        folds.forEach(function (qf) {
          gm.buckets.forEach(function (b) { if (qf.indexOf(b) === 0) need[b] = 1; });
        });
        var buckets = Object.keys(need);
        if (!buckets.length) return { hits: [], truncated: false };
        return Promise.all(buckets.map(function (b) {
          return j(BASE + '/_gloss/' + safeBucket(b) + '.json');
        })).then(function (shards) {
          var failed = buckets.filter(function (b, i) { return !shards[i]; });
          var hits = [], dedup = {};
          shards.forEach(function (sh) {
            if (!sh) return;
            folds.forEach(function (qf) {
              (sh[qf] || []).forEach(function (row) {
                var k = row[0] + '|' + row[1];
                if (dedup[k]) return; dedup[k] = 1;
                hits.push({ d: row[0], h: row[1], n: row[2] || 1 });
              });
            });
          });
          if (failed.length && !hits.length) {
            throw new Error('gloss index shard unreachable (' + failed.join(', ') + ')');
          }
          hits.sort(function (a, b) { return b.n - a.n || a.h.localeCompare(b.h); });
          var truncated = hits.length > 400;
          return { hits: hits.slice(0, 400), truncated: truncated };
        });
      });
  }

  window.DGEKoshaEngine = {
    search: search,
    glossSearch: glossSearch,
    loadEntry: loadEntry,
    applyUserOrder: applyUserOrder,
    fold: fold,
    toSLP1list: toSLP1list,
    gkey: gkey,
    base: function () { return BASE; },
    manifest: function () {
      return manifest ? Promise.resolve(manifest)
        : j(BASE + '/_index/manifest.json').then(function (m) { manifest = m; return m; });
    },
    bucketFor: function (dictSlug, efold) {
      if (!manifest || !manifest.dictionaries[dictSlug]) return null;
      var d = manifest.dictionaries[dictSlug];
      var eLen = manifest.entry_shard_len || 3;
      var bucket = efold.slice(0, eLen), deep = d.deep;
      if (deep && deep.length) {
        while (deep.indexOf(bucket) >= 0 && bucket.length < efold.length) {
          bucket = efold.slice(0, bucket.length + 1);
        }
      }
      return { category: d.category, bucket: bucket };
    }
  };

  if (window.DGE_KOSHA_ENGINE_ONLY) { console.log('[Init] kosha.js engine-only.'); return; }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', build);
  else build();
  console.log('[Init] kosha.js loaded.');
})();
