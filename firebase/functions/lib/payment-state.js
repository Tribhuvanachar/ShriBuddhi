// payment-state.js -- the donation payment state machine, as a pure
// function. Nothing here touches Firestore or a gateway SDK: it takes
// "here is the current status and here is what the gateway just told us"
// and returns "here is the next status, or here is why that's not a
// legal move" -- so every transition (and every rejected one) is
// testable without a live project or a real webhook.
//
// This is deliberately the ONLY place a donation's status is decided.
// index.js must never set `status` directly from a webhook payload's own
// status string -- it calls nextStatus() and persists whatever comes
// back, so an out-of-order or replayed webhook can never walk the
// donation backwards (e.g. a late PENDING event arriving after SUCCESS
// was already recorded).
'use strict';

// The only edges this machine allows. A gateway's own event vocabulary
// (however many statuses Cashfree/Razorpay/etc. use) gets normalized down
// to this small set BEFORE reaching this function -- see
// payment-providers.js's parseWebhookEvent, which is where a specific
// gateway's status strings map onto these.
const TRANSITIONS = {
  CREATED: ['PENDING', 'FAILED', 'CANCELLED'],
  PENDING: ['SUCCESS', 'FAILED', 'CANCELLED'],
  SUCCESS: ['REFUNDED', 'PARTIALLY_REFUNDED'],
  FAILED: [],           // terminal -- a failed attempt does not retry in place; the donor starts a new donation
  CANCELLED: [],         // terminal
  REFUNDED: [],          // terminal
  PARTIALLY_REFUNDED: ['REFUNDED'] // a partial refund can later be topped up to a full refund
};

const ALL_STATUSES = Object.keys(TRANSITIONS);

function isKnownStatus(s) {
  return typeof s === 'string' && ALL_STATUSES.includes(s);
}

/**
 * Is `from -> to` a legal single step? `from === to` is also allowed --
 * a duplicate webhook reporting the same status a donation already has
 * is not an error, it's the idempotent case, and the caller should treat
 * it as "nothing to do" rather than "invalid transition".
 */
function canTransition(from, to) {
  if (!isKnownStatus(from) || !isKnownStatus(to)) return false;
  if (from === to) return true;
  return TRANSITIONS[from].includes(to);
}

/**
 * Decides the next donation status given the current one and a
 * gateway-reported outcome, already normalized to one of ALL_STATUSES.
 *
 * @returns {{ok: boolean, changed: boolean, status?: string, reason?: string}}
 *   ok=false means the proposed status was not a legal move from here and
 *   MUST be logged, not silently applied, and MUST NOT throw -- an
 *   attacker-controlled or simply out-of-order webhook is not a reason to
 *   500 back to the gateway (which would just cause a retry storm).
 */
function nextStatus(currentStatus, reportedStatus) {
  if (!isKnownStatus(reportedStatus)) {
    return { ok: false, changed: false, reason: `unrecognized status "${reportedStatus}"` };
  }
  // A brand-new donation with no status yet only ever starts at CREATED
  // or PENDING -- treated as coming from CREATED.
  const from = isKnownStatus(currentStatus) ? currentStatus : 'CREATED';

  if (from === reportedStatus) {
    return { ok: true, changed: false, status: from };
  }
  if (!canTransition(from, reportedStatus)) {
    return {
      ok: false,
      changed: false,
      reason: `illegal transition ${from} -> ${reportedStatus} (a stale or out-of-order event)`
    };
  }
  return { ok: true, changed: true, status: reportedStatus };
}

/** True once a donation has reached a status nothing further can change automatically. */
function isTerminal(status) {
  return isKnownStatus(status) && TRANSITIONS[status].length === 0;
}

module.exports = { TRANSITIONS, ALL_STATUSES, isKnownStatus, canTransition, nextStatus, isTerminal };
