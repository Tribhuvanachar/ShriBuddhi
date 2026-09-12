#!/usr/bin/env python3
"""
gemini_summarize.py — batch padaccheda/anvaya/summary generation for one
kavya's per-canto (sarga) data.json files, using Gemini.

Part of the Raghavendra Vijaya ingestion (see dge/PENDING.md). Unlike
tools/gemini_enrich.py (which detects citations and cross-validates them
against the corpus), this script's task has no local-verification step:
padaccheda (word-split), anvaya (prose word-order) and a plain-language
summary are Gemini's own linguistic analysis of one verse, not a claim
about the outside world tools/reference_resolution could check. So the
safety principle here is narrower and different: give Gemini everything
DGE already knows about the verse (the Sanskrit text, and the corpus's own
linked English translation if one exists) rather than asking it to
translate blind, and label every output as AI-generated and unreviewed
(see the gemini_padaccheda/gemini_anvaya/gemini_summary entries in
dge/js/core.js's KNOWN_COMMENTARY_LABELS) so a reader never mistakes a
first-pass model output for a vetted commentary.

Mirrors tools/gemini_enrich.py's CLI shape and tools/gemini_client.py for
the actual HTTP/retry/error-classification mechanics (shared, not
duplicated -- see that module).

Cost/throughput knobs (see dge/PENDING.md for the benchmark this shipped
with):
  --batch-size N   groups N verses into one Gemini request. This is the
                   real cost lever -- the fixed system-instruction/schema
                   overhead is paid once per request, not once per verse,
                   so a bigger batch spends far fewer input tokens per
                   verse. Default 1 (one request per verse, old behaviour).
  --concurrency N  runs that many batch requests in parallel via a thread
                   pool. This buys wall-clock time, not cost -- the same
                   tokens get billed either way -- but is safe to combine
                   with --batch-size for both. Default 1 (sequential, old
                   behaviour). Stay under whatever RPM your Gemini tier
                   allows; a 429 here surfaces as a GeminiError warning
                   for that batch, not a crash of the whole run.

Usage:
  GEMINI_API_KEY=... python3 tools/gemini_summarize.py \
      --sarga-dir dge/data/DvaitaVedanta/Itara/Kavya/raghavendra_vijaya --cantos 1-10 \
      --batch-size 10 --concurrency 5
  python3 tools/gemini_summarize.py --sarga-dir ... --cantos 1 --dry-run
"""
from __future__ import annotations

import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gemini_client import (  # noqa: E402
    DEFAULT_MODEL, GeminiError, call_gemini,
)
from link_english_commentary import load_json, save_json  # noqa: E402

SYSTEM_INSTRUCTION = (
    "You are assisting a Sanskrit digital library (DGE) in analysing one "
    "verse at a time from a Sanskrit kavya (Raghavendra Vijaya, a devotional "
    "epic). You will be given the verse's Sanskrit text, and -- when the "
    "library already has one -- a published English translation of it. Use "
    "that translation as context to keep your analysis faithful to the "
    "verse's actual meaning; do not let it substitute for genuinely reading "
    "the Sanskrit. Produce three things: (1) padaccheda -- the verse split "
    "into its words, in Devanagari, following two DISTINCT rules depending "
    "on what kind of boundary each split crosses: euphonic sandhi between "
    "separate syntactical words is resolved and those words are separated "
    "by a SPACE (e.g. तदेव -> तत् एव); the internal members of a compound "
    "(samasa) are instead separated by a HYPHEN, keeping the case ending "
    "only on the compound's final member (e.g. स्वभक्ताभीष्टदानाय -> "
    "स्व-भक्त-अभीष्ट-दानाय, not split into separate case-inflected words). "
    "Do not leave an unsplit compound as one solid block, and do not use a "
    "space where a hyphen belongs or vice versa; (2) anvaya -- the same "
    "words rearranged into plain prose (subject-object-verb) word order, "
    "in Devanagari, to aid comprehension; (3) a concise one-to-two sentence "
    "summary in English of what the verse says. If you cannot confidently "
    "produce one of these for this verse (e.g. the text is too corrupt/"
    "ambiguous), say so plainly in that field rather than guessing -- do "
    "not fabricate a plausible-looking analysis."
)

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "padaccheda": {"type": "string"},
        "anvaya": {"type": "string"},
        "summary": {"type": "string"},
    },
    "required": ["padaccheda", "anvaya", "summary"],
}

