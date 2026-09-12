#!/usr/bin/env python3
"""
sync_guard.py — the last check before an unattended importer's output is
allowed into a pull request.

Every source-sync workflow runs its importer and then this, on the working
tree, before `create-pull-request`. It answers three questions from the git
diff and refuses (exit 1) on the first bad answer:

  * did any data.json LOSE items?  A parser that no longer matches the
    site's markup writes "items": [] over a good file; a short cache writes
    a truncated grantha. Any file whose item count falls below --min-ratio
    of the committed count (default 0.8) fails the run.
  * did anything outside --scope change?  An importer writing to a folder it
    should not (the ashtadhyayi_layers.py paniniya_vyakarana/ incident) is
    caught here rather than in review.
  * did the run touch more files than --max-files?  A fortnightly delta
    should be a handful of granthas; hundreds means a re-crawl or a bug.

It also writes a short markdown summary (item deltas per file) to stdout and
$GITHUB_STEP_SUMMARY, which becomes the PR body's substance.

    python3 tools/sync_guard.py --scope data/darshana/vedanta/advaita --max-files 60
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def git(*a):
    return subprocess.check_output(["git", *a], cwd=REPO, text=True, stderr=subprocess.DEVNULL)


def items_in(text: str) -> int | None:
    try:
        d = json.loads(text)
    except ValueError:
        return None
    if isinstance(d, dict):
        if isinstance(d.get("items"), list):
            return len(d["items"])
        if isinstance(d.get("shlokas"), (list, dict)):
            return len(d["shlokas"])
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scope", action="append", required=True, help="path prefix the importer may touch (repeatable)")
    ap.add_argument("--min-ratio", type=float, default=0.8)
    ap.add_argument("--max-files", type=int, default=200)
    ap.add_argument("--allow", action="append", default=[], help="extra path prefixes allowed to change (state files)")
    args = ap.parse_args()

    status = git("status", "--porcelain", "--untracked-files=all").splitlines()
    changed = []
    for line in status:
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        changed.append((line[:2], path))
    if not changed:
        print("sync_guard: nothing changed.")
        return 0

    allowed = list(args.scope) + list(args.allow)
    outside = [p for _, p in changed if not any(p.startswith(a.rstrip("/") + "/") or p == a for a in allowed)]
    problems = []
    if outside:
        problems.append("changes outside the importer's scope: " + ", ".join(outside[:10]) + (" …" if len(outside) > 10 else ""))
    if len(changed) > args.max_files:
        problems.append(f"{len(changed)} files changed, cap is {args.max_files}")

    rows = []
    for st, p in changed:
        if not p.endswith(".json"):
            continue
        new_text = open(os.path.join(REPO, p), encoding="utf-8").read() if os.path.exists(os.path.join(REPO, p)) else ""
        try:
            old_text = git("show", f"HEAD:{p}")
        except subprocess.CalledProcessError:
            old_text = ""
        n_old, n_new = items_in(old_text) if old_text else None, items_in(new_text) if new_text else None
        if n_old is not None and n_new is not None:
            rows.append((p, n_old, n_new))
            if n_new < n_old * args.min_ratio:
                problems.append(f"{p}: items {n_old} → {n_new} (below {args.min_ratio:.0%} of the committed count)")
            if n_new == 0 and n_old > 0:
                problems.append(f"{p}: items emptied")
        elif n_old is None and n_new == 0:
            problems.append(f"{p}: new file with no items")

    lines = ["## Sync guard", "", f"{len(changed)} file(s) changed."]
    if rows:
        lines += ["", "| file | items before | after |", "|---|---:|---:|"]
        for p, a, b in rows[:80]:
            lines.append(f"| `{p}` | {a} | {b} |")
        if len(rows) > 80:
            lines.append(f"| … {len(rows) - 80} more | | |")
    if problems:
        lines += ["", "**REFUSED:**"] + [f"- {x}" for x in problems]
    else:
        lines += ["", "No item losses, nothing outside scope — safe to open a pull request."]
    report = "\n".join(lines)
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        open(summary, "a", encoding="utf-8").write(report + "\n")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
