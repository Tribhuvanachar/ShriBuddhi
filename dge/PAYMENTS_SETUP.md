# DGE Donations, Payments & Supporters — Foundation

_Written 8 Sep 2026, updated 9 Sep 2026 (both gateways wired in). Neither
gateway has real credentials anywhere in this repo, no rupee has moved,
and nothing here is deployed. See §0 for exactly what that means._

## 0. Where this stands

The lead asked for the donation/payment/supporter system to be built on
**this project's existing Firebase stack** (Cloud Functions + Firestore +
Firebase Auth) rather than the Cloudflare Workers + Supabase architecture
that was independently proposed — see §1 for why that's the better fit
here. The gateway choice was then resolved: rather than pick one, the
lead asked for **both Cashfree and Razorpay wired in behind a switch** —
"make it work for both... should be just a switch to either as required
based on situations." §4 covers exactly what that switch is.

| Piece | State |
|---|---|
| Firestore schema (§3) | ✅ built — 8 collections, integer money, security rules |
| `lib/donation-core.js` (validation, sanitization, reference generation) | ✅ built, 33 unit tests |
| `lib/payment-state.js` (the status state machine) | ✅ built, 12 unit tests |
| `lib/payment-providers.js` (gateway adapter registry: `mock`, `cashfree`, `razorpay`) | ✅ built, 41 unit tests — see §4 for what "built" does and doesn't mean here |
| `lib/receipt-core.js` (receipt numbering + email content) | ✅ built, 9 unit tests |
| `lib/email-providers.js` | ✅ built — `console` only (logs instead of sending); a real provider is a later decision, same shape as the gateway |
| `createDonation` / `paymentWebhook` / `getDonationStatus` Cloud Functions | ✅ built, exercised end to end against the `mock` gateway (§6) |
| Firestore rules for the 8 new collections | ✅ built, 21 rules-emulator tests |
| **Cashfree and Razorpay credentials** | ❌ neither exists in this deployment — both adapters are code-complete and unit-tested against synthetic fixtures matching each gateway's documented shapes, but NEITHER has been exercised against a real sandbox account. See §4's honesty note. |
| Donation frontend page (`dge/donate.html`) | ✅ built 10 Sep 2026 — calls `createDonation`/`getDonationStatus` directly, branches on `checkout.gateway` (razorpay/cashfree/mock), never trusts a gateway's own return redirect for success (see §10) |
| Real transactional email | ❌ not started — `console` provider only |
| Rate limiting on `createDonation`/`paymentWebhook` | ❌ not started — flagged as a gap, see §8 |
| Supporter magic-link auth, entitlements actually granted | ❌ not started — Phase 3/4, deliberately deferred |
| Admin donations dashboard | ❌ not started — deliberately deferred (§21 of the spec this implements says the same) |
| Compliance sign-off (12A/80G/FCRA/gateway merchant approval) | ❌ the lead's own action item, not something this session can do — see §9 |

## 1. Architecture decision: Firebase-native, not Cloudflare Workers + Supabase

A detailed Cloudflare Workers + Supabase architecture was proposed
alongside this task. It's a reasonable design in isolation, but not the
right one **for this repository specifically**, and the lead confirmed
Firebase-native when asked directly:

- **This project already has a working Firebase deploy pipeline** —
  Firestore rules, Hosting, and Cloud Functions all deploy through
  GitHub Actions as of this same session (`FIREBASE_SETUP.md` §0). A
  second serverless runtime (Cloudflare Workers) means a second set of
  secrets, a second deploy pipeline, and a second thing that can be
  half-configured.
- **One identity system, not two.** Firebase Auth (Google sign-in, phone
  OTP) already exists with a working role system
  (`dge/firebase/firestore.rules`' `callerRole()`). Supabase Auth would
  be a second, parallel notion of "who is this person" that has to be
  reconciled with the first the moment a donor is also a signed-in
  reader — which is exactly what Phase 3 (magic-link supporter accounts)
  needs to do.
- **Firestore already holds this app's `users`, `broadcasts`, and
  `workflow_dispatches` collections**, with the exact security-rules
  pattern (public read where appropriate, Admin-SDK-only writes,
  role-gated admin reads) this feature reuses verbatim in §3 below.
- The one thing Postgres genuinely offers that Firestore doesn't — real
  SQL for settlement reconciliation (§7 of the pasted proposal) — is not
  needed for Phase 1. Firestore's collections here already model the
  join structure a reconciliation report needs (`payments.donationId`,
  `donations.donorId`); a CSV export or a small script that reads
  Firestore is enough until real settlement volume says otherwise. If it
  ever doesn't, adding Postgres for the money tables ONLY (not for auth,
  not as the API layer) is a smaller, later, well-justified step — not a
  Phase 1 decision.

