"""
Sanity-check the consolidated full-corpus index (943,051 chunks) with a
handful of known queries reused from the earlier LLM-eval question set --
confirming real end-to-end retrieval (real extraction -> real embedding
-> real cosine-similarity search) works at actual production scale, not
just the 423-chunk pilot subset.
"""
import json, time
from pathlib import Path
import numpy as np
from sentence_transformers import SentenceTransformer

HERE = Path(__file__).parent
corpus_emb = np.load(HERE / "corpus_emb_full.npy").astype(np.float32)  # fp16 -> fp32 for the matmul
chunk_ids = json.loads((HERE / "chunk_ids_full.json").read_text())
chunk_meta = json.loads((HERE / "chunk_meta_full.json").read_text())
print(f"Loaded index: {corpus_emb.shape}, {len(chunk_ids)} chunk ids")

QUERIES = [
    ("What does Prahlada say about not fearing the Lord's terrifying Narasimha form?",
     "stotra/PrahladaKrutaNarasimha"),
    ("According to the Aitareya Upanishad, what existed in the very beginning before creation?",
     "aitareya_upanishad"),
    ("Whose exposition of the Brahma Sutras is praised in Raghavendra Vijaya verse 8?",
     "raghavendra_vijaya"),
    ("How did Yudhishthira prepare his army before the Kurukshetra war?",
     "mahabharata_kannada"),
    ("What is the definition of a pratyahara in Sanskrit grammar?",
     None),  # open-ended, no specific expected source substring
]

print("Loading BAAI/bge-m3 ...", flush=True)
model = SentenceTransformer("BAAI/bge-m3")

q_texts = [q for q, _ in QUERIES]
t0 = time.time()
q_emb = model.encode(q_texts, normalize_embeddings=True, show_progress_bar=False).astype(np.float32)
print(f"Embedded {len(q_texts)} queries in {time.time()-t0:.2f}s", flush=True)

t0 = time.time()
sims = q_emb @ corpus_emb.T
print(f"Similarity search over {corpus_emb.shape[0]} chunks took {time.time()-t0:.2f}s", flush=True)

for qi, (q, expect_substr) in enumerate(QUERIES):
    order = np.argsort(-sims[qi])[:5]
    print(f"\n=== Q: {q}")
    for rank, ci in enumerate(order, 1):
        cid = chunk_ids[ci]
        m = chunk_meta[cid]
        score = float(sims[qi][ci])
        flag = ""
        if expect_substr and expect_substr in m["source"]:
            flag = "  <-- matches expected source"
        print(f"  #{rank} score={score:.3f} parent={m['parent_unit_id']} rep={m['rep_type']}{flag}")
