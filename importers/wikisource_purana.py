"""Sanskrit Wikisource importer for the Purana gaps identified in dge/PENDING.md
(11 Sep 2026 cross-check): Vayu, Bhavishya, Brahmavaivarta, Padma, the
remaining khandas/samhitas of Garuda/Skanda/Shiva, Narada's purvabhaga
padas, Brahmanda's Adhyatma Ramayana, Vishnudharmottara, Devi Bhagavata,
Ganesha.

Fetches via Special:Export (MediaWiki's own bulk-export endpoint, one HTTP
POST returns many pages' wikitext in a single XML document) rather than
one action=parse call per page -- confirmed necessary live: sa.wikisource.org
throttles the per-page parse API hard (instant 429s during scoping, even at
a 2s/request pace), but Special:Export is the wiki's own intended bulk
access path and was not throttled at all in the same session. The crawl is
therefore breadth-first and batched: fetch a level's pages in ONE export
call, discover the next level's links from whichever of those aren't yet
verse content, export THAT whole level in one call, and so on -- total
requests is the tree's depth, not its leaf count.

One generic parser, not one function per text (unlike wikisource_ayurveda.py's
four bespoke ones) -- confirmed live across several of these texts that they
share the same volunteer-transcription template: verses wrapped in
<poem>...</poem>, each line ending in a Devanagari '।।N।।' (or '॥N॥') marker.
Chapter numbering is read from the WIKILINK LABEL that reached a page (the
"१०" in "अध्यायः १०"), not guessed from colophons -- more reliable here than
wikisource_ayurveda.py's colophon/counter reconciliation for Sanskrit
Documents' Susruta pages, because every text in this batch carries a real
numbered index.

Registry-driven like importers/gretil_bulk.py: many texts, one engine, the
per-text index-page title(s) kept as data (SPEC below), not code. Re-running
an id re-crawls from the live wiki, so this doubles as the "source syncer"
for catching future edits/corrections on Wikisource's end.

Run:  python importers/wikisource_purana.py --list
      python importers/wikisource_purana.py --id vayu_purana --dry-run
      python importers/wikisource_purana.py --id vayu_purana
      python importers/dispatch.py wikisource_purana:vayu_purana
"""
import argparse, html, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import write_grantha, data_base

EXPORT_URL = "https://sa.wikisource.org/w/index.php"
SOURCE = "Sanskrit Wikisource (sa.wikisource.org)"
LICENCE = "CC BY-SA"
UA = {"User-Agent": "DGE-importer/1.0 (educational; https://github.com/Tribhuvanachar/bhumandala)"}

CHUNK = 60          # titles per Special:Export call -- comfortably under any default server cap
MIN_INTERVAL = 2.0  # floor between export batches, not per page
_last_fetch = [0.0]


def export_pages(titles, _retries=6):
    """titles -> {title: wikitext_or_None}. None means the page doesn't
    exist (a dead link in an index page's own list -- seen live on a couple
    of the texts below, e.g. a planned-but-never-written adhyaya)."""
    out = {}
    for i in range(0, len(titles), CHUNK):
        batch = titles[i:i + CHUNK]
        wait = MIN_INTERVAL - (time.time() - _last_fetch[0])
        if wait > 0:
            time.sleep(wait)
        data = urllib.parse.urlencode({
            "title": "Special:Export", "pages": "\n".join(batch),
            "action": "submit", "curonly": "1",
        }).encode("utf-8")
        req = urllib.request.Request(EXPORT_URL, data=data, headers=UA)
        for attempt in range(_retries):
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    xml_bytes = r.read()
                _last_fetch[0] = time.time()
                break
            except urllib.error.HTTPError as e:
                _last_fetch[0] = time.time()
                if e.code in (429, 503) and attempt < _retries - 1:
                    time.sleep(10 * (attempt + 1))
                    continue
                raise
        else:
            raise RuntimeError("export_pages: exhausted retries")
        root = ET.fromstring(xml_bytes)
        found = set()
        for page in root.findall(".//{*}page"):
            title_el = page.find("{*}title")
            title = title_el.text if title_el is not None else None
            rev = page.find("{*}revision")
            text_el = rev.find("{*}text") if rev is not None else None
            out[title] = text_el.text if text_el is not None else None
            found.add(title)
        for t in batch:
            if t not in found:
                out[t] = None  # redirected/renamed/never-existed title
    return out


