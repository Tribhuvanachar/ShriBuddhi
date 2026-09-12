#!/usr/bin/env python3
"""Does each pilot recording actually say its verse? (Kamadhenu, 7 Sep 2026 — the lead: "I don't want our training
to happen on some audio whose text is not known correctly.")

    python3 kamadhenu/training/verify_pilot_transcripts.py [--manifest kamadhenu/data/pilot/manifest.jsonl]
        [--model small] [--limit N] [--workers 4]

For every pilot file: local Whisper (faster-whisper, CPU, int8 — no API, no cost) transcribes the audio in Devanagari;
the expected verse text is normalised the same way (accents, daṇḍas, digits, spaces removed) and compared:
    cer            character error rate of ASR vs expected (Levenshtein / expected length) — Whisper's Sanskrit is
                   rough, so this is read relatively: the distribution over the set, not an absolute bar
    length_ratio   ASR characters / expected characters — a file that repeats words or halves runs long (> 1.5)
    self_repeat    share of the ASR text's 6-grams that occur more than once — the pattern in the Gītā takes
                   ("Māmakāḥ / Māmakāḥ / Pāṇḍavāścaiva / …") shows up here even when Whisper misspells everything
    coverage       fraction of the expected verse's 4-grams found in the ASR text (fuzzy: after normalisation)
Verdicts: ok · suspect_repetition (length_ratio > 1.5 or self_repeat > 0.35) · suspect_mismatch (coverage < 0.15 and
cer > 0.85) · short (ASR much shorter than the verse). Writes kamadhenu/reports/pilot_transcript_check.{json,md}.
The exporter (export_f5_dataset.py --require-verified) then refuses anything but `ok`.
"""
import argparse, json, re, sys, time, unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from kamadhenu_text import model_text  # noqa: E402

STRIP = re.compile(r"[\s।॥|0-9०-९.,;:!?'\"()\[\]\-–—]+")
ACCENTS = "".join(chr(c) for c in (0x0951, 0x0952, 0x0953, 0x0954, 0x1CD0, 0x1CD1, 0x1CD2, 0x1CDA, 0x1CDD, 0x200B, 0x200C, 0x200D, 0xFEFF))


try:
    from indic_transliteration import sanscript
except Exception:  # noqa: BLE001
    sanscript = None


def to_latin(t):
    """Whisper writes Sanskrit in a Latin, IAST-like spelling; the expected Devanagari is transliterated to IAST so
    both sides are compared as plain lowercase ASCII letters (diacritics and marks dropped, digits/punctuation gone)."""
    t = unicodedata.normalize("NFC", str(t or ""))
    t = "".join(c for c in t if c not in ACCENTS)
    if sanscript and re.search(r"[ऀ-ॿ]", t):
        try: t = sanscript.transliterate(t, sanscript.DEVANAGARI, sanscript.IAST)
        except Exception: pass  # noqa: BLE001
    t = unicodedata.normalize("NFD", t.lower())
    return re.sub(r"[^a-z]+", "", t)


def norm(t):
    return to_latin(t)


def levenshtein(a, b):
    if not a: return len(b)
    if not b: return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def ngrams(s, n):
    return [s[i:i + n] for i in range(max(0, len(s) - n + 1))]


