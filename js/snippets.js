// DGE Module: snippets.js
// Maps to F-009: Snippets — capture, save, play, download and share
// trimmed audio segments of a shloka.
window.DGE_VERSIONS = window.DGE_VERSIONS || {};
window.DGE_VERSIONS['snippets.js'] = 'v2.3 (Alt-filename fallback, real 404 fix, zero-padded filenames)';

window.playSnippet = async function(id, start, end) {
    if (typeof closeModal === 'function') closeModal('actionsSheetModal');

    const applySnippetLimits = () => {
        window.els.loopA.value = start;
        window.els.loopB.value = end;
        window.els.enableAB.checked = true;
        window.currentAudio.currentTime = start;
        window.currentAudio.play();
    };

    if (window.activeId !== id) {
        // Wait for the main audio fetching to complete
        await window.playShloka(id);

        // Ensure browser has loaded audio metadata before seeking
        if (window.currentAudio.readyState >= 1) {
            applySnippetLimits();
        } else {
            window.currentAudio.addEventListener('loadedmetadata', function handler() {
                applySnippetLimits();
                window.currentAudio.removeEventListener('loadedmetadata', handler);
            });
        }
    } else {
        // If already on the correct track, apply immediately
        applySnippetLimits();
    }
};

// --- Save / delete ---------------------------------------------------

window.saveSnippet = function() {
    if (!window.activeId) {
        if (typeof showToast === 'function') showToast('Play a shloka first, then set Start/End to save a snippet.');
        return;
    }

    const loopA = document.getElementById('loopA');
    const loopB = document.getElementById('loopB');
    const start = loopA ? parseFloat(loopA.value) : NaN;
    const end = loopB ? parseFloat(loopB.value) : NaN;

    if (isNaN(start) || isNaN(end) || end <= start) {
        if (typeof showToast === 'function') showToast('Set a valid Start and End time first (or use 🎯 Auto A-B Capture).');
        return;
    }

    if (typeof snippets === 'undefined') return;
    const id = window.activeId;
    if (!snippets[id]) snippets[id] = [];
    snippets[id].push({ start, end, savedAt: Date.now() });

    if (typeof nsKey === 'function') {
        localStorage.setItem(nsKey('snippets'), JSON.stringify(snippets));
    }

    if (typeof renderList === 'function') renderList();
    if (window.currentActionsSheetId === id && typeof renderActionsSheetContent === 'function') {
        renderActionsSheetContent(id);
    }
    if (typeof showToast === 'function') showToast(`Snippet saved for Shloka ${id} (${start.toFixed(1)}s–${end.toFixed(1)}s)`);
};

window.deleteSnippet = function(id, index) {
    if (typeof snippets === 'undefined' || !snippets[id]) return;
    snippets[id].splice(index, 1);
    if (snippets[id].length === 0) delete snippets[id];

    if (typeof nsKey === 'function') {
        localStorage.setItem(nsKey('snippets'), JSON.stringify(snippets));
    }

    if (typeof renderList === 'function') renderList();
    if (typeof renderActionsSheetContent === 'function') renderActionsSheetContent(id);
    if (typeof showToast === 'function') showToast('Snippet deleted.');
};

// --- Audio decoding / trimming / encoding -----------------------------
// Pure client-side WAV export so a snippet can be downloaded/shared as its
// own standalone audio file (no server-side processing available on a
// static GitHub Pages deploy).

function dgeGetAudioContext() {
    if (!window._dgeAudioCtx) {
        const Ctx = window.AudioContext || window.webkitAudioContext;
        window._dgeAudioCtx = new Ctx();
    }
    return window._dgeAudioCtx;
}

// Fetches actual audio bytes for a shloka, checking the offline cache
// first, then falling back to a live fetch — trying BOTH the primary
// filename and the alt filename (some files on archive.org are only
// reachable with a zero-width space before the extension; this mirrors
// the exact fallback cacheAllAudio() already uses, which is why bulk
// preload succeeds even when a single direct fetch of the primary URL
// 404s). A successful live fetch is opportunistically cached so future
// requests hit the cache instead of re-discovering which variant works.
async function dgeFetchAudioBlob(id) {
    if (!stotraData || !stotraData.metadata) throw new Error('No stotra data loaded');
    const fid = typeof dgeAudioFileId === 'function' ? dgeAudioFileId(id) : id;
    const primary = `${stotraData.metadata.archiveBaseUrl}${stotraData.metadata.filePrefix}${fid}${stotraData.metadata.fileExtension}`;
    const alt = `${stotraData.metadata.archiveBaseUrl}${stotraData.metadata.filePrefix}${fid}%E2%80%8B${stotraData.metadata.fileExtension}`;

    if ('caches' in window && typeof AUDIO_CACHE_NAME !== 'undefined') {
        try {
            const cache = await caches.open(AUDIO_CACHE_NAME);
            const hit = (await cache.match(primary)) || (await cache.match(alt));
            if (hit) return await hit.blob();
        } catch (e) {
            console.warn('Offline cache read error:', e);
        }
    }

    let res = await fetch(primary);
    if (!res.ok) res = await fetch(alt);
    if (!res.ok) throw new Error(`Could not fetch audio (tried both filename variants, last status ${res.status})`);

    const blob = await res.blob();

    if ('caches' in window && typeof AUDIO_CACHE_NAME !== 'undefined') {
        try {
            const cache = await caches.open(AUDIO_CACHE_NAME);
            await cache.put(res.url, new Response(blob, { headers: res.headers }));
        } catch (e) { /* best-effort, not fatal if this fails */ }
    }

    return blob;
}

