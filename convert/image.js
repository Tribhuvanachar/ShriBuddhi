// convert/image.js — window.DGE.ImageLoader namespace.
// Loader for one or more page-image files (JPG/PNG/WEBP) selected
// directly, as an alternative to uploading a PDF. Same
// load/getPageCount/getDocumentName/getPageImage shape as pdf.js (see
// loaders.js for how the app picks between them) so app.js's OCR loop
// never needs to know which one it's talking to.
//
// Named "ImageLoader", not "Image" — window.Image is the DOM Image
// element constructor, and shadowing it would be a nasty, easy-to-miss
// bug the moment any code in this page (or a future loader) does
// `new Image()`.
window.DGE = window.DGE || {};
window.DGE.ImageLoader = (function () {
  // Caps the longest edge of any normalized page image. Not about visual
  // quality — it's about staying well within Vision's request-size limits
  // and matching the resolution the PDF path already renders at
  // (scale=2.0 on a typical book page lands well under this). A raw phone
  // photo or full-resolution archive scan can otherwise be 4000px+ on a
  // side for no OCR-accuracy benefit, just a bigger payload.
  const MAX_DIMENSION = 3000;

  let pageFiles = []; // File[], in the order the user selected them
  let docName = '';

  // Files arrive in selection order, which is the browser's file-picker
  // order — not necessarily filename order. Re-sorting by filename here
  // would silently second-guess a user who deliberately picked files in a
  // specific order, so this loader trusts the order it's given; anything
  // that needs to *detect* page order from filenames (e.g. a future ZIP
  // loader unpacking many files at once) should sort before calling load().
  async function load(files) {
    pageFiles = Array.from(files);
    if (!pageFiles.length) throw new Error('No image file(s) given.');
    docName = pageFiles.length === 1
      ? pageFiles[0].name
      : `${pageFiles.length} images (starting "${pageFiles[0].name}")`;
    return { numPages: pageFiles.length, name: docName };
  }

  function getPageCount() {
    return pageFiles.length;
  }

  function getDocumentName() {
    return docName;
  }

  function loadImageElement(file) {
    return new Promise((resolve, reject) => {
      const url = URL.createObjectURL(file);
      const img = new Image();
      img.onload = () => resolve({ img, url });
      img.onerror = () => {
        URL.revokeObjectURL(url);
        reject(new Error(`Could not decode "${file.name}" as an image — it may be corrupted or an unsupported format (JP2 isn't decodable in-browser; convert it to JPG/PNG first).`));
      };
      img.src = url;
    });
  }

  // Every page — regardless of source format — is normalized to a PNG
  // through a canvas, same as the PDF loader's output. Downstream code
  // (Vision, the OCR loop) only ever sees a plain PNG base64 string; it
  // never has to know or care what format the original file was in.
  async function getPageImage(pageIndex) {
    const file = pageFiles[pageIndex - 1];
    if (!file) throw new Error(`No page ${pageIndex} loaded.`);

    const { img, url } = await loadImageElement(file);
    try {
      let w = img.naturalWidth, h = img.naturalHeight;
      if (!w || !h) throw new Error(`"${file.name}" decoded with zero dimensions — likely not a real image file.`);
      if (w > MAX_DIMENSION || h > MAX_DIMENSION) {
        const scale = MAX_DIMENSION / Math.max(w, h);
        w = Math.round(w * scale);
        h = Math.round(h * scale);
      }

      const canvas = document.createElement('canvas');
      canvas.width = w;
      canvas.height = h;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(img, 0, 0, w, h);
      const base64 = canvas.toDataURL('image/png').substring('data:image/png;base64,'.length);
      canvas.width = 0;
      canvas.height = 0;

      return { pageNumber: pageIndex, name: file.name, mimeType: 'image/png', imageBase64: base64, width: w, height: h };
    } finally {
      URL.revokeObjectURL(url);
    }
  }

  return { load, getPageCount, getDocumentName, getPageImage };
})();
