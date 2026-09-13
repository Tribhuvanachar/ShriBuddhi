# DGE Accounts, OTP & WhatsApp — Firebase Setup

_Originally written 10 Aug 2026 (Google Sign-In + Firebase phone OTP,
untested). Substantially revised 16 Aug 2026: added WhatsApp OTP and
broadcasts, tightened the security rules, and — for the first time —
tests. 204 of them now run without a Firebase project, credentials, or
money. See §10 for what still cannot be tested without live accounts._

## 0. Where this stands (8 Sep 2026, ~12:00 pm IST)

The lead created the Firebase project **`sarvamula-org`** and pasted its web config; it is now in
`dge/js/config.js` (`FIREBASE_CONFIG`) and `AUTH_CONFIG.enabled` is **true**. The three identifiers are
also GitHub secrets (`FIREBASE_API_KEY`, `FIREBASE_AUTH_DOMAIN`, `FIREBASE_PROJECT_ID`) — harmless, but
only `FIREBASE_PROJECT_ID` is used by the deploy workflows; the web config is public by design (§4).

| Console step (§3) | State |
|---|---|
| Authorized domains | ✅ `tribhuvanachar.github.io`, `sarvamula.org`, `madhvacharya.in`, `sanatanavidyagurukulam.com`, the `*.web.app`/`*.firebaseapp.com` hosts, `localhost` |
| Verified emails only | ✅ 7 Sep 2026: `user-auth.js` stores an email only when the provider marks it verified (`dgeVerifiedEmail`), and captures a later-verified one on the next sign-in; `firestore.rules` `emailOk()`/`emailVerifiedFlagOk()` reject any other email on create or self-update (7 emulator tests); the Manage Users screen exports the verified list as CSV (`dgeExportVerifiedEmails`). There is no email/password sign-up in DGE, so `sendEmailVerification` is not needed today; if one is added, the same rule already gates it |
| Google sign-in provider | ✅ enabled by the lead (6 Sep 2026, ~9:40 pm IST) |
| Firestore database | ✅ created by the lead, 8 Sep 2026 (production mode, per §3.3 below) |
| `FIREBASE_SERVICE_ACCOUNT` secret | ✅ added by the lead, 8 Sep 2026 |
| Firestore rules + indexes deploy | ✅ **live, 8 Sep 2026, ~11:56 am IST** (`Deploy — Firestore rules & indexes` runs 8 and 9) — see §0.1 for what it actually took to get here |
| Hosting deploy | ✅ **live, 8 Sep 2026, ~12:11 pm IST** — preview channel confirmed serving the real site (fetched, title "Sarvamūla Digital Library", the ॐ landing page and footer links render). First attempt had failed with `Error: ../.. is outside of project directory` (`dge/firebase/firebase.json`'s `hosting.public: "../.."` reached outside what firebase-tools treats as the config file's own directory); fixed with a dedicated `firebase-hosting.json` at the repo root (`public: "."`) used via `--config` — `dge/firebase/firebase.json` unchanged, still serves firestore/functions/emulators. `live` channel / DNS cutover is still the lead's decision, GitHub Pages remains the live origin until then |
| Cloud Functions (WhatsApp OTP + broadcasts + donations) | ✅ **all 9 functions live, 10 Sep 2026 ~10:46 am IST** (`sendOtp`, `verifyOtp`, `whatsappWebhook`, `runWhatsAppBroadcast`, `listWorkflows`, `runWorkflow`, `createDonation`, `paymentWebhook`, `getDonationStatus`, region `asia-south1`) — see the 10 Sep entries below for the four distinct root causes it took to get here. `whatsappWebhook` URL: `https://asia-south1-sarvamula-org.cloudfunctions.net/whatsappWebhook`; `paymentWebhook`: `https://asia-south1-sarvamula-org.cloudfunctions.net/paymentWebhook`. Still off in `AUTH_CONFIG` (`enablePhoneAuth: false`) and `PAYMENT_GATEWAYS_ENABLED=mock` — deployed and callable, not yet switched on for real traffic. |
| Role-based content access (Access Control) | ✅ **built 8 Sep 2026** — see §0.3 |

