/* =========================================================================
   site-footer.js — one shared "About Us · Contact Us · Credits · License ·
   Terms & Conditions" links row, instead of the reader keeping its own
   hand-written copy while every other page that wants the same row has
   none at all.

   Usage: an empty <div id="siteFooterLinks"></div> anywhere on the page,
   plus this script tag anywhere after it. Nothing else to configure — it
   renders itself once the DOM is ready and leaves an already-filled mount
   alone, so re-including this file twice is harmless.

   Two link sets, chosen automatically:
   - The full reader app (dge/index.html) already has modals.js's
     openAboutModal()/openModal() and its own About/Contact/License/Terms
     sheets — when those exist, this renders the same five links wired to
     the same handlers, so the reader's footer behaves exactly as it did
     with its old hand-written markup.
   - Anywhere else (the landing page today; other standalone pages later,
     per the DGE shell-consolidation rollout) those functions are absent,
     so this falls back to plain destinations that need no modal system of
     their own: About Us/Credits scrolls to #architect if this very page
     has one (the landing page's own Foundation band already carries that
     content) or links to it on the landing page otherwise; Contact Us is
     a mailto using contact-email.js's window.DGE_CONTACT_EMAIL; License
     links straight to the repo's LICENSE file — the same URL the reader's
     own License sheet already points to, not a second copy of its text;
     Terms shows the reader's own "not yet written" notice via alert() —
     the one honest thing to show, since there is no real terms page yet
     for a link to point to.
   ========================================================================= */
(function () {
  'use strict';

  window.DGE_VERSIONS = window.DGE_VERSIONS || {};
  window.DGE_VERSIONS['site-footer.js'] = 'v1.0';

  var LICENSE_URL = 'https://github.com/Tribhuvanachar/bhumandala/blob/main/LICENSE';
  var TERMS_NOTICE = 'Not yet written. This site is a free, ad-free educational and ' +
    'devotional resource; a full terms-of-use page for it hasn\'t been drafted yet. ' +
    'Contact us if you have a question in the meantime.';

  // Landing-page URL, derived from THIS SCRIPT's own location (always
  // dge/js/site-footer.js) rather than a hardcoded '../index.html' --
  // pages include it from different relative depths (dge/*.html says
  // "js/site-footer.js", dge/tirtha/index.html says
  // "../js/site-footer.js"), and a fixed relative string would resolve
  // wrong on anything but the shallowest one. Same technique
  // contact-email.js already uses for admin/config/config-overrides.json.
  // Computed NOW, synchronously, while this script is still the one
  // document.currentScript points to -- render() below runs later (often
  // after a DOMContentLoaded callback), by which point currentScript is
  // back to null, so the URL has to be captured up front and reused.
  var LANDING_PAGE_URL = (function () {
    var self = (document.currentScript && document.currentScript.src) ||
               (window.DGE_SCRIPT_BASE || '');
    try { return new URL('../../index.html', self).href; }
    catch (e) { return '../index.html'; } // fail soft, never throw
  })();

  function render() {
    var mount = document.getElementById('siteFooterLinks');
    if (!mount || mount.childElementCount) return; // no mount on this page, or already built

    var hasReaderModals = typeof window.openAboutModal === 'function' &&
                           typeof window.openModal === 'function';

    var links;
    if (hasReaderModals) {
      links = [
        { label: 'About Us', onclick: "window.openAboutModal()" },
        { label: 'Contact Us', onclick: "window.openModal('contactModal')" },
        { label: 'Credits', onclick: "if(document.getElementById('creditsModal')){window.openModal('creditsModal');}else{window.openAboutModal();}" },
        { label: 'License', onclick: "window.openModal('licenseModal')" },
        { label: 'Terms &amp; Conditions', onclick: "window.openModal('termsModal')" }
      ];
    } else {
      var aboutHref = document.getElementById('architect') ? '#architect' : LANDING_PAGE_URL + '#architect';
      var email = window.DGE_CONTACT_EMAIL || 'sanatanavidyagurukulam@gmail.com';
      window.dgeShowTermsNotice = window.dgeShowTermsNotice || function () { alert(TERMS_NOTICE); };
      links = [
        { label: 'About Us', href: aboutHref },
        { label: 'Contact Us', href: 'mailto:' + email },
        { label: 'License', href: LICENSE_URL, external: true },
        { label: 'Terms &amp; Conditions', onclick: 'window.dgeShowTermsNotice()' }
      ];
    }

    mount.innerHTML = links.map(function (l, i) {
      var sep = i ? '<span class="footer-sep">·</span>' : '';
      var el = l.href
        ? '<a class="footer-link" href="' + l.href + '"' + (l.external ? ' target="_blank" rel="noopener"' : '') + '>' + l.label + '</a>'
        : '<button class="footer-link" onclick="' + l.onclick + '">' + l.label + '</button>';
      return sep + el;
    }).join('');
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', render);
  else render();
})();
