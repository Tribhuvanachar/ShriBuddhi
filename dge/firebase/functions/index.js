// index.js — DGE's Cloud Functions: OTP over WhatsApp/MSG91, WhatsApp
// broadcasts, and the inbound webhook that honours opt-outs.
//
// Everything security-critical lives in ./lib/*-core.js as pure
// functions with tests. This file is the Firebase-shaped shell around
// them: it reads secrets, runs Firestore transactions, and mints custom
// tokens. Keep it that way — logic that lands here instead of in lib/
// is logic that cannot be tested without a live project.
//
// Deploy: cd dge/firebase && firebase deploy --only functions
// See ../FIREBASE_SETUP.md §7 for the secrets these expect.
'use strict';

const { onCall, onRequest, HttpsError } = require('firebase-functions/v2/https');
const { onSchedule } = require('firebase-functions/v2/scheduler');
const { defineSecret, defineString } = require('firebase-functions/params');
const { setGlobalOptions } = require('firebase-functions/v2');
const logger = require('firebase-functions/logger');
// Modular imports, NOT the older `admin.firestore.FieldValue` namespace
// style. That distinction cost a real debugging session: the functions
// emulator wraps the root `firebase-admin` export in a proxy to redirect
// it at the emulators, and the nested statics read back as undefined
// through that proxy -- so every serverTimestamp() call threw a bare
// INTERNAL under emulation while looking perfectly correct in review.
// The modular entry points are also the current firebase-admin v13 API.
const { initializeApp } = require('firebase-admin/app');
const { getFirestore, FieldValue, Timestamp } = require('firebase-admin/firestore');
const { getAuth } = require('firebase-admin/auth');

const otpCore = require('./lib/otp-core');
const waLib = require('./lib/whatsapp');
const { getProvider, assertProviderAllowed } = require('./lib/providers');
const broadcastCore = require('./lib/broadcast-core');
const wf = require('./lib/workflows-core');
const donationCore = require('./lib/donation-core');
const paymentState = require('./lib/payment-state');
const { getGateway, assertGatewayAllowed } = require('./lib/payment-providers');
const receiptCore = require('./lib/receipt-core');
const { getEmailProvider } = require('./lib/email-providers');

initializeApp();
const db = getFirestore();

// Region matters for latency AND for cost — keep functions near the
// users and near Firestore. asia-south1 (Mumbai) for an India-centred
// audience.
setGlobalOptions({ region: 'asia-south1', maxInstances: 10 });

// --- Secrets (set via `firebase functions:secrets:set NAME`) ----------
// Never hardcode these and never put them in config.js: unlike
// FIREBASE_CONFIG (which is public by design), these are real
// credentials. Storing them as secrets keeps them out of the repo and
// out of the deployed function's source.
const WHATSAPP_TOKEN = defineSecret('WHATSAPP_TOKEN');
const WHATSAPP_PHONE_NUMBER_ID = defineSecret('WHATSAPP_PHONE_NUMBER_ID');
const WHATSAPP_VERIFY_TOKEN = defineSecret('WHATSAPP_VERIFY_TOKEN');
const WHATSAPP_APP_SECRET = defineSecret('WHATSAPP_APP_SECRET');
const MSG91_AUTHKEY = defineSecret('MSG91_AUTHKEY');
// Pepper for hashing phone numbers into document IDs and UIDs. Must be
// set once and then NEVER rotated — rotating it orphans every existing
// phone-based account, because the derived UID would change.
const OTP_PEPPER = defineSecret('OTP_PEPPER');

// --- Non-secret config (plain env params, safe to see) ---------------
const OTP_PROVIDER = defineString('OTP_PROVIDER', { default: 'whatsapp' });
const OTP_TEMPLATE_NAME = defineString('OTP_TEMPLATE_NAME', { default: 'dge_otp' });
const OTP_TEMPLATE_LANG = defineString('OTP_TEMPLATE_LANG', { default: 'en' });
const OTP_DEFAULT_COUNTRY = defineString('OTP_DEFAULT_COUNTRY', { default: '91' });
const MSG91_TEMPLATE_ID = defineString('MSG91_TEMPLATE_ID', { default: '' });

// The token the workflow buttons run on. It must be a FINE-GRAINED personal
// access token, scoped to this one repository, with Actions: read and write
// and nothing else. A classic PAT with `repo` scope would hand whoever
// reaches this function the whole account -- see FIREBASE_SETUP.md SS12.
// Named GH_ rather than GITHUB_ because GitHub Actions refuses to let a
// repository secret's name start with the reserved GITHUB_ prefix --
// discovered 10 Sep 2026 when the console rejected creating it outright.
const GITHUB_DISPATCH_TOKEN = defineSecret('GH_DISPATCH_TOKEN');
const GITHUB_REPO = defineString('GITHUB_REPO', { default: 'Tribhuvanachar/bhumandala' });

// The donation/supporter system's own secrets and config. Both Cashfree
// and Razorpay are wired in (lib/payment-providers.js) alongside the
// `mock` gateway; see PAYMENTS_SETUP.md for what "wired in" does and
// does not mean here (no credentials exist in this deployment yet, so
// neither has been exercised against a real account).
//
// PAYMENT_WEBHOOK_SECRET is the `mock` gateway's own shared HMAC secret
// — Cashfree and Razorpay each carry their OWN secret below, because
// each gateway's webhook signing uses a different secret by design
// (Razorpay's is a dashboard-configured webhook secret, distinct from
// its API key secret; Cashfree signs with the same client secret used
// for API auth). Never collapse these into one shared value.
const PAYMENT_WEBHOOK_SECRET = defineSecret('PAYMENT_WEBHOOK_SECRET');
const CASHFREE_CLIENT_ID = defineSecret('CASHFREE_CLIENT_ID');
const CASHFREE_CLIENT_SECRET = defineSecret('CASHFREE_CLIENT_SECRET');
const RAZORPAY_KEY_SECRET = defineSecret('RAZORPAY_KEY_SECRET');
const RAZORPAY_WEBHOOK_SECRET = defineSecret('RAZORPAY_WEBHOOK_SECRET');

