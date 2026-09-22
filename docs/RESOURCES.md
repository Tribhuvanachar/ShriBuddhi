# Every account, key, URL and service this project uses

Written 22 Sep 2026, to answer one instruction: *"There should be no
duplication of keys. … I may ask any of this to be run from any of the
repository. Things should not be duplicated or rerun or recreated. It must
just use the already existing created ones."*

**Read this before creating anything.** Every resource below already exists.
Nothing here needs a second copy — not a project, not a bucket, not a service
account, not a key. If a workflow appears to need one, it needs the existing
one granted to it, not a new one made.

Companion documents: `CREDENTIALS.md` (how to spend money through Actions),
`SETUP_PLAYBOOK.md` (the console click-paths), `REPO_INVENTORY.md` (what each
repo contains).

---

## 0. Two corrections that invalidate older notes

**`bhumandala` and `JagatTest` are the same repository.** `bhumandala` was
renamed to `JagatTest`; `https://github.com/Tribhuvanachar/bhumandala` answers
`301 → JagatTest`. Earlier documents and this session's own earlier notes
described them as two repos with two roles. They are one repo. A local clone
directory named `bhumandala` is a second clone of `JagatTest`, usually stale.

This matters beyond tidiness: **every jsDelivr URL in the site still says
`gh/Tribhuvanachar/bhumandala@…` and works only because GitHub keeps the
rename redirect alive.** The day anyone creates a new repo called `bhumandala`
under this account, the redirect dies and the search index, the WordNet, the
Kavya corpus and the sandhi data all stop loading on the live site. Do not
create a repo by that name. Renaming these URLs to `JagatTest` is safe and
should be done the next time `js/config.js` is touched.

**ShriBuddhi is PUBLIC.** `GET /repos/Tribhuvanachar/ShriBuddhi` returns
`"private": false`, 2,688,101 KB. `CREDENTIALS.md` called it private and built
an argument on that; the argument is corrected in §4 below. Two consequences
worth stating plainly: repository *secrets* are still safe (GitHub never
exposes them to forks or to the public), but everything *committed* to this
repo is world-readable, including anything added while it was believed private.

---

## 1. Accounts and consoles

| what | identifier | where to open it |
|---|---|---|
| GitHub account | `Tribhuvanachar` | https://github.com/Tribhuvanachar |
| Google Cloud / Firebase project | **`sarvamula-org`** (display name "Sarvamula"), project number `1005094356690` | https://console.cloud.google.com/home/dashboard?project=sarvamula-org |
| Firebase console, same project | `sarvamula-org` | https://console.firebase.google.com/project/sarvamula-org |
| Live site | `https://sarvamula.org/` (200) | GitHub Pages, not Firebase Hosting — `firebase/firebase.json` says so in its own header |
| Sarvam Document AI | prepaid balance | https://dashboard.sarvam.ai |
| Google AI Studio (Gemini key) | same Google account | https://aistudio.google.com/apikey |
| Hugging Face space | `sarvamulaorg-kamadhenu` | https://sarvamulaorg-kamadhenu.hf.space |

**There is exactly one Google Cloud project.** `sarvamula-org` is both the
Firebase project and the GCP project — Firebase projects *are* GCP projects.
Do not create a second one for storage, for functions, or for the search index.

---

## 2. Service accounts — there are two, and only one is used

