#!/usr/bin/env python3
"""
sarvam_docai.py — layout-preserving OCR through Sarvam AI's Document AI.

Why a second OCR engine. The Vision + Gemini pipeline returns each page as
one flat string: headings, paragraphs, verse breaks, footnotes and indentation
are all gone, and a scholar reviewing it sees a wall of text. Sarvam's
Document AI ("Sarvam Vision") is trained on Indian-language scans and returns
HTML / Markdown / JSON with the page's structure kept — headings as headings,
paragraphs as paragraphs, tables as tables — which is exactly what a review
UI needs to show beside the scan.

The API (docs.sarvam.ai → Document Intelligence):
    POST https://api.sarvam.ai/doc-ai/v1/job/digitise
         header  api-subscription-key: <key>
         form    file=@pages.pdf  language=sa-IN|kn-IN|hi-IN|en-IN  output_format=html|md|json
      → {"job_id": …, "status": "pending"}
    GET  …/job/{id}/status        → status + usage{pages_total, pages_processed, …}
    GET  …/job/{id}/download-url  → a URL for the result (a zip or the file)
Limits: 10 pages per request, 200 MB per file, 10 requests a minute. So a
scan is sent in 10-page slices, each its own job, and the slices are stitched
into ONE staged file per run.

Cost: Sarvam bills per page from a prepaid balance on dashboard.sarvam.ai;
the docs do not print a rate. Every run records its page count under
"usage" in the staged file and in the workflow log, so the ₹ spent per book
is known once the lead has one bill to divide by. No key → --dry-run only.

    python3 tools/sarvam_docai.py --pdf book.pdf --pages 11-40 --work isha_tippani \
        --language sa-IN --format html --out dge/data/ocr_staging
    python3 tools/sarvam_docai.py --pdf-url https://archive.org/download/…/x.pdf --pages 1-10 --work x --dry-run

Writes dge/data/ocr_staging/<work>/sarvam_pages<A>-<B>.json:
    {source:{pdf, pages}, engine:"sarvam-docai", language, format, generated_at,
     usage:{pages_total, pages_succeeded, pages_failed, jobs},
     pages:[{page, html|md|json, ok}]}
which admin/ocr-review.html opens as a review set (tools/ocr_review_merge.py
turns approved blocks into a layer).
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile

API = "https://api.sarvam.ai/doc-ai/v1/job"
PAGES_PER_JOB = 10
KEY_ENV = "SARVAM_API_KEY"


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def parse_pages(spec: str, total: int | None) -> list[int]:
    out = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            a = int(a)
            b = int(b) if b else (total or a)
            out.extend(range(a, b + 1))
        else:
            out.append(int(part))
    out = sorted(set(p for p in out if p > 0 and (total is None or p <= total)))
    return out


def pdf_page_count(pdf: str) -> int | None:
    try:
        info = subprocess.check_output(["pdfinfo", pdf], text=True, stderr=subprocess.DEVNULL)
        m = re.search(r"^Pages:\s+(\d+)", info, re.M)
        return int(m.group(1)) if m else None
    except Exception:  # noqa: BLE001
        return None


def slice_pdf(pdf: str, first: int, last: int, out: str) -> None:
    """One PDF holding pages first..last, with pdfseparate/pdfunite (poppler)
    or qpdf, whichever the runner has."""
    if subprocess.call(["which", "qpdf"], stdout=subprocess.DEVNULL) == 0:
        # qpdf exits 3 for "succeeded with warnings" and 2 for a real error.
        # A scanned book almost always warns about something cosmetic — the
        # Raghavendra Vijaya scan reports an object count one off from its
        # highest object number — and the slice is written correctly anyway.
        # check_call treated that 3 as fatal, so the run died before it
        # reached Sarvam at all. Accept 3, and let 2 raise as it should.
        rc = subprocess.call(["qpdf", "--empty", "--pages", pdf, f"{first}-{last}", "--", out])
        if rc == 3:
            log(f"  qpdf warned on {os.path.basename(pdf)} but wrote the slice; continuing")
        elif rc != 0:
            raise subprocess.CalledProcessError(rc, "qpdf")
        return
    with tempfile.TemporaryDirectory() as td:
        subprocess.check_call(["pdfseparate", "-f", str(first), "-l", str(last), pdf, os.path.join(td, "p-%d.pdf")])
        parts = [os.path.join(td, f"p-{i}.pdf") for i in range(first, last + 1)]
        subprocess.check_call(["pdfunite", *parts, out])


def http(method: str, url: str, key: str, data=None, headers=None, timeout=120):
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("api-subscription-key", key)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read()


def multipart(fields: dict, file_field: str, path: str) -> tuple[bytes, str]:
    boundary = "----dge" + hex(int(time.time() * 1000))[2:]
    body = io.BytesIO()
    for k, v in fields.items():
        body.write(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
    body.write(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{file_field}\"; filename=\"{os.path.basename(path)}\"\r\n"
               f"Content-Type: application/pdf\r\n\r\n".encode())
    body.write(open(path, "rb").read())
    body.write(f"\r\n--{boundary}--\r\n".encode())
    return body.getvalue(), f"multipart/form-data; boundary={boundary}"


def digitise(pdf_slice: str, language: str, fmt: str, key: str, poll=6, max_wait=900) -> tuple[dict, bytes]:
    data, ctype = multipart({"language": language, "output_format": fmt}, "file", pdf_slice)
    _, body = http("POST", f"{API}/digitise", key, data=data, headers={"Content-Type": ctype})
    job = json.loads(body)
    jid = job.get("job_id") or job.get("id")
    if not jid:
        raise RuntimeError(f"no job id in {body[:200]!r}")
    log(f"  job {jid} submitted")
    waited = 0
    status = job
    while waited < max_wait:
        time.sleep(poll)
        waited += poll
        _, sb = http("GET", f"{API}/{jid}/status", key)
        status = json.loads(sb)
        st = str(status.get("status", "")).lower()
        if st in ("completed", "partially_completed", "failed", "rejected"):
            break
    st = str(status.get("status", "")).lower()
    if st in ("failed", "rejected"):
        raise RuntimeError(f"job {jid} {st}: {json.dumps(status)[:300]}")
    _, db = http("GET", f"{API}/{jid}/download-url", key)
    d = json.loads(db)
    url = d.get("download_url") or d.get("url")
    if not url:
        raise RuntimeError(f"no download url: {db[:200]!r}")
    with urllib.request.urlopen(url, timeout=300) as r:
        payload = r.read()
    return status, payload


def unpack(payload: bytes, fmt: str, pages: list[int]) -> list[dict]:
    """The result is a zip (one file per page) or a single document. Either
    way, return one entry per requested page, in order."""
    out = []
    if payload[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(payload)) as z:
            names = sorted(z.namelist(), key=lambda n: [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", n)])
            docs = [z.read(n).decode("utf-8", "replace") for n in names if not n.endswith("/")]
    else:
        docs = [payload.decode("utf-8", "replace")]
    if len(docs) == len(pages):
        for p, d in zip(pages, docs):
            out.append({"page": p, fmt: d, "ok": True})
    else:
        # One document for the whole slice: keep it whole on the first page and
        # say so, rather than guessing page boundaries.
        out.append({"page": pages[0], "page_end": pages[-1], fmt: "\n".join(docs), "ok": True,
                    "note": f"{len(docs)} document(s) returned for {len(pages)} pages; not split per page"})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--pdf", help="local PDF")
    src.add_argument("--pdf-url", help="URL of the PDF (downloaded once)")
    ap.add_argument("--pages", required=True, help='page spec, e.g. "1-10,15,20-24"')
    ap.add_argument("--work", required=True, help="staging folder under --out (a work slug)")
    ap.add_argument("--language", default="sa-IN", help="sa-IN (Sanskrit), kn-IN, hi-IN, en-IN …")
    ap.add_argument("--format", default="html", choices=["html", "md", "json"])
    ap.add_argument("--out", default="dge/data/ocr_staging")
    ap.add_argument("--dry-run", action="store_true", help="slice and count pages, call nothing")
    ap.add_argument("--max-pages", type=int, default=200, help="refuse to send more than this in one run")
    args = ap.parse_args()

    key = os.environ.get(KEY_ENV, "")
    if not key and not args.dry_run:
        log(f"{KEY_ENV} is not set — running as --dry-run.")
        args.dry_run = True

    pdf = args.pdf
    tmpdir = tempfile.mkdtemp(prefix="sarvam-")
    if args.pdf_url:
        pdf = os.path.join(tmpdir, "source.pdf")
        log(f"downloading {args.pdf_url}")
        urllib.request.urlretrieve(args.pdf_url, pdf)
    total = pdf_page_count(pdf)
    pages = parse_pages(args.pages, total)
    if not pages:
        log("no pages selected")
        return 2
    if len(pages) > args.max_pages:
        log(f"{len(pages)} pages asked for; cap is {args.max_pages} (raise --max-pages deliberately)")
        return 2

    # Contiguous runs of at most PAGES_PER_JOB pages, each one job.
    slices, cur = [], [pages[0]]
    for p in pages[1:]:
        if p == cur[-1] + 1 and len(cur) < PAGES_PER_JOB:
            cur.append(p)
        else:
            slices.append(cur)
            cur = [p]
    slices.append(cur)
    log(f"{len(pages)} pages in {len(slices)} job(s) of ≤{PAGES_PER_JOB}; language {args.language}; format {args.format}")
    if args.dry_run:
        print(json.dumps({"dry_run": True, "pages": len(pages), "jobs": len(slices), "pdf_pages": total,
                          "note": "Set SARVAM_API_KEY to run. Sarvam bills per page; this run would send %d." % len(pages)}, indent=1))
        return 0

    result = {
        "_readme": "Layout-preserving OCR from Sarvam Document AI (tools/sarvam_docai.py). Review in admin/ocr-review.html; nothing here reaches the library until approved.",
        "source": {"pdf": args.pdf_url or os.path.basename(args.pdf), "pages": pages, "pdf_pages": total},
        "engine": "sarvam-docai", "language": args.language, "format": args.format,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "usage": {"pages_total": 0, "pages_succeeded": 0, "pages_failed": 0, "jobs": 0},
        "pages": [],
    }
    for i, sl in enumerate(slices, 1):
        first, last = sl[0], sl[-1]
        part = os.path.join(tmpdir, f"slice_{first}-{last}.pdf")
        slice_pdf(pdf, first, last, part)
        log(f"[{i}/{len(slices)}] pages {first}-{last}")
        try:
            status, payload = digitise(part, args.language, args.format, key)
            u = status.get("usage") or {}
            result["usage"]["pages_total"] += int(u.get("pages_total") or len(sl))
            result["usage"]["pages_succeeded"] += int(u.get("pages_succeeded") or len(sl))
            result["usage"]["pages_failed"] += int(u.get("pages_failed") or 0)
            result["usage"]["jobs"] += 1
            result["pages"].extend(unpack(payload, args.format, sl))
        except Exception as exc:  # noqa: BLE001
            log(f"  failed: {exc}")
            result["usage"]["pages_failed"] += len(sl)
            result["pages"].extend({"page": p, "ok": False, "error": str(exc)[:200]} for p in sl)
        if i < len(slices):
            time.sleep(7)  # 10 requests a minute, and each job is ≥2 requests

    outdir = os.path.join(args.out, args.work)
    os.makedirs(outdir, exist_ok=True)
    outp = os.path.join(outdir, f"sarvam_pages{pages[0]}-{pages[-1]}.json")
    with open(outp, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    log(f"wrote {outp}: {result['usage']}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(f"## Sarvam Document AI\n\n`{outp}` — pages sent **{result['usage']['pages_total']}**, "
                     f"succeeded {result['usage']['pages_succeeded']}, failed {result['usage']['pages_failed']}, "
                     f"jobs {result['usage']['jobs']}. Sarvam bills per page from the prepaid balance.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
