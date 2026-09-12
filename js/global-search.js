/*
 * global-search.js — corpus-wide Sanskrit-aware fuzzy search UI for DGE.
 *
 * Self-injecting and additive: adding this one <script> tag is the ONLY change
 * to index.html. It builds its own launcher (a 🔎 button + Cmd/Ctrl-K) and an
 * overlay, so it won't collide with the existing in-grantha search or any
 * parallel edits to the page. Depends on dge-normalize.js + dge-search.js
 * (load those first) and reuses the Sanscript engine already on the page for
 * non-Devanagari input.
 *
 * The static index is generated offline by build_search_index.py into
 * dge/search_index/. Override the path by setting window.DGE_SEARCH_INDEX.
 */
(function () {
  'use strict';
  // The index is 330 MB and lives on the "search-dist" branch, not in the
  // site: rebuilding it with the extract_text fix took the published site to
  // 1,013 MB against a 1 GB Pages ceiling. config.js sets
  // window.DGE_SEARCH_INDEX from appConfig; this constant is the same URL, so
  // a page that does not load config.js still finds it. Set the variable to
  // 'search_index' to read a local build instead.
  var CDN_INDEX = 'https://cdn.jsdelivr.net/gh/Tribhuvanachar/bhumandala@838335f8152654c37ee1c256c36b6ff6aab3927f';
  var INDEX_BASE = window.DGE_SEARCH_INDEX || CDN_INDEX;
  var idxPromise = null, debounce = null;
  var currentScheme = 'auto'; // set by the scheme popup, read by queryOpts()
  // Search scope (31 Aug 2026 project-lead ask, replacing the old single-
  // section dropdown): a MULTI-SELECT of slug-path prefixes at ANY depth of
  // the Library tree -- a whole section, one work (raghavendra_vijaya), a
  // single sarga -- searched together as one OR'd scope. Empty means
  // "Everything". The engine consumes this directly as
  // opts.includeGranthaPrefixes (dge-search.js), which also narrows the
  // per-section index fan-out to just the sections these touch.
  var scopeSel = [];            // selected slug-path prefixes, deduped (no selected descendant of a selected ancestor)
  var scopeTreeData = null;     // built once from the index manifest's granthas
  var scopeLabelByPath = {};    // path -> display label (leaf grantha title, or taxonomy segment label)

  // Post-search filters: narrow the results ALREADY fetched (never a new
  // network round trip -- a fresh query is already a 10+ second multi-shard
  // fetch through jsdelivr, see onType()'s own note; re-querying per filter
  // toggle would only make that worse). lastHits/lastQuery hold the most
  // recent completed search so filters + renderRows() can re-slice it.
  // lastQueryDeva is the SAME query converted to Devanagari (see
  // queryToDevanagari() below) rather than folded to SLP1 -- computed once
  // per search, read by applyFilters()'s "Exact spelling only" toggle.
  var lastHits = null, lastQuery = '', lastQueryDeva = '', lastSearchElapsedMs = null;
  // "Exact spelling only" is a reader preference, not a per-search result --
  // persisted the same way as the app's other standing preferences (theme,
  // script, selection mode: dge_vyakarana_dark, dge_lang_pref,
  // dge_selection_mode) so it survives a page reload instead of resetting
  // to off every time.
  var EXACT_STORAGE_KEY = 'dge_gs_exact_spelling';
  // Default ON (30 Aug 2026, project-lead ask: "if I search for Kanthaya,
  // only those results which has explicit Kanthaya in the text must be
  // returned" -- fuzzy/near matches should be something a reader opts INTO,
  // not something they have to opt OUT of every search to avoid). A reader
  // who has never touched the chip gets exact-only by default; one who has
  // explicitly turned it off (localStorage holds '0') keeps that choice, same
  // persistence as before -- only the UNSET default direction changed.
  function dgeGsLoadExact() {
    try {
      var v = localStorage.getItem(EXACT_STORAGE_KEY);
      return v === null ? true : v === '1';
    } catch (e) { return true; }
  }
  function dgeGsSaveExact(v) {
    try { localStorage.setItem(EXACT_STORAGE_KEY, v ? '1' : '0'); } catch (e) { /* ignore */ }
  }
  var filterState = { type: 'all', categories: {}, siddhanta: {}, keyword: '', exact: dgeGsLoadExact() };
  // Single canonical label source (24 Aug 2026 UI/UX pass): both the
  // category filter-chip row AND the corpus-scope dropdown used to carry
  // their OWN hardcoded label maps -- one mostly-Devanagari, one entirely
  // IAST -- so the same category ("Vedāṅga" vs "वेदाङ्गानि") read as two
  // different taxonomies depending on which control you looked at, and
  // neither responded to the script picker. Both now resolve through
  // library.js's window.dgeSegLabel(seg), the exact function the Library
  // tree already uses for every folder label: DGE_PATH_LABELS' Devanagari
  // name (source of truth) run through dgeToActiveScript() so it follows
  // the reader's own script preference, the same as every other label in
  // the app. A category/section this maps has NOTHING app-specific about
  // it here anymore -- taxonomyLabel() falls back to a plain title-cased
  // rendering only if library.js somehow didn't load (defensive, not the
  // normal path -- index.html always loads library.js before this file).
  function taxonomyLabel(seg) {
    if (typeof window.dgeSegLabel === 'function') return window.dgeSegLabel(seg);
    return String(seg || '').replace(/_/g, ' ').replace(/\b\w/g, function (c) { return c.toUpperCase(); });
  }
  // Advaita/Dvaita/Vishishtadvaita aren't their own field on a hit (the
  // search index doesn't carry one) but this project's own taxonomy paths
  // already encode it unambiguously in the slug for anything under
  // darshana/vedanta/* -- real signal, not a guess, just read from where
  // it already lives rather than duplicated into a new field. The
  // dvaitavedanta prefix check is kept for hits from a not-yet-rebuilt
  // search index still carrying the pre-23-Aug-2026 top-level path.
  function siddhantaOf(slug) {
    if (/(^|\/)advaita(\/|$)/.test(slug)) return 'advaita';
    if (/(^|\/)vishishtadvaita(\/|$)/.test(slug)) return 'vishishtadvaita';
    if (/(^|\/)dvaita(\/|$)/.test(slug) || slug.indexOf('dvaitavedanta') === 0) return 'dvaita';
    return null;
  }



  function css() {
    if (document.getElementById('dge-gs-css')) return;
    var s = document.createElement('style');
    s.id = 'dge-gs-css';
    // Colours read the app's real design tokens (css/main.css) so the search
    // UI themes with the rest of the site. The overlay sits at modal level
    // (11000). Both the input-script picker and the search-scope picker are
    // the same custom button+popup-list shape (styled to match the app's
    // other controls) instead of a native <select> -- see the
    // .dge-gs-schemewrap comment below for why.
    // 24 Aug 2026: this used to also define a .dge-gs-fab floating circle.
    // The project lead's direct follow-up report overrides the earlier
    // "keep both FABs, they're frequent enough" call: "let it not sit
    // there... go into some menu item." build() below no longer creates a
    // trigger button of its own -- index.html's #dge-qa-tab is the only
    // entry point left, calling window.DGEGlobalSearch.open() directly
    // (still the same real, already-exported API further down this file).
    s.textContent = [
      '.dge-gs-overlay{position:fixed;inset:0;z-index:11000;background:rgba(0,0,0,.45);display:none}',
      '.dge-gs-overlay.open{display:block}',
      // overflow:visible, NOT hidden (31 Aug 2026): before any search runs
      // the panel is only as tall as the top bar plus one hint line, and
      // overflow:hidden was CLIPPING both dropdown popups at the panel's
      // bottom edge -- reported live with a screenshot: the scope list
      // showed "Everything" plus one section and cut off the other eleven.
      // The rounded-corner clipping the hidden overflow provided is kept by
      // rounding .dge-gs-results' own bottom corners below instead.
      '.dge-gs-panel{position:relative;max-width:720px;margin:6vh auto 0;background:var(--panel-bg,var(--card-bg,#fff));backdrop-filter:blur(var(--glass-blur,0px));-webkit-backdrop-filter:blur(var(--glass-blur,0px));color:var(--text-primary,#1a1a1a);border:1px solid var(--card-border,rgba(0,0,0,.12));border-radius:12px;box-shadow:0 10px 40px rgba(0,0,0,.4);overflow:visible;font-family:inherit}',
      '.dge-gs-top{display:flex;gap:8px;padding:12px;border-bottom:1px solid var(--card-border,rgba(0,0,0,.12));align-items:center}',
      // Phone widths (7 Sep 2026, reported with a screenshot: the ✕ and the
      // scope button sat at, and past, the screen's right edge): the panel
      // keeps a margin inside the viewport, and the bar wraps -- the input
      // takes the first line, the four buttons the second -- instead of
      // squeezing five flex:none controls into 400px.
      '@media (max-width:560px){.dge-gs-panel{margin:8px 8px 0}.dge-gs-top{flex-wrap:wrap;padding:10px}.dge-gs-top .dge-gs-input{flex:1 1 100%}.dge-gs-top .dge-gs-x{margin-left:auto}}',
      // min-width:0 overrides the flex-item default of auto (which resolves
      // to the input's intrinsic content width) -- without it, this input
      // refuses to shrink below that width on a narrow phone, pushing the
      // two flex:none schemewrap buttons (and their popups) past the
      // panel's right edge, where .dge-gs-panel{overflow:hidden} clips
      // them -- confirmed live: "Everything ▾" truncated to "Eve", the
      // opened scope popup's option labels all cut off mid-word.
      '.dge-gs-input{flex:1;min-width:0;font-size:17px;padding:10px 12px;border:1px solid var(--card-border,rgba(0,0,0,.2));border-radius:8px;background:var(--card-bg,transparent);color:inherit}',
      // A custom popup (trigger button + a dropped-down option list), not a
      // native <select> -- a <select>'s OPEN list is drawn by the OS on
      // mobile and cannot be restyled, which is exactly what made this look
      // inconsistent with every other dropdown in the app (all of which are
      // this same button+popup-list shape; see #displayPopup in index.html).
      '.dge-gs-schemewrap{position:relative;flex:none}',
      '.dge-gs-schemebtn{border:1px solid var(--card-border,rgba(0,0,0,.2));border-radius:8px;background:var(--card-bg,#fff);color:var(--text-primary,inherit);padding:0 12px;height:40px;font:inherit;font-size:14px;cursor:pointer;white-space:nowrap}',
      '.dge-gs-schemebtn:focus{outline:none;border-color:var(--accent-red,#7a3b1d)}',
      '.dge-gs-scheme-pop{position:absolute;top:calc(100% + 6px);right:0;background:var(--panel-bg,var(--card-bg,#fff));backdrop-filter:blur(var(--glass-blur,14px));-webkit-backdrop-filter:blur(var(--glass-blur,14px));border:1px solid var(--card-border,rgba(0,0,0,.15));border-radius:10px;box-shadow:0 8px 24px rgba(0,0,0,.25);padding:6px;display:flex;flex-direction:column;gap:2px;min-width:110px;max-height:60vh;overflow-y:auto;z-index:5;opacity:0;visibility:hidden;transform:translateY(4px);transition:opacity .12s ease,transform .12s ease,visibility .12s ease}',
      '.dge-gs-scheme-pop.show{opacity:1;visibility:visible;transform:translateY(0)}',
      '.dge-gs-scheme-opt{padding:8px 10px;font-size:13px;font-weight:600;border-radius:6px;cursor:pointer;color:var(--text-primary,inherit)}',
      '.dge-gs-scheme-opt:hover{background:var(--card-border,rgba(0,0,0,.08))}',
      '.dge-gs-scheme-opt.active{background:var(--card-active,rgba(122,59,29,.12));color:var(--accent-red,#7a3b1d)}',
      // Scope tree popup: anchored to the panel (its positioned ancestor),
      // spanning nearly its width -- a hierarchical checklist, not a flat
      // option list, so it gets its own class and geometry. Its own
      // max-height + scroll means it can never be cut off the way the old
      // section list was, however short the panel underneath is.
      '.dge-gs-scope-pop{position:absolute;top:calc(100% + 6px);right:0;width:min(88vw,440px);background:var(--panel-bg,var(--card-bg,#fff));backdrop-filter:blur(var(--glass-blur,14px));-webkit-backdrop-filter:blur(var(--glass-blur,14px));border:1px solid var(--card-border,rgba(0,0,0,.15));border-radius:10px;box-shadow:0 8px 24px rgba(0,0,0,.25);padding:6px;max-height:60vh;overflow-y:auto;z-index:6;opacity:0;visibility:hidden;transform:translateY(4px);transition:opacity .12s ease,transform .12s ease,visibility .12s ease}',
      '.dge-gs-scope-pop.show{opacity:1;visibility:visible;transform:translateY(0)}',
      '.dge-gs-scope-hint{padding:6px 10px 8px;font-size:11px;opacity:.55}',
      '.dge-gs-tree-row{display:flex;align-items:center;gap:6px;padding:7px 8px;font-size:13px;border-radius:6px;cursor:pointer;color:var(--text-primary,inherit)}',
      '.dge-gs-tree-row:hover{background:var(--card-border,rgba(0,0,0,.08))}',
      '.dge-gs-tree-exp{flex:none;width:22px;height:22px;line-height:22px;text-align:center;border-radius:5px;opacity:.7;font-size:11px}',
      '.dge-gs-tree-exp:hover{background:var(--card-active,rgba(122,59,29,.12))}',
      '.dge-gs-tree-box{flex:none;width:16px;height:16px;border:1.5px solid var(--card-border,rgba(0,0,0,.35));border-radius:4px;display:inline-flex;align-items:center;justify-content:center;font-size:11px;line-height:1;color:#fff;background:transparent}',
      '.dge-gs-tree-row.sel .dge-gs-tree-box{background:var(--accent-red,#7a3b1d);border-color:var(--accent-red,#7a3b1d)}',
      '.dge-gs-tree-row.cov .dge-gs-tree-box{background:var(--accent-red,#7a3b1d);border-color:var(--accent-red,#7a3b1d);opacity:.45}',
      '.dge-gs-tree-label{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}',
      '.dge-gs-tree-row.sel .dge-gs-tree-label{color:var(--accent-red,#7a3b1d);font-weight:700}',
      '.dge-gs-tree-n{flex:none;font-size:11px;opacity:.5}',
      '.dge-gs-tree-kids{display:none}',
      '.dge-gs-tree-kids.openk{display:block}',
      // Selected-targets chip row: the visible answer to "what am I
      // actually searching right now" -- lives OUTSIDE the popup, under the
      // search bar, exactly as asked ("all selected targets should appear
      // somewhere instead of in the drop-down").
      '.dge-gs-scope-chips{display:flex;flex-wrap:wrap;gap:6px;align-items:center;padding:8px 12px;border-bottom:1px solid var(--card-border,rgba(0,0,0,.12))}',
      '.dge-gs-scope-chips[hidden]{display:none}',
      '.dge-gs-scope-chip{display:inline-flex;align-items:center;gap:6px;max-width:100%;border:1px solid var(--accent-red,#7a3b1d);background:var(--card-active,rgba(122,59,29,.10));color:var(--accent-red,#7a3b1d);border-radius:999px;padding:3px 10px;font-size:12px;font-weight:600}',
      '.dge-gs-scope-chip span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}',
      '.dge-gs-scope-chip b{flex:none;cursor:pointer;font-weight:700;opacity:.75}',
      '.dge-gs-scope-chip b:hover{opacity:1}',
      '.dge-gs-scope-clear{border:none;background:none;color:var(--muted-text,#8a7a63);font-size:11px;cursor:pointer;text-decoration:underline dotted;padding:2px 4px}',
      '.dge-gs-x{border:1px solid var(--card-border,rgba(0,0,0,.2));background:var(--card-bg,#fff);color:var(--muted-text,#8a7a63);border-radius:8px;width:40px;height:40px;font-size:16px;cursor:pointer;flex:none}',
      '.dge-gs-x:hover{color:var(--accent-red,#7a3b1d);border-color:var(--accent-red,#7a3b1d)}',
      // Bottom corners rounded here now that the panel itself no longer
      // clips (see .dge-gs-panel's overflow comment above).
      '.dge-gs-results{max-height:64vh;overflow:auto;padding:6px 0;border-radius:0 0 12px 12px}',
      '.dge-gs-row{padding:10px 14px;cursor:pointer;border-bottom:1px solid var(--card-border,rgba(0,0,0,.06))}',
      '.dge-gs-row:hover{background:var(--card-active,rgba(122,59,29,.08))}',
      '.dge-gs-meta{font-size:12px;opacity:.7;display:flex;gap:8px;flex-wrap:wrap}',
      // Real taxonomy hierarchy per hit (see taxonomyCrumbsHtml()) — small
      // and muted so it reads as metadata, not competing with the title.
      '.dge-gs-crumbs{font-size:11px;margin-top:2px;display:flex;flex-wrap:wrap;align-items:center;gap:2px;opacity:.75}',
      '.dge-gs-crumb-seg{color:var(--accent-red,#7a3b1d);text-decoration:underline dotted;text-underline-offset:2px;cursor:pointer}',
      '.dge-gs-crumb-seg:hover,.dge-gs-crumb-seg:focus-visible{text-decoration-style:solid}',
      '.dge-gs-crumb-current{color:inherit;font-weight:600}',
      '.dge-gs-crumb-sep{opacity:.6}',
      '.dge-gs-snip{font-size:16px;margin-top:2px;line-height:1.5}',
      '.dge-gs-hl{background:rgba(232,178,77,.4);color:inherit;border-radius:3px;padding:0 1px;font-weight:700}',
      '.dge-gs-hint{padding:14px;opacity:.6;font-size:13px;display:flex;align-items:center;gap:8px}',
      '.dge-gs-histwrap{padding:4px 14px 12px}',
      '.dge-gs-histhead{font-size:11px;opacity:.55;margin-bottom:6px;display:flex;align-items:center;gap:8px}',
      '.dge-gs-histclear{background:none;border:none;color:inherit;font-size:11px;opacity:.7;cursor:pointer;text-decoration:underline;padding:0}',
      '.dge-gs-histchip{display:inline-block;margin:2px 4px 2px 0;padding:4px 10px;font:inherit;font-size:12.5px;color:inherit;background:var(--card-active,rgba(0,0,0,.06));border:1px solid var(--card-border,rgba(0,0,0,.12));border-radius:999px;cursor:pointer}',
      '.dge-gs-histchip:hover{border-color:var(--accent-red,#9A1B1B)}',
      '.dge-gs-sugrow{padding:8px 14px 0;display:flex;align-items:center;gap:4px;flex-wrap:wrap;font-size:13px}',
      // A cold-cache query is a manifest fetch plus several postings-bucket
      // and grantha-shard round trips through jsdelivr (see onType()'s own
      // comment) -- 10+ seconds is common. Confirmed live with a throttled
      // connection: the plain "Searching..." text alone sits completely
      // static that whole time, which reads as inert/stuck exactly like the
      // silent placeholder this hint was built to replace, just with one
      // more word on screen. This spinner keeps the modal visibly alive for
      // however long the wait actually is. Declares its own @keyframes
      // rather than reusing main.css's -- ashtadhyayi.html/dhatu.html load
      // this file too but style themselves with vyakarana-base.css instead
      // of main.css, so this file can't assume main.css's keyframe exists
      // (same self-contained-injection reasoning as this file's own header
      // comment gives for shipping its whole stylesheet inline).
      '.dge-gs-spinner{width:13px;height:13px;flex:none;border:2px solid var(--card-border,rgba(0,0,0,.2));border-top-color:var(--accent-red,#7a3b1d);border-radius:50%;animation:dge-gs-spin .7s linear infinite}',
      '@keyframes dge-gs-spin{100%{transform:rotate(360deg)}}',
      // Determinate readout under the spinner: dge-search.js's search() now
      // reports real "N of M index files fetched" / "N of M texts opened"
      // progress (both counts are known ahead of the fetch that reports
      // them -- see allWithProgress()'s own comment), so this shows that
      // instead of leaving the reader to guess how much longer a 10+ second
      // cold-cache query has left.
      '.dge-gs-progress{height:3px;margin:0 14px 10px;background:var(--card-border,rgba(0,0,0,.12));border-radius:2px;overflow:hidden}',
      '.dge-gs-progress-bar{display:block;height:100%;width:0%;background:var(--accent-red,#7a3b1d);transition:width .15s ease}',
      // Real elapsed seconds, ticking while a query runs (startElapsedTimer())
      // and a one-line final report once it lands (elapsedNoteHtml()) --
      // project-lead ask: "N of M" alone doesn't say how many actual SECONDS
      // this is taking. Tabular-nums so the width doesn't jitter as the digits change.
      '.dge-gs-elapsed{font-variant-numeric:tabular-nums;opacity:.7}',
      '.dge-gs-elapsed-note{padding-top:10px;font-size:12px;opacity:.55}',
      '.dge-gs-filterbar{padding:8px 12px;border-bottom:1px solid var(--card-border,rgba(0,0,0,.12));display:flex;flex-direction:column;gap:6px;}',
      '.dge-gs-frow{display:flex;gap:6px;flex-wrap:wrap;align-items:center;}',
      '.dge-gs-flabel{font-size:10.5px;opacity:.55;text-transform:uppercase;letter-spacing:.4px;flex:0 0 100%;margin-top:2px;}',
      '.dge-gs-flabel:first-child{margin-top:0;}',
      '.dge-gs-chip{border:1px solid var(--card-border,rgba(0,0,0,.2));background:var(--card-bg,#fff);color:var(--text-primary,inherit);border-radius:999px;padding:4px 11px;font-size:12px;cursor:pointer;white-space:nowrap;}',
      '.dge-gs-chip.active{background:var(--accent-red,#7a3b1d);border-color:var(--accent-red,#7a3b1d);color:#fff;}',
      '.dge-gs-kwbox{flex:1;min-width:120px;font-size:12px;padding:5px 9px;border:1px solid var(--card-border,rgba(0,0,0,.2));border-radius:8px;background:var(--card-bg,transparent);color:inherit;}',
      '.dge-gs-fcount{font-size:11px;opacity:.55;padding:0 4px;}'
    ].join('\n');
    document.head.appendChild(s);
  }

  // Guards against open() rebuilding the whole panel on every call: harmless
  // when there was nothing to populate post-load (the scheme <select> was
  // static markup), but the section <select> IS populated post-load from
  // the index's manifest, and a rebuilt duplicate got only "Everything" --
  // found by testing a second open() in the same page, not by inspection.
  function build() {
    if (document.getElementById('dge-gs-overlay')) return;
    css();
    var ov = document.createElement('div');
    ov.className = 'dge-gs-overlay';
    ov.id = 'dge-gs-overlay';
    ov.innerHTML =
      '<div class="dge-gs-panel" role="dialog" aria-label="Global search">' +
        '<div class="dge-gs-top">' +
          '<input class="dge-gs-input" id="dge-gs-input" placeholder="Search all texts — Devanagari, IAST, HK, or SLP1…" autocomplete="off">' +
          '<div class="dge-gs-schemewrap" id="dge-gs-scheme-wrap">' +
            '<button type="button" class="dge-gs-schemebtn" id="dge-gs-scheme-btn" title="Input script">auto ▾</button>' +
            '<div class="dge-gs-scheme-pop" id="dge-gs-scheme-pop">' +
              '<div class="dge-gs-scheme-opt active" data-scheme="auto">auto</div>' +
              '<div class="dge-gs-scheme-opt" data-scheme="devanagari">देव</div>' +
              '<div class="dge-gs-scheme-opt" data-scheme="iast">IAST</div>' +
              '<div class="dge-gs-scheme-opt" data-scheme="hk">HK</div>' +
              '<div class="dge-gs-scheme-opt" data-scheme="slp1">SLP1</div>' +
            '</div>' +
          '</div>' +
          // Same custom button+popup-list shape as the input-script picker
          // just above, not a native <select> -- a <select>'s OPEN list is
          // drawn by the OS on mobile and cannot be restyled, which made
          // this the one light-themed, unstyleable dropdown left in an
          // otherwise fully dark, custom-styled UI (confirmed against a
          // live screenshot). The section list is only known once the
          // index's manifest loads, so this starts as just "Everything"
          // and fills in via populateScope() below, same as the <select>
          // it replaces did with <option>s.
          // Scope picker (31 Aug 2026 rebuild): no longer a flat section
          // list -- a hierarchical, MULTI-SELECT tree of the whole library
          // (section -> work -> sarga/grantha), populated by
          // populateScope() once the index manifest loads. Selected
          // targets render as chips in #dge-gs-scope-chips below the bar,
          // not inside the popup.
          '<div class="dge-gs-schemewrap" id="dge-gs-section-wrap">' +
            '<button type="button" class="dge-gs-schemebtn" id="dge-gs-section-btn" title="Search scope">Everything ▾</button>' +
            '<div class="dge-gs-scope-pop" id="dge-gs-section-pop">' +
              '<div class="dge-gs-scope-hint">Tick any level — a whole section, one work, or a single sarga. Several at once searches them together.</div>' +
              '<div class="dge-gs-tree-row" id="dge-gs-scope-all"><span class="dge-gs-tree-exp"></span><span class="dge-gs-tree-box">✓</span><span class="dge-gs-tree-label"><b>Everything</b></span></div>' +
              '<div id="dge-gs-scope-tree"></div>' +
            '</div>' +
          '</div>' +
          '<button class="dge-gs-schemebtn" id="dge-gs-sugbtn" title="Suggestions on — tap to turn off" aria-label="Toggle search suggestions" onclick="window.dgeGsToggleSuggest()">💡</button>' +
          '<button class="dge-gs-x" id="dge-gs-x" title="Close (Esc)" aria-label="Close">✕</button>' +
        '</div>' +
        '<div class="dge-gs-scope-chips" id="dge-gs-scope-chips" hidden></div>' +
        '<div class="dge-gs-filterbar" id="dge-gs-filterbar" style="display:none;"></div>' +
        '<div class="dge-gs-results" id="dge-gs-results"><div class="dge-gs-hint">Type a word or phrase in any script. Matching is sandhi/spelling tolerant.</div></div>' +
      '</div>';
    // 1 Sep 2026, project-lead direction: the dialog stays open until the
    // reader EXPLICITLY closes it -- tapping outside no longer closes it
    // at all. (This also retires the 31 Aug ghost-click backdrop saga for
    // good: with no backdrop close path there is nothing for a trailing
    // compatibility click to hit.) Esc and the ✕ button remain the two
    // explicit ways out.
    document.body.appendChild(ov);

    // Same guard on the ✕ button: it renders at a fixed top-right spot the
    // opening tap can also coincide with (e.g. the Genie sheet's own close
    // control sat there a frame earlier).
    document.getElementById('dge-gs-x').addEventListener('click', function () {
      if (Date.now() - lastOpenAt < GHOST_CLICK_GUARD_MS) return;
      close();
    });
    document.getElementById('dge-gs-input').addEventListener('input', onType);
    // Enter commits the query to history even without opening a hit.
    document.getElementById('dge-gs-input').addEventListener('keydown', function (e) {
      if (e.key === 'Enter') gsPushHistory(e.target.value);
    });
    // Idle state shows the recent-search chips; suggestion toggle reflects
    // its persisted setting.
    document.getElementById('dge-gs-results').innerHTML = gsIdleHtml();
    var sugBtn = document.getElementById('dge-gs-sugbtn');
    if (sugBtn && !gsSuggestOn()) { sugBtn.style.opacity = '.35'; sugBtn.title = 'Suggestions off — tap to turn on'; }
    document.addEventListener('keydown', function (e) {
      if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K')) { e.preventDefault(); open(); }
      if (e.key === 'Escape') close();
    });

    // Re-runs the current query immediately after either popup's choice
    // changes -- no need to retype for the search to reflect the new
    // script/scope. Dispatches a real Event so onType(e) gets a genuine
    // e.target to read (onType destructures e.target.value); a bare
    // onType() call here previously threw "Cannot read properties of
    // undefined (reading 'target')" and silently skipped the re-search --
    // a real bug, confirmed live (picking an input-script option while a
    // query was already typed), not something introduced by this change.
    function rerunIfQueried() {
      var input = document.getElementById('dge-gs-input');
      if (input.value.trim()) input.dispatchEvent(new Event('input'));
    }

    var schemeBtn = document.getElementById('dge-gs-scheme-btn');
    var schemePop = document.getElementById('dge-gs-scheme-pop');
    schemeBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      schemePop.classList.toggle('show');
    });
    schemePop.addEventListener('click', function (e) {
      var opt = e.target.closest('.dge-gs-scheme-opt');
      if (!opt) return;
      currentScheme = opt.dataset.scheme;
      schemeBtn.textContent = (opt.textContent || currentScheme) + ' ▾';
      schemePop.querySelectorAll('.dge-gs-scheme-opt').forEach(function (o) { o.classList.toggle('active', o === opt); });
      schemePop.classList.remove('show');
      rerunIfQueried();
    });

    // Search-scope picker: the button opens the Library-tree popup (built
    // by populateScope() from the index manifest); all selection logic
    // lives in the scope-tree functions below build(). Opening it also
    // kicks ensureIndex() so a reader who opens the scope FIRST (before
    // typing anything) still gets the tree populated.
    var sectionBtn = document.getElementById('dge-gs-section-btn');
    var sectionPop = document.getElementById('dge-gs-section-pop');
    sectionBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      sectionPop.classList.toggle('show');
      if (sectionPop.classList.contains('show')) ensureIndex();
    });
    document.getElementById('dge-gs-scope-all').addEventListener('click', function () {
      clearScope();
    });

    // Same click-outside-closes convention as the overlay itself (line
    // above: `if (e.target === ov) close()`). Scoped per popup by its own
    // wrapper id so clicking inside one never closes the other.
    document.addEventListener('click', function (e) {
      if (schemePop.classList.contains('show') && !e.target.closest('#dge-gs-scheme-wrap')) {
        schemePop.classList.remove('show');
      }
      if (sectionPop.classList.contains('show') && !e.target.closest('#dge-gs-section-wrap')) {
        sectionPop.classList.remove('show');
      }
    });
  }

  // populateScope is attached on EVERY call, not only the one that
  // actually creates idxPromise -- 24 Aug 2026, needed once prefetchManifest()
  // below could call this before build() has ever run (no #dge-gs-scope-tree
  // to populate yet). Splitting "fetch and cache the index" from "populate
  // the (maybe not-yet-built) DOM" this way means a prefetch's own idle-time
  // call safely no-ops (populateScope's own data-populated/element-exists
  // guards handle that), and the LATER real call from open() -- after build()
  // has created the popup -- still populates it correctly, from the same
  // already-resolved, cached promise.
  // ---- search history + suggestions + hide-from-search (1 Sep 2026, the
  // project lead's three asks in one message: keep the last 25 searches,
  // offer IDE-style typo-tolerant suggestions while typing (toggleable),
  // and let the Library Manager hide a grantha from SEARCH independently
  // of hiding it from the Library tree). ------------------------------------
  var GS_ROOT = (function () {
    var s = (document.currentScript && document.currentScript.src) || '';
    try { return new URL('../../', s).href; } catch (e) { return '../'; }
  })();
  var HIST_KEY = 'dge.gs.history', HIST_MAX = 25;
  function gsHistory() { try { var a = JSON.parse(localStorage.getItem(HIST_KEY) || '[]'); return Array.isArray(a) ? a : []; } catch (e) { return []; } }
  function gsPushHistory(q) {
    q = (q || '').trim(); if (q.length < 2) return;
    var a = gsHistory().filter(function (x) { return x !== q; });
    a.unshift(q);
    try { localStorage.setItem(HIST_KEY, JSON.stringify(a.slice(0, HIST_MAX))); } catch (e) { /* ignore */ }
  }
  window.dgeGsHistoryPick = function (i) {
    var q = gsHistory()[i]; if (q == null) return;
    var inp = document.getElementById('dge-gs-input');
    inp.value = q; inp.dispatchEvent(new Event('input')); inp.focus();
  };
  window.dgeGsHistoryClear = function () {
    try { localStorage.removeItem(HIST_KEY); } catch (e) { /* ignore */ }
    var r = document.getElementById('dge-gs-results'); if (r) r.innerHTML = gsIdleHtml();
  };
  function gsIdleHtml() {
    var hint = '<div class="dge-gs-hint">Type a word or phrase in any script. Matching is sandhi/spelling tolerant.</div>';
    var h = gsHistory();
    if (!h.length) return hint;
    return hint + '<div class="dge-gs-histwrap"><div class="dge-gs-histhead">Recent searches ' +
      '<button type="button" class="dge-gs-histclear" onclick="window.dgeGsHistoryClear()">clear</button></div>' +
      h.map(function (q, i) {
        return '<button type="button" class="dge-gs-histchip" onclick="window.dgeGsHistoryPick(' + i + ')">' + esc(q) + '</button>';
      }).join('') + '</div>';
  }

  function gsSuggestOn() { try { return localStorage.getItem('dge.gs.suggest') !== '0'; } catch (e) { return true; } }
  window.dgeGsToggleSuggest = function () {
    var on = !gsSuggestOn();
    try { localStorage.setItem('dge.gs.suggest', on ? '1' : '0'); } catch (e) { /* ignore */ }
    var b = document.getElementById('dge-gs-sugbtn');
    if (b) { b.style.opacity = on ? '1' : '.35'; b.title = on ? 'Suggestions on — tap to turn off' : 'Suggestions off — tap to turn on'; }
    var inp = document.getElementById('dge-gs-input');
    if (inp && inp.value.trim()) inp.dispatchEvent(new Event('input'));
  };
  // Consonant skeleton across scripts: नारायण and "Nallayana" both reduce
  // to r/l-level skeletons (nryn vs nlyn) where a bounded edit distance
  // catches the typo. Aspirates fold (kh->k via the h-strip), vowels drop,
  // doubles collapse — the same folding family the sutra-name identifier
  // (intellisense.js) already uses.
  var GS_DEVA_C = { 'क':'k','ख':'k','ग':'g','घ':'g','ङ':'n','च':'c','छ':'c','ज':'j','झ':'j','ञ':'n',
    'ट':'t','ठ':'t','ड':'d','ढ':'d','ण':'n','त':'t','थ':'t','द':'d','ध':'d','न':'n',
    'प':'p','फ':'p','ब':'b','भ':'b','म':'m','य':'y','र':'r','ल':'l','व':'v','श':'s','ष':'s','स':'s','ह':'h','ळ':'l' };
  function gsSkel(s) {
    s = String(s || '').toLowerCase();
    var out = '';
    for (var i = 0; i < s.length; i++) {
      var ch = s[i];
      if (GS_DEVA_C[ch]) out += GS_DEVA_C[ch];
      else if (ch >= 'a' && ch <= 'z') out += ch;
    }
    return out.replace(/h/g, '').replace(/[aeiou]/g, '').replace(/(.)\1+/g, '$1');
  }
  function gsEditDist(a, b, max) {
    if (Math.abs(a.length - b.length) > max) return max + 1;
    var prev = [], cur, j;
    for (j = 0; j <= b.length; j++) prev[j] = j;
    for (var i = 1; i <= a.length; i++) {
      cur = [i]; var rowMin = i;
      for (j = 1; j <= b.length; j++) {
        cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
        if (cur[j] < rowMin) rowMin = cur[j];
      }
      if (rowMin > max) return max + 1;
      prev = cur;
    }
    return prev[b.length];
  }
  var gsEngineRef = null, gsCandCache = null;
  function gsCandidates() {
    if (gsCandCache) return gsCandCache;
    var set = {};
    gsHistory().forEach(function (q) { set[q] = 1; });
    if (gsEngineRef && gsEngineRef.granthas) {
      gsEngineRef.granthas.forEach(function (g) {
        var slug = (typeof g === 'string') ? g : (g && g.slug) || '';
        slug.split('/').slice(-3).forEach(function (seg) {
          if (!seg || seg === 'mula' || seg.indexOf('tika_') === 0 || /_\d+$/.test(seg)) return;
          set[seg.replace(/_/g, ' ')] = 1;
        });
      });
      gsCandCache = Object.keys(set);  // cache only once the manifest is in
      return gsCandCache;
    }
    return Object.keys(set);
  }
  function gsSuggestHtml(q) {
    if (!gsSuggestOn() || q.length < 3) return '';
    var qs = gsSkel(q);
    if (qs.length < 2) return '';
    var scored = [];
    gsCandidates().forEach(function (c) {
      if (c.toLowerCase() === q.toLowerCase()) return;
      var cs = gsSkel(c);
      if (!cs) return;
      var d;
      if (cs === qs) d = 0;
      else if (cs.indexOf(qs) === 0) d = 0.5;
      else if (cs.indexOf(qs) > 0) d = 1.5;
      else { d = gsEditDist(qs, cs, 2); if (d > 2) return; }
      scored.push([d, c]);
    });
    scored.sort(function (a, b) { return a[0] - b[0] || a[1].length - b[1].length; });
    var top = scored.slice(0, 6);
    if (!top.length) return '';
    return '<div class="dge-gs-sugrow"><span title="Suggestions">💡</span>' + top.map(function (t) {
      return '<button type="button" class="dge-gs-histchip" data-q="' + esc(t[1]) + '" onclick="window.dgeGsSuggestPick(this)">' + esc(t[1]) + '</button>';
    }).join('') + '</div>';
  }
  window.dgeGsSuggestPick = function (btn) {
    var inp = document.getElementById('dge-gs-input');
    inp.value = btn.getAttribute('data-q');
    inp.dispatchEvent(new Event('input')); inp.focus();
  };

  // Curator "hide from search" (admin/config/library-overrides.json's
  // searchHidden list — written by the Library Manager, independent of the
  // Library tree's own hidden list). Admins still see the hits, exactly
  // like the admin-only grantha filter beside it in render().
  var gsSearchHidden = null;
  // The same file also carries `moves` and the go-live `shelf`. Search hits
  // are keyed by a grantha's REAL taxonomy slug, while the shelf is written
  // in DISPLAY paths (what the Library drawer shows, after moves) -- so a
  // hit has to be mapped through `moves` before the shelf can judge it.
  // Without that, searching would happily return every SetuTila verse the
  // drawer is hiding, which is the one leak that would make the whole
  // go-live shelf pointless.
  var gsMoves = {};
  try {
    fetch(new URL('admin/config/library-overrides.json', GS_ROOT).href, { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (ov) {
        gsSearchHidden = (ov && Array.isArray(ov.searchHidden)) ? ov.searchHidden : [];
        gsMoves = (ov && ov.moves && typeof ov.moves === 'object') ? ov.moves : {};
        // role-access.js owns the shelf check; on the reader library.js has
        // already handed it the config, but ashtadhyayi.html/dhatu.html load
        // neither, so this hands it over there. Idempotent either way.
        if (typeof window.dgeSetShelfConfig === 'function') window.dgeSetShelfConfig(ov && ov.shelf);
      })
      .catch(function () { gsSearchHidden = []; });
  } catch (e) { gsSearchHidden = []; }

  // Mirrors dgeEffectiveDisplayPath() in library.js: longest matching source
  // prefix wins, so moving a deep subfolder isn't shadowed by a move of one
  // of its ancestors.
  function gsDisplayPath(realSlug) {
    var best = null;
    Object.keys(gsMoves).forEach(function (src) {
      if (realSlug === src || realSlug.indexOf(src + '/') === 0) {
        if (!best || src.length > best.length) best = src;
      }
    });
    if (!best) return realSlug;
    var dest = gsMoves[best];
    var rel = realSlug.slice(best.length).replace(/^\//, '');
    return dest ? (rel ? dest + '/' + rel : dest) : rel;
  }

  function gsIsSearchHiddenHit(h) {
    var g = (h && h.grantha) || '';
    if ((gsSearchHidden || []).some(function (p) { return g === p || g.indexOf(p + '/') === 0; })) return true;
    if (typeof window.dgeIsOffShelf === 'function' && window.dgeIsOffShelf(gsDisplayPath(g))) return true;
    return false;
  }

  function ensureIndex() {
    if (!idxPromise) {
      if (!window.DGESearch) { alert('Search scripts not loaded (need dge-search.js).'); return null; }
      idxPromise = window.DGESearch.create(INDEX_BASE).catch(function (e) {
        idxPromise = null;
        // Guarded: a prefetch call (see prefetchManifest()) can reach this
        // catch before build() has ever run, when #dge-gs-results doesn't
        // exist yet -- writing to it unconditionally would throw a second,
        // unrelated error on top of the real one.
        var el = document.getElementById('dge-gs-results');
        if (el) {
          el.innerHTML = '<div class="dge-gs-hint">Could not load the search index at "' + INDEX_BASE + '". Generate it with build_search_index.py and commit dge/search_index/.</div>';
        }
        throw e;
      });
    }
    return idxPromise.then(function (idx) {
      gsEngineRef = idx;   // feeds the suggestion candidates (gsCandidates)
      populateScope(idx);
      return idx;
    });
  }

  // ---- Library-tree scope picker ----------------------------------------
  // The tree only comes from the index's own manifest (every grantha's
  // slug is a slash path -- section/work/.../grantha), so the popup starts
  // as just "Everything" and fills in once ensureIndex() resolves. Guarded
  // so a second open() in the same page load doesn't rebuild it.
  function populateScope(idx) {
    var treeEl = document.getElementById('dge-gs-scope-tree');
    if (!treeEl || treeEl.getAttribute('data-populated')) return;
    var granthas = (idx && idx.granthas) || [];
    if (!granthas.length) return;
    treeEl.setAttribute('data-populated', '1');
    scopeTreeData = buildScopeTreeData(granthas);
    renderScopeChildren(treeEl, scopeTreeData, 0);
    refreshScopeRows();
  }

  // slugs -> nested {seg, path, children:{}, order:[], n, title?}. `n`
  // counts granthas under each node (shown beside expandable rows);
  // `title` is set on the node a grantha's full slug lands on, so a leaf
  // can show its real display title ("Sumadhva Vijaya सर्गः 1") instead of
  // a re-prettified slug segment.
  function buildScopeTreeData(granthas) {
    var root = { children: {}, order: [], n: 0 };
    granthas.forEach(function (g) {
      var segs = String(g.slug || '').split('/');
      var node = root, cum = '';
      root.n++;
      for (var i = 0; i < segs.length; i++) {
        cum = cum ? cum + '/' + segs[i] : segs[i];
        var ch = node.children[segs[i]];
        if (!ch) {
          ch = node.children[segs[i]] = { seg: segs[i], path: cum, children: {}, order: [], n: 0 };
          node.order.push(segs[i]);
        }
        ch.n++;
        if (i === segs.length - 1) ch.title = g.title;
        node = ch;
      }
    });
    return root;
  }

  function scopeNodeLabel(node) {
    var kids = node.order.length;
    if (!kids && node.title && node.title !== node.seg) return node.title;
    return taxonomyLabel(node.seg);
  }

  // Renders ONE level of children into `container`; each expandable row
  // gets an (initially empty) kids <div> whose own children render on the
  // first expand -- 1,200 granthas across ~3,000 tree nodes would be a lot
  // of DOM to build for a popup most readers only skim the top of.
  function renderScopeChildren(container, node, depth) {
    node.order.slice().sort(function (a, b) {
      return scopeNodeLabel(node.children[a]).localeCompare(scopeNodeLabel(node.children[b]));
    }).forEach(function (seg) {
      var ch = node.children[seg];
      var hasKids = ch.order.length > 0;
      var label = scopeNodeLabel(ch);
      scopeLabelByPath[ch.path] = label;
      var row = document.createElement('div');
      row.className = 'dge-gs-tree-row';
      row.setAttribute('data-path', ch.path);
      row.style.paddingLeft = (8 + depth * 16) + 'px';
      row.innerHTML =
        '<span class="dge-gs-tree-exp">' + (hasKids ? '▸' : '') + '</span>' +
        '<span class="dge-gs-tree-box">✓</span>' +
        '<span class="dge-gs-tree-label">' + esc(label) + '</span>' +
        (hasKids ? '<span class="dge-gs-tree-n">' + ch.n + '</span>' : '');
      container.appendChild(row);
      var kidsEl = null;
      if (hasKids) {
        kidsEl = document.createElement('div');
        kidsEl.className = 'dge-gs-tree-kids';
        container.appendChild(kidsEl);
      }
      row.addEventListener('click', function (e) {
        if (hasKids && e.target.closest('.dge-gs-tree-exp')) {
          var opening = !kidsEl.classList.contains('openk');
          if (opening && !kidsEl.getAttribute('data-rendered')) {
            kidsEl.setAttribute('data-rendered', '1');
            renderScopeChildren(kidsEl, ch, depth + 1);
            refreshScopeRows();
          }
          kidsEl.classList.toggle('openk', opening);
          row.querySelector('.dge-gs-tree-exp').textContent = opening ? '▾' : '▸';
          return;
        }
        toggleScope(ch.path);
      });
    });
  }

  // Selection semantics: scopeSel is a flat list of OR'd path prefixes.
  // Selecting a node prunes any already-selected DESCENDANTS (now
  // redundant); a node whose ancestor is already selected is shown as
  // covered (dimmed ✓) and toggling it is a no-op -- deselect the
  // ancestor (chip or row) to narrow.
  function toggleScope(path) {
    var i = scopeSel.indexOf(path);
    if (i !== -1) {
      scopeSel.splice(i, 1);
    } else {
      for (var p = 0; p < scopeSel.length; p++) {
        if (path.indexOf(scopeSel[p] + '/') === 0) return;
      }
      scopeSel = scopeSel.filter(function (sp) {
        return !(sp === path || sp.indexOf(path + '/') === 0);
      });
      scopeSel.push(path);
    }
    scopeChanged();
  }
  function clearScope() {
    if (!scopeSel.length) return;
    scopeSel = [];
    scopeChanged();
  }
  function scopeChanged() {
    refreshScopeRows();
    renderScopeChips();
    window.dgeGsRetry();
  }

  function refreshScopeRows() {
    var pop = document.getElementById('dge-gs-section-pop');
    if (!pop) return;
    Array.prototype.forEach.call(pop.querySelectorAll('.dge-gs-tree-row[data-path]'), function (row) {
      var path = row.getAttribute('data-path');
      var sel = scopeSel.indexOf(path) !== -1;
      var cov = false;
      if (!sel) {
        for (var p = 0; p < scopeSel.length; p++) {
          if (path.indexOf(scopeSel[p] + '/') === 0) { cov = true; break; }
        }
      }
      row.classList.toggle('sel', sel);
      row.classList.toggle('cov', cov);
    });
    var all = document.getElementById('dge-gs-scope-all');
    if (all) all.classList.toggle('sel', !scopeSel.length);
    var btn = document.getElementById('dge-gs-section-btn');
    if (btn) {
      btn.textContent = (!scopeSel.length ? 'Everything'
        : scopeSel.length === 1 ? scopeChipLabel(scopeSel[0])
        : scopeSel.length + ' targets') + ' ▾';
    }
  }

  // Chip text: a real display title stands alone; a generic slug-segment
  // label ("mula", a bare sarga) gets its parent prefixed so two chips
  // from different works never read identically.
  function scopeChipLabel(path) {
    var segs = path.split('/');
    var label = scopeLabelByPath[path] || taxonomyLabel(segs[segs.length - 1]);
    if (label !== taxonomyLabel(segs[segs.length - 1])) return label;
    if (segs.length > 1) return taxonomyLabel(segs[segs.length - 2]) + ' › ' + label;
    return label;
  }

  // The selected targets live HERE, under the search bar, not inside the
  // drop-down (project-lead ask, 31 Aug 2026) -- always visible while
  // results render, each removable on its own, one tap clears all.
  function renderScopeChips() {
    var box = document.getElementById('dge-gs-scope-chips');
    if (!box) return;
    box.innerHTML = '';
    if (!scopeSel.length) { box.hidden = true; return; }
    box.hidden = false;
    scopeSel.forEach(function (path) {
      var chip = document.createElement('span');
      chip.className = 'dge-gs-scope-chip';
      chip.title = path;
      var lbl = document.createElement('span');
      lbl.textContent = scopeChipLabel(path);
      var x = document.createElement('b');
      x.textContent = '✕';
      x.setAttribute('role', 'button');
      x.setAttribute('aria-label', 'Remove ' + path + ' from search scope');
      x.addEventListener('click', function () { toggleScope(path); });
      chip.appendChild(lbl);
      chip.appendChild(x);
      box.appendChild(chip);
    });
    if (scopeSel.length > 1) {
      var clear = document.createElement('button');
      clear.type = 'button';
      clear.className = 'dge-gs-scope-clear';
      clear.textContent = 'search everything';
      clear.addEventListener('click', clearScope);
      box.appendChild(clear);
    }
  }

  // `query` is optional. The word popover in intellisense.js passes the word
  // the reader tapped, so "where else does this occur" opens already
  // searching rather than asking them to retype it. Called with nothing, this
  // behaves exactly as before.
  // Reported live (screenshots): tapping "Search Library" from a word
  // selection did nothing on the first tap, then on the second tap the
  // overlay opened, results appeared for under a second, then the page
  // immediately navigated away to an unrelated grantha the reader never
  // clicked -- for the SAME query, every time. Root cause: the word-tools
  // buttons fire on pointerdown (see ai.js's own comment on
  // dgeApplyWordSelectionHighlight for the first-tap half of this same
  // report), so open() can run and a result row can render at that exact
  // screen position WHILE the triggering tap is still completing -- the
  // trailing compatibility click of that same physical gesture then lands
  // on whatever now occupies that spot, which is a real result row with a
  // real onclick. Guarding renderRows()'s row.onclick against firing within
  // this short a window of open() blocks exactly that stray same-gesture
  // click without adding any perceptible delay to a reader's own,
  // deliberate later tap.
  var lastOpenAt = 0;
  // 600, not the original 400: on a busy phone the overlay build + index
  // warm-up can delay the same gesture's trailing click past 400ms of
  // lastOpenAt (the backdrop-close symptom still reproduced "once or
  // twice" at 400). Nothing a reader deliberately taps exists that early
  // -- results take longer than this to even render -- so the wider
  // window costs no real interaction.
  var GHOST_CLICK_GUARD_MS = 600;

  function open(query) {
    build();
    document.getElementById('dge-gs-overlay').classList.add('open');
    lastOpenAt = Date.now();
    ensureIndex();
    var input = document.getElementById('dge-gs-input');
    if (query && typeof query === 'string') {
      input.value = query;
      // onType is debounced against typing; dispatching the event it already
      // listens for keeps one code path for "the query changed".
      input.dispatchEvent(new Event('input'));
    }
    setTimeout(function () { input.focus(); }, 30);
  }
  function close() { var o = document.getElementById('dge-gs-overlay'); if (o) o.classList.remove('open'); }

  // Detects which of the OTHER Brahmic scripts this app already offers as a
  // reading script (config.js's SCRIPT_OPTIONS -- Kannada/Telugu/Tamil/
  // Malayalam/Bengali/Odia) a query is written in, by Unicode block, the
  // same way the pre-existing Devanagari check above does. Project-lead
  // ask: a reader should be able to type a query in ANY of those scripts
  // (or English capitals/diacritics/plain SLP1) and "auto" should just work,
  // not silently mis-guess it as Roman IAST/SLP1 (which garbled anything
  // typed in an actual Indic script other than Devanagari -- confirmed live,
  // this used to hand Telugu/Tamil input straight to the SLP1 folder).
  // Sanscript.js already has real conversion tables for every one of these
  // (transliteration.js already round-trips through them for the reading
  // script itself) -- this only adds the DETECTION queryOpts()/
  // queryToDevanagari() were missing for a query, not a new engine.
  var BRAHMIC_SCRIPT_RANGES = [
    ['bengali', /[ঀ-৿]/],
    ['oriya', /[଀-୿]/],
    ['tamil', /[஀-௿]/],
    ['telugu', /[ఀ-౿]/],
    ['kannada', /[ಀ-೿]/],
    ['malayalam', /[ഀ-ൿ]/]
  ];
  function detectBrahmicScript(input) {
    for (var i = 0; i < BRAHMIC_SCRIPT_RANGES.length; i++) {
      if (BRAHMIC_SCRIPT_RANGES[i][1].test(input)) return BRAHMIC_SCRIPT_RANGES[i][0];
    }
    return null;
  }

  function queryOpts(input) {
    if (/[ऀ-ॿ]/.test(input)) return { scheme: 'devanagari' };
    var scheme = currentScheme;
    var detected = detectBrahmicScript(input);
    if (scheme === 'auto') scheme = detected || (/[āīūṛṝḷṁṃḥśṣṅñṭḍṇ]/i.test(input) ? 'iast' : 'slp1');
    if (scheme === 'slp1' || scheme === 'devanagari') return { scheme: scheme };
    try { if (window.Sanscript) return { slp1: window.Sanscript.t(input, scheme, 'slp1') }; } catch (e) {}
    return { scheme: 'slp1' };
  }

  // "Exact spelling only" (24 Aug 2026, the backlog item deferred when the
  // rest of this session's search work shipped -- the project lead's
  // go-ahead: "Sure. Go ahead. No problem."). The index itself only ever
  // stores trigrams over the PHONETICALLY FOLDED key (see
  // SEARCH_ARCHITECTURE.md/dge-normalize.js) -- there is no separate
  // literal-spelling index to query, and building one would mean
  // rebuilding the 330MB artifact, exactly the architecture change this
  // whole pass was told not to make. What the index DOES already store,
  // per unit, is the real Devanagari snippet text (row.s / h.snippet) --
  // so "exact" is implemented as a client-side POST-filter on the results
  // a normal fuzzy search already fetched, same as every other filter chip
  // in this file (type/category/siddhanta/keyword), never a new query.
  // Converts the query to Devanagari the same way queryOpts() above
  // detects its script, but to 'devanagari' instead of 'slp1' -- the
  // snippet's own stored script -- so the comparison is a literal
  // character-for-character containment check, not a folded one.
  function queryToDevanagari(input) {
    input = String(input || '');
    // Kannada/Telugu/Malayalam QUERIES (1 Sep 2026, project-lead report:
    // ಮೋದೇತ typed into Search Library found nothing while मोदेत did):
    // these blocks share Devanagari's layout codepoint-for-codepoint, so
    // transpose them directly via the same fold the exact-filter and the
    // index builder already use — no dependence on the scheme picker
    // (which has no Kannada entry) or on Sanscript having loaded.
    if (/[ఀ-ൿ]/.test(input)) input = dgeGsFoldIndic(input);
    if (/[ऀ-ॿ]/.test(input)) return input.trim();
    var scheme = currentScheme;
    var detected = detectBrahmicScript(input);
    if (scheme === 'auto') scheme = detected || (/[āīūṛṝḷṁṃḥśṣṅñṭḍṇ]/i.test(input) ? 'iast' : 'slp1');
    try { if (window.Sanscript) return window.Sanscript.t(input, scheme, 'devanagari').trim(); } catch (e) {}
    return input.trim();
  }

  // Orthographic-equivalence normalization for the exact-spelling
  // comparison -- "exact" means the same WORD as written, not the same
  // bytes. Three folds, applied to BOTH sides in applyFilters() so none
  // can introduce a one-directional false negative:
  //  * NFC -- an Android IME can emit an unnormalized codepoint sequence
  //    visually identical to the composed form (reported live);
  //  * strip zero-width joiner/non-joiner (U+200D/U+200C) -- IME ligature
  //    hints, byte-different, invisible;
  //  * anusvara <-> homorganic class nasal (कान्ताय <-> कांताय): every
  //    Sanskrit editor treats these as interchangeable spellings of the
  //    SAME word, and hiding one from a query typed the other way is a
  //    false negative a reader experiences as a missing verse. Class
  //    nasal + virama before a consonant folds to anusvara (ं).
  // Everything else stays byte-strict: vowel length, sibilant identity
  // (श/ष/स), visarga, gemination -- those distinguish genuinely different
  // words, which is exactly what "Exact spelling only" promises to honor.
  // Kannada / Telugu / Malayalam blocks share Devanagari's layout
  // codepoint-for-codepoint, so a plain block transposition maps them onto
  // Devanagari EXACTLY (same fold build_search_index.py applies at index
  // time -- the two must stay twins). Reported live, 31 Aug 2026: the
  // Kannada Yuktimallika's "ಭಕ್ತ್ಯಾ ಸ್ತುತ್ಯಾ" IS an exact hit for स्तुत्या --
  // identical orthography, different script -- but the Devanagari-substring
  // check below could never see it, so genuinely exact Dāsa-Sāhitya hits
  // were hidden while their category chip still advertised them.
  var DGE_GS_INDIC_FOLD_BLOCKS = [0x0C80, 0x0C00, 0x0D00]; // Kannada, Telugu, Malayalam
  function dgeGsFoldIndic(s) {
    var out = '';
    for (var i = 0; i < s.length; i++) {
      var cp = s.charCodeAt(i), ch = s[i];
      for (var b = 0; b < DGE_GS_INDIC_FOLD_BLOCKS.length; b++) {
        var base = DGE_GS_INDIC_FOLD_BLOCKS[b];
        if (cp >= base && cp < base + 0x80) { ch = String.fromCharCode(cp - base + 0x0900); break; }
      }
      out += ch;
    }
    return out;
  }
  function dgeGsExactNormalize(s) {
    return dgeGsFoldIndic(String(s || '').normalize('NFC')).replace(/[‌‍]/g, '')
      .replace(/[ङञणनम]्(?=[क-ह])/g, 'ं');
  }
  // Does a hit pass "Exact spelling only"? Normally: the normalized query
  // appears verbatim in the stored snippet. One honest exception (1 Sep
  // 2026, गुरुराजेन report): the stored snippet is the unit's first ~4,000
  // chars (build_search_index.py snippet()), so a word-index hit whose
  // match sits DEEPER in a mega-unit fails the substring check through no
  // fault of the spelling. When the snippet is visibly at that cap and the
  // hit came from the exact word index, absence from the excerpt is
  // incomplete evidence, not counter-evidence -- keep the hit.
  function dgeGsPassesExact(h, qExact) {
    if (h.snippet && dgeGsExactNormalize(h.snippet).indexOf(qExact) !== -1) return true;
    return !!(h.snippet && h.snippet.length >= 3900 &&
              h.via && h.via.indexOf('word-index') === 0);
  }

  // Shared by go() and the per-hit taxonomy crumbs below: the reader's own
  // URL from wherever this search happens to be running (ashtadhyayi.html
  // since the corpus-usage button, or any other page that loads this file)
  // — page-relative navigation would otherwise produce e.g.
  // ashtadhyayi.html?path=..., which that page ignores.
  function readerBase() {
    var path = window.location.pathname;
    if (!/\/(index\.html)?$/.test(path)) {
      path = path.replace(/[^/]*$/, 'index.html');
    }
    return path;
  }

  function go(slug, unit, hl) {
    // ?path= is the READER's contract.
    var p = readerBase() + '?path=' + slug;
    if (unit) p += '&jumpShloka=' + encodeURIComponent(unit);
    // core.js reads this as ?hl= (see dgeResolveQuickJumpTarget's caller) to
    // highlight the searched word/phrase on arrival -- Devanagari already,
    // same script the reader's own text is in, so it can be matched against
    // .dge-word spans without a scheme conversion on the far side. Reported
    // live: "that Vastu is not highlighted in any of the text" once a
    // search result was actually opened.
    if (hl) p += '&hl=' + encodeURIComponent(hl);
    window.location.href = p;
  }

  // Real taxonomy hierarchy per result (25 Aug 2026 project-lead ask: "in
  // the Kosha search, all sutras must be backlinked" turned out to have a
  // sibling ask already on record for global search too -- every hit's
  // title/category/score row said WHAT matched and roughly where, but
  // never showed or let a reader follow the actual taxonomy path a hit
  // lives at (h.grantha is that real path -- see taxonomyLabel()'s own
  // comment above for why the slug, not h.category, is the source of
  // truth). Every ancestor segment is a real link to the Library browser
  // drilled to that node (library.js's dgeOpenLibraryToPath, reached via
  // core.js's ?libraryPath= handling -- the SAME mechanism layer-stitch.js's
  // lineage strip now uses, not a second one invented here). The leaf
  // segment (the hit's own grantha) stays a plain "you are here" label,
  // matching that same convention -- the row itself is already the click
  // target to open it (see renderRows()'s own row.onclick).
  function taxonomyCrumbsHtml(grantha, title) {
    var segs = String(grantha || '').split('/').filter(Boolean);
    if (!segs.length) return '';
    var base = readerBase();
    var cum = '', out = [];
    segs.forEach(function (seg, i) {
      cum = cum ? cum + '/' + seg : seg;
      if (i === segs.length - 1) {
        out.push('<span class="dge-gs-crumb-current">' + esc(title || taxonomyLabel(seg)) + '</span>');
      } else {
        out.push('<a class="dge-gs-crumb-seg" href="' + esc(base + '?libraryPath=' + encodeURIComponent(cum)) + '">' + esc(taxonomyLabel(seg)) + '</a>');
      }
    });
    return '<div class="dge-gs-crumbs">' + out.join('<span class="dge-gs-crumb-sep">›</span>') + '</div>';
  }

  // A real query against this index is a manifest fetch plus several
  // postings-bucket and grantha-shard round trips through jsdelivr --
  // measured at 10+ seconds for a common word on a cold cache, not the
  // sub-second feel the debounce below implies. With no state shown while
  // that runs, the reader stares at the same "Type a word..." placeholder
  // the whole time, which reads as "this button does nothing" -- exactly
  // the bug report this responds to -- rather than as a slow search. The
  // "Searching..." line below is the fix; render()'s own "No matches."
  // already covers the empty-result end of this, so only the WAITING gap
  // was silent.
  // Real elapsed time, not just a step counter -- the project lead's explicit
  // complaint was that "N of M" alone doesn't say how many actual SECONDS a
  // cold-cache query (10+, see this function's own header comment) is
  // taking, which reads as stalled rather than slow. Ticks the visible label
  // independently of onProgress's own updates (which only fire when a fetch
  // batch settles, sometimes seconds apart) so the clock itself never looks
  // frozen. One live timer at a time -- clearElapsedTimer() is called before
  // starting a new one and on every terminal state (success or failure) so a
  // stale interval from a replaced query can't keep ticking into a label
  // that no longer belongs to it.
  var elapsedTimer = null;
  function clearElapsedTimer() { if (elapsedTimer) { clearInterval(elapsedTimer); elapsedTimer = null; } }
  function startElapsedTimer(results) {
    clearElapsedTimer();
    var startedAt = Date.now();
    elapsedTimer = setInterval(function () {
      var el = results.querySelector('.dge-gs-elapsed');
      if (!el) { clearElapsedTimer(); return; }
      el.textContent = ((Date.now() - startedAt) / 1000).toFixed(1) + 's';
    }, 100);
    return startedAt;
  }

  // ---- compound-interior extension (dge-search.js searchCompound()) ----
  // The word index finds whole words and compound-INITIAL occurrences; a
  // query word buried mid/end-compound (नीलकान्ताय for a कान्ताय query --
  // "a match is a match, beginning, middle or end", the project lead's
  // direct ask, 30 Aug 2026) needs the vocabulary grep. That costs a
  // one-time ~10MB word-list download (then HTTP-cached against the
  // immutable pinned URL, so effectively free forever after), which is why
  // it is NOT silently auto-fired on a reader's mobile data the first
  // time: the results footer offers it as a clearly-priced one-tap action,
  // and once the list has been fetched once on this device it runs
  // automatically on every eligible query after that.
  var searchSeq = 0;                    // bumped per query; stale async work checks it
  var compoundState = null;             // null | 'offer' | 'running' | 'done'
  var compoundAdded = 0, compoundCtx = null;
  var compoundDegraded = false;         // the scan itself lost fetches (see dge-search.js FETCH_ERR)

  function compoundEligible(qraw) {
    try {
      var norm = (window.DGENorm || {}).normalizeQuery;
      if (!norm) return false;
      var nq = norm(qraw, queryOpts(qraw));
      if (!nq.pkey) return false;
      // same tokenizer contract as dge-search.js wordTokens()
      var toks = nq.pkey.split(/[^0-9A-Za-zॐ]+/).filter(function (t) { return t && !/^[0-9]+$/.test(t); });
      return toks.length === 1 && toks[0].length >= 4;
    } catch (e) { return false; }
  }
  function vocabAlreadyFetched(idx) {
    if (idx && typeof idx.vocabLoaded === 'function' && idx.vocabLoaded()) return true;
    try { return localStorage.getItem('dge_gs_vocab_fetched') === '1'; } catch (e) { return false; }
  }
  function compoundFooterHtml() {
    if (compoundState === 'offer') {
      return '<div class="dge-gs-hint"><button type="button" class="dge-gs-chip" onclick="window.dgeGsRunCompound()">' +
        '🔎 Search inside compound words too</button>' +
        '<span style="opacity:.6"> one-time word-list download (~10 MB), instant afterwards</span></div>';
    }
    if (compoundState === 'running') {
      return '<div class="dge-gs-hint"><span class="dge-gs-spinner" aria-hidden="true"></span>' +
        '<span id="dge-gs-compound-progress">Scanning the word list…</span></div>';
    }
    if (compoundState === 'done') {
      return '<div class="dge-gs-hint">' + (compoundAdded
        ? 'Included ' + compoundAdded + ' match' + (compoundAdded === 1 ? '' : 'es') + ' found inside compound words.'
        : 'No further matches inside compound words.')
        // An honest asterisk when the scan itself lost fetches: "no
        // further matches" would otherwise claim an exhaustive sweep the
        // connection didn't actually allow.
        + (compoundDegraded
          ? ' ⚠ The connection hiccuped during the scan, so it may be incomplete — <button type="button" class="dge-gs-chip" onclick="window.dgeGsRetry()">search again</button> to redo it.'
          : '') + '</div>';
    }
    return '';
  }
  function runCompound(idx) {
    if (!compoundCtx || compoundCtx.seq !== searchSeq) return;
    compoundState = 'running';
    if (lastHits) applyFilters();
    var mySeq = compoundCtx.seq;
    var opts = Object.assign({}, compoundCtx.opts, {
      onProgress: function (stage, done, total) {
        var el = document.getElementById('dge-gs-compound-progress');
        if (!el) return;
        el.textContent = stage === 'vocab'
          ? 'Scanning the word list… (' + done + ' of ' + total + ')'
          : 'Opening matched texts… (' + done + ' of ' + total + ')';
      }
    });
    idx.searchCompound(compoundCtx.q, opts).then(function (hits) {
      if (mySeq !== searchSeq) return; // reader moved on to another query
      try { localStorage.setItem('dge_gs_vocab_fetched', '1'); } catch (e) {}
      var seen = {};
      (lastHits || []).forEach(function (h) { seen[h.grantha + '#' + h.unit] = 1; });
      var fresh = hits.filter(function (h) { return !seen[h.grantha + '#' + h.unit]; });
      compoundAdded = fresh.length;
      compoundState = 'done';
      compoundDegraded = !!hits.degraded;
      if (fresh.length) {
        var partial = lastHits ? lastHits.partial : false;
        var degraded = (lastHits ? lastHits.degraded : false) || hits.degraded;
        lastHits = (lastHits || []).concat(fresh);
        lastHits.partial = partial;
        lastHits.degraded = degraded;
        buildFilterBar(lastHits);
      }
      applyFilters();
    }).catch(function () {
      if (mySeq !== searchSeq) return;
      compoundState = null;
      applyFilters();
    });
  }
  window.dgeGsRunCompound = function () {
    var p = ensureIndex(); if (!p) return;
    p.then(function (idx) { runCompound(idx); });
  };

  // Re-fires the current query in place -- wired to the "Try again"
  // buttons the degraded-state notes render. Meaningful because
  // dge-search.js never caches a FAILED fetch (see its FETCH_ERR): a
  // retry genuinely refetches the pieces the connection dropped, rather
  // than replaying the same holes out of the session cache.
  window.dgeGsRetry = function () {
    var inp = document.getElementById('dge-gs-input');
    if (inp && inp.value.trim()) inp.dispatchEvent(new Event('input'));
  };

  function onType(e) {
    var q = e.target.value.trim();
    clearTimeout(debounce);
    clearElapsedTimer();
    searchSeq++;
    compoundState = null; compoundAdded = 0; compoundCtx = null; compoundDegraded = false;
    var results = document.getElementById('dge-gs-results');
    if (!q) { results.innerHTML = gsIdleHtml(); return; }
    results.innerHTML = gsSuggestHtml(q) +
      '<div class="dge-gs-hint"><span class="dge-gs-spinner" aria-hidden="true"></span>' +
      '<span class="dge-gs-searching-label">Searching…</span>' +
      ' <span class="dge-gs-elapsed">0.0s</span></div>' +
      '<div class="dge-gs-progress"><i class="dge-gs-progress-bar"></i></div>';
    startElapsedTimer(results);
    debounce = setTimeout(function () {
      var p = ensureIndex(); if (!p) return;
      lastQueryDeva = queryToDevanagari(q);
      var searchStartedAt = startElapsedTimer(results); // real search work starts now, not at the first keystroke
      // Two real stages, in order: fetching the rarest trigrams' postings
      // buckets, then opening the candidate granthas' unit shards -- see
      // dge-search.js's search()/allWithProgress(). Split the bar 50/50
      // between them (their relative sizes aren't comparable -- one counts
      // small index files, the other whole grantha shards -- so weighting
      // by byte size isn't something either side knows); each stage still
      // reports its own real "done of total" underneath the label. A stale
      // callback from a query the reader has since replaced finds its
      // elements already gone (results redrawn) and is a no-op.
      var onProgress = function (stage, done, total) {
        var label = results.querySelector('.dge-gs-searching-label');
        var bar = results.querySelector('.dge-gs-progress-bar');
        if (!label || !bar) return;
        var half = total ? (done / total) * 50 : 0;
        if (stage === 'postings') {
          label.textContent = 'Searching… fetching index (' + done + ' of ' + total + ')';
          bar.style.width = half + '%';
        } else {
          label.textContent = 'Searching… opening texts (' + done + ' of ' + total + ')';
          bar.style.width = (50 + half) + '%';
        }
      };
      // Reported live: कान्ताय's only genuine exact matches in the whole
      // corpus sit under DvaitaVedanta, which render() below already hides
      // post hoc from a non-admin reader -- but by then the shard-open
      // budget (dge-search.js's MAX_SHARDS/MAX_EXACT_SHARDS) had already
      // been spent opening those same granthas' shards, leaving no room for
      // a genuinely visible match elsewhere to even be considered. Passing
      // the same admin-only prefixes through as excludeGranthaPrefixes lets
      // dge-search.js drop them BEFORE they count against that budget, for
      // a reader who won't see them rendered anyway.
      var excludePrefixes = dgeSearchIsAdmin() ? [] : ADMIN_ONLY_GRANTHA_PREFIXES;
      var searchOpts = Object.assign({ limit: 30, includeGranthaPrefixes: scopeSel.slice(), onProgress: onProgress, excludeGranthaPrefixes: excludePrefixes }, queryOpts(q));
      // "Exact spelling only" ON (the default) routes through the word-level
      // EXACT index (dge-search.js searchExact()) -- a direct word->units
      // lookup with no shard-open budget and no candidate ties, the answer
      // to the reported "कान्ताय exists verbatim in Sumadhva Vijaya but an
      // unscoped search never returns it" (its trigram fragments tie with
      // ~48k unrelated units; no budget reaches the real one). The trigram
      // fuzzy path stays for exact=OFF, typo-tolerance being its actual
      // job.
      //
      // An EMPTY exact answer is no longer silently handed to the fuzzy
      // path (reported live, 31 Aug 2026: the same word searched in Roman
      // and Devanagari minutes apart "showed different results" -- one
      // run's word-index answer next to another run's fuzzy answer, the
      // swap decided invisibly by whichever section fetch a flaky mobile
      // connection happened to drop). Now:
      //   - empty AND degraded (a fetch failed): retry once -- the failed
      //     pieces were never cached (dge-search.js FETCH_ERR), so the
      //     retry genuinely refetches; still degraded-empty after that
      //     renders an honest "connection hiccuped, try again" note.
      //   - empty and CLEAN: that IS the exact answer. Fuzzy only fills in
      //     when the published index predates the words/ tree entirely
      //     (no word buckets exist to consult), never as a silent
      //     different-looking substitute.
      var useExact = filterState.exact;
      var mySeq = searchSeq;
      var indexHasWords = function (idx) {
        var m = (idx && idx.manifest) || {};
        return !!(m.wordBucketDeepen || m.vocabChunks);
      };
      p.then(function (idx) {
         if (!useExact) {
           return idx.search(q, searchOpts).then(function (hits) { hits._idx = idx; return hits; });
         }
         return idx.searchExact(q, searchOpts).then(function (hits) {
           if (!hits.length && hits.degraded && mySeq === searchSeq) {
             return idx.searchExact(q, searchOpts);
           }
           return hits;
         }).then(function (hits) {
           if (!hits.length && !hits.degraded && !indexHasWords(idx)) {
             return idx.search(q, searchOpts);
           }
           return hits;
         }).then(function (hits) { hits._idx = idx; return hits; });
       })
       .then(function (hits) {
         // A search the reader has since replaced (typed on, switched
         // script or scope) must NOT overwrite the newer query's results
         // when it finally lands: with the shard phase capped at 8s, a
         // slow older run can resolve SECONDS after the newer one already
         // rendered -- reported live as "in span of few seconds it
         // changes the results". The newer query bumped searchSeq, so
         // this run just stands down.
         if (mySeq !== searchSeq) return;
         clearElapsedTimer();
         lastSearchElapsedMs = Date.now() - searchStartedAt;
         var idx = hits._idx; delete hits._idx;
         if (!hits.length && hits.degraded) {
           // Nothing came back AND a fetch failed (even after the exact
           // path's one retry): saying "no matches" here would be a lie
           // about the corpus when the truth is about the connection.
           lastSearchElapsedMs = null;
           // The previous query's filter bar (and its counts) would sit
           // above this note as if it still applied -- it doesn't.
           var fb = document.getElementById('dge-gs-filterbar');
           if (fb) fb.style.display = 'none';
           var box = document.getElementById('dge-gs-results');
           if (box) {
             box.innerHTML = '<div class="dge-gs-hint">The connection hiccuped mid-search and parts of the index could not be fetched — this is not a "no matches" answer. ' +
               '<button type="button" class="dge-gs-chip" onclick="window.dgeGsRetry()">Try again</button></div>';
           }
           return;
         }
         render(hits, q);
         // Compound-interior extension: eligible single-word exact queries
         // continue into the vocabulary grep -- automatically when the word
         // list is already on this device, as a one-tap offer otherwise
         // (see the compoundState machinery above for why not silently).
         if (useExact && mySeq === searchSeq && compoundEligible(q)) {
           compoundCtx = { q: q, opts: searchOpts, seq: mySeq };
           if (idx && vocabAlreadyFetched(idx)) runCompound(idx);
           else { compoundState = 'offer'; if (lastHits) applyFilters(); }
         }
       })
       .catch(function () {
         clearElapsedTimer();
         // ensureIndex()'s own catch already writes a specific "could not
         // load the index" message and only fires on that one failure --
         // this covers every OTHER way the chain can reject (a posting or
         // shard fetch dying mid-search) so "Searching..." never just sits
         // there forever on a query that silently failed.
         var el = document.getElementById('dge-gs-results');
         if (el && el.innerHTML.indexOf('Searching') !== -1) {
           el.innerHTML = '<div class="dge-gs-hint">Search failed — check your connection and try again.</div>';
         }
       });
    }, 140);
  }

  // build_search_index.py now stores each unit's text up to 2000 chars
  // (was a fixed 140-char prefix), specifically so a match deeper into a
  // long commentary paragraph is actually IN the stored text somewhere —
  // but showing up to 2000 raw characters in one result row would be
  // unreadable. This slices a short, readable excerpt CENTERED on the
  // first place the query's own words actually appear, so what's shown is
  // the same text that gets highlighted, not an unrelated prefix. Falls
  // back to the plain prefix (today's behaviour) when no word is found in
  // this script — e.g. an IAST query against a Devanagari-only snippet,
  // a real but separate limitation this doesn't attempt to fix.
  function centerSnippet(text, q, radius) {
    radius = radius || 90;
    var words = (q || '').trim().split(/\s+/).filter(function (w) { return w.length >= 2; });
    var at = -1, matchLen = 0;
    for (var i = 0; i < words.length; i++) {
      var idx = text.toLowerCase().indexOf(words[i].toLowerCase());
      if (idx !== -1 && (at === -1 || idx < at)) { at = idx; matchLen = words[i].length; }
    }
    if (at === -1) return text.slice(0, radius * 2);
    var start = Math.max(0, at - radius);
    var end = Math.min(text.length, at + matchLen + radius);
    var out = text.slice(start, end);
    if (start > 0) out = '…' + out;
    if (end < text.length) out = out + '…';
    return out;
  }

  // Wraps whole-word, case-insensitive matches of the query's own words
  // (>=2 chars, so a stray single letter doesn't highlight half the
  // snippet) in <mark> — deliberately literal-substring, not aware of the
  // scheme normalization queryOpts() does for the search itself, since a
  // reader mainly wants to see the words they typed picked out of the
  // snippet they're already reading in that same script, not every
  // possible transliteration of a match found some other way.
  function highlightSnippet(escapedText, q) {
    var words = (q || '').trim().split(/\s+/).filter(function (w) { return w.length >= 2; });
    if (!words.length) return escapedText;
    var pattern = words.map(function (w) {
      return esc(w).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }).join('|');
    return escapedText.replace(new RegExp('(' + pattern + ')', 'gi'), '<mark class="dge-gs-hl">$1</mark>');
  }

  // Escapes quotes too: the output goes into attributes (data-slug="…") as
  // well as text, and a value containing a quote would close the attribute
  // early and let what follows parse as markup. Same defect CodeQL found on
  // kosha.js's licence tooltip.
  function esc(s) {
    return (s == null ? '' : String(s)).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  // Draws just the result rows for whatever hit list is passed (the full
  // search result, or a filtered slice of it) -- split out of render() so
  // the filter chips below can re-slice lastHits and redraw without a new
  // search.
  // "Found in 3.2s" / "Searched in 8.7s" -- shown once, on the render that
  // just completed a real search (not on a filter-chip re-render of the
  // same lastHits, which doesn't re-search and has nothing new to time).
  // Reset to null right after use so it can't get attached to a LATER
  // re-render of the same result set.
  function elapsedNoteHtml(zeroHits) {
    if (lastSearchElapsedMs == null) return '';
    var s = (lastSearchElapsedMs / 1000).toFixed(1) + 's';
    lastSearchElapsedMs = null;
    return '<div class="dge-gs-hint dge-gs-elapsed-note">' + (zeroHits ? 'Searched' : 'Found') + ' in ' + s + '.</div>';
  }

  function renderRows(hits, q, emptyMessage) {
    var box = document.getElementById('dge-gs-results');
    if (!hits || !hits.length) {
      // Zero hits on a capped sweep is not proof of absence: one long word
      // whose trigrams are all common can crowd its true source out of the
      // shard budget entirely (see dge-search.js's note on `partial`), and
      // adding a second word genuinely fixes that — so say it.
      var msg = esc(emptyMessage || 'No matches.');
      if (lastHits && lastHits.partial && !emptyMessage) {
        msg += ' The search could not sweep the whole library for this — a single long word matches too much of it faintly. Adding one more word from the same line usually finds it.';
      } else if (!emptyMessage && filterState.exact) {
        // A clean empty EXACT answer is exhaustive for whole words and
        // compound-initial forms (dge-search.js searchExact's partial=
        // false contract) -- so instead of a bare "No matches." that
        // reads like a shrug, say what would genuinely widen the net.
        msg += ' The word does not occur with this exact spelling as a whole or compound-initial word. If the spelling here may differ (sandhi, a variant form, a typo), turn off "Exact spelling only" above to search with tolerance.';
      }
      box.innerHTML = elapsedNoteHtml(true) + '<div class="dge-gs-hint">' + msg + '</div>' + compoundFooterHtml();
      return;
    }
    // A common word matches most of the corpus; the search stops after the
    // best few dozen granthas rather than opening all of them. Say so, so a
    // reader does not take a capped list for the whole of it.
    var note = elapsedNoteHtml(false)
      // A degraded run found real hits but KNOWS it lost fetches along
      // the way -- present what arrived, but never as the full answer
      // (the run-to-run inconsistency the project lead reported was
      // exactly these silently-passed-off partial runs).
      + (lastHits && lastHits.degraded
        ? '<div class="dge-gs-hint">⚠ The connection hiccuped mid-search — some matches may be missing from this list. ' +
          '<button type="button" class="dge-gs-chip" onclick="window.dgeGsRetry()">Search again</button></div>'
        : '')
      + (lastHits && lastHits.partial
        ? '<div class="dge-gs-hint">Best matches — the search stopped after the' +
          ' strongest few dozen texts rather than opening the whole library.' +
          ' A longer phrase narrows it.</div>'
        : '');
    box.innerHTML = note + hits.map(function (h) {
      // h.unit is a raw source-importer id (unit_0370, DV_5752, a verse
      // number...) -- real navigation state (kept in data-unit, below, for
      // go()/jumpShloka), but not something a reader needs to see, and the
      // project lead has separately asked that the app's own internal
      // references not surface the original source's own numbering
      // verbatim in the UI. No longer shown in the row itself.
      return '<div class="dge-gs-row" data-slug="' + esc(h.grantha) + '" data-unit="' + esc(h.unit) + '">' +
        '<div class="dge-gs-meta"><b>' + esc(h.title) + '</b><span>' + esc(h.category) + '</span><span>' + h.score.toFixed(2) + '</span></div>' +
        taxonomyCrumbsHtml(h.grantha, h.title) +
        '<div class="dge-gs-snip">' + highlightSnippet(esc(centerSnippet(h.snippet, q)), q) + '</div></div>';
    }).join('') + compoundFooterHtml();
    Array.prototype.forEach.call(box.querySelectorAll('.dge-gs-row'), function (row) {
      row.onclick = function (ev) {
        // See open()'s own comment on lastOpenAt/GHOST_CLICK_GUARD_MS: a
        // click landing here within this many ms of the overlay opening is
        // the trailing compatibility click of the SAME physical tap that
        // opened it, not a reader deliberately tapping a result row that
        // didn't exist yet when their gesture began.
        if (Date.now() - lastOpenAt < GHOST_CLICK_GUARD_MS) return;
        // A sutra reference inside the snippet (wired below) opens its own
        // popover on click; without this the row's own click-to-navigate
        // would also fire on the same tap, jumping to the grantha instead.
        if (ev.target.closest && ev.target.closest('.dge-sutra-ref')) return;
        // Same reasoning for a taxonomy crumb link: it's a real <a href>
        // navigating to the Library browser, not a proxy for "open this
        // hit" — letting the row handler also fire would race its own
        // window.location.href against the anchor's native navigation.
        if (ev.target.closest && ev.target.closest('.dge-gs-crumbs')) return;
        // A result the reader actually opened is a search worth remembering.
        var inpEl = document.getElementById('dge-gs-input');
        if (inpEl) gsPushHistory(inpEl.value);
        go(row.getAttribute('data-slug'), row.getAttribute('data-unit'), lastQueryDeva || q);
      };
    });
    // Sutra numbers appearing in a snippet get the same tappable popover
    // the reading view and Kosha already give them (js/intellisense.js) —
    // was Kosha-only; global corpus search snippets never got this.
    // entity-linker.js's cross-reference scan runs first for the same
    // "work name + number becomes one span" reason documented in its own
    // header comment and in render.js's equivalent pairing.
    if (typeof window.dgeScanForEntities === 'function') {
      try { window.dgeScanForEntities(box); } catch (e) {}
    }
    if (typeof window.dgeScanForSutras === 'function') {
      // Per-row, not once over the whole results box: intellisense.js's own
      // "always link, no cue word needed" trust list (CFG.alwaysLinkIn)
      // keys off window.currentGranthaSlug, which is what the READER is
      // showing -- meaningless here, since one results box mixes hits from
      // many granthas at once. Each row already carries its own hit's slug
      // (data-slug, used by the click-to-navigate handler above), so that's
      // checked per row instead. Same 'vedanga/vyakarana' prefix
      // intellisense.js trusts elsewhere -- a hit from Kāśikā or the
      // Aṣṭādhyāyī's own sūtrapāṭha cites bare "1.1.1"-shaped numbers with
      // no "सूत्र"/"पाणिनि" cue word nearby, same gap as Kosha's cards.
      Array.prototype.forEach.call(box.querySelectorAll('.dge-gs-row'), function (row) {
        var slug = row.getAttribute('data-slug') || '';
        try { window.dgeScanForSutras(row, { always: slug.indexOf('vedanga/vyakarana') === 0 }); } catch (e) {}
      });
    }
  }

  // Applies the current type/category/siddhanta/keyword filter state to
  // lastHits (never re-fetches -- see the comment on filterState above) and
  // redraws. Called on every filter chip click and every keystroke in the
  // refine box.
  function applyFilters() {
    if (!lastHits) return;
    var typeActive = filterState.type !== 'all';
    var catKeys = Object.keys(filterState.categories);
    var sidKeys = Object.keys(filterState.siddhanta);
    var kw = filterState.keyword.trim().toLowerCase();
    // Only actually filters when there's a real Devanagari string to check
    // against (lastQueryDeva) -- guards the edge case where conversion
    // failed and fell back to empty, which would otherwise hide everything.
    var exactActive = filterState.exact && !!lastQueryDeva;
    // Reported live: a query typed directly in Devanagari via an Android
    // IME still came back "No exact spelling matches" against results the
    // search itself had genuinely found containing that literal text --
    // confirmed live against the published index, several of the returned
    // hits DID contain the query as a byte-exact substring. An IME
    // composing conjuncts can emit a different (but visually identical)
    // codepoint sequence than the same text typed another way -- an
    // unnormalized Unicode form, or a stray zero-width joiner/non-joiner
    // used to force a particular conjunct rendering. Normalizing both
    // sides through the same NFC + zero-width-strip pass before comparing
    // makes the check robust to exactly that, without weakening what
    // "exact" means (still a real, literal, character-for-character
    // containment check -- just on the canonical form of both sides).
    var qExact = dgeGsExactNormalize(lastQueryDeva);
    var out = lastHits.filter(function (h) {
      if (typeActive && h.contentType !== filterState.type) return false;
      if (catKeys.length && filterState.categories[h.category] !== true) return false;
      if (sidKeys.length && filterState.siddhanta[siddhantaOf(h.grantha)] !== true) return false;
      if (kw && (h.title + ' ' + h.snippet).toLowerCase().indexOf(kw) === -1) return false;
      if (exactActive && !dgeGsPassesExact(h, qExact)) return false;
      return true;
    });
    var anyFilterActive = typeActive || catKeys.length || sidKeys.length || kw || exactActive;
    var emptyMsg = 'No matches.';
    if (anyFilterActive) {
      emptyMsg = exactActive
        ? 'No exact spelling matches among these results — try turning off "Exact spelling only" to see near matches too.'
        : 'No results match these filters.';
      // Reported live: कान्ताय genuinely occurs verbatim in Sumadhva Vijaya
      // (confirmed directly against the published index), but an UNSCOPED
      // search for it never opens that grantha's shard at all -- its own
      // interior trigrams are shared by ~48,000 units corpus-wide, so the
      // shard-open budget (dge-search.js's MAX_SHARDS/MAX_EXACT_SHARDS,
      // needed to keep a common query fast) is spent on other, arbitrarily-
      // tied candidates first. lastHits.partial (dge-search.js's own
      // "the sweep wasn't exhaustive" flag) is exactly the signal that this
      // happened -- scoping to one section (the picker next to the input)
      // searches only that section's much smaller candidate pool, so the
      // SAME exact match the unscoped sweep never reached opens in under a
      // second. Only worth saying when nothing is scoped yet and there's
      // somewhere narrower to go.
      if (exactActive && !out.length && lastHits.partial && !scopeSel.length) {
        emptyMsg += ' A search across the whole library can miss a real match' +
          ' buried in a very common word’s ties — narrowing the scope' +
          ' (the "Everything" picker above: tick a section, a work, or even' +
          ' one sarga) searches those texts directly and usually finds it.';
      }
    }
    renderRows(out, lastQuery, emptyMsg);
    var fc = document.getElementById('dge-gs-fcount');
    if (fc) fc.textContent = anyFilterActive ? (out.length + ' of ' + lastHits.length) : '';
  }

  function filterChip(label, active, onClick) {
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'dge-gs-chip' + (active ? ' active' : '');
    b.textContent = label;
    b.addEventListener('click', onClick);
    return b;
  }

  // Rebuilds the filter bar's chip set from the CURRENT unfiltered result
  // set every time a new search completes -- a stale chip from the
  // previous query (a category with zero hits this time) would just be
  // confusing dead weight, so the bar always reflects what this result set
  // actually contains rather than every category the corpus could ever have.
  function buildFilterBar(hits) {
    var bar = document.getElementById('dge-gs-filterbar');
    if (!hits || !hits.length) { bar.style.display = 'none'; bar.innerHTML = ''; return; }
    bar.innerHTML = '';
    bar.style.display = 'flex';

    // Counts must reflect what the reader can actually SEE under the
    // current "Exact spelling only" state -- a category chip advertising
    // (3) that produces 0 rows on tap (reported live, 31 Aug 2026, with
    // स्तुत्या) reads as a broken app. The chips' click handlers still pass
    // the FULL set around, so toggling exact re-counts automatically.
    var countBase = hits;
    if (filterState.exact && lastQueryDeva) {
      var qE = dgeGsExactNormalize(lastQueryDeva);
      countBase = hits.filter(function (h) { return dgeGsPassesExact(h, qE); });
    }
    var typeCounts = {};
    var catCounts = {};
    var sidCounts = {};
    countBase.forEach(function (h) {
      typeCounts[h.contentType] = (typeCounts[h.contentType] || 0) + 1;
      catCounts[h.category] = (catCounts[h.category] || 0) + 1;
      var sid = siddhantaOf(h.grantha);
      if (sid) sidCounts[sid] = (sidCounts[sid] || 0) + 1;
    });

    // Row 1: content type (only worth showing when the result set actually
    // mixes types -- a pure Rigveda search is all "shloka" and the toggle
    // would have nothing to do).
    if ((typeCounts.shloka ? 1 : 0) + (typeCounts.commentary ? 1 : 0) + (typeCounts.prose ? 1 : 0) > 1) {
      var typeRow = document.createElement('div');
      typeRow.className = 'dge-gs-frow';
      var typeLabel = document.createElement('span');
      typeLabel.className = 'dge-gs-flabel'; typeLabel.textContent = 'Type';
      typeRow.appendChild(typeLabel);
      [['all', 'All'], ['shloka', 'Shlokas'], ['commentary', 'Commentary']].forEach(function (pair) {
        if (pair[0] !== 'all' && !typeCounts[pair[0]]) return;
        typeRow.appendChild(filterChip(pair[1], filterState.type === pair[0], function () {
          filterState.type = pair[0];
          buildFilterBar(hits); // re-render so the active chip highlight updates
          applyFilters();
        }));
      });
      bar.appendChild(typeRow);
    }

    // Row 2: category (multi-select toggle chips).
    var catKeys = Object.keys(catCounts).sort(function (a, b) { return catCounts[b] - catCounts[a]; });
    if (catKeys.length > 1) {
      var catRow = document.createElement('div');
      catRow.className = 'dge-gs-frow';
      var catLabel = document.createElement('span');
      catLabel.className = 'dge-gs-flabel'; catLabel.textContent = 'Category';
      catRow.appendChild(catLabel);
      catKeys.forEach(function (cat) {
        var label = taxonomyLabel(cat) + ' (' + catCounts[cat] + ')';
        catRow.appendChild(filterChip(label, filterState.categories[cat] === true, function () {
          if (filterState.categories[cat]) delete filterState.categories[cat];
          else filterState.categories[cat] = true;
          buildFilterBar(hits);
          applyFilters();
        }));
      });
      bar.appendChild(catRow);
    }

    // Row 3: siddhanta -- only when the result set actually has vedanta
    // hits carrying one, which most searches (any Veda/Itihasa/Purana/
    // Stotra text) will not.
    var sidKeys = Object.keys(sidCounts);
    if (sidKeys.length > 1 || (sidKeys.length === 1 && sidCounts[sidKeys[0]] < hits.length)) {
      var sidRow = document.createElement('div');
      sidRow.className = 'dge-gs-frow';
      var sidLabel = document.createElement('span');
      sidLabel.className = 'dge-gs-flabel'; sidLabel.textContent = 'सिद्धान्तः · Siddhānta';
      sidRow.appendChild(sidLabel);
      sidKeys.forEach(function (sid) {
        var label = taxonomyLabel(sid) + ' (' + sidCounts[sid] + ')';
        sidRow.appendChild(filterChip(label, filterState.siddhanta[sid] === true, function () {
          if (filterState.siddhanta[sid]) delete filterState.siddhanta[sid];
          else filterState.siddhanta[sid] = true;
          buildFilterBar(hits);
          applyFilters();
        }));
      });
      bar.appendChild(sidRow);
    }

    // Row 4: exact-spelling toggle -- own row, since it's a mode the reader
    // opts into (see queryToDevanagari()'s comment above), not tied to this
    // result set's own contents the way type/category/siddhanta are. Only
    // shown when there's an actual Devanagari form of the query to check
    // against (see applyFilters()'s own guard) -- a dead toggle that can
    // never filter anything would just be confusing chrome.
    if (lastQueryDeva) {
      var exactRow = document.createElement('div');
      exactRow.className = 'dge-gs-frow';
      exactRow.appendChild(filterChip('Exact spelling only', filterState.exact, function () {
        filterState.exact = !filterState.exact;
        dgeGsSaveExact(filterState.exact);
        buildFilterBar(hits);
        applyFilters();
      }));
      bar.appendChild(exactRow);
    }

    // Row 5: keyword refine + a live "N of M shown" count.
    var kwRow = document.createElement('div');
    kwRow.className = 'dge-gs-frow';
    var kwInput = document.createElement('input');
    kwInput.type = 'text';
    kwInput.className = 'dge-gs-kwbox';
    kwInput.placeholder = 'Refine within these results…';
    kwInput.value = filterState.keyword;
    kwInput.addEventListener('input', function (e) { filterState.keyword = e.target.value; applyFilters(); });
    kwRow.appendChild(kwInput);
    var fc = document.createElement('span');
    fc.className = 'dge-gs-fcount'; fc.id = 'dge-gs-fcount';
    kwRow.appendChild(fc);
    bar.appendChild(kwRow);
  }

  // 23 Aug 2026: DvaitaVedanta (dge/data/darshana/vedanta/dvaita/DvaitaVedantaIn/)
  // is admin-only -- not linked in the Library nav, and per the project lead's
  // explicit ask, should not surface in search results for anyone else
  // either. The 330 MB CDN search index (see INDEX_BASE above) is a separate,
  // offline-built artifact this session can't rebuild, so a stale copy may
  // still carry old-path hits from before this restructure; filtering here,
  // on every hit this UI ever renders regardless of index freshness, is the
  // one place that reliably holds regardless of what the index contains.
  // Not real access control -- same caveat as admin-gate.js: this hides the
  // hit from the UI, it does not restrict the underlying static JSON file.
  var ADMIN_ONLY_GRANTHA_PREFIXES = ['darshana/vedanta/dvaita/DvaitaVedantaIn', 'dvaitavedanta'];
  function dgeSearchIsAdmin() {
    try {
      return localStorage.getItem('acharyaAuthorized') === 'true' ||
             localStorage.getItem('is_superadmin') === 'true';
    } catch (e) { return false; }
  }
  function dgeSearchIsAdminOnlyHit(h) {
    var g = h && h.grantha || '';
    return ADMIN_ONLY_GRANTHA_PREFIXES.some(function (p) { return g.indexOf(p) === 0; });
  }

  function render(hits, q) {
    // .filter() returns a fresh array, silently dropping the custom
    // `partial` flag dge-search.js sets on its result -- which is what
    // renderRows()'s "the sweep wasn't exhaustive" notes read. Carry it
    // across explicitly (pre-existing drop, found while wiring the
    // compound extension's own flag handling).
    var partial = (hits || []).partial;
    var degraded = (hits || []).degraded;
    hits = (hits || []).filter(function (h) {
      return dgeSearchIsAdmin() || (!dgeSearchIsAdminOnlyHit(h) && !gsIsSearchHiddenHit(h));
    });
    hits.partial = partial;
    hits.degraded = degraded;
    lastHits = hits;
    lastQuery = q;
    // type/category/siddhanta/keyword reset every search since they're
    // built from THIS result set's own contents (a category chip from the
    // last query may not even exist in this one). "Exact spelling only" is
    // different -- a mode the reader explicitly opted into, not tied to any
    // one result set -- so it persists across searches, same as the
    // scheme/section pickers already do.
    filterState = { type: 'all', categories: {}, siddhanta: {}, keyword: '', exact: filterState.exact };
    if (!hits || !hits.length) {
      document.getElementById('dge-gs-filterbar').style.display = 'none';
      renderRows([], q);
      return;
    }
    buildFilterBar(hits);
    applyFilters();
  }

  // Idle-time manifest prefetch (24 Aug 2026, project lead's "make search
  // lightning fast" directive) -- by the time a reader actually opens
  // search and types, the index object may already exist, saving a
  // manifest fetch + parse off the critical path of their FIRST query.
  // Deliberately NOT an eager/blocking fetch: manifest.json can be several
  // MB, and most readers on this page never open search at all -- costing
  // every one of them that bandwidth just to shave a round trip off the
  // minority who do would be the wrong trade for a mobile-first app that
  // already goes out of its way to keep data costs down elsewhere (offline
  // mode, lazy per-query shard/posting fetches). requestIdleCallback
  // (falling back to a plain timeout on a browser without it, e.g. Safari)
  // only runs this once the browser has nothing more pressing to do, and
  // it's skipped outright on a data-saver/slow connection -- exactly the
  // audience this restraint exists for.
  function prefetchManifest() {
    try {
      var conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
      if (conn && (conn.saveData || /2g/.test(conn.effectiveType || ''))) return;
    } catch (e) { /* navigator.connection isn't universally supported -- proceed as normal */ }
    var run = function () { ensureIndex(); };
    if (typeof window.requestIdleCallback === 'function') {
      window.requestIdleCallback(run, { timeout: 5000 });
    } else {
      setTimeout(run, 2000);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { build(); prefetchManifest(); });
  } else { build(); prefetchManifest(); }
  window.DGEGlobalSearch = { open: open, close: close };

  // Deep-link entry point (?gs=<query>): the kosha2 page's citation chips
  // (and anything else) can send a reader straight into corpus search.
  try {
    var gsq = new URLSearchParams(location.search).get('gs');
    if (gsq) setTimeout(function () {
      open();
      var inp = document.getElementById('dge-gs-input');
      if (inp) { inp.value = gsq; inp.dispatchEvent(new Event('input', { bubbles: true })); }
    }, 400);
  } catch (e) {}
})();
