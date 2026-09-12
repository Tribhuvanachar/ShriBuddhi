"""Layer/entry construction for the Kavya corpus.

Every Kavya layer is written as an `itihasa_purana_text` grantha so that
DGE's existing schemas.json and core.js need no change:

  dge/data/kavya_alankara/<work_id>/<layer_id>/data.json

  {
    "schema": "itihasa_purana_text",
    "grantha": { ...layer metadata... },
    "items":   [ { "id": "1", "shlokas": [ {...}, ... ] }, ... ]
  }

Field usage per layer kind (chosen so core.js renders the attested text
without modification):

  mula          -> shloka.sanskrit_text
  tika/tippani  -> shloka.bhashya[] = [{"commentator": ..., "text": ...}]
  padaccheda    -> shloka.padaccheda[] (structured) + shloka.artha (flat)
  anvaya        -> shloka.artha           (ai_generated flag on the grantha)
  translation_* -> shloka.artha           (grantha.language = 'en' | 'hi')
  saaramsha     -> shloka.artha           (ai_generated flag on the grantha)
"""
from __future__ import annotations

from .common import make_unit_id, norm_ws

SCHEMA_NAME = "itihasa_purana_text"

LAYER_KINDS = (
    "mula",
    "tika",
    "tippani",
    "padaccheda",
    "anvaya",
    "translation",
    "saaramsha",
)

# Layer kinds whose content is *attested* — a verifier failure if flagged AI.
ATTESTED_KINDS = ("mula", "tika", "tippani")

# Layer kinds that may legitimately be machine-generated.
GENERATABLE_KINDS = ("anvaya", "translation", "saaramsha", "padaccheda")


def make_grantha(
    layer_id,
    work_id,
    kind,
    name_sa="",
    name_iast="",
    name_en="",
    commentator="",
    language="sa",
    source=None,
    license_note="",
    ai_generated=False,
):
    if kind not in LAYER_KINDS:
        raise ValueError("unknown layer kind: %r" % (kind,))
    if ai_generated and kind in ATTESTED_KINDS:
        raise ValueError(
            "refusing to build an ai_generated %s layer (%s/%s): attested "
            "layers must never carry generated text" % (kind, work_id, layer_id)
        )
    return {
        "id": layer_id,
        "work_id": work_id,
        "layer_kind": kind,
        "name_sa": name_sa,
        "name_iast": name_iast,
        "name_en": name_en,
        "commentator": commentator,
        "language": language,
        "ai_generated": bool(ai_generated),
        "source": source or {},
        "license": license_note,
        "counts": {"items": 0, "shlokas": 0, "filled": 0},
    }


def make_layer(grantha):
    return {"schema": SCHEMA_NAME, "grantha": grantha, "items": []}


def make_item(number, name_sa="", name_en="", parent=None):
    return {
        "id": make_unit_id(parent, number) if parent else make_unit_id(number),
        "number": str(number),
        "name_sa": name_sa,
        "name_en": name_en,
        "shlokas": [],
    }


def make_shloka(unit_id, number=None, kind="verse"):
    return {
        "id": unit_id,
        "number": str(number) if number is not None else unit_id.split(".")[-1],
        "kind": kind,          # 'verse' | 'prose' | 'stage'
        "sanskrit_text": "",
        "artha": "",
        "bhashya": [],
    }


def set_payload(shloka, layer_kind, text, commentator="", extra=None):
    """Put `text` in the field the layer kind owns."""
    text = norm_ws(text)
    if not text:
        return shloka
    if layer_kind == "mula":
        shloka["sanskrit_text"] = text
    elif layer_kind in ("tika", "tippani"):
        shloka.setdefault("bhashya", []).append(
            {"commentator": commentator or "", "text": text}
        )
    else:
        shloka["artha"] = text
    if extra:
        shloka.update(extra)
    return shloka


def is_filled(shloka):
    return bool(
        shloka.get("sanskrit_text")
        or shloka.get("artha")
        or shloka.get("bhashya")
        or shloka.get("padaccheda")
    )


def recount(layer):
    items = layer.get("items", [])
    n_sh = 0
    n_filled = 0
    for it in items:
        for sh in it.get("shlokas", []):
            n_sh += 1
            if is_filled(sh):
                n_filled += 1
    layer["grantha"]["counts"] = {
        "items": len(items),
        "shlokas": n_sh,
        "filled": n_filled,
    }
    return layer["grantha"]["counts"]


def iter_shlokas(layer):
    for it in layer.get("items", []):
        for sh in it.get("shlokas", []):
            yield it, sh


def validate_layer(layer):
    """Returns a list of error strings (empty == valid)."""
    errs = []
    if layer.get("schema") != SCHEMA_NAME:
        errs.append("schema must be %r, got %r" % (SCHEMA_NAME, layer.get("schema")))
    g = layer.get("grantha") or {}
    for key in ("id", "work_id", "layer_kind"):
        if not g.get(key):
            errs.append("grantha.%s is required" % key)
    if g.get("layer_kind") not in LAYER_KINDS:
        errs.append("grantha.layer_kind %r not in %r" % (g.get("layer_kind"), LAYER_KINDS))
    if g.get("ai_generated") and g.get("layer_kind") in ATTESTED_KINDS:
        errs.append(
            "grantha %s is layer_kind=%s but flagged ai_generated"
            % (g.get("id"), g.get("layer_kind"))
        )
    seen = set()
    for it in layer.get("items", []):
        if not it.get("id"):
            errs.append("item without id")
        for sh in it.get("shlokas", []):
            sid = sh.get("id")
            if not sid:
                errs.append("shloka without id in item %s" % it.get("id"))
                continue
            if sid in seen:
                errs.append("duplicate shloka id %s" % sid)
            seen.add(sid)
            if not isinstance(sh.get("bhashya", []), list):
                errs.append("shloka %s: bhashya must be a list" % sid)
    return errs