// PAYMENT_GATEWAY is this deployment's DEFAULT gateway. A donation can
// ask for a different one (createDonation's optional `gateway` field) as
// long as it's in PAYMENT_GATEWAYS_ENABLED — that's the whole "switch":
// a config value or a per-request field, never a code change, to move a
// donation (or the deployment's default) between Cashfree and Razorpay.
const PAYMENT_GATEWAY = defineString('PAYMENT_GATEWAY', { default: 'mock' });
const PAYMENT_GATEWAYS_ENABLED = defineString('PAYMENT_GATEWAYS_ENABLED', { default: 'mock' });
// Cashfree's API host AND credentials differ between sandbox and
// production (a separate Test App vs Live App from the same dashboard).
// Defaults to sandbox — the safe failure direction is "real money can't
// move yet", never the reverse.
const CASHFREE_ENV = defineString('CASHFREE_ENV', { default: 'sandbox' });
const CASHFREE_API_VERSION = defineString('CASHFREE_API_VERSION', { default: '2023-08-01' });
// Razorpay's key_id is the PUBLIC half of its API credential — meant to
// reach the browser (Checkout.js needs it), unlike key_secret above.
// Still a defineString rather than a literal here so sandbox (rzp_test_)
// vs production (rzp_live_) is a config change, not a redeploy.
const RAZORPAY_KEY_ID = defineString('RAZORPAY_KEY_ID', { default: '' });
const EMAIL_PROVIDER = defineString('EMAIL_PROVIDER', { default: 'console' });

const PAYMENT_SECRETS = [PAYMENT_WEBHOOK_SECRET, CASHFREE_CLIENT_ID, CASHFREE_CLIENT_SECRET, RAZORPAY_KEY_SECRET, RAZORPAY_WEBHOOK_SECRET];

/** Per-gateway config, built the moment it's needed rather than at
 *  module scope — mirrors providerConfig() below for the same reason:
 *  an unconfigured gateway's secrets should never be *.value()'d unless
 *  a donation actually asked for that gateway. */
function paymentGatewayConfig(gatewayId) {
  if (gatewayId === 'cashfree') {
    return {
      clientId: CASHFREE_CLIENT_ID.value(),
      clientSecret: CASHFREE_CLIENT_SECRET.value(),
      apiVersion: CASHFREE_API_VERSION.value(),
      baseUrl: CASHFREE_ENV.value() === 'production' ? 'https://api.cashfree.com' : 'https://sandbox.cashfree.com'
    };
  }
  if (gatewayId === 'razorpay') {
    return { keyId: RAZORPAY_KEY_ID.value(), keySecret: RAZORPAY_KEY_SECRET.value() };
  }
  return {};
}

/** The webhook secret for a given gateway — kept separate from
 *  paymentGatewayConfig so paymentWebhook (which needs only this) does
 *  not have to declare every gateway's API secret, only its own. */
function paymentWebhookSecret(gatewayId) {
  if (gatewayId === 'cashfree') return CASHFREE_CLIENT_SECRET.value(); // Cashfree signs webhooks with the same client secret used for API auth
  if (gatewayId === 'razorpay') return RAZORPAY_WEBHOOK_SECRET.value();
  return PAYMENT_WEBHOOK_SECRET.value();
}

/** Is `gatewayId` one this deployment actually accepts right now? A
 *  client asking for a gateway not in PAYMENT_GATEWAYS_ENABLED falls
 *  back to the configured default rather than being trusted outright —
 *  the enabled-list is what makes "switch to either" a deliberate
 *  config decision, not something a crafted request can pick on its own. */
function isGatewayEnabled(gatewayId) {
  return PAYMENT_GATEWAYS_ENABLED.value().split(',').map(s => s.trim()).filter(Boolean).includes(gatewayId);
}

const CHALLENGES = 'otp_challenges';
const USERS = 'users';
const DISPATCHES = 'workflow_dispatches';
const DONORS = 'donors';
const DONATIONS = 'donations';
const PAYMENTS = 'payments';
const PAYMENT_EVENTS = 'payment_events';
const RECEIPTS = 'receipts';
const RECEIPT_COUNTERS = 'receipt_counters';
const SUPPORTER_ENTITLEMENTS = 'supporter_entitlements';
const PUBLIC_SUPPORTERS = 'public_supporters';

function providerConfig(providerId) {
  return {
    templateName: OTP_TEMPLATE_NAME.value(),
    languageCode: OTP_TEMPLATE_LANG.value(),
    hasCopyCodeButton: true,
    phoneNumberId: providerId === 'whatsapp' ? WHATSAPP_PHONE_NUMBER_ID.value() : undefined,
    accessToken: providerId === 'whatsapp' ? WHATSAPP_TOKEN.value() : undefined,
    authKey: providerId === 'msg91' ? MSG91_AUTHKEY.value() : undefined,
    templateId: providerId === 'msg91' ? MSG91_TEMPLATE_ID.value() : undefined
  };
}

