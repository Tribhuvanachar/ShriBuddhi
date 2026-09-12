#!/usr/bin/env python3
"""Vedavani (IIT Kharagpur, ACL 2025) Rigveda/Atharvaveda clip corpus on Hugging Face.

    dataset : https://huggingface.co/datasets/sanganaka/Vedavani-Dataset  (Apache-2.0)
    paper   : https://arxiv.org/abs/2506.00145
    audio   : Veda Prasara Samiti recitations, segmented by the paper's authors from
              https://archive.org/details/RigvedaChanting (Public Domain Mark) and
              https://archive.org/details/atharvaveda_202107
    NOT the same thing as the VedaVaNi Android app (com.vedic.chant) whose per-sukta
    MP3s are handled by tools/vedavani/extract_audio.py.

The audio (~5.4 GB, 30,779 WAVs, 16 kHz mono) never enters this git repository. What is
committed is a manifest: one row per clip with its exact download URL, LFS sha256, byte
size, duration, Devanagari text and the DGE ṛk id(s) the text was matched to.

Commands
    build-manifest   HF tree + CSVs + DGE Rigveda corpus  ->  manifest.csv.gz + summary.json
    verify           download N random clips: HTTP 200, RIFF/WAVE header, size, sha256, duration
    fetch            download clips (filtered by mandala / match kind) to a gitignored folder
    mirror           copy the whole dataset + our manifest into an org-owned HF dataset repo

Nothing here calls Gemini.
"""
from __future__ import annotations

import argparse
import bisect
import collections
import csv
import difflib
import glob
import gzip
import hashlib
import io
import json
import os
import random
import re
import struct
import sys
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DATASET = "sanganaka/Vedavani-Dataset"
RESOLVE = f"https://huggingface.co/datasets/{DATASET}/resolve/main/"
OUT_DIR = REPO / "kamadhenu_dataset" / "external" / "vedavani_hf"
MANIFEST = OUT_DIR / "manifest.csv.gz"
SUMMARY = OUT_DIR / "summary.json"
DEFAULT_DEST = REPO / "kamadhenu_dataset" / "incoming_audio" / "vedavani_hf"
RIGVEDA_GLOB = "dge/data/vedas/rigveda/shakala_shakha/samhita/mandala_*/data.json"
IST = timezone(timedelta(hours=5, minutes=30))

FIELDS = [
    "audio_file", "hf_path", "split", "batch", "veda", "group", "seq", "bytes", "sha256",
    "length_s", "text", "match", "rik_ids", "score",
]


def now_ist() -> str:
    return datetime.now(IST).strftime("%d %b %Y, %I:%M %p IST").lstrip("0")


# ----------------------------------------------------------------------------- text
_ACCENTS = re.compile("[॑-॔᳐-᳿꣠-ꣿ́̀]")
_KEEP = re.compile("[^ऀ-ॣ]")  # Devanagari letters/matras only (no digits/dandas)


def norm(s: str) -> str:
    """Accent-free, space-free Devanagari for matching (ळ→ड, ँ→ं, avagraha dropped)."""
    s = unicodedata.normalize("NFC", s or "")
    s = _ACCENTS.sub("", s)
    s = s.replace("ळ", "ड").replace("ऽ", "").replace("ँ", "ं")
    return _KEEP.sub("", s)


def parse_name(audio_file: str):
    """'Rigveda_35_0340.wav' -> (veda, group, seq)."""
    base = audio_file.rsplit("/", 1)[-1]
    m = re.match(r"(.+?)_(\d+)\.wav$", base)
    group, seq = (m.group(1), int(m.group(2))) if m else (base, -1)
    veda = "atharvaveda" if base.lower().startswith("atharva") else "rigveda"
    return veda, group, seq


