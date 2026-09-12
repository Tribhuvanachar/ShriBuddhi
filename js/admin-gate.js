/* =========================================================================
   admin-gate.js — shared "admin-only" visibility for standalone pages.

   dge/index.html (the reader) already knows how to tell an admin from a
   visitor (core.js's initAuthAndBranding, reading the same two localStorage
   keys this file reads). The standalone pages — Guru Parampara, Tirtha
   Prabandha, Dasa Sahitya, and others under dge/ that don't load the reader
   app — had no such check at all, so internal notes (a "Completeness
   Tracker", OCR confidence badges, raw external source links, internal
   reference numbers) rendered to every visitor unconditionally. This gives
   those pages the same gate in one script tag instead of bespoke JS per page.

   Usage: mark anything that should only reach a signed-in admin with the
   data-admin-only attribute. Add a second script tag (this one) anywhere —
   first, ideally, right after vandana-guard.js — and nothing else. Use
   data-admin-only="super" for the higher tier (super-admin) specifically;
   plain data-admin-only (any other value, or none) accepts either tier,
   matching the 🛡️ menu's own "either tier" rule in core.js.

   Not a security control — same as vandana-guard.js, there is nothing
   secret behind this, it is tidiness for the public reader. localStorage is
   readable by anyone with devtools; treat this as UI polish, not access
   control, and never put a real secret behind it.

   The hiding rule is injected as a blocking <style> the instant this script
   runs, so a non-admin never sees a flash of the content before JS decides —
   the same reasoning vandana-guard.js gives for running synchronously and
   first. Revealing for an admin removes the attribute outright (rather than
   fighting the stylesheet with an inline display value), so the element
   falls back to whatever display it would normally have. */
(function () {
  'use strict';

  window.DGE_VERSIONS = window.DGE_VERSIONS || {};
  window.DGE_VERSIONS['admin-gate.js'] = 'v1.0';

  var style = document.createElement('style');
  style.textContent = '[data-admin-only]{display:none !important;}';
  document.head.appendChild(style);

  function isAdmin() {
    try {
      return localStorage.getItem('acharyaAuthorized') === 'true' ||
             localStorage.getItem('is_superadmin') === 'true';
    } catch (e) { return false; }
  }
  function isSuperAdmin() {
    try { return localStorage.getItem('is_superadmin') === 'true'; }
    catch (e) { return false; }
  }

  function reveal() {
    var admin = isAdmin(), superAdmin = isSuperAdmin();
    document.body.classList.toggle('dge-is-admin', admin);
    document.body.classList.toggle('dge-is-superadmin', superAdmin);
    var els = document.querySelectorAll('[data-admin-only]');
    for (var i = 0; i < els.length; i++) {
      var el = els[i];
      var need = el.getAttribute('data-admin-only');
      var ok = (need === 'super') ? superAdmin : admin;
      if (ok) el.removeAttribute('data-admin-only');
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', reveal);
  else reveal();

  // Re-run after logging in/out on the SAME page (e.g. a page that also
  // embeds the access-prompt flow) without needing a reload.
  window.DGEAdminGate = { isAdmin: isAdmin, isSuperAdmin: isSuperAdmin, refresh: reveal };
})();
