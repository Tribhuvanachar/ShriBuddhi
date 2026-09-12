#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# This file (unlike the rest of this repo, which is Apache-2.0) is licensed
# AGPL-3.0-or-later: it only functions as a wrapper around the AGPL-licensed
# `chanda` library and has no independent purpose without it.
"""Identify the classical Sanskrit metre (vrutta) of a verse.

Thin wrapper around the upstream `chanda` library (hrishikeshrt/chanda,
"Chandojnanam", AGPL-3.0-or-later -- see tools/chandas/vendor/NOTICE.md).
This is for CLASSICAL (laukika) vrutta identification only -- Vedic chandas
is a separate, harder, still-unsolved problem for this project (see
dge/veda_toolkit/superseded/05_chandas_autodetect_FAILED.py and PENDING.md).

Install first:
    pip install -r tools/chandas/requirements.txt

CLI usage:
    python3 tools/chandas/identify_vrutta.py "धर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः"
    python3 tools/chandas/identify_vrutta.py --json "SHLOKA LINE 1
    SHLOKA LINE 2"
    echo "SHLOKA TEXT" | python3 tools/chandas/identify_vrutta.py

Library usage:
    from tools.chandas.identify_vrutta import identify
    identify("को न्वस्मिन् साम्प्रतं लोके गुणवान् कश्च वीर्यवान्")
    # -> {"lines": [{"text": "...", "meters": [{"name": "अनुष्टुभ्", "pada_positions": ["1", "2"]}, ...]}]}
"""
import argparse
import json
import sys


def identify(text: str, verse_mode: bool = None) -> dict:
    """Identify the metre(s) of one or more lines of Sanskrit text.

    Parameters
    ----------
    text : str
        One or more lines/padas of Sanskrit verse, any script `chanda`
        supports (Devanagari, IAST, ...).
    verse_mode : bool, optional
        Group lines into 4-line verses before matching. Defaults to True
        when `text` has more than one non-empty line, else False.

    Returns
    -------
    dict
        {"lines": [{"text": str, "meters": [str, ...]}, ...]}
        `meters` is empty when nothing matched (exact or fuzzy).
    """
    from chanda import analyze_text

    lines = [line for line in text.splitlines() if line.strip()]
    if verse_mode is None:
        verse_mode = len(lines) > 1

    result = analyze_text(text, verse_mode=verse_mode)
    out = []
    for line_result in result.result.line:
        chanda_result = line_result.result
        # (name, pada_positions) pairs, e.g. ('अनुष्टुभ्', ('1', '2')) --
        # positions say which pada-role(s) of that metre this line matches,
        # since e.g. Anustubh's odd/even padas have different lakshana.
        # Dedup exact repeats, keep distinct positions for the same name.
        seen = set()
        meters = []
        for name, positions in (chanda_result.chanda or []):
            key = (name, positions)
            if key not in seen:
                seen.add(key)
                meters.append({"name": name, "pada_positions": list(positions)})
        out.append({"text": chanda_result.line, "meters": meters})
    return {"lines": out}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("text", nargs="?", help="verse text; reads stdin if omitted")
    parser.add_argument("--json", action="store_true", help="print full JSON result")
    args = parser.parse_args()

    text = args.text if args.text is not None else sys.stdin.read()
    if not text.strip():
        parser.error("no text given (pass as an argument or pipe via stdin)")

    result = identify(text)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
        return

    for line in result["lines"]:
        if not line["meters"]:
            print(f"{line['text']}  ->  (no match)")
            continue
        names = ", ".join(m["name"] for m in line["meters"])
        print(f"{line['text']}  ->  {names}")


if __name__ == "__main__":
    main()
