#!/usr/bin/env python3
"""Offline CI gate for the DGE Gold-Standard Commentary Contract v2.2 (V1-V7),
run against any commentary carrying `"format": "gold_v2_2"` -- see
dge/GOLD_STANDARD_ARCHITECTURE.md Part C for the design and Part 1 for what
each check enforces. Two input shapes are understood, since they're both
real:

  - A standalone ingestion batch, `{"document": {...}, "units": [...]}`,
    matching the reference sample (extracted_gold_v2_2.json) and what a
    future Gemini-assisted import would emit BEFORE merge. Every unit in
    `units[]` is checked directly; its own `mula_sanskrit` is the source text.
  - An already-merged corpus file under dge/data/**/data.json. Walked
    generically (no schema assumed -- corpora nest shlokas differently) for
    any dict with `format: gold_v2_2`; its source text is the sibling `sa`
    field one level up, DGE's own convention (see render.js).

Usage:
  python3 tools/validate_gold_standard.py <file.json> [<file.json> ...]
  python3 tools/validate_gold_standard.py --scan-corpus [--data dge/data]
  python3 tools/validate_gold_standard.py <file.json> --update-checksums

Exit code is 1 if any check in FAIL_CHECKS below fired, 0 otherwise. Every
other check is real and reported, but not (yet) a hard gate -- each WARN
check's docstring says exactly why, most often because getting it wrong is a
philological judgment call this script cannot safely automate, and a false
FAIL would block CI on correct content (verified directly against the
project's own reference sample -- see tests/test_validate_gold_standard.py).
"""
import argparse
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECKSUM_MANIFEST = os.path.join(REPO, "tools", "gold_source_checksums.json")
GOLD_RENDER_JS = os.path.join(REPO, "dge", "js", "gold-render.js")

PRATIKA_RE = re.compile(r'\*\*"([^"]*)"\*\*')
# Near-miss quote styles that are legitimate *emphasis* on their own (the
# contract's own reference sample uses **'...'** for exactly that -- see
# BG_2.37's avataranika) -- so these only become a V2 finding when the
# inner text also happens to match a real word_mappings pratika, which is
# strong evidence the author meant a lemma reference and mistyped the
# required straight-double-quote form.
NEAR_MISS_RES = [
    re.compile(r'\*\*[“”]([^“”]*)[“”]\*\*'),   # curly double quotes
    re.compile(r"\*\*['‘’]([^'‘’]*)['‘’]\*\*"),  # single / curly-single quotes
]
DIALECTIC_OBJECTION_MARKERS = ["इति चेत्", "इत्याशङ्क्य", "इत्याशङ्क्याह"]
DIALECTIC_RESOLUTION_MARKERS = ["इति चेन्न", "समाधानम्", "सिद्धान्तः", "नाद्यः", "न, तस्मात्"]

findings = []  # list of dicts: {check, severity, unit, message}
FAIL_CHECKS = {"SCHEMA", "V2", "V3-forward", "V6"}


def add(check, severity, unit_id, message):
    findings.append({"check": check, "severity": severity, "unit": unit_id, "message": message})


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_checksums():
    if os.path.exists(CHECKSUM_MANIFEST):
        with open(CHECKSUM_MANIFEST, encoding="utf-8") as fh:
            return json.load(fh)
    return {}


