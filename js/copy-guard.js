// js/copy-guard.js
// The native OS/browser right-click and long-press menu is suppressed for
// everyone -- it is generic (Save Page, Inspect, View Source clutter) and
// the app's own Genie menu is the intended way to act on a selection or a
// shloka. Two honest limits on that suppression, stated here rather than
// left implicit:
//   1. This is friction, not security -- view-source, browser dev tools,
//      or simply disabling JavaScript bypass all of it. A determined
//      scraper is not stopped by a contextmenu listener.
//   2. Screenshots cannot be prevented by a website at all -- there is no
//      web API for it, on any browser or OS. Anything claiming to "block
//      screenshots" client-side is not real; this file makes no such
//      claim and does not attempt it.
window.DGE_VERSIONS = window.DGE_VERSIONS || {};
window.DGE_VERSIONS['copy-guard.js'] = 'v1.2 (30 Sep 2026: copy open to every reader; only the native menu is suppressed)';

(function () {
  document.addEventListener('contextmenu', function (ev) {
    // Editable fields keep their menu (paste into the search box, notes).
    var t = ev.target;
    if (t && t.closest && t.closest('input, textarea, [contenteditable="true"]')) return;
    ev.preventDefault();
  });

  // 30 Sep 2026, the lead: copying a shloka is not something to lock behind
  // a role or redirect away from. There used to be a 'copy' event listener
  // here that intercepted Ctrl+C for an unprivileged reader and nudged them
  // toward the app's own Copy/Share buttons instead; removed, so the
  // browser's native copy just works, same as those buttons.
})();
