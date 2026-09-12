#!/usr/bin/env python3
"""Import the four small vyakarana corpora from ashtadhyayi-com/data.

Source: https://github.com/ashtadhyayi-com/data (the data behind
ashtadhyayi.com). Its README: "You are free to use this data in your own
projects provided that appropriate credits are mentioned" — credits are
carried per-file in the attribution object below and rendered in each
corpus page's footer.

Corpora -> dge/data/vedanga/vyakarana/<slug>/data.json:
  fit             -> phitsutra        (Phit-sutras of Shantanava: svara rules)
  ganapath        -> ganapatha        (ganas w/ Ashtadhyayi sutra + members)
  linganushasanam -> linganushasana   (gender rules by adhikara)
  unaadi          -> unadi            (Unadi-sutras w/ pratyaya + vritti;
                                       id = pada*1000+n, so उ० ४-९८ = 4098)

Usage: python3 tools/vyakarana/import_ashtadhyayi_corpora.py [--src DIR]
(--src defaults to a local clone of ashtadhyayi-com/data)
"""
import argparse, datetime, json, os, subprocess, sys

MAP = [
    ("fit", "phitsutra", "फिट्सूत्राणि", "शान्तनवाचार्यः"),
    ("ganapath", "ganapatha", "गणपाठः", ""),
    ("linganushasanam", "linganushasana", "लिङ्गानुशासनम्", "पाणिनिः"),
    ("unaadi", "unadi", "उणादिसूत्राणि", ""),
]
OUT = "dge/data/vedanga/vyakarana"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="/home/user/ashtadhyayi-com/data")
    args = ap.parse_args()
    try:
        sha = subprocess.check_output(
            ["git", "-C", args.src, "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        sha = "unknown"
    today = datetime.date.today().isoformat()
    for src_dir, slug, title, author in MAP:
        path = os.path.join(args.src, src_dir, "data.txt")
        doc = json.load(open(path, encoding="utf-8"))
        items = doc.get("data") or []
        out = {
            "schema": "vyakarana_corpus_v1",
            "corpus": slug,
            "title": title,
            "author": author,
            "attribution": {
                "source_name": "ashtadhyayi.com",
                "source_url": f"https://github.com/ashtadhyayi-com/data/blob/master/{src_dir}/data.txt",
                "source_commit": sha,
                "accessed_date": today,
                "license_notes": "Free to use with credits, per the source "
                                 "repository's README; attribution rendered "
                                 "on the corpus page.",
            },
            "count": len(items),
            "items": items,
        }
        dst = os.path.join(OUT, slug)
        os.makedirs(dst, exist_ok=True)
        with open(os.path.join(dst, "data.json"), "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print(f"{slug}: {len(items)} items -> {dst}/data.json")


if __name__ == "__main__":
    sys.exit(main())
