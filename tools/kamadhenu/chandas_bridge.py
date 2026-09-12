"""Stage 5 — run the EXISTING DGE Chandas engine (js/chandas.js, unmodified) headlessly over text units.

The engine is browser JS; chandas_runner.js stubs three globals and loads the same data.json the site
uses, so results are identical to vyakarana/chandas.html. Results are cached by text hash in
processed/chandas_cache.json. No competing metre engine is introduced here."""
import hashlib, json, re, subprocess, sys
from pathlib import Path
from .common import ROOT, DS, PROCESSED, TOOLS, write_json, read_json, log, now_ist

RUNNER = TOOLS / "chandas_runner.js"
GANA_LETTERS = "यमतरजभनसलग"


def _hash(t):
    return hashlib.sha1(t.encode("utf-8")).hexdigest()[:20]


def _run_node(texts):
    r = subprocess.run(["node", str(RUNNER)], input=json.dumps(texts, ensure_ascii=False), capture_output=True, text=True, cwd=str(ROOT))
    if r.returncode != 0:
        raise RuntimeError("node runner failed: " + r.stderr[-500:])
    return json.loads(r.stdout)


def normalise_name(name):
    """Strip the anuṣṭubh pathyā/vipulā suffix and the '(N भेदौ)' decoration; keep the Devanagari name."""
    n = re.sub(r"\s*\(.*?\)\s*", "", name or "")
    n = re.sub(r"\s*—.*$", "", n).strip()
    return n


def summarise(res):
    """Flatten one analyzeText() result into the fields the dataset needs."""
    m = res.get("match") or {}
    padas = res.get("padas") or []
    names = m.get("names") or []
    kind = m.get("kind") or "अज्ञातम्"
    primary = names[0] if names else ""
    pattern_lg = "|".join("".join("G" if c == "ग" else "L" for c in p.get("pattern", "")) for p in padas)
    out = {
        "chandas": primary, "chandas_normalized": normalise_name(primary), "chandas_alternatives": names[1:],
        "kind": kind,
        "vrutta_family": res.get("jaati") or "",
        "pada_count": len(padas),
        "syllables_per_pada": [p.get("aksharas") for p in padas],
        "syllable_count": sum(p.get("aksharas", 0) for p in padas),
        "matras_per_pada": [p.get("matras") for p in padas],
        "laghu_guru": pattern_lg,
        "gana": "|".join(p.get("ganas", "") for p in padas),
        "yati": m.get("yati") or [],
        "anushtubh_variant": (re.search(r"— (.+)$", primary).group(1) if primary.startswith("अनुष्टुप्") and "—" in primary else ""),
        "classification": {"छन्दः": "anushtubh_rule", "समवृत्तम्": "sama", "अर्धसमवृत्तम्": "ardhasama", "उपजातिः": "upajati", "विषमवृत्तम्": "vishama", "मात्रावृत्तम् (जातिः)": "matra_jati", "अज्ञातम्": "unknown"}.get(kind, "unknown"),
        "near_matches": m.get("near") or [],
        "partial": bool(m.get("partial")),
        "anushtubh_irregular": list(m.get("irregular") or []),
        "upajati_mix": m.get("mix") or "",
    }
    n = set(out["syllables_per_pada"])
    out["confidence"] = (1.0 if out["classification"] in ("anushtubh_rule", "sama", "ardhasama", "upajati", "vishama") and not out["partial"]
                         else 0.8 if out["classification"] == "matra_jati" else 0.6 if out["partial"] else (0.3 if out["near_matches"] else 0.0))
    if out["anushtubh_irregular"]:
        out["confidence"] = 0.5      # 4×8 but breaks a pāda rule even allowing the four vipulās — text needs a look
    elif out["upajati_mix"]:
        out["confidence"] = 0.9      # generic indra/upendra-family mix, not one of the 42 named rows
    out["equal_padas"] = len(n) == 1 and out["pada_count"] >= 2
    refine(out)
    return out


INDRA, UPENDRA = "GGLGGLLGLGG", "LGLGGLLGLGG"


def _pada_ok(p, t):
    return len(p) == len(t) and all(a == b or (i == len(t) - 1) for i, (a, b) in enumerate(zip(p, t)))


def refine(out):
    """Kamadhenu-side reasons when the DGE engine returns अज्ञातम् (or a doubtful anuṣṭubh). The engine's verdict is
    kept untouched in `chandas`; `chandas_inferred` carries a lower-confidence fallback label and `inferred_reason`
    says why, so the review queue can be sorted. Since Sep 2026 the engine itself names the four anuṣṭubh vipulās,
    every indra/upendra upajāti mix, ardhasama verses given as one or two lines, and Kannada/Telugu/Malayalam
    input, so the reasons left here are text-side: unequal pādas, defective syllable counts, prose."""
    out["chandas_inferred"] = out["chandas_normalized"]
    out["inferred_reason"] = ""
    if out["anushtubh_irregular"]:
        out["inferred_reason"] = "4×8 syllables, but a pāda breaks the anuṣṭubh rules even allowing na/bha/ma/ra-vipulā: " + "; ".join(out["anushtubh_irregular"])
        return
    if out["classification"] != "unknown":
        return
    padas = out["laghu_guru"].split("|") if out["laghu_guru"] else []
    if out["equal_padas"] and out["near_matches"]:
        out["inferred_reason"] = "equal pādas, no exact vṛtta; nearest DGE candidates listed in near_matches"
    elif out["equal_padas"]:
        out["inferred_reason"] = f"equal pādas of {len(padas[0]) if padas else 0} akṣaras, no vṛtta of that length matches — metre missing from the DB or text defect"
    elif not out["equal_padas"] and out["pada_count"] >= 2:
        out["inferred_reason"] = "unequal pāda syllable counts — suspected text defect (typo, missing/extra akṣara, wrong line split) or prose"
    elif out["pada_count"] < 2:
        out["inferred_reason"] = "fewer than two pādas — prose, colophon, fragment, or a single line the splitter could not divide"


def analyse_texts(texts, batch=400):
    cache_p = PROCESSED / "chandas_cache_v5.json"
    cache = read_json(cache_p, {}) or {}
    todo = [t for t in dict.fromkeys(texts) if t and _hash(t) not in cache]
    for i in range(0, len(todo), batch):
        chunk = todo[i:i + batch]
        for t, r in zip(chunk, _run_node(chunk)):
            cache[_hash(t)] = summarise(r) if "error" not in r else {"chandas": "", "classification": "error", "error": r["error"], "confidence": 0.0}
        write_json(cache_p, cache)
    return [cache.get(_hash(t)) if t else None for t in texts]


def run():
    ti = read_json(DS / "text_index.json")
    units = ti["units"]
    log(f"chandas: analysing {len(units)} text units with js/chandas.js (node)")
    res = analyse_texts([u.get("metrical_text") or u.get("text") for u in units])
    for u, r in zip(units, res):
        u["chandas_analysis"] = r
    from collections import Counter
    c = Counter((r or {}).get("chandas_normalized") or "अज्ञातम्" for r in res)
    k = Counter((r or {}).get("classification") for r in res)
    ti["chandas_summary"] = {"generated_at": now_ist(), "by_classification": dict(k), "top_chandas": c.most_common(40)}
    write_json(DS / "text_index.json", ti)
    log(f"chandas: classification {dict(k)}; top {c.most_common(8)}")
    return ti


if __name__ == "__main__":
    run()
