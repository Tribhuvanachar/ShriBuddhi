// index.js — DGE's Cloud Functions: OTP over WhatsApp/MSG91, WhatsApp
// broadcasts, and the inbound webhook that honours opt-outs.
//
// Everything security-critical lives in ./lib/*-core.js as pure
// functions with tests. This file is the Firebase-shaped shell around
// them: it reads secrets, runs Firestore transactions, and mints custom
// tokens. Keep it that way — logic that lands here instead of in lib/
// is logic that cannot be tested without a live project.
//
// Deploy: cd firebase && firebase deploy --only functions
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
const { getStorage } = require('firebase-admin/storage');

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
const corpusAccess = require('./lib/corpus-access');

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
const GITHUB_DISPATCH_TOKEN = defineSecret('GITHUB_DISPATCH_TOKEN');
// The workflows live in the private repository -- all 57 of them. The public site
// repository has no .github/ at all, so the old default dispatched into a repository
// with nothing to dispatch. deploy-firebase-functions.yml writes this value into the
// deploy .env as well; this default is the floor under that, not the source of truth.
const GITHUB_REPO = defineString('GITHUB_REPO', { default: 'Tribhuvanachar/shribuddhi' });

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

// --- The authenticated corpus proxy ----------------------------------
//
// WHY THIS EXISTS. Every gate up to now has been UI-level, and role-access.js
// says so in its own header: the corpus files are public static assets, so
// anyone who knows or guesses a path can fetch a gated grantha's data.json
// straight from Hosting. This function is the other architecture — corpus
// text served from a PRIVATE bucket, one request at a time, with the same
// shelf/gate decision applied before a byte goes out.
//
// It is a SWITCH, not a migration: with corpusBase unset in config.js the
// reader fetches static files exactly as it does today and this function is
// never called. Set corpusBase and every corpus read goes through here
// instead. Nothing else in the reader changes. See CORPUS_PROXY.md.
//
// Shape:  GET <base>/<corpus path>/data.json
//         Authorization: Bearer <Firebase ID token>   (optional)
//
// A signed-out visitor is allowed — the library is public, the shelf is what
// narrows it — so a missing token means the 'anonymous' role rather than a
// refusal. A token that is present but bad IS refused (401), because
// silently demoting an expired session to anonymous would show a subscriber
// a "not found" for a text they pay for.
const CORPUS_BUCKET = defineString('CORPUS_BUCKET', { default: '' });
const CORPUS_PREFIX = defineString('CORPUS_PREFIX', { default: 'corpus/' });
// Where the live shelf is read from, so widening it is a commit + Hosting
// deploy rather than a function redeploy. Defaults to the project's own
// Hosting origin; the bundled copy below is the floor if this is unreachable.
const CORPUS_CONFIG_URL = defineString('CORPUS_CONFIG_URL', { default: '' });

const CORPUS_CONFIG_TTL_MS = 5 * 60 * 1000;
let corpusConfigCache = null;   // { at, overrides, roleAccess }

/**
 * The shelf, from Hosting if it answers and from the deployed snapshot if it
 * does not.
 *
 * The bundled snapshot (functions/library-overrides.json, copied in by
 * deploy-firebase-functions.yml) matters more than it looks: without it, a
 * config fetch that fails on a cold start leaves the function with no shelf
 * at all, and "no shelf" means everything is open. Failing open on a network
 * blip is exactly the failure this whole function exists to prevent. With
 * the snapshot the worst case is a stale shelf, and a stale shelf is only
 * wrong in the widening direction — the deploy that narrows it ships the new
 * snapshot with it.
 */
async function corpusOverrides() {
  const url = CORPUS_CONFIG_URL.value();
  if (url) {
    try {
      const res = await fetch(url, { headers: { accept: 'application/json' } });
      if (res.ok) return await res.json();
      logger.warn('corpus config fetch was not ok', { status: res.status });
    } catch (e) {
      logger.warn('corpus config fetch failed', { message: e && e.message });
    }
  }
  try {
    return require('./library-overrides.json');
  } catch (e) {
    logger.error('no corpus config at all — the shelf cannot be applied', { message: e && e.message });
    return null;
  }
}

/** Both config sources, cached briefly so a burst of page loads costs one read. */
async function corpusConfig() {
  const now = Date.now();
  if (corpusConfigCache && (now - corpusConfigCache.at) < CORPUS_CONFIG_TTL_MS) {
    return corpusConfigCache.value;
  }
  const [overrides, gatesSnap] = await Promise.all([
    corpusOverrides(),
    db.collection('config').doc('roleAccess').get().catch((e) => {
      logger.warn('roleAccess read failed', { message: e && e.message });
      return null;
    })
  ]);
  // A config read that failed is NOT the same as a config that says
  // "nothing is gated". Keep the last good value rather than opening up.
  if (!overrides && corpusConfigCache) return corpusConfigCache.value;
  const value = corpusAccess.configFrom(
    overrides,
    gatesSnap && gatesSnap.exists ? gatesSnap.data() : (corpusConfigCache ? { gates: corpusConfigCache.value.gates } : null)
  );
  corpusConfigCache = { at: now, value };
  return value;
}

