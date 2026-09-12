// dge/js/contact-email.js — the one place the standalone tool pages (which
// don't load core.js/config.js) get the project contact email from, so a
// change in admin/config/config-overrides.json reaches them too instead of
// staying stuck at whatever string was pasted into each page's own JS.
//
// window.DGE_CONTACT_EMAIL starts at the hardcoded default (so a click
// right after page load still works) and is refreshed once the fetch
// resolves — the same default-then-override pattern core.js already uses
// for every other appConfig field.
window.DGE_CONTACT_EMAIL = window.DGE_CONTACT_EMAIL || 'sanatanavidyagurukulam@gmail.com';

window.dgeAdminConfigUrl = window.dgeAdminConfigUrl || function (name) {
  const self = (document.currentScript && document.currentScript.src) ||
               (window.DGE_SCRIPT_BASE || '');
  try { return new URL('../../admin/config/' + name, self).href; }
  catch (e) { return '../admin/config/' + name; }   // fail soft, never throw
};

(function () {
  fetch(window.dgeAdminConfigUrl('config-overrides.json') + '?t=' + Date.now(), { cache: 'no-store' })
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (data) {
      const email = data && data.appConfig && data.appConfig.contactEmail;
      if (email) window.DGE_CONTACT_EMAIL = email;
    })
    .catch(function () { /* offline or missing file — keep the default */ });
})();
