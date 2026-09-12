#!/usr/bin/env python3
"""Stage B — build the Bhāgavata Sāroddhāra grantha from merged OCR pages.

Reads <work>/pages_merged.json (tools/saroddhara/ocr_merge.py) and the Vision page text, and writes:
  data/bhagavata_saroddhara/
      mula/data.json                 366 Bhāgavata verses selected by Viṣṇutīrtha (one item per verse; category = prakaraṇa)
      tika_vishnutirtha/data.json    the svopajña commentary, one item per verse (same ids → layer-stitch)
      tika_tippani/data.json         footnotes, one item per verse that has any (tika_* so layer-stitch joins it)
      tika_sara_sangraha_kannada/data.json the Kannada prakaraṇa summaries + front matter (id = first verse of the prakaraṇa)
      parishishta/data.json          the appendix verses
  <work>/verify_input/verify_queue.json + crops/   what a human (or their local Gemini) must check
  <work>/build_report.json            counts, verification stats, every failure
Every verse is checked against the Madhva Bhāgavata already in DGE (purana/maha_purana/bhagavata_purana_madhva):
exact/near matches take the DGE mūla text as canonical (OCR kept in `ocr`), mismatches go to the queue.
Corrections verified offline are applied by tools/saroddhara/apply_verified.py; nothing calls Gemini here."""
import argparse, difflib, glob, json, os, re, sys, datetime
from pathlib import Path
from collections import defaultdict, Counter

ROOT = Path(__file__).resolve().parents[2]
DEV = str.maketrans("०१२३४५६७८९", "0123456789"); KAN = str.maketrans("೦೧೨೩೪೫೬೭೮೯", "0123456789")
OUT_REL = "data/bhagavata_saroddhara"
BHP_REL = "data/purana/maha_purana/bhagavata_purana_madhva"
RE_VERSE_END = re.compile(r"(?:॥|\|\||।।|\|)\s*([०-९]{1,3})\s*(?:॥|\|\||।।|\|)")
RE_HEADING = re.compile(r"(\S.{1,60}?प्रकरणम्)\s*[॥|]+\s*([०-९]{1,2})\s*[॥|]")
RE_FOOT = re.compile(r"^\s*([०-९]{1,2})\s*[\.।]\s+(\S.*)$")
MAIN_START, MAIN_END = 99, 440          # PDF pages of the Sanskrit body (heading of prakaraṇa 1 is on p.101; p.99–100 = maṅgala)
KAN_START, KAN_END = 27, 96             # ಸಾರೋದ್ಧಾರ ಸಾರಸಂಗ್ರಹ (30 summaries)
FRONT = [(7, 16, "ಮುನ್ನುಡಿ", "kn"), (17, 20, "प्रास्ताविकम्", "sa"), (21, 22, "प्रथमावृत्तेः प्रास्ताविकम्", "sa"), (22, 26, "श्रीविष्णुतीर्थचरितम्", "sa")]
# Printed index (PDF p.97–98, Vision reading, hand-checked): prakaraṇa → (first verse, last verse)
INDEX = {1: (1, 16), 2: (17, 30), 3: (31, 42), 4: (43, 56), 5: (57, 101), 6: (102, 111), 7: (112, 121), 8: (122, 132), 9: (133, 137), 10: (138, 146),
         11: (147, 171), 12: (172, 177), 13: (178, 184), 14: (185, 193), 15: (194, 196), 16: (197, 199), 17: (200, 208), 18: (209, 221), 19: (222, 236),
         20: (237, 313), 21: (314, 323), 22: (324, 331), 23: (332, 337), 24: (338, 343), 25: (344, 346), 26: (347, 347), 27: (348, 349), 28: (350, 350),
         29: (351, 361), 30: (362, 364), 31: (365, 367)}   # 31 = the three closing verses (365–367) after "इति गुरुदक्षिणाप्रकरणम्" (उपसंहारः)
PRAK_NAMES = {31: "उपसंहारः"}


def dev_only(s): return re.sub(r"[^ऀ-ॿ]", "", s or "")
def ratio(a, b):
    a, b = dev_only(a), dev_only(b)
    return difflib.SequenceMatcher(None, a, b).ratio() if a and b else 0.0
def clean(s):
    s = re.sub(r"[ \t]+", " ", s or "").replace("|", "।").replace("।।", "॥").strip()
    s = re.sub(r"\s*॥\s*", " ॥ ", s); s = re.sub(r"\s*।\s*", " । ", s)
    return re.sub(r"\s+", " ", s).strip(" ,")
def strip_num(s): return RE_VERSE_END.sub("॥", s).replace("॥ ॥", "॥").strip()


def load_bhp():
    idx = {}
    for f in sorted(glob.glob(str(ROOT / BHP_REL / "skandha_*" / "data.json"))):
        sk = int(re.search(r"skandha_(\d+)", f).group(1)); d = json.load(open(f, encoding="utf-8"))
        for it in d.get("items", []):
            ad = int(re.sub(r"\D", "", it.get("id", "0")) or 0)
            for sh in it.get("shlokas", []):
                nums = re.findall(r"\d+", str(sh.get("number") or ""))
                rng = range(int(nums[0]), int(nums[-1]) + 1) if nums else []
                for n in rng:          # "14-16" = one item spanning three verse numbers
                    idx[(sk, ad, n)] = {"text": sh.get("sanskrit_text", ""), "item_id": it.get("id"), "skandha": sk, "number": sh.get("number")}
    return idx


