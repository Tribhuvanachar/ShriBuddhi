"""Valmiki Ramayana WITH word-to-word meaning + English translation
   -> itihasa/ramayana/<kanda>/saartha/data.json  (a NEW layer alongside /mula)

Source: valmikiramayan.net  (Desiraju Hanumanta Rao / K.M.K. Murthy).
        The famous word-for-word Valmiki Ramayana. Static .htm pages, no robots
        restriction. We read the ROMAN (IAST) page per sarga -- it carries
        all-ASCII verse ids (|| K-S-V ||), the *word* = meaning; gloss run, and a
        running English translation, so it parses far more reliably than the
        Devanagari page (whose verse numbers render in Devanagari numerals). The
        IAST verse is transliterated to Devanagari for sanskrit_text and the
        original IAST kept in `transliteration`.

        Kandas 1-6 are covered here; Uttara Kanda is NOT on this site
        (see NOTE at bottom -- pull it from valmiki.iitk.ac.in separately).

Why a separate `saartha` layer (not merged into /mula):
        /mula holds the BORI critical edition (different verse numbering). This
        site uses a different edition, so its verses cannot be merged onto BORI
        verse ids 1:1. We keep it as a self-contained parallel layer -- exactly
        the "commentary layer alongside mula" the catalog was scaffolded for.

Per-shloka shape written (itihasa_purana_text schema):
        {number, sanskrit_text (Devanagari), transliteration (IAST),
         padaccheda (word-by-word gloss), artha (English translation)}
"""
import re
from common import http_get, to_text, write_grantha

try:
    from common import iast_to_dev
except Exception:                       # keep importable for --dry parse tests
    def iast_to_dev(s):
        raise RuntimeError("indic-transliteration missing")

BASE = "https://www.valmikiramayan.net"

# kanda slug (our data tree) -> (site directory, contents-page basename)
KANDAS = [
    ("bala_kanda",       "baala",   "baala_contents"),
    ("ayodhya_kanda",    "ayodhya", "ayodhya_contents"),
    ("aranya_kanda",     "aranya",  "aranya_contents"),
    ("kishkindha_kanda", "kish",    "kishkindha_contents"),
    ("sundara_kanda",    "sundara", "sundara_contents"),
    ("yuddha_kanda",     "yuddha",  "yuddha_contents"),
    # uttara_kanda: absent on valmikiramayan.net -- handled elsewhere.
]

VERSE_LOCATOR = re.compile(r"verse\s*locator", re.I)
VID_END  = re.compile(r"\|\|\s*(\d+)-(\d+)-(\d+)\s*(?:\|\|)?")  # || K-S-V [||] ends the sanskrit
VID_TAIL = re.compile(r"\[\s*(\d+)-(\d+)-(\d+)\s*\]")       # [K-S-V] tail of the translation
GLOSS    = re.compile(r"\*\s*(.+?)\s*\*\s*=\s*([^;*]+)")    # *word* = meaning
# Discovery keys off the per-sarga FRAME filename '<prefix>_<N>_frame.htm',
# which is uniform across all six kandas (see _sarga_page_url's docstring),
# instead of the '/sargaN/' path segment. This is deliberate: the Sundara
# Kanda contents page writes its links with single/loosely quoted hrefs (and,
# unlike the other five, does not reliably carry the literal 'sargaN' token in
# a double-quoted href), so the original  href="...sarga\d+...\.htm"  pattern
# matched zero links there. Matching the frame filename with tolerant quoting
# (double, single, or none, with optional spaces around '=') recovers Sundara
# while producing identical results for the five kandas that already worked.
# The captured groups stay (full_href, sarga_number) so the callers below and
# _sarga_page_url() are unchanged.
SARGA_HREF = re.compile(r'href\s*=\s*["\']?([^"\'>\s]*?(\d+)_frame\.htm)', re.I)


def _clean_iast(s):
    # The site marks sandhi/compounds with ^, ^^, ~ -- strip so transliteration
    # doesn't choke, and collapse whitespace.
    s = s.replace("^^", "").replace("^", "").replace("~", "")
    return re.sub(r"\s+", " ", s).strip(" |-")