async function dgeFetchAndDecode(id) {
    const blob = await dgeFetchAudioBlob(id);
    const arrayBuffer = await blob.arrayBuffer();
    const ctx = dgeGetAudioContext();
    return await ctx.decodeAudioData(arrayBuffer.slice(0));
}

function dgeSliceAudioBuffer(sourceBuffer, startSec, endSec) {
    const sampleRate = sourceBuffer.sampleRate;
    const startSample = Math.max(0, Math.floor(startSec * sampleRate));
    const endSample = Math.min(sourceBuffer.length, Math.floor(endSec * sampleRate));
    const frameCount = Math.max(1, endSample - startSample);

    const ctx = dgeGetAudioContext();
    const sliced = ctx.createBuffer(sourceBuffer.numberOfChannels, frameCount, sampleRate);

    for (let ch = 0; ch < sourceBuffer.numberOfChannels; ch++) {
        const sourceData = sourceBuffer.getChannelData(ch);
        const slicedData = sliced.getChannelData(ch);
        slicedData.set(sourceData.subarray(startSample, startSample + frameCount));
    }
    return sliced;
}

function dgeWriteString(view, offset, str) {
    for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i));
}

function dgeFloatTo16BitPCM(view, offset, input) {
    for (let i = 0; i < input.length; i++, offset += 2) {
        const s = Math.max(-1, Math.min(1, input[i]));
        view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
    }
}

function dgeInterleave(inputL, inputR) {
    const length = inputL.length + inputR.length;
    const result = new Float32Array(length);
    let index = 0, i = 0;
    while (index < length) { result[index++] = inputL[i]; result[index++] = inputR[i]; i++; }
    return result;
}

function dgeAudioBufferToWavBlob(buffer) {
    const numChannels = buffer.numberOfChannels;
    const sampleRate = buffer.sampleRate;
    const bitDepth = 16;
    const samples = numChannels === 2
        ? dgeInterleave(buffer.getChannelData(0), buffer.getChannelData(1))
        : buffer.getChannelData(0);

    const bytesPerSample = bitDepth / 8;
    const blockAlign = numChannels * bytesPerSample;
    const dataSize = samples.length * bytesPerSample;
    const arrayBuffer = new ArrayBuffer(44 + dataSize);
    const view = new DataView(arrayBuffer);

    dgeWriteString(view, 0, 'RIFF');
    view.setUint32(4, 36 + dataSize, true);
    dgeWriteString(view, 8, 'WAVE');
    dgeWriteString(view, 12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, numChannels, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * blockAlign, true);
    view.setUint16(32, blockAlign, true);
    view.setUint16(34, bitDepth, true);
    dgeWriteString(view, 36, 'data');
    view.setUint32(40, dataSize, true);
    dgeFloatTo16BitPCM(view, 44, samples);

    return new Blob([view], { type: 'audio/wav' });
}

function dgeTriggerBlobDownload(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 4000);
}

// --- Download ----------------------------------------------------------

window.downloadFullShlokaAudio = async function(id) {
    if (typeof showToast === 'function') showToast('Preparing download…');
    try {
        const blob = await dgeFetchAudioBlob(id);
        const ext = (typeof stotraData !== 'undefined' && stotraData && stotraData.metadata && stotraData.metadata.fileExtension) || '.mp3';
        dgeTriggerBlobDownload(blob, `Shloka-${id}${ext}`);
    } catch (e) {
        console.warn('Download failed even after trying both filename variants:', e);
        try {
            const src = await resolveAudioSrc(id);
            window.open(src, '_blank');
            if (typeof showToast === 'function') showToast("Couldn't auto-download this file — opened it in a new tab instead. Long-press the player there to save it.");
        } catch (e2) {
            console.error('Download failed', e2);
            if (typeof showToast === 'function') showToast('Could not download this audio file.');
        }
    }
};

