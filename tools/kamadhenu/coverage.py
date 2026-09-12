"""Stage 7 — Chandas coverage: for every metre in the DGE database, how much audio exists, how many
unique texts, how many pādas; plus the 7-tier coverage target (section 18) that separates
'exists in DGE' / 'has usable audio' / 'has a strong TTS reference'."""
import json, re
from collections import defaultdict
from .common import DS, DGE, write_json, read_json, write_csv, write_text, html_page, table_html, esc, log, now_ist, COV_GOOD, COV_LIMITED, COV_NEEDS, COV_NONE, FILTER_JS

# Why these numbers: Vāgdhenu's bank needs ONE clean half-verse reference per metre (half-reference rule) and
# its held-out tests used 4 verses/metre; its recording sheet targeted 10 verses/metre for a meter-diverse set.
# So: ≥10 mapped recordings across ≥3 unique texts = GOOD; 3–9 = LIMITED; 1–2 = NEEDS MORE; 0 = NO AUDIO.
GOOD_N, LIMITED_N = 10, 3


def dge_metres():
    db = read_json(DGE / "data/vedanga/chandas/data.json")
    out = []
    for grp, kind in (("sama_vrutta", "sama"), ("ardhasama_vrutta", "ardhasama"), ("vishama_vrutta", "vishama"), ("upajati_vrutta", "upajati"), ("matra_vrutta", "matra")):
        for v in db.get(grp, []):
            names = v.get("vrutta_names") or []
            pats = [p.get("lakshana_raw", "") for p in v.get("padas", [])] if "padas" in v else [v.get("lakshana", "")]
            out.append({"name": names[0] if names else "?", "aliases": names[1:], "kind": kind,
                        "lg": "|".join("".join("G" if c == "ग" else "L" for c in p) for p in pats),
                        "syllables_per_pada": v.get("akshara_sankhya") or (v["padas"][0].get("akshara_sankhya") if v.get("padas") else None),
                        "gana": v.get("gana", ""), "yati": v.get("yati", [])})
    out.append({"name": "अनुष्टुप्", "aliases": ["श्लोकः"], "kind": "anushtubh_rule", "lg": "rule: 5th L, 6th G; 7th L in even pādas (pathyā)", "syllables_per_pada": 8, "gana": "", "yati": []})
    return out


def status_for(n_audio, n_texts):
    if n_audio == 0: return COV_NONE
    if n_audio >= GOOD_N and n_texts >= 3: return COV_GOOD
    if n_audio >= LIMITED_N: return COV_LIMITED
    return COV_NEEDS


