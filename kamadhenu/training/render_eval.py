#!/usr/bin/env python3
"""Kamadhenu Experiment A — A/B renders of the held-out verses (runs on the GPU box after training).

    python3 kamadhenu/training/render_eval.py --base base/model.safetensors --finetuned export/model.safetensors \
        [--finetuned-online export/model_online.safetensors] --vocab export/vocab.txt --out eval/

For each verse in kamadhenu/data/pilot/validation.jsonl: render with the zero-shot base and with the fine-tuned
weights (EMA and, if given, online), same reference clip (the lead's own, from tools/kamadhenu/space/refs), same
seed, same text convention as training. Writes <out>/<id>/{base,finetuned,finetuned_online}.wav and eval.json with
the generated/recorded duration ratio per verse — the first objective signal (1.0 ± 0.25 is on-tempo; the 7 Sep
zero-shot clip D ran ~1.65×). The lead's ear decides the rest (Phase 13 adds HUMAN_REVIEW.csv).

Uses f5_tts.infer.utils_infer directly (load_model builds the net, load_checkpoint loads a .safetensors/.pt with the
EMA keys, infer_process renders) — in the pinned IndicF5 commit the F5TTS api class passes a checkpoint argument its
own load_model no longer takes, so it cannot be used.
"""
import argparse, json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from kamadhenu_text import model_text  # noqa: E402
from ckpt_convert import normalize_f5_keys, MEL_BUFFERS  # noqa: E402

MODEL_CFG = dict(dim=1024, depth=22, heads=16, ff_mult=2, text_dim=512, conv_layers=4)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True); ap.add_argument("--finetuned", required=True)
    ap.add_argument("--finetuned-online", default=None); ap.add_argument("--vocab", required=True)
    ap.add_argument("--eval-jsonl", default="kamadhenu/data/pilot/validation.jsonl")
    ap.add_argument("--ref", default="tp_anushtubh_19"); ap.add_argument("--seed", type=int, default=60)
    ap.add_argument("--nfe", type=int, default=32); ap.add_argument("--cfg", type=float, default=2.0)
    ap.add_argument("--out", required=True); ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args(argv)
    import torch, soundfile as sf
    from f5_tts.model import DiT
    from f5_tts.model.utils import seed_everything
    from f5_tts.infer.utils_infer import load_vocoder, load_model, preprocess_ref_audio_text, infer_process
    from safetensors.torch import load_file

    def load_any(model, path):
        """IndicF5 wrapper layout, plain F5 layout or a trainer .pt — all reduced to bare keys, loaded strictly."""
        if path.endswith(".safetensors"):
            flat = load_file(path, device="cpu")
        else:
            ck = torch.load(path, map_location="cpu", weights_only=True)
            flat = ck.get("ema_model_state_dict") or ck["model_state_dict"]
        w, _ = normalize_f5_keys(flat)
        res = model.load_state_dict(w, strict=False)
        missing = [k for k in res.missing_keys if not k.endswith(MEL_BUFFERS)]
        if missing or res.unexpected_keys:
            raise RuntimeError(f"{path}: missing {missing[:5]} ({len(missing)}), unexpected {res.unexpected_keys[:5]} ({len(res.unexpected_keys)})")
        return model.to(device).eval()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    refs = json.load(open(ROOT / "tools/kamadhenu/space/refs/refs.json", encoding="utf-8"))["refs"]
    ref = refs[a.ref]; ref_wav = str(ROOT / "tools/kamadhenu/space/refs" / ref["wav"]); ref_text = model_text(ref["text"])
    rows = [json.loads(l) for l in open(ROOT / a.eval_jsonl, encoding="utf-8")]
    if a.limit: rows = rows[:a.limit]
    models = {"base": a.base, "finetuned": a.finetuned}
    if a.finetuned_online: models["finetuned_online"] = a.finetuned_online
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    vocoder = load_vocoder("vocos", device=device)
    ref_audio, ref_text = preprocess_ref_audio_text(ref_wav, ref_text, device=device)
    results = {r["id"]: {"text_id": r.get("text_id"), "meter": r.get("meter"), "recorded_seconds": r.get("duration"), "renders": {}} for r in rows}
    for name, ckpt in models.items():
        t0 = time.time()
        model = load_any(load_model(DiT, MODEL_CFG, "vocos", a.vocab, "euler", True, device), ckpt)
        for r in rows:
            d = out / r["id"]; d.mkdir(exist_ok=True)
            wav_path = d / f"{name}.wav"
            t1 = time.time(); seed_everything(a.seed)
            wav, sr, _ = infer_process(ref_audio, ref_text, model_text(r["text"]), model, vocoder, mel_spec_type="vocos",
                                       nfe_step=a.nfe, cfg_strength=a.cfg, show_info=lambda *x: None, device=device)
            sf.write(str(wav_path), wav, sr)
            secs = len(wav) / sr
            results[r["id"]]["renders"][name] = {"seconds": round(secs, 2), "duration_ratio": round(secs / r["duration"], 3) if r.get("duration") else None,
                                                  "render_seconds": round(time.time() - t1, 1)}
            print(f"{name:16s} {r['id']} {secs:6.2f}s (recorded {r.get('duration')})", flush=True)
        del model; torch.cuda.empty_cache()
        print(f"== {name}: {len(rows)} renders in {time.time() - t0:.0f}s", flush=True)
    summary = {}
    for name in models:
        ratios = sorted(v["renders"][name]["duration_ratio"] for v in results.values() if v["renders"].get(name, {}).get("duration_ratio"))
        summary[name] = {"n": len(ratios), "median_duration_ratio": ratios[len(ratios) // 2] if ratios else None,
                         "on_tempo": sum(1 for x in ratios if 0.75 <= x <= 1.25)}
    json.dump({"reference": a.ref, "ref_text": ref_text, "seed": a.seed, "nfe": a.nfe, "cfg": a.cfg, "models": models, "summary": summary, "verses": results},
              open(out / "eval.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    sys.exit(main())
