// DGE Module: dge-sanitize.js
// Body text reaches the page through innerHTML, and it has always reached it
// unescaped. That is deliberate: importers put markup in there -- 17,086 tags
// across the corpus, and a scan says they are exactly five, span/div/br/b/em,
// carrying the pramana citations from an id-addressed shelf and the Boray
// Gita layout.
// Escaping the lot would destroy real styling.
//
// The exposure is anything else that starts with '<' followed by a letter.
// Measured in a browser: "a<b इति" renders as "a" -- everything from the '<'
// onward is silently gone, with no error and nothing on the page to suggest
// text is missing. In a grammar text discussing sandhi that is an ordinary
// thing for a content editor to type.
//
// Nothing in the corpus is damaged today: every one of those 17,086 is one of
// the five intentional tags. The 2,374 remaining '<' are things like the
// Siddhanta Kaumudi's <{SK121}> sutra citations and the Dayabhaga's <९> marks,
// and those are safe as they stand -- HTML only starts a tag when a letter
// follows the '<', so a browser already shows them as text. This is a guard
// against what an editor or an OCR pass may introduce, not a repair.
//
// So: keep the tags the corpus uses, escape everything else. A stray '<'
// survives to the page instead of taking the rest of the line with it, "&c."
// stops depending on browser recovery, and a <script> is inert.
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

  // Opt-in inline markup, applied AFTER body() so it only ever sees text that
  // is already safe. Off unless a file asks for it by carrying
  //   "markup": "dge_inline_v1"
  // and that gate is not caution for its own sake: '*' occurs 6,305 times in
  // the corpus as an editorial mark -- the Satapatha Brahmana uses it -- and
  // reading every one of those as italic would silently mangle thousands of
  // passages in texts nobody had touched. A work opts in when someone has
  // looked at it.
  //
  // Same syntax as gold-render.js, deliberately: an editor should not have to
  // learn two dialects depending on which commentary they are in.
  const MARKUP_FLAG = 'dge_inline_v1';

  function inline(safeHtml) {
    if (typeof safeHtml !== 'string' || safeHtml.indexOf('*') < 0) return safeHtml;
    return safeHtml
      .replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>')
      .replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, '$1<em>$2</em>');
  }

  // The one call render.js makes: sanitise always, style only if asked.
  function render(text, markupFlag) {
    const safe = body(text);
    return markupFlag === MARKUP_FLAG ? inline(safe) : safe;
  }

  return { body: body, inline: inline, render: render, escapeText: escapeText,
           MARKUP_FLAG: MARKUP_FLAG, ALLOWED_TAGS: ALLOWED_TAGS };
})();

window.DGESanitize = DGESanitize;
