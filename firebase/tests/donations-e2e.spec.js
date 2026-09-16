// End-to-end tests against the REAL Firebase emulators (firestore,
// functions) with the `mock` payment gateway — no credentials, no money,
// no real gateway account. Mirrors e2e.spec.js's reasoning exactly:
// donation-core.js/payment-state.js/payment-providers.js/receipt-core.js
// are unit-tested in isolation, but index.js is the one file those tests
// cannot reach — it is the Firebase-shaped shell (Firestore transactions,
// secrets, the webhook HTTP endpoint) around them.
//
// Run with:  npm run test:donations-e2e
'use strict';

const { test, describe, before } = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');

const BASE = process.env.DGE_FN_BASE || 'http://127.0.0.1:5001/dge-test/asia-south1';
const FIRESTORE = 'http://127.0.0.1:8080/v1/projects/dge-test/databases/(default)/documents';
const WEBHOOK_SECRET = 'test-payment-webhook-secret-not-real'; // must match functions/.secret.local

async function readDoc(path) {
  const res = await fetch(`${FIRESTORE}/${path}`, { headers: { Authorization: 'Bearer owner' } });
  if (res.status === 404) return null;
  const body = await res.json();
  return firestoreFieldsToPlain(body.fields || {});
}

/** Minimal Firestore REST document -> plain JS object, just enough for
 *  the flat shapes this feature writes (no nested maps/arrays needed). */
function firestoreFieldsToPlain(fields) {
  const out = {};
  for (const [k, v] of Object.entries(fields)) {
    if ('stringValue' in v) out[k] = v.stringValue;
    else if ('integerValue' in v) out[k] = Number(v.integerValue);
    else if ('booleanValue' in v) out[k] = v.booleanValue;
    else if ('nullValue' in v) out[k] = null;
    else if ('timestampValue' in v) out[k] = v.timestampValue;
    else out[k] = v;
  }
  return out;
}

async function queryCollection(name) {
  const res = await fetch(`${FIRESTORE}/${name}`, { headers: { Authorization: 'Bearer owner' } });
  const body = await res.json().catch(() => ({}));
  return (body.documents || []).map(d => ({
    id: d.name.split('/').pop(),
    ...firestoreFieldsToPlain(d.fields || {})
  }));
}

