// dge/js/user-auth.js — Firebase-backed user accounts, roles & consent.
// See FIREBASE_SETUP.md for the console steps that have to happen outside
// this codebase first, and config.js's FIREBASE_CONFIG / AUTH_CONFIG for
// the switches this file reads.
//
// Deliberately inert whenever AUTH_CONFIG.enabled is false (the shipped
// default) — no Firebase network calls, no Account button shown, nothing
// in this file runs beyond the safety check at the bottom. Safe to ship
// on any deployment that hasn't gone through Firebase setup yet.
//
// Phone sign-in routes through one of three transports (see
// AUTH_CONFIG.phoneOtpProvider):
//   'firebase'  — Firebase's own SMS. No backend, ~$0.01/verification.
//   'whatsapp'  — WhatsApp Cloud API via our Cloud Functions, ~6x cheaper.
//   'msg91'     — India SMS gateway via the same Cloud Functions.
// The last two share one backend and one code path here; they differ only
// in which channel the Cloud Function hands the code to.
window.DGE_VERSIONS = window.DGE_VERSIONS || {};
window.DGE_VERSIONS['user-auth.js'] = 'v2.1 (Google + phone OTP over SMS/WhatsApp/MSG91, WhatsApp consent, lazy SDK)';

window.dgeCurrentUser = null;      // Firebase Auth user object, or null
window.dgeCurrentUserRole = null;  // resolved role string, or null
window.dgeCurrentUserProfile = null; // cached Firestore profile doc

let dgeAuth = null;
let dgeDb = null;
let dgeFunctions = null;
let dgeRecaptchaVerifier = null;   // firebase-SMS transport only
let dgeConfirmationResult = null;  // firebase-SMS transport only
let dgePendingPhone = null;        // whatsapp/msg91 transports
let dgeSdkPromise = null;          // in-flight (or settled) SDK load

const DGE_FIREBASE_SDK_VERSION = '12.17.1';

// --- Lazy SDK loading -------------------------------------------------
// The compat SDK is several hundred KB. It used to load from four static
// <script> tags in index.html, on every page view, for every visitor —
// including the overwhelming majority for whom AUTH_CONFIG.enabled is
// false and none of it ever runs. It is now fetched here, only when the
// feature is actually switched on, and firestore/functions only when the
// configuration actually needs them.

function dgeLoadScript(src) {
  return new Promise((resolve, reject) => {
    const el = document.createElement('script');
    el.src = src;
    // Order matters — firebase-app must finish before the others attach
    // themselves to it — and these are loaded sequentially below, so
    // async is off to keep behaviour predictable if that ever changes.
    el.async = false;
    el.onload = () => resolve(src);
    el.onerror = () => reject(new Error('Could not load ' + src));
    (document.head || document.documentElement).appendChild(el);
  });
}

/** Which SDK bundles this deployment's configuration actually needs. */
function dgeRequiredSdkModules(cfg) {
  const modules = ['firebase-app-compat.js', 'firebase-auth-compat.js', 'firebase-firestore-compat.js'];
  // Callable functions are only used by the transports that route an OTP
  // through our own backend.
  const provider = cfg && cfg.phoneOtpProvider;
  if (cfg && cfg.enablePhoneAuth && (provider === 'whatsapp' || provider === 'msg91')) {
    modules.push('firebase-functions-compat.js');
  }
  return modules;
}

/**
 * Loads the SDK once and caches the promise, so concurrent callers share
 * one load rather than racing to inject duplicate script tags.
 */
window.dgeEnsureFirebaseSdk = function() {
  if (dgeSdkPromise) return dgeSdkPromise;
  if (!window.AUTH_CONFIG || !window.AUTH_CONFIG.enabled) return Promise.resolve(false);

  const base = window.AUTH_CONFIG.sdkBase || `https://www.gstatic.com/firebasejs/${DGE_FIREBASE_SDK_VERSION}/`;
  const modules = dgeRequiredSdkModules(window.AUTH_CONFIG);

  dgeSdkPromise = (async () => {
    for (const m of modules) await dgeLoadScript(base + m);
    return typeof firebase !== 'undefined';
  })().catch((e) => {
    console.error('[Auth] Firebase SDK failed to load:', e);
    // Reset so a later attempt (a click after the network recovers) can
    // retry rather than being permanently poisoned by one failure.
    dgeSdkPromise = null;
    return false;
  });

  return dgeSdkPromise;
};

