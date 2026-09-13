/* =========================================================================
   Shared gate for the admin tools.

   Each admin page used to carry its passkey as a string literal, so changing
   one meant editing the page that used it and hoping you had found them all.
   They now come from admin/config/keys.json.

   What this is, plainly: a courtesy latch. The keys live in a public
   repository and in the page source, so anyone determined can read them. It
   stops an admin tool being opened by accident or wandered into; it is not
   access control, and nothing genuinely sensitive belongs behind it.
   ========================================================================= */
(function () {
  'use strict';

  // Derived from this script's own URL rather than the page's, so it holds
  // at any depth and on a project subpath as well as a domain root.
  const self = (document.currentScript && document.currentScript.src) || '';
  let url;
  try { url = new URL('../config/keys.json', self).href; }
  catch (e) { url = '../config/keys.json'; }

  const loaded = fetch(url, { cache: 'no-store' })
    .then(function (r) { return r.ok ? r.json() : null; })
    .catch(function () { return null; });

  /* Does `entered` open `gateName`? Resolves false rather than throwing when
     the file is missing or malformed — a broken config must never be the
     reason a gate springs open. */
  window.dgeCheckKey = function (gateName, entered) {
    return loaded.then(function (cfg) {
      var gate = cfg && cfg.gates && cfg.gates[gateName];
      if (!gate || !gate.key) return false;
      return String(entered || '').trim().toUpperCase() ===
             String(gate.key).trim().toUpperCase();
    });
  };

  /* The session flag a gate sets once opened. Falls back to the historical
     name so a page still works if the config cannot be read. */
  window.dgeGateFlag = function (gateName, fallback) {
    return loaded.then(function (cfg) {
      var gate = cfg && cfg.gates && cfg.gates[gateName];
      return (gate && gate.sessionFlag) || fallback;
    });
  };

  window.dgeKeysReady = loaded;
})();
