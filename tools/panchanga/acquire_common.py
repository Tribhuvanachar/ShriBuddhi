"""Shared helpers for the tools/panchanga/acquire_*.py scripts.

Each acquire_<source>.py script takes a fresh APK for one Panchanga source
and reproduces the manual extraction done on 11 Sep 2026 (see
dge/sources/README.md and dge/PENDING.md for that session's notes) as a
re-runnable tool: next year's app version in, a new dated archive folder
out, nothing hand-done.

Policy from DGE_Madhva_Acquisition_Architecture.md §24: never overwrite an
existing acquisition's artifact in place. write_archive() enforces this --
if the target folder already holds a manifest with the same artifact
hash, it's a no-op (already acquired); if the hash differs, it refuses
and tells the caller to pick a new folder name (a new year range, or a
`-v2` suffix) rather than silently clobbering history.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import zipfile

logging.disable(logging.CRITICAL)  # androguard is very chatty on DEBUG/INFO by default

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def apk_info(apk_path: str) -> dict:
    """Package name + version, via androguard (no aapt needed)."""
    from androguard.core.apk import APK
    a = APK(apk_path)
    return {
        "package": a.get_package(),
        "version": a.get_androidversion_name(),
        "sha256": sha256_file(apk_path),
    }


def extract_from_apk(apk_path: str, member: str) -> bytes:
    with zipfile.ZipFile(apk_path) as z:
        return z.read(member)


def write_archive(target_dir: str, files: dict, manifest: dict) -> str:
    """files: {relative_filename: bytes}. manifest: the source-manifest.json
    content (artifact_sha256 / artifact hashes are computed here and merged
    in, not passed by the caller, so they can't drift from the actual bytes
    written).

    Returns 'written', 'already_acquired', or raises on a real hash
    mismatch against an existing manifest (a genuine content change that
    needs a new folder, not an overwrite).
    """
    full_dir = os.path.join(ROOT, target_dir)
    manifest_path = os.path.join(full_dir, "source-manifest.json")

    if len(files) == 1:
        (fname, data), = files.items()
        manifest["artifact_sha256"] = sha256_bytes(data)
    else:
        manifest["artifacts"] = {fname: sha256_bytes(data) for fname, data in files.items()}

    if os.path.exists(manifest_path):
        existing = json.load(open(manifest_path, encoding="utf-8"))
        existing_hash = existing.get("artifact_sha256") or existing.get("artifacts")
        new_hash = manifest.get("artifact_sha256") or manifest.get("artifacts")
        if existing_hash == new_hash:
            return "already_acquired"
        raise FileExistsError(
            f"{target_dir} already holds a DIFFERENT acquisition "
            f"(existing hash {existing_hash} != new {new_hash}). "
            "Per architecture doc §24, pick a new folder (new date "
            "range or a -v2 suffix) rather than overwriting."
        )

    os.makedirs(full_dir, exist_ok=True)
    for fname, data in files.items():
        with open(os.path.join(full_dir, fname), "wb") as f:
            f.write(data)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
        f.write("\n")
    return "written"
