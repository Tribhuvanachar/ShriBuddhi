#!/usr/bin/env bash
# Assemble and upload the Kamadhenu ZeroGPU Space.
#   bash tools/kamadhenu/space/build_space.sh <hf-account>/kamadhenu [--no-upload]
# Pulls Vāgdhenu (Apache-2.0) at the pinned commit for src/ + reference_bank/, adds DGE's app.py,
# meter_map.json and requirements.txt, and uploads the result with the huggingface_hub Python API. Nothing from the
# vagdhenu checkout is committed to this repository.
set -euo pipefail
SPACE="${1:?usage: build_space.sh <hf-account>/kamadhenu [--no-upload]}"
HERE="$(cd "$(dirname "$0")" && pwd)"
VAGDHENU_COMMIT="c18927a8a77775753e32248177a5a6bea1019a12"    # 19 Jul 2026, the commit the public demo runs
WORK="${TMPDIR:-/tmp}/kamadhenu_space"; DIST="$WORK/dist"
rm -rf "$DIST"; mkdir -p "$WORK" "$DIST"
if [ ! -d "$WORK/vagdhenu/.git" ]; then git clone --quiet https://github.com/prathoshap/vagdhenu.git "$WORK/vagdhenu"; fi
git -C "$WORK/vagdhenu" checkout --quiet "$VAGDHENU_COMMIT"
cp -r "$WORK/vagdhenu/src" "$DIST/src"                          # render_core, prep_text, limits, reference_bank/
cp "$HERE/app.py" "$HERE/meter_map.json" "$HERE/requirements.txt" "$HERE/README.md" "$DIST/"
cp -r "$HERE/refs" "$DIST/refs"                                  # 3BHU1 reference prompts for the IndicF5 zero-shot engine
cat > "$DIST/THIRD_PARTY_NOTICES.md" <<'N'
src/ is Vāgdhenu (github.com/prathoshap/vagdhenu, Apache-2.0, Prof. Prathosh A P, IISc) at the commit named in build_space.sh.
Weights are downloaded at runtime from huggingface.co/prathoshap/vagdhenu (Apache-2.0; see its THIRD_PARTY_NOTICES.md for IndicF5/BigVGAN).
Kamadhenu-specific files (app.py, meter_map.json) © Sarvamūla Digital Library, Apache-2.0.
N
echo "assembled $DIST ($(du -sh "$DIST" | cut -f1))"
if [ "${2:-}" != "--no-upload" ]; then
  # huggingface_hub ≥ 1.0 removed the `huggingface-cli` binary; the Python API is stable across versions.
  # Creates the Space if needed, uploads dist/, then asks for ZeroGPU hardware (works on a PRO account;
  # on a free account the request is refused and the Space stays on CPU — set it by hand in Settings).
  python3 - "$SPACE" "$DIST" <<'PY'
import sys, os
from huggingface_hub import HfApi
space, dist = sys.argv[1], sys.argv[2]
api = HfApi(token=os.environ.get("HF_TOKEN"))
api.create_repo(space, repo_type="space", space_sdk="gradio", exist_ok=True)
api.upload_folder(repo_id=space, repo_type="space", folder_path=dist, path_in_repo=".", commit_message="deploy from bhumandala build_space.sh")
print(f"uploaded → https://huggingface.co/spaces/{space}")
# The IndicF5 base weights are gated (auto-accept). Accept the gate for this account and give the Space the
# token as a secret so hf_hub can download them at runtime.
import urllib.request
tok = os.environ.get("HF_TOKEN")
gate_ok = False
for url in ("https://huggingface.co/ai4bharat/IndicF5/ask-access", "https://huggingface.co/api/models/ai4bharat/IndicF5/ask-access"):
    try:
        req = urllib.request.Request(url, data=b"", method="POST", headers={"Authorization": f"Bearer {tok}"})
        with urllib.request.urlopen(req, timeout=30) as r:
            print(f"IndicF5 gate via {url}: HTTP {r.status}"); gate_ok = True; break
    except Exception as e:
        print(f"IndicF5 gate via {url}: {type(e).__name__}: {str(e)[:100]}")
try:   # verify: can this token read the gated config?
    req = urllib.request.Request("https://huggingface.co/ai4bharat/IndicF5/resolve/main/config.json", headers={"Authorization": f"Bearer {tok}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        print("IndicF5 gated read check: OK (HTTP", r.status, ")")
except Exception as e:
    print(f"IndicF5 gated read check: {type(e).__name__}: {str(e)[:100]} — the SarvamulaOrg account must click 'Agree and access repository' once at https://huggingface.co/ai4bharat/IndicF5")
try:
    api.add_space_secret(repo_id=space, key="HF_TOKEN", value=tok, description="read gated ai4bharat/IndicF5 at runtime")
    print("space secret HF_TOKEN set")
except Exception as e:
    print(f"space secret: {type(e).__name__}: {str(e)[:120]}")
try:
    api.request_space_hardware(repo_id=space, hardware="zero-a10g")
    print("hardware: ZeroGPU (zero-a10g) requested")
except Exception as e:   # not fatal: the upload is done; hardware can be set in the Space settings
    print(f"hardware request failed ({e.__class__.__name__}: {str(e)[:200]}) — set Hardware → ZeroGPU in the Space settings")
PY
fi
