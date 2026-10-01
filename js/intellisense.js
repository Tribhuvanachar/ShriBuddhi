/* =========================================================================
   Intellisense — sūtras, and the words themselves.

   A commentary says "1.1.3", or names a rule without numbering it, and the
   reader is expected to already know which rule that is. Most don't. This
   turns those mentions into something you can tap: the mūla text, what kind
   of rule it is, what carries over into it from earlier rules, an English
   gloss, and a way through to the full sūtra with its commentaries.

   Two ways in:

     By number   References in the rendered text become tappable. Wrapped
                 only where the context actually says a sūtra is meant —
                 see shouldLink() — because "1.2.3" in a Purāṇa is a verse
                 number, and turning those into grammar links would be worse
                 than doing nothing.

     By name     window.dgeIdentifySutra('namah svasti svaha') finds
                 नमःस्वस्तिस्वाहास्वधालंवषड्योगाच्च. Works from Devanagari,
                 IAST, Kannada, Telugu, Malayalam or a rough romanisation,
                 because everything folds to the same consonant-led skeleton
                 first. Wired to the search box, so typing a half-remembered
                 name into it offers the rule.

   And the words. Double-tap any Sanskrit word in the text and it says what
   the word IS — which stem or root it comes from, and what case, number,
   person or tense it is standing in — then offers the dictionaries and every
   other place in the library it occurs. The analysis is Vidyut's, computed
   ahead of time by tools/build_morphology.py, because Vidyut is a Rust binary
   over a 75 MB kośa and could never run in a browser.

   Words are not marked up. A page of Sanskrit with every word underlined is
   not a reading experience; selection is the affordance instead.

   Nothing is fetched until it is needed. The 352 KB sūtra index loads the
   first time a page turns out to cite a rule, the per-adhyāya detail only
   when a popover opens, and a morphology bucket only for the word actually
   double-tapped. A page nobody interrogates fetches none of it.
   ========================================================================= */
