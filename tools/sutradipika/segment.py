#!/usr/bin/env python3
"""Segment the staged Brahmasūtradīpikā into addressed sūtras.

ब्रह्मसूत्रदीपिका of Śrī Jagannātha Yati on the Brahma Sūtras, edited with an
English gist by Dr V. R. Panchamukhi (Rashtriya Sanskrit Vidyapeetha Series 94,
Tirupati, 2002). 238 pages.

BOTH ENGINES ARE NEEDED HERE, which is new. Sarvam covers 25-238 and Vision
1-238, and the first 24 pages are where adhyāya 1 pāda 1 lives -- its 31
sūtras, the canonical count, including अथातो ब्रह्मजिज्ञासा. Reading Sarvam
alone would have lost the opening pāda of the Brahma Sūtras and left a hole
that no count of the rest would show. So Sarvam is used where it reaches and
Vision fills in before it.

That is possible because everything this segmenter keys on is TEXTUAL, not a
layout tag:

  * A SŪTRA is wrapped in ॐ … ॐ and closes with its number within the pāda:
    `३९. ।। ॐ सम्भोगप्राप्तिरिति चेन्न वैशेष्यात् ॐ।।८॥`. It carries two
    numbers -- a running one through the whole work and the pāda-relative one
    -- and the pāda-relative one is the address.
  * An ADHIKARAṆA heading is `॥ अन्वयाधिकरणम् ॥ १० ॥`.
  * The ADHYĀYA and PĀDA are named in Roman numerals in the running header,
    `Adhyāya-II, Pāda-I`, and spelled `ADHYAYA - I` / `Pada-I` on the pages
    Vision alone has.

THE SANDHI TRAP, for the third time in this corpus. `अधिकरणम्` has no literal
अ in `अन्वयाधिकरणम्`: the vowel is absorbed into the ा of या. A pattern
written around अधिकरणम् matches none of the 196 headings. The same thing hid
ಸೂತ್ರಾರ್ಥ in the Vaidika Svara Prakaraṇam and the pratīka in Rukmiṇīśa Vijaya,
where नेमुस्ताम् + इति prints नेमुस्तामिति. Match from inside the word.

    python3 tools/sutradipika/segment.py --staged-dir <dir>
"""

from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "ocr_common"))
import staged as S  # noqa: E402

# ॐ … ॐ … ॥ N ॥ -- the sūtra and its number within the pāda.
SUTRA = re.compile(r"ॐ\s*ॐ?\s*(.{3,240}?)\s*ॐ\s*[।॥\s]*(" + S.ANY_DIGIT + r"+)\s*[।॥]")
# See the docstring: matched from INSIDE the word, because the अ is gone.
ADHIKARANA = re.compile(
    r"[।॥]+\s*([^।॥]*?धिकरणम्[^।॥]*?)\s*[।॥]+\s*(" + S.ANY_DIGIT + r"+)\s*[।॥]")
# The RUNNING number that opens a sūtra line: `३९. ।। ॐ …`. It runs 1..530
# through the whole work and is the reliable one; the pāda-relative number
# beside it is OCR-fragile -- `१०२. ॥ ॐ कम्पनात् ॐ॥३१॥` is sūtra 39 of its
# pāda printed as 31, and eight more like it collided with a real address.
RUNNING = re.compile(r"^\s*(" + S.ANY_DIGIT + r"+)\s*[.।]")
ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4}
ADHYAYA = re.compile(r"ADHY[ĀA]YA\s*[-–—]?\s*([IVX]+)", re.I)
PADA = re.compile(r"P[ĀA]DA\s*[-–—]?\s*([IVX]+)", re.I)
BOTH = re.compile(r"Adhy[āa]ya\s*[-–—]?\s*([IVX]+)\s*,\s*P[āa]da\s*[-–—]?\s*([IVX]+)", re.I)


def merged_lines(staged_dir: str) -> tuple[list[dict], dict]:
    """One ordered list of lines for the whole book, from both engines.

    Sarvam's layout blocks where it reaches; Vision's text, split to lines,
    on the pages before it. Which engine each line came from travels with it,
    so a reading can be traced back.
    """
    sar = S.load_sarvam(staged_dir)
    vis = S.load_vision(staged_dir)
    lines: list[dict] = []
    stats = collections.Counter()
    for page in sorted(set(sar) | set(vis)):
        if page in sar:
            for b in S.read_stream({page: sar[page]}):
                lines.append({**b, "engine": "sarvam"})
                stats["sarvam_blocks"] += 1
        else:
            for raw in vis[page].split("\n"):
                t = S.flat(raw)
                if t:
                    lines.append({"page": page, "kind": "line", "text": t,
                                  "engine": "vision"})
                    stats["vision_lines"] += 1
            stats["vision_only_pages"] += 1
    return lines, dict(stats)


