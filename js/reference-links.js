/* =========================================================================
   reference-links.js — mark the places a commentary CITES a scholarly source.

   This is the reader half of tools/reference_detect.py + tools/build_references.py,
   and it is the replacement for the generic word-marking that highlight-words.js
   used to do. The difference is the whole point:

     old   a word was marked because it existed in a database. तन्त्राणि is an
           ordinary noun that also sits in the dhātu data; भावः likewise;
           विश्व is in the kośa registry AND means "all". Most marks were
           false, and a wrong scholarly link misleads a reader in a way a
           missing one never does.

     new   a span is marked only where the build step found a citation FRAME
           around it — a root beside its own traditional artha (ज्वल
           दीप्ताविति), a lexicon named after इति (इत्यमरः), a sūtra's own
           words in quotation — and only where the thing cited was then found
           in the authoritative list. Nothing is decided in the browser.

   HOW A SPAN SURVIVES TRANSLITERATION. The build step stores each reference
   twice: char offsets into the original Devanagari ("s", kept so the source
   location is never lost) and a whitespace-token range ("w"). Rendering uses
   "w", because render.js wraps every \S+ run in its own <span class="dge-word">
   and by the time this runs the text may be in Kannada, Telugu or IAST.
   Character offsets do not survive that; token counts do.

   NO DOM SURGERY. Classes and data-attributes go onto the .dge-word spans
   that are already there, and one delegated click listener does the rest.
   Rewriting those spans into <a> elements would break pratika.js's
   word-index bookkeeping and ai.js's selection-to-word resolution, both of
   which walk the same spans.
   ========================================================================= */
