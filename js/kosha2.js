// js/kosha2.js — the Kosha results v2 page (kosha2.html).
// Drives window.DGEKoshaEngine (kosha.js loaded with DGE_KOSHA_ENGINE_ONLY)
// for lookup, renders from the ENRICHED render tree (kosha_r, built by
// tools/kosha_enrich.py) when it is reachable, and falls back to the raw
// gloss text of the same entries when it is not — so the page never shows
// less than the old overlay did.
//
// Feature map (mockup-review verdicts, 3 Sep 2026):
//   digest with consensus senses · language lens chips with counts ·
//   per-dictionary native layouts · searched-word highlighting ·
//   typed reference chips (sutra → Ashtadhyayi anchor, cite → corpus
//   search deep link, src → attribution popover, synonym → self lookup)
//   · AI strictly behind the ⋯ context menu (BYOK, via window.DGEGemini)
//   · per-card copy + whole-page copy/share + #word= deep links ·
//   pin/hide/reorder (reader-local) · committed visibility tiers from
//   admin/config/kosha-overrides.json · per-kosha A-Z browse mode.
(function () {
  'use strict';
  window.DGE_VERSIONS = window.DGE_VERSIONS || {};
  window.DGE_VERSIONS['kosha2.js'] = 'v1.4 (3 Sep 2026 mobile field report: every menu/reference opens as a BOTTOM SHEET with ✕/back — nothing runs off-screen or navigates away (Ashtadhyayi sutras render in-page from sutrapatha data, dhatu citations link to the dhatupatha, Unadi refs get an honest not-yet sheet); licence chips removed from reading cards (admin manager only); cards collapsible; long paragraph entries break per numbered sense; cluster-safe hit highlighting (अब्जेषु); digest shows unique-meaning count + top 4; language filter is one compact select; kosha arranging moved to ⚙ Arrange; NEW अर्थे mode: search inside the meanings via the gloss index) · v1.3 (3 Sep 2026 report: kosha order preference — Default/A–Z/Z–A/My order in ⚙ Settings, Move up / Move to top in each card menu, persisted in localStorage; browse picker gains a name filter; the alphabet rail sorts in varnamala order instead of page-encounter order; degraded-index toast + suggestion catch on top of kosha.js v2.0 shard honesty) · v1.1 (mobile: search input owns its own header row; browse: tap feedback + loading states + alphabet rail grouped by first akshara instead of one button per page; search-failure message; corpus pinned by dist SHA in config.js; v1.0: script switcher, jump rail, gender digest, 7 AI actions, settings sheet)';

  var E = window.DGEKoshaEngine;
  var RENDER_BASE = (window.KOSHA_RENDER_BASE || '').replace(/\/+$/, '');
  var LANG_NAME = { sa: 'संस्कृतम्', kn: 'ಕನ್ನಡ', en: 'English', hi: 'हिन्दी',
                    bn: 'বাংলা', te: 'తెలుగు', ta: 'தமிழ்', fr: 'Français', de: 'Deutsch' };

  var state = {
    mode: 'search',              // 'search' | 'browse'
    query: '', group: null, perDict: [], enriched: {},
    lens: 'all',
    pins: lsGet('kosha2_pins', []), hidden: lsGet('kosha2_hidden', []),
    order: lsGet('kosha2_order', []),
    sortmode: lsGet('kosha2_sortmode', 'curated'),   // curated | az | za | custom
    collapsed: lsGet('kosha2_collapsed', []),
    consMore: false,
    script: lsGet('kosha2_script', 'deva'),   // 'deva' | 'iast' | 'knda'
    history: lsGet('kosha2_history', []),
    browseDict: null, browsePage: 0, browseIndex: null,
    overrides: { visibility: {}, order: [], pins: [] },
    superadmin: false
  };
  var enrichCache = {}, browseCache = {};

  function lsGet(k, d) { try { var v = JSON.parse(localStorage.getItem(k) || 'null'); return v === null ? d : v; } catch (e) { return d; } }
  function lsSet(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]; }); }
  function $(s, r) { return (r || document).querySelector(s); }
  function toast(msg) { var t = $('#k2Toast'); t.textContent = msg; t.hidden = false; clearTimeout(toast._t); toast._t = setTimeout(function () { t.hidden = true; }, 2100); }
  function fetchJson(url) { return fetch(url).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; }); }

  // ---- display script (deva | iast | knda) -------------------------------
  // Input already folds every script; this is the OUTPUT side: after each
  // render, Devanagari runs in the results are transliterated in place.
  // Text nodes only — markup, hit-highlights and handlers are untouched.
  var DEVA_RUN = /[ऀ-ॿ][ऀ-ॿ‌‍]*/g;
  var SCRIPT_TARGET = { iast: 'iast', knda: 'kannada' };
  function xlitText(s) {
    var tgt = SCRIPT_TARGET[state.script];
    if (!tgt || !window.Sanscript) return s;
    return s.replace(DEVA_RUN, function (run) {
      try { return window.Sanscript.t(run, 'devanagari', tgt); } catch (e) { return run; }
    });
  }
  function applyScript(root) {
    if (state.script === 'deva' || !window.Sanscript || !root) return;
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
    var node;
    while ((node = walker.nextNode())) {
      if (DEVA_RUN.test(node.nodeValue)) node.nodeValue = xlitText(node.nodeValue);
      DEVA_RUN.lastIndex = 0;
    }
  }
  function setScript(sc) {
    state.script = sc; lsSet('kosha2_script', sc);
    document.querySelectorAll('#k2Script button').forEach(function (b) {
      b.classList.toggle('active', b.dataset.script === sc);
    });
    if (state.mode === 'browse' && state.browseDict) openBrowse(state.browseDict, state.browsePage);
    else if (state.mode === 'browse') renderBrowsePicker();
    else renderResults();
  }

  function pushHistory(hw) {
    var h = state.history.filter(function (x) { return x !== hw; });
    h.unshift(hw); state.history = h.slice(0, 25);
    lsSet('kosha2_history', state.history);
  }

  // ---- committed visibility tiers ----------------------------------------
  // public: everywhere · search_hidden: browse-only · unlisted: direct
  // ?browse= link only · disabled: nowhere. Superadmins see everything,
  // with a badge, so the manager can be verified from the page itself.
  function visTier(slug) { return state.overrides.visibility[slug] || 'public'; }
  function allowedInSearch(slug) {
    if (state.superadmin) return true;
    var t = visTier(slug); return t === 'public';
  }
  function allowedInBrowseList(slug) {
    if (state.superadmin) return true;
    var t = visTier(slug); return t === 'public' || t === 'search_hidden';
  }
  function allowedAtAll(slug) { return state.superadmin || visTier(slug) !== 'disabled'; }

  // ---- enriched twin fetch -----------------------------------------------
  function enrichedFor(slug, efold, headword) {
    if (!RENDER_BASE) return Promise.resolve(null);
    var loc = E.bucketFor(slug, efold);
    if (!loc) return Promise.resolve(null);
    var url = RENDER_BASE + '/' + loc.category + '/' + slug + '/e/' +
              encodeURIComponent(loc.bucket) + '.json';
    var p = enrichCache[url] || (enrichCache[url] = fetchJson(url));
    return p.then(function (sh) {
      if (!sh || !sh[efold]) return null;
      var rows = sh[efold].filter(function (it) { return it.headword === headword; });
      return rows.length ? rows : null;
    });
  }

  // ---- rendering ----------------------------------------------------------
  function markHits(escaped) {
    var q = (state.query || '').trim();
    if (!q || q.length < 2) return escaped;
    try {
      var re = new RegExp(q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g');
      // NEVER split a Devanagari cluster: highlighting अब्ज inside अब्जेषु
      // used to cut ज from its े and the akshara rendered broken (the
      // lead's 3 Sep report — copy-paste was fine, display was not).
      // Extend the highlight over trailing combining marks, and across a
      // virama into the next consonant.
      var CMB = /[ऀ-ःऺ-्॑-ॗॢॣ‌‍]/;
      var out = '', last = 0, m;
      while ((m = re.exec(escaped)) !== null) {
        var end = m.index + m[0].length;
        while (end < escaped.length) {
          var c = escaped[end];
          if (CMB.test(c)) {
            end++;
            if (c === '्' && end < escaped.length && /[क-हक़-य़ॸ-ॿ]/.test(escaped[end])) end++;
          } else break;
        }
        out += escaped.slice(last, m.index) + '<mark class="k2-hit">' + escaped.slice(m.index, end) + '</mark>';
        last = end;
        re.lastIndex = end;
      }
      return out + escaped.slice(last);
    } catch (e) { return escaped; }
  }

  // reference linkifiers, applied to already-escaped gloss text.
  // Unadi refs like (उ० ४-९८) become tappable everywhere; dhatu citations
  // like आप्लृ (व्याप्तौ) only inside etymology blocks, where that shape is
  // canonical (in running gloss prose it would be far too greedy).
  var inEtym = false, breakNums = false;
  function linkifyRefs(h) {
    h = h.replace(/उ(?:०|\.)\s*([०-९0-9]+[-–][०-९0-9]+)/g, function (mm, ref) {
      return '<button class="k2-ref unadi" data-unadi="' + esc(ref) + '" lang="sa">' + mm + '</button>';
    });
    if (inEtym) {
      var L = '[\\u0904-\\u0939\\u093c-\\u094d\\u0950-\\u0963\\u0971-\\u097f]';
      h = h.replace(new RegExp('(' + L + '{2,})\\s*\\((\\s*' + L + '+\\s*)\\)', 'g'),
        function (mm, root, artha) {
          return '<button class="k2-ref dhatu" data-dhatu="' + esc(root) + '" data-artha="' +
            esc(artha.trim()) + '" lang="sa">' + esc(root) + '</button> (' + esc(artha.trim()) + ')';
        });
    }
    // long paragraph-style entries (Vachaspatya, SKD, MW…): each numbered
    // sense starts on its own line, like Shabdartha-Kaustubha's layout
    if (breakNums) {
      h = h.replace(/(^|[\s।॥])([०-९]{1,3}|\d{1,3})(\s)/g, '$1<br><b class="k2-inl-no">$2</b>$3');
    }
    return h;
  }
  function spanHtml(sp) {
    if (!sp) return '';
    if (sp.t === 'sutra') {
      // in-page sheet, not a navigation — the full Ashtadhyayi page stays a
      // link INSIDE the sheet for whoever wants the deep context
      return '<button class="k2-ref sutra" data-sutra="' + esc(sp.id) +
             '" title="अष्टाध्यायी ' + esc(sp.id) + '">' + esc(sp.s) + '</button>';
    }
    if (sp.t === 'cite') {
      return '<button class="k2-ref cite" data-cite="' + esc(sp.s) + '" data-q="' + esc(sp.q || '') + '">' + esc(sp.s) + '</button>';
    }
    if (sp.t === 'src') {
      return '<button class="k2-ref src" data-src="' + esc(sp.s) + '">' + esc(sp.s) + '</button>';
    }
    return linkifyRefs(markHits(esc(sp.s)));
  }
  function spansHtml(spans) { return (spans || []).map(spanHtml).join(''); }

  function senseHtml(rs) {
    var h = '<div class="k2-sense"><span class="k2-sense-no">' + esc(rs.n) + '</span>';
    var glossLen = (rs.spans || []).reduce(function (n, sp) {
      // plain text spans carry t:"txt" (or no t at all in older builds)
      return n + (sp && (!sp.t || sp.t === 'txt') ? String(sp.s || '').length : 0);
    }, 0);
    breakNums = glossLen > 260;
    h += spansHtml(rs.spans);
    breakNums = false;
    if (rs.pos) h += '<span class="k2-pos">' + esc(rs.pos) + '</span>';
    if (rs.subs && rs.subs.length) {
      h += rs.subs.map(function (sub) {
        return '<div class="k2-sub"><span class="k2-sense-no">' + esc(sub.n) + '</span>' + spansHtml(sub.spans) + '</div>';
      }).join('');
    }
    if (rs.etym && rs.etym.length) {
      inEtym = true;
      h += '<div class="k2-etym"><b>व्युत्पत्तिः / निष्पत्तिः</b>' + spansHtml(rs.etym) + '</div>';
      inEtym = false;
    }
    if (rs.cites && rs.cites.length) {
      h += '<div class="k2-cites">' + rs.cites.map(function (c) { return '<span>' + spansHtml(c) + '</span>'; }).join('') + '</div>';
    }
    if (rs.syns && rs.syns.length) {
      h += '<div class="k2-note" style="margin-top:7px">समानार्थकाः</div><div class="k2-syns">' +
        rs.syns.map(function (s) { return '<button class="k2-syn" data-lookup="' + esc(s) + '">' + esc(s) + '</button>'; }).join('') + '</div>';
    }
    return h + '</div>';
  }
  function rawSenseHtml(sense, i) {
    var h = '<div class="k2-sense"><span class="k2-sense-no">' + (i + 1) + '</span>';
    breakNums = String(sense.gloss || '').length > 260;
    h += linkifyRefs(markHits(esc(sense.gloss || '')));
    breakNums = false;
    if (sense.pos) h += '<span class="k2-pos">' + esc(sense.pos) + '</span>';
    if (sense.etymology) {
      inEtym = true;
      h += '<div class="k2-etym"><b>व्युत्पत्तिः / निष्पत्तिः</b>' + linkifyRefs(markHits(esc(sense.etymology))) + '</div>';
      inEtym = false;
    }
    if (sense.citations && sense.citations.length) {
      h += '<div class="k2-cites">' + sense.citations.map(function (c) { return '<span class="k2-ref cite">' + esc(c.text || '') + '</span>'; }).join('') + '</div>';
    }
    return h + '</div>';
  }

  function mark(name) {
    var letters = String(name || '').replace(/[^A-Za-z]/g, '').slice(0, 2).toUpperCase();
    return letters || 'क';
  }

  function orderedDicts() {
    var arr = state.perDict.filter(function (d) { return allowedAtAll(d.slug); });
    if (state.lens !== 'all') arr = arr.filter(function (d) { return (d.meta.gloss_language || '') === state.lens; });
    arr = arr.filter(function (d) { return state.hidden.indexOf(d.slug) < 0; });
    // pins always lead; below them the user's chosen sort mode decides:
    // curated (site default), A–Z / Z–A by kosha name, or the user's own
    // hand-arranged order (built from the card menu's Move up / Move to top)
    var rank = {};
    // the user's own pins always lead. Below them, THEIR chosen mode wins:
    // an explicit A–Z / hand-arranged order outranks the site's committed
    // pins/order — those apply only in the curated default (and as the
    // fallback tail of a custom order).
    var seq = state.pins.slice();
    if (state.sortmode === 'custom') seq = seq.concat(state.order);
    if (state.sortmode === 'curated' || state.sortmode === 'custom') {
      seq = seq.concat(state.overrides.pins || [], state.overrides.order || []);
    }
    seq.forEach(function (s, i) { if (!(s in rank)) rank[s] = i; });
    var name = function (d) { return String(d.meta.name || d.slug); };
    arr.sort(function (a, b) {
      var ra = rank[a.slug] !== undefined ? rank[a.slug] : 999;
      var rb = rank[b.slug] !== undefined ? rank[b.slug] : 999;
      if (ra !== rb) return ra - rb;
      var na = name(a), nb = name(b);
      if (state.sortmode === 'az') return na < nb ? -1 : na > nb ? 1 : 0;
      if (state.sortmode === 'za') return na > nb ? -1 : na < nb ? 1 : 0;
      return 0;
    });
    return arr;
  }
  function setSortmode(m) {
    state.sortmode = m; lsSet('kosha2_sortmode', m);
    if (state.mode === 'search') renderResults();
  }
  function moveDict(slug, toTop) {
    // capture today's visible order, then move — so the first customization
    // starts from what the user is looking at, not from an empty list
    var cur = orderedDicts().map(function (d) { return d.slug; });
    var i = cur.indexOf(slug);
    if (i < 0) return;
    cur.splice(i, 1);
    cur.splice(toTop ? 0 : Math.max(0, i - 1), 0, slug);
    state.order = cur;
    state.sortmode = 'custom';
    lsSet('kosha2_order', state.order); lsSet('kosha2_sortmode', 'custom');
    renderResults(); toast(toTop ? 'Moved to top — saved as your order' : 'Moved up — saved as your order');
  }

  function consensus() {
    var seen = {}, out = [];
    state.perDict.forEach(function (d) {
      (d.items || []).forEach(function (it) {
        (it.senses || []).slice(0, 2).forEach(function (s) {
          var g = String(s.gloss || '').split(/[।॥;·\n]/)[0].trim();
          if (g && g.length <= 34 && !seen[g]) { seen[g] = 1; out.push(g); }
        });
      });
    });
    return out.slice(0, 20);
  }

  // gender / part-of-speech consensus across the dictionaries' own tags
  var POS_CANON = [
    [/पुं|पुल्लिङ्ग|\bm\b|^m\.|पु०/, 'पुं.'],
    [/स्त्री|\bf\b|^f\.|स्त्री०/, 'स्त्री.'],
    [/क्ली|नपुं|\bn\b|^n\.|न०|क्ली०/, 'नपुं.'],
    [/mfn|त्रि|त्रि०/, 'त्रि.'],
    [/ind|अव्य/, 'अव्य.']
  ];
  function genderConsensus() {
    var counts = {};
    function feed(pos) {
      if (!pos) return;
      var s = String(pos);
      POS_CANON.forEach(function (pc) { if (pc[0].test(s)) counts[pc[1]] = (counts[pc[1]] || 0) + 1; });
    }
    state.perDict.forEach(function (d) {
      var er = state.enriched[d.slug];
      if (er) er.forEach(function (rs) { feed(rs.pos); (rs.subs || []).forEach(function (x) { feed(x.pos); }); });
      (d.items || []).forEach(function (it) { (it.senses || []).forEach(function (s) { feed(s.pos); }); });
    });
    return Object.keys(counts).sort(function (a, b) { return counts[b] - counts[a]; })
      .slice(0, 4).map(function (k) { return { g: k, n: counts[k] }; });
  }

  function cardHtml(d) {
    var slug = d.slug, meta = d.meta || {};
    var pinned = state.pins.indexOf(slug) >= 0;
    var tier = visTier(slug);
    var enrichedRows = state.enriched[slug];
    var body = '';
    if (enrichedRows) {
      enrichedRows.forEach(function (row) {
        body += (row.senses_r || []).map(senseHtml).join('');
      });
    } else {
      (d.items || []).forEach(function (it) {
        body += (it.senses || []).map(rawSenseHtml).join('');
      });
    }
    // licensing is a curation detail — it lives in admin/kosha.html (the
    // Kosha Manager), never on the reading page (lead's 3 Sep report)
    var collapsed = state.collapsed.indexOf(slug) >= 0;
    return '<article class="k2-card' + (pinned ? ' pinned' : '') + (collapsed ? ' collapsed' : '') +
      '" id="k2c-' + esc(slug) + '" data-slug="' + esc(slug) + '">' +
      '<header class="k2-chead" data-collapse="' + esc(slug) + '"><div class="k2-mark">' + esc(mark(meta.name)) + '</div>' +
      '<div class="k2-cname"><h2>' + (pinned ? '★ ' : '') + esc(meta.name || slug) + '</h2>' +
      '<div class="k2-cmeta"><span class="k2-lang">' + esc(LANG_NAME[meta.gloss_language] || meta.gloss_language || '') + '</span>' +
      (tier !== 'public' && state.superadmin ? '<span>· ' + esc(tier) + ' (admin view)</span>' : '') +
      '</div></div>' +
      '<button class="k2-collbtn" data-collapse="' + esc(slug) + '" aria-label="Collapse" title="Collapse / expand">▾</button>' +
      '<div class="k2-cmenu"><button data-menu="' + esc(slug) + '" aria-label="Actions">⋯</button></div>' +
      '</header><div class="k2-cbody">' + (body || '<div class="k2-empty">—</div>') + '</div></article>';
  }
  function toggleCollapse(slug) {
    var i = state.collapsed.indexOf(slug);
    if (i >= 0) state.collapsed.splice(i, 1); else state.collapsed.push(slug);
    lsSet('kosha2_collapsed', state.collapsed);
    var el = $('#k2c-' + CSS.escape(slug));
    if (el) el.classList.toggle('collapsed', i < 0);
  }

  function renderResults() {
    var main = $('#k2Main');
    if (!state.group) { main.innerHTML = '<div class="k2-empty">कोशं अन्विष्यताम् — search across the dictionaries, or open one from Browse.</div>'; return; }
    var dicts = orderedDicts();
    var langs = {};
    state.perDict.forEach(function (d) { if (allowedAtAll(d.slug)) { var l = d.meta.gloss_language || '?'; langs[l] = (langs[l] || 0) + 1; } });
    var cons = consensus();
    var gen = genderConsensus();
    var hero = '<section class="k2-digest"><div class="k2-kicker">Word at a glance</div>' +
      '<div class="k2-hw" lang="sa">' + esc(state.group.hw) + '</div>' +
      (state.group.slp ? '<div class="k2-roman">' + esc(state.group.slp) + '</div>' : '') +
      (gen.length ? '<div class="k2-gender">' + gen.map(function (g) {
        return '<span class="k2-gchip" title="' + g.n + ' senses">' + esc(g.g) + '<span class="n">' + g.n + '</span></span>';
      }).join('') + '</div>' : '') +
      (cons.length ? '<div class="k2-consensus">' +
        cons.slice(0, state.consMore ? cons.length : 4).map(function (c) { return '<span lang="sa">' + markHits(esc(c)) + '</span>'; }).join('') +
        (cons.length > 4 ? '<button class="k2-morebtn" id="k2ConsMore">' +
          (state.consMore ? 'less' : '+' + (cons.length - 4) + ' more') + '</button>' : '') +
        '</div>' : '') +
      '<div class="k2-digest-meta"><span>' + cons.length + ' भिन्नार्थाः · ' + state.perDict.length + ' कोश</span>' +
      '<span>· <button class="k2-textbtn" id="k2CopyAll">Copy all</button> <button class="k2-textbtn" id="k2Share">Share</button></span></div></section>';
    // language filter lives as ONE compact select in the countline — the
    // old chip row was clutter on mobile (lead's 3 Sep report)
    var lensSel = '<select class="k2-lensel" id="k2LensSel" aria-label="Filter by language">' +
      ['all'].concat(Object.keys(langs).sort()).map(function (l) {
        var label = l === 'all' ? 'All languages' : (LANG_NAME[l] || l);
        var n = l === 'all' ? state.perDict.length : langs[l];
        return '<option value="' + esc(l) + '"' + (state.lens === l ? ' selected' : '') + '>' +
          esc(label) + ' (' + n + ')</option>';
      }).join('') + '</select>';
    // jump rail: one chip per kosha, in display order, scrolls to its card
    var jumpHtml = dicts.length > 1 ? '<div class="k2-jump">' + dicts.map(function (d) {
      var nm = (d.meta.name || d.slug).replace(/\s*\(.*\)$/, '');
      return '<button data-jump="' + esc(d.slug) + '">' +
        (state.pins.indexOf(d.slug) >= 0 ? '★ ' : '') + esc(nm.slice(0, 26)) + '</button>';
    }).join('') + '</div>' : '';
    var count = '<div class="k2-countline"><span>' + dicts.length + ' / ' + state.perDict.length + ' shown' +
      (state.hidden.length ? ' · ' + state.hidden.length + ' hidden by you' : '') + '</span>' +
      lensSel + '</div>';
    main.innerHTML = hero + jumpHtml + count + dicts.map(cardHtml).join('') +
      (dicts.length ? '' : '<div class="k2-empty">No dictionaries match this language filter.</div>');
    bindResults();
    applyScript(main);
  }

  // ---- browse mode --------------------------------------------------------
  function renderBrowsePicker() {
    var main = $('#k2Main');
    E.manifest().then(function (m) {
      var items = Object.keys(m.dictionaries).filter(allowedInBrowseList).sort().map(function (slug) {
        var d = m.dictionaries[slug];
        return '<button data-browse="' + esc(slug) + '"><b>' + esc(d.name || slug) + '</b>' +
          '<span class="m">' + esc(LANG_NAME[d.headword_language] || d.headword_language || '') + ' → ' +
          esc(LANG_NAME[d.gloss_language] || d.gloss_language || '') + ' · ' + (d.headwords || '?') + ' headwords</span></button>';
      }).join('');
      main.innerHTML = '<div class="k2-countline" style="padding-top:12px"><span>Open a kosha and read it in order</span></div>' +
        '<input class="k2-pickfilter" id="k2PickFilter" type="search" ' +
        'placeholder="Filter koshas by name…" aria-label="Filter koshas">' +
        '<div class="k2-browse-pick">' + items + '</div>';
      main.querySelectorAll('[data-browse]').forEach(function (b) {
        b.onclick = function () {
          b.classList.add('loading');           // instant tap feedback
          openBrowse(b.dataset.browse, 0);
        };
      });
      var pf = $('#k2PickFilter');
      pf.oninput = function () {
        var q = pf.value.trim().toLowerCase();
        main.querySelectorAll('[data-browse]').forEach(function (b) {
          b.hidden = q && b.textContent.toLowerCase().indexOf(q) < 0 &&
                     b.dataset.browse.indexOf(q) < 0;
        });
      };
    });
  }
  function openBrowse(slug, page) {
    if (!allowedInBrowseList(slug) && !(state.superadmin || visTier(slug) === 'unlisted')) { toast('This kosha is not browsable'); return; }
    state.browseDict = slug; state.browsePage = page;
    var base = RENDER_BASE || null;
    if (!base) { $('#k2Main').innerHTML = '<div class="k2-empty">Browse needs the enriched index (kosha_r), which is not reachable right now.</div>'; return; }
    // immediate loading state — big dictionaries take a moment on mobile
    if (!$('#k2Main .k2-browse-list')) {
      $('#k2Main').innerHTML = '<div class="k2-empty">लोड भवति… loading ' + esc(slug) + '</div>';
    } else {
      toast('Loading page ' + (page + 1) + '…');
    }
    var iurl = base + '/_browse/' + encodeURIComponent(slug) + '/index.json';
    (browseCache[iurl] ? Promise.resolve(browseCache[iurl]) : fetchJson(iurl).then(function (x) { browseCache[iurl] = x; return x; }))
      .then(function (idx) {
        if (!idx) { $('#k2Main').innerHTML = '<div class="k2-empty">No browse index for this kosha yet.</div>'; return; }
        state.browseIndex = idx;
        var purl = base + '/_browse/' + encodeURIComponent(slug) + '/page-' + page + '.json';
        fetchJson(purl).then(function (rows) {
          rows = rows || [];
          // alphabet rail GROUPED by first akshara — a large dictionary has
          // 1000+ pages, and one button per page froze mobile browsers.
          // One chip per starting letter, jumping to its first page; the
          // chip covering the current page is highlighted.
          var groups = [], seenCh = {};
          idx.first.forEach(function (w, i) {
            var ch = String(w).replace(/^[\s'‘"–-]+/, '').slice(0, 1);
            if (!seenCh[ch]) { seenCh[ch] = 1; groups.push({ ch: ch, page: i }); }
          });
          // rail chips in alphabet order, not page-encounter order — some
          // sources are not strictly sorted, and the encounter order read
          // as a jumbled alphabet (the आ भ ध… report, 3 Sep 2026). Unicode
          // order IS varnamala order within Devanagari (and A–Z for Latin).
          groups.sort(function (a, b) { return a.ch < b.ch ? -1 : a.ch > b.ch ? 1 : 0; });
          // highlight the chip whose section the current page sits in,
          // by page distance (chips no longer ascend by page)
          var curGroup = -1, best = -1;
          groups.forEach(function (g, gi) {
            if (g.page <= page && g.page >= best) { best = g.page; curGroup = gi; }
          });
          var alpha = groups.map(function (g, gi) {
            return '<button class="' + (gi === curGroup ? 'active' : '') +
              '" data-bpage="' + g.page + '" title="from page ' + (g.page + 1) +
              '" lang="sa">' + esc(g.ch) + '</button>';
          }).join('');
          $('#k2Main').innerHTML =
            '<div class="k2-countline" style="padding-top:12px"><span><button class="k2-textbtn" id="k2BrowseBack">← All koshas</button> ' +
            esc(slug) + ' · ' + idx.entries + ' headwords · page ' + (page + 1) + '/' + idx.pages + '</span>' +
            '<span class="k2-pagebtns">' +
            (page > 0 ? '<button class="k2-textbtn" data-bpage="' + (page - 1) + '">‹ Prev</button>' : '') +
            (page < idx.pages - 1 ? '<button class="k2-textbtn" data-bpage="' + (page + 1) + '">Next ›</button>' : '') +
            '</span></div>' +
            '<div class="k2-alpha">' + alpha + '</div>' +
            '<div class="k2-browse-list">' + rows.map(function (r) {
              return '<button data-lookup="' + esc(r.h) + '">' + esc(r.h) + '</button>';
            }).join('') + '</div>';
          $('#k2BrowseBack').onclick = function () { state.browseDict = null; renderBrowsePicker(); };
          $('#k2Main').querySelectorAll('[data-bpage]').forEach(function (b) {
            b.onclick = function () { openBrowse(slug, parseInt(b.dataset.bpage, 10)); };
          });
          $('#k2Main').querySelectorAll('[data-lookup]').forEach(function (b) {
            b.onclick = function () { setMode('search'); doLookup(b.dataset.lookup); };
          });
          applyScript($('#k2Main'));
        });
      });
  }

  // ---- bottom sheet: the ONE surface for menus and reference popups -------
  // The anchored popover ran past the right edge on mobile; a sheet from the
  // bottom never covers the reading column and always carries ✕ (and ‹ back
  // when it was opened from another sheet). The anchor argument is kept for
  // call-site compatibility but no longer positions anything.
  function popAt(anchor, html, backFn) {
    var pop = $('#k2Pop'), bd = $('#k2Back');
    pop.innerHTML = '<div class="k2-sheet-bar">' +
      (backFn ? '<button id="k2PopBack">‹ back</button>' : '<span></span>') +
      '<button id="k2PopClose" aria-label="Close">✕ close</button></div>' + html;
    applyScript(pop);
    pop.hidden = false; if (bd) bd.hidden = false;
    pop.scrollTop = 0;
    $('#k2PopClose').onclick = closePop;
    var bb = $('#k2PopBack');
    if (bb && backFn) bb.onclick = function () { backFn(); };
  }
  function closePop() {
    $('#k2Pop').hidden = true;
    var bd = $('#k2Back'); if (bd) bd.hidden = true;
  }

  function citePop(anchor, text, q) {
    var gsHref = 'index.html?gs=' + encodeURIComponent(q || text);
    popAt(anchor, '<h4>Citation</h4><div class="body" lang="sa">' + esc(text) + '</div>' +
      '<div class="row">' +
      '<a href="' + gsHref + '">🔎 Search the corpus for this</a>' +
      '<button data-copy="' + esc(text) + '">⧉ Copy citation</button></div>');
  }
  function srcPop(anchor, text) {
    popAt(anchor, '<h4>Source attribution</h4><div class="body" lang="sa">' + esc(text) + '</div>' +
      '<div class="k2-note" style="margin-top:6px">Part of the dictionary\'s own wording — the kosha it cites as its authority.</div>' +
      '<div class="row"><button data-copy="' + esc(text) + '">⧉ Copy</button></div>');
  }
  function cardMenu(anchor, slug) {
    var pinned = state.pins.indexOf(slug) >= 0, hidden = state.hidden.indexOf(slug) >= 0;
    var d = state.perDict.filter(function (x) { return x.slug === slug; })[0];
    popAt(anchor, '<h4>' + esc(d ? d.meta.name : slug) + '</h4><div class="row">' +
      '<button data-act="copy" data-slug="' + esc(slug) + '">⧉ Copy this entry</button>' +
      '<button data-act="link" data-slug="' + esc(slug) + '">🔗 Copy link to this card</button>' +
      '<button data-act="pin" data-slug="' + esc(slug) + '">' + (pinned ? '☆ Unpin' : '★ Pin to top') + '</button>' +
      '<button data-act="hide" data-slug="' + esc(slug) + '">' + (hidden ? '👁 Show' : '🙈 Hide for me') + '</button>' +
      '<button data-act="ai" data-slug="' + esc(slug) + '">✦ Ask AI about this entry…</button>' +
      '</div><div class="k2-note" style="margin-top:6px">Reorder the koshas under ⚙ Settings → Arrange.</div>');
  }
  function aiMenu(anchor, slug) {
    popAt(anchor, '<h4>AI · BYOK Gemini</h4><div class="row">' +
      ['Explain simply', 'Paninian analysis (sutras & derivation)', 'Etymology',
       'Puranic context', 'Usage in texts', 'Translate to ಕನ್ನಡ', 'Translate to English']
        .map(function (a) { return '<button data-ai="' + esc(a) + '" data-slug="' + esc(slug) + '">' + esc(a) + '</button>'; }).join('') +
      '</div><div class="k2-note" style="margin-top:6px">Uses your own Gemini key (⚙ Settings in the reader).</div>',
      function () { cardMenu(null, slug); });
  }

  // ---- vyakarana reference sheets (no page navigation, ever) ---------------
  var vyData = { sutra: null, dhatu: null, unadi: null };
  function sutraById() {
    vyData.sutra = vyData.sutra ||
      fetchJson('data/vedanga/vyakarana/ashtadhyayi/sutrapatha/data.json').then(function (d) {
        var by = {};
        ((d && d.items) || []).forEach(function (it) { by[it.id] = it; });
        return by;
      });
    return vyData.sutra;
  }
  function dhatuItems() {
    vyData.dhatu = vyData.dhatu ||
      fetchJson('data/vedanga/vyakarana/dhatupatha/data.json').then(function (d) {
        return (d && d.items) || [];
      });
    return vyData.dhatu;
  }
  function sutraSheet(id) {
    popAt(null, '<h4>अष्टाध्यायी · ' + esc(id) + '</h4><div class="body">Loading…</div>');
    sutraById().then(function (by) {
      var s = by && by[id];
      popAt(null, '<h4>अष्टाध्यायी · ' + esc(id) + '</h4>' +
        (s ? '<div class="k2-sutra-text" lang="sa">' + esc(s.sanskrit_text || '') + '</div>' +
          (s.padaccheda && s.padaccheda.length ? '<div class="k2-note">पदच्छेदः</div><div class="body" lang="sa">' + esc(s.padaccheda.join(' · ')) + '</div>' : '') +
          (s.anvaya ? '<div class="k2-note" style="margin-top:6px">अन्वयः</div><div class="body" lang="sa">' + esc(s.anvaya) + '</div>' : '')
          : '<div class="body">सूत्रं न लब्धम् (' + esc(id) + ').</div>') +
        '<div class="row">' +
        '<a href="vyakarana/ashtadhyayi.html#' + esc(id) + '">पूर्णसन्दर्भः अष्टाध्यायीपृष्ठे ↗</a>' +
        '<button data-copy="' + esc(s ? s.sanskrit_text + ' (' + id + ')' : id) + '">⧉ Copy</button></div>');
    });
  }
  var COMBINING = /[ऀ-ःऺ-्॑-ॗॢॣ]/;
  function stripSvara(s) { return String(s || '').replace(/[ँॅऀ॒॑॓॔]/g, ''); }
  function dhatuSheet(root, artha) {
    popAt(null, '<h4>धातुः · <span lang="sa">' + esc(root) + '</span></h4><div class="body">Loading…</div>');
    dhatuItems().then(function (items) {
      var r = stripSvara(root);
      var hits = items.filter(function (it) { return stripSvara(it.dhatu) === r; });
      if (!hits.length && artha) {
        hits = items.filter(function (it) { return (it.artha || '').indexOf(artha) >= 0; }).slice(0, 12);
      }
      popAt(null, '<h4>धातुः · <span lang="sa">' + esc(root) + (artha ? ' (' + esc(artha) + ')' : '') + '</span></h4>' +
        (hits.length ? hits.map(function (it) {
          return '<div class="k2-dhatu-row"><b lang="sa">' + esc(it.dhatu) + '</b>' +
            '<span lang="sa">' + esc(it.artha || '') + '</span>' +
            '<span class="g">गण ' + esc(it.gana) + ' · ' + esc(it.pada_code || '') + '</span></div>';
        }).join('') +
          (stripSvara(hits[0].dhatu) !== r ? '<div class="k2-note" style="margin-top:6px">धातुपाठे ‘' + esc(root) + '’ इति रूपं साक्षात् न लब्धम् — समानार्थकाः दर्शिताः।</div>' : '')
          : '<div class="body">धातुपाठे न लब्धः।</div>') +
        '<div class="row"><a href="vyakarana/dhatu.html">धातुपाठपृष्ठं पश्यतु ↗</a>' +
        '<button data-copy="' + esc(root + (artha ? ' (' + artha + ')' : '')) + '">⧉ Copy</button></div>');
    });
  }
  function unadiData() {
    vyData.unadi = vyData.unadi ||
      fetchJson('data/vedanga/vyakarana/unadi/data.json').then(function (d) {
        var by = {};
        ((d && d.items) || []).forEach(function (it) { by[String(it.i)] = it; });
        return by;
      });
    return vyData.unadi;
  }
  var DEVA_DIG = { '०': '0', '१': '1', '२': '2', '३': '3', '४': '4', '५': '5', '६': '6', '७': '7', '८': '8', '९': '9' };
  function unadiSheet(ref) {
    // "४-९८" -> id 4098 (pada*1000 + sutra) in the ashtadhyayi.com corpus
    var ascii = String(ref).replace(/[०-९]/g, function (c) { return DEVA_DIG[c]; });
    var mm = ascii.match(/^(\d)\s*[-–]\s*(\d{1,3})$/);
    var id = mm ? mm[1] + String(+mm[2]).padStart(3, '0') : null;
    popAt(null, '<h4>उणादिसूत्रम् · ' + esc(ref) + '</h4><div class="body">Loading…</div>');
    unadiData().then(function (by) {
      var s = id && by[id];
      popAt(null, '<h4>उणादिसूत्रम् · ' + esc(ref) + '</h4>' +
        (s ? '<div class="k2-sutra-text" lang="sa">' + esc(s.sutra) + '</div>' +
          (s.pratyay ? '<div class="k2-note">प्रत्ययः</div><div class="body" lang="sa">' + esc(s.pratyay) + '</div>' : '') +
          (s.sk ? '<div class="k2-note" style="margin-top:6px">वृत्तिः</div><div class="body" lang="sa">' + esc(s.sk).replace(/\[\[(\d+\.\d+\.\d+)\]\]/g, '<button class="k2-ref sutra" data-sutra="$1">$1</button>') + '</div>' : '')
          : '<div class="body" lang="sa">इदं सूत्रं उणादिपाठे न लब्धम् (' + esc(ref) + ').</div>') +
        '<div class="k2-note" style="margin-top:6px">उणादिपाठः · <a href="vyakarana/unadi.html" style="color:inherit">पूर्णसूची ↗</a></div>' +
        '<div class="row"><button data-copy="' + esc('उ० ' + ref + (s ? ' ' + s.sutra : '')) + '">⧉ Copy</button></div>');
      var pop = $('#k2Pop');
      pop.querySelectorAll('[data-sutra]').forEach(function (b) {
        b.onclick = function (e) { e.stopPropagation(); sutraSheet(b.dataset.sutra); };
      });
    });
  }
  // ---- ⚙ sheet: everything that is not content lives here -----------------
  function dictName(slug) {
    var d = state.perDict.filter(function (x) { return x.slug === slug; })[0];
    return d ? (d.meta.name || slug) : slug;
  }
  function cfgSheet(anchor) {
    var hist = state.history.slice(0, 10);
    var html = '<h4>कोश · Settings</h4>' +
      '<div class="k2-note">Display script</div><div class="row">' +
      [['deva', 'देवनागरी'], ['iast', 'IAST'], ['knda', 'ಕನ್ನಡ']].map(function (p) {
        return '<button data-cscript="' + p[0] + '"' + (state.script === p[0] ? ' class="on"' : '') + '>' + p[1] + '</button>';
      }).join('') + '</div>' +
      '<div class="k2-note" style="margin-top:8px">Kosha order (pins always first)</div><div class="row">' +
      [['curated', 'Default'], ['az', 'A–Z'], ['za', 'Z–A']]
        .concat(state.order.length ? [['custom', 'My order']] : [])
        .map(function (p) {
          return '<button data-csort="' + p[0] + '"' + (state.sortmode === p[0] ? ' class="on"' : '') + '>' + p[1] + '</button>';
        }).join('') +
      (state.order.length ? '<button data-csortreset="1" title="Forget my hand-arranged order">✕ reset my order</button>' : '') +
      '</div>' +
      (hist.length ? '<div class="k2-note" style="margin-top:8px">Recent lookups</div><div class="row">' +
        hist.map(function (h) { return '<button data-hist="' + esc(h) + '" lang="sa">' + esc(h) + '</button>'; }).join('') +
        '<button data-histclear="1" title="Clear history">✕ clear</button></div>' : '') +
      (state.pins.length ? '<div class="k2-note" style="margin-top:8px">Pinned to top</div><div class="row">' +
        state.pins.map(function (s) { return '<button data-unpin="' + esc(s) + '" title="Unpin">★ ' + esc(dictName(s)).slice(0, 24) + ' ✕</button>'; }).join('') + '</div>' : '') +
      (state.hidden.length ? '<div class="k2-note" style="margin-top:8px">Hidden by you</div><div class="row">' +
        state.hidden.map(function (s) { return '<button data-unhide="' + esc(s) + '" title="Show again">🙈 ' + esc(dictName(s)).slice(0, 24) + ' ✕</button>'; }).join('') + '</div>' : '') +
      (state.group ? '<div class="k2-note" style="margin-top:8px">Arrange — ↑ one up · ⇱ to top (saved as My order)</div>' +
        orderedDicts().map(function (d) {
          return '<div class="k2-arr-row"><span>' + esc(d.meta.name || d.slug) + '</span>' +
            '<button data-arrup="' + esc(d.slug) + '" aria-label="Move up">↑</button>' +
            '<button data-arrtop="' + esc(d.slug) + '" aria-label="Move to top">⇱</button></div>';
        }).join('') : '') +
      (state.superadmin ? '<div class="k2-note" style="margin-top:8px"><a href="../admin/kosha.html" style="color:inherit">Kosha Manager → committed tiers & pins</a></div>' : '');
    popAt(anchor, html);
    var pop = $('#k2Pop');
    pop.querySelectorAll('[data-cscript]').forEach(function (b) {
      b.onclick = function () { setScript(b.dataset.cscript); closePop(); };
    });
    pop.querySelectorAll('[data-csort]').forEach(function (b) {
      b.onclick = function () { setSortmode(b.dataset.csort); closePop(); toast('Kosha order: ' + b.textContent); };
    });
    var sr = pop.querySelector('[data-csortreset]');
    if (sr) sr.onclick = function () {
      state.order = []; lsSet('kosha2_order', []);
      if (state.sortmode === 'custom') setSortmode('curated'); else renderResults();
      closePop(); toast('Your hand-arranged order was reset');
    };
    pop.querySelectorAll('[data-hist]').forEach(function (b) {
      b.onclick = function () { closePop(); setMode('search'); doLookup(b.dataset.hist); };
    });
    var hc = pop.querySelector('[data-histclear]');
    if (hc) hc.onclick = function () { state.history = []; lsSet('kosha2_history', []); closePop(); toast('History cleared'); };
    pop.querySelectorAll('[data-unpin]').forEach(function (b) {
      b.onclick = function () { togglePin(b.dataset.unpin); closePop(); };
    });
    pop.querySelectorAll('[data-unhide]').forEach(function (b) {
      b.onclick = function () { toggleHide(b.dataset.unhide); closePop(); };
    });
    pop.querySelectorAll('[data-arrup]').forEach(function (b) {
      b.onclick = function (e) { e.stopPropagation(); moveDict(b.dataset.arrup, false); cfgSheet(anchor); };
    });
    pop.querySelectorAll('[data-arrtop]').forEach(function (b) {
      b.onclick = function (e) { e.stopPropagation(); moveDict(b.dataset.arrtop, true); cfgSheet(anchor); };
    });
  }

  function runAi(slug, action) {
    var d = state.perDict.filter(function (x) { return x.slug === slug; })[0];
    var gloss = d ? (d.items || []).map(function (it) { return (it.senses || []).map(function (s) { return s.gloss; }).join('\n'); }).join('\n') : '';
    var key = localStorage.getItem('gemini_api_key');
    if (!key) { toast('Add a Gemini key in the reader (⚙ Settings) first'); return; }
    if (!window.DGEGemini) { toast('Gemini client not loaded'); return; }
    toast('Asking…');
    window.DGEGemini.generate({
      prompt: action + ' — for the Sanskrit word ' + (state.group ? state.group.hw : '') +
        ' as defined in ' + (d ? d.meta.name : slug) + ':\n\n' + gloss.slice(0, 4000),
      apiKey: key, model: localStorage.getItem('gemini_model') || undefined
    }).then(function (r) {
      if (!r.ok) { toast(r.error && r.error.title || 'AI error'); return; }
      popAt($('#k2c-' + slug) ? $('#k2c-' + slug).querySelector('[data-menu]') : document.body,
        '<h4>AI · ' + esc(action) + '</h4><div class="body">' + esc((r.text || '').slice(0, 1200)) + '</div>' +
        '<div class="row"><button data-copy="' + esc(r.text || '') + '">⧉ Copy answer</button></div>');
    }).catch(function (e) { toast(String(e && e.message || e).slice(0, 80)); });
  }

  function cardText(slug) {
    var el = $('#k2c-' + CSS.escape(slug));
    return el ? (state.group.hw + ' — ' + el.innerText.replace(/\s+\n/g, '\n').trim()) : '';
  }
  function pageText() {
    return state.group ? (state.group.hw + '\n' +
      orderedDicts().map(function (d) { return '\n== ' + d.meta.name + ' ==\n' + cardText(d.slug).replace(/^[^\n]*\n?/, ''); }).join('\n')) : '';
  }
  function copyText(t, msg) {
    (navigator.clipboard ? navigator.clipboard.writeText(t) : Promise.reject())
      .then(function () { toast(msg || 'Copied'); })
      .catch(function () { toast('Copy failed'); });
  }

  // ---- events -------------------------------------------------------------
  function bindResults() {
    var ls = $('#k2LensSel');
    if (ls) ls.onchange = function () { state.lens = ls.value; renderResults(); };
    var cm = $('#k2ConsMore');
    if (cm) cm.onclick = function () { state.consMore = !state.consMore; renderResults(); };
    $('#k2Main').querySelectorAll('[data-collapse]').forEach(function (b) {
      b.onclick = function (e) {
        // the ⋯ menu button sits inside the header; don't collapse for it
        if (e.target.closest('[data-menu]')) return;
        e.stopPropagation();
        toggleCollapse(b.dataset.collapse || b.closest('[data-slug]').dataset.slug);
      };
    });
    $('#k2Main').querySelectorAll('[data-sutra]').forEach(function (b) {
      b.onclick = function (e) { e.stopPropagation(); sutraSheet(b.dataset.sutra); };
    });
    $('#k2Main').querySelectorAll('[data-dhatu]').forEach(function (b) {
      b.onclick = function (e) { e.stopPropagation(); dhatuSheet(b.dataset.dhatu, b.dataset.artha); };
    });
    $('#k2Main').querySelectorAll('[data-unadi]').forEach(function (b) {
      b.onclick = function (e) { e.stopPropagation(); unadiSheet(b.dataset.unadi); };
    });
    $('#k2Main').querySelectorAll('[data-lens]').forEach(function (b) {
      b.onclick = function () { state.lens = b.dataset.lens; renderResults(); };
    });
    $('#k2Main').querySelectorAll('[data-menu]').forEach(function (b) {
      b.onclick = function (e) { e.stopPropagation(); cardMenu(b, b.dataset.menu); };
    });
    $('#k2Main').querySelectorAll('[data-cite]').forEach(function (b) {
      b.onclick = function (e) { e.stopPropagation(); citePop(b, b.dataset.cite, b.dataset.q); };
    });
    $('#k2Main').querySelectorAll('[data-src]').forEach(function (b) {
      b.onclick = function (e) { e.stopPropagation(); srcPop(b, b.dataset.src); };
    });
    $('#k2Main').querySelectorAll('.k2-syn[data-lookup]').forEach(function (b) {
      b.onclick = function () { doLookup(b.dataset.lookup); };
    });
    $('#k2Main').querySelectorAll('[data-jump]').forEach(function (b) {
      b.onclick = function () {
        var el = $('#k2c-' + CSS.escape(b.dataset.jump));
        if (el) el.scrollIntoView({ block: 'start', behavior: 'smooth' });
      };
    });
    var ca = $('#k2CopyAll'); if (ca) ca.onclick = function () { copyText(pageText(), 'All results copied'); };
    var sh = $('#k2Share'); if (sh) sh.onclick = function () {
      var url = location.href.split('#')[0] + '#word=' + encodeURIComponent(state.group.hw);
      if (navigator.share) navigator.share({ title: 'DGE कोश — ' + state.group.hw, url: url }).catch(function () {});
      else copyText(url, 'Link copied');
    };
  }

  document.addEventListener('click', function (e) {
    var t = e.target.closest ? e.target.closest('[data-copy],[data-act],[data-ai]') : null;
    if (t && t.dataset.copy !== undefined && t.dataset.copy !== '') { copyText(t.dataset.copy); closePop(); return; }
    if (t && t.dataset.act) {
      var slug = t.dataset.slug;
      if (t.dataset.act === 'copy') copyText(cardText(slug), 'Entry copied');
      else if (t.dataset.act === 'link') copyText(location.href.split('#')[0] + '#word=' + encodeURIComponent(state.group.hw) + '&kosha=' + slug, 'Link copied');
      else if (t.dataset.act === 'pin') { togglePin(slug); }
      else if (t.dataset.act === 'hide') { toggleHide(slug); }
      else if (t.dataset.act === 'up') { moveDict(slug, false); }
      else if (t.dataset.act === 'top') { moveDict(slug, true); }
      else if (t.dataset.act === 'ai') { aiMenu(t, slug); return; }
      closePop(); return;
    }
    if (t && t.dataset.ai) { closePop(); runAi(t.dataset.slug, t.dataset.ai); return; }
    if (!e.target.closest || (!e.target.closest('#k2Pop') && !e.target.closest('[data-menu]') && !e.target.closest('[data-cite]') && !e.target.closest('[data-src]'))) closePop();
  });

  function togglePin(slug) {
    var i = state.pins.indexOf(slug);
    if (i >= 0) state.pins.splice(i, 1); else state.pins.unshift(slug);
    lsSet('kosha2_pins', state.pins); renderResults();
  }
  function toggleHide(slug) {
    var i = state.hidden.indexOf(slug);
    if (i >= 0) state.hidden.splice(i, 1); else state.hidden.push(slug);
    lsSet('kosha2_hidden', state.hidden); renderResults();
  }

  // ---- lookup flow --------------------------------------------------------
  var seq = 0;
  function doLookup(word, jumpSlug) {
    var mine = ++seq;
    state.query = word;
    $('#k2Input').value = word;
    $('#k2Sug').hidden = true;
    $('#k2Main').innerHTML = '<div class="k2-empty">अन्वेषणम्…</div>';
    E.search(word).catch(function (e) {
      if (mine !== seq) return null;
      $('#k2Main').innerHTML = '<div class="k2-empty">Search could not reach the dictionary index (' +
        esc(String(e && e.message || e).slice(0, 80)) + '). Check the connection and try again.</div>';
      return null;
    }).then(function (r) {
      if (!r) return;
      if (mine !== seq) return;
      if (!r.list.length) { state.group = null; $('#k2Main').innerHTML = '<div class="k2-empty">No headword found for “' + esc(word) + '”.</div>'; return; }
      if (r.degraded) toast('A part of the index did not load — results may be incomplete. Retry in a moment.');
      var g = r.list[0];
      state.group = { hw: g.hw, slp: Object.keys(g.slps || {})[0] || '', raw: g };
      pushHistory(g.hw);
      history.replaceState(null, '', '#word=' + encodeURIComponent(g.hw));
      E.loadEntry(g).then(function (perDict) {
        if (mine !== seq) return;
        state.perDict = perDict.filter(function (d) { return allowedInSearch(d.slug) || (state.superadmin && allowedAtAll(d.slug)); });
        state.enriched = {};
        renderResults();
        // enriched twins arrive per dictionary and upgrade cards in place
        state.perDict.forEach(function (d) {
          var m0 = (g.members || []).filter(function (m) { return m.d === d.slug; })[0];
          if (!m0) return;
          var efold = m0.f || m0.fold, ehw = m0.w || m0.h;
          enrichedFor(d.slug, efold, ehw).then(function (rows) {
            if (mine !== seq || !rows) return;
            state.enriched[d.slug] = rows;
            renderResults();
            if (jumpSlug) { var el = $('#k2c-' + CSS.escape(jumpSlug)); if (el) el.scrollIntoView({ block: 'start' }); }
          });
        });
        if (jumpSlug) { var el = $('#k2c-' + CSS.escape(jumpSlug)); if (el) el.scrollIntoView({ block: 'start' }); }
      });
    });
  }

  var sugSeq = 0;   // bumped by Enter/blur so a late debounce can't re-open
  function renderSug(q) {
    var box = $('#k2Sug'), mySeq = sugSeq;
    if (!q.trim()) { box.hidden = true; return; }
    E.search(q).then(function (r) {
      if (mySeq !== sugSeq || $('#k2Input').value !== q) return;
      if (!r.list.length) { box.innerHTML = '<div class="k2-empty" style="padding:14px">No matches yet…</div>'; box.hidden = false; return; }
      box.innerHTML = r.list.slice(0, 9).map(function (g) {
        return '<button data-key="' + esc(g.hw) + '"><span class="w" lang="sa">' + esc(g.hw) + '</span>' +
          '<span class="m">' + g.dictCount + ' कोश</span></button>';
      }).join('');
      box.hidden = false;
      box.querySelectorAll('[data-key]').forEach(function (b) {
        b.onclick = function () { doLookup(b.dataset.key); };
      });
    }).catch(function () {
      // suggestions are best-effort; an unreachable index just closes the box
      if (mySeq === sugSeq) box.hidden = true;
    });
  }

  function setMode(mode) {
    state.mode = mode;
    document.querySelectorAll('#k2Mode button').forEach(function (b) { b.classList.toggle('active', b.dataset.mode === mode); });
    var input = $('#k2Input');
    if (input) input.placeholder = mode === 'gloss'
      ? 'Search inside the meanings… (महाभारते, चन्द्र)'
      : 'Search Sanskrit, IAST, Kannada… (अब्ज, abja, ಅಬ್ಜ)';
    if (mode === 'browse') { state.browseDict ? openBrowse(state.browseDict, state.browsePage) : renderBrowsePicker(); }
    else if (mode === 'gloss') {
      $('#k2Main').innerHTML = '<div class="k2-empty" lang="sa">अर्थेषु अन्वेषणम् — type a word to find every ' +
        'headword whose MEANING mentions it (e.g. महाभारते), then press Enter.</div>';
    }
    else if (state.group) renderResults();
    else $('#k2Main').innerHTML = '<div class="k2-empty">कोशं अन्विष्यताम् — search across the dictionaries, or open one from Browse.</div>';
  }

  // ---- search inside the meanings (gloss index) ---------------------------
  var glossSeq = 0;
  function doGlossSearch(q) {
    q = (q || '').trim();
    if (!q) return;
    var mine = ++glossSeq;
    $('#k2Sug').hidden = true;
    $('#k2Main').innerHTML = '<div class="k2-empty">अर्थेषु अन्वेषणम्…</div>';
    E.glossSearch(q).then(function (r) {
      if (mine !== glossSeq) return;
      if (!r || !r.hits || !r.hits.length) {
        $('#k2Main').innerHTML = '<div class="k2-empty">No meanings mention “' + esc(q) + '”.</div>';
        return;
      }
      var byDict = {};
      r.hits.forEach(function (h) { (byDict[h.d] = byDict[h.d] || []).push(h); });
      var total = r.hits.length;
      $('#k2Main').innerHTML =
        '<div class="k2-countline" style="padding-top:12px"><span>“' + esc(q) + '” appears in the meanings of ' +
        total + ' headword-entr' + (total === 1 ? 'y' : 'ies') + ' across ' + Object.keys(byDict).length + ' कोश' +
        (r.truncated ? ' (first ' + total + ')' : '') + '</span></div>' +
        Object.keys(byDict).sort().map(function (slug) {
          var rows = byDict[slug];
          return '<div class="k2-gloss-dict">' + esc(dictName(slug)) + ' <span class="n">' + rows.length + '</span></div>' +
            '<div class="k2-gloss-hits">' + rows.map(function (h) {
              return '<button data-glookup="' + esc(h.h) + '" lang="sa">' + esc(h.h) +
                (h.n > 1 ? '<span class="n">×' + h.n + '</span>' : '') + '</button>';
            }).join('') + '</div>';
        }).join('');
      $('#k2Main').querySelectorAll('[data-glookup]').forEach(function (b) {
        b.onclick = function () { setMode('search'); doLookup(b.dataset.glookup); };
      });
      applyScript($('#k2Main'));
    }).catch(function (e) {
      if (mine !== glossSeq) return;
      var msg = String(e && e.message || e);
      $('#k2Main').innerHTML = '<div class="k2-empty">' +
        (msg.indexOf('not built') >= 0
          ? 'The meaning-search index is being built — this feature lights up as soon as it is published.'
          : 'Meaning-search could not reach its index (' + esc(msg.slice(0, 80)) + '). Try again.') + '</div>';
    });
  }

  // ---- boot ---------------------------------------------------------------
  function boot() {
    try { state.superadmin = localStorage.getItem('is_superadmin') === 'true' || localStorage.getItem('dge.admin.ok') === '1'; } catch (e) {}
    fetchJson('../admin/config/kosha-overrides.json').then(function (ov) {
      if (ov) state.overrides = Object.assign(state.overrides, ov);
      var input = $('#k2Input'), t;
      input.oninput = function () {
        clearTimeout(t);
        if (state.mode === 'gloss') return;   // no headword suggestions there
        var q = input.value; t = setTimeout(function () { renderSug(q); }, 140);
      };
      input.onkeydown = function (e) {
        if (e.key === 'Enter') {
          clearTimeout(t); sugSeq++;
          if (state.mode === 'gloss') { doGlossSearch(input.value); return; }
          var first = $('#k2Sug [data-key]'); if (first) doLookup(first.dataset.key); else doLookup(input.value);
        }
        if (e.key === 'Escape') { clearTimeout(t); sugSeq++; $('#k2Sug').hidden = true; }
      };
      // tapping anywhere in the results must not leave suggestions floating
      input.addEventListener('blur', function () {
        setTimeout(function () { sugSeq++; $('#k2Sug').hidden = true; }, 160);
      });
      $('#k2Clear').onclick = function () { input.value = ''; $('#k2Sug').hidden = true; input.focus(); };
      document.querySelectorAll('#k2Mode button').forEach(function (b) { b.onclick = function () { setMode(b.dataset.mode); }; });
      document.querySelectorAll('#k2Script button').forEach(function (b) {
        b.classList.toggle('active', b.dataset.script === state.script);
        b.onclick = function () { setScript(b.dataset.script); };
      });
      var cfg = $('#k2Cfg'); if (cfg) cfg.onclick = function (e) { e.stopPropagation(); cfgSheet(cfg); };
      var m = location.hash.match(/word=([^&]+)/);
      var k = location.hash.match(/kosha=([^&]+)/);
      var br = location.search.match(/[?&]browse=([^&]+)/);
      if (br) { setMode('browse'); openBrowse(decodeURIComponent(br[1]), 0); }
      else if (m) doLookup(decodeURIComponent(m[1]), k ? decodeURIComponent(k[1]) : null);
      else setMode('search');
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
