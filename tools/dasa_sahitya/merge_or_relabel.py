#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DGE — Dasa Sahitya: merge two composers, or move/relabel one composition
==========================================================================

The reusable tool the project lead asked for after the 21 Aug 2026 one-folder
merge: composer identity and category guesses are calls made by a human
looking at real examples, and that call can change later (a name turns out
to be the same person after all; a song is filed under the wrong form). This
script is how that change gets applied, WITHOUT hand-editing composer JSON
files or re-deriving the manifest by hand every time.

Both subcommands rewrite data/DvaitaVedanta/Itara/DasaSahitya/index.json and counts.json
before exiting, so the corpus is never left in a state where the manifest
disagrees with what's actually on disk.

--------------------------------------------------------------------------
1. Two composers turn out to be the same person:

    python3 tools/DvaitaVedanta/Itara/DasaSahitya/merge_or_relabel.py merge-composers \
        --from gopalaryaru --into gopala_dasaru \
        [--canonical-name "Gopala Dasaru"]

   Combines every composition from both composer files under one canonical
   name, running the same fingerprint dedupe() the web importer and the
   19 Aug composer merge both use (composer + first 80 Kannada chars) so an
   actual same-pada-in-both duplicate collapses instead of appearing twice.
   The --from file is deleted; --into is overwritten with the merged set.
   --canonical-name defaults to --into's existing composer name.

2. One song needs a different form (category) and/or a different composer:

    python3 tools/DvaitaVedanta/Itara/DasaSahitya/merge_or_relabel.py relabel \
        --composer gopalaryaru --id gopalaryaru__dasa1_1234 \
        --form suladi --move-to gopala_dasaru

   --form alone just changes that one record's form in place. --move-to
   alone (no --form) moves the record to a different composer file,
   updating its `composer` field and `tags` to match, without touching its
   form. Both together do both. If --move-to names a composer file that
   doesn't exist yet, it's created fresh with just this one record.

3. Finding a composition's id when you only know the title:

    python3 tools/DvaitaVedanta/Itara/DasaSahitya/merge_or_relabel.py find --composer gopalaryaru --title-contains "ಕರುಣ"

