#!/usr/bin/env python3
"""setutila.in importer — the second Sarvamula edition (Setu Tila).

Site anatomy (recon 4 Sep 2026): WordPress; every work is one post whose
content embeds a chunked static book: window.__BOOK_CHUNKS__ lists per-
chapter chunk files under /wp-content/themes/twentytwentyfour/texts/<work>/,
each block is a <div class='<Type> block-container'> carrying a STABLE UUID
anchor, and chapter-NNN.pathantara.json maps block UUIDs to variant
readings across editions (setutila / trk_patha / bg_patha) — SetuTila's own
cross-edition apparatus, which is exactly what lets us align this edition
against our SarvaMula (AnandaMakaranda) copy later.

Lessons applied (see tools/reports/importer_lessons.md):
- LAZY CONTENT IS THE CORPUS: harvest the chunk files the page lazy-loads,
  never just the rendered post body (the DvaitaVedanta harvest-gap lesson).
- RAW HTML IS KEPT: chunk files land verbatim under _raw/<slug>/ (bold,
  headings, classes, uuid anchors intact) so any future re-parse or
  restructure needs no re-crawl.
- AUTO-SYNC BY DESIGN: wp-json modified_gmt is the cheap delta probe;
  _sync_state.json records it per post + a hash per chunk, so re-runs
  download only what changed (run via the extract-setutila workflow).
- ONE READER SCHEMA: parsed output uses the SAME grantha_tika_text item
  shape as the DvaitaVedanta corpus, so reader/validators/search work
  unchanged; SetuTila extras ride in additive fields (block_uuid, cls,
  pathantara inside references, attribution metadata).
- FUTURE RESTRUCTURE IN MIND: every item keeps its source block UUID and
  chunk id — the grantha_v2 compiler (or a move into DvaitaVedanta trees)
  can re-key without information loss.

Usage:
  python3 tools/setutila/import_setutila.py            # sync everything
  python3 tools/setutila/import_setutila.py --slugs brahmasutra-bhashya
  python3 tools/setutila/import_setutila.py --force    # ignore sync state
"""
import argparse, datetime, hashlib, html, json, os, re, sys, time
import urllib.parse, urllib.request

BASE = "https://setutila.in"
OUT = "data/DvaitaVedanta/SarvaMula"
UA = {"User-Agent": "Mozilla/5.0 (DGE importer; bhumandala project; contact via site)"}
SLEEP = 0.35

# category (Devanagari name) -> folder. Mirrors the DvaitaVedanta naming
# where the same shelf exists, so a later merge is a move, not a rename.
CAT_DIRS = {
    "सूत्रप्रस्थानम्": "sutra_prasthana",
    "गीताप्रस्थानम्": "gita_prasthana",
    "उपनिषत्प्रस्थानम्": "upanishat_prasthana",
    "इतिहासप्रस्थानम्": "itihasa_prasthana",
    "पुराणप्रस्थानम्": "purana_prasthana",
    "श्रुतिप्रस्थानम्": "shruti_prasthana",
    "दशप्रकरणानि": "dasha_prakarana_granthas",
    "आचारग्रन्थाः": "achara_granthas",
    "स्तोत्रग्रन्थाः": "stotra_granthas",
    "मूलग्रन्थाः": "mula_granthas",
    "महाभारतम्": "mula_granthas/mahabharata",
    "Uncategorized": "misc",
}

_DEV = {'अ':'a','आ':'aa','इ':'i','ई':'ii','उ':'u','ऊ':'uu','ऋ':'r','ॠ':'rr','ए':'e','ऐ':'ai',
        'ओ':'o','औ':'au','ं':'m','ः':'h','ँ':'m',
        'क':'k','ख':'kh','ग':'g','घ':'gh','ङ':'n','च':'ch','छ':'chh','ज':'j','झ':'jh','ञ':'n',
        'ट':'t','ठ':'th','ड':'d','ढ':'dh','ण':'n','त':'t','थ':'th','द':'d','ध':'dh','न':'n',
        'प':'p','फ':'ph','ब':'b','भ':'bh','म':'m','य':'y','र':'r','ल':'l','व':'v',
        'श':'sh','ष':'sh','स':'s','ह':'h','ळ':'l',
        'ा':'aa','ि':'i','ी':'ii','ु':'u','ू':'uu','ृ':'r','े':'e','ै':'ai','ो':'o','ौ':'au','्':''}
