"""land_proofread.py exists to rescue paid work from a run whose push failed.
Its whole value is that it refuses to guess: a donor block that is not
demonstrably the same block must not overwrite anything.

The three ways it could silently corrupt the staging files:

  * merging by position when the files have drifted apart;
  * overwriting a proofread this repo already has with the donor's;
  * writing the donor's correction onto a block whose raw text differs,
    which means the donor was proofreading something else.
"""
import importlib.util
import json
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "tools" / "aitareya" / "land_proofread.py"
_spec = importlib.util.spec_from_file_location("land_proofread", TOOL)
land = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(land)


def block(page, text, proofread=None):
    b = {"aranyaka": 1, "adhyaya": 2, "khanda": 3, "page": page,
         "layer": "mula", "text": text}
    if proofread is not None:
        b["text_proofread"] = proofread
    return b


def test_lands_a_correction_onto_the_matching_block():
    local = {"blocks": [block(7, "क्ष्ठ")]}
    donor = {"blocks": [block(7, "क्ष्ठ", "कष्ट")]}
    blocks, st = land.merge_file(local, donor)
    assert blocks[0]["text_proofread"] == "कष्ट"
    assert st["landed"] == 1 and st["mismatch"] == 0


def test_leaves_the_raw_text_alone():
    local = {"blocks": [block(7, "क्ष्ठ")]}
    donor = {"blocks": [block(7, "क्ष्ठ", "कष्ट")]}
    blocks, _ = land.merge_file(local, donor)
    assert blocks[0]["text"] == "क्ष्ठ"


def test_refuses_when_the_block_counts_differ():
    local = {"blocks": [block(7, "a"), block(8, "b")]}
    donor = {"blocks": [block(7, "a", "A")]}
    blocks, st = land.merge_file(local, donor)
    assert st["count_mismatch"] == 1
    assert st["landed"] == 0
    assert blocks == local["blocks"]


def test_refuses_a_donor_whose_raw_text_drifted():
    local = {"blocks": [block(7, "this page")]}
    donor = {"blocks": [block(7, "a different page", "CORRECTED")]}
    blocks, st = land.merge_file(local, donor)
    assert "text_proofread" not in blocks[0]
    assert st["mismatch"] == 1 and st["landed"] == 0


def test_refuses_a_donor_whose_address_drifted():
    local = {"blocks": [block(7, "same text")]}
    d = block(7, "same text", "CORRECTED")
    d["khanda"] = 99
    blocks, st = land.merge_file(local, {"blocks": [d]})
    assert "text_proofread" not in blocks[0]
    assert st["mismatch"] == 1


def test_never_overwrites_a_proofread_this_repo_already_has():
    local = {"blocks": [block(7, "raw", "ours")]}
    donor = {"blocks": [block(7, "raw", "theirs")]}
    blocks, st = land.merge_file(local, donor)
    assert blocks[0]["text_proofread"] == "ours"
    assert st["already"] == 1 and st["landed"] == 0


def test_a_donor_block_with_no_correction_is_not_an_error():
    local = {"blocks": [block(7, "raw")]}
    donor = {"blocks": [block(7, "raw")]}
    blocks, st = land.merge_file(local, donor)
    assert "text_proofread" not in blocks[0]
    assert st["donor_blank"] == 1 and st["mismatch"] == 0


def test_dry_run_writes_nothing(tmp_path):
    staged = tmp_path / "staged"
    staged.mkdir()
    src = tmp_path / "artifact"
    src.mkdir()
    payload = {"blocks": [block(7, "raw")]}
    (staged / "x_segmented.json").write_text(json.dumps(payload), encoding="utf-8")
    (src / "x_segmented.json").write_text(
        json.dumps({"blocks": [block(7, "raw", "CORRECTED")]}), encoding="utf-8")

    land.main(["--from", str(src), "--staged-dir", str(staged)])
    after = json.loads((staged / "x_segmented.json").read_text(encoding="utf-8"))
    assert "text_proofread" not in after["blocks"][0]

    land.main(["--from", str(src), "--staged-dir", str(staged), "--write"])
    after = json.loads((staged / "x_segmented.json").read_text(encoding="utf-8"))
    assert after["blocks"][0]["text_proofread"] == "CORRECTED"


def test_keeps_the_file_s_own_indentation(tmp_path):
    """Re-serialising a 15,000-line staging file at the wrong indent rewrites
    every line and hides the 825 that actually changed."""
    staged, src = tmp_path / "staged", tmp_path / "artifact"
    staged.mkdir(), src.mkdir()
    payload = json.dumps({"blocks": [block(7, "raw")]}, ensure_ascii=False, indent=1)
    (staged / "x_segmented.json").write_text(payload + "\n", encoding="utf-8")
    (src / "x_segmented.json").write_text(
        json.dumps({"blocks": [block(7, "raw", "CORRECTED")]}), encoding="utf-8")

    land.main(["--from", str(src), "--staged-dir", str(staged), "--write"])
    after = (staged / "x_segmented.json").read_text(encoding="utf-8")
    assert after.split("\n")[1].startswith(' "blocks"'), after.split("\n")[1]


def test_indent_of_reads_the_file_not_the_default():
    assert land.indent_of('{\n  "a": 1\n}\n') == 2
    assert land.indent_of('{\n "a": 1\n}\n') == 1
    assert land.indent_of('{"a": 1}') == 1  # one line, nothing to read
