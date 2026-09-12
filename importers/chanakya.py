"""Sanskrit Documents ITX importer for the two distinct Chanakya nIti texts.
Neither matches itx.py's generic kavya parser (sarga headers via
'\\section{sargaH N ...}', verse markers '||canto.verse||'): chANakyanIti
marks verses inline as '|| CH\\-V' with no section headers at all, and
chANakyasUtra marks adhyaya boundaries as prose ("atha prathamo.adhyAyaH ..")
and sutras as '.. N..' (whose stated numbers run out of sequence/repeat in
the source itself -- positional numbering is used here instead, the same
convention core.js's own normalization already uses for every other flat
text in this corpus). Run:  python importers/dispatch.py chanakya_niti
"""
import re, collections
from common import http_get, itrans_to_dev, write_grantha

CHANAKYA = {
  "chanakya_niti": dict(
      name="Chanakya Niti", author="Chanakya", target="nitishastra/chanakya_niti",
      url="https://sanskritdocuments.org/doc_z_misc_major_works/chANakyanItisort.itx"),
  "chanakya_sutra": dict(
      name="Chanakya Sutra", author="Chanakya (Kautilya)", target="nitishastra/chanakya_sutra",
      url="https://sanskritdocuments.org/doc_z_misc_major_works/chANakyasUtra.itx"),
}

# sanskritdocuments.org's own stated norm (see the .itx header comment
# fetched at import time): personal study/research use, not to be
# reposted/repackaged for commercial purposes. No SPDX-style licence name
# -- recorded as the site's own stated terms, same as this project already
# does for every other sanskritdocuments.org import.
SOURCE_NOTE = ("Sanskrit Documents (sanskritdocuments.org), transliterated by "
               "Sunder Hattangadi. Site's stated norm: personal study/research use, "
               "not for commercial redistribution.")

# Matches its nitishastra/upaveda siblings (hitopadesha, kamasutra), both
# already imported under "generic" -- not the more specific
# itihasa_purana_text/grantha_mula_text schemas, which describe narrative
# epics or a Sarvamoola work's own mula/tika layering, neither of which
# fits a standalone didactic verse/aphorism collection like this one.
SCHEMA = "generic"

NITI_VEND = re.compile(r"\|\|\s*(\d+)\\-(\d+)\s*$")

def parse_niti(itx, name):
    buf = []
    chapters = collections.OrderedDict()
    seen_first = False
    for raw in itx.splitlines():
        s = raw.strip()
        if not s: continue
        if s[0] in "%#\\": continue          # ITRANS command / comment / preamble / \medskip\hrule separators
        m = NITI_VEND.search(raw)
        if m:
            if not seen_first:
                buf = []                      # preamble text before the first verse marker isn't verse content
                seen_first = True
            buf.append(raw[:m.start()].strip())
            itrans = " ".join(x for x in buf if x).strip()
            # "\-" is a LaTeX-style explicit-hyphenation-point marker some
            # sanskritdocuments.org .itx sources keep inline for print
            # line-wrapping -- itx.py's kavya parser found and fixed the
            # same artifact on kiratarjuniya; confirmed present here too
            # (chanakya_niti's final verse: "sarvajanto\- reko" wrongly
            # splitting "sarvajantoreko" across the line break).
            itrans = itrans.replace("\\-", "")
            dev = itrans_to_dev(itrans)
            ch, v = int(m.group(1)), int(m.group(2))
            chapters.setdefault(ch, []).append({"number": v, "sanskrit_text": dev})
            buf = []
        else:
            buf.append(s)
    return [{"id": f"adhyaya_{c:02d}", "reference": f"{name}, Adhyaya {c}", "shlokas": sh}
            for c, sh in chapters.items()]

SUTRA_VEND = re.compile(r"\.\.\s*\d+\s*\.\.?\s*$")

def parse_sutra(itx, name):
    buf = []
    chapters = collections.OrderedDict()
    ch = 0
    seq_in_ch = 0
    seen_first = False
    for raw in itx.splitlines():
        s = raw.strip()
        if not s: continue
        if s[0] in "%#\\": continue
        if "adhyAyaH" in s:
            # "atha prathamo.adhyAyaH .." opens a chapter; "iti dvitIyo.adhyAyaH .."
            # / "ityaShTamo.adhyAyaH .." (sandhi, no space after "iti") closes one --
            # both are structural markers, not verse content, and only the "atha"
            # form should advance the chapter counter. Case-insensitive: sandhi
            # capitalizes the next letter ("athAShTamo" for atha+aShTama, adhyaya
            # 8) -- a plain startswith("atha") silently dropped that whole
            # chapter (7 chapters found instead of the real 8), caught by
            # checking the actual chapter count against the source's own 8
            # "atha...adhyAyaH" headers rather than assuming the parse was right.
            if s.lower().startswith("atha"):
                ch += 1
                seq_in_ch = 0
            buf = []
            continue
        m = SUTRA_VEND.search(raw)
        if m:
            if not seen_first:
                buf = []
                seen_first = True
            buf.append(raw[:m.start()].strip())
            itrans = " ".join(x for x in buf if x).strip()
            itrans = itrans.replace("\\-", "")
            dev = itrans_to_dev(itrans)
            seq_in_ch += 1
            chapters.setdefault(ch, []).append({"number": seq_in_ch, "sanskrit_text": dev})
            buf = []
        else:
            buf.append(s)
    return [{"id": f"adhyaya_{c:02d}", "reference": f"{name}, Adhyaya {c}", "shlokas": sh}
            for c, sh in chapters.items()]

def run(tid):
    spec = CHANAKYA[tid]
    raw = http_get(spec["url"])
    if tid == "chanakya_niti":
        items = parse_niti(raw, spec["name"])
    else:
        items = parse_sutra(raw, spec["name"])
    write_grantha(spec["target"], SCHEMA, spec["author"], items,
                  source_url=spec["url"], source_note=SOURCE_NOTE)
