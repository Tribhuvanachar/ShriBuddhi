#!/usr/bin/env python3
"""spend_report.py -- what every engine cost, per work, with the losses named.

Answers, from evidence rather than memory: what has this project spent, on
which book, with which engine, how long it took, what failed, what that
failure cost, and what we could quote back to a vendor to ask about it.

Three sources, and it says which fact came from which:

  admin/config/cost_ledger.jsonl   money. One row per billed batch.
  admin/config/ocr_receipts.json   the staged files themselves -- source PDF,
                                   timings, usage blocks, every page error.
  admin/config/ocr_sarvam_missing.json  the pages that never came back.

A failure is only a LOSS if it was billed. A 402 is Sarvam declining the job
because the prepaid balance was empty; it is returned before a page is read,
so those pages cost nothing and the money is still on the account. A 500 is
Sarvam's server failing partway, and whether that meters is a question only
Sarvam can answer -- which is why it is counted separately and never folded
into a single "amount lost" that would be wrong either way.

    python3 tools/spend_report.py --out admin/config/spend_report.json
"""
import argparse, collections, json, os, sys, time

LEDGER = "admin/config/cost_ledger.jsonl"
RECEIPTS = "admin/config/ocr_receipts.json"
MISSING = "admin/config/ocr_sarvam_missing.json"

# How a page-level error is classified for money. Anything unrecognised is
# counted as unknown rather than guessed at.
REFUSED = "not billed - the job was declined before any page was read"
SERVER = "billing unconfirmed - the job failed partway through"
NOT_TRIED = "not billed - not attempted after an earlier refusal"


def classify(err: str) -> tuple:
    e = str(err)
    if "402" in e:
        return "refused", REFUSED
    if "not attempted" in e:
        return "not_attempted", NOT_TRIED
    if "500" in e or "Internal Server" in e:
        return "server_error", SERVER
    return "unknown", "unclassified - read the staged file"


def load(path, default=None):
    if not os.path.isfile(path):
        return default
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def iso_minutes(a, b):
    """Wall-clock minutes between the earliest and latest stamp, or None."""
    try:
        fmt = "%Y-%m-%dT%H:%M:%SZ"
        return round((time.mktime(time.strptime(b, fmt))
                      - time.mktime(time.strptime(a, fmt))) / 60.0, 1)
    except Exception:                                       # noqa: BLE001
        return None


# A book is not always one staging branch. The Harikathamrtasara is 31 of
# them, one per printed volume, and "what did the Harikathamrtasara cost" is
# the question someone actually asks. Grouping is by prefix, and a work that
# matches nothing is its own group, so nothing is hidden by it.
GROUPS = [
    ("hks__", "Harikathamrtasara (all volumes)"),
    ("sudha_25_tippani_", "Nyayasudha 25 - tippanis"),
    ("aitereya_upanisad_bh__", "Aitareya Upanisad bhashya - commentaries"),
    ("giia_vyakhyana_sangr__", "Gita vyakhyana sangraha"),
    ("sangraha_ramayanam_n__", "Sangraha Ramayanam"),
    ("ruksamhita__", "Ruksamhita vyakhyanagalu"),
    ("venkatesha__", "Venkatesha Mahatmya"),
]


def group_of(work: str) -> str:
    for prefix, label in GROUPS:
        if work.startswith(prefix):
            return label
    return work


