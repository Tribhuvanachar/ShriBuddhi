// Tests for broadcast audience selection.
//
// Weighted deliberately towards the exclusion cases. Sending a broadcast
// to someone who opted out is a compliance breach and a fast route to
// Meta throttling the number; sending a campaign twice is a real bill,
// twice. Both are decided by isEligible, so both are pinned here.
'use strict';

const { test, describe } = require('node:test');
const assert = require('node:assert/strict');

const bc = require('../functions/lib/broadcast-core');

const NOW = 1_000_000_000_000;

function user(overrides = {}) {
  return Object.assign({
    id: 'u1',
    phoneNumber: '+919876543210',
    role: 'basic',
    whatsappOptIn: true
  }, overrides);
}

const campaign = { id: 'c1', templateName: 'daily_shloka' };

describe('isEligible', () => {
  test('accepts an opted-in user with a phone number', () => {
    assert.deepEqual(bc.isEligible(user(), campaign, NOW), { eligible: true });
  });

  test('rejects a user who never opted in', () => {
    assert.equal(bc.isEligible(user({ whatsappOptIn: false }), campaign, NOW).reason, 'not_opted_in');
    assert.equal(bc.isEligible(user({ whatsappOptIn: undefined }), campaign, NOW).reason, 'not_opted_in');
  });

  test('treats a non-boolean opt-in as no consent', () => {
    // Consent must be an explicit true. A truthy string is a data bug,
    // not permission to message someone.
    for (const value of ['true', 1, {}, [], 'yes']) {
      assert.equal(bc.isEligible(user({ whatsappOptIn: value }), campaign, NOW).eligible, false,
        `opt-in value ${JSON.stringify(value)} must not count as consent`);
    }
  });

  test('an opt-out beats a contradictory opt-in flag', () => {
    // If the record contradicts itself, the safe direction is silence.
    const u = user({ whatsappOptIn: true, whatsappOptOutAt: NOW - 1000 });
    assert.equal(bc.isEligible(u, campaign, NOW).reason, 'opted_out');
  });

  test('rejects a user with no phone number', () => {
    assert.equal(bc.isEligible(user({ phoneNumber: null }), campaign, NOW).reason, 'no_phone');
    assert.equal(bc.isEligible(user({ phoneNumber: '' }), campaign, NOW).reason, 'no_phone');
  });

  test('rejects a number that has hard-bounced', () => {
    assert.equal(bc.isEligible(user({ whatsappUndeliverable: true }), campaign, NOW).reason, 'undeliverable');
  });

  test('rejects a user who already received this campaign', () => {
    // The idempotency guard that makes re-running a failed job safe.
    const u = user({ whatsappCampaigns: { c1: NOW - 5000 } });
    assert.equal(bc.isEligible(u, campaign, NOW).reason, 'already_sent');
  });

  test('still sends a DIFFERENT campaign to someone who got an earlier one', () => {
    const u = user({ whatsappCampaigns: { c0: NOW - 5000 } });
    assert.equal(bc.isEligible(u, campaign, NOW).eligible, true);
  });

  test('honours role targeting', () => {
    const targeted = Object.assign({}, campaign, { roles: ['sponsor', 'subscriber'] });
    assert.equal(bc.isEligible(user({ role: 'sponsor' }), targeted, NOW).eligible, true);
    assert.equal(bc.isEligible(user({ role: 'basic' }), targeted, NOW).reason, 'role_excluded');
  });

  test('treats a user with no role as basic for targeting', () => {
    const targeted = Object.assign({}, campaign, { roles: ['basic'] });
    assert.equal(bc.isEligible(user({ role: undefined }), targeted, NOW).eligible, true);
  });

  test('an empty roles list means everyone, not nobody', () => {
    const targeted = Object.assign({}, campaign, { roles: [] });
    assert.equal(bc.isEligible(user(), targeted, NOW).eligible, true);
  });

  test('enforces the frequency cap between broadcasts', () => {
    const capped = Object.assign({}, campaign, { minGapMs: 24 * 60 * 60 * 1000 });
    const recent = user({ whatsappLastBroadcastAt: NOW - 60 * 60 * 1000 });
    assert.equal(bc.isEligible(recent, capped, NOW).reason, 'frequency_capped');

    const older = user({ whatsappLastBroadcastAt: NOW - 25 * 60 * 60 * 1000 });
    assert.equal(bc.isEligible(older, capped, NOW).eligible, true);
  });

  test('no frequency cap configured means no cap applied', () => {
    const u = user({ whatsappLastBroadcastAt: NOW - 1000 });
    assert.equal(bc.isEligible(u, campaign, NOW).eligible, true);
  });

  test('rejects a null user rather than throwing', () => {
    assert.equal(bc.isEligible(null, campaign, NOW).reason, 'no_user');
  });

  test('survives a campaign object with no id', () => {
    assert.equal(bc.isEligible(user(), {}, NOW).eligible, true);
  });
});

