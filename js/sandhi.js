// DGE Module: sandhi.js
// Live sandhi-split / word analysis for selected text, via Dharmamitra's
// public tagging API (https://dharmamitra.org). Unlike the AI "Word"
// button in ai.js (which asks an LLM to guess), this calls a real
// analyzer and shows its actual output -- same "real, structured data"
// philosophy as dgeOpenShabdaForSelection/dgeOpenDhatuForSelection.
//
// IMPORTANT, read before touching this file: this is a LIVE THIRD-PARTY
// DEPENDENCY, not local computation. Every click sends the selected text
// to dharmamitra.org over the network. That was a deliberate, informed
// choice (see PENDING.md, 23 Aug entries) -- not an assumption to
// silently extend. In particular: do NOT batch this across the corpus
// (see tools/dcs/README.md's sandhi section) without separately deciding
// how to be a considerate caller of someone else's free server; this file
// only ever sends what a person actually selected, one request at a time.

window.DGE_VERSIONS = window.DGE_VERSIONS || {};
window.DGE_VERSIONS['sandhi.js'] = 'v1 (live sandhi/word split via Dharmamitra, unmodified pip-dependency-equivalent client call)';

const DGE_SANDHI_API_URL = 'https://dharmamitra.org/api-tagging/tagging-parsed/';
const DGE_SANDHI_TIMEOUT_MS = 12000;
const dgeSandhiCache = new Map(); // selected text -> parsed result (session-lifetime only)

function dgeSandhiToIAST(text) {
  const script = window.activeScript || 'devanagari';
  if (script === 'iast' || typeof window.Sanscript === 'undefined') return text;
  try { return window.Sanscript.t(text, script, 'iast'); }
  catch (e) { return text; }
}

function dgeSandhiFromIAST(text) {
  const script = window.activeScript || 'devanagari';
  if (script === 'iast' || typeof window.Sanscript === 'undefined') return text;
  try { return window.Sanscript.t(text, 'iast', script); }
  catch (e) { return text; }
}

function dgeFetchSandhiAnalysis(iastText) {
  const controller = (typeof AbortController !== 'undefined') ? new AbortController() : null;
  const timer = controller ? setTimeout(() => controller.abort(), DGE_SANDHI_TIMEOUT_MS) : null;
  return fetch(DGE_SANDHI_API_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      texts: [iastText],
      mode: 'unsandhied-lemma-morphosyntax',
      human_readable_tags: false,
      grammar_type: 'western',
    }),
    signal: controller ? controller.signal : undefined,
  })
    .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
    .then(function (data) {
      if (timer) clearTimeout(timer);
      const sentence = Array.isArray(data) ? data[0] : null;
      return sentence && sentence.grammatical_analysis ? sentence : null;
    })
    .catch(function (e) {
      if (timer) clearTimeout(timer);
      throw e;
    });
}

// The API response (unsandhied/lemma/tag/notice) is third-party content --
// escape before innerHTML, same discipline as any other external data.
function dgeSandhiEscape(text) {
  const div = document.createElement('div');
  div.textContent = String(text == null ? '' : text);
  return div.innerHTML;
}

function dgeRenderSandhiResult(sentence) {
  const box = document.getElementById('sandhiResult');
  if (!box) return;
  if (!sentence || !sentence.grammatical_analysis || sentence.grammatical_analysis.length === 0) {
    const msg = sentence && sentence.notice ? sentence.notice : 'No analysis returned for this selection.';
    box.innerHTML = '<p style="color:#8a7a63; font-size:13px;">' + dgeSandhiEscape(msg) + '</p>';
    return;
  }
  const rows = sentence.grammatical_analysis.map(function (w) {
    const unsandhied = dgeSandhiEscape(dgeSandhiFromIAST(w.unsandhied || ''));
    const lemma = dgeSandhiEscape(dgeSandhiFromIAST(w.lemma || ''));
    const tag = dgeSandhiEscape(w.tag || '');
    return '<div style="padding:8px 0; border-bottom:1px solid var(--card-border);">'
      + '<div style="font-family:var(--font-sanskrit); font-size:18px;">' + unsandhied + '</div>'
      + '<div style="font-size:12px; color:#8a7a63; margin-top:2px;">'
      + 'lemma: <span style="font-family:var(--font-sanskrit);">' + lemma + '</span>'
      + (tag ? '  ·  ' + tag : '')
      + '</div>'
      + '</div>';
  }).join('');
  box.innerHTML = rows;
}

window.dgeOpenSandhiForSelection = function (e) {
  if (e) e.preventDefault();
  // Devanagari reading, not the on-screen spelling — see dgeLookupWordText in ai.js.
  const selected = (typeof window.dgeLookupWordText === 'function') ? window.dgeLookupWordText() : dgeSelectedWordText();
  if (!selected) { if (typeof showToast === 'function') showToast('Select a word or phrase first.'); return; }
  dgeHideActionTooltip();

  if (typeof openModal === 'function') openModal('sandhiModal');
  const loading = document.getElementById('sandhiLoading');
  const box = document.getElementById('sandhiResult');
  if (loading) loading.style.display = 'block';
  if (box) box.innerHTML = '';

  if (dgeSandhiCache.has(selected)) {
    if (loading) loading.style.display = 'none';
    dgeRenderSandhiResult(dgeSandhiCache.get(selected));
    return;
  }

  const iast = dgeSandhiToIAST(selected);
  dgeFetchSandhiAnalysis(iast)
    .then(function (sentence) {
      dgeSandhiCache.set(selected, sentence);
      if (loading) loading.style.display = 'none';
      dgeRenderSandhiResult(sentence);
    })
    .catch(function () {
      if (loading) loading.style.display = 'none';
      if (box) {
        box.innerHTML = '<p style="color:#8a7a63; font-size:13px;">'
          + 'Sandhi analysis service is unavailable right now — this feature '
          + 'depends on a third-party service (dharmamitra.org), not this '
          + 'site itself. Try again in a moment.</p>';
      }
    });
};