DEVA_DIGITS = "०१२३४५६७८९"


def devnum_to_str(s):
    return "".join(str(DEVA_DIGITS.index(c)) if c in DEVA_DIGITS else c for c in s)


LINK = re.compile(r"\[\[([^\]|#]+?)(?:\|([^\]]*))?\]\]")
BR = re.compile(r"<br\s*/?>")
TAG = re.compile(r"<[^>]+>")
WIKIFMT = re.compile(r"'{2,3}")  # wikitext bold/italic markers, not part of the Sanskrit
POEM = re.compile(r"<poem[^>]*>(.*?)</poem>", re.S)
# Some texts (confirmed live: Vayu Purana's Uttarardha) number verses
# "chapter.verse" (e.g. "।। २.१ ।।") rather than a bare running number --
# the optional non-captured "chapter." prefix below discards the redundant
# chapter part (already known from the wikilink label that reached this
# page) and keeps only the verse number itself. Danda placement around the
# number varies a lot across this whole text family and neither side can be
# made mandatory: Padma Purana glues the number onto the last word with NO
# danda before it ("...वः पुनातु१।"), while Bhavishya Purana's Brahma Parva
# ends a line "... । । N" (two SPACE-SEPARATED single dandas) with NO danda
# after the number at all. The number itself, not surrounding punctuation,
# is therefore the only reliable anchor -- matching wikisource_ayurveda.py's
# own three Sanskrit Documents texts, which need no delimiter at all.
VEND = re.compile(r"[।॥]{0,2}\s*(?:[०-९]+\.)?([०-९]+(?:[-–][०-९]+)?)\s*[।॥]{0,2}\s*$")
CHAPTER_BOUNDARY = re.compile(
    r"^\s*(?:'''|==+\s*)?(?:श्री)?अध्यायः?\s*([०-९]+)\s*(?:'''|=+)?\s*$", re.M
)
NOISE_HDR = re.compile(r"^\{\{header.*?\}\}\s*", re.S)
SKIP_NS = ("वर्गः:", "श्रेणी:", "चित्र:", "File:", "सञ्चिका:")


def links_from(wikitext, current_title):
    seen, out = set(), []
    for m in LINK.finditer(wikitext):
        target, label = m.group(1).strip(), (m.group(2) or m.group(1)).strip()
        if target.startswith(SKIP_NS):
            continue
        if target.startswith("/"):
            target = current_title + target
        # MediaWiki normalizes runs of whitespace in a title to one space
        # (confirmed live: a handful of Vayu Purana links read "अध्यायः  १",
        # double space, and Special:Export 404s on the un-normalized form).
        target = re.sub(r"\s+", " ", target)
        if target in seen:
            continue
        seen.add(target)
        out.append((target, label))
    return out


def label_number(label):
    m = re.search(r"[०-९]+", label or "")
    return devnum_to_str(m.group(0)) if m else None


def parse_poem_page(wikitext, fallback_label_num):
    segments = []
    bounds = list(CHAPTER_BOUNDARY.finditer(wikitext))
    if len(bounds) >= 2:
        for i, b in enumerate(bounds):
            end = bounds[i + 1].start() if i + 1 < len(bounds) else len(wikitext)
            segments.append((devnum_to_str(b.group(1)), wikitext[b.start():end]))
    else:
        segments = [(fallback_label_num, wikitext)]

    result = []
    for chap_num, seg in segments:
        shlokas, buf = [], []
        for poem_m in POEM.finditer(seg):
            for raw in html.unescape(poem_m.group(1)).splitlines():
                line = WIKIFMT.sub("", TAG.sub("", BR.sub("", raw))).strip()
                if not line or line.startswith("{{") or line.startswith("|"):
                    continue
                vm = VEND.search(line)
                if vm:
                    buf.append(line[:vm.start()].strip())
                    text = " ".join(x for x in buf if x).strip()
                    buf = []
                    if text:
                        shlokas.append({"number": devnum_to_str(vm.group(1)), "sanskrit_text": text})
                else:
                    buf.append(line)
        if shlokas:
            result.append((chap_num, shlokas))
    return result


