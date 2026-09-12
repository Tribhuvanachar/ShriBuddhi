"""Stage 10 — Chandas reference bank: for every metre pick the best available recording (and alternatives)
by mapping confidence, QC grade/SNR, duration plausibility and full-verse-ness; say honestly whether the
reference can be trusted (text = audio has NOT been verified by ear unless a human override says so)."""
import json
from collections import defaultdict
from .common import DS, write_json, read_json, write_csv, write_text, html_page, table_html, esc, log, now_ist, DONE, VERIFIED, PARTIAL, NOT_STARTED, BLOCKED, FILTER_JS


def score(r, inv):
    q = {"A": 4, "B": 3, "C": 1, "D": 0, "F": -5}.get(inv.get("quality_grade", "F"), 0)
    s = r["confidence"] * 10 + q + min((inv.get("snr_db_est") or 0) / 10, 4)
    if r["duration_check"] == "plausible": s += 3
    if r["part"] == "full": s += 2
    if (inv.get("sample_rate") or 0) >= 22050: s += 1
    if "clipping" in inv.get("flags", []): s -= 2
    if inv.get("leading_silence_s", 0) > 1.5 or inv.get("trailing_silence_s", 0) > 1.5: s -= 1
    return round(s, 2)


def run():
    inv = {f["path"]: f for f in read_json(DS / "audio_inventory.json", {"files": []})["files"]}
    mp = read_json(DS / "audio_text_mapping.json", {"mappings": []})
    units = {u["id"]: u for u in read_json(DS / "text_index.json", {"units": []})["units"]}
    cov = read_json(DS / "chandas_coverage.json", {"metres": []})
    by_m = defaultdict(list)
    for r in mp["mappings"]:
        if not r.get("text_id") or r["confidence"] < 0.7: continue
        u = units.get(r["text_id"]); ca = (u or {}).get("chandas_analysis") or {}
        name = ca.get("chandas_inferred") or ca.get("chandas_normalized")
        if not name or name == "अज्ञातम्": continue
        i = inv.get(r["audio"], {})
        by_m[name].append((score(r, i), r, i, ca))
    entries = {}
    for name, lst in by_m.items():
        lst.sort(key=lambda x: -x[0])
        best_s, best, bi, ca = lst[0]
        alts = [{"audio": r["audio"], "score": s, "confidence": r["confidence"], "quality": i.get("quality_grade"), "duration_seconds": i.get("duration_seconds"), "text_id": r["text_id"]} for s, r, i, _ in lst[1:6]]
        safe = best["confidence"] >= 0.9 and bi.get("quality_grade") in ("A", "B") and best["duration_check"] == "plausible" and best["part"] == "full"
        verified = best.get("review_status") == "verified_by_human"
        status = VERIFIED if verified and safe else PARTIAL if safe else PARTIAL if best["confidence"] >= 0.7 else NOT_STARTED
        missing = []
        if not verified: missing.append("human confirmation that the audio speaks exactly this text (listen once)")
        if bi.get("quality_grade") not in ("A", "B"): missing.append(f"cleaner recording (grade {bi.get('quality_grade')}: {', '.join(bi.get('flags', []))})")
        if best["duration_check"] != "plausible": missing.append(f"single-rendition clip ({best['duration_note']})")
        if best["part"] != "full": missing.append("a full-verse (or clean hemistich) take; only a part is available")
        if (bi.get("sample_rate") or 0) < 22050: missing.append(f"≥24 kHz source (this one is {bi.get('sample_rate')} Hz)")
        if not ca.get("yati"): missing.append("yati not in DGE DB for this metre (no pause guidance)")
        entries[name] = {"chandas": name, "best": {"audio": best["audio"], "text_id": best["text_id"], "text": best["text"], "score": best_s, "confidence": best["confidence"], "quality": bi.get("quality_grade"),
                                                   "duration_seconds": bi.get("duration_seconds"), "sample_rate": bi.get("sample_rate"), "snr_db_est": bi.get("snr_db_est"), "part": best["part"], "duration_check": best["duration_check"]},
                         "alternatives": alts, "recordings": len(lst), "lg_pattern": ca.get("laghu_guru"), "syllable_count": ca.get("syllable_count"), "pada_count": ca.get("pada_count"), "yati": ca.get("yati"),
                         "cleanest_audio": max(lst, key=lambda x: (x[2].get("snr_db_est") or 0))[1]["audio"],
                         "pada_boundaries_known": bool(ca.get("pada_count") == 4 and ca.get("equal_padas")), "safe_as_reference": safe, "text_matches_audio_verified": verified, "status": status,
                         "what_is_missing": missing or ["nothing — but keep the human listen-check"]}
    # metres with no audio at all
    for m in cov.get("metres", []):
        if m["chandas"] not in entries:
            entries[m["chandas"]] = {"chandas": m["chandas"], "best": None, "alternatives": [], "recordings": 0, "lg_pattern": m.get("lg"), "syllable_count": m.get("syllables_per_pada"), "pada_count": 4 if m.get("kind") in ("sama", "upajati", "anushtubh_rule") else None,
                                    "yati": None, "cleanest_audio": None, "pada_boundaries_known": False, "safe_as_reference": False, "text_matches_audio_verified": False,
                                    "status": NOT_STARTED if m["texts_in_dge_corpus"] else BLOCKED, "what_is_missing": ["no recording mapped to any text of this metre" + ("" if m["texts_in_dge_corpus"] else " AND no text of this metre in the indexed DGE works — needs a text before a recording")]}
    order = sorted(entries.values(), key=lambda e: (-e["recordings"], e["chandas"]))
    summary = {"generated_at": now_ist(), "metres_with_candidate": sum(1 for e in order if e["best"]), "metres_safe_reference": sum(1 for e in order if e["safe_as_reference"]),
               "metres_human_verified": sum(1 for e in order if e["text_matches_audio_verified"]), "metres_total": len(order),
               "vagdhenu_bank_note": "Vāgdhenu ships 16 metre references in Prof. Prathosh's voice (src/reference_bank/bank.json). They are a working model of the format, not Kamadhenu references — the speaker differs."}
    out = {"_readme": "Best/alternative recordings per metre. safe_as_reference is structural; text_matches_audio_verified is only true after a human override (mapping_overrides.json verified:true).", "summary": summary, "entries": {e["chandas"]: e for e in order}}
    write_json(DS / "reference_bank.json", out)
    rows = [{"chandas": e["chandas"], "best_reference": (e["best"] or {}).get("audio", "—"), "alternatives": len(e["alternatives"]), "recordings": e["recordings"], "duration": (e["best"] or {}).get("duration_seconds"),
             "lg_pattern": e["lg_pattern"], "quality": (e["best"] or {}).get("quality"), "confidence": (e["best"] or {}).get("confidence"), "status": e["status"], "what_is_missing": "; ".join(e["what_is_missing"])} for e in order]
    write_csv(DS / "reference_bank.csv", rows)
    body = ["<div class='cards'>"] + [f"<div class='card'><b>{v}</b><span>{esc(k.replace('_',' '))}</span></div>" for k, v in summary.items() if isinstance(v, int)] + ["</div>",
            f"<div class='note'>{esc(summary['vagdhenu_bank_note'])} Naming a file after a metre does not make it a reference: every entry below still needs a human listen-check before it is used.</div>",
            "<input type='search' placeholder='filter…' onkeyup=\"kmFilter(this,'rb')\">",
            table_html(rows, ["chandas", "best_reference", "alternatives", "duration", "lg_pattern", "quality", "confidence", "status", "what_is_missing"], dev_fields=("chandas",), mono_fields=("best_reference", "lg_pattern"), id_attr="rb"), FILTER_JS]
    write_text(DS / "reference_bank.html", html_page("Kamadhenu — Chandas reference bank", "".join(body), "Chandas | best reference | alternatives | duration | L/G | quality | confidence | status | missing"))
    log(f"reference bank: {summary}")
    return out


if __name__ == "__main__":
    run()
