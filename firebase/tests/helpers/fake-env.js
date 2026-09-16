// fake-env.js — loads js/user-auth.js in a sandbox with a stubbed
// Firebase SDK and a minimal DOM.
//
// user-auth.js is a classic browser script that attaches to `window`, so
// it can be evaluated in a vm context with hand-built globals. That is
// enough to exercise the parts that have real logic — transport routing,
// what a new profile is created with, the OTP flows, consent writes, and
// the error paths — none of which need a real Firebase project.
//
// What this deliberately does NOT test: whether Firebase's own APIs
// behave as documented. The stub asserts our calls are shaped correctly;
// only a live project can confirm Google accepts them.
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const AUTH_JS = path.resolve(__dirname, '../../../js/user-auth.js');

/** A DOM element stub that records what the code under test does to it. */
function fakeElement(id) {
  return { id, style: {}, textContent: '', checked: false, value: '' };
}

/**
 * Minimal DOM.
 *
 * `head.appendChild` simulates the browser fetching an injected <script>:
 * it records the URL, and then either fires onload (making the fake
 * `firebase` global appear, as the real SDK would) or fires onerror when
 * the test asked for a failing network. Without this, the lazy loader
 * would await an onload that never comes and the test would hang.
 */
function fakeDocument(ids, opts = {}) {
  const elements = new Map(ids.map(id => [id, fakeElement(id)]));
  const listeners = {};
  const loadedScripts = [];

  const head = {
    appendChild: (node) => {
      loadedScripts.push(node.src);
      // Asynchronous, like a real network fetch — so ordering bugs that
      // depend on the load being synchronous cannot hide.
      setTimeout(() => {
        if (opts.scriptLoadFails) node.onerror && node.onerror(new Error('network'));
        else {
          if (opts.onScriptLoaded) opts.onScriptLoaded(node.src);
          node.onload && node.onload();
        }
      }, 0);
      return node;
    }
  };

  return {
    _elements: elements,
    _loadedScripts: loadedScripts,
    head,
    documentElement: head,
    getElementById: (id) => elements.get(id) || null,
    addEventListener: (evt, fn) => { (listeners[evt] = listeners[evt] || []).push(fn); },
    _fire: async (evt) => { for (const fn of (listeners[evt] || [])) await fn(); },
    createElement: (tag) => (tag === 'script'
      ? { tagName: 'SCRIPT', src: '', async: true, onload: null, onerror: null }
      : { textContent: '', innerHTML: '' })
  };
}

/**
 * Builds a stub Firebase compat SDK.
 *
 * `calls` records everything the code under test asked Firebase to do,
 * so a test can assert on the request rather than only the outcome.
 */
function fakeFirebase(opts = {}) {
  const calls = {
    signInWithPopup: [],
    signInWithCustomToken: [],
    signInWithPhoneNumber: [],
    callable: [],
    docSet: [],
    docUpdate: [],
    signOut: 0
  };

  const store = new Map(Object.entries(opts.docs || {}));
  let authStateCb = null;

  const SERVER_TS = { __sentinel: 'serverTimestamp' };

  function docRef(collection, id) {
    const key = `${collection}/${id}`;
    return {
      get: async () => {
        if (opts.getThrows) throw new Error(opts.getThrows);
        const data = store.get(key);
        return { exists: data !== undefined, data: () => data };
      },
      set: async (value) => {
        if (opts.setThrows) throw new Error(opts.setThrows);
        calls.docSet.push({ key, value });
        store.set(key, value);
      },
      update: async (patch) => {
        if (opts.updateThrows) throw new Error(opts.updateThrows);
        calls.docUpdate.push({ key, patch });
        store.set(key, Object.assign({}, store.get(key), patch));
      }
    };
  }

  const firebase = {
    initializeApp() { if (opts.initThrows) throw new Error(opts.initThrows); },
    app: () => ({
      functions: (region) => {
        calls.functionsRegion = region;
        return functionsObj;
      }
    }),
    auth: () => authObj,
    firestore: Object.assign(() => firestoreObj, {
      FieldValue: { serverTimestamp: () => SERVER_TS, delete: () => ({ __sentinel: 'delete' }) }
    }),
    functions: () => functionsObj
  };

  const authObj = {
    signInWithPopup: async (provider) => {
      calls.signInWithPopup.push(provider);
      if (opts.googleError) throw opts.googleError;
      return { user: { uid: 'u1' } };
    },
    signInWithCustomToken: async (token) => {
      calls.signInWithCustomToken.push(token);
      if (opts.customTokenError) throw opts.customTokenError;
      return { user: { uid: 'phone_abc' } };
    },
    signInWithPhoneNumber: async (phone, verifier) => {
      calls.signInWithPhoneNumber.push({ phone, verifier });
      // Read once: a test may expose this as a getter that varies per
      // call (to simulate "fails, then succeeds"), and reading it twice
      // would consume two turns of that sequence.
      const smsError = opts.smsError;
      if (smsError) throw smsError;
      return {
        confirm: async (code) => {
          if (opts.confirmError) throw opts.confirmError;
          return { user: { uid: 'phone_sms' } };
        }
      };
    },
    signOut: async () => { calls.signOut++; },
    onAuthStateChanged: (cb) => { authStateCb = cb; }
  };

  firebase.auth.GoogleAuthProvider = function () { this.providerId = 'google.com'; };
  firebase.auth.RecaptchaVerifier = function (containerId, params) {
    if (opts.recaptchaThrows) throw new Error(opts.recaptchaThrows);
    this.containerId = containerId;
    this.params = params;
  };

  const firestoreObj = {
    collection: (name) => ({ doc: (id) => docRef(name, id) })
  };

  const functionsObj = {
    httpsCallable: (name) => async (payload) => {
      calls.callable.push({ name, payload });
      const handler = (opts.callables || {})[name];
      if (!handler) throw new Error(`no stub for callable "${name}"`);
      return handler(payload);
    }
  };

  return {
    firebase,
    calls,
    store,
    SERVER_TS,
    fireAuthState: async (user) => { if (authStateCb) await authStateCb(user); },
    hasAuthListener: () => authStateCb !== null
  };
}

