#!/usr/bin/env python3
"""
check_content.py — refuse to ship a page whose text is missing.

Pages carry no words of their own; each one's prose is a file under
admin/content/ and its switches a file under admin/config/. That is what makes
them editable without touching markup, and it means a page is only as sound as
its files. A typo that drops a key does not fail loudly at build time — it
fails on a visitor's screen.

So this checks, before anything is pushed, that every page's files parse and
carry the keys that page actually reads. It is deliberately not clever: the
required keys are listed here by hand, because the point is to notice when the
page and its data drift apart, and deriving the list from the page would move
in lockstep with the drift.

    python3 tools/check_content.py          # report, exit 1 on any problem

Add a page by adding an entry to PAGES.
"""

import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PAGES = {
    'home': {
        'page': 'index.html',
        'content': ('admin/content/home.json',
                    ['brand', 'guru', 'vandana', 'labels', 'sections', 'panels', 'footer']),
        'config': ('admin/config/home.json',
                   ['enterUrl', 'requireOffering', 'minOfferings', 'passKey',
                    'photo', 'flowers', 'pranam']),
    },
}

# Keys nested inside a required one, where the page reads them directly and a
# missing one is just as fatal.
NESTED = {
    'admin/content/home.json': {
        'brand': ['latin', 'tagline'],
        'guru': ['nameSanskrit', 'nameLatin', 'title', 'moreLabel'],
        'vandana': ['sanskrit', 'transliteration'],
        'labels': ['hint', 'offerButton', 'pranamButton', 'enterLocked',
                   'enterReady', 'sectionsCue', 'readMore', 'readLess'],
        'footer': ['lines'],
    },
    'admin/config/home.json': {
        'photo': ['src', 'frameRatio'],
        'flowers': ['maxSettled'],
        'pranam': ['count'],
    },
}


def check_file(rel, required, problems):
    path = os.path.join(REPO, rel)
    if not os.path.exists(path):
        problems.append(f'{rel}: missing')
        return None
    try:
        with open(path, encoding='utf-8') as fh:
            doc = json.load(fh)
    except ValueError as e:
        problems.append(f'{rel}: not valid JSON — {e}')
        return None
    for key in required:
        if doc.get(key) is None:
            problems.append(f'{rel}: missing "{key}"')
    for parent, kids in NESTED.get(rel, {}).items():
        node = doc.get(parent)
        if not isinstance(node, dict):
            continue
        for k in kids:
            if node.get(k) is None:
                problems.append(f'{rel}: missing "{parent}.{k}"')
    return doc


def check_home(content, problems):
    """The landing page's own shape, beyond the flat key list.

    Every section names a Know More panel, and a name with no panel behind it
    renders a button that opens nothing — the kind of break that looks fine
    until someone taps it.
    """
    if not content:
        return
    panels = content.get('panels') or {}
    for i, sec in enumerate(content.get('sections') or []):
        where = f'sections[{i}]'
        for k in ('id', 'name'):
            if not sec.get(k):
                problems.append(f'admin/content/home.json: {where} has no "{k}"')
        panel = sec.get('panel')
        if panel and panel not in panels:
            problems.append(f'admin/content/home.json: {where} opens panel '
                            f'"{panel}", which does not exist')
    for name, p in panels.items():
        if not p.get('title'):
            problems.append(f'admin/content/home.json: panel "{name}" has no title')
    lines = (content.get('footer') or {}).get('lines')
    if isinstance(lines, list) and not lines:
        problems.append('admin/content/home.json: footer.lines is empty')


def main():
    problems = []
    for page, spec in PAGES.items():
        page_path = os.path.join(REPO, spec['page'])
        if not os.path.exists(page_path):
            problems.append(f'{spec["page"]}: missing')
        crel, ckeys = spec['content']
        grel, gkeys = spec['config']
        content = check_file(crel, ckeys, problems)
        check_file(grel, gkeys, problems)
        if page == 'home':
            check_home(content, problems)
        print(f'  {page:6} {spec["page"]}  ←  {crel}, {grel}')

    if problems:
        print('\n' + str(len(problems)) + ' problem(s):', file=sys.stderr)
        for p in problems:
            print('  ' + p, file=sys.stderr)
        print('\nThe pages read these files at runtime and have no copy of their\n'
              'own text, so shipping this would show a visitor an error page.',
              file=sys.stderr)
        return 1
    print('\nall pages have their text')
    return 0


if __name__ == '__main__':
    sys.exit(main())
