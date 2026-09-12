// js/markers.js
// Maps to F-010: Markers Engine
// Three independent marks per shloka:
//  - fav: boolean (Favorite)
//  - status: null -> 'pending' -> 'practice' -> 'done' -> null (cycles)
//  - doubt: boolean (needs revisiting / had a question)
// Surfaced through the unified Shloka Actions sheet (see js/actions.js)
// and filterable from the bottom-player Filter menu (see js/filter.js).

window.DGE_VERSIONS = window.DGE_VERSIONS || {};
window.DGE_VERSIONS['markers.js'] = 'v3.1 (Inline card toggles + status picker)';

const STATUS_CYCLE = [null, 'pending', 'practice', 'done'];

function dgeEnsureMark(id) {
  if (!marks[id]) marks[id] = { fav: false, status: null, doubt: false };
  return marks[id];
}

function dgeAfterMarkChange(id) {
  // Drop empty records so marks stays small and filters don't misfire on
  // stale all-false entries.
  const m = marks[id];
  if (m && !m.fav && !m.status && !m.doubt) delete marks[id];

  if (typeof dgeSaveMarks === 'function') dgeSaveMarks();
  if (typeof renderList === 'function') renderList();
  if (window.currentActionsSheetId === id && typeof renderActionsSheetContent === 'function') {
    renderActionsSheetContent(id);
  }
}

window.toggleFavorite = function(id) {
  const m = dgeEnsureMark(id);
  m.fav = !m.fav;
  dgeAfterMarkChange(id);
};

window.cycleStatus = function(id) {
  const m = dgeEnsureMark(id);
  const idx = STATUS_CYCLE.indexOf(m.status);
  m.status = STATUS_CYCLE[(idx + 1) % STATUS_CYCLE.length];
  dgeAfterMarkChange(id);
};

window.toggleDoubt = function(id) {
  const m = dgeEnsureMark(id);
  m.doubt = !m.doubt;
  dgeAfterMarkChange(id);
};

// Direct-select status picker — a small floating menu (shared, single
// instance in the DOM) rather than the old tap-to-cycle button, so
// picking a status is one tap instead of up to three.
window._dgeStatusPickerTargetId = null;

window.openStatusPicker = function(id, e) {
  if (e) e.stopPropagation();
  window._dgeStatusPickerTargetId = id;
  const menu = document.getElementById('statusPickerMenu');
  if (!menu || !e) return;

  menu.classList.add('show');
  const rect = e.currentTarget.getBoundingClientRect();
  const menuWidth = 190;
  let x = rect.left;
  if (x + menuWidth > window.innerWidth - 10) x = window.innerWidth - menuWidth - 10;
  menu.style.left = Math.max(10, x) + 'px';
  menu.style.top = (rect.bottom + 6) + 'px';
};

window.closeStatusPicker = function() {
  const menu = document.getElementById('statusPickerMenu');
  if (menu) menu.classList.remove('show');
};

window.setStatus = function(status) {
  const id = window._dgeStatusPickerTargetId;
  if (id === null || id === undefined) return;
  const m = dgeEnsureMark(id);
  m.status = status;
  dgeAfterMarkChange(id);
  window.closeStatusPicker();
};

document.addEventListener('click', (e) => {
  const menu = document.getElementById('statusPickerMenu');
  if (menu && menu.classList.contains('show') && !menu.contains(e.target) && !e.target.closest('.status-picker-btn')) {
    window.closeStatusPicker();
  }
});

// Kept for backward compatibility with any older code path that might
// still call the previous single-mark API.
window.toggleMark = function(id, type) {
  if (type === 'fav') return window.toggleFavorite(id);
  if (type === 'practice') {
    const m = dgeEnsureMark(id);
    m.status = m.status === 'practice' ? null : 'practice';
    dgeAfterMarkChange(id);
  }
};
