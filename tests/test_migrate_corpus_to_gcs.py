"""Tests for tools/migrate_corpus_to_gcs.py and the path contract it shares
with the corpusFile function.

The second half matters more than the first. The proxy's objectNameFor()
(firebase/functions/lib/corpus-access.js) REFUSES any path with a segment
outside [A-Za-z0-9._-] rather than sanitising it, which is the right call for
hostile input and a trap for our own corpus: the day someone imports a grantha
into a folder with a space or a Devanagari name, the reader would 404 on it
with no explanation. test_every_corpus_path_is_servable walks the real tree so
that fails here, at commit time, instead of there.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

import migrate_corpus_to_gcs as mig  # noqa: E402

# The exact character class functions/lib/corpus-access.js enforces per segment.
SEGMENT = re.compile(r"^[A-Za-z0-9._-]+$")


def test_enumerates_the_real_corpus():
    files = mig.corpus_files(mig.DATA)
    assert len(files) > 1000, "the corpus should be well over a thousand data.json files"
    rels = [rel for rel, _ in files]
    assert len(set(rels)) == len(rels), "no path may appear twice"
    assert all(rel.endswith("/data.json") for rel in rels)


def test_generated_sidecars_are_left_public():
    # _references/_padaccheda/_commentary_sandhi are loaded on every page view
    # for every visitor; routing them through a per-request role check would
    # buy nothing and cost an invocation each.
    rels = [rel for rel, _ in mig.corpus_files(mig.DATA)]
    for skip in mig.SKIP_DIRS:
        assert not any(("/" + skip + "/") in ("/" + r) or r.startswith(skip + "/") for r in rels), \
            f"{skip} should not be migrated"


def test_every_corpus_path_is_servable():
    """Every real corpus path must survive the proxy's own path check."""
    offenders = []
    for rel, _ in mig.corpus_files(mig.DATA):
        for seg in rel.split("/"):
            if not SEGMENT.match(seg):
                offenders.append((rel, seg))
                break
    assert not offenders, (
        "these corpus paths would be refused by corpus-access.js objectNameFor() "
        "and 404 behind the proxy:\n" + "\n".join(f"  {r}  (segment {s!r})" for r, s in offenders[:20])
    )


def test_manifest_shape_and_digests(tmp_path):
    root = tmp_path / "data"
    (root / "a" / "b").mkdir(parents=True)
    (root / "a" / "b" / "data.json").write_text('{"items":[]}', encoding="utf-8")
    (root / "a" / "notes.txt").write_text("ignore me", encoding="utf-8")
    (root / "_references").mkdir()
    (root / "_references" / "data.json").write_text("{}", encoding="utf-8")

    m = mig.build_manifest(root, "corpus/")
    assert m["count"] == 1, "only data.json files, and not the generated sidecars"
    row = m["files"][0]
    assert row["path"] == "a/b/data.json"
    assert row["object"] == "corpus/a/b/data.json"
    assert row["size"] == len('{"items":[]}')
    # base64 of the raw md5 digest — the form GCS reports back, so a re-run can
    # compare without downloading anything.
    import base64, hashlib
    assert row["md5"] == base64.b64encode(hashlib.md5(b'{"items":[]}').digest()).decode()


def test_prefix_is_normalised(tmp_path):
    root = tmp_path / "data"
    (root / "x").mkdir(parents=True)
    (root / "x" / "data.json").write_text("{}", encoding="utf-8")
    assert mig.build_manifest(root, "")["files"][0]["object"] == "x/data.json"
    assert mig.build_manifest(root, "p/")["files"][0]["object"] == "p/x/data.json"


def test_dry_run_needs_no_credentials_and_uploads_nothing(tmp_path):
    root = tmp_path / "data"
    (root / "x").mkdir(parents=True)
    (root / "x" / "data.json").write_text("{}", encoding="utf-8")
    out = tmp_path / "manifest.json"
    rc = mig.main(["--data", str(root), "--manifest", str(out)])
    assert rc == 0
    assert out.exists()


def test_apply_without_a_bucket_refuses(tmp_path):
    root = tmp_path / "data"
    (root / "x").mkdir(parents=True)
    (root / "x" / "data.json").write_text("{}", encoding="utf-8")
    with pytest.raises(SystemExit):
        mig.main(["--data", str(root), "--apply", "--quiet"])


def test_help_does_not_invite_a_key_on_the_command_line():
    # A credential typed on a command line lands in shell history and in the
    # process table. The script takes none; this keeps it that way.
    out = subprocess.run([sys.executable, str(REPO / "tools" / "migrate_corpus_to_gcs.py"), "--help"],
                         capture_output=True, text=True, check=True).stdout
    assert "--bucket" in out
    for flag in ("--key", "--credentials", "--service-account", "--token"):
        assert flag not in out, f"{flag} would put a credential on the command line"
