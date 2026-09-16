// Tests for js/user-auth.js — the client half of sign-in.
//
// Run against a stubbed Firebase SDK (helpers/fake-env.js), so these
// need no credentials. They cover the things that are OUR logic and can
// therefore actually be wrong: which transport a provider routes to,
// what a brand-new profile is created with, whether a failed write
// leaves the UI lying about what was saved, and whether the whole file
// really stays inert when the feature is off.
'use strict';

const { test, describe } = require('node:test');
const assert = require('node:assert/strict');

const { loadAuth } = require('./helpers/fake-env');

describe('inertness when the feature is off', () => {
  test('does nothing at all when AUTH_CONFIG.enabled is false', async () => {
    // The promise this file makes to every deployment that has not gone
    // through Firebase setup: no network calls, no Account button.
    const env = loadAuth({ authConfig: { enabled: false } });
    await env.fireReady();
    assert.equal(env.fb.hasAuthListener(), false, 'must not subscribe to auth state');
    assert.equal(env.document.getElementById('accountBtn').style.display, undefined, 'must not reveal the Account button');
  });

  test('fetches not one byte of SDK when the feature is off', async () => {
    // The reason the SDK is loaded lazily at all: it is several hundred
    // KB, and for every deployment that has not enabled accounts it
    // would be downloaded on every page view and never run.
    const env = loadAuth({ authConfig: { enabled: false } });
    await env.fireReady();
    assert.deepEqual(env.scripts, [], 'no script should be injected while disabled');
  });

  test('does nothing when the Firebase SDK failed to load', async () => {
    const env = loadAuth({ authConfig: { enabled: true }, withFirebase: false });
    await env.fireReady();
    assert.equal(env.document.getElementById('accountBtn').style.display, undefined);
  });

  test('leaves the page alone when the SDK network request fails', async () => {
    // Offline, or gstatic blocked. The reader must carry on working;
    // accounts are the only thing that should be missing.
    const env = loadAuth({ authConfig: { enabled: true }, scriptLoadFails: true });
    await env.fireReady();
    assert.equal(env.document.getElementById('accountBtn').style.display, undefined);
    assert.equal(env.fb.hasAuthListener(), false);
  });

  test('reports rather than throws when sign-in is attempted while disabled', async () => {
    const env = loadAuth({ authConfig: { enabled: false } });
    await env.window.dgeSignInWithGoogle();
    assert.match(env.toasts[0], /not set up/i);
    assert.equal(env.fb.calls.signInWithPopup.length, 0);
  });
});

