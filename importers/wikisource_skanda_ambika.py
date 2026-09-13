"""Bespoke importer for Skanda Purana's Ambika Khanda (Sanskrit Wikisource,
स्कन्दपुराणम्/खण्डः ८ (अम्बिकाखण्डः)) -- this khanda's 19 sub-pages are raw
MS-Word-pasted HTML (<p class="MsoNormal">...<span lang="SA">...verse...
</span></p>), not the site's usual <poem> wikitext every other khanda in
this project uses (confirmed live, 11 Sep 2026 -- see dge/PENDING.md), so
wikisource_purana.py's generic crawler treats these pages as link-only
index pages and finds no content. New taxonomy leaf (this khanda was not
part of the original gap list; deprioritized on the first import pass,
revisited here per the project lead's explicit go-ahead).

Chapter boundaries have no wikitext marker at all -- verified directly, the
literal string "अध्याय" never occurs mid-chapter, only in nav links and in
each chapter's own closing colophon ("इति स्कन्दपुराणे ...-ध्यायः", the
ordinal word varying, e.g. प्रथमोऽध्यायः/द्वितीयोऽध्यायः/...दशमोध्यायः).
Colophon-as-boundary is therefore the only signal, seeded per page by that
page's own known starting chapter (its own index link already states the
range, e.g. "अध्यायाः ११-२०") rather than trying to parse the ordinal words
themselves. One real transcription inconsistency confirmed live: chapter
3's colophon on page 1 spells the ending "...तृतीयोघ्यायः" (घ, gha) instead
of the expected "...तृतीयोध्यायः" (ध, dha) -- a source typo, not a
project bug -- so the boundary regex accepts either consonant.

Run: python importers/wikisource_skanda_ambika.py
"""
import html, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import write_grantha
from wikisource_purana import export_pages, preserve_stub_extra, SOURCE, LICENCE, DEVA_DIGITS

BASE = "स्कन्दपुराणम्/खण्डः ८ (अम्बिकाखण्डः)"
REL = "purana/maha_purana/skanda_purana/ambika_khanda"

# This khanda's 19 sub-pages are NOT uniform -- confirmed live, most (e.g.
# ०१-०३, ०५, ०७) are raw MS-Word-pasted HTML (<p class="MsoNormal">...
# <span lang="SA">...verse...</span></p>), but others (०४, ०८, ०९, १०-१९)
# are the site's ordinary <poem> wikitext instead. Both are handled by
# extracting one "paragraph" per <p> or, when there's no <p> at all, per
# raw line inside <poem> -- everything downstream (colophon boundaries,
# verse-end matching) works on that same list of paragraph/line strings.
P_TAG = re.compile(r"<p[^>]*>(.*?)</p>", re.S)
POEM = re.compile(r"<poem[^>]*>(.*?)</poem>", re.S)
TAG = re.compile(r"<[^>]+>")
BR = re.compile(r"<br\s*/?>")
PAGE_LABEL = re.compile(r"^अध्यायाः?\s*[०-९]")
SEPARATOR_LINE = re.compile(r"^[\s\-–—_]+$")  # apparatus-block dash rules, zero content
# The closing visarga/स् is sometimes just missing in this crowd-transcribed
# text (confirmed live, chapter 56's colophon on sub-page ०६ ends bare
# "...षट्पञ्चाशोध्याय" with no visarga at all) -- kept optional rather than
# required, alongside the ध/घ confusion already tolerated above.
COLOPHON = re.compile(r"इति\s*(?:श्री)?स्कन्दपुराणे.*?[धघ]्याय[ःस्]?")
# Danda placement varies a lot here -- space-separated "। । N । ।" on the
# <p>-format pages, adjacent "।।N।।" on the <poem>-format ones -- each side
# independently 0-2 dandas, each optionally followed by whitespace.
VEND = re.compile(r"(?:[।॥]\s*){0,2}([०-९]+(?:[-–][०-९]+)?)\s*(?:[।॥]\s*){0,2}$")


