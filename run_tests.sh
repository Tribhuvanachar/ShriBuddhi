#!/usr/bin/env bash
# All tests, no network, no third-party packages.
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONPATH="$PWD/tools"
python3 -m unittest discover -s tests -p "test_*.py" "$@"
