# Setup playbook

Five jobs, each one a list of steps with the exact page to open, the exact
button to press, and the exact place the value goes. Written 21 Sep 2026
against the code as it stands in ShriBuddhi.

Where a value must be kept secret, the instruction says which of the **three
different stores** it belongs in. They are not interchangeable, and putting a
value in the wrong one is the most common way these setups fail:

| store | what it is for | where |
|---|---|---|
| **GitHub Actions secrets** | things a *workflow* needs | `https://github.com/Tribhuvanachar/ShriBuddhi/settings/secrets/actions` |
| **Firebase Functions secrets** | things the *server* needs at runtime | the `firebase functions:secrets:set` command |
| **Function config strings** | non-secret settings (a public key id, a mode) | `firebase/functions/.env` or `functions:config` |

A sentence that says "paste it here" always means one of those three.

---

## A · Get the search index off the repository and onto Cloud Storage

**Why.** `search_index/` is **2,027 MB across 179,514 files** inside the git
repository, and it is *derived* — `tools/build_search_index.py` regenerates
all of it from `data/`. It is the single largest thing you own and none of it
needs to be in git. The workflow that publishes it to Cloud Storage already
exists and has **never once run**, because the secrets below were never set.

### A1 · Make a Cloud Storage bucket

1. Open **<https://console.cloud.google.com/storage/browser>**
2. Top of the page, check the **project selector** shows the project your
   Firebase app uses. If not, click it and pick that project.
3. Click **CREATE** (or **CREATE BUCKET**).
4. **Name**: something you will recognise, e.g. `sarvamula-search-index`.
   Bucket names are globally unique — if it is taken, add a suffix.
5. **Location type**: `Region`, and choose `asia-south1 (Mumbai)`.
6. **Storage class**: `Standard`.
7. **Access control**: choose **Uniform**.
8. Untick **Enforce public access prevention on this bucket** — the site
   fetches these files from the browser, so they must be publicly readable.
9. Click **CREATE**.
10. On the bucket's **PERMISSIONS** tab, click **GRANT ACCESS**.
    - *New principals*: `allUsers`
    - *Role*: `Storage Object Viewer`
    - **SAVE**, then confirm **ALLOW PUBLIC ACCESS**.

**Copy the bucket name.** That is the value of `SEARCH_INDEX_BUCKET`.

### A2 · Make a service account so the workflow may write to it

1. Open **<https://console.cloud.google.com/iam-admin/serviceaccounts>**
2. **CREATE SERVICE ACCOUNT**.
   - *Name*: `github-search-index`
   - **CREATE AND CONTINUE**
3. *Grant this service account access*: role **Storage Admin**. **CONTINUE**,
   then **DONE**.
4. Click the account you just made → **KEYS** tab → **ADD KEY** → **Create
   new key** → **JSON** → **CREATE**. A `.json` file downloads. **This file
   is shown once and never again.**

### A3 · Put the two values into GitHub

1. Open **<https://github.com/Tribhuvanachar/ShriBuddhi/settings/secrets/actions>**
2. **New repository secret**:
   - *Name*: `SEARCH_INDEX_BUCKET`
   - *Secret*: the bucket name from A1 (just the name — no `gs://`, no slash)
   - **Add secret**
3. **New repository secret** again:
   - *Name*: `FIREBASE_SERVICE_ACCOUNT`
   - *Secret*: open the downloaded `.json` in a text editor, select all,
     copy, paste the **whole file including the braces**
   - **Add secret**
4. **New repository secret** a third time:
   - *Name*: `FIREBASE_PROJECT_ID`
   - *Secret*: the `project_id` value from inside that same JSON file
   - **Add secret**

> The workflow accepts the key under any of `FIREBASE_SERVICE_ACCOUNT`,
> `FIREBASE_SERVICE_ACCOUNT_KEY`, `FIREBASE_ADMIN_SDK`, or
> `GOOGLE_APPLICATION_CREDENTIALS_JSON`. One of them is enough.

### A4 · Run it

1. Open **<https://github.com/Tribhuvanachar/ShriBuddhi/actions>**
2. Left sidebar → **"DGE re-index (search + library status)"** — that is the
   name it appears under; "the re-index workflow" is not findable. →
   **Run workflow**.
3. Watch the step **"Publish the index to Cloud Storage"**.

