// js/actions.js
// Maps to F-014: Unified Shloka Actions Sheet
// One entry point (the ⋯ button on each card) for everything spread
// across marks (favorite / status / doubt), notes, and saved snippets —
// plus download & share for the full shloka and for individual snippets
// and note entries.

window.DGE_VERSIONS = window.DGE_VERSIONS || {};
window.DGE_VERSIONS['actions.js'] = 'v3.3 (the two Image download/share buttons collapsed into a single "Preview & Share Image" action, routing through screenshot.js\'s new openShareImagePreview() instead of firing download/share immediately)';

window.currentActionsSheetId = null;

const STATUS_LABELS = {
  pending: { icon: '○', label: 'Pending' },
  practice: { icon: '🚧', label: 'Needs Practice' },
  done: { icon: '✅', label: 'Done' }
};

window.openActionsSheet = function(id) {
  window.currentActionsSheetId = id;
  if (typeof renderActionsSheetContent === 'function') renderActionsSheetContent(id);
  if (typeof openModal === 'function') openModal('actionsSheetModal');
};

window.renderActionsSheetContent = function(id) {
  const container = document.getElementById('actionsSheetContainer');
  if (!container || typeof stotraData === 'undefined' || !stotraData) return;

  const numEl = document.getElementById('actionsSheetShlokaNum');
  if (numEl) numEl.innerText = id;

  const m = (typeof marks !== 'undefined' && marks[id]) ? marks[id] : { fav: false, status: null, doubt: false };
  const noteEntries = (typeof notes !== 'undefined' && notes[id]) ? notes[id] : [];
  const snippetList = (typeof snippets !== 'undefined' && snippets[id]) ? snippets[id] : [];
  const flags = (typeof dgeGetEffectiveFeatureFlags === 'function') ? dgeGetEffectiveFeatureFlags() : {};

  let html = '';

  // Favorite/Status/Doubt are directly on the card itself (tap the
  // ★ / status / ❓ chips) — this line is just a summary, and only shows
  // the parts whose feature flag is actually on.
  const summaryParts = [];
  if (flags.showFavorite) summaryParts.push(m.fav ? '★ Favorite' : '☆ Not favorited');
  if (flags.showStatus) summaryParts.push(m.status ? STATUS_LABELS[m.status].icon + ' ' + STATUS_LABELS[m.status].label : '○ No status');
  if (flags.showDoubt) summaryParts.push(m.doubt ? '❓ Has doubt' : 'No doubt marked');
  if (summaryParts.length) {
    html += `<div style="display:flex; gap:8px; margin-bottom:18px; font-size:11px; color:var(--muted-text); align-items:center;">`;
    html += `<span>${summaryParts.join(' · ')}</span>`;
    html += `</div>`;
  }

  // --- Ask Acharya (works without selecting any text first) ---
  const acharyaTypes = (typeof dgeGetEffectiveQueryTypes === 'function') ? dgeGetEffectiveQueryTypes() : [];
  const acharyaButtons = acharyaTypes.filter(q => q.enabled && q.id !== 'grammar').map(q => {
    const action = q.action === 'bhashya'
      ? `window.closeModal('actionsSheetModal'); window.openBhashyaPickerForShloka(${id});`
      : `window.closeModal('actionsSheetModal'); window.askAcharyaForShloka(${id}, '${q.id}');`;
    return `<button class="btn-sm" style="flex:1; min-width:100px;" onclick="${action}">${q.icon} ${q.label}</button>`;
  }).join('');
  if (acharyaButtons) {
    html += `<div class="actions-section-label">🕉️ Ask Acharya</div>`;
    html += `<div style="display:flex; gap:8px; flex-wrap:wrap; margin-bottom:18px;">${acharyaButtons}</div>`;
  }

  // --- Notes (structured, individually shareable) ---
  if (flags.showNotes !== false) {
  html += `<div class="actions-section-label">Notes (${noteEntries.length})</div>`;
  if (noteEntries.length === 0) {
    html += `<div class="note-preview-box empty" style="margin-bottom:10px;">No notes yet.</div>`;
  } else {
    html += `<div style="display:flex; flex-direction:column; gap:8px; margin-bottom:10px;">`;
    noteEntries.forEach((entry, idx) => {
      const preview = entry.text.length > 160 ? entry.text.slice(0, 160) + '…' : entry.text;
      const when = new Date(entry.addedAt).toLocaleDateString();
      html += `
        <div class="note-preview-box" style="margin-bottom:0;">
          <div style="font-size:10px; color:var(--muted-text); margin-bottom:4px; display:flex; justify-content:space-between;">
            <span>${(entry.source || 'Manual').replace(/</g, '&lt;')} · ${when}</span>
          </div>
          <div>${typeof dgeRenderNoteMarkdown === 'function' ? dgeRenderNoteMarkdown(preview) : preview.replace(/</g, '&lt;')}</div>
          <div style="display:flex; gap:6px; margin-top:8px;">
            <button class="btn-icon" title="Copy this note" onclick="window.copyNoteEntry(${id}, ${idx})">📋</button>
            <button class="btn-icon" title="Share this note" onclick="window.shareNoteEntry(${id}, ${idx})">📤</button>
            <button class="btn-icon" title="Delete this note" style="color:var(--accent-red);" onclick="window.deleteNoteEntry(${id}, ${idx})">🗑️</button>
          </div>
        </div>`;
    });
    html += `</div>`;
  }
  html += `<button class="btn-sm" style="width:100%; margin-bottom:18px;" onclick="window.closeModal('actionsSheetModal'); window.openNote(${id});">➕ Add Note</button>`;
  }

  // --- Snippets ---
  if (flags.showSnippetTools !== false) {
  html += `<div class="actions-section-label">Saved Snippets (${snippetList.length})</div>`;
  if (snippetList.length === 0) {
    html += `<div class="note-preview-box empty" style="margin-bottom:18px;">No snippets yet. In 🛠 Tools, turn on ✂️ Active Loop, set Start/End (or use 🎯 Auto A-B Capture), then 💾 Save Snippet.</div>`;
  } else {
    html += `<div style="display:flex; flex-direction:column; gap:8px; margin-bottom:18px;">`;
    snippetList.forEach((s, idx) => {
      const dur = (s.end - s.start).toFixed(1);
      html += `
        <div class="snippet-row">
          <div style="flex-grow:1; min-width:0;">
            <div style="font-weight:700; font-size:12px;">${s.start.toFixed(1)}s – ${s.end.toFixed(1)}s
              <span style="color:var(--muted-text); font-weight:600;">(${dur}s)</span>
            </div>
          </div>
          <div class="snippet-row-actions">
            <button class="btn-icon" title="Play" onclick="window.playSnippet(${id}, ${s.start}, ${s.end})">▶️</button>
            <button class="btn-icon" title="Download" onclick="window.downloadSnippetAudio(${id}, ${s.start}, ${s.end})">⬇️</button>
            <button class="btn-icon" title="Share" onclick="window.shareShlokaAudio(${id}, {start:${s.start}, end:${s.end}})">📤</button>
            <button class="btn-icon" title="Delete" style="color:var(--accent-red);" onclick="window.deleteSnippet(${id}, ${idx})">🗑️</button>
          </div>
        </div>`;
    });
    html += `</div>`;
  }
  } // end flags.showSnippetTools

  // --- Full shloka download / share ---
  html += `<div class="actions-section-label">Share this verse</div>`;
  if (typeof dgeShlokaReference === 'function') {
    const ref = dgeShlokaReference(id);
    html += `<div style="font-size:11px; color:var(--muted-text); margin-bottom:8px; line-height:1.5;">${ref.line.replace(/</g, '&lt;')}${ref.short ? ` · <span style="font-weight:700;">?${ref.short}</span>` : ''}</div>`;
  }
  html += `<div style="display:flex; gap:8px; margin-bottom:8px;">`;
  html += `<button class="btn-sm" style="flex:1;" onclick="window.dgeShareShlokaLink(${id})">📤 Share link</button>`;
  html += `<button class="btn-sm" style="flex:1;" onclick="window.dgeCopyShlokaLink(${id})">🔗 Copy link</button>`;
  html += `</div>`;
  html += `<button class="btn-sm" style="width:100%; margin-bottom:8px;" onclick="if(typeof copyShlokaText==='function') copyShlokaText(${id})">📋 Copy Shloka Text</button>`;
  html += `<div style="display:flex; gap:8px; margin-bottom:8px;">`;
  html += `<button class="btn-sm" style="flex:1;" onclick="window.downloadFullShlokaAudio(${id})">⬇️ Audio</button>`;
  html += `<button class="btn-sm" style="flex:1;" onclick="window.shareShlokaAudio(${id})">📤 Share Text + Audio</button>`;
  html += `</div>`;
  html += `<button class="btn-sm" style="width:100%; margin-bottom:8px;" onclick="window.openShareImagePreview(${id})">🖼️ Preview &amp; Share Image</button>`;
  html += `<button class="btn-sm" style="width:100%;" onclick="window.shareShlokaTextOnly(${id})">📝 Share Text Only</button>`;
  html += `<div style="font-size:10px; color:var(--muted-text); margin-top:6px; line-height:1.5;">Some apps (e.g. WhatsApp for audio files) drop the caption text when sharing a file — use "Text Only" if the combined share arrives without it.</div>`;

  container.innerHTML = html;
};
