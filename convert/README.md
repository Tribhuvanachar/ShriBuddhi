# DGE Convert

Client-side tool: scanned PDF → page images → Google Cloud Vision OCR → Gemini proofreading → DGE-schema JSON. No backend, no server — everything runs in the browser, calling Google's APIs directly with keys you provide.

## Folder structure

```

└── convert/
    ├── index.html
    ├── style.css
    ├── app.js          — orchestration (window.DGE.App)
    ├── pdf.js           — PDF.js integration (window.DGE.PDF)
    ├── vision.js         — Vision OCR calls (window.DGE.Vision)
    ├── gemini.js         — Gemini proofreading (window.DGE.Gemini)
    ├── renderer.js        — preview rendering (window.DGE.Renderer)
    ├── utils.js          — shared helpers (window.DGE.Utils)
    ├── version.json
    ├── CHANGELOG.md
    ├── README.md
    └── cors-test.html      — standalone diagnostic, kept for future reference
```

PDF.js itself is loaded from CDN (cdnjs), not bundled locally — the `libs/` folder from earlier versions was never actually populated and can be deleted.

## Usage

1. Open `index.html` (works locally or hosted — no build step)
2. Paste Vision and Gemini API keys (saved to this browser only)
3. Upload a PDF
4. Run OCR — processes one page at a time, shows progress, saves resume state
5. Proofread — sends OCR output to Gemini, returns structured JSON
6. Preview, then download `ocr.json` and/or `final.json`

## Access

Not linked from the main reader app's navigation — treat this URL as admin-only, same spirit as the `?superadmin=` gate on the GitHub file manager, even though this page has no gate of its own.
