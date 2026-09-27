"""register_layers.py's item_count(), and why it must agree with audit_library's.

A leaf registered populated=false renders as "Not Available Yet". That is
indistinguishable from a text deliberately held back, so nothing downstream
ever flags it -- the same property that let a misspelt shelf path hide
maṇimañjarī's 306 verses.

item_count() here looked only at 'items'. The whole Kavya shelf is shaped
{metadata, shlokas: {"1": ..., "2": ...}} and the grantha_layer_v2 layers are
{schema, work, layer, units}, so both counted 0. Each function carried a comment
promising it was kept in sync with the other; the comments outlived the fact.
"""
import importlib.util
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rl = _load("register_layers", "tools/register_layers.py")
al = _load("audit_library", "tools/audit_library.py")


def test_the_kavya_shape_is_counted():
    """{metadata, shlokas: {...}} -- a dict keyed by verse number."""
    assert rl.item_count({"metadata": {}, "shlokas": {"1": {}, "2": {}}}) == 2


def test_the_grantha_layer_shape_is_counted():
    assert rl.item_count({"schema": "grantha_layer_v2", "units": [{}, {}, {}]}) == 3


def test_a_split_index_declares_its_own_total():
    """The index holds no units at this path, just a pointer to its parts."""
    assert rl.item_count(
        {"schema": "grantha_layer_v2_index", "parts": ["part-001.json"],
         "units_total": 27413}) == 27413


def test_nested_shlokas_lists_still_sum():
    assert rl.item_count({"items": [{"shlokas": [1, 2]}, {"shlokas": [3]}]}) == 3


def test_it_agrees_with_audit_library():
    """The canonical implementation. These two disagreeing is the bug."""
    for payload in (
        {"metadata": {}, "shlokas": {"1": {}, "2": {}}},
        {"schema": "grantha_layer_v2", "units": [{}, {}, {}]},
        {"schema": "grantha_layer_v2_index", "units_total": 99},
        {"items": [{"a": 1}, {"a": 2}]},
        {"compositions": {"x": 1}},
        {"entries": [1, 2, 3, 4]},
        {},
    ):
        assert rl.item_count(payload) == al.item_count(payload), payload


def test_a_real_kavya_leaf_counts_its_verses():
    f = REPO / "data/Tattvavada/Itara/Kavya/rukminisha_vijaya/sarga_1/data.json"
    if not f.is_file():
        import pytest
        pytest.skip("Rukminisha Vijaya not landed")
    d = json.loads(f.read_text(encoding="utf-8"))
    assert rl.item_count(d) == len(d["shlokas"]) > 0
    assert rl.title_of(d) == "Rugmiṇīśa Vijaya सर्गः 1"


def test_title_is_taken_from_metadata_not_left_null():
    """core.js falls back to the path when title is null, showing the reader a
    folder name like 'sarga_11' beside shelves that read 'Maṇimañjarī सर्गः 11'."""
    assert rl.title_of({"metadata": {"title": "X"}}) == "X"
    assert rl.title_of({"title": "Y"}) == "Y"
    assert rl.title_of({"metadata": {}}) is None
