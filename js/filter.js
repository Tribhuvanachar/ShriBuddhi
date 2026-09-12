// js/filter.js
// Maps to Feature: Filter
window.DGE_VERSIONS = window.DGE_VERSIONS || {};
window.DGE_VERSIONS['filter.js'] = 'v4.0 (per-criterion Include/Exclude filter state, replacing v3.0\'s OR-only checkboxes + the whole-set Negate toggle)';

// Each mark-based criterion (fav/pending/practice/done/doubt) is now its
// own independent tri-state: unset, 'include', or 'exclude' -- ashtadhyayi.
// com's own filter panels let you negate ANY ONE filter on its own
// ("Negate this filter" per facet), not just the whole checked set at
// once, which is what the previous whole-set Match/Negate toggle could
// do. Combining rule, the standard faceted-search one: a shloka passes if
// (no criteria are set to 'include', OR it matches at least one of them)
// AND (it matches NONE of the criteria set to 'exclude'). That reduces
// exactly to the old OR-only behaviour when only 'include' is ever used,
// and to the old whole-set Negate when every checked criterion is
// 'exclude' -- this supersedes both without losing either.
// "Single Track" (no auto-advance to the next matching shloka) stays a
// separate toggle, tracked via the existing window.currentFilter —
// audio.js already checks for currentFilter === 'none' to skip
// auto-advance, so that's left as-is.
window.filterCriteriaState = window.filterCriteriaState || {};

const DGE_FILTER_CRITERIA = ['fav', 'pending', 'practice', 'done', 'doubt'];

function dgeFilterCriterionMatches(type, m) {
  switch (type) {
    case 'fav': return !!(m && m.fav);
    case 'pending': return !!(m && m.status === 'pending');
    case 'practice': return !!(m && m.status === 'practice');
    case 'done': return !!(m && m.status === 'done');
    case 'doubt': return !!(m && m.doubt);
    default: return false;
  }
}

function getFilteredIds() {
  if (!stotraData) return [];
  let ids = [];
  const total = stotraData.metadata.totalShlokas || Object.keys(stotraData.shlokas).length;

  const rangeStartEl = document.getElementById('rangeStart');
  const rangeEndEl = document.getElementById('rangeEnd');

  const rs = rangeStartEl ? parseInt(rangeStartEl.value) : NaN;
  const re = rangeEndEl ? parseInt(rangeEndEl.value) : NaN;
  const rm = window.currentRangeMode || 'include';
  const hasRange = !isNaN(rs) && !isNaN(re) && rs <= re;

  const state = window.filterCriteriaState || {};
  const includeCriteria = DGE_FILTER_CRITERIA.filter(t => state[t] === 'include');
  const excludeCriteria = DGE_FILTER_CRITERIA.filter(t => state[t] === 'exclude');

  for (let i = 1; i <= total; i++) {
    if (includeCriteria.length || excludeCriteria.length) {
      const m = (typeof marks !== 'undefined') ? marks[i] : null;
      if (includeCriteria.length && !includeCriteria.some(t => dgeFilterCriterionMatches(t, m))) continue;
      if (excludeCriteria.some(t => dgeFilterCriterionMatches(t, m))) continue;
    }

    if (hasRange) {
      const inR = (i >= rs && i <= re);
      if ((rm === 'include' && !inR) || (rm === 'exclude' && inR)) continue;
    }

    // Section / category filter (layer-stitch.js's section navigator, when
    // a grantha's items carry a `category` heading): show only the verses
    // under the chosen heading. Keyed on that same category string, so one
    // dropdown both lists the headings and filters to them.
    if (window.dgeSectionFilterKey) {
      const sh = stotraData.shlokas[i];
      if (!sh || (sh.category || '') !== window.dgeSectionFilterKey) continue;
    }

    ids.push(i);
  }
  return ids;
}

