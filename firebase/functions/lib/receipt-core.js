// receipt-core.js -- receipt numbering and the receipt email's content,
// as pure functions. index.js owns the atomic counter (a Firestore
// transaction) and the actual send; this file only decides what the
// number and the message look like, so both are testable without a
// live project or an email provider.
'use strict';

/**
 * Formats a receipt number as DGE-YYYY-NNNNNN, zero-padded to 6 digits.
 * `seq` is the value AFTER incrementing this year's counter -- the
 * caller is responsible for that being atomic (see index.js's
 * nextReceiptNumber, a Firestore transaction on receipt_counters/{year}).
 *
 * Deliberately never derived from a gateway transaction id: a receipt
 * number must stay stable and DGE's own even if a gateway is swapped out
 * later, and a gateway id can leak which processor was used.
 */
function formatReceiptNumber(year, seq) {
  if (!Number.isInteger(year) || year < 2000 || year > 3000) {
    throw new Error(`formatReceiptNumber: implausible year ${year}`);
  }
  if (!Number.isInteger(seq) || seq < 1) {
    throw new Error(`formatReceiptNumber: seq must be a positive integer, got ${seq}`);
  }
  return `DGE-${year}-${String(seq).padStart(6, '0')}`;
}

/** major-unit string for display, e.g. 100150 minor -> "1,001.50". */
function formatAmountMajor(amountMinor, currency) {
  const major = (amountMinor / 100).toFixed(2);
  const [whole, frac] = major.split('.');
  // Indian digit grouping (last 3, then groups of 2) reads correctly for
  // the currency this feature ships with first; a non-INR currency falls
  // back to plain thousands grouping.
  let grouped;
  if (currency === 'INR') {
    const s = whole.replace('-', '');
    const lastThree = s.slice(-3);
    const rest = s.slice(0, -3);
    grouped = (rest ? rest.replace(/\B(?=(\d{2})+(?!\d))/g, ',') + ',' : '') + lastThree;
    if (whole.startsWith('-')) grouped = '-' + grouped;
  } else {
    grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  }
  return `${grouped}.${frac}`;
}

/**
 * Builds the receipt email's subject and plain-text body. Returns data,
 * not a sent message -- index.js's email step (currently the same
 * console-only, dev-visible pattern lib/providers.js uses for OTP; a
 * real transactional email provider is a later decision, same as the
 * payment gateway) is what actually delivers it.
 *
 * Deliberately makes NO tax-deductibility claim -- see the DO-NOT list
 * in PAYMENTS_SETUP.md. That line is added only once the Trust's actual
 * 12A/80G status is confirmed, and even then by a human editing this
 * template, not inferred here.
 */
function buildReceiptEmail({ receiptNumber, donorName, amountMinor, currency, paidAtIso, paymentMethod }) {
  const amount = formatAmountMajor(amountMinor, currency);
  const symbol = currency === 'INR' ? String.fromCharCode(0x20B9) : (currency || '') + ' ';
  const date = paidAtIso ? new Date(paidAtIso).toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' }) : '';

  const subject = `DGE Donation Receipt -- ${receiptNumber}`;
  const textBody = [
    `Thank you for supporting DGE${donorName ? ', ' + donorName : ''}.`,
    '',
    `Donation reference: ${receiptNumber}`,
    `Amount: ${symbol}${amount} ${currency || ''}`.trim(),
    date ? `Date: ${date}` : null,
    paymentMethod ? `Payment method: ${paymentMethod}` : null,
    '',
    'Keep this email as your receipt for this contribution.'
  ].filter(line => line !== null).join('\n');

  return { subject, textBody };
}

module.exports = { formatReceiptNumber, formatAmountMajor, buildReceiptEmail };
