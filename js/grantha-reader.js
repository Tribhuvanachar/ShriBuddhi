// grantha-reader.js — the work.json-aware reader for grantha_work_v2
// families (tools/reports/grantha_data_architecture.md). Additive preview
// beside the classic reader, per the kosha2 precedent: replaces nothing
// until the project lead signs off.
(function () {
  'use strict';
  window.DGE_VERSIONS = window.DGE_VERSIONS || {};
  window.DGE_VERSIONS['grantha-reader.js'] =
    'v1.4 (bhashya layer = Setu Tila edition: structural headings, pathantara footnotes, pramana citations rendered) · v1.3 (mangala folded into the first pada as a collapsible section; 0.0 out of the pada dropdown so jijnasadhikarana is the first left-nav entry) · v1.2 (3 Sep 2026 report: filterable sutra drawer (☰) grouped by adhikarana · per-card "sarvah vyakhyah" expansion loading every commentary for ONE sutra · chip double-click FOCUS shows only the refs a commentary actually glosses, auto-enabling its chain, jumping to its first pada when the current one is empty · ⚙ settings: what a sutra-list tap opens; v1.1: adhikarana select + dividers, wrapped chips; v1.0: chain-depth chips, lazy layers, pada nav, #ref links)';

  // v2 families available to this reader. Paths are relative to .
  var REGISTRY = {
    brahma_sutra: {
      path: 'data/darshana/vedanta/dvaita/DvaitaVedantaIn/sutra_prasthana/brahma_sutra',
      base_label: 'सूत्रम्'
    },
    anuvyakhyana_sudha: {
      path: 'data/darshana/vedanta/dvaita/DvaitaVedantaIn/sutra_prasthana/anuvyakhyana_sudha',
      base_label: 'अनुव्याख्यानम्'
    }
  };
  var ADH_NAME = ['मङ्गलम्', 'प्रथमाध्यायः', 'द्वितीयाध्यायः', 'तृतीयाध्यायः', 'चतुर्थाध्यायः'];
  var PAD_NAME = ['', 'प्रथमः पादः', 'द्वितीयः पादः', 'तृतीयः पादः', 'चतुर्थः पादः'];

  var state = {
    work: '', root: '', wj: null,
    base: '',                  // base layer slug (first in work.json)
    depth: {},                 // slug -> chain depth (0 = base)
    enabled: [],               // enabled layer slugs, persisted
    loaded: {},                // slug -> { byRef: {ref:[units]}, order:[refs] }
    loading: {},
    padas: [],                 // ["1.1", ...] from base layer
    pada: '', hlRef: '',
    adhik: '',                 // '' = whole pada; else filter to one adhikarana
    focus: '',                 // layer slug: show only refs this layer glosses
    cardAll: {},               // ref -> 1: this card shows EVERY layer's units
    drawer: false,
    cfg: { tap: 'all' }        // tap: what a sutra-list tap / card ⊕ opens —
                               // 'all' every commentary · 'chips' enabled only · 'off'
  };
  function cfgKey() { return 'grantha2_cfg_' + state.work; }
  function loadCfg() {
    try {
      var c = JSON.parse(localStorage.getItem(cfgKey()) || 'null');
      if (c && c.tap) state.cfg = c;
    } catch (e) {}
  }
  function saveCfg() { try { localStorage.setItem(cfgKey(), JSON.stringify(state.cfg)); } catch (e) {} }

  function $(s, r) { return (r || document).querySelector(s); }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c];
    });
  }
  function lsKey() { return 'grantha2_layers_' + state.work; }
  function refKey(r) { return r.split('.').map(Number); }
  function toast(msg) {
    var t = $('#g2Toast'); t.textContent = msg; t.hidden = false;
    clearTimeout(toast._t); toast._t = setTimeout(function () { t.hidden = true; }, 2000);
  }

  function fetchLayer(slug) {
    if (state.loaded[slug]) return Promise.resolve(state.loaded[slug]);
    if (state.loading[slug]) return state.loading[slug];
    state.loading[slug] = fetch(state.root + '/' + slug + '/data.json')
      .then(function (r) { if (!r.ok) throw new Error(slug + ' HTTP ' + r.status); return r.json(); })
      .then(function (d) {
        var byRef = {}, order = [];
        (d.units || []).forEach(function (u) {
          if (!byRef[u.ref]) { byRef[u.ref] = []; order.push(u.ref); }
          byRef[u.ref].push(u);
        });
        state.loaded[slug] = { byRef: byRef, order: order };
        delete state.loading[slug];
        return state.loaded[slug];
      });
    return state.loading[slug];
  }

  function chainDepth() {
    var by = {};
    (state.wj.layers || []).forEach(function (L) { by[L.slug] = L; });
    function d(slug, seen) {
      var L = by[slug];
      if (!L || slug === state.base) return 0;
      var co = L.commentary_on;
      if (!co || !by[co] || seen[slug]) return 1;   // unverified chain: level 1
      seen[slug] = 1;
      return 1 + d(co, seen);
    }
    (state.wj.layers || []).forEach(function (L) { state.depth[L.slug] = d(L.slug, {}); });
  }

  // ---- header / controls --------------------------------------------------
  function renderChips() {
    var el = $('#g2Layers');
    el.innerHTML = (state.wj.layers || []).map(function (L) {
      var on = state.enabled.indexOf(L.slug) >= 0;
      var depth = state.depth[L.slug] || 0;
      return '<button data-layer="' + esc(L.slug) + '" class="' + (on ? 'on' : '') +
        (state.focus === L.slug ? ' focus' : '') +
        ' d' + Math.min(depth, 3) + '" title="' + esc(L.author || '') +
        (L.commentary_on ? ' · on ' + esc(L.commentary_on) : '') +
        ' · double-click: only this commentary\'s places">' +
        (depth ? '<span class="tw">' + '›'.repeat(depth) + '</span>' : '') +
        '<span lang="sa">' + esc(L.title) + '</span>' +
        '<span class="n">' + (L.units || '') + '</span></button>';
    }).join('');
    el.querySelectorAll('[data-layer]').forEach(function (b) {
      // single click toggles; double-click focuses. The toggle waits a beat
      // so a double-tap does not fire it first.
      var t = null;
      b.onclick = function () {
        clearTimeout(t);
        t = setTimeout(function () { toggleLayer(b.dataset.layer); }, 260);
      };
      b.ondblclick = function (e) {
        e.preventDefault(); clearTimeout(t);
        toggleFocus(b.dataset.layer);
      };
    });
  }

  // FOCUS: show only the refs one commentary actually glosses, with its
  // whole chain (the lead's report: an 8-unit layer "shows nothing" — its
  // few refs sat in another pada, and nothing said so)
  function chainOf(slug) {
    var by = {};
    (state.wj.layers || []).forEach(function (L) { by[L.slug] = L; });
    var out = [], cur = slug, seen = {};
    while (cur && by[cur] && !seen[cur]) {
      seen[cur] = 1; out.push(cur);
      cur = cur === state.base ? '' : (by[cur].commentary_on || state.base);
    }
    if (out.indexOf(state.base) < 0) out.push(state.base);
    return out;
  }
  function toggleFocus(slug) {
    if (state.focus === slug || slug === state.base) {
      state.focus = '';
      renderChips(); renderNav(); renderPada();
      if (slug !== state.base) toast('Focus cleared — full view');
      return;
    }
    var chain = chainOf(slug);
    toast('Loading ' + slug + ' with its chain…');
    Promise.all(chain.map(fetchLayer)).then(function () {
      chain.forEach(function (s) {
        if (state.enabled.indexOf(s) < 0) state.enabled.push(s);
      });
      try { localStorage.setItem(lsKey(), JSON.stringify(state.enabled)); } catch (e) {}
      state.focus = slug;
      // land where the commentary actually is: first pada with units,
      // if the current one has none
      var L = state.loaded[slug];
      var here = L.order.some(function (r) { return r.indexOf(state.pada + '.') === 0; });
      if (!here && L.order.length) {
        state.pada = L.order[0].split('.').slice(0, 2).join('.');
        state.adhik = '';
      }
      renderChips(); renderNav(); renderPada(); window.scrollTo(0, 0);
    }).catch(function (e) { toast(String(e.message || e)); });
  }

  function toggleLayer(slug) {
    var i = state.enabled.indexOf(slug);
    if (i >= 0) {
      if (slug === state.base) { toast('मूलपाठं न निवार्यते — the base text stays on'); return; }
      state.enabled.splice(i, 1);
      finishToggle();
    } else {
      state.enabled.push(slug);
      toast('Loading ' + slug + '…');
      fetchLayer(slug).then(finishToggle).catch(function (e) {
        state.enabled = state.enabled.filter(function (s) { return s !== slug; });
        toast(String(e.message || e));
        renderChips();
      });
    }
    function finishToggle() {
      try { localStorage.setItem(lsKey(), JSON.stringify(state.enabled)); } catch (e) {}
      renderChips(); renderPada();
    }
  }

  function padaAdhikaranas(p) {
    // adhikaranas of a pada, in first-appearance order, with sutra counts
    var base = state.loaded[state.base];
    var out = [], idx = {};
    if (!base) return out;
    base.order.forEach(function (r) {
      if (r.indexOf(p + '.') !== 0) return;
      (base.byRef[r] || []).forEach(function (u) {
        var a = u.adhikarana;
        if (!a) return;
        if (!(a in idx)) { idx[a] = out.length; out.push({ name: a, n: 0 }); }
        out[idx[a]].n++;
      });
    });
    return out;
  }

  // the mangala pada (0.0) is NOT a pada of its own — it is folded into the
  // first real pada as a collapsible section (renderPada), so it never appears
  // in the pada dropdown or the ‹ › walk.
  function navPadas() {
    return state.padas.filter(function (p) { return p !== '0.0'; });
  }

  function renderNav() {
    var sel = $('#g2Pada');
    sel.innerHTML = navPadas().map(function (p) {
      var ap = p.split('.');
      var label = ADH_NAME[+ap[0]] + ' · ' + PAD_NAME[+ap[1]];
      return '<option value="' + p + '"' + (p === state.pada ? ' selected' : '') + '>' +
        label + ' (' + p + ')</option>';
    }).join('');
    sel.onchange = function () { gotoPada(sel.value); };
    var asel = $('#g2Adhik');
    var adhs = padaAdhikaranas(state.pada);
    asel.hidden = !adhs.length;
    asel.innerHTML = '<option value="">सर्वाणि अधिकरणानि (' + adhs.length + ')</option>' +
      adhs.map(function (a) {
        return '<option value="' + esc(a.name) + '"' +
          (a.name === state.adhik ? ' selected' : '') + '>' +
          esc(a.name) + ' · ' + a.n + '</option>';
      }).join('');
    asel.onchange = function () { state.adhik = asel.value; renderPada(); window.scrollTo(0, 0); };
    $('#g2Prev').onclick = function () { step(-1); };
    $('#g2Next').onclick = function () { step(1); };
    $('#g2Drawer').onclick = function () { state.drawer = !state.drawer; renderDrawer(); };
    $('#g2Cfg').onclick = openCfg;
    function step(d) {
      var np = navPadas();
      var i = np.indexOf(state.pada) + d;
      if (i >= 0 && i < np.length) gotoPada(np[i]);
    }
  }

  function gotoPada(p, hlRef) {
    state.pada = p; state.hlRef = hlRef || '';
    state.adhik = '';            // a fresh pada starts unfiltered
    renderNav(); renderPada(); renderDrawer();
    if (!hlRef) window.scrollTo(0, 0);
  }

  // ---- content ------------------------------------------------------------
  function unitsAt(slug, ref) {
    var L = state.loaded[slug];
    return (L && L.byRef[ref]) || [];
  }
  function layerMeta(slug) {
    return (state.wj.layers || []).filter(function (L) { return L.slug === slug; })[0];
  }

  // one card, every commentary: fetch whatever is not here yet, then flip
  function expandCard(ref) {
    if (state.cardAll[ref]) {
      delete state.cardAll[ref];
      renderPada();
      var el0 = document.getElementById('ref-' + ref);
      if (el0) el0.scrollIntoView({ block: 'start' });
      return;
    }
    var all = (state.wj.layers || []).map(function (L) { return L.slug; });
    var todo = all.filter(function (s) { return !state.loaded[s]; });
    if (todo.length) toast('Loading ' + todo.length + ' commentaries…');
    Promise.all(all.map(fetchLayer)).then(function () {
      state.cardAll[ref] = 1;
      renderPada();
      var el = document.getElementById('ref-' + ref);
      if (el) el.scrollIntoView({ block: 'start' });
      var n = all.filter(function (s) {
        return s !== state.base && unitsAt(s, ref).length;
      }).length;
      toast(n + ' व्याख्याः अस्मिन् सूत्रे');
    }).catch(function (e) { toast(String(e.message || e)); });
  }

  // ---- sutra drawer (☰): the pada's sutras, filterable, adhikarana-wise ----
  function renderDrawer() {
    var side = $('#g2Side');
    side.hidden = !state.drawer;
    $('#g2Drawer').classList.toggle('on', state.drawer);
    if (!state.drawer) return;
    var base = state.loaded[state.base];
    if (!base) { side.innerHTML = ''; return; }
    var refs = base.order.filter(function (r) { return r.indexOf(state.pada + '.') === 0; })
      .sort(function (a, b) {
        var ka = refKey(a), kb = refKey(b);
        return ka[0] - kb[0] || ka[1] - kb[1] || ka[2] - kb[2];
      });
    var lastA = null;
    side.innerHTML = '<div class="g2-side-head">' +
      '<input id="g2SideFilter" type="search" placeholder="सूत्रं अन्विष्यताम् — text or 1.1.5" lang="sa">' +
      '</div><div class="g2-side-list">' +
      refs.map(function (ref) {
        var bu = base.byRef[ref] || [];
        var a = bu.map(function (u) { return u.adhikarana || ''; }).filter(Boolean)[0] || '';
        var head = '';
        if (a && a !== lastA) { lastA = a; head = '<div class="g2-side-adhik" lang="sa">' + esc(a) + '</div>'; }
        var snip = (bu[0] ? bu[0].text : '').replace(/\s+/g, ' ').slice(0, 52);
        return head + '<button data-goref="' + esc(ref) + '" data-t="' + esc(ref + ' ' + snip) + '">' +
          '<span class="r">' + esc(ref) + '</span><span lang="sa">' + esc(snip) + '</span></button>';
      }).join('') + '</div>';
    var fi = $('#g2SideFilter');
    fi.oninput = function () {
      var q = fi.value.trim();
      side.querySelectorAll('[data-goref]').forEach(function (b) {
        b.hidden = q && b.dataset.t.indexOf(q) < 0;
      });
      // an adhikarana heading with every sutra under it hidden hides too
      side.querySelectorAll('.g2-side-adhik').forEach(function (h) {
        var n = h.nextElementSibling, any = false;
        while (n && !n.classList.contains('g2-side-adhik')) {
          if (!n.hidden) { any = true; break; }
          n = n.nextElementSibling;
        }
        h.hidden = q && !any;
      });
    };
    side.querySelectorAll('[data-goref]').forEach(function (b) {
      b.onclick = function () {
        var ref = b.dataset.goref;
        state.hlRef = ref;
        if (window.innerWidth < 1000) { state.drawer = false; renderDrawer(); }
        if (state.cfg.tap === 'all' && !state.cardAll[ref]) expandCard(ref);
        else {
          renderPada();
          var el = document.getElementById('ref-' + ref);
          if (el) el.scrollIntoView({ block: 'start' });
        }
      };
    });
  }

  // ---- ⚙ settings ----------------------------------------------------------
  function openCfg() {
    var dlg = $('#g2CfgDlg');
    var opts = [
      ['all', 'सर्वाः व्याख्याः — open every commentary on that sutra'],
      ['chips', 'चयनिताः एव — just scroll; show the selected commentaries'],
      ['off', 'न किमपि — scroll only, hide the ⊕ buttons']
    ];
    dlg.innerHTML = '<h4>ग्रन्थपाठकः · Settings</h4>' +
      '<div class="g2-note">When a sutra is opened from the ☰ list:</div>' +
      opts.map(function (o) {
        return '<label class="g2-opt"><input type="radio" name="g2tap" value="' + o[0] + '"' +
          (state.cfg.tap === o[0] ? ' checked' : '') + '> ' + esc(o[1]) + '</label>';
      }).join('') +
      '<div class="g2-note" style="margin-top:10px">Tips · double-click a commentary chip to see ONLY the places it comments on (its chain opens by itself) · ⊕ सर्वाः व्याख्याः on any sutra card opens everything for that one sutra.</div>' +
      '<div class="g2-dlg-row"><button id="g2CfgClose">Close</button></div>';
    dlg.querySelectorAll('[name=g2tap]').forEach(function (r) {
      r.onchange = function () { state.cfg.tap = r.value; saveCfg(); renderPada(); };
    });
    $('#g2CfgClose').onclick = function () { dlg.close(); };
    dlg.showModal();
  }

  function layerBlock(L, ref) {
    var us = unitsAt(L.slug, ref);
    if (!us.length) return '';
    var depth = Math.min(state.depth[L.slug] || 1, 3);
    return '<section class="g2-layer d' + depth + '">' +
      '<div class="g2-lname"><span lang="sa">' + esc(L.title) + '</span>' +
      (L.author ? '<span class="au" lang="sa">' + esc(L.author) + '</span>' : '') + '</div>' +
      us.map(function (u) {
        // structural heading node (the edition's own adhyaya / upodghata etc.)
        if (u.kind === 'heading') {
          return '<div class="g2-lheading l' + (u.level || 2) + '" lang="sa">' +
            esc(u.text) + '</div>';
        }
        // an edition that ships sanitised inline markup (Setu Tila: pramana
        // citations, kutra cross-refs, pathantara footnotes) carries it in
        // u.html — already escaped/whitelisted by the importer; otherwise the
        // plain u.text is escaped here.
        var bodyHtml = u.html ? u.html : esc(u.text).replace(/\n/g, '<br>');
        var fnotes = (u.footnotes && u.footnotes.length)
          ? '<div class="g2-fnotes">' + u.footnotes.map(function (nt, i) {
              return '<div class="g2-fnote"><sup>' + (i + 1) + '</sup> ' + esc(nt) + '</div>';
            }).join('') + '</div>'
          : '';
        return '<p class="g2-para' + (u.kind === 'colophon' ? ' g2-colophon' : '') +
          '" id="u-' + esc(u.id) + '" lang="sa">' + bodyHtml +
          '<button class="g2-pid" data-copyid="' + esc(u.id) + '" title="Copy paragraph link">¶' +
          esc(u.id.split('.').pop().slice(1)) + '</button>' + fnotes + '</p>';
      }).join('') + '</section>';
  }

  function renderPada() {
    var main = $('#g2Main');
    var base = state.loaded[state.base];
    if (!base) { main.innerHTML = '<div class="g2-empty">Loading…</div>'; return; }
    var others = (state.wj.layers || []).filter(function (L) {
      return L.slug !== state.base && state.enabled.indexOf(L.slug) >= 0;
    });
    // refs are the UNION across enabled layers: the mangala pada (0.0) has
    // commentary units with no base sutra, and a tika can gloss a ref the
    // base skips — those cards must still render
    var seen = {};
    var refs = [];
    [state.base].concat(others.map(function (L) { return L.slug; }))
      .forEach(function (slug) {
        var Ld = state.loaded[slug];
        if (!Ld) return;
        Ld.order.forEach(function (r) {
          if (r.indexOf(state.pada + '.') === 0 && !seen[r]) { seen[r] = 1; refs.push(r); }
        });
      });
    refs.sort(function (a, b) {
      var ka = refKey(a), kb = refKey(b);
      return ka[0] - kb[0] || ka[1] - kb[1] || ka[2] - kb[2];
    });
    var banner = '';
    if (state.focus) {
      refs = refs.filter(function (r) { return unitsAt(state.focus, r).length; });
      var FL = layerMeta(state.focus);
      banner = '<div class="g2-banner"><span lang="sa">' + esc(FL ? FL.title : state.focus) +
        '</span> — तस्याः स्थानान्येव दृश्यन्ते (' + refs.length + ' अस्मिन् पादे)' +
        '<button id="g2FocusOff">✕ full view</button></div>';
    }
    // one sutra card (base text + the commentary layers for this ref)
    function cardHtml(ref) {
      var bu = base.byRef[ref] || [];
      var topic = bu.map(function (u) { return u.topic || ''; }).filter(Boolean)[0];
      var expanded = !!state.cardAll[ref];
      // an expanded card shows EVERY layer that glosses this ref (loaded on
      // demand); otherwise the globally enabled ones
      var blocks = (expanded
        ? (state.wj.layers || []).filter(function (L) { return L.slug !== state.base; })
        : others);
      var expBtn = state.cfg.tap === 'off' ? '' :
        '<button class="g2-expbtn' + (expanded ? ' on' : '') + '" data-expand="' + esc(ref) +
        '" title="' + (expanded ? 'Back to the selected commentaries' : 'Open every commentary on this sutra') + '" lang="sa">' +
        (expanded ? '⊖ चयनिताः' : '⊕ सर्वाः व्याख्याः') + '</button>';
      return '<article class="g2-card' + (ref === state.hlRef ? ' hl' : '') +
        '" id="ref-' + esc(ref) + '">' +
        '<header class="g2-chead"><span class="g2-ref">' + esc(ref) + '</span>' +
        (topic ? '<span class="g2-topic" lang="sa">' + esc(topic) + '</span>' : '') +
        expBtn +
        '<button class="g2-linkbtn" data-reflink="' + esc(ref) + '" title="Copy link">🔗</button></header>' +
        (bu.length ? '<div class="g2-base" lang="sa">' + bu.map(function (u) {
          return esc(u.text).replace(/\n/g, '<br>');
        }).join('<br>') + '</div>' : '') +
        blocks.map(function (L) { return layerBlock(L, ref); }).join('');
    }

    // The mangala (pada 0.0) is shown as a collapsible section at the very top
    // of the FIRST real pada — not as a pada of its own. Built once here.
    var mangalaHtml = '';
    if (state.pada === (navPadas()[0] || '') && !state.adhik && !state.focus) {
      var mRefs = [];
      [state.base].concat(others.map(function (L) { return L.slug; })).forEach(function (slug) {
        var Ld = state.loaded[slug];
        if (!Ld) return;
        Ld.order.forEach(function (r) {
          if (r.indexOf('0.0.') === 0 && mRefs.indexOf(r) < 0) mRefs.push(r);
        });
      });
      if (mRefs.length) {
        mRefs.sort(function (a, b) { var ka = refKey(a), kb = refKey(b); return ka[2] - kb[2]; });
        mangalaHtml = '<details class="g2-mangala"><summary lang="sa">मङ्गलाचरणम्' +
          '<span class="n">' + mRefs.length + '</span></summary>' +
          '<div class="g2-mangala-body">' +
          mRefs.map(function (r) { return cardHtml(r) + '</article>'; }).join('') +
          '</div></details>';
      }
    }

    var lastAdhik = null;
    main.innerHTML = banner + mangalaHtml + refs.map(function (ref) {
      var bu = base.byRef[ref] || [];
      var adhik = bu.map(function (u) { return u.adhikarana || ''; }).filter(Boolean)[0] || '';
      if (state.adhik && adhik !== state.adhik) return '';
      var divider = '';
      if (adhik && adhik !== lastAdhik) {
        lastAdhik = adhik;
        divider = '<div class="g2-adhik-head" lang="sa">' + esc(adhik) +
          '<span class="n">' + esc(ref) + '–</span></div>';
      }
      return divider + cardHtml(ref) + '</article>';
    }).join('') || '<div class="g2-empty">No units here.</div>';
    if (state.adhik && !main.querySelector('.g2-card')) {
      main.innerHTML = '<div class="g2-empty">इदम् अधिकरणम् अस्मिन् पादे नास्ति।</div>';
    }
    if (state.focus && !refs.length) {
      main.innerHTML = banner + '<div class="g2-empty">अस्मिन् पादे इयं व्याख्या नास्ति — ‹ › इति पादान्तरं पश्यतु।</div>';
      var fo0 = $('#g2FocusOff'); if (fo0) fo0.onclick = function () { toggleFocus(state.focus); };
      return;
    }
    var fo = $('#g2FocusOff');
    if (fo) fo.onclick = function () { toggleFocus(state.focus); };
    main.querySelectorAll('[data-expand]').forEach(function (b) {
      b.onclick = function () { expandCard(b.dataset.expand); };
    });

    main.querySelectorAll('[data-reflink]').forEach(function (b) {
      b.onclick = function () { copyLink('#ref=' + b.dataset.reflink); };
    });
    main.querySelectorAll('[data-copyid]').forEach(function (b) {
      b.onclick = function () { copyLink('#unit=' + b.dataset.copyid); };
    });
    if (state.hlRef) {
      var el = document.getElementById('ref-' + state.hlRef);
      if (el) el.scrollIntoView({ block: 'start' });
    }
  }

  function copyLink(hash) {
    var url = location.origin + location.pathname + '?work=' + encodeURIComponent(state.work) + hash;
    (navigator.clipboard ? navigator.clipboard.writeText(url) : Promise.reject())
      .then(function () { toast('Link copied'); })
      .catch(function () { toast(url); });
  }

  // ---- boot ---------------------------------------------------------------
  function pickWork() {
    var main = $('#g2Main');
    main.innerHTML = '<div class="g2-empty">ग्रन्थं वृणुत — choose a work</div>' +
      '<div class="g2-pick">' + Object.keys(REGISTRY).map(function (w) {
        return '<a href="?work=' + esc(w) + '">' + esc(w) + '</a>';
      }).join('') + '</div>';
  }

  function boot() {
    var q = new URLSearchParams(location.search);
    var w = q.get('work') || '';
    if (!REGISTRY[w]) { pickWork(); return; }
    state.work = w;
    state.root = REGISTRY[w].path;
    loadCfg();
    fetch(state.root + '/work.json')
      .then(function (r) { return r.json(); })
      .then(function (wj) {
        state.wj = wj;
        state.base = (wj.layers && wj.layers[0] && wj.layers[0].slug) || 'mula';
        chainDepth();
        $('#g2Title').innerHTML = '<span lang="sa">' + esc(wj.title || w) + '</span>';
        document.title = (wj.title || w) + ' · DGE';
        try {
          state.enabled = JSON.parse(localStorage.getItem(lsKey()) || 'null') || [];
        } catch (e) { state.enabled = []; }
        // drop slugs the manifest no longer knows (a layer renamed or merged
        // away, e.g. tattvaprakashikabhavabodha → bhavabodha) — a stale saved
        // toggle must not 404 the whole boot
        var valid = {};
        (wj.layers || []).forEach(function (L) { valid[L.slug] = 1; });
        state.enabled = state.enabled.filter(function (s) { return valid[s]; });
        if (!state.enabled.length) {
          // default view: the base text plus its first direct commentary
          state.enabled = [state.base];
          var first = (wj.layers || []).filter(function (L) {
            return L.commentary_on === state.base;
          })[0];
          if (first) state.enabled.push(first.slug);
        }
        if (state.enabled.indexOf(state.base) < 0) state.enabled.unshift(state.base);
        var m = location.hash.match(/(?:ref|unit)=([\d.]+)/);
        var target = m ? m[1] : '';
        var targetPada = target ? target.split('.').slice(0, 2).join('.') : '';
        return Promise.all(state.enabled.map(fetchLayer)).then(function () {
          // work.json carries the pada union across ALL layers (the mangala
          // pada 0.0 exists only in the commentaries); fall back to deriving
          // from the base layer for older manifests
          var baseL = state.loaded[state.base];
          var seen = {};
          state.padas = (wj.padas && wj.padas.length) ? wj.padas.slice()
            : baseL.order.map(function (r) {
              return r.split('.').slice(0, 2).join('.');
            }).filter(function (p) { return seen[p] ? 0 : (seen[p] = 1); })
              .sort(function (a, b) {
                var ka = a.split('.').map(Number), kb = b.split('.').map(Number);
                return ka[0] - kb[0] || ka[1] - kb[1];
              });
          renderChips();
          // 0.0 (mangala) is not a landing pada — it lives folded into the
          // first real pada; a deep link into it opens that pada instead.
          var firstReal = navPadas()[0] || state.padas[0];
          var startPada = (targetPada && targetPada !== '0.0' &&
            state.padas.indexOf(targetPada) >= 0) ? targetPada : firstReal;
          gotoPada(startPada, target ? target.split('.').slice(0, 3).join('.') : '');
        });
      })
      .catch(function (e) {
        $('#g2Main').innerHTML = '<div class="g2-empty">Could not load this work (' +
          esc(String(e.message || e)) + ').</div>';
      });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
