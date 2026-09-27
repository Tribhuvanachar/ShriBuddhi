#!/usr/bin/env python3
"""Merge the five mūla-Gītā vyākhyānas into the Gītā they comment on.

    data/itihasa/bhagavad_gita/adhyaya_01..18/data.json

The Gītā is already on the shelf, all 700 verses, each carrying a
``bhashya`` array that already holds 21 commentators. So these five do not
become a grantha of their own; they go where the others are.

FIVE OF FIFTEEN. The edition prints fifteen vyākhyānas and ten are already
in the library -- the Gītābhāṣya division under
DvaitaVedantaIn/gita_prasthana/gita_bhashya/ and the Gītātātparya division
under gita_tatparya_nirnaya/, matched by author rather than by title. Only
the मूलगीताविभागः, the five that comment on the mūla verse itself, is
absent, and only those are written.

MERGE, NEVER REPLACE, AND NEVER TWICE. An entry is appended only when that
commentator is not already on that verse, so a second run changes nothing.

THE FILES ARE REWRITTEN THROUGH canonical(), NOT json.dump. It round-trips
each of the eighteen byte-for-byte, and the line count is checked before
and after.
"""

from __future__ import annotations

import argparse
import collections
import importlib.util
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "ocr_common"))


def _load(name: str, path: pathlib.Path):
    """Under a name of its own -- every segmenter here is ``segment.py``."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


seg = _load("gita_sangraha_segment", HERE / "segment.py")

TARGET = "data/itihasa/bhagavad_gita/adhyaya_{:02d}/data.json"

#: The five, as they will read in the commentator picker.
COMMENTATORS = {
    "gitavivrti": "Śrī Vidyādhirāja Tīrtha (Gītāvivṛti)",
    "gitalakshalankara": "Śrī Vādirāja Tīrtha (Gītālakṣālaṅkāra)",
    "gitasarasangraha": "Śrī Rāghavendra Tīrtha (Gītāsārasaṅgraha)",
    "anvayaprakashika": "Śrī Rāghavendra Yati (Gītānvayaprakāśikā)",
    "trividharthavivrti": "Pāṅgarī Śrīnivāsācārya (Trividhārthavivṛti)",
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
    """verse id -> {key: text}, joining the halves of a split verse.

    A long verse is set as two half-verses under two ``गītā`` titles and
    both address the verse they are halves of, so their commentary is
    joined rather than one half overwriting the other.
    """
    out: dict[str, dict[str, str]] = {}
    for u in units:
        vid = u.get("id")
        if not vid:
            continue
        for key in u["order"]:
            if key not in COMMENTATORS:
                continue
            text = " ".join(u["layers"][key].split())
            if len(text) < MIN_CHARS:
                continue
            bucket = out.setdefault(vid, {})
            bucket[key] = (bucket[key] + " " + text).strip() if key in bucket else text
    return out


def merge(payload: dict, found: dict[int, dict[str, str]]) -> dict:
    """Append to each verse's bhashya array, skipping what is already there."""
    stats = collections.Counter()
    for shloka in payload["items"][0]["shlokas"]:
        layers = found.get(shloka["number"])
        if not layers:
            continue
        arr = shloka.setdefault("bhashya", [])
        present = {e.get("commentator") for e in arr}
        touched = False
        for key, text in sorted(layers.items()):
            name = COMMENTATORS[key]
            if name in present:
                stats["kept"] += 1
                continue
            arr.append({"commentator": name, "text": text,
                        "language": "sanskrit", "kind": "commentary"})
            stats["added"] += 1
            stats[key] += 1
            touched = True
        if touched:
            stats["verses"] += 1
    return stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)

    units = seg.segment()
    found = collect(units)
    print(f"{len(units)} verse blocks, "
          f"{sum(1 for u in units if u.get('id'))} addressed, "
          f"{len(found)} verses carrying a new commentary")

    totals, written = collections.Counter(), 0
    pending: list[tuple[pathlib.Path, str]] = []
    for a in seg.ADHYAYAS:
        path = pathlib.Path(TARGET.format(a))
        original = path.read_text(encoding="utf-8")
        payload = json.loads(original)
        mine = {int(vid.split(".")[1]): layers
                for vid, layers in found.items()
                if int(vid.split(".")[0]) == a}
        stats = merge(payload, mine)
        totals.update(stats)
        text = canonical(payload)
        if text is None:
            print(f"canonical() refused adhyaya {a}", file=sys.stderr)
            return 1
        if text.count("\n") != original.count("\n"):
            print(f"adhyaya {a}: line count changed; refusing to write",
                  file=sys.stderr)
            return 1
        if stats["added"]:
            pending.append((path, text))
            written += 1

    for key, name in sorted(COMMENTATORS.items()):
        print(f"   {totals[key]:>5}   {name}")
    print(f"\n{totals['added']} commentaries added across {totals['verses']} "
          f"verses in {written} adhyāyas; {totals['kept']} already present")
    print("every adhyāya's line count unchanged")

    if not args.write:
        print("\n(dry run -- pass --write to emit)")
        return 0
    for path, text in pending:
        path.write_text(text, encoding="utf-8")
    print(f"\nwrote {len(pending)} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
