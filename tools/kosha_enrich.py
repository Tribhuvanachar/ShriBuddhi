#!/usr/bin/env python3
"""
kosha_enrich.py — compile the raw Kosha shards into a render-ready
enriched tree. THE ORIGINALS ARE NEVER TOUCHED: dge/data/kosha/** stays
byte-identical as provenance; this writes a parallel tree under
dge/data/kosha_r/** (same <category>/<dict>/e/<bucket>.json layout) that
the v2 results page renders directly instead of regex-parsing 63MB of
raw glosses at runtime.

Per sense the compiler emits a render model:

  {"n": 1, "pos": "पुल्लिङ्गः",              # gender/POS when detected
   "spans": [ {"t":"txt","s":"..."},          # plain run
              {"t":"hw","s":"अब्ज"},          # embedded headword (linkable)
              {"t":"etym","s":"[अप्सु जायते, जन्-ड]"},
              {"t":"sutra","s":"३-२-९७","id":"3.2.97"},   # -> Ashtadhyayi
              {"t":"src","s":"इति मेदिनी"},   # source attribution tag
              {"t":"cite","s":"माघ० ४-६३","q":"माघ"} ],   # text citation
   "etym": [spans...],                        # व्युत्पत्ति/निष्पत्ति block
   "cites": [spans...],                       # citation block
   "syns": ["हिमांशु","चन्द्रमस्", ...]}      # Amarakosha समानार्थक

Dictionaries whose raw shards already carry structure (शब्दार्थकौस्तुभः:
pos/etymology/citations fields) pass it through typed; the others get
per-dictionary parser profiles. Anything a profile cannot parse stays a
plain "txt" run — the page can always fall back to the original text,
so enrichment can only add, never lose.

Also emits, per dictionary, an A-Z browse index
(dge/data/kosha_r/_browse/<dict>/index.json + page-<n>.json) so a kosha
can be opened and read alphabetically, not only searched.

Usage:
  python3 tools/kosha_enrich.py             # full build
  python3 tools/kosha_enrich.py --dicts shabdArtha_kaustubha,amarakosha
  python3 tools/kosha_enrich.py --check     # verify tree is current (CI)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

# Defaults compile the in-repo fallback subset; the full 95-dictionary
# corpus lives in Tribhuvanachar/bhumandala-kosha-data (dist branch,
# ~1.8GB) and its build Action runs this same script with --src/--dst
# pointed at that tree. The enriched tree is served CDN-only; it is NOT
# committed to this repo (dge/data/kosha_r is gitignored).
SRC = Path("dge/data/kosha")
DST = Path("dge/data/kosha_r")
SUTRA_INDEX = Path("dge/data/vedanga/vyakarana/ashtadhyayi/_index/sutra_index.json")
BROWSE_PAGE = 250

DEVA_DIGIT = str.maketrans("०१२३४५६७८९", "0123456789")

# --- reference taggers (shared across profiles) --------------------------
# Ashtadhyayi sutra in either digit script, '-' '.' '।' '|' separated,
# optionally wrapped in quotes/brackets, optionally with वा० (vartika).
SUTRA_RE = re.compile(
    r"(?:\(|“|\")?\s*(?:वा०\s*)?([०-९0-9]{1}[.\-।|]\s*[०-९0-9]{1}[.\-।|]\s*[०-९0-9]{1,3})\s*(?:\)|”|\")?")
# source-attribution tags: इति <कोश>, or the compact ०-abbreviations
SRC_RE = re.compile(
    r"(इति\s+[ऀ-ॿ]{2,14}(?:\s*[॥।])?|(?:मेदिनी|नानार्थर०|अमरः|विश्वः|हैमः|हेमचन्द्रः|शब्दर०|त्रिका०|जटाधरः|राजनिघण्टुः|भरतः)\s*[॥।]?)")
# classical text citations: <abbrev>० <numbers>, Latin Ms./Bhāg. style,
# and Apte's Panini refs with Roman pada numerals (P. VI. 3. 77)
CITE_RE = re.compile(
    r"([ऀ-ॿ]{2,10}०\s*[०-९0-9]+(?:[-–.][०-९0-9]+)*"
    r"|P\.\s*[IVX]+\.\s*[0-9]+\.\s*[0-9]+"
    r"|[A-Z][A-Za-zśāīūṛṢṇّĀŚḍ]{0,12}[.]\s*[0-9]+(?:[.,]\s*[0-9]+)*)")
ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7,
         "VIII": 8, "IX": 9, "X": 10}
APTE_PANINI_RE = re.compile(r"^P\.\s*([IVX]+)\.\s*([0-9]+)\.\s*([0-9]+)$")
# bracketed etymology at the head of Apte/MW glosses
BRACKET_ETYM_RE = re.compile(r"^\s*(\[[^\]]{3,120}\])")
# leading POS/gender tags
POS_SA_RE = re.compile(r"^\s*((?:पुं|क्ली|स्त्री|न|त्रि|अव्य)[०.]?(?:\s*(?:न|पुं|क्ली|स्त्री)[०.]?)*)\s")
POS_EN_RE = re.compile(r"^\s*((?:mfn|ind|mf|a|m|n|f)\.(?:\s*\([^)]{1,12}\))?)\s")
AMARA_SYN_RE = re.compile(r"समानार्थक:\s*(.+)$", re.S)
NISPATTI_RE = re.compile(r"निष्पत्तिः|व्युत्पत्तिः")


def load_sutra_ids() -> set[str]:
    try:
        d = json.loads(SUTRA_INDEX.read_text(encoding="utf-8"))
        return set(d.get("ids") or [])
    except Exception:
        return set()


SUTRA_IDS: set[str] = set()


def norm_sutra_id(text: str) -> str | None:
    t = text.translate(DEVA_DIGIT)
    parts = re.split(r"[.\-।|]\s*", t.strip())
    if len(parts) != 3:
        return None
    try:
        a, p, n = int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError:
        return None
    sid = f"{a}.{p}.{n}"
    return sid if (not SUTRA_IDS or sid in SUTRA_IDS) else None


def tag_spans(text: str) -> list[dict]:
    """Splits one string into typed spans by scanning for sutra / source /
    citation references. Non-matching stretches stay plain 'txt'."""
    if not text:
        return []
    marks = []  # (start, end, span)
    for m in SUTRA_RE.finditer(text):
        sid = norm_sutra_id(m.group(1))
        if sid:
            marks.append((m.start(1), m.end(1),
                          {"t": "sutra", "s": m.group(1), "id": sid}))
    for m in SRC_RE.finditer(text):
        marks.append((m.start(1), m.end(1), {"t": "src", "s": m.group(1).strip()}))
    for m in CITE_RE.finditer(text):
        raw = m.group(1).strip()
        pm = APTE_PANINI_RE.match(raw)
        if pm and pm.group(1) in ROMAN:
            sid = f"{ROMAN[pm.group(1)]}.{pm.group(2)}.{pm.group(3)}"
            if not SUTRA_IDS or sid in SUTRA_IDS:
                marks.append((m.start(1), m.end(1),
                              {"t": "sutra", "s": raw, "id": sid}))
                continue
        q = re.split(r"[०0-9IVX]", raw)[0].rstrip("० .")
        marks.append((m.start(1), m.end(1), {"t": "cite", "s": raw, "q": q}))
    # drop overlaps, earliest-longest wins
    marks.sort(key=lambda x: (x[0], -(x[1] - x[0])))
    chosen, last_end = [], 0
    for s, e, sp in marks:
        if s >= last_end:
            chosen.append((s, e, sp))
            last_end = e
    out, pos = [], 0
    for s, e, sp in chosen:
        if s > pos:
            out.append({"t": "txt", "s": text[pos:s]})
        out.append(sp)
        pos = e
    if pos < len(text):
        out.append({"t": "txt", "s": text[pos:]})
    return out


def compile_sense(dict_slug: str, sense: dict, n: int) -> dict:
    gloss = sense.get("gloss") or ""
    out: dict = {"n": n}
    pos = sense.get("pos") or ""
    etym_text = sense.get("etymology") or ""
    cites = [c.get("text", "") for c in (sense.get("citations") or []) if c.get("text")]
    body = gloss

    if dict_slug == "amarakosha":
        m = AMARA_SYN_RE.search(body)
        if m:
            out["syns"] = [s.strip() for s in re.split(r"[,्?]\s*(?![^()]*\))", m.group(1))
                           if s.strip()][:40]
            # simpler split: commas only
            out["syns"] = [s.strip(" ।॥") for s in m.group(1).split(",") if s.strip(" ।॥")]
            body = body[:m.start()].rstrip()
        gm = re.match(r"^(\S+)\s+(पुं|नपुं|स्त्री|त्रि|अव्य)[।॥]?\s*", body)
        if gm and not pos:
            pos = gm.group(2)

    if dict_slug in ("apte-1957", "mw-cologne", "macdonell", "benfey"):
        # leading repeated headword ("अग a. [...]"), then POS, then [etym]
        hm = re.match(r"^\s*[ऀ-ॿ][ऀ-ॿ‌‍-]*\s+", body)
        if hm:
            body = body[hm.end():]
        pm = POS_EN_RE.match(body)
        if pm and not pos:
            pos = pm.group(1)
            body = body[pm.end():].lstrip()
        bm = BRACKET_ETYM_RE.match(body)
        if bm and not etym_text:
            etym_text = bm.group(1)
            body = body[bm.end():].lstrip()
        # MW's parenthesized derivation right after the POS: (fr. ... √ जन्)
        if not etym_text and dict_slug == "mw-cologne":
            mm = re.match(r"^\((fr\.[^()]{2,120}|√[^()]{2,120})\)", body)
            if mm:
                etym_text = mm.group(1)
                body = body[mm.end():].lstrip()
        # Apte subdivides one printed entry into —1 —2 … sense blocks
        if "\n—" in body or body.startswith("—"):
            parts = re.split(r"\n?—(?=[0-9])", body)
            head = parts[0].strip()
            subs = [p.strip() for p in parts[1:] if p.strip()]
            if subs:
                out["subs"] = [{"n": re.match(r"^([0-9]+)", p).group(1)
                                if re.match(r"^([0-9]+)", p) else str(i + 1),
                                "spans": tag_spans(re.sub(r"^[0-9]+\s*", "", p))}
                               for i, p in enumerate(subs)]
                body = head

    if dict_slug in ("vachaspatyam", "shabdakalpadruma", "abhidhanachintamani"):
        pm2 = re.match(r"^\s*\S+\s+((?:पु|न|क्ली|स्त्री|त्रि|अव्य)[०.,]\s*(?:\((?:[^)]*)\)\s*)?)", body)
        if pm2 and not pos:
            pos = pm2.group(1).strip()
        # bracketed vyutpatti right after the gender tag (SKD convention)
        vm = re.search(r"\(([^()]{6,160}(?:जायते|प्रत्यय|समास|धातो|कर्त्तरि|\+)[^()]{0,80})\)", body[:260])
        if vm and not etym_text:
            etym_text = vm.group(1)

    if pos:
        out["pos"] = pos
    if etym_text:
        out["etym"] = tag_spans(etym_text)
    if cites:
        out["cites"] = [tag_spans(c) for c in cites]
    out["spans"] = tag_spans(body)
    return out


def iter_dict_dirs():
    for cat_dir in sorted(SRC.iterdir()):
        if not cat_dir.is_dir() or cat_dir.name.startswith("_"):
            continue
        for dict_dir in sorted(cat_dir.iterdir()):
            if dict_dir.is_dir():
                yield cat_dir.name, dict_dir


def build(only: set[str] | None, check: bool) -> int:
    global SUTRA_IDS
    SUTRA_IDS = load_sutra_ids()
    manifest = {"schema": "kosha_render_v1", "source": "dge/data/kosha",
                "dictionaries": {}}
    stale = []
    for cat, dict_dir in iter_dict_dirs():
        slug = dict_dir.name
        if only and slug not in only:
            continue
        e_dir = dict_dir / "e"
        if not e_dir.is_dir():
            continue
        out_dir = DST / cat / slug / "e"
        counts = {"entries": 0, "senses": 0, "sutra": 0, "src": 0,
                  "cite": 0, "etym": 0, "syn": 0}
        browse: list[tuple[str, str, str]] = []  # (slp1, headword, bucket)
        for shard in sorted(e_dir.glob("*.json")):
            data = json.loads(shard.read_text(encoding="utf-8"))
            out_data = {}
            for key, entries in data.items():
                rows = entries if isinstance(entries, list) else [entries]
                out_rows = []
                for entry in rows:
                    senses = entry.get("senses") or []
                    r_senses = [compile_sense(slug, s, i + 1)
                                for i, s in enumerate(senses)]
                    for rs in r_senses:
                        counts["senses"] += 1
                        if "etym" in rs:
                            counts["etym"] += 1
                        if "syns" in rs:
                            counts["syn"] += 1
                        for sp in (rs.get("spans") or []) + (rs.get("etym") or []) \
                                + [x for c in rs.get("cites", []) for x in c]:
                            if sp["t"] in ("sutra", "src", "cite"):
                                counts[sp["t"]] += 1
                    out_rows.append({
                        "id": entry.get("id"),
                        "headword": entry.get("headword"),
                        "headword_slp1": entry.get("headword_slp1"),
                        "senses_r": r_senses,
                    })
                    counts["entries"] += 1
                    browse.append((entry.get("headword_slp1") or key,
                                   entry.get("headword") or key, shard.stem))
                out_data[key] = out_rows
            payload = json.dumps(out_data, ensure_ascii=False,
                                 separators=(",", ":"))
            out_file = out_dir / shard.name
            if check:
                if not out_file.exists() or \
                        hashlib.sha1(out_file.read_bytes()).hexdigest() != \
                        hashlib.sha1(payload.encode()).hexdigest():
                    stale.append(str(out_file))
            else:
                out_dir.mkdir(parents=True, exist_ok=True)
                out_file.write_text(payload, encoding="utf-8")
        # ---- browse index ------------------------------------------------
        browse.sort(key=lambda x: x[0])
        bdir = DST / "_browse" / slug
        pages = [browse[i:i + BROWSE_PAGE] for i in range(0, len(browse), BROWSE_PAGE)]
        bindex = {"dict": slug, "category": cat, "entries": len(browse),
                  "page_size": BROWSE_PAGE, "pages": len(pages),
                  "first": [p[0][1] for p in pages]}
        if not check:
            bdir.mkdir(parents=True, exist_ok=True)
            (bdir / "index.json").write_text(
                json.dumps(bindex, ensure_ascii=False), encoding="utf-8")
            for i, p in enumerate(pages):
                (bdir / f"page-{i}.json").write_text(json.dumps(
                    [{"h": h, "s": s, "b": b} for s, h, b in p],
                    ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        manifest["dictionaries"][slug] = dict(counts, category=cat,
                                              browse_pages=len(pages))
        print(f"{slug:26} {counts['entries']:>7} entries  {counts['senses']:>7} senses"
              f"  sutra {counts['sutra']:>5}  src {counts['src']:>6}"
              f"  cite {counts['cite']:>6}  etym {counts['etym']:>6}  syn {counts['syn']:>5}")
    if check:
        if stale:
            print(f"kosha_enrich --check: STALE ({len(stale)} shards), rerun the build")
            for s in stale[:10]:
                print("  ", s)
            return 1
        print("kosha_enrich --check: OK")
        return 0
    (DST / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nwrote {DST}/manifest.json")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dicts", help="comma-separated dict slugs (default all)")
    ap.add_argument("--src", help="raw kosha tree (default dge/data/kosha)")
    ap.add_argument("--dst", help="enriched output tree (default dge/data/kosha_r)")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    global SRC, DST
    if args.src: SRC = Path(args.src)
    if args.dst: DST = Path(args.dst)
    only = set(args.dicts.split(",")) if args.dicts else None
    return build(only, args.check)


if __name__ == "__main__":
    sys.exit(main())
