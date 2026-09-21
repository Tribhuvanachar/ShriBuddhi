#!/usr/bin/env python3
"""
segment.py -- turn the three staged Aitareya OCR volumes into addressed,
layer-tagged blocks.

This is the step docs/OCR_PENDING.md calls "segmentation", and the reason
those three branches have never landed. The staged files are page-level
Sarvam HTML -- 994, 596 and 320 pages of continuous prose. The target,
data/darshana/vedanta/dvaita/DvaitaVedantaIn/upanishad_prasthana/
aitareyopanishad_bhashya, addresses its units as

    द्वितीयारण्यके > <अध्यायः> > <खण्डः> > <the mula's opening words>

so nothing can be attached until each stretch of prose is given that
address. tools/merge_staged_commentary.py cannot help: it merges into a
numbered `shlokas` dict, and this target uses `items` with hierarchical
`reference` strings.

tools/upanishad_tippani/build_verify.py does this job for eight other
upanisads, and cannot be extended to cover these. It keys off a label
convention -- "वे.श्रुत्यर्थः-", "अ.सं.-" at line start -- used by the
multi-commentary Visvamadhva Mahaparisat volumes. Measured against these
three: one matching line in 15,662. They are single-commentary PPVP
editions and carry no such labels.

Each volume is structured differently, so each gets its own rule, and each
rule is something measured in the file rather than assumed:

  bhagavantaraya (994 pp)
      Two separately-paginated streams, interleaved by the scan, and the
      split is exact: of the pages whose running head OCR'd, all 370
      carrying "श्रीमन्महैतरेयोपनिषद्भाष्यम्" are odd PDF pages and all 359
      carrying an "आ-२, अ-१, खं-१" coordinate are even ones, with no
      exceptions either way. The even stream is the Bhavapradipa tippani
      and its running head states its own address, which is precisely the
      address the target uses. The odd stream is the mula and bhasya the
      shelf already holds.

  ratnamala (596 pp)
      One stream, divided by standalone label lines ending in a dash:
      टिप्पणी- (269), भाष्यम्- (260), उपनिषत्- (110), खण्डार्थः- (26).
      Those names are the shelf's own layer names.

  visvesvara_tirtha (320 pp)
      Neither convention: no coordinates, no section labels. Its running
      head is prose ("द्वितीयप्रघट्टके तृतीयोऽध्यायः"). Reported, not
      segmented -- see the note this prints.

Output is staged, never written into the corpus: this produces a file
under data/ocr_staging/ for review in admin/ocr-review.html, matching how
every other OCR batch in this project reaches the shelf.

  python3 tools/aitareya/segment.py                    # report
  python3 tools/aitareya/segment.py --write <dir>      # emit staged JSON
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter, OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / ("data/darshana/vedanta/dvaita/DvaitaVedantaIn/"
                 "upanishad_prasthana/aitareyopanishad_bhashya")

VOLUMES = {
    "bhagavantaraya": {
        "branch": "origin/ocr-staging/aitereya_upanisad_bh__ommentary_bhagavantaraya",
        "files": ["sarvam_pages10-209.json", "sarvam_pages210-409.json",
                  "sarvam_pages410-609.json", "sarvam_pages610-809.json",
                  "sarvam_pages810-1003.json"],
        "rule": "two_stream",
        "layer": "tika_bhavapradipa",
        "title": "भावप्रदीपः — भगवन्तरायः",
    },
    "ratnamala": {
        "branch": "origin/ocr-staging/aitereya_upanisad_bh__tha_ratnamala_commentary",
        "files": ["sarvam_pages6-205.json", "sarvam_pages206-405.json",
                  "sarvam_pages406-601.json"],
        "rule": "section_labels",
        "layer": "tika_bhashyartha_ratnamala",
        "title": "भाष्यार्थरत्नमाला",
    },
    "visvesvara_tirtha": {
        "branch": "origin/ocr-staging/aitereya_upanisad_bh__taries_visvesvara_tirtha",
        "files": ["sarvam_pages6-205.json", "sarvam_pages206-325.json"],
        "rule": "unstructured",
        "layer": "tika_visvesvara_tirtha",
        "title": "विश्वेश्वरतीर्थव्याख्या",
    },
}

DIGITS = {c: str(i) for i, c in enumerate("०१२३४५६७८९")}
COORD = re.compile(r"आ\s*-\s*([\d०-९]+)\s*,\s*अ\s*-\s*([\d०-९]+)\s*,\s*खं\s*-\s*([\d०-९]+)")
BHASHYA_HEAD = re.compile(r"श्रीमन्महैतरेयोपनिषद्भाष्यम्")
# A standalone label line: a short Devanagari phrase alone on its line,
# closed by a dash. Anchored to the whole line so ordinary prose that
# happens to contain a dash cannot match.
SECTION = re.compile(r"^\s*([ऀ-ॿ][ऀ-ॿ\s]{1,24}?)\s*[-–—]\s*$")
KNOWN_SECTIONS = {"उपनिषत्": "tika_upanishat", "भाष्यम्": "tika_bhashya",
                  "टिप्पणी": "tika_bhashyartha_ratnamala", "खण्डार्थः": "tika_khandartha"}

ADHYAYA = ["प्रथमोऽध्यायः", "द्वितीयोऽध्यायः", "तृतीयोऽध्यायः", "चतुर्थोऽध्यायः",
           "पञ्चमोऽध्यायः", "षष्ठोऽध्यायः", "सप्तमोऽध्यायः", "अष्टमोऽध्यायः"]
KHANDA = ["प्रथम: खण्ड:", "द्वितीय: खण्ड:", "तृतीय: खण्ड:", "चतुर्थ: खण्ड:",
          "पञ्चम: खण्ड:", "षष्ट: खण्ड:", "सप्तम: खण्ड:", "अष्टम: खण्ड:"]
ARANYAKA = {2: "द्वितीयारण्यके", 3: "तृतीयारण्यके"}


def num(s: str) -> int:
    return int("".join(DIGITS.get(c, c) for c in s))


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args],
                          capture_output=True, text=True).stdout


def strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html or "")


def dev_only(s: str) -> str:
    return re.sub(r"[^ऀ-ॿ]", "", s or "")


def load_pages(vol: str) -> list[dict]:
    """[{page, text}] for one volume, read off its staging branch."""
    cfg = VOLUMES[vol]
    slug = cfg["branch"].split("ocr-staging/")[1]
    out = []
    for fname in cfg["files"]:
        path = f"data/ocr_staging/{slug}/{fname}"
        blob = git("cat-file", "-p", f"{cfg['branch']}:{path}")
        if not blob.strip():
            raise SystemExit(f"{vol}: could not read {path} from {cfg['branch']}")
        for pg in json.loads(blob).get("pages", []):
            out.append({"page": pg.get("page"), "text": strip_tags(pg.get("html"))})
    out.sort(key=lambda p: p["page"])
    return out


def segment_two_stream(pages: list[dict], cfg: dict) -> tuple[list[dict], dict]:
    """bhagavantaraya. Even PDF pages are the tippani and carry their own
    address; odd pages are the bhasya stream and are set aside."""
    blocks, stats = [], Counter()
    current = None
    for p in pages:
        head = " ".join(p["text"].split())[:120]
        body = p["text"].strip()
        if not dev_only(body) or len(dev_only(body)) < 30:
            stats["blank"] += 1
            continue
        if BHASHYA_HEAD.search(head):
            stats["bhashya_stream"] += 1
            continue
        m = COORD.search(head)
        if m:
            current = (num(m.group(1)), num(m.group(2)), num(m.group(3)))
            stats["addressed"] += 1
        elif p["page"] % 2 == 1:
            # odd page with no bhasya head that OCR'd -- still the bhasya
            # stream by position, which the parity check established.
            stats["bhashya_stream_by_parity"] += 1
            continue
        else:
            stats["carried_forward"] += 1
        if current is None:
            stats["before_first_address"] += 1
            continue
        blocks.append({"aranyaka": current[0], "adhyaya": current[1],
                       "khanda": current[2], "page": p["page"],
                       "layer": cfg["layer"], "text": body})
    return blocks, dict(stats)


def segment_section_labels(pages: list[dict], cfg: dict) -> tuple[list[dict], dict]:
    """ratnamala. A standalone label line opens a run of text belonging to
    that layer, and the run ends at the next label."""
    blocks, stats = [], Counter()
    layer, buf, start = None, [], None
    def flush():
        if layer and buf:
            t = "\n".join(buf).strip()
            if dev_only(t):
                blocks.append({"aranyaka": None, "adhyaya": None, "khanda": None,
                               "page": start, "layer": layer, "text": t})
    for p in pages:
        for line in p["text"].split("\n"):
            s = line.strip()
            if not s:
                continue
            m = SECTION.match(s)
            name = m.group(1).strip() if m else None
            if name in KNOWN_SECTIONS:
                flush()
                layer, buf, start = KNOWN_SECTIONS[name], [], p["page"]
                stats[name] += 1
                continue
            if layer:
                buf.append(s)
    flush()
    return blocks, dict(stats)


def analyse_unstructured(pages: list[dict], cfg: dict) -> tuple[list[dict], dict]:
    stats = Counter()
    for p in pages:
        head = " ".join(p["text"].split())[:120]
        stats["pages"] += 1
        if COORD.search(head):
            stats["coord"] += 1
        if any(SECTION.match(l.strip()) and l.strip().rstrip("-–— ").strip() in KNOWN_SECTIONS
               for l in p["text"].split("\n")):
            stats["section_label"] += 1
    return [], dict(stats)


def address_by_bhashya(blocks: list[dict]) -> dict:
    """Give the ratnamala blocks an address.

    Its own भाष्यम् runs are the same Madhva bhasya the shelf already
    carries as tika_bhashya, whose items state their (aranyaka, adhyaya,
    khanda). So each भाष्यम् block is matched to the shelf item it shares
    the most 12-character shingles with, and the address travels forward
    to the टिप्पणी / उपनिषत् / खण्डार्थः blocks that follow it, which is
    where those blocks actually belong: the volume prints the bhasya for a
    khanda and then comments on it.

    A block that matches nothing above the floor leaves the address alone
    rather than inventing one -- an unaddressed block is reviewable, a
    wrongly addressed one is not.
    """
    items = []
    for d in sorted(TARGET.glob("tika_bhashya/data.json")):
        for x in json.loads(d.read_text())["items"]:
            parts = x["reference"].split(" > ")
            if len(parts) < 6:
                continue
            n = dev_only(x.get("sanskrit_text") or "")
            items.append({"addr": tuple(parts[3:6]),
                          "sh": set(n[i:i + 12] for i in range(len(n) - 12))})
    stats = Counter()
    current = None
    for b in blocks:
        if b["layer"] == "tika_bhashya":
            n = dev_only(b["text"])
            sh = set(n[i:i + 12] for i in range(len(n) - 12))
            if len(sh) >= 20:
                best, score = None, 0.0
                for it in items:
                    if not it["sh"]:
                        continue
                    ov = len(sh & it["sh"]) / len(sh)
                    if ov > score:
                        best, score = it["addr"], ov
                # 0.30 separates a real match from coincidental overlap of
                # shared scriptural quotation; measured on this volume the
                # true matches sit well above it and the rest near zero.
                if best and score >= 0.30:
                    current = best
                    stats["matched"] += 1
                else:
                    stats["below_floor"] += 1
        if current:
            b["aranyaka_name"], b["adhyaya_name"], b["khanda_name"] = current
            stats["addressed"] += 1
        else:
            stats["unaddressed"] += 1
    return dict(stats)


RULES = {"two_stream": segment_two_stream,
         "section_labels": segment_section_labels,
         "unstructured": analyse_unstructured}


def target_coverage() -> dict:
    """What the shelf already holds, as {layer: set of 12-char shingles}."""
    have = {}
    for d in sorted(TARGET.glob("*/data.json")):
        text = "".join(x.get("sanskrit_text") or "" for x in json.loads(d.read_text())["items"])
        n = dev_only(text)
        have[d.parent.name] = set(n[i:i + 12] for i in range(len(n) - 12))
    return have


def novelty(blocks: list[dict], have: dict) -> float:
    """Share of sampled shingles not found in any existing layer."""
    n = dev_only("".join(b["text"] for b in blocks))
    if len(n) < 200:
        return 0.0
    every = set().union(*have.values()) if have else set()
    sample = [n[i:i + 12] for i in range(0, len(n) - 12, 211)]
    hit = sum(1 for s in sample if s in every)
    return 100.0 * (1 - hit / max(1, len(sample)))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", metavar="DIR",
                    help="emit staged JSON per volume into DIR")
    ap.add_argument("--volumes", default=",".join(VOLUMES))
    args = ap.parse_args()

    have = target_coverage()
    print(f"target layers on the shelf: {', '.join(sorted(have))}\n")

    for vol in args.volumes.split(","):
        cfg = VOLUMES[vol]
        pages = load_pages(vol)
        blocks, stats = RULES[cfg["rule"]](pages, cfg)
        addr_stats = address_by_bhashya(blocks) if cfg["rule"] == "section_labels" else None
        chars = sum(len(dev_only(b["text"])) for b in blocks)
        print(f"== {vol}  ({cfg['rule']})")
        print(f"   pages read      : {len(pages)}")
        print(f"   page accounting : {stats}")
        print(f"   blocks          : {len(blocks)}   devanagari {chars:,}")
        if blocks:
            addressed = [b for b in blocks if b["adhyaya"] is not None]
            if addressed:
                spans = OrderedDict()
                for b in addressed:
                    spans.setdefault((b["aranyaka"], b["adhyaya"], b["khanda"]), []).append(b["page"])
                print(f"   addressed spans : {len(spans)} khaṇḍas")
            by_layer = Counter(b["layer"] for b in blocks)
            print(f"   by layer        : {dict(by_layer)}")
            print(f"   new vs shelf    : {novelty(blocks, have):.1f}%")
            if addr_stats:
                print(f"   addressing      : {addr_stats}")
                named = {b["layer"]: 0 for b in blocks}
                for b in blocks:
                    if b.get("adhyaya_name"):
                        named[b["layer"]] += 1
                print(f"   addressed/layer : {named}")
        if cfg["rule"] == "unstructured":
            print("   NOT SEGMENTED — no coordinate running head and no section\n"
                  "   labels. Needs a third rule before it can be addressed.")
        print()

        if args.write and blocks:
            out = Path(args.write)
            out.mkdir(parents=True, exist_ok=True)
            payload = {
                "_readme": ["Segmented from the staged Sarvam OCR by "
                            "tools/aitareya/segment.py. NOT merged into the corpus -- "
                            "review in admin/ocr-review.html first."],
                "work": vol, "source_branch": cfg["branch"], "rule": cfg["rule"],
                "target": str(TARGET.relative_to(ROOT)), "title": cfg["title"],
                "page_accounting": stats, "blocks": blocks,
            }
            (out / f"{vol}_segmented.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=1) + "\n")
            print(f"   wrote {out / (vol + '_segmented.json')}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
