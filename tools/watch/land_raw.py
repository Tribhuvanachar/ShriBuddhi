#!/usr/bin/env python3
"""
land_raw.py -- put what a watcher found into ParaBuddhi, unchanged, BEFORE anything else happens.

The rule (the lead, 1 Oct 2026): every import, OCR or weekly sync lands in ParaBuddhi first, as
the untouched base data. ShriBuddhi is where it is stripped of the origin's tags, rearranged and
stitched into the customised library; ParaBuddhi is what that was made from. If the landing
fails, nothing downstream may run -- so this exits non-zero when it cannot land something, and
the workflow's later steps depend on it.

What lands, by kind of source (tools/check_sources.py's probe kinds):

  github_commit       the repository at the commit that was seen, as a tarball under
                      source/_raw/<id>/ (kept: the newest two). A repository too large to
                      keep in git (> --max-mb) is recorded as a manifest with the exact commit
                      sha, which pins the upstream state just as well, and the report says so.
  everything else     the probe's evidence (fingerprint, counts, timestamp) as a small JSON,
                      plus, where ParaBuddhi already has an importer for the site
                      (import.yml: dvaitavedanta, setutila, anandamakaranda, meghamala), a
                      dispatch of that importer so the real crawl lands there too.

It writes only under source/_raw/ and import_config/watch_*.json in the ParaBuddhi checkout and
commits + pushes there (to main, as import.yml itself does). Run it with --dry-run to see the plan.

    python3 tools/watch/land_raw.py --pb pb --result result.json [--dry-run]
Environment: PARABUDDHI_TOKEN (push + actions:write on ParaBuddhi), GITHUB_TOKEN (read upstream).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request

PB_REPO = "Tribhuvanachar/ParaBuddhi"
#: watcher id -> the source name ParaBuddhi's import.yml takes
PB_IMPORTERS = {"dvaitavedanta": "dvaitavedanta", "setutila": "setutila",
                "anandamakaranda": "anandamakaranda", "srivaishnavan_meghamala": "meghamala"}


def _get(url, token=None, limit=None, timeout=600):
    h = {"User-Agent": "sarvamula-watch"}
    if token:
        h["Authorization"] = "Bearer " + token
    r = urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout)
    h256, n, chunks = hashlib.sha256(), 0, []
    while True:
        b = r.read(1 << 20)
        if not b:
            break
        n += len(b)
        if limit and n > limit:
            return None, n, None
        h256.update(b)
        chunks.append(b)
    return b"".join(chunks), n, h256.hexdigest()


def land_github(item, pb, max_mb, dry):
    repo = item["probe"]["repo"]
    branch = item["probe"].get("branch", "main")
    sid = item["id"]
    out = os.path.join(pb, "source", "_raw", sid)
    stamp = time.strftime("%Y%m%d", time.gmtime())
    commit = (item.get("detail") or {}).get("commit", "") or branch
    meta = {"id": sid, "repo": repo, "branch": branch, "commit": commit,
            "landed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    if dry:
        return "would fetch %s@%s (<= %d MB)" % (repo, commit, max_mb)
    os.makedirs(out, exist_ok=True)
    body, n, sha = _get("https://codeload.github.com/%s/tar.gz/%s" % (repo, commit if len(commit) >= 12 else branch),
                        os.environ.get("GITHUB_TOKEN"), limit=max_mb << 20)
    if body is None:
        meta.update({"snapshot": "too large to keep in git (> %d MB); upstream state pinned by commit sha" % max_mb})
        tree = _get("https://api.github.com/repos/%s/git/trees/%s?recursive=1" % (repo, commit),
                    os.environ.get("GITHUB_TOKEN"))[0]
        if tree:
            open(os.path.join(out, "tree_%s.json" % commit[:12]), "wb").write(tree)
        result = "pinned by sha (archive > %d MB)" % max_mb
    else:
        name = "%s_%s.tar.gz" % (stamp, commit[:12])
        open(os.path.join(out, name), "wb").write(body)
        meta.update({"snapshot": name, "bytes": n, "sha256": sha})
        olds = sorted(f for f in os.listdir(out) if f.endswith(".tar.gz"))
        for f in olds[:-2]:
            os.remove(os.path.join(out, f))
        result = "archived %s (%.1f MB)" % (name, n / 1e6)
    json.dump(meta, open(os.path.join(out, "LATEST.json"), "w"), indent=1)
    return result


def land_evidence(item, pb, dry):
    sid = item["id"]
    out = os.path.join(pb, "source", "_raw", sid)
    note = {"id": sid, "kind": item.get("kind"), "what": item.get("what"), "detail": item.get("detail"),
            "probe": item.get("probe"), "seen_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    if dry:
        return "would record evidence"
    os.makedirs(out, exist_ok=True)
    json.dump(note, open(os.path.join(out, "watch_%s.json" % time.strftime("%Y%m%d", time.gmtime())), "w",
                         encoding="utf-8"), ensure_ascii=False, indent=1)
    return "recorded evidence"


def dispatch_importer(sid, dry):
    src = PB_IMPORTERS.get(sid)
    if not src:
        return None
    if dry:
        return "would dispatch ParaBuddhi import.yml (%s)" % src
    tok = os.environ["PARABUDDHI_TOKEN"]
    req = urllib.request.Request(
        "https://api.github.com/repos/%s/actions/workflows/import.yml/dispatches" % PB_REPO,
        data=json.dumps({"ref": "main", "inputs": {"source": src, "args": ""}}).encode(),
        headers={"Authorization": "Bearer " + tok, "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json", "User-Agent": "sarvamula-watch"}, method="POST")
    urllib.request.urlopen(req, timeout=60).read()
    return "dispatched ParaBuddhi import.yml (%s)" % src


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--pb", required=True, help="ParaBuddhi checkout")
    ap.add_argument("--result", required=True, nargs="+", help="watcher result json file(s)")
    ap.add_argument("--max-mb", type=int, default=80)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--landed", default="", help="write {id: what happened} here")
    a = ap.parse_args(argv)

    changed = []
    for f in a.result:
        if os.path.exists(f):
            changed += json.load(open(f, encoding="utf-8")).get("changed", [])
    if not changed:
        print("nothing changed upstream; nothing to land")
        return 0
    if not a.dry_run and not os.environ.get("PARABUDDHI_TOKEN"):
        print("::error::%d source(s) changed but PARABUDDHI_TOKEN is not set, so nothing can be landed in "
              "ParaBuddhi. Add it (Settings -> Secrets -> Actions): a token with Contents + Actions "
              "read/write on %s. Nothing downstream may run until this works." % (len(changed), PB_REPO),
              file=sys.stderr)
        return 2
    landed, failed = {}, {}
    for item in changed:
        sid = item["id"]
        try:
            if item.get("kind") == "github_commit":
                msg = land_github(item, a.pb, a.max_mb, a.dry_run)
            else:
                msg = land_evidence(item, a.pb, a.dry_run)
            extra = dispatch_importer(sid, a.dry_run)
            landed[sid] = msg + ("; " + extra if extra else "")
        except Exception as exc:                                  # noqa: BLE001
            failed[sid] = "%s: %s" % (type(exc).__name__, str(exc)[:120])
    for k, v in landed.items():
        print("landed  %-26s %s" % (k, v))
    for k, v in failed.items():
        print("FAILED  %-26s %s" % (k, v))
    if a.landed:
        json.dump({"landed": landed, "failed": failed}, open(a.landed, "w"), indent=1)
    if a.dry_run:
        return 0
    if landed:
        git = lambda *c: subprocess.run(["git", "-C", a.pb, *c], check=True, capture_output=True, text=True)
        git("config", "user.name", "parabuddhi-watch")
        git("config", "user.email", "noreply@anthropic.com")
        git("add", "-A", "source/_raw", "import_config")
        if subprocess.run(["git", "-C", a.pb, "diff", "--cached", "--quiet"]).returncode:
            git("commit", "-m", "watch: land raw upstream data (%s)" % ", ".join(sorted(landed)))
            for attempt in range(3):
                p = subprocess.run(["git", "-C", a.pb, "push", "origin", "HEAD:main"], capture_output=True, text=True)
                if p.returncode == 0:
                    break
                subprocess.run(["git", "-C", a.pb, "pull", "--rebase", "origin", "main"], capture_output=True)
            else:
                print("::error::could not push to ParaBuddhi: " + p.stderr[-300:], file=sys.stderr)
                return 2
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
