#!/usr/bin/env python3
"""Segment the Saṅgraha Rāmāyaṇam (Pejāvara Maṭha edition, 2 vols).

सङ्ग्रहरामायणम् of Nārāyaṇa Paṇḍitācārya -- the same hand as the Sumadhva
Vijaya and the Maṇimañjarī, both already on this shelf -- with the
Bhāvārthadīpikā of Viśvapati Tīrtha and the Saṅgrahacandrikā of Bannañje
Govindācārya. Volume 1 is the Bāla and Ayodhyā kāṇḍas, volume 2 the
Sundara, Yuddha and Uttara.

Unlike the other works landed this week this one is a grantha of its own:
neither the mūla nor either commentary exists anywhere in the library. The
only occurrences of ``सङ्ग्रहरामायण`` in the corpus are other works quoting
it, and ``भावार्थदीपिका`` and ``सङ्ग्रहचन्द्रिका`` return nothing at all.

THE PAGE SETS THE VERSE APART FROM ITS NUMBER. A verse is a title block,
and its number is the block *below* it, alone -- ``॥ २६ ॥``. Reading the
number off the end of the verse finds nothing, because it is not there.

THE ADDRESS COMES FROM THE COLOPHONS, NOT THE RUNNING HEAD. The head does
carry it -- ``बालकां.स.५`` -- but only alternate pages have one, the others
carrying the page number and ``सं.रा.``, so an address held over from the
last page that had one lands a whole page of verses in the sarga before
theirs. That put 174 duplicate numbers and 960 gaps inside the sargas, and
made the first verse of the work a verse from the middle of it.

Each sarga instead ends with its own colophon -- ``इति
श्रीनारायणपण्डिताचार्य्यविरचिते रामाङ्के सङ्ग्रहरामायणे बालकाण्डे प्रथमः
सर्गः ॥`` -- and there are 64 of them, one per sarga. The kāṇḍa is read
from the colophon and the sarga is counted within it, so the ordinal
(प्रथमः, अष्टमः, and ``बालकाण्डेऽष्टमः`` with the avagraha eating the
space) never has to be parsed.
"""

from __future__ import annotations

import collections
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "ocr_common"))
import staged as S                                              # noqa: E402

STAGED = "data/ocr_staging/sangraha_ramayanam_n__mentaries_bhavartha_dipi_v{}"
VOLUMES = [1, 2]
SKIP = ("page-number", "image", "footer")

DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")

#: ``बालकां.स.५``, ``अयोध्याकां.स. २``, ``युद्धकां.स.१३``.
ADDRESS = re.compile(
    r"([ऀ-ॿ]+?)\s*कां\s*[.।]?\s*स\s*[.।]?\s*([०-९\d]+)")

#: The kāṇḍa each abbreviation stands for, and the order they run in.
#: Matched on a short distinctive stem, because the colophons misspell the
#: names: Ayodhyā is set as ``अयोद्धयाकाण्डे`` and ``अयोद्ध्याकाण्डे``, never
#: as ``अयोध्या``. Looking for the correct spelling dropped the entire kāṇḍa
#: -- 582 verses -- and silently renumbered the sargas of the kāṇḍas after it.
KANDAS = [("बाल", "bala_kanda", "बालकाण्डम्"),
          ("अयो", "ayodhya_kanda", "अयोध्याकाण्डम्"),
          # Printed ``अरण्यकां``, with the short अ, not ``आरण्य``. Looking
          # for the spelling the name has in the grammar rather than the
          # one on the page lost the whole kāṇḍa: 0 verses, silently.
          ("रण्य", "aranya_kanda", "आरण्यकाण्डम्"),
          ("किष्किन्ध", "kishkindha_kanda", "किष्किन्धाकाण्डम्"),
          ("सुन्दर", "sundara_kanda", "सुन्दरकाण्डम्"),
          ("युद्ध", "yuddha_kanda", "युद्धकाण्डम्"),
          ("उत्तर", "uttara_kanda", "उत्तरकाण्डम्")]

#: ``(भा.दी.)`` and ``(सं.चं.)``, the two commentaries, and the key each is
#: written under. The dots and the parentheses both come and go in the scan.
COMMENTARIES = [
    (re.compile(r"^\s*\(?\s*भा\s*[.।]?\s*दी\s*[.।]?\s*\)?\s*"),
     "bhavarthadipika"),
    (re.compile(r"^\s*\(?\s*सं\s*[.।]?\s*चं\s*[.।]?\s*\)?\s*"),
     "sangrahacandrika"),
]

