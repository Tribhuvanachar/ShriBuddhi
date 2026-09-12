/* =========================================================================
   entity-linker.js — scholarly cross-reference / entity-linking system.

   When rendered text names another citable work ("ब्रह्मसूत्रे १.१.२",
   "अष्टाध्याय्याम्", "ऋग्वेदे", "विष्णुपुराणे"), this recognizes it and marks
   it up with a subtle (not a blue-underline hyperlink) inline treatment. A
   hover (desktop) or tap (touch — the same handler, since a tap fires
   click too) opens a small scholarly card: work name, the reference
   location if one was given, and actions to open it or search for it.

   Pipeline (see dge/SEARCH_ARCHITECTURE.md's cross-reference section for the
   full writeup): TEXT -> DETECTION (regex over dge_entities.json's own
   alias list, built once) -> NORMALIZATION (Devanagari digits -> int) ->
   RESOLUTION (alias -> canonical entity id -> route/reference scheme from
   the SAME registry) -> RENDERING (this file's popover). Deliberately no
   network call and no LLM anywhere in this path — dge_entities.json is a
   small, static, hand-maintained registry fetched once and cached; matching
   is plain regex + a lookup table, same cost class as intellisense.js's
   existing sūtra-citation scan this file runs alongside.

   This is Levels 1-2 of the architecture doc's detection-difficulty ladder:
   explicit verse-numbered citations (Level 1, high confidence) and named
   works with no number (Level 2, work-only). Levels 3 (abbreviation
   registry — already partly covered, see each entity's `abbreviations`)
   and 4 (quoted-passage detection) are future work, not attempted here.

   Ordering with intellisense.js's sūtra-citation linker matters: a phrase
   like "अष्टाध्याय्याम् १.१.१" is BOTH one of this file's entity aliases
   AND contains "अष्टाध्याय", one of intellisense.js's own cue words for
   linking a bare number. This file's scanEntities() must run BEFORE
   intellisense.js's scan() at every call site so the whole "work name +
   number" phrase becomes one dge-entity-ref span first; intellisense.js's
   own walker then skips into it no further, because its acceptNode() also
   rejects a 'dge-entity-ref' ancestor (see the one-line addition made
   there alongside this file, mirroring its existing dge-sutra-ref guard).
   Without that ordering + guard, this exact citation would double-link:
   this file's span AND a nested intellisense.js sūtra-ref for the same
   digits.
   ========================================================================= */
