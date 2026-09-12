// dge/js/content-editor.js — admin/superadmin in-place content editor for
// already-published grantha pages. Two edit modes, matching the project
// lead's explicit ask: quick inline text fixes right on the reading page,
// and a structural popup editor (move/insert/delete, like Convert's schema
// editor) for reordering the shloka set. Nothing pushes to GitHub on a
// keystroke — edits stay staged in memory until a human reviews a preview
// and confirms, reusing admin-editor.js's existing dgeAdminBatchCommit
// (same safe "diff, don't blind-overwrite" discipline as Config Editor).
//
// This is deliberately a SEPARATE tool from content-inline.js, not a mode
// of it: this one edits the corpus (shloka text, in admin/content/*.json
// grantha files, with reorder/insert/delete), while content-inline.js
// edits page chrome (titles, panel copy, labels — small JSON page-content
// files unrelated to any grantha). Merging them would let one wrong click
// send a UI-copy edit through the shloka save path or vice versa. Kept
// visually distinct instead: content-inline.js floats as a collapsed
// "EDIT" tab on the left edge, while this one's toggle (✏️ Edit) sits
// inline, directly under the shloka it edits — so which tool is which is
// obvious from where its control lives, not from a label alone.
window.DGE_VERSIONS = window.DGE_VERSIONS || {};
window.DGE_VERSIONS['content-editor.js'] = 'v1.3';

window.dgeContentEditMode = false;
window.dgeContentEditsDirty = false;

// ------------------------------------------------------- draft autosave
// "Save" on an inline edit (or "Apply" in the structural editor) only
// ever staged the change in memory — nothing reaches GitHub until
// "Preview & Save" is clicked. A page refresh before that point silently
// discarded the edit with no explanation, which read as "it's not
// actually saving" even though the in-page reflection right after
// saving was real. Every staged edit now also mirrors into localStorage,
// keyed per grantha file, and is restored automatically before the first
// render on reload — so a refresh (or an accidental tab close) no longer
// loses work, and the save bar says plainly that this is local-only
// until published.
function dgeContentDraftKey() {
  return 'dgeContentDraft:' + (window.jsonFileName || '');
}

function dgePersistContentDraft() {
  try {
    localStorage.setItem(dgeContentDraftKey(), JSON.stringify({
      shlokas: stotraData.shlokas,
      totalShlokas: stotraData.metadata.totalShlokas,
      savedAt: Date.now()
    }));
  } catch (e) {
    console.warn('[content-editor] Could not persist draft to localStorage:', e);
  }
}

function dgeClearContentDraft() {
  try { localStorage.removeItem(dgeContentDraftKey()); } catch (e) { /* ignore */ }
}

// Called once from core.js right after stotraData is loaded and
// normalized, before the first render, so a restored draft is what the
// admin sees from the start instead of flashing the published version
// first. Returns true if a draft was actually applied, so the caller
// knows whether an extra render is needed.
window.dgeRestoreContentDraftIfAny = function () {
  if (!dgeContentEditorSupported()) return false;
  // Captured BEFORE any draft is applied, so the undo stack can tell "no
  // edits left" (matches what the server actually has right now) apart
  // from "back to the restored draft, which itself still isn't
  // published" — those are not the same state when a draft exists.
  window.dgeContentEditPristineSnapshot = {
    shlokas: JSON.parse(JSON.stringify(stotraData.shlokas)),
    totalShlokas: stotraData.metadata.totalShlokas
  };

  let raw;
  try { raw = localStorage.getItem(dgeContentDraftKey()); } catch (e) { return false; }
  if (!raw) return false;
  let draft;
  try { draft = JSON.parse(raw); } catch (e) { return false; }
  if (!draft || !draft.shlokas) return false;

  stotraData.shlokas = draft.shlokas;
  if (draft.totalShlokas) stotraData.metadata.totalShlokas = draft.totalShlokas;
  window.dgeContentEditsDirty = true;
  window.dgeContentDraftRestoredAt = draft.savedAt || null;
  return true;
};

function dgeMatchesPristineSnapshot() {
  const p = window.dgeContentEditPristineSnapshot;
  if (!p) return false; // unknown baseline -- stay conservative, treat as still dirty
  return stotraData.metadata.totalShlokas === p.totalShlokas
    && JSON.stringify(stotraData.shlokas) === JSON.stringify(p.shlokas);
}

