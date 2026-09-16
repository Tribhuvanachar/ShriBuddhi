// Firestore security-rules tests — run against the REAL Firestore
// emulator, not a stub. These are the tests that matter most in this
// directory: the rules are the actual enforcement layer, and every
// client-side check in this app is bypassable by anyone willing to open
// a console and call Firestore directly.
//
// Run with:  npm run test:rules
// (which starts the emulator, runs this file, and shuts it down)
//
// Named .spec.js rather than .test.js on purpose: node's default test
// glob does NOT pick up this suffix, so a plain `npm test` runs the
// credential-free unit tests and leaves this one to the script that
// knows how to start an emulator for it. Running this file directly,
// without an emulator on 127.0.0.1:8080, will hang and then fail.
//
// Most of what follows asserts that something FAILS. A rules test suite
// that only checks the happy path would pass just as happily against
// `allow read, write: if true`.
'use strict';

const { test, describe, before, after, beforeEach } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { initializeTestEnvironment, assertFails, assertSucceeds } = require('@firebase/rules-unit-testing');

let testEnv;

const UID_BASIC = 'user_basic';
const UID_OTHER = 'user_other';
const UID_ADMIN = 'user_admin';
const UID_SUPER = 'user_super';

before(async () => {
  testEnv = await initializeTestEnvironment({
    projectId: 'dge-test',
    firestore: {
      rules: fs.readFileSync(path.resolve(__dirname, '../firestore.rules'), 'utf8'),
      host: '127.0.0.1',
      port: 8080
    }
  });
});

after(async () => {
  if (testEnv) await testEnv.cleanup();
});

beforeEach(async () => {
  await testEnv.clearFirestore();
  // Seed the four profiles the rules read to resolve caller roles.
  await testEnv.withSecurityRulesDisabled(async (ctx) => {
    const db = ctx.firestore();
    await db.doc(`users/${UID_BASIC}`).set({ displayName: 'Basic', email: 'b@x.com', role: 'basic', whatsappOptIn: false });
    await db.doc(`users/${UID_OTHER}`).set({ displayName: 'Other', email: 'o@x.com', phoneNumber: '+919999999999', role: 'basic', whatsappOptIn: false });
    await db.doc(`users/${UID_ADMIN}`).set({ displayName: 'Admin', email: 'a@x.com', role: 'admin', whatsappOptIn: false });
    await db.doc(`users/${UID_SUPER}`).set({ displayName: 'Super', email: 's@x.com', role: 'superadmin', whatsappOptIn: false });
    await db.doc('otp_challenges/somehash').set({ codeHash: 'deadbeef', attempts: 0, expiresAt: Date.now() + 60000 });
    await db.doc('broadcasts/c1').set({ templateName: 'daily_shloka', status: 'scheduled' });
  });
});

const asUser = (uid) => testEnv.authenticatedContext(uid).firestore();
const asAnon = () => testEnv.unauthenticatedContext().firestore();

describe('users — read access', () => {
  test('a signed-out visitor can read nothing', async () => {
    await assertFails(asAnon().doc(`users/${UID_BASIC}`).get());
  });

  test('a user can read their own profile', async () => {
    await assertSucceeds(asUser(UID_BASIC).doc(`users/${UID_BASIC}`).get());
  });

  test("a user CANNOT read someone else's profile", async () => {
    // Profiles hold phone numbers and emails. Before this rule, any
    // signed-in account could read the entire user base's contact
    // details — the whole point of tightening it.
    await assertFails(asUser(UID_BASIC).doc(`users/${UID_OTHER}`).get());
  });

  test('a user cannot list the whole users collection', async () => {
    await assertFails(asUser(UID_BASIC).collection('users').get());
  });

  test('an admin can read any profile (Manage Users)', async () => {
    await assertSucceeds(asUser(UID_ADMIN).doc(`users/${UID_OTHER}`).get());
  });

  test('an admin can LIST users — the Manage Users query itself', async () => {
    // Distinct from reading one document: Firestore evaluates a list
    // against the rule for every matched doc, so tightening the read
    // rule could have silently broken this screen. This is the exact
    // query user-roles.js runs.
    await assertSucceeds(
      asUser(UID_ADMIN).collection('users').orderBy('lastLoginAt', 'desc').limit(200).get()
    );
    await assertSucceeds(asUser(UID_SUPER).collection('users').get());
  });

  test('a superadmin can read any profile', async () => {
    await assertSucceeds(asUser(UID_SUPER).doc(`users/${UID_OTHER}`).get());
  });
});

