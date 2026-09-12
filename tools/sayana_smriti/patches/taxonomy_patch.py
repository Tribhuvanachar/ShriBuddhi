#!/usr/bin/env python3
"""Add the two Dharmasūtra folders the importer can create but taxonomy.json
does not yet know about. Idempotent — safe to re-run."""

import argparse
import json
import sys
from pathlib import Path

NEW = {
    "vasistha_smriti": {"_default_author": "Vasishtha"},
    "baudhayana_smriti": {"_default_author": "Baudhayana"},
}


def sniff_indent(text: str, default: int = 1) -> int:
    """taxonomy.json is written with 1-space indent while library.json uses 2.
    Re-dumping with the wrong width reformats every line of the file for a
    two-key addition, so read the width off the file rather than assuming it
    (see the same lesson recorded in tools/register_layers.py)."""
    for line in text.splitlines()[1:]:
        stripped = line.lstrip(" ")
        if stripped.startswith('"'):
            return len(line) - len(stripped) or default
    return default


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dge-root", required=True)
    args = ap.parse_args()

    path = Path(args.dge_root) / "data" / "taxonomy.json"
    raw = path.read_text(encoding="utf-8")
    tax = json.loads(raw)
    indent = sniff_indent(raw)

    node = tax.get("smriti_dharma", {}).get("smriti")
    if node is None:
        print("!! smriti_dharma.smriti not found in taxonomy.json", file=sys.stderr)
        return 2

    added = [k for k in NEW if k not in node]
    for k in added:
        node[k] = NEW[k]

    if not added:
        print("taxonomy.json already up to date")
        return 0

    path.write_text(json.dumps(tax, ensure_ascii=False, indent=indent) + "\n", encoding="utf-8")
    print(f"added to taxonomy.json: {', '.join(added)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
