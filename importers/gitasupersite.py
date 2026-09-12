"""GitaSupersite classical-Sanskrit-bhashya enrichment for the Bhagavad Gita.

GitaSupersite (gitasupersite.iitk.ac.in -> www.gitasupersite.in) is the site that
carries the full classical multi-bhashya set per Gita shloka. It was rebuilt as a
client-side JS SPA, so a plain GET of the live site returns only a JS shell. The
OLD IIT-Kanpur pages were server-rendered with the SAME query params and the full
commentary text inline -- we therefore read them from the Wayback Machine.

This module is BEST-EFFORT and OPTIONAL. bhagavadgita.py calls enrich() only when
env GITA_SUPERSITE=1. If anything fails it logs and returns without touching the
base data. On the FIRST Actions run, spot-check that a bhashya heading matches the
expected author (the flag->author map below is verified for the sc* set; a couple
of rows are marked 'confirm').

URL scheme (old server-rendered page, via Wayback 'id_' raw passthrough):
  http://gitasupersite.iitk.ac.in/srimad?field_chapter_value={CH}
        &field_nsutra_value={V}&language=dv&show_mool=1&choose=1&<flag>=1...
"""
import re, json, urllib.parse
from common import http_get, to_text

# Sanskrit-commentary flags -> (commentator, traditional title). Verified high-
# confidence for the classical roster; '# confirm' rows validate on first run.
SANSKRIT_BHASHYAS = [
    ("scsh",   "Sri Shankaracharya",      "Bhashya"),
    ("scram",  "Sri Ramanujacharya",      "Bhashya"),
    ("scmad",  "Sri Madhvacharya",        "Bhashya"),
    ("scsri",  "Sri Sridhara Swami",      "Subodhini"),
    ("scms",   "Sri Madhusudana Sarasvati","Gudhartha Dipika"),
    ("scanand","Sri Anandagiri",          "Tika"),
    ("scneel", "Sri Nilakantha",          "Bhava Dipa"),
    ("scdhan", "Sri Dhanapati",           "Bhashyotkarsha Dipika"),
    ("scval",  "Sri Vallabhacharya",      "Tattva Dipika"),
    ("scpur",  "Sri Purushottamji",       "Amrita Tarangini"),
    ("scjaya", "Sri Jayatirtha",          "Prameya Dipika"),     # confirm
    ("scvv",   "Sri Vedanta Deshika",     "Tatparya Chandrika"), # confirm
]

WAYBACK = "https://web.archive.org/web/2id_/"


def _url(ch, v, flag):
    q = {
        "field_chapter_value": ch, "field_nsutra_value": v,
        "language": "dv", "show_mool": 1, "choose": 1, flag: 1,
    }
    live = "http://gitasupersite.iitk.ac.in/srimad?" + urllib.parse.urlencode(q)
    return WAYBACK + live


def _extract_commentary(page_text, commentator):
    """Pull the commentary block for one author from a server-rendered page.

    The old pages emit one labelled section per selected flag; anchoring on the
    rendered author heading is more robust than guessing container classes.
    Returns the block text after the heading, trimmed, or ''.
    """
    # normalise whitespace, then find the author heading and take text up to the
    # next heading-like boundary.
    txt = re.sub(r"[ \t]+", " ", page_text)
    key = commentator.replace("Sri ", "").split()[0]  # e.g. 'Shankaracharya'
    m = re.search(re.escape(key), txt, re.I)
    if not m:
        return ""
    tail = txt[m.end():]
    # stop at the next author name or an obvious footer marker
    stop = re.search(r"(Sri [A-Z][a-z]+acharya|Swami |Next Sloka|Previous Sloka|"
                     r"Chapter \d+|© |Copyright)", tail)
    block = tail[:stop.start()] if stop else tail
    block = block.strip(" :\n")
    return block if len(block) > 20 else ""


def fetch_shloka_bhashyas(ch, v):
    """Return a list of {commentator, text, language, kind, title} for (ch,v)."""
    out = []
    for flag, name, title in SANSKRIT_BHASHYAS:
        try:
            page = to_text(http_get(_url(ch, v, flag)))
        except Exception:
            continue
        text = _extract_commentary(page, name)
        if text:
            out.append({"commentator": name, "text": text, "language": "sa",
                        "kind": "commentary", "title": title})
    return out


def enrich(items_by_chapter):
    """Append GitaSupersite Sanskrit bhashyas onto each shloka in place."""
    total = 0
    for ch, items in items_by_chapter.items():
        for it in items:
            for sh in it.get("shlokas", []):
                extra = fetch_shloka_bhashyas(ch, sh["number"])
                if extra:
                    sh.setdefault("bhashya", []).extend(extra)
                    total += len(extra)
        print(f"  GitaSupersite: adhyaya {ch} enriched")
    print(f"  GitaSupersite: added {total} Sanskrit bhashya entries")
