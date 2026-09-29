#!/usr/bin/env python3
"""
publish_direct_fetch_rewrite.py -- stop the published site trying admin/ first.

Every reader-facing config/content fetch in this app is written the same
way: build a URL under admin/config/<name> or admin/content/<name> (the
live truth in the workshop repositories, which ship admin/), and fall back
to the repo-root config/<name> or content/<name> mirror when that 404s --
which it always does on a clean publish, since publish_clean_repo.py
excludes admin/ on purpose. That fallback is correct and stays; this
rewrites only the PRIMARY url each caller tries first, in the STAGED copy,
so a cleanly published site fetches the right path immediately instead of
wasting a request on a path that can never resolve there. The fallback
code is left in place -- once the primary URL is already correct it simply
never triggers, and deleting it would make this script the only thing that
keeps the two in sync.

Two call sites are deliberately NOT here: js/admin-remote.js's
fetchFromBrahma('admin/config/admin-menu.json') reads the WORKSHOP repo's
admin-menu.json over the GitHub API with an admin token, never a local
path, so there is no local admin/ to fall back from. js/config-editor.js's
DGE_CONFIG_OVERRIDES_PATH and friends are WRITE targets (dgeAdminUpsertFile,
dgeAdminDelete) for the same cross-repo admin tool -- a write always belongs
at the workshop's real admin/ path, regardless of which repo's copy of this
file happens to be running it. Same for chandas-page.js's "Publish to repo"
button target. Rewriting any of those would send a superadmin's real edit
to the wrong place.

    python3 tools/publish_direct_fetch_rewrite.py --staged <dir>

Exits 1 and prints which file if a listed string is no longer found exactly
once -- the source moved and this list needs updating, rather than silently
rewriting the wrong text or doing nothing.
"""
from __future__ import annotations

import argparse
import os
import sys

# (repo-relative path in the staged tree, exact old substring, exact new
# substring). Order does not matter -- every pair targets a different file
# or a disjoint span of the same file.
REWRITES = (
    ("js/core.js",
     "try { return new URL('../admin/config/' + name, self).href; }",
     "try { return new URL('../config/' + name, self).href; }"),
    ("js/core.js",
     "catch (e) { return '../admin/config/' + name; }",
     "catch (e) { return '../config/' + name; }"),
    ("js/core.js",
     "try { return new URL('../admin/content/' + name, self).href; }",
     "try { return new URL('../content/' + name, self).href; }"),
    ("js/core.js",
     "catch (e) { return '../admin/content/' + name; }",
     "catch (e) { return '../content/' + name; }"),

    # contact-email.js keeps its own copy of dgeAdminConfigUrl (the
    # `window.X || function...` guard) for pages that load it without
    # core.js -- same fix, independently, so whichever copy wins the race
    # is already correct.
    ("js/contact-email.js",
     "try { return new URL('../admin/config/' + name, self).href; }",
     "try { return new URL('../config/' + name, self).href; }"),
    ("js/contact-email.js",
     "catch (e) { return '../admin/config/' + name; }   // fail soft, never throw",
     "catch (e) { return '../config/' + name; }   // fail soft, never throw"),

    ("js/global-search.js",
     "var gsOvUrl = new URL('admin/config/library-overrides.json', GS_ROOT).href;",
     "var gsOvUrl = new URL('config/library-overrides.json', GS_ROOT).href;"),

    ("js/menu.js",
     "try { url = new URL('../admin/config/menu.json', self).href; }",
     "try { url = new URL('../config/menu.json', self).href; }"),
    ("js/menu.js",
     "catch (e) { url = '../admin/config/menu.json'; }",
     "catch (e) { url = '../config/menu.json'; }"),

    ("js/tour.js",
     "try { return new URL('../admin/content/tour.json', self).href; }",
     "try { return new URL('../content/tour.json', self).href; }"),
    ("js/tour.js",
     "catch (e) { return '../admin/content/tour.json'; }",
     "catch (e) { return '../content/tour.json'; }"),

    ("js/kosha2.js",
     "fetchJson('../admin/config/kosha-overrides.json')",
     "fetchJson('../config/kosha-overrides.json')"),

    ("js/ashtadhyayi.js",
     'var url = "../admin/content/ashtadhyayi-layers.json?t=" + Date.now();',
     'var url = "../content/ashtadhyayi-layers.json?t=" + Date.now();'),

    ("js/chandas-page.js",
     "var FEATURES_URL = '../../admin/config/chandas-features.json';",
     "var FEATURES_URL = '../../config/chandas-features.json';"),

    ("js/contextual-actions.js",
     "try { return new URL('../admin/config/contextual-actions.json', self).href; }",
     "try { return new URL('../config/contextual-actions.json', self).href; }"),
    ("js/contextual-actions.js",
     "catch (e) { return '../admin/config/contextual-actions.json'; }",
     "catch (e) { return '../config/contextual-actions.json'; }"),

    ("js/library.js",
     "                                        : '../admin/config/library-overrides.json';",
     "                                        : '../config/library-overrides.json';"),

    ("js/legal-content.js",
     "      : '../admin/content/legal.json';",
     "      : '../content/legal.json';"),

    ("js/modals.js",
     "    ? window.dgeContentUrl('whats-new.json') : 'admin/content/whats-new.json';",
     "    ? window.dgeContentUrl('whats-new.json') : 'content/whats-new.json';"),
    ("js/modals.js",
     "    const url = '../admin/content/home.json?t=' + Date.now();",
     "    const url = '../content/home.json?t=' + Date.now();"),

    ("js/core.js",
     "    const cfg = await window.dgeFetchPublicJson('../admin/config/seo.json');",
     "    const cfg = await window.dgeFetchPublicJson('../config/seo.json');"),

    ("library.html",
     "fetchOverridesJson('admin/config/library-overrides.json')",
     "fetchOverridesJson('config/library-overrides.json')"),

    ("sitemap.html",
     "fetchOverridesJson('admin/config/library-overrides.json')",
     "fetchOverridesJson('config/library-overrides.json')"),
)


def rewrite(staged: str, pairs=REWRITES) -> int:
    """Apply every (rel, old, new) in `pairs` (REWRITES by default) under
    `staged`. Returns the count applied; raises on a miss (0 or >1
    occurrences) rather than silently skipping one."""
    applied = 0
    by_file: dict[str, str] = {}
    for rel, old, new in pairs:
        path = os.path.join(staged, rel)
        if path not in by_file:
            if not os.path.isfile(path):
                raise SystemExit(f"{rel}: not found in the staged tree")
            with open(path, encoding="utf-8") as fh:
                by_file[path] = fh.read()
        text = by_file[path]
        count = text.count(old)
        if count != 1:
            raise SystemExit(
                f"{rel}: expected the old text exactly once, found {count}.\n"
                f"    {old!r}\n"
                "The source moved -- update REWRITES in "
                "tools/publish_direct_fetch_rewrite.py to match.")
        by_file[path] = text.replace(old, new, 1)
        applied += 1
    for path, text in by_file.items():
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
    return applied


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--staged", required=True, help="the staged publish directory")
    args = ap.parse_args(argv)
    try:
        n = rewrite(args.staged)
    except SystemExit as e:
        print(str(e), file=sys.stderr)
        return 1
    print(f"rewrote {n} direct-fetch primary URL(s) across "
          f"{len({rel for rel, _, _ in REWRITES})} file(s) -- "
          "admin/config or admin/content is no longer tried first.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
