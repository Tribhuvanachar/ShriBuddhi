"""
Consolidate the 472 per-shard embedding files (in chunk-index order, per
the checkpointed embed_full_corpus.py's own shard numbering) into one
matrix + one ordered chunk_id list, and build a lightweight metadata
index (chunk_id -> parent_unit_id/rep_type/lang/source/ai_generated,
WITHOUT the full text, which stays in representations_full.jsonl) for
fast lookup at query time.
"""
import json, glob
from pathlib import Path
import numpy as np

HERE = Path(__file__).parent
EMB_DIR = HERE / "embeddings"

shard_files = sorted(glob.glob(str(EMB_DIR / "shard_*.npy")))
print(f"{len(shard_files)} shard files found")

all_ids = []
mats = []
for shard_path in shard_files:
    shard_num = Path(shard_path).stem.replace("shard_", "")
    ids_path = EMB_DIR / f"shard_{shard_num}_ids.json"
    ids = json.loads(ids_path.read_text())
    mat = np.load(shard_path)
    assert mat.shape[0] == len(ids), f"{shard_path}: {mat.shape[0]} vectors vs {len(ids)} ids"
    all_ids.extend(ids)
    mats.append(mat)

full_matrix = np.vstack(mats)
print(f"Consolidated matrix: {full_matrix.shape}, dtype={full_matrix.dtype}")
assert len(all_ids) == full_matrix.shape[0]

np.save(HERE / "corpus_emb_full.npy", full_matrix)
(HERE / "chunk_ids_full.json").write_text(json.dumps(all_ids))

# metadata index: chunk_id -> {parent_unit_id, rep_type, lang, source, ai_generated}
print("Building metadata index from representations_full.jsonl ...")
meta = {}
with open(HERE / "representations_full.jsonl", encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        meta[r["chunk_id"]] = {
            "parent_unit_id": r["parent_unit_id"], "rep_type": r["rep_type"],
            "lang": r["lang"], "source": r["source"], "ai_generated": r["ai_generated"],
        }

missing = [cid for cid in all_ids if cid not in meta]
print(f"chunk_ids missing metadata: {len(missing)}")

(HERE / "chunk_meta_full.json").write_text(json.dumps(meta, ensure_ascii=False))

print(json.dumps({
    "total_chunks": len(all_ids),
    "matrix_shape": list(full_matrix.shape),
    "matrix_dtype": str(full_matrix.dtype),
    "matrix_size_mb": round(full_matrix.nbytes / 1e6, 1),
    "distinct_parent_units": len(set(m["parent_unit_id"] for m in meta.values())),
}, indent=2))