function dgeTimeAgo(ms) {
  const s = Math.max(1, Math.round((Date.now() - ms) / 1000));
  if (s < 60) return `${s}s ago`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.round(h / 24)}d ago`;
}

// ------------------------------------------------------------ undo stack
// A bounded stack of full pre-edit snapshots (in memory only, not
// persisted across reloads) — each inline save or structural Apply
// pushes the state as it was just before that change, so "Undo" steps
// back one edit at a time. An empty stack does NOT by itself mean "back
// to published" — if a draft was restored from localStorage on load,
// that draft (not the true published data) is where the stack bottoms
// out, so dgeMatchesPristineSnapshot() (compared against the snapshot
// taken before any draft was applied) is what actually decides whether
// dirty/draft state clears.
window.dgeContentEditUndoStack = [];
const DGE_UNDO_STACK_MAX = 20;

function dgePushUndoSnapshot() {
  window.dgeContentEditUndoStack.push({
    shlokas: JSON.parse(JSON.stringify(stotraData.shlokas)),
    totalShlokas: stotraData.metadata.totalShlokas
  });
  if (window.dgeContentEditUndoStack.length > DGE_UNDO_STACK_MAX) {
    window.dgeContentEditUndoStack.shift();
  }
}

window.dgeUndoContentEdit = function () {
  const stack = window.dgeContentEditUndoStack;
  if (!stack.length) return;
  const prev = stack.pop();
  stotraData.shlokas = prev.shlokas;
  stotraData.metadata.totalShlokas = prev.totalShlokas;
  if (dgeMatchesPristineSnapshot()) {
    window.dgeContentEditsDirty = false;
    window.dgeContentDraftRestoredAt = null;
    dgeClearContentDraft();
  } else {
    window.dgeContentEditsDirty = true;
    dgePersistContentDraft();
  }
  if (typeof renderList === 'function') renderList();
  dgeRenderContentEditorSaveBar();
};

// Different granthas store pada (line) breaks differently — PNS and most
// stotras use literal "<br>" tags (rendered via innerHTML in the reading
// view), while Sumadhva Vijaya's sarga files use plain "\n" (which the
// reading view's CSS doesn't turn into a visual break at all). A plain
// <textarea> can't interpret either as HTML, so editing raw "<br>" text
// showed the tag itself as ugly literal characters. Converting to real
// newlines for editing — and back to "<br>" on save, since that's the
// only one of the two that actually renders as a line break — fixes the
// display AND upgrades any touched Sumadhva Vijaya verse to render
// correctly too, without touching verses nobody edited.
function dgeSaToEditableText(sa) {
  return (sa || '').replace(/<br\s*\/?>/gi, '\n');
}
function dgeEditableTextToSa(text) {
  return (text || '').replace(/\r\n/g, '\n').replace(/\n/g, '<br>');
}

// Only grantha files that fetch as the plain {metadata, shlokas:{n:{...}}}
// shape are safe to edit here — anything that needed dgeNormalizeGranthaData
// to flatten it (itihasa_purana_text's per-chapter nesting, vedic_text's
// items array) would need real denormalization logic to save back without
// corrupting the source file's actual shape, not built yet. Gating on this
// keeps the feature honest about what it can safely touch instead of
// silently mangling a file it doesn't fully understand.
function dgeContentEditorIsAdmin() {
  return document.body.classList.contains('is-authorized') || localStorage.getItem('is_superadmin') === 'true';
}

function dgeContentEditorSupported() {
  return dgeContentEditorIsAdmin() && !!window.stotraDataEditable;
}

function dgeContentEditorButtonHtml() {
  if (!dgeContentEditorSupported()) return '';
  return `<button id="contentEditToggleBtn" class="btn-sm" onclick="window.dgeToggleContentEditMode()"
            title="Edit this grantha's shlokas (admin only)">✏️ ${window.dgeContentEditMode ? 'Exit Edit' : 'Edit'}</button>`;
}

// Called once from index.html after the top controls exist. Re-runs are
// harmless (idempotent) since it just replaces its own mount point's
// contents each time renderContentEditorControls is invoked.
function dgeMountContentEditorControls() {
  const mount = document.getElementById('contentEditorMount');
  if (!mount) return;
  mount.innerHTML = dgeContentEditorButtonHtml();
  if (window.dgeContentEditMode) {
    mount.innerHTML += `<button class="btn-sm" onclick="window.dgeOpenStructuralEditor()" title="Reorder, insert, or delete shlokas">🔀 Reorder / Insert / Delete</button>`;
  }
  dgeRenderContentEditorSaveBar();
}

window.dgeToggleContentEditMode = function () {
  if (!dgeContentEditorSupported()) return;
  window.dgeContentEditMode = !window.dgeContentEditMode;
  if (typeof renderList === 'function') renderList();
  dgeMountContentEditorControls();
};

// ------------------------------------------------------------- inline edit
window.dgeInlineEditShloka = function (id) {
  const card = document.getElementById(`shloka-${id}`);
  if (!card) return;
  const textEl = card.querySelector('.shloka-text');
  if (!textEl || textEl.querySelector('textarea')) return; // already editing

  const shloka = stotraData.shlokas[id];
  const original = dgeSaToEditableText(shloka.sa || '');
  textEl.innerHTML = '';
  const ta = document.createElement('textarea');
  ta.value = original;
  ta.className = 'content-edit-textarea';
  ta.rows = Math.max(2, original.split('\n').length);
  textEl.appendChild(ta);

  const btnRow = document.createElement('div');
  btnRow.className = 'content-edit-btn-row';
  btnRow.innerHTML = `
    <button class="btn-sm" onclick="event.stopPropagation(); window.dgeSaveInlineEdit(${id})">✔ Save</button>
    <button class="btn-sm" onclick="event.stopPropagation(); if(typeof renderList==='function') renderList();">✕ Cancel</button>
  `;
  textEl.appendChild(btnRow);
  ta.focus();
  ta.addEventListener('click', e => e.stopPropagation());
};

window.dgeSaveInlineEdit = function (id) {
  const card = document.getElementById(`shloka-${id}`);
  const ta = card && card.querySelector('.content-edit-textarea');
  if (!ta) return;
  const newText = dgeEditableTextToSa(ta.value);
  if (newText !== stotraData.shlokas[id].sa) {
    dgePushUndoSnapshot();
    stotraData.shlokas[id].sa = newText;
    window.dgeContentEditsDirty = true;
    dgePersistContentDraft();
    if (typeof window.showToast === 'function') window.showToast(`Shloka ${id} saved in this browser — click "Preview & Save" below to publish it.`);
  }
  if (typeof renderList === 'function') renderList();
  dgeRenderContentEditorSaveBar();
};

// --------------------------------------------------------- structural edit
let dgeStructuralRows = null; // working copy while the modal is open

function dgeBuildStructuralRows() {
  const ids = Object.keys(stotraData.shlokas).map(Number).sort((a, b) => a - b);
  // Shallow-copy the whole original shloka object (not just sa/commentaries)
  // so fields like note/reviewNote survive a reorder — only sa's display
  // format changes here, for editing.
  return ids.map(id => Object.assign({}, stotraData.shlokas[id], {
    sa: dgeSaToEditableText(stotraData.shlokas[id].sa || ''),
    commentaries: stotraData.shlokas[id].commentaries || {}
  }));
}

window.dgeOpenStructuralEditor = function () {
  if (!dgeContentEditorSupported()) return;
  dgeStructuralRows = dgeBuildStructuralRows();
  dgeRenderStructuralModal();
};

function dgeStructuralStartNumber() {
  const ids = Object.keys(stotraData.shlokas).map(Number);
  return ids.length ? Math.min(...ids) : 1;
}

function dgeRenderStructuralModal() {
  let modal = document.getElementById('structuralEditorModal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'structuralEditorModal';
    modal.className = 'content-editor-modal-overlay';
    document.body.appendChild(modal);
  }
  const start = dgeStructuralStartNumber();
  const rowsHtml = dgeStructuralRows.map((r, i) => `
    <div class="content-editor-row" data-idx="${i}">
      <div class="content-editor-row-num">${start + i}</div>
      <textarea class="content-editor-row-ta" data-idx="${i}" rows="${Math.max(2, r.sa.split('\n').length)}">${r.sa.replace(/</g, '&lt;')}</textarea>
      <div class="content-editor-row-toolbar">
        <button class="row-btn" title="Move up" ${i === 0 ? 'disabled' : ''} onclick="window.dgeStructuralMove(${i}, -1)">↑</button>
        <button class="row-btn" title="Move down" ${i === dgeStructuralRows.length - 1 ? 'disabled' : ''} onclick="window.dgeStructuralMove(${i}, 1)">↓</button>
        <button class="row-btn" title="Insert new shloka after this one" onclick="window.dgeStructuralInsertAfter(${i})">➕</button>
        <button class="row-btn" title="Delete this shloka" onclick="window.dgeStructuralDelete(${i})">🗑</button>
      </div>
    </div>
  `).join('');

  modal.innerHTML = `
    <div class="content-editor-modal">
      <div class="content-editor-modal-header">
        <b>Reorder / Insert / Delete Shlokas</b>
        <span style="font-size:12px; color:#888;">Numbering starts at ${start} and renumbers sequentially — matches this grantha's existing convention.</span>
        <button class="btn-icon" onclick="window.dgeCloseStructuralEditor()">✕</button>
      </div>
      <div class="content-editor-modal-body" id="structuralEditorRows">${rowsHtml}</div>
      <div class="content-editor-modal-footer">
        <button class="btn-sm" onclick="window.dgeCloseStructuralEditor()">Cancel</button>
        <button class="btn-sm btn-primary" onclick="window.dgeApplyStructuralEdits()">Apply</button>
      </div>
    </div>
  `;
  modal.style.display = 'flex';

  modal.querySelectorAll('.content-editor-row-ta').forEach(ta => {
    ta.addEventListener('input', () => {
      dgeStructuralRows[Number(ta.dataset.idx)].sa = ta.value;
    });
  });
}

window.dgeCloseStructuralEditor = function () {
  const modal = document.getElementById('structuralEditorModal');
  if (modal) modal.style.display = 'none';
  dgeStructuralRows = null;
};

window.dgeStructuralMove = function (idx, dir) {
  const j = idx + dir;
  if (j < 0 || j >= dgeStructuralRows.length) return;
  const tmp = dgeStructuralRows[idx];
  dgeStructuralRows[idx] = dgeStructuralRows[j];
  dgeStructuralRows[j] = tmp;
  dgeRenderStructuralModal();
};

window.dgeStructuralInsertAfter = function (idx) {
  dgeStructuralRows.splice(idx + 1, 0, { sa: '', commentaries: {} });
  dgeRenderStructuralModal();
};

window.dgeStructuralDelete = function (idx) {
  if (!confirm('Delete this shloka from the working copy? This only affects the staged edit — nothing is pushed until you save.')) return;
  dgeStructuralRows.splice(idx, 1);
  dgeRenderStructuralModal();
};

window.dgeApplyStructuralEdits = function () {
  dgePushUndoSnapshot();
  const start = dgeStructuralStartNumber();
  const newShlokas = {};
  dgeStructuralRows.forEach((r, i) => {
    // Keep every original field (note, reviewNote, etc.) — only sa's
    // display format needs converting back from editable text to storage.
    newShlokas[start + i] = Object.assign({}, r, {
      sa: dgeEditableTextToSa(r.sa),
      commentaries: r.commentaries || {}
    });
  });
  stotraData.shlokas = newShlokas;
  stotraData.metadata.totalShlokas = dgeStructuralRows.length;
  window.dgeContentEditsDirty = true;
  dgePersistContentDraft();
  window.dgeCloseStructuralEditor();
  if (typeof renderList === 'function') renderList();
  dgeRenderContentEditorSaveBar();
  if (typeof window.showToast === 'function') window.showToast('Structural changes saved in this browser — click "Preview & Save" below to publish.');
};

// ------------------------------------------------------------------ saving
function dgeRenderContentEditorSaveBar() {
  let bar = document.getElementById('contentEditorSaveBar');
  if (!window.dgeContentEditsDirty) {
    if (bar) bar.remove();
    return;
  }
  if (!bar) {
    bar = document.createElement('div');
    bar.id = 'contentEditorSaveBar';
    bar.className = 'content-editor-save-bar';
    document.body.appendChild(bar);
  }
  const undoCount = (window.dgeContentEditUndoStack || []).length;
  const restoredNote = window.dgeContentDraftRestoredAt
    ? ` Restored from this browser's storage, last saved ${dgeTimeAgo(window.dgeContentDraftRestoredAt)}.`
    : '';
  bar.innerHTML = `
    <span>Edits are saved in this browser only, not yet published — nobody else sees them, but they'll survive a reload.${restoredNote}</span>
    <button class="btn-sm" ${undoCount ? '' : 'disabled'} onclick="window.dgeUndoContentEdit()" title="${undoCount ? `Undo the last edit (${undoCount} more after that)` : 'No edits to undo yet'}">↶ Undo</button>
    <button class="btn-sm" onclick="window.dgeDiscardContentEdits()">Discard all</button>
    <button class="btn-sm btn-primary" onclick="window.dgeOpenSavePreview()">Preview &amp; Save…</button>
  `;
}