/** The caller's stored role, or 'anonymous'. Throws a 401-shaped error for a bad token. */
async function corpusCallerRole(req) {
  const header = String(req.get('authorization') || req.get('Authorization') || '');
  const m = /^Bearer\s+(.+)$/i.exec(header.trim());
  if (!m) return { uid: null, role: corpusAccess.ANONYMOUS };
  let decoded;
  try {
    decoded = await getAuth().verifyIdToken(m[1].trim());
  } catch (e) {
    const err = new Error('bad token');
    err.corpusStatus = 401;
    throw err;
  }
  const snap = await db.collection(USERS).doc(decoded.uid).get();
  return { uid: decoded.uid, role: (snap.exists && snap.data().role) || 'basic' };
}

exports.corpusFile = onRequest({ cors: true, maxInstances: 40 }, async (req, res) => {
  if (req.method === 'OPTIONS') { res.status(204).send(''); return; }
  if (req.method !== 'GET' && req.method !== 'HEAD') {
    res.status(405).json({ error: 'method' });
    return;
  }

  // The response depends on who is asking, so it must never land in a shared
  // cache. Both headers are needed: Vary alone does not stop a proxy that
  // ignores it, private alone does not tell a CDN which key to split on.
  res.set('Cache-Control', 'private, max-age=300');
  res.set('Vary', 'Authorization');

  const bucketName = CORPUS_BUCKET.value();
  if (!bucketName) {
    // The switch is off. Say so plainly — this one is a misconfiguration, not
    // a refusal, and hiding it would waste somebody's afternoon.
    res.status(503).json({ error: 'not-configured', hint: 'Set CORPUS_BUCKET to the private corpus bucket.' });
    return;
  }

  const raw = req.query && req.query.path ? String(req.query.path) : String(req.path || '').replace(/^\/+/, '');
  const objectPath = corpusAccess.objectNameFor(raw);
  if (!objectPath) { res.status(404).json({ error: 'not-found' }); return; }

  let caller;
  try {
    caller = await corpusCallerRole(req);
  } catch (e) {
    if (e && e.corpusStatus === 401) { res.status(401).json({ error: 'auth' }); return; }
    logger.error('corpusFile role resolution failed', { message: e && e.message });
    res.status(500).json({ error: 'internal' });
    return;
  }

  const cfg = await corpusConfig();
  const display = corpusAccess.displayPathFor(objectPath, cfg.moves);
  const verdict = corpusAccess.decide(display, caller.role, cfg);
  if (!verdict.allowed) {
    // 404, not 403, and no reason in the body. "Forbidden" on
    // darshana/.../SetuTila confirms the text exists and is worth attacking;
    // a flat not-found tells a prober nothing it did not already know. The
    // real reason goes to the log, where the lead can read it.
    logger.info('corpus refused', { path: display, role: caller.role, reason: verdict.reason });
    res.status(404).json({ error: 'not-found' });
    return;
  }

  const objectName = CORPUS_PREFIX.value() + objectPath;
  try {
    const file = getStorage().bucket(bucketName).file(objectName);
    const [meta] = await file.getMetadata();
    const etag = meta.etag ? String(meta.etag) : null;
    if (etag) res.set('ETag', etag);
    if (etag && req.get('if-none-match') === etag) { res.status(304).end(); return; }
    res.set('Content-Type', 'application/json; charset=utf-8');
    if (meta.size) res.set('Content-Length', String(meta.size));
    if (req.method === 'HEAD') { res.status(200).end(); return; }
    await new Promise((resolve, reject) => {
      file.createReadStream()
        .on('error', reject)
        .on('end', resolve)
        .pipe(res);
    });
  } catch (e) {
    if (e && (e.code === 404 || e.code === 'ENOENT')) { res.status(404).json({ error: 'not-found' }); return; }
    logger.error('corpusFile read failed', { object: objectName, message: e && e.message });
    if (!res.headersSent) res.status(502).json({ error: 'storage' });
    else res.end();
  }
});

// --- Server-side PDF (the Blaze half of the book builder) -------------
//
// WHY A SERVER RENDERS THIS AT ALL. js/book-builder.js already produces a
// finished book and hands it to the browser's own print engine, and that is
// still the default path — it is free, it needs no account, and it is the
// only engine in reach that shapes Devanagari conjuncts correctly (jsPDF and
// pdfmake place glyphs one code point at a time, so क्ष and every other
// saṃyuktākṣara come out broken). What it cannot do is hand back a FILE. The
// person has to find Save as PDF in a print dialog, pick the paper, and hope.
//
// This is the one-tap version: the same HTML, rendered by the same engine,
// returned as a .pdf. It needs the Blaze plan because it runs a real browser.
//
// THE RISK, STATED PLAINLY. This is a headless Chromium rendering a document
// a caller sent us. Left alone it would fetch whatever the document points
// at — an internal URL, a file:// path, a slow endpoint — so every request it
// makes is aborted unless bookRender.allowedRequest says otherwise, and that
// allows only data:/blob:/about:blank. JavaScript is off. The client inlines
// the stylesheet and the imprint icon before posting, so a correct book needs
// nothing from the network and a document that does was not one of ours.
const bookRender = require('./lib/book-render');

