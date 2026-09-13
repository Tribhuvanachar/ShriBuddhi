#!/usr/bin/env python3
"""Cross-check rigveda_pratishakhya/data.json (Layer A, Sanskrit Library)
against VedaVishtaram (Layer B: vedavishtaram.in/lakshanam/rp.html --
Saunaka's text with Uvata's Bhasya and Vishnumitra's Vrtti) and attach
Layer B's sutra text + Bhasya to every item where the two sources could
be aligned.

Why this exists, and its real limits (read before trusting the output):

1. VedaVishtaram's own sutra numbering does NOT always match Layer A's.
   Layer A (Cardona/Scharf) sometimes folds a preceding illustrative
   Vedic-verse quotation into the SAME numbered "line" as the following
   terse sutra; VedaVishtaram keeps that quotation as unnumbered "text"
   above the sutra div and numbers only the terse core. This was
   confirmed directly by hand for many patala-10/11 sutras (e.g. Layer
   A's "10.3" is VedaVishtaram's five-line illustrative verse PLUS its
   sutra 3 "atItyaitAnyavasyanti"). Total per-patala counts can still
   coincidentally agree (patala 10 = 22 in both, patala 11 = 71 in both)
   even though individual sutra boundaries differ -- agreement in count
   is not proof of 1:1 correspondence, which is why this was checked by
   spot-comparing actual text content, not just index equality.

2. Patala 10 (Krama) and patala 11 (Kramahetu) were checked this way
   extensively (a majority of both patalas' entries individually
   spot-checked against VedaVishtaram's text) and the same-index
   correspondence holds reliably there -- Layer A's text at (patala,
   sutra) is consistently either identical to, or a superset (with a
   preceding annotation prefix) of, VedaVishtaram's text at the SAME
   index. UNCERTAIN_RESOLUTIONS below is a hand-verified table built
   from that checking, with a citation for every resolution: either a
   direct VV match, or an explicit corpus-internal pattern (e.g. "purva"
   confirmed directly 6+ times elsewhere in this same text) -- never a
   silent guess.

3. Outside patala 10-11, that same-index correspondence is NOT verified
   and, going by the patala-level count mismatches already logged in
   dge/RV_PRATISHAKHYA_KRAMA_ARCHITECTURE.md sec.4a.1 (patala 2: 82 vs 41
   sutras -- a large, unexplained gap), likely does NOT hold uniformly.
   This script still attaches same-index VV text/Bhasya there (it's
   useful raw data either way) but marks it index_verified=false, and
   only resolves an uncertain [?] reading elsewhere in the corpus when
   an automated same-index substring match succeeds unambiguously (the
   "algorithmic OK" cases) -- never by pattern-guessing outside patala
   10-11, since the corpus-wide patterns used for patala 10-11 haven't
   been checked for validity in other patalas' technical vocabulary.

Run: python3 tools/pratishakhya/crosscheck_vedavishtaram.py
Updates: dge/data/vedanga/shiksha/pratishakhya/rigveda_pratishakhya/data.json
"""
import html
import json
import re
import sys
from pathlib import Path

import requests
from indic_transliteration import sanscript

sys.path.insert(0, str(Path(__file__).resolve().parent))
import import_rv_pratishakhya  # noqa: E402  (path must be set up first)

VV_URL = "https://vedavishtaram.in/lakshanam/rp.html"
REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = (
    REPO_ROOT
    / "dge/data/vedanga/shiksha/pratishakhya/rigveda_pratishakhya/data.json"
)

SUTRA_DIV_RE = re.compile(
    r'<div class="sutra" id="spatal-(\d+)-(\d+)">'
    r'<div class="sutra-num">[^<]*</div>'
    r'<div class="sutra-text">(.*?)</div></div>'
    r'(?:\s*<div class="bhashya">(.*?)</div>)?',
    re.S,
)

