#!/usr/bin/env python3
"""Phase 0 of the DGE frontend redesign: inventory every page's shared-chrome
wiring and guard against regressions as later phases touch it.

Usage:
    python3 tools/redesign/audit_pages.py            # write page_inventory.json
    python3 tools/redesign/audit_pages.py --check     # also fail (exit 1) if
                                                       # vandana-guard.js isn't
                                                       # the first <head> script
                                                       # on any gated page

Gated pages are every **/*.html and admin/**/*.html file EXCEPT the
landing/vandana-gate page itself (root index.html), which vandana-guard.js
exists to redirect *to* and therefore never loads.
"""
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_PATH = Path(__file__).resolve().parent / "page_inventory.json"

SCRIPT_SRC_RE = re.compile(r'<script\b[^>]*\bsrc=["\']([^"\']+)["\']', re.IGNORECASE)
LINK_CSS_RE = re.compile(
    r'<link\b[^>]*\brel=["\']stylesheet["\'][^>]*\bhref=["\']([^"\']+)["\']'
    r'|<link\b[^>]*\bhref=["\']([^"\']+\.css[^"\']*)["\'][^>]*\brel=["\']stylesheet["\']',
    re.IGNORECASE,
)
HEAD_RE = re.compile(r"<head\b[^>]*>(.*?)</head>", re.IGNORECASE | re.DOTALL)

WATCHED_SCRIPTS = ("vandana-guard.js", "site-footer.js", "ai.js", "modals.js")

# Pages that are gated by definition (everything but the landing page) but
# are known, already-documented exceptions to "vandana-guard.js loads
# first" -- listed explicitly so a real regression elsewhere never hides
# behind a silently-ignored legacy page. Each entry names why.
KNOWN_VANDANA_EXCEPTIONS = {
    "legacy/PrahladaKrutaNarasimhaStotra.html": (
        "Explicitly legacy/archived; predates vandana-guard.js and the "
        "current template system entirely. Out of scope for the redesign."
    ),
}


def discover_pages():
    # rglob walks into node_modules too -- harmless for the checked-in tree
    # (nothing under the site root or admin/ has one), but firebase/{functions,
    # tests}/node_modules/ is real: `npm install` there for the Firebase
    # test suite drops plenty of *.html (docs, fixtures, templates) that
    # were never a DGE page and never will be. Excluded here rather than
    # narrowing the rglob pattern, so a real future subfolder under the site root or
    # admin/ still gets picked up by default.
    def real_pages(root, skip_top=()):
        # data/ holds source material, not pages: SetuTila's _raw/
        # chapter chunks are the site's own HTML kept verbatim for
        # provenance (317 files) and must never be audited as DGE chrome.
        # .claude/ can hold a full nested worktree checkout (a background
        # agent's isolated copy of this repo) once dge/ stops being the
        # only thing rglob'd here -- excluded the same way node_modules is.
        return sorted(p for p in root.rglob("*.html")
                      if "node_modules" not in p.parts and ".claude" not in p.parts
                      and p.relative_to(root).parts[0] not in skip_top)

    pages = [REPO_ROOT / "index.html"]
    # dge/ moved to the repo root (12 Sep 2026); admin/ and data/ are walked
    # separately below (data/ excluded, never audited as DGE chrome), and
    # root index.html is already in the list above.
    pages.extend(p for p in real_pages(REPO_ROOT, skip_top={"admin", "data"}) if p != REPO_ROOT / "index.html")
    pages.extend(real_pages(REPO_ROOT / "admin"))
    return pages


def is_gated(path: Path) -> bool:
    """Every page except the landing/vandana-gate itself is expected to load
    vandana-guard.js as its first head script."""
    return path != REPO_ROOT / "index.html"


def script_names_in_order(head_html: str):
    return [Path(src.split("?")[0]).name for src in SCRIPT_SRC_RE.findall(head_html)]


def audit_page(path: Path):
    text = path.read_text(encoding="utf-8", errors="replace")
    head_match = HEAD_RE.search(text)
    head_html = head_match.group(1) if head_match else ""

    scripts_in_head = script_names_in_order(head_html)
    all_scripts = [Path(src.split("?")[0]).name for src in SCRIPT_SRC_RE.findall(text)]
    css_links = [
        (a or b).split("?")[0]
        for a, b in LINK_CSS_RE.findall(text)
    ]

    rel = path.relative_to(REPO_ROOT).as_posix()
    gated = is_gated(path)
    first_head_script = scripts_in_head[0] if scripts_in_head else None
    vandana_first = (first_head_script == "vandana-guard.js") if gated else None

    return {
        "path": rel,
        "gated": gated,
        "first_head_script": first_head_script,
        "vandana_guard_first": vandana_first,
        "has_site_footer_js": "site-footer.js" in all_scripts,
        "has_ai_js": "ai.js" in all_scripts,
        "has_modals_js": "modals.js" in all_scripts,
        "css_links": css_links,
        "title": _extract_title(text),
    }


def _extract_title(text: str):
    m = re.search(r"<title>(.*?)</title>", text, re.IGNORECASE | re.DOTALL)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else None


def main():
    check_mode = "--check" in sys.argv
    pages = discover_pages()
    records = [audit_page(p) for p in pages]

    OUT_PATH.write_text(
        json.dumps({"page_count": len(records), "pages": records}, indent=1, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"audit_pages: wrote {OUT_PATH.relative_to(REPO_ROOT)} ({len(records)} pages)")

    if not check_mode:
        return 0

    failures = [
        r["path"]
        for r in records
        if r["gated"]
        and r["vandana_guard_first"] is not True
        and r["path"] not in KNOWN_VANDANA_EXCEPTIONS
    ]
    known = [r["path"] for r in records if r["path"] in KNOWN_VANDANA_EXCEPTIONS]

    if failures:
        print("audit_pages --check: vandana-guard.js is NOT the first <head> script on:")
        for f in failures:
            print(f"  - {f}")
        return 1

    checked = len(pages) - 1 - len(known)
    print(f"audit_pages --check: OK -- vandana-guard.js is first on all {checked} gated pages")
    for k in known:
        print(f"  (known exception, not checked: {k} -- {KNOWN_VANDANA_EXCEPTIONS[k]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
