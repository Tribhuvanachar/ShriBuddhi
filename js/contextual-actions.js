// DGE Module: contextual-actions.js
// Reader interaction redesign, Phase A: the per-object-type contextual
// action model (section 7 of the redesign brief) plus the per-taxonomy-
// section extension mechanism the project lead asked for directly:
// "if it is something in Veda, it can have additional contextual menu
// like whether the svara is anudatta, udatta, or svarita... If it is in
// the context of Ashtadhyayi, something else can come... All these
// should be mappable. We can enable it, disable it, map it."
//
// Two halves:
//  1. A REGISTRY (dgeGetContextualActions/dgeRegisterContextualActions)
//     that answers "what actions apply to THIS object type, in THIS
//     taxonomy section, for THIS reader" — sourced from
//     admin/config/contextual-actions.json (the base menu, admin-editable,
//     same convention as menu.json/keys.json) plus any taxonomy overrides
//     registered there, plus anything a page registers at runtime.
//  2. A generic contextual-menu component (dgeOpenContextualMenu) for
//     object types that have NO existing UI to duplicate — commentary and
//     (future) chapter/page. Shloka keeps actions.js's existing, richer
//     sheet; word/phrase keeps ai.js's existing selection tooltip and its
//     Shabda/Dhatu/Sandhi buttons — this file does not replace either,
//     it only adds the taxonomy-extra row neither of them had a way to
//     show (see dgeRenderWordToolsExtras below), and provides the one
//     piece of UI that never existed at all: a real per-object-type menu
//     for commentary taps.
//
// Preserves existing functionality: every dgeCtx* handler below either
// delegates to an already-working function (toggleFavorite, openStatusPicker,
// playShloka, askAcharyaForShloka, dgeOpenShabdaForSelection, ...) or is new,
// additive functionality with no existing equivalent (commentary actions,
// svara info, study list).

window.DGE_VERSIONS = window.DGE_VERSIONS || {};
window.DGE_VERSIONS['contextual-actions.js'] = 'v1.0 (contextual action registry + per-taxonomy-section registration system)';

