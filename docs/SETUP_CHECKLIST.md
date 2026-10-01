# Setup checklist: exactly what to click (1 Oct 2026)

Repository: https://github.com/Tribhuvanachar/ShriBuddhi

## 1. Secrets and variables (once)

| Name | Kind | Where | What it is |
|---|---|---|---|
| `PARABUDDHI_TOKEN` | secret | https://github.com/Tribhuvanachar/ShriBuddhi/settings/secrets/actions | done |
| `SUPERADMIN_EMAILS` | variable *or* secret | https://github.com/Tribhuvanachar/ShriBuddhi/settings/variables/actions (the **Variables** tab) | comma-separated addresses of the people who get the Sunday report. Either tab works; both are read. |
| `REPORTS_EMAIL` | variable | same Variables page | who gets the nightly reader-reports digest; if blank, `SUPERADMIN_EMAILS` is used |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | secrets | the Secrets page | the mail account the workflows send *from* (below) |
| `REPORT_TRIAGE` | variable | Variables page | set to `off` to stop the nightly report sorting; anything else or unset = on |

**What SMTP is.** SMTP is how a program sends an e-mail through a mail account. GitHub cannot send mail by itself, so
the workflows log in to an ordinary mailbox and send from it. Nothing else is needed; no paid service.

**Easiest: a Gmail account used only for this** (e.g. a new `sarvamula.reports@gmail.com`):

1. https://myaccount.google.com/security → turn on **2-Step Verification** (Google requires it for the next step).
2. https://myaccount.google.com/apppasswords → App name `ShriBuddhi` → **Create** → copy the 16-letter password.
3. On the Secrets page → **New repository secret**, five times:
   `SMTP_HOST` = `smtp.gmail.com` · `SMTP_PORT` = `587` · `SMTP_USER` = the Gmail address ·
   `SMTP_PASSWORD` = the 16-letter app password (no spaces) · `SMTP_FROM` = the same Gmail address.

Without these the reports are not lost: each Sunday and each night the report is filed as an issue labelled `watch-report`
at https://github.com/Tribhuvanachar/ShriBuddhi/issues?q=label%3Awatch-report and says e-mail was not sent.

## 2. Firebase: authorised sign-in domains (so readers can sign in on Jagat)

https://console.firebase.google.com/project/sarvamula-org/authentication/settings → tab **Authorized domains** →
**Add domain**: Jagat's domain(s). The sitemap says the site is `sarvamula.org`, so add `sarvamula.org` and
`www.sarvamula.org`; also `tribhuvanachar.github.io` if Jagat is also served from GitHub Pages. If a domain is missing,
Google sign-in on that site fails with "auth/unauthorized-domain".

## 3. Clean up branches (https://github.com/Tribhuvanachar/ShriBuddhi/actions/workflows/cleanup-branches.yml)

Click **Run workflow** (right side). Fields:

* **groups** → type one or more of `verified`, `superseded`, `decide` (comma-separated).
* **confirm** → type `DELETE` (leave blank for a preview).
* **dry_run** → tick it for a preview that only lists, untick to actually delete.

What the groups mean (the lists are in `config/cleanup/branch-plan.json`):

* **verified**: safe, the content is already on `main`. 94 `ocr-staging/<book>` branches (every file on them is on `main`'s
  `data/ocr_staging/`, identical or older), plus `catalogue-repair` and `claude/nyaya-sudha-json-issue-12rcx6` (already merged).
  **Action: run it with `verified`, dry run first, then for real.**
* **superseded**: a newer or equivalent copy exists, so these are low risk but not provably identical. The older frozen
  copies of OCR runs (`buddhi-archive/ocr-staging-*`), the two `gemini-enrich/*` runs, seven old `claude/*` branches that each have a
  `buddhi-archive/claude-*` twin, and `kavya-dist`, `wordnet-dist`, `sandhi-dist` (that data is now in `data/` on `main`; each has a
  `buddhi-archive/*-dist` twin). **Action: dry-run `superseded`, glance at the list, then run it.**
* **decide**: nobody has decided; may hold the only copy of something. 34 branches: the other `buddhi-archive/*` snapshots,
  `recover/tattvavada-structure`, `audio-staging`, `genie-asr-audio-seed`, `migrate-purana-from-bhumandala`,
  `claude/ekadashi-tithi-code-analysis-mmqm89`, `claude/bhumandala-dge-migration`, `claude/rv-pratishakhya-krama-migration`.
  **Action: leave alone until you say, branch by branch, which to drop.** (Dry-run it to see the full list.)
* **keep**: never deleted whatever you type: `main`, `search-dist`, `nightly/library-sync`, `dv-cache-dist`,
  `dasa-sahitya-local-dist`, and the working branch.

