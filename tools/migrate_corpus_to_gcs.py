#!/usr/bin/env python3
"""Move the corpus from public static files into a private GCS bucket.

THE POINT. data/**/data.json is served today as a public static asset on
Firebase Hosting, so every gate in the reader is advisory: it stops the SITE
showing a text, not the file being fetched by anyone who knows the URL. The
corpusFile Cloud Function (firebase/functions/index.js) closes that by
serving corpus text from a PRIVATE bucket after checking the caller's role.
This script puts the files there.

It is the slow half of a switch that is otherwise one string:

    1. python3 tools/migrate_corpus_to_gcs.py --bucket sarvamula-corpus --apply
    2. python3 tools/migrate_corpus_to_gcs.py --bucket sarvamula-corpus --verify
    3. set CORPUS_BUCKET on the function, deploy it
    4. set corpusBase in js/config.js, deploy Hosting

Nothing is deleted from the repository or from Hosting by any of this. Step 4
is reversible by blanking one string; the static files stay exactly where they
are until someone decides, separately and deliberately, to stop publishing
them. That ordering is on purpose — a migration whose rollback needs a restore
is not a switch.

CREDENTIALS. This script does NOT take a key on the command line and never
prints one. It uses Application Default Credentials, so run it as:

    export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
    python3 tools/migrate_corpus_to_gcs.py --bucket <name> --apply

The service account needs roles/storage.objectAdmin on that bucket and nothing
else. The bucket itself must have uniform bucket-level access with NO public
member — a corpus bucket that allInUsers can read is the same static hosting
with extra steps.

--dry-run (the default) needs no credentials and no network at all: it walks
the tree, writes the manifest, and reports exactly what --apply would do.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"
DEFAULT_PREFIX = "corpus/"

# Folders under data that are not grantha text and have no business behind
# an access gate: the search index, the generated sidecars, the manifests. They
# stay public static files, because the reader loads them on every page view
# for every visitor and putting them behind a per-request role check would buy
# nothing and cost a function invocation each.
SKIP_DIRS = {"_references", "_padaccheda", "_commentary_sandhi", "_highlight", "_search"}


def corpus_files(root: Path):
    """Every data.json under data, as (relative posix path, absolute path)."""
    out = []
    for path in sorted(root.rglob("data.json")):
        rel = path.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts[:-1]):
            continue
        out.append((rel.as_posix(), path))
    return out


def md5_b64(path: Path) -> str:
    """The same digest GCS stores, so a re-run can skip what is already there."""
    h = hashlib.md5()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return base64.b64encode(h.digest()).decode("ascii")


def build_manifest(root: Path, prefix: str):
    rows = []
    total = 0
    for rel, path in corpus_files(root):
        size = path.stat().st_size
        total += size
        rows.append({"path": rel, "object": prefix + rel, "size": size, "md5": md5_b64(path)})
    return {"prefix": prefix, "count": len(rows), "bytes": total, "files": rows}


def get_bucket(name: str):
    """Imported lazily so --dry-run works on a machine with no GCS library."""
    try:
        from google.cloud import storage  # type: ignore
    except ImportError:
        sys.exit(
            "google-cloud-storage is not installed.\n"
            "  pip install google-cloud-storage\n"
            "(--dry-run needs neither the library nor credentials.)"
        )
    return storage.Client().bucket(name)


def upload(bucket, manifest, force=False, quiet=False):
    """Upload every file whose digest is not already in the bucket.

    Resumable by construction rather than by bookkeeping: a run that dies at
    file 900 of 1,728 re-checks the first 899 digests (cheap, metadata-only)
    and uploads the rest. There is no state file to go stale.
    """
    uploaded = skipped = 0
    sent = 0
    started = time.time()
    for i, row in enumerate(manifest["files"], 1):
        blob = bucket.blob(row["object"])
        if not force:
            try:
                blob.reload()
                if blob.md5_hash == row["md5"]:
                    skipped += 1
                    continue
            except Exception:
                pass  # not there yet, or metadata unreadable — upload it
        src = DATA / row["path"]
        blob.cache_control = "private, max-age=300"
        blob.content_type = "application/json; charset=utf-8"
        blob.upload_from_filename(str(src))
        uploaded += 1
        sent += row["size"]
        if not quiet and uploaded % 50 == 0:
            el = time.time() - started
            print(f"  {i}/{manifest['count']}  uploaded {uploaded}  "
                  f"{sent / 1e6:.1f} MB  {el:.0f}s", flush=True)
    return uploaded, skipped, sent


def verify(bucket, manifest, quiet=False):
    """Every file present, and the same bytes. Reports what is wrong, not just how many."""
    missing, mismatched = [], []
    for row in manifest["files"]:
        blob = bucket.blob(row["object"])
        try:
            blob.reload()
        except Exception:
            missing.append(row["path"])
            continue
        if blob.md5_hash != row["md5"]:
            mismatched.append(row["path"])
    if not quiet:
        for p in missing[:20]:
            print(f"  MISSING     {p}")
        for p in mismatched[:20]:
            print(f"  MISMATCHED  {p}")
        if len(missing) > 20 or len(mismatched) > 20:
            print(f"  … and {max(0, len(missing) - 20) + max(0, len(mismatched) - 20)} more")
    return missing, mismatched


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bucket", help="target GCS bucket (required for --apply/--verify)")
    ap.add_argument("--prefix", default=DEFAULT_PREFIX,
                    help=f"object-name prefix; must match the function's CORPUS_PREFIX (default {DEFAULT_PREFIX!r})")
    ap.add_argument("--data", default=str(DATA), help="corpus root (default data)")
    ap.add_argument("--apply", action="store_true", help="actually upload")
    ap.add_argument("--verify", action="store_true", help="check the bucket matches the tree")
    ap.add_argument("--force", action="store_true", help="re-upload even when the digest matches")
    ap.add_argument("--manifest", help="write the manifest here (default: skip)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    root = Path(args.data)
    if not root.is_dir():
        sys.exit(f"No corpus at {root}")
    prefix = args.prefix if (args.prefix == "" or args.prefix.endswith("/")) else args.prefix + "/"

    manifest = build_manifest(root, prefix)
    if not args.quiet:
        print(f"{manifest['count']} files, {manifest['bytes'] / 1e6:.1f} MB under {root}")
    if args.manifest:
        Path(args.manifest).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"manifest -> {args.manifest}")

    if not args.apply and not args.verify:
        if not args.quiet:
            print("dry run — nothing uploaded. Re-run with --bucket NAME --apply to upload.")
            for row in manifest["files"][:5]:
                print(f"  would upload {row['path']} -> gs://<bucket>/{row['object']}")
            if manifest["count"] > 5:
                print(f"  … and {manifest['count'] - 5} more")
        return 0

    if not args.bucket:
        sys.exit("--bucket is required for --apply and --verify")
    bucket = get_bucket(args.bucket)

    if args.apply:
        uploaded, skipped, sent = upload(bucket, manifest, force=args.force, quiet=args.quiet)
        print(f"uploaded {uploaded}, already current {skipped}, {sent / 1e6:.1f} MB sent")

    if args.verify:
        missing, mismatched = verify(bucket, manifest, quiet=args.quiet)
        if missing or mismatched:
            print(f"VERIFY FAILED — {len(missing)} missing, {len(mismatched)} mismatched")
            return 1
        print(f"verified {manifest['count']} objects in gs://{args.bucket}/{prefix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
