#!/usr/bin/env python3
"""Upaniṣad-bhāṣya ṭippaṇī volumes (Viśvamadhva Mahāpariṣat / Uttarādi Maṭha editions) + Tantrasārasaṅgraha:
hybrid OCR → labelled commentary blocks → comparison with the DGE text already imported from dvaitavedanta.in →
phone-sized Gemini verification prompts.

    python3 tools/upanishad_tippani/build_verify.py --work <scratch/upa> [--books kena,mandukya] [--out <dir>]

Per book (see BOOKS): Vision page text (from the ocr-staging branch JSON), Tesseract TSV lines (local run), the
book's own commentary-label convention ("वे.श्रुत्यर्थः-", "अ.सं.-" … at line start) → blocks. Every block is
looked up in ALL DGE layers of that work by 8-char shingles (calibrated on Māṇḍūkya: texts DGE has sit at 0.4–0.9,
texts it lacks at ≈0.1): coverage ≥ 0.7 = already in DGE, 0.25–0.7 = partial (OCR noise on either side, variant, or a
DGE gap inside the block), < 0.25 = NEW (not in DGE — usually one of
the commentaries the dvaitavedanta.in import lacks). Prompts: LABELS (map abbreviations → commentators),
NEW_nn (clean the OCR of new blocks: Vision vs Tesseract), DIFF_nn (word differences in partial blocks)."""
import argparse, csv, difflib, json, os, re, sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DV = ROOT / "dge/data/darshana/vedanta/dvaita/DvaitaVedantaIn/upanishad_prasthana"
BOOKS = {
    "kena":       {"vision": ["kena_upanishad_bhashya_tippani"],       "dge": DV / "kenopanishad_bhashya",           "title": "तलवकार (केन) उपनिषद्भाष्यम् — 8 व्याख्याः"},
    "isha":       {"vision": ["isha_upanishad_bhashya_tippani"],       "dge": DV / "ishavasyopanishad_bhashya",      "title": "ईशावास्योपनिषद्भाष्यम् — 13 व्याख्याः"},
    "katha":      {"vision": ["katha_upanishad_bhashya_tippani"],      "dge": DV / "kathopanishad_bhashya",          "title": "काठकोपनिषद्भाष्यम् — 6 व्याख्याः"},
    "mandukya":   {"vision": ["mandukya_upanishad_bhashya_tippani"],   "dge": DV / "mandukyopanishadbhashyam",       "title": "माण्डूक्योपनिषद्भाष्यम् — 7 व्याख्याः"},
    "mundaka":    {"vision": ["mundaka_upanishad_bhashya_tippani"],    "dge": DV / "mundakopanishadbhashyam",        "title": "आथर्वण (मुण्डक) उपनिषद्भाष्यम् — 12 व्याख्याः"},
    "prashna":    {"vision": ["prashna_upanishad_bhashya_tippani"],    "dge": DV / "shatprashnopanishadbhashyam",    "title": "षट्प्रश्नोपनिषद्भाष्यम् — 13 व्याख्याः"},
    "taittiriya": {"vision": ["taittiriya_upanishad_bhashya_tippani"], "dge": DV / "taittiriyopanishad_bhashya",     "title": "तैत्तिरीयोपनिषद्भाष्यम् — 6 टिप्पण्यः"},
    "tantrasara": {"vision": ["tantrasara_sangraha_tippani_a", "tantrasara_sangraha_tippani_b"],
                   "dge": [ROOT / "dge/data/darshana/vedanta/dvaita/Anandamakaranda/achara_and_ancillary_granthas/tantrasara_sangraha",
                           ROOT / "dge/data/DvaitaVedanta/SarvaMula/achara_granthas/tantrasara"],
                   "title": "तन्त्रसारसङ्ग्रहः (2017, प्रह्लादाचार्य जोशी) — 4 टिप्पण्यः"},
}
LABEL = re.compile(r"^\s*((?:[ऀ-ॿ]{1,7}\.){1,3}(?:[ऀ-ॿ]{1,12})?[ः:]?)\s*[-–—:]+\s*")
HEADER = re.compile(r"^\s*[\d०-९]{1,4}\s*$|^\s*[ऀ-ॿ ]{4,40}[\d०-९]{0,4}\s*$")   # page number / running title


def dev(s): return re.sub(r"[^ऀ-ॿ]", "", s or "")
def ratio(a, b): return difflib.SequenceMatcher(None, dev(a), dev(b), autojunk=False).ratio()


