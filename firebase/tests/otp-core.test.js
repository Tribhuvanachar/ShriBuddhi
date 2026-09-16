// Tests for the OTP state machine — expiry, attempt caps, rate limits,
// hashing, phone normalization.
//
// These run with zero credentials and zero network: `node --test`. Every
// function in otp-core.js takes `now` explicitly, which is what lets the
// expiry and rate-limit cases below be tested honestly instead of with
// sleeps.
'use strict';

const { test, describe } = require('node:test');
const assert = require('node:assert/strict');

const otp = require('../functions/lib/otp-core');

const PEPPER = 'test-pepper-not-a-real-one';

describe('normalizePhone', () => {
  test('accepts a well-formed international number', () => {
    assert.equal(otp.normalizePhone('+919876543210'), '+919876543210');
  });

  test('strips the separators humans actually type', () => {
    assert.equal(otp.normalizePhone('+91 98765-43210'), '+919876543210');
    assert.equal(otp.normalizePhone('+91 (98765) 43210'), '+919876543210');
    assert.equal(otp.normalizePhone('  +91.98765.43210  '), '+919876543210');
  });

  test('applies the default country code to a bare national number', () => {
    assert.equal(otp.normalizePhone('9876543210', '91'), '+919876543210');
  });

  test('drops the trunk 0 prefix on a national number', () => {
    assert.equal(otp.normalizePhone('09876543210', '91'), '+919876543210');
  });

  test('refuses a bare national number when no default country is configured', () => {
    // The important one: guessing a country here would mean sending a
    // code to a completely different person's phone.
    assert.equal(otp.normalizePhone('9876543210'), null);
  });

  test('rejects junk, empties and non-strings', () => {
    assert.equal(otp.normalizePhone(''), null);
    assert.equal(otp.normalizePhone('   '), null);
    assert.equal(otp.normalizePhone('not a phone'), null);
    assert.equal(otp.normalizePhone(null), null);
    assert.equal(otp.normalizePhone(undefined), null);
    assert.equal(otp.normalizePhone(919876543210), null);
    assert.equal(otp.normalizePhone('+'), null);
  });

  test('rejects numbers outside E.164 length limits', () => {
    assert.equal(otp.normalizePhone('+1234567'), null);            // too short
    assert.equal(otp.normalizePhone('+1234567890123456'), null);   // 16 digits
    assert.equal(otp.normalizePhone('+12345678'), '+12345678');    // 8 is the floor
    assert.equal(otp.normalizePhone('+123456789012345'), '+123456789012345'); // 15 is the ceiling
  });

  test('rejects a national number that is only zeroes', () => {
    assert.equal(otp.normalizePhone('0000', '91'), null);
  });
});

describe('generateOtp', () => {
  test('produces the requested number of digits', () => {
    for (const n of [4, 6, 8, 10]) {
      assert.match(otp.generateOtp(n), new RegExp(`^[0-9]{${n}}$`));
    }
  });

  test('defaults to 6 digits', () => {
    assert.match(otp.generateOtp(), /^[0-9]{6}$/);
  });

  test('rejects absurd lengths rather than silently clamping', () => {
    assert.throws(() => otp.generateOtp(3), /between 4 and 10/);
    assert.throws(() => otp.generateOtp(11), /between 4 and 10/);
    assert.throws(() => otp.generateOtp(6.5), /between 4 and 10/);
  });

  test('does not repeat itself across many draws', () => {
    // Not a randomness test — a smoke test that the generator is not
    // stuck returning a constant, which is a real failure mode when a
    // RNG is misused and would make every code guessable.
    const seen = new Set();
    for (let i = 0; i < 500; i++) seen.add(otp.generateOtp());
    assert.ok(seen.size > 450, `expected mostly-distinct codes, got ${seen.size}/500`);
  });

  test('uses the whole digit range in every position', () => {
    // Catches a modulo-bias or off-by-one that would strand a digit.
    const perPosition = [new Set(), new Set(), new Set(), new Set(), new Set(), new Set()];
    for (let i = 0; i < 2000; i++) {
      const code = otp.generateOtp();
      for (let p = 0; p < 6; p++) perPosition[p].add(code[p]);
    }
    for (let p = 0; p < 6; p++) {
      assert.equal(perPosition[p].size, 10, `position ${p} never saw all 10 digits`);
    }
  });
});

