#!/usr/bin/env python3
"""Registry-driven GRETIL importer for the Purāṇa and Vedāṅga gaps.

Separate from importers/gretil.py (verse corpora, one marker convention) and
importers/darshana_gretil.py (śāstra prose, heading-segmented) because these
texts share neither property: 34 texts across 13 mutually incompatible marker
grammars — prefix vs suffix, '.' vs ',' separators, and //, ||, (), <> or bare
delimiters. The grammar is therefore data, not code: importers/gretil_bulk.json
names a pattern per text and this module applies it.

Run:  python importers/gretil_bulk.py --list
      python importers/gretil_bulk.py --id vishnu_purana --dry-run
      python importers/dispatch.py gretil:vishnu_purana
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import http_get, to_text, iast_to_dev, data_base  # noqa: E402

BASE = "https://gretil.sub.uni-goettingen.de/gretil/"
HERE = os.path.dirname(os.path.abspath(__file__))
REGISTRY = os.path.join(HERE, "gretil_bulk.json")

# Editorial apparatus that must never reach the text. Each was observed in a
# real file: chapter callouts and line-class prefixes in the Agni-Purāṇa, the
# ritual-context tag in the Āśvalāyana-Śrautasūtra, GRETIL's own analytic
# markers, and print-page rules glued onto a verse line.
NOISE = [
    (re.compile(r"%\s*chapter\s*\{\d+\}"), " "),      # AP chapter callout
    (re.compile(r"^:\S+\s*", re.M), ""),               # AP line-class prefix
    (re.compile(r"\((?:darśa|paurṇamāsa|soma)[^)]*\)"), " "),  # AsvSS ritual tag
    (re.compile(r"[\\^~]"), ""),                       # GRETIL analytic markers
    (re.compile(r"_{3,}"), " "),                       # print-page rule
    (re.compile(r"\[[^\]]*\[[^\]]*\]"), " "),          # ApDS grammatical gloss
]
HEADER_END = re.compile(r"^\s*(?:TEXT\s*$|##\s*Revisions?:|\*{3,}\s*$|-{5,}\s*$)", re.M)
# "# Text" (a markdown-style heading, not the bare "TEXT" HEADER_END already
# looks for) is the real, consistent body-start marker across this whole
# corpus -- confirmed directly against several files, including ones whose
# header carries a "## Revisions:" bullet-point changelog BEFORE "# Text".
# HEADER_END.search() finds whichever alternative occurs earliest in the
# file, so on those files it was matching "## Revisions:" and treating the
# changelog line right after it as the start of the body -- real leaked
# header text ("2020-07-31: TEI encoding by mass conversion...") ended up
# inside the first extracted unit on every SUFFIX-style marker (a PREFIX
# marker's first unit starts after its own first match regardless, so this
# never surfaced there). Checked for last, not folded into HEADER_END's own
# alternation, because search() returns the leftmost match among
# alternatives at a given position, not the "best" one -- an explicit
# preference pass is the only way to make "# Text" win over an earlier,
# weaker signal.
TEXT_MARKER = re.compile(r"^#+\s*Text\s*$", re.M)
ATTRIB = re.compile(
    r"^(?:##\s*)?(?:Data entry|Contribution|Input by|Source|Publisher|Licence|License|"
    r"Based on|Contributed by|Date of this version|Description)\s*:?.*$", re.I | re.M)


def load_registry(path=REGISTRY):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def split_header(raw):
    match = None
    for match in TEXT_MARKER.finditer(raw):
        pass  # take the LAST "# Text" heading, in case an earlier one is quoted inside the header itself
    if match is None:
        match = HEADER_END.search(raw)
    head, body = (raw[:match.start()], raw[match.end():]) if match else (raw[:3000], raw)
    if not body.strip():
        head, body = "", raw
    attribution = " | ".join(
        re.sub(r"\s+", " ", line).strip() for line in ATTRIB.findall(head)
    )
    return attribution[:1500], body


def clean(text):
    for pattern, replacement in NOISE:
        text = pattern.sub(replacement, text)
    # Sansknet files mark word boundaries with dots rather than spaces; keep the
    # dots (they are meaningful for compounds) but never let them run together
    # with the surrounding whitespace into unreadable blocks.
    text = re.sub(r"\s+", " ", text)
    return text.strip(" /|<>-")


def parse(raw, spec, patterns):
    """Split a GRETIL file into (ref_tuple, text) units using this text's marker."""
    attribution, body = split_header(raw)
    if "<" in body[:2000] and "htm" in spec.get("_ext", "htm"):
        body = to_text(body)

    pattern = patterns[spec["marker"]]
    regex = re.compile(pattern["regex"], re.M | re.UNICODE | re.IGNORECASE)
    matches = list(regex.finditer(body))
    if not matches:
        return [], attribution, 0

    # An explicit "style" on the pattern wins over the string-prefix guess
    # below -- needed for a marker that has to match ANYWHERE in the body
    # (not just at a true line start) yet is still a prefix, e.g. a
    # multi-level "1.1.1 text..." reference repeated many times within one
    # giant physical line rather than once per real line break.
    if "style" in pattern:
        prefix_style = pattern["style"] == "prefix"
    else:
        prefix_style = pattern["regex"].lstrip("^").startswith(("\\(", "<", "(?P<sig>")) or \
            pattern["regex"].startswith("^")
    units, seen_span = [], 0
    for index, match in enumerate(matches):
        groups = match.groupdict()
        refs = tuple(v for k, v in sorted(groups.items())
                     if k.startswith("ref") and v is not None)
        if prefix_style:
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        else:
            start = seen_span
            end = match.start()
            seen_span = match.end()
        text = clean(body[start:end])
        # Some markers repeat before every sentence within one giant physical
        # line rather than once per actual line break -- confirmed directly
        # against nirukta's own source: only 18 real "^"-anchored matches in
        # the whole file (one per adhyaya, since each adhyaya is a single
        # unbroken line), yet the SAME ref recurs dozens of times inline
        # within that line. re.MULTILINE's "^" only ever matches the first
        # such occurrence per physical line, so every later inline repeat
        # passes straight through into the extracted text instead of being
        # consumed as a boundary. spec["strip_inline"] is the escape hatch
        # for exactly that: an optional regex removed from the text AFTER
        # extraction, opt-in per text so it changes nothing for the other
        # 33 registry entries.
        if spec.get("strip_inline"):
            text = re.sub(spec["strip_inline"], " ", text)
            text = re.sub(r"\s+", " ", text).strip()
        if len(text) < 3:
            continue
        units.append((refs, groups.get("pada"), text))
    return units, attribution, len(matches)