def tess_lines(tsv):
    if not os.path.exists(tsv): return []
    rows = list(csv.DictReader(open(tsv, encoding="utf-8", errors="ignore"), delimiter="\t", quoting=csv.QUOTE_NONE))
    lines = {}
    for r in rows:
        if r.get("level") != "5" or not (r.get("text") or "").strip(): continue
        k = (int(r["block_num"]), int(r["par_num"]), int(r["line_num"]))
        l = lines.setdefault(k, {"top": 10 ** 9, "words": []}); l["top"] = min(l["top"], int(r["top"])); l["words"].append(r["text"])
    return [" ".join(lines[k]["words"]) for k in sorted(lines, key=lambda k: lines[k]["top"])]


def align(vlines, tlines):
    """Vision line → best Tesseract line (monotone window)."""
    out, j = [], 0
    for v in vlines:
        best, bi = 0.0, None
        for i in range(max(0, j - 2), min(len(tlines), j + 6)):
            r = ratio(v, tlines[i])
            if r > best: best, bi = r, i
        if bi is not None and best >= 0.4:
            out.append((v, tlines[bi], round(best, 2))); j = bi + 1
        else:
            out.append((v, None, 0.0))
    return out


def load_vision(work, book):
    pages = {}
    for slug in BOOKS[book]["vision"]:
        for f in sorted(Path(work).glob(f"{book}/vision/*.json")):
            for p in json.load(open(f, encoding="utf-8"))["pages"]: pages[p["page"]] = p["text"]
    return pages


HEADING_KW = re.compile(r"टीका|टिप्पण|प्रकाशिका|खण्डार्थ|भाष्यम्|उपनिषत्|विवृति|रत्नावलि|विरचित|व्याख्या|श्रुत्यर्थ|दीपिका|पञ्चिका|विवरण|तात्पर्य|मूलम्|मन्त्राः|श्लोकाः|सङ्ग्रह|पदार्थ")


def is_heading(line):
    s = line.strip()
    return 3 <= len(dev(s)) <= 48 and not re.search(r"[।॥]", s) and bool(HEADING_KW.search(s)) and not re.search(r"\bइति\b", s)


