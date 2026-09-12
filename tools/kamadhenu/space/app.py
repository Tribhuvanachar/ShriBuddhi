"""Kamadhenu — DGE Sanskrit chant Space (Hugging Face ZeroGPU).

Same serving model as prathoshap/vagdhenu-demo (the file this is derived from, Apache-2.0): the Vāgdhenu
renderer is created lazily inside an @spaces.GPU function, so a GPU is attached only for the seconds a verse
is being synthesised. Differences from the demo:

  * API-first: /synthesize(text, dge_chandas, seed) → (audio, json) [Vāgdhenu baseline] and
    /synthesize_kamadhenu(text, ref_id, seed) → (audio, json) [IndicF5 zero-shot, 3BHU1 reference]. The metre comes from the caller —
    DGE's own chandas engine runs in the browser (js/chandas.js) and its verdict is mapped onto the
    reference bank by meter_map.json. Auto-detection with Vāgdhenu's tts_meter is only the fallback.
  * The voice is configuration: VAGDHENU_HF / VAGDHENU_VOICE / VAGDHENU_VOC env vars (Kamadhenu's own voice
    later replaces the baseline without a code change).
  * Per-IP daily limit is KAMADHENU_DAILY_LIMIT (default 10, as in the demo); one śloka per call.

Local run (real GPU + weights):  VAGDHENU_HF=prathoshap/vagdhenu python app.py
"""
import json, os, re, subprocess, sys, time

import gradio as gr
import spaces

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "src")
sys.path.insert(0, SRC)
from huggingface_hub import hf_hub_download  # noqa: E402
import limits  # noqa: E402  (Vāgdhenu abuse guards: one śloka, per-IP quota)

limits.DAILY_LIMIT = int(os.environ.get("KAMADHENU_DAILY_LIMIT", limits.DAILY_LIMIT))


def _ensure_bigvgan():
    try:
        import bigvgan  # noqa: F401
        return
    except ImportError:
        pass
    dst = os.path.join(HERE, "BigVGAN")
    if not os.path.isdir(os.path.join(dst, ".git")):
        subprocess.run(["git", "clone", "--depth", "1", "https://github.com/NVIDIA/BigVGAN.git", dst], check=True)
    sys.path.insert(0, dst)


_ensure_bigvgan()

WEIGHTS_REPO = os.environ.get("VAGDHENU_HF", "prathoshap/vagdhenu")
VOICE_FILE = os.environ.get("VAGDHENU_VOICE", "voice_steer_ema_2026-06-17.pt")
VOC_FILE = os.environ.get("VAGDHENU_VOC", "voc_bigvgan_EMA_2026-06-11.pth")
BANK_PATH = os.path.join(SRC, "reference_bank", "bank.json")
VOCAB = os.path.join(SRC, "reference_bank", "vocab.txt")
METER_MAP = json.load(open(os.path.join(HERE, "meter_map.json"), encoding="utf-8"))
BANK = json.load(open(BANK_PATH, encoding="utf-8"))
BANK_KEYS = [k for k, v in BANK.items() if not k.startswith("_") and isinstance(v, dict) and "wav" in v]

_RENDERER = None

# ---- Engine 2: "Kamadhenu trial" = IndicF5 base model (ai4bharat/IndicF5, MIT) in zero-shot mode, prompted
# with one of the project lead's own recordings (refs/refs.json; consent recorded in the dataset). This is NOT a
# trained Kamadhenu model — it is the licensed base model imitating the reference voice, offered side by side
# with the Vāgdhenu baseline so the difference can be heard before any training is approved.
INDICF5_REPO = os.environ.get("KAMADHENU_INDICF5", "ai4bharat/IndicF5")
REFS_DIR = os.path.join(HERE, "refs")
REFS = json.load(open(os.path.join(REFS_DIR, "refs.json"), encoding="utf-8"))["refs"]
# Diagnostic reference (7 Sep 2026): IndicF5's own model-card prompt clip (ai4bharat/IndicF5, MIT; Punjabi read
# speech, 8.1 s, 48 kHz) with the transcript the model card gives. Rendering the model card's Hindi sentence with
# it checks the deployment itself, independent of the lead's chanted references; rendering Sanskrit with it, and
# Hindi with the lead's clip, separates "chant tempo is the gap" from "Sanskrit is the gap".
DIAG_REFS = {
    "indicf5_pan_f_happy": {
        "wav": os.path.join("diag", "PAN_F_HAPPY_00001.wav"),
        "text": "ਭਹੰਪੀ ਵਿੱਚ ਸਮਾਰਕਾਂ ਦੇ ਭਵਨ ਨਿਰਮਾਣ ਕਲਾ ਦੇ ਵੇਰਵੇ ਗੁੰਝਲਦਾਰ ਅਤੇ ਹੈਰਾਨ ਕਰਨ ਵਾਲੇ ਹਨ, ਜੋ ਮੈਨੂੰ ਖੁਸ਼ ਕਰਦੇ  ਹਨ।",
        "chandas": "—", "work": "IndicF5 model-card prompt (Punjabi read speech)", "seconds": 8.1,
    }
}
DIAG_MAX_CHARS = 240
_INDICF5 = None


