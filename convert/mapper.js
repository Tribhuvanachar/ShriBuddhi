// convert/mapper.js — Schema Mapper, window.DGE.Mapper namespace.
// Converts Gemini's generic proofread output
// ({shlokas:[{number,index,sa,commentary}]}) into the REAL DGE grantha
// schema the main reader app expects — see data/stotra/pns/data.json
// for the reference shape this targets. Deliberately a separate,
// deterministic (non-AI) step: Gemini's job stays narrow and reliable
// (correct OCR text, split shloka/commentary); assembling the exact
// nested schema — which needs admin-supplied context Gemini can't know
// (commentary key naming, grantha title/author) — happens here in code,
// where it can be validated instead of hoping an AI free-forms it right.
window.DGE = window.DGE || {};
window.DGE.Mapper = (function () {

  // profile: { title, author, slug, commentaryKey, commentaryLabel }
  // proofread: { shlokas: [{ number, index, sa, commentary }] }
  function buildGranthaJson(proofread, profile) {
    const shlokas = {};
    (proofread.shlokas || []).forEach(s => {
      // Key by the merge-safe sequential "index" (see app.js), NOT the
      // model's own "number" — Gemini restarts that field from scratch in
      // every chunk, so it routinely repeats across a multi-chunk book and
      // using it here silently drops every shloka but the last one sharing
      // a given number. "index" is exactly the plain, gapless 1..N integer
      // key every reader-app module already assumes (see the shape note in
      // js/core.js) — a real fix, not a workaround.
      const num = (s.index != null ? s.index : s.number);
      const key = String(num);
      const commentaries = {};
      if (profile.commentaryKey && s.commentary) {
        commentaries[profile.commentaryKey] = s.commentary;
      }
      shlokas[key] = { sa: s.sa || '', commentaries };
    });

    const availableCommentaries = {};
    if (profile.commentaryKey) {
      availableCommentaries[profile.commentaryKey] = profile.commentaryLabel || profile.commentaryKey;
    }

    const metadata = {
      title: profile.title || '',
      author: profile.author || '',
      stotraCode: (profile.slug || '').split('/').pop() || '',
      archiveBaseUrl: '',
      filePrefix: '',
      fileExtension: '',
      totalShlokas: Object.keys(shlokas).length,
      availableCommentaries
    };
    // Optional -- the printed closing verse ("इति ... सर्गः"), when the admin
    // chose to record it separately (matches the existing convention already
    // used by DvaitaVedanta/Itara/Kavya/sumadhva_vijaya/sarga_1..8's own data.json files). Not
    // every grantha has one; only added when actually supplied.
    if (profile.colophon) metadata.colophon = profile.colophon;

    return { metadata, shlokas };
  }

  return { buildGranthaJson };
})();
