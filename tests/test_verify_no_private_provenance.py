"""Tests for tools/verify_no_private_provenance.py — the public-repo guard.

This is the last line: whatever the pipeline did or did not strip, this scans
the files a visitor can actually fetch. So the tests are about what it CATCHES,
including the cases no strip list anticipated.
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

import verify_no_private_provenance as g  # noqa: E402


def write(root: Path, rel: str, doc):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")


class TestScan:
    def test_catches_an_origin_host_anywhere(self):
        assert g.scan({"source_url": "https://dvaitavedanta.in/x"})
        assert g.scan({"a": {"b": ["https://setutila.in/y"]}})

    def test_catches_an_origin_record_id(self):
        assert g.scan({"id": "DV_14063"})
        assert g.scan({"note": "article5631"})

    def test_catches_a_structural_origin_field_by_name(self):
        for k in ("source_html", "content_id", "work_id", "block_uuid", "oldKey"):
            assert g.scan({"items": [{k: "anything"}]}), k

    def test_catches_a_key_named_after_a_source(self):
        assert g.scan({"readings": {"setutila": "-"}})

    def test_leaves_clean_published_content_alone(self):
        clean = {"schema": "grantha", "items": [
            {"id": 1, "sanskrit_text": "ॐ॥ य इज्यते", "section": "मूलम्", "tags": ["x"]}]}
        assert g.scan(clean) == []

    def test_ordinary_prose_is_not_flagged(self):
        # A scanner that cries wolf is a scanner nobody reads.
        assert g.scan({"notes": "a study of the upanishat literature"}) == []

    def test_reports_where_so_it_can_be_fixed(self):
        found = g.scan({"items": [{"deep": {"u": "https://srivaishnavan.com/a"}}]})
        assert any("items[0].deep.u" in p for p, _ in found)


class TestMain:
    def test_clean_corpus_passes(self, tmp_path, capsys):
        write(tmp_path, "a/data.json", {"items": [{"id": 1, "sanskrit_text": "ॐ"}]})
        assert g.main(["--data", str(tmp_path)]) == 0
        assert "no private-source fingerprints" in capsys.readouterr().out

    def test_a_single_fingerprint_fails_the_run(self, tmp_path, capsys):
        write(tmp_path, "a/data.json", {"items": [{"id": 1, "sanskrit_text": "ॐ"}]})
        write(tmp_path, "b/data.json", {"source_url": "https://dvaitavedanta.in/x", "items": []})
        assert g.main(["--data", str(tmp_path)]) == 1
        out = capsys.readouterr().out
        assert "b/data.json" in out
        assert "Parabuddhi" in out, "the message must say where to publish from"

    def test_generated_sidecars_are_not_scanned(self, tmp_path):
        # _references and friends are built from the corpus, not imported, and
        # a token-range sidecar has no provenance of its own.
        write(tmp_path, "_references/x/data.json", {"a": "https://setutila.in/x"})
        assert g.main(["--data", str(tmp_path), "--quiet"]) == 0

    def test_a_missing_corpus_is_not_an_error(self, tmp_path):
        assert g.main(["--data", str(tmp_path / "nope")]) == 0

    def test_unparseable_json_does_not_crash_the_scan(self, tmp_path):
        p = tmp_path / "bad" / "data.json"
        p.parent.mkdir(parents=True)
        p.write_text("{ not json", encoding="utf-8")
        assert g.main(["--data", str(tmp_path), "--quiet"]) == 0


def test_the_site_list_matches_parabuddhis():
    """Both repos hold this list; they must not drift.

    The private repo is not checked out when this runs, so the list is a
    literal here. Pinned by name so adding a source in one place and not the
    other fails rather than silently narrowing the guard.
    """
    assert set(g.PRIVATE_SITES) == {
        "dvaitavedanta.in", "srivaishnavan.com", "advaitasharada.sringeri.net",
        "setutila.in", "anandamakaranda.in", "upanishat.com",
        "tirthaprabandha.wordpress.com", "srimadhvyasa.wordpress.com",
    }


def test_the_importers_are_disabled_in_this_repo():
    """Every importer of a private source must refuse to run here."""
    import yaml
    for w in ("extract-dvaitavedanta", "extract-setutila", "sync-anandamakaranda",
              "sync-advaitasharada", "sync-meghamala"):
        p = REPO / ".github" / "workflows" / f"{w}.yml"
        d = yaml.safe_load(p.read_text(encoding="utf-8"))
        first = list(d["jobs"].values())[0]["steps"][0]
        assert "disabled" in first["name"].lower(), f"{w} must fail before it fetches"
        assert "exit 1" in first["run"], f"{w}'s guard must actually fail"
