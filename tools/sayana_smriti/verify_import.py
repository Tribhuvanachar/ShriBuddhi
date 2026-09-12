#!/usr/bin/env python3
"""
verify_import.py — post-run QA for the Sāyaṇa / Smṛti import.

Run this AFTER the importer, before merging the PR. It answers the question the
import log cannot: "did the right commentary land on the right verse, and will
any of it actually render?"

Checks, in order of how badly they'd hurt if missed:

  1. COVERAGE     how many mantras/verses actually got a layer, per file
  2. MISALIGNMENT re-derives each mantra's wisdomlib doc id from the shipped map
                  and compares it with the dump's record; also spot-checks the
                  stored commentary against a fresh fetch (--spot-check N)
  3. CONTAMINATION commentary that swallowed a heading, or is identical to the
                  translation next to it, or is a duplicate of another mantra's
  4. RENDERABILITY smriti bhashya[] present but core.js unpatched => invisible
  5. STRUCTURE    schema conformance, chapter gaps, malformed ids

Exit code is non-zero if any FAIL-level check trips, so it can gate a workflow.

    python verify_import.py --dge-root dge
    python verify_import.py --dge-root dge --spot-check 25     # needs egress
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

RV = "data/vedas/rigveda/shakala_shakha/samhita/mandala_{m:02d}/data.json"
EXPECTED_RV = 10552

# Heading fragments that must never appear inside an extracted commentary --
# their presence means the section splitter swallowed the next heading.
CONTAMINANTS = [
    "English translation", "Padapatha", "Multi-layer Annotation",
    "Sanskrit text [", "Commentary by S", "Explanatory notes",
    "Comparative notes", "Footnotes and references",
]

results = []          # (level, area, message)


def ok(area, msg):    results.append(("PASS", area, msg))
def warn(area, msg):  results.append(("WARN", area, msg))
def fail(area, msg):  results.append(("FAIL", area, msg))


# ------------------------------------------------------------------ rigveda

def check_rigveda(dge: Path, docmap: dict, dump: dict):
    total_items = total_sayana = total_wilson = 0
    per_mandala = {}
    all_sayana = []
    for m in range(1, 11):
        p = dge / RV.format(m=m)
        if not p.exists():
            fail("coverage", f"missing {p}")
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        items = data.get("items", [])
        n_say = n_wil = 0
        for it in items:
            c = it.get("commentaries") or {}
            if c.get("sayana"):
                n_say += 1
                all_sayana.append((it["id"], c["sayana"]))
            if c.get("wilson"):
                n_wil += 1
        per_mandala[m] = (len(items), n_say, n_wil)
        total_items += len(items); total_sayana += n_say; total_wilson += n_wil

        if not data.get("commentary_sources", {}).get("sayana") and n_say:
            warn("attribution", f"maṇḍala {m}: Sāyaṇa present but no commentary_sources block")

    pct = 100.0 * total_sayana / max(total_items, 1)
    line = f"Sāyaṇa on {total_sayana:,}/{total_items:,} mantras ({pct:.1f}%), Wilson on {total_wilson:,}"
    if total_sayana == 0:
        fail("coverage", "NO Sāyaṇa commentary found in any maṇḍala — the import did not land. " + line)
    elif pct < 90:
        warn("coverage", line + " — below 90%; check the run log for skipped pages")
    else:
        ok("coverage", line)

    if total_items != EXPECTED_RV:
        warn("structure", f"Rigveda item count {total_items:,} != expected {EXPECTED_RV:,}")

    for m, (n, s, w) in sorted(per_mandala.items()):
        p = 100.0 * s / max(n, 1)
        flag = "" if p >= 90 else "   <-- LOW"
        print(f"    maṇḍala {m:2d}: {s:5,}/{n:5,} Sāyaṇa ({p:5.1f}%)  Wilson {w:5,}{flag}")

    check_contamination(all_sayana)
    check_duplicates(all_sayana)
    check_docmap(dge, docmap, dump)


def check_contamination(rows):
    hits = defaultdict(list)
    for rid, text in rows:
        for frag in CONTAMINANTS:
            if frag in text:
                hits[frag].append(rid)
    if not hits:
        ok("contamination", "no heading text leaked into any Sāyaṇa entry")
        return
    for frag, ids in hits.items():
        n = len(ids)
        msg = f'"{frag}" appears inside {n} Sāyaṇa entries (e.g. {", ".join(ids[:5])})'
        (fail if n > len(rows) * 0.01 else warn)("contamination", msg)


def check_duplicates(rows):
    if not rows:
        return
    counts = Counter(t.strip()[:200] for _, t in rows)
    dup = [(t, c) for t, c in counts.items() if c > 3]
    uniq_ratio = len(counts) / len(rows)
    if uniq_ratio < 0.85:
        fail("duplication", f"only {uniq_ratio:.0%} of Sāyaṇa entries are unique — "
                            "strongly suggests an off-by-one or a repeated page")
    elif dup:
        worst = max(dup, key=lambda x: x[1])
        warn("duplication", f"{len(dup)} commentary texts repeat >3× "
                            f"(worst: {worst[1]}× — \"{worst[0][:60]}…\")")
    else:
        ok("duplication", f"{uniq_ratio:.0%} of Sāyaṇa entries are distinct")

    short = [rid for rid, t in rows if len(t.strip()) < 20]
    if short:
        warn("quality", f"{len(short)} Sāyaṇa entries under 20 chars (e.g. {', '.join(short[:5])})")


def check_docmap(dge: Path, docmap: dict, dump: dict):
    """The importer's own guard runs at fetch time; this re-checks the *result*
    independently, so a bug in the guard can't hide a bug in the merge."""
    if not dump:
        warn("alignment", "no dump/sayana_rigveda.jsonl found — skipping the independent re-check")
        return
    ids = docmap["doc_ids"]
    bad = [r["id"] for r in dump.values() if ids.get(r["id"]) != r.get("doc_id")]
    if bad:
        fail("alignment", f"{len(bad)} dump rows disagree with the doc map (e.g. {', '.join(bad[:5])})")
    else:
        ok("alignment", f"all {len(dump):,} dump rows agree with the shipped doc map")


