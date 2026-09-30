"""The public site must have no admin entry point, and the build must refuse if one returns.

tools/publish_strip_admin.py edits the STAGED copy. These tests run it on copies of the
real pages, so if someone changes render.html (or any page it touches) so that an
expected block no longer matches, this fails -- and so would the publish.
"""
import json
import os
import shutil
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
import publish_strip_admin as psa  # noqa: E402

SCRIPTS = ["admin-editor", "admin-remote", "config-editor", "content-editor", "preview-mode", "admin-gate"]


def stage(tmp_path):
    """A miniature staged tree made of the real files the tool touches, leaving out
    whatever the real publish leaves out (admin/, docs/, tools/, tests/, ...)."""
    import publish_clean_repo as pcr
    root = tmp_path / "staged"
    want = set(psa.BLOCKS) | set(psa.EXACT) | {"config/menu.json"}
    skip_top = set(pcr.EXCLUDE_DIRS) | {"data", "search_index", "backlinks", "node_modules", "images"}
    skip_rel = tuple(pcr.EXCLUDE_RELATIVE_DIRS)
    for dp, dirs, fs in os.walk(REPO):
        rel_dir = os.path.relpath(dp, REPO)
        dirs[:] = [d for d in dirs
                   if d not in pcr.EXCLUDE_DIRS
                   and not (rel_dir == "." and d in skip_top)
                   and os.path.normpath(os.path.join(rel_dir, d)) not in skip_rel]
        for f in fs:
            rel = os.path.normpath(os.path.join(rel_dir, f)).replace(os.sep, "/")
            if f.endswith(".html") or rel in want or rel in {"js/%s.js" % n for n in SCRIPTS}:
                dst = root / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(os.path.join(REPO, rel), dst)
    return root


def test_real_pages_are_stripped_cleanly(tmp_path):
    root = stage(tmp_path)
    assert psa.strip(str(root)) == []
    for n in SCRIPTS:
        assert not (root / "js" / (n + ".js")).exists()
    menu = json.loads((root / "config" / "menu.json").read_text(encoding="utf-8"))
    assert "admin" not in menu
    assert "admin" not in [e["id"] for e in menu["topBar"]]
    assert "access" not in [e["id"] for e in menu["topBar"]]


def test_no_page_keeps_an_admin_only_element_or_script(tmp_path):
    """admin-gate.js is what hid data-admin-only elements. Deleting it without removing
    them would have shown them to every visitor."""
    root = stage(tmp_path)
    psa.strip(str(root))
    for dp, _d, fs in os.walk(root):
        for f in fs:
            if f.endswith(".html"):
                s = psa.COMMENT.sub("", (open(os.path.join(dp, f), encoding="utf-8").read()))
                assert not psa.ADMIN_ONLY_TAG.search(s), f
                for n in SCRIPTS:
                    assert ('js/%s.js' % n) not in s, (f, n)


def test_inert_stand_ins_keep_the_page_scripts_working(tmp_path):
    root = stage(tmp_path)
    psa.strip(str(root))
    tirtha = (root / "tirtha" / "index.html").read_text(encoding="utf-8")
    assert '<input type="hidden" id="conf" value="">' in tirtha
    dasa = (root / "dasa-sahitya" / "index.html").read_text(encoding="utf-8")
    assert "getElementById('sourcesDetail')" not in dasa


def test_the_build_refuses_when_a_block_has_moved(tmp_path):
    root = stage(tmp_path)
    p = root / "render.html"
    p.write_text(p.read_text(encoding="utf-8").replace('data-topbar="admin"', 'data-topbar="adm1n"'), encoding="utf-8")
    problems = psa.strip(str(root))
    assert any("not found" in x for x in problems), problems


def test_remove_balanced_handles_nesting():
    html = 'a<div class="x"><div>in</div><div>in2</div></div>b'
    assert psa.remove_balanced(html, '<div class="x">') == "ab"


def test_remove_admin_only_elements_nested_and_ignores_comments():
    html = ('<p>keep</p><!-- data-admin-only in a comment --><div data-admin-only>'
            '<div>inner</div></div><span>keep2</span><a data-admin-only="super" href="x">gone</a>')
    out, n = psa.remove_admin_only_elements(html)
    assert n == 2
    assert "keep" in out and "keep2" in out and "gone" not in out and "inner" not in out
    assert "<!-- data-admin-only in a comment -->" in out
