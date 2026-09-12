"""Kamadhenu Phase 8 scaffold: text convention, vocab, the trainer's batch sampler simulation, checkpoint key
mapping, and the exporter's file formats (on a synthetic wav when soundfile/ffmpeg are available)."""
import csv, json, sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "kamadhenu/training"))

from kamadhenu_text import model_text, load_vocab, unknown_chars  # noqa: E402
import ckpt_convert  # noqa: E402

VOCAB = ROOT / "kamadhenu/training/vocab_indicf5.txt"


def test_model_text_follows_vagdhenu_convention():
    assert model_text("धर्मक्षेत्रे कुरुक्षेत्रे ।\nमामकाः पाण्डवाश्चैव ॥ १ ॥") == "धर्मक्षेत्रे कुरुक्षेत्रे मामकाः पाण्डवाश्चैव"
    assert model_text("गुरु: नम:-") == "गुरुः नमः"
    assert model_text("सत्य-धर्म  ,  'ॐ'  ऽ") == "सत्यधर्म ॐ ऽ"      # hyphen joins, avagraha and ॐ kept


def test_vocab_is_indicf5_shape_and_covers_the_pilot():
    v = load_vocab(VOCAB)
    assert len(v) == 2545 and v[0] == " " and "।" in v and "ऽ" in v and "ँ" in v
    vs = set(v)
    for split in ("train", "validation"):
        for line in open(ROOT / f"kamadhenu/data/pilot/{split}.jsonl", encoding="utf-8"):
            assert unknown_chars(model_text(json.loads(line)["text"]), vs) == []


def test_dynamic_batches_match_trainer_rules():
    import dry_run
    durs = [10.0, 20.0, 30.0, 5.0, 40.0]                      # frames = 937.5, 1875, 2812.5, 468.75, 3750
    b = dry_run.dynamic_batches(durs, frames_threshold=3200, max_samples=64)
    assert b == [[3, 0], [1], [2]]                              # ascending fill: 468.75+937.5 fits, +1875 would exceed 3200; 40 s (3750) is dropped
    assert dry_run.dynamic_batches(durs, 3200, max_samples=1) == [[3], [0], [1], [2]]
    assert dry_run.dynamic_batches(durs, 6400, max_samples=64) == [[3, 0, 1, 2], [4]]
    p = dry_run.plan(durs, "24GB", target_updates=10)
    assert p["batches_per_epoch"] == 3 and p["epochs"] == 4 and p["updates"] == 12 and p["too_long_for_batch"] == 1


def test_checkpoint_key_mapping_round_trip():
    # IndicF5's real model.safetensors layout (seen 7 Sep 2026): compiled EMA DiT + bundled vocoder + EMA buffers
    base = {"ema_model._orig_mod.transformer.w": 1, "ema_model._orig_mod.mel_spec.mel_stft.mel_scale.fb": 2,
            "vocoder._orig_mod.backbone.x": 7, "initted": 3, "step": 4}
    w, b = ckpt_convert.normalize_f5_keys(base)
    assert w == {"transformer.w": 1} and b == {"initted": 3, "step": 4}
    ck = ckpt_convert.wrap_for_trainer(base)
    assert ck == {"ema_model_state_dict": {"ema_model.transformer.w": 1, "initted": 3, "step": 4}}
    assert "step" not in ck                                     # no top-level step → trainer starts the fine-tune at 0
    # plain F5 layout and a raw online state dict reduce to the same thing
    assert ckpt_convert.normalize_f5_keys({"ema_model.transformer.w": 1})[0] == {"transformer.w": 1}
    assert ckpt_convert.normalize_f5_keys({"transformer.w": 1})[0] == {"transformer.w": 1}
    ck2 = {"ema_model_state_dict": {"ema_model.transformer.w": 1, "initted": 3, "step": 4},
           "model_state_dict": {"transformer.w": 9, "mel_spec.mel_stft.spectrogram.window": 0}, "step": 500}
    ema = ckpt_convert.flatten_for_export(ck2)
    assert ema == {"ema_model.transformer.w": 1, "initted": 3, "step": 4}
    assert ckpt_convert.flatten_for_export(ck2, online=True) == {"ema_model.transformer.w": 9}
    wl = ckpt_convert.wrapper_layout(ema, base)
    assert wl == {"ema_model._orig_mod.transformer.w": 1, "vocoder._orig_mod.backbone.x": 7, "initted": 3, "step": 4}