def _ident(key):
    ident = re.sub(r"[^0-9A-Za-z]+", "_", key)
    return f"{int(ident):02d}" if ident.isdigit() else ident


def group_items(units, spec):
    """Fold units into DGE items — one item per division.

    Normally that's the first-level division (spec["unit"]). A marker whose
    refs carry a real second conceptual level below that (not just a bare
    verse number) opts in via spec["subunit"] to bucket on (level 1, level
    2) instead, so e.g. an adhikaraṇa.adhyāya marker yields one item per
    adhyāya rather than folding every adhyāya of an adhikaraṇa into a
    single blob. Untouched for every text without "subunit" set.
    """
    unit_name = spec.get("unit", "section")
    sub_name = spec.get("subunit")
    schema = spec["schema"]
    buckets = {}
    order = []
    for refs, pada, text in units:
        if not refs:
            continue
        if sub_name and len(refs) >= 2:
            key = (str(refs[0]), str(refs[1]))
        else:
            top = refs[0] if len(refs) > 1 else "1"
            key = str(top)
        verse = refs[-1]
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        number = f"{verse}{pada}" if pada else verse
        buckets[key].append({"number": number, "sanskrit_text": iast_to_dev(text),
                             "iast_text": text})

    items = []
    for key in order:
        if sub_name and isinstance(key, tuple):
            top_key, sub_key = key
            item_id = f"{unit_name}_{_ident(top_key)}_{sub_name}_{_ident(sub_key)}"
            reference = f"{spec['name']}, {unit_name} {top_key}, {sub_name} {sub_key}"
        else:
            item_id = f"{unit_name}_{_ident(key)}"
            reference = f"{spec['name']}, {unit_name} {key}"
        if schema in ("itihasa_purana_text", "smriti_dharmashastra_text"):
            items.append({"id": item_id, "reference": reference, "shlokas": buckets[key]})
        else:
            joined = "\n".join(v["iast_text"] for v in buckets[key])
            items.append({"id": item_id, "reference": reference,
                          "sanskrit_text": iast_to_dev(joined), "iast_text": joined,
                          "artha": "", "notes": "", "tags": [], "references": [],
                          "audio": []})
    return items


