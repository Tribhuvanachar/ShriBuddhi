"""Tier C parser: ambuda.org bulk TEI export.

Ambuda ships TEI that is structurally the same as GRETIL corpusTEI but nests
<div type="section"> for kanda/sarga and puts the reference on <lg n="...">
rather than xml:id.  split_units_tei already accepts either attribute, so the
only real work here is walking the <div> stack to synthesise a full reference
when <lg n> carries only the verse number.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

from ..common import deva_to_ascii_digits, norm_ws
from .gretil_tei import _localname, _itertext


def split_units(xml_text, section=None):
    """`section` keeps only one top-level division, renumbered to chapter 1.

    Ambuda files one text per work except where the tradition does not:
    shatakatrayam is Bhartrhari's three satakas as sections 1, 2 and 3, and
    DGE holds them as three works, so each takes its own section. Sections are
    also named rather than numbered in places -- "AmrShtk", "all" -- which is
    not a chapter number and becomes 1.
    """
    root = ET.fromstring(xml_text)
    state = {"verse": "0", "prose": 0}

    def walk(el, stack):
        name = _localname(el.tag)
        n = None
        for k, v in el.attrib.items():
            if _localname(k) in ("n", "id") and v:
                n = deva_to_ascii_digits(v).split("_", 1)[-1]
                break
        if name == "div":
            new_stack = stack + ([n] if n else [])
            for child in el:
                for out in walk(child, new_stack):
                    yield out
            return
        if name in ("lg", "p", "seg"):
            body = _itertext(el)
            if not body:
                return
            if n and ("." in n or "," in n):
                parts = [p for p in n.replace(",", ".").split(".") if p]
            else:
                parts = [p for p in stack if p] + ([n] if n else [])
            if parts:
                if section is not None:
                    if str(parts[0]) != str(section):
                        return
                    parts = ["1"] + parts[1:]
                elif not str(parts[0]).lstrip("-").isdigit():
                    parts = ["1"] + parts[1:]
                # Ambuda numbers a play's prose p1, p2, ... beside verses
                # 1, 2, ... Left alone those sort after every verse in the
                # act, because a numeric id sorts before an alphanumeric one,
                # and the play would read as all its verses followed by all
                # its prose. <act>.<last verse>.<n> keeps it in order.
                if not str(parts[-1]).lstrip("-").isdigit():
                    state["prose"] += 1
                    parts = [parts[0], state["verse"], str(state["prose"])]
                else:
                    state["verse"], state["prose"] = str(parts[-1]), 0
                yield parts, name == "p", norm_ws(body)
            return
        for child in el:
            for out in walk(child, stack):
                yield out

    for out in walk(root, []):
        yield out
