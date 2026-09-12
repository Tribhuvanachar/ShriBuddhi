"""Kamandakiya Nitisara -- Jesse Knutson's Murty Classical Library edition
(refined from T. Ganapati Sastri 1912), proofread by Patrick Olivelle, UT
Austin South Asia Institute Open Educational Resources. Plain-text export
of the source Google Doc, explicitly CC BY 4.0 (stated in the document's
own header, verified live at import time, not assumed from prior notes).
Run:  python importers/dispatch.py kamandaki
"""
import re, collections
from common import http_get, iast_to_dev, write_grantha

DOC_ID = "1OFWLyjXMqqiHTBg3WqvFJsWuDhlEQgE62k_7Ik2BTYQ"
URL = f"https://docs.google.com/document/d/{DOC_ID}/export?format=txt"
SOURCE_NOTE = ("Nītisāra of Kāmandaki, ed. Jesse Knutson (Murty Classical Library, "
               "Harvard UP), proofread by Patrick Olivelle; UT Austin South Asia "
               "Institute Open Educational Resources. Explicitly CC BY 4.0 per the "
               "document's own stated license.")
LICENCE = "CC BY 4.0"
TARGET = "nitishastra/kamandakiya_nitisara"
SCHEMA = "generic"

# Isolated on its own line, no other content -- e.g. "prathamaḥ sargaḥ",
# "viṃśaḥ sargaḥ". Checked against the real document: exactly 20 such
# lines, none of which is a false positive against ordinary verse text.
SARGA_HDR = re.compile(r"^\S+\s+sarga[ḥh]$")
VEND = re.compile(r"\|\|\s*(\d+)\s*\|\|\s*$")

def parse(txt):
    lines = txt.splitlines()
    sarga = 0
    buf = []
    chapters = collections.OrderedDict()
    seen_first_sarga = False
    for raw in lines:
        s = raw.strip()
        if not s:
            continue
        if SARGA_HDR.match(s):
            sarga += 1
            seen_first_sarga = True
            buf = []
            continue
        if not seen_first_sarga:
            continue  # licence/editor preamble before "prathamaḥ sargaḥ"
        if "prakaraṇam" in s:
            # A topic-heading subline within the sarga (e.g.
            # "indriyajayaprakaraṇam") -- several sargas carry more than
            # one of these mid-chapter (confirmed: sarga 20 alone has two),
            # so this deliberately does NOT start a new grouping the way a
            # sarga header does; it is metadata to skip, not a boundary.
            buf = []
            continue
        m = VEND.search(raw)
        if m:
            buf.append(raw[:m.start()].strip())
            iast = " ".join(x for x in buf if x).strip()
            # Google Docs auto-substitutes a "smart quote" (U+2019) for the
            # ASCII apostrophe indic_transliteration's IAST scheme expects
            # for avagraha -- confirmed live: left unconverted, "yo
            # 'dhītavān" silently kept its bare apostrophe instead of
            # becoming "यो ऽधीतवान्". A stray "[1]"-style footnote marker
            # (one inline occurrence in the real document, referencing a
            # variant-reading note in the trailing appendix) is stripped
            # too -- it is apparatus, not text.
            iast = iast.replace("’", "'")
            iast = re.sub(r"\[\d+\]", "", iast)
            dev = iast_to_dev(iast)
            verse = int(m.group(1))
            chapters.setdefault(sarga, []).append({"number": verse, "sanskrit_text": dev})
            buf = []
        else:
            buf.append(s)
    return [{"id": f"sarga_{c:02d}", "reference": f"Kamandakiya Nitisara, Sarga {c}", "shlokas": sh}
            for c, sh in chapters.items()]

def run(_tid=None):
    items = parse(http_get(URL))
    write_grantha(TARGET, SCHEMA, "Kamandaki", items,
                  source_url=URL, source_note=SOURCE_NOTE, licence=LICENCE)
