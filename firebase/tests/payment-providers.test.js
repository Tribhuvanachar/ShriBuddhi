// Tests for payment-providers.js — the `mock` gateway adapter (the only
// one that exists until a real gateway is chosen; see PAYMENTS_SETUP.md).
'use strict';

const { test, describe } = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');

const pp = require('../functions/lib/payment-providers');

describe('assertGatewayAllowed', () => {
  test('refuses "mock" outside an emulator', () => {
    assert.throws(() => pp.assertGatewayAllowed('mock', {}), /emulator-only/);
  });
  test('allows "mock" when an emulator env var is set', () => {
    assert.doesNotThrow(() => pp.assertGatewayAllowed('mock', { FUNCTIONS_EMULATOR: 'true' }));
    assert.doesNotThrow(() => pp.assertGatewayAllowed('mock', { FIRESTORE_EMULATOR_HOST: 'localhost:8080' }));
  });
  test('any other gateway id is a no-op regardless of environment', () => {
    assert.doesNotThrow(() => pp.assertGatewayAllowed('cashfree', {}));
  });
});

describe('getGateway', () => {
  test('returns the mock gateway', () => {
    assert.equal(pp.getGateway('mock').id, 'mock');
  });
  test('throws on an unknown gateway id', () => {
    assert.throws(() => pp.getGateway('nope'), /Unknown payment gateway/);
  });
});

describe('mock gateway: createOrder', () => {
  test('returns a deterministic order id from the donation reference', async () => {
    const g = pp.getGateway('mock');
    const r = await g.createOrder({ donationReference: 'DGE-20260908-ABCDEF', amountMinor: 100100, currency: 'INR' });
    assert.equal(r.ok, true);
    assert.equal(r.gatewayOrderId, 'mock_order_DGE-20260908-ABCDEF');
    assert.equal(r.checkout.amountMinor, 100100);
    // The checkout payload handed to the browser must never carry a secret.
    assert.ok(!('secret' in r.checkout));
    assert.ok(!JSON.stringify(r.checkout).toLowerCase().includes('secret'));
  });
});

describe('mock gateway: webhook signature + parsing', () => {
  const SECRET = 'test-webhook-secret';
  function sign(rawBody) {
    return crypto.createHmac('sha256', SECRET).update(rawBody).digest('hex');
  }

  test('verifies a correctly signed body', () => {
    const g = pp.getGateway('mock');
    const body = Buffer.from(JSON.stringify({ eventId: 'evt_1', status: 'SUCCESS' }));
    const ok = g.verifyWebhookSignature(body, { 'x-mock-signature': sign(body) }, SECRET);
    assert.equal(ok, true);
  });

  test('rejects a tampered body against an untouched signature', () => {
    const g = pp.getGateway('mock');
    const original = Buffer.from(JSON.stringify({ eventId: 'evt_1', status: 'SUCCESS', amountMinor: 100 }));
    const signature = sign(original);
    const tampered = Buffer.from(JSON.stringify({ eventId: 'evt_1', status: 'SUCCESS', amountMinor: 999999 }));
    assert.equal(g.verifyWebhookSignature(tampered, { 'x-mock-signature': signature }, SECRET), false);
  });

  test('rejects a missing or malformed signature header', () => {
    const g = pp.getGateway('mock');
    const body = Buffer.from(JSON.stringify({ eventId: 'evt_1', status: 'SUCCESS' }));
    assert.equal(g.verifyWebhookSignature(body, {}, SECRET), false);
    assert.equal(g.verifyWebhookSignature(body, { 'x-mock-signature': 'not-hex-of-the-right-length' }, SECRET), false);
  });

  test('rejects the correct signature computed with the WRONG secret', () => {
    const g = pp.getGateway('mock');
    const body = Buffer.from(JSON.stringify({ eventId: 'evt_1', status: 'SUCCESS' }));
    const wrongSig = crypto.createHmac('sha256', 'a-different-secret').update(body).digest('hex');
    assert.equal(g.verifyWebhookSignature(body, { 'x-mock-signature': wrongSig }, SECRET), false);
  });

  test('parses a well-formed event and normalizes its status', () => {
    const g = pp.getGateway('mock');
    const body = Buffer.from(JSON.stringify({
      eventId: 'evt_42', eventType: 'payment.success', orderId: 'mock_order_X', paymentId: 'pay_1',
      status: 'SUCCESS', amountMinor: 100100, currency: 'INR', paymentMethod: 'upi'
    }));
    const evt = g.parseWebhookEvent(body);
    assert.equal(evt.eventId, 'evt_42');
    assert.equal(evt.status, 'SUCCESS');
    assert.equal(evt.gatewayOrderId, 'mock_order_X');
    assert.equal(evt.amountMinor, 100100);
  });

  test('returns null for unparseable JSON', () => {
    const g = pp.getGateway('mock');
    assert.equal(g.parseWebhookEvent(Buffer.from('not json')), null);
  });

  test('returns null when eventId or status is missing/unrecognized', () => {
    const g = pp.getGateway('mock');
    assert.equal(g.parseWebhookEvent(Buffer.from(JSON.stringify({ status: 'SUCCESS' }))), null); // no eventId
    assert.equal(g.parseWebhookEvent(Buffer.from(JSON.stringify({ eventId: 'e1', status: 'MADE_UP' }))), null);
  });
});

