// js/char-palette.js
// Maps to F-020: Floating Special-Character Keyboard
// A compact panel of base-letter keys (a, i, u, r, l, n, t, d, s, m, h) —
// tap for the plain letter, LONG-PRESS to reveal that letter's diacritic
// variants (long vowel, anusvāra/visarga, retroflex, etc.), matching how
// real phone keyboards handle accented characters. Fixed symbols (Om,
// avagraha, udātta, anudātta) sit alongside as their own single keys.
// Inserts into whichever text input/textarea was last focused.

window.DGE_VERSIONS = window.DGE_VERSIONS || {};
window.DGE_VERSIONS['char-palette.js'] = 'v2.0 (Long-press base-letter variants)';

const DGE_BASE_KEYS = [
  { base: 'a', variants: ['a', 'ā'] },
  { base: 'i', variants: ['i', 'ī'] },
  { base: 'u', variants: ['u', 'ū'] },
  { base: 'r', variants: ['r', 'ṛ', 'ṝ'] },
  { base: 'l', variants: ['l', 'ḷ', 'ḹ'] },
  { base: 'n', variants: ['n', 'ṅ', 'ñ', 'ṇ'] },
  { base: 't', variants: ['t', 'ṭ'] },
  { base: 'd', variants: ['d', 'ḍ'] },
  { base: 's', variants: ['s', 'ś', 'ṣ'] },
  { base: 'm', variants: ['m', 'ṃ'] },
  { base: 'h', variants: ['h', 'ḥ'] }
];

const DGE_FIXED_KEYS = [
  { ch: 'ॐ', label: 'Om' },
  { ch: '\u2019', label: "avagraha" },
  { ch: '\u0951', label: 'udātta' },
  { ch: '\u0952', label: 'anudātta' }
];

let dgeLastFocusedInput = null;

document.addEventListener('focusin', (e) => {
  if (e.target && (e.target.tagName === 'TEXTAREA' || (e.target.tagName === 'INPUT' && e.target.type === 'text'))) {
    dgeLastFocusedInput = e.target;
  }
});

window.dgeInsertSpecialChar = function(ch) {
  const el = dgeLastFocusedInput;
  if (!el || !document.body.contains(el)) {
    if (typeof showToast === 'function') showToast('Tap into a text field first, then pick a character.');
    return;
  }
  const start = el.selectionStart != null ? el.selectionStart : el.value.length;
  const end = el.selectionEnd != null ? el.selectionEnd : el.value.length;
  const val = el.value;
  el.value = val.slice(0, start) + ch + val.slice(end);
  const newPos = start + ch.length;
  el.focus();
  el.setSelectionRange(newPos, newPos);
  el.dispatchEvent(new Event('input', { bubbles: true }));
};

window.toggleCharPalette = function() {
  const panel = document.getElementById('charPalettePanel');
  if (panel) panel.classList.toggle('show');
};

function dgeRenderMainGrid() {
  const grid = document.getElementById('charPaletteGrid');
  if (!grid) return;
  let html = DGE_BASE_KEYS.map(k =>
    `<button type="button" title="Hold for ${k.variants.join(' / ')}" data-base="${k.base}">${k.base}</button>`
  ).join('');
  html += DGE_FIXED_KEYS.map(c =>
    `<button type="button" title="${c.label}" onclick="window.dgeInsertSpecialChar('${c.ch}')">${c.ch}</button>`
  ).join('');
  grid.innerHTML = html;
  dgeWireLongPress();
}

function dgeShowVariants(key) {
  const grid = document.getElementById('charPaletteGrid');
  if (!grid) return;
  const back = `<button type="button" title="Back" onclick="window.dgeRenderMainGridPublic()" style="font-weight:800;">←</button>`;
  const variantBtns = key.variants.map(v =>
    `<button type="button" onclick="window.dgeInsertSpecialChar('${v}'); window.dgeRenderMainGridPublic();">${v}</button>`
  ).join('');
  grid.innerHTML = back + variantBtns;
}
window.dgeRenderMainGridPublic = dgeRenderMainGrid;

function dgeWireLongPress() {
  const PRESS_MS = 420;
  document.querySelectorAll('#charPaletteGrid button[data-base]').forEach(btn => {
    let pressTimer = null;
    let longPressed = false;
    const keyDef = DGE_BASE_KEYS.find(k => k.base === btn.dataset.base);

    const start = (e) => {
      e.preventDefault();
      longPressed = false;
      pressTimer = setTimeout(() => {
        longPressed = true;
        if (navigator.vibrate) navigator.vibrate(12);
        dgeShowVariants(keyDef);
      }, PRESS_MS);
    };
    const cancel = () => { if (pressTimer) { clearTimeout(pressTimer); pressTimer = null; } };
    const end = (e) => {
      cancel();
      if (!longPressed) window.dgeInsertSpecialChar(keyDef.base);
    };

    btn.addEventListener('touchstart', start, { passive: false });
    btn.addEventListener('touchend', end);
    btn.addEventListener('touchcancel', cancel);
    btn.addEventListener('mousedown', start);
    btn.addEventListener('mouseup', end);
    btn.addEventListener('mouseleave', cancel);
  });
}

document.addEventListener('DOMContentLoaded', dgeRenderMainGrid);
