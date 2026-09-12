"""Non-destructive merge into an existing DGE layer.

Two hard rules, enforced here rather than left to each importer:

1.  An importer NEVER shrinks a text.  merge_into_existing() refuses to write
    if the resulting layer would carry fewer filled shlokas than the layer
    already on disk (ShrinkError).
2.  An existing reading is only replaced when the existing text is a strict
    substring of the incoming reading -- i.e. the repo copy was truncated.
    Those replacements are recorded on the shloka as `repaired_from` so the
    change is auditable.  Any other disagreement leaves the repo copy alone
    and is reported as a conflict.
"""
from __future__ import annotations

import re

from .common import fingerprint, norm_ws
from .schema import is_filled, recount


class ShrinkError(RuntimeError):
    pass


class MergeShapeError(RuntimeError):
    """The layer on disk is not in a shape this merge understands.

    Kept for callers that catch it. Nothing raises it since the id bridge in
    unit_key()/_index() taught the merge to read the pre-package shape.
    """


class MergeReport:
    def __init__(self, layer_id=""):
        self.layer_id = layer_id
        self.added_items = 0
        self.added_shlokas = 0
        self.filled_fields = 0
        self.repaired = []      # list of shloka ids
        self.conflicts = []     # list of (shloka_id, field)
        self.kept = 0           # existing values left untouched

    def as_dict(self):
        return {
            "layer": self.layer_id,
            "added_items": self.added_items,
            "added_shlokas": self.added_shlokas,
            "filled_fields": self.filled_fields,
            "repaired": self.repaired,
            "repaired_count": len(self.repaired),
            "conflicts": self.conflicts,
            "conflict_count": len(self.conflicts),
            "kept_existing": self.kept,
        }

    def __str__(self):
        return (
            "%s: +%d items, +%d shlokas, %d fields filled, %d repaired, "
            "%d conflicts, %d kept"
            % (
                self.layer_id,
                self.added_items,
                self.added_shlokas,
                self.filled_fields,
                len(self.repaired),
                len(self.conflicts),
                self.kept,
            )
        )


def unit_key(item_id):
    """`sarga_01`, `01`, `sarga 1`, `1` -> `1`.

    DGE's own granthas name a chapter for what it is and pad the number;
    this package numbers them bare. They are the same chapter and have to
    index to the same key, or a merge appends a second copy of the text
    beside the first instead of updating it.
    """
    digits = re.findall(r"\d+", str(item_id or ""))
    return str(int(digits[-1])) if digits else str(item_id or "")


def _index(layer):
    """Every shloka in the layer, under every key it can be addressed by.

    A shloka written by this package carries `id` ("1.34"). One written
    before it carries `number` (34) inside an item called `sarga_01`, and
    nothing else. Both have to resolve to the same entry, so both keys are
    registered, and a lookup tries the id first and the reconstructed
    <chapter>.<number> second.
    """
    idx = {}
    for it in layer.get("items", []):
        unit = unit_key(it.get("id"))
        for sh in it.get("shlokas", []):
            sid = sh.get("id")
            if sid:
                idx.setdefault(str(sid), sh)
                idx.setdefault("%s.%s" % (unit, str(sid).split(".")[-1]), sh)
            num = sh.get("number")
            if num is not None:
                idx.setdefault("%s.%s" % (unit, num), sh)
    return idx


def _is_repair(existing: str, incoming: str) -> bool:
    """True when `existing` is a strict, shorter substring of `incoming`."""
    a, b = fingerprint(existing), fingerprint(incoming)
    return bool(a) and bool(b) and a != b and a in b


def _merge_text_field(dst, src, field, sid, report):
    inc = norm_ws(src.get(field, ""))
    if not inc:
        return
    cur = norm_ws(dst.get(field, ""))
    if not cur:
        dst[field] = inc
        report.filled_fields += 1
        return
    if fingerprint(cur) == fingerprint(inc):
        report.kept += 1
        return
    if _is_repair(cur, inc):
        dst.setdefault("repaired_from", {})[field] = cur
        dst[field] = inc
        report.repaired.append(sid)
        return
    report.conflicts.append((sid, field))
    report.kept += 1


def _merge_bhashya(dst, src, sid, report):
    inc = src.get("bhashya") or []
    if not inc:
        return
    cur = dst.setdefault("bhashya", [])
    by_key = {}
    for i, b in enumerate(cur):
        by_key[(b.get("commentator", ""), fingerprint(b.get("text", "")))] = i
    by_commentator = {}
    for i, b in enumerate(cur):
        by_commentator.setdefault(b.get("commentator", ""), i)

    for b in inc:
        text = norm_ws(b.get("text", ""))
        if not text:
            continue
        com = b.get("commentator", "")
        if (com, fingerprint(text)) in by_key:
            report.kept += 1
            continue
        j = by_commentator.get(com)
        if j is not None and _is_repair(cur[j].get("text", ""), text):
            cur[j].setdefault("repaired_from", cur[j].get("text", ""))
            cur[j]["text"] = text
            report.repaired.append(sid)
            continue
        if j is not None:
            # same commentator, genuinely different reading -> keep both,
            # the reader shows them as separate cards.
            report.conflicts.append((sid, "bhashya:" + com))
        cur.append(dict(b, text=text))
        by_commentator.setdefault(com, len(cur) - 1)
        report.filled_fields += 1


