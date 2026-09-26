#!/usr/bin/env python3
"""
proofread.py -- Gemini-proofread segmented OCR blocks, in place, resumably.

The gap this fills: nothing in the repo proofreads *staged blocks*. The
Gemini workflows all operate on corpus text that is already clean
(gemini-enrich, gemini-summarize-kavya, gemini-deep-analysis-kavya), and
ocr-sanskrit-commentary.yml re-OCRs a PDF through Vision before
proofreading, keyed to numbered shlokas -- which cannot address Aitareya,
whose target uses hierarchical `items` and whose staged text came from
Sarvam, not Vision.

So tools/aitareya/write_layers.py refuses to run: it will not put
unproofread OCR on a shelf where three of the five layers it writes would
replace text a reader can see today. This is what clears that refusal.

The prompt keeps the anti-hallucination rules of tools/ocr_pipeline.py's
PROOFREAD_PROMPT -- correct OCR errors only, never rewrite, never invent,
self-classify -- and drops its verse-number machinery, which is about
shloka markers in a margin and has nothing to say about continuous
commentary prose.

RESUMABLE BY DESIGN. A block that already carries `text_proofread` is
skipped, so an interrupted run costs nothing to resume and a second run
over a finished file spends zero. At ~1,400 blocks across the three
volumes that matters: without it, one timeout means paying twice.

CONCURRENT. The first version called Gemini one block at a time. On 22 Sep
that took over two hours for 1,406 blocks and the implied rate got worse
as it went -- 2.3 s/block, then 3.6, then 4.9 -- because gemini_client's
HTTP timeout is 60 s with no retry, so every slow call stalls the whole
queue behind it. This project already had the answer: tools/gemini_bench.py
exists to sweep --concurrency and pick a safe production value from
evidence. --concurrency defaults to 6, which keeps the wall clock sane
without inviting the quota errors that sweep is for.

BUDGET. --budget is in rupees, enforced before each call against the
ledger's measured rate, and --real is the only thing that spends.

  python3 tools/aitareya/proofread.py                      # plan
  python3 tools/aitareya/proofread.py --real --budget 200
  python3 tools/aitareya/proofread.py --staged-dir <clone>/data/ocr_staging/aitareya

WHERE THIS ACTUALLY RUNS. GEMINI_API_KEY is a secret on the PUBLIC repo
(JagatTest), not on this one -- verified 22 Sep: a run here reported the
secret empty, while JagatTest's gemini-resolve-conflicts.yml shows it set.
That is deliberate and its own workflow says why: "Actions is free and
unlimited on a public repository and capped at 2,000 minutes a month on a
private one. Nothing sensitive is committed here: the text arrives from
the private repo and leaves for it." So the workflow that calls this lives
there, clones this repo's staging branch, and pushes the result back --
hence --staged-dir.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
STAGED = ROOT / "data/ocr_staging/aitareya"

# admin/config/spend_report.json: Rs79.39 over 1,536 pages.
RATE_PER_PAGE = 0.0517
# Sarvam's own page boundaries are gone once blocks are merged, so cost is
# estimated by characters instead, calibrated on this corpus: the three
# volumes are 2.15M Devanagari characters over 1,910 pages -> ~1,127/page.
CHARS_PER_PAGE = 1127

# Substituted by main() on the first real run, and by tests.
call_gemini = None
GeminiError = Exception

SYSTEM = ("You are proofreading raw OCR of a printed Sanskrit commentary "
          "(Devanagari). You correct scanning errors and nothing else.")

PROMPT = """Below is one block of OCR output from a scanned Sanskrit commentary.

Rules:
1. Correct OCR mistakes only -- misread characters, broken or merged words, obvious scan artefacts. Do NOT rewrite, summarise, paraphrase, modernise or "improve" the wording.
2. Preserve the Sanskrit exactly as intended. Preserve sandhi, case endings and punctuation (।, ॥) as printed.
3. Preserve paragraph and line order. Do not reorder, drop or add sentences.
4. Never invent text that is not grounded in the OCR reading, beyond fixing a small OCR-level error that the context clearly resolves.
5. Running heads, page numbers and catchwords are page furniture, not text: drop them if they have been spliced into the middle of a sentence.
6. Self-report a "classification":
   - "accept": the reading is unambiguous and plausible as-is.
   - "review": you made a judgment call -- likely right, but a human should glance at it.
   - "unresolved": you cannot determine confident text. Keep your best guess anyway, but do not invent.
   Give a brief "note" only when the classification is not "accept"; otherwise leave it empty.
7. Output ONLY valid JSON, no markdown fences, no commentary before or after.

OCR block:
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "text": {"type": "string"},
        "classification": {"type": "string", "enum": ["accept", "review", "unresolved"]},
        "note": {"type": "string"},
    },
    "required": ["text", "classification"],
}