def paragraphs_of(raw_html):
    # <poem> takes priority over <p> -- confirmed live (sub-page ०४): a
    # page can carry ONE stray <p> (just its own top nav link) alongside
    # its real content in a <poem> block, and checking <p> first would
    # return only that nav paragraph and silently miss everything else.
    while raw_html.count("<poem") > raw_html.count("</poem>"):
        raw_html += "</poem>"
    poem_matches = list(POEM.finditer(raw_html))
    if poem_matches:
        out = []
        for pm in poem_matches:
            out.extend(TAG.sub(" ", BR.sub(" ", line)) for line in pm.group(1).splitlines())
        return out
    return [TAG.sub(" ", m.group(1)) for m in P_TAG.finditer(raw_html)]


def to_devnum(n):
    return "".join(DEVA_DIGITS[int(d)] for d in str(n))


# 19 sub-pages, 10 adhyayas each except the last (181-184, only 4) --
# ranges confirmed against this khanda's own index page.
PAGES = [(to_devnum(i).rjust(2, "०"), (i - 1) * 10 + 1) for i in range(1, 19)] + [("१९", 181)]


def parse_page(raw_html, start_chapter):
    """-> {chapter_number: [{'number':, 'sanskrit_text':}, ...]}"""
    chapters = {}
    chap = start_chapter
    buf = []
    for raw in paragraphs_of(raw_html):
        text = re.sub(r"\s+", " ", raw).strip()
        if not text or PAGE_LABEL.match(text) or SEPARATOR_LINE.match(text):
            continue
        if COLOPHON.search(text):
            chap += 1
            buf = []
            continue
        vm = VEND.search(text)
        if vm:
            buf.append(text[:vm.start()].strip())
            full = " ".join(x for x in buf if x)
            buf = []
            if full:
                chapters.setdefault(chap, []).append(
                    {"number": vm.group(1), "sanskrit_text": full})
        else:
            buf.append(text)
    return chapters


def main():
    print(f"crawling {len(PAGES)} pages of {BASE} ...")
    titles = [f"{BASE}/{suffix}" for suffix, _ in PAGES]
    fetched = export_pages(titles)

    all_chapters = {}
    for (suffix, start_chapter), title in zip(PAGES, titles):
        wt = fetched.get(title)
        if wt is None:
            print(f"  ! {title}: MISSING")
            continue
        page_chapters = parse_page(html.unescape(wt), start_chapter)
        found = sorted(page_chapters)
        expected = list(range(start_chapter, start_chapter + (4 if suffix == "१९" else 10)))
        missing = [c for c in expected if c not in found]
        print(f"  {title}: chapters {found[:1]}..{found[-1:]} "
              + (f"MISSING {missing}" if missing else "complete"))
        all_chapters.update(page_chapters)

    items = [{"id": f"adhyaya_{c:03d}", "reference": f"Skanda Purana, Ambika Khanda, Adhyaya {c}",
              "shlokas": all_chapters[c]} for c in sorted(all_chapters)]
    n_shlokas = sum(len(it["shlokas"]) for it in items)
    print(f"total: {len(items)} chapters, {n_shlokas} shlokas (184 chapters expected)")
    if not items:
        return
    extra = preserve_stub_extra(REL)
    write_grantha(
        REL, "itihasa_purana_text", "Maharshi Veda Vyasa", items,
        source_url="https://sa.wikisource.org/wiki/" + BASE.replace(" ", "_"),
        source_note=f"{SOURCE}. Raw MS-Word-pasted HTML (not this project's usual <poem> "
                    "wikitext), 19 sub-pages of ~10 adhyayas each; chapter boundaries read "
                    "from each chapter's own closing colophon (no wikitext marker exists). "
                    "One source typo tolerated: chapter 3's colophon on the first sub-page "
                    "spells the ending with घ (gha) instead of ध (dha).",
        licence=LICENCE,
        **extra,
    )


if __name__ == "__main__":
    main()
