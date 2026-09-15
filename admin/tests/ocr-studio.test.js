// Tests for admin/js/ocr-studio-core.js — the document and style model behind
// the OCR studio.
//
// The design turns on one thing: a block keeps the tag the OCR gave it
// (srcTag) separately from the class we assign it (cls). srcTag is what "every
// other block like this one" means, so if anything ever edits it, bulk
// restyling silently starts hitting the wrong blocks. Several tests below
// exist only to pin that.
'use strict';

const { test, describe } = require('node:test');
const assert = require('node:assert/strict');

const S = require('../js/ocr-studio-core');

const PAGE = [
  '<h1>ईशावास्योपनिषत्</h1>',
  '<h2>प्रथमो मन्त्रः</h2>',
  '<p>ईशा वास्यमिदं सर्वम्</p>',
  '<blockquote>यत्किञ्च जगत्यां जगत्</blockquote>',
  '<h2>द्वितीयो मन्त्रः</h2>',
  '<p>कुर्वन्नेवेह कर्माणि</p>'
].join('\n');

describe('parseBlocks', () => {
  test('one block per OCR block tag, in order', () => {
    const b = S.parseBlocks(PAGE, 1);
    assert.equal(b.length, 6);
    assert.deepEqual(b.map((x) => x.srcTag), ['h1', 'h2', 'p', 'blockquote', 'h2', 'p']);
  });

  test('the inner markup is kept, not flattened to text', () => {
    const b = S.parseBlocks('<p>ईशा <b>वास्यम्</b> इदम्</p>', 1);
    assert.match(b[0].html, /<b>वास्यम्<\/b>/);
    assert.equal(b[0].text, 'ईशा वास्यम् इदम्');
  });

  test('text outside any block tag still becomes a block', () => {
    // OCR does emit bare lines. Dropping them loses content silently.
    const b = S.parseBlocks('loose line<p>in a block</p>trailing', 1);
    assert.deepEqual(b.map((x) => x.text), ['loose line', 'in a block', 'trailing']);
  });

  test('empty blocks are not carried', () => {
    assert.equal(S.parseBlocks('<p></p><p>  </p><p>real</p>', 1).length, 1);
  });

  test('every block gets an id and a starting class', () => {
    S.parseBlocks(PAGE, 1).forEach((b) => {
      assert.ok(b.id, 'needs an id');
      assert.ok(b.cls, 'needs a class');
    });
  });

  test('nothing in, nothing out', () => {
    assert.deepEqual(S.parseBlocks('', 1), []);
    assert.deepEqual(S.parseBlocks(null, 1), []);
  });
});

describe('classify', () => {
  test('the OCR tag decides the starting class', () => {
    assert.equal(S.classify('h1'), 'h1');
    assert.equal(S.classify('h2'), 'h2');
    assert.equal(S.classify('blockquote'), 'verse');
    assert.equal(S.classify('p'), 'body');
  });

  test('deeper headings fold into Heading 3 rather than inventing classes', () => {
    ['h3', 'h4', 'h5', 'h6'].forEach((t) => assert.equal(S.classify(t), 'h3'));
  });

  test('anything unrecognised is body, not a crash', () => {
    assert.equal(S.classify('span'), 'body');
    assert.equal(S.classify(''), 'body');
    assert.equal(S.classify(null), 'body');
  });
});

describe('docFromPages', () => {
  test('blocks from every page, with page numbers kept', () => {
    const d = S.docFromPages([{ page: 7, html: '<p>a</p>' }, { page: 8, html: '<p>b</p><p>c</p>' }]);
    assert.equal(d.blocks.length, 3);
    assert.deepEqual(d.blocks.map((b) => b.page), [7, 8, 8]);
  });

  test('block ids are unique across pages', () => {
    const d = S.docFromPages([{ page: 1, html: '<p>a</p>' }, { page: 2, html: '<p>b</p>' }]);
    assert.equal(new Set(d.blocks.map((b) => b.id)).size, 2);
  });

  test('a bare string page works too', () => {
    assert.equal(S.docFromPages(['<p>a</p>']).blocks.length, 1);
  });
});

