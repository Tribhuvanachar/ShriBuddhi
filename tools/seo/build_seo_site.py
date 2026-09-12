#!/usr/bin/env python3
"""Build the crawlable DGE: one static HTML document per section of every public grantha (tools/seo, 7 Sep 2026).

    python3 tools/seo/build_seo_site.py --out _site [--only vedas/rigveda] [--no-translit] [--quiet]

Reads dge/data/library.json + each data.json, decides pages (see paginate()), and writes under <out>:
    <publicRoot>/<category>/…/index.html         category index pages (children, counts, descriptions)
    <publicRoot>/…/<grantha>/index.html          the grantha: its text when it fits, else a section index
    <publicRoot>/…/<grantha>/<section>/index.html  sūkta / adhyāya / sarga / part pages with the verses inline
    sitemap.xml (+ sitemap-pages-N.xml)          canonical URLs only
    robots.txt                                   the repo's, with the sitemap line
    dge/data/seo_urls.json                       slug → canonical URL/title, also written into the repo so the
                                                 interactive reader can point its rel=canonical at the page

Every page: unique <title> and description, <link rel=canonical>, <html lang="sa">, visible breadcrumbs and a
BreadcrumbList, an <h1>, the Sanskrit text as Unicode with IAST beside it, prev/next and parent/child <a href>
links, a link into the interactive reader (short form ?rv1.1 when a key exists), JSON-LD (WebPage/CollectionPage
+ the work as a CreativeWork). No JavaScript is needed to read a page. Nothing is written into dge/data except
seo_urls.json; the generated tree is a deploy artifact (see .github/workflows/seo-pages.yml), never committed.
"""
import argparse, html, json, re, subprocess, sys, time
from collections import OrderedDict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import taxonomy as T  # noqa: E402

ROOT = T.ROOT
CFG = T.CFG
PUBLIC_TRANSLATION_KEYS = CFG.get("translationKeys", ["griffith", "macdonell"])
LEVEL2 = {"vedas/rigveda": "sukta", "vedas/atharvaveda": "sukta", "vedas/yajurveda/krishna_yajurveda/taittiriya_shakha": "prapathaka",
          "vedas/yajurveda/shukla_yajurveda": "adhyaya"}
LEVEL2_SA = {"sukta": "सूक्तम्", "prapathaka": "प्रपाठकः", "adhyaya": "अध्यायः", "part": "भागः"}
UNIT_WORD = {"vedas": ("mantra", "मन्त्रः"), "default": ("verse", "श्लोकः")}
NOW = time.strftime("%Y-%m-%d")


def is_generic_leaf(seg):
    """sarga_1, mandala_01, kanda_02 … and text layers (tika_x, bhashya, saartha) name nothing on their own."""
    return bool(re.match(r"^[a-z]+_\d+$", seg, re.I)) or seg not in T.LABELS or seg.startswith("tika_") or seg in ("bhashya", "saartha", "vritti", "parishishta")


STRUCTURAL = {"samhita", "mula", "brahmanas", "brahmana", "aranyakas", "aranyaka", "upanishads", "upanishad", "composers", "bhashya", "saartha", "vritti"}
ROOTS = set(CFG.get("rootMap", {}).keys())


def work_name(slug, crumbs):
    """(sa, en) for a grantha page: the leaf label joined with the nearest ancestor that names a WORK — skipping
    structural levels (saṃhitā, mūla) and top-level traditions (vedas) — with any numbered levels in between kept
    (shatapatha_brahmana/kanda_14/tika_sayana → शतपथब्राह्मणम् काण्डम् १४ Tika Sayana / Tika Sayana — Kāṇḍa 14 — Śatapatha)."""
    segs = slug.split("/")
    leaf_sa, leaf_en = crumbs[-1][0], crumbs[-1][1]
    leaf = segs[-1]
    is_layer = leaf in STRUCTURAL or leaf.startswith("tika_") or (leaf not in T.LABELS and not re.match(r"^[a-z]+_\d+$", leaf, re.I) and any(k in leaf for k in ("bhashya", "tika", "vritti", "saartha", "vyakhya")))
    want = 2 if is_layer else 1          # a layer of a work is named by the work AND the folder above it (the author / tradition)
    mids, works = [], []
    for k in range(len(segs) - 2, 0, -1):
        seg = segs[k]; prefix = "/".join(segs[: k + 1])
        if re.match(r"^[a-z]+_\d+$", seg, re.I) and not works:
            mids.append((T.label_sa(seg, prefix), T.label_en(seg))); continue
        if seg in STRUCTURAL or seg.startswith("tika_") or seg in ROOTS:
            continue
        works.append((T.label_sa(seg, prefix), T.label_en(seg)))
        if len(works) >= want: break
    mids.reverse()
    sa = " ".join([w[0] for w in reversed(works)] + [m[0] for m in mids] + [leaf_sa])
    en = " — ".join([leaf_en] + [m[1] for m in reversed(mids)] + [w[1] for w in works])
    return sa.strip(), en.strip()