window.dgeDiscardContentEdits = function () {
  if (!confirm('Discard all unsaved shloka edits and reload the original data?')) return;
  dgeClearContentDraft();
  window.dgeContentEditUndoStack = [];
  window.location.reload();
};

window.dgeOpenSavePreview = function () {
  const token = typeof dgeGithubToken === 'function' ? dgeGithubToken()
    : localStorage.getItem('github_admin_pat') || '';
  let modal = document.getElementById('contentSaveModal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'contentSaveModal';
    modal.className = 'content-editor-modal-overlay';
    document.body.appendChild(modal);
  }
  const fullPath = 'dge/' + window.jsonFileName;
  modal.innerHTML = `
    <div class="content-editor-modal" style="max-width:600px;">
      <div class="content-editor-modal-header"><b>Save changes to GitHub</b>
        <button class="btn-icon" onclick="document.getElementById('contentSaveModal').style.display='none'">✕</button>
      </div>
      <div class="content-editor-modal-body" style="padding:16px;">
        <p>This will push one commit updating:</p>
        <code style="display:block; padding:8px; background:#f4f4f4; border-radius:6px; word-break:break-all; color:#222;">${fullPath}</code>
        <p style="font-size:13px; color:#666;">${Object.keys(stotraData.shlokas).length} shloka(s) in the saved file after this change.</p>
        <label style="display:block; margin-top:12px; font-size:13px;">GitHub token (admin PAT — same one Config Editor uses):</label>
        <input type="password" id="contentEditorGhToken" value="${token}" style="width:100%; box-sizing:border-box;" placeholder="ghp_...">
      </div>
      <div class="content-editor-modal-footer">
        <button class="btn-sm" onclick="document.getElementById('contentSaveModal').style.display='none'">Cancel</button>
        <button class="btn-sm btn-primary" id="contentEditorPushBtn" onclick="window.dgePushContentEdits()">Push commit</button>
      </div>
    </div>
  `;
  modal.style.display = 'flex';
};

