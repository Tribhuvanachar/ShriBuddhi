/* =========================================================================
   dge-breadcrumb.js — Phase 2 of the frontend redesign.

   <dge-breadcrumb> is a drop-in replacement for the hand-written
   "<div class="brand"><a href="index.html">⌂ DGE</a><span>›</span>
   <span>Page Name</span></div>" markup duplicated across the 13 pages that
   share vyakarana-base.css's/kavya's/dasa-sahitya's/tirtha's/guru-
   parampara's .brand styling (see dge/css/vyakarana-base.css's own .brand
   rules, unchanged by this file). Renders the exact same DOM shape and
   classes those rules already target, so adopting it needs no CSS change.

   Usage:
     <dge-breadcrumb label="अष्टाध्यायी"></dge-breadcrumb>
       -> ⌂ DGE › अष्टाध्यायी                          (1-level, the common case)

     <dge-breadcrumb parent-label="धातुपाठः" parent-href="dhatu.html"
                      label="रूपाणि"></dge-breadcrumb>
       -> ⌂ DGE › धातुपाठः › रूपाणि                     (2-level, e.g. Dhatuforms/
                                                          Rupasiddhi/Prakriya/Krdanta
                                                          under Dhatupatha today)

     <dge-breadcrumb label="काव्यानि" deva></dge-breadcrumb>
       -> same, with the leaf label wrapped in <span class="deva"> for pages
          (Ashtadhyayi) that render it in Devanagari-specific type.

   home-href defaults to "index.html" (correct for every page one directory
   below dge/); pages one level deeper (dge/tirtha/, dge/guru-parampara/)
   pass home-href="../index.html".

   NOT WIRED INTO ANY PAGE YET as of Phase 2 — this is infrastructure ready
   for Phase 6's page-by-page migration, built and smoke-tested now so that
   work doesn't also have to invent the component. See dge-shell.js's own
   header comment for why <dge-header>/utility-rail are deferred the same
   way, and why the reader's own top-bar is out of scope entirely.
   ========================================================================= */
(function () {
  'use strict';

  window.DGE_VERSIONS = window.DGE_VERSIONS || {};
  window.DGE_VERSIONS['dge-breadcrumb.js'] = 'v1.0 (Phase 2, not yet adopted by any page)';

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  class DgeBreadcrumb extends HTMLElement {
    connectedCallback() {
      if (this.childElementCount) return; // already built
      this.classList.add('brand');

      var homeHref = this.getAttribute('home-href') || 'index.html';
      var homeLabel = this.getAttribute('home-label') || '⌂ DGE';
      var parentLabel = this.getAttribute('parent-label');
      var parentHref = this.getAttribute('parent-href');
      var label = this.getAttribute('label') || '';
      var isDeva = this.hasAttribute('deva');

      var parentClass = isDeva ? ' class="deva"' : '';
      var html = '<a href="' + esc(homeHref) + '" title="DGE Home">' + esc(homeLabel) + '</a>';
      if (parentLabel) {
        html += '<span aria-hidden="true">›</span>';
        html += parentHref
          ? '<a href="' + esc(parentHref) + '"' + parentClass + '>' + esc(parentLabel) + '</a>'
          : '<span' + parentClass + '>' + esc(parentLabel) + '</span>';
      }
      html += '<span aria-hidden="true">›</span>';
      html += isDeva
        ? '<span class="deva">' + esc(label) + '</span>'
        : '<span>' + esc(label) + '</span>';

      this.innerHTML = html;
    }
  }

  if (!customElements.get('dge-breadcrumb')) {
    customElements.define('dge-breadcrumb', DgeBreadcrumb);
  }
})();
