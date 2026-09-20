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


def test_sandhis_with_no_scanned_volume_stay_empty(by_sandhi):
    """Sandhis 2-9 have no commentary volume in staging -- those eight were
    never scanned. If commentary appears there, something matched a verse it
    should not have."""
    for n in range(2, 10):
        got = [i["id"] for i in by_sandhi[n] if i.get("commentaries")]
        assert got == [], "sandhi %d has commentary from nowhere: %s" % (n, got[:3])


def test_commentary_records_where_it_came_from(items):
    """Every attached block keeps its volume, its page and the padya number
    the book printed -- which is often NOT the padya it was attached to, and
    a reader checking against the printed edition needs both."""
    for i in items:
        if i.get("commentaries"):
            src = i.get("commentary_source")
            assert src and src.get("page"), "%s has commentary with no source" % i["id"]
