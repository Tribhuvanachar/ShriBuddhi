// DGE Module: ai.js
// Maps to F-014: AI Assistance
window.DGE_VERSIONS = window.DGE_VERSIONS || {};
window.DGE_VERSIONS['ai.js'] = 'v3.19 (Android\'s native "Translate / Copy / Select all" selection toolbar no longer lingers on top of the Genie sheet: selectionchange now clears the live browser selection the moment the sheet appears, substituting a .dge-word-picked highlight on the actual .dge-word span(s) so the reader still sees what\'s selected; a reader\'s first tap on a sheet button used to be silently consumed by Android dismissing its own toolbar instead of reaching the button. dgeSelectedWordText() now falls back to window.lastSelectedText once the live selection is gone. Everything from v3.18 unchanged.)';

// Appends a language directive read from onboarding.js's saved preference
// (dge_lang_pref: en/kn/sa), so every dgeCallProvider() call answers in the
// language the visitor picked, without the visitor having to ask for it
// every time. Empty string (no line added) when unset or English, since
// English is the model's natural default anyway.
function dgeLangInstruction() {
  var lang;
  try { lang = localStorage.getItem('dge_lang_pref'); } catch (e) { lang = null; }
  var line = { kn: 'Answer in Kannada (ಕನ್ನಡ) unless the user writes in a different language.',
               sa: 'Answer in simple Sanskrit (संस्कृतम्) unless the user writes in a different language.' }[lang];
  return line ? (' ' + line) : '';
}

// 1. Text Selection & Tooltip Event Listener
//
// No longer gated on is-authorized (admin AI-key unlock): the Shabda/Dhātu/
// Where-else word tools (#wordToolsRow) need no AI at all and are this
// app's own structured-data lookups, and askAcharya() already handles the
// no-key-configured case on its own (a friendly "configure a key" message,
// not a crash) -- so there was never a reason a plain reader couldn't even
// SEE this tooltip. Previously this returned before the tooltip could ever
// show for anyone without acharyaAuthorized set, which silently hid the
// word tools from every ordinary visitor, not just Ask Acharya.
// Contextual selection tooltip (24 Aug 2026, project lead's direct report:
// "clicking on a word or selecting a word should display the options
// contextually. That is also not happening"). Confirmed the tooltip itself
// was never actually failing to appear (verified live: a real selection
// correctly shows it) -- the real gap was that #wordToolsRow's word-level
// grammar tools (Shabda/Dhatu/Sandhi/Samasa) showed up identically whether
// the reader had selected a single word or dragged across a whole phrase,
// even though every one of those tools does a lookup that is only
// meaningful for exactly one word (a declension table, a dhatupatha root
// search, a per-word sandhi split) -- tapping any of them on a multi-word
// selection was a dead end, not a helpful contextual option. "Search
// Library" (corpus search) is left showing for both, since searching a
// phrase is perfectly reasonable.
// The row is built from config.js's WORD_ACTIONS rather than the hand-written
// markup it used to be, so which tools a reader is offered is configuration:
// a global admin default plus a per-device override, with the paid ones
// filtered out entirely for anyone who is not authorised to spend on them.
function dgeRenderWordToolsRow() {
  const row = document.getElementById('wordToolsRow');
  if (!row || typeof window.dgeGetEffectiveWordActions !== 'function') return;
  row.innerHTML = window.dgeGetEffectiveWordActions().map(function (a) {
    const call = a.arg
      ? "window." + a.handler + "(event, '" + a.arg + "')"
      : "window." + a.handler + "(event)";
    return '<button class="tooltip-btn"' + (a.wordOnly ? ' data-word-only' : '') +
      ' data-action-id="' + a.id + '" onpointerdown="' + call + '" title="' +
      String(a.title || '').replace(/"/g, '&quot;') + '">' + a.icon + ' ' + a.label + '</button>';
  }).join('');
}
window.dgeRenderWordToolsRow = dgeRenderWordToolsRow;
document.addEventListener('DOMContentLoaded', dgeRenderWordToolsRow);

function dgeUpdateWordToolsForSelection(txt) {
  const isSingleWord = !!txt && !/\s/.test(txt.trim());
  dgeRenderWordToolsRow();
  document.querySelectorAll('#wordToolsRow [data-word-only]').forEach(btn => {
    btn.style.display = isSingleWord ? '' : 'none';
  });
  renderAcharyaQueryButtons(isSingleWord);
  // Per-taxonomy-section extra word/phrase actions (e.g. Veda svara tools)
  // from contextual-actions.js's registry — additive only, never
  // duplicates the Shabda/Dhatu/Sandhi/Copy/Ask-Acharya buttons above.
  if (typeof window.dgeRenderWordToolsExtras === 'function') {
    window.dgeRenderWordToolsExtras(isSingleWord, txt || '');
  }
}

// Suppresses the always-visible कोश/global-search FABs (#kosha-fab,
// .dge-gs-fab) for as long as #actionTooltip is open -- confirmed live
// they were sitting visibly behind/around the tooltip (24 Aug live-
// testing screenshots), the same clutter complaint immersive mode
// (body.dge-immersive, main.css) already solves for full-screen reading.
// Also drives the mobile bottom-sheet's slide-up transition (main.css's
// #actionTooltip.dge-tt-show below 760px): the class is added a frame
// after display:flex so the browser registers the sheet's initial
// off-screen transform first, otherwise the transition is skipped
// entirely (a same-frame class add and the display change coalesce into
// one paint). A MutationObserver on the tooltip's own style attribute,
// rather than threading this through every one of the ~7 places in this
// file that already set tooltip.style.display, so none of those existing
// call sites need touching.
(function () {
  const tooltip = document.getElementById('actionTooltip');
  if (!tooltip) return;
  const sync = () => {
    const visible = !!tooltip.style.display && tooltip.style.display !== 'none';
    document.body.classList.toggle('dge-selecting', visible);
    if (visible) {
      requestAnimationFrame(() => tooltip.classList.add('dge-tt-show'));
    } else {
      tooltip.classList.remove('dge-tt-show');
    }
  };
  new MutationObserver(sync).observe(tooltip, { attributes: true, attributeFilter: ['style'] });
  sync();
})();

// Set right before this handler programmatically clears the live selection
// itself (below, to dismiss Android's native selection toolbar) -- that
// removeAllRanges() call fires its OWN selectionchange event, which would
// otherwise re-enter this same handler ~50ms later with an now-empty
// selection and immediately hide the sheet it had just shown. One-shot: the
// very next selectionchange event is swallowed here before it can reach the
// debounce logic below, and every OTHER selectionchange (a reader's own,
// including one made while a highlighted selection is still showing) still
// runs normally.
let dgeIgnoreNextSelectionChange = false;
document.addEventListener('selectionchange', () => {
  if (dgeIgnoreNextSelectionChange) { dgeIgnoreNextSelectionChange = false; return; }
  const activeTag = document.activeElement ? document.activeElement.tagName : '';
  if (['INPUT', 'TEXTAREA'].includes(activeTag)) {
     const tooltip = document.getElementById('actionTooltip');
     const modalBtn = document.getElementById('modalAppendBtn');
     if (tooltip) tooltip.style.display = 'none';
     if (modalBtn) modalBtn.style.display = 'none';
     return;
  }

  clearTimeout(window.selectionTimeout);
  window.selectionTimeout = setTimeout(() => {
    const selection = window.getSelection();
    const txt = (typeof window.dgeRobustSelectedText === 'function' ? window.dgeRobustSelectedText() : selection.toString().trim());
    const tooltip = document.getElementById('actionTooltip');
    const modalAppendBtn = document.getElementById('modalAppendBtn');

    if (!tooltip) return;

    const acharyaResEl = document.getElementById('acharyaResult');
    const isInsideAcharyaModal = acharyaResEl && acharyaResEl.contains(selection.anchorNode);

    const anchor = selection.anchorNode;
    const shlokaCard = anchor && anchor.nodeType === 3 ? anchor.parentElement.closest('.shloka-card') : (anchor && anchor.closest ? anchor.closest('.shloka-card') : null);
    
    if (shlokaCard) {
      window.contextShlokaId = parseInt(shlokaCard.id.split('-')[1]);
    } else if (!isInsideAcharyaModal) {
      window.contextShlokaId = null;
    }

    // A selection inside the app's own UI chrome (a settings popup/sheet, or
    // any other modal's own labels/buttons) isn't reading content the Genie
    // can act on -- confirmed live: drag-selecting a label inside the open
    // Display sheet (e.g. "Tap selects one word") still fell through to the
    // branch below and popped the Ask Acharya tooltip UNDER that same open
    // sheet, both full-width bottom sheets at the identical z-index with no
    // ordering between them, exactly the "popups on top of each other"
    // complaint. #acharyaResult is excluded from this check since it's
    // already handled by its own branch just below (modalAppendBtn).
    const chromeAncestorEl = anchor && (anchor.nodeType === 3 ? anchor.parentElement : anchor);
    const insideUiChrome = !isInsideAcharyaModal && chromeAncestorEl && chromeAncestorEl.closest &&
      chromeAncestorEl.closest('.popup, .modal-content');

    if (insideUiChrome) {
      tooltip.style.display = 'none';
      if (modalAppendBtn) modalAppendBtn.style.display = 'none';
      return;
    }

    if (txt.length > 0) {
      const range = selection.getRangeAt(0);
      const rect = range.getBoundingClientRect();
      if(rect.top === 0 && rect.left === 0) return;

      if (isInsideAcharyaModal && modalAppendBtn) {
        window.modalSelectedText = txt;
        tooltip.style.display = 'none';
        modalAppendBtn.style.display = 'flex';
        modalAppendBtn.style.top = `${Math.min(rect.bottom + 8, window.innerHeight - 50)}px`;
        modalAppendBtn.style.left = `${rect.left + (rect.width / 2)}px`;
      } else {
        window.lastSelectedText = txt;
        if (modalAppendBtn) modalAppendBtn.style.display = 'none';
        tooltip.style.display = 'flex';
        dgeUpdateWordToolsForSelection(txt);

        // The Genie sheet now overlaps live text -- and on Android, a live
        // selection also keeps the OS's own "Translate / Copy / Select all"
        // toolbar floating on screen underneath it (reported live, with
        // screenshots: it stayed visible on top of the sheet, and a reader's
        // FIRST tap on any sheet button was consumed by Android just
        // dismissing its own toolbar instead of reaching the button --
        // "nothing happens the first time, only the second tap works").
        // dgeHideActionTooltip() already cleared the live selection, but
        // only once a button was actually clicked -- by then the native
        // toolbar had already been sitting there the whole time the sheet
        // was open. Clearing it here instead, the moment the sheet first
        // appears, removes the native toolbar immediately; a same-colored
        // .dge-word-picked class on the actual word span(s) stands in for
        // the highlight so the reader still sees what's selected. Only done
        // when the selection lines up with real .dge-word span(s) -- a
        // freeform/Custom-mode drag that doesn't (e.g. spanning into a
        // commentary block) keeps the native selection as before, since
        // there is no word-level element to substitute a highlight onto.
        if (dgeApplyWordSelectionHighlight(range)) {
          dgeIgnoreNextSelectionChange = true;
          try { selection.removeAllRanges(); }
          catch (e) { dgeIgnoreNextSelectionChange = false; }
        }

        // Below 760px (this app's own desktop breakpoint -- see main.css)
        // this is now a real bottom sheet (main.css's own media query does
        // all the positioning: full-width, docked to the bottom edge,
        // slides up on show) rather than a box floated near the
        // selection -- the project lead's direct follow-up report: even
        // after the previous pass gave it real clearance from the
        // selection, it still read as something "fighting" for space with
        // the rest of the page; "pop up from beneath... like how the
        // upper menu appears" was the explicit ask. So on mobile this
        // clears any inline position from a prior desktop-width run
        // (e.g. a resize while the tooltip was open) and leaves
        // positioning entirely to CSS; the slide-up transition itself is
        // driven by the MutationObserver above adding .dge-tt-show.
        // Desktop keeps the original near-selection placement unchanged
        // -- no native auto-popup toolbar to collide with there, and a
        // full-width sheet would look out of place at that size anyway.
        if (window.innerWidth < 760) {
          tooltip.style.top = '';
          tooltip.style.left = '';
          tooltip.style.bottom = '';
        } else {
          const tw = tooltip.offsetWidth || 260;
          tooltip.style.bottom = 'auto';
          let left = rect.left + (rect.width / 2);
          left = Math.max(tw/2 + 8, Math.min(left, window.innerWidth - tw/2 - 8));
          tooltip.style.left = `${left}px`;

          let yPos = rect.bottom + 8;
          if (yPos + 100 > window.innerHeight) {
              yPos = rect.top - 95;
          }
          tooltip.style.top = `${yPos}px`;
        }
      }
    } else {
      tooltip.style.display = 'none';
      if (modalAppendBtn) modalAppendBtn.style.display = 'none';
    }
  }, 50);
});

// 2. Markdown Parser
// Line-based rather than the old chained-regex version, which only handled
// ##/### headers and single-* bullets, left numbered lists as plain text,
// and joined every line with <br> instead of real paragraph spacing — a
// Gemini reply with a numbered list or a top-level # heading rendered as a
// wall of text with literal "1." and "#" characters in it. Shared by every
// AI surface that renders a model reply (Ask Acharya here, and the Kosha
// quick actions in kosha.js), so the fix applies everywhere at once.
function parseMarkdown(md) {
  if (!md) return '';
  function inline(s) {
    return s
      .replace(/\*\*(.*?)\*\*/g, '<strong class="md-strong">$1</strong>')
      .replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, '$1<em>$2</em>');
  }
  var lines = String(md).replace(/\r\n/g, '\n').split('\n');
  var html = '', listTag = null;
  function closeList() { if (listTag) { html += '</' + listTag + '>'; listTag = null; } }
  lines.forEach(function (line) {
    var h = line.match(/^(#{1,3})\s+(.*)$/);
    var ol = line.match(/^\s*\d+[.)]\s+(.*)$/);
    var ul = line.match(/^\s*[*\-]\s+(.*)$/);
    if (h) {
      closeList();
      var cls = h[1].length === 1 ? 'md-h1' : h[1].length === 2 ? 'md-h2' : 'md-h3';
      html += '<div class="' + cls + '">' + inline(h[2]) + '</div>';
    } else if (ol) {
      if (listTag !== 'ol') { closeList(); html += '<ol class="md-list">'; listTag = 'ol'; }
      html += '<li>' + inline(ol[1]) + '</li>';
    } else if (ul) {
      if (listTag !== 'ul') { closeList(); html += '<ul class="md-list">'; listTag = 'ul'; }
      html += '<li>' + inline(ul[1]) + '</li>';
    } else if (!line.trim()) {
      closeList();
    } else {
      closeList();
      html += '<p class="md-p">' + inline(line) + '</p>';
    }
  });
  closeList();
  return html;
}

// 3. Multi-Provider AI Key Settings
function dgeCap(s) { return s.charAt(0).toUpperCase() + s.slice(1); }
const AI_PROVIDER_IDS = ['gemini', 'openai', 'claude'];

window.openKeyModal = function() {
  AI_PROVIDER_IDS.forEach(id => {
    const keyInput = document.getElementById(`user${dgeCap(id)}KeyInput`);
    const modelInput = document.getElementById(`user${dgeCap(id)}ModelInput`);
    if (keyInput) keyInput.value = localStorage.getItem(`user_${id}_key`) || '';
    if (modelInput) modelInput.value = localStorage.getItem(`user_${id}_model`) || (window.AI_PROVIDERS && window.AI_PROVIDERS[id] ? window.AI_PROVIDERS[id].defaultModel : '') || '';
  });
  const parallelToggle = document.getElementById('aiParallelModeToggle');
  if (parallelToggle) parallelToggle.checked = localStorage.getItem('user_ai_parallel_mode') === 'true';

  const audioBaseUrlInput = document.getElementById('userAudioBaseUrlInput');
  if (audioBaseUrlInput) audioBaseUrlInput.value = localStorage.getItem('audio_base_url_override') || '';
  const audioBaseUrlDefaultHint = document.getElementById('audioBaseUrlDefaultHint');
  if (audioBaseUrlDefaultHint) audioBaseUrlDefaultHint.textContent = (window.appConfig && window.appConfig.audioBaseUrl) || 'https://archive.org/download/';

  const searchIndexBaseInput = document.getElementById('userSearchIndexBaseInput');
  if (searchIndexBaseInput) searchIndexBaseInput.value = localStorage.getItem('search_index_base_override') || '';

  dgeRenderAcharyaSettingsUI();
  dgeLoadFeatureFlagsIntoUI();
  dgeLoadShlokaFieldsIntoUI();
  dgeLoadShareTemplateIntoUI();
  dgeRestoreSettingsSectionPins();
  if (typeof openModal === 'function') openModal('keyModal');
};

// Every settings section is collapsed by default. Pinning a section (📌
// in its header) keeps it expanded across future openings; anything
// left unpinned auto-collapses again as soon as Settings is closed, so
// it never silently accumulates as "always open" clutter.
function dgeGetPinnedSettingsSections() {
  try {
    return JSON.parse(localStorage.getItem('pinned_settings_sections') || '[]');
  } catch (e) {
    return [];
  }
}

function dgeRestoreSettingsSectionPins() {
  const pinned = new Set(dgeGetPinnedSettingsSections());
  document.querySelectorAll('#keyModal details[data-section-id]').forEach(details => {
    const id = details.dataset.sectionId;
    const pinBtn = details.querySelector('.settings-pin-btn');
    const isPinned = pinned.has(id);
    if (pinBtn) pinBtn.classList.toggle('pinned', isPinned);
    details.open = isPinned;
  });
}

window.dgeToggleSectionPin = function(btn) {
  const details = btn.closest('details');
  if (!details) return;
  const id = details.dataset.sectionId;
  if (!id) return;
  const pinned = new Set(dgeGetPinnedSettingsSections());
  if (pinned.has(id)) pinned.delete(id); else pinned.add(id);
  localStorage.setItem('pinned_settings_sections', JSON.stringify([...pinned]));
  btn.classList.toggle('pinned');
};

window.closeKeyModal = function() { 
  const pinned = new Set(dgeGetPinnedSettingsSections());
  document.querySelectorAll('#keyModal details[data-section-id]').forEach(details => {
    if (!pinned.has(details.dataset.sectionId)) details.open = false;
  });
  if (typeof closeModal === 'function') closeModal('keyModal'); 
};

window.saveAllApiKeys = function() {
  AI_PROVIDER_IDS.forEach(id => {
    const keyInput = document.getElementById(`user${dgeCap(id)}KeyInput`);
    const modelInput = document.getElementById(`user${dgeCap(id)}ModelInput`);
    const key = keyInput ? keyInput.value.trim() : '';
    const model = modelInput ? modelInput.value.trim() : '';
    if (key) localStorage.setItem(`user_${id}_key`, key); else localStorage.removeItem(`user_${id}_key`);
    if (model) localStorage.setItem(`user_${id}_model`, model); else localStorage.removeItem(`user_${id}_model`);
  });
  const parallelToggle = document.getElementById('aiParallelModeToggle');
  if (parallelToggle) localStorage.setItem('user_ai_parallel_mode', parallelToggle.checked ? 'true' : 'false');

  const audioBaseUrlInput = document.getElementById('userAudioBaseUrlInput');
  if (audioBaseUrlInput) {
    let url = audioBaseUrlInput.value.trim();
    if (url && !url.endsWith('/')) url += '/'; // must end with / — concatenated directly with each grantha's identifier folder
    if (url) { localStorage.setItem('audio_base_url_override', url); audioBaseUrlInput.value = url; }
    else localStorage.removeItem('audio_base_url_override');
  }

  const searchIndexBaseInput = document.getElementById('userSearchIndexBaseInput');
  if (searchIndexBaseInput) {
    // No trailing slash here, unlike the audio override above -- dge-search.js's
    // own fetch helper does `base + '/' + rel`, inserting the separator itself,
    // so a base that already ends in / would produce a double slash.
    let indexUrl = searchIndexBaseInput.value.trim().replace(/\/+$/, '');
    if (indexUrl) { localStorage.setItem('search_index_base_override', indexUrl); searchIndexBaseInput.value = indexUrl; }
    else localStorage.removeItem('search_index_base_override');
  }

  dgeSaveAcharyaSettingsFromUI();
  dgeSaveFeatureFlagsFromUI();
  dgeSaveShlokaFieldsFromUI();
  dgeSaveShareTemplateFromUI();

  window.closeKeyModal();
  if (typeof showToast === 'function') showToast('Settings saved.');
};

// --- Feature Visibility (🎛️) ---------------------------------------

const FEATURE_FLAG_CHECKBOX_IDS = {
  showFavorite: 'flagShowFavorite',
  showStatus: 'flagShowStatus',
  showDoubt: 'flagShowDoubt',
  showNotes: 'flagShowNotes',
  showSnippetTools: 'flagShowSnippetTools',
  showThemePicker: 'flagShowThemePicker',
  showScriptPicker: 'flagShowScriptPicker',
  showPreloadButton: 'flagShowPreloadButton',
  showSpeedControl: 'flagShowSpeedControl',
  showDhatuChips: 'flagShowDhatuChips',
  showWordMarks: 'flagShowWordMarks',
  showReferenceLinks: 'flagShowReferenceLinks',
  showPratikaLinks: 'flagShowPratikaLinks',
  showCommentarySandhi: 'flagShowCommentarySandhi',
  showPadaccheda: 'flagShowPadaccheda'
};

const SCRIPT_OPTION_CHECKBOX_IDS = {
  devanagari: 'scriptOptDevanagari',
  iast: 'scriptOptIast',
  kannada: 'scriptOptKannada',
  telugu: 'scriptOptTelugu',
  tamil: 'scriptOptTamil',
  malayalam: 'scriptOptMalayalam'
};

// Word-tool toggles are built from the registry rather than hand-listed like
// the flags above -- adding a tool to config.js should not also require a
// checkbox here, which is how such lists drift out of sync.
function dgeLoadWordActionsIntoUI() {
  const box = document.getElementById('wordActionToggles');
  if (!box || !window.WORD_ACTIONS) return;
  let global = {}, local = {};
  try { global = (window.appConfig && window.appConfig.wordActions) || {}; } catch (e) {}
  try { local = JSON.parse(localStorage.getItem('word_actions_override') || 'null') || {}; } catch (e) {}
  const aiOk = typeof window.dgeAiFeaturesAllowed === 'function' && window.dgeAiFeaturesAllowed();
  const POWERED_NOTE = { gemini: ' · paid AI', external: ' · third-party service' };
  box.innerHTML = window.WORD_ACTIONS
    .filter(function (a) { return a.powered !== 'gemini' || aiOk; })
    .map(function (a) {
      const on = local[a.id] !== undefined ? local[a.id]
               : global[a.id] !== undefined ? global[a.id] : a.enabled;
      return '<label class="flex-row" style="gap:8px; cursor:pointer; font-size:12px; font-weight:600;">' +
        '<input type="checkbox" data-wordaction="' + a.id + '" style="margin:0; width:14px; height:14px;"' +
        (on ? ' checked' : '') + '> ' + a.icon + ' ' + a.label +
        '<span style="font-weight:400; opacity:.65;">' + (POWERED_NOTE[a.powered] || '') + '</span></label>';
    }).join('');
}

function dgeSaveWordActionsFromUI() {
  const override = {};
  let any = false;
  document.querySelectorAll('#wordActionToggles [data-wordaction]').forEach(function (el) {
    override[el.dataset.wordaction] = el.checked;
    any = true;
  });
  if (!any) return;
  try { localStorage.setItem('word_actions_override', JSON.stringify(override)); } catch (e) {}
  if (typeof window.dgeRenderWordToolsRow === 'function') window.dgeRenderWordToolsRow();
}

function dgeLoadFeatureFlagsIntoUI() {
  const flags = (typeof dgeGetEffectiveFeatureFlags === 'function') ? dgeGetEffectiveFeatureFlags() : (window.FEATURE_FLAGS || {});
  Object.entries(FEATURE_FLAG_CHECKBOX_IDS).forEach(([flagKey, elId]) => {
    const el = document.getElementById(elId);
    if (el) el.checked = flags[flagKey] !== false;
  });

  const masterEl = document.getElementById('flagShowAllMarkers');
  if (masterEl) {
    const markerFlags = ['showFavorite', 'showStatus', 'showDoubt', 'showNotes', 'showSnippetTools'];
    masterEl.checked = markerFlags.every(f => flags[f] !== false);
  }

  dgeLoadWordActionsIntoUI();
  const scriptOptions = (typeof dgeGetEffectiveScriptOptions === 'function') ? dgeGetEffectiveScriptOptions() : (window.SCRIPT_OPTIONS || []);
  scriptOptions.forEach(opt => {
    const elId = SCRIPT_OPTION_CHECKBOX_IDS[opt.id];
    const el = elId ? document.getElementById(elId) : null;
    if (el) el.checked = opt.enabled !== false;
  });
}

window.dgeToggleAllMarkers = function(checked) {
  ['flagShowFavorite', 'flagShowStatus', 'flagShowDoubt', 'flagShowNotes', 'flagShowSnippetTools'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.checked = checked;
  });
};