# Hand-verified for patala 10 (Krama) and patala 11 (Kramahetu) only -- see
# the module docstring and dge/RV_PRATISHAKHYA_KRAMA_ARCHITECTURE.md sec.4c
# for the full per-item reasoning. Each value is (resolved_chars_in_order,
# method_note); "SKIP" means deliberately left unresolved (a genuine
# apparent edition variant, or no independent confirmation found).
P10_11_RESOLUTIONS = {
    "10.3":  (["SKIP", "U"], "First [?] ('[?]m luptantam...'): VedaVishtaram's parallel annotation line reads इ luptAntam (no anusvara) where Layer A implies Im/ईम् -- a genuine apparent edition variant, not an OCR gap; left unresolved. Second [?] ('p[?]rve'): VedaVishtaram's own annotation line 'itaH SiYcatAvartamaH pUrve dvEpadayoH dvayoH' matches exactly -- direct match, U."),
    "10.5":  (["U", "U", "U"], "Direct match: VedaVishtaram 10.5 = 'pUrvottarakftam rUpam pratyAdAnAvasAnayoH na brUyAt'."),
    "10.11": (["U"], "Direct match (sandhi-joined in VedaVishtaram): VedaVishtaram 10.11 = 'pratyAdAyaiva taM brUyAduttareRa punaH saha'."),
    "10.17": (["U", "U", "U"], "VedaVishtaram 10.17 = 'tadavagrahavad brUyAt' confirms the third [?] (brUyAt) directly. The first two ('itip[?]rvezu', 'p[?]rvEH') are in Layer A's preceding-annotation text not present in VedaVishtaram's own numbered div; resolved by the 'pUrva' pattern confirmed directly 6+ times elsewhere in this corpus (10.5, 11.5, 11.13, 11.15, 11.22, 11.34, 11.40, 11.41, 11.46)."),
    "10.20": (["U"], "Not in VedaVishtaram's own numbered div (VedaVishtaram 10.20 = only the second clause). Resolved by pattern: 'UzmavAt' from the UzmAn stem confirmed directly elsewhere (10.22, 11.41, 11.46)."),
    "10.22": (["U", "U"], "Direct match: VedaVishtaram 10.22 confirms both (UzmaRe the stem; dUBAvaH directly)."),
    "11.2":  (["U"], "Not in VedaVishtaram's numbered div (tail-only match). Resolved by pattern: 'bahUnAm' from 'bahu' confirmed elsewhere (11.57, 11.59)."),
    "11.4":  (["U"], "Not in VedaVishtaram's numbered div (tail-only). Resolved by the 'pUrva' pattern."),
    "11.5":  (["U"], "Direct match: VedaVishtaram 11.5 includes 'pUrvaM namati'."),
    "11.8":  (["SKIP"], "'uzarvas[?]yavo' does not match the recurring pUrva/UzmAn patterns and is not present in VedaVishtaram's own numbered div 8 (tail-only). No independent confirmation found; left unresolved pending Layer C or a Vedic concordance."),
    "11.11": (["U"], "Not in VedaVishtaram's numbered div (tail-only). Resolved by the 'pUrva' pattern (moderate confidence: not independently attested verbatim elsewhere in this corpus)."),
    "11.13": (["U"], "Direct match: VedaVishtaram 11.13 = 'anAnupUrvye padasaMdhyadarSanAt...'."),
    "11.15": (["U", "U"], "Direct match: VedaVishtaram 11.15 = 'padAnupUrvyeRa sapUrva A tatastato...' confirms both."),
    "11.22": (["U"], "Direct match: VedaVishtaram 11.22 = 'ayAvane pUrvaviDAnamAcaret'."),
    "11.25": (["U"], "Not in VedaVishtaram's numbered div (tail-only). Resolved by the UzmAn pattern."),
    "11.34": (["U"], "Direct match: VedaVishtaram 11.34 = 'punastaduktvADyavasAya pUrvavat'."),
    "11.40": (["U", "U", "U"], "Direct match: VedaVishtaram 11.40 = 'pravAdino dUrRASadUQyadUళaBAn' confirms all three."),
    "11.41": (["U"], "Direct match: VedaVishtaram 11.41 = 'pareSvaGoSeSu ca rePamUzmaRaH'."),
    "11.44": (["U"], "Not in VedaVishtaram's own numbered div 44 (tail-only). Resolved by verbatim internal cross-reference: the identical phrase 'pUrvaviDAnam Acaret' is directly confirmed in 11.22 within this same corpus."),
    "11.46": (["U", "U"], "Direct match: VedaVishtaram 11.46 = 'avikramaM dvyUzmasu cozmasaMDizu' confirms both (coṣma = ca+UzmA by sandhi)."),
    "11.53": (["U"], "Not in VedaVishtaram's numbered div (tail-only). Resolved by the 'pUrva' pattern."),
    "11.55": (["U"], "Not in VedaVishtaram's numbered div (tail-only). Resolved by the recurring 'udAttapUrva' compound (also in patala 3, unresolved separately)."),
    "11.57": (["U", "U"], "VedaVishtaram 11.57 confirms the second [?] (bahUn) directly; the first ('udAttap[?]rvaH', not in VedaVishtaram's numbered div) by the 'udAttapUrva' pattern."),
    "11.59": (["U"], "VedaVishtaram 11.59 itself reads a form that looks like an apparent typo for 'bahUni' (given the alternate spelling is not a Sanskrit stem while 'bahu/bahU' is standard, and 11.57 confirms 'bahUn' in this same corpus) -- resolved to U by cross-referencing both imperfect sources together."),
    "11.60": (["U"], "Not in VedaVishtaram's numbered div (tail-only). Resolved by the identical word 'rUpam' directly confirmed elsewhere (10.5)."),
    "11.66": (["U"], "Not in VedaVishtaram's numbered div (tail-only). Resolved by the 'pUrva' pattern."),
}

