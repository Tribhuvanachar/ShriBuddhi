#!/usr/bin/env python3
"""Turn the segmented Pāṣaṇḍakhaṇḍanam into its shelf file.

पाषण्डखण्डनम् of Śrī Vādirāja Tīrtha with the vyākhyā of Śrī Surottama Tīrtha,
129 verses in one continuous run. It sits under Tattvavada/Itara beside the
Yukti Mallikā, which is Vādirāja's too.

    data/Tattvavada/Itara/pasandakhandana/mula/data.json
    {metadata: {...}, shlokas: {"1": {sa, commentaries}, ...}}

    python3 tools/pasandakhandana/write_layers.py
    python3 tools/pasandakhandana/write_layers.py --write
"""

from __future__ import annotations

import argparse
import collections
import importlib.util
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "ocr_common"))
import segment as seg  # noqa: E402
import staged as S  # noqa: E402

TARGET = pathlib.Path("data/Tattvavada/Itara/pasandakhandana/mula")
COMMENTARY_KEY = "surottamatirtha"
COMMENTARY_TITLE = "व्याख्या — श्रीसुरोत्तमतीर्थः"
SOURCE = {
    "edition": "पाषण्डखण्डनम् — Pāṣaṇḍakhaṇḍanam of Śrī Vādirāja Tīrtha, with "
               "the vyākhyā of Śrī Surottama Tīrtha",
    "ocr": "Sarvam Document AI, 50 pages, with a Google Vision pass over the "
           "same book; segmented by tools/pasandakhandana/segment.py",
}


def build(pages: dict[int, str]) -> tuple[dict, collections.Counter]:
    rep = seg.segment(pages)
    stats = collections.Counter()
    shlokas = {}
    for n in range(1, rep["highest"] + 1):
        v = rep["verses"].get(n)
        if v is None:
            stats["lacuna"] += 1
            continue
        entry = {"sa": v["text"]}
        if v.get("commentary"):
            entry["commentaries"] = {COMMENTARY_KEY: v["commentary"]}
            stats["with_commentary"] += 1
        shlokas[str(n)] = entry
        stats["verses"] += 1
    payload = {
        "metadata": {
            "title": "Pāṣaṇḍakhaṇḍanam",
            "author": "Vadiraja Tirtha",
            "stotraCode": "pasandakhandana",
            "totalShlokas": rep["highest"],
            "availableCommentaries": {COMMENTARY_KEY: COMMENTARY_TITLE},
            "lacunae": rep["missing"],
            "source": SOURCE,
        },
        "shlokas": shlokas,
    }
    return payload, stats


def canonical(payload: dict) -> str | None:
    spec = importlib.util.spec_from_file_location(
        "format_data_json",
        pathlib.Path(__file__).resolve().parents[1] / "format_data_json.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.canonical(payload)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--staged-dir",
                    default="data/ocr_staging/"
                            "pasandakhandanam_vad__mentary_surottama_tirtha")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)
    pages = S.load_sarvam(args.staged_dir)
    if not pages:
        print(f"no delivered pages under {args.staged_dir}", file=sys.stderr)
        return 1
    payload, stats = build(pages)
    m = payload["metadata"]
    print(f"  {len(payload['shlokas'])}/{m['totalShlokas']} verses, "
          f"{stats['with_commentary']} with the vyākhyā, "
          f"{stats['lacuna']} lacunae {m['lacunae'][:8]}")
    if not args.write:
        print("\n(dry run -- pass --write to emit)")
        return 0
    TARGET.mkdir(parents=True, exist_ok=True)
    text = canonical(payload) or (
        json.dumps(payload, ensure_ascii=False, indent=1) + "\n")
    (TARGET / "data.json").write_text(text, encoding="utf-8")
    print(f"\nwrote {TARGET / 'data.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
