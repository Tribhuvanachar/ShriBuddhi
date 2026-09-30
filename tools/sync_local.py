#!/usr/bin/env python3
"""
sync_local.py -- push the edits made in a local ShriBuddhi checkout to GitHub.

For the person editing on a desktop (folders added, renamed, moved; data
edited). One command, and it does not send anything until you say so:

    python3 tools/sync_local.py                 # show what WOULD be pushed
    python3 tools/sync_local.py --go -m "Rename stotra folders"
    python3 tools/sync_local.py --go --reindex  # ...and start the search re-index

What --go does, in order, stopping at the first problem:
  1. refuses if you are mid-merge/rebase, or on a detached HEAD;
  2. checks the files you changed are Unicode NFC (the CI gate that went red on
     20 Sep 2026) and offers the one-line fix instead of pushing a red build;
  3. git add -A, git commit;
  4. git pull --rebase (so a teammate's push never makes yours fail);
  5. git push to the branch you are on;
  6. with --reindex, starts reindex.yml through tools/dispatch_workflow.py
     (needs GH_TOKEN in your environment; without it, prints the Actions link).

It never force-pushes, never rewrites other people's commits and never touches
a branch other than the one checked out. Folder renames: use `git mv`, or just
rename in your file manager -- `git add -A` records a rename either way.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = "Tribhuvanachar/ShriBuddhi"


def git(*args, check=True, capture=True):
    r = subprocess.run(["git", *args], cwd=ROOT, text=True,
                       capture_output=capture)
    if check and r.returncode != 0:
        sys.exit("git %s failed:\n%s" % (" ".join(args), (r.stderr or r.stdout).strip()))
    return (r.stdout or "").strip()


def in_progress() -> str:
    gd = git("rev-parse", "--git-dir")
    gd = gd if os.path.isabs(gd) else os.path.join(ROOT, gd)
    for marker, what in (("MERGE_HEAD", "a merge"), ("rebase-merge", "a rebase"),
                         ("rebase-apply", "a rebase"), ("CHERRY_PICK_HEAD", "a cherry-pick")):
        if os.path.exists(os.path.join(gd, marker)):
            return what
    return ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--go", action="store_true", help="actually commit and push (default: show only)")
    ap.add_argument("-m", "--message", default="", help="commit message")
    ap.add_argument("--reindex", action="store_true", help="start the search re-index after pushing")
    a = ap.parse_args()

    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    if branch == "HEAD":
        sys.exit("Detached HEAD: check out a branch first (git checkout main).")
    busy = in_progress()
    if busy:
        sys.exit("You are in the middle of %s. Finish or abort it first." % busy)

    porcelain = git("status", "--porcelain")
    changed = [l for l in porcelain.splitlines() if l.strip()]
    print("Branch: %s   Repo: %s" % (branch, REPO))
    if not changed:
        print("Nothing to push: no local changes.")
        ahead = git("rev-list", "--count", "@{u}..HEAD", check=False)
        if ahead and ahead != "0":
            print("(%s commit(s) are committed but not pushed; --go will push them.)" % ahead)
            if not a.go:
                return 0
        else:
            return 0
    else:
        print("%d changed path(s):" % len(changed))
        for l in changed[:40]:
            print("  " + l)
        if len(changed) > 40:
            print("  ... and %d more" % (len(changed) - 40))

    if not a.go:
        print("\nDry run. Nothing was committed or pushed. Re-run with --go to push.")
        return 0

    if changed:
        nfc = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "normalize_nfc.py"), "--check"],
                             cwd=ROOT, text=True, capture_output=True)
        if nfc.returncode != 0:
            print(nfc.stdout.strip())
            sys.exit("\nSome data files are not Unicode NFC, and CI would fail on them.\n"
                     "Fix with:  python3 tools/normalize_nfc.py --fix   then run this again.")
        msg = a.message.strip() or "Local edits from desktop (%d path(s))" % len(changed)
        git("add", "-A")
        git("commit", "-m", msg)
        print("Committed: " + msg)

    print("Pulling others' changes (rebase)...")
    r = subprocess.run(["git", "pull", "--rebase", "origin", branch], cwd=ROOT, text=True, capture_output=True)
    if r.returncode != 0:
        print(r.stdout + r.stderr)
        sys.exit("\nThe pull hit a conflict in the files above. Nothing was pushed.\n"
                 "Resolve them, then:  git rebase --continue   and run this again.\n"
                 "To give up:  git rebase --abort")
    print("Pushing...")
    r = subprocess.run(["git", "push", "-u", "origin", branch], cwd=ROOT, text=True, capture_output=True)
    if r.returncode != 0:
        print(r.stdout + r.stderr)
        sys.exit("\nPush failed (see above). Your commit is safe locally.")
    print("Pushed to origin/%s." % branch)

    if a.reindex:
        script = os.path.join(ROOT, "tools", "dispatch_workflow.py")
        if os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"):
            subprocess.run([sys.executable, script, "reindex.yml", "--repo", REPO, "--ref", branch], cwd=ROOT)
        else:
            print("No GH_TOKEN in the environment, so the re-index was not started.\n"
                  "Start it here: https://github.com/%s/actions/workflows/reindex.yml" % REPO)
    return 0


if __name__ == "__main__":
    sys.exit(main())
