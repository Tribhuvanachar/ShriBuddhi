/* =========================================================================
   dge-shell.js — Phase 2 of the frontend redesign: the shared global-shell
   custom elements.

   <dge-footer> — promotes site-footer.js's render() logic (the "About Us ·
   Contact Us · Credits · License · Terms & Conditions" links row) into a
   real custom element instead of a script that fills an empty mount div.
   Same two-branch behavior, same link sets, same landing-page-URL-from-
   script-src technique — this is a faithful port, not a rewrite. Usage:
   <dge-footer></dge-footer> anywhere on the page, plus this script tag
   anywhere after it (order doesn't matter relative to the tag itself,
   since custom elements upgrade whenever they're parsed or inserted).

   site-footer.js itself is UNCHANGED and still used by every page not yet
   migrated onto <dge-footer> (see the redesign plan's Phase 6 rollout
   order) — both can coexist indefinitely; a page uses exactly one of the
   two, never both.

   <dge-header>/utility-rail and a general-purpose <dge-header> wrapping the
   reader's own top-bar are deliberately NOT part of this file. The
   reader's top-bar/#actionsDrawer/popup system (dge/index.html) is a large,
   already-working, already-documented piece of the app with real
   containing-block/positioning constraints tied to its exact DOM position —
   it was never duplicated across pages (the audit that motivated this
   redesign found the Vyakarana-cluster pages' plain "<header><div
   class="bar"><div class="brand">..." markup was the actual duplication
   problem, not the reader's chrome). Wrapping the reader's top-bar in a
   custom element here would be a rewrite of working code for no benefit;
   <dge-header>'s scope is intentionally deferred to Phase 6, where it has
   a real, needed use: giving the Vyakarana cluster (and Kavya/Dasa-Sahitya/
   Tirtha/Guru-Parampara) pages a Kosha/Search utility rail they don't have
   today, alongside the breadcrumb they already do.
   ========================================================================= */
(function () {
  'use strict';

  window.DGE_VERSIONS = window.DGE_VERSIONS || {};
  window.DGE_VERSIONS['dge-shell.js'] = 'v1.0 (Phase 2: <dge-footer> custom element)';

  var LICENSE_URL = 'https://github.com/Tribhuvanachar/bhumandala/blob/main/LICENSE';
  var TERMS_NOTICE = 'Not yet written. This site is a free, ad-free educational and ' +
    'devotional resource; a full terms-of-use page for it hasn\'t been drafted yet. ' +
    'Contact us if you have a question in the meantime.';

  // Same technique as site-footer.js: captured synchronously at parse time,
  // while this script is still document.currentScript, since a custom
  // element's connectedCallback() runs later, by which point currentScript
  // has reverted to null.
  var LANDING_PAGE_URL = (function () {
    var self = (document.currentScript && document.currentScript.src) ||
               (window.DGE_SCRIPT_BASE || '');
    try { return new URL('../../index.html', self).href; }
    catch (e) { return '../index.html'; } // fail soft, never throw
  })();

  function footerLinks() {
    var hasReaderModals = typeof window.openAboutModal === 'function' &&
                           typeof window.openModal === 'function';
    if (hasReaderModals) {
      return [
        { label: 'About Us', onclick: "window.openAboutModal()" },
        { label: 'Contact Us', onclick: "window.openModal('contactModal')" },
        { label: 'Credits', onclick: "if(document.getElementById('creditsModal')){window.openModal('creditsModal');}else{window.openAboutModal();}" },
        { label: 'License', onclick: "window.openModal('licenseModal')" },
        { label: 'Terms &amp; Conditions', onclick: "window.openModal('termsModal')" }
      ];
    }
    var aboutHref = document.getElementById('architect') ? '#architect' : LANDING_PAGE_URL + '#architect';
    var email = window.DGE_CONTACT_EMAIL || 'sanatanavidyagurukulam@gmail.com';
    window.dgeShowTermsNotice = window.dgeShowTermsNotice || function () { alert(TERMS_NOTICE); };
    return [
      { label: 'About Us', href: aboutHref },
      { label: 'Contact Us', href: 'mailto:' + email },
      { label: 'License', href: LICENSE_URL, external: true },
      { label: 'Terms &amp; Conditions', onclick: 'window.dgeShowTermsNotice()' }
    ];
  }

  function renderFooterLinks(mount) {
    if (mount.childElementCount) return; // already built (e.g. re-inserted node)
    mount.innerHTML = footerLinks().map(function (l, i) {
      var sep = i ? '<span class="footer-sep">·</span>' : '';
      var el = l.href
        ? '<a class="footer-link" href="' + l.href + '"' + (l.external ? ' target="_blank" rel="noopener"' : '') + '>' + l.label + '</a>'
        : '<button class="footer-link" onclick="' + l.onclick + '">' + l.label + '</button>';
      return sep + el;
    }).join('');
  }

  class DgeFooter extends HTMLElement {
    connectedCallback() {
      this.classList.add('site-footer-links');
      renderFooterLinks(this);
    }
  }

  if (!customElements.get('dge-footer')) {
    customElements.define('dge-footer', DgeFooter);
  }
})();