(function (root) {
  'use strict';

  var isBrowser = typeof window !== 'undefined' && typeof document !== 'undefined';

  if (isBrowser) {
    window.DGE_VERSIONS = window.DGE_VERSIONS || {};
    window.DGE_VERSIONS['entity-linker.js'] = 'v1.0 (Level 1+2 cross-reference detection + hover/tap card, see dge/SEARCH_ARCHITECTURE.md)';
  }

  // Pure detection/resolution logic (everything down to findMatches()) has
  // no DOM dependency and is unit-tested directly under Node -- see
  // entity-linker.test.js (run with `node --test dge/js/entity-linker.test.js`,
  // same convention as dge-search.js/genie_asr_benchmark's resolver.test.js).
  // Only the browser-only half below (scanning real DOM nodes, the popover,
  // fetch()) is skipped when isBrowser is false.
  var self = isBrowser ? ((document.currentScript && document.currentScript.src) || (window.DGE_SCRIPT_BASE || '')) : '';
  var DATA_URL = (function () {
    try { return new URL('../data/dge_entities.json', self).href; }
    catch (e) { return 'data/dge_entities.json'; }
  })();

  /* --------------------------------------------------------- registry --- */
  var registryPromise = null;
  function loadRegistry() {
    if (!registryPromise) {
      registryPromise = fetch(DATA_URL).then(function (r) { return r.ok ? r.json() : null; })
        .then(function (d) { return d ? buildIndex(d.entities || {}) : null; })
        .catch(function () { registryPromise = null; return null; });
    }
    return registryPromise;
  }

  function escapeRe(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }

  // Longest alias first: "ब्रह्मसूत्राणि" must win over the shorter
  // "ब्रह्मसूत्र" it starts with, not the other way round.
  function buildIndex(entities) {
    var pairs = [];
    Object.keys(entities).forEach(function (id) {
      var e = entities[id];
      (e.aliases || []).concat(e.abbreviations || []).forEach(function (a) {
        pairs.push({ alias: a, id: id });
      });
    });
    pairs.sort(function (a, b) { return b.alias.length - a.alias.length; });
    var byAlias = {};
    pairs.forEach(function (p) { byAlias[p.alias.toLowerCase()] = p.id; });
    var pattern = pairs.length ? new RegExp('(' + pairs.map(function (p) { return escapeRe(p.alias); }).join('|') + ')', 'gi') : null;
    return { entities: entities, byAlias: byAlias, pattern: pattern };
  }

  /* ------------------------------------------------------ normalization -- */
  var DEVA_DIGITS = '०१२३४५६७८९';
  function toAsciiNum(tok) {
    return tok.replace(/[०-९]/g, function (c) { return String(DEVA_DIGITS.indexOf(c)); });
  }

  // Up to LOCATOR_WINDOW characters right after a matched work-name may
  // hold its numeric locator: "ब्रह्मसूत्रे १.१.२", "अष्टाध्याय्याम् (१.१.१)",
  // "भागवते १०.१४.८" -- 1-4 groups of Devanagari-or-ASCII digits separated
  // by '.', '-', an en-dash, or bare space (citation punctuation varies
  // more than search-index tokens do).
  var LOCATOR_WINDOW = 16;
  var LOCATOR_RE = /^[\s(,:.।-]*([०-९0-9]{1,3}(?:[.\-–\s]+[०-९0-9]{1,3}){0,3})/;

  function parseLocator(text, at) {
    var slice = text.slice(at, at + LOCATOR_WINDOW);
    var m = LOCATOR_RE.exec(slice);
    if (!m || !m[1]) return null;
    var nums = toAsciiNum(m[1]).split(/[.\-–\s]+/).filter(Boolean).map(function (n) { return parseInt(n, 10); });
    return { nums: nums, matchedLen: m[0].length };
  }

  // Resolves the matched work + an optional numeric locator into a
  // confidence-scored reference. A locator only counts as Level 1 (and
  // only then does its text get folded into the rendered span) when it has
  // EXACTLY as many components as the entity's own reference scheme -- a
  // stray trailing number that doesn't fit the scheme is left as plain
  // text rather than guessed at.
  function resolveReference(entity, nums) {
    var comps = entity.reference_components || [];
    if (nums && comps.length && nums.length === comps.length && nums.every(function (n) { return !isNaN(n) && n > 0; })) {
      var target = {};
      comps.forEach(function (c, i) { target[c] = nums[i]; });
      return { level: 1, confidence: 0.97, target: target, consumed: true };
    }
    return { level: 2, confidence: 0.72, target: null, consumed: false };
  }

  /* --------------------------------------------------------------- scan -- */
  // Pure text -> matches. No DOM. Returns non-overlapping matches in
  // left-to-right order: {start, end, id, level, target}. `end` includes the
  // numeric locator's own characters when the reference resolved to Level 1
  // (`consumed`), so the rendered span covers the whole citation, not just
  // the work name.
  function findMatches(text, ix) {
    if (!ix.pattern) return [];
    var out = [];
    var last = 0, m;
    ix.pattern.lastIndex = 0;
    while ((m = ix.pattern.exec(text))) {
      var alias = m[1];
      var id = ix.byAlias[alias.toLowerCase()];
      var entity = id && ix.entities[id];
      if (!entity) continue;
      if (m.index < last) continue; // inside a match already emitted this pass
      var afterIdx = m.index + alias.length;
      var loc = parseLocator(text, afterIdx);
      var ref = resolveReference(entity, loc && loc.nums);
      var end = ref.consumed ? afterIdx + loc.matchedLen : afterIdx;
      out.push({ start: m.index, end: end, id: id, level: ref.level, target: ref.target });
      last = end;
      ix.pattern.lastIndex = last;
    }
    return out;
  }

  var SKIP = new Set(['SCRIPT', 'STYLE', 'TEXTAREA', 'INPUT', 'BUTTON', 'A', 'SELECT']);

  function scanNode(rootEl, ix) {
    if (!ix.pattern) return 0;
    var walker = document.createTreeWalker(rootEl, NodeFilter.SHOW_TEXT, {
      acceptNode: function (n) {
        if (!n.nodeValue || n.nodeValue.length < 4) return NodeFilter.FILTER_REJECT;
        var p = n.parentElement;
        while (p && p !== rootEl) {
          // dge-cite: kosha-citations.js's own abbreviated-citation linker
          // (e.g. "ऋ.वे. 1.165", "भा. IX. २२. ३३") runs before this one in
          // kosha.js and covers some of the SAME works this file's own
          // abbreviations list also carries ("ऋ." for Ṛgveda, "भा." for
          // Bhāgavata) -- skipping into an already-wrapped .dge-cite span
          // would otherwise nest a second, narrower dge-entity-ref inside it.
          if (SKIP.has(p.tagName) || p.classList.contains('dge-entity-ref') ||
              p.classList.contains('dge-sutra-ref') || p.classList.contains('dge-cite')) {
            return NodeFilter.FILTER_REJECT;
          }
          p = p.parentElement;
        }
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    var jobs = [], node;
    while ((node = walker.nextNode())) {
      ix.pattern.lastIndex = 0;
      if (ix.pattern.test(node.nodeValue)) jobs.push(node);
    }
    var total = 0;
    jobs.forEach(function (textNode) {
      var text = textNode.nodeValue;
      var matches = findMatches(text, ix);
      if (!matches.length) return;
      var frag = document.createDocumentFragment();
      var last = 0;
      matches.forEach(function (mm) {
        if (mm.start > last) frag.appendChild(document.createTextNode(text.slice(last, mm.start)));
        var el = document.createElement('span');
        el.className = 'dge-entity-ref';
        el.setAttribute('role', 'button');
        el.setAttribute('tabindex', '0');
        el.dataset.entity = mm.id;
        el.dataset.level = String(mm.level);
        if (mm.target) el.dataset.target = JSON.stringify(mm.target);
        el.textContent = text.slice(mm.start, mm.end);
        frag.appendChild(el);
        last = mm.end;
      });
      if (last < text.length) frag.appendChild(document.createTextNode(text.slice(last)));
      textNode.parentNode.replaceChild(frag, textNode);
      total += matches.length;
    });
    return total;
  }

  /* Cheap pre-check, same idiom as intellisense.js's scan(): a page with no
     recognizable work name at all never even fetches the (small, cached)
     registry. */
  function scanEntities(rootEl) {
    if (!rootEl) return;
    loadRegistry().then(function (ix) {
      if (!ix || !ix.pattern) return;
      ix.pattern.lastIndex = 0;
      if (!ix.pattern.test(rootEl.innerText || rootEl.textContent || '')) return;
      scanNode(rootEl, ix);
    });
  }
  if (isBrowser) window.dgeScanForEntities = scanEntities;

  /* ------------------------------------------------------------- routing -- */
  // {name} and {name:02d} template substitution -- entity route templates
  // only ever use these two forms (see dge_entities.json).
  function fillTemplate(tpl, vars) {
    return tpl.replace(/\{(\w+)(?::(\d+)d)?\}/g, function (_, key, pad) {
      var v = vars[key];
      if (v == null) return '';
      v = String(v);
      if (pad) { while (v.length < parseInt(pad, 10)) v = '0' + v; }
      return v;
    });
  }

  function buildOpenUrl(entity, target) {
    if (entity.route_type === 'custom') {
      var base;
      try { base = new URL(entity.canonical_route, self).href; } catch (e) { base = entity.canonical_route; }
      if (target && entity.jump_target_kind === 'custom_page') {
        return fillTemplate(entity.route_template, Object.assign({ base: base }, target));
      }
      return base;
    }
    // A 'reader_templated' route ALWAYS needs its {var} filled in -- a Level 2
    // (named-work-only) match has no target to fill it with, so this falls
    // back to part 1 of every component (e.g. amsha_01) as an honest,
    // real, navigable representative entry point rather than shipping a
    // link with a literal, broken "{amsha:02d}" still in the URL.
    var route = entity.canonical_route;
    if (entity.route_type === 'reader_templated') {
      var vars = target;
      if (!vars) {
        vars = {};
        (entity.reference_components || []).forEach(function (c) { vars[c] = 1; });
      }
      route = fillTemplate(entity.canonical_route, vars);
    }
    var path = isBrowser ? window.location.pathname : '/index.html';
    if (!/\/(index\.html)?$/.test(path)) path = path.replace(/[^/]*$/, 'index.html');
    var url = path + '?path=' + route;
    if (target && entity.jump_target_kind === 'vedicId' && entity.jump_target_template) {
      url += '&jumpVedicId=' + encodeURIComponent(fillTemplate(entity.jump_target_template, target));
    } else if (target && entity.jump_target_kind === 'shlokaNumber' && entity.jump_target_template) {
      url += '&jumpShloka=' + encodeURIComponent(fillTemplate(entity.jump_target_template, target));
    }
    return url;
  }

  /* ------------------------------------------------------------ popover -- */
  var pop = null;
  function closePop() { if (pop) { pop.remove(); pop = null; } }

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  // Same convention as intellisense.js's tr(): labels are stored in
  // Devanagari and transliterated to the reader's active script, rather
  // than this file inventing a second label system.
  var tr = function (t) {
    return (typeof window.dgeToActiveScript === 'function') ? window.dgeToActiveScript(t) : t;
  };

  var COMPONENT_LABELS = {
    adhyaya: 'अध्यायः', pada: 'पादः', sutra: 'सूत्रम्', mandala: 'मण्डलम्',
    sukta: 'सूक्तम्', rik: 'ऋक्', skandha: 'स्कन्धः', shloka: 'श्लोकः',
    amsha: 'अंशः', parva: 'पर्व', kanda: 'काण्डः', sarga: 'सर्गः'
  };

  function locatorLine(entity, target) {
    var comps = entity.reference_components || [];
    return comps.map(function (c) {
      var label = tr(COMPONENT_LABELS[c] || c);
      return label + ' ' + (target[c] != null ? target[c] : '—');
    }).join(' · ');
  }

  function css() {
    if (document.getElementById('dge-er-css')) return;
    var s = document.createElement('style');
    s.id = 'dge-er-css';
    s.textContent = [
      // Subtle: a fine dotted underline in the muted-text tone, not a
      // link-blue solid underline -- reads as "this is annotated", not
      // "this is a web link", per the project lead's own ask.
      '.dge-entity-ref{cursor:pointer;border-bottom:1px dotted var(--muted-text,#8a7a63);text-decoration:none;color:inherit;transition:background-color .12s ease}',
      '.dge-entity-ref:hover,.dge-entity-ref:focus{background:var(--card-active,rgba(122,59,29,.1));outline:none;border-radius:3px}',
      '.dge-er-pop{position:fixed;z-index:12000;width:min(320px,88vw);background:var(--card-bg,#fff);color:var(--text-primary,#1a1a1a);border:1px solid var(--card-border,rgba(0,0,0,.15));border-radius:12px;box-shadow:0 12px 32px rgba(0,0,0,.35);padding:12px 14px;font-family:inherit;font-size:14px}',
      '.dge-er-head{display:flex;align-items:center;justify-content:space-between;gap:8px;font-weight:700;margin-bottom:4px}',
      '.dge-er-x{border:none;background:none;color:var(--muted-text,#8a7a63);font-size:15px;cursor:pointer;line-height:1;padding:2px}',
      '.dge-er-x:hover{color:var(--accent-red,#7a3b1d)}',
      '.dge-er-loc{font-size:12.5px;opacity:.75;margin-bottom:8px}',
      '.dge-er-note{font-size:11.5px;opacity:.6;margin-bottom:8px;font-style:italic}',
      '.dge-er-actions{display:flex;flex-direction:column;gap:6px}',
      '.dge-er-actions a,.dge-er-actions button{display:block;text-align:left;border:1px solid var(--card-border,rgba(0,0,0,.2));background:var(--card-bg,#fff);color:var(--accent-red,#7a3b1d);border-radius:8px;padding:6px 10px;font-size:13px;font-weight:600;text-decoration:none;cursor:pointer;font-family:inherit}',
      '.dge-er-actions a:hover,.dge-er-actions button:hover{background:var(--card-active,rgba(122,59,29,.1))}'
    ].join('\n');
    document.head.appendChild(s);
  }

  function place(anchor) {
    if (!pop) return;
    var r = anchor.getBoundingClientRect();
    var w = pop.offsetWidth;
    var left = Math.max(8, Math.min(r.left, window.innerWidth - w - 8));
    var h = pop.offsetHeight || 160;
    var below = r.bottom + 8;
    var top = (below + h > window.innerHeight - 8 && r.top - h - 8 > 8) ? r.top - h - 8 : below;
    pop.style.left = left + 'px';
    pop.style.top = Math.max(8, Math.min(top, window.innerHeight - h - 8)) + 'px';
  }

  function openPop(anchor, id, targetJson) {
    loadRegistry().then(function (ix) {
      if (!ix) return;
      var entity = ix.entities[id];
      if (!entity) return;
      var target = targetJson ? JSON.parse(targetJson) : null;
      css();
      closePop();
      pop = document.createElement('div');
      pop.className = 'dge-er-pop';
      var name = tr(entity.sanskrit_name || entity.display_name) + ' · ' + entity.display_name;
      var openLabel = entity.route_type === 'custom'
        ? 'Open in ' + entity.display_name + ' →'
        : (target ? 'Open in DGE →' : 'Open work in DGE →');
      var html = '<div class="dge-er-head"><span>' + esc(name) + '</span>' +
        '<button class="dge-er-x" data-er-close aria-label="Close">✕</button></div>';
      if (target) {
        html += '<div class="dge-er-loc">' + esc(locatorLine(entity, target)) + '</div>';
      } else {
        html += '<div class="dge-er-note">Reference to the whole work — no specific location was given here.</div>';
      }
      if (entity.jump_target_kind === 'unresolved' && target) {
        html += '<div class="dge-er-note">Verse-level linking for this work isn’t wired up yet — opening the work itself.</div>';
      }
      html += '<div class="dge-er-actions">' +
        '<a href="' + esc(buildOpenUrl(entity, target)) + '">' + esc(openLabel) + '</a>' +
        '<button type="button" data-er-search>Search this reference</button>' +
        '</div>';
      pop.innerHTML = html;
      document.body.appendChild(pop);
      place(anchor);
      pop.querySelector('[data-er-search]').addEventListener('click', function () {
        closePop();
        var q = entity.sanskrit_name || entity.display_name;
        if (window.DGEGlobalSearch && typeof window.DGEGlobalSearch.open === 'function') {
          window.DGEGlobalSearch.open(q);
        }
      });
    });
  }

  if (isBrowser) {
    // Desktop hover shows the same card after a short delay (avoids flashing
    // one open/close per pointer pass); touch has no hover event at all, so
    // tap (a real click) is the only path there and always works via the
    // click handler below -- one implementation serves both per the spec's
    // "same card as a dialog on touch" ask.
    var hoverTimer = null;
    document.addEventListener('mouseover', function (ev) {
      var ref = ev.target.closest && ev.target.closest('.dge-entity-ref');
      if (!ref) return;
      clearTimeout(hoverTimer);
      hoverTimer = setTimeout(function () { openPop(ref, ref.dataset.entity, ref.dataset.target); }, 350);
    });
    document.addEventListener('mouseout', function (ev) {
      var ref = ev.target.closest && ev.target.closest('.dge-entity-ref');
      if (ref) clearTimeout(hoverTimer);
    });
    document.addEventListener('click', function (ev) {
      var ref = ev.target.closest && ev.target.closest('.dge-entity-ref');
      if (ref) { ev.preventDefault(); openPop(ref, ref.dataset.entity, ref.dataset.target); return; }
      if (ev.target.closest && ev.target.closest('[data-er-close]')) { closePop(); return; }
      if (pop && !ev.target.closest('.dge-er-pop')) closePop();
    });
    document.addEventListener('keydown', function (ev) {
      if (ev.key === 'Escape') closePop();
      if ((ev.key === 'Enter' || ev.key === ' ') && ev.target.classList && ev.target.classList.contains('dge-entity-ref')) {
        ev.preventDefault();
        openPop(ev.target, ev.target.dataset.entity, ev.target.dataset.target);
      }
    });

    // Idle prefetch, same reasoning as global-search.js's prefetchManifest():
    // the registry is tiny (a few KB, unlike the 330MB search index) but
    // there is still no reason to pay for it on a page nobody reads text on.
    var run = function () { loadRegistry(); };
    if (typeof window.requestIdleCallback === 'function') window.requestIdleCallback(run, { timeout: 4000 });
    else setTimeout(run, 1500);
  }

  // Node-testable exports (see entity-linker.test.js), same convention as
  // dge-search.js: pure functions only -- buildIndex/findMatches/resolveReference/
  // toAsciiNum/fillTemplate/buildOpenUrl need no DOM. buildOpenUrl still touches
  // `self`/`window.location` for the 'reader'/'reader_templated' branches, so
  // tests pass an explicit currentPath instead of relying on a real location.
  var API = {
    buildIndex: buildIndex, findMatches: findMatches, resolveReference: resolveReference,
    toAsciiNum: toAsciiNum, parseLocator: parseLocator, fillTemplate: fillTemplate,
    buildOpenUrl: buildOpenUrl
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
  if (isBrowser) window.DGEEntityLinker = API;
})(typeof window !== 'undefined' ? window : this);
