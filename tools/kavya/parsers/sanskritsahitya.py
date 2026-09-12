"""Tier A parser: github.com/sanskritsahitya-com/data

Verified against the live repo (meghadutam/meghadutam.json, Aug 2026).

Top level:
    {"title": str,
     "books":    [{"number": "1", "name": "..."}, ...],   # optional
     "chapters": [{"number": "1", "name": "..."}, ...],   # optional
     "data":     [ <unit>, ... ]}

Unit keys actually observed:
    n   verse number                       (required)
    c   chapter number, may embed the book number as "1.1"
    i   DEPRECATED index -- ignored
    v   mula verse text (Devanagari)
    t   non-verse text (stage direction / prose)
    sp  speaker (drama)
    ch  {"n": "मन्दाक्रान्ता"}  metre
    anv anvaya (editorial, attested -- NOT machine generated)
    es  English prose rendering
    hs  Hindi prose rendering
    pc  padaccheda: [{"w": surface,
                      "p": [{"l": lemma, "cn": "1.1", "vp": [upasarga],
                             "inf": stem, "s": [pratyaya], "fin": finite form,
                             "pn": person, "t": lakara, "pp": "P1"/"A1"}],
                      "e": English gloss}]
    <other> a commentary, keyed by a short code that differs per work
            (meghadutam uses "vd").  Codes are declared per work in
            config/works.json; unknown string-valued keys are reported by
            `--probe` instead of being silently dropped.
"""
from __future__ import annotations

from ..common import make_unit_id, norm_ws
from ..schema import make_grantha, make_item, make_layer, make_shloka, recount

RESERVED = {"n", "c", "i", "v", "t", "sp", "ch", "anv", "es", "hs", "pc"}

#: source key -> (layer_id, layer_kind, language)
STANDARD_LAYERS = {
    "v": ("mula", "mula", "sa"),
    "t": ("mula", "mula", "sa"),
    "anv": ("anvaya", "anvaya", "sa"),
    "es": ("translation_en", "translation", "en"),
    "hs": ("translation_hi", "translation", "hi"),
    "pc": ("padaccheda", "padaccheda", "sa"),
}

#: The reader labels a layer by its name_sa and falls back to the English, so
#: without these the chip row reads "सञ्जीविनी | Padaccheda | Anvaya |
#: Translation En" -- one Devanagari name and three Latin ones, in a UI that is
#: Devanagari-first everywhere else. The commentaries carry their own names
#: from works.json; these are the four every work shares.
STANDARD_NAMES = {
    "anvaya":         {"name_sa": "अन्वयः", "name_iast": "Anvaya", "name_en": "Anvaya"},
    "padaccheda":     {"name_sa": "पदच्छेदः", "name_iast": "Padaccheda", "name_en": "Padaccheda"},
    "translation_en": {"name_sa": "आङ्ग्लानुवादः", "name_iast": "Āṅglānuvāda",
                       "name_en": "English translation"},
    "translation_hi": {"name_sa": "हिन्द्यनुवादः", "name_iast": "Hindyanuvāda",
                       "name_en": "Hindi translation"},
}


def probe(doc):
    """Report the keys present in a work's data, so an unknown commentary code
    is surfaced before any import writes it."""
    seen = {}
    for unit in doc.get("data", []):
        for k, v in unit.items():
            slot = seen.setdefault(k, {"count": 0, "sample": ""})
            slot["count"] += 1
            if not slot["sample"] and isinstance(v, str):
                slot["sample"] = v[:80]
    unknown = sorted(k for k in seen if k not in RESERVED)
    return {
        "title": doc.get("title", ""),
        "units": len(doc.get("data", [])),
        "keys": seen,
        "unknown_keys": unknown,
    }


def _chapter_names(doc):
    names = {}
    for ch in doc.get("chapters", []) or []:
        names[str(ch.get("number"))] = ch.get("name", "")
    return names


def _unit_ids(unit, default_chapter="1"):
    c = str(unit.get("c") or default_chapter)
    n = str(unit.get("n") or "")
    return c, make_unit_id(c, n)


