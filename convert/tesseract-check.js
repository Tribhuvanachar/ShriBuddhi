// convert/tesseract-check.js — optional free second-opinion OCR via
// Tesseract.js (WASM, runs entirely in-browser), window.DGE.TesseractCheck
// namespace. Purely a cross-check signal against Vision's output for a
// human reviewer to act on — never blocks or fails the primary OCR run;
// every call site treats a cross-check failure as non-fatal.
window.DGE = window.DGE || {};
window.DGE.TesseractCheck = (function () {
  let worker = null;
  let workerLang = null;

  // Vision's languageHints use BCP-47/ISO-639-1 codes; Tesseract's
  // traineddata files use their own convention (mostly ISO-639-2/3-based).
  // Only the languages DGE is realistically likely to hit are mapped —
  // falls back to English rather than guessing at a traineddata filename
  // that doesn't exist for an unmapped code.
  const LANG_MAP = {
    kn: 'kan', sa: 'san', en: 'eng', hi: 'hin', ta: 'tam', te: 'tel',
    bn: 'ben', ml: 'mal', gu: 'guj', mr: 'mar', pa: 'pan', or: 'ori'
  };

  function mapLanguageHints(hints) {
    if (!hints || !hints.length) return 'eng';
    const mapped = hints.map(h => LANG_MAP[h]).filter(Boolean);
    return mapped.length ? mapped.join('+') : 'eng';
  }

  // One worker reused across every page in a run (recreated only if the
  // language changes) — recreating per page would re-download/re-init the
  // language data and WASM core every time, per Tesseract.js's own guidance.
  async function ensureWorker(lang) {
    if (worker && workerLang === lang) return worker;
    if (worker) await worker.terminate();
    if (typeof Tesseract === 'undefined') {
      throw new Error('Tesseract.js failed to load — check your internet connection.');
    }
    worker = await Tesseract.createWorker(lang);
    workerLang = lang;
    return worker;
  }

  // Returns {text, words} — words normalized to the same {text, confidence,
  // boundingBox:{x,y,width,height}} shape vision.js uses, so both engines'
  // output can be compared/rendered identically. Tesseract's confidence is
  // 0-100; rescaled to 0-1 to match Vision's scale.
  async function recognizeBase64Png(base64Png, lang) {
    const w = await ensureWorker(lang);
    const result = await w.recognize('data:image/png;base64,' + base64Png);
    const data = result && result.data;
    const words = ((data && data.words) || []).map(word => ({
      text: word.text || '',
      confidence: typeof word.confidence === 'number' ? word.confidence / 100 : null,
      boundingBox: word.bbox
        ? { x: word.bbox.x0, y: word.bbox.y0, width: word.bbox.x1 - word.bbox.x0, height: word.bbox.y1 - word.bbox.y0 }
        : null
    })).filter(w => w.text);
    return { text: (data && data.text) || '', words };
  }

  async function terminate() {
    if (worker) { await worker.terminate(); worker = null; workerLang = null; }
  }

  // --- similarity + word diff, purely string-level (no image involved) ---
  function normalize(s) {
    return String(s || '').normalize('NFC').replace(/\s+/g, ' ').trim();
  }

  // Character-level Levenshtein distance -> similarity ratio in [0,1].
  // O(n*m) on normalized page text (hundreds to low thousands of chars) —
  // fine at this scale, not something to run on whole books at once.
  function similarity(a, b) {
    a = normalize(a); b = normalize(b);
    if (!a && !b) return 1;
    if (!a || !b) return 0;
    const m = a.length, n = b.length;
    let prev = new Array(n + 1);
    let curr = new Array(n + 1);
    for (let j = 0; j <= n; j++) prev[j] = j;
    for (let i = 1; i <= m; i++) {
      curr[0] = i;
      for (let j = 1; j <= n; j++) {
        curr[j] = a[i - 1] === b[j - 1]
          ? prev[j - 1]
          : 1 + Math.min(prev[j], curr[j - 1], prev[j - 1]);
      }
      [prev, curr] = [curr, prev];
    }
    return 1 - prev[n] / Math.max(m, n);
  }

  // Word-level LCS diff — two parallel token arrays ({text, match}) for
  // side-by-side rendering with mismatches highlighted. Word-granularity
  // rather than character-granularity: readable at a glance, not a wall of
  // single-character highlight noise from any minor spacing difference.
  function wordDiff(a, b) {
    const wa = normalize(a).split(' ').filter(Boolean);
    const wb = normalize(b).split(' ').filter(Boolean);
    const m = wa.length, n = wb.length;
    const dp = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0));
    for (let i = m - 1; i >= 0; i--) {
      for (let j = n - 1; j >= 0; j--) {
        dp[i][j] = wa[i] === wb[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
      }
    }
    const outA = [], outB = [];
    let i = 0, j = 0;
    while (i < m && j < n) {
      if (wa[i] === wb[j]) { outA.push({ text: wa[i], match: true }); outB.push({ text: wb[j], match: true }); i++; j++; }
      else if (dp[i + 1][j] >= dp[i][j + 1]) { outA.push({ text: wa[i], match: false }); i++; }
      else { outB.push({ text: wb[j], match: false }); j++; }
    }
    while (i < m) { outA.push({ text: wa[i], match: false }); i++; }
    while (j < n) { outB.push({ text: wb[j], match: false }); j++; }
    return { a: outA, b: outB };
  }

  return { mapLanguageHints, recognizeBase64Png, terminate, similarity, wordDiff };
})();
