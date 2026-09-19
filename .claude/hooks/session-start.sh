#!/bin/bash
# Installs the Python packages the test suite needs but the base image
# doesn't carry, so `python3 -m pytest tests/` (what run_tests.sh prefers)
# and `python3 -m unittest discover -s tests` both actually collect every
# test file instead of erroring out at import time.
#
# This list must stay identical to .github/workflows/test.yml's own
# `pip install` line -- that workflow is the canonical source of what CI
# needs, and a session that can't reproduce CI's result isn't a useful
# check. If that line changes, change this one in the same commit.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

pip install --quiet pytest beautifulsoup4 requests pyyaml numpy indic-transliteration openpyxl
