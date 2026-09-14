#!/usr/bin/env python3
"""One encoding for every filesystem-facing name this corpus writes.

WHY. Filenames here carry SLP1, where capitalisation is meaning: gaD.json is
ड and gad.json is द. NTFS and the default macOS APFS see one name, so a
checkout silently writes one over the other -- 37,234 colliding paths, and a
commit from that working copy deletes the loser for everyone. Seven more paths
are named con/nul/prn, syllable pairs that collide with reserved MS-DOS device
names Windows has refused since 1983.

build_search_index.py's bucket_key() already solved the case half for the word
index and said so: "no two distinct buckets collide case-insensitively". It was
never applied to the trigram tree or to data/kosha, and it does not handle the
device names. This is that function, finished, in one place both the builder
and the client can agree on.

    Ba   -> b-a        an uppercase letter is lowercase + '-'
    ba   -> ba         lowercase is already safe
    nul  -> nul~       a reserved device name gets a '~'
    COn  -> c-o-n      needs no suffix: escaping already broke the match

THE MARKER IS '~' AND NOT '-', which was the first attempt and was wrong. The
repo holds both `nul` and `nuL`. Escaping takes nuL -> nul-, so giving the
reserved name a '-' too would land both on `nul-` -- a fix that reintroduces
exactly the collision it exists to remove, on the one name it was written for.
'~' cannot arise from either rule, and appears in neither charset, so it is
unambiguous. (Git's protectNTFS objects only to '~' followed by a digit, the
8.3 short-name shape; '~' at the end of a stem is fine.)

'-' is safe as the escape because none of the charsets that reach here contain
it: trigrams draw from [A-Za-z^$], SLP1 from letters and digits. So 'b-a' can
only have come from 'Ba' and never from a literal.

Mirrored exactly by safeComponent() in js/dge-search.js. If one changes and the
other does not, every fetch 404s.
"""
from __future__ import annotations

# Reserved regardless of extension or case. CONIN$/CONOUT$ are reserved too but
# cannot arise here: '$' only appears in trigrams, never after these letters.
RESERVED = frozenset(
    ["con", "prn", "aux", "nul"]
    + [f"com{i}" for i in range(10)]
    + [f"lpt{i}" for i in range(10)]
)

# '-' and '~' are the encoder's OWN markers, so they must survive a second
# pass or the function is not idempotent -- bucket_key() escapes Ba to b-a and
# then hands that here, and without this the '-' became '_' and every bucket
# name silently changed. Safe to allow: neither character appears in the
# charsets that reach here (trigrams are [A-Za-z^$], SLP1 is letters and
# digits), so a '-' can only ever be one this function put there.
SAFE_EXTRA = frozenset("^$-~")


def safe_component(name: str) -> str:
    """A single path component that survives a case-insensitive filesystem."""
    out = []
    for ch in name:
        if "0" <= ch <= "9" or "a" <= ch <= "z" or ch in SAFE_EXTRA:
            out.append(ch)
        elif "A" <= ch <= "Z":
            out.append(ch.lower() + "-")
        else:
            out.append("_")
    s = "".join(out) or "_"
    # Windows matches a device name on the stem, so test before any extension.
    if s.split(".")[0].lower() in RESERVED:
        s += "~"
    return s


def is_hostile(name: str) -> bool:
    """True when this component would collide or be refused on Windows/macOS."""
    return safe_component(name) != name
