#!/usr/bin/env python3
"""Import the Advaita Sharada corpus (advaitasharada.sringeri.net).

Sringeri Sharada Peetham's critical digital edition of the Shankara
bhashyas with their commentarial literature. Imported with case-by-case
permission granted by the project lead on 2 Sep 2026 for non-commercial,
educational dharma-prachara use; the site's robots.txt allows crawling
and publishes the sitemap this importer enumerates. Every record keeps
its source URL and the site's own unit anchors.

DELTA-ONLY per the project lead's instruction: works whose text the DGE
library already holds (the ten Shankara bhashyas under
darshana/vedanta/advaita/shankara_bhashya/) are NOT imported — only the
sub-commentaries, vartikas, prakaranas and stotras we lack. (Noted for
the lead: the Sringeri editions of the held bhashyas are cleaner than
our current OCR-derived texts; replacing them is a separate decision.)

Page model (fully server-rendered Astro):
  h1.chrome                      work title (Devanagari)
  p.chapter-head                 section title
  div.unit.verse#ID              verse: p.verse-text + span.verse-no
  p.unit.prose.kind-*#ID         prose paragraph (kind: prose, heading,
                                 mangala, avatarika, bhashya, ...)
  p.unit.colophon#ID             colophon
IDs are hierarchical (BS_C01_S01_V01, ..._B1 / _P0001 / _I01): a prose
paragraph whose id extends the previous verse's id belongs to that
verse's unit. Soft hyphens (U+00AD) are presentation-only and stripped.

Usage:
  python3 importers/advaita_sharada.py --sitemap --cache .as_cache --write
  python3 importers/advaita_sharada.py --works bhamati,ratnaprabha --write
"""

from __future__ import annotations

import argparse
import html as html_mod
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "dvaitavedanta"))
from dv_parse import sanitize_article_html  # noqa: E402

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("pip install beautifulsoup4", file=sys.stderr)
    raise

SITE = "https://advaitasharada.sringeri.net"
SITEMAP = SITE + "/sitemap-0.xml"
OUT_ROOT = Path("data/darshana/vedanta/advaita")

SOURCE_NOTE = (
    "Advaita Sharada — the Dharmika Granthas digitisation project of "
    "Sringeri Sharada Peetham (advaitasharada.sringeri.net). Imported "
    "with case-by-case permission granted by the project lead on "
    "2 Sep 2026 for non-commercial, educational dharma-prachara use; "
    "the site's robots.txt permits crawling. Every record retains its "
    "source URL and the site's own unit anchor."
)

