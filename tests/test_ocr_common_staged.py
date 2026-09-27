"""tools/ocr_common/staged.py — the parts every staged-OCR segmenter needs.

Written after three works had each been able to make the same four mistakes.
These tests exist so the fourth work inherits the fix rather than the bug.
"""
import importlib.util
from pathlib import Path

MOD = Path(__file__).resolve().parents[1] / "tools/ocr_common/staged.py"
_spec = importlib.util.spec_from_file_location("ocr_staged", MOD)
S = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(S)


def nums(text, **kw):
    return [n for _, _, n in S.markers(text, **kw)]


def test_both_danda_forms_are_the_same_marker():
    """॥ is U+0965; ।। is two U+0964. The Veṅkaṭeśa Māhātmya writes 1,280 of
    its markers the first way and 584 the second, and matching only the first
    lost 31% of them silently — one adhyāya read as 44 verses instead of 215
    and merely looked like a part of the book with little commentary."""
    assert nums("क ॥ १२ ॥") == [12]
    assert nums("क ।। १२ ।।") == [12]
    assert "॥" != "।।" and len("।।") == 2


def test_digits_are_read_in_three_scripts():
    """A Kannada book's numbering looks like nothing at all to a
    Devanāgarī-only pattern."""
    assert nums("क ॥ ४१ ॥") == [41]      # Devanagari
    assert nums("ಕ ॥ ೪೧ ॥") == [41]      # Kannada
    assert nums("k ॥ 41 ॥") == [41]      # ASCII


def test_a_number_in_parentheses_is_a_citation():
    """(ಫಿಟ್ ಸೂತ್ರ-೮೫) cites the Phiṭ Sūtras. Counted as the book's own they
    turned one part into '1..87 with 58 gaps'."""
    assert nums("शेषं ॥ ५ ॥ (अन्यत्र ॥ ८७ ॥) अतः") == [5]
    assert nums("शेषं ॥ ५ ॥ (अन्यत्र ॥ ८७ ॥) अतः", skip_parenthesised=False) == [5, 87]


def test_a_closing_number_may_drop_its_last_danda():
    """...शरणं विरिञ्चम् ॥ ११ — 17 verses of Rukmiṇīśa Vijaya close that way."""
    assert S.closing_number("...विरिञ्चम् ॥ ११") == 11
    assert S.closing_number("...विरिञ्चम् ॥ ११ ॥") == 11
    assert S.closing_number("यथा ॥ ९ ॥ इत्युक्तम् अतः") is None, \
        "a number quoted mid-block does not close it"


def test_a_block_of_several_units_splits_at_its_markers():
    """p456 of the Veṅkaṭeśa Māhātmya carries verses 5 through 11 in one
    622-character block; only the last marker closes it."""
    text = " ".join(f"पाठोऽयमत्र वर्तते दीर्घः ॥ {n} ॥" for n in ("१", "२", "३"))
    pieces = S.split_at_markers(text)
    assert pieces is not None and len(pieces) == 3
    assert all("पाठोऽयमत्र" in p for p in pieces)


def test_a_block_that_does_not_split_into_unit_shapes_is_left_whole():
    """Refusing is the point: a block whose pieces are not unit-shaped is not a
    run of units, and cutting it would invent addressing."""
    assert S.split_at_markers("क ॥ १ ॥") is None          # one marker, at the end
    assert S.split_at_markers("क" * 900 + " ॥ १ ॥ " + "ख" * 900) is None


def test_a_number_far_below_the_running_maximum_is_a_quotation():
    """The Pāṣaṇḍakhaṇḍana quotes verses 13 and 17 again on pages 37 and 39,
    in a run that has reached 92 and 96 and goes on rising."""
    assert S.is_quotation(13, 92)
    assert not S.is_quotation(93, 92)
    assert not S.is_quotation(92, 92), "a verse and its gloss share a number"


def test_page_report_names_the_gaps():
    assert S.page_report({1: "a", 3: "b"}) == {
        "pages": 2, "page_range": [1, 3], "page_gaps": [2]}
    assert S.page_report({})["pages"] == 0
