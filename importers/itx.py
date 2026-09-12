"""Generic sanskritdocuments ITX importer (ITRANS -> Devanagari). Handles .itx
mahakavya files whose verses end with '|| canto\\.verse||' and whose sargas start
with '\\section{sargaH N ...}'. Run:  python importers/dispatch.py <id>
"""
import re, collections
from common import http_get, itrans_to_dev, write_grantha

# /mula target -- matches the layer-folder convention used for the other
# itihasa/kavya entries (leaves room for a commentary layer later).
ITX = {
  "kumarasambhava": dict(name="Kumarasambhava", author="Kalidasa", unit="sarga",
      schema="itihasa_purana_text", target="kavya_alankara/kumarasambhava/mula",
      url="https://sanskritdocuments.org/doc_z_misc_major_works/kumArasambhavam.itx"),
  "kiratarjuniya":  dict(name="Kiratarjuniya", author="Bharavi", unit="sarga",
      schema="itihasa_purana_text", target="kavya_alankara/kiratarjuniya/mula",
      url="https://sanskritdocuments.org/doc_z_misc_major_works/kirAtArjunIyam.itx"),
}

SEC  = re.compile(r"\\section\{[^}]*?(\d+)")
VEND = re.compile(r"\|\|\s*(\d+)(?:\\?\.(\d+))?\s*\|\|")

def parse(itx, name, unit):
    sarga = 1; buf = []; cantos = collections.OrderedDict()
    seen_first_verse = False
    for raw in itx.splitlines():
        s = raw.strip()
        if not s: continue
        ms = SEC.search(raw)
        if ms: sarga = int(ms.group(1)); buf = []; continue
        if s[0] in "%#\\" : continue          # ITRANS command / comment / preamble
        if s.startswith("iti "): buf = []; continue   # colophon
        mv = VEND.search(raw)
        if mv:
            if not seen_first_verse:
                # Same class of bug confirmed for real in gretil.py's parser
                # (see common.py/gretil.py): a source's un-prefixed preamble
                # text before the first verse marker isn't verse content,
                # even if none of the usual comment-prefix checks catch it.
                buf = []
                seen_first_verse = True
            buf.append(raw[:mv.start()].strip())
            itrans = " ".join(x for x in buf if x).strip()
            # "\-" is a LaTeX-style explicit-hyphenation-point marker some
            # sanskritdocuments.org .itx sources keep inline (a valid break
            # point for print line-wrapping, not real content) -- it isn't
            # caught by the "line starts with \" skip above since it can sit
            # mid-line, mid-word. itrans_to_dev() passes unrecognized
            # sequences through literally, so it survives into the output
            # as a stray backslash-hyphen splitting a word. Confirmed for
            # real on kiratarjuniya (~50% of verses affected).
            itrans = itrans.replace("\\-", "")
            dev = itrans_to_dev(itrans)
            if mv.group(2) is not None:        # ||canto.verse||
                sarga = int(mv.group(1)); verse = int(mv.group(2))
            else:                               # ||verse||
                verse = int(mv.group(1))
            cantos.setdefault(sarga, []).append({"number": verse, "sanskrit_text": dev})
            buf = []
        else:
            buf.append(s)
    return [{"id": f"{unit}_{c:02d}", "reference": f"{name}, {unit.title()} {c}", "shlokas": sh}
            for c, sh in cantos.items()]

def run(tid):
    spec = ITX[tid]
    items = parse(http_get(spec["url"]), spec["name"], spec["unit"])
    write_grantha(spec["target"], spec["schema"], spec["author"], items)
