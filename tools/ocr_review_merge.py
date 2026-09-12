#!/usr/bin/env python3
"""
ocr_review_merge.py — turn a scholar's approved OCR text into a library layer.

admin/ocr-review.html shows a staged OCR file beside the page scans and lets
a reviewer accept, edit or reject each unit. Its decisions are saved as
<same folder>/review/<staged basename>.decisions.json:

    {"_readme": …, "staged": "<path>", "decisions": {
       "<unit id>": {"decision": "accept|edit|reject", "text": "<final text>",
                     "note": "…", "by": "<name>", "at": "<ISO>"} … }}

This script reads the staged file and the decisions and writes the result
where the library can see it. Two modes, by what the staged file is:

  * page / block OCR (vision_pages_*.json, sarvam_pages*.json, an
    upanishad blocks file, an anandamakaranda snapshot) → a NEW OR UPDATED
    LAYER data.json at --target, schema grantha_tika_text / grantha_tippani_text
    / grantha_mula_text, one item per approved unit, merged by id when the
    target exists (--mode append|replace).
  * a Gemini commentary staged file (shlokas[] with classification) → an
    "approved" copy of the staged file (<name>.approved.json) in which the
    reviewer's decisions are folded into `sa`/`commentary` and
    `classification`, so the existing tools/merge_staged_commentary.py can
    merge it into the sarga exactly as before (--sarga-dir runs it for you).

Undecided units are left out unless --include-undecided. Rejected units are
never written. Every written item records the decision under
verification.human, so a later run never applies it twice.

    python3 tools/ocr_review_merge.py --staged dge/data/ocr_staging/isha/vision_pages_1-292.json \
        --target dge/data/darshana/vedanta/dvaita/DvaitaVedantaIn/upanishad_prasthana/isha/tippani_x/data.json \
        --schema grantha_tippani_text --title "ईशावास्योपनिषद्भाष्यटिप्पणी" --author "श्री…" --mode append
    python3 tools/ocr_review_merge.py --staged dge/data/ocr_staging/kumara/mallinatha_canto1_pages1-40.json \
        --sarga-dir dge/data/kavya_alankara/kumarasambhava
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from html.parser import HTMLParser

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(p):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def save(p, d):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(d, fh, ensure_ascii=False, indent=1)
        fh.write("\n")


def decisions_path(staged):
    d, b = os.path.split(staged)
    return os.path.join(d, "review", re.sub(r"\.json$", "", b) + ".decisions.json")


# ---------------------------------------------------------------- units
def html_to_text(html):
    html = re.sub(r"<(br|/p|/div|/h[1-6]|/li|/tr)[^>]*>", "\n", html, flags=re.I)
    html = re.sub(r"<[^>]+>", "", html)
    html = html.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return re.sub(r"\n{3,}", "\n\n", html).strip()


#: Elements that start a new reviewable block. Everything else (inline
#: markup, bare text) is gathered into the block it sits in.
_BLOCK_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "blockquote",
               "div", "ul", "ol", "table", "pre", "section", "article"}


class _BlockSplitter(HTMLParser):
    """Split a page of HTML into top-level blocks, each keeping its own markup.

    Why this exists (11 Sep 2026). This module used to turn a Sarvam page into
    blocks by splitting its PLAIN TEXT on blank lines and throwing the HTML
    away — so the layout-preserving engine's entire output was reduced to
    strings before a reviewer ever saw it, and a heading was indistinguishable
    from a line of verse. Splitting on element boundaries instead keeps each
    block's own markup, which is what the reviewer edits and what the layer
    now stores.

    Deliberately simple: it tracks nesting depth and closes a fragment when
    depth returns to zero. Malformed markup degrades to fewer, larger blocks
    rather than to an exception — a coarse review beats a crashed import.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks = []
        self._buf = []
        self._depth = 0

    def _flush(self):
        frag = "".join(self._buf).strip()
        self._buf = []
        if frag:
            self.blocks.append(frag)

    def handle_starttag(self, tag, attrs):
        if self._depth == 0 and tag in _BLOCK_TAGS:
            self._flush()
        self._buf.append(self.get_starttag_text() or f"<{tag}>")
        if tag not in ("br", "img", "hr", "meta", "link", "input"):
            self._depth += 1

    def handle_startendtag(self, tag, attrs):
        self._buf.append(self.get_starttag_text() or f"<{tag}/>")

    def handle_endtag(self, tag):
        self._buf.append(f"</{tag}>")
        if self._depth > 0:
            self._depth -= 1
        if self._depth == 0 and tag in _BLOCK_TAGS:
            self._flush()

    def handle_data(self, data):
        self._buf.append(data)

    def close(self):
        super().close()
        self._flush()


def split_html_blocks(html):
    """[(html fragment, plain text), …] for one page of layout-preserving OCR."""
    sp = _BlockSplitter()
    try:
        sp.feed(html or "")
        sp.close()
    except Exception:                                     # pragma: no cover
        # Never let one odd page stop an import; fall back to the whole page.
        return [(html, html_to_text(html))] if (html or "").strip() else []
    out = []
    for frag in sp.blocks:
        text = html_to_text(frag).strip()
        if text:
            out.append((frag, text))
    return out


