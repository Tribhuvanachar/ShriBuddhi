// js/screenshot.js
// Maps to F-016: Shloka Screenshot Card
// Renders a themed "fancy card" image (stotra name, shloka number, shloka
// text) via Canvas, matching whichever theme is currently active, so a
// shloka can be shared as a standalone image instead of just plain text.

window.DGE_VERSIONS = window.DGE_VERSIONS || {};
window.DGE_VERSIONS['screenshot.js'] = 'v2.2 (Live-preview image composer: dgeRenderShlokaCard split into dgeBuildShlokaCardCanvas + a thin blob wrapper so a preview sheet can show the real canvas before sharing; new opts.textStyle -- "gold" (default, unchanged) or "solid" with a real WCAG contrast ratio sampled from the template artwork; document.fonts.ready now capped at 1.5s so a slow/blocked font host cannot leave the live preview stuck on "Rendering…" indefinitely. Everything from v2.1 -- real image dimensions -- unchanged when opts is omitted)';

function dgeWrapCanvasText(ctx, text, maxWidth) {
  const words = text.split(/\s+/).filter(Boolean);
  const lines = [];
  let current = '';
  words.forEach(word => {
    const test = current ? current + ' ' + word : word;
    if (ctx.measureText(test).width > maxWidth && current) {
      lines.push(current);
      current = word;
    } else {
      current = test;
    }
  });
  if (current) lines.push(current);
  return lines;
}

function dgeRoundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function dgeLoadTemplateImage(path) {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => resolve(null);
    img.src = path;
  });
}

// Layered gold "engraved plaque" text: a dark offset shadow (recess),
// a gold gradient body, and a thin dark edge stroke — gives a metallic,
// embossed look entirely via Canvas, no external assets needed.
function dgeDrawEmbossedGoldText(ctx, text, x, y) {
  ctx.save();
  ctx.fillStyle = 'rgba(0,0,0,0.5)';
  ctx.fillText(text, x + 2, y + 3);
  ctx.restore();

  const grad = ctx.createLinearGradient(0, y - 32, 0, y + 12);
  grad.addColorStop(0, '#fff7c0');
  grad.addColorStop(0.25, '#ffe98a');
  grad.addColorStop(0.5, '#ffd54a');
  grad.addColorStop(0.75, '#c69214');
  grad.addColorStop(1, '#fff2a8');

  ctx.save();
  ctx.fillStyle = grad;
  ctx.shadowColor = 'rgba(255, 213, 77, 0.55)';
  ctx.shadowBlur = 14;
  ctx.fillText(text, x, y);
  ctx.restore();

  ctx.save();
  ctx.strokeStyle = '#5e3d00';
  ctx.lineWidth = 1.1;
  ctx.strokeText(text, x, y);
  ctx.restore();
}

// Plain, single-colour text -- the alternative to the embossed-gold style
// above, for a reader who wants a colour the gold gradient doesn't give
// them (or whose template makes gold hard to read). A soft drop shadow is
// the only fixed legibility aid; anything more (an outline, an auto-picked
// colour) would fight the "the colour I chose" point of offering this at
// all, which is why the preview sheet's contrast rating exists instead.
function dgeDrawStyledText(ctx, text, x, y, opts) {
  if (opts && opts.textStyle === 'solid') {
    ctx.save();
    ctx.fillStyle = 'rgba(0,0,0,0.35)';
    ctx.fillText(text, x + 1, y + 2);
    ctx.restore();
    ctx.save();
    ctx.fillStyle = opts.solidColor || '#ffffff';
    ctx.fillText(text, x, y);
    ctx.restore();
    return;
  }
  dgeDrawEmbossedGoldText(ctx, text, x, y);
}

// WCAG 2.x relative-luminance contrast ratio (the same formula the spec's
// own 4.5:1 "AA normal text" threshold is defined against) -- used only to
// rate the Plain Color option, since the embossed-gold style already
// carries its own dark recess + stroke for legibility on any background
// and doesn't need this check.
function dgeSRGBToLinear(c) {
  c = c / 255;
  return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
}
function dgeRelLuminance(rgb) {
  return 0.2126 * dgeSRGBToLinear(rgb[0]) + 0.7152 * dgeSRGBToLinear(rgb[1]) + 0.0722 * dgeSRGBToLinear(rgb[2]);
}
function dgeContrastRatio(rgbA, rgbB) {
  const lA = dgeRelLuminance(rgbA), lB = dgeRelLuminance(rgbB);
  const lighter = Math.max(lA, lB), darker = Math.min(lA, lB);
  return (lighter + 0.05) / (darker + 0.05);
}
function dgeHexToRgb(hex) {
  hex = String(hex || '#ffffff').replace('#', '');
  if (hex.length === 3) hex = hex.split('').map(c => c + c).join('');
  const n = parseInt(hex, 16);
  return [(n >> 16) & 255, (n >> 8) & 255, (isNaN(n) ? 0xff : n) & 255];
}