# Hand-verified for patala 2 (Samhita/sandhi definitions), sutras 1-42 only
# (11 Sep 2026) -- see dge/RV_PRATISHAKHYA_KRAMA_ARCHITECTURE.md sec.6.10 for
# the full cross-check. VedaVishtaram's OWN "patala 2" page content stops at
# sutra 42 (confirmed: (2,43) has no entry at all, and VedaVishtaram's
# "patala 3" is a DIFFERENT topic -- accent -- not a continuation of Layer
# A's patala-2 sutras 43-82, which remain entirely unchecked against this
# source). Within 1-42, the great majority of what LOOKS like a text
# divergence between Layer A and VedaVishtaram is NOT an error in either
# source: Layer A presents each sutra's words UN-SANDHI'd (pada-boundaries
# kept separate), VedaVishtaram presents the CONTINUOUSLY sandhi-joined
# recitation form of the identical sutra (e.g. Layer A "ataH anyAH" =
# VedaVishtaram "atonyAH", the same words with ordinary a-class-visarga
# sandhi applied) -- a real, useful thing to know before assuming any
# character-level difference is a content error. A few positions where
# VedaVishtaram's OWN page independently drops a trailing visarga (2.20,
# 2.29, 2.30) look like small VedaVishtaram-side scan/rendering slips, not
# something to import into Layer A.
P2_RESOLUTIONS = {
    "2.8":  (["U"], "Not in VedaVishtaram's own numbered div (tail-only match -- VedaVishtaram 2.8 covers only 'te 'nvakSarasandhayo 'nulomAH', the sutra's second clause). Resolved by the 'pUrva' pattern, now independently confirmed 4 times within this same patala via direct VedaVishtaram matches (2.24, 2.27, 2.28, 2.33)."),
    "2.27": (["U"], "Direct match (sandhi-joined in VedaVishtaram): VedaVishtaram 2.27 = 'hrasvapUrvastu so'kAram' (pUrvaH + tu sandhi-joined into pUrvastu) -- confirms pUrva."),
    "2.33": (["U", "U", "U"], "Third [?] ('ozWyap[?]rvAH'): direct match, VedaVishtaram 2.33 = '...paYcAlAnAm ozWyapUrvA Bavanti'. First two [?] ('p[?]rvar[?]pARi', in the sutra's opening clause -- not present in VedaVishtaram's own numbered div, tail-only source): resolved as 'pUrvarUpa' (retention-of-the-former-sound), a standard, independently well-attested Sanskrit phonetics technical term (a recognized sandhi-outcome category alongside guna/vrddhi/pararUpa) -- not sourced from VedaVishtaram for these two, unlike the third."),
    "2.36": (["'"], "NOT a missing letter, resolved as an avagraha: VedaVishtaram's own page renders this exact position as a literal ZERO WIDTH NON-JOINER (U+200C) character, not text -- the same site-side corruption-of-an-avagraha artifact independently confirmed at the corresponding position in VedaVishtaram's own 2.24 ('viSarjanIyaH'+'ariPitaH' -> 'viSarjanIyo'riPitaH', an ordinary a-class-visarga-before-a elision). Read the same way here ('...Avo'+'antopahitAt' -> 'Avo'ntopahitAt', the identical rule), which is also grammatically sensible on its own terms, not merely inferred from the artifact."),
    "2.40": (["SKIP"], "'ayo[?]pAzwiH' sits in a portion of this long citation-heavy sutra that VedaVishtaram's own numbered div does not cover at all (VedaVishtaram 2.40 is a much shorter tail excerpt starting later, at 'amum uktam...'). No independent confirmation found; left unresolved rather than guessed."),
}


def fetch_vv_html():
    resp = requests.get(VV_URL, timeout=60)
    resp.raise_for_status()
    # requests' charset auto-detection mis-guesses this server's encoding
    # (it doesn't declare charset in its Content-Type header) and garbles
    # every Devanagari byte -- decode the raw bytes as UTF-8 explicitly.
    return resp.content.decode("utf-8")


