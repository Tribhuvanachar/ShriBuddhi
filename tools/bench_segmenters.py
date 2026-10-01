#!/usr/bin/env python3
"""
bench_segmenters.py -- which padaccheda engine is worth building into the corpus?

Scores word segmentation against the human padaccheda layers the Kavya package
ships (data/kavya_alankara/<work>/padaccheda, a word-by-word list made by an
editor). Three engines, same verses:

  ours    tools/padaccheda.py Segmenter (per written token, corpus vocabulary)
  cheda   Vidyut's whole-verse segmenter (vidyut.cheda.Chedaka)
  scl     Saṃsādhanī's sandhi splitter over HTTP (sanskrit.uohyd.ac.in); a
          small sample only, throttled, because it is a university's server.

METRIC. Per verse, the human list and the engine's output are each reduced to a
bag of words (final visarga/s/r written alike, avagraha expanded, compound
hyphens dropped) and scored by F1 of the bags; the headline numbers are the
mean F1 and the share of verses the engine got exactly right. This is a
deliberately forgiving metric -- it does not penalise an engine for splitting a
compound the editor left whole -- so read it as an upper bound, and as a fair
way to rank engines against each other.

    python3 tools/bench_segmenters.py --works raghuvamsha,kumarasambhava --per-work 150
    python3 tools/bench_segmenters.py --scl 40
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
DATA = os.path.join(ROOT, "data", "kavya_alankara")

FINALS = str.maketrans({"स": "ः", "र": "ः", "ो": "ः"})


def norm(w):
    w = w.replace("ऽ", "अ").replace("्", "्")
    w = re.sub(r"[।॥,;:\-‑‌‍]", "", w).strip()
    if w.endswith("स्") or w.endswith("र्"):
        w = w[:-2] + "ः"
    return w


def bag(words):
    return [norm(w) for w in words if norm(w)]


def f1(a, b):
    from collections import Counter
    ca, cb = Counter(a), Counter(b)
    hit = sum((ca & cb).values())
    if not hit:
        return 0.0
    p, r = hit / max(1, sum(ca.values())), hit / max(1, sum(cb.values()))
    return 2 * p * r / (p + r)


def verses(work, limit):
    pp = os.path.join(DATA, work, "padaccheda", "data.json")
    mp = os.path.join(DATA, work, "mula", "data.json")
    if not (os.path.exists(pp) and os.path.exists(mp)):
        return []
    P = json.load(open(pp, encoding="utf-8"))
    M = json.load(open(mp, encoding="utf-8"))
    text = {s["id"]: s.get("sanskrit_text") or "" for it in M["items"] for s in it.get("shlokas", [])}
    out = []
    for it in P["items"]:
        for s in it.get("shlokas", []):
            words = [x.get("w", "") for x in s.get("padaccheda") or []]
            t = text.get(s["id"], "")
            if words and t:
                out.append((work + ":" + s["id"], t, words))
    step = max(1, len(out) // max(1, limit))
    return out[::step][:limit]


def clean(t):
    return re.sub(r"[।॥\n]", " ", t)


def run_cheda(items, data="/tmp/vidyut_data"):
    from vidyut import cheda
    from vidyut.lipi import Scheme, transliterate
    ck = cheda.Chedaka(data)
    def seg(t):
        toks = ck.run(transliterate(clean(t), Scheme.Devanagari, Scheme.Slp1))
        return [transliterate(x.text, Scheme.Slp1, Scheme.Devanagari) for x in toks]
    return [seg(t) for _, t, _ in items]


def run_ours(items):
    import build_padaccheda as bp
    from padaccheda import Segmenter, strip_punct, is_devanagari
    vocab, _ = bp.load_vocab()
    stems, avyaya, inflected, verbs = bp.load_morphology()
    seg = Segmenter(vocab, {}, stems, avyaya, inflected, verbs)
    res = []
    for _, t, _ in items:
        words = []
        for tok in clean(t).split():
            tok = strip_punct(tok)
            if not tok or not is_devanagari(tok):
                continue
            got = seg.confident_split(tok)
            words.extend([w for w, _ in got] if got else [tok])
        res.append(words)
    return res


SCL_HOSTED = "https://sanskrit.uohyd.ac.in/cgi-bin/scl"
SPLITTER = "/MT/prog/sandhi_splitter/sandhi_splitter.cgi"


def run_scl(items, pause=1.0, base=SCL_HOSTED):
    res = []
    for _, t, _ in items:
        q = urllib.parse.urlencode({"word": "+".join(clean(t).split()), "encoding": "Unicode",
                                    "outencoding": "D", "mode": "sent", "disp_mode": "json"})
        try:
            with urllib.request.urlopen(urllib.request.Request(base.rstrip("/") + SPLITTER + "?" + q, headers={"User-Agent": "sarvamula-bench"}), timeout=30) as r:
                body = r.read().decode("utf-8", "replace")
            seg = json.loads(body)["segmentation"][0]
            res.append([w for w in re.split(r"[\s\-]+", seg.lstrip("?")) if w])
        except Exception:
            res.append([])
        time.sleep(pause)
    return res


def score(name, items, outs):
    fs = [f1(bag(o), bag(h)) for o, (_, _, h) in zip(outs, items)]
    exact = sum(1 for o, (_, _, h) in zip(outs, items) if bag(o) == bag(h))
    print("%-6s verses %4d   mean F1 %.3f   exactly right %4.1f%%" % (name, len(items), sum(fs) / len(fs), 100 * exact / len(items)))
    return fs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--works", default="raghuvamsha,kumarasambhava,kiratarjuniya,shishupalavadha,meghaduta,bhattikavya")
    ap.add_argument("--per-work", type=int, default=100)
    ap.add_argument("--scl", type=int, default=0, help="also score SCL on this many verses (throttled)")
    ap.add_argument("--scl-base", default=SCL_HOSTED, help="SCL CGI base; a local container is http://localhost:8080/cgi-bin/scl")
    ap.add_argument("--scl-pause", type=float, default=1.0, help="seconds between requests (0 is fine for your own container)")
    a = ap.parse_args(argv)
    items = []
    for w in a.works.split(","):
        items += verses(w.strip(), a.per_work)
    print("%d verses from %s" % (len(items), a.works))
    score("cheda", items, run_cheda(items))
    score("ours", items, run_ours(items))
    if a.scl:
        sub = items[:: max(1, len(items) // a.scl)][: a.scl]
        print("-- same %d verses for every engine --" % len(sub))
        score("cheda", sub, run_cheda(sub))
        score("ours", sub, run_ours(sub))
        score("scl", sub, run_scl(sub, a.scl_pause, a.scl_base))
    return 0


if __name__ == "__main__":
    sys.exit(main())
