#!/usr/bin/env python3
"""
publish_clean_repo.py -- publish the site as a repository with no history.

A rename does not do this and neither does a fresh clone: both carry every
commit with them. This builds a tree from the content on disk and commits it
with NO PARENT, so the published repository contains exactly one commit and
there is nothing behind it to read.

It is meant to be run again for every release. Each run replaces that single
commit, so history never starts accumulating -- otherwise a month of releases
rebuilds the very thing this removes.

WHAT IT DOES NOT DO, and this matters before anyone relies on it: it cannot
un-publish what was already public. A repository that has been public may
already be held by Software Heritage (which archives public GitHub
repositories, history included), by the Wayback Machine, or by anyone who
cloned it. Deleting the old repository stops NEW readers; it does not reach
copies already made. Going forward-clean is achievable. Retroactive erasure
is not something any tool here can promise.

    python3 tools/publish_clean_repo.py --source ../buddhi --scan
    python3 tools/publish_clean_repo.py --source ../buddhi --out /tmp/jagat \
        --author "Name <email>" --message "Sarvamula digital library"
    ... then push it, which the script prints but never does itself.
"""
from __future__ import annotations

import argparse
import fnmatch
import os
import re
import shutil
import subprocess
import sys

# Paths that describe HOW the site is made rather than what it contains.
# Nothing here is content; every one of them is tooling, configuration or a
# record of process.
# `firebase` is here on the same grounds as `tools`, and it is the one people argue
# about, so it is worth naming: it is the server side of the site -- phone login,
# donations, WhatsApp, the admin workflow dispatcher and workflows.json, which is a
# plain-English catalogue of how the corpus is made. None of it is text anyone reads.
# It lives in the private repository as of 16 Sep 2026 and deploys from there.
# `firebase-hosting.json` goes with it: deploy configuration, whose ignore list names
# private-side directories that do not exist publicly. deploy-firebase-hosting.yml
# copies it into the checkout at deploy time.
EXCLUDE_DIRS = (".git", ".github", ".claude", "docs", "admin", "tools", "firebase",
                "node_modules", ".pytest_cache", "__pycache__")
EXCLUDE_FILES = ("CLAUDE.md", "PENDING.md", "HANDOFF.md", ".gitattributes",
                 "firebase-hosting.json")

# In-browser test harnesses that live beside the code they test. No page loads
# any of them -- they reference each other and nothing else does -- so they are
# tooling that happens to sit in js/ rather than in tools/. A few comments in
# js/ will name files that are no longer beside them; comments, not code.
EXCLUDE_GLOBS = ("*.test.js", "test-*.js")

# Words that name the private side of the project. A hit is not automatically
# a leak -- parabuddhi matches a line of the Narada Purana, and bhumandala is
# an ordinary Sanskrit word -- so this reports and never edits.
PRIVATE_NAMES = ("ShriBuddhi", "BrahmaBuddhi", "ParaBuddhi",
                 "Tribhuvanachar/bhumandala", "ocr-staging", "gemini-enrich")
TOOLING_NAMES = ("anthropic.com", "Claude Code", "claude-code")

# Names of the repository and host the site USED to live at. Unlike the two
# tuples above these need no judgement: a published release that still points
# at the old repository both tells a reader where to go looking and sends real
# traffic to a URL that will stop existing. They are reported separately and
# loudly for exactly that reason.
#
# 16 Sep 2026: added after a scan reported the tree clean while sitemap.xml
# carried 1,245 absolute URLs under the old name. The scanner only ever looked
# for the PRIVATE side, so the repository's own former name walked straight
# past it -- the commit that swept the old name out of 75 files had left the
# generated files behind, and nothing was watching for the regression.
STALE_NAMES = ("tribhuvanachar.github.io", "Tribhuvanachar/buddhi",
               "Tribhuvanachar/bhumandala", "JagatTest", "/Buddhi/")

TEXT_SUFFIXES = (".js", ".html", ".json", ".css", ".md", ".txt", ".xml", ".yml", ".yaml")


def walk(source: str):
    """Every file that would be published, relative to the source root."""
    for root, dirs, files in os.walk(source):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for name in files:
            if name in EXCLUDE_FILES:
                continue
            if any(fnmatch.fnmatch(name, g) for g in EXCLUDE_GLOBS):
                continue
            full = os.path.join(root, name)
            yield full, os.path.relpath(full, source)


