#!/usr/bin/env python3
"""Schema validation for every Kavya layer on disk.

Kept separate from verify_kavya.py on purpose: this one answers "is the JSON
well formed for DGE's itihasa_purana_text schema", verify_kavya.py answers
"is the corpus correct".  ingest workflows run this first so a malformed file
fails fast and cheap.
"""
from __future__ import annotations

import argparse
import os
import sys

from .common import log, read_json
from .schema import validate_layer

CATEGORY = "kavya_alankara"


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--data-root", default="dge/data")
    args = p.parse_args(argv)
    root = os.path.join(args.data_root, CATEGORY)
    errors, checked = [], 0
    for dirpath, _dirnames, filenames in os.walk(root):
        if "data.json" not in filenames:
            continue
        path = os.path.join(dirpath, "data.json")
        checked += 1
        layer = read_json(path)
        if layer is None:
            errors.append("%s: unreadable" % path)
            continue
        for e in validate_layer(layer):
            errors.append("%s: %s" % (path, e))
    for e in errors:
        log("ERROR " + e)
    log("validate_data: %d layers, %d errors" % (checked, len(errors)))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