describe('hashOtp / safeEqualHex', () => {
  test('is deterministic for the same salt and code', () => {
    assert.equal(otp.hashOtp('123456', 'salt'), otp.hashOtp('123456', 'salt'));
  });

  test('differs for the same code under a different salt', () => {
    // This is the property that stops one leaked hash from identifying
    // the same code in every other challenge.
    assert.notEqual(otp.hashOtp('123456', 'saltA'), otp.hashOtp('123456', 'saltB'));
  });

  test('never contains the plaintext code', () => {
    assert.ok(!otp.hashOtp('123456', 'salt').includes('123456'));
  });

  test('safeEqualHex matches equal strings and rejects everything else', () => {
    assert.equal(otp.safeEqualHex('abc123', 'abc123'), true);
    assert.equal(otp.safeEqualHex('abc123', 'abc124'), false);
    assert.equal(otp.safeEqualHex('abc', 'abc123'), false);  // length mismatch
    assert.equal(otp.safeEqualHex(null, 'abc'), false);
    assert.equal(otp.safeEqualHex('abc', undefined), false);
    assert.equal(otp.safeEqualHex('', ''), true);
  });
});

describe('checkSendRateLimit', () => {
  const NOW = 1_000_000_000_000;

  test('allows the first ever send', () => {
    assert.deepEqual(otp.checkSendRateLimit(null, NOW), { allowed: true });
  });

  test('blocks a resend inside the cooldown', () => {
    const existing = { lastSentAt: NOW - 10_000, sendCount: 1, windowStartedAt: NOW - 10_000 };
    const r = otp.checkSendRateLimit(existing, NOW);
    assert.equal(r.allowed, false);
    assert.equal(r.reason, 'cooldown');
    assert.equal(r.retryAfterMs, 50_000);
  });

  test('allows a resend once the cooldown has elapsed', () => {
    const existing = { lastSentAt: NOW - 61_000, sendCount: 1, windowStartedAt: NOW - 61_000 };
    assert.equal(otp.checkSendRateLimit(existing, NOW).allowed, true);
  });

  test('blocks once the hourly cap is reached', () => {
    // The limit that actually protects the bill: without it, a script
    // requesting codes in a loop bills a paid message every time.
    const existing = { lastSentAt: NOW - 120_000, sendCount: 5, windowStartedAt: NOW - 600_000 };
    const r = otp.checkSendRateLimit(existing, NOW);
    assert.equal(r.allowed, false);
    assert.equal(r.reason, 'too_many_requests');
    assert.ok(r.retryAfterMs > 0);
  });

  test('lets sends resume once the window has fully elapsed', () => {
    const existing = { lastSentAt: NOW - 3_600_001, sendCount: 99, windowStartedAt: NOW - 3_600_001 };
    assert.equal(otp.checkSendRateLimit(existing, NOW).allowed, true);
  });

  test('honours overridden limits', () => {
    const existing = { lastSentAt: NOW - 5_000, sendCount: 1, windowStartedAt: NOW - 5_000 };
    assert.equal(otp.checkSendRateLimit(existing, NOW, { resendCooldownMs: 1_000 }).allowed, true);
    assert.equal(otp.checkSendRateLimit(existing, NOW, { resendCooldownMs: 60_000 }).allowed, false);
  });

  test('treats a challenge with missing counters as sendable', () => {
    assert.equal(otp.checkSendRateLimit({}, NOW).allowed, true);
  });
});

