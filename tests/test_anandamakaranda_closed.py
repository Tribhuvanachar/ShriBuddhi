"""Anandamakaranda is closed: nothing new lands there.

27 Sep 2026, the lead: "Going forward, nothing should be entered into
Ananda Makaranda. So whatever is there like Rug Bhashya etc. they should be
going inside Dvaita Vedanta in. It applies to Gita also."

Only selected pieces of that tree will ever be pushed on to Jagat and the
lead picks those, so a new layer landed there is a layer nobody asked for
in a tree nobody is publishing from. New Dvaita material goes to
DvaitaVedantaIn instead.

A ratchet rather than a ban: the count below is what the tree held the day
it was closed. It may fall, as content moves to DvaitaVedantaIn. It may not
rise.
"""
import json
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[1]
TREE = REPO / "data/darshana/vedanta/dvaita/Anandamakaranda"

#: Populated data.json files in the tree on 27 Sep 2026, when it was closed.
POPULATED_WHEN_CLOSED = 49


def _populated():
    out = []
    for f in sorted(TREE.rglob("data.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        items = d.get("items") or []
        if isinstance(d.get("shlokas"), dict):
            items = list(d["shlokas"].values())
        if items:
            out.append(str(f.relative_to(TREE)))
    return out


def test_nothing_new_has_been_added():
    if not TREE.is_dir():
        return                      # already moved out entirely: fine
    now = _populated()
    assert len(now) <= POPULATED_WHEN_CLOSED, (
        "new content has landed in Anandamakaranda, which is closed — "
        "it belongs in DvaitaVedantaIn: "
        + ", ".join(sorted(now)[:5]))


def test_the_rule_is_written_down_where_an_importer_will_see_it():
    claude = (REPO / "CLAUDE.md").read_text(encoding="utf-8")
    assert "Anandamakaranda is closed" in claude
    assert "DvaitaVedantaIn" in claude
