#!/usr/bin/env python3
"""Move the two English Gītā translations onto the Gītā itself.

From  data/darshana/vedanta/dvaita/Anandamakaranda/gita_prasthana/gita_bhashya/
        tika_english_boray/      — Dr Giridhar Boray, after Rāghavendra Tīrtha's Gītāvivṛti
        tika_english_nadgouda/   — Prof. Gururao V. and Smt. Indira Nadgouda
to    data/itihasa/bhagavad_gita/adhyaya_NN/data.json, as bhashya[] entries.

WHY THEY MOVE. Anandamakaranda is closed, and these two were the only
layers stitched to its Gītā bhāṣya. They are not commentary on that
bhāṣya: every entry is titled with a Gītā verse -- 1.1, 2.47, 18.66 -- and
is that verse in English. So the verse is where they belong, beside the
21 commentators the Gītā already carries.

THE ADDRESSING IS EXACT. All 652 and 649 entries carry a unit_title of the
form ``A.V`` that lands on a real verse of a real adhyāya, with no
duplicate and nothing unmappable. Checked before moving, because a
translation filed against the wrong verse is worse than one not filed at
all.

FOUR ENTRIES DO NOT MOVE. Nadgouda's 2.12, 16.2, 9.31 and 15.18 hold a
line from the book's table of contents, dot leaders and page number and
all -- "Relation of God and the World.......... 270". They are left behind
rather than published against a verse they do not translate.

THE TEXT IS NOT EDITED. Boray's carries the verse in IAST before the
English, and both carry the occasional stray page number from the scan.
Moving a text is not licence to rewrite it; the markup passes through
dge-sanitize.js like the corpus's other 17,086 tags.
"""

from __future__ import annotations

import argparse
import collections
import importlib.util
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
SOURCE = pathlib.Path(
    "data/darshana/vedanta/dvaita/Anandamakaranda/gita_prasthana/gita_bhashya")
TARGET = "data/itihasa/bhagavad_gita/adhyaya_{:02d}/data.json"

LAYERS = {
    "tika_english_boray":
        "Dr. Giridhar Boray (English, after Rāghavendra Tīrtha's Gītāvivṛti)",
    "tika_english_nadgouda":
        "Prof. Gururao V. Nadgouda & Smt. Indira Nadgouda (English)",
}

#: How many verses each adhyāya really has -- an address outside this is a
#: misfiled entry, not a verse.
VERSES = {1: 47, 2: 72, 3: 43, 4: 42, 5: 29, 6: 47, 7: 30, 8: 28, 9: 34,
          10: 42, 11: 55, 12: 20, 13: 35, 14: 27, 15: 20, 16: 24, 17: 28,
          18: 78}

ADDRESS = re.compile(r"^(\d+)\.(\d+)$")
#: A run of dot leaders: the signature of a contents line, not a translation.
CONTENTS_LINE = re.compile(r"\.{6,}")
TAGS = re.compile(r"<[^>]+>")


def canonical(payload: dict) -> str | None:
    spec = importlib.util.spec_from_file_location(
        "format_data_json", HERE.parent / "format_data_json.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.canonical(payload)


def read(folder: str) -> tuple[dict, list]:
    """(address -> text) for one layer, and the entries left behind."""
    d = json.loads((SOURCE / folder / "data.json").read_text(encoding="utf-8"))
    out, skipped = {}, []
    for it in d["items"]:
        unit = (it.get("unit_title") or "").strip()
        m = ADDRESS.match(unit)
        text = (it.get("sanskrit_text") or "").strip()
        if not m or int(m.group(2)) > VERSES.get(int(m.group(1)), 0):
            skipped.append((unit, "not a verse of this text"))
            continue
        plain = TAGS.sub(" ", text)
        if CONTENTS_LINE.search(plain):
            skipped.append((unit, "a line from the table of contents"))
            continue
        if not plain.strip():
            skipped.append((unit, "empty"))
            continue
        key = (int(m.group(1)), int(m.group(2)))
        assert key not in out, f"{folder}: {unit} twice"
        out[key] = text
    return out, skipped


def merge(payload: dict, adhyaya: int, layers: dict) -> collections.Counter:
    stats = collections.Counter()
    for shloka in payload["items"][0]["shlokas"]:
        arr = shloka.setdefault("bhashya", [])
        present = {e.get("commentator") for e in arr}
        for folder, name in LAYERS.items():
            text = layers[folder].get((adhyaya, shloka["number"]))
            if not text:
                continue
            if name in present:
                stats["kept"] += 1
                continue
            arr.append({"commentator": name, "text": text,
                        "language": "english", "kind": "translation"})
            stats["added"] += 1
            stats[folder] += 1
    return stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)

    layers, skipped = {}, {}
    for folder in LAYERS:
        layers[folder], skipped[folder] = read(folder)
        print(f"{folder}: {len(layers[folder])} verses"
              f"{', ' + str(len(skipped[folder])) + ' left behind' if skipped[folder] else ''}")
        for unit, why in skipped[folder]:
            print(f"     {unit}: {why}")

    totals, pending = collections.Counter(), []
    for a in sorted(VERSES):
        path = pathlib.Path(TARGET.format(a))
        original = path.read_text(encoding="utf-8")
        payload = json.loads(original)
        stats = merge(payload, a, layers)
        totals.update(stats)
        text = canonical(payload)
        if text is None:
            print(f"canonical() refused adhyaya {a}", file=sys.stderr)
            return 1
        if text.count("\n") != original.count("\n"):
            print(f"adhyaya {a}: line count changed; refusing", file=sys.stderr)
            return 1
        if stats["added"]:
            pending.append((path, text))

    for folder, name in LAYERS.items():
        print(f"   {totals[folder]:>5}   {name}")
    print(f"\n{totals['added']} entries across {len(pending)} adhyāyas; "
          f"{totals['kept']} already present")
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