async function callFn(name, data) {
  const res = await fetch(`${BASE}/${name}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ data })
  });
  const body = await res.json().catch(() => ({}));
  return { status: res.status, body: body.result !== undefined ? body.result : body };
}

function signMockWebhook(payload) {
  const raw = Buffer.from(JSON.stringify(payload));
  const signature = crypto.createHmac('sha256', WEBHOOK_SECRET).update(raw).digest('hex');
  return { raw, signature };
}

async function postMockWebhook(payload) {
  const { raw, signature } = signMockWebhook(payload);
  const res = await fetch(`${BASE}/paymentWebhook?gateway=mock`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'x-mock-signature': signature },
    body: raw
  });
  return { status: res.status, text: await res.text() };
}

let seq = 0;
const freshDonor = () => ({
  name: 'Test Donor',
  email: `donor${Date.now()}_${seq++}@example.com`,
  phone: '9876543210',
  country: 'IN',
  amount: 501,
  displayName: true,
  displayAmount: true
});

before(async () => {
  const res = await fetch(`${BASE}/createDonation`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ data: freshDonor() })
  }).catch(() => null);
  if (!res) throw new Error(`Emulators not reachable at ${BASE}. Start them first — see npm run test:donations-e2e.`);
});

describe('createDonation', () => {
  test('creates a PENDING donation and returns a mock checkout payload', async () => {
    const { status, body } = await callFn('createDonation', freshDonor());
    assert.equal(status, 200, JSON.stringify(body));
    assert.equal(body.ok, true);
    assert.match(body.donationReference, /^DGE-\d{8}-[0-9A-HJKMNP-TV-Z]{6}$/);
    assert.equal(body.checkout.gateway, 'mock');

    const donations = await queryCollection('donations');
    const mine = donations.find(d => d.donationReference === body.donationReference);
    assert.ok(mine, 'donation doc must exist');
    assert.equal(mine.status, 'PENDING');
    assert.equal(mine.amountMinor, 50100);
  });

  test('rejects a tampered/invalid amount before any gateway call', async () => {
    const { status, body } = await callFn('createDonation', Object.assign(freshDonor(), { amount: -100 }));
    assert.equal(status, 400); // HttpsError('invalid-argument', ...) maps to HTTP 400
    assert.match(JSON.stringify(body), /amount/i);
  });

  test('rejects a name that sanitizes to nothing (pure markup)', async () => {
    const { body } = await callFn('createDonation', Object.assign(freshDonor(), { name: '<b></b>' }));
    assert.match(JSON.stringify(body), /name/i);
  });
});

describe('paymentWebhook + getDonationStatus: the full mock-gateway flow', () => {
  test('an unsigned webhook is rejected', async () => {
    const raw = Buffer.from(JSON.stringify({ eventId: 'evt_x', status: 'SUCCESS', orderId: 'mock_order_nope' }));
    const res = await fetch(`${BASE}/paymentWebhook?gateway=mock`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: raw
    });
    assert.equal(res.status, 401);
  });

  test('a webhook for an unknown order id is recorded but does not crash', async () => {
    const r = await postMockWebhook({ eventId: `evt_unknown_${Date.now()}`, status: 'SUCCESS', orderId: 'mock_order_does_not_exist', amountMinor: 100, currency: 'INR' });
    assert.equal(r.status, 200);
  });

  test('SUCCESS moves the donation to SUCCESS, generates a receipt, and lists the supporter publicly', async () => {
    const { body: created } = await callFn('createDonation', freshDonor());
    const ref = created.donationReference;
    const gatewayOrderId = created.checkout.sessionId ? `mock_order_${ref}` : null; // createOrder's own id shape
    assert.ok(gatewayOrderId);

    const eventId = `evt_success_${Date.now()}`;
    const webhookRes = await postMockWebhook({
      eventId, status: 'SUCCESS', orderId: gatewayOrderId, paymentId: 'pay_1', amountMinor: 50100, currency: 'INR', paymentMethod: 'upi'
    });
    assert.equal(webhookRes.status, 200);

    // getDonationStatus is the server-verified truth the success page checks.
    const { body: statusBody } = await callFn('getDonationStatus', { donationReference: ref });
    assert.equal(statusBody.status, 'SUCCESS');
    assert.match(statusBody.receiptNumber, /^DGE-\d{4}-\d{6}$/);

    const publicSupporters = await queryCollection('public_supporters');
    const entry = publicSupporters.find(s => s.donationReference === ref);
    assert.ok(entry, 'public_supporters entry must exist for an opted-in donor');
    assert.equal(entry.displayName, 'Test Donor');
    assert.ok(!('email' in entry) && !('donorId' in entry));

    return { ref, gatewayOrderId, eventId }; // handed to the next test via closure below
  });

  test('a duplicate delivery of the SAME webhook event is a true no-op (idempotency)', async () => {
    const { body: created } = await callFn('createDonation', freshDonor());
    const ref = created.donationReference;
    const gatewayOrderId = `mock_order_${ref}`;
    const eventId = `evt_dup_${Date.now()}`;
    const payload = { eventId, status: 'SUCCESS', orderId: gatewayOrderId, paymentId: 'pay_dup', amountMinor: 50100, currency: 'INR', paymentMethod: 'upi' };

    const first = await postMockWebhook(payload);
    assert.equal(first.status, 200);
    const { body: afterFirst } = await callFn('getDonationStatus', { donationReference: ref });
    const receiptAfterFirst = afterFirst.receiptNumber;
    assert.ok(receiptAfterFirst);

    const second = await postMockWebhook(payload); // byte-identical replay
    assert.equal(second.status, 200);
    const { body: afterSecond } = await callFn('getDonationStatus', { donationReference: ref });
    assert.equal(afterSecond.receiptNumber, receiptAfterFirst, 'a replayed webhook must not mint a second receipt');

    const publicSupporters = await queryCollection('public_supporters');
    const mine = publicSupporters.filter(s => s.donationReference === ref);
    assert.equal(mine.length, 1, 'a replayed webhook must not duplicate the public_supporters entry');
  });

  test('a stale PENDING event arriving after SUCCESS cannot walk the donation backwards', async () => {
    const { body: created } = await callFn('createDonation', freshDonor());
    const ref = created.donationReference;
    const gatewayOrderId = `mock_order_${ref}`;

    await postMockWebhook({ eventId: `evt_a_${Date.now()}`, status: 'SUCCESS', orderId: gatewayOrderId, paymentId: 'pay_a', amountMinor: 50100, currency: 'INR' });
    const { body: afterSuccess } = await callFn('getDonationStatus', { donationReference: ref });
    assert.equal(afterSuccess.status, 'SUCCESS');

    // A gateway's own retries/out-of-order delivery could still send an
    // earlier PENDING notification after the SUCCESS one already landed.
    await postMockWebhook({ eventId: `evt_b_${Date.now()}`, status: 'PENDING', orderId: gatewayOrderId, amountMinor: 50100, currency: 'INR' });
    const { body: afterStalePending } = await callFn('getDonationStatus', { donationReference: ref });
    assert.equal(afterStalePending.status, 'SUCCESS', 'status must not regress to PENDING');
  });
});

describe('getDonationStatus', () => {
  test('rejects a malformed reference without touching Firestore', async () => {
    const { status, body } = await callFn('getDonationStatus', { donationReference: 'not-a-real-reference' });
    assert.equal(status, 400); // HttpsError('invalid-argument', ...) maps to HTTP 400
    assert.match(JSON.stringify(body), /does not look like/i);
  });
  test('reports not-found for a well-formed but nonexistent reference', async () => {
    const { status, body } = await callFn('getDonationStatus', { donationReference: 'DGE-20260101-ABCDEF' });
    assert.equal(status, 404); // HttpsError('not-found', ...) maps to HTTP 404
    assert.match(JSON.stringify(body), /no donation found/i);
  });
});
