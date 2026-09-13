"""DGE importer shared helpers. Runs on a GitHub Actions Ubuntu runner
(full network). Writes data.json in the DGE 'itihasa_purana_text' shape.
"""
import os, re, json, html, urllib.request

try:
    from indic_transliteration import sanscript
    from indic_transliteration.sanscript import transliterate
    def iast_to_dev(s):
        return transliterate(s, sanscript.IAST, sanscript.DEVANAGARI)
except Exception:                       # allows --dry parse tests without the dep
    def iast_to_dev(s):
        raise RuntimeError("pip install indic-transliteration (see importers/requirements.txt)")

def http_get(url, timeout=90):
    req = urllib.request.Request(url, headers={"User-Agent": "DGE-importer/1.0 (educational)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")

def strip_html(doc):
    # <style>/<script> element CONTENT (CSS/JS text) survives a plain
    # tag-stripping regex -- only the tag delimiters get removed, not what's
    # between them -- and some GRETIL pages embed a <style> block directly
    # inside the body/<pre> content, not just in <head>. Confirmed for real:
    # narada_smriti's live page did exactly this, and the CSS text got
    # transliterated character-by-character into the first "verse" as
    # garbage (e.g. "font-family" -> nonsense Devanagari) before this fix.
    doc = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", "", doc, flags=re.S | re.I)
    m = re.search(r"<pre[^>]*>(.*?)</pre>", doc, re.S | re.I)
    txt = re.sub(r"<[^>]+>", "", m.group(1) if m else doc)
    return html.unescape(txt)

def data_base():
    return "dge/data" if os.path.isdir("dge/data") else ("data" if os.path.isdir("data") else "dge/data")

def write_grantha(rel_path, schema, default_author, items, **extra):
    folder = os.path.join(data_base(), rel_path)
    os.makedirs(folder, exist_ok=True)
    fp = os.path.join(folder, "data.json")
    # **extra lets a caller record source_url/source_note/licence alongside
    # the text itself (the project's own standing policy: every import
    # notes its source and licence for future reference) without every
    # importer needing its own bespoke json.dump call.
    doc = {"schema": schema, "default_author": default_author}
    doc.update(extra)
    doc["items"] = items
    json.dump(doc, open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    n = sum(len(it.get("shlokas", [])) for it in items)
    print(f"  wrote {fp}  ({len(items)} units, {n} shlokas)")

try:
    from indic_transliteration import sanscript as _sc
    from indic_transliteration.sanscript import transliterate as _trx
    def itrans_to_dev(s):
        return _trx(s, _sc.ITRANS, _sc.DEVANAGARI)
    def itrans_to_iast(s):
        return _trx(s, _sc.ITRANS, _sc.IAST)
except Exception:
    def itrans_to_dev(s):
        raise RuntimeError("pip install indic-transliteration (see importers/requirements.txt)")
    def itrans_to_iast(s):
        raise RuntimeError("pip install indic-transliteration (see importers/requirements.txt)")

def to_text(doc):
    """HTML -> text preserving line breaks (for GRETIL corpustei + 1_sanskr
    pages). Unlike strip_html() above, this doesn't assume a <pre> wrapper
    or single-line-per-verse markup -- some GRETIL pages (the newer
    corpustei/transformations exports, e.g. harivamsha) structure each line
    with real HTML block tags (<l>, <lg>, <p>) instead of plain-text
    newlines inside one <pre>, so treating the whole page as one blob (or
    just extracting <pre> content) collapses all the line structure the
    parser below actually needs. Also strips <style>/<script> element
    content specifically (not just their tags) for the same reason
    strip_html() does -- belt and suspenders with gretil.py's own
    stray-line-drop logic below."""
    doc = re.sub(r"(?i)<(script|style)\b[^>]*>.*?</\1>", "", doc, flags=re.S)
    # The whole <head> too, not just style/script: legacy 1_sanskr pages put
    # the work's name in <title>, which otherwise leaks into the first verse.
    doc = re.sub(r"(?is)<head\b[^>]*>.*?</head>", "", doc)
    doc = re.sub(r"(?i)<br\s*/?>", "\n", doc)
    doc = re.sub(r"(?i)</(p|div|lg|l|tr|li|h[1-6])\s*>", "\n", doc)
    doc = re.sub(r"<[^>]+>", "", doc)
    return html.unescape(doc)
