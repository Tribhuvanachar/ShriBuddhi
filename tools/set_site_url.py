#!/usr/bin/env python3
"""Point the site's absolute URLs at whichever domain is currently live.

Why this exists
---------------
The reader resolves its own links relatively and its JavaScript uses
``location.origin``, so both follow whatever domain served the page. Open
Graph / link-preview metadata is the exception: it must be fully
qualified, and it is read by crawlers (WhatsApp, Telegram, X) that never
execute JavaScript. So it has to be baked into the HTML, which means it
has to be *changed* in the HTML whenever the domain changes.

Rather than leaving that as "remember to grep for the old domain", every
such spot is marked in the HTML:

    <!-- site-url: dge/images/guru/guruji.jpg -->
    <meta property="og:image" content="https://host/dge/images/guru/guruji.jpg">

The marker carries the path *within the site*; this script joins it to
``siteOrigin`` from admin/config/site.config.json and rewrites the URL in the tag on
the following line.

Usage
-----
    python3 tools/set_site_url.py                 # apply admin/config/site.config.json
    python3 tools/set_site_url.py --check         # verify, exit 1 on drift
    python3 tools/set_site_url.py --set https://www.sarvamula.org
    python3 tools/set_site_url.py --dry-run
"""

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "admin" / "config" / "site.config.json"

# Files scanned for markers. Deliberately an explicit list rather than a
# glob over the whole repo: this rewrites URLs, and it should never be
# able to wander into a data file or a vendored asset by accident.
MANAGED_FILES = [
    "index.html",
]

MARKER_RE = re.compile(r"<!--\s*site-url:\s*(?P<path>[^\s>]+?)\s*-->")
# The URL inside the attribute on the tag that follows the marker.
URL_ATTR_RE = re.compile(
    r"(?P<attr>\b(?:content|href|src)\s*=\s*[\"'])(?P<url>https?://[^\"']+)(?P<close>[\"'])"
)


class SiteUrlError(Exception):
    pass


def load_config(path=CONFIG_PATH):
    if not path.exists():
        raise SiteUrlError(f"Missing {path.name} — the site URL has nowhere to come from.")
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SiteUrlError(f"{path.name} is not valid JSON: {e}") from e

    origin = cfg.get("siteOrigin")
    if not isinstance(origin, str) or not origin.strip():
        raise SiteUrlError(f"{path.name} has no usable 'siteOrigin'.")
    return cfg


def normalize_origin(origin):
    """Trims trailing slashes and refuses anything that isn't a real origin."""
    origin = origin.strip().rstrip("/")
    if not re.match(r"^https?://[^/\s]+", origin):
        raise SiteUrlError(
            f"siteOrigin must start with http:// or https:// and a host — got {origin!r}"
        )
    if " " in origin:
        raise SiteUrlError(f"siteOrigin must not contain spaces — got {origin!r}")
    return origin


def build_url(origin, path):
    return f"{normalize_origin(origin)}/{path.lstrip('/')}"


def rewrite_text(text, origin):
    """Returns (new_text, changes) where changes is a list of (old, new)."""
    changes = []
    out = []
    pos = 0

    for marker in MARKER_RE.finditer(text):
        want = build_url(origin, marker.group("path"))
        # Look only at the rest of the document from this marker, and only
        # at the FIRST url-bearing attribute after it — a marker governs
        # exactly one tag, never everything that follows it.
        tail_start = marker.end()
        attr = URL_ATTR_RE.search(text, tail_start)
        if not attr:
            raise SiteUrlError(
                f"site-url marker for {marker.group('path')!r} is not followed by any "
                "content=/href=/src= attribute holding an absolute URL."
            )

        # Guard against a marker matching a tag far below it (e.g. someone
        # deleted the tag it was meant to govern).
        between = text[tail_start:attr.start()]
        if between.count("\n") > 3:
            raise SiteUrlError(
                f"site-url marker for {marker.group('path')!r} has no tag directly after "
                f"it — the nearest absolute URL is {between.count(chr(10))} lines away."
            )

        current = attr.group("url")
        if current != want:
            changes.append((current, want))

        out.append(text[pos:attr.start()])
        out.append(attr.group("attr") + want + attr.group("close"))
        pos = attr.end()

    out.append(text[pos:])
    return "".join(out), changes


def process(origin, files=None, dry_run=False, check=False):
    files = files or MANAGED_FILES
    total_changes = 0
    markers_found = 0

    for rel in files:
        path = REPO_ROOT / rel
        if not path.exists():
            raise SiteUrlError(f"Managed file not found: {rel}")

        text = path.read_text(encoding="utf-8")
        markers_found += len(MARKER_RE.findall(text))
        new_text, changes = rewrite_text(text, origin)

        for old, new in changes:
            total_changes += 1
            verb = "would change" if (dry_run or check) else "changed"
            print(f"  {rel}: {verb}\n    {old}\n → {new}")

        if changes and not dry_run and not check:
            path.write_text(new_text, encoding="utf-8")

    if markers_found == 0:
        # Not fatal, but almost certainly a mistake — silently doing
        # nothing is the failure mode this whole script exists to prevent.
        print("WARNING: no <!-- site-url: ... --> markers found in any managed file.",
              file=sys.stderr)

    return total_changes, markers_found


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true",
                        help="verify only; exit 1 if any managed URL is out of date")
    parser.add_argument("--dry-run", action="store_true",
                        help="show what would change without writing")
    parser.add_argument("--set", metavar="ORIGIN",
                        help="set siteOrigin in admin/config/site.config.json to this, then apply")
    args = parser.parse_args(argv)

    try:
        cfg = load_config()

        if args.set:
            origin = normalize_origin(args.set)
            cfg["siteOrigin"] = origin
            CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n",
                                   encoding="utf-8")
            print(f"admin/config/site.config.json: siteOrigin set to {origin}")
        else:
            origin = normalize_origin(cfg["siteOrigin"])

        print(f"Site origin: {origin}")
        changes, _ = process(origin, dry_run=args.dry_run, check=args.check)

        if args.check:
            if changes:
                print(f"\nFAIL: {changes} managed URL(s) do not match siteOrigin. "
                      "Run: python3 tools/set_site_url.py", file=sys.stderr)
                return 1
            print("OK: every managed URL matches siteOrigin.")
            return 0

        if changes:
            print(f"\n{changes} URL(s) updated." if not args.dry_run
                  else f"\n{changes} URL(s) would be updated.")
            if not args.dry_run:
                domain = cfg.get("customDomain", {})
                if domain.get("status") != "live" and origin.startswith(domain.get("origin", "\0")):
                    print("\nReminder: also add this domain under Firebase console → "
                          "Authentication → Settings → Authorized domains, or Google "
                          "Sign-In will fail silently on it.")
        else:
            print("Already up to date — nothing to change.")
        return 0

    except SiteUrlError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
