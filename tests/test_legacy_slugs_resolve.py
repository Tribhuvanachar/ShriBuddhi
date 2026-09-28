"""Every legacy-slug redirect must land somewhere that exists.

DGE_LEGACY_SLUGS (js/core.js) upgrades an old URL to the text's current home.
A redirect whose DESTINATION does not exist is worse than no redirect at all:
without it an old link 404s honestly, with it js/core.js resolves the slug,
finds no library.json entry, keeps its guessed fetch path and tells the reader
"Please ensure data/stotra/pns/data.json is available in the repository" -- a
lost-file message for what is really a pointer to nowhere. Two of these had
been live for weeks ('stotras' -> 'stotra', 'koshas' -> 'kosha'; neither
destination exists in any repo).
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _legacy_map():
    text = (ROOT / "js/core.js").read_text(encoding="utf-8")
    i = text.index("const DGE_LEGACY_SLUGS = {")
    j = text.index("\n};", i)
    body = text[i:j]
    # Strip // comments first. The block documents the redirects it REMOVED by
    # quoting them ("used to read 'stotras': 'stotra'"), and a naive regex
    # happily reads those back as live entries -- which is exactly the bug the
    # comment is there to explain.
    body = "\n".join(re.sub(r"//.*$", "", line) for line in body.split("\n"))
    return dict(re.findall(r"'([^']+)':\s*'([^']+)'", body))


def _known_nodes():
    lib = json.loads((ROOT / "data/library.json").read_text(encoding="utf-8"))
    nodes = set()
    for g in lib["granthas"]:
        slug = g["path"][5:-10]
        parts = slug.split("/")
        for i in range(1, len(parts) + 1):
            nodes.add("/".join(parts[:i]))
    return nodes


def test_every_redirect_destination_exists():
    nodes = _known_nodes()
    dead = {src: dst for src, dst in _legacy_map().items() if dst not in nodes}
    assert dead == {}, (
        "legacy redirects pointing at paths no longer in the library: " + repr(dead))


def _upgrade(slug, legacy):
    """Python mirror of js/core.js's dgeUpgradeLegacySlug: longest matching
    source prefix wins, one pass, and a slug already at or under its own
    destination is left alone."""
    best = None
    for src in legacy:
        if slug == src or slug.startswith(src + "/"):
            if best is None or len(src) > len(best):
                best = src
    if best is None:
        return slug
    dest = legacy[best]
    if slug == dest or slug.startswith(dest + "/"):
        return slug
    return dest + slug[len(best):]


def test_resolution_is_idempotent():
    """Resolution runs ONCE per slug, so wherever a redirect lands must be a
    final answer: feeding a destination back through must not move it again.
    (A destination that merely sits under another redirect's key is fine --
    'vedanga/nirukta/mula' is under the 'vedanga/nirukta' key, and the
    resolver's own already-upgraded guard returns it untouched.)"""
    legacy = _legacy_map()
    moved = {d: _upgrade(d, legacy) for d in set(legacy.values())
             if _upgrade(d, legacy) != d}
    assert moved == {}, "these destinations resolve further: " + repr(moved)
