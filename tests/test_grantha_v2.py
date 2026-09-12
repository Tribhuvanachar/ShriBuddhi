"""The v2 grantha trees (grantha_data_architecture.md) must stay
internally consistent: well-formed ids, resolvable on-anchors, complete
dv_map coverage. tools/validate_grantha.py is the checker; this wrapper
keeps it in every pytest run."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_grantha_v2_trees_validate():
    res = subprocess.run(
        [sys.executable, "tools/validate_grantha.py", "--quiet"],
        cwd=ROOT, capture_output=True, text=True)
    assert res.returncode == 0, res.stdout + res.stderr
