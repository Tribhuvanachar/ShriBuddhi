// broadcast-core.js — who gets a scheduled WhatsApp broadcast, and who
// must not. Pure functions, so the "must not" half is testable.
//
// The expensive mistakes in a broadcast system are all in the audience
// selection, not the sending: messaging someone who opted out (a
// compliance breach and a fast route to Meta throttling the number),
// or double-sending a campaign after a retry (a real bill, twice). Both
// are decided here and pinned by tests.
'use strict';

/**
 * Decides whether one user should receive one campaign.
 *
 * Every rejection reason is returned rather than folded into a boolean,
 * so a dry run can explain the audience rather than just count it.
 *
 * @returns {{eligible: boolean, reason?: string}}
 */
function isEligible(user, campaign, now) {
  if (!user) return { eligible: false, reason: 'no_user' };

  // Explicit opt-in is required — never inferred from "they signed up".
  // WhatsApp's own policy requires opt-in obtained outside WhatsApp, and
  // this flag is the record of it.
  if (user.whatsappOptIn !== true) return { eligible: false, reason: 'not_opted_in' };

  // An opt-out always wins, even if a later opt-in flag is somehow also
  // set — the safe direction when the record is contradictory.
  if (user.whatsappOptOutAt) return { eligible: false, reason: 'opted_out' };

  if (!user.phoneNumber) return { eligible: false, reason: 'no_phone' };

  // A number that has hard-bounced (not on WhatsApp, blocked us) is not
  // retried — Meta counts repeated undeliverable sends against the
  // sender's quality rating.
  if (user.whatsappUndeliverable === true) return { eligible: false, reason: 'undeliverable' };

  // Idempotency: the per-user record of campaigns already delivered.
  // This is what makes a re-run of a failed scheduled job safe.
  const sent = user.whatsappCampaigns || {};
  if (campaign?.id && sent[campaign.id]) return { eligible: false, reason: 'already_sent' };

  // Audience targeting by role, when the campaign narrows it.
  if (Array.isArray(campaign?.roles) && campaign.roles.length) {
    if (!campaign.roles.includes(user.role || 'basic')) {
      return { eligible: false, reason: 'role_excluded' };
    }
  }

  // Frequency cap — a floor on the gap between any two broadcasts to the
  // same person, independent of campaign. Guards against several
  // campaigns firing the same day and reading as spam.
  const minGapMs = campaign?.minGapMs ?? 0;
  if (minGapMs > 0 && user.whatsappLastBroadcastAt) {
    if ((now - user.whatsappLastBroadcastAt) < minGapMs) {
      return { eligible: false, reason: 'frequency_capped' };
    }
  }

  return { eligible: true };
}

/**
 * Partitions a user list into recipients and a reason-tallied rejection
 * summary.
 */
function selectAudience(users, campaign, now) {
  const recipients = [];
  const skipped = {};
  for (const u of users) {
    const verdict = isEligible(u, campaign, now);
    if (verdict.eligible) {
      recipients.push(u);
    } else {
      skipped[verdict.reason] = (skipped[verdict.reason] || 0) + 1;
    }
  }
  return { recipients, skipped, total: users.length };
}

/**
 * Splits recipients into batches. Meta rate-limits per phone number ID,
 * and a scheduled function has a wall-clock budget, so a broadcast to a
 * large audience is paced rather than fired all at once.
 */
function batch(items, size) {
  if (!Number.isInteger(size) || size < 1) throw new Error('batch size must be a positive integer');
  const out = [];
  for (let i = 0; i < items.length; i += size) out.push(items.slice(i, i + size));
  return out;
}

/**
 * Caps a run to what the budget allows, so a misconfigured campaign
 * cannot bill for an unbounded number of messages in one firing. The
 * remainder is reported, not silently dropped — the caller logs it.
 */
function applySendCap(recipients, cap) {
  if (!cap || cap < 0 || recipients.length <= cap) {
    return { toSend: recipients, deferred: [] };
  }
  return { toSend: recipients.slice(0, cap), deferred: recipients.slice(cap) };
}

module.exports = { isEligible, selectAudience, batch, applySendCap };
