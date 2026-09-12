import importlib.util, json, pathlib, sys

import pytest

# The exporter pulls in numpy and soundfile (audio I/O). CI and most laptops
# do not have them; the crossmatch logic is what this file tests, so skip
# cleanly instead of failing pytest's collection for the whole suite.
pytest.importorskip("numpy")
pytest.importorskip("soundfile")

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "kamadhenu" / "training"))
import verify_pilot_transcripts as v  # noqa: E402
import export_f5_dataset as e  # noqa: E402

UNITS = [
    {"text_id": "w:V1", "text": "अग्निमीळे पुरोहितं यज्ञस्य देवमृत्विजम् होतारं रत्नधातमम्"},
    {"text_id": "w:V2", "text": "अग्निः पूर्वेभिर्ऋषिभिरीड्यो नूतनैरुत स देवाँ एह वक्षति"},
    {"text_id": "w:V3", "text": "अग्निना रयिमश्नवत्पोषमेव दिवेदिवे यशसं वीरवत्तमम्"},
    {"text_id": "x:V1", "text": "धर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः मामकाः पाण्डवाश्चैव किमकुर्वत सञ्जय"},
]


def test_crossmatch_confirms_remaps_and_gives_up():
    rows = [
        {"id": "a", "text_id": "w:V1", "asr": "agnimīḷe purohitaṁ yajñasya devam ṛtvijam hotāraṁ ratnadhātamam", "verdict": "ok"},
        {"id": "b", "text_id": "w:V1", "asr": "agniḥ pūrvebhir ṛṣibhir īḍyo nūtanair uta sa devāṁ eha vakṣati", "verdict": "ok"},
        {"id": "c", "text_id": "w:V3", "asr": "Ṭ Ṭ Ṭ Ṭ Ṭ", "verdict": "suspect_repetition"},
        {"id": "d", "text_id": "x:V1", "asr": "dharmakṣetre kurukṣetre samavetā yuyutsavaḥ", "verdict": "ok"},
    ]
    out = {r["id"]: r for r in v.crossmatch(rows, UNITS)}
    assert out["a"]["decision"] == "confirmed" and out["a"]["heard"] == "w:V1"
    assert out["b"]["decision"] == "remap" and out["b"]["heard"] == "w:V2" and out["b"]["heard_text"].startswith("अग्निः")
    assert out["c"]["decision"] == "inconclusive"
    assert out["d"]["decision"] == "confirmed"          # pool is the recording's own work only


def test_export_gate_reads_crossmatch_and_optionally_remaps(tmp_path):
    rows = [{"id": "a", "text_id": "w:V1", "asr": "agnimīḷe purohitaṁ yajñasya devam ṛtvijam hotāraṁ ratnadhātamam"},
            {"id": "b", "text_id": "w:V1", "asr": "agniḥ pūrvebhir ṛṣibhir īḍyo nūtanair uta sa devāṁ eha vakṣati"},
            {"id": "c", "text_id": "w:V3", "asr": "Ṭ Ṭ Ṭ"}]
    rep = v.write_crossmatch(v.crossmatch(rows, UNITS), tmp_path, "test")
    assert (tmp_path / "crossmatch.md").exists() and rep["decisions"]["remap"] == 1
    verdicts = e.verified_ids(tmp_path / "crossmatch.json")
    pilot = [{"id": i, "text_id": "w:V1", "text": "x", "audio": "y"} for i in ("a", "b", "c", "z")]
    kept, dropped = e.split_verified(pilot, verdicts)
    assert [r["id"] for r in kept] == ["a"] and {d["id"]: d["decision"] for d in dropped} == {"b": "remap", "c": "inconclusive", "z": "not_checked"}
    kept, dropped = e.split_verified(pilot, verdicts, accept_remap=True)
    assert [r["id"] for r in kept] == ["a", "b"] and kept[1]["text"].startswith("अग्निः") and kept[1]["remapped_from"] == "w:V1"


def test_plain_verdict_report_still_gates(tmp_path):
    p = tmp_path / "r.json"
    p.write_text(json.dumps({"rows": [{"id": "a", "verdict": "ok"}, {"id": "b", "verdict": "short"}]}), encoding="utf-8")
    verdicts = e.verified_ids(p)
    kept, dropped = e.split_verified([{"id": "a"}, {"id": "b"}], verdicts)
    assert [r["id"] for r in kept] == ["a"] and dropped == [{"id": "b", "decision": "short"}]
