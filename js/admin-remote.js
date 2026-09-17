// js/admin-remote.js
// BYOK loader for the working repository-hosted management/admin pages.
//
// 12 Sep 2026: every admin/management page (Library Manager, Kosha Manager,
// OCR Review/Studio, Repo & Workflows, Access Control, ...), the Convert
// tool, and the DvaitaVedanta status page moved out of this repo entirely,
// into the PRIVATE Tribhuvanachar/the working repository repo — buddhi is public
// (`git clone`-able by anyone) and must contain only served reader content.
//
// This file is the ONLY trace of that mechanism left in buddhi. It does
// not name a single moved page: the full list — names, paths, tier
// requirements — lives solely in the working repository's own admin/config/admin-menu.json,
// fetched live over the GitHub Contents API using a visitor's OWN
// the working repository-scoped personal access token (same BYOK trust model as
// admin-editor.js's buddhi-scoped one: stored in localStorage on this
// device only, sent to nothing but api.github.com, never bundled or
// hardcoded here). Without a valid token, nobody — not even someone reading
// this file's source — learns what pages exist behind it.
//
// How a page actually renders: fetched HTML is rewritten so its own asset
// references resolve correctly from their NEW location, then dropped into
// an iframe via srcdoc.
//   - A reference that resolves to buddhi (this repo — most of an admin
//     page's own `../js/...`, `../images/...`, `../render.html`, ... — it
//     used to sit one level under this repo's root, still does relative to
//     the working repository's own admin/) becomes an absolute jsDelivr URL: public,
//     unauthenticated, loaded natively by the browser.
//   - A reference that resolves to the working repository itself (admin/, convert/,
//     dvaitavedanta-status/ — content that moved WITH the page) has to be
//     fetched here, with the Authorization header a private repo needs (a
//     plain <script src>/<link href> can never carry one), then inlined.
// A small shim is injected as the first thing the loaded page runs so its
// OWN runtime fetch()/XHR calls to a relative path get the same treatment —
// this is what makes admin/library.html's own `fetch("config/library-overrides.json")`
// (etc.) keep working without editing every admin page's script bodies.
//
// Known limits (by design, for a first working version — see the move's own
// report): a CSS file's own `url(...)` references aren't rewritten, and a
// loaded page's `window.location.href = '...'` navigations (as opposed to
// an <a href>, which IS rewritten) aren't intercepted — closing this overlay
// and reopening a different tool from the menu is the workaround for both.