**Read that step carefully, because it can lie.** It is `continue-on-error`,
so a failed upload still shows a green tick and the job still says success.
It also prints `uploading NNN files to gs://…` **before** the transfer, so a
glance at the log looks like it worked whether or not it did. On 22 Sep it
printed exactly that and then died on `HTTPError 400: Invalid bucket name`.

Since 22 Sep the step says so itself: a failure now writes **`PUBLISH
FAILED`** into the run summary, and a bucket name it cannot use is rejected
*before* the transfer with a message saying what the value should look like.
It also strips a leading `gs://`, a trailing slash and any path, so those
shapes no longer matter.

**It worked if** the summary says `published to gs://…` and does **not** say
`PUBLISH FAILED`.

The index lands at `gs://<bucket>/search_index/<data-sha>/`, cached for a
year, and each build gets its own immutable prefix — so a new build never
disturbs the one the live site is reading.

---

## B · Shrink the repositories

**Today: 8.2 GB.** Where it is:

| | size | tracked in git? | derived? |
|---|---|---|---|
| `search_index/` | 2,027 MB, 179,514 files | yes | **yes** — rebuilt from `data/` |
| `data/` | 1,866 MB | yes | no — this is the library itself |
| `tools/dcs/vendor/` | 388 MB | yes | **yes** — a vendored third-party corpus |
| `.git/` | 3,200 MB | — | history of all the above |

### B1 · Stop tracking the index (do A first)

Once A4 has published successfully — **not before**:

```bash
cd ShriBuddhi
git rm -r --cached search_index
printf 'search_index/\n' >> .gitignore
git commit -m "The search index is published to Cloud Storage, not carried in git"
git push
```

The files stay on your disk; git stops carrying them. **This removes 2 GB
from every future clone but not from history** — `.git` stays 3.2 GB until
B3.

### B2 · Stop tracking the vendored corpus

`tools/dcs/vendor/` is third-party data, not our source:

```bash
git rm -r --cached tools/dcs/vendor
printf 'tools/dcs/vendor/\n' >> .gitignore
git commit -m "DCS vendor data is a download, not source"
git push
```

Write a one-line fetch script beside it so a fresh checkout can get it back.

### B3 · Actually shrink `.git` (destructive — read twice)

Only B3 reclaims the 3.2 GB, and it **rewrites history**: every commit hash
changes, and everyone with a clone must re-clone. Do it once, deliberately,
when nobody has unpushed work.

1. Install the tool: **<https://github.com/newren/git-filter-repo>**
   (`pip install git-filter-repo`)
2. **Make a backup clone first**: `git clone --mirror <url> backup.git`
3. ```bash
   git filter-repo --path search_index --path tools/dcs/vendor --invert-paths
   git push --force --all
   git push --force --tags
   ```
4. Tell everyone with a clone to delete it and clone again.

**Expected after all three: about 2.1 GB**, nearly all of it `data/`, which
is the library and should stay.

> If you would rather not rewrite history, do B1 and B2 only and tell people
> to clone with `--depth 1`. That gives them a ~2 GB checkout without
> touching anyone's existing clone.

---

## C · Firebase and Firestore

**Do not create a new project.** An earlier version of this section read as
if you were starting from zero. You are not, and following it literally would
have duplicated a working project.

### What already exists — checked, not assumed

| thing | state | evidence |
|---|---|---|
| Firebase project | **`sarvamula-org`** exists | Firebase console; `js/config.js` line 760 |
| Web config in the site | **done**, pasted 6 Sep 2026 | `FIREBASE_CONFIG` in `js/config.js` |
| Google sign-in | **on** | `AUTH_CONFIG.enableGoogleSignIn: true` |
| Firestore + roles | **exists** | your own check; `firebase/firestore.rules` reads `users/<uid>.role` |
| Blaze plan | **active since 8 Sep 2026** | header of `deploy-firebase-functions.yml` |

So **C1, C2 and C3 as previously written are already done.** Nothing to redo.

### One correction to the old text

It told you to enable **Phone** auth. Do not, unless you mean to pay for it.
`AUTH_CONFIG.enablePhoneAuth` is deliberately **`false`**, and the comment
beside it says why: phone OTP needs Blaze and costs roughly ₹0.85 per
verification through Firebase's own SMS, against about ₹0.145 through the
WhatsApp path (§E). The code supports all three channels. Turning the console
provider on without choosing a channel here changes nothing and can start
costing money.

### What is actually left: deploying rules and functions

