#!/usr/bin/env python3
"""Integrity checks on the emitted dvaitavedanta tree.

Runs after every write. Catches the failure modes that actually bite:
  * chrome/CSS/Latin scraped instead of verse text (low Devanagari ratio) —
    importers/common.py documents this exact bug biting narada_smriti
  * duplicate item ids inside a layer
  * tika ids that have no matching mula id (breaks cross-layer linking)
  * empty layers, truncated text, missing provenance
  * accidental \\uXXXX escaping instead of real Devanagari on disk

Exit code is 0 unless --strict is passed and errors were found.

Run:  python tools/dvaitavedanta/verify_extract.py --data dge/data/darshana/vedanta/dvaita/DvaitaVedantaIn
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dv_parse import devanagari_count, devanagari_ratio  # noqa: E402

MIN_RATIO = 0.55
MIN_CHARS = 4
REQUIRED_TOP = {"schema", "default_author", "source_url", "source_note", "items"}


def check_layer(path, payload, errors, warnings):
    rel = path
    missing = REQUIRED_TOP - set(payload)
    if missing:
        errors.append(f"{rel}: missing top-level keys {sorted(missing)}")

    items = payload.get("items") or []
    if not items:
        warnings.append(f"{rel}: no items")
        return set()

    ids = [item.get("id") for item in items]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        errors.append(f"{rel}: duplicate item ids {sorted(duplicates)[:5]}")

    for item in items:
        text = item.get("sanskrit_text") or ""
        if devanagari_count(text) < MIN_CHARS:
            errors.append(f"{rel}:{item.get('id')}: text has no Devanagari")
            continue
        ratio = devanagari_ratio(text)
        if ratio < MIN_RATIO:
            errors.append(f"{rel}:{item.get('id')}: Devanagari ratio {ratio:.2f} "
                          f"< {MIN_RATIO} — likely scraped chrome")
        source = item.get("source") or {}
        if not source.get("url"):
            errors.append(f"{rel}:{item.get('id')}: missing source.url")
        if not item.get("reference"):
            warnings.append(f"{rel}:{item.get('id')}: empty reference (no breadcrumb?)")

    if payload.get("schema") == "grantha_tika_text":
        untitled = [i.get("id") for i in items if not i.get("tika_title")]
        if untitled:
            warnings.append(f"{rel}: {len(untitled)} tika item(s) without tika_title")

    return set(ids)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", default="dge/data/darshana/vedanta/dvaita/DvaitaVedantaIn")
    parser.add_argument("--strict", action="store_true",
                        help="exit non-zero when errors are found")
    args = parser.parse_args(argv)

    if not os.path.isdir(args.data):
        print(f"nothing to verify: {args.data} does not exist")
        return 0

    errors: list[str] = []
    warnings: list[str] = []
    by_grantha: dict[str, dict[str, set]] = {}
    layer_count = item_count = 0

    for dirpath, _dirnames, filenames in os.walk(args.data):
        if "data.json" not in filenames:
            continue
        path = os.path.join(dirpath, "data.json")
        rel = os.path.relpath(path, args.data)
        raw = open(path, encoding="utf-8").read()
        if "\\u0" in raw:
            errors.append(f"{rel}: escaped \\uXXXX on disk — needs ensure_ascii=False")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            errors.append(f"{rel}: invalid JSON — {exc}")
            continue
        layer_count += 1
        item_count += len(payload.get("items") or [])
        ids = check_layer(rel, payload, errors, warnings)
        grantha = os.path.dirname(os.path.dirname(rel))
        by_grantha.setdefault(grantha, {})[os.path.basename(dirpath)] = ids

    # Cross-layer id linking: grantha_tika_text ids should match mula ids.
    for grantha, layers in by_grantha.items():
        mula = layers.get("mula")
        if not mula:
            continue
        for name, ids in layers.items():
            if name == "mula" or not ids:
                continue
            orphans = ids - mula
            if orphans:
                warnings.append(
                    f"{grantha}/{name}: {len(orphans)} id(s) with no matching mula item "
                    f"(e.g. {sorted(orphans)[:3]})"
                )

    print(f"verified {layer_count} layer file(s), {item_count:,} item(s) under {args.data}")
    for warning in warnings[:40]:
        print(f"  warn  {warning}")
    if len(warnings) > 40:
        print(f"  warn  …and {len(warnings) - 40} more")
    for error in errors[:40]:
        print(f"  ERROR {error}")
    if len(errors) > 40:
        print(f"  ERROR …and {len(errors) - 40} more")

    print(f"\n{len(errors)} error(s), {len(warnings)} warning(s)")
    if errors and args.strict:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