(function () {
  'use strict';

  window.DGE_VERSIONS = window.DGE_VERSIONS || {};
  window.DGE_VERSIONS['admin-remote.js'] = 'v1.0 (the working repository BYOK loader)';

  var BB_OWNER = 'Tribhuvanachar';
  var BB_REPO = 'the working repository';
  var BB_BRANCH = 'main';
  var BH_OWNER = 'Tribhuvanachar';
  var BH_REPO = 'Jagat';
  var BH_BRANCH = 'main';
  var GH_API = 'https://api.github.com';
  var TOKEN_KEY = 'brahmabuddhi_pat';

  // Config/content that used to sit under buddhi's admin/ and, when this
  // moved, turned out to be read live by every visitor (the whole site
  // menu, SEO tags, landing-page words, legal text, ...) rather than by the
  // admin tools alone — see config/menu.json's own _readme. Those files
  // stayed in buddhi at its repo-root config/ and content/. An inlined
  // admin page's OWN relative fetch (e.g. admin/library.html's
  // fetch("config/library-overrides.json")) still textually resolves to
  // "admin/config/library-overrides.json" — this table redirects exactly
  // those known names back to buddhi instead of the working repository.
  var LEGACY_PUBLIC_CONFIG = ['chandas-features.json', 'config-overrides.json', 'contextual-actions.json',
    'home.json', 'intellisense.json', 'kosha-overrides.json', 'library-overrides.json',
    'menu.json', 'seo.json', 'site.config.json'];
  var LEGACY_PUBLIC_CONTENT = ['ashtadhyayi-layers.json', 'home.json', 'legal.json', 'reader.json',
    'tour.json', 'whats-new.json'];
  var BRAHMA_PREFIXES = ['admin/', 'convert/', 'dvaitavedanta-status/'];

  function token() {
    try { return localStorage.getItem(TOKEN_KEY) || ''; } catch (e) { return ''; }
  }
  function setToken(t) {
    try { localStorage.setItem(TOKEN_KEY, t); } catch (e) { /* private mode: token only lasts this tab */ }
  }

  // Resolves `ref` (a src/href/fetch string found on or fetched from a page
  // at `basePath`) against basePath's own directory, exactly like a browser
  // would resolve a relative URL — plus one extra convention: a ref starting
  // with "/" is repo-root-absolute (used by admin/js/keys.js's inlined
  // copy), not resolved against basePath at all. Returns null for anything
  // absolute/external (http(s):, data:, javascript:, mailto:, a bare #hash)
  // — those are left completely alone by every caller below.
  function resolvePath(basePath, ref) {
    if (!ref) return null;
    if (/^([a-z][a-z0-9+.-]*:)?\/\//i.test(ref)) return null;
    if (/^(data|blob|javascript|mailto|tel):/i.test(ref)) return null;
    if (ref.charAt(0) === '#') return null;
    var hashIdx = ref.indexOf('#');
    if (hashIdx >= 0) ref = ref.slice(0, hashIdx);
    var query = '';
    var qIdx = ref.indexOf('?');
    if (qIdx >= 0) { query = ref.slice(qIdx); ref = ref.slice(0, qIdx); }
    var stack;
    if (ref.charAt(0) === '/') {
      stack = [];
      ref = ref.slice(1);
    } else {
      stack = basePath.split('/').slice(0, -1);
    }
    ref.split('/').forEach(function (p) {
      if (p === '' || p === '.') return;
      if (p === '..') stack.pop(); else stack.push(p);
    });
    return { path: stack.join('/'), query: query };
  }

  function legacyTranslate(path) {
    var m = /^admin\/config\/(.+)$/.exec(path);
    if (m && LEGACY_PUBLIC_CONFIG.indexOf(m[1]) !== -1) return { repo: 'buddhi', path: 'config/' + m[1] };
    var m2 = /^admin\/content\/(.+)$/.exec(path);
    if (m2 && LEGACY_PUBLIC_CONTENT.indexOf(m2[1]) !== -1) return { repo: 'buddhi', path: 'content/' + m2[1] };
    return null;
  }

  function repoFor(path) {
    var legacy = legacyTranslate(path);
    if (legacy) return legacy;
    var isBrahma = BRAHMA_PREFIXES.some(function (p) { return path.indexOf(p) === 0; });
    return { repo: isBrahma ? 'brahma' : 'buddhi', path: path };
  }

  function jsDelivrUrl(path) {
    return 'https://cdn.jsdelivr.net/gh/' + BH_OWNER + '/' + BH_REPO + '@' + BH_BRANCH + '/' + path;
  }

  function fetchFromBrahma(path) {
    var url = GH_API + '/repos/' + BB_OWNER + '/' + BB_REPO + '/contents/' + path + '?ref=' + BB_BRANCH;
    return fetch(url, {
      headers: { 'Accept': 'application/vnd.github.v3.raw', 'Authorization': 'token ' + token() },
      cache: 'no-store'
    }).then(function (res) {
      if (!res.ok) throw new Error(path + ': ' + res.status + ' ' + res.statusText + (res.status === 401 || res.status === 404 ? ' (check your the working repository token in the prompt)' : ''));
      return res;
    });
  }

  // ------------------------------------------------------------------
  // Token prompt + admin menu
  // ------------------------------------------------------------------
  window.dgeOpenBrahmaBuddhiGate = function () {
    if (!token()) { showTokenPrompt(); return; }
    loadMenu();
  };

  function showTokenPrompt() {
    var existing = document.getElementById('bbTokenOverlay');
    if (existing) { existing.style.display = 'flex'; return; }
    var overlay = document.createElement('div');
    overlay.id = 'bbTokenOverlay';
    overlay.style.cssText = 'position:fixed;inset:0;z-index:99999;background:rgba(0,0,0,.55);display:flex;align-items:center;justify-content:center;padding:16px;';
    overlay.innerHTML =
      '<div style="background:#fff;color:#222;border-radius:12px;max-width:420px;width:100%;padding:20px;box-shadow:0 10px 40px rgba(0,0,0,.35);font-family:system-ui,sans-serif;">' +
        '<h3 style="margin:0 0 8px;font-size:16px;">Management Tools</h3>' +
        '<p style="font-size:12px;color:#666;line-height:1.5;margin:0 0 12px;">Paste a GitHub personal access token scoped ONLY to the private the working repository repo (Contents: Read and write, fine-grained, with an expiry). It is stored in this browser only and sent to nothing but api.github.com.</p>' +
        '<input id="bbTokenInput" type="password" placeholder="github_pat_…" style="width:100%;box-sizing:border-box;padding:8px 10px;border:1px solid #ccc;border-radius:8px;font-size:13px;margin-bottom:12px;">' +
        '<div style="display:flex;gap:8px;justify-content:flex-end;">' +
          '<button id="bbTokenCancel" style="padding:7px 14px;border-radius:8px;border:1px solid #ccc;background:transparent;cursor:pointer;">Cancel</button>' +
          '<button id="bbTokenSave" style="padding:7px 14px;border-radius:8px;border:none;background:#7a3b1d;color:#fff;cursor:pointer;">Save &amp; Unlock</button>' +
        '</div>' +
      '</div>';
    document.body.appendChild(overlay);
    document.getElementById('bbTokenInput').value = token();
    document.getElementById('bbTokenCancel').onclick = function () { overlay.remove(); };
    document.getElementById('bbTokenSave').onclick = function () {
      var v = document.getElementById('bbTokenInput').value.trim();
      if (!v) return;
      setToken(v);
      overlay.remove();
      loadMenu();
    };
  }
  window.dgeShowBrahmaBuddhiTokenPrompt = showTokenPrompt;

  function tier() {
    var admin = false, superadmin = false;
    try {
      admin = localStorage.getItem('acharyaAuthorized') === 'true';
      superadmin = localStorage.getItem('is_superadmin') === 'true';
    } catch (e) { /* private mode: treat as logged out */ }
    return { admin: admin || superadmin, superadmin: superadmin };
  }

  var injectedRowIds = []; // so re-opening the gate replaces rather than duplicates

  // Every page this loader can open is keyed by its admin-menu.json `id` —
  // a caller elsewhere in buddhi (a deep-link button inside Library
  // Manager, Kosha Manager, etc.) passes that id, never a literal path, so
  // no the working repository path string sits in buddhi's public JS anywhere.
  // Resolved lazily against the same fetch loadMenu() already does, cached
  // so a deep link opened before the popup menu itself doesn't re-fetch.
  var menuItemsById = null; // null = not yet fetched; {} once it is
  var menuFetchPromise = null;
  function fetchMenuItems() {
    if (menuItemsById) return Promise.resolve(menuItemsById);
    if (menuFetchPromise) return menuFetchPromise;
    menuFetchPromise = fetchFromBrahma('admin/config/admin-menu.json')
      .then(function (res) { return res.json(); })
      .then(function (cfg) {
        menuItemsById = {};
        (cfg.items || []).forEach(function (item) { menuItemsById[item.id] = item; });
        return menuItemsById;
      })
      .catch(function (e) { menuFetchPromise = null; throw e; });
    return menuFetchPromise;
  }

  function loadMenu() {
    var popup = document.getElementById('adminToolsPopup');
    if (!popup) return;
    injectedRowIds.forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.remove();
    });
    injectedRowIds = [];
    var loadingRow = document.createElement('div');
    loadingRow.className = 'pop-item';
    loadingRow.id = 'bbLoadingRow';
    loadingRow.textContent = 'Loading management tools…';
    popup.appendChild(loadingRow);

    fetchMenuItems()
      .then(function (itemsById) {
        loadingRow.remove();
        var who = tier();
        var cfg = { items: Object.keys(itemsById).map(function (k) { return itemsById[k]; }) };
        (cfg.items || []).forEach(function (item, i) {
          var need = item.requires === 'superadmin' ? who.superadmin : (item.requires === 'admin' ? who.admin : true);
          if (!need) return;
          var row = document.createElement('div');
          row.className = 'pop-item';
          row.id = item.id || ('bbItem' + i);
          row.textContent = (item.icon ? item.icon + ' ' : '') + item.label;
          row.onclick = function () {
            if (typeof window.togglePopup === 'function') window.togglePopup('adminToolsPopup');
            window.dgeOpenBrahmaBuddhiPage(item.path);
          };
          popup.appendChild(row);
          injectedRowIds.push(row.id);
        });
        if (typeof window.togglePopup === 'function') window.togglePopup('adminToolsPopup');
      })
      .catch(function (e) {
        loadingRow.textContent = 'Could not load: ' + e.message;
        if (typeof window.showToast === 'function') window.showToast('the working repository menu failed to load: ' + e.message);
      });
  }

  // ------------------------------------------------------------------
  // Page loading
  // ------------------------------------------------------------------
  // `dest` is EITHER a real the working repository path (always contains "/" — this is
  // how loadMenu()'s own click handler calls it, having already fetched the
  // menu securely) OR a bare admin-menu.json `id` (never contains "/" — how
  // every OTHER caller in buddhi's public JS/HTML must call it, e.g. a
  // deep-link button inside Library Manager). An id is resolved against
  // fetchMenuItems()'s cache before anything loads, so the only path
  // strings that ever exist in buddhi's shipped source are the ids
  // themselves, which mean nothing without a valid the working repository token to
  // resolve them. `querySuffix`, if given, is appended to the resolved
  // path (e.g. deep-linking to a specific Library Manager section).
  window.dgeOpenBrahmaBuddhiPage = function (dest, querySuffix) {
    if (!token()) { showTokenPrompt(); return; }
    var resolved = dest.indexOf('/') !== -1
      ? Promise.resolve(dest)
      : fetchMenuItems().then(function (itemsById) {
          var item = itemsById[dest];
          if (!item) throw new Error('unknown management-tool id: ' + dest);
          return item.path;
        });
    resolved.then(function (path) {
      path = path + (querySuffix || '');
      openResolvedPage(path);
    }).catch(function (e) {
      if (typeof window.showToast === 'function') window.showToast('the working repository: ' + e.message);
    });
  };

  function openResolvedPage(path) {
    var overlay = document.getElementById('bbPageOverlay');
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.id = 'bbPageOverlay';
      overlay.style.cssText = 'position:fixed;inset:0;z-index:99998;background:#fff;display:flex;flex-direction:column;';
      overlay.innerHTML =
        '<div style="display:flex;align-items:center;justify-content:space-between;padding:8px 12px;background:#222;color:#fff;font-size:13px;flex-shrink:0;font-family:system-ui,sans-serif;">' +
          '<span id="bbPageTitle">Loading…</span>' +
          '<button id="bbPageClose" style="background:transparent;border:1px solid #666;color:#fff;border-radius:6px;padding:4px 10px;cursor:pointer;">✕ Close</button>' +
        '</div>' +
        '<iframe id="bbPageFrame" style="flex:1;border:0;width:100%;"></iframe>';
      document.body.appendChild(overlay);
      document.getElementById('bbPageClose').onclick = function () { overlay.style.display = 'none'; };
    }
    overlay.style.display = 'flex';
    var titleEl = document.getElementById('bbPageTitle');
    var frame = document.getElementById('bbPageFrame');
    titleEl.textContent = 'Loading ' + path + '…';

    var basePath = path.split('?')[0];
    fetchFromBrahma(path)
      .then(function (res) { return res.text(); })
      .then(function (html) { return inlineAssets(html, basePath); })
      .then(function (html) {
        frame.setAttribute('srcdoc', injectFetchShim(html, basePath));
        titleEl.textContent = path;
      })
      .catch(function (e) {
        titleEl.textContent = 'Failed to load ' + path;
        frame.setAttribute('srcdoc', '<pre style="padding:20px;color:#a00;font-family:monospace;white-space:pre-wrap;">' + String(e.message || e).replace(/</g, '&lt;') + '</pre>');
      });
  }

  // Rewrites <script src>, stylesheet/icon <link href>, <img src> and
  // <a href> found in the fetched page's raw HTML text. See the file
  // header for why buddhi targets become plain absolute jsDelivr URLs
  // while the working repository targets have to be fetched here and inlined.
  function inlineAssets(html, basePath) {
    var jobs = [];

    html = html.replace(/<script\b([^>]*?)\ssrc=(["'])([^"']+)\2([^>]*)><\/script>/gi, function (whole, pre, q, src, post) {
      var resolved = resolvePath(basePath, src);
      if (!resolved) return whole;
      var target = repoFor(resolved.path);
      if (target.repo === 'buddhi') return '<script' + pre + ' src="' + jsDelivrUrl(target.path) + resolved.query + '"' + post + '></script>';
      var idx = jobs.length;
      jobs.push({ idx: idx, kind: 'script', path: target.path });
      return '<script data-bb-pending="' + idx + '"' + pre + post + '></script>';
    });

    html = html.replace(/<link\b([^>]*?)\shref=(["'])([^"']+)\2([^>]*)>/gi, function (whole, pre, q, href, post) {
      var attrs = pre + ' ' + post;
      var isStylesheet = /rel=["']?stylesheet["']?/i.test(attrs);
      var isIcon = /rel=["']?(?:icon|apple-touch-icon)["']?/i.test(attrs);
      if (!isStylesheet && !isIcon) return whole;
      var resolved = resolvePath(basePath, href);
      if (!resolved) return whole;
      var target = repoFor(resolved.path);
      if (target.repo === 'buddhi') return '<link' + pre + ' href="' + jsDelivrUrl(target.path) + resolved.query + '"' + post + '>';
      if (isIcon) return ''; // not worth an authenticated round trip for a favicon; drop rather than break
      var idx = jobs.length;
      jobs.push({ idx: idx, kind: 'style', path: target.path });
      return '<link data-bb-pending="' + idx + '"' + pre + post + '>';
    });

    html = html.replace(/<img\b([^>]*?)\ssrc=(["'])([^"']+)\2([^>]*)>/gi, function (whole, pre, q, src, post) {
      var resolved = resolvePath(basePath, src);
      if (!resolved) return whole;
      var target = repoFor(resolved.path);
      if (target.repo === 'buddhi') return '<img' + pre + ' src="' + jsDelivrUrl(target.path) + resolved.query + '"' + post + '>';
      var idx = jobs.length;
      jobs.push({ idx: idx, kind: 'image', path: target.path });
      return '<img data-bb-pending="' + idx + '"' + pre + post + '>';
    });

    // A link to another the working repository-hosted page is rewritten to reopen
    // through this same loader (a raw href can't carry the auth header a
    // private repo needs); a link to a buddhi page is left as a normal
    // link — this iframe navigating there is fine, it is public.
    html = html.replace(/<a\b([^>]*?)\shref=(["'])([^"']+)\2([^>]*)>/gi, function (whole, pre, q, href, post) {
      var resolved = resolvePath(basePath, href);
      if (!resolved) return whole;
      var target = repoFor(resolved.path);
      if (target.repo !== 'brahma') return whole;
      var call = 'window.parent.dgeOpenBrahmaBuddhiPage &amp;&amp; window.parent.dgeOpenBrahmaBuddhiPage(' +
        JSON.stringify(target.path + (resolved.query || '')).replace(/"/g, '&quot;') + ')';
      return '<a' + pre + ' href="javascript:void(0)" onclick="' + call + '"' + post + '>';
    });

    if (!jobs.length) return Promise.resolve(html);

    return Promise.all(jobs.map(function (job) {
      return fetchFromBrahma(job.path).then(function (res) {
        if (job.kind === 'image') {
          return res.blob().then(function (blob) {
            return new Promise(function (resolve) {
              var reader = new FileReader();
              reader.onload = function () { resolve({ idx: job.idx, kind: job.kind, content: reader.result }); };
              reader.readAsDataURL(blob);
            });
          });
        }
        return res.text().then(function (text) { return { idx: job.idx, kind: job.kind, content: text }; });
      }).catch(function (e) {
        return { idx: job.idx, kind: job.kind, content: '', error: e };
      });
    })).then(function (results) {
      results.forEach(function (f) {
        if (f.kind === 'script') {
          html = html.replace(new RegExp('<script data-bb-pending="' + f.idx + '"([^>]*)></script>'), function (whole, attrs) {
            if (f.error) return '<script>console.warn(' + JSON.stringify('the working repository asset failed: ' + f.error.message) + ');</script>';
            return '<script' + attrs + '>' + f.content.replace(/<\/script>/gi, '<\\/script>') + '</script>';
          });
        } else if (f.kind === 'style') {
          html = html.replace(new RegExp('<link data-bb-pending="' + f.idx + '"([^>]*)>'), function (whole, attrs) {
            var cleaned = attrs.replace(/\srel=(["']).*?\1/i, '').replace(/\stype=(["']).*?\1/i, '');
            return '<style' + cleaned + '>' + f.content + '</style>';
          });
        } else if (f.kind === 'image') {
          html = html.replace(new RegExp('<img data-bb-pending="' + f.idx + '"([^>]*)>'), function (whole, attrs) {
            return '<img src="' + (f.content || '') + '"' + attrs + '>';
          });
        }
      });
      return html;
    });
  }

  // Injected as the first thing the loaded page runs, so ITS OWN runtime
  // fetch() calls to a relative path (e.g. admin/library.html's own
  // fetch("config/library-overrides.json"), admin/kosha.html's
  // fetch("config/kosha-overrides.json")) resolve by the same rules as the
  // static rewriting above, without editing every admin page's script body.
  // The token lives only inside this one srcdoc iframe's own JS realm.
  function injectFetchShim(html, basePath) {
    var shim = '<script>(function(){' +
      'var BASE_PATH=' + JSON.stringify(basePath) + ';' +
      'var TOKEN=' + JSON.stringify(token()) + ';' +
      'var LEGACY_CFG=' + JSON.stringify(LEGACY_PUBLIC_CONFIG) + ';' +
      'var LEGACY_CONTENT=' + JSON.stringify(LEGACY_PUBLIC_CONTENT) + ';' +
      'var BRAHMA_PREFIXES=' + JSON.stringify(BRAHMA_PREFIXES) + ';' +
      resolvePath.toString() + ';' +
      'function legacyTranslate(path){' +
        'var m=/^admin\\/config\\/(.+)$/.exec(path);' +
        'if(m&&LEGACY_CFG.indexOf(m[1])!==-1)return{repo:"buddhi",path:"config/"+m[1]};' +
        'var m2=/^admin\\/content\\/(.+)$/.exec(path);' +
        'if(m2&&LEGACY_CONTENT.indexOf(m2[1])!==-1)return{repo:"buddhi",path:"content/"+m2[1]};' +
        'return null;' +
      '}' +
      'function repoFor(path){var l=legacyTranslate(path);if(l)return l;var isBrahma=BRAHMA_PREFIXES.some(function(p){return path.indexOf(p)===0;});return{repo:isBrahma?"brahma":"buddhi",path:path};}' +
      'var origFetch=window.fetch.bind(window);' +
      'window.fetch=function(input,init){' +
        'var url=(typeof input==="string")?input:(input&&input.url);' +
        'if(url){' +
          'var resolved=resolvePath(BASE_PATH,url);' +
          'if(resolved){' +
            'var target=repoFor(resolved.path);' +
            'if(target.repo==="brahma"){' +
              'var opts={};for(var k in init)opts[k]=init[k];' +
              'opts.headers={};if(init&&init.headers)for(var h in init.headers)opts.headers[h]=init.headers[h];' +
              'opts.headers.Authorization="token "+TOKEN;opts.headers.Accept="application/vnd.github.v3.raw";opts.cache="no-store";' +
              'return origFetch("https://api.github.com/repos/Tribhuvanachar/the working repository/contents/"+target.path+"?ref=main"+(resolved.query?resolved.query.replace("?","&"):""), opts);' +
            '}' +
            'return origFetch("https://cdn.jsdelivr.net/gh/Tribhuvanachar/Jagat@main/"+target.path+(resolved.query||""), init);' +
          '}' +
        '}' +
        'return origFetch(input, init);' +
      '};' +
    '})();<' + '/script>';
    if (/<head[^>]*>/i.test(html)) return html.replace(/<head([^>]*)>/i, '<head$1>' + shim);
    return shim + html;
  }
})();
