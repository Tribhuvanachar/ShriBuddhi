// ============================================================
// LAYER STITCHING — multi-layer grantha reading
// See MULTI_LAYER_READER_ARCHITECTURE.md for the full design.
//
// The DvaitaVedanta importer (and a few other pipelines) file one grantha
// as sibling folders — mula/ + tika_*/ — each with its own data.json and
// its own library.json entry, joined only by shared item ids. Nothing at
// rest nests them into the per-item commentaries{} object the reader's
// multi-commentary tab UI feeds on, so opening any layer showed ONE layer
// with no way to its siblings. This module stitches them at load time:
//
//   1. data/layer_manifest.json (generated offline by
//      tools/build_layer_manifest.py, from the data itself) says which
//      granthas are actually id-joinable and what each layer is called.
//      No manifest entry -> this module does nothing for that grantha.
//   2. Opening a mula spine advertises every joinable sibling layer in
//      metadata.availableCommentaries — WITHOUT fetching any of them
//      (nyaya_sudha's layers total ~42 MB; the spine alone is 2.6 MB).
//   3. A layer's data.json is fetched only when the reader actually turns
//      that commentary on, then merged into shlokas[n].commentaries by id
//      (exact id first, then the importer's -N collision suffix stripped).
//   4. Opening a tika_* folder directly still works standalone, plus a
//      banner linking back to the stitched mula spine.
//
// Also owns the two navigation pieces the stitched view needs: the curated
// lineage strip (what this grantha comments on) and the breadcrumb-derived
// section navigator (adhyaya > pada > adhikarana), both data-driven from
// fields the importer already captures per item.
// ============================================================
window.DGE_VERSIONS = window.DGE_VERSIONS || {};
window.DGE_VERSIONS['layer-stitch.js'] = 'v1.3 (volume navigator: a grantha the library splits across numbered sibling folders -- sumadhva_vijaya/sarga_1..16, shatapatha_brahmana/kanda_NN -- gets a picker that switches between them, siblings read from library.json so an unpopulated volume still lists and says so; lineage strip now falls back to walking the taxonomy path for every mula, not just the five in DGE_GRANTHA_LINEAGE. v1.2 (section navigator gains a category FILTER mode: when items carry a `category` heading (Tīrthaprabandha kṣetra/deity), the dropdown filters the list to that heading via getFilteredIds instead of jumping, with per-heading counts and an "all" option; structural-breadcrumb texts keep the jump behaviour. v1.1: auto-select the primary layer on load + dgeStitchedAvailableKeys for the per-card pill row; v1.0: manifest-gated load-time stitching of sibling mula/tika_* layers into commentaries{}, lineage strip, breadcrumb section navigator, standalone-tika banner)';

// Fetched once per page load, same cache-busting rationale as
// dgeLibraryCatalogPromise (core.js): GitHub Pages' CDN happily serves a
// stale manifest forever otherwise. Small file (~150 KB), only granthas
// with at least one joinable layer are in it.
window.dgeLayerManifestPromise = fetch('data/layer_manifest.json?t=' + Date.now(), { cache: 'no-store' })
  .then(res => res.ok ? res.json() : null)
  .catch(() => null);