function dgeSaveFeatureFlagsFromUI() {
  const override = {};
  let any = false;
  Object.entries(FEATURE_FLAG_CHECKBOX_IDS).forEach(([flagKey, elId]) => {
    const el = document.getElementById(elId);
    if (el) { override[flagKey] = el.checked; any = true; }
  });
  if (any) localStorage.setItem('feature_flags_override', JSON.stringify(override));
  dgeSaveWordActionsFromUI();

  const scriptOverride = {};
  let anyScript = false;
  Object.entries(SCRIPT_OPTION_CHECKBOX_IDS).forEach(([scriptId, elId]) => {
    const el = document.getElementById(elId);
    if (el) { scriptOverride[scriptId] = el.checked; anyScript = true; }
  });
  if (anyScript) localStorage.setItem('script_options_override', JSON.stringify(scriptOverride));

  if (typeof applyFeatureFlags === 'function') applyFeatureFlags();
}

window.resetAudioBaseUrlToDefault = function() {
  localStorage.removeItem('audio_base_url_override');
  const input = document.getElementById('userAudioBaseUrlInput');
  if (input) input.value = '';
  if (typeof showToast === 'function') showToast('Audio source reset to the project default.');
};

window.resetSearchIndexBaseToDefault = function() {
  localStorage.removeItem('search_index_base_override');
  const input = document.getElementById('userSearchIndexBaseInput');
  if (input) input.value = '';
  if (typeof showToast === 'function') showToast('Search index source reset to the project default — reload the page for it to take effect.');
};

window.resetFeatureFlagsToDefault = function() {
  localStorage.removeItem('feature_flags_override');
  localStorage.removeItem('script_options_override');
  dgeLoadFeatureFlagsIntoUI();
  if (typeof applyFeatureFlags === 'function') applyFeatureFlags();
  if (typeof showToast === 'function') showToast('Feature visibility reset to defaults.');
};

// --- Shloka Fields (🧩) — Padaccheda, Anvaya, Vrutta, etc. -------------

const SHLOKA_FIELD_CHECKBOX_IDS = {
  padaccheda: 'fieldPadaccheda',
  anvaya: 'fieldAnvaya',
  pratipadartha: 'fieldPratipadartha',
  tatparya: 'fieldTatparya',
  vyakarana: 'fieldVyakarana',
  vrutta: 'fieldVrutta',
  alankara: 'fieldAlankara',
  samasa: 'fieldSamasa',
  crossReferences: 'fieldCrossReferences'
};

function dgeLoadShlokaFieldsIntoUI() {
  const fields = (typeof dgeGetEffectiveShlokaFields === 'function') ? dgeGetEffectiveShlokaFields() : (window.SHLOKA_EXTRA_FIELDS || []);
  fields.forEach(f => {
    const elId = SHLOKA_FIELD_CHECKBOX_IDS[f.id];
    const el = elId ? document.getElementById(elId) : null;
    if (el) el.checked = f.enabled !== false;
  });
}

function dgeSaveShlokaFieldsFromUI() {
  const override = {};
  let any = false;
  Object.entries(SHLOKA_FIELD_CHECKBOX_IDS).forEach(([fieldId, elId]) => {
    const el = document.getElementById(elId);
    if (el) { override[fieldId] = el.checked; any = true; }
  });
  if (any) localStorage.setItem('shloka_extra_fields_override', JSON.stringify(override));
  if (typeof renderList === 'function') renderList();
}

window.resetShlokaFieldsToDefault = function() {
  localStorage.removeItem('shloka_extra_fields_override');
  dgeLoadShlokaFieldsIntoUI();
  if (typeof renderList === 'function') renderList();
  if (typeof showToast === 'function') showToast('Shloka field visibility reset to defaults.');
};

// --- Share Image Template (🖼️) ------------------------------------

window.selectShareTemplate = function(id) {
  localStorage.setItem('default_share_template', id);
  document.querySelectorAll('#defaultShareTemplateGrid .share-tpl-thumb').forEach(el => {
    el.classList.toggle('selected', el.dataset.tplId === id);
  });
};

async function dgeLoadShareTemplateIntoUI() {
  const grid = document.getElementById('defaultShareTemplateGrid');
  if (!grid) return;
  grid.innerHTML = `<div style="grid-column: 1 / -1; font-size:11px; color:var(--muted-text); padding:8px 0;">Loading templates…</div>`;

  const templates = (typeof dgeDiscoverShareTemplates === 'function') ? await dgeDiscoverShareTemplates() : [];
  const current = localStorage.getItem('default_share_template') || 'plain';

  grid.innerHTML = templates.map(t => {
    const thumb = t.filename
      ? `<img src="images/${t.filename}" alt="" style="width:100%; height:100%; object-fit:cover;">`
      : `<div style="width:100%; height:100%; display:flex; align-items:center; justify-content:center; background:var(--card-bg); color:var(--muted-text); font-size:10px;">Plain</div>`;
    return `
      <button type="button" class="share-tpl-thumb${t.id === current ? ' selected' : ''}" data-tpl-id="${t.id}" onclick="window.selectShareTemplate('${t.id}')">
        <div class="share-tpl-thumb-img">${thumb}</div>
        <div class="share-tpl-thumb-label">${t.label}</div>
      </button>`;
  }).join('') + `<button type="button" class="btn-sm" style="grid-column: 1 / -1;" onclick="window.refreshShareTemplates()">↻ Refresh (check for new uploads)</button>`;
}

window.refreshShareTemplates = async function() {
  if (typeof dgeDiscoverShareTemplates === 'function') await dgeDiscoverShareTemplates(true);
  dgeLoadShareTemplateIntoUI();
  if (typeof showToast === 'function') showToast('Template list refreshed.');
};

function dgeSaveShareTemplateFromUI() {
  // selection is already saved live by selectShareTemplate() on tap —
  // nothing further needed here, kept only so the shared Save flow can
  // still call it without checking whether it exists.
}

// Resolves the ACHARYA_QUERY_TYPES list with any per-device overrides (from
// the ⚙️ Ask Acharya Settings section below) layered on top of the shipped
// defaults in config.js.
function dgeGetEffectiveQueryTypes() {
  const defaults = window.ACHARYA_QUERY_TYPES || [];
  let override = null;
  try { override = JSON.parse(localStorage.getItem('acharya_query_config') || 'null'); } catch (e) { /* ignore */ }

  return defaults.map(def => {
    const o = (override && Array.isArray(override)) ? override.find(x => x.id === def.id) : null;
    const presetOverrides = (o && o.presetOverrides) || {};
    const presets = (def.presets || []).map(p => ({
      ...p,
      enabled: presetOverrides[p.id] !== undefined ? presetOverrides[p.id] : p.default
    }));
    return {
      ...def,
      presets,
      customNotes: (o && o.customNotes !== undefined) ? o.customNotes : def.customNotes,
      depth: (o && o.depth) || def.depth
    };
  });
}
window.dgeGetEffectiveQueryTypes = dgeGetEffectiveQueryTypes;

// Builds the actual numbered "provide:" list sent to Acharya for a given
// (effective, override-aware) type config — enabled presets first (fixed
// wording, can't be typo'd), then the free-text custom notes appended
// last if present.
function dgeBuildFieldsForType(typeConfig) {
  const out = (typeConfig.presets || []).filter(p => p.enabled !== false).map(p => p.label);
  if (typeConfig.customNotes && typeConfig.customNotes.trim()) {
    out.push(typeConfig.customNotes.trim());
  }
  return out;
}
window.dgeBuildFieldsForType = dgeBuildFieldsForType;

// Renders the entire "⚙️ Ask Acharya Settings" body from config — a
// checkbox per preset (fixed label, can't be mistyped) plus one free-text
// "additional instructions" box per type. Bhashya also gets its depth
// selector above its checkboxes.
function dgeRenderAcharyaSettingsUI() {
  const container = document.getElementById('acharyaSettingsContainer');
  if (!container) return;
  const types = dgeGetEffectiveQueryTypes();

  let html = '';
  types.forEach(t => {
    html += `<div class="provider-key-row">`;
    html += `<label>${t.icon} ${t.label} — fields to include</label>`;

    if (t.id === 'bhashya') {
      html += `<div style="margin:8px 0;">`;
      html += `<div style="font-size:11px; font-weight:700; color:var(--muted-text); margin-bottom:4px;">Analysis depth</div>`;
      html += `<select class="modal-input" data-acharya-depth="${t.id}" style="margin:0;">`;
      ['summary', 'sentence', 'word'].forEach(d => {
        const dLabel = d === 'summary' ? 'Summary' : d === 'sentence' ? 'Sentence-by-sentence' : 'Word-by-word';
        html += `<option value="${d}" ${t.depth === d ? 'selected' : ''}>${dLabel}</option>`;
      });
      html += `</select></div>`;
    }

    (t.presets || []).forEach(p => {
      html += `<label class="flex-row" style="gap:8px; cursor:pointer; font-size:12px; font-weight:500; margin:6px 0; align-items:flex-start;">
        <input type="checkbox" data-acharya-preset="${t.id}::${p.id}" ${p.enabled !== false ? 'checked' : ''} style="margin:2px 0 0 0; width:14px; height:14px; flex-shrink:0;">
        <span>${p.label}</span>
      </label>`;
    });

    html += `<div style="font-size:11px; font-weight:700; color:var(--muted-text); margin-top:8px;">Additional instructions${t.id === 'translate' ? ' (this IS the whole instruction for Custom)' : ' (optional, free text)'}</div>`;
    html += `<textarea class="modal-input" data-acharya-notes="${t.id}" style="height:70px; margin-top:4px; font-size:12px;">${(t.customNotes || '').replace(/</g, '&lt;')}</textarea>`;
    html += `</div>`;
  });

  container.innerHTML = html;
}

window.resetAcharyaFieldsToDefault = function() {
  localStorage.removeItem('acharya_query_config');
  dgeRenderAcharyaSettingsUI();
  if (typeof showToast === 'function') showToast('Ask Acharya settings reset to defaults.');
};

function dgeSaveAcharyaSettingsFromUI() {
  const container = document.getElementById('acharyaSettingsContainer');
  if (!container) return;

  const types = window.ACHARYA_QUERY_TYPES || [];
  const override = types.map(t => {
    const presetOverrides = {};
    container.querySelectorAll(`input[data-acharya-preset^="${t.id}::"]`).forEach(cb => {
      const presetId = cb.dataset.acharyaPreset.split('::')[1];
      presetOverrides[presetId] = cb.checked;
    });
    const notesEl = container.querySelector(`textarea[data-acharya-notes="${t.id}"]`);
    const depthEl = container.querySelector(`select[data-acharya-depth="${t.id}"]`);
    return {
      id: t.id,
      presetOverrides,
      customNotes: notesEl ? notesEl.value : undefined,
      depth: depthEl ? depthEl.value : undefined
    };
  });

  localStorage.setItem('acharya_query_config', JSON.stringify(override));
  renderAcharyaQueryButtons();
}

function dgeGetConfiguredProviders() {
  const out = [];
  AI_PROVIDER_IDS.forEach(id => {
    const key = localStorage.getItem(`user_${id}_key`);
    if (key) {
      const model = localStorage.getItem(`user_${id}_model`) || (window.AI_PROVIDERS && window.AI_PROVIDERS[id] ? window.AI_PROVIDERS[id].defaultModel : '') || '';
      out.push({ id, key, model });
    }
  });
  return out;
}

// --- Provider call adapters ---------------------------------------------
// Note: Gemini and OpenAI's chat/completions endpoints support direct
// browser calls out of the box. Anthropic's API requires the
// 'anthropic-dangerous-direct-browser-access' header to allow CORS from a
// browser context (a deliberate, documented opt-in on their side for
// "bring your own key" apps like this one) — without it, requests are
// rejected with a CORS/auth error.

// Delegates network + error classification to the shared window.DGEGemini
// client (js/gemini.js) so a quota/permission/network failure reads as
// plain English with an actual next step instead of a raw API message, and
// gets one automatic retry on a lighter model first. The function's own
// contract (resolve to the answer text, throw Error on failure) is kept
// unchanged so dgeCallProvider()'s uniform dispatch across Gemini/OpenAI/
// Claude -- and the Promise.allSettled multi-provider flow above it --
// don't need to change.
async function dgeCallGemini(apiKey, model, systemPrompt, history) {
  const modelName = model || (typeof appConfig !== 'undefined' && appConfig.geminiModel) || 'gemini-3.6-flash';
  const contents = history.map(m => ({ role: m.role === 'assistant' ? 'model' : 'user', parts: [{ text: m.content }] }));
  const r = await window.DGEGemini.generate({ contents, system: systemPrompt, apiKey, model: modelName });
  if (!r.ok) throw new Error(r.error.title + ' — ' + r.error.message + ' ' + r.error.action);
  return r.fellBack ? `[${r.notice}]\n\n${r.text}` : r.text;
}

