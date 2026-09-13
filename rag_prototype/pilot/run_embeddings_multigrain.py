"""
Embed only the NEW multi-granularity rows (passage groups + commentary
blocks) with BGE-M3, then concatenate with the already-computed base
423-chunk embedding matrix (reused, not recomputed) to score the combined
499-chunk multi-granularity corpus against queries_large.json.
"""
import json, time
from pathlib import Path
import numpy as np
from sentence_transformers import SentenceTransformer

HERE = Path(__file__).parent
all_rows = json.loads((HERE / "representations_multigrain.json").read_text())
new_rows = json.loads((HERE / "new_multigrain_rows_only.json").read_text())
queries = json.loads((HERE / "queries_large.json").read_text())

base_emb = np.load(HERE / "corpus_emb.npy")  # matches the first 423 rows of all_rows, by construction
assert base_emb.shape[0] == len(all_rows) - len(new_rows), "base embedding count mismatch"

print(f"Loading BAAI/bge-m3 for {len(new_rows)} new rows ...", flush=True)
t0 = time.time()
model = SentenceTransformer("BAAI/bge-m3")
print(f"Loaded in {time.time()-t0:.1f}s", flush=True)

texts = [r["text"] for r in new_rows]
t0 = time.time()
new_emb = model.encode(texts, normalize_embeddings=True, show_progress_bar=True, batch_size=16)
embed_s = time.time() - t0
print(f"Embedded {len(texts)} new chunks in {embed_s:.1f}s ({embed_s/len(texts)*1000:.1f} ms/chunk)")

combined_emb = np.vstack([base_emb, new_emb])
np.save(HERE / "corpus_emb_multigrain.npy", combined_emb)

query_emb = np.load(HERE / "query_emb.npy")
sims = query_emb @ combined_emb.T

results = []
for qi, q in enumerate(queries):
    order = np.argsort(-sims[qi])
    ranked_chunks = [
        {"chunk_id": all_rows[j]["chunk_id"], "parent_unit_id": all_rows[j]["parent_unit_id"],
         "covers": all_rows[j]["covers"], "rep_type": all_rows[j]["rep_type"],
         "granularity": all_rows[j]["granularity"], "score": float(sims[qi][j])}
        for j in order[:40]
    ]
    results.append({"id": q["id"], "category": q["category"], "query": q["query"],
                     "target_parent": q["target_parent"], "ranked_chunks": ranked_chunks})

(HERE / "embedding_results_multigrain.json").write_text(json.dumps(results, ensure_ascii=False, indent=1))

meta = {
    "model": "BAAI/bge-m3",
    "n_new_chunks": len(new_rows),
    "n_total_chunks": len(all_rows),
    "embed_new_s": round(embed_s, 2),
    "ms_per_new_chunk": round(embed_s / len(texts) * 1000, 2),
}
(HERE / "embedding_multigrain_meta.json").write_text(json.dumps(meta, indent=2))
print(json.dumps(meta, indent=2))
