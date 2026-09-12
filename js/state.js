// DGE Module: state.js
window.DGE_VERSIONS = window.DGE_VERSIONS || {};
window.DGE_VERSIONS['state.js'] = 'v2.1 (AI Excerpt legacy-note migration)';

window.activeScript = localStorage.getItem('app_script') || 'devanagari';
window.activeId = null;
window.stotraData = null;
window.currentAudio = new Audio();
window.isPlaying = false;
window.currentFilter = 'all';
// Real bug found via live testing, 24 Aug: this used to be a single
// string ('none'/'all'/one specific key), so picking a second commentary
// silently replaced the first instead of adding to it -- "I can only
// choose one commentary... I can choose any number of commentaries."
// Now a Set of every currently-selected commentary key; empty = Mula Only.
window.selectedCommentaries = new Set();

// Safe empty defaults. Real data is loaded by window.loadPersistedState()
// once window.stotraCode is known (see core.js initApp()) — stotraCode
// isn't set yet at this point in the load sequence, so we can't resolve
// the correct namespaced key here.
window.marks = {};
window.notes = {};
window.snippets = {};

// Namespaced localStorage key helper. This existed in the old single-file
// legacy app (js/legacy/...) but was never carried over when the app was
// split into modules — every save call elsewhere (markers.js, notes.js,
// snippets.js, audio.js's "Preload All Audio") was guarded by
// `typeof nsKey === 'function'`, which was always false, so none of them
// ever actually persisted. This restores it.
window.nsKey = function(base) {
  return `narasimha_${base}_${window.stotraCode || 'pns'}`;
};

function dgeGenId() {
  return Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 7);
}

// Loads marks/notes/snippets for the current stotraCode, migrating older
// on-disk shapes forward:
//  - marks[id] used to be a bare string ('fav' | 'practice'). It's now
//    { fav: bool, status: 'pending'|'practice'|'done'|null, doubt: bool }.
//  - notes[id] used to be a single concatenated string. It's now an array
//    of individually shareable/deletable entries:
//    [{ id, text, source, addedAt }, ...]
window.loadPersistedState = function() {
  try {
    const rawMarks = JSON.parse(localStorage.getItem(nsKey('marks')) || '{}');
    const migratedMarks = {};
    Object.keys(rawMarks).forEach(id => {
      const v = rawMarks[id];
      if (v && typeof v === 'object') {
        migratedMarks[id] = { fav: !!v.fav, status: v.status || null, doubt: !!v.doubt };
      } else if (v === 'fav') {
        migratedMarks[id] = { fav: true, status: null, doubt: false };
      } else if (v === 'practice') {
        migratedMarks[id] = { fav: false, status: 'practice', doubt: false };
      }
    });
    window.marks = migratedMarks;
  } catch (e) {
    console.warn('Could not load marks:', e);
    window.marks = {};
  }

  try {
    const rawNotes = JSON.parse(localStorage.getItem(nsKey('notes')) || '{}');
    const migratedNotes = {};
    Object.keys(rawNotes).forEach(id => {
      const v = rawNotes[id];
      if (Array.isArray(v)) {
        migratedNotes[id] = v.map(entry => {
          if (entry && entry.source === 'AI Excerpt') return { ...entry, source: 'Acharya Excerpt' };
          return entry;
        });
      } else if (typeof v === 'string' && v.trim()) {
        migratedNotes[id] = [{ id: dgeGenId(), text: v, source: 'Migrated Note', addedAt: Date.now() }];
      }
    });
    window.notes = migratedNotes;
    dgeSaveNotes();
  } catch (e) {
    console.warn('Could not load notes:', e);
    window.notes = {};
  }

  try {
    window.snippets = JSON.parse(localStorage.getItem(nsKey('snippets')) || '{}');
  } catch (e) {
    console.warn('Could not load snippets:', e);
    window.snippets = {};
  }
};

function dgeSaveMarks() { localStorage.setItem(nsKey('marks'), JSON.stringify(window.marks)); }
function dgeSaveNotes() { localStorage.setItem(nsKey('notes'), JSON.stringify(window.notes)); }
window.dgeSaveMarks = dgeSaveMarks;
window.dgeSaveNotes = dgeSaveNotes;
window.dgeGenId = dgeGenId;