describe('cashfree gateway: not restricted to an emulator (it is a real gateway)', () => {
  test('assertGatewayAllowed is a no-op for cashfree outside an emulator', () => {
    assert.doesNotThrow(() => pp.assertGatewayAllowed('cashfree', {}));
  });
});

describe('cashfree gateway: createOrder', () => {
  test('sends the amount in MAJOR units (rupees), our own reference as order_id and idempotency key', async () => {
    const g = pp.getGateway('cashfree');
    let seenUrl, seenOpts;
    const fakeFetch = async (url, opts) => {
      seenUrl = url; seenOpts = opts;
      return { ok: true, json: async () => ({ order_id: 'DGE-X', cf_order_id: 'cf_1', payment_session_id: 'session_abc' }) };
    };
    const r = await g.createOrder({
      donationReference: 'DGE-20260909-ABCDEF', amountMinor: 50150, currency: 'INR',
      customer: { donorId: 'd1', name: 'Sri Example', email: 'e@x.com', phone: '9876543210' },
      returnUrl: 'https://x.com/success',
      config: { baseUrl: 'https://sandbox.cashfree.com', clientId: 'id', clientSecret: 'secret', apiVersion: '2023-08-01', fetchImpl: fakeFetch }
    });
    assert.equal(r.ok, true);
    assert.equal(r.checkout.paymentSessionId, 'session_abc');
    assert.equal(seenUrl, 'https://sandbox.cashfree.com/pg/orders');
    assert.equal(seenOpts.headers['x-idempotency-key'], 'DGE-20260909-ABCDEF');
    assert.equal(seenOpts.headers['x-client-secret'], 'secret');
    const body = JSON.parse(seenOpts.body);
    assert.equal(body.order_id, 'DGE-20260909-ABCDEF');
    assert.equal(body.order_amount, 501.5); // 50150 minor units -> 501.50 major
    assert.equal(body.customer_details.customer_phone, '9876543210');
  });

  test('a placeholder phone is used when the donor left it blank, rather than failing order creation', async () => {
    const g = pp.getGateway('cashfree');
    let seenBody;
    const fakeFetch = async (url, opts) => { seenBody = JSON.parse(opts.body); return { ok: true, json: async () => ({ order_id: 'X', payment_session_id: 's' }) }; };
    await g.createOrder({
      donationReference: 'DGE-X', amountMinor: 100, currency: 'INR',
      customer: { donorId: 'd1', name: 'X', email: 'e@x.com', phone: '' },
      config: { baseUrl: 'https://sandbox.cashfree.com', clientId: 'id', clientSecret: 'secret', apiVersion: '2023-08-01', fetchImpl: fakeFetch }
    });
    assert.ok(seenBody.customer_details.customer_phone);
  });

  test('a non-ok response or a missing payment_session_id is reported as a failure, not thrown', async () => {
    const g = pp.getGateway('cashfree');
    const fakeFetch = async () => ({ ok: false, status: 400, json: async () => ({ message: 'bad request' }) });
    const r = await g.createOrder({
      donationReference: 'DGE-X', amountMinor: 100, currency: 'INR',
      customer: { donorId: 'd1', name: 'X', email: 'e@x.com', phone: '9876543210' },
      config: { baseUrl: 'https://sandbox.cashfree.com', clientId: 'id', clientSecret: 'secret', apiVersion: '2023-08-01', fetchImpl: fakeFetch }
    });
    assert.equal(r.ok, false);
    assert.match(r.message, /bad request/);
  });
});

