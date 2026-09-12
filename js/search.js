// js/search.js
// Maps to F-005: Search & Highlighting
window.DGE_VERSIONS = window.DGE_VERSIONS || {};
window.DGE_VERSIONS['search.js'] = 'v1.1 (Removed duplicate highlightText/navSearch)';

function handleSearch() {
  const searchInput = document.getElementById('searchInput');
  const clearSearchBtn = document.getElementById('clearSearchBtn');

  if (clearSearchBtn && searchInput) {
    clearSearchBtn.style.display = searchInput.value ? 'block' : 'none';
  }

  // A new search narrows (or widens) which shlokas match, so whatever list-
  // mode page the reader was on before no longer means the same thing --
  // start back at page 1 rather than landing wherever the old page number
  // happens to still clamp to in the new result set (see render.js).
  window.dgeListPage = 0;
  
  if (typeof searchDebounceTimer !== 'undefined') {
    clearTimeout(searchDebounceTimer);
  }
  
  searchDebounceTimer = setTimeout(() => {
    if (typeof renderList === 'function') renderList();
  }, 120);
}

function clearSearch() {
  const searchInput = document.getElementById('searchInput');
  const navContainer = document.getElementById('searchNavigator');
  
  if (searchInput) searchInput.value = '';
  if (navContainer) navContainer.style.display = 'none';
  
  handleSearch();
}

// highlightText() and navSearch() live in render.js — they operate on
// window.searchMatches / window.currentMatchIdx, which render.js owns.
// (A duplicate copy used to live here too; since both were plain function
// declarations sharing one global scope, whichever script ran last simply
// overwrote the other with no error — fragile and confusing, so removed.)
