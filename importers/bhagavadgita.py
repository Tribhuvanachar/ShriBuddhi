"""Srimad Bhagavad Gita -> itihasa/bhagavad_gita/adhyaya_NN/data.json

A NEW dedicated Gita section under Itihasas (the Gita is Bhishma Parva 23-40 of
the Mahabharata, so Itihasa is its correct home). One data.json per adhyaya; each
shloka carries the mula (Devanagari) + transliteration + word-by-word meaning +
a bhashya[] array of every available translation and commentary -- the schema's
per-shloka bhashya[] = [{commentator, text, language}] is exactly the "many
commentaries per sloka" shape (the app can toggle by commentator).

BASE SOURCE (reliable, no JS, GitHub-Actions friendly):
  github.com/gita/gita  (the BhagavadGita.io open dataset)
    data/verse.json        -> id, chapter_number, verse_number, text (Devanagari),
                              transliteration, word_meanings
    data/translation.json  -> verse_id, authorName, lang, description
    data/commentary.json   -> verse_id, authorName, lang, description
  This already bundles ~20 translations + several commentaries (Sanskrit/English/Hindi).

CLASSICAL SANSKRIT BHASHYAS (optional enrichment):
  gitasupersite.iitk.ac.in adds the classical Sanskrit bhashyas (Shankara,
  Ramanuja, Madhva, Sridhara, Madhusudana, Nilakantha, Vallabha, ...). That site
  is now a JS SPA, so it is imported separately via importers/gitasupersite.py
  (Wayback server-rendered snapshots). Enable with env GITA_SUPERSITE=1; it is
  best-effort and never blocks the base import.
"""
import os, json, collections
from common import http_get, write_grantha

RAW = "https://raw.githubusercontent.com/gita/gita/main/data"
VERSES_PER_CHAPTER = [47,72,43,42,29,47,30,28,34,42,55,20,35,27,20,24,28,78]  # sanity check


def _load(name):
    return json.loads(http_get(f"{RAW}/{name}"))


def build_items():
    verses = _load("verse.json")
    try:
        translations = _load("translation.json")
    except Exception as e:
        print(f"  ! translation.json failed: {e}"); translations = []
    try:
        commentaries = _load("commentary.json")
    except Exception as e:
        print(f"  ! commentary.json failed: {e}"); commentaries = []

    # verse global id -> bhashya list
    bhashya_by_vid = collections.defaultdict(list)
    for rec in translations:
        txt = (rec.get("description") or "").strip()
        if txt:
            bhashya_by_vid[rec["verse_id"]].append({
                "commentator": rec.get("authorName", "Unknown"),
                "text": txt, "language": rec.get("lang", ""), "kind": "translation",
            })
    for rec in commentaries:
        txt = (rec.get("description") or "").strip()
        if txt:
            bhashya_by_vid[rec["verse_id"]].append({
                "commentator": rec.get("authorName", "Unknown"),
                "text": txt, "language": rec.get("lang", ""), "kind": "commentary",
            })

    # group verses by chapter, preserving verse order
    chapters = collections.defaultdict(list)
    for v in verses:
        chapters[v["chapter_number"]].append(v)

    items_by_chapter = {}
    for ch in sorted(chapters):
        shlokas = []
        for v in sorted(chapters[ch], key=lambda x: x["verse_number"]):
            sh = {
                "number": v["verse_number"],
                "sanskrit_text": (v.get("text") or "").strip(),
            }
            if v.get("transliteration"): sh["transliteration"] = v["transliteration"].strip()
            if v.get("word_meanings"):   sh["artha"] = v["word_meanings"].strip()
            bh = bhashya_by_vid.get(v["id"])
            if bh: sh["bhashya"] = bh
            shlokas.append(sh)
        # verse-count sanity check
        exp = VERSES_PER_CHAPTER[ch-1] if ch-1 < len(VERSES_PER_CHAPTER) else None
        if exp and len(shlokas) != exp:
            print(f"  ~ adhyaya {ch}: got {len(shlokas)} shlokas, expected {exp}")
        items_by_chapter[ch] = [{
            "id": f"adhyaya_{ch:02d}",
            "reference": f"Bhagavad Gita, Adhyaya {ch}",
            "shlokas": shlokas,
        }]
    return items_by_chapter


def run():
    items_by_chapter = build_items()
    # optional classical-Sanskrit-bhashya enrichment
    if os.environ.get("GITA_SUPERSITE") == "1":
        try:
            import gitasupersite
            gitasupersite.enrich(items_by_chapter)
        except Exception as e:
            print(f"  ! GitaSupersite enrichment skipped: {e}")
    for ch, items in items_by_chapter.items():
        write_grantha(f"itihasa/bhagavad_gita/adhyaya_{ch:02d}",
                      "itihasa_purana_text", "Bhagavan Sri Krishna", items)


if __name__ == "__main__":
    run()