(function () {
  'use strict';

  // Fallback used only if admin/config/contextual-actions.json is missing
  // or fails to parse — mirrors menu.json's own "never crash, just fall
  // back to what's hardcoded" convention. Kept intentionally small (base
  // shloka/word/commentary/reference only) since the full config is the
  // source of truth whenever it loads successfully.
  var FALLBACK_CONFIG = {
    base: {
      shloka: [
        { id: 'favorite', icon: 'star', label: 'Favorite', action: 'dgeCtxToggleFavorite', group: 'mark' },
        { id: 'status', icon: 'status', label: 'Reading status', action: 'dgeCtxOpenStatusPicker', group: 'mark' },
        { id: 'doubt', icon: 'doubt', label: 'Mark doubt', action: 'dgeCtxToggleDoubt', group: 'mark' },
        { id: 'bookmark', icon: 'bookmark', label: 'Bookmark', action: 'dgeCtxBookmark', group: 'mark' },
        { id: 'shareLink', icon: 'share', label: 'Share link', action: 'dgeCtxShareLink', group: 'share' },
        { id: 'copyLink', icon: 'link', label: 'Copy link', action: 'dgeCtxCopyLink', group: 'share' },
        { id: 'shareText', icon: 'text', label: 'Share text', action: 'dgeCtxShareText', group: 'share' },
        { id: 'copy', icon: 'copy', label: 'Copy text', action: 'dgeCtxCopyShloka', group: 'share' },
        { id: 'shareImage', icon: 'image', label: 'Share image', action: 'dgeCtxShareImage', group: 'share' },
        { id: 'shareAudio', icon: 'audio', label: 'Text + audio', action: 'dgeCtxShareAudio', group: 'share' },
        { id: 'play', icon: 'play', label: 'Play', action: 'dgeCtxPlayShloka', group: 'study' },
        { id: 'askAcharya', icon: 'acharya', label: 'Explain this shloka', action: 'dgeCtxAskAcharyaShloka', group: 'study' },
        { id: 'more', icon: 'more', label: 'Notes & snippets', action: 'dgeCtxOpenMoreSheet', group: 'study' }
      ],
      word: [
        { id: 'dictionary', icon: 'book', label: 'Dictionary', action: 'dgeCtxOpenShabda' },
        { id: 'copy', icon: 'copy', label: 'Copy', action: 'dgeCtxCopySelection' },
        { id: 'askAcharya', icon: 'acharya', label: 'Ask about this word', action: 'dgeCtxAskAcharyaWord' }
      ],
      phrase: [
        { id: 'copy', icon: 'copy', label: 'Copy', action: 'dgeCtxCopySelection' },
        { id: 'askAcharya', icon: 'acharya', label: 'Ask about this phrase', action: 'dgeCtxAskAcharyaPhrase' }
      ],
      commentary: [
        { id: 'copy', icon: 'copy', label: 'Copy commentary', action: 'dgeCtxCopyCommentary' },
        { id: 'askAcharya', icon: 'acharya', label: 'Explain this commentary', action: 'dgeCtxAskAcharyaCommentary' }
      ],
      reference: [
        { id: 'open', icon: 'open', label: 'Open in DGE', action: 'dgeCtxOpenReference' }
      ],
      chapter: [],
      page: []
    },
    taxonomyOverrides: []
  };

  var config = null;
  var configPromise = null;
  var runtimeRegistrations = []; // pages/features can add more via dgeRegisterContextualActions()

  function configUrl() {
    // A hardcoded "../admin/config/..." only resolves correctly from pages
    // exactly one level under the repo root (dge/index.html). It silently
    // 404s from anything nested deeper (dge/dasa-sahitya/index.html,
    // dge/vyakarana/*.html) since "../" only climbs past dasa-sahitya/,
    // landing on a dge/admin/ that doesn't exist -- this went unnoticed
    // because no page at that depth had loaded this file until dasa-sahitya
    // integration surfaced it. Resolve relative to THIS SCRIPT's own src
    // instead (document.currentScript, captured at parse time before any
    // async work), same pattern entity-linker.js already uses for
    // dge_entities.json -- correct at any page depth.
    var self = (document.currentScript && document.currentScript.src) || (window.DGE_SCRIPT_BASE || '');
    try { return new URL('../../admin/config/contextual-actions.json', self).href; }
    catch (e) { return '../admin/config/contextual-actions.json'; }
  }
  var CONFIG_URL = configUrl(); // must run synchronously at parse time -- document.currentScript is only valid then

  function fetchConfig() {
    if (configPromise) return configPromise;
    configPromise = fetch(CONFIG_URL + '?t=' + Date.now(), { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .catch(function () { return null; })
      .then(function (json) {
        config = (json && json.base) ? json : FALLBACK_CONFIG;
        return config;
      });
    return configPromise;
  }
  fetchConfig();

  // Runtime extension point — e.g. a vyakarana page can call this instead
  // of (or in addition to) editing the JSON, for logic too dynamic to
  // express as static data. Same shape as one taxonomyOverrides entry.
  window.dgeRegisterContextualActions = function (registration) {
    if (!registration || !Array.isArray(registration.add)) return;
    runtimeRegistrations.push(registration);
  };

  function matchesPrefixes(prefixes, slug) {
    if (!prefixes || !prefixes.length) return true;
    return prefixes.some(function (p) { return slug.indexOf(p) === 0; });
  }

  function passesRequires(action) {
    if (!action.requires) return true;
    if (action.requires === 'superadmin') return localStorage.getItem('is_superadmin') === 'true';
    if (action.requires === 'admin') return document.body.classList.contains('is-authorized');
    return true;
  }

  function activeOverrides(objectType, slug) {
    var cfg = config || FALLBACK_CONFIG;
    return (cfg.taxonomyOverrides || []).concat(runtimeRegistrations).filter(function (ov) {
      if (!ov || ov.enabled === false) return false;
      if (ov.objectTypes && ov.objectTypes.indexOf(objectType) === -1) return false;
      return matchesPrefixes(ov.pathPrefixes, slug);
    });
  }

  // Full action list for an object type: base + every matching taxonomy
  // override's additions, minus anything an override explicitly removes,
  // minus anything gated behind a role the current reader doesn't have.
  window.dgeGetContextualActions = function (objectType, context) {
    context = context || {};
    var slug = context.granthaSlug || window.currentGranthaSlug || '';
    var cfg = config || FALLBACK_CONFIG;
    var list = ((cfg.base && cfg.base[objectType]) || []).slice();
    var removedIds = {};

    activeOverrides(objectType, slug).forEach(function (ov) {
      (ov.remove || []).forEach(function (id) { removedIds[id] = true; });
      (ov.add || []).forEach(function (a) { list.push(a); });
    });

    return list.filter(function (a) { return !removedIds[a.id] && passesRequires(a); });
  };

  // Just the taxonomy-contributed extras (no base actions) — used to add
  // a taxonomy-specific row onto UI that already has its own base actions
  // rendered some other way (ai.js's word-selection tooltip), so nothing
  // gets rendered twice.
  window.dgeGetContextualOverrideActions = function (objectType, context) {
    context = context || {};
    var slug = context.granthaSlug || window.currentGranthaSlug || '';
    var out = [];
    activeOverrides(objectType, slug).forEach(function (ov) {
      (ov.add || []).forEach(function (a) { out.push(a); });
    });
    return out.filter(passesRequires);
  };

  // ---- Generic contextual menu (bottom sheet on mobile / same modal
  // markup as actionsSheetModal on desktop — main.css already makes any
  // .modal-overlay/.modal-content responsive) -------------------------

  var ICON_GLYPH = {
    star: '⭐', status: '◐', doubt: '❓', copy: '📋', play: '▶️', acharya: '🕉️',
    bookmark: '🔖', share: '📤', link: '🔗', text: '📝', image: '🖼️', audio: '🎧', refs: '📚',
    link: '🔗', more: '⋯', book: '📖', puzzle: '🧩', search: '🔍', add: '➕',
    open: '↗️', bookmark: '🔖', type: '🔤', audio: '🎧', export: '⬇️', edit: '✏️',
    svara: '𝄄'
  };

  function esc(s) {
    var d = document.createElement('div');
    d.textContent = s == null ? '' : String(s);
    return d.innerHTML;
  }

  function ensureMenuEl() {
    var el = document.getElementById('dgeContextMenu');
    if (el) return el;
    el = document.createElement('div');
    el.className = 'modal-overlay';
    el.id = 'dgeContextMenu';
    el.innerHTML =
      '<div class="modal-content ctx-menu-content">' +
        '<div class="modal-header-sticky">' +
          '<h4 class="ctx-menu-title" id="dgeContextMenuTitle" style="margin:0; color:var(--accent-red); font-size:15px;"></h4>' +
          '<button class="btn-sm" onclick="window.closeModal(\'dgeContextMenu\')" style="font-size:11px;">✖ Close</button>' +
        '</div>' +
        '<div class="modal-body"><div id="dgeContextMenuBody" class="ctx-menu-grid"></div></div>' +
      '</div>';
    document.body.appendChild(el);
    el.addEventListener('click', function (e) {
      var btn = e.target.closest('[data-ctx-action]');
      if (!btn) return;
      var fnName = btn.getAttribute('data-ctx-action');
      var ctx = window.__dgeCtxPendingContext || {};
      if (typeof window.closeModal === 'function') window.closeModal('dgeContextMenu');
      var fn = window[fnName];
      if (typeof fn === 'function') fn(ctx);
      else console.warn('[contextual-actions] no handler registered for action "' + fnName + '"');
    });
    // Clicking the dimmed backdrop closes it, same as every other modal-overlay.
    el.addEventListener('click', function (e) {
      if (e.target === el && typeof window.closeModal === 'function') window.closeModal('dgeContextMenu');
    });
    return el;
  }

  var TITLES = { word: 'Word', phrase: 'Selection', commentary: 'Commentary', reference: 'Reference', chapter: 'Chapter', page: 'Page' };

  // objectType: 'commentary' | 'chapter' | 'page' (word/phrase/shloka/
  // reference each already have their own dedicated surface — see file
  // header). context is passed through untouched to whichever dgeCtx*
  // handler the tapped button names.
  window.dgeOpenContextualMenu = function (objectType, context) {
    var actions = window.dgeGetContextualActions(objectType, context);
    if (!actions.length) {
      if (typeof window.showToast === 'function') window.showToast('No actions available here yet.');
      return;
    }
    ensureMenuEl();
    window.__dgeCtxPendingContext = context || {};
    var titleEl = document.getElementById('dgeContextMenuTitle');
    var bodyEl = document.getElementById('dgeContextMenuBody');
    var label = (context && context.label) ? context.label
      : (context && context.text) ? ('"' + (context.text.length > 28 ? context.text.slice(0, 28) + '…' : context.text) + '"')
      : (TITLES[objectType] || '');
    if (titleEl) titleEl.textContent = label;
    if (bodyEl) {
      var btn = function (a) {
        var glyph = ICON_GLYPH[a.icon] || '•';
        return '<button type="button" class="ctx-action-btn" data-ctx-action="' + esc(a.action) + '">' +
          '<span class="ctx-action-icon" aria-hidden="true">' + glyph + '</span>' +
          '<span class="ctx-action-label">' + esc(a.label) + '</span></button>';
      };
      // 7 Sep 2026: grouped sheet — Mark / Share this verse / Study — so every share action sits together
      // (the lead: "all share related features under one tab"). Items without a group (runtime registrations
      // such as the metre check) go under Study; a sheet whose items carry no groups at all renders flat.
      var GROUPS = [['mark', 'Mark'], ['share', 'Share this verse'], ['study', 'Study']];
      var grouped = actions.some(function (a) { return a.group; });
      if (!grouped || objectType !== 'shloka') {
        bodyEl.innerHTML = actions.map(btn).join('');
      } else {
        var ref = (objectType === 'shloka' && typeof window.dgeShlokaReference === 'function') ? window.dgeShlokaReference(shlokaIdFrom(context)) : null;
        var html = ref ? '<div class="ctx-group-ref">' + esc(ref.line) + (ref.short ? ' <span class="ctx-group-short">?' + esc(ref.short) + '</span>' : '') + '</div>' : '';
        GROUPS.forEach(function (g) {
          var items = actions.filter(function (a) { return (a.group || 'study') === g[0]; });
          if (!items.length) return;
          html += '<div class="ctx-group-label">' + g[1] + '</div>' + items.map(btn).join('');
        });
        bodyEl.innerHTML = html;
      }
    }
    if (typeof window.openModal === 'function') window.openModal('dgeContextMenu');
  };

  // ---- Word/phrase tooltip integration: renders ONLY taxonomy-extra
  // actions (base word/phrase actions already exist as ai.js's Shabda/
  // Dhatu/Sandhi/Copy/Ask-Acharya buttons — rendering the base list again
  // here would duplicate them). Called from ai.js's selectionchange
  // handler each time the tooltip's content is updated. -----------------
  window.dgeRenderWordToolsExtras = function (isSingleWord, selectedText) {
    var row = document.getElementById('wordToolsExtraRow');
    if (!row) return;
    var objectType = isSingleWord ? 'word' : 'phrase';
    var extras = window.dgeGetContextualOverrideActions(objectType, { text: selectedText });
    if (!extras.length) { row.style.display = 'none'; row.innerHTML = ''; return; }
    window.__dgeCtxPendingContext = { text: selectedText, granthaSlug: window.currentGranthaSlug };
    row.innerHTML = extras.map(function (a) {
      var glyph = ICON_GLYPH[a.icon] || '•';
      return '<button type="button" class="tooltip-btn" data-ctx-action="' + esc(a.action) + '">' + glyph + ' ' + esc(a.label) + '</button>';
    }).join('');
    row.style.display = 'flex';
  };

  document.addEventListener('DOMContentLoaded', function () {
    var row = document.getElementById('wordToolsExtraRow');
    if (!row) return;
    row.addEventListener('click', function (e) {
      var btn = e.target.closest('[data-ctx-action]');
      if (!btn) return;
      var fn = window[btn.getAttribute('data-ctx-action')];
      var ctx = window.__dgeCtxPendingContext || {};
      var tooltip = document.getElementById('actionTooltip');
      if (tooltip) tooltip.style.display = 'none';
      if (typeof fn === 'function') fn(ctx);
    });
  });

  // ---- Commentary tap -> commentary contextual menu (genuinely new;
  // no prior UI to duplicate). Delegated via one listener on the list
  // container rather than an onclick per block, so it costs nothing when
  // no commentary is rendered and needs no change to render.js's markup. --
  document.addEventListener('click', function (e) {
    // Never hijack a tap on something with its own real behavior nested
    // inside a commentary block (a footnote link, a sutra-ref, an
    // already-linked entity span, a tab, an expand toggle).
    if (e.target.closest('a, button, .dge-sutra-ref, .dge-entity-ref, .dge-commentary-tab, details summary')) return;
    // A drag-selection's mouseup also fires a click — when there's a real
    // text selection, section 7's hierarchy gives WORD/PHRASE priority
    // over the commentary-level menu, and ai.js's own selectionchange
    // tooltip is already handling it; don't also pop this menu on top.
    var sel = window.getSelection();
    if (sel && sel.toString().trim().length > 0) return;
    var block = e.target.closest('.commentary-block');
    if (!block) return;
    // A tap that lands on a WORD is a word selection, not a request for the
    // commentary's own menu. The lead's report (9 Sep 2026): selecting a word
    // in a commentary "restricts options to commentary-related choices rather
    // than allowing full linguistic analysis" -- on a phone a tap on a word is
    // just a tap, so this handler swallowed it and offered copy/ask-about-this-
    // commentary instead of शब्द/धातु/कोश. Section 7's own hierarchy already
    // says WORD outranks the commentary level; this makes a tap obey it too,
    // the way a drag-selection always did. The commentary menu still answers a
    // tap on the block's margins, its title, or the gaps between words.
    var word = e.target.closest('.dge-word');
    if (word && typeof window.dgeOpenWordToolsForElement === 'function' &&
        window.dgeOpenWordToolsForElement(word)) return;
    var card = block.closest('.shloka-card');
    var shlokaId = card && card.id ? parseInt(card.id.split('-')[1], 10) : (window.contextShlokaId || window.activeId);
    var cKey = block.getAttribute('data-ckey') || null;
    var titleEl = block.querySelector('.commentary-title');
    var label = titleEl ? titleEl.textContent.replace(/\s+/g, ' ').trim() : 'Commentary';
    window.dgeOpenContextualMenu('commentary', { shlokaId: shlokaId, cKey: cKey, el: block, label: label });
  });

  // ---- Handlers: delegate to existing functionality wherever it exists ----

  function shlokaIdFrom(ctx) { return (ctx && ctx.shlokaId != null) ? ctx.shlokaId : (window.contextShlokaId || window.activeId); }

  async function copyText(text, okMessage) {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
      } else {
        var ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.left = '-9999px';
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
      }
      if (typeof window.showToast === 'function') window.showToast(okMessage || 'Copied.');
    } catch (err) {
      if (typeof window.showToast === 'function') window.showToast('Could not copy — select and copy manually.');
    }
  }

  window.dgeCtxToggleFavorite = function (ctx) { if (typeof window.toggleFavorite === 'function') window.toggleFavorite(shlokaIdFrom(ctx)); };
  window.dgeCtxOpenStatusPicker = function (ctx) {
    if (typeof window.openStatusPicker !== 'function') return;
    var id = shlokaIdFrom(ctx);
    // openStatusPicker positions its popup off a real anchor element's
    // rect (markers.js) and no-ops without one — anchor to the shloka
    // card itself (or the viewport center as a last resort) so it still
    // opens correctly when triggered from this menu rather than the old
    // inline status chip.
    var anchor = document.getElementById('shloka-' + id) || document.body;
    window.openStatusPicker(id, { currentTarget: anchor, stopPropagation: function () {} });
  };
  window.dgeCtxToggleDoubt = function (ctx) { if (typeof window.toggleDoubt === 'function') window.toggleDoubt(shlokaIdFrom(ctx)); };
  window.dgeCtxCopyShloka = function (ctx) { if (typeof window.copyShlokaText === 'function') window.copyShlokaText(shlokaIdFrom(ctx)); };
  window.dgeCtxPlayShloka = function (ctx) { if (typeof window.playShloka === 'function') window.playShloka(shlokaIdFrom(ctx)); };
  window.dgeCtxAskAcharyaShloka = function (ctx) { if (typeof window.askAcharyaForShloka === 'function') window.askAcharyaForShloka(shlokaIdFrom(ctx), 'shloka'); };
  window.dgeCtxShowReferences = function (ctx) {
    // entity-linker.js owns reference detection/UI (see file header) —
    // this just surfaces its existing scan result for the current card
    // rather than re-implementing detection here.
    var id = shlokaIdFrom(ctx);
    var card = document.getElementById('shloka-' + id);
    var ref = card && card.querySelector('.dge-entity-ref, .dge-sutra-ref');
    if (ref) { ref.click(); return; }
    if (typeof window.showToast === 'function') window.showToast('No recognized references on this shloka.');
  };
  window.dgeCtxOpenMoreSheet = function (ctx) { if (typeof window.openActionsSheet === 'function') window.openActionsSheet(shlokaIdFrom(ctx)); };
  // Share group (7 Sep 2026) — the same functions the More sheet's buttons call, plus link/bookmark from share.js.
  window.dgeCtxShareLink = function (ctx) { if (typeof window.dgeShareShlokaLink === 'function') window.dgeShareShlokaLink(shlokaIdFrom(ctx)); };
  window.dgeCtxCopyLink = function (ctx) { if (typeof window.dgeCopyShlokaLink === 'function') window.dgeCopyShlokaLink(shlokaIdFrom(ctx)); };
  window.dgeCtxShareText = function (ctx) { if (typeof window.shareShlokaTextOnly === 'function') window.shareShlokaTextOnly(shlokaIdFrom(ctx)); };
  window.dgeCtxShareImage = function (ctx) { if (typeof window.openShareImagePreview === 'function') window.openShareImagePreview(shlokaIdFrom(ctx)); };
  window.dgeCtxShareAudio = function (ctx) { if (typeof window.shareShlokaAudio === 'function') window.shareShlokaAudio(shlokaIdFrom(ctx)); };
  window.dgeCtxBookmark = function (ctx) { if (typeof window.dgeBookmarkShloka === 'function') window.dgeBookmarkShloka(shlokaIdFrom(ctx)); };

  window.dgeCtxOpenShabda = function () { var btn = document.querySelector('[data-word-only][onpointerdown*="dgeOpenShabdaForSelection"]'); if (btn) btn.click(); else if (typeof window.dgeOpenShabdaForSelection === 'function') window.dgeOpenShabdaForSelection(null); };
  window.dgeCtxOpenDhatu = function () { if (typeof window.dgeOpenDhatuForSelection === 'function') window.dgeOpenDhatuForSelection(null); };
  window.dgeCtxSearchCorpus = function (ctx) {
    var q = (ctx && ctx.text) ? ctx.text : (typeof window.dgeRobustSelectedText === 'function' ? window.dgeRobustSelectedText() : '');
    if (!q) return;
    if (typeof window.dgeOpenGlobalSearch === 'function') window.dgeOpenGlobalSearch(q);
    else if (typeof window.openGlobalSearch === 'function') window.openGlobalSearch(q);
    else window.location.href = 'global-search.html?q=' + encodeURIComponent(q);
  };
  window.dgeCtxCopySelection = function (ctx) { copyText((ctx && ctx.text) || (typeof window.dgeRobustSelectedText === 'function' ? window.dgeRobustSelectedText() : ''), 'Copied.'); };
  window.dgeCtxAskAcharyaWord = function () { if (typeof window.askAcharya === 'function') window.askAcharya(null, 'grammar'); };
  window.dgeCtxAskAcharyaPhrase = function () { if (typeof window.askAcharya === 'function') window.askAcharya(null, 'translate'); };
  window.dgeCtxAddToStudyList = function (ctx) {
    var id = shlokaIdFrom(ctx);
    if (typeof window.marks === 'undefined' || !id) return;
    window.marks[id] = window.marks[id] || { fav: false, status: null, doubt: false };
    if (!window.marks[id].status) window.marks[id].status = 'practice';
    if (typeof window.dgeSaveMarks === 'function') window.dgeSaveMarks();
    if (typeof window.renderList === 'function') window.renderList();
    if (typeof window.showToast === 'function') window.showToast('Added to study list (marked "Needs Practice").');
  };

  window.dgeCtxCopyCommentary = function (ctx) {
    var block = ctx && ctx.el;
    var text = block ? block.innerText.replace(/\s+/g, ' ').trim() : '';
    copyText(text, 'Commentary copied.');
  };
  window.dgeCtxAskAcharyaCommentary = function (ctx) {
    var id = shlokaIdFrom(ctx);
    if (id != null && typeof window.openBhashyaPickerForShloka === 'function') {
      window.openBhashyaPickerForShloka(id);
    } else if (typeof window.askAcharyaForShloka === 'function') {
      window.askAcharyaForShloka(id, 'bhashya');
    }
  };

  window.dgeCtxOpenReference = function (ctx) {
    var el = ctx && ctx.el;
    if (el) { el.click(); return; }
    if (typeof window.showToast === 'function') window.showToast('Open this reference from its own card.');
  };
  window.dgeCtxAskAcharyaReference = function (ctx) {
    var label = (ctx && ctx.label) || '';
    if (typeof window.askAcharya === 'function') {
      window.lastSelectedText = label;
      window.askAcharya(null, 'translate');
    }
  };

  window.dgeCtxBookmarkChapter = function () { if (typeof window.showToast === 'function') window.showToast('Chapter bookmarks are coming soon.'); };
  window.dgeCtxAskAcharyaChapter = function () { if (typeof window.showToast === 'function') window.showToast('Chapter summaries are coming soon.'); };
  window.dgeCtxBookmarkPage = function () { if (typeof window.showToast === 'function') window.showToast('Page bookmarks are coming soon.'); };
  window.dgeCtxSearchWithinText = function () { if (typeof window.togglePopup === 'function') window.togglePopup('searchPopup'); };
  window.dgeCtxOpenDisplaySettings = function () { if (typeof window.togglePopup === 'function') window.togglePopup('displayPopup'); };
  window.dgeCtxOpenAudioPanel = function () { if (typeof window.expandAudioPlayer === 'function') window.expandAudioPlayer(); };
  window.dgeCtxExportPage = function () { if (typeof window.showToast === 'function') window.showToast('Use ⋯ on a shloka to copy/download/share it.'); };
  window.dgeCtxEnterEditMode = function () { if (typeof window.dgeToggleContentEditMode === 'function') window.dgeToggleContentEditMode(); };

  // ---- The Veda example: svara (accent) info, wired via the taxonomy
  // override above (pathPrefixes: ["vedas/"]). Honest about what the
  // corpus actually has today: DGE's digitized Vedic text does not yet
  // carry Unicode Vedic-accent combining marks (verified against sampled
  // corpus files), so this doesn't invent per-syllable analysis — it
  // explains what svara marking is, reports what it found in the actual
  // selected text (nothing, today), and says so plainly. The point of
  // this handler is to prove the per-taxonomy REGISTRATION mechanism
  // works end-to-end for real Veda content; full accent-rule tooling is
  // future work once the corpus itself carries accent data (tracked
  // alongside the corpus's other known content gaps). ------------------
  var SVARA_MARKS = {
    '॒': 'anudātta (grave, "॒")',
    '᳚': 'dīrgha svarita ("᳚")',
    '᳜': 'kampa svarita ("᳜")',
    '᳝': 'anudāttatara ("᳝")',
    '॑': 'udātta / svarita marker ("॑")'
  };
  window.dgeCtxShowSvaraInfo = function (ctx) {
    var text = (ctx && ctx.text) || '';
    var found = [];
    Object.keys(SVARA_MARKS).forEach(function (ch) {
      if (text.indexOf(ch) !== -1) found.push(SVARA_MARKS[ch]);
    });
    var body = found.length
      ? ('This word carries: ' + esc(found.join(', ')) + '.')
      : 'This selection has no encoded Vedic accent (svara) marks — anudātta, udātta and svarita are traditionally marked with combining accent characters, which this text does not yet carry in DGE’s digitized corpus.';
    ensureMenuEl();
    var titleEl = document.getElementById('dgeContextMenuTitle');
    var bodyEl = document.getElementById('dgeContextMenuBody');
    if (titleEl) titleEl.textContent = 'Svara (accent)' + (text ? ' — "' + text + '"' : '');
    if (bodyEl) bodyEl.innerHTML = '<p style="font-size:13px; line-height:1.6; color:var(--text-primary); grid-column:1/-1;">' + body + '</p>';
    if (typeof window.openModal === 'function') window.openModal('dgeContextMenu');
  };
})();
