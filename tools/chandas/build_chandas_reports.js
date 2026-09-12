#!/usr/bin/env node
// Corpus-wide vṛtta reports (छन्दःसूची) — precomputed with the site's own engine.
//
// Loads dge/js/chandas.js and dge/js/chandas-report.js unmodified (the same
// stub trick as tools/kamadhenu/chandas_runner.js), walks every data.json
// under dge/data (ocr_staging excluded) and writes:
//
//   dge/data/vedanga/chandas/reports/granthas/<slug with / → __>.json   one report per grantha
//   dge/data/vedanga/chandas/reports/by_vrutta.json                     name → {n, kind, granthas:[[slug,n]…], byBranch:{…}, examples:[[slug,unit]…]}
//   dge/data/vedanga/chandas/reports/manifest.json                      totals, per-branch uniques, per-grantha rows, DB names with zero use
//
// The page (dge/vyakarana/chandas.html → js/chandas-page.js) shows these
// instantly and regenerates a single grantha in the browser with the same
// DGEChandasReport.build(), so the two never disagree.
//
// Run:  node tools/chandas/build_chandas_reports.js [--only <slug-prefix>]   (~20–40 min for the whole corpus)
'use strict';
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const ROOT = path.resolve(__dirname, '..', '..');
const DATA = path.join(ROOT, 'dge/data');
const OUT = path.join(DATA, 'vedanga/chandas/reports');
const TOPDIRS = ['darshana', 'DvaitaVedanta/Itara/DasaSahitya', 'itihasa', 'kavya_alankara', 'purana', 'smriti_dharma', 'stotra',
  'nitishastra', 'upaveda', 'agama', 'vedas', 'shastra', 'misc', 'vedanga'];
const only = (() => { const i = process.argv.indexOf('--only'); return i > 0 ? process.argv[i + 1] : ''; })();

global.window = global;
global.document = { readyState: 'complete', querySelector: () => null, addEventListener: () => {} };
global.localStorage = { getItem: () => null, setItem: () => {} };
global.fetch = () => Promise.resolve({ json: () => Promise.resolve(JSON.parse(fs.readFileSync(path.join(DATA, 'vedanga/chandas/data.json'), 'utf8'))) });
const engineSrc = fs.readFileSync(path.join(ROOT, 'dge/js/chandas.js'), 'utf8');
eval(engineSrc);
eval(fs.readFileSync(path.join(ROOT, 'dge/js/chandas-report.js'), 'utf8'));
const ENGINE = 'chandas.js@' + crypto.createHash('sha1').update(engineSrc).digest('hex').slice(0, 10);

function* walk(dir) {
  for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
    if (ent.name === 'ocr_staging' || ent.name === 'reports') continue;
    const p = path.join(dir, ent.name);
    if (ent.isDirectory()) yield* walk(p);
    else if (ent.name === 'data.json') yield p;
  }
}
function branchOf(slug) { const s = slug.split('/'); return s[0] === 'vedanga' ? 'vedanga/' + s[1] : s[0]; }
function titleOf(doc) {
  return String(doc.title || doc.title_devanagari || (doc.metadata && (doc.metadata.title || doc.metadata.DisplayName)) || '');
}

