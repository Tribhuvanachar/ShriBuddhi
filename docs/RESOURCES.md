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

**`bhumandala`, `Buddhi` and `JagatTest` are all the same repository.** Both
old names answer `301 → JagatTest`:

    https://github.com/Tribhuvanachar/bhumandala  ->  .../JagatTest
    https://github.com/Tribhuvanachar/Buddhi      ->  .../JagatTest

Earlier documents described them as separate repos with separate roles. They
are one repo with three names, which also means **`BUDDHI_TOKEN` is the
JagatTest token** — that is what `promote-to-buddhi.yml` and `reindex.yml`'s
pin-bump step have always been pushing to. A local clone directory named
`bhumandala` or `buddhi` is another clone of `JagatTest`, usually stale.

Workflow `repository:` fields now spell it `Tribhuvanachar/JagatTest` (fixed
22 Sep 2026 in `reindex.yml` and `promote-to-buddhi.yml`), so they no longer
depend on a redirect that a new repo of either old name would break.

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
| **The site people actually read** | `https://tribhuvanachar.github.io/JagatTest/` and `https://tribhuvanachar.github.io/ShriBuddhi/` — both 200, 41,853 bytes, `<title>Sarvamūla Digital Library</title>` | GitHub Pages, not Firebase Hosting — `firebase/firebase.json` says so in its own header |
| `sarvamula.org` | **a placeholder.** `301 → www.sarvamula.org`, which serves the twelve bytes `coming soon` | served by GitHub Pages (`server: GitHub.com`) from a repo this session cannot see. Neither ShriBuddhi nor JagatTest has a `CNAME`, so the domain is attached elsewhere — `Sarvamula` or `Madhvacharya` are the candidates. |

> **Corrected 26 Sep 2026.** This row used to read *"Live site ·
> `https://sarvamula.org/` (200)"*. The 200 was real and the conclusion was
> wrong: the body is `coming soon`. Checking a status code and not the
> response is the same mistake as reading an `echo` as an upload result, and
> as reading an ambiguous 404 as "absent" — three times now, always by
> trusting a signal that was never about the thing being claimed.
>
> **The Pages path is case-sensitive.** `…github.io/JagatTest/` serves the
> site; `…github.io/jagattest/` is a 404. The repository is `JagatTest`, with
> both capitals.
| Sarvam Document AI | prepaid balance | https://dashboard.sarvam.ai |
| Google AI Studio (Gemini key) | same Google account | https://aistudio.google.com/apikey |
| Hugging Face space | `sarvamulaorg-kamadhenu` | https://sarvamulaorg-kamadhenu.hf.space |

**There is exactly one Google Cloud project.** `sarvamula-org` is both the
Firebase project and the GCP project — Firebase projects *are* GCP projects.
Do not create a second one for storage, for functions, or for the search index.

---

## 2. Service accounts — there are two, and each does a different half

> **Corrected 22 Sep 2026, same day it was written.** The first version of
> this section said `firebase-adminsdk-fbsvc@` was "created automatically by
> Firebase", "used by nothing in this project's CI", and should be left alone.
> That was wrong, and confidently wrong. The IAM page shows it carrying
> **fourteen roles** — Artifact Registry Administrator, Cloud Build Editor,
> Cloud Functions Admin, Cloud Run Admin, Cloud Scheduler Admin, Eventarc
> Admin, Firebase Admin, Firebase Admin SDK Administrator Service Agent,
> Firebase Authentication Admin, Firebase Rules Admin, Pub/Sub Admin, Secret
> Manager Admin, Service Account Token Creator, Service Account User. Nothing
> accumulates fourteen roles by accident. They were granted one at a time,
> over several failed deploy attempts, specifically to make a **Cloud
> Functions deploy** work. The reasoning error was inferring a purpose from a
> name instead of looking at the grants.

