// convert/renderer.js — preview rendering, window.DGE.Renderer namespace
window.DGE = window.DGE || {};
window.DGE.Renderer = (function () {

  function escapeHtml(str) {
    return String(str == null ? '' : str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  function renderPreview(dgeJson, containerEl) {
    if (!containerEl) return;
    if (!dgeJson || !Array.isArray(dgeJson.shlokas) || !dgeJson.shlokas.length) {
      containerEl.innerHTML = '<p>No shloka data to preview yet.</p>';
      return;
    }
    let html = '';
    dgeJson.shlokas.forEach(function (s) {
      html += '<div class="preview-shloka">';
      html += '<div class="preview-num">Shloka ' + (s.number != null ? s.number : (s.index != null ? s.index : '')) + '</div>';
      html += '<div class="preview-sa">' + escapeHtml(s.sa || '') + '</div>';
      if (s.commentary) {
        html += '<div class="preview-commentary">' + escapeHtml(s.commentary) + '</div>';
      }
      html += '</div>';
    });
    containerEl.innerHTML = html;
  }

  function renderRawOcr(ocrPages, containerEl) {
    if (!containerEl) return;
    if (!ocrPages || !ocrPages.length) {
      containerEl.innerHTML = '<p>No OCR data to preview yet.</p>';
      return;
    }
    let html = '';
    ocrPages.forEach(function (p) {
      html += '<div class="preview-raw-page">';
      html += '<div class="preview-num">Page ' + (p.page != null ? p.page : '') + (p.engine === 'tesseract' ? ' (Tesseract.js only)' : '') + '</div>';
      // Vision's own per-word confidence — not proof of correctness, but a
      // real, free signal for which words are worth a human double-checking
      // instead of re-reading every single page start to finish. Tesseract-only
      // pages have no comparable summarized confidence, so this whole block
      // is skipped for them rather than showing a fabricated number.
      if (typeof p.avgConfidence === 'number') {
        const pct = Math.round(p.avgConfidence * 100);
        const cls = pct >= 90 ? 'conf-good' : (pct >= 75 ? 'conf-mid' : 'conf-low');
        html += '<div class="preview-confidence ' + cls + '">Vision confidence: ' + pct + '%';
        if (p.lowConfidenceWords && p.lowConfidenceWords.length) {
          html += ' — ' + p.lowConfidenceWords.length + ' word(s) worth checking: ';
          html += p.lowConfidenceWords.map(function (w) {
            return '<span class="low-conf-word" title="' + Math.round(w.confidence * 100) + '% confidence">' + escapeHtml(w.text) + '</span>';
          }).join(' ');
        }
        html += '</div>';
      }
      html += '<div class="preview-raw-text">' + escapeHtml(p.text || '(no text detected)') + '</div>';
      // Tesseract cross-check, when the opt-in checkbox was on for this run —
      // a real independent-agreement signal, word-diffed against Vision's
      // text so a mismatch is visible at a glance rather than requiring a
      // full re-read of both texts side by side.
      if (p.crossCheck) {
        const pct = Math.round(p.crossCheck.similarity * 100);
        const cls = pct >= 90 ? 'conf-good' : (pct >= 70 ? 'conf-mid' : 'conf-low');
        html += '<div class="preview-confidence ' + cls + '">Tesseract cross-check: ' + pct + '% similar to Vision' + (pct < 70 ? ' — low agreement, worth checking' : '') + '</div>';
        const diff = window.DGE.TesseractCheck.wordDiff(p.text, p.crossCheck.text);
        html += '<div class="crosscheck-diff"><div class="crosscheck-col"><div class="crosscheck-label">Vision</div>' +
          diff.a.map(w => '<span class="' + (w.match ? '' : 'diff-mismatch') + '">' + escapeHtml(w.text) + '</span>').join(' ') + '</div>';
        html += '<div class="crosscheck-col"><div class="crosscheck-label">Tesseract</div>' +
          diff.b.map(w => '<span class="' + (w.match ? '' : 'diff-mismatch') + '">' + escapeHtml(w.text) + '</span>').join(' ') + '</div></div>';
      }
      html += '</div>';
    });
    containerEl.innerHTML = html;
  }

  function rowHtml(key, sa, commentaryText) {
    return '<div class="schema-row" data-key="' + escapeHtml(key) + '">' +
      '<div class="schema-row-toolbar">' +
        '<span class="preview-num">Shloka ' + escapeHtml(key) + '</span>' +
        '<button type="button" class="row-btn row-move-up" title="Move up">&#9650;</button>' +
        '<button type="button" class="row-btn row-move-down" title="Move down">&#9660;</button>' +
        '<input type="number" class="row-move-to-input" placeholder="#" title="Move to position...">' +
        '<button type="button" class="row-btn row-move-to-btn" title="Move to the position typed on the left">Move</button>' +
        '<button type="button" class="row-btn row-insert-after" title="Insert a new blank shloka right after this one">+ shloka</button>' +
        '<button type="button" class="row-btn row-split-after" title="End the sarga here -- everything after this shloka becomes a new, separately-numbered sarga block">&#9986; split sarga after this</button>' +
        '<button type="button" class="row-btn row-delete" title="Delete this shloka (renumbers everything after it)">&#10005; delete</button>' +
      '</div>' +
      '<label class="hint">Sanskrit</label>' +
      '<textarea class="schema-sa-input" rows="2">' + escapeHtml(sa || '') + '</textarea>' +
      '<label class="hint">Commentary</label>' +
      '<textarea class="schema-commentary-input" rows="3">' + escapeHtml(commentaryText || '') + '</textarea>' +
    '</div>';
  }

  // Keeps each row's displayed/collected number in sync with its actual DOM
  // position -- this is what lets delete/move/insert "just work" without any
  // separate bookkeeping: the key is ALWAYS "position + startAt", recomputed
  // right after every structural change.
  function renumberRows(containerEl, startAt) {
    const start = startAt || 1;
    const rows = containerEl.querySelectorAll('.schema-row');
    rows.forEach(function (row, i) {
      const key = String(start + i);
      row.setAttribute('data-key', key);
      const numEl = row.querySelector('.preview-num');
      if (numEl) numEl.textContent = 'Shloka ' + key;
    });
  }

  // Renders the mapped grantha schema as an EDITABLE table — one row per
  // shloka, Sanskrit and commentary each in their own textarea, plus a
  // per-row toolbar (move/insert/split/delete) — so the admin can fix
  // structural mistakes (a stray page, a wrongly-merged sarga boundary, a
  // shloka OCR split in two) without leaving this screen or re-running
  // OCR/Proofread. Deliberately editable rather than read-only: this is the
  // last checkpoint before content goes live. `startAt` lets a segment that
  // doesn't begin at shloka 1 (rare, only if the admin overrides it) render
  // with the right opening number.
  function renderSchemaMapEditable(mappedJson, containerEl, startAt) {
    if (!containerEl) return;
    const keys = Object.keys(mappedJson.shlokas || {}).sort((a, b) => Number(a) - Number(b));
    if (!keys.length) {
      containerEl.innerHTML = '<p>Nothing to preview — build the schema first.</p>';
      return;
    }
    let html = '';
    keys.forEach(function (k) {
      const s = mappedJson.shlokas[k];
      const cKeys = Object.keys(s.commentaries || {});
      html += rowHtml(k, s.sa, cKeys.length ? s.commentaries[cKeys[0]] : '');
    });
    containerEl.innerHTML = html;
    if (startAt && startAt !== 1) renumberRows(containerEl, startAt);
    wireRowToolbar(containerEl);
  }

  // Event delegation on the container -- rows come and go (insert/delete/
  // split), so listeners are attached once on the stable parent rather than
  // per-row. "Split" is the one operation that can create a whole new
  // segment (a new file to push), which is app.js's concern, not this
  // module's -- it's surfaced as a bubbling CustomEvent instead of a direct
  // call, keeping this module ignorant of what a "segment" even is.
  function notifyChanged(containerEl) {
    containerEl.dispatchEvent(new CustomEvent('dge-schema-changed', { bubbles: true }));
  }

  function wireRowToolbar(containerEl) {
    if (containerEl._dgeToolbarWired) return;
    containerEl._dgeToolbarWired = true;
    containerEl.addEventListener('input', function (e) {
      if (e.target.classList.contains('schema-sa-input') || e.target.classList.contains('schema-commentary-input')) {
        notifyChanged(containerEl);
      }
    });
    containerEl.addEventListener('click', function (e) {
      const row = e.target.closest ? e.target.closest('.schema-row') : null;
      if (!row) return;

      if (e.target.classList.contains('row-move-up')) {
        const prev = row.previousElementSibling;
        if (prev && prev.classList.contains('schema-row')) {
          row.parentNode.insertBefore(row, prev);
          renumberRows(containerEl);
          notifyChanged(containerEl);
        }
        return;
      }
      if (e.target.classList.contains('row-move-down')) {
        const next = row.nextElementSibling;
        if (next && next.classList.contains('schema-row')) {
          row.parentNode.insertBefore(next, row);
          renumberRows(containerEl);
          notifyChanged(containerEl);
        }
        return;
      }
      if (e.target.classList.contains('row-move-to-btn')) {
        const input = row.querySelector('.row-move-to-input');
        const target = parseInt(input && input.value, 10);
        if (!Number.isFinite(target) || target < 1) return;
        const rows = Array.from(containerEl.querySelectorAll('.schema-row'));
        const clampedIdx = Math.max(0, Math.min(rows.length - 1, target - 1));
        const ref = rows[clampedIdx];
        if (ref === row) return;
        // Insert before the row currently sitting at the target position --
        // matches "type 45, this shloka goes and sits in the 45th spot".
        const refIdx = rows.indexOf(ref);
        const curIdx = rows.indexOf(row);
        row.parentNode.removeChild(row);
        containerEl.insertBefore(row, curIdx < refIdx ? ref.nextElementSibling : ref);
        renumberRows(containerEl);
        if (input) input.value = '';
        notifyChanged(containerEl);
        return;
      }
      if (e.target.classList.contains('row-insert-after')) {
        const blank = document.createElement('div');
        blank.innerHTML = rowHtml('', '', '');
        row.parentNode.insertBefore(blank.firstElementChild, row.nextSibling);
        renumberRows(containerEl);
        notifyChanged(containerEl);
        return;
      }
      if (e.target.classList.contains('row-delete')) {
        const rows = containerEl.querySelectorAll('.schema-row');
        if (rows.length <= 1) {
          alert('A sarga needs at least one shloka -- delete the whole block instead if this file should go away entirely.');
          return;
        }
        row.parentNode.removeChild(row);
        renumberRows(containerEl);
        notifyChanged(containerEl);
        return;
      }
      if (e.target.classList.contains('row-split-after')) {
        containerEl.dispatchEvent(new CustomEvent('dge-split-sarga', {
          bubbles: true, detail: { afterRow: row, containerEl: containerEl }
        }));
        return;
      }
    });
  }

  // Reads the (possibly admin-edited) textareas back out of the DOM into
  // the real shlokas object shape — this is what actually gets pushed,
  // not the original un-edited mapper output. Renumbers first so a row
  // that was moved/inserted/deleted just before Push always collects under
  // its true current position, never a stale data-key.
  function collectEditedShlokas(containerEl, commentaryKey, startAt) {
    renumberRows(containerEl, startAt || 1);
    const rows = containerEl.querySelectorAll('.schema-row');
    const shlokas = {};
    rows.forEach(function (row) {
      const key = row.getAttribute('data-key');
      const sa = row.querySelector('.schema-sa-input').value;
      const commentary = row.querySelector('.schema-commentary-input').value;
      const commentaries = {};
      if (commentaryKey && commentary) commentaries[commentaryKey] = commentary;
      shlokas[key] = { sa: sa, commentaries: commentaries };
    });
    return shlokas;
  }

  return { renderPreview, renderRawOcr, renderSchemaMapEditable, collectEditedShlokas, renumberRows };
})();
