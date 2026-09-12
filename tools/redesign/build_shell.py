#!/usr/bin/env python3
"""Phase 9 of the DGE frontend redesign: bake <dge-footer>/<dge-breadcrumb>
custom elements to static markup at build time, closing the
":not(:defined)" FOUC gap Phase 2 accepted as a stated trade-off (dge-
shell.js's own header comment) instead of standing up a real build
pipeline for it.

Ports dge/js/dge-shell.js's footerLinks()/renderFooterLinks() and
dge/js/dge-breadcrumb.js's DgeBreadcrumb.connectedCallback() -- same
branches, same output -- rather than re-deriving the markup, so this stays
in lockstep with what the browser would render. Both custom elements
already guard `if (childElementCount) return`, so baked-in children make
the runtime scripts a no-op on these pages: the <script> tags stay in
place as a safety net for any page authored with an empty tag later, not
removed.

Usage:
    python3 tools/redesign/build_shell.py            # bake, report what changed
    python3 tools/redesign/build_shell.py --check     # fail (exit 1) if baking
                                                       # would change any file --
                                                       # the CI drift gate

Deliberately conservative (Phase 9's "written in place, not a dist/
mirror" scope): this writes fully rendered markup into the SAME dge/**/*.html
files the site already ships, once. It does not introduce a bundler, a
templating language, or a separate output directory -- every page keeps
working exactly as it does today (site-footer.js pages, admin pages, and
any page not yet migrated onto <dge-footer>/<dge-breadcrumb> are untouched)
and gains a build-time snapshot CI can catch drift against.
"""
import html
import posixpath
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

SCRIPT_SRC_RE = re.compile(r'<script\b[^>]*\bsrc=["\']([^"\']+)["\']', re.IGNORECASE)
BREADCRUMB_RE = re.compile(r'<dge-breadcrumb\b([^>]*)>(.*?)</dge-breadcrumb>', re.IGNORECASE | re.DOTALL)
FOOTER_RE = re.compile(r'<dge-footer\b([^>]*)>(.*?)</dge-footer>', re.IGNORECASE | re.DOTALL)
ATTR_RE = re.compile(r'([a-zA-Z][a-zA-Z\-]*)(?:\s*=\s*"([^"]*)")?')
COMMENT_RE = re.compile(r'<!--.*?-->', re.DOTALL)


def mask_comments(text):
    """Several of these pages' own HTML comments mention "<dge-footer>" or
    "<dge-breadcrumb>" as prose (documenting the tag, not being it) --
    e.g. index.html's "<!-- Phase 6 ... <dge-footer> (dge-shell.js) -- same
    link sets ... -->" directly above the real, empty tag. A naive regex
    over the raw file matches that prose "<dge-footer>" first and then
    swallows everything up to the real </dge-footer>, reading it as
    already-baked and silently skipping the page. Matching against a
    same-length, comment-blanked copy instead (real markup is never inside
    a comment) keeps every span valid against the ORIGINAL text, so
    replacements still slice the real file correctly."""
    return COMMENT_RE.sub(lambda m: 'C' * len(m.group(0)), text)

LICENSE_URL = 'https://github.com/Tribhuvanachar/bhumandala/blob/main/LICENSE'
DEFAULT_CONTACT_EMAIL = 'sanatanavidyagurukulam@gmail.com'  # see contact-email.js: the
# async config-overrides.json fetch it starts can never beat this element's
# synchronous first (and only) render, so the live JS always bakes this same
# fallback in practice -- matched here, not "fixed", to stay a faithful port.


def esc(s):
    """dge-shell.js's/dge-breadcrumb.js's esc() -- HTML-escape a decoded string."""
    if s is None:
        return ''
    return (str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            .replace('"', '&quot;').replace("'", '&#39;'))


def parse_attrs(attrs_str):
    """getAttribute() equivalent: HTML-decode each value, matching what the
    browser hands the custom element's JS (attributes are stored decoded).
    A bare attribute (no "=...", e.g. the `deva` boolean) gets True -- using
    finditer rather than findall so an unmatched optional group comes back
    as None, not findall's empty-string stand-in, which would be
    indistinguishable from a real attr="" value."""
    attrs = {}
    for m in ATTR_RE.finditer(attrs_str):
        name, value = m.group(1), m.group(2)
        attrs[name.lower()] = html.unescape(value) if value is not None else True
    return attrs


def discover_pages():
    pages = [REPO_ROOT / "index.html"]
    pages.extend(sorted((REPO_ROOT / "dge").rglob("*.html")))
    return pages


def landing_page_url(page_text):
    """Faithful port of dge-shell.js's LANDING_PAGE_URL: new URL('../../index.html',
    <the dge-shell.js script's own resolved URL>). Computed purely from the
    script src the page itself uses to load dge-shell.js, so it's correct
    regardless of how deep the page sits."""
    m = re.search(r'<script\b[^>]*\bsrc=["\']([^"\']*dge-shell\.js[^"\']*)["\']', page_text, re.IGNORECASE)
    if not m:
        return None
    script_src = m.group(1).split('?')[0]
    script_dir = posixpath.dirname(script_src)
    target = posixpath.normpath(posixpath.join(script_dir, '../../index.html')) if script_dir \
        else posixpath.normpath('../../index.html')
    return target


def has_reader_modals(page_text):
    """typeof window.openAboutModal === 'function' && typeof window.openModal
    === 'function' -- both are defined only by modals.js, so this collapses
    to "does this page load modals.js" (a page either loads it, defining
    both, or loads neither)."""
    return bool(re.search(r'<script\b[^>]*\bsrc=["\'][^"\']*modals\.js[^"\']*["\']', page_text, re.IGNORECASE))


