"""Sanskrit Wikisource importer for four Ayurveda classics -- clean,
volunteer-transcribed text (not OCR), confirmed live per this project's
"only clean transcribed text, note source+licence" sourcing policy.
Licence: Wikisource content is CC BY-SA (the site's standard licence for
user-contributed text; no per-page override found on any of the four).

Each text's own wikitext markup differs enough that a single generic
parser would be fragile, so each gets its own small function; all share
fetch_wikitext() (MediaWiki API, wikitext form) and a couple of small
line-classifying regexes. Run:  python importers/dispatch.py wikisource_madhava
(or wikisource_susruta / wikisource_sharngadhara)
"""
import re, json, time, urllib.parse, urllib.request
import collections
from common import write_grantha

API = "https://sa.wikisource.org/w/api.php"
SOURCE = "Sanskrit Wikisource (sa.wikisource.org)"
LICENCE = "CC BY-SA"

def fetch_wikitext(title, _retries=3):
    url = (API + "?action=parse&page=" + urllib.parse.quote(title) +
           "&prop=wikitext&format=json&formatversion=2")
    req = urllib.request.Request(url, headers={"User-Agent": "DGE-importer/1.0 (educational)"})
    for attempt in range(_retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.loads(r.read().decode("utf-8", "replace"))
            if "parse" not in d:
                raise RuntimeError(f"fetch_wikitext({title!r}): {d}")
            return d["parse"]["wikitext"]
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < _retries - 1:
                time.sleep(10 * (attempt + 1))  # wikisource's own rate limit, back off and retry
                continue
            raise
    raise RuntimeError(f"fetch_wikitext({title!r}): exhausted retries")

DEVA_DIGITS = "०१२३४५६७८९"
def devnum_to_int(s):
    return int("".join(str(DEVA_DIGITS.index(c)) for c in s))

# A bare trailing Devanagari-numeral verse/sutra end marker -- these three
# texts use no "||N||"-style delimiter at all, just a number closing the
# line (confirmed live on all three: no such delimiter anywhere in any of
# them).
VEND = re.compile(r"([०-९]+)\s*$")
SECTION_HDR = re.compile(r"^==\s*(.+?)\s*==$")


def parse_madhava(wt):
    """Single page, mula-only, no interleaved commentary. Sections (disease
    topics, not numbered adhyayas -- this text is organized by topic, e.g.
    ज्वरनिदानम्) are '==...==' headers; every content line is ':'-prefixed
    and a verse/couplet ends with a bare trailing number, RESETTING per
    section (confirmed: section 1 ends at 21, section 2 restarts at 1)."""
    lines = wt.splitlines()
    chapters = collections.OrderedDict()
    section = None
    buf = []
    just_opened = False
    for raw in lines:
        s = raw.strip()
        if not s:
            continue
        m = SECTION_HDR.match(s)
        if m:
            title = m.group(1).strip()
            # Trailing table-of-contents / source-note sections, not verse
            # content -- confirmed live, these are the only two "==...=="
            # headers on the page with no verse content under them.
            if title in ("विषयानुक्रमणिका", "स्रोतः"):
                section = None
            else:
                section = title
            buf = []
            just_opened = True
            continue
        if s.startswith(":;") or section is None:
            buf = []
            continue  # structural header line, or inside a skipped trailing section
        content = s[1:].strip() if s.startswith(":") else s
        if just_opened:
            # Every section restates its own title as the first content
            # line right after "==...=="  -- bare ("पञ्चनिदानलक्षणम्"), with
            # the stock chapter-opening word "अथ " (space, "अथ ज्वरनिदानम्"),
            # or with "अथ" sandhi'd directly onto the title with no space
            # ("अथाग्निमान्द्य..." for अथ+अग्निमान्द्य...). Confirmed live on
            # section after section; without stripping all three forms it
            # prepends onto verse 1's own text.
            just_opened = False
            stripped = content
            if stripped.startswith("अथ "):
                stripped = stripped[len("अथ "):]
            elif stripped.startswith("अथ"):
                stripped = stripped[len("अथ"):]
            if content == section or stripped == section:
                continue
        vm = VEND.search(content)
        if vm:
            buf.append(content[:vm.start()].strip())
            text = " ".join(x for x in buf if x).strip()
            n = devnum_to_int(vm.group(1))
            chapters.setdefault(section, []).append({"number": n, "sanskrit_text": text})
            buf = []
        else:
            buf.append(content)
    return [{"id": f"section_{i:02d}", "reference": f"Madhava Nidana, {name}", "shlokas": sh}
            for i, (name, sh) in enumerate(chapters.items(), 1)]


CHAPTER_START = re.compile(r"^:;?\S*ऽध्यायः?\s*$")

def parse_sharngadhara_khanda(wt, khanda_name):
    """One khanda page. '==...==' section headers, one per adhyaya (7 for
    Purvakhanda, confirmed complete against the khanda's own closing
    colophons -- unlike Susruta below, every adhyaya here gets its own
    '==...==', so a plain running counter is enough, no colophon
    reconciliation needed. ':;इति...' colophons and bare 'ऽध्यायः'
    sub-captions (short un-numbered topic tags before some verses, e.g.
    'मङ्गलाचरणम्') are skipped as structural noise -- NOTE: a caption tag
    occasionally ends up prefixed onto the following verse's text rather
    than being cleanly separated, a known, accepted, minor imperfection
    (see this importer's own PENDING.md note), not lost content."""
    lines = wt.splitlines()
    chapters = collections.OrderedDict()
    adhyaya = 0
    buf = []
    for raw in lines:
        s = raw.strip()
        if not s:
            continue
        m = SECTION_HDR.match(s)
        if m:
            adhyaya += 1
            buf = []
            continue
        if s.startswith(":;") or CHAPTER_START.match(s) or adhyaya == 0:
            buf = []
            continue
        content = s[1:].strip() if s.startswith(":") else s
        vm = VEND.search(content)
        if vm:
            buf.append(content[:vm.start()].strip())
            text = " ".join(x for x in buf if x).strip()
            n = devnum_to_int(vm.group(1))
            chapters.setdefault(adhyaya, []).append({"number": n, "sanskrit_text": text})
            buf = []
        else:
            buf.append(content)
    return [{"id": f"{khanda_name}_adhyaya_{c:02d}",
             "reference": f"Sharngadhara Samhita, {khanda_name.title()}akhanda, Adhyaya {c}",
             "shlokas": sh} for c, sh in chapters.items()]


# The specific closing-colophon phrasing this text always uses -- "इति
# (श्री)सुश्रुतसंहितायां ...अध्यायः N". Confirmed live: a *bare* "इति" is an
# extremely common ordinary Sanskrit word ("thus") that appears inside many
# verse lines that also happen to end in a number (the verse's own closing
# count) -- an early looser "इति ... N$" regex matched dozens of those false
# positives per subpage. Requiring "सुश्रुतसंहितायां" (with the common
# "श्री" honorific optionally attached) right after "इति" makes this
# specific to real colophons. Checked against the fully assembled multi-line
# text (see below), not a single raw line: confirmed live, some colophons
# wrap across two source lines ("...विज्ञानीयो" / "नामाष्टाविंशतितमोऽध्यायः
# २८"), so a single-line-only check both misses those as colophons AND
# wrongly emits their second half as a spurious extra "verse".
COLOPHON_SIG = re.compile(r"^इति\s*(?:श्री)?सुश्रुतसंहितायां")

def parse_susruta_page(wt, start_chapter):
    """One sthana subpage. NEITHER '==...==' headers NOR a fully-consistent
    per-chapter marker exist here -- confirmed live: some chapters open
    with a bare 'ऽध्यायः' start-marker and have no closing colophon (e.g.
    adhyayas 11-12 in sutrasthana/1-15), others have a closing colophon
    ("इति सुश्रुतसंहितायां ... दशमोऽध्यायः १०") but no start-marker (e.g.
    adhyaya 10) -- the two signal types are complementary, together
    covering every chapter boundary with no true gap, but a naive parser
    trusting only one of them silently misattributes whole chapters'
    worth of verses to their neighbour.

    Verses are buffered UNCOMMITTED until a boundary resolves which
    chapter they belong to: a colophon is authoritative (carries the
    closing chapter's own number) and always wins; a start-marker only
    closes the pending buffer if no colophon already did, using the
    running counter -- this is the one case where the counter, not the
    text itself, supplies the number. start_chapter seeds the counter
    per subpage (e.g. 16 for ".../adhyaya 16-30"), since chapter
    numbering continues across subpages, not per-page from 1."""
    lines = wt.splitlines()
    chapters = collections.OrderedDict()
    current = start_chapter
    confirmed = True  # true once `current` is known-correct (colophon-set or the initial seed)
    pending = []
    buf = []

    def close_span(ch):
        if pending:
            chapters.setdefault(ch, []).extend(pending)
            pending[:] = []

    for raw in lines:
        s = raw.strip()
        if not s:
            continue
        # A structural chapter-start marker (no trailing number) is only
        # ever a boundary when it has NO other content -- confirmed live,
        # every real one matches this on its own line. A colophon can ALSO
        # start with ":;" (the ";" is not a reliable "this is a boundary"
        # signal by itself -- confirmed live, colophons and start-markers
        # both appear with and without it inconsistently), so a colophon
        # must be allowed to fall through to the content/VEND path below
        # rather than being swallowed here just because of its prefix.
        if CHAPTER_START.match(s):
            if not confirmed:
                close_span(current)
                current += 1
            confirmed = False
            buf = []
            continue
        content = s.lstrip(":;").strip() if s[:1] in (":", ";") else s
        vm = VEND.search(content)
        if vm:
            buf.append(content[:vm.start()].strip())
            text = " ".join(x for x in buf if x).strip()
            n = devnum_to_int(vm.group(1))
            buf = []
            if COLOPHON_SIG.match(text):
                close_span(n)
                current = n + 1
                confirmed = True
            else:
                pending.append({"number": n, "sanskrit_text": text})
        else:
            buf.append(content)
    close_span(current)  # flush any chapter that never got an explicit closing signal
    return [{"id": f"adhyaya_{c:02d}", "reference": f"Susruta Samhita, Adhyaya {c}", "shlokas": sh}
            for c, sh in chapters.items()]


def run(tid):
    if tid == "wikisource_madhava":
        wt = fetch_wikitext("माधवनिदानम्")
        items = parse_madhava(wt)
        write_grantha(
            "upaveda/ayurveda/madhava_nidana", "generic", "माधवकरः", items,
            source_url="https://sa.wikisource.org/wiki/माधवनिदानम्",
            source_note=SOURCE + ". Mula text only -- no interleaved commentary on "
                "this page. Organized into 68 disease-topic sections (not numbered "
                "adhyayas), matching the source page's own == section == structure.",
            licence=LICENCE,
        )
    elif tid == "wikisource_sharngadhara":
        khandas = [
            ("शार्ङ्गधरसंहिता/पूर्वखण्डम्", "purva"),
            ("शार्ङ्गधरसंहिता/मध्यखण्डम्", "madhya"),
            ("शार्ङ्गधरसंहिता/उत्तरखण्डम्", "uttara"),
            ("शार्ङ्गधरसंहिता/परिशिष्टम्", "parishishta"),
        ]
        items = []
        for i, (title, name) in enumerate(khandas):
            if i:
                time.sleep(2)
            items.extend(parse_sharngadhara_khanda(fetch_wikitext(title), name))
        write_grantha(
            "upaveda/ayurveda/sharngadhara_samhita", "generic", "शार्ङ्गधराचार्यः", items,
            source_url="https://sa.wikisource.org/wiki/शार्ङ्गधरसंहिता",
            source_note=SOURCE + ". All four khandas (Purva/Madhya/Uttara + the "
                "Parishishta appendix). Known, accepted minor imperfection: a short "
                "un-numbered caption/topic-tag line before a verse (e.g. "
                "'मङ्गलाचरणम्') is occasionally prepended onto that verse's own text "
                "rather than being cleanly separated -- no safe general filter was "
                "found (unlike Madhava Nidana's section-title repeats, these captions "
                "are not simple title-repeats), so it is left as-is rather than risk "
                "dropping real content.",
            licence=LICENCE,
        )
    elif tid == "wikisource_susruta":
        pages = [
            ("सुश्रुतसंहिता/सूत्रस्थानम्/अध्याय ०१-१५", 1),
            ("सुश्रुतसंहिता/सूत्रस्थानम्/अध्याय १६-३०", 16),
            ("सुश्रुतसंहिता/सूत्रस्थानम्/अध्याय ३१-४६", 31),
        ]
        items = []
        for i, (title, seed) in enumerate(pages):
            if i:
                time.sleep(2)
            items.extend(parse_susruta_page(fetch_wikitext(title), seed))
        write_grantha(
            "upaveda/ayurveda/susruta_samhita_sutrasthana", "generic", "सुश्रुतः", items,
            source_url="https://sa.wikisource.org/wiki/सुश्रुतसंहिता",
            source_note=SOURCE + ". Sutrasthana ONLY (46 adhyayas) -- this text's "
                "other five sthanas (Nidana/Sharira/Chikitsa/Kalpa + the "
                "Uttaratantra) are not yet imported; each has its own page "
                "structure that needs the same per-page boundary verification "
                "this importer already did for Sutrasthana before being trusted, "
                "left for a future pass rather than imported without that check.",
            licence=LICENCE,
        )
    else:
        raise ValueError(f"unknown wikisource_ayurveda id: {tid}")
