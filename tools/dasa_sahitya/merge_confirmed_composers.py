#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DGE — Dasa Sahitya cross-source composer merge
==================================================

Folds the 12 composer identities confirmed as the SAME person across the
web crawl (dge/data/DvaitaVedanta/Itara/DasaSahitya/) and the local-asset imports
(dge/data/dasa_sahitya_local/{dasa1,collection_padagalu,raw_dump}) into one
canonical file each under dge/data/DvaitaVedanta/Itara/DasaSahitya/composers/, using the
existing cross-source fingerprint dedupe() from import_DvaitaVedanta/Itara/DasaSahitya.py
(composer + first 80 non-punctuation Kannada chars) so the SAME pada seen
in two sources collapses to one record with both sources recorded in
`also_at`, while genuinely different padas by the same composer stay as
separate entries.

Composer IDENTITY is settled (see dasa_sahitya_local/ALL_SOURCES_composer_
registry.json) — this script does not guess at that. It does NOT touch the
5 "needs_human_review" composers (ambiguous ankita/name-root matches) or
the ~117 composers found in only one source; those stay exactly where they
are.

What it does, per confirmed composer:
  1. Collect every matching record from every source it appears in.
  2. Normalize `composer` to one canonical English name (local sources'
     Kannada name is kept as `composer_local`) so the shared fingerprint
     logic actually finds cross-script duplicates.
  3. Give local-asset records (which have no real source URL) a synthetic
     one, so dedupe()'s `also_at` provenance list stays meaningful instead
     of collapsing every local duplicate under one blank "" URL.
  4. Run the existing dedupe(), write the merged set to
     dge/data/DvaitaVedanta/Itara/DasaSahitya/composers/<canonical_slug>.json, replacing the
     web-only file.
  5. Remove the now-merged dasaru file(s) from dasa_sahitya_local and
     rewrite its index.json so nothing is duplicated across both folders.
  6. Rewrite dge/data/DvaitaVedanta/Itara/DasaSahitya/index.json's composer counts.

