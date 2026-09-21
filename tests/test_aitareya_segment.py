"""tools/aitareya/segment.py rests on two measured claims. Guard both.

The first is that bhagavantaraya interleaves two separately-paginated
streams on a strict parity: the bhasya stream on odd PDF pages, the
Bhavapradipa tippani with its own "आ-२, अ-१, खं-१" address on even ones.
Every block the segmenter produces for that volume depends on it, and if a
future re-OCR shifts the page offset by one the rule silently attaches the
wrong text to every khanda -- silently, because the output would still look
well-formed. So the parity is asserted, not assumed.

The second is that ratnamala's blocks can be addressed by matching its own
भाष्यम् runs against the shelf's tika_bhashya, which states the address.
The check that this works is not that blocks come out addressed -- they
would, from any matcher, including a broken one -- but that the addresses
come out in the order the printed volume runs in. Nothing in the matcher
constrains that; each block is matched independently. Monotonicity is
therefore evidence, and a regression in it is a real failure.

These read the staging branches, so they skip rather than fail when the
refs are not present (a shallow clone, a fresh checkout).
"""
import importlib.util
import json
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MOD = ROOT / "tools/aitareya/segment.py"


def load():
    spec = importlib.util.spec_from_file_location("aitareya_segment", MOD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


seg = load()


def have_branch(name):
    out = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--verify", "-q", name],
                         capture_output=True, text=True)
    return out.returncode == 0


needs_staging = pytest.mark.skipif(
    not have_branch(seg.VOLUMES["ratnamala"]["branch"]),
    reason="ocr-staging refs not present in this clone")


def test_the_label_convention_the_other_pipeline_uses_is_absent():
    """build_verify.py keys off "वे.श्रुत्यर्थः-" style labels at line start.
    If a future edition of these volumes did carry them, that pipeline
    would be the right tool and this one redundant -- so record that they
    do not, which is why this module exists at all."""
    LABEL = re.compile(r"^\s*((?:[ऀ-ॿ]{1,7}\.){1,3}"
                       r"(?:[ऀ-ॿ]{1,12})?[ः:]?)\s*[-–—:]+\s*")
    sample = "टिप्पणी -\nस एष इति ॥ गरणदर्शनश्रोतृत्वादिकं\nभाष्यम्-\nस एष भगवान् गिरिः ।"
    assert not any(LABEL.match(l) for l in sample.split("\n"))
    # but this module's own SECTION rule does find the labels it relies on
    found = [l.strip() for l in sample.split("\n") if seg.SECTION.match(l.strip())]
    assert "टिप्पणी -" in found or "भाष्यम्-" in found


def test_section_rule_ignores_prose_containing_a_dash():
    """SECTION is anchored to the whole line precisely so that ordinary
    commentary prose, which is full of dashes, cannot open a false layer."""
    prose = "इदानीं 'तमिन्द्र उवाच' इत्यादिकं व्याचष्टे- तस्मा इति ।।"
    assert seg.SECTION.match(prose) is None


def test_known_sections_are_shelf_layer_names():
    shelf = {d.name for d in seg.TARGET.iterdir() if d.is_dir()}
    mapped = set(seg.KNOWN_SECTIONS.values())
    # the two the shelf already has must map onto it exactly
    assert {"tika_bhashya", "tika_upanishat"} <= mapped
    assert {"tika_bhashya", "tika_upanishat"} <= shelf


@needs_staging
def test_bhagavantaraya_stream_parity_is_strict():
    pages = seg.load_pages("bhagavantaraya")
    odd_bhashya = even_bhashya = odd_coord = even_coord = 0
    for p in pages:
        head = " ".join(p["text"].split())[:120]
        if seg.BHASHYA_HEAD.search(head):
            if p["page"] % 2: odd_bhashya += 1
            else: even_bhashya += 1
        elif seg.COORD.search(head):
            if p["page"] % 2: odd_coord += 1
            else: even_coord += 1
    assert odd_bhashya > 300 and even_bhashya == 0, (
        f"bhasya stream is no longer odd-only: {odd_bhashya} odd, {even_bhashya} even")
    assert even_coord > 300 and odd_coord == 0, (
        f"addressed stream is no longer even-only: {even_coord} even, {odd_coord} odd")


@needs_staging
def test_ratnamala_addresses_come_out_in_volume_order():
    pages = seg.load_pages("ratnamala")
    blocks, _ = seg.segment_section_labels(pages, seg.VOLUMES["ratnamala"])
    seg.address_by_bhashya(blocks)

    order, rank = [], {}
    for x in json.loads((seg.TARGET / "tika_bhashya/data.json").read_text())["items"]:
        a = tuple(x["reference"].split(" > ")[3:6])
        if len(a) == 3 and a not in rank:
            rank[a] = len(order); order.append(a)

    seen = []
    for b in blocks:
        if b.get("adhyaya_name"):
            a = (b["aranyaka_name"], b["adhyaya_name"], b["khanda_name"])
            if not seen or seen[-1] != a:
                seen.append(a)
    assert len(seen) >= 25, f"only {len(seen)} distinct addresses -- matching regressed"
    ranks = [rank[a] for a in seen if a in rank]
    backwards = [(ranks[i - 1], ranks[i]) for i in range(1, len(ranks)) if ranks[i] < ranks[i - 1]]
    assert not backwards, (
        "addresses no longer run in the volume's own order, so the matcher is "
        f"attaching text to the wrong khanda: {backwards[:5]}")


@needs_staging
def test_unmatched_blocks_are_left_unaddressed_not_guessed():
    """A block that matches nothing must keep no address rather than take
    a plausible one: an unaddressed block is reviewable, a wrongly
    addressed one reads as correct."""
    blocks = [{"layer": "tika_bhashya", "page": 1, "text": "इदम् अत्यन्तम् असम्बद्धम् " * 30}]
    stats = seg.address_by_bhashya(blocks)
    assert blocks[0].get("adhyaya_name") is None
    assert stats.get("unaddressed") == 1
