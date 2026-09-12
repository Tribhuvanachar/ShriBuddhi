#!/usr/bin/env python3
"""Cross-check every Bhāgavata Sāroddhāra verse against the DGE Madhva Bhāgavata mūla, word by word.

    python3 tools/saroddhara/mula_crosscheck.py [--out data/ocr_staging/bhagavata_saroddhara/verify_input/mula_crosscheck.json]

Policy (one text, not two): the DGE Madhva Bhāgavata is the master copy. A Sāroddhāra verse that the
build verified against it already carries the DGE text verbatim (the print's OCR stays in `ocr`). This
report lists every verse where the PRINT (Vision OCR) still differs from that master text at the word
level, so a person can confirm that the print really agrees (OCR noise) or flag a genuine variant reading
(pāṭhabheda) — which is then fixed on BOTH sides through tools/saroddhara/apply_chat_answers.py
--sync-bhagavata. Verses whose text was NOT unified yet (mismatch, ref_not_in_dge, extra) are listed first."""
import argparse, difflib, json, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "saroddhara"))
from build_saroddhara import load_bhp, ratio  # noqa: E402
BASE = ROOT / "data/bhagavata_saroddhara"
OUT = ROOT / "data/ocr_staging/bhagavata_saroddhara/verify_input/mula_crosscheck.json"
NOISE = str.maketrans("", "", "ऽ")   # avagraha is printed inconsistently


def words(t):
    t = re.sub(r"[॥।|]\s*[०-९0-9]*\s*[॥।|]?", " ", t or "")
    t = re.sub(r"[()\[\]'\"“”‘’*?\-–—]", " ", t)
    return [w.translate(NOISE) for w in t.split() if re.search(r"[ऀ-ॿ]", w)]


def ref_str(r): return f"{r['skandha']}.{r['adhyaya']}.{r['verse']}" if r else None


def diff_pairs(a, b):
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    out = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal": continue
        pa, pb = " ".join(a[i1:i2]), " ".join(b[j1:j2])
        r = ratio(pa, pb) if pa and pb else 0.0
        out.append({"print": pa or None, "dge": pb or None, "similarity": round(r, 2), "kind": "ocr_noise" if r >= 0.8 else "word"})
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--batches", type=int, default=0, help="also write diffs_batch_NN.json: compact word-diff items, N per file, for a chat without URL access")
    ap.add_argument("--exclude", default="", help="comma-separated verse ids or book refs already adjudicated (left out of the batches)")
    a = ap.parse_args()
    bhp = load_bhp(); mula = json.load(open(BASE / "mula/data.json", encoding="utf-8"))
    rows = []; stats = {"verses": 0, "identical_to_dge": 0, "unified_print_noise_only": 0, "unified_print_word_diffs": 0, "not_unified": 0}
    for it in mula["items"]:
        stats["verses"] += 1
        v = it["verification"]; key = tuple(v.get("dge_key") or [])
        if not key and it.get("bhagavata_ref"):                       # verses supplied by hand carry only bhagavata_ref
            r = it["bhagavata_ref"]; key = (int(r["skandha"]), int(r["adhyaya"]), int(re.findall(r"\d+", str(r["verse"]))[0]))
        dge = bhp.get(key, {}).get("text") if key else None
        ocr = (it.get("ocr") or {}).get("vision") or ""
        cur = it["sanskrit_text"]
        unified = bool(dge) and words(cur) == words(dge)
        pairs_print = diff_pairs(words(ocr), words(dge)) if dge else []
        if unified and not pairs_print:
            stats["identical_to_dge"] += 1; continue
        if unified:
            bucket = "unified_print_word_diffs" if any(p["kind"] == "word" for p in pairs_print) else "unified_print_noise_only"
        else:
            bucket = "not_unified"
        stats[bucket] += 1
        rows.append({"id": f"BS_V{it['verse_no']:03d}", "verse_num": it["verse_no"], "prakarana": it["category"], "pdf_page": it["source"].get("pdf_page"),
                     "book_ref": ref_str(it.get("bhagavata_ref")), "status": v["status"], "bucket": bucket,
                     "current_text": cur, "print_ocr_vision": ocr or None, "dge_mula_text": dge,
                     "differences_print_vs_dge": pairs_print or None,
                     "question": ("Which reading does the print actually have for each 'word' difference? If the print is right and DGE is wrong, answer decision='printed' with the full verse; if the print agrees with DGE (OCR noise), decision='dge'."
                                  if bucket != "not_unified" else "Text not yet unified with the DGE mūla — see batch_01_critical.json for the arbitration question.")})
    order = {"not_unified": 0, "unified_print_word_diffs": 1, "unified_print_noise_only": 2}
    rows.sort(key=lambda r: (order[r["bucket"]], r["verse_num"]))
    out = {"_readme": "Sāroddhāra verses vs DGE Madhva Bhāgavata, word by word. Master copy = DGE Bhāgavata; every unified verse already carries the DGE text. 'print' = what the scanned edition shows (Vision OCR); 'dge' = the master. kind=ocr_noise: the two spellings differ by little (OCR error likely); kind=word: a different word — needs a human eye on the scan.",
           "_answer_shape": {"id": "BS_V042", "decision": "dge|printed|unsure", "verified_text": "full verse if printed, else null", "bhagavata_ref": "s.a.v", "note": "…"},
           "policy": "ONE text: apply_chat_answers.py writes decision=dge into the Sāroddhāra and decision=printed (with --sync-bhagavata) into BOTH the Sāroddhāra and the Bhāgavata mūla.",
           "stats": stats, "items": rows}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(stats), "→", Path(a.out).relative_to(ROOT))
    if a.batches:
        write_batches(rows, a.batches, {x.strip() for x in a.exclude.split(",") if x.strip()}, Path(a.out).parent)


