#!/usr/bin/env python3
"""Registry-driven GRETIL importer for the Purāṇa and Vedāṅga gaps.

Separate from importers/gretil.py (verse corpora, one marker convention) and
importers/darshana_gretil.py (śāstra prose, heading-segmented) because these
texts share neither property: 34+ texts across mutually incompatible marker
grammars — prefix vs suffix, '.' vs ',' separators, and //, ||, (), <> or bare
delimiters. The grammar is therefore data, not code: importers/gretil_bulk.json
names a pattern per text and this module applies it.

Multi-book texts are routed to one folder per book (the catalog's
one-entry-per-part convention, same as Bhāgavata's skandha_NN) via the
registry's split_targets / sig_targets / derived fields — see route_units().

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
    (re.compile(r"\(\d{1,3}\)"), " "),                 # inline footnote refs (1),(2)
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
LEGACY_END = re.compile(r"gretil\.sub\.uni-goettingen\.de/gretil\.htm\S*[ \t]*$", re.M)
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
        # Legacy 1_sanskr pages have no "# Text" heading at all; their long
        # English preamble (edition, SANSKNET notice, the whole diacritics
        # table) reliably ends with GRETIL's own boilerplate pointer to
        # gretil.htm. Without this cut the preamble lands in the first verse
        # and gets transliterated into Devanagari gibberish — seen for real
        # on lip_2__u.htm and vampsm_u.htm.
        for match in LEGACY_END.finditer(raw):
            pass
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
    """Split a GRETIL file into (ref_tuple, pada, text, sig) units using this
    text's marker."""
    # Legacy 1_sanskr pages must lose their markup BEFORE the header split:
    # split_header can cut between <style> and </style>, after which to_text's
    # element-content regex no longer sees a complete element and the raw CSS
    # text leaks into the first extracted unit (seen for real on both
    # lip_2__u.htm and vampsm_u.htm).
    if "htm" in spec.get("_ext", "") and "<" in raw[:2000]:
        raw = to_text(raw)
    attribution, body = split_header(raw)
    if "<" in body[:2000] and "htm" in spec.get("_ext", "htm"):
        body = to_text(body)

    # Editorial front matter between the header and the first real chapter —
    # the Agni-Purāṇa carries its edition's full anukramaṇikā (a table of
    # contents with print page numbers) there, which would otherwise be glued
    # onto the first verse. Opt-in per text: everything before the first match
    # of this regex is dropped (the match itself is kept, so the ordinary
    # NOISE pass still sees it).
    if spec.get("strip_before"):
        cut = re.search(spec["strip_before"], body)
        if cut:
            body = body[cut.start():]

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
        units.append((refs, groups.get("pada"), text, groups.get("sig") or ""))
    return units, attribution, len(matches)


def leaf_label(target):
    """'purana/garuda_purana/uttara_khanda_pretakalpa' -> 'Uttara Khanda Pretakalpa'."""
    return target.rstrip("/").rsplit("/", 1)[-1].replace("_", " ").title()


def route_units(units, spec):
    """Assign every unit to its output folder.

    Two registry-declared mechanisms, applied in this order:

    sig_targets   {siglum(lowercase): target} — a supplementary source file
                  with its own siglum sequence (the Vāmana-Purāṇa's
                  Saromāhātmya) whose refs would otherwise collide with the
                  main text's adhyāya numbering. Routed by siglum, refs kept.

    split_targets a multi-book text whose first ref level is the book. Either
                  a dict {ref1: target} or a '{ref1:02d}' format string. The
                  book component is consumed so the remaining refs group by
                  chapter inside each book's folder. A dict key matches the
                  FIRST dot-component of ref1, keeping any residue — the
                  Śiva-Purāṇa writes book 7's part level as 'ŚivP_7.1,c.v',
                  so '7.1' routes on '7' and keeps '1' as a part ref.

    Returns an ordered {target: [units]}; units nothing claims stay at
    spec['target'].
    """
    sig_map = {k.lower(): v for k, v in spec.get("sig_targets", {}).items()}
    split = spec.get("split_targets")
    out = {}

    def bucket(target):
        return out.setdefault(target, [])

    for refs, pada, text, sig in units:
        if sig_map and sig.lower() in sig_map:
            bucket(sig_map[sig.lower()]).append((refs, pada, text, sig))
            continue
        if split and refs:
            head, _, residue = refs[0].partition(".")
            if isinstance(split, dict):
                target = split.get(head)
            else:
                target = split.format(ref1=int(head)) if head.isdigit() else None
            if target:
                rest = ((residue,) if residue else ()) + refs[1:]
                bucket(target).append((rest or refs, pada, text, sig))
                continue
        bucket(spec["target"]).append((refs, pada, text, sig))
    return out


