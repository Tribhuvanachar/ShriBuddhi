#!/usr/bin/env python3
"""Segment the staged Veṅkaṭeśa Māhātmya into addressed verses.

श्रीवेङ्कटेशमाहात्म्यम्, from the Bhaviṣyottara Purāṇa, printed with TWO
commentaries. 854 pages of Sarvam Document AI covering 3-856 with no gaps, and
a full Google Vision pass over the same book, which is why a disagreement
between the two can be evidence here rather than a guess.

WHAT THE EDITION GIVES US, measured across all 854 pages rather than read off
one:

  * The ADHYĀYA is announced by a section-title `॥ अथ नवमोऽध्यायः ॥` and closed
    by a colophon `।। इति ... अष्टमोऽध्यायः ।।`. The running header carries the
    adhyāya too, but it LAGS: adhyāya 9 opens on p455 and the header does not
    say so until p457, so a header-only reading loses the first verses of
    nearly every adhyāya.
  * The TWO COMMENTARIES name themselves in a block of their own --
    कल्याणकाण्डदीपः (620) and गूढकर्तृकव्याख्यानम् (413), plus the OCR variants
    काण्डदीपः and गूढकर्तृकन्याख्यानम्. That block is tagged `section-title`
    sometimes and `paragraph` other times, so it has to be matched by its TEXT.
    The order is fixed: verse, then कल्याणकाण्डदीपः and its gloss, then
    गूढकर्तृकव्याख्यानम् and its gloss, then the next verse.
  * The VERSE NUMBER closes a block, and IN TWO DIFFERENT FORMS. 1,280 blocks
    close with ॥ N ॥ (U+0965 DEVANAGARI DOUBLE DANDA) and 584 with ।। N ।।
    (two U+0964 single dandas). Reading only the first form loses 31% of the
    markers outright and, worse, silently: adhyāya 9 read as 44 verses instead
    of 168 and looked like a book with very little commentary.
  * A MŪLA BLOCK OFTEN HOLDS SEVERAL VERSES. p456 carries 5 through 11 in one
    622-character block. Only the last marker closes the block, so without
    splitting, six of those seven verses are unreachable.
  * SPEAKER LABELS -- शुक उवाच-, धरण्युवाच-, शतानन्द उवाच- -- stand in blocks of
    their own and mark the mūla resuming after a gloss.

    python3 tools/venkatesha/segment.py --staged-dir <dir>
    python3 tools/venkatesha/segment.py --staged-dir <dir> --json report.json
"""

from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import re
import sys

ADHYAYA = {
    "प्रथमोऽध्यायः": 1, "द्वितीयोऽध्यायः": 2, "तृतीयोऽध्यायः": 3,
    "चतुर्थोऽध्यायः": 4, "पञ्चमोऽध्यायः": 5, "षष्ठोऽध्यायः": 6,
    "सप्तमोऽध्यायः": 7, "अष्टमोऽध्यायः": 8, "नवमोऽध्यायः": 9,
    "दशमोऽध्यायः": 10, "एकादशोऽध्यायः": 11,
}
# The two commentaries, with the OCR spellings that occur. गूढकर्तृकन्याख्यानम्
# is व्या misread as न्या, five times.
# A block OPENS a commentary when it is nothing but that commentary's name.
# Matched by shape rather than by an exact list, because the OCR spells both
# names several ways -- कल्याणाकाण्डदीपः, काल्याणकाण्डदीपः, गूढकर्तृव्याख्यानम्
# (no क), गूढकर्तृकन्याख्यानम् (व् read as न्), गूढकर्तृकब्याख्यानम् -- and an
# unrecognised opener does not fail loudly: its gloss is read as mūla instead,
# which is how 11 verses came to have a ṭīkā's name inside them.
#
# Anchored at both ends on purpose. Four blocks in the book are VERSES that
# mention a name -- काशतां काण्डदीपोऽयं यावदाचन्द्रतारकम् ।। is the closing
# benediction, not a heading -- and two are section headings referring to a
# commentary rather than opening one. All six carry text beyond the name and
# so do not match.
KALYANA_NAME = re.compile(
    r"^(?:नृपञ्चाननप्रणीत)?(?:का?ल्याणा?)?काण्डदीपः?\s*[।॥]*$")
GUDHA_NAME = re.compile(r"^गूढकर्तृक?[वबन]्?याख्यानम्?\s*[।॥]*$")


