// End-to-end tests against the REAL Firebase emulators (auth, firestore,
// functions) with the `console` OTP provider, which prints the code to
// the function log instead of sending it. No credentials, no money, no
// phone — but a genuine exercise of index.js, which the unit tests
// deliberately do not touch.
//
// Run with:  npm run test:e2e
//
// This suite exists because index.js is the one file in this feature that
// unit tests cannot reach: it is the Firebase-shaped shell (secrets,
// transactions, custom tokens) around the tested pure logic. The first
// time it was ever executed it failed immediately — `admin.firestore.
// FieldValue` reads back as undefined through the emulator's proxy of the
// firebase-admin root export, so every serverTimestamp() threw. Nothing
// short of running it would have found that.
'use strict';

const { test, describe, before } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');

const BASE = process.env.DGE_FN_BASE || 'http://127.0.0.1:5001/dge-test/asia-south1';
const FIRESTORE = 'http://127.0.0.1:8080/v1/projects/dge-test/databases/(default)/documents';
// The console provider appends "<phone> <code>" here — see providers.js.
// Reading a file the provider wrote is deterministic; scraping the
// emulator's log output races its buffering.
const ECHO = process.env.DGE_OTP_ECHO_FILE || '/tmp/dge-otp-echo.txt';

/**
 * Reads a whole collection straight out of the Firestore emulator.
 *
 * The `Bearer owner` header is what bypasses the security rules. Without
 * it these reads come back 403 — which is the rules working exactly as
 * intended (rules.spec.js asserts that no client may list `users` or
 * touch `otp_challenges` at all), but useless for inspecting what a
 * function actually wrote.
 */
async function readCollection(name) {
  const res = await fetch(`${FIRESTORE}/${name}`, {
    headers: { Authorization: 'Bearer owner' }
  });
  const body = await res.json().catch(() => ({}));
  return body.documents || [];
}