const DOM_IDS = [
  'accountSignedOut', 'accountSignedIn', 'accountName', 'accountRole',
  'accountBtn', 'phoneSignInSection', 'recaptchaContainer',
  'phoneOtpChannelLabel', 'whatsappOptInRow', 'whatsappOptInCheckbox'
];

/**
 * Loads user-auth.js into a fresh sandbox.
 * @returns the sandbox's window plus the stub handles and captured toasts.
 */
function loadAuth({ authConfig = {}, firebaseOpts = {}, withFirebase = true, scriptLoadFails = false } = {}) {
  const fb = fakeFirebase(firebaseOpts);
  const toasts = [];
  let sandbox;

  const doc = fakeDocument(DOM_IDS, {
    scriptLoadFails,
    // The SDK global only exists once a script has "loaded" — which is
    // exactly the property the lazy-loading change is about.
    onScriptLoaded: () => { if (withFirebase) sandbox.firebase = fb.firebase; }
  });

  const windowObj = {
    AUTH_CONFIG: Object.assign({
      enabled: true,
      enableGoogleSignIn: true,
      enablePhoneAuth: false,
      phoneOtpProvider: 'firebase',
      functionsRegion: 'asia-south1',
      enableWhatsappBroadcasts: false,
      defaultRole: 'basic',
      roles: ['basic', 'subscriber', 'sponsor', 'admin', 'superadmin', 'special']
    }, authConfig),
    FIREBASE_CONFIG: { apiKey: 'fake', projectId: 'fake' },
    DGE_VERSIONS: {}
  };

  sandbox = {
    window: windowObj,
    document: doc,
    console: { log() {}, error() {}, warn() {} },
    showToast: (m) => toasts.push(m),
    setTimeout,
    clearTimeout,
    Promise
  };
  // NOTE: `firebase` is deliberately NOT pre-set. It appears only when a
  // script "loads" (see onScriptLoaded above), mirroring the real page,
  // where nothing defines that global until the SDK is fetched.

  // The script assigns to bare `window.x` and reads bare `firebase`, so
  // the sandbox's global object must BE the window-ish object for those
  // to resolve. Aliasing window onto the global keeps both forms working.
  const context = vm.createContext(sandbox);
  vm.runInContext('var window = this.window; var document = this.document;', context);
  vm.runInContext(fs.readFileSync(AUTH_JS, 'utf8'), context, { filename: 'user-auth.js' });

  return {
    window: windowObj,
    document: doc,
    fb,
    toasts,
    scripts: doc._loadedScripts,
    fireReady: () => doc._fire('DOMContentLoaded')
  };
}

module.exports = { loadAuth, fakeFirebase, fakeDocument, DOM_IDS };