window.downloadSnippetAudio = async function(id, start, end) {
    if (typeof showToast === 'function') showToast('Preparing snippet…');
    try {
        const decoded = await dgeFetchAndDecode(id);
        const sliced = dgeSliceAudioBuffer(decoded, start, end);
        const blob = dgeAudioBufferToWavBlob(sliced);
        dgeTriggerBlobDownload(blob, `Shloka-${id}-snippet-${start.toFixed(1)}-${end.toFixed(1)}.wav`);
    } catch (e) {
        console.error('Snippet download failed', e);
        if (typeof showToast === 'function') showToast('Could not prepare this snippet — try 📥 Preload All Audio in 🛠 Tools first, then retry.');
    }
};

// --- Share (Web Share API, with graceful fallback) ---------------------

window.shareShlokaTextOnly = async function(id) {
    const rawText = typeof getText === 'function' ? getText(id).replace(/<[^>]*>/g, '') : '';
    const text = typeof dgeShlokaShareText === 'function' ? dgeShlokaShareText(id) : `${rawText}\n\n— Shloka ${id}, ${document.title || 'Sarvamoola Digital Library'}`;
    const ref = typeof dgeShlokaReference === 'function' ? dgeShlokaReference(id) : null;
    try {
        if (navigator.share) {
            await navigator.share({ text, title: ref ? ref.title + (ref.ref ? ' ' + ref.ref : '') : `Shloka ${id}` });
        } else if (navigator.clipboard) {
            await navigator.clipboard.writeText(text);
            if (typeof showToast === 'function') showToast('Text copied to clipboard.');
        }
    } catch (e) {
        if (e && e.name === 'AbortError') return;
        console.error('Share text failed', e);
        if (typeof showToast === 'function') showToast('Could not share this text.');
    }
};

window.shareShlokaAudio = async function(id, snippet) {
    if (typeof showToast === 'function') showToast('Preparing to share…');
    try {
        const rawText = typeof getText === 'function' ? getText(id).replace(/<[^>]*>/g, '') : '';
        const text = typeof dgeShlokaShareText === 'function' ? dgeShlokaShareText(id) : `${rawText}\n\n— Shloka ${id}, ${document.title || 'Sarvamoola Digital Library'}`;

        let blob, filename, fetchFailed = false;
        try {
            if (snippet) {
                const decoded = await dgeFetchAndDecode(id);
                const sliced = dgeSliceAudioBuffer(decoded, snippet.start, snippet.end);
                blob = dgeAudioBufferToWavBlob(sliced);
                filename = `Shloka-${id}-snippet-${snippet.start.toFixed(1)}-${snippet.end.toFixed(1)}.wav`;
            } else {
                blob = await dgeFetchAudioBlob(id);
                const ext = (typeof stotraData !== 'undefined' && stotraData && stotraData.metadata && stotraData.metadata.fileExtension) || '.mp3';
                filename = `Shloka-${id}${ext}`;
            }
        } catch (fetchErr) {
            // Both the primary and alt (zero-width-space) filenames failed
            // live, and it isn't in the offline cache either. Fall back to
            // sharing a link instead of the bytes.
            console.warn('Could not fetch audio bytes for sharing after trying both filename variants:', fetchErr);
            fetchFailed = true;
        }

        if (fetchFailed) {
            const directUrl = snippet ? await resolveAudioSrc(id) : await resolveAudioSrc(id);
            const textWithLink = `${text}\n\n🎧 Audio: ${directUrl}`;
            if (navigator.share) {
                await navigator.share({ text: textWithLink, title: `Shloka ${id}` });
            } else if (navigator.clipboard) {
                await navigator.clipboard.writeText(textWithLink);
                if (typeof showToast === 'function') showToast("Couldn't attach the audio file directly — copied the text with a link to it instead.");
            }
            return;
        }

        const file = new File([blob], filename, { type: blob.type || 'audio/mpeg' });

        if (navigator.canShare && navigator.canShare({ files: [file] })) {
            await navigator.share({ files: [file], text, title: `Shloka ${id}` });
            return;
        }

        if (navigator.share) {
            // Some browsers can share text but not files
            await navigator.share({ text, title: `Shloka ${id}` });
            dgeTriggerBlobDownload(blob, filename);
            if (typeof showToast === 'function') showToast("Shared the text — this browser can't share audio directly, so the audio was also downloaded.");
            return;
        }

        // No Web Share API available (typically desktop) — fall back
        dgeTriggerBlobDownload(blob, filename);
        if (navigator.clipboard) { try { await navigator.clipboard.writeText(text); } catch (_) {} }
        if (typeof showToast === 'function') showToast("Sharing isn't supported in this browser — downloaded the audio and copied the text instead.");
    } catch (e) {
        if (e && e.name === 'AbortError') return; // user cancelled the native share sheet
        console.error('Share failed', e);
        if (typeof showToast === 'function') showToast('Could not share this audio.');
    }
};
