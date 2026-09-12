#!/usr/bin/env python3
"""Import the Sri Ramanuja Meghamala digital archive
(srivaishnavan.com/sri-ramanuja-meghamala/ — JIR Foundation).

A ~2,400-page Sri Vaishnava treasury: Valmiki Ramayana with
Govindaraja's vyakhya, the Brahma-sutra literature, Vedanta Desika's
granthas (Satadooshani, Paduka-sahasram, Rahasya-traya-saram, ...),
Divya Prabandham with vyakhyanas, upanishads with Vishishtadvaita
bhashyas, stotras, smritis and mahatmyas. Imported with case-by-case
permission granted by the project lead on 2 Sep 2026 for
non-commercial, educational dharma-prachara use. Works the DGE library
already holds in full (Sribhasyam, Vedartha Sangraha, Sarirarka-
sastrartha-dipika, Vishayavakya-dipika, Nyayakalapa-sangraha,
Nayasangatimalika) are excluded upstream in the fetch list.

Input: the knowledge-tree TSV extracted from the archive page
(path<TAB>leaf-title<TAB>url per line) and a cache directory of
fetched pages (md5(url).html). Unit model:

  * a paragraph carrying a verse marker (॥ N ॥) opens a new unit —
    the shloka/mantra — and following prose (its vyakhya) attaches;
  * marker-less prose accumulates into ~1,500-char units at paragraph
    boundaries;
  * every unit keeps sanitized source_html of its paragraphs.

Grantha grouping: one grantha per depth-1 tree node — the archive's own
tree already names one node per work (each Ramayana kaanda, each
upanishad, each stotra-kartā's collection, each Mahabharata parva);
deeper Adhyaya/Pada levels become section breadcrumbs. Devanagari node
names (the Mahabharata parvas) are transliterated for slugs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "dvaitavedanta"))
import dv_parse  # noqa: E402
from bs4 import BeautifulSoup, NavigableString, Tag  # noqa: E402
from html import escape  # noqa: E402

try:
    import lxml  # noqa: F401
    SOUP_PARSER = "lxml"
except ImportError:      # pure-Python fallback: ~100x slower on this corpus
    SOUP_PARSER = "html.parser"


def sanitize_walk(node) -> str:
    """dv_parse.sanitize_article_html's whitelist applied by walking the
    ALREADY-PARSED tree — no re-parse. The original re-parsed every
    paragraph through BeautifulSoup (500k+ soup builds over this corpus,
    hours of CPU on the pure-Python parser); this emits directly."""
    parts = []

    def walk(n):
        if isinstance(n, NavigableString):
            parts.append(escape(str(n), quote=False))
            return
        if not isinstance(n, Tag):
            return
        name = (n.name or "").lower()
        if name in dv_parse._HTML_DROP_TAGS:
            return
        keep = name in dv_parse._HTML_KEEP_TAGS and name != "a"
        if keep:
            attrs = ""
            for k, v in n.attrs.items():
                if k.lower() in dv_parse._HTML_KEEP_ATTRS:
                    sv = " ".join(v) if isinstance(v, list) else str(v)
                    attrs += f' {k.lower()}="{escape(sv)}"'
            parts.append(f"<{name}{attrs}>")
        for c in n.children:
            walk(c)
        if keep:
            parts.append(f"</{name}>")

    walk(node)
    out = re.sub(r"\n{3,}", "\n\n", "".join(parts)).strip()
    if len(out.encode("utf-8")) > dv_parse._HTML_MAX_BYTES:
        return ""
    if not re.search(r'class=|<(h[1-6]|strong|b|em|i|u|sup|sub|table)\b', out):
        return ""
    return out

OUT_ROOT = Path("data/darshana/vedanta/vishishtadvaita/RamanujaMeghamala")
SOURCE_NOTE = (
    "Sri Ramanuja Meghamala — the JIR Foundation's digital archive "
    "(srivaishnavan.com/sri-ramanuja-meghamala). Imported with "
    "case-by-case permission granted by the project lead on 2 Sep 2026 "
    "for non-commercial, educational dharma-prachara use. Every record "
    "retains its source URL."
)

MARKER = re.compile(r"॥\s*[०-९0-9]+(?:\s*[-–.]\s*[०-९0-9]+)*\s*॥")
PROSE_UNIT_CHARS = 1500

# Works the DGE library already holds in full — never emitted, matching
# the exclusions applied when the fetch list was built.
HELD_NODES = {
    "Sribhasyam",
    "Saareeraka Saastraartha Deepika",
    "Vishayavakya Dipika",
    "Nyayakalaapa Sangraha",
    "Nayasanghatimalika",
    "Vedartha Sangraha",
}

CAT_SLUG = {
    "Upanishads": "upanishad_prasthana",
    "Brahma Sutras": "sutra_prasthana",
    "Bhagavad Gita": "gita_prasthana",
    "Srimad Ramayanam": "ramayana",
    "SriMahabharatam": "mahabharata",
    "Puranas": "puranani",
    "Smrithi": "smritayah",
    "Stotras": "stotrani",
    "Rahasya Granthas": "rahasya_granthas",
    "Divya Prabhandham": "divya_prabandham",
    "Bhagavad Visayam": "bhagavad_vishayam",
    "Reference Texts": "reference_granthas",
    "Divya Desha Vaibhavam": "divya_desha_vaibhavam",
    "Agamas": "agamah",
    "Guruparampara": "guruparampara",
}


# Minimal Devanagari -> Latin, just enough for stable readable slugs
# (a consonant carries an inherent 'a'; a matra replaces it, a virama
# removes it). Not a scholarly scheme — slugs only, titles stay Devanagari.
DEV_CONS = {
    "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "n",
    "च": "ch", "छ": "chh", "ज": "j", "झ": "jh", "ञ": "n",
    "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n",
    "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n",
    "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m",
    "य": "y", "र": "r", "ल": "l", "व": "v",
    "श": "sh", "ष": "sh", "स": "s", "ह": "h", "ळ": "l",
}
DEV_VOWEL = {
    "अ": "a", "आ": "aa", "इ": "i", "ई": "ee", "उ": "u", "ऊ": "oo",
    "ऋ": "ri", "ए": "e", "ऐ": "ai", "ओ": "o", "औ": "au",
}
DEV_MATRA = {
    "ा": "aa", "ि": "i", "ी": "ee", "ु": "u", "ू": "oo",
    "ृ": "ri", "े": "e", "ै": "ai", "ो": "o", "ौ": "au",
}


def translit_dev(s: str) -> str:
    out = []
    for ch in s:
        if ch in DEV_CONS:
            out.append(DEV_CONS[ch] + "a")
        elif ch in DEV_VOWEL:
            out.append(DEV_VOWEL[ch])
        elif ch in DEV_MATRA:
            if out and out[-1].endswith("a"):
                out[-1] = out[-1][:-1]
            out.append(DEV_MATRA[ch])
        elif ch == "्":  # virama
            if out and out[-1].endswith("a"):
                out[-1] = out[-1][:-1]
        elif ch in "ंँ":
            out.append("m")
        elif ch == "ः":
            out.append("h")
        elif "०" <= ch <= "९":
            out.append(chr(ord(ch) - ord("०") + ord("0")))
        else:
            out.append(ch)
    return "".join(out)


def slugify(s: str) -> str:
    s = translit_dev(s)
    s = unicodedata.normalize("NFKD", s)
    s = re.sub(r"^\d+\.\s*", "", s)
    s = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_").lower()
    return s[:60] or "x"


def base_title(leaf_title: str) -> str:
    """'1. कठोपनिषत् – प्रथमा वल्ली' -> 'कठोपनिषत्' ; strips the leading
    number and any dash-separated part designator."""
    t = re.sub(r"^\d+\.\s*", "", leaf_title).strip()
    t = re.split(r"\s*[–—-]\s*", t)[0].strip()
    t = re.sub(r"\s*Part\s+[IVX0-9]+$", "", t, flags=re.I).strip()
    return t or leaf_title


def load_tree(tsv: Path):
    rows = []
    for line in tsv.read_text(encoding="utf-8").splitlines():
        if "\t" not in line:
            continue
        path, title, url = line.split("\t")[:3]
        parts = [p for p in path.split(" > ") if p]
        if not parts:
            continue
        rows.append((parts, title.strip(), url.strip()))
    return rows


def group_granthas(rows):
    """-> {(cat_slug, grantha_slug): {"title":…, "cat":…, "leaves":[(sub, title, url)]}}"""
    out = {}
    for parts, title, url in rows:
        cat = parts[0]
        cslug = CAT_SLUG.get(cat, slugify(cat))
        node = parts[1] if len(parts) > 1 else base_title(title)
        if node in HELD_NODES:
            continue
        g_title = node
        gslug = slugify(node)
        sub = parts[2:]
        key = (cslug, gslug)
        e = out.setdefault(key, {"title": g_title, "cat": cat, "leaves": []})
        e["leaves"].append((" > ".join(sub), title, url))
    return out


def cache_file(cache: Path, url: str) -> Path:
    return cache / (hashlib.md5(url.encode()).hexdigest() + ".html")


def parse_leaf(html_text: str, url: str):
    soup = BeautifulSoup(html_text, SOUP_PARSER)
    h1 = soup.select_one("h1")
    page_title = h1.get_text(" ", strip=True) if h1 else ""
    cont = soup.select_one(".entry-content") or soup.select_one("[class*=post-content]")
    if cont is None:
        return page_title, []
    units, cur, cur_len, cur_marked = [], [], 0, False

    def flush():
        nonlocal cur, cur_len, cur_marked
        if cur:
            units.append(list(cur))
        cur, cur_len, cur_marked = [], 0, False

    # "pre": exactly one page in the corpus (प्रपत्त्यनुपायत्व विचारः)
    # keeps its whole text in <pre> blocks with no <p> at all
    for p in cont.find_all(["p", "h2", "h3", "h4", "pre"]):
        text = p.get_text(" ", strip=True)
        if not text:
            continue
        marked = bool(MARKER.search(text))
        if marked:
            # a shloka/mantra opens a fresh unit; its vyakhya follows it
            flush()
            cur.append(p)
            cur_len += len(text)
            cur_marked = True
            continue
        cur.append(p)
        cur_len += len(text)
        # inside a verse unit the whole vyakhya stays with its shloka;
        # marker-less prose chunks close at a readable size
        if not cur_marked and cur_len >= PROSE_UNIT_CHARS:
            flush()
    flush()
    out = []
    for group in units:
        text = "\n".join(p.get_text(" ", strip=True) for p in group)
        text = re.sub(r"[ \t]+", " ", text).strip()
        src = "".join(sanitize_walk(p) or "" for p in group)
        m = MARKER.search(group[0].get_text(" ", strip=True))
        out.append({"text": text, "source_html": src,
                    "marker": m.group(0) if m else ""})
    return page_title, out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tree", required=True)
    ap.add_argument("--cache", required=True)
    ap.add_argument("--only", help="comma-separated cat_slug filters")
    ap.add_argument("--granthas", help="comma-separated cat_slug/grantha_slug keys to (re)write; others untouched")
    ap.add_argument("--strict", action="store_true",
                    help="never write a grantha with a missing/short cached page (the sync workflow's setting)")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    rows = load_tree(Path(args.tree))
    granthas = group_granthas(rows)
    only = set(args.only.split(",")) if args.only else None
    wanted = set(args.granthas.split(",")) if args.granthas else None
    cache = Path(args.cache)
    total_units = total_missing = skipped_strict = 0
    print(f"meghamala -> {OUT_ROOT}  [{'WRITE' if args.write else 'DRY RUN'}] "
          f"— {len(granthas)} granthas from {len(rows)} leaves")
    for (cslug, gslug), e in sorted(granthas.items()):
        if only and cslug not in only:
            continue
        if wanted is not None and f"{cslug}/{gslug}" not in wanted:
            continue
        items = []
        missing = 0
        for sub, ltitle, url in e["leaves"]:
            f = cache_file(cache, url)
            if not f.exists() or f.stat().st_size < 3000:
                missing += 1
                continue
            page_title, units = parse_leaf(f.read_text(encoding="utf-8", errors="replace"), url)
            sec = re.sub(r"^\d+\.\s*", "", ltitle)
            for j, u in enumerate(units, 1):
                uid = f"MM_{gslug[:24]}_{len(items)+1:05d}"
                items.append({
                    "id": uid,
                    "reference": " > ".join(x for x in [e["title"], sub, sec, u["marker"].strip("॥ ")] if x),
                    "section": sec,
                    "unit_title": u["marker"],
                    "sanskrit_text": u["text"],
                    "artha": "", "notes": "", "tags": [], "references": [], "audio": [],
                    "breadcrumb": [x for x in [e["cat"], e["title"], sub, sec] if x],
                    "source": {"site": "srivaishnavan.com", "url": url,
                               "page": page_title},
                    "source_html": u["source_html"],
                })
        total_units += len(items)
        total_missing += missing
        status = f"({missing} pages missing)" if missing else ""
        print(f"{cslug:24} {gslug[:36]:38} {len(e['leaves']):>4} leaves {len(items):>6} units {status}")
        if args.strict and missing:
            # A short cache would write a truncated grantha over a complete
            # one. Under --strict that grantha is left exactly as it is.
            skipped_strict += 1
            print(f"   !! strict: not writing {cslug}/{gslug} — {missing} page(s) not cached")
            continue
        if args.write and items:
            d = OUT_ROOT / cslug / gslug / "mula"
            d.mkdir(parents=True, exist_ok=True)
            (d / "data.json").write_text(json.dumps({
                "schema": "grantha_mula_text",
                "default_author": "",
                "source_url": e["leaves"][0][2],
                "source_note": SOURCE_NOTE,
                "items": items,
            }, ensure_ascii=False, indent=1), encoding="utf-8")
            meta = OUT_ROOT / cslug / gslug / "_meta.json"
            meta.write_text(json.dumps({
                "directory": gslug,
                "description": f"{e['title']} — Sri Ramanuja Meghamala (JIR Foundation).",
                "schema": "grantha_mula_text",
            }, ensure_ascii=False), encoding="utf-8")
    print(f"\nTOTAL {total_units} units; {total_missing} pages not yet cached"
          + (f"; {skipped_strict} grantha(s) left untouched under --strict" if skipped_strict else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