Not the CLI. **Three workflows already exist for this**, and the old §C4's
`firebase deploy` instructions were wrong to send you to a terminal:

| workflow | state | what it does |
|---|---|---|
| `deploy-firestore.yml` | **succeeded 22 Sep** | publishes `firestore.rules` + indexes |
| `deploy-firebase-functions.yml` | **never run** | Cloud Functions (needed for §D and §E) |
| `deploy-firebase-hosting.yml` | **never run** | the static site to Firebase Hosting |

**What the first success actually did**, since the distinction matters: it
released the rules and **deployed the indexes**, but reported *"latest version
of firestore.rules already up to date, skipping upload"*. So the rules content
was already live on the project before this — presumably published by hand, or
by this workflow back when it lived in bhumandala. The indexes in
`firestore.indexes.json` are the part that genuinely landed for the first time.

An earlier draft here said the rules had "never been published". That was
inferred from the workflow's run history and was wrong about the rules
themselves; only the *workflow* had never succeeded.

**`deploy-firestore.yml` is blocked on one missing secret, and it is not the
Firebase one.** Re-run on 22 Sep: it failed at *"Checkout bhumandala (the site
actually being deployed)"* with `Input required and not supplied: token`.

That step wants **`BUDDHI_TOKEN`**, a GitHub token with read access to
`Tribhuvanachar/bhumandala`, and ShriBuddhi does not have it. The Firebase
credential is fine — the re-index run the same day passed its
"Assemble the service-account key" step for the first time.

**Why a Firestore deploy checks out another repository at all**: the workflow
moved here from bhumandala on 12 Sep and says in its own header that the
rules and indexes "have to come from THERE, not from" this repo. It runs
`firebase deploy` inside `bhumandala/firebase`, so bhumandala's copy is what
reaches the project. (As of 22 Sep the two copies are byte-identical — 334
lines, both bootstrap lists empty — but bhumandala's is the authoritative
one, and if they ever drift, deploying this repo's would be wrong.)

**To unblock it:**

1. Make a token that can read bhumandala —
   <https://github.com/settings/personal-access-tokens> → **Fine-grained
   token** → Repository access: `Tribhuvanachar/bhumandala` → Permissions:
   **Contents: Read-only** → **Generate**.
2. <https://github.com/Tribhuvanachar/ShriBuddhi/settings/secrets/actions> →
   **New repository secret** → Name `BUDDHI_TOKEN` → paste → **Add secret**.
3. Re-run the workflow.

Note the secret stores are per-repository. JagatTest having a token of a
similar name does nothing for a workflow running in ShriBuddhi.

**Until `deploy-firestore.yml` succeeds, `firebase/firestore.rules` has never
been published.** Whatever is enforcing roles in your Firestore today is
whatever was set in the console, not the file in this repo. That is the single
most important thing in section C, and it is the one thing that was never
framed as urgent.

Run them from
<https://github.com/Tribhuvanachar/ShriBuddhi/actions>, in this order:
`deploy-firestore.yml`, then `deploy-firebase-functions.yml`. Hosting stays
optional — GitHub Pages is still the live origin.

### The roles the deploy service account needs

`deploy-firestore.yml` on 22 Sep got past the checkout and the credential and
then failed on IAM:

```
Error: Request to serviceusage.googleapis.com/v1/projects/<id>/services/
firestore.googleapis.com had HTTP Error: 403,
Permission denied to get service [firestore.googleapis.com]
```

That is not a Firestore permission. Before deploying anything, the Firebase
CLI asks the **Service Usage API** whether `firestore.googleapis.com` is
enabled on the project, and the service account may not ask.

Grant these on the **project**, at
<https://console.cloud.google.com/iam-admin/iam> (project selector must read
**Sarvamula**), to the `client_email` from the `FIREBASE_SERVICE_ACCOUNT`
JSON:

| role | why |
|---|---|
| **Service Usage Consumer** | the check above — `serviceusage.services.get` |
| **Firebase Rules Admin** | publishing `firestore.rules` |
| **Cloud Datastore Index Admin** | publishing `firestore.indexes.json` |

`Editor` covers all three, and is the blunt option if the console makes the
individual roles hard to find. Prefer the three.

### Where each value goes — unchanged, and still the part that trips people

