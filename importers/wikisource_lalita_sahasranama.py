"""One-off importer for Lalita Sahasranama Stotra (Brahmanda Purana,
Uttarakhanda's Hayagriva-Agastya dialogue) into the GLOBAL stotra library
(dge/data/stotra/), not under purana/ -- per the project lead's explicit
call: it is used and known as a stotra, not read as Purana narrative, so it
belongs alongside the corpus's other standalone stotras rather than filed
as a Purana leaf. purana/maha_purana/brahmanda_purana/lalitopakhyana_
lalita_sahasranama is deliberately left empty (see its own data.json note)
rather than filled with this same content twice.

Source page has exactly two '==...==' sections (confirmed live): the
पूर्वभागः (Agastya's framing narrative) and the स्तोत्रम् itself (the 1000
names). Both use properly-closed <poem> blocks, but neither carries ANY
verse numbering at all (checked live) -- stanzas are split on a plain
double-danda and numbered sequentially by this importer instead.

Run: python importers/wikisource_lalita_sahasranama.py
"""
import html, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import write_grantha
from wikisource_purana import export_pages, NOISE_HDR, POEM, TAG, BR, WIKIFMT, SOURCE, LICENCE

TITLE = "श्री ललितासहस्रनामस्तोत्रम्"
REL = "stotra/lalita_sahasranama"
SECTION_HDR = re.compile(r"^==\s*(.+?)\s*==\s*$", re.M)
SECTION_SLUG = {"॥ पूर्वभागः ॥": "purvabhaga", "श्री ललितासहस्रनामस्तोत्रम्": "stotram"}
# Confirmed live: this transcription carries NO verse numbers anywhere at
# all (checked both sections for Devanagari and ASCII digits, zero found) --
# unlike every Purana text this project has imported so far, a plain
# double-danda closes each stanza with nothing else. Numbering below is
# therefore assigned sequentially by this importer, not read from the source.
STANZA_END = re.compile(r"[।॥]{2}\s*$")


def extract_shlokas(segment):
    shlokas, buf = [], []
    n = 0
    for poem_m in POEM.finditer(segment):
        for raw in html.unescape(poem_m.group(1)).splitlines():
            line = WIKIFMT.sub("", TAG.sub("", BR.sub("", raw))).strip()
            if not line or line.startswith("{{") or line.startswith("|"):
                continue
            buf.append(line)
            if STANZA_END.search(line):
                text = " ".join(x for x in buf if x).strip()
                buf = []
                if text:
                    n += 1
                    shlokas.append({"number": str(n), "text": text})
    if buf:
        text = " ".join(x for x in buf if x).strip()
        if text:
            n += 1
            shlokas.append({"number": str(n), "text": text})
    return shlokas


def main():
    print(f"crawling {TITLE} ...")
    out = export_pages([TITLE])
    wt = out.get(TITLE)
    if wt is None:
        print("MISSING page"); return
    body = NOISE_HDR.sub("", html.unescape(wt), count=1)

    bounds = list(SECTION_HDR.finditer(body))
    items, sections = [], []
    for i, b in enumerate(bounds):
        start, end = b.end(), (bounds[i + 1].start() if i + 1 < len(bounds) else len(body))
        title = b.group(1)
        slug = SECTION_SLUG.get(title, f"section_{i+1}")
        verses = extract_shlokas(body[start:end])
        print(f"  {title} ({slug}): {len(verses)} verses")
        for v in verses:
            items.append({"id": f"{slug}_{v['number']}", "reference": f"{title}, {v['number']}",
                          "section": slug, "sanskrit_text": v["text"]})
        if verses:
            sections.append({"id": slug, "title": title, "items": len(verses)})

    if not items:
        print("NOTHING PARSED"); return
    write_grantha(
        REL, "grantha_mula_text", "Hayagriva (to Agastya); traditional, Brahmanda Purana, Uttarakhanda", items,
        title="श्री ललितासहस्रनामस्तोत्रम्",
        sections=sections,
        source_url="https://sa.wikisource.org/wiki/" + TITLE,
        source_note=f"{SOURCE}. Filed under the global stotra library (not purana/) per the "
                    "project lead's call: this text is used and known as a standalone stotra, "
                    "not read as Purana narrative, even though it originates as the "
                    "Hayagriva-Agastya dialogue in Brahmanda Purana's Uttarakhanda "
                    "(Lalitopakhyana). Verse numbers are this importer's own (source carries "
                    "none); a source line occasionally runs one stanza's close and the next "
                    "prose caption together with no line break, so a handful of items span "
                    "more than one stanza -- known, accepted minor imperfection, no content "
                    "lost. See dge/PENDING.md, 11 Sep 2026.",
        licence=LICENCE,
    )


if __name__ == "__main__":
    main()
