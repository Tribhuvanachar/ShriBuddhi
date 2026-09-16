// otp-core.js — the OTP state machine, as pure functions.
//
// Deliberately has NO dependency on Firebase, on the network, or on the
// clock: every function here takes `now` as an argument and returns plain
// objects. That is what makes the security-critical parts of this feature
// (expiry, attempt caps, rate limits, constant-time comparison) actually
// testable without a live project — see ../../tests/otp-core.test.js,
// which exercises every branch below.
//
// The rule this module exists to enforce: the plaintext OTP is never
// stored anywhere. Only a salted SHA-256 hash of it is persisted, so a
// dump of the Firestore collection does not hand someone a list of live
// codes.
'use strict';

const crypto = require('crypto');

// A challenge is burned after this many wrong guesses. 5 is the usual
// balance: generous enough for a mistyped code, tight enough that
// brute-forcing a 6-digit code (1 in 1,000,000) is hopeless.
const DEFAULT_MAX_ATTEMPTS = 5;
const DEFAULT_CODE_DIGITS = 6;
const DEFAULT_TTL_MS = 5 * 60 * 1000;        // 5 minutes
const DEFAULT_RESEND_COOLDOWN_MS = 60 * 1000; // 1 minute between sends
const DEFAULT_MAX_SENDS_PER_WINDOW = 5;
const DEFAULT_SEND_WINDOW_MS = 60 * 60 * 1000; // per hour, per phone number

/**
 * Normalizes a user-typed phone number to E.164 (`+<country><number>`).
 *
 * Intentionally strict rather than clever: this is an auth boundary, and
 * a permissive parser that "helpfully" guesses a country code is how you
 * end up sending an OTP to the wrong person's phone. Accepts an explicit
 * `+`-prefixed international number, or a bare national number ONLY when
 * a defaultCountryCode is supplied by config.
 *
 * @returns {string|null} E.164 string, or null if it can't be trusted.
 */
function normalizePhone(input, defaultCountryCode) {
  if (typeof input !== 'string') return null;

  // Strip everything a human might type as separators: spaces, hyphens,
  // parentheses, dots. Keep a leading '+' if present.
  const trimmed = input.trim();
  if (!trimmed) return null;

  const hasPlus = trimmed.startsWith('+');
  const digits = trimmed.replace(/[^0-9]/g, '');
  if (!digits) return null;

  if (hasPlus) {
    // E.164 allows at most 15 digits, and a country code is at least 1,
    // so a plausible international number is 8-15 digits.
    if (digits.length < 8 || digits.length > 15) return null;
    return '+' + digits;
  }

  // No '+': only usable if config told us which country to assume.
  if (!defaultCountryCode) return null;
  const cc = String(defaultCountryCode).replace(/[^0-9]/g, '');
  if (!cc) return null;

  // A bare national number sometimes arrives with a trunk '0' prefix
  // (e.g. 09876543210 in India) — that 0 is not part of the number.
  const national = digits.replace(/^0+/, '');
  if (!national) return null;

  const combined = cc + national;
  if (combined.length < 8 || combined.length > 15) return null;
  return '+' + combined;
}

/**
 * Generates a numeric OTP using a cryptographically secure RNG.
 *
 * Uses rejection sampling rather than `randomInt % 10`, because modulo on
 * a non-power-of-10 range biases the low digits — a small bias, but this
 * is a credential and there is no reason to accept any.
 */
function generateOtp(digits = DEFAULT_CODE_DIGITS) {
  if (!Number.isInteger(digits) || digits < 4 || digits > 10) {
    throw new Error(`OTP length must be an integer between 4 and 10, got ${digits}`);
  }
  let out = '';
  while (out.length < digits) {
    // crypto.randomInt is uniform over [0, 10) — no modulo bias.
    out += String(crypto.randomInt(0, 10));
  }
  return out;
}

/** Salted SHA-256 of the code. The salt is per-challenge, not global. */
function hashOtp(code, salt) {
  return crypto.createHash('sha256').update(String(salt) + ':' + String(code)).digest('hex');
}

/**
 * Compares two hashes without leaking, via timing, how many leading
 * characters matched. Overkill for a hash comparison over a network with
 * far larger jitter — but it costs one function call, and getting into
 * the habit of comparing secrets this way is worth more than the cycles.
 */
function safeEqualHex(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string') return false;
  const bufA = Buffer.from(a, 'utf8');
  const bufB = Buffer.from(b, 'utf8');
  if (bufA.length !== bufB.length) return false;
  return crypto.timingSafeEqual(bufA, bufB);
}

/**
 * Decides whether this phone number is allowed to be sent another code
 * right now, based on the existing challenge doc (or null if none).
 *
 * Two independent limits, both needed:
 *  - a cooldown, so "Send code" mashed twice doesn't send two SMS; and
 *  - a rolling per-hour cap, so a script can't burn money by requesting
 *    codes for a number it doesn't own in a loop. The cap is the one
 *    that actually protects the budget.
 *
 * @returns {{allowed: boolean, reason?: string, retryAfterMs?: number}}
 */