function dgeAuthReady() {
  return !!(window.AUTH_CONFIG && window.AUTH_CONFIG.enabled && typeof firebase !== 'undefined');
}

function dgeToast(msg) {
  if (typeof showToast === 'function') showToast(msg);
  else console.log('[Auth]', msg);
}

function dgeInitFirebase() {
  if (!dgeAuthReady() || dgeAuth) return dgeAuth;
  try {
    firebase.initializeApp(window.FIREBASE_CONFIG);
    dgeAuth = firebase.auth();
    dgeDb = firebase.firestore();
    // Callable functions are only needed by the whatsapp/msg91
    // transports; guarded so a deployment that didn't load the functions
    // SDK still gets working Google sign-in rather than a hard failure.
    if (typeof firebase.functions === 'function') {
      const region = (window.AUTH_CONFIG && window.AUTH_CONFIG.functionsRegion) || 'asia-south1';
      dgeFunctions = firebase.app().functions(region);
    }
  } catch (e) {
    console.error('[Auth] Firebase init failed — check FIREBASE_CONFIG in config.js:', e);
    return null;
  }
  return dgeAuth;
}

/**
 * Which transport should carry the OTP. Split out from the send/verify
 * functions so the routing itself is testable without a Firebase SDK.
 */
window.dgeOtpTransportFor = function(providerId) {
  if (providerId === 'firebase') return 'firebase';
  if (providerId === 'whatsapp' || providerId === 'msg91') return 'functions';
  return null;
};

// Ensures a Firestore profile doc exists for this user, creating one with
// the configured default role on first sign-in ONLY. A returning user's
// role — possibly changed by a superadmin since their last visit via
// user-roles.js — is authoritative and must never be reset here; this
// only ever touches lastLoginAt on an existing doc.
async function dgeEnsureUserProfile(user) {
  if (!dgeDb || !user) return null;
  const ref = dgeDb.collection('users').doc(user.uid);
  const snap = await ref.get();
  if (!snap.exists) {
    const profile = {
      displayName: user.displayName || '',
      // 7 Sep 2026 (lead's ask): only a VERIFIED email is ever stored. Google
      // sign-in arrives verified; a phone-OTP account has none; anything
      // else stays '' until Firebase says emailVerified. firestore.rules
      // enforces the same (emailOk), so a tampered client cannot write one.
      email: dgeVerifiedEmail(user),
      emailVerified: !!(user.emailVerified && user.email),
      phoneNumber: user.phoneNumber || '',
      // Must be 'basic' — the security rules reject a profile created
      // with any other role, which is what stops anyone handing
      // themselves elevated access on first sign-in.
      role: 'basic',
      // Signing in is not consent to be messaged on WhatsApp. This stays
      // false until the person explicitly ticks the box; the rules
      // reject a create that tries to set it true.
      whatsappOptIn: false,
      createdAt: firebase.firestore.FieldValue.serverTimestamp(),
      lastLoginAt: firebase.firestore.FieldValue.serverTimestamp()
    };
    await ref.set(profile);
    return profile;
  }
  const patch = { lastLoginAt: firebase.firestore.FieldValue.serverTimestamp() };
  // A returning user whose email became verified since the profile was
  // created (or whose stored email predates the verified-only rule and no
  // longer matches) gets it captured now; never the other way round.
  const verified = dgeVerifiedEmail(user);
  const cur = snap.data() || {};
  if (verified && (cur.email !== verified || cur.emailVerified !== true)) { patch.email = verified; patch.emailVerified = true; }
  await ref.update(patch).catch(() => {});
  return Object.assign({}, cur, patch.email ? { email: patch.email, emailVerified: true } : {});
}

