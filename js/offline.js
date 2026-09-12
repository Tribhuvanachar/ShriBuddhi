// DGE Module: offline.js — registers sw.js (see that file for the actual
// caching strategy) and exposes a small status/update surface for the
// Menu drawer's "Offline Mode" row. Scoped to the main reader only
// (dge/index.html), matching this whole overhaul's scope — not the
// standalone tool pages (ashtadhyayi.html, kavya.html, etc.).
window.DGE_VERSIONS = window.DGE_VERSIONS || {};
window.DGE_VERSIONS['offline.js'] = 'v1.0 (registers sw.js for basic offline app-shell support)';

function dgeUpdateOfflineStatusUI() {
  const el = document.getElementById('offlineStatusText');
  if (!el) return;
  if (!('serviceWorker' in navigator)) { el.textContent = '📴 Offline Mode: not supported in this browser'; return; }
  el.textContent = navigator.serviceWorker.controller
    ? '📴 Offline Mode: Ready'
    : '📴 Offline Mode: preparing… (browse a few pages, then it\'s ready)';
}

if ('serviceWorker' in navigator) {
  // Registration itself is async and non-blocking, so there's no real need
  // to defer it to the page's `load` event the way some guides suggest
  // (that's only a minor bandwidth-priority nicety) -- and deferring to
  // `load` specifically is fragile here: a handful of external resources
  // (fonts, CDN scripts) can fail slowly or hang rather than erroring out
  // fast on a constrained connection, which delays `load` right along
  // with it. Registering as soon as the DOM is parsed avoids depending on
  // that. Failing to register (unsupported browser, non-secure origin,
  // etc.) is silently non-fatal either way -- the app works identically
  // without it.
  const register = () => {
    navigator.serviceWorker.register('sw.js').then((reg) => {
      window.dgeSwRegistration = reg;
      dgeUpdateOfflineStatusUI();
    }).catch(() => { /* offline mode just won't be available -- online use is unaffected */ });
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', register);
  else register();
  navigator.serviceWorker.addEventListener('controllerchange', dgeUpdateOfflineStatusUI);
}

document.addEventListener('DOMContentLoaded', dgeUpdateOfflineStatusUI);

// "Check for updates" button in the Menu drawer — service workers already
// auto-check on navigation, this is just an explicit, visible way to ask
// right now rather than wait.
window.dgeCheckForUpdate = function () {
  if (!window.dgeSwRegistration) {
    if (typeof showToast === 'function') showToast('Offline mode is not available in this browser.');
    return;
  }
  window.dgeSwRegistration.update().then(() => {
    if (typeof showToast === 'function') showToast('Checked for updates.');
  }).catch(() => {
    if (typeof showToast === 'function') showToast('Could not check for updates right now.');
  });
};
