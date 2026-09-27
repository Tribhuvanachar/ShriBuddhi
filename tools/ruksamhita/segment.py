#!/usr/bin/env python3
"""Segment the Ṛksaṃhitā with nine vyākhyānas (Vidyādhīśa edition, 5 vols).

ऋक्संहिता पदपाठसहिता, with the Ṛgbhāṣya of Madhva, Jayatīrtha's ṭīkā,
Rāghavendra's Mantrārthamañjarī, and the bhāṣyas of Skandasvāmin,
Veṅkaṭamādhava, Mudgala and Sāyaṇa, Kapālīśāstrī's Siddhāñjana and
Dyādeva's Nītimañjarī.  Five volumes, prathama aṣṭaka, adhyāyas 1-7 --
maṇḍala 1 only.

WHAT THIS DOES NOT TOUCH. The saṃhitā, its padapāṭha and Sāyaṇa's bhāṣya
are already in the corpus, complete, with svara -- 1,370 mantras in the
zone this edition covers, all carrying pada_patha, and Sāyaṇa on 1,337 of
them. So this reads them off the page only to *address* the commentary
that follows, and writes neither. What it writes is the other layers,
which exist nowhere in the library.

THE BOOK'S OWN MARKER IS THE ANCHOR. Each mantra is introduced by the
line ``ऋक्संहिता पदपाठसहिता``, 199 of them across volume 1 against 194
mantras. Anchoring on the mantra *text* instead looked simpler and was
wrong: the Nītimañjarī quotes ṛks as illustrations of its maxims --
``अत्रार्थे ऋक् (ऋ.१.१.६)-`` and then the whole mantra with its padapāṭha
-- so a text search lands on the quotation, and 1.1.7 and 1.1.8 were
skipped because 1.1.9's quotation was met first, inside the commentary on
1.1.6. Citations belong to another text; the label does not lie.

EACH COMMENTARY NAMES ITSELF, AND THE NAME ENDS IN A HYPHEN.
``सायण- अयम् अग्निः …``, ``मुद्गल- …``, ``स्कन्द- …``. Madhva's Ṛgbhāṣya
is the exception: it is a ``section-title`` reading ``ऋग्भाष्यम्``, with
its verse in the block below.

ADDRESSES COME FROM THE CORPUS, NOT THE PAGE. The running head carries
``[अ.१ अ.१ व.१`` and ``सू. १ मं. २]``, but it is a header -- the thing
OCR mangles most. The mantras are already on the shelf in order, so each
unit is matched against the next expected one and takes its id. A unit
that matches nothing is reported rather than guessed at.
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

STAGED = "data/ocr_staging/ruksamhita__ruksamhita_9_vyakhyanagalu_bhaga_{}"
VOLUMES = [1, 2, 3, 4, 5]
MANDALA = "data/vedas/rigveda/shakala_shakha/samhita/mandala_01/data.json"

SKIP = ("page-number", "footer", "image", "header", "folio")

#: The line that introduces every mantra.
PADAPATHA = re.compile(r"ऋक्\s*सं?हिता\s*पदपाठ\S*(?:\s*सहिता|\s*संहिता)?")

#: Madhva's bhāṣya is announced by a title of its own, not a hyphenated name.
RGBHASHYA = re.compile(r"^\s*ऋग्भाष्यम्\s*$")

#: The title that opens a commentary's *own* introduction, as against its
#: gloss on a mantra: ``श्रीस्कन्दस्वामिविरचितं भाष्यम्``,
#: ``श्रीमत्सायणाचार्यविरचितं भाष्यम् उपोद्घातप्रकरणम्``.
#:
#: Volume 1 gives pages 33 to 105 to these, one after another, and each of
#: them discusses the first mantra -- so the volume prints the mantra once
#: at the head of the whole sequence. Read as a mantra unit, that one label
#: swallowed all seventy-three pages: 131,513 characters filed as Madhva's
#: gloss on 1.1.1, against a median of 134 for that layer. The per-mantra
#: body starts at page 106, with the second mantra. Mantra 1 has no
#: per-mantra apparatus in this edition; the introductions are its apparatus.
INTRO_TITLE = re.compile(r"विरचित|उपोद्घात")

#: ``<name>- <text>``.  The corpus key each one is written under.  Sāyaṇa is
#: read so that the block is consumed and does not drift into the commentary
#: above it, and then dropped: the corpus already carries Sāyaṇa on 1,337 of
#: these 1,370 mantras, and a second copy would be a duplicate, not a layer.
COMMENTARIES = [
    (re.compile(r"^\s*ऋग्भाष्यटीका\s*[-–—]\s*"), "rgbhashya_tika"),
    (re.compile(r"^\s*मन्त्रार्थमञ्जरी\s*[-–—]\s*"), "mantrarthamanjari"),
    (re.compile(r"^\s*स्कन्द(?:स्वामी?)?\s*[-–—]\s*"), "skandasvamin"),
    (re.compile(r"^\s*वेङ्कटमाधवा?\s*[-–—]\s*"), "venkatamadhava"),
    (re.compile(r"^\s*मुद्गला?\s*[-–—]\s*"), "mudgala"),
    (re.compile(r"^\s*सायणा?\s*[-–—]\s*"), "sayana"),
    (re.compile(r"^\s*सिद्धाञ्ज\S*\s*[-–—]\s*"), "siddhanjana"),
    (re.compile(r"^\s*नीतिमञ्जरी\s*[-–—]\s*"), "nitimanjari"),
]

#: Already in the corpus; captured only so it does not bleed into its neighbour.
ALREADY_LANDED = {"sayana"}

ACCENT = re.compile(r"[॒॑॓॔᳐-᳿​-‍]")
STRIP = re.compile(r"[।॥|.,\-–—'\"“”‘’()\[\]॰ऽ\s\d०-९]+")


def fold(text: str) -> str:
    """Accents, punctuation and numbers off -- what is left is the wording."""
    return STRIP.sub("", ACCENT.sub("", unicodedata.normalize("NFC", text)))


def candidate_probes(text: str, limit: int = 6) -> list[str]:
    """The mantra as written, and again from each daṇḍa that follows.

    The first mantra of a sūkta is preceded by that sūkta's own header --
    ``९ मधुच्छन्दा वैश्वामित्रः । अग्निः । गायत्री ।``, the count, ṛṣi,
    devatā and metre -- so comparing from the front of the block misses it.
    Rather than parse that header, try again from each daṇḍa: one of the
    starts lands on the mantra, whatever the header happens to contain.
    """
    parts = re.split(r"[।॥]", text)
    out, acc = [], []
    for i in range(min(limit, len(parts))):
        piece = fold("".join(parts[i:]))
        if len(piece) >= 10:
            out.append(piece)
    return out


def corpus_mantras(path: str = MANDALA, upto_sukta: int = 200) -> list[dict]:
    d = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    out = []
    for it in d["items"]:
        parts = it["id"].split(".")
        if int(parts[1]) <= upto_sukta:
            out.append({"id": it["id"], "fold": fold(it["samhita_patha"])})
    return out


DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")


def printed_numbers(blocks: list[dict]) -> dict[int, int]:
    """Scan page -> the page number printed on it."""
    out = {}
    for b in blocks:
        if b["kind"] == "page-number":
            t = " ".join(b["text"].split()).translate(DIGITS)
            if t.isdigit():
                out.setdefault(b["page"], int(t))
    return out


def duplicate_scans(blocks: list[dict]) -> set[int]:
    """Scan pages that repeat a page already scanned, by number AND content.

    Every volume carries true duplicates -- the same page scanned twice,
    usually two apart, identical but for OCR noise. Left in, each one opens
    a second unit for a mantra already addressed, and since an id is given
    only once the second copy goes unaddressed and its commentary is lost.

    The printed number alone is not enough to spot them, and trusting it
    cost 110 mantras: the front matter is numbered separately and restarts,
    so volume 1 prints a page 3 in the prologue and another in the body,
    and they are different pages. So the content has to agree too. The
    fuller copy is the one kept -- a duplicate is sometimes the cleaner read
    of the two, and length is the only signal available without the image.
    """
    printed = printed_numbers(blocks)
    body: dict[int, list[str]] = {}
    for b in blocks:
        if b["kind"] not in ("page-number", "header", "footer"):
            body.setdefault(b["page"], []).append(b["text"])
    text = {p: fold(" ".join(v))[:300] for p, v in body.items()}
    weight = {p: len(" ".join(v)) for p, v in body.items()}

    groups: dict[int, list[int]] = {}
    for scan, number in printed.items():
        groups.setdefault(number, []).append(scan)

    drop: set[int] = set()
    for number, scans in groups.items():
        if len(scans) < 2:
            continue
        kept: list[int] = []
        for scan in sorted(scans):
            mine = text.get(scan, "")
            if not mine:
                continue
            twin = next(
                (k for k in kept
                 if difflib.SequenceMatcher(
                     None, mine, text.get(k, ""), autojunk=False
                 ).quick_ratio() >= 0.90
                 and difflib.SequenceMatcher(
                     None, mine, text.get(k, ""), autojunk=False
                 ).ratio() >= 0.90),
                None)
            if twin is None:
                kept.append(scan)
                continue
            if weight.get(scan, 0) > weight.get(twin, 0):
                drop.add(twin)
                kept[kept.index(twin)] = scan
            else:
                drop.add(scan)
    return drop


def blocks_of(volume: int) -> list[dict]:
    pages = S.load_sarvam(STAGED.format(volume))
    raw = S.read_stream(pages, skip=())
    drop = duplicate_scans(raw)
    out = [b for b in S.read_stream(pages, skip=SKIP) if b["page"] not in drop]
    for b in out:
        b["volume"] = volume
    return out


def split_units(blocks: list[dict]) -> list[dict]:
    """Cut at every ``ऋक्संहिता पदपाठसहिता`` and gather the layers under it."""
    units, cur, front_matter = [], None, False

    def start(page, volume, rest):
        nonlocal cur
        # Accumulated as lists and joined once at the end. Built by repeated
        # ``+=`` this was quadratic, and the commentary on 1.1.1 alone runs
        # to a hundred pages -- enough to turn a one-minute pass into a run
        # that had to be killed.
        cur = {"page": page, "volume": volume, "mantra": [rest.strip()],
               "layers": {}, "order": []}
        units.append(cur)

    key = None
    for b in blocks:
        text = " ".join(b["text"].split())
        if not text:
            continue

        m = PADAPATHA.search(text[:60])
        if m:
            front_matter = False
            start(b["page"], b["volume"], text[m.end():])
            key = None
            continue

        if (b["kind"] in ("section-title", "headline") and len(text) < 90
                and INTRO_TITLE.search(text)):
            # A commentary's own introduction opens here, so whatever unit is
            # open was the front matter's single display of the first mantra,
            # not a mantra of the body.
            front_matter = True
            if cur is not None:
                cur["front_matter"] = True
            cur, key = None, None
            continue

        if cur is None or front_matter:
            continue                      # front matter, before the first mantra

        if RGBHASHYA.match(text):
            key = "rgbhashya"
            continue

        for pat, name in COMMENTARIES:
            hit = pat.match(text)
            if hit:
                key = name
                text = text[hit.end():]
                break

        if key is None:
            # The mantra and its padapāṭha, still: they run over a block or two
            # below the label before the first commentary opens.
            cur["mantra"].append(text)
            continue

        if key not in cur["layers"]:
            cur["layers"][key] = [text]
            cur["order"].append(key)
        else:
            cur["layers"][key].append(text)

    units = [u for u in units if not u.get("front_matter")]
    for u in units:
        u["mantra"] = " ".join(x for x in u["mantra"] if x).strip()
        u["layers"] = {k: " ".join(v).strip() for k, v in u["layers"].items()}
    return units


def address(units: list[dict], mantras: list[dict],
            window: int = 4, threshold: float = 0.78) -> list[dict]:
    """Give each unit the id of the next corpus mantra it matches.

    Sequential and forward-only: the mantras are already in order on the
    shelf, so a unit is compared against the next few expected and takes the
    first that matches. A small window lets a mantra the scan dropped be
    stepped over without losing everything after it.

    The comparison is on the longest run the two share, not on the opening
    characters, because the first mantra of every sūkta is preceded by that
    sūkta's own header -- ``९ मधुच्छन्दा वैश्वामित्रः । अग्निः । गायत्री ।``,
    the count, ṛṣi, devatā and metre. Compared from the front, every one of
    those failed to match the mantra sitting right behind it, which is 144
    of the 145 that went unaddressed on the first run.
    """
    nxt = 0
    for u in units:
        u["id"] = None
        probes = candidate_probes(u["mantra"])
        if not probes:
            continue
        for off in range(min(window, len(mantras) - nxt)):
            want = mantras[nxt + off]["fold"]
            if not want:
                continue
            best = 0.0
            for probe in probes:
                r = difflib.SequenceMatcher(
                    None, probe[:len(want)], want, autojunk=False).ratio()
                if r > best:
                    best = r
                if best >= threshold:
                    break
            if best >= threshold:
                u["id"] = mantras[nxt + off]["id"]
                u["match"] = round(best, 3)
                nxt = nxt + off + 1
                break

    recover(units, mantras, threshold)
    return units


def recover(units: list[dict], mantras: list[dict], threshold: float) -> None:
    """Give a second chance to units the forward scan stepped over.

    The scan only ever looks a few mantras ahead, so one bad block can carry
    it past a good one -- and the good one is then never tried again. This
    pass takes each unaddressed unit and searches only between the ids its
    addressed neighbours already hold, which keeps the order intact and
    cannot reach an id that is already spoken for.
    """
    index = {m["id"]: i for i, m in enumerate(mantras)}
    taken = {u["id"] for u in units if u.get("id")}
    for pos, u in enumerate(units):
        if u.get("id"):
            continue
        before = next((units[i]["id"] for i in range(pos - 1, -1, -1)
                       if units[i].get("id")), None)
        after = next((units[i]["id"] for i in range(pos + 1, len(units))
                      if units[i].get("id")), None)
        lo = index[before] + 1 if before else 0
        hi = index[after] if after else len(mantras)
        if hi <= lo:
            continue
        probes = candidate_probes(u["mantra"])
        best, best_id = 0.0, None
        for m in mantras[lo:hi]:
            if m["id"] in taken or not m["fold"]:
                continue
            for probe in probes:
                r = difflib.SequenceMatcher(
                    None, probe[:len(m["fold"])], m["fold"],
                    autojunk=False).ratio()
                if r > best:
                    best, best_id = r, m["id"]
        if best >= threshold:
            u["id"], u["match"] = best_id, round(best, 3)
            u["recovered"] = True
            taken.add(best_id)


def segment(volumes=VOLUMES) -> list[dict]:
    blocks = []
    for v in volumes:
        blocks.extend(blocks_of(v))
    return address(split_units(blocks), corpus_mantras())


def report(units: list[dict]) -> dict:
    import collections
    layers = collections.Counter()
    for u in units:
        if not u.get("id"):
            continue
        for k in u["layers"]:
            layers[k] += 1
    return {
        "units": len(units),
        "addressed": sum(1 for u in units if u.get("id")),
        "unaddressed": sum(1 for u in units if not u.get("id")),
        "distinct_ids": len({u["id"] for u in units if u.get("id")}),
        "layers": layers,
    }


if __name__ == "__main__":
    us = segment()
    r = report(us)
    print(f"{r['units']} mantra blocks, {r['addressed']} addressed, "
          f"{r['unaddressed']} not, {r['distinct_ids']} distinct mantras")
    print("\nlayer coverage (addressed units only):")
    for k, n in r["layers"].most_common():
        tag = "  [already in the corpus]" if k in ALREADY_LANDED else ""
        print(f"   {k:<22} {n:>5}{tag}")
    ids = [u["id"] for u in us if u.get("id")]
    if ids:
        print(f"\nfirst {ids[0]}   last {ids[-1]}")
