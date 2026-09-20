"""The trees that stay in ShriBuddhi, and the one way out of them.

These lock a decision, not an implementation: a work under DvaitaVedantaIn or
Anandamakaranda does not publish from where it sits, and the only way it goes
public is by moving into data/Tattvavada/. If someone later deletes the
exclusion or teaches a generator to ignore it, these fail.
"""
import json
import os
import re
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from unpublished_trees import (PRIVATE_TREES, UNDECIDED_TREES,   # noqa: E402
                               is_unpublished, excludes_slug)
import promote_to_tattvavada as promote                          # noqa: E402


def test_the_three_source_named_trees_are_the_private_ones():
    """Started as two. RamanujaMeghamala was held back while the rule was
    "does not publish at all", because excluding it would have retired 175
    live URLs nobody asked to retire. Under ids nothing is retired -- the
    text stays published and searchable and only the shelf changes -- so the
    reason to hold it back went away with the exclusion."""
    assert set(PRIVATE_TREES) == {
        "data/darshana/vedanta/dvaita/DvaitaVedantaIn",
        "data/darshana/vedanta/dvaita/Anandamakaranda",
        "data/darshana/vedanta/vishishtadvaita/RamanujaMeghamala",
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


def test_nothing_is_left_undecided():
    """The list existed to surface a tree named after a source website that
    nobody had ruled on. There are none left."""
    assert UNDECIDED_TREES == ()


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


# --- opaque ids: publish the text, withhold the shelf ------------------------

import opaque_ids                                                # noqa: E402


def test_the_id_map_never_publishes():
    """It lives under admin/, which publish_clean_repo excludes. If it ever
    moves, the whole scheme is pointless -- the map IS the secret."""
    import publish_clean_repo
    assert opaque_ids.MAP_PATH.split(os.sep)[0] in publish_clean_repo.EXCLUDE_DIRS


def test_every_structure_private_work_has_an_id():
    assert check_problems() == []


def check_problems():
    return opaque_ids.check(ROOT)


def test_ids_are_not_derived_from_the_path():
    """Minting must not be a function of anything. The source websites
    publish their own structure, so a hash of a path is invertible by anyone
    holding their sitemap -- hash every candidate, compare, done."""
    assert len({opaque_ids.mint() for _ in range(200)}) == 200


def test_id_alphabet_avoids_confusable_letters():
    for c in "ILOU":
        assert c not in opaque_ids.ALPHABET


def test_minting_is_idempotent_and_never_reissues():
    """A published id is a link someone may hold. Re-minting must add
    nothing and change nothing."""
    before = opaque_ids.load(ROOT)["by_path"].copy()
    after = opaque_ids.load(ROOT)["by_path"]
    assert before == after and len(before) > 0


def test_tattvavada_keeps_its_readable_path():
    """Our own structure names nobody, so it is not hidden behind an id."""
    assert not opaque_ids.needs_id("data/Tattvavada/Itara/Kavya/raghavendra_vijaya")
    assert not opaque_ids.needs_id_slug("Tattvavada/SarvaMula/sutra_prasthana")


# --- the publish-time rewrite ------------------------------------------------

import publish_opaque_rewrite as R                              # noqa: E402


def test_the_two_registries_are_one_list():
    """unpublished_trees used to keep its own copy. Two lists that must agree
    are one list and a bug waiting for a quiet afternoon."""
    assert tuple(PRIVATE_TREES) == tuple(opaque_ids.STRUCTURE_PRIVATE)


def test_longest_slug_is_rewritten_first():
    """A work and the shelf above it are both in the map. Replace the shelf
    first and the work's tail dangles behind the id -- `id:xxx/mula`, which
    still shows a shelf."""
    keys = list(R.build_map(ROOT))
    assert keys == sorted(keys, key=lambda k: -len(k))


def test_a_private_slug_becomes_an_id():
    m = R.build_map(ROOT)
    slug = "darshana/vedanta/dvaita/DvaitaVedantaIn/dasha_prakarana_granthas/karma_nirnaya/mula"
    out, n = R.rewrite_text('{"g": "%s"}' % slug, m)
    assert n >= 1 and "DvaitaVedantaIn" not in out and R.ID_PREFIX in out


def test_the_flattened_form_is_rewritten_too():
    """Shard filenames and sidecar keys spell a slug with `__`. Missing that
    form leaves the manifest pointing at files rename_shards has moved."""
    m = R.build_map(ROOT)
    slug = "darshana/vedanta/dvaita/DvaitaVedantaIn/dasha_prakarana_granthas/karma_nirnaya/mula"
    out, n = R.rewrite_text("units/%s.json" % slug.replace("/", "__"), m)
    assert n >= 1 and "DvaitaVedantaIn" not in out


def test_a_public_slug_is_left_alone():
    m = R.build_map(ROOT)
    out, n = R.rewrite_text('{"g": "Tattvavada/Itara/Kavya/raghavendra_vijaya"}', m)
    assert n == 0 and "Tattvavada/Itara/Kavya/raghavendra_vijaya" in out


def test_taxonomy_pruning_removes_the_whole_subtree(tmp_path):
    """Replacing the KEY would leave every level beneath it standing, and
    those levels are the shelf."""
    p = tmp_path / "taxonomy.json"
    p.write_text(json.dumps({"darshana": {"vedanta": {"dvaita": {
        "DvaitaVedantaIn": {"dasha_prakarana_granthas": {"karma_nirnaya": {}}},
        "SarvaMula": {"sutra_prasthana": {}}}}}}), encoding="utf-8")
    assert R.prune_taxonomy(str(p)) == 1
    text = p.read_text(encoding="utf-8")
    assert "DvaitaVedantaIn" not in text
    assert "dasha_prakarana_granthas" not in text
    assert "SarvaMula" in text


def test_private_names_js_never_publishes():
    import publish_clean_repo
    import fnmatch
    assert any(fnmatch.fnmatch("private-names.js", g)
               for g in publish_clean_repo.EXCLUDE_GLOBS)


def test_no_published_js_names_a_private_tree():
    """js/ ships. Two files used to carry these names inline -- a breadcrumb
    label map and a folder-name lint allowlist -- neither of which a public
    page can use."""
    import publish_clean_repo as P
    names = [t.rsplit("/", 1)[-1] for t in PRIVATE_TREES]
    bad = []
    for full, rel in P.walk(ROOT):
        if not rel.startswith("js/") or not rel.endswith(".js"):
            continue
        text = open(full, encoding="utf-8", errors="replace").read()
        # A full slug is rewritten at publish time; a BARE name is not.
        for n in names:
            for hit in re.finditer(re.escape(n), text):
                before = text[max(0, hit.start() - 40):hit.start()]
                if "darshana/" not in before and "vishishtadvaita/" not in before:
                    bad.append((rel, n))
                    break
    assert bad == [], "bare private names in published js: %s" % bad[:5]


def test_the_id_map_is_not_in_the_published_config_allowlist():
    """The published site pulls a handful of files out of admin/config/ --
    home.json, menu.json, seo.json -- and js/admin-remote.js's
    LEGACY_PUBLIC_CONFIG is the list of which. opaque_ids.json in that list
    would put the whole id-to-path map on the public site, and every id would
    resolve to its real path for anybody who asked.

    Found by doing the naive thing while smoke-testing: copying
    admin/config/*.json into the staged site's config/ takes the map along.
    """
    src = open(os.path.join(ROOT, "js", "admin-remote.js"), encoding="utf-8").read()
    m = re.search(r"var LEGACY_PUBLIC_CONFIG = \[(.*?)\];", src, re.S)
    assert m, "LEGACY_PUBLIC_CONFIG not found -- has admin-remote.js moved?"
    names = [x.strip().strip("'\"") for x in m.group(1).replace("\n", " ").split(",") if x.strip()]
    assert names, "the allowlist parsed empty"
    assert os.path.basename(opaque_ids.MAP_PATH) not in names


def test_the_rewriter_refuses_a_staged_tree_holding_the_map(tmp_path):
    import subprocess
    site = tmp_path / "site"
    (site / "config").mkdir(parents=True)
    (site / "config" / "opaque_ids.json").write_text(
        json.dumps({"by_id": {"abc": "data/x"}, "by_path": {"data/x": "abc"}}), encoding="utf-8")
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "publish_opaque_rewrite.py"),
                        "--staged", str(site), "--root", ROOT],
                       capture_output=True, text=True)
    assert r.returncode != 0
    assert "id-to-path map" in r.stdout
