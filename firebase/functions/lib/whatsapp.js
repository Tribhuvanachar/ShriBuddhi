// whatsapp.js — Meta WhatsApp Cloud API client.
//
// Split into payload BUILDERS (pure, fully tested) and a thin SEND
// function (the only part that touches the network). The builders are
// where the format mistakes live — Meta's authentication templates have
// a fiddly component structure where the code must appear both in the
// body and again in the copy-code button, and getting that wrong fails
// at delivery time with an opaque error. So that shape is pinned by
// tests rather than by hope.
'use strict';

const crypto = require('crypto');

const GRAPH_VERSION = 'v21.0';

/**
 * Verifies that a webhook payload really came from Meta.
 *
 * Without this, anyone who learns the webhook URL can forge opt-outs —
 * or, worse, opt-INs — for any phone number they choose. Meta signs the
 * RAW request bytes, so the caller must pass `req.rawBody`: re-
 * serializing the parsed JSON produces different bytes and the signature
 * will never match.
 */
function verifySignature(rawBody, signatureHeader, appSecret) {
  if (!rawBody || !appSecret) return false;
  if (typeof signatureHeader !== 'string' || !signatureHeader.startsWith('sha256=')) return false;

  const expected = 'sha256=' + crypto.createHmac('sha256', appSecret).update(rawBody).digest('hex');
  const a = Buffer.from(signatureHeader, 'utf8');
  const b = Buffer.from(expected, 'utf8');
  if (a.length !== b.length) return false;
  return crypto.timingSafeEqual(a, b);
}

/**
 * Meta wants the recipient without the leading '+' (it tolerates it, but
 * the docs and every error message use the bare form).
 */
function toWaRecipient(e164Phone) {
  return String(e164Phone).replace(/^\+/, '');
}

/**
 * Builds the payload for an AUTHENTICATION template carrying an OTP.
 *
 * Meta requires authentication templates to be pre-approved in the
 * WhatsApp Manager, and requires the code to be passed as a body
 * parameter. When the template was created with a "copy code" or
 * "one-tap autofill" button — which is the whole reason to use WhatsApp
 * for OTP rather than SMS — the SAME code must also be passed as the
 * button's parameter. Omitting the button component on a template that
 * declares one is rejected at send time.
 *
 * @param {object} o
 * @param {string} o.to             recipient in E.164
 * @param {string} o.code           the plaintext OTP
 * @param {string} o.templateName   approved template name
 * @param {string} [o.languageCode] BCP-47-ish code Meta expects, e.g. 'en'
 * @param {boolean} [o.hasCopyCodeButton]
 */
function buildAuthTemplatePayload({ to, code, templateName, languageCode = 'en', hasCopyCodeButton = true }) {
  if (!to) throw new Error('buildAuthTemplatePayload: `to` is required');
  if (!code) throw new Error('buildAuthTemplatePayload: `code` is required');
  if (!templateName) throw new Error('buildAuthTemplatePayload: `templateName` is required');

  const components = [
    { type: 'body', parameters: [{ type: 'text', text: String(code) }] }
  ];

  if (hasCopyCodeButton) {
    components.push({
      type: 'button',
      sub_type: 'url',
      index: '0',
      parameters: [{ type: 'text', text: String(code) }]
    });
  }

  return {
    messaging_product: 'whatsapp',
    recipient_type: 'individual',
    to: toWaRecipient(to),
    type: 'template',
    template: {
      name: templateName,
      language: { code: languageCode },
      components
    }
  };
}

/**
 * Builds a payload for a general (utility/marketing) template — the
 * broadcast path. `bodyParams` fills the template's {{1}}, {{2}}, … in
 * order.
 */
function buildBroadcastTemplatePayload({ to, templateName, languageCode = 'en', bodyParams = [] }) {
  if (!to) throw new Error('buildBroadcastTemplatePayload: `to` is required');
  if (!templateName) throw new Error('buildBroadcastTemplatePayload: `templateName` is required');

  const template = {
    name: templateName,
    language: { code: languageCode }
  };

  // A template with no variables must NOT carry an empty components
  // array — Meta rejects `components: []` on some template types, so the
  // key is omitted entirely rather than sent empty.
  if (bodyParams.length) {
    template.components = [{
      type: 'body',
      parameters: bodyParams.map(p => ({ type: 'text', text: String(p) }))
    }];
  }

  return {
    messaging_product: 'whatsapp',
    recipient_type: 'individual',
    to: toWaRecipient(to),
    type: 'template',
    template
  };
}

/**
 * Classifies a Meta Graph API error into something the caller can act
 * on. The distinction that matters operationally: a transient failure is
 * worth retrying, a permanent one (bad number, template not approved,
 * user blocked us) is not, and retrying it just wastes quota and — for
 * template sends — potentially money.
 */
