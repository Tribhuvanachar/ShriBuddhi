#!/usr/bin/env python3
"""Checkpoint conversion between IndicF5's distribution format and the F5 trainer's (Kamadhenu Phase 8).

What IndicF5's `model.safetensors` actually holds (learned from the first real load, 7 Sep 2026): the Hub wrapper's
state dict — the DiT EMA weights under `ema_model._orig_mod.transformer.*` (a torch.compile'd module, hence
`_orig_mod`), the Vocos vocoder under `vocoder._orig_mod.*`, and the EMA buffers. The F5 trainer wants
{"ema_model_state_dict": {"ema_model.transformer.*": …, "initted": …, "step": …}} and its own `load_checkpoint`
wants the flat `ema_model.transformer.*` form. normalize_f5_keys() is the one place that reduces any of these
layouts to bare `transformer.*` keys; everything else is prefixing.

  to-trainer      model.safetensors → ckpt/model_last.pt        (no top-level step → the trainer starts at 0 from the EMA weights)
  verify          ckpt/model_last.pt --vocab vocab.txt          (builds the real model + EMA with torch and loads STRICTLY; run before training)
  to-safetensors  model_<step>.pt → out.safetensors [--online] [--wrapper-base base.safetensors]
                  plain F5 layout; with --wrapper-base also writes <out>.wrapper.safetensors in IndicF5's own layout
                  (vocoder keys copied from the base file) so the Hub wrapper / the Space can load it unchanged.

The key logic is pure Python; torch and safetensors are imported only inside the I/O commands.
"""
import argparse, sys

MEL_BUFFERS = ("mel_spec.mel_stft.mel_scale.fb", "mel_spec.mel_stft.spectrogram.window")
EMA_BUFFERS = ("initted", "step")


def normalize_f5_keys(flat):
    """Any layout → {bare model key: tensor}: strip `ema_model.` / `_orig_mod.` / `module.` prefixes, drop the
    vocoder, the EMA buffers and the mel-filterbank buffers. Returns (weights, buffers) where buffers holds
    initted/step if the source had them."""
    weights, buffers = {}, {}
    for k, v in flat.items():
        if k in EMA_BUFFERS:
            buffers[k] = v; continue
        if k.startswith("vocoder."):
            continue
        kk = k
        for p in ("ema_model.", "module."):
            if kk.startswith(p): kk = kk[len(p):]
        kk = kk.replace("_orig_mod.", "")
        if kk.endswith(MEL_BUFFERS) or kk in EMA_BUFFERS:
            continue
        weights[kk] = v
    return weights, buffers


def wrap_for_trainer(flat):
    """flat safetensors dict → trainer checkpoint dict (no 'step' → fresh fine-tune start)."""
    w, b = normalize_f5_keys(flat)
    ema = {"ema_model." + k: v for k, v in w.items()}
    ema.update(b)
    return {"ema_model_state_dict": ema}


def flatten_for_export(ckpt, online=False):
    """trainer checkpoint → flat dict with `ema_model.` keys (+ initted/step) that load_checkpoint(use_ema=True) reads."""
    src = ckpt["model_state_dict"] if online else ckpt["ema_model_state_dict"]
    w, b = normalize_f5_keys(src)
    flat = {"ema_model." + k: v for k, v in w.items()}
    if not online:
        flat.update(b)
    return flat


def wrapper_layout(flat_f5, base_flat):
    """plain F5 layout → IndicF5 Hub-wrapper layout: ema_model._orig_mod.<key> + the base file's vocoder + EMA buffers."""
    w, b = normalize_f5_keys(flat_f5)
    out = {"ema_model._orig_mod." + k: v for k, v in w.items()}
    for k, v in base_flat.items():
        if k.startswith("vocoder."):
            out[k] = v
    for k in EMA_BUFFERS:
        if k in b: out[k] = b[k]
        elif k in base_flat: out[k] = base_flat[k]
    return out


