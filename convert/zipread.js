// convert/zipread.js — minimal in-browser ZIP reader, window.DGE.ZipRead
// namespace. Exists to unpack GitHub Actions artifact downloads (always a
// plain, unencrypted, single-volume ZIP using STORE or DEFLATE
// compression) without adding an external library dependency: parses the
// End Of Central Directory record, walks the Central Directory, then reads
// each Local File Header + payload, using the browser's native
// DecompressionStream('deflate-raw') for DEFLATE entries.
window.DGE = window.DGE || {};
window.DGE.ZipRead = (function () {
  const EOCD_SIG = 0x06054b50;
  const CENTRAL_SIG = 0x02014b50;
  const LOCAL_SIG = 0x04034b50;

  async function inflateRaw(bytes) {
    if (typeof DecompressionStream === 'undefined') {
      throw new Error('This browser has no DecompressionStream support, needed to unzip the downloaded artifact. Try a recent Chrome, Edge, or Safari.');
    }
    const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream('deflate-raw'));
    const buf = await new Response(stream).arrayBuffer();
    return new Uint8Array(buf);
  }

  // Returns [{name, bytes: Uint8Array}], directory entries omitted.
  async function extractAll(arrayBuffer) {
    const bytes = new Uint8Array(arrayBuffer);
    const view = new DataView(arrayBuffer);

    let eocdOffset = -1;
    const scanFloor = Math.max(0, bytes.length - 22 - 65536);
    for (let i = bytes.length - 22; i >= scanFloor; i--) {
      if (view.getUint32(i, true) === EOCD_SIG) { eocdOffset = i; break; }
    }
    if (eocdOffset < 0) throw new Error('Not a valid ZIP file (no End Of Central Directory record found).');

    const entryCount = view.getUint16(eocdOffset + 10, true);
    const centralDirOffset = view.getUint32(eocdOffset + 16, true);

    const entries = [];
    let offset = centralDirOffset;
    for (let i = 0; i < entryCount; i++) {
      if (view.getUint32(offset, true) !== CENTRAL_SIG) throw new Error('Malformed ZIP central directory entry.');
      const compressionMethod = view.getUint16(offset + 10, true);
      const compressedSize = view.getUint32(offset + 20, true);
      const nameLen = view.getUint16(offset + 28, true);
      const extraLen = view.getUint16(offset + 30, true);
      const commentLen = view.getUint16(offset + 32, true);
      const localHeaderOffset = view.getUint32(offset + 42, true);
      const name = new TextDecoder().decode(bytes.subarray(offset + 46, offset + 46 + nameLen));
      entries.push({ name, compressionMethod, compressedSize, localHeaderOffset });
      offset += 46 + nameLen + extraLen + commentLen;
    }

    const out = [];
    for (const entry of entries) {
      if (entry.name.endsWith('/')) continue; // directory entry
      const lo = entry.localHeaderOffset;
      if (view.getUint32(lo, true) !== LOCAL_SIG) throw new Error(`Malformed ZIP local header for ${entry.name}.`);
      const nameLen = view.getUint16(lo + 26, true);
      const extraLen = view.getUint16(lo + 28, true);
      const dataStart = lo + 30 + nameLen + extraLen;
      const compressed = bytes.subarray(dataStart, dataStart + entry.compressedSize);
      let data;
      if (entry.compressionMethod === 0) data = compressed;
      else if (entry.compressionMethod === 8) data = await inflateRaw(compressed);
      else throw new Error(`Unsupported ZIP compression method ${entry.compressionMethod} for ${entry.name} (only STORE/DEFLATE are supported).`);
      out.push({ name: entry.name, bytes: data });
    }
    return out;
  }

  return { extractAll };
})();