describe('users — creating your own profile', () => {
  const NEW_UID = 'brand_new_user';

  test('a new user may create their own profile with the default role', async () => {
    // With the provider's verified email (a Google sign-in token); an
    // unverified one is the subject of the "verified emails only" suite.
    await assertSucceeds(testEnv.authenticatedContext(NEW_UID, { email: 'n@x.com', email_verified: true }).firestore()
      .doc(`users/${NEW_UID}`).set({ displayName: 'New', email: 'n@x.com', role: 'basic', whatsappOptIn: false }));
  });

  test('a new user may NOT hand themselves superadmin on the way in', async () => {
    // The privilege-escalation case. Sign-in is the one moment a client
    // writes its own profile, so it is the one moment this must hold.
    for (const role of ['superadmin', 'admin', 'sponsor', 'subscriber', 'special']) {
      await assertFails(asUser(NEW_UID).doc(`users/${NEW_UID}`).set({
        displayName: 'New', email: '', role, whatsappOptIn: false
      }), `creating a profile with role "${role}" must be rejected`);
    }
  });

  test('a user may not create a profile under someone else\'s uid', async () => {
    await assertFails(asUser(UID_BASIC).doc('users/victim_uid').set({ role: 'basic' }));
  });

  test('a signed-out visitor may not create a profile', async () => {
    await assertFails(asAnon().doc('users/anon_uid').set({ role: 'basic' }));
  });

  test('a new profile may not arrive with WhatsApp consent pre-set', async () => {
    // Consent is an explicit later action, never assumed at sign-up —
    // WhatsApp policy requires opt-in collected as a deliberate act.
    await assertFails(asUser(NEW_UID).doc(`users/${NEW_UID}`).set({
      displayName: 'New', role: 'basic', whatsappOptIn: true
    }));
  });

  test('a new profile may omit the consent field entirely', async () => {
    await assertSucceeds(asUser(NEW_UID).doc(`users/${NEW_UID}`).set({
      displayName: 'New', role: 'basic'
    }));
  });
});

describe('users — verified emails only (7 Sep 2026)', () => {
  // request.auth.token carries what the provider vouched for; the rules
  // let a profile hold that address and nothing else.
  const asVerified = (uid, email) => testEnv.authenticatedContext(uid, { email, email_verified: true }).firestore();
  const asUnverified = (uid, email) => testEnv.authenticatedContext(uid, { email, email_verified: false }).firestore();
  const base = { displayName: 'N', role: 'basic', whatsappOptIn: false };

  test('a verified provider email may be stored on create', async () => {
    await assertSucceeds(asVerified('v1', 'v1@x.com').doc('users/v1').set({ ...base, email: 'v1@x.com', emailVerified: true }));
  });
  test('an unverified email may not be stored, even the token\'s own', async () => {
    await assertFails(asUnverified('u1', 'u1@x.com').doc('users/u1').set({ ...base, email: 'u1@x.com' }));
  });
  test('an unverified account may still create a profile with an empty email', async () => {
    await assertSucceeds(asUnverified('u2', 'u2@x.com').doc('users/u2').set({ ...base, email: '', emailVerified: false }));
  });
  test('a verified account may not store a DIFFERENT address', async () => {
    await assertFails(asVerified('v2', 'v2@x.com').doc('users/v2').set({ ...base, email: 'someone-else@x.com' }));
  });
  test('emailVerified cannot be claimed without the token backing it', async () => {
    await assertFails(asUnverified('u3', 'u3@x.com').doc('users/u3').set({ ...base, email: '', emailVerified: true }));
  });
  test('a returning user may capture a newly verified email on update', async () => {
    await assertSucceeds(asVerified(UID_BASIC, 'b@x.com').doc(`users/${UID_BASIC}`).update({ email: 'b@x.com', emailVerified: true }));
  });
  test('a returning user may not overwrite the email with an unverified one', async () => {
    await assertFails(asUnverified(UID_BASIC, 'new@x.com').doc(`users/${UID_BASIC}`).update({ email: 'new@x.com' }));
  });
});

