"""108 Upaniṣat Sarvasva — the four things that were actually wrong.

Every test here stands for a measurement that came back wrong the first
time, not for a rule that looked sensible in the abstract.
"""
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools" / "upanishad_sarvasva"))
sys.path.insert(0, str(REPO / "tools" / "ocr_common"))

import segment as seg          # noqa: E402
import write_shelf as shelf    # noqa: E402

STAGED = REPO / "data/ocr_staging/108_upanishad_sarvas__narasimha_1_ttd_kannada"


@pytest.fixture(scope="module")
def works():
    if not STAGED.is_dir():
        pytest.skip("staged OCR not checked out")
    return seg.segment(str(STAGED))


# --------------------------------------------------------------- numbering

def test_a_mantra_carrying_both_numbers_gives_the_upanishad_wide_one():
    assert seg.numbers("... ಪ್ರತಿತಿಷ್ಠತಿ ॥ 9 (34)") == (9, 34)


def test_a_bare_parenthesis_is_the_LOCAL_number_not_the_running_one():
    """The bug that cut the volume into 187 pieces instead of 25.

    In ``॥ 8 (33)`` the parenthesis holds the Upaniṣad-wide number, but
    standing alone -- Chāndogya's prose khaṇḍas -- it is the number within
    the khaṇḍa and restarts a few lines later.  Read as Upaniṣad-wide, it
    looked like a new Upaniṣad beginning at every khaṇḍa.
    """
    assert seg.numbers("ತಸ್ಯೋಪ ವ್ಯಾಖ್ಯಾನಮ್ (9)") == (9, None)


def test_the_closing_danda_is_optional():
    """``|| 15`` with nothing after it is as common as ``॥ 15 ॥``."""
    assert seg.numbers("... ದೃಷ್ಟಯೇ || 15") == (15, None)
    assert seg.numbers("... ದೃಷ್ಟಯೇ ॥ 15 ॥") == (15, None)


def test_devanagari_and_kannada_digits_both_count():
    assert seg.numbers("... ॥ ೧೨ ॥") == (12, None)
    assert seg.numbers("... ॥ १२ ॥") == (12, None)


def test_stripping_the_number_keeps_the_mantra():
    out = seg.strip_number("ಓಂ ಈಶಾವಾಸ್ಯಮಿದಗ್ಂ ಸರ್ವಂ || 1")
    assert out == "ಓಂ ಈಶಾವಾಸ್ಯಮಿದಗ್ಂ ಸರ್ವಂ"


# --------------------------------------------------------------- colophons

def test_the_colophon_is_matched_from_INSIDE_the_word():
    """ಮಾಂಡೂಕ್ಯ + ಉಪನಿಷತ್ is written ಮಾಂಡೂಕ್ಯೋಪನಿಷತ್: the ಉ is swallowed.

    Searching for the literal ``ಉಪನಿಷ`` found nothing at all -- not one of
    the twenty-five colophons -- because every name ends in a vowel that
    takes the sandhi.  The same trap as ``धिकरणम्`` and ``ಸೂತ್ರಾರ್ಥ``.
    """
    for line in ("ಕೇನೋಪನಿಷತ್ತಮಾಪ್ತಿ",
                 "(ಹಂಸೋಪನಿಷತ್ ಸಮಾಪ್ತಾ)",
                 "ಮಾಂಡೂಕ್ಯೋಪನಿಷತ್ ಸಮಾಪ್ತಿ",
                 "(ಜಾಬಾಲೋಪನಿಷತ್ಮಾಪ್ರಾ)"):
        assert seg.is_colophon(line), line


def test_the_volumes_own_closing_line_is_not_an_upanishad_colophon():
    assert not seg.is_colophon("ಪ್ರಥಮ ಸಂಪುಟ ಸಮಾಪ್ತಿ")


# ---------------------------------------------------------------- headings

def test_a_mantra_promoted_to_section_title_is_not_a_heading():
    """Sarvam labelled a whole mantra ``section-title``, and it became the
    heading on all twelve units of Māṇḍūkya."""
    assert not seg.is_division(
        "ಮಂ.ಶ್ಲೋ.॥ ಗತಾಃ ಕಲಾಃ ಪಞ್ಚಾದಶ ಪ್ರತಿಷ್ಠಾ ದೇವಾಶ್ಚ ಸರ್ವೇ ॥ 7 (61)")
    assert not seg.is_division("ಮಂ.ಶ್ಲೋ.॥")


def test_the_veda_attribution_is_not_a_division():
    """It names the Upaniṣad, which sargaName already does."""
    assert not seg.is_division("(ಅಥರ್ವ ವೇದಾಂತರ್ಗತ)")


def test_a_real_khanda_heading_is_kept_verbatim():
    for line in ("ಪ್ರಥಮ ಖಂಡ",
                 "ದ್ವಿತೀಯ ಪ್ರಸಾರಕ - ಏಕೋಣನಿಂಶ ಖಂಡ",
                 "(ಪ್ರಥಮಾಧ್ಯಾಯ) 3ನೇ ವಲ್ಲಿ"):
        assert seg.is_division(line), line