// =====================================================================
// sendOtp — generate a code, store only its hash, deliver via provider.
// =====================================================================
exports.sendOtp = onCall(
  {
    secrets: [WHATSAPP_TOKEN, WHATSAPP_PHONE_NUMBER_ID, MSG91_AUTHKEY, OTP_PEPPER],
    // Abuse control at the edge, before any of our code (or Meta's
    // billing) is reached.
    enforceAppCheck: false,
    cors: true
  },
  async (request) => {
    const providerId = OTP_PROVIDER.value();
    assertProviderAllowed(providerId);

    const phone = otpCore.normalizePhone(request.data?.phone, OTP_DEFAULT_COUNTRY.value());
    if (!phone) {
      throw new HttpsError('invalid-argument', 'That phone number does not look right. Include the country code, e.g. +91 98765 43210.');
    }

    const pepper = OTP_PEPPER.value();
    const docId = otpCore.challengeDocId(phone, pepper);
    const ref = db.collection(CHALLENGES).doc(docId);
    const now = Date.now();

    // The rate-limit check and the counter increment must be atomic, or
    // two simultaneous requests both pass the check and both send.
    const code = otpCore.generateOtp();
    let challenge;
    try {
      challenge = await db.runTransaction(async (tx) => {
        const snap = await tx.get(ref);
        const existing = snap.exists ? snap.data() : null;

        const limit = otpCore.checkSendRateLimit(existing, now);
        if (!limit.allowed) {
          const err = new Error(limit.reason);
          err.__rateLimit = limit;
          throw err;
        }

        const next = otpCore.buildChallenge({ code, now, existing, provider: providerId });
        tx.set(ref, next);
        return next;
      });
    } catch (e) {
      if (e.__rateLimit) {
        const secs = Math.ceil(e.__rateLimit.retryAfterMs / 1000);
        throw new HttpsError(
          'resource-exhausted',
          e.__rateLimit.reason === 'cooldown'
            ? `Please wait ${secs}s before requesting another code.`
            : `Too many code requests for this number. Try again in about ${Math.ceil(secs / 60)} minutes.`
        );
      }
      throw e;
    }

    // Deliver only AFTER the challenge is committed. The other order
    // risks sending a code we then fail to store — the user gets an SMS
    // that can never be verified.
    const provider = getProvider(providerId);
    const result = await provider.send({
      phone,
      code,
      config: providerConfig(providerId),
      fetchImpl: globalThis.fetch
    });

    if (!result.ok) {
      logger.error('OTP delivery failed', { provider: providerId, kind: result.kind, message: result.message });
      // Free the cooldown so a provider-side failure doesn't lock the
      // user out for a minute for something that wasn't their doing.
      await ref.set({ lastSentAt: 0 }, { merge: true }).catch(() => {});
      throw new HttpsError(
        result.retryable ? 'unavailable' : 'failed-precondition',
        result.kind === 'permanent'
          ? 'That number cannot receive messages on this channel.'
          : 'Could not send the code right now. Please try again shortly.'
      );
    }

    logger.info('OTP sent', { provider: providerId, docId, sendCount: challenge.sendCount });
    return { ok: true, expiresInSec: Math.round(otpCore.DEFAULT_TTL_MS / 1000), provider: providerId };
  }
);

// =====================================================================
// verifyOtp — check the code, mint a Firebase custom token on success.
// =====================================================================
exports.verifyOtp = onCall(
  { secrets: [OTP_PEPPER], cors: true },
  async (request) => {
    const phone = otpCore.normalizePhone(request.data?.phone, OTP_DEFAULT_COUNTRY.value());
    const code = request.data?.code;
    if (!phone) throw new HttpsError('invalid-argument', 'Missing or malformed phone number.');

    const pepper = OTP_PEPPER.value();
    const ref = db.collection(CHALLENGES).doc(otpCore.challengeDocId(phone, pepper));
    const now = Date.now();

    // Transactional so two parallel guesses cannot each see the same
    // attempt count and effectively double the allowance.
    const verdict = await db.runTransaction(async (tx) => {
      const snap = await tx.get(ref);
      const existing = snap.exists ? snap.data() : null;
      const v = otpCore.verifyChallenge(existing, code, now);
      if (v.patch) tx.set(ref, v.patch, { merge: true });
      return v;
    });

    if (!verdict.ok) {
      const messages = {
        no_challenge: 'Request a code first.',
        already_used: 'That code has already been used. Request a new one.',
        expired: 'That code has expired. Request a new one.',
        too_many_attempts: 'Too many incorrect attempts. Request a new code.',
        malformed: 'Enter the numeric code from the message.',
        incorrect: 'That code is not correct.'
      };
      // 'unauthenticated' for a wrong code, 'resource-exhausted' when the
      // challenge is burned — the client shows different UI for each.
      const burned = verdict.reason === 'too_many_attempts' || verdict.reason === 'expired' || verdict.reason === 'already_used';
      throw new HttpsError(burned ? 'resource-exhausted' : 'unauthenticated', messages[verdict.reason] || 'Verification failed.');
    }

    // Stable UID derived from the phone number, so the same person
    // signing in again lands on the same account and the same role.
    const uid = otpCore.phoneUid(phone, pepper);

    try {
      await getAuth().getUser(uid);
      await getAuth().updateUser(uid, { phoneNumber: phone }).catch(() => {});
    } catch (e) {
      if (e.code === 'auth/user-not-found') {
        await getAuth().createUser({ uid, phoneNumber: phone });
      } else {
        throw e;
      }
    }

    // Profile doc: created here with the default role. The client cannot
    // choose its own role — the rules forbid it, and so does this.
    const userRef = db.collection(USERS).doc(uid);
    const userSnap = await userRef.get();
    if (!userSnap.exists) {
      await userRef.set({
        displayName: '',
        email: '',
        phoneNumber: phone,
        role: 'basic',
        signInMethod: 'phone_otp',
        // Verifying a code sent over WhatsApp is not consent to receive
        // broadcasts on WhatsApp. Opt-in stays false until the person
        // ticks the box — see the consent UI in user-auth.js.
        whatsappOptIn: false,
        createdAt: FieldValue.serverTimestamp(),
        lastLoginAt: FieldValue.serverTimestamp()
      });
    } else {
      await userRef.update({
        phoneNumber: phone,
        lastLoginAt: FieldValue.serverTimestamp()
      }).catch(() => {});
    }

    const token = await getAuth().createCustomToken(uid);
    logger.info('OTP verified, custom token issued', { uid });
    return { ok: true, token };
  }
);

// =====================================================================
// whatsappWebhook — Meta's inbound callbacks (opt-outs, delivery state).
// =====================================================================
exports.whatsappWebhook = onRequest(
  { secrets: [WHATSAPP_VERIFY_TOKEN, WHATSAPP_APP_SECRET], cors: false },
  async (req, res) => {
    // Meta's one-time subscription handshake.
    if (req.method === 'GET') {
      const mode = req.query['hub.mode'];
      const token = req.query['hub.verify_token'];
      if (mode === 'subscribe' && token === WHATSAPP_VERIFY_TOKEN.value()) {
        return res.status(200).send(String(req.query['hub.challenge'] || ''));
      }
      return res.status(403).send('Forbidden');
    }

    if (req.method !== 'POST') return res.status(405).send('Method Not Allowed');

    // Verify the payload really came from Meta. Without this, anyone who
    // learns the URL can forge opt-outs (or, worse, opt-INs) for any
    // number. `req.rawBody` is provided by the Functions runtime and is
    // required here — re-serializing the parsed body would change the
    // bytes and break the signature.
    const signature = req.get('x-hub-signature-256') || '';
    const appSecret = WHATSAPP_APP_SECRET.value();
    if (!waLib.verifySignature(req.rawBody, signature, appSecret)) {
      logger.warn('Rejected WhatsApp webhook with bad signature');
      return res.status(401).send('Bad signature');
    }

    // Acknowledge fast: Meta retries on a slow response, which would
    // duplicate the work below.
    res.status(200).send('OK');

    try {
      const messages = waLib.parseInboundMessages(req.body);
      for (const msg of messages) {
        const intent = waLib.detectOptOutIntent(msg.text);
        if (!intent || !msg.from) continue;
        await applyOptState(msg.from, intent);
      }
    } catch (e) {
      logger.error('Failed processing WhatsApp webhook', { error: e?.message });
    }
  }
);

