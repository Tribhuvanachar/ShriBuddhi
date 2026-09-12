#!/usr/bin/env python3
"""Measure the deployed Kamadhenu Space: GPU seconds per verse per metre, cold start, wall time.

    python3 tools/kamadhenu/space/measure.py https://<account>-kamadhenu.hf.space [--n 3]

Uses the public Gradio HTTP API (no gradio_client dependency). Picks one verified example verse per bank
metre from tests/fixtures/chandas_examples.json plus Gītā 1.1, calls /synthesize, and writes
kamadhenu_dataset/space_measurements.json — the numbers DEPLOYMENT_REFERENCE.md §5 asks for before any
GPU-server discussion. Each call spends the caller's ZeroGPU quota (≈ 6–15 GPU s per verse)."""
import argparse, json, sys, time, urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "kamadhenu_dataset" / "space_measurements.json"
GITA_1_1 = "धर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः ।\nमामकाः पाण्डवाश्चैव किमकुर्वत सञ्जय ॥"


def call(space, text, chandas, seed=60, timeout=300):
    req = urllib.request.Request(f"{space}/gradio_api/call/synthesize", data=json.dumps({"data": [text, chandas, seed]}).encode(),
                                 headers={"Content-Type": "application/json"})
    event = json.load(urllib.request.urlopen(req, timeout=60))["event_id"]
    t0 = time.time()
    with urllib.request.urlopen(f"{space}/gradio_api/call/synthesize/{event}", timeout=timeout) as r:
        ev = None
        for line in r:
            line = line.decode().strip()
            if line.startswith("event:"):
                ev = line[6:].strip()
            elif line.startswith("data:") and ev in ("complete", "error"):
                data = json.loads(line[5:])
                if ev == "error":
                    raise RuntimeError(data)
                return data, round(time.time() - t0, 2)
    raise RuntimeError("stream ended without a result")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("space"); ap.add_argument("--n", type=int, default=1)
    a = ap.parse_args(); space = a.space.rstrip("/")
    mm = json.load(open(ROOT / "tools/kamadhenu/space/meter_map.json", encoding="utf-8"))["by_name"]
    fx = json.load(open(ROOT / "tests/fixtures/chandas_examples.json", encoding="utf-8"))["examples"]
    cases = [("अनुष्टुप्", GITA_1_1)] + [(e["vrutta"], e["text"]) for e in fx if e["vrutta"] in mm]
    rows = []
    for i, (chandas, text) in enumerate(cases):
        for k in range(a.n):
            try:
                (audio, meta), wall = call(space, text, chandas)
                rows.append({"chandas": chandas, "bank_meter": meta.get("bank_meter"), "gpu_seconds": meta.get("gpu_seconds"),
                             "audio_seconds": meta.get("audio_seconds"), "wall_seconds": wall, "cold": i == 0 and k == 0})
                print(f"{chandas:22s} gpu {meta.get('gpu_seconds')}s  audio {meta.get('audio_seconds')}s  wall {wall}s", flush=True)
            except Exception as e:
                rows.append({"chandas": chandas, "error": str(e)}); print(f"{chandas}: {e}", file=sys.stderr)
    ok = [r for r in rows if "gpu_seconds" in r and not r["cold"]]
    summary = {"measured_at": datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d %b %Y, %I:%M %p IST"), "space": space, "calls": len(rows),
               "rtf_mean": round(sum(r["gpu_seconds"] / r["audio_seconds"] for r in ok if r["audio_seconds"]) / len(ok), 3) if ok else None,
               "gpu_seconds_per_verse_mean": round(sum(r["gpu_seconds"] for r in ok) / len(ok), 2) if ok else None,
               "cold_start_wall_seconds": next((r["wall_seconds"] for r in rows if r.get("cold") and "wall_seconds" in r), None),
               "rows": rows}
    json.dump(summary, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in summary.items() if k != "rows"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
