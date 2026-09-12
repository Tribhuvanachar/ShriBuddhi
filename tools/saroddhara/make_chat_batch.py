#!/usr/bin/env python3
"""Stage D′ — build a compact verification batch for pasting into a Gemini *chat* (no API, phone-friendly).

    python3 tools/saroddhara/make_chat_batch.py --work <scratch dir> [--out dge/data/ocr_staging/bhagavata_saroddhara/verify_input/batch_01_critical.json] [--print 12]

Picks the critical items out of the staged Bhāgavata Sāroddhāra data — verses OCR never found (printed index
numbers with no verse), verses whose OCR disagrees with the DGE Madhva Bhāgavata text (mismatch), and verses
that only nearly match (mula_near) — and writes one JSON list. Each entry carries both OCR readings, the DGE
candidate, the PDF page and, for missing verses, the neighbouring verses plus the raw OCR lines between them.
--print N prints the file in chunks of N items (copy/paste into the chat); answers come back through
tools/saroddhara/apply_chat_answers.py."""
import argparse, json, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "saroddhara"))
from build_saroddhara import load_bhp, INDEX, dev_only   # noqa: E402
BASE = ROOT / "dge/data/bhagavata_saroddhara"
DEFAULT_OUT = ROOT / "dge/data/ocr_staging/bhagavata_saroddhara/verify_input/batch_01_critical.json"

ANSWER_FORMAT = {
    "_how_to_answer": "Reply with ONE JSON list, one object per id, nothing else. decision: 'dge' (the DGE Madhva text is what the print shows, modulo OCR noise) | 'printed' (the print genuinely differs — give the exact printed text in verified_text) | 'vision' (Vision OCR is right as it stands) | 'unsure'. For missing_verse give verified_text (full verse, no number), bhagavata_ref 's.a.v' and pdf_page. If a neighbouring verse's current_text is really this verse (the OCR merged two verses), also add an object for that neighbour's id (e.g. BS_V005) with its correct verified_text and bhagavata_ref. Keep note to one line.",
    "_answer_shape": {"id": "BS_V042", "decision": "dge|printed|vision|unsure", "verified_text": "… or null", "bhagavata_ref": "10.1.14 or null", "pdf_page": 128, "note": "…"},
}


def ref_str(r):
    if not r: return None
    if isinstance(r, dict): return f"{r['skandha']}.{r['adhyaya']}.{r['verse']}"
    return ".".join(str(x) for x in r)


