#!/usr/bin/env python3
"""
fetch_and_build.py -- fetches every chapter subpage of a Sanskrit Wikisource
Pancharatra Samhita via the MediaWiki API, parses the wikitext, and writes
a data.json matching the existing pancharatra_samhitas on-disk shape
(schema: generic, items: [{id, reference, shlokas: [{number, sanskrit_text}]}]).

Parsing quirks this handles, found and fixed by testing against real pages
before trusting it at scale (see dge/PENDING.md, 23 Aug entry):
- Critical-apparatus footnote blocks, bounded by dash-lines, removed via a
  line-based state machine (a monolithic regex mis-paired dash-lines on
  real data and silently ate 62 real verses in testing -- caught by
  counting verse-ref markers before/after, not assumed correct).
- Inline footnote-marker digits (e.g. "13parapara..."), stripped after
  protecting the "|| N.M ||"-style verse-ref markers with a NON-numeric
  placeholder (a numeric placeholder had its own digits eaten by the same
  strip step it was meant to survive -- also caught by testing, not assumed).
- Editorial subheading lines (tab-indented, no danda punctuation at all)
  removed -- but ONLY lines with no danda, since indented VERSE lines
  (padas continuing a speaker's dialogue) are also tab-indented in this
  source and must not be dropped; caught because an early version used
  "no || anywhere on this line" as the test, which wrongly ate a verse's
  first pada whenever its own closing || fell on the next line instead.
- Chapter-title line(s) at the front extracted via a no-danda/no-trailing-
  dash heuristic (title lines are the only front-matter lines with neither),
  rather than a fixed line count -- chapter 1 has 2 title lines, chapter 2
  has 1, so a fixed count silently swallowed chapter 2's own subheading
  into a phantom "chapter_title" on first attempt.
- The generic "shuklambaradharam..." Ganesha-dhyana verse, a printer's-
  convention invocation with no verse-ref marker of its own, stripped by
  EXACT text match (not a heuristic) so it can't accidentally eat real
  content in a chapter that happens to lack it.
"""
import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from skrutable.transliteration import Transliterator

_translit = Transliterator(from_scheme="IAST", to_scheme="DEV")

API = "https://sa.wikisource.org/w/api.php"
UA = "bhumandala-sanskrit-library/1.0 (research/import; nonprofit Sanskrit digital library)"

# Two verse-ref conventions found in the SAME work (Ahirbudhnyasamhita
# switches conventions repeatedly, apparently different Wikisource
# contributors transcribing different chapter ranges of the same work, each
# with their own habits: Devanagari danda + period ("।। 1.1 ।।") for most
# chapters, ASCII pipe + hyphen ("|| 43-1 ||") from chapter 43 on, and a
# THIRD variant found checking why chapter 45 also produced zero verses --
# danda and pipe used interchangeably within the SAME closing pair
# ("।| ४५-१।|", not a consistent "।।" or "||"). Rather than keep
# special-casing new pairings as they turn up, danda and pipe are treated
# as interchangeable: any 2 characters drawn from {।, |} bracket the
# ref, in any combination.
REF_RX = re.compile(r"[।|]{2}\s*([\d०-९]+)[.\-]([\d०-९]+)\s*[।|]{2}")
# The parishishtam appendix numbers verses with a single sequential number
# instead of a chapter.verse pair -- see parse_chapter's is_appendix path.
APPENDIX_REF_RX = re.compile(r"[।|]{2}\s*([\d०-९]+)\s*[।|]{2}")
DEVA_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
DASH_LINE = re.compile(r"[-_]{3,}[ \t]*$")
PAGE_MARKER_RX = re.compile(r"प[्ृु]?\.\s*[\d०-९]*\)")
SENTINEL = "@@DGEREFMARKER@@"
MANGALA_TEXT = "शुक्लाम्बरधरं विष्णुं शशिवर्णं चतुर्भुजम्।\nप्रसन्नवदनं ध्यायेत् सर्वविघ्रोपशान्तये।।"


def to_int(s):
    return int(s.translate(DEVA_DIGITS))


class RateLimited(Exception):
    """Raised when the API stays 429 past every retry -- deliberately NOT
    the same outcome as PageMissing. An earlier version of this script
    returned None for both a real 429-after-retries failure and a
    genuinely-missing page, so the caller's "no parseable content" SKIP
    silently covered both -- 23 real chapters were marked skipped during
    a sustained rate-limit window and would have been imported as if the
    text just ended at chapter 37, caught only because 23 consecutive
    skips in a row was implausible enough to go check by hand. A
    real fetch failure now stops the run instead of being swallowed."""


