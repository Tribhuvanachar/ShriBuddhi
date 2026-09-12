// js/notes.js
// Maps to F-008: Notes Engine
// notes[id] is now an array of individually addressable entries:
//   { id, text, source, addedAt }
// instead of one big concatenated string, so each excerpt (manual note,
// AI append, etc.) can be shared or deleted on its own.

window.DGE_VERSIONS = window.DGE_VERSIONS || {};
window.DGE_VERSIONS['notes.js'] = 'v3.0 (Rich markdown rendering + formatting helpers)';

// Safe(r) markdown rendering for user-authored note text: escapes HTML
// FIRST (unlike parseMarkdown() in ai.js, which assumes trusted AI output
// and skips escaping), then applies basic bold/italic/list formatting on
// top of the already-escaped text. Supports **bold**, *italic*, and
// "- item" bullet lists — enough to make notes readable without needing
// a full rich-text editor.
function dgeRenderNoteMarkdown(text) {
  if (!text) return '';
  const escaped = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  return escaped
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/(?<!\*)\*([^*\n]+?)\*(?!\*)/g, '<em>$1</em>')
    .replace(/^[-•] (.*)$/gim, '<li>$1</li>')
    .replace(/(<li>.*<\/li>\n?)+/g, m => `<ul style="margin:4px 0; padding-left:20px;">${m}</ul>`)
    .replace(/\n/g, '<br>');
}
window.dgeRenderNoteMarkdown = dgeRenderNoteMarkdown;

// Wraps the current selection (or inserts at the cursor) in the note
// composer textarea with the given markdown markers — a lightweight
// formatting toolbar without needing a full rich-text editor widget.
window.dgeWrapNoteSelection = function(before, after) {
  const ta = document.getElementById('noteText');
  if (!ta) return;
  const start = ta.selectionStart, end = ta.selectionEnd;
  const val = ta.value;
  const selected = val.slice(start, end);
  ta.value = val.slice(0, start) + before + selected + (after !== undefined ? after : before) + val.slice(end);
  const cursorPos = selected ? start + before.length + selected.length + (after !== undefined ? after.length : before.length) : start + before.length;
  ta.focus();
  ta.setSelectionRange(cursorPos, cursorPos);
};

window.dgeInsertNoteBullet = function() {
  const ta = document.getElementById('noteText');
  if (!ta) return;
  const start = ta.selectionStart;
  const val = ta.value;
  const needsNewline = start > 0 && val[start - 1] !== '\n';
  const insert = (needsNewline ? '\n' : '') + '- ';
  ta.value = val.slice(0, start) + insert + val.slice(start);
  const cursorPos = start + insert.length;
  ta.focus();
  ta.setSelectionRange(cursorPos, cursorPos);
};

function openNoteModal() {
  if (typeof openModal === 'function') openModal('noteModal');
}

function closeNoteModal() {
  if (typeof closeModal === 'function') closeModal('noteModal');
  const box = document.getElementById('noteModalBox');
  const btn = document.getElementById('maxNoteBtn');
  if (box) box.classList.remove('fullscreen');
  if (btn) btn.innerText = '⛶ Expand';
}

// Opens the composer for a NEW note entry (notes are append/delete, not
// in-place edited — to fix a typo, delete the entry and add a new one).
function openNote(id) {
  window.targetNoteId = id;
  const shlokaNumEl = document.getElementById('noteShlokaNum');
  const noteTextEl = document.getElementById('noteText');
  if (shlokaNumEl) shlokaNumEl.innerText = id;
  if (noteTextEl) noteTextEl.value = '';
  openNoteModal();
  setTimeout(() => { if (noteTextEl) noteTextEl.focus(); }, 100);
}

function addNoteEntry(id, text, source) {
  const trimmed = (text || '').trim();
  if (!trimmed) return;
  if (typeof notes === 'undefined') return;

  if (!notes[id]) notes[id] = [];
  notes[id].push({
    id: typeof dgeGenId === 'function' ? dgeGenId() : String(Date.now()),
    text: trimmed,
    source: source || 'Manual',
    addedAt: Date.now()
  });

  if (typeof dgeSaveNotes === 'function') dgeSaveNotes();
  if (typeof renderList === 'function') renderList();
  if (window.currentActionsSheetId === id && typeof renderActionsSheetContent === 'function') {
    renderActionsSheetContent(id);
  }
}