/** Applies an opt-in/opt-out to every profile holding that number. */
async function applyOptState(phone, intent) {
  const snap = await db.collection(USERS).where('phoneNumber', '==', phone).limit(10).get();
  if (snap.empty) {
    logger.info('Opt state change for unknown number', { intent });
    return;
  }
  const batchWrite = db.batch();
  for (const doc of snap.docs) {
    batchWrite.update(doc.ref, intent === 'opt_out'
      ? { whatsappOptIn: false, whatsappOptOutAt: FieldValue.serverTimestamp() }
      : { whatsappOptIn: true, whatsappOptOutAt: FieldValue.delete(), whatsappOptInAt: FieldValue.serverTimestamp() });
  }
  await batchWrite.commit();
  logger.info('Applied WhatsApp opt state', { intent, count: snap.size });
}

// =====================================================================
// runWhatsAppBroadcast — scheduled sender for campaigns marked due.
// =====================================================================
// Reads campaign docs from `broadcasts/` rather than hardcoding content,
// so scheduling a message is a Firestore edit, not a redeploy.
exports.runWhatsAppBroadcast = onSchedule(
  {
    // Daily at 07:00 IST. Cloud Scheduler's free tier covers 3 jobs.
    schedule: '0 7 * * *',
    timeZone: 'Asia/Kolkata',
    secrets: [WHATSAPP_TOKEN, WHATSAPP_PHONE_NUMBER_ID]
  },
  async () => {
    const now = Date.now();
    const due = await db.collection('broadcasts')
      .where('status', '==', 'scheduled')
      .where('sendAfter', '<=', Timestamp.fromMillis(now))
      .limit(5)
      .get();

    if (due.empty) {
      logger.info('No broadcasts due');
      return;
    }

    for (const campaignDoc of due.docs) {
      await runOneCampaign(campaignDoc, now);
    }
  }
);

async function runOneCampaign(campaignDoc, now) {
  const campaign = Object.assign({ id: campaignDoc.id }, campaignDoc.data());

  // Claim the campaign before doing any work, so an overlapping run
  // cannot send it a second time.
  const claimed = await db.runTransaction(async (tx) => {
    const fresh = await tx.get(campaignDoc.ref);
    if (fresh.data()?.status !== 'scheduled') return false;
    tx.update(campaignDoc.ref, { status: 'sending', startedAt: FieldValue.serverTimestamp() });
    return true;
  });
  if (!claimed) {
    logger.info('Campaign already claimed by another run', { id: campaign.id });
    return;
  }

  const usersSnap = await db.collection(USERS).where('whatsappOptIn', '==', true).limit(2000).get();
  const users = usersSnap.docs.map(d => Object.assign({ id: d.id }, d.data(), {
    whatsappLastBroadcastAt: d.data().whatsappLastBroadcastAt?.toMillis?.() ?? null
  }));

  const { recipients, skipped, total } = broadcastCore.selectAudience(users, campaign, now);
  const { toSend, deferred } = broadcastCore.applySendCap(recipients, campaign.maxPerRun ?? 500);

  logger.info('Broadcast audience', { id: campaign.id, total, eligible: recipients.length, sending: toSend.length, deferred: deferred.length, skipped });

  let sent = 0;
  let failed = 0;

  for (const group of broadcastCore.batch(toSend, 20)) {
    const results = await Promise.all(group.map(async (user) => {
      const payload = waLib.buildBroadcastTemplatePayload({
        to: user.phoneNumber,
        templateName: campaign.templateName,
        languageCode: campaign.languageCode || 'en',
        bodyParams: campaign.bodyParams || []
      });
      const r = await waLib.sendMessage({
        payload,
        phoneNumberId: WHATSAPP_PHONE_NUMBER_ID.value(),
        accessToken: WHATSAPP_TOKEN.value()
      });
      return { user, r };
    }));

    const writes = db.batch();
    for (const { user, r } of results) {
      if (r.ok) {
        sent++;
        writes.update(db.collection(USERS).doc(user.id), {
          [`whatsappCampaigns.${campaign.id}`]: FieldValue.serverTimestamp(),
          whatsappLastBroadcastAt: FieldValue.serverTimestamp()
        });
      } else {
        failed++;
        // A permanently undeliverable number is marked so later
        // campaigns skip it, rather than retrying forever.
        if (r.kind === 'permanent') {
          writes.update(db.collection(USERS).doc(user.id), { whatsappUndeliverable: true });
        }
        logger.warn('Broadcast send failed', { uid: user.id, kind: r.kind, message: r.message });
      }
    }
    await writes.commit();
  }

  await campaignDoc.ref.update({
    status: deferred.length ? 'scheduled' : 'sent',
    lastRunAt: FieldValue.serverTimestamp(),
    stats: { sent, failed, skipped, deferred: deferred.length }
  });

  logger.info('Broadcast complete', { id: campaign.id, sent, failed, deferred: deferred.length });
}

// =====================================================================
// The workflow buttons — listWorkflows / runWorkflow.
//
// The site is static on GitHub Pages, so a page cannot start a job by
// itself, and it must never hold a token that could: anything shipped to a
// browser is readable by whoever opens it. These two functions are the one
// server-side hop in between. They hold the token, check the caller is an
// admin against Firestore (not against anything the client claims), and
// will only ever ask GitHub for one of the five workflows named in
// lib/workflows-core.js.
//
// The equivalent with no token to protect is the GitHub Actions page
// itself, which is what admin/workflows.html falls back to when this is
// not deployed. Neither is more capable than the other; this one is just
// inside the site.
// =====================================================================