# ----------------------------------------------------------------------------- corpus
class RigvedaIndex:
    """DGE Rigveda saṃhitā as one accent-free string with ṛk boundaries."""

    def __init__(self, repo: Path = REPO):
        self.ids: list[str] = []
        self.texts: list[str] = []
        starts: list[int] = []
        buf = io.StringIO()
        pos = 0
        for f in sorted(glob.glob(str(repo / RIGVEDA_GLOB))):
            for it in json.load(open(f, encoding="utf-8"))["items"]:
                t = norm(it.get("samhita_patha", ""))
                self.ids.append(it["id"])
                self.texts.append(t)
                starts.append(pos)
                buf.write(t)
                pos += len(t)
        self.big = buf.getvalue()
        self.starts = starts
        # 8-gram index for fuzzy candidates
        self.grams: dict[str, list[int]] = collections.defaultdict(list)
        for i, t in enumerate(self.texts):
            seen = set()
            for k in range(0, max(0, len(t) - 7), 4):
                g = t[k:k + 8]
                if g not in seen:
                    seen.add(g)
                    self.grams[g].append(i)

    def span(self, pos: int, length: int) -> list[int]:
        i = bisect.bisect_right(self.starts, pos) - 1
        j = bisect.bisect_right(self.starts, pos + length - 1) - 1
        return list(range(i, j + 1))

    def all_positions(self, q: str, cap: int = 50) -> list[int]:
        out, p = [], self.big.find(q)
        while p >= 0 and len(out) < cap:
            out.append(p)
            p = self.big.find(q, p + 1)
        return out

    def fuzzy(self, q: str):
        """Best (score, [rik idx...]) among 8-gram candidates, allowing a 2-ṛk window."""
        hits = collections.Counter()
        for k in range(0, max(1, len(q) - 7), 2):
            for i in self.grams.get(q[k:k + 8], ()):
                hits[i] += 1
        best = (0.0, [])
        for i, _ in hits.most_common(6):
            for width in (1, 2):
                idxs = list(range(i, min(i + width, len(self.texts))))
                cand = "".join(self.texts[j] for j in idxs)
                sm = difflib.SequenceMatcher(None, q, cand, autojunk=False)
                a, b, size = sm.find_longest_match(0, len(q), 0, len(cand))
                # ratio of q covered by matching blocks against the candidate window
                covered = sum(bl.size for bl in sm.get_matching_blocks())
                score = covered / max(1, len(q))
                if score > best[0]:
                    # keep only the ṛks the matched region actually touches
                    lo = min(bl.b for bl in sm.get_matching_blocks() if bl.size)
                    hi = max(bl.b + bl.size for bl in sm.get_matching_blocks() if bl.size)
                    off, touched = 0, []
                    for j in idxs:
                        L = len(self.texts[j])
                        if hi > off and lo < off + L:
                            touched.append(j)
                        off += L
                    best = (round(score, 3), touched or idxs)
        return best


def map_rows(rows: list[dict], idx: RigvedaIndex, fuzzy_min: float = 0.85) -> collections.Counter:
    """Fill match / rik_ids / score on each Rigveda row in place."""
    stats = collections.Counter()
    by_group: dict[str, list[dict]] = collections.defaultdict(list)
    pending_amb = []
    for r in rows:
        if r["veda"] != "rigveda":
            r["match"], r["rik_ids"], r["score"] = "n/a", "", ""
            stats["atharvaveda"] += 1
            continue
        by_group[r["group"]].append(r)
        q = norm(r["text"])
        if len(q) < 8:
            r["match"], r["rik_ids"], r["score"] = "too_short", "", ""
            stats["too_short"] += 1
            continue
        poss = idx.all_positions(q)
        if len(poss) == 1:
            span = idx.span(poss[0], len(q))
            r["match"] = "exact" if len(span) == 1 else "exact_span"
            r["_idx"] = span
            r["score"] = "1.0"
            stats[r["match"]] += 1
        elif len(poss) > 1:
            r["_cands"] = [idx.span(p, len(q)) for p in poss]
            pending_amb.append(r)
        else:
            score, span = idx.fuzzy(q)
            if score >= fuzzy_min and span:
                r["match"], r["_idx"], r["score"] = "fuzzy", span, str(score)
                stats["fuzzy"] += 1
            else:
                r["match"], r["rik_ids"], r["score"] = "unmatched", "", str(score)
                stats["unmatched"] += 1
    # Ambiguous texts (refrains, repeated pādas): pick the candidate nearest the
    # neighbouring clips of the same recording group — recordings run in text order.
    for r in pending_amb:
        grp = by_group[r["group"]]
        pos_of = {x["seq"]: x["_idx"][0] for x in grp if x.get("_idx")}
        before = [pos_of[s] for s in range(r["seq"] - 1, r["seq"] - 7, -1) if s in pos_of]
        after = [pos_of[s] for s in range(r["seq"] + 1, r["seq"] + 7) if s in pos_of]
        if before or after:
            # A refrain closes the ṛk it belongs to, so the clip just before is the best
            # anchor: prefer the nearest candidate at or after it, else the nearest overall.
            anchor = before[0] if before else after[0]
            best = min(r["_cands"], key=lambda c: (c[0] - anchor if c[0] >= anchor else 10 ** 6 + anchor - c[0]))
            r["match"], r["_idx"], r["score"] = "resolved", best, "1.0"
            stats["resolved"] += 1
        else:
            r["match"], r["_idx"], r["score"] = "ambiguous", r["_cands"][0], "1.0"
            r["rik_ids"] = "|".join(";".join(idx.ids[i] for i in c) for c in r["_cands"][:8])
            stats["ambiguous"] += 1
    for r in rows:
        if r.get("_idx") and r["match"] != "ambiguous":
            r["rik_ids"] = ";".join(idx.ids[i] for i in r["_idx"])
        r.pop("_idx", None)
        r.pop("_cands", None)
    return stats


