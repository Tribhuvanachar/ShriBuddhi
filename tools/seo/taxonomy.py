"""Canonical public URLs and labels for every DGE taxonomy path (tools/seo, 7 Sep 2026).

The internal slug (the folder under data, e.g. vedas/rigveda/shakala_shakha/samhita/mandala_01) is a storage
location. The public URL describes the literary entity and never changes when files move:

    vedas/rigveda/shakala_shakha/samhita/mandala_01   →  /veda/rigveda/samhita/mandala-1/
    DvaitaVedanta/Itara/Kavya/raghavendra_vijaya/sarga_1         →  /kavya/raghavendra-vijaya/sarga-1/
    itihasa/mahabharata/adi_parva/mula                →  /itihasa/mahabharata/adi-parva/

Rules (admin/config/seo.json): the top-level folder is renamed by rootMap; segments in dropSegments (the default
`mula` layer) vanish; a taxonomy level with exactly one child everywhere in the catalogue collapses (Ṛgveda has only
the Śākala śākhā, so `shakala_shakha` adds nothing); mandala_01 → mandala-1; underscores → hyphens; lowercase.
The build refuses to run if two internal paths map to one public URL.

Labels come from the same tables the Library drawer uses (DGE_PATH_LABELS / DGE_NUMBERED_PREFIXES in js/library.js,
read from the file so there is one source of truth) plus admin/config/library-overrides.json's custom labels.
"""
import json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CFG = json.load(open(ROOT / "admin/config/seo.json", encoding="utf-8"))
_LIBJS = (ROOT / "js/library.js").read_text(encoding="utf-8")


def _js_object(name):
    i = _LIBJS.find("const " + name + " = {")
    if i < 0:
        return {}
    j = _LIBJS.find("\n};", i)
    body = _LIBJS[i:j]
    return {k: v for k, v in re.findall(r"([A-Za-z0-9_]+):\s*'([^']*)'", body)}


LABELS = _js_object("DGE_PATH_LABELS")
NUMBERED = _js_object("DGE_NUMBERED_PREFIXES")
_OVR = json.load(open(ROOT / "admin/config/library-overrides.json", encoding="utf-8"))
OVERRIDE_LABELS = _OVR.get("labels", {})
DEVA_DIGITS = "०१२३४५६७८९"
IAST_OK = True
try:
    from indic_transliteration import sanscript
except Exception:  # noqa: BLE001
    IAST_OK = False


def deva_num(n):
    return "".join(DEVA_DIGITS[int(c)] for c in str(n))


def iast(text):
    if not IAST_OK or not text:
        return ""
    try:
        return sanscript.transliterate(text, sanscript.DEVANAGARI, sanscript.IAST)
    except Exception:  # noqa: BLE001
        return ""


def auto_label(seg):
    m = re.match(r"^([a-z]+)_(\d+)$", seg, re.I)
    if m and m.group(1).lower() in NUMBERED:
        return NUMBERED[m.group(1).lower()] + " " + deva_num(int(m.group(2)))
    return " ".join(w[:1].upper() + w[1:] for w in seg.split("_"))


def label_sa(seg, full_path=None):
    """Devanagari label when the tables have one, else the humanised segment."""
    if full_path is not None and full_path in OVERRIDE_LABELS:
        return OVERRIDE_LABELS[full_path]
    return LABELS.get(seg) or auto_label(seg)


def label_en(seg):
    """Plain-Latin label: IAST of the Devanagari label when there is one, else the humanised segment."""
    m = re.match(r"^([a-z]+)_(\d+)$", seg, re.I)
    if m and m.group(1).lower() in NUMBERED:
        return (iast(NUMBERED[m.group(1).lower()]) or m.group(1).title()) + " " + str(int(m.group(2)))
    if seg in LABELS:
        return iast(LABELS[seg]) or auto_label(seg)
    return auto_label(seg)


def slugify_segment(seg):
    m = re.match(r"^([a-z]+)_0*(\d+)$", seg, re.I)
    if m:
        return m.group(1).lower() + "-" + m.group(2)
    s = re.sub(r"[^a-z0-9]+", "-", seg.lower()).strip("-")
    return s or "x"


