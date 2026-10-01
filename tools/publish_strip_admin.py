#!/usr/bin/env python3
"""
publish_strip_admin.py -- take every admin entry point out of the STAGED copy.

THE RULE, as the lead set it on 30 Sep 2026: anything to do with administration
lives only in ShriBuddhi. The public site (Jagat) has no admin menu, no admin
pages, no admin passkey prompts and none of the scripts behind them. It had
one left: the "Admin Tools" button in the top-right menu, and its Access
(passkey) sibling.

WHAT IT DOES, to the staged copy only. The source keeps everything, because
that is where the admin works.

  1. Deletes the admin-only scripts (and their stylesheet) and every tag that loads them.
  2. Removes, from render.html, the Admin Tools and Access menus, the four admin
     modals (Repo Files, Site Settings, Manage Users, AI Keys & Features), the
     content-edit quick action and the admin-only library toggle.
  3. Removes every element marked data-admin-only from every page. admin-gate.js
     used to hide those at runtime (it injects `[data-admin-only]{display:none}`),
     so deleting the script alone would have SHOWN them to everyone. Two of them
     are read by their page's own script, so they become inert stand-ins instead
     (see EXACT below).
  4. Removes the admin and access entries from config/menu.json.
  5. Refuses to finish if any of those markers is still present.

NOT touched, on purpose: js/role-access.js and js/user-auth.js. They are not admin UI.
role-access.js enforces the go-live shelf and role gates on every reader, and user-auth.js
is sign-in. (js/user-roles.js, the Manage Users code, WAS being shipped until 1 Oct 2026 and
is now removed with the other admin scripts: it defines nothing the public pages call.
Roles live in Firestore and are managed from ShriBuddhi; a grant takes effect on Jagat at
once because both read the same project.) The
admin functions the remaining public code still names are all guarded
(`typeof ... === 'function'`, `&&`, a ternary), which is checked by
tests/test_publish_strip_admin.py and by loading the staged pages in a browser.

    python3 tools/publish_strip_admin.py --staged /tmp/jagat
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

# Scripts that exist only to give an administrator something to click.
ADMIN_SCRIPTS = ("admin-editor", "admin-remote", "config-editor",
                 "content-editor", "preview-mode", "admin-gate",
                 # added 1 Oct 2026: the inline page-text editor (it takes a GitHub token) and the
                 # Manage Users code, whose modal was already cut but whose script still shipped.
                 "content-inline", "user-roles")

# Stylesheets that exist only for those scripts: the <link> and the file both go.
ADMIN_STYLES = ("content-inline",)

# (file, exact opening tag) of each element to cut from the staged markup. The
# element is removed together with everything up to its matching close tag.
BLOCKS = {
    "render.html": [
        '<div style="position:relative;" data-topbar="admin">',
        '<div style="position:relative;" data-topbar="access">',
        '<div class="modal-overlay" id="userRolesModal">',
        '<div class="modal-overlay" id="configEditorModal">',
        '<div class="modal-overlay" id="adminEditorModal">',
        '<div class="modal-overlay" id="keyModal">',
        '<div class="pop-item" id="ciEditPopItem"',
        '<div class="range-row-flex" style="margin-bottom:10px;" data-admin-only>',
        '<div id="contentEditorMount" class="content-editor-mount">',
    ],
}

# Exact-string replacements, each of which must match exactly once. The elements
# below are data-admin-only but their page's script reads them, so deleting them
# would throw; each is swapped for something inert. Runs BEFORE the generic
# data-admin-only removal.
EXACT = {
    # select#conf is the "any confidence" filter; .value of a hidden input is ''
    # which is the same "Any confidence" the select defaults to.
    "tirtha/index.html": [
        ('<select id="conf" data-admin-only><option value="">Any confidence</option>'
         '<option value="high">High</option><option value="medium">Medium</option>'
         '<option value="low">Low</option></select>',
         '<input type="hidden" id="conf" value="">'),
    ],
    # The script fills this with the names of the external sites the data was
    # compiled from. Give it a plain object to write into instead of the page.
    "dasa-sahitya/index.html": [
        ("document.getElementById('sourcesDetail')", "{}"),
    ],
}

# What must be gone from the staged HTML when this finishes.
MARKERS = ("adminToolsBtn", "adminToolsPopup", "accessKeyBtn", "accessPopup",
           'data-topbar="admin"', 'data-topbar="access"',
           "userRolesModal", "configEditorModal", "adminEditorModal", "keyModal",
           "ciEditPopItem", "contentEditorMount", "content-inline.css")

ADMIN_ONLY_TAG = re.compile(r"<([A-Za-z][A-Za-z0-9]*)\b[^>]*\bdata-admin-only\b[^>]*>")
COMMENT = re.compile(r"<!--.*?-->", re.S)

TAG = re.compile(r"<(/?)div\b[^>]*>", re.I)


def remove_balanced(html: str, opening: str) -> str:
    """Cut the <div> that starts with `opening`, through its matching </div>."""
    start = html.find(opening)
    if start < 0:
        raise ValueError("not found: %s" % opening)
    if html.find(opening, start + 1) >= 0:
        raise ValueError("found more than once: %s" % opening)
    depth = 0
    for m in TAG.finditer(html, start):
        depth += -1 if m.group(1) else 1
        if depth == 0:
            end = m.end()
            # take the line's trailing newline too, so no blank line is left
            if html[end:end + 1] == "\n":
                end += 1
            return html[:start].rstrip(" \t") + html[end:]
    raise ValueError("unbalanced <div> after: %s" % opening)


def remove_admin_only_elements(html: str) -> tuple[str, int]:
    """Cut every element carrying data-admin-only, through its matching close tag."""
    count = 0
    while True:
        m = ADMIN_ONLY_TAG.search(COMMENT.sub(lambda c: " " * len(c.group(0)), html))
        if not m:
            return html, count
        name = m.group(1)
        start = m.start()
        depth = 0
        end = None
        for t in re.finditer(r"<(/?)%s\b[^>]*>" % re.escape(name), html[start:], re.I):
            depth += -1 if t.group(1) else 1
            if depth == 0:
                end = start + t.end()
                break
        if end is None:
            raise ValueError("unbalanced <%s> carrying data-admin-only" % name)
        if html[end:end + 1] == "\n":
            end += 1
        html = html[:start] + html[end:]
        count += 1


def script_tag_re(name: str):
    return re.compile(
        r'[ \t]*<script\b[^>]*\bsrc="[^"]*\bjs/%s\.js[^"]*"[^>]*>\s*</script>[ \t]*\n?' % re.escape(name),
        re.I)


def html_files(root):
    for dp, _d, fs in os.walk(root):
        for f in fs:
            if f.endswith(".html"):
                yield os.path.join(dp, f)


def strip(staged: str) -> list[str]:
    problems: list[str] = []

    # 1. scripts: tags first, then the files
    removed_tags = 0
    for path in html_files(staged):
        s = open(path, encoding="utf-8").read()
        t = s
        for name in ADMIN_SCRIPTS:
            t, n = script_tag_re(name).subn("", t)
            removed_tags += n
        if t != s:
            open(path, "w", encoding="utf-8").write(t)
    for path in html_files(staged):
        t = u = open(path, encoding="utf-8").read()
        for name in ADMIN_STYLES:
            t = re.sub(r'[ \t]*<link\b[^>]*\bhref="[^"]*\bcss/%s\.css[^"]*"[^>]*>[ \t]*\n?' % re.escape(name), "", t, flags=re.I)
        if t != u:
            open(path, "w", encoding="utf-8").write(t)
    for name in ADMIN_STYLES:
        sp = os.path.join(staged, "css", name + ".css")
        if os.path.exists(sp):
            os.remove(sp)
    deleted = 0
    for name in ADMIN_SCRIPTS:
        p = os.path.join(staged, "js", name + ".js")
        if os.path.exists(p):
            os.remove(p)
            deleted += 1
        else:
            problems.append("js/%s.js is not in the staged tree (already gone, or renamed?)" % name)

    # 2. markup blocks
    for rel, openings in BLOCKS.items():
        p = os.path.join(staged, rel)
        if not os.path.exists(p):
            problems.append("%s is not in the staged tree" % rel)
            continue
        s = open(p, encoding="utf-8").read()
        for opening in openings:
            try:
                s = remove_balanced(s, opening)
            except ValueError as e:
                problems.append("%s: %s" % (rel, e))
        open(p, "w", encoding="utf-8").write(s)

    # 2b. data-admin-only elements, on every page
    removed_admin_only = 0
    for rel, pairs in EXACT.items():
        p = os.path.join(staged, rel)
        if not os.path.exists(p):
            problems.append("%s is not in the staged tree" % rel)
            continue
        s = open(p, encoding="utf-8").read()
        for old, new in pairs:
            if s.count(old) != 1:
                problems.append("%s: expected exactly one of %r, found %d" % (rel, old[:50], s.count(old)))
            else:
                s = s.replace(old, new)
        open(p, "w", encoding="utf-8").write(s)
    for path in html_files(staged):
        s = open(path, encoding="utf-8").read()
        try:
            t, n = remove_admin_only_elements(s)
        except ValueError as e:
            problems.append("%s: %s" % (os.path.relpath(path, staged), e))
            continue
        if n:
            removed_admin_only += n
            open(path, "w", encoding="utf-8").write(t)

    # 3. menu config
    mp = os.path.join(staged, "config", "menu.json")
    if os.path.exists(mp):
        d = json.load(open(mp, encoding="utf-8"))
        before = len(d.get("topBar", []))
        d["topBar"] = [e for e in d.get("topBar", []) if e.get("id") not in ("admin", "access")]
        d.pop("admin", None)
        if len(d["topBar"]) == before:
            problems.append("config/menu.json had no admin/access topBar entries to remove")
        with open(mp, "w", encoding="utf-8") as fh:
            json.dump(d, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
    else:
        problems.append("config/menu.json is not in the staged tree")

    # 4. nothing may be left
    for path in html_files(staged):
        s = COMMENT.sub("", open(path, encoding="utf-8").read())
        rel = os.path.relpath(path, staged)
        for mk in MARKERS:
            if mk in s:
                problems.append("%s still contains %r" % (rel, mk))
        if ADMIN_ONLY_TAG.search(s):
            problems.append("%s still has an element with data-admin-only" % rel)
        for name in ADMIN_SCRIPTS:
            if re.search(r'src="[^"]*js/%s\.js' % re.escape(name), s):
                problems.append("%s still loads js/%s.js" % (rel, name))
    if os.path.exists(mp):
        s = open(mp, encoding="utf-8").read()
        for mk in ('"adminToolsPopup"', '"id": "admin"', '"id": "access"'):
            if mk in s:
                problems.append("config/menu.json still contains %s" % mk)

    print("stripped admin from the staged tree: %d <script> tag(s), %d script file(s), %d markup block(s), %d data-admin-only element(s)"
          % (removed_tags, deleted, sum(len(v) for v in BLOCKS.values()), removed_admin_only))
    return problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 2)[1])
    ap.add_argument("--staged", required=True, help="the staged tree to rewrite in place")
    args = ap.parse_args(argv)
    problems = strip(args.staged)
    if problems:
        print("\nadmin is NOT fully out of the staged tree:", file=sys.stderr)
        for p in problems:
            print("  - " + p, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