/** The caller's role, read from their own profile document. Never from the
 *  client: `is_superadmin` in localStorage decides what the UI shows, and a
 *  browser can set it to anything. */
async function callerRole(request) {
  const uid = request.auth && request.auth.uid;
  if (!uid) throw new HttpsError('unauthenticated', 'Sign in first.');
  const snap = await db.collection(USERS).doc(uid).get();
  return { uid, role: (snap.exists && snap.data().role) || 'basic' };
}

function githubHeaders(token) {
  return {
    Authorization: `Bearer ${token}`,
    Accept: 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28',
    'User-Agent': 'dge-admin-panel'
  };
}

/** Maps a WorkflowError onto the HttpsError the client sees. Anything else
 *  is logged and reported as a generic failure — a GitHub error body can
 *  carry the token's own scopes, which is not something to hand a browser. */
function asHttpsError(e, where) {
  if (e instanceof wf.WorkflowError) return new HttpsError(e.code, e.message);
  logger.error(`${where} failed`, { message: e && e.message });
  return new HttpsError('internal', 'GitHub could not be reached. Try the Actions page directly.');
}

exports.listWorkflows = onCall(
  { secrets: [GITHUB_DISPATCH_TOKEN], cors: true },
  async (request) => {
    const { role } = await callerRole(request);
    wf.assertRole(role, 'admin');

    const catalogue = wf.catalogue();
    let runs = {};
    try {
      // One call for the whole panel: the 30 newest runs across every
      // workflow, reduced to the newest of each one we know about. Asking
      // per workflow would be five round trips for the same five lines.
      const res = await fetch(
        `https://api.github.com/repos/${GITHUB_REPO.value()}/actions/runs?per_page=30`,
        { headers: githubHeaders(GITHUB_DISPATCH_TOKEN.value()) }
      );
      if (res.ok) runs = wf.latestRuns(await res.json());
      else logger.warn('Could not list runs', { status: res.status });
    } catch (e) {
      // A panel that lists the buttons but not their last run is still
      // usable; one that fails outright because the status lookup did is
      // not. Status is decoration, the buttons are the point.
      logger.warn('Could not list runs', { message: e && e.message });
    }

    return { ok: true, role, repo: GITHUB_REPO.value(), ref: wf.REF, workflows: catalogue, runs };
  }
);

exports.runWorkflow = onCall(
  { secrets: [GITHUB_DISPATCH_TOKEN], cors: true },
  async (request) => {
    const { uid, role } = await callerRole(request);

    let job, inputs;
    try {
      job = wf.findWorkflow(String(request.data && request.data.workflow || ''));
      if (!job) throw new wf.WorkflowError('invalid-argument', 'That is not one of the workflows this panel runs.');
      wf.assertRole(role, wf.minRoleFor(job));
      inputs = wf.buildInputs(job, request.data && request.data.inputs);
    } catch (e) {
      throw asHttpsError(e, 'runWorkflow');
    }

    // The audit row is written BEFORE the dispatch and updated after, so a
    // dispatch that succeeded at GitHub and then failed on the way back is
    // still recorded. "Who republished the corpus, and when" must not
    // depend on the happy path.
    const ref = db.collection(DISPATCHES).doc();
    const last = await db.collection(DISPATCHES)
      .where('uid', '==', uid).where('workflow', '==', job.id)
      .orderBy('at', 'desc').limit(1).get()
      .catch(() => null);
    try {
      const at = last && !last.empty ? last.docs[0].data().at : null;
      wf.checkCooldown(at && at.toMillis ? at.toMillis() : null, Date.now());
    } catch (e) {
      throw asHttpsError(e, 'runWorkflow');
    }

    await ref.set({
      uid, role, workflow: job.id, file: job.file, inputs,
      at: FieldValue.serverTimestamp(),
      result: 'pending'
    });

    let res;
    try {
      res = await fetch(
        `https://api.github.com/repos/${GITHUB_REPO.value()}/actions/workflows/${job.file}/dispatches`,
        {
          method: 'POST',
          headers: { ...githubHeaders(GITHUB_DISPATCH_TOKEN.value()), 'Content-Type': 'application/json' },
          body: JSON.stringify({ ref: wf.REF, inputs })
        }
      );
    } catch (e) {
      await ref.update({ result: 'unreachable' }).catch(() => {});
      throw asHttpsError(e, 'runWorkflow');
    }

    // 204 is the whole of a successful dispatch: GitHub queues the run and
    // returns no body, so there is no run id to hand back here. The panel
    // finds it by polling listWorkflows, which is why the run row carries
    // its start time.
    if (res.status !== 204) {
      const body = await res.text().catch(() => '');
      logger.error('Dispatch rejected', { status: res.status, workflow: job.id, body: body.slice(0, 300) });
      await ref.update({ result: `http_${res.status}` }).catch(() => {});
      throw new HttpsError(
        res.status === 401 || res.status === 403
          ? 'failed-precondition'
          : 'internal',
        res.status === 401 || res.status === 403
          ? 'GitHub refused the token. It may have expired, or lost its Actions permission.'
          : 'GitHub would not start that run. Try the Actions page directly.'
      );
    }

    await ref.update({ result: 'dispatched' }).catch(() => {});
    logger.info('Workflow dispatched', { uid, workflow: job.id, inputs });
    return { ok: true, workflow: job.id, name: job.name, inputs };
  }
);

// =====================================================================
// Donations, payments, receipts, supporters — Phase 1 foundation.
//
// No real payment gateway is wired in yet (see PAYMENTS_SETUP.md): the
// `mock` gateway (lib/payment-providers.js) exercises this entire
// pipeline — createDonation, a webhook, the state machine, the receipt,
// the public Supporters Wall entry — end to end, so it is all built and
// tested for real right now rather than only sketched. Adding a real
// gateway later means adding one entry to lib/payment-providers.js;
// nothing below this comment should need to change.
//
// The one rule everything here enforces: nothing the browser says about
// a payment's OUTCOME is ever trusted. `createDonation` only ever
// creates a CREATED/PENDING record; only a verified gateway webhook
// (paymentWebhook) can move a donation to SUCCESS, through
// payment-state.js's state machine, which refuses to walk a donation
// backwards or sideways from wherever a possibly-out-of-order or
// possibly-replayed event finds it.
// =====================================================================

