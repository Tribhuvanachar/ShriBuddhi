/* =========================================================================
   commentary-sandhi.js — mark the sandhi joins inside a commentary.

   A commentary is prose, and prose written in sandhi hides its own word
   boundaries: सन्तोऽपि is सन्तः + अपि, गुरोर्भक्तिः is गुरोः + भक्तिः,
   कान्तायेति is the verse's कान्ताय with an इति welded on. A reader who
   cannot see the join cannot look the word up.

   WHAT IS DELIBERATELY *NOT* SPLIT, and why (tools/build_padaccheda.py
   --commentary decides all of this at build time):

     · a Gold-Standard protected phrase — इत्यर्थः, इति भावः, इत्युक्ते.
       The commentary uses these as single units of punctuation.
     · a span already identified as a scholarly citation
       (tools/build_references.py). दिश अतिसर्जने is a dhātu quoted with its
       artha; the segmenter reads अतिसर्जने as अति + सः + जने, which is
       nonsense sitting inside a correct citation.
     · a pratīka — a word quoted verbatim from the verse. Cutting through one
       destroys the thing the commentary is pointing at and breaks
       pratika.js's verse↔commentary link, which is keyed on the written form.

   The build gate is narrow on purpose: two pieces, and either a closed-class
   indeclinable on the right (इति, अपि, एव, इव, हि, तु …) or a visarga seam
   that is visibly written (गुरोः + भक्तिः → गुरोर्). A wrong cut in a
   commentary reads as a claim about what the commentator wrote.

   Matching in the browser is by WORD, not by offset: the commentary may be
   showing in Kannada, Telugu or IAST by the time this runs, so each word span
   is converted back to Devanagari (highlight-words.js's dgeToDevanagariWord)
   and looked up. Same approach pratika.js uses, same reason.
   ========================================================================= */
(function () {
  'use strict';
  window.DGE_VERSIONS = window.DGE_VERSIONS || {};
  window.DGE_VERSIONS['commentary-sandhi.js'] = 'v1.0 (10 Sep 2026: सन्धिच्छेदः marks on commentary prose, with pratīka / citation / protected-phrase guards)';

  var STRIP = /^[\s"'‘’“”(){}\[\]।॥,;:.!?\-–—…]+|[\s"'‘’“”(){}\[\]।॥,;:.!?\-–—…]+$/g;

  function clean(s) { return String(s == null ? '' : s).replace(STRIP, ''); }

  function deva(word) {
    if (typeof window.dgeToDevanagariWord === 'function') {
      return clean(window.dgeToDevanagariWord(clean(word)));
    }
    return clean(word);
  }

  function enabled() {
    try {
      var flags = typeof window.dgeGetEffectiveFeatureFlags === 'function'
        ? window.dgeGetEffectiveFeatureFlags() : (window.FEATURE_FLAGS || {});
      return flags.showCommentarySandhi !== false;
    } catch (e) { return true; }
  }
  window.dgeCommentarySandhiEnabled = enabled;

  /* {written token: [left, right]} for one commentary of one verse. */
  function tableFor(unitId, cKey) {
    var data = window.dgeCommentarySandhi;
    if (!data || !data.units) return null;
    var unit = data.units[String(unitId)];
    if (!unit) return null;
    var rows = unit[cKey];
    if (!rows || !rows.length) return null;
    var out = {};
    for (var i = 0; i < rows.length; i++) {
      // [token, seams, piece, piece]
      out[rows[i][0]] = rows[i].slice(2);
    }
    return out;
  }
  window.dgeCommentarySandhiTable = tableFor;

  function unitIdOf(card) {
    var id = card && card.id ? String(card.id) : '';
    return id.indexOf('shloka-') === 0 ? id.slice(7) : '';
  }

  function markCard(card) {
    if (!card || !enabled()) return 0;
    if (card.getAttribute('data-sandhi-done') === '1') return 0;
    var unitId = unitIdOf(card);
    if (!unitId) return 0;
    var blocks = card.querySelectorAll('.commentary-block[data-ckey]');
    if (!blocks.length) return 0;
    card.setAttribute('data-sandhi-done', '1');
    var n = 0;
    for (var b = 0; b < blocks.length; b++) {
      var table = tableFor(unitId, blocks[b].getAttribute('data-ckey'));
      if (!table) continue;
      var words = blocks[b].querySelectorAll('.dge-word');
      for (var i = 0; i < words.length; i++) {
        var el = words[i];
        // A citation mark and a pratīka link are both louder claims than a
        // sandhi seam; where one is already on the word, this stays quiet
        // rather than stacking a third underline on the same characters.
        if (el.classList.contains('dge-ref') || el.classList.contains('dge-pratika')) continue;
        var pieces = table[deva(el.textContent)];
        if (!pieces) continue;
        el.classList.add('dge-sandhi');
        el.setAttribute('data-sandhi', pieces.join(' + '));
        el.setAttribute('title', 'सन्धिः · ' + pieces.join(' + '));
        n++;
      }
    }
    return n;
  }

  function markAll(root) {
    root = root || document;
    if (!enabled() || !window.dgeCommentarySandhi) return 0;
    var cards = root.querySelectorAll ? root.querySelectorAll('.shloka-card') : [];
    var n = 0;
    for (var i = 0; i < cards.length; i++) n += markCard(cards[i]);
    return n;
  }
  window.dgeCommentarySandhiMarkAll = markAll;
  window.dgeCommentarySandhiMarkCard = markCard;

  /* A tooltip is unreachable on a phone, so a tap says the same thing.
     Deliberately not a modal: the reader is mid-sentence. */
  document.addEventListener('click', function (e) {
    var el = e.target && e.target.closest ? e.target.closest('.dge-sandhi') : null;
    if (!el) return;
    var pieces = el.getAttribute('data-sandhi');
    if (pieces && typeof window.showToast === 'function') {
      window.showToast(clean(el.textContent) + ' = ' + pieces);
    }
  });
})();