def strip_num(t):
    return re.sub(r"\s*(?:॥|\|\||।।)\s*[०-९0-9]{1,3}\s*(?:॥|\|\||।।)?\s*$", "", t or "").strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--print", type=int, default=0, dest="chunk")
    a = ap.parse_args()
    W = Path(a.work)
    pages = {p["page"]: p for p in json.load(open(W / "merged/pages_merged.json", encoding="utf-8"))["pages"]}
    queue = {q["id"]: q for q in json.load(open(W / "verify_input/verify_queue.json", encoding="utf-8"))["items"]}
    mula = json.load(open(BASE / "mula/data.json", encoding="utf-8"))["items"]
    by_n = {it["verse_no"]: it for it in mula}
    bhp = load_bhp()
    items = []

    # 1. missing verses — printed-index numbers with no detected verse
    present = set(by_n)
    missing = [n for lo, hi in INDEX.values() for n in range(lo, hi + 1) if n not in present]
    for n in missing:
        prev = max((k for k in by_n if k < n), default=None); nxt = min((k for k in by_n if k > n), default=None)
        pk = next((p for p, (lo, hi) in INDEX.items() if lo <= n <= hi), None)
        p0 = by_n[prev]["source"].get("pdf_page") if prev else None; p1 = by_n[nxt]["source"].get("pdf_page") if nxt else None
        ctx = []
        used = {strip_num(by_n[k]["ocr"].get("vision", "")) for k in (prev, nxt) if k}
        for pg in range(p0 or p1 or 0, (p1 or p0 or 0) + 1):
            P = pages.get(pg)
            if not P: continue
            for ln in P["lines"]:
                if ln.get("region") in ("verse", "ref") or re.search(r"॥\s*[०-९]+\s*॥", ln.get("text", "")):
                    if strip_num(ln.get("text", "")) in used: continue
                    e = {"pdf_page": pg, "y": ln["y"], "region": ln.get("region"), "vision": ln.get("vision"), "tesseract": ln.get("tess")}
                    if ln.get("ref"): e["printed_ref"] = ref_str(ln["ref"]); e["ref_assigned_to_verse"] = ln.get("verse_no")
                    ctx.append(e)
            for o in P.get("vision_orphans", []): ctx.append({"pdf_page": pg, "region": "vision_orphan", "vision": o})
        cands = []
        for e in ctx:
            if e.get("printed_ref") and not e.get("ref_assigned_to_verse"):
                key = tuple(int(x) for x in e["printed_ref"].split("."))
                if key in bhp: cands.append({"ref": e["printed_ref"], "text": bhp[key]["text"]})
        items.append({"id": f"BS_V{n:03d}", "type": "missing_verse", "verse_num": n, "prakarana_no": pk,
                      "prakarana": by_n[nxt]["category"] if nxt else None,
                      "neighbours": {"prev": {"verse_num": prev, "pdf_page": p0, "bhagavata_ref": ref_str(by_n[prev].get("bhagavata_ref")), "current_text": by_n[prev]["sanskrit_text"]} if prev else None,
                                     "next": {"verse_num": nxt, "pdf_page": p1, "bhagavata_ref": ref_str(by_n[nxt].get("bhagavata_ref")), "current_text": by_n[nxt]["sanskrit_text"]} if nxt else None},
                      "pdf_page": [p0, p1], "book_ref": None, "ocr_vision": None, "ocr_tesseract": None,
                      "ocr_context": ctx[:14], "dge_mula_candidate": cands[:2] or None,
                      "issue": f"Printed index says prakaraṇa {pk} has verse {n}, but OCR structure found no verse between {prev} (p.{p0}) and {nxt} (p.{p1}). Find it in ocr_context (a verse line + its ref line '। s । a । v ।'), or say it is absent/misnumbered. Check whether prev/next current_text is actually verse {n}."})

    # 2. mismatches and near-matches against the DGE Madhva mūla
    for it in mula:
        st = it["verification"]["status"]
        if st not in ("mismatch", "mula_near"): continue
        q = queue.get(f"BS_V{it['verse_no']:03d}", {})
        key = tuple(it["verification"].get("dge_key") or [])
        items.append({"id": f"BS_V{it['verse_no']:03d}", "type": "mismatch" if st == "mismatch" else "near_match", "verse_num": it["verse_no"],
                      "prakarana": it["category"], "book_ref": ref_str(it.get("bhagavata_ref")), "pdf_page": it["source"].get("pdf_page"),
                      "ocr_vision": q.get("ocr_vision") or it["ocr"].get("vision"), "ocr_tesseract": q.get("ocr_tesseract"),
                      "dge_mula_candidate": bhp.get(key, {}).get("text") if key else None, "dge_similarity": it["verification"].get("dge_similarity"),
                      "current_text": it["sanskrit_text"],
                      "issue": (f"OCR and the DGE Madhva text for {ref_str(it.get('bhagavata_ref'))} differ substantially (similarity {it['verification'].get('dge_similarity')}). Is the printed verse really {ref_str(it.get('bhagavata_ref'))}, a different verse, or a variant reading? Give the exact printed text."
                                if st == "mismatch" else
                                f"Close but not identical to DGE {ref_str(it.get('bhagavata_ref'))} (similarity {it['verification'].get('dge_similarity')}) — OCR noise or a real variant reading (pāṭhabheda)? If a variant, give the exact printed text.")})
    order = {"missing_verse": 0, "mismatch": 1, "near_match": 2}
    items.sort(key=lambda x: (order[x["type"]], x["verse_num"]))
    out = {"_readme": "Bhāgavata Sāroddhāra — critical verification batch for a Gemini chat session. Sāroddhāra verse numbers follow the printed index; book_ref = printed Bhāgavata reference skandha.adhyaya.verse; dge_mula_candidate = Madhva Bhāgavata text already in DGE.",
           **ANSWER_FORMAT, "counts": {t: sum(1 for i in items if i["type"] == t) for t in order}, "items": items}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"wrote {Path(a.out).relative_to(ROOT)}: {out['counts']}", file=sys.stderr)
    if a.chunk:
        # chat rendering: same items minus fields the chat does not need (current_text duplicates ocr_vision,
        # y/region geometry); each chunk is also written next to the batch file for phone access via the raw URL
        def slim(it):
            it = {k: v for k, v in it.items() if k not in ("current_text", "dge_similarity")}
            if "ocr_context" in it:
                it["ocr_context"] = [{k: v for k, v in c.items() if k not in ("y", "region") and v is not None} for c in it["ocr_context"]]
            return it
        total = -(-len(items) // a.chunk)
        for i in range(0, len(items), a.chunk):
            k = i // a.chunk + 1
            chunk = {"_how_to_answer": ANSWER_FORMAT["_how_to_answer"], "_answer_shape": ANSWER_FORMAT["_answer_shape"],
                     "chunk": f"{k} of {total}", "items": [slim(x) for x in items[i:i + a.chunk]]}
            cp = Path(a.out).with_name(Path(a.out).stem + f"_chunk{k}.json")
            json.dump(chunk, open(cp, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
            print(f"\n===== chunk {k} of {total} (items {i + 1}–{min(i + a.chunk, len(items))}) → {cp.relative_to(ROOT)} =====")
            print(json.dumps(chunk, ensure_ascii=False, indent=0))


if __name__ == "__main__":
    main()
