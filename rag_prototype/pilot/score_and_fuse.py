"""
Score BGE-M3 (chunk-level and parent-level), the real DGE lexical search
(exact / fuzzy / best-of-both), and a reciprocal-rank-fusion hybrid of
lexical-best + embedding-parent, against queries_large.json's known
targets. Writes a full report to fusion_report.json and prints a summary
table.
"""
import json
from pathlib import Path
from collections import OrderedDict

HERE = Path(__file__).parent
queries = json.loads((HERE / "queries_large.json").read_text())
emb_results = {r["id"]: r for r in json.loads((HERE / "embedding_results.json").read_text())}
lex_results = {r["id"]: r for r in json.loads((HERE / "lexical_results.json").read_text())}

RRF_K = 60


def dedupe_parent_ranking(ranked_chunks):
    """[{parent_unit_id, score}, ...] sorted desc by chunk score -> list of
    distinct parent_unit_ids in order of their best chunk's score."""
    best = OrderedDict()
    for c in ranked_chunks:
        pid = c["parent_unit_id"]
        if pid not in best or c["score"] > best[pid]:
            best[pid] = c["score"]
    return [pid for pid, _ in sorted(best.items(), key=lambda kv: -kv[1])]


def lex_hits_to_parent_ranking(hits):
    """dge-search.js hit objects {grantha, unit, score} -> ordered distinct
    parent_unit_id list (already rank-ordered by the search engine itself,
    so just dedupe preserving order and keep the best (first) score per
    parent)."""
    seen = OrderedDict()
    for h in hits:
        pid = f"{h['grantha']}::{h['unit']}"
        if pid not in seen:
            seen[pid] = True
    return list(seen.keys())


def rank_of(target, ranking):
    try:
        return ranking.index(target) + 1
    except ValueError:
        return None


def merge_lexical_best(exact_ranking, fuzzy_ranking):
    """Union, exact-mode results ranked first (matches the production
    default of 'Exact spelling only' ON), then fuzzy results not already
    present -- i.e. what a user gets by trying both toggle positions."""
    merged = list(exact_ranking)
    for pid in fuzzy_ranking:
        if pid not in merged:
            merged.append(pid)
    return merged


def rrf_fuse(rankings, k=RRF_K):
    """rankings: list of ordered-list-of-parent-ids (best first). Returns
    a single fused ranking by reciprocal rank fusion."""
    scores = {}
    for ranking in rankings:
        for i, pid in enumerate(ranking):
            scores[pid] = scores.get(pid, 0.0) + 1.0 / (k + i + 1)
    return [pid for pid, _ in sorted(scores.items(), key=lambda kv: -kv[1])]


def metrics(ranks, n):
    hit1 = sum(1 for r in ranks if r == 1)
    hit3 = sum(1 for r in ranks if r and r <= 3)
    hit5 = sum(1 for r in ranks if r and r <= 5)
    mrr = sum((1.0 / r) if r else 0.0 for r in ranks)
    return {
        "n": n,
        "hit@1": round(hit1 / n, 3), "hit@3": round(hit3 / n, 3),
        "hit@5": round(hit5 / n, 3), "mrr": round(mrr / n, 3),
    }


rows = []
systems = ["emb_chunk", "emb_parent", "lex_exact", "lex_fuzzy", "lex_best", "hybrid_rrf"]
ranks_by_system = {s: [] for s in systems}
ranks_by_system_and_cat = {}

for q in queries:
    target = q["target_parent"]
    er = emb_results[q["id"]]
    lr = lex_results[q["id"]]

    chunk_ranking_raw = [c["parent_unit_id"] for c in er["ranked_chunks"]]  # chunk-level, not deduped
    parent_ranking = dedupe_parent_ranking(er["ranked_chunks"])
    exact_ranking = lex_hits_to_parent_ranking(lr["exact"])
    fuzzy_ranking = lex_hits_to_parent_ranking(lr["fuzzy"])
    lex_best_ranking = merge_lexical_best(exact_ranking, fuzzy_ranking)
    hybrid_ranking = rrf_fuse([lex_best_ranking, parent_ranking])

    row = {
        "id": q["id"], "category": q["category"], "query": q["query"], "target": target,
        "rank_emb_chunk": rank_of(target, chunk_ranking_raw),
        "rank_emb_parent": rank_of(target, parent_ranking),
        "rank_lex_exact": rank_of(target, exact_ranking),
        "rank_lex_fuzzy": rank_of(target, fuzzy_ranking),
        "rank_lex_best": rank_of(target, lex_best_ranking),
        "rank_hybrid_rrf": rank_of(target, hybrid_ranking),
        "top3_emb_parent": parent_ranking[:3],
        "top3_lex_best": lex_best_ranking[:3],
        "top3_hybrid": hybrid_ranking[:3],
    }
    rows.append(row)

    ranks_by_system["emb_chunk"].append(row["rank_emb_chunk"])
    ranks_by_system["emb_parent"].append(row["rank_emb_parent"])
    ranks_by_system["lex_exact"].append(row["rank_lex_exact"])
    ranks_by_system["lex_fuzzy"].append(row["rank_lex_fuzzy"])
    ranks_by_system["lex_best"].append(row["rank_lex_best"])
    ranks_by_system["hybrid_rrf"].append(row["rank_hybrid_rrf"])

    cat = q["category"]
    ranks_by_system_and_cat.setdefault(cat, {s: [] for s in systems})
    for s in systems:
        ranks_by_system_and_cat[cat][s].append(row[f"rank_{s}"])

overall = {s: metrics(ranks_by_system[s], len(queries)) for s in systems}
by_category = {
    cat: {s: metrics(ranks, len(ranks)) for s, ranks in sysranks.items()}
    for cat, sysranks in ranks_by_system_and_cat.items()
}

report = {"overall": overall, "by_category": by_category, "rows": rows}
(HERE / "fusion_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))

print("=== OVERALL (n=%d queries) ===" % len(queries))
print(f"{'system':<14}{'hit@1':>8}{'hit@3':>8}{'hit@5':>8}{'mrr':>8}")
for s in systems:
    m = overall[s]
    print(f"{s:<14}{m['hit@1']:>8}{m['hit@3']:>8}{m['hit@5']:>8}{m['mrr']:>8}")

print("\n=== BY CATEGORY (hit@1 / hit@3 / mrr) ===")
for cat, sysranks in by_category.items():
    print(f"\n{cat} (n={sysranks['emb_parent']['n']}):")
    for s in systems:
        m = sysranks[s]
        print(f"  {s:<14} hit@1={m['hit@1']:<6} hit@3={m['hit@3']:<6} mrr={m['mrr']}")
