#!/usr/bin/env python3
"""
build_repo_inventory.py — keep admin/config/repo-map.json honest, and render
docs/REPO_INVENTORY.md from it.

The manifest has two kinds of field, and this script only ever touches one:

  * hand-written — `category`, `purpose`, `notes`, `recommendation`, `reason`,
    `keep`, `display_name`, `source`, `pair`, `cost`. These say WHY a workflow
    or branch exists and what to do with it. No script can know that; a person
    (or a Claude session working for one) writes them and this script leaves
    them exactly as found.

  * generated — everything under `generated` on a workflow (its name, triggers,
    dispatch inputs, the secrets it uses, the scripts it calls, which
    directories it commits to) and everything under `snapshot` on a branch
    (ahead/behind main, merged or not, last commit). These are read from the
    workflow files and from git, and rewritten on every run.

A workflow file that exists on disk but not in the manifest is added with
`category: "unclassified"` so the admin page shows it (with a nudge to
classify it) instead of hiding it. A manifest entry whose file is gone is
dropped. The same for branches, against `origin/*`.

    python3 tools/build_repo_inventory.py            # refresh generated fields + render docs
    python3 tools/build_repo_inventory.py --check    # exit 1 if the committed manifest is stale
    python3 tools/build_repo_inventory.py --no-git   # skip the branch sweep (offline)

`--check` is what CI runs: a new workflow file without a manifest entry, or a
dispatch input that changed without the manifest following, fails the build,
so the admin page can never quietly show a stale form.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("PyYAML is needed: pip install pyyaml")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WF_DIR = os.path.join(ROOT, ".github", "workflows")
MANIFEST = os.path.join(ROOT, "admin", "config", "repo-map.json")
DOC = os.path.join(ROOT, "docs", "REPO_INVENTORY.md")

IST = timezone(timedelta(hours=5, minutes=30))

# Categories, in the order the admin page and the document show them. The
# label is the accordion heading; the blurb is the one line under it.
WORKFLOW_CATEGORIES = [
    ("source-sync",    "🌐 Online source syncers",
     "One card per outside website we take text from. Each asks the site whether anything changed since last time and reports; none of them imports on its own."),
    ("content-import", "📥 Importers — bring text in",
     "Fetch a corpus from its source and open a pull request (or republish a dist branch). These rewrite what readers see, so they are run by hand and reviewed."),
    ("enrichment",     "✨ Gemini enrichment — costs money",
     "Send text to Gemini for padaccheda, anvaya, summaries, reference resolution or dhātu meanings. Every run spends prepaid credits: estimate first (CLAUDE.md rule)."),
    ("ocr",            "🔎 OCR — scanned books to text",
     "Turn PDF page scans into staged JSON with Google Vision (₹) and, where the pipeline says so, a Gemini proofread (₹). Staged, never merged automatically."),
    ("index-links",    "🔍 Search index & cross-links",
     "Rebuild the things derived from the corpus: the search index, backlinks, sūtra/dhātu occurrence indexes, trackers, library status, the WordNet."),
    ("deploy",         "🚀 Deploy & infrastructure",
     "Firebase Hosting/Functions/Firestore deploys, the SEO page build, and secret pushes. Nothing here changes corpus data."),
    ("kamadhenu",      "🐄 Kamadhenu voice (TTS) experiments",
     "The IndicF5 fine-tuning programme on Hugging Face: Space deploys, diagnostics, log readers, and the one paid training job. Dated experiment scaffolding."),
    ("ci",             "✅ Tests",
     "Runs on every push and pull request. Never delete."),
    ("probe-oneoff",   "🧪 One-off probes — kept as a record",
     "Diagnostics that answered a question once (is this site reachable, is this scan alignable). They write nothing. Safe to delete; git history keeps them."),
    ("unclassified",   "❓ Not yet classified",
     "New workflow files this script found with no manifest entry. Give each a category, purpose and recommendation in admin/config/repo-map.json."),
]

BRANCH_CATEGORIES = [
    ("current-work",           "🔵 Current work — do not delete"),
    ("runtime-dist",           "🔵 Runtime / staging data branch — do not delete"),
    ("open-pr-needs-decision", "🔴 Needs a decision (open PR, stale content)"),
    ("review-needed",          "🟡 Review needed (unmerged, not obviously stale)"),
    ("merged-safe-delete",     "🟢 Safe to delete (fully merged into main)"),
    ("stale-superseded",       "🟢 Safe to delete (superseded — content already on main another way)"),
    ("unclassified",           "❓ Not yet classified"),
]

HAND_WORKFLOW_FIELDS = ("category", "display_name", "purpose", "notes", "recommendation",
                        "reason", "keep", "source", "pair", "cost", "trigger")
HAND_BRANCH_FIELDS = ("category", "purpose", "notes", "recommendation")


# ---------------------------------------------------------------- workflows
def cron_to_ist(expr: str) -> str:
    """Render a UTC cron as a sentence in IST, the project's reporting rule."""
    parts = expr.split()
    if len(parts) != 5:
        return expr
    minute, hour, dom, mon, dow = parts
    try:
        h, m = int(hour), int(minute)
    except ValueError:
        return expr + " (UTC)"
    local = (datetime(2000, 1, 1, h, m, tzinfo=timezone.utc)).astimezone(IST)
    when = local.strftime("%-I:%M %p").lower().replace("am", "am").replace("pm", "pm") + " IST"
    day_shift = local.date() != datetime(2000, 1, 1).date()
    dows = {"0": "Sunday", "1": "Monday", "2": "Tuesday", "3": "Wednesday", "4": "Thursday",
            "5": "Friday", "6": "Saturday", "7": "Sunday"}
    if dow != "*":
        d = dows.get(dow, dow)
        if day_shift:
            d = "the night after " + d
        return f"{when}, every {d}"
    if dom != "*":
        days = [x.strip() for x in dom.split(",")]
        if day_shift:
            days = [f"{x}+1" for x in days]
        suffix = " and ".join(f"{x}{'st' if x.endswith('1') and x != '11' else 'nd' if x.endswith('2') and x != '12' else 'rd' if x.endswith('3') and x != '13' else 'th'}" for x in days)
        return f"{when} on the {suffix} of every month"
    return f"{when} daily"