def est_cost(chars: int) -> float:
    return (chars / CHARS_PER_PAGE) * RATE_PER_PAGE


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--volumes", default="bhagavantaraya,ratnamala")
    ap.add_argument("--budget", type=float, default=200.0, help="rupees")
    ap.add_argument("--real", action="store_true")
    ap.add_argument("--concurrency", type=int, default=6,
                    help="parallel Gemini calls. 1 restores the old "
                         "one-at-a-time behaviour")
    ap.add_argument("--model", default=None)
    ap.add_argument("--staged-dir", default=None,
                    help="where the *_segmented.json files are. Defaults to "
                         "this repo's data/ocr_staging/aitareya. The workflow "
                         "that actually runs this lives in the PUBLIC repo "
                         "(free Actions minutes) and points it at a clone of "
                         "the private one, so the path must be settable.")
    args = ap.parse_args()

    staged = Path(args.staged_dir) if args.staged_dir else STAGED
    files = []
    for vol in args.volumes.split(","):
        p = staged / f"{vol}_segmented.json"
        if not p.exists():
            print(f"{vol}: no staged file at {p} -- run segment.py --write first")
            continue
        doc = json.loads(p.read_text())
        todo = [b for b in doc["blocks"] if not b.get("text_proofread")]
        chars = sum(len(b.get("text") or "") for b in todo)
        print(f"{vol:<18} {len(doc['blocks']):>4} blocks, {len(todo):>4} to do, "
              f"{chars:>9,} chars, est Rs{est_cost(chars):.2f}")
        files.append((p, doc, todo))

    total = sum(est_cost(sum(len(b.get('text') or '') for b in t)) for _, _, t in files)
    print(f"\ntotal estimate: Rs{total:.2f}   budget: Rs{args.budget:.2f}")

    if not args.real:
        print("\n(plan only -- pass --real to spend)")
        return 0

    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        print("\nGEMINI_API_KEY is not set in this environment.\n"
              "That is expected locally -- see docs/CREDENTIALS.md. Run this "
              "through .github/workflows/gemini-proofread-blocks.yml, where the\n"
              "secret is available, rather than pasting a key here.",
              file=sys.stderr)
        return 1

    # Bound onto the module so a test can substitute it. Imported here
    # rather than at the top so --plan works without gemini_client present.
    global call_gemini, GeminiError
    if call_gemini is None:
        from gemini_client import call_gemini as _cg, GeminiError as _ge  # noqa: E402
        call_gemini, GeminiError = _cg, _ge

    spent, done, usage = 0.0, 0, {}
    lock = threading.Lock()
    budget = args.budget
    model = args.model

    def one(b):
        """One block. Returns its cost, or 0 if nothing was billed.

        The budget is checked inside the lock before the call, so N workers
        cannot each decide there is room for the same last rupee.
        """
        nonlocal spent, done
        text = (b.get("text") or "").strip()
        if not text:
            return 0.0
        c = est_cost(len(text))
        with lock:
            if spent + c > budget:
                return None          # signals: stop, budget reached
            spent += c
        try:
            out = call_gemini(SYSTEM, PROMPT + text, SCHEMA, key,
                              **({"model": model} if model else {}),
                              max_output_tokens=32768, usage_totals=usage)
        except GeminiError as e:
            with lock:
                spent -= c           # not billed, do not charge the budget
            print(f"  block p{b.get('page')} failed: {e} -- leaving it "
                  f"unproofread and carrying on")
            return 0.0
        b["text_proofread"] = out.get("text") or text
        b["classification"] = out.get("classification", "unresolved")
        if out.get("note"):
            b["note"] = out["note"]
        with lock:
            done += 1
            if done % 25 == 0:
                print(f"  {done} blocks, Rs{spent:.2f}")
        return c

    for path, doc, todo in files:
        stop = False
        with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
            futures = {pool.submit(one, b): b for b in todo}
            for f in as_completed(futures):
                if f.result() is None and not stop:
                    stop = True
                    print(f"budget reached at Rs{spent:.2f} -- letting the "
                          f"calls already in flight finish, then stopping; "
                          f"rerun to continue where this left off")
        # Written once per volume rather than every 25 blocks: with workers
        # mutating `doc` concurrently, a mid-flight dump could serialise a
        # half-updated structure. The pool is drained by the time we get here.
        # A file is only marked proofread when nothing is left undone in it.
        if all(x.get("text_proofread") for x in doc["blocks"] if (x.get("text") or "").strip()):
            doc["proofread"] = True
            doc["proofread_usage"] = usage
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
        try:
            shown = path.relative_to(ROOT)
        except ValueError:
            shown = path          # a clone outside this repo
        print(f"wrote {shown}  proofread={doc.get('proofread', False)}")

    print(f"\n{done} blocks proofread, about Rs{spent:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