describe('lazy SDK loading', () => {
  const names = (env) => env.scripts.map(s => s.split('/').pop());

  test('loads app, auth and firestore when enabled', async () => {
    const env = loadAuth({ authConfig: { enabled: true } });
    await env.fireReady();
    assert.deepEqual(names(env), [
      'firebase-app-compat.js',
      'firebase-auth-compat.js',
      'firebase-firestore-compat.js'
    ]);
  });

  test('loads firebase-app FIRST — the rest attach themselves to it', async () => {
    const env = loadAuth({ authConfig: { enabled: true } });
    await env.fireReady();
    assert.equal(names(env)[0], 'firebase-app-compat.js');
  });

  test('does NOT load the functions SDK unless a transport needs it', async () => {
    // Only the whatsapp/msg91 OTP transports call Cloud Functions.
    const off = loadAuth({ authConfig: { enabled: true, enablePhoneAuth: false } });
    await off.fireReady();
    assert.equal(names(off).includes('firebase-functions-compat.js'), false);

    const sms = loadAuth({ authConfig: { enabled: true, enablePhoneAuth: true, phoneOtpProvider: 'firebase' } });
    await sms.fireReady();
    assert.equal(names(sms).includes('firebase-functions-compat.js'), false,
      'Firebase SMS runs client-side and needs no callable functions');
  });

  test('loads the functions SDK for the WhatsApp and MSG91 transports', async () => {
    for (const provider of ['whatsapp', 'msg91']) {
      const env = loadAuth({ authConfig: { enabled: true, enablePhoneAuth: true, phoneOtpProvider: provider } });
      await env.fireReady();
      assert.ok(names(env).includes('firebase-functions-compat.js'), `${provider} needs callable functions`);
    }
  });

  test('fetches from the pinned gstatic version', async () => {
    const env = loadAuth({ authConfig: { enabled: true } });
    await env.fireReady();
    for (const src of env.scripts) {
      assert.match(src, /^https:\/\/www\.gstatic\.com\/firebasejs\/\d+\.\d+\.\d+\//);
    }
  });

  test('honours an overridden SDK base', async () => {
    const env = loadAuth({ authConfig: { enabled: true, sdkBase: 'https://example.test/sdk/' } });
    await env.fireReady();
    assert.ok(env.scripts.every(s => s.startsWith('https://example.test/sdk/')));
  });

  test('loads the SDK once, however many callers ask for it', async () => {
    // Concurrent callers must share one load rather than racing to
    // inject duplicate script tags.
    const env = loadAuth({ authConfig: { enabled: true } });
    await env.fireReady();
    const afterStartup = env.scripts.length;
    await Promise.all([
      env.window.dgeEnsureFirebaseSdk(),
      env.window.dgeEnsureFirebaseSdk(),
      env.window.dgeEnsureFirebaseSdk()
    ]);
    assert.equal(env.scripts.length, afterStartup, 'no duplicate script injections');
  });

  test('a click before the SDK arrives waits instead of failing', async () => {
    // The button is only revealed after startup finishes, but a click
    // that lands mid-load must still work.
    const env = loadAuth({ authConfig: { enabled: true } });
    await env.window.dgeSignInWithGoogle();
    assert.equal(env.fb.calls.signInWithPopup.length, 1);
  });

  test('reports a load failure to the user rather than failing silently', async () => {
    const env = loadAuth({ authConfig: { enabled: true }, scriptLoadFails: true });
    await env.window.dgeSignInWithGoogle();
    assert.match(env.toasts.at(-1), /connection|reach/i);
    assert.equal(env.fb.calls.signInWithPopup.length, 0);
  });

  test('a failed load can be retried once the network recovers', async () => {
    // The promise must not be cached in its rejected state, or the
    // feature stays dead until a page reload.
    const env = loadAuth({ authConfig: { enabled: true }, scriptLoadFails: true });
    await env.window.dgeEnsureFirebaseSdk();
    const afterFirst = env.scripts.length;
    await env.window.dgeEnsureFirebaseSdk();
    assert.ok(env.scripts.length > afterFirst, 'a retry should attempt the fetch again');
  });
});

describe('startup', () => {
  test('reveals the Account button and subscribes to auth state', async () => {
    const env = loadAuth();
    await env.fireReady();
    assert.equal(env.document.getElementById('accountBtn').style.display, 'flex');
    assert.equal(env.fb.hasAuthListener(), true);
  });

  test('shows the phone section only when phone auth is enabled', async () => {
    const off = loadAuth({ authConfig: { enablePhoneAuth: false } });
    await off.fireReady();
    assert.equal(off.document.getElementById('phoneSignInSection').style.display, undefined);

    const on = loadAuth({ authConfig: { enablePhoneAuth: true } });
    await on.fireReady();
    assert.equal(on.document.getElementById('phoneSignInSection').style.display, 'block');
  });

  test('hides the reCAPTCHA slot for transports that do not use it', async () => {
    const wa = loadAuth({ authConfig: { enablePhoneAuth: true, phoneOtpProvider: 'whatsapp' } });
    await wa.fireReady();
    assert.equal(wa.document.getElementById('recaptchaContainer').style.display, 'none');

    const sms = loadAuth({ authConfig: { enablePhoneAuth: true, phoneOtpProvider: 'firebase' } });
    await sms.fireReady();
    assert.notEqual(sms.document.getElementById('recaptchaContainer').style.display, 'none');
  });

  test('tells the user which channel the code will arrive on', async () => {
    const wa = loadAuth({ authConfig: { enablePhoneAuth: true, phoneOtpProvider: 'whatsapp' } });
    await wa.fireReady();
    assert.match(wa.document.getElementById('phoneOtpChannelLabel').textContent, /WhatsApp/);

    const sms = loadAuth({ authConfig: { enablePhoneAuth: true, phoneOtpProvider: 'msg91' } });
    await sms.fireReady();
    assert.match(sms.document.getElementById('phoneOtpChannelLabel').textContent, /SMS/);
  });

  test('builds callables against the configured region', async () => {
    const env = loadAuth({ authConfig: { functionsRegion: 'europe-west1' } });
    await env.fireReady();
    assert.equal(env.fb.calls.functionsRegion, 'europe-west1');
  });
});

describe('dgeOtpTransportFor', () => {
  test('routes each known provider to its transport', () => {
    const env = loadAuth();
    assert.equal(env.window.dgeOtpTransportFor('firebase'), 'firebase');
    assert.equal(env.window.dgeOtpTransportFor('whatsapp'), 'functions');
    assert.equal(env.window.dgeOtpTransportFor('msg91'), 'functions');
  });

  test('returns null for an unknown provider rather than guessing', () => {
    const env = loadAuth();
    assert.equal(env.window.dgeOtpTransportFor('twilio'), null);
    assert.equal(env.window.dgeOtpTransportFor(''), null);
    assert.equal(env.window.dgeOtpTransportFor(undefined), null);
  });
});

describe('Google sign-in', () => {
  test('opens the Google popup', async () => {
    const env = loadAuth();
    await env.fireReady();
    await env.window.dgeSignInWithGoogle();
    assert.equal(env.fb.calls.signInWithPopup.length, 1);
    assert.equal(env.fb.calls.signInWithPopup[0].providerId, 'google.com');
  });

  test('stays quiet when the user simply closed the popup', async () => {
    // Shouting "Sign-in failed" at someone who changed their mind is
    // noise, not information.
    const err = new Error('popup closed');
    err.code = 'auth/popup-closed-by-user';
    const env = loadAuth({ firebaseOpts: { googleError: err } });
    await env.fireReady();
    await env.window.dgeSignInWithGoogle();
    assert.deepEqual(env.toasts, []);
  });

  test('reports a genuine sign-in failure', async () => {
    const err = new Error('network unreachable');
    err.code = 'auth/network-request-failed';
    const env = loadAuth({ firebaseOpts: { googleError: err } });
    await env.fireReady();
    await env.window.dgeSignInWithGoogle();
    assert.match(env.toasts[0], /Sign-in failed/);
  });
});

describe('profile creation on first sign-in', () => {
  test('creates a new profile as basic, with consent off', async () => {
    // Both defaults are enforced by the security rules too; this asserts
    // the client does not even try to send anything else, so a rule
    // rejection never becomes the first line of defence.
    const env = loadAuth();
    await env.fireReady();
    await env.fb.fireAuthState({ uid: 'newuser', displayName: 'A', email: 'a@x.com', phoneNumber: null });

    assert.equal(env.fb.calls.docSet.length, 1);
    const written = env.fb.calls.docSet[0];
    assert.equal(written.key, 'users/newuser');
    assert.equal(written.value.role, 'basic');
    assert.equal(written.value.whatsappOptIn, false);
    assert.equal(env.window.dgeCurrentUserRole, 'basic');
  });

  test('stores the email only when the provider verified it', async () => {
    // Google sign-in arrives with emailVerified true; the address is kept.
    let env = loadAuth();
    await env.fireReady();
    await env.fb.fireAuthState({ uid: 'g', displayName: 'G', email: 'G@X.com', emailVerified: true });
    assert.equal(env.fb.calls.docSet[0].value.email, 'g@x.com');
    assert.equal(env.fb.calls.docSet[0].value.emailVerified, true);
    // An unverified address is never written, whatever the provider passed.
    env = loadAuth();
    await env.fireReady();
    await env.fb.fireAuthState({ uid: 'u', displayName: 'U', email: 'u@x.com', emailVerified: false });
    assert.equal(env.fb.calls.docSet[0].value.email, '');
    assert.equal(env.fb.calls.docSet[0].value.emailVerified, false);
  });

  test('captures a newly verified email on a returning user, and only then', async () => {
    let env = loadAuth({ firebaseOpts: { docs: { 'users/r': { role: 'basic', email: '' } } } });
    await env.fireReady();
    await env.fb.fireAuthState({ uid: 'r', displayName: 'R', email: 'r@x.com', emailVerified: true });
    assert.equal(env.fb.calls.docSet.length, 0);
    assert.deepEqual(Object.keys(env.fb.calls.docUpdate[0].patch).sort(), ['email', 'emailVerified', 'lastLoginAt']);
    assert.equal(env.fb.calls.docUpdate[0].patch.email, 'r@x.com');
    // Unverified: the profile is not touched beyond lastLoginAt.
    env = loadAuth({ firebaseOpts: { docs: { 'users/r': { role: 'basic', email: '' } } } });
    await env.fireReady();
    await env.fb.fireAuthState({ uid: 'r', displayName: 'R', email: 'r@x.com', emailVerified: false });
    assert.deepEqual(Object.keys(env.fb.calls.docUpdate[0].patch), ['lastLoginAt']);
  });

  test('ignores a tampered defaultRole in config', async () => {
    // config.js is client-side and editable by anyone with devtools; the
    // create path must not read a role from it.
    const env = loadAuth({ authConfig: { defaultRole: 'superadmin' } });
    await env.fireReady();
    await env.fb.fireAuthState({ uid: 'newuser', displayName: 'A', email: 'a@x.com' });
    assert.equal(env.fb.calls.docSet[0].value.role, 'basic');
  });

  test('never resets a returning user\'s role', async () => {
    // A superadmin promoted since the last visit must stay promoted.
    const env = loadAuth({ firebaseOpts: { docs: { 'users/known': { role: 'superadmin', displayName: 'S' } } } });
    await env.fireReady();
    await env.fb.fireAuthState({ uid: 'known', displayName: 'S' });

    assert.equal(env.fb.calls.docSet.length, 0, 'must not overwrite an existing profile');
    assert.equal(env.window.dgeCurrentUserRole, 'superadmin');
    assert.deepEqual(Object.keys(env.fb.calls.docUpdate[0].patch), ['lastLoginAt']);
  });

  test('clears cached identity on sign-out', async () => {
    const env = loadAuth({ firebaseOpts: { docs: { 'users/known': { role: 'admin' } } } });
    await env.fireReady();
    await env.fb.fireAuthState({ uid: 'known' });
    assert.equal(env.window.dgeCurrentUserRole, 'admin');

    await env.fb.fireAuthState(null);
    assert.equal(env.window.dgeCurrentUserRole, null);
    assert.equal(env.window.dgeCurrentUserProfile, null);
  });
});

describe('phone OTP — Firebase SMS transport', () => {
  const cfg = { enablePhoneAuth: true, phoneOtpProvider: 'firebase' };

  test('sends via signInWithPhoneNumber with a reCAPTCHA verifier', async () => {
    const env = loadAuth({ authConfig: cfg });
    await env.fireReady();
    const ok = await env.window.dgeSendPhoneOtp('+919876543210');
    assert.equal(ok, true);
    assert.equal(env.fb.calls.signInWithPhoneNumber[0].phone, '+919876543210');
    assert.equal(env.fb.calls.signInWithPhoneNumber[0].verifier.params.size, 'invisible');
    assert.equal(env.fb.calls.callable.length, 0, 'must not call Cloud Functions on this transport');
  });

  test('confirms the code through the confirmation result', async () => {
    const env = loadAuth({ authConfig: cfg });
    await env.fireReady();
    await env.window.dgeSendPhoneOtp('+919876543210');
    assert.equal(await env.window.dgeConfirmPhoneOtp('123456'), true);
  });

  test('refuses to verify before a code was requested', async () => {
    const env = loadAuth({ authConfig: cfg });
    await env.fireReady();
    assert.equal(await env.window.dgeConfirmPhoneOtp('123456'), false);
    assert.match(env.toasts[0], /Request a code first/);
  });

  test('reports a wrong code without signing anyone in', async () => {
    const env = loadAuth({ authConfig: cfg, firebaseOpts: { confirmError: new Error('invalid code') } });
    await env.fireReady();
    await env.window.dgeSendPhoneOtp('+919876543210');
    assert.equal(await env.window.dgeConfirmPhoneOtp('000000'), false);
    assert.match(env.toasts.at(-1), /Incorrect or expired/);
  });

  test('discards a spent reCAPTCHA so a retry can succeed', async () => {
    // A used verifier cannot be reused; keeping it would make every
    // subsequent attempt fail identically until a page reload.
    let attempt = 0;
    const env = loadAuth({
      authConfig: cfg,
      firebaseOpts: { get smsError() { return attempt++ === 0 ? new Error('recaptcha spent') : null; } }
    });
    await env.fireReady();
    assert.equal(await env.window.dgeSendPhoneOtp('+919876543210'), false);
    assert.equal(await env.window.dgeSendPhoneOtp('+919876543210'), true);
  });
});

describe('phone OTP — Cloud Function transports (WhatsApp / MSG91)', () => {
  const cfg = { enablePhoneAuth: true, phoneOtpProvider: 'whatsapp' };

  function callables(overrides = {}) {
    return Object.assign({
      sendOtp: async () => ({ data: { ok: true, expiresInSec: 300 } }),
      verifyOtp: async () => ({ data: { ok: true, token: 'CUSTOM_TOKEN' } })
    }, overrides);
  }

  test('sends the code through the sendOtp callable', async () => {
    const env = loadAuth({ authConfig: cfg, firebaseOpts: { callables: callables() } });
    await env.fireReady();
    const ok = await env.window.dgeSendPhoneOtp('+919876543210');
    assert.equal(ok, true);
    // Field-wise rather than deepEqual: the payload object is built
    // inside the vm realm, so its prototype is not the one deepEqual
    // compares against.
    assert.equal(env.fb.calls.callable[0].name, 'sendOtp');
    assert.equal(env.fb.calls.callable[0].payload.phone, '+919876543210');
    assert.equal(env.fb.calls.signInWithPhoneNumber.length, 0, 'must not use the SMS transport');
  });

  test('signs in with the custom token the function returns', async () => {
    const env = loadAuth({ authConfig: cfg, firebaseOpts: { callables: callables() } });
    await env.fireReady();
    await env.window.dgeSendPhoneOtp('+919876543210');
    assert.equal(await env.window.dgeConfirmPhoneOtp('123456'), true);
    assert.deepEqual(env.fb.calls.signInWithCustomToken, ['CUSTOM_TOKEN']);
  });

  test('verifies against the number the code was SENT to, not the input field', async () => {
    // The user can edit the phone field after requesting a code; the
    // verification must still refer to the number actually messaged.
    const env = loadAuth({ authConfig: cfg, firebaseOpts: { callables: callables() } });
    await env.fireReady();
    await env.window.dgeSendPhoneOtp('+919876543210');
    await env.window.dgeConfirmPhoneOtp('123456');
    const verify = env.fb.calls.callable.find(c => c.name === 'verifyOtp');
    assert.equal(verify.payload.phone, '+919876543210');
  });

  test('surfaces the server\'s rate-limit message verbatim', async () => {
    // The Cloud Function writes these for a person to read ("wait 45s"),
    // so replacing them with a generic string loses real information.
    const env = loadAuth({
      authConfig: cfg,
      firebaseOpts: { callables: callables({ sendOtp: async () => { throw new Error('Please wait 45s before requesting another code.'); } }) }
    });
    await env.fireReady();
    assert.equal(await env.window.dgeSendPhoneOtp('+919876543210'), false);
    assert.match(env.toasts.at(-1), /wait 45s/);
  });

  test('does not sign in when the function returns no token', async () => {
    const env = loadAuth({
      authConfig: cfg,
      firebaseOpts: { callables: callables({ verifyOtp: async () => ({ data: { ok: false } }) }) }
    });
    await env.fireReady();
    await env.window.dgeSendPhoneOtp('+919876543210');
    assert.equal(await env.window.dgeConfirmPhoneOtp('123456'), false);
    assert.equal(env.fb.calls.signInWithCustomToken.length, 0);
  });

  test('reports a rejected code', async () => {
    const env = loadAuth({
      authConfig: cfg,
      firebaseOpts: { callables: callables({ verifyOtp: async () => { throw new Error('That code is not correct.'); } }) }
    });
    await env.fireReady();
    await env.window.dgeSendPhoneOtp('+919876543210');
    assert.equal(await env.window.dgeConfirmPhoneOtp('000000'), false);
    assert.match(env.toasts.at(-1), /not correct/);
  });

  test('refuses to verify before a code was requested', async () => {
    const env = loadAuth({ authConfig: cfg, firebaseOpts: { callables: callables() } });
    await env.fireReady();
    assert.equal(await env.window.dgeConfirmPhoneOtp('123456'), false);
    assert.equal(env.fb.calls.callable.length, 0);
  });

  test('rejects an unknown provider instead of silently doing nothing', async () => {
    const env = loadAuth({ authConfig: { enablePhoneAuth: true, phoneOtpProvider: 'twilio' } });
    await env.fireReady();
    assert.equal(await env.window.dgeSendPhoneOtp('+919876543210'), false);
    assert.match(env.toasts.at(-1), /Unknown OTP provider/);
  });

  test('refuses to send when phone auth is switched off', async () => {
    const env = loadAuth({ authConfig: { enablePhoneAuth: false, phoneOtpProvider: 'whatsapp' } });
    await env.fireReady();
    assert.equal(await env.window.dgeSendPhoneOtp('+919876543210'), false);
    assert.equal(env.fb.calls.callable.length, 0);
  });
});

describe('WhatsApp consent', () => {
  const cfg = { enableWhatsappBroadcasts: true };
  const docs = { 'users/known': { role: 'basic', phoneNumber: '+919876543210', whatsappOptIn: false } };

  test('records consent with a timestamp', async () => {
    const env = loadAuth({ authConfig: cfg, firebaseOpts: { docs } });
    await env.fireReady();
    await env.fb.fireAuthState({ uid: 'known' });

    assert.equal(await env.window.dgeSetWhatsappOptIn(true), true);
    const patch = env.fb.calls.docUpdate.at(-1).patch;
    assert.equal(patch.whatsappOptIn, true);
    assert.ok(patch.whatsappOptInAt, 'consent must be timestamped — it is the record of opt-in');
  });

  test('withdrawing consent does not stamp a new opt-in time', async () => {
    const env = loadAuth({ authConfig: cfg, firebaseOpts: { docs } });
    await env.fireReady();
    await env.fb.fireAuthState({ uid: 'known' });

    await env.window.dgeSetWhatsappOptIn(false);
    const patch = env.fb.calls.docUpdate.at(-1).patch;
    assert.equal(patch.whatsappOptIn, false);
    assert.equal('whatsappOptInAt' in patch, false);
  });

  test('refuses when nobody is signed in', async () => {
    const env = loadAuth({ authConfig: cfg });
    await env.fireReady();
    assert.equal(await env.window.dgeSetWhatsappOptIn(true), false);
    assert.match(env.toasts.at(-1), /Sign in first/);
  });

  test('re-syncs the checkbox when the write is rejected', async () => {
    // Otherwise the box stays ticked and the person believes they
    // subscribed when nothing was saved.
    const env = loadAuth({ authConfig: cfg, firebaseOpts: { docs, updateThrows: 'permission denied' } });
    await env.fireReady();
    await env.fb.fireAuthState({ uid: 'known' });

    const box = env.document.getElementById('whatsappOptInCheckbox');
    box.checked = true;
    assert.equal(await env.window.dgeSetWhatsappOptIn(true), false);
    assert.equal(box.checked, false, 'checkbox must fall back to the stored value');
  });

  test('shows the consent row only for an account with a phone number', async () => {
    const withPhone = loadAuth({ authConfig: cfg, firebaseOpts: { docs } });
    await withPhone.fireReady();
    await withPhone.fb.fireAuthState({ uid: 'known' });
    assert.equal(withPhone.document.getElementById('whatsappOptInRow').style.display, 'flex');

    const noPhone = loadAuth({ authConfig: cfg, firebaseOpts: { docs: { 'users/known': { role: 'basic' } } } });
    await noPhone.fireReady();
    await noPhone.fb.fireAuthState({ uid: 'known' });
    assert.equal(noPhone.document.getElementById('whatsappOptInRow').style.display, 'none');
  });

  test('hides the consent row where broadcasts are switched off', async () => {
    const env = loadAuth({ authConfig: { enableWhatsappBroadcasts: false }, firebaseOpts: { docs } });
    await env.fireReady();
    await env.fb.fireAuthState({ uid: 'known' });
    assert.equal(env.document.getElementById('whatsappOptInRow').style.display, 'none');
  });
});

describe('account UI', () => {
  test('shows the signed-in panel with name and role', async () => {
    const env = loadAuth({ firebaseOpts: { docs: { 'users/known': { role: 'sponsor' } } } });
    await env.fireReady();
    await env.fb.fireAuthState({ uid: 'known', displayName: 'Shyam' });

    assert.equal(env.document.getElementById('accountSignedIn').style.display, 'block');
    assert.equal(env.document.getElementById('accountSignedOut').style.display, 'none');
    assert.equal(env.document.getElementById('accountName').textContent, 'Shyam');
    assert.equal(env.document.getElementById('accountRole').textContent, 'sponsor');
  });

  test('falls back to phone, then email, for a display name', async () => {
    const env = loadAuth({ firebaseOpts: { docs: { 'users/k': { role: 'basic' } } } });
    await env.fireReady();
    await env.fb.fireAuthState({ uid: 'k', displayName: null, phoneNumber: '+919876543210' });
    assert.equal(env.document.getElementById('accountName').textContent, '+919876543210');

    await env.fb.fireAuthState({ uid: 'k', displayName: null, phoneNumber: null, email: 'a@x.com' });
    assert.equal(env.document.getElementById('accountName').textContent, 'a@x.com');
  });

  test('signs out through the SDK', async () => {
    const env = loadAuth();
    await env.fireReady();
    await env.window.dgeSignOut();
    assert.equal(env.fb.calls.signOut, 1);
    assert.match(env.toasts.at(-1), /Signed out/);
  });
});
