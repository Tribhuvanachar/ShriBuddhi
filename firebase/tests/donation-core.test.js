// Tests for donation-core.js — input validation, sanitization, amount
// handling, and donation-reference generation. Zero credentials, zero
// network: `node --test`.
'use strict';

const { test, describe } = require('node:test');
const assert = require('node:assert/strict');

const dc = require('../functions/lib/donation-core');

describe('sanitizeDisplayText', () => {
  test('strips tags and collapses whitespace', () => {
    assert.equal(dc.sanitizeDisplayText('  <b>Sri   Example</b>  ', 50), 'Sri Example');
  });

  test('strips a script tag entirely, including its content markers', () => {
    // The XSS case: a name typed as an attack must come out as inert text.
    const out = dc.sanitizeDisplayText('<script>alert(1)</script>Name', 50);
    assert.ok(!out.includes('<'), 'no angle bracket must survive');
    assert.ok(!out.includes('>'), 'no angle bracket must survive');
  });

  test('caps length', () => {
    const out = dc.sanitizeDisplayText('x'.repeat(500), 10);
    assert.equal(out.length, 10);
  });

  test('non-string input becomes empty string, not a throw', () => {
    assert.equal(dc.sanitizeDisplayText(undefined, 10), '');
    assert.equal(dc.sanitizeDisplayText(null, 10), '');
    assert.equal(dc.sanitizeDisplayText(12345, 10), '');
  });

  test('strips control characters', () => {
    // Built via fromCharCode rather than typed literally, so this test
    // file itself never contains a raw control byte.
    const withControlChars = 'a' + String.fromCharCode(1) + 'b' + String.fromCharCode(7) + 'c';
    assert.equal(dc.sanitizeDisplayText(withControlChars, 10), 'a b c');
  });
});

describe('isValidEmail', () => {
  test('accepts ordinary addresses', () => {
    assert.equal(dc.isValidEmail('person@example.com'), true);
    assert.equal(dc.isValidEmail(' person@example.com '), true);
  });
  test('rejects obviously-not-an-email strings', () => {
    for (const bad of ['not-an-email', 'a@b', '@example.com', 'a b@example.com', '', null, undefined, 42]) {
      assert.equal(dc.isValidEmail(bad), false, `expected ${JSON.stringify(bad)} to be invalid`);
    }
  });
});

describe('isPlausiblePhone', () => {
  test('empty/absent is fine — phone is optional', () => {
    assert.equal(dc.isPlausiblePhone(''), true);
    assert.equal(dc.isPlausiblePhone(null), true);
    assert.equal(dc.isPlausiblePhone(undefined), true);
  });
  test('accepts a plausible digit count', () => {
    assert.equal(dc.isPlausiblePhone('+91 98765 43210'), true);
  });
  test('rejects too short or too long', () => {
    assert.equal(dc.isPlausiblePhone('12345'), false);
    assert.equal(dc.isPlausiblePhone('1'.repeat(20)), false);
  });
});

describe('validateDonorInput', () => {
  test('accepts a well-formed submission and returns sanitized fields', () => {
    const r = dc.validateDonorInput({ name: 'Sri Example', email: 'Person@Example.com', phone: '9876543210', country: 'in' });
    assert.equal(r.ok, true);
    assert.deepEqual(r.errors, []);
    assert.equal(r.donor.email, 'person@example.com'); // lowercased
    assert.equal(r.donor.countryCode, 'IN');
  });

  test('rejects a missing name, invalid email, and bad country together', () => {
    const r = dc.validateDonorInput({ name: '   ', email: 'nope', country: 'usa' });
    assert.equal(r.ok, false);
    assert.ok(r.errors.some(e => e.includes('name')));
    assert.ok(r.errors.some(e => e.includes('email')));
    assert.ok(r.errors.some(e => e.includes('country')));
  });

  test('a name that is pure markup (no text between the tags) sanitizes to empty and is rejected', () => {
    const r = dc.validateDonorInput({ name: '  <b></b>  <i></i>  ', email: 'e@x.com', country: 'IN' });
    assert.equal(r.ok, false);
    assert.ok(r.errors.some(e => e.includes('name')));
  });

  test('PAN is optional; a present-but-malformed one is rejected', () => {
    const ok = dc.validateDonorInput({ name: 'X', email: 'e@x.com', country: 'IN' });
    assert.equal(ok.ok, true);
    assert.equal(ok.donor.pan, '');

    const bad = dc.validateDonorInput({ name: 'X', email: 'e@x.com', country: 'IN', pan: 'not-a-pan' });
    assert.equal(bad.ok, false);
    assert.ok(bad.errors.some(e => e.includes('PAN')));

    const good = dc.validateDonorInput({ name: 'X', email: 'e@x.com', country: 'IN', pan: 'abcde1234f' });
    assert.equal(good.ok, true);
    assert.equal(good.donor.pan, 'ABCDE1234F');
  });
});

