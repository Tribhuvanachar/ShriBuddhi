#!/usr/bin/env python3
"""Structural markup for Sanskrit commentary OCR: <TP> pratikas and rule paragraphs.

DETERMINISTIC AND OFFLINE. No model, no network, no API. The same input always
produces the same output, because this runs on every incoming OCR document and
a formatter that answers differently on Tuesday is not a formatter.

It adds markup. It does not edit Sanskrit: no emendation, no sandhi, no
spelling, no silent insertion or deletion. If the OCR says निरूपयतिति that is
what comes out. A validation pass checks exactly that before returning.

TWO THINGS THE SPECIFICATION DID NOT MATCH IN THE REAL CORPUS, both supported:

1. The spec is written in ASCII | and ||. The supplied sample contains none --
   thirteen U+0964 DANDA and not one pipe. A double danda there is TWO U+0964,
   not U+0965. All forms are accepted and none is ever rewritten into another.

2. The spec requires an opening delimiter: INTRODUCER | PRATIKA |. The sample
   has no opening delimiter anywhere. Its real shape is

       ... इति कोषोक्तेराह– ननु गन्धरसेति ।।

   introducer, EN DASH, pratika, closing danda. Implementing the spec literally
   would have found nothing at all in the text it was written for. So the dash
   form is rule P1B, beside the spec's P1A, and it is the one that fires.

Confidence, per the spec's own note: P1 is an explicit quotation structure and
P2 an inferred one, so P1 wins every conflict and P2 stays deliberately narrow
-- one or two words and an approved ending, never a greedy scan.

  python3 tools/format_commentary.py IN [OUT]     format
  python3 tools/format_commentary.py IN --debug   what fired, and what was rejected
  python3 tools/format_commentary.py IN --diff    unified diff against the source
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import sys

RULES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "commentary_rules.json")
DEVA = r"\u0900-\u097F"
# U+0964 DANDA and U+0965 DOUBLE DANDA live INSIDE the Devanagari block, so
# the obvious character class swallows them and a pratika quietly eats its own
# closing delimiter. Excluded explicitly: this is precisely why the first case
# in the supplied sample was not detected at all, and why the second matched
# only by luck, with the danda inside the pratika.
DEVA_WORD = r"\u0900-\u0963\u0966-\u097F"
# A word for our purposes: Devanagari plus the marks OCR leaves inside words.
WORD = rf"[{DEVA_WORD}\u200c\u200d'’‘]+"


def load_rules(path: str = RULES_PATH) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _alt(strings) -> str:
    """Longest-first alternation, so केचित्तु beats केचित्."""
    return "|".join(re.escape(s) for s in sorted(set(strings), key=len, reverse=True))


# An introducer opening with an independent vowel is written with the matching
# dependent sign once sandhi has joined it to the preceding word: कोषोक्तेः +
# आह is कोषोक्तेराह, in which the letters आ and ह never occur together. Matching
# the word list literally therefore misses exactly the case the corpus is full
# of -- it is why the first pratika in the supplied sample went undetected.
# The variant is generated deterministically, not guessed.
_MATRA = {"आ": "ा", "इ": "ि", "ई": "ी", "उ": "ु", "ऊ": "ू",
          "ऋ": "ृ", "ए": "े", "ऐ": "ै", "ओ": "ो", "औ": "ौ"}


#: Word-final म् and the anusvara are the same sound written two ways, and this
#: edition writes उक्तं where the rule table says उक्तम्. Nothing in the table
#: matched भावेनोक्तं, इत्यत उक्तं or इत्याशयेनोक्तं for that reason alone.
def _anusvara_variants(w):
    out = []
    if "म्" in w:
        out.append(w.replace("म्", "ं"))
    if "ं" in w:
        out.append(w.replace("ं", "म्"))
    return out


def with_sandhi_variants(words):
    """Every way the same introducer or particle is actually written.

    Two transformations, both deterministic and both forced on us by the
    corpus rather than guessed: an independent vowel becomes its matra once
    sandhi joins the word to what precedes (आह -> ...ाह), and word-final म्
    is written as an anusvara (उक्तम् -> उक्तं).
    """
    out = list(words)
    for w in words:
        if w and w[0] in _MATRA:
            out.append(_MATRA[w[0]] + w[1:])
    for w in list(out):
        out.extend(_anusvara_variants(w))
    return out


class Formatter:
    def __init__(self, rules: dict | None = None):
        r = rules or load_rules()
        self.rules = r
        self.limits = r["limits"]

        singles, doubles = r["delimiters"]["single"], r["delimiters"]["double"]
        # Doubles first: '।।' must win over '।' at the same position.
        self.DELIM = rf"(?:{_alt(doubles)}|{_alt(singles)})"
        self.dash = r["separators"]["dashes"]

        self.intro_exact = r["introducers_exact"]
        self.intro_family = r["introducers_family"]
        self.suffixes = r["pratika_suffixes"]
        self.closers = r["paragraph_closers"]
        self.starters = r["paragraph_starters"]

        # An introducer matches at the END of a word -- sandhi joins it to what
        # precedes, and the corpus's own कोषोक्तेराह is exactly that.
        intro_alt = _alt(with_sandhi_variants(
            list(self.intro_exact.values()) + list(self.intro_family.values())))
        self.INTRO = rf"(?:{intro_alt})"
        dash_alt = _alt(self.dash)
        maxw = self.limits["p1_max_pratika_words"]

        # P1A -- the specification's form: introducer, opening delimiter,
        # pratika, closing delimiter. The closing delimiter goes INSIDE the TP.
        self.RE_P1A = re.compile(
            rf"(?P<intro>{self.INTRO})"
            rf"(?P<sep>[\s]*(?:{dash_alt})?[\s]*)"
            rf"(?P<open>{self.DELIM})"
            rf"(?P<gap>\s*)"
            rf"(?P<prat>{WORD}(?:\s+{WORD}){{0,{maxw - 1}}})"
            rf"(?P<pad>\s*)"
            rf"(?P<close>{self.DELIM})")

        # P1B -- what the corpus actually contains. The dash is REQUIRED here;
        # without an opening delimiter it is the only thing keeping the match
        # from wandering into ordinary prose.
        self.RE_P1B = re.compile(
            rf"(?P<intro>{self.INTRO})"
            rf"(?P<sep>[\s]*(?:{dash_alt})[\s]*)"
            rf"(?P<prat>{WORD}(?:\s+{WORD}){{0,{maxw - 1}}})"
            rf"(?P<pad>\s*)"
            rf"(?P<close>{self.DELIM})")

        # P1C -- introducer, a plain space, pratika, danda. No opening delimiter
        # and no dash, which is why neither rule above sees it:
        #     इत्यत आह उद्देशेनैवेति ।
        # It is the loosest of the three, so it leans entirely on the citation
        # gate -- without that requirement this shape would capture prose, and
        # with it the pratika has to end the way a pratika ends.
        self.RE_P1C = re.compile(
            rf"(?P<intro>{self.INTRO})"
            rf"(?P<sep>[ \t]+)"
            rf"(?P<prat>{WORD}(?:\s+{WORD}){{0,{maxw - 1}}})"
            rf"(?P<pad>\s*)"
            rf"(?P<close>{self.DELIM})")

        # P2 -- inferred. One or two words between delimiters, the last ending
        # in an approved family. Never a scan of the paragraph.
        #
        # Restricted to the pipe forms by default. Section 11 of the spec makes
        # this "delimiter + one or two words + delimiter", and section 29
        # forbids reading भिन्नेति ।। as a pratika -- but in danda-punctuated
        # prose those are the same shape, so honouring both means declining to
        # fire on a danda. Every Pattern-2 example in the spec uses pipes.
        n = self.limits["p2_max_words"]
        if self.limits.get("p2_delimiters", "pipes_only") == "pipes_only":
            p2_delim = r"(?:\|\||\|)"
        else:
            p2_delim = self.DELIM
        self.P2_DELIM = p2_delim
        self.RE_P2 = re.compile(
            rf"(?P<open>{p2_delim})"
            rf"(?P<gap>\s*)"
            rf"(?P<prat>{WORD}(?:\s+{WORD}){{0,{n - 1}}})"
            rf"(?P<pad>\s*)"
            rf"(?P<close>{p2_delim})")
        # The citation particle is fused to the quoted word by sandhi, so इति is
        # written -मिति, -पीति, -वदिति: the independent vowel becomes its matra
        # and a literal endswith("इति") fails on exactly the real cases.
        # यच्चायमिति, गन्धर्वादीनामिति and इत्युपलक्षणमिति were all missed this
        # way -- the same defect as कोषोक्तेराह against आह.
        self.SUFFIX_FORMS = with_sandhi_variants(list(self.suffixes.values()))
        self.BARE = {w.strip() for w in
                     (r.get("bare_particles", {}).get("forms") or [])}
        self.SUFFIX_RE = re.compile(rf"(?:{_alt(self.SUFFIX_FORMS)})$")

        self.RE_EXISTING_TP = re.compile(r"<TP>.*?</TP>", re.S)
        self.RE_EXISTING_P = re.compile(r'<p class="rule">.*?</p>', re.S)

    # ---------- helpers -------------------------------------------------

    def _rule_id_for_intro(self, text: str) -> str:
        for table in (self.intro_exact, self.intro_family):
            for rid, w in sorted(table.items(), key=lambda kv: -len(kv[1])):
                for form in with_sandhi_variants([w]):
                    if text.endswith(form):
                        return rid
        return "P1_?"

    def ends_as_citation(self, pratika: str) -> bool:
        """Does this end the way a pratika ends?

        A pratika is a quoted lemma plus its citation particle -- लक्ष्मीपतेः +
        इति, गुरोः अपि + इति. Requiring the particle is the definition of the
        thing, not a heuristic about it, and it is the single check that stops
        an introducer swallowing whatever prose happens to precede the next
        danda: the 77-character capture in SM6:2 ends in वा, which no citation
        ever does.
        """
        words = pratika.split()
        if not words:
            return False
        # The particle alone is not a citation of anything: इति and इत्यर्थः are
        # ordinary commentary joinery, and P1C read both as pratikas until this
        # check existed.
        if " ".join(words) in self.BARE:
            return False
        return bool(self.SUFFIX_RE.search(words[-1]))

    def _suffix_id(self, word: str) -> str | None:
        best, bid = "", None
        for rid, suf in self.suffixes.items():
            if word.endswith(suf) and len(suf) > len(best):
                best, bid = suf, rid
        return bid

    # ---------- stages --------------------------------------------------

    def normalize(self, text: str) -> str:
        """Safe only: line endings, trailing space, runs of spaces. Danda
        characters are never touched, and a blank line is never invented."""
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r" *\n *", "\n", text)
        return text.strip()

    def find_tps(self, text: str, debug: list | None = None) -> list[tuple[int, int, str, str]]:
        """-> spans (start, end, rule_id, inner) that must become <TP>inner</TP>.

        Ordered by precedence: existing tags, then P1A, then P1B, then P2. A
        position claimed by an earlier rule is closed to every later one, which
        is what makes nested TPs structurally impossible rather than merely
        checked for afterwards.
        """
        taken: list[tuple[int, int]] = []

        def free(a: int, b: int) -> bool:
            return all(b <= s or a >= e for s, e in taken)

        for m in self.RE_EXISTING_TP.finditer(text):
            taken.append((m.start(), m.end()))

        out = []
        for rid_base, rx in (("P1A", self.RE_P1A), ("P1B", self.RE_P1B),
                             ("P1C", self.RE_P1C)):
            for m in rx.finditer(text):
                a, b = m.start("prat"), m.end("close")
                if not free(m.start(), m.end()):
                    if debug is not None:
                        debug.append(f"  skip  {rid_base} at {m.start()}: overlaps a claimed span")
                    continue
                cap_ok = True
                if rid_base == "P1C":
                    # P1C has no delimiter or dash to bound it, so it is capped
                    # by length too. Longer ones are reported as candidates
                    # rather than accepted: some genuine quotations are long,
                    # and a 57-character sentence ending in इति is exactly the
                    # case that needs a person to look at it.
                    cap_ok = len(m.group("prat")) <= self.limits.get("p1c_max_chars", 40)
                    if not cap_ok and debug is not None:
                        debug.append(
                            f"  candidate P1C at {m.start()}: {len(m.group('prat'))} chars, "
                            f"over the cap -- NOT LINKED: {m.group('prat')[:50]!r}")
                if not cap_ok:
                    continue
                if self.limits.get("p1_require_citation_ending", True) \
                        and not self.ends_as_citation(m.group("prat")):
                    if debug is not None:
                        debug.append(
                            f"  reject {rid_base} at {m.start()}: {m.group('prat')[:40]!r} "
                            f"does not end in a citation particle")
                    continue
                rid = self._rule_id_for_intro(m.group("intro"))
                taken.append((m.start(), m.end()))
                out.append((a, b, f"{rid_base}/{rid}", text[a:b]))
                if debug is not None:
                    debug.append(
                        f"TP DETECTED rule={rid_base}/{rid} introducer={m.group('intro')!r} "
                        f"open={(m.groupdict().get('open') or '(none)')!r} "
                        f"text={m.group('prat')!r} close={m.group('close')!r} "
                        f"confidence=high position={a}")

        for m in self.RE_P2.finditer(text):
            words = m.group("prat").split()
            # The OPENING delimiter may already belong to an earlier match, as
            # its closing one. In "... भाविन इति ।। पूर्वस्येति ।" the same ।।
            # closes the first pratika and opens the second, and requiring the
            # whole match to be untouched lost every pratika that followed
            # another. Only the pratika and its own closing danda have to be
            # free -- which is also the only span this rule goes on to claim,
            # so nothing can nest.
            if not free(m.start("prat"), m.end()):
                continue
            # Through ends_as_citation, not _suffix_id alone: that is where the
            # bare-particle guard lives, and P2 was going round it. With P2
            # restricted to pipes the gap never showed, because the corpus has
            # no pipes; the moment dandas were allowed it tagged a naked इति ।
            if not self.ends_as_citation(m.group("prat")):
                if debug is not None:
                    debug.append(f"  reject P2 at {m.start()}: {m.group('prat')!r} "
                                 f"is not a lemma plus a citation particle")
                continue
            sid = self._suffix_id(words[-1]) or "P2_?"
            a, b = m.start("prat"), m.end("close")
            taken.append((a, b))
            out.append((a, b, f"P2/{sid}", text[a:b]))
            if debug is not None:
                debug.append(
                    f"TP DETECTED rule=P2/{sid} open={m.group('open')!r} text={m.group('prat')!r} "
                    f"close={m.group('close')!r} confidence=inferred position={a}")

        out.sort(key=lambda t: t[0])
        return out

    def apply_tps(self, text: str, spans) -> str:
        out, last = [], 0
        for a, b, _rid, inner in spans:
            out.append(text[last:a]); out.append("<TP>" + inner + "</TP>"); last = b
        out.append(text[last:])
        return "".join(out)

    def paragraphs(self, text: str, debug: list | None = None) -> str:
        """Split on semantic boundaries and wrap each piece in <p class="rule">.

        A TP may contain dandas, so paragraph detection runs over text in which
        TPs are already opaque -- it never looks inside one.
        """
        if self.RE_EXISTING_P.search(text):
            return text                       # already paragraphed: idempotent

        shields: list[str] = []

        def shield(m):
            shields.append(m.group(0))
            return "\x00%d\x00" % (len(shields) - 1)

        guarded = self.RE_EXISTING_TP.sub(shield, text)

        closer_re = re.compile(rf"(?:{_alt(self.closers.values())})\s*(?:{self.DELIM})")
        starter_re = re.compile(rf"(?<![{DEVA_WORD}])(?:{_alt(self.starters.values())})(?![{DEVA_WORD}])")

        cuts = {0, len(guarded)}
        for m in closer_re.finditer(guarded):
            cuts.add(m.end())
            if debug is not None:
                debug.append(f"PARAGRAPH BREAK rule=closer marker={m.group(0).strip()!r} position={m.end()}")
        for m in starter_re.finditer(guarded):
            # The marker belongs to the NEW paragraph, so the cut is before it.
            cuts.add(m.start())
            if debug is not None:
                debug.append(f"PARAGRAPH BREAK rule=starter marker={m.group(0)!r} position={m.start()}")
        for m in re.finditer(r"\n+", guarded):
            cuts.add(m.start()); cuts.add(m.end())

        ordered = sorted(cuts)
        parts = [guarded[a:b].strip() for a, b in zip(ordered, ordered[1:])]
        parts = [p for p in parts if p]
        if not parts:
            return text

        body = "\n".join('<p class="rule">\n%s\n</p>' % p for p in parts)
        return re.sub(r"\x00(\d+)\x00", lambda m: shields[int(m.group(1))], body)

    # ---------- validation ----------------------------------------------

    @staticmethod
    def validate(src: str, out: str) -> list[str]:
        problems = []
        if out.count("<TP>") != out.count("</TP>"):
            problems.append("unbalanced <TP>")
        if out.count('<p class="rule">') != out.count("</p>"):
            problems.append("unbalanced <p class=\"rule\">")
        depth = 0
        for tok in re.findall(r"</?TP>", out):
            depth += 1 if tok == "<TP>" else -1
            if depth > 1:
                problems.append("nested <TP>"); break
            if depth < 0:
                problems.append("stray </TP>"); break
        depth = 0
        for tok in re.findall(r'<p class="rule">|</p>', out):
            depth += 1 if tok.startswith("<p") else -1
            if depth > 1:
                problems.append("nested rule paragraph"); break
        # Source preservation: every Devanagari character, in order, survives.
        strip = lambda s: "".join(re.findall(rf"[{DEVA}]", s))
        if strip(src) != strip(out):
            problems.append("Sanskrit text changed -- this stage must only add markup")
        return problems

    # ---------- entry point ---------------------------------------------

    def format(self, text: str, debug: list | None = None) -> str:
        src = text
        norm = self.normalize(text)
        tagged = self.apply_tps(norm, self.find_tps(norm, debug))
        out = self.paragraphs(tagged, debug)
        problems = self.validate(src, out)
        if problems:
            # False negatives beat destructive false positives: hand back the
            # normalized source rather than markup we cannot vouch for.
            if debug is not None:
                debug.append("VALIDATION FAILED: " + "; ".join(problems))
            return norm
        return out


_DEFAULT = None


def format_commentary(text: str) -> str:
    """The reusable entry point for the ingestion pipeline."""
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = Formatter()
    return _DEFAULT.format(text)


# ---------------------------------------------------------------- corpus mode

TEXT_FIELDS = ("sanskrit_text", "text", "sa")


def corpus_files(path: str) -> list[str]:
    if os.path.isfile(path):
        return [path]
    return sorted(os.path.join(d, f)
                  for d, _s, fs in os.walk(path) for f in fs if f == "data.json")


def run_corpus(path: str, fmt: "Formatter", in_place: bool = False):
    """Apply the formatter to every unit's body text under a path.

    Selective by design: a single data.json, one grantha's folder, or a whole
    shelf. Reports rather than writes unless asked, because the point of a
    first run is for a scholar to look at it.
    """
    results = []
    for f in corpus_files(path):
        try:
            doc = json.load(open(f, encoding="utf-8"))
        except (OSError, ValueError) as e:
            results.append({"file": f, "error": str(e)}); continue
        items = doc.get("items") if isinstance(doc, dict) else None
        if not isinstance(items, list):
            continue
        field = next((x for x in TEXT_FIELDS
                      if any(isinstance(i.get(x), str) for i in items if isinstance(i, dict))), None)
        if not field:
            continue
        units, changed = [], 0
        for i in items:
            if not isinstance(i, dict) or not isinstance(i.get(field), str):
                continue
            before = i[field]
            dbg: list = []
            after = fmt.format(before, dbg)
            if after != before:
                changed += 1
                units.append({"id": i.get("id", ""), "before": before, "after": after,
                              "events": dbg})
                if in_place:
                    i[field] = after
        if in_place and changed:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import format_data_json
            text = format_data_json.canonical(doc) or json.dumps(
                doc, ensure_ascii=False, separators=(",", ":"))
            with open(f, "w", encoding="utf-8", newline="") as fh:
                fh.write(text)
        results.append({"file": f, "field": field, "units": len(items),
                        "changed": changed, "detail": units})
    return results


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input")
    ap.add_argument("output", nargs="?")
    ap.add_argument("--debug", action="store_true")
    ap.add_argument("--diff", action="store_true")
    ap.add_argument("--corpus", action="store_true",
                    help="treat input as a data.json or a folder of them")
    ap.add_argument("--in-place", action="store_true",
                    help="with --corpus, write the formatting back into the corpus")
    ap.add_argument("--json", action="store_true", help="with --corpus, emit the report as JSON")
    a = ap.parse_args(argv)

    if a.corpus:
        res = run_corpus(a.input, Formatter(), a.in_place)
        if a.json:
            json.dump(res, sys.stdout, ensure_ascii=False, indent=1)
            return 0
        tot_u = sum(r.get("units", 0) for r in res)
        tot_c = sum(r.get("changed", 0) for r in res)
        for r in res:
            if "error" in r:
                print(f"  ERROR {r['file']}: {r['error']}", file=sys.stderr); continue
            print(f"  {r['changed']:>4}/{r['units']:<5} {r['file']}")
        print(f"\n{len(res)} file(s), {tot_u} units, {tot_c} changed"
              + ("" if a.in_place else "  (nothing written -- pass --in-place)"))
        return 0

    src = open(a.input, encoding="utf-8").read()
    f = Formatter()
    dbg: list[str] = [] if a.debug else None
    out = f.format(src, dbg)

    if a.debug:
        for line in dbg:
            print(line, file=sys.stderr)
        print(f"-- {len(dbg)} event(s)", file=sys.stderr)
    if a.diff:
        sys.stdout.writelines(difflib.unified_diff(
            src.splitlines(True), out.splitlines(True),
            fromfile=a.input, tofile=a.input + " (formatted)"))
        return 0
    if a.output:
        with open(a.output, "w", encoding="utf-8") as fh:
            fh.write(out)
        print(f"wrote {a.output}")
    else:
        sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
