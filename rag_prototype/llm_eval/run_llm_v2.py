"""
v2: tuned prompt. Same retrieval_context.json, same models, same
temperature/max_tokens/n_ctx as v1 -- the ONLY variable changed is the
system prompt, to isolate its effect for a clean before/after comparison.

Diagnosis that motivated this version (see conversation): v1's Gemma (and
likely others) falsely refused q4 even though the correct source
(Prahlada::3) was retrieved -- because that unit's ONLY representations
are Sanskrit (mula + Sanskrit commentary), unlike every other retrieved
unit in that question's context, which had an English gloss sitting next
to it. The model appears to have treated "no English translation
supplied" as "insufficient evidence", rather than translating the
Sanskrit itself, even though v1's prompt never actually forbade that.

v2 explicitly: (a) states that translating/interpreting supplied
Sanskrit/Kannada text is REQUIRED, not "outside knowledge"; (b) narrows
the refusal condition to "the passages don't address the topic at all",
not "no passage states it in the question's own wording"; (c) forbids
volunteering any extra unrequested/unsourced fact when refusing (targets
Mistral's v1 pattern of correct refusals immediately followed by a
fabricated 'bonus' claim).
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
    "1. Base your answer ONLY on facts, statements, and meaning actually present in the supplied "
    "SOURCE passages. Do not add any fact, date, name, attribution, or identification that is not "
    "derivable from the text shown to you, even if you recognize the material from elsewhere.\n"
    "2. The supplied passages may be in Sanskrit, Kannada, or English, and may be in a different "
    "language than the QUESTION. You MUST read, translate, and interpret the supplied text "
    "yourself to produce your answer -- translating or paraphrasing what is actually written in a "
    "supplied passage is REQUIRED and is NOT 'outside knowledge'. Outside knowledge means only "
    "information that is NOT present in the supplied passages, even if expressed in a different "
    "language than your answer.\n"
    "3. Refuse -- say exactly 'This is not established by the supplied sources.' -- ONLY when none "
    "of the supplied passages actually address the question's topic. Do NOT refuse merely because "
    "answering requires you to translate or synthesize Sanskrit/Kannada text, or because no "
    "passage states the answer in exactly the question's own wording.\n"
    "4. Every claim in your answer must cite the source unit id(s) it came from, in the form "
    "[source: <unit_id>].\n"
    "5. If you refuse, refuse and stop -- do not add any other claim, guess, or 'for context' fact "
    "alongside the refusal.\n"
    "6. If multiple sources are needed to answer fully, use and cite all of them.\n"
    "7. Be concise and direct."
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
    model_path = HERE / "models" / cfg["file"]

    contexts = json.loads((HERE / "retrieval_context.json").read_text())

    print(f"[v2] Loading {cfg['family']} from {model_path} ...", flush=True)
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
            if "System role not supported" not in str(e):
                raise
            out = llm.create_chat_completion(
                messages=[{"role": "user", "content": f"{SYSTEM_PROMPT}\n\n{user_msg}"}],
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
    out_path = HERE / f"llm_answers_v2_{model_key}.json"
    out_path.write_text(json.dumps({"meta": meta, "results": results}, ensure_ascii=False, indent=1))
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