**Net result**: `GitHub Pages (frontend, once built) → Firebase Cloud
Functions (API) → Firestore`. One deploy pipeline, one identity system,
one set of secrets. This is the same shape `sendOtp`/`verifyOtp` and the
admin workflow-dispatch functions already use — donations are one more
feature in the same house style, not a parallel system next to it.

## 2. Money is stored as integer minor units, never a float

Every amount in this feature (`amountMinor` on `donations`/`payments`,
never `amount`) is an **integer number of paise**, not a decimal rupee
value. Firestore has no fixed-point decimal type — only IEEE-754
doubles — so a `numeric(18,2)` column (which the SQL version of this
schema used, and which is fine in Postgres) would be a silent rounding
bug waiting to happen in Firestore. `lib/donation-core.js`'s
`majorToMinor()` is the one place a client-typed amount like `"1001.50"`
becomes `100150` — it rejects (does not round) anything with more than 2
decimal places, `NaN`, `Infinity`, or a non-positive value.

## 3. Firestore schema

All eight collections and their security rules live in
`dge/firebase/firestore.rules`; the write side lives entirely in
`dge/firebase/functions/index.js` using the Admin SDK, which bypasses
rules — **no client, not even a superadmin, may write any of these
collections directly.** That's not an oversight to fix later; it's the
whole point. `createDonation` and `paymentWebhook` are the only code
that may ever set a donation's amount or move it to `SUCCESS`.

| Collection | Doc ID | Client read | Notes |
|---|---|---|---|
| `donors` | auto | superadmin only | name, email, phone, PAN — the most sensitive PII here |
| `donations` | auto | admin | `amountMinor`, `status`, `contributionType`, `donorId` reference (no raw PII) |
| `payments` | auto | admin | gateway order/payment IDs, no PII |
| `payment_events` | `{gateway}_{gatewayEventId}` | **nobody** | sealed like `otp_challenges` — the doc ID itself IS the webhook-idempotency uniqueness constraint |
| `receipts` | `{donationId}` | admin | receipt number, email-sent status |
| `receipt_counters` | `{year}` | **nobody** | an atomic sequence Firestore transaction increments; a client that could write this could mint its own receipt numbers |
| `supporter_entitlements` | `{donorId}_{entitlementCode}` | admin (for now) | Phase 4 — nothing grants one yet; will become `isOwner(donorId) \|\| isAdmin()` once Phase 3 links a donor to a signed-in uid |
| `public_supporters` | `{donationId}` | **everyone** | the Supporters Wall — only `displayName`/`amountMinor` (nullable)/`currency`/`paidAt`/`donationReference`; never email, phone, PAN, or the raw `donorId` |

Two Firestore-native simplifications versus the originally-pasted SQL
schema, both deliberate:
- `payment_events`' doc ID *is* `gateway + gatewayEventId` — Postgres
  needed a separate `unique(gateway, gateway_event_id)` constraint;
  Firestore doc IDs are unique by construction, so the ID does that job.
- `receipts` and `supporter_entitlements` use composite/foreign doc IDs
  (`{donationId}`, `{donorId}_{entitlementCode}`) for the same reason —
  no separate unique index needed.

## 4. Two gateways, one switch — Cashfree and Razorpay

`dge/firebase/functions/lib/payment-providers.js` is a small registry —
the exact shape `lib/providers.js` already uses for OTP delivery
channels (WhatsApp/MSG91/console). It holds three entries: `mock`
(refused outside a Firebase emulator, same as `providers.js`'s `console`
OTP channel), and now **`cashfree`** and **`razorpay`**, each a
self-contained `{ id, createOrder, verifyWebhookSignature,
parseWebhookEvent }` built against that gateway's own current
documentation (sources below).

**The switch, concretely — a config value or a request field, never a
code change:**
- `PAYMENT_GATEWAY` (Cloud Functions param, default `mock`) is this
  deployment's default gateway.
