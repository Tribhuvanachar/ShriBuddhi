#!/usr/bin/env python3
"""
scl_crosscheck_dhatu.py -- does Saṃsādhanī recognise the verb forms we generate?

Our conjugation tables (data/vedanga/vyakarana/prakriya/<gana>/<code>.json) come
from vidyut-prakriya. Saṃsādhanī is an independent implementation of the same
grammar, so asking its morphological analyser about a sample of our forms is a
cheap second opinion: a form it does not recognise, or reads as a different
lakāra/person/number, is worth a look by a person (one of the two is wrong, or
the root has a variant the other does not model).

REPORT ONLY. It changes no data. Output: a summary on stdout and, with --report,
the disagreements as JSON.

It calls a university's server, so it is throttled (1 request/s), capped
(--sample, default 60 roots x 3 forms) and meant to be run by hand, not on a schedule.
Every answer is cached in _dump/.scl_cache.json so a re-run asks nothing twice.

    python3 tools/scl_crosscheck_dhatu.py --sample 60 --report _dump/scl_dhatu.json
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import random
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MORPH = "https://sanskrit.uohyd.ac.in/cgi-bin/scl/MT/prog/morph/morph.cgi"
LAKARA = {"Lat": "लट्", "Lit": "लिट्", "Lot": "लोट्", "Lan": "लङ्", "VidhiLin": "विधिलिङ्",
          "AshirLin": "आशीर्लिङ्", "Lut": "लुट्", "Lrt": "लृट्", "Lun": "लुङ्", "Lrn": "लृङ्"}
# forms keys look like "Lat.00": person (0 = prathama) . number (0 = eka)
PURUSHA = {"0": "प्र", "1": "म", "2": "उ"}
VACANA = {"0": "एक", "1": "द्वि", "2": "बहु"}
CACHE = os.path.join(ROOT, "_dump", ".scl_cache.json")


def ask(form, cache):
    if form in cache:
        return cache[form]
    q = urllib.parse.urlencode({"morfword": form, "encoding": "Unicode", "outencoding": "DEV", "mode": "json"})
    try:
        with urllib.request.urlopen(urllib.request.Request(MORPH + "?" + q, headers={"User-Agent": "sarvamula-crosscheck"}), timeout=30) as r:
            body = r.read().decode("utf-8", "replace")
        try:
            res = json.loads(body)
            res = res if isinstance(res, list) else []
        except ValueError:
            res = []
    except Exception:
        return None
    cache[form] = res
    time.sleep(1.0)
    return res


def parse_ans(s):
    import re
    return dict(re.findall(r"\{([^:{}]+):([^{}]*)\}", s or ""))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--sample", type=int, default=60, help="roots to sample")
    ap.add_argument("--keys", default="Lat.00,Lit.00,Lot.00", help="which forms of each root to check")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--report", default="")
    a = ap.parse_args(argv)

    files = sorted(glob.glob(os.path.join(ROOT, "data/vedanga/vyakarana/prakriya/*/*.json")))
    random.Random(a.seed).shuffle(files)
    cache = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}
    keys = a.keys.split(",")
    checked = agree = unknown = different = 0
    bad = []
    for f in files[: a.sample]:
        d = json.load(open(f, encoding="utf-8"))
        for k in keys:
            forms = (d.get("forms") or {}).get(k) or []
            if not forms:
                continue
            form = forms[0]
            want = {"लकारः": LAKARA[k.split(".")[0]], "पुरुषः": PURUSHA[k[-2]], "वचनम्": VACANA[k[-1]]}
            res = ask(form, cache)
            if res is None:
                continue
            checked += 1
            verbs = [r for r in res if r.get("APP") == "verb"]
            if not res:
                unknown += 1
                bad.append({"code": d["code"], "dhatu": d["dhatu"], "key": k, "form": form, "scl": "not recognised"})
                continue
            ok = False
            for r in verbs:
                an = parse_ans(r.get("ANS"))
                if all(an.get(x) == y for x, y in want.items()):
                    ok = True
                    break
            if ok:
                agree += 1
            else:
                different += 1
                bad.append({"code": d["code"], "dhatu": d["dhatu"], "key": k, "form": form,
                            "scl": [parse_ans(r.get("ANS")) for r in verbs][:3] or "no verb reading"})
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
    print("checked %d forms: agree %d (%.0f%%), SCL reads differently %d, SCL does not recognise %d"
          % (checked, agree, 100 * agree / max(1, checked), different, unknown))
    for b in bad[:10]:
        print("  ", b["code"], b["dhatu"], b["key"], b["form"], "->", json.dumps(b["scl"], ensure_ascii=False)[:100])
    if a.report:
        os.makedirs(os.path.dirname(os.path.abspath(a.report)), exist_ok=True)
        json.dump({"checked": checked, "agree": agree, "different": different, "unknown": unknown, "cases": bad},
                  open(a.report, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