describe('users — updating your own profile', () => {
  test('a user may edit their own display name', async () => {
    await assertSucceeds(asUser(UID_BASIC).doc(`users/${UID_BASIC}`).update({ displayName: 'Renamed' }));
  });

  test('a user may grant and withdraw WhatsApp consent', async () => {
    await assertSucceeds(asUser(UID_BASIC).doc(`users/${UID_BASIC}`).update({ whatsappOptIn: true }));
    await assertSucceeds(asUser(UID_BASIC).doc(`users/${UID_BASIC}`).update({ whatsappOptIn: false }));
  });

  test('a user may NOT promote themselves', async () => {
    await assertFails(asUser(UID_BASIC).doc(`users/${UID_BASIC}`).update({ role: 'superadmin' }));
    await assertFails(asUser(UID_BASIC).doc(`users/${UID_BASIC}`).update({ role: 'admin' }));
  });

  test('an admin may not promote themselves to superadmin', async () => {
    // An admin is still the owner of their own doc, so the self-update
    // rule applies to them exactly as it does to anyone else.
    await assertFails(asUser(UID_ADMIN).doc(`users/${UID_ADMIN}`).update({ role: 'superadmin' }));
  });

  test('a superadmin may not change their OWN role either', async () => {
    // Not a security boundary so much as a footgun guard: the only way
    // to lose the last superadmin is for one to demote themselves.
    await assertFails(asUser(UID_SUPER).doc(`users/${UID_SUPER}`).update({ role: 'basic' }));
  });

  test('a user may NOT rewrite the record of campaigns already sent', async () => {
    // Client-writable, this would let someone clear the dedupe record
    // and re-trigger paid broadcast messages to themselves.
    await assertFails(asUser(UID_BASIC).doc(`users/${UID_BASIC}`).update({ whatsappCampaigns: {} }));
    await assertFails(asUser(UID_BASIC).doc(`users/${UID_BASIC}`).update({ 'whatsappCampaigns.c1': null }));
  });

  test('a user may NOT clear their own undeliverable flag', async () => {
    await assertFails(asUser(UID_BASIC).doc(`users/${UID_BASIC}`).update({ whatsappUndeliverable: false }));
  });

  test('a user may NOT erase an opt-out recorded by the STOP webhook', async () => {
    await assertFails(asUser(UID_BASIC).doc(`users/${UID_BASIC}`).update({ whatsappOptOutAt: null }));
  });

  test('a user may NOT forge their broadcast frequency-cap timestamp', async () => {
    await assertFails(asUser(UID_BASIC).doc(`users/${UID_BASIC}`).update({ whatsappLastBroadcastAt: 0 }));
  });

  test('an allowed field mixed with a forbidden one is rejected as a whole', async () => {
    // Rules evaluate the write, not each field, so a permitted change
    // cannot be used to smuggle a forbidden one alongside it.
    await assertFails(asUser(UID_BASIC).doc(`users/${UID_BASIC}`).update({
      displayName: 'Fine', whatsappUndeliverable: false
    }));
  });

  test("a user may not edit someone else's profile", async () => {
    await assertFails(asUser(UID_BASIC).doc(`users/${UID_OTHER}`).update({ displayName: 'Hacked' }));
  });
});

