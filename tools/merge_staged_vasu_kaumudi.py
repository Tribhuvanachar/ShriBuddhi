#!/usr/bin/env python3
"""
merge_staged_vasu_kaumudi.py — Stage 2 of the Vasu Siddhānta-Kaumudī
pipeline: reads Stage-1 staged files (tools/vasu_kaumudi_ocr.py) and
merges their entries into the Ashtadhyayi reader's vasu_kaumudi layer,
dge/data/vedanga/vyakarana/ashtadhyayi/vasu_kaumudi/data.json.

Keying: an entry's "sk" (Vasu's serial number) -> kaumudiIndex ->
Ashtadhyayi sutra id via kaumudi_order/data.json. The layer's items use
the same shape as the existing vasu (1891) layer: the English text lives
in sanskrit_text, language "en". The corpus's own sutra text is
authoritative; the staged sutra_ocr is audit trail only and is NOT
merged.

Classification gate (same contract as merge_staged_commentary.py):
"accept" always merges; "review"/"unresolved" only with the
corresponding --include-* flag. Entries with partial="head"/"tail"
(cut by a batch boundary) merge only when the OTHER half is also
present in the inputs (the two halves are joined) or --include-partial
is given; otherwise they are reported and skipped. Duplicate sk across
staged files (the 1-page dispatch overlap): the more complete /
better-classified copy wins; ties -> the longer english text.

Usage:
  python3 tools/merge_staged_vasu_kaumudi.py --staged a.json b.json ... [--include-review]
  python3 tools/merge_staged_vasu_kaumudi.py --staged-dir dge/data/ocr_staging/vasu_siddhanta_kaumudi
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

LAYER = Path("dge/data/vedanga/vyakarana/ashtadhyayi/vasu_kaumudi/data.json")
ORDER = Path("dge/data/vedanga/vyakarana/ashtadhyayi/kaumudi_order/data.json")
SUTRAPATHA = Path("dge/data/vedanga/vyakarana/ashtadhyayi/sutrapatha/data.json")

HEADER = {
    "schema": "grantha_tika_text",
    "default_author": "Śrīśa Chandra Vasu",
    "title": "Vasu — Siddhānta-Kaumudī English translation",
    "title_devanagari": "Vasu SK (Eng.)",
    "language": "en",
    "source": "S.C. Vasu, The Siddhānta Kaumudī of Bhaṭṭoji Dīkṣita, English "
              "translation (Pāṇini Office, 4 volumes, 1905-07) — public domain. "
              "Scan: archive.org/details/Siddhanta_Kaumudi_English_Translation-SC_Vasu. "
              "Digitised for DGE via Vision OCR + Gemini proofreading "
              "(tools/vasu_kaumudi_ocr.py), classification-gated per entry.",
    "licence": "public domain (Vasu 1905-07); OCR digitisation this project's own",
}

CLASS_RANK = {"accept": 2, "review": 1, "unresolved": 0}


def load_entries(paths: list[Path]) -> list[dict]:
    out = []
    for p in paths:
        doc = json.loads(p.read_text(encoding="utf-8"))
        for e in doc.get("entries") or []:
            e["_from"] = p.name
            e["_volume"] = doc.get("volume", "")
            out.append(e)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--staged", nargs="*", default=[])
    ap.add_argument("--staged-dir")
    ap.add_argument("--include-review", action="store_true")
    ap.add_argument("--include-unresolved", action="store_true")
    ap.add_argument("--include-partial", action="store_true",
                    help="merge head/tail fragments even when the other half is absent")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    paths = [Path(p) for p in args.staged]
    if args.staged_dir:
        paths += sorted(Path(args.staged_dir).glob("*.json"))
    if not paths:
        print("error: no staged files given", file=sys.stderr)
        return 1

    order = json.loads(ORDER.read_text(encoding="utf-8"))
    sk_to_id = {it["kaumudiIndex"]: it["id"] for it in order["items"]}
    valid_ids = {it["id"] for it in order["items"]}
    sutra_text = {}
    if SUTRAPATHA.exists():
        sp = json.loads(SUTRAPATHA.read_text(encoding="utf-8"))
        for it in sp.get("items", []):
            sutra_text[it["id"]] = it.get("sanskrit_text", "")

    import difflib
    import re as _re

    def deva(s: str) -> str:
        return "".join(_re.findall(r"[ऀ-ॿ]+", s or ""))

    def sim(ocr: str, sid: str) -> float:
        ref = deva(sutra_text.get(sid, ""))
        got = deva(ocr)
        if not ref or not got:
            return 0.0
        return difflib.SequenceMatcher(None, got, ref).ratio()

    raw = load_entries(paths)

    # join head+tail halves of one sk split across two staged batches
    by_sk: dict[int, list[dict]] = {}
    for e in raw:
        sk = e.get("sk")
        if not isinstance(sk, int) or sk <= 0:
            continue
        by_sk.setdefault(sk, []).append(e)

    merged: dict[int, dict] = {}
    skipped = {"partial": [], "gated": [], "unmapped": []}
    for sk, copies in sorted(by_sk.items()):
        heads = [c for c in copies if c.get("partial") == "head"]
        tails = [c for c in copies if c.get("partial") == "tail"]
        wholes = [c for c in copies if not c.get("partial")]
        cand = None
        if wholes:
            cand = max(wholes, key=lambda c: (CLASS_RANK.get(c.get("classification"), 0),
                                              len(c.get("english") or "")))
        elif heads and tails:
            h = max(heads, key=lambda c: len(c.get("english") or ""))
            t = max(tails, key=lambda c: len(c.get("english") or ""))
            cand = dict(h)
            cand["english"] = (h.get("english") or "").rstrip() + "\n" + \
                              (t.get("english") or "").lstrip()
            worst = min((h, t), key=lambda c: CLASS_RANK.get(c.get("classification"), 0))
            cand["classification"] = worst.get("classification", "review")
            if CLASS_RANK.get(cand["classification"], 0) > 1:
                cand["classification"] = "review"
                cand["note"] = (cand.get("note") or "joined across a batch boundary")
        elif args.include_partial:
            cand = max(copies, key=lambda c: len(c.get("english") or ""))
        else:
            skipped["partial"].append(sk)
            continue

        cls = cand.get("classification", "unresolved")
        if cls == "review" and not args.include_review:
            skipped["gated"].append(sk)
            continue
        if cls == "unresolved" and not args.include_unresolved:
            skipped["gated"].append(sk)
            continue
        merged[sk] = cand

    if LAYER.exists():
        doc = json.loads(LAYER.read_text(encoding="utf-8"))
    else:
        doc = dict(HEADER, items=[])
    # sk_items is the canonical one-row-per-SK-entry store; items (what the
    # reader consumes) is DERIVED from it below, one row per sutra id with
    # same-id entries joined — so a re-merge never re-reads joined text.
    items_by_sk = {}
    for it in doc.get("sk_items", doc.get("items", [])):
        items_by_sk[it.get("sk_number")] = it

    added = updated = 0
    ref_disagreements = []
    for sk, e in merged.items():
        # Two independent claims about which sutra this entry translates:
        # the book's printed Panini ref (digits — mostly reliable, but a
        # degraded ८ can OCR as ६) and the kaumudi_order map (built from
        # a different SK edition, drifts locally: the book's S.2 is
        # 1.1.71 where the map says 1.1.70). When they disagree, the
        # corpus's own sutrapatha arbitrates: the entry's OCR'd sutra
        # line is compared against both candidates' authoritative text
        # and the closer one wins; a near-tie keeps the map and flags
        # the entry review.
        printed = (e.get("panini_ref") or "").strip()
        mapped = sk_to_id.get(sk)
        if printed and printed in valid_ids and mapped and mapped != printed:
            s_p, s_m = sim(e.get("sutra_ocr", ""), printed), sim(e.get("sutra_ocr", ""), mapped)
            if s_p >= s_m + 0.1:
                sid = printed
            elif s_m >= s_p + 0.1:
                sid = mapped
            else:
                sid = mapped
                e["classification"] = "review"
                e["note"] = ((e.get("note") or "") +
                             f" [ref ambiguous: printed {printed} ({s_p:.2f}) vs map {mapped} ({s_m:.2f})]").strip()
            ref_disagreements.append((sk, mapped, printed, sid, round(s_p, 2), round(s_m, 2)))
        elif printed and printed in valid_ids:
            sid = printed
        else:
            sid = mapped
        if sid is None:
            skipped["unmapped"].append(sk)
            continue
        item = {
            "id": sid,
            "reference": sid,
            "sk_number": sk,
            "sanskrit_text": (e.get("english") or "").strip(),
            "author": "Śrīśa Chandra Vasu",
            "tika_title": "Vasu SK (Eng.)",
            "language": "en",
            "tags": ["ashtadhyayi", "vasu_kaumudi"],
            "source": {"volume": e.get("_volume", ""), "page": e.get("page", 0),
                       "staged": e.get("_from", ""),
                       "classification": e.get("classification", "")},
        }
        if sk in items_by_sk:
            if items_by_sk[sk]["sanskrit_text"] != item["sanskrit_text"]:
                items_by_sk[sk].update(item)
                updated += 1
        else:
            items_by_sk[sk] = item
            added += 1

    # The reader indexes a layer's items by sutra id, last-one-wins
    # (ashtadhyayi.js L.byId[it.id]=it) — and distinct SK entries can
    # legitimately share one sutra (the SK treats e.g. हलन्त्यम् twice).
    # Emit ONE item per id, concatenating same-id entries in SK order.
    by_id: dict[str, list[dict]] = {}
    for k in sorted(items_by_sk):
        by_id.setdefault(items_by_sk[k]["id"], []).append(items_by_sk[k])
    out_items = []
    for sid in by_id:
        group = by_id[sid]
        if len(group) == 1:
            out_items.append(group[0])
            continue
        first = dict(group[0])
        first["sanskrit_text"] = "\n\n".join(
            f"[S. {g['sk_number']}]\n{g['sanskrit_text']}" for g in group)
        first["sk_numbers"] = [g["sk_number"] for g in group]
        out_items.append(first)
    out_items.sort(key=lambda it: it["sk_number"])
    doc["sk_items"] = [items_by_sk[k] for k in sorted(items_by_sk)]
    doc["items"] = out_items
    for k, v in HEADER.items():
        doc.setdefault(k, v)

    print(f"merge: {added} added, {updated} updated, layer now {len(doc['items'])} "
          f"of {len(sk_to_id)} mappable SK entries")
    if ref_disagreements:
        print(f"  printed-ref vs kaumudi_order disagreements ({len(ref_disagreements)}, sutrapatha-arbitrated):")
        for sk, m, p, chosen, s_p, s_m in ref_disagreements[:25]:
            print(f"    S.{sk}: map={m}({s_m}) printed={p}({s_p}) -> {chosen}")
    for k, v in skipped.items():
        if v:
            print(f"  skipped ({k}): {len(v)} -> {v[:15]}{' …' if len(v) > 15 else ''}")
    if args.dry_run:
        print("[dry-run] not written")
        return 0
    LAYER.parent.mkdir(parents=True, exist_ok=True)
    LAYER.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {LAYER}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
