#!/usr/bin/env python3
"""
gemini_bench.py — one-off benchmark harness for tools/gemini_summarize.py's
--batch-size/--concurrency/--model knobs.

Loads a small, real sample of verses READ-ONLY from a sarga's data.json
(never writes to corpus data -- this is a diagnostic tool, not an
ingestion one) and runs them through several model / batch-size
combinations, then a concurrency sweep, reporting REAL token usage
(gemini_client's usage_totals, not an estimate), wall-clock time, and the
generated text -- so cost/time tradeoffs for scaling gemini_summarize.py
to the full library get chosen from measured numbers, not guesses.

Two phases, both printed as a report and written to --out as JSON:
  1. model x batch-size grid -- same verses, every combination, sequential
     (concurrency=1) so timing/cost differences are attributable to the
     model/batch-size choice alone, not scheduling noise. Reports real
     tokens-per-verse and $-per-1000-verses for each combination (using
     --price-per-m-in/--price-per-m-out, since price varies by model and
     changes over time -- this script does not hardcode it).
  2. concurrency sweep -- one fixed model/batch-size (--sweep-model/
     --sweep-batch-size), the same batches re-submitted at each level in
     --concurrency-levels, recording wall-clock and any GeminiError kind
     (specifically watching for "quota"/"overloaded", i.e. rate-limiting)
     so a safe production --concurrency value can be picked from evidence.

Usage (needs GEMINI_API_KEY; this is a real, billed benchmark, not a
dry-run -- keep --verses small):
  GEMINI_API_KEY=... python3 tools/gemini_bench.py \
      --sarga-path data/DvaitaVedanta/Itara/Kavya/raghavendra_vijaya/sarga_2/data.json \
      --verses 12 --models gemini-flash-latest,gemini-flash-lite-latest \
      --batch-sizes 1,4,12 \
      --sweep-model gemini-flash-latest --sweep-batch-size 10 \
      --concurrency-levels 1,5,10,20 --sweep-batches 10 \
      --out /tmp/gemini-bench-report.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gemini_client import GeminiError  # noqa: E402
from gemini_summarize import (  # noqa: E402
    call_gemini_for_batch, call_gemini_for_verse,
)
from link_english_commentary import load_json  # noqa: E402


def load_sample_verses(sarga_path: Path, n: int) -> list[dict]:
    """Read-only: picks the first `n` verses with non-blank Sanskrit text.
    Does not care whether they already carry gemini_* fields -- this tool
    never writes them back, so re-analyzing an already-done verse is fine."""
    data = load_json(sarga_path)
    shlokas = data.get("shlokas") or {}
    out = []
    for n_str in sorted(shlokas.keys(), key=int):
        shloka = shlokas[n_str]
        sa = (shloka.get("sa") or "").strip()
        if not sa:
            continue
        en = (shloka.get("commentaries") or {}).get("pavamanacharya_english")
        out.append({"index": n_str, "sa": sa, "en": en})
        if len(out) >= n:
            break
    return out


def _chunked(items: list, size: int) -> list[list]:
    return [items[i:i + size] for i in range(0, len(items), size)]


def run_model_batch_combo(verses: list[dict], model: str, batch_size: int, api_key: str) -> dict:
    """Sequential (concurrency=1) run of `verses` through `model` at
    `batch_size`. Returns usage/timing/results for this one combination."""
    usage_totals: dict = {}
    outputs = {}
    errors = []
    t0 = time.monotonic()
    if batch_size <= 1:
        for v in verses:
            try:
                result = call_gemini_for_verse(v["sa"], v["en"], api_key, model, usage_totals)
                outputs[v["index"]] = result
            except GeminiError as e:
                errors.append({"index": v["index"], "kind": e.kind, "message": str(e)})
    else:
        for chunk in _chunked(verses, batch_size):
            try:
                response = call_gemini_for_batch(chunk, api_key, model, usage_totals)
                for r in response.get("results") or []:
                    if r.get("index"):
                        outputs[r["index"]] = r
            except GeminiError as e:
                errors.append({"kind": e.kind, "message": str(e),
                                "indices": [v["index"] for v in chunk]})
    elapsed = time.monotonic() - t0
    return {
        "model": model, "batch_size": batch_size, "verse_count": len(verses),
        "elapsed_seconds": round(elapsed, 2), "usage": usage_totals,
        "errors": errors, "sample_outputs": {k: outputs[k] for k in list(outputs)[:2]},
    }


def run_concurrency_sweep(verses: list[dict], model: str, batch_size: int, api_key: str,
                           levels: list[int]) -> list[dict]:
    """Re-submits the same `verses` (chunked into `batch_size`) at each
    concurrency level in `levels`, sequentially across levels (so levels
    don't interfere with each other's timing/rate-limit signal). Returns
    one report dict per level."""
    chunks = _chunked(verses, batch_size)
    reports = []
    for level in levels:
        usage_totals: dict = {}
        errors = []
        t0 = time.monotonic()
        if level <= 1:
            for chunk in chunks:
                try:
                    call_gemini_for_batch(chunk, api_key, model, usage_totals)
                except GeminiError as e:
                    errors.append({"kind": e.kind, "message": str(e)})
        else:
            with ThreadPoolExecutor(max_workers=level) as pool:
                futures = [pool.submit(call_gemini_for_batch, chunk, api_key, model, usage_totals)
                           for chunk in chunks]
                for fut in as_completed(futures):
                    try:
                        fut.result()
                    except GeminiError as e:
                        errors.append({"kind": e.kind, "message": str(e)})
        elapsed = time.monotonic() - t0
        quota_errors = sum(1 for e in errors if e["kind"] in ("quota", "overloaded"))
        reports.append({
            "concurrency": level, "batches": len(chunks), "verse_count": len(verses),
            "elapsed_seconds": round(elapsed, 2), "usage": usage_totals,
            "error_count": len(errors), "quota_or_overloaded_errors": quota_errors,
            "errors": errors,
        })
        print(f"  concurrency={level}: {len(chunks)} batches in {elapsed:.1f}s, "
              f"{len(errors)} error(s) ({quota_errors} quota/overloaded)")
    return reports


def _cost(usage: dict, price_in: float, price_out: float) -> float:
    """A thinking-capable model bills `thoughtsTokenCount` (internal
    reasoning, not part of the visible completion) at the output rate too
    -- confirmed by a real run where it was LARGER than the visible output
    for gemini-flash-latest (see gemini_client._accumulate_usage's
    docstring). Must be added to output_tokens here or cost is understated,
    sometimes by more than half."""
    billed_output = usage.get("output_tokens", 0) + usage.get("thoughts_tokens", 0)
    return (usage.get("prompt_tokens", 0) / 1_000_000 * price_in
            + billed_output / 1_000_000 * price_out)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sarga-path", required=True, type=Path)
    p.add_argument("--verses", type=int, default=12, help="Sample size for the model x batch-size grid")
    p.add_argument("--models", default="gemini-flash-latest,gemini-flash-lite-latest")
    p.add_argument("--batch-sizes", default="1,4,12")
    p.add_argument("--sweep-model", default="gemini-flash-latest")
    p.add_argument("--sweep-batch-size", type=int, default=10)
    p.add_argument("--sweep-batches", type=int, default=10, help="How many batches to submit per concurrency level")
    p.add_argument("--concurrency-levels", default="1,5,10,20")
    p.add_argument("--price-per-m-in", type=float, default=0.75, help="USD per million input tokens (for the report's $ estimate only)")
    p.add_argument("--price-per-m-out", type=float, default=3.75, help="USD per million output tokens")
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args(argv)

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("error: GEMINI_API_KEY is not set", file=sys.stderr)
        return 1

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    batch_sizes = [int(b) for b in args.batch_sizes.split(",") if b.strip()]
    levels = [int(c) for c in args.concurrency_levels.split(",") if c.strip()]

    print(f"=== Phase 1: model x batch-size grid ({args.verses} verses, sequential) ===")
    grid_verses = load_sample_verses(args.sarga_path, args.verses)
    grid_results = []
    for model in models:
        for batch_size in batch_sizes:
            print(f"  running model={model} batch_size={batch_size} ...")
            report = run_model_batch_combo(grid_verses, model, batch_size, api_key)
            usage = report["usage"]
            cost = _cost(usage, args.price_per_m_in, args.price_per_m_out)
            per_verse = cost / max(1, report["verse_count"])
            report["estimated_cost_usd"] = round(cost, 6)
            report["estimated_cost_usd_per_1000_verses"] = round(per_verse * 1000, 4)
            grid_results.append(report)
            thoughts_note = f", {usage['thoughts_tokens']:,} thinking tokens" if usage.get("thoughts_tokens") else ""
            print(f"    {usage.get('calls', 0)} call(s), "
                  f"{usage.get('prompt_tokens', 0):,} prompt + {usage.get('output_tokens', 0):,} output tokens"
                  f"{thoughts_note} = {usage.get('total_tokens', 0):,} total, "
                  f"{report['elapsed_seconds']}s, "
                  f"${report['estimated_cost_usd_per_1000_verses']}/1000 verses "
                  f"(at --price-per-m-in/out {args.price_per_m_in}/{args.price_per_m_out} -- "
                  f"pass this model's OWN real price if comparing against a different model), "
                  f"{len(report['errors'])} error(s), model_version={usage.get('model_version')}")

    print(f"\n=== Phase 2: concurrency sweep (model={args.sweep_model}, "
          f"batch_size={args.sweep_batch_size}, {args.sweep_batches} batches/level) ===")
    sweep_verses = load_sample_verses(args.sarga_path, args.sweep_batch_size * args.sweep_batches)
    sweep_results = run_concurrency_sweep(sweep_verses, args.sweep_model, args.sweep_batch_size,
                                           api_key, levels)

    report = {
        "sarga_path": str(args.sarga_path),
        "grid": grid_results,
        "concurrency_sweep": sweep_results,
    }
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=1)
        print(f"\nWrote full report (incl. sample outputs for quality review) to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
