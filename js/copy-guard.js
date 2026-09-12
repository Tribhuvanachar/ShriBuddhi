// js/copy-guard.js
// Light friction against casual right-click-save/copy-paste scraping of
// the corpus text, for non-admin readers only. Two honest limits, stated
// here rather than left implicit:
//   1. This is friction, not security -- view-source, browser dev tools,
//      or simply disabling JavaScript bypass all of it. A determined
//      scraper is not stopped by a contextmenu/copy listener.
//   2. Screenshots cannot be prevented by a website at all -- there is no
//      web API for it, on any browser or OS. Anything claiming to "block
//      screenshots" client-side is not real; this file makes no such
//      claim and does not attempt it.
window.DGE_VERSIONS = window.DGE_VERSIONS || {};
window.DGE_VERSIONS['copy-guard.js'] = 'v1.1 (10 Sep 2026: copy is a role-granted capability, not admin-only)';

(function () {
  // 10 Sep 2026: copy is no longer an admin-or-nobody switch. It is a
  // capability granted per role in admin/access-control.html (see
  // dgeRoleCan in role-access.js) -- the lead's choice, so a scholar can be
  // allowed to take a word into their own notes without being made an
  // admin. An admin still always can; an unconfigured deployment behaves
  // exactly as before, because an ungranted capability is closed.
  function mayCopy() {
    if (typeof window.dgeRoleCan === 'function') return window.dgeRoleCan('copy');
    try {
      return localStorage.getItem('acharyaAuthorized') === 'true' ||
             localStorage.getItem('is_superadmin') === 'true';
    } catch (e) { return false; }
  }

  document.addEventListener('contextmenu', function (ev) {
    if (mayCopy()) return;
    // Editable fields keep their menu (paste into the search box, notes).
    var t = ev.target;
    if (t && t.closest && t.closest('input, textarea, [contenteditable="true"]')) return;
    ev.preventDefault();
  });

  // Copy is redirected to a nudge toward the app's own Share tools
  // (copyShlokaText / Share-as-Image) rather than silently doing nothing —
  // a blocked Ctrl+C with no explanation reads as the page being broken,
  // and those tools exist precisely for a reader who wants to take a
  // verse elsewhere.
  document.addEventListener('copy', function (ev) {
    if (mayCopy()) return;
    var sel = window.getSelection ? window.getSelection().toString() : '';
    if (!sel) return;
    ev.preventDefault();
    if (typeof showToast === 'function') {
      showToast('Use the 📋 Copy or Share button on a shloka to take it with you.');
    }
  });
})();
