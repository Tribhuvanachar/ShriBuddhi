"""
wikisource.py — MediaWiki API reader, used for two things DGE cannot get
anywhere else:

  1. Whitney & Lanman's *Atharva-Veda Saṃhitā* (HOS 7–8, 1905) — the only
     per-mantra English source that systematically reports SĀYAṆA'S READINGS.
     en.wikisource.org/wiki/Atharva-Veda_Samhita/Book_{ROMAN}/Hymn_{N}
     Covers Books I–XIX; Book XX is not transcribed there (Griffith covers it).

  2. sa.wikisource.org — the one untested lead for the eleven minor smṛtis
     (Aṅgiras, Atri, Dakṣa, Hārīta, Likhita, Pracetas, Saṃvarta, Śaṅkha,
     Śātātapa, Uśanas, Yama), which exist nowhere else as e-text. CC BY-SA.

Both were unreachable from the authoring sandbox (Wikimedia is cache-only
through its proxy), so this module is written against the documented API and
tested on fixtures. `probe()` exists to answer "is it actually there?" from
Actions before a full run is attempted.

API used (no auth, no key):
    https://{lang}.wikisource.org/w/api.php
        ?action=parse&page={title}&prop=wikitext|text&format=json&formatversion=2
"""

from __future__ import annotations

import json
import re
from typing import Dict, List, Optional
from urllib.parse import quote

from bs4 import BeautifulSoup

from common import clean

ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
         "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII", "XIX", "XX"]


def api(lang: str = "en") -> str:
    return f"https://{lang}.wikisource.org/w/api.php"


def parse_url(title: str, lang: str = "en", prop: str = "text") -> str:
    return (f"{api(lang)}?action=parse&page={quote(title, safe='')}"
            f"&prop={prop}&format=json&formatversion=2")


def search_url(query: str, lang: str = "sa", limit: int = 50) -> str:
    return (f"{api(lang)}?action=query&list=search&srsearch={quote(query, safe='')}"
            f"&srlimit={limit}&format=json&formatversion=2")


def category_url(category: str, lang: str = "sa", limit: int = 500,
                 cmcontinue: str = "") -> str:
    """Members of a category, e.g. 'वर्गः:स्मृतयः' (the Smṛti category on
    sa.wikisource — confirmed to exist)."""
    u = (f"{api(lang)}?action=query&list=categorymembers"
         f"&cmtitle={quote(category, safe='')}&cmlimit={limit}"
         f"&cmtype=page|subcat&format=json&formatversion=2")
    return u + (f"&cmcontinue={quote(cmcontinue, safe='')}" if cmcontinue else "")


def prefix_url(prefix: str, lang: str = "sa", limit: int = 200) -> str:
    """All pages starting with `prefix` — used to find the subpages of a work
    that is split across several pages (e.g. 'यमस्मृतिः/')."""
    return (f"{api(lang)}?action=query&list=allpages"
            f"&apprefix={quote(prefix, safe='')}&aplimit={limit}"
            f"&format=json&formatversion=2")


def category_members(body: str):
    """-> ([{'title','ns'}], cmcontinue|'')"""
    try:
        d = json.loads(body)
    except Exception:                                     # noqa: BLE001
        return [], ""
    rows = [{"title": m["title"], "ns": m.get("ns", 0)}
            for m in (d.get("query") or {}).get("categorymembers", [])]
    return rows, (d.get("continue") or {}).get("cmcontinue", "")


def all_pages(body: str):
    try:
        d = json.loads(body)
    except Exception:                                     # noqa: BLE001
        return []
    return [p["title"] for p in (d.get("query") or {}).get("allpages", [])]


def html_from_parse(body: str) -> Optional[str]:
    """Pull the rendered HTML out of an action=parse response, or None if the
    page does not exist (the API returns an `error` object, not a 404)."""
    try:
        d = json.loads(body)
    except Exception:                                     # noqa: BLE001
        return None
    if "error" in d:
        return None
    return (d.get("parse") or {}).get("text")


def search_results(body: str) -> List[Dict]:
    try:
        d = json.loads(body)
    except Exception:                                     # noqa: BLE001
        return []
    return [{"title": r["title"], "size": r.get("size", 0)}
            for r in (d.get("query") or {}).get("search", [])]


# ---------------------------------------------------- Whitney Atharvaveda

def av_title(book: int, hymn: int) -> str:
    return f"Atharva-Veda Samhita/Book_{ROMAN[book]}/Hymn_{hymn}"


_VERSE_NUM = re.compile(r"^\s*(\d{1,3})\s*[.)]\s*")