// A cheap, sparsely-sampled average colour of the canvas under the text's
// own safe zone -- a real reading of what the Plain Color text is about to
// sit on (template artwork, or the plain fallback background), not a
// guess. Only ever called right after the background/template is drawn
// and before any text, so it can't pick up the text's own pixels.
function dgeSampleZoneAverageRgb(ctx, zone, W, H) {
  const x = Math.max(0, Math.floor(zone.x)), y = Math.max(0, Math.floor(zone.y));
  const w = Math.max(1, Math.min(Math.floor(zone.w), W - x));
  const h = Math.max(1, Math.min(Math.floor(zone.h), H - y));
  let data;
  try { data = ctx.getImageData(x, y, w, h).data; } catch (e) { return [255, 255, 255]; }
  let r = 0, g = 0, b = 0, n = 0;
  const step = 4 * 41; // a prime stride spreads the sample across the whole zone cheaply
  for (let i = 0; i < data.length; i += step) {
    r += data[i]; g += data[i + 1]; b += data[i + 2]; n++;
  }
  return n ? [r / n, g / n, b / n] : [255, 255, 255];
}

// Builds the actual canvas (previously the body of dgeRenderShlokaCard).
// Split out so the live-preview sheet can show this SAME canvas directly
// instead of round-tripping through a PNG blob on every adjustment.
// opts is optional and defaults to the original, only-ever style (gold
// embossed text) -- calling this with no opts reproduces the exact same
// drawing as before this split, byte for byte.
async function dgeBuildShlokaCardCanvas(id, opts) {
  opts = opts || { textStyle: 'gold' };
  // Capped at 1.5s: document.fonts.ready doesn't resolve until every
  // requested font's network fetch has settled, success or failure, so a
  // slow/blocked font host can leave it pending far longer than that. That
  // was already true before this preview sheet existed, but it went
  // unnoticed then -- the old flow just downloaded/shared a moment later
  // than expected. Now a reader is actually watching a "Rendering…"
  // placeholder for it, so an unbounded wait reads as the feature being
  // stuck rather than merely slow. Timing out just proceeds with whatever
  // fonts have loaded so far, same as the try/catch already did for an
  // outright failure.
  if (document.fonts && document.fonts.ready) {
    try { await Promise.race([document.fonts.ready, new Promise(r => setTimeout(r, 1500))]); } catch (e) { /* best-effort */ }
  }

  const tpl = (typeof dgeGetSelectedShareTemplate === 'function')
    ? await dgeGetSelectedShareTemplate()
    : { id: 'plain', filename: null, safeZone: { x: 90, y: 260, w: 900, h: 560 }, hasBakedBranding: false };

  const templateImg = tpl.filename ? await dgeLoadTemplateImage(`images/${tpl.filename}`) : null;

  // Size the canvas to the template's REAL dimensions (read from the
  // loaded image) rather than a guessed/hardcoded size — this way a
  // newly-uploaded template of any aspect ratio is never stretched or
  // distorted to fit an assumed size.
  const W = templateImg ? templateImg.naturalWidth : 1080;
  const H = templateImg ? templateImg.naturalHeight : 1080;
  const canvas = document.createElement('canvas');
  canvas.width = W; canvas.height = H;
  const ctx = canvas.getContext('2d');

  const style = getComputedStyle(document.body);
  const bg = style.getPropertyValue('--bg-main').trim() || '#FAF3E6';
  const accentGold = style.getPropertyValue('--accent-gold').trim() || '#B9821F';
  const cardBg = style.getPropertyValue('--card-bg').trim() || '#ffffff';

  const pad = 60;
  if (templateImg) {
    ctx.drawImage(templateImg, 0, 0, W, H);
  } else {
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = cardBg;
    ctx.strokeStyle = accentGold;
    ctx.lineWidth = 4;
    dgeRoundRect(ctx, pad, pad, W - pad * 2, H - pad * 2, 28);
    ctx.fill();
    ctx.stroke();
  }

  ctx.textAlign = 'center';

  const zone = tpl.safeZone || { x: pad, y: pad + 80, w: W - pad * 2, h: H - pad * 2 - 160 };
  const zoneCx = zone.x + zone.w / 2;

  // Sampled right after the background/template is drawn and before any
  // text -- a real reading of what the text is about to sit on, only
  // meaningful (and only computed) for the Plain Color style, since gold
  // embossed text already carries its own legibility aids.
  let contrastRatio = null;
  if (opts.textStyle === 'solid') {
    const zoneRgb = dgeSampleZoneAverageRgb(ctx, zone, W, H);
    contrastRatio = dgeContrastRatio(dgeHexToRgb(opts.solidColor || '#ffffff'), zoneRgb);
  }

  const stotraTitleRaw = (typeof stotraData !== 'undefined' && stotraData && stotraData.metadata) ? stotraData.metadata.title : '';
  const stotraTitle = (typeof applyTransliteration === 'function' ? applyTransliteration(stotraTitleRaw, window.activeScript || 'devanagari') : stotraTitleRaw).replace(/<[^>]*>/g, '');

  const shlokaTextRaw = typeof getText === 'function' ? getText(id) : '';
  const shlokaText = shlokaTextRaw.replace(/<[^>]*>/g, '');

  // Measure everything first so the whole block can be vertically
  // centered in the safe zone, not just horizontally.
  ctx.font = "bold 32px 'Tiro Devanagari Sanskrit', serif";
  const titleLines = dgeWrapCanvasText(ctx, stotraTitle, zone.w);
  const titleLineH = 40;

  ctx.font = "44px 'Tiro Devanagari Sanskrit', serif";
  const shlokaLines = dgeWrapCanvasText(ctx, shlokaText, zone.w);
  const shlokaLineH = 58;

  const badgeH = 40;
  const ruleGap = 26;
  const gapBeforeShloka = 22;

  const totalH = (titleLines.length * titleLineH) + ruleGap + badgeH + gapBeforeShloka + (shlokaLines.length * shlokaLineH);
  let curY = zone.y + Math.max(0, (zone.h - totalH) / 2) + titleLineH * 0.75;

  ctx.font = "bold 32px 'Tiro Devanagari Sanskrit', serif";
  titleLines.forEach(line => {
    dgeDrawStyledText(ctx, line, zoneCx, curY, opts);
    curY += titleLineH;
  });

  curY += ruleGap * 0.4;
  ctx.strokeStyle = 'rgba(198,146,20,0.85)';
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(zoneCx - 60, curY);
  ctx.lineTo(zoneCx + 60, curY);
  ctx.stroke();
  curY += ruleGap * 0.6 + 14;

  ctx.font = "600 22px 'Inter', sans-serif";
  dgeDrawStyledText(ctx, `Shloka ${id}`, zoneCx, curY, opts);
  curY += gapBeforeShloka + 16;

  ctx.font = "44px 'Tiro Devanagari Sanskrit', serif";
  shlokaLines.forEach(line => {
    dgeDrawStyledText(ctx, line, zoneCx, curY, opts);
    curY += shlokaLineH;
  });

  // Skip the footer if this template already has branding baked into
  // the artwork — drawing our own here would double it up.
  if (!tpl.hasBakedBranding) {
    ctx.font = "600 20px 'Inter', sans-serif";
    dgeDrawStyledText(ctx, '🙏 ' + (document.title || 'Sarvamoola Digital Library'), W / 2, H - pad - 30, opts);
  }

  return { canvas, contrastRatio };
}

