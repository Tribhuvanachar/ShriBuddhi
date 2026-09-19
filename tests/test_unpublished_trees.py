"""The trees that stay in ShriBuddhi, and the one way out of them.

These lock a decision, not an implementation: a work under DvaitaVedantaIn or
Anandamakaranda does not publish from where it sits, and the only way it goes
public is by moving into data/Tattvavada/. If someone later deletes the
exclusion or teaches a generator to ignore it, these fail.
"""
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from unpublished_trees import (PRIVATE_TREES, UNDECIDED_TREES,   # noqa: E402
                               is_unpublished, excludes_slug)
import promote_to_tattvavada as promote                          # noqa: E402


def test_the_two_trees_the_lead_named_are_the_ones_excluded():
    assert set(PRIVATE_TREES) == {
        "data/darshana/vedanta/dvaita/DvaitaVedantaIn",
        "data/darshana/vedanta/dvaita/Anandamakaranda",
    }


@pytest.mark.parametrize("path", [
    "data/darshana/vedanta/dvaita/DvaitaVedantaIn",
    "data/darshana/vedanta/dvaita/DvaitaVedantaIn/sutra_prasthana/x/mula/data.json",
    "./data/darshana/vedanta/dvaita/Anandamakaranda/dvadasha_stotra/mula/data.json",
])
def test_inside_a_private_tree(path):
    assert is_unpublished(path)


@pytest.mark.parametrize("path", [
    "data/Tattvavada/SarvaMula/sutra_prasthana/x/data.json",
    "data/darshana/vedanta/vishishtadvaita/RamanujaMeghamala/x/data.json",
    # A longer name that merely STARTS with an excluded one is a different
    # work. Substring matching would swallow it; segment matching must not.
    "data/darshana/vedanta/dvaita/DvaitaVedantaInternational/x/data.json",
    "data/darshana/vedanta/dvaita/Anandamakarandaka/x/data.json",
])
def test_outside_a_private_tree(path):
    assert not is_unpublished(path)


def test_slug_form_agrees_with_path_form():
    """library.json, the sitemap and the search index all carry the slug --
    the path with `data/` stripped. The two questions must not disagree."""
    for t in PRIVATE_TREES:
        assert excludes_slug(t[len("data/"):])


def test_undecided_trees_still_publish():
    """UNDECIDED_TREES is a list to report, not a second exclusion. Anything
    in it publishes exactly as it does today until the lead moves it up."""
    for t in UNDECIDED_TREES:
        assert not is_unpublished(t), (
            "%s is being excluded without having been classified" % t)


def test_sitemap_omits_every_private_tree():
    import build_sitemap
    for s, _ in build_sitemap.load_populated_granthas():
        assert not excludes_slug(s), "%s would be listed in sitemap.xml" % s


def test_publisher_ships_no_file_from_a_private_tree():
    import publish_clean_repo
    for _, rel in publish_clean_repo.walk(ROOT):
        assert not is_unpublished(rel), "%s would be published" % rel


def test_promotion_refuses_a_work_that_is_already_public():
    """The tool exists to move works OUT of the private trees. Pointed at
    anything else it must stop, not invent a second way to reshuffle the
    library."""
    with pytest.raises(SystemExit):
        promote.plan("data/Tattvavada/SarvaMula", "Itara", ROOT)


def test_promotion_lands_under_tattvavada_and_nowhere_else():
    p = promote.plan(
        "data/darshana/vedanta/dvaita/Anandamakaranda/dvadasha_stotra",
        "Itara/Stotra", ROOT)
    assert p["dest"].startswith("data/Tattvavada/")
    assert not is_unpublished(p["dest"])
    assert p["works"] > 0


def test_registry_report_runs():
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "unpublished_trees.py"),
                        "--root", ROOT], capture_output=True, text=True)
    assert r.returncode == 0
    assert "DvaitaVedantaIn" in r.stdout