/** Finds a donor by email, or creates one. Never runs as a client-facing
 *  query — only from inside createDonation, via the Admin SDK. */
async function findOrCreateDonor(donorFields) {
  const existing = await db.collection(DONORS).where('email', '==', donorFields.email).limit(1).get();
  if (!existing.empty) {
    const ref = existing.docs[0].ref;
    // Keep the donor record current, but never silently drop a PAN a
    // past donation supplied just because this one didn't include it.
    const patch = { fullName: donorFields.fullName, updatedAt: FieldValue.serverTimestamp() };
    if (donorFields.phone) patch.phone = donorFields.phone;
    if (donorFields.pan) patch.pan = donorFields.pan;
    await ref.update(patch);
    return ref.id;
  }
  const ref = db.collection(DONORS).doc();
  await ref.set({
    fullName: donorFields.fullName,
    email: donorFields.email,
    phone: donorFields.phone || '',
    countryCode: donorFields.countryCode,
    pan: donorFields.pan || '',
    createdAt: FieldValue.serverTimestamp(),
    updatedAt: FieldValue.serverTimestamp()
  });
  return ref.id;
}

/**
 * Atomically claims the next receipt number for the given calendar year.
 * A transaction, not a plain increment, because two donations reaching
 * SUCCESS in the same instant must never be handed the same number.
 */
async function nextReceiptNumber(year) {
  const ref = db.collection(RECEIPT_COUNTERS).doc(String(year));
  const seq = await db.runTransaction(async (tx) => {
    const snap = await tx.get(ref);
    const next = (snap.exists ? (snap.data().seq || 0) : 0) + 1;
    tx.set(ref, { seq: next }, { merge: true });
    return next;
  });
  return receiptCore.formatReceiptNumber(year, seq);
}

/**
 * Placeholder for Phase 4 (supporter_entitlements). No entitlement is
 * defined yet, so this is a deliberate no-op — the hook exists so
 * granting one later is a change here, not a new webhook code path.
 */
async function maybeGrantEntitlements(/* donation */) {
  return [];
}

// =====================================================================
// createDonation — validates input, creates/reuses the donor, opens a
// gateway order, and returns only what the browser needs to continue.
// =====================================================================
exports.createDonation = onCall(
  { secrets: PAYMENT_SECRETS, cors: true, enforceAppCheck: false },
  async (request) => {
    const data = request.data || {};

    const donorCheck = donationCore.validateDonorInput(data);
    if (!donorCheck.ok) {
      throw new HttpsError('invalid-argument', donorCheck.errors.join('; '));
    }

    const amountMinor = donationCore.majorToMinor(data.amount);
    if (amountMinor == null) {
      throw new HttpsError('invalid-argument', 'Enter a valid amount, e.g. 501 or 501.50.');
    }
    const amountCheck = donationCore.validateAmountMinor(amountMinor);
    if (!amountCheck.ok) {
      throw new HttpsError('invalid-argument', amountCheck.reason);
    }

    const currency = donationCore.DEFAULT_CURRENCY; // single-currency until Phase 5 (international)

    // The "switch to either gateway" mechanism: a client MAY name a
    // gateway (e.g. an admin flipping a campaign between Cashfree and
    // Razorpay, or a future UI that offers a choice), but only when it's
    // in PAYMENT_GATEWAYS_ENABLED — an unrecognized or disabled request
    // silently falls back to this deployment's own configured default
    // rather than trusting the client's say-so outright.
    const requestedGateway = typeof data.gateway === 'string' ? data.gateway : null;
    const gatewayId = (requestedGateway && isGatewayEnabled(requestedGateway)) ? requestedGateway : PAYMENT_GATEWAY.value();
    try {
      assertGatewayAllowed(gatewayId);
    } catch (e) {
      logger.error('createDonation: gateway not allowed in this environment', { gatewayId, message: e.message });
      throw new HttpsError('failed-precondition', 'Donations are not accepting payments on this deployment yet.');
    }
    const gateway = getGateway(gatewayId);

    const donorId = await findOrCreateDonor(donorCheck.donor);
    const donationReference = donationCore.generateDonationReference();

    // contributionType/fcraApplicable are DELIBERATELY hardcoded to the
    // conservative default regardless of the donor's own country until a
    // human confirms the Trust's FCRA status and turns this on for real
    // — see PAYMENTS_SETUP.md's FCRA boundary. This is not yet donor
    // country-aware; that logic is Phase 5 work, not a bug here.
    const donationRef = db.collection(DONATIONS).doc();
    await donationRef.set({
      donationReference,
      donorId,
      amountMinor,
      currency,
      gateway: gatewayId,
      contributionType: 'DOMESTIC',
      fcraApplicable: false,
      purposeCode: donationCore.sanitizeDisplayText(data.purpose, donationCore.MAX_PURPOSE_LEN),
      displayName: !!data.displayName,
      displayAmount: !!data.displayAmount,
      status: 'CREATED',
      createdAt: FieldValue.serverTimestamp(),
      paidAt: null,
      updatedAt: FieldValue.serverTimestamp()
    });

    let order;
    try {
      order = await gateway.createOrder({
        donationReference,
        amountMinor,
        currency,
        customer: { donorId, name: donorCheck.donor.fullName, email: donorCheck.donor.email, phone: donorCheck.donor.phone },
        returnUrl: typeof data.returnUrl === 'string' ? data.returnUrl : null,
        config: paymentGatewayConfig(gatewayId)
      });
    } catch (e) {
      logger.error('createDonation: gateway order creation failed', { gatewayId, message: e.message });
      await donationRef.update({ status: 'FAILED', updatedAt: FieldValue.serverTimestamp() });
      throw new HttpsError('unavailable', 'Could not start the payment. Please try again shortly.');
    }
    if (!order || !order.ok) {
      await donationRef.update({ status: 'FAILED', updatedAt: FieldValue.serverTimestamp() });
      throw new HttpsError('unavailable', 'Could not start the payment. Please try again shortly.');
    }

    await db.collection(PAYMENTS).doc().set({
      donationId: donationRef.id,
      gateway: gatewayId,
      gatewayOrderId: order.gatewayOrderId,
      gatewayPaymentId: null,
      gatewayStatus: null,
      amountMinor,
      currency,
      paymentMethod: null,
      createdAt: FieldValue.serverTimestamp(),
      updatedAt: FieldValue.serverTimestamp()
    });
    await donationRef.update({ status: 'PENDING', updatedAt: FieldValue.serverTimestamp() });

    logger.info('Donation created', { donationReference, gatewayId, amountMinor });
    return { ok: true, donationReference, checkout: order.checkout };
  }
);