# ------------------------------------------------------- the whole volume

def test_there_are_exactly_the_twenty_five_the_contents_lists(works):
    assert [w["name"] for w in works] == [c[0] for c in seg.CONTENTS]


def test_every_span_begins_where_the_printed_contents_says(works):
    """The scan runs three pages ahead of the book's own numbering, and all
    twenty-five spans land on their contents-page plus that offset.  This is
    what confirms the boundaries -- the śānti-mantra rule found them, the
    contents page agrees, and neither was derived from the other."""
    assert seg.check([{"units": w["units"]} for w in works]) == []


def test_the_counts_agree_with_what_these_upanishads_have(works):
    """Praśna 67, Māṇḍūkya 12, Aitareya 33, Īśā 18 -- reached independently,
    by cutting at śānti mantras and counting what is there.

    Where the edition prints its own running number, that is the figure to
    meet: Muṇḍaka is numbered to 65 here against the usual 64, and the
    sixty-fifth is the real closing mantra, not a stray.
    """
    for w in works:
        canon = seg.CANONICAL.get(w["name"])
        if canon is None:
            continue
        got = len(w["units"])
        printed = max([u["cum"] for u in w["units"] if u.get("cum")] or [0])
        target = printed or canon
        assert got <= target, f"{w['name']}: {got} exceeds {target}"
        assert got >= target - 2, f"{w['name']}: only {got} of {target}"


def test_the_running_numbers_never_go_backwards_inside_an_upanishad(works):
    """A span that had swallowed its neighbour would show the number
    restarting partway through -- which is exactly how the 187-span split
    was found."""
    for w in works:
        cums = [u["cum"] for u in w["units"] if u.get("cum")]
        assert cums == sorted(cums), w["slug"]


def test_the_header_fragments_are_gone(works):
    """``೧.``, ``೦.`` and ``ಂ.`` -- the running head, broken up."""
    for w in works:
        for u in w["units"]:
            assert len(u["mula"]) >= seg.MIN_MANTRA, (w["slug"], u["mula"])


def test_the_addressed_mantras_are_actually_MANTRA_shaped(works):
    """Counts alone do not validate.  A unit whose text is the Kannada gloss,
    or a heading, or nothing at all, would still count as one."""
    for w in works:
        for i, u in enumerate(w["units"], 1):
            where = f"{w['slug']} #{i}"
            assert u["mula"].strip(), f"{where}: empty"
            assert len(u["mula"]) >= 12, f"{where}: {u['mula']!r}"
            assert not seg.GLOSS.match(u["mula"]), f"{where}: this is the gloss"
            assert not seg.OPEN.match(u["mula"]), f"{where}: marker not stripped"


def test_a_heading_never_leaks_past_its_own_upanishad(works):
    """Aitareya's ``ತೃತೀಯಾಧ್ಯಾಯಃ`` was labelling the opening of Chāndogya."""
    first = {w["slug"]: w["units"][0].get("heading") for w in works}
    assert first["chandogya_upanishad"] != "ತೃತೀಯಾಧ್ಯಾಯಃ"


def test_most_mantras_carry_their_tatparya(works):
    total = sum(len(w["units"]) for w in works)
    glossed = sum(1 for w in works for u in w["units"] if u.get("tatparya"))
    assert total > 1250
    assert glossed / total > 0.95, f"{glossed}/{total}"


# ------------------------------------------------------------- the shelf

def test_the_shortfall_is_declared_in_words_not_left_to_be_noticed(works):
    """Sequential keys cannot carry a hole the way numbered ones can, so an
    Upaniṣad that is short of its own count has to say so.  Kena is 34 of
    35 and Kaṭha 118 of 120."""
    files = shelf.build(works)
    kena = files["kena_upanishad"]["metadata"]["source"]
    assert "35" in kena["extent"]
    assert "extent" not in files["prashna_upanishad"]["metadata"]["source"]


def test_every_upanishad_becomes_one_shelf_file_with_its_gloss(works):
    files = shelf.build(works)
    assert set(files) == {c[1] for c in seg.CONTENTS}
    for slug, payload in files.items():
        shlokas = payload["shlokas"]
        assert shlokas, slug
        # keys are 1..N with no gaps -- the reader assumes plain indices
        assert sorted(int(k) for k in shlokas) == list(range(1, len(shlokas) + 1))
        assert payload["metadata"]["totalShlokas"] == len(shlokas)
        assert any(v.get("commentaries") for v in shlokas.values()), slug


def test_no_provenance_reaches_the_shelf(works):
    """No source_url, no page numbers, no origin breadcrumb."""
    files = shelf.build(works)
    for slug, payload in files.items():
        src = payload["metadata"]["source"]
        assert "source_url" not in src and "url" not in src, slug
        blob = repr(payload)
        assert "http://" not in blob and "https://" not in blob, slug