(function () {
  'use strict';
  window.DGE_VERSIONS = window.DGE_VERSIONS || {};
  window.DGE_VERSIONS['reference-links.js'] = 'v1.0 (10 Sep 2026: context-aware धातु/कोश/सूत्र citation links; replaces generic lexical marking)';

  var TYPE_LABEL = { dhatu: 'धातुः', kosha: 'कोशः', sutra: 'सूत्रम्' };

  /* Where a link goes. A kośa the library does not hold has no page to open,
     so it is marked and titled but deliberately not made clickable — same
     rule kosha-citations.js states: a link that lands nowhere is worse than
     no link. tools/build_references.py's registry lists those under
     "unresolved" so the gap stays visible. */
  var HELD_KOSHAS = {
    amarakosha: 1, vachaspatyam: 1, shabdakalpadruma: 1,
    abhidhanachintamani: 1, shabdArtha_kaustubha: 1
  };

  function enabled() {
    try {
      var flags = typeof window.dgeGetEffectiveFeatureFlags === 'function'
        ? window.dgeGetEffectiveFeatureFlags() : (window.FEATURE_FLAGS || {});
      return flags.showReferenceLinks !== false;
    } catch (e) { return true; }
  }
  window.dgeReferenceLinksEnabled = enabled;

  function debugOn() {
    try { return localStorage.getItem('dge_debug_references') === '1'; } catch (e) { return false; }
  }

  /* The page this reference opens. Relative to render.html, which is where
     the reader lives. */
  function hrefFor(ref) {
    if (ref.t === 'dhatu') return 'vyakarana/prakriya.html#' + encodeURIComponent(ref.i);
    if (ref.t === 'sutra') return 'vyakarana/ashtadhyayi.html#' + encodeURIComponent(ref.i);
    if (ref.t === 'kosha') {
      return HELD_KOSHAS[ref.i] ? 'kosha2.html?browse=' + encodeURIComponent(ref.i) : '';
    }
    return '';
  }

  function titleFor(ref) {
    var t = TYPE_LABEL[ref.t] || ref.t;
    var s = t + ' · ' + (ref.l || ref.i);
    if (ref.c === 'medium') s += ' (probable)';
    if (hrefFor(ref)) s += ' — tap to open';
    return s;
  }

  /* The references for one card, from window.dgeReferences (fetched per
     grantha in core.js). Absent file, absent verse or absent commentary all
     mean the same thing: nothing to mark. */
  function refsFor(unitId, cKey) {
    var data = window.dgeReferences;
    if (!data || !data.units) return null;
    var unit = data.units[String(unitId)];
    if (!unit) return null;
    var list = unit[cKey];
    return (list && list.length) ? list : null;
  }
  window.dgeReferencesFor = refsFor;

  function unitIdOf(card) {
    var id = card && card.id ? String(card.id) : '';
    return id.indexOf('shloka-') === 0 ? id.slice(7) : '';
  }

  function markBlock(block, refs) {
    var words = block.querySelectorAll('.dge-word');
    if (!words.length) return 0;
    var n = 0;
    for (var r = 0; r < refs.length; r++) {
      var ref = refs[r];
      var a = ref.w && ref.w[0], b = ref.w && ref.w[1];
      if (!(a >= 0) || !(b > a) || b > words.length) continue;
      var href = hrefFor(ref);
      var title = titleFor(ref);
      for (var i = a; i < b; i++) {
        var el = words[i];
        // First writer wins. Overlaps are already resolved in the build step,
        // so this only guards against a re-run over a card already marked.
        if (el.classList.contains('dge-ref')) continue;
        el.classList.add('dge-ref', 'dge-ref-' + ref.t);
        if (ref.c === 'medium') el.classList.add('dge-ref-medium');
        if (i === a) el.classList.add('dge-ref-start');
        if (i === b - 1) el.classList.add('dge-ref-end');
        el.setAttribute('data-ref-type', ref.t);
        el.setAttribute('data-ref-id', ref.i == null ? '' : String(ref.i));
        el.setAttribute('data-ref-confidence', ref.c || '');
        // The ORIGINAL character range, carried through to the DOM so the
        // source location is recoverable from a rendered page (the directive's
        // "preserve source text" requirement) — and so a bug report can quote
        // exactly which characters were claimed.
        if (ref.s && ref.s.length === 2) el.setAttribute('data-ref-span', ref.s[0] + ':' + ref.s[1]);
        if (href) el.setAttribute('data-ref-href', href);
        el.setAttribute('title', title);
        n++;
      }
      if (debugOn()) {
        // Why this reference exists, not just that it does. Development only —
        // localStorage dge_debug_references='1'.
        console.log('[dge-ref] %s %s (%s) "%s" @%s — %s',
          ref.t, ref.i, ref.c, ref.x, (ref.s || []).join(':'), ref.r);
      }
    }
    return n;
  }

  function markCard(card) {
    if (!card || !enabled()) return 0;
    if (card.getAttribute('data-refs-done') === '1') return 0;
    var unitId = unitIdOf(card);
    if (!unitId) return 0;
    var blocks = card.querySelectorAll('.commentary-block[data-ckey]');
    if (!blocks.length) return 0;
    card.setAttribute('data-refs-done', '1');
    var n = 0;
    for (var b = 0; b < blocks.length; b++) {
      var refs = refsFor(unitId, blocks[b].getAttribute('data-ckey'));
      if (refs) n += markBlock(blocks[b], refs);
    }
    return n;
  }

  function markAll(root) {
    root = root || document;
    if (!enabled() || !window.dgeReferences) return 0;
    var cards = root.querySelectorAll ? root.querySelectorAll('.shloka-card') : [];
    var n = 0;
    for (var i = 0; i < cards.length; i++) n += markCard(cards[i]);
    if (n && debugOn()) console.log('[dge-ref] marked %d word spans', n);
    return n;
  }
  window.dgeReferenceMarkAll = markAll;
  window.dgeReferenceMarkCard = markCard;

  /* One delegated listener. A citation can run over several words and every
     one of them carries the target, so a tap anywhere in the span works. */
  document.addEventListener('click', function (e) {
    var el = e.target && e.target.closest ? e.target.closest('.dge-ref') : null;
    if (!el) return;
    var href = el.getAttribute('data-ref-href');
    if (!href) return;   // a lexicon this library does not hold — marked, not linked
    e.preventDefault();
    e.stopPropagation();
    window.open(href, '_blank', 'noopener');
  });
})();
