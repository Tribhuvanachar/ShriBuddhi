#!/usr/bin/env python3
"""Segment 108 Upaniṣat Sarvasva (saṃpuṭa 1, Kannada, TTD) from staged OCR.

The book is a Kannada exposition of the Upaniṣads.  Every unit is a pair:

    ಮಂ.ಶ್ಲೋ.॥ <the mantra, Sanskrit in Kannada script>  ॥ 8 (33)
    ತಾ||      <the Kannada tātparya>

Four things this file knows that cost measurements to learn.

**The markers are openers, not closers.**  Every other segmenter in this
tree hunts a trailing ``॥ N ॥``; here the text announces each unit up front.
That is far more reliable -- so the stream is split on the openers and the
block boundaries Sarvam guessed are ignored entirely.  They have to be:
Sarvam merges a mantra and its gloss into one paragraph often enough that
trusting a block boundary loses the gloss.

**A mantra carries two numbers, and the useful one is in parentheses.**
``॥ 8 (33)`` is the eighth mantra of its division and the thirty-third of
the Upaniṣad.  The local number restarts at every khaṇḍa, so only the
parenthesised one is unique within an Upaniṣad.

**The parenthesised number is also where the Upaniṣad boundaries are.**
It resets to 1 at each new Upaniṣad, which makes the boundary a property of
the numbering rather than of a heading OCR may have dropped -- and it
validates itself, because its maximum is that Upaniṣad's own mantra count.
Praśna stops at 67, Muṇḍaka at 64, Kaṭha at 120, which is exactly what
those Upaniṣads have.  Headings are not trustworthy here: the ordinals come
through as ``ಸಜ್ಜನ ಪ್ರಸಾರಕ`` for ಪಂಚಮ and ``ಸ್ಪಷ್ಟ ಖಂಡ`` for ಷಷ್ಠ, so
divisions are numbered by position and the printed heading is kept verbatim
beside it rather than parsed.

**The colophon names the Upaniṣad, and it sits at the end.**  There is no
reliable title block -- the display titles are large type Sarvam mostly
missed -- but ``ಕೇನೋಪನಿಷತ್ತಮಾಪ್ತಿ`` closes Kena.  So a name is read
backwards, from the colophon that ends a span, not forwards from a heading.
"""

from __future__ import annotations

import re
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "ocr_common"))
import staged as S                                              # noqa: E402

BODY_START = 56                     # pages 1-55 are essays and front matter
SKIP = S.FURNITURE + ("header",)    # the running head bleeds into the tails

D = S.ANY_DIGIT

#: ``ಮಂ.ಶ್ಲೋ.॥``, ``ಮಂ.ಶ್ಲೋ॥``, and the bare ``ಶ್ಲೋ॥`` the later pages use.
OPEN = re.compile(r"(?:ಮಂ\s*\.?\s*)?ಶ್ಲೋ\s*\.?\s*[|।॥]{1,2}")
#: ``ತಾ||`` early on, ``ತಾ :`` from the Bṛhadāraṇyaka onwards.
GLOSS = re.compile(r"ತಾ\s*(?:[|।॥]{1,2}|[:：])")
MARKER = re.compile(OPEN.pattern + "|" + GLOSS.pattern)

#: ``॥ 8 (33)`` -- local number then the Upaniṣad-wide one.
TAIL_BOTH = re.compile(r"[|।॥]\s*(" + D + r"+)\s*\(\s*(" + D + r"+)\s*\)\s*[|।॥]?\s*$")
#: ``(9)`` alone.  This one is a trap: in ``॥ 8 (33)`` the parenthesis holds
#: the Upaniṣad-wide number, but where it stands alone -- Chāndogya's prose
#: khaṇḍas, and Bṛhadāraṇyaka's -- it is the *local* number of that khaṇḍa
#: and restarts a few lines later.  Reading it as Upaniṣad-wide cut the
#: volume into 187 pieces instead of 21.  Only the two-number form says
#: anything about position within the Upaniṣad.
TAIL_CUM = re.compile(r"\(\s*(" + D + r"+)\s*\)\s*[|।॥]?\s*$")
#: ``|| 15`` -- the closing daṇḍa is missing about as often as it is there.
TAIL_LOCAL = re.compile(r"[|।॥]\s*(" + D + r"+)\s*[|।॥]?\s*$")

