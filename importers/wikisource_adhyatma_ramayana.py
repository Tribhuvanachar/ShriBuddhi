"""One-off importer for Adhyatma Ramayana (Brahmanda Purana's embedded
work), Sanskrit Wikisource. Bespoke rather than routed through the generic
wikisource_purana.py engine because this text's single page diverges from
that engine's assumptions in two ways, both confirmed live:

1. Its <poem> tags are never closed (patched generically in
   wikisource_purana.crawl(), reused here via parse_poem_page).
2. Sarga boundaries are marked by an ORDINAL WORD ("प्रथमः सर्गः", "द्वितीयः
   सर्गः", ...), not a Devanagari numeral -- wikisource_purana.py's
   CHAPTER_BOUNDARY regex requires digits and cannot split on these. Each
   sarga's CLOSING colophon does carry its own number ("...बालकाण्डे
   प्रथमः सर्गः ।।१।"), but only kanda-level markers are reliable enough
   across the whole page to split on confidently (bold "'''...काण्डम्'''"
   text, confirmed live at exactly 2 occurrences -- see below) -- so this
   import keeps sarga-level colophons as ordinary verses within their
   kanda's flat list rather than trying to re-derive per-sarga boundaries.

Confirmed live (11 Sep 2026, via the site's own search API,
intitle:अध्यात्मरामायण): Wikisource carries only ONE page for this text, and
it holds only Bala and Ayodhya Kanda -- not the other 5 (Aranya, Kishkindha,
Sundara, Yuddha, Uttara). This is a genuine gap in Wikisource's own
transcription, not a parsing limitation; the missing kandas need a
different source entirely (see dge/PENDING.md).

Run: python importers/wikisource_adhyatma_ramayana.py
"""
import html, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import write_grantha
from wikisource_purana import export_pages, NOISE_HDR, TAG, BR, WIKIFMT, devnum_to_str, SOURCE, LICENCE, preserve_stub_extra

TITLE = "अध्यात्मरामायणम्"
REL = "purana/maha_purana/brahmanda_purana/adhyatma_ramayana"
# Confirmed live: exactly these two kanda-opening markers occur on the page,
# each preceding that kanda's entire content up to the next marker (or end
# of page for the last one).
KANDA_MARKER = re.compile(r"'''+\s*अध्यात्मरामयणे\s+(\S+)\s*काण्डम्\s*'''+")
# This whole page's <poem> is one giant tag spanning BOTH kandas (opens at
# byte 0, effectively never closes) -- confirmed live -- so splitting the
# page into per-kanda segments first (needed for kanda id/reference) then
# looking for <poem>...</poem> inside each segment finds nothing in every
# segment but the last, since the real opening tag ends up outside every
# other segment's own slice. Verse lines are extracted directly instead,
# without requiring a <poem> wrapper to be intact within the segment.
# Two verse-end conventions were confirmed live within this ONE page: Bala
# Kanda uses the usual danda ("भजे ।।१।।"), Ayodhya Kanda instead uses plain
# ASCII dots ("स्थितम् .. १.."), so both are accepted here.
VEND_LOCAL = re.compile(r"[।॥.]{1,3}\s*([०-९]+(?:[-–][०-९]+)?)\s*[।॥.]{0,3}\s*$")
KANDA_SLUG = {"बाल": "bala", "अयोध्या": "ayodhya"}  # extend if more kandas ever surface here


def extract_shlokas(segment):
    shlokas = []
    buf = []
    for raw in html.unescape(segment).splitlines():
        line = WIKIFMT.sub("", TAG.sub("", BR.sub("", raw))).strip()
        if not line or line.startswith("{{") or line.startswith("|") or line.startswith("=="):
            continue
        vm = VEND_LOCAL.search(line)
        if vm:
            buf.append(line[:vm.start()].strip())
            text = " ".join(x for x in buf if x).strip()
            buf = []
            if text:
                shlokas.append({"number": devnum_to_str(vm.group(1)), "sanskrit_text": text})
        else:
            buf.append(line)
    return shlokas


def main():
    print(f"crawling {TITLE} ...")
    out = export_pages([TITLE])
    wt = out.get(TITLE)
    if wt is None:
        print("MISSING page"); return
    body = html.unescape(wt)
    body = NOISE_HDR.sub("", body, count=1)

    bounds = list(KANDA_MARKER.finditer(body))
    print(f"{len(bounds)} kanda marker(s) found: {[b.group(1) for b in bounds]}")
    items = []
    for i, b in enumerate(bounds):
        start = b.end()
        end = bounds[i + 1].start() if i + 1 < len(bounds) else len(body)
        kanda_name = b.group(1)
        shlokas = extract_shlokas(body[start:end])
        print(f"  {kanda_name} Kanda: {len(shlokas)} shlokas")
        if shlokas:
            slug = KANDA_SLUG.get(kanda_name, kanda_name)
            items.append({"id": f"{slug}_kanda", "reference": f"Adhyatma Ramayana, {kanda_name} Kanda",
                          "shlokas": shlokas})

    if not items:
        print("NOTHING PARSED"); return
    extra = preserve_stub_extra(REL)
    write_grantha(
        REL, "itihasa_purana_text", "Maharshi Veda Vyasa", items,
        source_url="https://sa.wikisource.org/wiki/" + TITLE,
        source_note=f"{SOURCE}. PARTIAL: only Bala and Ayodhya Kanda are transcribed on "
                    "Wikisource's single page for this text (confirmed via the site's own "
                    "search API, no other page exists) -- Aranya, Kishkindha, Sundara, "
                    "Yuddha and Uttara Kanda are not yet available from this source. Each "
                    "item here is a whole kanda's flat verse list (sarga boundaries, marked "
                    "only by an ordinal word like 'प्रथमः सर्गः' rather than a numeral, are "
                    "kept as ordinary colophon verses within that list rather than split "
                    "out -- see this script's own docstring).",
        licence=LICENCE,
        **extra,
    )


if __name__ == "__main__":
    main()
