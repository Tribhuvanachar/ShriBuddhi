/* =========================================================================
   dvaita-catalog.js — द्वैतवेदान्तग्रन्थानुक्रमणी.

   Reads the committed bibliography (data/catalogs/
   dvaita_grantha_anukramani.json, built by
   tools/import_dvaita_grantha_anukramani.py) and lays an editable overlay
   over it. The import is never rewritten in place; every correction a
   scholar makes lands in a separate overrides file:

       data/catalogs/dvaita_grantha_anukramani.overrides.json

   Edits are held in localStorage as a draft the moment they are made and
   go to GitHub only when someone presses Sync — same shape as
   admin/ocr-review.html, and the reason this page does NOT use Firestore:
   the master data belongs in the repo, reviewable in a diff, and the
   Firestore path made editing depend on a users/{uid} role document that
   a first-time signer-in on this page never had, so it just said no.

   Everything the page derives — canonical spellings, suggested parent
   links, cross-corpus matches — is a proposal shown for review. Accepting
   one writes it to the overrides; nothing is applied silently.
   ========================================================================= */
(function () {
  "use strict";

  window.DGE_VERSIONS = window.DGE_VERSIONS || {};
  window.DGE_VERSIONS['dvaita-catalog.js'] = 'v2.0';

  var DATA_URL = "../data/catalogs/dvaita_grantha_anukramani.json";
  var OVERRIDES_PATH = "data/catalogs/dvaita_grantha_anukramani.overrides.json";
  var OVERRIDES_URL = "../data/catalogs/dvaita_grantha_anukramani.overrides.json";
  var DRAFT_KEY = "dge.dvc.draft";
  var CHUNK = 250;

  var TAG_FIELDS = ["vibhaga", "vishayaVibhaga", "prasthana"];
  var FIELD_LABEL = {
    grantha: "ग्रन्थः · title", karta: "कर्तृ · author",
    vibhaga: "विभागः", vishayaVibhaga: "विषयविभागः", prasthana: "प्रस्थानम्",
    availability: "उपलब्धता", status: "स्थितिः", labels: "अङ्कनानि · labels",
    note: "टिप्पणम् · note"
  };
  // Columns the grid lets you edit. grantha/karta are editable too: a
  // misspelled title is exactly the kind of thing this page exists to fix.
  var EDITABLE = ["grantha", "karta", "vibhaga", "vishayaVibhaga", "prasthana",
                   "availability", "status", "labels", "note"];

  var LS = {
    get: function (k, d) { try { var v = localStorage.getItem("dge.dvc." + k); return v === null ? d : JSON.parse(v); } catch (e) { return d; } },
    set: function (k, v) { try { localStorage.setItem("dge.dvc." + k, JSON.stringify(v)); } catch (e) {} }
  };

  var state = {
    items: [], byId: {}, masters: { categories: [], authors: [], titles: [] },
    suggestions: { parentLinks: [] }, crossLinks: {}, duplicates: {}, dropped: [],
    catById: {}, authById: {}, titleById: {},
    ov: null,               // the overrides object being edited
    committedSha: null,     // GitHub blob sha of the committed overrides file
    dirty: false,
    view: LS.get("view", "tree"),
    tab: "catalogue",
    script: LS.get("script", "deva"),
    sort: LS.get("sort", "row"),
    q: "",
    tagFilters: { vibhaga: new Set(), vishayaVibhaga: new Set(), prasthana: new Set() },
    alpha: null,   // {script:'deva'|'roman', letter}
    labelFilter: "",
    onlyFlag: "",
    expanded: {},           // id -> true, tree expansion
    personFilter: null,     // {personId, authorIds:Set} — set by a #person= deep link
    view_ids: [],           // current filtered id list (flat views)
    shown: 0,
    children: {},           // effective parentId -> [childId...]
    roots: []
  };

  function $(s, r) { return (r || document).querySelector(s); }
  function $all(s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); }
  function esc(s) { var d = document.createElement('div'); d.textContent = s == null ? '' : String(s); return d.innerHTML; }

  /* ---------------- overrides: the editable layer ---------------- */
  function emptyOverrides() {
    return {
      _readme: [
        "Scholar corrections layered over data/catalogs/dvaita_grantha_anukramani.json.",
        "Written by dvaita-grantha-anukramani/ (Sync to GitHub). The imported",
        "catalogue itself is never edited -- re-running the importer keeps every",
        "correction here intact.",
        "canonical: variant spelling -> the spelling to show everywhere, per kind.",
        "parents:   row id -> the row id that is really its parent.",
        "rows:      row id -> field overrides, labels and a note for that one row.",
        "review:    row id -> retain | delete | merge (duplicate decisions).",
        "links:     row/master id -> a confirmed cross-corpus match.",
        "extraTerms: kind -> terms a curator added that the sheet never used."
      ],
      version: 1, updatedAt: null,
      canonical: { category: {}, author: {}, title: {} },
      parents: {}, rows: {}, review: {}, links: {},
      extraTerms: { category: [], author: [], title: [] }
    };
  }

  function loadDraft() { try { var raw = localStorage.getItem(DRAFT_KEY); return raw ? JSON.parse(raw) : null; } catch (e) { return null; } }
  function saveDraft() {
    try { localStorage.setItem(DRAFT_KEY, JSON.stringify(state.ov)); } catch (e) {}
    state.dirty = true;
    updateSyncBar();
  }
  function discardDraft() {
    try { localStorage.removeItem(DRAFT_KEY); } catch (e) {}
    location.reload();
  }

  function countEdits() {
    if (!state.ov) return 0;
    var c = state.ov.canonical;
    return Object.keys(c.category).length + Object.keys(c.author).length + Object.keys(c.title).length
      + Object.keys(state.ov.parents).length + Object.keys(state.ov.rows).length
      + Object.keys(state.ov.review).length + Object.keys(state.ov.links).length
      + Object.keys(state.ov.extraTerms || {}).reduce(function (n, k) { return n + state.ov.extraTerms[k].length; }, 0);
  }

  /* ---------------- effective values ---------------- */
  // A displayed value is: this row's own override, else the canonical
  // spelling chosen for whatever the import holds, else the import's value.
  function canonicalOf(kind, value) {
    if (!value) return value;
    var map = state.ov && state.ov.canonical[kind];
    return (map && map[value]) || value;
  }
  function eff(item, field) {
    var rowOv = state.ov && state.ov.rows[item.id];
    if (rowOv && rowOv[field] != null && rowOv[field] !== '') return rowOv[field];
    var v = item[field] || '';
    if (TAG_FIELDS.indexOf(field) >= 0) return canonicalOf('category', v);
    if (field === 'karta') return canonicalOf('author', v);
    if (field === 'grantha') return canonicalOf('title', v);
    return v;
  }
  function effParent(item) {
    var p = state.ov && state.ov.parents[item.id];
    if (p !== undefined) return p || null;
    return item.parentId;
  }
  function labelsOf(item) {
    var rowOv = state.ov && state.ov.rows[item.id];
    return (rowOv && rowOv.labels) || [];
  }
  function reviewOf(id) { return (state.ov && state.ov.review[id]) || null; }

  // Romanised form for the IAST view and for roman sorting. Comes from the
  // master entry, which carries one IAST per canonical spelling, so the
  // page never needs a transliteration library at runtime.
  function iastOf(item, field) {
    var v = eff(item, field);
    if (!v) return '';
    var master = null;
    if (field === 'grantha') master = state.titleById[item.titleId];
    else if (field === 'karta') master = state.authById[item.kartaId];
    else if (TAG_FIELDS.indexOf(field) >= 0) master = state.catById[item[field + 'Id']];
    return (master && master.iast) || v;
  }
  function show(item, field) { return state.script === 'iast' ? iastOf(item, field) : eff(item, field); }
  function showTerm(master) { return state.script === 'iast' ? (master.iast || master.canonical) : master.canonical; }

  /* ---------------- data load ---------------- */
  function loadData() {
    return fetch(DATA_URL).then(function (r) { return r.json(); }).then(function (d) {
      state.items = d.items || [];
      state.byId = {};
      state.items.forEach(function (it) { state.byId[it.id] = it; });
      state.masters = d.masters || { categories: [], authors: [], titles: [] };
      state.masters.categories.forEach(function (c) { state.catById[c.id] = c; });
      state.masters.authors.forEach(function (a) { state.authById[a.id] = a; });
      state.masters.titles.forEach(function (t) { state.titleById[t.id] = t; });
      state.suggestions = d.suggestions || { parentLinks: [] };
      state.crossLinks = d.crossLinks || {};
      state.duplicates = d.duplicates || {};
      state.dropped = d.droppedDuplicates || [];
      $("#dvc-total").textContent = state.items.length.toLocaleString();
    });
  }

  // The committed overrides file, with any local draft laid over it.
  function loadOverrides() {
    return fetch(OVERRIDES_URL, { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .catch(function () { return null; })
      .then(function (committed) {
        var base = committed || emptyOverrides();
        ['canonical', 'parents', 'rows', 'review', 'links'].forEach(function (k) {
          if (!base[k]) base[k] = (k === 'canonical') ? { category: {}, author: {}, title: {} } : {};
        });
        // Predates extraTerms: a file synced before curators could add a term
        // of their own has no such key.
        if (!base.extraTerms) base.extraTerms = { category: [], author: [], title: [] };
        var draft = loadDraft();
        if (draft) { state.ov = draft; state.dirty = true; }
        else { state.ov = base; state.dirty = false; }
      });
  }

  /* ---------------- tree structure ---------------- */
  function rebuildTree() {
    state.children = {};
    state.roots = [];
    state.items.forEach(function (it) {
      if (reviewOf(it.id) === 'delete') return;
      var p = effParent(it);
      if (p && state.byId[p] && reviewOf(p) !== 'delete') {
        (state.children[p] = state.children[p] || []).push(it.id);
      } else {
        state.roots.push(it.id);
      }
    });
  }

  /* ---------------- filter + sort ---------------- */
  function sortKey(id) {
    var it = state.byId[id];
    switch (state.sort) {
      case 'title': return eff(it, 'grantha');
      case 'titleRoman': return iastOf(it, 'grantha').toLowerCase();
      case 'author': return eff(it, 'karta');
      case 'authorRoman': return iastOf(it, 'karta').toLowerCase();
      default: return null;
    }
  }
  // The order the tradition reads a grantha in, applied among siblings: the
  // mula or bhashya, then its tikas, then the tippanis on those, then the
  // vyakhyas, and independent works after all of it. The lead, 9 Sep 2026:
  // "Bhashya and then under it the child would be Tika... Within each Tika,
  // their corresponding tippanis. Apart from Tikas, there could be Vyakhyas...
  // And then comes anything related to Bhashya as Swatantra Grantha."
  // Sheet order and A→Z both break ties inside a rank, never across them.
  var CAT_ORDER = ['मूलम्', 'मूल', 'सर्वमूलम्', 'S.M.T', 'भाष्यम्', 'भाष्यम', 'टीका', 'टिप्पणी',
                   'व्याख्यानम्', 'खण्डार्थः', 'तात्पर्यम्', 'प्रकरणम्', 'स्वतन्त्रग्रन्थः'];
  var CAT_RANK = {};
  CAT_ORDER.forEach(function (v, i) { CAT_RANK[v] = i; });
  function catRank(id) {
    var it = state.byId[id];
    var v = eff(it, 'vishayaVibhaga') || eff(it, 'vibhaga') || '';
    var r = CAT_RANK[v];
    // Anything the sheet tags with a term not in the reading order sorts after
    // the ones that are, rather than being silently treated as a mula.
    return r === undefined ? CAT_ORDER.length : r;
  }

  // Tree only. A flat table sorted "A→Z by title" must actually be A→Z, so
  // the reading order groups siblings in the tree and nowhere else.
  function sortSiblings(ids) {
    var base = sortIds(ids);
    if (base.length < 2) return base;
    return base.sort(function (a, b) { return catRank(a) - catRank(b); });
  }

  function sortIds(ids) {
    if (state.sort === 'row') return ids.slice().sort(function (a, b) { return state.byId[a].row - state.byId[b].row; });
    var roman = state.sort.indexOf('Roman') > 0;
    return ids.slice().sort(function (a, b) {
      var ka = sortKey(a) || '', kb = sortKey(b) || '';
      // An empty title/author would otherwise head an A→Z list; the handful
      // of rows the sheet left unnamed belong at the end, not the top.
      if (!ka !== !kb) return ka ? -1 : 1;
      if (ka === kb) return state.byId[a].row - state.byId[b].row;
      // 'sa' collation orders Devanagari properly; roman keys are plain ASCII.
      return roman ? (ka < kb ? -1 : 1) : ka.localeCompare(kb, 'sa');
    });
  }

  /* ---------------- first-letter index ---------------- */
  // Which field the letter bar indexes: whatever the sort is ordering by, so
  // the bar and the list always agree about what "alphabetical" means here.
  function alphaField() { return state.sort.indexOf('author') === 0 ? 'karta' : 'grantha'; }

  // The Devanagari initial is the first codepoint that is a letter -- a word
  // opening on a conjunct (स्+व) still files under its first consonant, and
  // stray danda/space/digits at the head of a cell are skipped.
  function devaInitial(s) {
    for (var i = 0; i < s.length; i++) {
      var ch = s[i];
      if (/[ऄ-हक़-ॡ]/.test(ch)) return ch;
    }
    return '';
  }
  // NFD splits ā/ī/ṭ/ś/ṇ/ṛ into a base letter plus a combining mark, so
  // dropping the marks leaves the plain English letter a reader would look
  // under -- Ṭīkā files under T, not in some separate diacritic section.
  function romanInitial(s) {
    var folded = s.normalize ? s.normalize('NFD').replace(/[̀-ͯ]/g, '') : s;
    var m = folded.match(/[A-Za-z]/);
    return m ? m[0].toUpperCase() : '';
  }
  function initialOf(it, script) {
    var f = alphaField();
    return script === 'roman' ? romanInitial(iastOf(it, f)) : devaInitial(eff(it, f));
  }

  function matches(it) {
    if (reviewOf(it.id) === 'delete') return false;
    if (state.alpha && initialOf(it, state.alpha.script) !== state.alpha.letter) return false;
    if (state.personFilter && !state.personFilter.authorIds.has(it.kartaId)) return false;
    // The chips HIDE kinds; they do not select one. The lead, 9 Sep 2026:
    // "All relevant ones must be populated. If I do not want to see a
    // particular kind of notes, I will go to Vibhaga section and unselect the
    // tippani or vyakhya." Selecting-to-show meant the tree was empty of
    // tippanis until you asked for them by name -- backwards for a reader who
    // wants the whole grantha and only occasionally less of it.
    for (var i = 0; i < TAG_FIELDS.length; i++) {
      var hidden = state.tagFilters[TAG_FIELDS[i]];
      if (hidden.size && hidden.has(eff(it, TAG_FIELDS[i]))) return false;
    }
    if (state.labelFilter && labelsOf(it).indexOf(state.labelFilter) < 0) return false;
    if (state.onlyFlag) {
      if (state.onlyFlag === 'missingTags' && (eff(it, 'vibhaga') || eff(it, 'vishayaVibhaga') || eff(it, 'prasthana'))) return false;
      if (state.onlyFlag === 'missingKarta' && eff(it, 'karta')) return false;
      if (state.onlyFlag === 'noParent' && effParent(it)) return false;
      if (state.onlyFlag === 'unresolvedLink' && !it.unresolvedLink) return false;
      if (state.onlyFlag === 'edited' && !(state.ov.rows[it.id] || state.ov.parents[it.id])) return false;
    }
    var q = state.q.trim().toLowerCase();
    if (q) {
      var hay = (eff(it, 'grantha') + ' ' + eff(it, 'karta') + ' ' + it.breadcrumb + ' ' +
                 iastOf(it, 'grantha') + ' ' + iastOf(it, 'karta')).toLowerCase();
      if (hay.indexOf(q) < 0) return false;
    }
    return true;
  }

  function recompute() {
    state.view_ids = sortIds(state.items.filter(matches).map(function (it) { return it.id; }));
    state.shown = 0;
    $("#dvc-count").textContent = state.view_ids.length.toLocaleString() + " / " + state.items.length.toLocaleString();
  }

  /* ---------------- TREE VIEW ---------------- */
  // When a search or filter is on, the tree shows every match plus the
  // ancestors needed to reach it, fully expanded -- otherwise a match three
  // levels down would simply not be on screen.
  function visibleSet() {
    // A NARROWING filter (search, a flag, a label, a person) hides most of the
    // tree, so its few matches are force-expanded into view -- otherwise a hit
    // three levels down is simply not on screen. Hiding a kind with a chip is
    // the opposite: nearly everything still matches, and force-expanding all
    // of it would blow the tree open every time a curator switched off
    // तिप्पणी. There, drop the hidden nodes and leave expansion to the reader.
    var narrowing = state.q.trim() || state.onlyFlag || state.labelFilter || state.personFilter || state.alpha;
    var hiding = TAG_FIELDS.some(function (f) { return state.tagFilters[f].size; });
    if (!narrowing && !hiding) return null;
    var keep = {};
    state.items.forEach(function (it) {
      if (!matches(it)) return;
      keep[it.id] = true;
      var p = effParent(it), guard = 0;
      while (p && state.byId[p] && guard++ < 50) {
        if (!keep[p]) keep[p] = narrowing ? 'ancestor' : 'kept';
        p = effParent(state.byId[p]);
      }
    });
    return keep;
  }

  function nodeHTML(id, depth, keep) {
    var it = state.byId[id];
    var kids = (state.children[id] || []).filter(function (c) { return !keep || keep[c]; });
    var open = state.expanded[id] || (keep && keep[id] === 'ancestor');
    var caret = kids.length
      ? '<button class="dvc-caret" data-toggle="' + id + '" aria-expanded="' + (open ? 'true' : 'false') + '">' + (open ? '▾' : '▸') + '</button>'
      : '<span class="dvc-caret dvc-caret-leaf">·</span>';
    var cat = eff(it, 'vishayaVibhaga') || eff(it, 'vibhaga');
    var catM = state.catById[it.vishayaVibhagaId] || state.catById[it.vibhagaId];
    var flags = '';
    if (it.exactDuplicateGroup) flags += '<span class="dvc-badge dvc-badge-dup" title="Exact duplicate">≡</span>';
    if (!effParent(it) && hasSuggestion(id)) flags += '<span class="dvc-badge dvc-badge-sugg" title="A parent is suggested for this row — see the Links tab">?</span>';
    if (it.unresolvedLink) flags += '<span class="dvc-badge dvc-badge-warn" title="Link names a title found nowhere in the sheet">⚠</span>';
    var lbl = labelsOf(it).map(function (l) { return '<span class="dvc-label">' + esc(l) + '</span>'; }).join('');
    var edited = (state.ov.rows[id] || state.ov.parents[id]) ? ' dvc-edited' : '';

    var html = '<div class="dvc-node' + edited + '" data-id="' + id + '" style="padding-left:' + (depth * 20) + 'px">' +
      caret +
      '<span class="dvc-node-title" data-open="' + id + '">' + esc(show(it, 'grantha') || '(अनाम)') + '</span>' +
      (cat ? '<span class="dvc-chip-cat">' + esc(catM && state.script === 'iast' ? catM.iast : cat) + '</span>' : '') +
      (eff(it, 'karta') ? '<span class="dvc-node-karta">' + esc(show(it, 'karta')) + '</span>' : '') +
      lbl + flags +
      (kids.length ? '<span class="dvc-kidcount">' + kids.length + '</span>' : '') +
      '<span class="dvc-node-row">#' + it.row + '</span>' +
      '</div>';
    if (open && kids.length) {
      html += sortSiblings(kids).map(function (c) { return nodeHTML(c, depth + 1, keep); }).join('');
    }
    return html;
  }

  var suggById = null;
  function hasSuggestion(id) {
    if (!suggById) {
      suggById = {};
      (state.suggestions.parentLinks || []).forEach(function (s) { suggById[s.id] = s; });
    }
    return suggById[id];
  }

  function renderTree(reset) {
    var box = $("#dvc-tree");
    var keep = visibleSet();
    var roots = state.roots.filter(function (r) { return !keep || keep[r]; });
    roots = sortSiblings(roots);
    if (reset) { box.innerHTML = ''; state.shown = 0; }
    if (!roots.length) { box.innerHTML = '<div class="dvc-empty-msg">No entries match.</div>'; $("#dvc-more").style.display = 'none'; return; }
    var end = Math.min(state.shown + CHUNK, roots.length);
    var html = '';
    for (var i = state.shown; i < end; i++) html += nodeHTML(roots[i], 0, keep);
    box.insertAdjacentHTML('beforeend', html);
    state.shown = end;
    $("#dvc-count").textContent = roots.length.toLocaleString() + " roots / " + state.items.length.toLocaleString() + " entries";
    $("#dvc-more").style.display = state.shown < roots.length ? 'block' : 'none';
    $("#dvc-more").textContent = "अधिकं · show more ▾ (" + (roots.length - state.shown).toLocaleString() + ")";
  }

  /* ---------------- TABLE VIEW ---------------- */
  function rowHTML(id) {
    var it = state.byId[id];
    var edited = (state.ov.rows[id] || state.ov.parents[id]) ? ' class="dvc-edited"' : '';
    return '<tr' + edited + ' data-id="' + id + '">' +
      '<td class="dvc-num">' + it.row + '</td>' +
      '<td class="dvc-grantha" title="' + esc(it.breadcrumb) + '"><span data-open="' + id + '">' + esc(show(it, 'grantha') || '(अनाम)') + '</span></td>' +
      '<td>' + esc(show(it, 'karta')) + '</td>' +
      TAG_FIELDS.map(function (f) { return '<td>' + esc(show(it, f) || '—') + '</td>'; }).join('') +
      '<td class="dvc-muted">' + esc(eff(it, 'availability')) + '</td>' +
      '<td class="dvc-muted">' + esc(eff(it, 'status')) + '</td>' +
      '</tr>';
  }
  function renderTable(reset) {
    var box = $("#dvc-tbody");
    if (reset) { box.innerHTML = ''; state.shown = 0; }
    if (!state.view_ids.length) { box.innerHTML = '<tr><td colspan="8" class="dvc-empty-msg">No entries match.</td></tr>'; $("#dvc-more").style.display = 'none'; return; }
    var end = Math.min(state.shown + CHUNK, state.view_ids.length);
    var html = '';
    for (var i = state.shown; i < end; i++) html += rowHTML(state.view_ids[i]);
    box.insertAdjacentHTML('beforeend', html);
    state.shown = end;
    $("#dvc-more").style.display = state.shown < state.view_ids.length ? 'block' : 'none';
    $("#dvc-more").textContent = "अधिकं · show more ▾ (" + (state.view_ids.length - state.shown).toLocaleString() + ")";
  }

  /* ---------------- GRID (spreadsheet) VIEW ---------------- */
  function gridCell(it, field, r, c) {
    var val = field === 'labels' ? labelsOf(it).join(', ')
            : field === 'note' ? ((state.ov.rows[it.id] || {}).note || '')
            : eff(it, field);
    var overridden = state.ov.rows[it.id] && state.ov.rows[it.id][field] != null;
    return '<td class="dvc-gcell' + (overridden ? ' dvc-gcell-edited' : '') + '" data-id="' + it.id +
      '" data-field="' + field + '" data-r="' + r + '" data-c="' + c + '" tabindex="-1">' + esc(val) + '</td>';
  }
  function renderGrid(reset) {
    var box = $("#dvc-gbody");
    if (reset) { box.innerHTML = ''; state.shown = 0; }
    if (!state.view_ids.length) { box.innerHTML = '<tr><td colspan="11" class="dvc-empty-msg">No entries match.</td></tr>'; $("#dvc-more").style.display = 'none'; return; }
    var end = Math.min(state.shown + CHUNK, state.view_ids.length);
    var html = '';
    for (var i = state.shown; i < end; i++) {
      var it = state.byId[state.view_ids[i]];
      html += '<tr data-id="' + it.id + '"><td class="dvc-num">' + it.row + '</td>' +
        EDITABLE.map(function (f, ci) { return gridCell(it, f, i, ci); }).join('') +
        '<td class="dvc-muted">' + esc(parentLabel(it)) + '</td></tr>';
    }
    box.insertAdjacentHTML('beforeend', html);
    state.shown = end;
    $("#dvc-more").style.display = state.shown < state.view_ids.length ? 'block' : 'none';
    $("#dvc-more").textContent = "अधिकं · show more ▾ (" + (state.view_ids.length - state.shown).toLocaleString() + ")";
  }
  function parentLabel(it) {
    var p = effParent(it);
    return p && state.byId[p] ? ('#' + state.byId[p].row + ' ' + eff(state.byId[p], 'grantha')) : '';
  }

  function datalistFor(field) {
    if (TAG_FIELDS.indexOf(field) >= 0) return 'dvc-dl-category';
    if (field === 'karta') return 'dvc-dl-author';
    return '';
  }

  function beginEdit(td) {
    if (td.querySelector('input')) return;
    var id = td.dataset.id, field = td.dataset.field;
    var cur = td.textContent;
    var list = datalistFor(field);
    td.innerHTML = '<input class="dvc-ginput" value="' + esc(cur) + '"' + (list ? ' list="' + list + '"' : '') + '>';
    var input = td.querySelector('input');
    input.focus(); input.select();
    var done = false;
    function commit(save) {
      if (done) return; done = true;
      var v = input.value.trim();
      if (save && v !== cur) setRowField(id, field, v);
      td.innerHTML = esc(save ? v : cur);
      td.classList.toggle('dvc-gcell-edited', !!(state.ov.rows[id] && state.ov.rows[id][field] != null));
    }
    input.addEventListener('blur', function () { commit(true); });
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') { commit(true); focusCell(+td.dataset.r + 1, +td.dataset.c); e.preventDefault(); }
      else if (e.key === 'Escape') { commit(false); td.focus(); }
      else if (e.key === 'Tab') { commit(true); focusCell(+td.dataset.r, +td.dataset.c + (e.shiftKey ? -1 : 1)); e.preventDefault(); }
    });
  }
  function focusCell(r, c) {
    var td = $('td.dvc-gcell[data-r="' + r + '"][data-c="' + c + '"]');
    if (td) { td.focus(); td.scrollIntoView({ block: 'nearest' }); }
  }

  function setRowField(id, field, value) {
    var rows = state.ov.rows;
    if (!rows[id]) rows[id] = {};
    if (field === 'labels') {
      var arr = value.split(',').map(function (s) { return s.trim(); }).filter(Boolean);
      if (arr.length) rows[id].labels = arr; else delete rows[id].labels;
    } else if (value === '') {
      delete rows[id][field];
    } else {
      rows[id][field] = value;
    }
    if (!Object.keys(rows[id]).length) delete rows[id];
    saveDraft();
  }

  /* ---------------- views + tabs ---------------- */
  function renderCurrentView(reset) {
    $("#dvc-tree").style.display = state.view === 'tree' ? '' : 'none';
    $("#dvc-tablewrap").style.display = state.view === 'table' ? '' : 'none';
    $("#dvc-gridwrap").style.display = state.view === 'grid' ? '' : 'none';
    if (state.view === 'tree') renderTree(reset);
    else if (state.view === 'table') renderTable(reset);
    else renderGrid(reset);
  }
  function rerender() { rebuildTree(); recompute(); renderCurrentView(true); }

  function showTab(tab) {
    state.tab = tab;
    ['catalogue', 'links', 'masters', 'duplicates', 'crosslinks', 'reports'].forEach(function (t) {
      var el = $("#dvc-panel-" + t);
      if (el) el.style.display = (t === tab) ? '' : 'none';
      var btn = $('.dvc-tab[data-tab="' + t + '"]');
      if (btn) btn.classList.toggle('on', t === tab);
    });
    if (tab === 'links') renderLinks();
    if (tab === 'masters') renderMasters();
    if (tab === 'duplicates') renderDuplicates();
    if (tab === 'crosslinks') renderCrossLinks();
    if (tab === 'reports') renderReports();
  }

  /* ---------------- LINKS tab ---------------- */
  function renderLinks() {
    var sugg = (state.suggestions.parentLinks || []).filter(function (s) {
      var it = state.byId[s.id];
      return it && !effParent(it) && reviewOf(s.id) !== 'delete';
    });
    var accepted = Object.keys(state.ov.parents).length;
    var orphans = state.items.filter(function (it) { return !effParent(it) && !hasSuggestion(it.id) && reviewOf(it.id) !== 'delete'; });
    var bad = state.items.filter(function (it) { return it.unresolvedLink; });

    var html = '<h3>सुझाव-सम्बन्धाः · Suggested parents <span class="dvc-muted">(' + sugg.length + ' open, ' + accepted + ' accepted)</span></h3>' +
      '<p class="dvc-hint">The sheet leaves the Link column empty on ' + orphans.length.toLocaleString() +
      '+ rows, yet many are plainly commentaries — a title that reads “&lt;a known work&gt; + टीका/टिप्पणी/व्याख्या/भाष्यम्/खण्डार्थः”. ' +
      'Each suggestion below is that reading, never applied on its own. Accepting one re-parents the row everywhere, including the tree.</p>';

    html += sugg.slice(0, 400).map(function (s) {
      var it = state.byId[s.id];
      return '<div class="dvc-suggrow">' +
        '<div class="dvc-suggmain"><b>#' + it.row + ' ' + esc(eff(it, 'grantha')) + '</b>' +
        '<span class="dvc-muted"> · ' + esc(eff(it, 'karta')) + '</span>' +
        '<div class="dvc-muted">suggested parent: ' + s.candidates.map(function (c) {
          var p = state.byId[c];
          return p ? '<button class="dvc-btn dvc-btn-sm" data-accept-parent="' + s.id + '" data-parent="' + c + '">✓ #' + p.row + ' ' + esc(eff(p, 'grantha')) + '</button>' : '';
        }).join(' ') + ' <span class="dvc-conf">(' + s.confidence + ', on “' + esc(s.suffix) + '”)</span></div></div>' +
        '<button class="dvc-btn dvc-btn-sm" data-reject-parent="' + s.id + '">✕ not a commentary</button>' +
        '</div>';
    }).join('') || '<p class="dvc-muted">none left to review</p>';
    if (sugg.length > 400) html += '<p class="dvc-muted">' + (sugg.length - 400) + ' more — accept some and they clear.</p>';

    html += '<h3>अनिर्दिष्ट-लिङ्काः · Link names a title that does not exist <span class="dvc-muted">(' + bad.length + ')</span></h3>';
    html += bad.length ? '<table class="dvc-minitable"><tbody>' + bad.map(function (it) {
      return '<tr><td>#' + it.row + '</td><td>' + esc(eff(it, 'grantha')) + '</td><td class="dvc-muted">Link: ' + esc(it.linkRaw) + '</td></tr>';
    }).join('') + '</tbody></table>' : '<p class="dvc-muted">none</p>';

    html += '<h3>अपितृकाः · Roots with no suggestion <span class="dvc-muted">(' + orphans.length.toLocaleString() + ')</span></h3>' +
      '<p class="dvc-hint">Standalone works, or commentaries whose base title is spelled differently. Set a parent for any of them from the grid view’s parent column, or fix the spelling in the Masters tab first.</p>';
    $("#dvc-links-body").innerHTML = html;
  }

  function acceptParent(childId, parentId) {
    state.ov.parents[childId] = parentId;
    saveDraft(); rerender(); renderLinks();
  }
  function rejectParent(childId) {
    // Recorded as an explicit "no parent" so the suggestion stops coming back.
    state.ov.parents[childId] = "";
    saveDraft(); rerender(); renderLinks();
  }

  /* ---------------- MASTERS tab ---------------- */
  function masterKinds() {
    return [
      { kind: 'category', label: 'वर्गाः · Categories', list: state.masters.categories,
        hint: 'One shared vocabulary for विभागः, विषयविभागः and प्रस्थानम् — the sheet uses the same terms across all three.' },
      { kind: 'author', label: 'कर्तारः · Authors', list: state.masters.authors,
        hint: 'Honorific and ending variants (श्रीजयतीर्थः / जयतीर्थः / जयतीर्थ) folded onto one person.' },
      { kind: 'title', label: 'ग्रन्थनामानि · Work titles', list: state.masters.titles,
        hint: 'Spelling variants of the same work — the ones to settle before parent links can resolve.' }
    ];
  }
  function renderMasters() {
    var onlyVariants = $("#dvc-masters-onlyvar") && $("#dvc-masters-onlyvar").checked;
    var q = ($("#dvc-masters-q") && $("#dvc-masters-q").value || '').trim().toLowerCase();
    var html = masterKinds().map(function (mk) {
      var list = mk.list.filter(function (m) {
        if (onlyVariants && m.variants.length < 2 && !isEdited(mk.kind, m)) return false;
        if (q && (m.canonical + ' ' + (m.iast || '') + ' ' + variantChosen(mk.kind, m)).toLowerCase().indexOf(q) < 0) return false;
        return true;
      });
      var withVar = mk.list.filter(function (m) { return m.variants.length > 1; }).length;
      var added = addedTerms(mk.kind);
      return '<section class="dvc-masterblock"><h3>' + mk.label +
        ' <span class="dvc-muted">(' + (mk.list.length + added.length) + ' terms, ' + withVar + ' with more than one spelling)</span></h3>' +
        '<p class="dvc-hint">' + mk.hint + '</p>' +
        '<div class="dvc-addform"><input type="text" class="dvc-newterm" data-kind="' + mk.kind +
          '" placeholder="add a term this sheet has not used yet…">' +
          '<button class="dvc-btn" data-addterm="' + mk.kind + '">➕ Add</button></div>' +
        (added.length ? '<div class="dvc-masterchips">' + added.map(function (t) {
          return '<span class="dvc-mchip">' + esc(t) + '<button class="dvc-mchip-x" data-delterm="' + mk.kind + '" data-val="' + esc(t) + '">×</button></span>';
        }).join('') + '</div>' : '') +
        '<table class="dvc-minitable"><thead><tr><th>Canonical</th><th>IAST</th><th>Used</th><th>Spellings found · click one to make it canonical</th><th></th></tr></thead><tbody>' +
        list.slice(0, 300).map(function (m) { return masterRowHTML(mk.kind, m); }).join('') +
        '</tbody></table>' +
        (list.length > 300 ? '<p class="dvc-muted">' + (list.length - 300) + ' more — search above to narrow.</p>' : '') +
        '</section>';
    }).join('');
    $("#dvc-masters-body").innerHTML = html;
  }

  function masterRowHTML(kind, m) {
    var chosen = variantChosen(kind, m);
    var edited = isEdited(kind, m);
    return '<tr' + (edited ? ' class="dvc-edited"' : '') + ' data-mkind="' + kind + '" data-mkey="' + esc(m.key) + '">' +
      '<td><b class="dvc-canon" data-editcanon="1" title="Click to rename this term everywhere">' + esc(chosen) + '</b></td>' +
      '<td class="dvc-muted">' + esc(iastFor(kind, chosen, m)) + '</td>' +
      '<td class="dvc-rnum">' + m.count + '</td>' +
      '<td>' + m.variants.map(function (v) {
        var isChosen = v.value === chosen;
        return '<button class="dvc-vchip' + (isChosen ? ' on' : '') + '" data-canon-kind="' + kind +
          '" data-canon-key="' + esc(m.key) + '" data-canon-val="' + esc(v.value) + '" title="' +
          (isChosen ? 'The spelling shown everywhere' : 'Use this spelling everywhere instead') + '">' +
          esc(v.value) + ' <span class="dvc-muted">×' + v.count + '</span></button>';
      }).join('') + '</td>' +
      '<td><button class="dvc-btn dvc-btn-sm" data-mergemaster="1">⇢ merge</button>' +
      (edited ? ' <button class="dvc-btn dvc-btn-sm" data-resetmaster="1" title="Drop my change to this term">undo</button>' : '') +
      '</td></tr>';
  }

  // What this term currently displays as: a curator's choice if they made
  // one (any of its spellings mapped in the overrides points at it), else
  // the commonest spelling the sheet used.
  function variantChosen(kind, m) {
    var map = state.ov.canonical[kind] || {};
    for (var i = 0; i < m.variants.length; i++) {
      var mapped = map[m.variants[i].value];
      if (mapped) return mapped;
    }
    return m.canonical;
  }
  // IAST is transliterated at build time, so a spelling the sheet never used
  // has none. After a merge the chosen value usually IS another term's
  // spelling, so borrow that term's reading; after a rename to something new,
  // say nothing rather than leave the old term's reading beside a new name.
  var iastIndex = {};
  function iastFor(kind, chosen, m) {
    if (chosen === m.canonical) return m.iast || '';
    if (!iastIndex[kind]) {
      var ix = iastIndex[kind] = {};
      masterList(kind).forEach(function (x) {
        if (!x.iast) return;
        if (!(x.canonical in ix)) ix[x.canonical] = x.iast;
        x.variants.forEach(function (v) { if (!(v.value in ix)) ix[v.value] = x.iast; });
      });
    }
    return iastIndex[kind][chosen] || '';
  }
  function masterList(kind) {
    return kind === 'category' ? state.masters.categories
         : kind === 'author' ? state.masters.authors : state.masters.titles;
  }
  function masterByKey(kind, key) {
    return masterList(kind).filter(function (x) { return x.key === key; })[0];
  }
  function isEdited(kind, m) {
    var map = state.ov.canonical[kind] || {};
    return m.variants.some(function (v) { return map[v.value]; });
  }
  function addedTerms(kind) {
    return ((state.ov.extraTerms || {})[kind]) || [];
  }
  // Every value this kind can currently be set to — the observed canonicals
  // plus anything a curator has added. Feeds the merge target list and the
  // grid's autocomplete.
  function allTermsFor(kind) {
    var seen = {}, out = [];
    masterList(kind).forEach(function (m) {
      var v = variantChosen(kind, m);
      if (v && !seen[v]) { seen[v] = 1; out.push(v); }
    });
    addedTerms(kind).forEach(function (v) { if (!seen[v]) { seen[v] = 1; out.push(v); } });
    return out;
  }

  // Point EVERY spelling of this term at `value`, so one action fixes every
  // row that used any of them. `value` need not be one of the observed
  // spellings — that is what makes this a rename rather than just a pick.
  function setCanonical(kind, key, value) {
    var m = masterByKey(kind, key);
    if (!m || !value) return;
    var map = state.ov.canonical[kind] = state.ov.canonical[kind] || {};
    m.variants.forEach(function (v) {
      if (v.value === value) delete map[v.value];
      else map[v.value] = value;
    });
    saveDraft(); rerender(); renderMasters(); refreshDatalists();
  }
  function resetCanonical(kind, key) {
    var m = masterByKey(kind, key);
    if (!m) return;
    var map = state.ov.canonical[kind] || {};
    m.variants.forEach(function (v) { delete map[v.value]; });
    saveDraft(); rerender(); renderMasters(); refreshDatalists();
  }
  // Merging is the same operation aimed at another term's canonical: two
  // master entries that never folded together automatically (स्तोत्रम् and
  // स्तोत्रग्रन्थः) become one because both now display the same value.
  function mergeMaster(kind, key, targetValue) {
    setCanonical(kind, key, targetValue);
  }

  function beginCanonEdit(td, kind, key, currentValue, opts) {
    if (td.querySelector('input')) return;
    var listId = 'dvc-dl-master-' + kind;
    var dl = $('#' + listId);
    if (!dl) {
      dl = document.createElement('datalist');
      dl.id = listId;
      document.body.appendChild(dl);
    }
    dl.innerHTML = allTermsFor(kind).slice(0, 1200).map(function (v) { return '<option value="' + esc(v) + '">'; }).join('');
    td.innerHTML = '<input class="dvc-ginput" list="' + listId + '" value="' + esc(opts && opts.blank ? '' : currentValue) +
      '" placeholder="' + esc(opts && opts.placeholder || '') + '">';
    var input = td.querySelector('input');
    input.focus(); input.select();
    var done = false;
    function finish(save) {
      if (done) return; done = true;
      var v = input.value.trim();
      if (save && v && v !== currentValue) setCanonical(kind, key, v);
      else renderMasters();
    }
    input.addEventListener('blur', function () { finish(true); });
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') finish(true);
      else if (e.key === 'Escape') finish(false);
    });
  }

  /* ---------------- DUPLICATES tab ---------------- */
  // The columns a group's rows actually disagree on. The lead's rule is "a
  // duplicate is a row whose every column repeats", so a group shown here has
  // to say where it falls short of that -- otherwise a reader can only take
  // the heading's word for it that these are not exact repeats.
  var DUP_COLS = [
    { f: 'grantha', label: 'title' }, { f: 'karta', label: 'author' },
    { f: 'linkRaw', label: 'link' }, { f: 'vibhaga', label: 'विभागः' },
    { f: 'vishayaVibhaga', label: 'विषयविभागः' }, { f: 'prasthana', label: 'प्रस्थानम्' },
    { f: 'status', label: 'status' }, { f: 'mention', label: 'mention' },
    { f: 'sourceLibrary', label: 'source' }, { f: 'availability', label: 'availability' }
  ];
  function differingCols(ids) {
    var rows = ids.map(function (id) { return state.byId[id]; }).filter(Boolean);
    if (rows.length < 2) return [];
    var out = [];
    DUP_COLS.forEach(function (c) {
      var first = eff(rows[0], c.f) || '';
      for (var i = 1; i < rows.length; i++) {
        if ((eff(rows[i], c.f) || '') !== first) { out.push(c.label); return; }
      }
    });
    var parents = rows.map(function (r) { return effParent(r) || ''; });
    if (parents.some(function (p) { return p !== parents[0]; })) out.push('parent');
    return out;
  }

  function dupRowHTML(id) {
    var it = state.byId[id];
    if (!it) return '';
    var st = reviewOf(id);
    return '<div class="dvc-duprow' + (st === 'delete' ? ' dvc-marked-delete' : '') + '" data-duprow="' + id + '">' +
      '<div class="dvc-dupinfo"><b>#' + it.row + '</b> ' + esc(it.breadcrumb) +
      '<span class="dvc-muted"> · ' + esc(eff(it, 'karta')) + '</span>' +
      (st ? ' <span class="dvc-statuspill">' + esc(st) + '</span>' : '') + '</div>' +
      '<div class="dvc-dupacts">' +
      '<button class="dvc-btn dvc-btn-sm" data-review="retain" data-id="' + id + '">keep</button>' +
      '<button class="dvc-btn dvc-btn-sm" data-review="delete" data-id="' + id + '">drop</button>' +
      (st ? '<button class="dvc-btn dvc-btn-sm" data-review="clear" data-id="' + id + '">undo</button>' : '') +
      '</div></div>';
  }

  function dupGroupHTML(g, showName) {
    var diff = differingCols(g.ids);
    return '<div class="dvc-dupgroup">' + (showName && g.name ? '<div class="dvc-dupname">' + esc(g.name) + '</div>' : '') +
      (diff.length ? '<div class="dvc-dupdiff">differs in: ' + esc(diff.join(', ')) + '</div>'
                   : '<div class="dvc-dupdiff dvc-dupdiff-same">every column identical</div>') +
      g.ids.map(dupRowHTML).join('') + '</div>';
  }
  // The rows the importer already deleted. Without this the tab opened on
  // "Exact duplicates (0 groups)" and read as though nothing had been removed
  // -- when in fact 556 rows had been, 551 of them past row 1180. The
  // deletions are the answer to "are the duplicates gone", so show them.
  function droppedHTML() {
    var dropped = state.dropped || [];
    if (!dropped.length) return '';
    var beyond = dropped.filter(function (x) { return x.row > 1180; }).length;
    var byKept = {};
    dropped.forEach(function (x) { (byKept[x.keptRow] = byKept[x.keptRow] || []).push(x); });
    var keys = Object.keys(byKept).sort(function (a, b) { return a - b; });
    return '<h3>अपनीताः · Already deleted at import <span class="dvc-muted">(' + dropped.length + ' rows)</span></h3>' +
      '<p class="dvc-hint">Rows whose every column repeated an earlier row, removed before the catalogue was built — ' +
      beyond + ' of them past row 1180. They are gone from all ' + state.items.length.toLocaleString() +
      ' entries below; this is the record of what went.</p>' +
      '<details><summary>show all ' + dropped.length + '</summary><table class="dvc-minitable">' +
      '<thead><tr><th>kept</th><th>deleted rows</th><th>ग्रन्थनाम</th></tr></thead><tbody>' +
      keys.map(function (k) {
        var g = byKept[k];
        return '<tr><td>#' + esc(k) + '</td><td class="dvc-muted">' +
          esc(g.map(function (x) { return '#' + x.row; }).join(', ')) + '</td><td>' + esc(g[0].grantha) + '</td></tr>';
      }).join('') + '</tbody></table></details>';
  }

  function renderDuplicates() {
    var d = state.duplicates;
    var ex = d.exactRowDuplicates || [], npk = d.nameParentKartaDuplicates || [], coll = d.nameCollisions || [];
    $("#dvc-dup-body").innerHTML =
      droppedHTML() +
      '<h3>ठीक समानाः · Exact duplicates still present <span class="dvc-muted">(' + ex.length + ' groups)</span></h3>' +
      '<p class="dvc-hint">Every column identical AND the same resolved parent. Empty is the expected state — the importer ' +
      'already removes these; anything here arrived from a later edit.</p>' +
      (ex.slice(0, 120).map(function (g) { return dupGroupHTML(g); }).join('') || '<p class="dvc-muted">none</p>') +
      '<h3>नाम+मूल+कर्तृ-साम्यम् <span class="dvc-muted">(' + npk.length + ')</span></h3>' +
      '<p class="dvc-hint">Title, parent and author match but something else differs — worth a look, not auto-mergeable.</p>' +
      (npk.map(function (g) { return dupGroupHTML(g); }).join('') || '<p class="dvc-muted">none</p>') +
      '<h3>नामसाम्यम् · Same title only <span class="dvc-muted">(' + coll.length + ', informational)</span></h3>' +
      '<p class="dvc-hint">Grouped by title alone, so every group below differs in at least one other column — each says which. ' +
      'Normal for the दशप्रकरण, where one commentary title recurs once per mūla. These are <b>not</b> duplicates by the ' +
      'all-columns rule and are not deleted; the ones that were are listed at the top of this tab.</p>' +
      '<details><summary>show ' + coll.length + ' groups</summary>' +
      coll.slice(0, 150).map(function (g) { return dupGroupHTML(g, true); }).join('') + '</details>';
  }

  /* ---------------- CROSS-LINKS tab ---------------- */
  // 'data/darshana/.../jayanti_nirnaya/mula/data.json' ->
  // 'darshana › vedanta › dvaita › SarvaMula › ... › jayanti_nirnaya › mula'
  function pathCrumb(p) {
    return String(p || '')
      .replace(/^dge\/data\//, '').replace(/\/data\.json$/, '')
      .split('/').join(' › ');
  }

  // Confirm / undo for one proposed join. Every section shares it so a
  // decision is recorded the same way wherever it is made, and so none of
  // them is a dead end a curator can look at but not act on.
  function linkCell(id, value) {
    return state.ov.links[id]
      ? '<span class="dvc-statuspill">confirmed</span> ' +
        '<button class="dvc-btn dvc-btn-sm" data-unlink-id="' + esc(id) + '" title="Withdraw this confirmation">undo</button>'
      : '<button class="dvc-btn dvc-btn-sm" data-link-id="' + esc(id) + '" data-link-val="' + esc(value) + '">✓ confirm</button>';
  }

  function renderCrossLinks() {
    var cl = state.crossLinks;
    var lib = cl.library || [], para = cl.parampara || [], alias = cl.authorAliases || [], dasa = cl.dasaSahitya || [];
    var paraAuthors = para.filter(function (p) { return p.kind === 'author'; });
    var paraWorks = para.filter(function (p) { return p.kind === 'work'; });

    var html = '<p class="dvc-hint">Candidate joins between this catalogue and the rest of the project, matched on a diacritic-free romanisation of both sides (one side is Devanagari, the other bare English or Kannada). Every one is a proposal — confirm the ones that are right.</p>';

    html += '<h3>पुस्तकालये विद्यमानाः · Already digitised in the library <span class="dvc-muted">(' + lib.length + ')</span></h3>' +
      '<table class="dvc-minitable"><thead><tr><th>#</th><th>Catalogue entry</th><th>library.json</th><th></th></tr></thead><tbody>' +
      lib.slice(0, 200).map(function (m) {
        var it = state.byId[m.id]; if (!it) return '';
        return '<tr><td>' + it.row + '</td><td>' + esc(eff(it, 'grantha')) + '</td><td class="dvc-muted">' +
          m.matches.map(function (x) {
            // The bare title is useless where four library entries are all
            // called "Tika": show each one's place in the taxonomy, which is
            // the only thing that tells them apart.
            return '<div class="dvc-libmatch"><b>' + esc(x.title) + '</b>' +
              (x.populated ? '' : ' <i>(not yet digitised)</i>') +
              '<div class="dvc-libcrumb">' + esc(pathCrumb(x.path)) + '</div></div>';
          }).join('') + '</td>' +
          '<td>' + linkCell(m.id, m.matches[0].path) + '</td></tr>';
      }).join('') + '</tbody></table>';

    html += '<h3>गुरुपरम्परा · Authors matched to a paramparā node <span class="dvc-muted">(' + paraAuthors.length + ')</span></h3>' +
      '<p class="dvc-hint">Matched on the name alone, so each one is a proposal. Confirming it makes this the person of record: ' +
      'tools/sync_dvaita_crosslinks.py then treats it as authoritative over its own guesses, and the ācārya’s page lists these works.</p>' +
      '<table class="dvc-minitable"><tbody>' + paraAuthors.map(function (p) {
        return '<tr><td>' + esc(p.canonical) + '</td><td class="dvc-muted">→ ' + esc(p.nodeId) + '</td>' +
          '<td>' + linkCell(p.authorId, p.nodeId) + '</td></tr>';
      }).join('') + '</tbody></table>';

    html += '<h3>गुरुपरम्परायाः कृतयः · Works listed on a paramparā node <span class="dvc-muted">(' + paraWorks.length + ')</span></h3>' +
      '<p class="dvc-hint">Guru Paramparā records each ācārya’s works as free English text. These are the ones that also appear in this catalogue — the beginning of keeping the two in step.</p>' +
      '<table class="dvc-minitable"><tbody>' + paraWorks.slice(0, 100).map(function (p) {
        return '<tr><td>' + esc(p.canonical) + '</td><td class="dvc-muted">→ ' +
          p.matches.map(function (h) { return esc(h.node) + ': ' + esc(h.work); }).join('<br>') + '</td></tr>';
      }).join('') + '</tbody></table>';

    html += '<h3>author_aliases.json <span class="dvc-muted">(' + alias.length + ' of ' + state.masters.authors.length + ' authors)</span></h3>' +
      '<p class="dvc-hint">The project’s canonical person ids. Only ' + alias.length + ' of this catalogue’s ' +
      state.masters.authors.length + ' authors are known there yet — the rest are candidates to add, which is how that file is meant to grow.</p>' +
      '<table class="dvc-minitable"><tbody>' + alias.map(function (a) {
        return '<tr><td>' + esc(a.canonical) + '</td><td class="dvc-muted">→ ' + esc(a.personId) + '</td></tr>';
      }).join('') + '</tbody></table>';

    if (dasa.length) {
      html += '<h3>दाससाहित्यम् <span class="dvc-muted">(' + dasa.length + ')</span></h3>' +
        '<p class="dvc-hint">Weakest of the four joins, and the one to read hardest: matched on a bare given name, and नरसिंहः / राघवेन्द्रः ' +
        'are among the commonest names in the tradition. A ṭīkākāra and a Kannada composer sharing one is no evidence they are one person. ' +
        'Confirm only what you know; a confirmation adds the composer’s Kannada name as a spelling of that person.</p>' +
        '<table class="dvc-minitable"><tbody>' +
        dasa.map(function (x) {
          return '<tr><td>' + esc(x.canonical) + '</td><td class="dvc-muted">→ ' + esc(x.composer || x.slug) + '</td>' +
            '<td>' + linkCell('dasa:' + x.authorId, x.slug) + '</td></tr>';
        }).join('') + '</tbody></table>';
    }
    $("#dvc-cross-body").innerHTML = html;
  }

  /* ---------------- REPORTS tab ---------------- */
  var REPORT_FIELDS = [
    { id: 'prasthana', label: 'प्रस्थानम्' }, { id: 'vibhaga', label: 'विभागः' },
    { id: 'vishayaVibhaga', label: 'विषयविभागः' }, { id: 'karta', label: 'कर्तृ · author' },
    { id: 'availability', label: 'उपलब्धता' }, { id: 'status', label: 'स्थितिः' },
    { id: '_depth', label: 'Depth in the tree' }, { id: '_hasParent', label: 'Has a parent?' },
    { id: '_labels', label: 'Label' }
  ];
  function reportValue(it, field) {
    if (field === '_depth') return String(treeDepth(it));
    if (field === '_hasParent') return effParent(it) ? 'yes' : 'no';
    if (field === '_labels') return labelsOf(it).join(', ') || '(none)';
    return eff(it, field) || '(रिक्तम्)';
  }
  function treeDepth(it) {
    var d = 0, p = effParent(it), guard = 0;
    while (p && state.byId[p] && guard++ < 50) { d++; p = effParent(state.byId[p]); }
    return d;
  }
  function buildReport() {
    var g1 = $("#dvc-rep-g1").value, g2 = $("#dvc-rep-g2").value;
    var rows = state.view_ids.map(function (id) { return state.byId[id]; });
    var counts = {};
    rows.forEach(function (it) {
      var k1 = reportValue(it, g1);
      var k2 = g2 ? reportValue(it, g2) : null;
      var key = JSON.stringify([k1, k2]);
      counts[key] = (counts[key] || 0) + 1;
    });
    var out = Object.keys(counts).map(function (k) {
      var parts = JSON.parse(k);
      return { a: parts[0], b: parts[1] || '', n: counts[k] };
    }).sort(function (x, y) { return y.n - x.n; });
    state.lastReport = { g1: g1, g2: g2, rows: out, total: rows.length };
    var head = '<tr><th>' + esc(labelOf(g1)) + '</th>' + (g2 ? '<th>' + esc(labelOf(g2)) + '</th>' : '') + '<th class="dvc-rnum">count</th></tr>';
    $("#dvc-rep-out").innerHTML = '<p class="dvc-hint">' + out.length + ' groups over ' + rows.length.toLocaleString() +
      ' entries in the current filter.</p><table class="dvc-minitable"><thead>' + head + '</thead><tbody>' +
      out.slice(0, 400).map(function (r) {
        return '<tr><td>' + esc(r.a) + '</td>' + (g2 ? '<td>' + esc(r.b) + '</td>' : '') + '<td class="dvc-rnum">' + r.n + '</td></tr>';
      }).join('') + '</tbody></table>';
  }
  function labelOf(id) { var f = REPORT_FIELDS.filter(function (x) { return x.id === id; })[0]; return f ? f.label : id; }
  function exportReportCSV() {
    if (!state.lastReport) return;
    var r = state.lastReport;
    var lines = [[labelOf(r.g1)].concat(r.g2 ? [labelOf(r.g2)] : []).concat(['count']).join(',')];
    r.rows.forEach(function (x) { lines.push([csv(x.a)].concat(r.g2 ? [csv(x.b)] : []).concat([x.n]).join(',')); });
    download(lines.join('\r\n'), 'dvaita-report-' + r.g1 + (r.g2 ? '-by-' + r.g2 : '') + '.csv');
  }
  function renderReports() {
    var opts = function (sel, blank) {
      return (blank ? '<option value="">(none)</option>' : '') + REPORT_FIELDS.map(function (f) {
        return '<option value="' + f.id + '"' + (sel === f.id ? ' selected' : '') + '>' + esc(f.label) + '</option>';
      }).join('');
    };
    if (!$("#dvc-rep-g1")) {
      $("#dvc-reports-body").innerHTML =
        '<p class="dvc-hint">Build a report over whatever the catalogue filters are currently showing: pick one or two fields to group by. Everything here follows the filters at the top of the Catalogue tab.</p>' +
        '<div class="dvc-controls"><label>Group by <select id="dvc-rep-g1"></select></label>' +
        '<label>then by <select id="dvc-rep-g2"></select></label>' +
        '<button class="dvc-btn" id="dvc-rep-run">▶ Generate</button>' +
        '<button class="dvc-btn" id="dvc-rep-csv">⬇ Report CSV</button>' +
        '<button class="dvc-btn" id="dvc-rep-rowscsv">⬇ Rows CSV (current filter)</button></div>' +
        '<div id="dvc-rep-out"></div>';
      $("#dvc-rep-g1").innerHTML = opts('prasthana', false);
      $("#dvc-rep-g2").innerHTML = opts('', true);
      $("#dvc-rep-run").onclick = buildReport;
      $("#dvc-rep-csv").onclick = exportReportCSV;
      $("#dvc-rep-rowscsv").onclick = exportRowsCSV;
    }
    buildReport();
  }

  function csv(v) { v = v == null ? '' : String(v); return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; }
  function download(text, name) {
    var blob = new Blob(["﻿" + text], { type: 'text/csv;charset=utf-8' });
    var url = URL.createObjectURL(blob), a = document.createElement('a');
    a.href = url; a.download = name;
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(url); }, 4000);
  }
  function exportRowsCSV() {
    var cols = ['row', 'grantha', 'granthaIast', 'breadcrumb', 'karta', 'vibhaga', 'vishayaVibhaga',
                 'prasthana', 'availability', 'status', 'parent', 'labels'];
    var lines = [cols.join(',')];
    state.view_ids.forEach(function (id) {
      var it = state.byId[id];
      lines.push([it.row, csv(eff(it, 'grantha')), csv(iastOf(it, 'grantha')), csv(it.breadcrumb),
                  csv(eff(it, 'karta')), csv(eff(it, 'vibhaga')), csv(eff(it, 'vishayaVibhaga')),
                  csv(eff(it, 'prasthana')), csv(eff(it, 'availability')), csv(eff(it, 'status')),
                  csv(parentLabel(it)), csv(labelsOf(it).join(' '))].join(','));
    });
    download(lines.join('\r\n'), 'dvaita-grantha-anukramani-' + new Date().toISOString().slice(0, 10) + '.csv');
  }
  window.dvcExportCSV = exportRowsCSV; // used by the verification script

  /* ---------------- GitHub sync ---------------- */
  function ghCfg() { return window.GITHUB_REPO_CONFIG || { owner: 'Tribhuvanachar', repo: 'bhumandala', branch: 'main' }; }
  function ghToken() { try { return localStorage.getItem('github_admin_pat') || ''; } catch (e) { return ''; } }
  function b64(str) { return btoa(String.fromCharCode.apply(null, new TextEncoder().encode(str))); }
  function ghApi(path, opts) {
    var c = ghCfg();
    return fetch('https://api.github.com/repos/' + c.owner + '/' + c.repo + path,
      Object.assign({ headers: { Authorization: 'token ' + ghToken(), Accept: 'application/vnd.github+json' } }, opts || {}))
      .then(function (r) {
        if (!r.ok) return r.text().then(function (t) { throw new Error(r.status + ' ' + (t || r.statusText)); });
        return r.json();
      });
  }
  function syncToGitHub() {
    if (!ghToken()) {
      syncSay('No GitHub token saved in this browser. Add one under Admin → AI Keys & Features (it is the same token the other admin pages use), then press Sync again.', true);
      return;
    }
    var c = ghCfg();
    syncSay('Reading the committed file…');
    // Re-read first so a sync never clobbers someone else's newer edits blindly.
    ghApi('/contents/' + OVERRIDES_PATH + '?ref=' + c.branch)
      .then(function (f) { return f.sha; })
      .catch(function () { return null; })
      .then(function (sha) {
        state.ov.updatedAt = new Date().toISOString();
        var body = { message: 'Grantha Anukramani: ' + countEdits() + ' curated corrections', content: b64(JSON.stringify(state.ov, null, 1) + '\n'), branch: c.branch };
        if (sha) body.sha = sha;
        return ghApi('/contents/' + OVERRIDES_PATH, { method: 'PUT', body: JSON.stringify(body) });
      })
      .then(function (res) {
        state.committedSha = res.content && res.content.sha;
        try { localStorage.removeItem(DRAFT_KEY); } catch (e) {}
        state.dirty = false;
        updateSyncBar();
        syncSay('Synced to GitHub — ' + countEdits() + ' corrections committed to ' + ghCfg().branch + '.');
      })
      .catch(function (e) { syncSay('Sync failed: ' + (e.message || e), true); });
  }
  function syncSay(msg, bad) {
    var el = $("#dvc-syncsay");
    if (el) { el.textContent = msg; el.className = bad ? 'dvc-err' : 'dvc-ok'; }
  }
  function updateSyncBar() {
    var n = countEdits();
    $("#dvc-editcount").textContent = n ? (n + ' correction' + (n === 1 ? '' : 's')) : 'no corrections yet';
    $("#dvc-dirty").style.display = state.dirty ? '' : 'none';
    $("#dvc-sync").disabled = !state.dirty;
  }

  // Both alphabets, always both on screen: a scholar reading the Devanagari
  // wants ज, someone who knows the work as Jayatirthiya-tika wants J, and
  // neither should have to change a display setting to get an index.
  // Counts come from every entry, not the filtered view, so a letter never
  // disappears out from under a reader mid-browse; a letter with no entries
  // simply is not drawn.
  function buildAlphaBar() {
    var wrap = $("#dvc-alpha");
    if (!wrap) return;
    var fieldLabel = alphaField() === 'karta' ? 'कर्तृ · author' : 'ग्रन्थनाम · title';
    var html = '<div class="dvc-alpharow"><span class="dvc-flab">आदि-अक्षरम् · first letter of ' +
      fieldLabel + '</span>' +
      '<button type="button" class="dvc-chip' + (state.alpha ? '' : ' on') + '" data-alpha-all="1">सर्वे · all</button></div>';
    [['deva', 'देवनागरी'], ['roman', 'A→Z']].forEach(function (pair) {
      var script = pair[0];
      var counts = {};
      state.items.forEach(function (it) {
        var k = initialOf(it, script);
        if (k) counts[k] = (counts[k] || 0) + 1;
      });
      var letters = Object.keys(counts).sort(function (a, b) {
        return script === 'roman' ? (a < b ? -1 : 1) : a.localeCompare(b, 'sa');
      });
      if (!letters.length) return;
      html += '<div class="dvc-alpharow"><span class="dvc-flab">' + pair[1] + '</span>' +
        letters.map(function (l) {
          var on = state.alpha && state.alpha.script === script && state.alpha.letter === l;
          return '<button type="button" class="dvc-alphabtn' + (on ? ' on' : '') +
            '" data-alpha-script="' + script + '" data-alpha="' + esc(l) + '" title="' +
            counts[l] + ' entries">' + esc(l) + '</button>';
        }).join('') + '</div>';
    });
    wrap.innerHTML = html;
  }

  /* ---------------- filter chips ---------------- */
  function buildChips() {
    TAG_FIELDS.forEach(function (col) {
      var wrap = $("#dvc-chips-" + col);
      if (!wrap) return;
      var counts = {};
      state.items.forEach(function (it) { var v = eff(it, col); if (v) counts[v] = (counts[v] || 0) + 1; });
      // A chip reads as ON (this kind is showing) until it is clicked off, so
      // the default state of the page is every kind visible.
      wrap.innerHTML = Object.keys(counts).sort(function (a, b) { return counts[b] - counts[a]; }).map(function (v) {
        var off = state.tagFilters[col].has(v);
        return '<button type="button" class="dvc-chip' + (off ? ' dvc-chip-off' : ' on') +
          '" data-col="' + col + '" data-val="' + esc(v) + '" title="' +
          (off ? 'Hidden — click to show again' : 'Showing — click to hide these') + '">' +
          esc(v) + ' <span class="dvc-muted">' + counts[v] + '</span></button>';
      }).join('');
    });
    buildAlphaBar();
    var labels = {};
    state.items.forEach(function (it) { labelsOf(it).forEach(function (l) { labels[l] = (labels[l] || 0) + 1; }); });
    var lw = $("#dvc-chips-labels");
    if (lw) {
      var keys = Object.keys(labels);
      lw.innerHTML = keys.length ? keys.map(function (l) {
        return '<button type="button" class="dvc-chip' + (state.labelFilter === l ? ' on' : '') + '" data-label="' + esc(l) + '">' + esc(l) + ' <span class="dvc-muted">' + labels[l] + '</span></button>';
      }).join('') : '<span class="dvc-muted">no labels yet — add them in the grid view’s labels column</span>';
    }
    refreshDatalists();
  }

  // The grid's autocomplete offers exactly the master list's current terms —
  // renames, merges and added terms all reach it, which is what keeps a
  // curator from silently reintroducing a spelling they just retired.
  function refreshDatalists() {
    var dl = $("#dvc-dl-category");
    if (dl) dl.innerHTML = allTermsFor('category').map(function (v) { return '<option value="' + esc(v) + '">'; }).join('');
    var da = $("#dvc-dl-author");
    if (da) da.innerHTML = allTermsFor('author').slice(0, 1200).map(function (v) { return '<option value="' + esc(v) + '">'; }).join('');
  }

  /* ---------------- detail panel ---------------- */
  function openDetail(id) {
    var it = state.byId[id];
    if (!it) return;
    var kids = state.children[id] || [];
    var p = effParent(it);
    var libMatch = (state.crossLinks.library || []).filter(function (m) { return m.id === id; })[0];
    $("#dvc-detail").innerHTML =
      '<button class="dvc-btn dvc-btn-sm" id="dvc-detail-close" style="float:right">✕</button>' +
      '<h3>' + esc(eff(it, 'grantha') || '(अनाम)') + '</h3>' +
      '<div class="dvc-muted">' + esc(iastOf(it, 'grantha')) + ' · sheet row ' + it.row + '</div>' +
      '<table class="dvc-minitable"><tbody>' +
      ['karta', 'vibhaga', 'vishayaVibhaga', 'prasthana', 'availability', 'status'].map(function (f) {
        return '<tr><td class="dvc-muted">' + esc(FIELD_LABEL[f] || f) + '</td><td>' + esc(eff(it, f) || '—') + '</td></tr>';
      }).join('') +
      '<tr><td class="dvc-muted">मूलम् · parent</td><td>' + (p && state.byId[p] ? '<a href="#" data-open="' + p + '">' + esc(eff(state.byId[p], 'grantha')) + '</a>' : '—') + '</td></tr>' +
      '<tr><td class="dvc-muted">वंशः · lineage</td><td>' + esc(it.breadcrumb) + '</td></tr>' +
      guruLinkFor(it) +
      (it.mention ? '<tr><td class="dvc-muted">note in sheet</td><td>' + esc(it.mention) + '</td></tr>' : '') +
      (libMatch ? '<tr><td class="dvc-muted">in the library</td><td>' + libMatch.matches.map(function (x) { return esc(x.title); }).join(', ') + '</td></tr>' : '') +
      '</tbody></table>' +
      (kids.length ? '<h4>' + kids.length + ' commentaries / dependent works</h4><ul class="dvc-kidlist">' +
        sortIds(kids).map(function (c) {
          var k = state.byId[c];
          return '<li><a href="#" data-open="' + c + '">' + esc(eff(k, 'grantha')) + '</a> <span class="dvc-muted">' + esc(eff(k, 'karta')) + '</span></li>';
        }).join('') + '</ul>' : '');
    $("#dvc-detail").style.display = '';
    $("#dvc-detail-close").onclick = function () { $("#dvc-detail").style.display = 'none'; };
  }

  /* ---------------- deep links from Guru Paramparā ---------------- */
  // #entry=r884  -> open that entry, with its ancestors expanded
  // #person=jayatirtha -> show only that ācārya's works
  function personToAuthorIds(personId) {
    var ids = new Set();
    (state.crossLinks.parampara || []).forEach(function (p) {
      if (p.kind === 'author' && p.nodeId === personId && p.authorId) ids.add(p.authorId);
    });
    (state.crossLinks.authorAliases || []).forEach(function (a) {
      if (a.personId === personId) ids.add(a.authorId);
    });
    Object.keys(state.ov.links || {}).forEach(function (k) {
      if (k.indexOf('kar-') === 0 && state.ov.links[k] === personId) ids.add(k);
    });
    return ids;
  }
  function applyHash() {
    var h = (location.hash || '').replace(/^#/, '');
    if (!h) return false;
    var m = /^entry=(.+)$/.exec(h);
    if (m) {
      var id = decodeURIComponent(m[1]);
      var it = state.byId[id];
      if (!it) return false;
      var p = effParent(it), guard = 0;
      while (p && state.byId[p] && guard++ < 50) { state.expanded[p] = true; p = effParent(state.byId[p]); }
      renderCurrentView(true);
      openDetail(id);
      var el = $('.dvc-node[data-id="' + id + '"]');
      if (el) el.scrollIntoView({ block: 'center' });
      return true;
    }
    m = /^person=(.+)$/.exec(h);
    if (m) {
      var pid = decodeURIComponent(m[1]);
      var ids = personToAuthorIds(pid);
      if (!ids.size) return false;
      state.personFilter = { personId: pid, authorIds: ids };
      showPersonBanner();
      rerender();
      return true;
    }
    return false;
  }
  function showPersonBanner() {
    var el = $("#dvc-personbanner");
    if (!el) return;
    if (!state.personFilter) { el.style.display = 'none'; return; }
    var names = state.masters.authors.filter(function (a) { return state.personFilter.authorIds.has(a.id); })
      .map(function (a) { return a.canonical; }).join(', ');
    el.style.display = '';
    el.innerHTML = 'Showing only works by <b>' + esc(names) + '</b> ' +
      '<span class="dvc-muted">(from Guru Paramparā · ' + esc(state.personFilter.personId) + ')</span> ' +
      '<button class="dvc-btn dvc-btn-sm" id="dvc-clearperson">✕ show everything</button>';
    $("#dvc-clearperson").onclick = function () {
      state.personFilter = null;
      try { history.replaceState(null, '', location.pathname + location.search); } catch (e) {}
      showPersonBanner(); rerender();
    };
  }
  // The reverse link: this author is a paramparā node, so offer their page.
  function guruLinkFor(item) {
    if (!item.kartaId) return '';
    var pid = null;
    (state.crossLinks.parampara || []).forEach(function (p) {
      if (p.kind === 'author' && p.authorId === item.kartaId) pid = p.nodeId;
    });
    (state.crossLinks.authorAliases || []).forEach(function (a) {
      if (a.authorId === item.kartaId) pid = pid || a.personId;
    });
    if (!pid) return '';
    return '<tr><td class="dvc-muted">गुरुपरम्परा</td><td><a href="../guru-parampara/guru1.html#' +
      esc(pid) + '" target="_blank" rel="noopener">' + esc(pid) + ' ↗</a></td></tr>';
  }

  /* ---------------- wiring ---------------- */
  function wire() {
    $("#dvc-search").addEventListener('input', function (e) { state.q = e.target.value; rerender(); });
    $("#dvc-sort").addEventListener('change', function (e) {
      var wasField = alphaField();
      state.sort = e.target.value; LS.set('sort', state.sort);
      // Switching between title and author sorting changes what the letter bar
      // indexes, so a letter picked for the old field would silently filter on
      // the new one. Drop it and redraw.
      if (alphaField() !== wasField) state.alpha = null;
      buildAlphaBar(); rerender();
    });
    $("#dvc-onlyflag").addEventListener('change', function (e) { state.onlyFlag = e.target.value; rerender(); });
    $("#dvc-more").addEventListener('click', function () { renderCurrentView(false); });
    $("#dvc-export").addEventListener('click', exportRowsCSV);
    $("#dvc-sync").addEventListener('click', syncToGitHub);
    $("#dvc-discard").addEventListener('click', function () {
      if (confirm('Discard every unsynced correction in this browser?')) discardDraft();
    });
    $("#dvc-expandall").addEventListener('click', function () {
      state.items.forEach(function (it) { if ((state.children[it.id] || []).length) state.expanded[it.id] = true; });
      renderCurrentView(true);
    });
    $("#dvc-collapseall").addEventListener('click', function () { state.expanded = {}; renderCurrentView(true); });

    $all(".dvc-viewbtn").forEach(function (b) {
      b.addEventListener('click', function () {
        state.view = b.dataset.view; LS.set('view', state.view);
        $all(".dvc-viewbtn").forEach(function (x) { x.classList.toggle('on', x === b); });
        $("#dvc-treectl").style.display = state.view === 'tree' ? '' : 'none';
        renderCurrentView(true);
      });
    });
    $all(".dvc-scriptbtn").forEach(function (b) {
      b.addEventListener('click', function () {
        state.script = b.dataset.script; LS.set('script', state.script);
        $all(".dvc-scriptbtn").forEach(function (x) { x.classList.toggle('on', x === b); });
        rerender(); if (state.tab !== 'catalogue') showTab(state.tab);
      });
    });
    $all(".dvc-tab").forEach(function (b) { b.addEventListener('click', function () { showTab(b.dataset.tab); }); });

    document.addEventListener('click', function (e) {
      var t = e.target;
      var toggle = t.closest('[data-toggle]');
      if (toggle) { var id = toggle.dataset.toggle; state.expanded[id] = !state.expanded[id]; renderCurrentView(true); return; }
      var open = t.closest('[data-open]');
      if (open) { e.preventDefault(); openDetail(open.dataset.open); return; }
      var alphaBtn = t.closest('[data-alpha]');
      if (alphaBtn) {
        var sc = alphaBtn.dataset.alphaScript, ltr = alphaBtn.dataset.alpha;
        state.alpha = (state.alpha && state.alpha.script === sc && state.alpha.letter === ltr)
          ? null : { script: sc, letter: ltr };
        buildAlphaBar(); rerender(); return;
      }
      if (t.closest('[data-alpha-all]')) { state.alpha = null; buildAlphaBar(); rerender(); return; }
      var chip = t.closest('.dvc-chip');
      if (chip && chip.dataset.col) {
        var set = state.tagFilters[chip.dataset.col], v = chip.dataset.val;
        if (set.has(v)) set.delete(v); else set.add(v);
        // Rebuild rather than toggle a class by hand: 'on' now means "showing",
        // so the two states differ by more than one class name.
        buildChips(); rerender(); return;
      }
      if (chip && chip.dataset.label) {
        state.labelFilter = state.labelFilter === chip.dataset.label ? '' : chip.dataset.label;
        buildChips(); rerender(); return;
      }
      var vchip = t.closest('[data-canon-kind]');
      if (vchip) { setCanonical(vchip.dataset.canonKind, vchip.dataset.canonKey, vchip.dataset.canonVal); return; }
      var canonCell = t.closest('[data-editcanon]');
      if (canonCell) {
        var trA = canonCell.closest('tr');
        beginCanonEdit(canonCell.parentNode, trA.dataset.mkind, trA.dataset.mkey, canonCell.textContent.trim());
        return;
      }
      var mergeBtn = t.closest('[data-mergemaster]');
      if (mergeBtn) {
        var trB = mergeBtn.closest('tr');
        var cell = trB.querySelector('td');
        beginCanonEdit(cell, trB.dataset.mkind, trB.dataset.mkey,
                       cell.textContent.trim(), { blank: true, placeholder: 'merge into which term?' });
        return;
      }
      var resetBtn = t.closest('[data-resetmaster]');
      if (resetBtn) {
        var trC = resetBtn.closest('tr');
        resetCanonical(trC.dataset.mkind, trC.dataset.mkey);
        return;
      }
      var addBtn = t.closest('[data-addterm]');
      if (addBtn) {
        var kind = addBtn.dataset.addterm;
        var inp = $('.dvc-newterm[data-kind="' + kind + '"]');
        var val = inp && inp.value.trim();
        if (!val) return;
        var extra = state.ov.extraTerms = state.ov.extraTerms || {};
        extra[kind] = extra[kind] || [];
        if (extra[kind].indexOf(val) < 0) extra[kind].push(val);
        saveDraft(); renderMasters(); refreshDatalists();
        return;
      }
      var delBtn = t.closest('[data-delterm]');
      if (delBtn) {
        var k2 = delBtn.dataset.delterm, v2 = delBtn.dataset.val;
        var ex = (state.ov.extraTerms || {})[k2] || [];
        state.ov.extraTerms[k2] = ex.filter(function (x) { return x !== v2; });
        saveDraft(); renderMasters(); refreshDatalists();
        return;
      }
      var acc = t.closest('[data-accept-parent]');
      if (acc) { acceptParent(acc.dataset.acceptParent, acc.dataset.parent); return; }
      var rej = t.closest('[data-reject-parent]');
      if (rej) { rejectParent(rej.dataset.rejectParent); return; }
      var rev = t.closest('[data-review]');
      if (rev) {
        var v2 = rev.dataset.review;
        if (v2 === 'clear') delete state.ov.review[rev.dataset.id]; else state.ov.review[rev.dataset.id] = v2;
        saveDraft(); rerender();
        // Repaint just this row. Re-rendering the whole tab collapsed the
        // <details> the curator was working inside and threw the page back to
        // the top -- one decision cost them their place in a 310-group list.
        var row = rev.closest('[data-duprow]');
        if (row) row.outerHTML = dupRowHTML(row.dataset.duprow);
        else renderDuplicates();
        return;
      }
      var lnk = t.closest('[data-link-id]');
      if (lnk) { state.ov.links[lnk.dataset.linkId] = lnk.dataset.linkVal; saveDraft(); renderCrossLinks(); return; }
      var unlnk = t.closest('[data-unlink-id]');
      if (unlnk) { delete state.ov.links[unlnk.dataset.unlinkId]; saveDraft(); renderCrossLinks(); return; }
    });

    // grid editing
    $("#dvc-gbody").addEventListener('dblclick', function (e) {
      var td = e.target.closest('.dvc-gcell'); if (td) beginEdit(td);
    });
    $("#dvc-gbody").addEventListener('click', function (e) {
      var td = e.target.closest('.dvc-gcell'); if (td) td.focus();
    });
    $("#dvc-gbody").addEventListener('keydown', function (e) {
      var td = e.target.closest && e.target.closest('.dvc-gcell');
      if (!td || td.querySelector('input')) return;
      var r = +td.dataset.r, c = +td.dataset.c;
      if (e.key === 'Enter' || e.key === 'F2') { beginEdit(td); e.preventDefault(); }
      else if (e.key === 'ArrowDown') { focusCell(r + 1, c); e.preventDefault(); }
      else if (e.key === 'ArrowUp') { focusCell(r - 1, c); e.preventDefault(); }
      else if (e.key === 'ArrowRight') { focusCell(r, c + 1); e.preventDefault(); }
      else if (e.key === 'ArrowLeft') { focusCell(r, c - 1); e.preventDefault(); }
      else if (e.key.length === 1 && !e.ctrlKey && !e.metaKey) { beginEdit(td); td.querySelector('input').value = e.key; e.preventDefault(); }
    });
    // spreadsheet paste: TSV fills down/right from the focused cell
    document.addEventListener('paste', function (e) {
      if (state.view !== 'grid') return;
      var td = document.activeElement && document.activeElement.closest && document.activeElement.closest('.dvc-gcell');
      if (!td) return;
      var text = (e.clipboardData || window.clipboardData).getData('text/plain');
      if (!text) return;
      e.preventDefault();
      var grid = text.replace(/\r/g, '').split('\n').map(function (l) { return l.split('\t'); });
      var r0 = +td.dataset.r, c0 = +td.dataset.c, n = 0;
      grid.forEach(function (vals, ri) {
        vals.forEach(function (val, ci) {
          var cell = $('td.dvc-gcell[data-r="' + (r0 + ri) + '"][data-c="' + (c0 + ci) + '"]');
          if (!cell) return;
          setRowField(cell.dataset.id, cell.dataset.field, val.trim());
          n++;
        });
      });
      renderCurrentView(true);
      syncSay('pasted ' + n + ' cells into the draft');
    });

    var mq = $("#dvc-masters-q"), mo = $("#dvc-masters-onlyvar");
    if (mq) mq.addEventListener('input', renderMasters);
    if (mo) mo.addEventListener('change', renderMasters);
    window.addEventListener('beforeunload', function (e) {
      if (state.dirty) { e.preventDefault(); e.returnValue = ''; }
    });
  }

  /* ---------------- boot ---------------- */
  function init() {
    Promise.all([loadData(), loadOverrides()]).then(function () {
      $all(".dvc-viewbtn").forEach(function (b) { b.classList.toggle('on', b.dataset.view === state.view); });
      $all(".dvc-scriptbtn").forEach(function (b) { b.classList.toggle('on', b.dataset.script === state.script); });
      $("#dvc-sort").value = state.sort;
      $("#dvc-treectl").style.display = state.view === 'tree' ? '' : 'none';
      buildChips();
      wire();
      rerender();
      updateSyncBar();
      applyHash();
      window.addEventListener('hashchange', applyHash);
    }).catch(function (e) {
      console.error('[dvaita-catalog] init failed', e);
      $("#dvc-tree").innerHTML = '<div class="dvc-empty-msg">Could not load the catalogue: ' + esc(e.message || e) + '</div>';
    });
  }

  document.addEventListener('DOMContentLoaded', init);
})();