def footer_links(page_text):
    if has_reader_modals(page_text):
        return [
            {'label': 'About Us', 'onclick': "window.openAboutModal()"},
            {'label': 'Contact Us', 'onclick': "window.openModal('contactModal')"},
            {'label': 'Credits', 'onclick': "window.openAboutModal()"},
            {'label': 'License', 'onclick': "window.openModal('licenseModal')"},
            {'label': 'Terms &amp; Conditions', 'onclick': "window.openModal('termsModal')"},
        ]
    has_architect = bool(re.search(r'\bid\s*=\s*"architect"', page_text, re.IGNORECASE))
    if has_architect:
        about_href = '#architect'
    else:
        landing = landing_page_url(page_text) or 'index.html'
        about_href = landing + '#architect'
    return [
        {'label': 'About Us', 'href': about_href},
        {'label': 'Contact Us', 'href': 'mailto:' + DEFAULT_CONTACT_EMAIL},
        {'label': 'License', 'href': LICENSE_URL, 'external': True},
        {'label': 'Terms &amp; Conditions', 'onclick': 'window.dgeShowTermsNotice()'},
    ]


def render_footer_links(page_text):
    parts = []
    for i, l in enumerate(footer_links(page_text)):
        sep = '<span class="footer-sep">·</span>' if i else ''
        if l.get('href'):
            target = ' target="_blank" rel="noopener"' if l.get('external') else ''
            el = '<a class="footer-link" href="' + l['href'] + '"' + target + '>' + l['label'] + '</a>'
        else:
            el = '<button class="footer-link" onclick="' + l['onclick'] + '">' + l['label'] + '</button>'
        parts.append(sep + el)
    return ''.join(parts)


def render_breadcrumb(attrs):
    home_href = attrs.get('home-href') or 'index.html'
    home_label = attrs.get('home-label') or '⌂ DGE'
    parent_label = attrs.get('parent-label')
    parent_href = attrs.get('parent-href')
    label = attrs.get('label') or ''
    is_deva = 'deva' in attrs

    parent_class = ' class="deva"' if is_deva else ''
    out = '<a href="' + esc(home_href) + '" title="DGE Home">' + esc(home_label) + '</a>'
    if parent_label:
        out += '<span aria-hidden="true">›</span>'
        if parent_href:
            out += '<a href="' + esc(parent_href) + '"' + parent_class + '>' + esc(parent_label) + '</a>'
        else:
            out += '<span' + parent_class + '>' + esc(parent_label) + '</span>'
    out += '<span aria-hidden="true">›</span>'
    out += ('<span class="deva">' + esc(label) + '</span>') if is_deva \
        else ('<span>' + esc(label) + '</span>')
    return out


def apply_over_real_tags(pattern, page_text, masked_text, render):
    """Find `pattern` in masked_text (comments blanked, so only real tags
    match) but build the replacement text by slicing page_text at the same
    spans -- mask_comments() preserves length exactly, so every span from a
    masked_text match lines up with the identical span in page_text.
    `render(attrs_str)` returns the new tag or None to leave a match
    untouched (already baked)."""
    changed = False
    out = []
    last = 0
    for m in pattern.finditer(masked_text):
        attrs_str = m.group(1)
        inner = page_text[m.start(2):m.end(2)]
        if inner.strip():
            continue  # already baked -- leave this span exactly as it is
        replacement = render(attrs_str)
        out.append(page_text[last:m.start()])
        out.append(replacement)
        last = m.end()
        changed = True
    out.append(page_text[last:])
    return ''.join(out), changed


def bake(page_text):
    masked = mask_comments(page_text)
    rendered_footer_links = None  # computed lazily, once, from the ORIGINAL page text

    def render_breadcrumb_tag(attrs_str):
        attrs = parse_attrs(attrs_str)
        return '<dge-breadcrumb' + attrs_str + ' class="brand">' + render_breadcrumb(attrs) + '</dge-breadcrumb>'

    def render_footer_tag(attrs_str):
        nonlocal rendered_footer_links
        if rendered_footer_links is None:
            rendered_footer_links = render_footer_links(masked)
        return '<dge-footer' + attrs_str + ' class="site-footer-links">' + rendered_footer_links + '</dge-footer>'

    out, changed_bc = apply_over_real_tags(BREADCRUMB_RE, page_text, masked, render_breadcrumb_tag)
    masked = mask_comments(out)  # `out` may differ in length from page_text now; re-derive before the next pass
    out, changed_footer = apply_over_real_tags(FOOTER_RE, out, masked, render_footer_tag)
    return out, (changed_bc or changed_footer)


def main():
    check_mode = '--check' in sys.argv
    touched = []
    for page in discover_pages():
        text = page.read_text(encoding='utf-8')
        if '<dge-footer' not in text and '<dge-breadcrumb' not in text:
            continue
        new_text, changed = bake(text)
        if not changed:
            continue
        rel = page.relative_to(REPO_ROOT).as_posix()
        touched.append(rel)
        if not check_mode:
            page.write_text(new_text, encoding='utf-8')

    if check_mode:
        if touched:
            print("build_shell --check: these pages have un-baked <dge-footer>/<dge-breadcrumb> "
                  "tags -- run `python3 tools/redesign/build_shell.py` and commit the result:")
            for t in touched:
                print(f"  - {t}")
            return 1
        print("build_shell --check: OK -- every <dge-footer>/<dge-breadcrumb> tag is baked and in sync")
        return 0

    if touched:
        print(f"build_shell: baked {len(touched)} page(s):")
        for t in touched:
            print(f"  - {t}")
    else:
        print("build_shell: nothing to bake -- every tag already up to date")
    return 0


if __name__ == '__main__':
    sys.exit(main())
