#!/usr/bin/env python3
"""KAMADHENU master command — rerunnable, idempotent.

    python3 tools/kamadhenu_audit.py            # everything except downloading (uses whatever audio is present)
    python3 tools/kamadhenu_audit.py --fetch    # also (re)probe sources and download reachable audio first
    python3 tools/kamadhenu_audit.py --offline  # skip every network call (no source probe, no fetch)

Workflow for new recordings: copy files into kamadhenu_dataset/incoming_audio/<any-folder>/, run this command,
open kamadhenu_dataset/KAMADHENU_STATUS.html. Originals are never modified; every output is regenerated from
inputs + caches, so re-running never destroys earlier results.
"""
import sys, time, traceback
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.kamadhenu import common, sources, fetch, inventory, texts, chandas_bridge, mapping, coverage, reference_bank, dataset, health, requests, compare_vagdhenu, frontend_gap, gap_matrix, dashboard  # noqa: E402


def main(argv):
    do_fetch = "--fetch" in argv; offline = "--offline" in argv
    steps = []
    if not offline:
        steps.append(("sources", lambda: sources.run()))
    if do_fetch and not offline:
        steps.append(("fetch", lambda: fetch.run()))
    steps += [
        ("inventory (audio QC)", inventory.run),
        ("texts (DGE canonical index)", texts.run),
        ("chandas (DGE engine, headless)", chandas_bridge.run),
        ("mapping (audio ↔ text)", mapping.run),
        ("coverage (pass 1)", coverage.run),
        ("reference bank", reference_bank.run),
        ("coverage (pass 2, with reference status)", coverage.run),
        ("dataset + subsets", dataset.run),
        ("health report", health.run),
        ("recording requests", requests.run),
        ("vāgdhenu chandas comparison", compare_vagdhenu.run),
        ("frontend gap tests", frontend_gap.run),
        ("gap matrix", gap_matrix.run),
        ("dashboard", dashboard.run),
    ]
    failures = []
    t0 = time.time()
    for name, fn in steps:
        common.log(f"=== {name}")
        try:
            fn()
        except Exception as e:  # never hide failures — record and continue so the dashboard still shows the rest
            failures.append((name, repr(e)))
            common.log(f"!!! {name} FAILED: {e!r}")
            traceback.print_exc()
    common.write_json(common.DS / "last_run.json", {"finished_at": common.now_ist(), "seconds": round(time.time() - t0, 1), "failures": failures, "args": argv})
    common.log(f"done in {time.time()-t0:.0f}s; failures: {failures or 'none'}; open kamadhenu_dataset/KAMADHENU_STATUS.html")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
