"""Tests for fold_tiny_layers.py — the post-extract repair that merges
numbered chunks of one commentary into a single layer and folds one-off
topic headings into the enclosing layer (run 33543273107 minted 1,255
such folders across the corpus)."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from fold_tiny_layers import (  # noqa: E402
    item_id_key, reliable_author, strip_digits,
)


def w(root: Path, layer: str, doc: dict) -> None:
    d = root / layer
    d.mkdir(parents=True, exist_ok=True)
    (d / "data.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")


def r(root: Path, layer: str) -> dict:
    return json.loads((root / layer / "data.json").read_text(
        encoding="utf-8"))


def item(n: int, text: str = "पाठः", title: str = "", **extra) -> dict:
    it = {"id": f"DV_{n}", "sanskrit_text": text, "unit_title": title}
    it.update(extra)
    return it


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    root = tmp_path / "DvaitaVedanta" / "later_acharyas" / "parva"
    w(root, "mula", {"schema": "grantha_mula_text",
                     "default_author": "श्रीमदाचार्यः",
                     "items": [item(100), item(200), item(300)]})
    return root


def run_tool(tmp_path: Path, threshold: int = 3) -> str:
    out = subprocess.run(
        [sys.executable, str(HERE / "fold_tiny_layers.py"),
         "--data", str(tmp_path / "DvaitaVedanta"),
         "--config", str(HERE / "dv_sources.json"),
         "--threshold", str(threshold)],
        capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return out.stdout


def test_numbered_chunks_merge_into_one_layer(tree, tmp_path):
    # chunk 1 carries an "author" capture, chunks 2-3 arrive bare —
    # the whole family still merges, ordered by content id, authorless
    w(tree, "tika_1_bhavapradipa",
      {"schema": "grantha_tika_text",
       "default_author": "( १) भगवन्तरायकृतभावप्रदीपः",
       "items": [item(110, "प्रथमः")]})
    w(tree, "tika_2_bhavapradipa",
      {"schema": "grantha_tika_text", "default_author": "",
       "items": [item(210, "द्वितीयः")]})
    w(tree, "tika_3_bhavapradipa",
      {"schema": "grantha_tika_text", "default_author": "",
       "items": [item(310, "तृतीयः")]})
    w(tree, "tika_4_bhavapradipa",
      {"schema": "grantha_tika_text", "default_author": "",
       "items": [item(410, "चतुर्थः")]})
    run_tool(tmp_path)
    merged = r(tree, "tika_bhavapradipa")
    assert [i["id"] for i in merged["items"]] == [
        "DV_110", "DV_210", "DV_310", "DV_410"]
    assert not (merged.get("default_author") or "").strip()
    assert not (tree / "tika_1_bhavapradipa").exists()


def test_rare_heading_folds_into_enclosing_item(tree, tmp_path):
    w(tree, "tika_yavadadhikaranam_15",
      {"schema": "grantha_tika_text", "default_author": "",
       "items": [item(250, "॥ सूत्रम् ॥", tika_title="यावदधिकरणम् - १५",
                      source_html="<p class=\"shloka\">सूत्रम्</p>")]})
    run_tool(tmp_path)
    assert not (tree / "tika_yavadadhikaranam_15").exists()
    mula = r(tree, "mula")
    # folds into the item with the nearest smaller id (DV_200)
    target = mula["items"][1]
    assert "यावदधिकरणम् - १५" in target["sanskrit_text"]
    assert "॥ सूत्रम् ॥" in target["sanskrit_text"]
    assert target.get("source_html")  # carried when the target had none


def test_orphan_before_all_ids_becomes_mula_item(tree, tmp_path):
    w(tree, "tika_mangala",
      {"schema": "grantha_tika_text", "default_author": "",
       "items": [item(50, "मङ्गलम्", tika_title="मङ्गलाचरणम्")]})
    run_tool(tmp_path)
    mula = r(tree, "mula")
    assert mula["items"][0]["id"] == "DV_50"
    assert mula["items"][0]["unit_title"] == "मङ्गलाचरणम्"
    assert "tika_title" not in mula["items"][0]


def test_attributed_and_large_layers_survive(tree, tmp_path):
    w(tree, "tika_panchika",
      {"schema": "grantha_tika_text",
       "default_author": "श्रीजयतीर्थविरचिता",
       "items": [item(120)]})
    w(tree, "tika_khandartha",
      {"schema": "grantha_tika_text", "default_author": "",
       "items": [item(130), item(230), item(330), item(340)]})
    run_tool(tmp_path)
    assert (tree / "tika_panchika").exists()
    assert (tree / "tika_khandartha").exists()
    assert len(r(tree, "mula")["items"]) == 3


def test_garbage_author_does_not_shield(tree, tmp_path):
    # '८.' / '१३. प्र' style captures are not real attributions
    w(tree, "tika_8",
      {"schema": "grantha_tika_text", "default_author": "८.",
       "items": [item(150, "अष्टमखण्डः")]})
    run_tool(tmp_path)
    assert not (tree / "tika_8").exists()


def test_helpers():
    assert strip_digits("tika_23_kashitimmannacarya") == \
        "tika_kashitimmannacarya"
    assert strip_digits("tika_ramasubba_141") == "tika_ramasubba"
    assert strip_digits("tika_8") == "tika"
    assert reliable_author("श्रीजयतीर्थः")
    assert not reliable_author("८.")
    assert not reliable_author("१३. प्र")
    assert not reliable_author("")
    assert item_id_key({"id": "DV_19355"}) == 19355
    assert item_id_key({"id": ""}) == -1