def run():
    ti = read_json(DS / "text_index.json", {"units": []}); mp = read_json(DS / "audio_text_mapping.json", {"mappings": []})
    rb = read_json(DS / "reference_bank.json", {"entries": {}}) or {"entries": {}}
    metres = dge_metres()
    alias = {}
    for m in metres:
        for n in [m["name"]] + m["aliases"]:
            alias[re.sub(r"म्$", "", n)] = m["name"]
    def canon(n):
        n = re.sub(r"\s*\(.*$", "", n or "").strip()
        return alias.get(re.sub(r"म्$", "", n), n)
    texts_by_m = defaultdict(set); audio_by_m = defaultdict(list); padas_by_m = defaultdict(int); speakers = defaultdict(set)
    unit = {u["id"]: u for u in ti["units"]}
    for u in ti["units"]:
        ca = u.get("chandas_analysis") or {}
        name = canon(ca.get("chandas_inferred") or ca.get("chandas_normalized"))
        if name and name != "अज्ञातम्":
            texts_by_m[name].add(u["id"])
    for r in mp["mappings"]:
        if not r.get("text_id") or r["confidence"] < 0.7:
            continue
        u = unit.get(r["text_id"]); ca = (u or {}).get("chandas_analysis") or {}
        name = canon(ca.get("chandas_inferred") or ca.get("chandas_normalized"))
        if not name or name == "अज्ञातम्": continue
        audio_by_m[name].append(r)
        padas_by_m[name] += ca.get("pada_count", 0) if r["part"] == "full" else (2 if str(r["part"]).startswith("half") else 1)
        speakers[name].add(r["folder"].split("/")[0] + "/" + r["folder"].split("/")[1] if "/" in r["folder"] else r["folder"])
    rows = []
    for m in metres:
        n = m["name"]; a = audio_by_m.get(n, [])
        rows.append({"chandas": n, "kind": m["kind"], "syllables_per_pada": m["syllables_per_pada"], "lg": m["lg"], "exists_in_dge": True,
                     "texts_in_dge_corpus": len(texts_by_m.get(n, [])), "audio_examples": len(a), "unique_texts_with_audio": len({r["text_id"] for r in a}),
                     "padas_with_audio": padas_by_m.get(n, 0), "high_confidence_audio": sum(1 for r in a if r["confidence"] >= 0.9),
                     "quality_A_or_B": sum(1 for r in a if (r.get("audio_quality") or "F") in "AB"), "speaker_groups": len(speakers.get(n, [])),
                     "has_strong_reference": bool((rb["entries"].get(n) or {}).get("safe_as_reference")), "reference_human_verified": bool((rb["entries"].get(n) or {}).get("text_matches_audio_verified")),
                     "coverage_status": status_for(len(a), len({r["text_id"] for r in a}))})
    # metres seen in texts but not in DB (e.g. inferred labels)
    for n, ids in texts_by_m.items():
        if n not in {r["chandas"] for r in rows}:
            a = audio_by_m.get(n, [])
            rows.append({"chandas": n, "kind": "inferred/label", "syllables_per_pada": None, "lg": "", "exists_in_dge": False, "texts_in_dge_corpus": len(ids), "audio_examples": len(a),
                         "unique_texts_with_audio": len({r["text_id"] for r in a}), "padas_with_audio": padas_by_m.get(n, 0), "high_confidence_audio": sum(1 for r in a if r["confidence"] >= 0.9),
                         "quality_A_or_B": sum(1 for r in a if (r.get("audio_quality") or "F") in "AB"), "speaker_groups": len(speakers.get(n, [])), "has_strong_reference": False, "coverage_status": status_for(len(a), len({r["text_id"] for r in a}))})
    rows.sort(key=lambda r: (-r["audio_examples"], -r["texts_in_dge_corpus"], r["chandas"]))
    db_rows = [r for r in rows if r["exists_in_dge"]]
    N = len(db_rows)
    tiers = {
        "1_at_least_one_recording": sum(1 for r in db_rows if r["audio_examples"] >= 1),
        "2_multiple_recordings": sum(1 for r in db_rows if r["audio_examples"] >= 2),
        "3_high_quality_reference": sum(1 for r in db_rows if r["has_strong_reference"]),
        "3b_reference_human_verified": sum(1 for r in db_rows if r.get("reference_human_verified")),
        "4_multiple_speakers": sum(1 for r in db_rows if r["speaker_groups"] >= 2),
        "5_exact_pada_level_reference": sum(1 for r in db_rows if (rb["entries"].get(r["chandas"]) or {}).get("pada_boundaries_known") and r["has_strong_reference"]),
        "6_insufficient_evidence": sum(1 for r in db_rows if 1 <= r["audio_examples"] < LIMITED_N),
        "7_completely_missing": sum(1 for r in db_rows if r["audio_examples"] == 0),
    }
    pct = {k: round(100 * v / N, 1) for k, v in tiers.items()}
    three = {"chandas_exists_in_dge": N, "chandas_with_text_in_indexed_corpus": sum(1 for r in db_rows if r["texts_in_dge_corpus"] > 0),
             "chandas_with_usable_audio": sum(1 for r in db_rows if r["audio_examples"] >= 1 and r["quality_A_or_B"] >= 1),
             "chandas_with_strong_tts_reference": tiers["3_high_quality_reference"], "chandas_with_human_verified_reference": tiers["3b_reference_human_verified"],
             "note": "strong reference = structurally safe (confidence ≥0.9, grade A/B, plausible duration, full verse); it is NOT a listened/verified reference until a human marks it"}
    summary = {"generated_at": now_ist(), "metres_in_dge_db": N, "thresholds": {"GOOD": f"≥{GOOD_N} recordings across ≥3 texts", "LIMITED": f"{LIMITED_N}–{GOOD_N-1}", "NEEDS_MORE": f"1–{LIMITED_N-1}", "NO_AUDIO": "0",
                                                                                     "why": "Vāgdhenu needs one clean half-verse reference per metre; its held-out tests used 4 verses/metre and its recording sheet targeted 10/metre"},
               "status_counts": {s: sum(1 for r in db_rows if r["coverage_status"] == s) for s in (COV_GOOD, COV_LIMITED, COV_NEEDS, COV_NONE)},
               "tiers": tiers, "tiers_percent": pct, "three_distinct_things": three}
    out = {"_readme": "Per-metre audio coverage computed from audio_text_mapping (confidence ≥0.70) and the DGE Chandas engine's verdict on each mapped text.", "summary": summary, "metres": rows}
    write_json(DS / "chandas_coverage.json", out)
    write_csv(DS / "chandas_coverage.csv", rows)
    body = ["<div class='cards'>"] + [f"<div class='card'><b>{v}</b><span>{esc(k)}</span></div>" for k, v in summary["status_counts"].items()] + ["</div>"]
    body.append("<h2>Three different things</h2><div class='cards'>" + "".join(f"<div class='card'><b>{v}</b><span>{esc(k.replace('_',' '))}</span></div>" for k, v in three.items()) + "</div>")
    body.append("<h2>Coverage tiers (of %d metres in the DGE database)</h2>" % N + table_html([{"tier": k.replace("_", " "), "metres": v, "percent": f"{pct[k]}%"} for k, v in tiers.items()], ["tier", "metres", "percent"]))
    body.append(f"<div class='note'>Thresholds: {esc(summary['thresholds']['why'])}. GOOD = {esc(summary['thresholds']['GOOD'])}; LIMITED = {LIMITED_N}–{GOOD_N-1}; NEEDS MORE = 1–{LIMITED_N-1}; NO AUDIO = 0.</div>")
    body.append("<input type='search' placeholder='filter metre…' onkeyup=\"kmFilter(this,'cov')\">")
    body.append(table_html(rows, ["chandas", "kind", "syllables_per_pada", "audio_examples", "unique_texts_with_audio", "padas_with_audio", "high_confidence_audio", "quality_A_or_B", "texts_in_dge_corpus", "has_strong_reference", "coverage_status", "lg"], dev_fields=("chandas",), mono_fields=("lg",), id_attr="cov") + FILTER_JS)
    write_text(DS / "chandas_coverage.html", html_page("Kamadhenu — Chandas coverage", "".join(body), "Chandas | audio examples | unique texts | pādas | coverage status"))
    log(f"coverage: {summary['status_counts']}; tiers {tiers}")
    return out


if __name__ == "__main__":
    run()