async function dgeCallOpenAI(apiKey, model, systemPrompt, history) {
  if (!model) throw new Error('No OpenAI model set — add one in ⚙️ Settings (e.g. a current GPT model name from your OpenAI account).');
  const messages = [{ role: 'system', content: systemPrompt }, ...history.map(m => ({ role: m.role, content: m.content }))];
  const res = await fetch('https://api.openai.com/v1/chat/completions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${apiKey}` },
    body: JSON.stringify({ model, messages })
  });
  const data = await res.json();
  if (data.error) throw new Error(data.error.message || 'OpenAI request failed');
  return data.choices[0].message.content;
}

async function dgeCallClaude(apiKey, model, systemPrompt, history) {
  if (!model) throw new Error('No Claude model set — add one in ⚙️ Settings (e.g. a current Claude model name from your Anthropic console).');
  const messages = history.map(m => ({ role: m.role, content: m.content }));
  const res = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': apiKey,
      'anthropic-version': '2023-06-01',
      'anthropic-dangerous-direct-browser-access': 'true'
    },
    body: JSON.stringify({ model, max_tokens: 1500, system: systemPrompt, messages })
  });
  const data = await res.json();
  if (data.error) throw new Error(data.error.message || 'Claude request failed');
  return (data.content || []).map(b => b.text || '').join('');
}

async function dgeCallProvider(p, systemPrompt, history) {
  if (p.id === 'gemini') return dgeCallGemini(p.key, p.model, systemPrompt, history);
  if (p.id === 'openai') return dgeCallOpenAI(p.key, p.model, systemPrompt, history);
  if (p.id === 'claude') return dgeCallClaude(p.key, p.model, systemPrompt, history);
  throw new Error('Unknown provider: ' + p.id);
}

// 4. Bhashya Picker Workflow
window.openBhashyaPicker = function(e) {
  if (e) e.preventDefault();
  const tooltip = document.getElementById('actionTooltip');
  if (tooltip) tooltip.style.display = 'none';
  
  window.getSelection().removeAllRanges();

  const targetId = window.contextShlokaId || window.activeId || 1;
  window.currentAcharyaShlokaId = targetId;

  const shloka = window.stotraData ? window.stotraData.shlokas[targetId] : null;
  const container = document.getElementById('bhashyaOptionsContainer');
  if (!container) return;
  container.innerHTML = '';

  if (shloka && shloka.commentaries && window.stotraData.metadata.availableCommentaries) {
    Object.entries(shloka.commentaries).forEach(([cKey, cText]) => {
      const name = window.stotraData.metadata.availableCommentaries[cKey] || cKey;
      const displayName = typeof applyTransliteration === 'function' ? applyTransliteration(name, window.activeScript || 'devanagari') : name;
      container.innerHTML += `
        <button class="bhashya-picker-btn" onpointerdown="window.executeBhashyaAnalysis('${cKey}')">
           <span>📖 ${displayName}</span>
           <span style="font-size:11px; opacity:0.6;">Analyze ➔</span>
        </button>`;
    });

    container.innerHTML += `
      <button class="bhashya-picker-btn" style="border-color: var(--accent-gold);" onpointerdown="window.executeBhashyaAnalysis('all')">
         <span>📚 All Available Commentaries Combined</span>
         <span style="font-size:11px; opacity:0.6;">Analyze ➔</span>
      </button>`;
  }

  container.innerHTML += `
    <button class="bhashya-picker-btn" style="background:transparent; border-style:dashed;" onpointerdown="window.executeBhashyaAnalysis('general')">
       <span>📖 Commentary-Style Analysis (No specific source)</span>
       <span style="font-size:11px; opacity:0.6;">Analyze ➔</span>
    </button>`;

  if (typeof openModal === 'function') openModal('bhashyaPickerModal');
};

window.closeBhashyaPicker = function() {
  if (typeof closeModal === 'function') closeModal('bhashyaPickerModal');
};

window.executeBhashyaAnalysis = function(cKey) {
  window.closeBhashyaPicker();
  const targetId = window.currentAcharyaShlokaId || window.contextShlokaId || window.activeId || 1;
  const shloka = window.stotraData ? window.stotraData.shlokas[targetId] : null;

  let commentaryTextToFeed = "";
  let commTitle = "";

  if (cKey === 'all' && shloka && shloka.commentaries) {
    commTitle = "All Available Commentaries";
    Object.entries(shloka.commentaries).forEach(([k, v]) => {
       const name = window.stotraData.metadata.availableCommentaries[k] || k;
       commentaryTextToFeed += `\n--- Commentary: ${name} ---\n${v}\n`;
    });
  } else if (cKey !== 'general' && shloka && shloka.commentaries && shloka.commentaries[cKey]) {
    commTitle = window.stotraData.metadata.availableCommentaries[cKey] || cKey;
    commentaryTextToFeed = shloka.commentaries[cKey];
  }

  const payload = {
    type: 'commentary',
    selectedText: window.lastSelectedText,
    shlokaText: shloka ? shloka.sa : "",
    commentaryTitle: commTitle,
    commentaryText: commentaryTextToFeed
  };

  window.askAcharya(null, 'commentary', payload);
};

// 5. Core Ask Acharya Engine (Madhva Sampradaya Context)
function dgeShowFollowUpBox(visible) {
  const box = document.getElementById('acharyaFollowUpBox');
  if (box) box.style.display = visible ? 'flex' : 'none';
}

async function dgeRunAcharyaQuery(promptText) {
  const resultEl = document.getElementById('acharyaResult');
  const loadingEl = document.getElementById('acharyaLoading');
  const providers = dgeGetConfiguredProviders();

  if (providers.length === 0) {
    if (loadingEl) loadingEl.style.display = 'none';
    if (resultEl) resultEl.innerHTML = `<span style="color:var(--accent-red); font-weight:bold;">आचार्यः ध्याने मग्नः अस्ति (Acharya is meditating).</span><br><br>Please add at least one AI key via the Settings (⚙️) in the top toolbar.`;
    dgeShowFollowUpBox(false);
    return;
  }

  window.acharyaHistory = window.acharyaHistory || [];
  window.acharyaHistory.push({ role: 'user', content: promptText });

  if (loadingEl) loadingEl.style.display = 'block';
  dgeShowFollowUpBox(false);

  const parallelMode = localStorage.getItem('user_ai_parallel_mode') === 'true';
  const activeProviders = parallelMode ? providers : providers.slice(0, 1);

  const settled = await Promise.allSettled(
    activeProviders.map(p => dgeCallProvider(p, window.acharyaSystemPrompt || '', window.acharyaHistory))
  );

  const succeeded = [];
  settled.forEach((r, i) => {
    if (r.status === 'fulfilled') succeeded.push({ provider: activeProviders[i], text: r.value });
    else console.error(`${activeProviders[i].id} failed:`, r.reason);
  });

  if (loadingEl) loadingEl.style.display = 'none';

  if (succeeded.length === 0) {
    window.acharyaHistory.pop();
    if (resultEl) {
      const isAuth = document.body.classList.contains('is-authorized');
      resultEl.innerHTML = isAuth
        ? `<span style="color:var(--accent-red); font-weight:bold;">All configured providers failed.</span> Check the API key(s) and model name(s) in ⚙️ Settings, and the browser console for details.`
        : `<span style="color:var(--accent-red); font-weight:bold;">आचार्यः ध्याने मग्नः अस्ति (Acharya is meditating).</span><br><br>The traditional text analysis engine is currently unavailable. Please try again later.`;
    }
    dgeShowFollowUpBox(true);
    return;
  }

  let finalReplyForHistory;
  let html = '';

  if (succeeded.length === 1) {
    finalReplyForHistory = succeeded[0].text;
    html = parseMarkdown(finalReplyForHistory);
  } else {
    succeeded.forEach(s => {
      const label = (window.AI_PROVIDERS && window.AI_PROVIDERS[s.provider.id]) ? window.AI_PROVIDERS[s.provider.id].label : s.provider.id;
      html += `<div class="provider-answer"><div class="provider-answer-label">${label}</div>${parseMarkdown(s.text)}</div>`;
    });

    try {
      const summaryPrompt = `Here are ${succeeded.length} independent AI responses to the same question: "${promptText}"\n\n` +
        succeeded.map((s, i) => `Response ${i + 1} (${s.provider.id}):\n${s.text}`).join('\n\n---\n\n') +
        `\n\nSynthesize these into ONE combined answer, noting any point where they meaningfully disagree. Format using clean markdown.`;
      finalReplyForHistory = await dgeCallProvider(succeeded[0].provider, window.acharyaSystemPrompt || '', [{ role: 'user', content: summaryPrompt }]);
      html = `<div class="provider-summary"><div class="provider-answer-label">🧭 Combined Summary</div>${parseMarkdown(finalReplyForHistory)}</div>` + html;
    } catch (e) {
      console.error('Summary generation failed', e);
      finalReplyForHistory = succeeded[0].text;
    }
  }

  window.acharyaHistory.push({ role: 'assistant', content: finalReplyForHistory });
  if (resultEl) resultEl.innerHTML = html;
  dgeShowFollowUpBox(true);
}

// Per-card entry point — lets Ask Acharya be triggered directly from a
// shloka's card/actions-sheet without first selecting any text. "Shloka"
// and "Native Meaning" fall back to the full verse text automatically
// (see askAcharya above); "Word" isn't offered here since it needs an
// actual word selection to mean anything.
window.askAcharyaForShloka = function(id, type) {
  window.contextShlokaId = id;
  window.lastSelectedText = '';
  window.askAcharya(null, type);
};

window.openBhashyaPickerForShloka = function(id) {
  window.contextShlokaId = id;
  window.openBhashyaPicker(null);
};

window.askAcharya = async function(e, type, payload) {
  if (e) e.preventDefault();
  const tooltip = document.getElementById('actionTooltip');
  if (tooltip) tooltip.style.display = 'none';

  window.currentAcharyaShlokaId = window.contextShlokaId || window.activeId;

  // Sandhi/Samasa have no Vidyut-precomputed data behind them (unlike
  // Shabda/Dhātu) -- this is a plain LLM call, so say so up front rather
  // than let it look like the same kind of structured lookup. Set before
  // the no-providers check below so it still shows on the "configure a
  // key" message, which is exactly where a Sandhi/Samasa visitor most
  // needs the explanation of why a key is required at all.
  const aiOnlyNote = document.getElementById('acharyaAiOnlyNote');
  if (aiOnlyNote) aiOnlyNote.style.display = (type === 'sandhi' || type === 'samasa') ? 'block' : 'none';

  const providers = dgeGetConfiguredProviders();
  if (providers.length === 0) {
    if (document.body.classList.contains('is-authorized')) { window.openKeyModal(); return; }
    if (typeof openModal === 'function') openModal('acharyaModal');
    const loading = document.getElementById('acharyaLoading');
    const result = document.getElementById('acharyaResult');
    if (loading) loading.style.display = 'none';
    if (result) result.innerHTML = `<span style="color:var(--accent-red); font-weight:bold;">आचार्यः ध्याने मग्नः अस्ति (Acharya is meditating).</span><br><br>Please configure at least one AI key via the Settings (⚙️) in the top toolbar.`;
    dgeShowFollowUpBox(false);
    return;
  }

  const text0 = payload ? payload.selectedText : (window.lastSelectedText || window.getSelection().toString().trim());
  let text = text0;

  // "Shloka" always means the WHOLE verse — a selection (or none at all)
  // only tells us WHICH shloka, not how much of it to analyze. Selecting
  // a single word and tapping Shloka still gets the full-verse analysis.
  if (type === 'shloka' && window.currentAcharyaShlokaId && typeof getText === 'function') {
    text = getText(window.currentAcharyaShlokaId).replace(/<[^>]*>/g, '');
  }

  // "Word", "Sandhi" and "Samasa" genuinely need a specific selection —
  // can't run without one.
  if ((type === 'grammar' || type === 'sandhi' || type === 'samasa') && !text) {
    if (typeof closeModal === 'function') closeModal('acharyaModal');
    if (typeof showToast === 'function') showToast('Select a specific word first to ask for word-level analysis.');
    return;
  }

  // "Native Meaning" works with or without a selection — falls back to
  // the whole shloka if nothing specific was highlighted.
  if (type === 'translate' && !text && window.currentAcharyaShlokaId && typeof getText === 'function') {
    text = getText(window.currentAcharyaShlokaId).replace(/<[^>]*>/g, '');
  }

  if(!text && type !== 'commentary') return;
  window.getSelection().removeAllRanges();

  if (typeof openModal === 'function') openModal('acharyaModal');
  const resultEl = document.getElementById('acharyaResult');
  if (resultEl) resultEl.innerHTML = '';

  let targetLang = "English";
  if(window.activeScript === 'kannada') targetLang = "Kannada";
  if(window.activeScript === 'telugu') targetLang = "Telugu";
  if(window.activeScript === 'tamil') targetLang = "Tamil";
  if(window.activeScript === 'malayalam') targetLang = "Malayalam";

  const effectiveTypes = dgeGetEffectiveQueryTypes();
  const typeConfig = effectiveTypes.find(q => q.id === type);

  const externalLinksNote = window.AI_ALLOW_EXTERNAL_LINKS
    ? ' If you are confident a specific external resource exists for this (e.g. a well-known Sanskrit text repository), you may include one plain hyperlink.'
    : ' Do not include any hyperlinks or URLs.';

  let promptText = "";
  if (type === 'shloka' || type === 'grammar') {
      const fieldsList = dgeBuildFieldsForType(typeConfig || {});
      const persona = type === 'shloka'
        ? "You are a traditional scholar of the Madhva Sampradaya (Dvaita Vedanta)."
        : "You are a traditional Vyakarana Acharya.";
      const fieldsPrompt = (fieldsList.length ? fieldsList : ['Word Meaning']).map((f, i) => `${i + 1}. ${f}`).join('\n');
      promptText = `${persona} For the text: "${text}", provide:\n${fieldsPrompt}\nFormat using clean markdown headings.${externalLinksNote}`;
  } else if (type === 'commentary') {
      const depth = (typeConfig && typeConfig.depth) || 'summary';
      const depthInstruction = {
        summary: 'Provide a concise overall summary of the philosophical Siddhanta.',
        sentence: 'Provide a sentence-by-sentence breakdown and explanation.',
        word: 'Provide a detailed word-by-word meaning and analysis.'
      }[depth] || 'Provide a concise overall summary of the philosophical Siddhanta.';

      const extraFields = dgeBuildFieldsForType(typeConfig || {});
      const extraFieldsPrompt = extraFields.length ? extraFields.map((f, i) => `${i + 4}. ${f}`).join('\n') + '\n' : '';

      if (payload && payload.commentaryText) {
          promptText = `You are a traditional scholar of the Madhva Sampradaya (Dvaita Vedanta). Analyze ONLY the supplied commentary text provided below. Do NOT hallucinate external commentaries.

Mula Shloka: "${payload.shlokaText}"
Commentary Name: "${payload.commentaryTitle}"
Commentary Text: "${payload.commentaryText}"
Highlighted Fragment: "${payload.selectedText}"

Provide a detailed scholarly breakdown in clean markdown:
1. ${depthInstruction}
2. Pramana & Citation Expansion: Identify every scriptural quote (Shruti, Smriti, Gita, Amarakosha, etc.) cited in this text. Provide the FULL Sanskrit quote, source attribution, and precise meaning.
3. Philosophical Siddhanta strictly according to Sri Madhvacharya's Dvaita philosophy derived from this commentary.
${extraFieldsPrompt}${externalLinksNote}`;
      } else {
          promptText = `You are a traditional scholar of the Madhva Sampradaya (Dvaita Vedanta). Analyze this commentary excerpt: "${text}". ${depthInstruction} Also provide Purvapaksha & Siddhanta (strictly according to Sri Madhvacharya), and Pramana/Citations expanded with full quotes.
${extraFieldsPrompt}Format using clean markdown.${externalLinksNote}`;
      }
  } else if (type === 'translate') {
      const fieldsList = dgeBuildFieldsForType(typeConfig || {});
      const fieldsPrompt = (fieldsList.length ? fieldsList : ['A natural translation']).map((f, i) => `${i + 1}. ${f}`).join('\n');
      promptText = `For this Sanskrit text: "${text}" (target language: ${targetLang} where relevant), provide:\n${fieldsPrompt}\nFormat cleanly using markdown.${externalLinksNote}`;
  } else if (type === 'sandhi' || type === 'samasa') {
      // Dedicated word-tool buttons (wordToolsRow), not one of the
      // configurable Ask Acharya categories -- fixed instruction, no
      // preset/customNotes layering. Vidyut has no precomputed sandhi or
      // samasa data (see intellisense.js's own note that it "resolves
      // inflected forms, not sandhi-joined ones"), so this is the LLM's
      // own analysis; askAcharya() above shows acharyaAiOnlyNote to say so.
      const instruction = type === 'sandhi'
        ? 'Provide its Sandhi-vichcheda (sandhi split) into the original constituent words, naming the sandhi rule(s) involved and citing the Ashtadhyayi sutra number if you can identify one confidently. If no sandhi applies here, say so plainly.'
        : 'Determine whether this is a Samasa (compound). If so, provide the Samasa-Vigraha: the Vigrahavakya (expanded phrase), the Samasta-pada, and the type of samasa (Tatpurusha, Dvandva, Bahuvrihi, Karmadharaya, Avyayibhava, Dvigu, etc). If it is not a compound, say so plainly.';
      promptText = `You are a traditional Vyakarana Acharya. For this Sanskrit word: "${text}", ${instruction} Format using clean markdown.${externalLinksNote}`;
  }

  // Fresh top-level question — start a new conversation thread. Also
  // clear any leftover follow-up text from a PREVIOUS analysis, which was
  // otherwise staying populated when switching to a different button.
  window.acharyaHistory = [];
  const staleFollowUpInput = document.getElementById('acharyaFollowUpInput');
  if (staleFollowUpInput) staleFollowUpInput.value = '';
  window.acharyaSystemPrompt = "You are Acharya, embedded in a Vedic text reading app. If the user asks a follow-up question, continue this conversation naturally and stay consistent with your earlier answers, in the philosophical tradition of Sri Madhvacharya (Dvaita Vedanta) unless asked otherwise. IMPORTANT FORMATTING RULE: never use LaTeX or math notation of any kind (no $...$, \\sqrt{}, \\text{}, \\rightarrow, or similar). This app only renders plain text and basic markdown (headings, bold, italic, lists) — LaTeX shows up as broken literal text. Write all derivations in plain prose instead: e.g. write 'root labh (bhvādi-gaṇa, 1st class)' instead of '$\\sqrt{\\text{labh}}$', and 'X + Y becomes Z' instead of an arrow/equation." + dgeLangInstruction();

  await dgeRunAcharyaQuery(promptText);
};