def _get_indicf5():
    global _INDICF5
    if _INDICF5 is None:
        from transformers import AutoModel
        _INDICF5 = AutoModel.from_pretrained(INDICF5_REPO, trust_remote_code=True, token=os.environ.get("HF_TOKEN") or None)
        try:
            _INDICF5 = _INDICF5.to("cuda")
        except Exception:
            pass
    return _INDICF5


def _get_renderer():
    global _RENDERER
    if _RENDERER is None:
        from render_core import Renderer
        voice = hf_hub_download(WEIGHTS_REPO, VOICE_FILE)
        voc = hf_hub_download(WEIGHTS_REPO, VOC_FILE)
        _RENDERER = Renderer(voice, voc, BANK_PATH, device="cuda", vocab_file=VOCAB if os.path.exists(VOCAB) else None,
                             nfe=int(os.environ.get("KAMADHENU_NFE", "32")))
    return _RENDERER


def _n_syllables_per_pada(text):
    padas = [p for p in re.split(r"[\n।॥|]+", text) if p.strip()]
    if not padas:
        return 0
    return round(limits._n_aksharas(text) / (4 if len(padas) >= 3 else 2 if len(padas) == 2 else 4))


def resolve_meter(text, dge_chandas):
    """DGE chandas verdict → bank key. Returns (bank_key, how)."""
    name = re.sub(r"\s*\(.*?\)\s*", "", dge_chandas or "")
    name = re.sub(r"\s*—.*$", "", name).strip()          # 'अनुष्टुप् (श्लोकः) — र-विपुला (पादे 1)' → 'अनुष्टुप्'
    if name in ("गद्यम्", "prose", "gadya"):
        return METER_MAP["prose"], "prose"
    for part in name.split(","):                          # ardhasama rows join names: 'वियोगिनी, वैतालीय, सुन्दरी'
        k = METER_MAP["by_name"].get(part.strip())
        if k in BANK_KEYS:
            return k, "dge_name"
    n = _n_syllables_per_pada(text)
    k = METER_MAP["by_syllables"].get(str(n))
    if k in BANK_KEYS:
        return k, f"dge_syllables_{n}"
    try:                                                    # Vāgdhenu's own detector as last resort (CPU)
        from render_core import detect_meter_key
        det = detect_meter_key(text)
    except Exception:
        det = ""
    for bk in BANK_KEYS:
        if det and (bk.lower() == det.lower() or BANK[bk]["wav"].replace(".wav", "").lower() == det.lower()):
            return bk, "vagdhenu_detect"
    return METER_MAP["fallback"], "fallback"


# ZeroGPU duration: the `spaces` client multiplies the requested seconds by the hardware's duration_factor (1.5 on the
# sm_120 Blackwell cards this Space gets, configs.json in spaces 0.51.3) before checking the caller's quota, so
# duration=120 was billed as a 180 s request and refused visitors with fewer than 180 s left even though a warm verse
# takes 4-14 GPU s and the worst measured cold start 23 s (space_measurements.json). 60 s here = a 90 s request.
GPU_SECONDS = int(os.environ.get("KAMADHENU_GPU_SECONDS", "60"))


@spaces.GPU(duration=GPU_SECONDS)
def _render(text, bank_key, seed):
    t0 = time.time()
    sr, audio = _get_renderer().render_one(text, bank_key, seed=int(seed))
    return sr, audio, round(time.time() - t0, 2)


@spaces.GPU(duration=GPU_SECONDS)
def _render_indicf5(text, ref_id, seed):
    import numpy as np, torch
    torch.manual_seed(int(seed))
    r = REFS.get(ref_id) or DIAG_REFS[ref_id]
    t0 = time.time()
    audio = _get_indicf5()(text, ref_audio_path=os.path.join(REFS_DIR, r["wav"]), ref_text=r["text"])
    audio = np.asarray(audio)
    if audio.dtype == np.int16:
        audio = audio.astype(np.float32) / 32768.0
    return 24000, audio.astype(np.float32), round(time.time() - t0, 2)


