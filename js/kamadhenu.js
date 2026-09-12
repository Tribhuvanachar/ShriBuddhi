// DGE Module: kamadhenu.js — client for the Kamadhenu ZeroGPU Space ("Generate this verse", Mode 2).
//
// Not loaded by any page yet: it is wired into the reader once appConfig.kamadhenuSpaceUrl points at a
// deployed Space (tools/kamadhenu/space/). Talks to the Space's Gradio HTTP API directly (no client lib):
//   POST {space}/gradio_api/call/synthesize        {data: [text, dgeChandas, seed]}  → {event_id}
//   GET  {space}/gradio_api/call/synthesize/{id}   server-sent events; 'complete' carries [audio, meta]
// The metre is DGE's own verdict (window.DGEChandas.analyzeText) so the Space never re-detects it.
// Every call spends the visitor's ZeroGPU quota (≈ 6–15 GPU s per verse) and counts against the Space's
// per-IP daily limit; the first call after idle takes 30–60 s while the model loads.
(function () {
  'use strict';
  function spaceUrl() {
    var u = (window.appConfig && window.appConfig.kamadhenuSpaceUrl) || '';
    return u.replace(/\/+$/, '');
  }
  function chandasOf(text) {
    try {
      if (window.DGEChandas && window.DGEChandas.ready && window.DGEChandas.ready()) {
        var m = window.DGEChandas.analyzeText(text).match;
        return (m && m.names && m.names[0]) || '';
      }
    } catch (e) { /* metre is optional; the Space falls back to syllable count */ }
    return '';
  }
  function parseSSE(txt) {
    var ev = null, lines = txt.split(/\r?\n/);
    for (var i = 0; i < lines.length; i++) {
      var l = lines[i];
      if (l.indexOf('event:') === 0) ev = l.slice(6).trim();
      else if (l.indexOf('data:') === 0 && (ev === 'complete' || ev === 'error')) {
        var data = JSON.parse(l.slice(5));
        if (ev === 'error') throw new Error(typeof data === 'string' ? data : JSON.stringify(data));
        return data;
      }
    }
    return null;
  }
  function fileUrl(space, audio) {
    if (!audio) return null;
    if (audio.url) return audio.url;
    if (audio.path) return space + '/gradio_api/file=' + audio.path;
    return null;
  }
  /** generate(text, {chandas, seed, onStatus}) → Promise<{url, meta}> */
  function generate(text, opts) {
    opts = opts || {};
    var space = spaceUrl();
    if (!space) return Promise.reject(new Error('Kamadhenu Space not configured (appConfig.kamadhenuSpaceUrl)'));
    var chandas = opts.chandas != null ? opts.chandas : chandasOf(text);
    var seed = opts.seed != null ? opts.seed : 60;
    var say = opts.onStatus || function () {};
    // engine: 'vagdhenu' (baseline, /synthesize) or 'kamadhenu' (IndicF5 zero-shot with a 3BHU1 reference clip,
    // /synthesize_kamadhenu; opts.ref = reference id from refs.json)
    var engine = opts.engine === 'kamadhenu' ? 'kamadhenu' : 'vagdhenu';
    var endpoint = engine === 'kamadhenu' ? 'synthesize_kamadhenu' : 'synthesize';
    var payload = engine === 'kamadhenu' ? [text, opts.ref || 'tp_anushtubh_19', seed] : [text, chandas, seed];
    say('requesting');
    return fetch(space + '/gradio_api/call/' + endpoint, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ data: payload })
    }).then(function (r) {
      if (!r.ok) throw new Error('Space returned ' + r.status);
      return r.json();
    }).then(function (j) {
      say('rendering (first call after idle can take a minute)');
      return fetch(space + '/gradio_api/call/' + endpoint + '/' + j.event_id);
    }).then(function (r) { return r.text(); }).then(function (txt) {
      var data = parseSSE(txt);
      if (!data) throw new Error('no result from the Space');
      if (data[1] && data[1].error) throw new Error(data[1].error);   // the Space returns failures as data
      var url = fileUrl(space, data[0]);
      if (!url) throw new Error('Space returned no audio');
      say('done');
      return { url: url, meta: data[1] || {}, chandas: chandas, engine: engine };
    });
  }
  window.DGEKamadhenu = {
    available: function () { return !!spaceUrl(); },
    chandasOf: chandasOf,
    generate: generate
  };
})();
