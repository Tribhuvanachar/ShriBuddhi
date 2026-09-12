#!/usr/bin/env python3
"""
gemini_deep_analysis.py — chandas (metre), alankara (figures of speech),
samasa breakdown, and pratipadartha (word-by-word gloss) generation for
verses that already have gemini_padaccheda/gemini_anvaya (see
tools/gemini_summarize.py). A deliberate second pass, not a bigger version
of the first one: reuses the already-generated padaccheda/anvaya as
context instead of re-deriving them (they cost real money once already --
regenerating them here would be pure waste), and only runs on verses that
have them, skipping (with a warning) anything that doesn't.

Schema is adapted from an external review's proposal, with two changes
made after checking it against this project's own conventions:
  - Dropped "cross_references" entirely. This project already has a
    dedicated, verified citation pipeline (tools/gemini_enrich.py +
    tools/reference_resolution/) that cross-checks a detected citation
    against the actual corpus before trusting it. A bare Gemini-claimed
    "see also Bhagavata Purana 7.8" here, with no such check, is exactly
    the kind of unverifiable claim that pipeline exists to prevent --
    don't undermine it by adding a second, unverified citation path.
  - padaccheda is NOT regenerated -- it's read from the verse's existing
    gemini_padaccheda and given to Gemini as the basis for samasa_vishesha
    (which compounds it names must come from that padaccheda, not a fresh
    guess), so a verse without one yet is skipped rather than silently
    redone from scratch at extra cost.

Like gemini_summarize.py's batch mode, an external review flagged that a
much heavier per-verse schema (5 structured fields here vs. 3 short
strings there) risks output-token truncation and quality loss when many
verses share one call -- plausible for a schema this size, but NOT
something to take on faith: --batch-size defaults to 1 here specifically
so it can be benchmarked against real output before trusting a bigger
value (tools/gemini_bench.py's pattern, not built into this script itself
since it operates in a different task than gemini_bench.py's target).

Stored per-verse under `gemini_deep_analysis` (a nested object, NOT
under `commentaries` -- render.js's commentary blocks expect a plain
string per key, and this is structured data). Rendered via the existing
Shloka Fields settings toggles (Pratipadartha/Tatparya/Vyakarana/Vrutta/
Alankara) -- see SHLOKA_EXTRA_FIELDS in dge/js/config.js, whose dataKeys
point at this object's own field names (23 Aug 2026).

Usage:
  GEMINI_API_KEY=... python3 tools/gemini_deep_analysis.py \
      --sarga-dir dge/data/DvaitaVedanta/Itara/Kavya/raghavendra_vijaya --cantos 1-10
  python3 tools/gemini_deep_analysis.py --sarga-dir ... --cantos 1 --dry-run
"""
from __future__ import annotations

import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gemini_client import DEFAULT_MODEL, GeminiError, call_gemini  # noqa: E402
from link_english_commentary import load_json, save_json  # noqa: E402

