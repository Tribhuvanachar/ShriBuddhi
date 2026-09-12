#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# This file (unlike the rest of this repo, which is Apache-2.0) is licensed
# AGPL-3.0-or-later: it exists solely to process the AGPL-licensed vendored
# data in vendor/, and its output is a derivative compilation of that data.
"""Build dge/data/vedanga/chandas/data.json from the vendored Chandojnanam CSVs.

Source: hrishikeshrt/chanda ("Chandojnanam"), AGPL-3.0-or-later.
See vendor/NOTICE.md for the pinned commit and the licence caveat.

Usage:
    python3 tools/chandas/build_vrutta_db.py
"""
import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
VENDOR = HERE / "vendor"
OUT = HERE.parent.parent / "dge" / "data" / "vedanga" / "chandas" / "data.json"

SOURCE = "hrishikeshrt/chanda (Chandojnanam) @ 3a9607c6e7a23d60c03d10f839913d01f8bd7ee2"
LICENCE = "AGPL-3.0-or-later"


def _int(v):
    v = v.strip()
    return int(v) if v else None


def _yati(v):
    v = v.strip()
    return [int(x) for x in v.split(",")] if v else []


def _matra_seq(v):
    return [int(x) for x in v.strip().split("-")]


def load_examples():
    with open(VENDOR / "examples.json", encoding="utf-8") as f:
        raw = json.load(f)
    return {name: [line for line in lines if line] for name, lines in raw.items()}


def load_sama(examples):
    items = []
    with open(VENDOR / "chanda_sama.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            names = [n.strip() for n in row["वृत्त"].split(",")]
            entry_examples = []
            for n in names:
                if n in examples:
                    entry_examples = examples[n]
                    break
            items.append({
                "vrutta_names": names,
                "gana": row["गण"],
                "lakshana": row["लक्षण"],
                "akshara_sankhya": _int(row["अक्षरसङ्ख्या"]),
                "matra": _int(row["मात्रा"]),
                "yati": _yati(row["यति"]),
                "examples": entry_examples,
            })
    return items


def load_per_pada(filename):
    """ardhasama / vishama / upajaati share the same column shape:
    vrutta, pada(1-4), lakshana, lakshana (raw), akshara_sankhya, matra, yati
    -- one row per distinct pada, grouped here by vrutta name."""
    by_name = {}
    order = []
    with open(VENDOR / filename, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = row["वृत्त"].strip()
            if name not in by_name:
                by_name[name] = []
                order.append(name)
            by_name[name].append({
                "pada": _int(row["पद"]),
                "lakshana": row["लक्षण"],
                "lakshana_raw": row["लक्षण (raw)"],
                "akshara_sankhya": _int(row["अक्षरसङ्ख्या"]),
                "matra": _int(row["मात्रा"]),
                "yati": _yati(row["यति"]),
            })
    return [{"vrutta_names": [n], "padas": by_name[n]} for n in order]


def load_matra_vrutta():
    items = []
    with open(VENDOR / "chanda_matra.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            items.append({
                "vrutta_names": [row["वृत्त"].strip()],
                "matra_per_pada": _matra_seq(row["मात्रा"]),
            })
    return items


def load_akshara_jaati():
    items = []
    with open(VENDOR / "chanda_jaati.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            items.append({
                "akshara_sankhya": _int(row["अक्षरसंख्या"]),
                "jaati": row["जाति"].strip(),
            })
    return items


def main():
    examples = load_examples()
    sama = load_sama(examples)
    ardhasama = load_per_pada("chanda_ardhasama.csv")
    vishama = load_per_pada("chanda_vishama.csv")
    upajati = load_per_pada("chanda_upajaati.csv")
    matra_vrutta = load_matra_vrutta()
    akshara_jaati = load_akshara_jaati()

    data = {
        "schema": "vedanga_chandas_vrutta_database",
        "source": SOURCE,
        "licence": LICENCE,
        "note": (
            "Sama/ardhasama/vishama/upajati vrutta lakshana, matra-vrutta "
            "matra counts and akshara-count jaati names, for classical "
            "(laukika) Sanskrit metre lookup and identification -- not "
            "Vedic chandas, see PENDING.md for why that's a separate, "
            "unsolved problem. Ingest and build script under tools/chandas/; "
            "tools/chandas/identify_vrutta.py wraps the upstream `chanda` "
            "PyPI library (same project) for actually identifying the "
            "metre of a given verse against this data."
        ),
        "counts": {
            "sama_vrutta": len(sama),
            "ardhasama_vrutta": len(ardhasama),
            "vishama_vrutta": len(vishama),
            "upajati_vrutta": len(upajati),
            "matra_vrutta": len(matra_vrutta),
            "akshara_jaati": len(akshara_jaati),
        },
        "sama_vrutta": sama,
        "ardhasama_vrutta": ardhasama,
        "vishama_vrutta": vishama,
        "upajati_vrutta": upajati,
        "matra_vrutta": matra_vrutta,
        "akshara_jaati": akshara_jaati,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")

    total = sum(data["counts"].values())
    print(f"Wrote {OUT} -- {total} entries across {len(data['counts'])} tables")


if __name__ == "__main__":
    main()
