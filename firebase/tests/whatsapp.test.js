// Tests for the WhatsApp Cloud API layer — payload shapes, error
// classification, webhook parsing, opt-out detection, and the send path
// against a fake fetch.
//
// The payload tests matter more than they look: Meta rejects a malformed
// authentication template at delivery time with an opaque error code, so
// a shape mistake would otherwise only surface as "OTPs mysteriously
// never arrive" against a live, paid account.
'use strict';

const { test, describe } = require('node:test');
const assert = require('node:assert/strict');

const wa = require('../functions/lib/whatsapp');

describe('toWaRecipient', () => {
  test('drops the leading + Meta does not want', () => {
    assert.equal(wa.toWaRecipient('+919876543210'), '919876543210');
  });

  test('leaves an already-bare number alone', () => {
    assert.equal(wa.toWaRecipient('919876543210'), '919876543210');
  });
});

describe('buildAuthTemplatePayload', () => {
  const base = { to: '+919876543210', code: '123456', templateName: 'dge_otp' };

  test('puts the code in the body parameter', () => {
    const p = wa.buildAuthTemplatePayload(base);
    assert.equal(p.messaging_product, 'whatsapp');
    assert.equal(p.type, 'template');
    assert.equal(p.to, '919876543210');
    assert.equal(p.template.name, 'dge_otp');
    const body = p.template.components.find(c => c.type === 'body');
    assert.deepEqual(body.parameters, [{ type: 'text', text: '123456' }]);
  });

  test('repeats the code in the copy-code button', () => {
    // Meta requires the button parameter on templates that declare a
    // copy-code button; omitting it fails the send.
    const p = wa.buildAuthTemplatePayload(base);
    const button = p.template.components.find(c => c.type === 'button');
    assert.ok(button, 'expected a button component by default');
    assert.equal(button.sub_type, 'url');
    assert.equal(button.index, '0');
    assert.deepEqual(button.parameters, [{ type: 'text', text: '123456' }]);
  });

  test('omits the button component when the template has no button', () => {
    const p = wa.buildAuthTemplatePayload(Object.assign({}, base, { hasCopyCodeButton: false }));
    assert.equal(p.template.components.filter(c => c.type === 'button').length, 0);
    assert.equal(p.template.components.length, 1);
  });

  test('defaults the language to en and honours an override', () => {
    assert.equal(wa.buildAuthTemplatePayload(base).template.language.code, 'en');
    assert.equal(
      wa.buildAuthTemplatePayload(Object.assign({}, base, { languageCode: 'hi' })).template.language.code,
      'hi'
    );
  });

  test('coerces a numeric code to a string', () => {
    // A code that arrives as a number would serialize as `"text": 123456`
    // and be rejected by Meta's schema.
    const p = wa.buildAuthTemplatePayload(Object.assign({}, base, { code: 123456 }));
    assert.strictEqual(p.template.components[0].parameters[0].text, '123456');
  });

  test('refuses to build an incomplete payload', () => {
    assert.throws(() => wa.buildAuthTemplatePayload({ code: '1', templateName: 't' }), /`to` is required/);
    assert.throws(() => wa.buildAuthTemplatePayload({ to: '+91', templateName: 't' }), /`code` is required/);
    assert.throws(() => wa.buildAuthTemplatePayload({ to: '+91', code: '1' }), /`templateName` is required/);
  });
});

describe('buildBroadcastTemplatePayload', () => {
  test('fills body parameters in order', () => {
    const p = wa.buildBroadcastTemplatePayload({
      to: '+919876543210',
      templateName: 'daily_shloka',
      bodyParams: ['Bhagavad Gita', '2.47']
    });
    assert.deepEqual(p.template.components[0].parameters, [
      { type: 'text', text: 'Bhagavad Gita' },
      { type: 'text', text: '2.47' }
    ]);
  });

  test('omits components entirely for a template with no variables', () => {
    // An empty components array is rejected on some template types, so
    // the key must be absent rather than empty.
    const p = wa.buildBroadcastTemplatePayload({ to: '+919876543210', templateName: 'plain' });
    assert.equal('components' in p.template, false);
  });

  test('refuses to build an incomplete payload', () => {
    assert.throws(() => wa.buildBroadcastTemplatePayload({ templateName: 't' }), /`to` is required/);
    assert.throws(() => wa.buildBroadcastTemplatePayload({ to: '+91' }), /`templateName` is required/);
  });
});