// What a grantha comments on, curated — the corpus itself records no
// machine link between granthas (measured: pratika-prefix matching from
// nyaya_sudha's spine to anuvyakhyana's verses resolves only 56%, far too
// weak to auto-link without fabricating; see the architecture doc §5).
// Keys and targets are grantha-dir slugs relative to data/. Each chain is
// rendered oldest-first above the title, ending at the current grantha.
const DGE_GRANTHA_LINEAGE = {
  'darshana/vedanta/dvaita/DvaitaVedantaIn/later_acharyas/nyaya_sudha': [
    { label: 'ब्रह्मसूत्राणि', slug: 'darshana/vedanta/dvaita/DvaitaVedantaIn/sutra_prasthana/brahma_sutra_bhashya/mula' },
    { label: 'अनुव्याख्यानम्', slug: 'darshana/vedanta/dvaita/DvaitaVedantaIn/sutra_prasthana/anuvyakhyana/mula' }
  ],
  'darshana/vedanta/dvaita/DvaitaVedantaIn/sutra_prasthana/anuvyakhyana': [
    { label: 'ब्रह्मसूत्राणि', slug: 'darshana/vedanta/dvaita/DvaitaVedantaIn/sutra_prasthana/brahma_sutra_bhashya/mula' }
  ],
  'darshana/vedanta/dvaita/DvaitaVedantaIn/sutra_prasthana/brahma_sutra_bhashya': [
    { label: 'ब्रह्मसूत्राणि', slug: null } // the spine of this grantha IS the sutra text
  ],
  'darshana/vedanta/dvaita/DvaitaVedantaIn/later_acharyas/nyayamrita': [],
  'darshana/vedanta/dvaita/DvaitaVedantaIn/later_acharyas/tatparya_chandrika': [
    { label: 'ब्रह्मसूत्राणि', slug: 'darshana/vedanta/dvaita/DvaitaVedantaIn/sutra_prasthana/brahma_sutra_bhashya/mula' },
    { label: 'तत्त्वप्रकाशिका', slug: 'darshana/vedanta/dvaita/DvaitaVedantaIn/sutra_prasthana/brahma_sutra_bhashya/tika_tattvaprakashika' }
  ]
};

// Per-page-load stitch state. null = current grantha is not stitchable.
let dgeStitch = null;

function dgeStitchBaseId(id) {
  return String(id || '').replace(/-\d+$/, '');
}

// Called from core.js after dgeNormalizeGranthaData and BEFORE initApp(),
// so the extended availableCommentaries is already in place when
// renderStotraChrome builds the commentary picker. Async because it may
// need the manifest fetch to resolve; core.js awaits it.
window.dgeApplyLayerStitching = async function(slug) {
  dgeStitch = null;
  if (!slug || !window.stotraData || !window.stotraData.metadata) return;
  const manifest = await window.dgeLayerManifestPromise;
  if (!manifest || !manifest.granthas) return;

  const lastSlash = slug.lastIndexOf('/');
  if (lastSlash < 0) return;
  const parent = slug.slice(0, lastSlash);
  const leafDir = slug.slice(lastSlash + 1);
  const entry = manifest.granthas[parent];
  if (!entry) return;

  if (leafDir !== 'mula') {
    // A tika_* layer opened standalone: keep it exactly as it renders
    // today, but remember enough to offer the way back to the full view.
    if (leafDir.indexOf('tika_') === 0) {
      const layer = (entry.layers || []).find(l => l.folder === leafDir);
      dgeStitch = {
        role: 'tika', granthaRel: parent, granthaTitle: entry.title || '',
        mulaSlug: parent + '/mula', layerLabel: layer ? layer.label : ''
      };
    }
    return;
  }

  // The spine. Advertise every joinable sibling layer without fetching it.
  const meta = window.stotraData.metadata;
  meta.availableCommentaries = meta.availableCommentaries || {};
  const layers = {};
  (entry.layers || []).forEach(l => {
    if (!l.matched) return; // ids don't join this grantha's mula — leave standalone
    let key = l.folder.replace(/^tika_/, '');
    if (meta.availableCommentaries[key] && !layers[key]) key = 'layer_' + key;
    if (layers[key]) return;
    layers[key] = { folder: l.folder, label: l.label || key, author: l.author || '',
                    items: l.items, matched: l.matched, state: 'pending', unmatched: 0 };
    meta.availableCommentaries[key] = layers[key].label;
  });
  if (!Object.keys(layers).length) return;

  // The catalog title says "श्रीमन्न्यायसुधा — mula"; the stitched view IS
  // the grantha, so drop the layer suffix the manifest already resolved.
  if (entry.title) meta.title = entry.title;
  if (!meta.author && entry.author) meta.author = entry.author;

  // id -> internal shloka number, built once. Exact id first; the base id
  // (importer's -N duplicate suffix stripped) fills the gaps so a tika
  // keyed DV_978 still lands on a spine item stored as DV_978-2.
  const idMap = {};
  Object.keys(window.stotraData.shlokas).forEach(n => {
    const uid = window.stotraData.shlokas[n].unitId;
    if (!uid) return;
    if (idMap[uid] === undefined) idMap[uid] = n;
    const base = dgeStitchBaseId(uid);
    if (idMap[base] === undefined) idMap[base] = n;
  });

  dgeStitch = { role: 'mula', granthaRel: parent, granthaTitle: entry.title || '',
                layers, idMap, loadsInFlight: 0 };

  // Auto-select the PRIMARY layer so the grantha opens showing real text.
  // Found the hard way (project lead's first phone test, 25 Aug night): on
  // a pratīka-spine grantha like Nyāya Sudhā the commentary IS the content,
  // and with selectedCommentaries starting empty the page looked empty —
  // the 💬 picker sits inside the collapsed mobile top bar where nobody
  // finds it. भाष्यम् wins where present (it is the grantha's own bhāṣya);
  // otherwise the layer with the widest coverage (manifest order). Only
  // when nothing else is selected — an explicit reader choice always wins.
  if (window.selectedCommentaries && window.selectedCommentaries.size === 0) {
    const keys = Object.keys(layers);
    const primary = layers['bhashya'] ? 'bhashya' : keys[0];
    window.selectedCommentaries.add(primary);
    dgeStitch.autoSelected = primary;
  }
  console.log(`[Stitch] ${parent}: advertised ${Object.keys(layers).length} sibling layer(s)` +
    (dgeStitch.autoSelected ? `, auto-selected "${dgeStitch.autoSelected}"` : ''));
};

