/* private-names.js -- the names that exist in ShriBuddhi and never in public.
 *
 * NOT PUBLISHED. publish_clean_repo.py's EXCLUDE_GLOBS drops it, so the
 * public site loads nothing here and the globals below stay undefined. Every
 * reader of them treats that as "no private names", which is the correct
 * answer out there: those trees have no public path, so nothing public can
 * ever need to label or lint one.
 *
 * It exists because two published files used to carry the names inline --
 * js/library.js as breadcrumb labels and js/admin-editor.js as a folder-name
 * lint allowlist -- and both shipped `DvaitaVedantaIn` and `Anandamakaranda`
 * in plain sight. Neither needed to: one labels a breadcrumb that is not
 * shown publicly, the other exempts a folder that cannot be edited publicly.
 * Moving them here keeps both working where they are used, in the private
 * checkout, and leaves nothing behind in the published copy.
 */
(function (w) {
  'use strict';

  /* Folder segments that are PascalCase on purpose, so admin-editor.js's
   * naming lint does not nag about them on every load. */
  w.DGE_PRIVATE_PASCAL_CASE = ['DvaitaVedantaIn', 'Anandamakaranda', 'RamanujaMeghamala'];

  /* Breadcrumb labels for those same shelves, for an admin browsing the
   * private checkout where the real paths are what the page is built from. */
  w.DGE_PRIVATE_LABELS = {
    DvaitaVedantaIn: 'द्वैतसाहित्यम्',
    Anandamakaranda: 'सर्वमूलग्रन्थाः',
    RamanujaMeghamala: 'रामानुजमेघमाला'
  };
}(typeof window !== 'undefined' ? window : this));
