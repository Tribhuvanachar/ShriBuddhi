"""Tests for tools/parabuddhi_stage.py — which corpus files go private.

The consequential test here is test_every_origin_in_the_corpus_is_classified.
This script decides what stays publishable, and the way that decision rots is
not a wrong answer today — it is a NEW importer six months from now whose site
is in neither list. If unknown sites silently fell through to "public", the
first symptom would be material nobody decided about sitting in a public
repository. So the script refuses, and this test walks the real corpus to make
that refusal fire here rather than there.
"""

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

import parabuddhi_stage as ps  # noqa: E402


def write(root: Path, rel: str, doc):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return p


def test_the_two_lists_do_not_overlap():
    assert not (set(ps.STAGED_SITES) & ps.PUBLIC_SITES), \
        "a site cannot be both staged and public"


def test_every_staged_site_carries_a_rights_line():
    for site, rights in ps.STAGED_SITES.items():
        assert isinstance(rights, str) and len(rights) > 20, \
            f"{site} needs a real rights line, not {rights!r}"


def test_every_origin_in_the_corpus_is_classified():
    """No file in the real corpus may come from an unclassified site."""
    _, _, unknown = ps.classify(ps.DATA)
    assert not unknown, (
        "these files come from a site in neither STAGED_SITES nor PUBLIC_SITES:\n"
        + "\n".join(f"  {site!r}  {rel}" for rel, site in unknown[:20])
    )


def test_the_named_unresolved_sources_are_staged():
    # The ones the registry flags as unresolved or case-by-case. Pinned by name
    # so removing one from the private tier has to be deliberate.
    for site in ("dvaitavedanta.in", "setutila.in", "anandamakaranda.in",
                 "advaitasharada.sringeri.net", "srivaishnavan.com"):
        assert site in ps.STAGED_SITES


def test_open_sources_stay_public():
    # Hiding public-domain and openly licensed material would cost content and
    # buy nothing. Pinned so a broad "stage everything" edit fails here.
    for site in ("gretil.sub.uni-goettingen.de", "sanskritdocuments.org",
                 "sa.wikisource.org", "archive.org", "github.com"):
        assert site in ps.PUBLIC_SITES


class TestOriginSite:
    def test_reads_the_per_unit_source_dict(self):
        assert ps.origin_site({"items": [{"source": {"site": "example.org"}}]}) == "example.org"

    def test_falls_back_to_the_top_level_url_as_a_hostname(self):
        assert ps.origin_site({"source_url": "https://example.org/a/b"}) == "example.org"

    def test_the_per_unit_dict_wins_over_the_top_level_url(self):
        # The importers write source.site consistently; source_url is sometimes
        # a section landing page rather than the record's own origin.
        doc = {"source_url": "https://landing.example/", "items": [{"source": {"site": "real.example"}}]}
        assert ps.origin_site(doc) == "real.example"

    def test_the_legacy_shloka_shape_is_read_too(self):
        doc = {"shlokas": {"1": {"source": {"site": "example.org"}}}}
        assert ps.origin_site(doc) == "example.org"

    def test_no_origin_mark_is_none_not_a_guess(self):
        assert ps.origin_site({"items": [{"sanskrit_text": "ॐ"}]}) is None
        assert ps.origin_site({}) is None
        assert ps.origin_site({"source_url": "not-a-url"}) is None