// The email an account may carry: the provider's address, only when the
// provider vouches for it. Exposed for the tests.
function dgeVerifiedEmail(user) {
  return (user && user.emailVerified && user.email) ? String(user.email).trim().toLowerCase() : '';
}
window.dgeVerifiedEmail = dgeVerifiedEmail;

function dgeUpdateAccountUI() {
  const signedOutEl = document.getElementById('accountSignedOut');
  const signedInEl = document.getElementById('accountSignedIn');
  if (!signedOutEl || !signedInEl) return;

  if (window.dgeCurrentUser) {
    signedOutEl.style.display = 'none';
    signedInEl.style.display = 'block';
    const nameEl = document.getElementById('accountName');
    const roleEl = document.getElementById('accountRole');
    if (nameEl) nameEl.textContent = window.dgeCurrentUser.displayName || window.dgeCurrentUser.phoneNumber || window.dgeCurrentUser.email || 'Signed in';
    if (roleEl) roleEl.textContent = window.dgeCurrentUserRole || 'basic';

    // Device access vs account role. A person holding the 🔑 passkeys sees
    // every admin tool but is still 'basic' to Firestore, which refuses
    // their writes -- the lead hit exactly this and had no way to tell the
    // two apart ("I have logged in as admin and superadmin, yet my account
    // shows I am a normal user"). Both are named here, and where they
    // disagree the one-time fix is spelled out rather than left to a doc.
    const devEl = document.getElementById('accountDeviceAccess');
    const noteEl = document.getElementById('accountRoleNote');
    let dev = [];
    try {
      if (localStorage.getItem('is_superadmin') === 'true') dev.push('super admin');
      else if (localStorage.getItem('acharyaAuthorized') === 'true') dev.push('admin');
    } catch (e) { /* private mode */ }
    if (devEl) devEl.textContent = dev.length ? dev.join(', ') + ' access (🔑 passkey)' : 'reader';
    const role = window.dgeCurrentUserRole || 'basic';
    const needsBootstrap = dev.length && role !== 'superadmin' && role !== 'admin';
    if (noteEl) {
      if (needsBootstrap && typeof window.dgeSuperadminBootstrapHtml === 'function') {
        noteEl.innerHTML = window.dgeSuperadminBootstrapHtml({
          uid: window.dgeCurrentUser.uid, email: window.dgeCurrentUser.email
        });
        noteEl.style.display = 'block';
      } else {
        noteEl.style.display = 'none';
        noteEl.innerHTML = '';
      }
    }

    // WhatsApp consent row — only meaningful once we have a number to
    // message, so it stays hidden for an email-only account.
    const waRow = document.getElementById('whatsappOptInRow');
    const waBox = document.getElementById('whatsappOptInCheckbox');
    const hasPhone = !!(window.dgeCurrentUserProfile && window.dgeCurrentUserProfile.phoneNumber);
    if (waRow) waRow.style.display = (hasPhone && window.AUTH_CONFIG.enableWhatsappBroadcasts) ? 'flex' : 'none';
    if (waBox) waBox.checked = !!(window.dgeCurrentUserProfile && window.dgeCurrentUserProfile.whatsappOptIn);
  } else {
    signedOutEl.style.display = 'block';
    signedInEl.style.display = 'none';
  }
}

window.openAccountModal = function() {
  dgeUpdateAccountUI();
  if (typeof openModal === 'function') openModal('accountModal');
};

window.dgeSignInWithGoogle = async function() {
  if (!window.AUTH_CONFIG || !window.AUTH_CONFIG.enabled) { dgeToast('Accounts are not set up yet on this deployment.'); return; }
  // Normally already loaded by the startup handler; awaited here so a
  // click that lands mid-load waits rather than failing.
  await window.dgeEnsureFirebaseSdk();
  if (!dgeAuthReady()) { dgeToast('Could not reach the sign-in service. Check your connection and try again.'); return; }
  if (!dgeAuth) dgeInitFirebase();
  if (!dgeAuth) return;
  try {
    const provider = new firebase.auth.GoogleAuthProvider();
    await dgeAuth.signInWithPopup(provider);
    // onAuthStateChanged below picks up the result; the vandana is asked afresh at every sign-in.
    dgeVandanaAfterSignIn();
  } catch (e) {
    console.error('[Auth] Google sign-in failed:', e);
    // A popup the user themselves dismissed is not an error worth
    // shouting about.
    if (e.code === 'auth/popup-closed-by-user' || e.code === 'auth/cancelled-popup-request') return;
    dgeToast('Sign-in failed: ' + (e.message || e));
  }
};

