/* =========================================================================
   selection-modes.js — Phase 4 of the frontend redesign.

   window.DGE_SELECTION_MODE (via window.dgeCurrentSelectionMode()) is a
   persisted reading preference -- Śloka / Paragraph / Word / Custom / Off --
   controlling what a single TAP selects as the Genie's context, so getting
   a verse/commentary-block/word into "Ask Acharya" doesn't always need a
   careful drag-select. Picker lives in #displayPopup (Display ▸ Genie
   Selection Mode), next to the other reading preferences.

   Deliberately does NOT touch what a genuine drag-selection does in any
   mode except Off -- ai.js's existing selectionchange-triggered tooltip is
   completely unmodified for Śloka/Paragraph/Word/Custom. Those three modes
   work by programmatically creating a real text Selection (a Range over
   the tapped element) on a plain tap, which then flows through ai.js's
   *existing*, *unchanged* selectionchange handling exactly as a manual
   drag-select already does today -- this file adds a tap shortcut to reach
   that same selection state, not a parallel context system.

   "Custom" (== today's only behavior, drag-select only, no tap shortcuts)
   is the default, so nobody's reading experience changes unless they
   explicitly opt into a different mode.

   Off suppresses the Genie's selection-triggered tooltip entirely via
   stopImmediatePropagation() on the selectionchange event -- which is why
   this script MUST be loaded, and its listener registered, before ai.js's:
   listeners on the same event+target run in registration order, and
   stopImmediatePropagation() only blocks handlers registered after it.
   ========================================================================= */
(function () {
  'use strict';

  window.DGE_VERSIONS = window.DGE_VERSIONS || {};
  window.DGE_VERSIONS['selection-modes.js'] = 'v1.0 (Phase 4)';

  var STORAGE_KEY = 'dge_selection_mode';
  var VALID = ['sloka', 'paragraph', 'word', 'custom', 'off'];
  var LABELS = { sloka: 'Śloka', paragraph: 'Paragraph', word: 'Word', custom: 'Custom', off: 'Off' };

  var mode = (function () {
    try {
      var v = localStorage.getItem(STORAGE_KEY);
      return VALID.indexOf(v) !== -1 ? v : 'custom';
    } catch (e) { return 'custom'; }
  })();

  window.dgeCurrentSelectionMode = function () { return mode; };

  function syncUI() {
    document.querySelectorAll('#displayPopup .pop-item[data-selmode]').forEach(function (el) {
      el.classList.toggle('active', el.dataset.selmode === mode);
    });
  }

  window.dgeSetSelectionMode = function (next) {
    if (VALID.indexOf(next) === -1) return;
    mode = next;
    try { localStorage.setItem(STORAGE_KEY, next); } catch (e) {}
    syncUI();
    if (mode === 'off') {
      var tooltip = document.getElementById('actionTooltip');
      if (tooltip) tooltip.style.display = 'none';
    }
    if (typeof window.showToast === 'function') {
      window.showToast('Genie selection: ' + LABELS[mode]);
    }
  };

  // Registered here, before ai.js loads -- see header comment.
  document.addEventListener('selectionchange', function (e) {
    if (mode !== 'off') return;
    e.stopImmediatePropagation();
    var tooltip = document.getElementById('actionTooltip');
    if (tooltip) tooltip.style.display = 'none';
  });

  var TAP_SNAP_SELECTOR = { word: '.dge-word', sloka: '.shloka-text', paragraph: '.commentary-block' };

  document.addEventListener('click', function (e) {
    var selector = TAP_SNAP_SELECTOR[mode];
    if (!selector) return; // off/custom: no tap shortcut, native behavior only

    var target = e.target.closest(selector);
    if (!target) return;

    // Only a plain tap on the text itself snaps the selection -- a tap on
    // something with its own real behavior *nested inside* the target
    // (a footnote link, a commentary tab, an expand toggle) is left alone.
    // A tap on the target element itself always proceeds, even though e.g.
    // .shloka-text already has its own onclick (loadShloka, for the audio
    // player) -- that existing behavior and this one compose fine: tapping
    // a verse in Śloka mode both makes it the active/playing verse (as
    // today) and selects its text as Genie context.
    if (e.target !== target && e.target.closest('button, a, input, textarea, select, .dge-commentary-tab, .mini, .sActions')) {
      return;
    }

    // Deferred to the next tick, and re-located by screen position rather
    // than by holding on to the DOM node found above -- two reasons:
    // (1) at least one other click listener on this page (registered after
    //     this one) resets the selection if set synchronously within this
    //     same click dispatch, so this has to run after the whole dispatch
    //     finishes regardless;
    // (2) .shloka-text carries its own onclick (loadShloka -- selects it
    //     for playback), which calls renderList() and rebuilds the shloka
    //     list's DOM from scratch. Since click events bubble, a tap on a
    //     .dge-word span (nested inside .shloka-text) or on .shloka-text
    //     itself triggers that rebuild too -- by the time this deferred
    //     callback runs, `target`/`el` above may already be a detached
    //     node from the old DOM, and selecting a detached node's contents
    //     silently fails. document.elementFromPoint at the original click
    //     coordinates finds whatever is now at that screen position after
    //     any such rebuild, since a same-content re-render leaves layout
    //     essentially unchanged.
    var clientX = e.clientX, clientY = e.clientY;
    setTimeout(function () {
      try {
        var liveEl = document.elementFromPoint(clientX, clientY);
        if (!liveEl) return;
        var liveTarget = liveEl.closest(selector);
        if (!liveTarget) return;
        var finalEl = liveTarget;
        if (mode === 'sloka') {
          var card = liveTarget.closest('.shloka-card');
          if (card) finalEl = card.querySelector('.shloka-text') || card;
        }
        var range = document.createRange();
        range.selectNodeContents(finalEl);
        var sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
      } catch (err) {}
    }, 0);
  });
})();
