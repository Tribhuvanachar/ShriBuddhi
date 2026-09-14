#!/usr/bin/env python3
"""Drive the Sarvam OCR workflow end to end, without a browser.

Until now a scan cost the lead four manual steps: open Actions, fill the
form, wait, find the run, download the zip, and hand it over. Everything
after "dispatch" is mechanical, so this does it: dispatch, poll, pull the
artifact, unpack it into one entry per page, and write the staged file.

THE ONE STEP THAT STAYS MANUAL, ON PURPOSE. `dispatch` spends money --
Sarvam bills per page and the key is a repository secret this session
never sees, so the workflow is the only way to reach it. That call is a
real-world transaction and is left to ask for approval every time rather
than being made quiet. `watch` and `fetch` are free and never prompt, so
a run that was already paid for can always be recovered without paying
again -- which is exactly what saved the 13 Sep run when unpack() was
still wrong.

Credentials: none are read or stored here. The session's proxy injects
them for api.github.com, which is why there is no token argument.

    python3 tools/ocr_auto.py runs                       # what has run lately
    python3 tools/ocr_auto.py fetch --run-id 123456789   # recover a paid run
    python3 tools/ocr_auto.py dispatch --pdf-path source/pdf/x.pdf \
            --pages 44-53 --work raghavendra_vijaya      # COSTS MONEY
"""
from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import time
import urllib.request
import zipfile

REPO = os.environ.get("DGE_REPO", "Tribhuvanachar/shribuddhi")
WORKFLOW = "ocr-sarvam.yml"
API = "https://api.github.com"

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))


def api(path: str, method: str = "GET", body: dict | None = None, raw: bool = False):
    url = path if path.startswith("http") else f"{API}/repos/{REPO}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/vnd.github+json")
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=120) as r:
        payload = r.read()
        if raw:
            return payload
        return json.loads(payload) if payload else {}


def cmd_runs(a):
    d = api(f"/actions/workflows/{WORKFLOW}/runs?per_page={a.limit}")
    if not d.get("workflow_runs"):
        print("no runs yet")
        return 0
    for r in d["workflow_runs"]:
        print(f"  {r['id']}  {r['status']:<12} {str(r['conclusion']):<10} "
              f"{r['created_at']}  {r.get('display_title','')[:48]}")
    return 0


def cmd_dispatch(a):
    inputs = {"pages": a.pages, "work": a.work, "lang": a.lang,
              "fmt": a.fmt, "mode": "real-run" if a.real else "dry-run"}
    if a.pdf_path:
        inputs["pdf_path"] = a.pdf_path
    if a.pdf_url:
        inputs["pdf_url"] = a.pdf_url
    n_pages = sum(len(range(int(p.split("-")[0]), int(p.split("-")[-1]) + 1))
                  for p in a.pages.split(","))
    print(f"About to dispatch a {'REAL (BILLED)' if a.real else 'dry'} run: "
          f"{n_pages} page(s) of {a.work}")
    api(f"/actions/workflows/{WORKFLOW}/dispatches", "POST",
        {"ref": a.ref, "inputs": inputs})
    print("dispatched; finding the run id …")
    for _ in range(20):
        time.sleep(3)
        d = api(f"/actions/workflows/{WORKFLOW}/runs?per_page=1")
        runs = d.get("workflow_runs") or []
        if runs:
            print(f"run id {runs[0]['id']}  {runs[0]['html_url']}")
            return 0
    print("dispatched, but the run id did not appear — check Actions", file=sys.stderr)
    return 1


def cmd_watch(a):
    """Poll until the run leaves 'in_progress'. Free, so it never prompts."""
    while True:
        r = api(f"/actions/runs/{a.run_id}")
        print(f"  {r['status']}  {r.get('conclusion') or ''}", flush=True)
        if r["status"] == "completed":
            return 0 if r["conclusion"] == "success" else 1
        time.sleep(a.interval)