def _guards(text, request):
    text = (text or "").strip()
    if not text:
        raise gr.Error("empty verse")
    try:
        msg = limits.validate_one_shloka(text)
    except Exception as e:
        raise gr.Error(f"validate: {type(e).__name__}: {e}")
    if msg:
        raise gr.Error(msg)
    try:
        ip = limits.client_ip(request) if request is not None else "unknown"
        allowed = limits.check_and_count(ip)
    except Exception as e:
        raise gr.Error(f"quota: {type(e).__name__}: {e}")
    if not allowed:
        raise gr.Error(f"daily limit of {limits.DAILY_LIMIT} verses reached from this network")
    return text


def _as_data(fn):
    """The /call API of this Space delivers `data: null` for raised errors (message hidden), so every failure is
    returned as (None, {"error": message}) instead — the reader shows the message, the UI shows the JSON.
    functools.wraps keeps the original signature visible, which Gradio needs to inject the `request: gr.Request`
    argument (without it every call failed with "missing 1 required positional argument: 'request'")."""
    import functools

    @functools.wraps(fn)
    def wrapped(*a, **k):
        try:
            return fn(*a, **k)
        except gr.Error as e:
            return None, {"error": str(e)}
        except Exception as e:
            return None, {"error": f"{type(e).__name__}: {e}"}
    return wrapped


@_as_data
def synthesize_kamadhenu(text, ref_id, seed, request: gr.Request):
    """Kamadhenu trial: IndicF5 zero-shot with a 3BHU1 reference prompt. Same guards as /synthesize."""
    text = _guards(text, request)
    if ref_id not in REFS:
        raise gr.Error(f"unknown reference '{ref_id}'; choose one of {', '.join(REFS)}")
    try:
        sr, audio, gpu_s = _render_indicf5(text, ref_id, seed)
    except Exception as e:
        raise gr.Error(f"rendering failed: {type(e).__name__}: {e}")
    r = REFS[ref_id]
    meta = {"engine": "indicf5-zero-shot", "base_model": f"{INDICF5_REPO} (MIT)", "voice": "3BHU1 reference prompt (no training)",
            "reference": {"id": ref_id, "chandas": r["chandas"], "work": r["work"], "seconds": r["seconds"]},
            "seed": int(seed), "sample_rate": sr, "audio_seconds": round(len(audio) / sr, 2), "gpu_seconds": gpu_s,
            "note": "zero-shot: the base model imitates the reference clip's voice and pace; metre is not modelled — compare with /synthesize (Vāgdhenu baseline)"}
    return (sr, audio), meta


@_as_data
def diagnose(text, ref_id, seed, request: gr.Request):
    """Diagnostics (7 Sep 2026): IndicF5 zero-shot with ANY short text (Hindi, Sanskrit prose, a śloka) and either the
    lead's clips or IndicF5's own prompt. No śloka validation — only the length cap and the per-IP daily quota."""
    text = (text or "").strip()
    if not text:
        raise gr.Error("empty text")
    if len(text) > DIAG_MAX_CHARS:
        raise gr.Error(f"diagnostic text is capped at {DIAG_MAX_CHARS} characters")
    try:
        ip = limits.client_ip(request) if request is not None else "unknown"
        if not limits.check_and_count(ip):
            raise gr.Error(f"daily limit of {limits.DAILY_LIMIT} verses reached from this network")
    except gr.Error:
        raise
    except Exception as e:
        raise gr.Error(f"quota: {type(e).__name__}: {e}")
    if ref_id not in REFS and ref_id not in DIAG_REFS:
        raise gr.Error(f"unknown reference '{ref_id}'; choose one of {', '.join(list(REFS) + list(DIAG_REFS))}")
    try:
        sr, audio, gpu_s = _render_indicf5(text, ref_id, seed)
    except Exception as e:
        raise gr.Error(f"rendering failed: {type(e).__name__}: {e}")
    r = REFS.get(ref_id) or DIAG_REFS[ref_id]
    meta = {"engine": "indicf5-zero-shot", "diagnostic": True, "base_model": f"{INDICF5_REPO} (MIT)",
            "reference": {"id": ref_id, "work": r["work"], "seconds": r["seconds"]}, "text": text,
            "seed": int(seed), "sample_rate": sr, "audio_seconds": round(len(audio) / sr, 2), "gpu_seconds": gpu_s}
    return (sr, audio), meta


