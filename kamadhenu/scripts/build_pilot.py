#!/usr/bin/env python3
"""Kamadhenu Phase 6 — build the reproducible pilot dataset (100–200 excellent examples).

    python3 kamadhenu/scripts/build_pilot.py [--target 200] [--per-meter 25]

Reads kamadhenu_dataset/metadata.jsonl (the master audit output), converts records to the Kamadhenu schema
(kamadhenu/data/schema/kamadhenu_schema.json) and picks, deterministically:
  grade A audio (B only with --grades A,B; never C/D); text↔audio confidence ≥ 0.9; a named metre from the DGE engine;
  a full verse; 4–45 s; plausible pace; no duplicate audio or text; at most --per-meter per metre so that the
  pilot spans metres instead of being all anuṣṭubh.
Writes kamadhenu/data/pilot/manifest.jsonl (all selected), train.jsonl, validation.jsonl (every 10th, by id)."""
import argparse, collections, json, re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "kamadhenu_dataset/metadata.jsonl"
OUT = ROOT / "kamadhenu/data/pilot"


def to_schema(r):
    meter = r.get("chandas") or None
    kind = {"anushtubh_rule": "anushtubh_rule", "sama": "sama", "ardhasama": "ardhasama", "upajati": "upajati", "vishama": "vishama", "matra_jati": "matra_jati"}.get(
        (r.get("chandas_analysis") or {}).get("classification", ""), None)
    lg = r.get("laghu_guru") or None
    return {"id": r["id"], "text": r.get("text") or "", "normalized_text": r.get("normalized_text"), "audio": r["audio"], "audio_sha1": None,
            "duration": r.get("duration_seconds"), "sample_rate": r.get("sample_rate"), "channels": r.get("channels"),
            "speaker": "unattributed:" + r["audio"].split("/")[2] if "unattributed" in str(r.get("speaker", "")) else r.get("speaker"),
            "source": r["audio"].split("/")[2] if r["audio"].startswith("kamadhenu_dataset/incoming_audio/") else "other",
            "script": "Devanagari", "language": "sa", "text_id": r.get("text_id"), "work": r.get("work"), "part": r.get("part"),
            "meter": meter, "meter_confidence": r.get("chandas_confidence"), "meter_kind": kind, "pada_count": r.get("pada_count"),
            "pada_text": [x for x in (r.get("text") or "").split("\n") if x.strip()] or None, "laghu_guru": lg, "gana": r.get("gana"),
            "syllables": r.get("syllable_count"), "syllables_per_pada": [len(x) for x in lg.split("|")] if lg else None, "yati": r.get("yati") or None,
            "chandas_source": "dge_engine" if meter else None, "recording_quality": r.get("audio_quality"), "snr_db": r.get("snr_db_est"),
            "peak_dbfs": None, "clipping": None, "text_audio_confidence": r.get("mapping_confidence"),
            "verified_by": "structure" if r.get("review_status") == "auto_accepted" else None, "split": None, "exclusion_reason": None, "notes": None}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--target", type=int, default=200); ap.add_argument("--per-meter", type=int, default=25)
    ap.add_argument("--grades", default="A", help="audio grades allowed; default A only (A,B adds the 11 kHz Sumadhva Vijaya files)"); a = ap.parse_args()
    grades = set(a.grades.split(","))
    recs = [json.loads(l) for l in open(SRC, encoding="utf-8")]
    cands = []
    for r in recs:
        if r.get("audio_quality") not in grades: continue
        if (r.get("mapping_confidence") or 0) < 0.9 or r.get("duration_check") != "plausible": continue
        if not r.get("chandas") or r["chandas"] == "अज्ञातम्" or (r.get("chandas_confidence") or 0) < 0.9: continue
        if r.get("part") != "full": continue
        d = r.get("duration_seconds") or 0
        if not 4 <= d <= 45: continue
        if r.get("qc_flags"): continue
        cands.append(r)
    # deterministic order: grade A first, then higher SNR, then id
    cands.sort(key=lambda r: (0 if r["audio_quality"] == "A" else 1, -(r.get("snr_db_est") or 0), r["id"]))
    seen_text, per_meter, picked = set(), collections.Counter(), []
    for r in cands:
        key = re.sub(r"[^ऀ-ॿ]", "", r.get("text") or "")
        m = re.sub(r"\s*\(.*?\)\s*|\s*—.*$", "", r["chandas"]).strip()
        if key in seen_text or per_meter[m] >= a.per_meter: continue
        seen_text.add(key); per_meter[m] += 1; picked.append(r)
        if len(picked) >= a.target: break
    OUT.mkdir(parents=True, exist_ok=True)
    rows = [to_schema(r) for r in picked]
    rows.sort(key=lambda x: x["id"])
    for i, x in enumerate(rows): x["split"] = "validation" if i % 10 == 9 else "train"
    for name, sel in (("manifest.jsonl", rows), ("train.jsonl", [x for x in rows if x["split"] == "train"]), ("validation.jsonl", [x for x in rows if x["split"] == "validation"])):
        with open(OUT / name, "w", encoding="utf-8") as fh:
            for x in sel: fh.write(json.dumps(x, ensure_ascii=False) + "\n")
    summary = {"built_at": datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d %b %Y, %I:%M %p IST"), "candidates": len(cands), "selected": len(rows),
               "train": sum(1 for x in rows if x["split"] == "train"), "validation": sum(1 for x in rows if x["split"] == "validation"),
               "hours": round(sum(x["duration"] or 0 for x in rows) / 3600, 2), "by_grade": dict(collections.Counter(x["recording_quality"] for x in rows)),
               "by_work": dict(collections.Counter(x["work"] for x in rows)), "by_meter": dict(per_meter.most_common()), "criteria": vars(a)}
    json.dump(summary, open(OUT / "summary.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
