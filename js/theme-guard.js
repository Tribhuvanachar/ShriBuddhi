/* =========================================================================
   Theme pre-paint guard.

   restorePrefs() (core.js) applies the visitor's saved theme by adding a
   theme-<name> class to document.body -- but it only runs from inside
   initApp(), which itself only runs after the current grantha's JSON
   content has finished fetching. Until then, body's background (main.css)
   resolves against tokens.css's bare :root default with no theme class
   present at all, so a saved theme other than Vandana flashes in visibly
   once the fetch resolves. Because render.html is the one shell reused
   for every grantha (see dgeGoToGrantha in library.js, which navigates via
   a plain page load, not history.pushState), this flash recurs on every
   grantha/sarga/adhyaya jump, not just first load.

   document.body does not exist yet while <head> is still parsing, but
   document.documentElement (<html>) always does. This script sets the
   theme class there instead, synchronously, before first paint -- and
   tokens.css's per-theme blocks now match html.theme-X as well as
   body.theme-X, so the CSS custom properties are already correct on an
   ancestor by the time body is created and painted, before applyTheme()
   ever touches body's own classList.

   Include it as the SECOND script in <head>, immediately after
   vandana-guard.js (which must stay first). Mirrors restorePrefs()'s exact
   fallback chain (see core.js) so the two can never disagree about which
   theme is active; window.applyTheme (utils.js) mirrors the same class
   onto <html> from then on, so every later theme change stays in sync too.
   ========================================================================= */
(function () {
  'use strict';

  var THEMES = ['vandana', 'traditional'];
  var ALIASES = { minimal: 'traditional', vibrant: 'traditional', darkglass: 'vandana' };   // removed 7 Sep 2026

  var theme;
  try {
    var saved = localStorage.getItem('app_theme');
    if (saved) {
      theme = saved;
    } else {
      // Same one-time migration restorePrefs() performs for a visitor who
      // has the legacy plain dark-mode flag but no app_theme yet.
      theme = 'vandana';   // the default (the legacy app_darkMode flag also landed on a dark theme)
    }
  } catch (e) {
    // Storage inaccessible (private-mode quirk, etc.) -- tokens.css's bare
    // :root default already IS the Vandana palette, so doing nothing here
    // still paints the right colors for that common case.
    return;
  }

  theme = ALIASES[theme] || theme;
  if (THEMES.indexOf(theme) === -1) theme = 'vandana';

  var html = document.documentElement;
  html.classList.add('theme-' + theme);
  html.classList.toggle('dark-mode', theme === 'vandana');
})();