Every operation is one call, always ends with a rebuilt manifest -- there is
deliberately no "preview" mode: run `find` first to confirm you have the
right id, then act.
"""
import argparse
import datetime as _dt
import hashlib
import json
import os
import re

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
COMP_DIR = os.path.join(ROOT, "data", "DvaitaVedanta/Itara/DasaSahitya", "composers")
MANIFEST_PATH = os.path.join(ROOT, "data", "DvaitaVedanta/Itara/DasaSahitya", "index.json")
COUNTS_PATH = os.path.join(ROOT, "data", "DvaitaVedanta/Itara/DasaSahitya", "counts.json")
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
        primary, other = (r, keep) if _text_len(r) > _text_len(keep) else (keep, r)
        urls = [primary["source"]["url"]] + primary["also_at"]
        for u in [other["source"]["url"]] + other["also_at"]:
            if u not in urls:
                primary["also_at"].append(u)
        primary["tags"] = sorted(set(primary["tags"]) | set(other["tags"]))
        if not primary["deity"] and other["deity"]:
            primary["deity"] = other["deity"]
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
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def composer_payload(composer, items, bio_notes=""):
    return {"schema": "dasa_pada_text", "default_author": composer,
            "composer": composer, "count": len(items),
            "bio_notes": bio_notes, "items": items}


def comp_path(slug):
    # composers/<slug>/data.json, not a flat composers/<slug>.json -- the
    # taxonomy/library.json leaf convention (21 Aug 2026 restructure); the
    # directory is created lazily by dump_json's caller sites that write a
    # NEW composer file (merge/move destinations), not read here.
    return os.path.join(COMP_DIR, slug, "data.json")


def load_composer(slug):
    p = comp_path(slug)
    if not os.path.exists(p):
        raise SystemExit(f"no composer file for '{slug}' at {p}")
    return load_json(p)


def rebuild_manifest():
    counts_by_composer, counts_by_form, composers_list, total = {}, {}, [], 0
    untitled_composer_count = with_text = multi_source = 0
    for slug in sorted(os.listdir(COMP_DIR)):
        leaf = os.path.join(COMP_DIR, slug, "data.json")
        if not os.path.isfile(leaf):
            continue
        d = load_json(leaf)
        n = d["count"]
        total += n
        counts_by_composer[d["composer"] or slug] = n
        if not d["composer"]:
            untitled_composer_count += n
        for r in d["items"]:
            counts_by_form[r["form"]] = counts_by_form.get(r["form"], 0) + 1
            if r.get("text", {}).get("kannada"):
                with_text += 1
            if r.get("also_at"):
                multi_source += 1
        composers_list.append({"slug": slug, "composer": d["composer"], "count": n,
                                "file": f"composers/{slug}/data.json"})
    manifest = load_json(MANIFEST_PATH)
    manifest["count_total"] = total
    manifest["generated"] = FETCH_DATE
    manifest["counts_by_composer"] = dict(sorted(counts_by_composer.items(), key=lambda x: -x[1]))
    manifest["counts_by_form"] = dict(sorted(counts_by_form.items(), key=lambda x: -x[1]))
    manifest["composers"] = sorted(composers_list, key=lambda c: c["slug"])
    manifest.setdefault("pending", {})
    manifest["pending"]["untitled_composer"] = untitled_composer_count
    dump_json(MANIFEST_PATH, manifest)
    dump_json(COUNTS_PATH, {
        "generated": FETCH_DATE, "total_unique": total, "with_text": with_text,
        "multi_source": multi_source,
        "by_form": dict(sorted(counts_by_form.items(), key=lambda x: -x[1])),
        "by_composer": dict(sorted(counts_by_composer.items(), key=lambda x: -x[1])),
    })
    print(f"manifest rebuilt: {total} compositions, {len(composers_list)} composer files")


def cmd_merge_composers(args):
    from_d = load_composer(args.from_slug)
    into_d = load_composer(args.into_slug)
    canonical = args.canonical_name or into_d["composer"] or from_d["composer"]
    bio_notes = into_d.get("bio_notes") or from_d.get("bio_notes") or ""

    all_recs = list(from_d["items"]) + list(into_d["items"])
    for r in all_recs:
        r["composer"] = canonical
        r.setdefault("also_at", [])
        r["tags"] = [t for t in r.get("tags", []) if not t.startswith("composer:")]
        r["tags"].append(f"composer:{canonical}")

    merged, dup_count = dedupe(all_recs)
    merged.sort(key=lambda r: (r["title"].get("kn") or r["title"].get("latin") or ""))

    dump_json(comp_path(args.into_slug), composer_payload(canonical, merged, bio_notes))
    os.remove(comp_path(args.from_slug))
    os.rmdir(os.path.dirname(comp_path(args.from_slug)))
    print(f"merged '{args.from_slug}' ({len(from_d['items'])}) into "
          f"'{args.into_slug}' ({len(into_d['items'])}) as '{canonical}': "
          f"{len(merged)} unique compositions ({dup_count} duplicates collapsed). "
          f"Deleted {args.from_slug}/data.json.")
    rebuild_manifest()


def _find_record(composer_slug, comp_id):
    d = load_composer(composer_slug)
    for i, r in enumerate(d["items"]):
        if r["id"] == comp_id:
            return d, i
    raise SystemExit(f"no composition with id '{comp_id}' in {composer_slug}/data.json "
                      f"-- run the 'find' subcommand to look up the right id")


def cmd_relabel(args):
    d, idx = _find_record(args.composer, args.id)
    rec = d["items"][idx]
    changed = []

    if args.form:
        rec["form"] = args.form
        rec["tags"] = [t for t in rec.get("tags", []) if not t.startswith("form:")]
        rec["tags"].append(f"form:{args.form}")
        changed.append(f"form -> {args.form}")

    if args.move_to and args.move_to != args.composer:
        del d["items"][idx]
        d["count"] = len(d["items"])
        dump_json(comp_path(args.composer), d)

        target_path = comp_path(args.move_to)
        if os.path.exists(target_path):
            target = load_json(target_path)
        else:
            target = composer_payload(args.new_composer_name or "", [])
        canonical = args.new_composer_name or target["composer"] or rec.get("composer", "")
        rec["composer"] = canonical
        rec["tags"] = [t for t in rec.get("tags", []) if not t.startswith("composer:")]
        rec["tags"].append(f"composer:{canonical}")
        target["composer"] = canonical
        target["default_author"] = canonical
        target["items"].append(rec)
        target["count"] = len(target["items"])
        dump_json(target_path, target)
        changed.append(f"moved from {args.composer}/data.json to {args.move_to}/data.json "
                        f"(composer set to '{canonical}')")
    elif changed:
        dump_json(comp_path(args.composer), d)

    if not changed:
        print("nothing to do -- pass --form and/or --move-to")
        return
    print(f"{args.id}: " + "; ".join(changed))
    rebuild_manifest()


def cmd_find(args):
    d = load_composer(args.composer)
    needle = (args.title_contains or "").strip()
    hits = 0
    for r in d["items"]:
        title = (r["title"].get("kn", "") + " " + r["title"].get("latin", ""))
        if not needle or needle in title:
            print(f"{r['id']}  [{r['form']}]  {r['title'].get('kn') or r['title'].get('latin')}")
            hits += 1
    print(f"\n{hits} composition(s) in {args.composer}/data.json"
          + (f" matching '{needle}'" if needle else ""))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("merge-composers", help="fold one composer's file into another's")
    p.add_argument("--from", dest="from_slug", required=True, help="composer slug to merge FROM (deleted after)")
    p.add_argument("--into", dest="into_slug", required=True, help="composer slug to merge INTO (kept, overwritten)")
    p.add_argument("--canonical-name", default=None, help="composer name to use for the merged set (default: --into's existing name)")
    p.set_defaults(func=cmd_merge_composers)

    p = sub.add_parser("relabel", help="change one composition's form and/or which composer it belongs to")
    p.add_argument("--composer", required=True, help="composer slug the composition currently lives under")
    p.add_argument("--id", required=True, help="the composition's id (see the 'find' subcommand)")
    p.add_argument("--form", default=None, help="new form, e.g. suladi/mundige/dandaka/pada")
    p.add_argument("--move-to", default=None, help="composer slug to move this composition to")
    p.add_argument("--new-composer-name", default=None, help="composer display name if --move-to creates a brand-new composer file")
    p.set_defaults(func=cmd_relabel)

    p = sub.add_parser("find", help="list a composer's compositions (with ids) to find the one you want")
    p.add_argument("--composer", required=True)
    p.add_argument("--title-contains", default=None, help="filter by a substring of the title (Kannada or Latin)")
    p.set_defaults(func=cmd_find)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