# The same two names as a PREFIX, for the blocks where the OCR ran the heading
# and the first line of its gloss together: p522 reads
# "कल्याणकाण्डदीपः शुकवत्तिकाया वादनतूलतन्तुरुपादानम् ।". Fourteen verses were
# really glosses of this shape. The trailing \s+ is what keeps the four
# benediction VERSES that mention a name out of it -- कल्याणकाण्डदीपेड्भूत्
# continues the word rather than ending it.
KALYANA_PREFIX = re.compile(
    r"^(?:नृपञ्चाननप्रणीत)?(?:का?ल्याणा?)?काण्डदीपः\s*[।॥]*\s+(?=\S)")
GUDHA_PREFIX = re.compile(r"^गूढकर्तृक?[वबन]्?याख्यानम्\s*[।॥]*\s+(?=\S)")


def commentary_named(text: str) -> str | None:
    """The ṭīkā this block names, if the block is nothing but that name."""
    flat = " ".join(text.split())
    if KALYANA_NAME.match(flat):
        return "kalyanakandadipa"
    if GUDHA_NAME.match(flat):
        return "gudhakartrikavyakhyana"
    return None


def commentary_prefixed(text: str) -> tuple[str, str] | None:
    """The ṭīkā this block OPENS and the gloss text that follows it, where the
    OCR ran the heading and its first line together."""
    flat = " ".join(text.split())
    m = KALYANA_PREFIX.match(flat)
    if m:
        return "kalyanakandadipa", flat[m.end():]
    m = GUDHA_PREFIX.match(flat)
    if m:
        return "gudhakartrikavyakhyana", flat[m.end():]
    return None


COMMENTARY_TITLES = {
    "kalyanakandadipa": "कल्याणकाण्डदीपः — नृपञ्चाननः",
    "gudhakartrikavyakhyana": "गूढकर्तृकव्याख्यानम्",
}

DEV_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
# BOTH danda forms. See the docstring: ignoring ।। loses 31% of the markers.
DD = r"(?:॥|।।)"
VERSE_NUM = re.compile(DD + r"\s*([0-9०-९]+)\s*" + DD)
CLOSE_NUM = re.compile(DD + r"\s*([0-9०-९]+)\s*" + DD + r"\s*[।॥]?\s*$")
BARE_NUM = re.compile(r"^\s*" + DD + r"?\s*([0-9०-९]+)\s*" + DD + r"?\s*$")
# ॥ अथ नवमोऽध्यायः ॥ -- the adhyaya opening, which the running header lags.
ADHYAYA_OPEN = re.compile(r"अथ\s+(\S+ऽध्यायः)")
# ।। इति ... अष्टमोऽध्यायः ।। -- the closing colophon. DOTALL because the block
# carries newlines, which is why an earlier [^\n] pattern matched none of them.
ADHYAYA_CLOSE = re.compile(r"इति.{0,300}?(\S+ऽध्यायः)", re.S)
SPEAKER = re.compile(r"^\S{2,20}(?:उवाच|ोवाच)\s*[-–—:]?\s*$")
# परिशिष्टम् - १ .. ४, the appendices, and the Kannada front matter. They are
# not part of any adhyāya, and while the adhyāya carried into them the last
# gloss of adhyāya 11 never closed: it ran to 109,687 characters, which is the
# rest of the book rather than a commentary on verse 450.
NOT_AN_ADHYAYA = re.compile(r"^(?:परिशिष्टम्|ಪ್ರಸ್ತಾವನೆ|[ivxlIVXL]+$|[0-9]+$)")

BLOCK = re.compile(r'<(\w+)[^>]*data-layout="([^"]+)"[^>]*>(.*?)</\1>', re.S)
TEXT_BLOCKS = ("paragraph", "section-title", "headline")


def untag(html: str) -> str:
    """HTML to text, keeping <br> as the line break it stands for."""
    return re.sub(r"<[^>]+>", " ", re.sub(r"<br\s*/?>", "\n", html)).strip()


def load_pages(staged_dir: str) -> dict[int, str]:
    """Every Sarvam page that came back, across all staged files.

    Sarvam's ranges overlap -- pages 163-702 was dispatched alongside 203-402
    and 403-602 -- so a page appears in several files and the first delivery
    wins. The Vision pass is a separate shape (plain `text`, no `ok`) and is
    read by vision_pages(), not here.
    """
    pages: dict[int, str] = {}
    for path in sorted(glob.glob(os.path.join(staged_dir, "*.json"))):
        if "vision" in os.path.basename(path):
            continue
        try:
            doc = json.loads(open(path, encoding="utf-8").read())
        except (OSError, ValueError):
            continue
        for page in doc.get("pages") or []:
            html = page.get("html") or page.get("text") or ""
            if page.get("ok") and html.strip():
                pages.setdefault(page["page"], html)
    return pages


