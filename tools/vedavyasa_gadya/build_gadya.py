#!/usr/bin/env python3
"""Import Śrī Vedavyāsa Gadyam (Yādavārya, a disciple-devotee of Vedeśa Tīrtha) from sanskritdocuments.org into the
DvaitaVedanta later-ācāryas shelf as a mūla text:

    dge/data/darshana/vedanta/dvaita/DvaitaVedantaIn/later_acharyas/vedavyasa_gadya/mula/data.json

Usage:  python3 tools/vedavyasa_gadya/build_gadya.py [--html cached.html]
The gadya is prose: a chain of dative epithets of Vedavyāsa, each closed by a daṇḍa. One item per epithet
(the natural recitation unit — this is also what the lead's Kamadhenu recording follows), plus the opening
title and the closing colophon as their own items. Registers the grantha in library.json / taxonomy.json
(idempotent). Source credited per sanskritdocuments.org terms (free non-commercial use)."""
import html, json, re, sys, datetime, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
URL = "https://sanskritdocuments.org/doc_deities_misc/vedavyAsagadyam.html"
OUT_DIR = ROOT / "dge/data/darshana/vedanta/dvaita/DvaitaVedantaIn/later_acharyas/vedavyasa_gadya"
LIB_PATH = "dge/data/darshana/vedanta/dvaita/DvaitaVedantaIn/later_acharyas/vedavyasa_gadya/mula/data.json"
AUTHOR = "Yādavārya (यादवार्यः)"


def fetch(cache=None):
    if cache:
        return Path(cache).read_text(encoding="utf-8", errors="ignore")
    return subprocess.run(["curl", "-sS", "-L", "--max-time", "60", URL], capture_output=True, text=True, errors="ignore").stdout


def devanagari_text(page):
    body = re.sub(r"<script.*?</script>|<style.*?</style>", "", page, flags=re.S)
    txt = html.unescape(re.sub(r"<[^>]+>", "\n", body))
    lines = [l.strip() for l in txt.splitlines() if re.search(r"[ऀ-ॿ]", l)]
    # the page repeats the title (heading + body); keep body from the first non-title line
    while lines and lines[0] == "श्रीवेदव्यासगद्यम्":
        lines.pop(0)
    return " ".join(lines)


def build(text):
    text = re.sub(r"\s+", " ", text).strip()
    # split at daṇḍa / double daṇḍa, keeping the punctuation with the phrase
    parts = [p.strip() for p in re.split(r"(?<=[।॥])", text) if p.strip()]
    items, n = [], 0
    for p in parts:
        if p.startswith("इति ") or "सम्पूर्णम्" in p:
            items.append({"id": "VG_COLOPHON", "reference": "कोलोफोन्", "sanskrit_text": p, "tags": ["colophon", "gadya"], "notes": "",
                          "references": [], "audio": [], "category": "श्रीवेदव्यासगद्यम्", "section": "gadya", "kind": "colophon", "verse_no": None})
            continue
        n += 1
        items.append({"id": f"VG_G{n:03d}", "reference": f"गद्यम् · {n}", "sanskrit_text": p, "tags": ["prose", "gadya", "epithet"], "notes": "",
                      "references": [], "audio": [], "category": "श्रीवेदव्यासगद्यम्", "section": "gadya", "kind": "gadya_phrase", "verse_no": n})
    return items


def register():
    lib_p = ROOT / "dge/data/library.json"; tax_p = ROOT / "dge/data/taxonomy.json"
    lib = json.loads(lib_p.read_text(encoding="utf-8")); tax = json.loads(tax_p.read_text(encoding="utf-8"))
    entry = {"path": LIB_PATH, "populated": True, "title": "श्रीवेदव्यासगद्यम् (Vedavyāsa Gadyam, Yādavārya) — मूलम्",
             "addedAt": datetime.date.today().isoformat(),
             "source": {"source": "Sanskrit Documents (sanskritdocuments.org), Devanāgarī edition 'vedavyAsagadyam' encoded and proofread by Krishnananda Achar",
                        "source_url": URL, "licence": "sanskritdocuments.org standard usage terms (free non-commercial use, source credited); the text (17th c.) is public domain"},
             "facets": {"default_author": AUTHOR, "deity": "Vedavyāsa", "genre": "gadya (prose stotra)"}}
    gs = lib["granthas"]
    for i, g in enumerate(gs):
        if g["path"] == LIB_PATH:
            gs[i] = entry; break
    else:
        pos = max((i for i, g in enumerate(gs) if "/later_acharyas/bhagavata_saroddhara/" in g["path"]), default=len(gs) - 1) + 1
        gs.insert(pos, entry)
    lib_p.write_text(json.dumps(lib, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    la = tax["darshana"]["vedanta"]["dvaita"]["DvaitaVedanta"]["later_acharyas"]
    la.setdefault("vedavyasa_gadya", {"_default_author": AUTHOR})["mula"] = {"_schema": "grantha_mula_text", "_default_author": AUTHOR}
    tax_p.write_text(json.dumps(tax, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    mp = OUT_DIR / "_meta.json"
    if not mp.exists():
        mp.write_text(json.dumps({"directory": "vedavyasa_gadya", "description": "श्रीवेदव्यासगद्यम् — Vedavyāsa Gadyam of Yādavārya (prose stotra of Vedavyāsa, dative epithets)", "schema": "grantha_mula_text"}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    cache = sys.argv[sys.argv.index("--html") + 1] if "--html" in sys.argv else None
    items = build(devanagari_text(fetch(cache)))
    data = {"schema": "grantha_mula_text", "default_author": AUTHOR, "title": "श्रीवेदव्यासगद्यम्",
            "source": "Sanskrit Documents (sanskritdocuments.org)", "source_url": URL,
            "licence": "sanskritdocuments.org standard usage terms (free non-commercial use, source credited); text is public domain",
            "source_note": "Edition 'vedavyAsagadyam' (Devanāgarī), encoded and proofread by Krishnananda Achar (sanskritdocuments.org, 2020). Prose gadya split at every daṇḍa: one item per dative epithet, which is the unit the lead's recitation follows; the colophon (इति … सम्पूर्णम्) is kept as its own item.",
            "availableCommentaries": {}, "sections": [{"id": "gadya", "title": "गद्यम्", "items": len(items)}], "items": items}
    OUT_DIR.joinpath("mula").mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "mula/data.json").write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    register()
    print(f"wrote {len(items)} items → {LIB_PATH}")


if __name__ == "__main__":
    main()