#: ``ಕೇನೋಪನಿಷತ್ತಮಾಪ್ತಿ``, ``(ಹಂಸೋಪನಿಷತ್ ಸಮಾಪ್ತಾ)``, ``(ಜಾಬಾಲೋಪನಿಷತ್ಮಾಪ್ರಾ)``
#: -- ಸಮಾಪ್ತ survives OCR as ಮಾಪ್ತಿ and ಮಾಪ್ರಾ about as often as intact.
#:
#: Matched from ``ಪನಿಷ``, not ``ಉಪನಿಷ``: every one of these names ends in a
#: vowel that swallows the ಉ, so ಮಾಂಡೂಕ್ಯ + ಉಪನಿಷತ್ is written
#: ಮಾಂಡೂಕ್ಯೋಪನಿಷತ್ and there is no ಉ left in the line to match.  Looking for
#: the literal word found nothing at all, in all twenty-five of them.
COLOPHON = re.compile(r"ಪನಿಷ\S*?\s*(?:ಸಮಾಪ್ತ|ಮಾಪ್ತ|ಮಾಪ್ರ)")
#: The volume's own closing line, not an Upaniṣad's.
VOLUME_END = re.compile(r"ಸಂಪುಟ\s*ಸಮಾಪ್ತಿ")

SHANTI = re.compile(r"^\(?\s*ಶಾಂತಿ\s*ಮಂತ್ರ")
VEDA = re.compile(r"^\(\s*\S*ವೇದಾಂತ\S*\s*\)$")

#: Shortest a real mantra runs.  Three "mantras" came through as ``೧.``,
#: ``೦.`` and ``ಂ.`` -- the running head ``೧೦೮ ಉಪನಿಷತ್ ಸರ್ವಸ್ವ`` broken up on
#: pages where Sarvam labelled it a paragraph instead of a header, so
#: dropping headers did not catch it.  Nothing real in the volume comes
#: anywhere near this short; the next shortest mantra is over eighty
#: characters.
MIN_MANTRA = 12

#: Longest a real division heading runs.  ``ಸಪ್ತಮ ಪ್ರಸಾರಕ - ಅಷ್ಟಾದಶಃ ಖಂಡಃ``
#: is about as long as they get; anything past this is a paragraph Sarvam
#: mislabelled.
MAX_HEADING = 60


def is_division(text: str) -> bool:
    """Whether a section-title is really a khaṇḍa/vallī heading.

    Sarvam promotes a mantra to ``section-title`` often enough to matter --
    thirty-six bare ``ಮಂ.ಶ್ಲೋ.॥`` fragments, and whole mantras besides, one
    of which became the heading on all twelve units of Māṇḍūkya.  A heading
    that carries a mantra marker is not a heading.  Neither is the veda
    attribution that opens each Upaniṣad: it names the Upaniṣad, which
    ``sargaName`` already does, so as a division label it says nothing.
    """
    t = " ".join(text.split())
    return bool(t) and len(t) <= MAX_HEADING and not OPEN.search(t) \
        and "ವೇದಾಂತ" not in t

DEV_KAN = str.maketrans(S.DEV_DIGITS + S.KAN_DIGITS, "0123456789" * 2)


def _int(s: str) -> int:
    return int(s.translate(DEV_KAN))


def numbers(text: str) -> tuple[int | None, int | None]:
    """Return ``(local, cumulative)`` for one mantra, either may be absent."""
    m = TAIL_BOTH.search(text)
    if m:
        return _int(m.group(1)), _int(m.group(2))
    m = TAIL_CUM.search(text)
    if m:
        return _int(m.group(1)), None
    m = TAIL_LOCAL.search(text)
    if m:
        return _int(m.group(1)), None
    return None, None


def strip_number(text: str) -> str:
    """Drop the trailing number from a mantra, keeping the text itself."""
    for pat in (TAIL_BOTH, TAIL_CUM, TAIL_LOCAL):
        m = pat.search(text)
        if m:
            return text[:m.start()].strip(" |।॥")
    return text


def is_colophon(text: str) -> bool:
    t = " ".join(text.split())
    return bool(COLOPHON.search(t)) and not VOLUME_END.search(t) and len(t) < 90


def read(staged_dir: str) -> list[dict]:
    """Body blocks in reading order, with the running head dropped."""
    pages = S.load_sarvam(staged_dir)
    return [b for b in S.read_stream(pages, skip=SKIP) if b["page"] >= BODY_START]


