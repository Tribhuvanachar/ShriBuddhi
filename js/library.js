// js/library.js — Library browser modal, window.openLibraryModal().
// Renders every POPULATED grantha from data/library.json as a collapsible
// TREE mirroring the real taxonomy folder structure, rather than one flat
// list per top-level category. With four Vedas x shakha x samhita x
// mandala/kanda now live, a flat list interleaved unrelated texts
// (Rigveda mandala 1, Atharvaveda kanda 1, Rigveda mandala 2 ...) and
// gave no sense of where anything sat in the corpus.
// Deliberately excludes unpopulated entries — the catalog lists hundreds
// of planned granthas, and showing empty placeholders would look broken.
window.DGE_VERSIONS = window.DGE_VERSIONS || {};
window.DGE_VERSIONS['library.js'] = 'v3.21 (Sri Ramanuja Meghamala segment labels. v3.20: stale-draft gate: a super-admin draft previews only when NEWER than the committed overrides (draftAt vs updatedAt). v3.19: super-admin draft preview of the Library Manager\'s unexported overrides + searchable By-Author facet index. On top of v3.17\'s mula_gretil/mula_dcs labels)';

// Display names for path segments, stored in DEVANAGARI as the single
// source of truth — every label is then run through the app's existing
// applyTransliteration() into whichever script the user has selected
// (Sanskrit / English-IAST / Kannada / Telugu / Tamil / Malayalam).
// Previously these were hardcoded IAST while grantha titles rendered in
// Devanagari, so the same menu mixed two scripts and neither responded
// to the script selector.
// Anything not listed falls back to dgeAutoLabel(), which is ASCII and
// deliberately left untransliterated — a folder name we have no Sanskrit
// name for shouldn't be mangled through a Devanagari->script converter.
// The table itself lives in js/path-labels.js, which every page carrying
// this file loads first -- library.html needs the same names (see that
// file's header).
const DGE_PATH_LABELS = window.DGE_PATH_LABELS || {};

// Numbered folders, e.g. "mandala_07". The prefix is Devanagari (so it
// transliterates with everything else) and the numeral is converted to
// the matching script's digits by the same engine.
const DGE_NUMBERED_PREFIXES = {
  mandala: 'मण्डलम्', kanda: 'काण्डम्', adhyaya: 'अध्यायः',
  skandha: 'स्कन्धः', prapathaka: 'प्रपाठकः', anuvaka: 'अनुवाकः',
  ashtaka: 'अष्टकम्', parva: 'पर्व', sarga: 'सर्गः',
  amsha: 'अंशः', pada: 'पादः'
};

const DGE_DEVA_DIGITS = ['०','१','२','३','४','५','६','७','८','९'];
function dgeDevaNum(n) {
  return String(n).split('').map(d => DGE_DEVA_DIGITS[+d]).join('');
}

// A label/title that mixes Devanagari text with plain ASCII digits (e.g.
// a custom curator label like "स्कन्धः 1") passes dgeToActiveScript's
// Devanagari-detection gate as a whole, but the digit run itself is never
// touched by that gate -- it stays ASCII through a non-Devanagari script
// selection too, so the digits don't follow the rest of the label into
// Kannada/Tamil/etc. Converting the digits to Devanagari first lets the
// later transliteration pass carry them through like everything else.
function dgeLocalizeNumerals(text) {
  if (!text || !/[ऀ-ॿ]/.test(text)) return text;
  return text.replace(/\d+/g, m => dgeDevaNum(parseInt(m, 10)));
}

// ---------------------------------------------------------------------- //
// Library Manager curation overrides (admin/library.html exports
// admin/config/library-overrides.json). A NON-DESTRUCTIVE display layer only:
// hide/pin/reorder/rename/move all affect how populated granthas group
// and sort in this tree, never library.json/taxonomy.json or the actual
// fetch path -- dgeGoToGrantha always navigates on the real slug even
// after a display-only move. Absent/empty file = identical to before
// this existed.
// ---------------------------------------------------------------------- //
// `adds` (31 Aug 2026): folders the curator created in the Library Manager
// that exist only in the overrides layer. This tree is built from the
// granthas' display paths, so an added folder appears here automatically
// once anything is MOVED under it and is simply absent while empty --
// carried in the shape so the two tools stay field-for-field in sync.
let dgeLibOverrides = { hidden: [], pinned: [], labels: {}, order: {}, moves: {}, adds: [], shelf: null };
// True only while a super-admin's UNEXPORTED Library Manager draft (this
// browser's localStorage, see admin/library.html) is being overlaid in
// place of the committed file -- drives the "draft preview" notice in
// dgeRenderLibraryRoot(). Readers never take this branch: for them the
// committed admin/config/library-overrides.json is the only source.
let dgeLibOverridesDraftPreview = false;

function dgeNormalizeOverrides(ov) {
  return {
    hidden: Array.isArray(ov.hidden) ? ov.hidden : [],
    pinned: Array.isArray(ov.pinned) ? ov.pinned : [],
    labels: (ov.labels && typeof ov.labels === 'object') ? ov.labels : {},
    order: (ov.order && typeof ov.order === 'object') ? ov.order : {},
    moves: (ov.moves && typeof ov.moves === 'object') ? ov.moves : {},
    adds: Array.isArray(ov.adds) ? ov.adds : [],
    // Hide-from-CORPUS-SEARCH list (1 Sep 2026): read by global-search.js,
    // not by this tree — carried in the shape so the manager draft-drift
    // comparison below stays field-for-field accurate.
    searchHidden: Array.isArray(ov.searchHidden) ? ov.searchHidden : [],
    // The go-live shelf (10 Sep 2026): an ALLOW-list, the opposite direction
    // from `hidden` above and the shape a launch needs -- everything is
    // private except a named handful. See dgeMatchShelf in role-access.js
    // for why ancestors of an allowed path stay visible too.
    shelf: (ov.shelf && typeof ov.shelf === 'object') ? ov.shelf : null
  };
}
// Order-insensitive fingerprint, mirroring admin/library.html's ovKey() --
// used only to decide whether a manager draft actually DIFFERS from the
// committed file before flagging a preview.
function dgeOverridesKey(ov) {
  const o = dgeNormalizeOverrides(ov || {});
  return JSON.stringify({ h: o.hidden.slice().sort(), p: o.pinned, l: o.labels, o: o.order, m: o.moves, a: o.adds.slice().sort(), sh: o.searchHidden.slice().sort() });
}

async function dgeLoadLibraryOverrides() {
  dgeLibOverridesDraftPreview = false;
  try {
    const url = window.dgeAdminConfigUrl ? window.dgeAdminConfigUrl('library-overrides.json')
                                        : '../admin/config/library-overrides.json';
    // dgeFetchPublicJson (core.js) falls back to the repo-root config/ mirror
    // when admin/config/ 404s -- which it always does on a cleanly published
    // site (admin/ is excluded on purpose). Without this, the go-live shelf
    // never applied on a real publish: everything read as on-shelf, because
    // an absent shelf config is the "nothing is restricted" default. Guarded
    // because this file, unlike library.js's other consumers, can run before
    // core.js on some pages -- same defensive style legal-content.js already
    // uses for window.dgeContentUrl.
    const ov = typeof window.dgeFetchPublicJson === 'function'
      ? await window.dgeFetchPublicJson(url)
      : await fetch(url, { cache: 'no-store' }).then(r => r.ok ? r.json() : null).catch(() => null);
    if (ov) {
      dgeLibOverrides = dgeNormalizeOverrides(ov);
      // role-access.js owns the shelf CHECK (it needs the effective role and
      // the preview state); this file owns the shelf DATA, because the
      // curator's own file is where it belongs. Handing it over here keeps
      // both halves where they make sense.
      if (typeof window.dgeSetShelfConfig === 'function') window.dgeSetShelfConfig(dgeLibOverrides.shelf);
      dgeOverlayManagerDraft(ov.updatedAt);
      return;
    }
  } catch (e) { /* no overrides file yet */ }
  // Legacy fallback: the older hide-only file, still honored when the
  // newer overrides file doesn't exist yet.
  try {
    const vis = await fetch('data/library-visibility.json', { cache: 'no-store' }).then(r => r.ok ? r.json() : null);
    if (vis && Array.isArray(vis.hidden)) dgeLibOverrides.hidden = vis.hidden;
  } catch (e) { /* nothing hidden */ }
  dgeOverlayManagerDraft();
}

// 1 Sep 2026, project-lead report: edits made in the Library Manager
// "appear finalized" there after a refresh (the manager re-reads its own
// localStorage draft) but never showed in this Library panel -- because
// this panel reads ONLY the committed library-overrides.json, and a draft
// isn't committed until it's exported and pushed. Deliberate for readers;
// blind for the curator. So: a super-admin whose browser holds a draft
// that differs from the committed file now sees the DRAFT here too,
// clearly labeled as a preview (see dgeRenderLibraryRoot's notice), so
// they can check their curation in the real reader UI before publishing.
function dgeOverlayManagerDraft(committedUpdatedAt) {
  if (!dgeIsSuperAdmin()) return;
  try {
    const draft = JSON.parse(localStorage.getItem('dge.liboverrides') || 'null');
    if (!draft || typeof draft !== 'object') return;
    if (dgeOverridesKey(draft) === dgeOverridesKey(dgeLibOverrides)) return;
    // 2 Sep 2026, project-lead report: "the latest library is not
    // displaying the changes ... via the overrides I gave you." Their
    // device held a draft from BEFORE those overrides were committed,
    // and this preview replaced the committed curation with it — the
    // stale draft masked every newer committed change. A draft only
    // previews when it is NEWER than the committed file: the manager
    // stamps drafts with draftAt, exports carry updatedAt. A legacy
    // draft with no stamp never outranks a stamped committed file.
    const draftAt = Number(draft.draftAt) || 0;
    const committedAt = Number(committedUpdatedAt) || 0;
    if (committedAt > draftAt) return;
    dgeLibOverrides = dgeNormalizeOverrides(draft);
    dgeLibOverridesDraftPreview = true;
  } catch (e) { /* unreadable draft -- the committed file stands */ }
}

