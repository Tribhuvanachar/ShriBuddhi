"""Tier B parser: GRETIL (plain e-text and corpusTEI).

The one thing this parser gets right that a naive one does not:

GRETIL marker conventions are NOT uniform, and they are not even uniform per
collection.  Four shapes occur in the kavya material:

    DOT    Ragh_1.1          chapter . verse
    COLON  BhSv_2:1          ACT : SENTENCE      (Bhasa's prose dramas)
    COMMA  ChUp_1,1.1        book , chapter . verse
    PAREN  ... (1.1)         trailing parenthesised reference
    BARE   ... || 1.1 ||     trailing danda-wrapped reference

Trying them in a FIXED ORDER is the bug that produced two well-known
failures:

  * Bhasa: "BhSv_2:1" matched the numeric rule as "verse 2", so acts 2 and 3
    folded into act 1 and Svapnavasavadatta came out as one act.
  * Kavyaprakasa-Balabodhini: the dominant convention there is not the first
    one tried, so the file yielded 9 entries instead of 738 across 10 ullasas.

So: count every convention over the whole file first, and parse with whichever
one DOMINATES.  A file is allowed exactly one convention.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from ..common import deva_to_ascii_digits, norm_ws
from ..schema import make_grantha, make_item, make_layer, make_shloka, recount

# Marker regexes.  Each captures the reference body in group('ref').
CONVENTIONS = {
    "COLON": re.compile(r"(?<![\w.])[A-Za-zĀāĪīŪūṚṛṜṝḶḷṆṇṬṭḌḍŚśṢṣṄṅÑñṂṃḤḥ]{2,12}_(?P<ref>\d+:\d+(?:\.\d+)?)"),
    "COMMA": re.compile(r"(?<![\w.])[A-Za-zĀāĪīŪūṚṛṜṝḶḷṆṇṬṭḌḍŚśṢṣṄṅÑñṂṃḤḥ]{2,12}_(?P<ref>\d+,\d+(?:\.\d+)?)"),
    "DOT":   re.compile(r"(?<![\w.])[A-Za-zĀāĪīŪūṚṛṜṝḶḷṆṇṬṭḌḍŚśṢṣṄṅÑñṂṃḤḥ]{2,12}_(?P<ref>\d+(?:\.\d+){1,2})"),
    "PAREN": re.compile(r"\((?P<ref>\d+(?:[.,]\d+){1,2})\)\s*$", re.M),
    "BARE":  re.compile(r"[।॥|]{1,2}\s*(?P<ref>[\d०-९]+(?:[.,][\d०-९]+){1,2})\s*[।॥|]{1,2}"),
}

# COLON is act:sentence -> the unit is prose, not a verse.
PROSE_CONVENTIONS = {"COLON"}


def detect_convention(text):
    """Return (name, hits) for the convention that dominates `text`."""
    counts = {name: len(rx.findall(text)) for name, rx in CONVENTIONS.items()}
    # A DOT match is also produced by COLON/COMMA lines' tail; subtract them so
    # a prose drama is not misread as a verse text.
    counts["DOT"] = max(0, counts["DOT"] - counts["COLON"] - counts["COMMA"])
    name = max(counts, key=lambda k: (counts[k], k == "DOT"))
    return (name, counts[name]) if counts[name] else (None, 0)


def _ref_parts(ref):
    ref = deva_to_ascii_digits(ref)
    return [p for p in re.split(r"[.,:]", ref) if p != ""]


def marker_trails(text, marks):
    """Does the reference sit AFTER the verse it names, or before it?

    Both happen. GRETIL's own e-texts and TEI files close a verse with its
    reference — "... || BharSt_1.1 ||" — while a marker-led file opens with
    it: "KAvyapraBAl_1.1 atra bAlabodhinI ...". Assuming either one is what
    silently shifts an entire text by one verse: every reading lands under
    its neighbour's number, nothing looks broken, and only someone who knows
    the text notices. So it is decided from the file: substantial text before
    the first marker means the marker closes its unit rather than opening it.
    """
    if not marks:
        return False
    head = re.sub(r"[\s|/।॥–—-]", "", text[:marks[0][0]])
    return len(head) >= 20


def split_units(text, convention=None, trailing=None):
    """Yield (ref_parts, is_prose, body) in document order."""
    if convention is None:
        convention, hits = detect_convention(text)
        if not convention:
            return
    rx = CONVENTIONS[convention]
    prose = convention in PROSE_CONVENTIONS

    marks = [(m.start(), m.end(), m.group("ref")) for m in rx.finditer(text)]
    if not marks:
        return

    if trailing is None:
        trailing = (convention in ("PAREN", "BARE")
                    or marker_trails(text, marks))
    prev_end = 0
    for i, (s, e, ref) in enumerate(marks):
        if trailing:
            body = text[prev_end:s]
            prev_end = e
        else:
            nxt = marks[i + 1][0] if i + 1 < len(marks) else len(text)
            body = text[e:nxt]
        body = norm_ws(re.sub(r"\s*//\s*", " ", body))
        body = body.strip(" |/–—-")
        if body:
            yield _ref_parts(ref), prose, body


# --------------------------------------------------------------------------
# corpusTEI
# --------------------------------------------------------------------------

def _localname(tag):
    return tag.rsplit("}", 1)[-1]


def _itertext(el):
    """Text of an element, with verse lines kept apart.

    <lg><l>a</l><l>b</l></lg> must not come out as "ab": TEI writes no
    whitespace between <l> siblings, and the reader renders the mula with
    white-space:pre-wrap, so each pada gets its own line.
    """
    lines = [c for c in el if _localname(c.tag) == "l"]
    if lines:
        out = []
        head = norm_ws(el.text or "")
        if head:
            out.append(head)
        for c in lines:
            t = norm_ws("".join(c.itertext()))
            if t:
                out.append(t)
            tail = norm_ws(c.tail or "")
            if tail:
                out.append(tail)
        return "\n".join(out)
    return norm_ws("".join(el.itertext()))


def tei_plaintext(xml_text):
    """The TEI body as flat text, one verse line per line.

    For the files whose <lg>/<l> carry no xml:id -- most of the kavya
    material, as it turns out -- the reference is not in the markup at all
    but inside the verse's last line. Flattening the body puts those files
    back on the same footing as GRETIL's plain e-texts, which is what the
    convention detection above was written for.
    """
    root = ET.fromstring(xml_text)
    bodies = [el for el in root.iter() if _localname(el.tag) == "body"]
    lines = []
    for body in bodies or [root]:
        for el in body.iter():
            if _localname(el.tag) not in ("l", "p", "seg"):
                continue
            if any(_localname(c.tag) in ("l", "p", "seg") for c in el):
                continue        # a container; its children carry the text
            txt = norm_ws("".join(el.itertext()))
            if txt:
                lines.append(txt)
    return "\n".join(lines)


def split_units_tei(xml_text):
    """Yield (ref_parts, is_prose, body) from a GRETIL corpusTEI file.

    Units are <lg>/<l>/<p>/<seg> carrying xml:id or n.  The id IS the
    reference, exactly as in the plain e-texts, so the same convention
    detection applies.
    """
    root = ET.fromstring(xml_text)
    ids = []
    for el in root.iter():
        name = _localname(el.tag)
        # NB: <div> is a container, not a unit. Including it here made
        # every sarga emit its whole text as a phantom unit "1".
        if name not in ("lg", "p", "seg"):
            continue
        ref = None
        for k, v in el.attrib.items():
            if _localname(k) in ("id", "n") and v:
                ref = v
                break
        if not ref:
            continue
        body = _itertext(el)
        if body:
            ids.append((ref, body, name))
    if not ids:
        return
    joined = " ".join(r for r, _, _ in ids)
    convention, _ = detect_convention(joined) 
    if convention is None:
        convention = "DOT" if any("." in r for r, _, _ in ids) else None
    prose = convention in PROSE_CONVENTIONS
    for ref, body, name in ids:
        raw = ref.split("_", 1)[-1]
        parts = _ref_parts(raw)
        if not parts:
            continue
        yield parts, prose or name == "p", body


# --------------------------------------------------------------------------
# Layer construction
# --------------------------------------------------------------------------

def build_layer(units, work_id, layer_id, kind, commentator="",
                name_sa="", name_en="", language="sa", source=None,
                license_note="", item_depth=None):
    """`units` is the iterable produced by split_units / split_units_tei."""
    g = make_grantha(
        layer_id, work_id, kind,
        name_sa=name_sa, name_en=name_en, commentator=commentator,
        language=language, source=source or {}, license_note=license_note,
    )
    layer = make_layer(g)
    items = {}
    seen = {}
    for parts, is_prose, body in units:
        # GRETIL's TEI gives every PADA its own xml:id -- Ragh_1.1a, .1b, .1c --
        # alongside the verse's. Those reduce to a bare "a"/"b"/"c" here, and
        # they are not units: their text is already inside the verse above them.
        # Left in, Raghuvamsa parses as 8,185 "verses" of which 6,545 are pada
        # fragments, all sharing three ids, and the layer is thrown away whole
        # by the duplicate-id check downstream.
        if not any(ch.isdigit() for ch in "".join(parts)):
            continue
        depth = item_depth if item_depth is not None else (len(parts) - 1 or 1)
        head = parts[:depth] or parts[:1]
        item_id = ".".join(head)
        uid = ".".join(parts)
        it = items.get(item_id)
        if it is None:
            it = make_item(item_id)
            it["id"] = item_id
            items[item_id] = it
            layer["items"].append(it)
        # A reference can legitimately occur twice in one file -- the
        # Natyasastra repeats 7.119 nine times where a verse is interrupted by
        # prose. Suffixing keeps both readings; the alternative, which is what
        # happened before, is that validate_layer sees a duplicate id and drops
        # all 4,303 verses of the text.
        n = seen.get(uid, 0) + 1
        seen[uid] = n
        if n > 1:
            uid = "%s-%d" % (uid, n)
        sh = make_shloka(uid, kind="prose" if is_prose else "verse")
        if kind in ("tika", "tippani"):
            sh["bhashya"] = [{"commentator": commentator, "text": body}]
        elif kind == "mula":
            sh["sanskrit_text"] = body
        else:
            sh["artha"] = body
        it["shlokas"].append(sh)
    recount(layer)
    return layer
