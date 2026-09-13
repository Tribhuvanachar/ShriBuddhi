"""
Post-process retrieval_context.json: cap each individual passage's length
and the total context budget per question, so every prompt fits inside the
8192-token context window shared by all three candidate models (Gemma-2's
native limit is the binding one). This is a chunking/budget policy any
production RAG system needs anyway -- not a change to retrieval ranking,
which is untouched; only how much of the top-ranked material is shown to
the LLM.
"""
import json
from pathlib import Path

HERE = Path(__file__).parent
MAX_CHARS_PER_PASSAGE = 700
MAX_TOTAL_CHARS = 6000

contexts = json.loads((HERE / "retrieval_context.json").read_text())

for c in contexts:
    total = 0
    new_retrieved = []
    for r in c["retrieved"]:
        new_passages = []
        for p in r["passages"]:
            text = p["text"]
            if len(text) > MAX_CHARS_PER_PASSAGE:
                text = text[:MAX_CHARS_PER_PASSAGE] + " ...[truncated]"
            if total + len(text) > MAX_TOTAL_CHARS:
                continue
            total += len(text)
            new_passages.append({**p, "text": text})
        if new_passages:
            new_retrieved.append({**r, "passages": new_passages})
    c["retrieved"] = new_retrieved

(HERE / "retrieval_context.json").write_text(json.dumps(contexts, ensure_ascii=False, indent=1))

for c in contexts:
    total_chars = sum(len(p["text"]) for r in c["retrieved"] for p in r["passages"])
    n_passages = sum(len(r["passages"]) for r in c["retrieved"])
    print(f"{c['id']:5} total_chars={total_chars:5} n_passages={n_passages} n_parents={len(c['retrieved'])}")
