/**
 * book-render.js — the decisions behind renderBook, without the renderer.
 *
 * THE POINT OF THIS FILE. Server-side PDF means a browser, on our machine,
 * rendering a document a caller sent us. That is an unusually sharp tool: a
 * headless Chromium that follows the HTML it is given will happily fetch an
 * internal URL, read a local file through file://, or spend a minute of CPU
 * on a page designed to spend a minute of CPU. None of that is a hypothetical
 * for a public endpoint.
 *
 * So the rules live here — who may ask, how big a document may be, what the
 * renderer is allowed to load, what the file comes back called — as pure
 * functions with tests, and index.js holds only the part that needs a real
 * browser. The one rule this file cannot enforce (network interception) is
 * stated in allowedRequest(), which index.js uses as the predicate.
 *
 * Mirrors dgeRoleCan in js/role-access.js for the capability check, and
 * has to: a reader that offers the button to someone the server refuses is a
 * bug report, and a reader that hides it from someone the server would serve
 * is a feature nobody can find.
 */

'use strict';

const MAX_HTML_BYTES = 8 * 1024 * 1024;   // ~8 MB: a 700-page A5 book is well under 2 MB
const MAX_TITLE = 80;

/**
 * May this role prepare a book?
 *
 * Admins always may (they may everything). Otherwise the capability must be
 * configured AND name the role — an unconfigured capability is closed, not
 * open, which is the direction every other gate in this project takes.
 */
function mayRenderBook(role, capabilities) {
  const r = role || 'anonymous';
  if (r === 'admin' || r === 'superadmin') return true;
  const caps = capabilities && typeof capabilities === 'object' ? capabilities : {};
  const allowed = caps.book;
  if (!Array.isArray(allowed) || !allowed.length) return false;
  return allowed.indexOf(r) >= 0;
}

/**
 * Is the posted document something we are willing to render?
 *
 * Returns null when it is fine, or a short reason string. The reason IS safe
 * to return here, unlike the corpus gate's: a caller who posted the document
 * already knows everything these messages reveal, and "too large" is a far
 * better answer than a timeout.
 */
function checkHtml(html, limit) {
  const max = typeof limit === 'number' ? limit : MAX_HTML_BYTES;
  if (typeof html !== 'string' || !html.trim()) return 'empty';
  const bytes = Buffer.byteLength(html, 'utf8');
  if (bytes > max) return 'too-large';
  if (!/^\s*<!DOCTYPE html/i.test(html)) return 'not-a-document';
  return null;
}

/**
 * What the renderer may load, given a fully self-contained document.
 *
 * The client inlines the stylesheet and the imprint icon before posting, so a
 * correct book needs NOTHING from the network. That makes this predicate
 * simple and absolute rather than a list of trusted hosts to keep current:
 * data: URIs and the document itself, nothing else. about:blank is here
 * because setContent navigates there first.
 *
 * A remote font or image would therefore silently not appear — which is the
 * right trade. The alternative is a renderer that can be pointed at anything
 * reachable from inside the project's network.
 */
function allowedRequest(url) {
  const u = String(url || '');
  return u.startsWith('data:') || u === 'about:blank' || u.startsWith('blob:');
}

/** A4 or A5, and the margins the print stylesheet was drawn for. */
function pdfOptionsFor(spec) {
  const s = spec && typeof spec === 'object' ? spec : {};
  return {
    format: String(s.pageSize || 'a5').toLowerCase() === 'a4' ? 'A4' : 'A5',
    printBackground: true,
    preferCSSPageSize: true,
    margin: { top: '14mm', bottom: '16mm', left: '14mm', right: '14mm' }
  };
}

/**
 * The download filename.
 *
 * Devanagari titles are the normal case here, and a Content-Disposition
 * filename is a header — so the readable name is transliteration-free ASCII
 * with everything else stripped, and the real title rides in filename* where
 * UTF-8 is actually allowed. A title that reduces to nothing (an all-
 * Devanagari one usually does) falls back rather than producing ".pdf".
 */
function filenameFor(title) {
  const raw = String(title || '').trim();
  const ascii = raw.replace(/[^A-Za-z0-9 _-]+/g, ' ').replace(/\s+/g, '-')
    .replace(/^-+|-+$/g, '').slice(0, MAX_TITLE);
  return (ascii || 'sarvamula-book') + '.pdf';
}

/** The header value, with the real title preserved for clients that read RFC 5987. */
function contentDispositionFor(title) {
  const ascii = filenameFor(title);
  const utf8 = encodeURIComponent(String(title || 'book').trim() || 'book') + '.pdf';
  return `attachment; filename="${ascii}"; filename*=UTF-8''${utf8}`;
}

module.exports = {
  MAX_HTML_BYTES, mayRenderBook, checkHtml, allowedRequest, pdfOptionsFor,
  filenameFor, contentDispositionFor
};