def parse_whitney_hymn(html: str) -> Dict[int, Dict[str, str]]:
    """-> {verse_no: {'translation': str, 'commentary': str}}

    Whitney's layout per verse is a translation paragraph followed by his
    philological note. The note is what carries Sāyaṇa ("Ppp. reads paryanti
    in a…", "SPP. with the majority of his authorities…"), so it is kept as a
    separate field rather than concatenated — a reader wants the translation
    plain and the apparatus optional."""
    soup = BeautifulSoup(html or "", "html.parser")
    for sel in ("table", "sup.reference", "div.reflist", "span.mw-editsection",
                "div.noprint", "style", "script"):
        for n in soup.select(sel):
            n.decompose()

    out: Dict[int, Dict[str, str]] = {}
    current = None
    for p in soup.find_all(["p", "dd", "blockquote"]):
        t = clean(p.get_text(" ", strip=True))
        if not t:
            continue
        m = _VERSE_NUM.match(t)
        if m:
            current = int(m.group(1))
            out.setdefault(current, {"translation": "", "commentary": ""})
            body = t[m.end():].strip()
            if body:
                out[current]["translation"] = body
        elif current is not None:
            slot = "translation" if not out[current]["translation"] else "commentary"
            out[current][slot] = clean((out[current][slot] + " " + t).strip())
    return out


# --------------------------------------------------- sa.wikisource probing

MINOR_SMRITIS = [
    ("angiras_smriti", "अङ्गिरःस्मृतिः"),
    ("atri_smriti", "अत्रिस्मृतिः"),
    ("daksha_smriti", "दक्षस्मृतिः"),
    ("harita_smriti", "हारीतस्मृतिः"),
    ("likhita_smriti", "लिखितस्मृतिः"),
    ("pracetas_smriti", "प्रचेतःस्मृतिः"),
    ("samvarta_smriti", "संवर्तस्मृतिः"),
    ("shankha_smriti", "शङ्खस्मृतिः"),
    ("shatatapa_smriti", "शातातपस्मृतिः"),
    ("ushanas_smriti", "उशनःस्मृतिः"),
    ("yama_smriti", "यमस्मृतिः"),
]

# Nibandhas and commentaries number by chapter.verse ("१.१", "१२.४५"), not a
# bare running count -- the original digits-only pattern silently matched
# NOTHING on pages using that convention (Mitakshara's Sadacaradhyaya: 302
# real "॥ chapter.verse ॥" markers, 1 match under the old pattern), so the
# whole page fell through as "no verses" even though it was full of real
# commentary. `[.,]` covers both a decimal chapter.verse and a comma-joined
# multi-ref close; a bare digit run still matches as before.
VERSE_END = re.compile(r"॥\s*([\d०-९]+(?:[.,][\d०-९]+)*)\s*॥")
_DEV_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")

DEVANAGARI = re.compile(r"[ऀ-ॿ]")
MIN_CHUNK_CHARS = 8
MIN_DEVANAGARI_RATIO = 0.55

# Editorial/critical-apparatus lines, not text -- the shape this project's
# other importers already gate on (dv_parse.py, importers/shankara_bhashya.py):
# variant-reading notes ("इत्यधिक पाठ. क. पु."), footnote-style citations to
# a sibling smriti opening with a bare number ("२. दक्षस्मृ० अ० २ श्लो २९"),
# and scan/tool boilerplate ("diCrunch", "स्रोत" source-credit lines). A whole
# chunk this matches is dropped; chunk-internal footnote markers are not
# swept (that needs per-corpus review -- see the PENDING.md writeup).
JUNK_LINE = re.compile(
    r"^\s*(?:[\d०-९]+\s*[.,)]\s*\S+स्मृ|इत्यधिक\s+पाठ|पाठान्तर|स्रोत$|"
    r"देवनागरी\s+कर्तुं|diCrunch|Diacritic\s+and\s+Indic)",
)


def _devanagari_ratio(s: str) -> float:
    letters = [c for c in s if c.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for c in letters if DEVANAGARI.match(c)) / len(letters)


def parse_devanagari_verses(text: str) -> List[Dict]:
    """Split a Sanskrit Wikisource page body into verses/commentary units on
    the trailing '॥ N ॥' or '॥ chapter.verse ॥' marker that closes each one.
    -> [{'number', 'text'}]. Drops a chunk outright if it is a single
    editorial/footnote line (JUNK_LINE) or reads as scraped chrome/OCR
    garbage rather than Sanskrit (too short, or below MIN_DEVANAGARI_RATIO)."""
    out: List[Dict] = []
    prev = 0
    for m in VERSE_END.finditer(text or ""):
        body = clean(text[prev:m.start()])
        prev = m.end()
        if not body or JUNK_LINE.match(body):
            continue
        if len(body) < MIN_CHUNK_CHARS or _devanagari_ratio(body) < MIN_DEVANAGARI_RATIO:
            continue
        num_raw = m.group(1).translate(_DEV_DIGITS)
        number = int(num_raw) if num_raw.isdigit() else num_raw
        out.append({"number": number, "text": body})
    return out


def page_body_text(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    for sel in ("table", "sup.reference", "div.reflist", "span.mw-editsection",
                "div.noprint", "style", "script", "ol.references"):
        for n in soup.select(sel):
            n.decompose()
    return clean(soup.get_text("\n", strip=True))
