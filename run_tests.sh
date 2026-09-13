#!/usr/bin/env bash
# All tests. Prefers pytest, because part of this suite cannot run without it.
#
# This script used to be `python3 -m unittest discover`, with a comment saying
# "no third-party packages". That stopped being true some time ago and the
# script had no way to say so:
#
#   * Ten test files are written as bare `def test_*()` functions rather than
#     unittest.TestCase classes. unittest's discovery does not collect those —
#     it imports the module, finds no TestCase, and reports nothing. Sixty-two
#     tests looked like they were in the suite and were never run once. Three
#     of them were failing.
#   * Six of those files use pytest fixtures (tmp_path, a `db` fixture) or
#     pytest.importorskip, which have no unittest equivalent. importorskip
#     raises pytest's own Skipped exception, which unittest reports as an
#     ERROR rather than a skip — so an optional dependency being absent looked
#     like a broken suite.
#
# So: run pytest when it is there. When it is not, run unittest and say plainly
# which tests are being left out, rather than printing a green total that has
# quietly dropped them.
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONPATH="$PWD/tools"

if python3 -c "import pytest" 2>/dev/null; then
    exec python3 -m pytest tests/ "$@"
fi

# Count what unittest is about to miss: files with module-level test functions
# and no TestCase class in them.
missing_files=0
missing_tests=0
for f in tests/test_*.py; do
    fns=$(grep -c '^def test_' "$f" || true)
    cls=$(grep -c '^class ' "$f" || true)
    if [ "$fns" -gt 0 ] && [ "$cls" -eq 0 ]; then
        missing_files=$((missing_files + 1))
        missing_tests=$((missing_tests + fns))
    fi
done

echo "WARNING: pytest is not installed." >&2
if [ "$missing_tests" -gt 0 ]; then
    echo "WARNING: $missing_tests test(s) in $missing_files file(s) are written as plain" >&2
    echo "         functions and will NOT run under unittest. Install pytest to run them:" >&2
    echo "             pip install pytest" >&2
    echo "         Some also need numpy or a sanskrit_parser install; those skip cleanly" >&2
    echo "         under pytest and error under unittest." >&2
fi

python3 -m unittest discover -s tests -p "test_*.py" "$@"