describe('cashfree gateway: webhook signature (timestamp + rawBody, HMAC-SHA256, base64)', () => {
  const SECRET = 'cf-client-secret';
  function sign(rawBody, ts) {
    return crypto.createHmac('sha256', SECRET).update(String(ts) + rawBody).digest('base64');
  }

  test('verifies a correctly signed, fresh body', () => {
    const g = pp.getGateway('cashfree');
    const body = Buffer.from(JSON.stringify({ type: 'PAYMENT_SUCCESS_WEBHOOK', data: {} }));
    const ts = Math.floor(Date.now() / 1000);
    const ok = g.verifyWebhookSignature(body, { 'x-webhook-signature': sign(body, ts), 'x-webhook-timestamp': String(ts) }, SECRET);
    assert.equal(ok, true);
  });

  test('rejects a tampered body', () => {
    const g = pp.getGateway('cashfree');
    const ts = Math.floor(Date.now() / 1000);
    const original = Buffer.from(JSON.stringify({ type: 'PAYMENT_SUCCESS_WEBHOOK', data: { a: 1 } }));
    const signature = sign(original, ts);
    const tampered = Buffer.from(JSON.stringify({ type: 'PAYMENT_SUCCESS_WEBHOOK', data: { a: 2 } }));
    assert.equal(g.verifyWebhookSignature(tampered, { 'x-webhook-signature': signature, 'x-webhook-timestamp': String(ts) }, SECRET), false);
  });

  test('rejects a stale timestamp outside the replay window', () => {
    const g = pp.getGateway('cashfree');
    const body = Buffer.from(JSON.stringify({ type: 'PAYMENT_SUCCESS_WEBHOOK' }));
    const staleTs = Math.floor(Date.now() / 1000) - 3600; // an hour old
    const ok = g.verifyWebhookSignature(body, { 'x-webhook-signature': sign(body, staleTs), 'x-webhook-timestamp': String(staleTs) }, SECRET);
    assert.equal(ok, false);
  });

  test('rejects a missing signature or timestamp header', () => {
    const g = pp.getGateway('cashfree');
    const body = Buffer.from('{}');
    assert.equal(g.verifyWebhookSignature(body, {}, SECRET), false);
    assert.equal(g.verifyWebhookSignature(body, { 'x-webhook-signature': 'x' }, SECRET), false);
  });
});

describe('cashfree gateway: parseWebhookEvent', () => {
  test('PAYMENT_SUCCESS_WEBHOOK normalizes to SUCCESS with amount converted to minor units', () => {
    const g = pp.getGateway('cashfree');
    const body = Buffer.from(JSON.stringify({
      type: 'PAYMENT_SUCCESS_WEBHOOK',
      data: { order: { order_id: 'DGE-X' }, payment: { cf_payment_id: 'p1', payment_amount: 501.5, payment_currency: 'INR', payment_method: { upi: {} } } }
    }));
    const evt = g.parseWebhookEvent(body);
    assert.equal(evt.status, 'SUCCESS');
    assert.equal(evt.gatewayOrderId, 'DGE-X');
    assert.equal(evt.amountMinor, 50150);
    assert.equal(evt.paymentMethod, 'upi');
  });

  test('PAYMENT_FAILED_WEBHOOK normalizes to FAILED', () => {
    const g = pp.getGateway('cashfree');
    const body = Buffer.from(JSON.stringify({ type: 'PAYMENT_FAILED_WEBHOOK', data: { order: { order_id: 'DGE-X' }, payment: { cf_payment_id: 'p1' } } }));
    assert.equal(g.parseWebhookEvent(body).status, 'FAILED');
  });

  test('PAYMENT_USER_DROPPED_WEBHOOK normalizes to CANCELLED', () => {
    const g = pp.getGateway('cashfree');
    const body = Buffer.from(JSON.stringify({ type: 'PAYMENT_USER_DROPPED_WEBHOOK', data: { order: { order_id: 'DGE-X' } } }));
    assert.equal(g.parseWebhookEvent(body).status, 'CANCELLED');
  });

  test('a successful REFUND_STATUS_WEBHOOK normalizes to REFUNDED and carries refundAmountMinor', () => {
    const g = pp.getGateway('cashfree');
    const body = Buffer.from(JSON.stringify({
      type: 'REFUND_STATUS_WEBHOOK',
      data: { refund: { order_id: 'DGE-X', cf_payment_id: 'p1', refund_status: 'SUCCESS', refund_amount: 200.5, refund_currency: 'INR' } }
    }));
    const evt = g.parseWebhookEvent(body);
    assert.equal(evt.status, 'REFUNDED');
    assert.equal(evt.refundAmountMinor, 20050);
  });

  test('a PENDING refund event is acknowledged but does not report a status change', () => {
    const g = pp.getGateway('cashfree');
    const body = Buffer.from(JSON.stringify({ type: 'REFUND_STATUS_WEBHOOK', data: { refund: { order_id: 'DGE-X', refund_status: 'PENDING' } } }));
    const evt = g.parseWebhookEvent(body);
    assert.equal(evt.status, null);
  });

  test('a recognized-but-not-actionable event type is acknowledged with status null, not rejected', () => {
    const g = pp.getGateway('cashfree');
    const body = Buffer.from(JSON.stringify({ type: 'PAYMENT_CHARGES_WEBHOOK', data: {} }));
    const evt = g.parseWebhookEvent(body);
    assert.notEqual(evt, null);
    assert.equal(evt.status, null);
  });

  test('returns null for unparseable JSON or a body with no type field', () => {
    const g = pp.getGateway('cashfree');
    assert.equal(g.parseWebhookEvent(Buffer.from('not json')), null);
    assert.equal(g.parseWebhookEvent(Buffer.from('{}')), null);
  });

  test('two events built from identical bytes get the same derived eventId (idempotency-key stability)', () => {
    const g = pp.getGateway('cashfree');
    const body1 = Buffer.from(JSON.stringify({ type: 'PAYMENT_SUCCESS_WEBHOOK', data: { order: { order_id: 'X' } } }));
    const body2 = Buffer.from(body1); // identical bytes, a fresh buffer (simulating a redelivered webhook)
    assert.equal(g.parseWebhookEvent(body1).eventId, g.parseWebhookEvent(body2).eventId);
  });
});