def units_of(staged):
    """The same unit model admin/ocr-review.html builds: [{id, page, text, kind}]."""
    units = []
    # vasu/lakshmi staged files carry `pages: [start, end]` (ints) beside
    # `entries[]`; only a list of page OBJECTS is page OCR.
    page_objs = isinstance(staged.get("pages"), list) and staged["pages"] and isinstance(staged["pages"][0], dict)
    if isinstance(staged.get("entries"), list):
        for e in staged["entries"]:
            units.append({"id": f"sk{e.get('sk')}", "page": e.get("page"), "text": (e.get("english") or "").strip(), "kind": "entry", "reference": str(e.get("sk"))})
        return "layer", units
    if isinstance(staged.get("shlokas"), list):
        return "commentary", None
    if page_objs and staged.get("engine") == "sarvam-docai":
        for pg in staged["pages"]:
            if not pg.get("ok", True):
                continue
            if pg.get("html"):
                # Split on ELEMENT boundaries, keeping each block's markup —
                # see _BlockSplitter above for why blank-line splitting was
                # wrong here.
                for n, (frag, text) in enumerate(split_html_blocks(pg["html"]), 1):
                    units.append({"id": f"p{pg['page']}_b{n}", "page": pg["page"],
                                  "text": text, "html": frag, "kind": "block"})
                continue
            body = pg.get("md") or (json.dumps(pg.get("json"), ensure_ascii=False) if pg.get("json") else "")
            for n, chunk in enumerate([c for c in re.split(r"\n\s*\n", body) if c.strip()], 1):
                units.append({"id": f"p{pg['page']}_b{n}", "page": pg["page"], "text": chunk.strip(), "kind": "block"})
        return "layer", units
    if page_objs:
        for pg in staged["pages"]:
            for n, chunk in enumerate([c for c in re.split(r"\n\s*\n", pg.get("text") or "") if c.strip()], 1):
                units.append({"id": f"p{pg['page']}_b{n}", "page": pg["page"], "text": chunk.strip(), "kind": "block"})
        return "layer", units
    if isinstance(staged.get("blocks"), list):
        for b in staged["blocks"]:
            units.append({"id": b.get("id"), "page": b.get("page"), "text": (b.get("vision_text") or b.get("text") or "").strip(), "kind": b.get("type") or b.get("label") or "block"})
        return "layer", units
    raise SystemExit("staged file shape not recognised (expected pages[], blocks[], entries[] or shlokas[])")


# ---------------------------------------------------------------- layer
def build_layer(staged, decisions, args):
    kind, units = units_of(staged)
    if kind != "layer":
        raise SystemExit("this staged file is a Gemini commentary file — use --sarga-dir")
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    items = []
    counts = {"accept": 0, "edit": 0, "reject": 0, "undecided": 0}
    for u in units:
        d = decisions.get(u["id"])
        if not d:
            counts["undecided"] += 1
            if not args.include_undecided:
                continue
            text, dec = u["text"], "undecided"
        elif d.get("decision") == "reject":
            counts["reject"] += 1
            continue
        else:
            dec = d.get("decision", "accept")
            counts[dec if dec in counts else "accept"] += 1
            text = (d.get("text") if dec == "edit" and d.get("text") is not None else u["text"]).strip()
        if not text:
            continue
        # The reviewer's STRUCTURE, not only their text (11 Sep 2026).
        # admin/ocr-review.html now edits the rendered layout itself, so a
        # decision can carry `html` — headings still headings, indentation
        # still indentation, and <b> where a प्रतीक was marked. Running a
        # layout-preserving OCR engine and then storing a flat string threw
        # away the entire reason for running it.
        # The reviewer's edited markup if they touched it, otherwise the
        # engine's own. A decision that carries no html (an older client, or a
        # plain accept) must NOT fall back to nothing — that would throw the
        # layout away on exactly the units nobody needed to correct.
        structured = (d or {}).get("html") or u.get("html")
        item = {
            "id": f"{args.id_prefix}{u['id']}",
            "reference": u.get("reference") or (f"p.{u['page']}" if u.get("page") is not None else u["id"]),
            "sanskrit_text": text,
            "artha": "", "notes": "", "tags": [t for t in [u.get("kind")] if t and t != "block"], "references": [], "audio": [],
            "source": {"staged": os.path.relpath(args.staged, REPO), "unit": u["id"], "page": u.get("page"),
                       "engine": staged.get("engine") or staged.get("model") or "vision"},
            "verification": {"human": {"decision": dec, "by": (d or {}).get("by", ""), "at": (d or {}).get("at", now),
                                       "note": (d or {}).get("note", "")}},
        }
        # sanskrit_text stays the plain string every existing consumer reads;
        # the structure rides alongside it rather than replacing it, so this
        # change cannot break a reader that has never heard of it.
        if structured:
            item["sanskrit_html"] = structured
        if args.schema == "grantha_tippani_text":
            item["author"] = args.author
        items.append(item)

    target = os.path.join(REPO, args.target)
    if os.path.exists(target) and args.mode == "append":
        doc = load(target)
        have = {it.get("id"): i for i, it in enumerate(doc.get("items") or [])}
        merged = list(doc.get("items") or [])
        for it in items:
            if it["id"] in have:
                merged[have[it["id"]]] = it
            else:
                merged.append(it)
        doc["items"] = merged
    else:
        doc = {"schema": args.schema, "default_author": args.author, "title": args.title,
               "title_devanagari": args.title_devanagari or args.title,
               "source": f"OCR staged in {os.path.relpath(args.staged, REPO)}, reviewed in admin/ocr-review.html",
               "items": items}
        if args.schema == "grantha_tippani_text":
            doc["tippani_title"] = args.title
    doc["review"] = {"decisions": os.path.relpath(args.decisions, REPO), "merged_at": now, "counts": counts}
    if not args.dry_run:
        save(target, doc)
        meta = os.path.join(os.path.dirname(target), "_meta.json")
        if not os.path.exists(meta):
            save(meta, {"directory": os.path.basename(os.path.dirname(target)), "description": args.title, "schema": args.schema})
    return counts, len(doc["items"])


