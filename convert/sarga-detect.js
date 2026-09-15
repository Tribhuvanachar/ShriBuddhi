// convert/sarga-detect.js — window.DGE.SargaDetect namespace.
//
// Scans a Proofread run's merged shlokas for sarga-boundary markers so a
// batch that actually spans multiple sargas (a real thing that happened —
// see PENDING.md's "sarga_10" entry) gets split into the right number of
// files instead of one mislabeled one. Two marker types, both real
// conventions in printed kavya texts:
//   - chapter-opening: "अथ <ordinal> सर्गः" (e.g. "अथ पञ्चदशः सर्गः")
//   - closing colophon: "इति ... <ordinal> सर्गः" (e.g. "...आनन्दाङ्किते
//     एकादशः सर्गः")
//
// Deliberately conservative: only claims a segment IS a single confident
// sarga number when the evidence actually says so cleanly. A stretch where
// the numbering can't be pinned down (a real, observed failure mode — see
// below) is labeled as an honest range ("sarga_12_to_14") rather than a
// guessed single number — the whole point of building this is to stop
// producing confidently-wrong labels, not to produce a different kind of
// confidently-wrong label.
window.DGE = window.DGE || {};
window.DGE.SargaDetect = (function () {

  // Sanskrit ordinal words for सर्गः (masculine), 1-30 — covers the vast
  // majority of real kavyas. A word not in this list simply isn't
  // recognized as a boundary (falls through to "no anchor found here"),
  // which is the safe direction to fail in.
  var ORDINALS = {
    'प्रथमः': 1, 'द्वितीयः': 2, 'तृतीयः': 3, 'चतुर्थः': 4, 'पञ्चमः': 5, 'षष्ठः': 6, 'सप्तमः': 7,
    'अष्टमः': 8, 'नवमः': 9, 'दशमः': 10, 'एकादशः': 11, 'द्वादशः': 12, 'त्रयोदशः': 13, 'चतुर्दशः': 14,
    'पञ्चदशः': 15, 'षोडशः': 16, 'सप्तदशः': 17, 'अष्टादशः': 18, 'एकोनविंशः': 19, 'नवदशः': 19,
    'विंशः': 20, 'एकविंशः': 21, 'द्वाविंशः': 22, 'त्रयोविंशः': 23, 'चतुर्विंशः': 24, 'पञ्चविंशः': 25,
    'षड्विंशः': 26, 'सप्तविंशः': 27, 'अष्टाविंशः': 28, 'एकोनत्रिंशः': 29, 'नवविंशः': 29, 'त्रिंशः': 30
  };
  // Longest words first so e.g. "त्रयोदशः" isn't partially shadowed by a
  // shorter alternation branch matching first.
  var ORDINAL_ALTERNATION = Object.keys(ORDINALS).sort(function (a, b) { return b.length - a.length; }).join('|');
  var CHAPTER_OPEN_RE = new RegExp('अथ\\s+(' + ORDINAL_ALTERNATION + ')\\s*सर्गः?', 'g');
  var COLOPHON_RE = new RegExp('इति[\\s\\S]{0,200}?(' + ORDINAL_ALTERNATION + ')\\s*सर्गः?', 'g');

  // Reverse of ORDINALS, for turning a plain sarga number back into its
  // Sanskrit ordinal word -- used by the manual "split sarga here" editor
  // control to suggest a colophon/heading for a newly-created segment.
  var NUMBER_TO_ORDINAL = {};
  Object.keys(ORDINALS).forEach(function (word) { NUMBER_TO_ORDINAL[ORDINALS[word]] = word; });
  function ordinalWord(n) { return NUMBER_TO_ORDINAL[n] || null; }

  // Swaps whichever ORDINALS word already appears in an existing colophon
  // (e.g. a sibling sarga's own metadata.colophon) for the ordinal matching
  // targetNum -- lets the editor suggest "...आनन्दाङ्किते द्वादशः सर्गः" from
  // "...आनन्दाङ्किते एकादशः सर्गः" without knowing this work's own lineage/title
  // wording. Returns null if no ordinal word is found to swap (caller should
  // fall back to leaving the field blank rather than guessing the wrong text).
  function suggestColophon(existingColophon, targetNum) {
    var word = ordinalWord(targetNum);
    if (!word || !existingColophon) return null;
    var re = new RegExp('(' + ORDINAL_ALTERNATION + ')(\\s*सर्गः?)', '');
    var m = re.exec(existingColophon);
    if (!m) return null;
    return existingColophon.slice(0, m.index) + word + m[2] + existingColophon.slice(m.index + m[0].length);
  }

  // Finds every boundary marker across the ordered shloka list. Returns
  // anchors sorted by position; 'start' = this shloka begins the named
  // sarga, 'end' = this shloka is the last verse of (or carries the
  // colophon for) the named sarga.
  function detectAnchors(shlokas) {
    var anchors = [];
    (shlokas || []).forEach(function (s, i) {
      // Confirmed directly against two independent real Gemini runs on the
      // same source content: a chapter-opening/closing line can legitimately
      // land in EITHER "sa" or "commentary" depending on how that specific
      // run split mula-verse text from explanatory material -- both are
      // reasonable readings of the same page, and Gemini isn't consistent
      // about which one it picks run to run. Checking "sa" alone silently
      // missed a real sarga 10/11 boundary in one such run (the two sargas
      // merged into one 133-shloka segment instead of splitting) purely
      // because that run's colophon happened to land in "commentary".
      var text = ((s && s.sa) || '') + '\n' + ((s && s.commentary) || '');
      var m;
      CHAPTER_OPEN_RE.lastIndex = 0;
      while ((m = CHAPTER_OPEN_RE.exec(text))) anchors.push({ pos: i, type: 'start', number: ORDINALS[m[1]] });
      COLOPHON_RE.lastIndex = 0;
      while ((m = COLOPHON_RE.exec(text))) anchors.push({ pos: i, type: 'end', number: ORDINALS[m[1]] });
    });
    anchors.sort(function (a, b) { return a.pos - b.pos; });
    return anchors;
  }

  function describeRange(startNum, endNum) {
    if (startNum != null && endNum != null) return startNum === endNum ? String(startNum) : (startNum + '_to_' + endNum);
    if (startNum != null) return startNum + '_onward';
    if (endNum != null) return 'through_' + endNum;
    return 'unknown';
  }

  // Builds segments from the anchors -- see the file header for the
  // reasoning. fallbackNumber is the sarga number the admin originally
  // chose as this batch's target (used only as a weak starting guess for
  // whatever comes before the first anchor).
  function buildSegments(anchors, totalCount, fallbackNumber) {
    if (!totalCount) return [];
    var facts = [{ pos: 0, number: fallbackNumber, type: 'initial' }]
      .concat(anchors)
      .concat([{ pos: totalCount, number: null, type: 'virtual-end' }]);

    var segments = [];
    for (var i = 0; i < facts.length - 1; i++) {
      var a = facts[i], b = facts[i + 1];
      var segStart = a.pos + (a.type === 'end' ? 1 : 0);
      var segEnd = b.pos - (b.type === 'start' ? 1 : 0) - (b.type === 'virtual-end' ? 1 : 0);
      if (segStart > segEnd) continue; // nothing between these two facts

      // If the left-hand fact was an 'end' anchor, that sarga is already
      // closed off (it belongs to the PREVIOUS segment) -- this new
      // segment starts at the NEXT number, not the one that just ended.
      var startNum = (a.type === 'end' && a.number != null) ? a.number + 1 : a.number;
      var endNum;
      if (b.type === 'start') endNum = (b.number != null) ? b.number - 1 : null;
      else if (b.type === 'end') endNum = b.number;
      else endNum = null; // virtual-end -- genuinely unbounded above

      if (startNum != null && endNum != null && startNum === endNum) {
        segments.push({ startIdx: segStart, endIdx: segEnd, sargaNumber: startNum, confident: true });
      } else if (startNum != null && endNum == null && b.type === 'virtual-end') {
        // Trailing segment after the last anchor, nothing contradicts the
        // starting number -- most likely just that sarga still in progress
        // (the batch ended before its colophon). Confident, not a range.
        segments.push({ startIdx: segStart, endIdx: segEnd, sargaNumber: startNum, confident: true, trailing: true });
      } else {
        segments.push({
          startIdx: segStart, endIdx: segEnd, sargaNumber: null,
          rangeLabel: describeRange(startNum, endNum), confident: false
        });
      }
    }
    return segments;
  }

  // Convenience: full pipeline, mergedShlokas -> segments. fallbackNumber
  // should be parsed from the admin's originally-chosen target slug's
  // trailing "sarga_N" (or similar) segment, if present.
  function detectSegments(mergedShlokas, fallbackNumber) {
    var anchors = detectAnchors(mergedShlokas);
    return buildSegments(anchors, (mergedShlokas || []).length, fallbackNumber);
  }

  return {
    ORDINALS: ORDINALS, detectAnchors: detectAnchors, buildSegments: buildSegments, detectSegments: detectSegments,
    ordinalWord: ordinalWord, suggestColophon: suggestColophon
  };
})();