// 23 Aug 2026: per-grantha "hidden" flag written directly onto a
// library.json entry (distinct from dgeLibOverrides.hidden above, which is
// an admin-curated path-prefix list read from library-overrides.json) --
// admin-only content -- the shelves reached only by an opaque id -- gated
// the same way admin-gate.js gates a standalone page. Not real access
// control -- see that file's own caveat -- but keeps it out of the reader
// nav and quick-jump for anyone who isn't signed in as admin.
function dgeIsAdmin() {
  try {
    return localStorage.getItem('acharyaAuthorized') === 'true' ||
           localStorage.getItem('is_superadmin') === 'true';
  } catch (e) { return false; }
}
// admin/library.html's own gate is super-admin only (not the broader
// acharyaAuthorized tier dgeIsAdmin() above accepts) -- matched here so the
// tracker link this file adds is never shown to someone who'd just be
// bounced by that page's own passkey prompt.
function dgeIsSuperAdmin() {
  try { return localStorage.getItem('is_superadmin') === 'true'; }
  catch (e) { return false; }
}
function dgeIsAdminOnlyGrantha(g) {
  return !!(g && g.hidden) && !dgeIsAdmin();
}

function dgeIsHiddenPath(path) {
  const parts = path.split('/');
  for (let i = 1; i <= parts.length; i++) {
    if (dgeLibOverrides.hidden.indexOf(parts.slice(0, i).join('/')) >= 0) return true;
  }
  // Role-based content gates (see js/role-access.js) -- a separate,
  // Firestore-backed layer from the curator's own hidden list above, kept
  // as a second independent check rather than merged into dgeLibOverrides
  // so an admin gating a path by role doesn't have to touch the same
  // committed file the Library Manager owns. Optional: if role-access.js
  // never loaded (or a deployment has no gates configured) this is a
  // no-op, same as before this existed.
  if (typeof window.dgeIsHiddenByRoleGate === 'function' && window.dgeIsHiddenByRoleGate(path)) return true;
  // The go-live shelf -- an allow-list, so this is the check that hides the
  // ~590 leaves nobody named rather than the handful somebody did.
  if (typeof window.dgeIsOffShelf === 'function' && window.dgeIsOffShelf(path)) return true;
  return false;
}

// A 'move' override is keyed by the REAL taxonomy slug and rewrites where
// a grantha (or, as a side effect, every grantha under that same prefix)
// GROUPS in the tree -- the longest matching source prefix wins so moving
// a deep subfolder isn't shadowed by a move of one of its ancestors.
function dgeEffectiveDisplayPath(realSlug) {
  const moves = dgeLibOverrides.moves;
  let best = null;
  Object.keys(moves).forEach(src => {
    if (realSlug === src || realSlug.indexOf(src + '/') === 0) {
      if (!best || src.length > best.length) best = src;
    }
  });
  if (!best) return realSlug;
  const dest = moves[best];
  const rel = realSlug.slice(best.length).replace(/^\//, '');
  return dest ? (rel ? dest + '/' + rel : dest) : rel;
}

// core.js needs this to judge a DIRECT ?path= link against the go-live
// shelf, which is written in display paths.
window.dgeEffectiveDisplayPath = dgeEffectiveDisplayPath;

function dgePinRank(path) {
  const i = dgeLibOverrides.pinned.indexOf(path);
  return i < 0 ? Infinity : i;
}
function dgeOrderRank(parentPath, name) {
  const explicit = dgeLibOverrides.order[parentPath];
  if (!explicit) return Infinity;
  const i = explicit.indexOf(name);
  return i < 0 ? Infinity : i;
}
// Pin/order apply WITHIN each of the two existing sibling groups (folders,
// then leaves) rather than fully interleaving them — a deliberately
// smaller scope than the admin tool's own single merged sibling list, to
// avoid restructuring how folders vs. leaves render. A curator can still
// pin/reorder subfolders among themselves, or a grantha among its
// leaf-siblings, just not mix the two groups' order together.
function dgeSortChildKeys(parentPath, keys) {
  return keys.slice().sort((a, b) => {
    const pa = dgePinRank(parentPath ? parentPath + '/' + a : a);
    const pb = dgePinRank(parentPath ? parentPath + '/' + b : b);
    if (pa !== pb) return pa - pb;
    const oa = dgeOrderRank(parentPath, a), ob = dgeOrderRank(parentPath, b);
    if (oa !== ob) return oa - ob;
    return dgeCompareSlugs(a, b);
  });
}
function dgeSortLeaves(parentPath, leaves) {
  return leaves.slice().sort((a, b) => {
    const pa = dgePinRank(a.slug), pb = dgePinRank(b.slug);
    if (pa !== pb) return pa - pb;
    const na = a.slug.split('/').pop(), nb = b.slug.split('/').pop();
    const oa = dgeOrderRank(parentPath, na), ob = dgeOrderRank(parentPath, nb);
    if (oa !== ob) return oa - ob;
    return dgeCompareSlugs(a.slug, b.slug);
  });
}

// Converts a Devanagari label into the user's currently selected script,
// reusing the same engine the reading view uses so the whole app stays
// consistent. Non-Devanagari input (an auto-generated ASCII folder name)
// is returned untouched.
function dgeToActiveScript(devaText) {
  const script = window.activeScript || localStorage.getItem('app_script') || 'devanagari';
  if (script === 'devanagari') return devaText;
  if (!/[\u0900-\u097F]/.test(devaText)) return devaText;
  if (typeof window.applyTransliteration === 'function') {
    try { return window.applyTransliteration(devaText, script); } catch (e) { return devaText; }
  }
  return devaText;
}

function dgeAutoLabel(seg) {
  const m = seg.match(/^([a-z]+)_(\d+)$/i);
  if (m && DGE_NUMBERED_PREFIXES[m[1].toLowerCase()]) {
    return DGE_NUMBERED_PREFIXES[m[1].toLowerCase()] + ' ' + dgeDevaNum(parseInt(m[2], 10));
  }
  // No Sanskrit name known — plain ASCII, left as-is by dgeToActiveScript.
  return seg.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
}

// fullPath (optional, 1 Sep 2026): the segment's full DISPLAY path, so a
// curator's folder rename (Library Manager labels are keyed by effective
// display path) actually shows here. Before this, `labels` were honored
// only on grantha leaves -- a manager folder rename silently never
// reached the reader, part of the "changes not reflected in the actual
// library" report. Callers that don't know the path get the old behavior.
function dgeSegLabel(seg, fullPath) {
  const custom = fullPath !== undefined ? dgeLibOverrides.labels[fullPath] : undefined;
  if (custom !== undefined) return dgeToActiveScript(dgeLocalizeNumerals(custom));
  return dgeToActiveScript(DGE_PATH_LABELS[seg] || dgeAutoLabel(seg));
}

// Raw (untransliterated) Devanagari-or-honest-fallback label for a
// grantha's own last path segment -- used as the leaf title fallback in
// openLibraryModal() when library.json's baked g.title has no Devanagari
// to transliterate. Deliberately NOT run through dgeToActiveScript here:
// the caller applies that once, over the whole composed title string.
function dgeGranthaAutoTitle(realSlug) {
  const segs = realSlug.split('/');
  const last = segs[segs.length - 1];
  return DGE_PATH_LABELS[last] || dgeAutoLabel(last);
}

// Compares path segments so "mandala_2" precedes "mandala_10" (numeric
// where both segments share a prefix), while keeping unrelated folders
// properly separated instead of interleaving them purely by trailing
// number — which is what the previous sort did.
function dgeCompareSlugs(a, b) {
  const pa = a.split('/'), pb = b.split('/');
  for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
    const x = pa[i], y = pb[i];
    if (x === undefined) return -1;
    if (y === undefined) return 1;
    if (x === y) continue;
    const mx = x.match(/^(.*?)(\d+)$/), my = y.match(/^(.*?)(\d+)$/);
    if (mx && my && mx[1] === my[1]) return parseInt(mx[2], 10) - parseInt(my[2], 10);
    return x.localeCompare(y);
  }
  return 0;
}

function dgeBuildTree(entries) {
  const root = { children: {}, leaves: [] };
  entries.forEach(e => {
    const segs = e.slug.split('/');
    let node = root;
    for (let i = 0; i < segs.length - 1; i++) {
      const s = segs[i];
      node.children[s] = node.children[s] || { children: {}, leaves: [], key: s };
      node = node.children[s];
    }
    node.leaves.push(e);
  });
  return root;
}

let dgeTreeNodeSeq = 0;
// path -> total registered granthas under it (populated or not), rebuilt at
// the top of every openLibraryModal() call; see the comment there.
let dgeLibTotalCounts = {};

// 24 Aug 2026 -- icon-driven Library home screen, alongside the existing
// text tree (project lead's ask: something resembling an external
// ChatGPT mockup's "icon structure," not a pixel copy of it). A view
// mode, not a separate feature: the SAME tree data, sort order, badges
// and drill-down (dgeRenderNode) the list view already builds -- this
// only changes how the TOP LEVEL is presented, replacing "however many
// taps to reach any category" with one tap into a labelled icon tile,
// then handing off to the existing list rendering for everything below
// it. dgeLibTree/dgeLibTopKeys are cached here (module scope, not
// re-fetched) so switching List<->Grid or drilling in/out is instant --
// only openLibraryModal() itself does the async catalog fetch.
let dgeLibTree = null;
let dgeLibTopKeys = [];
let dgeLibGridCategory = null; // null = showing the grid itself; else the top-level key drilled into

// Admin-only "show pending too" toggle -- see openLibraryModal()'s
// showPending. Persisted per-device (localStorage), same pattern as the
// script/theme/view-mode preferences elsewhere in this file. Re-checked
// against dgeIsAdmin() everywhere it's read, not just here, so a demoted
// or logged-out admin's stale flag never leaks pending leaves to a
// regular visitor.
let dgeLibShowPending = (function () {
  try { return localStorage.getItem('dge_lib_show_pending') === '1'; } catch (e) { return false; }
})();
window.dgeToggleLibraryShowPending = function () {
  if (!dgeIsAdmin()) return;
  dgeLibShowPending = !dgeLibShowPending;
  try { localStorage.setItem('dge_lib_show_pending', dgeLibShowPending ? '1' : '0'); } catch (e) { /* ignore */ }
  window.openLibraryModal();
};

