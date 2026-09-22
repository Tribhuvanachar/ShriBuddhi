# Prompt: finish the WhatsApp Cloud API setup for Sarvamula

*Written 22 Sep 2026. Paste this whole file into ChatGPT (or any assistant with
current Meta/WhatsApp knowledge). It is self-contained — the reader does not
have the repository.*

---

## What I need from you

The **code is finished and deployed**. What is missing is entirely on the Meta
side, and I am stuck because **I do not have a registered business**. I am one
person running a non-profit Sanskrit text library. I need a concrete,
ordered, do-this-then-that plan for the Meta console, written for someone who
has never done a WhatsApp Business API setup.

Please be explicit about **what is genuinely required versus what Meta merely
recommends**, and about what I can do *without* business verification. Where
Meta's rules have changed recently, say so and give the current behaviour.

---

## 1. What the software already does (all verified working)

Google Cloud project `sarvamula-org`, Cloud Functions 2nd gen, region
`asia-south1`. Deployed and live today.

### The webhook endpoint exists and responds

    https://asia-south1-sarvamula-org.cloudfunctions.net/whatsappWebhook

Verified just now: a `GET` with no `hub.verify_token` returns **403**, and a
`GET` with a wrong one also returns **403**. That is the code working
correctly — it is refusing an unverified handshake, not broken.

Its contract, from the source:

* **`GET`** — Meta's subscription handshake. Returns `hub.challenge` with
  HTTP 200 **only** when `hub.mode === 'subscribe'` **and**
  `hub.verify_token` exactly equals the secret `WHATSAPP_VERIFY_TOKEN`.
  Otherwise 403.
* **`POST`** — verifies `x-hub-signature-256` as an HMAC-SHA256 of the **raw**
  request bytes keyed with `WHATSAPP_APP_SECRET`. Mismatch → 401. Then it
  acknowledges 200 immediately and processes inbound messages, detecting
  opt-out/opt-in intent and updating the sender's profile.

### Sending

* Meta Graph API **v21.0**.
* OTP is sent as an **authentication template**, name **`dge_otp`**,
  language **`en`**. The payload builder handles the fiddly part where the
  code must appear both in the body parameter *and* again as the copy-code
  button parameter.
* There is also a broadcast function for opt-in marketing/announcements.

### The four secrets exist in Google Secret Manager

`WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_VERIFY_TOKEN`,
`WHATSAPP_APP_SECRET` — all four have versions, confirmed by an automated
audit today.

**But their values are unknown to me.** They were set by hand months ago and
are not recorded anywhere. Secret Manager will not display them to me in a
form I can compare against Meta. In particular the **Verify token field in the
Meta app dashboard is currently empty**, which means whatever
`WHATSAPP_VERIFY_TOKEN` holds has never been entered on Meta's side — so the
handshake has certainly never succeeded.

I can overwrite any of these four with a new value through a GitHub Actions
workflow in about two minutes. **Assume I will set fresh values for all of
them** rather than trying to recover the old ones. Tell me if that is the
wrong call.

### Nothing in the website calls WhatsApp yet

The front-end config has `enablePhoneAuth: false`,
`phoneOtpProvider: 'firebase'`, `enableWhatsappBroadcasts: false`. So no real
user can trigger a WhatsApp message today. This is deliberate — WhatsApp is
switched on only once the Meta side works.

The reason WhatsApp matters: an authentication template costs about
**₹0.145** per message in India against roughly **₹0.85** for Firebase's own
SMS. About six times cheaper, and the code arrives with a one-tap copy button.

---

## 2. Exactly what the Meta console shows right now

### Business portfolio — `Sarvamula.Org`

People with access:

| person | note |
|---|---|
| Sanatanavidya Gurukulam (`sanatanavidyagurukulam@gmail.com`) | full access to everything, can delete the portfolio; **2 WhatsApp accounts assigned**; last active 13 Sep 2026 |
| Madhvacharya Jagadguru (`jagadgurumadhvacharya@gmail.com`) | |
| jagadgurumadhvacharya… | |
| Tribhuvan Karanam (me, `shyam.tribhuvan@gmail.com`) | |

WhatsApp account asset: **Sarvamula.Org**, full access.

### System user

**`Sarvamula Backend`**, ID **`61594462042530`**, **Admin access**. Assigned
one business asset: the app **Sarvamula.Org**, full access. There is a
*Generate token* button. I do not know whether a token was ever generated, and
if it was I no longer have its value.

### Phone number

* **+91 89511 62886**
* Display name: **Sarvamula Digital Platform**
* **Phone number ID: `1233981309805986`**
* Status: **not registered.** Two places say so — *"Register your phone number
  to upload a profile picture"*, and on the Message links tab, *"You will need
  to connect the phone number to a WhatsApp Business API Client before
  creating message links."*

### Business profile as currently filled in

* Category: **Non-profit**
* Address: `487/1, 1st Main, Thyagaraja Nagar`
* Email: `sanatanavidyagurukuam@gmail.com`
* Website 1: `https://www.arvamula.orgs/`
* Website 2: `https://www.facebook.com/`
* "Official business account" (blue tick): *Submit request* button, not
  submitted.

> **Two of those are typos I have spotted and will fix before anything else.**
> The email is missing an `l` — the portfolio account is
> `sanatanavidyagurukulam@gmail.com`. The website should be
> `https://sarvamula.org/`, which is live; `www.arvamula.orgs` does not exist.
> The Facebook entry is a bare placeholder. Please confirm whether wrong
> website/email fields here would by themselves cause a verification or
> display-name rejection.

