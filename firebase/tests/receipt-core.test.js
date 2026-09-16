// Tests for receipt-core.js — receipt numbering and email content.
'use strict';

const { test, describe } = require('node:test');
const assert = require('node:assert/strict');

const rc = require('../functions/lib/receipt-core');

describe('formatReceiptNumber', () => {
  test('zero-pads to 6 digits', () => {
    assert.equal(rc.formatReceiptNumber(2026, 1), 'DGE-2026-000001');
    assert.equal(rc.formatReceiptNumber(2026, 184), 'DGE-2026-000184');
  });
  test('never derived from a gateway id — just the plain formatted counter', () => {
    assert.equal(rc.formatReceiptNumber(2026, 999999), 'DGE-2026-999999');
  });
  test('rejects an implausible year or non-positive sequence', () => {
    assert.throws(() => rc.formatReceiptNumber(1800, 1));
    assert.throws(() => rc.formatReceiptNumber(2026, 0));
    assert.throws(() => rc.formatReceiptNumber(2026, -1));
    assert.throws(() => rc.formatReceiptNumber(2026, 1.5));
  });
});

describe('formatAmountMajor', () => {
  test('formats INR with Indian digit grouping', () => {
    assert.equal(rc.formatAmountMajor(100150, 'INR'), '1,001.50');
    assert.equal(rc.formatAmountMajor(2500000, 'INR'), '25,000.00');
    assert.equal(rc.formatAmountMajor(100, 'INR'), '1.00');
  });
  test('falls back to plain thousands grouping for a non-INR currency', () => {
    assert.equal(rc.formatAmountMajor(2500000, 'USD'), '25,000.00');
  });
});

describe('buildReceiptEmail', () => {
  test('never claims tax deductibility', () => {
    const { subject, textBody } = rc.buildReceiptEmail({
      receiptNumber: 'DGE-2026-000184', donorName: 'Sri Example',
      amountMinor: 100100, currency: 'INR', paidAtIso: '2026-09-08T00:00:00Z', paymentMethod: 'UPI'
    });
    assert.match(subject, /DGE-2026-000184/);
    const lower = textBody.toLowerCase();
    assert.ok(!lower.includes('tax'), 'must not mention tax deductibility until the Trust\'s status is confirmed');
    assert.ok(!lower.includes('80g'));
    assert.ok(!lower.includes('12a'));
  });

  test('includes the amount, reference, and payment method', () => {
    const { textBody } = rc.buildReceiptEmail({
      receiptNumber: 'DGE-2026-000184', donorName: 'Sri Example',
      amountMinor: 100100, currency: 'INR', paidAtIso: '2026-09-08T00:00:00Z', paymentMethod: 'UPI'
    });
    assert.match(textBody, /DGE-2026-000184/);
    assert.match(textBody, /1,001\.00/);
    assert.match(textBody, /UPI/);
  });

  test('handles a missing donor name and payment method gracefully', () => {
    const { textBody } = rc.buildReceiptEmail({
      receiptNumber: 'DGE-2026-000001', amountMinor: 100, currency: 'INR'
    });
    assert.ok(textBody.length > 0);
    assert.ok(!textBody.includes('undefined'));
    assert.ok(!textBody.includes('null'));
  });
});
