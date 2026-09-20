/* opaque-resolve.js -- works that a reader reaches by id and never by path.
 *
 * Three shelves in this corpus are named after the websites their text came
 * from. The text is fine to publish and worth searching; the SHELF is not,
 * because a path like
 *     darshana/vedanta/dvaita/DvaitaVedantaIn/later_acharyas/...
 * reproduces that site's own structure and says where the text was taken
 * from before the page has even loaded.
 *
 * So the published site carries an opaque id in place of the path:
 *     id:q7m4k2px
 * and tools/publish_opaque_rewrite.py does the swap as the site is staged.
 * The private checkout keeps its readable paths; only what ships is changed.
 *
 * WHAT A READER GETS. data/display.json -- the published half of the display
 * layer -- gives each id a title and a shelf, and never a path. So a search
 * hit shows the verse, the work's name and "dvaita", which is our own
 * taxonomy, and stops there. The row does not open, because there is no
 * public page to open.
 *
 * WHAT AN ADMIN GETS. The id-to-path map lives in admin/config/opaque_ids.json,
 * which does not publish. An admin holding the private-repo token fetches it
 * through js/admin-remote.js, turns the id back into a path, and opens the
 * real reader. Running the private checkout locally, the same map is simply
 * there on disk and no token is needed.
 *
 * WHAT THIS IS NOT. It is not access control, and the same caveat applies
 * here as in admin-gate.js: this decides what the UI offers, not what a
 * static file server will hand out. The control that matters is that the
 * private works' data.json files are not in the published repository at all
 * -- publish_clean_repo.py prunes them -- so there is nothing at the other
 * end of a guessed URL.
 */
