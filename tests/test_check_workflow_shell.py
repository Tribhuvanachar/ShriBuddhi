"""The checker exists because a workflow shipped with an unterminated string
that YAML validation happily accepted. Its only job is to catch that, so the
test that matters is: does it catch that, and does it stay quiet otherwise.
"""
import importlib.util
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[1] / "tools" / "check_workflow_shell.py"
_spec = importlib.util.spec_from_file_location("check_workflow_shell", TOOL)
chk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(chk)

GOOD = 'echo "hello"\nif [ -n "$X" ]; then echo yes; fi\n'
BAD = 'echo "functions/index.js loads cleanly\n'   # the real one, verbatim


def workflow(run, shell=None):
    step = {"name": "a step", "run": run}
    if shell:
        step["shell"] = shell
    return {"jobs": {"j": {"steps": [step]}}}


def write(tmp_path, doc):
    import yaml
    p = tmp_path / "wf.yml"
    p.write_text(yaml.safe_dump(doc), encoding="utf-8")
    return p


def test_accepts_a_well_formed_step(tmp_path):
    assert chk.check_file(write(tmp_path, workflow(GOOD))) == []


def test_catches_the_unterminated_string_that_prompted_this(tmp_path):
    problems = chk.check_file(write(tmp_path, workflow(BAD)))
    assert len(problems) == 1
    assert "unexpected EOF" in problems[0]


def test_names_the_job_and_step_not_a_scratch_file(tmp_path):
    """bash reports the throwaway script it was handed, whose name tells a
    reader nothing. The step is what they need to find."""
    problem = chk.check_file(write(tmp_path, workflow(BAD)))[0]
    assert "job j" in problem and "a step" in problem
    assert "<step>" in problem
    assert ".sh" not in problem   # the scratch script's name, never useful


def test_ignores_a_step_that_is_not_shell(tmp_path):
    # `run:` under shell: python is Python, and bash -n would reject it.
    doc = workflow("x = 1\nif x:\n    print('ok')\n", shell="python")
    assert chk.check_file(write(tmp_path, doc)) == []


def test_checks_a_step_whose_shell_is_bash_explicitly(tmp_path):
    assert chk.check_file(write(tmp_path, workflow(BAD, shell="bash"))) != []


def test_a_step_with_no_run_block_is_not_an_error(tmp_path):
    doc = {"jobs": {"j": {"steps": [{"uses": "actions/checkout@v4"}]}}}
    assert chk.check_file(write(tmp_path, doc)) == []


def test_every_workflow_in_this_repo_parses():
    """The real assertion. A failure here names the workflow and the step."""
    problems = []
    for path in sorted(chk.WORKFLOWS.glob("*.yml")):
        problems.extend(chk.check_file(path))
    assert problems == [], "\n\n".join(problems)