def parse_vv(doc):
    vv_deva, vv_bhashya = {}, {}
    for m in SUTRA_DIV_RE.finditer(doc):
        p, s = int(m.group(1)), int(m.group(2))
        sutra_text = html.unescape(re.sub(r"<[^>]+>", "", m.group(3))).strip()
        sutra_text = re.sub(r"।।\s*\d+\s*।।\s*$", "", sutra_text).strip()
        vv_deva[(p, s)] = sutra_text
        b = m.group(4)
        if b:
            b = html.unescape(re.sub(r"<[^>]+>", "", b)).strip()
            b = re.sub(r'^<span class="bhashya-label">[^<]*</span>\s*', "", b)
            vv_bhashya[(p, s)] = b
    return vv_deva, vv_bhashya


def deva_to_slp1(s):
    return sanscript.transliterate(s.replace("‌", "").replace("‍", ""),
                                    sanscript.DEVANAGARI, sanscript.SLP1)


def norm(s):
    return re.sub(r"\s+", "", s.replace(".", "").replace(",", "").replace("[?]", "?")).lower()


def algorithmic_resolve(la_slp1, vv_slp1_cased):
    """Same-index substring resolution used outside patala 10-11: only
    accepted when every [?] in the sutra resolves to exactly one
    unambiguous match. See module docstring sec.3 on why this is not
    trusted for pattern-based inference outside patala 10-11.

    SLP1 is case-sensitive (e.g. "u" is short u, "U" is long ū) -- match
    the anchors case-insensitively (VV's sandhi/spelling choices can
    differ in case at word boundaries) but always read the resolved
    character back out of the ORIGINAL-case vv_slp1_cased, never the
    lowercased matching copy, or a resolved long "U" would silently come
    back as a short "u"."""
    la = la_slp1.lower()
    vv_lower = vv_slp1_cased.lower()
    out = []
    for m in re.finditer(r"\[\?\]", la):
        start, end = m.start(), m.end()
        wstart = start
        while wstart > 0 and not la[wstart - 1].isspace():
            wstart -= 1
        wend = end
        while wend < len(la) and not la[wend].isspace():
            wend += 1
        pre, post = la[wstart:start], la[end:wend]
        if len(pre) < 2 and len(post) < 2:
            return None
        # An empty pre/post (the "[?]" sits at the very start/end of its
        # LA word) needs a word-boundary anchor, not a bare empty string:
        # a bare "" matches at every position, and regex returns the
        # LEFTMOST position the rest of the pattern can satisfy -- which
        # is usually one character too early, swallowing the preceding
        # space as part of the "resolved" group (caught happening for
        # real on 1.39: an unanchored empty `pre` matched " u" instead of
        # "u" by grabbing the space before it). \b would also accept a
        # mid-word position; \s/^ is the correct word-edge anchor here.
        pre_pat = r"(?:^|(?<=\s))" if pre == "" else re.escape(pre)
        post_pat = r"(?:$|(?=\s))" if post == "" else re.escape(post)
        # cap at 2 chars: every case actually seen in this corpus is one
        # missing letter (occasionally represented by 2 SLP1 characters,
        # e.g. a long vowel); a longer match means the anchors above
        # still weren't tight enough -- reject rather than trust it.
        pattern = pre_pat + "(.{1,2}?)" + post_pat
        matches = list(re.finditer(pattern, vv_lower))
        if len(matches) != 1:
            return None
        span = matches[0].span(1)
        out.append(vv_slp1_cased[span[0]:span[1]])
    return out


def apply_resolution(item, resolved_chars):
    """Rebuild text_devanagari/text_iast with [?] replaced, by reusing
    import_rv_pratishakhya.transliterate_sutra directly (not a re-
    implementation) so any fix made there -- e.g. the SLP1 "x" = Vedic
    retroflex la remap -- automatically applies here too."""
    slp1 = item["text_slp1"]
    parts = re.split(r"(\[\?\])", slp1)
    it = iter(resolved_chars)
    rebuilt = "".join(next(it) if p == "[?]" else p for p in parts)
    return import_rv_pratishakhya.transliterate_sutra(rebuilt)