def bhp_match(bhp, ref, ocr_text):
    """Find the mūla verse for a printed reference; tolerate ±3 verse offset by picking the best textual match."""
    if not ref: return None, 0.0, None
    s, a, v = ref
    cands = [(k, bhp[k]) for k in ((s, a, v + d) for d in (0, -1, 1, -2, 2, -3, 3)) if k in bhp]
    if not cands: return None, 0.0, None
    best = max(cands, key=lambda kv: ratio(ocr_text, kv[1]["text"]))
    return best[0], round(ratio(ocr_text, best[1]["text"]), 3), best[1]


def line_stream(pages):
    """Flat, ordered list of body-region lines with their page/index/geometry (for partitioning + recovery)."""
    P = {p["page"]: p for p in pages}
    out = []
    for pg in range(MAIN_START, MAIN_END + 1):
        p = P.get(pg)
        if not p: continue
        for i, l in enumerate(p["lines"]):
            out.append(dict(l, page=pg, idx=i, key=(pg, i)))
    return out


def junk(t):
    return re.fullmatch(r"[\s,.'|।॥\-–—]*", t) or "Rarest" in t or re.fullmatch(r"[0-9. ]+", t.strip())


def ngram_index(bhp, n=5):
    idx = defaultdict(set)
    for k, v in bhp.items():
        d = dev_only(v["text"])
        for i in range(0, max(0, len(d) - n + 1), 2): idx[d[i:i + n]].add(k)
    return idx


def find_in_bhp(bhp, idx, text, n=5, min_ratio=0.8):
    d = dev_only(text)
    if len(d) < 24: return None, 0.0
    votes = Counter()
    for i in range(0, len(d) - n + 1, 2):
        for k in idx.get(d[i:i + n], ()): votes[k] += 1
    best = None; br = 0.0
    for k, c in votes.most_common(6):
        if c < 6: break
        r = ratio(text, bhp[k]["text"])
        if r > br: best, br = k, r
    return (best, round(br, 3)) if br >= min_ratio else (None, round(br, 3))