# ----------------------------------------------------------------------------- hub
def hf_api():
    from huggingface_hub import HfApi
    return HfApi(token=os.environ.get("HF_TOKEN") or None)


def hf_tree() -> dict[str, dict]:
    """basename -> {path, size, sha256} for every WAV in the dataset (LFS oid = sha256)."""
    out = {}
    for e in hf_api().list_repo_tree(DATASET, repo_type="dataset", path_in_repo="AudioFiles", recursive=True):
        path = getattr(e, "path", "")
        if not path.endswith(".wav"):
            continue
        lfs = getattr(e, "lfs", None)
        out[path.rsplit("/", 1)[-1]] = {
            "path": path,
            "size": getattr(e, "size", None),
            "sha256": (lfs.sha256 if lfs and hasattr(lfs, "sha256") else (lfs or {}).get("sha256") if isinstance(lfs, dict) else None) if lfs else None,
        }
    return out


def hf_csv_rows() -> list[dict]:
    from huggingface_hub import hf_hub_download
    rows = []
    for split in ("train", "validation", "test"):
        p = hf_hub_download(DATASET, f"{split}.csv", repo_type="dataset")
        for row in csv.DictReader(open(p, encoding="utf-8")):
            rows.append({"audio_file": row["audio_file"], "text": row["text"].strip(),
                         "length_s": row["length"], "split": split})
    return rows