class Taxonomy:
    """Built once from the list of internal slugs that will be published; answers url(slug) and crumbs(slug)."""

    def __init__(self, slugs):
        self.slugs = sorted(set(slugs))
        self.children = {}
        for s in self.slugs:
            parts = s.split("/")
            for i in range(len(parts)):
                parent = "/".join(parts[:i])
                self.children.setdefault(parent, set()).add(parts[i])
        self.drop = set(CFG.get("dropSegments", []))
        self.root_map = CFG.get("rootMap", {})
        self.public_root = CFG.get("publicRoot", "/dge").rstrip("/")
        # URLs the reader app already owns (its own index.html files anywhere in the site): a generated index never
        # replaces one of them; it moves to <url>texts/ instead (the root catalogue / -> /texts/).
        self.reserved = reserved_urls(self.public_root)
        self.catalogue = CFG.get("catalogueUrl") or self._free(self.public_root + "/")
        self._urls = {}
        for s in self.slugs:
            self._urls[s] = self._compute(s)
        seen = {}
        for s, u in self._urls.items():
            if u in seen:
                raise SystemExit(f"public URL collision: {u} ← {seen[u]} and {s}; add an alias in admin/config/seo.json")
            seen[u] = s

    def _kept_segments(self, slug):
        """(internal segment, prefix) pairs that survive collapsing, in order."""
        parts = slug.split("/")
        out = []
        for i, seg in enumerate(parts):
            prefix = "/".join(parts[: i + 1])
            parent = "/".join(parts[:i])
            if seg in self.drop and i == len(parts) - 1:
                continue
            # a level with a single child everywhere adds nothing to the address (rigveda → shakala_shakha)
            if i > 0 and len(self.children.get(parent, ())) == 1 and i < len(parts) - 1:
                continue
            out.append((seg, prefix))
        return out

    def _compute(self, slug):
        kept = self._kept_segments(slug)
        segs = []
        for j, (seg, prefix) in enumerate(kept):
            if j == 0 and seg in self.root_map:
                segs.append(self.root_map[seg])
            else:
                segs.append(slugify_segment(seg))
        return self._free(self.public_root + "/" + "/".join(segs) + "/")

    def _free(self, url):
        return url + "texts/" if url in self.reserved else url

    def url(self, slug):
        return self._urls[slug]

    def crumbs(self, slug):
        """[(label_sa, label_en, url or None)] from the site root down to this grantha; ancestors that are pure
        categories get their own index page URL (build_seo_site.py renders one for every kept prefix)."""
        out = []
        for seg, prefix in self._kept_segments(slug):
            out.append((label_sa(seg, prefix), label_en(seg), self.prefix_url(prefix)))
        return out

    def prefix_url(self, prefix):
        """URL of the index page for an internal prefix (a category or a grantha)."""
        if prefix in self._urls:
            return self._urls[prefix]
        # a category: same rule as a grantha, computed against the first slug under it
        for s in self.slugs:
            if s.startswith(prefix + "/"):
                kept = [(seg, p) for seg, p in self._kept_segments(s) if len(p) <= len(prefix)]
                segs = [self.root_map.get(seg, slugify_segment(seg)) if j == 0 else slugify_segment(seg) for j, (seg, p) in enumerate(kept)]
                return self._free(self.public_root + "/" + "/".join(segs) + "/")
        return None

    def category_prefixes(self):
        """Every internal prefix that is a category (has children, is not itself a grantha)."""
        return sorted(p for p in self.children if p and p not in self._urls)


def reserved_urls(public_root, repo=None):
    """Public URLs of the reader's own hand-written index.html files anywhere in the site (never data)."""
    root = (repo or ROOT)
    out = set()
    for p in root.rglob("index.html"):
        rel = p.relative_to(root).parent.as_posix()
        if rel.split("/")[0] in ("data", "node_modules") or "/node_modules/" in rel:
            continue
        out.add(public_root + "/" + (rel + "/" if rel != "." else ""))
    return out


def public_slugs(library):
    """Internal slugs the SEO build publishes: populated, not hidden, not under an excluded prefix."""
    hidden = set(_OVR.get("hidden", []))
    ex = CFG.get("excludePrefixes", []); inc = CFG.get("includePrefixes", [])
    out = []
    for g in library:
        if not g.get("populated") or g.get("hidden"):
            continue
        slug = g["path"].replace("data/", "").replace("/data.json", "")
        parts = slug.split("/")
        if any("/".join(parts[:i]) in hidden for i in range(1, len(parts) + 1)):
            continue
        if any(slug == p or slug.startswith(p + "/") for p in ex) and not any(slug == p or slug.startswith(p + "/") for p in inc):
            continue
        out.append(slug)
    return out


if __name__ == "__main__":
    lib = json.load(open(ROOT / "data/library.json", encoding="utf-8"))["granthas"]
    slugs = public_slugs(lib)
    t = Taxonomy(slugs)
    print(len(slugs), "public granthas;", len(t.category_prefixes()), "category pages")
    for s in ["vedas/rigveda/shakala_shakha/samhita/mandala_01", "DvaitaVedanta/Itara/Kavya/raghavendra_vijaya/sarga_1", "itihasa/mahabharata/adi_parva/mula",
              "vedas/yajurveda/krishna_yajurveda/taittiriya_shakha/samhita/kanda_01", "purana/maha_purana/bhagavata_purana/skandha_10",
              "vedas/samaveda/kauthuma_shakha/samhita/purvarchika", "DvaitaVedanta/Itara/Stotra/prahlada_kruta_narasimha", "DvaitaVedanta/Itara/DasaSahitya/composers/raghavendra"]:
        if s in t._urls:
            print(f"{s}\n   → {t.url(s)}\n   crumbs: {[(a, b, c) for a, b, c in t.crumbs(s)]}")
