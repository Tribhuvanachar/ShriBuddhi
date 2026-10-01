#!/usr/bin/env python3
"""
scheduler.py -- start the workflows that config/schedules.json says are due.

GitHub Actions can only read a cron from inside a workflow file, so changing "when" meant editing YAML.
This inverts it: ONE workflow (scheduler.yml) wakes every hour and runs this, which reads
config/schedules.json (times in IST, 5-field cron) and starts, through the workflow-dispatch API, every
enabled job whose cron fell in the last 70 minutes. Editing the JSON (by hand, or from admin/schedules.html)
changes the timing from the next hour on.

Safety: a job is skipped if its workflow already has a run created in the window (so a late or repeated
wake-up cannot fire it twice, and a run you started by hand counts). The window is longer than the wake-up
interval on purpose, to survive GitHub delaying a scheduled run.

    python3 tools/watch/scheduler.py --dry-run [--at 2026-10-04T20:31:00Z]   # what would start
    python3 tools/watch/scheduler.py                                          # start them (needs GITHUB_TOKEN)
    python3 tools/watch/scheduler.py --next 3                                 # the next 3 times each job will run
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG = os.path.join(ROOT, "config", "schedules.json")
IST = dt.timedelta(hours=5, minutes=30)
WINDOW_MIN = 70


def _field(spec, lo, hi):
    out = set()
    for part in spec.split(","):
        step = 1
        if "/" in part:
            part, s = part.split("/", 1)
            step = int(s)
        if part in ("*", ""):
            a, b = lo, hi
        elif "-" in part:
            a, b = (int(x) for x in part.split("-", 1))
        else:
            a = b = int(part)
            if "/" in spec and spec.split("/")[0] == part:
                b = hi
        out.update(range(a, b + 1, step))
    return out


def parse_cron(expr):
    f = expr.split()
    if len(f) != 5:
        raise ValueError("cron needs 5 fields: %r" % expr)
    minute, hour, dom, month, dow = f
    return {"minute": _field(minute, 0, 59), "hour": _field(hour, 0, 23), "dom": _field(dom, 1, 31),
            "month": _field(month, 1, 12), "dow": {d % 7 for d in _field(dow, 0, 7)},
            "dom_star": dom.startswith("*"), "dow_star": dow.startswith("*")}


def matches(c, t):
    """t: naive datetime already in IST."""
    if t.minute not in c["minute"] or t.hour not in c["hour"] or t.month not in c["month"]:
        return False
    dom_ok, dow_ok = t.day in c["dom"], ((t.weekday() + 1) % 7) in c["dow"]
    if c["dom_star"] or c["dow_star"]:       # standard cron: when both are restricted, either may match
        return dom_ok and dow_ok
    return dom_ok or dow_ok


def due(cron, now_utc, window=WINDOW_MIN):
    c = parse_cron(cron)
    end = (now_utc.replace(tzinfo=None) + IST).replace(second=0, microsecond=0)
    return any(matches(c, end - dt.timedelta(minutes=m)) for m in range(window))


def next_runs(cron, after_utc, n=3, horizon_days=800):
    c = parse_cron(cron)
    t = (after_utc.replace(tzinfo=None) + IST).replace(second=0, microsecond=0)
    out = []
    for _ in range(horizon_days * 1440):
        t += dt.timedelta(minutes=1)
        if matches(c, t):
            out.append(t)
            if len(out) == n:
                break
    return out


def load(path=CONFIG):
    return json.load(open(path, encoding="utf-8"))["jobs"]


def _api(method, url, token, body=None):
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
                                          "Content-Type": "application/json", "User-Agent": "sarvamula-scheduler"})
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read()
    return json.loads(raw) if raw else {}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--at", default="", help="pretend it is this UTC time (ISO)")
    ap.add_argument("--next", type=int, default=0, help="print the next N run times (IST) per job and exit")
    ap.add_argument("--config", default=CONFIG)
    a = ap.parse_args(argv)
    now = dt.datetime.fromisoformat(a.at.replace("Z", "")) if a.at else dt.datetime.utcnow()
    jobs = load(a.config)
    if a.next:
        for j in jobs:
            nxt = next_runs(j["cron"], now, a.next)
            print("%-26s %-10s %s" % (j["id"], "on" if j.get("enabled", True) else "PAUSED",
                                       ", ".join(t.strftime("%a %d %b %H:%M IST") for t in nxt)))
        return 0
    repo, token = os.environ.get("GITHUB_REPOSITORY", ""), os.environ.get("GITHUB_TOKEN", "")
    ref = os.environ.get("DEFAULT_BRANCH", "main")
    started, skipped = [], []
    for j in jobs:
        if not j.get("enabled", True):
            continue
        try:
            is_due = due(j["cron"], now)
        except ValueError as exc:
            print("::error::job %s has a bad cron: %s" % (j["id"], exc), file=sys.stderr)
            continue
        if not is_due:
            continue
        if a.dry_run or not (repo and token):
            started.append(j["id"] + (" (dry run)" if a.dry_run else " (no GITHUB_TOKEN)"))
            continue
        since = (now - dt.timedelta(minutes=WINDOW_MIN)).strftime("%Y-%m-%dT%H:%M:%SZ")
        runs = _api("GET", "https://api.github.com/repos/%s/actions/workflows/%s/runs?created=>=%s&per_page=1"
                    % (repo, j["workflow"], since), token)
        if runs.get("total_count"):
            skipped.append("%s (a run already exists since %s)" % (j["id"], since))
            continue
        _api("POST", "https://api.github.com/repos/%s/actions/workflows/%s/dispatches" % (repo, j["workflow"]), token,
             {"ref": ref, "inputs": {k: str(v) for k, v in (j.get("inputs") or {}).items()}})
        started.append(j["id"])
    print("started:", ", ".join(started) or "nothing is due")
    for s in skipped:
        print("skipped:", s)
    summ = os.environ.get("GITHUB_STEP_SUMMARY")
    if summ:
        with open(summ, "a", encoding="utf-8") as fh:
            fh.write("### Scheduler\n- started: %s\n%s\n" % (", ".join(started) or "nothing due",
                                                            "".join("- skipped: %s\n" % s for s in skipped)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