| value | store | why |
|---|---|---|
| `firebaseConfig` (apiKey, appId…) | **the site's source** | public by design; already in `js/config.js` |
| service-account JSON | **GitHub secret** | workflows use it |
| `RAZORPAY_KEY_SECRET` | **Functions secret** (§D) | server only, never the browser |
| `RAZORPAY_KEY_ID` | Functions **config string** | public, shown to the payer |
| `WHATSAPP_TOKEN` | **Functions secret** (§E) | server only |

`apiKey` is a public project identifier, not a password — it is meant to ship
in the browser. What protects the data is `firebase/firestore.rules`, which is
written and tested but, per the table above, **not yet deployed**.

**Never commit a service-account JSON or any `*_SECRET` to git.**

> Five files (`firebase/functions/index.js`, `firebase/tests/rules.spec.js`,
> `firebase/tests/README.md`, `firebase/functions/lib/providers.js`,
> `admin/README.md`) point at a `FIREBASE_SETUP.md` that **does not exist in
> this repository**. Treat this section as its replacement.

---

## D · Razorpay

The code is already written — `firebase/functions/lib/payment-providers.js`
implements order creation and webhook verification, and there are tests in
`firebase/tests/payment-providers.test.js`. What follows switches it on.

### D1 · Get the keys

1. **<https://dashboard.razorpay.com/app/website-app-settings/api-keys>**
2. Start in **Test mode** (the toggle is at the top of the dashboard).
3. **Generate Test Key**.
4. You get **Key Id** (`rzp_test_…`) and **Key Secret**. **The secret is
   shown once.** Copy both now.

### D2 · Give the SECRET to the functions — through GitHub, not a terminal

**The old text here told you to run `firebase functions:secrets:set` in a
local checkout. Ignore that.** It needs the Firebase CLI installed and logged
in as someone with rights on `sarvamula-org`, and this project already has a
workflow that does the same job with no terminal at all. The secret value goes
straight from GitHub into Google Secret Manager and is never printed.

**Step 1 — decide the webhook secret now**, before touching Razorpay. It is
just a long random string that you choose; Razorpay does not generate it. Any
of these will do:

    openssl rand -hex 32

Keep it somewhere you can paste it twice: once into GitHub below, once into
Razorpay in D3. They must match exactly.

**Step 2 — add two repository secrets** at
<https://github.com/Tribhuvanachar/ShriBuddhi/settings/secrets/actions>
→ **New repository secret**:

| Name | Value |
|---|---|
| `RAZORPAY_KEY_SECRET` | the **Key Secret** from D1 |
| `RAZORPAY_WEBHOOK_SECRET` | the random string from step 1 |

The **Key Id** (`rzp_test_…`) does **not** go here. It is not a secret — the
browser receives it to open Razorpay checkout — and it is given at deploy time
in D4 instead. *Never* paste the Key Secret into a workflow input: inputs are
recorded in the run's parameters in clear text.

**Step 3 — check the other ten secrets exist too.** This is the step that
actually bites. `firebase-tools` resolves **every** `defineSecret()` in
`functions/index.js` while it loads the code, so a Functions deploy **fails
outright** if even one of them has no version in Secret Manager — `--only` or
not. All twelve must exist:

    CASHFREE_CLIENT_ID      CASHFREE_CLIENT_SECRET   GITHUB_DISPATCH_TOKEN
    MSG91_AUTHKEY           OTP_PEPPER               PAYMENT_WEBHOOK_SECRET
    RAZORPAY_KEY_SECRET     RAZORPAY_WEBHOOK_SECRET  WHATSAPP_APP_SECRET
    WHATSAPP_PHONE_NUMBER_ID WHATSAPP_TOKEN          WHATSAPP_VERIFY_TOKEN

For anything not in use yet, a placeholder string is fine and always will be —
`PAYMENT_WEBHOOK_SECRET` in particular never needs a real value, because the
`mock` gateway it belongs to refuses to run outside an emulator. Set each one
as a GitHub repository secret with the **same name** (the one exception:
GitHub refuses any name starting with `GITHUB_`, so `GITHUB_DISPATCH_TOKEN` is
stored on GitHub as **`GH_DISPATCH_TOKEN`** and the workflow renames it on the
way in).

**Step 4 — run the push workflow.** Actions →
**"Push Firebase Functions secrets"** → *Run workflow* → leave
`rotate_otp_pepper` **off** → *Run*.

It prints two lines, `Pushed:` and `Skipped:`, naming only which secrets moved
— never a value. **Read them.** Anything in `Skipped: … (no GitHub secret set)`
has no version in Secret Manager and will fail your deploy in D4.

