#!/usr/bin/env python3
"""Take the text out of a data.json so it can be edited as text, and put it back.

Why this exists. The corpus is JSON, which is the right thing for structure and
the wrong thing for prose. In a text editor a data.json is one enormous line
where a paragraph break is the two characters \\n, the Devanagari is a wall, and
a regex anchored to ^ or $ matches the whole file. Bulk OCR cleanup -- which is
the point of this project -- is exactly the work a text editor is good at, and
exactly the work that shape prevents.

So: explode writes the text out as Markdown, where a line break is a line break
and ^ and $ mean what the editor thinks they mean. Edit it with every tool the
editor has. Then implode puts it back.

The safety property is that implode NEVER rebuilds the data.json. It reads the
original, replaces the body text of each unit, and writes the result. Ids,
schema, provenance, breadcrumbs, footnotes, ordering -- everything that is not
body text is carried across untouched, because it is never taken out in the
first place. A corrupted or truncated .md can lose your edits; it cannot lose
the corpus.

  python3 tools/dge_text.py explode data/.../data.json
  python3 tools/dge_text.py explode data/darshana/... --out work/     (a whole tree)
      ... edit the .md files in Atom, VS Code, anything ...
  python3 tools/dge_text.py implode work/.../data.md
  python3 tools/dge_text.py implode work/ --all

Styling inside the text follows js/gold-render.js: **bold**, *italic*, a blank
line for a new paragraph, '> ' for verse lines, '# ' for a heading. Note that
this styling only RENDERS for a commentary marked "format": "gold_v2_2";
elsewhere a line break renders and the asterisks would show literally.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

# The body field, in the order we look for it. Different importers named it
# differently and all of them are in the corpus.
TEXT_FIELDS = ("sanskrit_text", "text", "sa")

# Metadata shown above each unit for orientation. Read-only: implode ignores it,
# so an editor can see what they are working on without being able to damage the
# structure by mistyping a line of it.
CONTEXT_FIELDS = ("reference", "section", "unit_title", "author")

MARK = "<!-- dge:unit %d id=%s -->"
MARK_RE = re.compile(r"^<!-- dge:unit (\d+) id=(.*?) -->$")
HEADER = "<!-- dge:file %s field=%s units=%d -->"
HEADER_RE = re.compile(r"^<!-- dge:file (.*?) field=(\S+) units=(\d+) -->$")


def find_items(doc):
    """-> list of dicts that look like editable units, in file order."""
    if isinstance(doc, dict) and isinstance(doc.get("items"), list):
        return [i for i in doc["items"] if isinstance(i, dict)]
    return []


def body_field(items) -> str | None:
    for f in TEXT_FIELDS:
        if any(isinstance(i.get(f), str) for i in items):
            return f
    return None


def explode_one(src: str, out_path: str) -> int:
    doc = json.load(open(src, encoding="utf-8"))
    items = find_items(doc)
    if not items:
        raise SystemExit(f"{src}: no items[] to explode")
    field = body_field(items)
    if not field:
        raise SystemExit(f"{src}: no text field ({'/'.join(TEXT_FIELDS)}) in any item")

    lines = [HEADER % (os.path.relpath(src), field, len(items)),
             "<!-- Edit the text under each marker. Lines beginning <!-- dge: are",
             "     structure -- keep them exactly as they are. The 'context' lines",
             "     are shown for orientation only and are ignored on the way back. -->",
             ""]
    for n, it in enumerate(items):
        lines.append(MARK % (n, it.get("id", "")))
        for cf in CONTEXT_FIELDS:
            v = it.get(cf)
            if isinstance(v, str) and v.strip():
                lines.append("<!-- %s: %s -->" % (cf, v.replace("-->", "--&gt;")))
        lines.append("")
        lines.append(str(it.get(field, "")))
        lines.append("")

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines).rstrip("\n") + "\n")
    return len(items)


def parse_md(md_path: str):
    """-> (source_path, field, {ordinal: (id, text)}). Structure lines only."""
    raw = open(md_path, encoding="utf-8").read().split("\n")
    header = None
    for line in raw:
        m = HEADER_RE.match(line.strip())
        if m:
            header = (m.group(1), m.group(2), int(m.group(3)))
            break
    if not header:
        raise SystemExit(f"{md_path}: no '<!-- dge:file ... -->' header. "
                         "Was this produced by `dge_text.py explode`?")

    units, cur, buf = {}, None, []

    def flush():
        if cur is not None:
            units[cur[0]] = (cur[1], "\n".join(buf).strip("\n"))

    for line in raw:
        m = MARK_RE.match(line.strip())
        if m:
            flush()
            cur, buf = (int(m.group(1)), m.group(2)), []
            continue
        if cur is None:
            continue
        if line.strip().startswith("<!-- ") and line.strip().endswith(" -->"):
            continue                      # a context line: orientation, not content
        buf.append(line)
    flush()
    return header[0], header[1], units


def implode_one(md_path: str, src_override: str | None = None) -> tuple[str, int]:
    src, field, units = parse_md(md_path)
    if src_override:
        src = src_override
    if not os.path.isfile(src):
        raise SystemExit(f"{md_path}: names source {src}, which does not exist. "
                         "Run implode from the repository root, or pass --source.")

    doc = json.load(open(src, encoding="utf-8"))
    items = find_items(doc)
    if len(units) != len(items):
        raise SystemExit(f"{md_path}: has {len(units)} units, {src} has {len(items)}. "
                         "A marker line was added or deleted -- refusing to guess.")

    changed = 0
    for n, it in enumerate(items):
        if n not in units:
            raise SystemExit(f"{md_path}: unit {n} is missing. Refusing to write.")
        uid, text = units[n]
        if uid and str(it.get("id", "")) != uid:
            raise SystemExit(f"{md_path}: unit {n} says id={uid}, {src} says "
                             f"id={it.get('id')}. The files are out of step.")
        if it.get(field, "") != text:
            it[field] = text
            changed += 1

    # Written the way the corpus is written: one line, UTF-8 as itself. Matching
    # the existing shape keeps the diff to the units that actually changed.
    with open(src, "w", encoding="utf-8", newline="") as fh:
        json.dump(doc, fh, ensure_ascii=False, separators=(",", ":"))
    return src, changed


def md_for(src: str, out_root: str | None, base: str) -> str:
    if not out_root:
        return os.path.splitext(src)[0] + ".md"
    rel = os.path.relpath(src, base)
    return os.path.join(out_root, os.path.splitext(rel)[0] + ".md")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("explode", help="data.json -> editable .md")
    e.add_argument("path", help="a data.json, or a directory to walk")
    e.add_argument("--out", default="", help="write .md files under here (mirrors the tree)")

    i = sub.add_parser("implode", help=".md -> back into its data.json")
    i.add_argument("path", help="a .md, or a directory with --all")
    i.add_argument("--all", action="store_true", help="every .md under the directory")
    i.add_argument("--source", default="", help="override the data.json named in the header")

    a = ap.parse_args(argv)

    if a.cmd == "explode":
        if os.path.isfile(a.path):
            srcs, base = [a.path], os.path.dirname(a.path) or "."
        else:
            base = a.path
            srcs = sorted(os.path.join(d, f) for d, _s, fs in os.walk(a.path)
                          for f in fs if f == "data.json")
        if not srcs:
            print(f"no data.json found under {a.path}", file=sys.stderr)
            return 1
        total = 0
        for s in srcs:
            out = md_for(s, a.out or None, base)
            n = explode_one(s, out)
            total += n
            print(f"{out}  ({n} units)")
        print(f"\n{len(srcs)} file(s), {total} units. Edit the .md, then: "
              f"python3 tools/dge_text.py implode {a.out or os.path.dirname(srcs[0])}"
              + (" --all" if len(srcs) > 1 else ""))
        return 0

    mds = [a.path] if os.path.isfile(a.path) else (
        sorted(os.path.join(d, f) for d, _s, fs in os.walk(a.path)
               for f in fs if f.endswith(".md")) if a.all else [])
    if not mds:
        print("give a .md file, or a directory with --all", file=sys.stderr)
        return 1
    touched = 0
    for m in mds:
        src, changed = implode_one(m, a.source or None)
        touched += changed
        print(f"{src}  ({changed} unit(s) changed)")
    print(f"\n{len(mds)} file(s) written, {touched} unit(s) changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
