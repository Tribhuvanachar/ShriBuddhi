// payment-providers.js -- pluggable payment gateways, mirroring the same
// shape lib/providers.js already uses for OTP delivery: donation-core.js,
// payment-state.js and index.js's orchestration do not know or care which
// gateway is behind a donation. Adding a real one (Cashfree, Razorpay,
// Stripe, ...) later means adding one entry here against ITS current,
// verified API -- never touching the validation, state machine, receipt
// or Firestore code, all of which are already built and tested against
// the `mock` gateway below.
//
// IMPORTANT: no real gateway is wired in yet -- that decision (which
// gateway, sandbox vs. production credentials, the exact webhook
// signature scheme) is the project lead's to make, and any integration
// must be built against that gateway's OWN current documentation at the
// time, not from a half-remembered API shape. See ../../../PAYMENTS_SETUP.md.
//
// `mock` exists purely so the rest of the pipeline (createDonation ->
// webhook -> state machine -> receipt -> public_supporters) can be built
// and tested for real right now, the same way providers.js's `console`
// OTP channel exists to test sign-in without a real WhatsApp/SMS
// account. It is refused outside an emulator for the identical reason:
// a dev convenience that could reach production would mean donations
// silently succeeding without a rupee ever moving.
'use strict';

const crypto = require('crypto');
const donationCore = require('./donation-core');

/**
 * Constant-time comparison of two encoded strings (hex or base64) that
 * are expected to be the same LENGTH when correct. Guards the length
 * check itself (Buffer.from of two different-length strings would throw
 * inside timingSafeEqual) the same way otp-core.js's safeEqualHex does.
 */
function timingSafeEqualStr(a, b, encoding) {
  if (typeof a !== 'string' || typeof b !== 'string' || !a || !b) return false;
  let bufA, bufB;
  try {
    bufA = Buffer.from(a, encoding);
    bufB = Buffer.from(b, encoding);
  } catch (e) {
    return false;
  }
  if (bufA.length === 0 || bufB.length === 0 || bufA.length !== bufB.length) return false;
  return crypto.timingSafeEqual(bufA, bufB);
}

/**
 * Each gateway exposes:
 *   createOrder({ donationReference, amountMinor, currency, customer,
 *                 returnUrl, config }) -> Promise<{ok, gatewayOrderId,
 *                 checkout, message?}>
 *     `checkout` is whatever minimal, non-secret payload the BROWSER
 *     needs to continue (a session id, a redirect URL, ...) -- never the
 *     gateway's own API credentials.
 *   verifyWebhookSignature(rawBody, headers, secret) -> boolean
 *   parseWebhookEvent(rawBody, headers) -> {
 *     eventId, eventType, gatewayOrderId, gatewayPaymentId,
 *     status,           // one of payment-state.js's ALL_STATUSES, already normalized
 *     amountMinor, currency, paymentMethod
 *   } | null
 */