window.dgeSignOut = async function() {
  if (!dgeAuth) return;
  try {
    await dgeAuth.signOut();
    window.dgeCurrentUserProfile = null;
    dgeToast('Signed out.');
  } catch (e) {
    console.error('[Auth] Sign-out failed:', e);
  }
};

// --- Phone OTP -------------------------------------------------------

window.dgeSendPhoneOtp = async function(phoneNumberE164) {
  if (!window.AUTH_CONFIG || !window.AUTH_CONFIG.enabled || !window.AUTH_CONFIG.enablePhoneAuth) {
    dgeToast('Phone sign-in is not enabled on this deployment.');
    return false;
  }
  await window.dgeEnsureFirebaseSdk();
  if (!dgeAuthReady()) {
    dgeToast('Could not reach the sign-in service. Check your connection and try again.');
    return false;
  }
  if (!dgeAuth) dgeInitFirebase();
  if (!dgeAuth) return false;

  const providerId = window.AUTH_CONFIG.phoneOtpProvider;
  const transport = window.dgeOtpTransportFor(providerId);
  if (!transport) {
    dgeToast(`Unknown OTP provider "${providerId}" — check AUTH_CONFIG in config.js.`);
    return false;
  }

  if (transport === 'firebase') return dgeSendOtpViaFirebase(phoneNumberE164);
  return dgeSendOtpViaFunctions(phoneNumberE164);
};

async function dgeSendOtpViaFirebase(phoneNumberE164) {
  try {
    if (!dgeRecaptchaVerifier) {
      dgeRecaptchaVerifier = new firebase.auth.RecaptchaVerifier('recaptchaContainer', { size: 'invisible' });
    }
    dgeConfirmationResult = await dgeAuth.signInWithPhoneNumber(phoneNumberE164, dgeRecaptchaVerifier);
    return true;
  } catch (e) {
    console.error('[Auth] Sending OTP failed:', e);
    dgeToast('Could not send code: ' + (e.message || e));
    // A spent reCAPTCHA cannot be reused; drop it so the next attempt
    // builds a fresh one instead of failing identically forever.
    dgeRecaptchaVerifier = null;
    return false;
  }
}

async function dgeSendOtpViaFunctions(phoneNumberE164) {
  if (!dgeFunctions) {
    dgeToast('Messaging backend is unavailable — the Cloud Functions SDK did not load.');
    return false;
  }
  try {
    const call = dgeFunctions.httpsCallable('sendOtp');
    await call({ phone: phoneNumberE164 });
    // Remembered so verify doesn't depend on the input field still
    // holding the same text the code was actually sent to.
    dgePendingPhone = phoneNumberE164;
    return true;
  } catch (e) {
    console.error('[Auth] Sending OTP failed:', e);
    // Callable errors carry the server's message; it is written to be
    // shown to a person (cooldown seconds, "try again in N minutes").
    dgeToast(e.message || 'Could not send the code.');
    return false;
  }
}