- `PAYMENT_GATEWAYS_ENABLED` (default `mock`) is the allow-list; a
  gateway not on it can never be selected, by config or by request. Set
  it to e.g. `cashfree,razorpay` once both have real credentials.
- `createDonation` accepts an optional `gateway` field in its request;
  if it names something in `PAYMENT_GATEWAYS_ENABLED`, that donation
  uses it — otherwise it silently falls back to `PAYMENT_GATEWAY`'s
  default rather than trusting the client's say-so outright. This is
  the whole mechanism for "situation A uses Cashfree, situation B uses
  Razorpay" — a donation UI can pass whichever it wants; a campaign
  default is a config change; neither touches `index.js` or
  `payment-providers.js`.
- `paymentWebhook`'s URL already carries `?gateway=cashfree` /
  `?gateway=razorpay` as a query param (register each gateway's webhook
  in ITS OWN dashboard pointing at the same function URL with its own
  `?gateway=` value) — one endpoint already serves every gateway this
  deployment accepts; adding a gateway never means adding an endpoint.

**Money conversion differs between the two, and the adapters handle it
so nothing else in this codebase has to know:** Cashfree's Create Order
API wants the amount in major units (rupees, e.g. `501.50`) —
`donation-core.js`'s `minorToMajor()` does that conversion inside the
`cashfree` adapter only. Razorpay's Orders API already wants the
smallest currency unit (paise) — the SAME `amountMinor` this whole
feature stores everywhere else, passed straight through, no conversion.

**Refund classification (full vs. partial) is decided in `index.js`, not
in either adapter.** Both adapters normalize a successful refund webhook
to `{ status: 'REFUNDED', refundAmountMinor }` — `processPaymentEvent`
then compares `refundAmountMinor` against the donation's own
`amountMinor` to decide whether the real transition is to `REFUNDED` or
`PARTIALLY_REFUNDED`. Neither gateway's adapter needs the donation's
history to answer a question only `index.js` has the context for.

**Honesty about what "wired in" does NOT mean.** Neither gateway has a
sandbox account or any credential in this deployment — `CASHFREE_CLIENT_ID`,
`CASHFREE_CLIENT_SECRET`, `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, and
`RAZORPAY_WEBHOOK_SECRET` are all unset. Both adapters are built against
each gateway's OWN current documentation (pulled 9 Sep 2026 — see the
source URLs in the code comments in `payment-providers.js`) and covered
by 41 unit tests using synthetic fixtures shaped exactly like each
gateway's documented request/response/webhook payloads — but a unit test
against a synthetic fixture is not the same as a real API call, and
**neither adapter has been exercised against a real sandbox account.**
Specific gaps this session could not verify from primary docs, flagged
rather than guessed at in the code itself:
- **Cashfree's `x-webhook-timestamp` unit** (seconds vs. milliseconds) —
  `verifyWebhookSignature` assumes Unix seconds with a generous 10-minute
  window; confirm against a real received webhook before relying on that
  window being tight. The primary replay defense either way is
  `payment_events`' idempotency keying, not this timestamp check.
- **Cashfree's `x-api-version`** — defaults to `2023-08-01`
  (`CASHFREE_API_VERSION` param); confirm which version your merchant
  account/API keys were actually provisioned against before a real call.
- **Razorpay's exact behavior on a duplicate `receipt`** — the Orders API
  rejects a second order with a `receipt` value that already exists (our
  `donationReference` is used as the receipt), but this session could not
  verify whether that means "returns the existing order" or "returns an
  error" — `createDonation`'s current error handling treats any failure
  the same way (marks the donation `FAILED`), which is safe but may be
  unnecessarily conservative if it turns out to return the existing order.
- **Razorpay's `order.paid` event and full webhook envelope** (`account_id`,
  `contains`, etc.) — could not pull a verified sample payload; `order.paid`
  is currently treated as recognized-but-not-actionable (acknowledged,
  no status change) rather than guessed at.

Before a real transaction ever runs against either gateway: get real
sandbox credentials, dispatch a real `createDonation` call, and drive at
least one real webhook through `paymentWebhook` end to end — the same
verification `test:donations-e2e` already does for `mock`, but for real.

Primary sources consulted (9 Sep 2026): `cashfree.com/docs/reference/pgcreateorder`,
`cashfree.com/docs/api-reference/payments/latest/{orders/create,payments/webhooks,refunds/webhooks,enums}`,
`cashfree.com/docs/payments/online/webhooks/signature-verification`,
`razorpay.com/docs/api/orders/{create,entity}`, `razorpay.com/docs/api/payments/entity`,
`razorpay.com/docs/webhooks/{validate-test,payments,refunds}`.

## 5. FCRA / foreign-contribution boundary

`createDonation` hardcodes every donation to `contributionType:
'DOMESTIC'`, `fcraApplicable: false`, **regardless of the donor's own
country field**, until a human decides otherwise. This is intentional
and conservative: the code does not attempt to classify a donation as an
accepted "foreign contribution" for compliance purposes, because that
classification is a legal one this session cannot make. See
`dge/firebase/functions/index.js`'s `createDonation` for the exact
comment marking where donor-country-aware classification would go once
the Trust's FCRA registration/permission status and banking arrangement
are confirmed (Phase 5 in §8 below) — not before.

## 6. Testing this feature

```bash
cd dge/firebase/tests
npm test                    # pure-function unit tests (this feature: 88 of them --
                             # donation-core 26, payment-state 13, payment-providers 41
                             # (mock + cashfree + razorpay), receipt-core 8)