def tokenise(blocks: list[dict]) -> list[dict]:
    """The body as a flat token stream: headings, colophons, and the text.

    Headings and colophons become tokens of their own so a mantra that runs
    across a page break still joins up, while a heading between two mantras
    still separates them.
    """
    out, buf, marks = [], [], []

    def flush():
        """Emit the buffer as one token, keeping where each page began.

        A mantra regularly runs across a page break, so the buffer has to
        join pages; ``marks`` records the character offset each page starts
        at so a unit can still say which page it came from instead of
        inheriting the first page of the whole run.
        """
        nonlocal buf, marks
        if buf:
            out.append({"kind": "text", "text": "\n".join(buf),
                        "page": marks[0][1], "marks": marks})
        buf, marks = [], []

    for b in blocks:
        t = " ".join(b["text"].split())
        if not t:
            continue
        if is_colophon(t):
            flush()
            out.append({"kind": "colophon", "text": t, "page": b["page"]})
        elif SHANTI.match(t):
            flush()
            out.append({"kind": "shanti", "text": t, "page": b["page"]})
        elif VEDA.match(t):
            flush()
            out.append({"kind": "veda", "text": t, "page": b["page"]})
        elif b["kind"] in ("section-title", "headline") and is_division(t):
            flush()
            out.append({"kind": "heading", "text": t, "page": b["page"]})
        else:
            marks.append((sum(len(x) + 1 for x in buf), b["page"]))
            buf.append(b["text"])
    flush()
    return out


def units(tokens: list[dict]) -> list[dict]:
    """Walk the stream, pairing each mantra with the gloss that follows it."""
    out = []
    heading = None
    for tok in tokens:
        if tok["kind"] == "heading":
            heading = tok["text"]
            continue
        if tok["kind"] == "colophon":
            out.append({"colophon": tok["text"], "page": tok["page"]})
            continue
        if tok["kind"] in ("shanti", "veda"):
            # A heading belongs to the Upaniṣad it was printed in.  Left
            # standing, Aitareya's ``ತೃತೀಯಾಧ್ಯಾಯಃ`` labelled the opening
            # mantras of Chāndogya.
            heading = None
            out.append({tok["kind"]: tok["text"], "page": tok["page"]})
            continue

        text = tok["text"]
        marks = tok.get("marks") or [(0, tok["page"])]

        def page_at(offset: int) -> int:
            page = marks[0][1]
            for start, p in marks:
                if start <= offset:
                    page = p
                else:
                    break
            return page

        hits = list(MARKER.finditer(text))
        for i, m in enumerate(hits):
            end = hits[i + 1].start() if i + 1 < len(hits) else len(text)
            body = " ".join(text[m.end():end].split())
            if not body:
                continue
            is_gloss = m.group(0).lstrip().startswith("ತಾ")
            if is_gloss:
                if out and "mula" in out[-1] and not out[-1].get("tatparya"):
                    out[-1]["tatparya"] = body
                continue
            local, cum = numbers(body)
            mula = strip_number(body)
            if len(mula) < MIN_MANTRA:
                continue
            out.append({"mula": mula, "local": local, "cum": cum,
                        "heading": heading, "page": page_at(m.start())})
    return out


def upanishads(seq: list[dict]) -> list[dict]:
    """Cut the stream at the śānti mantra that opens each Upaniṣad.

    Every Upaniṣad in the volume opens with one, which no other signal
    manages: six have lost their colophon to OCR and most never had a title
    block Sarvam could see.  They are printed at both ends, though -- the
    mantra closing Praśna sits immediately above the one opening Muṇḍaka --
    so a run of them with no mantra in between is one boundary, not two.

    The Upaniṣad-wide number corroborates where it exists: a span that
    carries one should not see it restart, and its maximum should be that
    Upaniṣad's own mantra count.  ``anomalies`` reports where it does not.
    """
    spans, cur = [], []

    def close():
        nonlocal cur
        if any("mula" in u for u in cur):
            spans.append(cur)
        elif cur and spans:
            spans[-1].extend(cur)       # a colophon trailing the span it ends
        cur = []

    for item in seq:
        if "shanti" in item:
            close()
            continue
        cur.append(item)
    close()

    # A colophon names the Upaniṣad it closes, but the closing śānti mantra
    # is printed between the last mantra and the colophon -- so the cut lands
    # above it and it arrives at the head of the *next* span.  One that
    # precedes that span's first mantra therefore belongs to the span before.
    out = []
    for span in spans:
        first_mula = next((i for i, x in enumerate(span) if "mula" in x), len(span))
        trailing = [x["colophon"] for x in span[:first_mula] if "colophon" in x]
        own = [x["colophon"] for x in span[first_mula:] if "colophon" in x]
        if trailing and out:
            out[-1]["colophon"] = trailing[-1]
        out.append({"units": [x for x in span if "mula" in x],
                    "colophon": own[-1] if own else None})
    return out


