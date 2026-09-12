#!/usr/bin/env python3
"""Tag Śabdapāṭha headwords with the kṛt pratyaya they end in.

The Shabdapatha (dge/data/vedanga/vyakarana/shabdapatha/data.json) stores
fixed nominal stems with no derivational information. But the repo already
GENERATES, per verb root, every common kṛdanta stem with its pratyaya
(tools/build_prakriya.py -> dge/data/vedanga/vyakarana/prakriya/<NN>/*.json,
each entry {k: pratyaya key, t: stem surface, s: steps}). Joining the two on
the exact stem surface tags every Shabdapatha word that IS a generated
kṛdanta with its pratyaya -- e.g. भूत -> क्त, गमन -> ल्युट् -- real derivation
data, not a suffix-shape guess. A word matching several roots' stems with
the same pratyaya is one tag; genuinely different pratyayas (rare) are all
kept, comma-joined.

Writes a `krt` field ("kta" or "kta,lyuw") onto matching items in data.json
IN PLACE, then the caller should re-run tools/build_shabda_shards.py so the
by_akshara shards carry the same field. Words with no match get no field at
all (absence = "not a generated kṛdanta", which is honest -- the generator
covers ~30 pratyayas over the Dhatupatha's roots, not every kṛdanta in the
language).

Idempotent: re-running recomputes every tag from scratch.
"""
import glob
import json
import sys

SHABDA = "dge/data/vedanga/vyakarana/shabdapatha/data.json"
PRAKRIYA_GLOB = "dge/data/vedanga/vyakarana/prakriya/*/*.json"


def build_stem_map():
    stems = {}
    for path in glob.glob(PRAKRIYA_GLOB):
        # krtindex/ and formindex/ shards live one level deeper and do not
        # match this glob, but guard anyway in case layouts shift.
        if "krtindex" in path or "formindex" in path:
            continue
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        for k in d.get("krt") or []:
            stem, key = k.get("t"), k.get("k")
            if stem and key:
                stems.setdefault(stem, set()).add(key)
    return stems


def main():
    stems = build_stem_map()
    print(f"kṛt stems collected: {len(stems)}")
    with open(SHABDA, encoding="utf-8") as f:
        data = json.load(f)
    tagged = cleared = 0
    for it in data.get("items", []):
        keys = stems.get(it.get("word"))
        if keys:
            it["krt"] = ",".join(sorted(keys))
            tagged += 1
        elif it.pop("krt", None) is not None:
            cleared += 1
    with open(SHABDA, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    print(f"tagged {tagged} words, cleared {cleared} stale tags")
    from collections import Counter

    c = Counter(
        k for it in data["items"] for k in (it.get("krt") or "").split(",") if k
    )
    print("by pratyaya:", dict(c.most_common()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
