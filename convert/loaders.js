// convert/loaders.js — window.DGE.Loaders namespace.
// Picks which loader module (pdf.js / image.js, more later) should handle
// whatever the user just selected, so app.js never has to ask "is this a
// PDF?" itself — it just gets back something implementing load() /
// getPageCount() / getDocumentName() / getPageImage().
window.DGE = window.DGE || {};
window.DGE.Loaders = (function () {
  const IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp'];

  function isPdfFile(file) {
    return file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');
  }

  function isImageFile(file) {
    const lower = file.name.toLowerCase();
    if (lower.endsWith('.jp2')) return false; // matched below with its own message — not silently rejected as "unsupported"
    return (file.type && file.type.startsWith('image/')) || IMAGE_EXTENSIONS.some(ext => lower.endsWith(ext));
  }

  function isJp2File(file) {
    return file.name.toLowerCase().endsWith('.jp2') || file.type === 'image/jp2';
  }

  // Returns { loader, files, typeLabel } for a supported selection, or
  // throws an Error with a message meant to be shown to the user directly.
  function detect(fileList) {
    const files = Array.from(fileList || []);
    if (!files.length) throw new Error('No file selected.');

    if (files.length === 1 && isPdfFile(files[0])) {
      return { loader: window.DGE.PDF, files, typeLabel: 'PDF' };
    }
    if (files.length > 1 && files.some(isPdfFile)) {
      throw new Error('Only one PDF at a time — select a single PDF, or multiple page images instead.');
    }
    if (files.some(isJp2File)) {
      throw new Error('JP2 (JPEG 2000) images aren\'t supported yet — no browser can decode them without an extra decoder library, which isn\'t wired up here. Convert to JPG/PNG first, or use a different source.');
    }
    if (files.every(isImageFile)) {
      return {
        loader: window.DGE.ImageLoader,
        files,
        typeLabel: files.length === 1 ? 'image' : `${files.length} images`
      };
    }
    throw new Error('Unsupported file(s) — expected a single PDF, or one or more page images (JPG/PNG/WEBP).');
  }

  return { detect };
})();