// One icon per real top-level taxonomy key (see DGE_PATH_LABELS above for
// the keys actually in use). Unmapped keys fall back to a plain folder
// icon rather than guessing -- better an honest generic icon than a
// wrong specific one.
const DGE_LIBRARY_ICONS = {
  vedas: '📿', veda: '📿',
  itihasa: '⚔️', itihasas: '⚔️',
  purana: '📜', puranas: '📜',
  darshana: '🕉️',
  smriti_dharma: '⚖️', smritis: '⚖️',
  kavya_alankara: '🪶', kavya: '🪶',
  kosha: '📖', koshas: '📖',
  stotra: '🎶', stotras: '🎶',
  agama: '🔥', pancharatra_agama: '🔥',
  vedanga: '📚', ancillary: '📚',
  DasaSahitya: '🎵', dasakuta: '🎵', vyasakuta: '🎵',
  upaveda: '🧘', upavedas: '🧘',
  nitishastra: '🏛️',
  dharmashastra: '⚖️',
  misc: '🗂️',
};
function dgeLibraryIconFor(key) {
  return DGE_LIBRARY_ICONS[key] || '🗂️';
}

function dgeGetLibraryViewMode() {
  try { return localStorage.getItem('dge_library_view_mode') || 'grid'; }
  catch (e) { return 'grid'; }
}
window.dgeSetLibraryViewMode = function (mode) {
  try { localStorage.setItem('dge_library_view_mode', mode); } catch (e) { /* ignore */ }
  dgeLibGridCategory = null;
  document.querySelectorAll('#libraryViewToggle .range-mode-btn').forEach(b => b.classList.toggle('active', b.dataset.libraryView === mode));
  dgeRenderLibraryRoot();
};
// A grantha counts as "New" for this many days after register_layers.py
// first stamped its addedAt -- existing entries (registered before that
// tool tracked dates) have no addedAt at all and never show this badge,
// deliberately: there is no reliable way to backfill a real date for them
// (this repo's git history is a shallow clone), and guessing would be
// worse than just not claiming to know.
const DGE_LIB_NEW_DAYS = 21;
function dgeIsRecentlyAdded(addedAt) {
  if (!addedAt) return false;
  const t = Date.parse(addedAt);
  if (isNaN(t)) return false;
  return (Date.now() - t) / 86400000 <= DGE_LIB_NEW_DAYS;
}

// Collapses single-child chains ("Ṛgveda › Śākala Śākhā › Saṃhitā") into
// one row instead of three nested taps — the taxonomy is deep and mostly
// linear, so without this the tree needs four taps to reach any mantra.
//
// noCollapseAtRoot (24 Aug 2026, project lead's direct report, matched a
// live screenshot exactly): the List view's own TOP-LEVEL category rows
// were also going through this same collapsing, so a category with a
// single populated branch (e.g. आगमः -> पाञ्चरात्रम् -> Pancharatra
// Samhitas) rendered as one row with the whole chain glued into its
// label instead of the clean single name every other category row
// shows ("It should be just the parent... not the entire parent child
// connecting notes"). dgeRenderLibraryListView() passes true for this on
// its own top-level call only -- every deeper call (both the recursive
// collapse-continuation just below and normal child iteration in `inner`)
// leaves it unset, so the tap-depth reduction this comment describes is
// completely unchanged below the top level, including inside the grid
// view's own per-category drill-down (dgeRenderLibraryCategoryView),
// which never sets it either.
function dgeRenderNode(node, labelPrefix, depth, nodePath, noCollapseAtRoot) {
  const childKeys = dgeSortChildKeys(nodePath, Object.keys(node.children));
  if (!noCollapseAtRoot && childKeys.length === 1 && node.leaves.length === 0) {
    const only = node.children[childKeys[0]];
    const onlyPath = nodePath ? nodePath + '/' + childKeys[0] : childKeys[0];
    const label = (labelPrefix ? labelPrefix + ' › ' : '') + dgeSegLabel(childKeys[0], onlyPath);
    return dgeRenderNode(only, label, depth, onlyPath);
  }

  const id = 'dgeTree' + (dgeTreeNodeSeq++);
  const inner =
    childKeys.map(k => dgeRenderNode(node.children[k], dgeSegLabel(k, nodePath ? nodePath + '/' + k : k), depth + 1, nodePath ? nodePath + '/' + k : k)).join('') +
    dgeSortLeaves(nodePath, node.leaves).map(leaf => {
      // Pending leaves only ever appear here at all when dgeLibShowPending
      // (admin toggle) is on -- see openLibraryModal(). Muted/dashed and a
      // no-op click (there's no grantha to open yet) rather than styled
      // identically to a real, readable entry.
      if (leaf.populated === false) {
        return `<div class="pop-item" style="margin-left:${depth * 10}px; opacity:.55; cursor:default;"
              onclick="event.stopPropagation()" title="Registered but not yet populated">${leaf.title}
          <span style="margin-left:auto; font-size:9px; font-weight:700; color:var(--muted-text); border:1px dashed var(--line-color,currentColor); border-radius:999px; padding:1px 6px; letter-spacing:.3px;">pending</span>
        </div>`;
      }
      return `<div class="pop-item" style="margin-left:${depth * 10}px;"
            onclick="window.dgeGoToGrantha('${leaf.realSlug}')">${leaf.title}${
        dgeIsRecentlyAdded(leaf.addedAt)
          ? '<span style="margin-left:auto; font-size:9px; font-weight:800; color:#fff; background:var(--accent-red,#7a3b1d); border-radius:999px; padding:2px 6px; letter-spacing:.3px;">NEW</span>'
          : ''
      }</div>`;
    }).join('');

  if (!labelPrefix) return inner;

  const count = dgeCountLeaves(node);
  // "Lifecycle status" for a folder (Category 1's ask): how much of what's
  // registered under it is actually filled in yet. total comes from EVERY
  // registered grantha (populated or not, see openLibraryModal), so it
  // reflects real scaffolding rather than a guess. Falls back to count
  // itself if the path is missing from the map for any reason (shouldn't
  // happen -- every populated leaf's own ancestor prefixes are counted --
  // but a badge silently reading "count/count" is a harmless fallback,
  // never a broken one).
  const total = dgeLibTotalCounts[nodePath] || count;
  const countBadge = total > count
    ? `<span style="font-size:10px; color:var(--accent-red); font-weight:700;" title="${count} of ${total} texts registered under this section are filled in">${count}/${total}</span>`
    : `<span style="font-size:10px; color:var(--muted-text); font-weight:400;" title="All texts registered under this section are filled in">${count}</span>`;
  const isOpen = dgeLibOpenPaths.has(nodePath);
  return `<div style="margin-left:${depth * 10}px;">
    <div onclick="window.dgeToggleTreeNode('${id}', this, '${nodePath}')"
         style="cursor:pointer; padding:7px 4px; font-size:13px; font-weight:600;
                display:flex; align-items:center; gap:6px;">
      <span style="font-size:10px; width:10px;">${isOpen ? '▾' : '▸'}</span>
      <span style="flex:1;">${labelPrefix}</span>
      ${countBadge}
    </div>
    <div id="${id}" style="display:${isOpen ? 'block' : 'none'};">${inner}</div>
  </div>`;
}

// Folds a joinable multi-layer grantha's sibling entries — mula/ plus its
// tika_*/ folders — into ONE tree leaf pointing at the mula spine, so 44
// "श्रीमन्न्यायसुधा — tika_..." rows stop masquerading as unrelated works
// (MULTI_LAYER_READER_ARCHITECTURE.md §4). Strictly manifest-gated:
// only granthas tools/build_layer_manifest.py measured as id-joinable are
// in data/layer_manifest.json, and within one, only layers with
// matched > 0 are absorbed — an unjoinable layer (different id scheme, or
// a mis-split one-item folder from another leaf page) keeps its own row,
// since the stitched view cannot reach it. Detection runs on realSlug
// (the on-disk path); the folded leaf keeps the entry's DISPLAY slug
// (admin move overrides preserved) minus the '/mula' segment.
function dgeFoldLayerEntries(entries, manifest) {
  if (!manifest || !manifest.granthas) return entries;
  const out = [];
  entries.forEach(e => {
    const m = e.realSlug.match(/^(.*)\/(mula|tika_[^/]+)$/);
    const grantha = m ? manifest.granthas[m[1]] : null;
    if (!grantha) { out.push(e); return; }
    if (m[2] === 'mula') {
      const title = grantha.title
        ? dgeToActiveScript(dgeLocalizeNumerals(grantha.title))
        : (e.title || '').replace(/\s+—\s+mula$/, '');
      out.push(Object.assign({}, e, {
        slug: e.slug.replace(/\/mula$/, ''),
        title: title || e.title
      }));
      return;
    }
    const layer = (grantha.layers || []).find(l => l.folder === m[2]);
    if (layer && layer.matched > 0) return; // reachable as a tab on the stitched spine
    out.push(e);
  });
  return out;
}

function dgeCountLeaves(node) {
  let n = node.leaves.length;
  Object.values(node.children).forEach(c => { n += dgeCountLeaves(c); });
  return n;
}

// Which tree nodes the reader has open, by display path — persisted so the
// Library comes back exactly as it was left ("whatever nodes are opened,
// they should remain the same", 1 Sep 2026). Paths, not the sequential
// dgeTreeN ids, because those are re-assigned on every render.
let dgeLibOpenPaths = (function () {
  try { return new Set(JSON.parse(localStorage.getItem('dge_library_open_paths') || '[]')); }
  catch (e) { return new Set(); }
})();
function dgeSaveOpenPaths() {
  try { localStorage.setItem('dge_library_open_paths', JSON.stringify([...dgeLibOpenPaths].slice(-300))); }
  catch (e) { /* ignore */ }
}

window.dgeToggleTreeNode = function(id, headerEl, nodePath) {
  const el = document.getElementById(id);
  if (!el) return;
  const open = el.style.display !== 'none';
  el.style.display = open ? 'none' : 'block';
  const arrow = headerEl.querySelector('span');
  if (arrow) arrow.textContent = open ? '▸' : '▾';
  if (nodePath) {
    if (open) dgeLibOpenPaths.delete(nodePath); else dgeLibOpenPaths.add(nodePath);
    dgeSaveOpenPaths();
  }
};

