/*!
 * geo-finder.js — DGE "Nearest Holy Place" finder (shared module)
 * ------------------------------------------------------------------
 * A dependency-free, framework-agnostic geolocation finder used by BOTH the
 * Tirtha Prabandha page (tirtha.html) and the Guru Parampara page
 * (guru_parampara.html) — or any page with a list of coordinate-bearing places.
 *
 * Usage:
 *   NearestFinder.mount({
 *     places: [...],                       // array of your objects
 *     getLatLng: p => ({lat:p.lat, lng:p.lng}),  // -> {lat,lng} or null to skip
 *     getName:   p => p.name,
 *     getMeta:   p => p.current_name,      // optional secondary line
 *     onSelect:  p => focusOnPage(p),      // optional: called when a result is tapped
 *     label:     'Nearest tirtha',         // floating button label
 *     limit:     12                        // how many results to show
 *   });
 *
 * No backend, no external requests. Geolocation requires a secure context
 * (https:// or http://localhost); on file:// or plain http the module falls
 * back to manual location entry.
 *
 * License: part of the DGE project (non-commercial, dharma prachara).
 */
(function (global) {
  'use strict';

  var CSS = `
  .ngf-fab{position:fixed;right:16px;bottom:16px;z-index:9998;display:inline-flex;
    align-items:center;gap:8px;padding:12px 16px;border:none;border-radius:999px;
    background:#b3541e;color:#fff;font:600 15px/1 system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;
    box-shadow:0 6px 20px rgba(0,0,0,.28);cursor:pointer;transition:transform .12s ease,filter .12s ease}
  .ngf-fab:hover{filter:brightness(1.06)}
  .ngf-fab:active{transform:scale(.96)}
  .ngf-fab svg{width:18px;height:18px;fill:currentColor}
  .ngf-overlay{position:fixed;inset:0;z-index:9999;display:none;background:rgba(20,14,8,.55);
    backdrop-filter:blur(2px);align-items:flex-end;justify-content:center}
  .ngf-overlay.ngf-open{display:flex}
  .ngf-sheet{width:min(560px,100%);max-height:86vh;display:flex;flex-direction:column;
    background:#fff8f0;color:#241a12;border-radius:18px 18px 0 0;overflow:hidden;
    box-shadow:0 -8px 40px rgba(0,0,0,.35);animation:ngf-up .22s ease}
  @keyframes ngf-up{from{transform:translateY(24px);opacity:.4}to{transform:translateY(0);opacity:1}}
  @media(min-width:640px){.ngf-overlay{align-items:center}.ngf-sheet{border-radius:18px}}
  .ngf-head{display:flex;align-items:center;gap:10px;padding:16px 18px;border-bottom:1px solid #eadfce}
  .ngf-head h2{margin:0;font:700 18px/1.2 'Georgia',serif;flex:1}
  .ngf-x{border:none;background:transparent;font-size:22px;line-height:1;cursor:pointer;color:#8a6a4a;padding:4px 8px}
  .ngf-body{padding:8px 12px 16px;overflow:auto}
  .ngf-status{padding:18px;text-align:center;color:#7a6650;font-size:14px}
  .ngf-status button{margin-top:12px}
  .ngf-btn{display:inline-block;border:1px solid #b3541e;background:#b3541e;color:#fff;
    padding:9px 14px;border-radius:10px;font:600 14px/1 system-ui;cursor:pointer;text-decoration:none}
  .ngf-btn.ngf-ghost{background:transparent;color:#b3541e}
  .ngf-manual{display:flex;gap:8px;flex-wrap:wrap;justify-content:center;margin-top:12px}
  .ngf-manual input{width:120px;padding:8px;border:1px solid #d8c7ad;border-radius:8px;font-size:14px}
  .ngf-list{list-style:none;margin:0;padding:0}
  .ngf-item{display:flex;gap:12px;align-items:center;padding:12px 10px;border-bottom:1px solid #f0e6d6;border-radius:10px}
  .ngf-item:hover{background:#fdeedd}
  .ngf-rank{flex:0 0 34px;height:34px;border-radius:50%;background:#f0dcc2;color:#7a4a1c;
    display:flex;align-items:center;justify-content:center;font:700 14px system-ui}
  .ngf-info{flex:1;min-width:0;cursor:pointer}
  .ngf-name{font:600 15px/1.25 system-ui;margin:0 0 2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .ngf-sub{font-size:12.5px;color:#7a6650;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .ngf-dist{flex:0 0 auto;text-align:right}
  .ngf-km{font:700 15px system-ui;color:#8a3d12}
  .ngf-bearing{font-size:11px;color:#9a8368}
  .ngf-dir{display:inline-flex;align-items:center;gap:4px;margin-top:4px}
  .ngf-dir a{font-size:11.5px;color:#b3541e;text-decoration:none;border:1px solid #e3cfaa;border-radius:7px;padding:3px 7px}
  .ngf-dir a:hover{background:#f6e6cf}
  @media (prefers-color-scheme: dark){
    .ngf-sheet{background:#1e1712;color:#f0e6d8}
    .ngf-head{border-color:#3a2c20}.ngf-head h2{color:#f4d9b0}
    .ngf-x{color:#c9a983}
    .ngf-item{border-color:#33271d}.ngf-item:hover{background:#2a201780}
    .ngf-rank{background:#3a2a1c;color:#f0c48a}
    .ngf-sub,.ngf-status{color:#b8a488}
    .ngf-manual input{background:#2a2018;border-color:#463424;color:#f0e6d8}
  }
  html[data-theme="dark"] .ngf-sheet{background:#1e1712;color:#f0e6d8}
  html[data-theme="dark"] .ngf-head{border-color:#3a2c20}
  html[data-theme="dark"] .ngf-item{border-color:#33271d}
  html[data-theme="dark"] .ngf-rank{background:#3a2a1c;color:#f0c48a}
  html[data-theme="dark"] .ngf-sub,html[data-theme="dark"] .ngf-status{color:#b8a488}
  `;

  function injectCss() {
    if (document.getElementById('ngf-css')) return;
    var s = document.createElement('style');
    s.id = 'ngf-css';
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  // Haversine great-circle distance in km.
  function haversine(a, b) {
    var R = 6371;
    var dLat = (b.lat - a.lat) * Math.PI / 180;
    var dLng = (b.lng - a.lng) * Math.PI / 180;
    var la1 = a.lat * Math.PI / 180, la2 = b.lat * Math.PI / 180;
    var h = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
            Math.cos(la1) * Math.cos(la2) * Math.sin(dLng / 2) * Math.sin(dLng / 2);
    return 2 * R * Math.asin(Math.min(1, Math.sqrt(h)));
  }

  function bearing(a, b) {
    var y = Math.sin((b.lng - a.lng) * Math.PI / 180) * Math.cos(b.lat * Math.PI / 180);
    var x = Math.cos(a.lat * Math.PI / 180) * Math.sin(b.lat * Math.PI / 180) -
            Math.sin(a.lat * Math.PI / 180) * Math.cos(b.lat * Math.PI / 180) *
            Math.cos((b.lng - a.lng) * Math.PI / 180);
    var deg = (Math.atan2(y, x) * 180 / Math.PI + 360) % 360;
    var dirs = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
    return dirs[Math.round(deg / 45) % 8];
  }

  function fmtKm(km) {
    if (km < 1) return Math.round(km * 1000) + ' m';
    if (km < 10) return km.toFixed(1) + ' km';
    return Math.round(km) + ' km';
  }

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function NearestFinder() {}

  NearestFinder.mount = function (opts) {
    injectCss();
    opts = opts || {};
    var cfg = {
      places: opts.places || [],
      getLatLng: opts.getLatLng || function (p) {
        return (p && p.lat != null && p.lng != null) ? { lat: +p.lat, lng: +p.lng } : null;
      },
      getName: opts.getName || function (p) { return p.name || p.title || 'Place'; },
      getMeta: opts.getMeta || function (p) { return p.current_name || p.state || ''; },
      onSelect: opts.onSelect || null,
      label: opts.label || 'Nearest',
      limit: opts.limit || 12,
      mapsMode: opts.mapsMode || 'dir' // 'dir' = directions, 'search' = just open place
    };

    // Floating button
    var fab = document.createElement('button');
    fab.className = 'ngf-fab';
    fab.type = 'button';
    fab.innerHTML =
      '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2a7 7 0 0 0-7 7c0 5 7 13 7 13s7-8 7-13a7 7 0 0 0-7-7zm0 9.5A2.5 2.5 0 1 1 12 6a2.5 2.5 0 0 1 0 5.5z"/></svg>' +
      '<span>' + esc(cfg.label) + '</span>';

    var overlay = document.createElement('div');
    overlay.className = 'ngf-overlay';
    overlay.innerHTML =
      '<div class="ngf-sheet" role="dialog" aria-modal="true" aria-label="Nearest holy places">' +
        '<div class="ngf-head"><h2>' + esc(cfg.label) + '</h2>' +
          '<button class="ngf-x" type="button" aria-label="Close">&times;</button></div>' +
        '<div class="ngf-body"><div class="ngf-status">Tap “Use my location”.</div></div>' +
      '</div>';

    document.body.appendChild(fab);
    document.body.appendChild(overlay);

    var body = overlay.querySelector('.ngf-body');
    var sheet = overlay.querySelector('.ngf-sheet');

    function open() { overlay.classList.add('ngf-open'); showStart(); }
    function close() { overlay.classList.remove('ngf-open'); }

    fab.addEventListener('click', open);
    overlay.querySelector('.ngf-x').addEventListener('click', close);
    overlay.addEventListener('click', function (e) { if (e.target === overlay) close(); });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && overlay.classList.contains('ngf-open')) close();
    });

    function showStart() {
      body.innerHTML =
        '<div class="ngf-status">' +
          '<p>Find the holy places closest to you, sorted by distance.</p>' +
          '<button class="ngf-btn" id="ngf-go" type="button">Use my location</button>' +
          manualHtml() +
        '</div>';
      wireStart();
    }

    function manualHtml() {
      return '<div class="ngf-manual">' +
        '<input id="ngf-lat" inputmode="decimal" placeholder="latitude">' +
        '<input id="ngf-lng" inputmode="decimal" placeholder="longitude">' +
        '<button class="ngf-btn ngf-ghost" id="ngf-manual-go" type="button">Use these</button>' +
      '</div>';
    }

    function wireStart() {
      var go = body.querySelector('#ngf-go');
      if (go) go.addEventListener('click', locate);
      var mg = body.querySelector('#ngf-manual-go');
      if (mg) mg.addEventListener('click', function () {
        var la = parseFloat(body.querySelector('#ngf-lat').value);
        var ln = parseFloat(body.querySelector('#ngf-lng').value);
        if (isFinite(la) && isFinite(ln)) render({ lat: la, lng: ln });
        else setStatus('Enter valid numbers for latitude and longitude.');
      });
    }

    function setStatus(html) {
      body.innerHTML = '<div class="ngf-status">' + html + '</div>';
    }

    function locate() {
      if (!('geolocation' in navigator)) {
        setStatus('Geolocation isn’t available in this browser.' + manualHtml());
        wireStart(); return;
      }
      var secure = (location.protocol === 'https:' ||
                    location.hostname === 'localhost' ||
                    location.hostname === '127.0.0.1');
      setStatus('Locating you…');
      navigator.geolocation.getCurrentPosition(
        function (pos) { render({ lat: pos.coords.latitude, lng: pos.coords.longitude }); },
        function (err) {
          var msg = 'Couldn’t get your location';
          if (err && err.code === 1) msg = 'Location permission was denied.';
          else if (err && err.code === 3) msg = 'Location request timed out.';
          else if (!secure) msg = 'Location needs a secure (https) page. Enter coordinates instead:';
          setStatus(msg + manualHtml());
          wireStart();
        },
        { enableHighAccuracy: false, timeout: 12000, maximumAge: 300000 }
      );
    }

    function render(here) {
      var rows = [];
      for (var i = 0; i < cfg.places.length; i++) {
        var p = cfg.places[i];
        var ll = cfg.getLatLng(p);
        if (!ll || !isFinite(ll.lat) || !isFinite(ll.lng)) continue;
        rows.push({ p: p, ll: ll, km: haversine(here, ll), br: bearing(here, ll) });
      }
      rows.sort(function (a, b) { return a.km - b.km; });
      rows = rows.slice(0, cfg.limit);

      if (!rows.length) { setStatus('No places with coordinates to compare against yet.'); return; }

      var html = '<div style="padding:6px 8px 10px;color:#8a6a4a;font-size:12.5px">' +
        'Your location: ' + here.lat.toFixed(3) + ', ' + here.lng.toFixed(3) +
        ' · showing ' + rows.length + ' nearest</div><ul class="ngf-list">';

      rows.forEach(function (r, i) {
        var name = esc(cfg.getName(r.p));
        var meta = esc(cfg.getMeta(r.p));
        var maps = cfg.mapsMode === 'dir'
          ? 'https://www.google.com/maps/dir/?api=1&destination=' + r.ll.lat + ',' + r.ll.lng
          : 'https://www.google.com/maps/search/?api=1&query=' + r.ll.lat + ',' + r.ll.lng;
        html += '<li class="ngf-item" data-i="' + i + '">' +
          '<div class="ngf-rank">' + (i + 1) + '</div>' +
          '<div class="ngf-info" data-sel="' + i + '">' +
            '<p class="ngf-name">' + name + '</p>' +
            (meta ? '<div class="ngf-sub">' + meta + '</div>' : '') +
            '<div class="ngf-dir"><a href="' + maps + '" target="_blank" rel="noopener">Directions ↗</a></div>' +
          '</div>' +
          '<div class="ngf-dist"><div class="ngf-km">' + fmtKm(r.km) + '</div>' +
            '<div class="ngf-bearing">' + r.br + '</div></div>' +
        '</li>';
      });
      html += '</ul>';
      body.innerHTML = html;

      if (cfg.onSelect) {
        body.querySelectorAll('.ngf-info').forEach(function (el) {
          el.addEventListener('click', function () {
            var idx = +el.getAttribute('data-sel');
            close();
            try { cfg.onSelect(rows[idx].p, rows[idx]); } catch (e) {}
          });
        });
      }
    }

    // public handle
    return {
      open: open,
      close: close,
      setPlaces: function (arr) { cfg.places = arr || []; }
    };
  };

  global.NearestFinder = NearestFinder;
})(window);