SYSTEM_INSTRUCTION = (
    "You are an expert Sanskrit grammarian and kavya scholar analysing one "
    "verse at a time from a Sanskrit kavya (Raghavendra Vijaya, a devotional "
    "epic). You will be given the verse's Sanskrit text, its already-"
    "generated padaccheda (word-split, with samasa/compound members "
    "already hyphen-separated) and anvaya (prose word order), and -- when "
    "available -- a published English translation. Treat the given "
    "padaccheda as authoritative for which compounds exist in this verse; "
    "do not re-split the verse yourself. Produce: "
    "(1) chandas -- the verse's metre: its name (Sanskrit, with a "
    "transliteration), the syllable/gana structure if you can state it "
    "confidently, and the classical lakshana verse defining that metre if "
    "you know it (leave lakshana empty if you don't -- do not invent one); "
    "(2) alankara -- any figures of speech genuinely present (Shabdalankara "
    "or Arthalankara), each with its name, type, and a one-sentence "
    "justification grounded in the verse's actual words; return an empty "
    "list if none are clearly present rather than forcing a match; "
    "(3) samasa_vishesha -- for EVERY hyphenated compound in the given "
    "padaccheda (and only those), its split into member words, the samasa "
    "type (e.g. Tatpurusha, Bahuvrihi, Karmadharaya, Dvandva, Avyayibhava), "
    "and its vigraha vakya (analytical paraphrase); (4) pratipadartha -- a "
    "word-by-word gloss in the anvaya's order: each word's derivation/"
    "etymology if it is not simply its dictionary form (vigraha -- leave "
    "empty for a plain undeclined/underived word rather than repeating the "
    "word itself), its case/tense-mood-person (vibhakti for a noun, or "
    "dhatu+lakara+purusha+vacana for a verb), and its meaning; (5) "
    "bhavartha -- the verse's devotional/literary import in 1-3 sentences, "
    "distinct from a plain factual summary: what the verse is DOING "
    "(invoking, praising, establishing a theme) as much as what it says; "
    "(6) vyakarana_vishesha -- notable grammatical points about this verse "
    "as a whole that the pratipadartha table and samasa_vishesha don't "
    "already cover (an unusual sandhi, a rare verb formation, unusual "
    "sandhi/vibhakti usage) -- leave empty rather than restating what's "
    "already in those two fields. If you cannot confidently produce any "
    "one of these for this verse, say so plainly in a 'confidence_note' "
    "field rather than guessing -- do not fabricate a plausible-looking "
    "analysis, especially for chandas/alankara identification, where a "
    "wrong confident answer is worse than an honest 'uncertain'."
)

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "chandas": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "gana_structure": {"type": "string"},
                "lakshana": {"type": "string"},
            },
            "required": ["name"],
        },
        "alankara": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "type": {"type": "string", "enum": ["Shabdalankara", "Arthalankara"]},
                    "justification": {"type": "string"},
                },
                "required": ["name", "type", "justification"],
            },
        },
        "samasa_vishesha": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "compound": {"type": "string"},
                    "split": {"type": "string"},
                    "samasa_type": {"type": "string"},
                    "vigraha": {"type": "string"},
                },
                "required": ["compound", "split", "samasa_type", "vigraha"],
            },
        },
        "pratipadartha": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "order": {"type": "integer"},
                    "pada": {"type": "string"},
                    "vigraha": {"type": "string"},
                    "vibhakti_dhatu": {"type": "string"},
                    "artha": {"type": "string"},
                },
                "required": ["pada", "artha"],
            },
        },
        "bhavartha": {"type": "string"},
        "vyakarana_vishesha": {"type": "string"},
        "confidence_note": {"type": "string"},
    },
    "required": ["chandas", "alankara", "samasa_vishesha", "pratipadartha", "bhavartha"],
}

SYSTEM_INSTRUCTION_BATCH = SYSTEM_INSTRUCTION.replace(
    "analysing one verse at a time", "analysing several verses at once, each independently",
) + (
    " Return exactly one result object per verse given, in the same "
    "`results` array, each carrying the same `index` value it was given "
    "so the caller can match your output back to the correct verse."
)

RESPONSE_SCHEMA_BATCH = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"index": {"type": "string"}, **RESPONSE_SCHEMA["properties"]},
                "required": ["index"] + RESPONSE_SCHEMA["required"],
            },
        },
    },
    "required": ["results"],
}

FIELD_KEY = "gemini_deep_analysis"


def build_prompt(sanskrit_text: str, padaccheda: str, anvaya: str, english_translation: str | None) -> str:
    parts = [
        f"Sanskrit verse:\n{sanskrit_text}",
        f"\nPadaccheda (compounds already hyphen-separated):\n{padaccheda}",
        f"\nAnvaya:\n{anvaya}",
    ]
    if english_translation:
        parts.append(f"\nExisting published English translation (for context only):\n{english_translation}")
    return "\n".join(parts)


def build_batch_prompt(verses: list[dict]) -> str:
    parts = [f"You will analyse {len(verses)} verses below. Return one result "
             "object per verse in `results`, each tagged with its `index`."]
    for v in verses:
        block = (f"\n---\nindex: {v['index']}\nSanskrit verse:\n{v['sa']}"
                 f"\n\nPadaccheda:\n{v['padaccheda']}\n\nAnvaya:\n{v['anvaya']}")
        if v.get("en"):
            block += f"\n\nExisting published English translation (for context only):\n{v['en']}"
        parts.append(block)
    return "\n".join(parts)


def call_gemini_for_verse(sanskrit_text: str, padaccheda: str, anvaya: str, english_translation,
                           api_key: str, model: str, usage_totals: dict | None = None) -> dict:
    return call_gemini(
        SYSTEM_INSTRUCTION, build_prompt(sanskrit_text, padaccheda, anvaya, english_translation),
        RESPONSE_SCHEMA, api_key, model, temperature=0.1, max_output_tokens=4096, usage_totals=usage_totals,
    )


def call_gemini_for_batch(verses: list[dict], api_key: str, model: str,
                           usage_totals: dict | None = None) -> dict:
    return call_gemini(
        SYSTEM_INSTRUCTION_BATCH, build_batch_prompt(verses), RESPONSE_SCHEMA_BATCH, api_key, model,
        temperature=0.1, max_output_tokens=4096 * max(1, len(verses)), usage_totals=usage_totals,
    )


