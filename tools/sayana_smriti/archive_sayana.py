#!/usr/bin/env python3
"""
archive_sayana.py — Sāyaṇa's Ṛgveda-bhāṣya, in Sanskrit, from the archive.org scan.

WHY THIS EXISTS ALONGSIDE import_sayana_rigveda.py
--------------------------------------------------
That importer pulls Sāyaṇa as rendered in Wilson's English from wisdomlib, and
wisdomlib answers 403 to every datacenter IP range -- /robots.txt included, so
there is no crawler policy being expressed, just an edge rule against cloud
address space. It works from a residential connection (see PHONE.md) and not
from Actions.

archive.org is open to Actions, and carries the Sanskrit text. So this route
gives Sāyaṇa's own words rather than a Victorian paraphrase of them, with no
residential connection needed. The two are complementary, not rival: they write
`commentaries.sayana` and `commentaries.wilson`, which core.js labels separately.

HOW ALIGNMENT WORKS, AND WHY IT IS SAFE
---------------------------------------
The edition prints, per mantra and in order:

    <saṃhitā-pāṭha>   ... ॥ N ॥
    <pada-pāṭha>      ... ॥ N ॥
    <Sāyaṇa's bhāṣya>            (runs until the next mantra's saṃhitā-pāṭha)

Measured on maṇḍala 1: 4,242 markers for 2,006 mantras — 2.1 per mantra, which
is what that structure predicts.

So each mantra is identified by TWO independent signals: the marker's number,
and the text itself, which DGE already holds as `samhita_patha_plain` and
`pada_patha_plain`. Requiring both is what makes a wrong attachment detectable
rather than plausible -- a mis-cut lands commentary under a mantra whose own
words do not match it, and that is exactly what the score measures.

OCR damage is absorbed by comparing consonant-vowel skeletons: accents, daṇḍas,
the typesetter's pratīka quotes and the letters this scan habitually confuses
are folded away before scoring. What remains is what OCR gets right.

WHAT THIS DOES NOT DO
---------------------
It does not pretend the OCR is clean. Every layer it writes is marked as
uncorrected OCR of a scan, and mantras it cannot align at the required score
are left alone rather than filled with a best guess.
"""

from __future__ import annotations

import argparse
import http.client
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from difflib import SequenceMatcher
from pathlib import Path

ITEM = "rgveda-with-sayanabhasya"
UA = ("DGE-import/1.0 (Digital Grantha Engine; non-commercial educational "
      "digital library; github.com/Tribhuvanachar/bhumandala)")

# Which OCR file covers which maṇḍalas, from the item's own file listing.
VOLUMES = [
    ("maṇḍala 1", (1,)),
    ("maṇḍalas 2-5", (2, 3, 4, 5)),
    ("maṇḍalas 6-8", (6, 7, 8)),
    ("maṇḍalas 9-10", (9, 10)),
]

SAMHITA = "data/vedas/rigveda/shakala_shakha/samhita/mandala_{m:02d}/data.json"

ATTRIBUTION = {
    "sayana": {
        "commentator": "Sāyaṇācārya",
        "work": "Ṛgveda-bhāṣya",
        "edition": "Ṛgveda with Sāyaṇabhāṣya (scan digitised by the Internet Archive)",
        "source": f"https://archive.org/details/{ITEM}",
        "note": "Uncorrected OCR of a printed scan, aligned to each mantra by "
                "matching the saṃhitā- and pada-pāṭha the edition prints above "
                "the commentary. Not a critical edition; expect scanning errors.",
    }
}

# ---------------------------------------------------------------- text folding

_ACCENTS = "".join(chr(c) for c in
                   list(range(0x0951, 0x0953)) +
                   [0x1CD0, 0x1CD1, 0x1CD2, 0x1CDA, 0x1CDD, 0x1CE1])
_FOLD = (("ळ", "ल"), ("ऴ", "ल"), ("ॠ", "ऋ"), ("ॄ", "ृ"), ("ँ", "ं"),
         ("ऩ", "न"), ("ऱ", "र"), ("ऺ", ""), ("ऻ", ""))