SCALAR_FIELDS = ("sanskrit_text", "artha", "anvaya", "chandas", "speaker")


def merge_into_existing(existing, incoming, allow_new=True):
    """Merge `incoming` layer into `existing` (mutated and returned).

    `existing` may be None -> the incoming layer is returned as-is.
    """
    report = MergeReport(
        (incoming.get("grantha") or {}).get("id", "")
    )
    if existing and "grantha" not in existing:
        # A layer written before this package existed: no grantha block, items
        # named sarga_01 where this writes 1, shlokas carrying number where
        # this carries id. unit_key() and _index() bridge the two, so the
        # merge now updates that text rather than appending a second copy of
        # it; all that is missing is the metadata block, which the incoming
        # layer supplies. Everything the old file said about itself that this
        # package has no field for -- default_author, above all -- is kept.
        existing["grantha"] = dict(incoming.get("grantha") or {})
        existing.setdefault("schema", incoming.get("schema", "itihasa_purana_text"))
    if not existing:
        recount(incoming)
        report.added_items = len(incoming.get("items", []))
        report.added_shlokas = sum(
            len(i.get("shlokas", [])) for i in incoming.get("items", [])
        )
        report.filled_fields = incoming["grantha"]["counts"]["filled"]
        return incoming, report

    before_filled = sum(1 for _, sh in _iter(existing) if is_filled(sh))

    dst_idx = _index(existing)
    items_by_id = {}
    for it in existing.get("items", []):
        items_by_id.setdefault(it.get("id"), it)
        items_by_id.setdefault(unit_key(it.get("id")), it)

    for it in incoming.get("items", []):
        tgt_item = (items_by_id.get(it.get("id"))
                    or items_by_id.get(unit_key(it.get("id"))))
        if tgt_item is None:
            if not allow_new:
                continue
            tgt_item = {k: v for k, v in it.items() if k != "shlokas"}
            tgt_item["shlokas"] = []
            existing.setdefault("items", []).append(tgt_item)
            items_by_id[tgt_item["id"]] = tgt_item
            report.added_items += 1
        else:
            for k in ("name_sa", "name_en"):
                if not tgt_item.get(k) and it.get(k):
                    tgt_item[k] = it[k]

        for sh in it.get("shlokas", []):
            sid = sh.get("id")
            cur = dst_idx.get(sid)
            if cur is None:
                # The same verse as written before this package existed.
                cur = dst_idx.get("%s.%s" % (unit_key(it.get("id")),
                                             str(sid).split(".")[-1]))
            if cur is None:
                if not allow_new:
                    continue
                tgt_item["shlokas"].append(sh)
                dst_idx[sid] = sh
                report.added_shlokas += 1
                if is_filled(sh):
                    report.filled_fields += 1
                continue
            for f in SCALAR_FIELDS:
                _merge_text_field(cur, sh, f, sid, report)
            _merge_bhashya(cur, sh, sid, report)
            if sh.get("padaccheda") and not cur.get("padaccheda"):
                cur["padaccheda"] = sh["padaccheda"]
                report.filled_fields += 1

    # sort items and shlokas by numeric id so output is stable
    _sort(existing)
    recount(existing)

    after_filled = sum(1 for _, sh in _iter(existing) if is_filled(sh))
    if after_filled < before_filled:
        raise ShrinkError(
            "refusing to write %s: filled shlokas would drop %d -> %d"
            % (report.layer_id, before_filled, after_filled)
        )
    return existing, report


def _iter(layer):
    for it in layer.get("items", []):
        for sh in it.get("shlokas", []):
            yield it, sh


def _key(uid):
    out = []
    for part in str(uid or "").split("."):
        try:
            out.append((0, int(part), ""))
        except ValueError:
            out.append((1, 0, part))
    return out


def _shloka_sort_key(item, sh):
    """Order a verse by its id, or by its number where it has no id.

    A bridged layer holds both kinds at once -- the verses that were already
    there carry number, the ones this import added carry id -- and sorting on
    id alone files every pre-existing verse under a blank key, which puts the
    new arrivals at the top of the sarga and Raghuvamsa 1.3 above 1.1.
    """
    sid = sh.get("id")
    if sid:
        return _key(sid)
    num = sh.get("number")
    if num is not None:
        return _key("%s.%s" % (unit_key(item.get("id")), num))
    return _key("")


def _sort(layer):
    layer["items"] = sorted(layer.get("items", []),
                            key=lambda i: _key(unit_key(i.get("id"))))
    for it in layer["items"]:
        it["shlokas"] = sorted(it.get("shlokas", []),
                               key=lambda s: _shloka_sort_key(it, s))