def group_items(units, spec, label=""):
    """Fold units into DGE items — one item per chapter-level division.

    Two-level refs group on the first; three or more (a split residue such as
    the Vāyavīya-saṃhitā's part level) compound everything above the verse
    into one key ('1.12') so no level is silently flattened away.
    """
    unit_name = spec.get("unit", "section")
    schema = spec["schema"]
    buckets = {}
    order = []
    for refs, pada, text, _sig in units:
        if not refs:
            continue
        key = ".".join(refs[:-1]) if len(refs) > 1 else "1"
        verse = refs[-1]
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        if verse.isdigit():                    # '001' (AP zero-pads) -> '1'
            verse = str(int(verse))
        number = f"{verse}{pada}" if pada else verse
        buckets[key].append({"number": number, "sanskrit_text": iast_to_dev(text),
                             "iast_text": text})

    items = []
    for key in order:
        ident = re.sub(r"[^0-9A-Za-z]+", "_", key)
        if ident.isdigit():
            ident = f"{int(ident):02d}"
        item_id = f"{unit_name}_{ident}"
        where = f"{spec['name']}, {label}, " if label else f"{spec['name']}, "
        reference = f"{where}{unit_name} {key}"
        if schema in ("itihasa_purana_text", "smriti_dharmashastra_text"):
            items.append({"id": item_id, "reference": reference, "shlokas": buckets[key]})
        else:
            joined = "\n".join(v["iast_text"] for v in buckets[key])
            items.append({"id": item_id, "reference": reference,
                          "sanskrit_text": iast_to_dev(joined), "iast_text": joined,
                          "artha": "", "notes": "", "tags": [], "references": [],
                          "audio": []})
    return items


def urls_for(spec, registry):
    out = []
    if spec.get("tei"):
        out.append((BASE + registry["tei_plaintext"] + spec["tei"] + ".txt", "txt"))
    for legacy in spec.get("legacy", []) + spec.get("legacy_extra", []):
        out.append((BASE + legacy, "htm"))
    return out


def write(spec, items, attribution, source_urls, dry_run, target=None, extra_note=""):
    target = target or spec["target"]
    payload = {
        "schema": spec["schema"],
        "default_author": spec.get("author", ""),
        "source_url": source_urls[0] if source_urls else "",
        "source_note": (build_note(spec, attribution) + (" " + extra_note if extra_note else ""))[:2000],
        "items": items,
    }
    folder = os.path.join(data_base(), target)
    verses = sum(len(i.get("shlokas", [])) for i in items) or len(items)
    print(f"  {spec['id']:<32} {len(items):>4} items / {verses:>6} units -> {target}"
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
        units, attr, count = parse(raw, spec, registry["marker_patterns"])
        all_units += units
        matched += count
        attribution = attribution or attr

    if not all_units:
        raise SystemExit(f"{text_id}: marker '{spec['marker']}' matched nothing — "
                         "the file's format has changed; re-check gretil_bulk.json")

    written = {}
    for target, part in sorted(route_units(all_units, spec).items()):
        label = leaf_label(target) if target != spec["target"] else ""
        items = group_items(part, spec, label=label)
        write(spec, items, attribution, used, dry_run, target=target)
        written[target] = items

    # A derived slice republishes a span of the base text under its own
    # folder (GRETIL has no standalone Durgāsaptaśatī; the registry slices it
    # out of the Mārkaṇḍeya file). The base keeps the full run either way.
    for derived in spec.get("derived", []):
        sliced = derived_slice(written.get(spec["target"], []), derived.get("slice", ""))
        if not sliced:
            print(f"  ! derived target {derived['target']}: no usable slice", file=sys.stderr)
            continue
        note = f"Derived slice: {derived['slice']}. {derived.get('note', '')}".strip()
        write(spec, sliced, attribution, used, dry_run,
              target=derived["target"], extra_note=note)
        written[derived["target"]] = sliced
    return written


def derived_slice(items, slice_spec):
    """Items whose numeric id suffix falls inside 'adhyaya LO-HI'."""
    span = re.search(r"(\d+)\s*-\s*(\d+)", slice_spec or "")
    if not span:
        return []
    lo, hi = int(span.group(1)), int(span.group(2))
    digits = re.compile(r"_(\d+)$")
    return [i for i in items
            if (m := digits.search(i["id"])) and lo <= int(m.group(1)) <= hi]


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

    # --group, like --all, is a bulk run: reference-only (legacy-licence)
    # entries stay out of it per the registry's own policy and only run when
    # named explicitly with --id.
    selected = [t for t in texts if
                (args.id and t["id"] == args.id) or
                (args.group and t["target"].startswith(args.group)
                 and t.get("licence") == "cc-by-nc-sa-4.0") or
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
