"""Stage 17 — dataset health report (json + html)."""
import json, statistics
from collections import Counter
from .common import DS, write_json, read_json, write_text, html_page, table_html, esc, log, now_ist, fmt_dur


def hist(vals, edges):
    out = Counter()
    for v in vals:
        if v is None: out["unknown"] += 1; continue
        for lo, hi in zip(edges, edges[1:] + [None]):
            if hi is None or v < hi:
                out[f"{lo}–{hi}" if hi else f"≥{lo}"] += 1; break
    return dict(out)


def run():
    inv = read_json(DS / "audio_inventory.json", {"files": [], "summary": {}})
    mp = read_json(DS / "audio_text_mapping.json", {"mappings": [], "summary": {}, "unmatched_texts": []})
    ds = read_json(DS / "dataset_summary.json", {"subset_sizes": {}})
    rb = read_json(DS / "reference_bank.json", {"summary": {}})
    ext = read_json(DS / "external_audio_sources.json", {"totals": {}})
    files = inv["files"]; maps = mp["mappings"]
    durs = [f.get("duration_seconds") for f in files if f.get("duration_seconds")]
    works = {m.get("work") for m in maps if m.get("text_id") and m["confidence"] >= 0.5}
    metres = {m.get("chandas") for m in maps if m.get("text_id") and m["confidence"] >= 0.5 and m.get("chandas") and m["chandas"] != "अज्ञातम्"}
    units = {u["id"]: u for u in read_json(DS / "text_index.json", {"units": []})["units"]}
    patterns = {(units.get(m["text_id"]) or {}).get("chandas_analysis", {}).get("laghu_guru") for m in maps if m.get("text_id")} - {None, ""}
    rep = {
        "generated_at": now_ist(),
        "external_sources": ext.get("totals", {}),
        "total_audio_files": len(files), "total_duration": fmt_dur(sum(durs)), "total_duration_seconds": round(sum(durs), 1),
        "mapped_recordings": sum(1 for m in maps if m.get("text_id") and m["confidence"] >= 0.5),
        "unmatched_recordings": sum(1 for m in maps if not (m.get("text_id") and m["confidence"] >= 0.5)),
        "unmatched_corpus_texts": len(mp.get("unmatched_texts", [])),
        "high_confidence_mappings(>=0.90)": sum(1 for m in maps if m["confidence"] >= 0.9),
        "needing_review": sum(1 for m in maps if m.get("review_status") == "review"),
        "usable_training_examples": ds["subset_sizes"].get("dataset_training", 0), "usable_validation_examples": ds["subset_sizes"].get("dataset_validation", 0),
        "usable_reference_examples": rb.get("summary", {}).get("metres_safe_reference", 0),
        "unique_works": len(works - {None}), "unique_metres": len(metres), "unique_syllable_patterns": len(patterns),
        "speaker_count": "unknown — no speaker metadata in any source (folders used as proxy: %d)" % len({f["folder"].split("/")[0] + "/" + f["folder"].split("/")[1] if "/" in f["folder"] else f["folder"] for f in files}),
        "sample_rate_distribution": dict(Counter(f.get("sample_rate") for f in files)), "channel_distribution": dict(Counter(f.get("channels") for f in files)),
        "codec_distribution": dict(Counter((f.get("codec") or "?").split(" ")[0] for f in files)),
        "duration_distribution_seconds": hist(durs, [0, 5, 10, 20, 40, 60, 120, 300]),
        "audio_quality_failures": {k: v for k, v in inv.get("summary", {}).get("flags", {}).items()}, "quality_grades": inv.get("summary", {}).get("by_grade", {}),
        "clipping": sum(1 for f in files if "clipping" in f.get("flags", [])),
        "excessive_silence": sum(1 for f in files if any(x in f.get("flags", []) for x in ("long_leading_silence", "long_trailing_silence", "long_internal_silence", "mostly_silence"))),
        "exact_duplicates": sum(1 for f in files if f.get("exact_duplicates")), "likely_duplicates": sum(1 for f in files if f.get("likely_duplicates") and not f.get("exact_duplicates")),
        "decode_errors": inv.get("summary", {}).get("decode_errors", 0),
        "measurement_notes": ["loudness is RMS-based dBFS, not LUFS (no K-weighting implemented)", "SNR is a percentile estimate (90th − 10th percentile frame energy), not a speech/noise separation",
                              "duplicates: exact = identical bytes; likely = identical coarse energy-envelope fingerprint", "no ASR/forced alignment was run"],
    }
    write_json(DS / "dataset_health_report.json", rep)
    body = ["<div class='cards'>"] + [f"<div class='card'><b>{esc(v)}</b><span>{esc(k.replace('_',' '))}</span></div>" for k, v in rep.items() if isinstance(v, (int, str)) and k not in ("generated_at",)] + ["</div>"]
    for k in ("sample_rate_distribution", "channel_distribution", "codec_distribution", "duration_distribution_seconds", "audio_quality_failures", "quality_grades", "external_sources"):
        body.append(f"<h2>{esc(k.replace('_',' '))}</h2>" + table_html([{"value": kk, "count": vv} for kk, vv in rep[k].items()], ["value", "count"]))
    body.append("<h2>measurement notes</h2><ul>" + "".join(f"<li>{esc(n)}</li>" for n in rep["measurement_notes"]) + "</ul>")
    write_text(DS / "dataset_health_report.html", html_page("Kamadhenu — dataset health", "".join(body), "measured, not estimated"))
    log(f"health: {rep['total_audio_files']} files, {rep['total_duration']}, mapped {rep['mapped_recordings']}, review {rep['needing_review']}")
    return rep


if __name__ == "__main__":
    run()
