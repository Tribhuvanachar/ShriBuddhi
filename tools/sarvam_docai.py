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
        --language sa-IN --format html --out data/ocr_staging
    python3 tools/sarvam_docai.py --pdf-url https://archive.org/download/…/x.pdf --pages 1-10 --work x --dry-run

Writes data/ocr_staging/<work>/sarvam_pages<A>-<B>.json:
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
    """Page count via whichever of poppler / qpdf / PyMuPDF this box has.

    download_pdf() blocks a billed run on this answer, so it must not report
    "unreadable" merely because one tool is missing: poppler-utils is absent
    on some machines the pipeline is tested from, and pdfinfo was the only
    thing this asked.
    """
    try:
        info = subprocess.check_output(["pdfinfo", pdf], text=True, stderr=subprocess.DEVNULL)
        m = re.search(r"^Pages:\s+(\d+)", info, re.M)
        if m:
            return int(m.group(1))
    except Exception:  # noqa: BLE001
        pass
    try:
        out = subprocess.check_output(["qpdf", "--show-npages", pdf], text=True,
                                      stderr=subprocess.DEVNULL)
        return int(out.strip())
    except Exception:  # noqa: BLE001
        pass
    try:
        import pymupdf  # noqa: PLC0415
        return pymupdf.open(pdf).page_count
    except Exception:  # noqa: BLE001
        return None


def download_pdf(url: str, dest: str, attempts: int = 5) -> None:
    """Fetch the source PDF, and do not return until it is one.

    A bare urlretrieve lost Sarvam run #24 on JagatTest: archive.org answered
    a redirect with HTTP 500, the traceback surfaced as a plain exit 1, and
    the whole chunk had to be dispatched again. archive.org's 500s and resets
    are transient, so retry them; a file that downloads but does not parse is
    the same failure wearing a different hat, so check that too -- and check
    it HERE, before the first billed page, not after.
    """
    last = None
    for n in range(1, attempts + 1):
        try:
            urllib.request.urlretrieve(url, dest)
            pages = pdf_page_count(dest)
            if pages:
                log(f"downloaded {dest} ({pages} pages) on attempt {n}")
                return
            last = "downloaded, but pdfinfo counts 0 pages"
        except Exception as e:  # noqa: BLE001
            last = f"{type(e).__name__}: {e}"
        log(f"attempt {n}/{attempts} failed -- {last}")
        if n < attempts:
            time.sleep(2 ** n)
    raise SystemExit(f"no readable PDF after {attempts} attempts: {url} ({last})")


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


class SarvamJobError(RuntimeError):
    """A failure that still knows which job it was, so the receipt can name it."""

    def __init__(self, message, job_id=""):
        super().__init__(message)
        self.job_id = job_id


def digitise(pdf_slice: str, language: str, fmt: str, key: str, poll=6, max_wait=900) -> tuple[dict, bytes, str]:
    """Returns (status, payload, job_id).

    The job id is Sarvam's own handle on the work, and the only thing we
    could quote back to them: to ask what became of a chunk, whether a job
    that ended in a 500 was metered, or to claim pages billed and never
    delivered. It was written to the log and then dropped, so not one of the
    20,452 pages billed in September can be named to them today.
    """
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
        raise SarvamJobError(f"job {jid} {st}: {json.dumps(status)[:300]}", jid)
    _, db = http("GET", f"{API}/{jid}/download-url", key)
    d = json.loads(db)
    url = d.get("download_url") or d.get("url")
    if not url:
        raise RuntimeError(f"no download url: {db[:200]!r}")
    with urllib.request.urlopen(url, timeout=300) as r:
        payload = r.read()
    return status, payload, jid


#: Sarvam's own layout vocabulary, mapped onto the block tags the studio and
#: tools/ocr_review_merge.py understand. The point of the mapping is that each
#: Sarvam tag keeps its OWN slot: admin/ocr-studio.html's "all N" selects every
#: block the OCR tagged alike, so folding footnote and paragraph both onto <p>
#: would quietly destroy the distinction Sarvam paid attention to make.
LAYOUT_TAGS = {
    "headline": "h1",
    "section-title": "h2",
    "header": "h4",        # the running head at the top of a page
    "paragraph": "p",
    "footnote": "blockquote",
    "page-number": "div",
    "formula": "pre",
}
DEFAULT_TAG = "p"


