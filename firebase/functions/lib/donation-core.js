// donation-core.js — validation, sanitization and reference generation for
// the donation/supporter system, as pure functions.
//
// Same discipline as otp-core.js: no Firebase, no network, no ambient
// clock or randomness the caller didn't hand in — so every rule here
// (amount bounds, what a "safe" display name looks like, how a donation
// reference is shaped) is testable without a live project. index.js is
// the thin shell that calls these and does the Firestore/HTTP part.
//
// Money is stored as an INTEGER number of minor units (paise for INR,
// cents for USD, etc.), never a float. Firestore has no fixed-point
// decimal type -- only IEEE-754 doubles -- so a numeric(18,2) column
// (fine in Postgres) would be a silent rounding bug waiting to happen
// here. amountMinor is the one true amount everywhere in this feature; a
// UI converts it to/from a major-unit string only at the last moment.
'use strict';

const crypto = require('crypto');

const DEFAULT_MIN_AMOUNT_MINOR = 100;        // Rs.1.00 -- a symbolic floor mainly to reject 0/negative
const DEFAULT_MAX_AMOUNT_MINOR = 500000000;  // Rs.50,00,000 -- a sanity ceiling, not a real limit; revisit before it matters
const DEFAULT_CURRENCY = 'INR';
const MAX_NAME_LEN = 120;
const MAX_PURPOSE_LEN = 60;

// C0 control characters plus DEL -- stripped from any text a donor typed
// before it is stored or ever rendered anywhere (Supporters Wall, admin
// views, receipts).
const CONTROL_CHARS_RE = new RegExp('[\\u0000-\\u001F\\u007F]', 'g');

/**
 * Strips a display string down to plain text: no tags, no control
 * characters, collapsed whitespace, capped length. This is what stands
 * between a donor's typed name and both Firestore and a rendered
 * Supporters Wall -- it must survive a name containing markup without
 * ever needing the RENDERER to be the one being careful.
 */
function sanitizeDisplayText(input, maxLen) {
  if (typeof input !== 'string') return '';
  return input
    .replace(/<[^>]*>/g, ' ')       // strip anything tag-shaped
    .replace(CONTROL_CHARS_RE, ' ') // strip control characters
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, maxLen);
}

/**
 * A deliberately ordinary email check -- not a full RFC 5322 parser
 * (those accept addresses no mail server would), just enough to catch
 * "not an email at all" before it reaches a receipt-sending step.
 */
function isValidEmail(email) {
  if (typeof email !== 'string') return false;
  const s = email.trim();
  if (!s || s.length > 254) return false;
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(s);
}

/**
 * A light phone check for the donor record -- distinct from otp-core's
 * normalizePhone, which is an auth boundary and rightly stricter. A
 * donation's phone field is contact information, not a credential; a
 * malformed one should not block an otherwise-valid donation.
 */
function isPlausiblePhone(phone) {
  if (phone == null || phone === '') return true; // optional field
  if (typeof phone !== 'string') return false;
  const digits = phone.replace(/[^0-9]/g, '');
  return digits.length >= 7 && digits.length <= 15;
}

/**
 * Validates a donor's submitted name/email/phone/country. Returns the
 * SANITIZED fields to store, or a list of problems if the input can't be
 * trusted -- never throws, so index.js can turn `errors` into one
 * HttpsError with a message that names what's actually wrong.
 */
function validateDonorInput(input) {
  const errors = [];
  const raw = input || {};

  const fullName = sanitizeDisplayText(raw.name, MAX_NAME_LEN);
  if (!fullName) errors.push('name is required');

  const email = typeof raw.email === 'string' ? raw.email.trim().toLowerCase() : '';
  if (!isValidEmail(email)) errors.push('a valid email is required');

  const phone = typeof raw.phone === 'string' ? raw.phone.trim() : '';
  if (!isPlausiblePhone(phone)) errors.push('phone number does not look right');

  const countryCode = sanitizeDisplayText(raw.country, 4).toUpperCase();
  if (!/^[A-Z]{2}$/.test(countryCode)) errors.push('a two-letter country code is required');

  // PAN is optional at this layer -- whether it's legally required
  // depends on the Trust's actual receipt/tax workflow, which is not
  // decided yet (see PAYMENTS_SETUP.md). Only shape-checked when
  // present: 10 characters, the standard Indian PAN pattern.
  const panRaw = typeof raw.pan === 'string' ? raw.pan.trim().toUpperCase() : '';
  let pan = '';
  if (panRaw) {
    if (/^[A-Z]{5}[0-9]{4}[A-Z]$/.test(panRaw)) pan = panRaw;
    else errors.push('PAN does not look like a valid 10-character PAN');
  }

  return {
    ok: errors.length === 0,
    errors,
    donor: { fullName, email, phone, countryCode, pan }
  };
}