(function () {
  'use strict';

  window.DGE_VERSIONS = window.DGE_VERSIONS || {};
  window.DGE_VERSIONS['intellisense.js'] = 'v1.5 (REF also accepts hyphen/en-dash separators -- Śabdārthakaustubha cites "(३-२-९७)" -- with the 1-8/1-4 bounds and cue-gating unchanged. On top of v1.4\'s opts.always)';

  // "Open in Aṣṭādhyāyī" needs a real cross-page URL: this script is loaded
  // both by render.html (the word-modal path) and by the Vyakarana-
  // cluster pages themselves (vyakarana/*.html) -- two different depths
  // relative to vyakarana/ashtadhyayi.html, so no single hardcoded
  // relative string works for both includers. Same technique as
  // dge-shell.js's LANDING_PAGE_URL: resolved off this script's own src
  // (fixed at js/intellisense.js) rather than the including page's
  // location, captured synchronously while still document.currentScript.
  var ASHTADHYAYI_URL = (function () {
    var self = (document.currentScript && document.currentScript.src) ||
               (window.DGE_SCRIPT_BASE || '');
    try { return new URL('../vyakarana/ashtadhyayi.html', self).href; }
    catch (e) { return 'vyakarana/ashtadhyayi.html'; } // fail soft, never throw
  })();

  // Kept as a named constant since the link markup below now builds its
  // href from ASHTADHYAYI_URL rather than one hardcoded literal.
  var DGE_SI_OPEN_LABEL = "Open in Aṣṭādhyāyī →";

  const self = (document.currentScript && document.currentScript.src) || '';
  function dataUrl(rel) {
    try { return new URL('../data/vedanga/vyakarana/ashtadhyayi/_index/' + rel, self).href; }
    catch (e) { return 'data/vedanga/vyakarana/ashtadhyayi/_index/' + rel; }
  }

  const CFG = {
    enabled: true,
    linkNumbers: true,
    // Bare numbers are sūtras without asking only where that is the subject.
    alwaysLinkIn: ['vedanga/vyakarana'],
    // Anywhere else, a citation cue has to be nearby.
    cues: ['सूत्र', 'सूत्रम्', 'सूत्रे', 'अष्टाध्याय', 'पाणिनि', 'पा॰', 'पा.',
           'sutra', 'sūtra', 'ashtadhyayi', 'aṣṭādhyāyī', 'panini', 'pāṇini'],
    cueWindow: 24,
    identifyFromSearch: true,
    analyseWords: true
  };

  /* ----------------------------------------------------------- folding ---
     The client half of tools/build_sutra_index.py. Same rules, so a key
     computed here meets a key computed there. If you change one, change both
     — the tests in that file are the spec. */
  const BLOCKS = [[0x0C80, 0x0CFF, 0x0380], [0x0C00, 0x0C7F, 0x0300],
                  [0x0D00, 0x0D7F, 0x0400], [0x0980, 0x09FF, 0x0080],
                  [0x0A80, 0x0AFF, 0x0180]];
  const V = { 'अ':'a','आ':'a','इ':'i','ई':'i','उ':'u','ऊ':'u','ऋ':'r','ॠ':'r',
              'ऌ':'l','ॡ':'l','ए':'e','ऐ':'e','ओ':'o','औ':'o' };
  const C = { 'क':'k','ख':'k','ग':'g','घ':'g','ङ':'n','च':'c','छ':'c','ज':'j',
              'झ':'j','ञ':'n','ट':'t','ठ':'t','ड':'d','ढ':'d','ण':'n','त':'t',
              'थ':'t','द':'d','ध':'d','न':'n','प':'p','फ':'p','ब':'b','भ':'b',
              'म':'m','य':'y','र':'r','ल':'l','व':'v','श':'s','ष':'s','स':'s',
              'ह':'h','ळ':'l' };
  const M = { 'ा':'a','ि':'i','ी':'i','ु':'u','ू':'u','ृ':'r','ॄ':'r','ॢ':'l',
              'ॣ':'l','े':'e','ै':'e','ो':'o','ौ':'o' };
  const LAT = { 'ā':'a','ī':'i','ū':'u','ṛ':'r','ṝ':'r','ḷ':'l','ḹ':'l','ṅ':'n',
                'ñ':'n','ṭ':'t','ḍ':'d','ṇ':'n','ś':'s','ṣ':'s','ṃ':'m','ṁ':'m',
                'ḥ':'h','ḻ':'l','ĕ':'e','ŏ':'o' };

  function toDeva(s) {
    let out = '';
    for (const ch of s) {
      const cp = ch.codePointAt(0);
      let mapped = ch;
      for (const [lo, hi, off] of BLOCKS) {
        if (cp >= lo && cp <= hi) { mapped = String.fromCodePoint(cp - off); break; }
      }
      out += mapped;
    }
    return out;
  }

  function fold(text) {
    if (!text) return '';
    const s = toDeva(String(text).normalize('NFC'));
    let out = '';
    for (let i = 0; i < s.length; i++) {
      const ch = s[i];
      if (C[ch]) {
        out += C[ch];
        const nxt = s[i + 1];
        if (nxt === '्') { i++; continue; }
        if (M[nxt]) { out += M[nxt]; i++; continue; }
        out += 'a';
        continue;
      }
      if (V[ch]) { out += V[ch]; continue; }
      if (ch === 'ं' || ch === 'ँ') { out += 'm'; continue; }
      if (ch === 'ः') { out += 'h'; continue; }
      if (ch >= 'ऀ' && ch <= 'ॿ') continue;
      out += ch.toLowerCase();
    }
    let t = out.replace(/[āīūṛṝḷḹṅñṭḍṇśṣṃṁḥḻĕŏ]/g, c => LAT[c] || c);
    t = t.replace(/ai/g, 'e').replace(/au/g, 'o');
    t = t.replace(/[^a-z]/g, '');
    t = t.replace(/([kgcjtdpbs])h/g, '$1');
    return t.replace(/(.)\1+/g, '$1');
  }

  const skeleton = f => f.replace(/[aeiou]/g, '');

  /* -------------------------------------------------------------- data --- */
  let indexPromise = null;
  const detailCache = {};

  function loadIndex() {
    if (indexPromise) return indexPromise;
    indexPromise = fetch(dataUrl('sutra_index.json'), { cache: 'force-cache' })
      .then(r => (r.ok ? r.json() : null))
      .then(ix => {
        if (!ix || !ix.ids) return null;
        const byId = Object.create(null);
        for (let i = 0; i < ix.ids.length; i++) byId[ix.ids[i]] = i;
        ix.byId = byId;
        ix.skels = ix.keys.map(skeleton);
        return ix;
      })
      .catch(() => null);
    return indexPromise;
  }

  function loadDetail(adhyaya) {
    if (detailCache[adhyaya]) return detailCache[adhyaya];
    detailCache[adhyaya] = fetch(dataUrl('sutra_detail_' + adhyaya + '.json'),
                                 { cache: 'force-cache' })
      .then(r => (r.ok ? r.json() : null)).catch(() => null);
    return detailCache[adhyaya];
  }

  /* ---------------------------------------------------------- identify --- */
  /* Exact key, then prefix (a name given in part, which is the usual case —
     "namah svasti svaha" is the opening of a much longer rule), then the
     consonant skeleton, which survives disagreement about the vowels. */
  window.dgeIdentifySutra = function (text, limit) {
    limit = limit || 6;
    return loadIndex().then(ix => {
      if (!ix) return [];
      const f = fold(text);
      if (f.length < 3) return [];
      const sk = skeleton(f);
      const seen = new Set(), out = [];
      const push = (i, how) => {
        if (seen.has(i) || out.length >= limit) return;
        seen.add(i);
        out.push({ id: ix.ids[i], mula: ix.mula[i], topic: ix.topics[i], match: how });
      };
      for (let i = 0; i < ix.keys.length; i++) if (ix.keys[i] === f) push(i, 'exact');
      for (let i = 0; i < ix.keys.length; i++) if (ix.keys[i].startsWith(f)) push(i, 'prefix');
      for (let i = 0; i < ix.keys.length; i++) if (ix.keys[i].indexOf(f) >= 0) push(i, 'contains');
      if (!out.length && sk.length >= 3) {
        for (let i = 0; i < ix.skels.length; i++) if (ix.skels[i].startsWith(sk)) push(i, 'skeleton');
      }
      return out;
    });
  };

  window.dgeLookupSutra = function (id) {
    return loadIndex().then(ix => {
      if (!ix || !(id in ix.byId)) return null;
      const i = ix.byId[id];
      const base = { id: id, mula: ix.mula[i], topic: ix.topics[i] };
      return loadDetail(id.split('.')[0]).then(det => Object.assign(base, (det && det[id]) || {}));
    });
  };

  /* ------------------------------------------------------------- links --- */
  const DEVA_DIGITS = '०१२३४५६७८९';
  const asciiNum = s => s.replace(/[०-९]/g, d => String(DEVA_DIGITS.indexOf(d)));
  // Adhyaya 1-8, pada 1-4. The bound is what makes this safe to run over
  // prose: it rejects most numbers that merely look like a citation.
  // Separator accepts a comma too, not just . / । / ॰ -- Kāśikā's own
  // cross-references write it "adhyaya,pada।sutra" (e.g. "७,२।१"), a comma
  // between the first two groups where the sutra's own citation of itself
  // uses dandas throughout ("१।१।१"). Both conventions point at the same
  // kind of reference and should link the same way. Hyphen/en-dash added
  // 1 Sep 2026 for Śabdārthakaustubha's "(३-२-९७)" convention -- still
  // bounded, still cue-gated everywhere the caller doesn't pass {always},
  // so a hyphenated verse range in prose stays unlinked as before.
  const REF = /(?<![\d.०-९])([1-8१-८])[.।॰,\-–]([1-4१-४])[.।॰,\-–](\d{1,3}|[०-९]{1,3})(?![\d०-९.])/g;

  // The reader sets window.currentGranthaSlug as it navigates. A standalone
  // page has no such navigation, so it states once what it is showing:
  // <body data-grantha-slug="vedanga/vyakarana/ashtadhyayi">. That is what
  // decides whether a bare "1.1.3" is a sutra or somebody's verse number.
  function currentSlug() {
    return window.currentGranthaSlug ||
           (document.body && document.body.dataset.granthaSlug) || '';
  }

  function shouldLink(slug, opts) {
    if (!CFG.linkNumbers) return { always: false, cued: true };
    const always = (opts && opts.always) ||
      (CFG.alwaysLinkIn || []).some(p => (slug || '').indexOf(p) === 0);
    return { always: always, cued: true };
  }

  function hasCue(text, at) {
    const from = Math.max(0, at - CFG.cueWindow);
    const before = text.slice(from, at).toLowerCase();
    return (CFG.cues || []).some(c => before.indexOf(c.toLowerCase()) >= 0);
  }

  const SKIP = new Set(['SCRIPT', 'STYLE', 'TEXTAREA', 'INPUT', 'BUTTON', 'A', 'SELECT']);

  function markUp(root, ix, opts) {
    const mode = shouldLink(currentSlug(), opts);
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode: n => {
        if (!n.nodeValue || n.nodeValue.length < 5) return NodeFilter.FILTER_REJECT;
        let p = n.parentElement;
        while (p && p !== root) {
          // dge-entity-ref: entity-linker.js's cross-reference scan (a
          // citation like "अष्टाध्याय्याम् १.१.१" naming a work THEN a
          // number) runs before this one at every call site specifically so
          // its span already owns that number -- without also skipping into
          // it here, this walker would still find the same digits and wrap
          // a second, nested dge-sutra-ref around them.
          if (SKIP.has(p.tagName) || p.classList.contains('dge-sutra-ref') || p.classList.contains('dge-entity-ref')) return NodeFilter.FILTER_REJECT;
          p = p.parentElement;
        }
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    const jobs = [];
    let node;
    while ((node = walker.nextNode())) {
      REF.lastIndex = 0;
      if (REF.test(node.nodeValue)) jobs.push(node);
    }

    let made = 0;
    jobs.forEach(function (textNode) {
      const text = textNode.nodeValue;
      const frag = document.createDocumentFragment();
      let last = 0, m;
      REF.lastIndex = 0;
      while ((m = REF.exec(text))) {
        const id = asciiNum(m[1]) + '.' + asciiNum(m[2]) + '.' + asciiNum(m[3]);
        const known = id in ix.byId;
        const wanted = known && (mode.always || hasCue(text, m.index));
        if (!wanted) continue;
        if (m.index > last) frag.appendChild(document.createTextNode(text.slice(last, m.index)));
        const el = document.createElement('span');
        el.className = 'dge-sutra-ref';
        el.setAttribute('role', 'button');
        el.setAttribute('tabindex', '0');
        el.dataset.sutra = id;
        el.textContent = m[0];
        frag.appendChild(el);
        last = m.index + m[0].length;
        made++;
      }
      if (!made || last === 0) return;
      if (last < text.length) frag.appendChild(document.createTextNode(text.slice(last)));
      textNode.parentNode.replaceChild(frag, textNode);
    });
    return made;
  }

  /* Cheap pre-check so a page with no citation at all never fetches the
     index: test the raw text before loading 352 KB to look things up in.

     opts.always: link every "d.d.d"-shaped number as a sūtra in this root
     with no cue word required — for callers who already know, from the
     content's own structure rather than nearby prose, that a number here
     can only be a sūtra citation (e.g. Kosha's Kāśikā/Gaṇapāṭha/Anuvṛtti
     cards, each entry *being* one sūtra rather than merely mentioning one,
     so the citation sits right after the headword with nothing "sūtra-ish"
     in between for the cue-window check to find; likewise a Kosha AI/
     translation answer that quotes a rule after the page's own one-time
     scan already ran). Same trust level as CFG.alwaysLinkIn, just scoped to
     the caller's root instead of a whole grantha slug. */
  function scan(root, opts) {
    if (!CFG.enabled || !CFG.linkNumbers || !root) return;
    REF.lastIndex = 0;
    if (!REF.test(root.innerText || root.textContent || '')) return;
    loadIndex().then(ix => { if (ix) markUp(root, ix, opts); });
  }
  window.dgeScanForSutras = scan;

  /* ----------------------------------------------------------- popover --- */
  let pop = null;

  function closePop() { if (pop) { pop.remove(); pop = null; } }

  function esc(s) {
    return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  // Labels are Devanagari so they follow the reader's script selection, the
  // same convention library.js uses for the tree.
  const tr = t => (typeof window.dgeToActiveScript === 'function')
    ? window.dgeToActiveScript(t)
    : ((typeof window.applyTransliteration === 'function' && window.activeScript &&
        window.activeScript !== 'devanagari')
        ? window.applyTransliteration(t, window.activeScript) : t);

  function popHtml(s) {
    let h = '<div class="dge-si-head"><span class="dge-si-id">' + esc(s.id) + '</span>' +
            (s.td ? '<span class="dge-si-type">' + esc(tr(s.td)) + '</span>' : '') +
            '<button class="dge-si-x" data-si-close aria-label="Close">✕</button></div>' +
            '<div class="dge-si-mula">' + esc(tr(s.mula || '')) + '</div>';
    if (s.topic) h += '<div class="dge-si-topic">' + esc(tr(s.topic)) + '</div>';
    if (s.p && s.p.length) {
      h += '<div class="dge-si-row"><b>पदच्छेदः</b> ' +
           esc(s.p.map(tr).join(' · ')) + '</div>';
    }
    if (s.a) h += '<div class="dge-si-row"><b>अन्वयः</b> ' + esc(tr(s.a)) + '</div>';
    if (s.v && s.v.length) {
      h += '<div class="dge-si-row"><b>अनुवृत्तिः</b> ' + s.v.map(function (x) {
        return esc(tr(x[0])) + ' <span class="dge-si-from" data-sutra="' + esc(x[1]) + '">' +
               esc(x[1]) + '</span>';
      }).join(' · ') + '</div>';
    }
    if (s.e) h += '<div class="dge-si-en">' + esc(s.e) + '</div>';
    h += '<div class="dge-si-actions">' +
         '<a class="dge-si-go" href="' + ASHTADHYAYI_URL + '#' + esc(s.id) + '">' + DGE_SI_OPEN_LABEL + '</a>' +
         '</div>';
    return h;
  }

  function openPop(anchor, id) {
    closePop();
    pop = document.createElement('div');
    pop.className = 'dge-si-pop';
    pop.innerHTML = '<div class="dge-si-loading">…</div>';
    document.body.appendChild(pop);
    place(anchor);

    window.dgeLookupSutra(id).then(function (s) {
      if (!pop) return;
      pop.innerHTML = s ? popHtml(s)
        : '<div class="dge-si-row">Sūtra ' + esc(id) + ' is not in the index.</div>';
      place(anchor);
    });
  }

  function place(anchor) {
    if (!pop) return;
    const r = anchor.getBoundingClientRect();
    const w = pop.offsetWidth;      // fixed by the stylesheet, see .dge-si-pop
    let left = r.left + r.width / 2 - w / 2;
    left = Math.max(8, Math.min(left, window.innerWidth - w - 8));
    const h = pop.offsetHeight || 200;
    const below = r.bottom + 8;
    const top = (below + h > window.innerHeight - 8 && r.top - h - 8 > 8) ? r.top - h - 8 : below;
    pop.style.left = left + 'px';
    pop.style.top = Math.max(8, Math.min(top, window.innerHeight - h - 8)) + 'px';
  }

  document.addEventListener('click', function (ev) {
    const ref = ev.target.closest && ev.target.closest('.dge-sutra-ref, .dge-si-from');
    if (ref) { ev.preventDefault(); openPop(ref, ref.dataset.sutra); return; }
    const chain = ev.target.closest && ev.target.closest('[data-word]');
    if (chain) {
      ev.preventDefault();
      const r = chain.getBoundingClientRect();
      openWord({ getBoundingClientRect: () => r }, chain.getAttribute('data-word'));
      return;
    }
    const kosha = ev.target.closest && ev.target.closest('[data-kosha]');
    if (kosha) {
      const w = kosha.getAttribute('data-kosha');
      closePop();
      if (typeof window.dgeOpenKosha === 'function') window.dgeOpenKosha(w);
      return;
    }
    const rep = ev.target.closest && ev.target.closest('[data-report-word]');
    if (rep) {
      // Everything the popover is showing goes with the report (the analysis, the split, the
      // meaning), because "this split is wrong" is useless without the split. The popover stays
      // open so the screenshot shows it.
      const w = rep.getAttribute('data-report-word');
      const shown = pop ? pop.innerText.replace(/\s*\n\s*/g, ' | ').slice(0, 900) : '';
      const rp = { feature: 'word-popover', subject: w, extra: shown, category: 'wrong-split' };
      if (typeof window.dgeOpenReport === 'function') window.dgeOpenReport(rp);
      else if (window.dgeReport) window.dgeReport(rp);
      else {                       // pages without the footer shell: load the form ourselves
        const sc = document.createElement('script');
        try { sc.src = new URL('report-issue.js', self).href; } catch (e) { sc.src = 'js/report-issue.js'; }
        sc.onload = function () { if (window.dgeReport) window.dgeReport(rp); };
        document.head.appendChild(sc);
      }
      return;
    }
    const occur = ev.target.closest && ev.target.closest('[data-occur]');
    if (occur) {
      const w = occur.getAttribute('data-occur');
      closePop();
      // The global search index already knows every grantha a word appears
      // in; opening it prefilled is the whole "where else does this occur"
      // feature, rather than a second index that would drift from it.
      if (window.DGEGlobalSearch && typeof window.DGEGlobalSearch.open === 'function') {
        window.DGEGlobalSearch.open(w);
      }
      return;
    }
    if (ev.target.closest && ev.target.closest('[data-si-close]')) { closePop(); return; }
    if (pop && !ev.target.closest('.dge-si-pop')) closePop();
  });
  document.addEventListener('keydown', function (ev) {
    if (ev.key === 'Escape') closePop();
    if ((ev.key === 'Enter' || ev.key === ' ') && ev.target.classList &&
        ev.target.classList.contains('dge-sutra-ref')) {
      ev.preventDefault();
      openPop(ev.target, ev.target.dataset.sutra);
    }
  });
  window.addEventListener('resize', closePop);

  /* ---------------------------------------------------------- morphology ---
     Precomputed by tools/build_morphology.py from Vidyut and sharded by the
     first two SLP1 characters, so a lookup fetches one small bucket rather
     than the 6 MB whole. Vidyut itself is a Rust binary over a 75 MB kośa and
     could never run here; this is its answer, computed once.

     About half the words a reader taps will have an analysis. Vidyut resolves
     inflected forms, not sandhi-joined ones, and Sanskrit texts are full of
     the latter. A word with no analysis says so and still offers the rest. */
  const SLP = { 'अ':'a','आ':'A','इ':'i','ई':'I','उ':'u','ऊ':'U','ऋ':'f','ॠ':'F',
    'ऌ':'x','ॡ':'X','ए':'e','ऐ':'E','ओ':'o','औ':'O','क':'k','ख':'K','ग':'g',
    'घ':'G','ङ':'N','च':'c','छ':'C','ज':'j','झ':'J','ञ':'Y','ट':'w','ठ':'W',
    'ड':'q','ढ':'Q','ण':'R','त':'t','थ':'T','द':'d','ध':'D','न':'n','प':'p',
    'फ':'P','ब':'b','भ':'B','म':'m','य':'y','र':'r','ल':'l','व':'v','श':'S',
    'ष':'z','स':'s','ह':'h','ळ':'L','ं':'M','ः':'H','ँ':'~' };
  const SLP_M = { 'ा':'A','ि':'i','ी':'I','ु':'u','ू':'U','ृ':'f','ॄ':'F',
    'ॢ':'x','ॣ':'X','े':'e','ै':'E','ो':'o','ौ':'O' };

  function toSlp(word) {
    const s = toDeva(String(word).normalize('NFC'));
    let out = '';
    for (let i = 0; i < s.length; i++) {
      const ch = s[i];
      if (SLP[ch] && !(ch in SLP_M)) {
        const isCons = ch >= 'क' && ch <= 'ह' || ch === 'ळ';
        out += SLP[ch];
        if (isCons) {
          const nxt = s[i + 1];
          if (nxt === '्') { i++; continue; }
          if (SLP_M[nxt]) { out += SLP_M[nxt]; i++; continue; }
          out += 'a';
        }
        continue;
      }
      if (SLP_M[ch]) { out += SLP_M[ch]; continue; }
      if (ch === '्') continue;
    }
    return out;
  }

  function morphUrl(rel) {
    try { return new URL('../data/_morph/' + rel, self).href; }
    catch (e) { return 'data/_morph/' + rel; }
  }

  const morphCache = {};
  function loadBucket(slp) {
    const two = (slp + '__').slice(0, 2);
    const name = two.split('').map(c => (c >= 'A' && c <= 'Z') ? c + '_'
                                       : (/[a-z0-9]/.test(c) ? c : 'x')).join('');
    if (morphCache[name]) return morphCache[name];
    morphCache[name] = fetch(morphUrl(name + '.json'), { cache: 'force-cache' })
      .then(r => (r.ok ? r.json() : null)).catch(() => null);
    return morphCache[name];
  }

  const LINGA = { p: 'पुंलिङ्गम्', s: 'स्त्रीलिङ्गम्', n: 'नपुंसकलिङ्गम्' };
  const VIBH = { '1': 'प्रथमा', '2': 'द्वितीया', '3': 'तृतीया', '4': 'चतुर्थी',
                 '5': 'पञ्चमी', '6': 'षष्ठी', '7': 'सप्तमी', '8': 'सम्बोधनम्' };
  const VAC = { '1': 'एकवचनम्', '2': 'द्विवचनम्', '3': 'बहुवचनम्' };
  const PUR = { '1': 'उत्तमपुरुषः', '2': 'मध्यमपुरुषः', '3': 'प्रथमपुरुषः' };
  const LAK = { lat: 'लट्', lit: 'लिट्', lut: 'लुट्', lrt: 'लृट्', let: 'लेट्',
                lot: 'लोट्', lan: 'लङ्', vlin: 'विधिलिङ्', alin: 'आशीर्लिङ्',
                lun: 'लुङ्', lrn: 'लृङ्' };
  const PRA = { k: 'कर्तरि', km: 'कर्मणि', b: 'भावे' };
  const join = a => a.filter(Boolean).join(' · ');

  function describe(rec) {
    if (rec[0] === 'a') return { lemma: rec[1], gloss: 'अव्ययम्', kind: 'a' };
    if (rec[0] === 't') {
      return { lemma: rec[1], gloss: join([LAK[rec[2]], PUR[rec[3]], VAC[rec[4]], PRA[rec[5]]]), kind: 't' };
    }
    // kind/linga (p|s|n) travel with the gloss so the word tools can offer the
    // stem's full declension (shabda.html?gen=…, 7 Sep 2026).
    return { lemma: rec[1], gloss: join([LINGA[rec[2]], VIBH[rec[3]], VAC[rec[4]]]), kind: 's', linga: rec[2] };
  }

  /* Related words, from tools/build_synonyms.py — the English-Sanskrit
     dictionary read backwards, so a word's entry names the other words used
     for the same idea. Same bucketing as the morphology, so one rule serves
     both.

     Called "related", not "synonyms", on purpose. Inverting a bilingual
     dictionary yields words that share a sense and also words that merely sat
     in the same gloss; the English sense is shown beside each group so the
     reader can see which is which rather than being asked to trust it. */
  const synCache = {};
  function loadSyn(slp) {
    const two = (slp + '__').slice(0, 2);
    const name = two.split('').map(c => (c >= 'A' && c <= 'Z') ? c + '_'
                                       : (/[a-z0-9]/.test(c) ? c : 'x')).join('');
    if (synCache[name]) return synCache[name];
    let url;
    try { url = new URL('../data/_synonyms/' + name + '.json', self).href; }
    catch (e) { url = 'data/_synonyms/' + name + '.json'; }
    synCache[name] = fetch(url, { cache: 'force-cache' })
      .then(r => (r.ok ? r.json() : null)).catch(() => null);
    return synCache[name];
  }

  window.dgeRelatedWords = function (word) {
    const clean = String(word || '').replace(/[^ऀ-ॿ]/g, '');
    if (!clean) return Promise.resolve([]);
    const slp = toSlp(clean);
    if (!slp) return Promise.resolve([]);
    return loadSyn(slp).then(b => (b && b[clean]) || []);
  };

  /* Senses, from tools/build_wordnet.py — IndoWordNet's Sanskrit synsets.
     This is the only source in the library that defines a Sanskrit word IN
     SANSKRIT: the koshas gloss into English or Kannada, and the related words
     above are bound by an English sense. It is also the only one where the
     synonym set is a lexicographer's claim rather than something inferred by
     inverting a bilingual dictionary, which is why the two are shown as
     separate sections under their own names instead of being merged.

     A bucket is {s: [synset, ...], w: {word: [indices into s]}}. The synset is
     stored once and its members point at it; inlined under every member the
     tree came to 40 MB instead of 24.

     Looked up by the word as tapped and then by the stems Vidyut found for
     it. IndoWordNet lists nominal members inflected — अश्वः, not अश्व — and the
     build indexes the stem alongside, but a reader taps a word in a sentence
     (अश्वेन), and only the analysis connects that to either. */
  const wnCache = {};
  function loadWn(slp) {
    const two = (slp + '__').slice(0, 2);
    const name = two.split('').map(c => (c >= 'A' && c <= 'Z') ? c + '_'
                                       : (/[a-z0-9]/.test(c) ? c : 'x')).join('');
    if (wnCache[name]) return wnCache[name];
    // The tree is 26 MB and ships with the site, in data/_wordnet/, like the rest of
    // the corpus. It used to be served from a pinned jsDelivr branch because the
    // site was tight against a size ceiling; it is 30 MB gzipped and the whole site
    // is about 300 MB gzipped, so that reason is gone. The path is resolved from THIS
    // script's own URL (js/ -> ../data/_wordnet/), so it is right on every page,
    // including the four Vyakarana pages that sit in a subfolder and do not load
    // config.js. window.WORDNET_DATA_BASE, if a page sets it to a URL, still wins;
    // if the files are not there the fetch 404s, this resolves to null, and the
    // popover simply has no अर्थः section, with the analysis and related words
    // unaffected.
    const CDN = '';
    const set = window.WORDNET_DATA_BASE;
    const cdn = (set === undefined ? CDN : (set || '')).replace(/\/+$/, '');
    let url;
    if (cdn) url = cdn + '/' + name + '.json';
    else {
      try { url = new URL('../data/_wordnet/' + name + '.json', self).href; }
      catch (e) { url = 'data/_wordnet/' + name + '.json'; }
    }
    wnCache[name] = fetch(url, { cache: 'force-cache' })
      .then(r => (r.ok ? r.json() : null)).catch(() => null);
    return wnCache[name];
  }

  // अश्वः and अश्व are one word listed two ways, and a synset that names both
  // must not offer the reader the word they are already looking at.
  function wnStem(w) {
    return w.replace(/ः$/, '').replace(/म्$/, '');
  }

  window.dgeWordNet = function (word, lemmas) {
    const keys = [];
    [word].concat(lemmas || []).forEach(function (w) {
      const clean = String(w || '').replace(/[^ऀ-ॿ]/g, '');
      if (clean && keys.indexOf(clean) < 0) keys.push(clean);
    });
    if (!keys.length) return Promise.resolve([]);
    return Promise.all(keys.map(function (k) {
      const slp = toSlp(k);
      return slp ? loadWn(slp).then(b => [k, b]) : Promise.resolve([k, null]);
    })).then(function (pairs) {
      const out = [], seen = {};
      pairs.forEach(function (pair) {
        const key = pair[0], b = pair[1];
        if (!b || !b.w || !b.w[key]) return;
        b.w[key].forEach(function (i) {
          const r = b.s[i];
          if (!r || seen[r[1]]) return;
          seen[r[1]] = 1;
          const self_ = wnStem(key);
          out.push({ pos: r[0], gloss: r[1], example: r[2],
                     words: (r[3] || []).filter(w => wnStem(w) !== self_),
                     hyper: r[4] || '', other: r[5] || [] });
        });
      });
      return out;
    });
  };

  window.dgeAnalyseWord = function (word) {
    const clean = String(word || '').replace(/[^ऀ-ॿa-zA-Zāīūṛṝḷṅñṭḍṇśṣṃṁḥ]/g, '');
    if (!clean) return Promise.resolve([]);
    const slp = toSlp(clean);
    if (!slp) return Promise.resolve([]);
    return loadBucket(slp).then(function (b) {
      const recs = (b && (b[clean] || b[toDeva(clean)])) || null;
      return recs ? recs.map(describe) : [];
    });
  };

  /* ------------------------------------------------------- word popover --- */
  function wordHtml(word, an, rel, wn) {
    let h = '<div class="dge-si-head"><span class="dge-si-id">' + esc(word) + '</span>' +
            '<button class="dge-si-x" data-si-close aria-label="Close">✕</button></div>';
    if (an.length) {
      const byLemma = {};
      an.forEach(function (a) { (byLemma[a.lemma] = byLemma[a.lemma] || []).push(a.gloss); });
      h += '<div class="dge-si-row"><b>व्याकरणम्</b></div>';
      var lingaOf = {};
      an.forEach(function (a) { if (a.kind === 's' && a.linga && !lingaOf[a.lemma]) lingaOf[a.lemma] = a.linga.toUpperCase(); });
      Object.keys(byLemma).forEach(function (lemma) {
        h += '<div class="dge-si-morph"><span class="dge-si-lemma">' + esc(lemma) + '</span>' +
             byLemma[lemma].filter(Boolean).map(function (g) {
               return '<span class="dge-si-parse">' + esc(tr(g)) + '</span>';
             }).join('') +
             (lingaOf[lemma] ? '<a class="dge-si-parse dge-si-forms" href="vyakarana/shabda.html?gen=' + encodeURIComponent(lemma) + '&l=' + lingaOf[lemma] + '" title="All 24 forms of this stem, derived on the Śabdapāṭha page">रूपाणि ↗</a>' : '') +
             '</div>';
      });
    } else {
      h += '<div class="dge-si-none">No analysis — Vidyut resolves inflected words, ' +
           'not sandhi-joined ones. The dictionaries may still have it.</div>';
    }
    if (wn && wn.length) {
      // No source or licence line here (lead, 30 Sep 2026): IndoWordNet is
      // credited once, on the Credits page.
      h += '<div class="dge-si-row"><b>अर्थः</b></div>';
      wn.slice(0, 3).forEach(function (s) {
        h += '<div class="dge-si-wn"><div class="dge-si-def">' + esc(tr(s.gloss)) + '</div>' +
             (s.example ? '<div class="dge-si-eg">' + esc(tr(s.example)) + '</div>' : '') +
             (s.words.length ? '<div>' + s.words.slice(0, 8).map(function (w) {
                return '<span class="dge-si-word" data-word="' + esc(w) + '">' +
                       esc(tr(w)) + '</span>';
              }).join('') + '</div>' : '') +
             ((s.hyper || s.other.length) ? '<div class="dge-si-wn-meta">' +
                (s.hyper ? '<span class="dge-si-wn-lab">सामान्यम्</span>' +
                           '<span class="dge-si-word" data-word="' + esc(s.hyper) + '">' +
                           esc(tr(s.hyper)) + '</span>' : '') +
                // Kannada is a language here, not a script, so it is shown as
                // it stands rather than transliterated into the reader's.
                (s.other.length ? '<span class="dge-si-wn-lab">ಕನ್ನಡ</span>' +
                                  '<span class="dge-si-kn">' +
                                  esc(s.other.slice(0, 3).join(', ')) + '</span>' : '') +
              '</div>' : '') +
             '</div>';
      });
    }
    if (rel && rel.length) {
      h += '<div class="dge-si-row"><b>सम्बद्धाः</b></div>';
      rel.slice(0, 4).forEach(function (g) {
        h += '<div class="dge-si-rel"><span class="dge-si-sense">' + esc(g[0]) + '</span>' +
             g[1].slice(0, 8).map(function (w) {
               return '<span class="dge-si-word" data-word="' + esc(w) + '">' + esc(tr(w)) + '</span>';
             }).join('') + '</div>';
      });
    }
    h += '<div class="dge-si-actions">' +
         '<button class="dge-si-go" data-kosha="' + esc(word) + '">कोश — look it up →</button>' +
         '<button class="dge-si-go" data-occur="' + esc(word) + '">Other occurrences →</button>' +
         '<button class="dge-si-go dge-si-report" data-report-word="' + esc(word) + '" title="Report a problem with this analysis">⚑ Report</button>' +
         '</div>';
    return h;
  }

  function openWord(anchor, word) {
    closePop();
    pop = document.createElement('div');
    pop.className = 'dge-si-pop';
    pop.innerHTML = '<div class="dge-si-loading">…</div>';
    document.body.appendChild(pop);
    place(anchor);
    // The WordNet lookup waits on the analysis rather than running beside it:
    // its best key is often the stem the analysis returns, not the inflected
    // word that was tapped. Both bucket fetches are cached, so the wait costs
    // one round trip on the first word in a bucket and nothing after.
    Promise.all([window.dgeAnalyseWord(word), window.dgeRelatedWords(word)])
      .then(function (r) {
        return window.dgeWordNet(word, r[0].map(a => a.lemma))
          .then(function (wn) { return [r[0], r[1], wn]; });
      })
      .then(function (r) {
        if (!pop) return;
        pop.innerHTML = wordHtml(word, r[0], r[1], r[2]);
        place(anchor);
        enrichWord(word, r[0], anchor);
      });
  }

  /* ---------------------------------------- sandhi split and Saṃsādhanī ---
     Two more rows, added after the popover is already showing so the first paint
     never waits on them.

       सन्धिच्छेदः   the word divided where it is two words joined. Sources, in order:
                    data/_sandhi (Vidyut, vowel sandhi, names its sūtra) ->
                    data/_sandhi_wide (Vidyut, other junctions, one guess) ->
                    Saṃsādhanī's splitter, live. A wide guess is shown as
                    "सम्भाव्यम्" until Saṃsādhanī's analyser confirms BOTH halves are
                    words, then as "✓".
       विश्लेषणम्    only when Vidyut has no analysis of the word: Saṃsādhanī's
                    morphological analysis. A word Vidyut already explains costs the
                    university's server nothing. js/samsadhani.js has the manners. */
  const sandhiCache = {};
  function loadSandhi(dir, slp) {
    const two = (slp + '__').slice(0, 2);
    const name = two.split('').map(c => (c >= 'A' && c <= 'Z') ? c + '_'
                                       : (/[a-z0-9]/.test(c) ? c : 'x')).join('');
    const key = dir + '/' + name;
    if (sandhiCache[key]) return sandhiCache[key];
    let url;
    try { url = new URL('../data/' + dir + '/' + name + '.json', self).href; }
    catch (e) { url = 'data/' + dir + '/' + name + '.json'; }
    sandhiCache[key] = fetch(url, { cache: 'force-cache' })
      .then(r => (r.ok ? r.json() : null)).catch(() => null);
    return sandhiCache[key];
  }

  const WIDE_KIND = { v: 'विसर्गसन्धिः', c: 'व्यञ्जनसन्धिः', n: 'समासः / सन्धिविकाररहितः' };

  window.dgeSandhiLocal = function (word) {
    const clean = String(word || '').replace(/[^ऀ-ॿ]/g, '');
    const slp = clean && toSlp(clean);
    if (!slp) return Promise.resolve(null);
    return loadSandhi('_sandhi', slp).then(function (b) {
      const hit = b && b[clean];
      if (hit && hit.length) return { wide: false, splits: hit.slice(0, 2) };
      return loadSandhi('_sandhi_wide', slp).then(function (w) {
        const g = w && w[clean];
        return g ? { wide: true, splits: [{ first: g[0], second: g[1], name: WIDE_KIND[g[2]] || '' }] } : null;
      });
    });
  };

  function addRow(html) {
    if (!pop) return null;
    const d = document.createElement('div');
    d.className = 'dge-si-scl';
    d.innerHTML = html;
    const foot = pop.querySelector('.dge-si-actions');
    if (foot) pop.insertBefore(d, foot); else pop.appendChild(d);
    return d;
  }

  function splitChips(sp) {
    return '<span class="dge-si-lemma">' + esc(tr(sp.first)) + '</span> + ' +
           '<span class="dge-si-lemma">' + esc(tr(sp.second)) + '</span>' +
           (sp.name ? ' <span class="dge-si-parse">' + esc(sp.name) + '</span>' : '');
  }

  function enrichWord(word, an, anchor) {
    const scl = (typeof window.dgeSclAvailable === 'function' && window.dgeSclAvailable());
    window.dgeSandhiLocal(word).then(function (local) {
      if (!pop) return null;
      if (local && !local.wide) {
        const row0 = addRow('<div class="dge-si-row"><b>सन्धिच्छेदः</b><span class="dge-si-src scl-state"></span></div>' +
               '<div class="dge-si-morph">' + local.splits.map(splitChips).join('<br>') + '</div>');
        place(anchor);
        // A second opinion, once per word per reader (cached). Agreement earns a tick;
        // a different answer is shown beside ours rather than silently replacing it.
        if (scl && row0) {
          return window.dgeSclSplit(word).then(function (parts) {
            if (!pop || parts.length !== 2) return;
            const agree = local.splits.some(sp => sp.first === parts[0] && sp.second === parts[1]);
            const st = row0.querySelector('.scl-state');
            if (agree) { if (st) st.textContent = '✓ संसाधनी'; return; }
            row0.insertAdjacentHTML('beforeend', '<div class="dge-si-morph"><span class="dge-si-parse">Saṃsādhanī</span> ' +
              '<span class="dge-si-lemma">' + esc(tr(parts[0])) + '</span> + <span class="dge-si-lemma">' +
              esc(tr(parts[1])) + '</span></div>');
            place(anchor);
          });
        }
        return null;
      }
      if (local && local.wide) {
        const sp = local.splits[0];
        const row = addRow('<div class="dge-si-row"><b>सन्धिच्छेदः</b>' +
                           '<span class="dge-si-src scl-state">सम्भाव्यम्</span></div>' +
                           '<div class="dge-si-morph">' + splitChips(sp) + '</div>');
        place(anchor);
        if (scl && row) {
          return Promise.all([window.dgeSclKnows(sp.first), window.dgeSclKnows(sp.second)])
            .then(function (ok) {
              const st = row.querySelector('.scl-state');
              if (st) st.textContent = (ok[0] && ok[1]) ? '✓ पदद्वयं सम्यक्' : 'सम्भाव्यम् · अप्रमाणितम्';
            });
        }
        return null;
      }
      if (scl) {
        return window.dgeSclSplit(word).then(function (parts) {
          if (!pop || !parts.length) return;
          addRow('<div class="dge-si-row"><b>सन्धिच्छेदः</b></div><div class="dge-si-morph">' +
                 parts.map(p => '<span class="dge-si-lemma">' + esc(tr(p)) + '</span>').join(' + ') + '</div>');
          place(anchor);
        });
      }
      return null;
    });
    if (scl && !an.length) {
      window.dgeSclAnalyse(word).then(function (rs) {
        if (!pop || !rs.length) return;
        addRow('<div class="dge-si-row"><b>विश्लेषणम्</b></div>' + rs.slice(0, 4).map(function (r) {
          return '<div class="dge-si-morph"><span class="dge-si-lemma">' + esc(tr(r.lemma)) + '</span>' +
                 (r.parse ? '<span class="dge-si-parse">' + esc(tr(r.parse)) + '</span>' : '') + '</div>';
        }).join(''));
        place(anchor);
      });
    }
  }

  /* A word is picked out of the text by selecting it — a double-tap on a
     phone, a double-click on a desktop — rather than by making every word a
     link. Marking up every word would turn a page of Sanskrit into a page of
     underlines, which is not a reading experience. */
  function selectedWord() {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed) return null;
    const t = (typeof window.dgeRobustSelectedText === 'function' ? window.dgeRobustSelectedText() : sel.toString().trim());
    if (!t || t.length > 40 || /\s/.test(t)) return null;
    if (!/[ऀ-ॿ]/.test(t)) return null;
    return t.replace(/[।॥,.'"()\[\]]/g, '');
  }

  function wireWords() {
    const host = document.getElementById('shlokaList');
    if (!host) return;
    host.addEventListener('dblclick', function (ev) {
      const w = selectedWord();
      if (!w) return;
      const sel = window.getSelection();
      let anchor;
      try {
        const r = sel.getRangeAt(0).getBoundingClientRect();
        anchor = { getBoundingClientRect: () => r };
      } catch (e) { anchor = ev.target; }
      openWord(anchor, w);
    });
  }

  /* ------------------------------------------------------- search hook ---
     Typing a rule's name into the search box finds nothing, because the box
     searches the grantha you are reading and the rule is in a different text
     entirely. Rather than change what search does, this offers the match
     alongside it: a line under the box saying which sūtra that name belongs
     to, which opens the same popover. Nothing about handleSearch() changes,
     so a query that IS in this text behaves exactly as before. */
  function wireSearch() {
    // The reader's own search box by default; a standalone page names its
    // own with <body data-intellisense-search="#dh-search">. The hint goes
    // after whatever wraps the box, or after the box itself if nothing does.
    const sel = (document.body && document.body.dataset.intellisenseSearch || '').trim();
    const input = sel ? document.querySelector(sel)
                      : document.getElementById('searchInput');
    if (!input) return;
    const group = input.closest('.search-box-group') || input.parentNode;
    if (!group) return;

    const hint = document.createElement('div');
    hint.className = 'dge-si-hint';
    hint.style.display = 'none';
    group.insertAdjacentElement('afterend', hint);

    let timer = null;
    input.addEventListener('input', function () {
      clearTimeout(timer);
      timer = setTimeout(function () {
        const q = input.value.trim();
        if (fold(q).length < 4) { hint.style.display = 'none'; hint.innerHTML = ''; return; }
        window.dgeIdentifySutra(q, 3).then(function (hits) {
          if (!hits.length) { hint.style.display = 'none'; hint.innerHTML = ''; return; }
          hint.innerHTML = '<span class="dge-si-hint-lead">सूत्रम्</span>' +
            hits.map(function (h) {
              return '<span class="dge-sutra-ref" data-sutra="' + esc(h.id) + '" role="button" tabindex="0">' +
                     esc(h.id) + ' ' + esc(tr(h.mula)) + '</span>';
            }).join('');
          hint.style.display = 'flex';
        });
      }, 220);
    });
  }

  /* -------------------------------------------------------------- boot --- */
  function overrides() {
    const url = (typeof window.dgeAdminConfigUrl === 'function')
      ? window.dgeAdminConfigUrl('intellisense.json') : null;
    if (!url) return Promise.resolve(null);
    // dgeAdminConfigUrl only exists where core.js has already loaded, so
    // dgeFetchPublicJson (defined right beside it) is guaranteed present too
    // -- this falls back to the repo-root config/intellisense.json when
    // admin/config/intellisense.json 404s, the shape a cleanly published
    // site is in.
    return (typeof window.dgeFetchPublicJson === 'function')
      ? window.dgeFetchPublicJson(url)
      : fetch(url, { cache: 'no-store' }).then(r => (r.ok ? r.json() : null)).catch(() => null);
  }

  window.dgeIntellisenseReady = overrides().then(function (ov) {
    if (ov && typeof ov === 'object') {
      Object.keys(ov).forEach(function (k) { if (k[0] !== '_') CFG[k] = ov[k]; });
    }
    if (!CFG.enabled) return CFG;

    // Which parts of the page get scanned. The reader's own two containers by
    // default; any other page names its own with
    // <body data-intellisense-roots="#a,#b">. Without this the script could
    // be added to a page and quietly do nothing, which is how the Ashtadhyayi
    // and Dhatupatha pages came to look as though intellisense was off.
    const sel = (document.body && document.body.dataset.intellisenseRoots || '').trim();
    const roots = sel
      ? sel.split(',').map(s => document.querySelector(s.trim())).filter(Boolean)
      : [document.getElementById('shlokaList')];
    // renderList() rebuilds the list wholesale on every script change, theme
    // change and navigation, so a one-off pass would only ever mark up the
    // first render. Debounced because a rebuild fires many mutations.
    let t = null;
    const obs = new MutationObserver(function () {
      clearTimeout(t);
      t = setTimeout(function () { roots.forEach(scan); }, 120);
    });
    roots.forEach(function (el) {
      if (el) obs.observe(el, { childList: true, subtree: true });
    });
    roots.forEach(scan);
    if (CFG.identifyFromSearch) wireSearch();
    if (CFG.analyseWords !== false) wireWords();
    return CFG;
  });
})();