def blocks_to_html(blocks: list[dict]) -> str:
    """One page of Sarvam blocks as HTML, in reading order.

    `layout_tag` is carried through as data-layout so nothing Sarvam decided is
    lost to the tag mapping, and the confidence rides along for a reviewer who
    wants to know which blocks to look at first.
    """
    rows = sorted(blocks, key=lambda b: b.get("reading_order", 0))
    out = []
    for b in rows:
        text = (b.get("text") or "").strip()
        if not text:
            continue
        lt = b.get("layout_tag") or ""
        tag = LAYOUT_TAGS.get(lt, DEFAULT_TAG)
        body = "<br>".join(
            line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            for line in text.split("\n"))
        attrs = f' data-layout="{lt}"' if lt else ""
        conf = b.get("confidence")
        if isinstance(conf, (int, float)):
            attrs += f' data-confidence="{conf:.2f}"'
        out.append(f"<{tag}{attrs}>{body}</{tag}>")
    return "\n".join(out)


def unpack(payload: bytes, fmt: str, pages: list[int]) -> list[dict]:
    """One entry per requested page.

    Sarvam's zip is not "one file per page". For a ten-page slice asked for as
    HTML it returned twelve members: a status manifest, ten per-page JSON files
    carrying every block with its layout_tag, reading order, bounding box and
    confidence, and the rendered HTML for the whole slice as ONE document.

    The first version of this function concatenated all twelve — manifest
    included — into a single "html" string filed under the first page. The
    output was unusable and the per-page structure Sarvam had already worked
    out was thrown away. The per-page JSON is the better source whatever format
    was asked for, so it is preferred when present; the flat document is the
    fallback for a response that does not carry it.
    """
    out = []
    members = []
    if payload[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(payload)) as z:
            names = sorted(z.namelist(),
                           key=lambda n: [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", n)])
            members = [z.read(n).decode("utf-8", "replace") for n in names if not n.endswith("/")]
    else:
        members = [payload.decode("utf-8", "replace")]

    # Per-page JSON: an object with page_num and blocks. The manifest has
    # page_count and no blocks, so it drops out here rather than being filed
    # as though it were a page of the book.
    per_page = {}
    leftovers = []
    for m in members:
        t = m.lstrip()
        if t[:1] == "{":
            try:
                o = json.loads(m)
            except ValueError:
                leftovers.append(m)
                continue
            if isinstance(o, dict) and "page_num" in o and isinstance(o.get("blocks"), list):
                per_page[int(o["page_num"])] = o
                continue
            if isinstance(o, dict) and "page_count" in o:
                continue                       # the status manifest
            leftovers.append(m)
        else:
            leftovers.append(m)

    if per_page:
        # page_num is 1-based within the slice; pages[] are the real PDF pages.
        for i, p in enumerate(pages, start=1):
            o = per_page.get(i)
            if o is None:
                out.append({"page": p, "ok": False, "error": "no page %d in the response" % i})
                continue
            blocks = o.get("blocks") or []
            entry = {"page": p, "ok": True, "blocks_count": len(blocks)}
            entry[fmt if fmt != "json" else "html"] = blocks_to_html(blocks)
            if fmt == "json":
                entry["blocks"] = blocks
            if o.get("image_width"):
                entry["image_size"] = [o.get("image_width"), o.get("image_height")]
            out.append(entry)
        return out

    docs = leftovers or members
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
    ap.add_argument("--out", default="data/ocr_staging")
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
        download_pdf(args.pdf_url, pdf)
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
        # One row per job: what we asked for, what Sarvam called it, how long
        # it took and how it ended. This is the receipt, and the only record
        # that can be quoted back to Sarvam about one specific chunk.
        "receipts": [],
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "pages": [],
    }
    for i, sl in enumerate(slices, 1):
        first, last = sl[0], sl[-1]
        part = os.path.join(tmpdir, f"slice_{first}-{last}.pdf")
        slice_pdf(pdf, first, last, part)
        log(f"[{i}/{len(slices)}] pages {first}-{last}")
        t0 = time.time()
        try:
            status, payload, jid = digitise(part, args.language, args.format, key)
            u = status.get("usage") or {}
            result["receipts"].append({
                "job_id": jid, "pages": [first, last], "page_count": len(sl),
                "status": str(status.get("status") or "completed"),
                "seconds": round(time.time() - t0, 1),
                "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "pages_succeeded": int(u.get("pages_succeeded") or len(sl)),
                "pages_failed": int(u.get("pages_failed") or 0),
                "error": "",
            })
            result["usage"]["pages_total"] += int(u.get("pages_total") or len(sl))
            result["usage"]["pages_succeeded"] += int(u.get("pages_succeeded") or len(sl))
            result["usage"]["pages_failed"] += int(u.get("pages_failed") or 0)
            result["usage"]["jobs"] += 1
            result["pages"].extend(unpack(payload, args.format, sl))
        except Exception as exc:  # noqa: BLE001
            log(f"  failed: {exc}")
            result["receipts"].append({
                "job_id": getattr(exc, "job_id", ""), "pages": [first, last],
                "page_count": len(sl), "status": "failed",
                "seconds": round(time.time() - t0, 1),
                "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "pages_succeeded": 0, "pages_failed": len(sl),
                "error": str(exc)[:200],
            })
            result["usage"]["pages_failed"] += len(sl)
            result["pages"].extend({"page": p, "ok": False, "error": str(exc)[:200]} for p in sl)
            # A 402 is the prepaid balance being empty. It will not come back
            # between one slice and the next, so carrying on only turns one
            # dead run into a whole dead batch: on 18 Sep 2026 every slice of
            # all 32 chunks kept calling, and 4,606 pages came back 402 while
            # the runs reported success.
            if "402" in str(exc):
                remaining = [p for later in slices[i:] for p in later]
                if remaining:
                    log(f"  402 Payment Required - the Sarvam balance is empty. "
                        f"Abandoning the remaining {len(remaining)} page(s) of this chunk.")
                    result["usage"]["pages_failed"] += len(remaining)
                    result["pages"].extend(
                        {"page": p, "ok": False,
                         "error": "not attempted: the Sarvam balance was empty earlier in this run"}
                        for p in remaining)
                result["aborted"] = "402 Payment Required - top up at dashboard.sarvam.ai"
                break
        if i < len(slices):
            time.sleep(7)  # 10 requests a minute, and each job is ≥2 requests

    outdir = os.path.join(args.out, args.work)
    os.makedirs(outdir, exist_ok=True)
    outp = os.path.join(outdir, f"sarvam_pages{pages[0]}-{pages[-1]}.json")
    with open(outp, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    log(f"wrote {outp}: {result['usage']}")
    # The file is written either way -- the evidence of what happened is worth
    # keeping. The EXIT CODE is what must tell the truth: a run that OCRed
    # nothing is not a success, however calmly it ends. All 32 chunks of the
    # 18 Sep 2026 batch returned 0 here with pages_succeeded == 0, so GitHub
    # showed 32 green checks for an empty account and nobody looked again.
    ok, failed = result["usage"]["pages_succeeded"], result["usage"]["pages_failed"]
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(f"## Sarvam Document AI\n\n`{outp}` — pages sent **{result['usage']['pages_total']}**, "
                     f"succeeded {result['usage']['pages_succeeded']}, failed {result['usage']['pages_failed']}, "
                     f"jobs {result['usage']['jobs']}. Sarvam bills per page from the prepaid balance.\n")
            if failed:
                fh.write(f"\n**{failed} page(s) did not OCR.** "
                         f"{result.get('aborted', 'See the staged file for the per-page error.')}\n")
    if ok == 0:
        log(f"FAILED: {failed} page(s) attempted, none succeeded. Nothing was staged that is worth reviewing.")
        return 1
    if failed:
        log(f"FAILED: {ok} page(s) succeeded but {failed} did not. "
            f"Re-run the missing range once the cause is fixed.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
