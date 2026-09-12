/* ==========================================================================
 * DGE · शब्दचिह्नानि — the background colour on a word that says "this one
 * goes somewhere".
 *
 * The project lead asked (9 Sep 2026) for "dhatus in the sloka highlighted
 * with a special background color" and for "matched koshas in the commentary"
 * to carry the same mark. Two separate marks, one mechanism:
 *
 *   धातुः   the written form is an inflected verb form we hold a full
 *           derivation for (prakriya/formindex, 204,975 forms), or the
 *           per-grantha dhātu-occurrence index named it in THIS verse
 *   कोशः    the written form is a headword in a shipped dictionary
 *
 * A mark is a promise that tapping the word gets you somewhere, and nothing
 * more. It is NOT a claim that the word has been analysed: an inflected form
 * inside a commentary is usually not a कोश headword, and it stays unmarked
 * rather than being guessed at. That restraint is what keeps the marking
 * useful — a page where every word is coloured says nothing.
 *
 * WHY A POST-RENDER DOM PASS rather than marks baked into the HTML string.
 * The answer needs a fetch (tools/build_highlight_index.py shards the word
 * lists two characters deep so a card pulls ~10 KB, not 3.5 MB), and the
 * renderer is synchronous. Marking afterwards means the verse paints
 * immediately and the colour arrives when it arrives; it also means the SAME
 * pass covers the mūla, every commentary block, and anything a later feature
 * renders, as long as the words sit in .dge-word spans.
 * ========================================================================== */
