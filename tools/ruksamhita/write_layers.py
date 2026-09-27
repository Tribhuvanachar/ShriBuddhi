#!/usr/bin/env python3
"""Merge the Ṛksaṃhitā vyākhyānas into the maṇḍala they comment on.

The Ṛgveda saṃhitā is already on the shelf -- 2,006 mantras in maṇḍala 1,
each with its padapāṭha, svara, ṛṣi, devatā and metre, and each carrying a
``commentaries`` dict that already holds Sāyaṇa and the European
translators. So these vyākhyānas do not become a grantha of their own.
They go where Sāyaṇa already is, as further keys on the mantra itself.

    data/vedas/rigveda/shakala_shakha/samhita/mandala_01/data.json

WHAT IS NOT WRITTEN. Sāyaṇa: the corpus has him on 1,337 of the 1,370
mantras this edition covers, and a second copy is a duplicate, not a
layer. The saṃhitā text and the padapāṭha: already there, with accents the
OCR does not carry. The edition's headline feature is the one thing it has
nothing to add to.

MERGE, NEVER REPLACE. Each mantra's ``commentaries`` dict is updated in
place. The repository has been bitten by the other way round -- a --fix
that replaced instead of merging deleted ``source_url`` from 214 entries
and reported it as a success -- so this writes only keys of its own and
refuses to overwrite one that is already there.

THE FILE IS REWRITTEN THROUGH canonical(), NOT json.dump. One unit per
line, byte-identical for every line this run does not touch, so the diff
is exactly the mantras that gained a commentary. The line count is checked
before and after.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "ocr_common"))


def _load(name: str, path: pathlib.Path):
    """Load a module under a name of its own.

    Every segmenter in this tree is called ``segment.py``, so a plain
    ``import segment`` resolves to whichever one reached sys.modules first.
    Under pytest that is a different file in a different directory, and the
    whole suite fails somewhere else entirely.
    """
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


seg = _load("ruksamhita_segment", HERE / "segment.py")

TARGET = pathlib.Path("data/vedas/rigveda/shakala_shakha/samhita/mandala_01/data.json")

#: Written under these keys, beside the ``sayana`` already there.
LABELS = {
    "rgbhashya": "ऋग्भाष्यम् — श्रीमदानन्दतीर्थः",
    "rgbhashya_tika": "ऋग्भाष्यटीका — श्रीजयतीर्थः",
    "mantrarthamanjari": "मन्त्रार्थमञ्जरी — श्रीराघवेन्द्रतीर्थः",
    "skandasvamin": "भाष्यम् — श्रीस्कन्दस्वामी",
    "venkatamadhava": "भाष्यम् — वेङ्कटमाधवाचार्यः",
    "mudgala": "भाष्यम् — मुद्गलः",
    "siddhanjana": "सिद्धाञ्जनम् — कपालिशास्त्री",
    "nitimanjari": "नीतिमञ्जरी — श्रीद्यादेवः",
}

#: Below this a "commentary" is a stray fragment, not a gloss.
MIN_CHARS = 12


def canonical(payload: dict) -> str | None:
    spec = importlib.util.spec_from_file_location(
        "format_data_json", HERE.parent / "format_data_json.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.canonical(payload)


def collect(units: list[dict]) -> dict[str, dict[str, str]]:
    """mantra id -> {key: text}, skipping what the corpus already holds."""
    out: dict[str, dict[str, str]] = {}
    for u in units:
        mid = u.get("id")
        if not mid:
            continue
        for key in u["order"]:
            if key in seg.ALREADY_LANDED or key not in LABELS:
                continue
            text = " ".join(u["layers"][key].split())
            if len(text) < MIN_CHARS:
                continue
            out.setdefault(mid, {})[key] = text
    return out


def merge(payload: dict, found: dict[str, dict[str, str]]) -> dict:
    stats = {"mantras": 0, "added": 0, "kept": 0, "unknown": 0}
    by_id = {it["id"]: it for it in payload["items"]}
    for mid, layers in found.items():
        item = by_id.get(mid)
        if item is None:
            stats["unknown"] += 1
            continue
        com = item.setdefault("commentaries", {})
        touched = False
        for key, text in layers.items():
            if key in com:                    # never overwrite what is there
                stats["kept"] += 1
                continue
            com[key] = text
            stats["added"] += 1
            touched = True
        if touched:
            stats["mantras"] += 1
    return stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)

    units = seg.segment()
    found = collect(units)
    print(f"{len(units)} mantra blocks, "
          f"{sum(1 for u in units if u.get('id'))} addressed, "
          f"{len(found)} mantras carrying a new layer")

    original = TARGET.read_text(encoding="utf-8")
    payload = json.loads(original)
    before = original.count("\n")
    stats = merge(payload, found)

    import collections
    per_key = collections.Counter(
        k for layers in found.values() for k in layers)
    for key, n in per_key.most_common():
        print(f"   {key:<22} {n:>5}   {LABELS[key]}")
    print(f"\n{stats['added']} commentaries added across {stats['mantras']} "
          f"mantras; {stats['kept']} already present and left alone; "
          f"{stats['unknown']} ids not in the file")

    text = canonical(payload)
    if text is None:
        print("canonical() refused the payload", file=sys.stderr)
        return 1
    after = text.count("\n")
    if after != before:
        print(f"line count changed {before} -> {after}; refusing to write",
              file=sys.stderr)
        return 1
    print(f"line count unchanged at {before}")

    if not args.write:
        print("\n(dry run -- pass --write to emit)")
        return 0
    TARGET.write_text(text, encoding="utf-8")
    print(f"\nwrote {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