def walk_body(pages, bhp=None):
    """Sequential scan of the Sanskrit body → verse units with commentary/footnotes.
    Verse blocks come from the region tags; verses the tagger missed are recovered by matching 2-/4-line windows of
    body text against the Madhva Bhāgavata (bhp); body lines are then partitioned to the preceding verse."""
    stream = line_stream(pages)
    # prakaraṇa per line
    prak_no, prak_name, after_end = 0, "भागवतागतिप्रकरणम्", False
    for l in stream:
        t = l["text"]
        if l["region"] == "heading":
            m = RE_HEADING.search(t); n = int(m.group(2).translate(DEV))
            if after_end and n <= prak_no:          # closing repetition of the heading after "इति … ॥ N ॥" — not a new prakaraṇa
                l["region"] = "closing_heading"
            else:
                prak_no = n; prak_name = m.group(1).strip(" '॥|"); after_end = False
        elif l["region"] == "prakarana_end":
            after_end = True
            if prak_no >= 30: prak_no, prak_name = 31, PRAK_NAMES[31]
        l["prak"] = (prak_no, prak_name)
    # verse blocks from tags
    blocks = []   # {key_start, key_end, lines:[stream idx], ref line}
    i = 0
    while i < len(stream):
        l = stream[i]
        if l["region"] == "verse":
            j = i
            while j < len(stream) and stream[j]["region"] == "verse" and stream[j]["page"] == l["page"]: j += 1
            ref = stream[j] if j < len(stream) and stream[j]["region"] == "ref" else None
            blocks.append({"lines": list(range(i, j)), "ref": ref, "src": "tag"})
            i = j + (1 if ref else 0); continue
        if l["region"] == "ref" and not (blocks and blocks[-1]["ref"] is None and stream[blocks[-1]["lines"][-1]]["page"] >= l["page"] - 1 and not blocks[-1].get("ref_attached")):
            # ref without tagged verse lines: previous 2 body lines are the verse
            prev = [k for k in range(max(0, i - 2), i) if stream[k]["region"] == "body" and not junk(stream[k]["text"])]
            if prev: blocks.append({"lines": prev, "ref": l, "src": "ref_only"})
            i += 1; continue
        if l["region"] == "ref" and blocks and blocks[-1]["ref"] is None:
            blocks[-1]["ref"] = l; blocks[-1]["ref_attached"] = True
        i += 1
    # recovery: the commentary QUOTES Bhāgavata verses constantly, so a text match alone is not evidence. Only fill
    # the deficit the printed index shows for each prakaraṇa, preferring windows that carry a missing verse number.
    used = {k for b in blocks for k in b["lines"]}
    if bhp:
        idx = ngram_index(bhp)
        found = Counter(stream[b["lines"][0]]["prak"][0] for b in blocks)
        deficit = {p: (INDEX[p][1] - INDEX[p][0] + 1) - found.get(p, 0) for p in INDEX}
        body = [k for k, l in enumerate(stream) if l["region"] == "body" and k not in used and not junk(l["text"])]
        pos = {k: n for n, k in enumerate(body)}
        cands = []
        for k in body:
            t = stream[k]["text"].rstrip(); pk = stream[k]["prak"][0]
            if deficit.get(pk, 0) <= 0: continue
            m = RE_VERSE_END.search(t)
            if not (m or t.endswith("॥")): continue
            n = pos[k]
            for w in (2, 4):
                ks = body[max(0, n - w + 1):n + 1]
                if len(ks) < w or any(kk in used for kk in ks): continue
                if any(stream[kk]["page"] < stream[k]["page"] - 1 for kk in ks): continue
                txt = strip_num(" ".join(stream[kk]["text"] for kk in ks))
                key, r = find_in_bhp(bhp, idx, txt)
                if key:
                    num = int(m.group(1).translate(DEV)) if m else None
                    in_range = num is not None and INDEX[pk][0] <= num <= INDEX[pk][1]
                    cands.append((pk, (2 if in_range else 0) + r, ks, key, r, num)); break
        cands.sort(key=lambda c: -c[1])
        for pk, score, ks, key, r, num in cands:
            if deficit[pk] <= 0 or any(kk in used for kk in ks): continue
            blocks.append({"lines": ks, "ref": None, "src": "recovered", "bhp_key": key, "bhp_ratio": r, "marker_no": num}); used.update(ks); deficit[pk] -= 1
    blocks.sort(key=lambda b: b["lines"][0])
    # build verse units + partition body lines
    verses = []
    for b in blocks:
        ls = [stream[k] for k in b["lines"]]; ref = b["ref"]
        pg = ls[0]["page"]
        verses.append({"page": pg, "verse_lines": [l["text"] for l in ls], "line_keys": [l["key"] for l in ls], "ref": (ref or {}).get("ref") or (list(b["bhp_key"]) if b.get("bhp_key") else None),
                       "ref_range": (ref or {}).get("ref_range"), "ref_printed": bool(ref), "verse_no_printed": (ref or {}).get("verse_no") or b.get("marker_no"), "fnmark": (ref or {}).get("fnmark"),
                       "commentary": [], "footnotes": [], "prakarana_no": ls[0]["prak"][0], "prakarana": ls[0]["prak"][1], "intro": [],
                       "cls": [l["cls"] for l in ls] + ([ref["cls"]] if ref else []), "pages": [pg], "detected_by": b["src"], "recovered_ratio": b.get("bhp_ratio"),
                       "first_key": b["lines"][0], "last_key": (b["ref"]["key"] if ref and "key" in ref else ls[-1]["key"])})
    # partition: body lines between consecutive verse blocks → commentary of the earlier verse (before the first verse of a prakaraṇa → intro of that verse)
    vpos = [(v["first_key"], v) for v in verses]
    cur = None; heading_seen = False
    bounds = {}
    for v in verses:
        bounds[v["first_key"]] = v
    ends = {}
    for v in verses:
        for k in v["line_keys"]: ends[k] = v
    pending_intro = []
    for l in stream:
        if l["key"] in ends:
            if ends[l["key"]] is not cur: cur = ends[l["key"]]; cur["intro"].extend(pending_intro); pending_intro = []
            continue
        if l["region"] in ("header",) or junk(l["text"]) or l["region"] == "ref": continue
        if l["region"] == "heading": cur = None; pending_intro = []; continue
        if l["region"] == "closing_heading": continue
        if l["region"] == "prakarana_end": continue
        if l["region"] == "footnote": continue
        if l["region"] == "body":
            if cur is None: pending_intro.append(l["text"])
            else:
                cur["commentary"].append(l["text"])
                if l["page"] not in cur["pages"]: cur["pages"].append(l["page"])
    # footnotes
    pending_foot = defaultdict(list)
    for l in stream:
        if l["region"] != "footnote": continue
        m = RE_FOOT.match(l["text"])
        if m: pending_foot[l["page"]].append([int(m.group(1).translate(DEV)), m.group(2)])
        elif pending_foot[l["page"]] and not junk(l["text"]): pending_foot[l["page"]][-1][1] += " " + l["text"]
    by_page = defaultdict(list)
    for v in verses:
        for pg in v["pages"]: by_page[pg].append(v)
    for pg, fns in pending_foot.items():
        for k, txt in fns:
            tgt = next((v for v in by_page.get(pg, []) if v.get("fnmark") == k and v["page"] == pg), None); sure = bool(tgt)
            if not tgt:
                cands = by_page.get(pg, []); tgt = cands[-1] if cands else (verses[-1] if verses else None)
            if tgt: tgt["footnotes"].append({"n": k, "text": clean(txt), "page": pg, "attached_by": "marker" if sure else "page (unverified)"})
    return verses


