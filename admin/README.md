# Admin

**Moved here from `Tribhuvanachar/bhumandala` on 12 Sep 2026.** bhumandala is
the *public* repo — anyone can `git clone` it — and it must contain only
served reader content, nothing administrative. These pages are now reached
exclusively through bhumandala's BYOK loader (`js/admin-brahmabuddhi.js`),
which fetches them live over the GitHub Contents API using a viewer's own
BrahmaBuddhi-scoped personal access token, base64-decodes them, rewrites
their same-repo asset references, and renders the result in a srcdoc
iframe. Without a valid token, a visitor to bhumandala sees no menu entry,
no link, and no page name anywhere in its served HTML/JS — the full list of
what exists here lives only in `config/admin-menu.json`, in this repo.

**Not everything that once lived under bhumandala's `admin/` came with it.**
Two of its four subfolders — `config/` and `content/` — turned out to hold
data the *live public reader* fetches directly and unauthenticated on every
visit (the whole site menu, SEO tags, the landing page's words, legal text,
the What's New panel, kosha/library/chandas visibility overrides, …), not
admin-only material that merely happened to sit in the same folder tree.
Moving those here would have taken the public site's menu and several
reader features down. They were split out to bhumandala's own repo-root
`config/` and `content/` instead — see that repo's `config/` for the file
that documents which is which. Only the config genuinely read by nobody but
these tools moved here: `keys.json` (the old passkey gate, now secondary to
the PAT) and the admin-only state/status files (`repo-map.json`,
`sources.registry.json`, `sources.state.json`, `search-index.state.json`,
`library-status.json`, `kavya-status.json`, `pending_pdf_sources.json`,
`dv_sync.state.json`).

`convert/` (the OCR/conversion tool) and `dvaitavedanta-status/` (an
internal extraction-progress tracker) moved here alongside these pages, as
siblings of this `admin/` folder at the repo root — matching the relative
depth their own internal `../js/…`, `../images/…` references already
assumed, restoring a `../convert/...` reference from `admin/dasa-capture.html`
and `admin/ocr-studio.html` that had been silently broken since bhumandala's
own `pages/` reorg moved `convert/` a level deeper without updating them.

Everything below this point describes the pages and config as they stood
the day of the move; update it in place as things change here from now on.

---

Every admin page and every hand-editable config file for the Sarvamūla
Digital Library. They used to be scattered through bhumandala's repo root;
this folder is the one place to look — now in BrahmaBuddhi rather than
bhumandala, for the reason above.

## Pages

| Page | What it manages |
|---|---|
| `library.html` | Library curation — hide, pin, reorder, rename, move. Exports `config/library-overrides.json`. |
| `kosha.html` | Kosha (lexicon) dictionaries and their status. |
| `ashtadhyayi.html` | Aṣṭādhyāyī sūtras, vṛttis and related data. |
| `audio.html` | Audio catalogue and playback metadata. |
| `genie-asr-recorder.html` | Records the Genie ASR benchmark's voice samples and pushes them straight to the `genie-asr-audio-seed` branch of this repo — see its own note in `config/keys.json` (gate `genieasr`) for why that's a separate gate from `audioadmin`. |
| `dasa-capture.html` | Dāsa Sāhitya capture and entry. |
| `holy-places.html` | Holy places and brindāvana curation for Guru Paramparā. |
| `repo-map.html` | **Repository & Workflows** — one page, three tabs. *Workflows*: every workflow file grouped in accordions (online source syncers first, one card per website; then importers, Gemini enrichment, OCR, index & cross-links, deploy, Kamadhenu, tests, one-off probes), each with what it does, when it runs, what it writes, what it costs, its last run, a recommendation with the reason, its real input form, and Run / Delete buttons. *Branches*: the same for every branch. *Ask Claude*: leave an instruction for Claude against chosen library sections (`tasks/README.md`). Runs go through the Cloud Function when deployed (`FIREBASE_SETUP.md` §12), else through the browser's GitHub token, else GitHub itself. Data: `config/repo-map.json` (hand-written purpose/recommendation + generated fields, refreshed by `tools/build_repo_inventory.py`, which also renders `docs/REPO_INVENTORY.md`) and `firebase/functions/workflows.json` (the curated input forms). |
| `ocr-review.html` | **OCR Review** — scholar review of staged OCR: the page scan on the left (from the `ocr-images/<work>` branch, rendered free on demand), the text in units on the right, accept / edit / reject per unit, decisions saved beside the staged file, and a Finalise panel that runs `ocr-review-merge.yml` to turn approved text into a library layer as a pull request. Pipeline: `docs/OCR_REVIEW.md`. Admin passkey is enough (a scholar need not be super-admin). |
| `ocr-studio.html` | **OCR Studio** — the styling half of the same pipeline: the page scans on the left, the digitised document on the right, and a Word-style class panel. Each block keeps the tag the OCR gave it (`srcTag`) separately from the class we assign it (`cls`), so selecting one heading and pressing **all N** moves exactly the blocks the OCR tagged the same way, and editing a class's appearance restyles every block carrying it. Exports standalone HTML, or blocks in the shape `tools/ocr_review_merge.py` already reads. **⚖ Compare engines** stacks all three readers one beneath the other — Sarvam Document AI (layout kept, paid, `SARVAM_API_KEY`, `.github/workflows/ocr-sarvam.yml`), Google Cloud Vision (flat text, paid, `VISION_API_KEY`, `.github/workflows/ocr-vision-pages.yml`) and Tesseract.js (free, WASM, runs in the tab) — each beside the scan it read, with block/char counts and how far it agrees with the chosen reading; **Use this** adopts one for styling. Vision and Sarvam are loaded from their staged files (`?sarvam=…&vision=…`) because their keys are repository secrets only a workflow holds; Tesseract runs here on the loaded scans. Gemini is deliberately not offered: it proofreads Vision's text and never reads a scan. Model and its tests: `admin/js/ocr-studio-core.js`, `firebase/tests/ocr-studio.test.js`. Same passkey as OCR Review. |
| `workflows.html` | Redirect stub — the old "Run a Workflow" page, folded into `repo-map.html` on 9 Sep 2026. Kept so bookmarks land. |
| `content-provenance.html` | Reference map of which file/field governs each part of the reader-facing site — a static "where do I change this?" lookup, not a live inspector. |

Reached from the shield icon in the library's top bar, which appears only
for authorised users.

Not moved: `convert/` — the OCR and conversion tool is a self-contained
app of some fifteen files that reference each other relatively. It stays
where it is, and is still linked from the same admin menu.

## Config

| File | Read by | Written by |
|---|---|---|
| `config/config-overrides.json` | `js/core.js` at boot, merged over `js/config.js` | Site Settings, in-app (`js/config-editor.js`) |
| `content/home.json` | the landing page — **all of its words** | hand-edited |
| `content/whats-new.json` | `js/modals.js`, re-read every time the panel opens | Site Settings, or by hand |
| `content/reader.json` | `js/core.js` at boot — the Support and About panels' text | in place on the page, Site Settings, or by hand |
| `content/tour.json` | `js/tour.js` — the guided walkthrough's steps | in place on the page, or by hand |
| `config/home.json` | the landing page — where it leads, the photo, the flowers | hand-edited |
| `config/menu.json` | `js/menu.js` — which menu items appear, and in what order | hand-edited |
| `config/intellisense.json` | `js/intellisense.js` — sūtra identification | hand-edited |
| `config/library-overrides.json` | `js/library.js` | `library.html`, exported and committed by hand |
| `config/library-status.json` | `library.html` | `tools/gen_library_status.py` — a generated snapshot of what is loaded |
| `config/site.config.json` | `tools/set_site_url.py` | hand-edited, then applied with that script |
| `config/keys.json` | `js/keys.js`, used by every gated admin page | hand-edited |

Each file carries a `_readme` key listing what it accepts, so the file
itself is the reference and this table only has to say which is which.

`site.config.json` holds the site's own absolute URL. Almost nothing needs
it — the reader resolves its links relatively and runtime JavaScript uses
`location.origin`, both of which follow whatever domain served the page.
The exception is Open Graph metadata, which link-preview crawlers read
without executing JavaScript, so it has to be written into the HTML. Change
`siteOrigin` there and run `python3 tools/set_site_url.py`; never hand-edit
the tag it manages.

Two different arrangements here, on purpose.

**Overrides.** `config-overrides.json` and the rest hold only the fields
actually changed; anything absent falls back to a default in the code. These
fail open — missing, empty or malformed leaves the defaults standing, so the
menus stay as written in the markup and the gates stay shut. A broken config
file is never the reason something disappears or springs open.

**Sources.** `content/home.json` and `config/home.json` are not overrides:
they are the only copy. `index.html` carries no words of its own, so there is
nothing to fall back to, and that is the point — a second copy of the text is
a second thing to keep in step, and it is always the stale one that reaches
the screen. If either file cannot be read the page says so and offers to
retry, rather than showing a half-drawn gate or letting anyone past a vandana
it could not display.

That trade is only safe because it is checked. `python3 tools/check_content.py`
fails if a page's files are missing, unparseable, or short of a key that page
reads — including a section whose Know More button points at a panel that does
not exist. Run it before pushing.

### Which file owns what

Asked often enough to be worth stating once:

| To change | Edit |
|---|---|
| Which menu items appear, and their order | `config/menu.json` |
| Where sūtra citations become tappable, and word analysis | `config/intellisense.json` |
| Any word on the landing page | `content/home.json` |
| Where the landing page leads, or how the gate behaves | `config/home.json` |
| Which reading scripts are offered | `SCRIPT_OPTIONS` in `js/config.js` |
| Feature switches (theme picker, snippet tools, …) | `FEATURE_FLAGS` in `js/config.js` |
| Passkeys | `config/keys.json` |
| What's New and Coming Soon | `content/whats-new.json` |
| Sponsor, contributors, key sponsors | `content/reader.json` |
| The walkthrough's steps and wording | `content/tour.json` |
| Contact address, app name, designer credit | `config/config-overrides.json` |

## Config that is not here

Deliberately, because moving it would mean moving the code that owns it:

- **`js/config.js`** — the defaults themselves: `appConfig`,
  `SPONSOR_CONFIG`, `CONTRIBUTORS_CONFIG`, `WHATS_NEW_CONFIG`,
  `FEATURE_FLAGS`, `AI_PROVIDERS`, `GITHUB_REPO_CONFIG`,
  `ADMIN_ACCESS_LEVELS`. Loaded by every page in the app. `WHATS_NEW_CONFIG`,
  `SPONSOR_CONFIG`, `CONTRIBUTORS_CONFIG` and `KEY_SPONSORS_CONFIG` used to
  live here and no longer do — they are content, in `admin/content/`.
- **`data/`** — corpus data rather than settings: `library.json`,
  `taxonomy.json`, `schemas.json`, `tippanikaras.json`.

## Removed

Files that no code read, deleted rather than left to mislead. All of them
remain in git history if any is ever wanted back.

- `Config.json` — dead, and it carried the `SHRI108` passkey.
- `Claude.html`, `grok.html`, `MegaInteractive.html`, `Sunrise.html` —
  early prototypes of the reading page, superseded by ``.
- `PrahladaKrutaNarasimhaStotra.html` and `data_pns.json` — a standalone
  copy of the Prahlāda-kṛta Nṛsiṃha Stotra, superseded by the live text at
  `data/DvaitaVedanta/Itara/Stotra/prahlada_kruta_narasimha/` (renamed from `pns/` 23 Aug
  2026; the internal `stotraCode`/localStorage namespace stayed `pns`,
  see `core.js`'s `STOTRA_CODE_CONTINUITY`).
- `version.json` at the root — read by nothing. `convert/version.json`
  is a different file and is still in use.
- `data/tippanikaras.json`, `data/_taxonomy.json` — no reader.

One consequence worth naming: anyone holding a link to
`PrahladaKrutaNarasimhaStotra.html` will now get a 404. The same stotra
lives in the library, so the content is not lost — only that URL.

## Two things worth knowing

**The passkeys are not security.** They now live in one place —
`config/keys.json` — instead of being string literals inside the five pages
they guarded. That makes them changeable; it does not make them secret. The
file sits in a public repository, and the page source reveals them anyway.
They stop an admin tool being opened by accident or wandered into. Nothing
genuinely sensitive belongs behind them. Real protection needs a server, or
the Firebase accounts being wired up in `js/user-auth.js`.

**Paths here are derived, not written.** `js/core.js`, `js/menu.js`
and `js/keys.js` each resolve this folder from their own script URL rather
than from the page's, so the config loads correctly from any page depth, and
whether the site is served from a domain root or from a project subpath such
as `tribhuvanachar.github.io/bhumandala/`.

## Editing a page's words on the page

Any page with a `data-content-file` on its `<body>` can be edited where it is
read. Unlock super admin, press **Edit text** in the bar at the bottom, tap a
highlighted line, change it, **Publish**.

Edits stage in the browser and survive a refresh; nothing reaches GitHub until
Publish, which writes the whole file in one commit after re-reading it, so a
change someone else made meanwhile is not overwritten. It uses the same
personal access token as Repo Files.

To make a new field editable, give the element `data-edit="<path>"` — a path
into that page's content file, such as `brand.latin`,
`sections.0.name`, or `SPONSOR_CONFIG.introText`. Nothing else is needed;
`js/content-inline.js` finds it.

## The taxonomy restructure

`data/` was reorganised onto the top level proposed in
`DGE_Shastra_Taxonomy.md`. What used to be a mix of categories, single works
and a drawer called `ancillary` now reads as a tree a student would
recognise:

| Was | Is |
|---|---|
| `ancillary/{shiksha,vyakarana,chandas,nirukta,jyotisha}` | `vedanga/…` — it was the Vedāṅgas all along |
| `ancillary/pratishakhya` | `vedanga/shiksha/pratishakhya` |
| `sutras/kalpa_sutras` | `vedanga/kalpa` |
| `vyakarana` | `vedanga/vyakarana` — merged beside the grammatical schools |
| `sarvamoola_grantha` | `darshana/vedanta/dvaita/Anandamakaranda` |
| `shankara_bhashya` | `darshana/vedanta/advaita/shankara_bhashya` |
| `itihasas` / `puranas` / `stotras` / `koshas` | `itihasa` / `purana` / `stotra` / `kosha` |
| `smritis` / `dharmashastra` | `smriti_dharma/smriti` / `smriti_dharma/dharmashastra` |
| `kavya` | `kavya_alankara` |
| `dvaitavedanta` (23 Aug 2026) | `darshana/vedanta/dvaita/DvaitaVedantaIn` — admin-only, see `entry.hidden` in `library.json` |
| `darshana/vedanta/dvaita/sarvamula` (23 Aug 2026) | `darshana/vedanta/dvaita/Anandamakaranda` |
| `stotra/pns` (23 Aug 2026) | `DvaitaVedanta/Itara/Stotra/prahlada_kruta_narasimha` |
| `pancharatra_agama` | `agama/pancharatra` |
| `dasakuta` / `vyasakuta` | `DvaitaVedanta/Itara/DasaSahitya/dasakuta` / `DvaitaVedanta/Itara/DasaSahitya/vyasakuta` |
| `vedas` | unchanged |

Two scripts did it, and both still run: `tools/restructure_taxonomy.py`
(reports by default, `--apply` moves) and `tools/migrate_slugs.py` (the
cross-references, the backlinks and the search-index shard names).

**Old links still work.** `DGE_LEGACY_SLUGS` in `js/core.js` rewrites an
old `?path=` on the way in, so a bookmark or a shared link from before the
move lands on the text rather than on "Not Yet Available". That table is now
the only copy of the old names left in the codebase — don't delete it
because it looks redundant.

The search index was rewritten rather than rebuilt. Its postings are keyed
by grantha index, not by slug, so only the manifest, `backlinks.json` and
the shard filenames carried the old names. The result is what a rebuild
would have produced, for a fraction of the work.