# slug -> (relative dge dir under OUT_ROOT, layer dir, schema, default_author)
# The ten bhashyas DGE already held were first excluded, then added back
# as REPLACEMENTS (project lead, 2 Sep 2026): our OCR-derived texts are
# corrupted (e.g. our Brahmasutra-bhashya reads तत्राथाब्द where Sringeri
# reads तत्र अथशब्दः), so the Sringeri editions overwrite them in place —
# same folders, same single 'bhashya' layer, no sibling layers depend on
# the old unit_NNNN ids.
WORKS = {
    # --- sutra-prasthana commentaries -------------------------------
    "bhamati":                  ("sutra_prasthana_tikas/bhamati", "mula", "grantha_tika_text", "श्रीवाचस्पतिमिश्रः"),
    "kalpataru":                ("sutra_prasthana_tikas/kalpataru", "mula", "grantha_tika_text", "श्रीअमलानन्दः"),
    "parimala":                 ("sutra_prasthana_tikas/parimala", "mula", "grantha_tika_text", "श्रीअप्पय्यदीक्षितः"),
    "ratnaprabha":              ("sutra_prasthana_tikas/ratnaprabha", "mula", "grantha_tika_text", "श्रीगोविन्दानन्दः"),
    "nyayanirnaya":             ("sutra_prasthana_tikas/nyayanirnaya", "mula", "grantha_tika_text", "श्रीआनन्दगिरिः"),
    "panchapadika":             ("sutra_prasthana_tikas/panchapadika", "mula", "grantha_tika_text", "श्रीपद्मपादाचार्यः"),
    "vivaranaprameyasangraha":  ("sutra_prasthana_tikas/vivarana_prameya_sangraha", "mula", "grantha_tika_text", "श्रीविद्यारण्यः"),
    "nyayarakshamani":          ("sutra_prasthana_tikas/nyaya_rakshamani", "mula", "grantha_tika_text", "श्रीअप्पय्यदीक्षितः"),
    "vaiyasika-nyayamala":      ("sutra_prasthana_tikas/vaiyasika_nyayamala", "mula", "grantha_tika_text", "श्रीभारतीतीर्थः"),
    "vaktavyakashika":          ("sutra_prasthana_tikas/vaktavyakashika", "mula", "grantha_tika_text", ""),
    "purnanandi":               ("sutra_prasthana_tikas/purnanandi", "mula", "grantha_tika_text", ""),
    # --- upanishad-prasthana commentaries ---------------------------
    "brihadaranyakabhashya-vartika": ("upanishad_prasthana_tikas/brihadaranyaka_vartika", "mula", "grantha_tika_text", "श्रीसुरेश्वराचार्यः"),
    "taittiriya-vartika":       ("upanishad_prasthana_tikas/taittiriya_vartika", "mula", "grantha_tika_text", "श्रीसुरेश्वराचार्यः"),
    "taittiriya-vanamala":      ("upanishad_prasthana_tikas/taittiriya_vanamala", "mula", "grantha_tika_text", "श्रीअच्युतकृष्णानन्दतीर्थः"),
    "anandagiri-isha":          ("upanishad_prasthana_tikas/anandagiri_isha", "mula", "grantha_tika_text", "श्रीआनन्दगिरिः"),
    "anandagiri-kena-pada":     ("upanishad_prasthana_tikas/anandagiri_kena_pada", "mula", "grantha_tika_text", "श्रीआनन्दगिरिः"),
    "anandagiri-kena-vakya":    ("upanishad_prasthana_tikas/anandagiri_kena_vakya", "mula", "grantha_tika_text", "श्रीआनन्दगिरिः"),
    "anandagiri-kathaka":       ("upanishad_prasthana_tikas/anandagiri_kathaka", "mula", "grantha_tika_text", "श्रीआनन्दगिरिः"),
    "anandagiri-prashna":       ("upanishad_prasthana_tikas/anandagiri_prashna", "mula", "grantha_tika_text", "श्रीआनन्दगिरिः"),
    "anandagiri-mundaka":       ("upanishad_prasthana_tikas/anandagiri_mundaka", "mula", "grantha_tika_text", "श्रीआनन्दगिरिः"),
    "anandagiri-mandukya":      ("upanishad_prasthana_tikas/anandagiri_mandukya", "mula", "grantha_tika_text", "श्रीआनन्दगिरिः"),
    "anandagiri-taittiriya":    ("upanishad_prasthana_tikas/anandagiri_taittiriya", "mula", "grantha_tika_text", "श्रीआनन्दगिरिः"),
    "anandagiri-aitareya":      ("upanishad_prasthana_tikas/anandagiri_aitareya", "mula", "grantha_tika_text", "श्रीआनन्दगिरिः"),
    "anandagiri-chandogya":     ("upanishad_prasthana_tikas/anandagiri_chandogya", "mula", "grantha_tika_text", "श्रीआनन्दगिरिः"),
    "anandagiri-brha":          ("upanishad_prasthana_tikas/anandagiri_brihadaranyaka", "mula", "grantha_tika_text", "श्रीआनन्दगिरिः"),
    # --- bhashyas we do NOT hold ------------------------------------
    # --- held-bhashya replacements (Sringeri editions over OCR text) ---
    "brahmasutra-bhashya":      ("shankara_bhashya/brahmasutra_bhashya", "bhashya", "grantha_bhashya_text", "श्रीमच्छङ्करभगवत्पादाः"),
    "bhagavadgita-bhashya":     ("shankara_bhashya/gita_bhashya", "bhashya", "grantha_bhashya_text", "श्रीमच्छङ्करभगवत्पादाः"),
    "isha-bhashya":             ("shankara_bhashya/upanishad_bhashya/isha_upanishad", "bhashya", "grantha_bhashya_text", "श्रीमच्छङ्करभगवत्पादाः"),
    "kena-pada-bhashya":        ("shankara_bhashya/upanishad_bhashya/kena_upanishad", "bhashya", "grantha_bhashya_text", "श्रीमच्छङ्करभगवत्पादाः"),
    "prashna-bhashya":          ("shankara_bhashya/upanishad_bhashya/prashna_upanishad", "bhashya", "grantha_bhashya_text", "श्रीमच्छङ्करभगवत्पादाः"),
    "aitareya-bhashya":         ("shankara_bhashya/upanishad_bhashya/aitareya_upanishad", "bhashya", "grantha_bhashya_text", "श्रीमच्छङ्करभगवत्पादाः"),
    "chandogya-bhashya":        ("shankara_bhashya/upanishad_bhashya/chandogya_upanishad", "bhashya", "grantha_bhashya_text", "श्रीमच्छङ्करभगवत्पादाः"),
    "taittiriya-bhashya":       ("shankara_bhashya/upanishad_bhashya/taittiriya_upanishad", "bhashya", "grantha_bhashya_text", "श्रीमच्छङ्करभगवत्पादाः"),
    "brihadaranyaka-bhashya":   ("shankara_bhashya/upanishad_bhashya/brihadaranyaka_upanishad", "bhashya", "grantha_bhashya_text", "श्रीमच्छङ्करभगवत्पादाः"),
    "mandukya-karika-bhashya":  ("shankara_bhashya/upanishad_bhashya/mandukya_upanishad", "bhashya", "grantha_bhashya_text", "श्रीमच्छङ्करभगवत्पादाः"),
    "kathaka-bhashya":          ("shankara_bhashya_extra/kathaka_bhashya", "mula", "grantha_bhashya_text", "श्रीमच्छङ्करभगवत्पादाः"),
    "mundaka-bhashya":          ("shankara_bhashya_extra/mundaka_bhashya", "mula", "grantha_bhashya_text", "श्रीमच्छङ्करभगवत्पादाः"),
    "kena-vakya-bhashya":       ("shankara_bhashya_extra/kena_vakya_bhashya", "mula", "grantha_bhashya_text", "श्रीमच्छङ्करभगवत्पादाः"),
    # --- gita-prasthana ---------------------------------------------
    "anandagiri-gita":          ("gita_prasthana_tikas/anandagiri_gita", "mula", "grantha_tika_text", "श्रीआनन्दगिरिः"),
    # --- prakarana granthas -----------------------------------------
    "vivekachudamani":          ("prakarana_granthas/vivekachudamani", "mula", "grantha_prakarana_text", "श्रीमच्छङ्करभगवत्पादाः"),
    "shatashloki":              ("prakarana_granthas/shatashloki", "mula", "grantha_prakarana_text", "श्रीमच्छङ्करभगवत्पादाः"),
    "sarvavedantasiddhantasarasangraha": ("prakarana_granthas/sarvavedanta_siddhanta_sara_sangraha", "mula", "grantha_prakarana_text", "श्रीमच्छङ्करभगवत्पादाः"),
    "hastamalakiyam":           ("prakarana_granthas/hastamalakiyam", "mula", "grantha_prakarana_text", "श्रीहस्तामलकाचार्यः"),
    "hastamalakiya-bhashya":    ("prakarana_granthas/hastamalakiyam", "tika_bhashya", "grantha_tika_text", ""),
    "shrutisarasamuddharanam":  ("prakarana_granthas/shrutisara_samuddharanam", "mula", "grantha_prakarana_text", "श्रीतोटकाचार्यः"),
    "vedantasara":              ("prakarana_granthas/vedantasara", "mula", "grantha_prakarana_text", "श्रीसदानन्दयोगीन्द्रः"),
    "vedantaparibhasha":        ("prakarana_granthas/vedanta_paribhasha", "mula", "grantha_prakarana_text", "श्रीधर्मराजाध्वरीन्द्रः"),
    "shastra-siddanthalesha-sangraha": ("prakarana_granthas/siddhantalesha_sangraha", "mula", "grantha_prakarana_text", "श्रीअप्पय्यदीक्षितः"),
    # --- siddhi prasthana -------------------------------------------
    "advaitasiddhi":            ("siddhi_granthas/advaitasiddhi", "mula", "grantha_prakarana_text", "श्रीमधुसूदनसरस्वती"),
    "krishnalankara":           ("prakarana_granthas/siddhantalesha_sangraha", "tika_krishnalankara", "grantha_tika_text", ""),
    # --- stotras ----------------------------------------------------
    "pancharatna-stotrani":     ("stotrani/pancharatna_stotrani", "mula", "grantha_stotra_text", ""),
}

