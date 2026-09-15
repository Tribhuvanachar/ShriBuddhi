// convert/review-ui.js — focused review panel for proofread units
// flagged by review-classifier.js (C/D/E), window.DGE.ReviewUI namespace.
// Reads straight from window.DGE.App's exported finalJson/ocrPages, so it
// always reflects whatever the last Proofread run actually produced —
// no separate copy of the data to keep in sync.
window.DGE = window.DGE || {};
window.DGE.ReviewUI = (function () {
  let queue = [];   // indices into finalJson.shlokas currently queued for review
  let queuePos = -1;
  let onProgress = null; // caller-supplied callback, fired after every accept/edit/unresolved

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
  }

  function ocrPageFor(pageNum) {
    const pages = window.DGE.App.getOcrPages() || [];
    return pages.find(p => p.page === pageNum);
  }

  // Counts by class, and how many of the flagged (C/D/E) ones already have
  // a human decision recorded — used both for the queue itself and for the
  // one-line summary shown before the queue is opened.
  function summary() {
    const finalJson = window.DGE.App.getFinalJson();
    const shlokas = (finalJson && finalJson.shlokas) || [];
    const counts = { A: 0, B: 0, C: 0, D: 0, E: 0 };
    let flaggedReviewed = 0, flaggedTotal = 0;
    shlokas.forEach(s => {
      if (s.reviewClass) counts[s.reviewClass]++;
      if (s.reviewClass === 'C' || s.reviewClass === 'D' || s.reviewClass === 'E') {
        flaggedTotal++;
        if (s.humanReviewed) flaggedReviewed++;
      }
    });
    return { counts, total: shlokas.length, flaggedTotal, flaggedReviewed };
  }

  function buildQueue(includeC) {
    const finalJson = window.DGE.App.getFinalJson();
    const shlokas = (finalJson && finalJson.shlokas) || [];
    const classes = includeC ? ['C', 'D', 'E'] : ['D', 'E'];
    queue = [];
    shlokas.forEach((s, i) => {
      if (classes.indexOf(s.reviewClass) !== -1 && !s.humanReviewed) queue.push(i);
    });
    return queue;
  }

  // Draws the page's master image at native resolution (CSS scales it down
  // responsively without touching the coordinate space, so the highlight
  // boxes — in original-image pixel coordinates — line up regardless of
  // display size) and outlines every word Vision itself wasn't confident
  // about, so the reviewer's eye goes straight to the actual uncertain
  // region instead of re-reading the whole page.
  function renderPageCanvas(canvas, ocrPage) {
    return new Promise(resolve => {
      if (!ocrPage || !ocrPage.masterImage) { resolve(); return; }
      const img = new Image();
      img.onload = () => {
        canvas.width = img.naturalWidth;
        canvas.height = img.naturalHeight;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0);
        (ocrPage.words || []).forEach(w => {
          if (!w.boundingBox || w.confidence == null || w.confidence >= 0.85) return;
          ctx.strokeStyle = '#e02020';
          ctx.lineWidth = Math.max(2, img.naturalWidth / 400);
          ctx.strokeRect(w.boundingBox.x, w.boundingBox.y, w.boundingBox.width, w.boundingBox.height);
        });
        resolve();
      };
      img.onerror = () => resolve();
      img.src = 'data:image/png;base64,' + ocrPage.masterImage;
    });
  }

  function renderDetail(container) {
    const finalJson = window.DGE.App.getFinalJson();
    if (!queue.length) {
      container.innerHTML = '<p>✅ Nothing left in the queue — every flagged unit has a recorded decision.</p>';
      return;
    }
    const idx = queue[queuePos];
    const s = finalJson.shlokas[idx];
    const ocrPage = ocrPageFor(s.page);
    const label = (window.DGE.ReviewClassifier.LABELS[s.reviewClass]) || s.reviewClass;

    container.innerHTML =
      '<div class="review-nav">' +
        '<button id="reviewPrevBtn"' + (queuePos <= 0 ? ' disabled' : '') + '>← Prev</button>' +
        '<span>' + (queuePos + 1) + ' / ' + queue.length + ' flagged (unit #' + (s.index != null ? s.index : idx + 1) + ', page ' + (s.page != null ? s.page : '?') + ')</span>' +
        '<button id="reviewNextBtn"' + (queuePos >= queue.length - 1 ? ' disabled' : '') + '>Next →</button>' +
      '</div>' +
      '<div class="review-badge review-badge-' + s.reviewClass + '">Class ' + s.reviewClass + ' — ' + esc(label) + '</div>' +
      (s.note ? '<div class="review-note"><b>Gemini’s reasoning:</b> ' + esc(s.note) + '</div>' : '') +
      (ocrPage && ocrPage.masterImage
        ? '<canvas id="reviewCanvas" class="review-canvas"></canvas><p class="hint">Red boxes = words Vision itself flagged as low-confidence on this page.</p>'
        : '<p class="hint">No stored page image for page ' + esc(s.page) + ' (OCR predates this feature, or ran without page images).</p>') +
      '<div class="review-candidates">' +
        '<div><b>Vision — full page ' + esc(s.page) + '</b><div class="review-cand-text">' + esc(ocrPage ? ocrPage.text : '(page not found in this OCR run)') + '</div></div>' +
        (ocrPage && ocrPage.crossCheck ? '<div><b>Tesseract — full page</b><div class="review-cand-text">' + esc(ocrPage.crossCheck.text) + '</div></div>' : '') +
      '</div>' +
      '<label class="hint">Gemini’s corrected text (editable)</label>' +
      '<textarea id="reviewSaInput" rows="3">' + esc(s.sa) + '</textarea>' +
      '<label class="hint">Commentary (editable)</label>' +
      '<textarea id="reviewCommentaryInput" rows="2">' + esc(s.commentary || '') + '</textarea>' +
      '<div class="review-actions">' +
        '<button id="reviewAcceptBtn">✅ Accept as-is</button>' +
        '<button id="reviewSaveEditBtn">✏️ Save my edit</button>' +
        '<button id="reviewUnresolvedBtn">⚠ Mark unresolved</button>' +
      '</div>';

    if (ocrPage && ocrPage.masterImage) {
      renderPageCanvas(container.querySelector('#reviewCanvas'), ocrPage);
    }

    const prevBtn = container.querySelector('#reviewPrevBtn');
    const nextBtn = container.querySelector('#reviewNextBtn');
    if (prevBtn) prevBtn.onclick = () => { if (queuePos > 0) { queuePos--; renderDetail(container); } };
    if (nextBtn) nextBtn.onclick = () => { if (queuePos < queue.length - 1) { queuePos++; renderDetail(container); } };
    container.querySelector('#reviewAcceptBtn').onclick = () => decide(container, idx, 'accepted');
    container.querySelector('#reviewUnresolvedBtn').onclick = () => decide(container, idx, 'unresolved');
    container.querySelector('#reviewSaveEditBtn').onclick = () => {
      s.sa = container.querySelector('#reviewSaInput').value;
      s.commentary = container.querySelector('#reviewCommentaryInput').value;
      decide(container, idx, 'edited');
    };
  }

  // Records the human decision directly on the shloka (so it travels with
  // the data into the schema mapper and the eventual pushed JSON — nothing
  // about this is a separate, easy-to-lose side table), removes it from the
  // active queue, and lands on whatever's now at the same position.
  function decide(container, idx, status) {
    const finalJson = window.DGE.App.getFinalJson();
    finalJson.shlokas[idx].humanReviewed = status;
    const posInQueue = queue.indexOf(idx);
    if (posInQueue !== -1) queue.splice(posInQueue, 1);
    if (queuePos >= queue.length) queuePos = queue.length - 1;
    renderDetail(container);
    if (typeof onProgress === 'function') onProgress();
  }

  function renderSummary(el) {
    if (!el) return;
    const sum = summary();
    if (!sum.total) { el.textContent = 'Run Proofread first.'; return; }
    const parts = Object.keys(sum.counts).map(k => k + ':' + sum.counts[k]).join(' ');
    el.textContent = `${sum.total} unit(s) — ${parts}. ${sum.flaggedReviewed}/${sum.flaggedTotal} flagged unit(s) reviewed.`;
  }

  function open(containerEl, includeC, progressCallback) {
    onProgress = progressCallback || null;
    buildQueue(includeC);
    queuePos = 0;
    renderDetail(containerEl);
  }

  return { open, summary, renderSummary, buildQueue };
})();