window.dgeConfirmPhoneOtp = async function(code) {
  const providerId = window.AUTH_CONFIG && window.AUTH_CONFIG.phoneOtpProvider;
  const transport = window.dgeOtpTransportFor(providerId);

  if (transport === 'firebase') {
    if (!dgeConfirmationResult) { dgeToast('Request a code first.'); return false; }
    try {
      await dgeConfirmationResult.confirm(code);
      dgeConfirmationResult = null;
      dgeVandanaAfterSignIn();
      return true;
    } catch (e) {
      console.error('[Auth] OTP confirmation failed:', e);
      dgeToast('Incorrect or expired code.');
      return false;
    }
  }

  if (!dgePendingPhone) { dgeToast('Request a code first.'); return false; }
  if (!dgeFunctions) { dgeToast('Messaging backend is unavailable.'); return false; }
  try {
    const call = dgeFunctions.httpsCallable('verifyOtp');
    const res = await call({ phone: dgePendingPhone, code });
    const token = res && res.data && res.data.token;
    if (!token) { dgeToast('Verification failed.'); return false; }
    // The custom token is what actually signs the person in — the Cloud
    // Function minted it only after checking the code server-side.
    await dgeAuth.signInWithCustomToken(token);
    dgePendingPhone = null;
    return true;
  } catch (e) {
    console.error('[Auth] OTP confirmation failed:', e);
    dgeToast(e.message || 'Incorrect or expired code.');
    return false;
  }
};

// --- WhatsApp broadcast consent --------------------------------------
// Recorded as a deliberate act by the person themselves. WhatsApp policy
// requires opt-in collected outside WhatsApp, and this checkbox — plus
// the whatsappOptInAt timestamp — is the record of it.
window.dgeSetWhatsappOptIn = async function(optIn) {
  if (!window.dgeCurrentUser || !dgeDb) { dgeToast('Sign in first.'); return false; }
  try {
    const patch = { whatsappOptIn: !!optIn };
    if (optIn) patch.whatsappOptInAt = firebase.firestore.FieldValue.serverTimestamp();
    await dgeDb.collection('users').doc(window.dgeCurrentUser.uid).update(patch);
    if (window.dgeCurrentUserProfile) window.dgeCurrentUserProfile.whatsappOptIn = !!optIn;
    dgeToast(optIn ? 'Subscribed to WhatsApp updates.' : 'Unsubscribed from WhatsApp updates.');
    return true;
  } catch (e) {
    console.error('[Auth] Consent update failed:', e);
    dgeToast('Could not save that preference.');
    // Re-sync the checkbox with what is actually stored, so the UI never
    // claims a preference the database rejected.
    dgeUpdateAccountUI();
    return false;
  }
};

document.addEventListener('DOMContentLoaded', async () => {
  // The cheap check first, before any network work: on a deployment that
  // hasn't done the Firebase setup this returns immediately and not one
  // byte of SDK is fetched.
  if (!window.AUTH_CONFIG || !window.AUTH_CONFIG.enabled) return;

  const loaded = await window.dgeEnsureFirebaseSdk();
  if (!loaded || !dgeAuthReady()) return; // offline or blocked — leave the page as it was
  if (!dgeInitFirebase()) return;

  const accountBtn = document.getElementById('accountBtn');
  if (accountBtn) accountBtn.style.display = 'flex';

  if (window.AUTH_CONFIG.enablePhoneAuth) {
    const phoneSection = document.getElementById('phoneSignInSection');
    if (phoneSection) phoneSection.style.display = 'block';

    // Only Firebase's own SMS transport needs the reCAPTCHA widget; the
    // Cloud-Function transports are protected server-side by the rate
    // limits in otp-core.js instead.
    const recaptcha = document.getElementById('recaptchaContainer');
    if (recaptcha && window.AUTH_CONFIG.phoneOtpProvider !== 'firebase') recaptcha.style.display = 'none';

    const label = document.getElementById('phoneOtpChannelLabel');
    if (label) {
      label.textContent = window.AUTH_CONFIG.phoneOtpProvider === 'whatsapp'
        ? 'We will send a code to your WhatsApp.'
        : 'We will send a code by SMS.';
    }
  }

  dgeAuth.onAuthStateChanged(async (user) => {   // fires on restore too; the sign-in hooks above are the only vandana triggers
    window.dgeCurrentUser = user;
    if (user) {
      // Sign-in must survive a missing profile store: until the Firestore database exists in the
      // console (FIREBASE_SETUP.md §3 step 3) the users/<uid> read/write fails with a permission or
      // "API not enabled" error. The person is still signed in; they just get the default role.
      let profile = null;
      try {
        profile = await dgeEnsureUserProfile(user);
      } catch (e) {
        console.warn('[Auth] signed in, but the profile store is not available yet:', e && e.message);
        dgeToast('Signed in as ' + (user.displayName || user.email || 'user') + '. Profile storage is not set up yet, so roles are unavailable for now.');
      }
      window.dgeCurrentUserProfile = profile;
      window.dgeCurrentUserRole = profile ? profile.role : 'basic';
    } else {
      window.dgeCurrentUserRole = null;
      window.dgeCurrentUserProfile = null;
    }
    dgeBridgeRoleToAdminTools(window.dgeCurrentUserRole);
    dgeUpdateAccountUI();
  });
});

