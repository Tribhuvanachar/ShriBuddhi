"""Shared paths, IO helpers and the fixed status vocabulary for the Kamadhenu audit."""
import csv, json, os, sys, time, hashlib, datetime, html as _html
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DGE = ROOT / "dge"
DS = ROOT / "kamadhenu_dataset"
INCOMING = DS / "incoming_audio"
PROCESSED = DS / "processed"
REPORTS = DS  # generated reports live next to the dataset so one folder is the whole picture
TOOLS = ROOT / "tools" / "kamadhenu"

# Exact status vocabulary demanded by the task (section 14). Nothing else may be used.
DONE = "🟢 DONE"
VERIFIED = "🟢 VERIFIED"
PARTIAL = "🟡 PARTIAL"
IN_PROGRESS = "🟠 IN PROGRESS"
NOT_STARTED = "🔴 NOT STARTED"
BLOCKED = "🔴 BLOCKED"
NOT_REQUIRED = "⚪ NOT REQUIRED"
STATUSES = [DONE, VERIFIED, PARTIAL, IN_PROGRESS, NOT_STARTED, BLOCKED, NOT_REQUIRED]

# Coverage vocabulary (section 7)
COV_GOOD = "🟢 GOOD COVERAGE"
COV_LIMITED = "🟡 LIMITED COVERAGE"
COV_NEEDS = "🟠 NEEDS MORE EXAMPLES"
COV_NONE = "🔴 NO AUDIO"

AUDIO_EXT = {".wav", ".mp3", ".m4a", ".flac", ".aac", ".ogg", ".opus", ".wma", ".aiff", ".aif", ".mp4", ".webm", ".amr", ".3gp"}


def now_ist():
    """Timestamp in IST (Asia/Kolkata), the project lead's local time."""
    t = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5, minutes=30)))
    return t.strftime("%d %b %Y, %I:%M %p IST").replace(" 0", " ")


def log(*a):
    print("[kamadhenu]", *a, flush=True)


def read_json(p, default=None):
    p = Path(p)
    if not p.exists():
        return default
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def write_json(p, obj):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def write_jsonl(p, rows):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def write_csv(p, rows, fields=None):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    rows = list(rows)
    if fields is None:
        fields = []
        for r in rows:
            for k in r:
                if k not in fields:
                    fields.append(k)
    with open(p, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if v is None else (json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v)) for k, v in r.items()})


def write_text(p, s):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(s)


def esc(s):
    return _html.escape("" if s is None else str(s), quote=True)


def sha1_file(p, limit=None):
    h = hashlib.sha1()
    with open(p, "rb") as f:
        while True:
            b = f.read(1 << 20)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def rel(p):
    try:
        return str(Path(p).resolve().relative_to(ROOT))
    except Exception:
        return str(p)


def fmt_dur(sec):
    if sec is None:
        return "—"
    sec = float(sec)
    if sec < 60:
        return f"{sec:.1f}s"
    m, s = divmod(int(round(sec)), 60)
    h, m = divmod(m, 60)
    return f"{h}h {m:02d}m {s:02d}s" if h else f"{m}m {s:02d}s"


HTML_HEAD = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
:root{{--bg:#faf7f1;--panel:#fff;--ink:#241c14;--muted:#7a6f60;--line:#e5dccb;--accent:#8f3a1d;--ok:#2f8f5b;--warn:#c98a2b;--bad:#b23b3b;--info:#2f6f9f}}
body{{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 system-ui,"Noto Sans",sans-serif}}
main{{max-width:1280px;margin:0 auto;padding:18px 16px 60px}}
h1{{font-size:22px;margin:0 0 4px}} h2{{font-size:17px;margin:26px 0 8px;border-bottom:1px solid var(--line);padding-bottom:4px}}
.sub{{color:var(--muted);font-size:12.5px;margin-bottom:14px}}
table{{border-collapse:collapse;width:100%;background:var(--panel);font-size:13px}}
th,td{{border:1px solid var(--line);padding:5px 8px;vertical-align:top;text-align:left}}
th{{background:#f1e9da;position:sticky;top:0}}
.wrap{{overflow-x:auto;margin-bottom:10px}}
.dev{{font-family:"Noto Sans Devanagari","Noto Serif Devanagari",serif;font-size:14.5px}}
.mono{{font-family:ui-monospace,Menlo,monospace;font-size:12px;word-break:break-word;min-width:220px}}
.pill{{display:inline-block;padding:1px 8px;border-radius:999px;font-size:12px;border:1px solid var(--line);background:#f7f2e8;white-space:nowrap}}
.cards{{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:10px;margin:10px 0}}
.card{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:10px 12px}}
.card b{{display:block;font-size:20px}} .card span{{color:var(--muted);font-size:12px}}
.note{{background:#fff8e6;border:1px solid #f0d9a0;border-radius:8px;padding:8px 12px;margin:8px 0;font-size:13px}}
.bad{{color:var(--bad)}} .ok{{color:var(--ok)}} .warn{{color:var(--warn)}}
details summary{{cursor:pointer;color:var(--accent)}}
input[type=search]{{width:100%;max-width:420px;padding:7px 10px;border:1px solid var(--line);border-radius:8px;font:inherit;margin:6px 0 10px}}
</style></head><body><main>
"""
HTML_FOOT = "</main></body></html>\n"


def html_page(title, body, subtitle=""):
    return HTML_HEAD.format(title=esc(title)) + f"<h1>{esc(title)}</h1><div class='sub'>{esc(subtitle)} · generated {esc(now_ist())} · regenerate with <code>python3 tools/kamadhenu_audit.py</code></div>" + body + HTML_FOOT


def table_html(rows, fields, cls="", dev_fields=(), mono_fields=(), id_attr=""):
    h = [f"<div class='wrap'><table class='{cls}'{(' id=' + chr(34) + id_attr + chr(34)) if id_attr else ''}><thead><tr>" + "".join(f"<th>{esc(f)}</th>" for f in fields) + "</tr></thead><tbody>"]
    for r in rows:
        cells = []
        for f in fields:
            v = r.get(f, "")
            if isinstance(v, (list, dict)):
                v = json.dumps(v, ensure_ascii=False)
            c = "dev" if f in dev_fields else ("mono" if f in mono_fields else "")
            cells.append(f"<td class='{c}'>{esc(v)}</td>")
        h.append("<tr>" + "".join(cells) + "</tr>")
    h.append("</tbody></table></div>")
    return "".join(h)


FILTER_JS = """<script>
function kmFilter(inp, tableId){var q=inp.value.toLowerCase();var rows=document.querySelectorAll('#'+tableId+' tbody tr');rows.forEach(function(r){r.style.display=r.innerText.toLowerCase().indexOf(q)>=0?'':'none';});}
</script>"""
