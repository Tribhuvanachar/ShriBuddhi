// DGE Module: render.js
// js/render.js
// Maps to F-003 (Rendering) & F-007 (Commentary)
window.DGE_VERSIONS = window.DGE_VERSIONS || {};
window.DGE_VERSIONS['render.js'] = 'v5.0 (बन्नञ्जे-पाठः: a verse carrying an alternate mula reading shows a chip that reveals it inline, marked when the two recensions genuinely disagree rather than merely spell differently; an alternate mula is never rendered as a commentary. v4.9 (list view paged at 25 by default, 10/25/50/100 from the page bar, page bar repeated below the list, dgeListPageFor lands a jump on its page. v4.8: verse card carries only the verse: fav/doubt as the card edge, counts under the number, copy in the ⋯ menu for everyone; dgePadaBreak breaks the mūla into pāda lines from the chandas engine. v4.7: unloaded stitched layers render as tappable dashed pills on each card, capped at 6 + overflow into the picker; v4.6: stitched sibling-layer commentaries: setCommentaryView/dgeToggleCommentarySelection kick off dgeEnsureStitchedLayers (layer-stitch.js) so a just-selected layer\'s sibling data.json is fetched and merged on demand; LIST_PAGE_SIZE exposed as window.DGE_LIST_PAGE_SIZE for the section-navigator jump. Everything from v4.5 -- Gold-Standard render path -- unchanged)';

// 7 Sep 2026: verse text broken into its pādas for display (the lead: "as a
// thumb rule, every shloka should render in two lines or 4 as per their
// vṛtta"). The chandas engine (chandas.js, DGEChandas) scans the Devanagari
// once per distinct verse text (cached); when it names a metre, a line
// break goes after every pāda for pādas longer than 8 syllables (4 lines)
// and only at the half-verse for anuṣṭubh-length pādas (2 lines). Speaker
// tags ("… उवाच |") get their own line. Breaks are inserted only where the
// text has none already, and only when every syllable aligns with the
// source -- any doubt and the text is returned untouched.
const _dgePadaCache = new Map();
function dgePadaBreak(sa) {
  if (typeof sa !== 'string' || !sa || !(window.DGEChandas && window.DGEChandas.ready && window.DGEChandas.ready())) return sa;
  if (_dgePadaCache.has(sa)) return _dgePadaCache.get(sa);
  let out = sa;
  try {
    let pre = '', body = sa;
    const pm = sa.match(/^([\s\S]*?(?:उवाच|ऊचुः)\s*[|।॥]*[ \t]*(?:<br\s*\/?>|\n)?)/);
    if (pm) {
      pre = pm[1]; body = sa.slice(pre.length);
      if (!/\n|<br/i.test(pre)) pre = pre.replace(/\s*$/, '') + '\n';
    }
    const res = window.DGEChandas.analyzeText(body);
    const padas = (res && res.padas) || [];
    if (res && res.match && (padas.length === 2 || padas.length === 4) && padas.every(p => p.sylls && p.sylls.length)) {
      const perPada = padas.length === 4 && padas[0].aksharas > 8;   // 4 lines for long metres, 2 for anuṣṭubh-length
      const LETTER = /[\u0904-\u0939\u0958-\u0961]/;              // a skipped consonant/vowel = misalignment
      let pos = 0, result = '';
      for (let k = 0; k < padas.length; k++) {
        const target = padas[k].sylls.map(sy => sy.text + (sy.coda || '')).join('');
        let ti = 0;
        while (pos < body.length && ti < target.length) {
          const ch = body[pos];
          if (ch === target[ti]) ti++;
          else if (LETTER.test(ch)) throw new Error('align');
          result += ch; pos++;
        }
        if (ti < target.length) throw new Error('short');
        const breakHere = k < padas.length - 1 && (perPada || k === 1);
        if (breakHere) {
          const tail = body.slice(pos).match(/^(?:[ \t]*(?:[|।॥\-]|<br\s*\/?>|\n))*[ \t]*/);
          const run = tail ? tail[0] : '';
          result += run; pos += run.length;
          if (!/\n|<br/i.test(run)) result = result.replace(/[ \t]+$/, '') + '\n';
        }
      }
      result += body.slice(pos);
      out = pre + result;
    } else if (pre) {
      out = pre + body;
    }
  } catch (e) { out = sa; }
  _dgePadaCache.set(sa, out);
  return out;
}
window.dgePadaBreak = dgePadaBreak;
// The metre table loads asynchronously; the first render can come before it
// is in. One re-render once it lands (chandas-check.js / kavya.js load it on
// demand; the reader asks for it here so the breaks appear on first read).
(function () {
  let tries = 0;
  const kick = () => {
    if (window.DGEChandas && window.DGEChandas.ready && window.DGEChandas.ready()) { if (typeof renderList === 'function' && window.stotraData) renderList(); return; }
    if (window.DGEChandas && window.DGEChandas.loadDB && tries === 0) window.DGEChandas.loadDB('').catch(() => {});
    if (++tries < 40) setTimeout(kick, 500);
  };
  document.addEventListener('DOMContentLoaded', () => setTimeout(kick, 300));
})();

const DGE_LAKARA_SHORT = { Lat: 'लट्', Lit: 'लिट्', Lut: 'लुट्', Lrt: 'लृट्', Lot: 'लोट्', Lan: 'लङ्', VidhiLin: 'विधिलिङ्', AshirLin: 'आशीर्लिङ्', Lun: 'लुङ्', Lrn: 'लृङ्' };
function dgeDhatuChipsHtml(id, shloka) {
  const hits = window.dgeDhatuHits;
  if (!hits || (typeof dgeGetEffectiveFeatureFlags === 'function' && dgeGetEffectiveFeatureFlags().showDhatuChips === false)) return '';
  const keys = [String(id)];
  if (shloka.unitId) { keys.push(shloka.unitId); if (shloka.unitNo) keys.push(shloka.unitId + '#' + shloka.unitNo); }
  let list = null;
  for (const k of keys) { if (hits[k]) { list = hits[k]; break; } }
  if (!list || !list.length) return '';
  const chips = list.slice(0, 12).map(h => {
    // `amb` was a 0/1 flag and is now the NUMBER of roots that write this
    // spelling (build_dhatu_prayoga_index.py, 10 Sep 2026); `alts` lists the
    // others. Both readings of the old shape still work: 1 is falsy-adjacent
    // only in that a certain chip carries no fourth element at all.
    const [word, code, key, amb, alts] = h;
    const krt = key.indexOf('krt:') === 0;
    const page = krt ? 'krdanta' : 'prakriya';
    const cell = krt ? key.slice(4) : key;
    const lak = krt ? 'कृदन्त' : (DGE_LAKARA_SHORT[key.split('.')[0]] || key.split('.')[0]);
    return `<a class="dge-dhatu-chip${amb ? ' amb' : ''}" href="vyakarana/${page}.html#${code}:${cell}" onclick="event.stopPropagation()" ` +
      `title="धातुः ${code} · ${lak}${amb > 1 ? ` · this spelling is also a form of ${amb - 1} other root${amb > 2 ? 's' : ''}${Array.isArray(alts) && alts.length ? ' (' + alts.join(', ') + ')' : ''} — shown here as the one this library attests most` : (amb ? ' · also reads as another word' : '')}">${word}<small>${lak}</small></a>`;
  }).join('');
  return `<div class="dge-dhatu-row" title="धातुरूपाणि in this verse — tap a form for its derivation and other uses">${chips}${list.length > 12 ? `<span class="dge-dhatu-more">+${list.length - 12}</span>` : ''}</div>`;
}

function getText(id) {
  if (!stotraData || !stotraData.shlokas[id]) return `श्लोक ${id}`;
  // Safely check if transliteration module is loaded
  return typeof applyTransliteration === 'function' 
    ? applyTransliteration(stotraData.shlokas[id].sa, activeScript)
    : stotraData.shlokas[id].sa;
}

// renderList() in "Full List" (📜) mode used to build one full DOM card per
// matching shloka with no limit at all -- fine for something PNS-sized (43),
// but genuinely froze/crashed a phone on a large grantha (a 2000-shloka
// Rigveda maṇḍala's "Full List" view being the reported case). core.js
// already forces single-view as the DEFAULT for anything over 150 shlokas,
// but that is only a nudge: the reader can still tap "📜 Full List" in the
// Display menu and get the exact same unbounded render. This is the actual
// safety net -- list mode never builds more than LIST_PAGE_SIZE cards at
// once, with Prev/Next paging through the rest.
// 7 Sep 2026: the page size is the reader's own (25 by default, 10/25/50/100
// from the page bar, remembered per device) -- the lead asked for the Vedas
// "as a list with default paging enabled, 25 per page and adjustable".
const DGE_LIST_PAGE_SIZES = [10, 25, 50, 100];
function dgeListPageSize() {
  try {
    const n = parseInt(localStorage.getItem('app_listPageSize'), 10);
    if (DGE_LIST_PAGE_SIZES.indexOf(n) !== -1) return n;
  } catch (e) { /* ignore */ }
  return 25;
}
window.dgeListPageSize = dgeListPageSize;
// Exposed for layer-stitch.js's section-navigator jump, which must land
// the target card's page before scrolling to it.
Object.defineProperty(window, 'DGE_LIST_PAGE_SIZE', { get: dgeListPageSize, configurable: true });
// The page that holds a given shloka id in the current filtered list, or
// -1 when it isn't listed -- so a jump (quick jump, search hit, audio
// auto-advance, deep link) can turn to that page before scrolling.
window.dgeListPageFor = function (id) {
  if (window.viewMode === 'single' || typeof getFilteredIds !== 'function') return -1;
  const idx = getFilteredIds().indexOf(id);
  return idx < 0 ? -1 : Math.floor(idx / dgeListPageSize());
};
window.dgeSetListPageSize = function (n) {
  n = parseInt(n, 10);
  if (DGE_LIST_PAGE_SIZES.indexOf(n) === -1) return;
  // Keep the first card on screen where it is: page 3 of 25 becomes page 1 of 100.
  const firstIdx = (window.dgeListPage || 0) * dgeListPageSize();
  try { localStorage.setItem('app_listPageSize', String(n)); } catch (e) { /* ignore */ }
  window.dgeListPage = Math.floor(firstIdx / n);
  renderList();
};

