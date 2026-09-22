#!/usr/bin/env python3
"""`bash -n` every `run:` block in every GitHub Actions workflow.

Written 22 Sep 2026 after a workflow edit shipped with an unterminated string:

    echo "functions/index.js loads cleanly

The YAML parsed, the file looked right in review, and the run failed in the
Actions log with `unexpected EOF while looking for matching '"'` -- a whole
deploy cycle to learn about a missing quote. YAML validity says nothing about
the shell inside a `run:` block, and that is where most of the code lives.

    python3 tools/check_workflow_shell.py
    python3 tools/check_workflow_shell.py .github/workflows/reindex.yml

A step is skipped when its `shell:` is not bash/sh -- python and pwsh steps
are not ours to parse.
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys
import tempfile

try:
    import yaml
except ImportError:  # pragma: no cover - environment without pyyaml
    print("pyyaml is required: pip install pyyaml", file=sys.stderr)
    raise SystemExit(2)

WORKFLOWS = pathlib.Path(".github/workflows")
SHELLS = {None, "bash", "sh", "bash -e {0}"}


def steps_of(doc: dict):
    """Yield (job, step) for every step in a parsed workflow."""
    for job_name, job in (doc.get("jobs") or {}).items():
        for step in job.get("steps") or []:
            if isinstance(step, dict):
                yield job_name, step


def check_run(script: str) -> str | None:
    """Return bash's complaint, or None when the script parses."""
    with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as fh:
        fh.write(script)
        path = fh.name
    try:
        proc = subprocess.run(["bash", "-n", path], capture_output=True, text=True)
        if proc.returncode == 0:
            return None
        # bash names the temp file; that path means nothing to a reader.
        return proc.stderr.replace(path, "<step>").strip()
    finally:
        pathlib.Path(path).unlink(missing_ok=True)


def check_file(path: pathlib.Path) -> list[str]:
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return [f"{path}: not valid YAML: {exc}"]
    if not isinstance(doc, dict):
        return []

    problems = []
    for job_name, step in steps_of(doc):
        script = step.get("run")
        if not script:
            continue
        shell = step.get("shell")
        if shell is not None and shell.split()[0] not in ("bash", "sh"):
            continue
        err = check_run(script)
        if err:
            name = step.get("name") or step.get("uses") or "(unnamed step)"
            problems.append(f"{path}: job {job_name}: step {name!r}:\n{err}")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", help="workflow files; default is every one")
    args = ap.parse_args(argv)

    paths = [pathlib.Path(p) for p in args.paths] or sorted(
        list(WORKFLOWS.glob("*.yml")) + list(WORKFLOWS.glob("*.yaml")))
    if not paths:
        print(f"no workflows under {WORKFLOWS}", file=sys.stderr)
        return 1

    problems = []
    for path in paths:
        problems.extend(check_file(path))

    for p in problems:
        print(p)
    print(f"\n{len(paths)} workflow(s) checked, {len(problems)} bad step(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