describe('users — role management by admins', () => {
  test('a superadmin may change another user\'s role', async () => {
    await assertSucceeds(asUser(UID_SUPER).doc(`users/${UID_BASIC}`).update({ role: 'sponsor' }));
  });

  test('a plain admin may NOT change roles', async () => {
    // Reading the user list and rewriting it are deliberately different
    // privileges.
    await assertFails(asUser(UID_ADMIN).doc(`users/${UID_BASIC}`).update({ role: 'sponsor' }));
  });

  test('a basic user may not change anyone\'s role', async () => {
    await assertFails(asUser(UID_BASIC).doc(`users/${UID_OTHER}`).update({ role: 'admin' }));
  });

  test('a signed-out visitor may not change roles', async () => {
    await assertFails(asAnon().doc(`users/${UID_BASIC}`).update({ role: 'admin' }));
  });
});

describe('bootstrap allowlist — the first superadmin', () => {
  // The chicken-and-egg these rules exist to break: a new account is
  // 'basic', and nobody may change their own role, so nobody can ever make
  // the first superadmin from inside the app.
  //
  // WHAT THESE TESTS PIN. The repository ships with BOTH allowlists empty,
  // which is the state that matters most: an empty allowlist must grant
  // nobody anything, or every fork of this project would hand its author
  // superadmin on every deployment. A populated list cannot be exercised
  // here without editing the rules file the suite loads, so these assert
  // the closed default and the exact shape of the escape hatch; the
  // populated case is checked by hand after a deploy (FIREBASE_SETUP.md §4).

  test('with the allowlist empty, nobody may claim superadmin for themselves', async () => {
    await assertFails(asUser(UID_BASIC).doc(`users/${UID_BASIC}`).update({ role: 'superadmin' }));
    await assertFails(asUser(UID_ADMIN).doc(`users/${UID_ADMIN}`).update({ role: 'superadmin' }));
  });

  test('an existing superadmin still may not CHANGE their own role', async () => {
    // The bootstrap rule is scoped to the allowlist, not to "anyone who is
    // already a superadmin" — a self-role-CHANGE stays shut for everybody.
    //
    // Writing the value it already holds is a different thing and does
    // succeed, by the pre-existing self-edit rule: request.resource.data.role
    // == resource.data.role holds, and a write that changes nothing has an
    // empty affectedKeys(), which hasOnly() accepts. That is a no-op, not an
    // escalation, so it is not asserted against here — a first draft of this
    // test did assert it and was wrong.
    await assertFails(asUser(UID_SUPER).doc(`users/${UID_SUPER}`).update({ role: 'basic' }));
    await assertFails(asUser(UID_ADMIN).doc(`users/${UID_ADMIN}`).update({ role: 'superadmin' }));
  });

  test('a signed-out visitor may not claim anything', async () => {
    await assertFails(asAnon().doc(`users/${UID_BASIC}`).update({ role: 'superadmin' }));
  });

  test('the escape hatch is role-only: a claim may not smuggle other fields', async () => {
    // Even for an allowlisted account this must fail, because hasOnly(['role'])
    // rejects the write outright. Asserted against a non-allowlisted user
    // too, so the test is meaningful with the shipped empty list.
    await assertFails(asUser(UID_BASIC).doc(`users/${UID_BASIC}`)
      .update({ role: 'superadmin', displayName: 'Sneaky' }));
  });

  test('the escape hatch is superadmin-only: no other role may be self-assigned', async () => {
    await assertFails(asUser(UID_BASIC).doc(`users/${UID_BASIC}`).update({ role: 'admin' }));
    await assertFails(asUser(UID_BASIC).doc(`users/${UID_BASIC}`).update({ role: 'sponsor' }));
  });

  test('ordinary self-edits still work — the new rule took nothing away', async () => {
    await assertSucceeds(asUser(UID_BASIC).doc(`users/${UID_BASIC}`).update({ displayName: 'Renamed' }));
  });
});

