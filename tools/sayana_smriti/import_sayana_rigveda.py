#!/usr/bin/env python3
"""
import_sayana_rigveda.py — pull Sāyaṇa's Ṛgveda-bhāṣya (as rendered in H. H.
Wilson's 1866 edition) from wisdomlib.org and merge it into DGE's existing
Rigveda Samhita data files as a new commentary layer.

WHAT IT ADDS (per mantra, additive only — nothing existing is overwritten):

    items[i].commentaries.sayana   Sāyaṇa's gloss, English
    items[i].commentaries.wilson   Wilson's translation of the mantra

Both slot straight into the `commentaries` dict the app already renders
(see dgeNormalizeGranthaData() in dge/js/core.js) — no schema change, no
UI change required. Optional label polish: patches/core-js-labels.md.

WHY THERE IS NO CRAWLER
-----------------------
wisdomlib's doc IDs for this book are perfectly contiguous: one page per
maṇḍala, one per sūkta, one per mantra, in order. `rigveda_docmap.json`
was generated from DGE's own sūkta/mantra counts and VERIFIED against eight
independently-observed book-page IDs and three mantra anchors
(1.1.1=828866, 1.164.1=830744, 10.191.1=840450) — all exact. So we address
all 10,552 pages directly and skip ~700 index fetches.

The map is still checked at run time: every fetched page's own title must
report the maṇḍala.sūkta.ṛk we asked for, and its Devanagari must match the
mantra already in DGE. Either check failing by more than --max-drift aborts
the run rather than writing misaligned commentary.

USAGE
    pip install -r requirements.txt
    python import_sayana_rigveda.py --dge-root ../bhumandala/dge            # all 10 maṇḍalas
    python import_sayana_rigveda.py --dge-root ../bhumandala/dge --mandala 1 --limit 20
    python import_sayana_rigveda.py --dge-root ../bhumandala/dge --dry-run  # dump only, no merge

LICENCE POSITION
    Sāyaṇa (14th c.) and Wilson's translation (1850–66) are both public
    domain. wisdomlib.org is the digitiser; the importer records
    attribution in each data file's `commentary_sources` block and the app
    should keep a visible credit, as it does for ashtadhyayi.com.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

from common import Fetcher, append_jsonl, clean, load_json, save_json
from wisdomlib import parse_page, parse_reference, split_sanskrit_block

BOOK = "https://www.wisdomlib.org/hinduism/book/rig-veda-english-translation/d/doc{doc}.html"
SAMHITA = "data/vedas/rigveda/shakala_shakha/samhita/mandala_{m:02d}"

ATTRIBUTION = {
    "sayana": {
        "commentator": "Sāyaṇācārya",
        "work": "Ṛgveda-bhāṣya",
        "language": "en",
        "via": "H. H. Wilson, Rig-Veda Sanhita (1850–66), as digitised by wisdomlib.org",
        "licence": "Public domain (Sāyaṇa 14th c.; Wilson d. 1860). "
                   "Digitisation by wisdomlib.org — keep visible attribution. "
                   "Non-commercial educational use.",
    },
    "wilson": {
        "commentator": "H. H. Wilson",
        "work": "Rig-Veda Sanhita, English translation",
        "language": "en",
        "via": "wisdomlib.org",
        "licence": "Public domain (1850–66).",
    },
}

_PUNCT = re.compile(r"[\s।॥\.\|,;:'\"()\[\]–—-]+")


def norm_deva(s: str) -> str:
    """Compare-only normalisation: strip whitespace, daṇḍas and punctuation so
    an accent-mark or spacing difference doesn't read as a misalignment."""
    return _PUNCT.sub("", s or "")


def strip_accents_deva(s: str) -> str:
    return re.sub(r"[॒॑᳐-᳿꣠-ꣿ]", "", s or "")