describe('applying a class — the thing the studio is for', () => {
  const fresh = () => S.docFromPages([{ page: 1, html: PAGE }]);

  test("'like' restyles every block the OCR tagged the same way", () => {
    // Select ONE h2 and say "these are Heading 3" -- both h2s move, and
    // nothing else does.
    const d = fresh();
    const anH2 = d.blocks.find((b) => b.srcTag === 'h2');
    const n = S.applyClass(d, anH2.id, 'h3', 'like');
    assert.equal(n, 2);
    assert.deepEqual(d.blocks.filter((b) => b.cls === 'h3').map((b) => b.srcTag), ['h2', 'h2']);
    assert.equal(d.blocks.find((b) => b.srcTag === 'h1').cls, 'h1', 'the h1 must not move');
  });

  test("'one' moves only the block picked", () => {
    const d = fresh();
    const anH2 = d.blocks.find((b) => b.srcTag === 'h2');
    assert.equal(S.applyClass(d, anH2.id, 'colophon', 'one'), 1);
    assert.equal(d.blocks.filter((b) => b.cls === 'colophon').length, 1);
  });

  test("'all' moves the whole document", () => {
    const d = fresh();
    assert.equal(S.applyClass(d, d.blocks[0].id, 'body', 'all'), 4);
    assert.ok(d.blocks.every((b) => b.cls === 'body'));
  });

  test('it reports how many blocks actually changed, not how many it looked at', () => {
    const d = fresh();
    S.applyClass(d, d.blocks[0].id, 'body', 'all');
    assert.equal(S.applyClass(d, d.blocks[0].id, 'body', 'all'), 0, 'a no-op is 0');
  });

  test('an unknown class changes nothing', () => {
    const d = fresh();
    assert.equal(S.applyClass(d, d.blocks[0].id, 'not-a-class', 'all'), 0);
    assert.equal(d.blocks[0].cls, 'h1');
  });

  test('THE SOURCE TAG IS NEVER EDITED', () => {
    // If cls were written back over srcTag, a second bulk apply would hit a
    // different set of blocks than the first -- the operation would stop being
    // repeatable and nobody would know why.
    const d = fresh();
    const before = d.blocks.map((b) => b.srcTag).join(',');
    const anH2 = d.blocks.find((b) => b.srcTag === 'h2');
    S.applyClass(d, anH2.id, 'title', 'like');
    S.applyClass(d, anH2.id, 'note', 'like');
    assert.equal(d.blocks.map((b) => b.srcTag).join(','), before);
    assert.equal(d.blocks.filter((b) => b.cls === 'note').length, 2,
      'the second apply must hit the same two blocks as the first');
  });

  test('blocksLike ignores the current class entirely', () => {
    const d = fresh();
    const anH2 = d.blocks.find((b) => b.srcTag === 'h2');
    S.applyClass(d, anH2.id, 'body', 'one');          // now it looks like a paragraph
    assert.equal(S.blocksLike(d, anH2.id).length, 2, 'still grouped by what the OCR said');
  });
});

describe('counts', () => {
  test('every class is listed, including the empty ones', () => {
    const c = S.counts(S.docFromPages([{ page: 1, html: PAGE }]));
    assert.equal(c.h2, 2);
    assert.equal(c.body, 2);
    assert.equal(c.verse, 1);
    assert.equal(c.colophon, 0, 'an unused class still needs a row in the panel');
  });
});

