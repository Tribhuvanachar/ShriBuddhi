"""
dcs_common.py -- shared CoNLL-U -> DGE "generic" schema conversion, factored
out of build_jyotisha_pilot.py so later DCS imports (build_sivasutra.py and
whatever follows) don't re-derive the same parsing logic.

DCS CoNLL-U convention used here: each "sentence" is one pada (verse-line)
or, for prose sutra texts, one whole sutra; `sent_counter` groups a text's
sentences into verses/units, `sent_subcounter` orders the padas within one
(sutra texts have exactly one subcounter per unit; verse texts typically
have two, matching a shloka's two half-verses).

CHAPTER NESTING, fixed after a real near-miss (23 Aug): DCS's "## chapter:"
line isn't always a single number -- e.g. Maitrayani Samhita uses "MS, 1,
1, 1" (Kanda.Prapathaka.Anuvaka), Aitareya Brahmana uses "AB, 1, 2"
(Pancika.Khanda). Extracting only the trailing number, as an earlier
version of this file did, silently collapsed distinct sections onto the
same id (e.g. "MS, 1, 1, 5" and "MS, 1, 2, 5" would both become chapter 5)
and would have overwritten data. Fixed by keeping the FULL numeric path
after the text abbreviation, joined with '.' -- correct at any nesting
depth, and identical output to before for the two already-shipped
single-level texts (Suryasiddhanta, Sivasutra).
"""
import glob
import json
import os
import re

from skrutable.transliteration import Transliterator

_translit = Transliterator(from_scheme="IAST", to_scheme="DEV")

_NUMERIC_FIELD = re.compile(r"-?\d+(?:\.\d+)*")


def _parse_chapter_path(line):
    """'## chapter: MS, 1, 1, 1' -> '1.1.1'; '## chapter: SūrSiddh, 1' -> '1'.

    A 4th convention, found in Sāṃkhyatattvakaumudī (23 Aug, batch 4): a
    single comma-field can itself already be dot-separated, e.g.
    '## chapter: STKau zu SāṃKār, 1.2' (kārikā 1, subsection 2) -- one
    field, not several comma-separated ones. The original version only
    accepted a bare integer per comma-field and silently produced no
    chapter_path (and hence 0 items) for this text -- caught by the
    established discipline of treating an implausible item count as a
    bug, not a small text. Each comma-field matching digits optionally
    dot-separated is now split on '.' and the pieces flattened in, so
    both conventions -- several single-integer fields, or one
    already-dotted field -- produce the same joined path.

    A 5th convention, found checking Carakasamhita before importing it
    (23 Aug, batch 5): a comma-field can be a non-numeric SECTION NAME
    interleaved between numeric fields, e.g. '## chapter: Ca, Sū., 1'
    vs '## chapter: Ca, Cik., 1' -- Sutrasthana chapter 1 and
    Cikitsasthana chapter 1, two genuinely different sections of the
    same samhita. The original version (correctly, for MS/AB) dropped
    any non-numeric field -- here that would silently collapse both
    onto the same chapter_path '1', overwriting one sthana's content
    with the other's. Checked across the whole Ayurveda cluster before
    trusting this: Carakasamhita, Sushrutasamhita and
    Ashtangahridayasamhita (plus their commentaries) all carry this
    convention, 8 sthana names in Caraka alone. Fixed by keeping a
    non-numeric field too, as a slug (its letters only, diacritics kept
    so distinct sthana abbreviations can't collide by having their
    Sanskrit diacritics stripped down to the same bare consonant)."""
    value = line.split(":", 1)[1].strip()
    parts = [p.strip() for p in value.split(",")]
    path_parts = []
    for p in parts[1:]:
        if _NUMERIC_FIELD.fullmatch(p):
            path_parts.extend(p.lstrip("-").split("."))
        elif p:
            slug = re.sub(r"[^\w]+", "", p)
            if slug:
                path_parts.append(slug)
    return ".".join(path_parts) if path_parts else None