LIVRE_RE = re.compile(r"livre\s+(\d+)", re.I)
LECON_RE = re.compile(r"leçon\s+(\d+)", re.I)
# The editor's own chapter-heading furniture (French "leçon"/"livre", English
# "section") -- never genuine Sanskrit vocabulary in this corpus, so safe to
# strip outright rather than let iast_to_dev() mangle it into gibberish
# Devanagari. Matches e.g. "leçon 3", "livre 2", "section (prakaraṇa) 12a".
LECON_FURNITURE_RE = re.compile(
    r"\b(?:leçon|livre)\s+\d+\b|\bsection\s*\(prakaraṇa\)\s*\d+[a-z-]*", re.I)


def parse_livre_lecon(raw, spec):
    """Bespoke parser for Kāmasūtra's 'livre N ... leçon M' chapter markers.

    The file's own adhikaraṇa.adhyāya.sūtra numbers (spec's nominal
    "bare_prefix_three_level" marker) recur ~1609 times in the body --
    confirmed by inspection, not assumed -- because they're also used as
    inline cross-reference citations within running prose (e.g. a passage
    in adhikaraṇa 2 citing "6.1.3"), not only at true sūtra starts. Bucketing
    on that marker at adhyāya granularity (not just adhikaraṇa, which
    happens to absorb the noise silently since citations only ever point at
    valid 1-7 adhikaraṇa numbers) creates spurious chapters like
    "adhikarana 1, adhyaya 20" -- adhikaraṇa 1 only has 5 adhyāyas.

    "livre N" (7 occurrences, one per adhikaraṇa) and "leçon M" (36
    occurrences total, matching the well-known 5+10+5+2+6+6+2 adhyāya
    count per adhikaraṇa) are the French editor's own deliberate chapter
    headers, each appearing exactly once at a true chapter start -- verified
    against the source file directly, not assumed. "livre N" and its
    adhikaraṇa's first "leçon 1" always share one line; every other "leçon"
    within that adhikaraṇa carries no "livre" of its own, so the current
    adhikaraṇa number is carried forward from the last "livre" seen.
    """
    attribution, body = split_header(raw)
    marks = sorted(
        [(m.start(), "livre", m.group(1)) for m in LIVRE_RE.finditer(body)] +
        [(m.start(), "lecon", m.group(1)) for m in LECON_RE.finditer(body)]
    )
    chapters = []  # (adhikarana, adhyaya, text_start_offset)
    adhikarana = None
    for pos, kind, num in marks:
        if kind == "livre":
            adhikarana = num
        else:
            if adhikarana is None:
                continue
            chapters.append((adhikarana, num, pos))
    units = []
    for index, (adhikarana, adhyaya, pos) in enumerate(chapters):
        start = LECON_RE.match(body, pos).end()
        end = chapters[index + 1][2] if index + 1 < len(chapters) else len(body)
        text = clean(LECON_FURNITURE_RE.sub(" ", body[start:end]))
        if len(text) < 3:
            continue
        units.append(((adhikarana, adhyaya), None, text))
    return units, attribution, len(marks)


def urls_for(spec, registry):
    out = []
    if spec.get("tei"):
        out.append((BASE + registry["tei_plaintext"] + spec["tei"] + ".txt", "txt"))
    for legacy in spec.get("legacy", []) + spec.get("legacy_extra", []):
        out.append((BASE + legacy, "htm"))
    return out