function clearRange() {
  const rangeStartEl = document.getElementById('rangeStart');
  const rangeEndEl = document.getElementById('rangeEnd');

  if (rangeStartEl) rangeStartEl.value = "";
  if (rangeEndEl) rangeEndEl.value = "";
  applyRangeFilter();
}

// Replaces the old native <select id="rangeMode"> with a two-button
// toggle matching the rest of the app's popup styling (native <select>
// dropdowns render as an OS picker on mobile, jarringly inconsistent with
// every other custom-styled option list in this popup).
window.currentRangeMode = 'include';
window.setRangeMode = function(mode, btnEl) {
  window.currentRangeMode = mode;
  const toggle = document.getElementById('rangeModeToggle');
  if (toggle) {
    toggle.querySelectorAll('.range-mode-btn').forEach(b => b.classList.toggle('active', b === btnEl));
  }
  applyRangeFilter();
};

function dgeJumpToFirstFiltered() {
  const aIds = getFilteredIds();
  if (aIds.length) {
    // Select and scroll to the first filtered shloka; do not start audio
    // as a side effect of toggling a mark filter.
    if (typeof loadShloka === 'function') loadShloka(aIds[0]);
  } else {
    if (typeof currentAudio !== 'undefined' && currentAudio) currentAudio.pause();
    if (typeof activeId !== 'undefined') activeId = null;
    if (typeof isPlaying !== 'undefined') isPlaying = false;
    if (typeof updatePlayUI === 'function') updatePlayUI();
  }
}

// Cycles one criterion through unset -> include -> exclude -> unset on
// each tap, matching the checkbox's own visual states (☐ / ☑ include /
// ☒ exclude). Any number of criteria can be independently include'd
// and/or exclude'd at once -- see getFilteredIds()'s combining rule above.
window.cycleFilterCriterion = function(type) {
  if (!window.filterCriteriaState) window.filterCriteriaState = {};
  const current = window.filterCriteriaState[type];
  const next = current === undefined ? 'include' : (current === 'include' ? 'exclude' : undefined);
  if (next === undefined) delete window.filterCriteriaState[type];
  else window.filterCriteriaState[type] = next;

  const el = document.querySelector(`#filterPopup .filter-checkbox-item[data-filter-type="${type}"]`);
  if (el) {
    el.classList.toggle('active', next === 'include');
    el.classList.toggle('excluded', next === 'exclude');
  }

  if (typeof renderList === 'function') renderList();
  dgeJumpToFirstFiltered();
};

window.clearAllFilterCriteria = function() {
  window.filterCriteriaState = {};
  document.querySelectorAll('#filterPopup .filter-checkbox-item').forEach(el => el.classList.remove('active', 'excluded'));
  if (typeof renderList === 'function') renderList();
  dgeJumpToFirstFiltered();
};

// "Single Track" — a separate toggle for turning OFF auto-advance to the
// next filtered shloka, independent of which mark criteria are checked.
window.toggleSingleTrackMode = function() {
  const isSingleTrack = (typeof currentFilter !== 'undefined' && currentFilter === 'none');
  if (typeof currentFilter !== 'undefined') currentFilter = isSingleTrack ? 'all' : 'none';

  const btn = document.getElementById('opt-none');
  if (btn) btn.classList.toggle('active', !isSingleTrack);
};

// Kept for backward compatibility with any older direct call.
function setFilter(type) {
  if (type === 'none') { window.toggleSingleTrackMode(); return; }
  if (type === 'all') { window.clearAllFilterCriteria(); return; }
  window.cycleFilterCriterion(type);
}

function applyRangeFilter() {
  if (typeof renderList === 'function') renderList();
  const aIds = getFilteredIds();
  if (aIds.length && (typeof currentFilter === 'undefined' || currentFilter !== 'none')) {
      // Select, don't play — changing the range should not start audio.
      if (typeof loadShloka === 'function') loadShloka(aIds[0]);
  }
}
