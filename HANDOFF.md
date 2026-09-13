# HANDOFF — for the next Claude Code session (written 7 Sep 2026, ~1:20 pm IST)

Two sessions end here: `claude/copyleft-licensing-dg-zmk9ac` (6 Sep, the long one) and
`claude/handoff-pending-review-o4cvmf` (6–7 Sep, this one). Everything both did is merged to `main`
(last merge 923d66cb); nothing lives only in chat. This file says where the state is, what is pending, and the
standing rules. Read it first, then the files it points to. Delete or rewrite it when it is stale.

## 1. Paste-ready opening prompt for the new session

> Read HANDOFF.md at the repo root, then the status files it names, and continue the pending items in the
> order I give you. Standing rules in HANDOFF.md §3 apply to everything. Do tasks end to end; report times in IST;
> Playwright screenshots before merging any UI change; merge to main by the §3 procedure.
> Start with: (1) whatever I report from the phone about the new reader, chandas reports, dhātu chips or the
> declension generator; (2) the Firebase Hosting deploy once the `FIREBASE_SERVICE_ACCOUNT` secret exists;
> (3) Kamadhenu Phase 8 (IndicF5 fine-tune config + CPU dry run, no training, then the Experiment A cost card).
> Ask me only for decisions that are mine (money, DNS cutover, publishing, deleting data).

## 2. Where the state lives (read these, in this order)

