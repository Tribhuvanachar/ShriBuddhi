#!/usr/bin/env python3
"""One canonical shape for every data.json: one unit per line.

The corpus ships as a single line -- one file here is 346,591 characters with
no newline in it at all. Two things follow, and both of them hurt.

A text editor cannot work on it. A regular expression anchored to ^ or $
matches the whole file, so the line-based half of an editor's toolkit is
simply unavailable for the bulk cleanup this project exists to do.

And nobody can review a change to it. When the first content editor sent a
pull request, GitHub could not show a diff at all -- one line changed, and
that line was the file. The reviewer's choice was to trust it or to read
346 KB. That is not a review, and the malformed file in it went through.

So: keep the compact form inside each unit, and put each unit on its own
line. A diff then names the units that changed and nothing else, ^ and $ mean
what an editor thinks they mean, and the cost is one byte per unit -- measured
at +0.1% on disk and +4.7% in the pack, because the only new bytes are the
newlines and git deltas those almost perfectly.

This is NOT pretty-printing. Indenting every key costs 5.4% for structure
nobody reads, and it still would not make the text itself legible: a JSON
string is one line however you indent around it. For reading and editing the
TEXT, use tools/dge_text.py explode.

  python3 tools/format_data_json.py --check --all    CI gate
  python3 tools/format_data_json.py --all           reformat the corpus
  python3 tools/format_data_json.py PATH...         reformat named files
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

# The two container shapes in the corpus. Everything else is left alone --
# indexes, manifests and backlinks are generated, never hand-edited, and
# reformatting them would be churn for no reader's benefit.
LIST_KEY = "items"
DICT_KEY = "shlokas"


def dumps_compact(o) -> str:
    return json.dumps(o, ensure_ascii=False, separators=(",", ":"))


def canonical(doc) -> str | None:
    """-> the canonical text, or None if this shape is not ours to format."""
    if not isinstance(doc, dict):
        return None

    if isinstance(doc.get(LIST_KEY), list) and doc[LIST_KEY]:
        units = ",\n".join(dumps_compact(u) for u in doc[LIST_KEY])
        head = {k: v for k, v in doc.items() if k != LIST_KEY}
        prefix = dumps_compact(head)[:-1] + ("," if head else "")
        return prefix + '"%s":[\n' % LIST_KEY + units + "\n]}\n"

    if isinstance(doc.get(DICT_KEY), dict) and doc[DICT_KEY]:
        units = ",\n".join("%s:%s" % (dumps_compact(k), dumps_compact(v))
                           for k, v in doc[DICT_KEY].items())
        head = {k: v for k, v in doc.items() if k != DICT_KEY}
        prefix = dumps_compact(head)[:-1] + ("," if head else "")
        return prefix + '"%s":{\n' % DICT_KEY + units + "\n}}\n"

    return None


def process(path: str, check_only: bool) -> tuple[int, str]:
    """-> (1 if it needs reformatting, message). -1 signals a real error."""
    try:
        raw = open(path, encoding="utf-8").read()
    except (OSError, UnicodeDecodeError) as e:
        return -1, f"{path}: cannot read ({e})"
    try:
        doc = json.loads(raw)
    except ValueError as e:
        return -1, f"{path}: invalid JSON ({e}) -- run normalize_data_json.py first"

    want = canonical(doc)
    if want is None or want == raw:
        return 0, ""

    # The guarantee: reformatting may move bytes, never meaning.
    if json.loads(want) != doc:
        return -1, f"{path}: reformatting changed the parsed content -- refusing to write"

    if not check_only:
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(want)
    n = len(doc.get(LIST_KEY) or doc.get(DICT_KEY) or ())
    return 1, f"{path} ({n} units)"


def staged_data_json() -> list[str]:
    out = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACM", "-z"],
                         capture_output=True, text=True).stdout
    return [f for f in out.split("\0")
            if os.path.basename(f) == "data.json" and os.path.isfile(f)]


def all_data_json(root: str = "data") -> list[str]:
    return sorted(os.path.join(d, f)
                  for d, _s, fs in os.walk(root) for f in fs if f == "data.json")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--check", action="store_true", help="report only; exit 1 if any file is off")
    ap.add_argument("--staged", action="store_true")
    ap.add_argument("--stage-fixed", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)

    paths = list(a.paths)
    if a.staged:
        paths += staged_data_json()
    if a.all:
        paths += all_data_json()
    if not paths:
        ap.error("nothing to do -- give paths, or --staged, or --all")

    touched, errors = [], []
    for p in paths:
        n, msg = process(p, a.check)
        if n < 0:
            errors.append(msg)
        elif n > 0:
            touched.append(msg)

    if not a.quiet:
        for msg in touched[:40]:
            print(("would reformat " if a.check else "reformatted ") + msg)
        if len(touched) > 40:
            print(f"... and {len(touched) - 40} more")
    for msg in errors:
        print("ERROR " + msg, file=sys.stderr)

    if touched and a.stage_fixed and not a.check:
        files = [m.split(" (")[0] for m in touched]
        subprocess.run(["git", "add", "--"] + files, check=False)

    if errors:
        return 2
    if a.check and touched:
        print(f"\n{len(touched)} data.json file(s) are not in canonical form.\n"
              "Run: python3 tools/format_data_json.py --all", file=sys.stderr)
        return 1
    if not a.quiet:
        print(f"format_data_json: {len(paths)} file(s), {len(touched)} reformatted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
