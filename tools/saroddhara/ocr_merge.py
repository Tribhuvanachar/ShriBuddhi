#!/usr/bin/env python3
"""Stage A — merge the two OCR readings of the Bhāgavata Sāroddhāra scan into geometry-aware page lines.

Inputs (paths via env/args): the Vision per-page JSON (from .github/workflows/ocr-vision-pages.yml, branch
ocr-staging/bhagavata_saroddhara), Tesseract TSVs (san+kan, 300 dpi, one per page) and the 300-dpi page PNGs.
For every page: detect the footnote rule (long horizontal dark run in the lower half), take Tesseract's line
boxes as the geometry, align each Vision line to its best-matching Tesseract line (Vision is the better reader,
Tesseract the better segmenter), tag regions (header / body / footnote / verse / ref / heading) and score
agreement between the two engines (classes A–E as in dge/convert/review-classifier.js).
Output: <out>/pages_merged.json — the single input of build_saroddhara.py."""
import csv, json, os, re, sys, difflib
from pathlib import Path
import numpy as np
from PIL import Image

DEV = str.maketrans("०१२३४५६७८९", "0123456789")
RE_VERSE_END = re.compile(r"(?:॥|\|\||।।|\|)\s*([०-९]{1,3})\s*(?:॥|\|\||।।|\|)")
RE_REF = re.compile(r"[।|]?\s*([०-९]{1,2})\s*[।|]\s*([०-९]{1,2})\s*[।|]\s*([०-९]{1,3}(?:\s*[-–]\s*[०-९]{1,3})?)\s*[।|]?\s*(?:\(\s*([०-९]{1,2})\s*\))?")
RE_HEADING = re.compile(r"(\S.{1,60}प्रकरणम्)\s*[॥|]+\s*([०-९]{1,2})\s*[॥|]")
RE_END = re.compile(r"इति\s*(\S.{1,70}?प्रकरण(?:म्|ं))")
RE_FOOT = re.compile(r"^\s*([०-९]{1,2})\s*[\.।]\s+\S")


def dev_only(s):
    return re.sub(r"[^ऀ-ॿ]", "", s)


def sim(a, b):
    a, b = dev_only(a), dev_only(b)
    if not a and not b: return 1.0
    if not a or not b: return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def tess_lines(tsv):
    rows = list(csv.DictReader(open(tsv, encoding="utf-8"), delimiter="\t", quoting=csv.QUOTE_NONE))
    lines = {}
    for r in rows:
        if r["level"] != "5" or not r["text"].strip(): continue
        k = (int(r["block_num"]), int(r["par_num"]), int(r["line_num"]))
        l = lines.setdefault(k, {"top": 10 ** 9, "bottom": 0, "left": 10 ** 9, "right": 0, "words": [], "conf": []})
        t, h, x, w = int(r["top"]), int(r["height"]), int(r["left"]), int(r["width"])
        l["top"] = min(l["top"], t); l["bottom"] = max(l["bottom"], t + h); l["left"] = min(l["left"], x); l["right"] = max(l["right"], x + w)
        l["words"].append(r["text"]); l["conf"].append(float(r["conf"]))
    out = []
    for k in sorted(lines, key=lambda k: (lines[k]["top"], lines[k]["left"])):
        l = lines[k]
        out.append({"y": l["top"], "h": l["bottom"] - l["top"], "x": l["left"], "x2": l["right"], "tess": " ".join(l["words"]),
                    "tconf": round(sum(l["conf"]) / len(l["conf"]), 1)})
    return out


def find_rule(png, y_from_frac=0.35):
    """y of the footnote separator: a row whose dark run spans ≥35 % of the page width, in the lower part."""
    im = np.asarray(Image.open(png).convert("L"))
    H, W = im.shape
    dark = im < 128
    best = None
    for y in range(int(H * y_from_frac), H - 40):
        row = dark[y]
        # longest run of dark pixels
        runs = np.diff(np.concatenate([[0], row.astype(np.int8), [0]]))
        starts = np.where(runs == 1)[0]; ends = np.where(runs == -1)[0]
        if len(starts):
            L = int((ends - starts).max())
            if L >= 0.35 * W and (best is None or y < best[0]):
                best = (y, L)
    return best[0] if best else None, W, H