Both live in `sarvamula-org`
(https://console.cloud.google.com/iam-admin/serviceaccounts?project=sarvamula-org):

| service account | who created it | used by | keep? |
|---|---|---|---|
| `github-search-index@sarvamula-org.iam.gserviceaccount.com` | created by hand for CI | **every workflow** — reindex publish, Firestore deploy, hosting, functions | **yes — this is the one** |
| `firebase-adminsdk-…@sarvamula-org.iam.gserviceaccount.com` | created automatically by Firebase when the project was made | nothing in this project's CI | leave it alone |

This is the "two service accounts, there must be just one" question, answered
from the run log rather than from memory. Reindex run `35705512268` printed:

    service-account key assembled from: SA_JSON_1
    Activated service account credentials for: [github-search-index@***.iam.gserviceaccount.com]

So `github-search-index` is the single identity doing all the work, and the
secret it came out of is `FIREBASE_SERVICE_ACCOUNT` (see §3).

**The `firebase-adminsdk` account is not a duplicate you made and should not be
deleted.** Firebase creates it for every project and uses it internally for
Admin SDK operations and parts of the console. No secret in any repository
holds its key, and no workflow authenticates as it. Deleting it risks breaking
Firebase features for no gain. *Two accounts exist; one credential is in use.
That is already the "just one" you asked for.*

Roles currently granted to `github-search-index`: Cloud Datastore Index Admin,
Firebase Rules Admin, Service Usage Consumer, Storage Admin. **Grant new
permissions to this account. Never make a new account to hold them.**

**Missing, and blocking playbook §D entirely: Secret Manager Admin**
(`roles/secretmanager.admin`). Confirmed 22 Sep 2026 by run 35718541325:

    ERROR: (gcloud.secrets.list) [github-search-index@…] does not have
    permission … Permission 'secretmanager.secrets.list' denied
    reason: IAM_PERMISSION_DENIED

Without it this account cannot read which function secrets exist, cannot add a
version to one, and cannot deploy Cloud Functions (the deploy resolves every
`defineSecret()` while loading the code). Grant it at
<https://console.cloud.google.com/iam-admin/iam?project=sarvamula-org> —
**to this existing account**, not to a new one.

---

## 3. GitHub secrets — which repo holds what, and where each value comes from

`gh` is not installed in the session container and `/actions/secrets` is
blocked by the proxy (403), so a session **cannot list or set secrets**. The
names below come from reading every workflow file; the values must be checked
in the browser:

* ShriBuddhi → https://github.com/Tribhuvanachar/ShriBuddhi/settings/secrets/actions
* JagatTest → https://github.com/Tribhuvanachar/JagatTest/settings/secrets/actions

GitHub never shows a secret's value after it is saved — only its name and last
update date. "Where to check its value" therefore means *go back to the source
that issued it*, which is the last column.

### Set on ShriBuddhi

| secret | what it is | where the value is re-issued |
|---|---|---|
| `FIREBASE_SERVICE_ACCOUNT` | the **whole JSON key file** for `github-search-index@` | IAM → that account → Keys → Add key. Paste the file verbatim. |
| `SEARCH_INDEX_BUCKET` | a **bucket name**, not a URL: `sarvamula-search-index` | Cloud Storage console |
| `SARVAM_API_KEY` | Sarvam Document AI | https://dashboard.sarvam.ai |
| `VISION_API_KEY` | Google Cloud Vision API key | GCP → APIs & Services → Credentials |
| `BRAHMABUDDHI_TOKEN` | PAT that can push to BrahmaBuddhi | GitHub → Settings → Developer settings → PATs |
| `BUDDHI_TOKEN` | PAT used by the deploy/promote workflows | same |
| `ANTHROPIC_API_KEY`, `CLAUDE_CODE_OAUTH_TOKEN` | Claude Code action | console.anthropic.com |
| `HF_TOKEN` | Hugging Face | huggingface.co/settings/tokens |
| Internet Archive, WhatsApp, MSG91, Razorpay, Cashfree, OTP | see §5 | — |

### Set on JagatTest

| secret | what it is | where the value is re-issued |
|---|---|---|
| `GEMINI_API_KEY` | Gemini | https://aistudio.google.com/apikey |
| `SHRIBUDDHI_TOKEN` | PAT used to clone ShriBuddhi **and push back to it** | GitHub PAT settings — **currently read-only; see §4** |
| `SARVAM_API_KEY`, `VISION_API_KEY` | present here too | as above |

### The real duplication is in the NAMES, not the keys

Four workflows search a *list* of alternative secret names for the same one
credential, because nobody remembered which name had been used:

* Firebase service account, in `reindex.yml`, `deploy-firestore.yml`,
  `deploy-firebase-hosting.yml`, `deploy-firebase-functions.yml`,
  `deploy-preview-shribuddhi.yml`, `push-firebase-function-secrets.yml`:
  `FIREBASE_SERVICE_ACCOUNT` → `FIREBASE_SERVICE_ACCOUNT_KEY` →
  `FIREBASE_SERVICE_ACCOUNT_SARVAMULA_ORG` → `FIREBASE_ADMIN_SDK` →
  `GOOGLE_APPLICATION_CREDENTIALS_JSON`, and failing those, assembled from
  `FIREBASE_PRIVATE_KEY` + `FIREBASE_CLIENT_EMAIL` + `FIREBASE_PRIVATE_KEY_ID`
  + `FIREBASE_CLIENT_ID`.
  **Only `FIREBASE_SERVICE_ACCOUNT` is actually set** — the run log's
  "assembled from: SA_JSON_1" proves the first name matched. The other eight
  names should be deleted from the workflows, and any that were ever set
  should be deleted from the repo, so there is one name for one key.
* Internet Archive, in `archive-upload.yml`: `IA_ACCESS_KEY` /
  `ARCHIVE_ACCESS_KEY` / `IAS3_ACCESS_KEY` / `INTERNETARCHIVE_ACCESS_KEY`
  (and the matching `*_SECRET_KEY`). Four names, one S3-like credential pair
  from https://archive.org/account/s3.php. Canonical: `IA_ACCESS_KEY` /
  `IA_SECRET_KEY`.
* Dispatch token, in `push-firebase-function-secrets.yml`:
  `GH_DISPATCH_TOKEN` / `GITHUB_DISPATCH_TOKEN`. Canonical:
  `GITHUB_DISPATCH_TOKEN`, which is also the name the Cloud Function reads.

None of these are duplicate *credentials*. They are duplicate *aliases*, which
is worse in one way — you cannot tell from the workflow which name to set — and
harmless in another: setting one is enough.

---

## 4. `SHRIBUDDHI_TOKEN` cannot push, and it is costing money

JagatTest run `35687670866` (Gemini proofread, 22 Sep) cloned ShriBuddhi
successfully, spent real money proofreading 825 blocks, and then:

    remote: Invalid username or token. Password authentication is not supported
    fatal: Authentication failed for 'https://github.com/Tribhuvanachar/ShriBuddhi.git/'

The reachability check at step 4 returned HTTP 200 and the partial clone
worked, so the token is valid — it simply has **read but not write** on
ShriBuddhi. Every cross-repo Gemini workflow ends this way: money spent,
result thrown away. The 825 blocks were recovered by hand from the run's
artifact (`tools/aitareya/land_proofread.py`), but that is a rescue, not a fix.

**Fix:** GitHub → Settings → Developer settings → Fine-grained tokens → the
token behind `SHRIBUDDHI_TOKEN` → Repository permissions → **Contents:
Read and write** → Regenerate/Update, then paste the new value into JagatTest's
`SHRIBUDDHI_TOKEN`.

**Better fix, now available:** ShriBuddhi is public (§0). The entire reason
Gemini work was moved to JagatTest was *"Actions is free and unlimited on a
public repository and capped at 2,000 minutes a month on a private one"* — and
that cap no longer applies to ShriBuddhi. `GEMINI_API_KEY` can be added to
ShriBuddhi's secrets and the Gemini workflows run there directly, reading and
writing `data/ocr_staging/` in the same checkout. No cross-repo token, no push
step, nothing to fail after the money is spent.

---

## 5. Cloud Functions and their secrets

Region `asia-south1`, project `sarvamula-org`. Source: `firebase/functions/index.js`.

| function | deployed? (probed 22 Sep) |
|---|---|
| `whatsappWebhook` | yes — 403 to an unsigned GET |
| `paymentWebhook` | yes — 405 to a GET |
| `corpusFile` | **no — 404** |
| `renderBook` | **no — 404** |
| `sendOtp`, `verifyOtp`, `listWorkflows`, `runWorkflow`, `createDonation`, `getDonationStatus` | callable-only, not probeable by URL |

`deploy-firebase-functions.yml` has never run, which is consistent with
`corpusFile`/`renderBook` being absent while the older ones are live.

Function secrets live in **Google Secret Manager**, not in GitHub —
https://console.cloud.google.com/security/secret-manager?project=sarvamula-org.
`push-firebase-function-secrets.yml` copies them up from GitHub secrets:
`WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_VERIFY_TOKEN`,
`WHATSAPP_APP_SECRET`, `MSG91_AUTHKEY`, `OTP_PEPPER`, `PAYMENT_WEBHOOK_SECRET`,
`RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`, `CASHFREE_CLIENT_ID`,
`CASHFREE_CLIENT_SECRET`, `GITHUB_DISPATCH_TOKEN`.

Issuing consoles: Meta for WhatsApp (developers.facebook.com), msg91.com,
dashboard.razorpay.com, merchant.cashfree.com. `OTP_PEPPER` is a locally
generated random string with no external issuer — if it is rotated, every
outstanding OTP hash is invalidated.

---

## 6. Storage and CDN

| resource | value |
|---|---|
| Search-index bucket | `gs://sarvamula-search-index`, project `sarvamula-org`, region `asia-south1` |
| Public URL of the published index | `https://storage.googleapis.com/sarvamula-search-index/search_index/<hash>/` |
| Current published build | `search_index/449134cbc285/` — verified 200, 215,933 files |
| Bucket public access | `allUsers` → Storage Object Viewer (granted 22 Sep) |
| Firebase Storage bucket | `sarvamula-org.firebasestorage.app` — separate, for app uploads |
| jsDelivr search pin | `gh/Tribhuvanachar/bhumandala@838335f8152654c37ee1c256c36b6ff6aab3927f` = ShriBuddhi branch `buddhi-archive/search-dist`, built 11 Sep 2026 |
| jsDelivr WordNet pin | `…@66c7895fa7b1f30150ebbf74ea67abc28909e550/_wordnet` |
| jsDelivr Kavya pin | `…@75ef2103bc07770ccb861497c32636d706c09fa4` |
| jsDelivr sandhi pin | `…@2a255c3dd7f357364c75a72afa664a6588c8ff44/_sandhi` |
| Kosha pin | `gh/Tribhuvanachar/Kosha@54072a8d40d4907df588d722b3796afe06ec2568/data/koshas` |

The Firebase **web** config in `js/config.js` (`apiKey:
"AIzaSyC_mvK6f4CS91B51iEvx2B6wlk_9A-lVCw"`, `authDomain`,
`messagingSenderId: 1005094356690`, `appId`, `measurementId: G-YB411NKZLE`) is
**not a secret**. Firebase web API keys are public identifiers; access is
controlled by `firestore.rules`, not by hiding this string.

`admin/config/keys.json` is likewise not an API key file — it holds admin-gate
passkeys, and `admin/js/keys.js` describes it as "a courtesy latch". Nothing
sensitive belongs behind it.

---

## 7. Rules for any repository that is asked to run something

1. **Look here first.** Every account, bucket, project and service account
   already exists. The answer to "I need a service account" is
   `github-search-index@sarvamula-org.iam.gserviceaccount.com`. The answer to
   "I need a GCP project" is `sarvamula-org`. The answer to "I need a bucket"
   is `sarvamula-search-index`.
2. **Grant, do not create.** If a new repo's workflow cannot reach something,
   add the missing IAM role to the existing service account, or add the
   existing secret to that repo. Do not mint a parallel identity.
3. **One name per secret.** Use the canonical names in §3. Do not add a new
   alias to a fallback chain; delete the chain instead.
4. **A key belongs in the repo whose workflow needs it,** and the same value
   may legitimately be set in several repos — that is copying a credential,
   not duplicating a resource. Rotating it means updating every repo listed
   in §3, which is why the list is here.
5. **Never create a repository named `bhumandala`** (§0).
6. **Check before concluding something is missing.** Both times a session
   concluded a resource did not exist, the session was wrong: once from a
   shallow clone, once from an ambiguous GCS 404 that meant "no permission".
   A 404 from Cloud Storage does not distinguish "absent" from "not yours".
