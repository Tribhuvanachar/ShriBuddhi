#!/usr/bin/env python3
"""
check_vishvasa.py — has anything moved across the 13 text-bearing repos of
github.com/vishvAsa since we last looked?

This is the vishvAsa-family sibling of tools/check_sources.py, split out into
its own small tool for two reasons, not one:

  1. It is thirteen git repos treated as one source family (a real Sanskrit
     digital library, not thirteen unrelated sites), so it reports one issue
     per run with a per-repo table rather than thirteen separate rows lost in
     a much longer general report.
  2. It gives a richer signal than the generic `github_commit` probe in
     check_sources.py -- not just "the sha changed" but how much: commits
     ahead and files touched, via the GitHub compare API, since that is what
     actually helps a human judge whether a change is worth a look now or can
     wait.

Like check_sources.py, THIS SCRIPT IMPORTS NOTHING. It only fingerprints and
reports. That split matters more here than anywhere else in this project:
per docs/PENDING.md's own explicit finding (K.E. Devanathan's 2006
Sribhashyaprakashah, hosted but not owned by vishvAsa), several works in this
family are NOT clearable for import on the site owner's personal permission
alone -- an auto-import job here would be a real legal mistake, not just an
engineering shortcut. A human reviews every work before it is pulled in; this
tool exists only to make sure that review starts promptly, not to skip it.

    python3 tools/check_vishvasa.py                  # check all 13, report
    python3 tools/check_vishvasa.py --only vishvasa_vedah_rk,vishvasa_puranam
    python3 tools/check_vishvasa.py --write-state     # remember what was seen

Reads  admin/config/sources.registry.json  (entries with checked_by ==
       "check-vishvasa.yml" -- that is how the repo list is discovered; it is
       not hardcoded here)
Writes admin/config/vishvasa.state.json    (with --write-state)
       the report on stdout, and to $GITHUB_STEP_SUMMARY when set.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY = os.path.join(REPO, "admin", "config", "sources.registry.json")
STATE = os.path.join(REPO, "admin", "config", "vishvasa.state.json")
UA = ("DGE-vishvasa-check/1.0 (+https://github.com/Tribhuvanachar/parabuddhi; "
      "non-commercial, educational; checks for updates every 15 days)")


def fetch_json(url, timeout=60, tries=3):
    last = None
    headers = {"User-Agent": UA, "Accept": "application/vnd.github+json"}
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as exc:
            # A 404 on /compare means one side of the range is gone (a force
            # push or a rebased branch upstream) -- worth reporting as such,
            # not worth retrying.
            if exc.code == 404:
                raise
            last = exc
        except Exception as exc:                                  # noqa: BLE001
            last = exc
        time.sleep(2 * (i + 1))
    raise last


def commit_info(repo, branch):
    d = fetch_json("https://api.github.com/repos/%s/commits/%s" % (repo, branch))
    sha = d.get("sha", "")
    date = (d.get("commit", {}).get("committer") or {}).get("date", "")
    return sha, date


def compare(repo, old_sha, new_sha):
    """How much moved between two commits: commits ahead and files touched.

    Both counts are the honest GitHub numbers for `old_sha...new_sha`, capped
    implicitly by the compare API itself (which stops listing files past 300 --
    fine here, a repo moving that much in one fortnight is itself the finding).
    """
    d = fetch_json("https://api.github.com/repos/%s/compare/%s...%s"
                    % (repo, old_sha, new_sha))
    # The compare API caps the `files` array at 300 entries even when more
    # changed; `d["files"]` being present but shorter than that cap is the
    # honest case, so this only needs the plain count -- a repo that hits the
    # cap in one fortnight is itself worth flagging, and the table still shows
    # "300" rather than silently rounding down.
    return {
        "commits_ahead": d.get("ahead_by", 0),
        "files_changed": len(d.get("files") or []),
    }


def load_registry_repos(only):
    reg = json.load(open(REGISTRY, encoding="utf-8"))["sources"]
    repos = [s for s in reg if s.get("checked_by") == "check-vishvasa.yml"]
    if only:
        repos = [s for s in repos if s["id"] in only]
    return repos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="comma-separated source ids")
    ap.add_argument("--write-state", action="store_true")
    args = ap.parse_args()

    only = {s for s in args.only.split(",") if s}
    srcs = load_registry_repos(only)
    if not srcs:
        print("No vishvasa_* entries found in the registry"
              + (" matching --only" if only else "") + ".", file=sys.stderr)
        return 1

    state = json.load(open(STATE, encoding="utf-8")) if os.path.exists(STATE) else {"sources": {}}
    old = state.get("sources", {})

    changed, unchanged, failed = [], [], []
    now = {}
    for src in srcs:
        sid = src["id"]
        gh = src.get("github", {})
        repo = gh.get("repo")
        branch = gh.get("branch", "content")
        if not repo:
            failed.append((sid, "registry entry has no github.repo"))
            continue
        try:
            sha, date = commit_info(repo, branch)
        except Exception as exc:                                  # noqa: BLE001
            failed.append((sid, "%s: %s" % (type(exc).__name__, str(exc)[:70])))
            continue
        commit12 = sha[:12]
        now[sid] = {"fingerprint": sha[:16],
                     "detail": {"repo": repo, "branch": branch,
                                "commit": commit12, "date": date}}
        prev = (old.get(sid) or {}).get("detail") or {}
        prev_commit = prev.get("commit")
        if not prev_commit:
            changed.append((sid, repo, "first look", {"commit": commit12, "date": date}))
        elif prev_commit != commit12:
            diff = {}
            try:
                diff = compare(repo, prev_commit, commit12)
            except Exception as exc:                              # noqa: BLE001
                diff = {"diff_error": "%s: %s" % (type(exc).__name__, str(exc)[:60])}
            detail = {"commit": commit12, "date": date, "was": prev_commit, **diff}
            changed.append((sid, repo, "CHANGED", detail))
        else:
            unchanged.append(sid)

    lines = ["## vishvAsa source check", "",
             "13-repo family; see tools/reports/vishvasa_gap_report.md for what each "
             "holds and admin/config/sources.registry.json's vishvasa_* entries for "
             "rights. **Nothing has been imported.**", ""]
    if changed:
        lines += ["| repo | what | commits ahead | files changed | new HEAD |",
                  "|---|---|---|---|---|"]
        for sid, repo, what, detail in changed:
            lines.append("| `%s` | %s | %s | %s | `%s` (%s) |" % (
                repo, what,
                detail.get("commits_ahead", "?" if what == "CHANGED" else "-"),
                detail.get("files_changed", "?" if what == "CHANGED" else "-"),
                detail.get("commit", ""), detail.get("date", "")[:10]))
        lines.append("")
    lines.append("%d changed · %d unchanged · %d unreachable"
                 % (len(changed), len(unchanged), len(failed)))
    if failed:
        lines += ["", "Unreachable:"] + ["- %s — %s" % f for f in failed]
    report = "\n".join(lines)
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(report + "\n")

    if args.write_state:
        merged = dict(old)
        merged.update(now)
        json.dump({"_readme": state.get("_readme", [
                       "Written by tools/check_vishvasa.py (run by check-vishvasa.yml). "
                       "Fingerprints only -- no content. Mirrors the shape of "
                       "admin/config/sources.state.json but tracks the 13 text-bearing "
                       "repos of github.com/vishvAsa as one family. See "
                       "tools/reports/vishvasa_gap_report.md for what each repo holds. "
                       "Delete an entry to force a first-look report for it.",
                   ]),
                   "checked_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   "sources": merged},
                  open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            # (baseline_note from the manually-seeded first version is dropped
            # once a real run has happened -- checked_at_utc above says when.)

    return 1 if failed and not (changed or unchanged) else 0


if __name__ == "__main__":
    sys.exit(main())