> `OTP_PEPPER` is deliberately skipped once it already has a version. Phone
> account IDs are derived from it, so rotating it orphans every existing phone
> account. Leave that tickbox alone.

### D3 · The webhook

The URL is already known — `paymentWebhook` is deployed and answers today
(a `GET` returns 405, which is the function refusing a non-POST, i.e. it is
live). There is no need to deploy first to find out what it is:

    https://asia-south1-sarvamula-org.cloudfunctions.net/paymentWebhook

1. <https://dashboard.razorpay.com/app/webhooks> → **Add New Webhook**.
2. **Webhook URL**: the URL above, exactly.
3. **Secret**: paste the *same* random string you put in
   `RAZORPAY_WEBHOOK_SECRET` in D2. A mismatch here is the single most common
   failure — the function verifies the signature and rejects every event, so
   payments succeed at Razorpay and no `donations` document is ever updated.
4. **Active Events**: tick `payment.captured`, `payment.failed`, `order.paid`.
5. **Create Webhook**.

Nothing else to do here. The signature check, including `x-razorpay-event-id`
de-duplication, is already implemented and tested
(`firebase/tests/payment-providers.test.js`).

### D4 · Turn it on, then test

Until 22 Sep 2026 **this step was impossible**, and it is worth knowing why
before running it: `deploy-firebase-functions.yml` hardcoded
`PAYMENT_GATEWAY=mock`, `PAYMENT_GATEWAYS_ENABLED=mock` and an empty
`RAZORPAY_KEY_ID` into the deploy's `.env`, with no input to change them. You
could do all of D1–D3 perfectly and the deployed `createDonation` would still
refuse every donation — `mock` is emulator-only by design
(`payment-providers.js` `assertGatewayAllowed`). Those three are now workflow
inputs.

Actions → **"Deploy — Firebase Functions"** → *Run workflow*:

| input | value |
|---|---|
| `payment_gateway` | `razorpay` |
| `payment_gateways_enabled` | `razorpay` |
| `razorpay_key_id` | `rzp_test_…` from D1 |
| everything else | leave as-is |

The workflow refuses to proceed if the gateway is not in the enabled list, if
`razorpay` is enabled with a blank key id, or if what you typed does not look
like a Key Id — that last check exists so a Key *Secret* pasted into the wrong
box is caught before it is written into the run's parameters in clear text.
(If that ever happens, rotate the key at Razorpay immediately.)

**Then test.** Open the donation flow, use Razorpay's test card
**4111 1111 1111 1111**, any future expiry, any CVV, and confirm:

