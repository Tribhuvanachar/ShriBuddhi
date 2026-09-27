#!/usr/bin/env python3
"""Segment the Gītā Vyākhyāna Saṅgraha (Gurusārvabhauma edition, 4 vols).

गीता-व्याख्यान-सङ्ग्रहः, पञ्चदशव्याख्यानसमेता श्रीमद्भगवद्गीता -- the Gītā
with fifteen commentaries, ~2,800 pages, the complete Gītā across four
volumes (adhyāyas 1-2, 3-8, 9-12, 13-18).

WHAT THIS WRITES IS FIVE OF THE FIFTEEN. Ten are already in the library,
matched by author rather than by title: the Gītābhāṣya division (Madhva,
Padmanābha, Narahari, Jayatīrtha, Rāghavendra, Sumatīndra) all six under
DvaitaVedantaIn/gita_prasthana/gita_bhashya/, and the Gītātātparya division
(Madhva, Padmanābha, Jayatīrtha, Rāghavendra) all four under
gita_tatparya_nirnaya/. The mūla Gītā itself is at
itihasa/bhagavad_gita/adhyaya_01..18 and already carries 21 commentators.

What is absent everywhere is the मूलगीताविभागः -- the five that comment on
the mūla Gītā rather than on Madhva's bhāṣya. Those are what this reads.

EACH COMMENTARY IS NAMED BY THE ABBREVIATION THE BOOK ASSIGNS IT. Its own
contents page gives the table: ``वि०वि०—`` is Vidyādhirāja's Gītāvivṛti,
``वा०ल०—`` Vādirāja's Gītālakṣālaṅkāra, and so on. The others are read too,
so their blocks are consumed and do not drift into the five, and then
dropped.

THE RUNNING HEADER IS NOT ENOUGH TO ADDRESS BY. It does carry the verse --
``अध्यायः ३ - श्लोकः १५`` -- but only a third of pages have one and they
reach just 453 of the 700 verses, with two impossible adhyāyas (57, 58) in
the noise. It is also spelt both ``अध्याय`` and ``अध्यायः``, and matching
only the first found volume 1 alone and reported volumes 2-4 as having no
headers at all. So the addresses come from the corpus: all 700 verses are
already on the shelf in order, and each unit takes the id of the next one
it matches.
"""

from __future__ import annotations

import difflib
import json
import pathlib
import re
import sys
import unicodedata

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "ocr_common"))
import staged as S                                              # noqa: E402

STAGED = "data/ocr_staging/giia_vyakhyana_sangr__ntaries_on_bhagavad_gita_v{}"
VOLUMES = [1, 2, 3, 4]
GITA = "data/itihasa/bhagavad_gita/adhyaya_{:02d}/data.json"
ADHYAYAS = range(1, 19)

SKIP = ("page-number", "footer", "image", "header", "folio", "sidebar")

#: The title that introduces the mūla verse.
GITA_TITLE = re.compile(r"^\s*गीता\s*$")

#: ``अध्यायः ३ - श्लोकः १५``, and ``अध्याय २ - श्लोकः २४`` without the
#: visarga. Used only to corroborate, never to address.
ADDRESS = re.compile(
    r"अध्याय\S{0,2}\s*([०-९\d]+)\s*[-–—]\s*श्लोक\S{0,2}\s*([०-९\d]+)")

#: The five on the mūla Gītā, by the abbreviation the book's contents page
#: assigns each, and the key each is written under.
COMMENTARIES = [
    (re.compile(r"^\s*वि\s*०\s*वि\s*०\s*[-–—]\s*"), "gitavivrti"),
    (re.compile(r"^\s*वा\s*०\s*ल\s*०\s*[-–—]\s*"), "gitalakshalankara"),
    (re.compile(r"^\s*सा\s*०\s*सं\s*०\s*[-–—]\s*"), "gitasarasangraha"),
    (re.compile(r"^\s*अ\s*०\s*प्र\s*०\s*[-–—]\s*"), "anvayaprakashika"),
    (re.compile(r"^\s*त्रि\s*०\s*वि\s*०\s*[-–—]\s*"), "trividharthavivrti"),
]