def extract(html: str) -> dict:
    p = parse_page(html)
    sec = p["sections"]
    accented, plain, iast = split_sanskrit_block(sec.get("sanskrit", ""))
    return {
        "title": p["title"],
        "ref": parse_reference(p["title"]),
        "sayana": clean(sec.get("sayana", "")),
        "wilson": clean(sec.get("translation", "")),
        "sanskrit_accented": accented,
        "sanskrit_plain": plain,
        "iast": iast,
        "padapatha": clean(sec.get("padapatha", "")),
        "details": clean(sec.get("details", "")),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dge-root", required=True,
                    help="path to the repo's dge/ directory")
    ap.add_argument("--docmap", default=str(Path(__file__).parent / "rigveda_docmap.json"))
    ap.add_argument("--out-dir", default="dump",
                    help="where the standalone dump is written")
    ap.add_argument("--cache-dir", default=".httpcache")
    ap.add_argument("--mandala", type=int, action="append",
                    help="restrict to these maṇḍalas (repeatable)")
    ap.add_argument("--limit", type=int, default=0, help="stop after N mantras (smoke test)")
    ap.add_argument("--ids", action="append",
                    help="restrict to specific mantra ids, e.g. --ids 1.164.1 (repeatable)")
    ap.add_argument("--delay", type=float, default=1.2)
    ap.add_argument("--max-drift", type=float, default=0.02,
                    help="abort if more than this fraction of pages misalign")
    ap.add_argument("--dry-run", action="store_true", help="write the dump but do not touch data.json")
    ap.add_argument("--offline", action="store_true", help="cache only; never hit the network")
    ap.add_argument("--overwrite", action="store_true",
                    help="replace an existing commentaries.sayana instead of skipping it")
    args = ap.parse_args()

    dge = Path(args.dge_root)
    if not (dge / "data" / "schemas.json").exists():
        print(f"!! {dge} does not look like the dge/ directory", file=sys.stderr)
        return 2

    docmap = load_json(args.docmap)
    ids = docmap["doc_ids"]
    fetcher = Fetcher(cache_dir=args.cache_dir, delay=args.delay, offline=args.offline)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    dump_path = out / "sayana_rigveda.jsonl"
    if dump_path.exists():
        dump_path.unlink()

    only_ids = set(args.ids or [])
    if only_ids and not args.mandala:
        args.mandala = sorted({int(i.split(".")[0]) for i in only_ids})
    mandalas = sorted(set(args.mandala)) if args.mandala else list(range(1, 11))
    totals = {"pages": 0, "sayana": 0, "wilson": 0, "drift": 0, "missing": 0}
    drift_examples = []
    started = time.time()

    for m in mandalas:
        folder = dge / SAMHITA.format(m=m)
        data_path = folder / "data.json"
        if not data_path.exists():
            print(f"!! no data.json at {data_path}; skipping maṇḍala {m}", file=sys.stderr)
            continue
        data = load_json(data_path)
        items = data.get("items", [])
        by_id = {it["id"]: it for it in items}
        added = 0
        print(f"\n== Maṇḍala {m}: {len(items)} mantras")

        for it in items:
            if args.limit and totals["pages"] >= args.limit:
                break
            rid = it["id"]
            if only_ids and rid not in only_ids:
                continue
            doc = ids.get(rid)
            if doc is None:
                totals["missing"] += 1
                continue
            html = fetcher.get(BOOK.format(doc=doc), allow_missing=True)
            totals["pages"] += 1
            if not html:
                totals["missing"] += 1
                continue
            rec = extract(html)

            # --- alignment guards -------------------------------------------
            ok_title = rec["ref"] == ("rv", *[int(x) for x in rid.split(".")])
            local = strip_accents_deva(it.get("samhita_patha_plain") or it.get("samhita_patha", ""))
            fetched = strip_accents_deva(rec["sanskrit_plain"])
            ok_text = (not local or not fetched
                       or norm_deva(local)[:40] == norm_deva(fetched)[:40])
            if not (ok_title and ok_text):
                totals["drift"] += 1
                if len(drift_examples) < 10:
                    drift_examples.append(
                        {"id": rid, "doc": doc, "page_title": rec["title"],
                         "local": local[:60], "fetched": rec["sanskrit_plain"][:60]})
                continue

            row = {"id": rid, "mandala": m, "doc_id": doc,
                   "url": BOOK.format(doc=doc),
                   "sayana": rec["sayana"], "wilson": rec["wilson"],
                   "sanskrit_plain": rec["sanskrit_plain"], "iast": rec["iast"]}
            append_jsonl(dump_path, [row])

            comm = by_id[rid].setdefault("commentaries", {})
            if rec["sayana"] and (args.overwrite or not comm.get("sayana")):
                comm["sayana"] = rec["sayana"]
                totals["sayana"] += 1
                added += 1
            if rec["wilson"] and (args.overwrite or not comm.get("wilson")):
                comm["wilson"] = rec["wilson"]
                totals["wilson"] += 1

            if totals["pages"] % 250 == 0:
                el = time.time() - started
                print(f"   {totals['pages']} pages · {totals['sayana']} Sāyaṇa · "
                      f"{totals['drift']} drift · {el/60:.1f} min "
                      f"(cache hit {fetcher.stats['hit']})")

        if totals["pages"] and totals["drift"] / max(totals["pages"], 1) > args.max_drift:
            print("\n!! ALIGNMENT DRIFT EXCEEDED — aborting before writing.",
                  file=sys.stderr)
            print(json.dumps(drift_examples, ensure_ascii=False, indent=2), file=sys.stderr)
            return 3

        if added and not args.dry_run:
            data.setdefault("commentary_sources", {}).update(ATTRIBUTION)
            save_json(data_path, data)
            print(f"   -> wrote {data_path} (+{added} Sāyaṇa)")
        elif args.dry_run:
            print(f"   -> dry run: {added} Sāyaṇa entries NOT written")

    counts = {
        "generated_from": "wisdomlib.org/hinduism/book/rig-veda-english-translation",
        "mantras_expected": docmap["mantra_count"],
        "pages_fetched": totals["pages"],
        "sayana_added": totals["sayana"],
        "wilson_added": totals["wilson"],
        "misaligned_skipped": totals["drift"],
        "missing_pages": totals["missing"],
        "drift_examples": drift_examples,
        "http": fetcher.stats,
        "elapsed_min": round((time.time() - started) / 60, 1),
    }
    save_json(out / "COUNTS_sayana.json", counts, indent=2)
    print("\n" + json.dumps(counts, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
