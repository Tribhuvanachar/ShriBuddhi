#!/usr/bin/env python3
"""
build_destinations.py -- where does each upstream section end up in ShriBuddhi, and what did we call it?

ParaBuddhi holds the origin's data untouched; ShriBuddhi strips the origin's tags, rearranges and
stitches (SarvaMula, for one, is the SetuTila text with tīkā and ṭippaṇī pulled in from
dvaitavedanta.in and anandamakaranda.in). To keep a weekly sync honest, every upstream section needs
a recorded destination, and every origin label a recorded name of ours. That record is
ParaBuddhi's  import_config/destinations.registry.json  (format: docs/SOURCE_DESTINATIONS.md).

This tool SEEDS it from what already exists, and re-derives it on demand:

  * ParaBuddhi's provenance/source/**/map.jsonl: per unit, the origin's own tags (`cls`, `layer`,
    `chunk`, `work`, `type`, `chapter`, `repo`/`path`, ...), its reference breadcrumb, and the staged
    path it was written to;
  * ShriBuddhi's data/ tree: where that staged path actually lives here (matched by the longest
    unique path suffix; a section that cannot be matched uniquely is listed as `unresolved` with its
    candidates, never guessed).

The hand-edited parts of an existing registry (`decision`, `note`, a manually set `destination`) are
kept; re-running only adds what is new and refreshes counts.

    python3 tools/watch/build_destinations.py --pb ../parabuddhi --sb . [--write]
    python3 tools/watch/build_destinations.py --pb ../parabuddhi --sb . --check     # exit 1 if a destination is missing

NOTE: the registry lives in ParaBuddhi. It names origins (that is its job) and must never be copied
into the public tree.
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import sys

TAG_KEYS = {  # per site: which origin fields are the site's own labels
    "setutila.in": ("cls", "chunk"),
    "dvaitavedanta.in": ("layer", "work_id"),
    "anandamakaranda.in": ("type", "chapter"),
    "advaitasharada.sringeri.net": ("work",),
    "srivaishnavan.com": ("page",),
    "vishvasa": ("repo", "layer"),
    "tirthaprabandha.wordpress.com": ("prabandha", "kshetra"),
    "srimadhvyasa.wordpress.com": ("layer",),
    "upanishat.com": ("layer",),
}


def sb_index(sb):
    idx = collections.defaultdict(list)
    for dp, dn, fn in os.walk(os.path.join(sb, "data")):
        dn[:] = [d for d in dn if not d.startswith("_") and d not in ("ocr_staging", "kosha", "kamadhenu")]
        if "data.json" in fn:
            rel = os.path.relpath(dp, os.path.join(sb, "data")).replace(os.sep, "/")
            parts = rel.split("/")
            for k in range(1, len(parts) + 1):
                idx["/".join(parts[-k:])].append(rel)
    return idx


def resolve(staged_dir, idx):
    parts = staged_dir.split("/")
    for k in range(len(parts), 1, -1):
        c = idx.get("/".join(parts[-k:]))
        if c is not None:
            return sorted(set(c))
    return []


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--pb", required=True)
    ap.add_argument("--sb", default=".")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    reg_path = os.path.join(a.pb, "import_config", "destinations.registry.json")
    old = json.load(open(reg_path, encoding="utf-8")) if os.path.exists(reg_path) else {}
    old_by = {(s, e.get("key")): e for s, v in (old.get("sources") or {}).items() for e in v.get("sections", [])}
    idx = sb_index(a.sb)

    srcs = {}
    for mf in sorted(glob.glob(os.path.join(a.pb, "provenance", "source", "**", "map.jsonl"), recursive=True)):
        rel = os.path.relpath(mf, os.path.join(a.pb, "provenance", "source")).replace(os.sep, "/")
        site = rel.split("/")[0]
        staged_dir = os.path.dirname(os.path.dirname(rel[len(site) + 1:]))  # drop /data.json/map.jsonl
        tags = TAG_KEYS.get(site, ())
        groups = collections.OrderedDict()
        for line in open(mf, encoding="utf-8"):
            o = json.loads(line).get("origin", {})
            sig = tuple(str(o.get(t, "")) for t in tags)
            g = groups.setdefault(sig, {"units": 0, "sample_reference": "", "sample_url": ""})
            g["units"] += 1
            if not g["sample_reference"]:
                g["sample_reference"] = str(o.get("origin_reference", ""))[:160]
                g["sample_url"] = str(o.get("url", ""))
        cands = resolve(staged_dir, idx)
        for sig, g in groups.items():
            key = "%s|%s" % (staged_dir, "|".join(sig))
            e = {"key": key,
                 "origin_tags": dict(zip(tags, sig)),
                 "origin_sample": g["sample_reference"],
                 "origin_url_sample": g["sample_url"],
                 "units": g["units"],
                 "staged_path": staged_dir,
                 "destination": cands[0] if len(cands) == 1 else None,
                 "candidates": cands if len(cands) != 1 else [],
                 "status": "mapped" if len(cands) == 1 else ("ambiguous" if cands else "unresolved")}
            prev = old_by.get((site, key))
            if prev:
                for hand in ("decision", "note", "our_label", "layer_kind", "commentator"):
                    if hand in prev:
                        e[hand] = prev[hand]
                if prev.get("destination") and prev.get("status") in ("mapped", "manual"):
                    e["destination"], e["status"], e["candidates"] = prev["destination"], prev.get("status", "manual"), []
            srcs.setdefault(site, {"sections": []})["sections"].append(e)

    for site, v in srcs.items():
        tally = collections.Counter(e["status"] for e in v["sections"])
        v["summary"] = dict(tally)
        # which of OUR layer names each origin label became (the label map)
        lab = collections.defaultdict(collections.Counter)
        for e in v["sections"]:
            if e["destination"] and e["origin_tags"]:
                first = next(iter(e["origin_tags"].values()))
                lab[first][os.path.basename(e["destination"])] += e["units"]
        v["label_map"] = {k: dict(c.most_common(3)) for k, c in lab.items() if k}

    doc = {"_readme": ["Where each upstream section lands in ShriBuddhi, and what each origin label became.",
                       "Built by tools/watch/build_destinations.py from provenance/ and ShriBuddhi's data/; hand edits",
                       "(decision, note, our_label, layer_kind, commentator, a manual destination) survive a rebuild.",
                       "status: mapped (one ShriBuddhi folder), ambiguous (several candidates: set `destination`), unresolved",
                       "(no match: either not stitched in yet, or renamed -- set `destination` or `decision: not_used`),",
                       "manual (a person set it).  See docs/SOURCE_DESTINATIONS.md in ShriBuddhi.",
                       "PRIVATE: names origins. Never copy into a public tree."],
           "sources": srcs}
    total = collections.Counter(e["status"] for v in srcs.values() for e in v["sections"])
    print("sources:", len(srcs), " sections:", sum(total.values()), dict(total))
    for site, v in srcs.items():
        print("  %-30s %s" % (site, v["summary"]))
    bad = [e for v in srcs.values() for e in v["sections"] if e["status"] != "mapped" and e.get("decision") != "not_used"
           and e["status"] != "manual"]
    if a.write:
        os.makedirs(os.path.dirname(reg_path), exist_ok=True)
        json.dump(doc, open(reg_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("wrote", reg_path)
    if a.check and bad:
        print("%d section(s) have no confirmed destination" % len(bad), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
