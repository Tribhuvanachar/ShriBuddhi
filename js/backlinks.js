/* =========================================================================
   "Who discusses this verse?"

   The corpus already knows. Every commentary that comments on a sūtra says so
   in its own references[].target, and build_search_index.py inverts all of
   them into search_index/backlinks.json — 22,929 pointers. Until now nothing
   in the reader showed them, so a student reading a sūtra had no way to learn
   that seven commentaries discuss it, or to get to any of them.

   Each verse that is cited now carries a small mark saying how many texts
   discuss it. Tapping it lists them by name, and each one opens that
   commentary at that same verse.

   COVERAGE IS WHAT THE CORPUS STATES, which today is the Aṣṭādhyāyī
   sūtrapāṭha, the Kāśikā and the Anuvyākhyāna — the only texts whose data
   files carry reference targets. Everything else shows no marks at all, which
   is the honest result rather than a bug. Adding targets to more texts and
   rerunning build_search_index.py and shard_backlinks.py widens it with no
   change here.

   Costs nothing where there is nothing: a grantha with no shard fetches one
   small index and stops.
   ========================================================================= */
(function () {
  'use strict';

  window.DGE_VERSIONS = window.DGE_VERSIONS || {};
  window.DGE_VERSIONS['backlinks.js'] = 'v1.0 (which commentaries discuss this verse)';

  const self = (document.currentScript && document.currentScript.src) || '';
  function url(rel) {
    try { return new URL('../search_index/backlinks/' + rel, self).href; }
    catch (e) { return 'search_index/backlinks/' + rel; }
  }

  const esc = (s) => String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');

  const tr = (t) => (typeof window.dgeToActiveScript === 'function')
    ? window.dgeToActiveScript(t) : t;

  let indexPromise = null;
  function loadIndex() {
    if (!indexPromise) {
      indexPromise = fetch(url('index.json'), { cache: 'force-cache' })
        .then(r => (r.ok ? r.json() : null)).catch(() => null);
    }
    return indexPromise;
  }

  let shard = null;          // { sources, units, odd } for the current grantha
  let titles = {};

  function loadShard(slug) {
    return loadIndex().then(function (ix) {
      if (!ix || !ix.cited || !(slug in ix.cited)) return null;
      titles = ix.titles || {};
      return fetch(url(slug.replace(/\//g, '__') + '.json'), { cache: 'force-cache' })
        .then(r => (r.ok ? r.json() : null)).catch(() => null);
    });
  }

  /* The shard stores a unit as indices into its own sources list, with
     anything irregular kept separately — see tools/shard_backlinks.py. This
     puts the two back together. */
  function citationsFor(unit) {
    if (!shard) return [];
    const out = [];
    (shard.units[unit] || []).forEach(function (i) {
      const s = shard.sources[i];
      if (s) out.push({ slug: s, unit: unit, note: 'comments_on' });
    });
    ((shard.odd || {})[unit] || []).forEach(function (row) {
      const s = shard.sources[row[0]];
      if (s) out.push({ slug: s, unit: row[1] || unit, note: row[2] || '' });
    });
    return out;
  }

  function label(slug) {
    return titles[slug] || slug.split('/').pop().replace(/_/g, ' ');
  }

  /* ----------------------------------------------------------- popover --- */
  let pop = null;
  function close() { if (pop) { pop.remove(); pop = null; } }

  function open(anchor, unit) {
    close();
    const rows = citationsFor(unit);
    if (!rows.length) return;
    pop = document.createElement('div');
    // Deliberately the intellisense popover's own class: a reader should not
    // have to learn two different panels that do the same kind of thing.
    pop.className = 'dge-si-pop';
    pop.innerHTML =
      '<div class="dge-si-head"><span class="dge-si-id">' + esc(unit) + '</span>' +
      '<span class="dge-si-type">' + rows.length + '</span>' +
      '<button class="dge-si-x" data-bl-close aria-label="Close">✕</button></div>' +
      '<div class="dge-si-row"><b>व्याख्यातारः</b></div>' +
      rows.map(function (r) {
        return '<a class="dge-bl-item" href="index.html?path=' + encodeURIComponent(r.slug) +
               '&jumpVedicId=' + encodeURIComponent(r.unit) + '">' +
               '<span class="dge-bl-name">' + esc(tr(label(r.slug))) + '</span>' +
               (r.note && r.note !== 'comments_on'
                  ? '<span class="dge-bl-note">' + esc(r.note) + '</span>' : '') +
               '</a>';
      }).join('');
    document.body.appendChild(pop);

    const r = anchor.getBoundingClientRect();
    const w = pop.offsetWidth;
    let left = Math.max(8, Math.min(r.left + r.width / 2 - w / 2, window.innerWidth - w - 8));
    const h = pop.offsetHeight;
    const top = (r.bottom + 8 + h > window.innerHeight - 8 && r.top - h - 8 > 8)
      ? r.top - h - 8 : r.bottom + 8;
    pop.style.left = left + 'px';
    pop.style.top = Math.max(8, Math.min(top, window.innerHeight - h - 8)) + 'px';
  }

  document.addEventListener('click', function (ev) {
    const mark = ev.target.closest && ev.target.closest('.dge-bl-mark');
    if (mark) { ev.stopPropagation(); open(mark, mark.dataset.unit); return; }
    if (ev.target.closest && ev.target.closest('[data-bl-close]')) { close(); return; }
    if (pop && !ev.target.closest('.dge-si-pop')) close();
  });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') close(); });
  window.addEventListener('resize', close);

  /* -------------------------------------------------------- decoration --- */
  /* renderList() keys cards by a sequential index and keeps the real
     reference on the shloka as vedicId (see the normalizer in core.js), so
     the card number is not the id the backlinks are filed under. */
  function decorate() {
    if (!shard) return;
    const data = window.stotraData;
    if (!data || !data.shlokas) return;
    document.querySelectorAll('#shlokaList .shloka-card').forEach(function (card) {
      if (card.querySelector('.dge-bl-mark')) return;
      const n = card.id.split('-')[1];
      const sh = data.shlokas[n];
      const unit = sh && sh.vedicId;
      if (!unit) return;
      const rows = citationsFor(unit);
      if (!rows.length) return;
      const row = card.querySelector('.shloka-main-row');
      if (!row) return;
      const mark = document.createElement('button');
      mark.className = 'dge-bl-mark';
      mark.dataset.unit = unit;
      mark.title = rows.length + ' text(s) discuss this';
      mark.innerHTML = '<span class="dge-bl-dot"></span>' + rows.length;
      row.appendChild(mark);
    });
  }
  window.dgeDecorateBacklinks = decorate;

  /* -------------------------------------------------------------- boot --- */
  function start() {
    const slug = window.currentGranthaSlug;
    if (!slug) return;
    loadShard(slug).then(function (s) {
      if (!s || !s.units) return;
      shard = s;
      decorate();
      const list = document.getElementById('shlokaList');
      if (!list) return;
      // renderList() rebuilds the list on every script, theme and view change,
      // which drops the marks; debounced because one rebuild fires many
      // mutations.
      let t = null;
      new MutationObserver(function () {
        clearTimeout(t);
        t = setTimeout(decorate, 120);
      }).observe(list, { childList: true });
    });
  }

  // currentGranthaSlug is set during initApp, after this script has parsed.
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { setTimeout(start, 400); });
  } else {
    setTimeout(start, 400);
  }
})();
