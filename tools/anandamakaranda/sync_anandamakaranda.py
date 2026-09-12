#!/usr/bin/env python3
"""
sync_anandamakaranda.py — keep the SarvaMūla granthas that came from
anandamakaranda.in in step with the wiki.

The site is a MediaWiki, and for every work it publishes a block-level JSON
export at <Title>/JSON (a <pre class="gr-json-meta"> holding
{"schema": 1, "doc": {...}, "blocks": [{id, oldKey, type, parent, chapter,
verseType, text}, ...]}). Our items carry item.source.block_id = block.id, so
the wiki's blocks and our items can be joined without scraping or Gemini.

Two layouts exist on our side, and the sync treats them differently:

  * ONE-TO-ONE — every item is exactly one wiki block (Tattvodyota: 180
    blocks, 180 items, texts identical). A changed block replaces the item's
    text (the old text is kept in previous_text), new blocks are appended,
    everything we added locally (artha, notes, references, audio,
    verification …) is untouched. Safe to merge unattended.
  * COMPOSITE — the first import folded bhāṣya blocks into their sūtra's
    item (Brahmasutra: 2,252 blocks became 1,315 items, a verse item holds
    the verse plus its bhāṣya with inline HTML). Replacing by block would
    tear those apart, so nothing in data.json is touched. Instead the wiki's
    current blocks are written to <layer>/_sync/anandamakaranda.json beside
    the data.json, and the report lists exactly which blocks changed since
    the previous snapshot — a diff a scholar can apply, by hand or through
    the review page, with the wiki's text in front of them.

Either way:
  1. Map: every dge/data/…/SarvaMula/**/data.json whose source_url is
     https://anandamakaranda.in/index.php?title=<Title> (47 files; asserted).
  2. Change detection: revision ids per page (one API call per 50 titles)
     against admin/config/sync/anandamakaranda.state.json.
  3. New top-level works on the wiki that we do not hold are listed for the
     lead; nothing is imported automatically (no licence statement on the
     wiki — used under the lead's case-by-case authorisation).

    python3 tools/anandamakaranda/sync_anandamakaranda.py                    # report only
    python3 tools/anandamakaranda/sync_anandamakaranda.py --write --write-state
    python3 tools/anandamakaranda/sync_anandamakaranda.py --titles Tattvodyota --force --write

Exit 2 if the mapping invariant fails, 1 if the API is unreachable, else 0.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROOT = os.path.join(REPO, "dge", "data", "darshana", "vedanta", "dvaita", "SarvaMula")
STATE = os.path.join(REPO, "admin", "config", "sync", "anandamakaranda.state.json")
API = "https://anandamakaranda.in/api.php"
RAW = "https://anandamakaranda.in/index.php?action=raw&title="
UA = ("DGE-source-sync/1.0 (+https://github.com/Tribhuvanachar/bhumandala; "
      "non-commercial, educational)")
EXPECTED_FILES = 47
ONE_TO_ONE_MIN = 0.95   # share of items whose text equals their block's text


def fetch(url, timeout=90, tries=3):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as exc:                                # noqa: BLE001
            last = exc
            time.sleep(3 * (i + 1))
    raise last


def load(p):
    return json.load(open(p, encoding="utf-8"))


def save(p, d):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(d, fh, ensure_ascii=False, indent=1)
        fh.write("\n")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def title_map():
    out = {}
    for p in sorted(glob.glob(os.path.join(ROOT, "**", "data.json"), recursive=True)):
        try:
            d = load(p)
        except ValueError:
            continue
        u = d.get("source_url", "") or ""
        if "anandamakaranda.in" in u and "title=" in u:
            t = urllib.parse.unquote(u.split("title=", 1)[1]).strip()
            out.setdefault(t, os.path.relpath(p, REPO))
    return out


def revisions(titles):
    out = {}
    for i in range(0, len(titles), 50):
        q = urllib.parse.urlencode({"action": "query", "prop": "revisions", "rvprop": "ids|timestamp",
                                    "titles": "|".join(titles[i:i + 50]), "format": "json",
                                    "formatversion": "2", "maxlag": "5"})
        d = json.loads(fetch(API + "?" + q))
        for pg in d.get("query", {}).get("pages", []):
            rev = (pg.get("revisions") or [{}])[0]
            out[pg["title"]] = {"revid": rev.get("revid"), "timestamp": rev.get("timestamp"), "missing": pg.get("missing", False)}
        time.sleep(0.5)
    return out


def wiki_json(title):
    body = fetch(RAW + urllib.parse.quote(title + "/JSON")).decode("utf-8", "replace")
    m = re.search(r"<pre[^>]*>(.*?)</pre>", body, re.S)
    txt = m.group(1) if m else body
    txt = re.sub(r"^__\w+__\s*$", "", txt, flags=re.M)
    d = json.loads(txt)
    if d.get("schema") != 1:
        raise ValueError(f"{title}/JSON schema is {d.get('schema')!r}, expected 1 — the export changed shape")
    return d


def layout_of(items, blocks):
    """'one-to-one' when nearly every item is exactly one block, else 'composite'."""
    by_id = {b.get("id"): norm(b.get("text")) for b in blocks}
    matched = compared = 0
    for it in items:
        bid = (it.get("source") or {}).get("block_id")
        if bid in by_id:
            compared += 1
            if norm(it.get("sanskrit_text")) == by_id[bid]:
                matched += 1
    if not compared:
        return "composite", 0.0
    return ("one-to-one" if matched / compared >= ONE_TO_ONE_MIN else "composite"), matched / compared


def merge_one_to_one(doc, wiki):
    items = doc.get("items") or []
    by_block = {(it.get("source") or {}).get("block_id"): it for it in items if (it.get("source") or {}).get("block_id")}
    added = changed = same = 0
    seen = set()
    for b in wiki.get("blocks", []):
        bid = b.get("id")
        if not bid:
            continue
        seen.add(bid)
        text = (b.get("text") or "").strip()
        tags = [t for t in [b.get("type"), b.get("verseType")] if t]
        if bid in by_block:
            it = by_block[bid]
            if norm(it.get("sanskrit_text")) != norm(text):
                it["previous_text"] = it.get("sanskrit_text", "")
                it["sanskrit_text"] = text
                changed += 1
            else:
                same += 1
        else:
            items.append({"id": b.get("oldKey") or bid, "reference": b.get("oldKey") or bid, "sanskrit_text": text,
                          "artha": "", "notes": "", "tags": tags, "references": [], "audio": [],
                          "source": {"site": "anandamakaranda.in", "block_id": bid, "oldKey": b.get("oldKey"),
                                     "type": b.get("type"), "chapter": b.get("chapter")}})
            added += 1
    dropped = [bid for bid in by_block if bid not in seen]
    doc["items"] = items
    return {"added": added, "changed": changed, "same": same, "dropped_upstream": dropped}


def snapshot_diff(old, new):
    """Block-level diff between two wiki exports (or none)."""
    ob = {b.get("id"): b for b in (old or {}).get("blocks", [])}
    nb = {b.get("id"): b for b in new.get("blocks", [])}
    added = [i for i in nb if i not in ob]
    removed = [i for i in ob if i not in nb]
    changed = [i for i in nb if i in ob and norm(nb[i].get("text")) != norm(ob[i].get("text"))]
    return {"added": added, "removed": removed, "changed": changed}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--titles", help="comma-separated wiki titles (blank = every mapped work)")
    ap.add_argument("--force", action="store_true", help="re-fetch even if the revid is unchanged")
    ap.add_argument("--write", action="store_true", help="write merged data.json / snapshots")
    ap.add_argument("--write-state", action="store_true")
    args = ap.parse_args()

    tmap = title_map()
    if len(tmap) != EXPECTED_FILES:
        print(f"mapping invariant broken: {len(tmap)} anandamakaranda-sourced files, expected {EXPECTED_FILES}. "
              f"Update EXPECTED_FILES deliberately if the corpus changed.", file=sys.stderr)
        return 2
    titles = [t.strip() for t in args.titles.split(",")] if args.titles else sorted(tmap)
    titles = [t for t in titles if t in tmap]

    state = load(STATE) if os.path.exists(STATE) else {"pages": {}}
    seen = state.get("pages", {})
    try:
        revs = revisions(titles)
    except Exception as exc:                                    # noqa: BLE001
        print(f"anandamakaranda.in API unreachable: {exc}", file=sys.stderr)
        return 1

    lines = ["## Ānandamakaranda sync", ""]
    changed_titles = []
    for t in titles:
        r = revs.get(t) or {}
        if r.get("missing"):
            lines.append(f"- `{t}` — page missing on the wiki (kept as is)")
            continue
        if r.get("revid") == (seen.get(t) or {}).get("revid") and not args.force:
            continue
        changed_titles.append(t)
    lines.append(f"{len(titles)} works checked; **{len(changed_titles)} changed** since the last sync.")
    lines.append("")

    written = 0
    for t in changed_titles:
        rel = tmap[t]
        path = os.path.join(REPO, rel)
        try:
            w = wiki_json(t)
        except Exception as exc:                                # noqa: BLE001
            lines.append(f"- `{t}` — /JSON not usable ({str(exc)[:80]}); left as is, needs a hand import")
            continue
        doc = load(path)
        items = doc.get("items") or []
        layout, share = layout_of(items, w.get("blocks", []))
        snap_path = os.path.join(os.path.dirname(path), "_sync", "anandamakaranda.json")
        old_snap = load(snap_path) if os.path.exists(snap_path) else None
        if layout == "one-to-one":
            rep = merge_one_to_one(doc, w)
            doc["source_synced"] = {"revid": revs[t].get("revid"), "timestamp": revs[t].get("timestamp"),
                                    "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "layout": layout}
            lines.append(f"- `{t}` → `{rel}` (one-to-one, {share:.0%}): +{rep['added']} new, {rep['changed']} changed, "
                         f"{rep['same']} unchanged" + (f", {len(rep['dropped_upstream'])} gone from the wiki (kept)" if rep["dropped_upstream"] else ""))
            if args.write:
                save(path, doc)
                written += 1
        else:
            d = snapshot_diff(old_snap, w)
            what = (f"+{len(d['added'])} blocks, {len(d['changed'])} changed, {len(d['removed'])} removed since the last snapshot"
                    if old_snap else f"first snapshot, {len(w.get('blocks', []))} blocks")
            lines.append(f"- `{t}` → `{rel}` (composite layout, {share:.0%} one-to-one): data.json untouched; "
                         f"wiki blocks snapshotted to `_sync/anandamakaranda.json` — {what}")
            for bid in (d["changed"] + d["added"])[:8]:
                b = next((x for x in w["blocks"] if x.get("id") == bid), {})
                lines.append(f"    - `{bid}` ({b.get('type')}): {norm(b.get('text'))[:90]}")
            if args.write:
                save(snap_path, {"_readme": "The wiki's current block export for this work, kept beside data.json because this layer's items do not map one-to-one onto wiki blocks. Compare with the previous commit of this file to see what changed upstream; apply by hand or through the review page.",
                                 "title": t, "revid": revs[t].get("revid"), "timestamp": revs[t].get("timestamp"),
                                 "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                 "doc": w.get("doc"), "blocks": w.get("blocks", [])})
                written += 1
        seen[t] = {"revid": revs[t].get("revid"), "timestamp": revs[t].get("timestamp"), "layout": layout}
        time.sleep(0.5)

    try:
        q = urllib.parse.urlencode({"action": "query", "list": "allpages", "apnamespace": "0", "aplimit": "500", "format": "json", "formatversion": "2"})
        pages = json.loads(fetch(API + "?" + q)).get("query", {}).get("allpages", [])
        tops = sorted({p["title"] for p in pages if "/" not in p["title"]})
        new = [t for t in tops if t not in tmap and t not in ("Main Page", "MobileAuthComplete")]
        if new:
            lines += ["", f"Top-level wiki pages we do not hold ({len(new)}): " + ", ".join(new[:40]) + (" …" if len(new) > 40 else "")]
    except Exception:                                           # noqa: BLE001
        pass

    report = "\n".join(lines)
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        open(summary, "a", encoding="utf-8").write(report + "\n")
    if args.write_state:
        save(STATE, {"_readme": "Written by tools/anandamakaranda/sync_anandamakaranda.py: the wiki revision last synced for each SarvaMūla work, and whether that layer merges one-to-one or is snapshotted. Delete an entry to force a re-sync.",
                     "checked_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "pages": seen})
    print(f"\n{written} file(s) written" if args.write else "\n(report only — add --write to merge)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
