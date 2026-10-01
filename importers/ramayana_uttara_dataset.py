"""Uttara Kanda from the Ashutosh-Vijay Valmiki_Ramayan_Dataset
   -> itihasa/ramayana/uttara_kanda/saartha/data.json

valmikiramayan.net has no Uttara Kanda, so the `saartha` layer stops at Yuddha.
This fills it from the raw rows landed in ParaBuddhi
(_sources/github_Ashutosh-Vijay_Valmiki_Ramayan_Dataset/uttara_kanda.raw.jsonl).
It reads that file; it never fetches. Verse ids follow this edition (111 sargas,
vulgate numbering), not the BORI numbering of /mula, so it stays a parallel layer.

Per-shloka shape: {number, sanskrit_text, transliteration, artha (word glosses
then English sentence, as in the other saartha layers)}; sarga `summary` where the source has one.

The source's provenance is mixed and partly unknown (see its SOURCE.md in
ParaBuddhi); the English layers are unverified.

  python3 importers/ramayana_uttara_dataset.py PATH/TO/uttara_kanda.raw.jsonl
"""
import json, os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
from format_data_json import canonical

OUT = os.path.join(os.path.dirname(__file__), "..", "data", "itihasa", "ramayana",
                   "uttara_kanda", "saartha", "data.json")
# the id marker and anything after it (a few rows carry stray fragments past it)
TAIL = re.compile(r"\s*(?:।।|॥|\|\|)\s*7\s*\.\s*\d+\s*\.\s*\d+\s*(?:।।|॥|\|\|)?.*$", re.S)
TAIL_IAST = re.compile(r"\s*\|\|\s*7\.\d+\.\d+\s*\|\|\s*$")

def clean(s, rx):
    return rx.sub("", (s or "").strip()).strip()

def build(rows):
    by = {}
    for r in rows:
        by.setdefault(r["sarga"], []).append(r)
    items = []
    for sno in sorted(by):
        sh = []
        for r in sorted(by[sno], key=lambda r: r["shloka"]):
            v = {"number": r["shloka"],
                 "sanskrit_text": clean(r["shloka_text"], TAIL),
                 "transliteration": clean(r["transliteration"], TAIL_IAST)}
            # like the sibling saartha layers: word glosses then the sentence, in `artha`
            artha = " ".join(x.strip() for x in (r.get("translation"), r.get("explanation")) if (x or "").strip())
            if artha:
                v["artha"] = artha
            sh.append(v)
        it = {"id": f"sarga_{sno:03d}", "reference": f"Uttara Kanda, Sarga {sno}"}
        summ = next(((r.get("comments") or "").strip() for r in by[sno] if (r.get("comments") or "").strip()), "")
        if summ:
            it["summary"] = summ
        it["shlokas"] = sh
        items.append(it)
    return {"schema": "itihasa_purana_text", "default_author": "Maharshi Valmiki", "items": items}

if __name__ == "__main__":
    rows = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
    doc = build(rows)
    text = canonical(doc)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w", encoding="utf-8").write(text if text.endswith("\n") else text + "\n")
    print(len(doc["items"]), "sargas", sum(len(i["shlokas"]) for i in doc["items"]), "shlokas ->", OUT)