_CH_CACHE = {}
def chandas_ok(lines):
    """True when the DGE Chandas engine recognises these lines as a metre (or an equal-pāda structure)."""
    import subprocess
    key = "\n".join(lines)
    if key in _CH_CACHE: return _CH_CACHE[key]
    runner = Path(__file__).resolve().parents[1] / "kamadhenu" / "chandas_runner.js"
    txt = re.sub(r"(?:॥|\|\||।।)\s*[०-९]{1,3}\s*(?:॥|\|\||।।)", "॥", key)
    try:
        r = subprocess.run(["node", str(runner)], input=json.dumps([txt], ensure_ascii=False), capture_output=True, text=True, cwd=str(runner.parents[2]))
        res = json.loads(r.stdout)[0]; m = res.get("match") or {}; pad = res.get("padas") or []
        score = 3 if m.get("names") else 2 if (len(pad) == 4 and len({p["aksharas"] for p in pad}) == 1) else 1 if (len(pad) == 2 and pad[0]["aksharas"] == pad[1]["aksharas"] and pad[0]["aksharas"] >= 16) else 0
    except Exception:
        score = 0
    _CH_CACHE[key] = score
    return score


def choose_verse_lines(cands):
    """cands = up to 4 lines above (and including) the marker line, top→bottom. Return how many (from the bottom) form the verse."""
    n = len(cands)
    if n <= 2: return n
    options = [k for k in (4, 3, 2) if k <= n]
    scored = [(chandas_ok(cands[n - k:]), k) for k in options]
    best = max(scored, key=lambda t: (t[0], t[1] in (2, 4), t[1]))
    if best[0] > 0: return best[1]
    # no metre recognised: prefer 4 when the top line of the 4 does NOT end a sentence (ends without । or ॥) and the 2nd ends with । (a half-verse)
    if n >= 4 and cands[n - 3].rstrip().endswith("।") and not cands[n - 4].rstrip().endswith(("।", "॥")): return 4
    return 2