| What | File |
|---|---|
| Everything done 6–7 Sep, with numbers and known limits | `dge/PENDING.md`, section "Pending on this session / next Claude session" — the top three entries (7 Sep scholar features; 7 Sep ten-point reader review; 7 Sep reader declutter) |
| Kamadhenu TTS programme — phases, numbers, human actions | `kamadhenu/KAMADHENU_STATUS.md` (+ `kamadhenu_dataset/WHAT_I_NEED_TO_DO.md` for the lead's view) |
| Kamadhenu Space (ZeroGPU) deployment + measurements + the ×1.5 GPU-duration accounting | `kamadhenu_dataset/DEPLOYMENT_REFERENCE.md` §2, `kamadhenu_dataset/space_measurements.json` |
| Firebase / accounts / hosting migration state | `dge/FIREBASE_SETUP.md` §0, `dge/GO_LIVE_ARCHITECTURE.md` |
| Vṛtta reports (data + builder + page) | `dge/data/vedanga/chandas/reports/manifest.json`, `tools/chandas/build_chandas_reports.js`, `dge/js/chandas-report.js`, `dge/js/chandas-page.js`, `admin/config/chandas-features.json` |
| Dhātu occurrence index | `dge/data/vedanga/vyakarana/dhatu_prayoga/manifest.json`, `tools/build_dhatu_prayoga_index.py` (its docstring is the design note) |
| Any-stem declension | `dge/js/shabda-gen.js` (+ `subanta-steps.js`, `dge/wasm/vidyut/`) |
| Library curation (display-only moves, labels) | `admin/config/library-overrides.json` |
| Role-based content access (create roles, gate paths, preview-as-role) | `admin/access-control.html`, `dge/js/role-access.js`, `dge/firebase/firestore.rules` (`config/{docId}`), `dge/FIREBASE_SETUP.md` §0.3 |
| Donations/payments/supporters (Phase 1 foundation, no gateway chosen yet) | `dge/PAYMENTS_SETUP.md`, `dge/firebase/functions/lib/{donation-core,payment-state,payment-providers,receipt-core,email-providers}.js`, `index.js`'s `createDonation`/`paymentWebhook`/`getDonationStatus` |
| Upaniṣad ṭippaṇī OCR, Chandas Gemini workflow, Sāroddhāra | `dge/data/ocr_staging/upanishad_tippani/<book>/summary.json`, `kamadhenu_dataset/chandas_gemini_review.md`, `tools/saroddhara/` |

## 3. Standing rules from the lead (non-negotiable)

- **Merging**: fetch `origin/main` → temp branch → `git merge --no-ff <feature>` → `python3 -m pytest tests/`
  (349) + `python3 tools/audit_library.py` + `python3 tools/validate_data.py` → push temp:main → ff-only sync
  the feature branch → delete temp → push feature. Playwright screenshots before merging any UI change
  (the `pip install playwright` + `/opt/pw-browsers/chromium` recipe in this session's scratch scripts works;
  serve the REPO ROOT, not `dge/`, or `admin/config/*` overrides don't load; set
  `sessionStorage.dge_vandana_passed=1`, `localStorage.has_seen_welcome=true`, `dge_tour_seen=1`,
  `dge_onboarded=true` to skip the gates).
- **Commit trailers, exactly**: `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>` and the session URL
  line; never put a model identifier in code, docs, PR text or commit bodies.
- **Money**: no Gemini API call without a ₹ estimate and a go-ahead (the lead has no API credits; Gemini is used
  through the Android app with paste-back packs). No paid GPU/cloud spend without a cost card and approval.
  ZeroGPU on the PRO Hugging Face account is within budget. Vision API is approved.
- **Training**: DO NOT TRAIN A MODEL until the lead approves an experiment card. Base model = IndicF5 (MIT);
  Vāgdhenu is the benchmark only; F5-TTS weights (CC-BY-NC) are excluded.
- **Secrets**: never print or commit secret values; tokens live in GitHub Actions secrets (`HF_TOKEN`,
  `FIREBASE_*`) and are used only inside workflows. `admin/config/keys.json` is never echoed.
- **Data**: never silently delete or overwrite; never fabricate content; every claim about audio/text comes
  from a measurement or the lead's own words. Speaker of all reachable recordings = the lead (3BHU1), consent recorded.
- **Time**: report in IST (`10:30 am IST`), convert from the UTC that git/Actions/logs use.
- **UI taste, from this session's reviews**: the verse comes first (chrome minimal, first card near the top);
  two themes only (Vandana dark default, Traditional light); accordions with ▾/▴ for menu sections; the
  verse card carries only the verse; layouts stay one body-class switch (`reader.html`/`app.html` are thin
  entry pages, never copies).

## 4. What this session shipped (7 Sep 2026) — the short version

1. **Reader declutter** (index.html 4.66.0): search row in the top bar between an icon-only Library button and
   ☰; sticky reading card removed, read-along highlight lives in the active verse card; credit line gone;
   compact header; Display sheet accordions; two themes; Screen section (full screen, wake lock).
2. **Ten-point review**: chandas engine now splits on ASCII `|` and `<br>` and drops उवाच speaker lines (the
   Prahlāda Nṛsiṃha stotra scans Vasantatilakā); one काव्यम् in the library tree, Prahlāda stotra under
   Sarvamūla स्तोत्राणि (display-only moves); verse card = verse only with pāda line breaks from the engine
   (2 lines for anuṣṭubh-length pādas, 4 for longer); grouped nav rail with Chandas/Uṇādi/Phiṭ/Liṅgānuśāsana/
   Gaṇapāṭha/Rūpasiddhi and the rail mounted on those pages; pinned Library ignores outside taps and docks as a
   resizable pane on ≥760 px; no saved-password prompt on the search box (API-key inputs are text until
   focused); copy-guard on the reading pages.
3. **Vṛtta reports** on chandas.html: per-grantha, library/branch, per-vṛtta, leaderboards; precomputed (1 min,
   Node runs the browser engine) + in-browser regenerate with progress/ETA; feature gating via
   `admin/config/chandas-features.json` and the page's super-admin panel.
4. **Dhātu occurrences**: 912,115 exact hits of 251,597 nameable forms; badges + examples on prakriya/krdanta,
   usage sort on dhatu.html, chips under every verse card in the reader (bidirectional links). 80 MB of data.
5. **Any-stem declension** on shabda.html (`?gen=<stem>&l=P|S|N`), and the reader's word tools always offer a
   table.
6. **Kamadhenu Space**: GPU request lowered to 60 s (ZeroGPU bills ×1.5 on this hardware, so 120 s reached
   visitors as "180 s requested"); both engines re-verified; measurements recorded. The lead's own verdict on
   the IndicF5 zero-shot trial: voice ~70 % similar, words unintelligible — expected for an untrained base
   model on chant; this is the "before" sample for Phase 8.
7. **Library drawer, six phone reports** (index.html 4.67.0, evening): the drawer's right edge resizes on every
   screen size (200 px–95 vw on a phone, grip pill on the edge); `rv1.1` / `rv1` jump to the first mantra of
   that sūkta/maṇḍala (a partial dotted id resolves as a prefix, core.js `dgeResolveQuickJumpTarget`);
   the quick-jump box is a typeahead over every folder and text (slug, label and its HK transliteration;
   ↑/↓/Enter; folder → drilled category view, text → reader, "Search all texts for …" as the last row);
   "Browse" → "View"; the global search closes the drawer first and its bar wraps inside a phone screen;
   the list view is paged at 25 (10/25/50/100 from the page bar, above and below the list, remembered per
   device) and nothing forces single view on large granthas any more — a Ṛgveda maṇḍala opens as a paged list.
   Jumps (quick jump, search hit, audio auto-advance) turn to the page holding the verse (`dgeListPageFor`).
8. **Kamadhenu Phase 8 done** (`kamadhenu/training/`, README there): exporter, vocab, checkpoint converter, config,
   launcher, A/B renderer, and the CPU dry run executed on the real pilot audio (re-fetched from Drive into the
   gitignored `kamadhenu_dataset/incoming_audio/`). The lead now has `kamadhenu/docs/EXPERIMENT_A_CARD.md` to approve:
   ~1–1.7 h on a 24 GB card, ₹30–95 estimated, cap ₹185. Nothing trained, nothing rented.

9. **Short URLs, shareable verses, grouped verse sheet, daily vandana** (index.html 4.68.0, evening): `dge/js/shortcuts.js`
   is the one grammar for `?rv1.1.3`-style addresses (13 keys: rv av avp ts vs sv smv rgv pns bhp mbh rm hv; docs/SHORT_URLS.md;
   `tests/test_shortcuts.py` resolves every key's example against the real data); the reader resolves a bare token, keeps the
   short form in the address bar and writes it back as you read (`dgeSyncUrl` on selection and paging); the landing page
   forwards a bare token; `tools/shortcuts/user-site-index.html` is the file for a future `tribhuvanachar.github.io` repo
   (the root user site is a 404 today). `dge/js/share.js`: every Share / Copy carries the taxonomy crumbs, the verse reference
   and the canonical link; the verse sheet (contextual-actions.json/js) is grouped Mark / Share this verse / Study with
   Share link, Copy link, Bookmark. Vandana: once per device per day (`dge_vandana_day`) and again at every sign-in
   (user-auth.js `dgeVandanaAfterSignIn`); "Meet the Founder" in the Explore menu; tapping the portrait itself offers flowers.
10. **Kamadhenu Experiment A done** (approved 6:20 pm IST, cap ₹185, 24 GB; four HF Jobs on `l4x1`): 1 pip conflict, 2 EMA
   key layout (IndicF5's file is the Hub wrapper's dict `ema_model._orig_mod.*` + `vocoder.*`), 3 fp16 diverged (NaN),
   **4 bf16 healthy** — 3,060 updates in 20.5 min, loss 0.73→0.66, real A/B renders. Spend ≈ ₹154. Results in
   `SarvamulaOrg/kamadhenu-voice-a` + artifact on run 34139626712 + `kamadhenu/reports/experiment_a/`. Duration ratio is
   NOT a discriminator for F5 (fixed by the reference/text ratio) — the lead's ear decides. `kamadhenu-hf-job-logs.yml`
   prints any HF job's log by id.

11. **SEO architecture** (docs/SEO_ARCHITECTURE.md, evening): `tools/seo/` turns dge/data into a crawlable static tree —
   one HTML page per section (16,977 pages, 726,698 units, ~0.9 GB, 2.5 min), category indexes, canonical tags, unique
   titles/descriptions, breadcrumbs + BreadcrumbList/WebPage/CreativeWork JSON-LD, prev/next, sitemap index, robots;
   `tools/seo/validate_seo.py` passes clean (0 duplicate titles, 0 orphans). Generated pages are a deploy artifact
   (`.github/workflows/seo-pages.yml`), never committed. **Waiting on the lead**: Settings → Pages → Source → GitHub
   Actions, then run the workflow with deploy=true, then `canonicalLive: true` in admin/config/seo.json. Licensed corpora
   (GO_LIVE §2.2) are excluded by prefix until classified.

## 5. Pending, in priority order

1. **Lead's feedback on the 7 Sep work** — expect it from the phone. Likely follow-ups: chips in App layout are
   hidden until a card is expanded (deliberate); a search phrase spanning a pāda break won't match (known);
   the Display sheet's "Reading View" header shows no current value until a view is chosen.
2. **Pilot transcripts were wrong for 1 pair in 4 — Experiment A must be rerun on verified data (8 Sep, 12:45 am IST).**
   Whisper small + medium runs cross-matched against every verse of the work (final, 1:55 am IST): 93 confirmed,
   38 wrong verse (all 10 Tīrtha Prabandha files are Paścima not Dakṣiṇa; 28 Saroddhāra files +1/+2 verses or
   next part), 5 inconclusive (need a human ear). Gate: `export_f5_dataset.py --require-verified
   kamadhenu/reports/pilot_transcript_check/crossmatch.json [--accept-remap]` → 93 or 131 pairs. Attempt 4
   trained with 28 % wrong pairs; it stands as an engineering proof only. Rerun needs the lead's cost go-ahead
   (≈ ₹150–185 on l4x1). Then apply the same check to the Gītā recordings.
3. **Vedavani (Hugging Face) Rigveda clips — lead's decision on the mirror (7 Sep, 11:30 pm IST).**
   `sanganaka/Vedavani-Dataset` (IIT KGP, ACL 2025, Apache-2.0; audio = Veda Prasara Samiti group recitation from
   archive.org, Public Domain Mark) has 20,782 per-pāda Rigveda WAVs, 16 kHz, 36.6 h. NOT the VedaVaNi app
   (`tools/vedavani/`). Built `tools/vedavani_hf/vedavani_corpus.py` + `vedavani-hf-corpus.yml`; committed
   `kamadhenu_dataset/external/vedavani_hf/manifest.csv.gz` mapping 20,483 clips (98.6 %) to DGE ṛk ids, covering
   10,440 of 10,552 ṛks; 3 random clips verified end-to-end (HTTP 200, RIFF, sha256, duration). Audio stays out of
   git. Recommended: run the workflow in `mirror` mode into `SarvamulaOrg/vedavani-dataset-mirror` (private) so
   training pulls from a repo we own; the lead has not yet said yes. Also pending: listen to the three sample clips
   sent in chat (group chant, not a single voice — style reference, not a Kamadhenu voice).
4. **SEO proof-build — validator now passes locally after a real fix (7 Sep, 11:55 pm IST):** the builder
   used to write its catalogue over `/dge/index.html` and `/dge/kavya/index.html` (the app shell and the Kāvya
   reader). Now stamped pages + refuse-to-overwrite + reserved URLs (`/dge/texts/`, `/dge/kavya/texts/`). CI
   proof-build re-dispatched with deploy=false; deploy=true still waits on the artifact-size question (see PENDING).
5. **Firebase: Firestore rules + indexes are LIVE (8 Sep, ~11:56 am IST) after four real, distinct root
   causes.** In order: (1) no service-account secret at all — fixed by adding `FIREBASE_SERVICE_ACCOUNT`;
   (2) the service account missing Google Cloud IAM roles for control-plane deploys — fixed by adding
   "Firebase Admin" and "Firebase Rules Admin" in Cloud Console → IAM & Admin → IAM; (3) `FIREBASE_PROJECT_ID`
   held `sarvamula` instead of `sarvamula-org` (found via a diagnostic step reporting the secret's length/shape
   without ever printing it — 9 chars, didn't end in `-org`) — fixed by the lead correcting the secret;
   (4) a redundant single-field index in `firestore.indexes.json` (`users`/`lastLoginAt`) that Firestore
   rejects when declared as composite — fixed in the repo, removed. Full writeup in `dge/FIREBASE_SETUP.md`
   §0.1. `Deploy — Firebase Hosting` (channel=preview) and `Deploy — Firebase Functions` both dispatched
   right after; check their outcome and, once hosting preview is confirmed, verify Google sign-in and a
   real profile write on it before the lead decides live channel / DNS cutover.
   `.github/workflows/push-firebase-function-secrets.yml` is ready for the WhatsApp/MSG91/OTP_PEPPER secrets
   once the lead works through `dge/FIREBASE_SETUP.md` §0.2's ordered checklist (Meta Business setup is
   the lead's part; the rest is mine once each prerequisite lands).
   Security note left for the lead: the service-account JSON passed through this chat session to get set up —
   worth generating a fresh key and deleting the old one from Firebase Console → Project settings → Service
   accounts now that the deploy is confirmed working, as routine hygiene.
   Unrelated, noticed while re-running the JS suite: `dge/firebase/tests/user-auth.test.js` "phone OTP —
   Firebase SMS transport → confirms the code through the confirmation result" fails on a clean checkout
   (pre-existing, not caused by anything this session touched, not part of the Python merge gate) — worth a
   look next time that file is touched.
6. ~~Verified-email capture~~ — **done 7 Sep 2026**: `user-auth.js` stores only provider-verified emails
   (`dgeVerifiedEmail`) and captures a later-verified one on the next sign-in; `firestore.rules` `emailOk()` /
   `emailVerifiedFlagOk()` enforce it on create and self-update; Manage Users exports the verified list as CSV
   (`dgeExportVerifiedEmails`). 47 rules tests (emulator runs in the sandbox: `npm run test:rules`) + 196 unit
   tests pass. Not screenshotted: the export button needs a signed-in super-admin. Rules take effect only when
   the lead publishes them to the live project (Firestore is not created yet).
7. **Kamadhenu Experiment A (Phase 12)** — waits on the lead's decision on `kamadhenu/docs/EXPERIMENT_A_CARD.md`.
   On approval: rent one 24 GB card, `HF_TOKEN` + `KAMADHENU_VRAM=24GB`, run `launch_experiment_a.sh --dry-run`, then
   the real run (resumable, 150-min cap), bring back `export/`, `eval/`, `train.log`, and give the lead the 13 A/B pairs
   with the duration ratios. Independent of that: Phase 13 evaluation script + HUMAN_REVIEW.csv.
8. **Scholar features, next steps**: (a) Vedic metre detection is still the data's declared `chandas`, not the
   engine (PENDING.md's long-open item); (b) dhātu index: sandhi-fused forms are uncounted, `_morph` records
   carry no dhātu code, so the intellisense popover links to shabda tables but not to dhātu cells — a
   lemma→code side table would close that; (c) `vidyut` Python wheel (19 MB) timed out through the proxy —
   with it, `tools/` could pregenerate declension tables and verify the analogy paradigms offline; (d) a
   "differs from the paradigm in cells …" diff on shabda-gen is an easy scholar win.
9. **Upaniṣad ṭippaṇī ×7 + Tantrasāra**: Vision + Tesseract done for all 3,453 pages; LABELS/NEW/DIFF packs
   regenerated; importer into the mapped layers waits for the lead's Gemini answers.
10. **Chandas engine**: ārṣa triṣṭubh/jagatī classification, अनुष्टुभ् alias, re-ingest Gemini Parts C/D, harvest
   lakṣaṇa verses for the remaining fixtures (184 unresolved metres without examples). The new reports list
   93 DB vṛttas never attested in the library — a ready-made target list.
11. **Sāroddhāra leftovers**: master defects (11.2.37/38, 10.99.34, 10.99.35), 122 extra-beyond-index verses,
   287 refs not in DGE, reindex for backlinks.
12. Waiting on the lead: Śrīpādarāja Aṣṭottara-śata-nāmāvali text (108 names); listen-list answers.
13. Long-paused (Gemini credits): Vasu SK English (5 batches), Lakṣmī Vyākhyā pilot; Grantha data overhaul pilot.

## 6. Gotchas learned this session

- `core.js` checks `<meta name="dge-html-version">` against `DGE_EXPECTED_HTML_VERSION`; bump both on any
  index.html structure change or every reader shows the "cached page" banner.
- `menu.js renderThemes` re-parents theme rows from a config; anything that wraps them (accordions) must
  survive that — it now appends within the current parent.
- `library.json` grouping is by path segments; `admin/config/library-overrides.json` `moves` rename display
  paths without touching real ones (`config.js` and deep links use real slugs).
- ZeroGPU: `@spaces.GPU(duration=N)` is billed as N × `duration_factor` (1.5 on sm_120); `KAMADHENU_GPU_SECONDS`
  overrides the default 60.
- The interlink workflow (`.github/workflows/interlink.yml`) now rebuilds the sūtra-prayoga index, the dhātu
  occurrence index and the vṛtta reports on library changes — do not hand-edit those data folders.
