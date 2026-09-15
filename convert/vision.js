// convert/vision.js — Google Cloud Vision OCR, window.DGE.Vision namespace.
// Confirmed working via direct browser fetch (no CORS block) before this
// was built — see convert/cors-test.html.
window.DGE = window.DGE || {};
window.DGE.Vision = (function () {

  async function ocrImageBase64(base64Png, apiKey, languageHints) {
    const url = `https://vision.googleapis.com/v1/images:annotate?key=${encodeURIComponent(apiKey)}`;
    const request = {
      image: { content: base64Png },
      // DOCUMENT_TEXT_DETECTION, not TEXT_DETECTION — Google's own guidance is
      // that this feature is the one tuned for dense document/book-page text;
      // TEXT_DETECTION targets sparse scene text (signs, labels) and is a worse
      // fit for a full scanned page. Also gives per-symbol confidence scores,
      // which TEXT_DETECTION's plain fullTextAnnotation.text throws away.
      features: [{ type: 'DOCUMENT_TEXT_DETECTION' }]
    };
    if (languageHints && languageHints.length) {
      request.imageContext = { languageHints };
    }
    const body = { requests: [request] };

    let res;
    try {
      res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
    } catch (e) {
      throw new Error('Network error reaching Vision API — check your connection: ' + e.message);
    }

    const data = await res.json().catch(() => ({}));

    if (!res.ok) {
      const msg = (data.error && data.error.message) || `HTTP ${res.status}`;
      if (res.status === 401 || res.status === 403) throw new Error('Vision API key rejected, or the API isn\'t enabled on that project: ' + msg);
      if (res.status === 429) throw new Error('Vision API quota exceeded — wait and retry, or check your Cloud project\'s quota: ' + msg);
      throw new Error('Vision API error: ' + msg);
    }

    const annotation = data.responses && data.responses[0];
    if (annotation && annotation.error) {
      throw new Error('Vision API returned an error for this page: ' + annotation.error.message);
    }
    const fta = annotation && annotation.fullTextAnnotation;
    if (!fta) return { text: '', avgConfidence: null, lowConfidenceWords: [], words: [] };
    const words = extractWords(fta);
    return { text: fta.text || '', words, ...summarizeConfidence(words) };
  }

  // Flattens Vision's page/block/paragraph/word/symbol tree into one array
  // of {text, confidence, boundingBox} per word. This — not the deeply
  // nested raw response — is what "immutable OCR evidence" actually needs
  // to be reproducible and reviewable: every word's text, confidence, and
  // on-page location, with none of the redundant structural nesting. Vision
  // reports each vertex of a (usually axis-aligned) quadrilateral; normalized
  // here to a plain {x, y, width, height} box for direct use when cropping
  // the source image later.
  function extractWords(fta) {
    const words = [];
    (fta.pages || []).forEach(page => {
      (page.blocks || []).forEach(block => {
        (block.paragraphs || []).forEach(para => {
          (para.words || []).forEach(word => {
            const text = (word.symbols || []).map(s => s.text || '').join('');
            if (!text) return;
            words.push({
              text,
              confidence: typeof word.confidence === 'number' ? word.confidence : null,
              boundingBox: normalizeBoundingBox(word.boundingBox)
            });
          });
        });
      });
    });
    return words;
  }

  function normalizeBoundingBox(bb) {
    const verts = bb && bb.vertices;
    if (!verts || !verts.length) return null;
    const xs = verts.map(v => v.x || 0), ys = verts.map(v => v.y || 0);
    const x = Math.min(...xs), y = Math.min(...ys);
    return { x, y, width: Math.max(...xs) - x, height: Math.max(...ys) - y };
  }

  // Vision's own per-word confidence (0-1) — a real, cheap signal for which
  // words are worth a human double-checking, without needing a second OCR
  // pass or any ground truth to compare against.
  const LOW_CONFIDENCE_THRESHOLD = 0.85;
  function summarizeConfidence(words) {
    let sum = 0, count = 0;
    const lowConfidenceWords = [];
    words.forEach(word => {
      if (typeof word.confidence !== 'number') return;
      sum += word.confidence;
      count++;
      if (word.confidence < LOW_CONFIDENCE_THRESHOLD) {
        lowConfidenceWords.push({ text: word.text, confidence: word.confidence });
      }
    });
    return {
      avgConfidence: count ? sum / count : null,
      lowConfidenceWords
    };
  }

  // Sends several pages in ONE HTTP call instead of one call per page --
  // Vision's images:annotate endpoint already accepts multiple entries in
  // its "requests" array, each returning its own independent result, so
  // this is a real reduction in network round-trips (not a change to how
  // much Vision itself charges or how fast it OCRs any single image) --
  // over a large book, the per-request overhead (TLS handshake, HTTP
  // headers, this browser's own request queuing) adds up across hundreds
  // of individual calls. Deliberately conservative: a single bad or
  // erroring page in the batch fails the WHOLE batch (thrown, same as any
  // other Vision error) rather than trying to salvage the good ones
  // out-of-order -- keeps the exact same "halts cleanly, nothing after
  // the failure point is trusted, everything before it is already saved"
  // resume model runOcr() already relies on, just with a coarser unit.
  async function ocrImagesBatch(images, apiKey, languageHints) {
    const url = `https://vision.googleapis.com/v1/images:annotate?key=${encodeURIComponent(apiKey)}`;
    const requests = images.map(img => {
      const req = { image: { content: img.base64Png }, features: [{ type: 'DOCUMENT_TEXT_DETECTION' }] };
      if (languageHints && languageHints.length) req.imageContext = { languageHints };
      return req;
    });

    let res;
    try {
      res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ requests })
      });
    } catch (e) {
      throw new Error('Network error reaching Vision API — check your connection: ' + e.message);
    }

    const data = await res.json().catch(() => ({}));

    if (!res.ok) {
      const msg = (data.error && data.error.message) || `HTTP ${res.status}`;
      if (res.status === 401 || res.status === 403) throw new Error('Vision API key rejected, or the API isn\'t enabled on that project: ' + msg);
      if (res.status === 429) throw new Error('Vision API quota exceeded — wait and retry, or check your Cloud project\'s quota: ' + msg);
      throw new Error('Vision API error: ' + msg);
    }

    const responses = data.responses || [];
    return images.map((img, i) => {
      const annotation = responses[i];
      if (!annotation) throw new Error(`Vision API returned no result for page ${img.page} (batch of ${images.length}).`);
      if (annotation.error) throw new Error(`Vision API returned an error for page ${img.page}: ${annotation.error.message}`);
      const fta = annotation.fullTextAnnotation;
      if (!fta) return { page: img.page, text: '', avgConfidence: null, lowConfidenceWords: [], words: [] };
      const words = extractWords(fta);
      return { page: img.page, text: fta.text || '', words, ...summarizeConfidence(words) };
    });
  }

  return { ocrImageBase64, ocrImagesBatch };
})();