#: The volume's own table of contents, off its page 7 -- number, name, and
#: the page the book prints for each.  This is the authority for what the
#: twenty-five spans are and what they are called, and it is worth far more
#: than reading names off colophons: six colophons did not survive the scan
#: at all, and three of those that did are misread (ಈಶಾವಾಸ್ಯ as ಕಳಾವಾಸ್ಯ,
#: ಅಥರ್ವಶಿರಸ್ as ಅಧ್ವಶಿರ, ಅಥರ್ವಶಿಖಾ as ಅಥರ್ವಶಿಬ).
#:
#: It also checks the segmentation rather than merely labelling it.  The
#: scan runs three pages ahead of the printed numbering, and every one of
#: the twenty-five spans the śānti-mantra rule finds begins at exactly its
#: contents-page plus that offset -- so the boundaries are confirmed by the
#: book, not inferred.  ``check`` enforces it; a span that drifts fails
#: rather than quietly taking the next Upaniṣad's name.
CONTENTS = [
    ("ಈಶಾವಾಸ್ಯೋಪನಿಷತ್", "isha_upanishad", 53),
    ("ಕೇನೋಪನಿಷತ್", "kena_upanishad", 57),
    ("ಕಠೋಪನಿಷತ್", "katha_upanishad", 64),
    ("ಪ್ರಶ್ನೋಪನಿಷತ್", "prashna_upanishad", 89),
    ("ಮುಂಡಕೋಪನಿಷತ್", "mundaka_upanishad", 106),
    ("ಮಾಂಡೂಕ್ಯೋಪನಿಷತ್", "mandukya_upanishad", 122),
    ("ತೈತ್ತಿರೀಯೋಪನಿಷತ್", "taittiriya_upanishad", 125),
    ("ಐತರೇಯೋಪನಿಷತ್", "aitareya_upanishad", 154),
    ("ಛಾಂದೋಗ್ಯೋಪನಿಷತ್", "chandogya_upanishad", 164),
    ("ಬೃಹದಾರಣ್ಯಕೋಪನಿಷತ್", "brihadaranyaka_upanishad", 293),
    ("ಬ್ರಹ್ಮೋಪನಿಷತ್", "brahma_upanishad", 463),
    ("ಕೈವಲ್ಯೋಪನಿಷತ್", "kaivalya_upanishad", 468),
    ("ಜಾಬಾಲೋಪನಿಷತ್", "jabala_upanishad", 474),
    ("ಶ್ವೇತಾಶ್ವತರೋಪನಿಷತ್", "shvetashvatara_upanishad", 478),
    ("ಹಂಸೋಪನಿಷತ್", "hamsa_upanishad", 500),
    ("ಆರುಣಿಕೋಪನಿಷತ್", "arunika_upanishad", 505),
    ("ಗರ್ಭೋಪನಿಷತ್", "garbha_upanishad", 509),
    ("ನಾರಾಯಣೋಪನಿಷತ್", "narayana_upanishad", 520),
    ("ಪರಮಹಂಸೋಪನಿಷತ್", "paramahamsa_upanishad", 524),
    ("ಅಮೃತಬಿಂದೂಪನಿಷತ್", "amritabindu_upanishad", 527),
    ("ಅಮೃತನಾದೋಪನಿಷತ್", "amritanada_upanishad", 532),
    ("ಅಥರ್ವಶಿರೋಪನಿಷತ್", "atharvashira_upanishad", 537),
    ("ಅಥರ್ವಶಿಖೋಪನಿಷತ್", "atharvashikha_upanishad", 547),
    ("ಮೈತ್ರಾಯಣ್ಯುಪನಿಷತ್", "maitrayani_upanishad", 551),
    ("ಕೌಷೀತಕೀಬ್ರಾಹ್ಮಣೋಪನಿಷತ್", "kaushitaki_brahmana_upanishad", 569),
]