def skeleton(s: str) -> str:
    """Devanagari consonant-vowel skeleton: what OCR reproduces reliably.

    Accents, punctuation, spacing and the letter pairs this scan confuses are
    all removed, because each of them is a coin-flip in the scan and none of
    them carries identity -- two mantras never differ only by an accent.
    """
    if not s:
        return ""
    s = unicodedata.normalize("NFC", s)
    s = re.sub(f"[{_ACCENTS}]", "", s)
    s = re.sub(r"[^ऀ-ॿ]", "", s)
    # The danda, double danda and Devanagari digits live INSIDE the Devanagari
    # block, so the class above keeps them. They have to go explicitly: the scan
    # places them erratically and repeats every verse number twice, so leaving
    # them in feeds the matcher noise that correlates with nothing.
    s = re.sub(r"[।॥०-९]", "", s)
    for a, b in _FOLD:
        s = s.replace(a, b)
    return s


# The edition carries a critical apparatus at the foot of many pages: numbered
# variant readings keyed to manuscript sigla, e.g.
#     १. ख-च-फ-'आत्रेये' नास्ति। २. ख-ग-च-ण-भ-ल-स-'प्रातरनुवाके' नास्ति।
# The OCR interleaves these with the body, so the block following a pada-patha is
# sometimes apparatus rather than commentary. Found by reading RV 5.1.2's
# alignment, not by any score -- an apparatus block scores exactly as well as a
# real one, because the score measures the MANTRA above it, not what follows.
_SIGLA = re.compile(r"[क-हा-ौ]-[क-हा-ौ]-[क-हा-ौ]-")
_NUMBERED_NOTE = re.compile(r"^\s*[०-९]+\s*[.।]")


def looks_like_apparatus(text: str) -> bool:
    """True if this block is variant readings rather than Sāyaṇa's prose."""
    if not text:
        return False
    head = text.strip()[:400]
    # Two independent marks, both required: an opening note number, and the
    # hyphenated manuscript sigla that only ever appear in the apparatus.
    return bool(_NUMBERED_NOTE.match(head)) and bool(_SIGLA.search(head))


def similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


# ------------------------------------------------------------------ numbering

_DEVA_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
_MARKER = re.compile(r"॥\s*([०-९0-9]{1,3})\s*॥")


def to_int(s: str) -> int | None:
    try:
        return int(s.translate(_DEVA_DIGITS))
    except ValueError:
        return None


class Block:
    """Text running up to a ॥ N ॥ marker, with that marker's number."""

    __slots__ = ("num", "text", "start", "end")

    def __init__(self, num, text, start, end):
        self.num, self.text, self.start, self.end = num, text, start, end

    def __repr__(self):
        return f"Block({self.num}, {self.text[:24]!r})"


def parse_blocks(ocr: str) -> list[Block]:
    """Split the OCR on ॥ N ॥ markers.

    Every mantra contributes two of these (saṃhitā, then pada), and sūkta and
    anuvāka ends contribute more. Nothing is filtered here -- the caller decides
    what a block is by matching it against a mantra it already holds, which is a
    far better test than any heuristic about the number alone.
    """
    blocks, prev = [], 0
    for m in _MARKER.finditer(ocr):
        num = to_int(m.group(1))
        if num is not None:
            blocks.append(Block(num, ocr[prev:m.start()], prev, m.end()))
        prev = m.end()
    return blocks


# ------------------------------------------------------------------ alignment