def _sarga_page_url(kdir, frame_href, sarga_no):
    """Frame href '.../baala/sarga1/bala_1_frame.htm' -> the utf8 roman page
    '.../utf8/baala/sarga1/<prefix>roman<N>.htm', prefix = leading alpha run."""
    base = frame_href.rsplit("/", 1)[-1]
    m = re.match(r"([a-zA-Z]+)", base)
    prefix = m.group(1) if m else kdir
    return f"{BASE}/utf8/{kdir}/sarga{sarga_no}/{prefix}roman{sarga_no}.htm"


def discover_sargas(kdir, contents_base):
    """Ordered {sarga_no: roman_page_url} read from the kanda contents page."""
    url = f"{BASE}/{kdir}/{contents_base}.htm"
    try:
        html = http_get(url)
    except Exception as e:
        print(f"  ! contents page failed ({url}): {e}")
        return {}
    found = {}
    for href, sno in SARGA_HREF.findall(html):
        sno = int(sno)
        found.setdefault(sno, _sarga_page_url(kdir, href, sno))
    return dict(sorted(found.items()))


def parse_sarga(text, sarga_no, transliterate=True):
    """Parse one roman sarga page's plain text into a list of shloka dicts.

    Splitting on the literal 'Verse Locator' anchor gives one block per verse;
    each block is  <IAST sanskrit> || K-S-V ||  <*w*=m; ...>  <english> [K-S-V].
    """
    shlokas = []
    for blk in VERSE_LOCATOR.split(text):
        mend = VID_END.search(blk)
        # Sanskrit ends at '|| K-S-V ||'; if that marker is missing, fall back
        # to the start of the gloss run (first '*'); else skip (page chrome).
        if mend:
            v = int(mend.group(3))
            sanskrit = _clean_iast(blk[:mend.start()])
            rest = blk[mend.end():]
        else:
            star = blk.find("*")
            mtail = VID_TAIL.search(blk)
            if star == -1 or not mtail:
                continue
            v = int(mtail.group(3))
            sanskrit = _clean_iast(blk[:star])
            rest = blk[star:]
        glosses = GLOSS.findall(rest)
        padaccheda = "; ".join(f"{w.strip()} = {m.strip()}" for w, m in glosses)
        if glosses:
            last = rest.rfind(";")
            tail = rest[last + 1:] if last != -1 else ""
        else:
            tail = rest
        mt = VID_TAIL.search(tail)
        translation = re.sub(r"\s+", " ", (tail[:mt.start()] if mt else tail)).strip()
        if not sanskrit:
            continue
        item = {"number": v}
        if transliterate:
            try:
                item["sanskrit_text"] = iast_to_dev(sanskrit)
                item["transliteration"] = sanskrit
            except Exception:
                item["sanskrit_text"] = sanskrit
        else:
            item["sanskrit_text"] = sanskrit
        if padaccheda:  item["padaccheda"] = padaccheda
        if translation: item["artha"] = translation
        shlokas.append(item)
    return shlokas


def run():
    for kslug, kdir, contents_base in KANDAS:
        print(f"{kslug} ...")
        sargas = discover_sargas(kdir, contents_base)
        if not sargas:
            print(f"  ! no sargas discovered for {kslug}; skipping")
            continue
        items = []
        for sno, url in sargas.items():
            try:
                page = to_text(http_get(url))
            except Exception as e:
                print(f"  ! sarga {sno} fetch failed: {e}")
                continue
            sh = parse_sarga(page, sno)
            if not sh:
                print(f"  ~ sarga {sno}: no verses parsed ({url})")
                continue
            items.append({
                "id": f"sarga_{sno:03d}",
                "reference": f"{kslug.replace('_',' ').title()}, Sarga {sno}",
                "shlokas": sh,
            })
            print(f"  sarga {sno}: {len(sh)} shlokas")
        if items:
            write_grantha(f"itihasa/ramayana/{kslug}/saartha",
                          "itihasa_purana_text", "Maharshi Valmiki", items)


if __name__ == "__main__":
    run()
