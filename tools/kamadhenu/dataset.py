"""Stage 8/9 — master dataset (metadata.jsonl/csv) + logical subsets with an explicit reason for every exclusion."""
import json
from collections import Counter
from .common import DS, write_json, read_json, write_csv, write_jsonl, log, now_ist

SUBSETS = ["dataset_all", "dataset_verified", "dataset_high_quality", "dataset_reference_bank", "dataset_training", "dataset_validation", "dataset_review", "dataset_unmatched_audio", "dataset_unmatched_text"]


_SPK = None


def speaker_for(folder):
    """kamadhenu_dataset/speakers.json: longest matching folder prefix → speaker id; else '<folder> (unattributed)'."""
    global _SPK
    if _SPK is None:
        _SPK = read_json(DS / "speakers.json", {}).get("by_folder", {})
    best = max((k for k in _SPK if folder.startswith(k)), key=len, default=None)
    if best: return _SPK[best]
    parts = folder.split("/")
    return parts[0] + ":" + (parts[1] if len(parts) > 1 else "") + " (unattributed)"


def record(r, inv, u):
    ca = (u or {}).get("chandas_analysis") or {}
    return {
        "id": f"km_{inv.get('sha1','')[:12]}", "audio": r["audio"], "text_id": r.get("text_id"),
        "text": r.get("text") or "", "normalized_text": (u or {}).get("slp1", ""), "phonetic_key": (u or {}).get("phonetic_key", ""),
        "work": r.get("work") or r.get("work_guess"), "section": r.get("section") or r.get("section_guess"), "chapter": (u or {}).get("chapter"), "verse_id": r.get("verse_id") or r.get("verse_guess"),
        "part": r.get("part"), "chandas": ca.get("chandas_inferred") or ca.get("chandas_normalized") or "", "chandas_engine_verdict": ca.get("chandas", ""), "chandas_confidence": ca.get("confidence"),
        "pada_count": ca.get("pada_count"), "syllable_count": ca.get("syllable_count"), "laghu_guru": ca.get("laghu_guru", ""), "gana": ca.get("gana", ""), "yati": ca.get("yati", []),
        "speaker": speaker_for(inv.get("folder", "")),
        "duration_seconds": inv.get("duration_seconds"), "sample_rate": inv.get("sample_rate"), "channels": inv.get("channels"), "bit_depth": inv.get("bit_depth"), "codec": inv.get("codec"),
        "audio_quality": inv.get("quality_grade"), "qc_flags": inv.get("flags", []), "snr_db_est": inv.get("snr_db_est"),
        "mapping_confidence": r.get("confidence", 0.0), "mapping_signal": r.get("signal"), "duration_check": r.get("duration_check"), "review_status": r.get("review_status"), "review_reason": r.get("review_reason", ""),
    }


def run():
    inv = {f["path"]: f for f in read_json(DS / "audio_inventory.json", {"files": []})["files"]}
    mp = read_json(DS / "audio_text_mapping.json", {"mappings": [], "unmatched_texts": []})
    units = {u["id"]: u for u in read_json(DS / "text_index.json", {"units": []})["units"]}
    rb = read_json(DS / "reference_bank.json", {"entries": {}}) or {"entries": {}}
    ref_audio = {e.get("best", {}).get("audio") for e in rb["entries"].values() if e.get("best")} | {a["audio"] for e in rb["entries"].values() for a in e.get("alternatives", [])}
    rows = [record(r, inv.get(r["audio"], {}), units.get(r.get("text_id"))) for r in mp["mappings"]]
    write_jsonl(DS / "metadata.jsonl", rows)
    write_csv(DS / "metadata.csv", rows)
    sub = {k: [] for k in SUBSETS}; excl = {k: [] for k in SUBSETS}
    spk = read_json(DS / "speakers.json", {}).get("speakers", {})
    for r in rows:
        sub["dataset_all"].append(r["id"])
        if spk.get(r["speaker"], {}).get("consent_to_train_voice") is False:
            excl["dataset_verified"].append({"id": r["id"], "reason": f"speaker {r['speaker']}: not the Kamadhenu voice, no consent — excluded from every subset"}); continue
        mapped = bool(r["text_id"]) and r["mapping_confidence"] >= 0.5
        if not mapped:
            sub["dataset_unmatched_audio"].append(r["id"]); continue
        if r["review_status"] in ("auto_accepted", "verified_by_human"):
            sub["dataset_verified"].append(r["id"])
        else:
            sub["dataset_review"].append(r["id"]); excl["dataset_verified"].append({"id": r["id"], "reason": f"review_status={r['review_status']}: {r['review_reason'] or r['duration_check']}"})
        q = r["audio_quality"] or "F"
        if q in "AB" and r["review_status"] in ("auto_accepted", "verified_by_human") and r["duration_check"] == "plausible" and r["part"] == "full":
            sub["dataset_high_quality"].append(r["id"])
        else:
            why = []
            if q not in "AB": why.append(f"audio_quality={q} ({', '.join(r['qc_flags']) or 'low-rate source'})")
            if r["duration_check"] != "plausible": why.append(f"duration {r['duration_check']}")
            if r["part"] != "full": why.append(f"part={r['part']} (not a full verse)")
            if r["review_status"] not in ("auto_accepted", "verified_by_human"): why.append("not verified")
            excl["dataset_high_quality"].append({"id": r["id"], "reason": "; ".join(why)})
        if r["audio"] in ref_audio:
            sub["dataset_reference_bank"].append(r["id"])
    # training/validation split: deterministic by id hash, from high-quality only; validation = every 10th
    hq = sorted(sub["dataset_high_quality"])
    for i, rid in enumerate(hq):
        (sub["dataset_validation"] if i % 10 == 9 else sub["dataset_training"]).append(rid)
    excl["dataset_training"].append({"id": "*", "reason": "only dataset_high_quality members are eligible; everything excluded from it is excluded here for the same reason"})
    sub["dataset_unmatched_text"] = [t["text_id"] for t in mp.get("unmatched_texts", [])]
    meta = {"generated_at": now_ist(), "records": len(rows), "subset_sizes": {k: len(v) for k, v in sub.items()},
            "notes": {"dataset_training/validation": "deterministic 90/10 split of dataset_high_quality (validation = every 10th by sorted id). Training has NOT been run.",
                      "speaker": "speaker identity is not recorded anywhere in the sources; the folder is used as a proxy and marked 'unattributed'",
                      "sample_rate": "reported at the source's native rate; nothing is resampled here"}}
    write_json(DS / "subsets" / "subsets.json", {"summary": meta, "subsets": sub, "exclusions": excl})
    for k, ids in sub.items():   # subsets hold references only (id + audio path + text id); full rows live once in metadata.jsonl
        ids_set = set(ids)
        write_jsonl(DS / "subsets" / f"{k}.jsonl", [{"id": r["id"], "audio": r["audio"], "text_id": r["text_id"]} for r in rows if r["id"] in ids_set] if k != "dataset_unmatched_text" else [{"text_id": t} for t in ids])
    write_json(DS / "dataset_summary.json", meta)
    log(f"dataset: {len(rows)} records; subsets {meta['subset_sizes']}")
    return meta


if __name__ == "__main__":
    run()
