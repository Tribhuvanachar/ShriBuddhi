/* =========================================================================
   legal-content.js — fill the Credits / License / Terms modals from one
   admin-editable source, admin/content/legal.json.

   The reader ships static fallback copy inside #licenseModal / #termsModal so
   the modals are never empty if this file or the JSON fails to load; when the
   JSON is present its text wins. #creditsModal is populated entirely from the
   JSON (Credits was previously just an alias for the About modal).

   Edit the text at admin/legal.html (super-admin → Edit text → publish) or by
   hand in admin/content/legal.json — both the reader modals and that admin
   page read the same file, so there is one source of truth.
   ========================================================================= */
(function () {
  'use strict';
  window.DGE_VERSIONS = window.DGE_VERSIONS || {};
  window.DGE_VERSIONS['legal-content.js'] = 'v1.0';

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  // Credits carries structured groups; the rest are single html blobs. Only a
  // conservative tag set is trusted (the file is repo-committed, same trust as
  // every other data-driven block), and group item strings are escaped.
  function creditsHtml(c) {
    if (!c) return '';
    var h = c.intro_html || '';
    (c.groups || []).forEach(function (g) {
      h += '<p style="margin:12px 0 4px;"><strong>' + (g.heading || '') + '</strong></p><ul style="margin:0 0 4px 18px;">';
      (g.items || []).forEach(function (it) { h += '<li>' + it + '</li>'; });
      h += '</ul>';
    });
    h += c.outro_html || '';
    return h;
  }

  function fill(modalId, html, title) {
    var m = document.getElementById(modalId);
    if (!m || !html) return;
    var body = m.querySelector('.modal-body');
    if (body) body.innerHTML = html;
    if (title) {
      var h = m.querySelector('.modal-header-sticky h3');
      // keep any leading emoji already in the heading
      if (h && !/\S/.test(h.textContent.replace(/^[^\w]*$/, ''))) { /* noop */ }
    }
  }

  function contentUrl() {
    // core.js's dgeContentUrl resolves admin/content/<file> correctly whether
    // the site is served from a domain root or a project sub-path — the same
    // helper the reader uses for whats-new.json. Fall back to a page-relative
    // path (the reader lives one level deep, at dge/index.html) if it's absent.
    var base = (typeof window.dgeContentUrl === 'function')
      ? window.dgeContentUrl('legal.json')
      : '../admin/content/legal.json';
    return base + (base.indexOf('?') >= 0 ? '&' : '?') + 't=' + Date.now();
  }

  function apply(data) {
    if (!data) return;
    if (data.credits) fill('creditsModal', creditsHtml(data.credits));
    if (data.license && data.license.html) fill('licenseModal', data.license.html);
    if (data.terms && data.terms.html) fill('termsModal', data.terms.html);
  }

  function boot() {
    fetch(contentUrl(), { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(apply)
      .catch(function () { /* static fallbacks stay */ });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
