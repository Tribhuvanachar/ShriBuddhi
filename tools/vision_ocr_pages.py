#!/usr/bin/env python3
"""Vision-only page OCR: render a PDF page range and run Google Cloud Vision DOCUMENT_TEXT_DETECTION on
every page, writing one JSON with the full text + words (confidence) per page. No Gemini, no proofread.

    VISION_API_KEY=... python3 tools/vision_ocr_pages.py --pdf file.pdf --start 1 --end 459 \
        --out dge/data/ocr_staging/<slug>/vision_pages_1-459.json [--dpi 200] [--batch 8] [--lang sa,kn]

Meant to run inside .github/workflows/ocr-vision-pages.yml (the key is a repository secret); the
local Tesseract pass + the merge/classification happen in the importer for the work concerned."""
import argparse, base64, io, json, os, sys, time
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vision_client import ocr_images_batch, VisionError  # noqa: E402


def render(pdf, page_no, dpi):
    import fitz
    d = fitz.open(pdf)
    pix = d[page_no - 1].get_pixmap(dpi=dpi)
    return pix.tobytes("png"), pix.width, pix.height


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True); ap.add_argument("--start", type=int, required=True); ap.add_argument("--end", type=int, required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--dpi", type=int, default=200); ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--lang", default="sa,kn,hi")
    a = ap.parse_args()
    key = os.environ.get("VISION_API_KEY")
    if not key:
        sys.exit("VISION_API_KEY not set")
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    done = {}
    if out.exists():
        done = {p["page"]: p for p in json.load(open(out, encoding="utf-8")).get("pages", [])}
    pages = [p for p in range(a.start, a.end + 1) if p not in done]
    print(f"vision: {len(pages)} pages to OCR ({len(done)} already in {out})", flush=True)
    hints = [h for h in a.lang.split(",") if h]
    t0 = time.time()
    for i in range(0, len(pages), a.batch):
        chunk = pages[i:i + a.batch]
        imgs = []; dims = []
        for p in chunk:
            png, w, h = render(a.pdf, p, a.dpi); imgs.append(base64.b64encode(png).decode("ascii")); dims.append((w, h))
        for attempt in range(3):
            try:
                res = ocr_images_batch(imgs, key, hints); break
            except VisionError as e:
                print(f"  batch {chunk[0]}-{chunk[-1]} attempt {attempt+1}: {e}", flush=True); time.sleep(5 * (attempt + 1)); res = None
        if res is None:
            for p in chunk: done[p] = {"page": p, "error": "vision failed after 3 attempts"}
        else:
            for p, r, (w, h) in zip(chunk, res, dims):
                done[p] = {"page": p, "width": w, "height": h, "dpi": a.dpi, "text": r.get("text", ""), "words": r.get("words", [])}
        # "engine" names the reader, so admin/ocr-studio.html can put this file
        # in the right engine's slot. Without it stagedEngine() finds nothing to
        # go on and the Load button drops Vision's output into the Sarvam row.
        data = {"_readme": "Raw Google Vision DOCUMENT_TEXT_DETECTION per PDF page (no proofreading). Produced by tools/vision_ocr_pages.py.",
                "engine": "vision",
                "pdf": os.path.basename(a.pdf), "dpi": a.dpi, "language_hints": hints, "pages": [done[k] for k in sorted(done)]}
        json.dump(data, open(out, "w", encoding="utf-8"), ensure_ascii=False)
        print(f"  {len(done)} pages done ({time.time()-t0:.0f}s)", flush=True)
    errs = sum(1 for p in done.values() if p.get("error"))
    print(f"vision: finished {len(done)} pages, {errs} errors -> {out}")


if __name__ == "__main__":
    main()
