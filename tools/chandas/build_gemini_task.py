#!/usr/bin/env python3
"""Build the self-contained Gemini task file for closing the Chandas engine gaps.

Writes dge/data/vedanga/chandas/GEMINI_CHANDAS_TASK.md from
  * dge/data/vedanga/chandas/data.json           (the 245 vṛttas the engine knows)
  * kamadhenu_dataset/text_index.json            (verses the engine could not name)
  * tests/fixtures/chandas_examples.json         (vṛttas that already have a verified example)

The file is meant to be hosted at ONE raw GitHub URL and handed to Gemini (which has no
GitHub access) as its entire brief. Gemini answers in the strict JSON described inside the
file; tools/chandas/apply_gemini_chandas.py ingests that JSON. No Gemini call happens here.

Usage:  python3 tools/chandas/build_gemini_task.py [--batch 40]
"""
import argparse
import json
import re
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "dge" / "data" / "vedanga" / "chandas" / "data.json"
INDEX = ROOT / "kamadhenu_dataset" / "text_index.json"
FIXTURE = ROOT / "tests" / "fixtures" / "chandas_examples.json"
OUT = ROOT / "dge" / "data" / "vedanga" / "chandas" / "GEMINI_CHANDAS_TASK.md"
RAW_URL = "https://raw.githubusercontent.com/Tribhuvanachar/bhumandala/main/dge/data/vedanga/chandas/GEMINI_CHANDAS_TASK.md"

MBTN = "mahabharata_tatparya_nirnaya"   # prose-heavy ṭippaṇī units; excluded from the verse list


def lg(dev):
    return "".join("G" if c == "ग" else "L" if c == "ल" else c for c in dev)


def load():
    db = json.loads(DB.read_text(encoding="utf-8"))
    idx = json.loads(INDEX.read_text(encoding="utf-8"))
    fx = json.loads(FIXTURE.read_text(encoding="utf-8")) if FIXTURE.exists() else {"examples": []}
    return db, idx, fx


def vrutta_rows(db):
    """One row per vṛtta (245): id, primary name, alt names, type, per-pāda L/G, akṣaras, yati."""
    rows = []
    for v in db["sama_vrutta"]:
        rows.append(OrderedDict(id=v["vrutta_names"][0], names=v["vrutta_names"], type="sama",
                                gana=v["gana"], padas=[lg(v["lakshana"])] * 4, aksharas=[v["akshara_sankhya"]] * 4,
                                yati=v.get("yati") or []))
    for key, typ in (("ardhasama_vrutta", "ardhasama"), ("vishama_vrutta", "vishama"), ("upajati_vrutta", "upajati")):
        for v in db[key]:
            rows.append(OrderedDict(id=v["vrutta_names"][0], names=v["vrutta_names"], type=typ,
                                    gana="/".join(p["lakshana"] for p in v["padas"]),
                                    padas=[lg(p["lakshana_raw"]) for p in v["padas"]],
                                    aksharas=[p["akshara_sankhya"] for p in v["padas"]],
                                    yati=[p.get("yati") or [] for p in v["padas"]] if any(p.get("yati") for p in v["padas"]) else []))
    return rows


def unresolved(idx):
    out = []
    for u in idx["units"]:
        if u["work"] == MBTN:
            continue
        ca = u.get("chandas_analysis") or {}
        if ca.get("classification") == "unknown" or ca.get("anushtubh_irregular"):
            out.append(OrderedDict(id=u["id"], work=u["work_label"], text=u["metrical_text"],
                                   scan=ca.get("laghu_guru", ""), syllables=ca.get("syllables_per_pada", []),
                                   reason=ca.get("inferred_reason", ""), near=[n if isinstance(n, str) else n.get("name", "") for n in (ca.get("near_matches") or [])][:3]))
    return out


def md_table(header, rows):
    return "| " + " | ".join(header) + " |\n|" + "|".join("---" for _ in header) + "|\n" + "\n".join("| " + " | ".join(r) + " |" for r in rows) + "\n"


