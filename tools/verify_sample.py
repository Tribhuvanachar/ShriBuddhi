#!/usr/bin/env python3
"""verify_sample.py -- pick the units a human should actually look at.

The lead's rule, 21 Sep 2026: for every work, and for every chapter or
division inside it, check the FIRST unit, the LAST unit, and two at random in
between. Not two per book -- two per chapter. A book of forty sargas gets
about a hundred and sixty checks, and the ends of every one of them, because
that is where segmentation breaks: a chapter's first unit catches a heading
swallowed into the text, its last catches a colophon or the next chapter
bleeding in.

A "chapter" is whatever the work divides itself by, in this order of
preference: an explicit section/sarga/kanda/sandhi/adhyaya field, else the
leading component of a structured reference like "1.2.3", else the whole work
as a single division.

Deterministic: the same seed gives the same sample, so a re-run checks the
same units and a fix can be proved rather than asserted.

    python3 tools/verify_sample.py --work darshana/.../mula
    python3 tools/verify_sample.py --all --out admin/config/verify_plan.json
"""
import argparse, json, os, random, re, sys

DIVISION_FIELDS = ("sandhi_number", "sarga", "kanda", "adhyaya", "section",
                   "chapter", "canto", "skandha", "prashna", "valli", "pada")


def division_of(item, index):
    """Which chapter this unit belongs to, and how we decided."""
    for f in DIVISION_FIELDS:
        v = item.get(f)
        if v not in (None, "", []):
            return str(v), f
    ref = str(item.get("reference") or item.get("id") or "")
    m = re.match(r"^\s*([0-9]{1,3})[.\-:/]", ref)
    if m:
        return m.group(1), "reference-prefix"
    return "(whole work)", "none"


def sample_work(path, per_chapter_random=2, seed=20260921):
    with open(path, encoding="utf-8") as fh:
        items = (json.load(fh) or {}).get("items") or []
    if not items:
        return {"path": path, "units": 0, "divisions": 0, "picks": [],
                "note": "no items"}
    groups, how = {}, "none"
    for i, it in enumerate(items):
        d, how = division_of(it, i)
        groups.setdefault(d, []).append(i)

    rnd = random.Random("%s|%s" % (path, seed))
    picks = []
    for d, idxs in groups.items():
        idxs = sorted(idxs)
        chosen = {idxs[0]: "first", idxs[-1]: "last"}
        middle = [i for i in idxs[1:-1] if i not in chosen]
        for i in (rnd.sample(middle, min(per_chapter_random, len(middle)))
                  if middle else []):
            chosen[i] = "random"
        for i in sorted(chosen):
            it = items[i]
            picks.append({"division": d, "why": chosen[i], "index": i,
                          "id": it.get("id"),
                          "reference": it.get("reference") or it.get("unit_title") or ""})
    return {"path": path, "units": len(items), "divisions": len(groups),
            "divided_by": how, "picks": picks}


def find_works(root):
    out = []
    lib = os.path.join(root, "data", "library.json")
    if os.path.isfile(lib):
        with open(lib, encoding="utf-8") as fh:
            for g in (json.load(fh).get("granthas") or []):
                if g.get("populated") and g.get("path"):
                    out.append(g["path"])
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 2)[1])
    ap.add_argument("--root", default=".")
    ap.add_argument("--work", help="a grantha path under data/, or a data.json")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--random", type=int, default=2, help="how many between the ends")
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)

    targets = []
    if args.work:
        p = args.work
        if not p.endswith("data.json"):
            p = os.path.join(args.root, "data", p.lstrip("/"), "data.json")
        targets = [p]
    elif args.all:
        targets = [os.path.join(args.root, p) for p in find_works(args.root)]
    else:
        ap.error("give --work or --all")

    plans, units, picks, divs = [], 0, 0, 0
    for t in targets:
        if not os.path.isfile(t):
            continue
        pl = sample_work(t, args.random)
        plans.append(pl)
        units += pl["units"]; picks += len(pl["picks"]); divs += pl["divisions"]

    print("%d work(s), %s unit(s), %d division(s)" % (len(plans), f"{units:,}", divs))
    print("%s unit(s) to check -- %.1f%% of the corpus" % (f"{picks:,}", 100.0 * picks / max(units, 1)))
    if args.out:
        with open(os.path.join(args.root, args.out), "w", encoding="utf-8") as fh:
            json.dump({"_readme": [
                "Which units to check, by the rule: first, last and two at",
                "random in every chapter of every work. Deterministic -- the",
                "same seed picks the same units, so a fix can be proved.",
            ], "seed": 20260921, "works": plans}, fh, ensure_ascii=False, indent=1)
            fh.write("\n")
        print("wrote %s" % args.out)
    elif len(plans) == 1:
        for p in plans[0]["picks"][:24]:
            print("   %-14s %-8s %s" % (p["division"], p["why"], p["id"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