describe('razorpay gateway: not restricted to an emulator', () => {
  test('assertGatewayAllowed is a no-op for razorpay outside an emulator', () => {
    assert.doesNotThrow(() => pp.assertGatewayAllowed('razorpay', {}));
  });
});

describe('razorpay gateway: createOrder', () => {
  test('sends the amount in MINOR units unchanged (Razorpay already wants paise), receipt = our own reference', async () => {
    const g = pp.getGateway('razorpay');
    let seenUrl, seenOpts;
    const fakeFetch = async (url, opts) => { seenUrl = url; seenOpts = opts; return { ok: true, json: async () => ({ id: 'order_ABC', amount: 50150, currency: 'INR', status: 'created' }) }; };
    const r = await g.createOrder({
      donationReference: 'DGE-20260909-ABCDEF', amountMinor: 50150, currency: 'INR',
      customer: { donorId: 'd1', name: 'X', email: 'e@x.com', phone: '9876543210' },
      config: { keyId: 'rzp_test_x', keySecret: 'secret', fetchImpl: fakeFetch }
    });
    assert.equal(r.ok, true);
    assert.equal(r.gatewayOrderId, 'order_ABC');
    assert.equal(r.checkout.keyId, 'rzp_test_x'); // the PUBLIC key id, safe to hand to the browser
    assert.equal(seenUrl, 'https://api.razorpay.com/v1/orders');
    const body = JSON.parse(seenOpts.body);
    assert.equal(body.amount, 50150); // unchanged -- no major/minor conversion for Razorpay
    assert.equal(body.receipt, 'DGE-20260909-ABCDEF');
    // Basic auth must be present and must never leak the key_secret anywhere the browser sees.
    assert.match(seenOpts.headers.Authorization, /^Basic /);
    assert.ok(!('secret' in r.checkout));
    assert.ok(!JSON.stringify(r.checkout).includes('secret'));
  });

  test('a rejected order creation (e.g. duplicate receipt) is reported as a failure, not thrown', async () => {
    const g = pp.getGateway('razorpay');
    const fakeFetch = async () => ({ ok: false, status: 400, json: async () => ({ error: { description: 'duplicate receipt' } }) });
    const r = await g.createOrder({
      donationReference: 'DGE-X', amountMinor: 100, currency: 'INR',
      customer: { donorId: 'd1', name: 'X', email: 'e@x.com', phone: '9876543210' },
      config: { keyId: 'rzp_test_x', keySecret: 'secret', fetchImpl: fakeFetch }
    });
    assert.equal(r.ok, false);
    assert.match(r.message, /duplicate receipt/);
  });
});

