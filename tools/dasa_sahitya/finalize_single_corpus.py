#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DGE — Dasa Sahitya: fold the remaining local-asset composers into one corpus
=============================================================================

Step 4 of dasa_sahitya_local/ARCHITECTURE.md's "Path to one folder" plan.
The 12 composers confirmed as the SAME person across sources were already
folded in by merge_confirmed_composers.py. This script handles everything
else that's left in dasa_sahitya_local/ after that:

  - dasa1/dasaru/*.json           -- 123 composers with no web-side match
                                      (5 name-root-alike ones were checked by
                                      the project lead and confirmed to be
                                      DIFFERENT people from their web-side
                                      candidates -- so every remaining dasa1
                                      composer becomes its own new composer
                                      file here, none merged into an existing
                                      one)
  - raw_dump/dasaru/ugabhoga.json -- 278 unattributed compositions, folded
                                      into the existing composers/untitled.json
                                      bucket via the same fingerprint dedupe()
                                      used everywhere else in this pipeline,
                                      so an exact duplicate against the web
                                      crawl's own untitled pile collapses
                                      instead of appearing twice

collection_padagalu/ is already empty -- its composers were among the 12
confirmed duplicates and got merged out by the earlier pass.

After this runs, dasa_sahitya_local/ holds nothing new to review; every
composition lives under dge/data/DvaitaVedanta/Itara/DasaSahitya/composers/. Re-running this
script is safe as long as dasa_sahitya_local/dasa1/dasaru/ and
raw_dump/dasaru/ugabhoga.json still exist locally (they are NOT deleted by
this script -- only referenced -- since they live on the
dasa-sahitya-local-dist branch, not in this checkout, when run for real).

Usage:
    python3 tools/DvaitaVedanta/Itara/DasaSahitya/finalize_single_corpus.py \
        --local-dir /path/to/a/checkout/of/dasa-sahitya-local-dist
"""
import argparse
import datetime as _dt
import hashlib
import json
import os
import re

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
WEB_DIR = os.path.join(ROOT, "dge", "data", "DvaitaVedanta/Itara/DasaSahitya")
FETCH_DATE = _dt.date.today().isoformat()

_PUNCT_RE = re.compile(r"[\s।॥.,\-–—’‘'\"()\[\]:;!?|/]+")


def slugify(text):
    text = re.sub(r"[^\w\s-]", "", text or "", flags=re.UNICODE).strip().lower()
    text = re.sub(r"[\s_-]+", "_", text)
    return text or "untitled"


def _fingerprint(rec):
    comp = slugify(rec.get("composer", ""))
    body = "".join("".join(st) for st in rec["text"]["kannada"])
    body = _PUNCT_RE.sub("", body)
    if body:
        return "b:" + hashlib.sha1((comp + "|" + body[:80]).encode()).hexdigest()
    t = (rec["title"].get("kn") or rec["title"].get("latin") or "").strip().lower()
    t = _PUNCT_RE.sub("", t)
    return "t:" + hashlib.sha1((comp + "|" + t).encode()).hexdigest()


def _text_len(rec):
    return sum(len(l) for st in rec["text"]["kannada"] for l in st)


def dedupe(records):
    by_key, dups = {}, 0
    for r in records:
        r.setdefault("also_at", [])
        k = _fingerprint(r)
        if k not in by_key:
            by_key[k] = r
            continue
        dups += 1
        keep = by_key[k]
        if _text_len(r) > _text_len(keep):
            primary, other = r, keep
        else:
            primary, other = keep, r
        urls = [primary["source"]["url"]] + primary["also_at"]
        for u in [other["source"]["url"]] + other["also_at"]:
            if u not in urls:
                primary["also_at"].append(u)
        primary["tags"] = sorted(set(primary["tags"]) | set(other["tags"]))
        if not primary["deity"] and other["deity"]:
            primary["deity"] = other["deity"]
        if not primary["composer"] and other["composer"]:
            primary["composer"] = other["composer"]
        if not primary["meaning"] and other["meaning"]:
            primary["meaning"] = other["meaning"]
        if primary["form"] == "pada" and other["form"] != "pada":
            primary["form"] = other["form"]
        by_key[k] = primary
    return list(by_key.values()), dups


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def dump_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def fold_in_dasa1(local_dir):
    """Every remaining dasa1 composer becomes its own new composer file --
    none of them matched anything already in DvaitaVedanta/Itara/DasaSahitya/composers/ (the 12
    that did were already merged out by merge_confirmed_composers.py, and
    the 5 name-root-alike candidates were confirmed as different people)."""
    src_dir = os.path.join(local_dir, "dasa1", "dasaru")
    comp_dir = os.path.join(WEB_DIR, "composers")
    if not os.path.isdir(src_dir):
        print(f"  (skip: {src_dir} not found)")
        return 0, 0
    n_files, n_recs = 0, 0
    for fn in sorted(os.listdir(src_dir)):
        if not fn.endswith(".json"):
            continue
        d = load_json(os.path.join(src_dir, fn))
        recs = d.get("compositions", [])
        for r in recs:
            r.setdefault("also_at", [])
        out_path = os.path.join(comp_dir, fn)
        if os.path.exists(out_path):
            raise SystemExit(f"refusing to overwrite an existing composer file: {fn} "
                              "-- this composer may already be merged; check by hand")
        dump_json(out_path, {"composer": d.get("composer", ""), "count": len(recs),
                              "compositions": recs})
        n_files += 1
        n_recs += len(recs)
    print(f"  dasa1: added {n_files} new composer files, {n_recs} compositions")
    return n_files, n_recs


def fold_in_raw_dump_ugabhoga(local_dir):
    """The unattributed genre-only ugabhoga.json dump has no composer at
    all -- folds into the existing untitled.json bucket, deduped by content
    fingerprint against what's already there (an exact duplicate of a web
    untitled item collapses instead of appearing twice)."""
    src_path = os.path.join(local_dir, "raw_dump", "dasaru", "ugabhoga.json")
    if not os.path.exists(src_path):
        print(f"  (skip: {src_path} not found)")
        return 0, 0
    new_recs = load_json(src_path).get("compositions", [])
    for r in new_recs:
        r.setdefault("also_at", [])

    untitled_path = os.path.join(WEB_DIR, "composers", "untitled.json")
    existing = load_json(untitled_path)["compositions"] if os.path.exists(untitled_path) else []
    merged, dup_count = dedupe(existing + new_recs)
    dump_json(untitled_path, {"composer": "", "count": len(merged), "compositions": merged})
    print(f"  raw_dump/ugabhoga: folded {len(new_recs)} in, {dup_count} exact duplicates "
          f"collapsed, untitled.json now {len(merged)} total")
    return len(new_recs), dup_count


def rebuild_web_manifest():
    comp_dir = os.path.join(WEB_DIR, "composers")
    manifest_path = os.path.join(WEB_DIR, "index.json")
    manifest = load_json(manifest_path)
    counts_by_composer, counts_by_form, composers_list, total = {}, {}, [], 0
    untitled_composer_count = 0
    for fn in sorted(os.listdir(comp_dir)):
        if not fn.endswith(".json"):
            continue
        d = load_json(os.path.join(comp_dir, fn))
        n = d["count"]
        total += n
        counts_by_composer[d["composer"] or fn] = n
        if not d["composer"]:
            untitled_composer_count += n
        for r in d["compositions"]:
            counts_by_form[r["form"]] = counts_by_form.get(r["form"], 0) + 1
        composers_list.append({"slug": fn[:-5], "composer": d["composer"], "count": n,
                                "file": f"composers/{fn}"})
    manifest["count_total"] = total
    manifest["generated"] = FETCH_DATE
    manifest["counts_by_composer"] = dict(sorted(counts_by_composer.items(), key=lambda x: -x[1]))
    manifest["counts_by_form"] = dict(sorted(counts_by_form.items(), key=lambda x: -x[1]))
    manifest["composers"] = sorted(composers_list, key=lambda c: c["slug"])
    manifest.setdefault("pending", {})
    manifest["pending"]["untitled_composer"] = untitled_composer_count
    manifest["note_merged_from_local_assets"] = (
        f"Fully folded into one corpus on {FETCH_DATE} -- the 12 confirmed cross-source "
        "duplicates by merge_confirmed_composers.py, everything else (123 dasa1 composers "
        "confirmed distinct, the raw_dump ugabhoga pile) by finalize_single_corpus.py. "
        "dasa_sahitya_local/ is retired; see ARCHITECTURE.md for the review history."
    )
    dump_json(manifest_path, manifest)
    print(f"rebuilt {os.path.relpath(manifest_path, ROOT)}: {total} compositions, "
          f"{len(composers_list)} composer files")


def rebuild_counts_report():
    comp_dir = os.path.join(WEB_DIR, "composers")
    total = with_text = multi_source = 0
    by_form, by_composer = {}, {}
    for fn in sorted(os.listdir(comp_dir)):
        if not fn.endswith(".json"):
            continue
        d = load_json(os.path.join(comp_dir, fn))
        for r in d["compositions"]:
            total += 1
            if r.get("text", {}).get("kannada"):
                with_text += 1
            if r.get("also_at"):
                multi_source += 1
            by_form[r["form"]] = by_form.get(r["form"], 0) + 1
        if d["compositions"]:
            by_composer[d["composer"] or fn] = len(d["compositions"])
    report = {
        "generated": FETCH_DATE,
        "total_unique": total,
        "with_text": with_text,
        "multi_source": multi_source,
        "by_form": dict(sorted(by_form.items(), key=lambda x: -x[1])),
        "by_composer": dict(sorted(by_composer.items(), key=lambda x: -x[1])),
    }
    dump_json(os.path.join(WEB_DIR, "counts.json"), report)
    print(f"rebuilt counts.json: {total} total, {with_text} with text, "
          f"{multi_source} found on >1 source")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--local-dir", required=True,
                     help="path to a checkout of the dasa-sahitya-local-dist branch "
                          "(has dasa1/, raw_dump/, collection_padagalu/ at its root)")
    args = ap.parse_args()

    print("== Folding dasa_sahitya_local/ into DvaitaVedanta/Itara/DasaSahitya/ ==")
    fold_in_dasa1(args.local_dir)
    fold_in_raw_dump_ugabhoga(args.local_dir)
    rebuild_web_manifest()
    rebuild_counts_report()
    print("\nDone. dasa_sahitya_local/ has nothing left to review -- see ARCHITECTURE.md.")


if __name__ == "__main__":
    main()
