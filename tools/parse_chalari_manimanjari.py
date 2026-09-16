#!/usr/bin/env python3
"""
parse_chalari_manimanjari.py -- Chalari Acharya's commentary on the
Manimanjari, out of a transcribed .docx and into a staged layer.

Not OCR. The .docx is a keyed transcription (Google Lens, corrected by hand),
so the text arrives clean and the only work is finding where each verse ends
and its commentary begins. The edition's rhythm does that for us:

    [verse, line 1]                short, no closing number
    [verse, line 2 ... ॥ N ॥]      short, closes with the verse number
    [commentary ...]               long; quoted verses on their own '>' lines
    [... ॥ N ॥]                    the commentary closes with the same number

so a short paragraph that ends in a verse number is a verse, everything up to
the next one is its commentary, and the number is read off the page rather
than counted. The sarga turns at the colophon.

WHAT THIS TEXT IS, and it matters for how it is labelled: the transcription is
a normalised edition, not a diplomatic one. Against the scanned original it
splits sandhi the book prints joined (मरीचीति -> "मरीचिर्" इति), writes word
-division hyphens, supplies avagraha, and turns anusvara into the conjunct
nasal (अंगिराः -> अङ्गिराः). The substance matches; the orthography is the
transcriber's. The staged file says so on its face.

    python3 tools/parse_chalari_manimanjari.py IN.docx --report
    python3 tools/parse_chalari_manimanjari.py IN.docx --out layers/tika_chalari.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import zipfile

DIGITS = {chr(0x0966 + i): str(i) for i in range(10)}
DIGITS.update({str(i): str(i) for i in range(10)})
DIGIT_CLASS = "".join(sorted(DIGITS))
BAR = "।॥|"

END_NUMBER = re.compile(r"[%s]{1,2}\s*([%s]{1,3})\s*[%s]{1,2}\s*$" % (BAR, DIGIT_CLASS, BAR))
# The same closer, wherever it falls: the edition often runs three glosses
# into one paragraph -- "प्रजा" इति ... ॥ ९ ॥ "दित्याम्" इति ... ॥ १० ॥ -- and
# reading only the paragraph's final number left the first two verses bare.
ANY_NUMBER = re.compile(r"[%s]{1,2}\s*([%s]{1,3})\s*[%s]{1,2}" % (BAR, DIGIT_CLASS, BAR))
SARGA_NAMES = {
    "प्रथम": 1, "द्वितीय": 2,
    "तृतीय": 3, "चतुर्थ": 4,
    "पञ्चम": 5, "षष्ठ": 6,
    "सप्तम": 7, "अष्टम": 8,
}
# "इति श्री-मणिमञ्जर्यां प्रथमः सर्गः" and the longer signed forms.
COLOPHON = re.compile(r"इति\s*श्री.{0,200}?(%s)[^\s]*\s*सर्ग"
                      % "|".join(SARGA_NAMES), re.S)

# A verse line is a pada or two, never a paragraph of commentary.
VERSE_MAX_CHARS = 150


def to_int(s: str) -> int | None:
    try:
        return int("".join(DIGITS[c] for c in s))
    except (KeyError, ValueError):
        return None


def paragraphs(path: str) -> list[str]:
    """The document's paragraphs, in order, as plain text."""
    xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8")
    out = []
    for block in re.findall(r"<w:p[ >].*?</w:p>", xml, re.S):
        text = "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", block, re.S))
        text = (text.replace("&amp;", "&").replace("&gt;", ">")
                    .replace("&lt;", "<").replace("&quot;", '"').strip())
        if text:
            out.append(text)
    return out


def is_verse_close(text: str) -> int | None:
    """The verse number, if this paragraph COULD be a verse's last line."""
    if len(text) > VERSE_MAX_CHARS or text.startswith(">") or text.startswith('"'):
        return None
    match = END_NUMBER.search(text)
    return to_int(match.group(1)) if match else None


def is_verse_open(text: str) -> bool:
    """True for a verse's FIRST line, and this is the whole discriminator.

    A commentary's closing words are short and end in the verse number too --
    "इत्यमरः । इत्युभयत्र ज्ञेयं ॥ ३ ॥" is 33 characters and looks exactly
    like a verse. What it does not have is a verse line in front of it: it
    follows a quotation or a paragraph of prose. Requiring a real opening
    line is what tells the two apart, and without it the parse doubled verses
    and invented a sarga.
    """
    return bool(text
                and len(text) <= VERSE_MAX_CHARS
                and not text.startswith(">")
                and not text.startswith('"')
                and END_NUMBER.search(text) is None
                and COLOPHON.search(text) is None
                and text.rstrip().endswith("\u0964"))


