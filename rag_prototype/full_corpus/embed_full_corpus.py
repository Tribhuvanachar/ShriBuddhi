"""
Checkpointed, resumable BGE-M3 embedding of representations_full.jsonl.

Design: local CPU, no paid compute, per explicit instruction (10 Sep 2026).
At this sandbox's measured throughput (~464 chars/sec, from the earlier
423-chunk pilot), the full ~883K-chunk / 258.5M-char corpus is roughly a
150+ hour job -- far longer than any single run of this script. So:

  - Chunks are processed in fixed-size SHARDS (2,000 chunks each).
  - Each finished shard is written immediately (embeddings as float16 to
    halve disk, plus the chunk_ids it covers) -- never held in memory
    across shards.
  - embed_checkpoint.json records the next unprocessed index after every
    shard, so re-running this script (same session, a later session, or
    on different hardware entirely) resumes exactly where it left off
    instead of restarting or double-embedding.
  - Progress (chunks done, elapsed, measured rate, ETA at that rate) is
    printed after every shard so real progress is always visible, not
    just at the end.

Usage: python3 embed_full_corpus.py [max_seconds]
  max_seconds: optional wall-clock budget for this invocation (e.g. run
  for at most 3600s then stop cleanly at the next shard boundary and
  exit 0 -- safe to just re-run the same command to continue).
"""
import json, sys, time
from pathlib import Path
import numpy as np
from sentence_transformers import SentenceTransformer

HERE = Path(__file__).parent
REPS_PATH = HERE / "representations_full.jsonl"
EMB_DIR = HERE / "embeddings"
EMB_DIR.mkdir(exist_ok=True)
CHECKPOINT_PATH = HERE / "embed_checkpoint.json"
SHARD_SIZE = 2000

max_seconds = float(sys.argv[1]) if len(sys.argv) > 1 else None

print("Loading representations_full.jsonl (chunk_id + text only) ...", flush=True)
t0 = time.time()
chunk_ids, texts = [], []
with open(REPS_PATH, encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        chunk_ids.append(r["chunk_id"])
        texts.append(r["text"])
total = len(texts)
print(f"Loaded {total} chunks in {time.time()-t0:.1f}s", flush=True)

if CHECKPOINT_PATH.exists():
    ckpt = json.loads(CHECKPOINT_PATH.read_text())
    start_idx = ckpt["next_index"]
    cum_chunks_done = ckpt.get("cumulative_chunks_embedded", start_idx)
    cum_seconds = ckpt.get("cumulative_embed_seconds", 0.0)
    print(f"Resuming from checkpoint: {start_idx}/{total} already done "
          f"({cum_seconds/3600:.1f}h of embedding time so far)", flush=True)
else:
    start_idx = 0
    cum_chunks_done = 0
    cum_seconds = 0.0

if start_idx >= total:
    print("Already complete. Nothing to do.")
    sys.exit(0)

print("Loading BAAI/bge-m3 ...", flush=True)
t0 = time.time()
model = SentenceTransformer("BAAI/bge-m3")
print(f"Model loaded in {time.time()-t0:.1f}s", flush=True)

run_start = time.time()
idx = start_idx
while idx < total:
    if max_seconds is not None and (time.time() - run_start) > max_seconds:
        print(f"Wall-clock budget ({max_seconds}s) reached; stopping cleanly at shard boundary. "
              f"Re-run this script to continue from index {idx}.", flush=True)
        break

    batch_ids = chunk_ids[idx: idx + SHARD_SIZE]
    batch_texts = texts[idx: idx + SHARD_SIZE]
    shard_num = idx // SHARD_SIZE

    t_shard = time.time()
    emb = model.encode(batch_texts, normalize_embeddings=True, show_progress_bar=False, batch_size=16)
    shard_seconds = time.time() - t_shard

    np.save(EMB_DIR / f"shard_{shard_num:05d}.npy", emb.astype(np.float16))
    (EMB_DIR / f"shard_{shard_num:05d}_ids.json").write_text(json.dumps(batch_ids))

    idx += len(batch_ids)
    cum_chunks_done += len(batch_ids)
    cum_seconds += shard_seconds

    rate = cum_chunks_done / cum_seconds if cum_seconds > 0 else 0
    remaining = total - idx
    eta_hours = (remaining / rate / 3600) if rate > 0 else float("inf")

    CHECKPOINT_PATH.write_text(json.dumps({
        "next_index": idx, "total": total,
        "cumulative_chunks_embedded": cum_chunks_done,
        "cumulative_embed_seconds": round(cum_seconds, 1),
        "measured_chunks_per_sec": round(rate, 3),
        "eta_hours_remaining_at_current_rate": round(eta_hours, 2),
        "last_updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }, indent=2))

    print(f"[shard {shard_num}] {idx}/{total} ({100*idx/total:.1f}%) done, "
          f"{shard_seconds:.1f}s this shard, {rate:.2f} chunks/s overall, "
          f"ETA {eta_hours:.1f}h remaining", flush=True)

if idx >= total:
    print(f"COMPLETE: all {total} chunks embedded.", flush=True)