#: The ten already in the library. Read so their blocks are consumed and do
#: not drift into one of the five, then dropped.
#:
#: ``भा०र०`` is the Bhāvaratnakośa, and the scan reads it as ``भा०२०`` on 93
#: blocks of volume 1 alone -- र as २. Both spellings, or a tenth of that
#: commentary lands inside whichever of the five precedes it.
ALREADY_LANDED = [
    (re.compile(r"^\s*प\s*०\s*टी\s*०\s*[-–—]\s*"), "bhavaprakashika_padmanabha"),
    (re.compile(r"^\s*न\s*०\s*टी\s*०\s*[-–—]\s*"), "bhavaprakashika_narahari"),
    (re.compile(r"^\s*प्र\s*०\s*दी\s*०\s*[-–—]\s*"), "prameyadipika"),
    (re.compile(r"^\s*भा\s*०\s*दी\s*०\s*[-–—]\s*"), "bhavadipa"),
    (re.compile(r"^\s*भा\s*०\s*(?:र|२)\s*०\s*[-–—]\s*"), "bhavaratnakosha"),
    (re.compile(r"^\s*प्रका\s*०\s*[-–—]\s*"), "bhavapradipika"),
    (re.compile(r"^\s*न्या\s*०\s*दी\s*०\s*[-–—]\s*"), "nyayadipika"),
    (re.compile(r"^\s*न्या\s*०\s*टी\s*०\s*[-–—]\s*"), "nyayadipika_tika"),
]

ALL_MARKERS = COMMENTARIES + ALREADY_LANDED
WRITTEN = {key for _, key in COMMENTARIES}

ACCENT = re.compile(r"[॒॑॓॔᳐-᳿​-‍]")
STRIP = re.compile(r"[।॥|.,\-–—'\"“”‘’()\[\]॰ऽ\s\d०-९]+")

#: A speaker line is printed above the verse in the corpus but not always in
#: the book, so it is dropped from both sides before comparing.
SPEAKER = re.compile(r"^\s*\S+\s*उवाच\s*[-–—]?\s*")


def fold(text: str) -> str:
    return STRIP.sub("", ACCENT.sub("", unicodedata.normalize("NFC", text)))


def corpus_verses() -> list[dict]:
    """All 700 verses, in order, from the Gītā already on the shelf."""
    out = []
    for a in ADHYAYAS:
        d = json.loads(pathlib.Path(GITA.format(a)).read_text(encoding="utf-8"))
        for s in d["items"][0]["shlokas"]:
            text = SPEAKER.sub("", (s.get("sanskrit_text") or "").strip())
            out.append({"adhyaya": a, "number": s["number"],
                        "id": f"{a}.{s['number']}", "fold": fold(text)})
    return out


def candidate_probes(text: str, limit: int = 4) -> list[str]:
    """The block as written, and again from each daṇḍa that follows it."""
    parts = re.split(r"[।॥]", text)
    out = []
    for i in range(min(limit, len(parts))):
        piece = fold("".join(parts[i:]))
        if len(piece) >= 12:
            out.append(piece)
    return out


def blocks_of(volume: int) -> list[dict]:
    pages = S.load_sarvam(STAGED.format(volume))
    out = []
    for b in S.read_stream(pages, skip=SKIP):
        b["volume"] = volume
        out.append(b)
    return out


def strip_marker(text: str) -> tuple[str | None, str]:
    """Take the commentary's abbreviation off the front of a block.

    Repeatedly: the scan sets it down twice often enough to matter --
    ``अ०प्र०— अ०प्र०— पूर्वाध्याये…`` -- and stripping once leaves the
    second one sitting at the head of the commentary, where it reads as
    text.
    """
    hit = None
    while True:
        for pat, name in ALL_MARKERS:
            m = pat.match(text)
            if m:
                hit = hit or name
                text = text[m.end():]
                break
        else:
            return hit, text