/**
 * Validates an amount already expressed in minor units (an integer). The
 * caller (index.js) is responsible for converting whatever the client
 * sent (typically a major-unit number like 1001 meaning Rs.1001) into
 * minor units BEFORE calling this -- kept as a separate, obvious step
 * (majorToMinor below) so the float-vs-integer boundary is one visible
 * line, not buried in validation.
 */
function validateAmountMinor(amountMinor, opts = {}) {
  const min = opts.minAmountMinor ?? DEFAULT_MIN_AMOUNT_MINOR;
  const max = opts.maxAmountMinor ?? DEFAULT_MAX_AMOUNT_MINOR;
  if (!Number.isInteger(amountMinor)) return { ok: false, reason: 'amount must be a whole number of minor units' };
  if (amountMinor < min) return { ok: false, reason: `amount is below the minimum (${min} minor units)` };
  if (amountMinor > max) return { ok: false, reason: `amount is above the maximum (${max} minor units)` };
  return { ok: true };
}

/**
 * Converts a client-submitted major-unit amount (e.g. 1001 or 1001.50
 * meaning Rs.1001.50) to an integer minor-unit amount. Rejects anything
 * that isn't a clean, finite number with at most 2 decimal places --
 * NaN, Infinity, -100, and 10.999 are all refused rather than silently
 * rounded, because a donation amount is exactly the kind of value that
 * must never be "close enough".
 *
 * @returns {number|null} integer minor units, or null if untrustworthy.
 */
function majorToMinor(amountMajor) {
  if (typeof amountMajor === 'string') amountMajor = amountMajor.trim();
  const n = Number(amountMajor);
  if (!Number.isFinite(n) || n <= 0) return null;
  // Reject more than 2 decimal places by checking the STRING, not by
  // rounding -- 10.005 should never quietly become 10.01 or 10.00.
  const str = String(amountMajor);
  const dot = str.indexOf('.');
  if (dot !== -1 && str.length - dot - 1 > 2) return null;
  const minor = Math.round(n * 100);
  return Number.isSafeInteger(minor) ? minor : null;
}

/**
 * The reverse of majorToMinor: an integer minor-unit amount to a clean
 * 2-decimal-place major-unit number, for gateways (Cashfree's Create
 * Order API) that want the amount expressed in rupees rather than paise.
 * Routed through toFixed(2)/Number() rather than a bare division so the
 * result is never something like 1001.3299999999999 -- division by 100
 * is exact for the specific values IEEE-754 doubles represent cleanly,
 * but not guaranteed for all of them, and a gateway request is not the
 * place to find out which.
 */
function minorToMajor(amountMinor) {
  if (!Number.isInteger(amountMinor)) throw new Error(`minorToMajor: amountMinor must be an integer, got ${amountMinor}`);
  return Number((amountMinor / 100).toFixed(2));
}

/**
 * Generates a donation reference: DGE-YYYYMMDD-XXXXXX, where XXXXXX is 6
 * cryptographically random uppercase base32-ish characters (Crockford's
 * alphabet, which drops ambiguous characters like 0/O and 1/I/L -- this
 * reference is read aloud on support calls and typed into a "check my
 * donation" box, so a shape that can't be confused character-by-character
 * matters more than raw entropy density).
 *
 * `now` and `randomBytesImpl` are both injected so this is testable
 * without depending on the real clock or truly consuming entropy per
 * test run.
 */
const CROCKFORD_ALPHABET = '0123456789ABCDEFGHJKMNPQRSTVWXYZ'; // no I, L, O, U
function generateDonationReference(now = Date.now(), randomBytesImpl = crypto.randomBytes) {
  const d = new Date(now);
  const y = d.getUTCFullYear();
  const m = String(d.getUTCMonth() + 1).padStart(2, '0');
  const day = String(d.getUTCDate()).padStart(2, '0');
  const bytes = randomBytesImpl(6);
  let suffix = '';
  for (let i = 0; i < 6; i++) suffix += CROCKFORD_ALPHABET[bytes[i] % CROCKFORD_ALPHABET.length];
  return `DGE-${y}${m}${day}-${suffix}`;
}

/** True for a string shaped like something generateDonationReference could have produced. */
function isWellFormedDonationReference(ref) {
  return typeof ref === 'string' && /^DGE-\d{8}-[0-9A-HJKMNP-TV-Z]{6}$/.test(ref);
}

module.exports = {
  DEFAULT_MIN_AMOUNT_MINOR,
  DEFAULT_MAX_AMOUNT_MINOR,
  DEFAULT_CURRENCY,
  MAX_PURPOSE_LEN,
  sanitizeDisplayText,
  isValidEmail,
  isPlausiblePhone,
  validateDonorInput,
  validateAmountMinor,
  majorToMinor,
  minorToMajor,
  generateDonationReference,
  isWellFormedDonationReference
};
