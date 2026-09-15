#!/usr/bin/env python3
"""
split_manimanjari_layers.py -- separate Maṇimañjarī's staged OCR into the
three layers the printed edition actually carries.

The 1930s edition prints, for every verse, a fixed cycle:

    [Raghavendracharya's Sanskrit vyakhyana on verse N,  ending ॥ N ॥]
    [the mula verse N]
    [॥ N ॥]
    [Raghavendracharya's Kannada anvaya-vyakhyana on verse N, ending || N ||]

OCR flattens all three into one stream of paragraphs, which is why the
staged file cannot be merged as-is: a reader would get commentary and verse
run together, and the Kannada gloss interleaved into Sanskrit prose. The
lead asked for the Sanskrit and Kannada commentaries to become separate
layers; this is the step that makes that possible.

Two facts about the page do the work, and neither is a guess:

  * Script separates Kannada from everything else outright -- the Kannada
    gloss is printed in Kannada script, the verse and Sanskrit tika in
    Devanagari. That is a Unicode range test, not a heuristic.
  * The mula verse is the block immediately followed by the standalone
    verse-number, and is verse-shaped (a couple of padas, not a paragraph).

Verses are segmented by the cycle, NOT by the OCR's digits. The printed
numerals are the least reliable thing on the page -- this scan reads १५ as
९५ and २० as ३०, often enough that keying on them mis-files verses. The
cycle itself never lies: the Kannada gloss closes a verse, so the first
Devanagari block after Kannada opens the next one. Verse numbers are
therefore ordinals within the sarga, and every OCR-read numeral is kept
beside them as a cross-check -- --report names each disagreement, which is
exactly what a reviewer needs to look at. Sarga comes from the running
head, which the edition prints on every page.

Output is three staged files under data/ocr_staging/<work>/layers/. Nothing
is merged: staged OCR stays staged until a person reviews it, same as every
other work in this pipeline.

    python3 tools/split_manimanjari_layers.py \
        --staged data/ocr_staging/manimanjari/sarvam_pages122-312.json
    python3 tools/split_manimanjari_layers.py --staged ... --report
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import sys

BLOCK_RE = re.compile(r"<(h\d|p|div|pre|blockquote)\b([^>]*)>(.*?)</\1>", re.S)
LAYOUT_RE = re.compile(r'data-layout="([^"]+)"')
CONF_RE = re.compile(r'data-confidence="([^"]+)"')

# Devanagari, Kannada, Gujarati and ASCII digits all turn up: the OCR reads
# the edition's Devanagari numerals as Kannada or Gujarati often enough that
# refusing them would drop real verse boundaries.
DIGITS = {}
for base, offset in (("०", 0), ("೦", 0), ("૦", 0)):
    for i in range(10):
        DIGITS[chr(ord(base) + i)] = str(i)
for i in range(10):
    DIGITS[str(i)] = str(i)
DIGIT_CLASS = "".join(sorted(DIGITS))

BAR = "।॥|"          # danda, double danda, and OCR's pipe for both
NUM_ONLY = re.compile(r"^[%s\s]*([%s]{1,3})[%s\s]*$" % (BAR, DIGIT_CLASS, BAR))
NUM_TAIL = re.compile(r"[%s]{1,2}\s*([%s]{1,3})\s*[%s]{1,2}\s*$" % (BAR, DIGIT_CLASS, BAR))

SARGA_NAMES = {
    "प्रथम": 1, "द्वितीय": 2,
    "तृतीय": 3, "चतुर्थ": 4,
    "पञ्चम": 5, "षष्ठ": 6,
    "सप्तम": 7, "ससम": 7,   # OCR drops the प in सप्तम often enough
    "अष्टम": 8,
}
SARGA_RE = re.compile(r"(%s)[^\s]*\s*सर्ग" % "|".join(SARGA_NAMES))
# The sarga actually turns at the "<ordinal>सर्गप्रारम्भः" heading, not at the
# running head -- the running head lags a page or two behind the colophon, and
# trusting it shifted four verses of sarga 4 back into sarga 3.
PRARAMBHA_RE = re.compile(r"(%s)[^\s]*\s*सर्ग\s*प्रारम्भ" % "|".join(SARGA_NAMES))
# Both halves of the closing colophon: the mula's ("इति श्रीमत् ... सर्गः") and
# Raghavendracharya's own ("मणिमञ्जरीप्रकाशे जनिते ... सर्गः"). They stand after
# the last Kannada gloss, so without recognising them each sarga gained a
# phantom final verse made of nothing but its colophon.
COLOPHON_RE = re.compile(r"मणिमञ्ज[रय][\u0900-\u097F]*प्रकाश|इति\s*श्रीम"
                         r"|सर्ग[\u0900-\u097F]*समाप्त|वर्यानुग्रह")
# Raghavendracharya's own signature closes the sarga for good. What follows it
# -- the invocation over the next sarga's first page -- already belongs to the
# next sarga, even though the "प्रारम्भः" heading is still a block or two away.
TIKA_COLOPHON_RE = re.compile(r"मणिमञ्ज[रय][\u0900-\u097F]*प्रकाश|सर्ग[\u0900-\u097F]*समाप्त")
RUNNING_TITLE = "मणिमञ्जरी"   # मणिमञ्जरी

FURNITURE_LAYOUTS = {"page-number"}
EDGE_LAYOUTS = {"header", "footer", "folio"}

# A mula verse is two padas of an anushtubh, not a paragraph of prose. The
# longest genuine two-line verse in this text is comfortably under this;
# the shortest tika paragraph is comfortably over it.
MULA_MAX_CHARS = 300
MULA_MAX_LINES = 6

# Below this a script run is a quotation inside another script's block,
# not a block of its own.
MIN_SCRIPT_RUN_CHARS = 25

# Raghavendracharya opens every gloss the way a commentator does: the word he
# is about to explain, then "इति", then a danda -- "महदिति ॥", "अथेति ॥",
# "इतीति ॥". A block that opens that way is commentary whatever its length,
# and saying so keeps the closing gloss of a sarga from being read as a verse.
# "ीति" as well as "इति": इति + इति sandhis to इतीति, which is how the gloss on
# a verse ending in इति opens.
TIKA_OPENER = re.compile(r"^.{0,42}?(इ|ी)ति\s*[।॥|]")

LAYERS = {
    "mula": "manimanjari/mula",
    "tika_sanskrit": "manimanjari/tika_raghavendra_sanskrit",
    "tika_kannada": "manimanjari/tika_raghavendra_kannada",
}


ANY_NUM = re.compile(r"[%s]{1,2}\s*([%s]{1,3})\s*[%s]{1,2}" % (BAR, DIGIT_CLASS, BAR))


def vision_numerals(path: str) -> dict:
    """Every danda-wrapped numeral the second engine read, by page.

    Google Vision loses this edition's reading order -- it drops a line of the
    Kannada gloss into the middle of a verse -- so it is no use as the layout
    backbone. It is a good second vote on the numerals, which is precisely
    where the Sarvam pass is weakest: where one engine reads २३ as ११, the
    other usually does not make the same mistake.
    """
    with open(path, encoding="utf-8") as handle:
        doc = json.load(handle)
    seen: dict = {}
    for page in doc.get("pages", []):
        nums = {to_int(m.group(1)) for m in ANY_NUM.finditer(page.get("text") or "")}
        seen[page.get("page")] = {n for n in nums if n}
    return seen


def to_int(s: str) -> int | None:
    try:
        return int("".join(DIGITS[c] for c in s))
    except (KeyError, ValueError):
        return None


def strip_tags(html: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", html)
    text = re.sub(r"<[^>]+>", "", text)
    text = (text.replace("&amp;", "&").replace("&lt;", "<")
                .replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'"))
    return "\n".join(line.strip() for line in text.split("\n")).strip()


def _danda_wrapped(text: str) -> bool:
    """True for ॥ २० ॥ (a verse number), false for a bare 20 (a page number)."""
    return any(c in text for c in BAR)


def script_of(text: str) -> str:
    kan = sum(1 for c in text if 0x0C80 <= ord(c) <= 0x0CFF)
    dev = sum(1 for c in text if 0x0900 <= ord(c) <= 0x097F)
    if kan > dev:
        return "kannada"
    return "devanagari" if dev else "other"


def split_by_script(text: str) -> list[str]:
    """Split a block the OCR merged across a script change.

    The scan sometimes runs the last line of a Devanagari verse and the first
    line of its Kannada gloss into one paragraph. Majority script would then
    file the whole thing under whichever won, losing a verse. Lines are
    grouped into same-script runs instead; a run too small to stand on its own
    (a Devanagari pratika quoted inside the Kannada gloss, say) stays attached
    to the run before it.
    """
    lines = [l for l in text.split("\n") if l.strip()]
    while lines and NUM_ONLY.match(lines[0]) and not _danda_wrapped(lines[0]) and len(lines[0]) <= 4:
        lines.pop(0)          # a page number the scan ran into the block
    if not lines:
        return []
    runs: list[list[str]] = []
    scripts: list[str] = []
    for line in lines:
        this = script_of(line)
        if runs and (this == scripts[-1] or this == "other" or scripts[-1] == "other"):
            runs[-1].append(line)
            if scripts[-1] == "other":
                scripts[-1] = this
            continue
        runs.append([line])
        scripts.append(this)
    merged: list[list[str]] = []
    merged_scripts: list[str] = []
    for run, script in zip(runs, scripts):
        body = "\n".join(run)
        if merged and len(body) < MIN_SCRIPT_RUN_CHARS:
            merged[-1].extend(run)
            continue
        merged.append(run)
        merged_scripts.append(script)
    return ["\n".join(run) for run in merged]


def duplicate_pages(staged: dict, window: int = 6, threshold: float = 0.85) -> dict:
    """Leaves this scan photographed twice.

    Printed folio ६४ is PDF page 183 and again PDF page 185; the same happens
    at ६५/६६ and twice more later. Left in, each repeated spread invents about
    four verses and shifts every verse after it -- which is exactly what both
    engines were disagreeing about. The later copy is dropped and named in the
    report, so a reviewer can compare the two readings rather than take this
    on trust.
    """
    texts = {}
    for page in staged.get("pages", []):
        body = page.get("html") or page.get("md") or page.get("text") or ""
        body = re.sub(r"[^\u0900-\u097F\u0C80-\u0CFF]+", " ", strip_tags(body))
        texts[page.get("page")] = " ".join(body.split())
    numbers = sorted(n for n in texts if n is not None)
    dropped = {}
    for i, first in enumerate(numbers):
        if first in dropped or len(texts[first]) < 200:
            continue
        for later in numbers[i + 1:i + window]:
            if later in dropped or len(texts[later]) < 200:
                continue
            # A page that merely CONTAINS another page's text is not a repeat
            # of it; the same leaf photographed twice is the same length.
            shorter, longer = sorted((len(texts[first]), len(texts[later])))
            if shorter < 0.75 * longer:
                continue
            ratio = difflib.SequenceMatcher(None, texts[first][:1500],
                                            texts[later][:1500]).ratio()
            if ratio > threshold:
                dropped[later] = (first, round(ratio, 3))
    return dropped


def split_at_colophon(text: str) -> list[str]:
    """Cut a verse loose from the colophon printed under it.

    The last verse of sarga 6 came back in one paragraph with the colophon
    that follows it. Recognising the block as a colophon then filed the verse
    under the sarga's closing matter and lost it; recognising it as a verse
    would have swallowed the colophon. It is both, so it is split.
    """
    lines = text.split("\n")
    for i in range(1, len(lines)):
        if COLOPHON_RE.search(lines[i]) and len("\n".join(lines[:i]).strip()) >= 30:
            return ["\n".join(lines[:i]).strip(), "\n".join(lines[i:]).strip()]
    return [text]


def read_blocks(staged: dict, skip: dict | None = None) -> list[dict]:
    """Flatten pages[] into an ordered block list, keeping page and layout."""
    blocks = []
    skip = skip or {}
    for page in staged.get("pages", []):
        if not page.get("ok", True) or page.get("page") in skip:
            continue
        num = page.get("page")
        html = page.get("html") or ""
        if html:
            for match in BLOCK_RE.finditer(html):
                layout = LAYOUT_RE.search(match.group(2))
                conf = CONF_RE.search(match.group(2))
                text = strip_tags(match.group(3))
                if not text:
                    continue
                pieces = [part for piece in split_by_script(text)
                          for part in split_at_colophon(piece)]
                for piece in pieces:
                    blocks.append({
                        "page": num,
                        "layout": layout.group(1) if layout else "",
                        "confidence": float(conf.group(1)) if conf else None,
                        "text": piece,
                    })
            continue
        body = page.get("md") or page.get("text") or ""
        for chunk in re.split(r"\n\s*\n", body):
            chunk = chunk.strip()
            if chunk:
                blocks.append({"page": num, "layout": "", "confidence": None, "text": chunk})
    return blocks


def is_furniture(block: dict) -> bool:
    """Page number, running head, or a bare verse-number standing in the
    margin. A footer carrying a real line of verse is NOT furniture -- the
    OCR mislabels those, and dropping them would lose text."""
    text = block["text"]
    if block["layout"] in FURNITURE_LAYOUTS:
        return True
    # A bare numeral is the printed page number, whatever the OCR labelled the
    # block -- it comes back as "dateline", "folio" and "headline" too.
    if NUM_ONLY.match(text) and not _danda_wrapped(text) and len(text) <= 4:
        return True
    # The running head prints on every page and the OCR labels it "header",
    # "paragraph" and "headline" by turns. Left in, it reads as a Devanagari
    # block after the Kannada gloss -- which is exactly the shape of a new
    # verse, so it would insert one and shift every verse after it.
    if RUNNING_TITLE in text and len(text) <= len(RUNNING_TITLE) + 4:
        return True
    if SARGA_RE.search(text) and len(text) <= 24:
        return True
    if PRARAMBHA_RE.search(text) and len(text) <= 60:
        return True
    if block["layout"] in EDGE_LAYOUTS:
        if NUM_ONLY.match(text):
            return True
        if len(text) <= 8:
            return True
    return False


def classify(blocks: list[dict]) -> None:
    """Tag every block with layer, sarga and verse ordinal, in place."""
    # Pass 1: sarga from the "<ordinal>सर्गप्रारम्भः" heading, carried forward.
    sarga = 1
    turn_after = False
    for block in blocks:
        match = PRARAMBHA_RE.search(block["text"])
        if match and len(block["text"]) <= 60:
            sarga, turn_after = SARGA_NAMES[match.group(1)], False
        elif turn_after:
            sarga, turn_after = sarga + 1, False
        block["sarga"] = sarga
        block["colophon"] = bool(COLOPHON_RE.search(block["text"]))
        if TIKA_COLOPHON_RE.search(block["text"]):
            turn_after = True

    content = [b for b in blocks if not is_furniture(b)]

    # Pass 2: number tokens. A bare numeral in the margin is the printed page
    # number; a numeral wrapped in dandas is the verse number. That is the
    # discriminator the edition itself uses, and it survives the OCR calling
    # both of them "page-number".
    for block in content:
        text = block["text"]
        block["script"] = script_of(text)
        marker = NUM_ONLY.match(text)
        block["marker"] = bool(marker) and _danda_wrapped(text)
        tail = marker if block["marker"] else NUM_TAIL.search(text)
        block["ocr_number"] = to_int(tail.group(1)) if tail else None

    # Pass 3: layer and verse group. The Kannada gloss closes a verse, so the
    # first Devanagari block after Kannada opens the next -- that boundary is
    # structural, and no numeral is trusted to find it.
    verse = 0
    seen_kannada = True          # so the very first Devanagari block opens verse 1
    current_sarga = None
    for i, block in enumerate(content):
        if block["sarga"] != current_sarga:
            current_sarga, verse, seen_kannada = block["sarga"], 0, True
        if block["marker"]:
            block["layer"] = None          # the number itself is not content
            block["verse"] = verse or None
            continue
        if block["script"] == "kannada":
            block["layer"] = "tika_kannada"
            block["verse"] = verse or None
            seen_kannada = True
            continue
        if block["colophon"]:
            # Closes the sarga; belongs to the verse just finished.
            block["layer"] = "tika_sanskrit" if verse else None
            block["verse"] = verse or None
            continue
        if seen_kannada:
            verse += 1
            seen_kannada = False
        following = content[i + 1] if i + 1 < len(content) else None
        verse_shaped = (len(block["text"]) <= MULA_MAX_CHARS
                        and block["text"].count("\n") < MULA_MAX_LINES)
        closed_by_marker = bool(following and following["marker"])
        before_kannada = bool(following and not following["marker"]
                              and following["script"] == "kannada")
        # The last verse of a sarga is closed by the colophon, not by a number
        # or a Kannada gloss -- without this it reads as prose, and its whole
        # verse folds into the one before it.
        before_colophon = bool(following and following["colophon"])
        opens_a_gloss = bool(TIKA_OPENER.match(block["text"]))
        block["layer"] = ("mula" if verse_shaped and not opens_a_gloss
                          and (closed_by_marker or before_kannada or before_colophon)
                          else "tika_sanskrit")
        block["verse"] = verse

    _absorb_groups_without_mula(content)

    for block in blocks:
        block.setdefault("layer", None)
        block.setdefault("verse", None)
        block.setdefault("ocr_number", None)


def _absorb_groups_without_mula(content: list[dict]) -> None:
    """A verse has a verse in it.

    The colophon, the signature and the invocation over the next sarga all
    sit after a Kannada gloss, so the cycle reads them as the start of
    another verse -- which is why six sargas each ended with a phantom final
    verse made of nothing but closing matter. A group carrying no mula block
    is not a verse: it joins the group before it, or the one after it when it
    opens a sarga. Verses are then renumbered so the count is the real one.
    """
    groups: dict[tuple, list] = {}
    for block in content:
        if block.get("verse"):
            groups.setdefault((block["sarga"], block["verse"]), []).append(block)
    sargas = sorted({key[0] for key in groups})
    for sarga in sargas:
        keys = sorted(key for key in groups if key[0] == sarga)
        keep = [key for key in keys if any(b["layer"] == "mula" for b in groups[key])]
        if not keep:
            # A whole "sarga" with no verse in it is the matter after the last
            # colophon -- the editor's own signature. It belongs to the sarga
            # before it, not to one of its own.
            previous = [n for n in sargas if n < sarga]
            if not previous:
                continue
            for key in keys:
                for block in groups[key]:
                    block["sarga"] = previous[-1]
                    block["verse"] = max(k[1] for k in groups if k[0] == previous[-1])
            continue
        for key in keys:
            if key in keep:
                continue
            target = max([k for k in keep if k < key], default=min(keep))
            for block in groups[key]:
                block["verse"] = target[1]
        for new_number, key in enumerate(keep, 1):
            for block in content:
                if block["sarga"] == sarga and block["verse"] == key[1]:
                    block["_renumbered"] = new_number
    for block in content:
        if "_renumbered" in block:
            block["verse"] = block.pop("_renumbered")


def assemble(blocks: list[dict], layer: str) -> list[dict]:
    """One unit per (sarga, verse), joining blocks the page break split."""
    units: list[dict] = []
    index: dict[tuple, dict] = {}
    for block in blocks:
        if block.get("layer") != layer:
            continue
        key = (block["sarga"], block["verse"])
        unit = index.get(key)
        if unit is None:
            unit = {
                "id": "s%s_v%s" % (block["sarga"], block["verse"]),
                "type": layer,
                "sarga": block["sarga"],
                "verse": block["verse"],
                "page": block["page"],
                "pages": [],
                "text": "",
                "confidence": [],
            }
            index[key] = unit
            units.append(unit)
        if block["page"] not in unit["pages"]:
            unit["pages"].append(block["page"])
        unit["text"] = (unit["text"] + "\n" + block["text"]).strip()
        if block["confidence"] is not None:
            unit["confidence"].append(block["confidence"])
    for unit in units:
        confs = unit.pop("confidence")
        unit["ocr_confidence"] = round(sum(confs) / len(confs), 3) if confs else None
    return units


def write_layer(out_dir: str, name: str, units: list[dict], staged: dict, source: str) -> str:
    path = os.path.join(out_dir, name + ".json")
    doc = {
        "_readme": ("Staged OCR, split out of %s by tools/split_manimanjari_layers.py. "
                    "NOT merged into the corpus -- review in admin/ocr-review.html first."
                    % os.path.basename(source)),
        "work": "manimanjari",
        "layer": LAYERS[name],
        "source": staged.get("source", ""),
        "engine": staged.get("engine", ""),
        "language": "kn" if name == "tika_kannada" else "sa",
        "split_from": source,
        "blocks": units,
    }
    os.makedirs(out_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(doc, handle, ensure_ascii=False, indent=1)
        handle.write("\n")
    return path


def report(blocks: list[dict], second: dict | None = None) -> str:
    content = [b for b in blocks if b.get("layer")]
    lines = ["blocks: %d total, %d content" % (len(blocks), len(content))]
    for name in LAYERS:
        got = [b for b in content if b["layer"] == name]
        lines.append("  %-14s %4d blocks, %4d chars median"
                     % (name, len(got),
                        sorted(len(b["text"]) for b in got)[len(got) // 2] if got else 0))

    verses: dict[int, set] = {}
    for block in content:
        if block["verse"]:
            verses.setdefault(block["sarga"], set()).add(block["verse"])
    lines.append("verses by sarga (ordinal, not the OCR's numeral):")
    total = 0
    for sarga in sorted(verses):
        total += len(verses[sarga])
        got = {(block["sarga"], block["verse"]) for block in content
               if block["layer"] == "tika_kannada"}
        no_kannada = sorted(v for v in verses[sarga] if (sarga, v) not in got)
        lines.append("  sarga %d: %d verses%s"
                     % (sarga, len(verses[sarga]),
                        (", no Kannada gloss for %s" % no_kannada[:10]) if no_kannada else ""))
    lines.append("  %d verses in all" % total)

    # The cross-check. Each verse is numbered up to three times on the page
    # (closing the tika, standing alone, closing the Kannada), so one bad
    # glyph is not a problem -- a verse where NOT ONE of them matches the
    # position is. Those are what a reviewer should open. Reported, never
    # silently corrected.
    numerals: dict[tuple, set] = {}
    where: dict[tuple, int] = {}
    pages_of: dict[tuple, set] = {}
    for block in content:
        if not block["verse"]:
            continue
        key = (block["sarga"], block["verse"])
        if block["ocr_number"]:
            numerals.setdefault(key, set()).add(block["ocr_number"])
        where.setdefault(key, block["page"])
        pages_of.setdefault(key, set()).add(block["page"])
    if second:
        for key, pages in pages_of.items():
            for page in pages:
                numerals.setdefault(key, set()).update(second.get(page, set()))
    highest: dict[int, int] = {}
    for key, values in numerals.items():
        plausible = [v for v in values if v <= key[1] + 4]
        if plausible:
            highest[key[0]] = max(highest.get(key[0], 0), max(plausible))
    short = [(sarga, len(verses[sarga]), highest[sarga]) for sarga in sorted(verses)
             if highest.get(sarga, 0) > len(verses[sarga])]
    if short:
        lines.append("  a numeral higher than the verse count was read in %d sarga(s) -- "
                     "the last verse may have swallowed the one after it: %s"
                     % (len(short), ", ".join("sarga %d has %d but the page reads %d"
                                              % row for row in short)))

    unconfirmed = sorted(k for k, v in numerals.items() if k[1] not in v)
    silent = sorted(k for k in where if k not in numerals)
    lines.append("numbering: %d of %d verses confirmed by a numeral on the page%s"
                 % (len(numerals) - len(unconfirmed), len(where),
                    " (both engines)" if second else ""))
    if unconfirmed:
        lines.append("  no numeral matches the position for %d: %s"
                     % (len(unconfirmed),
                        ", ".join("s%dv%d (p%d, scan reads %s)"
                                  % (k[0], k[1], where[k], sorted(numerals[k]))
                                  for k in unconfirmed[:12])))
    if silent:
        lines.append("  no numeral read at all for %d: %s"
                     % (len(silent), ", ".join("s%dv%d (p%d)" % (k[0], k[1], where[k])
                                               for k in silent[:12])))
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 2)[1])
    ap.add_argument("--staged", required=True, help="staged OCR JSON to split")
    ap.add_argument("--out-dir", default="", help="default: <staged dir>/layers")
    ap.add_argument("--keep-duplicate-pages", action="store_true",
                    help="do not drop repeated leaves (they invent verses)")
    ap.add_argument("--second-engine", default="",
                    help="a second engine's staged OCR, used only to cross-check the numerals")
    ap.add_argument("--report", action="store_true", help="print the split summary only")
    args = ap.parse_args(argv)

    with open(args.staged, encoding="utf-8") as handle:
        staged = json.load(handle)

    duplicates = {} if args.keep_duplicate_pages else duplicate_pages(staged)
    blocks = read_blocks(staged, duplicates)
    if duplicates:
        print("duplicate leaves dropped (the scan photographed them twice): "
              + ", ".join("p%d repeats p%d at %.0f%%" % (later, first, ratio * 100)
                          for later, (first, ratio) in sorted(duplicates.items())))
    if not blocks:
        print("no readable blocks in %s" % args.staged, file=sys.stderr)
        return 1
    classify(blocks)
    second = vision_numerals(args.second_engine) if args.second_engine else None
    print(report(blocks, second))
    if args.report:
        return 0

    out_dir = args.out_dir or os.path.join(os.path.dirname(args.staged), "layers")
    for name in LAYERS:
        units = assemble(blocks, name)
        path = write_layer(out_dir, name, units, staged, args.staged)
        print("wrote %s (%d units)" % (path, len(units)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