// The stitched layer keys a card's tab bar should offer even before they
// are selected/loaded — render.js draws these as tappable pills so the
// reader can SEE what exists and load a layer with one tap, the way the
// source site's own pill row works. Ordered as the manifest ordered them
// (widest coverage first).
window.dgeStitchedAvailableKeys = function() {
  if (!dgeStitch || dgeStitch.role !== 'mula') return [];
  return Object.keys(dgeStitch.layers);
};

// Fetch + merge every selected-but-pending stitched layer, then re-render.
// Called after every selection change (render.js). Concurrent calls are
// safe: a layer in 'loading' is skipped, and the re-render happens once
// per resolved fetch.
window.dgeEnsureStitchedLayers = function() {
  if (!dgeStitch || dgeStitch.role !== 'mula') return;
  const wanted = Object.keys(dgeStitch.layers).filter(k =>
    dgeStitch.layers[k].state === 'pending' &&
    (window.selectedCommentaries && window.selectedCommentaries.has(k)));
  if (!wanted.length) return;
  // The bigger layers are megabytes (tika_vakyartharatnamala: 9.7 MB) —
  // say so instead of leaving an unexplained empty tab while it downloads.
  if (typeof showToast === 'function') {
    showToast('⏳ Loading ' + wanted.map(k => dgeStitch.layers[k].label).join(', ') + '…');
  }
  wanted.forEach(key => {
    const layer = dgeStitch.layers[key];
    layer.state = 'loading';
    dgeStitch.loadsInFlight++;
    const url = 'data/' + dgeStitch.granthaRel + '/' + layer.folder + '/data.json?t=' + Date.now();
    fetch(url)
      .then(res => { if (!res.ok) throw new Error('HTTP ' + res.status); return res.json(); })
      .then(data => { dgeMergeStitchedLayer(key, layer, data); })
      .catch(err => {
        console.error(`[Stitch] failed to load ${layer.folder}:`, err);
        layer.state = 'error';
        if (typeof showToast === 'function') showToast(`Could not load ${layer.label} — check your connection and try again.`);
      })
      .then(() => {
        dgeStitch.loadsInFlight--;
        // Re-render whether this fetch merged or failed, so the loading
        // placeholder never outlives the request that showed it.
        if (typeof dgeRescrollToActiveCard === 'function') dgeRescrollToActiveCard();
        else if (typeof renderList === 'function') renderList();
      });
  });
};