SOFT_HYPHEN = "­"


def fetch(url, cache_dir: Path, delay: float, refresh=False):
    key = re.sub(r"[^A-Za-z0-9._-]+", "_", url.split("//", 1)[-1])[:180]
    f = cache_dir / (key + ".html")
    if f.exists() and not refresh:
        return f.read_text(encoding="utf-8")
    req = urllib.request.Request(url, headers={"User-Agent": "DGE-importer/1.0 (dharma-prachara; contact: sanatanavidyagurukulam@gmail.com)"})
    with urllib.request.urlopen(req, timeout=120) as r:
        body = r.read().decode("utf-8", "replace")
    cache_dir.mkdir(parents=True, exist_ok=True)
    f.write_text(body, encoding="utf-8")
    time.sleep(delay)
    return body


def sitemap_sections():
    """{work_slug: [section tokens in sitemap order]}"""
    req = urllib.request.Request(SITEMAP, headers={"User-Agent": "DGE-importer/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        xml = r.read().decode("utf-8", "replace")
    out = {}
    for u in re.findall(r"<loc>([^<]+)</loc>", xml):
        m = re.match(re.escape(SITE) + r"/read/([^/]+)/([^/]+)/?$", u)
        if not m:
            continue
        out.setdefault(m.group(1), []).append(m.group(2))
    return out


def clean_text(el) -> str:
    t = el.get_text(" ", strip=True)
    t = t.replace(SOFT_HYPHEN, "")
    return re.sub(r"[ \t]+", " ", t).strip()


def unit_base_id(uid: str) -> str:
    """BS_C01_S01_V01_B1 -> BS_C01_S01_V01 ; prose paragraphs keep their
    own id as base."""
    m = re.match(r"^(.*_V\d+)_[A-Z]+\d*$", uid or "")
    return m.group(1) if m else (uid or "")


def parse_section(html_text: str, url: str, work: str):
    soup = BeautifulSoup(html_text, "html.parser")
    h1 = soup.select_one("h1")
    work_title = clean_text(h1) if h1 else work
    ch = soup.select_one("p.chapter-head")
    chapter = clean_text(ch) if ch else ""
    items = []
    pending_title = ""
    by_base = {}
    for el in soup.select(".unit"):
        classes = el.get("class") or []
        uid = el.get("id") or ""
        if "verse" in classes:
            vt = el.select_one(".verse-text")
            vn = el.select_one(".verse-no")
            item = {
                "id": uid,
                "unit_title": (clean_text(vn) if vn else "") or pending_title,
                "sanskrit_text": clean_text(vt) if vt else clean_text(el),
                "chapter": chapter,
                "kind": "verse",
                "source_html": sanitize_article_html(el) or "",
            }
            items.append(item)
            by_base[uid] = item
            pending_title = ""
            continue
        kind = next((c[5:] for c in classes if c.startswith("kind-")), "")
        text = clean_text(el)
        if not text:
            continue
        if kind == "heading":
            pending_title = text
            continue
        base = unit_base_id(uid)
        if base in by_base:
            tgt = by_base[base]
            tgt["sanskrit_text"] = (tgt["sanskrit_text"] + "\n\n" + text).strip()
            more = sanitize_article_html(el) or ""
            if more:
                tgt["source_html"] = (tgt.get("source_html") or "") + more
            continue
        item = {
            "id": uid or f"{work}_auto_{len(items)+1}",
            "unit_title": pending_title,
            "sanskrit_text": text,
            "chapter": chapter,
            "kind": kind or ("colophon" if "colophon" in classes else "prose"),
            "source_html": sanitize_article_html(el) or "",
        }
        items.append(item)
        if uid:
            by_base[uid] = item
        pending_title = ""
    return work_title, chapter, items


def human_ref(uid: str, work_title: str, chapter: str) -> str:
    segs = []
    for part in (uid or "").split("_")[1:]:
        m = re.match(r"([A-Z]+)(\d+)$", part)
        if m:
            segs.append(str(int(m.group(2))))
    return " > ".join(x for x in [work_title, chapter, ".".join(segs)] if x)


def emit(work, cfg, sections, cache_dir, delay, write, refresh, report):
    rel_dir, layer, schema, author = cfg
    all_items, work_title = [], work
    for sec in sections:
        url = f"{SITE}/read/{work}/{sec}/"
        try:
            body = fetch(url, cache_dir, delay, refresh)
        except Exception as e:
            report.append(f"  FAIL {url}: {e}")
            continue
        wt, chapter, items = parse_section(body, url, work)
        work_title = wt or work_title
        for it in items:
            it["_src"] = url
        all_items.extend(items)
        report.append(f"  {work}/{sec}: {len(items)} units")
    # de-duplicate ids (a chapter container id can repeat across pages)
    seen = {}
    out_items = []
    for it in all_items:
        base = it["id"]
        n = seen.get(base, 0) + 1
        seen[base] = n
        uid = base if n == 1 else f"{base}-{n}"
        out_items.append({
            "id": uid,
            "reference": human_ref(base, work_title, it.get("chapter", "")),
            "section": it.get("chapter", ""),
            "unit_title": it.get("unit_title", ""),
            "sanskrit_text": it["sanskrit_text"],
            "artha": "", "notes": "", "tags": [], "references": [], "audio": [],
            "breadcrumb": [x for x in [work_title, it.get("chapter", "")] if x],
            "source": {"site": "advaitasharada.sringeri.net", "url": it["_src"],
                       "anchor": base, "work": work},
            "source_html": it.get("source_html") or "",
        })
    doc = {
        "schema": schema,
        "default_author": author,
        "source_url": f"{SITE}/read/{work}",
        "source_note": SOURCE_NOTE,
        "items": out_items,
    }
    if write:
        d = OUT_ROOT / rel_dir / layer
        d.mkdir(parents=True, exist_ok=True)
        (d / "data.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
        meta = OUT_ROOT / rel_dir / "_meta.json"
        if not meta.exists() or layer == "mula":
            meta.write_text(json.dumps({
                "directory": rel_dir.split("/")[-1],
                "description": f"{work_title} — Advaita Sharada (Sringeri).",
                "schema": schema,
            }, ensure_ascii=False), encoding="utf-8")
    return work_title, len(out_items)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--works", help="comma-separated slugs (default: all configured)")
    ap.add_argument("--cache", default=".as_cache")
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()

    sections = sitemap_sections()
    todo = [w.strip() for w in args.works.split(",")] if args.works else list(WORKS)
    cache = Path(args.cache)
    report = []
    total = 0
    print(f"advaitasharada.sringeri.net -> {OUT_ROOT}  "
          f"[{'WRITE' if args.write else 'DRY RUN'}] — {len(todo)} work(s)")
    for w in todo:
        if w not in WORKS:
            print(f"!! unknown work {w}"); continue
        secs = sections.get(w) or []
        if not secs:
            print(f"!! no sitemap sections for {w}"); continue
        title, n = emit(w, WORKS[w], secs, cache, args.delay, args.write,
                        args.refresh, report)
        total += n
        print(f"{w:36} {title[:30]:32} {len(secs):>4} sections {n:>6} units")
    print(f"\nTOTAL {total} units across {len(todo)} works")
    fails = [r for r in report if "FAIL" in r]
    for f in fails: print(f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
