#!/usr/bin/env python3
"""harvest_ocr_receipts.py -- read every staged OCR file and record what it cost.

The staging branches are the only first-hand record of what the OCR engines
actually did. Workflow exit codes are not: on 18 Sep 2026 runs reported
success over 4,606 pages Sarvam had refused. So this reads the staged files
themselves, off `origin/ocr-staging/*`, and writes one row per file.

It needs no network. The branches are already fetched, and `git ls-tree` and
`git cat-file` read them from the local object store -- fetching each branch
in turn takes about three minutes each and is pure waste.

    python3 tools/harvest_ocr_receipts.py --out admin/config/ocr_receipts.json
"""
import argparse, json, os, subprocess, sys

README = [
    "Every staged OCR file this project holds, read off the ocr-staging",
    "branches themselves by tools/harvest_ocr_receipts.py -- not from workflow",
    "exit codes, which reported success over 5,342 pages that were refused.",
    "One row per staged file: which engine, which source PDF, when it was",
    "written, what its own usage block claims, and every page-level error.",
    "",
    "'receipts' is empty for every row harvested before 21 Sep 2026 and will",
    "not be empty again. Sarvam returns a job_id per chunk; sarvam_docai.py",
    "logged it and dropped it, so none of the 20,452 pages billed in September",
    "can be named back to Sarvam. It is now written into the staged file along",
    "with each job's duration and outcome.",
]


def branches():
    out = subprocess.run(["git", "branch", "-r"], capture_output=True, text=True).stdout
    return [b for b in out.split() if b.startswith("origin/ocr-staging/")]


def harvest_one(ref):
    ls = subprocess.run(["git", "ls-tree", "-r", "-l", ref],
                        capture_output=True, text=True).stdout
    rows = []
    for line in ls.splitlines():
        parts = line.split(None, 4)
        if len(parts) < 5:
            continue
        _mode, _typ, sha, size, path = parts
        base = os.path.basename(path)
        if "/ocr_staging/" not in path:
            continue
        if not (base.startswith("sarvam_") or base.startswith("vision_")):
            continue
        blob = subprocess.run(["git", "cat-file", "blob", sha], capture_output=True).stdout
        try:
            d = json.loads(blob)
        except Exception:                                   # noqa: BLE001
            continue
        errs = {}
        for p in (d.get("pages") or []):
            if isinstance(p, dict) and p.get("ok") is False:
                e = str(p.get("error") or "")[:70]
                errs[e] = errs.get(e, 0) + 1
        src = d.get("source")
        rows.append({
            "file": base, "bytes": int(size),
            "engine": d.get("engine") or
                      ("google-vision" if base.startswith("vision_") else "sarvam-docai"),
            "source_pdf": (src or {}).get("pdf") if isinstance(src, dict) else src,
            "pdf_pages": (src or {}).get("pdf_pages") if isinstance(src, dict) else None,
            "generated_at": d.get("generated_at"), "started_at": d.get("started_at"),
            "usage": d.get("usage") or {}, "receipts": d.get("receipts") or [],
            "page_entries": len(d.get("pages") or []), "errors": errs,
        })
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 2)[1])
    ap.add_argument("--out", default="admin/config/ocr_receipts.json")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    refs = branches()
    works, files, fails = {}, 0, 0
    for i, ref in enumerate(refs, 1):
        work = ref.split("ocr-staging/", 1)[1]
        rows = harvest_one(ref)
        works[work] = rows
        files += len(rows)
        fails += sum(sum(r["errors"].values()) for r in rows)
        if not args.quiet:
            print("%3d/%d %-52s %d file(s)" % (i, len(refs), work[:52], len(rows)))
    payload = {"_readme": README,
               "harvested_on": __import__("time").strftime("%Y-%m-%d"),
               "works": works}
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print("\n%d work(s), %d staged file(s), %d page-level failure(s)" % (len(works), files, fails))
    print("wrote %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