function dgeMergeStitchedLayer(key, layer, data) {
  const items = (data && Array.isArray(data.items)) ? data.items : [];
  let merged = 0, unmatched = 0;
  items.forEach(item => {
    const n = dgeStitch.idMap[item.id] !== undefined
      ? dgeStitch.idMap[item.id]
      : dgeStitch.idMap[dgeStitchBaseId(item.id)];
    if (n === undefined) { unmatched++; return; }
    let text = item.sanskrit_text || item.text || '';
    // Every tika item repeats the site's own layer heading as its first
    // line ("परिमळ\n..."); the tab label already says it. Strip ONLY a
    // short heading line that matches the label — never body text.
    const nl = text.indexOf('\n');
    if (nl > 0 && nl <= layer.label.length + 12) {
      const first = text.slice(0, nl).trim();
      if (first === layer.label || first.indexOf(layer.label) !== -1 || layer.label.indexOf(first) !== -1) {
        text = text.slice(nl + 1);
      }
    }
    if (!text.trim()) return;
    const sh = window.stotraData.shlokas[n];
    if (!sh.commentaries) sh.commentaries = {};
    // Several layer items can land on one spine item (the -N suffix case);
    // keep them all, in file order.
    sh.commentaries[key] = sh.commentaries[key] ? sh.commentaries[key] + '\n\n' + text : text;
    merged++;
  });
  layer.state = 'loaded';
  layer.unmatched = unmatched;
  console.log(`[Stitch] ${layer.folder}: merged ${merged} item(s) into spine` +
    (unmatched ? `, ${unmatched} had no matching spine id (skipped, see verify_extract.py warnings)` : ''));
}

// ---------- chrome: lineage strip + standalone-tika banner ----------