def mock_analyze_verse(*args, **kwargs) -> dict:
    """--dry-run stand-in, same spirit as gemini_summarize.py's mock."""
    return {
        "chandas": {"name": "[dry-run mock]", "gana_structure": "", "lakshana": ""},
        "alankara": [], "samasa_vishesha": [], "pratipadartha": [],
        "bhavartha": "[dry-run mock] bhavartha placeholder",
        "vyakarana_vishesha": "", "confidence_note": "",
    }


def _verse_prereqs(shloka: dict) -> tuple[str, str] | None:
    """Returns (padaccheda, anvaya) if both already exist for this verse,
    else None -- callers skip rather than regenerate them here."""
    commentaries = shloka.get("commentaries") or {}
    padaccheda = commentaries.get("gemini_padaccheda")
    anvaya = commentaries.get("gemini_anvaya")
    if not padaccheda or not anvaya:
        return None
    return padaccheda, anvaya


def analyze_shloka(shloka: dict, api_key, model: str, dry_run: bool, force: bool,
                    usage_totals: dict | None = None) -> str:
    """Mutates `shloka` in place. Returns 'analyzed', 'skipped_existing',
    or 'skipped_no_prereqs'."""
    if FIELD_KEY in shloka and not force:
        return "skipped_existing"
    prereqs = _verse_prereqs(shloka)
    if prereqs is None:
        return "skipped_no_prereqs"
    padaccheda, anvaya = prereqs

    sanskrit_text = shloka.get("sa", "")
    if not sanskrit_text.strip():
        return "skipped_no_prereqs"
    english_translation = (shloka.get("commentaries") or {}).get("pavamanacharya_english")

    if dry_run:
        result = mock_analyze_verse()
    else:
        result = call_gemini_for_verse(sanskrit_text, padaccheda, anvaya, english_translation,
                                        api_key, model, usage_totals)
    shloka[FIELD_KEY] = result
    return "analyzed"


def analyze_batch(chunk: list[tuple[str, dict]], api_key, model: str, dry_run: bool, force: bool,
                   usage_totals: dict | None = None) -> dict:
    """chunk: list of (n_str, shloka dict). Mutates shlokas in place.
    Returns counts by outcome. Matches back to verses by the `index`
    Gemini echoes, never by response position -- a verse missing from the
    response is left untouched and warned about, not guessed via
    alignment (same principle as gemini_summarize.py's analyze_batch)."""
    todo = []
    counts = {"analyzed": 0, "skipped_existing": 0, "skipped_no_prereqs": 0}
    for n_str, shloka in chunk:
        if FIELD_KEY in shloka and not force:
            counts["skipped_existing"] += 1
            continue
        prereqs = _verse_prereqs(shloka)
        sanskrit_text = shloka.get("sa", "")
        if prereqs is None or not sanskrit_text.strip():
            counts["skipped_no_prereqs"] += 1
            continue
        padaccheda, anvaya = prereqs
        todo.append((n_str, shloka, padaccheda, anvaya))
    if not todo:
        return counts

    verses_payload = [
        {"index": n_str, "sa": shloka.get("sa", ""), "padaccheda": padaccheda, "anvaya": anvaya,
         "en": (shloka.get("commentaries") or {}).get("pavamanacharya_english")}
        for n_str, shloka, padaccheda, anvaya in todo
    ]

    if dry_run:
        results = [{"index": v["index"], **mock_analyze_verse()} for v in verses_payload]
    else:
        response = call_gemini_for_batch(verses_payload, api_key, model, usage_totals)
        results = response.get("results") or []

    by_index = {r.get("index"): r for r in results if r.get("index")}
    for n_str, shloka, _, _ in todo:
        r = by_index.get(n_str)
        if r is None:
            print(f"warning: batch response had no result for verse {n_str}", file=sys.stderr)
            continue
        shloka[FIELD_KEY] = {k: v for k, v in r.items() if k != "index"}
        counts["analyzed"] += 1
    return counts


def _chunked(items: list, size: int) -> list[list]:
    return [items[i:i + size] for i in range(0, len(items), size)]