# ---------------------------------------------------------------- commentary
def build_approved_commentary(staged, decisions, args):
    counts = {"accept": 0, "edit": 0, "reject": 0, "undecided": 0}
    out = json.loads(json.dumps(staged))
    for s in out.get("shlokas", []):
        uid = f"v{s.get('number')}"
        d = decisions.get(uid)
        if not d:
            counts["undecided"] += 1
            if not args.include_undecided:
                s["classification"] = "unresolved"
            continue
        if d.get("decision") == "reject":
            counts["reject"] += 1
            s["classification"] = "unresolved"
            s["note"] = ("rejected in review: " + (d.get("note") or "")).strip()
            continue
        dec = d.get("decision", "accept")
        counts[dec if dec in counts else "accept"] += 1
        if dec == "edit":
            fields = d.get("fields") or {}
            if "sa" in fields:
                s["sa"] = fields["sa"]
            if "commentary" in fields:
                s["commentary"] = fields["commentary"]
            elif d.get("text") is not None:
                s["commentary"] = d["text"]
        s["classification"] = "accept"
        s["verification"] = {"human": {"decision": dec, "by": d.get("by", ""), "at": d.get("at", ""), "note": d.get("note", "")}}
    approved = re.sub(r"\.json$", "", args.staged) + ".approved.json"
    if not args.dry_run:
        save(approved, out)
        if args.sarga_dir:
            subprocess.check_call([sys.executable, os.path.join(REPO, "tools", "merge_staged_commentary.py"),
                                   "--staged", approved, "--sarga-dir", args.sarga_dir])
    return counts, approved


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--staged", required=True)
    ap.add_argument("--decisions", help="default: <dir>/review/<name>.decisions.json")
    ap.add_argument("--target", help="layer data.json to write (page/block OCR)")
    ap.add_argument("--schema", default="grantha_tika_text", choices=["grantha_tika_text", "grantha_tippani_text", "grantha_mula_text"])
    ap.add_argument("--title", default="")
    ap.add_argument("--title-devanagari", default="")
    ap.add_argument("--author", default="")
    ap.add_argument("--id-prefix", default="")
    ap.add_argument("--mode", default="append", choices=["append", "replace"])
    ap.add_argument("--sarga-dir", help="for a Gemini commentary staged file: run merge_staged_commentary.py into this sarga dir")
    ap.add_argument("--include-undecided", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    args.staged = os.path.abspath(args.staged)
    args.decisions = os.path.abspath(args.decisions or decisions_path(args.staged))
    staged = load(args.staged)
    decisions = load(args.decisions).get("decisions", {}) if os.path.exists(args.decisions) else {}
    if not decisions:
        print(f"no decisions at {os.path.relpath(args.decisions, REPO)} — nothing approved yet", file=sys.stderr)
        return 2

    kind, _ = units_of(staged)
    if kind == "commentary":
        counts, out = build_approved_commentary(staged, decisions, args)
        print(f"commentary: {counts} → {os.path.relpath(out, REPO)}" + (f" → merged into {args.sarga_dir}" if args.sarga_dir and not args.dry_run else ""))
    else:
        if not args.target:
            raise SystemExit("--target is required for page/block OCR")
        if not args.title:
            raise SystemExit("--title is required for a new layer")
        counts, n = build_layer(staged, decisions, args)
        print(f"layer: {counts} → {args.target} now holds {n} items" + (" (dry run)" if args.dry_run else ""))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        open(summary, "a", encoding="utf-8").write(f"## OCR review merge\n\n`{os.path.relpath(args.staged, REPO)}` → decisions {counts}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