let puppeteerModule;       // resolved once, lazily — see the catch below
let browserPromise = null; // one browser per warm instance, not one per request

function getPuppeteer() {
  if (puppeteerModule === undefined) {
    try {
      puppeteerModule = require('puppeteer');
    } catch (e) {
      // Deliberately not fatal at load time. puppeteer is a heavy, awkward
      // dependency (it downloads a browser at install), and a project that
      // has not installed it should still deploy and run sendOtp, donations
      // and the corpus proxy. Only this one endpoint goes dark, and it says
      // why.
      puppeteerModule = null;
      logger.warn('puppeteer is not installed — renderBook will answer 503', { message: e && e.message });
    }
  }
  return puppeteerModule;
}

async function getBrowser() {
  const puppeteer = getPuppeteer();
  if (!puppeteer) return null;
  if (!browserPromise) {
    browserPromise = puppeteer.launch({
      headless: 'new',
      args: [
        '--no-sandbox',                 // required inside the Cloud Run container
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',      // /dev/shm is tiny here; without this Chromium dies mid-render
        '--font-render-hinting=none'
      ]
    }).catch((e) => { browserPromise = null; throw e; });
  }
  return browserPromise;
}

exports.renderBook = onRequest(
  { cors: true, memory: '1GiB', timeoutSeconds: 120, maxInstances: 3, concurrency: 1 },
  async (req, res) => {
    if (req.method === 'OPTIONS') { res.status(204).send(''); return; }
    if (req.method !== 'POST') { res.status(405).json({ error: 'method' }); return; }

    // Unlike the corpus proxy, this one requires an account. Rendering costs
    // real CPU on someone's card, so "who is this" is not optional and there
    // is no anonymous tier.
    let uid, role;
    try {
      const header = String(req.get('authorization') || '');
      const m = /^Bearer\s+(.+)$/i.exec(header.trim());
      if (!m) { res.status(401).json({ error: 'auth' }); return; }
      const decoded = await getAuth().verifyIdToken(m[1].trim());
      uid = decoded.uid;
      const snap = await db.collection(USERS).doc(uid).get();
      role = (snap.exists && snap.data().role) || 'basic';
    } catch (e) {
      res.status(401).json({ error: 'auth' });
      return;
    }

    let capabilities = {};
    try {
      const snap = await db.collection('config').doc('roleAccess').get();
      if (snap.exists) capabilities = snap.data().capabilities || {};
    } catch (e) {
      // A capability map we could not read is not an open one.
      logger.warn('renderBook could not read capabilities', { message: e && e.message });
    }
    if (!bookRender.mayRenderBook(role, capabilities)) {
      // 403 rather than the corpus proxy's 404: there is nothing to hide
      // here. The caller knows the feature exists — they pressed its button —
      // and "you do not have this yet" is the useful answer.
      res.status(403).json({ error: 'forbidden', capability: 'book' });
      return;
    }

    const body = req.body && typeof req.body === 'object' ? req.body : {};
    const bad = bookRender.checkHtml(body.html, bookRender.MAX_HTML_BYTES);
    if (bad) { res.status(400).json({ error: bad }); return; }

    const browser = await getBrowser().catch((e) => {
      logger.error('could not launch the renderer', { message: e && e.message });
      return null;
    });
    if (!browser) {
      res.status(503).json({
        error: 'renderer-unavailable',
        hint: 'The PDF service is not installed on this deployment. Use Print → Save as PDF in the reader.'
      });
      return;
    }

    let page;
    try {
      page = await browser.newPage();
      await page.setJavaScriptEnabled(false);
      await page.setRequestInterception(true);
      page.on('request', (r) => {
        if (bookRender.allowedRequest(r.url())) r.continue();
        else r.abort();
      });
      await page.setContent(body.html, { waitUntil: 'load', timeout: 30000 });
      const pdf = await page.pdf(bookRender.pdfOptionsFor(body.spec));
      res.set('Content-Type', 'application/pdf');
      res.set('Content-Disposition',
        bookRender.contentDispositionFor((body.spec && body.spec.title) || 'Sarvamula book'));
      res.set('Cache-Control', 'private, no-store');
      res.status(200).end(pdf);
      logger.info('book rendered', { uid, role, bytes: pdf.length });
    } catch (e) {
      logger.error('renderBook failed', { uid, message: e && e.message });
      if (!res.headersSent) res.status(500).json({ error: 'render-failed' });
      else res.end();
    } finally {
      if (page) await page.close().catch(() => {});
    }
  }
);

// Exported for tests that need the internals without a live project.
// (The signature check itself lives in lib/whatsapp.js, where it is
// testable without loading firebase-admin — see tests/whatsapp.test.js.)
exports.__internal = { applyOptState, runOneCampaign, findOrCreateDonor, nextReceiptNumber, processPaymentEvent, onDonationSucceeded };
