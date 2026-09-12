#!/usr/bin/env python3
"""Build dge/data/layer_manifest.json — the reader's map of stitchable layers.

A "multi-layer grantha" in this corpus is a directory holding one mula/ and
one or more tika_*/ folders, each with its own complete data.json registered
as its own library.json entry (the DvaitaVedanta importer's layout, but the
same shape exists under nyaya/, mimamsa/, ayurveda/ etc.). The reader
(dge/js/layer-stitch.js) stitches those sibling layers into the mula spine's
per-item commentaries{} at load time, joined by item id.

This tool decides — offline, from the data itself, never by guessing at
runtime — WHICH granthas are actually joinable: a grantha earns a manifest
entry only if at least one tika layer's item ids overlap its mula's item
ids (after stripping the importer's `-N` collision suffix). A grantha whose
tika folders use a different id scheme (e.g. tarkasangraha: mula sutra_N,
tika_dipika prakarana_N — measured overlap 0) gets NO entry, and the reader
leaves it exactly as it is today. Layers with matched == 0 inside an
otherwise-joinable grantha are still listed (so the library drawer knows
not to fold them away), just marked unjoinable.

Labels come from the data too: each layer's items carry the source site's
own layer heading (tika_title / source.layer, e.g. "सुधा", "परिमळ") — the
majority value wins, falling back to the folder slug. Re-run after any
crawl or restructure; the file is fully derived, never hand-edited.

Usage: python3 tools/build_layer_manifest.py [--root dge/data] [--check]
  --check: exit 1 if the committed manifest differs from what would be
           written (for CI / verify runs); writes nothing.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

SUFFIX_RE = re.compile(r"-\d+$")


def base_id(item_id: str) -> str:
    """DV_978-2 -> DV_978 (the importer's duplicate-id disambiguation)."""
    return SUFFIX_RE.sub("", item_id or "")


def majority(values) -> str:
    counts = Counter(v.strip() for v in values if v and v.strip())
    return counts.most_common(1)[0][0] if counts else ""


def load_items(path: Path):
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"  WARN unreadable {path}: {exc}", file=sys.stderr)
        return None, []
    items = data.get("items")
    return data, items if isinstance(items, list) else []


def layer_label(items, folder: str) -> str:
    label = majority(it.get("tika_title") or (it.get("source") or {}).get("layer", "")
                     for it in items)
    label = label or folder.removeprefix("tika_")
    # The known mis-split folders (see PENDING.md: karmavijaya-class heading
    # bugs) carry a whole body-text sentence as their "layer name" — a tab
    # label must stay a label. Truncation is display-only; the folder keeps
    # its full data untouched.
    if len(label) > 40:
        label = label[:38].rstrip() + "…"
    return label


def build(root: Path, lib_titles: dict) -> dict:
    granthas = {}
    for mula_json in sorted(root.glob("**/mula/data.json")):
        gdir = mula_json.parent.parent
        tika_dirs = sorted(d for d in gdir.iterdir()
                           if d.is_dir() and d.name.startswith("tika_")
                           and (d / "data.json").is_file())
        if not tika_dirs:
            continue
        mula_data, mula_items = load_items(mula_json)
        if not mula_items:
            continue
        mula_bases = {base_id(it.get("id", "")) for it in mula_items} - {""}

        layers = []
        any_matched = False
        for tdir in tika_dirs:
            tdata, titems = load_items(tdir / "data.json")
            if not titems:
                continue
            matched = sum(1 for it in titems if base_id(it.get("id", "")) in mula_bases)
            author = (tdata.get("default_author") or "").strip()
            layers.append({
                "folder": tdir.name,
                "label": layer_label(titems, tdir.name),
                # Long "authors" are the known mis-scraped body-text fields
                # (see PENDING.md) — withhold them from display rather than
                # show a paragraph as an author name.
                "author": author if len(author) <= 60 else "",
                "items": len(titems),
                "matched": matched,
            })
            any_matched = any_matched or matched > 0
        if not any_matched:
            continue
        layers.sort(key=lambda l: -l["matched"])
        rel = gdir.relative_to(root).as_posix()
        lib_title = lib_titles.get(f"dge/data/{rel}/mula/data.json", "")
        title = lib_title.split(" — ")[0].strip() if lib_title else gdir.name
        granthas[rel] = {
            "title": title,
            "author": (mula_data.get("default_author") or "").strip(),
            "mulaItems": len(mula_items),
            "layers": layers,
        }
    return granthas


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="dge/data")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    root = Path(args.root)
    out_path = root / "layer_manifest.json"

    lib_titles = {}
    lib_path = root / "library.json"
    if lib_path.is_file():
        with lib_path.open(encoding="utf-8") as f:
            for g in json.load(f).get("granthas", []):
                lib_titles[g.get("path", "")] = g.get("title", "")

    granthas = build(root, lib_titles)
    manifest = {
        "_readme": "Generated by tools/build_layer_manifest.py — do not hand-edit. "
                   "Maps each joinable multi-layer grantha dir to its stitchable "
                   "commentary layers (see dge/MULTI_LAYER_READER_ARCHITECTURE.md).",
        "granthas": granthas,
    }
    payload = json.dumps(manifest, ensure_ascii=False, indent=1) + "\n"

    if args.check:
        current = out_path.read_text(encoding="utf-8") if out_path.is_file() else ""
        if current != payload:
            print(f"{out_path} is stale — re-run tools/build_layer_manifest.py",
                  file=sys.stderr)
            return 1
        print(f"{out_path} is up to date ({len(granthas)} granthas)")
        return 0

    out_path.write_text(payload, encoding="utf-8")
    total_layers = sum(len(g["layers"]) for g in granthas.values())
    print(f"Wrote {out_path}: {len(granthas)} granthas, {total_layers} layers")
    for rel, g in sorted(granthas.items()):
        joinable = sum(1 for l in g["layers"] if l["matched"] > 0)
        print(f"  {rel}: {joinable}/{len(g['layers'])} joinable layers")
    return 0


if __name__ == "__main__":
    sys.exit(main())