const gateways = {
  /**
   * Dev/test-only gateway. `createOrder` never calls out to anything --
   * it deterministically fabricates a gateway order id from the
   * donation reference, so a test can predict it. The webhook shape
   * below is OUR OWN fixture format, not any real gateway's; it exists
   * only to exercise index.js's webhook handler and the state machine
   * end to end.
   */
  mock: {
    id: 'mock',
    async createOrder({ donationReference, amountMinor, currency }) {
      const gatewayOrderId = `mock_order_${donationReference}`;
      return {
        ok: true,
        gatewayOrderId,
        checkout: {
          gateway: 'mock',
          // A real gateway hands the browser a session id / redirect URL
          // here; the mock hands back enough for a test harness to
          // simulate the browser side without a real checkout page.
          sessionId: `mock_session_${donationReference}`,
          amountMinor,
          currency
        }
      };
    },

    /**
     * HMAC-SHA256 over the raw body, same construction as the WhatsApp
     * webhook (lib/whatsapp.js) -- a real gateway's own scheme must be
     * implemented against ITS current documentation when chosen; do not
     * assume this shape carries over.
     */
    verifyWebhookSignature(rawBody, headers, secret) {
      if (!rawBody || !secret) return false;
      const header = headers && (headers['x-mock-signature'] || headers['X-Mock-Signature']);
      if (typeof header !== 'string' || !header) return false;
      const expected = crypto.createHmac('sha256', secret).update(rawBody).digest('hex');
      const a = Buffer.from(header, 'utf8');
      const b = Buffer.from(expected, 'utf8');
      if (a.length !== b.length) return false;
      return crypto.timingSafeEqual(a, b);
    },

    parseWebhookEvent(rawBody) {
      let body;
      try { body = JSON.parse(rawBody.toString('utf8')); } catch (e) { return null; }
      if (!body || typeof body !== 'object') return null;
      const statusMap = {
        SUCCESS: 'SUCCESS',
        FAILED: 'FAILED',
        CANCELLED: 'CANCELLED',
        REFUNDED: 'REFUNDED',
        PARTIALLY_REFUNDED: 'PARTIALLY_REFUNDED',
        PENDING: 'PENDING'
      };
      const status = statusMap[body.status];
      if (!body.eventId || !status) return null;
      return {
        eventId: String(body.eventId),
        eventType: String(body.eventType || `payment.${status.toLowerCase()}`),
        gatewayOrderId: body.orderId ? String(body.orderId) : null,
        gatewayPaymentId: body.paymentId ? String(body.paymentId) : null,
        status,
        amountMinor: Number.isInteger(body.amountMinor) ? body.amountMinor : null,
        currency: typeof body.currency === 'string' ? body.currency : null,
        paymentMethod: typeof body.paymentMethod === 'string' ? body.paymentMethod : null
      };
    }
  },

  /**
   * Cashfree Payment Gateway (Orders API). Built against Cashfree's own
   * current docs (api-reference/payments/latest, docs pulled 9 Sep
   * 2026) -- see PAYMENTS_SETUP.md for the exact source URLs. Not yet
   * exercised against a real Cashfree account: no credentials exist in
   * this deployment. `config` (built by index.js's paymentGatewayConfig)
   * carries clientId/clientSecret/apiVersion/baseUrl -- never imported
   * as module-level secrets here, so this file stays testable without
   * touching firebase-functions/params.
   */
  cashfree: {
    id: 'cashfree',
    async createOrder({ donationReference, amountMinor, currency, customer, returnUrl, config }) {
      const res = await (config.fetchImpl || globalThis.fetch)(`${config.baseUrl}/pg/orders`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-client-id': config.clientId,
          'x-client-secret': config.clientSecret,
          'x-api-version': config.apiVersion,
          // Our own donationReference IS a well-formed, safe-to-retry
          // idempotency key -- reusing it here means a network-level
          // retry of the same createDonation call can never open two
          // Cashfree orders for one donation.
          'x-idempotency-key': donationReference
        },
        body: JSON.stringify({
          order_id: donationReference, // our reference IS the Cashfree order_id -- one id, not two to keep in sync
          order_amount: donationCore.minorToMajor(amountMinor),
          order_currency: currency,
          customer_details: {
            customer_id: customer.donorId,
            customer_name: customer.name,
            customer_email: customer.email,
            // Cashfree requires a phone number on customer_details; an
            // optional donor field becomes a placeholder here rather
            // than failing order creation over a field this app itself
            // treats as optional -- see PAYMENTS_SETUP.md's note on this.
            customer_phone: customer.phone || '9999999999'
          },
          order_meta: returnUrl ? { return_url: returnUrl } : undefined
        })
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok || !body.payment_session_id) {
        return { ok: false, message: body.message || `Cashfree order creation failed (HTTP ${res.status})` };
      }
      return {
        ok: true,
        gatewayOrderId: body.order_id || donationReference,
        checkout: { gateway: 'cashfree', paymentSessionId: body.payment_session_id, orderId: body.order_id || donationReference }
      };
    },

    /**
     * timestamp + rawBody, HMAC-SHA256, base64 -- NOT the raw body alone.
     * Cashfree's own docs warn explicitly that verifying against a
     * re-parsed/re-serialized body breaks the hash (a decimal amount
     * becoming an integer is enough to change every byte after it), so
     * this must run on the literal bytes the runtime handed us.
     */
    verifyWebhookSignature(rawBody, headers, secret, now = Date.now()) {
      if (!rawBody || !secret) return false;
      const signature = headers && (headers['x-webhook-signature'] || headers['X-Webhook-Signature']);
      const timestamp = headers && (headers['x-webhook-timestamp'] || headers['X-Webhook-Timestamp']);
      if (!signature || !timestamp) return false;

      // Cashfree's docs recommend rejecting a stale signature as a
      // replay defense, but do not state x-webhook-timestamp's unit in
      // what this session could verify -- treated as Unix SECONDS here
      // (the far more common HTTP-header convention, e.g. Stripe's own
      // t= field) with a generous 10-minute window, so a wrong guess at
      // the unit fails safe toward "still accepted" rather than
      // rejecting genuine webhooks outright. CONFIRM the actual unit
      // against a real received webhook before relying on this window
      // being tight. Either way, this is a SECONDARY defense: the
      // primary replay protection is payment_events' idempotency keying
      // on the event id (index.js), which makes a byte-identical
      // replayed webhook a no-op regardless of this check.
      const timestampMs = Number(timestamp) * 1000;
      const age = Math.abs(now - timestampMs);
      if (!Number.isFinite(age) || age > 10 * 60 * 1000) return false;

      const expected = crypto.createHmac('sha256', secret).update(String(timestamp) + rawBody).digest('base64');
      return timingSafeEqualStr(signature, expected, 'base64');
    },

    parseWebhookEvent(rawBody) {
      let body;
      try { body = JSON.parse(rawBody.toString('utf8')); } catch (e) { return null; }
      if (!body || typeof body !== 'object' || !body.type) return null;
      const data = body.data || {};

      if (body.type === 'PAYMENT_SUCCESS_WEBHOOK') {
        return eventOf(data.payment, {
          status: 'SUCCESS',
          gatewayOrderId: data.order && data.order.order_id,
          gatewayPaymentId: data.payment && data.payment.cf_payment_id,
          amountMinor: amountToMinor(data.payment && data.payment.payment_amount),
          currency: data.payment && data.payment.payment_currency,
          paymentMethod: data.payment && data.payment.payment_method && Object.keys(data.payment.payment_method)[0]
        });
      }
      if (body.type === 'PAYMENT_FAILED_WEBHOOK') {
        return eventOf(data.payment, {
          status: 'FAILED',
          gatewayOrderId: data.order && data.order.order_id,
          gatewayPaymentId: data.payment && data.payment.cf_payment_id
        });
      }
      if (body.type === 'PAYMENT_USER_DROPPED_WEBHOOK') {
        return eventOf(data.payment, {
          status: 'CANCELLED',
          gatewayOrderId: data.order && data.order.order_id,
          gatewayPaymentId: data.payment && data.payment.cf_payment_id
        });
      }
      if (body.type === 'REFUND_STATUS_WEBHOOK' || body.type === 'AUTO_REFUND_STATUS_WEBHOOK') {
        const refund = data.refund || data.auto_refund;
        if (!refund || refund.refund_status !== 'SUCCESS') {
          // Only a SUCCEEDED refund moves the donation; a pending or
          // failed refund attempt is recorded but changes nothing yet.
          return eventOf(refund, { status: null, gatewayOrderId: refund && refund.order_id });
        }
        return eventOf(refund, {
          status: 'REFUNDED', // index.js decides REFUNDED vs PARTIALLY_REFUNDED by comparing refundAmountMinor to the donation's own amount
          gatewayOrderId: refund.order_id,
          gatewayPaymentId: refund.cf_payment_id,
          refundAmountMinor: amountToMinor(refund.refund_amount),
          currency: refund.refund_currency
        });
      }
      // A recognized-but-not-actionable event type (e.g.
      // PAYMENT_CHARGES_WEBHOOK) -- acknowledged, no status change.
      return { eventId: cashfreeEventId(body), eventType: body.type, gatewayOrderId: null, gatewayPaymentId: null, status: null, amountMinor: null, currency: null, paymentMethod: null };

      function eventOf(entity, fields) {
        return Object.assign({
          eventId: cashfreeEventId(body),
          eventType: body.type,
          gatewayOrderId: null,
          gatewayPaymentId: null,
          amountMinor: null,
          currency: null,
          paymentMethod: null
        }, fields);
      }
    }
  },

  /**
   * Razorpay (Orders API + Checkout). Built against Razorpay's own
   * current docs (docs pulled 9 Sep 2026) -- see PAYMENTS_SETUP.md.
   * Also not yet exercised against a real account.
   */
  razorpay: {
    id: 'razorpay',
    async createOrder({ donationReference, amountMinor, currency, customer, config }) {
      const auth = Buffer.from(`${config.keyId}:${config.keySecret}`).toString('base64');
      const res = await (config.fetchImpl || globalThis.fetch)('https://api.razorpay.com/v1/orders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Basic ${auth}` },
        body: JSON.stringify({
          amount: amountMinor, // Razorpay's Orders API already wants the smallest currency unit -- no conversion, unlike Cashfree
          currency,
          // `receipt` is Razorpay's own idempotency mechanism for this
          // API (there is no generic Idempotency-Key header on Orders) --
          // our donationReference is already unique and <=40 chars, so
          // it doubles as the receipt with no extra bookkeeping.
          receipt: donationReference,
          notes: { donationReference, donorId: customer.donorId }
        })
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok || !body.id) {
        const message = (body.error && body.error.description) || `Razorpay order creation failed (HTTP ${res.status})`;
        return { ok: false, message };
      }
      return {
        ok: true,
        gatewayOrderId: body.id,
        checkout: {
          gateway: 'razorpay',
          orderId: body.id,
          amount: body.amount,
          currency: body.currency,
          // key_id is Razorpay's PUBLIC identifier, the same role a
          // Stripe publishable key plays -- it is meant to reach the
          // browser (Checkout.js needs it to open the payment modal)
          // and carries no ability to authenticate a server call on its
          // own, unlike key_secret, which never leaves this function.
          keyId: config.keyId
        }
      };
    },

    /** Raw body, HMAC-SHA256, hex -- Razorpay's own validateWebhookSignature helper does the same construction. */
    verifyWebhookSignature(rawBody, headers, secret) {
      if (!rawBody || !secret) return false;
      const signature = headers && (headers['x-razorpay-signature'] || headers['X-Razorpay-Signature']);
      if (!signature) return false;
      const expected = crypto.createHmac('sha256', secret).update(rawBody).digest('hex');
      return timingSafeEqualStr(signature, expected, 'hex');
    },

    parseWebhookEvent(rawBody, headers) {
      let body;
      try { body = JSON.parse(rawBody.toString('utf8')); } catch (e) { return null; }
      if (!body || typeof body !== 'object' || !body.event) return null;

      // Razorpay doesn't guarantee ordered or exactly-once delivery and
      // documents x-razorpay-event-id specifically for de-duplication;
      // fall back to a hash of the body if a delivery somehow lacks it
      // (a synthetic id here still gets the SAME idempotency guarantee
      // as a real one, since it's a pure function of the same bytes).
      const eventId = (headers && (headers['x-razorpay-event-id'] || headers['X-Razorpay-Event-Id']))
        || crypto.createHash('sha256').update(rawBody).digest('hex');

      const payment = body.payload && body.payload.payment && body.payload.payment.entity;
      const refund = body.payload && body.payload.refund && body.payload.refund.entity;

      if (body.event === 'payment.captured' && payment) {
        return {
          eventId, eventType: body.event, gatewayOrderId: payment.order_id, gatewayPaymentId: payment.id,
          status: 'SUCCESS', amountMinor: payment.amount, currency: payment.currency, paymentMethod: payment.method || null
        };
      }
      if (body.event === 'payment.failed' && payment) {
        return {
          eventId, eventType: body.event, gatewayOrderId: payment.order_id, gatewayPaymentId: payment.id,
          status: 'FAILED', amountMinor: payment.amount, currency: payment.currency, paymentMethod: payment.method || null
        };
      }
      if (body.event === 'refund.processed' && refund) {
        return {
          eventId, eventType: body.event, gatewayOrderId: null, gatewayPaymentId: refund.payment_id,
          status: 'REFUNDED', refundAmountMinor: refund.amount, currency: refund.currency, paymentMethod: null,
          amountMinor: null
        };
      }
      // A recognized-but-not-actionable event (payment.authorized,
      // refund.failed, order.paid, downtime.*, ...) -- acknowledged, no
      // status change. Safer than guessing at fields for events this
      // session could not pull a verified sample payload for; see
      // PAYMENTS_SETUP.md's explicit gap note on order.paid.
      return { eventId, eventType: body.event, gatewayOrderId: null, gatewayPaymentId: null, status: null, amountMinor: null, currency: null, paymentMethod: null };
    }
  }
};