@_as_data
def synthesize(text, dge_chandas, seed, request: gr.Request):
    # Every failure is raised as gr.Error so the /synthesize API returns a message instead of `data: null`
    # (Gradio hides other exception types from clients). The stage name says where it broke.
    text = (text or "").strip()
    if not text:
        raise gr.Error("empty verse")
    try:
        msg = limits.validate_one_shloka(text)
    except Exception as e:
        raise gr.Error(f"validate: {type(e).__name__}: {e}")
    if msg:
        raise gr.Error(msg)
    try:
        ip = limits.client_ip(request) if request is not None else "unknown"
        allowed = limits.check_and_count(ip)
    except Exception as e:
        raise gr.Error(f"quota: {type(e).__name__}: {e}")
    if not allowed:
        raise gr.Error(f"daily limit of {limits.DAILY_LIMIT} verses reached from this network")
    try:
        bank_key, how = resolve_meter(text, dge_chandas)
    except Exception as e:
        raise gr.Error(f"meter: {type(e).__name__}: {e}")
    try:
        sr, audio, gpu_s = _render(text, bank_key, seed)
    except Exception as e:                                  # surfaces ZeroGPU quota errors verbatim
        raise gr.Error(f"rendering failed: {type(e).__name__}: {e}")
    meta = {"dge_chandas": dge_chandas or None, "bank_meter": bank_key, "meter_resolved_by": how,
            "seed": int(seed), "sample_rate": sr, "audio_seconds": round(len(audio) / sr, 2), "gpu_seconds": gpu_s,
            "voice": f"{WEIGHTS_REPO}/{VOICE_FILE}", "engine": "vagdhenu@c18927a8"}
    return (sr, audio), meta


with gr.Blocks(title="Kamadhenu — DGE Sanskrit chant") as demo:
    gr.Markdown("# Kamadhenu — DGE Sanskrit chant\nServing layer for the Sarvamūla Digital Library. "
                "Backbone: [Vāgdhenu](https://github.com/prathoshap/vagdhenu) (Prof. Prathosh, IISc), Apache-2.0. "
                "The reader calls `/synthesize` directly; this page is for manual checks.")
    with gr.Row():
        with gr.Column():
            txt = gr.Textbox(label="Verse (Devanagari, one śloka)", lines=4)
            chandas = gr.Textbox(label="DGE chandas (as reported by the reader; blank = detect)", value="")
            seed = gr.Slider(0, 1000, value=60, step=1, label="Seed")
            btn = gr.Button("Chant", variant="primary")
        with gr.Column():
            out = gr.Audio(label="Chant", type="numpy")
            meta = gr.JSON(label="meta")
    btn.click(synthesize, inputs=[txt, chandas, seed], outputs=[out, meta], api_name="synthesize")
    gr.Markdown("## Kamadhenu trial — IndicF5 (MIT) zero-shot, prompted with the lead's own recording\n"
                "Not a trained model: the base model imitates the chosen reference clip. Same verse box above.")
    with gr.Row():
        with gr.Column():
            ref = gr.Dropdown(choices=[(f"{v['chandas']} — {v['work']} ({v['seconds']} s)", k) for k, v in REFS.items()],
                              value=next(iter(REFS)), label="Reference voice clip (3BHU1)")
            seed2 = gr.Slider(0, 1000, value=60, step=1, label="Seed")
            btn2 = gr.Button("Chant (Kamadhenu trial)", variant="secondary")
        with gr.Column():
            out2 = gr.Audio(label="Chant (IndicF5 zero-shot)", type="numpy")
            meta2 = gr.JSON(label="meta")
    btn2.click(synthesize_kamadhenu, inputs=[txt, ref, seed2], outputs=[out2, meta2], api_name="synthesize_kamadhenu")
    with gr.Accordion("Diagnostics — any short text, any reference (owner use; counts against the same quota)", open=False):
        dtxt = gr.Textbox(label="Text (≤ 240 chars: Hindi, Sanskrit prose or a śloka)", lines=2)
        dref = gr.Dropdown(choices=list(REFS) + list(DIAG_REFS), value=next(iter(REFS)), label="Reference clip")
        dseed = gr.Number(value=60, precision=0, label="Seed")
        dbtn = gr.Button("Render (diagnostic)")
        dout = gr.Audio(label="Diagnostic render", type="numpy")
        dmeta = gr.JSON(label="Details")
        dbtn.click(diagnose, inputs=[dtxt, dref, dseed], outputs=[dout, dmeta], api_name="diagnose")

if __name__ == "__main__":
    demo.launch(show_error=True)
