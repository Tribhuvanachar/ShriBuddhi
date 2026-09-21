"""The legacy-slug upgrade must not re-fire on its own output.

Two of the rules in js/core.js rename a folder into a leaf BELOW itself:

    'vedanga/nirukta'  ->  'vedanga/nirukta/mula'

The prefix test then matched the upgraded slug all over again, because
'vedanga/nirukta/mula' does start with 'vedanga/nirukta/', and the leaf was
appended a second time. Every link to the Nirukta and the Jyotisha asked for
data/vedanga/nirukta/mula/mula/data.json, got a 404, and showed the reader
"Data Not Found" -- two of the six Vedangas unreachable from the library,
behind a rule whose whole purpose was to make them reachable.

The render sweep of all 1,306 granthas found it on 21 Sep 2026.

These tests run the REAL function, extracted from js/core.js and executed in
node. An earlier version of this file re-implemented it in Python instead,
and every behavioural test passed with the fix deleted from the JS -- it was
testing the copy, not the code. If node is missing the tests skip rather than
pretend.
"""
import json
import os
import re
import shutil
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORE = os.path.join(ROOT, "js", "core.js")
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")


def _source():
    return open(CORE, encoding="utf-8").read()


def _table_block(src):
    m = re.search(r"(const|var|let)?\s*DGE_LEGACY_SLUGS\s*=\s*\{.*?\n\};", src, re.S)
    assert m, "DGE_LEGACY_SLUGS not found in js/core.js"
    return m.group(0).lstrip()


def _fn_block(src):
    m = re.search(r"window\.dgeUpgradeLegacySlug\s*=\s*function[\s\S]*?\n\};", src)
    assert m, "dgeUpgradeLegacySlug not found in js/core.js"
    return m.group(0)


def upgrade_many(slugs):
    """Run the shipped function over each slug, in node."""
    src = _source()
    table = _table_block(src)
    if not table.startswith(("const", "var", "let")):
        table = "const " + table
    script = (table + "\nconst window = {};\n" + _fn_block(src) +
              "\nconst input = " + json.dumps(slugs) + ";\n"
              "console.log(JSON.stringify(input.map(window.dgeUpgradeLegacySlug)));")
    out = subprocess.run([NODE, "-e", script], capture_output=True, text=True, cwd=ROOT)
    assert out.returncode == 0, "node failed: " + (out.stderr or "")[:400]
    return json.loads(out.stdout.strip().splitlines()[-1])


def table():
    body = re.sub(r"//[^\n]*", "", _table_block(_source()))
    return dict(re.findall(r"'([^']+)'\s*:\s*'([^']+)'", body))


def test_the_table_is_present_and_nonempty():
    assert len(table()) > 10


def test_a_rule_pointing_below_itself_does_not_re_fire():
    """The exact shape of the bug.

    Most rules move a slug sideways ('puranas' -> 'purana') and cannot match
    their own output. Two point BELOW themselves, and those can, because the
    destination still begins with the source. Feeding such a destination back
    in must return it untouched.

    This is not the same as saying no rule may act on another rule's
    destination: 'ancillary/nirukta' -> 'vedanga/nirukta' -> '.../mula' is a
    deliberate two-step chain and is fine.
    """
    t = table()
    nested = [(s, d) for s, d in t.items() if d.startswith(s + "/")]
    assert nested, "expected at least the two vedanga rules to point below themselves"
    got = upgrade_many([d for _, d in nested])
    for (src, dest), out in zip(nested, got):
        assert out == dest, (
            "rule %r -> %r re-fires on its own output, giving %r" % (src, dest, out))


def test_upgrading_converges():
    """Repeated application must reach a fixed point, never grow without end."""
    t = table()
    probes = list(t) + list(t.values()) + [s + "/mula" for s in t]
    cur = probes
    for _ in range(6):
        nxt = upgrade_many(cur)
        if nxt == cur:
            return
        for before, after in zip(cur, nxt):
            assert not (after != before and after.startswith(before + "/") and
                        after[len(before):].count("/") == 1 and
                        after.endswith("/" + before.rsplit("/", 1)[-1])), (
                "%r grew by repeating its own last segment: %r" % (before, after))
        cur = nxt
    pytest.fail("slugs never settled after six passes")


def test_the_two_vedangas_resolve_to_a_real_file():
    slugs = ["vedanga/nirukta", "vedanga/nirukta/mula",
             "vedanga/jyotisha", "vedanga/jyotisha/mula"]
    for slug, got in zip(slugs, upgrade_many(slugs)):
        path = os.path.join(ROOT, "data", got, "data.json")
        assert os.path.isfile(path), "%r -> %r, which is not a file" % (slug, got)