// Nested Ask Acharya: selecting text INSIDE Acharya's own analysis offers
// this alongside "Add to Notes". Rather than reusing the Shloka/Word/
// Bhashya buttons (which are built around the ORIGINAL verse, not
// Acharya's own explanatory prose), this pre-fills the existing follow-up
// box with the selection — the follow-up mechanism already carries the
// full conversation history, so the AI has real context for what's being
// asked about. Pre-filling (not auto-sending) lets the user edit the
// question before it goes out.
window.askFurtherAboutSelection = function(e) {
  if (e) e.preventDefault();
  const modalBtn = document.getElementById('modalAppendBtn');
  if (modalBtn) modalBtn.style.display = 'none';
  if (window.getSelection) window.getSelection().removeAllRanges();

  const selectedText = window.modalSelectedText;
  if (!selectedText) return;

  const input = document.getElementById('acharyaFollowUpInput');
  if (input) {
    input.value = `Please go deeper on this part: "${selectedText}"`;
    input.focus();
  }
  if (typeof showToast === 'function') showToast('Edit the question if needed, then tap Ask.');
};

window.sendAcharyaFollowUp = async function() {
  const input = document.getElementById('acharyaFollowUpInput');
  if (!input) return;
  const q = input.value.trim();
  if (!q) return;
  input.value = '';
  await dgeRunAcharyaQuery(q);
};

// Follow-up mic input (independent tiny SpeechRecognition instance so it
// doesn't collide with the search box's listener in voice.js).
let dgeFollowUpRecognition = null;
window.startFollowUpVoiceInput = function() {
  const Ctor = window.SpeechRecognition || window.webkitSpeechRecognition;
  const input = document.getElementById('acharyaFollowUpInput');
  if (!Ctor || !input) return;

  dgeFollowUpRecognition = new Ctor();
  // Always English — see the identical fix and its reasoning in voice.js's
  // startSearchVoiceInput.
  dgeFollowUpRecognition.lang = 'en-IN';
  dgeFollowUpRecognition.interimResults = true;
  dgeFollowUpRecognition.onresult = (event) => {
    let transcript = '';
    for (let i = 0; i < event.results.length; i++) transcript += event.results[i][0].transcript;
    input.value = transcript;
  };
  dgeFollowUpRecognition.onerror = () => {};
  try { dgeFollowUpRecognition.start(); } catch (e) { /* ignore */ }
};

// Saves the CURRENT full Acharya answer to this shloka's notes in one tap.
// notes.js's appendSelectedTextToNote (the modal's floating "➕ Notes"
// button) already covers a hand-picked excerpt, but only once text inside
// the modal is actually selected -- there was no way to keep the whole
// answer without selecting and copying it by hand first. Reuses
// addNoteEntry() exactly as every other note-adding path does (it calls
// dgeSaveNotes()/renderList() itself), just with 'Ask Acharya' as the
// source so these entries read distinctly from a manual note or an
// excerpt in the shloka's Notes list.
window.saveAcharyaAnalysisToNotes = function() {
  const resEl = document.getElementById('acharyaResult');
  const text = resEl ? resEl.innerText.trim() : '';
  if (!text) { if (typeof showToast === 'function') showToast('Nothing to save yet.'); return; }

  const targetId = window.currentAcharyaShlokaId || window.contextShlokaId || window.activeId;
  if (!targetId) { if (typeof showToast === 'function') showToast('Please tap on a Shloka card first.'); return; }

  if (typeof addNoteEntry === 'function') addNoteEntry(targetId, text, 'Ask Acharya');
  if (typeof showToast === 'function') showToast(`Saved to Shloka ${targetId} notes!`);
};

window.shareAcharyaAnalysis = function() {
  const resEl = document.getElementById('acharyaResult');
  const resText = resEl ? resEl.innerText : '';
  if (!resText) return;
  if (navigator.share) {
    navigator.share({ title: `Acharya Analysis (Shloka ${window.currentAcharyaShlokaId || window.activeId || ''})`, text: resText }).catch(()=>{});
  } else {
    navigator.clipboard.writeText(resText);
    if (typeof showToast === 'function') showToast("Analysis copied to clipboard!");
  }
};

window.closeAcharyaModal = function() { 
  if (typeof closeModal === 'function') closeModal('acharyaModal');
  const appendBtn = document.getElementById('modalAppendBtn');
  if (appendBtn) appendBtn.style.display = 'none';
  window.getSelection().removeAllRanges();
  dgeShowFollowUpBox(false);
  window.acharyaHistory = [];
  const followUpInput = document.getElementById('acharyaFollowUpInput');
  if (followUpInput) followUpInput.value = '';
};

// 6. Render the (globally configurable) Ask Acharya query-type buttons.
// isSingleWord reuses dgeUpdateWordToolsForSelection()'s own word-vs-phrase
// classification (the same check #wordToolsRow's Shabda/Dhatu/Sandhi/Samasa
// buttons already hide by) to also hide "⚙️ Word" when the live selection
// is a multi-word phrase, since that button's grammar analysis is only
// meaningful for exactly one word -- same reasoning, same signal, just
// applied to this row too instead of a fresh check. Left undefined on the
// initial DOMContentLoaded render and after an Ask Acharya Settings save
// (no live selection to classify at either point), so "Word" stays visible
// then.
function renderAcharyaQueryButtons(isSingleWord) {
  const row = document.getElementById('acharyaQueryButtonsRow');
  const fullContainer = document.getElementById('acharyaFullWidthButtons');
  const types = dgeGetEffectiveQueryTypes();
  if (!row || !fullContainer || !types) return;

  row.innerHTML = '';
  fullContainer.innerHTML = '';

  // Every Acharya query is a paid Gemini call, so the whole row is hidden
  // from a reader who is not authorised to spend the project's credits.
  if (typeof window.dgeAiFeaturesAllowed === 'function' && !window.dgeAiFeaturesAllowed()) return;
  const enabled = types.filter(q => q.enabled && !(q.id === 'grammar' && isSingleWord === false));
  enabled.forEach(q => {
    const btn = document.createElement('button');
    btn.className = 'tooltip-btn';
    btn.innerText = `${q.icon} ${q.label}`;
    if (q.style === 'full') {
      btn.style.cssText = 'width:100%; text-align:center; background: rgba(226, 102, 74, 0.2);';
    }
    btn.addEventListener('pointerdown', (e) => {
      if (q.action === 'bhashya') window.openBhashyaPicker(e);
      else window.askAcharya(e, q.id);
    });
    (q.style === 'full' ? fullContainer : row).appendChild(btn);
  });

  if (fullContainer.children.length > 0) {
    fullContainer.insertAdjacentHTML('afterbegin', '<div style="height:1px; background:rgba(255,255,255,0.1); margin:4px 0;"></div>');
  }
}
document.addEventListener('DOMContentLoaded', renderAcharyaQueryButtons);

/// Resolves the current selection against render.js's per-word <span
// class="dge-word"> boundaries (dgeWrapWordsForTap) rather than trusting
// window.getSelection().toString() directly -- the confirmed fragility:
// on mobile, a native drag/double-tap selection can jump to a shared
// ancestor on rapid re-selection and yield truncated or empty text. When
// the selection's start/end land inside a .dge-word span, this returns
// that span's own complete textContent (a single word), or -- for a
// multi-word drag spanning several spans -- walks the sibling .dge-word
// spans between them in document order and rejoins their text, which is
// also more robust than the raw string (immune to odd whitespace/entity
// handling at the drag's edges). Falls back to the raw selection string
// when the DOM doesn't have word spans (e.g. selection made outside any
// .shloka-text) so nothing regresses where the boundary doesn't exist.
// The element a run of .dge-word spans belongs to. A multi-word drag is only
// rejoined within ONE of these, so a selection that runs from the verse into
// the commentary below it falls back to the raw string rather than silently
// splicing two different texts together.
//
// 9 Sep 2026: .commentary-block joined .shloka-text here. Commentary text now
// carries word spans too (render.js), and the lead's report was that selecting
// a word in a commentary "restricts options to commentary-related choices
// rather than allowing full linguistic analysis" -- half of which was this:
// with no recognised container, a commentary selection fell back to the raw
// browser string and never resolved to a word.
var DGE_WORD_CONTAINERS = '.shloka-text, .commentary-block';
window.DGE_WORD_CONTAINERS = DGE_WORD_CONTAINERS;

/* --- Copy, from the 🕉️ Genie row ----------------------------------------
 *
 * Added 10 Sep 2026 on the lead's report that right-clicking a word gave no
 * way to copy it. Both handlers are registered in config.js's WORD_ACTIONS
 * with requiresCapability:'copy', so they appear only for a role that has
 * been granted it (role-access.js) -- an admin always, others by grant.
 *
 * The clipboard write is deliberately NOT a document 'copy' event:
 * copy-guard.js intercepts those for anyone without the capability, and
 * routing an explicitly-granted Copy button back through the same guard it
 * is exempt from would be a loop waiting to happen.
 */
function dgeCopyToClipboard(text, okMessage) {
  if (!text) { if (typeof showToast === 'function') showToast('Nothing selected.'); return; }
  const fallback = () => {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.left = '-9999px';
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); } catch (e) { /* reported below */ }
    ta.remove();
  };
  const done = () => { if (typeof showToast === 'function') showToast(okMessage || 'Copied.'); };
  try {
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(done).catch(() => { fallback(); done(); });
    } else { fallback(); done(); }
  } catch (e) { fallback(); done(); }
}
window.dgeCopyToClipboard = dgeCopyToClipboard;

window.dgeCopySelectionText = function(event) {
  if (event && event.preventDefault) event.preventDefault();
  const txt = (typeof window.dgeSelectedWordText === 'function' && window.dgeSelectedWordText())
    || window.dgeRobustSelectedText() || (window.lastSelectedText || '');
  dgeCopyToClipboard(String(txt).trim(), 'Copied.');
};

/* The sentence a word sits in. A Sanskrit sentence ends at a daṇḍa, so the
   span is cut at । or ॥ (and at Latin sentence punctuation, since a
   commentary's English gloss lives in the same block). Falls back to the
   whole block when there is no daṇḍa anywhere -- a verse line is a
   reasonable answer to "copy the sentence" and an empty clipboard is not. */
window.dgeCopySentenceAroundSelection = function(event) {
  if (event && event.preventDefault) event.preventDefault();
  let node = null;
  try {
    const sel = window.getSelection();
    if (sel && sel.rangeCount) {
      const c = sel.getRangeAt(0).startContainer;
      node = c.nodeType === 3 ? c.parentElement : c;
    }
  } catch (e) { /* fall through */ }
  const host = node && node.closest ? node.closest(DGE_WORD_CONTAINERS) : null;
  if (!host) { window.dgeCopySelectionText(event); return; }
  const full = (host.innerText || host.textContent || '').replace(/\s+/g, ' ').trim();
  const word = String((typeof window.dgeSelectedWordText === 'function' && window.dgeSelectedWordText())
    || window.dgeRobustSelectedText() || '').trim();
  let sentence = full;
  if (word) {
    const at = full.indexOf(word);
    if (at >= 0) {
      const before = full.slice(0, at);
      const after = full.slice(at + word.length);
      const cutL = Math.max(before.lastIndexOf('।'), before.lastIndexOf('॥'),
                            before.lastIndexOf('. '), before.lastIndexOf('? '), before.lastIndexOf('! '));
      const ends = [after.indexOf('।'), after.indexOf('॥'), after.indexOf('. ')].filter(i => i >= 0);
      const cutR = ends.length ? Math.min.apply(null, ends) : -1;
      sentence = (cutL >= 0 ? before.slice(cutL + 1) : before) + word +
                 (cutR >= 0 ? after.slice(0, cutR + 1) : after);
    }
  }
  dgeCopyToClipboard(sentence.trim(), 'Sentence copied.');
};

window.dgeRobustSelectedText = function() {
  let raw = '';
  try { raw = (window.getSelection().toString() || '').trim(); } catch (e) { return ''; }
  try {
    const sel = window.getSelection();
    if (!sel || sel.rangeCount === 0 || sel.isCollapsed) return raw;
    const range = sel.getRangeAt(0);
    const nodeToWord = (node) => {
      if (!node) return null;
      const el = node.nodeType === 3 ? node.parentElement : node;
      return el && el.closest ? el.closest('.dge-word') : null;
    };
    const startWord = nodeToWord(range.startContainer);
    const endWord = nodeToWord(range.endContainer);
    if (!startWord || !endWord) return raw;
    if (startWord === endWord) return startWord.textContent.trim() || raw;
    const container = startWord.closest(DGE_WORD_CONTAINERS);
    if (!container || !container.contains(endWord)) return raw;
    const words = Array.from(container.querySelectorAll('.dge-word'));
    const si = words.indexOf(startWord), ei = words.indexOf(endWord);
    if (si === -1 || ei === -1) return raw;
    const lo = Math.min(si, ei), hi = Math.max(si, ei);
    return words.slice(lo, hi + 1).map(w => w.textContent).join(' ').trim() || raw;
  } catch (e) {
    return raw;
  }
};

// Word-level tools on the selection tooltip: unlike the AI "Word" button
// above (which asks an LLM), these navigate to this app's own real,
// structured data for the selected word rather than generating an answer.
// Stands in for the browser's own selection highlight once
// selectionchange's handler above has cleared the real one (see its own
// comment) -- applied to the actual .dge-word span(s) the selection
// covered, using the identical start/end-word walk dgeRobustSelectedText()
// already does above, so "what's highlighted" and "what dgeSelectedWordText()
// returns" can never disagree. Returns false (and touches nothing) when the
// selection doesn't line up with real word spans, so the caller knows to
// leave the native selection alone for a freeform/Custom-mode drag.
window.dgeApplyWordSelectionHighlight = function(range) {
  dgeClearWordSelectionHighlight();
  try {
    const nodeToWord = (node) => {
      if (!node) return null;
      const el = node.nodeType === 3 ? node.parentElement : node;
      return el && el.closest ? el.closest('.dge-word') : null;
    };
    const startWord = nodeToWord(range.startContainer);
    const endWord = nodeToWord(range.endContainer);
    if (!startWord || !endWord) return false;
    let words;
    if (startWord === endWord) {
      words = [startWord];
    } else {
      const container = startWord.closest(DGE_WORD_CONTAINERS);
      if (!container || !container.contains(endWord)) return false;
      const all = Array.from(container.querySelectorAll('.dge-word'));
      const si = all.indexOf(startWord), ei = all.indexOf(endWord);
      if (si === -1 || ei === -1) return false;
      const lo = Math.min(si, ei), hi = Math.max(si, ei);
      words = all.slice(lo, hi + 1);
    }
    words.forEach(w => w.classList.add('dge-word-picked'));
    window._dgeHighlightedWords = words;
    return true;
  } catch (e) { return false; }
};
function dgeClearWordSelectionHighlight() {
  if (window._dgeHighlightedWords) {
    window._dgeHighlightedWords.forEach(w => { try { w.classList.remove('dge-word-picked'); } catch (e) {} });
  }
  window._dgeHighlightedWords = null;
}
window.dgeClearWordSelectionHighlight = dgeClearWordSelectionHighlight;

// Opens the word sheet on ONE word span, as if the reader had selected it.
// Rather than building the sheet a second way, this makes a real selection
// over the span and lets the selectionchange handler above do everything it
// already does -- positioning, the picked-word highlight, which tools apply.
// Used by the commentary tap handler (contextual-actions.js): a tap that
// lands on a word is a word selection, not a request for the commentary's
// own menu.
window.dgeOpenWordToolsForElement = function (el) {
  if (!el) return false;
  try {
    const sel = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(el);
    sel.removeAllRanges();
    sel.addRange(range);
    return true;
  } catch (e) { return false; }
};

function dgeSelectedWordText() {
  try {
    const live = window.dgeRobustSelectedText();
    if (live) return live;
  } catch (e) {}
  // The selectionchange handler above now clears the live browser
  // selection itself (to dismiss Android's native toolbar) as soon as the
  // Genie sheet appears, well before a reader taps any of its buttons --
  // so by the time a word-tools handler (Shabda/Dhatu/Sandhi/Samasa/
  // Search Library) calls this, window.getSelection() is often already
  // empty. window.lastSelectedText is the same text captured at that
  // selectionchange moment (see its own assignment above), so it is the
  // correct fallback rather than a stale guess.
  return window.lastSelectedText || '';
}

// What the word tools should LOOK UP, as opposed to what the reader tapped.
//
// Every index they consult is Devanagari-keyed -- the verb form index, the
// शब्दपाठः, the कोश, the corpus search index -- so with the display script set
// to Kannada, Telugu or IAST, every one of these tools answered "not found"
// for words that are plainly in the data. (Found while making the धातु/कोश
// marks work in every script, 10 Sep 2026: the mark appeared and the tap it
// promised then failed.) The modals themselves are Devanagari surfaces
// throughout -- paradigms, derivations, Dhatupatha entries -- so the
// Devanagari reading is also the right thing to show in them.
//
// highlight-words.js owns the conversion (and its cache); absent, this is the
// identity function and behaviour is exactly what it was.
function dgeLookupWordText() {
  const word = dgeSelectedWordText();
  if (!word || typeof window.dgeToDevanagariWord !== 'function') return word;
  // Multi-word selections are transliterated word by word: Sanscript handles a
  // whole string, but the Tamil/Bengali candidate resolution below is per word.
  return word.split(/(\s+)/).map(function (piece) {
    return /\s/.test(piece) ? piece : (window.dgeToDevanagariWord(piece) || piece);
  }).join('') || word;
}
window.dgeLookupWordText = dgeLookupWordText;
function dgeHideActionTooltip() {
  const tooltip = document.getElementById('actionTooltip');
  if (tooltip) tooltip.style.display = 'none';
  dgeClearWordSelectionHighlight();
  // Every word-tools handler (Shabda/Dhatu/Sandhi/Samasa/corpus-search)
  // reads the selected word into a local variable before calling this, so
  // clearing the live selection here is always safe. Without it, the
  // browser's own text-selection stayed active underneath whatever modal
  // opened next -- on Android that means its native "Translate / Copy /
  // Select all" selection toolbar kept floating on top of DGE's modal
  // (reported live, with screenshots). The selectionchange handler above
  // now clears it proactively too (see its own comment), so this is
  // usually a no-op by the time a button is clicked -- kept as a backstop
  // for the freeform/Custom-mode selections that handler deliberately
  // leaves alone.
  try { window.getSelection().removeAllRanges(); } catch (e) {}
}

