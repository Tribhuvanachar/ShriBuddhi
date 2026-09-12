#!/usr/bin/env python3
"""Stage C — apply human/Gemini-verified answers to the Bhāgavata Sāroddhāra data layers.

    python3 tools/saroddhara/apply_verified.py verify_output/answers.json [more.json ...]

answers.json (exported by verify_queue.html, or written by hand / by Gemini) maps queue ids to answers:
  "BS_V017":                  {"verified_text": "...", "accept_vision": false, "note": "..."}   verse text
  "BS_V017_C_p111_y842":      {"verified_text": "..."}                                          one commentary line
  "BS_V017_F1_p111":          {"verse": 17}                                                     footnote re-attachment
  "BS_V006":                  {"verified_text": "...", "bhagavata_ref": "1.5.13", "page": 103}  a verse OCR missed
Every applied answer is recorded in the item's `verification.human` field; nothing is applied twice."""
import json, re, sys, datetime
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "data/bhagavata_saroddhara"


def load(sub): return json.load(open(BASE / sub / "data.json", encoding="utf-8"))
def save(sub, d): json.dump(d, open(BASE / sub / "data.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def main(files):
    answers = {}
    for f in files: answers.update(json.load(open(f, encoding="utf-8")))
    mula, tika, tipp = load("mula"), load("tika_vishnutirtha"), load("tika_tippani")
    by_n = {it["verse_no"]: it for it in mula["items"]}
    tby = {it["id"]: it for it in tika["items"]}; fby = {it["id"]: it for it in tipp["items"]}
    stamp = datetime.date.today().isoformat(); n_applied = 0; log = []
    for qid, a in answers.items():
        if not isinstance(a, dict) or qid.startswith("_"): continue     # "_unsure" etc. are bookkeeping
        m = re.match(r"BS_V(\d+)(?:_C_p(\d+)_y(\d+)|_F(\d+)_p(\d+))?$", qid)
        if not m: log.append(f"skip {qid}: unknown id shape"); continue
        n = int(m.group(1)); it = by_n.get(n)
        txt = (a.get("verified_text") or "").strip()
        if m.group(2):            # commentary line
            if not it or it["id"] not in tby or not txt: log.append(f"skip {qid}: no commentary item or empty text"); continue
            t = tby[it["id"]]; old = t.get("ocr_lines_replaced", [])
            if qid in old: continue
            # replace the matching OCR line (found in the queue) by the verified text
            src = a.get("original") or ""
            if src and src in t["sanskrit_text"]: t["sanskrit_text"] = t["sanskrit_text"].replace(src, txt, 1)
            else: t.setdefault("human_corrections", []).append({"id": qid, "text": txt})
            t.setdefault("ocr_lines_replaced", []).append(qid); n_applied += 1
        elif m.group(4):          # footnote attachment
            tgt = a.get("verse")
            if not it or not tgt or tgt == n: continue
            src_item = fby.get(it["id"]); k = int(m.group(4))
            if not src_item: continue
            fn = next((f for f in src_item.get("footnotes", []) if f["n"] == k), None)
            if not fn: continue
            src_item["footnotes"].remove(fn); fn["attached_by"] = "human"
            dst = by_n.get(int(tgt))
            if dst:
                d = fby.get(dst["id"]) or {"id": dst["id"], "reference": f"{dst['category']} · टिप्पणी · {dst['verse_no']}", "sanskrit_text": "", "tags": ["footnote"], "notes": "", "references": [], "audio": [], "category": dst["category"], "verse_no": dst["verse_no"], "footnotes": [], "source": {}}
                if d["id"] not in fby: tipp["items"].append(d); fby[d["id"]] = d
                d["footnotes"].append(fn)
            for x in (src_item, fby.get(dst["id"]) if dst else None):
                if x: x["sanskrit_text"] = "\n".join(f"{f['n']}. {f['text']}" for f in x["footnotes"])
            n_applied += 1
        else:                     # verse
            if it is None:        # a missed verse supplied by the human
                if not txt: continue
                ref = a.get("bhagavata_ref") or ""; parts = [int(x) for x in re.findall(r"\d+", ref)][:3]
                pk = next((i["prakarana_no"] for i in mula["items"] if i["verse_no"] > n), mula["items"][-1]["prakarana_no"])
                cat = next((i["category"] for i in mula["items"] if i["prakarana_no"] == pk), "")
                new = {"id": f"BS_P{pk:02d}_V{n:03d}", "reference": f"{cat} · श्लोकः {n}" + (f" · भा. {parts[0]}.{parts[1]}.{parts[2]}" if len(parts) == 3 else ""), "sanskrit_text": txt, "tags": ["verse", "bhagavata"], "notes": "", "references": ([{"target": f"purana/maha_purana/bhagavata_purana_madhva/skandha_{parts[0]:02d}", "unit_id": f"adhyaya_{parts[1]:02d}", "note": f"cites Bhāgavata {parts[0]}.{parts[1]}.{parts[2]}"}] if len(parts) == 3 else []),
                       "audio": [], "category": cat, "prakarana_no": pk, "verse_no": n, "bhagavata_ref": ({"skandha": parts[0], "adhyaya": parts[1], "verse": str(parts[2])} if len(parts) == 3 else None),
                       "verification": {"status": "human_supplied", "human": {"date": stamp, "note": a.get("note")}}, "source": {"pdf_page": a.get("page")}}
                mula["items"].append(new); mula["items"].sort(key=lambda i: i["verse_no"]); by_n[n] = new; n_applied += 1
                continue
            if it.get("verification", {}).get("human"): continue
            if a.get("accept_vision") and not txt: txt = it.get("ocr", {}).get("vision", "").strip()
            parts = [int(x) for x in re.findall(r"\d+", a.get("bhagavata_ref") or "")][:3]
            if len(parts) == 3 and parts != [int(x) for x in re.findall(r"\d+", str((it.get("bhagavata_ref") or {}).get("skandha", "")) + "." + str((it.get("bhagavata_ref") or {}).get("adhyaya", "")) + "." + str((it.get("bhagavata_ref") or {}).get("verse", "")))][:3]:
                it["bhagavata_ref"] = {"skandha": parts[0], "adhyaya": parts[1], "verse": str(parts[2])}
                it["reference"] = re.sub(r" · भा\. [\d.\-]+$", "", it["reference"]) + f" · भा. {parts[0]}.{parts[1]}.{parts[2]}"
                it["references"] = [{"target": f"purana/maha_purana/bhagavata_purana_madhva/skandha_{parts[0]:02d}", "unit_id": f"adhyaya_{parts[1]:02d}", "note": f"cites Bhāgavata {parts[0]}.{parts[1]}.{parts[2]}"}]
                it["verification"]["dge_key"] = parts; it["verification"]["ref_reidentified"] = True
            if txt:
                it["sanskrit_text"] = re.sub(r"\s*(?:॥|\|\||।।)\s*[०-९]{1,3}\s*(?:॥|\|\||।।)\s*$", " ॥", txt).strip()
            it["verification"]["human"] = {"date": stamp, "note": a.get("note"), "accepted_vision": bool(a.get("accept_vision")), "text_changed": bool(txt), "via": a.get("via", "verify_queue")}
            it["verification"]["status"] = "human_verified"; n_applied += 1
            if a.get("decision") == "dge" and a.get("note") and re.search(r"[Pp]rint reads|word order|पाठ", a["note"]):
                line = "पाठभेदः (मुद्रित-सारोद्धारः): " + a["note"].strip()      # genuine print variant → editorial note on the verse
                if line not in (it.get("notes") or ""): it["notes"] = ((it.get("notes") or "") + "\n" + line).strip()
    save("mula", mula); save("tika_vishnutirtha", tika); save("tika_tippani", tipp)
    print(f"applied {n_applied} answers; {len(log)} skipped"); [print("  ", l) for l in log[:20]]


if __name__ == "__main__":
    main(sys.argv[1:])