# Batch variant: same task, but Gemini analyses several verses in one call
# and must tag each result with the caller-supplied `index` so results can
# be matched back to the right verse -- never by response position, which
# would silently mis-attribute an analysis if Gemini reordered or dropped
# one (see analyze_batch()'s by_index lookup).
SYSTEM_INSTRUCTION_BATCH = (
    "You are assisting a Sanskrit digital library (DGE) in analysing "
    "several verses at once from a Sanskrit kavya (Raghavendra Vijaya, a "
    "devotional epic). You will be given a numbered list of verses, each "
    "with its Sanskrit text and -- when the library already has one -- a "
    "published English translation. Analyse each verse independently: one "
    "verse's content or context must never influence another verse's "
    "analysis. Use each verse's own translation (when given) as context to "
    "keep your analysis faithful to its actual meaning; do not let it "
    "substitute for genuinely reading the Sanskrit. For every verse "
    "produce three things: (1) padaccheda -- the verse split into its "
    "words, in Devanagari, following two DISTINCT rules depending on what "
    "kind of boundary each split crosses: euphonic sandhi between separate "
    "syntactical words is resolved and those words are separated by a "
    "SPACE (e.g. तदेव -> तत् एव); the internal members of a compound "
    "(samasa) are instead separated by a HYPHEN, keeping the case ending "
    "only on the compound's final member (e.g. स्वभक्ताभीष्टदानाय -> "
    "स्व-भक्त-अभीष्ट-दानाय, not split into separate case-inflected words). "
    "Do not leave an unsplit compound as one solid block, and do not use a "
    "space where a hyphen belongs or vice versa; (2) anvaya -- the same "
    "words rearranged into plain prose (subject-object-verb) word order, "
    "in Devanagari, to aid "
    "comprehension; (3) a concise one-to-two sentence summary in English "
    "of what the verse says. If you cannot confidently produce one of "
    "these for a particular verse (e.g. its text is too corrupt/"
    "ambiguous), say so plainly in that field rather than guessing -- do "
    "not fabricate a plausible-looking analysis, and do not omit that "
    "verse's result object because one field is uncertain. Return exactly "
    "one result object per verse given, in the same `results` array, each "
    "carrying the same `index` value it was given so the caller can match "
    "your output back to the correct verse."
)

RESPONSE_SCHEMA_BATCH = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "string"},
                    "padaccheda": {"type": "string"},
                    "anvaya": {"type": "string"},
                    "summary": {"type": "string"},
                },
                "required": ["index", "padaccheda", "anvaya", "summary"],
            },
        },
    },
    "required": ["results"],
}

FIELD_TO_KEY = {
    "padaccheda": "gemini_padaccheda",
    "anvaya": "gemini_anvaya",
    "summary": "gemini_summary",
}

DISPLAY_LABELS = {
    "gemini_padaccheda": "AI Padaccheda (Gemini, unreviewed)",
    "gemini_anvaya": "AI Anvaya (Gemini, unreviewed)",
    "gemini_summary": "AI Summary (Gemini, unreviewed)",
}


def build_prompt(sanskrit_text: str, english_translation: str | None) -> str:
    parts = [f"Sanskrit verse:\n{sanskrit_text}"]
    if english_translation:
        parts.append(f"\nExisting published English translation (for context only):\n{english_translation}")
    return "\n".join(parts)


def build_batch_prompt(verses: list[dict]) -> str:
    """verses: list of {"index": str, "sa": str, "en": str|None}."""
    parts = [f"You will analyse {len(verses)} verses below. Return one result "
             "object per verse in `results`, each tagged with its `index`."]
    for v in verses:
        block = f"\n---\nindex: {v['index']}\nSanskrit verse:\n{v['sa']}"
        if v.get("en"):
            block += f"\n\nExisting published English translation (for context only):\n{v['en']}"
        parts.append(block)
    return "\n".join(parts)


def call_gemini_for_verse(sanskrit_text: str, english_translation, api_key: str, model: str,
                           usage_totals: dict | None = None) -> dict:
    return call_gemini(
        SYSTEM_INSTRUCTION,
        build_prompt(sanskrit_text, english_translation),
        RESPONSE_SCHEMA,
        api_key,
        model,
        temperature=0.2,
        max_output_tokens=2048,
        usage_totals=usage_totals,
    )


def call_gemini_for_batch(verses: list[dict], api_key: str, model: str,
                           usage_totals: dict | None = None) -> dict:
    return call_gemini(
        SYSTEM_INSTRUCTION_BATCH,
        build_batch_prompt(verses),
        RESPONSE_SCHEMA_BATCH,
        api_key,
        model,
        temperature=0.2,
        max_output_tokens=2048 * max(1, len(verses)),
        usage_totals=usage_totals,
    )


