/* =========================================================================
   The derivation viewer — प्रक्रिया · तिङन्त and कृदन्त forms.

   dhatu.html has always carried two buttons per root pointing here and at
   krdanta.html, and both pages were missing, so both 404'd. This is what they
   were meant to be: the whole tiṅanta paradigm for a root, and for the lakāras
   a student meets first, the step-by-step derivation of each form — every step
   naming the Aṣṭādhyāyī rule that fired, and every one of those tappable,
   because intellisense.js resolves exactly those ids.

   Data is per root, built ahead of time by tools/build_prakriya.py from
   Vidyut. One root is ~29 KB and nothing else is fetched.

   Both pages run from this file; which one is decided by document.body's
   data-view, so the paradigm and the kṛdanta list share their loading, their
   error handling and their step rendering rather than diverging.
   ========================================================================= */
(function () {
  'use strict';

  const self = (document.currentScript && document.currentScript.src) || '';
  function dataUrl(rel) {
    try { return new URL('../data/vedanga/vyakarana/prakriya/' + rel, self).href; }
    catch (e) { return 'data/vedanga/vyakarana/prakriya/' + rel; }
  }

  const esc = (s) => String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');

  const LAKARA = {
    Lat: 'लट्', Lit: 'लिट्', Lut: 'लुट्', Lrt: 'लृट्',
    Lot: 'लोट्', Lan: 'लङ्', VidhiLin: 'विधिलिङ्', Lun: 'लुङ्'
  };
  const LAKARA_EN = {
    Lat: 'present', Lit: 'perfect', Lut: 'periphrastic future', Lrt: 'future',
    Lot: 'imperative', Lan: 'imperfect', VidhiLin: 'optative', Lun: 'aorist'
  };
  const PURUSHA = ['प्रथमपुरुषः', 'मध्यमपुरुषः', 'उत्तमपुरुषः'];
  const VACANA = ['एकवचनम्', 'द्विवचनम्', 'बहुवचनम्'];
  const KRT = {
    kta: 'क्त', ktavatu: 'क्तवतु', ktvA: 'क्त्वा', tumun: 'तुमुन्',
    Satf: 'शतृ', SAnac: 'शानच्', tavya: 'तव्य', anIyar: 'अनीयर्',
    yat: 'यत्', Rvul: 'ण्वुल्', tfc: 'तृच्', lyuw: 'ल्युट्'
  };
  const KRT_EN = {
    kta: 'past passive participle', ktavatu: 'past active participle',
    ktvA: 'absolutive', tumun: 'infinitive', Satf: 'present participle, parasmaipada',
    SAnac: 'present participle, ātmanepada', tavya: 'gerundive', anIyar: 'gerundive',
    yat: 'gerundive', Rvul: 'agent noun', tfc: 'agent noun', lyuw: 'action noun'
  };

  /* Steps are delta-encoded — a rule that changes nothing stores only its code
     (see steps_of in tools/build_prakriya.py). Carry the last result forward so
     every step shows the state of the derivation at that point.

     A rule that only assigns a designation (an इत्संज्ञा, say) is a real step
     of the derivation but never changes the visible string — carrying the
     result forward means it renders identically to the step before it,
     which read as a UI bug ("the sutra changed but the form didn't") rather
     than as what it actually is. Marked (not hidden) here; the Main/All
     toggle below decides whether the reader sees it by default. */
  function stepsHtml(steps) {
    let last = '';
    const items = steps.map(function (st) {
      const code = st[0];
      const changed = st.length > 1;
      if (changed) last = st[1];
      // A sutra code is what intellisense.js already knows how to open; an
      // ordinary rule reference (a paribhasha, a vartika) is shown plainly.
      const isSutra = /^[1-8]\.[1-4]\.\d{1,3}$/.test(code);
      return '<li class="' + (changed ? 'pk-step-changed' : 'pk-step-same') + '">' +
        (isSutra
          ? '<span class="dge-sutra-ref pk-code" data-sutra="' + esc(code) + '" role="button" tabindex="0">' + esc(code) + '</span>'
          : '<span class="pk-code pk-code-plain">' + esc(code) + '</span>') +
        '<span class="pk-result deva">' + esc(last) + '</span>' +
        (changed ? '' : '<span class="pk-step-note">no visible change — this rule marks the form for a later step</span>') +
        '</li>';
    }).join('');
    const anySame = steps.some(st => st.length <= 1);
    return '<div class="pk-steps-block">' +
      (anySame ? '<label class="pk-steps-toggle"><input type="checkbox" class="pk-all-steps"> Show every step, including ones with no visible change</label>' : '') +
      '<ol class="pk-steps pk-main-only">' + items + '</ol></div>';
  }

  // Which lakaras carry derivations is the build's decision, not this page's —
  // read it from the manifest rather than restating it here, so widening the
  // build with --lakaras needs no edit to the reader.
  let stepped_names = null;
  function steppedNames() {
    return stepped_names || ['लट्', 'लोट्'];
  }

  // 7 Sep 2026: corpus occurrences of every form (tools/build_dhatu_prayoga_index.py →
  // data/vedanga/vyakarana/dhatu_prayoga/by_dhatu/<gana>/<code>.json). A count
  // badge on each cell, and example snippets — linked into the reader — under
  // the derivation panel when a cell is opened.
  let USAGE = null;
  function usageUrl(code) {
    try { return new URL('../data/vedanga/vyakarana/dhatu_prayoga/by_dhatu/' + code.split('.')[0] + '/' + code + '.json', self).href; }
    catch (e) { return ''; }
  }
  function loadUsage(code) {
    USAGE = null;
    return fetch(usageUrl(code), { cache: 'force-cache' }).then(r => (r.ok ? r.json() : null)).then(u => { USAGE = u; return u; }).catch(() => null);
  }
  // n = occurrences of a form only this root can write. sn = occurrences of a
  // form several roots can, counted in full against each of them (10 Sep 2026).
  // The two are never added: the same कृत्वा is in the sn of both 05.0007 and
  // 08.0010, and adding them is exactly the arithmetic that reported 29,938
  // "having done"s as a root meaning "to injure".
  function usageBadge(key) {
    const f = USAGE && USAGE.forms && USAGE.forms[key];
    if (!f) return '';
    const sn = f.sn || 0;
    const t = f.n.toLocaleString() + ' occurrences in the library' +
      (sn ? ' — and ' + sn.toLocaleString() + ' more of a spelling another root also writes, which cannot be attributed either way' : '');
    return '<span class="pk-usage' + (!f.n && sn ? ' pk-usage-shared' : '') + '" title="' + t + '">' +
      f.n.toLocaleString() + '×' + (sn ? '<sup>~' + sn.toLocaleString() + '</sup>' : '') + '</span>';
  }
  function readerLink(slug, unit, word) {
    let u = '../index.html?path=' + encodeURIComponent(slug);
    const m = String(unit || '').match(/(?:^|#)(\d+)$/);
    if (m) u += '&jumpShloka=' + m[1]; else if (unit) u += '&jumpVedicId=' + encodeURIComponent(unit);
    if (word) u += '&hl=' + encodeURIComponent(word);
    return u;
  }
  function examplesHtml(key, label) {
    const f = USAGE && USAGE.forms && USAGE.forms[key];
    if (!f) return '<p class="pk-note">No occurrence of this form found in the library (exact, word-bounded matches only — sandhi-joined uses are not counted).</p>';
    const ex = f.e || [];
    const sn = f.sn || 0;
    const shareNote = sn
      ? ' · <em>' + sn.toLocaleString() + ' further occurrence' + (sn === 1 ? '' : 's') +
        ' of this spelling belong to this root OR to another that writes it identically — they are not counted above, and the examples below marked so are among them</em>'
      : '';
    return '<div class="pk-usage-block"><h3 class="pk-h2 deva">प्रयोगाः <span class="pk-sub">' + esc(label || '') + ' · ' + f.n.toLocaleString() + ' in the library' +
      (ex.length < f.n ? ', first ' + ex.length + ' shown' : '') + shareNote + '</span></h3><ol class="pk-ex">' +
      ex.map(e => '<li><span class="deva pk-ex-snip">' + esc(e[3]).replace(esc(e[2]), '<mark>' + esc(e[2]) + '</mark>') + '</span> ' +
        '<a class="pk-ex-ref" href="' + readerLink(e[0], e[1], e[2]) + '" title="' + esc(e[0]) + '">' + esc(e[4] || e[0]) + (e[1] ? ' · ' + esc(e[1]) : '') + ' ↗</a></li>').join('') +
      '</ol></div>';
  }
  function usageSummaryHtml(view) {
    if (!USAGE) return '';
    const keys = Object.keys(USAGE.forms || {}).filter(k => view === 'krdanta' ? k.indexOf('krt:') === 0 : k.indexOf('krt:') !== 0);
    if (!keys.length) return '';
    const shown = keys.sort((a, b) => USAGE.forms[b].n - USAGE.forms[a].n).slice(0, 8);
    const shared = USAGE.shared || 0;
    return '<div class="pk-usage-sum"><b>धातुप्रयोगसूची</b> · ' + USAGE.total.toLocaleString() + ' occurrences of ' + USAGE.cells + ' forms in the library' +
      (shared ? ' <span class="muted">(+' + shared.toLocaleString() + ' on spellings shared with another root)</span>' : '') + ' · most used: ' +
      shown.map(k => '<span class="deva">' + esc((USAGE.forms[k].e[0] || [])[2] || k) + '</span> <span class="muted">' + USAGE.forms[k].n.toLocaleString() + '</span>').join(', ') + '</div>';
  }

  function paradigmHtml(d, lakara) {
    const stepped = Object.prototype.hasOwnProperty.call(d.steps, lakara + '.00');
    let h = '<table class="pk-grid"><thead><tr><th></th>' +
            VACANA.map(v => '<th class="deva">' + v + '</th>').join('') +
            '</tr></thead><tbody>';
    for (let p = 0; p < 3; p++) {
      h += '<tr><th class="deva pk-pur">' + PURUSHA[p] + '</th>';
      for (let v = 0; v < 3; v++) {
        const key = lakara + '.' + p + v;
        const forms = d.forms[key];
        if (!forms || !forms.length) { h += '<td class="pk-none">—</td>'; continue; }
        const text = forms.map(esc).join(' / ');
        const badge = usageBadge(key);
        h += stepped
          ? '<td><button class="pk-form deva" id="pk-cell-' + esc(key) + '" data-key="' + esc(key) + '">' + text + '</button>' + badge + '</td>'
          : '<td><button class="pk-form pk-form-flat deva" id="pk-cell-' + esc(key) + '" data-key="' + esc(key) + '">' + text + '</button>' + badge + '</td>';
      }
      h += '</tr>';
    }
    h += '</tbody></table>';
    if (!stepped) {
      // Build/storage tradeoffs (why only two lakāras get full derivations
      // yet) belong in tools/build_prakriya.py's comments, not here — a
      // reader isn't asking about the site's disk budget, and "116 MB"
      // read like an error rather than an explanation of what they're
      // looking at. Say only what is actually true from where they stand:
      // these forms are real and complete, the step-by-step view just
      // isn't built for this lakāra yet.
      h += '<p class="pk-note">' + esc(LAKARA[lakara]) +
           "'s forms above are complete. Step-by-step derivation is available for " +
           esc(steppedNames().join(', ')) + ' — tap a form there to see it worked out sūtra by sūtra.</p>';
    }
    return h;
  }

  function krtHtml(d) {
    if (!d.krt || !d.krt.length) return '<p class="pk-note">No kṛdanta forms derived for this root.</p>';
    return d.krt.map(function (k, i) {
      // The sutra that introduces the pratyaya is read off the derivation
      // itself — the first step whose result actually contains the
      // pratyaya's name (a participle's derivation passes through the
      // lakara rule first, so "first changed step" alone points one rule
      // early for शतृ/शानच्). Data-driven either way, never a
      // hand-maintained list.
      var intro = null, firstChanged = null;
      var kname = KRT[k.k] || '';
      for (var s = 1; s < (k.s || []).length; s++) {
        if (k.s[s].length <= 1) continue;
        if (!firstChanged) firstChanged = k.s[s][0];
        if (kname && k.s[s][1].indexOf(kname) !== -1) { intro = k.s[s][0]; break; }
      }
      intro = intro || firstChanged;
      var introHtml = (intro && /^[1-8]\.[1-4]\.\d{1,3}$/.test(intro))
        ? '<a class="pk-krt-sutra" href="ashtadhyayi.html#' + esc(intro) + '" ' +
          'title="the sutra that provides this pratyaya — open it in the Ashtadhyayi reader" ' +
          'onclick="event.stopPropagation()">ℹ️ ' + esc(intro) + '</a>'
        : '';
      return '<section class="pk-krt">' +
        '<button class="pk-krt-head" data-krt="' + i + '">' +
          '<span class="pk-form deva">' + esc(k.t) + '</span>' +
          '<span class="pk-krt-name deva">' + esc(KRT[k.k] || k.k) + '</span>' +
          '<span class="pk-krt-en">' + esc(KRT_EN[k.k] || '') + '</span>' +
          introHtml +
          '<span class="pk-arrow" aria-hidden="true">▾</span>' +
        '</button>' +
        '<div class="pk-krt-body" id="pk-krt-' + i + '" hidden></div>' +
      '</section>';
    }).join('');
  }

  function headerHtml(d) {
    return '<div class="hero">' +
      '<h1 class="deva">' + esc(d.dhatu) + '</h1>' +
      '<div class="sub"><span class="deva">' + esc(d.artha || '') + '</span>' +
      (d.gana ? ' · गणः ' + esc(d.gana) : '') +
      (d.pada ? ' · <span class="deva">' + esc(d.pada) + '</span>' : '') +
      ' · <code>' + esc(d.code) + '</code></div>' +
      '<div class="pk-actions">' +
        '<a class="chip" href="dhatu.html#' + esc(d.code) + '">← धातुपाठः</a>' +
        '<a class="chip" href="ashtadhyayi.html">↔ अष्टाध्यायी</a>' +
        (document.body.dataset.view === 'krdanta'
          ? '<a class="chip" href="prakriya.html#' + esc(d.code) + '">प्रक्रिया · तिङन्त</a>'
          : '<a class="chip" href="krdanta.html#' + esc(d.code) + '">कृदन्त forms</a>') +
        '<a class="chip" href="rupasiddhi.html#' + esc(d.code) + '" title="उपसर्ग-योजना, सनादि, सर्वे लकाराः — live derivation workbench">✨ रूपसिद्धिः</a>' +
      '</div></div>';
  }

  function render(d, wantKey) {
    const view = document.body.dataset.view === 'krdanta' ? 'krdanta' : 'tinanta';
    const root = document.getElementById('root');
    // Shared by both views below: the "show every step" toggle a stepsHtml()
    // block carries. Delegated on root (survives root.innerHTML being
    // replaced wholesale on every view/lakāra switch) rather than bound per
    // checkbox, which would need re-wiring after each redraw.
    root.addEventListener('change', function (ev) {
      if (!ev.target.classList.contains('pk-all-steps')) return;
      const ol = ev.target.closest('.pk-steps-block').querySelector('.pk-steps');
      if (ol) ol.classList.toggle('pk-main-only', !ev.target.checked);
    });
    if (view === 'krdanta') {
      root.innerHTML = headerHtml(d) + '<h2 class="pk-h2 deva">कृदन्तरूपाणि</h2>' + usageSummaryHtml('krdanta') + krtHtml(d);
      function openKrt(i) {
        const b = root.querySelector('[data-krt="' + i + '"]');
        const body = document.getElementById('pk-krt-' + i);
        if (!b || !body) return;
        if (body.hidden) { body.innerHTML = stepsHtml(d.krt[i].s) + examplesHtml('krt:' + d.krt[i].k, KRT[d.krt[i].k] || d.krt[i].k); body.hidden = false; }
        b.classList.add('open');
      }
      root.addEventListener('click', function (ev) {
        const b = ev.target.closest('[data-krt]');
        if (!b) return;
        const i = +b.getAttribute('data-krt');
        const body = document.getElementById('pk-krt-' + i);
        if (!body) return;
        if (body.hidden) { openKrt(i); }
        else { body.hidden = true; b.classList.remove('open'); }
      });
      // A deep link (from shabda.js's kṛt-form fallback, via
      // tools/build_krt_form_index.py's reverse index) names the exact
      // kṛt pratyaya to open — e.g. लभ्यः resolves to "yat".
      if (wantKey) {
        const i = d.krt.findIndex(function (k) { return k.k === wantKey; });
        if (i !== -1) {
          openKrt(i);
          const b = root.querySelector('[data-krt="' + i + '"]');
          b.classList.add('pk-deep-hl');
          b.scrollIntoView({ behavior: 'smooth', block: 'center' });
          setTimeout(function () { b.classList.remove('pk-deep-hl'); }, 2600);
        }
      }
      return;
    }

    // A deep link (from ai.js's Dhatu word-tool, via
    // tools/build_prakriya_form_index.py's reverse index) names the exact
    // cell to open — start on its lakara instead of लट्.
    let lakara = (wantKey && d.forms[wantKey] && d.forms[wantKey].length) ? wantKey.split('.')[0] : 'Lat';
    function draw() {
      root.innerHTML = headerHtml(d) +
        '<div class="pk-lak">' + Object.keys(LAKARA).map(function (l) {
          const has = Object.keys(d.forms).some(k => k.indexOf(l + '.') === 0);
          return '<button class="chip' + (l === lakara ? ' on' : '') +
                 (has ? '' : ' pk-empty') + '" data-lak="' + l + '"' +
                 (has ? '' : ' disabled') + ' title="' + esc(LAKARA_EN[l]) + '">' +
                 '<span class="deva">' + esc(LAKARA[l]) + '</span></button>';
        }).join('') + '</div>' +
        paradigmHtml(d, lakara) + usageSummaryHtml('tinanta') +
        '<div id="pk-deriv"></div>';
    }
    draw();

    // Shared by the click handler and the deep-link opener below, so a
    // programmatic open (a word-tool click landing here) shows exactly the
    // same derivation-panel state a manual tap would.
    function openFormCell(cell, key) {
      root.querySelectorAll('.pk-form').forEach(el => el.classList.remove('on'));
      cell.classList.add('on');
      const derivs = d.steps[key];
      const panel = document.getElementById('pk-deriv');
      if (!panel) return;
      const p = +key.split('.')[1][0], v = +key.split('.')[1][1];
      const label = LAKARA[lakara] + ' · ' + PURUSHA[p] + ' · ' + VACANA[v];
      const formText = (derivs ? derivs.map(x => x.t) : (d.forms[key] || [])).join(' / ');
      panel.innerHTML = '<h2 class="pk-h2 deva">' + esc(formText) +
        '</h2><div class="pk-sub deva">' + esc(label) + '</div>' +
        (derivs ? derivs.map(x => stepsHtml(x.s)).join('') : '') +
        examplesHtml(key, label);
    }

    root.addEventListener('click', function (ev) {
      const lak = ev.target.closest('[data-lak]');
      if (lak && !lak.disabled) { lakara = lak.getAttribute('data-lak'); draw(); return; }
      const form = ev.target.closest('[data-key]');
      if (!form) return;
      const key = form.getAttribute('data-key');
      openFormCell(form, key);
      document.getElementById('pk-deriv').scrollIntoView({ behavior: 'smooth', block: 'start' });
    });

    if (wantKey && d.forms[wantKey] && d.forms[wantKey].length) {
      const cell = document.getElementById('pk-cell-' + wantKey);
      if (cell) {
        cell.classList.add('pk-deep-hl');
        if (cell.tagName === 'BUTTON') openFormCell(cell, wantKey);
        cell.scrollIntoView({ behavior: 'smooth', block: 'center' });
        setTimeout(function () { cell.classList.remove('pk-deep-hl'); }, 2600);
      }
    }
  }

  function fail(msg) {
    document.getElementById('root').innerHTML =
      '<div class="hero"><h1>—</h1><div class="sub">' + esc(msg) + '</div>' +
      '<div class="pk-actions"><a class="chip" href="dhatu.html">← धातुपाठः</a></div></div>';
  }

  function load() {
    // A plain "#01.0008" opens the root at लट्, as always. A word-tool deep
    // link adds ":<key>" — "#02.0058:Lit.00" — naming the exact
    // lakāra.puruṣa.vacana cell to open and highlight (see ai.js's
    // dgeOpenDhatuForSelection/dgeFindDhatuFormHit, which also renders
    // this same cell inline in its own modal, and
    // tools/build_prakriya_form_index.py which builds the reverse index
    // both read from).
    const raw = (location.hash || '').replace(/^#/, '').trim();
    const sep = raw.indexOf(':');
    const code = sep === -1 ? raw : raw.slice(0, sep);
    const wantKey = sep === -1 ? null : raw.slice(sep + 1);
    if (!/^\d{2}\.\d{4}$/.test(code)) {
      fail('Open this from a root in the Dhātupāṭha — it needs a root code such as 01.0008.');
      return;
    }
    Promise.all([
      fetch(dataUrl(code.split('.')[0] + '/' + code + '.json'), { cache: 'force-cache' }).then(r => (r.ok ? r.json() : null)),
      loadUsage(code)
    ]).then(([d]) => d)
      .then(d => d ? render(d, wantKey)
                   : fail('No derivation has been generated for root ' + code + ' yet.'))
      .catch(() => fail('Could not load the derivation for root ' + code + '.'));
  }

  fetch(dataUrl('manifest.json'), { cache: 'force-cache' })
    .then(r => (r.ok ? r.json() : null))
    .then(function (m) {
      if (m && Array.isArray(m.lakarasWithSteps)) {
        stepped_names = m.lakarasWithSteps.map(l => LAKARA[l] || l);
      }
    })
    .catch(function () { /* the fallback in steppedNames() stands */ });

  window.addEventListener('hashchange', load);

  const themeBtn = document.getElementById('themeBtn');
  if (themeBtn) {
    // Same key dhatu.html uses, so the choice carries between the two.
    if (localStorage.getItem('dge_vyakarana_dark') === '1') document.body.classList.add('dark');
    themeBtn.addEventListener('click', function () {
      const dark = document.body.classList.toggle('dark');
      localStorage.setItem('dge_vyakarana_dark', dark ? '1' : '0');
    });
  }

  load();
})();
