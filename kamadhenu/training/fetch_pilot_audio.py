#!/usr/bin/env python3
"""Fetch the pilot set's source recordings (Google Drive, public folders) into kamadhenu_dataset/incoming_audio/.

    python3 kamadhenu/training/fetch_pilot_audio.py [--manifest kamadhenu/data/pilot/manifest.jsonl] [--workers 4]

The audio is never committed (kamadhenu_dataset/.gitignore); this re-downloads exactly the files the pilot names,
using the Drive ids in kamadhenu_dataset/drive_manifest.json. Idempotent: an existing file of plausible size is kept.
Exit 1 if any file is still missing (the exporter would then report it as a problem too)."""
import argparse, json, os, sys, time, urllib.request, concurrent.futures as cf
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="kamadhenu/data/pilot/manifest.jsonl")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args(argv)
    items = json.load(open(ROOT / "kamadhenu_dataset/drive_manifest.json", encoding="utf-8"))["files"]
    items = items if isinstance(items, list) else list(items.values())
    by_key = {}
    for x in items:
        by_key.setdefault((x["folder"].split("/")[0], x["name"]), x)
    rows = [json.loads(l) for l in open(ROOT / a.manifest, encoding="utf-8")]

    def get(r):
        p = ROOT / r["audio"]
        if p.exists() and p.stat().st_size > 1000:
            return "have", r["audio"]
        parts = r["audio"].split("/")
        it = by_key.get((parts[3], parts[-1])) or next((x for x in items if x["name"] == parts[-1]), None)
        if not it:
            return "not in drive_manifest", r["audio"]
        p.parent.mkdir(parents=True, exist_ok=True)
        err = ""
        for attempt in range(3):
            try:
                rq = urllib.request.Request(it["download_url"], headers={"User-Agent": "Mozilla/5.0"})
                b = urllib.request.urlopen(rq, timeout=120).read()
                if b[:5] == b"<!DOC" or len(b) < 1000:
                    raise RuntimeError(f"html/short response ({len(b)} bytes)")
                p.write_bytes(b)
                return "ok", r["audio"]
            except Exception as e:  # noqa: BLE001
                err = str(e); time.sleep(2 * (attempt + 1))
        return "fail " + err, r["audio"]

    t0 = time.time()
    with cf.ThreadPoolExecutor(a.workers) as ex:
        res = list(ex.map(get, rows))
    c = Counter(s.split(" ")[0] for s, _ in res)
    print(f"{len(rows)} pilot files: {dict(c)} in {time.time() - t0:.0f}s")
    bad = [(s, p) for s, p in res if not s.startswith(("ok", "have"))]
    for s, p in bad:
        print("  ", s, p)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
