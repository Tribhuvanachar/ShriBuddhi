// convert/utils.js — shared helpers, window.DGE.Utils namespace
window.DGE = window.DGE || {};
window.DGE.Utils = (function () {

  function fileToBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result.substring(reader.result.indexOf(',') + 1));
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  function downloadJson(obj, filename) {
    const blob = new Blob([JSON.stringify(obj, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  function saveProgress(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) { /* storage full/unavailable — non-fatal */ }
  }
  function loadProgress(key) {
    try { return JSON.parse(localStorage.getItem(key)); } catch (e) { return null; }
  }
  function clearProgress(key) {
    try { localStorage.removeItem(key); } catch (e) { /* ignore */ }
  }

  // LLMs sometimes wrap JSON output in ```json fences or add stray text
  // despite instructions not to — this strips fences first, then falls
  // back to extracting the outermost {...} block before giving up.
  function parseJsonLoose(text) {
    let cleaned = String(text).trim();
    cleaned = cleaned.replace(/^```(?:json)?\s*/i, '').replace(/```\s*$/i, '').trim();
    try {
      return JSON.parse(cleaned);
    } catch (e) {
      const start = cleaned.indexOf('{');
      const end = cleaned.lastIndexOf('}');
      if (start !== -1 && end !== -1 && end > start) {
        try { return JSON.parse(cleaned.slice(start, end + 1)); } catch (e2) { /* fall through */ }
      }
      throw new Error('Could not parse JSON from the model\'s response: ' + e.message);
    }
  }

  function formatError(e) {
    if (e && e.message) return e.message;
    return String(e);
  }

  // Parses "1-10, 15, 20-25" into a sorted array of unique page numbers.
  // Returns null for blank/whitespace-only input, meaning "all pages" —
  // callers must treat that as distinct from an empty array (which would
  // mean "select nothing"). Unparseable tokens are silently skipped
  // rather than rejecting the whole input — this is a quick text box,
  // not a strict format.
  function parsePageSelection(text) {
    const trimmed = String(text || '').trim();
    if (!trimmed) return null;
    const pages = new Set();
    trimmed.split(',').forEach(part => {
      const p = part.trim();
      if (!p) return;
      const range = p.match(/^(\d+)\s*-\s*(\d+)$/);
      if (range) {
        const start = parseInt(range[1], 10), end = parseInt(range[2], 10);
        for (let i = Math.min(start, end); i <= Math.max(start, end); i++) pages.add(i);
      } else if (/^\d+$/.test(p)) {
        pages.add(parseInt(p, 10));
      }
    });
    return Array.from(pages).sort((a, b) => a - b);
  }

  // Rebuilds page text from {text, boundingBox} words by visual row instead
  // of trusting the OCR engine's own block/paragraph grouping. Fixes the
  // case where a layout has a narrow side-column (e.g. right-margin verse
  // numbers) that the engine detects as its own block and appends wholesale
  // at the end of the page, rather than interleaved after each line.
  // Words with no boundingBox (shouldn't happen for Vision/Tesseract output,
  // but non-fatal if it does) are appended at the end, in their original order.
  function reconstructReadingOrder(words) {
    const placed = (words || []).filter(w => w && w.boundingBox);
    const unplaced = (words || []).filter(w => !w || !w.boundingBox);
    if (!placed.length) return (unplaced.map(w => w.text || '')).join(' ').trim();

    // Sort top-to-bottom first so rows get built in page order.
    const sorted = placed.slice().sort((a, b) => a.boundingBox.y - b.boundingBox.y);
    const rows = [];
    sorted.forEach(word => {
      const cy = word.boundingBox.y + word.boundingBox.height / 2;
      // A word joins the last row if its vertical center falls within that
      // row's band (half the word's own height as tolerance) — cheap and
      // good enough for the roughly-horizontal lines a scanned page has.
      const last = rows[rows.length - 1];
      if (last && Math.abs(cy - last.cy) <= Math.max(word.boundingBox.height, last.height) * 0.6) {
        last.words.push(word);
        last.cy = (last.cy * last.words.length + cy) / (last.words.length + 1);
      } else {
        rows.push({ cy, height: word.boundingBox.height, words: [word] });
      }
    });
    const lines = rows.map(row =>
      row.words.slice().sort((a, b) => a.boundingBox.x - b.boundingBox.x).map(w => w.text).join(' ')
    );
    if (unplaced.length) lines.push(unplaced.map(w => w.text || '').join(' '));
    return lines.join('\n').trim();
  }

  // Digit-script ranges actually seen in this project's sources (matches
  // the language hint chips in the Setup tab) -- each is a contiguous
  // 0-9 block in Unicode, so a single offset covers the whole script.
  const INDIC_DIGIT_BASES = [0x0966 /* devanagari */, 0x0ce6 /* kannada */, 0x0c66 /* telugu */,
    0x0be6 /* tamil */, 0x0d66 /* malayalam */, 0x09e6 /* bengali */];
  function digitCharToArabic(ch) {
    if (ch >= '0' && ch <= '9') return ch;
    const code = ch.codePointAt(0);
    for (let i = 0; i < INDIC_DIGIT_BASES.length; i++) {
      const base = INDIC_DIGIT_BASES[i];
      if (code >= base && code <= base + 9) return String(code - base);
    }
    return null;
  }

  // Looks for the LAST danda-delimited marker in the text (॥, | or ‖ on
  // both sides, e.g. "॥ १५ ॥") whose inner content is digits only (any
  // one supported script, not mixed) and converts it to a plain integer
  // -- this is the verse/shloka number actually printed on the page,
  // used to suggest where a partial OCR/Proofread batch's numbering
  // should start instead of always defaulting to 1. A compound marker
  // like "१.४४" (chapter.verse) is deliberately rejected (contains a
  // non-digit '.') rather than guessed at, since this project's
  // per-sarga files expect a single flat number, not a chapter.verse pair.
  function detectVerseNumber(text) {
    if (!text) return null;
    const re = /[॥|‖]\s*([^॥|‖]{1,6}?)\s*[॥|‖]/g;
    let match, lastNum = null;
    while ((match = re.exec(text)) !== null) {
      const inner = match[1].trim();
      if (!inner) continue;
      const arabicChars = inner.split('').map(digitCharToArabic);
      if (arabicChars.some(c => c === null)) continue;
      const n = parseInt(arabicChars.join(''), 10);
      if (Number.isFinite(n) && n > 0) lastNum = n;
    }
    return lastNum;
  }

  return {
    fileToBase64, downloadJson, saveProgress, loadProgress, clearProgress, parseJsonLoose, formatError,
    parsePageSelection, reconstructReadingOrder, detectVerseNumber
  };
})();
