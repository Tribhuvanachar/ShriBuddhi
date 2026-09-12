#!/usr/bin/env python3
"""validate_dhatu_lexicon.py -- scans dge/data/vedanga/vyakarana/dhatu_lexicon/
data.json for corrupted entries (control characters, empty required fields)
that a live Gemini call occasionally produces (observed once during the
initial full-corpus run: a French field came back as literal control bytes
mid-response). Prints the affected dhatu ids -- pass them to
gemini_dhatu_lexicon.py's --dhatus with --force to regenerate just those.

Usage:
  python3 tools/validate_dhatu_lexicon.py           # print bad ids, exit 1 if any
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PATH = Path("dge/data/vedanga/vyakarana/dhatu_lexicon/data.json")


def has_control_chars(s: str) -> bool:
    return any(ord(c) < 0x20 and c not in "\n\t" for c in s)


def find_bad_ids(data: dict) -> list[str]:
    bad = []
    for it in data.get("items", []):
        meanings = it.get("meanings", {})
        concept = it.get("pedagogy", {}).get("concept", "")
        broken = (
            any(has_control_chars(v) for v in meanings.values())
            or has_control_chars(concept)
            or not concept.strip()
        )
        if broken:
            bad.append(it["id"])
    return bad


def main() -> int:
    if not PATH.exists():
        print(f"no such file: {PATH}", file=sys.stderr)
        return 1
    data = json.loads(PATH.read_text(encoding="utf-8"))
    bad = find_bad_ids(data)
    if not bad:
        print(f"clean: {len(data.get('items', []))} entries, no corruption found")
        return 0
    print(f"{len(bad)} corrupted entr{'y' if len(bad)==1 else 'ies'} found:")
    print(",".join(bad))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
