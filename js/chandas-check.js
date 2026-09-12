/* chandas-check.js — per-shloka metre verification in the main reader.
   Adds a "छन्दः-परीक्षा" action to the shloka contextual menu (via
   dgeRegisterContextualActions) and renders the analysis as a collapsible
   panel directly under the shloka card:
     · metre identification against the 245-vrutta DB (DGEChandas —
       the SAME engine as vyakarana/chandas.html, zero API cost)
     · akshara-wise laghu (।) / guru (ऽ) scansion per pada
     · syllable + matra counts, gana formula, yati positions
     · deviations: unknown patterns list the nearest vruttas (≤2 differences)
       — the standard signal of a metrical break or text corruption
     · "AI cross-check" hands the verse to the existing Ask-Acharya flow
       (BYOK — the reader's own configured key; nothing billed to the site)
   Load order: after chandas.js (the engine) and contextual-actions.js. */
(function () {
  'use strict';
  window.DGE_VERSIONS = window.DGE_VERSIONS || {};
  window.DGE_VERSIONS['chandas-check.js'] =
    'v1.0 (shloka contextual action → inline scansion panel via DGEChandas; nearest-vrutta deviation hints; BYOK AI cross-check)';

  var esc = function (s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
      return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c];
    });
  };

  function shlokaText(id) {
    try {
      var d = window.stotraData;
      if (d && d.shlokas && d.shlokas[id] && d.shlokas[id].sa) return d.shlokas[id].sa;
    } catch (e) {}
    var card = document.getElementById('shloka-' + id);
    var t = card && card.querySelector('.shloka-text, .sanskrit-text, .shloka-sa');
    return t ? t.innerText : (card ? card.innerText : '');
  }

  function padaHtml(p, yati) {
    var yset = {};
    (yati || []).reduce(function (acc, y) { yset[acc + y] = true; return acc + y; }, 0);
    var syl = '', mark = '';
    p.sylls.forEach(function (s, i) {
      var y = yset[i + 1] ? ' chk-yati' : '';
      syl += '<span class="chk-s' + (s.guru ? ' chk-g' : '') + y + '">' + esc(s.text + (s.coda || '')) + '</span>';
      mark += '<span class="chk-m' + y + '">' + (s.guru ? 'ऽ' : '।') + '</span>';
    });
    return '<div class="chk-pada"><div class="chk-row">' + syl + '</div>' +
      '<div class="chk-row chk-marks">' + mark + '</div>' +
      '<div class="chk-meta">' + p.aksharas + ' अक्षराणि · ' + p.matras + ' मात्राः · गणाः ' +
      esc(p.ganas) + '</div></div>';
  }

  function panelHtml(id, res) {
    var m = res.match || {};
    var head;
    if (m.names && m.names.length) {
      head = '<b>' + esc(m.names.join(' / ')) + '</b> <small>(' + esc(m.kind || '') + ')</small>' +
        (m.gana ? '<div class="chk-meta">गणाः ' + esc(m.gana) +
          (m.yati && m.yati.length ? ' · यतिः ' + m.yati.join(', ') : '') +
          (m.aksh ? ' · अक्षराणि ' + m.aksh : '') + '</div>' : '');
    } else if (m.kind === 'अज्ञातम्' && m.near && m.near.length) {
      head = '<b>वृत्तं न निर्णीतम्</b> — <span class="chk-warn">सम्भाव्यविचलनम् / पाठदोषः?</span>' +
        '<div class="chk-meta">समीपवर्तीनि: ' + m.near.map(esc).join(', ') + '</div>';
    } else if (m.kind) {
      head = '<b>' + esc(m.kind) + '</b>';
    } else {
      head = '<b>विश्लेषणं न शक्यम्</b>';
    }
    return '<div class="chk-head">' + head + '</div>' +
      res.padas.map(function (p) { return padaHtml(p, m.yati); }).join('') +
      '<div class="chk-actions">' +
      '<button class="chk-btn" data-chk-ai="' + id + '">✦ AI cross-check (Ask Acharya)</button>' +
      '<a class="chk-btn" href="vyakarana/chandas.html?q=' + encodeURIComponent(shlokaText(id)) + '">🎵 Full analyzer ↗</a>' +
      '<button class="chk-btn" data-chk-close="' + id + '">✕ Close</button></div>' +
      '<div class="chk-meta">Scansion computed locally by the site\'s own chandas engine — no AI cost. ' +
      'The AI cross-check uses your configured key (⚙).</div>';
  }

  function injectStyles() {
    if (document.getElementById('chk-style')) return;
    var st = document.createElement('style');
    st.id = 'chk-style';
    st.textContent =
      '.chk-panel{margin:8px 12px;padding:10px 12px;border:1px solid var(--card-border,#444);' +
      'border-radius:12px;background:var(--panel-bg,var(--card-bg,#222));font-size:14px}' +
      '.chk-head{font-family:var(--font-sanskrit,serif);font-size:15px;margin-bottom:6px;color:var(--accent-gold,#e0b055)}' +
      '.chk-warn{color:var(--accent-red,#d06a4e)}' +
      '.chk-pada{margin:8px 0;border-top:1px dashed var(--card-border,#444);padding-top:6px}' +
      '.chk-row{display:flex;flex-wrap:wrap;gap:2px;font-family:var(--font-sanskrit,serif)}' +
      '.chk-s{min-width:26px;text-align:center;padding:1px 3px;border-radius:5px}' +
      '.chk-s.chk-g{background:color-mix(in srgb,var(--accent-gold,#e0b055) 22%,transparent)}' +
      '.chk-yati{box-shadow:inset -2px 0 0 var(--accent-red,#d06a4e)}' +
      '.chk-m{min-width:26px;text-align:center;color:var(--muted-text,#999)}' +
      '.chk-meta{font-size:12px;color:var(--muted-text,#999);margin-top:3px}' +
      '.chk-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px}' +
      '.chk-btn{border:1px solid var(--card-border,#444);border-radius:999px;background:none;' +
      'color:var(--text-primary,#eee);padding:5px 12px;cursor:pointer;font-size:12.5px;text-decoration:none}' +
      '.chk-btn:hover{border-color:var(--accent-gold,#e0b055)}';
    document.head.appendChild(st);
  }

  window.dgeCtxChandasCheck = function (ctx) {
    var id = (ctx && ctx.shlokaId != null) ? ctx.shlokaId : (window.contextShlokaId || window.activeId);
    if (id == null) return;
    injectStyles();
    var card = document.getElementById('shloka-' + id);
    if (!card) return;
    var existing = document.getElementById('chk-' + id);
    if (existing) { existing.remove(); return; }   // toggle off
    var panel = document.createElement('div');
    panel.className = 'chk-panel';
    panel.id = 'chk-' + id;
    panel.innerHTML = '<div class="chk-meta">छन्दः-विश्लेषणम्…</div>';
    card.appendChild(panel);
    window.DGEChandas.loadDB('').then(function () {
      var res = window.DGEChandas.analyzeText(shlokaText(id));
      panel.innerHTML = panelHtml(id, res);
      panel.querySelectorAll('[data-chk-ai]').forEach(function (b) {
        b.onclick = function () {
          if (typeof window.askAcharyaForShloka === 'function') window.askAcharyaForShloka(id, 'shloka');
        };
      });
      panel.querySelectorAll('[data-chk-close]').forEach(function (b) {
        b.onclick = function () { panel.remove(); };
      });
    }).catch(function () {
      panel.innerHTML = '<div class="chk-meta">वृत्तकोशः न प्राप्तः — the vrutta database did not load.</div>';
    });
  };

  function register() {
    if (typeof window.dgeRegisterContextualActions === 'function') {
      // same shape as a taxonomyOverrides entry: objectTypes + add[]
      window.dgeRegisterContextualActions({
        objectTypes: ['shloka'],
        add: [{ id: 'chandas', icon: 'music', label: 'छन्दः-परीक्षा (metre check)', action: 'dgeCtxChandasCheck' }]
      });
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', register);
  else register();
})();