def write(spec, items, attribution, source_urls, dry_run):
    payload = {
        "schema": spec["schema"],
        "default_author": spec.get("author", ""),
        "source_url": source_urls[0] if source_urls else "",
        "source_note": build_note(spec, attribution),
        "items": items,
    }
    folder = os.path.join(data_base(), spec["target"])
    verses = sum(len(i.get("shlokas", [])) for i in items) or len(items)
    print(f"  {spec['id']:<32} {len(items):>4} items / {verses:>6} units -> {spec['target']}"
          + ("   [dry run]" if dry_run else ""))
    if dry_run:
        return payload
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "data.json"), "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=1)
        handle.write("\n")
    return payload


def build_note(spec, attribution):
    parts = ["GRETIL."]
    if spec.get("licence") == "cc-by-nc-sa-4.0":
        parts.append("Distributed under CC BY-NC-SA 4.0 by GRETIL.")
    else:
        parts.append("THIS GRETIL TEXT FILE IS FOR REFERENCE PURPOSES ONLY! "
                     "COPYRIGHT AND TERMS OF USAGE AS FOR SOURCE FILE.")
    for key in ("source_edition", "extra_copyright", "scope", "quality", "note"):
        if spec.get(key):
            parts.append(f"{key}: {spec[key]}")
    if attribution:
        parts.append(attribution)
    return " ".join(parts)[:2000]


def run(text_id, dry_run=False, registry=None):
    registry = registry or load_registry()
    specs = {t["id"]: t for t in registry["texts"]}
    if text_id not in specs:
        raise SystemExit(f"unknown gretil_bulk id: {text_id}")
    spec = specs[text_id]

    chunks = []
    used = []
    for url, ext in urls_for(spec, registry):
        try:
            chunks.append((http_get(url), ext))
            used.append(url)
        except Exception as exc:                      # noqa: BLE001
            print(f"  ! {url}: {exc}", file=sys.stderr)
    if not chunks:
        raise SystemExit(f"{text_id}: nothing fetched")

    all_units, attribution, matched = [], "", 0
    for raw, ext in chunks:
        spec["_ext"] = ext
        if spec["marker"] == "livre_lecon":
            units, attr, count = parse_livre_lecon(raw, spec)
        else:
            units, attr, count = parse(raw, spec, registry["marker_patterns"])
        all_units += units
        matched += count
        attribution = attribution or attr

    if not all_units:
        raise SystemExit(f"{text_id}: marker '{spec['marker']}' matched nothing — "
                         "the file's format has changed; re-check gretil_bulk.json")
    items = group_items(all_units, spec)
    write(spec, items, attribution, used, dry_run)
    return items


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--id", default="")
    parser.add_argument("--all", action="store_true", help="every CC-licensed text")
    parser.add_argument("--group", default="", help="only ids whose target starts with this")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args(argv)

    registry = load_registry()
    texts = registry["texts"]

    if args.list:
        for spec in texts:
            flag = "" if spec.get("licence") == "cc-by-nc-sa-4.0" else "  [reference-only]"
            scope = "" if spec.get("complete") else f"  (partial: {spec.get('scope','')[:60]})"
            print(f"{spec['id']:<32} {spec['target']}{flag}{scope}")
        missing = registry["not_in_gretil"]
        print(f"\nnot in GRETIL: " +
              ", ".join(f"{k} ({len(v)})" for k, v in missing.items() if k != '_note'))
        return 0

    selected = [t for t in texts if
                (args.id and t["id"] == args.id) or
                (args.group and t["target"].startswith(args.group)) or
                (args.all and t.get("licence") == "cc-by-nc-sa-4.0")]
    if not selected:
        print("nothing selected; use --id, --group or --all", file=sys.stderr)
        return 2

    failures = 0
    for spec in selected:
        try:
            run(spec["id"], dry_run=args.dry_run, registry=registry)
        except SystemExit as exc:
            print(f"  FAILED {spec['id']}: {exc}", file=sys.stderr)
            failures += 1
    print(f"\n{len(selected) - failures}/{len(selected)} succeeded")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
