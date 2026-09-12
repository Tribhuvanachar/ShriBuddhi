#!/usr/bin/env python3
"""Kamadhenu Phase 1 — one row per audio file, in the columns the project brief asks for.

    python3 kamadhenu/scripts/build_audio_inventory.py

Reads the measurements the Kamadhenu audit already made (kamadhenu_dataset/audio_inventory.json — ffprobe/decode
per file; kamadhenu_dataset/metadata.jsonl — the text mapping + DGE Chandas verdict per file) and writes
kamadhenu/data/audio_inventory.csv plus the numbers for docs/AUDIO_INVENTORY.md. No audio is copied or re-read;
re-run `python3 tools/kamadhenu_audit.py` first if recordings were added."""
import csv, json, collections
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
DS = ROOT / "kamadhenu_dataset"
OUT = ROOT / "kamadhenu/data/audio_inventory.csv"

inv = {f["path"]: f for f in json.load(open(DS / "audio_inventory.json", encoding="utf-8"))["files"]}
recs = [json.loads(l) for l in open(DS / "metadata.jsonl", encoding="utf-8")]
by_audio = {r["audio"]: r for r in recs}
SOURCE = {"dge_linked": "DGE audio repo / archive.org (already linked to the reader)", "drive": "project lead's Google Drive folders"}
COLS = ["file_path", "filename", "format", "codec", "sample_rate", "channels", "bit_depth", "duration_s", "file_size", "peak_dbfs", "rms_dbfs",
        "snr_db_est", "clipping_runs", "quality_grade", "qc_flags", "exact_duplicate_of", "source", "folder", "speaker", "recording_type",
        "text_id", "text_first_words", "mapping_confidence", "mapping_signal", "review_status", "meter", "meter_confidence", "laghu_guru",
        "pada_count", "part", "usable_for_training"]
rows = []
for path, f in sorted(inv.items()):
    r = by_audio.get(path, {})
    top = f["folder"].split("/")[0]
    rtype = ("verse recitation" if r.get("part") in ("full", "half_1", "half_2") else "pāda" if str(r.get("part", "")).startswith("pada") else
             "long teaching-style recording" if (f.get("duration_seconds") or 0) > 45 else "unknown")
    usable = (f.get("quality_grade") in ("A", "B") and (r.get("mapping_confidence") or 0) >= 0.9 and r.get("duration_check") == "plausible"
              and not f.get("exact_duplicates"))
    rows.append({"file_path": path, "filename": f["file"], "format": f.get("container"), "codec": f.get("codec"), "sample_rate": f.get("sample_rate"),
                 "channels": f.get("channels"), "bit_depth": f.get("bit_depth"), "duration_s": f.get("duration_seconds"), "file_size": f.get("size"),
                 "peak_dbfs": f.get("peak_dbfs"), "rms_dbfs": f.get("rms_dbfs"), "snr_db_est": f.get("snr_db_est"), "clipping_runs": f.get("clip_runs"),
                 "quality_grade": f.get("quality_grade"), "qc_flags": ";".join(f.get("flags") or []), "exact_duplicate_of": ";".join(f.get("exact_duplicates") or []),
                 "source": SOURCE.get(top, top), "folder": f["folder"], "speaker": r.get("speaker", "unattributed"), "recording_type": rtype,
                 "text_id": r.get("text_id"), "text_first_words": (r.get("text") or "")[:40].replace("\n", " "), "mapping_confidence": r.get("mapping_confidence"),
                 "mapping_signal": r.get("mapping_signal"), "review_status": r.get("review_status"), "meter": r.get("chandas"), "meter_confidence": r.get("chandas_confidence"),
                 "laghu_guru": r.get("laghu_guru"), "pada_count": r.get("pada_count"), "part": r.get("part"), "usable_for_training": "yes" if usable else "no"})
OUT.parent.mkdir(parents=True, exist_ok=True)
with open(OUT, "w", encoding="utf-8", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=COLS); w.writeheader(); w.writerows(rows)

# numbers for the human report
H = lambda rs: round(sum(x["duration_s"] or 0 for x in rs) / 3600, 2)
paired = [x for x in rows if (x["mapping_confidence"] or 0) >= 0.7]
strong = [x for x in rows if (x["mapping_confidence"] or 0) >= 0.9]
usable = [x for x in rows if x["usable_for_training"] == "yes"]
with_meter = [x for x in paired if x["meter"] and x["meter"] != "अज्ञातम्" and (x["meter_confidence"] or 0) >= 0.6]
with_lg = [x for x in paired if x["laghu_guru"]]
stats = {"files": len(rows), "hours_total": H(rows), "hours_grade_A": H([x for x in rows if x["quality_grade"] == "A"]),
         "hours_grade_AB": H([x for x in rows if x["quality_grade"] in ("A", "B")]), "pairs_conf70": len(paired), "hours_pairs_conf70": H(paired),
         "pairs_conf90": len(strong), "hours_pairs_conf90": H(strong), "usable_for_training": len(usable), "hours_usable": H(usable),
         "pct_pairs_with_meter": round(100 * len(with_meter) / max(1, len(paired)), 1), "pct_pairs_with_laghu_guru": round(100 * len(with_lg) / max(1, len(paired)), 1),
         "unmatched_audio": len([x for x in rows if (x["mapping_confidence"] or 0) < 0.7]), "long_teaching_files": len([x for x in rows if x["recording_type"] == "long teaching-style recording"]),
         "exact_duplicates": len([x for x in rows if x["exact_duplicate_of"]]), "sample_rates": dict(collections.Counter(x["sample_rate"] for x in rows)),
         "by_folder_top": {k: {"files": len(v), "hours": H(v)} for k, v in sorted(collections.defaultdict(list, {k: [x for x in rows if x["folder"].split("/")[0] == k] for k in {x["folder"].split("/")[0] for x in rows}}).items())}}
json.dump(stats, open(ROOT / "kamadhenu/data/audio_inventory_stats.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(stats, ensure_ascii=False, indent=1))
