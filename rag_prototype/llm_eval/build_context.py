"""
Retrieval context builder for the LLM benchmark, using the ADOPTED
architecture only: BGE-M3 (base 423-chunk, verse-level representation
corpus -- multi-granularity was NOT adopted) as primary ranking, with the
confidence-aware lexical exact-match override (>=0.9, i.e. dge-search.js's
own 'word-index-exact' band) -- never blind RRF.

For each question, the top-K distinct parent units (by this fused score)
each contribute ALL of their own real representations (mula + any
commentary/translation/Kannada-meaning chunks already in
representations.json) as separate labeled source blocks, so the LLM sees
genuine source material, not a single flattened blob.
"""
import json
from pathlib import Path
import numpy as np
from sentence_transformers import SentenceTransformer

HERE = Path(__file__).parent
PILOT = HERE.parent / "pilot"

questions = json.loads((HERE / "questions.json").read_text())
lex_for_q = {r["id"]: r for r in json.loads((HERE / "lexical_for_questions.json").read_text())}
reps = json.loads((PILOT / "representations.json").read_text())
corpus_emb = np.load(PILOT / "corpus_emb.npy")
assert corpus_emb.shape[0] == len(reps)

CONFIDENCE_THRESHOLD = 0.9
OVERRIDE_BOOST = 100.0
TOP_K_PARENTS = 5

print("Loading BAAI/bge-m3 ...", flush=True)
model = SentenceTransformer("BAAI/bge-m3")

q_texts = [q["question"] for q in questions]
q_emb = model.encode(q_texts, normalize_embeddings=True, show_progress_bar=False)
sims = q_emb @ corpus_emb.T  # [n_questions, n_chunks]

reps_by_parent = {}
for r in reps:
    reps_by_parent.setdefault(r["parent_unit_id"], []).append(r)

output = []
for qi, q in enumerate(questions):
    # dedupe to parent-level scores (verse-level corpus: covers = self)
    best = {}
    for ci, r in enumerate(reps):
        s = float(sims[qi][ci])
        pid = r["parent_unit_id"]
        if pid not in best or s > best[pid]:
            best[pid] = s

    lr = lex_for_q[q["id"]]
    for h in lr["exact"]:
        if h["score"] >= CONFIDENCE_THRESHOLD:
            pid = f"{h['grantha']}::{h['unit']}"
            best[pid] = best.get(pid, 0.0) + OVERRIDE_BOOST

    ranked = sorted(best.items(), key=lambda kv: -kv[1])[:TOP_K_PARENTS]

    retrieved = []
    for rank, (pid, score) in enumerate(ranked, start=1):
        parent_reps = reps_by_parent.get(pid, [])
        passages = [
            {"rep_type": pr["rep_type"], "lang": pr["lang"], "script": pr["script"],
             "ai_generated": pr["ai_generated"], "text": pr["text"]}
            for pr in parent_reps
        ]
        retrieved.append({
            "rank": rank, "parent_unit_id": pid, "score": round(score, 4),
            "lexical_override": score >= OVERRIDE_BOOST,
            "passages": passages,
        })

    output.append({
        "id": q["id"], "category": q["category"], "question": q["question"],
        "answerable": q["answerable"], "gold_targets": q["gold_targets"],
        "retrieved": retrieved,
    })

(HERE / "retrieval_context.json").write_text(json.dumps(output, ensure_ascii=False, indent=1))

# quick sanity print: did retrieval actually surface the gold target(s)?
for r in output:
    ids_retrieved = {x["parent_unit_id"] for x in r["retrieved"]}
    hits = [g for g in r["gold_targets"] if g in ids_retrieved]
    print(f"{r['id']:5} {r['category']:24} gold_in_topK={len(hits)}/{len(r['gold_targets'])}"
          f"  override_used={any(x['lexical_override'] for x in r['retrieved'])}")
