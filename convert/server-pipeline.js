// convert/server-pipeline.js — "Server Pipeline" tab, window.DGE.ServerPipeline
// namespace. A self-contained alternative to the local Upload/OCR/Proofread/
// Review/Push flow above: instead of running Vision+Gemini calls in THIS
// browser tab (which times out on a real book), it dispatches
// ocr-preview-pages.yml / ocr-sanskrit-commentary.yml on GitHub Actions
// (actions.js) and brings the result back for review here. Deliberately
// independent of app.js's state machine -- reuses only github.js's token
// and this page's existing styling.
window.DGE = window.DGE || {};
window.DGE.ServerPipeline = (function () {
  const $ = id => document.getElementById(id);
  let lastPreviewMeta = null;      // {total_pages, rendered_pages, out_of_range_pages}
  let lastPreviewImages = {};      // {pageNum: objectURL}
  let lastStaged = null;           // parsed staged.json
  let lastStagedFilename = null;

  function log(msg) {
    const el = $('spLog');
    if (!el) return;
    el.textContent += msg + '\n';
    el.scrollTop = el.scrollHeight;
  }

  function setStatus(msg) {
    const el = $('spStatus');
    if (el) el.textContent = msg || '';
  }

  // .error-box (shared with the rest of this page) defaults to
  // display:none in CSS and needs that toggled explicitly in JS -- same
  // convention as app.js's own setError()/clearError().
  function setSpError(msg) {
    const el = $('spError');
    if (!el) return;
    if (msg) { el.style.display = 'block'; el.textContent = msg; }
    else { el.style.display = 'none'; el.textContent = ''; }
  }

  function collectPdfInputs() {
    const url = $('spPdfUrl').value.trim();
    const p1 = $('spPdfUrlPart1').value.trim();
    const p2 = $('spPdfUrlPart2').value.trim();
    const p3 = $('spPdfUrlPart3').value.trim();
    if (url && p1) throw new Error('Give either a single PDF URL or split-7z part URLs, not both.');
    if (!url && !p1) throw new Error('Give a PDF URL, or at least the first split-7z part URL.');
    const inputs = {};
    if (url) {
      inputs.pdf_url = url;
    } else {
      inputs.pdf_url_part1 = p1;
      if (p2) inputs.pdf_url_part2 = p2;
      if (p3) inputs.pdf_url_part3 = p3;
    }
    return inputs;
  }

  function parsePageListLocal(spec) {
    const out = new Set();
    (spec || '').split(',').forEach(part => {
      part = part.trim();
      if (!part) return;
      if (part.includes('-')) {
        const [lo, hi] = part.split('-').map(n => parseInt(n, 10));
        for (let i = lo; i <= hi; i++) out.add(i);
      } else {
        out.add(parseInt(part, 10));
      }
    });
    return Array.from(out).filter(n => Number.isFinite(n)).sort((a, b) => a - b);
  }

  async function renderPreviewImages() {
    const strip = $('spPreviewStrip');
    strip.innerHTML = '';
    Object.keys(lastPreviewImages).map(Number).sort((a, b) => a - b).forEach(n => {
      const fig = document.createElement('figure');
      fig.className = 'sp-preview-page';
      const img = document.createElement('img');
      img.src = lastPreviewImages[n];
      img.alt = `Page ${n}`;
      const cap = document.createElement('figcaption');
      cap.textContent = `Page ${n}`;
      fig.appendChild(img);
      fig.appendChild(cap);
      strip.appendChild(fig);
    });
  }

  async function doPreview() {
    setSpError('');
    try {
      const pdfInputs = collectPdfInputs();
      const startPage = parseInt($('spStartPage').value, 10);
      const endPage = parseInt($('spEndPage').value, 10);
      if (!startPage || !endPage) throw new Error('Enter both a start page and an end page first.');
      const extra = parsePageListLocal($('spExtraPreviewPages').value);
      // preview the two boundary pages plus anything extra the admin
      // typed, capped so one click can't accidentally request hundreds
      const pages = Array.from(new Set([startPage, endPage, ...extra])).slice(0, 20).sort((a, b) => a - b);

      setStatus('Dispatching page preview workflow...');
      log(`Preview: pages [${pages.join(',')}]`);
      const { run, artifacts } = await window.DGE.Actions.runWorkflowAndWait(
        'ocr-preview-pages.yml',
        { ...pdfInputs, pages: pages.join(',') },
        { onProgress: r => setStatus(`Preview run ${r.status === 'completed' ? r.conclusion : r.status}...`) }
      );
      if (run.conclusion !== 'success') {
        throw new Error(`Preview run finished with conclusion "${run.conclusion}" — check it on GitHub: ${run.html_url}`);
      }
      const artifact = artifacts.find(a => a.name === 'page-preview');
      if (!artifact) throw new Error('Preview run succeeded but produced no "page-preview" artifact.');

      setStatus('Downloading preview images...');
      const zipBuf = await window.DGE.Actions.downloadArtifactZip(artifact.id);
      const files = await window.DGE.ZipRead.extractAll(zipBuf);

      const metaFile = files.find(f => f.name.endsWith('meta.json'));
      lastPreviewMeta = metaFile ? JSON.parse(new TextDecoder().decode(metaFile.bytes)) : null;

      Object.values(lastPreviewImages).forEach(url => URL.revokeObjectURL(url));
      lastPreviewImages = {};
      files.filter(f => /page-(\d+)\.png$/.test(f.name)).forEach(f => {
        const n = parseInt(f.name.match(/page-(\d+)\.png$/)[1], 10);
        lastPreviewImages[n] = URL.createObjectURL(new Blob([f.bytes], { type: 'image/png' }));
      });
      await renderPreviewImages();

      if (lastPreviewMeta) {
        $('spPreviewMeta').textContent = `PDF has ${lastPreviewMeta.total_pages} page(s) total.` +
          (lastPreviewMeta.out_of_range_pages.length
            ? ` Out of range (ignored): ${lastPreviewMeta.out_of_range_pages.join(', ')}.` : '');
        if (endPage > lastPreviewMeta.total_pages) {
          setSpError(`Warning: end page ${endPage} is past this PDF's last page (${lastPreviewMeta.total_pages}).`);
        }
      }
      setStatus('Preview ready — check the pages below before sending for OCR.');
      log('Preview complete.');
    } catch (e) {
      setSpError(e.message || String(e));
      setStatus('');
      log('Preview error: ' + (e.message || e));
    }
  }

  function renderStagedShlokas() {
    const area = $('spJsonView');
    if (!lastStaged) { area.innerHTML = ''; return; }
    const counts = { accept: 0, review: 0, unresolved: 0 };
    (lastStaged.shlokas || []).forEach(s => { counts[s.classification] = (counts[s.classification] || 0) + 1; });
    const summary = document.createElement('p');
    summary.className = 'hint';
    summary.textContent = `${(lastStaged.shlokas || []).length} shloka(s): ` +
      `${counts.accept || 0} accept, ${counts.review || 0} review, ${counts.unresolved || 0} unresolved.`;

    const list = document.createElement('div');
    list.className = 'sp-shloka-list';
    (lastStaged.shlokas || []).forEach(s => {
      const row = document.createElement('div');
      row.className = `sp-shloka-row sp-cls-${s.classification || 'unresolved'}`;
      row.innerHTML = `<b>#${s.number != null ? s.number : '?'}</b> ` +
        `<span class="sp-badge">${s.classification || 'unresolved'}</span>` +
        (s.note ? ` <span class="hint">${escapeHtml(s.note)}</span>` : '') +
        `<div class="sp-sa">${escapeHtml(s.sa || '')}</div>` +
        (s.commentary ? `<div class="sp-commentary">${escapeHtml(s.commentary)}</div>` : '');
      list.appendChild(row);
    });

    const raw = document.createElement('details');
    raw.innerHTML = `<summary>Raw JSON</summary><pre class="sp-raw-json">${escapeHtml(JSON.stringify(lastStaged, null, 1))}</pre>`;

    area.innerHTML = '';
    area.appendChild(summary);
    area.appendChild(list);
    area.appendChild(raw);
  }

  function escapeHtml(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, c =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  async function doRunOcr() {
    setSpError('');
    try {
      const pdfInputs = collectPdfInputs();
      const startPage = parseInt($('spStartPage').value, 10);
      const endPage = parseInt($('spEndPage').value, 10);
      const excludePages = $('spExcludePages').value.trim();
      const workSlug = $('spWorkSlug').value.trim();
      const canto = $('spCanto').value.trim();
      const commentaryKey = $('spCommentaryKey').value.trim();
      const displayLabel = $('spDisplayLabel').value.trim();
      const contextAnchor = $('spContextAnchor').value.trim();
      const contentField = $('spContentField').value;
      const model = $('spModel').value;

      if (!startPage || !endPage) throw new Error('Enter both a start page and an end page.');
      if (!workSlug || !canto || !commentaryKey || !displayLabel) {
        throw new Error('Work slug, canto, commentary key, and display label are all required.');
      }
      if (!confirm(`Send pages ${startPage}-${endPage} for OCR + Gemini proofreading?\n\n` +
        `This calls the Vision and Gemini APIs (real, billed usage) and stages the result — ` +
        `it will NOT be merged into the corpus yet.`)) {
        return;
      }

      setStatus('Dispatching OCR + proofread workflow — this can take a few minutes for a real page range...');
      log(`OCR run: pages ${startPage}-${endPage}, exclude [${excludePages}], key=${commentaryKey}`);
      const { run, artifacts } = await window.DGE.Actions.runWorkflowAndWait(
        'ocr-sanskrit-commentary.yml',
        {
          ...pdfInputs,
          start_page: String(startPage), end_page: String(endPage), exclude_pages: excludePages,
          work_slug: workSlug, canto: String(canto), commentary_key: commentaryKey,
          display_label: displayLabel, context_anchor: contextAnchor, content_field: contentField,
          model, also_merge: false,
        },
        { timeoutMs: 30 * 60 * 1000, onProgress: r => setStatus(`OCR run ${r.status === 'completed' ? r.conclusion : r.status}...`) }
      );
      if (run.conclusion !== 'success') {
        throw new Error(`OCR run finished with conclusion "${run.conclusion}" — check the log on GitHub: ${run.html_url}`);
      }
      const artifact = artifacts.find(a => a.name === 'staged-commentary');
      if (!artifact) throw new Error('OCR run succeeded but produced no "staged-commentary" artifact.');

      setStatus('Downloading staged result...');
      const zipBuf = await window.DGE.Actions.downloadArtifactZip(artifact.id);
      const files = await window.DGE.ZipRead.extractAll(zipBuf);
      const stagedFile = files.find(f => f.name.endsWith('.json'));
      if (!stagedFile) throw new Error('Artifact had no .json file inside.');
      lastStaged = JSON.parse(new TextDecoder().decode(stagedFile.bytes));
      lastStagedFilename = `${commentaryKey}_canto${canto}_pages${startPage}-${endPage}.json`;
      renderStagedShlokas();

      $('spOutputActions').style.display = '';
      setStatus('Done — review the output below.');
      log('OCR run complete, staged output loaded.');
    } catch (e) {
      setSpError(e.message || String(e));
      setStatus('');
      log('OCR run error: ' + (e.message || e));
    }
  }

  function downloadStagedJson() {
    if (!lastStaged) return;
    const blob = new Blob([JSON.stringify(lastStaged, null, 1)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = lastStagedFilename || 'staged.json';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  async function shareStagedJson() {
    if (!lastStaged) return;
    const blob = new Blob([JSON.stringify(lastStaged, null, 1)], { type: 'application/json' });
    const file = new File([blob], lastStagedFilename || 'staged.json', { type: 'application/json' });
    if (navigator.canShare && navigator.canShare({ files: [file] })) {
      try {
        await navigator.share({ files: [file], title: 'DGE OCR staged commentary' });
      } catch (e) {
        if (e.name !== 'AbortError') setSpError('Share failed: ' + (e.message || e));
      }
    } else {
      setSpError('Web Share (with file attachments) isn\'t available in this browser — ' +
        'download the JSON instead and attach it manually to an email.');
    }
  }

  async function pushToStaging() {
    setSpError('');
    if (!lastStaged) return;
    try {
      const path = `data/ocr_staging/${lastStaged.work_slug}/${lastStagedFilename}`;
      if (!confirm(`Push this staged file to ${path} on main?\n\n` +
        `This does NOT merge it into the corpus — it's a separate later step ` +
        `(tools/merge_staged_commentary.py) that reads staged files from this folder.`)) {
        return;
      }
      setStatus('Pushing staged file to the repo...');
      const result = await window.DGE.GitHub.commitFiles(
        [{ path, text: JSON.stringify(lastStaged, null, 1) + '\n' }],
        `data: stage OCR commentary '${lastStaged.commentary_key}' for ${lastStaged.work_slug} canto ${lastStaged.canto}`
      );
      setStatus(result.uploaded ? `Pushed to ${path}.` : 'No change — an identical file is already staged there.');
      log(`Pushed staged file to ${path} (uploaded=${result.uploaded}, unchanged=${result.unchanged}).`);
    } catch (e) {
      setSpError(e.message || String(e));
      setStatus('');
    }
  }

  function init() {
    $('spPreviewBtn').addEventListener('click', doPreview);
    $('spRunOcrBtn').addEventListener('click', doRunOcr);
    $('spDownloadBtn').addEventListener('click', downloadStagedJson);
    $('spShareBtn').addEventListener('click', shareStagedJson);
    $('spPushBtn').addEventListener('click', pushToStaging);
  }

  return { init };
})();
