#!/usr/bin/env python3
"""
check_indowordnet.py -- has IndoWordNet changed since data/_wordnet/ was built?

Three independent signals, because each can move without the others:

  dump     sha256 of the pyiwn data dump tools/build_wordnet.py builds from.
           A different hash means a rebuild would produce different data.
  live     the Sanskrit row of CFILT's own statistics endpoint
           (cfilt.iitb.ac.in/indowordnet/currentStatistics?langno=13): counts of
           noun / adjective / verb / adverb synsets and the total. It moves when
           CFILT edits the wordnet, which can be well before pyiwn re-packages it.
  pyiwn    the latest pyiwn release on PyPI (the dump's distributor).

State lives in tools/wordnet_source.json (not in data/, so it never ships).

    python3 tools/check_indowordnet.py            # report; exit 0 always
    python3 tools/check_indowordnet.py --write    # also record the current values
    python3 tools/check_indowordnet.py --github-output $GITHUB_OUTPUT

Outputs (stdout / GITHUB_OUTPUT): dump_changed, live_changed, pyiwn_changed, changed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "tools", "wordnet_source.json")
LIVE_URL = "https://www.cfilt.iitb.ac.in/indowordnet/currentStatistics?langno=13"
PYPI_URL = "https://pypi.org/pypi/pyiwn/json"


def _get(url, timeout=120):
    req = urllib.request.Request(url, headers={"User-Agent": "sarvamula-wordnet-watch"})
    return urllib.request.urlopen(req, timeout=timeout)


def dump_sha256():
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import build_wordnet
    h = hashlib.sha256()
    with _get(build_wordnet.DATA_URL, timeout=600) as r:
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def live_stats():
    with _get(LIVE_URL) as r:
        raw = json.loads(r.read().decode("utf-8"))
    row = json.loads(raw) if isinstance(raw, str) else raw
    return {"counts": row[1:], "name": row[0]}


def pyiwn_version():
    with _get(PYPI_URL) as r:
        return json.load(r)["info"]["version"]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--write", action="store_true", help="record the current values as the baseline")
    ap.add_argument("--github-output", help="append key=value lines to this file")
    ap.add_argument("--skip-dump", action="store_true", help="do not download the 30 MB dump")
    a = ap.parse_args(argv)

    old = json.load(open(STATE, encoding="utf-8")) if os.path.exists(STATE) else {}
    new = {"live_counts": live_stats()["counts"], "pyiwn_version": pyiwn_version()}
    new["dump_sha256"] = old.get("dump_sha256", "") if a.skip_dump else dump_sha256()

    res = {
        "dump_changed": bool(old) and new["dump_sha256"] != old.get("dump_sha256"),
        "live_changed": bool(old) and new["live_counts"] != old.get("live_counts"),
        "pyiwn_changed": bool(old) and new["pyiwn_version"] != old.get("pyiwn_version"),
    }
    res["changed"] = any(res.values())
    print("recorded:", json.dumps({k: old.get(k) for k in new}, ensure_ascii=False))
    print("current :", json.dumps(new, ensure_ascii=False))
    for k, v in res.items():
        print("%s=%s" % (k, str(v).lower()))
    if a.github_output:
        with open(a.github_output, "a", encoding="utf-8") as fh:
            for k, v in res.items():
                fh.write("%s=%s\n" % (k, str(v).lower()))
    if a.write:
        with open(STATE, "w", encoding="utf-8") as fh:
            json.dump(new, fh, indent=1, sort_keys=True)
            fh.write("\n")
        print("wrote", os.path.relpath(STATE, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
