// Tests for functions/lib/book-render.js — the rules around the server-side
// PDF renderer.
//
// The renderer itself is a real Chromium and cannot be unit tested. What CAN
// be tested is every decision made before it is handed a document, and those
// are the decisions that matter: a headless browser rendering a caller's HTML
// is only safe because of what this module refuses.
'use strict';

const { test, describe } = require('node:test');
const assert = require('node:assert/strict');

const br = require('../functions/lib/book-render');

describe('mayRenderBook', () => {
  test('an unconfigured capability is closed, not open', () => {
    assert.equal(br.mayRenderBook('basic', {}), false);
    assert.equal(br.mayRenderBook('basic', null), false);
    assert.equal(br.mayRenderBook('basic', { book: [] }), false);
    assert.equal(br.mayRenderBook('basic', { copy: ['basic'] }), false);
  });

  test('a role the capability names may', () => {
    assert.equal(br.mayRenderBook('sponsor', { book: ['sponsor'] }), true);
    assert.equal(br.mayRenderBook('basic', { book: ['sponsor'] }), false);
  });

  test('admins may, configured or not', () => {
    assert.equal(br.mayRenderBook('admin', {}), true);
    assert.equal(br.mayRenderBook('superadmin', {}), true);
  });

  test('a signed-out caller may not, even if anonymous is somehow listed as a role elsewhere', () => {
    assert.equal(br.mayRenderBook(null, { book: ['basic'] }), false);
    assert.equal(br.mayRenderBook('', { book: ['basic'] }), false);
  });

  test('a near-miss spelling of admin is just a stranger', () => {
    for (const claim of ['Admin', 'ADMIN', ' admin', 'admin ']) {
      assert.equal(br.mayRenderBook(claim, {}), false, JSON.stringify(claim));
    }
  });

  test('a capabilities map that is not a map cannot grant anything', () => {
    assert.equal(br.mayRenderBook('basic', 'book'), false);
    assert.equal(br.mayRenderBook('basic', { book: 'everyone' }), false);
    assert.equal(br.mayRenderBook('basic', { book: true }), false);
  });
});

describe('checkHtml', () => {
  const doc = '<!DOCTYPE html><html><body>ॐ</body></html>';

  test('a real document passes', () => {
    assert.equal(br.checkHtml(doc), null);
    assert.equal(br.checkHtml('\n  ' + doc), null, 'leading whitespace is fine');
    assert.equal(br.checkHtml('<!doctype html><html></html>'), null, 'case does not matter');
  });

  test('nothing, or not a document, is refused', () => {
    assert.equal(br.checkHtml(''), 'empty');
    assert.equal(br.checkHtml('   '), 'empty');
    assert.equal(br.checkHtml(null), 'empty');
    assert.equal(br.checkHtml(42), 'empty');
    assert.equal(br.checkHtml('<h1>hello</h1>'), 'not-a-document');
    assert.equal(br.checkHtml('<script>fetch("http://169.254.169.254/")</script>'), 'not-a-document');
  });

  test('an oversized document is refused before the renderer sees it', () => {
    const big = '<!DOCTYPE html><html><body>' + 'x'.repeat(200) + '</body></html>';
    assert.equal(br.checkHtml(big, 100), 'too-large');
    assert.equal(br.checkHtml(big, 10000), null);
  });

  test('the size limit counts BYTES, not characters — Devanagari is three bytes a glyph', () => {
    // 400 Devanagari code points is 1,200 bytes. A character-counting limit
    // would let a Sanskrit book through at three times the intended size.
    const dev = '<!DOCTYPE html><html><body>' + 'क'.repeat(400) + '</body></html>';
    assert.equal(dev.length < 500, true);
    assert.equal(br.checkHtml(dev, 500), 'too-large');
  });

  test('the default ceiling is generous enough for a real book and finite', () => {
    assert.equal(br.MAX_HTML_BYTES, 8 * 1024 * 1024);
    assert.equal(br.checkHtml('<!DOCTYPE html>' + 'x'.repeat(br.MAX_HTML_BYTES)), 'too-large');
  });
});

