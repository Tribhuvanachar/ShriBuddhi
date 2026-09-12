/* =========================================================================
   DGE · रूपसिद्धिः — the derivation workbench.

   Any root + any stack of upasargas + any sanadi affix (णिच् / सन् / यङ् /
   यङ्लुक्, singly or chained) + kartari or karmani, across all 11 lakaras
   (लेट् and लृङ् included) — and every kridanta with its declension in all
   three lingas. Every form opens its full step-by-step derivation, each
   step naming the rule that produced it.

   All of it is derived ON THIS DEVICE by vidyut-prakriya compiled to
   WebAssembly (dge/wasm/vidyut/, Apache-2.0, the Ambuda project) — the
   same engine that generates this repo's precomputed prakriya/ data — so
   arbitrary combinations need no pregenerated files and nothing ever
   leaves the browser. The precomputed pages (prakriya.html, krdanta.html,
   dhatuforms.html) remain the fast, engine-free views of the common cases.

   Root arguments come from dhatu_wasm_index.json (aupadeshika + gana +
   antargana per Dhatupatha code); labels and search from the Dhatupatha
   the reader already knows; documented upasarga meanings from
   upasarga_artha.json.
   ========================================================================= */
(function () {
  'use strict';

  // Page-relative to dge/vyakarana/rupasiddhi.html (Phase 10: moved one
  // directory deeper than dge/ -- ../ reaches dge/data/).
  var DATA = '../data/vedanga/vyakarana/';
  // Captured now, during evaluation — document.currentScript is null later,
  // and the wasm paths must resolve relative to this file, not the page.
  var SELF = (document.currentScript && document.currentScript.src) || location.href;
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var esc = function (s) {
    return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  };

  /* ---- SLP1 -> Devanagari, self-contained (no CDN dependency) ---------- */
  var V = { a: '', A: 'ा', i: 'ि', I: 'ी', u: 'ु', U: 'ू', f: 'ृ', F: 'ॄ',
            x: 'ॢ', X: 'ॣ', e: 'े', E: 'ै', o: 'ो', O: 'ौ' };
  var VI = { a: 'अ', A: 'आ', i: 'इ', I: 'ई', u: 'उ', U: 'ऊ', f: 'ऋ', F: 'ॠ',
             x: 'ऌ', X: 'ॡ', e: 'ए', E: 'ऐ', o: 'ओ', O: 'औ' };
  var C = { k: 'क', K: 'ख', g: 'ग', G: 'घ', N: 'ङ', c: 'च', C: 'छ', j: 'ज',
            J: 'झ', Y: 'ञ', w: 'ट', W: 'ठ', q: 'ड', Q: 'ढ', R: 'ण', t: 'त',
            T: 'थ', d: 'द', D: 'ध', n: 'न', p: 'प', P: 'फ', b: 'ब', B: 'भ',
            m: 'म', y: 'य', r: 'र', l: 'ल', v: 'व', S: 'श', z: 'ष', s: 'स',
            h: 'ह' };
  var OTHER = { M: 'ं', H: 'ः', '~': 'ँ', "'": 'ऽ' };
  function deva(slp) {
    var out = '', i = 0, s = String(slp || '');
    while (i < s.length) {
      var ch = s[i];
      if (C[ch]) {
        var nx = s[i + 1];
        if (nx && V[nx] !== undefined) { out += C[ch] + V[nx]; i += 2; }
        else { out += C[ch] + '्'; i += 1; }
      } else if (VI[ch]) { out += VI[ch]; i += 1; }
      else if (OTHER[ch]) { out += OTHER[ch]; i += 1; }
      else if (ch === '\\' || ch === '^') { i += 1; /* accents: not rendered */ }
      else { out += ch; i += 1; }
    }
    return out;
  }

  /* ---- vocabulary ------------------------------------------------------ */
  var UPASARGAS = [
    ['प्र', 'pra'], ['परा', 'parA'], ['अप', 'apa'], ['सम्', 'sam'],
    ['अनु', 'anu'], ['अव', 'ava'], ['निस्', 'nis'], ['निर्', 'nir'],
    ['दुस्', 'dus'], ['दुर्', 'dur'], ['वि', 'vi'], ['आ', 'AN'],
    ['नि', 'ni'], ['अधि', 'aDi'], ['अपि', 'api'], ['अति', 'ati'],
    ['सु', 'su'], ['उत्', 'ud'], ['अभि', 'aBi'], ['प्रति', 'prati'],
    ['परि', 'pari'], ['उप', 'upa']
  ];
  var SLP_TO_DEVA_UPA = {};
  UPASARGAS.forEach(function (u) { SLP_TO_DEVA_UPA[u[1]] = u[0]; });

  var SANADI_MODES = [
    ['शुद्धः', []],
    ['णिजन्तः (causative)', ['Ric']],
    ['सन्नन्तः (desiderative)', ['san']],
    ['यङन्तः (intensive)', ['yaN']],
    ['यङ्लुगन्तः', ['yaNluk']],
    ['सन्नन्तात् णिच्', ['san', 'Ric']],
    ['णिजन्तात् सन्', ['Ric', 'san']]
  ];
  var LAKARAS = [
    ['Lat', 'लट्', 'present'], ['Lit', 'लिट्', 'perfect'],
    ['Lut', 'लुट्', 'periphrastic future'], ['Lrt', 'लृट्', 'future'],
    ['Let', 'लेट्', 'Vedic subjunctive'], ['Lot', 'लोट्', 'imperative'],
    ['Lan', 'लङ्', 'imperfect'], ['VidhiLin', 'विधिलिङ्', 'optative'],
    ['AshirLin', 'आशीर्लिङ्', 'benedictive'], ['Lun', 'लुङ्', 'aorist'],
    ['Lrn', 'लृङ्', 'conditional']
  ];
  var PURUSHA = ['Prathama', 'Madhyama', 'Uttama'];
  var PURUSHA_D = ['प्रथमः', 'मध्यमः', 'उत्तमः'];
  var VACANA = ['Eka', 'Dvi', 'Bahu'];
  var VACANA_D = ['एकवचनम्', 'द्विवचनम्', 'बहुवचनम्'];
  var VIBHAKTI = ['Prathama', 'Dvitiya', 'Trtiya', 'Caturthi', 'Panchami',
                  'Sasthi', 'Saptami', 'Sambodhana'];
  var VIBHAKTI_D = ['प्रथमा', 'द्वितीया', 'तृतीया', 'चतुर्थी', 'पञ्चमी',
                    'षष्ठी', 'सप्तमी', 'सम्बोधनम्'];
  var LINGA = [['Pum', 'पुंलिङ्गम्'], ['Stri', 'स्त्रीलिङ्गम्'], ['Napumsaka', 'नपुंसकलिङ्गम्']];

  // Curated kridanta inventory in traditional groups. `avy` marks avyaya
  // (indeclinable) pratyayas; `la` marks participles that need a lakara.
  var KRT_GROUPS = [
    ['कृत्याः', [
      ['tavyat', 'तव्यत्'], ['tavya', 'तव्य'], ['anIyar', 'अनीयर्'],
      ['yat', 'यत्'], ['Ryat', 'ण्यत्'], ['kyap', 'क्यप्']]],
    ['निष्ठा', [['kta', 'क्त'], ['ktavatu', 'क्तवतु']]],
    ['सत्-प्रत्ययौ', [
      ['Satf', 'शतृ', { la: 1 }], ['SAnac', 'शानच्', { la: 1 }],
      ['kvasu', 'क्वसु'], ['kAnac', 'कानच्']]],
    ['अव्ययानि', [
      ['ktvA', 'क्त्वा (सोपसर्गे ल्यप्)', { avy: 1 }],
      ['tumun', 'तुमुन्', { avy: 1 }], ['Ramul', 'णमुल्', { avy: 1 }]]],
    ['भावादौ', [
      ['GaY', 'घञ्'], ['ap', 'अप्'], ['ktin', 'क्तिन्'], ['a', 'अ'],
      ['yuc', 'युच्'], ['lyuw', 'ल्युट्'], ['ktri', 'क्त्रि']]],
    ['कर्तरि', [
      ['Rvul', 'ण्वुल्'], ['tfc', 'तृच्'], ['ac', 'अच्'], ['ka', 'क'],
      ['Sa', 'श'], ['tfn', 'तृन्'], ['GinuR', 'घिनुण्'], ['kvip', 'क्विप्']]],
    ['खलादौ', [['Kal', 'खल्'], ['KaS', 'खश्']]]
  ];

  /* ---- state ----------------------------------------------------------- */
  var state = {
    roots: [],            // dhatupatha items (labels/search)
    byCode: {},
    wasmArgs: {},         // code -> [aupadeshika, gana, antargana?]
    upaArtha: {},         // code -> [[upasarga, hindi meaning], ...]
    code: null,
    prefixes: [],         // SLP1 strings
    sanadi: 0,            // index into SANADI_MODES
    prayoga: 'Kartari',
    lakara: 'Lat',
    vidyut: null,         // engine instance once ready
    enginePromise: null
  };

  /* ---- engine ---------------------------------------------------------- */
  function engine() {
    if (state.enginePromise) return state.enginePromise;
    state.enginePromise = import(new URL('../wasm/vidyut/vidyut_prakriya.js', SELF).href)
      .then(function (mod) {
        return mod.default(new URL('../wasm/vidyut/vidyut_prakriya_bg.wasm', SELF).href)
          .then(function () { state.vidyut = mod.Vidyut.init(); return state.vidyut; });
      });
    return state.enginePromise;
  }
  function dhatuArgs() {
    var wa = state.wasmArgs[state.code];
    if (!wa) return null;
    return {
      aupadeshika: wa[0], gana: wa[1], antargana: wa[2] || null,
      sanadi: SANADI_MODES[state.sanadi][1], prefixes: state.prefixes
    };
  }
  function deriveTin(purusha, vacana) {
    var d = dhatuArgs();
    if (!d || !state.vidyut) return [];
    try {
      return state.vidyut.deriveTinantas({
        dhatu: d, lakara: state.lakara, prayoga: state.prayoga,
        purusha: purusha, vacana: vacana, skip_at_agama: false, pada: null
      }) || [];
    } catch (e) { return []; }
  }
  function deriveKrt(krt, la) {
    var d = dhatuArgs();
    if (!d || !state.vidyut) return [];
    try {
      return state.vidyut.deriveKrdantas({
        dhatu: d, krt: krt, unadi: null,
        lakara: la || null, prayoga: la ? state.prayoga : null
      }) || [];
    } catch (e) { return []; }
  }
  function deriveSub(krt, la, linga, vibhakti, vacana) {
    var d = dhatuArgs();
    if (!d || !state.vidyut) return [];
    try {
      return state.vidyut.deriveSubantas({
        pratipadika: { basic: null, nyap: null, taddhitanta: null,
                       krdanta: { dhatu: d, krt: krt, unadi: null,
                                  lakara: la || null, prayoga: la ? state.prayoga : null } },
        linga: linga, vibhakti: vibhakti, vacana: vacana
      }) || [];
    } catch (e) { return []; }
  }

  /* ---- derivation steps rendering -------------------------------------- */
  var RULE_SRC = { ashtadhyayi: '', varttika: 'वा॰', dhatupatha: 'धा॰',
                   kashika: 'का॰', linganushasanam: 'लिङ्गा॰', kaumudi: 'कौ॰',
                   unadi: 'उ॰', phit: 'फि॰', anyatra: '' };
  function stepsHtml(history) {
    var rows = history.map(function (st) {
      var code = st.rule.code, src = st.rule.source;
      var isSutra = src === 'ashtadhyayi' && /^\d\.\d\.\d{1,3}$/.test(code);
      var codeHtml = isSutra
        ? '<span class="dge-sutra-ref rs-code" data-sutra="' + esc(code) + '" role="button" tabindex="0">' + esc(code) + '</span>'
        : '<span class="rs-code rs-code-plain">' + esc((RULE_SRC[src] || src) + ' ' + code) + '</span>';
      var terms = st.result.filter(function (t) { return t.text; })
        .map(function (t) {
          return '<span class="' + (t.wasChanged ? 'rs-t-chg' : 'rs-t') + ' deva">' + esc(deva(t.text)) + '</span>';
        }).join('<span class="rs-plus">+</span>');
      return '<li>' + codeHtml + '<span class="rs-terms">' + terms + '</span></li>';
    }).join('');
    return '<ol class="rs-steps">' + rows + '</ol>';
  }
  function openDrawer(title, sub, prakriyas) {
    var body = prakriyas.map(function (p, i) {
      return (prakriyas.length > 1 ? '<h4 class="deva rs-alt">' + esc(deva(p.text)) + '</h4>' : '') +
        stepsHtml(p.history);
    }).join('');
    $('#rs-drawerTitle').innerHTML = '<span class="deva">' + esc(title) + '</span>' +
      (sub ? '<small>' + esc(sub) + '</small>' : '');
    $('#rs-drawerBody').innerHTML = body ||
      '<p class="rs-note">No derivation — this combination is not grammatically derivable.</p>';
    $('#rs-drawer').classList.add('open');
    $('#rs-backdrop').classList.add('open');
    if (typeof window.dgeScanForEntities === 'function') {
      try { window.dgeScanForEntities($('#rs-drawerBody')); } catch (e) {}
    }
    if (typeof window.dgeScanForSutras === 'function') {
      try { window.dgeScanForSutras($('#rs-drawerBody')); } catch (e) {}
    }
  }
  function closeDrawer() {
    $('#rs-drawer').classList.remove('open');
    $('#rs-backdrop').classList.remove('open');
  }

  /* ---- UI: header / picker --------------------------------------------- */
  function rootLabel(it) {
    return it ? it.dhatu + ' · ' + (it.artha || '') + ' (' + it.id + ')' : '';
  }
  function headerHtml() {
    var it = state.byCode[state.code];
    return '<div class="hero rs-hero">' +
      '<h1 class="deva">' + esc(it ? it.dhatu : 'रूपसिद्धिः') + '</h1>' +
      (it ? '<div class="sub"><span class="deva">' + esc(it.artha || '') + '</span>' +
        ' · गणः ' + esc(it.gana) + ' · <span class="deva">' + esc(it.pada || '') + '</span>' +
        ' · <code>' + esc(it.id) + '</code></div>' : '') +
      '<div class="rs-pick"><input id="rs-search" list="rs-roots" placeholder="धातुं मृग्यताम् — भू, कृ, गम्…" autocomplete="off">' +
      '<datalist id="rs-roots"></datalist></div>' +
      (it ? '<div class="pk-actions">' +
        '<a class="chip" href="dhatu.html#' + esc(it.id) + '">← धातुपाठः</a>' +
        '<a class="chip" href="prakriya.html#' + esc(it.id) + '">प्रक्रिया</a>' +
        '<a class="chip" href="krdanta.html#' + esc(it.id) + '">कृदन्त</a>' +
        '<a class="chip" href="dhatuforms.html#' + esc(it.id) + '">रूपाणि</a>' +
      '</div>' : '') +
      '</div>';
  }

  /* ---- UI: builder ------------------------------------------------------ */
  function upaOptions(sel) {
    var h = '<option value="">—</option>';
    UPASARGAS.forEach(function (u) {
      h += '<option value="' + u[1] + '"' + (sel === u[1] ? ' selected' : '') + '>' + u[0] + '</option>';
    });
    return h;
  }
  function builderHtml() {
    var it = state.byCode[state.code];
    var slots = state.prefixes.map(function (p, i) {
      return '<select class="rs-upa" data-slot="' + i + '">' + upaOptions(p) + '</select>' +
        '<span class="rs-plus2">+</span>';
    }).join('');
    var combo = state.prefixes.map(function (p) { return SLP_TO_DEVA_UPA[p] || p; }).join(' + ');
    return '<section class="rs-box">' +
      '<div class="rs-boxhead deva">उपसर्गयोजना <small>· stack any upasargas, in order</small></div>' +
      '<div class="rs-builder">' + slots +
      '<select class="rs-upa" data-slot="new">' + upaOptions('') + '</select>' +
      '<span class="rs-plus2">+</span>' +
      '<span class="rs-root deva">' + esc(it ? it.dhatu : '—') + '</span>' +
      (state.prefixes.length ? '<button class="rs-clear" id="rs-clearUpa" title="remove all upasargas">✕</button>' : '') +
      '</div>' +
      (combo ? '<div class="rs-combo deva">' + esc(combo + ' + ' + (it ? it.dhatu : '')) + '</div>' : '') +
      '</section>';
  }
  function modesHtml() {
    var san = SANADI_MODES.map(function (m, i) {
      return '<button class="chip' + (i === state.sanadi ? ' on' : '') + '" data-sanadi="' + i + '"><span class="deva">' + esc(m[0]) + '</span></button>';
    }).join('');
    return '<section class="rs-box">' +
      '<div class="rs-modes">' +
      '<div class="rs-modegrp"><span class="rs-lab deva">प्रयोगः</span>' +
      '<button class="chip' + (state.prayoga === 'Kartari' ? ' on' : '') + '" data-prayoga="Kartari"><span class="deva">कर्तरि</span></button>' +
      '<button class="chip' + (state.prayoga === 'Karmani' ? ' on' : '') + '" data-prayoga="Karmani"><span class="deva">कर्मणि / भावे</span></button>' +
      '</div>' +
      '<div class="rs-modegrp"><span class="rs-lab deva">सनादिः</span>' + san + '</div>' +
      '</div></section>';
  }
  function lakaraHtml() {
    return '<div class="rs-lak">' + LAKARAS.map(function (l) {
      return '<button class="chip' + (l[0] === state.lakara ? ' on' : '') + '" data-lak="' + l[0] + '" title="' + esc(l[2]) + '"><span class="deva">' + esc(l[1]) + '</span></button>';
    }).join('') + '</div>';
  }

  /* ---- UI: paradigm table ---------------------------------------------- */
  function tableHtml() {
    var h = '<table class="pk-grid rs-grid"><thead><tr><th></th>' +
      VACANA_D.map(function (v) { return '<th class="deva">' + v + '</th>'; }).join('') +
      '</tr></thead><tbody>';
    for (var p = 0; p < 3; p++) {
      h += '<tr><th class="deva pk-pur">' + PURUSHA_D[p] + '</th>';
      for (var v = 0; v < 3; v++) {
        h += '<td><button class="rs-cell deva" data-p="' + p + '" data-v="' + v + '">…</button></td>';
      }
      h += '</tr>';
    }
    return h + '</tbody></table>';
  }
  function fillTable() {
    var cells = document.querySelectorAll('.rs-cell');
    cells.forEach(function (c) { c.textContent = '…'; c._pr = null; });
    engine().then(function () {
      for (var p = 0; p < 3; p++) {
        for (var v = 0; v < 3; v++) {
          var prs = deriveTin(PURUSHA[p], VACANA[v]);
          var cell = document.querySelector('.rs-cell[data-p="' + p + '"][data-v="' + v + '"]');
          if (!cell) continue;
          cell._pr = prs;
          cell.textContent = prs.length
            ? prs.map(function (x) { return deva(x.text); }).join(' / ')
            : '—';
          cell.disabled = !prs.length;
        }
      }
    }).catch(function (e) {
      var st = $('#rs-status');
      if (st) st.textContent = 'engine failed to load: ' + e;
    });
  }

  /* ---- UI: kridanta section --------------------------------------------- */
  function krtHtml() {
    var h = '<section class="rs-box"><div class="rs-boxhead deva">कृदन्ताः ' +
      '<small>· tap a form for its derivation · ▦ for declensions</small></div>';
    KRT_GROUPS.forEach(function (g) {
      h += '<div class="rs-krtgrp"><span class="rs-lab deva">' + esc(g[0]) + '</span><div class="rs-krtrow">';
      g[1].forEach(function (k) {
        h += '<span class="rs-krt" data-krt="' + k[0] + '"' + (k[2] && k[2].la ? ' data-la="1"' : '') +
          (k[2] && k[2].avy ? ' data-avy="1"' : '') + '>' +
          '<button class="rs-krtform deva" data-act="steps">…</button>' +
          '<span class="rs-krtname deva">' + esc(k[1]) + '</span>' +
          '<button class="rs-krtdecl" data-act="decl" title="declension in all three lingas">▦</button>' +
          '</span>';
      });
      h += '</div></div>';
    });
    return h + '<div id="rs-declPanel"></div></section>';
  }
  function fillKrts() {
    engine().then(function () {
      document.querySelectorAll('.rs-krt').forEach(function (el) {
        var prs = deriveKrt(el.dataset.krt, el.dataset.la ? 'Lat' : null);
        el._pr = prs;
        var b = el.querySelector('.rs-krtform');
        // dedupe optional forms for the compact chip; the drawer shows all
        var texts = [];
        prs.forEach(function (x) { var t = deva(x.text); if (texts.indexOf(t) === -1) texts.push(t); });
        b.textContent = texts.length ? texts.slice(0, 2).join(' / ') + (texts.length > 2 ? '…' : '') : '—';
        if (!prs.length) el.classList.add('rs-krtnone');
        else el.classList.remove('rs-krtnone');
        var d = el.querySelector('.rs-krtdecl');
        d.style.display = (el.dataset.avy || !prs.length) ? 'none' : '';
      });
    });
  }
  function declHtml(krt, la) {
    var h = '';
    LINGA.forEach(function (lg) {
      h += '<h4 class="deva rs-declh">' + lg[1] + '</h4>' +
        '<div class="df-table"><table><thead><tr><th></th>' +
        VACANA_D.map(function (v) { return '<th class="deva">' + v + '</th>'; }).join('') +
        '</tr></thead><tbody>';
      VIBHAKTI.forEach(function (vb, vi) {
        h += '<tr><th class="deva">' + VIBHAKTI_D[vi] + '</th>';
        VACANA.forEach(function (vc) {
          var prs = deriveSub(krt, la, lg[0], vb, vc);
          var texts = [];
          prs.forEach(function (x) { var t = deva(x.text); if (texts.indexOf(t) === -1) texts.push(t); });
          h += '<td class="deva">' + esc(texts.join(', ') || '—') + '</td>';
        });
        h += '</tr>';
      });
      h += '</tbody></table></div>';
    });
    return h;
  }

  /* ---- UI: documented upasarga meanings --------------------------------- */
  function upaArthaHtml() {
    var list = state.upaArtha[state.code];
    if (!list || !list.length) return '';
    var rows = list.map(function (u) {
      return '<button class="rs-uparow" data-upa="' + esc(u[0]) + '">' +
        '<span class="deva rs-upaname">' + esc(u[0]) + ' + ' + esc((state.byCode[state.code] || {}).dhatu || '') + '</span>' +
        '<span class="rs-upahi">' + esc(u[1]) + '</span></button>';
    }).join('');
    return '<section class="rs-box"><div class="rs-boxhead deva">उपसर्गार्थाः ' +
      '<small>· documented meanings (Hindi) — tap to set the builder</small></div>' +
      '<div class="rs-upalist">' + rows + '</div></section>';
  }

  /* ---- render ----------------------------------------------------------- */
  function render() {
    var root = $('#root');
    if (!state.code) {
      root.innerHTML = headerHtml() +
        '<p class="rs-note">धातुपाठात् एकं धातुं चिनुत — type a root above, or open this page from a root in the <a href="dhatu.html">Dhātupāṭha</a>.</p>';
      wireSearch();
      return;
    }
    root.innerHTML = headerHtml() + builderHtml() + modesHtml() +
      '<section class="rs-box"><div class="rs-boxhead deva">तिङन्तरूपाणि <span id="rs-status" class="rs-status"></span></div>' +
      lakaraHtml() + tableHtml() + '</section>' +
      krtHtml() + upaArthaHtml() +
      '<p class="df-note">रूपसिद्धिः — व्युत्पत्तिः अस्मिन्नेव यन्त्रे क्रियते (vidyut-prakriya, Apache-2.0, Ambuda) · ' +
      'उपसर्गार्थाः · ' +
      'a derived form is the grammar\'s output, not an attested citation — for attested usage see the corpus search.</p>';
    wireSearch();
    fillTable();
    fillKrts();
  }

  function wireSearch() {
    var inp = $('#rs-search'), dl = $('#rs-roots');
    if (!inp || !dl) return;
    if (!dl.childElementCount) {
      dl.innerHTML = state.roots.map(function (it) {
        return '<option value="' + esc(rootLabel(it)) + '">';
      }).join('');
    }
    inp.addEventListener('change', function () {
      var v = inp.value.trim();
      var m = v.match(/\((\d{2}\.\d{4})\)\s*$/);
      var hit = m ? state.byCode[m[1]] : null;
      if (!hit) {
        var dv = v.replace(/\s.*$/, '');
        hit = state.roots.find(function (it) { return it.dhatu === dv || it.id === v; });
      }
      if (hit) { location.hash = '#' + hit.id; }
    });
  }

  /* ---- events ----------------------------------------------------------- */
  document.addEventListener('click', function (ev) {
    var t = ev.target;
    var chip = t.closest('[data-sanadi],[data-prayoga],[data-lak]');
    if (chip) {
      if (chip.dataset.sanadi !== undefined) state.sanadi = +chip.dataset.sanadi;
      if (chip.dataset.prayoga) state.prayoga = chip.dataset.prayoga;
      if (chip.dataset.lak) state.lakara = chip.dataset.lak;
      render();
      return;
    }
    if (t.id === 'rs-clearUpa') { state.prefixes = []; render(); return; }
    var cell = t.closest('.rs-cell');
    if (cell && cell._pr && cell._pr.length) {
      var it = state.byCode[state.code];
      var lak = LAKARAS.find(function (l) { return l[0] === state.lakara; });
      openDrawer(cell._pr.map(function (x) { return deva(x.text); }).join(' / '),
        (it ? it.dhatu + ' · ' : '') + lak[1] + ' · ' + PURUSHA_D[+cell.dataset.p] + ' · ' + VACANA_D[+cell.dataset.v],
        cell._pr);
      return;
    }
    var krtEl = t.closest('.rs-krt');
    if (krtEl && t.closest('[data-act="steps"]') && krtEl._pr && krtEl._pr.length) {
      openDrawer(krtEl._pr.map(function (x) { return deva(x.text); }).filter(function (x, i, a) { return a.indexOf(x) === i; }).join(' / '),
        krtEl.querySelector('.rs-krtname').textContent,
        krtEl._pr);
      return;
    }
    if (krtEl && t.closest('[data-act="decl"]')) {
      var panel = $('#rs-declPanel');
      var krt = krtEl.dataset.krt;
      if (panel.dataset.open === krt) { panel.innerHTML = ''; panel.dataset.open = ''; return; }
      panel.dataset.open = krt;
      panel.innerHTML = '<p class="rs-note">deriving declensions…</p>';
      setTimeout(function () {
        panel.innerHTML = '<div class="rs-declhead deva">' +
          esc(krtEl.querySelector('.rs-krtname').textContent) + ' — सुबन्तरूपाणि' +
          '</div>' + declHtml(krt, krtEl.dataset.la ? 'Lat' : null);
        panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }, 30);
      return;
    }
    var upaRow = t.closest('.rs-uparow');
    if (upaRow) {
      var parts = upaRow.dataset.upa.split('+').map(function (x) { return x.trim(); });
      var slp = [];
      parts.forEach(function (p) {
        var f = UPASARGAS.find(function (u) { return u[0] === p; });
        if (f) slp.push(f[1]);
      });
      if (slp.length) { state.prefixes = slp; render(); window.scrollTo({ top: 0, behavior: 'smooth' }); }
      return;
    }
    if (t.id === 'rs-drawerClose' || t.id === 'rs-backdrop') closeDrawer();
  });
  document.addEventListener('change', function (ev) {
    var sel = ev.target.closest('.rs-upa');
    if (!sel) return;
    var slot = sel.dataset.slot;
    if (slot === 'new') { if (sel.value) state.prefixes.push(sel.value); }
    else {
      if (sel.value) state.prefixes[+slot] = sel.value;
      else state.prefixes.splice(+slot, 1);
    }
    render();
  });

  /* ---- boot ------------------------------------------------------------- */
  function applyHash() {
    var h = decodeURIComponent((location.hash || '').replace(/^#/, '').trim());
    var m = h.match(/^(\d{2}\.\d{4})$/);
    state.code = m ? m[1] : null;
    render();
  }
  function boot() {
    var themeBtn = $('#themeBtn');
    if (localStorage.getItem('dge_vyakarana_dark') === '1') document.body.classList.add('dark');
    if (themeBtn) themeBtn.addEventListener('click', function () {
      var dark = document.body.classList.toggle('dark');
      localStorage.setItem('dge_vyakarana_dark', dark ? '1' : '0');
    });
    // drawer skeleton lives outside #root so render() never clobbers it
    var dw = document.createElement('div');
    dw.innerHTML = '<div class="rs-backdrop" id="rs-backdrop"></div>' +
      '<div class="rs-drawer" id="rs-drawer"><div class="rs-drawerin">' +
      '<button class="rs-x" id="rs-drawerClose">×</button>' +
      '<h3 id="rs-drawerTitle"></h3><div id="rs-drawerBody"></div></div></div>';
    while (dw.firstChild) document.body.appendChild(dw.firstChild);

    Promise.all([
      fetch(DATA + 'dhatupatha/data.json').then(function (r) { return r.json(); }),
      fetch(DATA + 'dhatu_wasm_index.json').then(function (r) { return r.json(); }),
      fetch(DATA + 'upasarga_artha.json').then(function (r) { return r.ok ? r.json() : { items: {} }; })
        .catch(function () { return { items: {} }; })
    ]).then(function (res) {
      state.roots = res[0].items || [];
      state.roots.forEach(function (it) { state.byCode[it.id] = it; });
      state.wasmArgs = res[1].items || {};
      state.upaArtha = res[2].items || {};
      applyHash();
      engine(); // warm up in the background
    }).catch(function (e) {
      $('#root').innerHTML = '<p class="rs-note">could not load data (' + esc(e) + ') — serve from the dge/ folder.</p>';
    });
    window.addEventListener('hashchange', applyHash);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