def segment(staged_dir: str) -> dict:
    """Address every sūtra, with the dīpikā on it.

    The address is adhyāya.pāda.N, and N is taken from READING ORDER rather
    than from the printed pāda-relative number, which the OCR damages often
    enough to collide: nine sūtras were printed with another's number and
    overwrote it. The printed number is kept beside the text as
    `printed_number` so a disagreement is visible rather than smoothed away.

    Some sūtras are set TWICE -- once as a display line and again at the head
    of their commentary, with the same running number and slightly different
    OCR. Those are merged, the longer reading kept, because they are one sūtra.
    """
    lines, stats = merged_lines(staged_dir)
    stats = collections.Counter(stats)

    found: list[dict] = []
    adhyaya = pada = None
    adhikarana = None
    for ln in lines:
        t = ln["text"]
        m = BOTH.search(t)
        if m:
            adhyaya, pada = ROMAN.get(m.group(1).upper()), ROMAN.get(m.group(2).upper())
            continue
        a = ADHYAYA.search(t)
        if a and len(t) < 60:
            adhyaya = ROMAN.get(a.group(1).upper()) or adhyaya
            continue
        p = PADA.search(t)
        if p and len(t) < 60:
            pada = ROMAN.get(p.group(1).upper()) or pada
            continue
        h = ADHIKARANA.search(t)
        if h:
            adhikarana = (S.flat(h.group(1)), S.to_int(h.group(2)))
            stats["adhikarana_headings"] += 1
            continue
        sm = SUTRA.search(t)
        if sm and adhyaya and pada:
            run = RUNNING.match(t)
            found.append({
                "adhyaya": adhyaya, "pada": pada,
                "running": S.to_int(run.group(1)) if run else None,
                "printed_number": S.to_int(sm.group(2)),
                "sa": S.flat(sm.group(1)), "page": ln["page"],
                "engine": ln["engine"],
                "adhikarana": adhikarana[0] if adhikarana else "",
                "adhikarana_number": adhikarana[1] if adhikarana else None,
                "tail": t[sm.end():].strip(),
            })
            continue
        if found:
            found[-1].setdefault("body", []).append(t)

    # Merge a sūtra set twice under one running number.
    merged: list[dict] = []
    for f in found:
        prev = merged[-1] if merged else None
        if (prev and f["running"] is not None
                and prev["running"] == f["running"]):
            stats["set_twice_merged"] += 1
            if len(f["sa"]) > len(prev["sa"]):
                prev["sa"] = f["sa"]
            prev.setdefault("body", []).extend(
                [f["tail"]] + f.get("body", []))
            continue
        merged.append(f)

    # THE PRINTED NUMBER IS PREFERRED, and overridden only when it cannot be
    # right: already used in this pāda, or not ahead of the last one accepted.
    # Numbering purely by reading order instead looked perfect -- 500 sūtras,
    # no gaps -- and was wrong, because a sūtra line the OCR missed shifts
    # every address after it. 208 of the 500 printed numbers then disagreed
    # with their slot, which is the measurement that gave it away.
    sutras: dict[tuple[int, int, int], dict] = {}
    last: dict[tuple[int, int], int] = {}
    for f in merged:
        key2 = (f["adhyaya"], f["pada"])
        n = f["printed_number"]
        if n <= last.get(key2, 0) or (key2[0], key2[1], n) in sutras:
            n = last.get(key2, 0) + 1
            stats["printed_number_overridden"] += 1
        last[key2] = n
        body = "\n".join([f["tail"]] + f.get("body", [])).strip()
        sutras[(f["adhyaya"], f["pada"], n)] = {
            "adhyaya": f["adhyaya"], "pada": f["pada"], "sutra": n,
            "running": f["running"], "printed_number": f["printed_number"],
            "sa": f["sa"], "page": f["page"], "engine": f["engine"],
            "adhikarana": f["adhikarana"],
            "adhikarana_number": f["adhikarana_number"],
            "commentary": body,
        }

    per: dict[tuple[int, int], list[int]] = collections.defaultdict(list)
    for (a, p, n) in sutras:
        per[(a, p)].append(n)
    padas = []
    for (a, p) in sorted(per):
        got = sorted(per[(a, p)])
        padas.append({"adhyaya": a, "pada": p, "found": len(got),
                      "highest": max(got),
                      "missing": [i for i in range(1, max(got) + 1)
                                  if i not in set(got)]})
    return {
        **S.page_report({**S.load_sarvam(staged_dir), **S.load_vision(staged_dir)}),
        "stats": dict(stats),
        "padas": padas,
        "sutras_found": sum(x["found"] for x in padas),
        "sutras_missing": sum(len(x["missing"]) for x in padas),
        "with_commentary": sum(1 for v in sutras.values() if v["commentary"]),
        "with_adhikarana": sum(1 for v in sutras.values() if v["adhikarana"]),
        "from_vision": sum(1 for v in sutras.values() if v["engine"] == "vision"),
        "sutras": sutras,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--staged-dir", required=True)
    ap.add_argument("--json")
    args = ap.parse_args(argv)
    rep = segment(args.staged_dir)
    print(f"pages {rep['pages']} ({rep['page_range'][0]}-{rep['page_range'][1]}), "
          f"gaps {len(rep['page_gaps'])}")
    print(f"{rep['stats']}\n")
    for x in rep["padas"]:
        flag = "" if not x["missing"] else f"  MISSING {x['missing'][:8]}"
        print(f"  {x['adhyaya']}.{x['pada']}  {x['found']:>3} sūtras, "
              f"highest {x['highest']:>3}{flag}")
    print(f"\n{rep['sutras_found']} sūtras, {rep['sutras_missing']} missing; "
          f"{rep['with_commentary']} with the dīpikā, "
          f"{rep['with_adhikarana']} under an adhikaraṇa, "
          f"{rep['from_vision']} read from Vision")
    if args.json:
        out = dict(rep)
        out["sutras"] = [v for _, v in sorted(rep["sutras"].items())]
        json.dump(out, open(args.json, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    return 0 if rep["sutras_missing"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