// Instant Śabda lookup modal: this used to open shabda.html in a new tab --
// a full page navigation (blank paint, the whole declension-browser UI,
// then a scroll-into-view) just to answer "what does this inflected form
// decline from?". The reader never needed the browser UI for that, only
// the one answer, so this fetches the same data directly and renders it
// in a modal without leaving the page. A kṛdanta (verb-derived) match now
// renders its real step-by-step derivation inline too, not just a link to
// go read it elsewhere -- see dgeRenderShabdaKrt below.
const DGE_SHABDA_MODAL_ID = 'dgeShabdaModal';
let DGE_SHABDA_CACHE = null; // the parsed shabdapatha item list, fetched once per page load
const DGE_KRT_NAME = { kta:'क्त', ktavatu:'क्तवतु', ktvA:'क्त्वा', tumun:'तुमुन्', Satf:'शतृ', SAnac:'शानच्', tavya:'तव्य', anIyar:'अनीयर्', yat:'यत्', Rvul:'ण्वुल्', tfc:'तृच्', lyuw:'ल्युट्' };
const DGE_KRT_NAME_EN = { kta:'past passive participle', ktavatu:'past active participle', ktvA:'absolutive', tumun:'infinitive', Satf:'present participle, parasmaipada', SAnac:'present participle, ātmanepada', tavya:'gerundive', anIyar:'gerundive', yat:'gerundive', Rvul:'agent noun', tfc:'agent noun', lyuw:'action noun' };
const DGE_VIBHAKTI = ["प्रथमा","द्वितीया","तृतीया","चतुर्थी","पञ्चमी","षष्ठी","सप्तमी","सम्बोधनम्"];

function dgeShabdaEsc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;'); }

// Shared by every "instant word-tool" modal (Śabda, Dhātu, and any future
// one) -- a single class-scoped stylesheet rather than one copy per modal
// ID, so a second modal (dgeDhatuModal) built the same way gets the same
// look for free instead of duplicating this block.
function dgeEnsureWordModalStyle() {
  if (document.getElementById('dgeWordModalStyle')) return;
  const style = document.createElement('style');
  style.id = 'dgeWordModalStyle';
  style.textContent = [
    '.dge-word-modal .dsm-word{font-size:22px;font-weight:700;color:var(--accent-red);margin:0 0 2px;}',
    '.dge-word-modal .dsm-sub{font-size:12px;color:var(--muted-text);margin-bottom:14px;}',
    '.dge-word-modal .dsm-kv{display:flex;gap:8px;padding:4px 0;font-size:13px;border-bottom:1px dashed var(--card-border);}',
    '.dge-word-modal .dsm-kk{flex:0 0 100px;color:var(--muted-text);font-size:11px;text-transform:uppercase;letter-spacing:.4px;padding-top:2px;}',
    '.dge-word-modal .dsm-kvv{flex:1;}',
    '.dge-word-modal table.dsm-table{width:100%;border-collapse:collapse;margin-top:10px;font-size:13px;}',
    '.dge-word-modal table.dsm-table th,.dge-word-modal table.dsm-table td{padding:6px 8px;text-align:center;border-bottom:1px dashed var(--card-border);}',
    '.dge-word-modal table.dsm-table th{color:var(--muted-text);font-size:10.5px;font-weight:700;}',
    '.dge-word-modal table.dsm-table td:first-child,.dge-word-modal table.dsm-table th:first-child{text-align:left;color:var(--muted-text);}',
    '.dge-word-modal table.dsm-table td.dsm-hl{background:rgba(226,102,74,.28);font-weight:700;border-radius:6px;}',
    '.dge-word-modal table.dsm-table td.sst-cell-hint{cursor:pointer;}',
    '.dge-word-modal table.dsm-table td.sst-cell-on{outline:2px solid var(--accent-red);outline-offset:-2px;border-radius:6px;}',
    '.dge-word-modal .dsm-lakara-block{margin-top:10px;border:1px solid var(--card-border);border-radius:var(--radius-sm);padding:0 10px 8px;}',
    '.dge-word-modal .dsm-lakara-block summary{cursor:pointer;padding:9px 0;font-size:14px;font-weight:700;color:var(--accent-red);list-style:none;}',
    '.dge-word-modal .dsm-lakara-block summary::-webkit-details-marker{display:none;}',
    '.dge-word-modal .dsm-lakara-block summary::before{content:"▸ ";display:inline-block;transition:transform .15s;}',
    '.dge-word-modal .dsm-lakara-block[open] summary::before{transform:rotate(90deg);}',
    '.dge-word-modal .dsm-lakara-en{font-size:11px;font-weight:600;color:var(--muted-text);}',
    '.dge-word-modal .dsm-steps{list-style:none;margin:8px 0 0;padding:0;}',
    '.dge-word-modal .dsm-steps li{display:flex;gap:10px;align-items:baseline;padding:5px 0;border-bottom:1px dashed var(--card-border);font-size:13px;}',
    '.dge-word-modal .dsm-code{flex:0 0 62px;font-family:monospace;color:var(--muted-text);font-size:11px;}',
    '.dge-word-modal .dsm-code.dge-sutra-ref{cursor:pointer;text-decoration:underline dotted;color:var(--accent-red);}',
    '.dge-word-modal .dsm-result{flex:1;font-size:15px;}',
    '.dge-word-modal .dsm-loading{padding:24px 0;text-align:center;color:var(--muted-text);}',
    '.dge-word-modal .dsm-empty{padding:12px 0;color:var(--muted-text);font-size:13px;line-height:1.6;}',
    '.dge-word-modal .dsm-empty a{color:var(--accent-red);}',
    '.dge-word-modal .dsm-full-link{display:block;text-align:center;margin-top:14px;font-size:12px;color:var(--muted-text);}',
    '.dge-word-modal .dsm-section-label{font-size:11px;font-weight:700;color:var(--muted-text);text-transform:uppercase;letter-spacing:.4px;margin:16px 0 6px;border-top:1px solid var(--card-border);padding-top:12px;}',
    '.dge-word-modal .dsm-pada-listed{opacity:.72;font-style:italic;}',
    '.dge-word-modal .dsm-krt-alt{margin:-8px 0 12px;font-size:11.5px;opacity:.85;}',
    '.dge-word-modal .dsm-kosha-entry{padding:6px 0;font-size:12.5px;line-height:1.55;border-bottom:1px dashed var(--card-border);}',
    '.dge-word-modal .dsm-kosha-entry b{color:var(--accent-red);}',
    '.dge-word-modal .dsm-kosha-more{width:100%;margin-top:8px;}',
    '.dge-word-modal .dsm-sandhi-row{padding:6px 0;font-size:14px;border-bottom:1px dashed var(--card-border);}',
    '.dge-word-modal .dsm-sandhi-row .dge-sutra-ref{margin-left:6px;font-size:11px;color:var(--muted-text);cursor:pointer;text-decoration:underline dotted;}',
    '.dge-word-modal .dsm-ai-tag{display:inline-block;margin-left:6px;font-size:9.5px;font-weight:600;color:var(--muted-text);background:var(--card-bg);border:1px solid var(--card-border);border-radius:4px;padding:1px 5px;text-transform:none;letter-spacing:0;}',
    '.dge-word-modal .dsm-lex-langs{display:grid;grid-template-columns:1fr;gap:2px;margin-bottom:10px;}',
    '.dge-word-modal .dsm-lex-row{display:flex;gap:8px;padding:4px 0;font-size:12.5px;border-bottom:1px dashed var(--card-border);}',
    '.dge-word-modal .dsm-lex-row b{flex:0 0 78px;color:var(--muted-text);font-weight:700;}',
    '.dge-word-modal .dsm-lex-pedagogy{font-size:13px;line-height:1.55;}',
    '.dge-word-modal .dsm-lex-pedagogy>p{margin:0 0 8px;color:var(--muted-text);}',
    '.dge-word-modal .dsm-lex-scenario{background:var(--card-bg);border:1px solid var(--card-border);border-radius:8px;padding:8px 10px;margin-bottom:6px;font-size:12.5px;}',
    '.dge-word-modal .dsm-lex-example{margin-top:4px;font-size:14px;}',
    '.dge-word-modal .dsm-lex-example-en{color:var(--muted-text);font-size:12px;font-style:italic;}'
  ].join('\n');
  document.head.appendChild(style);
}

// Builds (once) a modal-overlay/modal-content/modal-body shell in the
// shared word-modal shape, and returns its body element for the caller to
// fill in. `id` is the overlay's element id, `bodyId` the id given to its
// body element, `headerHtml` the header <h3> content.
function dgeEnsureWordModalShell(id, bodyId, headerHtml) {
  if (document.getElementById(id)) return document.getElementById(bodyId);
  dgeEnsureWordModalStyle();
  document.body.insertAdjacentHTML('beforeend',
    '<div class="modal-overlay" id="' + id + '">' +
      '<div class="modal-content dge-word-modal" style="max-width:420px;">' +
        '<div class="modal-header-sticky">' +
          '<h3 style="margin:0; color:var(--accent-red); font-size:16px;">' + headerHtml + '</h3>' +
          '<button class="btn-sm" onclick="window.closeModal(\'' + id + '\')" style="font-size:11px;">✖ Close</button>' +
        '</div>' +
        '<div class="modal-body" id="' + bodyId + '"></div>' +
      '</div>' +
    '</div>');
  return document.getElementById(bodyId);
}

function dgeEnsureShabdaModal() {
  dgeEnsureWordModalShell(DGE_SHABDA_MODAL_ID, 'dgeShabdaModalBody', '🔤 शब्दः · Śabda');
  return document.getElementById(DGE_SHABDA_MODAL_ID);
}

function dgeFetchShabdaData(word) {
  // Sharded by the word's first character (tools/build_shabda_shards.py):
  // declension is suffixal, so a form's first akshara is its stem's --
  // one ~100 KB shard answers instead of the whole 7.6 MB file. The full
  // file remains the fallback for a missing shard (and for callers that
  // pass no word).
  const ch = String(word || '').trim()[0];
  if (ch) {
    const name = 'u' + ch.codePointAt(0).toString(16).padStart(4, '0') + '.json';
    DGE_SHABDA_SHARDS = DGE_SHABDA_SHARDS || {};
    if (!DGE_SHABDA_SHARDS[name]) {
      DGE_SHABDA_SHARDS[name] =
        fetch('data/vedanga/vyakarana/shabdapatha/by_akshara/' + name)
          .then(r => r.ok ? r.json() : null)
          .then(d => d ? (d.items || []) : null)
          .catch(() => null);
    }
    return DGE_SHABDA_SHARDS[name].then(items =>
      items !== null ? items : dgeFetchShabdaData());
  }
  if (DGE_SHABDA_CACHE) return Promise.resolve(DGE_SHABDA_CACHE);
  return fetch('data/vedanga/vyakarana/shabdapatha/data.json')
    .then(r => r.ok ? r.json() : { items: [] })
    .then(d => { DGE_SHABDA_CACHE = d.items || []; return DGE_SHABDA_CACHE; })
    .catch(() => { DGE_SHABDA_CACHE = []; return DGE_SHABDA_CACHE; });
}
let DGE_SHABDA_SHARDS = null;

// Same exact-cell reverse lookup as shabda.js's findFormLocation, kept as
// its own small copy since shabda.js's version lives inside that page's
// own closure and this page (index.html) doesn't load shabda.js at all.
function dgeFindShabdaForm(items, surface) {
  const target = String(surface || '').trim();
  for (let i = 0; i < items.length; i++) {
    const cells = String(items[i].forms || '').split(';');
    for (let c = 0; c < cells.length && c < 24; c++) {
      const variants = (cells[c] || '').split('-');
      for (let v = 0; v < variants.length; v++) {
        if (variants[v].trim() === target) return { item: items[i], cellIndex: c };
      }
    }
  }
  return null;
}

function dgeShabdaDeclTable(forms, hlIdx) {
  const cells = String(forms || '').split(';');
  while (cells.length < 24) cells.push('');
  let h = '<table class="dsm-table"><thead><tr><th></th><th class="deva">एक.</th><th class="deva">द्वि.</th><th class="deva">बहु.</th></tr></thead><tbody>';
  for (let vb = 0; vb < 8; vb++) {
    h += '<tr><th class="deva">' + DGE_VIBHAKTI[vb] + '</th>';
    for (let n = 0; n < 3; n++) {
      const idx = vb * 3 + n;
      const hl = (hlIdx != null && idx === hlIdx);
      const has = !!(cells[idx] || '').trim();
      h += '<td class="deva' + (hl ? ' dsm-hl' : '') + (has ? ' sst-cell-hint' : '') + '"' +
        (has ? ' data-ci="' + idx + '" title="रूपसिद्धिः — tap for the derivation"' : '') + '>' +
        dgeShabdaEsc((cells[idx] || '').split('-').join(', ')) + '</td>';
    }
    h += '</tr>';
  }
  h += '</tbody></table>';
  return h;
}

// Real gap found via live testing, 24 Aug: these sutra codes rendered as
// inert plain text -- no onclick, no data-sutra, nothing. The app already
// has a working in-place sutra popover (intellisense.js's .dge-sutra-ref
// convention, opened from Prakriyā/Rūpasiddhi/the Sandhi tool via the
// same document-level click delegate) -- this table's own derivation
// steps just never adopted it. Same isSutra regex prakriya.js already
// uses to tell a real sutra citation (clickable) from a paribhasha/
// vartika reference (shown plainly, nothing to look up).
function dgeShabdaStepsHtml(steps) {
  let last = '';
  return '<ol class="dsm-steps">' + steps.map(function (st) {
    const code = st[0];
    if (st.length > 1) last = st[1];
    const isSutra = /^[1-8]\.[1-4]\.\d{1,3}$/.test(code);
    const codeHtml = isSutra
      ? '<span class="dsm-code dge-sutra-ref" data-sutra="' + dgeShabdaEsc(code) + '" role="button" tabindex="0">' + dgeShabdaEsc(code) + '</span>'
      : '<span class="dsm-code">' + dgeShabdaEsc(code) + '</span>';
    return '<li>' + codeHtml + '<span class="dsm-result deva">' + dgeShabdaEsc(last) + '</span></li>';
  }).join('') + '</ol>';
}

// "Search Library" -- where else does this word occur (§5.2): closes the shabda modal and
// opens the global corpus search already searching for the surface form the
// reader looked up. Rendered only when global-search.js is actually loaded
// on this page, so the link can never be a dead end. Appended to every
// branch of dgeOpenShabdaForSelection's fallback chain below, not just the
// exact-match case -- useful regardless of which of them actually answered.
function dgeShabdaWhereElseLink(surface) {
  if (!(window.DGEGlobalSearch && window.DGEGlobalSearch.open)) return '';
  return '<a class="dsm-full-link" href="#" data-dsm-where="' + dgeShabdaEsc(surface) + '">🔍 साहित्ये अन्यत्र — search library ↗</a>';
}
function dgeShabdaWireWhereElse(body) {
  const a = body.querySelector('[data-dsm-where]');
  if (!a) return;
  a.addEventListener('click', function (e) {
    e.preventDefault();
    if (typeof closeModal === 'function') closeModal(DGE_SHABDA_MODAL_ID);
    window.DGEGlobalSearch.open(a.getAttribute('data-dsm-where'));
  });
}

// The matched (or tapped) declension cell's step-by-step subanta prakriyā,
// via js/subanta-steps.js — the "Shabda must return the prakriyā" ask.
// Degrades silently to the plain table when that script isn't loaded or the
// engine can't load: the lookup's own answer never depends on it. Only the
// exact-match branch has a cell to derive from -- the other fallbacks below
// (kṛdanta, morphology, sandhi) never call this.
function dgeShabdaSubantaSteps(body, item, ci) {
  const S = window.DGESubantaSteps, box = body.querySelector('#dsmSteps');
  if (!S || !box || ci == null || ci < 0) return;
  const vb = Math.floor(ci / 3), vc = ci % 3;
  S.css();
  body.querySelectorAll('td.sst-cell-on').forEach(td => td.classList.remove('sst-cell-on'));
  const cell = body.querySelector('td[data-ci="' + ci + '"]');
  if (cell) cell.classList.add('sst-cell-on');
  box.className = 'sst-panel';
  box.innerHTML = '<div class="sst-loading">रूपसिद्धिः सज्जीक्रियते…</div>';
  const expected = String(item.forms || '').split(';')[ci] || '';
  S.derive(item.word, item.linga, vb, vc).then(function (results) {
    if (!box.isConnected) return;
    box.innerHTML = S.panelHtml(item.word, item.linga, vb, vc, results, expected);
  }).catch(function () {
    if (!box.isConnected) return;
    box.innerHTML = '<p class="sst-note">Could not load the derivation engine — the forms above are unaffected.</p>';
  });
}
// Wires the tap-any-cell-for-its-derivation behaviour once the exact-match
// HTML (dgeShabdaExactHtml, which lays down the #dsmSteps placeholder and
// td[data-ci] cells) is actually in the DOM -- called from
// dgeOpenShabdaForSelection after its one body.innerHTML write, never from
// dgeShabdaExactHtml itself (which only builds a string, no DOM access).
function dgeWireShabdaSubantaSteps(body, item, cellIndex) {
  dgeShabdaSubantaSteps(body, item, cellIndex);
  body.querySelectorAll('td[data-ci]').forEach(function (td) {
    td.addEventListener('click', function () {
      dgeShabdaSubantaSteps(body, item, parseInt(td.dataset.ci, 10));
    });
  });
}

