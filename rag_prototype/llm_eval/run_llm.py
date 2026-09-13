"""
Run one local GGUF model (llama-cpp-python, CPU) over retrieval_context.json.
Usage: python3 run_llm.py <model_key>
  model_key in {mistral, qwen, gemma}

Strict "answer only from supplied sources, cite unit ids, refuse if
insufficient" system prompt. Records wall-clock latency, tokens/sec, and
peak RSS memory (via resource.getrusage) for the hardware section of the
report. No fine-tuning, no new corpus content generated here -- pure
inference over already-retrieved real DGE passages.
"""
import json, sys, time, resource
from pathlib import Path
from llama_cpp import Llama

HERE = Path(__file__).parent
MODELS = {
    "mistral": {"file": "Mistral-7B-Instruct-v0.3-Q4_K_M.gguf", "family": "Mistral-7B-Instruct-v0.3", "size_gb": 4.37},
    "qwen": {"file": "Qwen2.5-7B-Instruct-Q4_K_M.gguf", "family": "Qwen2.5-7B-Instruct", "size_gb": 4.68},
    "gemma": {"file": "gemma-2-9b-it-Q4_K_M.gguf", "family": "gemma-2-9b-it", "size_gb": 5.76},
}

SYSTEM_PROMPT = (
    "You are a scholarly assistant for the Sarvamula Digital Library (DGE), a Sanskrit/Kannada "
    "textual corpus. You will be given a QUESTION and a numbered list of SOURCE passages "
    "retrieved from the DGE corpus, each labeled with its source unit id, language, and whether "
    "it is AI-generated.\n\n"
    "Rules, follow exactly:\n"
    "1. Answer using ONLY information contained in the supplied SOURCE passages. Do not use "
    "outside knowledge of Sanskrit texts, even if you recognize the material.\n"
    "2. Every claim in your answer must cite the source unit id(s) it came from, in the form "
    "[source: <unit_id>].\n"
    "3. If the supplied sources do not contain enough information to answer the question, you "
    "MUST say so explicitly: 'This is not established by the supplied sources.' Do not guess or "
    "fill gaps with outside knowledge.\n"
    "4. If multiple sources are needed to answer fully, use and cite all of them.\n"
    "5. Be concise and direct."
)


def build_context_block(retrieved):
    blocks = []
    for r in retrieved:
        for p in r["passages"]:
            tag = f"[{r['parent_unit_id']} | {p['rep_type']} | lang={p['lang']}" + \
                  (" | AI-GENERATED" if p["ai_generated"] else "") + "]"
            blocks.append(f"{tag}\n{p['text']}")
    return "\n\n".join(blocks)


def main():
    model_key = sys.argv[1]
    cfg = MODELS[model_key]
    model_path = HERE.parent / "llm_eval" / "models" / cfg["file"]

    contexts = json.loads((HERE / "retrieval_context.json").read_text())

    print(f"Loading {cfg['family']} from {model_path} ...", flush=True)
    t0 = time.time()
    llm = Llama(model_path=str(model_path), n_ctx=8192, n_threads=4, verbose=False)
    load_s = time.time() - t0
    print(f"Loaded in {load_s:.1f}s", flush=True)

    results = []
    for c in contexts:
        context_block = build_context_block(c["retrieved"])
        user_msg = f"SOURCE PASSAGES:\n\n{context_block}\n\nQUESTION: {c['question']}"

        t0 = time.time()
        try:
            out = llm.create_chat_completion(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                max_tokens=400,
                temperature=0.2,
            )
        except ValueError as e:
            # gemma-2's chat template rejects a separate system role; fold
            # the same instructions into one user turn instead (content
            # unchanged, only the role structure differs -- noted in the
            # report as a methodology footnote).
            if "System role not supported" not in str(e):
                raise
            out = llm.create_chat_completion(
                messages=[
                    {"role": "user", "content": f"{SYSTEM_PROMPT}\n\n{user_msg}"},
                ],
                max_tokens=400,
                temperature=0.2,
            )
        gen_s = time.time() - t0
        answer = out["choices"][0]["message"]["content"]
        usage = out.get("usage", {})
        completion_tokens = usage.get("completion_tokens", 0)
        tok_per_s = completion_tokens / gen_s if gen_s > 0 else 0.0

        print(f"[{c['id']}] {gen_s:.1f}s, {completion_tokens} tok, {tok_per_s:.1f} tok/s", flush=True)

        results.append({
            "id": c["id"], "category": c["category"], "question": c["question"],
            "answerable": c["answerable"], "gold_targets": c["gold_targets"],
            "retrieved_parent_ids": [r["parent_unit_id"] for r in c["retrieved"]],
            "answer": answer,
            "gen_seconds": round(gen_s, 2),
            "completion_tokens": completion_tokens,
            "tokens_per_sec": round(tok_per_s, 2),
        })

    peak_rss_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    meta = {
        "model_key": model_key, "family": cfg["family"], "gguf_size_gb": cfg["size_gb"],
        "load_seconds": round(load_s, 1), "peak_rss_mb": round(peak_rss_mb, 1),
        "n_questions": len(results),
        "avg_gen_seconds": round(sum(r["gen_seconds"] for r in results) / len(results), 2),
        "avg_tokens_per_sec": round(sum(r["tokens_per_sec"] for r in results) / len(results), 2),
    }
    out_path = HERE / f"llm_answers_{model_key}.json"
    out_path.write_text(json.dumps({"meta": meta, "results": results}, ensure_ascii=False, indent=1))
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
