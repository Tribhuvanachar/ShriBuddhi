# Changelog

## v0.35.0 — 2026-08-23
- **New "☁️ Server Pipeline" tab** — an alternative to the local Upload/OCR/Proofread/Review/Push flow, for a real book that times out this browser tab. Instead of running Vision/Gemini calls here, it dispatches two new GitHub Actions workflows and brings the result back:
  1. **Preview** (`ocr-preview-pages.yml`) — free, Gemini/Vision-free: renders just the start/end/extra pages you type so you can visually confirm the range (and see the PDF's real total page count) before spending anything.
  2. **Send for OCR + Proofread** (`ocr-sanskrit-commentary.yml`) — the real, billed run: same Vision OCR + Gemini proofreading as the local flow (server-side port: `tools/ocr_pipeline.py`), staged as a plain JSON file (never auto-merged into the corpus — that's a deliberate separate step, `tools/merge_staged_commentary.py`). Supports excluding specific pages within the range, and takes either a direct PDF URL or up to 3 split-7z part URLs (downloaded and combined server-side via `7z`) — no file upload needed.
  Result renders inline (per-shloka accept/review/unresolved coloring, plus raw JSON), with Download and Web-Share (mobile "send to any app," e.g. attach in Gmail) always available, and a separate "Push to `ocr_staging`" action using the same GitHub token as the Push tab.
  New `actions.js` (`window.DGE.Actions` — dispatch/poll GitHub Actions runs, download artifacts) and `zipread.js` (`window.DGE.ZipRead` — minimal in-browser ZIP reader for artifact downloads, no external library).

## v0.10.0 — 2026-08-10
- **Document Loader architecture** — OCR no longer assumes its source is a PDF. `app.js`'s OCR loop now talks to a generic `currentLoader` (`load()` / `getPageCount()` / `getDocumentName()` / `getPageImage(index)`), chosen at file-selection time by a new `loaders.js` factory. `pdf.js` was generalized to expose that same shape (its old `loadPdf`/`renderPageToPngBase64` still work — thin wrappers now, not a second code path) and Vision (`vision.js`) still only ever sees a base64 PNG, unchanged.
- New **`image.js`** (`window.DGE.ImageLoader`) — upload one or more page-image files (JPG/PNG/WEBP) directly instead of a PDF, in the order you select them. Every page is normalized to PNG via canvas and capped at 3000px on its longest edge (bounds the Vision request payload and matches the resolution the PDF path already renders at — a raw phone photo or full-res scan gains nothing from going in uncapped).
- New **`loaders.js`** (`window.DGE.Loaders.detect`) — picks PDF vs. image loader from what was actually selected; rejects a mixed PDF+image selection or multiple PDFs with a clear message instead of silently picking one.
- **JP2 explicitly NOT supported yet, on purpose** — no mainstream browser decodes JPEG 2000 without an added WASM/JS decoder, and Vision's synchronous `images:annotate` endpoint doesn't accept JP2 bytes directly either. Selecting a `.jp2` file now fails immediately with a clear explanation instead of a silent blank-OCR result. Revisit if/when a specific decoder library is chosen and tested.
- File input now accepts multiple files (`multiple` attribute) and both PDF and image MIME types/extensions.

## v0.7.0 — 2026-08-07
- **URL import** — new "Fetch Page" option alongside PDF upload, for sources that are already digital text (confirmed to be a MediaWiki site by fetching a real page before writing this). Pulls raw text via MediaWiki's `?action=raw` endpoint (works across essentially any MediaWiki install, no server-side extension dependency), strips basic wikitext markup, and feeds the result into the exact same chunked proofread → schema map → push pipeline that OCR'd PDFs already use — no OCR step, no separate code path, no new credential surface. A page that's already text just skips straight to step 3.
- New `urlimport.js` (`window.DGE.UrlImport`).

## v0.6.0 — 2026-08-06
- **Schema Mapper + Push to GitHub — closes the pipeline.** New step 4: maps Gemini's generic proofread output into the REAL DGE grantha schema (matching `data/stotras/pns/data.json`'s shape exactly), shown as an EDITABLE preview (every shloka's Sanskrit and commentary in its own textarea) before anything is pushed. "Push to GitHub" commits the new/updated grantha `data.json` AND the matching `data/library.json` catalog entry (title + `populated: true`) together in ONE atomic commit.
- New `github.js` (`window.DGE.GitHub`) — a Convert-scoped port of the main app's batch diff-commit technique (blob/tree/commit/ref via the Git Data API), reusing the same approach rather than reimplementing something different. Shares the same `github_admin_pat` localStorage key as the main app's Admin panel — paste the token once, it works in both places.
- New `mapper.js` (`window.DGE.Mapper`) — deliberately a plain deterministic function, not another AI call: assembling the exact nested schema needs admin-supplied context (commentary key naming, title, author) that Gemini has no way to know, and a rigid schema is exactly where letting an LLM free-form is riskiest.
- Target grantha is chosen from the live `data/library.json` catalog (only NOT-yet-populated entries listed by default, to avoid accidental overwrites — pushing to an already-populated one requires an explicit confirmation), or a free-typed new path for anything not in the catalog yet.

## v0.5.0 — 2026-08-05
- **Root-caused a real failure:** a 31-page PDF's single-request proofread call threw "Could not parse JSON from the model's response" — confirmed exactly the risk flagged in v0.4.0's known limitations. Fixed at the source, two ways:
  1. **Chunked proofreading.** Gemini is now called once per chunk of pages (default 8, adjustable in the UI) instead of once for the entire book. Each chunk's result is saved to IndexedDB the moment it completes, so re-running Proofread — even after closing the tab — automatically skips finished chunks and resumes from the first unfinished one. A failure on one chunk no longer loses any earlier chunks' work.
  2. **Schema-constrained Gemini output** (`responseMimeType`/`responseSchema` in the request). Forces syntactically valid JSON matching the expected shape at the decoding level, instead of relying on the model to freely produce valid punctuation across a long response. Also now explicitly detects a `MAX_TOKENS` finish reason and reports it as a clear, actionable error ("try a smaller chunk size") instead of letting truncated output reach the JSON parser and surface as a confusing generic syntax error.
- **Moved OCR + proofread progress from localStorage to IndexedDB** (new `idb.js`, `window.DGE.IDB`). localStorage's ~5–10MB per-origin ceiling, shared across every cached file, was a real risk for the eventual goal of converting ~600-page volumes — IndexedDB has no such practical limit.
- Added a manual **"Clear saved progress for this file"** control (Danger Zone) — for replacing a PDF with a corrected version under the same filename.
- Merged proofread output now carries a guaranteed-unique, guaranteed-ordered `index` field per entry alongside Gemini's own `number` field (which restarts per chunk and can repeat across a merged multi-chunk result — kept as-is since it may reflect a real verse number printed on the source page, just not safe to rely on alone for ordering).

## v0.4.1 — 2026-08-04
- Added a **raw OCR preview** — "Show Raw OCR" / "Show Proofread" toggle above the preview area, so Vision's untouched output can be eyeballed for accuracy independently of Gemini's proofreading pass. Raw preview auto-shows right after an OCR run finishes; proofread preview auto-shows right after a proofread run finishes; either can be recalled manually at any time via the toggle buttons.
- Investigated a reported logger issue (console showing `{}` instead of a real Gemini error message). Reviewed `app.js`, `gemini.js`, and `utils.js` end to end — found no code path that produces this; every error is already resolved through `formatError()`, which correctly reads `e.message`. No fix was needed or made here; flag if the raw `{}` output recurs so it can be caught live (browser + exact console line would help pin it down).

## v0.4.0 — 2026-08-04
- **First real functional pipeline.** Previous versions (up to 0.3.0) were stub/placeholder modules only.
- PDF.js wired up for real (loaded from CDN — the local `libs/` placeholder files were never populated with a real build, so CDN is now the source of truth; `libs/` can be deleted).
- Page-by-page rendering to PNG, one page at a time (deliberate — avoids holding many rendered canvases in memory at once on mobile).
- Real Google Cloud Vision OCR integration, page-by-page with progress display.
- Real Gemini proofreading integration — prompts toward the actual DGE shloka/commentary schema, with loose JSON parsing to handle stray markdown fences in model output.
- Resume support: last successfully OCR'd page is saved to localStorage per-file; interrupted runs offer to resume instead of restarting.
- Error handling for invalid keys, quota limits, network failures, and unreadable PDFs — with specific, actionable messages rather than generic failures.
- Preview renders the final Gemini-proofread JSON as shloka/commentary blocks.
- Downloads for both `ocr.json` (raw OCR) and `final.json` (proofread).
- `window.DGE` used as the single global namespace throughout (`DGE.PDF`, `DGE.Vision`, `DGE.Gemini`, `DGE.Renderer`, `DGE.Utils`, `DGE.App`) — kept fully separate from the main reader app's globals since this is always a standalone page.

### Known limitations, not yet addressed
- Gemini proofreading sends the *entire* OCR text in one request — for a very long book this may exceed the model's practical input size and need chunking. Not yet hit in testing; flag if it happens.
- No GitHub integration yet, by design (see requirements) — when added, should reuse the Contents/Blobs API helpers already built in the main app's `admin-editor.js`.

## v0.3.0 (prior)
- Added PDF inspection module separation.
- Added page preparation module (stub only, not real rendering).
- Versioning and cache-busting scaffolding retained from this point forward.
