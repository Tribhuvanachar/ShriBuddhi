// DGE Module: reader-state.js
// Reader redesign, section 33: "audit for duplicated state; converge on a
// coherent model" — ReaderState / StudyState / AudioState / AssistantState
// / SearchState.
//
// This is deliberately an ACCESSOR layer, not a rewrite of where state
// actually lives. The audit behind this redesign found nine-plus
// independent globals/localStorage keys (window.activeId, window.marks,
// audio.js's contextShlokaId, selection-modes.js's own mode singleton,
// ai.js's window.contextShlokaId/lastSelectedText, ...) — all still
// working, all read/written from many call sites across render.js,
// audio.js, ai.js, genie.js, markers.js, filter.js, history.js. Migrating
// every one of those call sites to a new store in one pass, while another
// session is concurrently landing changes to several of the same files
// (render.js, core.js), is exactly the kind of large blind rewrite this
// redesign was told NOT to do ("preserve all existing functionality").
//
// So: the existing globals stay the single source of truth (nothing here
// duplicates or shadows them), and this file gives the rest of the
// redesign — and any future code — ONE coherent, documented shape to read
// and write through instead of reaching into scattered globals directly.
// New code (contextual-actions.js, the shloka-card redesign) already goes
// through dgeReaderState()/dgeStudyState() where it touches this state.
// A future pass can move the underlying storage behind these functions
// without another cross-file migration, since callers only ever see the
// accessor.

window.DGE_VERSIONS = window.DGE_VERSIONS || {};
window.DGE_VERSIONS['reader-state.js'] = 'v1.0 (canonical state accessor layer over existing globals)';

(function () {
  'use strict';

  // ReaderState { selectedGrantha, selectedChapter, selectedShloka,
  //               selectedWord, selectedCommentary }
  window.dgeReaderState = function () {
    var sel = window.getSelection ? window.getSelection() : null;
    var selText = sel ? sel.toString().trim() : '';
    var isSingleWord = !!selText && !/\s/.test(selText);
    return {
      selectedGrantha: window.currentGranthaSlug || null,
      selectedChapter: (window.stotraData && window.stotraData.metadata && window.stotraData.metadata.currentChapter) || null,
      selectedShloka: (window.contextShlokaId != null) ? window.contextShlokaId : (window.activeId != null ? window.activeId : null),
      selectedWord: isSingleWord ? selText : null,
      selectedPhrase: (selText && !isSingleWord) ? selText : null,
      selectedCommentary: (window.selectedCommentaries && window.selectedCommentaries.size) ? Array.from(window.selectedCommentaries) : []
    };
  };

  // StudyState { favorite, readingStatus, doubt, notes } for one shloka id
  // — the same shape markers.js/state.js already persist per id
  // (window.marks[id]), just read through one named accessor instead of
  // reaching into the raw object at every call site.
  window.dgeStudyState = function (shlokaId) {
    var m = (typeof window.marks !== 'undefined' && window.marks) ? window.marks[shlokaId] : null;
    var noteList = (typeof window.notes !== 'undefined' && window.notes) ? (window.notes[shlokaId] || []) : [];
    return {
      favorite: !!(m && m.fav),
      readingStatus: m ? (m.status || null) : null, // null | 'practice' | 'done'
      doubt: !!(m && m.doubt),
      notes: noteList
    };
  };

  // AudioState { status, currentItem, position, duration, queue }
  // status is derived from currentAudio (a real HTMLMediaElement,
  // state.js) rather than tracked separately, so it can never drift from
  // what's actually playing — see section 9's IDLE/LOADED/PLAYING/PAUSED/
  // BUFFERING/COMPLETED/ERROR state list.
  window.dgeAudioState = function () {
    var a = window.currentAudio;
    if (!a || !window.activeId) {
      return { status: 'idle', currentItem: null, position: 0, duration: 0, queue: [] };
    }
    var status = 'idle';
    if (a.error) status = 'error';
    else if (a.ended) status = 'completed';
    else if (!a.paused && !a.ended) status = a.readyState < 3 ? 'buffering' : 'playing';
    else if (a.paused && a.currentTime > 0) status = 'paused';
    else if (a.readyState > 0) status = 'loaded';
    return {
      status: status,
      currentItem: window.activeId,
      position: a.currentTime || 0,
      duration: a.duration || 0,
      queue: (typeof window.dgeGetFilteredIds === 'function') ? window.dgeGetFilteredIds() : []
    };
  };

  // AssistantState { context, open, mode } for Ask Acharya / Genie.
  window.dgeAssistantState = function () {
    var modal = document.getElementById('acharyaModal');
    var reader = window.dgeReaderState();
    var context = reader.selectedWord ? { type: 'word', text: reader.selectedWord }
      : reader.selectedPhrase ? { type: 'phrase', text: reader.selectedPhrase }
      : (reader.selectedShloka != null) ? { type: 'shloka', shlokaId: reader.selectedShloka }
      : { type: 'none' };
    return {
      context: context,
      open: !!(modal && modal.style.display === 'flex'),
      mode: window.currentAcharyaShlokaId != null ? 'shloka' : (context.type === 'word' ? 'word' : 'general')
    };
  };

  // SearchState { query, filters, results, selectedResult } — best-effort:
  // global search owns its own state (dge/js/global-search.js,
  // dge-search.js, the parallel session's territory per this redesign's
  // brief); this only reports the in-reader corpus search box, which this
  // file's module already had visibility into.
  window.dgeSearchState = function () {
    var input = document.getElementById('searchInput');
    return {
      query: input ? input.value : '',
      filters: { scope: window.currentSearchScope || 'all' },
      results: null,
      selectedResult: null
    };
  };
})();
