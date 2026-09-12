// js/history.js
// Maps to F-018: Reading History
// Logs every verse played (deduped per-session, timestamped) to
// localStorage, and provides a viewer modal to browse/jump back to
// recently-read verses.

window.DGE_VERSIONS = window.DGE_VERSIONS || {};
window.DGE_VERSIONS['history.js'] = 'v1.2 (TOC jump respects single-view reading mode)';

const DGE_HISTORY_MAX_ENTRIES = 100;

function dgeGetHistoryKey() {
  return typeof nsKey === 'function' ? nsKey('readingHistory') : null;
}

function dgeGetReadingHistory() {
  const key = dgeGetHistoryKey();
  if (!key) return [];
  try {
    return JSON.parse(localStorage.getItem(key) || '[]');
  } catch (e) {
    return [];
  }
}

// Logs a play event. Collapses repeats of the SAME verse played again
// within a short window (2 minutes) into a single entry (updating its
// timestamp) rather than spamming the history with re-plays/loops of the
// same shloka.
function dgeLogReadingHistory(id) {
  const key = dgeGetHistoryKey();
  if (!key) return;
  let history = dgeGetReadingHistory();
  const now = Date.now();

  if (history.length && history[0].id === id && (now - history[0].at) < 2 * 60 * 1000) {
    history[0].at = now;
  } else {
    history.unshift({ id, at: now });
  }

  if (history.length > DGE_HISTORY_MAX_ENTRIES) history = history.slice(0, DGE_HISTORY_MAX_ENTRIES);
  localStorage.setItem(key, JSON.stringify(history));
}
window.dgeLogReadingHistory = dgeLogReadingHistory;

function dgeFormatHistoryTime(ts) {
  const d = new Date(ts);
  const now = new Date();
  const sameDay = d.toDateString() === now.toDateString();
  const time = d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  if (sameDay) return `Today, ${time}`;
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (d.toDateString() === yesterday.toDateString()) return `Yesterday, ${time}`;
  return d.toLocaleDateString([], { month: 'short', day: 'numeric' }) + `, ${time}`;
}

window.openReadingHistory = function() {
  const container = document.getElementById('readingHistoryContainer');
  if (!container) return;
  const history = dgeGetReadingHistory();

  if (!history.length) {
    container.innerHTML = `<div class="note-preview-box empty">No reading history yet — play a few shlokas and they'll show up here.</div>`;
  } else {
    container.innerHTML = `
      <button class="btn-sm" style="width:100%; margin-bottom:12px;" onclick="window.clearReadingHistory()">🗑️ Clear History</button>
      <div style="display:flex; flex-direction:column; gap:8px;">
        ${history.map(h => `
          <button class="btn-sm history-entry-btn" onclick="window.jumpToHistoryEntry(${h.id})">
            <span style="font-weight:800;">Shloka ${h.id}</span>
            <span style="color:var(--muted-text); font-weight:600; font-size:11px;">${dgeFormatHistoryTime(h.at)}</span>
          </button>
        `).join('')}
      </div>`;
  }
  if (typeof openModal === 'function') openModal('historyModal');
};

window.jumpToHistoryEntry = function(id) {
  if (typeof closeModal === 'function') closeModal('historyModal');
  if (typeof playShloka === 'function') playShloka(id);
};

window.clearReadingHistory = function() {
  const key = dgeGetHistoryKey();
  if (key) localStorage.removeItem(key);
  window.openReadingHistory();
  if (typeof showToast === 'function') showToast('Reading history cleared.');
};

// Quick-jump Table of Contents — a grid of every shloka number, tappable
// to go straight there. Simple stand-in for a real sitemap until the
// site grows into a multi-page structure where an actual sitemap makes
// sense.
window.openTocModal = function() {
  const grid = document.getElementById('tocGrid');
  if (!grid || typeof stotraData === 'undefined' || !stotraData) return;
  const total = stotraData.metadata.totalShlokas || Object.keys(stotraData.shlokas).length;

  let html = '';
  for (let i = 1; i <= total; i++) {
    const isActive = (typeof activeId !== 'undefined' && activeId === i);
    html += `<button class="${isActive ? 'active-verse' : ''}" onclick="window.jumpToTocEntry(${i})">${i}</button>`;
  }
  grid.innerHTML = html;
  if (typeof openModal === 'function') openModal('tocModal');
};

window.jumpToTocEntry = function(id) {
  if (typeof closeModal === 'function') closeModal('tocModal');
  if (window.viewMode === 'single' && typeof window.dgeSetSingleViewId === 'function') {
    window.dgeSetSingleViewId(id);
  } else if (typeof loadShloka === 'function') {
    // Select and scroll to it; jumping from the table of contents should
    // not start audio any more than clicking a shloka's text does.
    loadShloka(id);
  }
};