describe('buildChallenge', () => {
  const NOW = 1_000_000_000_000;

  test('stores a hash and never the code itself', () => {
    const c = otp.buildChallenge({ code: '123456', now: NOW });
    assert.ok(c.codeHash);
    assert.equal(JSON.stringify(c).includes('123456'), false);
    assert.equal(otp.hashOtp('123456', c.salt), c.codeHash);
  });

  test('sets expiry, zero attempts and unconsumed state', () => {
    const c = otp.buildChallenge({ code: '123456', now: NOW });
    assert.equal(c.expiresAt, NOW + otp.DEFAULT_TTL_MS);
    assert.equal(c.attempts, 0);
    assert.equal(c.consumed, false);
  });

  test('gives each challenge a distinct salt', () => {
    const a = otp.buildChallenge({ code: '123456', now: NOW });
    const b = otp.buildChallenge({ code: '123456', now: NOW });
    assert.notEqual(a.salt, b.salt);
    assert.notEqual(a.codeHash, b.codeHash);
  });

  test('carries the send counter forward inside an open window', () => {
    // The bypass this prevents: if asking for a new code reset the
    // counter, the hourly cap would be meaningless.
    const existing = { windowStartedAt: NOW - 600_000, sendCount: 3 };
    const c = otp.buildChallenge({ code: '123456', now: NOW, existing });
    assert.equal(c.sendCount, 4);
    assert.equal(c.windowStartedAt, NOW - 600_000);
  });

  test('resets the counter once the window has elapsed', () => {
    const existing = { windowStartedAt: NOW - 3_600_001, sendCount: 5 };
    const c = otp.buildChallenge({ code: '123456', now: NOW, existing });
    assert.equal(c.sendCount, 1);
    assert.equal(c.windowStartedAt, NOW);
  });

  test('resets attempts, so a new code is not born already burned', () => {
    const existing = { windowStartedAt: NOW - 1000, sendCount: 1, attempts: 5, consumed: true };
    const c = otp.buildChallenge({ code: '999999', now: NOW, existing });
    assert.equal(c.attempts, 0);
    assert.equal(c.consumed, false);
  });
});

describe('verifyChallenge', () => {
  const NOW = 1_000_000_000_000;

  function challengeFor(code, overrides = {}) {
    return Object.assign(otp.buildChallenge({ code, now: NOW }), overrides);
  }

  test('accepts the correct code and burns the challenge', () => {
    const c = challengeFor('123456');
    const r = otp.verifyChallenge(c, '123456', NOW + 1000);
    assert.equal(r.ok, true);
    assert.equal(r.patch.consumed, true);
  });

  test('tolerates surrounding whitespace in what the user pasted', () => {
    const c = challengeFor('123456');
    assert.equal(otp.verifyChallenge(c, '  123456  ', NOW + 1000).ok, true);
  });

  test('rejects a wrong code and counts the attempt', () => {
    const c = challengeFor('123456');
    const r = otp.verifyChallenge(c, '654321', NOW + 1000);
    assert.equal(r.ok, false);
    assert.equal(r.reason, 'incorrect');
    assert.equal(r.patch.attempts, 1);
  });

  test('rejects a code that has expired', () => {
    const c = challengeFor('123456');
    const r = otp.verifyChallenge(c, '123456', NOW + otp.DEFAULT_TTL_MS);
    assert.equal(r.ok, false);
    assert.equal(r.reason, 'expired');
  });

  test('rejects the correct code one millisecond after expiry', () => {
    const c = challengeFor('123456');
    assert.equal(otp.verifyChallenge(c, '123456', NOW + otp.DEFAULT_TTL_MS - 1).ok, true);
    assert.equal(otp.verifyChallenge(c, '123456', NOW + otp.DEFAULT_TTL_MS).ok, false);
  });

  test('refuses to replay an already-used code', () => {
    // Stops a code seen once — on a shared device's lock screen, say —
    // from being used again later.
    const c = challengeFor('123456', { consumed: true });
    const r = otp.verifyChallenge(c, '123456', NOW + 1000);
    assert.equal(r.ok, false);
    assert.equal(r.reason, 'already_used');
  });

  test('refuses the correct code once attempts are exhausted', () => {
    // The brute-force stop: a burned challenge cannot be revived by
    // eventually guessing right.
    const c = challengeFor('123456', { attempts: otp.DEFAULT_MAX_ATTEMPTS });
    const r = otp.verifyChallenge(c, '123456', NOW + 1000);
    assert.equal(r.ok, false);
    assert.equal(r.reason, 'too_many_attempts');
  });

  test('reports too_many_attempts on the attempt that exhausts the cap', () => {
    const c = challengeFor('123456', { attempts: otp.DEFAULT_MAX_ATTEMPTS - 1 });
    const r = otp.verifyChallenge(c, '000000', NOW + 1000);
    assert.equal(r.ok, false);
    assert.equal(r.reason, 'too_many_attempts');
    assert.equal(r.patch.attempts, otp.DEFAULT_MAX_ATTEMPTS);
  });

  test('a full brute-force run never succeeds after the cap', () => {
    let c = challengeFor('999999');
    for (let i = 0; i < otp.DEFAULT_MAX_ATTEMPTS; i++) {
      const r = otp.verifyChallenge(c, String(100000 + i), NOW + 1000);
      assert.equal(r.ok, false);
      c = Object.assign({}, c, r.patch);
    }
    const finally_ = otp.verifyChallenge(c, '999999', NOW + 1000);
    assert.equal(finally_.ok, false, 'correct code must not work once the cap is hit');
  });

  test('rejects a missing challenge', () => {
    assert.deepEqual(otp.verifyChallenge(null, '123456', NOW), { ok: false, reason: 'no_challenge' });
  });

  test('rejects malformed submissions and still counts them', () => {
    const c = challengeFor('123456');
    for (const bad of ['', '   ', 'abcdef', '12', '12345678901', null, undefined, 123456]) {
      const r = otp.verifyChallenge(c, bad, NOW + 1000);
      assert.equal(r.ok, false, `submission ${JSON.stringify(bad)} must not verify`);
    }
    assert.equal(otp.verifyChallenge(c, 'abcdef', NOW + 1000).reason, 'malformed');
  });

  test('honours a custom attempt cap', () => {
    const c = challengeFor('123456', { attempts: 2 });
    assert.equal(otp.verifyChallenge(c, '123456', NOW + 1000, { maxAttempts: 2 }).reason, 'too_many_attempts');
    assert.equal(otp.verifyChallenge(c, '123456', NOW + 1000, { maxAttempts: 3 }).ok, true);
  });

  test('a code from one challenge does not verify against another', () => {
    // Different salts mean a code captured for one phone number is
    // useless against a different challenge even if the digits match.
    const a = otp.buildChallenge({ code: '123456', now: NOW });
    const b = otp.buildChallenge({ code: '123456', now: NOW });
    const mixed = Object.assign({}, b, { salt: a.salt });
    assert.equal(otp.verifyChallenge(mixed, '123456', NOW + 1000).ok, false);
  });
});