def vision_pages(staged_dir: str) -> dict[int, str]:
    """The Vision pass, for checking a reading the Sarvam output makes doubtful."""
    out: dict[int, str] = {}
    for path in sorted(glob.glob(os.path.join(staged_dir, "*vision*.json"))):
        try:
            doc = json.loads(open(path, encoding="utf-8").read())
        except (OSError, ValueError):
            continue
        for page in doc.get("pages") or []:
            text = page.get("text") or ""
            if text.strip():
                out.setdefault(page["page"], text)
    return out


def adhyaya_of(text: str) -> int | None:
    """The adhyaya a block announces, closes, or heads."""
    flat = " ".join(text.split())
    if flat in ADHYAYA:
        return ADHYAYA[flat]
    m = ADHYAYA_OPEN.search(flat)
    if m and m.group(1) in ADHYAYA:
        return ADHYAYA[m.group(1)]
    return None


def adhyaya_closed_by(text: str) -> int | None:
    """The adhyaya a closing colophon names, if this block is one."""
    if "इति" not in text or "ऽध्याय" not in text:
        return None
    m = ADHYAYA_CLOSE.search(" ".join(text.split()))
    if m and m.group(1) in ADHYAYA:
        return ADHYAYA[m.group(1)]
    return None


def read_blocks(pages: dict[int, str]) -> tuple[list[dict], dict]:
    """The book as one ordered stream of text blocks, each carrying its adhyāya.

    The adhyāya is taken from the OPENING section-title where there is one,
    because the running header lags it by a page or two and losing the first
    verses of an adhyāya that way is silent.
    """
    current = None
    stream: list[dict] = []
    stats: collections.Counter = collections.Counter()
    for page in sorted(pages):
        for m in BLOCK.finditer(pages[page]):
            kind, body = m.group(2), untag(m.group(3))
            if kind in ("page-number", "footer", "footnote", "table"):
                continue
            if not body:
                continue
            if kind == "header":
                a = adhyaya_of(body)
                if a:
                    current = a
                    stats["adhyaya_from_header"] += 1
                elif NOT_AN_ADHYAYA.match(" ".join(body.split())):
                    current = None
                    stats["left_the_adhyayas"] += 1
                continue
            if kind not in TEXT_BLOCKS:
                continue
            closed = adhyaya_closed_by(body)
            if closed is not None:
                current = closed
                stats["adhyaya_colophons"] += 1
                continue
            opened = adhyaya_of(body)
            if opened is not None and len(body) < 60:
                current = opened
                stats["adhyaya_openings"] += 1
                continue
            name = commentary_named(body)
            if name is None:
                pre = commentary_prefixed(body)
                if pre:
                    name, body = pre[0], pre[1]
                    stats["heading_merged_into_its_gloss"] += 1
            stream.append({
                "page": page, "adhyaya": current, "kind": kind, "text": body,
                "opens": name,                     # this block NAMES a commentary
                "speaker": bool(SPEAKER.match(" ".join(body.split()))),
                "commentary": None,                # filled by mark_regions
            })
    return stream, dict(stats)


def mark_regions(stream: list[dict]) -> dict:
    """Set `commentary` to the ṭīkā key for every block inside a gloss.

    A commentary opens where it names itself and runs until the mūla resumes.
    The mūla resumes at a block that is verse-shaped: short, and closing with a
    verse number, or announced by a speaker label. Everything else between is
    gloss, however it happens to start -- the gloss on one verse runs over many
    blocks and across page breaks and only the first block names the ṭīkā.

    The same mistake as Rukmiṇīśa Vijaya is available here and is refused the
    same way: testing each block in isolation would make every continuation
    block eligible to be a verse, and a continuation that ended with a quoted
    ॥ N ॥ would become one.
    """
    stats: collections.Counter = collections.Counter()
    active = None
    at_adhyaya = None
    for b in stream:
        # A gloss cannot run from one adhyāya into the next. Left open it
        # swallows everything after it: one region ran to 109,687 characters,
        # which is not a commentary on a verse but the rest of the book.
        if active and b["adhyaya"] != at_adhyaya:
            active = None
            stats["closed_by_adhyaya"] += 1
        name = b["opens"]
        if name:
            active, at_adhyaya = name, b["adhyaya"]
            stats[f"opened_{name}"] += 1
            b["commentary"] = name
            continue
        if active and looks_like_mula(b):
            active = None
            stats["closed_by_mula"] += 1
        b["commentary"] = active
    return dict(stats)


