#!/usr/bin/env python3
"""
merge_mula.py -- reconcile the two independent readings of the HKS mula.

There are two, and they were made in completely different ways:

  * `data/.../harikathamrutasara/data.json` -- 947 padyas lifted from the
    Shri HKS Android app's compiled string resources. Clean text, no OCR
    error in it at all, because it was never scanned.
  * the 127-page printed mula, read by Vision and Sarvam and adjudicated by
    Gemini, segmented by tools/hks/segment_mula.py -- 1,009 padyas.

They agree exactly on the padya count for 22 of the 33 sandhis. Two sources
that share no method and no lineage agreeing that closely is the strongest
evidence either of them can offer, so where they agree nothing needs doing.

WHERE THEY DIFFER, this merges in ONE direction only and only on hard
evidence. Every sandhi of the HKS closes on Jagannatha Dasa's ankita,
ಜಗನ್ನಾಥವಿಠಲ. That gives a completeness test the text applies to itself: a
sandhi whose last padya carries the ankita is whole, and one that stops
short of it is not.

By that test the app is missing sandhi 24 ENTIRELY -- 0 padyas -- while the
scan has all 63 and ends on the ankita. So sandhi 24 comes from the scan.

Everything else that differs is REPORTED AND LEFT ALONE. Sandhis 18, 19, 20
and 25 disagree by more than a padya, and the boundary between 24 and 25 is
the likely reason, but "likely" is not a reason to overwrite a clean reading
with a scanned one. Those stay for a person to settle.

    python3 tools/hks/merge_mula.py --segmented <file> --write
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re

WORK = "data/Tattvavada/Itara/DasaSahitya/harikathamrutasara/data.json"
ANKITA = ("ಜಗನ್ನಾಥವಿಠಲ", "ಜಗನ್ನಾಥವಿಠ್ಠಲ")


def bare(t: str) -> str:
    return re.sub(r"[\s|।॥]+", "", str(t or ""))


def ends_on_ankita(padyas, field) -> bool:
    return bool(padyas) and any(a in bare(padyas[-1][field]) for a in ANKITA)


def load(root: str, segmented: str):
    cur = json.load(open(os.path.join(root, WORK), encoding="utf-8"))
    seg = json.load(open(segmented, encoding="utf-8"))
    by_cur = collections.defaultdict(list)
    for it in cur["items"]:
        by_cur[it["sandhi_number"]].append(it)
    by_seg = {s["number"]: s for s in seg["sandhis"]}
    return cur, by_cur, by_seg


def plan(by_cur, by_seg) -> dict:
    """Which sandhis to take from the scan, and which merely to report."""
    take, report = [], []
    for n in range(1, 34):
        cur = by_cur.get(n) or []
        s = by_seg.get(n)
        scan = (s or {}).get("padyas") or []
        if len(cur) == len(scan) and cur:
            continue
        cur_ok = ends_on_ankita(cur, "sa")
        scan_ok = ends_on_ankita(scan, "text")
        if not cur and scan_ok:
            take.append(n)
            report.append("sandhi %2d: absent from the app, %d padyas in the scan "
                          "ending on the ankita -- taken from the scan" % (n, len(scan)))
        else:
            report.append("sandhi %2d: app %d padya(s)%s, scan %d%s -- left alone"
                          % (n, len(cur), "" if cur_ok else " (no ankita)",
                             len(scan), "" if scan_ok else " (no ankita)"))
    return {"take": take, "report": report}


def build(cur, by_cur, by_seg, take) -> list:
    """The merged item list, in sandhi then padya order."""
    out = []
    for n in range(1, 34):
        if n in take:
            s = by_seg[n]
            title = "%s ಸಂಧಿ" % s["title"].strip()
            for p in s["padyas"]:
                out.append({
                    "id": "hks-%d-%d" % (n, p["number"]),
                    "sa": p["text"],
                    "sandhi_number": n,
                    "sandhi_title": title,
                    # Marked because it is not the same provenance as its
                    # neighbours: this one was read off a scan, and a reader
                    # comparing editions is entitled to know which is which.
                    "text_source": "printed mula, OCR adjudicated",
                    "source_page": p["page"],
                })
        else:
            out.extend(by_cur.get(n) or [])
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 2)[1])
    ap.add_argument("--segmented", required=True)
    ap.add_argument("--root", default=".")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)

    cur, by_cur, by_seg = load(args.root, args.segmented)
    p = plan(by_cur, by_seg)

    print("app: %d padyas   scan: %d padyas"
          % (sum(len(v) for v in by_cur.values()),
             sum(len(s["padyas"]) for s in by_seg.values())))
    print("sandhis agreeing exactly: %d of 33\n"
          % sum(1 for n in range(1, 34)
                if by_cur.get(n) and len(by_cur[n]) == len((by_seg.get(n) or {}).get("padyas") or [])))
    for line in p["report"]:
        print("  " + line)

    items = build(cur, by_cur, by_seg, p["take"])
    print("\nmerged: %d padyas (%+d)" % (len(items), len(items) - len(cur["items"])))

    if not args.write:
        print("\nnot written -- pass --write")
        return 0

    cur["items"] = items
    meta = cur.setdefault("source_meta", {})
    meta["merged_from_scan"] = {
        "sandhis": p["take"],
        "why": ("absent from the Android app's string resources; present and "
                "complete in the printed mula, ending on the ankita"),
        "tool": "tools/hks/merge_mula.py",
    }
    path = os.path.join(args.root, WORK)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cur, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("wrote %s" % WORK)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
