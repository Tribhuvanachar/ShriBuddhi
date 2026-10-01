#!/usr/bin/env python3
"""compose_report.py -- one markdown report from the per-source watcher results.

    python3 tools/watch/compose_report.py results/ > report.md

`results/` holds the JSON files each matrix job wrote (`result-<name>.json` from the probe,
`landed-<name>.json` from land_raw.py). Times are IST, as every report in this project is.
"""
from __future__ import annotations

import glob
import json
import os
import sys
import time


def ist_now():
    return time.strftime("%A %d %b %Y, %I:%M %p IST", time.gmtime(time.time() + 19800))


def main(argv=None):
    d = (argv or sys.argv[1:] or ["results"])[0]
    changed, unchanged, failed, skipped, landed, land_failed = [], [], [], [], {}, {}
    for f in sorted(glob.glob(os.path.join(d, "**", "result-*.json"), recursive=True)):
        r = json.load(open(f, encoding="utf-8"))
        changed += r.get("changed", [])
        unchanged += r.get("unchanged", [])
        failed += r.get("failed", [])
        skipped += r.get("skipped", [])
    for f in sorted(glob.glob(os.path.join(d, "**", "landed-*.json"), recursive=True)):
        r = json.load(open(f, encoding="utf-8"))
        landed.update(r.get("landed", {}))
        land_failed.update(r.get("failed", {}))
    out = ["# Weekly source watch — %s" % ist_now(), ""]
    out.append("**%d changed · %d unchanged · %d unreachable**" % (len(changed), len(unchanged), len(failed)))
    out.append("")
    if changed:
        out += ["## Changed upstream", ""]
        for c in changed:
            det = ", ".join("%s: %s" % (k, v) for k, v in (c.get("detail") or {}).items())
            out.append("- **%s** — %s%s" % (c["id"], c.get("what", ""), (" (" + det + ")") if det else ""))
            if c["id"] in landed:
                out.append("  - ParaBuddhi: %s" % landed[c["id"]])
            elif c["id"] in land_failed:
                out.append("  - ParaBuddhi: **FAILED** — %s" % land_failed[c["id"]])
            else:
                out.append("  - ParaBuddhi: **not landed**")
            if c.get("importer"):
                out.append("  - stitch step: %s" % c["importer"])
        out.append("")
    if land_failed:
        out += ["## Could not land in ParaBuddhi", ""] + ["- %s — %s" % kv for kv in land_failed.items()] + [""]
    if failed:
        out += ["## Unreachable", ""] + ["- %s — %s" % (f.get("id"), f.get("error")) for f in failed] + [""]
    if unchanged:
        out += ["## Unchanged", "", ", ".join(sorted(set(unchanged))), ""]
    if not changed and not failed:
        out += ["Nothing moved upstream this week.", ""]
    out += ["---", "Raw data lands in ParaBuddhi first (`source/_raw/<source>/`); ShriBuddhi's stitch step is "
            "run by a person after reading this. Nothing was published."]
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