describe('razorpay gateway: webhook signature (raw body, HMAC-SHA256, hex)', () => {
  const SECRET = 'rzp-webhook-secret';
  function sign(rawBody) { return crypto.createHmac('sha256', SECRET).update(rawBody).digest('hex'); }

  test('verifies a correctly signed body', () => {
    const g = pp.getGateway('razorpay');
    const body = Buffer.from(JSON.stringify({ event: 'payment.captured' }));
    assert.equal(g.verifyWebhookSignature(body, { 'x-razorpay-signature': sign(body) }, SECRET), true);
  });
  test('rejects a tampered body', () => {
    const g = pp.getGateway('razorpay');
    const original = Buffer.from(JSON.stringify({ event: 'payment.captured', a: 1 }));
    const signature = sign(original);
    const tampered = Buffer.from(JSON.stringify({ event: 'payment.captured', a: 2 }));
    assert.equal(g.verifyWebhookSignature(tampered, { 'x-razorpay-signature': signature }, SECRET), false);
  });
  test('rejects the right signature computed with the wrong secret', () => {
    const g = pp.getGateway('razorpay');
    const body = Buffer.from(JSON.stringify({ event: 'payment.captured' }));
    const wrongSig = crypto.createHmac('sha256', 'not-the-secret').update(body).digest('hex');
    assert.equal(g.verifyWebhookSignature(body, { 'x-razorpay-signature': wrongSig }, SECRET), false);
  });
});

describe('razorpay gateway: parseWebhookEvent', () => {
  test('payment.captured normalizes to SUCCESS (amount already in minor units, no conversion)', () => {
    const g = pp.getGateway('razorpay');
    const body = Buffer.from(JSON.stringify({
      event: 'payment.captured',
      payload: { payment: { entity: { id: 'pay_1', order_id: 'order_1', status: 'captured', amount: 50150, currency: 'INR', method: 'upi' } } }
    }));
    const evt = g.parseWebhookEvent(body, { 'x-razorpay-event-id': 'evt_1' });
    assert.equal(evt.status, 'SUCCESS');
    assert.equal(evt.eventId, 'evt_1');
    assert.equal(evt.gatewayOrderId, 'order_1');
    assert.equal(evt.amountMinor, 50150);
  });

  test('payment.failed normalizes to FAILED', () => {
    const g = pp.getGateway('razorpay');
    const body = Buffer.from(JSON.stringify({ event: 'payment.failed', payload: { payment: { entity: { id: 'pay_1', order_id: 'order_1', status: 'failed', amount: 100, currency: 'INR' } } } }));
    assert.equal(g.parseWebhookEvent(body, {}).status, 'FAILED');
  });

  test('refund.processed normalizes to REFUNDED, keyed by payment id (Razorpay refund payloads carry no order_id)', () => {
    const g = pp.getGateway('razorpay');
    const body = Buffer.from(JSON.stringify({ event: 'refund.processed', payload: { refund: { entity: { id: 'rfnd_1', payment_id: 'pay_1', amount: 20050, currency: 'INR' } } } }));
    const evt = g.parseWebhookEvent(body, {});
    assert.equal(evt.status, 'REFUNDED');
    assert.equal(evt.gatewayOrderId, null);
    assert.equal(evt.gatewayPaymentId, 'pay_1');
    assert.equal(evt.refundAmountMinor, 20050);
  });

  test('a recognized-but-unverified event (payment.authorized, order.paid, refund.failed) is acknowledged with status null', () => {
    const g = pp.getGateway('razorpay');
    for (const event of ['payment.authorized', 'order.paid', 'refund.failed', 'payment.downtime.started']) {
      const body = Buffer.from(JSON.stringify({ event, payload: {} }));
      const evt = g.parseWebhookEvent(body, {});
      assert.notEqual(evt, null, `${event} should still parse`);
      assert.equal(evt.status, null, `${event} should not report a status change`);
    }
  });

  test('falls back to a deterministic id derived from the body when x-razorpay-event-id is absent', () => {
    const g = pp.getGateway('razorpay');
    const body = Buffer.from(JSON.stringify({ event: 'payment.captured', payload: { payment: { entity: { id: 'pay_1', order_id: 'order_1', status: 'captured', amount: 100, currency: 'INR' } } } }));
    const evt1 = g.parseWebhookEvent(body, {});
    const evt2 = g.parseWebhookEvent(Buffer.from(body), {}); // identical bytes, fresh buffer
    assert.ok(evt1.eventId);
    assert.equal(evt1.eventId, evt2.eventId);
  });

  test('returns null for unparseable JSON or a body with no event field', () => {
    const g = pp.getGateway('razorpay');
    assert.equal(g.parseWebhookEvent(Buffer.from('not json'), {}), null);
    assert.equal(g.parseWebhookEvent(Buffer.from('{}'), {}), null);
  });
});
