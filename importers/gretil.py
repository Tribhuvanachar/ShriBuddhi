"""Generic GRETIL importer (IAST -> Devanagari). Handles both the older
'// ABBR_canto.verse //' marker style (Manu/Raghuvamsha/Shishupalavadha/
other smritis) and the plainer 'Word canto.verse text /' prose-citation
style some pages use (Vishnu Smriti). Star-passage markers ('*ABBR_N') and
'[h: ... :h]' headers are skipped. Run:  python importers/dispatch.py <id>
"""
import re, collections
from common import http_get, to_text, iast_to_dev, write_grantha

# id -> spec. unit = folder/label for each canto ('adhyaya'|'sarga').
# All target a "/mula" leaf -- matches the layer-folder convention already
# used for Ramayana/Mahabharata in the catalog (leaves room for a
# commentary layer alongside it later). Smritis stay flat, matching their
# own already-scaffolded catalog entries.
GRETIL = {
  "harivamsha":        dict(name="Harivamsha", author="Maharshi Veda Vyasa", unit="adhyaya",
      schema="itihasa_purana_text", target="itihasa/harivamsha/mula",
      # The corpustei *HTML* export (used until now) never matched anything --
      # see _hv_parse() below for why. This is the plaintext transformation of
      # the same constituted text, which actually uses the "// HV_a.v" /
      # "*HV_a.v*n" marker convention _hv_parse() is built for.
      urls=["https://gretil.sub.uni-goettingen.de/gretil/corpustei/transformations/plaintext/sa_harivaMza.txt"]),
  "manu_smriti":       dict(name="Manu Smriti", author="Manu", unit="adhyaya",
      schema="smriti_dharmashastra_text", target="smriti_dharma/smriti/manu_smriti",
      urls=["https://gretil.sub.uni-goettingen.de/gretil/1_sanskr/6_sastra/4_dharma/smrti/manu2p_u.htm"]),
  "yajnavalkya_smriti":dict(name="Yajnavalkya Smriti", author="Yajnavalkya", unit="adhyaya",
      schema="smriti_dharmashastra_text", target="smriti_dharma/smriti/yajnavalkya_smriti",
      urls=["https://gretil.sub.uni-goettingen.de/gretil/1_sanskr/6_sastra/4_dharma/smrti/yajn2_pu.htm"]),
  "parashara_smriti":  dict(name="Parashara Smriti", author="Parashara", unit="adhyaya",
      schema="smriti_dharmashastra_text", target="smriti_dharma/smriti/parashara_smriti",
      urls=["https://gretil.sub.uni-goettingen.de/gretil/1_sanskr/6_sastra/4_dharma/smrti/pars2_pu.htm"]),
  "narada_smriti":     dict(name="Narada Smriti", author="Narada", unit="adhyaya",
      schema="smriti_dharmashastra_text", target="smriti_dharma/smriti/narada_smriti",
      urls=["https://gretil.sub.uni-goettingen.de/gretil/1_sanskr/6_sastra/4_dharma/smrti/nars2_pu.htm"]),
  "vishnu_smriti":     dict(name="Vishnu Smriti", author="Vishnu", unit="adhyaya",
      schema="smriti_dharmashastra_text", target="smriti_dharma/smriti/vishnu_smriti",
      urls=["https://gretil.sub.uni-goettingen.de/gretil/1_sanskr/6_sastra/4_dharma/smrti/visnus_u.htm"]),
  "raghuvamsha":       dict(name="Raghuvamsha", author="Kalidasa", unit="sarga",
      schema="itihasa_purana_text", target="kavya_alankara/raghuvamsha/mula",
      urls=["https://gretil.sub.uni-goettingen.de/gretil/1_sanskr/5_poetry/2_kavya/kragh_pu.htm"]),
  "shishupalavadha":   dict(name="Shishupalavadha", author="Magha", unit="sarga",
      schema="itihasa_purana_text", target="kavya_alankara/shishupalavadha/mula",
      urls=["https://gretil.sub.uni-goettingen.de/gretil/corpustei/transformations/html/sa_mAgha-zizupAlavadha.htm"]),
}

RE_A  = re.compile(r"//\s*([A-Za-z]{1,8})_(\d+)[.,](\d+)")            # // ABBR_canto.verse  (Manu/Raghu/Shishu/Harivamsha)
RE_B  = re.compile(r"^\s*\S+\s+(\d+)[.,](\d+)\s+(.+?)\s*\\?/{1,2}\s*$") # Word canto.verse  text //  (Visnu prose sutra)
STAR  = re.compile(r"\*[A-Za-z]+_\d")                                   # *HV_1.0*1:1 star-passage marker

def _emit(cantos, c, v, iast):
    iast = re.sub(r"[\\^~]", "", iast).strip()       # drop GRETIL analytic markers
    # Some GRETIL pages mark an original print-page break with a run of
    # underscores glued directly onto the same line as the following verse
    # marker -- confirmed for real on raghuvamsha. Since it shares the
    # matched line rather than sitting on its own separate line, the
    # stray-line-drop logic in parse() below never sees it as a discardable
    # line on its own; it has to be stripped here instead. Underscores
    # never appear in real Sanskrit verse text, so any run of 3+ is safe
    # to remove regardless of position.
    iast = re.sub(r"_{3,}", " ", iast).strip()
    if not iast:
        return
    dev = iast_to_dev(iast).replace("//", "॥").replace("/", "।")
    cantos.setdefault(c, []).append({"number": v, "sanskrit_text": dev})