def mock_analyze_verse(sanskrit_text: str, english_translation) -> dict:
    """Deterministic, network-free stand-in for call_gemini_for_verse(),
    used by --dry-run. Does NOT attempt real padaccheda/anvaya (that needs
    actual language understanding) -- it exists only to exercise the
    merge/labeling/idempotency mechanics of this script without a network
    call, same spirit as gemini_enrich.py's mock_detect_citations."""
    return {
        "padaccheda": f"[dry-run mock] {sanskrit_text}",
        "anvaya": f"[dry-run mock] {sanskrit_text}",
        "summary": "[dry-run mock] summary placeholder -- real analysis requires a live Gemini call",
    }


def analyze_shloka(shloka: dict, api_key, model: str, dry_run: bool, force: bool,
                    fields, usage_totals: dict | None = None) -> bool:
    """Mutates `shloka["commentaries"]` in place. Returns True if changed."""
    commentaries = shloka.setdefault("commentaries", {})
    missing = [f for f in fields if force or FIELD_TO_KEY[f] not in commentaries]
    if not missing:
        return False

    sanskrit_text = shloka.get("sa", "")
    if not sanskrit_text.strip():
        return False
    english_translation = commentaries.get("pavamanacharya_english")

    if dry_run:
        result = mock_analyze_verse(sanskrit_text, english_translation)
    else:
        result = call_gemini_for_verse(sanskrit_text, english_translation, api_key, model, usage_totals)

    changed = False
    for field in missing:
        value = (result.get(field) or "").strip()
        if value:
            commentaries[FIELD_TO_KEY[field]] = value
            changed = True
    return changed


def analyze_batch(chunk: list[tuple[str, dict]], api_key, model: str, dry_run: bool, force: bool,
                   fields, usage_totals: dict | None = None) -> int:
    """chunk: list of (n_str, shloka dict) for one canto. Mutates shlokas in
    place. Returns the count of shlokas actually changed.

    Results are matched back to verses by the `index` Gemini echoes, never
    by response position/order -- a verse missing from the response is left
    untouched (and warned about) rather than guessed via alignment, same
    "don't fabricate" principle as analyze_shloka()."""
    todo = []
    for n_str, shloka in chunk:
        commentaries = shloka.setdefault("commentaries", {})
        missing = [f for f in fields if force or FIELD_TO_KEY[f] not in commentaries]
        if not missing:
            continue
        sanskrit_text = shloka.get("sa", "")
        if not sanskrit_text.strip():
            continue
        todo.append((n_str, shloka, missing))
    if not todo:
        return 0

    verses_payload = [
        {"index": n_str, "sa": shloka.get("sa", ""), "en": shloka["commentaries"].get("pavamanacharya_english")}
        for n_str, shloka, _ in todo
    ]

    if dry_run:
        results = [
            {"index": v["index"], **mock_analyze_verse(v["sa"], v["en"])}
            for v in verses_payload
        ]
    else:
        response = call_gemini_for_batch(verses_payload, api_key, model, usage_totals)
        results = response.get("results") or []

    by_index = {r.get("index"): r for r in results if r.get("index")}

    changed = 0
    for n_str, shloka, missing in todo:
        r = by_index.get(n_str)
        if r is None:
            print(f"warning: batch response had no result for verse {n_str}", file=sys.stderr)
            continue
        commentaries = shloka["commentaries"]
        verse_changed = False
        for field in missing:
            value = (r.get(field) or "").strip()
            if value:
                commentaries[FIELD_TO_KEY[field]] = value
                verse_changed = True
        if verse_changed:
            changed += 1
    return changed


def _chunked(items: list, size: int) -> list[list]:
    return [items[i:i + size] for i in range(0, len(items), size)]


