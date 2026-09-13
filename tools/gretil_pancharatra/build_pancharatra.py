#!/usr/bin/env python3
"""
build_pancharatra.py -- 23 Aug: fills 2 of the 13 empty Pancharatra Samhita
taxonomy leaves, per a GRETIL availability check (asked directly: "all the
Pancharatra Samhitas... available in GRETIL etc needs to be filled in").
DCS itself carries none of these (checked directly, only Sattvatatantra
matched anything Pancharatra-shaped, imported separately in batch 8) --
GRETIL is a different source with its own licence to verify per file, not
assumed from the one Pancharatra Samhita already in this repo
(Prakashasamhita, CC BY-NC-SA 4.0).

Checked, not guessed: of the 13 named samhitas still empty, only 2 have a
GRETIL e-text at all -- Pauskarasamhita (PARTIAL: adhyayas 27-43 of the
printed edition only, not the whole text) and Vishvaksenasamhita
(complete). The other 11 (Ahirbudhnya, Hayagriva, Ishvara, Jayakhya,
Lakshmitantra, Naradiya, Padma, Parama, Parashara, Vasishtha, Vishnu) have
no GRETIL e-text -- confirmed by reading GRETIL's own Vaishnava-section
catalog directly, not by a missed search. Two near-misses caught along
the way and correctly NOT used as substitutes: GRETIL's
"Jnanamritasarasamhita" is Narada-Pancharatra-adjacent but is a different
text from "Naradiyasamhita" itself; its "Parasharadharmasamhita" is
Parashara's DHARMASHASTRA smriti (already handled separately, see
build_batch7_smriti.py), not the Pancharatra Parasharasamhita.

Licence verified directly from each file's own TEI <availability> element
(not assumed to match Prakashasamhita just because both are GRETIL):
both state "Distributed under a Creative Commons Attribution-
NonCommercial-ShareAlike 4.0 International License" verbatim -- same
licence as Prakashasamhita, confirmed rather than presumed.

Output matches Prakashasamhita's own on-disk shape exactly (schema:
"generic", items: [{id, reference, shlokas: [{number, sanskrit_text}]}]),
not the DCS-import shape or the tools/kavya/ pipeline's schema -- this
keeps all 3 Pancharatra Samhita leaves in this repo internally consistent
with each other, which matters more here than matching either of those
other conventions.
"""
import collections
import json
import os
import re
import xml.etree.ElementTree as ET

from skrutable.transliteration import Transliterator

_translit = Transliterator(from_scheme="IAST", to_scheme="DEV")

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VENDOR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor")
SOURCE_NAME = "GRETIL (Sansknet Project)"
LICENCE = "CC BY-NC-SA 4.0"

REF_PATTERN = re.compile(r"[A-Za-z]+_(\d+)\.(\d+)")


def _localname(tag):
    return tag.rsplit("}", 1)[-1]


def _lg_text(lg_el):
    """Join an <lg>'s <l> children into one verse string, one pada per line."""
    lines = []
    for l_el in lg_el:
        if _localname(l_el.tag) != "l":
            continue
        text = "".join(l_el.itertext())
        text = re.sub(r"//\s*[A-Za-z]+_\d+\.\d+\s*//", "", text)  # strip trailing ref
        text = re.sub(r"\s+", " ", text).strip(" /")
        if text:
            lines.append(text)
    return " ".join(lines)


def parse_gretil_tei(xml_path, ref_prefix):
    """Yield (adhyaya:int, verse:int, iast_text:str) in document order,
    reading the ref directly off each <lg>'s last <l> (GRETIL's convention
    here: the reference closes the verse it names, e.g. '... // Vis_1.1 //'
    inside the final pada's own text, not as separate markup)."""
    tree = ET.parse(xml_path)
    root = tree.getroot()
    body = None
    for el in root.iter():
        if _localname(el.tag) == "body":
            body = el
            break
    if body is None:
        return
    for lg in body.iter():
        if _localname(lg.tag) != "lg":
            continue
        full_text = "".join(lg.itertext())
        m = REF_PATTERN.search(full_text)
        if not m:
            continue
        adhyaya, verse = int(m.group(1)), int(m.group(2))
        text = _lg_text(lg)
        if text:
            yield adhyaya, verse, text


def build(xml_filename, ref_prefix, out_rel_path, work_title_sa, work_title_en,
          source_url, note_extra=""):
    xml_path = os.path.join(VENDOR, xml_filename)
    units = list(parse_gretil_tei(xml_path, ref_prefix))
    by_adhyaya = collections.OrderedDict()
    for adhyaya, verse, text in sorted(units, key=lambda u: (u[0], u[1])):
        by_adhyaya.setdefault(adhyaya, []).append((verse, text))

    items = []
    for adhyaya in sorted(by_adhyaya):
        shlokas = []
        for verse, iast_text in by_adhyaya[adhyaya]:
            devanagari = _translit.transliterate(iast_text)
            shlokas.append({"number": verse, "sanskrit_text": devanagari})
        items.append({
            "id": "adhyaya%02d" % adhyaya,
            "reference": "%s, Adhyaya %d" % (work_title_en, adhyaya),
            "shlokas": shlokas,
        })

    out = {
        "schema": "generic",
        "default_author": "Traditionally revealed (Pancharatra Agama)",
        "source": "%s, %s" % (SOURCE_NAME, source_url),
        "licence": LICENCE,
        "note": ("%d adhyayas, %d shlokas total, Devanagari produced from the "
                 "GRETIL IAST e-text via skrutable's transliterator (pip "
                 "dependency, no vendored code).%s"
                 % (len(items), len(units), (" " + note_extra) if note_extra else "")),
        "items": items,
    }
    out_path = os.path.join(REPO, out_rel_path)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("%s: %d adhyayas, %d shlokas -> %s" % (work_title_en, len(items), len(units), out_rel_path))
    return len(units)


def main():
    build(
        "visvaksena.xml", "Vis",
        "dge/data/agama/pancharatra/pancharatra_samhitas/vishvaksena_samhita/data.json",
        "विष्वक्सेनसंहिता", "Vishvaksena Samhita",
        "https://gretil.sub.uni-goettingen.de/gretil/corpustei/sa_viSvaksenasaMhitA.xml",
    )
    build(
        "pauskara_27-43.xml", "Paus",
        "dge/data/agama/pancharatra/pancharatra_samhitas/paushkara_samhita/data.json",
        "पौष्करसंहिता", "Paushkara Samhita",
        "https://gretil.sub.uni-goettingen.de/gretil/corpustei/sa_pauSkarasaMhitA-27-43.xml",
        note_extra=("PARTIAL TEXT: only adhyayas 27-43 of the printed edition "
                     "(P.P. Apte, ed., Tirupati 2006) are available on GRETIL -- "
                     "adhyayas 1-26 and beyond 43 are not part of this e-text, "
                     "not a coverage gap introduced here."),
    )


if __name__ == "__main__":
    main()