// Thin wrapper preserving the original public contract: callers that
// already `await dgeRenderShlokaCard(id)` for a PNG Blob (download/share
// below) see no change at all when opts is omitted.
async function dgeRenderShlokaCard(id, opts) {
  const built = await dgeBuildShlokaCardCanvas(id, opts);
  return new Promise(resolve => built.canvas.toBlob(blob => resolve(blob), 'image/png'));
}

window.downloadShlokaScreenshot = async function(id, opts) {
  if (typeof showToast === 'function') showToast('Rendering image…');
  try {
    const blob = await dgeRenderShlokaCard(id, opts);
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `Shloka-${id}.png`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 4000);
  } catch (e) {
    console.error('Screenshot render failed', e);
    if (typeof showToast === 'function') showToast('Could not render this image.');
  }
};

window.shareShlokaScreenshot = async function(id, opts) {
  if (typeof showToast === 'function') showToast('Rendering image…');
  try {
    const blob = await dgeRenderShlokaCard(id, opts);
    const file = new File([blob], `Shloka-${id}.png`, { type: 'image/png' });

    if (navigator.canShare && navigator.canShare({ files: [file] })) {
      await navigator.share({ files: [file], title: `Shloka ${id}` });
      return;
    }

    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `Shloka-${id}.png`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 4000);
    if (typeof showToast === 'function') showToast("Sharing images isn't supported here — downloaded it instead.");
  } catch (e) {
    if (e && e.name === 'AbortError') return;
    console.error('Screenshot share failed', e);
    if (typeof showToast === 'function') showToast('Could not share this image.');
  }
};

