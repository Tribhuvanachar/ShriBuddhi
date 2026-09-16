#!/usr/bin/env python3
"""Build data/layer_manifest.json — the reader's map of stitchable layers.

A "multi-layer grantha" in this corpus is a directory holding one mula/ and
one or more tika_*/ folders, each with its own complete data.json registered
as its own library.json entry (the DvaitaVedanta importer's layout, but the
same shape exists under nyaya/, mimamsa/, ayurveda/ etc.). The reader
(js/layer-stitch.js) stitches those sibling layers into the mula spine's
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

A second, newer shape (tools/reports/grantha_data_architecture.md) also
produces stitchable siblings: a `work.json` (schema grantha_work_v2) next
to one `<layer-slug>/data.json` per layer, each a flat `units: [{id, ref,
text, ...}]` list rather than legacy's `items: [{id, sanskrit_text, ...}]`.
There the join key is `ref` (the shared traditional citation, e.g.
"1.1.1"), not `id` — every layer of the family uses the same ref scheme by
construction, so overlap is checked directly rather than needing the -N
suffix heuristic. build_v2() below handles this shape and its entries are
merged into the same `granthas` dict the legacy build() produces, so the
reader (layer-stitch.js) doesn't need to know which shape it's looking at.
The family's first `work.json["layers"]` entry is its spine (usually
"mula", but e.g. brahma_sutra's is "sutra") — recorded as `spineSlug` only
when it isn't the "mula" the reader assumes by default.

Usage: python3 tools/build_layer_manifest.py [--root data] [--check]
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
NUMERIC_ID_RE = re.compile(r"^\d+$")


def base_id(item_id: str) -> str:
    """SM13:1-2 -> SM13:1 (the importer's duplicate-id disambiguation)."""
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
        # Excludes purely-numeric base ids: parabuddhi/tools/publish.py renumbers
        # every unit sequentially WITHIN ITS OWN FILE (public_id = i + 1), so once a
        # mula/tika pair has both been through that cutover their ids are no longer a
        # shared identity -- they're two independent 1..N counters that happen to
        # overlap by coincidence of position, not because they name the same verse. A
        # plain-integer overlap counted as `matched` here would make this tool report
        # a grantha as joinable (and layer-stitch.js would merge commentary onto
        # verses) purely because both files are short, which is silent data
        # corruption, not merely a broken join. Real (pre-cutover or not-yet-
        # published) ids from the importer keep their letters, so this only ever
        # narrows what counts as a genuine match.
        mula_bases = {b for b in (base_id(it.get("id", "")) for it in mula_items)
                      if b and not NUMERIC_ID_RE.match(b)}

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
        lib_title = lib_titles.get(f"data/{rel}/mula/data.json", "")
        title = lib_title.split(" — ")[0].strip() if lib_title else gdir.name
        granthas[rel] = {
            "title": title,
            "author": (mula_data.get("default_author") or "").strip(),
            "mulaItems": len(mula_items),
            "layers": layers,
        }
    return granthas


def load_units(path: Path):
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"  WARN unreadable {path}: {exc}", file=sys.stderr)
        return None, []
    units = data.get("units")
    return data, units if isinstance(units, list) else []


def build_v2(root: Path, lib_titles: dict) -> dict:
    granthas = {}
    for work_json in sorted(root.glob("**/work.json")):
        try:
            work = json.loads(work_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"  WARN unreadable {work_json}: {exc}", file=sys.stderr)
            continue
        if work.get("schema") != "grantha_work_v2":
            continue
        wlayers = work.get("layers") or []
        if len(wlayers) < 2:
            continue  # nothing to stitch onto the spine
        gdir = work_json.parent
        spine_slug = wlayers[0].get("slug", "")
        _, spine_units = load_units(gdir / spine_slug / "data.json")
        if not spine_units:
            continue
        spine_refs = {u.get("ref") for u in spine_units if u.get("ref")}
        if not spine_refs:
            continue

        layers = []
        any_matched = False
        for wl in wlayers[1:]:
            slug = wl.get("slug", "")
            if not slug or not (gdir / slug / "data.json").is_file():
                continue
            _, tunits = load_units(gdir / slug / "data.json")
            if not tunits:
                continue
            matched = sum(1 for u in tunits if u.get("ref") in spine_refs)
            layer = {
                "folder": slug,
                "label": wl.get("title") or slug,
                "author": wl.get("author") or "",
                "items": len(tunits),
                "matched": matched,
            }
            # Links to data/author_aliases.json's persons registry, where
            # work.json's own layer entry names one (tools/compile_grantha_v2.py
            # / compile_anuvyakhyana_v2.py's COMMENTATOR_IDS) -- passed through
            # rather than re-derived, so the manifest never has to guess an
            # attribution the compiler declined to make.
            if wl.get("commentator_id"):
                layer["commentatorId"] = wl["commentator_id"]
            layers.append(layer)
            any_matched = any_matched or matched > 0
        if not any_matched:
            continue
        layers.sort(key=lambda l: -l["matched"])
        rel = gdir.relative_to(root).as_posix()
        lib_title = lib_titles.get(f"data/{rel}/{spine_slug}/data.json", "")
        title = lib_title.split(" — ")[0].strip() if lib_title else (work.get("title") or gdir.name)
        entry = {
            "title": title,
            "author": wlayers[0].get("author") or "",
            "mulaItems": len(spine_units),
            "layers": layers,
        }
        if wlayers[0].get("commentator_id"):
            entry["commentatorId"] = wlayers[0]["commentator_id"]
        if spine_slug != "mula":
            entry["spineSlug"] = spine_slug
        granthas[rel] = entry
    return granthas


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="data")
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
    granthas.update(build_v2(root, lib_titles))
    manifest = {
        "_readme": "Generated by tools/build_layer_manifest.py — do not hand-edit. "
                   "Maps each joinable multi-layer grantha dir to its stitchable "
                   "commentary layers (see MULTI_LAYER_READER_ARCHITECTURE.md).",
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