def run(sarga_dir: Path, cantos, model: str, dry_run: bool, force: bool,
        limit, fields, batch_size: int = 1, concurrency: int = 1) -> int:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not dry_run and not api_key:
        print("error: GEMINI_API_KEY is not set (pass --dry-run to test without one)",
              file=sys.stderr)
        return 1

    total_changed = 0
    total_considered = 0
    usage_totals: dict = {}
    for n in cantos:
        sarga_path = sarga_dir / f"sarga_{n}" / "data.json"
        if not sarga_path.exists():
            print(f"error: {sarga_path} does not exist", file=sys.stderr)
            return 1
        data = load_json(sarga_path)
        shlokas = data.get("shlokas")
        if not isinstance(shlokas, dict):
            print(f"error: {sarga_path} has no top-level 'shlokas' dict", file=sys.stderr)
            return 1

        n_strs = sorted(shlokas.keys(), key=int)
        if limit is not None:
            remaining = max(0, limit - total_considered)
            n_strs = n_strs[:remaining]
        total_considered += len(n_strs)
        items = [(n_str, shlokas[n_str]) for n_str in n_strs]

        canto_changed = 0
        if batch_size <= 1:
            # old, unbatched path -- one Gemini call per verse
            for n_str, shloka in items:
                try:
                    if analyze_shloka(shloka, api_key, model, dry_run, force, fields, usage_totals):
                        canto_changed += 1
                except GeminiError as e:
                    print(f"warning: canto {n} verse {n_str}: Gemini call failed ({e.kind}): {e}",
                          file=sys.stderr)
        else:
            chunks = _chunked(items, batch_size)
            if concurrency <= 1:
                for chunk in chunks:
                    try:
                        canto_changed += analyze_batch(chunk, api_key, model, dry_run, force, fields, usage_totals)
                    except GeminiError as e:
                        idxs = ",".join(n_str for n_str, _ in chunk)
                        print(f"warning: canto {n} batch [{idxs}]: Gemini call failed ({e.kind}): {e}",
                              file=sys.stderr)
            else:
                with ThreadPoolExecutor(max_workers=concurrency) as pool:
                    future_to_chunk = {
                        pool.submit(analyze_batch, chunk, api_key, model, dry_run, force, fields, usage_totals): chunk
                        for chunk in chunks
                    }
                    for future in as_completed(future_to_chunk):
                        chunk = future_to_chunk[future]
                        try:
                            canto_changed += future.result()
                        except GeminiError as e:
                            idxs = ",".join(n_str for n_str, _ in chunk)
                            print(f"warning: canto {n} batch [{idxs}]: Gemini call failed ({e.kind}): {e}",
                                  file=sys.stderr)

        if canto_changed:
            # add/refresh display labels for whichever fields this run touched
            avail = data.setdefault("metadata", {}).setdefault("availableCommentaries", {})
            for field in fields:
                avail[FIELD_TO_KEY[field]] = DISPLAY_LABELS[FIELD_TO_KEY[field]]
            save_json(sarga_path, data)
        total_changed += canto_changed
        print(f"canto {n}: analyzed {canto_changed} verse(s)")

    print(f"Total: {total_changed}/{total_considered} verse(s) analyzed across {len(cantos)} canto(s)")
    if usage_totals:
        model_used = usage_totals.get("model_version") or model
        thoughts = usage_totals.get("thoughts_tokens", 0)
        thoughts_note = f", {thoughts:,} thinking tokens (billed at the output rate, not shown above)" if thoughts else ""
        print(f"Gemini usage: {usage_totals['calls']} call(s), "
              f"{usage_totals['prompt_tokens']:,} prompt tokens, "
              f"{usage_totals['output_tokens']:,} output tokens{thoughts_note}, "
              f"{usage_totals['total_tokens']:,} total tokens "
              f"(model={model_used}, batch_size={batch_size}, concurrency={concurrency}; "
              f"a fallback-model call inside a single attempt is included in these totals)")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sarga-dir", required=True, type=Path,
                    help="Directory containing sarga_N/data.json subfolders")
    p.add_argument("--cantos", default="1-10",
                    help="Canto range or comma list, e.g. '1-10' or '1,3,5'")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--dry-run", action="store_true",
                    help="No network call; use a deterministic mock analyzer instead")
    p.add_argument("--force", action="store_true",
                    help="Re-analyze verses that already carry these commentary keys")
    p.add_argument("--limit", type=int, default=None,
                    help="Analyze at most N verses total (for a first pass / smoke test)")
    p.add_argument("--fields", default="padaccheda,anvaya,summary",
                    help="Comma list of which of padaccheda/anvaya/summary to generate")
    p.add_argument("--batch-size", type=int, default=1,
                    help="Verses per Gemini request (cost lever -- amortizes the fixed "
                         "system-instruction/schema overhead across more verses). Default 1.")
    p.add_argument("--concurrency", type=int, default=1,
                    help="Parallel in-flight requests (time lever -- same tokens billed "
                         "either way). Default 1 (sequential).")
    args = p.parse_args(argv)

    cantos = []
    for part in args.cantos.split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = part.split("-")
            cantos.extend(range(int(lo), int(hi) + 1))
        else:
            cantos.append(int(part))
    fields = [f.strip() for f in args.fields.split(",") if f.strip()]
    for f in fields:
        if f not in FIELD_TO_KEY:
            print(f"error: unknown field '{f}' (expected one of {sorted(FIELD_TO_KEY)})", file=sys.stderr)
            return 1
    if args.batch_size < 1:
        print("error: --batch-size must be >= 1", file=sys.stderr)
        return 1
    if args.concurrency < 1:
        print("error: --concurrency must be >= 1", file=sys.stderr)
        return 1

    return run(args.sarga_dir, cantos, args.model, args.dry_run, args.force, args.limit, fields,
               args.batch_size, args.concurrency)


if __name__ == "__main__":
    raise SystemExit(main())