# ----------------------------------------------------------------------------- commands
def cmd_build_manifest(a):
    t0 = time.time()
    tree = hf_tree()
    rows = hf_csv_rows()
    print(f"tree: {len(tree)} wavs; csv rows: {len(rows)}")
    for r in rows:
        r["veda"], r["group"], r["seq"] = parse_name(r["audio_file"])
        ent = tree.get(r["audio_file"])
        r["hf_path"] = ent["path"] if ent else ""
        r["batch"] = ent["path"].split("/")[1] if ent else ""
        r["bytes"] = ent["size"] if ent else ""
        r["sha256"] = ent["sha256"] or "" if ent else ""
    missing = [r["audio_file"] for r in rows if not r["hf_path"]]
    idx = RigvedaIndex()
    stats = map_rows(rows, idx)
    rows.sort(key=lambda r: (r["veda"], r["group"], r["seq"]))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with gzip.open(MANIFEST, "wt", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    rig = [r for r in rows if r["veda"] == "rigveda"]
    mapped = [r for r in rig if r["match"] in ("exact", "exact_span", "resolved", "fuzzy")]
    covered = set()
    for r in mapped:
        covered.update(r["rik_ids"].split(";"))
    hours = lambda rs: round(sum(float(r["length_s"] or 0) for r in rs) / 3600, 2)
    summary = {
        "dataset": DATASET,
        "resolve_base": RESOLVE,
        "built_at": now_ist(),
        "rows": len(rows),
        "rigveda_rows": len(rig),
        "atharvaveda_rows": len(rows) - len(rig),
        "rigveda_hours": hours(rig),
        "atharvaveda_hours": hours([r for r in rows if r["veda"] != "rigveda"]),
        "bytes_total": sum(int(r["bytes"] or 0) for r in rows),
        "missing_in_tree": missing,
        "match": dict(stats),
        "rigveda_mapped_rows": len(mapped),
        "rigveda_mapped_hours": hours(mapped),
        "dge_riks_total": len(idx.ids),
        "dge_riks_covered": len(covered),
        "groups": len({r["group"] for r in rig}),
        "elapsed_s": round(time.time() - t0, 1),
        "provenance": {
            "licence_dataset": "Apache-2.0 (dataset card)",
            "audio_origin": "Veda Prasara Samiti, via archive.org RigvedaChanting / atharvaveda_202107 (Public Domain Mark 1.0)",
            "paper": "https://arxiv.org/abs/2506.00145",
        },
    }
    json.dump(summary, open(SUMMARY, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False, indent=1))


def read_manifest() -> list[dict]:
    if not MANIFEST.exists():
        sys.exit(f"{MANIFEST} missing — run build-manifest first")
    with gzip.open(MANIFEST, "rt", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def wav_info(b: bytes):
    if b[:4] != b"RIFF" or b[8:12] != b"WAVE":
        return None
    i, fmt, datalen = 12, None, None
    while i + 8 <= len(b):
        cid, sz = b[i:i + 4], struct.unpack("<I", b[i + 4:i + 8])[0]
        if cid == b"fmt ":
            fmt = struct.unpack("<HHIIHH", b[i + 8:i + 24])
        if cid == b"data":
            datalen = sz
            break
        i += 8 + sz + (sz & 1)
    if not fmt or datalen is None:
        return None
    _, ch, rate, _, _, bits = fmt
    return {"channels": ch, "rate": rate, "bits": bits,
            "duration_s": round(datalen / (rate * ch * bits / 8), 3)}


def download(row: dict, dest: Path | None = None) -> bytes:
    from huggingface_hub import hf_hub_download
    p = hf_hub_download(DATASET, row["hf_path"], repo_type="dataset")
    b = open(p, "rb").read()
    if dest:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b)
    return b


def cmd_verify(a):
    rows = [r for r in read_manifest() if r["veda"] == a.veda and r["hf_path"]]
    random.seed(a.seed)
    sample = random.sample(rows, min(a.sample, len(rows)))
    report, ok = [], 0
    for r in sample:
        url = RESOLVE + r["hf_path"]
        t = time.time()
        b = download(r)
        info = wav_info(b) or {}
        sha = hashlib.sha256(b).hexdigest()
        rec = {"audio_file": r["audio_file"], "url": url, "bytes": len(b),
               "bytes_match": str(len(b)) == r["bytes"],
               "sha256_match": sha == r["sha256"] if r["sha256"] else None,
               "riff": bool(info), **info,
               "duration_match": abs(info.get("duration_s", -1) - float(r["length_s"])) < 0.01,
               "rik_ids": r["rik_ids"], "match": r["match"], "text": r["text"],
               "secs": round(time.time() - t, 1)}
        good = rec["riff"] and rec["bytes_match"] and rec["duration_match"] and rec["sha256_match"] is not False
        ok += good
        report.append(rec)
        print(("OK  " if good else "BAD ") + json.dumps(rec, ensure_ascii=False))
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        json.dump({"checked_at": now_ist(), "ok": ok, "total": len(sample), "files": report},
                  open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{ok}/{len(sample)} verified")
    return 0 if ok == len(sample) else 1


def select_rows(a) -> list[dict]:
    rows = [r for r in read_manifest() if r["hf_path"] and r["veda"] == a.veda]
    kinds = set(a.match.split(",")) if a.match else None
    if kinds:
        rows = [r for r in rows if r["match"] in kinds]
    if a.mandala:
        want = set()
        for part in a.mandala.split(","):
            lo, _, hi = part.partition("-")
            want.update(range(int(lo), int(hi or lo) + 1))
        rows = [r for r in rows if r["rik_ids"] and int(r["rik_ids"].split(".")[0]) in want]
    if a.limit:
        rows = rows[: a.limit]
    return rows


def cmd_fetch(a):
    rows = select_rows(a)
    dest = Path(a.dest)
    total = sum(int(r["bytes"] or 0) for r in rows)
    print(f"{len(rows)} clips, {total / 1e6:.1f} MB -> {dest}")
    if a.dry_run:
        for r in rows[:20]:
            print(" ", r["hf_path"], r["rik_ids"], r["length_s"])
        return 0
    bad = 0
    with open(dest / "fetched.jsonl", "a", encoding="utf-8") if (dest.mkdir(parents=True, exist_ok=True) or True) else None as log:
        for n, r in enumerate(rows, 1):
            target = dest / r["audio_file"]
            if target.exists() and target.stat().st_size == int(r["bytes"] or -1):
                continue
            b = download(r, target)
            sha = hashlib.sha256(b).hexdigest()
            if r["sha256"] and sha != r["sha256"]:
                bad += 1
                print(f"sha256 mismatch: {r['audio_file']}")
            log.write(json.dumps({"audio_file": r["audio_file"], "bytes": len(b), "sha256": sha,
                                  "rik_ids": r["rik_ids"], "text": r["text"], "length_s": r["length_s"]},
                                 ensure_ascii=False) + "\n")
            if n % 200 == 0:
                print(f"  {n}/{len(rows)}")
    print(f"done, {bad} checksum failures")
    return 1 if bad else 0


def cmd_mirror(a):
    """snapshot_download the upstream dataset and push it, plus our manifest, to a repo we own."""
    from huggingface_hub import snapshot_download, upload_folder, upload_file
    api = hf_api()
    api.create_repo(a.repo, repo_type="dataset", private=a.private, exist_ok=True)
    local = snapshot_download(DATASET, repo_type="dataset", local_dir=a.workdir,
                              allow_patterns=a.allow or None, max_workers=8)
    print("snapshot at", local)
    upload_folder(repo_id=a.repo, repo_type="dataset", folder_path=local,
                  commit_message=f"Mirror of {DATASET} ({now_ist()})", ignore_patterns=[".cache/*"])
    for f in (MANIFEST, SUMMARY):
        if f.exists():
            upload_file(path_or_fileobj=str(f), path_in_repo=f"dge/{f.name}", repo_id=a.repo,
                        repo_type="dataset", commit_message="DGE manifest with ṛk mapping")
    readme = (f"# Mirror of {DATASET}\n\nMirrored {now_ist()} for the DGE / Kamadhenu project.\n\n"
              "Upstream licence: Apache-2.0 (dataset card). Audio origin: Veda Prasara Samiti recitations "
              "segmented by the Vedavani authors (arXiv:2506.00145) from archive.org items "
              "`RigvedaChanting` and `atharvaveda_202107` (Public Domain Mark 1.0).\n\n"
              "`dge/manifest.csv` maps every Rigveda clip to DGE ṛk ids (mandala.sukta.rik).\n")
    upload_file(path_or_fileobj=readme.encode(), path_in_repo="README_DGE.md", repo_id=a.repo,
                repo_type="dataset", commit_message="DGE provenance note")
    print("mirrored to", a.repo)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build-manifest").set_defaults(fn=cmd_build_manifest)
    v = sub.add_parser("verify")
    v.add_argument("--sample", type=int, default=3)
    v.add_argument("--seed", type=int, default=None)
    v.add_argument("--veda", default="rigveda")
    v.add_argument("--out", default=None)
    v.set_defaults(fn=cmd_verify)
    f = sub.add_parser("fetch")
    f.add_argument("--dest", default=str(DEFAULT_DEST))
    f.add_argument("--veda", default="rigveda")
    f.add_argument("--match", default="exact,exact_span,resolved,fuzzy")
    f.add_argument("--mandala", default="", help='e.g. "1" or "1-3" or "1,5,9"')
    f.add_argument("--limit", type=int, default=0)
    f.add_argument("--dry-run", action="store_true")
    f.set_defaults(fn=cmd_fetch)
    m = sub.add_parser("mirror")
    m.add_argument("--repo", required=True, help="e.g. SarvamulaOrg/vedavani-dataset-mirror")
    m.add_argument("--private", action="store_true")
    m.add_argument("--workdir", default="/tmp/vedavani_snapshot")
    m.add_argument("--allow", nargs="*", default=None, help="snapshot allow_patterns (default: everything)")
    m.set_defaults(fn=cmd_mirror)
    a = ap.parse_args(argv)
    return a.fn(a) or 0


if __name__ == "__main__":
    sys.exit(main())
