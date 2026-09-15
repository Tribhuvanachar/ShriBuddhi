/*
 * genie-asr-recorder.js — DGE Genie ASR benchmark recorder.
 *
 * WHY THIS FILE EXISTS
 * ---------------------
 * The project lead was recording ASR benchmark voice samples with a
 * standalone HTML file (never checked in) that had two structural problems:
 * its item list was a hardcoded array frozen at the moment it was written,
 * so it silently went stale every time genie_asr_benchmark/manifests/
 * manifest.json grew; and "already recorded" was tracked only in that
 * browser's IndexedDB, with no way to tell "recorded here" from "actually
 * in the repo" across devices. Recordings left that tool as a ZIP the
 * project lead had to hand to someone else to unpack and commit by hand.
 *
 * This page fixes both: it reads the manifest at runtime instead of
 * hardcoding it, reads genie-asr-audio-seed's real tree from the GitHub API
 * as the ground truth for "already recorded", and can push a finished
 * recording straight to that branch instead of round-tripping through a ZIP.
 * The ZIP/manifest download stays as an offline fallback.
 *
 * The WAV encoder, IndexedDB schema and ZIP writer below are a faithful port
 * of the standalone tool's own logic — same mic-capture settings (echo
 * cancellation / noise suppression / AGC all deliberately off, for clean ASR
 * test data), same resample-to-16kHz PCM16 mono WAV, same IndexedDB store
 * shape. The push-to-GitHub logic instead follows admin/audio.html's Git
 * Contents-API pattern in this repo, adapted for a per-file commit (each
 * clip is small — one spoken command — so the simpler Contents API PUT is
 * enough; audio.html's blob/tree/commit dance exists there for its much
 * larger, multi-file, atomic-batch case, which doesn't apply here).
 *
 * Runs in the browser (attaches window.GenieASRRecorder for the page's own
 * wiring below) and in Node (module.exports), so the parts that don't touch
 * the DOM — WAV encoding, manifest grouping, tree-presence mapping, push
 * request construction — are covered by tests instead of by reloading the
 * page and eyeballing it. Same convention as js/audio-detect.js.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.GenieASRRecorder = factory();
}(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  var TARGET_SAMPLE_RATE = 16000;
  var REPO_OWNER = 'Tribhuvanachar';
  var REPO_NAME = 'bhumandala';
  var REPO_BRANCH = 'genie-asr-audio-seed';
  var AUDIO_ROOT = 'genie_asr_benchmark/audio';

  // -----------------------------------------------------------------
  // WAV encoding — linear-interpolation resample to 16kHz, then a
  // standard 44-byte RIFF/WAVE header around 16-bit PCM mono samples.
  // -----------------------------------------------------------------
  function resample(input, inRate, outRate) {
    if (inRate === outRate) return input;
    var ratio = inRate / outRate;
    var outLength = Math.max(1, Math.round(input.length / ratio));
    var out = new Float32Array(outLength);
    for (var i = 0; i < outLength; i++) {
      var pos = i * ratio;
      var lo = Math.floor(pos);
      var hi = Math.min(lo + 1, input.length - 1);
      var frac = pos - lo;
      var a = input[lo] || 0, b = input[hi] || 0;
      out[i] = a + (b - a) * frac;
    }
    return out;
  }

  function pcm16WavBytes(samples, sampleRate) {
    var numSamples = samples.length;
    var blockAlign = 2; // 16-bit mono
    var byteRate = sampleRate * blockAlign;
    var dataSize = numSamples * 2;
    var buffer = new ArrayBuffer(44 + dataSize);
    var view = new DataView(buffer);
    function writeStr(offset, s) {
      for (var i = 0; i < s.length; i++) view.setUint8(offset + i, s.charCodeAt(i));
    }
    writeStr(0, 'RIFF');
    view.setUint32(4, 36 + dataSize, true);
    writeStr(8, 'WAVE');
    writeStr(12, 'fmt ');
    view.setUint32(16, 16, true);       // PCM fmt chunk size
    view.setUint16(20, 1, true);        // audio format: PCM
    view.setUint16(22, 1, true);        // channels: mono
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, byteRate, true);
    view.setUint16(32, blockAlign, true);
    view.setUint16(34, 16, true);       // bits per sample
    writeStr(36, 'data');
    view.setUint32(40, dataSize, true);
    var offset = 44;
    for (var i = 0; i < numSamples; i++, offset += 2) {
      var s = Math.max(-1, Math.min(1, samples[i]));
      view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
    }
    return new Uint8Array(buffer);
  }

  // Direct port of the standalone tool's encodeWav(input, inRate, outRate):
  // resample to the target rate, then wrap as PCM16 mono WAV.
  function encodeWav(input, inRate, outRate) {
    var resampled = resample(input, inRate, outRate || TARGET_SAMPLE_RATE);
    return pcm16WavBytes(resampled, outRate || TARGET_SAMPLE_RATE);
  }

  function concatFloat32(chunks) {
    var total = 0;
    for (var i = 0; i < chunks.length; i++) total += chunks[i].length;
    var out = new Float32Array(total);
    var offset = 0;
    for (var j = 0; j < chunks.length; j++) { out.set(chunks[j], offset); offset += chunks[j].length; }
    return out;
  }

  // -----------------------------------------------------------------
  // Manifest shape — read genie_asr_benchmark/manifests/manifest.json at
  // runtime rather than hardcoding items, so this page never goes stale as
  // the manifest grows. Items are grouped by `category` (the only grouping
  // field the real manifest has — there is no "tier" field in the source of
  // truth, so this page doesn't invent one).
  // -----------------------------------------------------------------
  function audioFileFor(item) {
    // Every item in the real manifest that has already been recorded carries
    // an explicit audio_file; items not yet recorded (the three newest
    // categories, as of this being written) omit it, so fall back to the
    // same "audio/<category>/<id>.wav" convention every other item uses.
    return item.audio_file || ('audio/' + item.category + '/' + item.id + '.wav');
  }

  function repoAudioPath(item) {
    return AUDIO_ROOT + '/' + item.category + '/' + item.id + '.wav';
  }

  function groupByCategory(manifest) {
    var order = [];
    var byCat = {};
    manifest.forEach(function (item) {
      if (!byCat[item.category]) { byCat[item.category] = []; order.push(item.category); }
      byCat[item.category].push(item);
    });
    order.sort();
    return order.map(function (cat) { return { category: cat, items: byCat[cat] }; });
  }

  // -----------------------------------------------------------------
  // GitHub Trees API — authoritative "already recorded" state. IndexedDB
  // only knows what THIS browser recorded; the repo's genie-asr-audio-seed
  // branch is what's actually real, so that tree is ground truth and local
  // recordings are shown layered on top of it, not instead of it.
  // -----------------------------------------------------------------
  function treeApiUrl(owner, repo, branch) {
    return 'https://api.github.com/repos/' + owner + '/' + repo + '/git/trees/' +
      encodeURIComponent(branch) + '?recursive=1';
  }

  function buildTreePresenceMap(treeResponse, manifest) {
    var byPath = {};
    var entries = (treeResponse && treeResponse.tree) || [];
    entries.forEach(function (e) { if (e.type === 'blob') byPath[e.path] = e; });
    var map = {};
    manifest.forEach(function (item) {
      var e = byPath[repoAudioPath(item)];
      map[item.id] = e ? { present: true, sha: e.sha, size: e.size } : { present: false };
    });
    return map;
  }

  // -----------------------------------------------------------------
  // Push to GitHub — Contents API (PUT .../contents/{path}), one commit per
  // clip. Each clip is a single short spoken command (tens of KB), so the
  // blob/tree/commit batching admin/audio.html uses for large multi-file
  // pushes isn't needed here; a plain Contents API PUT is atomic per file
  // and simple enough to unit-test the request shape without a network call.
  // Hardcoded to REPO_OWNER/REPO_NAME/REPO_BRANCH — this page structurally
  // cannot target any other repo or branch regardless of what token is
  // pasted in (see admin/config/keys.json's genieasr gate note for why that
  // still isn't the same as a token scoped to just this branch).
  // -----------------------------------------------------------------
  function buildPushRequest(opts) {
    // opts: {owner, repo, branch, path, base64Content, message, existingSha, token}
    var url = 'https://api.github.com/repos/' + opts.owner + '/' + opts.repo + '/contents/' + opts.path;
    var body = { message: opts.message, content: opts.base64Content, branch: opts.branch };
    if (opts.existingSha) body.sha = opts.existingSha;
    return {
      url: url,
      method: 'PUT',
      headers: {
        Authorization: 'token ' + opts.token,
        Accept: 'application/vnd.github+json',
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(body)
    };
  }

  function pushRequestForItem(item, base64Content, token, existingSha) {
    return buildPushRequest({
      owner: REPO_OWNER,
      repo: REPO_NAME,
      branch: REPO_BRANCH,
      path: repoAudioPath(item),
      base64Content: base64Content,
      message: 'Genie ASR recorder: add ' + item.id + ' (' + item.category + ')',
      existingSha: existingSha,
      token: token
    });
  }

  // -----------------------------------------------------------------
  // ZIP writer — store method (no compression; payloads are already WAV),
  // ported from admin/audio.html's buildZip(), which is a real, working,
  // dependency-free ZIP writer already exercised in this repo (local file
  // headers + central directory + end-of-central-directory record).
  // -----------------------------------------------------------------
  var CRC_TABLE = (function () {
    var table = new Uint32Array(256);
    for (var n = 0; n < 256; n++) {
      var c = n;
      for (var k = 0; k < 8; k++) c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1);
      table[n] = c >>> 0;
    }
    return table;
  })();
  function crc32(bytes) {
    var crc = 0xFFFFFFFF;
    for (var i = 0; i < bytes.length; i++) crc = CRC_TABLE[(crc ^ bytes[i]) & 0xFF] ^ (crc >>> 8);
    return (crc ^ 0xFFFFFFFF) >>> 0;
  }
  function buildZip(entries) { // [{name, bytes: Uint8Array}]
    var localParts = [], centralParts = [], offset = 0;
    var encoder = (typeof TextEncoder !== 'undefined') ? new TextEncoder() : null;
    function toBytes(s) {
      if (encoder) return encoder.encode(s);
      var out = []; for (var i = 0; i < s.length; i++) out.push(s.charCodeAt(i) & 0xFF);
      return new Uint8Array(out);
    }
    entries.forEach(function (e) {
      var nameBytes = toBytes(e.name);
      var crc = crc32(e.bytes), size = e.bytes.length;
      var lh = new DataView(new ArrayBuffer(30));
      lh.setUint32(0, 0x04034b50, true); lh.setUint16(4, 20, true); lh.setUint16(6, 0, true);
      lh.setUint16(8, 0, true); lh.setUint16(10, 0, true); lh.setUint16(12, 0, true);
      lh.setUint32(14, crc, true); lh.setUint32(18, size, true); lh.setUint32(22, size, true);
      lh.setUint16(26, nameBytes.length, true); lh.setUint16(28, 0, true);
      localParts.push(new Uint8Array(lh.buffer), nameBytes, e.bytes);

      var ch = new DataView(new ArrayBuffer(46));
      ch.setUint32(0, 0x02014b50, true); ch.setUint16(4, 20, true); ch.setUint16(6, 20, true);
      ch.setUint16(8, 0, true); ch.setUint16(10, 0, true); ch.setUint16(12, 0, true); ch.setUint16(14, 0, true);
      ch.setUint32(16, crc, true); ch.setUint32(20, size, true); ch.setUint32(24, size, true);
      ch.setUint16(28, nameBytes.length, true); ch.setUint16(30, 0, true); ch.setUint16(32, 0, true);
      ch.setUint16(34, 0, true); ch.setUint16(36, 0, true); ch.setUint32(38, 0, true);
      ch.setUint32(42, offset, true);
      centralParts.push(new Uint8Array(ch.buffer), nameBytes);
      offset += 30 + nameBytes.length + size;
    });
    var centralStart = offset;
    var centralSize = centralParts.reduce(function (s, p) { return s + p.length; }, 0);
    var eocd = new DataView(new ArrayBuffer(22));
    eocd.setUint32(0, 0x06054b50, true); eocd.setUint16(4, 0, true); eocd.setUint16(6, 0, true);
    eocd.setUint16(8, entries.length, true); eocd.setUint16(10, entries.length, true);
    eocd.setUint32(12, centralSize, true); eocd.setUint32(16, centralStart, true); eocd.setUint16(20, 0, true);
    return { localParts: localParts, centralParts: centralParts, eocd: new Uint8Array(eocd.buffer) };
  }

  // Manifest export for the ZIP/manifest-download fallback. Uses the real
  // manifest field names (transcript_text, notes) rather than the old
  // standalone tool's invented ones (phrase, note, tier, section).
  function manifestExportData(manifest, statusById) {
    return {
      format: 'DGE Genie ASR benchmark',
      generated_at: new Date().toISOString(),
      count: manifest.length,
      items: manifest.map(function (item) {
        return {
          category: item.category,
          id: item.id,
          language: item.language,
          transcript_text: item.transcript_text,
          notes: item.notes || null,
          path: repoAudioPath(item),
          status: (statusById && statusById[item.id]) || 'not_recorded'
        };
      })
    };
  }

  return {
    TARGET_SAMPLE_RATE: TARGET_SAMPLE_RATE,
    REPO_OWNER: REPO_OWNER,
    REPO_NAME: REPO_NAME,
    REPO_BRANCH: REPO_BRANCH,
    AUDIO_ROOT: AUDIO_ROOT,
    resample: resample,
    pcm16WavBytes: pcm16WavBytes,
    encodeWav: encodeWav,
    concatFloat32: concatFloat32,
    audioFileFor: audioFileFor,
    repoAudioPath: repoAudioPath,
    groupByCategory: groupByCategory,
    treeApiUrl: treeApiUrl,
    buildTreePresenceMap: buildTreePresenceMap,
    buildPushRequest: buildPushRequest,
    pushRequestForItem: pushRequestForItem,
    crc32: crc32,
    buildZip: buildZip,
    manifestExportData: manifestExportData
  };
}));

// =====================================================================
// Browser wiring — DOM, IndexedDB, getUserMedia. None of this runs under
// Node (module.exports above returns before this point in that case is not
// how UMD works — guarded explicitly instead, since the factory already ran).
// =====================================================================
if (typeof document !== 'undefined') {
  (function () {
    'use strict';
    var G = window.GenieASRRecorder;
    var $ = function (s) { return document.querySelector(s); };
    var $$ = function (s) { return Array.prototype.slice.call(document.querySelectorAll(s)); };

    var GATE = 'genieasr';
    var SESSION_FLAG = 'dge.genieasr.ok';
    var TOKEN_KEY = 'github_genieasr_pat';
    var MANIFEST_URL = '../genie_asr_benchmark/manifests/manifest.json';

    if (sessionStorage.getItem(SESSION_FLAG) === '1') start();
    else {
      $('#gate').style.display = 'flex';
      var tryK = function () {
        window.dgeCheckKey(GATE, $('#gk').value).then(function (ok) {
          if (ok) { sessionStorage.setItem(SESSION_FLAG, '1'); location.reload(); }
          else { $('#gk').value = ''; $('#gk').placeholder = 'wrong — try again'; }
        });
      };
      $('#gbtn').onclick = tryK;
      $('#gk').addEventListener('keydown', function (e) { if (e.key === 'Enter') tryK(); });
      $('#gk').focus();
    }

    function start() {
      if (sessionStorage.getItem(SESSION_FLAG) !== '1') return;
      $('#gate').style.display = 'none'; $('#hdr').style.display = ''; $('#main').style.display = '';
      if (localStorage.getItem('dge.genieasr.dark') === '1') document.body.classList.add('dark');
      $('#theme').onclick = function () {
        document.body.classList.toggle('dark');
        localStorage.setItem('dge.genieasr.dark', document.body.classList.contains('dark') ? '1' : '0');
      };
      var tok = localStorage.getItem(TOKEN_KEY);
      if (tok) $('#ghToken').value = tok;
      $('#ghToken').addEventListener('input', function () {
        localStorage.setItem(TOKEN_KEY, $('#ghToken').value);
        refreshAllPushButtons();
      });

      boot();
    }

    // -----------------------------------------------------------------
    // IndexedDB — same schema as the standalone tool: a clips store keyed
    // by manifest item id, plus an (unused so far, kept for parity/future
    // use — e.g. remembering the last mic device) meta store.
    // -----------------------------------------------------------------
    var DB_NAME = 'dge_genie_asr_recorder_v1', STORE = 'clips', META = 'meta';
    var dbPromise = null;
    function openDB() {
      if (dbPromise) return dbPromise;
      dbPromise = new Promise(function (resolve, reject) {
        var req = indexedDB.open(DB_NAME, 1);
        req.onupgradeneeded = function () {
          var db = req.result;
          if (!db.objectStoreNames.contains(STORE)) db.createObjectStore(STORE, { keyPath: 'id' });
          if (!db.objectStoreNames.contains(META)) db.createObjectStore(META, { keyPath: 'key' });
        };
        req.onsuccess = function () { resolve(req.result); };
        req.onerror = function () { reject(req.error); };
      });
      return dbPromise;
    }
    function storeOp(store, mode, fn) {
      return openDB().then(function (db) {
        return new Promise(function (resolve, reject) {
          var os = db.transaction(store, mode).objectStore(store);
          var req = fn(os);
          req.onsuccess = function () { resolve(req.result); };
          req.onerror = function () { reject(req.error); };
        });
      });
    }
    function getClip(id) { return storeOp(STORE, 'readonly', function (os) { return os.get(id); }); }
    function putClip(o) { return storeOp(STORE, 'readwrite', function (os) { return os.put(o); }); }
    function delClip(id) { return storeOp(STORE, 'readwrite', function (os) { return os.delete(id); }); }
    function clearClips() { return storeOp(STORE, 'readwrite', function (os) { return os.clear(); }); }
    function allClips() {
      return openDB().then(function (db) {
        return new Promise(function (resolve, reject) {
          var out = [];
          var req = db.transaction(STORE, 'readonly').objectStore(STORE).openCursor();
          req.onsuccess = function () {
            var cur = req.result;
            if (cur) { out.push(cur.value); cur.continue(); } else resolve(out);
          };
          req.onerror = function () { reject(req.error); };
        });
      });
    }

    // -----------------------------------------------------------------
    // Mic capture — settings deliberately off for clean ASR test data.
    // -----------------------------------------------------------------
    var micStream = null;
    var recCtx = null, recSource = null, recProcessor = null, recMute = null;
    var recChunks = [], recId = null, isRecording = false;

    async function enableMic() {
      micStream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: false, noiseSuppression: false, autoGainControl: false }
      });
      $('#micBtn').textContent = '🎙️ Microphone enabled';
      $('#micBtn').disabled = true;
      $$('.rec-btn').forEach(function (b) { b.disabled = false; });
    }

    function startRecording(id) {
      if (!micStream) throw new Error('Enable the microphone first.');
      if (isRecording) return;
      recCtx = new (window.AudioContext || window.webkitAudioContext)();
      recSource = recCtx.createMediaStreamSource(micStream);
      recProcessor = recCtx.createScriptProcessor(4096, 1, 1);
      recMute = recCtx.createGain();
      recMute.gain.value = 0; // silence the monitor path so playback doesn't feed back into the mic
      recChunks = [];
      recId = id;
      isRecording = true;
      recProcessor.onaudioprocess = function (e) {
        recChunks.push(new Float32Array(e.inputBuffer.getChannelData(0)));
      };
      recSource.connect(recProcessor);
      recProcessor.connect(recMute);
      recMute.connect(recCtx.destination);
    }

    async function stopRecording() {
      if (!isRecording) return null;
      isRecording = false;
      var id = recId;
      recProcessor.disconnect(); recSource.disconnect(); recMute.disconnect();
      var sr = recCtx.sampleRate;
      var samples = G.concatFloat32(recChunks);
      var ctxToClose = recCtx;
      recChunks = []; recId = null; recProcessor = null; recSource = null; recMute = null; recCtx = null;
      await ctxToClose.close();
      var wavBytes = G.encodeWav(samples, sr, G.TARGET_SAMPLE_RATE);
      return { id: id, wavBytes: wavBytes, blob: new Blob([wavBytes], { type: 'audio/wav' }) };
    }

    // -----------------------------------------------------------------
    // Boot: fetch manifest + GitHub tree in parallel, render, wire up.
    // -----------------------------------------------------------------
    var manifest = [];
    var groups = [];
    var treePresence = {}; // id -> {present, sha, size} — authoritative
    var localStatus = {};  // id -> 'done' | 'recording' — from IndexedDB, this browser only
    var treeLoadFailed = false;

    async function boot() {
      try {
        var res = await fetch(MANIFEST_URL, { cache: 'no-store' });
        if (!res.ok) throw new Error('HTTP ' + res.status);
        manifest = await res.json();
      } catch (e) {
        $('#counter').textContent = 'Could not load manifest.json: ' + e.message;
        return;
      }
      groups = G.groupByCategory(manifest);

      var clips = await allClips();
      clips.forEach(function (c) { if (c.done) localStatus[c.id] = 'done'; });

      try {
        var treeRes = await fetch(G.treeApiUrl(G.REPO_OWNER, G.REPO_NAME, G.REPO_BRANCH), { cache: 'no-store' });
        if (!treeRes.ok) throw new Error('HTTP ' + treeRes.status);
        var treeJson = await treeRes.json();
        treePresence = G.buildTreePresenceMap(treeJson, manifest);
      } catch (e) {
        treeLoadFailed = true;
        console.warn('Could not load genie-asr-audio-seed tree — falling back to local-only status:', e);
      }

      render();
    }

    function statusFor(id) {
      if (treePresence[id] && treePresence[id].present) return 'in_repo';
      if (localStatus[id] === 'done') return 'local_unpushed';
      return 'not_recorded';
    }

    function updateCounter() {
      var total = manifest.length;
      var inRepo = 0, localOnly = 0;
      manifest.forEach(function (item) {
        var s = statusFor(item.id);
        if (s === 'in_repo') inRepo++;
        else if (s === 'local_unpushed') localOnly++;
      });
      $('#bar').style.width = total ? Math.round((inRepo / total) * 100) + '%' : '0%';
      var txt = inRepo + ' / ' + total + ' in the repo';
      if (localOnly) txt += ', ' + localOnly + ' recorded here not yet pushed';
      if (treeLoadFailed) txt += ' (could not reach GitHub — repo status may be stale)';
      $('#counter').textContent = txt;
    }

    function badgeFor(status) {
      if (status === 'in_repo') return '<span class="badge ok">✅ in repo</span>';
      if (status === 'local_unpushed') return '<span class="badge part">🟡 recorded here, not pushed</span>';
      return '<span class="badge pend">⚪ not recorded</span>';
    }

    function render() {
      var app = $('#app');
      app.innerHTML = '';
      groups.forEach(function (group) {
        var sect = document.createElement('section');
        sect.className = 'catgroup';
        var h = document.createElement('h2');
        h.className = 'sect';
        h.textContent = group.category + ' (' + group.items.length + ')';
        sect.appendChild(h);
        group.items.forEach(function (item) { sect.appendChild(renderItemCard(item)); });
        app.appendChild(sect);
      });
      updateCounter();
    }

    function renderItemCard(item) {
      var card = document.createElement('div');
      card.className = 'card item';
      card.dataset.id = item.id;
      var status = statusFor(item.id);
      card.innerHTML =
        '<div class="item-head">' +
          '<span class="item-id">' + item.id + '</span>' +
          '<span class="item-lang">' + (item.language || '') + '</span>' +
          badgeFor(status) +
        '</div>' +
        '<div class="item-text">' + escapeHtml(item.transcript_text || '') + '</div>' +
        (item.notes ? '<div class="muted item-notes">' + escapeHtml(item.notes) + '</div>' : '') +
        '<div class="row item-controls">' +
          '<button class="btn rec-btn" data-act="record" disabled>⏺ Record</button>' +
          '<button class="btn" data-act="stop" disabled>⏹ Stop</button>' +
          '<button class="btn" data-act="play" disabled>▶ Play</button>' +
          '<button class="btn" data-act="push" disabled>⬆ Push</button>' +
          '<button class="btn danger" data-act="delete" disabled>🗑</button>' +
          '<span class="muted item-status"></span>' +
        '</div>';
      refreshItemButtons(card, item);
      return card;
    }

    function escapeHtml(s) {
      return String(s).replace(/[&<>"']/g, function (c) {
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
      });
    }

    async function refreshItemButtons(card, item) {
      var clip = await getClip(item.id);
      var micReady = !!micStream;
      card.querySelector('[data-act="record"]').disabled = !micReady || isRecording;
      card.querySelector('[data-act="stop"]').disabled = !(isRecording && recId === item.id);
      card.querySelector('[data-act="play"]').disabled = !clip || !clip.done;
      card.querySelector('[data-act="delete"]').disabled = !clip;
      card.querySelector('[data-act="push"]').disabled = !clip || !clip.done || !$('#ghToken').value.trim();
    }

    // Pasting/clearing the token doesn't itself change any card's recorded
    // state, so this only needs to flip the push buttons' disabled bit, not
    // re-run the full IndexedDB lookup in refreshItemButtons for every card.
    function refreshAllPushButtons() {
      var hasToken = !!$('#ghToken').value.trim();
      $$('.item [data-act="push"]').forEach(function (btn) {
        if (!hasToken) { btn.disabled = true; return; }
        var card = btn.closest('.item');
        var id = card && card.dataset.id;
        getClip(id).then(function (clip) { btn.disabled = !(clip && clip.done); });
      });
    }

    // -----------------------------------------------------------------
    // Item controls
    // -----------------------------------------------------------------
    document.addEventListener('click', async function (e) {
      var btn = e.target.closest && e.target.closest('[data-act]');
      if (!btn) return;
      var card = btn.closest('.item');
      if (!card) return;
      var id = card.dataset.id;
      var item = manifest.find(function (m) { return m.id === id; });
      if (!item) return;
      var act = btn.dataset.act;
      var statusSpan = card.querySelector('.item-status');

      try {
        if (act === 'record') {
          startRecording(id);
          statusSpan.textContent = 'Recording…';
          card.querySelector('[data-act="stop"]').disabled = false;
          card.querySelector('[data-act="record"]').disabled = true;
        } else if (act === 'stop') {
          var result = await stopRecording();
          if (result) {
            await putClip({ id: result.id, category: item.category, done: true, blob: result.blob, createdAt: Date.now() });
            localStatus[result.id] = 'done';
            statusSpan.textContent = 'Saved locally.';
          }
          $$('.item [data-act="record"]').forEach(function (b) { b.disabled = !micStream; });
          card.querySelector('.item-head').innerHTML =
            '<span class="item-id">' + item.id + '</span>' +
            '<span class="item-lang">' + (item.language || '') + '</span>' +
            badgeFor(statusFor(item.id));
          await refreshItemButtons(card, item);
        } else if (act === 'play') {
          var clip = await getClip(id);
          if (clip && clip.blob) {
            var audio = new Audio(URL.createObjectURL(clip.blob));
            audio.play();
          }
        } else if (act === 'delete') {
          if (confirm('Delete the local recording for ' + id + '? This only affects this browser, not the repo.')) {
            await delClip(id);
            delete localStatus[id];
            await refreshItemButtons(card, item);
            card.querySelector('.item-head').innerHTML =
              '<span class="item-id">' + item.id + '</span>' +
              '<span class="item-lang">' + (item.language || '') + '</span>' +
              badgeFor(statusFor(item.id));
          }
        } else if (act === 'push') {
          await pushOne(item, statusSpan);
          await refreshItemButtons(card, item);
          card.querySelector('.item-head').innerHTML =
            '<span class="item-id">' + item.id + '</span>' +
            '<span class="item-lang">' + (item.language || '') + '</span>' +
            badgeFor(statusFor(item.id));
        }
      } catch (err) {
        statusSpan.textContent = 'Error: ' + err.message;
        console.error(err);
      }
    });

    function b64FromArrayBuffer(buf) {
      var bytes = new Uint8Array(buf), binary = '';
      for (var i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
      return btoa(binary);
    }

    async function pushOne(item, statusSpan) {
      var token = $('#ghToken').value.trim();
      if (!token) { statusSpan.textContent = 'Paste a GitHub token first.'; return; }
      var clip = await getClip(item.id);
      if (!clip || !clip.done) { statusSpan.textContent = 'Record it first.'; return; }
      statusSpan.textContent = 'Pushing…';
      var buf = await clip.blob.arrayBuffer();
      var base64 = b64FromArrayBuffer(buf);
      var existingSha = treePresence[item.id] && treePresence[item.id].present ? treePresence[item.id].sha : null;
      var req = G.pushRequestForItem(item, base64, token, existingSha);
      var res = await fetch(req.url, { method: req.method, headers: req.headers, body: req.body });
      if (!res.ok) {
        var j = await res.json().catch(function () { return {}; });
        throw new Error('Push failed: ' + res.status + ' ' + (j.message || res.statusText));
      }
      var j2 = await res.json();
      treePresence[item.id] = { present: true, sha: j2.content && j2.content.sha, size: buf.byteLength };
      statusSpan.textContent = 'Pushed to ' + G.REPO_BRANCH + '.';
      updateCounter();
    }

    // -----------------------------------------------------------------
    // Batch push — every locally-recorded item not yet confirmed in the repo.
    // -----------------------------------------------------------------
    $('#pushAllBtn') && ($('#pushAllBtn').onclick = async function () {
      var token = $('#ghToken').value.trim();
      if (!token) { $('#pushAllStatus').textContent = 'Paste a GitHub token first.'; return; }
      var toPush = manifest.filter(function (item) { return statusFor(item.id) === 'local_unpushed'; });
      if (!toPush.length) { $('#pushAllStatus').textContent = 'Nothing local waiting to be pushed.'; return; }
      $('#pushAllBtn').disabled = true;
      var log = $('#pushAllLog'); log.style.display = 'block'; log.textContent = '';
      for (var i = 0; i < toPush.length; i++) {
        var item = toPush[i];
        log.textContent += 'Pushing ' + item.id + '…\n';
        try {
          var fakeSpan = { textContent: '' };
          await pushOne(item, fakeSpan);
          log.textContent += '  ok.\n';
        } catch (e) {
          log.textContent += '  FAILED: ' + e.message + '\n';
        }
        log.scrollTop = log.scrollHeight;
      }
      render();
      $('#pushAllBtn').disabled = false;
      $('#pushAllStatus').textContent = 'Batch push finished — see log.';
    });

    // -----------------------------------------------------------------
    // Fallback: ZIP / manifest download — works fully offline, no token,
    // no network, for when pushing straight to GitHub isn't wanted or
    // available.
    // -----------------------------------------------------------------
    function triggerDownload(blob, filename) {
      var a = document.createElement('a');
      a.href = URL.createObjectURL(blob); a.download = filename;
      document.body.appendChild(a); a.click(); a.remove();
    }

    $('#manifestBtn') && ($('#manifestBtn').onclick = function () {
      var statusById = {};
      manifest.forEach(function (item) { statusById[item.id] = statusFor(item.id); });
      var data = G.manifestExportData(manifest, statusById);
      triggerDownload(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }), 'genie_asr_manifest_export.json');
    });

    $('#zipBtn') && ($('#zipBtn').onclick = async function () {
      var clips = await allClips();
      var done = clips.filter(function (c) { return c.done; });
      if (!done.length) { $('#zipStatus').textContent = 'No local recordings to package yet.'; return; }
      var entries = [];
      for (var i = 0; i < done.length; i++) {
        var c = done[i];
        var item = manifest.find(function (m) { return m.id === c.id; });
        if (!item) continue;
        var bytes = new Uint8Array(await c.blob.arrayBuffer());
        entries.push({ name: G.repoAudioPath(item), bytes: bytes });
      }
      var statusById = {};
      manifest.forEach(function (item) { statusById[item.id] = statusFor(item.id); });
      var manifestJson = JSON.stringify(G.manifestExportData(manifest, statusById), null, 2);
      entries.push({ name: 'genie_asr_benchmark/manifests/manifest_export.json', bytes: new TextEncoder().encode(manifestJson) });
      entries.push({
        name: 'README.txt',
        bytes: new TextEncoder().encode(
          'DGE Genie ASR benchmark recordings, exported ' + new Date().toISOString() + '.\n' +
          'Unzip at the repo root so the genie_asr_benchmark/audio/... paths land in place,\n' +
          'or copy each file to its matching path under genie_asr_benchmark/audio/ on the\n' +
          'genie-asr-audio-seed branch — never onto main. See that branch\'s own README.\n'
        )
      });
      var zip = G.buildZip(entries);
      var blob = new Blob(zip.localParts.concat(zip.centralParts, [zip.eocd]), { type: 'application/zip' });
      triggerDownload(blob, 'genie_asr_benchmark_recordings.zip');
      $('#zipStatus').textContent = 'Downloaded ' + done.length + ' clip(s).';
    });

    $('#resetBtn') && ($('#resetBtn').onclick = async function () {
      if (!confirm('Clear ALL local recordings in this browser? This does not touch the repo.')) return;
      await clearClips();
      localStatus = {};
      render();
    });

    $('#micBtn') && ($('#micBtn').onclick = function () {
      enableMic().catch(function (e) { $('#micStatus').textContent = 'Mic error: ' + e.message; });
    });
  })();
}