window.currentSearchScope = 'all';
window.setSearchScope = function(scope, label, el) {
  window.currentSearchScope = scope;
  const btn = document.getElementById('searchScopeBtn');
  if (btn) btn.innerText = label;
  document.querySelectorAll('#searchScopePopup .pop-item').forEach(item => item.classList.remove('active'));
  if (el) el.classList.add('active');
  if (typeof togglePopup === 'function') togglePopup('searchScopePopup');
  if (typeof handleSearch === 'function') handleSearch();
};

// Per-card commentary tab switching -- distinct from setCommentaryView()
// above, which is a GLOBAL choice (the 📜 commentary picker) applying to
// every shloka card at once. This is local to one card: every selected
// commentary is already rendered in the DOM (setCommentaryView/'all'
// decided that), this just shows/hides the already-rendered blocks, so
// switching tabs never re-fetches or re-renders anything.
window.dgeShowCommentaryTab = function(shlokaIndex, cKey, btnEl) {
  const container = document.querySelector(`.dge-commentary-tabbed[data-shloka="${shlokaIndex}"]`);
  if (!container) return;
  container.querySelectorAll('.commentary-block[data-ckey]').forEach(block => {
    block.style.display = (cKey === 'all' || block.dataset.ckey === cKey) ? '' : 'none';
  });
  container.querySelectorAll('.dge-commentary-tab').forEach(tab => tab.classList.remove('active'));
  if (btnEl) btnEl.classList.add('active');
};

// The commentary bar, above the verses rather than behind the 💬 icon in the
// top bar. The project lead, on finding a text whose commentaries he had not
// realised were there: the availability notice "disappears too quickly and
// should point to the exact place to click", and the availability and its
// click options belong "above sloka renderings instead of the global menu".
//
// So this replaces a one-shot toast with something that does not go away: the
// names of every commentary this text carries, each one a switch, sitting
// where the reader is already looking. The 💬 picker still works and stays in
// sync -- this is a second, unmissable way in, not a replacement.
//
// Both in-file commentaries (metadata.availableCommentaries) and stitched
// sibling layers (layer-stitch.js) are listed, because from the reader's side
// the difference between "in this file" and "in the folder next door" is not
// one they should have to know about.
function dgeCommentaryBarEntries() {
  const meta = (typeof stotraData !== 'undefined' && stotraData && stotraData.metadata) || {};
  const available = meta.availableCommentaries || {};
  const keys = Object.keys(available);
  if (typeof window.dgeStitchedAvailableKeys === 'function') {
    window.dgeStitchedAvailableKeys().forEach(k => { if (keys.indexOf(k) === -1) keys.push(k); });
  }
  return keys.map(k => {
    const name = available[k] || k;
    return {
      key: k,
      label: typeof applyTransliteration === 'function' ? applyTransliteration(name, activeScript) : name,
      on: typeof selectedCommentaries !== 'undefined' && selectedCommentaries.has(k)
    };
  });
}

function dgeRenderCommentaryBar() {
  const bar = document.getElementById('commentaryAvailableBar');
  if (!bar) return;
  const entries = dgeCommentaryBarEntries();
  if (!entries.length) { bar.style.display = 'none'; bar.innerHTML = ''; return; }
  const onCount = entries.filter(e => e.on).length;
  const pills = entries.map(e =>
    `<button type="button" class="dge-cbar-pill${e.on ? ' on' : ''}" data-ckey="${e.key}" aria-pressed="${e.on}" ` +
    `title="${e.on ? 'Hide' : 'Show'} this commentary under every verse" ` +
    `onclick="dgeToggleCommentarySelection('${e.key}')">${e.label}</button>`).join('');
  // "All"/"None" is one button, not two: whichever of them is the useful
  // next move is the one shown.
  const bulk = onCount === entries.length
    ? `<button type="button" class="dge-cbar-bulk" onclick="window.dgeSetAllCommentaries(false)">✕ hide all</button>`
    : `<button type="button" class="dge-cbar-bulk" onclick="window.dgeSetAllCommentaries(true)">show all ${entries.length}</button>`;
  // The summary is the whole control when collapsed, so it stays short enough
  // for one line on a 400px screen -- a count, not a sentence. The instruction
  // moved into the body, where it is next to the names it is about.
  const lead = onCount
    ? `<span class="dge-cbar-label">📖 भाष्यटीकाः · showing ${onCount} of ${entries.length}</span>`
    : `<span class="dge-cbar-label">📖 भाष्यटीकाः · ${entries.length} commentar${entries.length === 1 ? 'y' : 'ies'}</span>`;
  const hint = onCount ? '' :
    `<span class="dge-cbar-hint">tap a name to read ${entries.length === 1 ? 'it' : 'one'} under each verse</span>`;
  bar.className = 'dge-cbar' + (onCount ? '' : ' dge-cbar-idle');
  // <summary> is the whole control on a phone. A text like the Rigveda has 8
  // commentaries, each pill long enough to take its own row at 400px, so the
  // flat bar pushed the first verse a full screen down. The summary carries
  // the count so the collapsed state still says what is behind it.
  const caret = `<span class="dge-cbar-caret" aria-hidden="true"></span>`;
  bar.innerHTML =
    `<summary class="dge-cbar-summary">${lead}${caret}</summary>` +
    `<div class="dge-cbar-body">${hint}${pills}${entries.length > 1 ? bulk : ''}</div>`;
  bar.style.display = 'block';
  dgeSyncCommentaryBarOpen(bar);
}

// Open on a wide screen, collapsed on a phone -- but never fighting a reader
// who has said otherwise. <details> cannot be forced open from CSS, so the
// `open` attribute is set here; once the reader toggles it themselves that
// choice wins for the rest of the session.
const DGE_CBAR_OPEN_KEY = 'dge_cbar_open';
function dgeSyncCommentaryBarOpen(bar) {
  let stored = null;
  try { stored = sessionStorage.getItem(DGE_CBAR_OPEN_KEY); } catch (e) { /* private mode */ }
  if (stored === '1' || stored === '0') { bar.open = stored === '1'; return; }
  bar.open = window.matchMedia('(min-width: 760px)').matches;
}
window.dgeSyncCommentaryBarOpen = dgeSyncCommentaryBarOpen;

document.addEventListener('toggle', function (e) {
  const bar = e.target;
  if (!bar || bar.id !== 'commentaryAvailableBar') return;
  try { sessionStorage.setItem(DGE_CBAR_OPEN_KEY, bar.open ? '1' : '0'); } catch (err) { /* private mode */ }
}, true);
window.dgeRenderCommentaryBar = dgeRenderCommentaryBar;

// The bar's bulk switch. setCommentaryView() does the same job but also
// closes the 💬 popup, which is wrong when the tap came from the bar and no
// popup is open.
window.dgeSetAllCommentaries = function (on) {
  const available = (typeof stotraData !== 'undefined' && stotraData && stotraData.metadata && stotraData.metadata.availableCommentaries) || {};
  const keys = Object.keys(available);
  if (typeof window.dgeStitchedAvailableKeys === 'function') {
    window.dgeStitchedAvailableKeys().forEach(k => { if (keys.indexOf(k) === -1) keys.push(k); });
  }
  selectedCommentaries = on ? new Set(keys) : new Set();
  dgeSyncCommentaryPopupState();
  if (typeof window.dgeEnsureStitchedLayers === 'function') window.dgeEnsureStitchedLayers();
  dgeRescrollToActiveCard();
};

