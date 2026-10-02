#!/usr/bin/env python3
"""Build the offline Kosha packs (the "offline fast mode" data).

WHY PACKS. The live corpus is ~320,000 tiny shard files. Saving ~70,000 of them one by one
into a browser would be hundreds of MB and tens of thousands of requests. A pack bundles many
shards into one gzip file, so a reader downloads a few files once, unpacks them into the
browser's IndexedDB, and the normal kosha.js engine then reads every shard locally.

WHAT GOES IN. Only the chosen dictionaries (default: shabdArtha_kaustubha, shabdakalpadruma,
vachaspatyam):
  * every entry shard of those dictionaries           (<category>/<dict>/e/<bucket>.json)
  * the INDEX shards, filtered to those dictionaries   (_index/<bucket>.json) - an index shard
    lists the members of EVERY dictionary, so ~85% of each is dropped
  * optionally the enriched-layout shards              (@r/<category>/<dict>/e/<bucket>.json)
  * a restricted manifest (only these dictionaries, only buckets that still have members)

Shard files keep the names the data repo uses; kosha.js accepts both naming schemes.

Usage:
  python tools/build_kosha_offline.py --out OUTDIR [--sha SHA] [--dicts a,b,c]
                                      [--with-enriched] [--names names.txt] [--pack-mb 24]
Writes OUTDIR/offline-manifest.json and OUTDIR/pack-NN.json.gz and prints the sizes.
"""
import argparse, gzip, json, os, subprocess, sys, tempfile, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

REPO = "Tribhuvanachar/Kosha"
DEFAULT_SHA = "54072a8d40d4907df588d722b3796afe06ec2568"      # = js/config.js koshaDataBase pin
DEFAULT_DICTS = "shabdArtha_kaustubha,shabdakalpadruma,vachaspatyam"
KEEP = "!'()*-._~"                                              # what encodeURIComponent leaves alone


def legacy_name(bucket):
    """Old shard file name: letters, digits and '_' kept (letters keep their case); every other
    character is % + lower-case hex of its code point (checked against the 18,680 published files)."""
    out = ""
    for ch in bucket:
        out += ch if (ch.isascii() and ch.isalnum()) or ch == "_" else "%" + format(ord(ch), "x")
    return out or "_"          # the literal file name (the URL form is quote(name))


def safe_name(bucket):
    """New (14 Sep 2026) Windows-safe name: capital -> lower + '-', other -> '_'."""
    out = ""
    for ch in bucket:
        if ch.isascii() and (ch.isdigit() or ch.islower()) or ch in "^$":
            out += ch
        elif ch.isascii() and ch.isupper():
            out += ch.lower() + "-"
        else:
            out += "_"
    out = out or "_"
    if out.split(".")[0].lower() in {"con", "prn", "aux", "nul"} | {f"com{i}" for i in range(10)} | {f"lpt{i}" for i in range(10)}:
        out += "~"
    return out


