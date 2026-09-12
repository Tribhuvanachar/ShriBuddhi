/* =========================================================================
   Menus, from admin/config/menu.json.

   The top-bar buttons, the Explore popup, the Admin popup and the theme list
   used to be fixed markup in render.html: adding an item meant editing the
   page, and hiding one meant deleting a line and remembering why. They are
   now described in one config file, which decides what appears and in what
   order.

   The markup in render.html is still the default. Nothing here removes an
   item that the config does not mention, and if the config cannot be read at
   all this file does nothing whatsoever — the menus stay as written. A broken
   config file must never be the reason a menu is empty.
   ========================================================================= */
(function () {
  'use strict';

  // Derived from this script's own URL rather than the page's, so it holds
  // at any depth and on a project subpath as well as a domain root.
  const self = (document.currentScript && document.currentScript.src) || '';
  let url;
  try { url = new URL('../admin/config/menu.json', self).href; }
  catch (e) { url = '../admin/config/menu.json'; }

  const esc = (s) => String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');

  /* Which tier is unlocked on this device. Reads the same two localStorage
     flags every other gate in the app reads, rather than a third opinion. */
  function tier() {
    let admin = false, superadmin = false;
    try {
      admin = localStorage.getItem('acharyaAuthorized') === 'true';
      superadmin = localStorage.getItem('is_superadmin') === 'true';
    } catch (e) { /* private browsing — treat as logged out */ }
    return { admin: admin || superadmin, superadmin: superadmin };
  }

  /* Two separate questions, deliberately. An item switched off in the config
     is not rendered at all — if it were merely hidden, admin-editor.js would
     find it by id and reveal it again. An item the current tier may not use
     is rendered but hidden, because that is exactly the element
     admin-editor.js reveals once its own gate passes. */
  function included(item) {
    if (item.enabled === false) return false;
    if (item.feature === 'auth' && !(window.AUTH_CONFIG && window.AUTH_CONFIG.enabled)) return false;
    return true;
  }

  function permitted(item, who) {
    if (item.requires === 'superadmin') return who.superadmin;
    if (item.requires === 'admin') return who.admin;
    return true;
  }

  /* An item does one of two things: calls a function on window, or goes to a
     URL. Both close the popup first, matching what the hand-written markup
     did. Built as an onclick string for consistency with the rest of the
     page, with the id and popup name escaped for the same reason. */
  function onclickFor(item, popupId) {
    const close = `window.togglePopup('${esc(popupId)}');`;
    if (item.action) return close + ` window.${esc(item.action)} && window.${esc(item.action)}()`;
    if (item.href)   return close + ` window.location.href='${esc(item.href)}'`;
    return close;
  }

  function itemHtml(item, popupId, who) {
    const cls = ['pop-item'].concat(item.className ? [item.className] : []).join(' ');
    const hidden = permitted(item, who) ? '' : ' style="display:none;"';
    return `<div class="${esc(cls)}"${item.id ? ` id="${esc(item.id)}"` : ''}${hidden}` +
           ` onclick="${esc(onclickFor(item, popupId))}">` +
           `${item.icon ? esc(item.icon) + ' ' : ''}${esc(item.label)}</div>`;
  }

  /* Rebuilds a popup from a list. Leaves the popup untouched if the config
     has nothing to say about it. */
  function renderPopup(popupId, spec, who) {
    const popup = document.getElementById(popupId);
    if (!popup || !spec || !Array.isArray(spec.items)) return;
    const items = spec.items.filter(included);
    if (!items.length) return;
    popup.innerHTML =
      `<div class="popup-label">${esc(spec.label || '')}</div>` +
      items.map(i => itemHtml(i, popupId, who)).join('');
  }

  /* Reorders the top bar and hides what is switched off. Entries are matched
     by the data-topbar attribute in the markup; a button the config does not
     name keeps its place, because appendChild only moves what it is given. */
  function renderTopBar(list) {
    const bar = document.querySelector('.top-actions');
    if (!bar || !Array.isArray(list) || !list.length) return;
    list.forEach(function (entry) {
      const el = bar.querySelector(`[data-topbar="${CSS.escape(String(entry.id))}"]`);
      if (!el) return;
      // Removed rather than hidden — several of these are revealed later by
      // other code (core.js for the admin shield, user-auth.js for the
      // account button), which would undo a display:none.
      if (entry.enabled === false) { el.remove(); return; }
      bar.appendChild(el);   // moves it to the end, so the list order wins
    });
  }

  /* Reorders the theme rows in config order INSIDE whatever container they
     sit in -- since 7 Sep 2026 that is the Appearance accordion body built
     by utils.js dgeInitAccordions; appending to #displayPopup itself pulled
     them out of the accordion to the bottom of the sheet. */
  function renderThemes(list) {
    const popup = document.getElementById('displayPopup');
    if (!popup || !Array.isArray(list) || !list.length) return;
    list.forEach(function (t) {
      const el = popup.querySelector(`.pop-item[data-theme="${CSS.escape(String(t.id))}"]`);
      if (!el) return;
      if (t.enabled === false) { el.style.display = 'none'; return; }
      if (t.label) {
        const swatch = el.querySelector('.theme-swatch');
        el.textContent = t.label;
        if (swatch) el.insertBefore(swatch, el.firstChild);
      }
      (el.parentNode || popup).appendChild(el);
    });
  }

  function apply(cfg) {
    const who = tier();
    renderTopBar(cfg.topBar);
    renderPopup('sectionsPopup', cfg.explore, who);
    renderPopup('adminToolsPopup', cfg.admin, who);
    renderThemes(cfg.themes);

    // The theme picker marks the active entry by walking these same nodes;
    // re-running it puts the tick back on whichever theme is in force.
    if (typeof window.applyTheme === 'function' && window.activeTheme) {
      window.applyTheme(window.activeTheme);
    }
  }

  const ready = (document.readyState === 'loading')
    ? new Promise(r => document.addEventListener('DOMContentLoaded', r))
    : Promise.resolve();

  window.dgeMenuReady = Promise.all([
    ready,
    fetch(url, { cache: 'no-store' }).then(r => (r.ok ? r.json() : null)).catch(() => null)
  ]).then(function (results) {
    const cfg = results[1];
    if (!cfg || typeof cfg !== 'object') return null;
    try { apply(cfg); } catch (e) { console.warn('[Menu] config ignored:', e); return null; }
    return cfg;
  });
})();