def cmd_fetch(a):
    """Pull the artifact and unpack it. Never re-dispatches: a paid run's
    output is recoverable from the artifact long after the commit step of
    the workflow itself has failed."""
    arts = api(f"/actions/runs/{a.run_id}/artifacts").get("artifacts") or []
    if not arts:
        print("no artifacts on that run (expired after 90 days?)", file=sys.stderr)
        return 1
    art = arts[0]
    print(f"artifact {art['name']} ({art['size_in_bytes']:,} bytes)")
    blob = api(art["archive_download_url"], raw=True)

    outer = zipfile.ZipFile(io.BytesIO(blob))
    names = outer.namelist()
    print(f"  {len(names)} member(s): {', '.join(names[:6])}")

    os.makedirs(a.out, exist_ok=True)
    written = []
    for n in names:
        p = os.path.join(a.out, os.path.basename(n))
        with open(p, "wb") as fh:
            fh.write(outer.read(n))
        written.append(p)
        print(f"  wrote {p}")
    return 0 if written else 1


def expand_pages(spec: str) -> list[int]:
    out = []
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-", 1)
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


def cmd_ingest(a):
    """Fetch a run's artifact and stage it -- but only if it has the right shape.

    The 13 Sep run is why this validates instead of trusting. Its artifact
    carries `pages` with ONE entry whose html is the status manifest and all
    ten pages concatenated into a single string, because unpack() was wrong at
    the time. Staging that would have looked like success: a file appears, the
    index lists it, and the studio opens page 44 showing the whole slice with
    the manifest at the top. A paid run silently in the wrong shape is the
    failure this tool exists to stop, so a bad shape is refused loudly and the
    artifact is left on disk to be recovered by hand.
    """
    rc = cmd_fetch(a)
    if rc:
        return rc
    src = [os.path.join(a.out, f) for f in sorted(os.listdir(a.out)) if f.endswith(".json")]
    if not src:
        print("artifact held no JSON", file=sys.stderr)
        return 1
    with open(src[0], encoding="utf-8") as fh:
        doc = json.load(fh)

    pages = doc.get("pages")
    if not isinstance(pages, list) or not pages:
        print("no `pages` list in the artifact", file=sys.stderr)
        return 1

    want = expand_pages(a.pages) if a.pages else None
    got = [p.get("page") for p in pages if isinstance(p, dict)]
    if len(pages) == 1 and pages[0].get("page_end") not in (None, pages[0].get("page")):
        print(f"REFUSING: the artifact has 1 entry spanning pages "
              f"{pages[0].get('page')}-{pages[0].get('page_end')}. That is the "
              f"pre-fix unpack() shape -- the whole slice in one blob, manifest "
              f"included. Re-run on a workflow built after 085695d50f, or "
              f"recover by hand from {src[0]}.", file=sys.stderr)
        return 1
    if want and got != want:
        print(f"REFUSING: artifact covers {got} but {want} was asked for.", file=sys.stderr)
        return 1

    dest_dir = os.path.join("data", "ocr_staging", a.work)
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, os.path.basename(src[0]))
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
    print(f"staged {dest}: {len(pages)} page(s), engine={doc.get('engine')}")

    idx = os.path.join("tools", "build_ocr_staging_index.py")
    if os.path.exists(idx):
        subprocess.run([sys.executable, idx], check=False)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("runs"); r.add_argument("--limit", type=int, default=10)
    r.set_defaults(fn=cmd_runs)

    d = sub.add_parser("dispatch")
    d.add_argument("--pages", required=True)
    d.add_argument("--work", required=True)
    d.add_argument("--pdf-path", default="")
    d.add_argument("--pdf-url", default="")
    d.add_argument("--lang", default="sa-IN")
    d.add_argument("--fmt", default="html")
    d.add_argument("--ref", default="main")
    d.add_argument("--real", action="store_true", help="BILLED. Without this it is a dry run.")
    d.set_defaults(fn=cmd_dispatch)

    w = sub.add_parser("watch")
    w.add_argument("--run-id", required=True)
    w.add_argument("--interval", type=int, default=15)
    w.set_defaults(fn=cmd_watch)

    i = sub.add_parser("ingest")
    i.add_argument("--run-id", required=True)
    i.add_argument("--work", required=True)
    i.add_argument("--pages", default="", help="what was asked for, to check the artifact covers it")
    i.add_argument("--out", default="/tmp/claude-0/ocr_artifact")
    i.set_defaults(fn=cmd_ingest)

    f = sub.add_parser("fetch")
    f.add_argument("--run-id", required=True)
    f.add_argument("--out", default="/tmp/claude-0/ocr_artifact")
    f.set_defaults(fn=cmd_fetch)

    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