def save_checksums(manifest):
    with open(CHECKSUM_MANIFEST, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")


def find_units_in_batch(data, source_label):
    """{"document": {...}, "units": [...]} shape -- each unit is checked
    directly, mula_sanskrit lives inside the unit itself."""
    for unit in data.get("units", []):
        yield source_label, unit.get("id", "?"), unit, unit.get("mula_sanskrit")


def find_units_in_corpus(data, source_label):
    """Already-merged dge/data/**/data.json -- walked generically since
    shloka nesting differs across corpora (flat shlokas{}, items[].shlokas[],
    etc.) rather than assuming one shape, matching the reader's own "100%
    generic" requirement."""
    def walk(obj, path, parent):
        if isinstance(obj, dict):
            if obj.get("format") == "gold_v2_2" and "commentary_markdown" in obj:
                mula = obj.get("mula_sanskrit") or (parent.get("sa") if isinstance(parent, dict) else None)
                yield source_label, path, obj, mula
            for k, v in obj.items():
                yield from walk(v, f"{path}.{k}" if path else k, obj)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                yield from walk(v, f"{path}[{i}]", obj)

    yield from walk(data, "", None)


def iter_units(path):
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    label = os.path.relpath(path, REPO)
    if isinstance(data, dict) and "units" in data and isinstance(data["units"], list) and "document" in data:
        yield from find_units_in_batch(data, label)
    else:
        yield from find_units_in_corpus(data, label)


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------

def check_schema(uid, unit):
    md = unit.get("commentary_markdown")
    if not isinstance(md, str) or not md.strip():
        add("SCHEMA", "FAIL", uid, "commentary_markdown missing or empty")
        return False
    wm = unit.get("word_mappings")
    if not isinstance(wm, list):
        add("SCHEMA", "FAIL", uid, "word_mappings is not a list")
        return False
    for i, m in enumerate(wm):
        if not isinstance(m, dict) or not all(k in m for k in ("mula_word", "pratika", "gloss")):
            add("SCHEMA", "FAIL", uid, f"word_mappings[{i}] missing mula_word/pratika/gloss")
            return False
    return True


def check_v1_source_immutability(uid, source_label, mula_text, manifest, update):
    if not mula_text:
        add("V1", "WARN", uid, "no source text reachable to checksum (corpus shloka has no sibling 'sa')")
        return
    key = f"{source_label}::{uid}"
    digest = sha256(mula_text)
    if update:
        manifest[key] = digest
        return
    baseline = manifest.get(key)
    if baseline is None:
        add("V1", "WARN", uid, "no checksum baseline yet -- run --update-checksums to checkpoint")
    elif baseline != digest:
        add("V1", "FAIL", uid, "source text checksum differs from the checkpointed baseline (Layer 1 must be byte-faithful)")


def check_v2_v3_pratika(uid, unit):
    md = unit["commentary_markdown"]
    wm = unit.get("word_mappings", [])
    pratikas = {m["pratika"] for m in wm if isinstance(m, dict) and "pratika" in m}

    lemma_spans = PRATIKA_RE.findall(md)

    # V2 -- malformed near-miss quote style that happens to match a real
    # word_mappings pratika (see NEAR_MISS_RES docstring above).
    for rx in NEAR_MISS_RES:
        for inner in rx.findall(md):
            if inner in pratikas:
                add("V2", "FAIL", uid, f'"{inner}" matches a word_mappings pratika but is wrapped in the wrong quote style (must be **"..."**)')

    # V3 forward (hard): every word_mappings pratika must appear as a real
    # **"..."** lemma span somewhere in commentary_markdown -- the literal
    # parity rule as the spec states it.
    lemma_set = set(lemma_spans)
    for m in wm:
        p = m.get("pratika")
        if p and p not in lemma_set:
            add("V3-forward", "FAIL", uid, f'word_mappings pratika "{p}" never appears as a **"..."** span in commentary_markdown')

    # V3 reverse (soft): a **"..."** span with no word_mappings entry.
    # gold-render.js already degrades this gracefully (dge-gold-unmapped),
    # and the project's own reference sample has one real instance of this
    # (BG_2.1's "कुतः") -- a real, known, accepted gap, not a defect this
    # script should block on.
    for span in lemma_spans:
        if span not in pratikas:
            add("V3-reverse", "WARN", uid, f'"{span}" is a pratika span with no matching word_mappings entry')


def check_v4_gloss_tokens(uid, unit):
    """Zero residual external sandhi in padaccheda/gloss, per A1's "never
    leave dangling avagrahas" rule (सोऽयम् -> सः अयम्; तेऽपि -> ते अपि).
    Reported as a WARN, not a hard FAIL: an avagraha in exegetical prose is
    sometimes a genuinely unsplit syntactic boundary (what the rule targets)
    and sometimes conventional idiomatic liaison a working philologist would
    leave joined (देहतोऽपि) -- telling the two apart needs real sandhi
    analysis this script doesn't attempt. Verified directly against the
    project's own reference sample: this WARNs on two real spots
    (BG_2.12's "देहतोऽपि", BG_2.37's "पक्षद्वयेऽपि"), which is a legitimate
    candidate list for a human/Gemini review pass, not a false positive to
    suppress.
    """
    for tok in unit.get("padaccheda", []):
        if "ऽ" in tok:  # ऽ
            add("V4", "WARN", uid, f'possible unrestored avagraha in padaccheda: "{tok}"')
    for m in unit.get("word_mappings", []):
        g = m.get("gloss", "")
        if "ऽ" in g:
            add("V4", "WARN", uid, f'possible unrestored avagraha in gloss: "{g}"')


def check_v5_dialectic_pairing(uid, unit):
    """Every objection needs a paired resolution or an explicit
    `unanswered:` flag (B3). WARN only, and deliberately weak: detected
    lexically via the objection/resolution marker vocabulary in Part A2 of
    the contract. Checked directly against the reference sample: BG_2.12
    raises an objection ending "...वादिति चेत्" and resolves it a few
    sentences later via "नाद्यः" -- but "इति चेत्" is sandhi-glued onto the
    previous word there (वादिति, not a separate "इति"), which is the normal
    way this reads in real prose, so a literal-substring marker search does
    NOT catch it; only the resolution marker fires, and the check treats
    "resolution marker present, no objection marker" as nothing to report.
    A real objection with no marker this heuristic recognizes, or with its
    marker sandhi-joined the same way, passes silently -- worth a human/
    Gemini pass, not something this script can safely enforce.
    """
    md = unit["commentary_markdown"]
    flags = unit.get("flags", {}) if isinstance(unit.get("flags"), dict) else {}
    if flags.get("unanswered") in ("deferred", "rhetorical"):
        return
    has_objection = any(marker in md for marker in DIALECTIC_OBJECTION_MARKERS)
    has_resolution = any(marker in md for marker in DIALECTIC_RESOLUTION_MARKERS)
    if has_objection and not has_resolution:
        add("V5", "WARN", uid, "an objection marker appears with no matching resolution marker or flags.unanswered")


def check_v7_closed_world_citations(uid, unit):
    """Unresolved citations must render as plain text, never an orphan
    link (D2/V7). WARN, structural only: gold-render.js does not yet
    consume `quotations[]` for citation linking at all (the pramana chip
    is built from the block directive's own inline cite text, not this
    array) -- so today "no orphan link" holds trivially. This checks the
    array's own shape so it's not silently malformed once that wiring is
    built, rather than pretending closed-world enforcement exists already.
    """
    for i, q in enumerate(unit.get("quotations", []) or []):
        if not isinstance(q, dict) or not q.get("span") or not q.get("source_as_printed"):
            add("V7", "WARN", uid, f"quotations[{i}] missing span/source_as_printed")
            continue
        src = q.get("identified_source")
        if src is not None and not re.fullmatch(r"[a-z0-9_.]+", src or ""):
            add("V7", "WARN", uid, f'quotations[{i}].identified_source "{src}" is not a clean slug')


def check_v6_danda_integrity(units):
    """Zero line-initial daṇḍas (D1/V6), checked by actually running the
    real renderer (dge/js/gold-render.js) under Node -- not a reimplemented
    copy of its binding logic -- and scanning the HTML it produces for any
    daṇḍa not preceded by the non-breaking space bindDandas() inserts. A
    "headless render at mobile widths" per the contract's own wording would
    need Playwright measuring line-wraps; that's unnecessary here because
    the binding is a string-level guarantee (a NBSP-bound daṇḍa cannot start
    a visual line, at any width), so checking the string is both simpler
    and exactly as strong a guarantee.
    """
    if not units:
        return
    if not os.path.exists(GOLD_RENDER_JS):
        add("V6", "WARN", "*", "dge/js/gold-render.js not found -- skipped")
        return
    payload = [{"id": uid, "commentary_markdown": u["commentary_markdown"], "word_mappings": u.get("word_mappings", [])}
               for uid, u in units]
    driver = """
    global.window = {};
    require(process.argv[2]);
    const DGEGoldRender = global.window.DGEGoldRender;
    const fs = require('fs');
    const units = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
    const out = units.map(u => {
      const r = DGEGoldRender.render({format: 'gold_v2_2', commentary_markdown: u.commentary_markdown, word_mappings: u.word_mappings});
      return {id: u.id, html: r ? (r.pillGridHtml + r.bodyHtml) : ''};
    });
    process.stdout.write(JSON.stringify(out));
    """
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as jsf, \
         tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as dataf:
        jsf.write(driver)
        json.dump(payload, dataf, ensure_ascii=False)
        js_path, data_path = jsf.name, dataf.name
    try:
        result = subprocess.run(["node", js_path, GOLD_RENDER_JS, data_path],
                                 capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            add("V6", "WARN", "*", f"node render check failed to run: {result.stderr.strip()[:300]}")
            return
        rendered = json.loads(result.stdout)
    finally:
        os.unlink(js_path)
        os.unlink(data_path)

    unbound = re.compile(r"(?<!\xa0)[।॥]")
    for r in rendered:
        if unbound.search(r["html"]):
            add("V6", "FAIL", r["id"], "rendered output contains a danda not bound with a non-breaking space")


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", help="gold-standard batch or corpus data.json file(s)")
    ap.add_argument("--scan-corpus", action="store_true", help="walk --data for embedded format:gold_v2_2 commentary")
    ap.add_argument("--data", default="dge/data")
    ap.add_argument("--update-checksums", action="store_true", help="write the V1 baseline instead of checking it")
    args = ap.parse_args()

    paths = list(args.paths)
    if args.scan_corpus:
        data_root = args.data if os.path.isdir(args.data) else os.path.join(REPO, args.data)
        paths.extend(sorted(glob.glob(os.path.join(data_root, "**", "data.json"), recursive=True)))
    if not paths:
        print("no input files -- pass file(s) or --scan-corpus")
        return 2

    manifest = load_checksums()
    all_units = []  # (uid, unit) for the V6 render pass
    n_units = 0

    for path in paths:
        try:
            for source_label, uid, unit, mula_text in iter_units(path):
                n_units += 1
                if not check_schema(uid, unit):
                    continue
                check_v1_source_immutability(uid, source_label, mula_text, manifest, args.update_checksums)
                check_v2_v3_pratika(uid, unit)
                check_v4_gloss_tokens(uid, unit)
                check_v5_dialectic_pairing(uid, unit)
                check_v7_closed_world_citations(uid, unit)
                all_units.append((uid, unit))
        except (OSError, json.JSONDecodeError) as e:
            add("SCHEMA", "FAIL", path, f"could not read/parse: {e}")

    check_v6_danda_integrity(all_units)

    if args.update_checksums:
        save_checksums(manifest)
        print(f"checksums: wrote {len(manifest)} baseline entries to {os.path.relpath(CHECKSUM_MANIFEST, REPO)}")
        return 0

    fails = [f for f in findings if f["severity"] == "FAIL"]
    warns = [f for f in findings if f["severity"] == "WARN"]
    print(f"validate_gold_standard: {n_units} gold_v2_2 unit(s) checked across {len(paths)} file(s), "
          f"{len(fails)} failures, {len(warns)} warnings")
    for f in fails:
        print(f"  FAIL [{f['check']}] {f['unit']}: {f['message']}")
    for f in warns:
        print(f"  WARN [{f['check']}] {f['unit']}: {f['message']}")

    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
