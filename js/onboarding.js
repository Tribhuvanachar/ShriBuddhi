// DGE Module: onboarding.js
// First-visit name + language preference (Issue 27). Shown once per
// browser; "Skip" always available so it never blocks entry. The language
// choice is the one global preference read by:
//   - transliteration.js's setScript(), for the default display script
//   - ai.js's acharyaSystemPrompt, for the main reader's Ask Acharya replies
//   - ashtadhyayi.js's aiLang, for that page's own separate Gemini prompt
// Scope note: this does NOT translate menu/heading UI text or change sort
// ordering (e.g. Kannada collation) — see PENDING.md for why those are
// deferred rather than guessed at.

window.DGE_VERSIONS = window.DGE_VERSIONS || {};
window.DGE_VERSIONS['onboarding.js'] = 'v1.0';

(function () {
  "use strict";
  var ONBOARDED_KEY = 'dge_onboarded';
  var NAME_KEY = 'dge_user_name';
  var LANG_KEY = 'dge_lang_pref';

  // 21 Sep 2026, the lead: once per LOGIN for a signed-in reader, once per
  // BROWSER for a guest.
  //
  // A guest has nowhere to be remembered but this browser, so localStorage
  // is the whole answer for them. A signed-in reader does have somewhere --
  // their own profile -- and remembering it there is what makes the promise
  // true: answer once, and a new phone or a borrowed laptop does not ask
  // again. Storing it per-browser-per-uid would have asked a second time on
  // the second device, which is the thing being complained about.
  //
  // preferences is already in firestore.rules' selfEditableOnly list, so
  // this needs no rules change and no new document.
  function signedIn() {
    return !!(window.dgeCurrentUser && window.dgeCurrentUser.uid);
  }

  function profileSaysDone() {
    var p = window.dgeCurrentUserProfile;
    return !!(p && p.preferences && p.preferences.onboardedAt);
  }

  // Never throws: a reader whose profile cannot be written still gets to
  // use the site, and the worst case is being asked again next time.
  function rememberOnProfile(patch) {
    try {
      if (!signedIn() || typeof dgeDb === 'undefined' || !dgeDb) return;
      var prefs = Object.assign({}, (window.dgeCurrentUserProfile || {}).preferences || {}, patch,
                                { onboardedAt: new Date().toISOString() });
      window.dgeCurrentUserProfile = Object.assign({}, window.dgeCurrentUserProfile || {},
                                                   { preferences: prefs });
      dgeDb.collection('users').doc(window.dgeCurrentUser.uid)
           .update({ preferences: prefs })
           .catch(function (e) { console.warn('[Onboarding] preference not saved:', e && e.message); });
    } catch (e) { /* offline, or no Firestore: the local key still stands */ }
  }

  // Language preference -> default display script. Sanskrit/English both
  // already have a natural script (devanagari/iast); a Kannada speaker who
  // may not read Devanagari benefits most from the script switching too.
  var LANG_TO_SCRIPT = { en: 'iast', kn: 'kannada', sa: 'devanagari' };

  var pickedLang = null;

  function $(sel) { return document.querySelector(sel); }

  function syncLangButtons() {
    document.querySelectorAll('#onboardLangSeg [data-onboard-lang]').forEach(function (b) {
      var on = b.dataset.onboardLang === pickedLang;
      b.classList.toggle('active-fav', on);
      b.style.background = on ? 'var(--accent-red)' : '';
      b.style.color = on ? '#fff' : '';
      b.style.borderColor = on ? 'var(--accent-red)' : '';
    });
  }

  function wire() {
    document.querySelectorAll('#onboardLangSeg [data-onboard-lang]').forEach(function (b) {
      b.addEventListener('click', function () {
        pickedLang = b.dataset.onboardLang;
        syncLangButtons();
      });
    });
  }

  window.dgeSaveOnboarding = function () {
    var nameEl = $('#onboardName');
    var name = nameEl ? nameEl.value.trim() : '';
    var lang = pickedLang || 'en';
    try {
      if (name) localStorage.setItem(NAME_KEY, name);
      localStorage.setItem(LANG_KEY, lang);
      localStorage.setItem(ONBOARDED_KEY, '1');
      rememberOnProfile({ lang: lang, displayName: name || '' });
    } catch (e) {}
    if (typeof window.setScript === 'function') {
      window.setScript(LANG_TO_SCRIPT[lang] || 'devanagari');
    }
    if (typeof window.closeModal === 'function') window.closeModal('onboardingModal');
  };

  window.dgeSkipOnboarding = function () {
    try { localStorage.setItem(ONBOARDED_KEY, '1'); } catch (e) {}
    // Skipping is an answer too. Asking a signed-in reader again on their
    // next device, because they declined once, is the same nuisance.
    rememberOnProfile({});
    if (typeof window.closeModal === 'function') window.closeModal('onboardingModal');
  };

  function localDone() {
    try { return !!localStorage.getItem(ONBOARDED_KEY); } catch (e) { return true; }
  }

  function decide() {
    if (signedIn()) {
      // Their account is the record. A browser that has answered before but
      // is new to THIS account still asks, which is right -- it is the
      // account's first time, and the answer then follows the account.
      if (profileSaysDone()) return;
    } else if (localDone()) {
      return;
    }
    if (typeof window.openModal === 'function') window.openModal('onboardingModal');
  }

  var decided = false;
  function decideOnce() {
    if (decided) return;
    decided = true;
    decide();
  }

  function boot() {
    wire();
    // Sign-in is restored asynchronously. Deciding at DOMContentLoaded would
    // read every returning reader as a guest and ask them again on a browser
    // that had answered -- so wait for auth to settle when auth exists at
    // all, and fall back on a timer so a Firebase that never loads cannot
    // leave the panel permanently unasked.
    var authy = !!(window.AUTH_CONFIG && window.AUTH_CONFIG.enabled);
    if (!authy || window.dgeAuthSettled) { decideOnce(); return; }
    document.addEventListener('dge:auth-settled', decideOnce, { once: true });
    setTimeout(decideOnce, 4000);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
