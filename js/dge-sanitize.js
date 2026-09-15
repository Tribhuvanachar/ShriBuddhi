// DGE Module: dge-sanitize.js
// Body text reaches the page through innerHTML, and it has always reached it
// unescaped. That is not an oversight -- importers deliberately put markup in
// there: 17,086 tags across the corpus, span/div/br/b/em and nothing else,
// carrying the Anandamakaranda pramana citations and the Boray Gita layout.
// Escaping it all would destroy that.
//
// But unescaped means the browser reads EVERY '<' as a tag, and 2,374 of them
// are not tags. The Siddhanta Kaumudi cites its own sutras as <{SK121}>, so a
// reader sees "खरि चे ति चर्त्त्वे" -- the citation silently eaten and the
// sandhi broken across the gap. The Dayabhaga's <९> section marks vanish the
// same way. And a content editor who types '<' loses whatever follows it.
//
// So: keep the tags the corpus actually uses, escape everything else. The
// citation becomes visible, a stray '<' survives, '&c.' stops being a
// half-entity, and a <script> is inert.
window.DGE_VERSIONS = window.DGE_VERSIONS || {};
window.DGE_VERSIONS['dge-sanitize.js'] = 'v1.0 (whitelist sanitiser for body text on the innerHTML path)';

const DGESanitize = (function () {
  // Grounded in a scan of the whole corpus, not in guesswork: these five are
  // every tag that occurs in body text. i/strong/sup/sub are allowed too --
  // they are the obvious equivalents an editor would reach for, and refusing
  // them would only teach people that markup is unreliable here.
  const ALLOWED_TAGS = {
    span: 1, div: 1, br: 1, b: 1, i: 1, em: 1, strong: 1, sup: 1, sub: 1
  };
  // class is the only attribute in the corpus (6,487 of them) and the only one
  // that cannot carry behaviour. Everything else is dropped, which is what
  // makes an onclick harmless even on a tag we keep.
  const ALLOWED_ATTRS = { 'class': /^[A-Za-z0-9 _-]*$/ };

  // A tag is kept only in its strict form: a name, then quoted attributes.
  // Anything sloppier -- an unquoted value, a stray '<' -- fails to match and
  // is escaped as text, which is the safe direction to fail in.
  const TAG = /<(\/?)([A-Za-z][A-Za-z0-9]*)((?:\s+[A-Za-z-]+\s*=\s*"[^"<>]*")*)\s*(\/?)>/g;
  const ATTR = /([A-Za-z-]+)\s*=\s*"([^"<>]*)"/g;
  // A bare '&' is escaped; a real entity is left as it stands, so the corpus's
  // 100 deliberate entities survive and its 2,468 bare ampersands ("&c.", in
  // Keith's translation) stop depending on browser recovery.
  const BARE_AMP = /&(?!(?:#\d+|#x[0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]*);)/g;

  function escapeText(s) {
    return s.replace(BARE_AMP, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function rebuild(m) {
    const closing = m[1], name = m[2].toLowerCase(), attrs = m[3] || '', selfClose = m[4];
    if (closing) return '</' + name + '>';
    let kept = '';
    ATTR.lastIndex = 0;
    let a;
    while ((a = ATTR.exec(attrs)) !== null) {
      const an = a[1].toLowerCase(), av = a[2];
      const rule = ALLOWED_ATTRS[an];
      if (rule && rule.test(av)) kept += ' ' + an + '="' + av + '"';
    }
    return '<' + name + kept + (selfClose || name === 'br' ? '/' : '') + '>';
  }

  // The only entry point. Returns HTML safe to assign to innerHTML.
  function body(html) {
    if (typeof html !== 'string' || (html.indexOf('<') < 0 && html.indexOf('&') < 0)) {
      return typeof html === 'string' ? html : '';
    }
    let out = '', last = 0, m;
    TAG.lastIndex = 0;
    while ((m = TAG.exec(html)) !== null) {
      if (!ALLOWED_TAGS[m[2].toLowerCase()]) continue;   // fall through: escaped as text
      out += escapeText(html.slice(last, m.index)) + rebuild(m);
      last = m.index + m[0].length;
    }
    return out + escapeText(html.slice(last));
  }

  return { body: body, escapeText: escapeText, ALLOWED_TAGS: ALLOWED_TAGS };
})();

window.DGESanitize = DGESanitize;