window.dgePushContentEdits = async function () {
  const tokenInput = document.getElementById('contentEditorGhToken');
  const token = tokenInput ? tokenInput.value.trim() : '';
  if (!token) { alert('Paste a GitHub token first.'); return; }
  localStorage.setItem('github_admin_pat', token);

  const btn = document.getElementById('contentEditorPushBtn');
  if (btn) { btn.disabled = true; btn.textContent = 'Pushing…'; }

  try {
    const fullPath = 'dge/' + window.jsonFileName;
    // Reconstruct the on-disk shape from the live (edited) stotraData —
    // only safe because dgeContentEditorSupported() already confirmed this
    // grantha's source file uses this exact {metadata, shlokas} shape with
    // no lossy normalization in between.
    const outShlokas = {};
    Object.keys(stotraData.shlokas).forEach(id => {
      const s = stotraData.shlokas[id];
      // Keep every field already on the in-memory shloka (note,
      // reviewNote, etc.) — previously this hand-picked only sa/
      // commentaries and silently dropped everything else on every push.
      outShlokas[id] = Object.assign({}, s, { commentaries: s.commentaries || {} });
    });
    const outData = {
      metadata: Object.assign({}, stotraData.metadata, { totalShlokas: Object.keys(outShlokas).length }),
      shlokas: outShlokas
    };
    const text = JSON.stringify(outData, null, 2) + '\n';
    const bytes = new TextEncoder().encode(text);

    const result = await dgeAdminBatchCommit(
      [{ path: fullPath, bytes }],
      `Edit shlokas via reading-page content editor: ${stotraData.metadata.title || fullPath}`
    );

    if (result.uploaded === 0) {
      alert('Nothing changed relative to what\'s already on GitHub — no commit made.');
    } else {
      // This site is served through GitHub Pages' CDN, which caches
      // responses for a few minutes independent of anything this app
      // does — the commit above is real and immediate (visible on
      // GitHub right away), but the LIVE site can lag behind it for a
      // short while. Said explicitly here since a refresh right after
      // pushing showing the old text looks exactly like a failed save
      // when it isn't one.
      alert(`Saved. Pushed ${result.uploaded} file(s) in one commit.\n\nThis site is served through GitHub Pages, which can take a few minutes to catch up on its own end — if a refresh right now still shows the old text, that's this CDN delay, not a failed save. The commit is already on GitHub.`);
    }
    window.dgeContentEditsDirty = false;
    dgeClearContentDraft();
    window.dgeContentEditUndoStack = [];
    window.dgeContentDraftRestoredAt = null;
    document.getElementById('contentSaveModal').style.display = 'none';
    dgeRenderContentEditorSaveBar();
  } catch (e) {
    alert('Push failed: ' + (e && e.message ? e.message : e));
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = 'Push commit'; }
  }
};
