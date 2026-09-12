// dge/js/shabda-gen.js — नूतनशब्दरूपाणि: a declension table for ANY prātipadika.
//
// The Śabdapāṭha is a fixed list of 9,007 words. A reader (or the reader's
// own word-tool) meets a stem that is not on it — a name, a rare noun, a
// compound — and until now stopped at "not found". This section derives all
// 24 cells with the same Pāṇinian engine subanta-steps.js already uses for
// per-cell रूपसिद्धिः (vidyut-prakriya, WASM, in the browser), shows the
// table in the Śabdapāṭha's own layout, opens the sūtra-by-sūtra derivation
// of any cell on tap, and names the closest listed paradigm (same liṅga,
// same ending — like राम, like नदी) so the analogy a student would reach
// for is one tap away. Results are cached per device.
//
//   URL: shabda.html?gen=<stem>&l=P|S|N   (the word-tools link here)
(function () {
  'use strict';
  var LINGA_D = { P: 'पुंल्लिङ्गम्', S: 'स्त्रीलिङ्गम्', N: 'नपुंसकलिङ्गम्' };
  var VIBHAKTI = ['प्रथमा', 'द्वितीया', 'तृतीया', 'चतुर्थी', 'पञ्चमी', 'षष्ठी', 'सप्तमी', 'सम्बोधनम्'];
  // Exemplars the tradition itself teaches by: one per (liṅga, ending) where one is on the list.
  var EXEMPLARS = { 'P:a': 'राम', 'P:i': 'हरि', 'P:u': 'गुरु', 'P:f': 'पितृ', 'P:I': 'सुधी', 'P:U': 'खलपू',
    'S:A': 'रमा', 'S:i': 'मति', 'S:I': 'नदी', 'S:u': 'धेनु', 'S:U': 'वधू', 'S:f': 'मातृ',
    'N:a': 'फल', 'N:i': 'वारि', 'N:u': 'मधु', 'N:f': 'कर्तृ' };
  var S = { stem: '', linga: 'P', cells: null, results: null };

  function $(s) { return document.querySelector(s); }
  function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;'); }
  function antaOf(w) { return (window.DGEShabda && window.DGEShabda.antaOf) ? window.DGEShabda.antaOf(w) : ''; }
  function cacheKey(stem, l) { return 'dge_sg:' + l + ':' + stem; }

  function tableHtml(cells, stem) {
    var h = '<div class="df-table"><table><thead><tr><th></th><th class="deva">एकवचनम्</th><th class="deva">द्विवचनम्</th><th class="deva">बहुवचनम्</th></tr></thead><tbody>';
    for (var v = 0; v < 8; v++) {
      h += '<tr><th class="deva">' + VIBHAKTI[v] + '</th>';
      for (var n = 0; n < 3; n++) {
        var idx = v * 3 + n, txt = cells[idx] || '';
        h += '<td class="deva' + (txt ? ' sst-cell-hint' : '') + '"' + (txt ? ' data-sg-ci="' + idx + '" title="रूपसिद्धिः — tap for the derivation"' : '') + '>' +
          (txt ? esc(txt).replace(/-/g, ', ') : '<span class="muted">—</span>') + '</td>';
      }
      h += '</tr>';
    }
    return h + '</tbody></table></div>';
  }

  function exemplarHtml(stem, linga) {
    var anta = antaOf(stem);
    var ex = EXEMPLARS[linga + ':' + anta];
    var all = (window.DGEShabda && window.DGEShabda.all) ? window.DGEShabda.all() : [];
    var hit = null;
    if (all.length) {
      var exact = all.filter(function (it) { return it.word === stem && it.linga === linga; })[0];
      if (exact) return '<div class="sg-note">This word is already in the Śabdapāṭha — <a href="#' + esc(exact.id) + '">open its listed table</a>; the generated one below is the engine\'s own derivation for comparison.</div>';
      hit = ex ? all.filter(function (it) { return it.word === ex && it.linga === linga; })[0] : null;
      if (!hit) hit = all.filter(function (it) { return it.linga === linga && antaOf(it.word) === anta; })[0];
    }
    if (!hit) return '';
    return '<div class="sg-note">Pattern: declines like <a class="deva" href="#' + esc(hit.id) + '"><b>' + esc(hit.word) + '</b></a> (' + esc(LINGA_D[linga]) + ', ' +
      (anta === 'H' ? 'हलन्तः' : anta + '-कारान्तः') + ') — compare the two tables cell by cell.</div>';
  }

  function generate(stem, linga) {
    var out = $('#sg-out');
    stem = String(stem || '').normalize('NFC').trim();
    if (!stem || !/^[ऀ-ॿ]+$/.test(stem)) { out.innerHTML = '<div class="sg-err">Type the prātipadika in Devanagari (e.g. राघवेन्द्र, सरस्वती, जगत्).</div>'; return; }
    if (!window.DGESubantaSteps) { out.innerHTML = '<div class="sg-err">The derivation engine is not loaded on this page.</div>'; return; }
    S.stem = stem; S.linga = linga;
    var cached = null;
    try { cached = JSON.parse(localStorage.getItem(cacheKey(stem, linga)) || 'null'); } catch (e) {}
    out.innerHTML = '<div class="muted">Deriving 24 forms with vidyut-prakriya… <span id="sg-prog">0/24</span></div>';
    var t0 = Date.now();
    var jobs = [];
    for (var v = 0; v < 8; v++) for (var n = 0; n < 3; n++) jobs.push([v, n]);
    var results = [], done = 0;
    var run = cached ? Promise.resolve(cached) : jobs.reduce(function (p, vn) {
      return p.then(function () {
        return window.DGESubantaSteps.derive(stem, linga, vn[0], vn[1]).then(function (r) {
          results[vn[0] * 3 + vn[1]] = r.map(function (x) { return x.textDeva; });
          done++; var pg = $('#sg-prog'); if (pg) pg.textContent = done + '/24';
        }).catch(function () { results[vn[0] * 3 + vn[1]] = []; done++; });
      });
    }, Promise.resolve()).then(function () {
      var cells = results.map(function (r) { return (r || []).join('-'); });
      var rec = { stem: stem, linga: linga, cells: cells, ms: Date.now() - t0, at: new Date().toISOString() };
      try { localStorage.setItem(cacheKey(stem, linga), JSON.stringify(rec)); } catch (e) {}
      return rec;
    });
    run.then(function (rec) {
      S.cells = rec.cells;
      var filled = rec.cells.filter(Boolean).length;
      out.innerHTML = '<div class="sg-head"><span class="deva sg-stem">' + esc(stem) + '</span> <span class="muted deva">' + esc(LINGA_D[linga]) + '</span>' +
        '<span class="muted small"> · ' + filled + '/24 cells derived' + (rec.ms ? ' in ' + (rec.ms / 1000).toFixed(1) + ' s' : ' (cached)') + ' · vidyut-prakriya</span></div>' +
        exemplarHtml(stem, linga) +
        (filled ? tableHtml(rec.cells, stem) : '<div class="sg-err">The engine derives nothing from this stem — check the ending (a bare stem, no visarga: राम not रामः) and the liṅga.</div>') +
        '<div id="sg-deriv"></div>' +
        '<div class="sg-actions"><button type="button" class="btn" id="sg-again">↻ Re-derive</button> ' +
        '<a class="btn" href="../index.html?hl=' + encodeURIComponent(stem) + '" title="Search the library for this stem">🔍 in the library</a></div>';
      try { history.replaceState(null, '', '?gen=' + encodeURIComponent(stem) + '&l=' + linga + location.hash); } catch (e) {}
    }).catch(function (e) { out.innerHTML = '<div class="sg-err">' + esc(e.message || e) + '</div>'; });
  }

  function showDerivation(idx) {
    var v = Math.floor(idx / 3), n = idx % 3;
    var panel = $('#sg-deriv');
    if (!panel) return;
    panel.innerHTML = '<div class="muted">Deriving…</div>';
    window.DGESubantaSteps.derive(S.stem, S.linga, v, n).then(function (res) {
      panel.innerHTML = window.DGESubantaSteps.panelHtml(S.stem, S.linga, v, n, res, S.cells[idx] || '');
      panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }).catch(function (e) { panel.innerHTML = '<div class="sg-err">' + esc(e.message || e) + '</div>'; });
  }

  function boot() {
    var sec = $('#sg-sec');
    if (!sec) return;
    sec.addEventListener('click', function (ev) {
      var chip = ev.target.closest('[data-sg-l]');
      if (chip) { S.linga = chip.getAttribute('data-sg-l'); sec.querySelectorAll('[data-sg-l]').forEach(function (c) { c.classList.toggle('on', c === chip); }); return; }
      if (ev.target.id === 'sg-go') { generate($('#sg-stem').value, S.linga); return; }
      if (ev.target.id === 'sg-again') { try { localStorage.removeItem(cacheKey(S.stem, S.linga)); } catch (e) {} generate(S.stem, S.linga); return; }
      var cell = ev.target.closest('[data-sg-ci]');
      if (cell) showDerivation(+cell.getAttribute('data-sg-ci'));
    });
    $('#sg-stem').addEventListener('keydown', function (e) { if (e.key === 'Enter') generate(this.value, S.linga); });
    var q = new URLSearchParams(location.search);
    var gen = q.get('gen');
    if (gen) {
      var l = (q.get('l') || 'P').toUpperCase(); if (!LINGA_D[l]) l = 'P';
      S.linga = l; sec.querySelectorAll('[data-sg-l]').forEach(function (c) { c.classList.toggle('on', c.getAttribute('data-sg-l') === l); });
      $('#sg-stem').value = gen;
      sec.scrollIntoView({ block: 'start' });
      generate(gen, l);
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