describe('classifyGraphError', () => {
  const err = (code) => ({ error: { code, message: 'x' } });

  test('marks rate limits retryable', () => {
    for (const code of [4, 80007, 130429, 131056]) {
      const c = wa.classifyGraphError(400, err(code));
      assert.equal(c.retryable, true, `code ${code} should be retryable`);
      assert.equal(c.kind, 'rate_limited');
    }
  });

  test('marks undeliverable numbers permanent', () => {
    // Retrying these wastes quota and, on template sends, money.
    const c = wa.classifyGraphError(400, err(131026));
    assert.equal(c.retryable, false);
    assert.equal(c.kind, 'permanent');
  });

  test('marks template problems permanent', () => {
    for (const code of [132000, 132001, 132005, 132007, 132012, 132015]) {
      assert.equal(wa.classifyGraphError(400, err(code)).retryable, false, `code ${code}`);
    }
  });

  test('marks 5xx retryable and auth failures permanent', () => {
    assert.equal(wa.classifyGraphError(500, {}).retryable, true);
    assert.equal(wa.classifyGraphError(503, {}).retryable, true);
    assert.equal(wa.classifyGraphError(401, {}).retryable, false);
    assert.equal(wa.classifyGraphError(403, {}).retryable, false);
  });

  test('survives a body with no error object', () => {
    const c = wa.classifyGraphError(400, {});
    assert.equal(c.kind, 'unknown');
    assert.equal(c.message, 'HTTP 400');
  });
});

describe('sendMessage', () => {
  const args = { phoneNumberId: 'PNID', accessToken: 'TOKEN', payload: { to: '91987' } };

  function fakeFetch(status, body) {
    return async () => ({ ok: status >= 200 && status < 300, status, json: async () => body });
  }

  test('returns the message id on success', async () => {
    const r = await wa.sendMessage(Object.assign({}, args, {
      fetchImpl: fakeFetch(200, { messages: [{ id: 'wamid.ABC' }], contacts: [{ wa_id: '919876543210' }] })
    }));
    assert.equal(r.ok, true);
    assert.equal(r.messageId, 'wamid.ABC');
    assert.equal(r.waId, '919876543210');
  });

  test('sends a bearer token and JSON body to the right URL', async () => {
    let captured;
    await wa.sendMessage(Object.assign({}, args, {
      fetchImpl: async (url, opts) => {
        captured = { url, opts };
        return { ok: true, status: 200, json: async () => ({}) };
      }
    }));
    assert.match(captured.url, /^https:\/\/graph\.facebook\.com\/v\d+\.\d+\/PNID\/messages$/);
    assert.equal(captured.opts.method, 'POST');
    assert.equal(captured.opts.headers.Authorization, 'Bearer TOKEN');
    assert.equal(captured.opts.headers['Content-Type'], 'application/json');
    assert.deepEqual(JSON.parse(captured.opts.body), { to: '91987' });
  });

  test('classifies an API error rather than throwing', async () => {
    const r = await wa.sendMessage(Object.assign({}, args, {
      fetchImpl: fakeFetch(400, { error: { code: 131026, message: 'not a WhatsApp user' } })
    }));
    assert.equal(r.ok, false);
    assert.equal(r.kind, 'permanent');
    assert.equal(r.retryable, false);
    assert.equal(r.status, 400);
  });

  test('treats a network failure as retryable instead of crashing', async () => {
    const r = await wa.sendMessage(Object.assign({}, args, {
      fetchImpl: async () => { throw new Error('ECONNRESET'); }
    }));
    assert.equal(r.ok, false);
    assert.equal(r.retryable, true);
    assert.equal(r.kind, 'network');
  });

  test('survives a success response whose body is not JSON', async () => {
    const r = await wa.sendMessage(Object.assign({}, args, {
      fetchImpl: async () => ({ ok: true, status: 200, json: async () => { throw new Error('not json'); } })
    }));
    assert.equal(r.ok, true);
    assert.equal(r.messageId, null);
  });

  test('refuses to send without credentials', async () => {
    await assert.rejects(() => wa.sendMessage({ payload: {}, accessToken: 'T' }), /phoneNumberId is required/);
    await assert.rejects(() => wa.sendMessage({ payload: {}, phoneNumberId: 'P' }), /accessToken is required/);
  });
});

describe('verifySignature', () => {
  const crypto = require('node:crypto');
  const SECRET = 'app-secret';
  const rawBody = Buffer.from(JSON.stringify({ entry: [{ id: 'x' }] }), 'utf8');
  const goodSig = 'sha256=' + crypto.createHmac('sha256', SECRET).update(rawBody).digest('hex');

  test('accepts a correctly signed payload', () => {
    assert.equal(wa.verifySignature(rawBody, goodSig, SECRET), true);
  });

  test('rejects a payload signed with the wrong secret', () => {
    // The forgery case: without this check, anyone who learns the
    // webhook URL could opt any phone number in or out at will.
    const forged = 'sha256=' + crypto.createHmac('sha256', 'wrong-secret').update(rawBody).digest('hex');
    assert.equal(wa.verifySignature(rawBody, forged, SECRET), false);
  });

  test('rejects a payload whose body was altered after signing', () => {
    const tampered = Buffer.from(JSON.stringify({ entry: [{ id: 'evil' }] }), 'utf8');
    assert.equal(wa.verifySignature(tampered, goodSig, SECRET), false);
  });

  test('rejects a missing, malformed or wrongly-prefixed signature', () => {
    assert.equal(wa.verifySignature(rawBody, '', SECRET), false);
    assert.equal(wa.verifySignature(rawBody, 'deadbeef', SECRET), false);
    assert.equal(wa.verifySignature(rawBody, 'sha1=deadbeef', SECRET), false);
    assert.equal(wa.verifySignature(rawBody, null, SECRET), false);
    assert.equal(wa.verifySignature(rawBody, undefined, SECRET), false);
  });

  test('rejects everything when no body or secret is available', () => {
    // Fails closed: a function deployed without the secret configured
    // must reject webhooks, not accept them all.
    assert.equal(wa.verifySignature(null, goodSig, SECRET), false);
    assert.equal(wa.verifySignature(rawBody, goodSig, ''), false);
    assert.equal(wa.verifySignature(rawBody, goodSig, undefined), false);
  });

  test('rejects a truncated signature of the right prefix', () => {
    assert.equal(wa.verifySignature(rawBody, goodSig.slice(0, 20), SECRET), false);
  });
});

