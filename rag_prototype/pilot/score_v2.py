"""
Experiment 2 report (this session): confidence-aware lexical override vs.
blind RRF, and multi-granularity retrieval vs. verse-only -- all against
the same 48-query gold set, all four combinations (base/multigrain x
plain-embedding/confidence-hybrid).

Confidence-aware override (NOT RRF): lexical search only ever influences
ranking when its OWN "exact" mode returns a hit at or above a confidence
threshold (dge-search.js's own scoring bands: 1.0 = exact pkey, 0.97 =
whole-word, 0.9 = word-start -- see dge-search.js _score()). When it does,
that parent is guaranteed the top rank (a large additive boost, not a
blended rank-fusion score) since a confirmed exact/near-exact textual
match should never be second-guessed by a fuzzy semantic score. Below the
threshold, lexical contributes nothing at all -- no dilution of a
confident embedding ranking by a weak or absent lexical signal, which is
exactly what sank blind RRF last time.
"""
import json
from pathlib import Path
from collections import OrderedDict

HERE = Path(__file__).parent
queries = json.loads((HERE / "queries_large.json").read_text())
lex_results = {r["id"]: r for r in json.loads((HERE / "lexical_results.json").read_text())}
emb_base = {r["id"]: r for r in json.loads((HERE / "embedding_results.json").read_text())}
emb_multi = {r["id"]: r for r in json.loads((HERE / "embedding_results_multigrain.json").read_text())}

CONFIDENCE_THRESHOLD = 0.9   # dge-search.js word-start band and above
OVERRIDE_BOOST = 100.0       # large enough to always outrank any cosine-sim score


def dedup_parent_scores(ranked_chunks):
    """Expand each chunk's `covers` list (verse-level chunks cover just
    themselves; passage-group/commentary-block chunks cover several real
    units) into per-parent scores, keeping the max chunk score seen for
    each covered parent. Returns {parent_unit_id: score}."""
    best = {}
    for c in ranked_chunks:
        covers = c.get("covers") or [c["parent_unit_id"]]
        for pid in covers:
            if pid not in best or c["score"] > best[pid]:
                best[pid] = c["score"]
    return best


def ranking_from_scores(score_map):
    return [pid for pid, _ in sorted(score_map.items(), key=lambda kv: -kv[1])]


def apply_confidence_override(score_map, lex_exact_hits, threshold=CONFIDENCE_THRESHOLD):
    out = dict(score_map)
    for h in lex_exact_hits:
        if h["score"] >= threshold:
            pid = f"{h['grantha']}::{h['unit']}"
            out[pid] = out.get(pid, 0.0) + OVERRIDE_BOOST
    return out


def rank_of(target, ranking):
    try:
        return ranking.index(target) + 1
    except ValueError:
        return None


def metrics(ranks, n):
    hit1 = sum(1 for r in ranks if r == 1)
    hit3 = sum(1 for r in ranks if r and r <= 3)
    hit5 = sum(1 for r in ranks if r and r <= 5)
    mrr = sum((1.0 / r) if r else 0.0 for r in ranks)
    return {"n": n, "hit@1": round(hit1 / n, 3), "hit@3": round(hit3 / n, 3),
            "hit@5": round(hit5 / n, 3), "mrr": round(mrr / n, 3)}


SYSTEMS = ["emb_base", "emb_multigrain", "conf_hybrid_base", "conf_hybrid_multigrain",
           "lex_exact_only"]
ranks_overall = {s: [] for s in SYSTEMS}
ranks_by_cat = {}
rows = []

for q in queries:
    target = q["target_parent"]
    lr = lex_results[q["id"]]

    base_scores = dedup_parent_scores(emb_base[q["id"]]["ranked_chunks"])
    multi_scores = dedup_parent_scores(emb_multi[q["id"]]["ranked_chunks"])

    conf_base_scores = apply_confidence_override(base_scores, lr["exact"])
    conf_multi_scores = apply_confidence_override(multi_scores, lr["exact"])

    lex_exact_ranking = []
    seen = OrderedDict()
    for h in lr["exact"]:
        pid = f"{h['grantha']}::{h['unit']}"
        seen.setdefault(pid, True)
    lex_exact_ranking = list(seen.keys())

    r_emb_base = rank_of(target, ranking_from_scores(base_scores))
    r_emb_multi = rank_of(target, ranking_from_scores(multi_scores))
    r_conf_base = rank_of(target, ranking_from_scores(conf_base_scores))
    r_conf_multi = rank_of(target, ranking_from_scores(conf_multi_scores))
    r_lex_exact = rank_of(target, lex_exact_ranking)

    row = {
        "id": q["id"], "category": q["category"], "query": q["query"], "target": target,
        "rank_emb_base": r_emb_base, "rank_emb_multigrain": r_emb_multi,
        "rank_conf_hybrid_base": r_conf_base, "rank_conf_hybrid_multigrain": r_conf_multi,
        "rank_lex_exact_only": r_lex_exact,
        "top3_emb_multigrain": ranking_from_scores(multi_scores)[:3],
        "top3_conf_hybrid_multigrain": ranking_from_scores(conf_multi_scores)[:3],
        "lex_override_fired": any(h["score"] >= CONFIDENCE_THRESHOLD for h in lr["exact"]),
    }
    rows.append(row)

    ranks_overall["emb_base"].append(r_emb_base)
    ranks_overall["emb_multigrain"].append(r_emb_multi)
    ranks_overall["conf_hybrid_base"].append(r_conf_base)
    ranks_overall["conf_hybrid_multigrain"].append(r_conf_multi)
    ranks_overall["lex_exact_only"].append(r_lex_exact)

    cat = q["category"]
    ranks_by_cat.setdefault(cat, {s: [] for s in SYSTEMS})
    for s in SYSTEMS:
        ranks_by_cat[cat][s].append(row[f"rank_{s}"])

overall = {s: metrics(ranks_overall[s], len(queries)) for s in SYSTEMS}
by_category = {cat: {s: metrics(r, len(r)) for s, r in sysranks.items()}
                for cat, sysranks in ranks_by_cat.items()}

report = {"overall": overall, "by_category": by_category, "rows": rows,
          "confidence_threshold": CONFIDENCE_THRESHOLD, "override_boost": OVERRIDE_BOOST}
(HERE / "v2_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))

print("=== OVERALL (n=%d) ===" % len(queries))
print(f"{'system':<24}{'hit@1':>8}{'hit@3':>8}{'hit@5':>8}{'mrr':>8}")
for s in SYSTEMS:
    m = overall[s]
    print(f"{s:<24}{m['hit@1']:>8}{m['hit@3']:>8}{m['hit@5']:>8}{m['mrr']:>8}")

print("\n=== BY CATEGORY ===")
for cat, sysranks in by_category.items():
    print(f"\n{cat} (n={sysranks['emb_base']['n']}):")
    for s in SYSTEMS:
        m = sysranks[s]
        print(f"  {s:<24} hit@1={m['hit@1']:<6} hit@3={m['hit@3']:<6} hit@5={m['hit@5']:<6} mrr={m['mrr']}")

n_override = sum(1 for r in rows if r["lex_override_fired"])
print(f"\nConfidence override fired on {n_override}/{len(rows)} queries (lexical exact score >= {CONFIDENCE_THRESHOLD})")