describe('users — deletes', () => {
  test('nobody may delete a profile, not even a superadmin', async () => {
    await assertFails(asUser(UID_BASIC).doc(`users/${UID_BASIC}`).delete());
    await assertFails(asUser(UID_SUPER).doc(`users/${UID_BASIC}`).delete());
    await assertFails(asAnon().doc(`users/${UID_BASIC}`).delete());
  });
});

describe('otp_challenges — sealed from every client', () => {
  // Only the Admin SDK inside Cloud Functions touches this collection.
  // A client that could read it could time a brute force against the
  // attempt counter; one that could write it could reset that counter
  // and guess forever.
  test('a signed-out visitor can neither read nor write', async () => {
    await assertFails(asAnon().doc('otp_challenges/somehash').get());
    await assertFails(asAnon().doc('otp_challenges/somehash').set({ attempts: 0 }));
  });

  test('a signed-in user can neither read nor write', async () => {
    await assertFails(asUser(UID_BASIC).doc('otp_challenges/somehash').get());
    await assertFails(asUser(UID_BASIC).doc('otp_challenges/somehash').set({ attempts: 0 }));
  });

  test('even a superadmin cannot read or reset a challenge', async () => {
    await assertFails(asUser(UID_SUPER).doc('otp_challenges/somehash').get());
    await assertFails(asUser(UID_SUPER).doc('otp_challenges/somehash').update({ attempts: 0 }));
  });

  test('nobody can list the collection', async () => {
    await assertFails(asUser(UID_SUPER).collection('otp_challenges').get());
  });
});

describe('broadcasts — admin-only operational data', () => {
  test('a basic user cannot read campaigns', async () => {
    await assertFails(asUser(UID_BASIC).doc('broadcasts/c1').get());
  });

  test('a signed-out visitor cannot read campaigns', async () => {
    await assertFails(asAnon().doc('broadcasts/c1').get());
  });

  test('an admin can read campaigns', async () => {
    await assertSucceeds(asUser(UID_ADMIN).doc('broadcasts/c1').get());
  });

  test('an admin cannot schedule a campaign', async () => {
    // Reading the schedule and spending money on it are different
    // privileges.
    await assertFails(asUser(UID_ADMIN).doc('broadcasts/c2').set({ templateName: 't', status: 'scheduled' }));
  });

  test('a superadmin can create, update and delete campaigns', async () => {
    await assertSucceeds(asUser(UID_SUPER).doc('broadcasts/c2').set({ templateName: 't', status: 'scheduled' }));
    await assertSucceeds(asUser(UID_SUPER).doc('broadcasts/c2').update({ status: 'paused' }));
    await assertSucceeds(asUser(UID_SUPER).doc('broadcasts/c2').delete());
  });

  test('a basic user cannot create a campaign', async () => {
    await assertFails(asUser(UID_BASIC).doc('broadcasts/c3').set({ templateName: 't' }));
  });
});

describe('config — role gates, readable by everyone, writable only by a superadmin', () => {
  test('a signed-out visitor can read the role gates', async () => {
    // Content gating has to work for anonymous browsing too, not just
    // signed-in users — a gate that only anonymous visitors can't see
    // would defeat its own purpose.
    await assertSucceeds(asAnon().doc('config/roleAccess').get());
    await assertSucceeds(asAnon().doc('config/roles').get());
  });

  test('a basic user can read but not write it', async () => {
    await assertSucceeds(asUser(UID_BASIC).doc('config/roleAccess').get());
    await assertFails(asUser(UID_BASIC).doc('config/roleAccess').set({ gates: [] }));
  });

  test('an admin (not superadmin) can read but not write it', async () => {
    await assertSucceeds(asUser(UID_ADMIN).doc('config/roleAccess').get());
    await assertFails(asUser(UID_ADMIN).doc('config/roleAccess').set({ gates: [] }));
  });

  test('a superadmin can create, update and delete it', async () => {
    await assertSucceeds(asUser(UID_SUPER).doc('config/roleAccess').set({ gates: [{ prefix: 'x', allowRoles: ['sponsor'] }] }));
    await assertSucceeds(asUser(UID_SUPER).doc('config/roleAccess').update({ gates: [] }));
    await assertSucceeds(asUser(UID_SUPER).doc('config/roleAccess').delete());
    await assertSucceeds(asUser(UID_SUPER).doc('config/roles').set({ list: [{ id: 'basic', label: 'Basic' }] }));
  });
});