describe('challengeDocId / phoneUid', () => {
  test('are deterministic for the same phone and pepper', () => {
    assert.equal(otp.challengeDocId('+919876543210', PEPPER), otp.challengeDocId('+919876543210', PEPPER));
    assert.equal(otp.phoneUid('+919876543210', PEPPER), otp.phoneUid('+919876543210', PEPPER));
  });

  test('never embed the phone number', () => {
    // A listing of document IDs must not be a listing of the site's
    // users' phone numbers.
    assert.ok(!otp.challengeDocId('+919876543210', PEPPER).includes('9876543210'));
    assert.ok(!otp.phoneUid('+919876543210', PEPPER).includes('9876543210'));
  });

  test('differ between phone numbers and between peppers', () => {
    assert.notEqual(otp.challengeDocId('+919876543210', PEPPER), otp.challengeDocId('+919876543211', PEPPER));
    assert.notEqual(otp.challengeDocId('+919876543210', PEPPER), otp.challengeDocId('+919876543210', 'other'));
  });

  test('the doc ID and the UID for one number are different values', () => {
    // They are derived from the same input; domain separation stops the
    // public-ish UID from revealing the challenge document's location.
    const phone = '+919876543210';
    assert.notEqual(otp.challengeDocId(phone, PEPPER), otp.phoneUid(phone, PEPPER).replace('phone_', ''));
  });

  test('produce a UID within Firebase limits', () => {
    const uid = otp.phoneUid('+919876543210', PEPPER);
    assert.ok(uid.length <= 128);
    assert.match(uid, /^phone_[0-9a-f]{32}$/);
  });

  test('refuse to run without a pepper', () => {
    assert.throws(() => otp.challengeDocId('+919876543210', ''), /pepper/);
    assert.throws(() => otp.phoneUid('+919876543210', null), /pepper/);
  });
});