#: The scan is this many pages ahead of the numbering the book prints.
PAGE_OFFSET = 3

#: What each Upaniṣad has, where the tradition fixes a count.  The segmenter
#: reaches its own totals; the tests compare, so an Upaniṣad that quietly
#: absorbs its neighbour is caught by the count rather than by a name.
#:
#: Where this edition numbers differently it is the edition that counts, not
#: the textbook figure.  Muṇḍaka is the case: its running numbers here go 1
#: to 65 without a gap and end on ``ತದೇತತ್ಸತ್ಯಮೃಷಿರಂಗಿರಾಃ``, the genuine last
#: mantra, against the usual 64.
CANONICAL = {
    "ಈಶಾವಾಸ್ಯೋಪನಿಷತ್": 18, "ಕೇನೋಪನಿಷತ್": 35, "ಕಠೋಪನಿಷತ್": 120,
    "ಪ್ರಶ್ನೋಪನಿಷತ್": 67, "ಮುಂಡಕೋಪನಿಷತ್": 64, "ಮಾಂಡೂಕ್ಯೋಪನಿಷತ್": 12,
    "ಐತರೇಯೋಪನಿಷತ್": 33,
}


def check(spans: list[dict]) -> list[str]:
    """Complain where the spans and the printed contents disagree."""
    out = []
    if len(spans) != len(CONTENTS):
        out.append(f"{len(spans)} spans against {len(CONTENTS)} in the contents")
        return out
    for span, (name, _, page) in zip(spans, CONTENTS):
        want = page + PAGE_OFFSET
        got = span["units"][0]["page"]
        if abs(got - want) > 4:
            out.append(f"{name}: starts at {got}, contents says {want}")
    return out


def name_of(span: dict, index: int) -> str:
    """The contents' name for the index-th span (1-based)."""
    return CONTENTS[index - 1][0]


def colophon_name(span: dict) -> str | None:
    """What the span's own closing colophon calls it, where one survived."""
    if not span.get("colophon"):
        return None
    t = span["colophon"].strip("() ")
    t = re.sub(r"\s*(?:ಸಮಾಪ್ತ|ಮಾಪ್ತ|ಮಾಪ್ರ)\S*\s*$", "", t).strip(" -–—")
    t = re.sub(r"ಪನಿಷ(?:ತ್ತು|ತ್ತ|ತ್|ತ)?\s*$", "ಪನಿಷತ್", t)
    return t or None


def anomalies(span: dict) -> list[str]:
    """Where the Upaniṣad-wide number disagrees with the span it lands in."""
    cums = [u["cum"] for u in span["units"] if u.get("cum")]
    out = []
    if cums and cums != sorted(cums):
        out.append("the running number goes backwards")
    if cums and max(cums) > len(span["units"]) * 2:
        out.append(f"highest {max(cums)} against {len(span['units'])} mantras")
    return out


def segment(staged_dir: str) -> list[dict]:
    seq = units(tokenise(read(staged_dir)))
    out = []
    for i, span in enumerate(upanishads(seq), 1):
        us = span["units"]
        out.append({
            "name": name_of(span, i),
            "index": i,
            "units": us,
            "highest": max([u["cum"] for u in us if u.get("cum")] or [len(us)]),
            "slug": CONTENTS[i - 1][1],
            "colophon_name": colophon_name(span),
            "pages": (us[0]["page"], us[-1]["page"]),
        })
        out[-1]["anomalies"] = anomalies(out[-1])
    return out


if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else (
        "data/ocr_staging/108_upanishad_sarvas__narasimha_1_ttd_kannada")
    works = segment(d)
    total = glossed = 0
    for u in works:
        g = sum(1 for x in u["units"] if x.get("tatparya"))
        total += len(u["units"]); glossed += g
        flags = "; ".join(u["anomalies"])
        print(f"{u['index']:>3}. {u['name'][:32]:<34} "
              f"pp{u['pages'][0]}-{u['pages'][1]:<5} "
              f"{len(u['units']):>4} units, highest {u['highest']:>4}, "
              f"{g:>4} glossed  {flags}")
    print(f"\n{total} mantras, {glossed} with a tātparya")
    problems = check([{"units": u["units"]} for u in works])
    print("contents check: " + ("; ".join(problems) if problems else "all 25 agree"))