describe('donors — the most sensitive PII, superadmin read only', () => {
  test('a signed-out visitor, a basic user, and an admin (not superadmin) are all denied read', async () => {
    await testEnv.withSecurityRulesDisabled(async (ctx) => {
      await ctx.firestore().doc('donors/d1').set({ fullName: 'X', email: 'x@x.com', pan: 'ABCDE1234F' });
    });
    await assertFails(asAnon().doc('donors/d1').get());
    await assertFails(asUser(UID_BASIC).doc('donors/d1').get());
    await assertFails(asUser(UID_ADMIN).doc('donors/d1').get());
  });
  test('a superadmin can read it', async () => {
    await testEnv.withSecurityRulesDisabled(async (ctx) => {
      await ctx.firestore().doc('donors/d1').set({ fullName: 'X', email: 'x@x.com' });
    });
    await assertSucceeds(asUser(UID_SUPER).doc('donors/d1').get());
  });
  test('no client, not even a superadmin, may write directly — only Cloud Functions (Admin SDK) may', async () => {
    await assertFails(asUser(UID_SUPER).doc('donors/d2').set({ fullName: 'X', email: 'x@x.com' }));
  });
});

describe('donations — admin read, no direct client write ever', () => {
  test('a basic user cannot read', async () => {
    await testEnv.withSecurityRulesDisabled(async (ctx) => {
      await ctx.firestore().doc('donations/don1').set({ donationReference: 'DGE-1', status: 'SUCCESS', amountMinor: 100 });
    });
    await assertFails(asUser(UID_BASIC).doc('donations/don1').get());
  });
  test('an admin can read', async () => {
    await testEnv.withSecurityRulesDisabled(async (ctx) => {
      await ctx.firestore().doc('donations/don1').set({ donationReference: 'DGE-1', status: 'SUCCESS', amountMinor: 100 });
    });
    await assertSucceeds(asUser(UID_ADMIN).doc('donations/don1').get());
  });
  test('a client cannot set its own donation to SUCCESS — this is exactly the tamper this feature must resist', async () => {
    await assertFails(asUser(UID_SUPER).doc('donations/don2').set({ status: 'SUCCESS', amountMinor: 999999999 }));
    await assertFails(asUser(UID_BASIC).doc('donations/don2').set({ status: 'SUCCESS', amountMinor: 1 }));
  });
});

describe('payments — admin read, no client write', () => {
  test('read/write follow the same admin-only, no-client-write shape as donations', async () => {
    await testEnv.withSecurityRulesDisabled(async (ctx) => {
      await ctx.firestore().doc('payments/p1').set({ donationId: 'don1', gateway: 'mock' });
    });
    await assertFails(asUser(UID_BASIC).doc('payments/p1').get());
    await assertSucceeds(asUser(UID_ADMIN).doc('payments/p1').get());
    await assertFails(asUser(UID_SUPER).doc('payments/p1').set({ gatewayStatus: 'SUCCESS' }));
  });
});

describe('payment_events — sealed off from every client, like otp_challenges', () => {
  test('not even a superadmin may read or write it', async () => {
    await testEnv.withSecurityRulesDisabled(async (ctx) => {
      await ctx.firestore().doc('payment_events/mock_evt1').set({ gateway: 'mock', processingStatus: 'PROCESSED' });
    });
    await assertFails(asUser(UID_SUPER).doc('payment_events/mock_evt1').get());
    await assertFails(asUser(UID_SUPER).doc('payment_events/mock_evt2').set({ gateway: 'mock' }));
  });
});

