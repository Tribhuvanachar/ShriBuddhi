// dge/js/chandas-report.js — Vṛtta report core, shared by the site and the
// Node precompute pass (tools/chandas/build_chandas_reports.js loads this file
// unmodified, the way chandas_runner.js loads chandas.js). One implementation,
// so a report generated in the browser and one shipped in the repo agree.
//
//   DGEChandasReport.unitsOf(doc)              → [{id, text, declared}] every text unit a data.json carries
//   DGEChandasReport.classify(text, declared)  → {name, kind, src, aksharas} for one unit
//   DGEChandasReport.build(doc, meta, onProgress) → the per-grantha report object
//   DGEChandasReport.merge(reports)            → corpus/branch aggregate {byVrutta, unique, …}
//
// Report shape (per grantha):
//   { slug, title, branch, schema, units, scanned, metrical, prose, unknown,
//     byVrutta: { name: {n, kind, src} }, samples: { name: [unitId, …≤3] },
//     builtAt, ms, engine }
// kind: sama | ardhasama | vishama | upajati | matra | anushtubh | jaati | declared
// src:  engine (DGEChandas matched) | declared (the data file's own chandas
//       field, e.g. Rigveda mantras) | jaati (syllable-count name only)
(function () {
  'use strict';
  var TAG = /<[^>]+>/g;
  var DEVA = /[ऀ-ॿ]/;
  var PROSE_CHARS = 700;          // longer units are commentary prose, not verse: counted, not scanned

  function unitsOf(doc) {
    var out = [];
    var sh = doc && doc.shlokas;
    if (sh && !Array.isArray(sh) && typeof sh === 'object') {
      Object.keys(sh).forEach(function (k) {
        var v = sh[k];
        var t = v && typeof v === 'object' ? (v.sa || v.sanskrit_text || v.text || '') : String(v || '');
        if (t) out.push({ id: String(k), text: t, declared: v && v.chandas });
      });
    }
    (doc && doc.items || []).forEach(function (it) {
      var uid = String(it.id || it.reference || '');
      var base = it.sanskrit_text || it.samhita_patha || it.mula_text || it.sa || it.text || '';
      if (typeof base === 'string' && base) out.push({ id: uid, text: base, declared: it.chandas });
      (it.shlokas || []).forEach(function (s) {
        var suid = uid + (s.number != null ? '#' + s.number : '');
        var st = s.sanskrit_text || s.sa || '';
        if (typeof st === 'string' && st) out.push({ id: suid, text: st, declared: s.chandas });
      });
    });
    return out;
  }

  function cleanDeclared(d) {
    if (!d || typeof d !== 'string') return '';
    return d.replace(/\s*\(.*?\)\s*/g, '').split(/[,/;]/)[0].trim();
  }

  function classify(text, declared) {
    var t = String(text || '').replace(TAG, ' ');
    if (!DEVA.test(t)) return { name: '', kind: 'nodeva', src: '' };
    if (t.length > PROSE_CHARS) return { name: '', kind: 'prose', src: '' };
    var dec = cleanDeclared(declared);
    var eng = window.DGEChandas;
    var res = null;
    try { res = eng && eng.ready() ? eng.analyzeText(t) : null; } catch (e) { res = null; }
    var padas = res && res.padas || [];
    var ak = padas.length ? padas[0].aksharas : 0;
    if (res && res.match && res.match.names && res.match.names.length) {
      // "अनुष्टुप् (श्लोकः) — न-विपुला (पादे 3)" → base अनुष्टुप् (श्लोकः), variant न-विपुला (पादे 3):
      // one vṛtta for the unique counts, the variant kept alongside.
      var full = res.match.names[0], dash = full.indexOf(' — ');
      var base = dash > 0 ? full.slice(0, dash) : full, variant = dash > 0 ? full.slice(dash + 3) : '';
      return { name: base, variant: variant, kind: res.match.kind || 'sama', src: 'engine', aksharas: ak, declared: dec };
    }
    if (dec) return { name: dec, kind: 'declared', src: 'declared', aksharas: ak };
    // No named vṛtta: name the syllable-class (jāti) when the pādas are
    // regular. Two equal half-verses count as four pādas of half the length
    // (the engine already tried that split and found no vṛtta), so an
    // irregular śloka reports as अनुष्टुप् (अनियमितः), not as a 16-syllable
    // अष्टिः, and a 22-syllable half as the 11-syllable त्रिष्टुप् class.
    if (padas.length >= 2 && ak && padas.every(function (p) { return p.aksharas === ak; })) {
      var per = (padas.length === 2 && ak % 2 === 0) ? ak / 2 : (padas.length === 4 ? ak : 0);
      if (per === 8) return { name: 'अनुष्टुप् (अनियमितः)', kind: 'छन्दः', src: 'engine', aksharas: 8 };
      var j = per ? eng.jaatiName(per) : '';
      if (j) return { name: j + ' (जातिः, ' + per + ')', kind: 'jaati', src: 'jaati', aksharas: per };
    }
    return { name: '', kind: 'unknown', src: '', aksharas: ak };
  }

  function newReport(doc, meta, units) {
    return { slug: meta.slug, title: meta.title || '', branch: meta.branch || (meta.slug || '').split('/')[0],
      schema: doc && doc.schema || (doc && doc.shlokas ? 'legacy_shlokas' : ''),
      units: units.length, scanned: 0, metrical: 0, prose: 0, unknown: 0,
      byVrutta: {}, samples: {}, builtAt: new Date().toISOString(), engine: meta.engine || '' };
  }
  function addUnit(rep, u) {
    var c = classify(u.text, u.declared);
    if (c.kind === 'nodeva') return;
    rep.scanned++;
    if (c.kind === 'prose') { rep.prose++; }
    else if (!c.name) { rep.unknown++; }
    else {
      rep.metrical++;
      var e = rep.byVrutta[c.name] || (rep.byVrutta[c.name] = { n: 0, kind: c.kind, src: c.src });
      e.n++;
      if (c.variant) { e.variants = e.variants || {}; e.variants[c.variant] = (e.variants[c.variant] || 0) + 1; }
      var s = rep.samples[c.name] || (rep.samples[c.name] = []);
      if (s.length < 3) s.push(u.id);
    }
  }

  function build(doc, meta, onProgress) {
    var t0 = Date.now();
    var units = unitsOf(doc);
    var rep = newReport(doc, meta, units);
    for (var i = 0; i < units.length; i++) {
      addUnit(rep, units[i]);
      if (onProgress && (i % 50 === 0 || i === units.length - 1)) onProgress(i + 1, units.length);
    }
    rep.ms = Date.now() - t0;
    return rep;
  }

  // Same report, built in slices so a page can paint a progress bar and an
  // ETA between them (the sync build() blocks the thread). Resolves to the
  // report; rejects only if the caller's `cancelled()` returns true.
  function buildAsync(doc, meta, onProgress, cancelled) {
    var t0 = Date.now();
    var units = unitsOf(doc);
    var rep = newReport(doc, meta, units);
    var i = 0, SLICE = 120;
    return new Promise(function (resolve, reject) {
      function step() {
        if (cancelled && cancelled()) { reject(new Error('cancelled')); return; }
        var end = Math.min(units.length, i + SLICE);
        for (; i < end; i++) addUnit(rep, units[i]);
        if (onProgress) onProgress(i, units.length);
        if (i < units.length) setTimeout(step, 0);
        else { rep.ms = Date.now() - t0; resolve(rep); }
      }
      step();
    });
  }

  function merge(reports) {
    var agg = { granthas: 0, units: 0, scanned: 0, metrical: 0, prose: 0, unknown: 0, byVrutta: {}, byBranch: {} };
    reports.forEach(function (r) {
      if (!r) return;
      agg.granthas++; agg.units += r.units || 0; agg.scanned += r.scanned || 0;
      agg.metrical += r.metrical || 0; agg.prose += r.prose || 0; agg.unknown += r.unknown || 0;
      var b = agg.byBranch[r.branch] || (agg.byBranch[r.branch] = { granthas: 0, metrical: 0, byVrutta: {} });
      b.granthas++; b.metrical += r.metrical || 0;
      Object.keys(r.byVrutta || {}).forEach(function (name) {
        var v = r.byVrutta[name];
        var a = agg.byVrutta[name] || (agg.byVrutta[name] = { n: 0, kind: v.kind, granthas: 0 });
        a.n += v.n; a.granthas++;
        if (v.variants) { a.variants = a.variants || {}; Object.keys(v.variants).forEach(function (k) { a.variants[k] = (a.variants[k] || 0) + v.variants[k]; }); }
        b.byVrutta[name] = (b.byVrutta[name] || 0) + v.n;
      });
    });
    agg.unique = Object.keys(agg.byVrutta).length;
    Object.keys(agg.byBranch).forEach(function (k) { agg.byBranch[k].unique = Object.keys(agg.byBranch[k].byVrutta).length; });
    return agg;
  }

  window.DGEChandasReport = { unitsOf: unitsOf, classify: classify, build: build, buildAsync: buildAsync, merge: merge, PROSE_CHARS: PROSE_CHARS };
})();