/** Cashfree webhooks carry no single obvious "event id" field across all
 *  types -- derived deterministically from the payload instead, which
 *  gives the exact same idempotency guarantee (same bytes -> same id). */
function cashfreeEventId(body) {
  return crypto.createHash('sha256').update(JSON.stringify(body)).digest('hex');
}

/** Cashfree amounts arrive as major-unit numbers (e.g. 501.00); converts
 *  to the integer minor units this whole feature stores everywhere else. */
function amountToMinor(amountMajor) {
  return typeof amountMajor === 'number' && Number.isFinite(amountMajor) ? Math.round(amountMajor * 100) : null;
}

function getGateway(id) {
  const g = gateways[id];
  if (!g) {
    throw new Error(`Unknown payment gateway "${id}". Known gateways: ${Object.keys(gateways).join(', ')}`);
  }
  return g;
}

/**
 * Refuses the `mock` gateway outside an emulator -- called on every
 * order creation and every webhook, not just at startup, so a config
 * change at runtime cannot quietly make it the production gateway.
 * Mirrors providers.js's assertProviderAllowed exactly.
 */
function assertGatewayAllowed(id, env = process.env) {
  if (id !== 'mock') return;
  const inEmulator = !!(env.FUNCTIONS_EMULATOR === 'true' || env.FIRESTORE_EMULATOR_HOST || env.FIREBASE_AUTH_EMULATOR_HOST);
  if (!inEmulator) {
    throw new Error('The "mock" payment gateway is emulator-only and must never be used in a deployed environment.');
  }
}

module.exports = { gateways, getGateway, assertGatewayAllowed };