// 8 Sep 2026: a real signed-in admin/superadmin used to see none of the
// admin tools unless they ALSO knew the separate ?superadmin=CODE passkey
// (dge/js/admin-editor.js) — two unrelated systems for "is this an admin"
// that never talked to each other. This bridges the REAL Firestore role
// (enforced server-side by firestore.rules; see callerRole() there) onto
// the same localStorage flags the passkey sets, and re-runs
// dgeRevealAdminTools() so the menu updates live, no reload needed.
//
// A marker (the `_viaSignIn` suffix) tracks which grant came from THIS
// bridge, so signing out of the Firebase account only revokes what
// signing in granted — a passkey entered by hand stays valid until the
// person clears it themselves, same as before this existed.
function dgeBridgeRoleToAdminTools(role) {
  try {
    if (role === 'superadmin') {
      localStorage.setItem('is_superadmin', 'true');
      localStorage.setItem('is_superadmin_viaSignIn', 'true');
    } else if (localStorage.getItem('is_superadmin_viaSignIn') === 'true') {
      localStorage.removeItem('is_superadmin');
      localStorage.removeItem('is_superadmin_viaSignIn');
    }
    if (role === 'admin' || role === 'superadmin') {
      localStorage.setItem('acharyaAuthorized', 'true');
      localStorage.setItem('acharyaAuthorized_viaSignIn', 'true');
    } else if (localStorage.getItem('acharyaAuthorized_viaSignIn') === 'true') {
      localStorage.removeItem('acharyaAuthorized');
      localStorage.removeItem('acharyaAuthorized_viaSignIn');
    }
  } catch (e) { /* localStorage unavailable (private mode, etc.) — admin tools just stay hidden */ }
  if (typeof window.dgeRevealAdminTools === 'function') window.dgeRevealAdminTools();
  if (typeof window.dgeRevealAccessMenu === 'function') window.dgeRevealAccessMenu();
}
window.dgeBridgeRoleToAdminTools = dgeBridgeRoleToAdminTools;

// A fresh sign-in (Google popup or OTP confirmed) pays respects again (7 Sep 2026, the lead: "every time a user
// logs in"): forget today's pass and go through the gate, which brings the person straight back here.
function dgeVandanaAfterSignIn() {
  // The WHOLE body is guarded, not just the URL parse. This runs AFTER a
  // sign-in has already succeeded, from inside the caller's try — so anything
  // that throws here (a page with no guard script, an embedded context with no
  // location) would be caught by the caller and reported to the person as
  // "Incorrect or expired code" or "Sign-in failed", for a sign-in that
  // actually worked. Sending someone back through the gate is a courtesy;
  // it must never be able to fail the thing it follows.
  try {
    try { localStorage.removeItem('dge_vandana_day'); } catch (e) { /* ignore */ }
    try { sessionStorage.removeItem('dge_vandana_passed'); } catch (e) { /* ignore */ }
    var guard = document.querySelector('script[src*="vandana-guard.js"]');
    var gate = new URL('../../index.html', guard ? guard.src : new URL('js/x.js', location.href).href);
    if (gate.pathname === location.pathname) return;
    gate.searchParams.set('next', location.pathname + location.search + location.hash);
    setTimeout(function () { location.href = gate.href; }, 600);
  } catch (e) {
    /* no gate to return to — the sign-in still stands */
  }
}
window.dgeVandanaAfterSignIn = dgeVandanaAfterSignIn;
