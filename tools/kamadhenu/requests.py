"""Section 16 — RECORDING_REQUESTS.csv derived from measured coverage (never asks for what already exists)."""
import re
from collections import defaultdict
from .common import DS, read_json, write_csv, log, COV_GOOD, COV_LIMITED, COV_NEEDS, COV_NONE

# Metres that matter first: what Vāgdhenu's production bank needed + the metres that dominate the indexed DGE corpus.
CORE = ["अनुष्टुप्", "उपजाति", "इन्द्रवज्रा", "उपेन्द्रवज्रा", "वंशस्थ", "इन्द्रवंशा", "वसन्ततिलका", "मालिनी", "शार्दूलविक्रीडित", "स्रग्धरा", "मन्दाक्रान्ता", "शिखरिणी", "रथोद्धता", "शालिनी", "द्रुतविलम्बित", "भुजङ्गप्रयात", "प्रमाणिका", "स्वागता", "प्रमिताक्षरा", "मञ्जुभाषिणी", "पृथ्वी", "हरिणी", "पुष्पिताग्रा", "आर्या"]


def run():
    cov = read_json(DS / "chandas_coverage.json", {"metres": []}); rb = read_json(DS / "reference_bank.json", {"entries": {}})
    ti = read_json(DS / "text_index.json", {"units": []})
    by_m = defaultdict(list)
    for u in ti["units"]:
        ca = u.get("chandas_analysis") or {}
        n = ca.get("chandas_inferred") or ca.get("chandas_normalized")
        if n and n != "अज्ञातम्" and ca.get("confidence", 0) >= 0.9 and u["work"] != "mahabharata_tatparya_nirnaya":
            by_m[re.sub(r"\s*\(.*$", "", n)].append(u)
    rows = []
    for m in cov["metres"]:
        name = m["chandas"]; texts = by_m.get(name, [])
        e = rb["entries"].get(name, {})
        strong = e.get("safe_as_reference")
        if m["coverage_status"] == COV_GOOD and strong:
            continue
        if not texts:
            if m["audio_examples"] == 0 and m["texts_in_dge_corpus"] == 0:
                rows.append({"text_id": "—", "text": "—", "chandas": name, "reason": "no text of this metre in the indexed DGE works; a text must be added to DGE before any recording", "priority": "P3", "suggested_recording_type": "none yet — provide text first", "count": 0, "unit": "—", "duration_target": "—"})
            continue
        core = name in CORE
        best = e.get("best") or {}
        weak_best = bool(best) and (best.get("quality") != "A" or (best.get("sample_rate") or 0) < 22050 or best.get("duration_check") != "plausible")
        if m["audio_examples"] == 0:
            pr = "P0" if core else "P1" if len(texts) >= 5 else "P2"
            why = "no audio at all for this metre" + (" (core metre: in Vāgdhenu's bank / frequent in the corpus)" if core else "")
        elif not strong or (core and weak_best):
            pr = "P0" if core else "P1"
            why = (f"{m['audio_examples']} recording(s) exist but the best one is not reference-grade: quality {best.get('quality')}, {best.get('sample_rate')} Hz, duration {best.get('duration_check')} — a clean single take in the Kamadhenu voice is needed"
                   if strong else f"{m['audio_examples']} recording(s) exist but none qualifies as a clean full-verse reference ({'; '.join(e.get('what_is_missing', [])[:2])})")
        elif m["coverage_status"] in (COV_NEEDS, COV_LIMITED):
            pr = "P1" if core else "P2"
            why = f"only {m['audio_examples']} recording(s) across {m['unique_texts_with_audio']} text(s); training-grade coverage wants ≥10 across ≥3 texts"
        else:
            continue
        n_req = 3 if pr == "P0" else 2
        picks = sorted(texts, key=lambda u: (0 if u["work"] in ("sumadhva_vijaya", "bhagavad_gita", "tirtha_prabandha") else 1, u["id"]))[:n_req]
        for u in picks:
            rows.append({"text_id": u["id"], "text": (u["metrical_text"] or u["text"]).replace("\n", " / "), "chandas": name, "reason": why, "priority": pr,
                         "suggested_recording_type": "reference (single clean rendition, full śloka, pause only at pāda ends / yati, 48 kHz 24-bit WAV, no drone)" if pr == "P0" else "training (natural pārāyaṇa pace, full śloka, one take)",
                         "count": n_req, "unit": "full śloka" if (u.get("chandas_analysis") or {}).get("pada_count") == 4 else "verse as written", "duration_target": f"≈{round(((u.get('chandas_analysis') or {}).get('syllable_count') or 32) * 0.33)}s"})
    order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    rows.sort(key=lambda r: (order[r["priority"]], r["chandas"], r["text_id"]))
    write_csv(DS / "RECORDING_REQUESTS.csv", rows, ["priority", "chandas", "text_id", "text", "unit", "count", "duration_target", "suggested_recording_type", "reason"])
    from collections import Counter
    log(f"recording requests: {dict(Counter(r['priority'] for r in rows))} rows")
    return rows


if __name__ == "__main__":
    run()
