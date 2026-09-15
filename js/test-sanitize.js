// Plain-Node test for dge-sanitize.js (run: node js/test-sanitize.js), in this
// project's established no-framework pattern.
//
// The cases are the real ones found by scanning the corpus, not invented:
// the Anandamakaranda pramana spans and the Boray Gita divs that must survive,
// the Siddhanta Kaumudi's <{SK121}> citations and the Dayabhaga's <९> marks
// that are being eaten today, and Keith's "&c." ampersands.
global.window = {};
require('./dge-sanitize.js');
const S = global.window.DGESanitize;

let failures = 0;
function assert(cond, msg) {
  if (cond) { console.log('  ok   ' + msg); }
  else { failures++; console.log('  FAIL ' + msg); }
}
function eq(got, want, msg) {
  assert(got === want, msg + (got === want ? '' : '\n         got:  ' + got + '\n         want: ' + want));
}

console.log('markup the corpus actually relies on survives:');
eq(S.body('<span class="gr-blockquote">x</span>'),
   '<span class="gr-blockquote">x</span>', 'Anandamakaranda pramana span kept with its class');
eq(S.body('<div class="gita-iast"><em>yatra</em></div>'),
   '<div class="gita-iast"><em>yatra</em></div>', 'Boray Gita div + em kept');
eq(S.body('a<br/>b'), 'a<br/>b', 'self-closing br kept');
eq(S.body('a<br>b'), 'a<br/>b', 'bare br normalised to self-closing');
eq(S.body('<b>Comments:</b>'), '<b>Comments:</b>', 'bold kept');

console.log('\ncontent the browser is eating today becomes visible:');
eq(S.body('खरि चे <{SK121}>ति'), 'खरि चे &lt;{SK121}&gt;ति',
   'Siddhanta Kaumudi sutra citation survives instead of vanishing');
eq(S.body('विभागः । <९> विशेषेण'), 'विभागः । &lt;९&gt; विशेषेण',
   'Dayabhaga section mark survives');
eq(S.body('the scorpion, &c. Thou art'), 'the scorpion, &amp;c. Thou art',
   'bare ampersand escaped rather than left to browser recovery');
eq(S.body('&amp; and &#x27; and &gt;'), '&amp; and &#x27; and &gt;',
   'real entities are left exactly as they are');

console.log('\nanything that could carry behaviour is neutralised:');
eq(S.body('<script>alert(1)</script>'), '&lt;script&gt;alert(1)&lt;/script&gt;',
   'script tag inert');
eq(S.body('<span onclick="alert(1)">x</span>'), '<span>x</span>',
   'event handler dropped from a tag we keep');
// The OPENING tag fails the strict form and is escaped; the closing tag is a
// valid allowed tag and is kept. A stray </span> is inert -- it cannot carry
// behaviour -- so this is the safe outcome, not a gap.
eq(S.body('<span onclick=alert(1)>x</span>'), '&lt;span onclick=alert(1)&gt;x</span>',
   'unquoted attribute: opening tag escaped, handler never reaches the DOM');
eq(S.body('<img src=x onerror="alert(1)">'), '&lt;img src=x onerror="alert(1)"&gt;',
   'img is not on the list');
eq(S.body('<span class="a\\"onmouseover=\\"alert(1)">x</span>'.replace(/\\"/g, '"')),
   '&lt;span class="a"onmouseover="alert(1)"&gt;x</span>',
   'a class value that breaks out of its quotes escapes the whole opening tag');
eq(S.body('<span class="js-x">y</span>'), '<span class="js-x">y</span>',
   'ordinary class value passes');
eq(S.body('<span class="a<b">y</span>'), '&lt;span class="a&lt;b"&gt;y</span>',
   'a < inside an attribute value is not a valid tag form');

console.log('\nplain text is untouched:');
eq(S.body('रामः गच्छति'), 'रामः गच्छति', 'Devanagari with no markup unchanged');
eq(S.body('a\nb'), 'a\nb', 'newlines preserved for the later \\n -> <br> step');
eq(S.body(''), '', 'empty string');
eq(S.body(null), '', 'null does not throw');
// A '>' with no '<' anywhere cannot open anything, so the browser already
// renders it as text. Leaving it alone matters: 609,972 of them are the ' > '
// separators in breadcrumbs, and escaping every one would be churn for a
// character that was never at risk.
eq(S.body('a > b'), 'a > b', 'lone > left alone -- inert, and the breadcrumb separator');
eq(S.body('<b>a</b> > c'), '<b>a</b> &gt; c', 'but once a tag is present, > is escaped too');

console.log('\nidempotence (it may run twice without doubling):');
const once = S.body('<span class="x">a &c. <{SK1}></span>');
eq(S.body(once), once, 'sanitising an already-sanitised string is a no-op');

console.log(failures === 0 ? '\nALL PASSED' : '\n' + failures + ' FAILED');
process.exit(failures === 0 ? 0 : 1);
