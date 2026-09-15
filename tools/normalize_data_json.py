#!/usr/bin/env python3
"""Make the Enter key safe in a data.json.

A line break in a text field is a real feature here -- js/render.js turns a
newline in the stored string into a <br> on the page. But JSON says a newline
inside a string must be written as the two characters \\ and n; a raw one is a
control character and the file stops being JSON. Browsers use a strict parser,
so the page simply stops loading.

Content editors work these files in a text editor, doing bulk find/replace and
regex passes, and in a text editor a line break is the Enter key. Asking people
to hand-type \\n inside a 300 KB single line, correctly, every time, under
search-and-replace, is a rule that will be broken -- and it was.

So this tool does the translation instead. It finds raw control characters that
are inside a JSON string and escapes them, leaving every other byte of the file
exactly as it was. Press Enter, get a line break on the page, keep valid JSON.

What it does NOT do: reformat, reorder, reindent, or re-encode anything. The
output differs from the input only at the characters that were illegal. That
matters because these files are reviewed as diffs.

Usage:
  python3 tools/normalize_data_json.py PATH...        fix in place
  python3 tools/normalize_data_json.py --check PATH... report, exit 1 if any
  python3 tools/normalize_data_json.py --staged        fix what git has staged
  python3 tools/normalize_data_json.py --check --all   check every data.json
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

# The escapes JSON names. Everything else below 0x20 has to go out as \uXXXX.
NAMED = {"\n": "\\n", "\r": "\\r", "\t": "\\t", "\b": "\\b", "\f": "\\f"}


def escape_control_chars_in_strings(text: str) -> tuple[str, int]:
    """Escape raw control characters that sit inside JSON string literals.

    Returns (fixed_text, number_of_characters_escaped). Characters outside
    string literals -- the newlines and indentation of a pretty-printed file --
    are structural whitespace and are left alone.
    """
    out: list[str] = []
    fixed = 0
    in_string = False
    escaped = False

    for ch in text:
        if in_string:
            if escaped:
                out.append(ch)
                escaped = False
                continue
            if ch == "\\":
                out.append(ch)
                escaped = True
                continue
            if ch == '"':
                out.append(ch)
                in_string = False
                continue
            if ch < " ":
                out.append(NAMED.get(ch) or "\\u%04x" % ord(ch))
                fixed += 1
                continue
            out.append(ch)
            continue

        out.append(ch)
        if ch == '"':
            in_string = True

    return "".join(out), fixed


def normalize(text: str) -> tuple[str, int]:
    """Fix the text and prove the fix did not change what the file MEANS.

    The check is the point: a lenient parse of the original and a strict parse
    of the result have to be the same object. If they are not, something other
    than escaping happened and we must not write the file.
    """
    fixed_text, count = escape_control_chars_in_strings(text)
    if count == 0:
        return text, 0

    before = json.loads(text, strict=False)
    after = json.loads(fixed_text)
    if before != after:
        raise ValueError("escaping changed the parsed content -- refusing to write")
    return fixed_text, count


def is_already_valid(text: str) -> bool:
    try:
        json.loads(text)
        return True
    except ValueError:
        return False


def process(path: str, check_only: bool) -> tuple[int, str]:
    """-> (characters_needing_escape, message). -1 signals a real error."""
    try:
        text = open(path, encoding="utf-8").read()
    except (OSError, UnicodeDecodeError) as e:
        return -1, f"{path}: cannot read ({e})"

    if is_already_valid(text):
        return 0, ""

    try:
        fixed_text, count = normalize(text)
    except ValueError as e:
        return -1, f"{path}: {e}"

    if count == 0:
        # Invalid for some reason escaping cannot repair -- a truncated file, a
        # trailing comma, a smart quote. Say so plainly instead of pretending.
        try:
            json.loads(text)
        except ValueError as e:
            return -1, f"{path}: invalid JSON, and not because of a raw control character ({e})"

    if not check_only:
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(fixed_text)
    return count, f"{path}: {count} raw control character(s) inside strings"


def staged_json_files() -> list[str]:
    out = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACM", "-z"],
                         capture_output=True, text=True).stdout
    return [f for f in out.split("\0") if f.endswith(".json") and os.path.isfile(f)]


def all_data_json(root: str = "data") -> list[str]:
    found = []
    for dirpath, _dirnames, filenames in os.walk(root):
        found.extend(os.path.join(dirpath, f) for f in filenames if f.endswith(".json"))
    return sorted(found)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--check", action="store_true",
                    help="report without writing; exit 1 if anything needs fixing")
    ap.add_argument("--staged", action="store_true", help="operate on git's staged .json files")
    ap.add_argument("--all", action="store_true", help="operate on every .json under data/")
    ap.add_argument("--stage-fixed", action="store_true",
                    help="git add each file this run fixed (used by the pre-commit hook)")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)

    paths = list(a.paths)
    if a.staged:
        paths += staged_json_files()
    if a.all:
        paths += all_data_json()
    if not paths:
        ap.error("nothing to do -- give paths, or --staged, or --all")

    touched, errors = [], []
    for p in paths:
        count, msg = process(p, a.check)
        if count < 0:
            errors.append(msg)
        elif count > 0:
            touched.append((p, msg))

    for _p, msg in touched:
        if not a.quiet or not a.check:
            print(("WOULD FIX " if a.check else "fixed     ") + msg)
    if touched and not a.check:
        print("Your line breaks are kept -- each one renders as <br> on the page.")
    for msg in errors:
        print("ERROR     " + msg, file=sys.stderr)

    if touched and a.stage_fixed and not a.check:
        subprocess.run(["git", "add", "--"] + [p for p, _ in touched], check=False)

    if errors:
        return 2
    if a.check and touched:
        print(f"\n{len(touched)} file(s) hold a raw line break inside a JSON string.\n"
              "Run: python3 tools/normalize_data_json.py " + " ".join(p for p, _ in touched),
              file=sys.stderr)
        return 1
    if not a.quiet and not touched:
        print(f"normalize_data_json: {len(paths)} file(s) checked, all valid JSON")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
