#!/usr/bin/env python3
"""Turn placeholder unit ids into the scholar-settled semantic ones.

tools/renumber_origin_ids.py stripped the imported site's record numbers and
left dge_<hash> placeholders behind. This replaces those with ids that state
where a unit sits in the tradition: SM13.1:412 is unit 412 of Nyayasudha, the
first tika on the Anuvyakhyana, the 13th Sarvamula grantha.

The map is built from OWNERS first -- the data.json whose items[] carries an
id -- and only then applied everywhere. That order is what keeps the corpus
joined up: 1,670 files under data/vedanga hold cross-references pointing at
these units and know nothing about the grantha that owns them, so a rewrite
driven per-file would renumber each file consistently with itself and
inconsistently with every other. One map, built once, applied globally.

A unit's number is its POSITION in the file, which is also the scholar's
instruction for the damaged tika folders: number them one, two, three rather
than trusting a name that is a fragment of captured text.

Anything the catalogue does not cover keeps its placeholder and is reported.
Minting an id for a folder nobody has ruled on would be inventing taxonomy.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import subprocess
import sys

CAT = "data/_catalog/sarvamula_index.json"
PLACEHOLDER = re.compile(r"\bdge_[0-9a-f]{12}\b")
TEXT_EXT = {".json", ".js", ".py", ".md", ".html", ".yml", ".yaml", ".txt", ".xml"}


def code_by_dir() -> dict[str, str]:
    """Directory holding a data.json -> its code. `mula` is the work itself."""
    cat = json.load(open(CAT, encoding="utf-8"))
    out: dict[str, str] = {}

    def add(base: str | None, code: str, tikas: list) -> None:
        if not base:
            return
        out[base] = code
        out[os.path.join(base, "mula")] = code
        for t in tikas or []:
            out[os.path.join(base, t["folder"])] = t["code"]
            if t.get("mula_at"):
                out[t["mula_at"]] = t["code"]
            for st in t.get("sub_tikas") or []:
                # SM13.1's sub-commentaries are filed under the later_acharyas
                # copy of Nyayasudha, not beside the Anuvyakhyana.
                also = t.get("also_at")
                if also:
                    out[os.path.join(also, st["folder"])] = st["code"]

    for w in cat["works"]:
        add(w.get("commentary_path"), w["code"], w.get("tikas"))
        for extra in w.get("also_paths") or []:
            add(extra, w["code"], w.get("tikas"))
        add(w.get("sarvamula_path"), w["code"], None)
    for l in cat.get("later_acharyas", []):
        add(l["folder"], l["code"], l.get("tikas"))
    return out


def build_map(lookup: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    """id -> "<WORK code>:<n>", where the work is the GRANTHA, not the layer.

    The first version of this keyed on the layer and would have been a bad
    bug. 5,462 of the 9,282 ids are carried by more than one file -- one by
    fifteen -- and that is not duplication to clean up, it is the alignment
    the reader depends on. dge_52d4654b49ee appears in the Mahabharata
    Tatparya Nirnaya's mula and in every tika beneath it; the entries sit at
    different indices and hold different text, but each one's reference reads
    adhyayah 8. The id names the ADHYAYA, and sharing it is what makes
    clicking a commentary land on the matching chapter.

    Minting per layer would have split that one anchor into fifteen ids, each
    file internally consistent and none of them joined -- precisely the
    failure the lead said must not happen, and invisible until someone
    clicked.

    So the number comes from the MULA's ordering, which is the complete list
    of the work's anchors (32 for MBTN, where a tika may carry only 16). In
    the mula this id sits at index 7, so it mints as SM28:8 -- the adhyaya
    number falls out of the position. An anchor a tika has and the mula does
    not is appended after, in first-seen order.
    """
    mapping, uncovered, seen = {}, [], {}

    def ids_of(path):
        try:
            doc = json.load(open(path, encoding="utf-8"))
        except Exception:
            return []
        items = doc.get("items") or doc.get("units")
        if not isinstance(items, list):
            return []
        return [it["id"] for it in items
                if isinstance(it, dict) and isinstance(it.get("id"), str)
                and PLACEHOLDER.fullmatch(it["id"])]

    # Group every layer under the work that owns it, mula first.
    works: dict[str, list[str]] = {}
    for path in sorted(glob.glob("data/**/data.json", recursive=True)):
        d = os.path.dirname(path)
        code = lookup.get(d)
        if not code:
            if ids_of(path):
                uncovered.append(f"{d}  ({len(ids_of(path))} id(s))")
            continue
        work = code.split(".")[0]          # SM13.1.4 -> SM13
        works.setdefault(work, []).append(path)

    for work, paths in works.items():
        paths.sort(key=lambda p: (os.path.basename(os.path.dirname(p)) != "mula", p))
        n = 0
        for path in paths:
            for i in ids_of(path):
                if i in mapping:
                    continue               # already anchored by an earlier layer
                n += 1
                mapping[i] = f"{work}:{n}"
        seen[work] = n
    return mapping, uncovered


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--map-out", default="")
    a = ap.parse_args()

    lookup = code_by_dir()
    print(f"{len(lookup)} folder(s) carry a catalogue code")
    mapping, uncovered = build_map(lookup)
    print(f"{len(mapping)} id(s) mapped; {len(uncovered)} folder(s) uncovered")
    for u in uncovered[:10]:
        print(f"    uncovered: {u}")

    files = [f for f in subprocess.run(
        ["git", "grep", "-lI", "-E", r"\bdge_[0-9a-f]{12}\b"],
        capture_output=True, text=True).stdout.splitlines()
        if os.path.splitext(f)[1].lower() in TEXT_EXT]

    hits = touched = unmapped = 0
    for rel in files:
        try:
            before = open(rel, encoding="utf-8").read()
        except (OSError, UnicodeDecodeError):
            continue
        misses = set()

        def sub(m):
            nonlocal misses
            new = mapping.get(m.group(0))
            if new is None:
                misses.add(m.group(0))
                return m.group(0)   # a reference to something we cannot name yet
            return new

        after, n = PLACEHOLDER.subn(sub, before)
        unmapped += len(misses)
        if after == before:
            continue
        hits += n
        touched += 1
        if not a.dry_run:
            open(rel, "w", encoding="utf-8").write(after)

    print(f"{hits} occurrence(s) rewritten across {touched} file(s); "
          f"{unmapped} placeholder(s) had no owner and were left alone")

    if a.map_out and not a.dry_run:
        json.dump({"_readme": "placeholder id -> semantic id, built from owners.",
                   "count": len(mapping), "map": dict(sorted(mapping.items()))},
                  open(a.map_out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"map written to {a.map_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
