"""Valmiki Ramayana -> itihasa/ramayana/<kanda>/data.json
Source: bombay.indology.info BORI critical ed. (native Devanagari), coded 'KSSSVVVpada'.
"""
import re, collections
from common import http_get, write_grantha

URL   = "https://bombay.indology.info/ramayana/text/UD/Ram%02d.txt"
KANDA = {1:"bala_kanda",2:"ayodhya_kanda",3:"aranya_kanda",4:"kishkindha_kanda",
         5:"sundara_kanda",6:"yuddha_kanda",7:"uttara_kanda"}
LINE  = re.compile(r"^(\d{7})([a-z])\s+(.+)$")   # 7 digits: K SSS VVV

def parse(text, kanda):
    sargas = collections.OrderedDict()
    for ln in text.splitlines():
        m = LINE.match(ln.strip())
        if not m:
            continue
        num, _pada, t = m.group(1), m.group(2), m.group(3).strip()
        if int(num[0]) != kanda:
            continue
        sarga, verse = int(num[1:4]), int(num[4:7])
        sargas.setdefault(sarga, collections.OrderedDict()).setdefault(verse, []).append(t)
    items = []
    for sarga, verses in sargas.items():
        sh = [{"number": v, "sanskrit_text": " ".join(pl)} for v, pl in verses.items()]
        items.append({"id": f"sarga_{sarga:03d}",
                      "reference": f"{KANDA[kanda].replace('_',' ').title()}, Sarga {sarga}",
                      "shlokas": sh})
    return items

def run():
    for k in range(1, 8):
        print(f"{KANDA[k]} …")
        items = parse(http_get(URL % k), k)
        # /mula -- matches the layer folder already scaffolded in the
        # catalog (leaves room for a commentary layer alongside it later).
        write_grantha(f"itihasa/ramayana/{KANDA[k]}/mula", "itihasa_purana_text", "Maharshi Valmiki", items)

if __name__ == "__main__":
    run()