describe('allowedRequest — what the renderer may load', () => {
  test('a self-contained document needs only these', () => {
    assert.equal(br.allowedRequest('about:blank'), true);
    assert.equal(br.allowedRequest('data:image/png;base64,iVBORw0KGgo='), true);
    assert.equal(br.allowedRequest('blob:null/abc'), true);
  });

  test('everything reachable over a network is refused', () => {
    for (const url of [
      'http://169.254.169.254/computeMetadata/v1/',   // the metadata server
      'http://metadata.google.internal/',
      'https://example.com/x.css',
      'http://localhost:8080/',
      'http://127.0.0.1/',
      'ws://x/',
      'https://fonts.googleapis.com/css2?family=Noto+Sans+Devanagari'
    ]) {
      assert.equal(br.allowedRequest(url), false, url + ' must be refused');
    }
  });

  test('local files are refused', () => {
    assert.equal(br.allowedRequest('file:///etc/passwd'), false);
    assert.equal(br.allowedRequest('file:///srv/key.json'), false);
  });

  test('a scheme that merely starts with an allowed word is refused', () => {
    // "datafile:" begins with "data" — startsWith on the scheme alone would
    // have let it through; the colon is part of the test on purpose.
    assert.equal(br.allowedRequest('datafile://x'), false);
    assert.equal(br.allowedRequest('about:blank#x'), false);
    assert.equal(br.allowedRequest(''), false);
    assert.equal(br.allowedRequest(null), false);
  });
});

describe('pdfOptionsFor', () => {
  test('A5 is the default, A4 when asked', () => {
    assert.equal(br.pdfOptionsFor({}).format, 'A5');
    assert.equal(br.pdfOptionsFor(null).format, 'A5');
    assert.equal(br.pdfOptionsFor({ pageSize: 'a4' }).format, 'A4');
    assert.equal(br.pdfOptionsFor({ pageSize: 'A4' }).format, 'A4');
    assert.equal(br.pdfOptionsFor({ pageSize: 'legal' }).format, 'A5', 'anything else falls back');
  });

  test('backgrounds print — the watermark and the cover are backgrounds', () => {
    assert.equal(br.pdfOptionsFor({}).printBackground, true);
  });
});

describe('filenameFor / contentDispositionFor', () => {
  test('an ordinary title becomes an ordinary filename', () => {
    assert.equal(br.filenameFor('Sumadhva Vijaya'), 'Sumadhva-Vijaya.pdf');
    assert.equal(br.filenameFor('  Sarga 1-3  '), 'Sarga-1-3.pdf');
  });

  test('a Devanagari title falls back rather than producing ".pdf"', () => {
    assert.equal(br.filenameFor('श्रीमध्वविजयः'), 'sarvamula-book.pdf');
    assert.equal(br.filenameFor(''), 'sarvamula-book.pdf');
    assert.equal(br.filenameFor(null), 'sarvamula-book.pdf');
    assert.equal(br.filenameFor('---'), 'sarvamula-book.pdf');
  });

  test('nothing a caller types can break out of the header', () => {
    // A title is caller-controlled and lands in a response header. A newline
    // or a quote here would be header injection.
    const nasty = 'a"\r\nSet-Cookie: x=1\r\n\r\n<b>';
    const name = br.filenameFor(nasty);
    assert.ok(!/[\r\n"]/.test(name), name);
    const header = br.contentDispositionFor(nasty);
    assert.ok(!/[\r\n]/.test(header), header);
  });

  test('the real title survives in filename*, percent-encoded', () => {
    const header = br.contentDispositionFor('श्रीमध्वविजयः');
    assert.match(header, /^attachment; filename="sarvamula-book\.pdf"; filename\*=UTF-8''/);
    assert.ok(!/[^\x20-\x7e]/.test(header), 'the header must be pure ASCII');
    const encoded = header.split("UTF-8''")[1].replace(/\.pdf$/, '');
    assert.equal(decodeURIComponent(encoded), 'श्रीमध्वविजयः');
  });

  test('a very long title is cut, not passed through', () => {
    const name = br.filenameFor('x'.repeat(500));
    assert.ok(name.length <= 84, name.length);
  });
});
