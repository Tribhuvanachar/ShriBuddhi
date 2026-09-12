"""Mahabharata -- English translation layer (K.M. Ganguli, public domain)
   -> itihasa/mahabharata/<parva>_parva/translation_ganguli/data.json

IMPORTANT REALITY CHECK (documented in COMMENTARY_IMPORT_HANDOFF.md):
  A free, scrapable, per-SHLOKA word-to-word English Mahabharata does NOT exist
  (unlike valmikiramayan.net for the Ramayana). The only word-by-word MBh is an
  offline print book (Sarasvati Mohan / Santurkar). So for the Mahabharata we add
  the best free option: the complete Kisari Mohan Ganguli English prose
  translation (public domain), aligned at the SECTION (adhyaya) level -- not per
  shloka. The Devanagari mula already lives in /mula (BORI critical edition).

Source: sacred-texts.com  (clean static HTML, public-domain Ganguli text).
  URL: https://sacred-texts.com/hin/m{BB}/m{BB}{SSS}.htm   BB=book 01-18, SSS=section

Note: Ganguli follows the Calcutta/Vulgate numbering while /mula is BORI critical,
so section boundaries mostly-but-not-exactly correspond -- treat this as an
adhyaya-level reading aid, not a verse-aligned gloss. Stored under the `generic`
schema (searchable `text` field).
"""
import re, time
from common import http_get, to_text, write_grantha

BASE = "https://sacred-texts.com/hin"
# Politeness delay -- unlike tools/DvaitaVedanta/Itara/DasaSahitya's crawler, this loop has no
# built-in pause between requests, and it can make thousands of them across
# 18 books (up to max_gap consecutive misses per book, on top of every real
# hit). A public archive site deserves the same courtesy Dasa Sahitya's own
# crawler already gives every other source.
REQUEST_DELAY = 0.5
PARVA = {1:"adi",2:"sabha",3:"vana",4:"virata",5:"udyoga",6:"bhishma",7:"drona",
         8:"karna",9:"shalya",10:"sauptika",11:"stri",12:"shanti",13:"anushasana",
         14:"ashvamedhika",15:"ashramavasika",16:"mausala",17:"mahaprasthanika",
         18:"svargarohana"}

DROP_LINE = re.compile(r"(sacred[- ]texts|^Next:|^Previous:|^Index$|Hinduism|"
                       r"Buy this Book|^p\.\s*\d+$|^\s*$)", re.I)
PAGE_MARK = re.compile(r"\bp\.\s*\d+\b")
FOOTNOTE  = re.compile(r"\[\s*\d+\s*\]")
SECTION_HEAD = re.compile(r"SECTION\s+[IVXLCDM\d]+", re.I)


def clean_section(raw_html):
    raw_html = re.sub(r"(?is)<head.*?</head>", "", raw_html)   # drop <title>/nav
    txt = to_text(raw_html)
    lines = []
    for ln in txt.splitlines():
        ln = ln.strip()
        if not ln or DROP_LINE.search(ln):
            continue
        ln = PAGE_MARK.sub("", ln)
        ln = FOOTNOTE.sub("", ln)
        ln = re.sub(r"\s+", " ", ln).strip()
        if ln:
            lines.append(ln)
    return "\n".join(lines).strip()


def run(max_gap=3):
    for book in range(1, 19):
        parva = PARVA[book]
        print(f"{parva} parva (book {book:02d}) ...")
        items, sec, gap = [], 1, 0
        while gap <= max_gap:
            url = f"{BASE}/m{book:02d}/m{book:02d}{sec:03d}.htm"
            try:
                raw = http_get(url)
                gap = 0
            except Exception:
                gap += 1
                sec += 1
                continue
            finally:
                time.sleep(REQUEST_DELAY)
            body = clean_section(raw)
            if body and len(body) > 40:
                mh = SECTION_HEAD.search(body)
                items.append({
                    "id": f"section_{sec:03d}",
                    "title": f"{parva.title()} Parva, Section {sec}",
                    "author": "Kisari Mohan Ganguli (tr.)",
                    "text": body,
                })
                print(f"  section {sec}: {len(body)} chars")
            sec += 1
        if items:
            write_grantha(f"itihasa/mahabharata/{parva}_parva/translation_ganguli",
                          "generic", "Kisari Mohan Ganguli (tr.)", items)
            print(f"  -> {len(items)} sections")


if __name__ == "__main__":
    run()