def parse(paras: list[str]) -> list[dict]:
    """[{sarga, verse, mula, commentary}] in verse order.

    The edition does not alternate verse/commentary one for one. It often
    prints a RUN of verses and then the commentary on all of them:

        [45-46] verse 9   [47-48] verse 10   [49-50] verse 11
        [51]    "प्रजा" इति ... ॥ ९ ॥ "दित्याम्" इति ... ॥ १० ॥ ...

    so pairing each verse with the paragraphs that follow it leaves 96 verses
    looking uncommented while their gloss sits under the verse before. What
    does hold everywhere is that a gloss CLOSES with the number of the verse
    it glosses, and the verse closes with the same number -- the edition
    numbers both sides. So the commentary is cut at those closers and matched
    to the verse by number, and a number is only allowed to close a gloss when
    it is the one the next unglossed verse is waiting for. A quoted verse
    carrying its own number therefore cannot end a segment.
    """
    anchors = [i for i in range(1, len(paras))
               if is_verse_close(paras[i]) is not None and is_verse_open(paras[i - 1])]
    anchor_at = {i: n for n, i in enumerate(anchors)}
    verse_lines = set(anchors) | {i - 1 for i in anchors}

    units = [{"sarga": 0, "verse": is_verse_close(paras[i]),
              "mula": paras[i - 1] + "\n" + paras[i], "commentary": ""}
             for i in anchors]

    # Sarga: 1 until a colophon passes by, then the next one.
    sarga = 1
    for n, i in enumerate(anchors):
        units[n]["sarga"] = sarga
        stop = anchors[n + 1] - 1 if n + 1 < len(anchors) else len(paras)
        for b in paras[i + 1:stop]:
            match = COLOPHON.search(b)
            if match:
                sarga = SARGA_NAMES[match.group(1)] + 1
                break

    # Which sarga each paragraph sits in, so a gloss can be matched to its
    # verse by (sarga, number) rather than by a running pointer. A pointer
    # stalls forever the first time a number is misread or a verse carries no
    # gloss at all; a key does not.
    sarga_at: list[int] = []
    here = 1
    for text in paras:
        sarga_at.append(here)
        match = COLOPHON.search(text)
        if match:
            here = SARGA_NAMES[match.group(1)] + 1
    by_key = {(u["sarga"], u["verse"]): u for u in units}

    pending: list[str] = []
    for i, text in enumerate(paras):
        if i in verse_lines:
            continue
        cursor = 0
        for match in ANY_NUMBER.finditer(text):
            unit = by_key.get((sarga_at[i], to_int(match.group(1))))
            if unit is None or unit["commentary"]:
                continue
            pending.append(text[cursor:match.end()].strip())
            unit["commentary"] = "\n".join(x for x in pending if x).strip()
            pending = []
            cursor = match.end()
        rest = text[cursor:].strip()
        if rest:
            pending.append(rest)
    return units


def report(units: list[dict]) -> str:
    by_sarga: dict[int, list[int]] = {}
    for u in units:
        by_sarga.setdefault(u["sarga"], []).append(u["verse"])
    lines = ["%d units parsed" % len(units)]
    for sarga in sorted(by_sarga):
        verses = by_sarga[sarga]
        gaps = [v for v in range(1, max(verses) + 1) if v not in set(verses)]
        dupes = sorted({v for v in verses if verses.count(v) > 1})
        lines.append("  sarga %d: %d verses, highest %d%s%s"
                     % (sarga, len(verses), max(verses),
                        (", gaps %s" % gaps[:10]) if gaps else "",
                        (", repeated %s" % dupes[:10]) if dupes else ""))
    empty = [u for u in units if not u["commentary"].strip()]
    if empty:
        lines.append("  %d verse(s) with no commentary: %s"
                     % (len(empty), ["s%dv%d" % (u["sarga"], u["verse"]) for u in empty][:10]))
    chars = sum(len(u["commentary"]) for u in units)
    lines.append("  commentary: %s chars, %s median per verse"
                 % (f"{chars:,}", sorted(len(u["commentary"]) for u in units)[len(units) // 2]))
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 2)[1])
    ap.add_argument("docx")
    ap.add_argument("--out", default="", help="write the staged layer here")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args(argv)

    units = parse(paragraphs(args.docx))
    print(report(units))
    if args.report or not args.out:
        return 0

    blocks = [{
        "id": "s%d_v%d" % (u["sarga"], u["verse"]),
        "type": "tika_chalari",
        "sarga": u["sarga"],
        "verse": u["verse"],
        "text": u["commentary"],
        "mula_as_transcribed": u["mula"],
    } for u in units]
    doc = {
        "_readme": ("Chalari Acharya's commentary on the Manimanjari, parsed from a "
                    "keyed transcription by tools/parse_chalari_manimanjari.py. "
                    "NOT merged into the corpus -- review in admin/ocr-review.html first. "
                    "The transcription is a NORMALISED edition, not a diplomatic one: "
                    "against the scan it splits sandhi the book prints joined, adds "
                    "word-division hyphens and avagraha, and writes anusvara as the "
                    "conjunct nasal. Substance matches; orthography is the transcriber's."),
        "work": "manimanjari",
        "layer": "manimanjari/tika_chalari",
        "language": "sa",
        "engine": "keyed transcription (Google Lens, hand-corrected)",
        "mula_author": "श्रीनारायण"
                       "पण्डिताचार्यः",
        "commentator": "चलार्याचार्यः",
        "blocks": blocks,
    }
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(doc, handle, ensure_ascii=False, indent=1)
        handle.write("\n")
    print("wrote %s (%d units)" % (args.out, len(blocks)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
