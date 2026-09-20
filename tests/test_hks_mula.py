"""Harikathamrtasara: the mula must stay whole.

Jagannatha Dasa closes every sandhi on his ankita, ಜಗನ್ನಾಥವಿಠಲ. That gives
the text a completeness test it applies to itself, and it is a better test
than any padya count from outside: a sandhi that does not reach the ankita
has been cut short, whoever counted it and however they counted.

It caught a real one. The Android app's string resources, which this work was
first built from, have no sandhi 24 at all -- 0 padyas, and nothing in the
data said so. The printed mula has all 63, ending on the ankita.
"""
import collections
import json
import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(ROOT, "data", "Tattvavada", "Itara", "DasaSahitya",
                    "harikathamrutasara", "data.json")
ANKITA = ("ಜಗನ್ನಾಥವಿಠಲ", "ಜಗನ್ನಾಥವಿಠ್ಠಲ")


@pytest.fixture(scope="module")
def items():
    return json.load(open(WORK, encoding="utf-8"))["items"]


@pytest.fixture(scope="module")
def by_sandhi(items):
    out = collections.defaultdict(list)
    for it in items:
        out[it["sandhi_number"]].append(it)
    return out


def bare(t):
    return re.sub(r"[\s|।॥]+", "", str(t or ""))


def test_all_thirty_three_sandhis_are_present(by_sandhi):
    assert sorted(by_sandhi) == list(range(1, 34))


def test_no_sandhi_is_empty(by_sandhi):
    empty = [n for n in range(1, 34) if not by_sandhi[n]]
    assert empty == [], "sandhi(s) with no padyas: %s" % empty


def test_padya_ids_are_unique(items):
    dupes = [k for k, v in collections.Counter(i["id"] for i in items).items() if v > 1]
    assert dupes == []


def test_every_padya_has_text(items):
    empty = [i["id"] for i in items if not str(i.get("sa", "")).strip()]
    assert empty == []


@pytest.mark.parametrize("n", [n for n in range(1, 34) if n != 33])
def test_sandhi_closes_on_the_ankita(by_sandhi, n):
    """33 is the phalashruti and is excluded: it closes the work rather than
    a sandhi, and does not carry the ankita in its final padya."""
    last = by_sandhi[n][-1]
    assert any(a in bare(last["sa"]) for a in ANKITA), (
        "sandhi %d ends at padya %s without the ankita -- it is cut short"
        % (n, last["id"]))


def test_sandhi_24_is_the_one_recovered_from_the_scan(by_sandhi):
    """Guards the recovery specifically. If this work is ever rebuilt from
    the app resources alone, sandhi 24 silently vanishes again."""
    assert len(by_sandhi[24]) == 63
    assert all(i.get("text_source") for i in by_sandhi[24])


# --- the commentary, keyed by the verse it quotes ---------------------------

def test_most_padyas_carry_commentary(items):
    with_c = [i for i in items if i.get("commentaries")]
    assert len(with_c) >= 600, "commentary coverage fell to %d padyas" % len(with_c)


def test_no_commentary_is_empty(items):
    empty = [i["id"] for i in items
             for k, v in (i.get("commentaries") or {}).items()
             if not str(v).strip()]
    assert empty == []


def test_no_sandhi_is_entirely_without_commentary(by_sandhi):
    """Every sandhi the project holds a volume for carries some commentary.

    This test used to assert the opposite for 26 and 27 -- that they must stay
    empty, because "their volume IS scanned and simply does not carry them,"
    each padya scoring 0.38-0.65 against its best block. That reasoning was
    drawn from the bug's own symptom. The volume is hks__25_26_27_hks, and its
    publisher's preface on page 3 says what it holds: Arohana 25 (19 padyas),
    Avarohana 26 (7), Anukramanika 27 (5). Internal title pages announce 26 on
    page 131 and 27 on page 168, each printing the number on the line BELOW the
    title, where no pattern was looking for it. cur_sandhi therefore sat on 25
    for all 209 pages, every block came out labelled 25, and the 26 and 27
    blocks were dropped as duplicate padya numbers. The 0.38-0.65 scores were
    against sandhi-25 blocks, because the real ones had never reached the file.

    They score 0.93-0.99 now, 1:1 onto their own padyas. Guarding the positive
    fact instead: a sandhi with nothing at all is the shape that bug had.
    """
    bare = [n for n, rows in sorted(by_sandhi.items())
            if rows and not any(i.get("commentaries") for i in rows)]
    assert bare == [], "sandhi(s) with no commentary whatsoever: %s" % bare


def test_commentary_coverage_holds_after_the_2_to_9_import(items):
    """643 padyas before those eight volumes, 925 after. A drop below this
    means a regression in segmentation or matching, not a content decision."""
    with_c = [i for i in items if i.get("commentaries")]
    assert len(with_c) >= 900, "coverage fell to %d padyas" % len(with_c)


def test_commentary_records_where_it_came_from(items):
    """Every attached block keeps its volume, its page and the padya number
    the book printed -- which is often NOT the padya it was attached to, and
    a reader checking against the printed edition needs both."""
    for i in items:
        if i.get("commentaries"):
            src = i.get("commentary_source")
            assert src and src.get("page"), "%s has commentary with no source" % i["id"]