1. Razorpay's dashboard shows the payment **captured**;
2. a document appears in the **`donations`** collection in Firestore
   (<https://console.firebase.google.com/project/sarvamula-org/firestore>)
   and reaches a paid state — that second part is what proves the *webhook*
   arrived, not just the checkout.

If (1) happens and (2) does not, the webhook secret does not match. Redo D3
step 3 and D2 step 2 with the same string.

**Going live**: flip the dashboard to Live mode, generate live keys
(`rzp_live_…`), repeat D2 (new `RAZORPAY_KEY_SECRET`, push workflow) and D3
(new webhook on the live dashboard), redeploy with the `rzp_live_…` key id,
and complete Razorpay's KYC.

### Are you ready for D2–D4? — state as of 22 Sep 2026

| | |
|---|---|
| Razorpay code written and tested | yes — `lib/payment-providers.js`, `tests/payment-providers.test.js` |
| `paymentWebhook` deployed and reachable | **yes** — 405 to a GET |
| `FIREBASE_PROJECT_ID` + `FIREBASE_SERVICE_ACCOUNT` set | yes — `deploy-firestore.yml` succeeded 22 Sep on them |
| A way to set the gateway at deploy time | **now yes** — added 22 Sep; before that, D4 could not work |
| All twelve `defineSecret()` names have versions | **unknown — check this first** (D2 step 3/4) |
| `deploy-firebase-functions.yml` ever run successfully | **no, not once.** Expect to debug the first run. |

The last two lines are the honest risk. The deploy has never been run, and the
most likely first failure is a missing Secret Manager version, which fails the
whole deploy with `--only` set or not. Run the push workflow first and read its
`Skipped:` line.

---

## E · WhatsApp Business API

`firebase/functions/lib/whatsapp.js` is written; `sendOtp`, `verifyOtp`,
`whatsappWebhook` and `runWhatsAppBroadcast` are already exported.

### E1 · Meta app and WhatsApp product

1. **<https://developers.facebook.com/apps/>** → **Create App** → type
   **Business** → name it → **Create app**.
2. On the app dashboard, find **WhatsApp** → **Set up**.
3. It gives you a **test number** and a **Phone number ID**. Note the ID.
4. **API Setup** → **Temporary access token** (valid 24 hours) — fine for
   testing, replaced in E3 for production.

### E2 · A message template (required for OTP)

WhatsApp does **not** allow free-form messages to someone who has not
messaged you first. An OTP must go through an approved template.

1. **<https://business.facebook.com/wa/manage/message-templates/>**
2. **Create template** → Category **Authentication** → Name: `dge_otp`
   (this must match `OTP_TEMPLATE_NAME`, whose default is `dge_otp`)
3. Language **English**. Add the one-time-password body with its `{{1}}`
   variable and submit.
4. Approval usually takes minutes to a few hours.

### E3 · A permanent token

A 24-hour token is no good for a live site.

1. **<https://business.facebook.com/settings/system-users>**
2. **Add** → name it `dge-whatsapp` → role **Admin** → **Create**.
3. **Add Assets** → your app → **Full control** → **Save**.
4. **Generate New Token** → pick the app → tick **whatsapp_business_messaging**
   and **whatsapp_business_management** → **Generate**.
5. **Copy it now — it is shown once.**

### E4 · Give them to the functions

```bash
cd ShriBuddhi/firebase
firebase functions:secrets:set WHATSAPP_TOKEN            # E3
firebase functions:secrets:set WHATSAPP_PHONE_NUMBER_ID  # E1 step 3
firebase functions:secrets:set WHATSAPP_VERIFY_TOKEN     # invent a random string, keep it
firebase functions:secrets:set WHATSAPP_APP_SECRET       # App settings > Basic > App Secret
firebase functions:secrets:set OTP_PEPPER                # invent a long random string
firebase deploy --only functions
```

### E5 · Point the webhook at us

1. Meta app dashboard → **WhatsApp** → **Configuration** → **Edit** webhook.
2. **Callback URL**:
   `https://asia-south1-<your-project-id>.cloudfunctions.net/whatsappWebhook`
3. **Verify token**: exactly the `WHATSAPP_VERIFY_TOKEN` string from E4.
4. **Verify and save** — Meta calls the URL immediately and it must answer.
   If it fails, the functions are not deployed yet.
5. **Manage** → subscribe to the **messages** field.

### E6 · Production number

The test number cannot message arbitrary people. To use your own:
**<https://business.facebook.com/wa/manage/phone-numbers/>** → **Add phone
number** → verify by SMS or call. The number must not be active on the normal
WhatsApp or WhatsApp Business app — if it is, delete that account first.

**Consent.** `whatsappOptIn` starts `false` on every profile and
`firestore.rules` rejects a create that tries to set it true. Signing in is
not consent to be messaged. Do not work around this.

---

## The order to do things in

1. **C** — Firebase, because D and E both deploy functions into it.
2. **A** — the index, because it is the biggest immediate win and unblocks B.
3. **B1/B2** — stop tracking the derived files. **B3 only when ready.**
4. **D** and **E** — independent of each other; do whichever is more urgent.

## When something does not work

- *`FIREBASE_PROJECT_ID secret is not set`* — §A3 step 4 was skipped. The
  re-index no longer dies here; it skips the upload and carries on.
- *Re-index says success but nothing reached the bucket* — see §A4. The
  publish step is `continue-on-error`; check the run summary for
  `PUBLISH FAILED`.
- *`Invalid bucket name`* — `SEARCH_INDEX_BUCKET` holds something that is not
  a bucket name. It wants `sarvamula-search`, not a `gs://` or `https://`
  URL, and not uppercase.
- *`Input required and not supplied: token`* in a deploy-firebase workflow —
  the service-account secret is missing from **ShriBuddhi**. Having it on
  JagatTest does not help; they are separate secret stores.
- *Razorpay webhook shows 401* — `RAZORPAY_WEBHOOK_SECRET` does not match the
  dashboard, or the functions were not redeployed after setting it.
- *WhatsApp webhook verification fails* — the functions are not deployed, or
  `WHATSAPP_VERIFY_TOKEN` differs by a character.
- *Template message not delivered* — the template is not approved yet, or
  `OTP_TEMPLATE_NAME` does not match its name exactly.