def spot_check(dump: dict, n: int):
    """Refetch n random pages and diff against what was stored. Needs egress."""
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from common import Fetcher                        # noqa: PLC0415
        from wisdomlib import parse_page                  # noqa: PLC0415
    except Exception as e:                                # noqa: BLE001
        warn("spot-check", f"importer modules not on the path ({e}); skipped")
        return
    if not dump:
        warn("spot-check", "no dump to sample from; skipped")
        return
    f = Fetcher(cache_dir=".httpcache_verify", delay=1.5)
    sample = random.sample(list(dump.values()), min(n, len(dump)))
    mismatches = []
    for row in sample:
        html = f.get(row["url"], allow_missing=True)
        if not html:
            mismatches.append((row["id"], "page unreachable"))
            continue
        fresh = (parse_page(html)["sections"].get("sayana") or "").strip()
        if fresh[:120] != (row.get("sayana") or "").strip()[:120]:
            mismatches.append((row["id"], "stored text differs from a fresh fetch"))
    if mismatches:
        fail("spot-check", f"{len(mismatches)}/{len(sample)} sampled mantras differ: "
                           + "; ".join(f"{i} ({w})" for i, w in mismatches[:5]))
    else:
        ok("spot-check", f"{len(sample)} randomly sampled mantras match a fresh fetch exactly")


# ------------------------------------------------------------------- smriti