def blocks_of(work, book, chunk_chars=700):
    pages = load_vision(work, book)
    # running titles: short lines that recur on many pages (the work title / "व्याख्यासप्तकोपेतम्" header)
    freq = Counter()
    for t in pages.values():
        for l in {x.strip() for x in t.split("\n")[:3] if x.strip()}: freq[dev(l)] += 1
    running = {k for k, n in freq.items() if n >= max(8, len(pages) // 12) and 3 <= len(k) <= 40}
    blocks, cur = [], None

    def new_block(pno, label):
        b = {"book": book, "page": pno, "label": label, "vision": [], "tess": [], "agree": []}; blocks.append(b); return b

    for pno in sorted(pages):
        vl = [l for l in pages[pno].split("\n") if l.strip()]
        tl = tess_lines(f"{work}/{book}/tess/p{pno:04d}.tsv")
        head = []
        while vl and len(head) < 3 and (re.fullmatch(r"\s*[\d०-९]{1,4}\s*", vl[0]) or dev(vl[0]) in running): head.append(vl.pop(0))
        for v, t, r in align(vl, tl):
            m = LABEL.match(v)
            if m:
                cur = new_block(pno, m.group(1).replace(":", "ः")); v = v[m.end():]
            elif is_heading(v):
                cur = new_block(pno, "§ " + re.sub(r"\s+", " ", v.strip())); continue
            if cur is None: cur = new_block(pno, "(unlabelled)")
            # keep blocks chat-sized: start a continuation block at a danda boundary once it grows past chunk_chars
            if sum(len(x) for x in cur["vision"]) > chunk_chars and re.search(r"[।॥]\s*$", cur["vision"][-1] if cur["vision"] else ""):
                cur = new_block(pno, cur["label"] + " (cont.)" if not cur["label"].endswith("(cont.)") else cur["label"])
            cur["vision"].append(v); cur["tess"].append(t or ""); cur["agree"].append(r)
    for i, b in enumerate(blocks):
        b["id"] = f"{book.upper()}_B{i + 1:04d}"
        b["vision_text"] = " ".join(b.pop("vision")); b["tess_text"] = " ".join(x for x in b.pop("tess") if x)
        b["agreement"] = round(sum(b["agree"]) / len(b["agree"]), 2) if b["agree"] else 0.0; b.pop("agree")
    return [b for b in blocks if dev(b["vision_text"])]


def dge_units(book):
    dirs = BOOKS[book]["dge"]; dirs = dirs if isinstance(dirs, list) else [dirs]
    units = []
    for d in dirs:
        for f in sorted(Path(d).rglob("data.json")):
            layer = f.parent.name if f.parent != Path(d) else Path(d).name
            for it in json.load(open(f, encoding="utf-8")).get("items", []):
                if it.get("sanskrit_text"): units.append({"layer": layer, "id": it.get("id"), "text": it["sanskrit_text"]})
    return units


def shingles(t, n=8):
    d = dev(t); return {d[i:i + n] for i in range(0, max(0, len(d) - n + 1), 2)}


def match(blocks, units):
    idx = defaultdict(set)
    for ui, u in enumerate(units):
        for s in shingles(u["text"]): idx[s].add(ui)
    for b in blocks:
        sh = shingles(b["vision_text"])
        if len(sh) < 4: b["match"] = {"class": "tiny", "coverage": 0.0}; continue
        votes = Counter()
        for s in sh:
            for ui in idx.get(s, ()): votes[ui] += 1
        if not votes: b["match"] = {"class": "new", "coverage": 0.0}; continue
        ui, c = votes.most_common(1)[0]; cov = round(c / len(sh), 2)
        b["match"] = {"class": "matched" if cov >= 0.7 else "partial" if cov >= 0.25 else "new", "coverage": cov,
                      "layer": units[ui]["layer"], "unit_id": units[ui]["id"]}
    return blocks


def word_diffs(a, b):
    wa, wb = [w for w in re.split(r"\s+", a) if dev(w)], [w for w in re.split(r"\s+", b) if dev(w)]
    sm = difflib.SequenceMatcher(None, wa, wb, autojunk=False); out = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal": continue
        pa, pb = " ".join(wa[i1:i2]), " ".join(wb[j1:j2])
        if pa and pb and ratio(pa, pb) >= 0.8: continue
        out.append({"print": pa or None, "dge": pb or None, "context": " ".join(wb[max(0, j1 - 2):j1] + ["【" + (pb or "∅") + "】"] + wb[j2:j2 + 2])})
    return out


HEAD = ("You are helping verify the OCR of a printed Sanskrit book against a digital text the library already has. "
        "This message is self-contained. Task tag: {pack}.\nBOOK: {title}\n\n")
REPLY = "REPLY WITH JSON ONLY — no prose, no code fences. Start with {{ and end with }}. Shape:\n"


def prompts(book, blocks, units, outdir, per_new=8, per_diff=20):
    files = []; title = BOOKS[book]["title"]; layers = sorted({u["layer"] for u in units})
    labs = Counter(b["label"] for b in blocks)
    # LABELS
    pack = f"UP-{book.upper()}-LABELS"
    body = HEAD.format(pack=pack, title=title) + ("The print introduces each commentary with an abbreviation at the start of a line (e.g. 'वे.श्रुत्यर्थः-'). "
        "Map EVERY abbreviation below to the commentator and the work's name, using the front-matter list of commentaries for this book that you know "
        "(Viśvamadhva Mahāpariṣat / Uttarādi Maṭha edition). OCR mangles some abbreviations — group variants of the same label. "
        f"The library already has these layers for this work: {', '.join(layers)}. Say which layer each label corresponds to, or 'NEW' if none.\n\n")
    body += "LABELS (abbreviation | occurrences | first words of a sample block):\n"
    for lab, n in labs.most_common(40):
        smp = next((b["vision_text"][:90] for b in blocks if b["label"] == lab), "")
        body += f"- {lab} | {n} | {smp}\n"
    body += ("\n" + REPLY + '{"pack": "' + pack + '", "items": [ {"label": "<abbreviation exactly>", "same_as": "<canonical label or null>", '
             '"commentator": "<name>", "work": "<title of the commentary>", "dge_layer": "<layer name or NEW>", "confidence": 0.0-1.0} ]}')
    files.append((f"{book}/LABELS.txt", body))
    # NEW blocks
    new = sorted([b for b in blocks if b["match"]["class"] == "new" and len(dev(b["vision_text"])) >= 40 and (b["agreement"] < 0.8)],
                 key=lambda b: (re.sub(r" \(cont\.\)", "", b["label"]), b["page"]))
    nn = -(-len(new) // per_new) if new else 0
    for k in range(nn):
        chunk = new[k * per_new:(k + 1) * per_new]; pack = f"UP-{book.upper()}-NEW-{k + 1:02d}"
        body = HEAD.format(pack=pack, title=title) + ("These passages are in the print but NOT in the library's digital text. Two OCR readings are given "
            "(Vision = usually better; Tesseract = second opinion). Produce the clean Devanagari text of each passage: fix OCR errors, keep the "
            "printed wording, keep dandas, drop running headers/page numbers, do not add or omit words. Say who the commentator is (from the label).\n\n")
        for b in chunk:
            body += f"### {b['id']} (page {b['page']}, label {b['label']})\nVISION: {b['vision_text']}\nTESSERACT: {b['tess_text'] or '(none)'}\n\n"
        body += (REPLY + '{"pack": "' + pack + '", "items": [ {"id": "<block id>", "clean_text": "<corrected Devanagari>", "commentator": "<name or null>", '
                 '"kind": "bhashya" | "mula" | "tika" | "kannada" | "front_matter" | "other", "confidence": 0.0-1.0} ]}\n'
                 f"One object per block ({len(chunk)}).")
        files.append((f"{book}/NEW_{k + 1:02d}_of_{nn:02d}.txt", body))
    # DIFF items from partial blocks
    by_id = {(u["layer"], u["id"]): u for u in units}
    items = []
    for b in blocks:
        if b["match"]["class"] != "partial": continue
        u = by_id.get((b["match"]["layer"], b["match"]["unit_id"]))
        if not u: continue
        for d in word_diffs(b["vision_text"], u["text"])[:6]:
            items.append({"id": b["id"], "page": b["page"], "label": b["label"], "dge_layer": u["layer"], **d})
    nd = -(-len(items) // per_diff) if items else 0
    for k in range(nd):
        chunk = items[k * per_diff:(k + 1) * per_diff]; pack = f"UP-{book.upper()}-DIFF-{k + 1:02d}"
        body = HEAD.format(pack=pack, title=title) + ("Single word differences between the PRINT (Vision OCR) and the library's DIGITAL text (dge), "
            "two words of context, the differing stretch inside 【】 (∅ = nothing there). Decide per item: 'dge' (OCR noise or page furniture; digital "
            "text is right), 'printed' (the print's reading is right and the digital text is wrong or missing it — give the correct words), "
            "'unsure'.\n\nITEMS:\n") + json.dumps(chunk, ensure_ascii=False, indent=0)
        body += ("\n\n" + REPLY + '{"pack": "' + pack + '", "items": [ {"id": "<block id>", "print": "<print word(s)>", "decision": "dge" | "printed" | "unsure", '
                 '"correct": "<words to use if printed>", "note": "one line"} ]}')
        files.append((f"{book}/DIFF_{k + 1:02d}_of_{nd:02d}.txt", body))
    for name, body in files:
        p = Path(outdir) / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(body, encoding="utf-8")
    return files


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--work", required=True); ap.add_argument("--books", default=",".join(BOOKS))
    ap.add_argument("--out", default=str(ROOT / "dge/data/ocr_staging/upanishad_tippani")); a = ap.parse_args()
    for book in a.books.split(","):
        if not list(Path(a.work).glob(f"{book}/vision/*.json")): print(f"{book}: no Vision pages yet — skipped"); continue
        units = dge_units(book); blocks = match(blocks_of(a.work, book), units)
        cls = Counter(b["match"]["class"] for b in blocks); labs = Counter(b["label"] for b in blocks)
        out = Path(a.out) / book; out.mkdir(parents=True, exist_ok=True)
        json.dump({"book": book, "title": BOOKS[book]["title"], "pages": max(b["page"] for b in blocks), "blocks": blocks,
                   "summary": {"classes": dict(cls), "labels": labs.most_common(30), "dge_layers": sorted({u["layer"] for u in units}), "dge_units": len(units)}},
                  open(out / "blocks.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        files = prompts(book, blocks, units, Path(a.out) / "prompts")
        print(f"{book}: {len(blocks)} blocks {dict(cls)}; labels {len(labs)}; prompts {len(files)}")


if __name__ == "__main__":
    main()
