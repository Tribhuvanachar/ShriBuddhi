#!/usr/bin/env python3
"""Attach each adhikara heading's ORIGIN SUTRA reference to the sutrapatha.

The source's "ad" column carries, per "##"-joined adhikara, the
adhyaya.pada.sutra of the rule that first states it ("आकडारात् एका
संज्ञा$1$4$1##कारके$1$4$23"). The import used to store that raw string;
tools/clean_adhikara_suffix.py then stripped the references as display
noise, leaving `adhikara` a clean display string. This tool brings the
references back as STRUCTURE -- a parallel `adhikara_refs` array of
[text, our_sutra_id] pairs -- so the reader can jump to the sutra where an
adhikara begins.

Two alignment problems, both handled by per-pada text alignment (the
realign_sutra_enrichment.py technique), never by trusting sutra numbers:

  1. WHICH of our sutras carries a given source row's "ad" value -- the
     source's numbering disagrees with ours inside several padas.
  2. WHAT our id is for the reference itself ("$1$4$1" is in source
     numbering too). A full source-id -> our-id map is built from the same
     alignment across every pada and each reference is remapped through it.
     A reference whose source sutra aligns to nothing of ours is dropped
     from adhikara_refs (the display text keeps the heading; there is just
     nothing to link to), and reported.

The display string `adhikara` itself is not touched.

    python3 tools/add_adhikara_refs.py /path/to/ashtadhyayi-com-data-clone           # report
    python3 tools/add_adhikara_refs.py /path/to/ashtadhyayi-com-data-clone --apply   # write

Rebuild the reader's index afterwards:
    python3 tools/build_sutra_index.py
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))
from build_kaumudi_order import align  # same consonant-bag aligner

SUTRAPATHA_PATH = REPO_ROOT / "dge/data/vedanga/vyakarana/ashtadhyayi/sutrapatha/data.json"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    apply_it = "--apply" in sys.argv
    if len(args) != 1:
        print(__doc__)
        return 1
    src = json.loads((Path(args[0]) / "sutraani/data.txt").read_text(encoding="utf-8"))["data"]
    doc = json.loads(SUTRAPATHA_PATH.read_text(encoding="utf-8"))
    ours = doc["items"]

    ours_by_pada = defaultdict(list)
    for it in ours:
        a, p, _ = it["id"].split(".")
        ours_by_pada[a + "." + p].append(it)
    theirs_by_pada = defaultdict(list)
    for r in src:
        theirs_by_pada[r["a"] + "." + r["p"]].append(r)

    # One text-alignment pass gives both maps.
    src_to_ours = {}           # "1.4.1" (source numbering) -> our id
    ad_of_our = {}             # our id -> source "ad" string
    unaligned_src = []         # source rows the aligner paired with nothing
    for pada in ours_by_pada:
        o = ours_by_pada[pada]
        t = sorted(theirs_by_pada.get(pada, []), key=lambda r: int(r["n"]))
        for i, j in align([x["sanskrit_text"] for x in o], [x["s"] for x in t]):
            if j is not None and i is None:
                unaligned_src.append((pada, t[j]))
                continue
            if i is None or j is None:
                continue
            row = t[j]
            src_to_ours[f"{row['a']}.{row['p']}.{row['n']}"] = o[i]["id"]
            if (row.get("ad") or "").strip():
                ad_of_our[o[i]["id"]] = row["ad"].strip()

    # A source row the aligner left unpaired is usually a sutra the source
    # counts separately where our text merges it into a neighbour (their
    # 2.1.11 विभाषा vs our 2.1.11 विभाषाऽपपरि...). If exactly one of our
    # sutras in the same pada CONTAINS the source row's text, that is the
    # merge target and references to the source row resolve there.
    import re as _re
    import unicodedata as _ud
    def _norm(s):
        s = _ud.normalize("NFC", s or "")
        return _re.sub(r"[^क-हा-्ंःअ-औ]", "", s)
    for pada, row in unaligned_src:
        needle = _norm(row["s"])
        if len(needle) < 3:
            continue
        hosts = [x["id"] for x in ours_by_pada[pada] if needle in _norm(x["sanskrit_text"])]
        if len(hosts) == 1:
            src_to_ours.setdefault(f"{row['a']}.{row['p']}.{row['n']}", hosts[0])

    changed = ref_ok = ref_dropped = 0
    dropped_examples = []
    for it in ours:
        ad = ad_of_our.get(it["id"])
        if not ad:
            continue
        refs = []
        for seg in ad.split("##"):
            parts = seg.split("$")
            text = parts[0].strip()
            if not text:
                continue
            our_ref = None
            if len(parts) >= 4 and all(p.isdigit() for p in parts[1:4]):
                our_ref = src_to_ours.get(f"{int(parts[1])}.{int(parts[2])}.{int(parts[3])}")
            if our_ref:
                refs.append([text, our_ref])
                ref_ok += 1
            else:
                refs.append([text, None])
                ref_dropped += 1
                if len(dropped_examples) < 6:
                    dropped_examples.append((it["id"], seg))
        if refs:
            changed += 1
            if apply_it:
                it["adhikara_refs"] = refs

    print(f"sutras with adhikara refs: {changed}; "
          f"references resolved: {ref_ok}, unresolved (kept without a link): {ref_dropped}")
    for ex in dropped_examples:
        print("  unresolved:", ex)
    if apply_it:
        SUTRAPATHA_PATH.write_text(
            json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"wrote {SUTRAPATHA_PATH}")
    else:
        print("report only -- rerun with --apply to write")
    return 0


if __name__ == "__main__":
    sys.exit(main())