(function (w) {
  'use strict';

  var PREFIX = 'id:';
  var MAP_PATH = 'admin/config/opaque_ids.json';
  var displayCache = null;
  var mapCache = null;

  function isOpaqueId(s) {
    return typeof s === 'string' && s.indexOf(PREFIX) === 0;
  }

  /* The site root, derived from this script's own URL the way
   * global-search.js derives GS_ROOT. It must not be the page's directory:
   * every path below is root-relative, and a page in a subfolder --
   * vyakarana/dhatu.html, which loads this -- would otherwise ask for
   * vyakarana/admin/config/opaque_ids.json and get a 404 that looks exactly
   * like "this reader has no access". Found by that 404. */
  var ROOT = (function () {
    var src = (typeof document !== 'undefined' && document.currentScript &&
               document.currentScript.src) || '';
    try { return new URL('../', src).href; } catch (e) { return '../'; }
  }());

  function base() {
    return w.DGE_SITE_BASE || ROOT;
  }

  /* The published display layer. A miss is not an error: a build that has
   * not been through the rewrite has no display.json and every id in it
   * would be a bug rather than a lookup failure, so callers fall back to
   * showing the id itself. */
  function loadDisplay() {
    if (displayCache) return displayCache;
    displayCache = fetch(new URL('data/display.json', base()).href,
                         { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : { works: {} }; })
      .catch(function () { return { works: {} }; });
    return displayCache;
  }

  function displayFor(id) {
    return loadDisplay().then(function (d) {
      return (d && d.works && d.works[id]) || null;
    });
  }

  function isAdmin() {
    try {
      return w.localStorage.getItem('acharyaAuthorized') === 'true' ||
             w.localStorage.getItem('is_superadmin') === 'true' ||
             !!w.localStorage.getItem('brahmabuddhi_pat');
    } catch (e) { return false; }
  }

  /* The id-to-path map, from whichever side is actually available.
   *
   * Locally the private checkout IS the site, so the file sits at its own
   * path and a plain fetch gets it. On the published site it is not there at
   * all, and the only way through is the GitHub API with the admin's token,
   * which js/admin-remote.js already implements for exactly this repo. Try
   * the cheap one first; the network cost of being wrong is one 404. */
  function loadMap() {
    if (mapCache) return mapCache;
    mapCache = fetch(new URL(MAP_PATH, base()).href, { cache: 'no-store' })
      .then(function (r) {
        if (r.ok) return r.json();
        throw new Error('not local');
      })
      .catch(function () {
        if (typeof w.dgeBrahmaBuddhiFetch === 'function') {
          return w.dgeBrahmaBuddhiFetch(MAP_PATH).then(function (r) { return r.json(); });
        }
        throw new Error('the id map needs the private checkout or an admin token');
      });
    return mapCache;
  }

  function resolve(id) {
    if (!isOpaqueId(id)) return Promise.resolve(id);
    return loadMap().then(function (m) {
      var p = m && m.by_id && m.by_id[id.slice(PREFIX.length)];
      if (!p) throw new Error('no path for ' + id);
      return p;
    });
  }

  /* Where an admin should be sent for this id.
   *
   * `render.html?path=<slug>&jumpShloka=<unit>`. render.html is the reader --
   * it is the only page that loads js/core.js, which is what reads ?path=.
   *
   * Two wrong URLs were tried before this one, and both failed quietly
   * rather than loudly, which is why each needed a browser to catch:
   *   - `render.html?grantha=` -- render.html ignores that parameter, falls
   *     back to a default work and shows "Data Not Found", which reads like
   *     a permissions failure and is not one.
   *   - `index.html?path=` -- what global-search.js's readerBase() produces.
   *     At the site root index.html is the LANDING page, not the reader; it
   *     loads and then reports "The page could not load its text."
   *
   * Always from the site root, never the current directory. The pages that
   * carry search sit in subfolders and a work reached by id is under none
   * of them. */
  function readerUrl(id, unit) {
    return resolve(id).then(function (path) {
      var slug = path.replace(/^data\//, '').replace(/\/data\.json$/, '');
      var u = base() + 'render.html?path=' + encodeURIComponent(slug);
      if (unit) u += '&jumpShloka=' + encodeURIComponent(unit);
      return u;
    });
  }

  /* Fill in the title and shelf for every id-addressed crumb under `root`.
   *
   * The search index stores the last path segment as a work's title, which
   * for these is almost always `mula` -- true, and useless to read. The real
   * title is in display.json, but that is a fetch and rendering is not, so
   * the row paints with whatever the index had and this corrects it a moment
   * later. One fetch covers every row on the page; loadDisplay caches it. */
  function decorate(root) {
    var nodes = (root || document).querySelectorAll('.dge-gs-crumbs-opaque[data-opaque]');
    if (!nodes.length) return Promise.resolve(0);
    return loadDisplay().then(function (d) {
      var n = 0;
      Array.prototype.forEach.call(nodes, function (el) {
        var info = d && d.works && d.works[el.getAttribute('data-opaque')];
        if (!info) return;
        var cur = el.querySelector('.dge-gs-crumb-current');
        if (cur && info.title) { cur.textContent = info.title; n++; }
        if (info.shelf && !el.querySelector('.dge-gs-crumb-shelf')) {
          var sh = document.createElement('span');
          sh.className = 'dge-gs-crumb-shelf';
          sh.textContent = info.shelf;
          el.insertBefore(sh, el.firstChild);
          var sep = document.createElement('span');
          sep.className = 'dge-gs-crumb-sep';
          sep.textContent = '\u203a';
          el.insertBefore(sep, cur);
        }
      });
      return n;
    }).catch(function () { return 0; });
  }

  w.dgeOpaqueDecorate = decorate;
  w.dgeIsOpaqueId = isOpaqueId;
  w.dgeOpaqueDisplay = displayFor;
  w.dgeOpaqueResolve = resolve;
  w.dgeOpaqueReaderUrl = readerUrl;
  w.dgeOpaqueIsAdmin = isAdmin;
  w.DGE_OPAQUE_PREFIX = PREFIX;
}(typeof window !== 'undefined' ? window : this));
