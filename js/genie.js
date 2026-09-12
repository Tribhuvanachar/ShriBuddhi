/* =========================================================================
   genie.js — Phase 3 of the frontend redesign.

   Gesture layer for #dge-qa-tab ("the Genie"), which kept its exact
   existing edge-docked shape/position (see main.css's own header comment
   on .dge-qa-tab for why a free-floating avatar was considered and
   rejected) but is now reskinned with a real avatar and driven entirely
   through pointer events instead of a plain onclick, so it can tell a tap
   apart from a drag, a double-tap, and a long-press:

     tap          -> opens #quickActionsPopup (identical to the old plain
                     click -- zero behavior change from before this file)
     double-tap    -> runs the primary contextual action: Ask Acharya for
                     whatever śloka/word is currently in context
     long-press    -> opens a short "how to use the Genie" dialog
     drag          -> slides the tab up/down along the right edge, clamped
                     so it never leaves the edge or overlaps the top bar /
                     bottom player

   Deliberately NOT implemented (scope trim, noted rather than silently
   dropped): parking/hiding the tab entirely, and free 2D placement off the
   edge. Both were part of the original mockup's gesture set but conflict
   with the "stay docked, stay minimal" decision this file already
   respects -- an edge-docked tab that's already this small has little left
   to gain from also being hideable.
   ========================================================================= */
(function () {
  'use strict';

  window.DGE_VERSIONS = window.DGE_VERSIONS || {};
  window.DGE_VERSIONS['genie.js'] = 'v1.0 (Phase 3: gesture layer for #dge-qa-tab)';

  var TAP_WINDOW_MS = 280;
  var LONG_PRESS_MS = 600;
  var DRAG_THRESHOLD_PX = 8;

  function ready(fn) {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', fn);
    else fn();
  }

  ready(function () {
    var tab = document.getElementById('dge-qa-tab');
    if (!tab) return; // page has no Genie tab (not the reader)

    var pointerId = null, downX = 0, downY = 0, startBottom = 0;
    var moved = false, longPressTimer = null, tapTimer = null, tapCount = 0;

    function currentBottomPx() {
      var cs = getComputedStyle(tab);
      return parseFloat(cs.bottom) || 0;
    }

    // The doc comment above promises dragging "never... overlaps the top
    // bar / bottom player", but only the top bar was actually accounted
    // for -- minBottom was a flat 20px regardless of whether .bottom-player
    // (z-index 9999, above this tab's own 9990) was on screen. Confirmed
    // live: dragging to the old floor left the tab's lower half literally
    // unclickable, swallowed under the player bar. Measured fresh on each
    // drag rather than cached, since the player's own height isn't fixed
    // (e.g. wider safe-area insets) and it doesn't exist at all on every
    // page.
    function bottomPlayerClearance() {
      var player = document.querySelector('.bottom-player');
      if (!player || getComputedStyle(player).display === 'none') return 0;
      return player.getBoundingClientRect().height;
    }

    function clampBottom(px) {
      var minBottom = 20 + bottomPlayerClearance(); // never below the safe-area gap, or under the bottom player when it's showing
      var maxBottom = Math.max(minBottom, window.innerHeight - tab.offsetHeight - 70); // stay clear of the top bar
      return Math.min(maxBottom, Math.max(minBottom, px));
    }

    function primaryAction() {
      var id = window.contextShlokaId || window.activeId;
      if (typeof window.askAcharyaForShloka === 'function' && id) {
        window.askAcharyaForShloka(id);
      } else if (typeof window.showToast === 'function') {
        window.showToast('Select a śloka or word first, then double-tap the Genie.');
      }
    }

    function openQuickActions() {
      if (typeof window.togglePopup === 'function') window.togglePopup('quickActionsPopup');
    }

    function registerTap() {
      tapCount++;
      clearTimeout(tapTimer);
      tapTimer = setTimeout(function () {
        if (tapCount === 1) openQuickActions();
        else if (tapCount >= 2) primaryAction();
        tapCount = 0;
      }, TAP_WINDOW_MS);
    }

    tab.addEventListener('pointerdown', function (e) {
      pointerId = e.pointerId;
      moved = false;
      downX = e.clientX; downY = e.clientY;
      startBottom = currentBottomPx();
      try { tab.setPointerCapture(pointerId); } catch (err) {}
      clearTimeout(longPressTimer);
      longPressTimer = setTimeout(function () {
        if (!moved) {
          tab.classList.remove('dge-genie-dragging');
          openGenieHelp();
        }
      }, LONG_PRESS_MS);
    });

    tab.addEventListener('pointermove', function (e) {
      if (e.pointerId !== pointerId) return;
      var dy = e.clientY - downY;
      var dx = e.clientX - downX;
      if (!moved && Math.hypot(dx, dy) > DRAG_THRESHOLD_PX) {
        moved = true;
        clearTimeout(longPressTimer);
        tab.classList.add('dge-genie-dragging');
      }
      if (moved) {
        // Dragging up (negative dy) should move the tab up the screen, i.e.
        // increase its `bottom` value -- inverse of pointer-Y delta.
        tab.style.bottom = clampBottom(startBottom - dy) + 'px';
      }
    });

    tab.addEventListener('pointerup', function (e) {
      if (e.pointerId !== pointerId) return;
      clearTimeout(longPressTimer);
      tab.classList.remove('dge-genie-dragging');
      if (!moved) registerTap();
      pointerId = null;
    });

    tab.addEventListener('pointercancel', function () {
      clearTimeout(longPressTimer);
      tab.classList.remove('dge-genie-dragging');
      pointerId = null;
    });

    // Keyboard activation (Enter/Space on a focused button) fires a plain
    // click with no pointer sequence -- treat that as a single tap so the
    // tab stays keyboard-accessible.
    tab.addEventListener('click', function (e) {
      if (e.detail === 0) openQuickActions(); // detail===0 => keyboard-triggered, not a real pointer click
    });
  });

  function openGenieHelp() {
    var existing = document.getElementById('dge-genie-help');
    if (existing) { existing.showModal(); return; }

    var dlg = document.createElement('dialog');
    dlg.id = 'dge-genie-help';
    dlg.className = 'dge-genie-help-dialog';
    dlg.innerHTML =
      '<h3>🕉️ The Genie</h3>' +
      '<dl>' +
      '<dt>Tap</dt><dd>Kosha, corpus search, and other quick actions.</dd>' +
      '<dt>Double-tap</dt><dd>Ask Acharya about whatever śloka or word you last selected.</dd>' +
      '<dt>Long-press</dt><dd>Opens this help.</dd>' +
      '<dt>Drag</dt><dd>Slide the Genie up or down out of your way — it stays on the edge.</dd>' +
      '</dl>' +
      '<button class="dge-genie-help-close">Got it</button>';
    document.body.appendChild(dlg);
    dlg.querySelector('.dge-genie-help-close').addEventListener('click', function () { dlg.close(); });
    dlg.addEventListener('click', function (e) { if (e.target === dlg) dlg.close(); });
    dlg.showModal();
  }
})();