describe('majorToMinor', () => {
  test('converts a plain rupee amount', () => {
    assert.equal(dc.majorToMinor(1001), 100100);
    assert.equal(dc.majorToMinor('1001.50'), 100150);
  });
  test('rejects more than 2 decimal places rather than rounding', () => {
    assert.equal(dc.majorToMinor('10.005'), null);
    assert.equal(dc.majorToMinor(10.999), null);
  });
  test('rejects non-positive, NaN, and Infinity', () => {
    for (const bad of [0, -100, 'abc', NaN, Infinity, -Infinity, null, undefined]) {
      assert.equal(dc.majorToMinor(bad), null, `expected ${bad} to be rejected`);
    }
  });
});

describe('validateAmountMinor', () => {
  test('accepts an amount within the default bounds', () => {
    assert.equal(dc.validateAmountMinor(100100).ok, true);
  });
  test('rejects a non-integer', () => {
    assert.equal(dc.validateAmountMinor(100.5).ok, false);
  });
  test('rejects below the minimum and above the maximum', () => {
    assert.equal(dc.validateAmountMinor(1).ok, false);
    assert.equal(dc.validateAmountMinor(dc.DEFAULT_MAX_AMOUNT_MINOR + 1).ok, false);
  });
  test('respects overridden bounds', () => {
    assert.equal(dc.validateAmountMinor(50, { minAmountMinor: 100 }).ok, false);
    assert.equal(dc.validateAmountMinor(150, { minAmountMinor: 100, maxAmountMinor: 200 }).ok, true);
  });
});

describe('generateDonationReference / isWellFormedDonationReference', () => {
  test('shape is DGE-YYYYMMDD-XXXXXX', () => {
    const ref = dc.generateDonationReference(Date.UTC(2026, 8, 8)); // month is 0-indexed: September
    assert.match(ref, /^DGE-20260908-[0-9A-HJKMNP-TV-Z]{6}$/);
    assert.equal(dc.isWellFormedDonationReference(ref), true);
  });

  test('never contains the excluded look-alike characters I, L, O, U', () => {
    // Run many times since the suffix is random — this asserts the
    // ALPHABET excludes them, not just that one draw happened to.
    for (let i = 0; i < 200; i++) {
      const ref = dc.generateDonationReference(Date.now());
      const suffix = ref.split('-')[2];
      assert.ok(!/[ILOU]/.test(suffix), `suffix ${suffix} contained an excluded character`);
    }
  });

  test('is injectable for deterministic tests', () => {
    const fixedBytes = () => Buffer.from([0, 1, 2, 3, 4, 5]);
    const ref = dc.generateDonationReference(Date.UTC(2026, 0, 1), fixedBytes);
    // bytes 0..5 are each < 33 (the alphabet length), so `% 33` is the
    // identity and the suffix is just the alphabet's own first 6 characters.
    assert.equal(ref, 'DGE-20260101-012345');
  });

  test('same day, different random bytes, gives different references', () => {
    const a = dc.generateDonationReference(Date.UTC(2026, 0, 1), () => Buffer.from([1, 1, 1, 1, 1, 1]));
    const b = dc.generateDonationReference(Date.UTC(2026, 0, 1), () => Buffer.from([2, 2, 2, 2, 2, 2]));
    assert.notEqual(a, b);
  });

  test('isWellFormedDonationReference rejects garbage', () => {
    for (const bad of ['', 'DGE-123-ABCDEF', 'dge-20260908-abcdef', 'DGE-20260908-ABCDEI', null, undefined, 42]) {
      assert.equal(dc.isWellFormedDonationReference(bad), false, `expected ${bad} to be rejected`);
    }
  });
});