def main():
    print(f"Fetching {VV_URL} ...", file=sys.stderr)
    vv_deva, vv_bhashya = parse_vv(fetch_vv_html())
    vv_slp1 = {k: deva_to_slp1(v) for k, v in vv_deva.items()}
    print(f"{len(vv_deva)} VedaVishtaram sutra entries parsed", file=sys.stderr)

    with open(DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)

    n_resolved_1011 = n_skipped_1011 = n_algo_resolved = n_attached = 0
    n_resolved_p2 = n_skipped_p2 = 0
    for item in data["items"]:
        key = (item["patala"], item["sutra"])
        vv_text = vv_deva.get(key)
        if vv_text is not None:
            item["vedavishtaram_sutra_text"] = vv_text
            item["vedavishtaram_bhashya"] = vv_bhashya.get(key, "")
            # patala 2 sutras 1-42: hand cross-checked 11 Sep 2026, sec.6.10 --
            # VedaVishtaram's own patala-2 page content stops at 42, so 43+
            # has no VV counterpart at all and stays unverified regardless.
            item["vedavishtaram_index_verified"] = (
                item["patala"] in (10, 11)
                or (item["patala"] == 2 and item["sutra"] <= 42)
            )
            n_attached += 1

        if not item["has_uncertain_reading"]:
            continue

        if item["id"] in P10_11_RESOLUTIONS:
            chars, note = P10_11_RESOLUTIONS[item["id"]]
            if "SKIP" in chars:
                item["crosscheck"] = (
                    "VedaVishtaram (vedavishtaram.in) checked, 11 Sep 2026 -- " + note
                )
                n_skipped_1011 += 1
                continue
            deva, iast = apply_resolution(item, chars)
            item["text_devanagari"] = deva
            item["text_iast"] = iast
            item["has_uncertain_reading"] = False
            item["crosscheck"] = (
                "VedaVishtaram (vedavishtaram.in), 11 Sep 2026 -- " + note
            )
            n_resolved_1011 += 1
        elif item["id"] in P2_RESOLUTIONS:
            chars, note = P2_RESOLUTIONS[item["id"]]
            if "SKIP" in chars:
                item["crosscheck"] = (
                    "VedaVishtaram (vedavishtaram.in) checked, 11 Sep 2026 -- " + note
                )
                n_skipped_p2 += 1
                continue
            deva, iast = apply_resolution(item, chars)
            item["text_devanagari"] = deva
            item["text_iast"] = iast
            item["has_uncertain_reading"] = False
            item["crosscheck"] = (
                "VedaVishtaram (vedavishtaram.in), 11 Sep 2026 -- " + note
            )
            n_resolved_p2 += 1
        elif item["patala"] not in (10, 11) and vv_text is not None:
            resolved = algorithmic_resolve(item["text_slp1"], vv_slp1[key])
            if resolved:
                deva, iast = apply_resolution(item, resolved)
                item["text_devanagari"] = deva
                item["text_iast"] = iast
                item["has_uncertain_reading"] = False
                item["crosscheck"] = (
                    "VedaVishtaram (vedavishtaram.in), 11 Sep 2026 -- unambiguous "
                    "same-index substring match; NOT individually hand-verified "
                    "for sutra-boundary drift (see module docstring sec.3)."
                )
                n_algo_resolved += 1

    still_uncertain = sum(1 for it in data["items"] if it["has_uncertain_reading"])
    print(f"patala 10-11: {n_resolved_1011} resolved by hand-verified table, "
          f"{n_skipped_1011} deliberately left unresolved", file=sys.stderr)
    print(f"patala 2 (sutras 1-42): {n_resolved_p2} resolved by hand-verified table, "
          f"{n_skipped_p2} deliberately left unresolved", file=sys.stderr)
    print(f"other patalas: {n_algo_resolved} resolved by unambiguous same-index match", file=sys.stderr)
    print(f"{n_attached} items got VedaVishtaram text/bhashya attached", file=sys.stderr)
    print(f"{still_uncertain} sutras remain has_uncertain_reading=true", file=sys.stderr)

    CROSSCHECK_NOTE_MARKER = " Cross-checked against VedaVishtaram"
    base_note = data["note"].split(CROSSCHECK_NOTE_MARKER)[0].rstrip()
    data["note"] = base_note + (
        " Cross-checked against VedaVishtaram (Layer B, vedavishtaram.in/lakshanam/rp.html "
        "-- Saunaka's text with Uvata's Bhasya and Vishnumitra's Vrtti) on 11 Sep 2026 via "
        "tools/pratishakhya/crosscheck_vedavishtaram.py; see that script's docstring for "
        "what was and wasn't verified. vedavishtaram_sutra_text/vedavishtaram_bhashya are "
        "attached wherever a same-index VedaVishtaram entry exists; "
        "vedavishtaram_index_verified is true for patalas 10-11 and for patala 2's sutras "
        "1-42 (VedaVishtaram's own patala-2 page content stops at 42; sutras 43-82 have no "
        "VedaVishtaram counterpart at all and stay unverified), where correspondence was "
        "checked by hand against actual content, not assumed from matching indices."
    )

    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"Wrote {DATA_PATH}", file=sys.stderr)


if __name__ == "__main__":
    main()
