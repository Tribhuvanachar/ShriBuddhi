# RAG prototype — session handoff

Everything here is prototype/experiment code and results from a multi-day RAG
architecture investigation (retrieval model selection, hybrid search tuning,
local LLM benchmark, full-corpus embedding pipeline). Nothing here has been
wired into the production DGE app or committed to `dge/`. Saved here as a
safety net before this session (`RAG search for LLM assessment`,
`session_01BummwZqg6zXowioMEfDdq2`) is archived/handed off.

## What's included (small: code + results, ~1.2 MB)

- `pilot/` — the first retrieval experiments: BGE-M3 vs. lexical vs. hybrid,
  confidence-aware fusion, multi-granularity chunking test. `fusion_report.json`
  and `v2_report.json` have the full per-query results.
- `llm_eval/` — the local LLM benchmark (Mistral / Qwen / gemma-2-9b-it, all
  Q4_K_M via llama.cpp): prompts, retrieval context, all answers, and my
  grading of each (`grading_*.json`). **Conclusion: gemma-2-9b-it is the
  provisional production candidate** — zero hallucinations, best citation
  discipline, best Kannada handling; Mistral was rejected (39% hallucination
  rate); Qwen over-refuses even with good evidence present.
- `full_corpus/` — the scripts that built the real, full-corpus RAG index:
  `extract_full_corpus.py` (943,051 chunks from the whole `dge/data` tree,
  multi-representation: mula + commentary + translation + Kannada meaning,
  with a 2,000-char split fix for a real bug found mid-run — see the script's
  own docstring), `embed_full_corpus.py` (checkpointed/resumable BGE-M3
  embedding — survived 3 container restarts with zero data loss),
  `consolidate.py`, `validate_full_index.py`.

## What's NOT included here — still only in this session's ephemeral scratchpad

These are too large for a normal git commit and need a deliberate decision
(dataset repo? CDN branch, matching the existing `search-dist`/`kavya-dist`
pattern? git-lfs?) before they go anywhere permanent:

- `corpus_emb_full.npy` — 1.93 GB, the actual embedding matrix for all
  943,051 chunks (fp16, 1024-dim, BGE-M3).
- `representations_full.jsonl` — 1.0 GB, the source text for every chunk.
- `chunk_meta_full.json` — 288 MB, chunk_id → {parent_unit_id, rep_type,
  lang, source, ai_generated}.
- `chunk_ids_full.json` — 79 MB, the ordered chunk_id list matching the
  embedding matrix's row order.
- `models/gemma-2-9b-it-Q4_K_M.gguf` — 5.76 GB, downloaded from
  `bartowski/gemma-2-9b-it-GGUF`, trivially re-downloadable if lost.

**If the container holding this session is reclaimed before those are moved
somewhere durable, they need to be rebuilt from scratch** — `extract_full_corpus.py`
+ `embed_full_corpus.py` regenerate them deterministically (the embedding
pass took ~41 hours of actual compute on a 4-core CPU last time, checkpointed
so it survives interruption).

## Known open items

- Retrieval at full-corpus scale still misses the same class of broad
  conceptual/cosmogonic questions identified in the small pilot (e.g. "what
  existed before creation") — confirmed, not a new problem.
- The full-corpus *lexical* exact-match index (the other half of the
  confidence-aware hybrid architecture) has not been built yet — only the
  embedding half exists at full scale so far.
- gemma-2-9b-it's one known false-refusal case (refuses when the only
  evidence for a question is untranslated Sanskrit, no English gloss) was
  investigated and NOT fixed by prompt tuning — see `llm_eval/run_llm_v2.py`'s
  docstring for what was tried.