// =====================================================================
// paymentWebhook — the ONLY thing that may move a donation to SUCCESS.
// Signature-verified, idempotent (payment_events/{gateway}_{eventId}),
// and drives every transition through payment-state.js so a stale or
// replayed event can never walk a donation backwards.
// =====================================================================
exports.paymentWebhook = onRequest(
  { secrets: PAYMENT_SECRETS, cors: false },
  async (req, res) => {
    if (req.method !== 'POST') { res.status(405).send('Method Not Allowed'); return; }

    // Each gateway's own dashboard is configured with its OWN webhook
    // URL — .../paymentWebhook?gateway=cashfree, ?gateway=razorpay —
    // so this one endpoint already serves every gateway this deployment
    // accepts; adding a gateway never means adding a new endpoint.
    const gatewayId = String(req.query.gateway || '');
    let gateway;
    try {
      assertGatewayAllowed(gatewayId);
      gateway = getGateway(gatewayId);
    } catch (e) {
      logger.warn('paymentWebhook: unknown or disallowed gateway', { gatewayId, message: e.message });
      res.status(400).send('Unknown gateway');
      return;
    }

    // `req.rawBody` (provided by the Functions runtime) is required here —
    // re-serializing req.body would change the exact bytes and break the
    // signature, the same reasoning as the WhatsApp webhook above.
    if (!gateway.verifyWebhookSignature(req.rawBody, req.headers, paymentWebhookSecret(gatewayId))) {
      logger.warn('paymentWebhook: bad signature', { gatewayId });
      res.status(401).send('Bad signature');
      return;
    }

    const event = gateway.parseWebhookEvent(req.rawBody, req.headers);
    if (!event) {
      logger.warn('paymentWebhook: unparseable event', { gatewayId });
      res.status(400).send('Unparseable event');
      return;
    }

    // Idempotency: the event doc's ID IS the uniqueness constraint — a
    // second delivery of the same event collides on the same doc ID
    // rather than needing a separate unique-index lookup.
    const eventRef = db.collection(PAYMENT_EVENTS).doc(`${gatewayId}_${event.eventId}`);
    const claimed = await db.runTransaction(async (tx) => {
      const snap = await tx.get(eventRef);
      if (snap.exists && snap.data().processingStatus === 'PROCESSED') return false; // already handled — true idempotent no-op
      tx.set(eventRef, {
        gateway: gatewayId,
        gatewayEventId: event.eventId,
        eventType: event.eventType,
        gatewayOrderId: event.gatewayOrderId,
        gatewayPaymentId: event.gatewayPaymentId,
        receivedAt: FieldValue.serverTimestamp(),
        processingStatus: 'RECEIVED'
      }, { merge: true });
      return true;
    });
    if (!claimed) {
      res.status(200).send('OK (already processed)');
      return;
    }

    try {
      await processPaymentEvent(gatewayId, event, eventRef);
      res.status(200).send('OK');
    } catch (e) {
      logger.error('paymentWebhook: processing failed', { gatewayId, eventId: event.eventId, message: e.message });
      await eventRef.set({ processingStatus: 'ERROR', errorMessage: String(e.message || e), processedAt: FieldValue.serverTimestamp() }, { merge: true }).catch(() => {});
      // 200, not 500: our own failure to process is not a reason to make
      // the gateway retry-storm an endpoint that will fail identically
      // every time. The event is durably recorded either way (see the
      // ERROR status above) for a human to investigate.
      res.status(200).send('Recorded, not processed');
    }
  }
);

/** The actual state update, split out from the HTTP handler so it has no
 *  req/res in its signature — easier to reason about, and reusable from
 *  a future manual-reconciliation tool without faking an HTTP request. */
