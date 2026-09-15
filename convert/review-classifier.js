// convert/review-classifier.js — combines Gemini's self-reported
// classification with the underlying OCR confidence/agreement signals into
// one of the five review classes from the DGE OCR verification policy.
// window.DGE.ReviewClassifier namespace. Pure, synchronous, no I/O.
window.DGE = window.DGE || {};
window.DGE.ReviewClassifier = (function () {

  const LABELS = {
    A: 'Auto-accepted — strong agreement, no meaningful contradiction',
    B: 'High confidence — minor disagreement, strong evidence',
    C: 'AI-assisted — OCR conflict resolved by Gemini using context',
    D: 'Human review — substantial conflict, low confidence, or difficult typography',
    E: 'Unresolved — no defensible candidate'
  };

  // classification: Gemini's own self-report ('accept'|'review'|'unresolved'),
  //   or undefined for legacy/unclassified data (proofread before this existed).
  // avgConfidence: Vision's average word confidence for the source page (0-1 or null).
  // crossCheckSimilarity: Tesseract-vs-Vision similarity for the source page
  //   (0-1, or null if the cross-check wasn't run for that page).
  //
  // Gemini's self-report is the primary signal — it actually saw both
  // candidates (when there were two) and used context, which the raw
  // numbers alone don't capture. The confidence/agreement numbers refine
  // within that: they escalate a Gemini "review" to human-required "D" when
  // the underlying evidence was severely weak even after Gemini's attempt,
  // and they distinguish a solid "A" from a merely-adequate "B" acceptance.
  function classify({ classification, avgConfidence, crossCheckSimilarity }) {
    if (classification === 'unresolved') return 'E';
    if (classification === 'review') {
      const severelyWeak = (typeof avgConfidence === 'number' && avgConfidence < 0.6) ||
                            (typeof crossCheckSimilarity === 'number' && crossCheckSimilarity < 0.5);
      return severelyWeak ? 'D' : 'C';
    }
    // classification === 'accept', or missing (legacy data) — treated the
    // same as "accept" rather than escalated, since there's no signal
    // suggesting otherwise.
    const strongEvidence = (avgConfidence == null || avgConfidence >= 0.9) &&
                            (crossCheckSimilarity == null || crossCheckSimilarity >= 0.9);
    return strongEvidence ? 'A' : 'B';
  }

  return { classify, LABELS };
})();