def wikitext(page_title, retries=8):
    url = API + "?" + urllib.parse.urlencode({
        "action": "parse", "page": page_title, "prop": "wikitext", "format": "json",
    })
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                data = json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                wait = min(8 * (2 ** attempt), 120)
                print(f"    429, retrying in {wait}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            if e.code == 429:
                raise RateLimited(f"{page_title!r} still 429 after {retries} attempts")
            raise
        if "error" in data:
            return None  # a real "page does not exist" from the API itself
        return data["parse"]["wikitext"]["*"]
    raise RateLimited(f"{page_title!r}: exhausted retries")


def subpage_list(index_title, link_prefix=None):
    """Parse the index page's wikitext for [[Title/Subpage|label]] links,
    in document order (this is the chapter ordering, not alphabetical).
    `link_prefix` defaults to `index_title` -- the usual case, a page's own
    subpages link to themselves as "ThisPage/Sub". Padmasamhita's pada
    index pages don't: fetched at "पद्मसंहिता/क्रियापादः", but the chapter
    links on that page read "क्रियापादः/अध्यायः N" with no "पद्मसंहिता/"
    prefix at all (checked directly, not assumed to match every other
    index page's own naming) -- passing link_prefix="क्रियापादः"
    separately from the fetched title handles that."""
    wt = wikitext(index_title)
    if wt is None:
        raise RuntimeError(f"could not fetch index page {index_title!r}")
    prefix = link_prefix if link_prefix is not None else index_title
    links = re.findall(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]", wt)
    seen = set()
    out = []
    for link in links:
        link = link.strip()
        if link.startswith(prefix + "/") and link not in seen:
            seen.add(link)
            out.append(link)
    return out


def extract_poem_block(wt):
    """Return the wikitext between "<poem>" and "</poem>", or None if there
    is no "<poem>" at all. Some pages (Ahirbudhnyasamhita ch. 59, confirmed
    by reading its own raw wikitext, not assumed) are missing the closing
    tag entirely -- the real content sits between the first "<poem>" and a
    second, stray, empty "<poem>" right at the end of the page instead.
    Handled generally: the block ends at whichever comes first, an actual
    "</poem>", another "<poem>", or the end of the page."""
    open_m = re.search(r"<poem>", wt)
    if not open_m:
        return None
    start = open_m.end()
    close_m = re.search(r"</poem>", wt[start:])
    next_open_m = re.search(r"<poem>", wt[start:])
    if close_m and (not next_open_m or close_m.start() < next_open_m.start()):
        end = start + close_m.start()
    elif next_open_m:
        end = start + next_open_m.start()
    else:
        end = len(wt)
    return wt[start:end]


def parse_chapter(page_title, is_first_chapter=False, is_appendix=False):
    wt = wikitext(page_title)
    if wt is None:
        return None, []
    poem = extract_poem_block(wt)
    if poem is None:
        return None, []

    # Normalize the precomposed double-danda character (U+0965 "॥") to two
    # single-dandas (U+0964 "।।") up front -- some chapters' transcribers
    # typed the single Unicode codepoint, others typed the single danda
    # twice, both rendering identically but only the latter matched every
    # downstream danda-counting rule until this was found (chapter 50 came
    # back with real content but zero verses -- checked directly rather
    # than assumed to be yet another punctuation-pairing variant).
    poem = poem.replace("॥", "।।")

    if is_first_chapter:
        poem = poem.replace(MANGALA_TEXT, "")

    # 0. Strip print-edition page-number markers ("प्. ४१४)" = "p. 414)"),
    # present only in the later, ASCII-pipe-convention chapters.
    poem = PAGE_MARKER_RX.sub("", poem)

    # 1. Strip footnote apparatus blocks (line-based state machine). Most
    # chapters delimit these with a dash-line ("---------"); chapter 59
    # instead uses an underscore-line ("__________________") -- checked
    # directly against its raw wikitext, not assumed -- so both characters
    # are accepted as the same paired open/close delimiter.
    lines = poem.split("\n")
    out_lines = []
    in_footnote = False
    for line in lines:
        if DASH_LINE.fullmatch(line.strip("\n")):
            in_footnote = not in_footnote
            continue
        if not in_footnote:
            out_lines.append(line)
    poem = "\n".join(out_lines)

    # 2. Strip editorial subheadings. The two conventions in this work
    # format them differently -- tab-indented in chapters 1-42 (not always
    # isolated by blank lines on both sides, so an isolation-only check
    # regressed and let subheading text leak into verse 2.61's body when
    # tried), plain isolated paragraphs with no indentation from chapter 43
    # on. Kept as two separate rules, either one sufficient, rather than
    # one replacing the other.
    lines = poem.split("\n")
    kept = []
    for i, line in enumerate(lines):
        s = line.strip("\t ")
        has_punct = ("।" in line) or ("|" in line)
        if not s or has_punct:
            kept.append(line)
            continue
        tab_indented_subheading = line.startswith("\t")
        prev_blank = (i == 0) or not lines[i - 1].strip()
        next_blank = (i == len(lines) - 1) or not lines[i + 1].strip()
        isolated_subheading = prev_blank and next_blank
        if tab_indented_subheading or isolated_subheading:
            continue
        kept.append(line)
    poem = "\n".join(kept)

    # 3. Extract front-matter title line(s): no danda/pipe, no trailing dashes.
    lines = poem.split("\n")
    title_parts, rest_lines, in_title_zone = [], [], True
    for line in lines:
        s = line.strip()
        if in_title_zone and not s:
            if title_parts:
                in_title_zone = False
            continue
        no_punct = "।" not in s and "|" not in s
        if in_title_zone and s and no_punct and not re.search(r"-{2,}\s*$", s):
            title_parts.append(s)
            continue
        in_title_zone = False
        rest_lines.append(line)
    chapter_title = " ".join(title_parts)
    poem = "\n".join(rest_lines)

    # The parishishtam (appendix) page -- a sudarshana-sahasranama-stotra,
    # confirmed by reading its own raw wikitext -- numbers its verses with a
    # single sequential number ("।। ११९ ।।"), not the chapter.verse pairs
    # every regular adhyaya uses ("।। ५९-१ ।।"). It isn't itself part of any
    # numbered adhyaya, so it gets its own ref pattern and its own
    # (string-keyed) unit shape rather than being forced into REF_RX.
    ref_rx = APPENDIX_REF_RX if is_appendix else REF_RX

    # 4. Protect verse-ref markers, strip remaining bare digits (footnote
    # markers), restore in document order.
    refs = []
    def protect(mm):
        refs.append(mm.group(0))
        return SENTINEL
    poem = re.sub(ref_rx, protect, poem)
    poem = re.sub(r"\d+", "", poem)
    for r in refs:
        poem = poem.replace(SENTINEL, r, 1)

    # 5. Split into (chapter, verse, body) units.
    units = []
    prev_end = 0
    appendix_series = 1
    appendix_last_vs = 0
    for mm in ref_rx.finditer(poem):
        body = poem[prev_end:mm.start()]
        prev_end = mm.end()
        body = re.sub(r"\d+", "", body)
        body = re.sub(r"\s+", " ", body).strip(" \n\t।|")
        if body:
            if is_appendix:
                # The parishishtam turns out to hold two independently-
                # numbered sub-poems back to back on the same page (checked
                # directly: a 21-verse dhyana/nyasa preamble, then the
                # sahasranama proper, whose own numbering restarts at 1) --
                # a restart to literally 1 marks that boundary, so each
                # restart starts a fresh sub-item rather than colliding
                # verse numbers into one. (Not "any decrease" -- see the
                # same condition's own rationale in parse_chapter_critical,
                # where a plain decrease turned out to also fire on an
                # isolated duplicate verse number, not a real restart.)
                vs = to_int(mm.group(1))
                if vs == 1 and appendix_last_vs > 1:
                    appendix_series += 1
                appendix_last_vs = vs
                units.append((("parishishtam", appendix_series), vs, body))
            else:
                ch, vs = to_int(mm.group(1)), to_int(mm.group(2))
                units.append((ch, vs, body))
    return chapter_title, units


# Jayakhyasamhita (checked directly against its own raw wikitext, not
# assumed to match Ahirbudhnyasamhita just because both are Wikisource) is
# a different digitization entirely -- a critical edition with its own
# apparatus, not an OCR-style plain transcription. Verses are numbered
# per-chapter with a single sequential number ("।। 1 ।।", "।। 2 ।।", ...),
# not a chapter.verse pair, and its editorial apparatus -- variant
# readings, uncertain readings, section headings -- turns out to come in
# far more shapes than first appeared from a first, small sample (checked
# directly at full scale, not assumed from 2 chapters to hold for all 33):
# a bare digit or "*" marker attached straight to a word with the actual
# footnote text on its own line below; a marker-less inline variant
# spelling attached straight to a word ("घर्मे(र्मो)"); an uncertain
# reading marked with a trailing "?" instead of a marker character
# ("तम्(त्?)"); a parenthesized section heading immediately followed by
# " - " and real verse text *on the same line* ("(प्रधानात्...) -
# विभक्तं..."); and a bracketed variant of a *whole pada*, in either
# round parens or square brackets, sometimes standing alone on its own
# line and sometimes trailing real content on the same line
# ("...यथावद्वक्तुमर्हसि। [नारदो ब्रह्मणः ...]"). Chasing each shape with
# its own regex kept missing the next one; the one property genuinely
# true across all of them, checked directly against a real chapter's
# paren/bracket counts (always balanced, bar one stray trailing
# character in dropped tail text past the last verse), is that this
# source never uses "(...)" or "[...]" for real verse content at all --
# so instead every bracketed span, wherever it falls and however deep it
# nests, is apparatus and is stripped outright, inside-out via a
# fixed-point loop so a nested case like "(*. ... (Adyar Library Ms.)
# ... नीतः)" fully resolves.
#
# A recognizable Sanskrit chapter-colophon idiom, "<name> नाम <ordinal>
# पटलः।", appears as the true closing colophon (harmless -- it falls
# after the last verse ref and is never assigned to any unit) but was
# also found duplicated as a *front-matter* line before chapter 1's own
# verse 1 -- there it would otherwise leak into verse 1's body (it
# carries a danda, so the plain no-danda title-zone heuristic doesn't
# catch it), so it is stripped as its own line pattern, unrelated to the
# bracket stripping above.
CRITICAL_PAREN_SPAN_RX = re.compile(r"\([^()]*\)")
CRITICAL_BRACKET_SPAN_RX = re.compile(r"\[[^\[\]]*\]")
# Some Lakshmitantram chapters (adhyaya 25, checked directly) use curly
# braces for the exact same inline-marker/footnote-line apparatus other
# chapters use square brackets for ("श्रीः{1}---", "{1. श्रीरुवाच I. }")
# -- a third delimiter style, not seen in Ahirbudhnyasamhita/
# Jayakhyasamhita/Padmasamhita, so kept separate rather than added to the
# shared paren/bracket loop those already-verified paths use.
CRITICAL_CURLY_SPAN_RX = re.compile(r"\{[^{}]*\}")
CRITICAL_COLOPHON_LINE_RX = re.compile(r".*नाम\s+\S+\s*पटलः\s*।\s*$")
# The bare "20-3" crossref tag doesn't only sit on its own line (handled
# by CRITICAL_CROSSREF_LINE_RX below) -- checked directly, it also trails
# a danda directly, on both a colophon-idiom line ("...पटलः। 2-1") and a
# real verse pada's own closing danda ("...जगत्पते। 3-1"). One rule
# covers both: strip a trailing "N-M" tag wherever it follows a danda,
# before any line-shape-based check runs, so those checks always see a
# clean line ending right at the danda.
CRITICAL_DANDA_CROSSREF_RX = re.compile(r"।\s*[\d०-९]+-[\d०-९]+")
# A bare "20-3", "20-4" cross-reference tag (chapter-verse, unbracketed,
# unpunctuated) recurs on its own line after some verses -- patala 20
# alone carries 99 of them. Left alone, it isn't itself mistaken for a
# verse ref (no danda/pipe brackets), but the final bare-digit strip
# would still eat its digits and leave a bare "-" stitched onto the
# following verse's body -- stripped as a whole line instead, same
# treatment as the colophon-idiom line above.
CRITICAL_CROSSREF_LINE_RX = re.compile(r"^[\d०-९]+-[\d०-९]+$")


def parse_chapter_critical(page_title, chapter_num):
    wt = wikitext(page_title)
    if wt is None:
        return None, []
    poem = extract_poem_block(wt)
    if poem is None:
        return None, []
    poem = poem.replace("॥", "।।")
    poem = CRITICAL_DANDA_CROSSREF_RX.sub("।", poem)

    lines = poem.split("\n")
    kept = [l for l in lines if not CRITICAL_COLOPHON_LINE_RX.match(l.strip("\t "))]
    poem = "\n".join(kept)

    prev = None
    while prev != poem:
        prev = poem
        poem = CRITICAL_PAREN_SPAN_RX.sub("", poem)
        poem = CRITICAL_BRACKET_SPAN_RX.sub("", poem)

    # Checked directly at full 33-patala scale: a bare "?" (not wrapped in
    # parens, unlike "(तथाऽनेक?)") also turns up on its own as an
    # uncertain-reading/illegible-text marker, and a handful of "(" / ")"
    # survive unpaired -- genuine source typos (an opening or closing
    # paren with no partner at all, not a nesting case the fixed-point
    # loop above would resolve). Neither character is ever legitimate in
    # this corpus's verse text, so both are simply removed outright,
    # wherever they still stand once the paired stripping above is done.
    poem = poem.replace("?", "")
    poem = re.sub(r"[()\[\]]", "", poem)

    # A paren-wrapped section heading is sometimes followed by " - " and
    # real verse text on the *same* line ("(प्रधानात्...) - विभक्तं...");
    # once the heading itself is stripped above, that leaves a bare
    # "। - " stitched onto the next real pada. A danda is never itself
    # followed by a hyphen in this text, so this is unambiguous to clean
    # up -- not a guess at every possible hyphen use (a genuine word-wrap
    # hyphen, seen elsewhere in this corpus, sits at the end of a word
    # before a line break, never right after a danda).
    poem = re.sub(r"।\s*-\s+", "। ", poem)

    # A bracketed section heading's trailing "N-M" tag ("[...] 15-1") only
    # becomes an isolated bare-tag line -- matchable by
    # CRITICAL_CROSSREF_LINE_RX -- once the bracket itself is gone, so this
    # runs after the paren/bracket stripping above, not before it.
    lines = poem.split("\n")
    kept = [l for l in lines if not CRITICAL_CROSSREF_LINE_RX.match(l.strip("\t "))]
    poem = "\n".join(kept)

    # Front-matter title line(s): same no-danda/no-trailing-dash heuristic
    # as parse_chapter's own step 3, reused verbatim.
    lines = poem.split("\n")
    title_parts, rest_lines, in_title_zone = [], [], True
    for line in lines:
        s = line.strip()
        if in_title_zone and not s:
            if title_parts:
                in_title_zone = False
            continue
        no_punct = "।" not in s and "|" not in s
        if in_title_zone and s and no_punct and not re.search(r"-{2,}\s*$", s):
            title_parts.append(s)
            continue
        in_title_zone = False
        rest_lines.append(line)
    chapter_title = " ".join(title_parts)
    poem = "\n".join(rest_lines)

    refs = []
    def protect(mm):
        refs.append(mm.group(0))
        return SENTINEL
    poem = re.sub(APPENDIX_REF_RX, protect, poem)
    poem = re.sub(r"\d+", "", poem)
    for r in refs:
        poem = poem.replace(SENTINEL, r, 1)

    # A numbering restart to literally 1 here means the same thing it does
    # in the parishishtam: checked directly against patala 1's own raw
    # wikitext, its first ~78 verses turn out to be a separately-numbered
    # frame narrative (the sages' backstory), with the samhita's own text
    # proper restarting its numbering at 1 right after a section heading --
    # not a parsing artifact. Two other kinds of non-monotonicity are
    # different and deliberately NOT treated as a restart: a numbering
    # *gap* (e.g. patala 15 skips straight from 179 to 181), and an
    # isolated *duplicate* verse number the source itself repeats mid-
    # sequence (patala 20 labels two consecutive, different-content verses
    # both "3", then later both "304") -- checked directly, not assumed;
    # an earlier version treated any vs <= last_vs as a restart and that
    # duplicate alone fractured patala 20 into three bogus series. Only
    # vs == 1 immediately after a genuinely higher number is a restart.
    units = []
    prev_end = 0
    series = 1
    last_vs = 0
    for mm in APPENDIX_REF_RX.finditer(poem):
        body = poem[prev_end:mm.start()]
        prev_end = mm.end()
        body = re.sub(r"\d+", "", body)
        # A stray leading "-" can still remain here specifically -- when a
        # removed bracket/paren sat right at the very start of this
        # verse's own body slice, not after a danda inside it (the
        # danda-adjacent case is already cleaned up above) -- trimmed like
        # the other leftover punctuation rather than kept as real text.
        body = re.sub(r"\s+", " ", body).strip(" \n\t।|-")
        if body:
            vs = to_int(mm.group(1))
            if vs == 1 and last_vs > 1:
                series += 1
            last_vs = vs
            units.append(((chapter_num, series), vs, body))
    return chapter_title, units


# Lakshmitantram shares Jayakhyasamhita's per-chapter single-number ref
# convention, but its apparatus is a genuinely different shape, checked
# directly against adhyaya 1's own raw wikitext rather than assumed to
# match just because both share that ref convention: variant-reading
# footnotes are square-bracket-wrapped, referenced by an inline "[N]"
# marker attached straight to a word (handled by the same generic
# bracket-span stripping already built for Jayakhyasamhita) -- but each
# verse's own textual commentary sits on a *tab-indented* line right
# after its ref, with no bracket or paren of its own at all
# ("\t1. नम इति विशिष्टोपायस्य..."), sometimes reduced to a placeholder
# dash-run when there's no variant ("\t8. - - - - - - - - - - -"), and
# at least once (adhyaya 1, after verse 4) continuing across several
# *more* tab-indented lines quoting a complete extra benedictory verse
# under a "टिप्पणी" ("gloss") sub-heading, itself just another tab-
# indented line. One rule covers the whole family: real verse text in
# this source is never itself tab-indented (confirmed directly -- the
# front matter's own tab-indented title lines are already consumed by
# the title-zone extraction below before this runs, so this only ever
# touches genuine apparatus), so any line starting with a tab is
# dropped outright, however many of them run together.
def parse_chapter_lakshmi(page_title, chapter_num):
    wt = wikitext(page_title)
    if wt is None:
        return None, []
    poem = extract_poem_block(wt)
    if poem is None:
        return None, []
    poem = poem.replace("॥", "।।")

    prev = None
    while prev != poem:
        prev = poem
        poem = CRITICAL_PAREN_SPAN_RX.sub("", poem)
        poem = CRITICAL_BRACKET_SPAN_RX.sub("", poem)
        poem = CRITICAL_CURLY_SPAN_RX.sub("", poem)

    # Front-matter title line(s): same no-danda/no-trailing-dash heuristic
    # as parse_chapter's own step 3, reused verbatim.
    lines = poem.split("\n")
    title_parts, rest_lines, in_title_zone = [], [], True
    for line in lines:
        s = line.strip()
        if in_title_zone and not s:
            if title_parts:
                in_title_zone = False
            continue
        no_punct = "।" not in s and "|" not in s
        if in_title_zone and s and no_punct and not re.search(r"-{2,}\s*$", s):
            title_parts.append(s)
            continue
        in_title_zone = False
        rest_lines.append(line)
    chapter_title = " ".join(title_parts)
    poem = "\n".join(rest_lines)

    poem = "\n".join(l for l in poem.split("\n") if not l.startswith("\t"))

    refs = []
    def protect(mm):
        refs.append(mm.group(0))
        return SENTINEL
    poem = re.sub(APPENDIX_REF_RX, protect, poem)
    poem = re.sub(r"\d+", "", poem)
    for r in refs:
        poem = poem.replace(SENTINEL, r, 1)

    units = []
    prev_end = 0
    series = 1
    last_vs = 0
    for mm in APPENDIX_REF_RX.finditer(poem):
        body = poem[prev_end:mm.start()]
        prev_end = mm.end()
        body = re.sub(r"\d+", "", body)
        body = re.sub(r"\s+", " ", body).strip(" \n\t।|-")
        if body:
            vs = to_int(mm.group(1))
            if vs == 1 and last_vs > 1:
                series += 1
            last_vs = vs
            units.append(((chapter_num, series), vs, body))
    return chapter_title, units


# Padmasamhita (checked directly against a chapter sample from each of
# its 4 padas, not assumed to share one convention just because they're
# part of the same work) uses the same chapter.verse ref pairing
# Ahirbudhnyasamhita/Vishnusamhita do, but each pada's own editorial
# apparatus differs: yogapada wraps section headings in asterisks
# ("*योगद्वैविध्यम्*"), kriyapada's headings carry no delimiter at all,
# just a bare "." where a verse line would instead end in a danda
# ("स्थानद्यैविध्यम्."), jnanapada's sampled chapter carries no section
# headings at all, and charyapada wraps them in a tab-indented double
# pipe ("|| विलोमनिरूपणम्.||"). One shared rule covers all four without
# needing to know which pada a given page belongs to: a heading line
# never carries a danda/pipe of its own (real verse text always does),
# so any such line that's either asterisk-wrapped, double-pipe-wrapped,
# or simply ends in a bare "." is apparatus, not text. Footnotes across
# all 4 padas use the same bracket/paren apparatus as Jayakhyasamhita's
# critical convention (inline bare-digit markers, footnote text on its
# own parenthesized line) -- reused directly via the same paren/bracket
# fixed-point stripping loop.
#
# jnanapada's sampled chapter was also seen dropping the chapter prefix
# on at least one verse ref ("।। 10 ।।" instead of "।। 1.10 ।।") -- and,
# checked directly, found kriyapada adhyaya 16 wasn't the only place a
# ref's own chapter digit can't be trusted: its own raw wikitext reads
# "।। 116.56 ।।" sitting directly between two verses correctly marked
# "16.55" and "16.57" -- a plain source-side typo (an extra "1"), not a
# real chapter-116-out-of-32. Since the page's own true chapter number
# is already known externally (this function's own `chapter_num`
# parameter, taken from the page title, which every convention agrees is
# reliable), a two-number ref's own captured chapter digit is never used
# at all -- the ref pattern only needs to recognize *where* a ref sits
# and pull out its verse number; `chapter_num` supplies the chapter
# unconditionally, closing this whole class of typo rather than
# hand-fixing the one instance found.
#
# Checked directly at full scale: yogapada/kriyapada's asterisk-wrapped
# headings also turn up in two further variants -- a leading "?" before
# the opening "*" ("?* परवारकल्पनम्.*"), and "?" substituted for the
# closing "*" outright ("* कौतुकायाममानम्?") -- recurring often enough
# (several chapters, several times each) to be a real, if inconsistent,
# transcription habit rather than one-off typos, unlike the isolated
# unbalanced-paren cases elsewhere in the corpus that are left alone.
# "*" and "?" are treated as interchangeable heading delimiters, either
# one allowed at either end, the same way "।" and "|" already are for
# verse-ref brackets elsewhere in this file.
PADMA_HEADING_ASTERISK_RX = re.compile(r"^[*?].*[*?]$")
PADMA_HEADING_PIPE_RX = re.compile(r"^\|\|.*\|\|$")
PADMA_HEADING_BAREPERIOD_RX = re.compile(r"^[^।|]*[^।|\s]\.$")
PADMA_REF_RX = re.compile(
    r"[।|]{2}\s*(?:([\d०-९]+)[.\-]([\d०-९]+)|([\d०-९]+))\s*[।|]{2}"
)


def parse_chapter_padma(page_title, chapter_num):
    wt = wikitext(page_title)
    if wt is None:
        return None, []
    poem = extract_poem_block(wt)
    if poem is None:
        return None, []
    poem = poem.replace("॥", "।।")

    prev = None
    while prev != poem:
        prev = poem
        poem = CRITICAL_PAREN_SPAN_RX.sub("", poem)
        poem = CRITICAL_BRACKET_SPAN_RX.sub("", poem)

    # A "*"/"?"-delimited heading can span *several* tab-indented lines,
    # with the opening delimiter on the first and the closing one only on
    # the last ("\t* भगवतः मन्दिरे परिचर्यापराणां\n\tक्षेत्रादिप्रदानां
    # ...फलप्रश्नः.*") -- checked directly, not assumed single-line the
    # way every other sampled heading was. The per-line check below can't
    # see that. Real verse text in this source is never itself tab-
    # indented (same property already relied on for Lakshmitantram), so
    # any tab-indented line is dropped outright first, subsuming the
    # multi-line case without needing to pair "*"/"?" characters across
    # the whole poem -- which would be unsafe here, since a bare "?" is
    # also used on its own, unpaired, as an inline uncertain-reading
    # marker (handled separately below).
    poem = "\n".join(l for l in poem.split("\n") if not l.startswith("\t"))

    lines = poem.split("\n")
    kept = []
    for line in lines:
        s = line.strip("\t ")
        if (PADMA_HEADING_ASTERISK_RX.match(s)
                or PADMA_HEADING_PIPE_RX.match(s)
                or PADMA_HEADING_BAREPERIOD_RX.match(s)):
            continue
        kept.append(line)
    poem = "\n".join(kept)

    # A bare, unpaired "?" turns up constantly in charyapada/kriyapada
    # verse lines themselves, mid-sentence, marking an uncertain reading
    # ("जराया ? वा पञ्चिगव्यं", "विंशच्छतैस्तु विमलेदहं?") -- checked
    # directly at full-corpus scale, not a rare one-off: over 50 verses
    # across several charyapada chapters alone. Every heading use of "?"
    # was already consumed above (as a line-boundary delimiter, or as
    # part of a tab-indented block), so any "?" still left at this point
    # is this inline marker and is dropped -- replaced with a space
    # rather than deleted outright, since it isn't always surrounded by
    # its own whitespace in the source.
    poem = poem.replace("?", " ")

    # Front-matter title line(s): same no-danda/no-trailing-dash heuristic
    # as parse_chapter's own step 3, reused verbatim.
    lines = poem.split("\n")
    title_parts, rest_lines, in_title_zone = [], [], True
    for line in lines:
        s = line.strip()
        if in_title_zone and not s:
            if title_parts:
                in_title_zone = False
            continue
        no_punct = "।" not in s and "|" not in s
        if in_title_zone and s and no_punct and not re.search(r"-{2,}\s*$", s):
            title_parts.append(s)
            continue
        in_title_zone = False
        rest_lines.append(line)
    chapter_title = " ".join(title_parts)
    poem = "\n".join(rest_lines)

    refs = []
    def protect(mm):
        refs.append(mm.group(0))
        return SENTINEL
    poem = re.sub(PADMA_REF_RX, protect, poem)
    poem = re.sub(r"\d+", "", poem)
    for r in refs:
        poem = poem.replace(SENTINEL, r, 1)

    units = []
    prev_end = 0
    for mm in PADMA_REF_RX.finditer(poem):
        body = poem[prev_end:mm.start()]
        prev_end = mm.end()
        body = re.sub(r"\d+", "", body)
        body = re.sub(r"\s+", " ", body).strip(" \n\t।|-")
        if body:
            # The ref's own chapter digit (group 1, present only for the
            # two-number form) is never used -- see this function's own
            # docstring comment on PADMA_REF_RX above.
            vs = to_int(mm.group(2)) if mm.group(1) is not None else to_int(mm.group(3))
            units.append((chapter_num, vs, body))
    return chapter_title, units


CHAPTER_NUM_RX = re.compile(r"([\d०-९]+)\s*$")


def build(work_title_devanagari, index_page_devanagari, out_rel_path, source_url,
          repo_root, note_extra="", request_delay=2.0, convention="ocr"):
    """Resumable: progress is cached in a sidecar `.progress.json` next to
    the output file (per source page, not per chapter, since one page can
    be re-fetched idempotently). A RateLimited failure mid-run saves what's
    done and stops cleanly -- re-running the same command later picks up
    only the remaining pages rather than re-fetching everything, and never
    silently ships a partial text as if it were the whole one (the run
    only writes the final data.json once every page has been fetched)."""
    import os

    out_path = repo_root + "/" + out_rel_path
    cache_path = out_path + ".progress.json"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    cache = {}
    if os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as f:
            cache = json.load(f)
        print(f"resuming from cache: {len(cache)} pages already fetched")

    print(f"fetching index: {index_page_devanagari}")
    pages = subpage_list(index_page_devanagari)
    print(f"  {len(pages)} subpages found")

    try:
        for i, page in enumerate(pages):
            if page in cache:
                continue
            is_first = (i == 0)
            if convention in ("critical", "lakshmi"):
                num_m = CHAPTER_NUM_RX.search(page)
                chapter_num = to_int(num_m.group(1)) if num_m else i + 1
                if convention == "lakshmi":
                    title, units = parse_chapter_lakshmi(page, chapter_num=chapter_num)
                else:
                    title, units = parse_chapter_critical(page, chapter_num=chapter_num)
            else:
                is_appendix = page.endswith("परिशिष्टम्")
                title, units = parse_chapter(page, is_first_chapter=is_first, is_appendix=is_appendix)
            cache[page] = {"title": title, "units": units}
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False)
            if not units:
                print(f"  SKIP {page}: page exists but carries no parseable verse content")
            else:
                print(f"  {page}: {len(units)} verses")
            time.sleep(request_delay)
    except RateLimited as e:
        done = sum(1 for p in pages if p in cache)
        print(f"\nRATE LIMITED after {done}/{len(pages)} pages: {e}")
        print(f"Progress saved to {cache_path} -- re-run this command later to resume.")
        return None, None

    missing = [p for p in pages if p not in cache]
    if missing:
        print(f"\nWARNING: {len(missing)} pages never fetched (not rate-limited, "
              f"just not yet attempted): {missing}")
        return None, None

    # A chapter key is either a bare int adhyaya/patala number (the common
    # case), or a 2-element (base, series) tuple: either ("parishishtam",
    # series) for the appendix, or (chapter_num, series) for a chapter
    # whose own numbering restarts mid-chapter (found directly in
    # Jayakhyasamhita patala 1 -- a frame narrative numbered 1-78, then the
    # samhita's own text restarting at 1). If this run resumed from an
    # on-disk `.progress.json` cache, such a tuple round-tripped through
    # JSON as a 2-element list -- normalized back to a tuple here too
    # (fresh runs already have real tuples; this is a no-op for those).
    # `normalize_key` collapses the (base, series=1) case to the bare base
    # so a series-less chapter's key always matches, whichever of
    # parse_chapter's or parse_chapter_critical's shape it came from.
    def chapter_key_parts(ch):
        if isinstance(ch, (list, tuple)) and len(ch) == 2:
            base, series = ch
            return base, series, (base == "parishishtam")
        return ch, 1, False

    def normalize_key(ch):
        base, series, is_app = chapter_key_parts(ch)
        return ("parishishtam", series) if is_app else (base if series == 1 else (base, series))

    all_units = []
    chapter_titles = {}
    for page in pages:
        title, units = cache[page]["title"], cache[page]["units"]
        if not units:
            continue
        chapters_seen = sorted(set(normalize_key(u[0]) for u in units), key=chapter_key_parts)
        for c in chapters_seen:
            if c not in chapter_titles and title:
                chapter_titles[c] = title
        all_units.extend(units)

    by_chapter = {}
    for ch, vs, body in all_units:
        ch = normalize_key(ch)
        by_chapter.setdefault(ch, []).append((vs, body))

    # Regular adhyayas sort numerically, series in order, and come first;
    # the appendix (a string-based key, not an adhyaya number) always
    # sorts last, whatever its magnitude would otherwise suggest.
    def chapter_sort_key(ch):
        base, series, is_app = chapter_key_parts(ch)
        return (1, 0, series) if is_app else (0, base, series)

    items = []
    for ch in sorted(by_chapter, key=chapter_sort_key):
        base, series, is_app = chapter_key_parts(ch)
        shlokas = []
        for vs, iast_or_deva in sorted(by_chapter[ch]):
            # Wikisource content here is ALREADY Devanagari (unlike GRETIL's
            # IAST) -- no transliteration needed.
            shlokas.append({"number": vs, "sanskrit_text": iast_or_deva})
        # The extracted page title describes the page's own opening
        # heading, not a mid-page numbering restart -- only used for the
        # first series, so a "Part 2"+ continuation always gets its own
        # distinguishing default label instead of the first series' title.
        if is_app:
            default_ref = "Parishishtam (Appendix)" if series == 1 else f"Parishishtam (Appendix), Part {series}"
            ref = chapter_titles.get(ch, default_ref) if series == 1 else default_ref
            item_id = "parishishtam" if series == 1 else "parishishtam%d" % series
        else:
            default_ref = f"Adhyaya {base}" if series == 1 else f"Adhyaya {base}, Part {series}"
            ref = chapter_titles.get(ch, default_ref) if series == 1 else default_ref
            item_id = "adhyaya%02d" % base if series == 1 else "adhyaya%02d_part%d" % (base, series)
        items.append({
            "id": item_id,
            "reference": f"{work_title_devanagari}, {ref}",
            "shlokas": shlokas,
        })

    total_verses = sum(len(it["shlokas"]) for it in items)
    out = {
        "schema": "generic",
        "default_author": "Traditionally revealed (Pancharatra Agama)",
        "source": f"Sanskrit Wikisource, {source_url}",
        "licence": "CC BY-SA 4.0",
        "note": (f"{len(items)} adhyayas, {total_verses} shlokas total, transcribed "
                 f"by Sanskrit Wikisource contributors."
                 + (" " + note_extra if note_extra else "")),
        "items": items,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.remove(cache_path)
    print(f"WROTE {out_rel_path}: {len(items)} adhyayas, {total_verses} verses")
    return items, total_verses


# (id_prefix, Devanagari pada name, index-page fetch title, chapter link
# prefix). Checked directly, not assumed uniform: yogapada's own index is
# reachable at the bare pada name, but kriyapada/jnanapada/charyapada's
# bare names either 404 or (kriyapada) redirect -- each only resolves at
# "पद्मसंहिता/<pada>". Every pada's *chapter* pages, regardless, link from
# their own index as a bare "<pada>/अध्यायः N" with no "पद्मसंहिता/"
# prefix at all -- see subpage_list's docstring.
PADMA_PADAS = [
    ("yoga", "योगपादः", "योगपादः", "योगपादः"),
    ("kriya", "क्रियापादः", "पद्मसंहिता/क्रियापादः", "क्रियापादः"),
    ("jnana", "ज्ञानपादः", "पद्मसंहिता/ज्ञानपादः", "ज्ञानपादः"),
    ("charya", "चर्यापादः", "पद्मसंहिता/चर्यापादः", "चर्यापादः"),
]


def build_padma(out_rel_path, source_url, repo_root, request_delay=2.0):
    """Padmasamhita doesn't fit build()'s single-work shape: it's 4
    independently-numbered sub-works (each pada restarts adhyaya
    numbering at 1), reached through inconsistent page-title conventions
    per pada (see PADMA_PADAS above) -- one shared progress cache (keyed
    "<pada_id>:<page>" so the 4 padas' own page titles, which can collide
    on plain "अध्यायः १", never collide with each other) and one final
    data.json with pada-qualified item ids instead."""
    import os

    out_path = repo_root + "/" + out_rel_path
    cache_path = out_path + ".progress.json"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    cache = {}
    if os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as f:
            cache = json.load(f)
        print(f"resuming from cache: {len(cache)} pages already fetched")

    pada_pages = {}
    for pid, pname, index_title, link_prefix in PADMA_PADAS:
        print(f"fetching pada index: {pname} ({index_title})")
        pages = subpage_list(index_title, link_prefix=link_prefix)
        print(f"  {len(pages)} chapters found")
        pada_pages[pid] = pages

    try:
        for pid, pname, index_title, link_prefix in PADMA_PADAS:
            for page in pada_pages[pid]:
                cache_key = f"{pid}:{page}"
                if cache_key in cache:
                    continue
                num_m = CHAPTER_NUM_RX.search(page)
                chapter_num = to_int(num_m.group(1)) if num_m else None
                title, units = parse_chapter_padma(page, chapter_num=chapter_num)
                cache[cache_key] = {"title": title, "units": units}
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(cache, f, ensure_ascii=False)
                if not units:
                    print(f"  SKIP {pid}:{page}: page exists but carries no parseable verse content")
                else:
                    print(f"  {pid}:{page}: {len(units)} verses")
                time.sleep(request_delay)
    except RateLimited as e:
        done = sum(1 for pid, *_ in PADMA_PADAS for p in pada_pages[pid] if f"{pid}:{p}" in cache)
        total = sum(len(pada_pages[pid]) for pid, *_ in PADMA_PADAS)
        print(f"\nRATE LIMITED after {done}/{total} pages: {e}")
        print(f"Progress saved to {cache_path} -- re-run this command later to resume.")
        return None, None

    missing = [f"{pid}:{p}" for pid, *_ in PADMA_PADAS for p in pada_pages[pid]
               if f"{pid}:{p}" not in cache]
    if missing:
        print(f"\nWARNING: {len(missing)} pages never fetched (not rate-limited, "
              f"just not yet attempted): {missing}")
        return None, None

    items = []
    for pid, pname, index_title, link_prefix in PADMA_PADAS:
        by_chapter = {}
        chapter_titles = {}
        for page in pada_pages[pid]:
            entry = cache[f"{pid}:{page}"]
            title, units = entry["title"], entry["units"]
            if not units:
                continue
            chapters_seen = sorted(set(u[0] for u in units))
            for c in chapters_seen:
                if c not in chapter_titles and title:
                    chapter_titles[c] = title
            for ch, vs, body in units:
                by_chapter.setdefault(ch, []).append((vs, body))
        for ch in sorted(by_chapter):
            shlokas = [{"number": vs, "sanskrit_text": text}
                       for vs, text in sorted(by_chapter[ch])]
            ref = chapter_titles.get(ch, f"Adhyaya {ch}")
            items.append({
                "id": "%s_adhyaya%02d" % (pid, ch),
                "reference": f"पद्मसंहिता, {pname}, {ref}",
                "shlokas": shlokas,
            })

    total_verses = sum(len(it["shlokas"]) for it in items)
    out = {
        "schema": "generic",
        "default_author": "Traditionally revealed (Pancharatra Agama)",
        "source": f"Sanskrit Wikisource, {source_url}",
        "licence": "CC BY-SA 4.0",
        "note": (f"{len(items)} adhyayas across 4 independently-numbered padas "
                 f"(yoga, kriya, jnana, charya), {total_verses} shlokas total, "
                 f"transcribed by Sanskrit Wikisource contributors."),
        "items": items,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.remove(cache_path)
    print(f"WROTE {out_rel_path}: {len(items)} adhyayas, {total_verses} verses")
    return items, total_verses


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("work_title",
                     help="Ignored with --padma (pass a placeholder) -- "
                          "Padmasamhita's 4 padas each carry their own name "
                          "instead.")
    ap.add_argument("index_page",
                     help="Ignored with --padma (pass a placeholder).")
    ap.add_argument("out_rel_path")
    ap.add_argument("source_url")
    ap.add_argument("--repo-root", default="/home/user/bhumandala")
    ap.add_argument("--note-extra", default="")
    ap.add_argument("--convention", choices=["ocr", "critical", "lakshmi"], default="ocr",
                     help="'ocr' (default) for a plain-transcription page like "
                          "Ahirbudhnyasamhita/Vishnusamhita; 'critical' for a "
                          "critical-edition page with per-chapter verse "
                          "numbering and a bracket/paren apparatus, like "
                          "Jayakhyasamhita; 'lakshmi' for Lakshmitantram's own "
                          "tab-indented-commentary apparatus.")
    ap.add_argument("--padma", action="store_true",
                     help="Padmasamhita's own 4-pada build path instead of "
                          "the single-work build() -- see build_padma().")
    args = ap.parse_args()
    if args.padma:
        build_padma(args.out_rel_path, args.source_url, args.repo_root)
    else:
        build(args.work_title, args.index_page, args.out_rel_path, args.source_url,
              args.repo_root, args.note_extra, convention=args.convention)
