"""Tier D parser: sa.wikisource.org.

Used where no TEI or JSON source exists, which for the kavya material means
the dramas and the satakas -- Bhasa, Sudraka, Visakhadatta, Bhartrhari,
Amaru -- none of which GRETIL carries.

Three things about Wikisource had to be met on its own terms:

RENDERED TEXT, NOT WIKITEXT.  Half of these works are ProofreadPage
transclusions: the page's wikitext is a header template and one line,
`<pages index="विक्रमाङ्कदेवचरितम् .djvu" from=1 to=504/>`, and the 60,000
words live in the Page: namespace behind it.  Asking the API for wikitext
returns 232 characters and no text at all, so this asks for the RENDERED html
(`prop=text`) and takes the text out of that.  It also disposes of every
template and infobox for free.

A VERSE NUMBER IS ONE NUMBER.  GRETIL writes `Ragh_1.1`; Wikisource closes a
verse with `।। ६ ।।` -- the chapter is the page, and the number is bare.  The
BARE matcher shared with the GRETIL parser requires at least two numeric
components, so on these pages it matched nothing, and this parser's own code
for the single-number case (`if len(parts) == 1`) could never run.  Hence a
matcher of its own here rather than a change to the shared one, which is
tuned for files where a bare number really would be a false positive.

THE PROSE IS THE PLAY.  A Sanskrit drama is prose with verses set into it, and
only the verses carry numbers.  Emitting just those would publish
Mrcchakatika as a book of quotations with the play removed.  So every block is
kept in document order: a numbered verse is `<act>.<n>`, and the prose that
follows it is `<act>.<n>.<k>`, which is three numeric parts and therefore
sorts between verse n and verse n+1 rather than after the whole act, as a
lettered id would.
"""
from __future__ import annotations

import html as _html
import re
from html.parser import HTMLParser

from ..common import deva_to_ascii_digits, norm_ws

TEMPLATE = re.compile(r"\{\{[^{}]*\}\}")
TAGS = re.compile(r"</?[^>]+>")
HEADING = re.compile(r"^\s*(=+)\s*(.+?)\s*\1\s*$", re.M)
LINK = re.compile(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]")

#: `।। ६ ।।`, `॥ 1.2 ॥`, `। ५ ।` -- one to three components, unlike the shared
#: GRETIL BARE matcher, which insists on two.
BARE_1 = re.compile(r"[।॥|]{1,2}\s*([\d०-९]+(?:\s*[.,]\s*[\d०-९]+){0,2})\s*[।॥|]{1,2}")

#: Rendered furniture that is not the text: edit links, page-number markers
#: from ProofreadPage, footnote backlinks, navigation boxes.
DROP_CLASSES = ("noprint", "mw-editsection", "pagenum", "reference",
                "mw-references", "navbox", "ws-noexport", "printfooter",
                "catlinks", "mw-jump-link", "toc")


class _Text(HTMLParser):
    """Rendered HTML -> text, with the block structure kept as blank lines."""

    BLOCK = {"p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "br",
             "dd", "dt", "blockquote", "poem"}
    SKIP = {"script", "style", "sup", "table"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self._skip = 0
        self._drop = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get("class", "") or ""
        if self._drop or any(c in cls for c in DROP_CLASSES):
            self._drop += 1
            return
        if tag in self.SKIP:
            self._skip += 1
            return
        if tag in self.BLOCK:
            self.out.append("\n\n")

    def handle_endtag(self, tag):
        if self._drop:
            self._drop -= 1
            return
        if tag in self.SKIP and self._skip:
            self._skip -= 1
            return
        if tag in self.BLOCK:
            self.out.append("\n\n")

    def handle_data(self, data):
        if self._skip or self._drop:
            return
        self.out.append(data)

    def text(self):
        return _html.unescape("".join(self.out))


def from_html(rendered):
    p = _Text()
    p.feed(rendered or "")
    return p.text()


def clean(wikitext):
    s = TEMPLATE.sub(" ", wikitext or "")
    s = LINK.sub(r"\1", s)
    s = TAGS.sub("\n", s)
    return s


DEVA = re.compile(r"[ऀ-ॿ]")


def is_sanskrit(body, floor=0.5):
    """Is this block the text, or the book around it?

    Wikisource's scanned editions carry their apparatus inline: an English
    introduction, an editor's name, a corrigenda table, running heads. Kadambari
    came through with 193 such blocks. This is a Devanagari corpus, so a block
    whose letters are mostly not Devanagari is not part of it. Prakrit passages
    in the dramas are written in Devanagari and are unaffected.
    """
    letters = [c for c in body if c.isalpha()]
    if not letters:
        return False
    return sum(1 for c in letters if DEVA.match(c)) / len(letters) >= floor


def split_units(text, default_chapter="1", wikitext=True, keep_prose=True):
    """Yield (ref_parts, is_prose, body) in document order.

    `text` is rendered text from from_html(), or raw wikitext when
    `wikitext=True` (the older path, kept for the fixtures).
    """
    if wikitext:
        text = clean(text)
    chapter = str(default_chapter)
    last_verse = "0"
    prose_n = 0
    for block in re.split(r"\n\s*\n", text):
        block = block.strip()
        if not block:
            continue
        h = HEADING.search(block)
        if h:
            digits = re.findall(r"[\d०-९]+", h.group(2))
            if digits:
                chapter = deva_to_ascii_digits(digits[0])
                last_verse, prose_n = "0", 0
            block = HEADING.sub(" ", block).strip()
            if not block:
                continue
        marks = list(BARE_1.finditer(block))
        if marks:
            m = marks[-1]          # the marker closes the verse it numbers
            ref = deva_to_ascii_digits(re.sub(r"\s+", "", m.group(1)))
            parts = [p for p in re.split(r"[.,]", ref) if p]
            if len(parts) == 1:
                parts = [chapter] + parts
            body = norm_ws(block[: m.start()])
            if body and is_sanskrit(body):
                last_verse, prose_n = parts[-1], 0
                yield parts, False, body
            continue
        if not keep_prose:
            continue
        body = norm_ws(block)
        # Wikisource pages carry stage directions and speaker lines that are
        # the play; they also carry one-word navigation crumbs that are not.
        if len(body) < 12 or not is_sanskrit(body):
            continue
        prose_n += 1
        yield [chapter, last_verse, str(prose_n)], True, body