def dev_slug(text):
    out = []
    for ch in text:
        if ch in _DEV: out.append(_DEV[ch])
        elif re.match(r'[a-zA-Z0-9]', ch): out.append(ch.lower())
        elif out and out[-1] != '_' and ch in ' -–—/·.': out.append('_')
    s = re.sub(r'_+', '_', ''.join(out)).strip('_')
    return s or 'work'

def fetch(url, binary=False):
    time.sleep(SLEEP)
    req = urllib.request.Request(url, headers=UA)
    data = urllib.request.urlopen(req, timeout=60).read()
    return data if binary else data.decode("utf-8", "replace")

def fetch_json(url):
    return json.loads(fetch(url))

def sha(s):
    return hashlib.sha256(s.encode("utf-8") if isinstance(s, str) else s).hexdigest()[:16]

TOOLS_RE = re.compile(r"<div class=['\"]block-tools['\"]>.*?</div>", re.S)
BLOCK_RE = re.compile(
    r"<div class='([A-Za-z0-9_]+) block-container'( data-uuid='([0-9a-f-]+)')?>(.*?)</div>\s*(?=<div class='[A-Za-z0-9_]+ block-container'|\Z)",
    re.S)
# a handful of shorter works (upadhi-khandhana, ishavasya-bhashya,
# yati-pranava-kalpa) skip the chunk-file system entirely and inline the
# same block-container markup straight in the post body, double-quoted
BLOCK_START_RE = re.compile(r"<div class=[\"']([A-Za-z0-9_]+) block-container[\"'][^>]*>")
UUID_IN_TOOLS = re.compile(r'copyBlockLink\((?:"|&quot;)([0-9a-f-]+)(?:"|&quot;)\)')
TAG_RE = re.compile(r"<[^>]+>")

def parse_blocks(chunk_html):
    """Split a chunk into typed blocks, keeping raw html per block and the
    stable uuid the site's own link/copy tooling uses."""
    blocks = []
    for m in BLOCK_RE.finditer(chunk_html):
        cls, _, uuid_attr, body = m.group(1), m.group(2), m.group(3), m.group(4)
        um = UUID_IN_TOOLS.search(body)
        uuid = uuid_attr or (um.group(1) if um else None)
        clean = TOOLS_RE.sub("", body)
        text = html.unescape(TAG_RE.sub(" ", clean))
        text = re.sub(r"\s+", " ", text).strip()
        blocks.append({"cls": cls, "uuid": uuid, "html": clean.strip(), "text": text})
    return blocks

def parse_blocks_inline(body):
    """Fallback for posts whose blocks are inlined in the post body itself
    (no __BOOK_CHUNKS__): slice between consecutive block-container starts.
    Same block vocabulary, but double-quoted attrs and trailing TOC/scripts."""
    starts = list(BLOCK_START_RE.finditer(body))
    blocks = []
    for i, m in enumerate(starts):
        end = starts[i + 1].start() if i + 1 < len(starts) else len(body)
        seg = body[m.end():end]
        if i + 1 == len(starts):
            cut = seg.find("<script")
            if cut >= 0:
                seg = seg[:cut]
        # trailing run of </div> = the block's own closer + page wrappers
        seg = re.sub(r"(\s*</div>)+\s*$", "", seg)
        um = UUID_IN_TOOLS.search(seg)
        clean = TOOLS_RE.sub("", seg)
        text = html.unescape(TAG_RE.sub(" ", clean))
        text = re.sub(r"\s+", " ", text).strip()
        blocks.append({"cls": m.group(1), "uuid": um.group(1) if um else None,
                       "html": clean.strip(), "text": text})
    return blocks

def attribution(url):
    return {
        "source_name": "setutila.in",
        "source_url": url,
        "accessed_date": datetime.date.today().isoformat(),
        "license_notes": "Public Sarvamula edition site; imported for "
                         "non-commercial study with attribution; raw source "
                         "preserved under _raw/ for provenance.",
    }

