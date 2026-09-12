#!/usr/bin/env python3
"""Fold Gemini chat replies for the Upaniṣad-ṭippaṇī pack into the staging area.

    python3 tools/upanishad_tippani/apply_answers.py reply1.txt [reply2.txt ...]

Reply kinds (by the `pack` tag inside the JSON): UP-<BOOK>-LABELS → labels.json (abbreviation → commentator /
layer); UP-<BOOK>-NEW-nn → clean_text on the block (kept only if it resembles the Vision or Tesseract reading,
ratio ≥ 0.6 — Gemini must not rewrite from memory); UP-<BOOK>-DIFF-nn → decisions.json. Everything lands under
data/ocr_staging/upanishad_tippani/<book>/answers/ and is idempotent; the importer reads these files."""
import difflib, json, re, sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
STG = ROOT / "data/ocr_staging/upanishad_tippani"


def parse(text):
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m: text = m.group(1)
    text = text.strip()
    try: return json.loads(text)
    except json.JSONDecodeError:
        s = text.find("{"); e = text.rfind("}") + 1
        return json.loads(text[s:e])


def dev(s): return re.sub(r"[^ऀ-ॿ]", "", s or "")
def ratio(a, b): return difflib.SequenceMatcher(None, dev(a), dev(b), autojunk=False).ratio()


def main():
    stamp = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d %b %Y, %I:%M %p IST")
    for f in sys.argv[1:]:
        d = parse(open(f, encoding="utf-8").read())
        pack = (d.get("pack") or ""); m = re.match(r"UP-([A-Z]+)-(LABELS|NEW|DIFF)(?:-(\d+))?", pack)
        if not m: print(f"{f}: no UP-<BOOK>-… pack tag, skipped"); continue
        book, kind = m.group(1).lower(), m.group(2)
        out = STG / book / "answers"; out.mkdir(parents=True, exist_ok=True)
        items = d.get("items") or []
        if kind == "LABELS":
            p = out / "labels.json"; cur = json.load(open(p, encoding="utf-8")) if p.exists() else {}
            for it in items:
                if it.get("label"): cur[it["label"]] = dict(it, at=stamp)
            json.dump(cur, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print(f"{book}: {len(items)} label mappings → {p.relative_to(ROOT)}")
        elif kind == "NEW":
            blocks = {b["id"]: b for b in json.load(open(STG / book / "blocks.json", encoding="utf-8"))["blocks"]}
            p = out / "clean_text.json"; cur = json.load(open(p, encoding="utf-8")) if p.exists() else {}
            ok = held = 0
            for it in items:
                b = blocks.get(it.get("id")); t = (it.get("clean_text") or "").strip()
                if not b or not t: continue
                r = max(ratio(t, b["vision_text"]), ratio(t, b.get("tess_text", "")))
                if r >= 0.6:
                    cur[it["id"]] = {"clean_text": t, "commentator": it.get("commentator"), "kind": it.get("kind"), "confidence": it.get("confidence"), "ocr_ratio": round(r, 2), "at": stamp}; ok += 1
                else:
                    cur.setdefault("_held", {})[it["id"]] = {"clean_text": t, "ocr_ratio": round(r, 2), "at": stamp}; held += 1
            json.dump(cur, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print(f"{book}: {ok} clean texts accepted, {held} held (do not resemble the OCR) → {p.relative_to(ROOT)}")
        else:
            p = out / "decisions.json"; cur = json.load(open(p, encoding="utf-8")) if p.exists() else {}
            for it in items:
                if it.get("id") and it.get("print") is not None: cur[f"{it['id']}|{it['print']}"] = dict(it, at=stamp)
            json.dump(cur, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print(f"{book}: {len(items)} word-diff decisions → {p.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