describe('selectAudience', () => {
  test('partitions users and tallies why each was skipped', () => {
    const users = [
      user({ id: 'a' }),
      user({ id: 'b' }),
      user({ id: 'c', whatsappOptIn: false }),
      user({ id: 'd', whatsappOptOutAt: NOW }),
      user({ id: 'e', phoneNumber: null }),
      user({ id: 'f', whatsappCampaigns: { c1: NOW } })
    ];
    const { recipients, skipped, total } = bc.selectAudience(users, campaign, NOW);
    assert.equal(total, 6);
    assert.deepEqual(recipients.map(u => u.id), ['a', 'b']);
    assert.deepEqual(skipped, { not_opted_in: 1, opted_out: 1, no_phone: 1, already_sent: 1 });
  });

  test('handles an empty user list', () => {
    assert.deepEqual(bc.selectAudience([], campaign, NOW), { recipients: [], skipped: {}, total: 0 });
  });

  test('a list where nobody qualifies produces no recipients', () => {
    const users = [user({ whatsappOptIn: false }), user({ whatsappOptIn: false })];
    const { recipients, skipped } = bc.selectAudience(users, campaign, NOW);
    assert.equal(recipients.length, 0);
    assert.equal(skipped.not_opted_in, 2);
  });
});

describe('batch', () => {
  test('splits into full batches plus a remainder', () => {
    assert.deepEqual(bc.batch([1, 2, 3, 4, 5], 2), [[1, 2], [3, 4], [5]]);
  });

  test('returns one batch when the size exceeds the list', () => {
    assert.deepEqual(bc.batch([1, 2], 10), [[1, 2]]);
  });

  test('returns nothing for an empty list', () => {
    assert.deepEqual(bc.batch([], 5), []);
  });

  test('rejects a nonsensical batch size instead of looping forever', () => {
    // A size of 0 would make the loop in batch() never advance.
    assert.throws(() => bc.batch([1], 0), /positive integer/);
    assert.throws(() => bc.batch([1], -1), /positive integer/);
    assert.throws(() => bc.batch([1], 1.5), /positive integer/);
  });
});

describe('applySendCap', () => {
  test('passes everything through when under the cap', () => {
    const { toSend, deferred } = bc.applySendCap([1, 2, 3], 10);
    assert.deepEqual(toSend, [1, 2, 3]);
    assert.deepEqual(deferred, []);
  });

  test('splits at the cap and reports the remainder rather than dropping it', () => {
    // Silently truncating would make a partial send look complete.
    const { toSend, deferred } = bc.applySendCap([1, 2, 3, 4, 5], 2);
    assert.deepEqual(toSend, [1, 2]);
    assert.deepEqual(deferred, [3, 4, 5]);
  });

  test('treats a missing or zero cap as uncapped', () => {
    assert.deepEqual(bc.applySendCap([1, 2, 3], 0).toSend, [1, 2, 3]);
    assert.deepEqual(bc.applySendCap([1, 2, 3], null).toSend, [1, 2, 3]);
    assert.deepEqual(bc.applySendCap([1, 2, 3], undefined).toSend, [1, 2, 3]);
  });
});
