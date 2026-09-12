/* ==========================================================================
 * DGE · प्रतीकाः — the words a commentary is quoting FROM the verse, and the
 * line drawn back to where each one stands in it.
 *
 * A traditional commentary does not restate the verse; it picks a word out of
 * it, marks the pick, and glosses what follows. Sumadhva Vijaya 1.1, verbatim:
 *
 *     ।। कान्तायेति ।। कान्ताय रमणीयाय ।
 *
 * कान्तायेति is कान्ताय + इति fused (य् + इ → ये), announcing which word is
 * about to be explained; कान्ताय then recurs bare as the lemma, and रमणीयाय is
 * the gloss. A reader who cannot see that structure is reading a wall of
 * Sanskrit. A reader who can is reading a commentary.
 *
 * WHAT COUNTS AS A PRATĪKA HERE. The Gold-Standard contract (Part 0.3) is
 * strict about this and it is the right rule: a pratīka is a word that occurs
 * in the MŪLA. Not a word the commentator introduces, however emphatic — so
 * मुख्याश्रयायेत्यर्थः in that same passage is NOT marked, because
 * मुख्याश्रयाय is the commentator's own gloss and appears nowhere in the
 * verse. Requiring an actual mūla token is what keeps this from becoming a
 * bold-everything highlighter.
 *
 * And the contract's FOSSILIZED CLITIC DENYLIST (Part 0.4) is enforced
 * literally: इत्यर्थः, इति भावः, इत्याह, इत्यत आह, इति चेत्, इति चेन्न,
 * तथाहि, यद्वा, किञ्च, इत्येवमादि are the marks OF a citation and are never
 * themselves the thing cited.
 *
 * WHY NO DATA FILE. The Gold-Standard path (gold-render.js) already renders
 * pratīkas for commentary carrying word_mappings — of which this library
 * currently holds none, while it holds thousands of plain-string
 * commentaries. This finds them at render time from the two things always
 * present: the verse and the commentary. Where real word_mappings do arrive,
 * that path stays authoritative and this one steps aside.
 *
 * Script-agnostic by construction: it compares the words on screen with each
 * other, so it works in Devanagari, IAST or Kannada without transliterating
 * anything. The इति markers are the one thing that must be recognised across
 * scripts, and those go through highlight-words.js's own converter.
 * ========================================================================== */
