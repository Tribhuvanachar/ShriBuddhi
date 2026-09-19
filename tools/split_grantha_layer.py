#!/usr/bin/env python3
"""split_grantha_layer.py — break a big grantha_layer_v2 layer file into
scholar-sized part files.

The project lead's ask (19 Sep 2026): the Nyaya Sudha layer files compiled by
compile_anuvyakhyana_v2.py are too big to hand a scholar for review/correction
(tippani_vakyartharatnamala/data.json alone is 12 MB) — split each into
chunks around 500 KB-1 MB, never cutting a verse's commentary paragraphs
across two files (a verse's units, grouped by `ref`, always land together).

What this does, for one layer directory (e.g. .../tika_nyayasudha/):
  1. Reads data.json ({schema: "grantha_layer_v2", ..., units: [...]}).
  2. Groups units by `ref`, IN FILE ORDER — never reordered, so refs already
     in reading order stay that way across parts.
  3. Accumulates ref-groups into a part until adding the next group would
     push the part's serialized size past --target-bytes; then starts a new
     part. A single ref-group bigger than the target still gets its own
     part rather than being split (no group is ever divided) -- this is why
     "around" 500 KB-1 MB rather than an exact cap.
  4. Writes part-001.json, part-002.json, ... (each a normal grantha_layer_v2
     file, plus part/of), and rewrites data.json itself into a small INDEX:
     {schema: "grantha_layer_v2_index", work, layer, units_total, parts: [...]}.

data.json's PATH never changes -- library.json, taxonomy.json and every
existing deep link still point at the same file. Only its content becomes a
pointer instead of the data; js/corpus-fetch.js's dgeResolveLayerV2Parts and
tools/build_layer_manifest.py's load_units() both resolve it transparently,
so nothing downstream needs to know a layer is split versus not.

Run once per layer directory, or --all-under a grantha's directory to split
every layer that exceeds the threshold:

    python3 tools/split_grantha_layer.py \\
        data/darshana/vedanta/dvaita/DvaitaVedantaIn/sutra_prasthana/anuvyakhyana_sudha \\
        --all-under --target-bytes 800000

    python3 tools/split_grantha_layer.py \\
        data/.../anuvyakhyana_sudha/tika_nyayasudha --target-bytes 800000

--check reports what would happen without writing anything.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DEFAULT_TARGET = 800_000  # bytes; "around 500 KB-1 MB" per the ask


def unit_size(unit: dict) -> int:
    return len(json.dumps(unit, ensure_ascii=False).encode("utf-8"))


def group_by_ref(units: list[dict]) -> list[tuple[str, list[dict]]]:
    """[(ref, [units...]), ...] as maximal CONTIGUOUS runs of the same ref,
    in original order. Concatenating every group's units reconstructs
    `units` exactly -- this never reorders anything, unlike grouping by ref
    value globally: at least one layer (tippani_vakyartharatnamala) reuses
    a ref like "1.1.0" as a recurring bucket at several distant points in
    the file, and a global group-by-value would pull all of those together
    to their first occurrence, silently rewriting reading order. A
    contiguous run is the only shape a "this verse's commentary, then the
    next" split can honestly mean anyway."""
    groups: list[tuple[str, list[dict]]] = []
    current_ref = None
    current: list[dict] = []
    for u in units:
        r = u.get("ref", "")
        if current and r != current_ref:
            groups.append((current_ref, current))
            current = []
        current_ref = r
        current.append(u)
    if current:
        groups.append((current_ref, current))
    return groups


def plan_parts(units: list[dict], target_bytes: int) -> list[list[dict]]:
    groups = group_by_ref(units)
    parts: list[list[dict]] = []
    current: list[dict] = []
    current_size = 0
    for _ref, group in groups:
        gsize = sum(unit_size(u) for u in group)
        if current and current_size + gsize > target_bytes:
            parts.append(current)
            current, current_size = [], 0
        current.extend(group)
        current_size += gsize
    if current:
        parts.append(current)
    return parts


def split_layer(layer_dir: Path, target_bytes: int, check: bool) -> bool:
    src = layer_dir / "data.json"
    if not src.is_file():
        print(f"  SKIP {layer_dir}: no data.json")
        return False
    doc = json.loads(src.read_text(encoding="utf-8"))
    if doc.get("schema") == "grantha_layer_v2_index":
        print(f"  SKIP {layer_dir}: already split ({len(doc.get('parts', []))} parts)")
        return False
    if doc.get("schema") != "grantha_layer_v2" or not isinstance(doc.get("units"), list):
        print(f"  SKIP {layer_dir}: not a grantha_layer_v2 units file")
        return False
    units = doc["units"]
    total_size = len(json.dumps(doc, ensure_ascii=False).encode("utf-8"))
    if total_size <= target_bytes:
        print(f"  SKIP {layer_dir}: {total_size:,} bytes already under target")
        return False

    parts = plan_parts(units, target_bytes)
    sizes = [sum(unit_size(u) for u in p) for p in parts]
    print(f"  {layer_dir.name}: {total_size:,} bytes, {len(units)} units "
          f"-> {len(parts)} part(s), sizes {', '.join(f'{s:,}' for s in sizes)}")

    if check:
        return True

    part_names = []
    for i, part_units in enumerate(parts, start=1):
        name = f"part-{i:03d}.json"
        part_names.append(name)
        part_doc = {
            "schema": "grantha_layer_v2",
            "work": doc.get("work", ""),
            "layer": doc.get("layer", layer_dir.name),
            "part": i,
            "of": len(parts),
            "units": part_units,
        }
        (layer_dir / name).write_text(
            json.dumps(part_doc, ensure_ascii=False, indent=1), encoding="utf-8")

    index_doc = {
        "schema": "grantha_layer_v2_index",
        "work": doc.get("work", ""),
        "layer": doc.get("layer", layer_dir.name),
        "units_total": len(units),
        "parts": part_names,
    }
    src.write_text(json.dumps(index_doc, ensure_ascii=False, indent=1), encoding="utf-8")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", help="a layer directory, or (with --all-under) a work directory")
    ap.add_argument("--all-under", action="store_true",
                     help="split every layer directory (one holding a data.json) under `path`")
    ap.add_argument("--target-bytes", type=int, default=DEFAULT_TARGET)
    ap.add_argument("--check", action="store_true", help="report only, write nothing")
    args = ap.parse_args()

    root = Path(args.path)
    if args.all_under:
        layer_dirs = sorted(d.parent for d in root.glob("*/data.json"))
    else:
        layer_dirs = [root]

    any_split = False
    for d in layer_dirs:
        any_split = split_layer(d, args.target_bytes, args.check) or any_split
    if args.check and any_split:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
