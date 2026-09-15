#!/usr/bin/env python3
"""Switch a work on for inline markup (**bold**, *italic*).

Off by default, and the default is the careful one: '*' already occurs 6,305
times in the corpus as an editorial mark -- the Satapatha Brahmana uses it --
so reading every asterisk as italic would silently mangle thousands of passages
in texts nobody had touched. A work opts in when someone has looked at it.

Switching on adds one key to the file:  "markup": "dge_inline_v1"

It does nothing on its own. A file with no asterisks renders identically before
and after; it only means that from now on an editor's **bold** will be bold
rather than four literal asterisks.

  python3 tools/enable_inline_markup.py data/.../data.json
  python3 tools/enable_inline_markup.py data/.../karma_nirnaya --recursive
  python3 tools/enable_inline_markup.py PATH --off
  python3 tools/enable_inline_markup.py PATH --check
"""
from __future__ import annotations

import argparse
import json
import os
import sys

FLAG = "dge_inline_v1"
KEY = "markup"


def targets(path: str, recursive: bool) -> list[str]:
    if os.path.isfile(path):
        return [path]
    if not recursive:
        raise SystemExit(f"{path} is a directory -- pass --recursive to do every data.json in it")
    return sorted(os.path.join(d, f)
                  for d, _s, fs in os.walk(path) for f in fs if f == "data.json")


def asterisk_report(doc) -> int:
    """How many asterisks are already in this file's text -- the one thing
    worth looking at before switching a work on."""
    n = 0
    stack = [doc]
    while stack:
        o = stack.pop()
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(v, str) and k in ("sanskrit_text", "text", "sa"):
                    n += v.count("*")
                else:
                    stack.append(v)
        elif isinstance(o, list):
            stack.extend(o)
    return n


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path")
    ap.add_argument("--recursive", action="store_true")
    ap.add_argument("--off", action="store_true", help="switch it back off")
    ap.add_argument("--check", action="store_true", help="report only")
    a = ap.parse_args(argv)

    files = targets(a.path, a.recursive)
    if not files:
        print(f"no data.json under {a.path}", file=sys.stderr)
        return 1

    changed = 0
    for f in files:
        doc = json.load(open(f, encoding="utf-8"))
        if not isinstance(doc, dict):
            continue
        on = doc.get(KEY) == FLAG
        want = not a.off
        stars = asterisk_report(doc)
        state = "on" if on else "off"
        if a.check:
            print(f"{state:>3}  {stars:>5} asterisk(s)  {f}")
            continue
        if on == want:
            continue
        if want and stars:
            # Not refused -- someone has to be able to switch on a text that
            # uses asterisks -- but never silently, because each one is about
            # to start meaning something.
            print(f"NOTE  {f} already contains {stars} asterisk(s); each will now "
                  f"be read as markup. Check them.", file=sys.stderr)
        if want:
            doc[KEY] = FLAG
        else:
            doc.pop(KEY, None)
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import format_data_json
        text = format_data_json.canonical(doc) or json.dumps(
            doc, ensure_ascii=False, separators=(",", ":"))
        with open(f, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        changed += 1
        print(("switched on  " if want else "switched off ") + f)

    if not a.check:
        print(f"\n{changed} file(s) changed of {len(files)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