// A form neither the fixed शब्दपाठः, the kṛdanta index, Vidyut's curated
// morphology vocabulary, nor a precomputed sandhi split resolves may still
// be an honest SAMĀSA (compound) whose final member (उत्तरपदम्) is an
// ordinary listed pratipadika, declined regularly -- Sanskrit compounds
// inflect only on their last member. Scans every headword's own 24 already-
// tabulated forms for one the surface literally ENDS WITH (e.g.
// जयीन्द्रज्योतिषे ends in ज्योतिष्'s चतुर्थी एकवचन "ज्योतिषे" --
// ज्योतिष् itself is a real headword, @jyotiS1). Pure string comparison
// over curated data already on the page (no WASM, no network beyond the
// one full-list fetch below), kept as the LAST real attempt before the
// honest not-found message: dgeMorphFallbackHtml and dgeSandhiFallbackHtml
// above are genuine Vidyut analyses, so they take priority whenever they
// actually have an answer -- this is a coarser heuristic (it identifies
// only the final member, not the whole compound) that fires only once both
// of those have already come up empty.
//
// False-positive guard, verified against the whole Raghavendra Vijaya
// sarga_1 corpus (43 real compound hits, 0 known false positives after
// tuning): a short/common ending matches unrelated words by pure chance
// (3-character endings like तम्/कम्/सन् falsely matched verb forms and
// kṛdantas), so both the matched suffix and the leftover prefix must clear
// a minimum length; सर्वनाम (pronoun: तद्/यद्/एतद्/किम्/अदस्) headwords are
// excluded outright since their endings coincide with ordinary noun
// endings but a bare pronoun stem is never a real compound's semantic
// final member. Among qualifying hits the LONGEST suffix wins (most
// specific). Mirrors shabda.js's own copy of this same logic (kept
// separate for the same reason as dgeFindShabdaForm above -- this page
// doesn't load shabda.js).
const DGE_COMPOUND_MIN_SUFFIX_LEN = 4, DGE_COMPOUND_MIN_PREFIX_LEN = 2;
function dgeIsPronounHeadword(it) { return (it.artha || '').indexOf('सर्वनाम') >= 0; }
function dgeFindShabdaCompoundMatch(items, surface) {
  const w = String(surface || '').trim(); if (!w) return null;
  let best = null;
  for (let i = 0; i < items.length; i++) {
    const it = items[i];
    if (dgeIsPronounHeadword(it)) continue;
    const cells = String(it.forms || '').split(';');
    for (let c = 0; c < cells.length && c < 24; c++) {
      const variants = (cells[c] || '').split('-');
      for (let v = 0; v < variants.length; v++) {
        const form = variants[v].trim();
        if (!form || form.length < DGE_COMPOUND_MIN_SUFFIX_LEN) continue;
        if (w.length - form.length < DGE_COMPOUND_MIN_PREFIX_LEN) continue;
        if (w.slice(w.length - form.length) !== form) continue;
        if (!best || form.length > best.form.length) {
          best = { item: it, cellIndex: c, form: form, prefix: w.slice(0, w.length - form.length) };
        }
      }
    }
  }
  return best;
}
// Renders a compound-final match honestly distinct from an ordinary
// headword hit (dgeShabdaExactHtml): names the recognized final member and
// its vibhakti/vacana, shows that member's own full declension table (tap-
// for-derivation included, same as an exact match), and flags the
// remaining prefix as an unlisted/unanalyzed compound part -- never blurs
// the line between "this exact word is a listed headword" and "this
// word's ending matches a listed headword's declined form."
function dgeShabdaCompoundHtml(surface, hit) {
  const vb = Math.floor(hit.cellIndex / 3), vac = ['एकवचनम्', 'द्विवचनम्', 'बहुवचनम्'][hit.cellIndex % 3];
  return '<div class="dsm-word deva">' + dgeShabdaEsc(surface) + '</div>' +
    '<div class="dsm-sub">समासः · not itself a listed headword -- ends in a recognized final member (उत्तरपदम्)</div>' +
    '<div class="dsm-kv"><div class="dsm-kk">उत्तरपदम्</div><div class="dsm-kvv deva">' + dgeShabdaEsc(hit.item.word) +
      ' — ' + dgeShabdaEsc(DGE_VIBHAKTI[vb]) + ' ' + dgeShabdaEsc(vac) +
      (hit.item.artha ? ', ' + dgeShabdaEsc(hit.item.artha) : '') + '</div></div>' +
    '<div class="dsm-kv"><div class="dsm-kk">शेषः</div><div class="dsm-kvv deva">' + dgeShabdaEsc(hit.prefix) + '</div></div>' +
    '<div class="dsm-empty">The remaining part above is not separately analyzed here (likely a proper name or an ' +
      'unlisted prior member) — only the compound\'s final member is identified, from its own declension table below.</div>' +
    dgeShabdaDeclTable(hit.item.forms, hit.cellIndex) +
    '<div id="dsmSteps"></div>' +
    '<a class="dsm-full-link" href="vyakarana/shabda.html#' + dgeShabdaEsc(hit.item.id) + '" target="_blank">View in full शब्दपाठः browser ↗</a>' +
    dgeShabdaWhereElseLink(hit.item.word);
}
function dgeShabdaNotFoundHtml(surface) {
  return '<div class="dsm-empty">No exact form found for "' + dgeShabdaEsc(surface) + '", ' +
    'and it doesn\'t look like a sandhi join the grammar engine resolves either. ' +
    'It may still be findable in the full word list — <a href="vyakarana/shabda.html?q=' + encodeURIComponent(surface) + '" target="_blank">search the full शब्दपाठः ↗</a>, or ' +
    '<a href="#" id="dsmReportMissing">report this as missing</a>.</div>' +
    '<div class="dsm-gen">Or derive its table now, taking "' + dgeShabdaEsc(surface) + '" as the stem: ' +
    ['P', 'S', 'N'].map(function (l) { return '<a class="btn-sm" href="vyakarana/shabda.html?gen=' + encodeURIComponent(surface) + '&l=' + l + '" target="_blank">' + ({ P: 'पुं', S: 'स्त्री', N: 'नपुं' })[l] + '</a>'; }).join(' ') +
    ' <span class="dsm-sub">(vidyut-prakriya, on the Śabdapāṭha page)</span></div>' +
    dgeShabdaWhereElseLink(surface);
}

function dgeShabdaExactHtml(it, cellIndex) {
  const krtTag = (it.krt || '').split(',').filter(Boolean)
    .map(k => DGE_KRT_NAME[k] || k).join(', ');
  let h = '<div class="dsm-word deva">' + dgeShabdaEsc(it.word) + '</div>' +
    '<div class="dsm-sub">' + dgeShabdaEsc(it.linga_iast || '') +
    (krtTag ? ' · <span class="deva">' + dgeShabdaEsc(krtTag) + 'प्रत्ययान्तः</span>' : '') + '</div>';
  if (it.artha) h += '<div class="dsm-kv"><div class="dsm-kk">अर्थः</div><div class="dsm-kvv deva">' + dgeShabdaEsc(it.artha) + '</div></div>';
  if (it.artha_hin) h += '<div class="dsm-kv"><div class="dsm-kk">हिन्दी</div><div class="dsm-kvv">' + dgeShabdaEsc(it.artha_hin) + '</div></div>';
  if (it.artha_eng) h += '<div class="dsm-kv"><div class="dsm-kk">English</div><div class="dsm-kvv">' + dgeShabdaEsc(it.artha_eng) + '</div></div>';
  h += dgeShabdaDeclTable(it.forms, cellIndex);
  // The looked-up form's own step-by-step prakriyā renders here right away
  // (js/subanta-steps.js, the rupasiddhi WASM engine loaded lazily); any
  // other cell in the table is tappable for its derivation too -- see
  // dgeWireShabdaSubantaSteps, called once this string is actually in the DOM.
  h += '<div id="dsmSteps"></div>';
  h += '<a class="dsm-full-link" href="vyakarana/shabda.html#' + dgeShabdaEsc(it.id) + '" target="_blank">View in full शब्दपाठः browser ↗</a>';
  h += dgeShabdaWhereElseLink(it.word);
  return h;
}

// A form the Śabdapāṭha (fixed nominal stems) genuinely has no entry for
// may still be a kṛdanta -- a word derived from a verb root (लभ्यः, from
// लभ्+यत्) via tools/build_krt_form_index.py's reverse index. Renders the
// real step-by-step derivation right here (Category 5's "Prakriya
// integration in the modal"), fetched from the same per-root JSON
// prakriya.js's krdanta.html view uses, not just a link to go read it on
// another page. Resolves to null (not a fallback message) on a miss --
// dgeOpenShabdaForSelection's fallback chain decides what happens next.
// Which of several homographic roots to show FIRST. The only evidence in the
// building is how often each root is attested in this corpus by forms that are
// NOT ambiguous — tools/build_dhatu_prayoga_index.py writes exactly that as
// root_weights.json. डुकृञ् करणे is written unambiguously 17,049 times
// (करोति, चकार, कुर्वन्ति), कृञ् हिंसायाम् 110, so कृत्वा leads with "to do".
// Absent the file, order is left as the index gave it rather than guessed at.
let DGE_ROOT_WEIGHTS_PROMISE = null;
function dgeRootWeights() {
  if (!DGE_ROOT_WEIGHTS_PROMISE) {
    DGE_ROOT_WEIGHTS_PROMISE = fetch('data/vedanga/vyakarana/dhatu_prayoga/root_weights.json', { cache: 'force-cache' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) { return (d && d.weights) || {}; })
      .catch(function () { return {}; });
  }
  return DGE_ROOT_WEIGHTS_PROMISE;
}
window.dgeRankDhatuCandidates = function (list) {
  if (!list || list.length < 2) return Promise.resolve(list || []);
  return dgeRootWeights().then(function (w) {
    return list.slice().sort(function (a, b) {
      const d = (w[b.c] || 0) - (w[a.c] || 0);
      return d || String(a.c).localeCompare(String(b.c));
    });
  }).catch(function () { return list; });
};

function dgeShabdaKrtHtml(surface, hit, all) {
  const code = hit.c, krtKey = hit.k, rootPart = code.split('.')[0];
  return fetch('data/vedanga/vyakarana/prakriya/' + rootPart + '/' + code + '.json')
    .then(r => r.ok ? r.json() : null)
    .then(function (d) {
      const k = d && d.krt && d.krt.find(x => x.k === krtKey);
      if (!k) return null;
      // Say plainly that another root writes this too, rather than presenting
      // one reading as the answer.
      const others = (all || []).filter(function (x) { return x.c !== code; });
      const alt = others.length
        ? '<div class="dsm-sub dsm-krt-alt">' + others.length + ' other root' + (others.length === 1 ? '' : 's') +
          ' write' + (others.length === 1 ? 's' : '') + ' this same form — ' +
          others.map(function (x) {
            return '<a href="vyakarana/krdanta.html#' + dgeShabdaEsc(x.c) + ':' + dgeShabdaEsc(x.k) + '" target="_blank">' + dgeShabdaEsc(x.c) + '</a>';
          }).join(', ') + '. This one is the most attested in the library.</div>'
        : '';
      return '<div class="dsm-word deva">' + dgeShabdaEsc(surface) + '</div>' +
        '<div class="dsm-sub">कृदन्तः · ' + dgeShabdaEsc(DGE_KRT_NAME[krtKey] || krtKey) + ' (' + dgeShabdaEsc(DGE_KRT_NAME_EN[krtKey] || '') + ') · from <span class="deva">' + dgeShabdaEsc(d.dhatu) + '</span> "' + dgeShabdaEsc(d.artha || '') + '"</div>' +
        alt +
        dgeShabdaStepsHtml(k.s) +
        '<a class="dsm-full-link" href="vyakarana/krdanta.html#' + dgeShabdaEsc(code) + ':' + dgeShabdaEsc(krtKey) + '" target="_blank">View in full कृदन्त browser ↗</a>' +
        dgeShabdaWhereElseLink(surface);
    })
    .catch(() => null);
}

// Neither the fixed शब्दपाठः nor the kṛdanta index has every word (they are
// both curated, finite lists) -- Vidyut's own precomputed morphology
// (data/_morph/, built by tools/build_morphology.py, exposed publicly
// as window.dgeAnalyseWord by intellisense.js) resolves inflected forms
// well beyond either list. Not every miss has an entry here either --
// Vidyut resolves inflected forms, not sandhi-joined ones, which is
// exactly what dgeSandhiFallbackHtml below tries next.
function dgeMorphFallbackHtml(word) {
  if (typeof window.dgeAnalyseWord !== 'function') return Promise.resolve(null);
  return window.dgeAnalyseWord(word).then(function (an) {
    if (!an || !an.length) return null;
    const byLemma = {};
    an.forEach(function (a) { (byLemma[a.lemma] = byLemma[a.lemma] || []).push(a.gloss); });
    let h = '<div class="dsm-word deva">' + dgeShabdaEsc(word) + '</div>' +
      '<div class="dsm-sub">व्याकरणम् · not in the fixed शब्दपाठः list, but the grammar engine resolves this form directly</div>';
    const lingaOf = {};
    an.forEach(function (a) { if (a.kind === 's' && a.linga && !lingaOf[a.lemma]) lingaOf[a.lemma] = a.linga.toUpperCase(); });
    Object.keys(byLemma).forEach(function (lemma) {
      h += '<div class="dsm-kv"><div class="dsm-kk deva">' + dgeShabdaEsc(lemma) + '</div><div class="dsm-kvv">' +
        byLemma[lemma].filter(Boolean).map(g => dgeShabdaEsc(g)).join(' · ') +
        (lingaOf[lemma] ? ' <a class="btn-sm" href="vyakarana/shabda.html?gen=' + encodeURIComponent(lemma) + '&l=' + lingaOf[lemma] + '" target="_blank" title="All 24 forms of ' + dgeShabdaEsc(lemma) + ', derived">रूपाणि ↗</a>' : '') +
        '</div></div>';
    });
    return h + dgeShabdaWhereElseLink(word);
  }).catch(() => null);
}

// Real, precomputed sandhi-vicheda from Vidyut (data/_sandhi/, built by
// tools/build_sandhi_index.py -- see that file's own docstring for exactly
// what it covers and why). Shared between two callers: this Shabda-modal
// fallback (word looks like a compound the fixed lists don't carry on its
// own) and the dedicated Sandhi word-tool button below, which shows the
// identical rows in its own modal when there's no Shabda context at all.
// Caps how long any one external-data promise is allowed to keep a UI
// surface waiting -- `fallback` is returned instead once `ms` elapses,
// without cancelling the original promise (it may still resolve later and
// populate a cache for next time, it just stops blocking THIS caller).
// Used for anything that can reach out to a CDN the reader's own network
// might be slow to, or briefly unable to, reach: a hung fetch there should
// degrade to "no result yet" or an AI fallback, never a stuck spinner.
function dgeWithTimeout(promise, ms, fallback) {
  return Promise.race([promise, new Promise(res => setTimeout(() => res(fallback), ms))]);
}

