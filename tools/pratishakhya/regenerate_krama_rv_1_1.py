#!/usr/bin/env python3
"""Regenerates RV 1.1's Krama-patha from DGE's own Pada-patha/Samhita-patha
data, computationally, using krama_engine.generate_verse() -- no hardcoded
verse/pair/Parigraha strings. This is the direct response to the reviewed
spec's success criterion (11 Sep 2026): "Delete the manually supplied RV 1.1
pair strings and Parigraha strings, regenerate RV 1.1 entirely from DGE
Pada/Samhita, and obtain the same result ... with every nontrivial
transformation traceable to an actual sutra."

Input: dge/data/vedas/rigveda/shakala_shakha/samhita/mandala_01/data.json,
items 1.1.1-1.1.9 ONLY (pada_patha, samhita_patha fields). Nothing else from
that file, and no per-verse word lists typed by hand anywhere in this script.

Second review pass (11 Sep 2026, "chatgpt review"): the first run of this
script was correctly flagged for (1) presenting unaudited top-level counts
with no visible invariant proving them consistent, (2) letting "confidence"
double as if it meant "verified correct" when it only ever meant "the
phonology classifier picked a branch it's sure of", and (3) a comparison
report that keys by flat global index, so one inserted/removed unit
cascades into many spurious-looking downstream mismatches. This version
fixes all three: build_counts() now asserts its own invariant rather than
just reporting numbers; attest_ardharcas() checks each ardharca's FULL
chained reconstruction (sanskrit_phonology.reconstruct_chain) against DGE's
own attested samhita_patha, layering this repo's long-planned VALIDATE mode
(architecture doc sec.7) on top of GENERATE; and compare_against_old() keys
by (ardharca_index, unit_index_within_ardharca).

A first attempt at attestation compared each ISOLATED 2-word Krama pair
against the continuous samhita text with a plain substring check -- that
was itself wrong and is not used here: a word's OWN Krama pair is computed
against just its one neighbour, but its form in the CONTINUOUS text is
often governed by a DIFFERENT (later) neighbour, so most "mismatches" that
check produced were expected divergences, not bugs (e.g. "purohitam" the
Krama pair vs. "purohitaM" -- anusvara -- in the continuous chain, because
the continuous text also has yajJasya right after it). Building the
CORRECT check (chain reconstruction, i.e. actually simulating how the
continuous text is built by folding samhita_join across a whole ardharca)
surfaced two real, narrow, now-fixed phonology bugs along the way: (a)
resolve_compound() misfiring on a chained string's own elision-avagraha,
collapsing every space built up so far (fixed via samhita_join's new
resolve_w1_compound=False parameter); (b) the lexical-exception tables
(IRREGULAR_VISARGA_STEMS etc.) only matching a bare word, never that word
occurring at the end of a longer chain (fixed via _match_lexical_suffix()).
One further, real, NOT-yet-fixed bug remains and is documented where it's
found: the indic_transliteration SLP1 scheme cannot distinguish "र्ऋ"
(bare consonant, then an independent vowel) from "रृ" (consonant + a
dependent vowel-matra) -- both round-trip to the identical SLP1 "rf" --
so a chain that passes back through this module a second time after a
_finish_consonant_then_vowel() fix can lose that distinction. See
sanskrit_phonology.py's module docstring for the exact repro.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from krama_engine import split_into_ardharcas, generate_verse  # noqa: E402
from sanskrit_phonology import reconstruct_chain  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SAMHITA_PATH = ROOT / "dge/data/vedas/rigveda/shakala_shakha/samhita/mandala_01/data.json"
OLD_OUTPUT_PATH = ROOT / "dge/data/vedanga/shiksha/pratishakhya/rigveda_pratishakhya/krama_generated_output.json"
OUT_PATH = ROOT / "dge/data/vedanga/shiksha/pratishakhya/rigveda_pratishakhya/krama_regenerated_output.json"

ACCENT_MARKS = "॒॑"


def strip_accents(s):
    return "".join(ch for ch in s if ch not in ACCENT_MARKS)


def _strip_pada_iti_gloss(token):
    """DGE's own pada_patha carries a real, common editorial convention this
    script did not need to handle for RV 1.1 (checked directly: RV 1.1 has
    zero instances) but that appears immediately in RV 1.2 onward (541+76+1
    times across Mandala 1, found while scanning beyond RV 1.1's own scope
    11-13 Sep 2026): a danda-delimited token can carry an "iti" GLOSS for
    the word immediately before it, disambiguating an otherwise-ambiguous
    Pada spelling -- e.g. "vaayo iti" (is "vaayo" complete, or truncated?)
    or, for a compound, giving BOTH the fused citation form and the true
    avagraha-split form: "vaajiiniivasuu iti vaajiiniiऽvasuu". This is a
    DIFFERENT phenomenon from a real, independent "iti" WORD (a quotative
    particle -- "thus [he/she said]") that stands as its OWN danda-
    delimited token elsewhere in this same corpus (confirmed: 12 such
    standalone tokens exist in Mandala 1) -- that one must NOT be touched
    here, and isn't (a standalone "iti" token has no other word in it to
    gloss).

    Rule, derived directly from all 3 shapes actually observed in Mandala 1
    (not guessed): within a token containing "iti" as one of several
    space-separated words, the word immediately before "iti" is the one
    being glossed; anything AFTER "iti" (if present) is its disambiguated
    real form and replaces it; anything else BEFORE the glossed word is a
    separate, unrelated real word in its own right (needed for exactly one
    observed case, "upaऽaasate uto iti", where "upaऽaasate" and "uto" are
    two distinct Pada words that happen to share one danda-token with no
    danda between them -- an isolated data quirk, not a new convention).

    Returns a list of 0+ real words (usually exactly 1)."""
    words = token.split()
    if words == ["इति"]:
        return ["इति"]  # a genuine standalone iti word, never a gloss target
    if "इति" not in words:
        return [token]
    idx = words.index("इति")
    before, after = words[:idx], words[idx + 1:]
    real_form = " ".join(after) if after else (before[-1] if before else "")
    leading_extra = before[:-1] if before else []
    return leading_extra + ([real_form] if real_form else [])


def split_pada_words(pada_patha_stripped):
    """pada_patha uses '।' between words within a pada and '॥' verse-final.
    Both are word separators here; strip whitespace per token, then strip
    any pada_patha-internal "iti" disambiguation gloss (see
    _strip_pada_iti_gloss) -- a no-op for RV 1.1, which has none."""
    text = pada_patha_stripped.replace("॥", "।")
    tokens = [w.strip() for w in text.split("।")]
    words = []
    for t in tokens:
        if t:
            words.extend(_strip_pada_iti_gloss(t))
    return words


def load_verses():
    data = json.loads(SAMHITA_PATH.read_text(encoding="utf-8"))
    by_id = {it["id"]: it for it in data["items"]}
    verse_ids = [f"1.1.{n}" for n in range(1, 10)]
    verses = []
    for vid in verse_ids:
        item = by_id[vid]
        pada_stripped = strip_accents(item["pada_patha"])
        samhita_stripped = strip_accents(item["samhita_patha"])
        pada_words = split_pada_words(pada_stripped)
        verses.append({"id": vid, "pada_words": pada_words, "samhita_patha_stripped": samhita_stripped})
    return verses


def regenerate_all():
    verses = load_verses()
    out_items = []
    for v in verses:
        ardharcas, split_method = split_into_ardharcas(v["id"], v["pada_words"], v["samhita_patha_stripped"])
        units_per_ardharca = generate_verse(ardharcas)
        out_items.append({
            "id": v["id"],
            "pada_words": v["pada_words"],
            "samhita_patha_stripped": v["samhita_patha_stripped"],
            "ardharca_split_method": split_method,
            "ardharcas": [
                {"pada_words": words, "units": units}
                for words, units in zip(ardharcas, units_per_ardharca)
            ],
        })
    return out_items


def attest_ardharcas(new_items):
    """VALIDATE-mode pass (architecture doc sec.7), layered on top of
    GENERATE: for each ardharca, fold sanskrit_phonology.samhita_join
    across ALL of its words (reconstruct_chain) to build the one
    continuous string this engine's phonology predicts, and compare it
    against DGE's own attested samhita_patha for that ardharca. This is a
    real, mechanically-checkable fact about the PHONOLOGY -- and explicitly
    NOT the same claim as "this Krama output is philologically correct"
    (matching DGE's own Samhita only shows internal self-consistency with
    this repo's other data; agreement with a traditional Krama-patha
    edition remains the open question in architecture doc sec.10).

    Deliberately NOT checked per-unit against the continuous text: an
    individual Krama retake pair is computed against only its own
    neighbour, but that same word's form in the continuous chain is often
    governed by a DIFFERENT (later) neighbour -- e.g. "purohitam" (the
    Krama pair, computed against "iiLe" before it) vs. "purohitaM" (the
    anusvara form the continuous text shows, because "yajJasya" follows
    it there). Comparing pairs one at a time against continuous text
    produced many false "mismatches" for exactly this reason before this
    function existed; the chain reconstruction below avoids that by
    building the SAME kind of chained text DGE's own data is, so the
    comparison is apples to apples.

    Mutates each ardharca dict in place, adding a "chain_reconstruction"
    field."""
    for item in new_items:
        parts = [p.strip() for p in item["samhita_patha_stripped"].replace("॥", "।").split("।") if p.strip()]
        for a_idx, ardharca in enumerate(item["ardharcas"]):
            computed, rules = reconstruct_chain(ardharca["pada_words"])
            expected = parts[a_idx] if a_idx < len(parts) else None
            matched = expected is not None and computed == expected
            ardharca["chain_reconstruction"] = {
                "computed": computed,
                "attested": expected,
                "status": "EXACT_MATCH" if matched else "DIFFERS",
                "rules_used": rules,
                "note": "" if matched else "The phonology engine's own chained reconstruction of this "
                                            "ardharca's continuous text does not match DGE's attested "
                                            "samhita_patha -- a real, checkable phonology discrepancy "
                                            "(see dge/RV_PRATISHAKHYA_KRAMA_ARCHITECTURE.md sec.6.6 for "
                                            "which specific ones are already understood and why).",
            }


def flatten_pair_and_parigraha_texts(item):
    """For comparison against the old hand-aligned output: returns the
    sequence of unit "text" strings in recitation order across all
    ardharcas of one verse."""
    texts = []
    for ardharca in item["ardharcas"]:
        for u in ardharca["units"]:
            texts.append(u["text"])
    return texts


def compare_against_old(new_items):
    """Keyed by (ardharca_index, unit_index_within_ardharca), not a single
    flattened per-verse index -- a fix for the 11 Sep 2026 review's point 9:
    with a flat global index, one inserted/removed unit in ardharca 2 makes
    every later unit look mismatched even when ardharca 1 is identical and
    only one real thing changed. Keying per-ardharca contains the blast
    radius of a genuine difference to the ardharca it actually occurred in."""
    if not OLD_OUTPUT_PATH.exists():
        return None
    old_data = json.loads(OLD_OUTPUT_PATH.read_text(encoding="utf-8"))
    old_by_id = {it["id"]: it for it in old_data["items"]}
    report = []
    for new_item in new_items:
        vid = new_item["id"]
        old_item = old_by_id.get(vid)
        if old_item is None:
            report.append({"id": vid, "status": "NO_OLD_VERSION"})
            continue
        ardharca_reports = []
        verse_all_match = True
        for a_idx, (old_ardharca, new_ardharca) in enumerate(zip(old_item["ardharcas"], new_item["ardharcas"])):
            old_texts = [u["text"] for u in old_ardharca["units"]]
            new_texts = [u["text"] for u in new_ardharca["units"]]
            old_types = [u.get("type") for u in old_ardharca["units"]]
            new_types = [u.get("type") for u in new_ardharca["units"]]
            max_len = max(len(old_texts), len(new_texts))
            diffs = []
            for i in range(max_len):
                ot = old_texts[i] if i < len(old_texts) else None
                nt = new_texts[i] if i < len(new_texts) else None
                if ot != nt:
                    diffs.append({
                        "unit_index_within_ardharca": i,
                        "old": ot, "new": nt,
                        "old_type": old_types[i] if i < len(old_types) else None,
                        "new_type": new_types[i] if i < len(new_types) else None,
                    })
            if diffs:
                verse_all_match = False
            ardharca_reports.append({
                "ardharca_index": a_idx,
                "status": "EXACT_MATCH" if not diffs else "DIFFERS",
                "diffs": diffs,
            })
        if len(old_item["ardharcas"]) != len(new_item["ardharcas"]):
            verse_all_match = False
        report.append({
            "id": vid,
            "status": "EXACT_MATCH" if verse_all_match else "DIFFERS",
            "ardharcas": ardharca_reports,
        })
    return report


def build_counts(new_items):
    """Every count here is cross-checked by an explicit invariant assertion
    before being returned, per the 11 Sep 2026 review's point 1: a count
    that merely LOOKS plausible is not the same as one proven consistent
    with the data it was computed from. If an assertion fails, this
    function raises rather than silently shipping a wrong number."""
    counts = {"pada_count": 0, "pair_count": 0, "parigraha_count": 0,
              "ardharca_count": 0, "special_exception_count": 0, "unresolved_count": 0,
              "candidate_reconstruction_count": 0, "chain_reconstruction_mismatch_count": 0}
    total_word_boundaries = 0
    tri_unit_count = 0
    for item in new_items:
        for ardharca in item["ardharcas"]:
            counts["ardharca_count"] += 1
            n_words = len(ardharca["pada_words"])
            counts["pada_count"] += n_words
            total_word_boundaries += max(n_words - 1, 0)
            if ardharca.get("chain_reconstruction", {}).get("status") == "DIFFERS":
                counts["chain_reconstruction_mismatch_count"] += 1
            for u in ardharca["units"]:
                if u["type"] == "pair":
                    counts["pair_count"] += 1
                elif u["type"] == "parigraha":
                    counts["parigraha_count"] += 1
                elif u["type"] in ("monosyllable_retake_tri_unit", "monosyllable_confirm_pair"):
                    counts["special_exception_count"] += 1
                    if u["type"] == "monosyllable_retake_tri_unit":
                        tri_unit_count += 1
                if u.get("confidence") == "low":
                    counts["unresolved_count"] += 1
                if u.get("status") == "candidate_reconstruction":
                    counts["candidate_reconstruction_count"] += 1

    # INVARIANT: every word-boundary (n-1 per ardharca) is filled by exactly
    # one of {an ordinary "pair" unit, a "monosyllable_retake_tri_unit"} --
    # the tri-unit REPLACES the ordinary pair at that boundary (sutra 10.3),
    # it does not sit alongside it. The tri-unit's own confirming
    # "monosyllable_confirm_pair" is a deliberate EXTRA unit beyond the
    # boundary count (Uvata's own example: 2 boundaries -> 3 output units),
    # so it is intentionally excluded from this sum, not an oversight.
    assert counts["pair_count"] + tri_unit_count == total_word_boundaries, (
        f"invariant violated: pair_count ({counts['pair_count']}) + "
        f"monosyllable_retake_tri_unit count ({tri_unit_count}) != "
        f"total word-boundaries ({total_word_boundaries})"
    )
    counts["invariant_check"] = {
        "formula": "pair_count + monosyllable_retake_tri_unit_count == sum(len(ardharca.pada_words) - 1)",
        "pair_count": counts["pair_count"],
        "monosyllable_retake_tri_unit_count": tri_unit_count,
        "total_word_boundaries": total_word_boundaries,
        "holds": True,
    }
    return counts


def main():
    new_items = regenerate_all()
    attest_ardharcas(new_items)
    comparison = compare_against_old(new_items)
    counts = build_counts(new_items)

    out = {
        "schema": "generic",
        "note": "Krama-patha for RV 1.1 (all 9 verses) computed by "
                "tools/pratishakhya/krama_engine.py (real sandhi engine + predicate "
                "classifiers) directly from DGE's Pada-patha/Samhita-patha, per the "
                "reviewed spec's success criterion. No per-verse pair or Parigraha "
                "strings are hardcoded anywhere in this pipeline; the only per-verse "
                "manual input is the two ardharca-split overrides in krama_engine.py's "
                "ARDHARCA_SPLIT_OVERRIDES, logged there with the reason each was needed. "
                "Every unit carries independent status/confidence fields, and every "
                "ardharca carries a chain_reconstruction field -- see krama_engine.py's "
                "and regenerate_krama_rv_1_1.py's module docstrings for what each one "
                "does and does NOT establish. Reproducing DGE's own attested "
                "samhita_patha (chain_reconstruction) is a real, checkable fact but is "
                "NOT the same claim as philological correctness against a traditional "
                "Krama-patha edition, which remains open (architecture doc sec.10).",
        "engine_source": "tools/pratishakhya/krama_engine.py",
        "pada_samhita_source": "dge/data/vedas/rigveda/shakala_shakha/samhita/mandala_01/data.json",
        "counts": counts,
        "comparison_against_hand_aligned_output": comparison,
        "items": new_items,
    }
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_PATH}")
    print("\n=== Counts ===")
    for k, v in counts.items():
        print(f"  {k}: {v}")
    print("\n=== Comparison against hand-aligned krama_generated_output.json (per-ardharca) ===")
    if comparison is None:
        print("  (old output file not found)")
    else:
        for r in comparison:
            print(f"  {r['id']}: {r['status']}")
            for ar in r.get("ardharcas", []):
                if ar["status"] != "EXACT_MATCH":
                    print(f"    ardharca {ar['ardharca_index']}: DIFFERS")
                    for d in ar["diffs"]:
                        print(f"      unit {d['unit_index_within_ardharca']}: OLD={d['old']!r}  NEW={d['new']!r}")
    print("\n=== Chain reconstruction vs DGE's attested samhita_patha (per-ardharca) ===")
    for item in new_items:
        for a_idx, ardharca in enumerate(item["ardharcas"]):
            cr = ardharca["chain_reconstruction"]
            if cr["status"] != "EXACT_MATCH":
                print(f"  {item['id']} ardharca {a_idx}: DIFFERS")
                print(f"    computed: {cr['computed']!r}")
                print(f"    attested: {cr['attested']!r}")


if __name__ == "__main__":
    main()