def number_verses(verses):
    """Global verse numbers. Printed numbers (ref-line prefix or the verse's own end marker) are trusted only when
    they agree with their neighbours; an isolated deviation is an OCR digit error and is replaced by the sequence."""
    issues = []
    printed = []
    for v in verses:
        n = v.get("verse_no_printed")
        m = RE_VERSE_END.search(v["verse_lines"][-1]) if v["verse_lines"] else None
        n2 = int(m.group(1).translate(DEV)) if m else None
        printed.append(n or n2)
        v["_end_marker"] = n2
    N = len(verses)
    for i, v in enumerate(verses):
        p = printed[i]; prev = verses[i - 1]["n"] if i else 0
        if i and v["prakarana_no"] != verses[i - 1]["prakarana_no"] and v["prakarana_no"] in INDEX:
            exp_prev = INDEX[verses[i - 1]["prakarana_no"]][1] if verses[i - 1]["prakarana_no"] in INDEX else prev
            if prev != exp_prev: issues.append({"page": v["page"], "prakarana_end": verses[i - 1]["prakarana_no"], "counter": prev, "index_says": exp_prev, "why": "verse count of the previous prakaraṇa disagrees with the printed index"})
            prev = INDEX[v["prakarana_no"]][0] - 1          # anchor on the printed index
        nxt = next((printed[j] for j in range(i + 1, min(N, i + 3)) if printed[j]), None)
        if p == prev + 1: v["n"] = p; v["numbering"] = "printed"
        elif p is None:
            v["n"] = prev + 1; v["numbering"] = "sequence"
        elif nxt is not None and nxt == prev + 2:          # neighbours say this is prev+1 → printed digit misread
            v["n"] = prev + 1; v["numbering"] = f"sequence (printed {p} rejected)"; issues.append({"page": v["page"], "printed": p, "used": prev + 1, "why": "next verse is numbered prev+2"})
        elif nxt is not None and nxt == p + 1 and p > prev:  # a consistent jump → verses missing before this one
            v["n"] = p; v["numbering"] = "printed (gap before)"; issues.append({"page": v["page"], "printed": p, "expected": prev + 1, "why": f"{p - prev - 1} verse(s) not detected before this one"})
        elif p > prev and p - prev <= 6:
            v["n"] = p; v["numbering"] = "printed (gap before, unconfirmed)"; issues.append({"page": v["page"], "printed": p, "expected": prev + 1, "why": "gap, no confirming neighbour"})
        else:
            v["n"] = prev + 1; v["numbering"] = f"sequence (printed {p} rejected)"; issues.append({"page": v["page"], "printed": p, "used": prev + 1, "why": "printed number out of range"})
        v.pop("_end_marker", None)
    return issues


def crop(png_dir, pg, y0, y1, out, W):
    try:
        from PIL import Image
        im = Image.open(f"{png_dir}/{pg:03d}.png"); im.crop((0, max(0, y0 - 12), W, min(im.height, y1 + 12))).save(out)
        return str(out)
    except Exception as e:
        return None


def write_viewer(vq, queue):
    """verify_queue.html — offline page next to the JSON: shows crop + both OCR readings + an answer box, exports answers.json."""
    import html as H
    rows = []
    for q in queue:
        img = f"<img src='{H.escape(q['crop'])}' style='max-width:100%;border:1px solid #ccc'>" if q.get("crop") else ""
        fields = "".join(f"<div><b>{H.escape(k)}</b>: <span class='dev'>{H.escape(str(v))}</span></div>" for k, v in q.items() if k in ("page", "prakarana", "printed_ref", "status", "ocr_vision", "ocr_tesseract", "dge_mula_candidate", "similarity", "footnote", "pages_of_prakarana", "numbering"))
        rows.append(f"<section id='{H.escape(q['id'])}' data-id='{H.escape(q['id'])}'><h3>{H.escape(q['id'])} <small>{H.escape(q['kind'])}</small></h3>{img}{fields}<div class='q'>{H.escape(q['question'])}</div><textarea placeholder='verified text / answer'></textarea><label><input type='checkbox' class='ok'> OCR (Vision) is already correct</label></section>")
    page = ("<!doctype html><meta charset='utf-8'><title>Bhāgavata Sāroddhāra — OCR verification</title><style>body{font-family:system-ui;max-width:1000px;margin:auto;padding:12px}section{border:1px solid #ddd;border-radius:8px;padding:10px;margin:10px 0}.dev{font-family:'Noto Sans Devanagari',serif;font-size:16px}.q{color:#8f3a1d;margin:6px 0}textarea{width:100%;min-height:60px;font-size:16px}h3 small{color:#888;font-weight:normal}#bar{position:sticky;top:0;background:#fff;padding:8px;border-bottom:1px solid #ddd}</style>"
            f"<div id='bar'><b>{len(queue)} items</b> · fill the boxes (or tick 'already correct'), then <button onclick='exp()'>Export answers.json</button> and put the file in verify_output/</div>" + "".join(rows) +
            "<script>function exp(){const out={};document.querySelectorAll('section').forEach(s=>{const t=s.querySelector('textarea').value.trim();const ok=s.querySelector('.ok').checked;if(t||ok)out[s.dataset.id]={verified_text:t||null,accept_vision:ok}});const b=new Blob([JSON.stringify(out,null,1)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='answers.json';a.click()}</script>")
    (vq / "verify_queue.html").write_text(page, encoding="utf-8")