def merge_page(pg, vtext, tsv, png):
    tl = tess_lines(tsv) if os.path.exists(tsv) else []
    rule_y, W, H = find_rule(png) if os.path.exists(png) else (None, 1429, 2448)
    vlines = [l.strip() for l in vtext.split("\n") if l.strip()]
    used = set()
    # align: for each tess line pick the best unused vision line (greedy by similarity, threshold 0.45)
    for l in tl:
        best, bi = 0.0, None
        for i, v in enumerate(vlines):
            if i in used: continue
            s = sim(l["tess"], v)
            if s > best: best, bi = s, i
        if bi is not None and best >= 0.45:
            l["vision"] = vlines[bi]; l["sim"] = round(best, 3); used.add(bi)
        else:
            l["vision"] = ""; l["sim"] = 0.0
    orphans = [v for i, v in enumerate(vlines) if i not in used]
    if rule_y and not any(RE_FOOT.match(l["vision"] or l["tess"]) and rule_y < l["y"] < rule_y + 260 for l in tl):
        rule_y = None                                   # a long horizontal line that is not followed by "N. …" is not the footnote rule
    body_h = np.median([l["h"] for l in tl]) if tl else 40
    RE_EMB = re.compile(r"^(.*?(?:॥|\|\||।।)\s*[०-९]{1,3}\s*(?:॥|\|\||।।))\s*((?:[।|]\s*)?[०-९]{1,2}\s*[।|]\s*[०-९]{1,2}\s*[।|]\s*[०-९]{1,3}(?:\s*[-–]\s*[०-९]{1,3})?\s*[।|]?\s*(?:\(\s*[०-९]{1,2}\s*\))?)\s*$")
    expanded = []
    for l in tl:
        m = RE_EMB.match((l["vision"] or l["tess"]).strip())
        if m and l["y"] > 0.07 * H:
            v, r = m.group(1).strip(), m.group(2).strip()
            l2 = dict(l); l2["vision"] = r; l2["tess"] = r; l2["sim"] = l["sim"]; l2["y"] = l["y"] + 1; l2["h"] = l["h"]; l2["synthetic_ref"] = True
            l["vision"] = v if l["vision"] else ""; l["tess"] = v
            expanded += [l, l2]
        else:
            expanded.append(l)
    tl = expanded
    for l in tl:
        txt = l["vision"] or l["tess"]
        l["text"] = txt
        l["region"] = "body"
        if l["y"] < 0.07 * H: l["region"] = "header"
        if rule_y and l["y"] > rule_y: l["region"] = "footnote"
        if RE_END.search(txt) and l["region"] == "body": l["region"] = "prakarana_end"
        elif RE_HEADING.search(txt) and l["region"] == "body": l["region"] = "heading"
        m = RE_REF.fullmatch(txt.strip()) or (RE_REF.search(txt) if re.fullmatch(r"[०-९ ।|()॥]+", txt.strip()) else None)
        if m and l["region"] == "body":
            vv = re.findall(r"[०-९]+", m.group(3))
            l["region"] = "ref"; l["ref"] = [int(m.group(1).translate(DEV)), int(m.group(2).translate(DEV)), int(vv[0].translate(DEV))]
            l["ref_range"] = m.group(3).translate(DEV).replace(" ", ""); l["fnmark"] = int(m.group(4).translate(DEV)) if m.group(4) else None
        l["cls"] = "A" if l["sim"] >= 0.95 else "B" if l["sim"] >= 0.85 else "C" if l["sim"] >= 0.7 else "D" if l["vision"] else "E"
    # footnote fallback when no rule was detected: first "N. …" line in the lower 45 % of the page starts the zone
    if not rule_y:
        for i, l in enumerate(tl):
            if l["region"] == "body" and l["y"] > 0.55 * H and RE_FOOT.match(l["text"]):
                for m in tl[i:]:
                    if m["region"] == "body": m["region"] = "footnote"
                break
    # verses: walk back from every ref line — the verse is the (up to 4) body lines just above it, stopping at a
    # commentary end marker "॥ N ॥" whose N is not this verse's number, a heading, or a taller/shorter font break.
    for i, l in enumerate(tl):
        if l["region"] != "ref": continue
        m = re.match(r"\s*([०-९]{1,3})\s*(?:॥|\|\||।।)", l["text"])
        vno = int(m.group(1).translate(DEV)) if m else None
        j = i - 1; got = []
        while j >= 0 and len(got) < 4:
            q = tl[j]
            if q["region"] not in ("body", "verse"): break
            e = RE_VERSE_END.search(q["text"])
            if e and got:                       # an end marker above the verse's own last line = commentary end
                n = int(e.group(1).translate(DEV))
                if vno is None or n != vno: break
            if e and not got and vno is None:
                vno = int(e.group(1).translate(DEV))
            got.append(j); j -= 1
        got = got[::-1]                          # top → bottom
        choice = choose_verse_lines([tl[k]["text"] for k in got])
        for k in got[len(got) - choice:]:
            tl[k]["region"] = "verse"
        l["verse_no"] = vno; l["verse_choice"] = {"candidates": len(got), "chosen": choice}
    return {"page": pg, "W": W, "H": H, "rule_y": rule_y, "body_h": float(body_h), "lines": tl, "vision_orphans": orphans,
            "n_lines": len(tl), "agreement": {c: sum(1 for l in tl if l["cls"] == c) for c in "ABCDE"}}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--vision", required=True); ap.add_argument("--tess-dir", required=True); ap.add_argument("--png-dir", required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--start", type=int, default=1); ap.add_argument("--end", type=int, default=10 ** 6)
    a = ap.parse_args()
    V = {p["page"]: p["text"] for p in json.load(open(a.vision, encoding="utf-8"))["pages"]}
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    prev = {}
    pm = out / "pages_merged.json"
    if pm.exists():
        prev = {p["page"]: p for p in json.load(open(pm, encoding="utf-8"))["pages"]}
    pages = []
    for pg in sorted(V):
        if pg < a.start or pg > a.end: pages.append(prev.get(pg)) if pg in prev else None; continue
        tsv = f"{a.tess_dir}/{pg:03d}.tsv"; png = f"{a.png_dir}/{pg:03d}.png"
        if not os.path.exists(tsv):
            if pg in prev: pages.append(prev[pg])
            continue
        pages.append(merge_page(pg, V[pg], tsv, png))
    pages = [p for p in pages if p]
    agg = {c: sum(p["agreement"][c] for p in pages) for c in "ABCDE"}
    json.dump({"_readme": "Geometry-aware merged OCR lines per page (Tesseract boxes + Vision text). cls A–E = engine agreement per line.",
               "pages": pages, "agreement": agg}, open(pm, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"merged {len(pages)} pages; agreement {agg}")


if __name__ == "__main__":
    main()
