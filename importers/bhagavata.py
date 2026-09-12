"""Srimad Bhagavata Purana -> purana/bhagavata_purana/skandha_NN/data.json
Source: GRETIL (IAST), lines coded 'BhP_SS.AA.VVV/pada'. Converts IAST->Devanagari.
"""
import re, collections
from common import http_get, strip_html, iast_to_dev, write_grantha

URL  = "http://gretil.sub.uni-goettingen.de/gretil/1_sanskr/3_purana/bhagp/bhp_%02du.htm"
LINE = re.compile(r"BhP_(\d+)\.(\d+)\.(\d+)\s*/\s*(\d+)\s+(.+)")

def parse(text, skandha):
    verses = collections.OrderedDict()          # (adhyaya, verse) -> [(pada, text)]
    for ln in text.splitlines():
        m = LINE.search(ln.strip())
        if not m:
            continue
        S, A, V, pada, t = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)), m.group(5).strip()
        if S != skandha:
            continue
        verses.setdefault((A, V), []).append((pada, t))
    adhyayas = collections.OrderedDict()
    for (A, V), padas in verses.items():
        padas.sort()
        adhyayas.setdefault(A, []).append({"number": V, "sanskrit_text": iast_to_dev(" ".join(t for _, t in padas))})
    return [{"id": f"adhyaya_{A:02d}", "reference": f"Skandha {skandha}, Adhyaya {A}", "shlokas": sh}
            for A, sh in adhyayas.items()]

def run():
    for sk in range(1, 13):
        print(f"skandha {sk} …")
        items = parse(strip_html(http_get(URL % sk)), sk)
        write_grantha(f"purana/bhagavata_purana/skandha_{sk:02d}", "itihasa_purana_text", "Maharshi Veda Vyasa", items)

if __name__ == "__main__":
    run()
