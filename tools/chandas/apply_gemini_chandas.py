#!/usr/bin/env python3
"""Ingest Gemini's answer to GEMINI_CHANDAS_TASK.md — or seed the example suite from our own corpus.

    python3 tools/chandas/apply_gemini_chandas.py response.json [more.json ...]
    python3 tools/chandas/apply_gemini_chandas.py --seed-from-corpus

Every example verse (Part A, Part D, and Part C `corrected_text`) is re-scanned with the real engine
(js/chandas.js via tools/kamadhenu/chandas_runner.js). An example is accepted only when the engine
names the claimed vṛtta; accepted examples go to
  * tests/fixtures/chandas_examples.json   — the regression suite (tests/test_chandas_examples.py), and
  * data/vedanga/chandas/data.json     — the `verified_examples` field of the matching metre row.
Parts B, C and D never change a lakṣaṇa or a grantha text by themselves: they are written to
kamadhenu_dataset/chandas_gemini_review.md for a person to check against the cited authority.
Rejected examples are listed in the same report with the engine's actual verdict.
"""
import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "data" / "vedanga" / "chandas" / "data.json"
FIXTURE = ROOT / "tests" / "fixtures" / "chandas_examples.json"
INDEX = ROOT / "kamadhenu_dataset" / "text_index.json"
REPORT = ROOT / "kamadhenu_dataset" / "chandas_gemini_review.md"
RUNNER = ROOT / "tools" / "kamadhenu" / "chandas_runner.js"
MBTN = "mahabharata_tatparya_nirnaya"


def now_ist():
    return datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d %b %Y, %I:%M %p IST")


def engine(texts):
    r = subprocess.run(["node", str(RUNNER)], input=json.dumps(list(texts), ensure_ascii=False),
                       capture_output=True, text=True, cwd=str(ROOT), check=True)
    return json.loads(r.stdout)


def engine_names(res):
    m = res.get("match") or {}
    names = []
    for n in m.get("names") or []:
        names.extend(x.strip() for x in n.split(","))
    return names, m.get("kind", ""), ["".join("G" if c == "ग" else "L" for c in p["pattern"]) for p in res["padas"]]


def clean_verse(text):
    text = re.sub(r"[-–—]", "", text)                 # hyphenated compounds in the SMV/RV data
    lines = [l.strip(" ।॥|") for l in re.split(r"[\n।॥]+", text)]
    return "\n".join(l for l in lines if l)


def row_ids(db):
    ids = {}
    for key in ("sama_vrutta", "ardhasama_vrutta", "vishama_vrutta", "upajati_vrutta"):
        for v in db[key]:
            for n in v["vrutta_names"]:
                ids.setdefault(n, v["vrutta_names"][0])
                for part in n.split(","):        # ardhasama rows join their names in one string
                    ids.setdefault(part.strip(), v["vrutta_names"][0])
    return ids


def load_fixture():
    if FIXTURE.exists():
        return json.loads(FIXTURE.read_text(encoding="utf-8"))
    return {"schema": "dge_chandas_examples_v1", "note": "One engine-verified example verse per vṛtta; tests/test_chandas_examples.py replays every entry.", "examples": []}


