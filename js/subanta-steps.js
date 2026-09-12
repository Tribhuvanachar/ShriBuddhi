/* ==========================================================================
 * DGE · Subanta prakriyā — step-by-step derivations for the Śabdapāṭha.
 *
 * Shared by shabda.html (tap any declension cell) and the reader's word
 * modal (ai.js — the matched form's derivation renders automatically).
 * Uses the same vidyut-prakriya WASM engine rupasiddhi.html ships
 * (dge/wasm/vidyut/, Apache-2.0), loaded lazily on the first derivation
 * request only — a reader who never asks for steps never pays the 1.2 MB.
 *
 * Feminine stems: vidyut distinguishes a plain prātipadika from a
 * nyāp-anta one (लता is ṭāp-anta; deriving it as {basic} yields the wrong
 * लताः for प्रथमा एकवचनम्, while {nyap} yields लता — verified against the
 * engine, not assumed). Since the Śabdapāṭha's own data doesn't say which
 * a feminine headword is, both are derived and the caller matches results
 * against the form its table actually displays.
 *
 * Self-contained SLP1 ↔ Devanagari converters (no Sanscript dependency:
 * both host pages load it from a CDN that can fail, and a derivation
 * feature that silently dies with it would read as broken).
 * ========================================================================== */
(function () {
  'use strict';

  var SELF = (document.currentScript && document.currentScript.src) || location.href;

  /* ---- SLP1 -> Devanagari (same tables rupasiddhi.js uses) ---- */
  var VI = { a: 'अ', A: 'आ', i: 'इ', I: 'ई', u: 'उ', U: 'ऊ', f: 'ऋ', F: 'ॠ',
             x: 'ऌ', X: 'ॡ', e: 'ए', E: 'ऐ', o: 'ओ', O: 'औ' };
  var V  = { a: '', A: 'ा', i: 'ि', I: 'ी', u: 'ु', U: 'ू', f: 'ृ', F: 'ॄ',
             x: 'ॢ', X: 'ॣ', e: 'े', E: 'ै', o: 'ो', O: 'ौ' };
  var C  = { k: 'क', K: 'ख', g: 'ग', G: 'घ', N: 'ङ', c: 'च', C: 'छ', j: 'ज',
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
      else if (ch === '\\' || ch === '^') { i += 1; }
      else { out += ch; i += 1; }
    }
    return out;
  }
  /* ---- Devanagari -> SLP1 (inverse; enough for prātipadika stems) ---- */
  var D2C = {}, D2VI = {}, D2V = {}, D2O = {};
  Object.keys(C).forEach(function (k) { D2C[C[k]] = k; });
  Object.keys(VI).forEach(function (k) { D2VI[VI[k]] = k; });
  Object.keys(V).forEach(function (k) { if (V[k]) D2V[V[k]] = k; });
  Object.keys(OTHER).forEach(function (k) { D2O[OTHER[k]] = k; });
  function slp(dv) {
    var out = '', s = String(dv || '').normalize('NFC'), i = 0;
    while (i < s.length) {
      var ch = s[i];
      if (D2C[ch]) {
        var nx = s[i + 1];
        if (nx === '्') { out += D2C[ch]; i += 2; }           // virama
        else if (nx && D2V[nx]) { out += D2C[ch] + D2V[nx]; i += 2; }
        else { out += D2C[ch] + 'a'; i += 1; }
      } else if (D2VI[ch]) { out += D2VI[ch]; i += 1; }
      else if (D2O[ch]) { out += D2O[ch]; i += 1; }
      else if (ch === '‌' || ch === '‍') { i += 1; }     // ZW(N)J
      else { out += ch; i += 1; }
    }
    return out;
  }

  /* ---- lazy engine ---- */
  var enginePromise = null, vidyut = null;
  function engine() {
    if (enginePromise) return enginePromise;
    enginePromise = import(new URL('../wasm/vidyut/vidyut_prakriya.js', SELF).href)
      .then(function (mod) {
        return mod.default(new URL('../wasm/vidyut/vidyut_prakriya_bg.wasm', SELF).href)
          .then(function () { vidyut = mod.Vidyut.init(); return vidyut; });
      })
      .catch(function (e) { enginePromise = null; throw e; });
    return enginePromise;
  }

  var LINGA = { P: 'Pum', S: 'Stri', N: 'Napumsaka' };
  var VIBHAKTI = ['Prathama', 'Dvitiya', 'Trtiya', 'Caturthi', 'Panchami',
                  'Sasthi', 'Saptami', 'Sambodhana'];
  var VIBHAKTI_D = ['प्रथमा', 'द्वितीया', 'तृतीया', 'चतुर्थी', 'पञ्चमी',
                    'षष्ठी', 'सप्तमी', 'सम्बोधनम्'];
  var VACANA = ['Eka', 'Dvi', 'Bahu'];
  var VACANA_D = ['एकवचनम्', 'द्विवचनम्', 'बहुवचनम्'];

  function esc(s) {
    return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  /* Derive every prakriyā the engine offers for one declension-table cell.
   * lingaCode: the Śabdapāṭha's own P/S/N/A. Returns a Promise of
   * [{text, textDeva, history}] — [] when nothing derives; rejects only if
   * the engine itself cannot load. Avyaya (A) resolves to [] immediately:
   * an indeclinable has no subanta derivation, and that is an answer, not
   * an error. */
  function derive(stemDeva, lingaCode, vibIdx, vacIdx) {
    var linga = LINGA[lingaCode];
    if (!linga) return Promise.resolve([]);
    var stem = slp(stemDeva);
    return engine().then(function (v) {
      var shapes = lingaCode === 'S'
        ? [{ basic: null, nyap: stem, taddhitanta: null, krdanta: null },
           { basic: stem, nyap: null, taddhitanta: null, krdanta: null }]
        : [{ basic: stem, nyap: null, taddhitanta: null, krdanta: null }];
      var out = [], seen = {};
      shapes.forEach(function (pp) {
        var prs;
        try {
          prs = v.deriveSubantas({
            pratipadika: pp, linga: linga,
            vibhakti: VIBHAKTI[vibIdx], vacana: VACANA[vacIdx]
          }) || [];
        } catch (e) { prs = []; }
        prs.forEach(function (p) {
          if (seen[p.text]) return;
          seen[p.text] = true;
          out.push({ text: p.text, textDeva: deva(p.text), history: p.history });
        });
      });
      return out;
    });
  }

  /* ---- rendering (rupasiddhi.js's step style, link-out sutra codes) ---- */
  var RULE_SRC = { ashtadhyayi: '', varttika: 'वा॰', dhatupatha: 'धा॰',
                   kashika: 'का॰', linganushasanam: 'लिङ्गा॰', kaumudi: 'कौ॰',
                   unadi: 'उ॰', phit: 'फि॰', anyatra: '' };
  function stepsHtml(history) {
    var rows = (history || []).map(function (st) {
      var code = st.rule.code, src = st.rule.source;
      var isSutra = src === 'ashtadhyayi' && /^\d\.\d\.\d{1,3}$/.test(code);
      // In-page popover (intellisense.js's document click delegate), not a
      // real navigation: a target="_blank" tab doesn't reliably inherit the
      // vandana-guard sessionStorage flag, so the new tab bounced through the
      // gate and back -- the "click does nothing but flash the landing page"
      // bug. The host page must load intellisense.js for this to open.
      var codeHtml = isSutra
        ? '<span class="sst-code dge-sutra-ref" role="button" tabindex="0" data-sutra="' + esc(code) + '">' + esc(code) + '</span>'
        : '<span class="sst-code sst-code-plain">' + esc(((RULE_SRC[src] || src) + ' ' + code).trim()) + '</span>';
      var terms = st.result.filter(function (t) { return t.text; })
        .map(function (t) {
          return '<span class="deva ' + (t.wasChanged ? 'sst-t-chg' : 'sst-t') + '">' + esc(deva(t.text)) + '</span>';
        }).join('<span class="sst-plus">+</span>');
      return '<li>' + codeHtml + '<span class="sst-terms">' + terms + '</span></li>';
    }).join('');
    return '<ol class="sst-steps">' + rows + '</ol>';
  }

  /* One cell's full panel: header naming the vibhakti/vacana, then each
   * derivable form's steps. expectedDeva (the cell's own display text,
   * '-'-separated variants) marks which derivations match the table. */
  function panelHtml(stemDeva, lingaCode, vibIdx, vacIdx, results, expectedDeva) {
    var head = '<div class="sst-head deva">' + esc(stemDeva) + ' · ' +
      VIBHAKTI_D[vibIdx] + ' ' + VACANA_D[vacIdx] + '</div>';
    if (lingaCode === 'A') {
      return head + '<p class="sst-note">अव्ययम् — indeclinable, so there is no विभक्ति derivation to show.</p>';
    }
    if (!results.length) {
      return head + '<p class="sst-note">No derivation — the engine does not derive this form from the bare stem (some pronouns and irregular words need special handling it doesn’t expose for plain prātipadikas).</p>';
    }
    var expected = String(expectedDeva || '').split('-').map(function (x) { return x.trim(); });
    var anyMatch = results.some(function (r) { return expected.indexOf(r.textDeva) !== -1; });
    var body = results.map(function (r) {
      var tag = expected.indexOf(r.textDeva) !== -1
        ? '' : (anyMatch ? ' <small class="sst-alt">(वैकल्पिकम्)</small>' : '');
      return (results.length > 1 ? '<h4 class="deva sst-form">' + esc(r.textDeva) + tag + '</h4>' : '') +
        stepsHtml(r.history);
    }).join('');
    var note = !anyMatch && expectedDeva
      ? '<p class="sst-note">The engine’s derivation differs from the listed form — both are shown as-is rather than reconciled by guesswork.</p>'
      : '';
    return head + body + note;
  }

  /* ---- shared styles, injected once ---- */
  var cssDone = false;
  function css() {
    if (cssDone) return; cssDone = true;
    var s = document.createElement('style');
    s.textContent = [
      '.sst-panel{margin:8px 0 4px;padding:10px 12px;border:1px solid var(--card-border,rgba(0,0,0,.15));border-radius:10px;background:var(--card-bg,rgba(0,0,0,.02));font-size:14px;overflow-x:auto}',
      '.sst-head{font-weight:700;margin-bottom:6px}',
      '.sst-form{margin:10px 0 2px;font-size:15px}',
      '.sst-steps{margin:4px 0;padding-left:0;list-style:none}',
      '.sst-steps li{display:flex;gap:8px;align-items:baseline;padding:2px 0;border-bottom:1px dashed var(--card-border,rgba(0,0,0,.07))}',
      '.sst-steps li:last-child{border-bottom:none}',
      '.sst-code{flex:none;font-size:11.5px;font-family:monospace;color:var(--accent-red,#7a3b1d);text-decoration:none;border:1px solid var(--card-border,rgba(0,0,0,.2));border-radius:6px;padding:1px 5px}',
      // Two-class selector so this wins over intellisense.css's generic
      // .dge-sutra-ref styling (gold dotted-underline) regardless of which
      // stylesheet loads later -- the sutra code here keeps looking like the
      // rest of the derivation-step boxes, just clickable.
      '.dge-sutra-ref.sst-code{cursor:pointer;color:var(--accent-red,#7a3b1d);border:1px solid var(--card-border,rgba(0,0,0,.2));padding:1px 5px;border-radius:6px}',
      '.dge-sutra-ref.sst-code:hover{background:var(--card-active,rgba(122,59,29,.12))}',
      '.sst-code-plain{border-style:dashed;color:var(--muted-text,#8a7a63)}',
      '.sst-terms{flex:1;line-height:1.6}',
      '.sst-t-chg{font-weight:700;color:var(--accent-red,#7a3b1d)}',
      '.sst-plus{opacity:.45;padding:0 3px}',
      '.sst-alt{opacity:.6;font-weight:400}',
      '.sst-note{font-size:12.5px;opacity:.7;margin:6px 0 0}',
      '.sst-loading{font-size:12.5px;opacity:.7;padding:6px 0}',
      '.sst-cell-hint{cursor:pointer}',
      '.sst-cell-on{outline:2px solid var(--accent-red,#7a3b1d);outline-offset:-2px;border-radius:4px}'
    ].join('\n');
    document.head.appendChild(s);
  }

  window.DGESubantaSteps = {
    derive: derive, stepsHtml: stepsHtml, panelHtml: panelHtml,
    css: css, deva: deva, slp: slp, warm: engine
  };
})();
