#!/usr/bin/env python3
"""Land a Gemini proofread that never made it back to this repo.

gemini-proofread-blocks.yml runs on JagatTest, where GEMINI_API_KEY is, and
pushes the corrected blocks back here.  On 22 Sep 2026 run 35687670866 hit the
240-minute job ceiling; the artifact step still uploaded (825 proofread blocks,
already paid for) but the push step failed with "Invalid username or token" --
SHRIBUDDHI_TOKEN can clone the private repo but cannot push to it.

Rather than pay for those blocks twice, download the run's `gemini-proofread`
artifact and merge it in with this.  Merging by POSITION alone would be
reckless, so every block is matched on its address and its raw `text`; a block
whose raw text has drifted is refused and reported, never silently overwritten.

    python3 tools/aitareya/land_proofread.py --from <unzipped-artifact-dir>
    python3 tools/aitareya/land_proofread.py --from <dir> --write
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

STAGED_DIR = pathlib.Path("data/ocr_staging/aitareya")
ADDRESS = ("aranyaka", "adhyaya", "khanda", "coarse", "page", "layer")


def indent_of(raw: str, default: int = 1) -> int:
    """Re-serialising with the wrong indent rewrites every line of a 15,000-line
    file and buries the handful of real changes.  Read the indent back off the
    file instead of assuming json.dump's."""
    for line in raw.split("\n", 40)[1:]:
        if line.strip():
            return len(line) - len(line.lstrip(" ")) or default
    return default


def address(block: dict) -> tuple:
    return tuple(block.get(k) for k in ADDRESS)


def merge_file(local: dict, donor: dict) -> tuple[list[dict], dict]:
    """Return (blocks, stats).  `local` is mutated only through the copy."""
    lb, db = local.get("blocks") or [], donor.get("blocks") or []
    stats = {"landed": 0, "already": 0, "donor_blank": 0, "mismatch": 0,
             "count_mismatch": int(len(lb) != len(db))}
    if stats["count_mismatch"]:
        return lb, stats

    out = []
    for l, d in zip(lb, db):
        proofed = (d.get("text_proofread") or "").strip()
        if (l.get("text_proofread") or "").strip():
            stats["already"] += 1
        elif not proofed:
            stats["donor_blank"] += 1
        elif address(l) != address(d) or (l.get("text") or "") != (d.get("text") or ""):
            # The donor was proofreading a different block than this one.
            stats["mismatch"] += 1
        else:
            l = dict(l)
            l["text_proofread"] = d["text_proofread"]
            stats["landed"] += 1
        out.append(l)
    return out, stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="src", required=True,
                    help="directory holding the unzipped gemini-proofread artifact")
    ap.add_argument("--staged-dir", default=str(STAGED_DIR))
    ap.add_argument("--write", action="store_true",
                    help="without this nothing is written; the counts are still printed")
    args = ap.parse_args(argv)

    src, staged = pathlib.Path(args.src), pathlib.Path(args.staged_dir)
    donors = sorted(src.glob("*_segmented.json"))
    if not donors:
        print(f"no *_segmented.json under {src}", file=sys.stderr)
        return 1

    refused = 0
    for donor_path in donors:
        target = staged / donor_path.name
        if not target.exists():
            print(f"{donor_path.name:40s} SKIP  no such file under {staged}")
            refused += 1
            continue
        raw = target.read_text(encoding="utf-8")
        local = json.loads(raw)
        donor = json.loads(donor_path.read_text(encoding="utf-8"))
        blocks, st = merge_file(local, donor)
        if st["count_mismatch"]:
            print(f"{donor_path.name:40s} REFUSED  block counts differ "
                  f"({len(local.get('blocks') or [])} here, "
                  f"{len(donor.get('blocks') or [])} in the artifact)")
            refused += 1
            continue
        print(f"{donor_path.name:40s} land={st['landed']:5d} already={st['already']:5d} "
              f"donor-blank={st['donor_blank']:5d} mismatch={st['mismatch']:5d}")
        refused += st["mismatch"]
        if args.write and st["landed"]:
            local["blocks"] = blocks
            target.write_text(
                json.dumps(local, ensure_ascii=False, indent=indent_of(raw)) + "\n",
                encoding="utf-8")

    if not args.write:
        print("\ndry run -- nothing written.  Re-run with --write to land it.")
    return 1 if refused else 0


if __name__ == "__main__":
    raise SystemExit(main())