describe('styles', () => {
  test('a rule carries the appearance, not the semantics', () => {
    const r = S.ruleFor({ size: 20, weight: 700, italic: true, align: 'center', before: 4, after: 6, indent: 8 });
    assert.match(r, /font-size:20px/);
    assert.match(r, /font-weight:700/);
    assert.match(r, /font-style:italic/);
    assert.match(r, /text-align:center/);
    assert.match(r, /margin:4px 0 6px 0/);
    assert.match(r, /padding-left:8px/);
  });

  test('an unset colour is simply absent rather than empty', () => {
    assert.ok(!/color:/.test(S.ruleFor({ size: 15, color: '' })));
    assert.match(S.ruleFor({ size: 15, color: '#900' }), /color:#900/);
  });

  test('the CSS is scoped so it cannot leak into the admin chrome', () => {
    const css = S.styleCss(S.defaultStyles(), '.doc');
    assert.ok(css.split('\n').every((l) => !l.trim() || l.startsWith('.doc ')));
  });

  test('every class has a semantic export tag', () => {
    const s = S.defaultStyles();
    Object.keys(s).forEach((k) => {
      assert.ok(/^(h[1-6]|p|blockquote|pre)$/.test(s[k].tag), k + ' needs a real tag');
      assert.ok(s[k].label, k + ' needs a label');
    });
  });
});

describe('exportHtml', () => {
  test('a block exports under its CLASS tag, not the tag the OCR gave it', () => {
    // This is what makes reclassification real rather than cosmetic.
    const d = S.docFromPages([{ page: 1, html: '<p>this is really a heading</p>' }]);
    S.applyClass(d, d.blocks[0].id, 'h2', 'one');
    const out = S.exportHtml(d, 'x');
    assert.match(out, /<h2 data-cls="h2">this is really a heading<\/h2>/);
    assert.ok(!/<p data-cls="h2">/.test(out));
  });

  test('the style table rides along, so it is a styled document not inline formatting', () => {
    const d = S.docFromPages([{ page: 1, html: PAGE }]);
    const out = S.exportHtml(d, 'ईशावास्य');
    assert.match(out, /<style>/);
    assert.match(out, /\[data-cls="h2"\]/);
    assert.ok(!/style="/.test(out), 'no inline style attributes');
  });

  test('the title is escaped', () => {
    assert.match(S.exportHtml(S.docFromPages([]), '<script>x</script>'),
      /<title>&lt;script&gt;/);
  });

  test('Devanagari survives the round trip', () => {
    const out = S.exportHtml(S.docFromPages([{ page: 1, html: PAGE }]), 'x');
    assert.match(out, /ईशावास्योपनिषत्/);
    assert.match(out, /यत्किञ्च जगत्यां जगत्/);
  });
});

describe('toMergeBlocks', () => {
  test('gives ocr_review_merge.py the html beside text it already reads', () => {
    const d = S.docFromPages([{ page: 3, html: '<h2>शीर्षकम्</h2>' }]);
    const m = S.toMergeBlocks(d);
    assert.equal(m.length, 1);
    assert.equal(m[0].page, 3);
    assert.equal(m[0].cls, 'h2');
    assert.equal(m[0].text, 'शीर्षकम्');
    assert.match(m[0].html, /^<h2 data-cls="h2">/);
  });

  test('reclassification reaches the merge path too', () => {
    const d = S.docFromPages([{ page: 1, html: '<p>a colophon line</p>' }]);
    S.applyClass(d, d.blocks[0].id, 'colophon', 'one');
    assert.match(S.toMergeBlocks(d)[0].html, /data-cls="colophon"/);
  });
});

describe('textOf', () => {
  test('strips markup and normalises entities', () => {
    assert.equal(S.textOf('<p>a &amp; b</p>'), 'a & b');
    assert.equal(S.textOf('a<br>b'), 'a\nb');
    assert.equal(S.textOf('  <b> x </b>  '), 'x');
  });
});

// ---------------------------------------------------------------------------
// THE THREE ENGINES
//
// DGE reads scans with three different engines, and which one a book wants is
// a judgement made by looking, not a constant in code. The comparison model
// below is what lets a person look: one row per engine, always the same three
// rows in the same order, each carrying its own reading of the same page.
// ---------------------------------------------------------------------------
describe('engines', () => {
  test('exactly the three that actually read a scan', () => {
    assert.deepEqual(S.ENGINE_IDS.slice().sort(), ['sarvam', 'tesseract', 'vision']);
  });

  test('GEMINI IS NOT AN ENGINE — it proofreads Vision, it never reads a scan', () => {
    assert.equal(S.ENGINE_IDS.indexOf('gemini'), -1);
    // and a staged file naming a Gemini model is therefore Vision output
    assert.equal(S.stagedEngine({ model: 'gemini-flash-latest' }), 'vision');
  });

  test('only Sarvam keeps the layout, only Tesseract is free and local', () => {
    assert.equal(S.engineMeta('sarvam').layout, true);
    assert.equal(S.engineMeta('vision').layout, false);
    assert.equal(S.engineMeta('tesseract').layout, false);
    assert.equal(S.engineMeta('tesseract').key, null);
    assert.equal(S.engineMeta('tesseract').runsIn, 'browser');
    assert.equal(S.engineMeta('sarvam').runsIn, 'workflow');
    assert.equal(S.engineMeta('vision').runsIn, 'workflow');
  });

  test('a staged file is read into the slot of the engine that made it', () => {
    assert.equal(S.stagedEngine({ engine: 'sarvam-docai' }), 'sarvam');
    assert.equal(S.stagedEngine({ engine: 'vision' }), 'vision');
    assert.equal(S.stagedEngine({ ocr_engine: 'Tesseract.js 5' }), 'tesseract');
    assert.equal(S.stagedEngine({}), '');
    assert.equal(S.stagedEngine(null), '');
  });

  test('an unknown engine id still yields a usable row rather than throwing', () => {
    const m = S.engineMeta('whatever');
    assert.equal(m.id, 'whatever');
    assert.equal(typeof m.label, 'string');
  });
});

describe('agreement', () => {
  test('identical readings agree completely', () => {
    assert.equal(S.agreement('राम कृष्ण गोविन्द', 'राम कृष्ण गोविन्द'), 1);
  });

  test('line breaks in different places do not count as disagreement', () => {
    assert.equal(S.agreement('राम कृष्ण\nगोविन्द', 'राम\nकृष्ण गोविन्द'), 1);
  });

  test('a misread word pulls it down but not to zero', () => {
    const a = S.agreement('राम कृष्ण गोविन्द', 'राम कष्ण गोविन्द');
    assert.ok(a > 0.5 && a < 1, 'expected partial agreement, got ' + a);
  });

  test('nothing in common is zero; two empties are one', () => {
    assert.equal(S.agreement('अ आ', 'क ख'), 0);
    assert.equal(S.agreement('', ''), 1);
    assert.equal(S.agreement('अ', ''), 0);
  });
});

describe('comparison', () => {
  const sarvam = [{ page: 1, html: '<h2>प्रथमो मन्त्रः</h2><p>ईशा वास्यमिदं सर्वम्</p>' },
                  { page: 2, html: '<p>द्वितीयम्</p>' }];
  const vision = [{ page: 1, html: '<p>प्रथमो मन्त्रः</p><p>ईशा वास्यमिदं सर्वम्</p>' }];

  test('all three rows exist even when only one engine has been run', () => {
    const c = S.buildComparison([{ id: 'sarvam', pages: sarvam }]);
    assert.deepEqual(c.engines.map((e) => e.id), ['sarvam', 'vision', 'tesseract']);
    assert.deepEqual(c.engines.map((e) => e.loaded), [true, false, false]);
  });

  test('rows keep their order whichever engine loaded first', () => {
    const a = S.buildComparison([{ id: 'tesseract', pages: vision }, { id: 'sarvam', pages: sarvam }]);
    const b = S.buildComparison([{ id: 'sarvam', pages: sarvam }, { id: 'tesseract', pages: vision }]);
    assert.equal(a.engines.map((e) => e.id).join(','), b.engines.map((e) => e.id).join(','));
  });

  test('the layout-preserving engine is chosen by default when it is there', () => {
    const c = S.buildComparison([{ id: 'vision', pages: vision }, { id: 'sarvam', pages: sarvam }]);
    assert.equal(c.chosen, 'sarvam');
  });

  test('with no layout engine loaded, the first loaded one is chosen', () => {
    const c = S.buildComparison([{ id: 'vision', pages: vision }]);
    assert.equal(c.chosen, 'vision');
  });

  test('nothing loaded chooses nothing rather than guessing', () => {
    const c = S.buildComparison([]);
    assert.equal(c.chosen, '');
    assert.equal(S.chosenDoc(c), null);
    assert.deepEqual(Object.keys(c.pages), []);
  });

  test('pages are the union across engines, in order', () => {
    const c = S.buildComparison([{ id: 'sarvam', pages: sarvam }, { id: 'vision', pages: vision }]);
    assert.equal(c.pages.join(','), '1,2');
  });

  test('choosing an engine that read nothing is refused', () => {
    const c = S.buildComparison([{ id: 'sarvam', pages: sarvam }]);
    assert.equal(S.chooseEngine(c, 'tesseract'), false);
    assert.equal(c.chosen, 'sarvam');
  });

  test('choosing a loaded engine switches what the styling half works on', () => {
    const c = S.buildComparison([{ id: 'sarvam', pages: sarvam }, { id: 'vision', pages: vision }]);
    assert.equal(S.chooseEngine(c, 'vision'), true);
    assert.equal(c.chosen, 'vision');
    assert.equal(S.chosenDoc(c).blocks[0].srcTag, 'p');
  });

  test('one page, one row per engine, with the scan-side blocks it read', () => {
    const c = S.buildComparison([{ id: 'sarvam', pages: sarvam }, { id: 'vision', pages: vision }]);
    const rows = S.comparePage(c, 1);
    assert.equal(rows.length, 3);
    assert.deepEqual(rows.map((r) => r.id), ['sarvam', 'vision', 'tesseract']);
    assert.equal(rows[0].blocks.length, 2);
    assert.equal(rows[1].blocks.length, 2);
    assert.equal(rows[2].blocks.length, 0);
  });

  test('agreement is measured against the chosen reading, and the chosen row is 1', () => {
    const c = S.buildComparison([{ id: 'sarvam', pages: sarvam }, { id: 'vision', pages: vision }]);
    const rows = S.comparePage(c, 1);
    assert.equal(rows[0].agreement, 1);          // sarvam is chosen
    // Vision read the same words, only as <p> instead of <h2> — same text.
    assert.equal(rows[1].agreement, 1);
    assert.equal(rows[2].agreement, null);       // nothing loaded, no claim made
  });

  test('an engine that read a page the others did not still shows on that page', () => {
    const c = S.buildComparison([{ id: 'sarvam', pages: sarvam }, { id: 'vision', pages: vision }]);
    const rows = S.comparePage(c, 2);
    assert.equal(rows[0].blocks.length, 1);
    assert.equal(rows[1].blocks.length, 0);
  });

  test('stats describe how much and how richly each engine read', () => {
    const c = S.buildComparison([{ id: 'sarvam', pages: sarvam }, { id: 'vision', pages: vision }]);
    assert.equal(c.engines[0].stats.headings, 1);   // sarvam saw the heading
    assert.equal(c.engines[1].stats.headings, 0);   // vision flattened it
    assert.equal(c.engines[0].stats.pages, 2);
    assert.ok(c.engines[0].stats.chars > 0);
  });

  test('THE SOURCE TAG SURVIVES THE CHOICE — styling one engine cannot edit another', () => {
    const c = S.buildComparison([{ id: 'sarvam', pages: sarvam }, { id: 'vision', pages: vision }]);
    const sd = c.engines[0].doc;
    S.applyClass(sd, sd.blocks[0].id, 'title', 'all');
    assert.equal(c.engines[0].doc.blocks[0].srcTag, 'h2');
    assert.equal(c.engines[1].doc.blocks[0].cls, 'body');
  });

  test('pageText joins a page into one reading for comparison', () => {
    const c = S.buildComparison([{ id: 'sarvam', pages: sarvam }]);
    assert.equal(S.pageText(c.engines[0].doc, 2), 'द्वितीयम्');
    assert.equal(S.pageText(null, 1), '');
  });
});
