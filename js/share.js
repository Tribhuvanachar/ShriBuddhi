/* =========================================================================
   Share / copy / bookmark a verse WITH its address (7 Sep 2026).

   The lead's report: a shared verse arrived as "Shloka 202 — Sarvamoola Digital Library" — no Veda, no maṇḍala,
   no way back to it. Every share and copy now carries the hierarchy (the taxonomy labels of the grantha's path,
   the same ones the Library shows), the verse's own reference (1.24.3 · Adhyāya 1 · 12 …) and the canonical
   link (js/shortcuts.js's short form when one exists: ?rv1.24.3).

   Depends on: dgeCurrentSlug / dgeCanonicalUrl (core.js), dgeSegLabel (library.js), getText (render.js),
   DGEShortcuts (shortcuts.js). Every dependency is optional — the text degrades to what is known.
   ========================================================================= */
(function () {
  'use strict';
  function strip(html) { return String(html || '').replace(/<br\s*\/?>/gi, '\n').replace(/<[^>]*>/g, '').replace(/\n{3,}/g, '\n\n').trim(); }

  window.dgeShlokaReference = function (id) {
    var slug = window.dgeCurrentSlug || '';
    var sd = window.stotraData;
    var sh = sd && sd.shlokas ? sd.shlokas[id] : null;
    var segs = slug.split('/').filter(Boolean);
    var crumbs = segs.map(function (seg, i) {
      return typeof dgeSegLabel === 'function' ? strip(dgeSegLabel(seg, segs.slice(0, i + 1).join('/'))) : seg;
    });
    var title = sd && sd.metadata && sd.metadata.title ? strip(sd.metadata.title) : (crumbs[crumbs.length - 1] || document.title);
    var ref = '';
    if (sh) {
      var vid = sh.vedicId ? String(sh.vedicId).trim() : '';
      if (vid && !/^[A-Z]{2,}_/.test(vid)) ref = vid.length > 120 ? vid.slice(0, 117) + '…' : vid;   // data-side codes (DV_2586) are not a reference
      else if (sh.unitNo) ref = (sh.unitId || '') + ' · ' + sh.unitNo;
    }
    var url;
    try { url = new URL(typeof window.dgeCanonicalUrl === 'function' ? window.dgeCanonicalUrl(id) : location.href, location.href).href; }
    catch (e) { url = location.href; }
    var short = (window.DGEShortcuts && sh) ? window.DGEShortcuts.make(slug, sh, id) : null;
    var where = crumbs.join(' › ');
    var line = where + (ref ? ' · ' + ref : ' · ' + (typeof id === 'number' || /^\d+$/.test(String(id)) ? 'श्लोकः ' + id : String(id)));
    return { id: id, title: title, crumbs: crumbs, ref: ref, url: url, short: short, line: line };
  };

  window.dgeShlokaShareText = function (id) {
    var raw = typeof getText === 'function' ? strip(getText(id)) : '';
    var r = window.dgeShlokaReference(id);
    return raw + '\n\n— ' + r.line + '\n' + r.url;
  };

  async function copy(text) {
    if (navigator.clipboard) { await navigator.clipboard.writeText(text); return true; }
    var ta = document.createElement('textarea'); ta.value = text; ta.style.position = 'fixed'; ta.style.left = '-9999px';
    document.body.appendChild(ta); ta.select(); var ok = document.execCommand('copy'); ta.remove(); return ok;
  }
  function toast(msg) { if (typeof showToast === 'function') showToast(msg); }

  window.dgeShareShlokaLink = async function (id) {
    var r = window.dgeShlokaReference(id);
    try {
      if (navigator.share) await navigator.share({ title: r.title + (r.ref ? ' ' + r.ref : ''), text: r.line, url: r.url });
      else { await copy(r.url); toast('Link copied' + (r.short ? ' — ?' + r.short : '') + '.'); }
    } catch (e) {
      if (e && e.name === 'AbortError') return;
      try { await copy(r.url); toast('Sharing is not available here; the link is copied instead.'); } catch (e2) { toast('Could not share this link.'); }
    }
  };
  window.dgeCopyShlokaLink = async function (id) {
    var r = window.dgeShlokaReference(id);
    try { await copy(r.url); toast('Link copied' + (r.short ? ' — ?' + r.short : '') + '.'); }
    catch (e) { toast('Could not copy the link.'); }
  };
  // A page cannot add a browser bookmark itself; it can make sure the address bar points at THIS verse and say
  // which key adds the bookmark. (The address already follows the verse being read — see core.js dgeSyncUrl.)
  window.dgeBookmarkShloka = function (id) {
    if (typeof window.dgeSyncUrl === 'function') window.dgeSyncUrl(id);
    var r = window.dgeShlokaReference(id);
    var isMac = /Mac|iPhone|iPad/.test(navigator.platform || '');
    toast('The address now points at this verse' + (r.short ? ' (?' + r.short + ')' : '') + '. Bookmark it with ' +
      (isMac ? '⌘D' : 'Ctrl+D') + ', or the browser menu › Add to bookmarks.');
  };
})();