def get(url, tries=5):
    for n in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "kosha-offline-builder"}), timeout=60) as r:
                return r.read()
        except Exception as e:                                   # noqa: BLE001
            if n == tries - 1:
                raise
            time.sleep(1 + n)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--sha", default=DEFAULT_SHA)
    ap.add_argument("--dicts", default=DEFAULT_DICTS)
    ap.add_argument("--with-enriched", action="store_true")
    ap.add_argument("--names", help="file of `git ls-tree -r --name-only` for the pinned commit (skips the clone)")
    ap.add_argument("--pack-mb", type=float, default=24.0, help="uncompressed MB per pack file")
    ap.add_argument("--workers", type=int, default=24)
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    want = a.dicts.split(",")
    raw = f"https://raw.githubusercontent.com/{REPO}/{a.sha}/data/"
    os.makedirs(a.out, exist_ok=True)

    full = json.loads(get(raw + "koshas/_index/manifest.json"))
    print("pinned commit", a.sha[:10], "- dictionaries in the corpus:", len(full["dictionaries"]))
    for d in want:
        assert d in full["dictionaries"], f"unknown dictionary {d}"

    if a.names:
        names = open(a.names, encoding="utf-8").read().split("\n")
    else:
        tmp = tempfile.mkdtemp()
        subprocess.run(["git", "clone", "--quiet", "--filter=blob:none", "--no-checkout", "--depth", "1", "--branch", "dist",
                        f"https://github.com/{REPO}.git", tmp], check=True)
        names = subprocess.run(["git", "-C", tmp, "ls-tree", "-r", "-z", "--name-only", "HEAD"], check=True,
                               capture_output=True).stdout.decode("utf-8").split("\0")
    names = [n for n in names if n]
    nameset = set(names)

    jobs = []                                   # (key stored in pack, url path under data/)
    for d in want:
        cat = full["dictionaries"][d]["category"]
        pre = f"data/koshas/{cat}/{d}/e/"
        jobs += [(n[len("data/koshas/"):], n) for n in names if n.startswith(pre)]
        if a.with_enriched:
            pre = f"data/koshas_r/{cat}/{d}/e/"
            jobs += [("@r/" + n[len("data/koshas_r/"):], n) for n in names if n.startswith(pre)]
    n_entry = len(jobs)

    # index shards: only those named by the manifest's buckets; filtered after download
    index_jobs, missing = [], 0
    for b in full["buckets"]:
        for nm in dict.fromkeys([legacy_name(b), safe_name(b)]):
            p = f"data/koshas/_index/{nm}.json"
            if p in nameset:
                index_jobs.append((b, f"_index/{nm}.json", p)); break
        else:
            missing += 1
    print(f"entry/enriched shards: {n_entry}; index shards: {len(index_jobs)} (no file for {missing} buckets)")

    def url_of(path):
        return raw + urllib.parse.quote(path[len("data/"):], safe="/")

    def fetch_entry(job):
        key, path = job
        return key, json.loads(get(url_of(path)))

    keep_dicts = set(want)
    def fetch_index(job):
        b, key, path = job
        sh = json.loads(get(url_of(path)))
        out = {}
        for fold, members in sh.items():
            m = [x for x in members if x.get("d") in keep_dicts]
            if m:
                out[fold] = m
        return b, key, out

    shards, kept_buckets = {}, []
    t0 = time.time()
    with ThreadPoolExecutor(a.workers) as ex:
        for i, (key, obj) in enumerate(ex.map(fetch_entry, jobs)):
            shards[key] = obj
            if i % 2000 == 0:
                print(f"  entries {i}/{n_entry}  {time.time()-t0:.0f}s", flush=True)
        for i, (b, key, obj) in enumerate(ex.map(fetch_index, index_jobs)):
            if obj:
                shards[key] = obj
                kept_buckets.append(b)
            if i % 2000 == 0:
                print(f"  index {i}/{len(index_jobs)}  {time.time()-t0:.0f}s", flush=True)

    # restricted manifest: same schema, only our dictionaries, only buckets that still have members
    man = dict(full)
    man["dictionaries"] = {d: full["dictionaries"][d] for d in want}
    man["buckets"] = kept_buckets

    # pack: group shards, ~pack-mb of JSON each, gzip
    packs, cur, size, num, raw_total, gz_total = [], {}, 0, 0, 0, 0
    def flush():
        nonlocal cur, size, num, raw_total, gz_total
        if not cur:
            return
        num += 1
        blob = json.dumps({"v": 1, "shards": cur}, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        gz = gzip.compress(blob, 9)
        fn = f"pack-{num:02d}.json.gz"
        open(os.path.join(a.out, fn), "wb").write(gz)
        packs.append({"file": fn, "shards": len(cur), "bytes": len(gz), "rawBytes": len(blob)})
        raw_total += len(blob); gz_total += len(gz)
        cur, size = {}, 0
    for key in sorted(shards):
        enc = len(json.dumps(shards[key], ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        if size and size + enc > a.pack_mb * 1e6:
            flush()
        cur[key] = shards[key]; size += enc
    flush()

    meta = {"version": 1, "builtFrom": a.sha, "builtAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "dicts": want, "withEnriched": a.with_enriched, "manifest": man, "packs": packs,
            "totalBytes": gz_total, "totalRawBytes": raw_total, "shardCount": len(shards)}
    json.dump(meta, open(os.path.join(a.out, "offline-manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"\n{len(shards)} shards in {len(packs)} packs: {gz_total/1e6:.1f} MB gzip ({raw_total/1e6:.0f} MB raw); {time.time()-t0:.0f}s")
    for p in packs:
        print(f"  {p['file']}  {p['shards']} shards  {p['bytes']/1e6:.1f} MB")


if __name__ == "__main__":
    main()