def looks_like_mula(b: dict) -> bool:
    """Whether this block is the mūla text resuming after a gloss.

    Deliberately narrow. A gloss quotes verses constantly -- p41's
    गूढकर्तृकव्याख्यानम् quotes three lines of the Mahābhārata -- and those
    quotations do NOT carry a ॥ N ॥ of their own, which is what makes the
    closing marker usable at all.
    """
    if b["speaker"]:
        return True
    text = b["text"]
    if not CLOSE_NUM.search(text.rstrip()):
        return False
    if len(text) <= 700:
        return True
    # Length alone is the wrong test. p459 holds mūla verses 20 THROUGH 26 in
    # one 862-character block, and a flat cap left all seven inside the gloss
    # that preceded them -- the contiguous runs of missing verses in adhyāyas
    # 9, 10 and 11 were all this.
    #
    # What distinguishes a long mūla block from a long gloss that happens to
    # end on a quoted number is the RHYTHM of its markers: several of them, a
    # verse apart. A gloss quotes a number now and then, with paragraphs in
    # between.
    cuts = list(VERSE_NUM.finditer(text))
    if len(cuts) < 3:
        return False
    spans, prev = [], 0
    for m in cuts:
        spans.append(m.start() - prev)
        prev = m.end()
    return max(spans) <= 220


def split_multi_verse_blocks(stream: list[dict]) -> list[dict]:
    """Split a mūla block that holds several verses at its internal markers.

    p456 carries verses 5 through 11 in one 622-character block. Only the last
    marker closes a block, so six of those seven verses are unreachable without
    this. Runs after mark_regions and touches only blocks outside a gloss,
    because a gloss quotes numbers in passing and splitting one would end its
    region early.
    """
    out: list[dict] = []
    for b in stream:
        if b["commentary"] or b["opens"]:
            out.append(b)
            continue
        cuts = list(VERSE_NUM.finditer(b["text"]))
        if len(cuts) < 2 and not (
                len(cuts) == 1 and cuts[0].end() < len(b["text"].rstrip()) - 2):
            out.append(b)
            continue
        spans, prev = [], 0
        for m in cuts:
            spans.append(b["text"][prev:m.end()])
            prev = m.end()
        tail = b["text"][prev:].strip()
        if tail:
            spans.append(tail)
        pieces = [s.strip() for s in spans if s.strip()]
        if not all(10 <= len(s) <= 700 for s in pieces[:len(cuts)]):
            out.append(b)
            continue
        for text in pieces:
            piece = {**b, "text": text}
            # A piece can begin with a commentary heading: p459 is a SINGLE
            # 862-character block holding mūla verses 20-26 with the
            # कल्याणकाण्डदीपः gloss on each interleaved between them, so cutting
            # it at the markers hands back pieces that are gloss, not verse.
            pre = commentary_prefixed(text)
            if pre:
                piece["opens"], piece["text"] = pre[0], pre[1]
            elif commentary_named(text):
                piece["opens"] = commentary_named(text)
            piece["speaker"] = bool(SPEAKER.match(" ".join(piece["text"].split())))
            out.append(piece)
    return out


