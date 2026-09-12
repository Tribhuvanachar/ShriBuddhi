#!/usr/bin/env python3
"""compile_anuvyakhyana_v2.py — Nyayasudha consolidation, phase 2 of the
grantha architecture (tools/reports/grantha_data_architecture.md).

Reads the legacy DV import (later_acharyas/nyaya_sudha/mula/data.json,
whose source_html interleaves, per verse article: the pratika heading, a
topic caption, the Anuvyakhyana verse under an "anuvyakhyanam" heading,
then the Sudha and each upa-tika as headed segments) and emits:

    sutra_prasthana/anuvyakhyana_sudha/
      work.json
      mula/data.json                    Anuvyakhyana verses (Madhva)
      tika_nyayasudha/data.json         the Sudha, CONSOLIDATED — the
                                        legacy tree stored it as three
                                        accidental fragments
      tippani_parimala/ ... (6 upa-tika layers)
      _sources/dv_map.json  ·  _review.json

Unit shape as in the Brahmasutra pilot: {id, ref, text, topic?, on?};
refs are adhyaya.pada.verse_seq (positional — the source prints no verse
numbers), verse advance happens ONLY on the site's own per-verse mula
articles, so prose never registers as a verse. The legacy tree is
untouched. Run from repo root:  python3 tools/compile_anuvyakhyana_v2.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

from compile_grantha_v2 import (  # noqa: E402  (shared helpers)
    ADHYAYA, PADA, clean, norm_head, para_lines_to_paragraphs, same_sutra,
)

SRC = Path("data/darshana/vedanta/dvaita/DvaitaVedantaIn/later_acharyas/nyaya_sudha")
DST = Path("data/darshana/vedanta/dvaita/DvaitaVedantaIn/sutra_prasthana/anuvyakhyana_sudha")

LAYER_ALIASES = {
    "अनुव्याख्यानम्": "mula",
    "सुधा": "tika_nyayasudha",
    "परिमळ": "tippani_parimala", "परिमल": "tippani_parimala",
    "वाक्यार्थरत्नमाला": "tippani_vakyartharatnamala",
    "श्रीनिवासतीर्थीया": "tippani_srinivasatirthiya",
    "श्रीनिवासतीर्थीयम्": "tippani_srinivasatirthiya",
    "यादुपत्यम्": "tippani_yadupatyam",
    "वाक्यार्थचन्द्रिका": "tippani_vakyarthacandrika",
    "शेषवाक्यार्थचन्द्रिका": "tippani_sheshavakyarthacandrika",
    "सशेषवाक्यार्थचन्द्रिका": "tippani_sheshavakyarthacandrika",
}
_SQUASHED = {re.sub(r"\s+", "", k): v for k, v in LAYER_ALIASES.items()}

LAYER_META = {
    "mula": ("अनुव्याख्यानम्", "श्रीमदानन्दतीर्थभगवत्पादाचार्यः", ""),
    "tika_nyayasudha": ("न्यायसुधा", "श्रीजयतीर्थः", "mula"),
    "tippani_parimala": ("परिमळः", "", "tika_nyayasudha"),
    "tippani_vakyartharatnamala": ("वाक्यार्थरत्नमाला", "", ""),
    "tippani_srinivasatirthiya": ("श्रीनिवासतीर्थीया", "श्रीनिवासतीर्थः", ""),
    "tippani_yadupatyam": ("यादुपत्यम्", "", ""),
    "tippani_vakyarthacandrika": ("वाक्यार्थचन्द्रिका", "", ""),
    "tippani_sheshavakyarthacandrika": ("शेषवाक्यार्थचन्द्रिका",
                                        "श्रीपाण्डुरङ्गि-केशवाचार्यः", ""),
}


def layer_for_heading(head: str) -> str | None:
    sq = re.sub(r"\s+", "", head)
    if sq in _SQUASHED:
        return _SQUASHED[sq]
    for k, v in _SQUASHED.items():
        if k in sq or (len(sq) >= 4 and k.endswith(sq)):
            return v
    return None


def main() -> int:
    doc = json.loads((SRC / "mula" / "data.json").read_text(encoding="utf-8"))
    items = doc["items"]

    layers: dict[str, list[dict]] = {s: [] for s in LAYER_META}
    dv_map: dict[str, dict] = {}
    review: list[dict] = []
    counters: dict[tuple[str, str], int] = {}

    cur = {"a": 0, "p": 0, "v": 0}
    cur_adhik = {"name": ""}
    pada_state: dict[tuple[int, int], int] = {}
    cur_verse_title = ""
    last_verse_text = ""

    # a verse line ends in a double danda (pathabheda parens tolerated) or
    # is a lacuna of dots; Sudha prose paragraphs end in single dandas
    VERSE_LINE = re.compile(r"(।।|॥)\s*(\([^)]*\))?\s*$")
    DOTS = re.compile(r"^[.\s…]+$|\.{3,}")

    def is_verse_line(ln: str) -> bool:
        ln = ln.strip()
        if not ln:
            return False
        if DOTS.search(ln) and len(ln) < 120:
            return True
        return bool(VERSE_LINE.search(ln)) and len(ln) < 160

    def ref_str() -> str:
        return f"{cur['a']}.{cur['p']}.{cur['v']}"

    def goto_pada(a: int, p: int):
        if (a, p) != (cur["a"], cur["p"]):
            pada_state[(cur["a"], cur["p"])] = cur["v"]
            cur.update(a=a, p=p, v=pada_state.get((a, p), 0))

    def push(layer: str, text: str, art: dict, topic: str | None = None):
        text = text.strip()
        if not text:
            return
        r = ref_str()
        counters[(layer, r)] = counters.get((layer, r), 0) + 1
        uid = f"{r}.p{counters[(layer, r)]}"
        unit = {"id": uid, "ref": r, "text": text}
        if topic:
            unit["topic"] = topic
        if layer == "mula" and cur_adhik["name"]:
            unit["adhikarana"] = cur_adhik["name"]
        if layer != "mula":
            unit["on"] = [r]
        layers[layer].append(unit)
        dv_map[f"{layer}:{uid}"] = {"anchor": art["source"].get("anchor"),
                                    "url": art["source"].get("url")}

    def process_mula_block(lines: list[str], art: dict, topic: str | None):
        """An anuvyakhyanam segment: verse-groups separated by bare
        'anuvyakhyanam' label lines; each group = verse lines + optional
        unheaded Sudha prose on that very verse."""
        nonlocal last_verse_text, topic_used
        groups: list[list[str]] = [[]]
        for ln in lines:
            if re.sub(r"[\s।॥|]+", "", ln) == "अनुव्याख्यानम्":
                if groups[-1]:
                    groups.append([])
                continue
            groups[-1].append(ln)
        for g in (g for g in groups if g):
            verse_lines = []
            i = 0
            while i < len(g) and is_verse_line(g[i]):
                verse_lines.append(g[i]); i += 1
            prose = g[i:]
            vtext = "\n".join(verse_lines).strip()
            if vtext:
                if last_verse_text and same_sutra(vtext, last_verse_text):
                    # restatement — but a fuller reading upgrades the unit
                    if layers["mula"] and len(vtext) > len(layers["mula"][-1]["text"]):
                        layers["mula"][-1]["text"] = vtext
                        last_verse_text = vtext
                else:
                    cur["v"] += 1
                    last_verse_text = vtext
                    push("mula", vtext, art,
                         topic=None if topic_used else topic)
                    topic_used = True
            elif prose and not last_verse_text:
                review.append({"kind": "prose_before_any_verse",
                               "id": art["id"], "at": ref_str()})
            for para in para_lines_to_paragraphs(prose):
                push("tika_nyayasudha", para, art)

    n_articles = 0
    cur_layer: str | None = None      # persists across continuation articles
    for art in items:
        bc = art.get("breadcrumb") or []
        if len(bc) > 4 and bc[4].strip():
            import re as _re
            cur_adhik["name"] = _re.sub(r"^[०-९0-9]+\.\s*", "", bc[4].strip())
        elif len(bc) > 2 and "मङ्गल" in bc[2]:
            cur_adhik["name"] = "मङ्गलाचरणम्"
        a = ADHYAYA.get(bc[2]) if len(bc) > 2 else None
        p = PADA.get(bc[3]) if len(bc) > 3 else None
        if len(bc) > 2 and "मङ्गल" in bc[2]:
            a, p = 0, 0
        html = art.get("source_html") or ""
        if not html:
            html = "".join(f"<p>{ln}</p>"
                           for ln in (art.get("sanskrit_text") or "").split("\n"))
            review.append({"kind": "no_source_html_text_fallback", "id": art["id"]})
        soup = BeautifulSoup(html, "html.parser")
        els = soup.find_all(["h1", "h2", "h3", "h4", "p"])

        if a is None or p is None:
            # 16 pada-opener articles carry the pada name only in their text
            names = " ".join(clean(e.get_text(" ", strip=True)) for e in els[:4])
            na = next((v for k, v in ADHYAYA.items() if k in names), None)
            np = next((v for k, v in PADA.items() if k in names), None)
            if np is not None:
                goto_pada(na if na is not None else cur["a"] or 1, np)
                review.append({"kind": "pada_opener_resolved", "id": art["id"],
                               "to": f"{cur['a']}.{cur['p']}"})
            else:
                review.append({"kind": "unplaced_article", "id": art["id"],
                               "breadcrumb": bc[:5]})
        else:
            goto_pada(a, p)

        n_articles += 1
        is_verse_article = art["source"].get("layer") == "मूलम्"
        if is_verse_article:
            cur_verse_title = clean(art.get("unit_title") or "")
            cur_layer = None      # a verse article restarts its own sections
            # register the verse UP FRONT from the article title, so this
            # article's commentary sections anchor to it (an anuvyakhyanam
            # segment with the fuller text upgrades the unit in place)
            if cur_verse_title and not (
                    last_verse_text and same_sutra(cur_verse_title, last_verse_text)):
                cur["v"] += 1
                last_verse_text = cur_verse_title
                push("mula", cur_verse_title, art)

        pending: list[str] = []
        topic_line: str | None = None
        topic_used = False

        def flush(art=art):
            nonlocal pending, topic_line, topic_used
            if cur_layer and pending:
                if cur_layer == "mula":
                    process_mula_block(pending, art, topic_line)
                else:
                    for para in para_lines_to_paragraphs(pending):
                        push(cur_layer, para, art)
            pending = []

        for el in els:
            txt = clean(el.get_text(" ", strip=True))
            if not txt:
                continue
            if el.name.startswith("h"):
                head = norm_head(txt)
                slug = layer_for_heading(head)
                flush()
                if slug:
                    cur_layer = slug
                elif same_sutra(head, cur_verse_title) or not cur_verse_title:
                    pass          # the article's own pratika heading
                elif head.endswith(("धिकरणम्", "पादः")) or head in ADHYAYA:
                    pass          # section headings of the site's tree
                else:
                    review.append({"kind": "unknown_heading", "id": art["id"],
                                   "heading": head[:60], "at": ref_str()})
                continue
            if cur_layer is None:
                # before any layer heading: topic caption (verse articles);
                # pratika restatements are dropped either way
                if is_verse_article and topic_line is None \
                        and not same_sutra(txt, cur_verse_title):
                    topic_line = txt
                continue
            if same_sutra(txt, cur_verse_title) and len(txt) < 160 \
                    and cur_layer != "mula":
                continue          # stray pratika repeat inside a section
            pending.append(txt)
        flush()
        if is_verse_article and topic_line and layers["mula"]:
            lastu = layers["mula"][-1]
            if lastu["ref"] == ref_str() and "topic" not in lastu:
                lastu["topic"] = topic_line

    # ---- emit ----------------------------------------------------------
    DST.mkdir(parents=True, exist_ok=True)
    (DST / "_sources").mkdir(exist_ok=True)
    work_layers = []
    for slug, (title, author, chain) in LAYER_META.items():
        units = layers[slug]
        if not units:
            continue
        entry = {"slug": slug, "title": title, "author": author,
                 "units": len(units)}
        if slug != "mula":
            entry["commentary_on"] = chain
            if not chain:
                review.append({"kind": "commentary_chain_unverified",
                               "layer": slug})
        work_layers.append(entry)
        (DST / slug).mkdir(exist_ok=True)
        (DST / slug / "data.json").write_text(json.dumps({
            "schema": "grantha_layer_v2", "work": "anuvyakhyana_sudha",
            "layer": slug, "units": units,
        }, ensure_ascii=False, indent=1), encoding="utf-8")

    all_padas = sorted(
        {".".join(u["ref"].split(".")[:2])
         for units in layers.values() for u in units},
        key=lambda p: [int(x) for x in p.split(".")])

    (DST / "work.json").write_text(json.dumps({
        "schema": "grantha_work_v2",
        "work": "anuvyakhyana_sudha",
        "title": "ब्रह्मसूत्रानुव्याख्यानम् (न्यायसुधादिसहितम्)",
        "ref_scheme": "adhyaya.pada.shloka_seq",
        "ref_note": "verse numbers are positional (flow order per pada); the "
                    "source prints none",
        "related_work": "brahma_sutra",
        "padas": all_padas,
        "layers": work_layers,
        "licence_note": doc.get("source_note", ""),
        "generated_by": "tools/compile_anuvyakhyana_v2.py",
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    (DST / "_sources" / "dv_map.json").write_text(json.dumps({
        "site": "dvaitavedanta.in",
        "note": "paragraph id (layer:id) -> source article",
        "map": dv_map,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    (DST / "_review.json").write_text(json.dumps({
        "note": "compiler anomalies for the project lead / scholar",
        "items": review,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"articles parsed: {n_articles}")
    import collections
    per_pada = collections.Counter()
    for u in layers["mula"]:
        a, p, v = u["ref"].split(".")
        per_pada[f"{a}.{p}"] = max(per_pada[f"{a}.{p}"], int(v))
    for k in sorted(per_pada, key=lambda x: tuple(map(int, x.split(".")))):
        print(f"  pada {k}: {per_pada[k]} verses")
    for slug in LAYER_META:
        n = len(layers[slug])
        ch = sum(len(u["text"]) for u in layers[slug])
        print(f"{slug:36s} {n:6d} units {ch:11,d} chars")
    print(f"review: {dict(collections.Counter(r['kind'] for r in review))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