def _path_sort_key(chapter_path):
    """Sort key for a chapter_path that may now mix numeric segments with
    non-numeric section-name slugs (see _parse_chapter_path's 5th
    convention) -- plain int(p) on every segment, used before this fix,
    would crash on a slug. Numeric segments sort before non-numeric ones
    at the same position (arbitrary but stable) and compare by value;
    non-numeric segments compare as strings."""
    return [(0, int(p)) if p.isdigit() else (1, p) for p in chapter_path.split(".")]


def _parse_int(line):
    """Return the integer after '=', or None if missing/malformed. Two
    distinct blank-value cases were found, 24 Aug, and are NOT the same
    thing: (1) prose texts (e.g. Aitareya Brahmana, Jaiminiya Brahmana)
    leave 'sent_subcounter' blank on EVERY sentence -- there's no pada
    pairing in prose, so the caller treats a blank subcounter as 1, not
    missing; (2) a handful of individual sentences (e.g. in Matsyapurana)
    have a genuinely blank 'sent_subcounter' amid otherwise-numbered
    verse text -- a real data gap, correctly skipped by the caller when
    this returns None for something that ISN'T uniformly blank across
    the file. This function only reports what it sees; the caller
    decides which case applies."""
    value = line.split("=", 1)[1].strip()
    return int(value) if value.isdigit() else None


def parse_conllu_file(path):
    """Yield (chapter_path, sent_counter, sent_subcounter, iast_text).
    Silently skips units with a missing/malformed counter -- see _parse_int
    for the two distinct blank-subcounter cases this handles differently."""
    with open(path, encoding="utf-8") as f:
        lines = [l.rstrip("\n") for l in f]

    # Prose texts leave sent_subcounter blank on every sentence (no pada
    # pairing); verse texts populate it (1, 2, ...) except for isolated
    # real data gaps. Decide once per file which situation this is.
    subcounter_lines = [l for l in lines if l.startswith("# sent_subcounter = ")]
    file_has_no_subcounters = bool(subcounter_lines) and all(_parse_int(l) is None for l in subcounter_lines)

    # A third convention, found in some Aitareya/Jaiminiya Brahmana files:
    # no sent_counter/sent_subcounter fields at all, only '# sent_id =
    # NNNNNN_M' per sentence. Two consecutive sentences here (e.g.
    # 650034_1, 650034_2) are each grammatically complete on their own in
    # the files checked, not two halves of one verse -- so this fallback
    # deliberately does NOT group by sent_id's own numbering (which would
    # risk merging genuinely separate sentences into one unit). Instead
    # every sentence in such a file gets its own running index, subcounter
    # fixed at 1, guaranteeing no merging regardless of what the sent_id
    # numbers mean.
    has_counters = any(l.startswith("# sent_counter = ") for l in lines)

    chapter_path = None
    text = counter = subcounter = None
    running_index = 0

    def ready():
        return text is not None and counter is not None and subcounter is not None and chapter_path is not None

    for line in lines:
        if line.startswith("## chapter:"):
            chapter_path = _parse_chapter_path(line)
        elif line.startswith("# text = "):
            # A new sentence starting means the previous one (if any) is
            # complete -- matters only for the no-counters fallback, where
            # there's no explicit "end of unit" marker line like
            # sent_subcounter to flush on.
            if not has_counters and ready():
                yield chapter_path, counter, subcounter, text
            text = line[len("# text = "):].strip()
            if not has_counters:
                running_index += 1
                counter, subcounter = running_index, 1
        elif line.startswith("# sent_counter = "):
            counter = _parse_int(line)
        elif line.startswith("# sent_subcounter = "):
            parsed = _parse_int(line)
            subcounter = 1 if (parsed is None and file_has_no_subcounters) else parsed
            if has_counters:
                if ready():
                    yield chapter_path, counter, subcounter, text
                text = None

    if not has_counters and ready():
        yield chapter_path, counter, subcounter, text


