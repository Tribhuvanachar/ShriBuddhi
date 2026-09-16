// email-providers.js -- pluggable transactional email, same shape as
// lib/providers.js (OTP) and lib/payment-providers.js (gateways). No
// real provider is wired in yet -- that's a later decision (Resend,
// SendGrid, Postmark, ...), made once the project lead picks one. Only
// `console` exists today: it logs the receipt instead of emailing it,
// which is enough to build and test the whole receipt pipeline right
// now without an email account or spending anything.
'use strict';

const logger = require('firebase-functions/logger');

const providers = {
  /**
   * Dev-only: logs the message. Not restricted to the emulator the way
   * the `mock` payment gateway and `console` OTP provider are --
   * because unlike those two, sending no email has no financial or
   * security consequence, only a missed notification, and this module
   * has no real provider yet for it to be mistaken for.
   */
  console: {
    id: 'console',
    async send({ to, subject, textBody }) {
      logger.info('[email:console] would send', { to, subject, preview: textBody.slice(0, 200) });
      return { ok: true, messageId: 'console-' + Date.now() };
    }
  }

  // A real provider goes here once chosen, e.g.:
  //   resend: { id: 'resend', async send({ to, subject, textBody, config }) { ... } }
};

function getEmailProvider(id) {
  const p = providers[id];
  if (!p) throw new Error(`Unknown email provider "${id}". Known providers: ${Object.keys(providers).join(', ')}`);
  return p;
}

module.exports = { providers, getEmailProvider };
