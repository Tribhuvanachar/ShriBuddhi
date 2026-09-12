#!/usr/bin/env python3
"""compile_grantha_v2.py — Brahmasutra-family pilot of the DGE-native
grantha architecture (tools/reports/grantha_data_architecture.md).

Reads the legacy DV import (sutra_prasthana/brahma_sutra_bhashya/mula/
data.json, whose source_html preserves the site's full interleaved flow:
sutra line, then <h2>/<h3>-headed segments for the bhashya and each
commentary) and emits the new tree:

    sutra_prasthana/brahma_sutra/
      work.json                      family manifest with commentary chains
      sutra/data.json                one unit per sutra
      bhashya/data.json              Madhva's bhashya, paragraph units
      tika_<slug>/data.json          each commentary, paragraph units
      _sources/dv_map.json           paragraph id -> DV article provenance
      _review.json                   anomalies for the lead's review

Unit shape: {id, ref, text, heading?, on?}. ids are "<ref>.p<n>" —
append-only within their layer file; globally addressed as
"brahma_sutra:<layer>:<id>". refs are adhyaya.pada.sutra, numbered from
the source's own restatement lines (".. OM <sutra> OM .. <n> ..") and
positional order, cross-checked per pada. Commentary units carry
on: ["<ref>"] (coarse anchor to the parent layer at that sutra) —
paragraph-precise anchors are a later refinement pass.

The legacy tree is untouched; this is additive. Run from repo root:
    python3 tools/compile_grantha_v2.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

SRC = Path("data/darshana/vedanta/dvaita/DvaitaVedantaIn/sutra_prasthana/brahma_sutra_bhashya")
DST = Path("data/darshana/vedanta/dvaita/DvaitaVedantaIn/sutra_prasthana/brahma_sutra")

DEVA_DIGIT = str.maketrans("०१२३४५६७८९", "0123456789")

# heading text (normalized) -> layer slug. The DV flow's own labels,
# including the typo variants that actually occur in the corpus.
LAYER_ALIASES = {
    "सूत्रभाष्यम्": "bhashya", "सू त्रभाष्यम्": "bhashya",
    "सूत्राभाष्यम्": "bhashya", "ब्रह्मसूत्रभाष्यम्": "bhashya",
    "तत्त्वप्रकाशिका": "tika_tattvaprakashika",
    "तत्वप्रकाशिका": "tika_tattvaprakashika",
    "त्त्वप्रकाशिका": "tika_tattvaprakashika",
    "सत्तर्कदीपावली": "tika_sattarkadipavali",
    "तत्त्वप्रदीपिका": "tika_tattvapradipika",
    "भावदीपः": "tika_bhavadipa",
    "वाक्यार्थमुक्तावली": "tika_vakyarthamuktavali",
    "वाक्यार्थमञ्जरी": "tika_vakyarthamanjari",
    "भावबोधः": "tika_bhavabodha",
    "तत्त्वसुबोधिनी": "tika_tattvasubodhini",
    "गुर्वर्थदीपिका": "tika_gurvarthadipika",
    "वाक्यार्थविवरणम्": "tika_vakyarthavivarana",
    "अभिनवचन्द्रिका": "tika_abhinavacandrika",
    "विवृतिः": "tika_vivritti",
    # the source titles Bhavabodha's sections on 2.1.1 and 2.3.1 with the
    # fuller name; same author (Raghuttama-tirtha), same target (TP), and
    # the short-titled layer has no units at those refs — one work, so one
    # layer (the lead's 3 Sep 2026 report: an 8-unit chip that "shows
    # nothing" because its refs sat in padas 2.1/2.3)
    "तत्त्वप्रकाशिकाभावबोधः": "tika_bhavabodha",
    "भामती": "tika_bhamati",
}
LAYER_TITLES = {v: k for k, v in reversed(list(LAYER_ALIASES.items()))}
LAYER_TITLES["sutra"] = "सूत्रपाठः"
LAYER_TITLES["bhashya"] = "सूत्रभाष्यम्"
LAYER_TITLES["tika_tattvaprakashika"] = "तत्त्वप्रकाशिका"

# Commentary chains and authors as CONFIRMED by the traditional scholar,
# 3 Sep 2026 (tools/reports/bs_scholar_sheet_filled.md). Everything except
# the Sattarkadipavali (Padmanabha Tirtha — Madhva's direct disciple, so
# necessarily on the bhashya itself) comments on the Tattvaprakashika.
COMMENTARY_ON = {
    "bhashya": "sutra",
    "tika_tattvaprakashika": "bhashya",     # Jayatirtha on the bhashya
    "tika_tattvapradipika": "bhashya",      # Trivikrama Pandita on the bhashya
    "tika_sattarkadipavali": "bhashya",
    "tika_abhinavacandrika": "tika_tattvaprakashika",
    "tika_bhavabodha": "tika_tattvaprakashika",
    "tika_bhavadipa": "tika_tattvaprakashika",
    "tika_gurvarthadipika": "tika_tattvaprakashika",
    "tika_tattvaprakashikabhavabodha": "tika_tattvaprakashika",
    "tika_tattvasubodhini": "tika_tattvaprakashika",
    "tika_vakyarthamanjari": "tika_tattvaprakashika",
    "tika_vakyarthamuktavali": "tika_tattvaprakashika",
    "tika_vakyarthavivarana": "tika_tattvaprakashika",
    "tika_vivritti": "tika_tattvaprakashika",
    "tika_bhamati": "",                     # stray quoted heading; unplaced
}

# Scholar-confirmed authors — these OVERRIDE the legacy default_author
# fields (which had Gurvarthadipika under Raghavendra and Sattarkadipavali
# under Vyasatirtha; both corrected by the scholar).
SCHOLAR_AUTHORS = {
    "tika_abhinavacandrika": "श्रीसत्यनाथतीर्थः",
    "tika_bhavabodha": "श्रीरघूत्तमतीर्थः",
    "tika_bhavadipa": "श्रीराघवेन्द्रतीर्थः",
    "tika_gurvarthadipika": "श्रीवादिराजतीर्थः",
    "tika_sattarkadipavali": "श्रीपद्मनाभतीर्थः",
    "tika_tattvaprakashikabhavabodha": "श्रीरघूत्तमतीर्थः",
    "tika_tattvasubodhini": "पाण्डुरङ्गि-श्रीनिवासाचार्यः",
    "tika_vakyarthamanjari": "शर्करा-श्रीनिवासतीर्थः",
    "tika_vakyarthamuktavali": "ताम्रपर्णी-श्रीनिवासाचार्यः",
    "tika_vakyarthavivarana": "बिदरहळ्ळि-श्रीनिवासतीर्थः",
}

ADHYAYA = {"प्रथमाध्यायः": 1, "द्वितीयोऽध्यायः": 2, "तृतीयाध्यायः": 3,
           "तृतीयोऽध्यायः": 3, "चतुर्थाध्यायः": 4, "चतुर्थोऽध्यायः": 4}
PADA = {"प्रथमः पादः": 1, "द्वितीयः पादः": 2, "तृतीयः पादः": 3, "चतुर्थः पादः": 4}

# "।। ॐ <sutra> ॐ ।। १८ ।।" — the flow's own numbered restatement.
RESTATE = re.compile(r"[।॥|]{1,2}\s*ॐ\s*(.+?)\s*ॐ\s*[।॥|]{1,2}\s*([०-९0-9]+)\s*[।॥|]{0,2}")
OM_LINE = re.compile(r"^ॐ\s*(.+?)\s*ॐ\s*(?:[।॥|]{1,2}\s*([०-९0-9]+))?\s*[।॥|]{0,2}$")
VERSE_END = re.compile(r"(॥|॥\s*[०-९0-9\-]+\s*॥)\s*(?:\([^)]{1,40}\))?\s*$")
QUOTE_CLOSE = re.compile(r"(?:इति|’’ति|”ति)\s*[।॥]?\s*$")


def norm_head(t: str) -> str:
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"\s*\([०-९0-9]+\)\s*$", "", t)   # "सत्तर्कदीपावली (५)"
    return t.rstrip("।॥ ").strip()


# alias lookup tolerant of the flow's split/spaced heading variants
# ("भा वबोधः", "क्यार्थमुक्तावली", "श्रीजयतीर्थविरचिता तत्त्वप्रकाशिका")
_SQUASHED = {re.sub(r"\s+", "", k): v for k, v in LAYER_ALIASES.items()}


def layer_for_heading(head: str) -> str | None:
    sq = re.sub(r"\s+", "", head)
    if sq in _SQUASHED:
        return _SQUASHED[sq]
    for k, v in _SQUASHED.items():
        if k in sq:                     # "…विरचिता तत्त्वप्रकाशिका"
            return v
        if len(sq) >= 4 and k.endswith(sq):   # truncated: "वबोधः"
            return v
    return None


def norm_sutra_text(t: str) -> str:
    t = re.sub(r"\([^)]*\)", "", t)          # pathabheda parentheses
    t = t.replace(":", "ः")                   # ASCII colon typed for visarga
    return re.sub(r"[\s।॥|ॐ०-९0-9‘’“”'\"ऽ​]+", "", t)


def same_sutra(a: str, b: str) -> bool:
    na, nb = norm_sutra_text(a), norm_sutra_text(b)
    if not na or not nb:
        return False
    if na == nb or na in nb or nb in na:
        return True
    import difflib
    return difflib.SequenceMatcher(None, na, nb).ratio() >= 0.85


def clean(t: str) -> str:
    return re.sub(r"[ \t]+", " ", t).strip()


def para_lines_to_paragraphs(lines: list[str]) -> list[str]:
    """Group <p> lines into paragraphs: verse halves and quote-closers
    attach to the paragraph that introduced them; prose starts fresh."""
    paras: list[str] = []
    for ln in lines:
        ln = clean(ln)
        if not ln:
            continue
        attach = False
        if paras:
            prev = paras[-1]
            if prev.rstrip().endswith(("—", "–", "-")):
                attach = True                      # explicit quote intro
            elif VERSE_END.search(ln):
                attach = True                      # a verse line
            elif VERSE_END.search(prev.splitlines()[-1]) and QUOTE_CLOSE.search(ln):
                attach = True                      # "... iti" after verses
        if attach:
            paras[-1] += "\n" + ln
        else:
            paras.append(ln)
    return paras


def main() -> int:
    doc = json.loads((SRC / "mula" / "data.json").read_text(encoding="utf-8"))
    items = doc["items"]

    layers: dict[str, list[dict]] = {"sutra": [], "bhashya": []}
    dv_map: dict[str, dict] = {}
    review: list[dict] = []
    counters: dict[tuple[str, str], int] = {}

    # ref state advances as the flow restates numbered sutras
    cur = {"a": 0, "p": 0, "s": 0}     # adhyaya, pada, sutra
    cur_adhik = {"name": ""}           # adhikarana of the article in hand
    seen_sutra_text: dict[str, str] = {}   # ref -> sutra text (first wins)

    def ref_str() -> str:
        return f"{cur['a']}.{cur['p']}.{cur['s']}"

    def push(layer: str, text: str, art: dict, heading: str | None = None):
        text = text.strip()
        if not text:
            return
        layers.setdefault(layer, [])
        r = ref_str()
        counters[(layer, r)] = counters.get((layer, r), 0) + 1
        uid = f"{r}.p{counters[(layer, r)]}"
        unit = {"id": uid, "ref": r, "text": text}
        if heading:
            unit["heading"] = heading
        parent = COMMENTARY_ON.get(layer)
        if layer not in ("sutra",):
            unit["on"] = [r]
        layers[layer].append(unit)
        dv_map[f"{layer}:{uid}"] = {
            "anchor": art["source"].get("anchor"),
            "url": art["source"].get("url"),
        }

    pada_state: dict[tuple[int, int], int] = {}

    def advance(a=None, p=None, s=None):
        # the flow can be interrupted (mangala articles mid-file) — returning
        # to a pada must resume its counter, never restart it
        if (a is not None and a != cur["a"]) or (p is not None and p != cur["p"]):
            pada_state[(cur["a"], cur["p"])] = cur["s"]
            na = a if a is not None else cur["a"]
            np = p if p is not None else cur["p"]
            cur.update(a=na, p=np, s=pada_state.get((na, np), 0))
        if s is not None:
            if cur["s"] and s not in (cur["s"], cur["s"] + 1):
                review.append({"kind": "sutra_number_jump", "ref": ref_str(),
                               "to": s, "at": ref_str()})
            cur["s"] = s

    def register_sutra(text: str, num: int | None, art: dict):
        text = clean(text)
        text = re.sub(r"^ॐ\s*|\s*ॐ$", "", text)
        text = re.sub(r"[।॥|]+\s*[०-९0-9]*\s*[।॥|]*\s*$", "", text).strip()
        # a layer label glued to the sutra line (seen at 4.4.20) is an
        # extraction artifact, never part of the sutra
        text = re.sub(r"\s*(सूत्रभाष्यम्|तत्त्वप्रकाशिका)\s*$", "", text).strip()
        # the flow restates the current sutra constantly (article titles,
        # chunk headers) — only a genuinely NEW sutra advances the ref.
        # Deliberately NOT pada-wide: short sutras (darshanAchcha etc.)
        # genuinely recur within one pada.
        prev = seen_sutra_text.get(ref_str())
        if prev is not None and same_sutra(prev, text):
            return
        if num is not None and num > cur["s"]:
            # trust the source's own monotonic numbering — it is what pulls
            # positions right after un-numbered small adhikaranas
            if num > cur["s"] + 1:
                review.append({"kind": "sutra_number_gap", "at": ref_str(),
                               "to": num})
            advance(s=num)
        else:
            if num is not None and num != cur["s"] + 1:
                review.append({"kind": "sutra_number_ignored", "at": ref_str(),
                               "claimed": num})
            advance(s=cur["s"] + 1)
        r = ref_str()
        if r in seen_sutra_text:
            if same_sutra(seen_sutra_text[r], text):
                return          # restatement variant of the same sutra
            # collision: a genuinely different sutra landed on a taken ref
            review.append({"kind": "sutra_ref_collision", "ref": r,
                           "held": seen_sutra_text[r][:40], "new": text[:40]})
            advance(s=cur["s"] + 1)
            r = ref_str()
            if r in seen_sutra_text:
                return
        seen_sutra_text[r] = text
        counters[("sutra", r)] = 1
        unit = {"id": f"{r}.p1", "ref": r, "text": text}
        if cur_adhik["name"]:
            unit["adhikarana"] = cur_adhik["name"]
        layers["sutra"].append(unit)
        dv_map[f"sutra:{r}.p1"] = {"anchor": art["source"].get("anchor"),
                                   "url": art["source"].get("url")}

    n_articles = 0
    for art in items:
        bc = art.get("breadcrumb") or []
        if len(bc) > 2 and bc[2] == "तुलनात्मक विश्लेषण":
            # the site's comparative Shankara-bhashya section — deliberately
            # not part of the Madhva family tree
            review.append({"kind": "excluded_comparative", "id": art["id"]})
            continue
        a = ADHYAYA.get(bc[2]) if len(bc) > 2 else None
        p = PADA.get(bc[3]) if len(bc) > 3 else None
        adhikarana = bc[4] if len(bc) > 4 else ""
        if adhikarana:
            cur_adhik["name"] = re.sub(r"^[०-९0-9]+\.\s*", "", clean(adhikarana))
        elif len(bc) > 2 and bc[2] == "ग्रन्थारम्भः":
            cur_adhik["name"] = "मङ्गलाचरणम्"
        if len(bc) > 2 and bc[2] == "ग्रन्थारम्भः":
            a, p = 0, 0                       # mangala / upodghata: refs 0.0.n
        if a is None or p is None:
            review.append({"kind": "unplaced_article", "id": art["id"],
                           "breadcrumb": bc})
            continue
        advance(a=a, p=p)
        html = art.get("source_html") or ""
        if not html:
            # a few articles (sutra-only mula, mangala) were captured without
            # html — synthesize the element stream from the plain text. Layer
            # labels standing on their own line become headings, otherwise
            # every commentary of the mangala lands inside the bhashya as
            # inline text (the project lead's screenshots showed exactly that)
            lines = [ln for ln in (art.get("sanskrit_text") or "").split("\n")]
            def as_el(ln):
                t = clean(ln)
                if t and layer_for_heading(norm_head(t)):
                    return f"<h2>{ln}</h2>"
                return f"<p>{ln}</p>"
            html = "".join(as_el(ln) for ln in lines)
            review.append({"kind": "no_source_html_text_fallback", "id": art["id"]})
        n_articles += 1
        soup = BeautifulSoup(html, "html.parser")

        cur_layer = "bhashya" if "भाष्य" in (art["source"].get("layer") or "") else None
        pending: list[str] = []
        pending_heading: str | None = None
        first_p = True

        def flush(art=art):
            nonlocal pending, pending_heading
            if cur_layer and pending:
                for para in para_lines_to_paragraphs(pending):
                    # numbered restatements inside bhashya advance the ref
                    mm = OM_LINE.match(para.strip()) or None
                    if cur_layer == "bhashya" and mm:
                        num = mm.group(2)
                        register_sutra(mm.group(1),
                                       int(num.translate(DEVA_DIGIT)) if num else None,
                                       art)
                        continue
                    m2 = RESTATE.search(para)
                    if cur_layer == "bhashya" and m2 and para.strip().startswith(("।", "॥", "|", "ॐ")):
                        register_sutra(m2.group(1),
                                       int(m2.group(2).translate(DEVA_DIGIT)), art)
                        para = RESTATE.sub("", para, count=1).strip()
                        if not para:
                            continue
                    push(cur_layer, para, art,
                         heading=pending_heading)
                    pending_heading = None
            pending = []

        for el in soup.find_all(["h1", "h2", "h3", "h4", "p"]):
            txt = clean(el.get_text(" ", strip=True))
            if el.name.startswith("h"):
                head = norm_head(txt)
                if not head:
                    continue
                om = OM_LINE.match(head)
                if om:
                    # a sutra heading inside the flow: new sutra, back to bhashya
                    flush()
                    num = om.group(2)
                    register_sutra(om.group(1),
                                   int(num.translate(DEVA_DIGIT)) if num else None,
                                   art)
                    cur_layer = "bhashya"
                    continue
                slug = layer_for_heading(head)
                flush()
                if slug:
                    cur_layer = slug
                    pending_heading = None
                elif re.match(r"^[०-९0-9]+\.\s", head) or head.endswith("धिकरणम्"):
                    pass                       # adhikarana section heading
                else:
                    review.append({"kind": "unknown_heading", "id": art["id"],
                                   "heading": head, "at": ref_str()})
                    # keep current layer; keep the heading visible in text
                    pending.append(head)
                continue
            if not txt:
                continue
            if first_p:
                om = OM_LINE.match(txt)
                if om and art["source"].get("layer") == "मूलम्":
                    first_p = False
                    num = om.group(2)
                    register_sutra(om.group(1),
                                   int(num.translate(DEVA_DIGIT)) if num else None,
                                   art)
                    cur_layer = cur_layer or "bhashya"
                    continue
                if art["source"].get("layer") == "मूलम्" and adhikarana and (
                        txt.startswith(("१", "२", "३", "४", "५", "६", "७", "८", "९"))
                        or txt.rstrip("।॥ ").endswith("धिकरणम्")):
                    continue  # adhikarana heading line; the sutra follows
                ut = clean(art.get("unit_title") or "")
                if (art["source"].get("layer") == "मूलम्" and len(txt) <= 150
                        and ut and same_sutra(txt, ut)):
                    # small adhikaranas carry their sutra WITHOUT the OM
                    # wrapper; the article's own title names that sutra, so
                    # only a title-matching first line registers — prose
                    # first lines of continuation chunks never do
                    first_p = False
                    register_sutra(txt.strip("।॥| "), None, art)
                    cur_layer = cur_layer or "bhashya"
                    continue
                first_p = False
            pending.append(txt)
        flush()

    # ---- supplements ----------------------------------------------------
    # Six sutras of the edition that the flow never restates with usable
    # markers (they sit in standalone tika slices, plain lines, or one-sided
    # OM headings). Verified present in the DV source; anchored after the
    # sutra they follow. Restoring them brings the total to exactly the
    # traditional Madhva count of 564. Each lands with a review flag.
    SUPPLEMENTS = [
        ("1.4", "समाकर्षात्", "जगद्वाचित्वात्"),
        ("2.1", "अधिकं तु भेदनिर्देशात्", "अश्मादिवच्च तदनुपपत्तिः"),
        ("2.1", "उपसंहारदर्शनान्नेति चेन्न क्षीरवद्धि", "देवादिवदपि लोके"),
        ("3.2", "परमतः सेतून्मानसम्बन्धभेदव्यपदेशेभ्यः", "सामान्यात्तु"),
        ("3.3", "न सामान्यादप्युपलब्धेर्मृत्युवन्न हि लोकापत्तिः",
         "परेण च शब्दस्य ताद्विध्यं भूयस्त्वात्त्वनुबन्धः"),
        ("4.2", "वाङ्मनसि दर्शनाच्छब्दाच्च", "अत एव च सर्वाण्यनु"),
    ]
    for pada, after_txt, new_txt in SUPPLEMENTS:
        a, p = map(int, pada.split("."))
        pada_units = sorted((u for u in layers["sutra"]
                             if u["ref"].startswith(f"{a}.{p}.")),
                            key=lambda u: int(u["ref"].split(".")[2]))
        anchor = next((u for u in pada_units if same_sutra(u["text"], after_txt)), None)
        if anchor is None:
            review.append({"kind": "supplement_anchor_missing", "pada": pada,
                           "text": new_txt})
            continue
        at = int(anchor["ref"].split(".")[2]) + 1
        # shift every unit at >= `at` in this pada, in EVERY layer.
        # dv_map re-keying is two-phase (collect old, pop all, insert all)
        # so ref n and n+1 never collide mid-shift.
        remap = {}
        moves = []
        for lslug, units in layers.items():
            for u in units:
                ua, up, un = u["ref"].split(".")
                if int(ua) == a and int(up) == p and int(un) >= at:
                    new_ref = f"{a}.{p}.{int(un) + 1}"
                    remap[u["ref"]] = new_ref
                    old_id = u["id"]
                    u["ref"] = new_ref
                    u["id"] = new_ref + "." + old_id.rsplit(".", 1)[1]
                    moves.append((f"{lslug}:{old_id}", f"{lslug}:{u['id']}"))
        vals = {old: dv_map.pop(old) for old, _ in moves if old in dv_map}
        for old, new in moves:
            if old in vals:
                dv_map[new] = vals[old]
        for units in layers.values():
            for u in units:
                if "on" in u:
                    u["on"] = [remap.get(r, r) for r in u["on"]]
        new_ref = f"{a}.{p}.{at}"
        sup_unit = {"id": new_ref + ".p1", "ref": new_ref, "text": new_txt}
        if anchor.get("adhikarana"):
            sup_unit["adhikarana"] = anchor["adhikarana"]
        layers["sutra"].append(sup_unit)
        dv_map[f"sutra:{new_ref}.p1"] = {
            "anchor": None,
            "url": None,
            "note": "restored from the edition's own tika slices/headings; "
                    "see _review.json"}
        review.append({"kind": "sutra_supplemented", "ref": new_ref,
                       "text": new_txt})
    layers["sutra"].sort(key=lambda u: tuple(map(int, u["ref"].split("."))))

    # collapse artifact holes: where a supplement's +1 shift pushed an
    # edition-anchored number past a gap (e.g. tadoka's printed 17), pull
    # every number above the hole back down. Flagged, never silent — a
    # REAL edition hole would need the scholar, so it lands in _review.
    for pada in sorted({u["ref"].rsplit(".", 1)[0] for u in layers["sutra"]
                        if not u["ref"].startswith("0.")}):
        a, p = map(int, pada.split("."))
        nums = {int(u["ref"].split(".")[2]) for u in layers["sutra"]
                if u["ref"].startswith(pada + ".")}
        for hole in sorted(n for n in range(1, max(nums) + 1) if n not in nums):
            review.append({"kind": "hole_collapsed", "pada": pada, "at": hole})
            moves = []
            for lslug, units in layers.items():
                for u in units:
                    ua, up, un = u["ref"].split(".")
                    if int(ua) == a and int(up) == p and int(un) > hole:
                        old_id = u["id"]
                        u["ref"] = f"{a}.{p}.{int(un) - 1}"
                        u["id"] = u["ref"] + "." + old_id.rsplit(".", 1)[1]
                        moves.append((f"{lslug}:{old_id}", f"{lslug}:{u['id']}"))
            vals = {old: dv_map.pop(old) for old, _ in moves if old in dv_map}
            for old, new in moves:
                if old in vals:
                    dv_map[new] = vals[old]
            rm = {f"{a}.{p}.{n}": f"{a}.{p}.{n-1}" for n in range(hole + 1, max(nums) + 1)}
            for units in layers.values():
                for u in units:
                    if "on" in u:
                        u["on"] = [rm.get(r, r) for r in u["on"]]
            nums = {int(u["ref"].split(".")[2]) for u in layers["sutra"]
                    if u["ref"].startswith(pada + ".")}

    # ---- emit ----------------------------------------------------------
    DST.mkdir(parents=True, exist_ok=True)
    (DST / "_sources").mkdir(exist_ok=True)

    src_meta = doc.get("source_note", "")
    tika_authors = {}
    for sub in SRC.iterdir():
        if sub.is_dir() and (sub / "data.json").exists():
            try:
                d = json.loads((sub / "data.json").read_text(encoding="utf-8"))
                tika_authors[sub.name] = d.get("default_author", "")
            except Exception:
                pass

    work_layers = []
    order = ["sutra", "bhashya"] + sorted(k for k in layers if k.startswith("tika_"))
    for slug in order:
        units = layers.get(slug) or []
        if not units:
            continue
        author = {"sutra": "बादरायणः",
                  "bhashya": "श्रीमदानन्दतीर्थभगवत्पादाचार्यः",
                  "tika_tattvaprakashika": "श्रीजयतीर्थः",
                  "tika_tattvapradipika": "श्रीत्रिविक्रमपण्डिताचार्यः"}.get(
            slug) or SCHOLAR_AUTHORS.get(slug) or tika_authors.get(slug, "")
        entry = {"slug": slug,
                 "title": LAYER_TITLES.get(slug, slug),
                 "author": author,
                 "units": len(units)}
        co = COMMENTARY_ON.get(slug, "")
        if slug != "sutra":
            entry["commentary_on"] = co
            if not co:
                review.append({"kind": "commentary_chain_unverified", "layer": slug})
        work_layers.append(entry)
        (DST / slug).mkdir(exist_ok=True)
        (DST / slug / "data.json").write_text(json.dumps({
            "schema": "grantha_layer_v2",
            "work": "brahma_sutra",
            "layer": slug,
            "units": units,
        }, ensure_ascii=False, indent=1), encoding="utf-8")

    # the pada list is the UNION across layers: the mangala pada (0.0) has
    # bhashya/tika units but no sutra, so deriving it from the base layer
    # alone would make the mangalacharana unreachable in the reader
    all_padas = sorted(
        {".".join(u["ref"].split(".")[:2])
         for units in layers.values() for u in units},
        key=lambda p: [int(x) for x in p.split(".")])

    (DST / "work.json").write_text(json.dumps({
        "schema": "grantha_work_v2",
        "work": "brahma_sutra",
        "title": "ब्रह्मसूत्रम् (माध्वभाष्यादिसहितम्)",
        "ref_scheme": "adhyaya.pada.sutra",
        "review_status": "sutrapatha (all 564 sutras, positions and readings) "
                         "and commentary chains confirmed by a traditional "
                         "scholar, 3 Sep 2026 — tools/reports/"
                         "bs_scholar_sheet_filled.md. Patha-bheda vs the "
                         "Shankara patha: ashuddham-iti (Sh 3.1.25) and "
                         "antara-bhutagramavat-svatmanah (Sh 3.3.35) absent; "
                         "Sh 4.4.19 read and divided differently as our "
                         "4.4.20-21. Vivritti's author remains unidentified.",
        "padas": all_padas,
        "layers": work_layers,
        "licence_note": src_meta,
        "generated_by": "tools/compile_grantha_v2.py",
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    (DST / "_sources" / "dv_map.json").write_text(json.dumps({
        "site": "dvaitavedanta.in",
        "note": "paragraph id (layer:id) -> source article; full archived HTML "
                "stays in the legacy tree until migration completes",
        "map": dv_map,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    (DST / "_review.json").write_text(json.dumps({
        "note": "compiler anomalies for the project lead / next pass",
        "items": review,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---- report --------------------------------------------------------
    print(f"articles parsed: {n_articles}")
    per_pada: dict[str, int] = {}
    for u in layers["sutra"]:
        k = u["ref"].rsplit(".", 1)[0]
        per_pada[k] = max(per_pada.get(k, 0), int(u["ref"].rsplit(".", 1)[1]))
    total = sum(per_pada.values())
    print(f"sutras: {len(layers['sutra'])} units, max-numbered total {total}")
    for k in sorted(per_pada, key=lambda x: tuple(map(int, x.split(".")))):
        print(f"  pada {k}: {per_pada[k]}")
    for slug in order:
        if slug in layers:
            n = len(layers[slug])
            ch = sum(len(u['text']) for u in layers[slug])
            print(f"{slug:34s} {n:6d} units {ch:10,d} chars")
    print(f"review items: {len(review)}")
    import collections
    print("  ", dict(collections.Counter(r['kind'] for r in review)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