def register(layers):
    """library.json entries, taxonomy node and _meta.json anchor — idempotent."""
    lib_p = ROOT / "data/library.json"; tax_p = ROOT / "data/taxonomy.json"
    lib = json.loads(lib_p.read_text(encoding="utf-8")); tax = json.loads(tax_p.read_text(encoding="utf-8"))
    src = {"source": "Bhāgavata Sāroddhāra with svopajña ṭīkā, Acharya Vidyadhishthanam (Bengaluru) edition — scanned PDF supplied by the project lead; OCR: Google Vision + Tesseract, verified against the Madhva Bhāgavata in DGE",
           "licence": "Text of Śrī Viṣṇutīrtha (18th c.) is public domain; Kannada summaries/front matter are the edition's — editorial material, credited to the publisher"}
    keep = {f"{OUT_REL}/{sub}/data.json" for sub, _, _, _ in layers}
    lib["granthas"] = [g for g in lib["granthas"] if not (g["path"].startswith(OUT_REL + "/") and g["path"] not in keep)]
    gs = lib["granthas"]; existing = {g["path"]: i for i, g in enumerate(gs)}
    pos = max((i for i, g in enumerate(gs) if "/later_acharyas/" in g["path"]), default=len(gs) - 1) + 1
    for sub, d, title, author in layers:
        path = f"{OUT_REL}/{sub}/data.json"
        entry = {"path": path, "populated": bool(d["items"]), "title": f"भागवतसारोद्धारः — {title}", "addedAt": datetime.date.today().isoformat(), "source": src, "facets": {"default_author": author}}
        if path in existing: gs[existing[path]] = entry
        else: gs.insert(pos, entry); pos += 1
    lib_p.write_text(json.dumps(lib, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    node = tax["darshana"]["vedanta"]["dvaita"]["DvaitaVedanta"].setdefault("later_acharyas", {})
    node["bhagavata_saroddhara"] = {"_default_author": "Sri Vishnu Tirtha", "mula": {"_schema": "grantha_mula_text", "_default_author": "Maharshi Veda Vyasa"},
                                    "tika_vishnutirtha": {"_schema": "grantha_tika_text", "_default_author": "Sri Vishnu Tirtha"}, "tika_tippani": {"_schema": "grantha_tika_text"},
                                    "tika_sara_sangraha_kannada": {"_schema": "grantha_tika_text", "_default_author": "Editor (Kannada)"}, "parishishta": {"_schema": "grantha_mula_text"}, "upodghata": {"_schema": "grantha_mula_text"}}
    tax_p.write_text(json.dumps(tax, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    mp = ROOT / OUT_REL / "_meta.json"
    if not mp.exists():
        mp.write_text(json.dumps({"directory": "bhagavata_saroddhara", "description": "भागवतसारोद्धारः — Bhāgavata Sāroddhāra of Śrī Viṣṇutīrtha (Jayatīrtha, avadhūta) with his own ṭīkā, 30 prakaraṇas, 367 verses", "schema": "grantha_prakarana_text"}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True, help="scratch dir holding merged/pages_merged.json, vision/pages.json, hi/*.png")
    ap.add_argument("--write-data", action="store_true", help="write the data layers (otherwise only the report/queue)")
    a = ap.parse_args()
    W = Path(a.work)
    merged = json.load(open(W / "merged/pages_merged.json", encoding="utf-8"))["pages"]
    V = {p["page"]: p["text"] for p in json.load(open(W / "vision/pages.json", encoding="utf-8"))["pages"]}
    bhp = load_bhp()
    verses = walk_body(merged, bhp)
    for v in verses:                       # maṅgala verses (pp. 99–100) are verses 1–2 of prakaraṇa 1 in the printed index
        if v["prakarana_no"] == 0: v["prakarana_no"] = 1; v["prakarana"] = "भागवतागतिप्रकरणम्"
    issues = number_verses(verses)
    for v in verses:
        lo, hi = INDEX.get(v["prakarana_no"], (0, 10 ** 6))
        v["beyond_index"] = not (lo <= v["n"] <= hi)
    # ---- verification against the Madhva Bhāgavata
    queue = []; stats = Counter()
    vq = W / "verify_input"; (vq / "crops").mkdir(parents=True, exist_ok=True)
    Pm = {p["page"]: p for p in merged}
    ng = ngram_index(bhp)
    for v in verses:
        ocr = clean(" ".join(v["verse_lines"]))
        key, r, m = bhp_match(bhp, v["ref"], strip_num(ocr))
        v["ref_corrected"] = False
        if r < 0.85:                               # printed reference misread? search the whole Bhāgavata by text
            k2, r2 = find_in_bhp(bhp, ng, strip_num(ocr), min_ratio=0.85)
            if k2 and r2 > r:
                key, r, m = k2, r2, bhp[k2]; v["ref_corrected"] = bool(v["ref"]); v["ref_printed_value"] = v["ref"]; v["ref"] = list(k2)
        v["ocr_verse"] = ocr; v["bhp_key"] = key; v["bhp_sim"] = r
        if v.get("detected_by") == "recovered": v["status"] = "recovered_by_text"; v["text"] = m["text"] if m else strip_num(ocr) + " ॥"; stats["recovered_by_text"] += 1
        elif m and r >= 0.92: v["status"] = "mula_verified"; v["text"] = m["text"]; stats["mula_verified"] += 1
        elif m and r >= 0.75: v["status"] = "mula_near"; v["text"] = m["text"]; stats["mula_near"] += 1      # take DGE mūla, but a human must confirm the edition agrees
        elif v["ref"] and not m: v["status"] = "ref_not_in_dge"; v["text"] = strip_num(ocr) + " ॥"; stats["ref_not_in_dge"] += 1
        elif not v["ref"]: v["status"] = "no_ref"; v["text"] = strip_num(ocr) + " ॥"; stats["no_ref"] += 1
        else: v["status"] = "mismatch"; v["text"] = strip_num(ocr) + " ॥"; stats["mismatch"] += 1
        worst = min((c for c in v["cls"]), default="E")
        ctext = set(v["commentary"])
        com_cls = [l["cls"] for pg in v["pages"] for l in Pm[pg]["lines"] if l["region"] == "body" and l["text"] in ctext]
        v["commentary_cls"] = dict(Counter(com_cls))
        if v.get("beyond_index"): v["status"] = "extra_beyond_index"; stats["extra_beyond_index"] += 1
        if v.get("ref_corrected") and v["status"] == "mula_verified": v["status"] = "mula_verified_ref_corrected"; stats["mula_verified"] -= 1; stats["mula_verified_ref_corrected"] += 1
        need = v["status"] not in ("mula_verified",) or worst in ("C", "D", "E") or any(c in ("D", "E") for c in com_cls) or v.get("numbering") != "printed"
        if need:
            pg = v["page"]; ls = [l for l in Pm[pg]["lines"] if l["region"] in ("verse", "ref") and (l["text"] in v["verse_lines"] or l.get("ref") == v["ref"])]
            img = crop(W / "hi", pg, min(l["y"] for l in ls), max(l["y"] + l["h"] for l in ls), vq / "crops" / f"v{v['n']:03d}_p{pg}.png", Pm[pg]["W"]) if ls else None
            queue.append({"id": f"BS_V{v['n']:03d}", "kind": "verse", "page": pg, "prakarana": v["prakarana"], "printed_ref": v["ref"], "status": v["status"],
                          "ocr_vision": ocr, "ocr_tesseract": clean(" ".join(l["tess"] for l in ls if l["region"] == "verse")), "dge_mula_candidate": (m or {}).get("text"), "dge_key": key, "similarity": r,
                          "numbering": v.get("numbering"), "agreement": v["cls"], "crop": img and os.path.relpath(img, vq),
                          "question": ("This block was numbered beyond the printed index for its prakaraṇa — is it really a Sāroddhāra verse or a verse quoted inside the commentary?" if v.get("beyond_index") else "Does the printed verse match dge_mula_candidate? If the edition differs, give the exact printed text."),
                          "answer": {"verified_text": None, "note": None}})
        # commentary lines with weak agreement → queue per line (with page crop)
        for pg in v["pages"]:
            for l in Pm[pg]["lines"]:
                if l["region"] == "body" and l["text"] in ctext and l["cls"] in ("C", "D", "E"):
                    img = crop(W / "hi", pg, l["y"], l["y"] + l["h"], vq / "crops" / f"c{v['n']:03d}_p{pg}_y{l['y']}.png", Pm[pg]["W"])
                    queue.append({"id": f"BS_V{v['n']:03d}_C_p{pg}_y{l['y']}", "kind": "commentary_line", "page": pg, "verse": v["n"], "ocr_vision": l["vision"], "ocr_tesseract": l["tess"], "agreement": l["cls"], "similarity": l["sim"],
                                  "crop": img and os.path.relpath(img, vq), "question": "Read the crop; give the correct Devanagari line.", "answer": {"verified_text": None}})
        for fn in v["footnotes"]:
            if fn["attached_by"] != "marker":
                queue.append({"id": f"BS_V{v['n']:03d}_F{fn['n']}_p{fn['page']}", "kind": "footnote_attachment", "page": fn["page"], "verse": v["n"], "footnote": fn["text"][:200],
                              "question": "Which verse on this page does this footnote belong to? (attached by page position only)", "answer": {"verse": None}})
    have = {v["n"] for v in verses}
    for n in range(1, 368):
        if n in have: continue
        pk = next((p for p, (a, b) in INDEX.items() if a <= n <= b), None)
        pgs = sorted({v["page"] for v in verses if v["prakarana_no"] == pk})
        queue.append({"id": f"BS_V{n:03d}", "kind": "missing_verse", "prakarana_no": pk, "pages_of_prakarana": [min(pgs, default=None), max(pgs, default=None)],
                      "question": f"Verse {n} of the Sāroddhāra was not detected by OCR structure. Find it on the pages of prakaraṇa {pk} and give its text + Bhāgavata reference.",
                      "answer": {"verified_text": None, "bhagavata_ref": None, "page": None}})
    # ---- Kannada summaries + front matter
    summaries = []
    txt = "\n".join(V.get(pg, "") for pg in range(KAN_START, KAN_END + 1))
    txt = re.sub(r"^\s*[೦-೯0-9]+\s*$", "", txt, flags=re.M).replace("Rarest Archiver", "")
    parts = re.split(r"^\s*([0-9೦-೯]{1,2})\s*\.\s*(\S.{0,60}?ಪ್ರಕರಣ\S*)\s*$", txt, flags=re.M)
    for k in range(1, len(parts) - 2, 3):
        summaries.append({"n": int(parts[k].translate(KAN)), "title": parts[k + 1].strip(), "text": re.sub(r"\n{2,}", "\n", parts[k + 2]).strip()})
    front = []
    for s, e, title, lang in FRONT:
        t = "\n".join(V.get(pg, "") for pg in range(s, e + 1)); t = re.sub(r"^\s*[೦-೯0-9]+\s*$", "", t, flags=re.M).replace("Rarest Archiver", "").strip()
        front.append({"title": title, "lang": lang, "pages": [s, e], "text": t})
    # ---- appendix (परिशिष्टम्) as raw verse blocks
    app = []
    at = "\n".join(V.get(pg, "") for pg in range(441, 460)).replace("Rarest Archiver", "")
    for k, blk in enumerate(re.split(r"(?<=॥)\s*\n(?=\S)", at)):
        b = clean(blk.replace("\n", " "))
        if len(dev_only(b)) > 20: app.append(b)
    first_of = {}
    for v in verses: first_of.setdefault(v["prakarana_no"], v)
    # ---- data.json layers
    src = {"site": "Rarest Archiver scan of the Acharya Vidyadhishthanam (Bengaluru) edition", "pdf_pages": 459, "ocr": "Google Vision + Tesseract (san+kan), merged by tools/saroddhara/ocr_merge.py"}
    def base(schema, author, title, extra=None):
        d = {"schema": schema, "default_author": author, "title": title, "source": src["site"], "source_note": src["ocr"], "licence": "Text of Śrī Viṣṇutīrtha (18th c.), public domain; scan courtesy of the edition's publisher", "items": []}
        if extra: d.update(extra)
        return d
    mula = base("grantha_mula_text", "Maharshi Veda Vyasa (Bhāgavata verses selected by Sri Vishnu Tirtha)", "भागवतसारोद्धारः — मूलम् (श्लोकाः)")
    tika = base("grantha_tika_text", "Sri Vishnu Tirtha (Jayatirtha, avadhūta)", "भागवतसारोद्धारः — स्वोपज्ञटीका", {"tika_title": "स्वोपज्ञटीका — श्रीविष्णुतीर्थः"})
    tipp = base("grantha_tippani_text", "Editor (Acharya Vidyadhishthanam edition)", "भागवतसारोद्धारः — टिप्पणी")
    sara = base("grantha_tika_text", "Editor (Kannada)", "ಭಾಗವತಸಾರೋದ್ಧಾರ — ಸಾರಸಂಗ್ರಹ (ಕನ್ನಡ)", {"tika_title": "ಸಾರೋದ್ಧಾರ ಸಾರಸಂಗ್ರಹ — ಕನ್ನಡ ಪ್ರಕರಣಸಾರ", "language": "kn"})
    pari = base("grantha_mula_text", "Sri Vishnu Tirtha", "भागवतसारोद्धारः — परिशिष्टम्")
    for v in verses:
        vid = f"BS_P{v['prakarana_no']:02d}_V{v['n']:03d}"; v["id"] = vid
        ref = v["ref"]; refs = []
        if v["bhp_key"]:
            sk, ad, vn = v["bhp_key"]
            refs.append({"target": f"purana/maha_purana/bhagavata_purana_madhva/skandha_{sk:02d}", "unit_id": f"adhyaya_{ad:02d}", "note": f"cites Bhāgavata {sk}.{ad}.{vn}"})
        mula["items"].append({"id": vid, "reference": f"{v['prakarana']} · श्लोकः {v['n']}" + (f" · भा. {ref[0]}.{ref[1]}.{ref[2]}" if ref else ""),
                              "sanskrit_text": v["text"], "tags": ["verse", "bhagavata"], "notes": "", "references": refs, "audio": [], "category": v["prakarana"],
                              "prakarana_no": v["prakarana_no"], "verse_no": v["n"], "bhagavata_ref": ({"skandha": ref[0], "adhyaya": ref[1], "verse": v.get("ref_range") or str(ref[2])} if ref else None),
                              "verification": {"status": v["status"], "dge_similarity": v["bhp_sim"], "dge_key": v["bhp_key"], "numbering": v.get("numbering"), "detected_by": v.get("detected_by"), "ref_printed": v.get("ref_printed"), "printed_ref_as_read": v.get("ref_printed_value")},
                              "ocr": {"vision": v["ocr_verse"], "agreement": v["cls"]}, "breadcrumb": ["भागवतसारोद्धारः", v["prakarana"], str(v["n"])],
                              "source": {"pdf_page": v["page"]}})
        com = clean(" ".join(v["intro"] + v["commentary"])) if (v["intro"] or v["commentary"]) else ""
        if com:
            tika["items"].append({"id": vid, "reference": f"{v['prakarana']} · टीका · {v['n']}", "sanskrit_text": com, "tags": ["commentary"], "notes": ("प्रकरणोपोद्घातः सह" if v["intro"] else ""), "references": [], "audio": [],
                                  "category": v["prakarana"], "verse_no": v["n"], "tika_title": "स्वोपज्ञटीका", "ocr_agreement": v["commentary_cls"], "source": {"pdf_pages": v["pages"]}})
        if v["footnotes"]:
            tipp["items"].append({"id": vid, "reference": f"{v['prakarana']} · टिप्पणी · {v['n']}", "sanskrit_text": "\n".join(f"{f['n']}. {f['text']}" for f in v["footnotes"]), "tags": ["footnote"], "notes": "", "references": [], "audio": [],
                                  "category": v["prakarana"], "verse_no": v["n"], "tika_title": "टिप्पणी", "footnotes": v["footnotes"], "source": {"pdf_pages": sorted({f['page'] for f in v['footnotes']})}})
    for s in summaries:
        fv = first_of.get(s["n"])
        if not fv: continue
        sara["items"].append({"id": fv["id"], "reference": f"{s['n']}. {s['title']}", "sanskrit_text": s["text"], "tags": ["summary", "kannada"], "notes": "ಈ ಪ್ರಕರಣದ ಎಲ್ಲ ಶ್ಲೋಕಗಳಿಗೂ ಅನ್ವಯಿಸುವ ಸಾರಸಂಗ್ರಹ (ಮೊದಲ ಶ್ಲೋಕದಲ್ಲಿ ತೋರಿಸಲಾಗಿದೆ)", "references": [], "audio": [],
                              "category": fv["prakarana"], "prakarana_no": s["n"], "language": "kn", "tika_title": "ಸಾರಸಂಗ್ರಹ (ಕನ್ನಡ)", "source": {"pdf_pages": [KAN_START, KAN_END]}})
    upod = base("grantha_mula_text", "Editor / Sri Vishnu Tirtha (caritam)", "भागवतसारोद्धारः — उपोद्घातः (ಮುನ್ನುಡಿ, प्रास्ताविकम्, विष्णुतीर्थचरितम्)")
    for k, f in enumerate(front, 1):
        upod["items"].append({"id": f"BS_FRONT_{k:02d}", "reference": f["title"], "sanskrit_text": f["text"], "tags": ["front_matter", f["lang"]], "notes": "", "references": [], "audio": [], "category": "ಮುನ್ನುಡಿ / प्रास्ताविकम्", "language": f["lang"], "tika_title": "ಸಾರಸಂಗ್ರಹ (ಕನ್ನಡ)", "source": {"pdf_pages": f["pages"]}})
    for k, b in enumerate(app, 1):
        pari["items"].append({"id": f"BS_PARI_{k:03d}", "reference": f"परिशिष्टम् · {k}", "sanskrit_text": b, "tags": ["verse", "appendix"], "notes": "OCR (Vision), unverified", "references": [], "audio": [], "category": "परिशिष्टम्", "source": {"pdf_pages": [441, 459]}})
    report = {"built_at": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5, minutes=30))).strftime("%d %b %Y, %I:%M %p IST"),
              "verses": len(verses), "prakaranas": sorted({v["prakarana_no"] for v in verses}), "per_prakarana": dict(Counter(v["prakarana_no"] for v in verses)),
              "verification": dict(stats), "numbering_issues": issues, "commentary_items": len(tika["items"]), "footnote_items": len(tipp["items"]), "summaries": len(summaries), "front_matter": len(front), "appendix_blocks": len(app),
              "review_queue": len(queue), "queue_by_kind": dict(Counter(q["kind"] for q in queue)),
              "index_check": {str(p): {"expected": INDEX[p], "got": (min((v["n"] for v in verses if v["prakarana_no"] == p), default=None), max((v["n"] for v in verses if v["prakarana_no"] == p), default=None)), "count": sum(1 for v in verses if v["prakarana_no"] == p), "expected_count": INDEX[p][1] - INDEX[p][0] + 1} for p in INDEX},
              "missing_verse_numbers": [n for n in range(1, 368) if n not in {v["n"] for v in verses}], "detected_by": dict(Counter(v.get("detected_by") for v in verses))}
    json.dump({"_readme": "Verification queue for the Bhāgavata Sāroddhāra OCR. Fill answer.* (or edit verified_text) and drop the file into verify_output/; apply with tools/saroddhara/apply_verified.py. Crops are page strips at 300 dpi.",
               "instructions_for_gemini": "For each item: look at the crop image and the two OCR readings; return the exact Devanagari text printed in the image. For 'verse' items also say whether dge_mula_candidate is the same verse (ignoring sandhi/orthographic variants).",
               "items": queue}, open(vq / "verify_queue.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(report, open(W / "build_report.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    write_viewer(vq, queue)
    if a.write_data:
        layers = (("mula", mula, "Mula (Bhāgavata verses)", "Maharshi Veda Vyasa"), ("tika_vishnutirtha", tika, "Svopajña Ṭīkā — Sri Vishnu Tirtha", "Sri Vishnu Tirtha"),
                  ("tika_tippani", tipp, "Tippani (editor's footnotes)", "Editor"), ("tika_sara_sangraha_kannada", sara, "ಸಾರಸಂಗ್ರಹ (Kannada prakaraṇa summaries + front matter)", "Editor (Kannada)"),
                  ("parishishta", pari, "Parishishta (appendix)", "Sri Vishnu Tirtha"), ("upodghata", upod, "Upodghāta (Kannada preface, prāstāvika, Viṣṇutīrtha-caritam)", "Editor"))
        for sub, d, _, _ in layers:
            p = ROOT / OUT_REL / sub; p.mkdir(parents=True, exist_ok=True)
            json.dump(d, open(p / "data.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        register(layers)
    print(json.dumps(report, ensure_ascii=False, indent=1)[:3000])


if __name__ == "__main__":
    main()
