/* vyakarana-corpus.js — ONE viewer for the small sutra-corpora imported
   from ashtadhyayi.com (phitsutra / ganapatha / linganushasana / unadi).
   Each page sets window.CORPUS before loading this file; the corpus config
   below decides columns, filters and search fields. Multi-script display
   (Devanagari / IAST / Kannada) via Sanscript when the CDN is reachable —
   the toggle hides itself otherwise, Devanagari always works.
   Attribution: every data.json carries the source metadata written by
   tools/vyakarana/import_ashtadhyayi_corpora.py; renderFooterCredit()
   prints it at the bottom of the page. */
(function () {
  'use strict';
  window.DGE_VERSIONS = window.DGE_VERSIONS || {};
  window.DGE_VERSIONS['vyakarana-corpus.js'] =
    'v1.0 (shared corpus viewer: search by number/keyword, per-corpus filters, multi-script, sutra cross-links, source attribution footer)';

  var CFG = {
    phitsutra: {
      title: 'फिट्सूत्राणि',
      sub: 'Śāntanava\'s accent (svara) rules for the phiṭ (ready-made stems) — sūtra, pāda numbering, and the traditional gloss.',
      num: function (it) { return it.p + '.' + it.n; },
      main: function (it) { return it.s; },
      gloss: function (it) { return it.sk; },
      filters: function (items) {
        return { label: 'पादः', vals: uniq(items.map(function (i) { return i.p; })) };
      },
      matchFilter: function (it, v) { return it.p === v; },
    },
    ganapatha: {
      title: 'गणपाठः',
      sub: 'The gaṇas of the Aṣṭādhyāyī — headword, the sūtra that invokes the gaṇa, and every member word.',
      num: function (it) { return String(it.ind); },
      main: function (it) { return it.name; },
      badge: function (it) { return it.sutra || ''; },
      gloss: function (it) {
        var w = it.words || '';
        return w + (it.vartika ? '\nवार्तिकम्: ' + it.vartika : '');
      },
      filters: function () { return null; },
    },
    linganushasana: {
      title: 'लिङ्गानुशासनम्',
      sub: 'Pāṇinian gender rules, adhikāra-wise — strīliṅga, puṁliṅga, napuṁsaka, and the mixed sections.',
      num: function (it) { return String(it.id); },
      main: function (it) { return it.sutra; },
      badge: function (it) { return it.adhikaar || ''; },
      gloss: function (it) { return it.sk; },
      filters: function (items) {
        return { label: 'अधिकारः', vals: uniq(items.map(function (i) { return i.adhikaar; }).filter(Boolean)) };
      },
      matchFilter: function (it, v) { return it.adhikaar === v; },
    },
    unadi: {
      title: 'उणादिसूत्राणि',
      sub: 'The Uṇādi-sūtras — sūtra, the pratyaya it teaches, and the vṛtti. Numbered pāda.sūtra (उ० ४-९८ = 4.98).',
      num: function (it) { var s = String(it.i); return s[0] + '.' + String(+s.slice(1)); },
      main: function (it) { return it.sutra; },
      badge: function (it) { return it.pratyay || ''; },
      gloss: function (it) { return it.sk; },
      filters: function (items) {
        return { label: 'पादः', vals: uniq(items.map(function (i) { return String(i.i)[0]; })) };
      },
      matchFilter: function (it, v) { return String(it.i)[0] === v; },
    }
  };

  function uniq(a) {
    var s = {}, out = [];
    a.forEach(function (x) { if (x != null && !s[x]) { s[x] = 1; out.push(x); } });
    return out;
  }
  var esc = function (s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
      return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c];
    });
  };
  var $ = function (s) { return document.querySelector(s); };

  var corpus = window.CORPUS, cfg = CFG[corpus];
  var DATA = null, filterVal = '', q = '', script = 'deva';

  // <<sutra text>> spans (ganapatha, unadi vrittis) and [[7.3.33]] refs
  function linkifyRefs(escaped) {
    escaped = escaped.replace(/\[\[(\d+\.\d+\.\d+)\]\]/g,
      '<a class="vc-sutra" href="ashtadhyayi.html#$1" title="अष्टाध्यायी $1">$1</a>');
    escaped = escaped.replace(/&lt;&lt;\s*([^&]*?)\s*&gt;&gt;/g,
      '<span class="vc-quote" title="quoted sutra / gana-sutra">$1</span>');
    return escaped;
  }

  function xlit(s) {
    if (script === 'deva' || !window.Sanscript) return s;
    try {
      return s.replace(/[ऀ-ॿ][ऀ-ॿ‌‍]*/g, function (run) {
        return window.Sanscript.t(run, 'devanagari', script === 'iast' ? 'iast' : 'kannada');
      });
    } catch (e) { return s; }
  }

  function render() {
    var out = $('#vc-list');
    if (!DATA) { out.innerHTML = '<div class="df-note">Loading…</div>'; return; }
    var items = DATA.items;
    if (filterVal && cfg.matchFilter) items = items.filter(function (it) { return cfg.matchFilter(it, filterVal); });
    var ql = q.toLowerCase().trim();
    if (ql) {
      items = items.filter(function (it) {
        return (cfg.num(it) + ' ' + cfg.main(it) + ' ' + (cfg.badge ? cfg.badge(it) : '') + ' ' +
          (cfg.gloss(it) || '')).toLowerCase().indexOf(ql) >= 0;
      });
    }
    $('#vc-count').textContent = items.length + ' / ' + DATA.items.length;
    out.innerHTML = items.map(function (it) {
      var gloss = cfg.gloss(it);
      return '<section class="rs-box vc-item">' +
        '<div class="vc-head"><span class="vc-num">' + esc(cfg.num(it)) + '</span>' +
        '<span class="vc-main deva">' + linkifyRefs(esc(xlit(cfg.main(it)))) + '</span>' +
        (cfg.badge && cfg.badge(it) ? '<span class="vc-badge deva">' + esc(xlit(cfg.badge(it))) + '</span>' : '') +
        '</div>' +
        (gloss ? '<div class="vc-gloss deva">' + linkifyRefs(esc(xlit(gloss))).replace(/\n/g, '<br>') + '</div>' : '') +
        '</section>';
    }).join('') || '<div class="df-note">न किमपि लब्धम् — nothing matched.</div>';
  }

  function boot() {
    var themeBtn = $('#themeBtn');
    if (localStorage.getItem('dge_vyakarana_dark') === '1') document.body.classList.add('dark');
    if (themeBtn) themeBtn.addEventListener('click', function () {
      var dark = document.body.classList.toggle('dark');
      localStorage.setItem('dge_vyakarana_dark', dark ? '1' : '0');
    });
    $('#vc-q').addEventListener('input', function () { q = this.value; render(); });
    document.querySelectorAll('[data-script]').forEach(function (b) {
      b.addEventListener('click', function () {
        script = b.dataset.script;
        document.querySelectorAll('[data-script]').forEach(function (x) { x.classList.toggle('on', x === b); });
        render();
      });
    });
    if (!window.Sanscript) {
      var sw = $('#vc-scripts'); if (sw) sw.style.display = 'none';
    }
    fetch('../data/vedanga/vyakarana/' + corpus + '/data.json')
      .then(function (r) { return r.json(); })
      .then(function (d) {
        DATA = d;
        var f = cfg.filters(d.items);
        if (f) {
          $('#vc-filters').innerHTML = '<span class="df-note">' + esc(f.label) + ':</span>' +
            '<button class="chip on" data-f="">सर्वे</button>' +
            f.vals.map(function (v) { return '<button class="chip deva" data-f="' + esc(v) + '">' + esc(v) + '</button>'; }).join('');
          document.querySelectorAll('[data-f]').forEach(function (b) {
            b.addEventListener('click', function () {
              filterVal = b.dataset.f;
              document.querySelectorAll('[data-f]').forEach(function (x) { x.classList.toggle('on', x === b); });
              render();
            });
          });
        }
        // 9 Sep 2026, the lead: third-party names belong on the Credits
        // page, not on every page that happens to use their data. A source
        // the DATA itself names still shows -- that is this text's own
        // provenance, which a reader of that text needs.
        var at = d.attribution || {};
        $('#vc-credit').innerHTML = (at.source_url && at.source_name
          ? 'स्रोतः: <a href="' + esc(at.source_url) + '" target="_blank" rel="noopener">' + esc(at.source_name) + '</a>'
          : '') +
          (at.accessed_date ? ' · accessed ' + esc(at.accessed_date) : '') +
          (at.license_notes ? ' · ' + esc(at.license_notes) : '');
        render();
      })
      .catch(function () {
        $('#vc-list').innerHTML = '<div class="df-note">Corpus data not reachable — serve from the dge/ folder.</div>';
      });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