window.openLibraryModal = async function() {
  if (typeof openModal === 'function') openModal('libraryModal');
  const listEl = document.getElementById('libraryModalList');
  if (!listEl) return;
  listEl.innerHTML = `<div style="padding:20px; text-align:center; color:var(--muted-text); font-size:12px;">Loading library…</div>`;
  const pendingToggleEl = document.getElementById('libraryShowPendingToggle');
  if (pendingToggleEl) pendingToggleEl.checked = dgeLibShowPending;

  const library = await (window.dgeLibraryCatalogPromise || Promise.resolve(null));
  if (!library || !Array.isArray(library.granthas)) {
    listEl.innerHTML = `<div class="note-preview-box" style="margin:0;">Couldn't load the library catalog.</div>`;
    return;
  }

  // Admin-curated overrides — see admin/library.html. Optional; most
  // repos won't have one until the project lead actually curates something.
  await dgeLoadLibraryOverrides();
  // Role-based content gates — see js/role-access.js. Must resolve
  // before the dgeIsHiddenPath() filters below run since that function
  // reads the cached gate list synchronously; loadRoleAccessConfig caches
  // after its first call so this is free on every subsequent open.
  if (typeof window.dgeLoadRoleAccessConfig === 'function') await window.dgeLoadRoleAccessConfig();

  // The layer manifest (see layer-stitch.js / MULTI_LAYER_READER_ARCHITECTURE.md)
  // drives the drawer fold below: a joinable multi-layer grantha shows as
  // ONE leaf, not 44 sibling "granthas". Best-effort — no manifest, no fold.
  const layerManifest = (typeof window.dgeLayerManifestPromise !== 'undefined')
    ? await window.dgeLayerManifestPromise : null;

  // "Show pending" (admin-only, see dgeLibShowPending below): the everyday
  // reader deliberately hides ~590 still-empty leaves so a casual visitor
  // never hits a wall of dead ends -- but an admin browsing the SAME tree
  // wants exactly the opposite, the full scaffolding, so they can see at a
  // glance what's still missing without switching to admin/library.html.
  // Gated on dgeIsAdmin() twice (here AND in the toggle button itself) so
  // a stale localStorage flag from a former admin session can't leak
  // pending leaves to a regular visitor.
  const showPending = dgeLibShowPending && dgeIsAdmin();
  const populated = dgeFoldLayerEntries(
    library.granthas.filter(g => (g.populated || showPending) && !dgeIsAdminOnlyGrantha(g)).map(g => {
      const realSlug = window.dgeGranthaSlug(g.path);
      const slug = dgeEffectiveDisplayPath(realSlug); // where it GROUPS in the tree
      const custom = dgeLibOverrides.labels[slug];
      // g.title is baked into library.json by tools/audit_library.py's
      // derive_title() -- a plain-English humanized slug whenever the data
      // has no real title (which is most granthas: "Mula", "Tika Nirnaya").
      // Left as-is it never responds to the script/language selector, the
      // same gap DGE_PATH_LABELS/dgeAutoLabel already closes for FOLDER
      // labels above. Reuse that same raw (untransliterated) lookup here
      // for the leaf's own last path segment whenever g.title itself has
      // no Devanagari to transliterate -- an admin override is always
      // authoritative and skips this entirely.
      const hasDeva = g.title && /[ऀ-ॿ]/.test(g.title);
      const rawTitle = custom !== undefined ? custom
        : (hasDeva ? g.title : dgeGranthaAutoTitle(realSlug));
      return { slug, realSlug, title: dgeToActiveScript(dgeLocalizeNumerals(rawTitle)), addedAt: g.addedAt || null, facets: g.facets || null, populated: !!g.populated };
    }).filter(e => !dgeIsHiddenPath(e.slug)),
    layerManifest);
  if (!populated.length) {
    listEl.innerHTML = `<div class="note-preview-box" style="margin:0;">No texts are available yet — check back soon.</div>`;
    return;
  }

  // Folder-level completeness badges ("Category 1"'s lifecycle-status ask)
  // need to know how many texts COULD eventually live under a branch, not
  // just how many currently do -- computed from every registered grantha
  // (populated or not), the same grouping/hidden-path rules as the visible
  // tree above, so an admin-hidden or moved branch's total lines up with
  // where its populated count actually renders. Leaves themselves stay
  // populated-only as before (deliberately not showing ~550 empty
  // placeholder entries in the everyday reader) -- this only powers each
  // folder header's own badge.
  const allForTotals = dgeFoldLayerEntries(
    library.granthas.filter(g => !dgeIsAdminOnlyGrantha(g)).map(g => {
      const realSlug = window.dgeGranthaSlug(g.path);
      return { slug: dgeEffectiveDisplayPath(realSlug), realSlug };
    }).filter(e => !dgeIsHiddenPath(e.slug)),
    layerManifest).map(e => e.slug);
  dgeLibTotalCounts = {};
  allForTotals.forEach(slug => {
    const segs = slug.split('/');
    let prefix = '';
    for (let i = 0; i < segs.length - 1; i++) {
      prefix = prefix ? prefix + '/' + segs[i] : segs[i];
      dgeLibTotalCounts[prefix] = (dgeLibTotalCounts[prefix] || 0) + 1;
    }
  });

  dgeTreeNodeSeq = 0;
  dgeLibTree = dgeBuildTree(populated);
  dgeLibTopKeys = dgeSortChildKeys('', Object.keys(dgeLibTree.children));
  dgeLibPopulatedCount = populated.length;
  // Reopen where the reader left off (a drilled category persists alongside
  // the open tree nodes; an invalid stale path falls back to the grid
  // inside dgeRenderLibraryCategoryView itself).
  let savedCat = '';
  try { savedCat = localStorage.getItem('dge_library_category') || ''; } catch (e) { /* ignore */ }
  dgeLibGridCategory = savedCat || null;
  dgeUpdateLibraryDockBtn();
  dgeRenderLibraryRoot();
};