function classifyGraphError(status, body) {
  const code = body?.error?.code;
  const subcode = body?.error?.error_subcode;
  const message = body?.error?.message || `HTTP ${status}`;

  // 131026 = message undeliverable (not a WhatsApp user / can't receive)
  // 131047 = re-engagement required (outside 24h window, needs template)
  // 132xxx = template problems (not found, not approved, param mismatch)
  // 100    = invalid parameter
  const permanent = new Set([100, 131026, 131047, 131051, 132000, 132001, 132005, 132007, 132012, 132015, 132016, 133010]);

  // 4 = app-level rate limit, 80007 = business-level rate limit,
  // 130429 = messaging throughput limit — all worth backing off on.
  const rateLimited = new Set([4, 80007, 130429, 131056]);

  if (rateLimited.has(code)) return { retryable: true, kind: 'rate_limited', code, subcode, message };
  if (permanent.has(code)) return { retryable: false, kind: 'permanent', code, subcode, message };
  if (status >= 500) return { retryable: true, kind: 'server_error', code, subcode, message };
  if (status === 401 || status === 403) return { retryable: false, kind: 'auth', code, subcode, message };
  return { retryable: status >= 500, kind: 'unknown', code, subcode, message };
}

/**
 * Sends one payload to the Cloud API.
 *
 * The access token is passed in rather than read from the environment
 * here, so this module has no ambient dependency on secrets and stays
 * callable from a test with a fake `fetchImpl`.
 */
async function sendMessage({ payload, phoneNumberId, accessToken, fetchImpl = globalThis.fetch, graphVersion = GRAPH_VERSION, timeoutMs = 10000 }) {
  if (!phoneNumberId) throw new Error('sendMessage: phoneNumberId is required');
  if (!accessToken) throw new Error('sendMessage: accessToken is required');

  const url = `https://graph.facebook.com/${graphVersion}/${phoneNumberId}/messages`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  let res;
  let body;
  try {
    res = await fetchImpl(url, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload),
      signal: controller.signal
    });
    body = await res.json().catch(() => ({}));
  } catch (e) {
    // A network abort/timeout is transient by definition.
    return { ok: false, retryable: true, kind: 'network', message: e?.message || String(e) };
  } finally {
    clearTimeout(timer);
  }

  if (!res.ok) {
    const classified = classifyGraphError(res.status, body);
    return { ok: false, ...classified, status: res.status };
  }

  return {
    ok: true,
    messageId: body?.messages?.[0]?.id || null,
    waId: body?.contacts?.[0]?.wa_id || null
  };
}

/**
 * Pulls inbound user messages out of a Cloud API webhook envelope.
 *
 * Used for opt-out handling: WhatsApp requires honouring a user's "STOP"
 * and Meta penalises senders whose recipients block them, so this is a
 * compliance requirement rather than a nicety.
 */
function parseInboundMessages(webhookBody) {
  const out = [];
  const entries = webhookBody?.entry || [];
  for (const entry of entries) {
    for (const change of (entry.changes || [])) {
      const value = change.value || {};
      for (const msg of (value.messages || [])) {
        out.push({
          from: msg.from ? '+' + String(msg.from).replace(/^\+/, '') : null,
          type: msg.type,
          text: msg.text?.body || msg.button?.text || '',
          timestamp: msg.timestamp ? Number(msg.timestamp) * 1000 : null,
          messageId: msg.id || null
        });
      }
    }
  }
  return out;
}

// Words that mean "stop messaging me", in the languages this site's
// users actually write in. Matched as a whole-message intent: someone
// writing a sentence that happens to contain "stop" is not opting out,
// but a message that is just that word (with optional punctuation) is.
const OPT_OUT_WORDS = [
  'stop', 'unsubscribe', 'cancel', 'quit', 'end', 'optout', 'opt-out', 'opt out',
  'बंद', 'रोको', 'बंद करो',        // Hindi
  'ನಿಲ್ಲಿಸಿ', 'ಬೇಡ',                  // Kannada
  'நிறுத்து',                        // Tamil
  'ఆపు'                             // Telugu
];

const OPT_IN_WORDS = ['start', 'subscribe', 'resume', 'optin', 'opt-in', 'opt in', 'yes'];

function detectOptOutIntent(text) {
  if (typeof text !== 'string') return null;
  // Strip surrounding punctuation/whitespace but keep the word itself.
  const normalized = text.trim().toLowerCase().replace(/^[\s\p{P}]+|[\s\p{P}]+$/gu, '');
  if (!normalized) return null;
  if (OPT_OUT_WORDS.includes(normalized)) return 'opt_out';
  if (OPT_IN_WORDS.includes(normalized)) return 'opt_in';
  return null;
}

module.exports = {
  GRAPH_VERSION,
  verifySignature,
  toWaRecipient,
  buildAuthTemplatePayload,
  buildBroadcastTemplatePayload,
  classifyGraphError,
  sendMessage,
  parseInboundMessages,
  detectOptOutIntent,
  OPT_OUT_WORDS,
  OPT_IN_WORDS
};