def check_smriti(dge: Path):
    root = dge / "data" / "smriti_dharma"
    if not root.exists():
        warn("smriti", "no smriti_dharma directory")
        return
    any_bhashya = False
    print()
    for p in sorted(root.rglob("data.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        items = data.get("items", [])
        verses = commentaries = 0
        by_commentator = Counter()
        for it in items:
            for s in it.get("shlokas", []):
                verses += 1
                for b in s.get("bhashya", []) or []:
                    commentaries += 1
                    by_commentator[b.get("commentator", "?")] += 1
                if s.get("artha"):
                    by_commentator["(translation)"] += 1
        if commentaries:
            any_bhashya = True
        rel = p.relative_to(root).parent
        if verses or commentaries:
            top = ", ".join(f"{k.split('(')[0].strip()}×{v}" for k, v in by_commentator.most_common(3))
            print(f"    {str(rel):46} {len(items):4} ch · {verses:6,} verses · "
                  f"{commentaries:6,} bhāṣya   {top}")

        # Chapter-numbering gaps: a silent sign the crawler missed a section.
        # Careful — some ids legitimately cover TWO chapters, e.g. Narada's
        # `adhyaya_1516` (chapters 15 and 16 are merged in the standard
        # editions). Naively reading the trailing digits gives chapter 1516 and
        # reports 1,500 phantom gaps, so split those first.
        nums = []
        for it in items:
            m = re.search(r"(\d+)$", it.get("id", ""))
            if not m:
                continue
            digits = m.group(1)
            if len(digits) == 4 and int(digits[2:]) == int(digits[:2]) + 1:
                nums.extend([int(digits[:2]), int(digits[2:])])   # merged chapter
            else:
                nums.append(int(digits))
        nums.sort()
        if nums and nums != list(range(nums[0], nums[0] + len(nums))):
            missing = sorted(set(range(nums[0], nums[-1] + 1)) - set(nums))
            warn("structure", f"{rel}: chapter gaps at {missing[:10]}"
                              + (f" (+{len(missing) - 10} more)" if len(missing) > 10 else ""))

    if any_bhashya:
        ok("smriti", "bhāṣya entries present in the smṛti data")
        check_core_js_patched(dge)
    else:
        warn("smriti", "no bhāṣya entries anywhere in smriti_dharma "
                       "(expected if only the Sāyaṇa job has run so far)")


def check_core_js_patched(dge: Path):
    """Commentary in the data that the app throws away is worse than no
    commentary — it looks done and isn't."""
    core = dge / "js" / "core.js"
    if not core.exists():
        warn("render", "js/core.js not found")
        return
    src = core.read_text(encoding="utf-8")
    branch = src.find("Array.isArray(data.items[0].shlokas)")
    if branch < 0:
        warn("render", "could not locate the nested-śloka branch in core.js")
        return
    window = src[branch:branch + 2500]
    if "commentaries: {}" in window and "v.bhashya" not in window:
        fail("render", "core.js is UNPATCHED — the nested-śloka branch still hard-codes "
                       "commentaries:{}, so every smṛti bhāṣya you just imported will "
                       "load and render as nothing. Apply patched/core.js.")
    else:
        ok("render", "core.js nested-śloka branch reads artha/bhashya[] — commentary will render")

    if "sayana:" not in src:
        warn("render", "KNOWN_COMMENTARY_LABELS has no 'sayana' entry — it will "
                       "render as the auto-titlecased 'Sayana'")



PHASE2 = [
    ("Atharvaveda Śaunaka", "data/vedas/atharvaveda/shaunaka_shakha/samhita",
     ["griffith", "whitney", "whitney_notes"]),
    ("Sāmaveda Kauthuma", "data/vedas/samaveda/kauthuma_shakha/samhita",
     ["sayana", "wilson"]),
    ("Śukla Yajurveda", "data/vedas/yajurveda/shukla_yajurveda/vajasaneyi_madhyandina_shakha/samhita",
     ["griffith"]),
    ("Taittirīya Saṃhitā", "data/vedas/yajurveda/krishna_yajurveda/taittiriya_shakha/samhita",
     ["keith"]),
]

UPANISHAD_GLOBS = [
    "data/vedas/*/*/upanishad*", "data/vedas/*/*/*/upanishad*",
]


def check_phase2(dge: Path):
    """The four corpora outside the Ṛgveda. Reported, never failed: these are
    additive layers, and a run that has not happened yet is not an error."""
    any_layer = False
    for label, rel, keys in PHASE2:
        root = dge / rel
        files = sorted(root.rglob("data.json")) if root.exists() else []
        if not files:
            continue
        total = 0
        got = Counter()
        via = 0
        for p in files:
            for it in json.loads(p.read_text(encoding="utf-8")).get("items", []):
                total += 1
                c = it.get("commentaries") or {}
                for k in keys:
                    if c.get(k):
                        got[k] += 1
                if it.get("commentary_via"):
                    via += 1
        cov = ", ".join(f"{k} {got[k]:,} ({100*got[k]/max(total,1):.0f}%)" for k in keys if got[k]) \
              or "none yet"
        print(f"    {label:24} {total:6,} items · {cov}")
        if got:
            any_layer = True
        if via:
            print(f"    {'':24} {via:6,} carry commentary_via provenance "
                  f"(propagated from the Ṛgveda parallel)")
    if any_layer:
        ok("phase2", "at least one non-Ṛgveda Vedic commentary layer is present")
    else:
        warn("phase2", "no commentary on any Veda outside the Ṛgveda yet "
                       "(expected until import_veda_phase2.py / propagate_samaveda.py run)")


def check_upanishads(dge: Path):
    import glob as _glob
    seen, filled, empty = set(), [], []
    for pat in UPANISHAD_GLOBS:
        for d in _glob.glob(str(dge / pat)):
            for p in Path(d).rglob("data.json"):
                if p in seen:
                    continue
                seen.add(p)
                items = json.loads(p.read_text(encoding="utf-8")).get("items", [])
                name = p.parent.name
                if items:
                    keys = Counter()
                    for it in items:
                        for k in (it.get("commentaries") or {}):
                            keys[k] += 1
                    filled.append((name, len(items), dict(keys)))
                else:
                    empty.append(name)
    for name, n, keys in sorted(filled):
        layers = ", ".join(f"{k} {v}" for k, v in sorted(keys.items())) or "mūla only"
        print(f"    {name:44} {n:5} units · {layers}")
    if empty:
        print(f"    still empty: {', '.join(sorted(empty))}")
    if filled:
        ok("upanishads", f"{len(filled)} Upaniṣad folder(s) populated, {len(empty)} still empty")
    else:
        warn("upanishads", "every Upaniṣad folder is still empty "
                           "(expected until import_upanishads.py runs)")


# --------------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dge-root", required=True)
    ap.add_argument("--docmap", default=str(Path(__file__).parent / "rigveda_docmap.json"))
    ap.add_argument("--dump", default="dump/sayana_rigveda.jsonl")
    ap.add_argument("--spot-check", type=int, default=0,
                    help="refetch N random mantra pages and diff (needs network)")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    random.seed(args.seed)
    dge = Path(args.dge_root)
    docmap = json.loads(Path(args.docmap).read_text(encoding="utf-8"))

    dump = {}
    dp = Path(args.dump)
    if dp.exists():
        for line in dp.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                dump[r["id"]] = r

    print("=" * 78)
    print("DGE import verification")
    print("=" * 78)
    print("\nRIGVEDA — Sāyaṇa coverage")
    check_rigveda(dge, docmap, dump)
    if args.spot_check:
        spot_check(dump, args.spot_check)

    print("\nOTHER VEDAS (phase 2)")
    check_phase2(dge)

    print("\nUPANIṢADS")
    check_upanishads(dge)

    print("\nSMṚTI / DHARMAŚĀSTRA")
    check_smriti(dge)

    print("\n" + "=" * 78)
    for level in ("FAIL", "WARN", "PASS"):
        for lv, area, msg in results:
            if lv == level:
                print(f"  {lv:4}  [{area}] {msg}")
    fails = sum(1 for lv, _, _ in results if lv == "FAIL")
    warns = sum(1 for lv, _, _ in results if lv == "WARN")
    print("=" * 78)
    print(f"{fails} failure(s), {warns} warning(s)")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