// Called from renderStotraChrome (core.js) so it re-renders on every
// script change like the rest of the chrome.
window.dgeRenderStitchChrome = function() {
  const strip = document.getElementById('lineageStrip');
  if (!strip) return;
  const t = (s) => (typeof applyTransliteration === 'function' && window.activeScript)
    ? applyTransliteration(s, window.activeScript) : s;

  const parts = [];
  if (dgeStitch && dgeStitch.role === 'tika') {
    // A standalone tika/commentary layer only ever said "this part of
    // GRANTHA's LAYER" -- no indication of which top-level taxonomy branch
    // (darshana/vedanta/dvaita/... etc.) that grantha itself lives under,
    // confirmed live as a real gap: the reader has no way to tell a Dvaita
    // commentary from an Advaita one here without leaving the page. The
    // segments above the grantha's own directory (darshana, vedanta,
    // dvaita, DvaitaVedanta, purana_prasthana, ...) are prepended using the
    // exact same per-segment label table library.js's own Library tree and
    // global-search.js's category chips already read from -- real taxonomy
    // signal already encoded in the path, not a second guessed-at label
    // source, and not a competing breadcrumb component (dge-breadcrumb.js
    // is a page-header brand breadcrumb, out of scope for the reader's own
    // in-content chrome -- see that file's own header comment).
    //
    // 29 Aug 2026: these used to be plain, non-clickable <span>s -- real
    // taxonomy signal shown but dead weight to tap, confirmed by reading
    // this exact code (not a guess). Each is now a real link to the
    // Library browser drilled to that node (window.dgeOpenLibraryToPath,
    // wired via index.html's own ?libraryPath= handling in core.js) --
    // there's no data.json for an ancestor CATEGORY to open as a reader
    // page the way a leaf grantha's own link below does, so the Library
    // modal is the honest navigation target, not a second mechanism.
    if (dgeStitch.granthaRel && typeof window.dgeSegLabel === 'function') {
      const segs = dgeStitch.granthaRel.split('/');
      segs.pop(); // the grantha itself is shown just below via its own link/title
      let cum = '';
      segs.forEach(seg => {
        cum = cum ? cum + '/' + seg : seg;
        parts.push(`<a class="lineage-link" href="index.html?libraryPath=${encodeURIComponent(cum)}">${window.dgeSegLabel(seg, cum)}</a>`);
      });
    }
    // Standalone commentary layer: the way back to the stitched grantha.
    parts.push(`<span class="lineage-note">${t('अयं ग्रन्थभागः')} — </span>` +
      `<a class="lineage-link" href="index.html?path=${encodeURIComponent(dgeStitch.mulaSlug)}">` +
      `${t(dgeStitch.granthaTitle || 'सम्पूर्णग्रन्थः')}</a>` +
      `<span class="lineage-note"> ${t('इत्यस्य')} ${t(dgeStitch.layerLabel || '')} </span>`);
  } else {
    const rel = dgeStitch ? dgeStitch.granthaRel
      : (window.currentGranthaSlug || '').replace(/\/mula$/, '');
    const chain = DGE_GRANTHA_LINEAGE[rel];
    if (chain && chain.length) {
      chain.forEach(link => {
        parts.push(link.slug
          ? `<a class="lineage-link" href="index.html?path=${encodeURIComponent(link.slug)}">${t(link.label)}</a>`
          : `<span class="lineage-node">${t(link.label)}</span>`);
      });
      const ownTitle = (window.stotraData && window.stotraData.metadata && window.stotraData.metadata.title) || '';
      parts.push(`<span class="lineage-node lineage-current">${t(ownTitle)}</span>`);
    } else if (rel && typeof window.dgeSegLabel === 'function') {
      // 9 Sep 2026, the lead: "every item rendered from library should have
      // breadcrumb without miss." DGE_GRANTHA_LINEAGE above is a hand-written
      // table covering five granthas, so every OTHER mula -- 987 of the 1,280
      // populated library.json entries, jayanti_nirnaya among them -- fell to
      // the empty `parts` below and rendered no strip at all. The taxonomy is
      // already in the path; walk it exactly the way the tika branch does,
      // rather than waiting for someone to hand-write another table entry.
      const segs = rel.split('/');
      const leaf = segs.pop(); // shown as the current node, not as a link
      let cum = '';
      segs.forEach(seg => {
        cum = cum ? cum + '/' + seg : seg;
        parts.push(`<a class="lineage-link" href="index.html?libraryPath=${encodeURIComponent(cum)}">${window.dgeSegLabel(seg, cum)}</a>`);
      });
      // The label table first, metadata.title only as a fallback: this node is
      // the GRANTHA folder, whereas metadata.title describes the layer being
      // read, and on the many entries whose data.json carries no title core.js
      // synthesises one from the folder -- karma_nirnaya's reads "Mula". The
      // table's कर्मनिर्णयः is both right and transliterable by the script toggle.
      const ownTitle = window.dgeSegLabel(leaf, rel)
        || (window.stotraData && window.stotraData.metadata && window.stotraData.metadata.title) || '';
      parts.push(`<span class="lineage-node lineage-current">${t(ownTitle)}</span>`);
    }
  }
  if (parts.length) {
    strip.innerHTML = parts.join('<span class="lineage-sep">→</span>');
    strip.style.display = 'flex';
  } else {
    strip.style.display = 'none';
  }
};

// ---------- section navigator (adhyaya > pada > adhikarana) ----------

