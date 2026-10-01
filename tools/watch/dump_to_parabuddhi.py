#!/usr/bin/env python3
"""
dump_to_parabuddhi.py -- put a workflow's RAW output into ParaBuddhi, as a tarball, without fail.

For the importers, OCR runs and ingests that write into ShriBuddhi (import-kavya, ocr-*, ingest-*, ...):
before their results are built into `data/`, whatever they fetched or the engines returned goes to
ParaBuddhi `source/_raw/<id>/<UTC stamp>.tar.gz` (the newest --keep are retained), so the unchanged base
data exists somewhere that never gets rearranged. Exits non-zero when it cannot (no token, push refused):
a workflow step that follows it is then skipped, which is the point.

    python3 tools/watch/dump_to_parabuddhi.py --pb pb --id kavya --path .kavya_cache [--path other] [--keep 3]
Environment: PARABUDDHI_TOKEN is used by the workflow's clone of ParaBuddhi, not here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tarfile
import time


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--pb", required=True, help="ParaBuddhi checkout (cloned with a push-capable token)")
    ap.add_argument("--id", required=True, help="source/work id: becomes source/_raw/<id>/")
    ap.add_argument("--path", action="append", default=[], help="file or directory to archive (repeatable)")
    ap.add_argument("--files-from", default="", help="a text file with one path per line (kept with their directories)")
    ap.add_argument("--keep", type=int, default=3)
    ap.add_argument("--note", default="")
    a = ap.parse_args(argv)
    paths = [p for p in a.path if os.path.exists(p)]
    listed = []
    if a.files_from:
        listed = [l.strip() for l in open(a.files_from, encoding="utf-8") if l.strip() and os.path.exists(l.strip())]
    if not paths and not listed:
        print("::error::nothing to dump: none of %s exists" % a.path, file=sys.stderr)
        return 2
    out = os.path.join(a.pb, "source", "_raw", a.id)
    os.makedirs(out, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    name = "%s.tar.gz" % stamp
    full = os.path.join(out, name)
    with tarfile.open(full, "w:gz") as tf:
        for p in paths:
            tf.add(p, arcname=os.path.basename(p.rstrip("/")))
        for p in listed:                       # keep the directory structure: many files are called data.json
            tf.add(p, arcname=os.path.relpath(p))
    h = hashlib.sha256(open(full, "rb").read()).hexdigest()
    size = os.path.getsize(full)
    for old in sorted(f for f in os.listdir(out) if f.endswith(".tar.gz"))[:-a.keep]:
        os.remove(os.path.join(out, old))
    json.dump({"id": a.id, "archive": name, "bytes": size, "sha256": h, "from": a.path + ([a.files_from] if a.files_from else []), "note": a.note,
               "landed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "run": os.environ.get("GITHUB_SERVER_URL", "") + "/" + os.environ.get("GITHUB_REPOSITORY", "")
                      + "/actions/runs/" + os.environ.get("GITHUB_RUN_ID", "")},
              open(os.path.join(out, "LATEST.json"), "w"), indent=1)
    git = lambda *c, **k: subprocess.run(["git", "-C", a.pb, *c], capture_output=True, text=True, **k)
    git("config", "user.name", "parabuddhi-dump")
    git("config", "user.email", "noreply@anthropic.com")
    git("add", "-A", "source/_raw/%s" % a.id)
    if git("diff", "--cached", "--quiet").returncode == 0:
        print("nothing new to commit")
        return 0
    c = git("commit", "-m", "raw: %s (%.1f MB, %s)" % (a.id, size / 1e6, a.note or "workflow output"))
    if c.returncode:
        print("::error::commit failed: " + c.stderr[-300:], file=sys.stderr)
        return 2
    for _ in range(3):
        p = git("push", "origin", "HEAD:main")
        if p.returncode == 0:
            print("dumped %s (%.1f MB) to ParaBuddhi source/_raw/%s/%s" % (a.id, size / 1e6, a.id, name))
            return 0
        git("pull", "--rebase", "origin", "main")
    print("::error::could not push to ParaBuddhi: " + p.stderr[-300:], file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