def import_post(post, cats_by_id, state, force, summary):
    slug = post["slug"]
    title = html.unescape(post["title"]["rendered"])
    mod = post["modified_gmt"]
    st = state["posts"].get(slug, {})
    if not force and st.get("modified_gmt") == mod:
        summary["skipped"] += 1
        return

    body = post["content"]["rendered"]
    m = re.search(r"__BOOK_CHUNKS__\s*=\s*(\[[\s\S]*?\]);", body)
    chunks = json.loads(m.group(1)) if m else []
    inline = not chunks and BLOCK_START_RE.search(body) is not None
    if not chunks and not inline:
        # no chunk manifest AND no inline blocks: not a text post at all
        # (e.g. WordPress's stock hello-world) — record and write nothing
        state["posts"][slug] = {"modified_gmt": mod, "chunk_hashes": {},
                                "work_dir": None, "items": 0,
                                "note": "no book content"}
        print(f"  {slug}: no book content, skipped")
        return
    cat_names = [cats_by_id.get(c, "") for c in post.get("categories", [])]
    cat_dir = next((CAT_DIRS[c] for c in cat_names if c in CAT_DIRS), "misc")
    wslug = slug if re.match(r"^[a-z0-9-]+$", slug) else dev_slug(title)
    wdir = os.path.join(OUT, cat_dir, wslug.replace("-", "_"))
    raw_dir = os.path.join(OUT, "_raw", wslug.replace("-", "_"))
    os.makedirs(wdir, exist_ok=True)
    os.makedirs(raw_dir, exist_ok=True)

    if inline:
        # the post body itself is the (single) chunk
        chunks = [{"id": "inline", "title": title, "file": None}]
    items, chunk_meta, chunk_hashes = [], [], {}
    post_errors = []
    seq = 0
    for ch in chunks:
        cid = ch["id"]
        if ch["file"] is None:
            chtml = body
            chunk_hashes[cid] = sha(chtml)
            with open(os.path.join(raw_dir, "inline.body.html"), "w", encoding="utf-8") as f:
                f.write(chtml)
        else:
            # the chunk FILE is authoritative (chunk 0 is also inlined in the
            # post body, but the file exists for all of them)
            churl = BASE + ch["file"]
            try:
                chtml = fetch(churl)
            except Exception as e:
                summary["errors"].append(f"{slug}/{cid}: {e}")
                post_errors.append(f"{cid}: {e}")
                continue
            chunk_hashes[cid] = sha(chtml)
            with open(os.path.join(raw_dir, os.path.basename(ch["file"])), "w", encoding="utf-8") as f:
                f.write(chtml)
        pt = {}
        if ch.get("pathantara_file"):
            try:
                pt = fetch_json(BASE + ch["pathantara_file"])
                with open(os.path.join(raw_dir, os.path.basename(ch["pathantara_file"])), "w", encoding="utf-8") as f:
                    json.dump(pt, f, ensure_ascii=False, indent=0)
            except Exception as e:
                summary["errors"].append(f"{slug}/{cid} pathantara: {e}")
                post_errors.append(f"{cid} pathantara: {e}")
        com_html = None
        if ch.get("commentary_file"):
            try:
                com_html = fetch(BASE + ch["commentary_file"])
                with open(os.path.join(raw_dir, os.path.basename(ch["commentary_file"])), "w", encoding="utf-8") as f:
                    f.write(com_html)
            except Exception as e:
                summary["errors"].append(f"{slug}/{cid} commentary: {e}")
                post_errors.append(f"{cid} commentary: {e}")

        blocks = parse_blocks_inline(chtml) if ch["file"] is None else parse_blocks(chtml)
        sec_title = ch.get("title") or cid
        cur_heads = []
        for b in blocks:
            if b["cls"].startswith("Heading"):
                lvl = int(b["cls"][7:8] or "1")
                cur_heads = cur_heads[:lvl - 1] + [b["text"]]
            seq += 1
            refs = []
            if b["uuid"] and b["uuid"] in pt:
                refs.append({"kind": "pathantara", "block": b["uuid"],
                             "readings": pt[b["uuid"]]})
            items.append({
                "id": f"ST_{wslug.replace('-', '_')}_{seq:05d}",
                "reference": " > ".join([title, sec_title] + cur_heads[:2]),
                "section": sec_title,
                "unit_title": (b["text"][:80] if b["cls"].startswith("Heading") else ""),
                "sanskrit_text": b["text"],
                "artha": "", "notes": "", "tags": [b["cls"]],
                "references": refs, "audio": [],
                "breadcrumb": [cat_names[0] if cat_names else "", title, sec_title] + cur_heads[:2],
                "source": {"site": "setutila.in", "url": post["link"] + "#" + (b["uuid"] or cid),
                           "chunk": cid, "block_uuid": b["uuid"], "cls": b["cls"]},
                "source_html": b["html"],
            })
        chunk_meta.append({"id": cid, "title": sec_title, "file": ch["file"],
                           "anchor": ch.get("anchor"), "blocks": len(blocks),
                           "pathantara_entries": len(pt),
                           "has_commentary": bool(ch.get("commentary_file"))})

    with open(os.path.join(raw_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"post_id": post["id"], "slug": slug, "title": title,
                   "link": post["link"], "modified_gmt": mod,
                   "categories": cat_names, "chunks": chunk_meta,
                   "attribution": attribution(post["link"])},
                  f, ensure_ascii=False, indent=1)

    with open(os.path.join(wdir, "data.json"), "w", encoding="utf-8") as f:
        json.dump({
            "schema": "grantha_tika_text",
            "default_author": "श्रीमदानन्दतीर्थभगवत्पादाचार्यः",
            "source_url": post["link"],
            "source_note": "Setu Tila edition of the Sarvamula (setutila.in); "
                           "block UUIDs and pathantara variant readings "
                           "preserved for cross-edition alignment.",
            "attribution": attribution(post["link"]),
            "title": title,
            "items": items,
        }, f, ensure_ascii=False, indent=1)

    state["posts"][slug] = {"modified_gmt": mod, "chunk_hashes": chunk_hashes,
                            "work_dir": wdir, "items": len(items)}
    if post_errors:
        # persisted so a later --force / delta run knows what is still
        # missing upstream (e.g. chunk files the site's own manifest lists
        # but its server 404s on)
        state["posts"][slug]["errors"] = post_errors
    summary["imported"] += 1
    summary["items"] += len(items)
    print(f"  {slug}: {len(chunks)} chunks, {len(items)} items -> {wdir}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slugs", help="comma-separated post slugs (default: all)")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    os.makedirs(os.path.join(OUT, "_raw"), exist_ok=True)
    state_path = os.path.join(OUT, "_sync_state.json")
    state = {"posts": {}}
    if os.path.exists(state_path):
        state = json.load(open(state_path))

    cats = []
    page = 1
    while True:
        batch = fetch_json(f"{BASE}/wp-json/wp/v2/categories?per_page=100&page={page}")
        cats += batch
        if len(batch) < 100: break
        page += 1
    cats_by_id = {c["id"]: html.unescape(c["name"]) for c in cats}

    posts = []
    page = 1
    while True:
        batch = fetch_json(f"{BASE}/wp-json/wp/v2/posts?per_page=20&page={page}")
        posts += batch
        if len(batch) < 20: break
        page += 1
    want = set((args.slugs or "").split(",")) if args.slugs else None
    summary = {"imported": 0, "skipped": 0, "items": 0, "errors": []}
    for p in posts:
        if want and p["slug"] not in want: continue
        try:
            import_post(p, cats_by_id, state, args.force, summary)
        except Exception as e:
            summary["errors"].append(f"{p['slug']}: {e}")
        json.dump(state, open(state_path, "w"), ensure_ascii=False, indent=1)

    print(f"\nimported {summary['imported']} works ({summary['items']} items), "
          f"skipped {summary['skipped']} unchanged, {len(summary['errors'])} errors")
    for e in summary["errors"][:20]: print("  ERR", e)
    return 1 if summary["errors"] else 0

if __name__ == "__main__":
    sys.exit(main())
