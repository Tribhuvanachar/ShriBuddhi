#!/usr/bin/env python3
"""
recover_structure.py — put back the shape the import flattened away.

WHY THIS EXISTS
---------------
import_dvaitavedanta.py keeps a breadcrumb as a list of strings and throws the
tree away. So the corpus can be read page by page but cannot answer "what
contains this, and what else does that contain" — and a Dvaita reader asks
that first.

The tree was never missing from the pages. Every leaf renders the grantha's
whole navigation as nested <ul class="sub-menu">, each node carrying its own
content id and a data-level. This walks that markup and writes the parent /
child relation out as data.

It reads the HTTP cache rather than the network. The cache is keyed by SHA1 of
the URL and holds the pages exactly as fetched, so this costs nothing and can
be re-run at will -- but it also means the cache is the raw material, and
recovering more later depends on it still existing.

WHAT IT DOES NOT DO
-------------------
It does not invent an adhikaraṇa level. The source tree is
grantha > adhyāya/section > pāda > group > leaf, with no adhikaraṇa among
them; adhikaraṇa names occur only inside page headings. Grouping leaves under
an adhikaraṇa is a derivation to be made and marked as derived, separately,
and confirmed by someone who knows the text.

    python tools/dvaitavedanta/recover_structure.py --cache .dv_cache \\
        --out data/darshana/vedanta/dvaita/DvaitaVedantaIn/_structure.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dv_parse import make_soup, parse_content_url  # noqa: E402

try:
    from bs4 import Tag
except ImportError:  # pragma: no cover - dependency is declared in requirements
    raise SystemExit("beautifulsoup4 is required: pip install -r requirements.txt")


def _node_title(anchor: Tag) -> str:
    """The visible label, without the chevrons and counters around it."""
    return re.sub(r"\s+", " ", anchor.get_text(" ", strip=True)).strip()


LI_ID_RE = re.compile(r"category-loaded-class-(\d+)")


def _parent_id(anchor: Tag) -> int | None:
    """The content id of the node whose sub-menu contains this anchor.

    The markup nests as <li><a/><ul class="sub-menu"><li><a/>...</ul></li>, so
    the parent is the <li> two levels up. Its id comes from that <li>'s own
    class -- "category-loaded-class-4834" -- and NOT from its anchor: a node
    with children carries href="javascript:void(0)" as its expander, so
    reading the href finds nothing and every node looks like a root.

    Walking the nesting rather than reading data-level is what makes this
    exact; levels repeat across branches, parents do not.
    """
    own_li = anchor.find_parent("li")
    if own_li is None:
        return None
    parent_li = own_li.find_parent("li")
    while parent_li is not None:
        match = LI_ID_RE.search(" ".join(parent_li.get("class") or []))
        if match:
            return int(match.group(1))
        parent_li = parent_li.find_parent("li")
    return None


def tree_from_html(html: str) -> dict[int, dict]:
    """Every navigation node on one page, with its parent."""
    soup = make_soup(html)
    nodes: dict[int, dict] = {}
    for anchor in soup.find_all("a", href=True):
        parsed = parse_content_url(anchor.get("href", ""))
        if not parsed:
            continue
        cid = parsed[0]
        level = anchor.get("data-level")
        title = _node_title(anchor)
        if not title:
            continue
        found = {
            "id": cid,
            "title": title,
            "level": int(level) if level and level.isdigit() else None,
            "parent": _parent_id(anchor),
            "url": anchor["href"],
        }
        # A node is usually linked twice on a page: once inside the nested
        # sidebar, once in a flat list elsewhere. Last-one-wins let the flat
        # copy erase the parent the nested copy had found, which is what made
        # every node look like a root.
        current = nodes.get(cid)
        if current is None or (current["parent"] is None and found["parent"] is not None):
            nodes[cid] = found
    return nodes


def merge(into: dict[int, dict], more: dict[int, dict]) -> None:
    """Union of the per-page trees.

    Pages lazy-load their branches, so no single page carries every node and
    the same node can appear with a parent on one page and without on another.
    A known parent always beats an unknown one; otherwise first sighting wins.
    """
    for cid, node in more.items():
        current = into.get(cid)
        if current is None:
            into[cid] = node
            continue
        if current.get("parent") is None and node.get("parent") is not None:
            current["parent"] = node["parent"]
        if current.get("level") is None and node.get("level") is not None:
            current["level"] = node["level"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache", default=".dv_cache", help="the HTTP cache directory")
    ap.add_argument("--out", required=True, help="where to write the structure JSON")
    ap.add_argument("--limit", type=int, default=0, help="read only N cached pages")
    args = ap.parse_args(argv)

    cache = Path(args.cache)
    pages = sorted(cache.glob("*.html"))
    if args.limit:
        pages = pages[: args.limit]
    if not pages:
        print(f"!! no cached pages under {cache}", file=sys.stderr)
        return 1

    tree: dict[int, dict] = {}
    for n, page in enumerate(pages, 1):
        merge(tree, tree_from_html(page.read_text(encoding="utf-8", errors="replace")))
        if n % 200 == 0:
            print(f"  {n}/{len(pages)} pages · {len(tree)} nodes")

    roots = [c for c, v in tree.items() if v["parent"] is None]
    children: Counter[int] = Counter(
        v["parent"] for v in tree.values() if v["parent"] is not None
    )
    levels = Counter(v["level"] for v in tree.values())

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "generated_note": "Navigation tree recovered from the cached pages by "
                          "tools/dvaitavedanta/recover_structure.py. Parent comes "
                          "from the nesting of the source's own sub-menus, not "
                          "from data-level, which repeats across branches.",
        "pages_read": len(pages),
        "nodes": len(tree),
        "roots": sorted(roots),
        "level_histogram": {str(k): v for k, v in sorted(
            levels.items(), key=lambda kv: (kv[0] is None, kv[0]))},
        "tree": {str(k): v for k, v in sorted(tree.items())},
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\n{len(pages)} pages -> {len(tree)} nodes, {len(roots)} root(s)")
    print("levels:", dict(sorted(levels.items(), key=lambda kv: (kv[0] is None, kv[0]))))
    print(f"parents with children: {len(children)}; widest: {children.most_common(3)}")
    print(f"written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