def snippet(ws, i, j, n=2):
    return " ".join(ws[max(0, i - n):i] + ["【" + " ".join(ws[i:j]) + "】"] + ws[j:j + n]) if ws else ""


def write_batches(rows, per, exclude, outdir):
    """Compact word-diff items (no verse bodies) for pasting into a chat: one item per 'word' difference."""
    items = []
    for r in rows:
        if r["bucket"] != "unified_print_word_diffs" or r["id"] in exclude or (r["book_ref"] or "") in exclude:
            continue
        if r["status"] in ("human_verified", "human_supplied"):      # already adjudicated through answers.json
            continue
        dw, pw = words(r["dge_mula_text"]), words(r["print_ocr_vision"])
        sm = difflib.SequenceMatcher(None, pw, dw, autojunk=False)
        for op, i1, i2, j1, j2 in sm.get_opcodes():
            if op == "equal": continue
            pa, pb = " ".join(pw[i1:i2]), " ".join(dw[j1:j2])
            if pa and pb and ratio(pa, pb) >= 0.8: continue          # ocr_noise pairs are not worth a chat turn
            items.append({"id": r["id"], "ref": r["book_ref"], "pdf_page": r["pdf_page"], "dge_word": pb or None, "print_word": pa or None,
                          "context": snippet(dw, j1, j2) if pb else snippet(pw, i1, i2), "kind": "word"})
    # append-only: batches already written (and possibly already handed to a chat) keep their items and numbering
    seen, existing = set(), sorted(outdir.glob("diffs_batch_*.json"))
    for f in existing:
        for it in json.load(open(f, encoding="utf-8")).get("items", []):
            seen.add((it["id"], it.get("dge_word"), it.get("print_word")))
    items = [it for it in items if (it["id"], it["dge_word"], it["print_word"]) not in seen]
    start = len(existing)
    n = -(-len(items) // per) if items else 0
    for k in range(n):
        chunk = items[k * per:(k + 1) * per]
        f = outdir / f"diffs_batch_{start + k + 1:02d}.json"
        json.dump({"_how_to_answer": "One JSON list, one object per id: {id, decision: 'dge'|'printed'|'unsure', verified_text (full verse only when printed), note}. 'dge' with a note = keep the master text and record the print's reading as a footnote on the Sāroddhāra verse.",
                   "batch": f"{start + k + 1}", "items": chunk}, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        print(f"  {f.relative_to(ROOT)}: {len(chunk)} items")
    print(f"new word-diff items {len(items)} → {n} new batch file(s) after {start} existing (excluded {len(exclude)} adjudicated refs)")


if __name__ == "__main__":
    main()