def save_fixture(fx):
    fx["examples"].sort(key=lambda e: e["vrutta"])
    FIXTURE.write_text(json.dumps(fx, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def add_examples_to_db(db, accepted):
    by_id = {}
    for key in ("sama_vrutta", "ardhasama_vrutta", "vishama_vrutta", "upajati_vrutta"):
        for v in db[key]:
            by_id[v["vrutta_names"][0]] = v
    for e in accepted:
        v = by_id[e["vrutta"]]
        # `examples` (vendor, list of strings) stays as shipped; verified verses get their own key
        ex = v.setdefault("verified_examples", [])
        if not any(x.get("text") == e["text"] for x in ex):
            ex.append({"text": e["text"], "source": e["source"]})


def verify(candidates, ids):
    """candidates: [{vrutta, text, source, origin, claimed_scan?}] → (accepted, rejected)."""
    accepted, rejected = [], []
    if not candidates:
        return accepted, rejected
    results = engine([c["text"] for c in candidates])
    for c, r in zip(candidates, results):
        names, kind, scan = engine_names(r)
        target = ids.get(c["vrutta"])
        ok = target is not None and any(ids.get(n) == target for n in names)
        entry = dict(c, engine_names=names, engine_kind=kind, engine_scan=scan)
        (accepted if ok else rejected).append(entry)
    return accepted, rejected


def seed_from_corpus(db, fx, ids):
    idx = json.loads(INDEX.read_text(encoding="utf-8"))
    have = {e["vrutta"] for e in fx["examples"]}
    picked = {}
    for u in idx["units"]:
        if u["work"] == MBTN:
            continue
        ca = u.get("chandas_analysis") or {}
        if ca.get("confidence", 0) < 1.0 or ca.get("classification") in ("anushtubh_rule", "unknown", "matra_jati"):
            continue
        for n in ca.get("chandas", "").split(","):
            rid = ids.get(n.strip())
            if rid and rid not in have and rid not in picked:
                text = clean_verse(u["metrical_text"])
                if text:
                    picked[rid] = {"vrutta": rid, "text": text, "source": f"{u['work_label']} {u['id'].split(':', 1)[1].replace('sarga_', '').replace(':', '.')}",
                                   "origin": "dge_corpus", "corpus_id": u["id"]}
    vendor = ROOT / "tools" / "chandas" / "vendor" / "examples.json"
    if vendor.exists():
        for name, lines in json.loads(vendor.read_text(encoding="utf-8")).items():
            rid = ids.get(name)
            verse = [l for l in lines[1:] if l.strip()]
            if rid and rid not in have and rid not in picked and verse:
                picked[rid] = {"vrutta": rid, "text": clean_verse("\n".join(verse)), "source": "Chandojñānam examples.json", "origin": "vendor"}
    return list(picked.values())


def ingest(files, ids):
    """Split Gemini JSON files into example candidates and review items."""
    cands, review = [], {"B": [], "C": [], "D": [], "A_null": []}
    for f in files:
        data = json.loads(Path(f).read_text(encoding="utf-8"))
        if data.get("schema") != "dge_chandas_gemini_v1":
            sys.exit(f"{f}: unexpected schema {data.get('schema')!r}")
        part = data.get("part")
        for it in data.get("items", []):
            if part == "A":
                ex = it.get("example")
                if not ex or not ex.get("text"):
                    review["A_null"].append(it)
                    continue
                cands.append({"vrutta": it["vrutta"], "text": clean_verse(ex["text"]), "source": ex.get("source", "?"),
                              "origin": "gemini", "kind": ex.get("kind", "verse"), "claimed_scan": ex.get("scan"), "confidence": it.get("confidence")})
            elif part == "B":
                review["B"].append(it)
            elif part == "C":
                review["C"].append(it)
                if it.get("verdict") == "text_defect" and it.get("corrected_text") and it.get("chandas"):
                    cands.append({"vrutta": it["chandas"], "text": clean_verse(it["corrected_text"]), "source": it["id"],
                                  "origin": "gemini_part_c", "review_only": True, "confidence": it.get("confidence")})
            elif part == "D":
                review["D"].append(it)
                ex = it.get("example") or {}
                if ex.get("text"):
                    cands.append({"vrutta": it["vrutta"], "text": clean_verse(ex["text"]), "source": ex.get("source", "?"),
                                  "origin": "gemini_part_d", "review_only": True, "confidence": it.get("confidence")})
    return cands, review


def write_report(accepted, rejected, review, seeded):
    L = [f"# Chandas — Gemini/corpus ingest report\n\nGenerated {now_ist()} by `tools/chandas/apply_gemini_chandas.py`.\n"]
    L.append(f"* accepted examples: {len(accepted)} (engine named the claimed vṛtta)\n* rejected examples: {len(rejected)}\n")
    if seeded:
        L.append("* mode: `--seed-from-corpus` (verses already identified in kamadhenu_dataset/text_index.json + vendor examples)\n")
    if rejected:
        L.append("\n## Rejected examples (engine disagrees — do not use without a human check)\n")
        for e in rejected:
            L.append(f"* **{e['vrutta']}** ({e['origin']}, {e['source']}): engine says {e['engine_kind']} {e['engine_names'] or '—'}; scan {e['engine_scan']}\n  `{e['text'].replace(chr(10), ' / ')}`")
    if review["B"]:
        L.append("\n## Part B — proposed table corrections (verify against the cited authority before editing data.json)\n")
        for it in review["B"]:
            L.append(f"* **{it.get('vrutta')}** {it.get('field')}: `{it.get('current')}` → `{it.get('proposed')}` — {it.get('authority')} (conf {it.get('confidence')}) {it.get('note') or ''}")
    if review["C"]:
        L.append("\n## Part C — verdicts on unresolved verses\n")
        for it in review["C"]:
            L.append(f"* `{it.get('id')}` **{it.get('verdict')}** {it.get('chandas') or ''} (conf {it.get('confidence')}) — {it.get('note') or ''}" + (f"\n  corrected: `{it['corrected_text'].replace(chr(10), ' / ')}`" if it.get("corrected_text") else ""))
        ok = {e["source"] for e in accepted if e["origin"] == "gemini_part_c"}
        if ok:
            L.append(f"\nCorrected texts the engine confirms in the claimed metre ({len(ok)}): " + ", ".join(sorted(f"`{s}`" for s in ok)))
    if review["D"]:
        L.append("\n## Part D — metres proposed for addition (not added automatically)\n")
        for it in review["D"]:
            L.append(f"* **{it.get('vrutta')}** {it.get('type')} {it.get('gana')} `{'/'.join(it.get('padas') or [])}` yati {it.get('yati')} — {it.get('authority')} (conf {it.get('confidence')})")
    if review["A_null"]:
        L.append(f"\n## Part A — vṛttas Gemini could not exemplify ({len(review['A_null'])})\n\n" + ", ".join(it.get("vrutta", "?") for it in review["A_null"]))
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--seed-from-corpus", action="store_true")
    a = ap.parse_args()
    db = json.loads(DB.read_text(encoding="utf-8"))
    ids = row_ids(db)
    fx = load_fixture()
    review = {"B": [], "C": [], "D": [], "A_null": []}
    if a.seed_from_corpus:
        cands = seed_from_corpus(db, fx, ids)
    elif a.files:
        cands, review = ingest(a.files, ids)
    else:
        ap.error("give response JSON files or --seed-from-corpus")
    accepted, rejected = verify(cands, ids)
    have = {e["vrutta"] for e in fx["examples"]}
    new = [e for e in accepted if not e.get("review_only") and e["vrutta"] not in have]
    for e in new:
        fx["examples"].append({k: e[k] for k in ("vrutta", "text", "source", "origin") if k in e} | {"scan": e["engine_scan"], "verified": now_ist()})
        have.add(e["vrutta"])
    if new:
        save_fixture(fx)
        add_examples_to_db(db, new)
        DB.write_text(json.dumps(db, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    write_report(accepted, rejected, review, a.seed_from_corpus)
    total = sum(len(db[k]) for k in ("sama_vrutta", "ardhasama_vrutta", "vishama_vrutta", "upajati_vrutta"))
    print(f"candidates {len(cands)}: accepted {len(accepted)}, rejected {len(rejected)}, new fixtures {len(new)}; "
          f"example coverage {len(have)}/{total} vṛttas; report → {REPORT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
