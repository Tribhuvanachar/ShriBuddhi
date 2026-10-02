/* DGE — Kosha offline fast mode: the on-device store.
 *
 * The reader can save a few dictionaries (Shabdartha Kaustubha, Shabdakalpadruma,
 * Vachaspatyam) in the browser's IndexedDB. kosha.js then reads every shard from the device
 * instead of the network (scope "offline"): no round trips, works without internet.
 *
 * The data is built by tools/build_kosha_offline.py into a handful of gzip "packs" plus an
 * offline-manifest.json, published at KOSHA_OFFLINE_BASE (config.js). install() downloads the
 * packs, unpacks them and writes every shard under its relative path (e.g. "_index/bu.json",
 * "sanskrit_sanskrit/vachaspatyam/e/ind.json"); read(rel) is what kosha.js asks for.
 *
 * Nothing here runs unless the reader opts in; the "installed" hint lives in localStorage
 * (kosha_offline_installed) so config.js can choose the scope synchronously.
 */
(function () {
  'use strict';
  var DB = 'dge-kosha-offline';
  var dbp = null;

  function base() {
    var b = '';
    try { b = localStorage.getItem('kosha_offline_base') || ''; } catch (e) {}    // a test override
    return (b || window.KOSHA_OFFLINE_BASE || '').replace(/\/+$/, '');
  }
  function open() {
    return new Promise(function (res, rej) {
      if (!window.indexedDB) { rej(new Error('This browser cannot store data on the device.')); return; }
      var r = indexedDB.open(DB, 1);
      r.onupgradeneeded = function () {
        var d = r.result;
        if (!d.objectStoreNames.contains('shards')) d.createObjectStore('shards');
        if (!d.objectStoreNames.contains('meta')) d.createObjectStore('meta');
      };
      r.onsuccess = function () { res(r.result); };
      r.onerror = function () { rej(r.error); };
    });
  }
  function db() { return dbp || (dbp = open()); }
  // run fn(store) in one transaction; resolve with fn's request result once the transaction completes
  function tx(store, mode, fn) {
    return db().then(function (d) {
      return new Promise(function (res, rej) {
        var t = d.transaction(store, mode), out = fn(t.objectStore(store));
        t.oncomplete = function () { res(out && out.result); };
        t.onerror = t.onabort = function () { rej(t.error || new Error('storage failed')); };
      });
    });
  }

  function read(rel) {
    if (rel === '_index/manifest.json') return tx('meta', 'readonly', function (s) { return s.get('manifest'); }).then(function (v) { return v || null; });
    return tx('shards', 'readonly', function (s) { return s.get(rel); }).then(function (v) { return v === undefined ? null : v; });
  }
  function info() { return tx('meta', 'readonly', function (s) { return s.get('info'); }).then(function (v) { return v || null; }); }

  // fetch one gzip pack, reporting bytes as they arrive, and return the parsed JSON
  function fetchPack(url, onBytes) {
    return fetch(url).then(function (r) {
      if (!r.ok) throw new Error('Download failed (' + r.status + ') for ' + url.split('/').pop());
      var reader = r.body.getReader(), chunks = [], got = 0;
      return (function pump() {
        return reader.read().then(function (x) {
          if (x.done) return;
          chunks.push(x.value); got += x.value.length; if (onBytes) onBytes(got);
          return pump();
        });
      })().then(function () {
        var blob = new Blob(chunks), head = chunks.length ? chunks[0] : new Uint8Array(0);
        var gz = head.length > 1 && head[0] === 0x1f && head[1] === 0x8b;     // some hosts already unzip it
        if (!gz) return new Response(blob).json();
        if (typeof DecompressionStream !== 'function') throw new Error('This browser is too old to unpack the offline data.');
        return new Response(blob.stream().pipeThrough(new DecompressionStream('gzip'))).json();
      });
    });
  }

  function putShards(shards) {
    return db().then(function (d) {
      return new Promise(function (res, rej) {
        var t = d.transaction('shards', 'readwrite'), s = t.objectStore('shards');
        Object.keys(shards).forEach(function (k) { s.put(shards[k], k); });
        t.oncomplete = function () { res(); };
        t.onerror = t.onabort = function () { rej(t.error || new Error('storage failed (is the device full?)')); };
      });
    });
  }

  // The size and contents of what would be downloaded (a ~2 KB file).
  function plan() {
    var b = base();
    if (!b) return Promise.reject(new Error('The offline dictionaries are not published yet.'));
    return fetch(b + '/offline-manifest.json', { cache: 'no-cache' }).then(function (r) {
      if (!r.ok) throw new Error('The offline dictionaries are not published yet (' + r.status + ').');
      return r.json();
    }, function () { throw new Error('Cannot reach the offline dictionaries. Check your connection, or they may not be published yet.'); });
  }

  // Download + unpack everything. onProgress({done, total}) in compressed bytes.
  function install(onProgress) {
    return plan().then(function (meta) {
      var B = base(), total = meta.totalBytes, done = 0, chain = Promise.resolve();
      if (navigator.storage && navigator.storage.persist) { try { navigator.storage.persist(); } catch (e) {} }
      meta.packs.forEach(function (p) {
        chain = chain.then(function () {
          return fetchPack(B + '/' + p.file, function (n) { if (onProgress) onProgress({ done: done + n, total: total }); })
            .then(function (obj) { return putShards(obj.shards); })
            .then(function () { done += p.bytes; if (onProgress) onProgress({ done: done, total: total }); });
        });
      });
      return chain.then(function () {
        return db().then(function (d) {
          return new Promise(function (res, rej) {
            var t = d.transaction('meta', 'readwrite'), s = t.objectStore('meta');
            s.put(meta.manifest, 'manifest');
            s.put({ version: meta.version, builtFrom: meta.builtFrom, builtAt: meta.builtAt, dicts: meta.dicts,
                    bytes: meta.totalBytes, rawBytes: meta.totalRawBytes, installedAt: Date.now() }, 'info');
            t.oncomplete = function () { res(); };
            t.onerror = t.onabort = function () { rej(t.error); };
          });
        });
      }).then(function () { try { localStorage.setItem('kosha_offline_installed', '1'); } catch (e) {} return meta; });
    });
  }

  function remove() {
    return tx('shards', 'readwrite', function (s) { return s.clear(); })
      .then(function () { return tx('meta', 'readwrite', function (s) { return s.clear(); }); })
      .then(function () {
        try { localStorage.removeItem('kosha_offline_installed'); if (localStorage.getItem('kosha_scope') === 'offline') localStorage.setItem('kosha_scope', 'quick'); } catch (e) {}
      });
  }

  window.DGEKoshaOffline = {
    installed: function () { try { return localStorage.getItem('kosha_offline_installed') === '1'; } catch (e) { return false; } },
    read: read, info: info, plan: plan, install: install, remove: remove
  };
})();
