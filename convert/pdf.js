// convert/pdf.js — PDF.js integration, window.DGE.PDF namespace.
// Deliberately renders ONE page at a time and lets the canvas be
// released immediately after — this app is primarily used on a phone,
// and holding many rendered canvases in memory simultaneously for a
// large scanned book is a real crash risk on mobile.
window.DGE = window.DGE || {};
window.DGE.PDF = (function () {
  let currentDoc = null;
  let docName = '';

  async function loadPdf(file) {
    if (typeof pdfjsLib === 'undefined') {
      throw new Error('PDF.js failed to load — check your internet connection and reload the page.');
    }
    let arrayBuffer;
    try {
      arrayBuffer = await file.arrayBuffer();
    } catch (e) {
      throw new Error('Could not read the selected file.');
    }
    try {
      const loadingTask = pdfjsLib.getDocument({ data: arrayBuffer });
      currentDoc = await loadingTask.promise;
    } catch (e) {
      throw new Error('This doesn\'t look like a valid, readable PDF (it may be corrupted, password-protected, or a different file type): ' + (e.message || e));
    }
    docName = file.name;
    return { numPages: currentDoc.numPages, name: file.name };
  }

  // Generic DocumentLoader-shaped entry point (see loaders.js) — takes
  // whatever the file input handed over (array/FileList) and loads the
  // first (only) file as a PDF.
  async function load(files) {
    const file = (files instanceof FileList || Array.isArray(files)) ? files[0] : files;
    return loadPdf(file);
  }

  // The one real render implementation — fetches the PDF.js page once and
  // returns everything downstream needs (image + dimensions) in a single
  // Page Object, shared shape with image.js's getPageImage.
  async function getPageImage(pageIndex, scale) {
    if (!currentDoc) throw new Error('No PDF loaded.');
    const page = await currentDoc.getPage(pageIndex);
    const viewport = page.getViewport({ scale: scale || 2.0 });
    const canvas = document.createElement('canvas');
    canvas.width = viewport.width;
    canvas.height = viewport.height;
    const ctx = canvas.getContext('2d');
    await page.render({ canvasContext: ctx, viewport: viewport }).promise;
    const base64 = canvas.toDataURL('image/png').substring('data:image/png;base64,'.length);
    // Explicitly drop canvas dimensions to encourage prompt GC of the
    // (potentially large) pixel buffer before the next page renders.
    canvas.width = 0;
    canvas.height = 0;
    return {
      pageNumber: pageIndex,
      name: `${docName} — page ${pageIndex}`,
      mimeType: 'image/png',
      imageBase64: base64,
      width: Math.round(viewport.width),
      height: Math.round(viewport.height)
    };
  }

  // Kept for any existing caller that only ever wanted the base64 string —
  // thin wrapper over getPageImage now, not a second render path.
  async function renderPageToPngBase64(pageNum, scale) {
    return (await getPageImage(pageNum, scale)).imageBase64;
  }

  function getPageCount() {
    return currentDoc ? currentDoc.numPages : 0;
  }

  function getDocumentName() {
    return docName;
  }

  return { load, loadPdf, renderPageToPngBase64, getPageImage, getPageCount, getDocumentName };
})();