def crawl(seed_titles, _max_depth=4, verbose=True):
    """Breadth-first, batched. seed_titles: [(title, label), ...] to start
    from (label may be None for the very first level). Returns
    [(chapter_number_or_None, shlokas), ...] across every leaf discovered."""
    chapters = []
    frontier = list(seed_titles)
    visited = set()
    depth = 0
    while frontier and depth <= _max_depth:
        titles = [t for t, _ in frontier if t not in visited]
        if not titles:
            break
        visited.update(titles)
        if verbose:
            print(f"  depth {depth}: exporting {len(titles)} page(s)...")
        fetched = export_pages(titles)
        next_frontier = []
        for title, label in frontier:
            wt = fetched.get(title)
            if wt is None:
                continue
            wt = html.unescape(wt)
            body = NOISE_HDR.sub("", wt, count=1)
            # A handful of pages (confirmed live: Adhyatma Ramayana) never
            # close their <poem> tag -- MediaWiki's renderer tolerates this
            # (auto-closes at end of page) but our regex needs an explicit
            # close, so supply the ones missing rather than silently
            # treating the whole page as link-only and losing its verses.
            while body.count("<poem") > body.count("</poem>"):
                body += "</poem>"
            if POEM.search(body):
                chapters.extend(parse_poem_page(body, label_number(label)))
            else:
                for sub_title, sub_label in links_from(body, title):
                    if sub_title not in visited:
                        next_frontier.append((sub_title, sub_label))
        frontier = next_frontier
        depth += 1
    return chapters


def to_items(chapters, ref_prefix, id_prefix=""):
    """id_prefix distinguishes multi-part texts (Vayu's Purvardha/Uttarardha,
    each independently numbered 1..N) whose chapter ids would otherwise
    collide -- confirmed live: without it, Purvardha adhyaya 50 and
    Uttarardha adhyaya 50 both write "adhyaya_50", silently merging two
    unrelated chapters' worth of verses under one id in the reader."""
    items = []
    for i, (num, shlokas) in enumerate(chapters, 1):
        n = num if num is not None else str(i)
        base = f"adhyaya_{int(n):02d}" if n.isdigit() else f"adhyaya_{i:02d}"
        cid = f"{id_prefix}_{base}" if id_prefix else base
        items.append({"id": cid, "reference": f"{ref_prefix}, Adhyaya {n}", "shlokas": shlokas})
    return items


def preserve_stub_extra(rel_path):
    fp = os.path.join(data_base(), rel_path, "data.json")
    if not os.path.exists(fp):
        return {}
    try:
        d = json.load(open(fp, encoding="utf-8"))
    except Exception:
        return {}
    skip = {"schema", "default_author", "items", "source_url", "source_note", "source", "licence", "license"}
    return {k: v for k, v in d.items() if k not in skip}