async function processPaymentEvent(gatewayId, event, eventRef) {
  // A recognized-but-not-actionable event (payment.authorized,
  // refund.failed, Cashfree's PAYMENT_CHARGES_WEBHOOK, ...) — the
  // adapter already normalized this to status: null. Acknowledged and
  // recorded, but there is no donation to look up and nothing to change.
  if (event.status === null) {
    await eventRef.set({ processingStatus: 'PROCESSED', errorMessage: 'no-op event type, nothing to apply', processedAt: FieldValue.serverTimestamp() }, { merge: true });
    return;
  }

  // Most events carry the gateway's order id, which is how a payment doc
  // is normally found. Razorpay's own refund.processed payload is the
  // one exception this session could verify (its `refund.entity` carries
  // only `payment_id`, not `order_id` — see PAYMENTS_SETUP.md) — falling
  // back to a gatewayPaymentId lookup covers it without a gateway-specific
  // branch here.
  if (!event.gatewayOrderId && !event.gatewayPaymentId) {
    await eventRef.set({ processingStatus: 'ERROR', errorMessage: 'event carried no order id or payment id', processedAt: FieldValue.serverTimestamp() }, { merge: true });
    return;
  }

  const lookupField = event.gatewayOrderId ? 'gatewayOrderId' : 'gatewayPaymentId';
  const lookupValue = event.gatewayOrderId || event.gatewayPaymentId;
  const paymentSnap = await db.collection(PAYMENTS).where(lookupField, '==', lookupValue).limit(1).get();
  if (paymentSnap.empty) {
    logger.warn('paymentWebhook: no payment matches this event', { gatewayId, lookupField, lookupValue });
    await eventRef.set({ processingStatus: 'ERROR', errorMessage: 'no matching payment/donation', processedAt: FieldValue.serverTimestamp() }, { merge: true });
    return;
  }
  const paymentRef = paymentSnap.docs[0].ref;
  const donationId = paymentSnap.docs[0].data().donationId;
  const donationRef = db.collection(DONATIONS).doc(donationId);

  const outcome = await db.runTransaction(async (tx) => {
    const donationSnap = await tx.get(donationRef);
    if (!donationSnap.exists) return { applied: false, reason: 'donation not found' };
    const donation = donationSnap.data();

    // A refund event only ever reports "REFUNDED" from the adapter (see
    // payment-providers.js) — whether that's a FULL or PARTIAL refund is
    // decided HERE, gateway-agnostically, by comparing the refunded
    // amount against the donation's own original amount, so neither
    // gateway's adapter needs to know the donation's history to answer
    // a question only this function has the context to answer.
    let reportedStatus = event.status;
    if (reportedStatus === 'REFUNDED' && Number.isInteger(event.refundAmountMinor) && event.refundAmountMinor < donation.amountMinor) {
      reportedStatus = 'PARTIALLY_REFUNDED';
    }

    const transition = paymentState.nextStatus(donation.status, reportedStatus);
    if (!transition.ok) {
      return { applied: false, reason: transition.reason };
    }

    tx.update(paymentRef, {
      gatewayPaymentId: event.gatewayPaymentId,
      gatewayStatus: event.status,
      paymentMethod: event.paymentMethod || null,
      updatedAt: FieldValue.serverTimestamp()
    });

    if (!transition.changed) {
      // Same status reported again — nothing to change on the donation,
      // but the payment doc above still absorbs any new detail (e.g. a
      // paymentMethod that arrived on a later retry of the same event).
      return { applied: true, changed: false, status: transition.status, donation };
    }

    const patch = { status: transition.status, updatedAt: FieldValue.serverTimestamp() };
    if (transition.status === 'SUCCESS') patch.paidAt = FieldValue.serverTimestamp();
    tx.update(donationRef, patch);
    return { applied: true, changed: true, status: transition.status, donation: Object.assign({}, donation, patch) };
  });

  if (!outcome.applied) {
    logger.warn('paymentWebhook: transition rejected', { gatewayId, donationId, reason: outcome.reason });
    await eventRef.set({ processingStatus: 'IGNORED', errorMessage: outcome.reason, donationId, processedAt: FieldValue.serverTimestamp() }, { merge: true });
    return;
  }

  if (outcome.changed && outcome.status === 'SUCCESS') {
    await onDonationSucceeded(donationId, outcome.donation);
  }

  await eventRef.set({ processingStatus: 'PROCESSED', donationId, processedAt: FieldValue.serverTimestamp() }, { merge: true });
}

/** Runs once, the moment a donation is first confirmed SUCCESS: receipt,
 *  email, the public Supporters Wall entry, and any entitlement. */
async function onDonationSucceeded(donationId, donation) {
  const year = new Date().getUTCFullYear();
  const receiptNumber = await nextReceiptNumber(year);

  await db.collection(RECEIPTS).doc(donationId).set({
    receiptNumber,
    receiptStatus: 'GENERATED',
    emailSentAt: null,
    createdAt: FieldValue.serverTimestamp()
  });

  const donorSnap = await db.collection(DONORS).doc(donation.donorId).get();
  const donor = donorSnap.exists ? donorSnap.data() : { fullName: '', email: '' };

  // Email failure must never reverse the payment or the receipt above —
  // both are already committed by the time this runs. A failed send
  // just leaves emailSentAt null for a later retry to pick up.
  try {
    const { subject, textBody } = receiptCore.buildReceiptEmail({
      receiptNumber,
      donorName: donor.fullName,
      amountMinor: donation.amountMinor,
      currency: donation.currency,
      paidAtIso: new Date().toISOString(),
      paymentMethod: null
    });
    const emailResult = await getEmailProvider(EMAIL_PROVIDER.value()).send({ to: donor.email, subject, textBody });
    if (emailResult.ok) {
      await db.collection(RECEIPTS).doc(donationId).set({ emailSentAt: FieldValue.serverTimestamp() }, { merge: true });
    }
  } catch (e) {
    logger.error('onDonationSucceeded: receipt email failed (donation remains SUCCESS)', { donationId, message: e.message });
  }

  if (donation.displayName) {
    await db.collection(PUBLIC_SUPPORTERS).doc(donationId).set({
      donationReference: donation.donationReference,
      displayName: donor.fullName || 'Anonymous',
      amountMinor: donation.displayAmount ? donation.amountMinor : null,
      currency: donation.currency,
      paidAt: FieldValue.serverTimestamp()
    });
  }

  const granted = await maybeGrantEntitlements(donation);
  logger.info('Donation succeeded', { donationId, receiptNumber, entitlementsGranted: granted.length });
}

// =====================================================================
// getDonationStatus — the server-verified truth a success page must
// check before it ever says "thank you". The donation reference itself
// is the capability (crypto-random, effectively unguessable) — no
// sign-in is required to check on a donation you just made.
// =====================================================================
exports.getDonationStatus = onCall(
  { cors: true, enforceAppCheck: false },
  async (request) => {
    const ref = String((request.data && request.data.donationReference) || '');
    if (!donationCore.isWellFormedDonationReference(ref)) {
      throw new HttpsError('invalid-argument', 'That does not look like a donation reference.');
    }
    const snap = await db.collection(DONATIONS).where('donationReference', '==', ref).limit(1).get();
    if (snap.empty) throw new HttpsError('not-found', 'No donation found for that reference.');

    const donation = snap.docs[0];
    const receiptSnap = await db.collection(RECEIPTS).doc(donation.id).get();

    return {
      ok: true,
      status: donation.data().status,
      amountMinor: donation.data().amountMinor,
      currency: donation.data().currency,
      receiptNumber: receiptSnap.exists ? receiptSnap.data().receiptNumber : null
    };
  }
);

// Exported for tests that need the internals without a live project.
// (The signature check itself lives in lib/whatsapp.js, where it is
// testable without loading firebase-admin — see tests/whatsapp.test.js.)
exports.__internal = { applyOptState, runOneCampaign, findOrCreateDonor, nextReceiptNumber, processPaymentEvent, onDonationSucceeded };
