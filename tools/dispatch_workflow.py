#!/usr/bin/env python3
"""
dispatch_workflow.py -- start one GitHub Actions workflow, and nothing else.

Why a script rather than a curl line: the permission rule that lets a session
run workflows has to name something. Naming `curl` names every request curl
can make. Naming this file names exactly one action -- POST to the
workflow-dispatch endpoint of a repository in this project -- which is a rule
a person can read and agree to.

It refuses anything outside that: another owner, another endpoint, another
verb. There is no code path here that sends anything else.

    python3 tools/dispatch_workflow.py ocr-sarvam.yml \
        --repo Tribhuvanachar/ShriBuddhi --ref main \
        -f pdf_url=https://... -f pages=19-712 -f mode=dry-run

    python3 tools/dispatch_workflow.py ocr-sarvam.yml --show   # print, send nothing
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

# The only owner this script will talk to. A workflow dispatch spends money and
# uses repository secrets; it is not a thing to make generic.
OWNER = "Tribhuvanachar"
API = "https://api.github.com"


def token() -> str:
    for name in ("GH_TOKEN", "GITHUB_TOKEN"):
        value = os.environ.get(name)
        if value:
            return value
    raise SystemExit("no GH_TOKEN or GITHUB_TOKEN in the environment")


def request(method: str, url: str, body: dict | None = None) -> tuple[int, bytes]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer %s" % token())
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data is not None:
        # The egress proxy in front of the API rejects a body without it (415).
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def newest_run(repo: str, workflow: str) -> dict | None:
    status, body = request("GET", "%s/repos/%s/actions/workflows/%s/runs?per_page=1"
                                  % (API, repo, workflow))
    if status != 200:
        return None
    runs = json.loads(body).get("workflow_runs") or []
    return runs[0] if runs else None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 2)[1])
    ap.add_argument("workflow", help="workflow file name, e.g. ocr-sarvam.yml")
    ap.add_argument("--repo", default="%s/ShriBuddhi" % OWNER)
    ap.add_argument("--ref", default="main")
    ap.add_argument("-f", "--field", action="append", default=[],
                    metavar="KEY=VALUE", help="a workflow input; repeatable")
    ap.add_argument("--show", action="store_true",
                    help="print what would be sent and send nothing")
    args = ap.parse_args(argv)

    if not args.repo.startswith(OWNER + "/"):
        raise SystemExit("this script only dispatches in %s/*, not %r" % (OWNER, args.repo))
    if "/" in args.workflow or not args.workflow.endswith((".yml", ".yaml")):
        raise SystemExit("workflow must be a file name like ocr-sarvam.yml")

    inputs = {}
    for pair in args.field:
        if "=" not in pair:
            raise SystemExit("--field wants KEY=VALUE, got %r" % pair)
        key, value = pair.split("=", 1)
        inputs[key] = value

    url = "%s/repos/%s/actions/workflows/%s/dispatches" % (API, args.repo, args.workflow)
    payload = {"ref": args.ref, "inputs": inputs}

    print("POST %s" % url)
    print(json.dumps(payload, ensure_ascii=False, indent=1))
    if args.show:
        print("\n--show: nothing sent.")
        return 0

    before = newest_run(args.repo, args.workflow)
    before_id = before.get("id") if before else None

    status, body = request("POST", url, payload)
    if status != 204:
        print("\nrefused: HTTP %d\n%s" % (status, body.decode("utf-8", "replace")[:600]),
              file=sys.stderr)
        return 1
    print("\naccepted (HTTP 204). Waiting for the run to appear...")

    for _ in range(15):
        time.sleep(2)
        run = newest_run(args.repo, args.workflow)
        if run and run.get("id") != before_id:
            print("  %s" % run.get("html_url"))
            return 0
    print("  queued; it has not appeared in the run list yet.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