function saveNote() {
  const noteTextEl = document.getElementById('noteText');
  if (!noteTextEl) return;
  addNoteEntry(window.targetNoteId, noteTextEl.value, 'Manual');
  closeNoteModal();
  if (typeof showToast === 'function') showToast(`Note added for Shloka ${window.targetNoteId}!`);
}

function toggleMaximizeNote() {
  const box = document.getElementById('noteModalBox');
  const btn = document.getElementById('maxNoteBtn');
  if (!box || !btn) return;

  box.classList.toggle('fullscreen');
  btn.innerText = box.classList.contains('fullscreen') ? '🗗 Minimize' : '⛶ Expand';
}

window.deleteNoteEntry = function(id, entryIndex) {
  if (typeof notes === 'undefined' || !notes[id]) return;
  notes[id].splice(entryIndex, 1);
  if (notes[id].length === 0) delete notes[id];

  if (typeof dgeSaveNotes === 'function') dgeSaveNotes();
  if (typeof renderList === 'function') renderList();
  if (typeof renderActionsSheetContent === 'function') renderActionsSheetContent(id);
  if (typeof showToast === 'function') showToast('Note entry deleted.');
};

window.copyNoteEntry = async function(id, entryIndex) {
  if (typeof notes === 'undefined' || !notes[id] || !notes[id][entryIndex]) return;
  const text = notes[id][entryIndex].text;
  try {
    if (navigator.clipboard) {
      await navigator.clipboard.writeText(text);
    } else {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.left = '-9999px';
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      ta.remove();
    }
    if (typeof showToast === 'function') showToast('Note copied to clipboard.');
  } catch (e) {
    console.error('Copy note failed', e);
    if (typeof showToast === 'function') showToast('Could not copy this note.');
  }
};

window.shareNoteEntry = async function(id, entryIndex) {
  if (typeof notes === 'undefined' || !notes[id] || !notes[id][entryIndex]) return;
  const entry = notes[id][entryIndex];
  const text = `${entry.text}\n\n— Note on Shloka ${id} (${entry.source}), ${document.title || 'Sarvamoola Digital Library'}`;

  try {
    if (navigator.share) {
      await navigator.share({ text, title: `Shloka ${id} — Note` });
      return;
    }
    if (navigator.clipboard) {
      await navigator.clipboard.writeText(text);
      if (typeof showToast === 'function') showToast('Note copied to clipboard.');
    }
  } catch (e) {
    if (e && e.name === 'AbortError') return;
    console.error('Share note failed', e);
    if (typeof showToast === 'function') showToast('Could not share this note.');
  }
};

// Called by the "➕ Add Selection to Notes" floating button inside the
// Acharya AI result modal.
function appendSelectedTextToNote(e) {
  if (e) e.preventDefault();

  const modalBtn = document.getElementById('modalAppendBtn');
  if (modalBtn) modalBtn.style.display = 'none';
  if (window.getSelection) window.getSelection().removeAllRanges();

  const targetId = (typeof currentAcharyaShlokaId !== 'undefined' && currentAcharyaShlokaId) ? currentAcharyaShlokaId :
                   ((typeof contextShlokaId !== 'undefined' && contextShlokaId) ? contextShlokaId :
                   ((typeof activeId !== 'undefined' && activeId) ? activeId : null));

  if (!targetId) {
    if (typeof showToast === 'function') showToast('Please tap on a Shloka card first to make it active before appending notes.');
    return;
  }
  if (typeof modalSelectedText === 'undefined' || !modalSelectedText) return;

  addNoteEntry(targetId, modalSelectedText, 'Acharya Excerpt');
  if (typeof showToast === 'function') showToast(`Successfully added excerpt to Shloka ${targetId} notes!`);
};

window.openNoteModal = openNoteModal;
window.closeNoteModal = closeNoteModal;
window.openNote = openNote;
window.addNoteEntry = addNoteEntry;
window.saveNote = saveNote;
window.toggleMaximizeNote = toggleMaximizeNote;
window.appendSelectedTextToNote = appendSelectedTextToNote;