SCRIPT_RE = re.compile(
    r"(?:python3?|node)\s+(?:-u\s+)?((?:tools|importers|dge|kamadhenu|kamadhenu_dataset|genie_asr_benchmark)/[\w./\-]+\.(?:py|js))"
)
MODULE_RE = re.compile(r"python3?\s+-m\s+([\w.]+)")
SECRET_RE = re.compile(r"secrets\.([A-Z0-9_]+)")
PUSH_BRANCH_RE = re.compile(r"git push[^\n]*?(?:origin\s+)?(?:HEAD:|\+?)?refs/heads/([\w/\-]+)|git push[^\n]*?--force[^\n]*?origin\s+(?:HEAD:)?([\w/\-]+)")
PATH_HINT_RE = re.compile(r"(?:git add|add-paths:|path:|paths:)\s*\|?\s*([^\n]+)")

COST_SECRETS = {
    "GEMINI_API_KEY": "Gemini (₹ prepaid credits)",
    "VISION_API_KEY": "Google Vision OCR (₹)",
    "HF_TOKEN": "Hugging Face (ZeroGPU / Jobs — may bill)",
}


def read_workflow(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()
    doc = yaml.safe_load(raw) or {}
    # PyYAML turns the bare key `on` into boolean True.
    on = doc.get("on", doc.get(True, {})) or {}
    if isinstance(on, str):
        on = {on: None}
    if isinstance(on, list):
        on = {k: None for k in on}

    triggers = []
    schedule = []
    for cron in (on.get("schedule") or []):
        expr = cron.get("cron") if isinstance(cron, dict) else str(cron)
        schedule.append({"cron_utc": expr, "ist": cron_to_ist(expr)})
        triggers.append("schedule")
    if "workflow_dispatch" in on:
        triggers.append("manual")
    if "push" in on:
        p = on.get("push") or {}
        paths = p.get("paths") if isinstance(p, dict) else None
        branches = p.get("branches") if isinstance(p, dict) else None
        desc = "push"
        if branches:
            desc += " to " + ", ".join(branches)
        if paths:
            desc += " touching " + ", ".join(paths[:4]) + (" …" if len(paths) > 4 else "")
        triggers.append(desc)
    if "pull_request" in on:
        triggers.append("pull_request")
    if "workflow_run" in on:
        wr = on.get("workflow_run") or {}
        names = wr.get("workflows") if isinstance(wr, dict) else None
        triggers.append("after " + ", ".join(names) if names else "workflow_run")

    inputs = []
    wd = on.get("workflow_dispatch") or {}
    for name, spec in ((wd.get("inputs") or {}) if isinstance(wd, dict) else {}).items():
        spec = spec or {}
        entry = {
            "name": name,
            "label": str(spec.get("description") or name).strip(),
            "type": spec.get("type") or ("choice" if spec.get("options") else "string"),
            "default": spec.get("default", "" if not spec.get("options") else None),
            "required": bool(spec.get("required", False)),
        }
        if spec.get("options"):
            entry["options"] = [str(o) for o in spec["options"]]
            if entry["default"] is None:
                entry["default"] = entry["options"][0]
        inputs.append(entry)

    secrets = sorted(set(SECRET_RE.findall(raw)) - {"GITHUB_TOKEN"})
    scripts = sorted(set(SCRIPT_RE.findall(raw)) | {f"-m {m}" for m in MODULE_RE.findall(raw)})
    missing = [s for s in scripts if not s.startswith("-m") and not os.path.exists(os.path.join(ROOT, s))]

    cost = [COST_SECRETS[s] for s in secrets if s in COST_SECRETS]
    writes = []
    if "create-pull-request" in raw:
        writes.append("opens a pull request")
    if re.search(r"git push[^\n]*--force", raw) or "push --force" in raw:
        writes.append("force-pushes a dist/staging branch")
    elif re.search(r"\bgit push\b", raw):
        writes.append("commits directly to the branch it ran on")
    if "actions/upload-artifact" in raw:
        writes.append("uploads a run artifact")
    if "gh issue create" in raw:
        writes.append("opens a GitHub issue")
    if "firebase deploy" in raw or "firebase functions:secrets" in raw:
        writes.append("deploys to Firebase")
    if "actions/deploy-pages" in raw:
        writes.append("deploys GitHub Pages")
    if "huggingface" in raw.lower() or "hf_hub" in raw or "HfApi" in raw:
        writes.append("talks to Hugging Face")
    if not writes:
        writes.append("nothing in the repository (report only)")

    return {
        "name": doc.get("name") or os.path.basename(path),
        "triggers": triggers,
        "schedule": schedule,
        "inputs": inputs,
        "secrets": secrets,
        "cost": cost,
        "scripts": scripts,
        "missing_scripts": missing,
        "writes": writes,
        "lines": raw.count("\n") + 1,
    }


def refresh_workflows(manifest: dict) -> tuple[dict, list[str]]:
    on_disk = sorted(f for f in os.listdir(WF_DIR) if f.endswith((".yml", ".yaml")))
    old = manifest.get("workflows", {})
    new = {}
    problems = []
    for f in on_disk:
        entry = {k: v for k, v in (old.get(f) or {}).items() if k in HAND_WORKFLOW_FIELDS}
        if not entry.get("category"):
            entry["category"] = "unclassified"
            problems.append(f"workflow {f} has no manifest entry — classify it")
        entry.setdefault("keep", entry.get("recommendation", "keep") == "keep")
        entry["generated"] = read_workflow(os.path.join(WF_DIR, f))
        if entry["generated"]["missing_scripts"]:
            problems.append(f"workflow {f} references missing scripts: {entry['generated']['missing_scripts']}")
        new[f] = entry
    for f in old:
        if f not in new:
            problems.append(f"manifest lists {f} but the file is gone — entry dropped")
    return new, problems


# ---------------------------------------------------------------- branches
def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()


def branch_snapshot(name: str) -> dict | None:
    ref = f"origin/{name}"
    try:
        ahead = int(git("rev-list", "--count", f"origin/main..{ref}"))
        behind = int(git("rev-list", "--count", f"{ref}..origin/main"))
        merged = subprocess.call(["git", "merge-base", "--is-ancestor", ref, "origin/main"],
                                 cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0
        date, author, subject = git("log", "-1", "--format=%ad%x00%an%x00%s", "--date=short", ref).split("\x00")
    except subprocess.CalledProcessError:
        return None
    return {
        "merged_into_main": merged,
        "ahead_of_main": ahead,
        "behind_main": behind,
        "last_commit_date": date,
        "last_commit_subject": subject[:120],
        "last_author": author,
    }


def refresh_branches(manifest: dict) -> tuple[dict, list[str]]:
    try:
        names = [l.split("refs/heads/", 1)[1] for l in git("ls-remote", "--heads", "origin").splitlines() if "refs/heads/" in l]
    except subprocess.CalledProcessError:
        return manifest.get("branches", {}), ["could not list remote branches (offline?) — branch section left as is"]
    old = manifest.get("branches", {})
    new = {}
    problems = []
    for n in sorted(names):
        entry = {k: v for k, v in (old.get(n) or {}).items() if k in HAND_BRANCH_FIELDS}
        if not entry.get("category"):
            entry["category"] = "unclassified"
            problems.append(f"branch {n} has no manifest entry — classify it")
        snap = branch_snapshot(n) if n != "main" else {"merged_into_main": True, "ahead_of_main": 0, "behind_main": 0}
        if snap is None:
            snap = (old.get(n) or {}).get("snapshot", {})
            problems.append(f"branch {n} is not fetched locally — snapshot kept from last time")
        else:
            snap["checked_at"] = datetime.now(IST).strftime("%Y-%m-%d %H:%M IST")
        entry["snapshot"] = snap
        # A branch the manifest calls mergeable-and-deletable but git says has
        # unique commits is exactly the mistake this sweep exists to catch.
        if entry["category"] == "merged-safe-delete" and not snap.get("merged_into_main", False):
            problems.append(f"branch {n} is marked merged-safe-delete but has {snap.get('ahead_of_main')} commits main lacks")
        new[n] = entry
    for n in old:
        if n not in new:
            problems.append(f"manifest lists branch {n} but it no longer exists on origin — entry dropped")
    return new, problems


# ---------------------------------------------------------------- document
def render_doc(manifest: dict) -> str:
    out = []
    out.append("# Repository inventory — every workflow and branch, and what to do with it\n")
    out.append("_Generated by `tools/build_repo_inventory.py` from `admin/config/repo-map.json`. "
               "The same data drives the admin page **Repository & Workflows** "
               "(`admin/repo-map.html`). Edit the JSON, not this file._\n")
    out.append(f"_Last generated {datetime.now(IST).strftime('%d %b %Y, %-I:%M %p').lower()} IST._\n")

    wfs = manifest["workflows"]
    out.append("\n## Workflows\n")
    counts = {}
    for w in wfs.values():
        counts[w.get("recommendation", "keep")] = counts.get(w.get("recommendation", "keep"), 0) + 1
    out.append(f"{len(wfs)} workflow files. Recommendations: " +
               ", ".join(f"**{k}** {v}" for k, v in sorted(counts.items())) + ".\n")
    for cat, label, blurb in WORKFLOW_CATEGORIES:
        files = sorted(f for f, w in wfs.items() if w.get("category") == cat)
        if not files:
            continue
        out.append(f"\n### {label}\n\n_{blurb}_\n")
        for f in files:
            w = wfs[f]
            g = w["generated"]
            out.append(f"\n#### `{f}` — {w.get('display_name') or g['name']}\n")
            out.append(f"- **What it does:** {w.get('purpose', '_(no purpose written yet)_')}")
            if w.get("notes"):
                out.append(f"- **Notes:** {w['notes']}")
            trig = "; ".join(g["triggers"]) or "none"
            if g["schedule"]:
                trig += " — " + "; ".join(s["ist"] for s in g["schedule"])
            out.append(f"- **Runs when:** {trig}")
            out.append(f"- **Writes:** {', '.join(g['writes'])}")
            if g["cost"]:
                out.append(f"- **Costs money:** {', '.join(g['cost'])}")
            if g["inputs"]:
                out.append("- **Inputs:** " + ", ".join(f"`{i['name']}`" + (f" (default `{i['default']}`)" if i.get('default') not in (None, '') else "") for i in g["inputs"]))
            if g["scripts"]:
                out.append("- **Code it runs:** " + ", ".join(f"`{s}`" for s in g["scripts"]))
            rec = w.get("recommendation", "keep")
            out.append(f"- **Recommendation: {rec.upper()}** — {w.get('reason', '')}".rstrip(" —"))
    out.append("\n")

    brs = manifest["branches"]
    out.append("\n## Branches\n")
    out.append(f"{len(brs)} branches on origin.\n")
    for cat, label in BRANCH_CATEGORIES:
        names = sorted(n for n, b in brs.items() if b.get("category") == cat)
        if not names:
            continue
        out.append(f"\n### {label} ({len(names)})\n")
        out.append("| branch | ahead / behind main | last commit | purpose | recommendation |")
        out.append("|---|---|---|---|---|")
        for n in names:
            b = brs[n]
            s = b.get("snapshot", {})
            last = f"{s.get('last_commit_date', '?')} · {s.get('last_author', '')}"
            out.append(f"| `{n}` | {s.get('ahead_of_main', '?')} / {s.get('behind_main', '?')}"
                       f"{' · merged' if s.get('merged_into_main') else ''} | {last} | "
                       f"{(b.get('purpose') or '').replace('|', '/')} "
                       f"{('— ' + b['notes'].replace('|', '/')) if b.get('notes') else ''} | "
                       f"**{b.get('recommendation', '?')}** |")
    out.append("")
    return "\n".join(out)


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="report staleness and exit 1 instead of writing")
    ap.add_argument("--no-git", action="store_true", help="do not touch git (branch snapshots kept as they are)")
    args = ap.parse_args()

    with open(MANIFEST, encoding="utf-8") as fh:
        manifest = json.load(fh)
    before = json.dumps({"w": manifest.get("workflows"), "b": {k: {kk: vv for kk, vv in v.items() if kk != "snapshot"} for k, v in manifest.get("branches", {}).items()}}, sort_keys=True, ensure_ascii=False)

    workflows, problems = refresh_workflows(manifest)
    manifest["workflows"] = workflows
    if not args.no_git and not args.check:
        branches, more = refresh_branches(manifest)
        manifest["branches"] = branches
        problems += more
    manifest["generated_at"] = datetime.now(IST).strftime("%Y-%m-%d %H:%M IST")
    # The accordion order and headings, written once here and read by both the
    # admin page and the document, so the two can never disagree on a label.
    manifest["workflow_categories"] = [{"id": c, "label": l, "blurb": b} for c, l, b in WORKFLOW_CATEGORIES]
    manifest["branch_categories"] = [{"id": c, "label": l} for c, l in BRANCH_CATEGORIES]

    after = json.dumps({"w": manifest["workflows"], "b": {k: {kk: vv for kk, vv in v.items() if kk != "snapshot"} for k, v in manifest.get("branches", {}).items()}}, sort_keys=True, ensure_ascii=False)

    if args.check:
        hard = [p for p in problems if "no manifest entry" in p or "missing scripts" in p or "file is gone" in p]
        stale = before != after
        for p in problems:
            print("•", p)
        if stale:
            print("• generated fields differ from the committed manifest — run tools/build_repo_inventory.py and commit")
        if hard or stale:
            return 1
        print("repo-map.json is in step with .github/workflows/")
        return 0

    with open(MANIFEST, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    os.makedirs(os.path.dirname(DOC), exist_ok=True)
    with open(DOC, "w", encoding="utf-8") as fh:
        fh.write(render_doc(manifest))
    for p in problems:
        print("•", p)
    print(f"{len(manifest['workflows'])} workflows, {len(manifest.get('branches', {}))} branches → {os.path.relpath(MANIFEST, ROOT)}, {os.path.relpath(DOC, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