def split_units(blocks: list[dict]) -> list[dict]:
    """Cut at each ``गीता`` title and gather the commentaries under it."""
    units, cur, key = [], None, None
    for b in blocks:
        text = " ".join(b["text"].split())
        if not text:
            continue

        if GITA_TITLE.match(text):
            cur = {"page": b["page"], "volume": b["volume"],
                   "verse": [], "layers": {}, "order": []}
            units.append(cur)
            key = None
            continue
        if cur is None:
            continue

        hit, text = strip_marker(text)
        if hit:
            key = hit
        if key is None:
            cur["verse"].append(text)
            continue
        if key not in cur["layers"]:
            cur["layers"][key] = [text]
            cur["order"].append(key)
        else:
            cur["layers"][key].append(text)

    for u in units:
        u["verse"] = " ".join(u["verse"]).strip()
        u["layers"] = {k: " ".join(v).strip() for k, v in u["layers"].items()}
    return units


def score(probe: str, want: str, threshold: float) -> float:
    """How much of the block the verse accounts for.

    A prefix comparison is not enough, because this edition sets a long
    verse as two half-verses under two ``गीता`` titles: the corpus holds
    1.9 whole, the book prints ``नानाशस्त्रप्रहरणाः…`` on its own, and
    against the full verse that scores far too low. So the block is scored
    by how much of IT the verse contains, which is the same number for a
    whole verse and for either half of one.

    The minimum length is what keeps that from being generous: a short
    block shares enough with any verse to pass.
    """
    if len(probe) < 25:
        return 0.0
    head = difflib.SequenceMatcher(None, probe[:len(want)], want,
                                   autojunk=False)
    if head.real_quick_ratio() >= threshold and head.quick_ratio() >= threshold:
        r = head.ratio()
        if r >= threshold:
            return r
    sm = difflib.SequenceMatcher(None, probe, want, autojunk=False)
    covered = sum(b.size for b in sm.get_matching_blocks())
    return covered / len(probe)


def address(units: list[dict], verses: list[dict],
            window: int = 4, threshold: float = 0.78) -> list[dict]:
    """Sequential and forward-only, against the Gītā already on the shelf.

    The commentaries quote the Gītā at each other constantly -- with the
    citation printed, ``(गी. ४-१५)`` -- so a search that is free to look
    anywhere lands on a quotation. Going forward only, from the verse last
    matched, is what keeps a quotation from stealing an address.
    """
    nxt = 0
    for u in units:
        u["id"] = None
        probes = candidate_probes(u["verse"])
        if not probes:
            continue

        # The same verse again, before looking forward. This edition sets a
        # long verse as two half-verses under two ``गीता`` titles, and the
        # first half advances the scan past it -- so the second half matched
        # nothing and its commentary was dropped. Both halves address the
        # verse they are halves of.
        if nxt > 0:
            want = verses[nxt - 1]["fold"]
            if want and max((score(p, want, threshold) for p in probes),
                            default=0.0) >= threshold:
                u["id"] = verses[nxt - 1]["id"]
                u["continues"] = True
                continue

        for off in range(min(window, len(verses) - nxt)):
            want = verses[nxt + off]["fold"]
            if not want:
                continue
            best = 0.0
            for probe in probes:
                best = max(best, score(probe, want, threshold))
                if best >= threshold:
                    break
            if best >= threshold:
                u["id"] = verses[nxt + off]["id"]
                u["match"] = round(best, 3)
                nxt = nxt + off + 1
                break
    return units


def segment(volumes=VOLUMES) -> list[dict]:
    blocks = []
    for v in volumes:
        blocks.extend(blocks_of(v))
    return address(split_units(blocks), corpus_verses())


def report(units: list[dict]) -> dict:
    import collections
    layers = collections.Counter()
    for u in units:
        if u.get("id"):
            layers.update(u["layers"].keys())
    return {"units": len(units),
            "addressed": sum(1 for u in units if u.get("id")),
            "distinct": len({u["id"] for u in units if u.get("id")}),
            "layers": layers}


if __name__ == "__main__":
    us = segment()
    r = report(us)
    print(f"{r['units']} verse blocks, {r['addressed']} addressed, "
          f"{r['distinct']} distinct verses of 700")
    print("\nlayer coverage (addressed units only):")
    for k, n in r["layers"].most_common():
        tag = "" if k in WRITTEN else "   [already in the library]"
        print(f"   {k:<30} {n:>5}{tag}")
    ids = [u["id"] for u in us if u.get("id")]
    if ids:
        print(f"\nfirst {ids[0]}   last {ids[-1]}")
