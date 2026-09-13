"""
Embed every representation chunk with BAAI/bge-m3 (local, CPU, offline) and
score retrieval against queries_large.json -- both at chunk level (is the
literal representation-chunk retrieved) and at PARENT-UNIT level (is the
correct grantha+unit_id resolved, regardless of which representation of it
was matched).
"""
import json, time
from pathlib import Path
import numpy as np
from sentence_transformers import SentenceTransformer

HERE = Path(__file__).parent
reps = json.loads((HERE / "representations.json").read_text())
queries = json.loads((HERE / "queries_large.json").read_text())

print(f"Loading BAAI/bge-m3 ...", flush=True)
t0 = time.time()
model = SentenceTransformer("BAAI/bge-m3")
print(f"Loaded in {time.time()-t0:.1f}s", flush=True)

texts = [r["text"] for r in reps]
t0 = time.time()
corpus_emb = model.encode(texts, normalize_embeddings=True, show_progress_bar=True, batch_size=16)
embed_s = time.time() - t0
print(f"Embedded {len(texts)} chunks in {embed_s:.1f}s ({embed_s/len(texts)*1000:.1f} ms/chunk)")

q_texts = [q["query"] for q in queries]
t0 = time.time()
query_emb = model.encode(q_texts, normalize_embeddings=True, show_progress_bar=False)
query_s = time.time() - t0
print(f"Embedded {len(q_texts)} queries in {query_s:.2f}s ({query_s/len(q_texts)*1000:.1f} ms/query)")

np.save(HERE / "corpus_emb.npy", corpus_emb)
np.save(HERE / "query_emb.npy", query_emb)

sims = query_emb @ corpus_emb.T

results = []
for qi, q in enumerate(queries):
    order = np.argsort(-sims[qi])
    ranked_chunks = [
        {"chunk_id": reps[j]["chunk_id"], "parent_unit_id": reps[j]["parent_unit_id"],
         "rep_type": reps[j]["rep_type"], "score": float(sims[qi][j])}
        for j in order[:30]
    ]
    results.append({"id": q["id"], "category": q["category"], "query": q["query"],
                     "target_parent": q["target_parent"], "ranked_chunks": ranked_chunks})

(HERE / "embedding_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1))

meta = {
    "model": "BAAI/bge-m3",
    "n_chunks": len(reps),
    "n_parent_units": len(set(r["parent_unit_id"] for r in reps)),
    "n_queries": len(queries),
    "embed_corpus_s": round(embed_s, 2),
    "embed_query_s": round(query_s, 2),
    "ms_per_chunk": round(embed_s / len(texts) * 1000, 2),
}
(HERE / "embedding_meta.json").write_text(json.dumps(meta, indent=2))
print(json.dumps(meta, indent=2))
