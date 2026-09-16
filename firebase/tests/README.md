# Firebase layer — tests

258 tests, none of which need a Firebase project, credentials, a phone
number, or money.

```bash
cd firebase/tests
npm install          # once
npm test             # 196 unit tests, no emulator needed
npm run test:rules   # 47 security-rules tests against the real emulator
npm run test:e2e     # 15 end-to-end tests against the real emulators
npm run test:all     # all three
```

`test:rules` and `test:e2e` start the emulators (Java 11+ required), run
against them, and shut them down. They are the suites that exercise real
Firebase behaviour rather than a stub — `test:e2e` additionally needs the
Cloud Functions dependencies installed (`cd ../functions && npm install`).

## What each file covers

| File | Tests | What it pins down |
|---|---|---|
| `otp-core.test.js` | 49 | Phone normalization, code generation, salted hashing, expiry, attempt caps, per-number rate limits. |
| `whatsapp.test.js` | 38 | Cloud API payload shapes, error classification, webhook signature verification, opt-out intent detection. |
| `broadcast-core.test.js` | 25 | Who receives a broadcast and — mostly — who must not. |
| `user-auth.test.js` | 54 | The browser half: transport routing, profile defaults, OTP flows, consent, inertness when disabled. |
| `workflows-core.test.js` | 30 | Which GitHub Actions the admin panel may start, what inputs it accepts, and who may press which. |
| `rules.spec.js` | 47 | Firestore security rules, against the emulator. |
| `e2e.spec.js` | 15 | The whole OTP flow through the real `index.js`: send → store hashed → verify → custom token → profile created, plus the webhook's signature and handshake checks. |

Most assertions are that something **fails**. A suite that only checked
happy paths would pass just as happily against `allow read, write: if
true`.

## Why the end-to-end suite exists

`index.js` is the one file here that unit tests cannot reach: it is the
Firebase-shaped shell (secrets, transactions, custom tokens) wrapped
around logic that is tested in isolation elsewhere. It was written,
reviewed, and committed without ever being executed.

The first time it ran, it failed immediately. `admin.firestore.FieldValue`
reads back as `undefined` through the functions emulator's proxy of the
`firebase-admin` root export, so every `serverTimestamp()` threw a bare
`INTERNAL` — in `verifyOtp`, in the opt-out webhook, and throughout the
broadcast sender. The code looked correct in review and passed every unit
test. Only running it found this; `index.js` now uses the modular
`firebase-admin/{app,firestore,auth}` entry points instead, which don't
go through that proxy.

It uses the `console` OTP provider (`functions/lib/providers.js`), which
prints the code instead of sending it and refuses to run outside an
emulator (`assertProviderAllowed`) — and, when `DGE_OTP_ECHO_FILE` is set
(the `test:e2e` script sets it), also appends `<phone> <code>` to that
file so the suite can read a code back deterministically instead of
scraping the emulator's log output. `functions/.env.dge-test` (committed
— it holds no secret) sets both `OTP_PROVIDER=console` and
`DGE_OTP_ECHO_FILE` for the `dge-test` project this suite runs against.
`defineSecret()` params (`WHATSAPP_VERIFY_TOKEN`, `OTP_PEPPER`, etc.)
still need real or placeholder values from a local, git-ignored
`functions/.secret.local` (one `KEY=value` per line, same shape as
`.env.dge-test`) — the Firebase CLI refuses to resolve them from Secret
Manager without `firebase login`, which running this suite should never
require. See `../../FIREBASE_SETUP.md` for real (non-placeholder) values.

## Naming

`rules.spec.js` uses `.spec.js` deliberately: node's default test glob
matches `*.test.js` but not `*.spec.js`, so a plain `npm test` skips the
file that needs an emulator instead of failing on it. Run it via
`npm run test:rules`.

## What these tests cannot tell you

They verify our logic and our security rules. They cannot verify that
Google, Meta, or MSG91 accept our requests — the SDK is stubbed in
`helpers/fake-env.js`, and the Graph API calls go to a fake `fetch`.
Delivery, template approval, reCAPTCHA behaviour, and real billing are
only observable against live accounts. See `../../FIREBASE_SETUP.md` §10
for what to check the first time this runs for real.