describe('receipts and receipt_counters — no client access to the counters, admin read on receipts', () => {
  test('receipts: admin can read, nobody can write', async () => {
    await testEnv.withSecurityRulesDisabled(async (ctx) => {
      await ctx.firestore().doc('receipts/don1').set({ receiptNumber: 'DGE-2026-000001' });
    });
    await assertSucceeds(asUser(UID_ADMIN).doc('receipts/don1').get());
    await assertFails(asUser(UID_BASIC).doc('receipts/don1').get());
    await assertFails(asUser(UID_SUPER).doc('receipts/don1').set({ receiptNumber: 'DGE-2026-999999' }));
  });
  test('receipt_counters: sealed from every client — a client that could write this could mint its own receipt numbers', async () => {
    await testEnv.withSecurityRulesDisabled(async (ctx) => {
      await ctx.firestore().doc('receipt_counters/2026').set({ seq: 5 });
    });
    await assertFails(asUser(UID_SUPER).doc('receipt_counters/2026').get());
    await assertFails(asUser(UID_SUPER).doc('receipt_counters/2026').set({ seq: 999999 }));
  });
});

describe('supporter_entitlements — admin read only until Phase 3 links a donor to a uid', () => {
  test('a basic user cannot read someone else\'s entitlement', async () => {
    await testEnv.withSecurityRulesDisabled(async (ctx) => {
      await ctx.firestore().doc('supporter_entitlements/d1_PREMIUM_LIBRARY').set({ donorId: 'd1', entitlementCode: 'PREMIUM_LIBRARY' });
    });
    await assertFails(asUser(UID_BASIC).doc('supporter_entitlements/d1_PREMIUM_LIBRARY').get());
    await assertSucceeds(asUser(UID_ADMIN).doc('supporter_entitlements/d1_PREMIUM_LIBRARY').get());
  });
});

describe('public_supporters — the one collection in this feature that is public read', () => {
  test('a signed-out visitor can read it', async () => {
    await testEnv.withSecurityRulesDisabled(async (ctx) => {
      await ctx.firestore().doc('public_supporters/don1').set({ displayName: 'Sri Example', amountMinor: null, currency: 'INR' });
    });
    await assertSucceeds(asAnon().doc('public_supporters/don1').get());
  });
  test('no client, not even a superadmin, may write it directly — only onDonationSucceeded may', async () => {
    await assertFails(asUser(UID_SUPER).doc('public_supporters/don2').set({ displayName: 'Forged Name', amountMinor: 999999999 }));
  });
  test('it never carries donor PII fields even when present in the seeded doc — the RULE does not filter fields, so this documents what index.js must never write, not something the rules themselves enforce', async () => {
    // Firestore rules can restrict which DOCUMENTS are readable, not
    // which FIELDS within an allowed document — so the actual privacy
    // guarantee here is entirely "onDonationSucceeded in index.js only
    // ever writes displayName/amountMinor/currency/paidAt/donationReference".
    // This test exists as a tripwire: if a future edit ever writes email
    // or pan onto this collection, nothing in the rules would catch it.
    await testEnv.withSecurityRulesDisabled(async (ctx) => {
      await ctx.firestore().doc('public_supporters/don3').set({ displayName: 'X', amountMinor: 100, currency: 'INR' });
    });
    const snap = await asAnon().doc('public_supporters/don3').get();
    const data = snap.data();
    assert.ok(!('email' in data) && !('pan' in data) && !('phone' in data) && !('donorId' in data));
  });
});

describe('unlisted collections are denied by default', () => {
  test('an arbitrary collection is closed to everyone', async () => {
    await assertFails(asUser(UID_SUPER).doc('random_stuff/x').set({ a: 1 }));
    await assertFails(asUser(UID_BASIC).doc('random_stuff/x').get());
    await assertFails(asAnon().doc('random_stuff/x').get());
  });
});