def measure(expected, asr):
    e, a = norm(expected), norm(asr)
    cer = levenshtein(a, e) / max(1, len(e))
    ratio = len(a) / max(1, len(e))
    g6 = ngrams(a, 6); rep = 0.0
    if g6:
        from collections import Counter
        c = Counter(g6); rep = sum(v for v in c.values() if v > 1) / len(g6)
    e4 = set(ngrams(e, 4)); a4 = set(ngrams(a, 4))
    cov = len(e4 & a4) / max(1, len(e4))
    if ratio > 1.5 or rep > 0.35: verdict = "suspect_repetition"
    elif ratio < 0.45: verdict = "short"
    elif cov < 0.15 and cer > 0.85: verdict = "suspect_mismatch"
    else: verdict = "ok"
    return {"cer": round(cer, 3), "length_ratio": round(ratio, 2), "self_repeat": round(rep, 3), "coverage": round(cov, 3), "verdict": verdict,
            "expected_chars": len(e), "asr_chars": len(a)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="kamadhenu/data/pilot/manifest.jsonl"); ap.add_argument("--model", default="small")
    ap.add_argument("--limit", type=int, default=None); ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--out", default="kamadhenu/reports/pilot_transcript_check")
    ap.add_argument("--shard", default=None, help="i/n: check only every n-th file starting at i (0-based), for parallel runners")
    ap.add_argument("--merge", nargs="*", default=None, help="merge these shard JSON reports into --out instead of transcribing")
    ap.add_argument("--crossmatch", metavar="REPORT_JSON", nargs="+", default=None,
                    help="instead of transcribing: match every ASR in these reports against all verses of its work "
                         "(several reports, e.g. Whisper small and medium, are combined per recording)")
    ap.add_argument("--text-index", default="kamadhenu_dataset/text_index.json")
    a = ap.parse_args(argv)
    if a.crossmatch:
        units = json.load(open(ROOT / a.text_index, encoding="utf-8"))["units"]
        runs = [crossmatch(json.load(open(f, encoding="utf-8"))["rows"], units) for f in a.crossmatch]
        rep = write_crossmatch(combine_crossmatch(runs) if len(runs) > 1 else runs[0], a.out, " + ".join(a.crossmatch))
        print(json.dumps({k: v for k, v in rep.items() if k != "rows"}, ensure_ascii=False)); return 0
    if a.merge is not None:
        rows = []
        for f in a.merge: rows += json.load(open(f, encoding="utf-8"))["rows"]
        rows.sort(key=lambda m: m["id"]); write_reports(a, rows, 0, a.model); return 0
    from faster_whisper import WhisperModel
    rows = [json.loads(l) for l in open(ROOT / a.manifest, encoding="utf-8")]
    if a.shard:
        i, n = (int(x) for x in a.shard.split("/")); rows = rows[i::n]
    if a.limit: rows = rows[:a.limit]
    t0 = time.time()
    model = WhisperModel(a.model, device="cpu", compute_type="int8", cpu_threads=max(1, 4 // a.workers))
    print(f"whisper {a.model} loaded in {time.time() - t0:.0f}s; {len(rows)} files", flush=True)

    def one(r):
        p = ROOT / r["audio"]
        if not p.exists():
            return dict(id=r["id"], audio=r["audio"], verdict="missing")
        t1 = time.time()
        asr, segs, used = "", [], None
        for lang in ("sa", "hi", None):           # Sanskrit first; an empty result gets a Hindi pass, then auto-detect
            sg, info = model.transcribe(str(p), language=lang, beam_size=1, vad_filter=False, condition_on_previous_text=False)
            segs = list(sg); asr = " ".join(x.text.strip() for x in segs); used = lang or getattr(info, "language", None)
            if len(norm(asr)) >= 20: break
        speech = sum(s.end - s.start for s in segs)
        m = measure(model_text(r["text"]), asr)
        m.update(dict(id=r["id"], audio=r["audio"], work=r.get("work"), text_id=r.get("text_id"), duration=r.get("duration"), asr_language=used,
                      speech_seconds=round(speech, 1), segments=len(segs), expected=model_text(r["text"]), asr=asr, seconds=round(time.time() - t1, 1)))
        return m

    out = []
    with ThreadPoolExecutor(a.workers) as ex:
        for i, m in enumerate(ex.map(one, rows)):
            out.append(m)
            if (i + 1) % 10 == 0:
                print(f"  {i + 1}/{len(rows)} · {time.time() - t0:.0f}s", flush=True)
    write_reports(a, out, t0, a.model)
    return 0


# ---------------------------------------------------------------- cross-match against the whole work
def _grams(s, n=4):
    return {s[i:i + n] for i in range(len(s) - n + 1)}


def crossmatch(rows, units, min_score=0.3, margin=0.15):
    """For every checked recording, find the verse of the same work whose text the ASR resembles most.

    A CER against the *expected* text only says "does not match"; it cannot say what the recording IS.
    Comparing the ASR with every verse of the work does: an off-by-one file numbering or a wrong
    prabandha shows up as a clear best match on a different verse. Decisions:
      confirmed     best match is the expected verse, clearly ahead of the runner-up
      weak_confirm  expected verse is the best match but not by much
      remap         a different verse is the best match by a clear margin (rik/verse id in `heard`)
      inconclusive  the ASR is too garbled to match anything (try a bigger model, or listen)
    """
    corpus = {u.get("text_id") or u.get("id"): to_latin(u["text"]) for u in units if u.get("text")}
    G = {k: _grams(t) for k, t in corpus.items()}
    by_work = {}
    for k in corpus:
        by_work.setdefault(k.split(":")[0], []).append(k)
    out = []
    for r in rows:
        asr = to_latin(r.get("asr") or "")
        pool = by_work.get(r["text_id"].split(":")[0], [])
        rec = {"id": r["id"], "text_id": r["text_id"], "audio": r.get("audio"), "verdict": r.get("verdict"),
               "heard": None, "score": 0.0, "expected_score": 0.0, "runner_up": None, "decision": "inconclusive"}
        if len(asr) >= 20 and pool:
            ga = _grams(asr)
            sc = sorted(((len(ga & G[k]) / max(1, len(G[k])), k) for k in pool), reverse=True)
            best, second = sc[0], sc[1] if len(sc) > 1 else (0.0, None)
            exp_s = next((x for x, k in sc if k == r["text_id"]), 0.0)
            rec.update(heard=best[1], score=round(best[0], 3), expected_score=round(exp_s, 3), runner_up=second[1])
            if best[1] == r["text_id"] and best[0] >= 0.25 and best[0] - second[0] >= 0.1:
                rec["decision"] = "confirmed"
            elif best[1] != r["text_id"] and best[0] >= min_score and best[0] - max(exp_s, second[0] if second[1] != r["text_id"] else 0.0) >= margin:
                rec["decision"] = "remap"
                rec["heard_text"] = next(u["text"] for u in units if (u.get("text_id") or u.get("id")) == best[1])
            elif best[1] == r["text_id"] and best[0] >= 0.2:
                rec["decision"] = "weak_confirm"
        out.append(rec)
    return out


def combine_crossmatch(runs):
    """Merge cross-match rows from several ASR runs (e.g. Whisper small and medium) per recording:
    a decisive decision from any run wins (highest score); two runs naming different verses → 'conflict'."""
    by = {}
    for recs in runs:
        for r in recs:
            cur = by.get(r["id"])
            if cur is None:
                by[r["id"]] = dict(r); continue
            decisive = lambda x: x["decision"] in ("confirmed", "weak_confirm", "remap")
            if decisive(r) and decisive(cur) and r["heard"] != cur["heard"]:
                by[r["id"]] = dict(cur, decision="conflict", conflict_with=r["heard"])
            elif decisive(r) and (not decisive(cur) or r["score"] > cur["score"]):
                by[r["id"]] = dict(r)
    return [by[k] for k in sorted(by)]


def write_crossmatch(recs, out_dir, source):
    from collections import Counter
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    rep = {"checkedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "source_report": str(source), "files": len(recs),
           "decisions": dict(Counter(r["decision"] for r in recs)), "rows": recs}
    json.dump(rep, open(out_dir / "crossmatch.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    order = {"conflict": 0, "remap": 1, "inconclusive": 2, "weak_confirm": 3, "confirmed": 4}
    lines = [f"# Cross-match of recordings against the whole work\n\nSource: `{source}` · {len(recs)} files · " +
             " · ".join(f"{k} {v}" for k, v in sorted(rep["decisions"].items())) + "\n",
             "| id | file | expected | decision | heard | score | expected score |", "|---|---|---|---|---|---|---|"]
    for r in sorted(recs, key=lambda r: (order[r["decision"]], r["text_id"])):
        lines.append(f"| {r['id']} | {(r.get('audio') or '').split('/')[-1]} | {r['text_id'].split(':')[-1]} | {r['decision']} | "
                     f"{(r['heard'] or '').split(':')[-1]} | {r['score']} | {r['expected_score']} |")
    (out_dir / "crossmatch.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return rep


def write_reports(a, out, t0, model_name):
    from collections import Counter
    verdicts = Counter(m["verdict"] for m in out)
    cers = sorted(m["cer"] for m in out if "cer" in m)
    rep = {"checkedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "model": model_name, "files": len(out), "verdicts": dict(verdicts),
           "cer_median": cers[len(cers) // 2] if cers else None, "cer_p90": cers[int(len(cers) * 0.9)] if cers else None,
           "seconds": round(time.time() - t0) if t0 else None, "rows": out}
    Path(ROOT / (a.out + ".json")).write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    md = [f"# Pilot transcript check ({rep['checkedAt'][:10]}, whisper {model_name}, {len(out)} files)", "",
          f"Verdicts: {dict(verdicts)} · CER median {rep['cer_median']} · p90 {rep['cer_p90']} · {rep['seconds']} s", "",
          "| id | work | dur s | speech s | ratio | repeat | coverage | CER | verdict |", "|---|---|---|---|---|---|---|---|---|"]
    for m in sorted(out, key=lambda x: (x["verdict"] == "ok", -x.get("length_ratio", 0))):
        md.append(f"| {m['id']} | {m.get('work','')} | {m.get('duration','')} | {m.get('speech_seconds','')} | {m.get('length_ratio','')} | {m.get('self_repeat','')} | {m.get('coverage','')} | {m.get('cer','')} | **{m['verdict']}** |")
    md += ["", "## Every non-ok file: expected vs heard", ""]
    for m in out:
        if m["verdict"] != "ok":
            md += [f"### {m['id']} — {m['verdict']} ({m.get('audio','')})", "", f"expected: {m.get('expected','')}", "", f"heard: {m.get('asr','')}", ""]
    Path(ROOT / (a.out + ".md")).write_text("\n".join(md), encoding="utf-8")
    print(json.dumps({k: v for k, v in rep.items() if k != "rows"}, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