# ---------------------------------------------------------------------------
# Registry. Each entry either fills one taxonomy leaf on its own, or (when
# several entries share a "rel") is combined in the listed order before the
# single write_grantha call -- see run_one().
SPEC = [
    dict(id="vayu_purana", rel="purana/maha_purana/vayu_purana",
         parts=[("वायुपुराणम्/पूर्वार्धम्", "purvardha"), ("वायुपुराणम्/उत्तरार्धम्", "uttarardha")],
         ref="Vayu Purana", author="Maharshi Veda Vyasa"),

    # Bhavishya Purana -- 4 taxonomy leaves. Madhyama/Pratisarga parva are
    # further split into bhaga/khanda on Wikisource; each becomes its own
    # id-prefixed part merged into that leaf's single data.json.
    dict(id="bhavishya_brahma_parva", rel="purana/maha_purana/bhavishya_purana/brahma_parva",
         parts=[("भविष्यपुराणम् /पर्व १ (ब्राह्मपर्व)", "")],
         ref="Bhavishya Purana, Brahma Parva", author="Maharshi Veda Vyasa"),
    dict(id="bhavishya_madhyama_parva", rel="purana/maha_purana/bhavishya_purana/madhyama_parva",
         parts=[("भविष्यपुराणम् /पर्व २ (मध्यमपर्व)/भागः १", "bhaga1"),
                ("भविष्यपुराणम् /पर्व २ (मध्यमपर्व)/भागः २", "bhaga2"),
                ("भविष्यपुराणम् /पर्व २ (मध्यमपर्व)/भागः ३", "bhaga3")],
         ref="Bhavishya Purana, Madhyama Parva", author="Maharshi Veda Vyasa"),
    dict(id="bhavishya_pratisarga_parva", rel="purana/maha_purana/bhavishya_purana/pratisarga_parva",
         parts=[("भविष्यपुराणम् /पर्व ३ (प्रतिसर्गपर्व)/खण्डः १", "khanda1"),
                ("भविष्यपुराणम् /पर्व ३ (प्रतिसर्गपर्व)/खण्डः २", "khanda2"),
                ("भविष्यपुराणम् /पर्व ३ (प्रतिसर्गपर्व)/खण्डः ३", "khanda3"),
                ("भविष्यपुराणम् /पर्व ३ (प्रतिसर्गपर्व)/खण्डः ४", "khanda4")],
         ref="Bhavishya Purana, Pratisarga Parva", author="Maharshi Veda Vyasa"),
    dict(id="bhavishya_uttara_parva", rel="purana/maha_purana/bhavishya_purana/uttara_parva",
         parts=[("भविष्यपुराणम् /पर्व ४ (उत्तरपर्व)", "")],
         ref="Bhavishya Purana, Uttara Parva", author="Maharshi Veda Vyasa"),

    # Brahmavaivarta Purana -- 4 separate taxonomy leaves.
    dict(id="brahmavaivarta_brahma_khanda", rel="purana/maha_purana/brahmavaivarta_purana/brahma_khanda",
         parts=[("ब्रह्मवैवर्तपुराणम्/खण्डः १ (ब्रह्मखण्डः)", "")],
         ref="Brahmavaivarta Purana, Brahma Khanda", author="Maharshi Veda Vyasa"),
    dict(id="brahmavaivarta_prakriti_khanda", rel="purana/maha_purana/brahmavaivarta_purana/prakriti_khanda",
         parts=[("ब्रह्मवैवर्तपुराणम्/खण्डः २ (प्रकृतिखण्डः)", "")],
         ref="Brahmavaivarta Purana, Prakriti Khanda", author="Maharshi Veda Vyasa"),
    dict(id="brahmavaivarta_ganesha_khanda", rel="purana/maha_purana/brahmavaivarta_purana/ganesha_khanda",
         parts=[("ब्रह्मवैवर्तपुराणम्/गणपतिखण्डः", "")],
         ref="Brahmavaivarta Purana, Ganapati (Ganesha) Khanda", author="Maharshi Veda Vyasa"),
    dict(id="brahmavaivarta_krishna_janma_khanda", rel="purana/maha_purana/brahmavaivarta_purana/krishna_janma_khanda",
         parts=[("ब्रह्मवैवर्तपुराणम्/खण्डः ४ (श्रीकृष्णजन्मखण्डः)", "")],
         ref="Brahmavaivarta Purana, Krishna Janma Khanda", author="Maharshi Veda Vyasa"),

    # Padma Purana -- 7 khandas; "brahma_khanda" is a NEW taxonomy leaf (this
    # edition has 7, our taxonomy only had 6 before this pass).
    dict(id="padma_srishti_khanda", rel="purana/maha_purana/padma_purana/srishti_khanda",
         parts=[("पद्मपुराणम्/खण्डः १ (सृष्टिखण्डम्)", "")],
         ref="Padma Purana, Srishti Khanda", author="Maharshi Veda Vyasa"),
    dict(id="padma_bhumi_khanda", rel="purana/maha_purana/padma_purana/bhumi_khanda",
         parts=[("पद्मपुराणम्/खण्डः २ (भूमिखण्डः)", "")],
         ref="Padma Purana, Bhumi Khanda", author="Maharshi Veda Vyasa"),
    dict(id="padma_svarga_khanda", rel="purana/maha_purana/padma_purana/svarga_khanda",
         parts=[("पद्मपुराणम्/खण्डः ३ (स्वर्गखण्ड)", "")],
         ref="Padma Purana, Svarga Khanda", author="Maharshi Veda Vyasa"),
    dict(id="padma_brahma_khanda", rel="purana/maha_purana/padma_purana/brahma_khanda",
         parts=[("पद्मपुराणम्/खण्डः ४ (ब्रह्मखण्ड)", "")],
         ref="Padma Purana, Brahma Khanda", author="Maharshi Veda Vyasa"),
    dict(id="padma_patala_khanda", rel="purana/maha_purana/padma_purana/patala_khanda",
         parts=[("पद्मपुराणम्/खण्डः ५ (पातालखण्ड)", "")],
         ref="Padma Purana, Patala Khanda", author="Maharshi Veda Vyasa"),
    dict(id="padma_uttara_khanda", rel="purana/maha_purana/padma_purana/uttara_khanda",
         parts=[("पद्मपुराणम्/खण्डः ६ (उत्तरखण्डः)", "")],
         ref="Padma Purana, Uttara Khanda", author="Maharshi Veda Vyasa"),
    dict(id="padma_kriya_yoga_sara_khanda", rel="purana/maha_purana/padma_purana/kriya_yoga_sara_khanda",
         parts=[("पद्मपुराणम्/खण्डः ७ (क्रियाखण्डः)", "")],
         ref="Padma Purana, Kriya(yoga sara) Khanda", author="Maharshi Veda Vyasa"),

    # Garuda Purana -- purva_khanda (== Acharakanda) already populated via
    # GRETIL; only the other two khandas are missing.
    dict(id="garuda_brahma_khanda", rel="purana/maha_purana/garuda_purana/brahma_khanda",
         parts=[("गरुडपुराणम्/ब्रह्मकाण्डः (मोक्षकाण्डः)", "")],
         ref="Garuda Purana, Brahma (Mokshakanda) Khanda", author="Maharshi Veda Vyasa"),
    dict(id="garuda_uttara_khanda_pretakalpa", rel="purana/maha_purana/garuda_purana/uttara_khanda_pretakalpa",
         parts=[("गरुडपुराणम्/प्रेतकाण्डः (धर्मकाण्डः)", "")],
         ref="Garuda Purana, Uttara Khanda (Pretakalpa/Dharmakanda)", author="Maharshi Veda Vyasa"),

    # Skanda Purana -- revakhanda already populated; the other 7 khandas of
    # this edition's 8 are missing (Ambika khanda is a NEW taxonomy leaf,
    # this edition's 8th khanda, not previously tracked at all).
    dict(id="skanda_maheshvara_khanda", rel="purana/maha_purana/skanda_purana/maheshvara_khanda",
         parts=[("स्कन्दपुराणम्/खण्डः १ (माहेश्वरखण्डः)", "")],
         ref="Skanda Purana, Maheshvara Khanda", author="Maharshi Veda Vyasa"),
    dict(id="skanda_vaishnava_khanda", rel="purana/maha_purana/skanda_purana/vaishnava_khanda",
         parts=[("स्कन्दपुराणम्/खण्डः २ (वैष्णवखण्डः)", "")],
         ref="Skanda Purana, Vaishnava Khanda", author="Maharshi Veda Vyasa"),
    dict(id="skanda_brahma_khanda", rel="purana/maha_purana/skanda_purana/brahma_khanda",
         parts=[("स्कन्दपुराणम्/खण्डः ३ (ब्रह्मखण्डः)", "")],
         ref="Skanda Purana, Brahma Khanda", author="Maharshi Veda Vyasa"),
    dict(id="skanda_kashi_khanda", rel="purana/maha_purana/skanda_purana/kashi_khanda",
         parts=[("स्कन्दपुराणम्/खण्डः ४ (काशीखण्डः)", "")],
         ref="Skanda Purana, Kashi Khanda", author="Maharshi Veda Vyasa"),
    dict(id="skanda_avantya_khanda", rel="purana/maha_purana/skanda_purana/avantya_khanda",
         parts=[("स्कन्दपुराणम्/खण्डः ५ (अवन्तीखण्डः)", "")],
         ref="Skanda Purana, Avantya Khanda", author="Maharshi Veda Vyasa"),
    dict(id="skanda_nagara_khanda", rel="purana/maha_purana/skanda_purana/nagara_khanda",
         parts=[("स्कन्दपुराणम्/खण्डः ६ (नागरखण्डः)", "")],
         ref="Skanda Purana, Nagara Khanda", author="Maharshi Veda Vyasa"),
    dict(id="skanda_prabhasa_khanda", rel="purana/maha_purana/skanda_purana/prabhasa_khanda",
         parts=[("स्कन्दपुराणम्/खण्डः ७ (प्रभासखण्डः)", "")],
         ref="Skanda Purana, Prabhasa Khanda", author="Maharshi Veda Vyasa"),
    dict(id="skanda_ambika_khanda", rel="purana/maha_purana/skanda_purana/ambika_khanda",
         parts=[("स्कन्दपुराणम्/खण्डः ८ (अम्बिकाखण्डः)", "")],
         ref="Skanda Purana, Ambika Khanda", author="Maharshi Veda Vyasa"),

    # Shiva Purana -- Vidyeshvara + Vayaviya samhitas already populated.
    dict(id="shiva_shatarudra_samhita", rel="purana/maha_purana/shiva_purana/shatarudra_samhita",
         parts=[("शिवपुराणम्/संहिता ३ (शतरुद्रसंहिता)", "")],
         ref="Shiva Purana, Shatarudra Samhita", author="Maharshi Veda Vyasa"),
    dict(id="shiva_kotirudra_samhita", rel="purana/maha_purana/shiva_purana/kotirudra_samhita",
         parts=[("शिवपुराणम्/संहिता ४ (कोटिरुद्रसंहिता)", "")],
         ref="Shiva Purana, Kotirudra Samhita", author="Maharshi Veda Vyasa"),
    dict(id="shiva_uma_samhita", rel="purana/maha_purana/shiva_purana/uma_samhita",
         parts=[("शिवपुराणम्/संहिता ५ (उमासंहिता)", "")],
         ref="Shiva Purana, Uma Samhita", author="Maharshi Veda Vyasa"),
    dict(id="shiva_kailasa_samhita", rel="purana/maha_purana/shiva_purana/kailasa_samhita",
         parts=[("शिवपुराणम्/संहिता ६ (कैलाससंहिता)", "")],
         ref="Shiva Purana, Kailasa Samhita", author="Maharshi Veda Vyasa"),
    dict(id="shiva_rudra_srishti_khanda", rel="purana/maha_purana/shiva_purana/rudra_samhita/srishti_khanda",
         parts=[("शिवपुराणम्/संहिता २ (रुद्रसंहिता)/खण्डः १ (सृष्टिखण्डः)", "")],
         ref="Shiva Purana, Rudra Samhita, Srishti Khanda", author="Maharshi Veda Vyasa"),
    dict(id="shiva_rudra_sati_khanda", rel="purana/maha_purana/shiva_purana/rudra_samhita/sati_khanda",
         parts=[("शिवपुराणम्/संहिता २ (रुद्रसंहिता)/खण्डः २ (सतीखण्डः)", "")],
         ref="Shiva Purana, Rudra Samhita, Sati Khanda", author="Maharshi Veda Vyasa"),
    dict(id="shiva_rudra_parvati_khanda", rel="purana/maha_purana/shiva_purana/rudra_samhita/parvati_khanda",
         parts=[("शिवपुराणम्/संहिता २ (रुद्रसंहिता)/खण्डः ३ (पार्वतीखण्डः)", "")],
         ref="Shiva Purana, Rudra Samhita, Parvati Khanda", author="Maharshi Veda Vyasa"),
    dict(id="shiva_rudra_kumara_khanda", rel="purana/maha_purana/shiva_purana/rudra_samhita/kumara_khanda",
         parts=[("शिवपुराणम्/संहिता २ (रुद्रसंहिता)/खण्डः ४ (कुमारखण्डः)", "")],
         ref="Shiva Purana, Rudra Samhita, Kumara Khanda", author="Maharshi Veda Vyasa"),
    dict(id="shiva_rudra_yuddha_khanda", rel="purana/maha_purana/shiva_purana/rudra_samhita/yuddha_khanda",
         parts=[("शिवपुराणम्/संहिता २ (रुद्रसंहिता)/खण्डः ५ (युद्धखण्डः)", "")],
         ref="Shiva Purana, Rudra Samhita, Yuddha Khanda", author="Maharshi Veda Vyasa"),

    # Vishnudharmottara Purana -- single taxonomy leaf, 3 khandas merged in.
    dict(id="vishnu_dharmottara_purana", rel="purana/upa_purana/vishnu_dharmottara_purana",
         parts=[("विष्णुधर्मोत्तरपुराणम्/प्रथम खण्डः", "khanda1"),
                ("विष्णुधर्मोत्तरपुराणम्/द्वितीय खण्डः", "khanda2"),
                ("विष्णुधर्मोत्तरपुराणम्/तृतीय खण्डः", "khanda3")],
         ref="Vishnudharmottara Purana", author="Maharshi Veda Vyasa"),

    # Ganesha Purana -- single taxonomy leaf, 2 khandas merged in.
    dict(id="ganesha_purana", rel="purana/upa_purana/ganesha_purana",
         parts=[("गणेशपुराणम्/खण्डः १(उपासनाखण्डम्)", "upasana"),
                ("गणेशपुराणम्/खण्डः २(क्रीडाखण्डम्)", "krida")],
         ref="Ganesha Purana", author="Maharshi Veda Vyasa"),

    # Devi Bhagavata Purana -- single taxonomy leaf, Mahatmya + 12 skandhas.
    dict(id="devi_bhagavata_purana", rel="purana/upa_purana/devi_bhagavata_purana",
         parts=[("देवीभागवतपुराणम्/माहात्म्यम्", "mahatmya"),
                ("देवीभागवतपुराणम्/स्कन्धः ०१", "skandha01"),
                ("देवीभागवतपुराणम्/स्कन्धः ०२", "skandha02"),
                ("देवीभागवतपुराणम्/स्कन्धः ०३", "skandha03"),
                ("देवीभागवतपुराणम्/स्कन्धः ०४", "skandha04"),
                ("देवीभागवतपुराणम्/स्कन्धः ०५", "skandha05"),
                ("देवीभागवतपुराणम्/स्कन्धः ०६", "skandha06"),
                ("देवीभागवतपुराणम्/स्कन्धः ०७", "skandha07"),
                ("देवीभागवतपुराणम्/स्कन्धः ०८", "skandha08"),
                ("देवीभागवतपुराणम्/स्कन्धः ०९", "skandha09"),
                ("देवीभागवतपुराणम्/स्कन्धः ०१०", "skandha10"),
                ("देवीभागवतपुराणम्/स्कन्धः ११", "skandha11"),
                ("देवीभागवतपुराणम्/स्कन्धः १२", "skandha12")],
         ref="Devi Bhagavata Purana", author="Maharshi Veda Vyasa"),
]


