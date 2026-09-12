/* =========================================================================
   preview-mode.js — "show me what a general user sees", in one tap.

   The ask, 10 Sep 2026: an admin looking at every option at once wants to
   switch to a general-user view "who would not see any of those special
   features or options", and switch back.

   That was previously possible only by typing dgeSetPreviewRole('basic')
   into the browser console, and even then it changed only which CONTENT
   was gated — the 🛡️ Admin Tools menu, the paid Gemini word tools, the
   admin-only search hits and the pending-leaves toggle all stayed. This
   file is the switch; role-access.js's dgeEnterPreview/dgeExitPreview do
   the work (they park the admin flags every module reads, then reload, so
   the whole app answers "not an admin" rather than nine call sites being
   patched one at a time).

   THE BANNER IS LOAD-BEARING, not decoration. While previewing, the admin
   chrome is gone by design — including the 🔑 Access menu this was opened
   from. The banner is therefore the ONLY way back, so it renders straight
   into <body> with its own inline styles rather than depending on a CSS
   file or a container that some page might not have.
   ========================================================================= */
(function () {
  'use strict';
  window.DGE_VERSIONS = window.DGE_VERSIONS || {};
  window.DGE_VERSIONS['preview-mode.js'] = 'v1.0 (10 Sep 2026: one-tap view-as-a-role, with the admin chrome actually gone)';

  // Restore an interrupted preview BEFORE anything else reads the flags: a
  // stash with no live preview beside it means the tab was closed mid-
  // preview, and an admin should not have to know that to get their access
  // back. This is why the file is loaded in <head>, ahead of config.js and
  // everything downstream of it, and why the restore is written out here
  // rather than called from role-access.js -- that file loads far later,
  // by which point a dozen modules have already decided this is not an
  // admin and would stay wrong for the rest of the page's life.
  var STASH_KEY = 'dge.previewStash';
  var ROLE_KEY = 'dge.previewRole';
  var ADMIN_FLAGS = ['acharyaAuthorized', 'is_superadmin'];
  (function restoreIfStale() {
    try {
      var raw = localStorage.getItem(STASH_KEY);
      if (!raw) return;
      if (sessionStorage.getItem(ROLE_KEY)) return;   // still previewing, in this tab
      var stash = JSON.parse(raw) || {};
      ADMIN_FLAGS.forEach(function (k) {
        if (stash[k] == null) localStorage.removeItem(k);
        else localStorage.setItem(k, stash[k]);
      });
      localStorage.removeItem(STASH_KEY);
    } catch (e) { /* private mode */ }
  })();

  function esc(s) {
    var d = document.createElement('div');
    d.textContent = s == null ? '' : String(s);
    return d.innerHTML;
  }

  function activeRole() {
    try { return sessionStorage.getItem(ROLE_KEY) || null; } catch (e) { return null; }
  }

  /* Anonymous is offered first and named plainly, because it is the one
     everybody actually means by "a general user": someone who has not
     signed in at all. 'basic' — a real registered account — is a different
     and weaker test, so both are on the list rather than conflated. */
  function roleChoices() {
    var out = [{ id: 'anonymous', label: 'Visitor (not signed in)' },
               { id: 'basic', label: 'Signed in, no role granted' }];
    var seen = { anonymous: 1, basic: 1 };
    var extra = [];
    try {
      extra = (typeof window.dgeAllRoleDefs === 'function' ? window.dgeAllRoleDefs() : null)
        || (window.AUTH_CONFIG && window.AUTH_CONFIG.roles) || [];
    } catch (e) { extra = []; }
    extra.forEach(function (r) {
      var id = (r && r.id) || r;
      if (!id || seen[id]) return;
      seen[id] = 1;
      out.push({ id: id, label: (r && r.label) || (String(id).charAt(0).toUpperCase() + String(id).slice(1)) });
    });
    return out;
  }

  function banner() {
    var role = activeRole();
    var existing = document.getElementById('dgePreviewBanner');
    if (!role) { if (existing) existing.remove(); return; }
    if (existing) return;
    var label = roleChoices().filter(function (r) { return r.id === role; })[0];
    var el = document.createElement('div');
    el.id = 'dgePreviewBanner';
    el.setAttribute('role', 'status');
    el.style.cssText = [
      'position:fixed', 'left:0', 'right:0', 'bottom:0', 'z-index:2147483000',
      'display:flex', 'align-items:center', 'justify-content:center', 'gap:12px',
      'flex-wrap:wrap', 'padding:9px 14px', 'font:600 13px/1.35 system-ui,sans-serif',
      'background:#8A5A00', 'color:#fff', 'box-shadow:0 -2px 12px rgba(0,0,0,.35)'
    ].join(';');
    el.innerHTML =
      '<span>👁 Previewing as <b>' + esc(label ? label.label : role) + '</b> — admin tools, AI tools and hidden texts are switched off</span>' +
      '<button type="button" id="dgePreviewExitBtn" style="cursor:pointer;border:0;border-radius:6px;' +
      'padding:6px 12px;font:inherit;background:#fff;color:#8A5A00;">Exit preview</button>';
    document.body.appendChild(el);
    document.getElementById('dgePreviewExitBtn').onclick = function () {
      if (typeof window.dgeExitPreview === 'function') window.dgeExitPreview();
    };
    // The banner covers the last line of the page; give the document a
    // matching footer gap rather than leaving content permanently hidden.
    document.body.style.paddingBottom = (el.offsetHeight + 8) + 'px';
  }

  /* The picker. A plain prompt-free sheet rather than window.prompt(): the
     roles are a known list, and typing a role id from memory is exactly the
     friction that kept this feature in the console. */
  window.dgeOpenPreviewPicker = function () {
    if (typeof window.dgeEnterPreview !== 'function') return;
    var choices = roleChoices();
    var wrap = document.createElement('div');
    wrap.id = 'dgePreviewPicker';
    wrap.style.cssText = 'position:fixed;inset:0;z-index:2147483001;background:rgba(0,0,0,.55);' +
      'display:flex;align-items:center;justify-content:center;padding:18px;';
    wrap.innerHTML =
      '<div style="background:var(--panel-bg,#fff);color:var(--text-primary,#222);border-radius:12px;' +
      'max-width:380px;width:100%;padding:18px;font:14px/1.45 system-ui,sans-serif;">' +
      '<div style="font-weight:700;margin-bottom:4px;">👁 View the site as…</div>' +
      '<div style="font-size:12px;opacity:.75;margin-bottom:12px;">Your admin tools, the AI word tools and every text outside the published shelf are switched off until you exit. Nothing about your account changes.</div>' +
      choices.map(function (r) {
        return '<button type="button" class="dge-preview-choice" data-role="' + esc(r.id) + '" ' +
          'style="display:block;width:100%;text-align:left;margin:0 0 6px;padding:9px 12px;border-radius:8px;' +
          'border:1px solid var(--card-border,#ddd);background:transparent;color:inherit;font:inherit;cursor:pointer;">' +
          esc(r.label) + ' <span style="opacity:.55;font-size:11px;">' + esc(r.id) + '</span></button>';
      }).join('') +
      '<button type="button" id="dgePreviewCancel" style="margin-top:6px;width:100%;padding:8px;border:0;' +
      'background:transparent;color:inherit;opacity:.7;font:inherit;cursor:pointer;">Cancel</button></div>';
    document.body.appendChild(wrap);
    wrap.addEventListener('click', function (e) {
      if (e.target === wrap || e.target.id === 'dgePreviewCancel') { wrap.remove(); return; }
      var btn = e.target.closest && e.target.closest('.dge-preview-choice');
      if (btn) window.dgeEnterPreview(btn.getAttribute('data-role'));
    });
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', banner);
  else banner();
})();
