#!/usr/bin/env python3
"""
app.py — the DGE Audio Admin web panel.

Run it inside the Codespace and open the forwarded port:

    pip install -r requirements.txt
    python app.py                     # -> http://localhost:5000

What it does:
    upload a chanting recording → remove tabla/veena/drums → find the gaps →
    show each shloka with a play button so you can verify → export a JSON
    timestamp map + one WAV per shloka → save into the DGE audio folder →
    (optional, later) push to the bhumandala-audio-data repo.

Everything heavy happens in engine.py. This file is just the web glue.
"""
import io, json, os, shutil, uuid, zipfile
from flask import (Flask, request, jsonify, send_file, send_from_directory,
                   render_template)
import yaml
import engine as E

BASE = os.path.dirname(os.path.abspath(__file__))
JOBS = os.path.join(BASE, "jobs")
os.makedirs(JOBS, exist_ok=True)

def load_cfg():
    path = os.path.join(BASE, "config.yaml")
    if os.path.exists(path):
        with open(path) as f:
            return yaml.safe_load(f) or {}
    return {}

CFG = load_cfg()
app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024   # 500 MB uploads

def _safe_segment(s):
    # job/name/subfolder values land straight in os.path.join() below --
    # this is a local, single-admin tool (not a public multi-tenant
    # service), but a bare ".." still needs no "/" to pass Flask's default
    # <string> converter, so reject it rather than trust it silently.
    if not s or "/" in s or "\\" in s or s in (".", ".."):
        return None
    return s

# ------------------------------------------------------------------ pages
@app.get("/")
def index():
    d = CFG.get("defaults", {})
    return render_template("index.html",
                           default_min_len=d.get("min_len", 8.0),
                           default_min_gap=d.get("min_gap", 1.5),
                           default_pad=d.get("pad", 0.10),
                           output_dir=CFG.get("output", {}).get("local_dir", "(unset)"),
                           push_repo=CFG.get("push", {}).get("repo", "(unset)"))

# --------------------------------------------------------------- process
@app.post("/api/process")
def api_process():
    f = request.files.get("audio")
    if not f:
        return jsonify(error="No audio file uploaded."), 400
    job = uuid.uuid4().hex[:12]
    jdir = os.path.join(JOBS, job)
    os.makedirs(jdir, exist_ok=True)
    src = os.path.join(jdir, f.filename)
    f.save(src)

    form = request.form
    def num(k, d):
        try: return float(form.get(k, d))
        except (TypeError, ValueError): return d

    target = int(num("target", 0))
    p = E.Params(
        separate=form.get("separate", "true") == "true",
        min_len=num("min_len", CFG.get("defaults", {}).get("min_len", 8.0)),
        min_gap=num("min_gap", CFG.get("defaults", {}).get("min_gap", 1.5)),
        pad=num("pad", CFG.get("defaults", {}).get("pad", 0.10)),
        prefix=form.get("prefix", "chunk_"),
        start_no=int(num("start_no", 1)),
        width=int(num("width", 2)),
        model=CFG.get("separation", {}).get("model", "htdemucs"),
    )
    out = os.path.join(jdir, "out")
    try:
        res = E.process(src, out, target, p,
                        cache_dir=os.path.join(BASE, ".voice_cache"),
                        want_json=True, want_clips=True)
    except Exception as e:  # surface engine errors to the panel
        return jsonify(error=f"Processing failed: {e}"), 500

    return jsonify(job=job, source=res.source, duration=res.duration,
                   count=res.count, separated=res.separated, note=res.note,
                   params=res.params, chunks=res.chunks,
                   audio_url=f"/api/audio/{job}")

# ------------------------------------------------------------- media/files
@app.get("/api/audio/<job>")
def api_audio(job):
    job = _safe_segment(job)
    if not job:
        return "invalid job id", 400
    jdir = os.path.join(JOBS, job)
    for n in os.listdir(jdir):
        if os.path.isfile(os.path.join(jdir, n)) and n != "out":
            return send_from_directory(jdir, n)
    return "not found", 404

@app.get("/api/clip/<job>/<name>")
def api_clip(job, name):
    job, name = _safe_segment(job), _safe_segment(name)
    if not job or not name:
        return "invalid job id or clip name", 400
    return send_from_directory(os.path.join(JOBS, job, "out"), name)

@app.get("/api/download/<job>")
def api_download(job):
    job = _safe_segment(job)
    if not job:
        return "invalid job id", 400
    out = os.path.join(JOBS, job, "out")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for n in os.listdir(out):
            z.write(os.path.join(out, n), n)
    buf.seek(0)
    return send_file(buf, mimetype="application/zip",
                     as_attachment=True, download_name=f"{job}_shlokas.zip")

# ---------------------------------------------- save into the DGE folder
@app.post("/api/save/<job>")
def api_save(job):
    job = _safe_segment(job)
    if not job:
        return jsonify(error="invalid job id"), 400
    dest_rel = CFG.get("output", {}).get("local_dir")
    if not dest_rel:
        return jsonify(error="No output.local_dir set in config.yaml"), 400
    sub_raw = request.json.get("subfolder", "").strip("/") if request.is_json else ""
    # Each path segment of subfolder gets the same ".."/"\\" check as job/name
    # above -- this one genuinely needs to allow "/" (it's a nested
    # destination path), just not traversal within it.
    if sub_raw and any(not _safe_segment(seg) for seg in sub_raw.split("/")):
        return jsonify(error="invalid subfolder"), 400
    sub = sub_raw
    dest = os.path.join(BASE, dest_rel, sub) if sub else os.path.join(BASE, dest_rel)
    os.makedirs(dest, exist_ok=True)
    out = os.path.join(JOBS, job, "out")
    copied = []
    for n in os.listdir(out):
        shutil.copy2(os.path.join(out, n), os.path.join(dest, n))
        copied.append(n)
    return jsonify(saved_to=dest, files=copied)

# ---------------------------------------------- (future) push to repo
@app.post("/api/push/<job>")
def api_push(job):
    push = CFG.get("push", {})
    if not push.get("enabled"):
        return jsonify(error="Pushing is disabled. Set push.enabled: true in "
                       "config.yaml and provide a GH token, then use "
                       "scripts/push_to_repo.sh."), 400
    return jsonify(error="Use scripts/push_to_repo.sh from the Codespace terminal "
                   "(keeps your token out of the browser).", hint=push), 501

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
