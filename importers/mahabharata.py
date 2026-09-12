"""Mahabharata -> itihasa/mahabharata/<parva>/data.json
Source: bombay.indology.info BORI critical ed. (native Devanagari), coded 'BBAAAVVVpada'.
NOTE: add the itihasa/mahabharata/<parva> nodes to taxonomy.json so they render.
Only the constituted text (lowercase pada letters) is taken; capital-letter
codes = star/interpolated passages and are skipped.
"""
import re, collections
from common import http_get, write_grantha

URL   = "https://bombay.indology.info/mahabharata/text/UD/MBh%02d.txt"
# "vana" (not "aranyaka") for book 3 -- matches the parva slug already
# scaffolded in data/taxonomy.json and data/library.json; a different slug
# here would write real data to a path nothing in the catalog points at.
PARVA = {1:"adi",2:"sabha",3:"vana",4:"virata",5:"udyoga",6:"bhishma",7:"drona",
         8:"karna",9:"shalya",10:"sauptika",11:"stri",12:"shanti",13:"anushasana",
         14:"ashvamedhika",15:"ashramavasika",16:"mausala",17:"mahaprasthanika",18:"svargarohana"}
LINE  = re.compile(r"^(\d{8})([a-z])\s+(.+)$")   # 8 digits: BB AAA VVV ; lowercase pada = constituted

def parse(text, book):
    adh = collections.OrderedDict()
    for ln in text.splitlines():
        m = LINE.match(ln.strip())
        if not m:
            continue
        num, _pada, t = m.group(1), m.group(2), m.group(3).strip()
        if int(num[0:2]) != book:
            continue
        chapter, verse = int(num[2:5]), int(num[5:8])
        adh.setdefault(chapter, collections.OrderedDict()).setdefault(verse, []).append(t)
    items = []
    for ch, verses in adh.items():
        sh = [{"number": v, "sanskrit_text": " ".join(pl)} for v, pl in verses.items()]
        items.append({"id": f"adhyaya_{ch:03d}", "reference": f"{PARVA[book].title()} Parva, Adhyaya {ch}", "shlokas": sh})
    return items

def run():
    for b in range(1, 19):
        print(f"{PARVA[b]} parva …")
        items = parse(http_get(URL % b), b)
        # /mula -- matches the layer folder already scaffolded in the
        # catalog (leaves room for a commentary layer alongside it later).
        write_grantha(f"itihasa/mahabharata/{PARVA[b]}_parva/mula", "itihasa_purana_text", "Maharshi Veda Vyasa", items)

if __name__ == "__main__":
    run()