def build(batch):
    db, idx, fx = load()
    rows = vrutta_rows(db)
    have = {e["vrutta"] for e in fx.get("examples", [])}
    missing = [r for r in rows if r["id"] not in have]
    unres = unresolved(idx)
    now = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d %b %Y, %I:%M %p IST")

    L = []
    L.append(f"""# DGE Chandas engine — Gemini task brief

Generated {now} by `tools/chandas/build_gemini_task.py`. Canonical URL: `{RAW_URL}`

You are helping the Sarvamūla Digital Library (a Mādhva Sanskrit corpus) finish its classical-metre
(vṛtta) identifier. You have no repository access; **this file is your entire brief**. Everything you
return is verified mechanically by our engine before it is used, so precision matters more than volume:
answer `null` / `"unsure"` rather than inventing a verse or a lakṣaṇa.

## 0. How to answer

* Reply with **JSON only** (no prose before or after, no Markdown fences), one object per run:
  `{{"schema": "dge_chandas_gemini_v1", "part": "A" | "B" | "C" | "D", "items": [ ... ]}}`
* Work **one part per run**. If a part is too long for one reply, add `"batch": <n>` and do the batch we
  name in the prompt ("Part C batch 3"), or the first `{batch}` items when no batch is named.
* Devanagari only for Sanskrit text. Split every verse into pādas with `\\n` (four pādas for a
  catuṣpadī; an āryā-family verse also as four). No dandas, no verse numbers, no speaker lines.
* **Scan notation**: `L` = laghu, `G` = guru, one letter per akṣara, one string per pāda. Guru = long
  vowel, or a vowel followed by anusvāra/visarga/candrabindu/jihvāmūlīya/upadhmānīya, or followed by a
  conjunct; the last akṣara of a pāda is anceps. Gaṇa letters: य=LGG म=GGG त=GGL र=GLG ज=LGL
  भ=GLL न=LLL स=LLG ल=L ग=G.
* Cite sources exactly as `work chapter.verse` (e.g. `Kumārasambhava 1.1`, `Sumadhva Vijaya 7.10`,
  `Bhāgavata 4.9.6`, `Vṛttaratnākara 3.30`). Prefer Mādhva works (Sumadhva Vijaya, Rāghavendra Vijaya,
  Tīrthaprabandha, Dvādaśa Stotra, Madhva's own stotras), then Bhāgavata, Kālidāsa, Bhartṛhari,
  Māgha, Bhāravi, and the example verses printed in Vṛttaratnākara / Chandomañjarī / Śrutabodha.
* Give a `confidence` between 0 and 1 on every item. Self-check every example by scanning it: if your
  scan does not match the lakṣaṇa in §1, do not submit it.

## 1. The 245 vṛttas the engine knows (Chandojñānam table, AGPL-3.0 data)

`type`: sama = all four pādas alike; ardhasama = pādas 1,3 alike and 2,4 alike; viṣama = all differ;
upajāti = a named 4-pāda combination of indravajrā (I = GGLGGLLGLGG) and upendravajrā
(U = LGLGGLLGLGG) or of the other listed pādas. Yati = caesura positions counted in akṣaras.
""")
    trows = []
    for r in rows:
        pat = r["padas"][0] if r["type"] == "sama" else " / ".join(r["padas"])
        ak = str(r["aksharas"][0]) if r["type"] == "sama" else "/".join(map(str, r["aksharas"]))
        alt = ", ".join(r["names"][1:]) or "—"
        yati = ",".join(map(str, r["yati"])) if r["type"] == "sama" and r["yati"] else ("—" if r["type"] == "sama" else "")
        trows.append([r["id"], alt, r["type"], r["gana"], f"`{pat}`", ak, yati, "yes" if r["id"] in have else "**no**"])
    L.append(md_table(["vṛtta (id)", "other names", "type", "gaṇa", "pattern L/G", "akṣaras", "yati", "has verified example?"], trows))
    L.append(f"""
Totals: {len(rows)} vṛttas; {len(have)} already have a verified example verse; **{len(missing)} still need one** (Part A).

## 2. Part A — one authentic example verse for every vṛtta without one

For each vṛtta in §1 marked **no**, give one real verse (four pādas) actually composed in that metre, with its
source. Do not compose verses. A lakṣaṇa verse from Vṛttaratnākara / Chandomañjarī / Śrutabodha that is
itself written in the metre it defines is acceptable and should be marked `"kind": "lakshana_verse"`.
If you know no genuine verse, return `"example": null` — a null is useful, an invented verse is harmful.

Item shape:
```
{{"vrutta": "<id from §1, exactly>", "example": {{"text": "pāda1\\npāda2\\npāda3\\npāda4", "source": "work chapter.verse",
  "kind": "verse" | "lakshana_verse", "scan": ["L/G of pāda1", "…", "…", "…"]}}, "confidence": 0.0-1.0}}
```
Vṛttas that need an example (do them in this order, `{batch}` per batch):
""")
    for i in range(0, len(missing), batch):
        chunk = missing[i:i + batch]
        L.append(f"* batch {i // batch + 1}: " + ", ".join(f"{r['id']} ({'/'.join(map(str, r['aksharas'])) if r['type'] != 'sama' else r['aksharas'][0]})" for r in chunk))
    L.append("""
## 3. Part B — corrections to the table itself

Check §1 against Vṛttaratnākara (Kedārabhaṭṭa), Chandomañjarī (Gaṅgādāsa), Śrutabodha and Piṅgala's
Chandaḥsūtra with commentary. Report only real disagreements (wrong lakṣaṇa, wrong akṣara count, wrong or
missing yati, wrong or missing name, two names that are really one metre or one name that covers two).
Specific questions we already have:

1. The 14 indravajrā/upendravajrā upajāti names. Our table follows the prastāra order (first pāda changes
   fastest, I before U): 2 UIII कीर्ति, 3 IUII वाणी, 4 UUII माला, 5 IIUI शाला, 6 UIUI हंसी, 7 IUUI जाया,
   8 UUUI माया, 9 IIIU बाला, 10 UIIU आर्द्रा, 11 IUIU भद्रा, 12 UUIU प्रेमा, 13 IIUU रामा, 14 UIUU ऋद्धि,
   15 IUUU बुद्धि. The source table had ऋद्धि duplicated as IUII; we set it to UIUU by elimination.
   Confirm each name↔pattern from the Vṛttaratnākara commentary (tālavyādi mnemonic), especially
   ऋद्धि, and whether जाया/माया are the right way round.
2. Yati positions whose sum is not the pāda length: ऋषभगजविलसित and मणिमाला. Give the correct yati.
3. Any sama vṛtta in §1 whose L/G string you know to be wrong.

Item shape:
```
{"vrutta": "<id>", "field": "lakshana" | "yati" | "name" | "akshara_sankhya" | "merge" | "split",
 "current": "<what §1 says>", "proposed": "<correct value>", "authority": "text chapter.verse", "note": "", "confidence": 0.0-1.0}
```

## 4. Part C — verdicts on verses the engine could not name
""")
    L.append(f"""{len(unres)} verses from our corpus (Bhagavad Gītā, Sumadhva Vijaya, Rāghavendra Vijaya, Tīrthaprabandha,
Dvādaśa Stotra, Viṣṇu Sahasranāma, …) that the engine returns as अज्ञातम्, each with our own L/G scan and
pāda syllable counts. `reason` is the engine's guess at why. For each, decide:

* `"verdict": "metre"` — the verse is metrically fine and the metre is X (give `chandas`, and `scan` if our
  scan is wrong); include metres missing from §1 (then also add a Part D item);
* `"verdict": "text_defect"` — a typo / missing or extra akṣara / wrong line split; give `corrected_text`
  (full verse, four pādas) and `chandas`;
* `"verdict": "matra"` — an āryā-family or other mātrā metre (give `chandas` and mātrā per pāda);
* `"verdict": "prose"` — not a verse (colophon, gadya, mantra);
* `"verdict": "unsure"`.

Item shape:
```
{{"id": "<id below>", "verdict": "metre" | "text_defect" | "matra" | "prose" | "unsure", "chandas": "<name or null>",
 "corrected_text": "<full verse or null>", "scan": ["…"] | null, "note": "<one line>", "confidence": 0.0-1.0}}
```
""")
    for i in range(0, len(unres), batch):
        L.append(f"\n### Part C batch {i // batch + 1} (items {i + 1}–{min(i + batch, len(unres))})\n")
        for u in unres[i:i + batch]:
            near = f"; nearest: {', '.join(u['near'])}" if u["near"] else ""
            text = u["text"].replace("\n", " / ")
            L.append(f"* `{u['id']}` ({u['work']}) — {text}\n  scan `{u['scan']}` syllables {u['syllables']}; {u['reason']}{near}")
    L.append("""

## 5. Part D — metres missing from §1

List metres used in Mādhva kāvya and stotra literature (Sumadhva Vijaya, Rāghavendra Vijaya, Madhva's
Dvādaśa Stotra and other stotras, Vādirāja, Vyāsatīrtha, Jagannāthadāsa's Sanskrit works) or in standard
prosody manuals that are **not** in §1. Each with lakṣaṇa, gaṇa, akṣara count, yati, an authority, and one
genuine example verse (same rules as Part A). Skip anything already in §1 under another name — say so
in Part B instead.

Item shape:
```
{"vrutta": "<Devanagari name>", "type": "sama" | "ardhasama" | "vishama" | "matra", "gana": "…",
 "padas": ["L/G pāda1", "…"], "aksharas": [n, n, n, n], "yati": [..], "authority": "text chapter.verse",
 "example": {"text": "…", "source": "…", "scan": ["…"]}, "confidence": 0.0-1.0}
```

## 6. What happens to your answer

`tools/chandas/apply_gemini_chandas.py` re-scans every example with the engine and keeps only examples whose
engine result names the vṛtta you claimed; accepted examples become the engine's regression suite
(`tests/fixtures/chandas_examples.json`) and the `examples` field of the public metre database. Parts B, C, D
go into a human review report — nothing you say changes a lakṣaṇa or a grantha text without a person
checking the cited authority. So: cite precisely, scan honestly, and prefer `null` to a guess.
""")
    OUT.write_text("\n".join(L), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(rows)} vṛttas, {len(missing)} without example, {len(unres)} unresolved verses, {OUT.stat().st_size // 1024} KB")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=40)
    build(ap.parse_args().batch)
