// js/chandas-page.js — the Vṛtta report section of vyakarana/chandas.html.
//
// Four reports, all reading the precomputed files in
// data/vedanga/chandas/reports/ (tools/chandas/build_chandas_reports.js)
// and falling back to an in-browser run of the same DGEChandasReport code:
//
//   1. ग्रन्थवृत्तसूची  — pick any grantha: its vṛttas, counts, variants, sample
//      verses. Shown instantly when a precomputed (or locally cached) report
//      exists; otherwise "Generate now". Regenerate re-runs it here with a
//      progress bar, elapsed timer and ETA, and caches the result on this
//      device (localStorage).
//   2. समग्रसूची — the whole library and each branch (Veda, Upaveda, Darśana,
//      Itihāsa …): granthas, units, metrical units, unique vṛttas; a branch
//      can be re-scanned live (admin) with the same progress/ETA.
//   3. वृत्तप्रयोगः — pick a vṛtta: how many verses use it, by branch and
//      sub-branch, which granthas, with example verses linked into the reader.
//   4. Leaderboards — most used, least used, never-attested vṛttas of the
//      DB, granthas with the most variety.
//
// Feature visibility comes from admin/config/chandas-features.json (a
// per-device override lives in localStorage 'dge_chandas_features'); the
// super-admin panel at the bottom edits it and can publish it to the repo
// with the same GitHub token the content editor uses ('github_admin_pat').
(function () {
  'use strict';
  var ROOT = '../';
  var REPORTS = ROOT + 'data/vedanga/chandas/reports/';
  var FEATURES_URL = '../../admin/config/chandas-features.json';
  var FEATURE_KEYS = ['reports', 'regenerate', 'downloadJson', 'corpusStats', 'branchScan', 'libraryScan',
    'vruttaReport', 'leaderboards', 'unattested', 'readerLinks'];
  var BRANCH_LABEL = { vedas: 'वेदाः', upaveda: 'उपवेदाः', 'vedanga/kalpa': 'वेदाङ्गम् · कल्पः', 'vedanga/vyakarana': 'वेदाङ्गम् · व्याकरणम्',
    'vedanga/shiksha': 'वेदाङ्गम् · शिक्षा', 'vedanga/jyotisha': 'वेदाङ्गम् · ज्योतिषम्', 'vedanga/nirukta': 'वेदाङ्गम् · निरुक्तम्',
    darshana: 'दर्शनानि', itihasa: 'इतिहासाः', purana: 'पुराणानि', agama: 'आगमाः', shastra: 'शास्त्राणि',
    smriti_dharma: 'स्मृतिधर्मशास्त्राणि', kavya_alankara: 'काव्यालङ्कारौ', DasaSahitya: 'दाससाहित्यम्', stotra: 'स्तोत्राणि', misc: 'अन्यत्' };
  var S = { features: {}, lib: [], libBySlug: {}, manifest: null, byVrutta: null, running: false, cancel: false };

  function $(sel) { return document.querySelector(sel); }
  function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;'); }
  function num(n) { return (n || 0).toLocaleString('en-IN'); }
  function pct(a, b) { return b ? (100 * a / b).toFixed(1) + '%' : '–'; }
  function fmtTime(ms) { var s = Math.max(0, Math.round(ms / 1000)); return Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0'); }
  function branchOf(slug) { var p = slug.split('/'); return p[0] === 'vedanga' ? 'vedanga/' + p[1] : p[0]; }
  function subBranchOf(slug) { var p = slug.split('/'); return p.slice(0, p[0] === 'vedanga' ? 3 : 2).join('/'); }
  function bl(b) { return BRANCH_LABEL[b] || b; }

  // ---- tiers & features ----
  function tier() {
    try {
      if (localStorage.getItem('is_superadmin') === 'true') return 'super';
      if (localStorage.getItem('acharyaAuthorized') === 'true') return 'admin';
    } catch (e) {}
    return 'user';
  }
  function allowed(key) {
    var v = S.features[key];
    if (v === true) return true;
    if (v === false || v == null) return false;
    var t = tier();
    if (v === 'admin') return t === 'admin' || t === 'super';
    if (v === 'super') return t === 'super';
    return false;
  }
  function applyGates() {
    document.querySelectorAll('[data-feature]').forEach(function (el) {
      el.hidden = !allowed(el.getAttribute('data-feature'));
    });
    var adm = $('#cr-admin-sec');
    if (adm) adm.hidden = tier() !== 'super';
  }
  function loadFeatures() {
    return fetch(FEATURES_URL).then(function (r) { return r.ok ? r.json() : {}; }).catch(function () { return {}; })
      .then(function (j) {
        S.features = (j && j.features) || {};
        S.featuresRepo = JSON.parse(JSON.stringify(S.features));
        try { var o = JSON.parse(localStorage.getItem('dge_chandas_features') || 'null'); if (o) Object.assign(S.features, o); } catch (e) {}
        FEATURE_KEYS.forEach(function (k) { if (!(k in S.features)) S.features[k] = true; });
      });
  }

  // ---- data ----
  function loadLibrary() {
    return fetch(ROOT + 'data/library.json').then(function (r) { return r.json(); }).then(function (j) {
      (j.granthas || j).forEach(function (g) {
        if (!g || !g.path || g.populated === false) return;
        var slug = g.path.replace(/^dge\/data\//, '').replace(/\/data\.json$/, '');
        var rec = { slug: slug, title: g.title || slug, branch: branchOf(slug) };
        S.lib.push(rec); S.libBySlug[slug] = rec;
      });
    });
  }
  function loadManifest() {
    return fetch(REPORTS + 'manifest.json').then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; })
      .then(function (m) { S.manifest = m; });
  }
  function loadByVrutta() {
    if (S.byVrutta) return Promise.resolve(S.byVrutta);
    return fetch(REPORTS + 'by_vrutta.json').then(function (r) { return r.ok ? r.json() : {}; }).catch(function () { return {}; })
      .then(function (b) { S.byVrutta = b; return b; });
  }
  function readerLink(slug, unit) {
    var u = ROOT + 'index.html?path=' + encodeURIComponent(slug);
    var m = String(unit || '').match(/(?:^|#)(\d+)$/);
    if (m) u += '&jumpShloka=' + m[1];
    else if (unit) u += '&jumpVedicId=' + encodeURIComponent(unit);
    return u;
  }
  function linkHtml(slug, unit, label) {
    var t = S.libBySlug[slug] ? S.libBySlug[slug].title : slug;
    var text = esc(label || (t + (unit ? ' · ' + unit : '')));
    if (!allowed('readerLinks')) return '<span class="cr-ref">' + text + '</span>';
    return '<a class="cr-ref" href="' + readerLink(slug, unit) + '" title="' + esc(slug) + '">' + text + '</a>';
  }

  // ---- progress ----
  function progressUI(box) {
    var t0 = Date.now(), timer = null;
    box.innerHTML = '<div class="cr-prog"><div class="cr-bar"><div class="cr-fill"></div></div>' +
      '<div class="cr-prog-text"></div><button type="button" class="btn cr-cancel">✖ Cancel</button></div>';
    var fill = box.querySelector('.cr-fill'), txt = box.querySelector('.cr-prog-text');
    box.querySelector('.cr-cancel').addEventListener('click', function () { S.cancel = true; });
    var last = { done: 0, total: 0, label: '' };
    function paint() {
      var el = Date.now() - t0;
      var frac = last.total ? last.done / last.total : 0;
      var eta = frac > 0.02 ? el / frac - el : NaN;
      fill.style.width = (100 * frac).toFixed(1) + '%';
      txt.textContent = (last.label ? last.label + ' · ' : '') + num(last.done) + ' / ' + num(last.total) + ' · ' +
        (100 * frac).toFixed(0) + '% · elapsed ' + fmtTime(el) + (isNaN(eta) ? '' : ' · ETA ' + fmtTime(eta));
    }
    timer = setInterval(paint, 250);
    return {
      update: function (done, total, label) { last.done = done; last.total = total; if (label != null) last.label = label; },
      finish: function () { clearInterval(timer); paint(); },
      elapsed: function () { return Date.now() - t0; }
    };
  }

  // ---- 1. grantha report ----
  function cacheKey(slug) { return 'dge_chandas_rep:' + slug; }
  function cachedReport(slug) { try { return JSON.parse(localStorage.getItem(cacheKey(slug)) || 'null'); } catch (e) { return null; } }
  function cacheReport(rep) { try { localStorage.setItem(cacheKey(rep.slug), JSON.stringify(rep)); } catch (e) {} }

  function fetchReport(slug) {
    return fetch(REPORTS + 'granthas/' + slug.replace(/\//g, '__') + '.json')
      .then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; });
  }
  function generate(slug, box) {
    if (S.running) return Promise.reject(new Error('busy'));
    S.running = true; S.cancel = false;
    var rec = S.libBySlug[slug] || { slug: slug, title: slug, branch: branchOf(slug) };
    var prog = progressUI(box);
    prog.update(0, 1, 'loading');
    return fetch(ROOT + 'data/' + slug + '/data.json').then(function (r) {
      if (!r.ok) throw new Error('data.json not found for ' + slug);
      return r.json();
    }).then(function (doc) {
      return DGEChandasReport.buildAsync(doc, { slug: slug, title: rec.title, branch: rec.branch, engine: 'browser' },
        function (d, t) { prog.update(d, t, 'scanning'); }, function () { return S.cancel; });
    }).then(function (rep) {
      prog.finish(); S.running = false;
      cacheReport(rep);
      return rep;
    }).catch(function (e) { prog.finish(); S.running = false; throw e; });
  }

  function reportHtml(rep, source) {
    var names = Object.keys(rep.byVrutta).sort(function (a, b) { return rep.byVrutta[b].n - rep.byVrutta[a].n; });
    var h = '<div class="cr-head"><div><b class="deva">' + esc(rep.title) + '</b> <span class="muted">' + esc(rep.slug) + '</span></div>' +
      '<div class="muted">' + esc(bl(rep.branch)) + ' · ' + esc(source) + ' · ' + esc((rep.builtAt || '').replace('T', ' ').slice(0, 16)) +
      (rep.engine ? ' · ' + esc(rep.engine) : '') + (rep.ms ? ' · ' + (rep.ms / 1000).toFixed(1) + ' s' : '') + '</div></div>';
    h += '<div class="cr-stats">' + stat(rep.units, 'units') + stat(rep.metrical, 'metrical') + stat(names.length, 'unique vṛttas') +
      stat(rep.prose, 'prose') + stat(rep.unknown, 'unmatched') + '</div>';
    h += '<table class="cr-table"><thead><tr><th>#</th><th>वृत्तम्</th><th>kind</th><th class="r">verses</th><th class="r">%</th><th>variants</th><th>samples</th></tr></thead><tbody>';
    names.forEach(function (n, i) {
      var v = rep.byVrutta[n];
      var vars = v.variants ? Object.keys(v.variants).map(function (k) { return esc(k) + ' <span class="muted">' + v.variants[k] + '</span>'; }).join(', ') : '';
      var samples = (rep.samples[n] || []).map(function (u) { return linkHtml(rep.slug, u, u); }).join(' ');
      h += '<tr><td>' + (i + 1) + '</td><td><a href="#" class="cr-vlink deva" data-vrutta="' + esc(n) + '">' + esc(n) + '</a></td>' +
        '<td class="muted deva">' + esc(v.kind) + (v.src === 'declared' ? ' <small>(declared)</small>' : '') + '</td>' +
        '<td class="r">' + num(v.n) + '</td><td class="r">' + pct(v.n, rep.metrical) + '</td><td class="deva small">' + vars + '</td><td class="small">' + samples + '</td></tr>';
    });
    h += '</tbody></table>';
    return h;
  }
  function stat(n, label) { return '<div class="cr-stat"><div class="cr-num">' + num(n) + '</div><div class="cr-lbl">' + esc(label) + '</div></div>'; }

  function showGrantha(slug) {
    var out = $('#cr-grantha-out'), act = $('#cr-grantha-actions');
    if (!slug || !S.libBySlug[slug]) { out.innerHTML = '<div class="muted">Pick a grantha from the list.</div>'; act.innerHTML = ''; return; }
    out.innerHTML = '<div class="muted">Loading…</div>';
    var rec = S.libBySlug[slug];
    var local = cachedReport(slug);
    fetchReport(slug).then(function (rep) {
      var source = 'precomputed';
      if (local && (!rep || local.builtAt > rep.builtAt)) { rep = local; source = 'generated on this device'; }
      act.innerHTML = '';
      if (allowed('regenerate')) act.innerHTML += '<button type="button" class="btn ai" id="cr-regen">' + (rep ? '↻ Regenerate' : '▶ Generate now') + '</button> ';
      if (rep && allowed('downloadJson')) act.innerHTML += '<button type="button" class="btn" id="cr-dl">⬇ JSON</button> ';
      act.innerHTML += '<a class="btn" href="' + ROOT + 'index.html?path=' + encodeURIComponent(slug) + '">📖 Open in reader</a>';
      if (rep) out.innerHTML = reportHtml(rep, source);
      else out.innerHTML = '<div class="muted">No report exists yet for <b class="deva">' + esc(rec.title) + '</b>.' +
        (allowed('regenerate') ? ' Generate it now — it runs here in your browser.' : ' Ask an admin to generate it.') + '</div>';
      var regen = $('#cr-regen');
      if (regen) regen.addEventListener('click', function () {
        var pbox = document.createElement('div'); out.prepend(pbox);
        generate(slug, pbox).then(function (r) { out.innerHTML = reportHtml(r, 'generated on this device'); showGrantha(slug); })
          .catch(function (e) { pbox.innerHTML = '<div class="cr-err">' + esc(e.message) + '</div>'; });
      });
      var dl = $('#cr-dl');
      if (dl) dl.addEventListener('click', function () { download(slug.replace(/\//g, '__') + '.chandas.json', rep); });
    });
  }
  function download(name, obj) {
    var a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([JSON.stringify(obj, null, 1)], { type: 'application/json' }));
    a.download = name; document.body.appendChild(a); a.click(); a.remove();
  }

  // ---- 2. corpus / branch ----
  function corpusHtml() {
    var m = S.manifest;
    if (!m) return '<div class="muted">No precomputed corpus statistics yet (run tools/chandas/build_chandas_reports.js).</div>';
    var h = '<div class="cr-stats">' + stat(m.files, 'granthas') + stat(m.units, 'units') + stat(m.metrical, 'metrical') + stat(m.unique, 'unique vṛttas') +
      stat((m.unattested || []).length, 'DB vṛttas unattested') + '</div>' +
      '<div class="muted small">Built ' + esc((m.builtAt || '').replace('T', ' ').slice(0, 16)) + ' · ' + esc(m.engine || '') + ' · ' + (m.ms / 60000).toFixed(1) + ' min</div>';
    h += '<table class="cr-table"><thead><tr><th>शाखा · branch</th><th class="r">granthas</th><th class="r">units</th><th class="r">metrical</th><th class="r">unique vṛttas</th><th></th></tr></thead><tbody>';
    Object.keys(m.byBranch).sort(function (a, b) { return m.byBranch[b].metrical - m.byBranch[a].metrical; }).forEach(function (b) {
      var v = m.byBranch[b];
      h += '<tr><td><a href="#" class="cr-blink deva" data-branch="' + esc(b) + '">' + esc(bl(b)) + '</a> <span class="muted small">' + esc(b) + '</span></td>' +
        '<td class="r">' + num(v.granthas) + '</td><td class="r">' + num(v.units) + '</td><td class="r">' + num(v.metrical) + '</td><td class="r">' + num(v.unique) + '</td>' +
        '<td>' + (allowed('branchScan') ? '<button type="button" class="btn-sm cr-scan" data-branch="' + esc(b) + '">↻ scan now</button>' : '') + '</td></tr>';
    });
    h += '</tbody></table>';
    if (allowed('libraryScan')) h += '<div class="cr-row"><button type="button" class="btn cr-scan" data-branch="*">↻ Re-scan the whole library in this browser (' + num(S.lib.length) + ' granthas — several minutes)</button></div>';
    h += '<div id="cr-branch-out"></div>';
    return h;
  }
  function branchDetailHtml(b) {
    var m = S.manifest, v = m && m.byBranch[b];
    if (!v) return '';
    var names = Object.keys(v.vruttas).sort(function (x, y) { return v.vruttas[y] - v.vruttas[x]; });
    var rows = (m.rows || []).filter(function (r) { return r[2] === b; }).sort(function (x, y) { return y[5] - x[5]; }).slice(0, 15);
    var h = '<h3 class="deva">' + esc(bl(b)) + ' <span class="muted small">' + esc(b) + '</span></h3>' +
      '<div class="cr-stats">' + stat(v.granthas, 'granthas') + stat(v.metrical, 'metrical') + stat(v.unique, 'unique vṛttas') + '</div>' +
      '<div class="cr-two"><div><h4>Vṛttas in this branch</h4><table class="cr-table"><tbody>' +
      names.slice(0, 40).map(function (n, i) { return '<tr><td>' + (i + 1) + '</td><td><a href="#" class="cr-vlink deva" data-vrutta="' + esc(n) + '">' + esc(n) + '</a></td><td class="r">' + num(v.vruttas[n]) + '</td><td class="r muted">' + pct(v.vruttas[n], v.metrical) + '</td></tr>'; }).join('') +
      (names.length > 40 ? '<tr><td colspan="4" class="muted">… ' + (names.length - 40) + ' more</td></tr>' : '') + '</tbody></table></div>' +
      '<div><h4>Most varied granthas</h4><table class="cr-table"><tbody>' +
      rows.map(function (r) { return '<tr><td><a href="#" class="cr-glink deva" data-slug="' + esc(r[0]) + '">' + esc(r[1]) + '</a></td><td class="r">' + num(r[5]) + ' vṛttas</td><td class="r muted">' + num(r[4]) + ' verses</td></tr>'; }).join('') +
      '</tbody></table></div></div>';
    return h;
  }
  function scanBranch(b, box) {
    if (S.running) return;
    S.running = true; S.cancel = false;
    var list = b === '*' ? S.lib.slice() : S.lib.filter(function (g) { return g.branch === b; });
    var prog = progressUI(box);
    var reps = [], i = 0, t0 = Date.now();
    function next() {
      if (S.cancel || i >= list.length) { done(); return; }
      var g = list[i];
      prog.update(i, list.length, g.title.slice(0, 40));
      fetch(ROOT + 'data/' + g.slug + '/data.json').then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; })
        .then(function (doc) {
          if (!doc) { i++; next(); return; }
          return DGEChandasReport.buildAsync(doc, { slug: g.slug, title: g.title, branch: g.branch, engine: 'browser' }, null, function () { return S.cancel; })
            .then(function (rep) { reps.push(rep); cacheReport(rep); i++; next(); });
        }).catch(function () { done(); });
    }
    function done() {
      prog.finish(); S.running = false;
      var agg = DGEChandasReport.merge(reps);
      var names = Object.keys(agg.byVrutta).sort(function (x, y) { return agg.byVrutta[y].n - agg.byVrutta[x].n; });
      var out = document.createElement('div');
      out.innerHTML = '<h3>Live scan · ' + esc(b === '*' ? 'whole library' : bl(b)) + (S.cancel ? ' <span class="cr-err">(cancelled, partial)</span>' : '') +
        ' <span class="muted small">' + num(reps.length) + ' granthas in ' + fmtTime(Date.now() - t0) + '</span></h3>' +
        '<div class="cr-stats">' + stat(agg.units, 'units') + stat(agg.metrical, 'metrical') + stat(agg.unique, 'unique vṛttas') + stat(agg.prose, 'prose') + stat(agg.unknown, 'unmatched') + '</div>' +
        '<table class="cr-table"><tbody>' + names.slice(0, 60).map(function (n, k) { return '<tr><td>' + (k + 1) + '</td><td><a href="#" class="cr-vlink deva" data-vrutta="' + esc(n) + '">' + esc(n) + '</a></td><td class="r">' + num(agg.byVrutta[n].n) + '</td><td class="r muted">' + agg.byVrutta[n].granthas + ' granthas</td></tr>'; }).join('') + '</tbody></table>';
      box.appendChild(out);
      try { localStorage.setItem('dge_chandas_branch:' + b, JSON.stringify({ at: new Date().toISOString(), agg: agg })); } catch (e) {}
    }
    next();
  }

  // ---- 3. per-vṛtta ----
  function showVrutta(name) {
    var out = $('#cr-vrutta-out');
    if (!name) { out.innerHTML = ''; return; }
    out.innerHTML = '<div class="muted">Loading…</div>';
    loadByVrutta().then(function (b) {
      var v = b[name];
      var dbRow = (S.manifest && S.manifest.dbNames || []).filter(function (d) { return d[0] === name; })[0];
      if (!v) {
        out.innerHTML = '<div class="cr-head"><b class="deva">' + esc(name) + '</b></div><div class="muted">' +
          (dbRow ? 'In the vṛtta database (' + esc(dbRow[1]) + ') but not yet attested anywhere in the library.' : 'Not in the report data.') + '</div>';
        return;
      }
      var branches = Object.keys(v.byBranch).sort(function (x, y) { return v.byBranch[y] - v.byBranch[x]; });
      var sub = {};
      (v.granthas || []).forEach(function (g) { var k = subBranchOf(g[0]); sub[k] = (sub[k] || 0) + g[1]; });
      var subs = Object.keys(sub).sort(function (x, y) { return sub[y] - sub[x]; });
      var h = '<div class="cr-head"><b class="deva">' + esc(name) + '</b> <span class="muted deva">' + esc(v.kind) + '</span></div>' +
        '<div class="cr-stats">' + stat(v.n, 'verses in the library') + stat((v.granthas || []).length + (v.granthas && v.granthas.length >= 80 ? '+' : ''), 'granthas') + stat(branches.length, 'branches') + '</div>';
      if (v.variants) h += '<div class="small deva">Variants: ' + Object.keys(v.variants).map(function (k) { return esc(k) + ' <span class="muted">' + num(v.variants[k]) + '</span>'; }).join(' · ') + '</div>';
      h += '<div class="cr-two"><div><h4>By branch</h4><table class="cr-table"><tbody>' +
        branches.map(function (bn) { return '<tr><td class="deva">' + esc(bl(bn)) + '</td><td class="r">' + num(v.byBranch[bn]) + '</td><td class="r muted">' + pct(v.byBranch[bn], v.n) + '</td></tr>'; }).join('') + '</tbody></table>' +
        '<h4>By sub-branch</h4><table class="cr-table"><tbody>' +
        subs.slice(0, 25).map(function (sb) { return '<tr><td class="small">' + esc(sb) + '</td><td class="r">' + num(sub[sb]) + '</td></tr>'; }).join('') + '</tbody></table></div>' +
        '<div><h4>Granthas</h4><table class="cr-table"><tbody>' +
        (v.granthas || []).slice(0, 40).map(function (g) { return '<tr><td><a href="#" class="cr-glink deva" data-slug="' + esc(g[0]) + '">' + esc(S.libBySlug[g[0]] ? S.libBySlug[g[0]].title : g[0]) + '</a></td><td class="r">' + num(g[1]) + '</td></tr>'; }).join('') +
        '</tbody></table></div></div>';
      if (v.examples && v.examples.length) h += '<h4>Examples</h4><div class="cr-examples">' + v.examples.map(function (e) { return linkHtml(e[0], e[1]); }).join(' · ') + '</div>';
      out.innerHTML = h;
    });
  }

  // ---- 4. leaderboards ----
  function boardsHtml() {
    var m = S.manifest, b = S.byVrutta;
    if (!m || !b) return '<div class="muted">Loading…</div>';
    var names = Object.keys(b);
    var most = names.slice().sort(function (x, y) { return b[y].n - b[x].n; }).slice(0, 15);
    var least = names.filter(function (n) { return b[n].kind !== 'declared' && b[n].kind !== 'jaati'; }).sort(function (x, y) { return b[x].n - b[y].n || x.localeCompare(y); }).slice(0, 15);
    var varied = (m.rows || []).slice().sort(function (x, y) { return y[5] - x[5]; }).slice(0, 15);
    var wide = names.slice().sort(function (x, y) { return (b[y].granthas || []).length - (b[x].granthas || []).length; }).slice(0, 10);
    function list(arr, f) { return '<ol class="cr-ol">' + arr.map(f).join('') + '</ol>'; }
    var h = '<div class="cr-two">' +
      '<div><h4>Most used vṛttas</h4>' + list(most, function (n) { return '<li><a href="#" class="cr-vlink deva" data-vrutta="' + esc(n) + '">' + esc(n) + '</a> <span class="muted">' + num(b[n].n) + '</span></li>'; }) + '</div>' +
      '<div><h4>Rarest attested (named vṛttas)</h4>' + list(least, function (n) { return '<li><a href="#" class="cr-vlink deva" data-vrutta="' + esc(n) + '">' + esc(n) + '</a> <span class="muted">' + num(b[n].n) + '</span></li>'; }) + '</div>' +
      '<div><h4>Most widely spread</h4>' + list(wide, function (n) { return '<li><a href="#" class="cr-vlink deva" data-vrutta="' + esc(n) + '">' + esc(n) + '</a> <span class="muted">' + (b[n].granthas || []).length + ' granthas</span></li>'; }) + '</div>' +
      '<div><h4>Most varied granthas</h4>' + list(varied, function (r) { return '<li><a href="#" class="cr-glink deva" data-slug="' + esc(r[0]) + '">' + esc(r[1]) + '</a> <span class="muted">' + r[5] + ' vṛttas</span></li>'; }) + '</div>' +
      '</div>';
    if (allowed('unattested')) h += '<h4>In the vṛtta database, never attested in the library (' + (m.unattested || []).length + ')</h4><div class="deva small cr-wrap">' +
      (m.unattested || []).map(function (n) { return '<a href="#" class="cr-vlink" data-vrutta="' + esc(n) + '">' + esc(n) + '</a>'; }).join(' · ') + '</div>';
    return h;
  }

  // ---- admin panel ----
  function adminHtml() {
    var h = '<table class="cr-table"><thead><tr><th>feature</th><th>visible to</th></tr></thead><tbody>';
    FEATURE_KEYS.forEach(function (k) {
      var v = S.features[k];
      var val = v === true ? 'all' : v === false ? 'off' : v;
      h += '<tr><td><code>' + k + '</code></td><td><select data-fkey="' + k + '">' +
        ['all', 'admin', 'super', 'off'].map(function (o) { return '<option value="' + o + '"' + (o === val ? ' selected' : '') + '>' + o + '</option>'; }).join('') + '</select></td></tr>';
    });
    h += '</tbody></table><div class="cr-row">' +
      '<button type="button" class="btn ai" id="cr-adm-save">Save on this device</button> ' +
      '<button type="button" class="btn" id="cr-adm-reset">Reset to repo file</button> ' +
      '<button type="button" class="btn" id="cr-adm-dl">⬇ chandas-features.json</button> ' +
      '<button type="button" class="btn" id="cr-adm-publish" title="PUT admin/config/chandas-features.json on main with the stored GitHub token">⬆ Publish to repo</button>' +
      '</div><div id="cr-adm-msg" class="muted small"></div>';
    return h;
  }
  function readAdminForm() {
    var out = {};
    document.querySelectorAll('#cr-admin-out select[data-fkey]').forEach(function (s) {
      out[s.getAttribute('data-fkey')] = s.value === 'all' ? true : s.value === 'off' ? false : s.value;
    });
    return out;
  }
  function publish(features) {
    var msg = $('#cr-adm-msg');
    var tok = ''; try { tok = localStorage.getItem('github_admin_pat') || ''; } catch (e) {}
    if (!tok) { msg.textContent = 'No GitHub token on this device (set it in the reader\'s Admin → Repo Files).'; return; }
    var owner = 'Tribhuvanachar', repo = 'bhumandala', path = 'admin/config/chandas-features.json';
    var body = JSON.stringify({ note: S.featuresNote || 'Chandas report page feature visibility (see js/chandas-page.js).', updatedAt: new Date().toISOString(), features: features }, null, 2) + '\n';
    var api = 'https://api.github.com/repos/' + owner + '/' + repo + '/contents/' + path;
    var hdr = { Authorization: 'token ' + tok, Accept: 'application/vnd.github+json' };
    msg.textContent = 'Publishing…';
    fetch(api + '?ref=main', { headers: hdr }).then(function (r) { return r.ok ? r.json() : null; }).then(function (cur) {
      var payload = { message: 'Chandas report page: feature visibility (from the page\'s admin panel)', branch: 'main',
        content: btoa(unescape(encodeURIComponent(body))) };
      if (cur && cur.sha) payload.sha = cur.sha;
      return fetch(api, { method: 'PUT', headers: Object.assign({ 'Content-Type': 'application/json' }, hdr), body: JSON.stringify(payload) });
    }).then(function (r) { msg.textContent = r.ok ? 'Published to main (GitHub Pages picks it up in a few minutes).' : 'GitHub refused: HTTP ' + r.status; })
      .catch(function (e) { msg.textContent = 'Publish failed: ' + e.message; });
  }

  // ---- wiring ----
  function fillGranthaList() {
    var dl = $('#cr-grantha-list');
    if (!dl) return;
    dl.innerHTML = S.lib.map(function (g) { return '<option value="' + esc(g.title) + '  [' + esc(g.slug) + ']"></option>'; }).join('');
  }
  function slugFromInput(val) {
    var m = String(val || '').match(/\[([^\]]+)\]\s*$/);
    if (m && S.libBySlug[m[1]]) return m[1];
    if (S.libBySlug[val]) return val;
    var t = S.lib.filter(function (g) { return g.title === val; })[0];
    return t ? t.slug : '';
  }
  function fillVruttaList() {
    var dl = $('#cr-vrutta-list');
    if (!dl) return;
    var names = {};
    (S.manifest && S.manifest.dbNames || []).forEach(function (d) { names[d[0]] = 1; });
    Object.keys(S.byVrutta || {}).forEach(function (n) { names[n] = 1; });
    dl.innerHTML = Object.keys(names).sort().map(function (n) { return '<option value="' + esc(n) + '"></option>'; }).join('');
  }
  function openGrantha(slug) {
    $('#cr-grantha').value = S.libBySlug[slug] ? S.libBySlug[slug].title + '  [' + slug + ']' : slug;
    showGrantha(slug);
    $('#cr-grantha-sec').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
  function openVrutta(name) {
    $('#cr-vrutta').value = name;
    showVrutta(name);
    $('#cr-vrutta-sec').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function boot() {
    if (!$('#cr-grantha-sec')) return;
    Promise.all([loadFeatures(), loadLibrary(), loadManifest()]).then(function () {
      applyGates();
      fillGranthaList();
      $('#cr-corpus-out').innerHTML = corpusHtml();
      loadByVrutta().then(function () { fillVruttaList(); $('#cr-board-out').innerHTML = boardsHtml(); });
      $('#cr-admin-out').innerHTML = adminHtml();
      var q = new URLSearchParams(location.search);
      if (q.get('report')) openGrantha(q.get('report'));
      if (q.get('vrutta')) openVrutta(q.get('vrutta'));
    });
    $('#cr-grantha').addEventListener('change', function () { var s = slugFromInput(this.value); if (s) showGrantha(s); });
    $('#cr-grantha-go').addEventListener('click', function () { var s = slugFromInput($('#cr-grantha').value); if (s) showGrantha(s); else $('#cr-grantha-out').innerHTML = '<div class="muted">Pick a grantha from the list.</div>'; });
    $('#cr-vrutta').addEventListener('change', function () { showVrutta(this.value.trim()); });
    $('#cr-vrutta-go').addEventListener('click', function () { showVrutta($('#cr-vrutta').value.trim()); });
    document.addEventListener('click', function (ev) {
      var a = ev.target.closest('.cr-vlink, .cr-glink, .cr-blink, .cr-scan');
      if (!a) return;
      if (a.classList.contains('cr-vlink')) { ev.preventDefault(); openVrutta(a.getAttribute('data-vrutta')); }
      else if (a.classList.contains('cr-glink')) { ev.preventDefault(); openGrantha(a.getAttribute('data-slug')); }
      else if (a.classList.contains('cr-blink')) { ev.preventDefault(); $('#cr-branch-out').innerHTML = branchDetailHtml(a.getAttribute('data-branch')); }
      else if (a.classList.contains('cr-scan')) { var box = $('#cr-branch-out'); box.innerHTML = ''; scanBranch(a.getAttribute('data-branch'), box); }
      var id = ev.target.id;
      if (id === 'cr-adm-save') { var f = readAdminForm(); try { localStorage.setItem('dge_chandas_features', JSON.stringify(f)); } catch (e) {} S.features = f; applyGates(); $('#cr-corpus-out').innerHTML = corpusHtml(); $('#cr-board-out').innerHTML = boardsHtml(); $('#cr-adm-msg').textContent = 'Saved on this device.'; }
      if (id === 'cr-adm-reset') { try { localStorage.removeItem('dge_chandas_features'); } catch (e) {} S.features = JSON.parse(JSON.stringify(S.featuresRepo || {})); FEATURE_KEYS.forEach(function (k) { if (!(k in S.features)) S.features[k] = true; }); applyGates(); $('#cr-admin-out').innerHTML = adminHtml(); $('#cr-adm-msg').textContent = 'Back to the repo file.'; }
      if (id === 'cr-adm-dl') download('chandas-features.json', { note: 'Chandas report page feature visibility (see js/chandas-page.js).', updatedAt: new Date().toISOString(), features: readAdminForm() });
      if (id === 'cr-adm-publish') publish(readAdminForm());
    });
    window.addEventListener('storage', applyGates);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