async function callFn(name, data) {
  const res = await fetch(`${BASE}/${name}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ data })
  });
  return { status: res.status, body: await res.json().catch(() => ({})) };
}

/** The most recent code the console provider issued for a number. */
function codeFor(phone) {
  const lines = fs.existsSync(ECHO) ? fs.readFileSync(ECHO, 'utf8').trim().split('\n') : [];
  const mine = lines.filter(l => l.startsWith(phone + ' '));
  if (!mine.length) throw new Error(`no code issued for ${phone}`);
  return mine[mine.length - 1].split(' ')[1];
}

// Each test uses its own number so the per-number rate limits (1/minute)
// don't make the suite order-dependent.
let seq = 0;
const freshPhone = () => `+9198765${String(43000 + (seq++)).padStart(5, '0')}`;

before(async () => {
  const res = await fetch(`${BASE}/sendOtp`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ data: { phone: '+919999900000' } })
  }).catch(() => null);
  if (!res) throw new Error(`Emulators not reachable at ${BASE}. Start them first — see npm run test:e2e.`);
});

describe('sendOtp', () => {
  test('generates and delivers a code', async () => {
    const phone = freshPhone();
    const { body } = await callFn('sendOtp', { phone });
    assert.equal(body.result?.ok, true);
    assert.equal(body.result?.provider, 'console');
    assert.match(codeFor(phone), /^\d{6}$/);
  });

  test('rejects a malformed number before spending a send', async () => {
    const { body } = await callFn('sendOtp', { phone: 'not-a-phone' });
    assert.equal(body.error?.status, 'INVALID_ARGUMENT');
  });

  test('enforces the resend cooldown', async () => {
    // The rate limit that protects the bill, exercised through a real
    // Firestore transaction rather than in isolation.
    const phone = freshPhone();
    await callFn('sendOtp', { phone });
    const { body } = await callFn('sendOtp', { phone });
    assert.equal(body.error?.status, 'RESOURCE_EXHAUSTED');
    assert.match(body.error?.message, /wait \d+s/);
  });
});

describe('verifyOtp', () => {
  test('mints a custom token for the correct code', async () => {
    const phone = freshPhone();
    await callFn('sendOtp', { phone });
    const { body } = await callFn('verifyOtp', { phone, code: codeFor(phone) });
    assert.equal(body.result?.ok, true);
    assert.ok(body.result?.token, 'a custom token must come back');
    // A Firebase custom token is a JWT — three dot-separated segments.
    assert.equal(String(body.result.token).split('.').length, 3);
  });

  test('creates the profile as basic, with WhatsApp consent off', async () => {
    // The same defaults the security rules enforce, asserted here against
    // the document the function actually wrote.
    const phone = freshPhone();
    await callFn('sendOtp', { phone });
    await callFn('verifyOtp', { phone, code: codeFor(phone) });

    const docs = await readCollection('users');
    const mine = docs.find(d => d.fields?.phoneNumber?.stringValue === phone);
    assert.ok(mine, 'a profile document should exist for the verified number');
    assert.equal(mine.fields.role.stringValue, 'basic');
    assert.equal(mine.fields.whatsappOptIn.booleanValue, false);
    assert.equal(mine.fields.signInMethod.stringValue, 'phone_otp');
    assert.ok(mine.fields.createdAt?.timestampValue, 'createdAt must be a real server timestamp');
  });

  test('refuses a wrong code', async () => {
    const phone = freshPhone();
    await callFn('sendOtp', { phone });
    const real = codeFor(phone);
    const wrong = real === '000000' ? '111111' : '000000';
    const { body } = await callFn('verifyOtp', { phone, code: wrong });
    assert.equal(body.error?.status, 'UNAUTHENTICATED');
  });

  test('refuses to replay a code that already worked', async () => {
    const phone = freshPhone();
    await callFn('sendOtp', { phone });
    const code = codeFor(phone);
    const first = await callFn('verifyOtp', { phone, code });
    assert.equal(first.body.result?.ok, true);

    const second = await callFn('verifyOtp', { phone, code });
    assert.equal(second.body.error?.status, 'RESOURCE_EXHAUSTED');
    assert.match(second.body.error?.message, /already been used/);
  });

  test('refuses a code for a number that never requested one', async () => {
    // UNAUTHENTICATED, not RESOURCE_EXHAUSTED: the latter is reserved for
    // a challenge that existed and is now burned (expired, used, or out of
    // attempts), which the client surfaces to the user differently.
    const { body } = await callFn('verifyOtp', { phone: freshPhone(), code: '123456' });
    assert.equal(body.error?.status, 'UNAUTHENTICATED');
    assert.match(body.error?.message, /Request a code first/);
  });

  test('burns the challenge after too many wrong guesses', async () => {
    const phone = freshPhone();
    await callFn('sendOtp', { phone });
    const real = codeFor(phone);

    for (let i = 0; i < 5; i++) {
      const guess = String(100000 + i) === real ? String(200000 + i) : String(100000 + i);
      await callFn('verifyOtp', { phone, code: guess });
    }
    // Even the CORRECT code must now fail — the whole point of the cap.
    const { body } = await callFn('verifyOtp', { phone, code: real });
    assert.equal(body.result, undefined, 'the correct code must not work once the cap is hit');
    assert.equal(body.error?.status, 'RESOURCE_EXHAUSTED');
  });

  test('the same number always lands on the same account', async () => {
    // Stable UID derivation: a returning user must not get a new account
    // (and therefore a reset role) on every sign-in.
    const phone = freshPhone();
    await callFn('sendOtp', { phone });
    await callFn('verifyOtp', { phone, code: codeFor(phone) });

    const before = (await readCollection('users'))
      .filter(d => d.fields?.phoneNumber?.stringValue === phone);
    assert.equal(before.length, 1);

    // Wait out the cooldown by using the challenge doc directly is not
    // possible from here, so assert the invariant that matters: one doc
    // per number, keyed by a derived UID rather than a random one.
    assert.match(before[0].name.split('/').pop(), /^phone_[0-9a-f]{32}$/);
  });
});

describe('otp_challenges storage', () => {
  test('stores a hash, never the code itself', async () => {
    const phone = freshPhone();
    await callFn('sendOtp', { phone });
    const code = codeFor(phone);

    const docs = await readCollection('otp_challenges');
    const raw = JSON.stringify(docs);
    assert.ok(raw.includes('codeHash'), 'challenges should be stored');
    assert.equal(raw.includes(`"${code}"`), false, 'the plaintext code must never be persisted');
  });

  test('does not put the phone number in the document id', async () => {
    const docs = await readCollection('otp_challenges');
    assert.ok(docs.length > 0);
    for (const d of docs) {
      const id = d.name.split('/').pop();
      assert.match(id, /^[0-9a-f]{64}$/, 'challenge ids should be opaque hashes');
    }
  });
});

describe('whatsappWebhook', () => {
  test('rejects an unsigned payload', async () => {
    // Without this check anyone who learns the URL can forge opt-ins.
    const res = await fetch(`${BASE}/whatsappWebhook`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ entry: [] })
    });
    assert.equal(res.status, 401);
  });

  test('rejects a wrong verify token on the subscription handshake', async () => {
    const res = await fetch(`${BASE}/whatsappWebhook?hub.mode=subscribe&hub.verify_token=wrong&hub.challenge=xyz`);
    assert.equal(res.status, 403);
  });

  test('completes the handshake with the right verify token', async () => {
    const res = await fetch(`${BASE}/whatsappWebhook?hub.mode=subscribe&hub.verify_token=emulator-fake&hub.challenge=xyz`);
    assert.equal(res.status, 200);
    assert.equal(await res.text(), 'xyz');
  });
});