def scan(source: str) -> list[tuple[str, str, str]]:
    """[(relative path, term, the line it sits on)] for a person to judge."""
    hits = []
    for full, rel in walk(source):
        if not rel.endswith(TEXT_SUFFIXES):
            continue
        try:
            text = open(full, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        for term in PRIVATE_NAMES + TOOLING_NAMES + STALE_NAMES:
            for match in re.finditer(re.escape(term), text, re.I):
                line_start = text.rfind("\n", 0, match.start()) + 1
                line_end = text.find("\n", match.end())
                line = text[line_start:line_end if line_end > 0 else len(text)]
                hits.append((rel, term, line.strip()[:110]))
                break              # one example per term per file is enough
    return hits


def stage(source: str, out: str) -> int:
    """Copy the publishable tree to a clean directory with no .git."""
    if os.path.exists(out):
        shutil.rmtree(out)
    count = 0
    for full, rel in walk(source):
        target = os.path.join(out, rel)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copy2(full, target)
        count += 1
    return count


def commit(out: str, author: str, message: str) -> str:
    """One commit, no parent. Author and date are the caller's, not git's
    guess from the environment -- the point is a clean, deliberate record."""
    def run(*args, **kw):
        return subprocess.run(args, cwd=out, check=True, capture_output=True, text=True, **kw)

    run("git", "init", "-q", "-b", "main")
    run("git", "config", "user.name", author.split("<")[0].strip())
    run("git", "config", "user.email", author.split("<")[1].rstrip(">").strip())
    run("git", "add", "-A")
    run("git", "commit", "-q", "--no-gpg-sign", "-m", message)
    return run("git", "rev-parse", "HEAD").stdout.strip()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 2)[1])
    ap.add_argument("--source", required=True, help="the checkout holding the content")
    ap.add_argument("--out", default="", help="where to build the clean tree")
    ap.add_argument("--author", default="", help='"Name <email>" for the single commit')
    ap.add_argument("--message", default="", help="that commit's message")
    ap.add_argument("--scan", action="store_true",
                    help="report what names the private side of the project, and stop")
    args = ap.parse_args(argv)

    files = list(walk(args.source))
    print("%d file(s) would be published from %s" % (len(files), args.source))
    print("excluded: %s" % ", ".join(EXCLUDE_DIRS + EXCLUDE_FILES + EXCLUDE_GLOBS))
    print()

    hits = scan(args.source)
    stale = [h for h in hits if h[1] in STALE_NAMES]
    private = [h for h in hits if h[1] not in STALE_NAMES]

    if stale:
        print("STOP. %d file(s) still name the old repository or host. These are not"
              " judgement calls -- every one is wrong:" % len({h[0] for h in stale}))
        for rel, term, line in stale[:40]:
            print("  %-34s %-26s %s" % (rel[:34], term, line[:66]))
        if len({h[0] for h in stale}) > 40:
            print("  ... and %d more file(s)" % (len({h[0] for h in stale}) - 40))
        print()

    if private:
        print("%d file(s) name the private side of the project -- READ THESE, they are"
              " not all leaks:" % len({h[0] for h in private}))
        for rel, term, line in private[:40]:
            print("  %-34s %-22s %s" % (rel[:34], term, line[:70]))
    else:
        print("nothing found naming the private side of the project.")
    if args.scan:
        return 1 if stale else 0

    if stale:
        print("\nRefusing to build: fix the old-name references first, or this release"
              "\npublishes them. Nothing has been written.", file=sys.stderr)
        return 3

    if not (args.out and args.author and args.message):
        print("\n--out, --author and --message are all required to build.", file=sys.stderr)
        return 2

    print()
    n = stage(args.source, args.out)
    sha = commit(args.out, args.author, args.message)
    print("staged %d file(s) and made ONE commit with no parent: %s" % (n, sha[:12]))
    print("\nto publish, from %s:" % args.out)
    print("    git remote add origin https://github.com/<owner>/<repo>.git")
    print("    git push --force origin main")
    print("\nforce, because every release replaces that one commit rather than adding to it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