// Built from the per-item breadcrumb the importer already stores:
// [grantha, layer, adhyaya, pada, adhikarana, topic, unit]. The first two
// levels name the book, the last names the unit itself; everything
// between is the structural path. Grouping on up to the first THREE
// structural levels gives exactly the adhikarana picker a Dvaita reader
// expects on nyaya_sudha (अध्याय > पाद > अधिकरण) and degrades gracefully
// on shallower texts (gita_bhashya: adhyaya only). Does nothing when
// breadcrumbs are absent (every non-DvaitaVedanta text) or there is only
// one section to pick.
window.dgeInitSectionNav = function() {
  const row = document.getElementById('sectionNavRow');
  const select = document.getElementById('sectionNavSelect');
  if (!row || !select) return;
  row.style.display = 'none';
  select.innerHTML = '';
  // A fresh grantha starts unfiltered; the flag says which of the two
  // dropdown behaviours (filter vs jump) this text uses.
  window.dgeSectionFilterKey = null;
  window.dgeSectionNavIsFilter = false;
  if (!window.stotraData || !window.stotraData.shlokas) return;

  const t = (s) => (typeof applyTransliteration === 'function' && window.activeScript)
    ? applyTransliteration(s, window.activeScript) : s;
  const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;')
    .replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const order = Object.keys(window.stotraData.shlokas).map(Number).sort((a, b) => a - b);

  // MODE A — category headings (Tīrthaprabandha: kṣetra/deity like "गङ्गा",
  // "श्रीरङ्गम्"). When items carry a `category`, the dropdown FILTERS to the
  // chosen heading (the project lead's ask: "categories … in a drop-down and
  // filterable"), showing only that heading's verses. One "all" option clears
  // it. A count beside each heading makes the "8 ślokas under Gaṅgā" grouping
  // legible at a glance.
  const cats = [];      // [{key, count}] in reading order
  const catSeen = {};
  order.forEach(n => {
    const c = window.stotraData.shlokas[n].category;
    if (!c) return;
    if (catSeen[c] === undefined) { catSeen[c] = cats.length; cats.push({ key: c, count: 0 }); }
    cats[catSeen[c]].count++;
  });
  if (cats.length >= 2) {
    window.dgeSectionNavIsFilter = true;
    let html = `<option value="">${t('सर्वाणि')} (${order.length})</option>`;
    cats.forEach(c => {
      html += `<option value="${esc(c.key)}">${t(c.key)} (${c.count})</option>`;
    });
    select.innerHTML = html;
    row.style.display = 'flex';
    return;
  }

  // MODE B — structural breadcrumb sections (nyaya_sudha अध्याय > पाद >
  // अधिकरण, gita_bhashya adhyaya): the dropdown JUMPS to a section's first
  // verse, unchanged from the original navigator.
  const groups = []; // [{path:[...], firstN}], in reading order
  const seen = {};
  order.forEach(n => {
    const crumbs = window.stotraData.shlokas[n].breadcrumb;
    if (!Array.isArray(crumbs) || crumbs.length < 4) return;
    const path = crumbs.slice(2, -1).slice(0, 3);
    if (!path.length) return;
    const keyStr = path.join('>');
    if (seen[keyStr] === undefined) {
      seen[keyStr] = groups.length;
      groups.push({ path, firstN: n });
    }
  });
  if (groups.length < 2) return;

  // <optgroup> per parent path (adhyaya · pada), one <option> per deepest
  // section — native, keyboard/mobile friendly, no new popup plumbing.
  let html = `<option value="">${t('विभागं चिनुत')}…</option>`;
  let openGroup = null;
  groups.forEach(g => {
    const parent = g.path.slice(0, -1).join(' · ');
    const leafLabel = g.path[g.path.length - 1];
    if (parent !== openGroup) {
      if (openGroup !== null) html += '</optgroup>';
      if (parent) html += `<optgroup label="${t(parent)}">`;
      openGroup = parent;
    }
    html += `<option value="${g.firstN}">${t(leafLabel)}</option>`;
  });
  if (openGroup) html += '</optgroup>';
  select.innerHTML = html;
  row.style.display = 'flex';
};

window.dgeJumpToSection = function(value) {
  if (!window.stotraData || !window.stotraData.shlokas) return;

  // Filter mode (category texts): constrain the list to the chosen heading
  // via the shared filter pipeline (getFilteredIds reads dgeSectionFilterKey)
  // and re-render, rather than jumping. Empty value = show all.
  if (window.dgeSectionNavIsFilter) {
    window.dgeSectionFilterKey = value || null;
    window.dgeListPage = 0;
    if (typeof renderList === 'function') renderList();
    const list = document.getElementById('shlokaList') || document.querySelector('.shloka-list');
    if (list) list.scrollIntoView({ behavior: 'smooth', block: 'start' });
    return;
  }

  // Jump mode (structural sections): scroll to the section's first verse.
  const n = parseInt(value, 10);
  if (!n || !window.stotraData.shlokas[n]) return;
  window.currentReadingId = n;
  if (window.viewMode !== 'single' && typeof getFilteredIds === 'function') {
    const fIds = getFilteredIds();
    const idx = fIds.indexOf(n);
    const pageSize = window.DGE_LIST_PAGE_SIZE || 50;
    if (idx >= 0) window.dgeListPage = Math.floor(idx / pageSize);
  }
  if (typeof renderList === 'function') renderList();
  const el = document.getElementById('shloka-' + n);
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
};