Every service account in `sarvamula-org`
(<https://console.cloud.google.com/iam-admin/serviceaccounts?project=sarvamula-org>):

| principal | display name | roles | what it is for |
|---|---|---|---|
| `github-search-index@sarvamula-org.iam.gserviceaccount.com` | github-search-index | 5 — Cloud Datastore Index Admin, Firebase Rules Admin, Secret Manager Admin, Service Usage Consumer, Storage Admin | **the CI account the workflows use today.** Its key is the one in `FIREBASE_SERVICE_ACCOUNT`. Covers the search-index publish, Firestore rules + indexes, and Secret Manager. |
| `firebase-adminsdk-fbsvc@sarvamula-org.iam.gserviceaccount.com` | firebase-adminsdk | 14 — see the correction above | **the deploy account**, built up by hand through repeated failed Functions deploys. Everything a 2nd-gen Functions deploy needs. No GitHub secret holds its key. |
| `1005094356690-compute@developer.gserviceaccount.com` | Default compute service account | Editor | what 2nd-gen functions **run as**. This is the identity that must be able to *read* a function secret at call time. |
| `sarvamula-org@appspot.gserviceaccount.com` | App Engine default service account | Editor | legacy 1st-gen runtime. Not used by anything current. |
| `jagadgurumadhvacharyaadmin@gmail.com` | JagadGuru Madhvacharya | **Owner** | the human account. |

### Neither account can do the whole job

That is the real finding, and it is why the Functions deploy kept failing while
everything else worked:

| | github-search-index | firebase-adminsdk-fbsvc |
|---|---|---|
| publish the search index to GCS | **yes** (Storage Admin) | no |
| Firestore composite indexes | **yes** | no |
| Firestore rules | yes | yes |
| Secret Manager | yes | yes |
| deploy Cloud Functions | **no** | **yes** (11 roles' worth) |

`FIREBASE_SERVICE_ACCOUNT` holds the **github-search-index** key, so
`deploy-firebase-functions.yml` authenticates as the account that cannot deploy
functions — while the account that can sits unused with no key in any secret.

### What to do about it — consolidate onto `firebase-adminsdk-fbsvc`

Not because that name is a good one for a CI account (it is not), but because
of the arithmetic:

* Bringing **github-search-index** up to parity means granting **eleven** roles
  — Artifact Registry Administrator, Cloud Build Editor, Cloud Functions Admin,
  Cloud Run Admin, Cloud Scheduler Admin, Eventarc Admin, Firebase Admin,
  Firebase Authentication Admin, Pub/Sub Admin, Service Account Token Creator,
  Service Account User. (Not the twelfth, *Firebase Admin SDK Administrator
  Service Agent* — a service-agent role that belongs only to the account
  Firebase created it for.)
* Bringing **firebase-adminsdk-fbsvc** up to parity means granting **three**:
  Storage Admin, Cloud Datastore Index Admin, Service Usage Consumer.

Three grants against eleven, and the eleven would be re-deriving by hand a set
that already exists and was already paid for in failed runs. Then put that
account's key in `FIREBASE_SERVICE_ACCOUNT` and there is genuinely **one CI
identity** — which is what was asked for.

Its display name can be changed to something honest (IAM → Service Accounts →
the account → Edit → e.g. "CI — deploys and publishes") without changing the
email address anything refers to.

**How to tell which account a key file is for**, before pasting it anywhere:
open the downloaded `.json` and read its `"client_email"`. That line *is* the
identity — a key for the right account says

    "client_email": "firebase-adminsdk-fbsvc@sarvamula-org.iam.gserviceaccount.com"

Nothing else in the file needs to be looked at, and nothing else in it should
ever be pasted anywhere but the GitHub secret box — `private_key` is the whole
credential. After the switch, every run prints the account it authenticated as:

    Activated service account credentials for: [firebase-adminsdk-fbsvc@***.iam.gserviceaccount.com]

which is the confirmation that the secret was updated, not just saved.

**Rollback**, if a workflow breaks after the switch: generate a fresh key for
`github-search-index` and paste it back into `FIREBASE_SERVICE_ACCOUNT`. A
service-account key's value cannot be read back from the console, so there is
nothing to save beforehand — a new key is always issuable.

**Do not delete either account.** `firebase-adminsdk-fbsvc` is referenced by
Firebase itself; `github-search-index` is the rollback path and, until the
switch is verified, the working one.

---

## 2b. IAM roles — every grant, why it exists, and what proved it was needed

**This is the running record. Add a row here the same day a role is granted.**
Every entry below was established by a run that failed without it, not by
guesswork — which is the only reason it can be trusted.

All of these are on **`github-search-index@sarvamula-org.iam.gserviceaccount.com`**,
granted at
<https://console.cloud.google.com/iam-admin/iam?project=sarvamula-org>.

| role | granted | what needs it | what it looked like when missing |
|---|---|---|---|
| **Storage Admin** | 22 Sep 2026 | `reindex.yml` publishing 215,933 files to `gs://sarvamula-search-index` | `gcloud storage rsync` → 404, which GCS returns for *both* "no such bucket" and "not yours" |
| **Cloud Datastore Index Admin** | earlier | `deploy-firestore.yml` deploying the composite indexes | index deploy refused |
| **Firebase Rules Admin** | earlier | `deploy-firestore.yml` releasing `firestore.rules` | rules release refused |
| **Service Usage Consumer** | earlier | any call that checks whether an API is enabled | 20 Sep 2026: the Firestore deploy failed on Service Usage, which read as a Firestore problem |
| **Secret Manager Admin** | **22 Sep 2026** | reading which function secrets exist; adding a version; a Functions deploy resolving every `defineSecret()` | run 35718541325: `Permission 'secretmanager.secrets.list' denied`, `reason: IAM_PERMISSION_DENIED`. The audit's first version reported all twelve secrets MISSING — they were all present; it simply could not see them. |

### The Cloud Functions roles — an empirical list, not a guess

`deploy-firebase-functions.yml` authenticates as **github-search-index**, which
cannot even list functions. Proved by run 35723735140:

    ✔ Created a new secret version .../RAZORPAY_KEY_SECRET/versions/2
    Error: Failed to list functions for <project>

An earlier version of this section listed six roles from Google's
documentation, marked unverified. **Delete that instinct — the real list was
already in the project**, on `firebase-adminsdk-fbsvc`, arrived at by granting
one role at a time across several failed deploys. It is longer than the
documented six, and the five it adds are exactly the ones a docs page would not
have told you:

| role on `firebase-adminsdk-fbsvc` | why a Functions deploy needs it |
|---|---|
| Cloud Functions Admin | create, update and list the functions |
| Cloud Run Admin | 2nd-gen functions **are** Cloud Run services |
| Artifact Registry Administrator | the container image the build produces |
| Cloud Build Editor | the build itself |
| Service Account User | permission to *act as* the runtime account (`1005094356690-compute@…`) |
| Firebase Admin | firebase-tools' own project calls |
| **Cloud Scheduler Admin** | a scheduled function creates a Cloud Scheduler job |
| **Eventarc Admin** | every 2nd-gen background trigger is an Eventarc trigger |
| **Pub/Sub Admin** | Eventarc delivers through Pub/Sub topics |
| **Service Account Token Creator** | minting tokens for the invoker identity |
| **Firebase Authentication Admin** | the Auth-triggered and user-management paths |
| *Firebase Admin SDK Administrator Service Agent* | **do not copy this one.** A service-agent role, meaningful only on the account Firebase created it for. |

Whichever account ends up being the single CI identity needs the eleven above
plus Secret Manager Admin, Storage Admin, Cloud Datastore Index Admin, Firebase
Rules Admin and Service Usage Consumer. §2 explains why granting three roles to
`firebase-adminsdk-fbsvc` is the short way there rather than eleven to
`github-search-index`.

### Verified 22 Sep 2026, after the switch

`FIREBASE_SERVICE_ACCOUNT` now holds the **firebase-adminsdk-fbsvc** key (three
roles added to it: Storage Admin, Cloud Datastore Index Admin, Service Usage
Consumer). Four runs, in the order §D4 recommends:

| run | result |
|---|---|
| `reindex.yml` probe — 35736560446 | **success.** `Activated service account credentials for: [firebase-adminsdk-fbsvc@…]`, wrote the probe object, `anonymous GET of the published URL returned HTTP 200` → Storage Admin works, bucket still world-readable |
| secrets `audit_only` — 35736563122 | **success.** Full twelve-row table → Secret Manager Admin works |
| `deploy-firestore.yml` — 35736565787 | **success.** `deployed indexes … successfully`, `released rules firestore.rules` → Datastore Index Admin + Firebase Rules Admin work |
| `deploy-firebase-functions.yml` — **35740197469** | **success — the first one ever.** `✔ functions[corpusFile(asia-south1)] Successful create operation.` `✔ Deploy complete!` |
| `deploy-firebase-functions.yml` — **35748527407** | **all eleven functions, Razorpay live.** sendOtp, verifyOtp, whatsappWebhook, runWhatsAppBroadcast, listWorkflows, runWorkflow, createDonation, getDonationStatus, paymentWebhook, corpusFile updated; renderBook created |

So the account switch is confirmed and the search-index, Firestore and Secret
Manager halves are all working under one identity. That is the "there must be
just one" end state, verified rather than asserted.

**Every role in the table above is now proved**, not documented. The
successful deploy enabled and used cloudfunctions, cloudbuild,
artifactregistry, cloudscheduler, run, eventarc, pubsub, storage and
secretmanager, generated the Pub/Sub and Eventarc service identities, uploaded
the source, and created the Cloud Run service — which exercises Cloud Build,
Cloud Run and Service Account User in turn. Nothing in this section is now
taken from a documentation page.

`corpusFile` answered **404 before the deploy and 503 after it** — 503 being
its own designed "CORPUS_BUCKET is not set, the switch is off" response, so the
function is not merely present but executing.

### What it took to get there — three failures, none of them IAM

Worth keeping, because each looked like something it was not:

1. **`Cannot find module '@google-cloud/firestore/build/src/path'`**, reported
   by firebase-tools as *"Functions codebase could not be analyzed
   successfully. It may have a syntax or runtime error"*. Neither a syntax
   error nor in our code: `npm install --omit=optional`, there to skip
   puppeteer's Chrome download, also removed `@google-cloud/firestore` and
   `@google-cloud/storage`, which `firebase-admin` 13 declares optional and
   then requires. Fixed with `PUPPETEER_SKIP_DOWNLOAD=true`.
2. **`unexpected EOF while looking for matching '"'`** — an unterminated
   string in the workflow edit itself. Valid YAML, invalid shell. Hence
   `tools/check_workflow_shell.py`.
3. **`Max instances must be set to 20 or fewer to set the requested total
   CPU`** — a Cloud Run regional CPU cap, not a permission. `corpusFile` asked
   for 40 instances against a global default of 10.

The pattern across all three: the error text named a cause that was not the
cause. Reproducing locally — the same `npm install` plus
`node -e "require('./index.js')"` — found the first in a minute after two
failed deploy cycles had not.

### Non-IAM access grants

| grant | where | why |
|---|---|---|
| `allUsers` → **Storage Object Viewer** | bucket `sarvamula-search-index` | the browser fetches index shards straight from `storage.googleapis.com`; without it the index publishes and is unreadable. This is also what makes search public — see `SEARCH_INDEX.md` §7. |
| `roles/secretmanager.secretAccessor` on each function secret | held by the **functions' runtime** service account, bound per secret | how a deployed function reads a `defineSecret()` value at call time. `firebase functions:secrets:set` adds this binding automatically; `gcloud secrets versions add` does **not**, so `push-firebase-function-secrets.yml` copies the accessors off an existing secret whenever it has to create a new one. Adding a *version* needs nothing — the binding is on the secret. |

### Secret Manager state, measured 22 Sep 2026 (run 35724185990)

| secret | version? | set from a GitHub secret? |
|---|---|---|
| `CASHFREE_CLIENT_ID`, `CASHFREE_CLIENT_SECRET` | yes | no — pre-existing |
| `MSG91_AUTHKEY`, `OTP_PEPPER`, `PAYMENT_WEBHOOK_SECRET` | yes | no — pre-existing |
| `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_APP_SECRET` | yes | no — pre-existing |
| `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET` | yes | **yes — pushed 22 Sep from ShriBuddhi** |
| `GITHUB_DISPATCH_TOKEN` | **no** | no — needs `GH_DISPATCH_TOKEN` on GitHub |

Ten of the twelve exist in Secret Manager with **no corresponding GitHub
secret**, which is worth knowing: they were set up by hand at some point, the
values are not recoverable from anywhere in this project, and
`push-firebase-function-secrets.yml` leaves them alone precisely because a
GitHub secret that is unset is skipped rather than pushed as empty.

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
| `BUDDHI_TOKEN` | PAT for **JagatTest** — "Buddhi" is one of its former names. Used by `promote-to-buddhi.yml`, `reindex.yml`'s pin bump and `sync-firebase-to-jagattest.yml` | same |
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
   **Then write the grant into §2b the same day**, with the error that made it
   necessary. Four of the five roles listed there had to be rediscovered by
   watching a workflow fail, because nobody recorded them when they were
   granted.
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