def collect_padas(vendor_dir):
    """Parse every .conllu file in vendor_dir into {(chapter_path, unit):
    {subcounter: iast_text}}, shared by both single-file and split imports."""
    padas_by_unit = {}
    for path in sorted(glob.glob(os.path.join(vendor_dir, "*.conllu"))):
        for chapter_path, unit, subcounter, iast in parse_conllu_file(path):
            key = (chapter_path, unit)
            padas_by_unit.setdefault(key, {})[subcounter] = iast
    return padas_by_unit


def _sort_key(chapter_unit):
    chapter_path, unit = chapter_unit
    return (_path_sort_key(chapter_path), unit)


def _build_items(padas_by_unit, source_name, tag):
    items = []
    for (chapter_path, unit) in sorted(padas_by_unit, key=_sort_key):
        padas = padas_by_unit[(chapter_path, unit)]
        iast_full = " ".join(padas[k] for k in sorted(padas))
        devanagari = _translit.transliterate(iast_full)
        item_id = f"{chapter_path}.{unit}"
        items.append({
            "id": item_id,
            "title": item_id,
            "text": devanagari,
            "notes": (
                f"Source: {source_name}, CC-BY 4.0. Devanagari produced from "
                "the DCS IAST transcription via skrutable's transliterator "
                "(pip dependency, no vendored code)."
            ),
            "tags": [tag],
        })
    return items


def _write_data_json(out_path, items, chapters_seen, *, default_author,
                      source_name, source_url, licence, note):
    out = {
        "schema": "generic",
        "default_author": default_author,
        "source": source_name,
        "source_url": source_url,
        "licence": licence,
        "note": note.format(count=len(items), chapters=chapters_seen),
        "items": items,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)


def build_generic_import(
    vendor_dir, out_path, *, source_name, source_url, licence, note, tag,
    default_author="unspecified",
):
    """Parse every .conllu file in vendor_dir and write a DGE 'generic'
    schema data.json to out_path. Returns (item_count, chapters_seen)."""
    padas_by_unit = collect_padas(vendor_dir)
    items = _build_items(padas_by_unit, source_name, tag)
    chapters_seen = sorted(set(c for c, u in padas_by_unit), key=_path_sort_key)
    _write_data_json(out_path, items, chapters_seen, default_author=default_author,
                      source_name=source_name, source_url=source_url,
                      licence=licence, note=note)
    return len(items), chapters_seen


def build_split_import(
    vendor_dir, book_to_path, *, source_name, source_url, licence, note, tag,
    default_author="unspecified",
):
    """Like build_generic_import, but for a text whose DCS chapter_path's
    FIRST numeric component (the book/kanda/amsha number) already
    corresponds to separate existing taxonomy leaves -- e.g. Vishnu
    Purana's 6 amshas, or Paippalada Atharvaveda's kandas. book_to_path
    maps that leading number (int) to an output data.json path; any book
    number present in the source but absent from book_to_path is skipped
    (reported, not silently dropped) rather than guessed into a leaf.
    Returns {book_number: (item_count, chapters_seen)} for books written,
    plus a 'skipped' key listing book numbers found but not mapped."""
    padas_by_unit = collect_padas(vendor_dir)
    by_book = {}
    for (chapter_path, unit), padas in padas_by_unit.items():
        book = int(chapter_path.split(".")[0])
        by_book.setdefault(book, {})[(chapter_path, unit)] = padas

    results = {}
    skipped = sorted(b for b in by_book if b not in book_to_path)
    for book, out_path in book_to_path.items():
        book_padas = by_book.get(book, {})
        if not book_padas:
            continue
        items = _build_items(book_padas, source_name, tag)
        chapters_seen = sorted(set(c for c, u in book_padas), key=_path_sort_key)
        _write_data_json(out_path, items, chapters_seen, default_author=default_author,
                          source_name=source_name, source_url=source_url,
                          licence=licence, note=note)
        results[book] = (len(items), chapters_seen)
    results["skipped"] = skipped
    return results
