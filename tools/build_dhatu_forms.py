#!/usr/bin/env python3
"""Build per-root lakara conjugation tables (dge/data/vedanga/vyakarana/dhatuforms/<code>.json)
from ashtadhyayi-com/data's dhatuforms_vidyut_*.txt files.

Ten finite-verb tables (Issue 15's "Lunganta / Yang-lunganta / Sananta / Nichanta /
Karmani / Kartari" ask) -- shuddha (basic), san (desiderative), nich (causative),
yang (intensive), yangluk (intensive-luk), each in kartari (active) and karmani
(passive) voice, each carrying all 10 lakaras x 9 persons/numbers. The krut
(participle/krdanta) tables are NOT imported here: dge/krdanta.html already
derives those live from vidyut-prakriya (js/prakriya.js), so importing a static
copy would just be redundant data with no reader benefit.

One JSON file per root (same chunking shape as data/vedanga/vyakarana/vritti/<code>.json)
rather than 10 monolithic multi-MB files, so a reader only downloads the one root
they open.

Usage:
    python3 tools/build_dhatu_forms.py /path/to/ashtadhyayi-com/data
"""
import json
import sys
from pathlib import Path

# (json key prefix in the source file, our field name). shuddha_kartari is
# deliberately NOT included: dge/data/vedanga/vyakarana/prakriya/<gana>/<code>.json
# (built by tools/build_prakriya.py from vidyut-prakriya, no external data
# dependency) already derives that exact table -- basic active voice, 8 of its
# 10 lakaras -- and dge/prakriya.html already shows it with its full
# step-by-step derivation. Re-importing it here would be the same wordforms
# twice from two independently-generated sources, a real risk of the two
# quietly disagreeing on some root with no way for a reader to tell which is
# right.
VOICES = [
    ("shuddha", "karmani"),
    ("san", "kartari"), ("san", "karmani"),
    ("nich", "kartari"), ("nich", "karmani"),
    ("yang", "kartari"), ("yang", "karmani"),
    ("yangluk", "kartari"), ("yangluk", "karmani"),
]

SOURCE_NOTE = ("ashtadhyayi-com/data (github.com/ashtadhyayi-com/data, commit 24109f7, "
               "dhatu/dhatuforms_vidyut_*.txt); its README: \"free to use ... provided "
               "that appropriate credits are mentioned\".")


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: build_dhatu_forms.py /path/to/ashtadhyayi-com/data")
    src_root = Path(sys.argv[1]) / "dhatu"
    out_dir = Path(__file__).resolve().parent.parent / "dge" / "data" / "vedanga" / "vyakarana" / "dhatuforms"
    out_dir.mkdir(parents=True, exist_ok=True)

    # by_code[code][gana_key][pada_key] = {lakara: formstring}
    by_code = {}
    counts = {}
    for gana_key, pada_key in VOICES:
        fname = src_root / f"dhatuforms_vidyut_{gana_key}_{pada_key}.txt"
        data = json.loads(fname.read_text(encoding="utf-8"))
        counts[(gana_key, pada_key)] = len(data)
        for code, forms in data.items():
            by_code.setdefault(code, {}).setdefault(gana_key, {})[pada_key] = forms

    n_written = 0
    for code, ganas in by_code.items():
        out = {"id": code, "source": SOURCE_NOTE, "forms": ganas}
        (out_dir / f"{code}.json").write_text(
            json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        n_written += 1

    index = {"available": sorted(by_code.keys())}
    (out_dir / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    print("per-file source counts:", {f"{g}_{p}": n for (g, p), n in counts.items()})
    print(f"wrote {n_written} root files + index.json to {out_dir}")


if __name__ == "__main__":
    main()