def run(sarga_dir: Path, cantos, model: str, dry_run: bool, force: bool, limit,
        batch_size: int = 1, concurrency: int = 1) -> int:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not dry_run and not api_key:
        print("error: GEMINI_API_KEY is not set (pass --dry-run to test without one)", file=sys.stderr)
        return 1

    total_analyzed = total_no_prereqs = total_considered = 0
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

        canto_analyzed = canto_no_prereqs = 0
        if batch_size <= 1:
            for n_str, shloka in items:
                try:
                    outcome = analyze_shloka(shloka, api_key, model, dry_run, force, usage_totals)
                    if outcome == "analyzed":
                        canto_analyzed += 1
                    elif outcome == "skipped_no_prereqs":
                        canto_no_prereqs += 1
                except GeminiError as e:
                    print(f"warning: canto {n} verse {n_str}: Gemini call failed ({e.kind}): {e}", file=sys.stderr)
        else:
            chunks = _chunked(items, batch_size)
            if concurrency <= 1:
                for chunk in chunks:
                    try:
                        counts = analyze_batch(chunk, api_key, model, dry_run, force, usage_totals)
                        canto_analyzed += counts["analyzed"]
                        canto_no_prereqs += counts["skipped_no_prereqs"]
                    except GeminiError as e:
                        idxs = ",".join(n_str for n_str, _ in chunk)
                        print(f"warning: canto {n} batch [{idxs}]: Gemini call failed ({e.kind}): {e}", file=sys.stderr)
            else:
                with ThreadPoolExecutor(max_workers=concurrency) as pool:
                    future_to_chunk = {
                        pool.submit(analyze_batch, chunk, api_key, model, dry_run, force, usage_totals): chunk
                        for chunk in chunks
                    }
                    for future in as_completed(future_to_chunk):
                        chunk = future_to_chunk[future]
                        try:
                            counts = future.result()
                            canto_analyzed += counts["analyzed"]
                            canto_no_prereqs += counts["skipped_no_prereqs"]
                        except GeminiError as e:
                            idxs = ",".join(n_str for n_str, _ in chunk)
                            print(f"warning: canto {n} batch [{idxs}]: Gemini call failed ({e.kind}): {e}", file=sys.stderr)

        if canto_analyzed:
            # Deliberately NOT added to metadata.availableCommentaries --
            # that catalog is for keys the reader looks up inside
            # shlokas[n].commentaries (a plain string per key); this data
            # lives at shlokas[n].gemini_deep_analysis, a sibling nested
            # object, since render.js's commentary blocks expect text, not
            # structured chandas/alankara/samasa data. Adding it there
            # would register a commentary toggle that always renders
            # nothing until a real reader UI for this exists (see
            # dge/PENDING.md) -- a phantom entry, not a working one.
            save_json(sarga_path, data)
        total_analyzed += canto_analyzed
        total_no_prereqs += canto_no_prereqs
        print(f"canto {n}: analyzed {canto_analyzed} verse(s), "
              f"{canto_no_prereqs} skipped (no padaccheda/anvaya yet -- run gemini_summarize.py first)")

    print(f"Total: {total_analyzed}/{total_considered} verse(s) analyzed across {len(cantos)} canto(s) "
          f"({total_no_prereqs} lacked prerequisites)")
    if usage_totals:
        model_used = usage_totals.get("model_version") or model
        thoughts = usage_totals.get("thoughts_tokens", 0)
        thoughts_note = f", {thoughts:,} thinking tokens" if thoughts else ""
        print(f"Gemini usage: {usage_totals.get('calls', 0)} call(s), "
              f"{usage_totals.get('prompt_tokens', 0):,} prompt tokens, "
              f"{usage_totals.get('output_tokens', 0):,} output tokens{thoughts_note}, "
              f"{usage_totals.get('total_tokens', 0):,} total tokens "
              f"(model={model_used}, batch_size={batch_size}, concurrency={concurrency})")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sarga-dir", required=True, type=Path)
    p.add_argument("--cantos", default="1-10", help="Canto range or comma list, e.g. '1-10' or '1,3,5'")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--force", action="store_true", help="Re-analyze verses that already have gemini_deep_analysis")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--batch-size", type=int, default=1,
                    help="Verses per Gemini request. Default 1: this schema is heavy enough (5 structured "
                         "fields/verse) that batching risks output-token truncation -- benchmark before "
                         "raising this (tools/gemini_bench.py's pattern), don't assume it's safe.")
    p.add_argument("--concurrency", type=int, default=1)
    args = p.parse_args(argv)

    cantos = []
    for part in args.cantos.split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = part.split("-")
            cantos.extend(range(int(lo), int(hi) + 1))
        else:
            cantos.append(int(part))
    if args.batch_size < 1:
        print("error: --batch-size must be >= 1", file=sys.stderr)
        return 1
    if args.concurrency < 1:
        print("error: --concurrency must be >= 1", file=sys.stderr)
        return 1

    return run(args.sarga_dir, cantos, args.model, args.dry_run, args.force, args.limit,
               args.batch_size, args.concurrency)


if __name__ == "__main__":
    raise SystemExit(main())