def run_one(spec, dry_run=False):
    part_titles = [p[0] for p in spec["parts"]]
    print(f"[{spec['id']}] crawling {part_titles} ...")
    items = []
    for part_title, part_slug in spec["parts"]:
        chapters = crawl([(part_title, None)])
        ref = spec["ref"] if not part_slug else f"{spec['ref']}, {part_slug.replace('_', ' ').title()}"
        items.extend(to_items(chapters, ref, id_prefix=part_slug))
    n_shlokas = sum(len(it["shlokas"]) for it in items)
    print(f"[{spec['id']}] {len(items)} chapters, {n_shlokas} shlokas")
    if dry_run:
        for it in items[:2]:
            print(" ", it["id"], it["reference"], "first shloka:", it["shlokas"][0]["sanskrit_text"][:80])
        return items
    if not items:
        print(f"[{spec['id']}] NOTHING PARSED -- not writing (check page titles / markup assumptions)")
        return items
    extra = preserve_stub_extra(spec["rel"])
    write_grantha(
        spec["rel"], "itihasa_purana_text", spec["author"], items,
        source_url="https://sa.wikisource.org/wiki/" + urllib.parse.quote(spec["parts"][0][0].split("/")[0]),
        source_note=f"{SOURCE}. Raw community-transcribed text; not scan-verified by this project "
                    "beyond confirming each page carries real verse content. Re-run this importer "
                    "id to pick up future corrections on Wikisource's side.",
        licence=LICENCE,
        **extra,
    )
    return items


def load_registry():
    return {s["id"]: s for s in SPEC}


def run(tid):
    reg = load_registry()
    if tid not in reg:
        raise SystemExit(f"unknown wikisource_purana id: {tid} (known: {sorted(reg)})")
    run_one(reg[tid])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--id")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if args.list:
        for s in SPEC:
            print(s["id"], "->", s["rel"])
    elif args.all:
        for s in SPEC:
            try:
                run_one(s, dry_run=args.dry_run)
            except Exception as exc:
                print(f"[{s['id']}] FAILED: {exc}", file=sys.stderr)
    elif args.id:
        run_one(load_registry()[args.id], dry_run=args.dry_run)
    else:
        ap.print_help()