// ---------- volume navigator (sarga / kanda / amsha siblings) ----------

// Some granthas are split across numbered sibling folders, one data.json each:
// sumadhva_vijaya/sarga_1..sarga_16, shatapatha_brahmana/kanda_01..., 
// vishnu_purana/amsha_01... Only the volume being read is ever fetched, which
// is what keeps a 992-verse kavya off a single page -- but until now the only
// way from sarga 3 to sarga 4 was back out through the Library.
//
// The lead, 9 Sep 2026, on Sumadhva Vijaya: "it should be filterable sarga
// wise . total 16 sargas. at a time only 1 sarga should load."
//
// Siblings come from library.json rather than a guessed URL, so a volume that
// is registered but not yet populated still lists (and says so) instead of
// leading a reader to an empty page they cannot explain.
const DGE_VOLUME_WORDS = ['sarga', 'kanda', 'amsha', 'adhyaya', 'parva', 'ullasa',
                          'taranga', 'pariccheda', 'stabaka', 'mandala', 'ashtaka',
                          'khanda', 'prapathaka', 'anuvaka', 'canto'];
const DGE_VOLUME_RE = new RegExp('^(' + DGE_VOLUME_WORDS.join('|') + ')_(\\d+)$', 'i');

window.dgeGoToVolume = function(slug) {
  if (slug) window.location.href = 'index.html?path=' + encodeURIComponent(slug);
};

window.dgeInitVolumeNav = async function() {
  const row = document.getElementById('volumeNavRow');
  const select = document.getElementById('volumeNavSelect');
  const count = document.getElementById('volumeNavCount');
  if (!row || !select) return;
  row.style.display = 'none';
  select.innerHTML = '';

  const slug = window.currentGranthaSlug || '';
  const segs = slug.split('/').filter(Boolean);
  const leaf = segs[segs.length - 1] || '';
  const match = leaf.match(DGE_VOLUME_RE);
  if (!match) return;
  const parent = segs.slice(0, -1).join('/');
  if (!parent) return;

  const library = await (window.dgeLibraryCatalogPromise || Promise.resolve(null));
  const granthas = (library && library.granthas) || [];
  const siblings = [];
  granthas.forEach(g => {
    const rel = String(g.path || '').replace(/^dge\/data\//, '').replace(/\/data\.json$/, '');
    const parts = rel.split('/');
    if (parts.slice(0, -1).join('/') !== parent) return;
    const m = (parts[parts.length - 1] || '').match(DGE_VOLUME_RE);
    if (!m) return;
    siblings.push({ slug: rel, word: m[1].toLowerCase(), n: parseInt(m[2], 10),
                    populated: g.populated !== false });
  });
  if (siblings.length < 2) return;
  siblings.sort((a, b) => a.n - b.n);

  const t = (s) => (typeof applyTransliteration === 'function' && window.activeScript)
    ? applyTransliteration(s, window.activeScript) : s;
  const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;')
    .replace(/</g, '&lt;').replace(/>/g, '&gt;');
  // The label the Library tree already uses for this folder, so the two agree.
  const label = (s) => (typeof window.dgeSegLabel === 'function')
    ? window.dgeSegLabel(s.slug.split('/').pop(), s.slug)
    : s.word + ' ' + s.n;

  select.innerHTML = siblings.map(s =>
    `<option value="${esc(s.slug)}"${s.slug === slug ? ' selected' : ''}>` +
    `${esc(label(s))}${s.populated ? '' : ' — ' + t('अनुपलब्धम्')}</option>`).join('');
  if (count) {
    const shown = (window.stotraData && window.stotraData.shlokas)
      ? Object.keys(window.stotraData.shlokas).length : 0;
    count.textContent = `${siblings.length} ${siblings[0].word}` +
      (shown ? ` · ${shown} ${t('श्लोकाः')}` : '');
  }
  row.style.display = 'flex';
};
