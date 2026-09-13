/**
 * ocr-studio-core.js — the document and style model behind admin/ocr-studio.html.
 *
 * WHAT THE STUDIO IS FOR. Sarvam's layout-preserving OCR returns HTML: a
 * heading comes back as <h2>, a paragraph as <p>. tools/ocr_review_merge.py
 * already keeps that markup per block instead of flattening it to text. What
 * was missing is the half a person actually works in — seeing the digitised
 * page beside the original, and restyling the whole document from one block,
 * the way a Word style does.
 *
 * THE ONE IDEA. A block keeps TWO tags, and the distinction is the whole
 * design:
 *
 *   srcTag  what the OCR decided this block was. Never edited. It is the
 *           evidence, and it is what "every other block like this one" means.
 *   cls     what WE have decided it is. Edited freely, per block or in bulk.
 *
 * Because srcTag survives, selecting one heading and saying "all of these are
 * Heading 2" is a well-defined operation rather than a guess: the other blocks
 * the OCR tagged the same way are exactly the ones that change. And because
 * cls is separate from the style table, editing the Heading 2 style restyles
 * every block carrying it without touching a single block's own markup —
 * which is what makes it a style rather than formatting.
 *
 * THREE ENGINES, NOT ONE. DGE reads a scan with Sarvam Document AI (keeps
 * the layout), Google Cloud Vision (flat text) or Tesseract.js (free, WASM,
 * in this tab). Which one a particular book wants is a judgement made by
 * looking at all three, so the studio holds a document per engine and shows
 * them one beneath the other, each beside the page it read, until a person
 * picks one. Only then does the styling half above have anything to work on.
 * Gemini is not among them: it proofreads Vision's text afterwards and never
 * reads a scan.
 *
 * PURE. No DOM, no fetch. The page is the shell; every rule about what
 * changes when you click something lives here, where it can be tested.
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.dgeOcrStudio = api;
}(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  // Which HTML tags the OCR emits as a block. Anything else it returns is
  // inline and stays inside whatever block contains it.
  const BLOCK_TAGS = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'blockquote', 'pre', 'li', 'div'];

  /**
   * The style classes a person picks from, and how each renders.
   *
   * `tag` is what the class exports as, so the published HTML stays semantic —
   * a Heading 2 leaves here as an <h2>, not a <div> with big text. Everything
   * else is appearance and is safe to edit.
   */
  function defaultStyles() {
    return {
      title:     { label: 'Title',       tag: 'h1',         size: 30, weight: 700, italic: false, align: 'center', before: 0,  after: 18, indent: 0, color: '' },
      h1:        { label: 'Heading 1',   tag: 'h1',         size: 24, weight: 700, italic: false, align: 'left',   before: 20, after: 10, indent: 0, color: '' },
      h2:        { label: 'Heading 2',   tag: 'h2',         size: 20, weight: 700, italic: false, align: 'left',   before: 16, after: 8,  indent: 0, color: '' },
      h3:        { label: 'Heading 3',   tag: 'h3',         size: 17, weight: 600, italic: false, align: 'left',   before: 14, after: 6,  indent: 0, color: '' },
      body:      { label: 'Body',        tag: 'p',          size: 15, weight: 400, italic: false, align: 'left',   before: 0,  after: 10, indent: 0, color: '' },
      verse:     { label: 'Verse',       tag: 'blockquote', size: 16, weight: 400, italic: false, align: 'center', before: 10, after: 10, indent: 0, color: '' },
      commentary:{ label: 'Commentary',  tag: 'p',          size: 14, weight: 400, italic: false, align: 'left',   before: 0,  after: 8,  indent: 18, color: '' },
      colophon:  { label: 'Colophon',    tag: 'p',          size: 14, weight: 600, italic: true,  align: 'center', before: 12, after: 12, indent: 0, color: '' },
      note:      { label: 'Note',        tag: 'p',          size: 13, weight: 400, italic: true,  align: 'left',   before: 0,  after: 6,  indent: 18, color: '' }
    };
  }

  /** The class a block starts in, from the tag the OCR gave it. */
  function classify(srcTag) {
    const t = String(srcTag || '').toLowerCase();
    if (t === 'h1') return 'h1';
    if (t === 'h2') return 'h2';
    if (t === 'h3' || t === 'h4' || t === 'h5' || t === 'h6') return 'h3';
    if (t === 'blockquote') return 'verse';
    return 'body';
  }

  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  /** The inner text of an HTML fragment, without needing a DOM. */
  function textOf(html) {
    return String(html || '')
      .replace(/<br\s*\/?>/gi, '\n')
      .replace(/<[^>]+>/g, '')
      .replace(/&nbsp;/g, ' ')
      .replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"')
      .replace(/[ \t]+/g, ' ')
      .trim();
  }

  /**
   * Split one page of OCR HTML into blocks.
   *
   * Deliberately a scanner over top-level tags rather than a full parser: the
   * input is machine-generated and shallow, and mirroring
   * tools/ocr_review_merge.py's _BlockSplitter keeps the browser and the merge
   * tool agreeing on what a block is. Text outside any block tag still becomes
   * a block — OCR does emit bare lines, and silently dropping them would lose
   * content with nothing to show for it.
   */
  function parseBlocks(html, page) {
    const src = String(html || '');
    const out = [];
    const re = new RegExp('<(' + BLOCK_TAGS.join('|') + ')\\b[^>]*>([\\s\\S]*?)<\\/\\1>', 'gi');
    let last = 0, m;
    const loose = (chunk) => {
      const t = textOf(chunk);
      if (t) out.push({ srcTag: 'p', html: escapeHtml(t), text: t, page: page || null });
    };
    while ((m = re.exec(src)) !== null) {
      if (m.index > last) loose(src.slice(last, m.index));
      const inner = m[2];
      const t = textOf(inner);
      if (t) out.push({ srcTag: m[1].toLowerCase(), html: inner, text: t, page: page || null });
      last = re.lastIndex;
    }
    if (last < src.length) loose(src.slice(last));
    return out.map((b, i) => Object.assign({ id: 'b' + (i + 1), cls: classify(b.srcTag) }, b));
  }

  /** Build a document from pages of OCR HTML. */
  function docFromPages(pages) {
    const blocks = [];
    (pages || []).forEach((p, pi) => {
      const html = typeof p === 'string' ? p : (p && (p.html || p.text)) || '';
      const num = (p && p.page) || pi + 1;
      parseBlocks(html, num).forEach((b) => {
        blocks.push(Object.assign({}, b, { id: 'p' + num + '_' + b.id }));
      });
    });
    return { blocks: blocks, styles: defaultStyles() };
  }

  // ------------------------------------------------------------------------
  // THE THREE ENGINES
  //
  // DGE does not have "an OCR". It has three readers with different strengths,
  // and which one is right is a per-book judgement a scholar has to make by
  // looking, not something to decide once in code. So the studio holds all
  // three and lets the person choose.
  //
  // Gemini is deliberately NOT in this list. It never reads a scan — it
  // proofreads Vision's flat text afterwards (tools/gemini_ocr_commentary.py,
  // lakshmi_kaumudi_ocr.py, vasu_kaumudi_ocr.py all run PDF -> Vision -> Gemini).
  // Listing it as a fourth engine would invite a comparison that has no
  // meaning, and it is the one stage that costs real money per token.
  // ------------------------------------------------------------------------
  const ENGINES = [
    {
      id: 'sarvam',
      label: 'Sarvam Document AI',
      blurb: 'Indian-language scans, layout kept',
      layout: true,
      runsIn: 'workflow',
      where: '.github/workflows/ocr-sarvam.yml → tools/sarvam_docai.py',
      key: 'SARVAM_API_KEY',
      cost: 'paid · per page from the prepaid balance on dashboard.sarvam.ai'
    },
    {
      id: 'vision',
      label: 'Google Cloud Vision',
      blurb: 'DOCUMENT_TEXT_DETECTION, flat text',
      layout: false,
      runsIn: 'workflow',
      where: '.github/workflows/ocr-vision-pages.yml → tools/vision_ocr_pages.py',
      key: 'VISION_API_KEY',
      cost: 'paid · per page'
    },
    {
      id: 'tesseract',
      label: 'Tesseract.js',
      blurb: 'free, in-browser WASM, needs a language hint',
      layout: false,
      runsIn: 'browser',
      where: 'dge/convert/tesseract-check.js',
      key: null,
      cost: 'free · runs on this machine, sends nothing'
    }
  ];

  const ENGINE_IDS = ENGINES.map((e) => e.id);

  function engineMeta(id) {
    return ENGINES.find((e) => e.id === id) ||
      { id: String(id || 'unknown'), label: String(id || 'Unknown engine'), blurb: '',
        layout: false, runsIn: 'unknown', where: '', key: null, cost: '' };
  }

  /**
   * Which engine produced a staged file.
   *
   * Reads the file's own `engine` field first — sarvam_docai.py writes
   * "sarvam-docai" there. Older Vision+Gemini stagers wrote only `model`,
   * naming the Gemini model that PROOFREAD the page; those files are Vision
   * output, so a gemini model name resolves to 'vision' rather than inventing
   * a fourth engine. Returns '' when nothing in the file says.
   */
  function stagedEngine(staged) {
    const hay = [
      staged && staged.engine, staged && staged.ocr_engine, staged && staged.model
    ].map((v) => String(v == null ? '' : v).toLowerCase()).join(' ');
    if (/sarvam/.test(hay)) return 'sarvam';
    if (/tesseract/.test(hay)) return 'tesseract';
    if (/vision|gemini/.test(hay)) return 'vision';
    return '';
  }

  /** Words, normalised, for comparing two engines' reading of the same page. */
  function words(text) {
    return String(text || '')
      .normalize('NFC')
      .replace(/[।॥.,;:!?"'()\[\]—–-]/g, ' ')
      .split(/\s+/)
      .filter(Boolean);
  }

  /**
   * How much two readings agree, 0..1 — a Dice coefficient over word bags.
   *
   * Deliberately not an edit distance: at page scale that is millions of
   * operations per pair and this runs for every engine pair on every page.
   * A word bag also survives the difference that matters least here — the two
   * engines breaking lines in different places — while still collapsing when
   * one of them has genuinely misread the script.
   */
  function agreement(a, b) {
    const wa = words(a), wb = words(b);
    if (!wa.length && !wb.length) return 1;
    if (!wa.length || !wb.length) return 0;
    const bag = new Map();
    wa.forEach((w) => bag.set(w, (bag.get(w) || 0) + 1));
    let shared = 0;
    wb.forEach((w) => {
      const n = bag.get(w) || 0;
      if (n > 0) { bag.set(w, n - 1); shared++; }
    });
    return (2 * shared) / (wa.length + wb.length);
  }

  /** What to show on an engine's row header: how much it read, and how richly. */
  function engineStats(doc) {
    const blocks = (doc && doc.blocks) || [];
    let chars = 0, headings = 0;
    blocks.forEach((b) => {
      chars += (b.text || '').length;
      if (/^h[1-6]$/.test(b.srcTag)) headings++;
    });
    return {
      blocks: blocks.length,
      chars: chars,
      headings: headings,
      pages: pagesIn(doc).length
    };
  }

  function pagesIn(doc) {
    const seen = [];
    ((doc && doc.blocks) || []).forEach((b) => {
      const p = b.page == null ? 1 : b.page;
      if (seen.indexOf(p) < 0) seen.push(p);
    });
    return seen.sort(function (a, b) { return a - b; });
  }

  /**
   * Hold one document per engine, side by side, with one of them chosen.
   *
   * `sources` is a list of {id, pages, label?} — pages in the same shape
   * docFromPages takes. Engines with nothing loaded still appear, so the row
   * for an engine you have not run is visible and says why it is empty
   * instead of silently not being there.
   *
   * The engines come back in ENGINES order, always the same three rows in the
   * same places: a comparison whose rows move around between loads is not a
   * comparison.
   */
  function buildComparison(sources) {
    const byId = {};
    (sources || []).forEach((s) => {
      if (!s || !s.id) return;
      byId[s.id] = s;
    });
    const engines = ENGINES.map((meta) => {
      const src = byId[meta.id];
      const doc = src && src.pages ? docFromPages(src.pages) : null;
      return {
        id: meta.id,
        label: meta.label,
        meta: meta,
        doc: doc,
        loaded: !!doc && doc.blocks.length > 0,
        source: (src && src.label) || '',
        stats: doc ? engineStats(doc) : { blocks: 0, chars: 0, headings: 0, pages: 0 }
      };
    });
    const loaded = engines.filter((e) => e.loaded);
    return {
      engines: engines,
      // Default to the richest thing actually loaded, preferring an engine
      // that kept the layout — that is the output the styling half of the
      // studio can do anything with.
      chosen: (loaded.find((e) => e.meta.layout) || loaded[0] || { id: '' }).id,
      pages: allPages(engines)
    };
  }

  function allPages(engines) {
    const seen = [];
    engines.forEach((e) => {
      pagesIn(e.doc).forEach((p) => { if (seen.indexOf(p) < 0) seen.push(p); });
    });
    return seen.sort(function (a, b) { return a - b; });
  }

  /** Adopt one engine's reading. Refuses an engine with nothing loaded. */
  function chooseEngine(cmp, id) {
    const e = (cmp && cmp.engines || []).find((x) => x.id === id);
    if (!e || !e.loaded) return false;
    cmp.chosen = id;
    return true;
  }

  function chosenDoc(cmp) {
    const e = (cmp && cmp.engines || []).find((x) => x.id === cmp.chosen);
    return (e && e.doc) || null;
  }

  /** One engine's blocks for one page. */
  function pageBlocks(doc, page) {
    return ((doc && doc.blocks) || []).filter((b) => (b.page == null ? 1 : b.page) === page);
  }

  function pageText(doc, page) {
    return pageBlocks(doc, page).map((b) => b.text).join('\n');
  }

  /**
   * The comparison itself: one row per engine for a single page, in engine
   * order, each carrying that engine's blocks and how far it agrees with the
   * chosen engine. The agreement is against the CHOSEN one rather than
   * pairwise between all three, because the question a person is actually
   * asking is "if I take this one, what am I disagreeing with".
   */
  function comparePage(cmp, page) {
    const ref = pageText(chosenDoc(cmp), page);
    return (cmp && cmp.engines || []).map((e) => {
      const blocks = pageBlocks(e.doc, page);
      const text = blocks.map((b) => b.text).join('\n');
      return {
        id: e.id,
        label: e.label,
        meta: e.meta,
        loaded: e.loaded,
        chosen: e.id === cmp.chosen,
        blocks: blocks,
        text: text,
        chars: text.length,
        agreement: e.id === cmp.chosen ? 1 : (blocks.length ? agreement(ref, text) : null)
      };
    });
  }

  /** Every block the OCR tagged the same way as this one. */
  function blocksLike(doc, blockId) {
    const b = (doc.blocks || []).find((x) => x.id === blockId);
    if (!b) return [];
    return doc.blocks.filter((x) => x.srcTag === b.srcTag);
  }

  /**
   * Put a block, its lookalikes, or the whole document into a class.
   *
   * `scope`:
   *   'one'  just this block
   *   'like' every block the OCR tagged the same way — the "select a header and
   *          apply it everywhere" move, and the reason srcTag is never edited
   *   'all'  every block, for the rare wholesale reset
   *
   * Returns the number of blocks changed, so the UI can say what it did rather
   * than leaving the person to scroll and check.
   */
  function applyClass(doc, blockId, cls, scope) {
    if (!doc || !doc.styles || !doc.styles[cls]) return 0;
    let targets;
    if (scope === 'all') targets = doc.blocks.slice();
    else if (scope === 'like') targets = blocksLike(doc, blockId);
    else targets = doc.blocks.filter((x) => x.id === blockId);
    let n = 0;
    targets.forEach((b) => { if (b.cls !== cls) { b.cls = cls; n++; } });
    return n;
  }

  /** How many blocks sit in each class — the style panel's counts. */
  function counts(doc) {
    const out = {};
    Object.keys((doc && doc.styles) || {}).forEach((k) => { out[k] = 0; });
    ((doc && doc.blocks) || []).forEach((b) => { out[b.cls] = (out[b.cls] || 0) + 1; });
    return out;
  }

  /** One class as a CSS rule body. */
  function ruleFor(s) {
    const parts = [
      'font-size:' + Number(s.size || 15) + 'px',
      'font-weight:' + Number(s.weight || 400),
      'font-style:' + (s.italic ? 'italic' : 'normal'),
      'text-align:' + (s.align || 'left'),
      'margin:' + Number(s.before || 0) + 'px 0 ' + Number(s.after || 0) + 'px 0',
      'padding-left:' + Number(s.indent || 0) + 'px'
    ];
    if (s.color) parts.push('color:' + s.color);
    return parts.join(';');
  }

  /** The whole style table as CSS, scoped so it cannot leak into the admin chrome. */
  function styleCss(styles, scope) {
    const sel = scope || '.doc';
    return Object.keys(styles || {})
      .map((k) => sel + ' [data-cls="' + k + '"]{' + ruleFor(styles[k]) + '}')
      .join('\n');
  }

  /**
   * The finished document, as standalone HTML.
   *
   * Each block exports under its CLASS's tag, not the tag the OCR gave it, so
   * a paragraph reclassified as a heading really leaves here as a heading. The
   * style table rides along as one <style> block — which is what makes the
   * result a styled document rather than a pile of inline attributes.
   */
  function exportHtml(doc, title) {
    const styles = doc.styles || defaultStyles();
    const body = (doc.blocks || []).map((b) => {
      const s = styles[b.cls] || styles.body;
      const tag = (s && s.tag) || 'p';
      return '<' + tag + ' data-cls="' + b.cls + '">' + b.html + '</' + tag + '>';
    }).join('\n');
    return '<!DOCTYPE html><html lang="sa"><head><meta charset="utf-8">' +
      '<title>' + escapeHtml(title || 'Digitised document') + '</title>' +
      '<style>body{max-width:44rem;margin:2rem auto;padding:0 1rem;' +
      'font-family:"Noto Serif Devanagari",serif;line-height:1.7}\n' +
      styleCss(styles, 'body') + '</style></head><body>\n' + body + '\n</body></html>';
  }

  /**
   * The shape tools/ocr_review_merge.py consumes.
   *
   * It reads `html` beside `text` per block, so the studio's decisions reach
   * the corpus through the merge path that already exists rather than a second
   * one built alongside it.
   */
  function toMergeBlocks(doc) {
    const styles = doc.styles || defaultStyles();
    return (doc.blocks || []).map((b) => {
      const s = styles[b.cls] || styles.body;
      const tag = (s && s.tag) || 'p';
      return {
        page: b.page,
        cls: b.cls,
        html: '<' + tag + ' data-cls="' + b.cls + '">' + b.html + '</' + tag + '>',
        text: b.text
      };
    });
  }

  return {
    BLOCK_TAGS, defaultStyles, classify, parseBlocks, docFromPages,
    blocksLike, applyClass, counts, ruleFor, styleCss, exportHtml,
    toMergeBlocks, textOf, escapeHtml,
    ENGINES, ENGINE_IDS, engineMeta, stagedEngine, words, agreement,
    engineStats, pagesIn, buildComparison, chooseEngine, chosenDoc,
    pageBlocks, pageText, comparePage
  };
}));