window.DGEChandas.loadDB('').then(() => {
  const t0 = Date.now();
  const lib = JSON.parse(fs.readFileSync(path.join(DATA, 'library.json'), 'utf8'));
  const libTitle = {};
  (lib.granthas || lib).forEach(g => { if (g && g.path) libTitle[g.path.replace(/^dge\/data\//, '').replace(/\/data\.json$/, '')] = g.title; });
  fs.mkdirSync(path.join(OUT, 'granthas'), { recursive: true });
  const byV = {}; const rows = []; let files = 0, units = 0;
  for (const top of TOPDIRS) {
    const d = path.join(DATA, top);
    if (!fs.existsSync(d)) continue;
    for (const fp of walk(d)) {
      const slug = path.relative(DATA, path.dirname(fp)).split(path.sep).join('/');
      if (only && !slug.startsWith(only)) continue;
      if (slug.startsWith('vedanga/chandas')) continue;              // the vṛtta DB itself is not a text
      let doc; try { doc = JSON.parse(fs.readFileSync(fp, 'utf8')); } catch (e) { continue; }
      const rep = DGEChandasReport.build(doc, { slug, title: libTitle[slug] || titleOf(doc), branch: branchOf(slug), engine: ENGINE });
      if (!rep.scanned) continue;
      files++; units += rep.units;
      fs.writeFileSync(path.join(OUT, 'granthas', slug.replace(/\//g, '__') + '.json'), JSON.stringify(rep));
      const top1 = Object.entries(rep.byVrutta).sort((a, b) => b[1].n - a[1].n)[0];
      rows.push([slug, rep.title, rep.branch, rep.units, rep.metrical, Object.keys(rep.byVrutta).length, top1 ? top1[0] : '', top1 ? top1[1].n : 0]);
      for (const [name, v] of Object.entries(rep.byVrutta)) {
        const e = byV[name] || (byV[name] = { n: 0, kind: v.kind, granthas: [], byBranch: {}, examples: [] });
        e.n += v.n; e.granthas.push([slug, v.n]);
        if (v.variants) { e.variants = e.variants || {}; for (const [k, n] of Object.entries(v.variants)) e.variants[k] = (e.variants[k] || 0) + n; }
        e.byBranch[rep.branch] = (e.byBranch[rep.branch] || 0) + v.n;
        if (e.examples.length < 12) (rep.samples[name] || []).slice(0, 2).forEach(u => e.examples.push([slug, u]));
      }
      if (files % 100 === 0) console.error(`${files} files, ${units} units, ${((Date.now() - t0) / 1000).toFixed(0)} s`);
    }
  }
  for (const e of Object.values(byV)) { e.granthas.sort((a, b) => b[1] - a[1]); e.granthas = e.granthas.slice(0, 80); }
  fs.writeFileSync(path.join(OUT, 'by_vrutta.json'), JSON.stringify(byV));
  const db = JSON.parse(fs.readFileSync(path.join(DATA, 'vedanga/chandas/data.json'), 'utf8'));
  const dbNames = [];
  ['sama_vrutta', 'ardhasama_vrutta', 'vishama_vrutta', 'upajati_vrutta', 'matra_vrutta'].forEach(k => (db[k] || []).forEach(v => { if (v.vrutta_names && v.vrutta_names[0]) dbNames.push([v.vrutta_names[0], k.replace('_vrutta', '')]); }));
  const byBranch = {};
  rows.forEach(r => { const b = byBranch[r[2]] || (byBranch[r[2]] = { granthas: 0, units: 0, metrical: 0, vruttas: {} }); b.granthas++; b.units += r[3]; b.metrical += r[4]; });
  Object.entries(byV).forEach(([name, e]) => Object.entries(e.byBranch).forEach(([b, n]) => { if (byBranch[b]) byBranch[b].vruttas[name] = n; }));
  Object.values(byBranch).forEach(b => { b.unique = Object.keys(b.vruttas).length; });
  const manifest = {
    builtAt: new Date().toISOString(), engine: ENGINE, tool: 'tools/chandas/build_chandas_reports.js',
    files, units, metrical: rows.reduce((a, r) => a + r[4], 0), unique: Object.keys(byV).length,
    byBranch, dbNames,
    unattested: dbNames.filter(([n]) => !byV[n]).map(([n]) => n),
    rows, // [slug, title, branch, units, metrical, unique, topVrutta, topN]
    ms: Date.now() - t0
  };
  fs.writeFileSync(path.join(OUT, 'manifest.json'), JSON.stringify(manifest));
  console.error(`done: ${files} granthas, ${units} units, ${manifest.metrical} metrical, ${manifest.unique} distinct vṛttas, ${(manifest.ms / 60000).toFixed(1)} min`);
});