def parse(text, name, unit):
    text = to_text(text)
    cantos = collections.OrderedDict()
    buf = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line[0] in "[%#" or STAR.search(line):
            continue
        m = RE_A.search(line)
        if m:
            before = line[:m.start()].strip()
            iast = (" ".join(buf) + " " + before).strip() if buf else before
            _emit(cantos, int(m.group(2)), int(m.group(3)), iast)
            buf = []
            continue
        b = RE_B.match(line)
        if b:
            _emit(cantos, int(b.group(1)), int(b.group(2)), b.group(3))
            buf = []
            continue
        if line.endswith("/"):                 # pada continuation of a multi-line verse
            buf.append(line)
            continue
        buf = []                                # stray/header line: drop (do not pollute next verse)
    return [{"id": f"{unit}_{c:02d}", "reference": f"{name}, {unit.title()} {c}", "shlokas": sh}
            for c, sh in cantos.items()]

# --- Harivamsha: a genuinely different GRETIL markup convention ---------
# Every other entry in GRETIL above uses "// ABBR_c.v //" or "Word c.v text /"
# with a comma-or-dot separator and a symmetric "//...//" wrapper. Harivamsha's
# plaintext transformation does neither: a verse ends in a BARE "// HV_c.v"
# (dot separator, no closing "//" -- the ref itself terminates the marker),
# and a star (secondary-recension) passage ends in "*HV_c.v*n" instead, with
# "|" as its internal pada separator instead of "/". A regex built for the
# common pattern matches nothing in this file, which is the actual reason
# every import attempt wrote 0 shlokas -- not a network/access problem.
_HV_MARKER = re.compile(
    r"//\s*HV_(?P<ca>\d+)\.(?P<cv>\d+)|\*HV_(?P<sa>\d+)\.(?P<sv>\d+)\*(?P<sn>\d+)"
)
_HV_EDITORIAL    = re.compile(r"\[[hk]:.*?:[hk]\]", re.DOTALL)   # [h:...:h] header, [k:...:k] commentary
_HV_INTERLOCUTOR = re.compile(r"\{[^}]*\}")                      # {speaker uvaca:} tags
_HV_HEADER_RULE  = re.compile(r"_{6,}")                          # GRETIL's header/body separator rule (older pages)
# This plaintext transformation's own metadata block -- plain English
# ("Editorial lines: = header = commentary ## Revisions: ... TEI encoding by
# mass conversion of GRETIL's Sanskrit corpus") -- ends in a literal "# text"
# marker and carries NO underscore-rule separator at all. Confirmed for real:
# without this anchor, that whole English header got run through iast_to_dev()
# as if it were IAST and landed as phonetic Devanagari garbage prepended to
# the mangala verse (the marker-line fallback below doesn't help either,
# since header and verse text sit on effectively the same unbroken span).
_HV_HEADER_END = re.compile(r"#\s*text\b", re.IGNORECASE)

def _hv_strip_header(text):
    m = _HV_MARKER.search(text)
    if m is None:
        return text
    head = text[:m.start()]
    end_m = None
    for e in _HV_HEADER_END.finditer(head):
        end_m = e
    if end_m is not None:
        return text[end_m.end():]
    rule_end = None
    for r in _HV_HEADER_RULE.finditer(head):
        rule_end = r.end()
    if rule_end is not None:
        return text[rule_end:]
    return text[text.rfind("\n", 0, m.start()) + 1:]

def _hv_clean(raw):
    s = _HV_EDITORIAL.sub(" ", raw)
    s = _HV_INTERLOCUTOR.sub(" ", s)
    s = s.replace("||*", " ").replace("*||", " ")
    s = re.sub(r"\s*[/|]\s*", " / ", s)   # both constituted '/' and star '|' pada breaks
    s = re.sub(r"_{3,}", " ", s)          # defensive: same page-break artifact as raghuvamsha
    s = re.sub(r"\s+", " ", s).strip()
    return s.rstrip("/ ").strip()

def _hv_parse(text, name, unit):
    text = _hv_strip_header(text)
    cantos = collections.OrderedDict()
    last_end = 0
    for m in _HV_MARKER.finditer(text):
        raw = text[last_end:m.start()]
        last_end = m.end()
        star = m.group("sa") is not None
        c, v = (int(m.group("sa")), int(m.group("sv"))) if star else (int(m.group("ca")), int(m.group("cv")))
        cleaned = _hv_clean(raw)
        if not cleaned:
            continue
        dev = iast_to_dev(cleaned).replace("/", "।").strip()
        dev = (dev[:-1].strip() if dev.endswith("।") else dev) + " ॥"
        number = f"{v}*{m.group('sn')}" if star else v
        cantos.setdefault(c, []).append({"number": number, "sanskrit_text": dev})
    return [{"id": f"{unit}_{c:02d}", "reference": f"{name}, {unit.title()} {c}", "shlokas": sh}
            for c, sh in cantos.items()]

def run(tid):
    spec = GRETIL[tid]
    all_text = "\n".join(http_get(u) for u in spec["urls"])
    if tid == "harivamsha":
        items = _hv_parse(all_text, spec["name"], spec["unit"])
    else:
        items = parse(all_text, spec["name"], spec["unit"])
    write_grantha(spec["target"], spec["schema"], spec["author"], items)
