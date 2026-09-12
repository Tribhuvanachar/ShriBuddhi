// js/icons.js
// Maps to F-017: Shared Icon Set
// Small inline SVG icons (not image files) for the card's chip-toggle
// buttons. These replace emoji glyphs (★ ✅ 🚧 ❓ 📝 🎯), which render at
// inconsistent visual sizes/weights depending on the device's emoji font
// — that inconsistency was the actual cause of "favorite/status/doubt
// look bigger than notes/snippets". SVG with currentColor guarantees every
// icon here is the same size and follows the button's own color exactly,
// in every theme, with no separate image assets to manage.

window.DGE_VERSIONS = window.DGE_VERSIONS || {};
window.DGE_VERSIONS['icons.js'] = 'v1.0';

window.DGE_ICONS = {
  star: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="M12 3.5l2.6 5.6 6.1.7-4.5 4.2 1.2 6-5.4-3-5.4 3 1.2-6-4.5-4.2 6.1-.7z"/></svg>',
  starFilled: '<svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M12 3.5l2.6 5.6 6.1.7-4.5 4.2 1.2 6-5.4-3-5.4 3 1.2-6-4.5-4.2 6.1-.7z"/></svg>',
  question: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M9.3 9.3a2.7 2.7 0 0 1 5.2.9c0 1.8-2.6 2.1-2.6 3.9"/><circle cx="12" cy="17.3" r="0.15" fill="currentColor" stroke-width="1.4"/></svg>',
  statusPending: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="8.5"/></svg>',
  statusPractice: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3.5l9.3 16H2.7z"/><line x1="12" y1="9.5" x2="12" y2="14"/><circle cx="12" cy="16.8" r="0.15" fill="currentColor" stroke-width="1.4"/></svg>',
  statusDone: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="8.5" stroke-width="2"/><path d="M7.8 12.2l2.6 2.6 5.6-5.8"/></svg>',
  more: '<svg viewBox="0 0 24 24" width="15" height="15" fill="currentColor"><circle cx="5" cy="12" r="1.7"/><circle cx="12" cy="12" r="1.7"/><circle cx="19" cy="12" r="1.7"/></svg>',
  note: '<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-1px;"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6"/></svg>',
  snippet: '<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:-1px;"><circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4"/><circle cx="12" cy="12" r="0.7" fill="currentColor"/></svg>'
};