def align(items: list[dict], blocks: list[Block], *,
          threshold: float = 0.55, window: int = 40) -> dict:
    """Attach each mantra to its bhāṣya.

    Walks the mantras in order, and for each looks ahead a bounded window for a
    block whose marker number matches the mantra's position in its sūkta AND
    whose text resembles the mantra. Both must agree.

    The cursor advances on a hit, and on a miss it stays put -- so a mantra the
    scan omits costs one mantra, not the rest of the run. That is the failure
    mode round 2 of the probe had: it advanced only on hits with too small a
    window, and never recovered once it fell behind.
    """
    out, scores, misses = {}, [], []
    cursor = 0
    # One OCR file covers several maṇḍalas (2-5 share one, 6-8 another), so a
    # maṇḍala's mantras may begin thousands of blocks into the file. Until the
    # first mantra is placed, search the whole block list rather than a window
    # from position zero -- otherwise every maṇḍala but the volume's first
    # would look for its mantras among the previous maṇḍala's blocks and find
    # nothing. After the anchor, the window applies as normal.
    anchored = False

    for it in items:
        mid = it.get("id", "")
        parts = mid.split(".")
        rk = to_int(parts[-1]) if parts else None
        sam = skeleton(it.get("samhita_patha_plain") or it.get("samhita_patha") or "")
        pad = skeleton(it.get("pada_patha_plain") or it.get("pada_patha") or "")
        if not sam or rk is None:
            continue

        best = (0.0, -1)
        hi = len(blocks) if not anchored else min(cursor + window, len(blocks))
        for j in range(cursor, hi):
            b = blocks[j]
            if b.num != rk:                     # the number must agree first
                continue
            cand = skeleton(b.text)[-(len(sam) + 60):]
            sc = max(similarity(sam, cand), similarity(pad, cand) if pad else 0.0)
            if sc > best[0]:
                best = (sc, j)

        score, j = best
        scores.append(score)
        if score < threshold or j < 0:
            misses.append(mid)
            continue

        # The pada-pāṭha repeats the same number immediately after; the bhāṣya
        # is everything from the end of that repeat up to the next block.
        end_of_pada = j
        if j + 1 < len(blocks) and blocks[j + 1].num == rk:
            end_of_pada = j + 1
        # Step past any apparatus blocks sitting between the pada-pāṭha and the
        # commentary, rather than handing the reader a page of variant readings
        # labelled as Sāyaṇa.
        bhashya = ""
        for k in range(end_of_pada + 1, min(end_of_pada + 4, len(blocks))):
            if looks_like_apparatus(blocks[k].text):
                continue
            bhashya = blocks[k].text
            break

        bhashya = re.sub(r"\s+", " ", bhashya).strip()
        if bhashya:
            out[mid] = {"text": bhashya, "score": round(score, 3)}
        cursor = end_of_pada + 1
        anchored = True

    return {"aligned": out, "scores": scores, "misses": misses}


# -------------------------------------------------------------------- fetching

def fetch(url: str, timeout: int = 180, attempts: int = 4) -> bytes:
    """GET a URL, retrying the failures that are the network's fault and not ours.

    archive.org drops a connection now and then -- a SYN that never gets
    answered, which the kernel gives up on after about two minutes. One such
    drop used to end the whole run, which is a poor trade when the fix is to
    ask again a few seconds later. So transport failures are retried; an
    answer from the server is not, because a 404 says the same thing however
    often it is asked. 5xx and 429 are the exception: those are the server
    saying "not now", which is worth waiting out.
    """
    for attempt in range(1, attempts + 1):
        try:
            return urllib.request.urlopen(
                urllib.request.Request(url, headers={"User-Agent": UA}),
                timeout=timeout).read()
        except (urllib.error.URLError, http.client.HTTPException, OSError) as e:
            retryable = not (isinstance(e, urllib.error.HTTPError)
                             and e.code < 500 and e.code != 429)
            if attempt == attempts or not retryable:
                raise
            pause = 2 ** attempt
            print(f"  .. {url}\n     {e}; retrying in {pause}s "
                  f"({attempt} of {attempts - 1})", file=sys.stderr, flush=True)
            time.sleep(pause)


