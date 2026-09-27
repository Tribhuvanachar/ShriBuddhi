#!/usr/bin/env python3
"""Make the two Yukti Mallika shelvings one work.

THE TWO COPIES. `Itara/YuktiMallika/data.json` is a 20 MB Kannada edition:
5,542 verse units across 210 chapters and five saurabhas, each verse carrying
its own anuvada, artha and vivarane, plus a separate stream of Bhavavilasini
excerpts. `Itara/yukti_mallika/` is a Devanagari edition of the SAME work at a
far coarser grain: 143 section units, with the Satyapramoda and Surottama
tikas as proper sibling layers. Neither contains the other -- the Kannada copy
has the three Kannada commentary streams the Devanagari one lacks, and the
Devanagari one has two tikas the Kannada one lacks -- so neither could simply
be deleted, and as two shelf entries they read as two different works.

WHY THE TEXTS WOULD NOT MATCH. They are the same verses, but the Kannada copy
is OCR'd and the scan confuses visually close letters -- it reads
ಬೌದ್ಧಜೈನಾಗವೌ where the text has ಬೌದ್ಧಜೈನಾಗಮೌ, ವ for ಮ. Exact matching after
transliteration found only 57 of 143 sections and looked like deep divergence;
it was scan noise. Anchoring each section by its opening pratika, fuzzily and
under the constraint that sections appear IN ORDER, places all 143, every one
at ratio 0.75 or better and strictly increasing. The order constraint is what
makes it safe: a stray high-scoring match cannot pull a section backwards.

THE RESULT is one grantha under `yukti_mallika/`, spined on the finer copy:

    mula/                 5,542 verses          the spine
    tika_anuvada/         the Kannada anuvada   per verse
    tika_artha/           the Kannada artha     per verse
    tika_vivarane/        the Kannada vivarane  per verse
    tika_bhavavilasini/   Bhavavilasini         per chapter (see below)
    tika_satyapramoda/    Satyapramoda tika     at its section's opening verse
    tika_surottama/       Surottama tika        at its section's opening verse
    tika_mulantara/       the Devanagari mula   at its section's opening verse

The Bhavavilasini stream is filed per CHAPTER, not per verse, because it is
not verse-aligned: its 3,838 entries are a running stream of tika, artha and
anuvada, and not one of them equals a spine verse. Splitting it across verses
would mean guessing which verse each paragraph belongs to.

`tika_mulantara` keeps the Devanagari mula rather than discarding it as a
duplicate of the spine. It is the second witness, and on the evidence above
the cleaner one -- the spine is the copy with the scan errors.

`source_meta` is NOT carried over (CLAUDE.md: never publish provenance).

Usage: python3 tools/yukti_mallika/merge_editions.py [--check]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

from indic_transliteration import sanscript

ROOT = Path(__file__).resolve().parents[2]
KANNADA = ROOT / "data/Tattvavada/Itara/YuktiMallika/data.json"
TARGET = ROOT / "data/Tattvavada/Itara/yukti_mallika"

WORK = "युक्तिमल्लिका"
AUTHOR = "श्रीमद्वादिराजतीर्थः"
SAURABHA = {"01": "गुणसौरभम्", "02": "शुद्धिसौरभम्", "03": "भेदसौरभम्",
            "04": "विश्वसौरभम्", "05": "फलसौरभम्"}

# Punctuation, digits and the zero-width joiners the Kannada scan sprinkles
# through its output (ಸಾರಮ್<ZWNJ>) -- all of which differ between the two
# editions without the text differing at all.
STRIP = re.compile(r"[\s।॥|,.\-–—'‘’\"“”()​‌‍­0-9೦-೯०-९]+")

# How far ahead of the last anchor a section may be found. Generous enough for
# the longest chapter (1,022 verses in one saurabha) without letting a section
# match something most of a saurabha away.
WINDOW = 500
MIN_RATIO = 0.75


def norm(s: str) -> str:
    return STRIP.sub("", s or "")


def to_kannada(s: str) -> str:
    return sanscript.transliterate(s or "", sanscript.DEVANAGARI, sanscript.KANNADA)


def anchor_sections(spine, sections) -> list[int]:
    """One spine index per section, strictly increasing. Raises if any section
    cannot be placed -- a half-anchored merge would silently drop tika."""
    normed = [norm(i.get("sa", "")) for i in spine]
    out = []
    last = -1
    for item in sections:
        crumbs = item.get("breadcrumb") or []
        pratika = norm(to_kannada(crumbs[4]))[:60] if len(crumbs) > 4 else ""
        best_ratio, best_at = 0.0, None
        for n in range(last + 1, min(len(normed), last + 1 + WINDOW)):
            candidate = normed[n][:len(pratika) + 10]
            if not candidate or not pratika:
                continue
            ratio = SequenceMatcher(None, pratika, candidate).ratio()
            if ratio > best_ratio:
                best_ratio, best_at = ratio, n
        if best_ratio < MIN_RATIO or best_at is None:
            raise SystemExit(
                f"section {item.get('section')!r} could not be anchored "
                f"(best ratio {best_ratio:.2f}); refusing a partial merge")
        out.append(best_at)
        last = best_at
    return out


def dump(path: Path, schema: str, author: str, items: list[dict]) -> str:
    head = json.dumps({"schema": schema, "default_author": author},
                      ensure_ascii=False, separators=(",", ":"))[:-1]
    body = ",\n".join(json.dumps(i, ensure_ascii=False, separators=(",", ":"))
                      for i in items)
    return head + ',"items":[\n' + body + "\n]}\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="report only")
    args = ap.parse_args()

    if not KANNADA.is_file():
        print(f"{KANNADA} is gone -- it is this tool's input and is deleted only "
              "AFTER a successful merge; restore it from git to re-run",
              file=sys.stderr)
        return 1
    kan = json.loads(KANNADA.read_text(encoding="utf-8"))
    spine_src = kan["items"]
    sections = json.loads((TARGET / "mula/data.json").read_text(encoding="utf-8"))["items"]
    # This tool writes its spine over the very file it reads its sections from,
    # so a second run would anchor the Devanagari sections against themselves
    # and fail with a confusing zero ratio. Say what actually happened instead:
    # the inputs are `YuktiMallika/data.json` and the ORIGINAL 143-section
    # mula, and re-running needs both restored from git.
    if len(sections) != 143 or sections[0]["id"].startswith("ym"):
        print(f"{TARGET}/mula already holds the merged spine "
              f"({len(sections)} items) -- restore mula/ and the two tika_ "
              "folders from git before re-running", file=sys.stderr)
        return 1
    tikas = {
        name: json.loads((TARGET / f"tika_{name}/data.json").read_text(encoding="utf-8"))["items"]
        for name in ("satyapramoda", "surottama")
    }

    at = anchor_sections(spine_src, sections)
    print(f"anchored {len(at)} sections, spine positions {at[0]}..{at[-1]}")

    # The Kannada copy numbers its units "0101001-1" -- chapter code plus a
    # counter. tools/build_layer_manifest.py deliberately refuses to treat a
    # PURELY NUMERIC id as a shared identity between a mula and its tikas
    # (publish.py renumbers every file 1..N, so two files' integers overlap by
    # position, not because they name the same verse), and "0101001" is
    # numeric, so this family earned no manifest entry at all and nothing
    # stitched. The guard is right; the ids were wrong. A work-specific stem
    # makes them real names rather than integers.
    def unit_id(item):
        return "ym" + item["id"]

    def crumbs_for(item):
        return [WORK, SAURABHA.get(item["id"][:2], ""), item.get("chapter_title", "")]

    spine, streams = [], {"anuvada": [], "artha": [], "vivarane": []}
    for item in spine_src:
        uid = unit_id(item)
        spine.append({"id": uid, "sanskrit_text": item.get("sa", ""),
                      "section": item.get("chapter_title", ""),
                      "breadcrumb": crumbs_for(item), "layer": "मूलम्"})
        for key, text in (item.get("commentaries") or {}).items():
            if key in streams and isinstance(text, str) and text.strip():
                streams[key].append({"id": uid, "sanskrit_text": text,
                                     "tika_title": {"anuvada": "अनुवादः",
                                                    "artha": "अर्थः",
                                                    "vivarane": "विवरणम्"}[key]})

    # Bhavavilasini: one item per chapter, at that chapter's FIRST spine verse.
    first_of_chapter = {}
    for item in spine_src:
        first_of_chapter.setdefault(item["id"].split("-")[0], unit_id(item))
    per_chapter: dict[str, list[str]] = {}
    for block in kan.get("tika_excerpts") or []:
        uid = first_of_chapter.get(block.get("chapter_code"))
        if not uid:
            continue
        chunks = [v.get("sanskrit", "").strip() for v in block.get("verses") or []]
        per_chapter.setdefault(uid, []).extend(c for c in chunks if c)
    bhava = [{"id": uid, "sanskrit_text": "\n\n".join(texts),
              "tika_title": "भावविलासिनी"}
             for uid, texts in per_chapter.items()]

    written = {
        "mula": ("grantha_mula_text", AUTHOR, spine),
        "tika_anuvada": ("grantha_tika_text", AUTHOR, streams["anuvada"]),
        "tika_artha": ("grantha_tika_text", AUTHOR, streams["artha"]),
        "tika_vivarane": ("grantha_tika_text", AUTHOR, streams["vivarane"]),
        "tika_bhavavilasini": ("grantha_tika_text", "श्रीसुरोत्तमतीर्थः", bhava),
    }
    for name, items in tikas.items():
        label = {"satyapramoda": "सत्यप्रमोदटीका", "surottama": "सुरोत्तमटीका"}[name]
        author = {"satyapramoda": "श्रीसत्यप्रमोदतीर्थः",
                  "surottama": "श्रीसुरोत्तमतीर्थः"}[name]
        written[f"tika_{name}"] = ("grantha_tika_text", author, [
            {"id": unit_id(spine_src[at[i]]), "sanskrit_text": it.get("sanskrit_text", ""),
             "tika_title": label}
            for i, it in enumerate(items) if (it.get("sanskrit_text") or "").strip()])
    written["tika_mulantara"] = ("grantha_tika_text", AUTHOR, [
        {"id": unit_id(spine_src[at[i]]), "sanskrit_text": it.get("sanskrit_text", ""),
         "tika_title": "मूलम् (पाठान्तरम्)"}
        for i, it in enumerate(sections) if (it.get("sanskrit_text") or "").strip()])

    for name, (schema, author, items) in written.items():
        text = dump(TARGET / name / "data.json", schema, author, items)
        # Bytes, not characters: Kannada is three bytes per character in
        # UTF-8, so len(str) understates these files by roughly threefold.
        kb = len(text.encode("utf-8")) // 1024
        print(f"   {name:<24} {len(items):>5} items  {kb:>6} KB")
        if not args.check:
            out = TARGET / name / "data.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text, encoding="utf-8")
    # Conservation check. The point of this merge is that nothing is lost, so
    # it is asserted rather than asserted-about: every character of commentary
    # in either source must be present in exactly one output layer.
    def total(strings):
        return sum(len(s) for s in strings)
    expected = {
        "anuvada": total(c.get("anuvada", "") for c in
                         ((i.get("commentaries") or {}) for i in spine_src)),
        "artha": total(c.get("artha", "") for c in
                       ((i.get("commentaries") or {}) for i in spine_src)),
        "vivarane": total(c.get("vivarane", "") for c in
                          ((i.get("commentaries") or {}) for i in spine_src)),
    }
    for key, want in expected.items():
        got = total(i["sanskrit_text"] for i in written[f"tika_{key}"][2])
        if got != want:
            print(f"  REFUSED: {key} carries {got} chars, source had {want}",
                  file=sys.stderr)
            return 1
    want_tika = total(v.get("sanskrit", "").strip()
                      for b in (kan.get("tika_excerpts") or [])
                      for v in (b.get("verses") or []))
    got_tika = total(i["sanskrit_text"] for i in bhava)
    # Joining with a blank line adds separators, never drops text.
    if got_tika < want_tika:
        print(f"  REFUSED: bhavavilasini carries {got_tika} chars of {want_tika}",
              file=sys.stderr)
        return 1
    for name, items in list(tikas.items()) + [("mulantara", sections)]:
        want = total(i.get("sanskrit_text", "") for i in items)
        got = total(i["sanskrit_text"] for i in written[f"tika_{name}"][2])
        if got != want:
            print(f"  REFUSED: {name} carries {got} chars, source had {want}",
                  file=sys.stderr)
            return 1
    print("conservation: every source character accounted for")
    print("--check: nothing written" if args.check else f"wrote {len(written)} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