const DGE_SANDHI_CDN = 'https://cdn.jsdelivr.net/gh/Tribhuvanachar/bhumandala@2a255c3dd7f357364c75a72afa664a6588c8ff44/_sandhi';
const DGE_SANDHI_BUCKET_CACHE = {};
function dgeSandhiBucketOf(slp) {
  const two = (slp + '__').slice(0, 2);
  return two.split('').map(c => (c >= 'A' && c <= 'Z') ? c + '_'
                                : (/[a-z0-9]/.test(c) ? c : 'x')).join('');
}
function dgeFetchSandhiBucket(name) {
  if (DGE_SANDHI_BUCKET_CACHE[name]) return DGE_SANDHI_BUCKET_CACHE[name];
  // window.SANDHI_DATA_BASE overrides the CDN, same convention as
  // WORDNET_DATA_BASE in intellisense.js -- set it to '' to read a local
  // build from data/_sandhi/ instead (never committed to main, see
  // tools/build_sandhi_index.py's own manifest note on repo size).
  const set = window.SANDHI_DATA_BASE;
  const cdn = (set === undefined ? DGE_SANDHI_CDN : (set || '')).replace(/\/+$/, '');
  const url = cdn ? (cdn + '/' + name + '.json') : ('data/_sandhi/' + name + '.json');
  DGE_SANDHI_BUCKET_CACHE[name] = fetch(url, { cache: 'force-cache' })
    .then(r => (r.ok ? r.json() : null)).catch(() => null);
  return DGE_SANDHI_BUCKET_CACHE[name];
}
// The locally-committed split index (tools/build_sandhi_split_index.py,
// sanskrit_parser's Sandhi.split_all validated against this repo's own word
// lists). Tried BEFORE the CDN-hosted Vidyut index: it ships in the repo, so
// it is the one that works on a local checkout -- which is why the Sandhi
// tool did nothing there. Each half carries the list that recognised it, so
// a half that is a real verb form can be marked as the dhatu link it is.
const DGE_LOCAL_SANDHI_CACHE = {};
function dgeFetchLocalSandhiBucket(name) {
  if (!DGE_LOCAL_SANDHI_CACHE[name]) {
    DGE_LOCAL_SANDHI_CACHE[name] = fetch('data/_sandhi_local/' + name + '.json', { cache: 'force-cache' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .catch(function () { return null; });
  }
  return DGE_LOCAL_SANDHI_CACHE[name];
}
function dgeFindLocalSandhiSplits(word) {
  const clean = String(word || '').trim();
  if (!clean || typeof window.Sanscript === 'undefined') return Promise.resolve(null);
  let slp;
  try { slp = window.Sanscript.t(clean, 'devanagari', 'slp1'); } catch (e) { return Promise.resolve(null); }
  if (!slp) return Promise.resolve(null);
  return dgeWithTimeout(dgeFetchLocalSandhiBucket(dgeSandhiBucketOf(slp)), 5000, null)
    .then(function (b) { return (b && b[clean]) || null; });
}

function dgeFindSandhiSplits(word) {
  const clean = String(word || '').trim();
  if (!clean || typeof window.Sanscript === 'undefined') return Promise.resolve(null);
  let slp;
  try { slp = window.Sanscript.t(clean, 'devanagari', 'slp1'); } catch (e) { return Promise.resolve(null); }
  if (!slp) return Promise.resolve(null);
  // Capped at 5s: a hung fetch to the CDN must not keep the Sandhi
  // word-tool (or the Shabda modal's fallback chain, which also calls
  // this) waiting indefinitely -- both fall back to the AI path on a
  // timeout exactly as they would on a genuine miss.
  return dgeWithTimeout(dgeFetchSandhiBucket(dgeSandhiBucketOf(slp)), 5000, null)
    .then(b => (b && b[clean]) || null);
}
// One row per split, each half marked with what recognised it. A half that is
// a real verb form gets the dhatu background and is tappable straight through
// to its paradigm -- the lead's ask: "integrate this with your local dhatu
// library to identify and highlight matches with a special background color."
const DGE_SANDHI_SRC_TITLE = {
  v: 'a verb form — tap for its root',
  n: 'a known inflected form in this corpus',
  u: 'an upasarga'
};
function dgeLocalSandhiRowsHtml(splits) {
  return splits.map(function (s) {
    function half(text, src) {
      const cls = 'dge-sandhi-piece' + (src ? ' dge-src-' + src : '');
      const tip = DGE_SANDHI_SRC_TITLE[src] || '';
      return '<span class="' + cls + '"' + (tip ? ' title="' + dgeShabdaEsc(tip) + '"' : '') +
        (src === 'v' ? ' data-sandhi-dhatu="' + dgeShabdaEsc(text) + '" role="button" tabindex="0"' : '') +
        '>' + dgeShabdaEsc(text) + '</span>';
    }
    return '<div class="dsm-sandhi-row deva">' + half(s.a, s.sa) +
      ' <span class="dge-sandhi-plus">+</span> ' + half(s.b, s.sb) + '</div>';
  }).join('');
}

// Tapping a verb half opens the Dhātu popup on it, which is the whole point of
// splitting a compound: the root was never reachable while it sat glued to a
// prefix or a preceding word.
function dgeWireSandhiDhatuTaps(box) {
  if (!box) return;
  box.querySelectorAll('[data-sandhi-dhatu]').forEach(function (el) {
    el.addEventListener('click', function () {
      const w = el.dataset.sandhiDhatu;
      const prev = window.dgeSelectedWordText;
      window.dgeSelectedWordText = function () { return w; };
      try { window.dgeOpenDhatuForSelection(null); } finally { window.dgeSelectedWordText = prev; }
    });
  });
}

function dgeSandhiRowsHtml(splits) {
  return splits.map(function (s) {
    return '<div class="dsm-sandhi-row deva">' + dgeShabdaEsc(s.first) + ' + ' + dgeShabdaEsc(s.second) +
      (s.sutra ? ' <span class="dge-sutra-ref" data-sutra="' + dgeShabdaEsc(s.sutra) + '" role="button" tabindex="0">' +
        dgeShabdaEsc(s.name) + ' · ' + dgeShabdaEsc(s.sutra) + '</span>' : '') +
      '</div>';
  }).join('');
}
function dgeSandhiFallbackHtml(word) {
  return dgeFindSandhiSplits(word).then(function (splits) {
    if (!splits || !splits.length) return null;
    return '<div class="dsm-word deva">' + dgeShabdaEsc(word) + '</div>' +
      '<div class="dsm-sub">सन्धिविच्छेदः · not in the fixed शब्दपाठः list, but the grammar engine resolves this as a sandhi join</div>' +
      dgeSandhiRowsHtml(splits) + dgeShabdaWhereElseLink(word);
  }).catch(() => null);
}

// कोश (dictionary) results, first 3 dictionaries with a "see more" link to
// the full कोश overlay for the rest -- shown alongside whichever of the
// above resolves, or alongside the not-found message, since a dictionary
// gloss is useful regardless of whether Vidyut has a grammatical parse.
function dgeKoshaPanelHtml(word) {
  if (typeof window.dgeKoshaQuick !== 'function') return Promise.resolve('');
  return window.dgeKoshaQuick(word).then(function (q) {
    if (!q || !q.perDict.length) return '';
    const shown = q.perDict.slice(0, 3);
    let h = '<div class="dsm-section-label">कोशः · Dictionaries</div>';
    shown.forEach(function (d) {
      const name = (d.meta && d.meta.name) || d.slug;
      const item0 = d.items && d.items[0];
      const sense0 = item0 && item0.senses && item0.senses[0];
      const gloss = sense0 ? String(sense0.gloss || '') : '';
      const trimmed = gloss.length > 160 ? (gloss.slice(0, 160) + '…') : gloss;
      h += '<div class="dsm-kosha-entry"><b>' + dgeShabdaEsc(name) + '</b> — ' + dgeShabdaEsc(trimmed) + '</div>';
    });
    if (q.perDict.length > shown.length) {
      h += '<button class="btn-sm dsm-kosha-more" id="dsmKoshaMore" data-word="' + dgeShabdaEsc(word) + '">See ' +
        (q.perDict.length - shown.length) + ' more कोश (' + q.perDict.length + ' total) →</button>';
    }
    return h;
  }).catch(() => '');
}

// Wires the interactive bits of whatever dgeOpenShabdaForSelection just
// wrote into `body`. Split into two (rather than one "wire everything"
// function called after each of the two separate writes below) so neither
// listener gets bound twice -- the primary content and the कोश panel land
// in the DOM at different times, dsmReportMissing only ever in the former,
// dsmKoshaMore only ever in the latter.
function dgeWireShabdaReportMissing(body, word) {
  const rep = body.querySelector('#dsmReportMissing');
  if (rep) rep.addEventListener('click', function (e) {
    e.preventDefault();
    if (typeof window.dgeReportMissingForm === 'function') window.dgeReportMissingForm(word, 'shabda-modal');
  });
}
function dgeWireShabdaKoshaMore(body) {
  const more = body.querySelector('#dsmKoshaMore');
  if (more) more.addEventListener('click', function () {
    if (typeof window.dgeOpenKosha === 'function') window.dgeOpenKosha(more.dataset.word);
  });
}

// Real bug found via live testing, 24 Aug: tapping word A then quickly
// word B (before A's slower fetch resolved) let A's response land LAST
// and silently overwrite B's already-rendered modal with A's stale data
// -- no request-generation check existed anywhere in this chain. Every
// async .then() below that touches the DOM now checks its own captured
// `myReq` against the current window.dgeShabdaReqSeq first, so only the
// MOST RECENTLY opened word's response is ever allowed to render.
window.dgeShabdaReqSeq = window.dgeShabdaReqSeq || 0;
window.dgeOpenShabdaForSelection = function(e) {
  if (e) e.preventDefault();
  const word = dgeLookupWordText();
  if (!word) { if (typeof showToast === 'function') showToast('Select a word first.'); return; }
  dgeHideActionTooltip();
  dgeEnsureShabdaModal();
  window.openModal(DGE_SHABDA_MODAL_ID);
  const myReq = ++window.dgeShabdaReqSeq;
  const body = document.getElementById('dgeShabdaModalBody');
  body.innerHTML = '<div class="dsm-loading">खोजयति… searching “' + dgeShabdaEsc(word) + '”…</div>';

  // Fallback chain, each step Promise<string|null>: the fixed शब्दपाठः
  // declension table (curated) -> a kṛdanta derivation (curated) -> Vidyut's
  // own live morphology analysis (real, but not a curated table) -> a
  // Vidyut sandhi split (real) if the word looks like an unlisted compound
  // -> a compound-final-member suffix match against the same curated
  // शब्दपाठः table (heuristic -- only the final member is identified, see
  // dgeFindShabdaCompoundMatch -- so it runs after the two genuine Vidyut
  // analyses above, only once both of those have already come up empty)
  // -> only then an honest not-found. `exactMatch`/`compoundMatch` are set
  // only by the branches that actually have a declension cell/item to
  // derive from, so the final .then() below knows whether to wire the
  // tap-a-cell-for-its-derivation behaviour once the string it built is
  // actually in the DOM.
  let exactMatch = null, compoundMatch = null;
  dgeFetchShabdaData(word).then(function (items) {
    const loc = dgeFindShabdaForm(items, word);
    if (loc) { exactMatch = loc; return dgeShabdaExactHtml(loc.item, loc.cellIndex); }
    const cp = word.codePointAt(0).toString(16).toLowerCase().padStart(4, '0');
    return fetch('data/vedanga/vyakarana/prakriya/krtindex/' + cp + '.json')
      .then(r => r.ok ? r.json() : null)
      .then(function (m) {
        // A kṛdanta spelling can belong to several roots — कृत्वा is the ktvā
        // of both 05.0007 "to injure" and 08.0010 "to do" — so the index
        // returns a list. The old single-record shape is still accepted.
        const hit = m && m[word];
        if (!hit) return null;
        const list = Array.isArray(hit) ? hit : [hit];
        if (!list.length) return null;
        return dgeRankDhatuCandidates(list).then(function (ranked) {
          return dgeShabdaKrtHtml(word, ranked[0], ranked);
        });
      })
      .catch(() => null);
  }).catch(() => null)
    .then(function (html) { return html || dgeMorphFallbackHtml(word); })
    .then(function (html) { return html || dgeSandhiFallbackHtml(word); })
    .then(function (html) {
      if (html) return html;
      return dgeFetchShabdaData().then(function (items) {
        const hit = dgeFindShabdaCompoundMatch(items, word);
        if (!hit) return null;
        compoundMatch = hit;
        return dgeShabdaCompoundHtml(word, hit);
      }).catch(() => null);
    })
    .then(function (html) { return html || dgeShabdaNotFoundHtml(word); })
    .then(function (mainHtml) {
      if (myReq !== window.dgeShabdaReqSeq) return; // a newer word was opened meanwhile -- this response is stale
      body.innerHTML = mainHtml;
      dgeWireShabdaReportMissing(body, word);
      dgeShabdaWireWhereElse(body);
      if (exactMatch) dgeWireShabdaSubantaSteps(body, exactMatch.item, exactMatch.cellIndex);
      else if (compoundMatch) dgeWireShabdaSubantaSteps(body, compoundMatch.item, compoundMatch.cellIndex);
      // कोश (dictionary results, from a separate CDN-hosted repo) loads
      // independently and appends itself once ready -- never blocks the
      // primary content above, which a reader wants to see immediately
      // even when कोश itself is slow or briefly unreachable. A hung
      // fetch there is a real possibility (CDN hiccup, offline reader),
      // not just a test artifact, so it is capped rather than left to
      // run indefinitely.
      dgeWithTimeout(dgeKoshaPanelHtml(word), 8000, '').then(function (koshaHtml) {
        if (myReq !== window.dgeShabdaReqSeq) return;
        if (!koshaHtml || !body.isConnected) return;
        body.insertAdjacentHTML('beforeend', koshaHtml);
        dgeWireShabdaKoshaMore(body);
      });
    });
};

// Dedicated Sandhi word-tool: real Vidyut split first (own modal, sutra
// citations linking through to the existing Ashtadhyayi popover/page), and
// only when Vidyut has nothing for this word does it fall back to the
// AI-based Ask Acharya Sandhi path (askAcharya's 'sandhi' type, unchanged).
//
// Named dgeOpenVidyutSandhiForSelection (not dgeOpenSandhiForSelection) so
// it can't collide with sandhi.js's window.dgeOpenSandhiForSelection --
// the live dharmamitra.org analyzer, a separate real tool wired to
// #wordToolsRow's other Sandhi button. Both used to claim the same global
// name; sandhi.js loads after this file, so its assignment silently won
// every time and this Vidyut-first path was never actually reachable.
const DGE_SANDHI_MODAL_ID = 'dgeSandhiModal';
function dgeEnsureSandhiModal() {
  dgeEnsureWordModalShell(DGE_SANDHI_MODAL_ID, 'dgeSandhiModalBody', '🔗 सन्धिः · Sandhi');
  return document.getElementById(DGE_SANDHI_MODAL_ID);
}
window.dgeOpenVidyutSandhiForSelection = function (e) {
  if (e) e.preventDefault();
  const word = dgeLookupWordText();
  if (!word) { if (typeof showToast === 'function') showToast('Select a word first.'); return; }
  dgeHideActionTooltip();
  function fallbackToAi() {
    // Captured `word` explicitly rather than trusting a re-read of the live
    // selection -- by the time this async fallback runs the browser may
    // already have cleared it (see the identical reasoning in ai.js's
    // other async selection-driven word-tools).
    window.lastSelectedText = word;
    window.askAcharya(null, 'sandhi');
  }
  function show(html) {
    dgeEnsureSandhiModal();
    window.openModal(DGE_SANDHI_MODAL_ID);
    const body = document.getElementById('dgeSandhiModalBody');
    body.innerHTML = '<div class="dsm-word deva">' + dgeShabdaEsc(word) + '</div>' + html;
    dgeWireSandhiDhatuTaps(body);
  }
  // The local index first: it is committed to the repo, so it is the one that
  // answers on a local checkout. The CDN-hosted Vidyut index (vowel sandhi
  // only, with sutra citations) is the second try, and the AI guess the last.
  dgeFindLocalSandhiSplits(word).then(function (local) {
    if (local && local.length) {
      show('<div class="dsm-sub">सन्धिविच्छेदः · rule-based, verified against this library\u2019s own word lists</div>' +
           dgeLocalSandhiRowsHtml(local));
      return;
    }
    return dgeFindSandhiSplits(word).then(function (splits) {
      if (!splits || !splits.length) { fallbackToAi(); return; }
      show('<div class="dsm-sub">सन्धिविच्छेदः · precomputed, not AI-generated</div>' +
           dgeSandhiRowsHtml(splits));
    });
  }).catch(fallbackToAi);
};

// Instant Dhātu lookup modal, same reasoning as the Śabda one above: this
// used to open dhatu.html/prakriya.html in a new tab for what is usually
// just "which root, which form is this" -- now answered in a modal without
// leaving the page, real step-by-step derivation included, not a link to
// go read it elsewhere.
//
// Which lakara/purusha/vacana cell a surface form (e.g. उवाच) belongs to
// isn't decidable client-side without scanning all ~2200 per-root prakriya
// files (262 MB total), so tools/build_prakriya_form_index.py precomputes
// a reverse index, sharded by the form's first Devanagari codepoint so a
// single word-click only fetches one small shard.
// Every root whose paradigm reaches this form, not just the first. The lead,
// 9 Sep 2026, on clicking चक्रे and getting क्रुञ् "हिंसायाम्": return "all
// matching dhatus with user-selectable options, rather than defaulting to
// himsa". चक्रे has two roots, चकार five; 26,386 of the index's 204,970 forms
// have more than one. Tolerates the old single-object shard shape so a stale
// cached shard degrades to one candidate rather than throwing.
function dgeFindDhatuFormHits(word) {
  const w = String(word || '').trim();
  if (!w) return Promise.resolve([]);
  const cp = w.codePointAt(0).toString(16).toLowerCase().padStart(4, '0');
  return fetch('data/vedanga/vyakarana/prakriya/formindex/' + cp + '.json')
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (m) {
      const hit = m && m[w];
      if (!hit) return [];
      return Array.isArray(hit) ? hit : [hit];
    })
    .catch(function () { return []; });
}

const DGE_DHATU_MODAL_ID = 'dgeDhatuModal';
// Same lakara/puruṣa/vacana naming as prakriya.js's own LAKARA/PURUSHA/
// VACANA -- duplicated rather than shared because that file's copies live
// inside its own closure and this page doesn't load prakriya.js at all
// (same reasoning as DGE_KRT_NAME above). Key order (0/1/2 for
// prathama/madhyama/uttama puruṣa) matches tools/build_prakriya.py's own
// "<lakara>.<purusha><vacana>" cell-key convention.
const DGE_LAKARA = { Lat:'लट्', Lit:'लिट्', Lut:'लुट्', Lrt:'लृट्', Lot:'लोट्', Lan:'लङ्', VidhiLin:'विधिलिङ्', Lun:'लुङ्' };
const DGE_LAKARA_EN = { Lat:'present', Lit:'perfect', Lut:'periphrastic future', Lrt:'future', Lot:'imperative', Lan:'imperfect', VidhiLin:'optative', Lun:'aorist' };
const DGE_PURUSHA = ['प्रथमपुरुषः', 'मध्यमपुरुषः', 'उत्तमपुरुषः'];
const DGE_VACANA = ['एकवचनम्', 'द्विवचनम्', 'बहुवचनम्'];

function dgeEnsureDhatuModal() {
  dgeEnsureWordModalShell(DGE_DHATU_MODAL_ID, 'dgeDhatuModalBody', '📚 धातुः · Dhātu');
  return document.getElementById(DGE_DHATU_MODAL_ID);
}

function dgeShowDhatuNotFound(body, surface) {
  body.innerHTML = '<div class="dsm-empty">No exact verb form found for "' + dgeShabdaEsc(surface) + '". ' +
    'It may still be findable in the full धातुपाठः browser — <a href="vyakarana/dhatu.html?q=' + encodeURIComponent(surface) + '" target="_blank">search धातुपाठः ↗</a>, or ' +
    '<a href="#" id="ddmReportMissing">report this as missing</a>.</div>';
  const rep = document.getElementById('ddmReportMissing');
  if (rep) rep.addEventListener('click', function (e) {
    e.preventDefault();
    if (typeof window.dgeReportMissingForm === 'function') window.dgeReportMissingForm(surface, 'dhatu-modal');
  });
}

// Full tinanta paradigm (all 8 lakāras × 3 puruṣa × 3 vacana), rendered as
// one collapsible block per lakāra -- the matched lakāra opens expanded, the
// rest are there to browse without a second lookup. Unlike the Śabda
// declension table (which needs subanta-steps.js's live WASM engine for a
// derivation, since not every form is precomputed), a root's prakriya JSON
// already carries `steps` for all 72 cells alongside `forms` -- the exact
// same fetch dgeOpenDhatuForSelection already made, just not fully used
// until now. No extra request, no build-time work.
// Which pada a form belongs to, read off its own derivation: 1.3.72 is the
// sutra that assigns आत्मनेपदम्, 1.3.78 परस्मैपदम्. Grounded in Panini rather
// than guessed from the order of the variants array, and available for all
// eight lakaras because build_prakriya.py stores steps for every one.
// null = this variant has no recorded derivation to read.
function dgeDhatuPadaOf(d, key, form) {
  const variants = (d.steps && d.steps[key]) || [];
  for (let i = 0; i < variants.length; i++) {
    if (variants[i].t !== form) continue;
    const sutras = (variants[i].s || []).map(function (x) { return x[0]; });
    if (sutras.indexOf('1.3.72') >= 0) return 'A';
    if (sutras.indexOf('1.3.78') >= 0) return 'P';
    return null;
  }
  return null;
}

// The line under the word: which pada THIS form is, not which pada the
// Dhatupatha record happens to be labelled.
//
// Found live, 10 Sep 2026: गच्छति opened with "from ग॒मॢँ 'गतौ' · गणः 1 ·
// आत्मनेपदम्" while its own derivation two lines below applied 1.3.78
// शेषात् कर्तरि परस्मैपदम् and the paradigm printed परस्मैपद endings. The
// header was reading the shipped Dhatupatha record's `pada` field, which for
// this root says आत्मनेपदम्; the engine disagrees. Rather than pick a winner
// silently, the derivation's answer for the form in hand leads (it is the one
// the tables below actually follow) and the listed one is named beside it, so
// a reader who knows the Dhatupatha reading is not left thinking we lost it.
function dgeDhatuHeaderPada(d, key, form) {
  const listed = (d && d.pada) || '';
  const derived = dgeDhatuPadaOf(d, key, form);
  if (!derived) return dgeShabdaEsc(listed);
  const name = derived === 'A' ? 'आत्मनेपदम्' : 'परस्मैपदम्';
  if (!listed || listed === name) return dgeShabdaEsc(name);
  return dgeShabdaEsc(name) +
    ' <span class="dsm-pada-listed" title="the pada this root carries in the shipped धातुपाठः, which the derivation of this form does not follow">' +
    '(धातुपाठे ' + dgeShabdaEsc(listed) + ')</span>';
}

// One table per pada when a root is उभयपदी. The lead: "visual separation or
// separate tables for Atmanepadi and Parasmaipadi forms" -- चक्रे and चकार
// sharing a cell reads as two spellings of one form, when they are the two
// padas of it. `which` is 'P', 'A', or null for the undifferentiated table a
// single-pada root gets (and for any variant whose pada we cannot read).
function dgeDhatuLakaraTable(d, lk, hlKey, which) {
  let t = '<table class="dsm-table"><thead><tr><th></th><th class="deva">एक.</th><th class="deva">द्वि.</th><th class="deva">बहु.</th></tr></thead><tbody>';
  for (let p = 0; p < 3; p++) {
    t += '<tr><th class="deva">' + DGE_PURUSHA[p] + '</th>';
    for (let v = 0; v < 3; v++) {
      const key = lk + '.' + p + v;
      let forms = (d.forms && d.forms[key]) || [];
      if (which) {
        forms = forms.filter(function (f) {
          const pada = dgeDhatuPadaOf(d, key, f);
          return pada === which || pada === null;
        });
      }
      const hl = (key === hlKey);
      const has = forms.length > 0;
      t += '<td class="deva' + (hl ? ' dsm-hl' : '') + (has ? ' sst-cell-hint' : '') + '"' +
        (has ? ' data-dk="' + dgeShabdaEsc(key) + '" title="रूपसिद्धिः — tap for the derivation"' : '') + '>' +
        dgeShabdaEsc(forms.join(', ')) + '</td>';
    }
    t += '</tr>';
  }
  return t + '</tbody></table>';
}

function dgeDhatuFormsHtml(d, hlKey) {
  const lakaras = ['Lat', 'Lit', 'Lut', 'Lrt', 'Lot', 'Lan', 'VidhiLin', 'Lun'];
  const hlLakara = hlKey ? hlKey.split('.')[0] : null;
  return lakaras.map(function (lk) {
    // Split only where this lakara actually carries both padas -- a purely
    // parasmaipadi root gets the single table it has always had.
    const padas = {};
    for (let p = 0; p < 3; p++) {
      for (let v = 0; v < 3; v++) {
        const key = lk + '.' + p + v;
        ((d.forms && d.forms[key]) || []).forEach(function (f) {
          const x = dgeDhatuPadaOf(d, key, f);
          if (x) padas[x] = true;
        });
      }
    }
    const both = padas.P && padas.A;
    const body = both
      ? '<div class="dsm-pada-label deva">परस्मैपदम्</div>' + dgeDhatuLakaraTable(d, lk, hlKey, 'P') +
        '<div class="dsm-pada-label deva">आत्मनेपदम्</div>' + dgeDhatuLakaraTable(d, lk, hlKey, 'A')
      : dgeDhatuLakaraTable(d, lk, hlKey, null);
    return '<details class="dsm-lakara-block"' + (lk === hlLakara ? ' open' : '') + '>' +
      '<summary class="deva">' + dgeShabdaEsc(DGE_LAKARA[lk]) + ' <span class="dsm-lakara-en">· ' + dgeShabdaEsc(DGE_LAKARA_EN[lk]) + '</span></summary>' +
      body + '</details>';
  }).join('');
}

function dgeDhatuStepsFor(body, d, key) {
  const box = body.querySelector('#ddmSteps');
  if (!box) return;
  body.querySelectorAll('td.sst-cell-on').forEach(function (td) { td.classList.remove('sst-cell-on'); });
  const cell = body.querySelector('td[data-dk="' + key + '"]');
  if (cell) cell.classList.add('sst-cell-on');
  const variants = (d.steps && d.steps[key]) || [];
  if (!variants.length) { box.innerHTML = ''; return; }
  box.innerHTML = '<div class="dsm-section-label">रूपसिद्धिः · Derivation</div>' + variants.map(function (v) {
    return '<div class="dsm-word deva" style="font-size:15px;">' + dgeShabdaEsc(v.t) + '</div>' + dgeShabdaStepsHtml(v.s);
  }).join('<hr style="border:none;border-top:1px dashed var(--card-border);margin:10px 0;">');
}

// Wires tap-any-cell-for-its-derivation across the whole paradigm, not just
// the originally matched cell -- every cell's steps are already sitting in
// `d.steps`, so there is no async engine call here at all, unlike the Śabda
// table's subanta-steps.js.
function dgeWireDhatuFormsTable(body, d, initialKey) {
  dgeDhatuStepsFor(body, d, initialKey);
  body.querySelectorAll('td[data-dk]').forEach(function (td) {
    td.addEventListener('click', function () {
      dgeDhatuStepsFor(body, d, td.dataset.dk);
      const box = body.querySelector('#ddmSteps');
      if (box && box.scrollIntoView) box.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    });
  });
}

// AI (Gemini) multilingual meanings + pedagogical usage notes, from
// tools/gemini_dhatu_lexicon.py -- independently composed content, not
// copied from ashtadhyayi.com or any other source (see that script's own
// docstring and PENDING.md's 23 Aug entry for why this exists).
// Loaded independently of the primary paradigm render and appended if/when
// ready, same reasoning as dgeKoshaPanelHtml above: this file can grow to
// several MB across the whole Dhatupatha, so it must never be allowed to
// stall the modal's already-ready primary content.
let DGE_DHATU_LEXICON_CACHE = null;
function dgeFetchDhatuLexicon() {
  if (!DGE_DHATU_LEXICON_CACHE) {
    DGE_DHATU_LEXICON_CACHE = fetch('data/vedanga/vyakarana/dhatu_lexicon/data.json', { cache: 'force-cache' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        const byId = {};
        (d && d.items || []).forEach(function (it) { byId[it.id] = it; });
        return byId;
      })
      .catch(function () { return null; });
  }
  return DGE_DHATU_LEXICON_CACHE;
}
const DGE_LEXICON_LANGS = ['English', 'Kannada', 'Telugu', 'Tamil', 'Malayalam', 'Hindi',
  'Bengali', 'German', 'French', 'Russian', 'Chinese'];
function dgeDhatuLexiconHtml(entry) {
  if (!entry) return '';
  const m = entry.meanings || {};
  const rows = DGE_LEXICON_LANGS.filter(function (l) { return m[l] && m[l] !== '(uncertain)'; })
    .map(function (l) {
      return '<div class="dsm-lex-row"><b>' + dgeShabdaEsc(l) + '</b><span>' + dgeShabdaEsc(m[l]) + '</span></div>';
    }).join('');
  if (!rows) return '';
  const sources = entry.sources_used || [];
  const tag = sources.length ? 'AI-interpreted (Gemini), grounded in real sources below' : 'AI-generated (Gemini), unreviewed';
  let h = '<div class="dsm-section-label">बहुभाषा अर्थाः · Multilingual Meanings' +
    '<span class="dsm-ai-tag">' + dgeShabdaEsc(tag) + '</span></div>' +
    '<div class="dsm-lex-langs">' + rows + '</div>';
  const ped = entry.pedagogy;
  if (ped && (ped.concept || (ped.scenarios || []).length)) {
    h += '<div class="dsm-lex-pedagogy">' + (ped.concept ? '<p>' + dgeShabdaEsc(ped.concept) + '</p>' : '');
    (ped.scenarios || []).forEach(function (s) {
      h += '<div class="dsm-lex-scenario"><b class="deva">' + dgeShabdaEsc(s.form) + '</b>' +
        (s.grammar_trigger ? ' <span style="color:var(--muted-text);">(' + dgeShabdaEsc(s.grammar_trigger) + ')</span>' : '') +
        ' — ' + dgeShabdaEsc(s.meaning) +
        (s.example_sanskrit ? '<div class="dsm-lex-example deva">' + dgeShabdaEsc(s.example_sanskrit) + '</div>' : '') +
        (s.example_english ? '<div class="dsm-lex-example-en">' + dgeShabdaEsc(s.example_english) + '</div>' : '') +
        '</div>';
    });
    h += '</div>';
  }
  if (sources.length) {
    h += '<div style="font-size:11px;color:var(--muted-text);margin-top:8px;line-height:1.5;">grounded in: ' +
      sources.map(dgeShabdaEsc).join(' · ') + '</div>';
  }
  return h;
}

// Same stale-response guard as dgeOpenShabdaForSelection above, and for
// the same real reason: no request-generation check existed here either.
window.dgeDhatuReqSeq = window.dgeDhatuReqSeq || 0;
window.dgeOpenDhatuForSelection = function(e) {
  if (e) e.preventDefault();
  const word = dgeLookupWordText();
  if (!word) { if (typeof showToast === 'function') showToast('Select a word first.'); return; }
  dgeHideActionTooltip();
  dgeEnsureDhatuModal();
  window.openModal(DGE_DHATU_MODAL_ID);
  const myReq = ++window.dgeDhatuReqSeq;
  const body = document.getElementById('dgeDhatuModalBody');
  body.innerHTML = '<div class="dsm-loading">खोजयति… searching “' + dgeShabdaEsc(word) + '”…</div>';

  dgeFindDhatuFormHits(word).then(function (hits) {
    if (myReq !== window.dgeDhatuReqSeq) return; // a newer word was opened meanwhile
    if (!hits.length) {
      // Nothing matched the written form, so try peeling an upasarga off it.
      // The Dhatupatha stores bare roots -- गम् is indexed, समागच्छति is not
      // -- so a prefixed verb is invisible to a direct lookup no matter how
      // complete the index is. See js/vyakarana-runtime.js.
      if (typeof window.dgePeelUpasarga === 'function') {
        window.dgePeelUpasarga(word).then(function (peels) {
          if (myReq !== window.dgeDhatuReqSeq) return;
          if (!peels.length) { dgeShowDhatuNotFound(body, word); return; }
          dgeRenderDhatuPeeled(body, word, peels, 0, myReq);
        });
        return;
      }
      dgeShowDhatuNotFound(body, word);
      return;
    }
    // Which candidate opens FIRST is the whole of the lead's original report
    // ("clicking cakre should return all matching dhatus … rather than
    // defaulting to himsa"): the chips have offered every root since 8 Sep,
    // but the one shown on arrival was whichever the index happened to list
    // first. Now it is the root this library actually attests most.
    // The chips and the panel MUST share one array: they address each other by
    // index, and ranking one but not the other means a chip opens a different
    // root than it names.
    dgeRankDhatuCandidates(hits).then(function (ranked) {
      if (myReq !== window.dgeDhatuReqSeq) return;
      dgeRenderDhatuCandidate(body, word, ranked, 0, myReq);
      // Chips render immediately with codes and relabel themselves with each
      // root's name and meaning as soon as the list arrives -- the paradigm the
      // reader came for is never held up waiting on it.
      if (ranked.length > 1) {
        dgeFetchDhatuListByCode().then(function () {
          if (myReq !== window.dgeDhatuReqSeq) return;
          const box = body.querySelector('.dsm-cands');
          if (!box) return;
          const on = box.querySelector('.dsm-cand.on');
          const idx = on ? parseInt(on.dataset.dhatuCand, 10) : 0;
          box.outerHTML = dgeDhatuCandidateChipsHtml(ranked, idx);
          body.querySelectorAll('[data-dhatu-cand]').forEach(function (btn) {
            btn.addEventListener('click', function () {
              dgeRenderDhatuCandidate(body, word, ranked, parseInt(btn.dataset.dhatuCand, 10), myReq);
            });
          });
        });
      }
    });
  });
};

// Renders one candidate root and, above it, the row of roots to switch
// between. Each chip carries the root's own अर्थ, which is the whole point:
// क्रुञ् "हिंसायाम्" and डुकृञ् "करणे" both yield चक्रे, and only the meaning
// tells a reader which one their sentence means.
function dgeRenderDhatuCandidate(body, word, hits, index, myReq, opts) {
  opts = opts || {};
  const hit = hits[index];
  const rootPart = hit.c.split('.')[0];
  fetch('data/vedanga/vyakarana/prakriya/' + rootPart + '/' + hit.c + '.json')
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (d) {
      if (myReq !== window.dgeDhatuReqSeq) return;
      const step = d && d.steps && d.steps[hit.k] && d.steps[hit.k][0];
      if (!d || !step) { dgeShowDhatuNotFound(body, word); return; }
      body.innerHTML =
        '<div class="dsm-word deva">' + dgeShabdaEsc(opts.heading || word) + '</div>' +
        (opts.beforeSub || '') +
        dgeDhatuCandidateChipsHtml(hits, index) +
        '<div class="dsm-sub">from <span class="deva">' + dgeShabdaEsc(d.dhatu) + '</span> "' + dgeShabdaEsc(d.artha || '') + '" · गणः ' + dgeShabdaEsc(d.gana != null ? d.gana : '') + ' · ' + dgeDhatuHeaderPada(d, hit.k, word) + '</div>' +
        '<div id="ddmUpasargaArtha"></div>' +
        dgeDhatuFormsHtml(d, hit.k) +
        '<div id="ddmSteps"></div>' +
        '<a class="dsm-full-link" href="vyakarana/prakriya.html#' + dgeShabdaEsc(hit.c) + ':' + dgeShabdaEsc(hit.k) + '" target="_blank">View in full प्रक्रिया browser ↗</a>' +
        '<div id="ddmLexicon"></div>';
      if (opts.upasarga && typeof window.dgeUpasargaArtha === 'function') {
        window.dgeUpasargaArtha(hit.c, opts.upasarga).then(function (a) {
          if (myReq !== window.dgeDhatuReqSeq || !a) return;
          const box = body.querySelector('#ddmUpasargaArtha');
          if (!box || !box.isConnected) return;
          box.innerHTML = '<div class="dge-upasarga-artha"><span class="deva">' +
            dgeShabdaEsc(a.upasarga) + ' + ' + dgeShabdaEsc(d.dhatu) + '</span> — ' +
            dgeShabdaEsc(a.artha) + '</div>';
        });
      }
      if (typeof opts.onReady === 'function') opts.onReady(body);
      body.querySelectorAll('[data-dhatu-cand]').forEach(function (btn) {
        btn.addEventListener('click', function () {
          dgeRenderDhatuCandidate(body, word, hits, parseInt(btn.dataset.dhatuCand, 10), myReq);
        });
      });
      dgeWireDhatuFormsTable(body, d, hit.k);
      dgeWithTimeout(dgeFetchDhatuLexicon(), 8000, null).then(function (byId) {
        if (myReq !== window.dgeDhatuReqSeq) return;
        const lexHtml = dgeDhatuLexiconHtml(byId && byId[hit.c]);
        const box = body.querySelector('#ddmLexicon');
        if (!lexHtml || !box || !box.isConnected) return;
        box.outerHTML = '<div>' + lexHtml + '</div>';
      });
    })
    .catch(function () { if (myReq === window.dgeDhatuReqSeq) dgeShowDhatuNotFound(body, word); });
}