def parse(doc, work_id, commentary_keys=None, source=None, license_note=""):
    """Returns {layer_id: layer_dict}.

    `commentary_keys` maps a source key to layer metadata, e.g.
        {"vd": {"id": "vallabhadeva", "commentator": "Vallabhadeva",
                "name_sa": "वल्लभदेवटीका"}}
    """
    commentary_keys = commentary_keys or {}
    ch_names = _chapter_names(doc)
    layers = {}
    items = {}          # (layer_id, chapter) -> item dict

    def layer_for(layer_id, kind, language, **meta):
        if layer_id not in layers:
            g = make_grantha(
                layer_id,
                work_id,
                kind,
                language=language,
                source=source or {},
                license_note=license_note,
                **meta
            )
            layers[layer_id] = make_layer(g)
        return layers[layer_id]

    def shloka_for(layer_id, chapter, uid, kind="verse"):
        key = (layer_id, chapter)
        it = items.get(key)
        if it is None:
            it = make_item(chapter, name_sa=ch_names.get(chapter, ""))
            items[key] = it
            layers[layer_id]["items"].append(it)
        for sh in it["shlokas"]:
            if sh["id"] == uid:
                return sh
        sh = make_shloka(uid, kind=kind)
        it["shlokas"].append(sh)
        return sh

    for unit in doc.get("data", []):
        chapter, uid = _unit_ids(unit)
        if not uid:
            continue

        # ---- mula (verse or prose) -------------------------------------
        verse = norm_ws(unit.get("v", ""))
        prose = norm_ws(unit.get("t", ""))
        if verse or prose:
            layer_for("mula", "mula", "sa", name_sa="मूलम्", name_en="Mula")
            sh = shloka_for("mula", chapter, uid, kind="verse" if verse else "prose")
            sh["sanskrit_text"] = verse or prose
            if unit.get("sp"):
                sh["speaker"] = norm_ws(unit["sp"])
            ch = unit.get("ch")
            if isinstance(ch, dict) and ch.get("n"):
                sh["chandas"] = norm_ws(ch["n"])
            elif isinstance(ch, str) and ch:
                sh["chandas"] = norm_ws(ch)

        # ---- editorial layers ------------------------------------------
        for key, (lid, kind, lang) in STANDARD_LAYERS.items():
            if key in ("v", "t"):
                continue
            val = unit.get(key)
            if not val:
                continue
            layer_for(lid, kind, lang,
                      **STANDARD_NAMES.get(lid,
                                           {"name_en": lid.replace("_", " ").title()}))
            sh = shloka_for(lid, chapter, uid)
            if key == "pc":
                sh["padaccheda"] = _clean_pc(val)
                sh["artha"] = " · ".join(
                    "%s = %s" % (w.get("w", ""), w.get("e", ""))
                    for w in sh["padaccheda"]
                    if w.get("e")
                )
            else:
                sh["artha"] = norm_ws(val)

        # ---- commentaries ----------------------------------------------
        for key, meta in commentary_keys.items():
            val = unit.get(key)
            if not val or not isinstance(val, str):
                continue
            lid = meta.get("id") or key
            layer_for(
                lid,
                meta.get("kind", "tika"),
                meta.get("language", "sa"),
                name_sa=meta.get("name_sa", ""),
                name_iast=meta.get("name_iast", ""),
                name_en=meta.get("name_en", ""),
                commentator=meta.get("commentator", ""),
            )
            sh = shloka_for(lid, chapter, uid)
            sh.setdefault("bhashya", []).append(
                {"commentator": meta.get("commentator", ""), "text": norm_ws(val)}
            )

    for layer in layers.values():
        recount(layer)
    return layers


def _clean_pc(pc):
    out = []
    for w in pc or []:
        if not isinstance(w, dict):
            continue
        word = norm_ws(w.get("w", ""))
        if not word:
            continue
        parts = []
        for p in w.get("p", []) or []:
            if not isinstance(p, dict):
                continue
            part = {"lemma": norm_ws(p.get("l", ""))}
            if p.get("cn"):
                part["case_number"] = p["cn"]
            if p.get("fin"):
                part["finite"] = p["fin"]
            if p.get("t"):
                part["lakara"] = p["t"]
            if p.get("pn"):
                part["person"] = p["pn"]
            if p.get("pp"):
                part["pada"] = p["pp"]
            if p.get("vp"):
                part["upasarga"] = p["vp"]
            if p.get("inf"):
                part["stem"] = p["inf"]
            if p.get("s"):
                part["pratyaya"] = p["s"]
            if part["lemma"]:
                parts.append(part)
        out.append({"w": word, "p": parts, "e": norm_ws(w.get("e", ""))})
    return out