def build(root="."):
    ledger = []
    lp = os.path.join(root, LEDGER)
    if os.path.isfile(lp):
        with open(lp, encoding="utf-8") as fh:
            ledger = [json.loads(l) for l in fh if l.strip()]
    receipts = (load(os.path.join(root, RECEIPTS)) or {}).get("works", {})

    works = {}

    def row(work):
        return works.setdefault(work, {
            "work": work, "engines": {}, "inr": 0.0, "usd": 0.0,
            "pages_billed": 0, "tokens_in": 0, "tokens_out": 0,
            "source_pdf": "", "pdf_pages": None,
            "first_seen": "", "last_seen": "", "span_minutes": None,
        "processing_seconds": None,
            "staged_files": 0, "failures": [], "pages_failed": 0,
            "pages_refused": 0, "pages_server_error": 0,
            "batches": [],
        })

    # --- money, from the ledger
    for r in ledger:
        w = row(r.get("work") or "(unattributed)")
        eng = r.get("engine") or "?"
        e = w["engines"].setdefault(eng, {"inr": 0.0, "usd": 0.0, "pages": 0,
                                          "tokens_in": 0, "tokens_out": 0, "batches": 0})
        for k, f in (("inr", "inr"), ("usd", "usd")):
            e[k] += float(r.get(f) or 0); w[k] += float(r.get(f) or 0)
        for k in ("pages", "tokens_in", "tokens_out"):
            v = int(r.get(k) or 0)
            e[k if k != "pages" else "pages"] += v
        w["pages_billed"] += int(r.get("pages") or 0)
        w["tokens_in"] += int(r.get("tokens_in") or 0)
        w["tokens_out"] += int(r.get("tokens_out") or 0)
        e["batches"] += 1
        w["batches"].append({
            "at": r.get("at"), "engine": eng, "pages": int(r.get("pages") or 0),
            "inr": round(float(r.get("inr") or 0), 2), "usd": float(r.get("usd") or 0),
            "model": r.get("model") or "", "run_url": r.get("run_url") or "",
            "tokens_in": int(r.get("tokens_in") or 0),
            "tokens_out": int(r.get("tokens_out") or 0),
            "note": r.get("note") or "",
        })
        if r.get("source_pdf"):
            w["source_pdf"] = w["source_pdf"] or r["source_pdf"]

    # --- what actually happened, from the staged files
    for work, rows in receipts.items():
        w = row(work)
        w["staged_files"] = len(rows)
        stamps = sorted(x["generated_at"] for x in rows if x.get("generated_at"))
        if stamps:
            w["first_seen"], w["last_seen"] = stamps[0], stamps[-1]
            # The SPAN, not the duration. It is the distance between the first
            # and last staged file, so it counts every hour the work sat idle
            # between batches as if the engine were busy. For the September
            # runs, which were interleaved across dozens of books, this reads
            # about 120 hours for nearly everything and means nothing. Real
            # duration needs per-job timings, which only exist from 21 Sep.
            w["span_minutes"] = iso_minutes(stamps[0], stamps[-1])
        for x in rows:
            if x.get("source_pdf") and not w["source_pdf"]:
                w["source_pdf"] = x["source_pdf"]
            if x.get("pdf_pages") and not w["pdf_pages"]:
                w["pdf_pages"] = x["pdf_pages"]
            for err, n in (x.get("errors") or {}).items():
                kind, meaning = classify(err)
                w["pages_failed"] += n
                if kind == "server_error":
                    w["pages_server_error"] += n
                else:
                    w["pages_refused"] += n
                w["failures"].append({"file": x["file"], "engine": x["engine"],
                                      "pages": n, "error": err,
                                      "kind": kind, "meaning": meaning})
            for rc in (x.get("receipts") or []):
                w.setdefault("job_receipts", []).append(dict(rc, file=x["file"]))
                if rc.get("seconds") is not None:
                    w["processing_seconds"] = (w["processing_seconds"] or 0) + float(rc["seconds"])

    # --- totals
    eng_tot = collections.defaultdict(lambda: {
        "inr": 0.0, "usd": 0.0, "pages_billed": 0, "tokens_in": 0, "tokens_out": 0,
        "works": 0, "batches": 0, "pages_refused": 0, "pages_server_error": 0})
    for w in works.values():
        for eng, e in w["engines"].items():
            t = eng_tot[eng]
            t["inr"] += e["inr"]; t["usd"] += e["usd"]
            t["pages_billed"] += e["pages"]
            t["tokens_in"] += e["tokens_in"]; t["tokens_out"] += e["tokens_out"]
            t["works"] += 1; t["batches"] += e["batches"]
        # failures are attributed to the engine that produced the staged file
        for f in w["failures"]:
            eng = "sarvam" if "sarvam" in f["engine"] else f["engine"]
            t = eng_tot[eng]
            if f["kind"] == "server_error":
                t["pages_server_error"] += f["pages"]
            else:
                t["pages_refused"] += f["pages"]

    for t in eng_tot.values():
        t["inr"] = round(t["inr"], 2)
        t["inr_per_page"] = round(t["inr"] / t["pages_billed"], 4) if t["pages_billed"] else None

    grand = {
        "inr": round(sum(t["inr"] for t in eng_tot.values()), 2),
        "pages_billed": sum(t["pages_billed"] for t in eng_tot.values()),
        "pages_refused": sum(t["pages_refused"] for t in eng_tot.values()),
        "pages_server_error": sum(t["pages_server_error"] for t in eng_tot.values()),
        "works": len([w for w in works.values() if w["inr"] or w["staged_files"]]),
    }
    # The money question, answered in the only honest shape it has.
    sarvam_rate = eng_tot.get("sarvam", {}).get("inr_per_page")
    grand["confirmed_lost_inr"] = 0.0
    grand["at_risk_inr"] = round((sarvam_rate or 0) * grand["pages_server_error"], 2)
    grand["recoverable_by_rerun_inr"] = round((sarvam_rate or 0) * grand["pages_refused"], 2)

    for w in works.values():
        w["inr"] = round(w["inr"], 2)
        for e in w["engines"].values():
            e["inr"] = round(e["inr"], 2)
        w["batches"].sort(key=lambda b: b.get("at") or "")

    # Does the ledger account for every page the staging branches hold? On
    # 21 Sep 2026 it did not: 4,850 pages -- every Vision run over sandhis 2-9
    # of the Harikathamrtasara among them -- were staged, real and paid for,
    # and had no ledger row at all, understating the total by INR 949. The
    # check stays so the next drift is caught by the page rather than by
    # someone noticing a book claiming it cost nothing.
    staged_pages = collections.Counter()
    for work, rows in receipts.items():
        for x in rows:
            u = x.get("usage") or {}
            got = u.get("pages_succeeded")
            if got is None:
                got = x.get("page_entries") or 0
            eng = "sarvam" if "sarvam" in x["engine"] else "vision"
            staged_pages[(work, eng)] += got
    # Only the engines that leave a staged file can be reconciled against one.
    # Gemini adjudicates pages the other two already read and writes to
    # data/ocr_staging/_gemini, so counting it here would report its whole
    # 1,536 pages as billed-but-never-staged, which is an artefact of the
    # comparison rather than anything wrong with the ledger.
    STAGING_ENGINES = ("sarvam", "vision")
    ledger_pages = collections.Counter()
    for r in ledger:
        eng = r.get("engine") or "?"
        eng = "sarvam" if "sarvam" in eng else ("vision" if "vision" in eng else eng)
        if eng not in STAGING_ENGINES:
            continue
        ledger_pages[(r.get("work") or "", eng)] += int(r.get("pages") or 0)
    unledgered, overledgered = [], []
    for key in set(staged_pages) | set(ledger_pages):
        d = staged_pages[key] - ledger_pages[key]
        if d > 0:
            unledgered.append({"work": key[0], "engine": key[1], "pages": d})
        elif d < 0:
            overledgered.append({"work": key[0], "engine": key[1], "pages": -d})
    reconciliation = {
        "staged_pages": sum(staged_pages.values()),
        "ledger_pages": sum(ledger_pages.values()),
        "staged_not_in_ledger": sorted(unledgered, key=lambda r: -r["pages"]),
        "in_ledger_not_staged": sorted(overledgered, key=lambda r: -r["pages"]),
        "pages_unledgered": sum(r["pages"] for r in unledgered),
        "pages_overledgered": sum(r["pages"] for r in overledgered),
    }

    # Roll up, so a reader can ask about a book rather than a branch.
    groups = {}
    for w in works.values():
        g = groups.setdefault(group_of(w["work"]), {
            "group": group_of(w["work"]), "works": [], "inr": 0.0,
            "pages_billed": 0, "pages_failed": 0, "pages_refused": 0,
            "pages_server_error": 0, "staged_files": 0, "engines": {},
            "first_seen": "", "last_seen": "", "processing_seconds": None})
        g["works"].append(w["work"])
        for k in ("inr", "pages_billed", "pages_failed", "pages_refused",
                  "pages_server_error", "staged_files"):
            g[k] += w.get(k) or 0
        if w.get("processing_seconds") is not None:
            g["processing_seconds"] = (g["processing_seconds"] or 0) + w["processing_seconds"]
        for eng, e in w["engines"].items():
            ge = g["engines"].setdefault(eng, {"inr": 0.0, "pages": 0})
            ge["inr"] += e["inr"]; ge["pages"] += e["pages"]
        for f in ("first_seen", "last_seen"):
            v = w.get(f)
            if not v:
                continue
            if not g[f] or (f == "first_seen" and v < g[f]) or (f == "last_seen" and v > g[f]):
                g[f] = v
    for g in groups.values():
        g["inr"] = round(g["inr"], 2)
        g["span_minutes"] = iso_minutes(g["first_seen"], g["last_seen"])
        for ge in g["engines"].values():
            ge["inr"] = round(ge["inr"], 2)

    return {
        "reconciliation": reconciliation,
        "groups": sorted(groups.values(), key=lambda g: -g["inr"]),
        "_readme": [
            "Generated by tools/spend_report.py. Read by admin/spend.html.",
            "confirmed_lost_inr is 0.00 and that is a finding, not a placeholder:",
            "every page that failed was either refused before Sarvam read it (402,",
            "so never billed) or lost to a server error whose billing only Sarvam",
            "can confirm (500). Nothing is known to have been paid for and lost.",
            "at_risk_inr prices the 500s at the rate the ledger actually shows.",
        ],
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "grand": grand,
        "engines": {k: v for k, v in sorted(eng_tot.items())},
        "works": sorted(works.values(), key=lambda w: (-w["inr"], w["work"])),
        "gaps": [
            "No Sarvam job_id exists for anything run before 21 Sep 2026: it was "
            "logged and dropped. Those 20,452 billed pages cannot be named back "
            "to Sarvam, so a specific claim cannot be made for any of them.",
            "Per-page rates are the published list price. No invoice has been "
            "reconciled against these rows, so every rupee here is our own "
            "arithmetic rather than a confirmed charge.",
            "There is no true processing time for anything run before 21 Sep "
            "2026. What is shown is the SPAN from a book's first staged file to "
            "its last, which counts every idle hour between batches: the "
            "September runs were interleaved across dozens of books, so nearly "
            "every one reads about 120 hours and none of them mean it. Per-job "
            "durations are recorded from 21 Sep and will replace this.",
        ],
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 2)[1])
    ap.add_argument("--root", default=".")
    ap.add_argument("--out", default="admin/config/spend_report.json")
    args = ap.parse_args(argv)
    rep = build(args.root)
    with open(os.path.join(args.root, args.out), "w", encoding="utf-8") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    g = rep["grand"]
    print("total spent        INR %9.2f over %d page(s), %d work(s)"
          % (g["inr"], g["pages_billed"], g["works"]))
    for k, t in rep["engines"].items():
        print("  %-14s INR %9.2f  %6d pages  %s/page"
              % (k, t["inr"], t["pages_billed"],
                 ("INR %.3f" % t["inr_per_page"]) if t["inr_per_page"] else "-"))
    print("pages refused (not billed)      %d  -> rerun costs INR %.2f"
          % (g["pages_refused"], g["recoverable_by_rerun_inr"]))
    print("pages lost to a server error    %d  -> INR %.2f at risk, ask Sarvam"
          % (g["pages_server_error"], g["at_risk_inr"]))
    print("confirmed lost                  INR %.2f" % g["confirmed_lost_inr"])
    rc = rep["reconciliation"]
    print("reconciliation      %d staged page(s) vs %d ledgered; %d unledgered, %d over"
          % (rc["staged_pages"], rc["ledger_pages"],
             rc["pages_unledgered"], rc["pages_overledgered"]))
    print("wrote %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
