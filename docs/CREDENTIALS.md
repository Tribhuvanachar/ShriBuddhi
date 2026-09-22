# Where the API keys are, and how to spend money

Written 22 Sep 2026, after a session was wasted concluding the paid
pipelines were "blocked on credentials". They were not. Nothing about this
needs asking again — it is all here.

## The short answer

**There are no API keys in the working container, and there should not be.**
Every paid engine runs inside a **GitHub Actions workflow** on
`Tribhuvanachar/ShriBuddhi`, and the keys are **repository secrets** that only
the runner sees. Searching the container's environment for `SARVAM_API_KEY`
finds nothing, and that is the design working, not a fault.

To spend money you do not need the key. You dispatch the workflow.

## Which secret lives in WHICH repo

This is the part that matters and the part that is easy to get wrong. The
secrets are **split across two repositories**, deliberately:

| engine | secret | repo that holds it | verified |
|---|---|---|---|
| Sarvam Document AI | `SARVAM_API_KEY` | **ShriBuddhi** (private) | run log shows `SARVAM_API_KEY: ***` |
| Google Cloud Vision | `VISION_API_KEY` | **ShriBuddhi** | — |
| Gemini, all uses | `GEMINI_API_KEY` | **JagatTest** (public) | JagatTest run 35518574290 shows `***`; a ShriBuddhi run on 22 Sep showed it **empty** |
| writing back to the private repo | `SHRIBUDDHI_TOKEN` | **JagatTest** | used by `gemini-resolve-conflicts.yml` |

**Gemini work runs from the public repo on purpose.** JagatTest's
`gemini-resolve-conflicts.yml` states the reason in its own header: *"Actions
is free and unlimited on a public repository and capped at 2,000 minutes a
month on a private one. Nothing sensitive is committed here: the text arrives
from the private repo and leaves for it."*

So a Gemini workflow belongs on **JagatTest**, clones ShriBuddhi with
`SHRIBUDDHI_TOKEN`, and pushes the result back. ShriBuddhi has six `gemini-*`
workflows and **not one of them has ever run** — they cannot, the key is not
there. Do not add a Gemini workflow to ShriBuddhi expecting it to work; that
mistake cost a failed run on 22 Sep.

Sarvam and Vision run on ShriBuddhi, where their keys are.

`admin/js/ocr-studio-core.js` states the same mapping in its `ENGINES`
table — each entry carries `runsIn: 'workflow'` and a `where:` naming the
workflow and the script it calls. That table is the canonical answer and is
the first place to look.

Tesseract is the exception: `runsIn: 'browser'`, no key, costs nothing.

## How to actually dispatch one

`gh` is **not installed** in the container. Use the REST API; the session's
`GITHUB_TOKEN` is already authorised for it (verified: `POST …/dispatches`
returns `204`).

    # find the workflow id once
    curl -s -H "Authorization: Bearer $GITHUB_TOKEN" \
      "https://api.github.com/repos/Tribhuvanachar/ShriBuddhi/actions/workflows?per_page=100" \
      | python3 -c "import json,sys;[print(w['id'],w['path']) for w in json.load(sys.stdin)['workflows']]"

    # dispatch it — Content-Type is REQUIRED, a missing one gives 415
    curl -X POST \
      -H "Authorization: Bearer $GITHUB_TOKEN" \
      -H "Accept: application/vnd.github+json" \
      -H "Content-Type: application/json" \
      https://api.github.com/repos/Tribhuvanachar/ShriBuddhi/actions/workflows/<ID>/dispatches \
      --data-binary @body.json

`ocr-sarvam.yml` is workflow id **356671665** on ShriBuddhi. Its body:

    {"ref":"main","inputs":{
      "pdf_url":"…","pages":"300-309","work_slug":"…",
      "language":"sa-IN","output_format":"html","mode":"dry-run"}}

**`mode` defaults to `dry-run`, which counts pages and spends nothing.**
`real-run` bills the prepaid balance at dashboard.sarvam.ai. Always dry-run
an unfamiliar range first; the run prints the page count it would send.

Watch it:

    curl -s -H "Authorization: Bearer $GITHUB_TOKEN" \
      ".../actions/workflows/<ID>/runs?per_page=3"

## The browser tools are different — they are BYOK

`js/gemini.js` reads its key from `localStorage["dge_gemini_api_key"]`, typed
in by whoever is using the page. Nothing is stored in the repo. BrahmaBuddhi's
admin pages go further: they are rendered through bhumandala's BYOK loader in
an iframe `srcdoc`, which is why that repo's `admin/js/keys.js` diverged from
this one's for a while.

`admin/config/keys.json` is **not** an API key file. It holds the passkeys for
the admin gate, and `admin/js/keys.js` says so plainly: "a courtesy latch …
the keys live in a public repository and in the page source". Nothing
sensitive belongs behind it.

The Firebase `apiKey` literal in `js/config.js` is likewise not a secret —
Firebase web API keys are public identifiers, and the file says so.

## What this means in practice

* Do not look for a `.env`. There isn't one and there shouldn't be.
* Do not ask for keys to be pasted into a session. They never need to be.
* A container with no keys can still spend money, through Actions.
* The one thing a dispatch cannot do is run when the secret is unset on the
  repo — `ocr-sarvam.yml` then does a dry run and sends nothing, rather than
  failing. A run that reports 0 pages sent may mean a missing secret.

## Costs, measured from `admin/config/spend_report.json`

| engine | rate | basis |
|---|---|---|
| Sarvam | ₹0.440 / page | ₹9,440.20 over 21,455 pages |
| Vision | ₹0.132 / page | ₹5,443.91 over 41,242 pages |
| Gemini | ₹0.0517 / page | ₹79.39 over 1,536 pages |

Use the ledger's own rate, not an estimate. A full-corpus Gemini proofread of
what remains is 39,706 pages ≈ **₹2,052**, not the ₹3,241 quoted earlier from
an estimate.