## 4. The other buttons

| Do this | URL | Fields |
|---|---|---|
| Rebuild `_sandhi`, `_sandhi_wide`, `_padaccheda` (also runs by itself on the 2nd of every month, 03:00 IST) | https://github.com/Tribhuvanachar/ShriBuddhi/actions/workflows/build-padaccheda-sandhi.yml | leave defaults, **Run workflow**; it opens a pull request |
| Saṃsādhanī in Docker, pilot | https://github.com/Tribhuvanachar/ShriBuddhi/actions/workflows/scl-pilot.yml | verses `150`, **Run workflow**; read the run summary |
| Weekly source watch, now | https://github.com/Tribhuvanachar/ShriBuddhi/actions/workflows/watch-sources.yml | blank = all |
| Nightly reader-report sort, now | https://github.com/Tribhuvanachar/ShriBuddhi/actions/workflows/triage-reports.yml | tick *dry_run* to preview |
| Publish ShriBuddhi → Jagat | https://github.com/Tribhuvanachar/ShriBuddhi/actions/workflows/publish-to-jagat.yml | tick **push** to publish; unticked is a dry run |

## 5. What "Docker run in Actions" means (Saṃsādhanī bulk)

Saṃsādhanī is a toolkit hosted on one university server. For 95,000 verses that server is too slow and not ours to hammer.
The same toolkit is packaged as a Docker image (a ready-to-run copy of the program). A GitHub Actions job can start that image on
GitHub's own machine for the length of the job, then talk to it at `localhost`: fast, free, no load on Hyderabad. The pilot above
does exactly that for 150 verses and prints its accuracy next to Vidyut's. If the pilot is good, the next step is a bulk run that
does the same over the whole corpus in slices and opens a pull request with the sidecars. **No setup from you beyond clicking Run.**

## 6. Reader reports: how they flow

1. A reader taps **Report a problem** (footer, the word popover's ⚑, the typo form, or "report as missing"). The form collects
   the page, library path, verse or word, what was on screen, and a screenshot.
2. **Signed in**: the report is saved in Firestore (`reports/`). **Not signed in** (or save fails): the reader's own mail app opens
   pre-filled, subject `[DGE-REPORT][category] feature — subject`, to the contact address. (Give that mailbox a filter on the
   subject prefix `[DGE-REPORT]` and a label per category and they sort themselves.)
3. **Every night, 11:00 pm IST**, `triage-reports.yml` reads the new Firestore reports, files each in a queue
   (**content** = missing text, wrong mapping; **proofreader** = typos; **linguistics** = dhātu/śabda/sandhi/padaccheda;
   **admin** = the rest) with a priority P1–P4 (3+ reports of the same thing or from an admin = P1), writes that back, and sends
   **one e-mail** to `REPORTS_EMAIL` listing the queues top-down. No night with new reports, no mail.
4. In ShriBuddhi, `admin/reports.html` shows them with the screenshots, filterable by queue and priority, and you mark them resolved.
5. **No AI is involved anywhere**: the rules are in `tools/watch/triage_reports.py`. Switch the nightly job off with `REPORT_TRIAGE=off`.

## 7. The six importers that still write straight into `data/`

| Workflow | Fetches from | Writes to | Suggested home |
|---|---|---|---|
| `ingest-gretil-bulk` | GRETIL | `data/purana/...`, `data/vedanga/...` (registry `importers/gretil_bulk.json`) | raw TEI → ParaBuddhi first (like Kavya), then stitch |
| `darshanas` | GRETIL (Nyāya, Mīmāṃsā) | `data/darshana/...` | same |
| `ingest` | importer scripts for Bhāgavata, Rāmāyaṇa, Mahābhārata, Harivaṃśa, smṛtis, Raghuvaṃśa… | `data/purana`, `data/itihasa`, `data/smriti_dharma`, `data/kavya_alankara` | raw to ParaBuddhi first; Kavya ones already covered by `import-kavya` (retire the overlap) |
| `ingest-commentaries` | valmikiramayan.net, sacred-texts (Ganguli), GitaSupersite, Shankara bhāṣya sources | `data/itihasa/...`, `data/darshana/vedanta/advaita/shankara_bhashya` | raw to ParaBuddhi first |
| `import-dasa-sahitya` | madhwafestivals.com, dasasahitya.net, meerasubbarao | `data/Tattvavada/Itara/DasaSahitya` | raw to ParaBuddhi first |
| `vedavani-extract` | VedaVaNi audio | audio files, PR | audio is not text; a different store (the archive.org upload path), decide |

Each needs the same one-step change `import-kavya` already has (a "Land the raw fetch in ParaBuddhi first" step). Say which to convert.