def test_experiment_config_is_consistent():
    import yaml
    cfg = yaml.safe_load(open(ROOT / "kamadhenu/training/experiment_a.yaml", encoding="utf-8"))
    assert cfg["base_model"]["repo"] == "ai4bharat/IndicF5"
    req = (ROOT / "tools/kamadhenu/space/requirements.txt").read_text()
    assert cfg["base_model"]["code_commit"] in req             # the Space and the trainer pin the same code
    import hashlib
    assert hashlib.sha1(VOCAB.read_bytes()).hexdigest() == cfg["base_model"]["vocab_sha1"]
    assert set(cfg["training"]["batch_size_per_gpu"]) == {"16GB", "24GB", "40GB"}
    assert cfg["training"]["num_warmup_updates"] < cfg["training"]["target_updates"]


def test_exporter_writes_f5_layout(tmp_path):
    sf = pytest.importorskip("soundfile")
    np = pytest.importorskip("numpy")
    import export_f5_dataset as ex
    exe = ex.ffmpeg_exe()
    if not exe:
        pytest.skip("imageio-ffmpeg not installed")
    src = tmp_path / "src.wav"
    t = np.arange(int(44100 * 6.0)) / 44100
    sf.write(src, (0.5 * np.sin(2 * np.pi * 220 * t)).astype("float32"), 44100)
    rows = [{"id": "t1", "text": "नमो नारायणाय ।\nनमः ॥", "audio": str(src.relative_to(ROOT)) if str(src).startswith(str(ROOT)) else str(src),
             "duration": 6.0, "meter": "अनुष्टुप्"}]
    ex.ROOT = Path("/")                                          # absolute source path in the row
    out = tmp_path / "ds"
    recs, problems = ex.export_rows(rows, out, exe, load_vocab(VOCAB), "t")
    assert problems == [] and len(recs) == 1
    m = recs[0]
    assert m["sample_rate"] == 24000 and abs(m["duration"] - 6.0) < 0.05 and abs(m["peak_dbfs"] - (-3.0)) < 0.2
    assert m["text"] == "नमो नारायणाय नमः" and m["frames"] == int(np.ceil(6.0 * 24000 / 256))
    with open(out / "metadata.csv", encoding="utf-8-sig", newline="") as f:
        rd = csv.reader(f, delimiter="|"); assert next(rd) == ["audio_file", "text"]; assert next(rd) == ["wavs/t1.wav", "नमो नारायणाय नमः"]
    assert json.load(open(out / "duration.json"))["duration"] == [m["duration"]]
    assert load_vocab(out / "vocab.txt")[0] == " "


def test_hf_job_bootstrap_and_cap():
    import hf_job
    sc = hf_job.bootstrap_script("abc123", 100, "SarvamulaOrg/kamadhenu-voice-a")
    assert "git checkout --quiet abc123" in sc and "launch_experiment_a.sh" in sc and "KAMADHENU_MAX_MINUTES=100" in sc
    assert "sparse-checkout set kamadhenu tools/kamadhenu/space kamadhenu_dataset" in sc
    usd, inr = hf_job.worst_case("l4x1", 150)
    assert usd == 2.0 and inr == 176 and inr <= 185
    assert hf_job.worst_case("a10g-small", 150)[1] > 185          # a10g at 150 min would breach the cap; submit refuses it


def test_run_record_writes_timings(tmp_path):
    import run_record
    out = tmp_path / "run.json"
    run_record.main(["--out", str(out), "--vram", "24GB", "--batch", "3200", "--epochs", "34", "--cap", "100", "--rc", "0",
                     "--step", "3060", "--t", "0", "600", "4800", "5400"])
    rec = json.load(open(out))
    assert rec["minutes"] == {"setup": 10.0, "train": 70.0, "export_eval": 10.0, "total": 90.0} and rec["last_step"] == "3060"