npm run test:rules          # Firestore rules, real emulator (this feature: 21 tests)
npm run test:donations-e2e  # real Functions + Firestore emulators, the `mock` gateway,
                             # end to end: createDonation -> signed webhook -> SUCCESS ->
                             # receipt -> Supporters Wall entry -> idempotent replay ->
                             # a stale out-of-order event rejected
```

The Cashfree and Razorpay adapters are covered by unit tests only (signature
verification, request shaping, event parsing/normalization against synthetic
fixtures) — `test:donations-e2e` still exercises the `mock` gateway exclusively,
since neither real gateway has credentials to run an actual end-to-end pass
against (see §4's honesty note).

`test:donations-e2e` needs `dge/firebase/functions/.secret.local`
(gitignored, never committed — same convention `FIREBASE_SETUP.md`
already documents for `.env.local`) holding a `PAYMENT_WEBHOOK_SECRET`
line; any value works since the `mock` gateway is the only thing that
ever reads it.

What these tests actually prove, concretely: amount tampering is
rejected before any gateway call; a name that is pure markup sanitizes
to nothing and is rejected; the browser's return URL is never trusted —
`getDonationStatus` is the only source of truth a success page may show;
a webhook with a bad or missing signature is rejected; a replayed
webhook event never mints a second receipt or a duplicate Supporters
Wall entry; a stale/out-of-order event (e.g. a late `PENDING` arriving
after `SUCCESS`) can never walk a donation backwards; the public
Supporters Wall entry never carries PAN, email, phone, or the donor's
internal ID.

## 7. What is NOT tested or built yet — be honest about this before real money moves

- **No rate limiting** on `createDonation` or `paymentWebhook`. `sendOtp`
  has one (`otp-core.js`'s cooldown + per-hour cap); this feature needs
  the equivalent before it is reachable by the public internet with a
  real gateway behind it — otherwise a script can open unlimited PENDING
  donations (cheap, but pollutes the data) or hammer the webhook
  endpoint.
- **No way to INITIATE a refund** — `index.js` can now RECEIVE a refund
  webhook from either gateway and correctly classify it as full vs.
  partial (comparing the refunded amount to the donation's own amount),
  but nothing calls a gateway's refund API or exposes an admin action to
  start one. A refund still has to be issued from the gateway's own
  dashboard for now; this feature only reacts to it afterward.
- **No donation frontend.** `createDonation`/`getDonationStatus` are
  callable functions with no UI in front of them yet.
- **No real email provider** — receipts are logged, not sent.
- **No admin dashboard** — deliberately, per §21 of the original spec;
  Firestore's own console (superadmin-only collections) covers
  operational inspection until real volume justifies building one.

## 8. Phases (what's built vs. what's still ahead)

| Phase | Status |
|---|---|
| **0 — Compliance** (legal entity, PAN, bank account, 12A/80G, FCRA status, gateway merchant approval) | ❌ the lead's own action items — nothing here can substitute for them, see §9 |
| **1 — Domestic payment foundation** (schema, validation, state machine, gateway adapter pattern, webhook idempotency, receipts, tests) | ✅ this document |
| **1a — Cashfree and Razorpay adapters, switchable per-donation or by deployment default** | ✅ code-complete and unit-tested against synthetic fixtures; ❌ neither has real credentials or a real end-to-end run — see §4 |
| **1b — Real credentials, rate limiting, and a donation UI** | ❌ next, once the lead adds real credentials for whichever gateway(s) go live first |
| **2 — Supporters Wall UI** (the `public_supporters` collection already exists and is tested; a page rendering it does not) | ❌ not started |
| **3 — Supporter magic-link auth** (Firebase Auth already supports this pattern; linking a `donorId` to a `uid` is the new part) | ❌ not started |
| **4 — Entitlements actually granted** (`supporter_entitlements` collection and `maybeGrantEntitlements()` hook exist; no entitlement is defined yet) | ❌ not started |
| **5 — International / FCRA-aware contributions** | ❌ not started, and must not start before §0 compliance is confirmed |

## 9. Before any of this touches a real rupee

This is the lead's checklist, not something an AI session can complete:

- [ ] Trust legal entity, PAN, and bank account verified
- [ ] 12A/12AB status confirmed (if applicable)
- [ ] 80G status confirmed (if applicable) — **this repo's receipt email
      template deliberately makes no tax-deductibility claim** until
      this is confirmed, see `receipt-core.js`'s own comment on that
- [ ] FCRA status and, if applicable, the FCRA-designated bank account
      confirmed against the Trust's actual registration — never assumed
      from a payment gateway's own marketing copy
- [ ] Merchant/KYC approval completed with Cashfree, Razorpay, or both —
      whichever actually goes live; `PAYMENT_GATEWAYS_ENABLED` (§4) only
      needs to name the ones that are actually approved and configured
- [ ] International payment capability, if wanted, separately approved
      by that gateway — never enabled by frontend code alone

## 10. The donation page (`dge/donate.html`), what it does and doesn't do

Self-contained (own inline CSS, no dependency on `config.js` or `user-auth.js`
— it duplicates the public `FIREBASE_CONFIG` values, which is fine per that
file's own comment that they're not secret), reachable at `dge/donate.html`.
No sign-in required — `createDonation`/`getDonationStatus` are both public
callables by design (§0 of this doc, `enforceAppCheck: false`).

- Sends `name`/`email`/`phone`/`country`(`'IN'`)/`pan`(optional)/`amount`/
  `purpose`/`displayName`/`displayAmount` to `createDonation`. Never sends a
  `gateway` field — which gateway actually runs is a deployment config
  decision (`PAYMENT_GATEWAY`/`PAYMENT_GATEWAYS_ENABLED`), not something the
  frontend should hardcode.
- Branches on the returned `checkout.gateway`:
  - `mock` — shows a plain "test mode, nothing was charged" banner with the
    donation reference. This is what actually happens today, since neither
    real gateway has credentials yet.
  - `razorpay` — loads Checkout.js and opens it with `keyId`/`orderId`/
    `amount`/`currency` from the response; on the modal's own success
    callback, redirects to `?ref=<reference>`.
  - `cashfree` — loads the v3 SDK and calls `cashfree.checkout()` with
    `paymentSessionId`; Cashfree owns the redirect back via `returnUrl`'s
    `{order_id}` placeholder (substituted by Cashfree itself, since our
    `donationReference` IS the Cashfree `order_id` — see
    `lib/payment-providers.js`).
  - `CASHFREE_MODE` (`'sandbox'` in the page's own script) has to be flipped
    to `'production'` by hand once real, live Cashfree credentials are
    configured — the client has no way to ask the server which
    `CASHFREE_ENV` is set.
- On load, a `?ref=` in the URL always re-verifies through
  `getDonationStatus` — never a gateway's own query params or the fact that
  its checkout redirected back at all. This is the one rule §0/§7 insist on
  everywhere else in this feature, carried through to the one place a
  browser actually sees a result.

**Still not done, before this should be linked from the site nav or shared
publicly:** rate limiting (§7 — this page makes it directly reachable by
anyone), real credentials for at least one gateway (above), and the
compliance checklist above. Right now it is reachable only by direct URL,
which is enough to test the `mock` path end to end but not yet something to
publish a link to.
