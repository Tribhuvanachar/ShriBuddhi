#!/usr/bin/env python3
"""Generate sitemap.xml for the DGE static site.

Why this exists
----------------
This is a plain GitHub Pages site with no server-side routing, so search
engines have no way to discover a grantha except by crawling the reader's
own client-side navigation -- which they generally don't execute. A
sitemap gives them the URL list directly.

The one rule that matters: never list a URL a reader can't actually reach.
dge/js/core.js will not fetch a grantha that has no library.json entry,
and short-circuits to "Not Yet Available" when `populated` is false (see
tools/audit_library.py's own docstring, which this project has been
bitten by before). So this walks dge/data/library.json and includes only
`populated: true` entries, applying the exact same admin-only/hidden
filters dge/js/library.js itself applies before showing a grantha to an
ordinary reader (a per-entry "hidden" flag, plus library-overrides.json's
admin-curated hidden path-prefix list) -- a URL that's admin-only or
curated out of the reader nav has no business being offered to search
engines either.

Grantha URLs are derived the same way dge/js/core.js's
dgeGranthaSlug()/dgeGoToGrantha() derive them at runtime: strip the
leading `dge/data/` and trailing `/data.json` from the catalog path to
get a slug, then point at `dge/index.html?path=<slug>`. Static pages
(the landing page, the vyakarana tools, kavya/tirtha/etc. section
fronts, ...) are a short explicit list below -- deliberately not a glob
over dge/**/*.html, since that would just as happily pick up
dge/convert/index.html (an admin import tool) or a data-completeness
tracker (dge/guru-parampara/tracker.html, marked data-admin-only in its
own nav card) as a real reader page.

lastmod per entry is whichever of (a) library.json's own `addedAt` field
and (b) the most recent git commit that touched the underlying file is
later -- a grantha can be edited well after it was first added, and a
static page has no addedAt at all, so git history is the only signal
for those. One `git log --name-only` pass over just the paths this
script cares about resolves every file's last-touched date in a single
subprocess call rather than one `git log` per file.

Usage:
    python3 tools/build_sitemap.py            # write sitemap.xml, sync robots.txt
    python3 tools/build_sitemap.py --check    # fail (exit 1) if either is stale --
                                               # the CI drift gate
"""
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent))
from set_site_url import load_config, build_url, SiteUrlError  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
LIBRARY_JSON = REPO_ROOT / "dge" / "data" / "library.json"
OVERRIDES_JSON = REPO_ROOT / "admin" / "config" / "library-overrides.json"
SITEMAP_PATH = REPO_ROOT / "sitemap.xml"
ROBOTS_PATH = REPO_ROOT / "robots.txt"

# Real top-level reader-facing pages, as of 28 Aug 2026 -- the site's
# structure changed the same day this was written, so this was checked
# against the actual file tree rather than copied from an older list.
# Excluded on purpose: dge/convert/index.html (admin import tool),
# dge/dvaitavedanta-status.html (admin-gated progress dashboard),
# dge/guru-parampara/tracker.html (data-admin-only nav card), and
# everything under admin/.
STATIC_PAGES = [
    "index.html",
    "home-panel.html",
    "dge/index.html",
    "dge/audio.html",
    "dge/gita.html",
    "dge/kavya/index.html",
    "dge/dasa-sahitya/index.html",
    "dge/tirtha/index.html",
    "dge/guru-parampara/index.html",
    "dge/guru-parampara/lineage-2d.html",
    "dge/guru-parampara/lineage-3d.html",
    "dge/vyakarana/ashtadhyayi.html",
    "dge/vyakarana/chandas.html",
    "dge/vyakarana/dhatu.html",
    "dge/vyakarana/dhatuforms.html",
    "dge/vyakarana/krdanta.html",
    "dge/vyakarana/prakriya.html",
    "dge/vyakarana/rupasiddhi.html",
    "dge/vyakarana/shabda.html",
]

SITEMAP_RE = re.compile(r"^Sitemap:\s*(\S+)\s*$", re.MULTILINE)


def grantha_slug(catalog_path):
    """Mirrors dge/js/core.js's dgeLibraryPathToFetchPath()+dgeGranthaSlug():
    strip a leading 'dge/', then a leading 'data/', then a trailing
    '/data.json'."""
    p = catalog_path
    if p.startswith("dge/"):
        p = p[len("dge/"):]
    if p.startswith("data/"):
        p = p[len("data/"):]
    if p.endswith("/data.json"):
        p = p[: -len("/data.json")]
    return p


def is_hidden_path(slug, hidden_prefixes):
    """Mirrors dge/js/library.js's dgeIsHiddenPath(): a slug is hidden if it,
    or any ancestor prefix of it, is in library-overrides.json's `hidden`
    list."""
    parts = slug.split("/")
    for i in range(1, len(parts) + 1):
        if "/".join(parts[:i]) in hidden_prefixes:
            return True
    return False


def load_hidden_prefixes(path=OVERRIDES_JSON):
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("hidden", [])


def load_populated_granthas():
    """Every library.json entry a reader can actually reach: populated,
    not per-entry `hidden` (dge/js/library.js's dgeIsAdminOnlyGrantha()),
    and not curated out via library-overrides.json's hidden prefixes
    (dgeIsHiddenPath())."""
    lib = json.loads(LIBRARY_JSON.read_text(encoding="utf-8"))
    hidden_prefixes = load_hidden_prefixes()
    out = []
    for g in lib["granthas"]:
        if not g.get("populated") or g.get("hidden"):
            continue
        slug = grantha_slug(g["path"])
        if is_hidden_path(slug, hidden_prefixes):
            continue
        out.append((slug, g))
    return out