class TestClassify:
    def test_buckets_by_site(self, tmp_path):
        write(tmp_path, "a/data.json", {"items": [{"source": {"site": "dvaitavedanta.in"}}]})
        write(tmp_path, "b/data.json", {"items": [{"source": {"site": "gretil.sub.uni-goettingen.de"}}]})
        write(tmp_path, "c/data.json", {"items": [{"sanskrit_text": "ॐ"}]})
        staged, public, unknown = ps.classify(tmp_path)
        assert [r for r, _ in staged] == ["a/data.json"]
        assert sorted(r for r, _ in public) == ["b/data.json", "c/data.json"]
        assert unknown == []

    def test_an_unclassified_site_is_unknown_not_public(self, tmp_path):
        write(tmp_path, "x/data.json", {"items": [{"source": {"site": "brand-new-site.example"}}]})
        _, public, unknown = ps.classify(tmp_path)
        assert unknown == [("x/data.json", "brand-new-site.example")]
        assert public == []

    def test_generated_sidecars_are_skipped(self, tmp_path):
        write(tmp_path, "_references/data.json", {"items": [{"source": {"site": "dvaitavedanta.in"}}]})
        write(tmp_path, "_padaccheda/x/data.json", {"items": [{"source": {"site": "dvaitavedanta.in"}}]})
        staged, public, unknown = ps.classify(tmp_path)
        assert staged == [] and public == [] and unknown == []

    def test_an_unreadable_file_is_reported_not_silently_public(self, tmp_path):
        p = tmp_path / "bad" / "data.json"
        p.parent.mkdir(parents=True)
        p.write_text("{ this is not json", encoding="utf-8")
        _, public, unknown = ps.classify(tmp_path)
        assert len(unknown) == 1 and public == []


class TestStage:
    def test_reports_without_copying_by_default(self, tmp_path):
        src = tmp_path / "data"
        write(src, "a/data.json", {"items": [{"source": {"site": "setutila.in"}}]})
        dest = tmp_path / "dest"
        rows, total = ps.stage(ps.classify(src)[0], dest, root=src, apply=False)
        assert len(rows) == 1
        assert not dest.exists(), "a report must not create anything"

    def test_copies_under_source_slash_site_slash_original_path(self, tmp_path):
        src = tmp_path / "data"
        write(src, "deep/work/data.json", {"items": [{"source": {"site": "setutila.in"}}]})
        dest = tmp_path / "dest"
        rows, _ = ps.stage(ps.classify(src)[0], dest, root=src, apply=True, quiet=True)
        out = dest / "source" / "setutila.in" / "deep" / "work" / "data.json"
        assert out.exists()
        assert rows[0]["object"] == "source/setutila.in/deep/work/data.json"
        assert rows[0]["rights"] == ps.STAGED_SITES["setutila.in"]
        assert len(rows[0]["sha256"]) == 64

    def test_the_public_file_survives_staging(self, tmp_path):
        """Staging copies. It must never remove anything from the public tree."""
        src = tmp_path / "data"
        p = write(src, "a/data.json", {"items": [{"source": {"site": "setutila.in"}}]})
        before = p.read_bytes()
        ps.stage(ps.classify(src)[0], tmp_path / "dest", root=src, apply=True, quiet=True)
        assert p.exists() and p.read_bytes() == before

    def test_restaging_is_idempotent(self, tmp_path):
        src = tmp_path / "data"
        write(src, "a/data.json", {"items": [{"source": {"site": "setutila.in"}}]})
        dest = tmp_path / "dest"
        r1, _ = ps.stage(ps.classify(src)[0], dest, root=src, apply=True, quiet=True)
        r2, _ = ps.stage(ps.classify(src)[0], dest, root=src, apply=True, quiet=True)
        assert r1[0]["sha256"] == r2[0]["sha256"]

    def test_site_filter_stages_only_that_site(self, tmp_path):
        src = tmp_path / "data"
        write(src, "a/data.json", {"items": [{"source": {"site": "setutila.in"}}]})
        write(src, "b/data.json", {"items": [{"source": {"site": "dvaitavedanta.in"}}]})
        rows, _ = ps.stage(ps.classify(src)[0], tmp_path / "dest", root=src,
                           sites={"setutila.in"}, apply=True, quiet=True)
        assert [r["site"] for r in rows] == ["setutila.in"]


def test_main_refuses_on_an_unclassified_site(tmp_path, capsys):
    src = tmp_path / "data"
    write(src, "x/data.json", {"items": [{"source": {"site": "brand-new-site.example"}}]})
    rc = ps.main(["--data", str(src), "--dest", str(tmp_path / "d"), "--apply"])
    assert rc == 2, "an unclassified site must stop the run, not default to public"
    assert "brand-new-site.example" in capsys.readouterr().out
    assert not (tmp_path / "d").exists()