// ---- pin/dock (1 Sep 2026, project-lead ask: "the library when opened
// should have an option to pin it so that the entire library section stays
// opened") ----
// Navigation in this app is a full page load (?path=...), so "stays open"
// means: a persisted flag that auto-reopens the Library drawer after every
// navigation, plus the open-node/category persistence above so it comes
// back in the same state. Auto-reopen is desktop-only (>=760px): on a
// phone the drawer covers the whole reading surface, which would trap the
// reader behind it on every page load.
function dgeLibraryDocked() {
  try { return localStorage.getItem('dge_library_docked') === '1'; } catch (e) { return false; }
}
window.dgeLibraryDocked = dgeLibraryDocked;
window.dgeToggleLibraryDock = function () {
  const on = !dgeLibraryDocked();
  try { localStorage.setItem('dge_library_docked', on ? '1' : '0'); } catch (e) { /* ignore */ }
  dgeUpdateLibraryDockBtn();
  dgeApplyLibraryDock();
};
// 7 Sep 2026: pinned + open on a wide screen = a docked side pane, IDE
// style: the page keeps scrolling and stays clickable beside it (main.css
// body.dge-library-docked), and the edge handle resizes it (below). The
// class follows the drawer's own .show state so every open/close path
// (button, navigation auto-reopen, ❮) keeps it right.
function dgeApplyLibraryDock() {
  const m = document.getElementById('libraryModal');
  const on = !!(m && m.classList.contains('show') && dgeLibraryDocked() && window.innerWidth >= 760);
  document.body.classList.toggle('dge-library-docked', on);
}
(function () {
  const start = function () {
    const m = document.getElementById('libraryModal');
    if (!m) return;
    new MutationObserver(dgeApplyLibraryDock).observe(m, { attributes: true, attributeFilter: ['class'] });
    window.addEventListener('resize', dgeApplyLibraryDock);
    dgeInitLibraryResize();
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
// Drag the drawer's right edge to set its width, kept per device in
// localStorage and applied through --dge-drawer-w (main.css). On a wide
// screen 260 px .. 60 vw; on a phone (7 Sep 2026, the lead's ask) 200 px ..
// 95 vw, so the drawer can be narrowed to see the text behind it.
function dgeInitLibraryResize() {
  const handle = document.getElementById('libraryResizeHandle');
  const m = document.getElementById('libraryModal');
  if (!handle || !m) return;
  const root = document.documentElement;
  const apply = function (w) { root.style.setProperty('--dge-drawer-w', Math.round(w) + 'px'); };
  const clamp = function (w) {
    const wide = window.innerWidth >= 760;
    return Math.max(wide ? 260 : 200, Math.min(w, Math.round(window.innerWidth * (wide ? 0.6 : 0.95))));
  };
  try { const saved = parseInt(localStorage.getItem('dge_library_width'), 10); if (saved >= 200) apply(clamp(saved)); } catch (e) {}
  let dragging = false;
  handle.addEventListener('pointerdown', function (e) {
    dragging = true; handle.setPointerCapture(e.pointerId); m.classList.add('resizing'); e.preventDefault();
  });
  handle.addEventListener('pointermove', function (e) {
    if (!dragging) return;
    apply(clamp(e.clientX));
  });
  const stop = function (e) {
    if (!dragging) return;
    dragging = false; m.classList.remove('resizing');
    try { localStorage.setItem('dge_library_width', String(clamp(e.clientX))); } catch (err) {}
  };
  handle.addEventListener('pointerup', stop);
  handle.addEventListener('pointercancel', stop);
}
function dgeUpdateLibraryDockBtn() {
  const b = document.getElementById('libraryDockBtn');
  if (!b) return;
  const on = dgeLibraryDocked();
  b.style.opacity = on ? '1' : '.45';
  b.style.transform = on ? 'none' : 'rotate(45deg)';
  b.title = on ? 'Pinned — the Library reopens after navigation. Tap to unpin.'
              : 'Pin the Library open (it reopens, as you left it, after navigating)';
}
(function () {
  if (!dgeLibraryDocked()) return;
  const auto = function () {
    if (window.innerWidth >= 760) window.openLibraryModal();
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', auto);
  else setTimeout(auto, 0);
})();

// Everything below builds off dgeLibTree/dgeLibTopKeys, cached by
// openLibraryModal() above -- none of these re-fetch or rebuild the tree,
// so switching view modes or drilling in/out of a category is instant.
let dgeLibPopulatedCount = 0;

function dgeTopLevelLeavesHtml() {
  return dgeSortLeaves('', dgeLibTree.leaves).map(leaf =>
    `<div class="pop-item" onclick="window.dgeGoToGrantha('${leaf.realSlug}')">${leaf.title}${
      dgeIsRecentlyAdded(leaf.addedAt)
        ? '<span style="margin-left:auto; font-size:9px; font-weight:800; color:#fff; background:var(--accent-red,#7a3b1d); border-radius:999px; padding:2px 6px; letter-spacing:.3px;">NEW</span>'
        : ''
    }</div>`
  ).join('');
}

// The List view -- unchanged in substance from before this pass, just
// pulled out into its own function so dgeRenderLibraryRoot() can pick
// between this and the grid.
function dgeRenderLibraryListView() {
  return dgeLibTopKeys.map(k => dgeRenderNode(dgeLibTree.children[k], dgeSegLabel(k, k), 0, k, true)).join('') + dgeTopLevelLeavesHtml();
}

// The new icon-driven home screen: one tile per top-level category
// (same keys/order/counts the list view already computes), each tappable
// straight through to that category's own list (dgeShowLibraryCategory) --
// no separate "grid data model," just a different view of the same tree.
function dgeRenderLibraryGridView() {
  const tiles = dgeLibTopKeys.map(k => {
    const node = dgeLibTree.children[k];
    const count = dgeCountLeaves(node);
    const total = dgeLibTotalCounts[k] || count;
    const countText = total > count ? `${count}/${total}` : `${count}`;
    return `<button type="button" class="dge-lib-tile" onclick="window.dgeShowLibraryCategory('${k}')">
      <span class="dge-lib-tile-icon">${dgeLibraryIconFor(k)}</span>
      <span class="dge-lib-tile-label">${dgeSegLabel(k, k)}</span>
      <span class="dge-lib-tile-count">${countText}</span>
    </button>`;
  }).join('');
  const topLeaves = dgeTopLevelLeavesHtml();
  return `<div class="dge-lib-grid">${tiles}</div>` + (topLeaves ? `<div class="popup-label" style="margin-top:14px;">Other</div>${topLeaves}` : '');
}

/* =========================================================================
   "View By" facets (25 Aug 2026) -- see PENDING.md's Pancharatra pass.

   Principle: the taxonomy tree stays the ONE authoritative hierarchy for
   what a text IS (Ratnatraya/Pramukha/Anya, Vaishnava/Shaiva/Shakta, ...).
   Guna, Madhvacharya-relevance, genre and availability are per-leaf METADATA
   (library.json's "facets", synced from each data.json by
   tools/audit_library.py's derive_facets()), never separate folders -- a
   text is never duplicated across the tree just because it also has a
   scholarly classification. This section regroups the SAME leaves already
   in dgeLibTree by that metadata instead of by taxonomy path, entirely
   client-side (no new fetch: facets rode along on the same catalog
   fetch openLibraryModal() already made).

   Scoped to the category drill-down (dgeRenderLibraryCategoryView) only,
   not the flat List view -- a facet grouping mixing unrelated top-level
   categories (Vedas next to Kavya) would be noise, not a view. List view
   keeps Hierarchy only; a real, disclosed limitation, not an oversight.
   ========================================================================= */
const DGE_VIEW_BY_FACETS = {
  guna_classification: {
    label: 'गुणः', extract: f => f && f.guna_classification,
    values: { sattvika: 'सात्त्विकम्', rajasa: 'राजसम्', tamasa: 'तामसम्', not_specified: 'अनिर्दिष्टम्' }
  },
  madhvacharya_relevance: {
    label: 'माध्वसाम्प्रदायसाम्यम्', extract: f => f && f.madhvacharya_relevance && f.madhvacharya_relevance.level,
    values: {
      direct_quote: 'प्रत्यक्षोद्धृतम्', prominent: 'प्रमुखम्',
      general_authority: 'सामान्यप्रामाण्यम्', other: 'अन्यत्', not_specified: 'अनिर्दिष्टम्'
    }
  },
  text_status: {
    label: 'उपलब्धता', extract: f => f && f.text_status,
    values: {
      extant_complete: '🟢 सम्पूर्णोपलब्धम्', extant_partial: '🟡 आंशिकोपलब्धम्',
      quotation_only: '🟠 उद्धृतांशमात्रम्', lost_unlocated: '🔴 अलभ्यम्', unpopulated: 'अनुपलब्धम्'
    }
  },
  genre: {
    label: 'प्रकारः', extract: f => f && f.genre,
    values: {}
  },
  // Purana-only: whether a work is one of the fixed 18 Mahapuranas, an
  // Upapurana, or one whose Maha/Upa status the tradition itself disputes
  // (e.g. Devi Bhagavata Purana) -- metadata alongside the physical
  // maha_purana/upa_purana split, not a replacement for it (see
  // PENDING.md's 25 Aug Purana pass).
  purana_class: {
    label: 'पुराणवर्गः', extract: f => f && f.purana_class,
    values: { mahapurana: 'महापुराणम्', upapurana: 'उपपुराणम्', disputed: 'विवादास्पदम्', regional: 'प्रादेशिकम्' }
  },
  // "By Author" (27 Aug 2026, Phase 7) -- reuses each data.json's own
  // default_author field (already read by tools/audit_library.py for
  // taxonomy_add()'s _default_author, now also copied into facets by
  // derive_facets()). No values map: like genre, author names are free
  // text, shown via dgeToActiveScript's transliteration same as any other
  // unmapped group label. Known, disclosed limitation: the corpus writes
  // the same person's name in different scripts across files (e.g.
  // "Sri Madhvacharya" vs. "श्रीमदानन्दतीर्थभगवत्पादाचार्यः", his diksha
  // name) with no canonical-name table yet, so those surface as separate
  // groups rather than one -- a later pass, not this one. "unspecified"
  // (~230 files with no author recorded) is folded into the same
  // not-specified sink every other facet uses, rather than showing as its
  // own literal group.
  default_author: {
    label: 'ग्रन्थकर्ता',
    extract: f => {
      const a = f && f.default_author;
      return (a && String(a).trim().toLowerCase() !== 'unspecified') ? a : undefined;
    },
    values: {}
  }
};
const DGE_VIEW_BY_NOT_SPECIFIED = 'not_specified';

function dgeFlattenLeaves(node, out) {
  out = out || [];
  node.leaves.forEach(l => out.push(l));
  Object.keys(node.children).forEach(k => dgeFlattenLeaves(node.children[k], out));
  return out;
}

// Which facet keys are worth offering for this node -- only those where at
// least one leaf underneath actually declares that key at all (regardless
// of whether the value itself is "not_specified"; "Guna: Not specified" is
// a legitimate, visible bucket, not a reason to hide the facet).
function dgeAvailableViewBys(node) {
  const leaves = dgeFlattenLeaves(node);
  return Object.keys(DGE_VIEW_BY_FACETS).filter(fk =>
    leaves.some(l => l.facets && DGE_VIEW_BY_FACETS[fk].extract(l.facets) !== undefined)
  );
}

let dgeLibViewBy = 'hierarchy';
window.dgeSetLibraryViewBy = function (key) {
  dgeLibViewBy = key;
  dgeRenderLibraryRoot();
};

function dgeViewByRowHtml(node) {
  const facetKeys = dgeAvailableViewBys(node);
  if (!facetKeys.length) return '';
  const btn = (key, label) => `<button type="button"
      class="dge-viewby-btn${dgeLibViewBy === key ? ' active' : ''}"
      onclick="window.dgeSetLibraryViewBy('${key}')">${label}</button>`;
  return `<div class="dge-viewby-row">
      <span class="dge-viewby-label">VIEW BY</span>
      ${btn('hierarchy', 'Hierarchy')}
      ${facetKeys.map(fk => btn(fk, DGE_VIEW_BY_FACETS[fk].label)).join('')}
    </div>`;
}

// Groups every leaf under `node` by one facet value and renders flat group
// headers instead of the taxonomy tree -- same leaf row markup dgeRenderNode
// already uses (.pop-item, NEW badge), just regrouped.
//
// Index mode (1 Sep 2026, project-lead ask for a real "view by author"):
// a facet with only a handful of groups (guna, availability) keeps the
// original everything-expanded layout, but one with MANY groups -- By
// Author alone has ~370 distinct names corpus-wide -- becomes a searchable
// NAME INDEX instead: an alphabetical list of collapsed group headers
// (name + work count) with a filter box on top; tapping a name expands
// that author's granthas. Same one-thumb pattern as the tree twisties, so
// it works identically on Android and desktop.
const DGE_FACET_INDEX_THRESHOLD = 9;
window.dgeFilterFacetGroups = function (input) {
  const q = String(input.value || '').trim().toLowerCase();
  document.querySelectorAll('#libraryModalList .dge-facet-group').forEach(g => {
    g.style.display = !q || (g.dataset.name || '').indexOf(q) >= 0 ? '' : 'none';
  });
};
function dgeRenderFacetView(node, facetKey) {
  const cfg = DGE_VIEW_BY_FACETS[facetKey];
  const leaves = dgeFlattenLeaves(node);
  const groups = {};
  leaves.forEach(l => {
    const raw = (l.facets && cfg.extract(l.facets)) || DGE_VIEW_BY_NOT_SPECIFIED;
    (groups[raw] = groups[raw] || []).push(l);
  });
  const indexMode = Object.keys(groups).length > DGE_FACET_INDEX_THRESHOLD;
  const labelOf = k => cfg.values[k] || dgeToActiveScript(k.replace(/_/g, ' '));
  const keys = Object.keys(groups).sort((a, b) => {
    if (a === DGE_VIEW_BY_NOT_SPECIFIED) return 1;   // Not-specified sinks to the bottom
    if (b === DGE_VIEW_BY_NOT_SPECIFIED) return -1;
    // Index mode reads like a directory -- alphabetical by displayed name;
    // the compact few-group layouts keep biggest-group-first.
    if (indexMode) return labelOf(a).localeCompare(labelOf(b));
    return groups[b].length - groups[a].length;
  });
  const search = indexMode
    ? `<input type="search" placeholder="Filter names…" oninput="window.dgeFilterFacetGroups(this)"
         style="width:100%; box-sizing:border-box; margin:2px 0 8px; padding:8px 12px; font:inherit; font-size:13px;
                border:1px solid var(--card-border,#ccc); border-radius:10px; background:var(--card-bg,transparent); color:inherit;">`
    : '';
  return search + keys.map(k => {
    const label = labelOf(k);
    const rows = dgeSortLeaves('', groups[k]).map(leaf =>
      `<div class="pop-item" style="margin-left:10px;" onclick="window.dgeGoToGrantha('${leaf.realSlug}')">${leaf.title}${
        dgeIsRecentlyAdded(leaf.addedAt)
          ? '<span style="margin-left:auto; font-size:9px; font-weight:800; color:#fff; background:var(--accent-red,#7a3b1d); border-radius:999px; padding:2px 6px; letter-spacing:.3px;">NEW</span>'
          : ''
      }</div>`
    ).join('');
    if (indexMode) {
      const gid = 'dgeFacet' + (dgeTreeNodeSeq++);
      // data-name feeds the filter box: matched against both the displayed
      // label and the raw key, so typing in either script (or plain ASCII
      // for a Devanagari-labeled author) still finds the group.
      const needle = (label + ' ' + k).toLowerCase().replace(/"/g, '');
      return `<div class="dge-facet-group" data-name="${needle}">
        <div onclick="window.dgeToggleTreeNode('${gid}', this)"
             style="cursor:pointer; padding:7px 4px; font-size:13px; font-weight:600; display:flex; align-items:center; gap:6px;">
          <span style="font-size:10px; width:10px;">▸</span>
          <span style="flex:1;">${label}</span>
          <span style="font-size:10px; color:var(--muted-text); font-weight:400;">${groups[k].length}</span>
        </div>
        <div id="${gid}" style="display:none;">${rows}</div>
      </div>`;
    }
    return `<div style="margin-top:6px;">
      <div style="padding:6px 4px; font-size:12px; font-weight:700; color:var(--muted-text); display:flex; align-items:center; gap:6px;">
        <span>${label}</span><span style="font-weight:400;">${groups[k].length}</span>
      </div>
      ${rows}
    </div>`;
  }).join('');
}

// Admin-only deep link into the Library Manager's completion tracker
// (admin/library.html), pre-filtered/scrolled to this section (its own
// ?section= handling, see that file's start()). Super-admin gated, not the
// broader dgeIsAdmin() tier -- that page's own gate is super-admin only,
// so showing this to a plain admin would just walk them into its passkey
// prompt. "Top right" of the section view per the project lead's ask: a
// flex child pushed to the far end of the breadcrumb row via margin-left:auto.
function dgeSectionTrackerHtml(key) {
  if (!dgeIsSuperAdmin()) return '';
  return `<a href="../admin/library.html?section=${encodeURIComponent(key)}" target="_blank" rel="noopener"
      style="margin-left:auto; font-size:11px; color:var(--muted-text); text-decoration:none; white-space:nowrap;"
      onclick="event.stopPropagation()" title="Open the completion tracker for this section (super-admin)">📊 Progress</a>`;
}

// One category's own subtree, reached by tapping its grid tile -- reuses
// dgeRenderNode exactly as the list view does, just scoped to one branch
// with a breadcrumb back to the grid instead of every branch at once.
// dgeLibViewBy != 'hierarchy' swaps that for dgeRenderFacetView() instead,
// same leaves, grouped by metadata rather than by taxonomy path.
//
// `key` was originally always a single top-level segment (a grid tile's own
// key). Generalized to accept a full slash path -- walks dgeLibTree one
// segment at a time -- so a taxonomy-breadcrumb ancestor click (any depth,
// e.g. "darshana/vedanta/dvaita" from a tika-page lineage strip or a
// corpus-search result) can land here too, not just a grid tile tap. A
// single-segment key still resolves in exactly one step, so every existing
// caller (the grid tiles) is unaffected.
function dgeRenderLibraryCategoryView(path) {
  const segs = String(path || '').split('/').filter(Boolean);
  let node = dgeLibTree;
  const resolved = [];
  for (const seg of segs) {
    if (!node || !node.children || !node.children[seg]) break;
    node = node.children[seg];
    resolved.push(seg);
  }
  if (!resolved.length) return dgeRenderLibraryGridView(); // nothing on this path exists -- fail back to the grid rather than a blank screen
  const body = dgeLibViewBy === 'hierarchy'
    ? dgeRenderNode(node, '', 0, resolved.join('/'))
    : dgeRenderFacetView(node, dgeLibViewBy);
  const crumbs = resolved.map((seg, i) => {
    const upToHere = resolved.slice(0, i + 1).join('/');
    if (i === resolved.length - 1) return `<span class="dge-lib-crumb-current">${dgeSegLabel(seg, upToHere)}</span>`;
    return `<span class="dge-lib-crumb-seg" onclick="event.stopPropagation(); window.dgeShowLibraryCategory('${upToHere.replace(/'/g, "\\'")}')">${dgeSegLabel(seg, upToHere)}</span><span class="dge-lib-crumb-sep">›</span>`;
  }).join('');
  return `<div class="dge-lib-breadcrumb">
      <span class="dge-lib-crumb-back" onclick="window.dgeShowLibraryGrid()">❮</span> ${crumbs}${dgeSectionTrackerHtml(resolved.join('/'))}
    </div>` + dgeViewByRowHtml(node) + body;
}

window.dgeShowLibraryCategory = function (path) {
  dgeLibGridCategory = path;
  dgeLibViewBy = 'hierarchy';
  dgeRenderLibraryRoot();
};

// Cross-page taxonomy deep-link target (see dge-breadcrumb.js's real page
// headers, layer-stitch.js's lineage strip, and global-search.js's per-hit
// crumbs): the target for an ANCESTOR taxonomy segment that has no readable
// grantha of its own (a pure category, e.g. "darshana/vedanta/dvaita") --
// there is no data.json to open as a reader page, so the honest navigation
// is the Library browser itself, drilled to that node. A LEAF grantha
// segment still links straight to the reader via dgeGoToGrantha's own
// ?path= route (opens the text itself, more useful than the modal). Waits
// on the same catalog fetch openLibraryModal() already awaits, so a link
// followed before the catalog resolves still lands on the right node
// instead of the bare grid.
window.dgeOpenLibraryToPath = async function (path) {
  await window.openLibraryModal();
  if (path) window.dgeShowLibraryCategory(path);
};
window.dgeShowLibraryGrid = function () {
  dgeLibGridCategory = null;
  dgeLibViewBy = 'hierarchy';
  dgeRenderLibraryRoot();
};

function dgeRenderLibraryRoot() {
  const listEl = document.getElementById('libraryModalList');
  if (!listEl || !dgeLibTree) return;
  const mode = dgeGetLibraryViewMode();
  // Super-admin only (see dgeOverlayManagerDraft): this browser holds an
  // unexported Library Manager draft, and THAT is what's rendered below.
  const draftNote = dgeLibOverridesDraftPreview
    ? `<div style="font-size:11px; margin-bottom:8px; padding:7px 10px; border:1px dashed var(--accent-gold,#b8860b); border-radius:8px; color:var(--accent-red,#7a3b1d);">
        🛠 <b>Draft preview</b> — showing this browser's unexported Library Manager draft.
        Readers still see the committed file; use <b>⬇ Export overrides</b> in the
        <a href="../admin/library.html" target="_blank" rel="noopener" style="color:inherit;">Library Manager</a>
        and commit it to publish.</div>`
    : '';
  const header = draftNote + `<div style="font-size:11px; color:var(--muted-text); margin-bottom:8px;">${dgeLibPopulatedCount} text(s) available</div>`;
  if (dgeLibGridCategory) {
    listEl.innerHTML = header + dgeRenderLibraryCategoryView(dgeLibGridCategory);
  } else {
    // Root-level View By (1 Sep 2026, project-lead report: "not showing
    // the view by authors section anywhere"): the facet row used to exist
    // only inside a category drill-down, so a reader who never drilled in
    // never saw it. Offered at the root too now — By Author across the
    // whole library is exactly the case that wants the widest scope.
    const vb = dgeViewByRowHtml(dgeLibTree);
    const body = dgeLibViewBy !== 'hierarchy'
      ? dgeRenderFacetView(dgeLibTree, dgeLibViewBy)
      : (mode === 'grid' ? dgeRenderLibraryGridView() : dgeRenderLibraryListView());
    listEl.innerHTML = header + vb + body;
  }
  // Where the reader is (root vs a drilled category) survives navigation —
  // part of the same "keep my place" ask as the dock/open-node persistence.
  try { localStorage.setItem('dge_library_category', dgeLibGridCategory || ''); } catch (e) { /* ignore */ }
}

// Quick Search entry point — parses e.g. "rv1.1.3" (see
// dgeParseQuickSearchQuery in config.js) and navigates straight to that
// verse, reusing dgeGoToGrantha's own path-encoding rule. The actual
// verse selection happens after the new page loads and normalizes its
// data (see the jumpVedicId/jumpShloka handling in core.js) — a full
// navigation is unavoidable here since the target grantha's data isn't
// loaded yet at the point this runs.
// Folder/section-name fallback for Quick Jump — e.g. typing "mahabharata
// sabha parva" or "chandas" with no verse number at all. Titles in
// library.json are NOT reliably searchable text: many are Devanagari
// (महाभारतम् आदिपर्व), some are plain English (Ganguli's own titles),
// depending on which importer wrote them — but every grantha's realSlug
// (its taxonomy path, e.g. "itihasa/mahabharata/adi_parva/mula") is
// always plain ASCII, underscore-separated. Matching against a
// normalized form of THAT, not the display title, is what makes this
// work regardless of which script the title happens to be in.
function dgeNormalizeForMatch(s) {
  return String(s || '').toLowerCase().replace(/[_/]+/g, ' ').replace(/[^a-z0-9\s]/g, '').replace(/\s+/g, ' ').trim();
}
async function dgeFuzzyMatchGrantha(text) {
  const q = dgeNormalizeForMatch(text);
  if (!q) return null;
  const library = await (window.dgeLibraryCatalogPromise || Promise.resolve(null));
  if (!library || !Array.isArray(library.granthas)) return null;
  const qWords = q.split(' ').filter(Boolean);
  let best = null, bestScore = -1, bestIsWholeWord = false;
  library.granthas.forEach(function (g) {
    if (!g.populated || dgeIsAdminOnlyGrantha(g)) return;
    const realSlug = window.dgeGranthaSlug(g.path);
    const hay = dgeNormalizeForMatch(realSlug + ' ' + (g.title || ''));
    if (!hay) return;
    const hayWords = hay.split(' ');
    // Prefer a WHOLE-WORD match (every query word is one of the slug's own
    // underscore/slash-delimited segments) over a raw substring one --
    // reported live: searching the single word "vastu" here landed on the
    // Buddhist Saṅghabhedavastu, because "vastu" merely sits inside that
    // one unbroken slug segment ("sanghabhedavastu"), not because it names
    // that text. Substring containment is kept only as a fallback for a
    // MULTI-word query ("mahabharata sabha" should still match a grantha
    // whose path only spells them run together) -- a coincidence across
    // every word of a real phrase is far less likely than one short word
    // landing inside one longer unrelated compound.
    const allWholeWords = qWords.every(function (w) { return hayWords.indexOf(w) !== -1; });
    const allSubstr = qWords.length > 1 && qWords.every(function (w) { return hay.indexOf(w) !== -1; });
    if (!allWholeWords && !allSubstr) return;
    let score = 100 - Math.min(99, hay.length - q.length);
    if (hay === q) score += 1000;
    else if (hay.indexOf(q) === 0) score += 200;
    if (allWholeWords) score += 500; // a real word always outranks a mere substring
    if (score > bestScore) { bestScore = score; best = realSlug; bestIsWholeWord = allWholeWords; }
  });
  // A single-word query that only ever matched as a raw substring (never a
  // real whole word, anywhere in the library) is too weak a signal to
  // silently navigate on -- exactly the false positive above. Reporting
  // "no match" here instead lets the caller fall through to the real
  // full-text corpus search for a single word (see dgeQuickJump below),
  // rather than landing on a wrong grantha with no way to tell why.
  if (best && !bestIsWholeWord && qWords.length < 2) return null;
  return best;
}

window.dgeQuickJump = function(text) {
  const target = (typeof window.dgeParseQuickSearchQuery === 'function') ? window.dgeParseQuickSearchQuery(text) : null;
  if (target) {
    const readableSlug = /^[a-z0-9_/]+$/i.test(target.granthaPath) ? target.granthaPath : encodeURIComponent(target.granthaPath);
    let url = window.location.pathname + '?path=' + readableSlug;
    if (target.vedicId) url += '&jumpVedicId=' + encodeURIComponent(target.vedicId);
    else if (target.shlokaNumber) url += '&jumpShloka=' + target.shlokaNumber;
    window.location.href = url;
    return true;
  }
  // Not a recognized "abbrev + verse number" pattern (e.g. "rv1.1.3") —
  // try matching it as a folder/section/grantha name instead before
  // giving up. Async, so this path can't return true/false synchronously
  // the way the pattern-match path above does; it resolves the
  // navigation (or the "not recognized" toast) itself.
  dgeFuzzyMatchGrantha(text).then(function (slug) {
    if (slug) { window.dgeGoToGrantha(slug); return; }
    // A single word that doesn't name any grantha/section is very likely a
    // CONTENT word the reader is trying to find IN the corpus, not
    // navigate BY name -- reported live: typing "Vastu" here landed
    // nowhere useful, and the word itself was never actually looked for in
    // any text (this box only ever matched grantha slugs/titles, never
    // content). Route it to the real full-text search instead of a dead
    // "not recognized" toast; a multi-word phrase still gets the toast,
    // since that's more likely a mistyped abbreviation than a search term.
    const words = String(text).trim().split(/\s+/).filter(Boolean);
    if (words.length === 1 && typeof window.DGEGlobalSearch === 'object' && window.DGEGlobalSearch.open) {
      dgeQuickJumpToGlobalSearch(words[0]);
      return;
    }
    if (typeof showToast === 'function') showToast('Not recognized — try e.g. "rv1.1.3", "pns5", or a section name like "mahabharata sabha parva".');
  });
  return false;
};

// The global search draws over the drawer, and on a phone the drawer's
// open state left the search panel sitting on top of a scrolled-off,
// keyboard-shrunk page (7 Sep 2026 screenshot). Close the drawer first --
// unless it is the pinned side pane on a wide screen, which is furniture.
function dgeQuickJumpToGlobalSearch(q) {
  dgeQuickJumpHide();
  if (!(dgeLibraryDocked() && window.innerWidth >= 760) && typeof closeModal === 'function') closeModal('libraryModal');
  window.DGEGlobalSearch.open(q);
}

// ---------------------------------------------------------------------
// Quick-jump typeahead (7 Sep 2026, the lead's ask: "start typing something
// and get intellisense of the library items shown below; clicking on it
// should take me to that grantha or folder"). A flat index of every folder
// and populated grantha is built once per catalog render from the same
// tree the drawer shows (dgeLibTree), so admin relabels, hidden paths and
// layer folds are all already applied. Matching is script-agnostic: the
// slug (ASCII), the label as displayed, and the label's HK
// transliteration are all searched, so "rigveda", "ऋग्वेद" and "Rgveda"
// find the same row.
// ---------------------------------------------------------------------
let dgeQjIndex = null, dgeQjIndexTree = null, dgeQjRows = [], dgeQjActive = -1;
const DGE_QJ_MAX = 12;
function dgeQjLatin(text) {
  if (!/[ऀ-ॿ]/.test(text) || typeof window.applyTransliteration !== 'function') return '';
  try { return String(window.applyTransliteration(text, 'hk') || ''); } catch (e) { return ''; }
}
function dgeQjBuildIndex() {
  if (dgeQjIndex && dgeQjIndexTree === dgeLibTree) return dgeQjIndex;
  const rows = [];
  const walk = function (node, nodePath) {
    Object.keys(node.children || {}).forEach(function (k) {
      const p = nodePath ? nodePath + '/' + k : k;
      const label = dgeSegLabel(k, p);
      rows.push({ kind: 'folder', path: p, title: label, n: dgeCountLeaves(node.children[k]),
        hay: dgeNormalizeForMatch(p + ' ' + label + ' ' + dgeQjLatin(label)), raw: String(label).toLowerCase() });
      walk(node.children[k], p);
    });
    (node.leaves || []).forEach(function (leaf) {
      if (leaf.populated === false) return;
      rows.push({ kind: 'grantha', path: leaf.slug, realSlug: leaf.realSlug, title: leaf.title,
        hay: dgeNormalizeForMatch(leaf.realSlug + ' ' + leaf.slug + ' ' + leaf.title + ' ' + dgeQjLatin(leaf.title)), raw: String(leaf.title).toLowerCase() });
    });
  };
  if (dgeLibTree) walk(dgeLibTree, '');
  dgeQjIndex = rows; dgeQjIndexTree = dgeLibTree;
  return rows;
}
function dgeQjMatch(text) {
  const q = dgeNormalizeForMatch(text);
  const rawQ = String(text || '').trim().toLowerCase();
  const words = q.split(' ').filter(Boolean);
  if (!words.length && !rawQ) return [];
  const out = [];
  dgeQjBuildIndex().forEach(function (r) {
    let score = 0;
    if (words.length && words.every(function (w) { return r.hay.indexOf(w) !== -1; })) {
      const segs = r.hay.split(' ');
      score = 100 - Math.min(90, r.hay.length / 4);
      if (words.every(function (w) { return segs.some(function (sg) { return sg.indexOf(w) === 0; }); })) score += 300; // starts a segment
      if (words.every(function (w) { return segs.indexOf(w) !== -1; })) score += 200;                          // is a whole segment
      if (r.raw.indexOf(rawQ) === 0) score += 250;                                                              // the title itself begins with it
    } else if (rawQ && /[ऀ-ॿ]/.test(rawQ) && r.raw.indexOf(rawQ) !== -1) {
      score = 400 + (r.raw.indexOf(rawQ) === 0 ? 250 : 0) - Math.min(90, r.raw.length / 2);
    }
    if (score > 0) out.push([score + (r.kind === 'folder' ? 40 : 0) - r.path.split('/').length * 6, r]);
  });
  out.sort(function (a, b) { return b[0] - a[0]; });
  // Folders outrank texts, but never crowd them out entirely: "rigv" should
  // list the maṇḍalas after the Ṛgveda folders, not twelve folders alone.
  const hasText = out.some(function (x) { return x[1].kind === 'grantha'; });
  const picked = []; let folders = 0;
  for (let i = 0; i < out.length && picked.length < DGE_QJ_MAX; i++) {
    const r = out[i][1];
    if (r.kind === 'folder') { if (hasText && folders >= 7) continue; folders++; }
    picked.push(r);
  }
  return picked;
}
function dgeQjEsc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;'); }
function dgeQjPathLabel(path) {
  const segs = String(path).split('/');
  const parents = segs.slice(0, -1);
  return parents.map(function (sg, i) { return dgeSegLabel(sg, parents.slice(0, i + 1).join('/')); }).join(' › ');
}
function dgeQuickJumpHide() {
  const box = document.getElementById('quickJumpSuggest');
  const input = document.getElementById('quickJumpInput');
  if (box) { box.hidden = true; box.innerHTML = ''; }
  if (input) input.setAttribute('aria-expanded', 'false');
  dgeQjRows = []; dgeQjActive = -1;
}
function dgeQjPaint() {
  const box = document.getElementById('quickJumpSuggest');
  if (!box) return;
  box.innerHTML = dgeQjRows.map(function (r, i) {
    const cls = 'dge-qj-item' + (i === dgeQjActive ? ' active' : '') + (r.kind === 'search' ? ' dge-qj-more' : '');
    const icon = r.kind === 'folder' ? '📁' : r.kind === 'grantha' ? '📖' : r.kind === 'jump' ? '⤴' : '🔍';
    const sub = r.kind === 'folder' ? (r.n ? r.n + ' text' + (r.n === 1 ? '' : 's') + (r.path.indexOf('/') > 0 ? ' · ' + dgeQjPathLabel(r.path) : '') : dgeQjPathLabel(r.path))
      : r.kind === 'grantha' ? dgeQjPathLabel(r.path) : '';
    return `<div class="${cls}" role="option" aria-selected="${i === dgeQjActive}" data-i="${i}"
        onmousedown="event.preventDefault()" onclick="window.dgeQuickJumpPick(${i})">
        <span class="dge-qj-kind">${icon}</span><span class="dge-qj-title">${dgeQjEsc(r.title)}</span>${sub ? '<span class="dge-qj-path">' + dgeQjEsc(sub) + '</span>' : ''}</div>`;
  }).join('');
  box.hidden = !dgeQjRows.length;
  const input = document.getElementById('quickJumpInput');
  if (input) input.setAttribute('aria-expanded', dgeQjRows.length ? 'true' : 'false');
  const act = box.querySelector('.dge-qj-item.active');
  if (act && act.scrollIntoView) act.scrollIntoView({ block: 'nearest' });
}
window.dgeQuickJumpSuggest = function (text) {
  const t = String(text || '').trim();
  if (!t) { dgeQuickJumpHide(); return; }
  const rows = [];
  const target = (typeof window.dgeParseQuickSearchQuery === 'function') ? window.dgeParseQuickSearchQuery(t) : null;
  if (target) rows.push({ kind: 'jump', title: 'Jump to ' + target.label + ' ' + (target.vedicId || target.shlokaNumber || ''), text: t });
  if (!dgeLibTree) {
    // Drawer just opened and the catalog is still loading: fill in when it lands.
    (window.dgeLibraryCatalogPromise || Promise.resolve()).then(function () {
      const input = document.getElementById('quickJumpInput');
      if (dgeLibTree && input && input.value.trim() === t) window.dgeQuickJumpSuggest(t);
    });
  } else {
    dgeQjMatch(t).forEach(function (r) { rows.push(r); });
  }
  if (t.split(/\s+/).length === 1 && typeof window.DGEGlobalSearch === 'object')
    rows.push({ kind: 'search', title: 'Search all texts for “' + t + '”', text: t });
  dgeQjRows = rows; dgeQjActive = -1;
  dgeQjPaint();
};
window.dgeQuickJumpPick = function (i) {
  const r = dgeQjRows[i];
  if (!r) return;
  if (r.kind === 'grantha') { dgeQuickJumpHide(); window.dgeGoToGrantha(r.realSlug); return; }
  if (r.kind === 'folder') {
    dgeQuickJumpHide();
    const input = document.getElementById('quickJumpInput');
    if (input) input.value = '';
    window.dgeShowLibraryCategory(r.path);
    const list = document.getElementById('libraryModalList');
    if (list && list.scrollIntoView) list.scrollIntoView({ block: 'start', behavior: 'smooth' });
    return;
  }
  if (r.kind === 'jump') { dgeQuickJumpHide(); window.dgeQuickJump(r.text); return; }
  if (r.kind === 'search') { dgeQuickJumpToGlobalSearch(r.text); }
};
// Keyboard on the input: ↓/↑ move through the list, Enter opens the
// highlighted row, Esc closes the list. Returns true when the key was
// consumed, so index.html's own Enter → dgeQuickJump fallback still runs
// when nothing is highlighted.
window.dgeQuickJumpKey = function (ev) {
  if (!dgeQjRows.length) return false;
  if (ev.key === 'ArrowDown' || ev.key === 'ArrowUp') {
    ev.preventDefault();
    const n = dgeQjRows.length;
    dgeQjActive = ev.key === 'ArrowDown' ? (dgeQjActive + 1) % n : (dgeQjActive - 1 + n) % n;
    dgeQjPaint();
    return true;
  }
  if (ev.key === 'Escape') { dgeQuickJumpHide(); return true; }
  if (ev.key === 'Enter' && dgeQjActive >= 0) { ev.preventDefault(); window.dgeQuickJumpPick(dgeQjActive); return true; }
  return false;
};
(function () {
  const wire = function () {
    const input = document.getElementById('quickJumpInput');
    if (!input) return;
    input.addEventListener('blur', function () { setTimeout(dgeQuickJumpHide, 150); });
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', wire); else wire();
})();

// A handful of taxonomy leaves are not shloka-shaped at all (a root/word
// list, not verses) and have their own dedicated browser/search page
// instead of being readable through the general reader. Opening one of
// these via the normal ?path= route fed render.html data it has no
// renderer for — the library entry existed and looked clickable, but
// nothing ever appeared ("Dhatu Patha... is not loading"). Keyed by the
// realSlug PREFIX so a future sibling under the same folder is covered
// without a new entry.
const DGE_SPECIAL_PAGES = [
  { prefix: 'vedanga/vyakarana/dhatupatha', page: 'vyakarana/dhatu.html' },
  { prefix: 'vedanga/vyakarana/shabdapatha', page: 'vyakarana/shabda.html' }
];
function dgeSpecialPageFor(realSlug) {
  const hit = DGE_SPECIAL_PAGES.find(function (e) {
    return realSlug === e.prefix || realSlug.indexOf(e.prefix + '/') === 0;
  });
  return hit ? hit.page : null;
}

window.dgeGoToGrantha = function(slug) {
  const special = dgeSpecialPageFor(slug);
  if (special) { window.location.href = special; return; }
  // Grantha slugs are always plain lowercase letters, digits, underscores,
  // and slashes by design (see taxonomy.json) — none of that needs
  // percent-encoding, and encodeURIComponent turning every "/" into
  // "%2F" just makes the address bar hard to read for no real benefit.
  // Falls back to full encoding only if something outside that safe set
  // ever shows up, so this can't silently produce a broken URL.
  const readableSlug = /^[a-z0-9_/]+$/i.test(slug) ? slug : encodeURIComponent(slug);
  window.location.href = window.location.pathname + '?path=' + readableSlug;
};

// 24 Aug 2026: Previous/Next Sarga/Adhyaya/Maṇḍala/Kāṇḍa navigator --
// project lead's direct ask, confirmed via investigation to not exist
// anywhere ("I already requested that there may be a navigator... that
// is currently missing"). Every multi-sarga/multi-mandala work (e.g.
// Raghavendra Vijaya's sarga_01..sarga_10, the Rigveda's mandala_01..10)
// stores each sub-unit as its OWN grantha entry/data.json -- there was no
// way to step to the next one without going back through the Library
// drawer's taxonomy tree. Pure UI wiring: reuses the SAME data.json's
// numbered-folder naming convention (dgeAutoLabel/DGE_NUMBERED_PREFIXES
// above) and library.json catalog this file already parses for the tree
// view -- no new data pipeline or metadata backfill needed. Deliberately
// no change to grantha data.json itself: prev/next are computed fresh
// from the catalog on every load, so a newly-added sarga is picked up
// automatically without touching every sibling file's own metadata.
let dgeChapterNavPrevSlug = null, dgeChapterNavNextSlug = null;
let dgeChapterNavPrefix = null, dgeChapterNavIdx = 0, dgeChapterNavTotal = 0;

window.dgeInitChapterNav = async function() {
  const row = document.getElementById('chapterNavRow');
  if (!row) return;
  row.style.display = 'none';
  dgeChapterNavPrevSlug = null;
  dgeChapterNavNextSlug = null;

  const slug = window.currentGranthaSlug;
  const lastSlash = slug ? slug.lastIndexOf('/') : -1;
  if (lastSlash < 0) return; // top-level grantha (e.g. stotra/xyz) -- no numbered parent to page within
  const parentPath = slug.slice(0, lastSlash);
  const lastSeg = slug.slice(lastSlash + 1);
  const m = lastSeg.match(/^([a-z]+)_(\d+)$/i);
  if (!m || !DGE_NUMBERED_PREFIXES[m[1].toLowerCase()]) return; // this leaf isn't a numbered sub-unit (sarga_2 etc.)
  const prefix = m[1].toLowerCase();

  const library = await (window.dgeLibraryCatalogPromise || Promise.resolve(null));
  if (!library || !Array.isArray(library.granthas)) return;

  const prefixRe = new RegExp('^' + prefix + '_\\d+$', 'i');
  const siblings = library.granthas
    .filter(g => g.populated && !dgeIsAdminOnlyGrantha(g))
    .map(g => window.dgeGranthaSlug(g.path))
    .filter(s => {
      const sl = s.lastIndexOf('/');
      return sl >= 0 && s.slice(0, sl) === parentPath && prefixRe.test(s.slice(sl + 1));
    });
  if (siblings.length < 2) return; // this is the only sub-unit under this parent -- nothing to page between

  siblings.sort(dgeCompareSlugs);
  const idx = siblings.indexOf(slug);
  if (idx === -1) return; // current grantha isn't itself in the populated catalog (shouldn't happen if it loaded at all)

  dgeChapterNavPrevSlug = idx > 0 ? siblings[idx - 1] : null;
  dgeChapterNavNextSlug = idx < siblings.length - 1 ? siblings[idx + 1] : null;
  dgeChapterNavPrefix = prefix;
  dgeChapterNavIdx = idx;
  dgeChapterNavTotal = siblings.length;
  window.dgeRenderChapterNav();
};

// Re-renders just the LABEL TEXT of the already-computed nav (prev/next
// slugs don't change with script) -- called both from dgeInitChapterNav
// above and from renderStotraChrome() (core.js) whenever the display
// script changes, the same way that function already re-labels every
// other piece of chrome.
window.dgeRenderChapterNav = function() {
  const row = document.getElementById('chapterNavRow');
  if (!row || (!dgeChapterNavPrevSlug && !dgeChapterNavNextSlug)) return;
  const prefix = dgeChapterNavPrefix, idx = dgeChapterNavIdx, total = dgeChapterNavTotal;

  const prevBtn = document.getElementById('chapterNavPrevBtn');
  const nextBtn = document.getElementById('chapterNavNextBtn');
  const posEl = document.getElementById('chapterNavPosition');

  if (prevBtn) {
    if (dgeChapterNavPrevSlug) {
      prevBtn.style.visibility = 'visible';
      prevBtn.textContent = '❮ ' + dgeSegLabel(dgeChapterNavPrevSlug.split('/').pop());
    } else {
      prevBtn.style.visibility = 'hidden';
    }
  }
  if (nextBtn) {
    if (dgeChapterNavNextSlug) {
      nextBtn.style.visibility = 'visible';
      nextBtn.textContent = dgeSegLabel(dgeChapterNavNextSlug.split('/').pop()) + ' ❯';
    } else {
      nextBtn.style.visibility = 'hidden';
    }
  }
  if (posEl) {
    posEl.textContent = dgeToActiveScript(DGE_NUMBERED_PREFIXES[prefix]) + ' ' +
      dgeToActiveScript(dgeDevaNum(idx + 1)) + ' / ' + dgeToActiveScript(dgeDevaNum(total));
  }
  row.style.display = 'flex';
};

window.dgeGoToChapterSibling = function(dir) {
  const slug = dir === 'prev' ? dgeChapterNavPrevSlug : dgeChapterNavNextSlug;
  if (slug) window.dgeGoToGrantha(slug);
};