(function () {
  "use strict";
  window.DGE_VERSIONS = window.DGE_VERSIONS || {};
  window.DGE_VERSIONS['pratika.js'] =
    'v1.0 (pratīka detection over plain-string commentary: fused-इति citation forms, ' +
    'marker-adjacent lemmas and bare mūla echoes, with bidirectional hover/tap sync ' +
    'to the word in the verse)';

  // Words that FOLLOW a citation and announce it. Devanagari is the reference
  // spelling; a word on screen in another script is converted before testing.
  var MARKERS = ['इति', 'इत्यर्थः', 'इत्यर्थ', 'इत्युक्तम्', 'इत्युक्तेः', 'इत्यनेन',
                 'इत्येतत्', 'इत्याह', 'इत्यत', 'इतियावत्', 'यावत्', 'उक्तम्', 'उक्तेः',
                 'अर्थः', 'भावः', 'शब्देन', 'शब्दः', 'शब्दात्', 'पदेन', 'पदम्', 'विशेषणम्'];

  // The contract's own denylist, plus the particles that would otherwise match
  // a mūla token constantly and mark half the page.
  var DENY = ['इति', 'इत्यर्थः', 'इत्यर्थ', 'इतिभावः', 'भावः', 'इत्याह', 'इत्यत', 'आह',
              'इतिचेत्', 'चेत्', 'चेन्न', 'तथाहि', 'यद्वा', 'किञ्च', 'इत्येवमादि',
              'यावत्', 'उक्तम्', 'उक्तेः', 'अर्थः', 'शब्देन', 'शब्दः', 'पदेन', 'पदम्',
              'एव', 'च', 'तु', 'हि', 'वा', 'न', 'स्यात्', 'अपि', 'यत्', 'तत्', 'सः', 'सा'];

  // The tails a citation's इति leaves behind when it fuses with the word
  // before it, and what the word looked like before the fusion. कान्ताय + इति
  // → कान्तायेति: the ेति comes off and the consonant keeps its inherent a.
  // गाथा + इति → गाथेति loses the ा too, so both readings are tried.
  var ITI_TAILS = [
    { tail: 'ेति',  restore: ['', 'ा'] },       // a/ā + i → e
    { tail: 'ीति',  restore: ['ि', 'ी'] },      // i/ī + i → ī
    { tail: 'िति',  restore: ['्', ''] },       // consonant + i
    { tail: 'ैति',  restore: ['े', 'ै'] },
    { tail: 'ूति',  restore: ['ु', 'ू'] },
    { tail: 'मिति', restore: ['म्'] },          // …म् + इति → …मिति
    { tail: 'रिति', restore: ['ः', 'र्'] }
  ];

  // A bare recurrence needs to be a substantial word to be evidence of
  // anything. Measured over Sumadhva Vijaya sarga 1 with three commentaries:
  // of 300 bare matches, the 87 at four characters or fewer are ये, तेन, येन,
  // तेषु, किं — pronouns and particles that coincide with a verse word rather
  // than quote it. The 213 longer ones are कान्ताय, नमस्करोमि,
  // कल्याणगुणैकधाम्ने: real lemmas standing at the head of their gloss.
  // An explicitly announced citation (fused इति, or a marker following) keeps
  // the low bar, because the announcement is itself the evidence.
  var MIN_ECHO_LEN = 5;

  var STRIP = /^[।॥॰,.;:!?"'()\[\]{}—–\-…*‘’“”\s]+|[।॥॰,.;:!?"'()\[\]{}—–\-…*‘’“”\s]+$/g;
  function clean(s) { return String(s == null ? '' : s).replace(STRIP, '').replace(/ऽ/g, ''); }

  // A word on screen, as Devanagari, for the marker/denylist tests only. The
  // pratīka match itself never needs this -- it compares screen text with
  // screen text.
  function deva(word) {
    if (typeof window.dgeToDevanagariWord === 'function') {
      return clean(window.dgeToDevanagariWord(clean(word)));
    }
    return clean(word);
  }

  function inList(list, word) { return list.indexOf(word) !== -1; }

  // Which mūla token this commentary word cites, or -1.
  //   exact      the same word, repeated as the lemma being glossed
  //   fused      the word with इति welded on, the classic citation form
  // Both are required to land on a token that is actually in the verse.
  function citedIndex(word, byText) {
    var w = clean(word);
    if (w.length < 2) return -1;
    if (Object.prototype.hasOwnProperty.call(byText, w)) return byText[w];
    for (var i = 0; i < ITI_TAILS.length; i++) {
      var t = ITI_TAILS[i];
      if (w.length <= t.tail.length) continue;
      if (w.lastIndexOf(t.tail) !== w.length - t.tail.length) continue;
      var stem = w.slice(0, w.length - t.tail.length);
      for (var r = 0; r < t.restore.length; r++) {
        var cand = stem + t.restore[r];
        if (Object.prototype.hasOwnProperty.call(byText, cand)) return byText[cand];
      }
    }
    return -1;
  }

  // Exported so the matcher can be exercised directly: which verse word a
  // commentary word cites, and whether it announced itself with a fused इति.
  // Returns null for anything that is not a citation.
  window.dgePratikaCitation = function (word, mulaWords) {
    var byText = {};
    (mulaWords || []).forEach(function (w, i) {
      var c = clean(w);
      if (c && !Object.prototype.hasOwnProperty.call(byText, c)) byText[c] = i;
    });
    var self = deva(word);
    if (inList(DENY, self)) return null;
    var idx = citedIndex(word, byText);
    if (idx < 0) return null;
    var fused = citedIndexIsFused(word, byText);
    if (!fused && clean(word).length < MIN_ECHO_LEN) return null;
    return { index: idx, fused: fused };
  };

  // The verse's own words, in order, as they appear on screen.
  function mulaTokens(card) {
    var host = card.querySelector('.shloka-text');
    if (!host) return null;
    var spans = host.querySelectorAll('.dge-word');
    if (!spans.length) return null;
    var tokens = [], byText = {};
    for (var i = 0; i < spans.length; i++) {
      var text = clean(spans[i].textContent);
      // The verse number (॥ १ ॥) is inside .verse-no and is not a word.
      if (!text || /^[०-९0-9]+$/.test(text)) { tokens.push(null); continue; }
      spans[i].classList.add('dge-mula-word');
      spans[i].setAttribute('data-mula-idx', String(i));
      tokens.push({ el: spans[i], text: text });
      if (!Object.prototype.hasOwnProperty.call(byText, text)) byText[text] = i;
    }
    return { tokens: tokens, byText: byText };
  }

  function enabled() {
    try {
      var flags = typeof window.dgeGetEffectiveFeatureFlags === 'function'
        ? window.dgeGetEffectiveFeatureFlags() : (window.FEATURE_FLAGS || {});
      return flags.showPratikaLinks !== false;
    } catch (e) { return true; }
  }
  window.dgePratikaEnabled = enabled;

  function markCard(card) {
    if (!card || !enabled() || card.getAttribute('data-pratika-done') === '1') return 0;
    var mula = mulaTokens(card);
    if (!mula) return 0;
    var blocks = card.querySelectorAll('.commentary-block');
    if (!blocks.length) return 0;
    card.setAttribute('data-pratika-done', '1');

    var found = 0;
    for (var b = 0; b < blocks.length; b++) {
      var words = blocks[b].querySelectorAll('.dge-word');
      // One pass to read the text, so the marker lookahead does not re-walk
      // the DOM for every candidate.
      var texts = [], devas = [];
      for (var i = 0; i < words.length; i++) { texts.push(clean(words[i].textContent)); devas.push(null); }
      var devaAt = function (i) {
        if (i < 0 || i >= texts.length) return '';
        if (devas[i] === null) devas[i] = deva(texts[i]);
        return devas[i];
      };
      for (var j = 0; j < words.length; j++) {
        var el = words[j];
        if (el.getAttribute('data-pratika-idx') !== null) continue;
        var self = devaAt(j);
        if (inList(DENY, self)) continue;
        var idx = citedIndex(texts[j], mula.byText);
        if (idx < 0 || !mula.tokens[idx]) continue;
        // A citation announced by its own fused इति, or by a marker within the
        // next two words, is the commentator explicitly picking this word out.
        // A bare recurrence is the lemma standing at the head of its gloss --
        // real, and worth linking, but quieter.
        var fused = citedIndexIsFused(texts[j], mula.byText);
        var marked = inList(MARKERS, devaAt(j + 1)) || inList(MARKERS, devaAt(j + 2));
        var high = fused || marked;
        if (!high && clean(texts[j]).length < MIN_ECHO_LEN) continue;
        el.classList.add('dge-pratika');
        if (!high) el.classList.add('dge-pratika-echo');
        el.setAttribute('data-pratika-idx', String(idx));
        el.setAttribute('title', high
          ? 'प्रतीकम् · quoted from the verse — tap to see it there'
          : 'the verse’s own word, glossed here — tap to see it there');
        found++;
      }
    }
    return found;
  }

  // Distinguishes "the same word again" from "the word with इति welded on".
  function citedIndexIsFused(word, byText) {
    var w = clean(word);
    if (Object.prototype.hasOwnProperty.call(byText, w)) return false;
    return citedIndex(word, byText) >= 0;
  }

  function markAll(root) {
    root = root || document;
    var cards = root.querySelectorAll ? root.querySelectorAll('.shloka-card') : [];
    var n = 0;
    for (var i = 0; i < cards.length; i++) n += markCard(cards[i]);
    return n;
  }
  window.dgePratikaMarkAll = markAll;
  window.dgePratikaMarkCard = markCard;

  /* ---- bidirectional sync ------------------------------------------------
   * Scoped to the card, so verse 3's कान्ताय never lights up verse 1's. One
   * delegated listener rather than a handler per span: a page can carry
   * thousands of these.
   */
  function partners(el) {
    var card = el.closest('.shloka-card');
    var idx = el.getAttribute('data-pratika-idx') || el.getAttribute('data-mula-idx');
    if (!card || idx === null) return [];
    var sel = el.classList.contains('dge-mula-word')
      ? '.dge-pratika[data-pratika-idx="' + idx + '"]'
      : '.dge-mula-word[data-mula-idx="' + idx + '"], .dge-pratika[data-pratika-idx="' + idx + '"]';
    var out = [];
    card.querySelectorAll(sel).forEach(function (p) { if (p !== el) out.push(p); });
    return out;
  }

  function clearSync() {
    document.querySelectorAll('.dge-pratika-sync').forEach(function (e) {
      e.classList.remove('dge-pratika-sync');
    });
  }

  function hit(e) {
    var t = e.target;
    return t && t.closest ? t.closest('.dge-pratika, .dge-mula-word[data-mula-idx]') : null;
  }

  document.addEventListener('mouseover', function (e) {
    var el = hit(e);
    if (!el) return;
    var ps = partners(el);
    if (!ps.length) return;
    el.classList.add('dge-pratika-sync');
    ps.forEach(function (p) { p.classList.add('dge-pratika-sync'); });
  });
  document.addEventListener('mouseout', function (e) { if (hit(e)) clearSync(); });

  // Tap: pulse the counterpart, and bring it into view only if it is not
  // already there -- scrolling under a reader who can already see the word is
  // just the page moving for no reason. Deliberately does NOT preventDefault:
  // a pratīka is still a word, and the word tools opening on it is right.
  document.addEventListener('click', function (e) {
    var el = hit(e);
    if (!el) return;
    var ps = partners(el);
    if (!ps.length) return;
    var target = ps[0];
    var r = target.getBoundingClientRect();
    if (r.top < 60 || r.bottom > window.innerHeight - 60) {
      target.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    ps.forEach(function (p) { p.classList.add('dge-pratika-sync'); });
    setTimeout(function () { ps.forEach(function (p) { p.classList.remove('dge-pratika-sync'); }); }, 1400);
  });
})();
