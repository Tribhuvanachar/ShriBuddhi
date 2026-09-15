// convert/urlimport.js — imports a MediaWiki page's text directly
// (a MediaWiki install), window.DGE.UrlImport namespace. No OCR step
// needed — the source is already digital text — so this feeds straight
// into the SAME chunked Gemini proofread/structure pipeline that OCR'd
// pages use, just skipping Vision entirely. Confirmed against a real
// fetched a real page from the target site before writing this (it's
// MediaWiki 1.44.5), rather than guessing at the markup.
window.DGE = window.DGE || {};
window.DGE.UrlImport = (function () {

  // Supports both "?title=PageName" and "/PageName" style wiki URLs.
  function parseWikiUrl(url) {
    const u = new URL(url);
    let title = u.searchParams.get('title');
    if (!title) {
      const parts = u.pathname.split('/').filter(Boolean);
      title = decodeURIComponent(parts[parts.length - 1] || '');
    }
    if (!title) throw new Error('Could not find a page title in that URL.');
    // MediaWiki's classic, extension-independent raw-text endpoint —
    // works the same way on essentially every MediaWiki install.
    const rawUrl = `${u.origin}/index.php?action=raw&title=${encodeURIComponent(title)}`;
    return { title, rawUrl };
  }

  // Strips the most common wikitext markup down to plain text. Doesn't
  // need to be perfect — Gemini's proofread/structure pass handles the
  // remaining messiness the same way it already handles OCR artifacts.
  function stripWikitext(wikitext) {
    let t = wikitext;
    t = t.replace(/\{\{[^{}]*\}\}/g, '');                       // simple (non-nested) templates
    t = t.replace(/\[\[([^\]|]*\|)?([^\]]*)\]\]/g, '$2');        // [[link|text]] -> text
    t = t.replace(/'''?/g, '');                                  // bold/italic markers
    t = t.replace(/^==+\s*(.*?)\s*==+$/gm, '\n$1\n');            // == Header == -> plain line
    t = t.replace(/<ref[^>]*>[\s\S]*?<\/ref>/g, '');             // footnote refs
    t = t.replace(/<[^>]+>/g, '');                                // any remaining HTML tags
    t = t.replace(/\n{3,}/g, '\n\n');                             // collapse excess blank lines
    return t.trim();
  }

  async function fetchPageText(pageUrl) {
    const { title, rawUrl } = parseWikiUrl(pageUrl);
    let res;
    try {
      res = await fetch(rawUrl);
    } catch (e) {
      throw new Error('Network error fetching the page: ' + e.message);
    }
    if (!res.ok) throw new Error(`Could not fetch page (HTTP ${res.status}) — check the URL, or this site's wiki may not support ?action=raw.`);
    const wikitext = await res.text();
    if (!wikitext || wikitext.trim().length < 20) throw new Error('Fetched page looks empty — check the page title in the URL is correct.');
    return { title, text: stripWikitext(wikitext) };
  }

  // Splits into fixed-size text slices, shaped exactly like OCR's
  // {page, text} entries — this is what lets the rest of the pipeline
  // (chunked proofread, resumability, schema map, push) run completely
  // unchanged regardless of whether content came from OCR or a URL.
  function splitIntoPages(text, charsPerPage) {
    const size = charsPerPage || 4000;
    const pages = [];
    for (let i = 0, p = 1; i < text.length; i += size, p++) {
      pages.push({ page: p, text: text.slice(i, i + size) });
    }
    return pages;
  }

  return { fetchPageText, splitIntoPages };
})();
