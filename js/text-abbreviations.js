/* =========================================================================
   Global short-URL abbreviations for deep-linking a grantha + shloka in one
   query param, e.g. ?SMV=1.1 for Sumadhva Vijaya, sarga 1, shloka 1 —
   instead of the verbose ?path=DvaitaVedanta/Itara/Kavya/sumadhva_vijaya/sarga_1&
   jumpShloka=1 the reader (core.js) already understands.

   Add an entry here and it works immediately, on every page that loads this
   script before core.js — no change to core.js's own logic needed. This is
   the ONE place these are configured, by design (the report's "globally
   configurable, strictly tied to their corresponding backend folders").

   path: the grantha slug under data/, exactly as index.html's own ?path=
         param expects it. Include {ch} where the work is split into
         per-chapter files (sarga_1, sarga_2, ...), the way Sumadhva Vijaya
         is — core.js substitutes the chapter number from the query value
         there. An abbreviation with no {ch} in its path is a single-file
         grantha; the whole query value is then the shloka number.
   ========================================================================= */
window.DGE_TEXT_ABBREVIATIONS = {
  SMV: {
    path: 'DvaitaVedanta/Itara/Kavya/sumadhva_vijaya/sarga_{ch}',
    label: 'Sumadhva Vijaya'
  }
};