def segment(pages: dict[int, str]) -> dict:
    stream, header_stats = read_blocks(pages)
    region_stats = mark_regions(stream)
    split = split_multi_verse_blocks(stream)
    if len(split) != len(stream):
        # Splitting exposes headings that were buried mid-block, so the regions
        # are marked again over the split stream. Only the first pass decides
        # what to split, so this settles in two passes.
        for b in split:
            b["commentary"] = None
        region_stats = mark_regions(split)
        stream = split

    verses: dict[tuple[int, int], dict] = {}
    glosses: dict[tuple[int, int], dict] = collections.defaultdict(dict)

    # Pass 1 -- the mūla. Unnumbered mūla-shaped blocks accumulate and are
    # joined to the numbered one that closes them, because the verse is printed
    # a line per block: p489 prints 9.119 as two blocks of 53 and 62 characters
    # and only the second carries the marker.
    pending: list[dict] = []
    last: dict[int, int] = {}
    for b in stream:
        a = b["adhyaya"]
        if b["commentary"] or b["opens"] or not a:
            pending = []
            continue
        if b["speaker"]:
            continue
        m = CLOSE_NUM.search(b["text"].rstrip())
        if not m:
            if len(b["text"]) <= 400:
                pending.append(b)
            else:
                pending = []
            continue
        n = int(m.group(1).translate(DEV_DIGITS))
        run = [x for x in pending if x["adhyaya"] == a] + [b]
        pending = []
        if n < 1:
            continue
        text = "\n".join(x["text"] for x in run)
        if (a, n) not in verses:
            verses[(a, n)] = {"adhyaya": a, "verse": n, "page": run[0]["page"],
                              "text": text, "how": "marker"}
            last[a] = max(last.get(a, 0), n)

    # Pass 2 -- the two glosses, each attached to the verse standing above the
    # block that named it.
    current_key, current_addr, buf = None, None, []

    def flush():
        if current_key and current_addr and buf:
            joined = "\n".join(buf)
            if joined.strip():
                glosses[current_addr].setdefault(current_key, joined)

    seen_addr = None
    for b in stream:
        a = b["adhyaya"]
        if not b["commentary"] and not b["opens"]:
            m = CLOSE_NUM.search(b["text"].rstrip())
            if m and a:
                n = int(m.group(1).translate(DEV_DIGITS))
                if (a, n) in verses:
                    seen_addr = (a, n)
        if b["opens"]:
            flush()
            current_key, current_addr, buf = b["opens"], seen_addr, []
            continue
        if b["commentary"]:
            buf.append(b["text"])
        else:
            flush()
            current_key, current_addr, buf = None, None, []
    flush()

    for addr, g in glosses.items():
        if addr in verses:
            verses[addr]["commentaries"] = g

    per = collections.defaultdict(list)
    for (a, n) in verses:
        per[a].append(n)
    adhyayas = []
    for a in sorted(per):
        got = sorted(per[a])
        high = max(got)
        adhyayas.append({"adhyaya": a, "found": len(got), "highest": high,
                         "missing": [i for i in range(1, high + 1)
                                     if i not in set(got)]})
    return {
        "pages": len(pages),
        "page_range": [min(pages), max(pages)] if pages else [],
        "page_gaps": [n for n in range(min(pages), max(pages) + 1)
                      if n not in pages] if pages else [],
        "header_stats": header_stats,
        "region_stats": region_stats,
        "adhyayas": adhyayas,
        "verses_found": sum(a["found"] for a in adhyayas),
        "verses_missing": sum(len(a["missing"]) for a in adhyayas),
        "with_kalyana": sum(1 for v in verses.values()
                            if "kalyanakandadipa" in (v.get("commentaries") or {})),
        "with_gudha": sum(1 for v in verses.values()
                          if "gudhakartrikavyakhyana" in (v.get("commentaries") or {})),
        "verses": verses,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--staged-dir", required=True)
    ap.add_argument("--json", help="write the full report here")
    args = ap.parse_args(argv)

    pages = load_pages(args.staged_dir)
    if not pages:
        print(f"no delivered pages under {args.staged_dir}", file=sys.stderr)
        return 1
    rep = segment(pages)
    print(f"pages {rep['pages']} ({rep['page_range'][0]}-{rep['page_range'][1]}), "
          f"gaps {len(rep['page_gaps'])}")
    print(f"adhyaya markers: {rep['header_stats']}")
    print(f"commentary regions: {rep['region_stats']}")
    for a in rep["adhyayas"]:
        flag = "" if not a["missing"] else \
            f"  MISSING {len(a['missing'])}: {a['missing'][:8]}"
        print(f"  adhyaya {a['adhyaya']:<3} {a['found']:>4} verses, "
              f"highest {a['highest']:>3}{flag}")
    print(f"\n{rep['verses_found']} verses addressed, {rep['verses_missing']} missing")
    print(f"   {rep['with_kalyana']} with कल्याणकाण्डदीपः, "
          f"{rep['with_gudha']} with गूढकर्तृकव्याख्यानम्")
    if args.json:
        out = dict(rep)
        out["verses"] = [v for _, v in sorted(rep["verses"].items())]
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=1)
        print("report written to", args.json)
    return 0 if rep["verses_missing"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