**10 Sep 2026 correction**: while actually adding these as GitHub repository secrets for the first
time, GitHub's own console refused to create one named `GITHUB_DISPATCH_TOKEN` — repository secret
names may never start with the reserved `GITHUB_` prefix. Every reference in this repo (`index.js`'s
`defineSecret()` call, `push-firebase-function-secrets.yml`) is renamed to **`GH_DISPATCH_TOKEN`**
throughout; the table row above and §12 below already reflect the new name. Also confirmed while
digging into this: `push-firebase-function-secrets.yml` had never been run even once, and separately
never pushed the five payment secrets (`PAYMENT_WEBHOOK_SECRET`, `CASHFREE_CLIENT_ID/SECRET`,
`RAZORPAY_KEY_SECRET`/`WEBHOOK_SECRET`) despite documenting them as required — both fixed the same
session (see `PAYMENTS_SETUP.md` §4 and the workflow file's own header comment).

**10 Sep 2026, getting from secrets resolving to all 9 functions actually live — three more
distinct root causes, in order:**
1. **`firebase deploy --non-interactive` refuses a `defineString()`'s own code-level `default`.**
   All twelve non-secret params (`OTP_PROVIDER`, `PAYMENT_GATEWAY`, etc.) failed with "In
   non-interactive mode but have no value for the following environment variables" even though
   every one has a `{ default: ... }` in `index.js`. Fixed: `deploy-firebase-functions.yml` now
   writes `dge/firebase/functions/.env` with each param's already-declared default before
   deploying — never committed, regenerated every run.
2. **Four more Google Cloud APIs needed a project owner to click Enable**, on top of Artifact
   Registry (8 Sep): `cloudscheduler.googleapis.com`, `run.googleapis.com`,
   `eventarc.googleapis.com`, `pubsub.googleapis.com`, and finally `cloudbilling.googleapis.com` —
   same class of problem as §0.1, same fix (Cloud Console → APIs & Services → Library → Enable),
   just five more of them, one at a time as each was reached.
3. **`firebase deploy` exits 1 even after every function deploys successfully** if Artifact
   Registry has no image cleanup policy yet for the deploy region — a one-time setup step, not a
   real failure. Fixed: the deploy step now passes `--non-interactive --force`, which lets
   firebase-tools configure that policy itself instead of erroring afterward.
4. **`runWhatsAppBroadcast` (the one scheduled function) needed two more IAM roles** on
   `firebase-adminsdk-fbsvc@...`, on top of the ones already granted for the other eight functions
   (Cloud Functions Admin, Cloud Build Editor, Artifact Registry Administrator, Cloud Run Admin,
   Eventarc Admin, Secret Manager Admin, Service Account User/Token Creator, plus the pre-existing
   Firebase Admin/Rules Admin/Authentication Admin) — **Cloud Scheduler Admin** and **Pub/Sub
   Admin** — easy to mis-click for similarly-named wrong roles
   (**Cloud Datastore Backup Schedules Admin**, **Pub/Sub Lite Admin**) when searching by keyword
   in the IAM role picker; both are real, different roles for unrelated products. Confirm the
   *exact* role name landed on the *right* service account, not just that "something with that
   keyword" was added.

### 0.1 What actually blocked the Firestore deploy (resolved 8 Sep 2026)

Nine dispatches, three distinct root causes, in the order they were found and fixed:

1. **No service-account secret at all** — `deploy-firebase-hosting.yml` read nine possible secret
   names, none set. Fixed: the lead added `FIREBASE_SERVICE_ACCOUNT` (Adarsh's generated key, whole
   JSON) as a repository secret.
2. **Missing Google Cloud IAM roles on the service account** — the auto-created `firebase-adminsdk-*`
   account only carries "Firebase Admin SDK Administrator Service Agent" (`roles/firebase.sdkAdminServiceAgent`),
   built for Admin SDK data reads/writes, not control-plane deploys. Fixed: the lead added "Firebase
   Admin" (`roles/firebase.admin`) and later "Firebase Rules Admin" (`roles/firebaserules.admin`) in
   Google Cloud Console → IAM & Admin → IAM, on `firebase-adminsdk-fbsvc@sarvamula-org.iam.gserviceaccount.com`.
   A `firebaserules.googleapis.com:test` 403 persisted for three attempts even after this — a red
   herring turned out to be the next item, not IAM; a `firebase-tools@13 → @15` bump also happened
   around here and got the deploy past that specific 403 into a *different*, more informative error.
3. **`FIREBASE_PROJECT_ID` secret held `sarvamula` instead of `sarvamula-org`** — found via a diagnostic
   step that reported the secret's length (9, not 13) and whether it ended in `-org` (no), without ever
   printing the value. Every deploy call had been asking Google about a project that doesn't exist;
   different APIs phrased that as a 403 or a 400 depending on how defensively each one is written.
   Fixed: the lead corrected the secret to `sarvamula-org`.
4. **A redundant single-field index in `firestore.indexes.json`** — once the project id was right, the
   deploy got all the way to uploading rules (succeeded) and then rejected one index entry
   (`users`/`lastLoginAt`) with "this index is not necessary, configure using single field index
   controls": Firestore auto-indexes every field both ascending and descending by default, so a
   single-field entry in the composite-index file is invalid. Fixed in the repo — removed; the only
   query against it (`orderBy('lastLoginAt', 'desc')`, no other filters) needs no composite index.

Net lesson for next time a Firebase deploy workflow fails: read the *literal* error text every time,
even the third or ninth time it looks similar — three of these four causes produced errors that read
as permission problems but were not.



### 0.2 Phone OTP + WhatsApp — the ordered path to turning it on

Read §2 first (cost) and §5 (channel tradeoffs) if you haven't. Recommendation there stands: prefer
`'whatsapp'` over `'firebase'` once you're ready for phone verification, for the ~6x cost difference.
This is the actual sequence, in order — each step names who does it:

1. **You: decide the channel.** `'whatsapp'`, `'msg91'`, or stay on Google-only for now. The rest of
   this list assumes `'whatsapp'`; `'msg91'` needs the same Cloud Functions plus DLT registration (§7
   doesn't cover DLT — that's an MSG91-side process).
2. **You: get Firestore rules deploying** (§0/§0.1 above) — Cloud Functions read the same project and
   the same rules govern `broadcasts`/`users` writes, so this has to work first.
3. **Me, once (2) is green: dispatch `Deploy — Firebase Functions`.** This deploys everything in
   `dge/firebase/functions` (`requestOtp`, `verifyOtp`, `whatsappWebhook`, `runWhatsAppBroadcast`, the
   admin workflow-dispatch functions). The functions that need WhatsApp secrets will exist but error
   when called until step 5 — that's expected, it doesn't block this deploy. If this 403s, it's very
   likely a *further* IAM role (2nd-gen functions deploy to Cloud Run under the hood and are more
   permission-hungry than Hosting/Firestore) — the workflow's header explains what to look for; read
   the actual error and grant only what it names, same playbook as §0.1.
4. **You: set up Meta.** Nobody but you (or Adarsh) can do this part:
   - Create a Meta Business account and a WhatsApp Business app at developers.facebook.com.
   - WhatsApp → API Setup: note the **Phone number ID**, generate a **permanent** (System User) access
     token — not the 24-hour temporary one.
   - **Register the phone number on the Cloud API.** WhatsApp Manager → Phone numbers shows the number
     stuck on **Pending** with "register this phone number using the registration API" even after you
     complete the SMS/voice OTP — that OTP only proves you own the number, it is a *different* step from
     making the number able to send/receive on the Cloud API. The "reach out to your partner" half of
     that message is generic boilerplate Meta shows on every number regardless of setup; ignore it for a
     direct (non-BSP) integration like this one and call the API yourself:
     ```bash
     curl -X POST "https://graph.facebook.com/v21.0/<PHONE_NUMBER_ID>/register" \
       -H "Authorization: Bearer <ACCESS_TOKEN>" \
       -H "Content-Type: application/json" \
       -d '{"messaging_product": "whatsapp", "pin": "<PICK_A_6_DIGIT_PIN>"}'
     ```
     The temporary token from API Setup works for this one call. The 6-digit `pin` you choose becomes
     that number's two-step verification PIN for future registrations/migrations — write it down next to
     `OTP_PEPPER`. A `{"success": true}` response flips WhatsApp Manager's status to Connected on refresh.
   - WhatsApp Manager → Message templates → create an **Authentication** template named `dge_otp`
     with the **copy code** button enabled. Approval is usually minutes to a few hours.
   - Create a **Utility** template for broadcasts (e.g. the daily shloka), with whatever variables you
     want to fill in per message.
   - Meta app → Settings → Basic: note the **App Secret**.
   - Pick any long random string for `OTP_PEPPER` (a password manager's generator is fine) — **write
     it down somewhere durable**, see the warning in step 5.
5. **You: add six GitHub repository secrets** (same screen as `FIREBASE_SERVICE_ACCOUNT` — Settings →
   Secrets and variables → Actions → Repository secrets): `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`,
   `WHATSAPP_VERIFY_TOKEN` (any random string you choose — Meta will ask for this exact value in step
   6), `WHATSAPP_APP_SECRET`, `OTP_PEPPER`, and `MSG91_AUTHKEY` only if using that channel instead.
   **`OTP_PEPPER` is written once, ever.** Phone-account UIDs are derived from it — changing it later
   orphans every existing phone account. `push-firebase-function-secrets.yml` refuses to overwrite an
   existing `OTP_PEPPER` version unless you explicitly tick `rotate_otp_pepper`, precisely to prevent
   that by accident.
6. **Me, once (5) is done: dispatch `Push Firebase Functions secrets`.** Pushes each one from GitHub
   into Firebase's own Secret Manager, where the functions actually read them — never through this
   chat, never committed. I'll report which names were pushed (never the values).
7. **You: point Meta's webhook** at the deployed `whatsappWebhook` function URL (printed in the step-4
   deploy log, or Firebase Console → Functions → `whatsappWebhook` → copy the trigger URL), using the
   `WHATSAPP_VERIFY_TOKEN` from step 5, and subscribe to the `messages` field. This is what honours
   **STOP** replies — not optional, ignoring opt-outs is a Meta policy breach and damages the sender
   quality rating that governs how much WhatsApp lets the account send at all.
8. **Me: flip the switches in `dge/js/config.js`** and merge: `AUTH_CONFIG.enablePhoneAuth = true`,
   `phoneOtpProvider = 'whatsapp'`, and — only once you're ready for broadcasts specifically —
   `enableWhatsappBroadcasts = true`. These can land in one commit or two; broadcasts don't require
   phone auth to be on, they're independent (§8).
9. **Both: test end to end.** Sign in with a real phone number, confirm the WhatsApp OTP arrives with
   the copy-code button, confirm a wrong code is rejected and rate limits hold (1/minute, 5/hour per
   number — `functions/lib/otp-core.js`). For broadcasts, add one test document to the `broadcasts`
   collection with `sendAfter` a minute out and confirm it fires and marks itself delivered (§8 has the
   exact document shape).

Nothing in steps 1, 4, 5, 7 can be done by an AI session — they're either a decision only you can make,
or require Meta Business Manager / GitHub settings access. Steps 3, 6, 8 are mine once their
prerequisites land; tell me when each is ready rather than waiting for all of them at once.

### 0.3 Role-based content access (`admin/access-control.html`)

The lead's ask: create custom roles beyond the fixed six, restrict specific library paths
(commentaries, granthas, whole folders) to specific roles, test the result without needing several
real accounts, and have a real signed-in account actually reflect its role in the app. Deliberately
**UI-level hiding, not server-enforced access** — the lead's explicit choice when offered both: a gated
path is left out of the reader's navigation/search for a role that can't see it, the same way
`admin/library.html`'s "Hide" list already works, but the underlying `data.json` stays a public static
file and a direct URL still fetches it. Real per-request enforcement would mean serving corpus text
through an authenticated proxy instead of static files on Hosting — a materially different (and more
expensive, see the cost note below) hosting architecture, out of scope unless asked for later.

**Pieces:**
- `firestore.rules`' `config/{docId}` block — `config/roles` (`{list:[{id,label}]}`) and
  `config/roleAccess` (`{gates:[{prefix,allowRoles:[id,...]}]}`), public read (so a signed-out visitor's
  view is gated too), superadmin-only write. Covered by 4 of the 51 rules-emulator tests in
  `dge/firebase/tests/rules.spec.js`.
- `dge/js/role-access.js` — loads those two docs once (cached), a pure prefix-matcher
  (`dgeMatchRoleGate`/`dgeIsRoleGatedPath`, unit tested in `dge/firebase/tests/role-access.test.js`
  without any Firebase/DOM), and `dgeSetPreviewRole`/`dgeGetPreviewRole`/`dgeClearPreviewRole`
  (sessionStorage, superadmin-only) for previewing the reader as another role in the same browser.
- `dge/js/library.js`'s `dgeIsHiddenPath` — extended with one extra check
  (`dgeIsHiddenByRoleGate`) alongside the pre-existing curator "hidden" list; a real admin/superadmin
  always bypasses a gate (so curating one can't lock its own author out), a *previewed* role does not.
- `admin/access-control.html` — role list (add/remove custom roles; the six built-ins can't be
  removed), a content-gate picker (path + which roles may see it, longest-prefix-wins), and an
  in-page "Test it" panel that checks the DRAFT instantly (no save needed) — the fast
  create-role → grant-access → test loop the lead asked for. Gated the same way every other
  `admin/*.html` page is (a passkey from `admin/config/keys.json`, or `localStorage.is_superadmin`) —
  but that only opens the PAGE; **saving still requires being actually signed in with a Firebase
  account whose stored role is `superadmin`**, enforced for real by the rules above, not by this page's
  own passkey.
- "Log in and see what roles I've got": `dge/js/user-auth.js`'s `dgeBridgeRoleToAdminTools()` — on
  every sign-in, mirrors the REAL Firestore role (`admin`/`superadmin`) onto the same
  `localStorage.is_superadmin`/`acharyaAuthorized` flags the old `?superadmin=CODE` passkey sets, live,
  no reload — so a real account now reveals the admin tools menu (including Access Control) the same
  way the passkey always did, without replacing the passkey.

**Cost**: reads two small Firestore docs per page view, on top of the Firebase SDK `user-auth.js`
already loads unconditionally whenever `AUTH_CONFIG.enabled` — well inside the free tier (50k
reads/day) at any traffic this site sees today. The lead separately asked whether the *whole* corpus
(not just these two config docs) could move into Firestore instead of static JSON: no — Firestore's
1 MiB per-document limit is a hard wall several `data.json` files already blow past by 20-70x (measured,
not estimated), so that would need re-chunking ~16,000 files into 100,000+ documents, and would turn
today's flat/CDN-cached hosting cost into one that scales with reader traffic. Not recommended; noted
here so the reasoning isn't lost.

**Not yet done**: nothing in this feature is deployed differently from the rest of the site — it rides
the existing Firestore rules + Hosting deploys above. It has not been exercised against a *live*
Firestore project (this session's Playwright check ran against the real page but with gstatic.com
unreachable from the sandbox, which the code handles by falling back to "no gates configured" — worth
one real click-through once Firestore is confirmed reachable from wherever the lead tests next).

## 1. What this is

User accounts, per-person roles (basic / subscriber / sponsor / admin /
superadmin / special), phone verification over three interchangeable
channels, and opt-in WhatsApp broadcasts — backed by Firebase. This is
the only backend DGE has; everything else remains a static site.

**It is OFF by default.** `AUTH_CONFIG.enabled` in `config.js` is `false`
out of the box — no Account button, no Firebase network calls, nothing
changes until you do the steps below AND flip that to `true`. There is a
test asserting exactly that, so it stays true.

Files involved, all deliberately isolated so a deployment that doesn't
want any of this can ignore them:

```
dge/js/user-auth.js          browser: sign-in, OTP, consent
dge/js/user-roles.js         browser: superadmin "Manage Users" screen
dge/js/config.js             FIREBASE_CONFIG + AUTH_CONFIG switches
dge/firebase/firestore.rules the real enforcement layer
dge/firebase/firebase.json   project config (emulators, hosting, functions)
dge/firebase/functions/      Cloud Functions: OTP, broadcasts, webhook
dge/firebase/tests/          234 tests — see tests/README.md
```

## 2. Cost — read this before enabling anything

**The pricing figures in the original brief for this work were wrong in
two places, both in the expensive direction.** Corrected here, with the
caveat that you should confirm current rates in your own console before
committing budget — these move.

| Thing | Reality (Aug 2026) |
|---|---|
| Google Sign-In | **Free**, any volume, no billing plan needed. |
| Firestore | Free tier: 50k reads / 20k writes per day, 1 GB. A profile doc is a few hundred bytes; 100k users is a few MB. |
| Firebase SMS OTP | **~$0.01 (~₹0.85) per verification in India.** Requires the Blaze plan. |
| WhatsApp auth template | **~₹0.145 (~$0.0017) per message in India** — roughly **6x cheaper than SMS**. |
| MSG91 SMS | ~₹0.15, comparable to WhatsApp; reaches non-WhatsApp users. |
| Cloud Functions | Free tier: 2M invocations/month. Requires Blaze. |
| Cloud Scheduler | 3 free jobs. This project uses 1. |
| Firebase Hosting | Free tier: 10 GB storage, 10 GB/month transfer, free SSL. |

Two corrections worth stating plainly, because they change decisions:

- **"Firebase Phone Auth is free for 10,000 SMS/month" is not true.** The
  free allowance is roughly **10 SMS per day** (~300/month), and phone
  auth requires Blaze regardless. Assume you pay from the first real
  user. At 100,000 verifications that is roughly **$1,000**.
- **"WhatsApp is free for the first 1,000 conversations/month" no longer
  applies to OTPs.** Since Meta's move to per-message pricing, *service*
  messages (user-initiated, inside the 24-hour window) are free, but
  **authentication, utility and marketing templates are billed per
  message**. An OTP is an authentication template — always paid. The good
  news is that it is still ~6x cheaper than SMS: the same 100,000
  verifications run roughly **₹14,500 (~$170)** instead of ~$1,000.

**Recommendation:** start with Google Sign-In only — free, no billing
setup, no Blaze. Add phone verification when you actually need it, and
when you do, prefer `whatsapp` over `firebase` for the cost difference.
Keep `msg91` in reserve for users who don't have WhatsApp.

## 3. Console steps (nobody but you can do these)

1. [console.firebase.google.com](https://console.firebase.google.com) → create a project.
2. **Authentication** → Sign-in method → enable **Google**.
3. **Firestore Database** → Create → **production mode** (not test mode — test mode ignores your rules for 30 days and then locks everything out).
4. **Firestore** → Rules → paste `dge/firebase/firestore.rules` → Publish. Or `cd dge/firebase && firebase deploy --only firestore:rules`.
5. **Project settings** → General → Your apps → Add app → Web (`</>`) → copy the `firebaseConfig` object.
6. **Authentication → Settings → Authorized domains** → add whichever domain actually serves the site. Today that is **`tribhuvanachar.github.io`**. When the custom domain goes live (expected 29 Aug 2026, or 18 Sep — see the checklist in `site.config.json`), **add `www.sarvamula.org` and `sarvamula.org` too**. Google Sign-In fails silently from an unauthorized domain: no error, no popup, nothing happens at all — which makes it one of the harder things to diagnose after a domain move. (`localhost` is authorized by default, so local testing needs nothing added.)

## 4. What to paste into this repo

In `dge/js/config.js`, replace every `REPLACE_WITH_...` in
`FIREBASE_CONFIG`, then set `AUTH_CONFIG.enabled = true`.

These values are **not secret** — Firebase's docs are explicit that this
object ships in client code; access control comes from the security
rules, not from hiding it. (The WhatsApp and MSG91 credentials in §7 are
a completely different matter and must never go in this file.)

That's all for Google Sign-In. Reload — a 👤 icon appears in the toolbar.
Signing in creates `users/<uid>` with `role: "basic"`.

**Becoming the first superadmin:** nobody starts as one, on purpose. Sign
in once, then in the Firestore console open `users/<your-uid>` and change
`role` to `superadmin` by hand. From then on you can promote others from
the in-app 👥 Manage Users screen.

## 5. Phone verification — picking a channel

Set `AUTH_CONFIG.enablePhoneAuth = true` and choose
`AUTH_CONFIG.phoneOtpProvider`:

- **`'firebase'`** — Firebase's own SMS. No backend needed; skip §6-7
  entirely. Enable **Phone** under Authentication → Sign-in method
  (requires Blaze). Uses an invisible reCAPTCHA, which can be finicky on
  `localhost` — test on the real domain if it misbehaves. Most expensive.
- **`'whatsapp'`** — WhatsApp Cloud API via our Cloud Functions. ~6x
  cheaper, arrives with a one-tap copy button. Needs §6 and §7.
- **`'msg91'`** — India SMS gateway via the same Cloud Functions. Needs
  §6, §7, and DLT registration.

The last two share one backend and one client code path. Switching
between them is one string here plus one env value on the deployed
functions.

## 6. Deploying the Cloud Functions

Needed only for the `whatsapp` and `msg91` channels, and for broadcasts.

```bash
cd dge/firebase
cp .firebaserc.example .firebaserc     # then put your project id in it
cd functions && npm install && cd ..
firebase deploy --only functions
```

The functions deploy to **asia-south1** (Mumbai). If you change that in
`functions/index.js`, change `AUTH_CONFIG.functionsRegion` to match, or
every call lands on a URL that does not exist.

Deploying functions requires the **Blaze** plan. Set a budget alert and a
low daily spend cap while you are still testing — the OTP rate limits in
`functions/lib/otp-core.js` (1 code per minute, 5 per hour per number)
are the code-level guard, but a billing cap is the one that cannot be
argued with.

## 7. WhatsApp Cloud API setup

1. Create a Meta Business account and a WhatsApp Business app at [developers.facebook.com](https://developers.facebook.com).
2. **WhatsApp → API Setup**: note the **Phone number ID** and generate a **permanent** access token (a System User token — the temporary 24-hour one is only useful for a first smoke test).
3. **Register the number** — see the "Register the phone number on the Cloud API" bullet in §0.2 step 4. SMS/voice ownership verification and Cloud API registration are two different steps; the number stays "Pending" in WhatsApp Manager until the registration API call succeeds.
4. **WhatsApp Manager → Message templates** → create an **Authentication** template. Name it `dge_otp` (or set `OTP_TEMPLATE_NAME` to whatever you call it). Enable the **copy code** button — that button is the reason to use WhatsApp for OTP at all. Approval usually takes minutes to a few hours.
5. Create a **Utility** template for broadcasts, with whatever variables you need. Utility is the correct category for "here is today's shloka"; marketing costs more and is held to stricter rules.
6. Set the secrets:

```bash
cd dge/firebase
firebase functions:secrets:set WHATSAPP_TOKEN
firebase functions:secrets:set WHATSAPP_PHONE_NUMBER_ID
firebase functions:secrets:set WHATSAPP_VERIFY_TOKEN   # any random string you choose
firebase functions:secrets:set WHATSAPP_APP_SECRET     # Meta app → Settings → Basic
firebase functions:secrets:set OTP_PEPPER              # any long random string
# only if using msg91:
firebase functions:secrets:set MSG91_AUTHKEY
```

**`OTP_PEPPER` must be set once and never rotated.** Phone-based account
UIDs are derived from it; changing it orphans every existing phone
account, because the same person would derive a different UID.

7. Point Meta's webhook at the deployed `whatsappWebhook` URL, using the
   `WHATSAPP_VERIFY_TOKEN` you chose, and subscribe to the `messages`
   field. This is what honours **STOP** replies. It is not optional:
   ignoring opt-outs is a policy breach, and recipients blocking the
   number damages the sender quality rating that governs how much
   WhatsApp lets you send at all.

## 8. WhatsApp broadcasts

Set `AUTH_CONFIG.enableWhatsappBroadcasts = true` to show the consent
checkbox on the account screen. Nobody is messaged without ticking it —
consent starts `false`, the security rules reject a profile created with
it `true`, and the audience selector requires a literal `true`.

To schedule a message, add a document to the `broadcasts` collection
(superadmin only, per the rules):

```js
{
  templateName: "dge_daily_shloka",   // an approved Utility template
  languageCode: "en",
  bodyParams: ["Bhagavad Gita", "2.47"],
  status: "scheduled",
  sendAfter: <Timestamp>,
  roles: ["subscriber", "sponsor"],   // optional; omit for everyone
  minGapMs: 86400000,                 // optional floor between broadcasts
  maxPerRun: 500                      // optional cap per firing
}
```

`runWhatsAppBroadcast` fires daily at 07:00 IST, claims each due campaign
transactionally (so an overlapping run cannot double-send), records
delivery per user, and marks hard-bounced numbers so later campaigns skip
them. A campaign that exceeds `maxPerRun` stays `scheduled` and continues
on the next firing.

## 9. Hosting (optional, not done)

`firebase.json` declares a hosting config, but **the site still ships from
GitHub Pages** and nothing here changes that. Migrating is a separate
decision — the upside over Pages is mainly the custom-domain SSL and CDN
story, and this repo carries large binary assets that are worth thinking
about before pointing a CDN at them. If you do migrate: `firebase deploy
--only hosting`, then add the A/CNAME records Firebase gives you at your
registrar. SSL and custom domains are free either way.

## 10. What is and isn't tested

**Tested — 249 tests, no credentials, no cost** (`cd dge/firebase/tests
&& npm install && npm run test:all` — `test:all` also needs `cd
../functions && npm install` once, for the end-to-end suite):

- The OTP state machine: expiry to the millisecond, attempt caps
  (including that a correct code fails once the cap is hit), per-number
  rate limits, salted hashing, and that the plaintext code is never
  stored.
- The security rules, **against the real Firestore emulator**: privilege
  escalation at sign-up, self-promotion, admin-vs-superadmin separation,
  the OTP collection being sealed from every client, and that a user
  cannot rewrite the record of which paid broadcasts they already
  received.
- WhatsApp payload shapes, webhook signature forgery, and opt-out
  detection (including that "please don't stop sending these" does *not*
  unsubscribe someone).
- The workflow buttons' allowlist: that a workflow not on the list, an
  input the workflow does not declare, a caller-supplied branch, or an
  admin reaching for a super-admin job are all refused.
- The browser flow with a stubbed SDK: transport routing, that a new
  profile is always created as `basic` with consent off even if
  `config.js` is tampered with, and that the whole feature stays inert
  when disabled.
- **`index.js` itself, end to end, against the real functions + Firestore
  + auth emulators** (`npm run test:e2e`, `dge/firebase/tests/e2e.spec.js`):
  send → store hashed → verify → mint a custom token → create the profile
  document, the resend cooldown, the attempt cap, replay protection, and
  the webhook's signature/handshake checks — all through the deployed
  function code, not a stub. This is the one file the rest of the suite
  cannot reach (it's the Firebase-shaped shell around the tested logic:
  secrets, transactions, custom tokens), and the one time it was written
  without ever being run, it failed immediately — `admin.firestore.
  FieldValue` reads back as `undefined` through the functions emulator's
  proxy of the `firebase-admin` root export, so every `serverTimestamp()`
  threw. Fixed by moving to the modular `firebase-admin/{app,firestore,
  auth}` imports, which don't go through that proxy. See
  `dge/firebase/tests/README.md` for what `test:e2e` needs locally
  (`functions/.secret.local`, git-ignored, for the `defineSecret()`
  params it can't reach without `firebase login`).

**Not tested, and only observable against live accounts:**

- That Google/Meta/MSG91 accept our requests, that templates are
  approved, that messages actually arrive.
- reCAPTCHA behaviour for the `firebase` SMS channel.
- Real billing. Set a budget cap before the first real send.

## 11. Deliberately not built

- **Unifying this with the existing localStorage passkey admin system.**
  The `?pass=`/`?superadmin=` system still works exactly as before, and
  runs in parallel with Firebase roles. Merging them would disrupt a
  working daily workflow while this is still new.
- **Pagination in Manage Users** — still the 200 most recently active.
- **App Check.** The OTP endpoints are protected by server-side rate
  limits, not by attestation. Worth adding if abuse ever shows up in the
  logs.
- **Delivery-status tracking.** The webhook parses inbound messages for
  opt-outs but ignores `statuses` callbacks; per-message delivery
  receipts are not recorded.

## 12. The workflow buttons (`admin/repo-map.html`, Workflows tab)

(Until 9 Sep 2026 this was a separate page, `admin/workflows.html`; it is now
the Workflows tab of *Repository & Workflows*, and the old URL redirects.)

The site is static on GitHub Pages: a page cannot start a job by itself, and
it must never hold a token that could — anything shipped to a browser is
readable by whoever opens it. So the panel talks to two Cloud Functions,
`listWorkflows` and `runWorkflow`, which hold the token and check the caller.
The page also accepts a personal GitHub token typed into the browser (the same
one Repo Files uses) as a second route, which is the lead's own credential and
never leaves their device; the Function route is the one that lets *other*
admins press buttons without holding a token.

```
admin/repo-map.html   ──▶  runWorkflow  ──▶  GitHub API
(admin latch +             (holds the token as     (workflow_dispatch,
 Firebase Auth)             a secret; reads the     ref: main, always)
                            caller's role from
                            Firestore, not from
                            anything the browser said)
```

**Until this is deployed the panel still works** — it lists the same five
workflows and every button opens the GitHub Actions page instead. That is not
a degraded mode so much as the same capability one tab away, and it is what
the page shows today, because `AUTH_CONFIG.enabled` is still `false`.

### What has to be true before it can be deployed

1. **The Blaze plan.** A Function on the free Spark plan cannot make an
   outbound call to a non-Google host, and `api.github.com` is one. Set a
   budget cap at the same time; these two functions cost effectively nothing
   (a handful of invocations a month), but a cap is what stops a mistake
   elsewhere from becoming a bill.
2. **A fine-grained token.** GitHub → Settings → Developer settings →
   Personal access tokens → **Fine-grained tokens**:
   - Repository access: **Only select repositories** → `bhumandala`, and
     nothing else.
   - Permissions: **Actions: Read and write**. Nothing else. Not `contents`,
     not `workflows`, not organisation permissions.
   - An expiry you will actually notice — 90 days, with a reminder.

   A classic PAT with `repo` scope would work and must not be used: it can
   read and write every repository the account can reach, and it would be
   sitting in a service whose whole job is to accept requests from a browser.
   If the token below is ever leaked, the worst it can do is start one of
   five workflows in one repository.

### Deploying it

```bash
cd dge/firebase
firebase functions:secrets:set GH_DISPATCH_TOKEN     # paste the token
firebase deploy --only functions:listWorkflows,functions:runWorkflow
firebase deploy --only firestore:indexes,firestore:rules
```

**8 Sep 2026 correction**: that `--only functions:listWorkflows,functions:runWorkflow` does NOT skip
the other six `defineSecret()`s in `functions/index.js` — firebase-tools loads and analyzes the WHOLE
file to build its deploy plan regardless of `--only`, so it still tries to resolve
`WHATSAPP_TOKEN`/`WHATSAPP_PHONE_NUMBER_ID`/`WHATSAPP_VERIFY_TOKEN`/`WHATSAPP_APP_SECRET`/
`MSG91_AUTHKEY`/`OTP_PEPPER` and fails if any of them has no version yet (see §0's status table for
where this was discovered the hard way, across three attempts). In practice: **every** secret needs a
version in Secret Manager before **any** function deploy, `--only` or not — a placeholder is fine for
whichever of the WhatsApp/MSG91 ones aren't real yet, since those transports stay off in
`AUTH_CONFIG` until deliberately switched on.

The repository defaults to `Tribhuvanachar/bhumandala`; override it with the
`GITHUB_REPO` env param if that ever changes.

### What the panel can and cannot do

- **Only the five workflows in `functions/workflows.json`.** A caller cannot
  name a workflow file, invent an input, or choose a branch: `ref` is always
  `main`, set in code, because a caller-supplied ref is arbitrary code
  execution by another name.
- **Roles are read server-side.** `is_superadmin` in localStorage decides
  what the UI *shows*; the Function reads `users/{uid}.role` from Firestore
  and decides what actually runs. Jobs that republish text a reader will see
  (`import-kavya`, `publish-wordnet`) need `superadmin`; the reporting and
  tracker jobs accept `admin`.
- **Every press is recorded** in the `workflow_dispatches` collection — who,
  which workflow, which inputs, and whether GitHub accepted it. Written by
  the Admin SDK, readable by admins, writable by no client.
- **One minute between presses** of the same workflow by the same account, so
  a double-click cannot open two pull requests.

The allowlist, the role rules and the input validation are all in
`functions/lib/workflows-core.js`, with 30 tests in
`tests/workflows-core.test.js` that run with no credentials and no cost.
