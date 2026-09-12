/* =========================================================================
   Guru Vandana guard.

   The vandana lives at the site root, so it only ever greeted people who
   arrived at the front door. A bookmark or a shared deep link into any page
   under dge/ walked straight past it. This bounces such a visitor back to
   the gate, remembers where they were headed, and the gate delivers them
   there once respects have been paid — so closing the bypass costs nobody
   their link.

   Include it as the FIRST script in the <head> of every page under dge/. It
   is deliberately synchronous: it has to decide before the page paints, or
   the visitor sees a flash of the library they have not yet been admitted
   to.

   It fails OPEN, always. Every branch that cannot establish the facts lets
   the visitor through. A guard that traps people out of the library on a
   browser quirk would be far worse than one that occasionally lets someone
   past, and this is a courtesy, not a security control — there is nothing
   secret behind it.
   ========================================================================= */
(function () {
  'use strict';

  // Written by the gate the moment respects are paid. The session key covers
  // this tab; the day key (7 Sep 2026, the lead: "every day afresh, like an
  // attendance") covers the whole device for the calendar day, so coming
  // back from another app a few minutes later — which on a phone is often a
  // brand-new tab session — does not ask again. A sign-in clears both
  // (user-auth.js dgeVandanaAfterSignIn), so respects are paid at each login.
  var PASS_KEY = 'dge_vandana_passed';
  var DAY_KEY = 'dge_vandana_day';
  function today() {
    var d = new Date(), m = d.getMonth() + 1, day = d.getDate();
    return d.getFullYear() + '-' + (m < 10 ? '0' : '') + m + '-' + (day < 10 ? '0' : '') + day;
  }

  var store;
  try {
    store = window.sessionStorage;
    // Probe rather than trust. Safari in private browsing hands back a
    // sessionStorage object whose setItem throws on use. Without this check
    // the guard would bounce that visitor to the gate, the gate would fail
    // to record anything, and the two would volley forever.
    store.setItem('__gv_probe', '1');
    store.removeItem('__gv_probe');
  } catch (e) {
    return;
  }

  if (store.getItem(PASS_KEY)) return;
  try {
    if (window.localStorage && window.localStorage.getItem(DAY_KEY) === today()) {
      store.setItem(PASS_KEY, String(Date.now()));
      return;
    }
  } catch (e) { /* no localStorage: fall back to the per-tab rule */ }

  var self = document.currentScript && document.currentScript.src;
  if (!self) return;

  var gate;
  try {
    // This file sits at <site>/dge/js/, so the gate is two levels up. Derived
    // from the script's own URL rather than written as a path, so the site
    // behaves the same served from a domain root or from a subpath.
    gate = new URL('../../index.html', self);
  } catch (e) {
    return;
  }

  // Never redirect a page to itself.
  if (gate.pathname === location.pathname) return;

  gate.searchParams.set('next', location.pathname + location.search + location.hash);
  location.replace(gate.href);
})();
