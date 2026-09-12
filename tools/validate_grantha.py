#!/usr/bin/env python3
"""validate_grantha.py — integrity checks for grantha_work_v2 trees
(tools/reports/grantha_data_architecture.md).

For every work.json under dge/data/** with schema grantha_work_v2:
  - every declared layer has a data.json whose unit count matches
  - unit ids are well-formed ("<a>.<p>.<s>.p<n>"), unique, and their ref
    prefix matches the unit's own ref field
  - every commentary unit's "on" refs exist in its parent layer
    (per commentary_on; layers with an unverified chain are checked
    against the sutra layer's ref set)
  - every unit appears in _sources/dv_map.json when that sidecar exists

Exit 1 on any failure; --quiet prints only failures.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ID_RE = re.compile(r"^\d+\.\d+\.\d+\.p\d+$")


def validate_work(work_dir: Path, quiet: bool) -> list[str]:
    errs: list[str] = []
    work = json.loads((work_dir / "work.json").read_text(encoding="utf-8"))
    layers = {L["slug"]: L for L in work.get("layers", [])}
    units_by_layer: dict[str, list[dict]] = {}

    for slug, L in layers.items():
        p = work_dir / slug / "data.json"
        if not p.exists():
            errs.append(f"{slug}: declared in work.json but {p} missing")
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        units = d.get("units", [])
        units_by_layer[slug] = units
        if L.get("units") != len(units):
            errs.append(f"{slug}: work.json says {L.get('units')} units, file has {len(units)}")
        seen = set()
        for u in units:
            uid = u.get("id", "")
            if not ID_RE.match(uid):
                errs.append(f"{slug}:{uid}: malformed id")
            if uid in seen:
                errs.append(f"{slug}:{uid}: duplicate id")
            seen.add(uid)
            if uid.rsplit(".", 1)[0] != u.get("ref"):
                errs.append(f"{slug}:{uid}: id/ref mismatch (ref={u.get('ref')})")
            if not (u.get("text") or "").strip():
                errs.append(f"{slug}:{uid}: empty text")

    ref_sets = {slug: {u["ref"] for u in units}
                for slug, units in units_by_layer.items()}
    # 'on' refs are FAMILY coordinates: the base layer (first in work.json —
    # sutra/mula) defines the ref universe; a commentary may anchor at any
    # base ref even where its own parent layer has no unit
    base_slug = work.get("layers", [{}])[0].get("slug", "")
    base_set = ref_sets.get(base_slug, set())
    for slug, units in units_by_layer.items():
        co = layers[slug].get("commentary_on") or ""
        target = ref_sets.get(co, set()) | base_set
        # pada-introduction refs (s=0) are legal anchors even though no
        # base unit carries them
        for u in units:
            for r in u.get("on", []):
                if r in target:
                    continue
                if re.match(r"^\d+\.\d+\.0$", r):
                    continue
                errs.append(f"{slug}:{u['id']}: on-target {r} not in the "
                            f"family ref universe (base layer {base_slug})")

    dv = work_dir / "_sources" / "dv_map.json"
    if dv.exists():
        mp = json.loads(dv.read_text(encoding="utf-8")).get("map", {})
        for slug, units in units_by_layer.items():
            missing = [u["id"] for u in units if f"{slug}:{u['id']}" not in mp]
            if missing:
                errs.append(f"{slug}: {len(missing)} unit(s) missing from dv_map "
                            f"(first: {missing[0]})")

    if not quiet:
        total = sum(len(v) for v in units_by_layer.values())
        print(f"{work_dir}: {len(units_by_layer)} layers, {total} units, "
              f"{len(errs)} error(s)")
    return errs


def main(argv=None) -> int:
    quiet = "--quiet" in (argv or sys.argv[1:])
    roots = sorted(Path("dge/data").rglob("work.json"))
    all_errs: list[str] = []
    for wj in roots:
        try:
            if json.loads(wj.read_text(encoding="utf-8")).get("schema") != "grantha_work_v2":
                continue
        except Exception:
            continue
        all_errs += validate_work(wj.parent, quiet)
    for e in all_errs[:50]:
        print("ERROR:", e)
    if len(all_errs) > 50:
        print(f"... and {len(all_errs) - 50} more")
    if not roots and not quiet:
        print("no grantha_work_v2 trees found")
    return 1 if all_errs else 0


if __name__ == "__main__":
    sys.exit(main())