Run once: `python3 merge_confirmed_composers.py`. Not idempotent against a
second run after dasa_sahitya_local's source files are already removed --
that is by design (a merge is a one-time promotion, not a repeatable sync).
"""
import datetime as _dt
import hashlib
import json
import os
import re

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
WEB_DIR = os.path.join(ROOT, "dge", "data", "DvaitaVedanta/Itara/DasaSahitya")
LOCAL_DIR = os.path.join(ROOT, "dge", "data", "dasa_sahitya_local")
FETCH_DATE = _dt.date.today().isoformat()

# canonical_english_name -> {
#   "web_prefixes": [composer-field prefixes to match in DvaitaVedanta/Itara/DasaSahitya/composers/*.json],
#   "local": {asset_name: [kannada composer names as they appear in that asset]},
# }
CONFIRMED = {
    "Purandara Dasaru": {
        "web_prefixes": ["Purandara Dasaru"],
        "local": {"dasa1": ["ಪುರಂದರದಾಸರು"], "collection_padagalu": ["ಪುರಂದರದಾಸ"],
                  "raw_dump": ["ಪುರಂದರದಾಸರು"]},
    },
    "Vijaya Dasaru": {
        "web_prefixes": ["Vijaya Dasaru", "Vijayadasaru"],
        "local": {"dasa1": ["ವಿಜಯದಾಸರು"]},
    },
    "Kanaka Dasaru": {
        "web_prefixes": ["Kanaka Dasaru"],
        "local": {"dasa1": ["ಕನಕದಾಸರು"], "collection_padagalu": ["ಕನಕದಾಸ"],
                  "raw_dump": ["ಕನಕದಾಸರು"]},
    },
    "Gopala Dasaru": {
        "web_prefixes": ["Gopala Dasaru", "Gopala Dasa"],
        "local": {"dasa1": ["ಗೋಪಾಲದಾಸರು"], "raw_dump": ["ಗೋಪಾಲದಾಸರು"]},
    },
    "Pranesha Dasaru": {
        "web_prefixes": ["Pranesha Dasaru"],
        "local": {"dasa1": ["ಪ್ರಾಣೇಶದಾಸರು"]},
    },
    "Jagannatha Dasaru": {
        "web_prefixes": ["Jagannatha Dasaru"],
        "local": {"dasa1": ["ಜಗನ್ನಾಥದಾಸರು"]},
    },
    "Prasanna Venkata Dasaru": {
        "web_prefixes": ["Prasanna Venkata Dasaru"],
        "local": {"dasa1": ["ಪ್ರಸನ್ನವೆಂಕಟದಾಸರು"]},
    },
    "Vadirajaru": {
        "web_prefixes": ["Vadirajaru"],
        "local": {"dasa1": ["ವಾದಿರಾಜ"]},
    },
    "Sripadarajaru": {
        "web_prefixes": ["Sripadarajaru"],
        "local": {"dasa1": ["ಶ್ರೀಪಾದರಾಜರು"], "collection_padagalu": ["ಶ್ರೀಪಾದರಾಜರು"]},
    },
    "Vyasarayaru": {
        "web_prefixes": ["Vyasarayaru", "Vyasarajaru"],
        "local": {"dasa1": ["ವ್ಯಾಸರಾಯರು"], "collection_padagalu": ["ವ್ಯಾಸರಾಯರು"]},
    },
    "Helavanakatte Giriyamma": {
        "web_prefixes": ["Helavanakatte Giriyamma"],
        "local": {"dasa1": ["ಹೆಳವನಕಟ್ಟೆ ಗಿರಿಯಮ್ಮ"]},
    },
    "Mohana Dasaru": {
        "web_prefixes": ["Mohana Dasaru"],
        "local": {"dasa1": ["ಮೋಹನದಾಸರು"]},
    },
}

# --------------------------------------------------------------------------- #
# Inlined from tools/DvaitaVedanta/Itara/DasaSahitya/import_DvaitaVedanta/Itara/DasaSahitya.py's dedupe()/slugify(),
# verbatim, rather than importing that module -- it pulls in requests/bs4 for
# its (unrelated, network-only) scraping code, which this merge script has no
# business depending on.
# --------------------------------------------------------------------------- #
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


def web_records_for(prefixes):
    """Return (records, consumed_filenames) for every web composer file
    whose `composer` field starts with one of `prefixes`."""
    records, consumed = [], []
    comp_dir = os.path.join(WEB_DIR, "composers")
    for fn in sorted(os.listdir(comp_dir)):
        if not fn.endswith(".json"):
            continue
        d = load_json(os.path.join(comp_dir, fn))
        name = d.get("composer", "")
        if any(name == p or name.startswith(p + " ") or name.startswith(p) for p in prefixes):
            for r in d["compositions"]:
                r.setdefault("also_at", [])
                records.append(r)
            consumed.append(fn)
    return records, consumed


def local_records_for(asset, kn_names, canonical):
    """Return (pada_records, bio_records, consumed_paths) for one
    (asset, kannada-name-list) pair across dasa_sahitya_local."""
    asset_dir = os.path.join(LOCAL_DIR, asset, "dasaru")
    if not os.path.isdir(asset_dir):
        return [], [], []
    pada_records, bio_records, consumed = [], [], []
    for fn in sorted(os.listdir(asset_dir)):
        path = os.path.join(asset_dir, fn)
        d = load_json(path)
        composer = d.get("composer", "")
        if composer not in kn_names:
            continue
        consumed.append(path)
        for i, r in enumerate(d["compositions"]):
            r["composer_local"] = r.get("composer", composer)
            r["composer"] = canonical
            r.setdefault("also_at", [])
            # Synthesize a stable, distinguishing locator so dedupe()'s
            # also_at provenance doesn't collapse every local-source
            # duplicate under one blank "" url.
            locator = f"local://{asset}/{fn.replace('.json','')}/{i}"
            r["source"]["url"] = r["source"].get("url") or locator
            if r.get("form") == "note":
                bio_records.append(r)
            else:
                pada_records.append(r)
    return pada_records, bio_records, consumed


def merge_one(canonical, spec):
    web_recs, web_files = web_records_for(spec["web_prefixes"])
    all_recs = list(web_recs)
    bio_notes = []
    local_consumed = []
    for asset, kn_names in spec["local"].items():
        pada_recs, bio_recs, consumed = local_records_for(asset, kn_names, canonical)
        all_recs.extend(pada_recs)
        bio_notes.extend(bio_recs)
        local_consumed.extend(consumed)

    for r in all_recs:
        r["composer"] = canonical
        if "composer_iast" in r:
            r.pop("composer_iast", None)  # web schema doesn't carry this field

    merged, dup_count = dedupe(all_recs)
    merged.sort(key=lambda r: (r["title"].get("kn") or r["title"].get("latin") or ""))

    return {
        "canonical": canonical,
        "merged": merged,
        "bio_notes": bio_notes,
        "raw_count": len(all_recs),
        "dup_count": dup_count,
        "web_files_consumed": web_files,
        "local_paths_consumed": local_consumed,
    }


def main():
    results = []
    for canonical, spec in CONFIRMED.items():
        res = merge_one(canonical, spec)
        results.append(res)
        slug = slugify(canonical)
        out = {
            "composer": canonical,
            "count": len(res["merged"]),
            "bio_notes": res["bio_notes"],
            "compositions": res["merged"],
        }
        dump_json(os.path.join(WEB_DIR, "composers", f"{slug}.json"), out)
        print(f"[{canonical}] {res['raw_count']} raw -> {len(res['merged'])} unique "
              f"({res['dup_count']} cross-source duplicates merged), "
              f"{len(res['bio_notes'])} bio note(s)")

        # Remove now-superseded web files that aren't the canonical slug's own file
        # (e.g. purandara_dasaru_part_1.json, gopala_dasa.json, vyasarajaru.json).
        for fn in res["web_files_consumed"]:
            if fn != f"{slug}.json":
                p = os.path.join(WEB_DIR, "composers", fn)
                if os.path.exists(p):
                    os.remove(p)
                    print(f"    removed superseded web file: {fn}")

        # Remove the now-merged local dasaru files.
        for p in res["local_paths_consumed"]:
            if os.path.exists(p):
                os.remove(p)
                print(f"    removed merged local file: {os.path.relpath(p, ROOT)}")

    # Rebuild dge/data/DvaitaVedanta/Itara/DasaSahitya/index.json + counts.json from what's on disk now.
    rebuild_web_manifest()
    for asset in ("dasa1", "collection_padagalu", "raw_dump"):
        rebuild_local_manifest(asset)

    print("\nDone.")


def rebuild_web_manifest():
    comp_dir = os.path.join(WEB_DIR, "composers")
    manifest_path = os.path.join(WEB_DIR, "index.json")
    manifest = load_json(manifest_path)
    counts_by_composer, counts_by_form, composers_list, total = {}, {}, [], 0
    for fn in sorted(os.listdir(comp_dir)):
        if not fn.endswith(".json"):
            continue
        d = load_json(os.path.join(comp_dir, fn))
        n = d["count"]
        total += n
        counts_by_composer[d["composer"] or fn] = n
        for r in d["compositions"]:
            counts_by_form[r["form"]] = counts_by_form.get(r["form"], 0) + 1
        composers_list.append({"slug": fn[:-5], "composer": d["composer"], "count": n,
                                "file": f"composers/{fn}"})
    manifest["count_total"] = total
    manifest["generated"] = FETCH_DATE
    manifest["counts_by_composer"] = dict(sorted(counts_by_composer.items(), key=lambda x: -x[1]))
    manifest["counts_by_form"] = dict(sorted(counts_by_form.items(), key=lambda x: -x[1]))
    manifest["composers"] = sorted(composers_list, key=lambda c: c["slug"])
    manifest["note_merged_from_local_assets"] = (
        f"12 composers folded in from dasa_sahitya_local via merge_confirmed_composers.py "
        f"on {FETCH_DATE}; see dge/data/dasa_sahitya_local/ARCHITECTURE.md for the review "
        "that confirmed these identities before merging."
    )
    dump_json(manifest_path, manifest)
    print(f"rebuilt {os.path.relpath(manifest_path, ROOT)}: {total} compositions, "
          f"{len(composers_list)} composer files")


def rebuild_local_manifest(asset):
    asset_dir = os.path.join(LOCAL_DIR, asset)
    dasaru_dir = os.path.join(asset_dir, "dasaru")
    manifest_path = os.path.join(asset_dir, "index.json")
    if not os.path.exists(manifest_path) or not os.path.isdir(dasaru_dir):
        return
    manifest = load_json(manifest_path)
    remaining = {os.path.splitext(f)[0] for f in os.listdir(dasaru_dir) if f.endswith(".json")}
    kept = [d for d in manifest.get("dasaru", []) if d["slug"] in remaining]
    manifest["dasaru"] = kept
    manifest["count_total"] = sum(d["count"] for d in kept)
    manifest["count_dasaru"] = len(kept)
    manifest["note_confirmed_composers_merged_out"] = (
        f"Composers confirmed as duplicates of the web corpus were merged into "
        f"dge/data/DvaitaVedanta/Itara/DasaSahitya/composers/ and removed from here by "
        f"merge_confirmed_composers.py on {FETCH_DATE}; see that folder's file for the "
        "merged record, and ALL_SOURCES_composer_registry.json for which composers those were."
    )
    dump_json(manifest_path, manifest)
    print(f"rebuilt {os.path.relpath(manifest_path, ROOT)}: {len(kept)} dasaru remaining")


if __name__ == "__main__":
    main()