def volume_for(mandala: int, cache: Path | None = None) -> str:
    meta = json.loads(fetch(f"https://archive.org/metadata/{ITEM}"))
    want = next(label for label, ms in VOLUMES if mandala in ms)
    key = want.split()[-1]
    names = [f["name"] for f in meta.get("files", []) if f.get("name","").endswith("_djvu.txt")]
    name = next((n for n in names if key in n), None)
    if name is None:
        raise RuntimeError(f"no OCR file for maṇḍala {mandala}; saw {names}")
    if cache:
        cache.mkdir(parents=True, exist_ok=True)
        cached = cache / re.sub(r"[^A-Za-z0-9_.-]", "_", name)
        if cached.exists():
            return cached.read_text(encoding="utf-8")
    text = fetch(f"https://archive.org/download/{ITEM}/{urllib.parse.quote(name)}"
                 ).decode("utf-8", "replace")
    if cache:
        cached.write_text(text, encoding="utf-8")
    return text


# ------------------------------------------------------------------------ main

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dge-root", required=True, help="path to the repo's dge/ directory")
    ap.add_argument("--mandala", type=int, action="append",
                    help="restrict to these maṇḍalas (repeatable; default all ten)")
    ap.add_argument("--cache-dir", default=".httpcache")
    ap.add_argument("--threshold", type=float, default=0.55,
                    help="minimum similarity to accept an alignment")
    ap.add_argument("--min-coverage", type=float, default=0.80,
                    help="abort without writing if a maṇḍala aligns below this")
    ap.add_argument("--dry-run", action="store_true", help="report only; write nothing")
    ap.add_argument("--overwrite", action="store_true",
                    help="replace an existing commentaries.sayana instead of skipping")
    args = ap.parse_args(argv)

    dge = Path(args.dge_root)
    if not (dge / "data" / "schemas.json").exists():
        print(f"!! {dge} does not look like the dge/ directory", file=sys.stderr)
        return 2

    mandalas = sorted(set(args.mandala)) if args.mandala else list(range(1, 11))
    cache = Path(args.cache_dir)
    grand = {"mantras": 0, "aligned": 0, "written": 0}
    per_mandala = {}

    for m in mandalas:
        path = dge / SAMHITA.format(m=m)
        if not path.exists():
            print(f"!! no data.json at {path}; skipping maṇḍala {m}", file=sys.stderr)
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        items = data.get("items", [])
        print(f"\n== Maṇḍala {m}: {len(items)} mantras")

        ocr = volume_for(m, cache)
        blocks = parse_blocks(ocr)
        print(f"   OCR {len(ocr):,} chars, {len(blocks):,} ॥N॥ blocks")

        res = align(items, blocks, threshold=args.threshold)
        got = len(res["aligned"])
        cov = got / max(len(items), 1)
        scores = sorted(s for s in res["scores"] if s > 0)
        med = scores[len(scores) // 2] if scores else 0.0
        print(f"   aligned {got}/{len(items)} ({100*cov:.1f}%), median score {med:.2f}")
        per_mandala[m] = {"mantras": len(items), "aligned": got,
                          "coverage": round(cov, 4), "median_score": round(med, 3)}
        grand["mantras"] += len(items)
        grand["aligned"] += got

        if cov < args.min_coverage:
            print(f"   !! coverage {100*cov:.1f}% is below --min-coverage "
                  f"{100*args.min_coverage:.0f}%; not writing maṇḍala {m}", file=sys.stderr)
            continue
        if args.dry_run:
            continue

        by_id = {it["id"]: it for it in items}
        added = 0
        for mid, rec in res["aligned"].items():
            comm = by_id[mid].setdefault("commentaries", {})
            if rec["text"] and (args.overwrite or not comm.get("sayana")):
                comm["sayana"] = rec["text"]
                added += 1
        if added:
            data.setdefault("commentary_sources", {}).update(ATTRIBUTION)
            path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n",
                            encoding="utf-8")
            print(f"   -> wrote {path} (+{added})")
            grand["written"] += added

    print("\n" + json.dumps({"per_mandala": per_mandala, "totals": grand},
                            ensure_ascii=False, indent=2))
    # A run that aligned nothing is a failure, whatever the exit path looked
    # like. The wisdomlib run exited 0 having imported zero, and that is exactly
    # the outcome worth making loud.
    if grand["mantras"] and grand["aligned"] == 0:
        print("!! aligned 0 mantras", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