describe('parseInboundMessages', () => {
  test('pulls text messages out of a real-shaped webhook envelope', () => {
    const body = {
      object: 'whatsapp_business_account',
      entry: [{
        id: 'WABA_ID',
        changes: [{
          field: 'messages',
          value: {
            messaging_product: 'whatsapp',
            messages: [{ from: '919876543210', id: 'wamid.1', timestamp: '1700000000', type: 'text', text: { body: 'STOP' } }]
          }
        }]
      }]
    };
    const msgs = wa.parseInboundMessages(body);
    assert.equal(msgs.length, 1);
    assert.equal(msgs[0].from, '+919876543210');
    assert.equal(msgs[0].text, 'STOP');
    assert.equal(msgs[0].timestamp, 1700000000000);
  });

  test('reads a quick-reply button press as its text', () => {
    const body = { entry: [{ changes: [{ value: { messages: [{ from: '919876543210', type: 'button', button: { text: 'Stop promotions' } }] } }] }] };
    assert.equal(wa.parseInboundMessages(body)[0].text, 'Stop promotions');
  });

  test('returns nothing for status-only callbacks and malformed bodies', () => {
    // Delivery-status callbacks arrive on the same webhook and must not
    // be mistaken for user messages.
    assert.deepEqual(wa.parseInboundMessages({ entry: [{ changes: [{ value: { statuses: [{ id: 'x', status: 'delivered' }] } }] }] }), []);
    assert.deepEqual(wa.parseInboundMessages({}), []);
    assert.deepEqual(wa.parseInboundMessages(null), []);
    assert.deepEqual(wa.parseInboundMessages({ entry: [] }), []);
  });

  test('flattens several messages across several entries', () => {
    const body = {
      entry: [
        { changes: [{ value: { messages: [{ from: '911', type: 'text', text: { body: 'a' } }] } }] },
        { changes: [{ value: { messages: [{ from: '912', type: 'text', text: { body: 'b' } }] } }] }
      ]
    };
    assert.equal(wa.parseInboundMessages(body).length, 2);
  });
});

describe('detectOptOutIntent', () => {
  test('recognises the standard opt-out words', () => {
    for (const word of ['STOP', 'stop', 'Stop', 'unsubscribe', 'CANCEL', 'quit', 'opt out']) {
      assert.equal(wa.detectOptOutIntent(word), 'opt_out', `"${word}" should opt out`);
    }
  });

  test('recognises opt-out in the Indian languages this site serves', () => {
    for (const word of ['बंद', 'ನಿಲ್ಲಿಸಿ', 'நிறுத்து', 'ఆపు']) {
      assert.equal(wa.detectOptOutIntent(word), 'opt_out', `"${word}" should opt out`);
    }
  });

  test('tolerates surrounding punctuation and whitespace', () => {
    assert.equal(wa.detectOptOutIntent('  STOP.  '), 'opt_out');
    assert.equal(wa.detectOptOutIntent('"stop"'), 'opt_out');
    assert.equal(wa.detectOptOutIntent('STOP!'), 'opt_out');
  });

  test('does NOT opt out on a sentence that merely contains the word', () => {
    // The expensive false positive: someone writing a real message gets
    // silently unsubscribed and never hears from the site again.
    assert.equal(wa.detectOptOutIntent('please do not stop sending these'), null);
    assert.equal(wa.detectOptOutIntent('I could not stop reading, thank you'), null);
    assert.equal(wa.detectOptOutIntent('where is the bus stop'), null);
  });

  test('recognises opt-in words', () => {
    for (const word of ['START', 'subscribe', 'resume', 'yes']) {
      assert.equal(wa.detectOptOutIntent(word), 'opt_in', `"${word}" should opt in`);
    }
  });

  test('returns null for anything else', () => {
    assert.equal(wa.detectOptOutIntent('hari om'), null);
    assert.equal(wa.detectOptOutIntent(''), null);
    assert.equal(wa.detectOptOutIntent('   '), null);
    assert.equal(wa.detectOptOutIntent(null), null);
    assert.equal(wa.detectOptOutIntent(undefined), null);
    assert.equal(wa.detectOptOutIntent(42), null);
  });
});