// A prefixed verb: the popup shows what was peeled off, the bare root's own
// paradigm, and -- the part that matters -- the meaning THIS upasarga gives
// THIS root. सम् + गम् is not "to go", it is "to unite", and showing the bare
// gloss beside समागच्छति would be quietly wrong.
function dgeRenderDhatuPeeled(body, word, peels, index, myReq) {
  var peel = peels[index];
  var hits = peel.roots;
  var chips = peels.length < 2 ? '' :
    '<div class="dsm-cands"><div class="dsm-cands-note">' + peels.length +
    ' ways to read this prefix — tap to compare</div>' +
    peels.map(function (p, i) {
      return '<button type="button" class="dsm-cand deva' + (i === index ? ' on' : '') +
        '" data-dhatu-peel="' + i + '">' + dgeShabdaEsc(p.upasarga + ' + ' + p.rest) + '</button>';
    }).join('') + '</div>';

  dgeRenderDhatuCandidate(body, peel.rest, hits, 0, myReq, {
    heading: word,
    beforeSub: chips +
      '<div class="dge-upasarga-row">' +
      '<span class="dge-upasarga deva">' + dgeShabdaEsc(peel.upasarga) + '</span>' +
      '<span class="dge-sandhi-plus">+</span>' +
      '<span class="dge-sandhi-piece dge-src-v deva">' + dgeShabdaEsc(peel.rest) + '</span>' +
      (peel.sutra ? '<span class="dge-sutra-ref" data-sutra="' + dgeShabdaEsc(peel.sutra) +
        '" role="button" tabindex="0">' + dgeShabdaEsc(peel.rule) + ' · ' + dgeShabdaEsc(peel.sutra) + '</span>'
        : '<span class="dsm-muted">' + dgeShabdaEsc(peel.rule) + '</span>') +
      '</div>',
    upasarga: peel.upasarga,
    onReady: function (el) {
      el.querySelectorAll('[data-dhatu-peel]').forEach(function (btn) {
        btn.addEventListener('click', function () {
          dgeRenderDhatuPeeled(body, word, peels, parseInt(btn.dataset.dhatuPeel, 10), myReq);
        });
      });
    }
  });
}

// The Dhatupatha list, once per page, keyed by code -- so a chip can name its
// root (डुकृञ् · करणे) without fetching that root's own 30-120 KB paradigm
// file just to read two fields off it.
let DGE_DHATU_LIST_PROMISE = null;
function dgeFetchDhatuListByCode() {
  if (!DGE_DHATU_LIST_PROMISE) {
    DGE_DHATU_LIST_PROMISE = fetch('data/vedanga/vyakarana/dhatupatha/data.json', { cache: 'force-cache' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        const by = {};
        ((d && d.items) || []).forEach(function (it) { if (it && it.id) by[it.id] = it; });
        window.DGE_DHATU_LIST_BY_CODE = by;
        return by;
      })
      .catch(function () { return {}; });
  }
  return DGE_DHATU_LIST_PROMISE;
}

// Chips are drawn only when there is a real choice; one root renders exactly
// as before. Labels come from the already-fetched dhatupatha list so a chip
// can name its root before that root's own file is loaded.
function dgeDhatuCandidateChipsHtml(hits, index) {
  if (hits.length < 2) return '';
  const meta = window.DGE_DHATU_LIST_BY_CODE || {};
  return '<div class="dsm-cands"><div class="dsm-cands-note">' + hits.length +
    ' roots produce this form — tap to compare</div>' +
    hits.map(function (h, i) {
      const m = meta[h.c] || {};
      const label = m.dhatu ? m.dhatu + (m.artha ? ' · ' + m.artha : '') : h.c;
      return '<button type="button" class="dsm-cand deva' + (i === index ? ' on' : '') +
        '" data-dhatu-cand="' + i + '">' + dgeShabdaEsc(label) + '</button>';
    }).join('') + '</div>';
}

// "Intelligence mapping" -- where else the word appears in the corpus
// (including which section, e.g. Vedanga), reusing the same corpus-wide
// search dhatu.js's own "corpus occurrences" button already opens rather
// than building a second index that would drift from it.
window.dgeOpenCorpusSearchForSelection = function(e) {
  if (e) e.preventDefault();
  const word = dgeLookupWordText();
  if (!word) { if (typeof showToast === 'function') showToast('Select a word first.'); return; }
  dgeHideActionTooltip();
  if (typeof window.DGEGlobalSearch === 'object' && window.DGEGlobalSearch.open) window.DGEGlobalSearch.open(word);
};
