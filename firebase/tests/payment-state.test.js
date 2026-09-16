// Tests for payment-state.js — the donation status state machine.
'use strict';

const { test, describe } = require('node:test');
const assert = require('node:assert/strict');

const ps = require('../functions/lib/payment-state');

describe('canTransition', () => {
  test('allows the normal happy path', () => {
    assert.equal(ps.canTransition('CREATED', 'PENDING'), true);
    assert.equal(ps.canTransition('PENDING', 'SUCCESS'), true);
    assert.equal(ps.canTransition('SUCCESS', 'REFUNDED'), true);
  });
  test('the same status to itself is always allowed (idempotent replay)', () => {
    for (const s of ps.ALL_STATUSES) assert.equal(ps.canTransition(s, s), true);
  });
  test('rejects walking a terminal status forward', () => {
    assert.equal(ps.canTransition('FAILED', 'SUCCESS'), false);
    assert.equal(ps.canTransition('REFUNDED', 'SUCCESS'), false);
    assert.equal(ps.canTransition('CANCELLED', 'PENDING'), false);
  });
  test('rejects going backwards from SUCCESS to PENDING', () => {
    assert.equal(ps.canTransition('SUCCESS', 'PENDING'), false);
  });
  test('rejects unknown statuses', () => {
    assert.equal(ps.canTransition('SUCCESS', 'HACKED'), false);
    assert.equal(ps.canTransition('HACKED', 'SUCCESS'), false);
  });
});

describe('nextStatus', () => {
  test('a brand-new donation (no currentStatus) can start at PENDING', () => {
    const r = ps.nextStatus(undefined, 'PENDING');
    assert.equal(r.ok, true);
    assert.equal(r.changed, true);
    assert.equal(r.status, 'PENDING');
  });

  test('CREATED -> PENDING -> SUCCESS, the ordinary flow', () => {
    let r = ps.nextStatus('CREATED', 'PENDING');
    assert.deepEqual([r.ok, r.status], [true, 'PENDING']);
    r = ps.nextStatus('PENDING', 'SUCCESS');
    assert.deepEqual([r.ok, r.status], [true, 'SUCCESS']);
  });

  test('a duplicate webhook reporting the same status is a no-op, not an error', () => {
    const r = ps.nextStatus('SUCCESS', 'SUCCESS');
    assert.equal(r.ok, true);
    assert.equal(r.changed, false);
    assert.equal(r.status, 'SUCCESS');
  });

  test('a stale PENDING arriving after SUCCESS is rejected, never applied', () => {
    const r = ps.nextStatus('SUCCESS', 'PENDING');
    assert.equal(r.ok, false);
    assert.equal(r.changed, false);
    assert.ok(r.reason.includes('illegal transition'));
  });

  test('an unrecognized reported status is rejected without throwing', () => {
    const r = ps.nextStatus('PENDING', 'TOTALLY_MADE_UP');
    assert.equal(r.ok, false);
    assert.match(r.reason, /unrecognized status/);
  });

  test('SUCCESS -> PARTIALLY_REFUNDED -> REFUNDED (a partial refund topped up)', () => {
    let r = ps.nextStatus('SUCCESS', 'PARTIALLY_REFUNDED');
    assert.deepEqual([r.ok, r.status], [true, 'PARTIALLY_REFUNDED']);
    r = ps.nextStatus('PARTIALLY_REFUNDED', 'REFUNDED');
    assert.deepEqual([r.ok, r.status], [true, 'REFUNDED']);
  });
});

describe('isTerminal', () => {
  test('FAILED, CANCELLED, REFUNDED are terminal', () => {
    assert.equal(ps.isTerminal('FAILED'), true);
    assert.equal(ps.isTerminal('CANCELLED'), true);
    assert.equal(ps.isTerminal('REFUNDED'), true);
  });
  test('CREATED, PENDING, SUCCESS, PARTIALLY_REFUNDED are not terminal', () => {
    assert.equal(ps.isTerminal('CREATED'), false);
    assert.equal(ps.isTerminal('PENDING'), false);
    assert.equal(ps.isTerminal('SUCCESS'), false);
    assert.equal(ps.isTerminal('PARTIALLY_REFUNDED'), false);
  });
});
