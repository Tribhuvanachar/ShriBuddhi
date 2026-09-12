// DGE Module: onboarding.js
// First-visit name + language preference (Issue 27). Shown once per
// browser; "Skip" always available so it never blocks entry. The language
// choice is the one global preference read by:
//   - transliteration.js's setScript(), for the default display script
//   - ai.js's acharyaSystemPrompt, for the main reader's Ask Acharya replies
//   - ashtadhyayi.js's aiLang, for that page's own separate Gemini prompt
// Scope note: this does NOT translate menu/heading UI text or change sort
// ordering (e.g. Kannada collation) — see dge/PENDING.md for why those are
// deferred rather than guessed at.

window.DGE_VERSIONS = window.DGE_VERSIONS || {};
window.DGE_VERSIONS['onboarding.js'] = 'v1.0';

(function () {
  "use strict";
  var ONBOARDED_KEY = 'dge_onboarded';
  var NAME_KEY = 'dge_user_name';
  var LANG_KEY = 'dge_lang_pref';

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
    } catch (e) {}
    if (typeof window.setScript === 'function') {
      window.setScript(LANG_TO_SCRIPT[lang] || 'devanagari');
    }
    if (typeof window.closeModal === 'function') window.closeModal('onboardingModal');
  };

  window.dgeSkipOnboarding = function () {
    try { localStorage.setItem(ONBOARDED_KEY, '1'); } catch (e) {}
    if (typeof window.closeModal === 'function') window.closeModal('onboardingModal');
  };

  function boot() {
    wire();
    var already;
    try { already = localStorage.getItem(ONBOARDED_KEY); } catch (e) { already = '1'; }
    if (already) return;
    if (typeof window.openModal === 'function') window.openModal('onboardingModal');
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