def cmd_to_trainer(src, dst):
    import torch
    from safetensors.torch import load_file
    flat = load_file(src, device="cpu")
    ck = wrap_for_trainer(flat)
    ema = ck["ema_model_state_dict"]
    ema.setdefault("initted", torch.tensor(True))
    ema.setdefault("step", torch.tensor(0))
    torch.save(ck, dst)
    n = sum(v.numel() for k, v in ema.items() if k.startswith("ema_model."))
    print(f"{src} → {dst}: {len(ema)} tensors, {n / 1e6:.1f} M parameters, no step (fine-tune starts at 0); "
          f"source had {sum(1 for k in flat if k.startswith('vocoder.'))} vocoder tensors (dropped)")


def cmd_verify(ckpt_path, vocab_file):
    """Build the model exactly as finetune_cli.py does and load the checkpoint the way trainer.load_checkpoint does."""
    import torch
    from ema_pytorch import EMA
    from f5_tts.model import CFM, DiT
    from f5_tts.model.utils import get_tokenizer
    vocab_char_map, vocab_size = get_tokenizer(vocab_file, "custom")
    mel = dict(n_fft=1024, hop_length=256, win_length=1024, n_mel_channels=100, target_sample_rate=24000, mel_spec_type="vocos")
    model = CFM(transformer=DiT(dim=1024, depth=22, heads=16, ff_mult=2, text_dim=512, conv_layers=4, text_num_embeds=vocab_size, mel_dim=100),
                mel_spec_kwargs=mel, vocab_char_map=vocab_char_map)
    ema = EMA(model, include_online_model=False)
    ck = torch.load(ckpt_path, map_location="cpu", weights_only=True)
    sd = dict(ck["ema_model_state_dict"])
    for k in ["ema_model." + m for m in MEL_BUFFERS]:
        sd.pop(k, None)
    ema.load_state_dict(sd)                               # strict, like the trainer
    online = {k.replace("ema_model.", ""): v for k, v in sd.items() if k not in EMA_BUFFERS}
    res = model.load_state_dict(online, strict=False)
    missing = [k for k in res.missing_keys if not k.endswith(MEL_BUFFERS)]
    if missing or res.unexpected_keys:
        sys.exit(f"online load: missing {missing[:5]}… ({len(missing)}), unexpected {res.unexpected_keys[:5]}… ({len(res.unexpected_keys)})")
    n = sum(p.numel() for p in model.parameters())
    print(f"verify ok: {ckpt_path} loads strictly into EMA and model ({n / 1e6:.1f} M parameters, vocab {vocab_size})")


def cmd_to_safetensors(src, dst, online=False, wrapper_base=None):
    import torch
    from safetensors.torch import save_file, load_file
    ck = torch.load(src, map_location="cpu", weights_only=True)
    flat = flatten_for_export(ck, online=online)
    flat = {k: v.contiguous() for k, v in flat.items()}
    if not online:
        flat.setdefault("initted", torch.tensor(True))
        flat.setdefault("step", torch.tensor(int(ck.get("step", 0))))
    meta = {"source": src, "weights": "online" if online else "ema", "step": str(ck.get("step", ""))}
    save_file(flat, dst, metadata=meta)
    print(f"{src} (step {ck.get('step', '?')}) → {dst}: {len(flat)} tensors ({'online' if online else 'EMA'} weights, plain F5 layout)")
    if wrapper_base:
        base = load_file(wrapper_base, device="cpu")
        wl = {k: v.contiguous() for k, v in wrapper_layout(flat, base).items()}
        wdst = dst.replace(".safetensors", ".wrapper.safetensors")
        save_file(wl, wdst, metadata=dict(meta, layout="indicf5-wrapper"))
        print(f"  + {wdst}: {len(wl)} tensors (IndicF5 wrapper layout, vocoder copied from {wrapper_base})")


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("to-trainer"); p1.add_argument("src"); p1.add_argument("dst")
    p2 = sub.add_parser("to-safetensors"); p2.add_argument("src"); p2.add_argument("dst"); p2.add_argument("--online", action="store_true")
    p2.add_argument("--wrapper-base", default=None)
    p3 = sub.add_parser("verify"); p3.add_argument("ckpt"); p3.add_argument("--vocab", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "to-trainer":
        cmd_to_trainer(a.src, a.dst)
    elif a.cmd == "verify":
        cmd_verify(a.ckpt, a.vocab)
    else:
        cmd_to_safetensors(a.src, a.dst, a.online, a.wrapper_base)


if __name__ == "__main__":
    sys.exit(main())