_TAX_HOLDER = []


def snippet(text, n=110):
    t = re.sub(r"\s+", " ", text or "").strip()
    t = re.sub(r"\s*[|।॥]+\s*[\d०-९]*\s*[|।॥]*\s*$", "", t)
    return t[:n]


def strip_html(s):
    s = re.sub(r"<br\s*/?>", "\n", str(s or ""), flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return html.unescape(s).strip()


def esc(s):
    return html.escape(str(s or ""), quote=True)


def text_of(rec):
    if isinstance(rec, str):
        return strip_html(rec)
    for k in ("sanskrit_text", "samhita_patha", "sa", "text", "devanagari"):
        v = rec.get(k)
        if isinstance(v, dict):
            v = v.get("devanagari") or v.get("sa")
        if v:
            return strip_html(v)
    return ""


def translation_of(rec):
    """Only public-domain / configured translation fields, never the unreviewed AI commentaries."""
    if not isinstance(rec, dict):
        return []
    out = []
    tr = rec.get("translation")
    if isinstance(tr, str) and tr.strip():
        out.append(("Translation", strip_html(tr)))
    elif isinstance(tr, list):
        for t in tr[:2]:
            if isinstance(t, str) and t.strip(): out.append(("Translation", strip_html(t)))
            elif isinstance(t, dict) and t.get("text"): out.append((t.get("source") or "Translation", strip_html(t["text"])))
    if rec.get("artha"):
        out.append(("अर्थः", strip_html(rec["artha"])))
    com = rec.get("commentaries")
    if isinstance(com, dict):
        for k in PUBLIC_TRANSLATION_KEYS:
            if com.get(k):
                out.append((k.replace("_", " ").title(), strip_html(com[k])))
    return out[:3]


def unit_from(rec, uid, number=None):
    return {"id": uid, "n": number, "sa": text_of(rec), "tr": translation_of(rec),
            "rishi": rec.get("rishi") if isinstance(rec, dict) else None, "devata": rec.get("devata") if isinstance(rec, dict) else None,
            "chandas": rec.get("chandas") if isinstance(rec, dict) else None,
            "title": strip_html((rec.get("unit_title") or rec.get("reference") or "") if isinstance(rec, dict) else "")}


def load_units(doc):
    """→ (kind, units, sections): kind 'nested' | 'vedic3' | 'vedic2' | 'flat'; sections only for nested."""
    items = doc.get("items")
    sh = doc.get("shlokas")
    if isinstance(items, list) and items:
        nested = [x for x in items if isinstance(x, dict) and isinstance(x.get("shlokas"), list) and x["shlokas"]]
        if nested:
            sections = []
            seq = 0
            for it in items:
                us = []
                for s in it.get("shlokas") or []:
                    seq += 1
                    us.append(unit_from(s, seq, s.get("number")))
                if us:
                    sections.append({"id": str(it.get("id") or ""), "ref": strip_html(it.get("reference") or ""), "units": us})
            return "nested", None, sections
        units = [unit_from(x, str(x.get("id") or i + 1), i + 1) for i, x in enumerate(items) if isinstance(x, dict)]
        ids = [u["id"] for u in units]
        if ids and all(re.match(r"^\d+\.\d+\.\d+$", i) for i in ids):
            return "vedic3", units, None
        if ids and all(re.match(r"^\d+\.\d+$", i) for i in ids):
            return "vedic2", units, None
        return "flat", units, None
    if isinstance(sh, dict):
        units = []
        for k in sorted(sh, key=lambda x: int(x) if str(x).isdigit() else 0):
            units.append(unit_from(sh[k], str(k), int(k) if str(k).isdigit() else None))
        return "flat", units, None
    return "flat", [], None


def size_of(units):
    return sum(len(u["sa"].encode("utf-8")) for u in units)


def chunk(units, max_bytes):
    out, cur, n = [], [], 0
    for u in units:
        b = len(u["sa"].encode("utf-8")) + 200
        if cur and n + b > max_bytes:
            out.append(cur); cur, n = [], 0
        cur.append(u); n += b
    if cur:
        out.append(cur)
    return out


def paginate(slug, doc, max_bytes):
    """→ list of pages: {seg (url segment or '' for the grantha page itself), label_sa, label_en, units, kind}."""
    kind, units, sections = load_units(doc)
    pages = []
    if kind == "nested":
        for sec in sections:
            m = re.match(r"^([a-z]+)_0*(\d+)$", sec["id"], re.I)
            if m:
                word, n = m.group(1).lower(), int(m.group(2))
                seg = f"{word}-{n}"; la = (T.NUMBERED.get(word) or T.auto_label(word)) + " " + T.deva_num(n); le = (T.iast(T.NUMBERED.get(word, "")) or word.title()) + " " + str(n)
            else:
                seg = T.slugify_segment(sec["id"]); shown = (sec["ref"] or "")[:70]
                la = f"{sec['id']} · {shown}" if shown else sec["id"]; le = la
            for i, part in enumerate(chunk(sec["units"], max_bytes)):
                pages.append({"seg": seg + (f"/part-{i + 1}" if i else ""), "label_sa": la + (f" भागः {T.deva_num(i + 1)}" if i else ""),
                              "label_en": le + (f" part {i + 1}" if i else ""), "units": part, "ref": sec["ref"]})
        return pages
    if kind in ("vedic3", "vedic2"):
        lvl = next((v for k, v in LEVEL2.items() if slug.startswith(k)), "section")
        groups = OrderedDict()
        for u in units:
            parts = [str(int(x)) if x.isdigit() else x for x in u["id"].split(".")]   # '01.1' and '1.1' are one sūkta
            key = ".".join(parts[:2]) if kind == "vedic3" else parts[0]
            groups.setdefault(key, []).append(u)
        # Only when every group shares the same leading numbers (Ṛgveda maṇḍala 1: 1.1 … 1.191) does the last number
        # name the section on its own; otherwise (Muṇḍaka 1.1, 2.1, 3.1) the whole key is the name.
        heads = {".".join(k.split(".")[:-1]) for k in groups}
        known = lvl in LEVEL2_SA and len(heads) == 1
        for key, us in groups.items():
            last = key.split(".")[-1]
            n = int(last) if last.isdigit() else None
            if known and n:                       # Ṛgveda 1.24 → sūkta 24 (the first number is the file itself)
                la = LEVEL2_SA[lvl] + " " + T.deva_num(n); le = T.iast(LEVEL2_SA[lvl]) + " " + str(n); seg0 = f"{lvl}-{n}"
            else:                                  # an unknown layout keeps the whole key: section 2.1 → section-2-1
                shown = ".".join(T.deva_num(x) if x.isdigit() else x for x in key.split("."))
                la = "विभागः " + shown; le = "Section " + key; seg0 = "section-" + "-".join(T.slugify_segment(x) for x in key.split("."))
            for i, part in enumerate(chunk(us, max_bytes)):
                pages.append({"seg": seg0 + (f"/part-{i + 1}" if i else ""), "label_sa": la + (f" भागः {T.deva_num(i + 1)}" if i else ""),
                              "label_en": le + (f" part {i + 1}" if i else ""), "units": part, "ref": key})
        return pages
    parts = chunk(units, max_bytes)
    if len(parts) <= 1:
        return [{"seg": "", "label_sa": "", "label_en": "", "units": units, "ref": ""}]
    for i, part in enumerate(parts):
        pages.append({"seg": f"part-{i + 1}", "label_sa": f"भागः {T.deva_num(i + 1)}", "label_en": f"Part {i + 1}", "units": part, "ref": ""})
    return pages


# ---------------------------------------------------------------- short keys (js/shortcuts.js table) ----
def load_shortcut_table():
    try:
        out = subprocess.run(["node", "-e", "global.window={};require(process.argv[1]);console.log(JSON.stringify(window.DGEShortcuts.table.map(e=>({key:e.key,kind:e.kind,path:e.path||null,parts:e.parts||null,unit:e.unit||null,pick:!!e.pick}))))",
                              str(ROOT / "dge/js/shortcuts.js")], capture_output=True, text=True, check=True).stdout
        return json.loads(out)
    except Exception:  # noqa: BLE001
        return []


def short_key(table, slug, page, kind_hint):
    for e in table:
        n1 = None
        if e["parts"]:
            m = re.match(e["path"].replace("{part}", "([a-z]+)").replace("/", "\\/") + "$", slug)
            if not m: continue
            try: n1 = e["parts"].index(m.group(1)) + 1
            except ValueError: continue
        elif e["path"]:
            rx = re.sub(r"\{1(?::\d)?\}", r"(\\d+)", e["path"].replace("/", "\\/")) + "$"
            m = re.match(rx, slug)
            if not m: continue
            n1 = int(m.group(1)) if m.groups() else None
        elif e["pick"]:
            if "samaveda/kauthuma_shakha/samhita" not in slug: continue
        else:
            continue
        ref = page.get("ref") or ""
        if e["kind"] == "vedic":
            if e["pick"]:
                u = page["units"][0]["id"] if page["units"] else ""
                return e["key"] + u if u.isdigit() else None
            if ref and re.match(r"^[\d.]+$", ref):
                return e["key"] + ref
            return e["key"] + str(n1) if n1 else None
        if e["kind"] == "shloka":
            return e["key"] + (str(n1) if n1 else "")
        if e["kind"] == "unit":
            m2 = re.search(r"(\d+)$", page.get("seg", "").split("/")[0])
            if n1 and m2: return f"{e['key']}{n1}.{int(m2.group(1))}"
            if m2: return f"{e['key']}{int(m2.group(1))}"
            return e["key"] + str(n1) if n1 else None
    return None


# ---------------------------------------------------------------- HTML ----
CSS = """
:root{color-scheme:light dark;--fg:#1c1712;--bg:#fbf7f0;--mut:#6d6157;--acc:#7a3b1d;--line:#e6dccb;--card:#fff}
@media(prefers-color-scheme:dark){:root{--fg:#efe6d8;--bg:#15110d;--mut:#b7a994;--acc:#e8b24d;--line:#3a3129;--card:#1e1813}}
body{margin:0;background:var(--bg);color:var(--fg);font-family:'Noto Sans Devanagari','Noto Serif Devanagari',Inter,system-ui,sans-serif;line-height:1.7}
header,main,footer{max-width:860px;margin:0 auto;padding:12px 18px}
header{border-bottom:1px solid var(--line)} .site{font-weight:700;color:var(--acc);text-decoration:none}
nav.crumbs ol{list-style:none;padding:0;margin:8px 0 0;display:flex;flex-wrap:wrap;gap:4px;font-size:14px}
nav.crumbs li+li:before{content:'›';margin:0 4px;color:var(--mut)} nav.crumbs a{color:var(--acc)}
h1{font-size:1.5rem;margin:14px 0 4px} .en{color:var(--mut);font-size:.95rem} .meta{color:var(--mut);font-size:.9rem;margin:6px 0 14px}
article.v{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin:10px 0}
article.v .n{color:var(--mut);font-size:.8rem} article.v p.sa{font-size:1.15rem;margin:4px 0;white-space:pre-line}
article.v p.tl{color:var(--mut);font-size:.95rem;margin:4px 0;white-space:pre-line} article.v p.tr{margin:6px 0 0;font-size:.95rem;white-space:pre-line}
article.v .attr{font-size:.8rem;color:var(--mut)} ul.kids{padding-left:18px} ul.kids li{margin:4px 0} .kids .cnt{color:var(--mut);font-size:.85rem}
nav.pn{display:flex;justify-content:space-between;gap:12px;margin:18px 0;font-size:.95rem} nav.pn a{color:var(--acc)}
.open{display:inline-block;margin:10px 0;padding:8px 14px;border:1px solid var(--acc);border-radius:999px;color:var(--acc);text-decoration:none}
footer{color:var(--mut);font-size:.85rem;border-top:1px solid var(--line);margin-top:24px}
"""


class Site:
    def __init__(self, out, quiet=False, translit=True):
        self.out = Path(out); self.quiet = quiet; self.translit = translit
        self.origin = CFG["siteOrigin"].rstrip("/") + CFG.get("sitePrefix", "").rstrip("/")
        self.site_name = CFG.get("siteName", "Sarvamūla Digital Library")
        self.lib = json.load(open(ROOT / "dge/data/library.json", encoding="utf-8"))["granthas"]
        self.by_slug = {g["path"].replace("dge/data/", "").replace("/data.json", ""): g for g in self.lib}
        self.slugs = T.public_slugs(self.lib)
        self.tax = T.Taxonomy(self.slugs)
        self.table = load_shortcut_table()
        self.urls = []              # (url, lastmod)
        self.url_map = {}           # slug → {url, title}
        self.titles = {}
        self.children = {}          # category prefix → [(label_sa, label_en, url, count, is_grantha)]
        self.stats = {"pages": 0, "units": 0, "bytes": 0}
        self._written = set()

    # ---- pieces ----
    def abs_url(self, u): return self.origin + u
    def reader_url(self, slug, jump=None):
        u = f"{CFG.get('sitePrefix', '')}/dge/index.html?path={slug}"
        return u + (f"&jumpShloka={jump}" if jump else "")
    def write(self, url, html_text):
        p = self.out / url.strip("/") / "index.html"
        if url in self._written:
            raise SystemExit(f"two pages want the same URL: {url} (second: {html_text[html_text.find('<title>') + 7: html_text.find('</title>')]})")
        self._written.add(url)
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.exists() and 'name="generator" content="dge-seo"' not in p.read_text(encoding="utf-8", errors="replace")[:2000]:
            raise SystemExit(f"refusing to overwrite a hand-written page with a generated one: {p} ({url})")
        p.write_text(html_text, encoding="utf-8")
        self.stats["pages"] += 1; self.stats["bytes"] += len(html_text.encode("utf-8"))

    def shell(self, *, url, title, desc, h1_sa, h1_en, crumbs, body, jsonld, extra_head=""):
        crumb_items = crumbs + []
        ol = "".join(f'<li><a href="{esc(c[2])}">{esc(c[0])}</a></li>' if c[2] and c[2] != url else f'<li aria-current="page">{esc(c[0])}</li>' for c in crumb_items)
        bl = {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": self.site_name, "item": self.abs_url(CFG.get("publicRoot", "/dge") + "/")}] + [
            {"@type": "ListItem", "position": i + 2, "name": f"{c[0]} ({c[1]})" if c[1] and c[1] != c[0] else c[0], "item": self.abs_url(c[2])} for i, c in enumerate(crumb_items) if c[2]]}
        ld = [dict(jsonld, **{"@context": "https://schema.org"}), dict(bl, **{"@context": "https://schema.org"})]
        return f"""<!DOCTYPE html>
<html lang="sa">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="generator" content="dge-seo">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{esc(self.abs_url(url))}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:type" content="article">
<meta property="og:url" content="{esc(self.abs_url(url))}">
<meta property="og:site_name" content="{esc(self.site_name)}">
<link rel="icon" href="{esc(CFG.get('sitePrefix', ''))}/dge/images/genie/favicon-48.png">
{extra_head}<style>{CSS}</style>
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>
</head>
<body>
<header><a class="site" href="{esc(CFG.get('sitePrefix', ''))}/">{esc(self.site_name)}</a> · <a href="{esc(CFG.get('publicRoot', '/dge'))}/">Library</a>
<nav class="crumbs" aria-label="Breadcrumb"><ol><li><a href="{esc(CFG.get('publicRoot', '/dge'))}/">DGE</a></li>{ol}</ol></nav></header>
<main>
<h1>{esc(h1_sa)}</h1>{f'<div class="en" lang="sa-Latn">{esc(h1_en)}</div>' if h1_en and h1_en != h1_sa else ''}
{body}
</main>
<footer>{esc(self.site_name)} · <a href="{esc(CFG.get('sitePrefix', ''))}/dge/index.html">Interactive reader</a> · <a href="{esc(self.tax.catalogue)}">All texts</a></footer>
</body>
</html>
"""

    def unit_html(self, u, slug, unit_word_sa, anchor_prefix="v"):
        n = u["n"] if u["n"] is not None else u["id"]
        aid = f"{anchor_prefix}-{re.sub(r'[^A-Za-z0-9.]+', '-', str(u['id'] or n))}"
        head = f'<div class="n"><a href="#{aid}">{esc(unit_word_sa)} {esc(T.deva_num(n) if str(n).isdigit() else n)}</a>' + (f' · {esc(u["id"])}' if u["id"] and str(u["id"]) != str(n) and re.match(r"^[\d.]+$", str(u["id"])) else "") + \
               (f' · <span lang="sa">{esc(u["title"])}</span>' if u["title"] and u["title"] != str(n) else "") + "</div>"
        sa = f'<p class="sa" lang="sa">{esc(u["sa"])}</p>'
        tl = f'<p class="tl" lang="sa-Latn">{esc(T.iast(u["sa"]))}</p>' if self.translit and u["sa"] else ""
        attr = ""
        if u.get("rishi") or u.get("devata") or u.get("chandas"):
            attr = '<div class="attr" lang="sa">' + " · ".join(f"{k} {esc(v)}" for k, v in (("ऋषिः", u.get("rishi")), ("देवता", u.get("devata")), ("छन्दः", u.get("chandas"))) if v) + "</div>"
        tr = "".join(f'<p class="tr" lang="{"sa" if lab == "अर्थः" else "en"}"><b>{esc(lab)}:</b> {esc(t)}</p>' for lab, t in u["tr"])
        return f'<article class="v" id="{aid}">{head}{sa}{tl}{attr}{tr}</article>'

    # ---- pages ----
    def build_grantha(self, slug):
        g = self.by_slug[slug]
        try:
            doc = json.load(open(ROOT / "dge/data" / slug / "data.json", encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            print("  skip", slug, e); return
        crumbs = self.tax.crumbs(slug)
        url = self.tax.url(slug)
        work_sa, work_en = work_name(slug, crumbs)
        meta = doc.get("metadata") or {}
        author = strip_html(meta.get("author") or (g.get("facets") or {}).get("default_author") or "")
        if author.lower() in ("unspecified", "unknown", "none"): author = ""
        src = g.get("source") or {}
        pages = paginate(slug, doc, CFG.get("maxTextBytesPerPage", 90000))
        unit_word = UNIT_WORD["vedas" if slug.startswith("vedas/") else "default"]
        total_units = sum(len(p["units"]) for p in pages)
        self.stats["units"] += total_units
        work_ld = {"@type": "CreativeWork", "name": work_sa, "alternateName": work_en, "inLanguage": "sa", "url": self.abs_url(url)}
        if author: work_ld["author"] = {"@type": "Person", "name": author}
        if src.get("licence"): work_ld["license"] = src["licence"] if src["licence"].startswith("http") else None
        work_ld = {k: v for k, v in work_ld.items() if v}
        parent = crumbs[-2] if len(crumbs) > 1 else None
        multi = len(pages) > 1 or bool(pages and pages[0]["seg"])
        # everything registered under this page's own URL (layers such as ṭīkā / bhāṣya / sārtha, and any sub-folder
        # whose collapsed URL is this one) is linked from here, so no page is left without a parent link
        rows = [r for r in self.children.get(url, []) if r[2] != url]
        layers_html = ""
        if rows:
            seen = set(); uniq = [r for r in rows if not (r[2] in seen or seen.add(r[2]))]
            lis = "".join(f'<li>{"📖 " if r[4] else "📁 "}<a href="{esc(r[2])}">{esc(r[0])}</a> <span class="en" lang="sa-Latn">{esc(r[1])}</span></li>' for r in uniq)
            layers_html = f'<h2 class="en">Commentaries and other layers of this text</h2><ul class="kids">{lis}</ul>'
        self._layers_html = layers_html
        # the grantha page: the text itself (single page) or a section index
        if not multi:
            p = pages[0] if pages else {"units": [], "seg": "", "ref": ""}
            self._write_text_page(slug, url, crumbs, work_sa, work_en, author, p, None, None, unit_word, work_ld, total_units, is_grantha=True)
        else:
            lis = []
            for p in pages:
                purl = url + p["seg"] + "/"
                first = p["units"][0]["sa"].split("\n")[0][:80] if p["units"] else ""
                lis.append(f'<li><a href="{esc(purl)}">{esc(p["label_sa"])}</a> <span class="en" lang="sa-Latn">{esc(p["label_en"])}</span> <span class="cnt">· {len(p["units"])} {unit_word[0]}{"s" if len(p["units"]) != 1 else ""}</span><br><span lang="sa" class="cnt">{esc(first)}</span></li>')
            body = f'<div class="meta">{esc(author) + " · " if author else ""}{len(pages)} sections · {total_units} {unit_word[0]}s · Sanskrit (Devanagari) with IAST</div>' \
                   f'<a class="open" href="{esc(self.reader_url(slug))}">Open in the interactive reader →</a><ul class="kids">{"".join(lis)}</ul>' + layers_html
            title = f"{work_en} · {work_sa} — contents | {self.site_name}"
            desc = f"{work_en}: {len(pages)} sections, {total_units} {unit_word[0]}s of Sanskrit text with transliteration" + (f", by {author}" if author else "") + f". {work_sa}."
            ld = {"@type": "CollectionPage", "name": title, "url": self.abs_url(url), "inLanguage": "sa", "about": work_ld,
                  "hasPart": [{"@type": "WebPage", "name": f"{p['label_en']} — {work_en}", "url": self.abs_url(url + p["seg"] + "/")} for p in pages[:200]]}
            self.write(url, self.shell(url=url, title=title, desc=desc, h1_sa=work_sa, h1_en=work_en, crumbs=crumbs, body=body, jsonld=ld))
            self._register(url, title, slug=slug)
            for i, p in enumerate(pages):
                prev = pages[i - 1] if i > 0 else None; nxt = pages[i + 1] if i + 1 < len(pages) else None
                self._write_text_page(slug, url + p["seg"] + "/", crumbs, work_sa, work_en, author, p, prev, nxt, unit_word, work_ld, total_units, is_grantha=False, grantha_url=url)
        pass

    def _write_text_page(self, slug, url, crumbs, work_sa, work_en, author, p, prev, nxt, unit_word, work_ld, total_units, is_grantha, grantha_url=None):
        n = len(p["units"])
        sec_sa, sec_en = p.get("label_sa", ""), p.get("label_en", "")
        h1_sa = f"{work_sa} · {sec_sa}" if sec_sa else work_sa
        h1_en = f"{work_en} · {sec_en}" if sec_en else work_en
        title = f"{sec_en + ' — ' if sec_en else ''}{work_en} · {work_sa}{' ' + sec_sa if sec_sa else ''} | {self.site_name}"
        first = p["units"][0]["sa"].replace("\n", " ") if p["units"] else ""
        first_l = snippet(T.iast(first) if self.translit else first)
        rd = p["units"][0] if p["units"] else {}
        attrs = " · ".join(f"{k} {v}" for k, v in (("ṛṣi", rd.get("rishi")), ("devatā", rd.get("devata")), ("chandas", rd.get("chandas"))) if v)
        desc = f"{h1_en}: {n} {unit_word[0]}{'s' if n != 1 else ''} in Sanskrit with IAST transliteration" + (f", by {author}" if author else "") + (f". {attrs}" if attrs else "") + (f'. Begins: "{first_l}…"' if first_l else "")
        if len(desc) > 300: desc = desc[:297].rsplit(" ", 1)[0] + "…"
        crumbs2 = crumbs + ([(sec_sa, sec_en, url)] if sec_sa else [])
        sk = short_key(self.table, slug, p, None)
        open_link = f'<a class="open" href="{esc(self.reader_url(slug, p["units"][0]["n"] if p["units"] and p["units"][0]["n"] else None))}">Open in the interactive reader →</a>' + \
                    (f' <span class="en">short address: <code>{esc(CFG.get("sitePrefix", ""))}/?{esc(sk)}</code></span>' if sk else "")
        meta = f'<div class="meta">{esc(author) + " · " if author else ""}{n} {unit_word[0]}{"s" if n != 1 else ""} · Sanskrit (Devanagari) with IAST' + (f' · <a href="{esc(grantha_url)}">all sections</a>' if grantha_url else "") + "</div>"
        pn = ""
        if prev or nxt:
            base = grantha_url or url
            pn = '<nav class="pn" aria-label="Sections">' + (f'<a rel="prev" href="{esc(base + prev["seg"] + "/")}">← {esc(prev["label_sa"])}</a>' if prev else "<span></span>") + \
                 (f'<a rel="next" href="{esc(base + nxt["seg"] + "/")}">{esc(nxt["label_sa"])} →</a>' if nxt else "<span></span>") + "</nav>"
        body = meta + open_link + pn + "".join(self.unit_html(u, slug, unit_word[1]) for u in p["units"]) + pn + (getattr(self, "_layers_html", "") if is_grantha else "")
        ld = {"@type": "WebPage", "name": title, "url": self.abs_url(url), "inLanguage": "sa", "isPartOf": {"@type": "WebSite", "name": self.site_name, "url": self.abs_url("/")},
              "about": work_ld, "mainEntity": {"@type": "CreativeWork", "name": h1_sa, "alternateName": h1_en, "inLanguage": "sa", "isPartOf": work_ld, "position": p.get("ref") or None}}
        ld["mainEntity"] = {k: v for k, v in ld["mainEntity"].items() if v}
        extra = (f'<link rel="prev" href="{esc(self.abs_url((grantha_url or url) + prev["seg"] + "/"))}">' if prev else "") + (f'<link rel="next" href="{esc(self.abs_url((grantha_url or url) + nxt["seg"] + "/"))}">' if nxt else "")
        self.write(url, self.shell(url=url, title=title, desc=desc, h1_sa=h1_sa, h1_en=h1_en, crumbs=crumbs2, body=body, jsonld=ld, extra_head=extra))
        self._register(url, title, slug=slug if is_grantha else None)

    def _register(self, url, title, slug=None):
        if title in self.titles:
            self.titles[title] += 1
        else:
            self.titles[title] = 1
        self.urls.append((url, NOW))
        if slug:
            self.url_map[slug] = {"url": url, "title": title}

    def _add_child(self, parent_url, row):
        self.children.setdefault(parent_url, []).append(row)

    def plan(self):
        """Register every page under its parent URL before anything is written: granthas under the nearest crumb
        above them, categories under theirs. Grantha pages and category pages both read this map."""
        self._prefixes = self.tax.category_prefixes()
        self._counts = {}
        for s in self.slugs:
            parts = s.split("/")
            for i in range(1, len(parts)):
                self._counts["/".join(parts[:i])] = self._counts.get("/".join(parts[:i]), 0) + 1
        self._cat_urls = {p: self.tax.prefix_url(p) for p in self._prefixes}
        for p in self._prefixes:
            parent = p.rsplit("/", 1)[0] if "/" in p else ""
            purl = self._cat_urls.get(parent) if parent else self.tax.catalogue
            if purl and self._cat_urls.get(p) and self._cat_urls[p] != purl:
                seg = p.rsplit("/", 1)[-1]
                self._add_child(purl, (T.label_sa(seg, p), T.label_en(seg), self._cat_urls[p], self._counts.get(p, 0), False))
        for s in self.slugs:
            crumbs = self.tax.crumbs(s)
            url = self.tax.url(s)
            parent_url = crumbs[-2][2] if len(crumbs) > 1 else self.tax.catalogue
            self._add_child(parent_url, (crumbs[-1][0], crumbs[-1][1], url, 0, True))

    def build_categories(self):
        prefixes, counts, urls = self._prefixes, self._counts, self._cat_urls
        grantha_urls = set(self.tax._urls.values())
        rendered = set()
        for p in [""] + prefixes:
            url = self.tax.catalogue if p == "" else urls[p]
            if not url: continue
            if p and url in grantha_urls: continue      # the mūla page already lists its layers (see build_grantha)
            if url in rendered: continue               # a collapsed single-child level shares its parent's page
            rendered.add(url)
            rows = self.children.get(url, [])
            if not rows and p: continue
            # de-duplicate (collapsed levels can register the same child twice)
            seen = set(); uniq = []
            for r in rows:
                if r[2] in seen: continue
                seen.add(r[2]); uniq.append(r)
            uniq.sort(key=lambda r: (r[4], r[1].lower()))
            if p == "":
                name_sa, name_en = "ग्रन्थसूची", "All texts"; crumbs = []
            else:
                seg = p.rsplit("/", 1)[-1]; name_sa, name_en = T.label_sa(seg, p), T.label_en(seg)
                crumbs = self.tax.crumbs(self.slugs[[i for i, s in enumerate(self.slugs) if s.startswith(p + "/")][0]])
                crumbs = [c for c in crumbs if c[2] and len(c[2]) <= len(url)]
                if len(crumbs) > 1:   # the same label recurs across traditions (saṃhitā, upaniṣadaḥ, mahābhāratam): say where
                    name_en = f"{name_en} — {crumbs[-2][1]}"; name_sa = f"{name_sa} ({crumbs[-2][0]})"
            h1_sa, h1_en = (name_sa.split(" (")[0], name_en.split(" — ")[0])
            lis = "".join(f'<li>{"📁 " if not r[4] else "📖 "}<a href="{esc(r[2])}">{esc(r[0])}</a> <span class="en" lang="sa-Latn">{esc(r[1])}</span> <span class="cnt">· {r[3]} {"text" if r[4] else "texts"}{"s" if not r[4] and r[3] != 1 else ""}</span></li>' for r in uniq)
            total = counts.get(p, len(self.slugs))
            title = f"{name_en} · {name_sa} | {self.site_name}" if p else f"All texts — {self.site_name}"
            desc = (f"{name_en} ({name_sa}) in the {self.site_name}: {total} Sanskrit texts with transliteration, arranged by tradition, work and section." if p
                    else f"{self.site_name}: {len(self.slugs)} Sanskrit texts — Vedas, Itihāsa, Purāṇa, Kāvya, Stotra, Dāsa sāhitya, Vedāṅga and Śāstra — each with its sections as crawlable pages.")
            body = f'<div class="meta">{total} texts</div><ul class="kids">{lis}</ul>'
            ld = {"@type": "CollectionPage", "name": title, "url": self.abs_url(url), "inLanguage": "sa",
                  "isPartOf": {"@type": "WebSite", "name": self.site_name, "url": self.abs_url("/")},
                  "hasPart": [{"@type": "CreativeWork" if r[4] else "CollectionPage", "name": r[0], "alternateName": r[1], "url": self.abs_url(r[2])} for r in uniq[:300]]}
            self.write(url, self.shell(url=url, title=title, desc=desc, h1_sa=h1_sa, h1_en=h1_en, crumbs=crumbs, body=body, jsonld=ld))
            self._register(url, title)

    def build_sitemaps(self):
        per = CFG.get("sitemapUrlsPerFile", 20000)
        urls = sorted(set(self.urls))
        files = []
        for i in range(0, len(urls), per):
            name = f"sitemap-pages-{i // per + 1}.xml"
            body = "".join(f"  <url><loc>{esc(self.abs_url(u))}</loc><lastmod>{d}</lastmod></url>\n" for u, d in urls[i:i + per])
            (self.out / name).write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + body + "</urlset>\n", encoding="utf-8")
            files.append(name)
        # the reader's own static pages (landing, tools) keep their entries via the existing generator's list
        try:
            sys.path.insert(0, str(ROOT / "tools")); import build_sitemap as legacy  # noqa: E402
            statics = [p for p in legacy.STATIC_PAGES]
        except Exception:  # noqa: BLE001
            statics = ["index.html", "dge/index.html"]
        body = "".join(f"  <url><loc>{esc(self.origin + '/' + p)}</loc><lastmod>{NOW}</lastmod></url>\n" for p in statics)
        (self.out / "sitemap-static.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + body + "</urlset>\n", encoding="utf-8")
        files.append("sitemap-static.xml")
        idx = "".join(f"  <sitemap><loc>{esc(self.origin + '/' + f)}</loc><lastmod>{NOW}</lastmod></sitemap>\n" for f in files)
        (self.out / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + idx + "</sitemapindex>\n", encoding="utf-8")
        robots = (ROOT / "robots.txt").read_text(encoding="utf-8")
        robots = re.sub(r"^Sitemap:.*$", f"Sitemap: {self.origin}/sitemap.xml", robots, flags=re.M)
        (self.out / "robots.txt").write_text(robots, encoding="utf-8")
        return files, len(urls)

    def run(self, only=None):
        t0 = time.time()
        self.plan()
        todo = [s for s in self.slugs if not only or s.startswith(only)]
        for i, s in enumerate(todo):
            self.build_grantha(s)
            if not self.quiet and (i + 1) % 100 == 0:
                print(f"  {i + 1}/{len(todo)} granthas, {self.stats['pages']} pages, {self.stats['bytes'] / 1e6:.0f} MB, {time.time() - t0:.0f}s", flush=True)
        self.build_categories()
        files, n = self.build_sitemaps()
        dup_titles = sum(1 for v in self.titles.values() if v > 1)
        rep = {"builtAt": NOW, "granthas": len(todo), "pages": self.stats["pages"], "units": self.stats["units"], "bytes": self.stats["bytes"],
               "sitemapUrls": n, "sitemapFiles": files, "duplicateTitles": dup_titles, "seconds": round(time.time() - t0)}
        (self.out / "seo-build.json").write_text(json.dumps(rep, indent=1), encoding="utf-8")
        if not only:
            (ROOT / "dge/data/seo_urls.json").write_text(json.dumps({"builtAt": NOW, "publicRoot": CFG.get("publicRoot", "/dge"), "granthas": self.url_map},
                                                                     ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(json.dumps(rep, indent=1))
        return rep


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="_site"); ap.add_argument("--only", default=None)
    ap.add_argument("--no-translit", action="store_true"); ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    Site(a.out, quiet=a.quiet, translit=not a.no_translit).run(only=a.only)


if __name__ == "__main__":
    main()