(function () {
  "use strict";
  window.DGE_VERSIONS = window.DGE_VERSIONS || {};
  window.DGE_VERSIONS['highlight-words.js'] =
    'v1.0 (धातु/कोश word marking from the sharded presence index, applied as a ' +
    'post-render DOM pass over .dge-word spans in the mūla and commentaries)';

  var BASE = 'data/_highlight';
  var MARK_KOSHA = 1;
  var MARK_DHATU = 2;

  // Must match normalise() in tools/build_highlight_index.py exactly: the two
  // sides are looking each other up, and a punctuation mark stripped on one
  // side but not the other is a silent miss for every word ending in a danda.
  var STRIP_CHARS = '।॥॰,.;:!?"\'()[]{}—–-…*​‌‍⁠';
  // Every character escaped individually rather than dropped into the class
  // as written: '–-…' would otherwise read as a RANGE from U+2013 to U+2026
  // and quietly strip a dozen characters nobody listed.
  var STRIP_CLASS = STRIP_CHARS.replace(/[.*+?^${}()|[\]\\\-]/g, '\\$&');
  var STRIP_RE = new RegExp('^[' + STRIP_CLASS + '\\s]+|[' + STRIP_CLASS + '\\s]+$', 'g');

  function normalise(word) {
    var w = String(word || '').replace(STRIP_RE, '');
    w = w.replace(/ऽ/g, '');
    return w.replace(STRIP_RE, '');
  }

  function prefixOf(word, depth) {
    var out = '';
    for (var i = 0; i < depth; i++) {
      out += i < word.length ? ('000' + word.charCodeAt(i).toString(16)).slice(-4) : '0000';
    }
    return out;
  }

  var manifestP = null;
  function manifest() {
    if (!manifestP) {
      manifestP = fetch(BASE + '/manifest.json', { cache: 'force-cache' })
        .then(function (r) { return r.ok ? r.json() : null; })
        .catch(function () { return null; });
    }
    return manifestP;
  }

  // A prefix listed as `deep` was split a character further because two
  // characters left it too large (वि- alone holds 8,700 verb forms). Same
  // walk-down the कोश reader does with its own oversized buckets.
  function shardNameFor(word, m) {
    var name = prefixOf(word, 2);
    if (m && m.deep && m.deep.indexOf(name) !== -1) name = prefixOf(word, 3);
    return name;
  }

  var shardCache = {};
  function loadShard(name) {
    if (!shardCache[name]) {
      shardCache[name] = fetch(BASE + '/' + name + '.json', { cache: 'force-cache' })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (raw) {
          // The shard is three newline-joined runs rather than word->number;
          // expanded here once per shard, then reused from cache.
          var out = {};
          if (!raw) return out;
          [['k', MARK_KOSHA], ['d', MARK_DHATU], ['b', MARK_KOSHA | MARK_DHATU]].forEach(function (pair) {
            var run = raw[pair[0]];
            if (!run) return;
            run.split('\n').forEach(function (w) { if (w) out[w] = pair[1]; });
          });
          return out;
        })
        .catch(function () { return {}; });
    }
    return shardCache[name];
  }

  // Exported: the marking pass is not the only thing that needs to know what
  // an on-screen word could be in Devanagari, and a private version would be
  // reimplemented worse elsewhere.
  window.dgeDevanagariCandidates = devanagariCandidates;

  // The lookup key for a word as it appears on screen: normalised, then
  // carried back to Devanagari if the reader is in another script. This is the
  // single best guess; devanagariCandidates() above is the full set, and the
  // index picks between them.
  function keyFor(raw) {
    var w = normalise(raw);
    if (!w) return '';
    if (scriptIsDevanagari()) return w;
    // Normalise again after transliterating: a danda survives the round trip
    // in some schemes and would otherwise be part of the key.
    return normalise(toDevanagari(w));
  }
  window.dgeWordMarkKey = keyFor;

  // Which Devanagari reading of an on-screen word the index actually knows.
  // Filled in by the marking pass and read back by the word tools, so a tap in
  // Tamil opens the word the mark was for rather than a spelling that only
  // survived the round trip.
  var resolved = {};
  function rememberResolved(scheme, shown, deva) { resolved[scheme + '\u0000' + shown] = deva; }
  window.dgeResolvedDevanagari = function (shown) {
    return resolved[(activeScheme() || '') + '\u0000' + normalise(shown)] || '';
  };

  // The Devanagari reading of a word as it appears on screen, for anything
  // that has to look it up in this library's data. Every index the word tools
  // consult -- the verb form index, the शब्दपाठः, the कोश, the corpus search
  // index -- is Devanagari-keyed, so a reader in Kannada or IAST was looking
  // up a spelling that could not be there. Exported from here because this is
  // where the transliteration and its cache already live.
  //
  // A round trip is not always lossless, and this does not pretend otherwise:
  // Tamil writes क ख ग घ with one letter, so a word carried into Tamil and
  // back may come back as a different word, and it simply will not be found.
  // The other scripts the reader can choose are one-to-one with Devanagari.
  window.dgeToDevanagariWord = function (word) {
    var w = String(word == null ? '' : word);
    if (!w || scriptIsDevanagari() || !canTransliterate()) return w;
    // A reading the marking pass already validated against the index beats the
    // plain back-transliteration, which in Tamil is usually a different word.
    return window.dgeResolvedDevanagari(w) || toDevanagari(w) || w;
  };

  // words -> { word-as-given: mask }, fetching only the shards those words
  // actually land in. Deduplicated, so a page of 25 verses costs the same as
  // one verse for every shard they share. Keyed back by the caller's own
  // spelling, so a caller in IAST never has to know a Devanagari key existed.
  function wordMarks(words) {
    return manifest().then(function (m) {
      var need = {}, candsOf = {};
      var scheme = activeScheme() || '';
      words.forEach(function (raw) {
        if (Object.prototype.hasOwnProperty.call(candsOf, raw)) return;
        var cands = devanagariCandidates(raw).filter(function (c) { return c.length >= 2; });
        candsOf[raw] = cands;
        // Only the shards the candidates land in. Candidates share their first
        // letters' alternatives, so this is a handful of shards even when the
        // candidate list is long -- and exactly one shard for a script that
        // round-trips.
        cands.forEach(function (c) { need[shardNameFor(c, m)] = 1; });
      });
      var names = Object.keys(need);
      if (!names.length) return {};
      return Promise.all(names.map(loadShard)).then(function (shards) {
        var bySharded = {};
        names.forEach(function (n, i) { bySharded[n] = shards[i] || {}; });
        var out = {};
        Object.keys(candsOf).forEach(function (raw) {
          var cands = candsOf[raw];
          for (var i = 0; i < cands.length; i++) {
            var mask = bySharded[shardNameFor(cands[i], m)][cands[i]];
            if (mask) {
              out[raw] = mask;
              if (scheme && scheme !== 'devanagari') rememberResolved(scheme, normalise(raw), cands[i]);
              return;
            }
          }
        });
        return out;
      });
    }).catch(function () { return {}; });
  }
  window.dgeWordMarks = wordMarks;

  // ---- reading a word in whatever script it is on screen ------------------
  // The index is keyed by Devanagari, because that is what the corpus and the
  // dictionaries are written in. A reader in IAST or Kannada is looking at
  // transliterations, so the word has to be carried back to Devanagari before
  // the lookup can be attempted at all — otherwise the marks simply never
  // appear, with nothing to say why.
  //
  // Sanscript is vendored (js/vendor/README.md) rather than fetched from a
  // CDN precisely so this cannot go quiet on a bad connection. If it is
  // somehow absent, the marks stand down outside Devanagari rather than
  // guessing: an unmarked page is honest, a wrongly marked one is not.
  // Every id in config.js's SCRIPT_OPTIONS must appear here, or the marks
  // stand down in that script with nothing to say why. 'hindi' and 'marathi'
  // are Devanagari under another name (see transliteration.js), so they are
  // not transliterated at all — a round trip would be lossy for nothing.
  var SCRIPT_SCHEME = {
    devanagari: 'devanagari', deva: 'devanagari', hindi: 'devanagari', marathi: 'devanagari',
    iast: 'iast', kannada: 'kannada', telugu: 'telugu',
    tamil: 'tamil', malayalam: 'malayalam', gujarati: 'gujarati',
    bengali: 'bengali', oriya: 'oriya', gurmukhi: 'gurmukhi', hk: 'hk', slp1: 'slp1'
  };

  function activeScheme() {
    return SCRIPT_SCHEME[window.activeScript || 'devanagari'] || null;
  }

  function scriptIsDevanagari() { return activeScheme() === 'devanagari'; }

  function canTransliterate() {
    return !!(window.Sanscript && typeof window.Sanscript.t === 'function') && !!activeScheme();
  }

  // Transliteration is per distinct word and memoised for the life of the
  // page: a commentary repeats the same particles hundreds of times, and
  // Sanscript.t is not free.
  // Keyed by scheme as well as word: the same string means different things in
  // IAST and in Kannada, and the reader can switch script without a reload.
  var toDevaCache = {};
  function toDevanagari(word) {
    var scheme = activeScheme();
    if (scheme === 'devanagari') return word;
    var key = scheme + '\u0000' + word;
    if (Object.prototype.hasOwnProperty.call(toDevaCache, key)) return toDevaCache[key];
    var out = '';
    try { out = window.Sanscript.t(word, scheme, 'devanagari') || ''; } catch (e) { out = ''; }
    toDevaCache[key] = out;
    return out;
  }

  /* ---- scripts that do not round-trip ------------------------------------
   * Devanagari → any script is a function; the way back is not always. Tamil
   * writes क ख ग घ with one letter and has no anusvāra, so carrying a word
   * out to Tamil and back returns the SAME word only 11.5% of the time
   * (measured over 35,687 index keys); Bengali writes ब and व alike, 94.6%.
   * Every other script the reader can pick — Kannada, Telugu, Malayalam,
   * Odia, IAST — comes back intact 100% of the time and never reaches any of
   * this.
   *
   * So for those two, the back-reading is treated as a PATTERN rather than an
   * answer: expand every position the target script could have written
   * ambiguously, and let the index say which reading is a real word. Same
   * principle the sandhi splitter runs on — generate candidates, validate
   * against the word lists we ship, discard the rest. That takes Tamil from
   * 11.5% to 94%.
   *
   * The table is DERIVED from Sanscript's own schemes at first use, not
   * written out here: probing every Devanagari unit for what it becomes and
   * what that becomes on the way back is the only version that cannot drift
   * out of step with the library, and it costs a few milliseconds once.
   */
  var CANDIDATE_CAP = 256;      // 93.6% at 64, 94.0% at 256, 94.7% uncapped
  var backTables = {};

  function backTable(scheme) {
    if (backTables[scheme]) return backTables[scheme];
    var S = window.Sanscript, byBack = {};
    var units = [], c;
    for (c = 0x0900; c <= 0x097f; c++) units.push(String.fromCharCode(c));
    // म् is two codepoints and collides with ं in Tamil — a single-character
    // scan cannot see that, and misses every word with a nasal.
    for (c = 0x0915; c <= 0x0939; c++) units.push(String.fromCharCode(c) + '्');
    units.forEach(function (u) {
      var fwd, back;
      try { fwd = S.t(u, 'devanagari', scheme); back = S.t(fwd, scheme, 'devanagari'); } catch (e) { return; }
      if (!fwd || !back) return;
      if (!byBack[back]) byBack[back] = [];
      if (byBack[back].indexOf(u) === -1) byBack[back].push(u);
    });
    var table = {};
    Object.keys(byBack).forEach(function (back) {
      var alts = byBack[back].slice();
      if (alts.indexOf(back) === -1) alts.push(back);
      // Only worth a table entry where the back-reading is not simply itself.
      if (alts.length > 1 || alts[0] !== back) table[back] = alts;
    });
    backTables[scheme] = {
      map: table,
      // Longest first, so ङ्क् is matched before क्.
      keys: Object.keys(table).sort(function (a, b) { return b.length - a.length; })
    };
    return backTables[scheme];
  }

  // Every Devanagari word the on-screen word could be. The first element is
  // the plain back-reading, so a script that round-trips exactly gets a
  // one-element list and none of the machinery below ever runs.
  function devanagariCandidates(word) {
    var plain = normalise(toDevanagari(normalise(word)));
    if (!plain || scriptIsDevanagari()) return plain ? [plain] : [];
    var t = backTable(activeScheme());
    if (!t.keys.length) return [plain];
    var out = [''], i = 0;
    while (i < plain.length) {
      var key = null, k;
      for (k = 0; k < t.keys.length; k++) {
        if (plain.lastIndexOf(t.keys[k], i) === i) { key = t.keys[k]; break; }
      }
      var alts = key ? t.map[key] : [plain.charAt(i)];
      var next = [];
      for (var p = 0; p < out.length; p++) {
        for (var a = 0; a < alts.length; a++) {
          next.push(out[p] + alts[a]);
          if (next.length > CANDIDATE_CAP) return [plain];   // give up, keep the plain reading
        }
      }
      out = next;
      i += key ? key.length : 1;
    }
    // The plain reading leads: where it is itself a real word, it wins.
    if (out.indexOf(plain) > 0) { out.splice(out.indexOf(plain), 1); out.unshift(plain); }
    return out;
  }

  function marksEnabled() {
    var scriptOk = scriptIsDevanagari() || canTransliterate();
    try {
      var flags = typeof window.dgeGetEffectiveFeatureFlags === 'function'
        ? window.dgeGetEffectiveFeatureFlags() : (window.FEATURE_FLAGS || {});
      return flags.showWordMarks !== false && scriptOk;
    } catch (e) { return scriptOk; }
  }
  window.dgeWordMarksEnabled = marksEnabled;

  // The per-grantha dhātu-occurrence index (dgeDhatuHits) is the stronger
  // signal where it exists: it names the forms a corpus pass actually
  // resolved in THIS verse, disambiguated, rather than merely asserting the
  // spelling is a possible verb form. Folded in so a verse the corpus pass
  // covered is marked even for a form the flat index happens to miss.
  function verseDhatuWords() {
    var hits = window.dgeDhatuHits;
    var out = {};
    if (!hits) return out;
    Object.keys(hits).forEach(function (k) {
      var list = hits[k];
      if (!list || !list.length) return;
      list.forEach(function (h) {
        // These come from the corpus index and are always Devanagari, whatever
        // script the page is displaying — no transliteration on this side.
        var w = normalise(Array.isArray(h) ? h[0] : (h && h.word));
        if (w) out[w] = 1;
      });
    });
    return out;
  }

  var CLASS_FOR = {};
  CLASS_FOR[MARK_KOSHA] = 'dge-mark-kosha';
  CLASS_FOR[MARK_DHATU] = 'dge-mark-dhatu';
  CLASS_FOR[MARK_KOSHA | MARK_DHATU] = 'dge-mark-both';

  var TITLE_FOR = {};
  TITLE_FOR[MARK_KOSHA] = 'कोशे विद्यते · a dictionary headword — tap for its entry';
  TITLE_FOR[MARK_DHATU] = 'धातुरूपम् · a verb form — tap for its derivation';
  TITLE_FOR[MARK_KOSHA | MARK_DHATU] = 'धातुरूपम् · कोशे च विद्यते — tap for its derivation and entry';

  // Running totals for the legend. Cards are marked one at a time as they
  // scroll in, so the legend has to accumulate rather than report the last
  // card -- otherwise it would flicker off on the first card that happens to
  // contain neither kind of word. Reset when the list is re-rendered.
  var tally = { dhatu: 0, kosha: 0 };

  // Marks every unmarked .dge-word under `root`. Idempotent: a span already
  // carrying data-dge-mark is skipped, so re-running after a partial re-render
  // costs nothing and never double-marks.
  function markUnder(root) {
    if (!marksEnabled()) {
      root.querySelectorAll('[data-dge-mark]').forEach(function (el) {
        el.classList.remove('dge-mark-kosha', 'dge-mark-dhatu', 'dge-mark-both');
        el.removeAttribute('data-dge-mark');
        el.removeAttribute('title');
      });
      tally = { dhatu: 0, kosha: 0 };
      renderLegend(tally);
      return Promise.resolve(0);
    }
    var spans = [];
    root.querySelectorAll('.dge-word:not([data-dge-mark])').forEach(function (el) { spans.push(el); });
    if (!spans.length) return Promise.resolve(0);

    var texts = spans.map(function (el) { return el.textContent; });
    var verseDhatus = verseDhatuWords();
    return wordMarks(texts).then(function (marks) {
      var n = 0;
      spans.forEach(function (el, i) {
        var mask = marks[texts[i]] || 0;
        if (verseDhatus[window.dgeResolvedDevanagari(texts[i]) || keyFor(texts[i])]) mask |= MARK_DHATU;
        // Mark the span either way: '0' records "checked, nothing to show",
        // which is what keeps a second pass from re-querying every word.
        el.setAttribute('data-dge-mark', String(mask));
        if (!mask) return;
        el.classList.add(CLASS_FOR[mask]);
        if (!el.getAttribute('title')) {
          // In a script that cannot write every Devanagari distinction, say
          // WHICH word the mark is for. In Tamil க is क, ख, ग and घ at once, so
          // the reading the index matched may not be the one on the page, and
          // presenting it silently as "this word" would be a small lie.
          var deva = window.dgeResolvedDevanagari(texts[i]);
          var plain = keyFor(texts[i]);
          el.setAttribute('title', TITLE_FOR[mask] +
            (deva && deva !== plain ? ' · read here as ' + deva : ''));
        }
        if (mask & MARK_DHATU) tally.dhatu++;
        if (mask & MARK_KOSHA) tally.kosha++;
        n++;
      });
      renderLegend(tally);
      return n;
    });
  }

  // WHY THE WORK IS DEFERRED PER CARD. A 100-verse page with all three
  // commentaries open carries 14,597 words, and marking them in one pass asked
  // for 756 shards at once — a burst no phone on a slow link should be made to
  // pay for text it has not scrolled to. Each card is marked as it comes into
  // view instead (with a screen of lead-in, so the colour is already there when
  // it arrives), which bounds the opening cost to what is actually on screen
  // and lets the shard cache absorb the rest as the reader moves.
  var observer = null;
  function observeCards(root) {
    // A re-render replaces every card, so the previous render's observations
    // are on detached nodes the observer would otherwise keep alive.
    if (observer) observer.disconnect();
    if (!observer) {
      observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (e) {
          if (!e.isIntersecting) return;
          observer.unobserve(e.target);
          markUnder(e.target);
        });
      }, { rootMargin: '600px 0px' });
    }
    var cards = root.querySelectorAll ? root.querySelectorAll('.shloka-card') : [];
    if (!cards.length) return markUnder(root);
    cards.forEach(function (c) { observer.observe(c); });
    return Promise.resolve(0);
  }

  function applyWordMarks(root) {
    root = root || document;
    // A card the observer never gets to is a card that never gets marked, so
    // anything but a live list (an older browser, a detached fragment, a
    // single-verse view) falls straight through to the direct pass.
    if (typeof IntersectionObserver !== 'function' || !marksEnabled()) return markUnder(root);
    tally = { dhatu: 0, kosha: 0 };
    return observeCards(root);
  }

  // The legend appears only when the page actually carries marks. A key to
  // colours that are not on screen is clutter, and a colour with no key is a
  // riddle -- so the two are tied to each other.
  function renderLegend(counts) {
    var box = document.getElementById('wordMarkLegend');
    if (!box) return;
    if (!counts.dhatu && !counts.kosha) { box.style.display = 'none'; box.innerHTML = ''; return; }
    var parts = [];
    if (counts.dhatu) parts.push('<span class="dge-mark-key"><span class="dge-mark-swatch k-dhatu"></span>' +
      'धातुरूपम् · verb form — tap for its derivation</span>');
    if (counts.kosha) parts.push('<span class="dge-mark-key"><span class="dge-mark-swatch k-kosha"></span>' +
      'कोशपदम् · dictionary headword — tap for its entry</span>');
    box.innerHTML = parts.join('');
    box.style.display = 'flex';
  }

  window.dgeApplyWordMarks = applyWordMarks;

  // Re-marking after the reader turns the feature on or off: clears the
  // data-dge-mark bookkeeping so the next pass re-decides every word.
  window.dgeResetWordMarks = function (root) {
    (root || document).querySelectorAll('[data-dge-mark]').forEach(function (el) {
      el.classList.remove('dge-mark-kosha', 'dge-mark-dhatu', 'dge-mark-both');
      el.removeAttribute('data-dge-mark');
    });
    return applyWordMarks(root);
  };
})();