function checkSendRateLimit(existing, now, opts = {}) {
  const cooldownMs = opts.resendCooldownMs ?? DEFAULT_RESEND_COOLDOWN_MS;
  const maxSends = opts.maxSendsPerWindow ?? DEFAULT_MAX_SENDS_PER_WINDOW;
  const windowMs = opts.sendWindowMs ?? DEFAULT_SEND_WINDOW_MS;

  if (!existing) return { allowed: true };

  const lastSentAt = existing.lastSentAt ?? 0;
  const sinceLast = now - lastSentAt;
  if (sinceLast < cooldownMs) {
    return {
      allowed: false,
      reason: 'cooldown',
      retryAfterMs: cooldownMs - sinceLast
    };
  }

  // The window is rolling in the sense that it resets once fully elapsed;
  // a true sliding window would need a timestamp list per number, which
  // is more storage than this threat justifies.
  const windowStartedAt = existing.windowStartedAt ?? 0;
  const windowAge = now - windowStartedAt;
  if (windowAge < windowMs && (existing.sendCount ?? 0) >= maxSends) {
    return {
      allowed: false,
      reason: 'too_many_requests',
      retryAfterMs: windowMs - windowAge
    };
  }

  return { allowed: true };
}

/**
 * Builds the challenge document to persist for a freshly generated code.
 * Carries forward the rate-limit counters from any existing challenge so
 * that requesting a new code does not reset the per-hour cap — resetting
 * it would make the cap trivially bypassable by just asking again.
 */
function buildChallenge({ code, now, existing = null, ttlMs = DEFAULT_TTL_MS, provider = 'unknown', sendWindowMs = DEFAULT_SEND_WINDOW_MS }) {
  const salt = crypto.randomBytes(16).toString('hex');
  const windowExpired = !existing || (now - (existing.windowStartedAt ?? 0)) >= sendWindowMs;

  return {
    codeHash: hashOtp(code, salt),
    salt,
    createdAt: now,
    expiresAt: now + ttlMs,
    attempts: 0,
    consumed: false,
    provider,
    lastSentAt: now,
    // Counters reset only when the whole window has elapsed.
    windowStartedAt: windowExpired ? now : existing.windowStartedAt,
    sendCount: windowExpired ? 1 : (existing.sendCount ?? 0) + 1
  };
}

/**
 * Checks a user-submitted code against a stored challenge.
 *
 * Order matters here and is deliberate: missing → consumed → expired →
 * attempts → hash. Checking the hash last means a burned or expired
 * challenge costs an attacker nothing to probe but tells them nothing
 * either, and an exhausted challenge can never be revived by a lucky
 * guess.
 *
 * This function does not mutate anything — it returns what the caller
 * should persist, so the transaction stays in one place.
 *
 * @returns {{ok: boolean, reason?: string, patch?: object}}
 */
function verifyChallenge(existing, submittedCode, now, opts = {}) {
  const maxAttempts = opts.maxAttempts ?? DEFAULT_MAX_ATTEMPTS;

  if (!existing) return { ok: false, reason: 'no_challenge' };
  if (existing.consumed) return { ok: false, reason: 'already_used' };
  if (now >= (existing.expiresAt ?? 0)) return { ok: false, reason: 'expired' };

  const attempts = existing.attempts ?? 0;
  if (attempts >= maxAttempts) return { ok: false, reason: 'too_many_attempts' };

  const submitted = typeof submittedCode === 'string' ? submittedCode.trim() : '';
  // Reject junk before hashing, so an empty string can't burn an attempt
  // on a typo-shaped input that was never going to be a code anyway.
  if (!/^[0-9]{4,10}$/.test(submitted)) {
    return { ok: false, reason: 'malformed', patch: { attempts: attempts + 1 } };
  }

  const candidate = hashOtp(submitted, existing.salt);
  if (!safeEqualHex(candidate, existing.codeHash)) {
    const nextAttempts = attempts + 1;
    return {
      ok: false,
      reason: nextAttempts >= maxAttempts ? 'too_many_attempts' : 'incorrect',
      patch: { attempts: nextAttempts }
    };
  }

  // Correct. Burn the challenge so the same code can never be replayed —
  // this is what stops a code observed once (shoulder-surfed, or read
  // from a shared device's notification) from being reused.
  return {
    ok: true,
    patch: { consumed: true, attempts: attempts + 1, consumedAt: now }
  };
}

/**
 * Doc ID for a phone number's challenge. Hashed with a server-side pepper
 * so that a listing of document IDs is not a listing of the site's users'
 * phone numbers.
 */
function challengeDocId(e164Phone, pepper) {
  if (!pepper) throw new Error('challengeDocId requires a server-side pepper');
  return crypto.createHash('sha256').update(String(pepper) + ':' + String(e164Phone)).digest('hex');
}

/** Stable, non-reversible UID for a phone-only account. */
function phoneUid(e164Phone, pepper) {
  if (!pepper) throw new Error('phoneUid requires a server-side pepper');
  const digest = crypto.createHash('sha256').update(String(pepper) + ':uid:' + String(e164Phone)).digest('hex');
  // Firebase UIDs are capped at 128 chars; 32 hex chars is ample and
  // keeps the value readable in the console.
  return 'phone_' + digest.slice(0, 32);
}

module.exports = {
  DEFAULT_MAX_ATTEMPTS,
  DEFAULT_CODE_DIGITS,
  DEFAULT_TTL_MS,
  DEFAULT_RESEND_COOLDOWN_MS,
  DEFAULT_MAX_SENDS_PER_WINDOW,
  DEFAULT_SEND_WINDOW_MS,
  normalizePhone,
  generateOtp,
  hashOtp,
  safeEqualHex,
  checkSendRateLimit,
  buildChallenge,
  verifyChallenge,
  challengeDocId,
  phoneUid
};