// Re-anchors the scroll position to the active card after a commentary
// selection change re-renders the list at a new (shorter or taller)
// height -- shared by both the quick actions and the per-item toggle
// below, so collapsing/expanding commentary never strands the viewport
// wherever the old commentary block used to end.
function dgeRescrollToActiveCard() {
  renderList();
  if (typeof activeId !== 'undefined' && activeId) {
    const ac = document.getElementById(`shloka-${activeId}`);
    if (ac) ac.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

// Keeps the popup's own checkmarks in sync with window.selectedCommentaries
// -- called after every change, whether from the quick actions or a
// single checkbox tap, so the UI never drifts from the actual state.
function dgeSyncCommentaryPopupState() {
  const available = (typeof stotraData !== 'undefined' && stotraData && stotraData.metadata && stotraData.metadata.availableCommentaries) || {};
  const total = Object.keys(available).length;
  document.querySelectorAll('#commentaryDynamicList .filter-checkbox-item').forEach(el => {
    el.classList.toggle('active', selectedCommentaries.has(el.dataset.ckey));
  });
  const noneBtn = document.getElementById('commentaryNoneBtn');
  const allBtn = document.getElementById('commentaryAllBtn');
  if (noneBtn) noneBtn.classList.toggle('active', selectedCommentaries.size === 0);
  if (allBtn) allBtn.classList.toggle('active', total > 0 && selectedCommentaries.size === total);
}

// The two quick actions -- "None" clears every selection, "All" selects
// every available commentary at once. Both are one-shot (close the popup);
// individual commentaries are toggled via dgeToggleCommentarySelection
// below instead, which deliberately leaves the popup open so several can
// be picked in one sitting.
window.setCommentaryView = function(view) {
  if (view === 'all') {
    const available = (typeof stotraData !== 'undefined' && stotraData && stotraData.metadata && stotraData.metadata.availableCommentaries) || {};
    selectedCommentaries = new Set(Object.keys(available));
  } else {
    selectedCommentaries = new Set();
  }
  dgeSyncCommentaryPopupState();
  if (typeof togglePopup === 'function') togglePopup('commentaryPopup');
  // Stitched sibling layers (layer-stitch.js) are fetched only when
  // actually selected — kick off any now-needed loads; each re-renders
  // the list again when its data arrives.
  if (typeof window.dgeEnsureStitchedLayers === 'function') window.dgeEnsureStitchedLayers();
  dgeRescrollToActiveCard();
};

// Toggles one commentary in or out of the selection -- any number can be
// on at once. Matches ashtadhyayi.com's own multi-select filter pattern
// used elsewhere in this app (see filter.js's cycleFilterCriterion).
window.dgeToggleCommentarySelection = function(key) {
  if (selectedCommentaries.has(key)) selectedCommentaries.delete(key);
  else selectedCommentaries.add(key);
  dgeSyncCommentaryPopupState();
  // See setCommentaryView above — a just-selected stitched layer may need
  // its sibling data.json fetched before it can render.
  if (typeof window.dgeEnsureStitchedLayers === 'function') window.dgeEnsureStitchedLayers();
  dgeRescrollToActiveCard();
};

// Builds a case-insensitive regex source from a query. For IAST, this
// tolerates both plain-letter-for-diacritic typing (a/ā, i/ī, u/ū, r/ṛ,
// n/ṅ/ñ/ṇ, t/ṭ, d/ḍ, s/ś/ṣ, m/ṃ, h/ḥ) AND common casual-romanization
// clusters (ch→c, sh→ś/ṣ, doubled vowels→long vowels, ri→ṛ) — so
// "uvacha", "uvaaca", or "uvaca" all match displayed "uvāca", and
// "krishna" matches "kṛṣṇa". Built as a single left-to-right scan
// (checking the longest cluster first at each position) rather than
// several chained string replacements, so substitutions never
// double-process each other's output. Covers common cases, not every
// possible spelling.
const IAST_SINGLE_TOLERANT = { a: 'aā', i: 'iī', u: 'uū', r: 'rṛṝ', l: 'lḷ', n: 'nṅñṇ', t: 'tṭ', d: 'dḍ', s: 'sśṣ', m: 'mṃ', h: 'hḥ' };
const IAST_CLUSTER_TOLERANT = [
  { pat: 'chh', out: '(?:chh|ch|c)' },
  { pat: 'ch', out: '(?:ch|c)' },
  { pat: 'sh', out: '(?:sh|ś|ṣ)' },
  { pat: 'aa', out: '(?:aa|ā|a)' },
  { pat: 'ii', out: '(?:ii|ī|i)' },
  { pat: 'uu', out: '(?:uu|ū|u)' },
  { pat: 'ri', out: '(?:ri|ṛ)' }
];
const REGEX_SPECIAL_CHARS = /[.*+?^${}()|[\]\\]/;

function dgeBuildSearchPattern(query) {
  if (window.activeScript !== 'iast') {
    return query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }

  let out = '';
  let i = 0;
  while (i < query.length) {
    const rest = query.slice(i).toLowerCase();
    const cluster = IAST_CLUSTER_TOLERANT.find(c => rest.startsWith(c.pat));
    if (cluster) {
      out += cluster.out;
      i += cluster.pat.length;
      continue;
    }
    const ch = query[i];
    const lower = ch.toLowerCase();
    if (IAST_SINGLE_TOLERANT[lower]) {
      const variants = IAST_SINGLE_TOLERANT[lower];
      out += `[${variants}${variants.toUpperCase()}]`;
    } else if (REGEX_SPECIAL_CHARS.test(ch)) {
      out += '\\' + ch;
    } else {
      out += ch;
    }
    i += 1;
  }
  return out;
}

function dgeTextMatchesQuery(text, pattern) {
  if (!pattern) return false;
  try {
    return new RegExp(pattern, 'i').test(text || '');
  } catch (e) {
    return (text || '').toLowerCase().includes(pattern.toLowerCase());
  }
}

// Resolves a SHLOKA_EXTRA_FIELDS dataKey against a shloka object -- either
// a plain top-level key ('padaccheda') or a dotted path into a nested
// object ('gemini_deep_analysis.pratipadartha'). Returns undefined rather
// than throwing if an intermediate segment is missing (a shloka with no
// gemini_deep_analysis yet is the common case, not an error).
function dgeGetNestedField(shloka, dataKey) {
  if (!dataKey) return undefined;
  return String(dataKey).split('.').reduce((node, key) => (node == null ? undefined : node[key]), shloka);
}

function highlightText(text, pattern) {
  if (!pattern) return text;
  try {
    const regex = new RegExp(`(${pattern})(?![^<]*>|[^<>]*<\\/)`, 'gi');
    return text.replace(regex, '<mark class="search-match">$1</mark>');
  } catch (e) {
    return text;
  }
}

// Word-level tap-to-select fix: gives each word in a shloka's rendered HTML
// its own DOM boundary (an invisible <span>, no styling of its own -- NOT
// a "make every word a link" redesign, which intellisense.js's own
// selectedWord() comment already explains was deliberately rejected as
// turning a page of Sanskrit into a page of underlines). The actual bug
// this fixes: with plain unwrapped text, resolving "which word did the
// reader select" depends entirely on window.getSelection().toString()
// after a native drag/double-tap gesture, which on mobile can jump to a
// shared ancestor and yield truncated or empty text on rapid
// re-selection. With each word's own span as a boundary, ai.js's
// dgeRobustSelectedText() can resolve the tapped word from the DOM
// structure itself instead of trusting that fragile string.
//
// Applied LAST, after highlightText()/footnote-marker injection/the Vedic
// pada-<br> substitution, so it only ever walks the final HTML and never
// has to reason about shifting character offsets those passes depend on.
// Tag-aware (tracks whether it's inside a `<...>` run), so it wraps only
// the actual text -- and correctly nests inside already-present <mark>/
// <sup> tags -- without ever splitting a tag's own markup.
function dgeWrapWordsForTap(html) {
  if (!html) return html;
  let out = '';
  let i = 0;
  const len = html.length;
  while (i < len) {
    if (html[i] === '<') {
      const close = html.indexOf('>', i);
      if (close === -1) { out += html.slice(i); break; }
      out += html.slice(i, close + 1);
      i = close + 1;
    } else {
      let j = i;
      while (j < len && html[j] !== '<') j++;
      out += html.slice(i, j).replace(/(\S+)/g, '<span class="dge-word">$1</span>');
      i = j;
    }
  }
  return out;
}

window.copyShlokaText = async function(id) {
  // The verse, then where it is and its link (share.js) — a pasted verse should say which text it is from.
  const text = typeof dgeShlokaShareText === 'function' ? dgeShlokaShareText(id)
    : (typeof getText === 'function' ? getText(id).replace(/<[^>]*>/g, '') : '');
  if (!text) return;
  try {
    if (navigator.clipboard) {
      await navigator.clipboard.writeText(text);
    } else {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.left = '-9999px';
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      ta.remove();
    }
    if (typeof showToast === 'function') showToast(`Shloka ${id} copied to clipboard.`);
  } catch (e) {
    console.error('Copy failed', e);
    if (typeof showToast === 'function') showToast('Could not copy this text.');
  }
};

function renderList() {
  if(!stotraData) return;
  const listEl = document.getElementById('shlokaList');
  if(!listEl) return;
  
  listEl.innerHTML = '';
  
  // Fetch filtered list if filter.js is loaded, otherwise load all
  const fIds = typeof getFilteredIds === 'function' ? getFilteredIds() : Object.keys(stotraData.shlokas).map(Number);
  
  const searchInput = document.getElementById('searchInput');
  const rawQuery = searchInput ? searchInput.value.trim() : '';
  const pattern = dgeBuildSearchPattern(rawQuery);
  const scope = window.currentSearchScope || 'all';
  const total = stotraData.metadata.totalShlokas || Object.keys(stotraData.shlokas).length;

  window.searchMatches = [];
  window.currentMatchIdx = -1;

  const singleMode = window.viewMode === 'single';

  // See the LIST_PAGE_SIZE comment above -- only paginate list mode, and
  // only once there's actually more than one page's worth to show.
  const LIST_PAGE_SIZE = dgeListPageSize();
  const needsPaging = !singleMode && fIds.length > LIST_PAGE_SIZE;
  let pageIdSet = null;
  if (needsPaging) {
    const maxPage = Math.max(0, Math.ceil(fIds.length / LIST_PAGE_SIZE) - 1);
    window.dgeListPage = Math.min(Math.max(window.dgeListPage || 0, 0), maxPage);
    const start = window.dgeListPage * LIST_PAGE_SIZE;
    pageIdSet = new Set(fIds.slice(start, start + LIST_PAGE_SIZE));
  }

  for (let i = 1; i <= total; i++) {
    if (!fIds.includes(i)) continue;
    if (pageIdSet && !pageIdSet.has(i)) continue;
    if (singleMode && i !== window.currentReadingId) continue;
    const shloka = stotraData.shlokas[i];
    if (!shloka) continue;

    // Transliterate once per shloka, to whatever script is currently
    // active, and reuse for BOTH search matching and display — this is
    // the actual text on screen, which is what a search should match.
    const mulaSrc = dgePadaBreak(shloka.sa);
    const mulaDisplayText = (typeof applyTransliteration === 'function') ? applyTransliteration(mulaSrc, activeScript) : mulaSrc;

    const convertedCommentaries = {};
    if (shloka.commentaries) {
      Object.entries(shloka.commentaries).forEach(([cKey, cText]) => {
        // Gold-Standard commentary (format:gold_v2_2, see
        // dge/GOLD_STANDARD_ARCHITECTURE.md) is an object, not a string --
        // kept as-is here rather than run through applyTransliteration,
        // which expects a plain string. It displays in its authored
        // Devanagari only for now; transliterating structured
        // commentary_markdown (block directives, pratīka markup) to other
        // scripts is a real follow-up, not attempted in this first build.
        if (cText && typeof cText === 'object' && cText.format === 'gold_v2_2') {
          convertedCommentaries[cKey] = cText;
        } else {
          convertedCommentaries[cKey] = typeof applyTransliteration === 'function' ? applyTransliteration(cText, activeScript) : cText;
        }
      });
    }

    // Search matching against a Gold-Standard commentary reads its raw
    // commentary_markdown string -- dgeTextMatchesQuery expects a string,
    // and this is the same text a legacy commentary would have carried.
    const dgeGoldSearchableText = (cText) => (cText && typeof cText === 'object') ? (cText.commentary_markdown || '') : cText;

    let forceCommentaries = [];
    let hasMatch = false;

    if(rawQuery) {
      if(scope === 'all') {
        hasMatch = i.toString().includes(rawQuery) || dgeTextMatchesQuery(mulaDisplayText, pattern);
        Object.entries(convertedCommentaries).forEach(([cKey, cText]) => {
          if (dgeTextMatchesQuery(dgeGoldSearchableText(cText), pattern)) {
            forceCommentaries.push(cKey);
            hasMatch = true;
          }
        });
      } else if(scope === 'mula') {
        hasMatch = i.toString().includes(rawQuery) || dgeTextMatchesQuery(mulaDisplayText, pattern);
      } else if(scope === 'notes') {
        const noteArr = (typeof notes !== 'undefined' && notes[i]) ? notes[i] : [];
        hasMatch = noteArr.some(n => dgeTextMatchesQuery(n.text || '', pattern));
      } else if(convertedCommentaries[scope]) {
        hasMatch = dgeTextMatchesQuery(dgeGoldSearchableText(convertedCommentaries[scope]), pattern);
        if(hasMatch) forceCommentaries.push(scope);
      }
      if(!hasMatch) continue;
    }

    // Redesigned card state model (reader redesign, sections 3-6/16-18):
    // ONE state object per shloka drives the card's visual treatment —
    // no more a permanent row of 5-6 tiny icon buttons sitting above the
    // text like an admin panel. Primary state (selected / completed /
    // in-progress) reads as a border color on the card itself; secondary
    // state (favorite / doubt) reads as a small badge next to the shloka
    // number, never a border, so "completed + favorite + doubt" together
    // stays legible instead of turning into competing borders (section 4).
    // The old always-visible action row moves into ONE contextual "⋯"
    // affordance (dgeOpenContextualMenu('shloka', ...), contextual-actions.js)
    // — same favorite/status/doubt/copy/play/Ask-Acharya actions, reached
    // through progressive disclosure instead of five permanent icons.
    const flags = (typeof dgeGetEffectiveFeatureFlags === 'function') ? dgeGetEffectiveFeatureFlags() : {};
    const m = (typeof marks !== 'undefined') ? marks[i] : null;
    const isFav = !!(m && m.fav);
    const status = m ? m.status : null;
    const isDoubt = !!(m && m.doubt);
    const noteCount = (typeof notes !== 'undefined' && notes[i]) ? notes[i].length : 0;
    const snipCount = (typeof snippets !== 'undefined' && snippets[i]) ? snippets[i].length : 0;
    const canStudy = document.body.classList.contains('is-authorized');

    const stateClasses = [
      activeId === i ? 'active' : '',
      (canStudy && isFav) ? 'is-fav' : '',
      (canStudy && isDoubt) ? 'is-doubt' : '',
      (canStudy && status === 'done') ? 'state-done' : '',
      (canStudy && status === 'practice') ? 'state-progress' : ''
    ].filter(Boolean).join(' ');

    const c = document.createElement('div');
    c.className = `shloka-card ${stateClasses}`.trim();
    c.id = `shloka-${i}`;

    // 7 Sep 2026 (the lead's option 1): the verse card carries only the
    // verse. ★ is the card's gold left edge (.is-fav), ? a dotted red edge
    // (.is-doubt), notes/snippets a tiny count under the number, and copy
    // lives in the ⋯ menu (shown to every reader; study actions inside it
    // are gated by contextual-actions.js itself).
    let countsHtml = '';
    if (canStudy && (noteCount > 0 || snipCount > 0)) {
      countsHtml = '<span class="shloka-counts">' +
        (noteCount > 0 ? `<span title="${noteCount} note(s)">${noteCount}✎</span>` : '') +
        (snipCount > 0 ? `<span title="${snipCount} saved snippet(s)">${snipCount}✂</span>` : '') + '</span>';
    }

    const moreBtnHtml = true
      ? `<button type="button" class="shloka-more-btn" title="Shloka ${i} actions" aria-label="Shloka ${i} actions" onclick="event.stopPropagation(); if (typeof window.dgeOpenContextualMenu === 'function') window.dgeOpenContextualMenu('shloka', {shlokaId:${i}}); else if (typeof openActionsSheet==='function') openActionsSheet(${i});">⋯</button>`
      : '';

    let commentaryHtml = '';
    if (shloka.commentaries) {
      // Collected first, joined after, so a tab bar can be prepended when
      // more than one commentary is actually rendering for this card --
      // stacked blocks stay the default (nothing to click, nothing
      // changes for a single-commentary view), tabs only appear when
      // there's something to switch between.
      const blocks = [];
      Object.entries(shloka.commentaries).forEach(([cKey, cText]) => {
        const isSelected = selectedCommentaries.has(cKey);
        const isForcedBySearch = forceCommentaries.includes(cKey);

        if (isSelected || isForcedBySearch) {
          const name = stotraData.metadata.availableCommentaries[cKey] || cKey;
          let convertedText = convertedCommentaries[cKey];
          let convertedName = typeof applyTransliteration === 'function' ? applyTransliteration(name, activeScript) : name;

          // Gold-Standard commentary (dge/GOLD_STANDARD_ARCHITECTURE.md
          // Parts A/B/D) takes a completely separate render path -- the
          // certificate wrapper + badge are the ONLY visible signal a
          // reader has that this commentary carries verified word-mapping/
          // pratīka data; a legacy plain-string commentary gets neither.
          // dgeGoldRenderResult is null whenever gold-render.js isn't
          // loaded or the data has no commentary_markdown, in which case
          // this falls through to the exact same plain-text path every
          // other commentary already uses -- never a hard dependency.
          const isGoldStandard = convertedText && typeof convertedText === 'object' && convertedText.format === 'gold_v2_2';
          const goldResult = (isGoldStandard && typeof DGEGoldRender !== 'undefined') ? DGEGoldRender.render(convertedText) : null;

          if (goldResult) {
            // The badge IS the switch (see GOLD_STANDARD_ARCHITECTURE.md
            // D.1): tapping it toggles .dge-gold-simple on this block,
            // which main.css uses to fold the pill grid and provenance
            // boxes back down to plain paragraph flow -- "the view can be
            // switched," per the project lead's own direct ask, without a
            // second render pass.
            const goldBadge = '<span class="dge-gold-badge" title="Gold-Standard: word-by-word mapping, structured citations, verified pratīka links. Tap to switch view." ' +
              'onclick="event.stopPropagation(); window.dgeToggleGoldSimple(this)">🏅 Gold</span>';
            blocks.push({ cKey, name: convertedName,
              html: `<div class="commentary-block dge-gold-wrapper" data-ckey="${cKey}"><div class="commentary-title">${convertedName}${goldBadge}</div>${highlightText(goldResult.pillGridHtml, pattern)}${highlightText(goldResult.bodyHtml, pattern)}</div>` });
          } else {
            // Word-tap spans on the commentary too, not just the mūla: the
            // reader asked for कोश matches inside a commentary to be marked,
            // and for a word selected there to offer the same analysis a word
            // in the verse does. Both need the word to be its own element.
            // The Gold-Standard branch above is deliberately NOT wrapped --
            // it already carries a verified word-by-word mapping of its own,
            // and a second, cruder one layered over it would fight it.
            // Small "AI" badge -- see dgeIsAiGeneratedCommentaryKey in
            // core.js for the naming convention this checks. Distinct from
            // (and in addition to) the "(Gemini, unreviewed)" text already
            // baked into the label itself, since a badge is far more
            // scannable than prose buried in a title a reader may not read
            // closely.
            const aiBadge = (typeof dgeIsAiGeneratedCommentaryKey === 'function' && dgeIsAiGeneratedCommentaryKey(cKey))
              ? '<span class="dge-ai-badge" title="AI-generated -- not author-verified">AI</span>' : '';
            blocks.push({ cKey, name: convertedName,
              html: `<div class="commentary-block" data-ckey="${cKey}"><div class="commentary-title">${convertedName}${aiBadge}</div>${dgeWrapWordsForTap(highlightText(convertedText, pattern))}</div>` });
          }
        }
      });
      // Stitched sibling layers (layer-stitch.js) that exist but are not
      // yet selected render as tappable "load me" pills alongside the real
      // tabs — the reader can SEE what commentaries exist and open one with
      // a single tap, the way the source site's own pill row works. Without
      // this, a pratīka-spine grantha looked empty and the only way in was
      // the 💬 picker hidden in the collapsed mobile top bar (project
      // lead's first phone test, 25 Aug night). Capped so a grantha with
      // mis-split junk layers (bhedojjivana's 216) doesn't drown the card —
      // the overflow pill opens the full picker.
      let unloadedTabsHtml = '';
      if (typeof window.dgeStitchedAvailableKeys === 'function') {
        const renderedKeys = new Set(blocks.map(b => b.cKey));
        const pending = window.dgeStitchedAvailableKeys().filter(k =>
          !renderedKeys.has(k) && !selectedCommentaries.has(k));
        const MAX_PENDING_PILLS = 6;
        const shown = pending.slice(0, MAX_PENDING_PILLS);
        const overflow = pending.length - shown.length;
        unloadedTabsHtml = shown.map(k => {
          const name = stotraData.metadata.availableCommentaries[k] || k;
          const label = typeof applyTransliteration === 'function' ? applyTransliteration(name, activeScript) : name;
          return `<button type="button" class="dge-commentary-tab dge-tab-unloaded" title="Tap to load this commentary" onclick="dgeToggleCommentarySelection('${k}')">${label}</button>`;
        }).join('') + (overflow > 0
          ? `<button type="button" class="dge-commentary-tab dge-tab-unloaded" onclick="window.togglePopup('commentaryPopup')">+${overflow} 💬</button>`
          : '');
      }
      if (blocks.length > 1 || (blocks.length && unloadedTabsHtml)) {
        const tabsHtml = `<div class="dge-commentary-tabs" role="tablist">` +
          `<button type="button" class="dge-commentary-tab active" onclick="dgeShowCommentaryTab(${i}, 'all', this)">All</button>` +
          blocks.map(b => `<button type="button" class="dge-commentary-tab" onclick="dgeShowCommentaryTab(${i}, '${b.cKey}', this)">${b.name}</button>`).join('') +
          unloadedTabsHtml + `</div>`;
        commentaryHtml = `<div class="dge-commentary-tabbed" data-shloka="${i}">${tabsHtml}${blocks.map(b => b.html).join('')}</div>`;
      } else if (blocks.length) {
        commentaryHtml = blocks.map(b => b.html).join('');
      } else if (unloadedTabsHtml) {
        // No commentary selected at all on this card, but layers exist —
        // the pill row alone, so the way in is visible right on the card.
        commentaryHtml = `<div class="dge-commentary-tabbed" data-shloka="${i}"><div class="dge-commentary-tabs" role="tablist">${unloadedTabsHtml}</div></div>`;
      }
    }

    // Additional structured fields (Padaccheda, Anvaya, Vrutta, etc.) —
    // shown independent of which commentary is selected, since these are
    // grammatical/analytical rather than per-commentary. Only renders for
    // fields that are both enabled AND actually present in this shloka's
    // data — silently absent otherwise, so this is safe to ship even
    // before any shloka has this data populated.
    let extraFieldsHtml = '';
    const effectiveExtraFields = (typeof dgeGetEffectiveShlokaFields === 'function') ? dgeGetEffectiveShlokaFields() : (window.SHLOKA_EXTRA_FIELDS || []);
    effectiveExtraFields.forEach(f => {
      if (!f.enabled) return;
      const raw = dgeGetNestedField(shloka, f.dataKey);
      if (!raw || (Array.isArray(raw) && raw.length === 0)) return;
      const t = (s) => (typeof applyTransliteration === 'function' ? applyTransliteration(String(s == null ? '' : s), activeScript) : s);
      const h = (s) => highlightText(t(s), pattern);
      let bodyHtml;
      switch (f.renderType) {
        case 'table': {
          // pratipadartha: [{order, pada, vigraha, vibhakti_dhatu, artha}]
          // -- word-by-word gloss table. vigraha (etymology) and
          // vibhakti_dhatu (case/tense-mood-person) are each skipped as a
          // column only if EVERY row lacks one, so a verse with no
          // notable derivations doesn't carry a permanently-empty column.
          const rows = [...raw].sort((a, b) => (a.order || 0) - (b.order || 0));
          const hasVigraha = rows.some(r => r.vigraha);
          const hasGrammar = rows.some(r => r.vibhakti_dhatu);
          bodyHtml = `<div class="dge-table-scroll"><table class="dge-analysis-table"><thead><tr>` +
            `<th>${h('पदम्')}</th>` + (hasVigraha ? `<th>${h('विग्रहः')}</th>` : '') +
            (hasGrammar ? `<th>${h('व्याकरणम्')}</th>` : '') + `<th>Meaning</th></tr></thead><tbody>` +
            rows.map(r => `<tr><td class="dge-analysis-pada">${h(r.pada || '')}</td>` +
              (hasVigraha ? `<td>${h(r.vigraha || '')}</td>` : '') +
              (hasGrammar ? `<td>${h(r.vibhakti_dhatu || '')}</td>` : '') +
              `<td>${h(r.artha || '')}</td></tr>`).join('') + `</tbody></table></div>`;
          break;
        }
        case 'list': {
          // alankara: [{name, type, justification}]
          bodyHtml = `<ul class="dge-analysis-list">` + raw.map(item =>
            `<li><b>${h(item.name || '')}</b>` + (item.type ? ` <span class="dge-analysis-tag">${h(item.type)}</span>` : '') +
            (item.justification ? ` — ${h(item.justification)}` : '') + `</li>`
          ).join('') + `</ul>`;
          break;
        }
        case 'samasa': {
          // samasa_vishesha: [{compound, split, samasa_type, vigraha}] --
          // one entry per hyphenated compound already named in this
          // verse's padaccheda.
          bodyHtml = `<ul class="dge-analysis-list">` + raw.map(item =>
            `<li><b>${h(item.compound || '')}</b>` + (item.samasa_type ? ` <span class="dge-analysis-tag">${h(item.samasa_type)}</span>` : '') +
            (item.split ? `<div class="dge-analysis-split">${h(item.split)}</div>` : '') +
            (item.vigraha ? `<div class="dge-analysis-lakshana">${h(item.vigraha)}</div>` : '') + `</li>`
          ).join('') + `</ul>`;
          break;
        }
        case 'chandas': {
          // {name, gana_structure, lakshana} -- a single verse's metre.
          if (!raw.name) return;
          bodyHtml = `<div class="dge-analysis-chandas"><b>${h(raw.name)}</b>` +
            (raw.gana_structure ? ` <span class="dge-analysis-tag">${h(raw.gana_structure)}</span>` : '') +
            (raw.lakshana ? `<div class="dge-analysis-lakshana">${h(raw.lakshana)}</div>` : '') + `</div>`;
          break;
        }
        default: {
          const displayText = Array.isArray(raw) ? raw.join(', ') : raw;
          bodyHtml = h(displayText);
        }
      }
      // Gemini-sourced fields (everything under gemini_deep_analysis) get
      // the same "AI, unreviewed" badge as an AI-generated commentary --
      // see dgeIsAiGeneratedCommentaryKey's convention in core.js. This
      // whole block is always Gemini output, so the badge isn't
      // conditional the way a commentary key's is.
      const isAiField = typeof f.dataKey === 'string' && f.dataKey.indexOf('gemini_deep_analysis.') === 0;
      const aiBadge = isAiField ? '<span class="dge-ai-badge" title="AI-generated -- not author-verified">AI</span>' : '';
      // Open by default for the fields most readers want on sight
      // (word-by-word gloss, purport); collapsed for the more specialist
      // ones (figures of speech, metre, extra grammar notes) so the card
      // doesn't grow long before anyone's asked for them.
      const openAttr = (f.renderType === 'list' || f.renderType === 'samasa' || f.renderType === 'chandas' || f.id === 'vyakarana') ? '' : ' open';
      extraFieldsHtml += `<details class="commentary-block dge-analysis-field" data-field="${f.id}"${openAttr}>` +
        `<summary class="commentary-title">${f.icon} ${f.label}${aiBadge}</summary>${bodyHtml}</details>`;
    });

    // Vedic content stores padas (quarter-verses) separated by " / " —
    // scoped to just that content (detected via vedicId, which only the
    // Vedic-schema normalizer in core.js sets) so this can't affect PNS
    // or any other text that might use "/" for something else. Applied
    // AFTER highlightText() so a search match spanning a pada boundary
    // still highlights correctly first.
    // Gemini-enrichment footnotes (see dge/js/footnote-engine.js) are only
    // meaningful against the Devanagari the enrichment was computed from —
    // quoted_text/segments are stored verbatim in Devanagari, so on any
    // other display script this falls back to plain highlighted text rather
    // than risk mismatched markers.
    let footnoteResult = null;
    if (shloka.geminiEnrichment && (!window.activeScript || window.activeScript === 'devanagari') &&
        typeof window.DGEFootnotes !== 'undefined') {
      footnoteResult = window.DGEFootnotes.render(shloka.geminiEnrichment);
    }

    let mulaHtml = highlightText(footnoteResult ? footnoteResult.html : mulaDisplayText, pattern);
    if (shloka.vedicId) {
      mulaHtml = mulaHtml.replace(/\s*\/\s*/g, '<br>');
    }
    if (!footnoteResult) mulaHtml = mulaHtml.replace(/\n/g, '<br>');   // pāda breaks (dgePadaBreak) and stored newlines
    mulaHtml = mulaHtml.replace(/(॥\s*[०-९0-9]+\s*॥\s*)$/, '<span class="verse-no">$1</span>');   // the closing ॥ N ॥ never splits across lines
    mulaHtml = dgeWrapWordsForTap(mulaHtml);
    const footnoteListHtml = footnoteResult
      ? `<div class="dge-fn-block">${footnoteResult.footnotesHtml}</div>` : '';

    // App View only (see dgeSetLayoutMode) -- hidden by default in the
    // existing Scholar view via main.css. Nothing to show/hide if this
    // card has neither commentary nor analysis fields.
    const appViewToggleHtml = (commentaryHtml || extraFieldsHtml)
      ? `<button type="button" class="dge-appview-toggle" onclick="event.stopPropagation(); window.dgeToggleCardExpanded(this)">▾ Show commentary</button>` : '';

    // Source view (1 Sep 2026, DvaitaVedanta re-harvest): units imported
    // with sanitized source-site markup (core.js's sourceHtml — class=
    // "shloka" pratika banners, h3 layer headings, lang="HI" spans) get a
    // 🕮 toggle showing the unit exactly as dvaitavedanta.in lays it out,
    // styled by those same class hooks mapped onto DGE tokens (main.css's
    // .dge-srcview rules). The markup was sanitized at import (tags/class/
    // lang/id only) and ships in this repo's own data.json — the same
    // trust level as every other data-driven block on this card.
    const srcBtnHtml = shloka.sourceHtml
      ? `<button class="btn-icon" title="Source view — this unit as the source site presents it" onclick="event.stopPropagation(); window.dgeToggleSourceView(this)">🕮</button>` : '';
    const srcViewHtml = shloka.sourceHtml
      ? `<div class="dge-srcview" hidden>${shloka.sourceHtml}</div>` : '';

    // बन्नञ्जे-पाठः. Sumadhva Vijaya is read in two recensions: the one most
    // of the tradition accepts (the primary text here, from dvaitavedanta.in)
    // and Bannanje Govindacharya's critical edition, which admits fewer
    // verses. Where his reading exists it is offered on the verse itself
    // rather than buried in a picker -- the lead's ask, 9 Sep 2026: "there
    // should be some marking which could display that version of this sloka
    // as well." An alternate MULA is not a commentary and is deliberately not
    // rendered as one: mistaking a variant reading for a gloss is the kind of
    // error a reader would carry away without noticing.
    // bannanjeVaries marks the ~26 verses where the two genuinely disagree
    // (word order, or a different verse); the rest differ only in spelling.
    const pathaChipHtml = shloka.bannanje
      ? `<div class="dge-tp-place-row"><button type="button" class="dge-patha-chip${shloka.bannanjeVaries ? ' dge-patha-varies' : ''}" onclick="event.stopPropagation(); window.dgeTogglePathaView(this)" title="${shloka.bannanjeVaries ? 'Bannanje Govindacharya reads this verse differently' : 'Show this verse as Bannanje Govindacharya’s edition reads it'}">बन्नञ्जे-पाठः${shloka.bannanjeVaries ? ' <span class="dge-patha-dot">•</span>' : ''} <span class="dge-tp-arrow">▾</span></button></div>`
      : '';
    const pathaViewHtml = shloka.bannanje
      ? `<div class="dge-pathaview" hidden><div class="dge-patha-label">बन्नञ्जे-पाठः${shloka.bannanjeVerse && String(shloka.bannanjeVerse) !== String(i) ? ` · ${shloka.bannanjeVerse}` : ''}</div><div class="dge-patha-text">${dgeWrapWordsForTap(highlightText(dgePadaBreak(shloka.bannanje), pattern).replace(/\n/g, '<br>'))}</div></div>`
      : '';

    // Tīrthaprabandha verses carry a link to the project's Tīrtha holy-places
    // page, filtered to the kṣetra this verse describes (tirtha_link in the
    // data). Rendered as a small 📍 chip; empty/absent for every other text.
    const tirthaPlace = (shloka.breadcrumb && shloka.breadcrumb[2]) ? shloka.breadcrumb[2] : 'Tīrtha';
    const tirthaChipHtml = shloka.tirthaLink
      ? `<div class="dge-tp-place-row"><a class="dge-tp-place" href="${shloka.tirthaLink}" onclick="event.stopPropagation();" title="See ${tirthaPlace} on the Tīrtha holy-places map">📍 ${tirthaPlace} <span class="dge-tp-arrow">↗</span></a></div>` : '';

    // 9 Sep 2026: a verse that condenses a specific Śrīmad Bhāgavatam verse
    // (core.js's dgeBuildBhagavataRefLink) links straight to it — same
    // chip-row idiom as the Tīrtha link just above, one level down since
    // it's a same-app jump rather than an outbound page.
    const bhagavataChipHtml = shloka.bhagavataLink
      ? `<div class="dge-tp-place-row"><a class="dge-tp-place" href="${shloka.bhagavataLink.url}" onclick="event.stopPropagation();" title="Open the source verse in Śrīmad Bhāgavatam">🔗 ${shloka.bhagavataLink.label} <span class="dge-tp-arrow">↗</span></a></div>` : '';

    // 7 Sep 2026: dhātu-form chips (window.dgeDhatuHits, loaded per grantha in
    // core.js). Key = the data-side unit id: a legacy shloka number, an item id,
    // or <chapter id>#<number> for nested verses. Hidden in App layout by CSS.
    const dhatuChipsHtml = dgeDhatuChipsHtml(i, shloka);
    c.innerHTML = `
      <div class="shloka-main-row">
        <div class="shloka-num">${i}${countsHtml}</div>
        <div class="shloka-text" onclick="if(!window.dgeContentEditMode && typeof loadShloka==='function') loadShloka(${i})">${mulaHtml}</div>
        ${window.dgeContentEditMode ? `<button class="btn-icon" title="Edit this shloka's text" onclick="event.stopPropagation(); window.dgeInlineEditShloka(${i})">✏️</button>` : ''}
        ${srcBtnHtml}
        ${moreBtnHtml}
      </div>
      ${pathaChipHtml}
      ${pathaViewHtml}
      ${dgePadacchedaChipHtml(i, shloka)}
      ${dgePadacchedaViewHtml(i, shloka)}
      ${tirthaChipHtml}
      ${bhagavataChipHtml}
      ${dhatuChipsHtml}
      ${footnoteListHtml}
      ${appViewToggleHtml}
      ${extraFieldsHtml}
      ${commentaryHtml}
      ${srcViewHtml}`;
    listEl.appendChild(c);
  }

  // Cross-reference detection over the freshly rendered cards. entity-linker.js's
  // scan (a work name + optional verse number, e.g. "ब्रह्मसूत्रे १.१.२") must
  // run BEFORE intellisense.js's own sūtra-citation scan (a bare number cued by
  // a nearby grammar term) so a citation naming both a work and a number becomes
  // ONE span -- see entity-linker.js's header comment for why the ordering
  // matters. Neither call previously ran in the reading view at all
  // (dgeScanForSutras was wired only into Kosha/Ashtadhyayi/Dhatu/Rupasiddhi),
  // so a citation appearing in a shloka or commentary went unlinked here.
  if (typeof window.dgeScanForEntities === 'function') {
    try { window.dgeScanForEntities(listEl); } catch (e) {}
  }
  if (typeof window.dgeScanForSutras === 'function') {
    try { window.dgeScanForSutras(listEl); } catch (e) {}
  }

  window.searchMatches = Array.from(document.querySelectorAll('.search-match'));
  const navContainer = document.getElementById('searchNavigator');
  if (rawQuery && window.searchMatches.length > 0 && navContainer) {
    navContainer.style.display = 'flex';
    navSearch(1);
  } else if (navContainer) {
    navContainer.style.display = 'none';
  }

  dgeUpdateSingleViewNav(fIds);
  dgeUpdateListViewNav(fIds, needsPaging);

  dgeRenderCommentaryBar();

  // धातु/कोश word marking (highlight-words.js). Deliberately AFTER the DOM is
  // in place and deliberately not awaited: the answer needs a fetch, and a
  // verse must never wait on a colour. Absent module = no marks, no error.
  // Generic lexical marking is revoked (config.js showWordMarks). The call
  // stays because the module honours the flag and clears anything already
  // marked, which is what makes turning it back on work as well as off.
  if (typeof window.dgeApplyWordMarks === 'function') window.dgeApplyWordMarks(listEl);

  // प्रतीकाः (pratika.js): the verse's own words where a commentary quotes
  // them back, and the link between the two. Pure DOM and string work over
  // spans that are already in place, so unlike the word marks it needs no
  // fetch and no lazy observation.
  if (typeof window.dgePratikaMarkAll === 'function') window.dgePratikaMarkAll(listEl);

  // सन्दर्भाः (reference-links.js): the धातु/कोश/सूत्र a commentary is
  // actually CITING, from _references/<slug>.json. Runs after the pratīka
  // pass because both write onto the same .dge-word spans and a pratīka is
  // the quieter claim -- a citation mark should be able to sit on top of one.
  if (typeof window.dgeReferenceMarkAll === 'function') window.dgeReferenceMarkAll(listEl);

  // सन्धिच्छेदः in the commentary prose (commentary-sandhi.js). Last of the
  // three, and it steps aside wherever one of the others already marked a
  // word: a citation and a pratīka are louder claims than a seam.
  if (typeof window.dgeCommentarySandhiMarkAll === 'function') window.dgeCommentarySandhiMarkAll(listEl);
}

// The page bar sits above the list and again below it (#listViewNavBottom),
// so a reader who has read to the bottom of a page has Next in reach.
// Above the list it also carries the page-size picker; the bar is hidden
// only when everything fits on one page at the SMALLEST size, so the picker
// stays reachable (choosing 10 on a 20-verse text is a real choice).
function dgeUpdateListViewNav(fIds, needsPaging) {
  const nav = document.getElementById('listViewNav');
  const navB = document.getElementById('listViewNavBottom');
  if (!nav) return;
  const size = dgeListPageSize();
  const total = fIds.length;
  const showBar = window.viewMode !== 'single' && total > DGE_LIST_PAGE_SIZES[0];
  if (!showBar) { nav.style.display = 'none'; if (navB) navB.style.display = 'none'; return; }
  const maxPage = Math.max(0, Math.ceil(total / size) - 1);
  const page = Math.min(window.dgeListPage || 0, maxPage);
  const startN = page * size + 1;
  const endN = Math.min((page + 1) * size, total);
  const prev = `<button class="btn-sm" onclick="window.dgeListViewStep(-1)" ${page <= 0 ? 'disabled' : ''} aria-label="Previous page">⟨ Prev</button>`;
  const next = `<button class="btn-sm" onclick="window.dgeListViewStep(1)" ${page >= maxPage ? 'disabled' : ''} aria-label="Next page">Next ⟩</button>`;
  const where = `<span style="font-weight:700; font-size:13px;">${startN}–${endN} of ${total.toLocaleString()}</span>
    <span style="font-size:11px; color:var(--muted-text);">page ${page + 1}/${maxPage + 1}</span>`;
  const sizes = `<span class="range-mode-toggle" role="group" aria-label="Verses per page" title="Verses per page" style="margin-left:auto;">
    ${DGE_LIST_PAGE_SIZES.map(n => `<button type="button" class="range-mode-btn${n === size ? ' active' : ''}" onclick="window.dgeSetListPageSize(${n})">${n}</button>`).join('')}
  </span>`;
  nav.style.display = 'flex';
  nav.style.flexWrap = 'wrap';
  nav.innerHTML = `${prev}<span style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">${where}</span>${next}${sizes}`;
  if (navB) {
    navB.style.display = maxPage > 0 ? 'flex' : 'none';
    navB.innerHTML = `${prev}<span style="display:flex; align-items:center; gap:8px;">${where}</span>${next}`;
  }
}

window.dgeListViewStep = function(dir) {
  window.dgeListPage = (window.dgeListPage || 0) + dir;
  renderList();
  // The address bar follows the page (its first verse), so a reload or a bookmark comes back to the same page.
  if (typeof getFilteredIds === 'function' && typeof window.dgeSyncUrl === 'function') {
    const first = getFilteredIds()[(window.dgeListPage || 0) * dgeListPageSize()];
    if (first) window.dgeSyncUrl(first);
  }
  const nav = document.getElementById('listViewNav');
  if (nav) nav.scrollIntoView({ behavior: 'smooth', block: 'start' });
};

// ---------------------------------------------------------------
// Single-shloka "one at a time" view mode — a separate reading position
// (currentReadingId) from the audio-playback position (activeId), so
// paging through verses to READ never jumps the currently playing audio
// around while it's actually playing. Tapping a shloka's text or paging
// with Prev/Next both call loadShloka() (select + sync the player's own
// track counter, never start playback) — audio only ever starts via an
// explicit Play tap; this only controls which card(s) renderList
// actually builds.
// ---------------------------------------------------------------
function dgeUpdateSingleViewNav(fIds) {
  const nav = document.getElementById('singleViewNav');
  if (!nav) return;
  if (window.viewMode !== 'single' || !stotraData) { nav.style.display = 'none'; return; }

  const ids = fIds || (typeof getFilteredIds === 'function' ? getFilteredIds() : Object.keys(stotraData.shlokas).map(Number));
  const idx = ids.indexOf(window.currentReadingId);
  nav.style.display = 'flex';
  nav.innerHTML = `
    <button class="btn-sm" onclick="window.dgeSingleViewStep(-1)" ${idx <= 0 ? 'disabled' : ''}>⟨ Prev</button>
    <span style="font-weight:700; font-size:13px;">${idx + 1} / ${ids.length}</span>
    <button class="btn-sm" onclick="window.dgeSingleViewStep(1)" ${(idx === -1 || idx >= ids.length - 1) ? 'disabled' : ''}>Next ⟩</button>
  `;
}

window.dgeSetViewMode = function(mode) {
  window.viewMode = (mode === 'single') ? 'single' : 'list';
  localStorage.setItem('app_viewMode', window.viewMode);
  document.querySelectorAll('#displayPopup .pop-item[data-viewmode]').forEach(el => {
    el.classList.toggle('active', el.dataset.viewmode === window.viewMode);
  });
  if (window.viewMode === 'single' && !window.currentReadingId) {
    const fIds = typeof getFilteredIds === 'function' ? getFilteredIds() : (stotraData ? Object.keys(stotraData.shlokas).map(Number) : []);
    window.currentReadingId = (typeof activeId !== 'undefined' && activeId) || fIds[0] || 1;
  }
  if (typeof renderList === 'function') renderList();
};

// Phase 5 of the mobile UI overhaul: a second, lower-density layout
// alongside the existing dense "Scholar" view (see the App Layouts entry
// in the Display sheet). Pure CSS/class-driven -- body.dge-app-view (see
// main.css) collapses each card's commentary/analysis behind the
// per-card .dge-appview-toggle button rendered below, with no re-render
// needed on switch since the collapse/reveal is driven entirely by CSS
// selectors on classes already present in the DOM either way.
//
// `announce` (24 Aug 2026, project lead's direct report: "the layout...
// not getting applied... old layout is still rendered"): the switch was
// ALWAYS applying and persisting correctly (confirmed live -- the class
// toggles, survives a reload), but with no commentary selected (the new
// default since the multi-select-commentary rework, a Set() rather than
// 'all') there is nothing for App view to collapse, and the remaining
// card-density difference was too small to notice -- so a tap genuinely
// looked like it did nothing. Two real fixes: main.css's own App-view
// density delta widened to actually be noticeable card-to-card (see the
// comment there), and this function now shows an explicit confirmation
// toast for a real user tap so switching is never silent -- but not on
// initApp()'s own startup restore, which calls this with announce left
// false/undefined so a normal page load doesn't toast on its own.
window.dgeSetLayoutMode = function (mode, announce) {
  const isApp = mode === 'app';
  document.body.classList.toggle('dge-app-view', isApp);
  localStorage.setItem('app_layoutMode', isApp ? 'app' : 'scholar');
  document.querySelectorAll('#displayPopup .pop-item[data-layout]').forEach(el => {
    el.classList.toggle('active', el.dataset.layout === (isApp ? 'app' : 'scholar'));
  });
  if (announce && typeof showToast === 'function') {
    showToast(isApp ? '📱 App layout applied.' : '📚 Scholar layout applied.');
  }
};

// Toggles one card's expanded state -- a dedicated button rather than a
// whole-card tap gesture, since .shloka-text's own tap already calls
// loadShloka() to select/play that verse; an ambiguous full-card tap
// would collide with that existing behaviour.
// The 🕮 source-view toggle (see the srcBtnHtml comment in renderList).
// पदच्छेदः — the verse with its sandhi joins opened out.
//
// Two sources, and the reader is told which is which, because they are not
// the same kind of claim. A `padaccheda` on the verse itself is an editor's:
// it is shown plainly. Anything from _padaccheda/<slug>.json is this
// repository's own segmenter (tools/padaccheda.py) and is labelled as
// analysis — measured at 55% exact against the 3,941 editor padacchedas the
// Aṣṭādhyāyī ships, on ordinary verse noticeably better, and in neither case
// something to print as though an editor had signed it.
//
// Only the tokens that actually split are listed. A verse whose every word
// stands alone has nothing to show and gets no chip, rather than a panel
// repeating the verse back.
function dgePadacchedaRows(id, shloka) {
  const editor = shloka.padaccheda;
  if (Array.isArray(editor) && editor.length) {
    return { source: 'editor', rows: [editor.map(String)] };
  }
  if (typeof editor === 'string' && editor.trim()) {
    return { source: 'editor', rows: [editor.split(/\s*[+·]\s*|\s{2,}/).filter(Boolean)] };
  }
  const data = window.dgePadaccheda;
  if (!data || !data.units) return null;
  const keys = [String(id)];
  if (shloka.unitId) { keys.push(shloka.unitId); if (shloka.unitNo) keys.push(shloka.unitId + '#' + shloka.unitNo); }
  for (const k of keys) {
    if (data.units[k] && data.units[k].length) return { source: data.source || 'engine', rows: data.units[k] };
  }
  return null;
}

function dgePadacchedaChipHtml(id, shloka) {
  if (typeof dgeGetEffectiveFeatureFlags === 'function' &&
      dgeGetEffectiveFeatureFlags().showPadaccheda === false) return '';
  const got = dgePadacchedaRows(id, shloka);
  if (!got) return '';
  const engine = got.source !== 'editor';
  const title = engine
    ? 'पदच्छेदः — where this verse joins two words into one written form. Worked out by this library’s own segmenter, not by an editor.'
    : 'पदच्छेदः as this edition gives it';
  return `<div class="dge-tp-place-row"><button type="button" class="dge-patha-chip dge-pc-chip" onclick="event.stopPropagation(); window.dgeTogglePadacchedaView(this)" title="${title}">पदच्छेदः${engine ? ' <span class="dge-pc-auto">≈</span>' : ''} <span class="dge-tp-arrow">▾</span></button></div>`;
}

function dgePadacchedaViewHtml(id, shloka) {
  if (typeof dgeGetEffectiveFeatureFlags === 'function' &&
      dgeGetEffectiveFeatureFlags().showPadaccheda === false) return '';
  const got = dgePadacchedaRows(id, shloka);
  if (!got) return '';
  const t = (x) => (typeof applyTransliteration === 'function' ? applyTransliteration(String(x), activeScript) : String(x));
  const engine = got.source !== 'editor';
  const body = got.rows.map(row => {
    // An engine row is [written token, seams, piece, piece …]; an editor row
    // is just the pieces, with nothing to point back at.
    const joined = engine ? row.slice(2) : row;
    const seams = engine ? String(row[1] || '') : '';
    const head = engine
      ? `<span class="dge-pc-src deva">${dgeEsc(t(row[0]))}</span><span class="dge-pc-eq">=</span>`
      : '';
    // Two different operations, and the mark says which: '+' where sandhi
    // fused two words, '-' where a compound's members were written together.
    // नारायणाय + अखिल-कारणाय is both at once.
    let parts = '';
    joined.forEach((w, k) => {
      if (k) {
        const samasa = seams.charAt(k - 1) === '-';
        parts += samasa
          ? '<span class="dge-pc-hyphen" title="समासः · members of one compound">-</span>'
          : '<span class="dge-pc-plus" title="सन्धिः · two words joined">+</span>';
      }
      parts += `<span class="dge-pc-part">${dgeEsc(t(w))}</span>`;
    });
    return `<div class="dge-pc-row">${head}<span class="dge-pc-parts deva">${parts}</span></div>`;
  }).join('');
  const note = engine
    ? '<div class="dge-pc-note">worked out by this library’s segmenter from its own word lists — not an editor’s reading</div>'
    : '';
  return `<div class="dge-pcview" hidden><div class="dge-patha-label">पदच्छेदः</div>${body}${note}</div>`;
}

// Minimal escape for the few strings this file interpolates itself.
function dgeEsc(s) {
  return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

window.dgeTogglePadacchedaView = function (btnEl) {
  const card = btnEl.closest('.shloka-card');
  const v = card && card.querySelector('.dge-pcview');
  if (!v) return;
  v.hidden = !v.hidden;
  const arrow = btnEl.querySelector('.dge-tp-arrow');
  if (arrow) arrow.textContent = v.hidden ? '▾' : '▴';
};

window.dgeTogglePathaView = function (btnEl) {
  const card = btnEl.closest('.shloka-card');
  const v = card && card.querySelector('.dge-pathaview');
  if (!v) return;
  v.hidden = !v.hidden;
  const arrow = btnEl.querySelector('.dge-tp-arrow');
  if (arrow) arrow.textContent = v.hidden ? '▾' : '▴';
};

window.dgeToggleSourceView = function (btnEl) {
  const card = btnEl.closest('.shloka-card');
  const v = card && card.querySelector('.dge-srcview');
  if (!v) return;
  v.hidden = !v.hidden;
  btnEl.classList.toggle('active', !v.hidden);
};

window.dgeToggleCardExpanded = function (btnEl) {
  const card = btnEl.closest('.shloka-card');
  if (!card) return;
  const expanded = card.classList.toggle('dge-card-expanded');
  btnEl.textContent = expanded ? '▴ Hide commentary' : '▾ Show commentary';
};

// Scrolls a card to sit just below the sticky header stack (top bar +
// reading-card-wrap), using their ACTUAL current rendered height rather
// than a guessed CSS scroll-margin-top — that guess was tuned for one
// layout state and went stale (visible as a scroll-then-correct jump)
// once the header's real height changed with the nav bar move.
function dgeScrollCardIntoView(cardEl) {
  if (!cardEl) return;
  const topBar = document.querySelector('.top-bar');
  const readingWrap = document.getElementById('readingCardWrap');
  const topBarHeight = topBar ? topBar.getBoundingClientRect().height : 0;
  const wrapHeight = readingWrap ? readingWrap.getBoundingClientRect().height : 0;
  const targetY = window.scrollY + cardEl.getBoundingClientRect().top - topBarHeight - wrapHeight - 10;
  // Instant, not smooth — an animated scroll visibly moves through the
  // space between old and new position before settling, which for a
  // quick Prev/Next tap can look exactly like "the page jumped and then
  // readjusted" even when it's working correctly. An instant jump has no
  // visible in-between motion to be misread that way.
  window.scrollTo({ top: Math.max(0, targetY), behavior: 'auto' });
}

window.dgeSingleViewStep = function(direction) {
  if (!stotraData) return;
  const fIds = typeof getFilteredIds === 'function' ? getFilteredIds() : Object.keys(stotraData.shlokas).map(Number);
  const idx = fIds.indexOf(window.currentReadingId);
  const newIdx = idx + direction;
  if (newIdx < 0 || newIdx >= fIds.length) return;
  window.currentReadingId = fIds[newIdx];
  // Keep the audio player's own track counter following the reader's
  // position too — but only when nothing is actually playing, so paging
  // to read never interrupts or retargets audio already underway.
  if (!(typeof isPlaying !== 'undefined' && isPlaying) && typeof loadShloka === 'function') loadShloka(window.currentReadingId);
  renderList();
  // Deferred a frame: reading layout (getBoundingClientRect) immediately
  // after renderList's DOM rebuild can catch the browser mid-reflow and
  // return a stale position, which is what a visible "jump then correct"
  // looks like — waiting for the next frame means layout has actually
  // finished settling before anything gets measured.
  requestAnimationFrame(() => {
    dgeScrollCardIntoView(document.getElementById(`shloka-${window.currentReadingId}`));
  });
};

// Used by TOC quick-jump: in single-view mode, jumping shows/reads that
// verse without forcing audio playback (list mode's jump-and-play
// behaviour via playShloka is untouched).
window.dgeSetSingleViewId = function(id) {
  window.currentReadingId = id;
  renderList();
  requestAnimationFrame(() => {
    dgeScrollCardIntoView(document.getElementById(`shloka-${window.currentReadingId}`));
  });
};

function navSearch(direction) {
  if (!window.searchMatches || window.searchMatches.length === 0) return;
  if(window.currentMatchIdx >= 0 && window.searchMatches[window.currentMatchIdx]) { 
    window.searchMatches[window.currentMatchIdx].classList.remove('active-match'); 
  }

  window.currentMatchIdx += direction;
  if (window.currentMatchIdx >= window.searchMatches.length) window.currentMatchIdx = 0;
  if (window.currentMatchIdx < 0) window.currentMatchIdx = window.searchMatches.length - 1;

  const target = window.searchMatches[window.currentMatchIdx];
  target.classList.add('active-match');
  target.scrollIntoView({ behavior: 'smooth', block: 'center' });
  
  const countEl = document.getElementById('searchMatchCount');
  if (countEl) countEl.innerText = `${window.currentMatchIdx + 1} / ${window.searchMatches.length}`;
}