def git_last_modified_dates(paths):
    """One git-log pass over exactly the given paths, returning
    {relpath: 'YYYY-MM-DD'} for the most recent commit touching each --
    far cheaper than a `git log -1 -- <file>` subprocess per file."""
    wanted = set(paths)
    if not wanted:
        return {}
    try:
        proc = subprocess.run(
            # --full-history: without it, merge history-simplification
            # decides which parent line "touched" a path, and that choice
            # shifted between git versions — CI (git 2.55) attributed
            # eleven Veda entries to 2026-08-06 while local git said
            # 2026-08-17 for the same commit graph, keeping the drift
            # gate red from Aug 28 to Sep 2 with both sides "in sync"
            # locally. Full history pins lastmod to the newest commit
            # that actually touched the path, on every git version.
            ["git", "log", "--full-history", "--format=%x00%ad", "--date=short",
             "--name-only", "--", *sorted(wanted)],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {}
    result = {}
    current_date = None
    for line in proc.stdout.splitlines():
        if line.startswith("\x00"):
            current_date = line[1:]
            continue
        if line in wanted and line not in result:
            result[line] = current_date
    return result


def entry_lastmod(rel_path, added_at, git_dates):
    """The later of library.json's addedAt and the file's last git-commit
    date -- a grantha edited after being added should show that later
    date, but a fresh, uncommitted addedAt is still a real signal git
    hasn't seen yet."""
    git_date = git_dates.get(rel_path)
    if git_date and added_at:
        return max(git_date, added_at)
    return git_date or added_at


def build_sitemap_xml(origin):
    static_git_dates = git_last_modified_dates(STATIC_PAGES)
    granthas = load_populated_granthas()
    grantha_git_dates = git_last_modified_dates(g["path"] for _, g in granthas)

    urls = []
    for rel in STATIC_PAGES:
        urls.append((build_url(origin, rel), static_git_dates.get(rel)))
    for slug, g in sorted(granthas, key=lambda item: item[0]):
        loc = build_url(origin, "dge/index.html?path=" + quote(slug, safe="/"))
        lastmod = entry_lastmod(g["path"], g.get("addedAt"), grantha_git_dates)
        urls.append((loc, lastmod))

    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, lastmod in urls:
        lines.append("  <url>")
        lines.append(f"    <loc>{escape(loc)}</loc>")
        if lastmod:
            lines.append(f"    <lastmod>{lastmod}</lastmod>")
        lines.append("  </url>")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def sync_robots_txt(origin, check=False):
    """Ensures robots.txt carries a `Sitemap:` directive pointing at the
    current siteOrigin. Returns True if the file already matched."""
    want = f"{origin}/sitemap.xml"
    if not ROBOTS_PATH.exists():
        text = "User-agent: *\nAllow: /\n"
    else:
        text = ROBOTS_PATH.read_text(encoding="utf-8")

    match = SITEMAP_RE.search(text)
    if match and match.group(1) == want:
        return True
    if check:
        return False

    if match:
        text = SITEMAP_RE.sub(f"Sitemap: {want}", text, count=1)
    else:
        if not text.endswith("\n"):
            text += "\n"
        text += f"\nSitemap: {want}\n"
    ROBOTS_PATH.write_text(text, encoding="utf-8")
    return True


def main():
    check_mode = "--check" in sys.argv
    try:
        origin = load_config()["siteOrigin"]
    except SiteUrlError as e:
        print(f"build_sitemap: {e}", file=sys.stderr)
        return 1

    new_xml = build_sitemap_xml(origin)
    if check_mode:
        # Gate on the URL SET only, never on lastmod values. lastmod
        # derives from git-log path attribution, and which commit a
        # path is credited to differs across git versions (CI's 2.55
        # vs local 2.43 disagreed even with --full-history — this
        # repo's API-made commits carry author dates far behind their
        # commit dates). The gate's job is catching missing or stale
        # URLs; dates are advisory hints for crawlers.
        def loc_set(xml):
            return set(re.findall(r"<loc>(.*?)</loc>", xml))
        old_xml = SITEMAP_PATH.read_text(encoding="utf-8") if SITEMAP_PATH.exists() else ""
        sitemap_stale = loc_set(old_xml) != loc_set(new_xml)
    else:
        sitemap_stale = not SITEMAP_PATH.exists() or SITEMAP_PATH.read_text(encoding="utf-8") != new_xml
    robots_ok = sync_robots_txt(origin, check=check_mode)

    if check_mode:
        problems = []
        if sitemap_stale:
            problems.append("sitemap.xml is out of date")
        if not robots_ok:
            problems.append("robots.txt's Sitemap: directive is out of date")
        if problems:
            print("build_sitemap --check: " + "; ".join(problems) +
                  " -- run `python3 tools/build_sitemap.py` and commit the result.")
            return 1
        print("build_sitemap --check: OK -- sitemap.xml and robots.txt are in sync")
        return 0

    if sitemap_stale:
        SITEMAP_PATH.write_text(new_xml, encoding="utf-8")
        print(f"build_sitemap: wrote {SITEMAP_PATH.relative_to(REPO_ROOT)}")
    else:
        print("build_sitemap: sitemap.xml already up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