#: A block that is nothing but ``॥ २६ ॥`` -- the number of the verse above.
NUMBER_ONLY = re.compile(r"^\s*[।॥|]{0,2}\s*([०-९\d]+)\s*[।॥|]{0,2}\s*$")

#: ...and the same number, set at the end of the verse instead. Both forms
#: are used. Reading only the block below left 620 commented verses with no
#: number at all.
NUMBER_TAIL = re.compile(r"[।॥|]\s*([०-९\d]+)\s*[।॥|]{0,2}\s*$")

#: ``इति … बालकाण्डे प्रथमः सर्गः ॥`` -- the line that closes each sarga.
COLOPHON = re.compile(r"इति\s+.{0,90}?सर्गः")

#: A verse runs to about this; past it the block is prose the scan mislabelled.
MAX_VERSE = 400
MIN_VERSE = 25


def kanda_of(text: str) -> tuple[str, str] | None:
    m = ADDRESS.search(text)
    if not m:
        return None
    name = m.group(1)
    for stem, slug, title in KANDAS:
        if name.endswith(stem) or stem in name:
            return slug, m.group(2).translate(DIGITS)
    return None


def blocks_of(volume: int) -> list[dict]:
    pages = S.load_sarvam(STAGED.format(volume))
    out = []
    for b in S.read_stream(pages, skip=SKIP):
        b["volume"] = volume
        out.append(b)
    return out


def body_starts(stream: list[dict]) -> int:
    """The first page whose running head names a kāṇḍa.

    Volume 1 gives 72 pages to the pīṭhikā before the mūla begins -- the
    editor's essays, a list of the author's works, a note on the figures of
    speech. Because the first colophon does not come until the end of the
    first sarga, all of it fell inside that sarga, and a line from a
    bibliography became verse 1 of the Bāla Kāṇḍa.
    """
    for b in stream:
        if b["kind"] == "header" and kanda_of(" ".join(b["text"].split())):
            return b["page"]
    return 0


def is_verse_block(kind: str, text: str, nxt: str) -> bool:
    """Whether this block is a verse, judged partly by what follows it.

    The scan labels a verse ``section-title`` or ``headline`` most of the
    time, but 758 of them come through as ``paragraph`` -- a third of the
    work. What marks a verse either way is what sits under it: its number
    alone on a line, or the first commentary. Footnotes are excluded
    whatever follows them; they are variant readings, not the text.
    """
    if kind == "footnote" or not looks_like_verse(text):
        return False
    if kind in ("section-title", "headline"):
        return True
    if kind != "paragraph":
        return False
    return bool(NUMBER_ONLY.match(nxt)
                or any(pat.match(nxt) for pat, _ in COMMENTARIES))


def looks_like_verse(text: str) -> bool:
    if not (MIN_VERSE <= len(text) <= MAX_VERSE):
        return False
    if any(p.match(text) for p, _ in COMMENTARIES):
        return False
    return not NUMBER_ONLY.match(text)