// ---------------------------------------------------------------------
// Live-preview sheet wiring (#shareImagePreviewSheet, index.html). Opens
// on the same "Preview & Share Image" action that used to fire
// download/share immediately -- now it renders the real canvas first, so
// the reader sees exactly what they're about to send, and can switch to
// Plain Color text with a live contrast rating before committing.
let dgeSharePreviewState = { id: null, textStyle: 'gold', solidColor: '#ffffff' };
let dgeSharePreviewReqSeq = 0;
let dgeSharePreviewDebounce = null;

window.openShareImagePreview = function(id) {
  dgeSharePreviewState = { id: id, textStyle: 'gold', solidColor: '#ffffff' };
  if (typeof window.closeModal === 'function') window.closeModal('actionsSheetModal');

  // Reset the sheet's own controls to their default (Gold) state each
  // time it opens fresh, so a choice made for a previous shloka doesn't
  // silently carry over and surprise the reader on this one.
  const goldBtn = document.querySelector('#shareImagePreviewSheet [data-textstyle="gold"]');
  const solidBtn = document.querySelector('#shareImagePreviewSheet [data-textstyle="solid"]');
  if (goldBtn) goldBtn.classList.add('active');
  if (solidBtn) solidBtn.classList.remove('active');
  const colorInput = document.getElementById('sharePreviewColorInput');
  if (colorInput) colorInput.value = '#ffffff';
  const colorRow = document.getElementById('sharePreviewColorRow');
  if (colorRow) colorRow.style.display = 'none';

  if (typeof window.togglePopup === 'function') window.togglePopup('shareImagePreviewSheet');
  window.dgeRefreshSharePreview();
};

window.dgeSetShareTextStyle = function(style, el) {
  dgeSharePreviewState.textStyle = style;
  document.querySelectorAll('#shareImagePreviewSheet [data-textstyle]').forEach(b => b.classList.remove('active'));
  if (el) el.classList.add('active');
  const colorRow = document.getElementById('sharePreviewColorRow');
  if (colorRow) colorRow.style.display = (style === 'solid') ? 'flex' : 'none';
  window.dgeRefreshSharePreview();
};

window.dgeSetShareSolidColor = function(hex) {
  dgeSharePreviewState.solidColor = hex;
  const input = document.getElementById('sharePreviewColorInput');
  if (input) input.value = hex;
  // Debounced: the native <input type=color> fires oninput continuously
  // while dragging, and each refresh re-renders a whole canvas.
  clearTimeout(dgeSharePreviewDebounce);
  dgeSharePreviewDebounce = setTimeout(window.dgeRefreshSharePreview, 120);
};

// Request-generation guard (same pattern as ai.js's dgeShabdaReqSeq/
// dgeDhatuReqSeq this session) -- a slow-resolving earlier render (e.g. a
// template image still loading) must never overwrite a newer one if the
// reader has already changed the style again by the time it settles.
window.dgeRefreshSharePreview = async function() {
  const id = dgeSharePreviewState.id;
  const wrap = document.getElementById('sharePreviewCanvasWrap');
  if (id == null || !wrap) return;
  const myReq = ++dgeSharePreviewReqSeq;
  try {
    const built = await dgeBuildShlokaCardCanvas(id, dgeSharePreviewState);
    if (myReq !== dgeSharePreviewReqSeq) return;
    wrap.innerHTML = '';
    built.canvas.className = 'share-preview-canvas';
    wrap.appendChild(built.canvas);

    const badge = document.getElementById('sharePreviewContrastBadge');
    if (badge) {
      if (built.contrastRatio == null) {
        badge.textContent = '';
      } else {
        const ratio = built.contrastRatio;
        const pass = ratio >= 4.5; // WCAG AA, normal-size text
        badge.textContent = `Contrast ${ratio.toFixed(1)}:1 ${pass ? '✓ Readable' : '⚠ Low'}`;
        badge.style.color = pass ? '#2e7d32' : 'var(--accent-red)';
      }
    }
  } catch (e) {
    console.error('Share preview render failed', e);
    wrap.innerHTML = '<div class="share-preview-loading">Could not render preview.</div>';
  }
};

window.dgeConfirmDownloadImage = async function() {
  const id = dgeSharePreviewState.id;
  if (id == null) return;
  await window.downloadShlokaScreenshot(id, dgeSharePreviewState);
  window.togglePopup('shareImagePreviewSheet');
};

window.dgeConfirmShareImage = async function() {
  const id = dgeSharePreviewState.id;
  if (id == null) return;
  await window.shareShlokaScreenshot(id, dgeSharePreviewState);
  window.togglePopup('shareImagePreviewSheet');
};