### The app's guided setup — "Connect on WhatsApp"

* **Step 1 · Try it out** — not done.
* **Step 2 · Production setup** — not done. Four sub-tasks:
  * *Configure Webhooks* — **Callback URL blank, Verify token blank.**
  * *Register your WhatsApp phone number* — shown as partially complete.
  * *Add payment to send business-initiated messages* — not done.
  * *Send message* — not done.
* **Step 3 · Business verification** — not started. Labelled
  *"Optional but recommended"*, 2–10 business days, *"Only an admin user can
  complete business verification."*

### The warning I do not understand

On the Configure Webhooks panel:

> ⚠ **Apps will only be able to receive test webhooks sent from the app
> dashboard while the app is unpublished. No production data, including from
> app admins, developers or testers, will be delivered unless the app has been
> published.** *Publish your app*

**This is my single biggest question.** See §4.

### Business verification documents Meta lists for India

GST REG-06 · GST REG-25 · Certificate of Incorporation/Formation · **Udyam
Registration Certificate** · FSSAI License · Business License / Shop and
Establishment License · Utility Bills · Bank Statements.

**I have none of these.** No GST registration, no incorporation, no shop
licence. I have personal utility bills and personal bank statements in my own
name, and a domain (`sarvamula.org`) I own.

---

## 3. My constraints — please do not assume otherwise

* I am an **individual in India**, not a company. No GST, no incorporation, no
  trust/society registration certificate in hand today.
* The project is a **free non-profit Sanskrit text library**. No revenue from
  it. There is a donations flow (Razorpay), not a product being sold.
* WhatsApp is wanted for exactly two things: **login OTPs** to our own users
  who asked for an account, and **opt-in announcements** to people who ticked
  a consent box. No cold outreach, no marketing to strangers.
* Expected volume at launch: **tens of messages a day**, not thousands.
* The phone number **+91 89511 62886** — I need to know whether it is usable.
  It may currently be signed in to the ordinary WhatsApp or WhatsApp Business
  app.

---

## 4. The questions, in the order they block me

1. **Does the app have to be "published"/Live for my webhook to receive real
   events?** The warning above says production data will not be delivered
   while unpublished. If so: what does publishing actually require for an app
   that only uses the WhatsApp Cloud API against its **own** WhatsApp Business
   Account using a **System User token** — does it need App Review for
   `whatsapp_business_messaging`, or is the Live toggle separate from
   permission review? Walk me through the exact toggle and any prerequisite.

2. **What can I do with no business verification at all?** Specifically: can I
   register the phone number, get an authentication template approved, send
   real OTPs to real users, and receive webhooks? What are the exact limits
   (messages per day, number of phone numbers, whether the display name shows
   or the phone number shows)? Is there a time limit after which an unverified
   account stops working?

3. **Verification with no registered business — what is the minimum path?**
   * Can an individual in India obtain a **Udyam Registration Certificate**
     for a non-profit/knowledge project, free and online, and would Meta
     accept it? What exactly do I fill in?
   * Would registering a **Trust or Society** be the more appropriate route
     for a non-profit, and does Meta accept a Trust Deed / Society
     Registration Certificate as "Certificate of Incorporation"?
   * Do **personal** utility bills and bank statements ever satisfy this when
     the business name is not a registered entity?
   * If the display name **"Sarvamula Digital Platform"** does not match any
     document I can produce, does verification fail on the name alone? Should
     the display name instead match whatever I end up registering?

4. **Correct order of operations.** Right now the webhook is unconfigured, the
   number is unregistered, and no token is generated. Which comes first, and
   what breaks if I do them out of order? Specifically: does the phone number
   need to be registered before the webhook subscription will verify, or the
   other way round?

5. **The phone number.** +91 89511 62886 may be active on the consumer
   WhatsApp app. What do I have to do to it first — delete the account in the
   app, wait some period? What is the exact sequence, and is it reversible if
   I change my mind?

6. **"Add payment to send business-initiated messages."** An OTP template is
   business-initiated, so I assume this is required before a single code can
   be sent. What payment methods does Meta accept for an Indian account
   (card? UPI? international card only?), is there a minimum charge, and does
   adding one immediately start billing?

7. **The `dge_otp` authentication template.** I need one approved, named
   exactly `dge_otp`, language `en`, with a copy-code button. Give me the
   exact content to submit, warn me about the things that get authentication
   templates rejected, and tell me how long approval usually takes.

8. **The System user token.** `Sarvamula Backend` has Admin access. When I
   click *Generate token*: which app do I pick, which permissions do I tick
   (`whatsapp_business_messaging`, `whatsapp_business_management`, anything
   else?), and should I choose a token that never expires or a 60-day one? I
   will store the result in Google Secret Manager as `WHATSAPP_TOKEN`.

9. **`WHATSAPP_APP_SECRET`** — confirm this is the **App Secret** from the
   app's Settings → Basic, and not anything to do with the system user or the
   WABA.

---

## 5. What I will do with your answer

I will set fresh values for all four secrets, enter the callback URL
`https://asia-south1-sarvamula-org.cloudfunctions.net/whatsappWebhook` and a
matching verify token in the Meta dashboard, redeploy the functions, and then
flip the site's `enablePhoneAuth` to `true` with
`phoneOtpProvider: 'whatsapp'`.

**Please give me the Meta-side steps as a numbered checklist I can follow
click by click**, flagging at each step whether it can be done now or is
blocked on verification. Where a step depends on something I have said I do
not have, say so plainly and give me the cheapest legitimate way to obtain it
— or tell me to skip it and what I lose by skipping.

Do not give me code. The code is done.