def segment(volumes=VOLUMES) -> list[dict]:
    """Walk the stream, closing a sarga at each colophon."""
    units: list[dict] = []
    pending: list[dict] = []
    seen: collections.Counter = collections.Counter()
    cur: dict | None = None
    key: str | None = None

    def close(colophon: str) -> None:
        nonlocal pending, cur, key
        # The name is whatever stands in front of काण्ड in the colophon;
        # matching a stem against the whole line let ``रामाङ्के`` and the
        # author's name interfere.
        named = re.search(r"([\u0900-\u097F]{2,14})काण्ड", colophon)
        slug = None
        if named:
            name = named.group(1)
            for stem, s_, _title in KANDAS:
                if stem in name:
                    slug = s_
                    break
        if slug and pending:
            seen[slug] += 1
            for u in pending:
                u["kanda"], u["sarga"] = slug, str(seen[slug])
            units.extend(pending)
        pending, cur, key = [], None, None

    for volume in volumes:
        stream = blocks_of(volume)
        start = body_starts(stream)
        for i, b in enumerate(stream):
            if b["page"] < start:
                continue        # pīṭhikā, contents, the editor's essays
            text = " ".join(b["text"].split())
            if not text:
                continue
            if b["kind"] in ("header", "footnote"):
                continue        # the head lags; the footnotes are variants

            if len(text) < 170 and COLOPHON.search(text):
                close(text)
                continue

            nxt = (" ".join(stream[i + 1]["text"].split())
                   if i + 1 < len(stream) else "")
            if is_verse_block(b["kind"], text, nxt):
                number = None
                tail = NUMBER_TAIL.search(text)
                if tail:
                    number = int(tail.group(1).translate(DIGITS))
                    text = text[:tail.start()].strip(" |।॥")
                cur = {"kanda": None, "sarga": None,
                       "page": b["page"], "volume": volume,
                       "verse": text, "number": number,
                       "layers": {}, "order": []}
                pending.append(cur)
                key = None
                continue
            if cur is None:
                continue

            m = NUMBER_ONLY.match(text)
            if m and cur["number"] is None and not cur["layers"]:
                cur["number"] = int(m.group(1).translate(DIGITS))
                continue

            hit = None
            for pat, name in COMMENTARIES:
                mm = pat.match(text)
                if mm:
                    hit, text = name, text[mm.end():]
                    break
            if hit:
                key = hit
            if key is None:
                continue
            cur["layers"].setdefault(key, []).append(text)
            if key not in cur["order"]:
                cur["order"].append(key)

    for u in units:
        u["layers"] = {k: " ".join(v).strip() for k, v in u["layers"].items()}
    return number_by_position([u for u in units if is_really_a_verse(u)])


def is_really_a_verse(unit: dict) -> bool:
    """A verse here carries its printed number, or a commentary, or both.

    What carries neither is the furniture that sits around a sarga break:
    the contents line for the sarga coming up (``पञ्चमः सर्गः अन्तःपुरवृद्धेन
    तारासान्त्वनम् …``), the Saṅgrahacandrikā's own closing line, and the
    editor's prose. Left in, one of those became verse 1 of 22 of the 64
    sargas, pushing the real opening verse to 2 -- so the Sundara Kāṇḍa
    began with a table of contents instead of Hanūmān's leap.

    143 units of 3,672, and the rule is safe because the two signals
    between them cover almost everything: 3,323 verses carry a printed
    number and 3,261 carry the Bhāvārthadīpikā.
    """
    return bool(unit.get("number") or unit["layers"])


def number_by_position(units: list[dict]) -> list[dict]:
    """Number each verse by where it stands in its sarga, 1..N.

    The printed numbers are kept, in ``printed``, but they cannot key the
    shelf: read straight off the page they give 144 duplicates and 1,587
    gaps across the 64 sargas, and the first verse of the work -- the
    maṅgalācaraṇa -- does not come out as 1. The book sets a verse's number
    on the line below it, and where the scan drops or repeats one of those
    lines the number lands on its neighbour.

    A position is unambiguous and complete, and keeping the printed number
    beside it means nothing is thrown away: a reader sees what the page
    says, and the shelf has a key it can rely on.
    """
    by_sarga: dict[tuple, list[dict]] = {}
    for u in units:
        by_sarga.setdefault((u["kanda"], u["sarga"]), []).append(u)
    for run in by_sarga.values():
        for i, u in enumerate(run, 1):
            u["printed"] = u["number"]
            u["number"] = i
    return units


def report(units: list[dict]) -> dict:
    sections = collections.Counter()
    layers = collections.Counter()
    for u in units:
        if u["kanda"] and u["number"]:
            sections[(u["kanda"], u["sarga"])] += 1
        layers.update(u["layers"].keys())
    return {"units": len(units),
            "addressed": sum(1 for u in units if u["kanda"] and u["number"]),
            "numbered": sum(1 for u in units if u.get("printed")),
            "sections": sections, "layers": layers}


if __name__ == "__main__":
    us = segment()
    r = report(us)
    print(f"{r['units']} verses, {r['addressed']} addressed, "
          f"{r['numbered']} carrying the number the page printed, "
          f"{len(r['sections'])} sargas")
    for k, n in r["layers"].most_common():
        print(f"   {k:<20} {n:>5}")
    per = collections.Counter()
    for (kanda, _), n in r["sections"].items():
        per[kanda] += n
    print()
    for _, slug, title in KANDAS:
        if per[slug]:
            sargas = len([1 for (k, _) in r["sections"] if k == slug])
            print(f"   {title:<18} {per[slug]:>5} verses in {sargas:>3} sargas")
