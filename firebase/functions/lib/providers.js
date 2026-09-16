// providers.js — pluggable OTP delivery channels.
//
// The point of this file: the OTP state machine (otp-core.js) and the
// sign-in flow (index.js) do not know or care how a code reaches the
// user. Adding a channel means adding an entry here, not touching the
// security-critical code. That is also why WhatsApp and MSG91 could be
// built as one feature rather than two — FIREBASE_SETUP.md had already
// identified that both need the identical "external OTP → Firebase
// custom token" backend, and only differ in the send call below.
'use strict';

const whatsapp = require('./whatsapp');

/**
 * Each provider exposes: send({ phone, code, config, fetchImpl }) and
 * resolves to { ok, retryable?, kind?, message?, messageId? }.
 */
const providers = {
  /**
   * Meta WhatsApp Cloud API. ~₹0.145 per authentication template in
   * India versus ~$0.01 (~₹0.85) for Firebase's own SMS — roughly 6x
   * cheaper, which is the reason this path exists at all.
   */
  whatsapp: {
    id: 'whatsapp',
    requiresSecrets: ['WHATSAPP_TOKEN', 'WHATSAPP_PHONE_NUMBER_ID'],
    async send({ phone, code, config, fetchImpl }) {
      const payload = whatsapp.buildAuthTemplatePayload({
        to: phone,
        code,
        templateName: config.templateName,
        languageCode: config.languageCode,
        hasCopyCodeButton: config.hasCopyCodeButton
      });
      return whatsapp.sendMessage({
        payload,
        phoneNumberId: config.phoneNumberId,
        accessToken: config.accessToken,
        fetchImpl
      });
    }
  },

  /**
   * MSG91 — the India-focused SMS gateway FIREBASE_SETUP.md flagged as
   * the cheap SMS option. Uses the plain "send SMS" flow API with our
   * own generated code, NOT MSG91's own OTP product, so that the code
   * lifecycle stays in otp-core.js and is identical across channels
   * (one expiry policy, one attempt cap, one audit trail).
   */
  msg91: {
    id: 'msg91',
    requiresSecrets: ['MSG91_AUTHKEY'],
    async send({ phone, code, config, fetchImpl = globalThis.fetch }) {
      const url = 'https://control.msg91.com/api/v5/flow/';
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 10000);
      try {
        const res = await fetchImpl(url, {
          method: 'POST',
          headers: {
            'authkey': config.authKey,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            template_id: config.templateId,
            short_url: '0',
            recipients: [{ mobiles: String(phone).replace(/^\+/, ''), OTP: code }]
          }),
          signal: controller.signal
        });
        const body = await res.json().catch(() => ({}));
        if (!res.ok || body?.type === 'error') {
          return {
            ok: false,
            retryable: res.status >= 500,
            kind: res.status >= 500 ? 'server_error' : 'permanent',
            message: body?.message || `HTTP ${res.status}`
          };
        }
        return { ok: true, messageId: body?.request_id || null };
      } catch (e) {
        return { ok: false, retryable: true, kind: 'network', message: e?.message || String(e) };
      } finally {
        clearTimeout(timer);
      }
    }
  },

  /**
   * Dev-only channel: logs the code instead of delivering it. Exists so
   * the whole sign-in flow can be exercised end to end against the
   * emulator without spending money or owning a phone number.
   *
   * index.js refuses to load this provider unless the function is
   * running against an emulator — see assertProviderAllowed. A dev
   * backdoor that survives into production is exactly the kind of thing
   * that turns a test convenience into an auth bypass.
   */
  console: {
    id: 'console',
    requiresSecrets: [],
    async send({ phone, code }) {
      console.log(`[otp:console] code for ${phone} is ${code}`);
      // Test seam: with DGE_OTP_ECHO_FILE set, also append the code to
      // that file so an automated end-to-end test can read it back
      // deterministically instead of scraping (and racing) the emulator's
      // log output. Guarded twice over -- this provider is already
      // emulator-only via assertProviderAllowed, and the env var has to
      // be set deliberately -- because a file full of live OTPs is exactly
      // the sort of convenience that must never reach a real deployment.
      const echoPath = process.env.DGE_OTP_ECHO_FILE;
      if (echoPath) {
        try {
          require('fs').appendFileSync(echoPath, `${phone} ${code}\n`);
        } catch (e) {
          console.warn('[otp:console] could not write echo file:', e.message);
        }
      }
      return { ok: true, messageId: 'console-' + Date.now() };
    }
  }
};

function getProvider(id) {
  const p = providers[id];
  if (!p) {
    throw new Error(`Unknown OTP provider "${id}". Known providers: ${Object.keys(providers).join(', ')}`);
  }
  return p;
}

/**
 * Refuses the `console` provider outside an emulator. Called on every
 * send, not just at startup, so that a config change at runtime cannot
 * quietly enable it in production.
 */
function assertProviderAllowed(id, env = process.env) {
  if (id !== 'console') return;
  const inEmulator = !!(env.FUNCTIONS_EMULATOR === 'true' || env.FIRESTORE_EMULATOR_HOST || env.FIREBASE_AUTH_EMULATOR_HOST);
  if (!inEmulator) {
    throw new Error('The "console" OTP provider is emulator-only and must never be used in a deployed environment.');
  }
}

module.exports = { providers, getProvider, assertProviderAllowed };
