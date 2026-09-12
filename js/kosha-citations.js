/* =========================================================================
   Citation links for कोश glosses (and anywhere else that wants them).

   The dictionaries cite constantly — the Purāṇa Index gives "भा. IX. २२. ३३",
   the Hindi Vedic-rituals lexicon gives "ऋ.वे. 1.165", Śabdārthakaustubha
   gives "रघु० ४-४४". A reader who wants to check one currently has to leave
   the lookup, find the text, and count verses.

   window.dgeMarkCitations(root) turns the ones we can resolve into taps that
   open a floating card with the verse itself.

   DELIBERATELY NARROW. A citation is linked only when the abbreviation maps
   to a text this library actually carries AND the numbering scheme is the
   same edition. Everything else is left as plain text, on the same principle
   the quick-jump table states: a link that lands on the wrong verse is worse
   than no link. So Sörensen's Mahābhārata references and the Purāṇa Index's
   Br./M./Vi./वा. citations are NOT linked — they index the Calcutta and
   Venkateshwar editions, whose numbering does not match the BORI critical
   text the library holds. Add a scheme here only after checking a real
   citation against real data.
   ========================================================================= */
(function () {
  'use strict';
  window.DGE_VERSIONS = window.DGE_VERSIONS || {};
  window.DGE_VERSIONS['kosha-citations.js'] = 'v1.0';

  var DEV_DIGITS = '०१२३४५६७८९';
  function num(s) {
    s = String(s == null ? '' : s).trim();
    var out = '';
    for (var i = 0; i < s.length; i++) {
      var d = DEV_DIGITS.indexOf(s[i]);
      out += d >= 0 ? String(d) : s[i];
    }
    var n = parseInt(out, 10);
    return isNaN(n) ? null : n;
  }
  var ROMAN = { i: 1, v: 5, x: 10, l: 50, c: 100, d: 500, m: 1000 };
  function roman(s) {
    s = String(s || '').toLowerCase();
    if (!/^[ivxlcdm]+$/.test(s)) return null;
    var t = 0;
    for (var i = 0; i < s.length; i++) {
      var v = ROMAN[s[i]], nx = ROMAN[s[i + 1]];
      t += (nx && nx > v) ? -v : v;
    }
    return t || null;
  }
  function pad2(n) { return String(n).padStart(2, '0'); }

  /* ---------------------------------------------------------- schemes ---
     Each scheme: a regex over the gloss text, and a resolver returning
     { path, find(data), label }. find() gets the parsed data.json and
     returns { ref, text } or null when the verse is not in this library. */
  var SCHEMES = [
    {
      id: 'atharvaveda',
      // AV. 7,28,1 — kanda,sukta,mantra, Saunaka recension. NOT AVP.: that is
      // Paippalada, a different recension with different numbering, and it is
      // the commoner abbreviation in this corpus (402 vs 63). The negative
      // lookahead on P is what keeps the two apart.
      re: /\bAV(?!P)[ŚS]?\.\s*([०-९\d]{1,2})\s*[.,\-]\s*([०-९\d]{1,3})\s*[.,\-]\s*([०-९\d]{1,3})/g,
      resolve: function (m) {
        var ka = num(m[1]), su = num(m[2]), mn = num(m[3]);
        if (!ka || ka < 1 || ka > 20 || !su || !mn) return null;
        return {
          label: 'अथर्ववेदः ' + ka + '.' + su + '.' + mn,
          path: 'vedas/atharvaveda/shaunaka_shakha/samhita/kanda_' + pad2(ka),
          find: function (d) {
            var want = ka + '.' + su + '.' + mn;
            var hit = (d.items || []).filter(function (x) { return x.id === want; })[0];
            return hit ? { ref: want, text: hit.samhita_patha || hit.text || '' } : null;
          }
        };
      }
    },
    {
      id: 'raghuvamsha-dev',
      // रघु० ४-४४ / रघु० ८।३७ — sarga, verse. The danda is a separator here.
      re: /रघु\s*[०॰]?\.?\s*([०-९\d]{1,2})\s*[।\-.,]\s*([०-९\d]{1,3})/g,
      resolve: function (m) { return raghu(num(m[1]), num(m[2])); }
    },
    {
      id: 'raghuvamsha-apte',
      // Apte's "R. 17. 27" is Raghuvamsha; Bohtlingk's "R. 1, 15, 11" is the
      // Ramayana, in an edition whose numbering this library does not match.
      // Two guards keep them apart: no third number may follow, and the scheme
      // only runs inside dictionaries that use Apte's convention. Measured over
      // the corpus, the true two-number form is 193 hits in the Apte family
      // against 2 in Bohtlingk, and the three-number form is 188 in Bohtlingk.
      onlyIn: ['apte-1957', 'apte-1890', 'pract'],
      re: /\bR\.\s*(\d{1,2})\s*[.,]\s*(\d{1,3})(?![\s.,]*\d)/g,
      resolve: function (m) { return raghu(num(m[1]), num(m[2])); }
    },
    {
      id: 'rigveda',
      // ऋ.वे. 1.165 / ऋग्वेद 1.165.3 / RV 1.165.3 — maṇḍala.sūkta[.mantra]
      re: /(ऋ\s*॰?\.?\s*वे\s*॰?\.?|ऋग्वेदे?|RV\.?|ṚV\.?)\s*([०-९\d]{1,2})[.\-,\s]+([०-९\d]{1,3})(?:[.\-,\s]+([०-९\d]{1,3}))?/g,
      resolve: function (m) {
        var ma = num(m[2]), su = num(m[3]), mn = num(m[4]);
        if (!ma || ma < 1 || ma > 10 || !su) return null;
        var id = ma + '.' + su + (mn ? '.' + mn : '');
        return {
          label: 'ऋग्वेदः ' + id,
          path: 'vedas/rigveda/shakala_shakha/samhita/mandala_' + pad2(ma),
          find: function (d) {
            var items = d.items || [];
            var want = mn ? (ma + '.' + su + '.' + mn) : null;
            for (var i = 0; i < items.length; i++) {
              if (want ? items[i].id === want
                       : String(items[i].id || '').indexOf(ma + '.' + su + '.') === 0) {
                return { ref: items[i].id,
                         text: items[i].samhita_patha || items[i].text || '',
                         note: mn ? '' : 'first mantra of the sūkta' };
              }
            }
            return null;
          }
        };
      }
    },
    {
      id: 'bhagavata',
      // भा. IX. २२. ३३ — skandha.adhyāya.śloka, skandha in UPPERCASE roman.
      // Deliberately NOT the Latin "Bhā.": the Purāṇa Index writes the
      // Devanagari भा. with uppercase roman (4,503 of its 4,511 citations),
      // whereas pund-v1 writes "Bhā. i. 109. 14" with lowercase roman for a
      // different work entirely. Matching both made अगस्त्य offer twelve
      // Bhāgavata links that were nothing of the kind — and low chapter
      // numbers would have resolved to a real but wrong verse rather than
      // failing visibly. BhP. is unambiguous, so it stays.
      re: /(भा\s*॰?\.|BhP\.)\s*([IVXL]{1,5}|[०-९\d]{1,2})[.,\s]+([०-९\d]{1,3})[.,\s]+([०-९\d]{1,3})/g,
      resolve: function (m) {
        var sk = roman(m[2]) || num(m[2]), ad = num(m[3]), sl = num(m[4]);
        if (!sk || sk < 1 || sk > 12 || !ad || !sl) return null;
        return {
          label: 'भागवतम् ' + sk + '.' + ad + '.' + sl,
          // Pre-23-Aug-2026-restructure path was 'purana/bhagavata_purana/...'
          // directly; the real corpus now nests it one level deeper under
          // 'maha_purana' (dge/data/purana/maha_purana/bhagavata_purana/) --
          // same stale-path class of bug already documented for dvaitavedanta
          // elsewhere in this codebase. Left uncaught, every भा. citation here
          // 404'd load()'s fetch and showed "Not found in this library's
          // copy." even though the verse is actually digitized.
          path: 'purana/maha_purana/bhagavata_purana/skandha_' + pad2(sk),
          find: function (d) {
            var a = (d.items || []).filter(function (x) { return x.id === 'adhyaya_' + pad2(ad); })[0];
            if (!a) return null;
            var s = (a.shlokas || []).filter(function (x) { return num(x.number) === sl; })[0];
            return s ? { ref: sk + '.' + ad + '.' + sl, text: s.sanskrit_text || '' } : null;
          }
        };
      }
    },
    {
      id: 'gita',
      // गीता 2.47 / BhG 2.47
      re: /(गीता(?:याम्)?|भ\s*॰?\.?\s*गी\s*॰?\.?|BhG\.?|Gītā)\s*([०-९\d]{1,2})[.,\-\s]+([०-९\d]{1,3})/g,
      resolve: function (m) {
        var ad = num(m[2]), sl = num(m[3]);
        if (!ad || ad < 1 || ad > 18 || !sl) return null;
        return {
          label: 'गीता ' + ad + '.' + sl,
          path: 'itihasa/bhagavad_gita/adhyaya_' + pad2(ad),
          find: function (d) {
            var a = (d.items || [])[0];
            if (!a) return null;
            var s = (a.shlokas || []).filter(function (x) { return num(x.number) === sl; })[0];
            return s ? { ref: ad + '.' + sl, text: s.sanskrit_text || '' } : null;
          }
        };
      }
    }
  ];

  function raghu(sa, vs) {
    if (!sa || sa < 1 || sa > 19 || !vs) return null;
    return {
      label: 'रघुवंशम् ' + sa + '.' + vs,
      path: 'kavya_alankara/raghuvamsha/mula',
      find: function (d) {
        var s2 = (d.items || []).filter(function (x) {
          return x.id === 'sarga_' + pad2(sa) || x.id === 'sarga_0' + pad2(sa); })[0];
        if (!s2) return null;
        var v = (s2.shlokas || []).filter(function (x) { return num(x.number) === vs; })[0];
        return v ? { ref: sa + '.' + vs, text: v.sanskrit_text || '' } : null;
      }
    };
  }

  /* ------------------------------------------------------------ data --- */
  var cache = {};
  function load(path) {
    if (cache[path]) return cache[path];
    cache[path] = fetch('data/' + path + '/data.json')
      .then(function (r) { return r.ok ? r.json() : null; })
      .catch(function () { return null; });
    return cache[path];
  }

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; });
  }

  /* ---------------------------------------------------------- popover --- */
  var card = null;
  function close() { if (card) { card.remove(); card = null; } }

  function open(spec) {
    close();
    card = document.createElement('div');
    card.className = 'dge-cite-card';
    card.innerHTML =
      '<div class="dge-cite-head"><span class="dge-cite-title">' + esc(spec.label) + '</span>' +
      '<button class="dge-cite-btn" data-a="min" title="Minimise">–</button>' +
      '<button class="dge-cite-btn" data-a="close" title="Close">✕</button></div>' +
      '<div class="dge-cite-body">…</div>';
    document.body.appendChild(card);

    card.querySelector('[data-a=close]').onclick = close;
    card.querySelector('[data-a=min]').onclick = function () {
      var m = card.classList.toggle('min');
      this.textContent = m ? '+' : '–';
      this.title = m ? 'Expand' : 'Minimise';
    };
    drag(card, card.querySelector('.dge-cite-head'));

    var body = card.querySelector('.dge-cite-body');
    load(spec.path).then(function (d) {
      var hit = d && spec.find(d);
      if (!hit) {
        body.innerHTML = '<div class="dge-cite-miss">Not found in this library’s copy.</div>';
        return;
      }
      body.innerHTML = '<div class="dge-cite-ref">' + esc(hit.ref) +
        (hit.note ? ' <span class="dge-cite-note">(' + esc(hit.note) + ')</span>' : '') + '</div>' +
        '<div class="dge-cite-text">' + esc(hit.text) + '</div>' +
        '<a class="dge-cite-go" href="?path=' + esc(encodeURI(spec.path)) + '">Open the full text →</a>';
    });
  }

  // Floating: the card is draggable by its header, so it can be parked out of
  // the way of whatever the reader is comparing it against.
  function drag(box, handle) {
    var sx = 0, sy = 0, ox = 0, oy = 0, on = false;
    function down(e) {
      if (e.target.classList.contains('dge-cite-btn')) return;
      var p = e.touches ? e.touches[0] : e, r = box.getBoundingClientRect();
      on = true; sx = p.clientX; sy = p.clientY; ox = r.left; oy = r.top;
      box.style.right = 'auto'; box.style.bottom = 'auto';
      e.preventDefault();
    }
    function move(e) {
      if (!on) return;
      var p = e.touches ? e.touches[0] : e;
      box.style.left = Math.max(4, Math.min(ox + p.clientX - sx, window.innerWidth - 60)) + 'px';
      box.style.top = Math.max(4, Math.min(oy + p.clientY - sy, window.innerHeight - 40)) + 'px';
    }
    function up() { on = false; }
    handle.addEventListener('mousedown', down); handle.addEventListener('touchstart', down, { passive: false });
    document.addEventListener('mousemove', move); document.addEventListener('touchmove', move, { passive: false });
    document.addEventListener('mouseup', up); document.addEventListener('touchend', up);
  }

  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') close(); });

  /* ----------------------------------------------------------- markup --- */
  // Walks text nodes only, so nothing already marked up (sūtra links from
  // intellisense.js, for instance) is touched or double-wrapped.
  window.dgeMarkCitations = function (root, opts) {
    if (!root) return 0;
    var source = (opts && opts.source) || null;
    injectCSS();
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode: function (n) {
        if (!n.nodeValue || n.nodeValue.length < 5) return NodeFilter.FILTER_REJECT;
        var p = n.parentNode;
        while (p && p !== root) {
          var t = p.nodeName;
          if (t === 'A' || t === 'BUTTON' || (p.classList && p.classList.contains('dge-cite'))) return NodeFilter.FILTER_REJECT;
          p = p.parentNode;
        }
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    var jobs = [], n, count = 0;
    while ((n = walker.nextNode())) jobs.push(n);

    jobs.forEach(function (node) {
      var text = node.nodeValue, hits = [];
      SCHEMES.forEach(function (sc) {
        // A scheme restricted to particular dictionaries is skipped elsewhere,
        // and skipped entirely when the caller did not say which dictionary
        // this text came from — guessing would defeat the restriction.
        if (sc.onlyIn && (!source || sc.onlyIn.indexOf(source) < 0)) return;
        sc.re.lastIndex = 0;
        var m;
        while ((m = sc.re.exec(text))) {
          var spec = sc.resolve(m);
          if (spec) hits.push({ start: m.index, end: m.index + m[0].length, raw: m[0], spec: spec });
        }
      });
      if (!hits.length) return;
      hits.sort(function (a, b) { return a.start - b.start; });
      // drop overlaps — first scheme to claim a span keeps it
      var kept = [];
      hits.forEach(function (h) { if (!kept.length || h.start >= kept[kept.length - 1].end) kept.push(h); });

      var frag = document.createDocumentFragment(), at = 0;
      kept.forEach(function (h) {
        if (h.start > at) frag.appendChild(document.createTextNode(text.slice(at, h.start)));
        var a = document.createElement('span');
        a.className = 'dge-cite';
        a.textContent = h.raw;
        a.title = h.spec.label;
        a.onclick = function (ev) { ev.stopPropagation(); open(h.spec); };
        frag.appendChild(a);
        at = h.end; count++;
      });
      if (at < text.length) frag.appendChild(document.createTextNode(text.slice(at)));
      node.parentNode.replaceChild(frag, node);
    });
    return count;
  };

  function injectCSS() {
    if (document.getElementById('dge-cite-css')) return;
    var s = document.createElement('style'); s.id = 'dge-cite-css';
    s.textContent = [
      '.dge-cite{border-bottom:1px dotted var(--accent-red,#8a5a2b);color:var(--accent-red,#8a5a2b);cursor:pointer}',
      // above the कोश overlay (11000), which is where these mostly appear
      '.dge-cite-card{position:fixed;right:16px;bottom:16px;z-index:12000;width:min(380px,calc(100vw - 32px));',
      '  background:var(--card-bg,#fffdf8);color:var(--text-primary,#222);border:1px solid var(--card-border,#e6ddcf);',
      '  border-radius:12px;box-shadow:0 6px 28px rgba(0,0,0,.28);font-size:15px;overflow:hidden}',
      '.dge-cite-head{display:flex;align-items:center;gap:6px;padding:8px 10px;background:var(--card-active,#f3ece1);',
      '  cursor:move;user-select:none;border-bottom:1px solid var(--card-border,#e6ddcf)}',
      '.dge-cite-title{flex:1;font-weight:600;font-size:14px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}',
      '.dge-cite-btn{background:none;border:none;font-size:15px;line-height:1;cursor:pointer;color:inherit;padding:2px 6px}',
      '.dge-cite-body{padding:10px 12px;max-height:50vh;overflow:auto}',
      '.dge-cite-card.min .dge-cite-body{display:none}',
      '.dge-cite-ref{font-size:12px;color:var(--muted-text,#888);margin-bottom:4px}',
      '.dge-cite-note{font-style:italic}',
      '.dge-cite-text{font-size:17px;line-height:1.7}',
      '.dge-cite-miss{font-size:14px;color:var(--muted-text,#888)}',
      '.dge-cite-go{display:inline-block;margin-top:10px;font-size:13px;color:var(--accent-red,#8a5a2b)}'
    ].join('\n');
    document.head.appendChild(s);
  }
})();
