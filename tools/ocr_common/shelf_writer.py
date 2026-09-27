#!/usr/bin/env python3
"""Emit a verse-plus-commentary text in the shape the reader renders.

    {metadata: {...}, shlokas: {"1": {sa, commentaries}, ...}}

One file per section. `lacunae` names the numbers the section's own numbering
reaches past but the OCR did not deliver, and `totalShlokas` is the highest
number the edition itself reaches -- so verse 25 is labelled 25 whether or not
24 survived. Maṇimañjarī is why: a verse vanished there and the count silently
became 305, which nothing noticed because nothing was written down. A declared
hole is a different thing from a silent one, and no text is invented to fill
one.
"""

from __future__ import annotations

import collections
import importlib.util
import json
import pathlib


def canonical(payload: dict) -> str | None:
    """Serialise the way the corpus does, one unit per line."""
    spec = importlib.util.spec_from_file_location(
        "format_data_json",
        pathlib.Path(__file__).resolve().parents[1] / "format_data_json.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.canonical(payload)


def build(rep: dict, *, title, author, source,
          commentary_key: str | None = None, commentary_title: str = "",
          section_name=lambda n: "", file_name=lambda n: f"section_{n}",
          ) -> tuple[dict, collections.Counter]:
    files, stats = {}, collections.Counter()
    for x in rep["sections"]:
        s = x["section"]
        shlokas = {}
        for n in range(1, x["highest"] + 1):
            u = rep["units"].get((s, n))
            if u is None:
                stats["lacuna"] += 1
                continue
            entry = {"sa": u["text"]}
            if commentary_key and u.get("commentary"):
                entry["commentaries"] = {commentary_key: u["commentary"]}
                stats["with_commentary"] += 1
            shlokas[str(n)] = entry
            stats["verses"] += 1
        meta = {
            "title": title(s),
            "author": author,
            "stotraCode": file_name(s),
            "totalShlokas": x["highest"],
            "sargaName": section_name(s),
            "lacunae": x["missing"],
            "source": source,
        }
        if commentary_key:
            meta["availableCommentaries"] = {commentary_key: commentary_title}
        files[file_name(s)] = {"metadata": meta, "shlokas": shlokas}
    return files, stats


def write(files: dict, target: pathlib.Path) -> int:
    for name, payload in files.items():
        d = target / name
        d.mkdir(parents=True, exist_ok=True)
        text = canonical(payload) or (
            json.dumps(payload, ensure_ascii=False, indent=1) + "\n")
        (d / "data.json").write_text(text, encoding="utf-8")
    return len(files)


def report(files: dict, stats: collections.Counter) -> None:
    for name, payload in sorted(files.items()):
        m = payload["metadata"]
        gap = f"  lacunae {len(m['lacunae'])}: {m['lacunae'][:6]}" if m["lacunae"] else ""
        print(f"  {name:<18} {len(payload['shlokas']):>4}/{m['totalShlokas']:<4} "
              f"units{gap}")
    print(f"\n{stats['verses']} verses, {stats['lacuna']} declared lacunae, "
          f"{stats['with_commentary']} with a commentary")
