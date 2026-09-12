// js/corpus-fetch.js — the one place a grantha's data.json is fetched.
//
// THE SWITCH. Two ways to read the corpus live behind this file:
//
//   corpusBase unset (today, and the default)
//       fetch('data/x/y/data.json') — a public static file on Hosting,
//       exactly as the reader has always done. Nothing about this path
//       changes; this module adds one indirection and no behaviour.
//
//   corpusBase set
//       fetch(corpusBase + '/x/y/data.json') with the signed-in reader's
//       Firebase ID token in an Authorization header. That endpoint is the
//       corpusFile Cloud Function, which resolves the caller's stored role,
//       applies the same shelf and gates the reader applies, and streams the
//       file from a PRIVATE bucket. A text the shelf hides is then genuinely
//       unreachable, not merely unlisted.
//
// Everything else in the reader is identical either way, which is the whole
// point: flipping corpusBase in config.js is the entire migration, and
// flipping it back is the entire rollback.
//
// Why this is a real change and not just paranoia: every gate in this app so
// far has been UI-level, and role-access.js says so in its own header. The
// data.json is a public static asset, so "hidden" has meant "not shown to
// someone who does not already know the URL". For the go-live shelf that was
// accepted deliberately. For anything genuinely restricted it is not enough,
// and this is the switch that makes it enough.
window.DGE_VERSIONS = window.DGE_VERSIONS || {};
window.DGE_VERSIONS['corpus-fetch.js'] = 'v1.0 (11 Sep 2026: corpusBase switch — static files or the authenticated proxy)';

(function () {
  'use strict';

  function corpusBase() {
    const c = window.appConfig || {};
    const b = c.corpusBase;
    return (typeof b === 'string' && b.trim()) ? b.trim().replace(/\/+$/, '') : '';
  }

  /** True when corpus reads are going through the authenticated proxy. */
  window.dgeCorpusProxyOn = function () { return !!corpusBase(); };

  /**
   * The corpus-relative object path ("x/y/data.json") behind whatever the
   * reader is holding — a fetch-relative "data/x/y/data.json", a repo-rooted
   * "data/x/y/data.json", or a full CDN URL under kavyaDataBase. The
   * proxy names files by their on-disk path under data/, so all three
   * have to come back to the same string.
   */
  window.dgeCorpusObjectPath = function (url) {
    let u = String(url || '').trim();
    if (!u) return '';
    const kavya = (window.KAVYA_DATA_BASE || '').replace(/\/+$/, '');
    if (kavya && u.indexOf(kavya) === 0) u = u.slice(kavya.length);
    if (/^https?:\/\//i.test(u)) {
      try { u = new URL(u).pathname; } catch (e) { return ''; }
    }
    u = u.split('?')[0].split('#')[0];
    u = u.replace(/^\/+/, '').replace(/^dge\//, '');
    // jsDelivr's own routing prefix: gh/<owner>/<repo>@<commit>/ . Stripped
    // by shape rather than by comparing against KAVYA_DATA_BASE, because that
    // config value carries a commit pin that MOVES — a URL minted before a
    // re-pin must not stop resolving just because the prefix no longer
    // matches character for character.
    u = u.replace(/^gh\/[^/]+\/[^/]+@[^/]+\//, '');
    // A CDN URL carries the repo and commit before the path
    // (…/gh/owner/repo@sha/data/x/y/data.json), so keep from the first
    // "data/" SEGMENT on. Segment, not substring: a grantha folder named
    // metadata/ or devadatta/ contains the letters "data/" and truncating
    // there would silently ask the proxy for a different text.
    const m = u.match(/(?:^|\/)data\/(.*)$/);
    return m ? m[1] : u;
  };

  /**
   * The reader's ID token, or null when nobody is signed in.
   *
   * Signed out is a normal, supported state — the library is public and the
   * shelf is what narrows it — so this resolves to null rather than waiting
   * or throwing. It also refuses to wait on a Firebase SDK that is not there:
   * accounts can be switched off entirely (AUTH_CONFIG.enabled false) and the
   * corpus must still load.
   */
  async function idToken() {
    try {
      if (!window.AUTH_CONFIG || !window.AUTH_CONFIG.enabled) return null;
      if (typeof window.dgeEnsureFirebaseSdk === 'function') await window.dgeEnsureFirebaseSdk();
      if (typeof firebase === 'undefined' || !firebase.apps || !firebase.apps.length) return null;
      const user = firebase.auth().currentUser;
      if (!user) return null;
      return await user.getIdToken();
    } catch (e) {
      // A token we could not mint is the same as no token: the visitor gets
      // whatever is public. Failing the whole fetch here would take the
      // public library down over a signed-in reader's expired session.
      console.warn('[Corpus] no ID token, continuing as a visitor:', e && e.message);
      return null;
    }
  }

  /**
   * The same token, for anything else that calls one of our own functions
   * (book-builder.js's one-tap PDF is the first). Shared rather than copied
   * so there is one answer to "how does this app get an ID token", and one
   * place to change it.
   */
  window.dgeIdTokenForApi = idToken;

  /**
   * Fetch a grantha dataset. Returns a Response, so callers keep their own
   * res.ok / res.json() handling and their own retries.
   *
   * `bust` (default true) is the cache-buster the static path has always
   * used. The proxy does not get one: its responses are ETagged and marked
   * private, so a conditional request is both fresher and cheaper than a URL
   * the browser has never seen.
   */
  window.dgeFetchCorpus = async function (url, opts) {
    const options = opts || {};
    const base = corpusBase();
    if (!base) {
      const bust = options.bust === false ? '' : ((String(url).indexOf('?') >= 0 ? '&' : '?') + 't=' + Date.now());
      return fetch(url + bust, options.init || {});
    }
    const objectPath = window.dgeCorpusObjectPath(url);
    if (!objectPath) throw new Error('Not a corpus path: ' + url);
    const init = Object.assign({}, options.init || {});
    const headers = new Headers(init.headers || {});
    const token = await idToken();
    if (token) headers.set('Authorization', 'Bearer ' + token);
    init.headers = headers;
    return fetch(base + '/' + objectPath, init);
  };
})();
