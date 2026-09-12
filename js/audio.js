// DGE Module: audio.js
// js/audio.js
// Maps to F-004 (Audio Engine) & F-013 (Offline Cache)
window.DGE_VERSIONS = window.DGE_VERSIONS || {};
window.DGE_VERSIONS['audio.js'] = 'v3.2 (read-along highlight and swipe/long-press live on the active list card; the separate reading card is gone. v3.1: Speed memory, resume, progress, swipe nav, long-press word lookup, zero-padded filenames)';

function formatTime(s) { 
  if (isNaN(s)) return "0:00.000"; 
  const m = Math.floor(s/60), sec = Math.floor(s%60), ms = Math.floor((s%1)*1000); 
  return m + ":" + (sec<10?"0":"") + sec + "." + String(ms).padStart(3,'0'); 
}

function updateRepeatDisplay() { 
  const repeatInput = document.getElementById('repeatInput');
  const repeatCounter = document.getElementById('repeatCounter');
  if (!repeatInput || !repeatCounter) return;
  
  const t = parseInt(repeatInput.value) || 1; 
  repeatCounter.innerText = (activeId && t > 1) ? `Loop ${currentLoopCount + 1}/${t}` : ""; 
}

function updatePlayUI() {
  const playBtn = document.getElementById('playBtn');
  if (playBtn) playBtn.innerHTML = isPlaying ? '⏸' : '▶';
  // 7 Sep 2026: no separate reading card any more -- the active verse's own
  // list card carries the playing state (main.css .shloka-card.playing).
  document.querySelectorAll('.shloka-card.playing').forEach(c => { if (!isPlaying || c.id !== `shloka-${activeId}`) c.classList.remove('playing'); });
  if (activeId && isPlaying) { const ac = document.getElementById(`shloka-${activeId}`); if (ac) ac.classList.add('playing'); }
  dgeUpdateBottomPlayerVisibility();
}

// Gates .bottom-player on reader-state.js's AudioState (dgeAudioState(),
// see dge/js/reader-state.js) instead of letting it render unconditionally.
// Per the second reviewer's critique (DGE_UI_CONTRACT.md): no audio ->
// nothing shown; the player only appears once the reader has *explicitly*
// pressed Play. loadShloka() (mere navigation/selection) puts the engine in
// 'loaded' status without ever calling .play() — that alone must NOT show
// the player, so 'loaded' is deliberately grouped with 'idle' here, not
// with the "something is actually happening" states.
function dgeUpdateBottomPlayerVisibility() {
  const player = document.querySelector('.bottom-player');
  if (!player) return;
  const st = (typeof window.dgeAudioState === 'function') ? window.dgeAudioState() : null;
  const active = !!st && st.status !== 'idle' && st.status !== 'loaded';
  player.classList.toggle('dge-audio-active', active);
}
window.dgeUpdateBottomPlayerVisibility = dgeUpdateBottomPlayerVisibility;

// Configurable Audio Source: swaps the shared host prefix stored in
// stotraData.metadata.archiveBaseUrl for whatever's currently effective
// (end-user override, then super-admin config, then the hardcoded
// default) — see dgeApplyAudioBaseUrlOverride in config.js. Every
// per-grantha identifier/folder after that prefix is untouched.
function dgeEffectiveArchiveBase() {
  const raw = stotraData.metadata.archiveBaseUrl;
  return (typeof window.dgeApplyAudioBaseUrlOverride === 'function') ? window.dgeApplyAudioBaseUrlOverride(raw) : raw;
}

// Zero-pads the shloka number in audio filenames when a grantha opts in via
// stotraData.metadata.fileNumberWidth (e.g. 2 -> "01", "02", ... "55").
// Absent/0 leaves ids unpadded, preserving existing works' filenames as-is.
function dgeAudioFileId(id) {
  const width = stotraData && stotraData.metadata && stotraData.metadata.fileNumberWidth;
  return width ? String(id).padStart(width, '0') : String(id);
}

async function resolveAudioSrc(id) {
  if (!stotraData || !stotraData.metadata) return "";

  const base = dgeEffectiveArchiveBase();
  const fid = dgeAudioFileId(id);
  const primary = `${base}${stotraData.metadata.filePrefix}${fid}${stotraData.metadata.fileExtension}`;
  const alt = `${base}${stotraData.metadata.filePrefix}${fid}%E2%80%8B${stotraData.metadata.fileExtension}`;
  
  if ('caches' in window) {
    try {
      const cache = await caches.open(AUDIO_CACHE_NAME);
      const hit = (await cache.match(primary)) || (await cache.match(alt));
      if (hit) { 
        const blob = await hit.blob(); 
        return URL.createObjectURL(blob); 
      }
    } catch (e) {
      console.warn("Offline cache read error:", e);
    }
  }
  return primary;
}

// Fills the thin progress bar under the N/total label — a quick visual
// sense of how far through the stotra the current verse is.
function dgeUpdateProgressIndicator(id, total) {
  const fill = document.getElementById('verseProgressFill');
  if (!fill || !total) return;
  const pct = Math.max(0, Math.min(100, (id / total) * 100));
  fill.style.width = pct + '%';
}
window.dgeUpdateProgressIndicator = dgeUpdateProgressIndicator;

// On load, points the track label / progress bar at the last-played verse
// WITHOUT auto-playing audio —
// autoplay is broadly blocked by browsers anyway, and starting sound
// unexpectedly on load is poor manners even where it isn't. This just
// picks up the reading experience where it left off; tapping play then
// starts that same verse normally.
function dgeRestoreLastVerse() {
  if (!stotraData || activeId) return; // don't override an explicit selection
  const key = typeof nsKey === 'function' ? nsKey('lastVerse') : null;
  if (!key) return;
  const saved = parseInt(localStorage.getItem(key), 10);
  if (!saved || !stotraData.shlokas || !stotraData.shlokas[saved]) return;

  contextShlokaId = saved;
  const total = stotraData.metadata.totalShlokas || Object.keys(stotraData.shlokas).length;
  const trackLabel = document.getElementById('trackLabel');
  if (trackLabel) trackLabel.innerText = `${saved}/${total}`;
  dgeUpdateProgressIndicator(saved, total);
}
// Long-press a word in a verse card (#shlokaList .shloka-text) to select it
// and go straight to Word-level Ask Acharya analysis, without needing to
// manually drag-select on a touchscreen. (Until 7 Sep 2026 this was bound
// to the separate reading card, since removed.) Cancels itself if the finger moves (treating it as a
// scroll/selection-drag instead) or lifts before the hold threshold.
(function dgeSetupLongPressWordLookup() {
  let pressTimer = null;
  let startX = 0, startY = 0;
  const MOVE_THRESHOLD = 10;
  const PRESS_MS = 550;

  function getWordRangeAtPoint(x, y) {
    let range = null;
    if (document.caretRangeFromPoint) {
      range = document.caretRangeFromPoint(x, y);
    } else if (document.caretPositionFromPoint) {
      const pos = document.caretPositionFromPoint(x, y);
      if (pos) {
        range = document.createRange();
        range.setStart(pos.offsetNode, pos.offset);
        range.setEnd(pos.offsetNode, pos.offset);
      }
    }
    if (!range || !range.startContainer || range.startContainer.nodeType !== 3) return null;

    const textNode = range.startContainer;
    const text = textNode.textContent;
    let start = range.startOffset, end = range.startOffset;
    const isWordChar = (ch) => !!ch && /[^\s.,;:!?()'"।॥]/.test(ch);

    while (start > 0 && isWordChar(text[start - 1])) start--;
    while (end < text.length && isWordChar(text[end])) end++;
    if (start === end) return null;

    const wordRange = document.createRange();
    wordRange.setStart(textNode, start);
    wordRange.setEnd(textNode, end);
    return wordRange;
  }

  document.addEventListener('DOMContentLoaded', () => {
    const card = document.getElementById('shlokaList');
    if (!card) return;

    card.addEventListener('touchstart', (e) => {
      if (!e.touches || !e.touches.length) return;
      if (!(e.target && e.target.closest && e.target.closest('.shloka-text'))) return;
      startX = e.touches[0].clientX;
      startY = e.touches[0].clientY;
      const touchX = startX, touchY = startY;
      pressTimer = setTimeout(() => {
        pressTimer = null;
        const wordRange = getWordRangeAtPoint(touchX, touchY);
        if (!wordRange) return;
        const sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(wordRange);
        if (navigator.vibrate) navigator.vibrate(15);
        window.lastSelectedText = wordRange.toString().trim();
        if (typeof askAcharya === 'function') askAcharya(null, 'grammar');
      }, PRESS_MS);
    }, { passive: true });

    const cancelPress = (e) => {
      if (!pressTimer) return;
      if (e.touches && e.touches.length) {
        const dx = Math.abs(e.touches[0].clientX - startX);
        const dy = Math.abs(e.touches[0].clientY - startY);
        if (dx <= MOVE_THRESHOLD && dy <= MOVE_THRESHOLD) return;
      }
      clearTimeout(pressTimer);
      pressTimer = null;
    };
    card.addEventListener('touchmove', cancelPress, { passive: true });
    card.addEventListener('touchend', () => { if (pressTimer) { clearTimeout(pressTimer); pressTimer = null; } }, { passive: true });
    card.addEventListener('touchcancel', () => { if (pressTimer) { clearTimeout(pressTimer); pressTimer = null; } }, { passive: true });
  });
})();

window.dgeRestoreLastVerse = dgeRestoreLastVerse;

// Swipe left/right on the ACTIVE verse card to go to the next/previous
// verse. Scoped to that one card (not the whole list) so it never fights
// with normal list scrolling. (Until 7 Sep 2026: the separate reading card.) Distinguishes a real swipe from a text-selection
// drag by requiring a reasonably fast, mostly-horizontal gesture — a
// slow drag (typical of selecting text) won't cross the speed threshold.
(function dgeSetupSwipeNav() {
  let touchStartX = 0, touchStartY = 0, touchStartTime = 0;

  document.addEventListener('DOMContentLoaded', () => {
    const card = document.getElementById('shlokaList');
    if (!card) return;

    card.addEventListener('touchstart', (e) => {
      if (!e.touches || !e.touches.length) return;
      touchStartTime = 0;
      if (!(e.target && e.target.closest && e.target.closest('.shloka-card.active'))) return;
      touchStartX = e.touches[0].clientX;
      touchStartY = e.touches[0].clientY;
      touchStartTime = Date.now();
    }, { passive: true });

    card.addEventListener('touchend', (e) => {
      if (!e.changedTouches || !e.changedTouches.length || !touchStartTime) return;
      const dx = e.changedTouches[0].clientX - touchStartX;
      const dy = e.changedTouches[0].clientY - touchStartY;
      const dt = Date.now() - touchStartTime;

      const isHorizontalEnough = Math.abs(dx) > Math.abs(dy) * 1.5;
      const isFarEnough = Math.abs(dx) > 60;
      const isFastEnough = dt < 500;

      if (isHorizontalEnough && isFarEnough && isFastEnough) {
        if (window.getSelection && window.getSelection().toString().length > 0) return; // don't hijack a selection
        if (dx < 0 && typeof playNextFiltered === 'function') playNextFiltered();
        else if (dx > 0 && typeof playPrevFiltered === 'function') playPrevFiltered();
      }
    }, { passive: true });
  });
})();

// Selects a shloka as the active track — updates activeId, the reading
// card, the track counter, scroll position and history — without ever
// starting playback. This is what clicking a shloka's text or landing on
// one via a filter should do: bring it into view and make it the track
// Play would act on next, nothing more. Split out of playShloka() so
// "select" and "start audio" are two different calls a caller can make on
// purpose, rather than always both happening together — clicking a
// shloka's text or applying a mark/range filter used to call playShloka()
// directly and start audio as an unwanted side effect of just looking at
// or filtering the text.
async function loadShloka(id) {
  if (!stotraData) return;
  // `.shloka-text`'s onclick calls this on EVERY tap inside it, including a
  // tap that only meant to select a WORD for the Genie (selection-modes.js's
  // 'word' tap-mode) -- re-tapping within the shloka that is ALREADY active
  // used to still run the full renderList() rebuild + a smooth scrollIntoView
  // every single time, even though nothing about which shloka is active
  // actually changed. Reported live and reproduced with Playwright: on a
  // real device, a 2nd/3rd word-tap in quick succession landed while that
  // smooth-scroll animation (or the DOM the previous rebuild just replaced)
  // was still settling, so selection-modes.js's captured tap coordinates
  // (needed to re-locate the tapped word via document.elementFromPoint after
  // its own deferred setTimeout(0) -- see that file's own comment) resolved
  // to the surrounding .shloka-text container instead of the .dge-word span,
  // silently failing to create a selection at all -- read by ai.js's
  // selectionchange handler as "selection cleared," closing the Genie sheet
  // it had just opened. Skipping the rebuild+scroll when `id` is already
  // `activeId` removes the instability at its source for the overwhelmingly
  // common case (selecting a second word, or the same word again, within the
  // verse already on screen) without touching what a genuine chapter/verse
  // SWITCH does.
  const alreadyActive = activeId === id;

  activeId = id;
  contextShlokaId = id;
  currentLoopCount = 0;
  audioRetryDone = false;
  // Selection alone never requests playback (see the error-retry comment).
  window.dgePlayRequested = false;

  if (typeof nsKey === 'function') localStorage.setItem(nsKey('lastVerse'), String(id));
  if (typeof dgeLogReadingHistory === 'function') dgeLogReadingHistory(id);
  if (typeof window.dgeSyncUrl === 'function') window.dgeSyncUrl(id);

  updateRepeatDisplay();
  if (!alreadyActive) {
    // Paged list view (render.js): turn to the page that holds this verse
    // first, or the card would not exist to scroll to (quick jump, search
    // hit, audio auto-advance across a page boundary).
    if (typeof window.dgeListPageFor === 'function') {
      const pg = window.dgeListPageFor(id);
      if (pg >= 0) window.dgeListPage = pg;
    }
    if (typeof renderList === 'function') renderList();

    const ac = document.getElementById(`shloka-${id}`);
    if (ac) ac.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  const total = stotraData.metadata.totalShlokas || Object.keys(stotraData.shlokas).length;
  const trackLabel = document.getElementById('trackLabel');
  const timeDisplay = document.getElementById('timeDisplay');

  if (trackLabel) trackLabel.innerText = `${id}/${total}`;
  if (typeof dgeUpdateProgressIndicator === 'function') dgeUpdateProgressIndicator(id, total);
  if (typeof wrapReadingCardWordsForSync === 'function') wrapReadingCardWordsForSync(id);
  if (timeDisplay) timeDisplay.innerText = "0:00.000 / 0:00.000";

  currentAudio.src = await resolveAudioSrc(id);

  const speedInput = document.getElementById('speedInput');
  currentAudio.playbackRate = speedInput ? (parseFloat(speedInput.value) || 1.0) : 1.0;

  const loopA = document.getElementById('loopA');
  const loopB = document.getElementById('loopB');
  const enableAB = document.getElementById('enableAB');

  if (loopA) loopA.value = "";
  if (loopB) loopB.value = "";
  if (enableAB) enableAB.checked = false;
}
window.loadShloka = loadShloka;

async function playShloka(id) {
  if (!stotraData) return;
  if (activeId === id && isPlaying) {
    currentAudio.pause();
    return;
  }
  await loadShloka(id);
  window.dgePlayRequested = true;
  currentAudio.play().catch(err => {
    if(err.name !== 'AbortError') console.error("Playback error:", err);
  });
  // Show the player the instant Play is actually pressed (currentAudio.play()
  // sets .paused=false synchronously, before the 'playing' event and before
  // its own promise settles) rather than waiting on that event -- on a slow
  // connection, or one that never fires because playback ultimately errors
  // out, waiting for 'playing' could mean an explicit Play never shows
  // anything at all. See dgeUpdateBottomPlayerVisibility()'s doc comment.
  dgeUpdateBottomPlayerVisibility();
}

function togglePlay() {
  if (!stotraData) return;
  
  if (!activeId) {
    const aIds = typeof getFilteredIds === 'function' ? getFilteredIds() : [];
    // Prefer whatever shloka is actually on screen (single-view Prev/Next,
    // or a TOC jump, tracked separately in window.currentReadingId) over
    // always the first filtered id — pressing Play with nothing yet
    // selected should start the verse the reader is looking at, not
    // silently jump back to the top of the filtered list.
    const startId = (aIds.includes(window.currentReadingId) ? window.currentReadingId : null) || aIds[0];
    if (startId) playShloka(startId);
  }
  else if (isPlaying) {
    currentAudio.pause();
    
    const autoABToggle = document.getElementById('autoABToggle');
    const loopA = document.getElementById('loopA');
    const loopB = document.getElementById('loopB');
    const enableAB = document.getElementById('enableAB');
    
    if (autoABToggle && autoABToggle.checked && loopA && loopB && enableAB) {
      const curr = currentAudio.currentTime.toFixed(1);
      if (!loopA.value) { 
        loopA.value = curr; 
      }
      else if (!loopB.value) { 
        loopB.value = curr; 
        enableAB.checked = true;
        currentAudio.currentTime = parseFloat(loopA.value);
        currentAudio.play();
        dgeUpdateBottomPlayerVisibility();
      }
      else { 
        loopA.value = ""; 
        loopB.value = ""; 
        enableAB.checked = false; 
      }
    }
  } else {
    window.dgePlayRequested = true;
    currentAudio.play();
    dgeUpdateBottomPlayerVisibility(); // see playShloka()'s comment on why this can't just wait for 'playing'
  }
}

function playNextFiltered() { 
  const ids = typeof getFilteredIds === 'function' ? getFilteredIds() : []; 
  if (!ids.length) return; 
  
  const idx = ids.indexOf(activeId); 
  if (idx !== -1 && idx < ids.length - 1) {
    playShloka(ids[idx + 1]); 
  } else { 
    currentAudio.pause(); 
    const repeatCounter = document.getElementById('repeatCounter');
    if (repeatCounter) repeatCounter.innerText = ""; 
  } 
}

function playPrevFiltered() { 
  const ids = typeof getFilteredIds === 'function' ? getFilteredIds() : []; 
  if (!ids.length) return; 
  
  const idx = ids.indexOf(activeId); 
  if (idx > 0) playShloka(ids[idx - 1]); 
  else playShloka(ids[ids.length - 1]); 
}

async function cacheAllAudio(btn) {
  if (!stotraData || btn.dataset.cached === "true") return;
  if (!('caches' in window)) { 
    alert('This browser does not support offline caching.'); 
    return; 
  }

  btn.innerText = "⏳ Preloading 0%"; 
  btn.disabled = true;
  
  const total = stotraData.metadata.totalShlokas || Object.keys(stotraData.shlokas).length;
  const cache = await caches.open(AUDIO_CACHE_NAME);
  const queue = Array.from({ length: total }, (_, i) => i + 1);
  let done = 0, success = 0;
  const CONCURRENCY = 4;

  const base = dgeEffectiveArchiveBase();
  async function worker() {
    while (queue.length) {
      const i = queue.shift();
      const fid = dgeAudioFileId(i);
      const primary = `${base}${stotraData.metadata.filePrefix}${fid}${stotraData.metadata.fileExtension}`;
      const alt = `${base}${stotraData.metadata.filePrefix}${fid}%E2%80%8B${stotraData.metadata.fileExtension}`;
      try {
        let res = await fetch(primary);
        if (!res.ok) res = await fetch(alt);
        if (res.ok) { 
          await cache.put(res.url, res.clone()); 
          success++; 
        }
      } catch (e) { /* Skip track on strict failure */ }
      done++;
      btn.innerText = `⏳ Preloading ${Math.round((done/total)*100)}%`;
    }
  }
  
  await Promise.all(Array.from({ length: CONCURRENCY }, worker));

  if (typeof nsKey === 'function') localStorage.setItem(nsKey('allCached'), 'true');
  btn.innerText = `✅ All Cached (${success}/${total})`;
  btn.dataset.cached = "true";
  btn.style.background = "#e8f5e9"; 
  btn.style.color = "#2e7d32"; 
  btn.style.borderColor = "#c8e6c9";
}

// ==========================================
// Native Audio Event Listeners
// ==========================================
if (currentAudio) {
  currentAudio.addEventListener('playing', () => { 
    isPlaying = true; 
    updatePlayUI(); 
  });
  
  currentAudio.addEventListener('pause', () => { 
    isPlaying = false; 
    updatePlayUI(); 
  });
  
  currentAudio.addEventListener('loadedmetadata', () => { 
    const speedInput = document.getElementById('speedInput');
    currentAudio.playbackRate = speedInput ? (parseFloat(speedInput.value) || 1.0) : 1.0; 
    
    const timeDisplay = document.getElementById('timeDisplay');
    if (timeDisplay) timeDisplay.innerText = `0:00.000 / ${formatTime(currentAudio.duration)}`; 
    updateRepeatDisplay(); 

    const seekSlider = document.getElementById('seekSlider');
    const seekSliderTotal = document.getElementById('seekSliderTotal');
    if (seekSlider && !isNaN(currentAudio.duration)) {
      seekSlider.max = currentAudio.duration;
      seekSlider.value = 0;
    }
    if (seekSliderTotal) seekSliderTotal.innerText = formatTime(currentAudio.duration);
  });

  currentAudio.addEventListener('error', () => {
    if (!activeId || !stotraData) return;
    const timeDisplay = document.getElementById('timeDisplay');
    
    if (audioRetryDone) {
      if (timeDisplay) timeDisplay.innerText = "Audio unavailable";
      // Still an explicit Play that was attempted -- show the player so the
      // reader can see the error/controls, rather than it silently staying
      // hidden because 'playing' never fired.
      dgeUpdateBottomPlayerVisibility();
      return;
    }
    
    audioRetryDone = true;
    currentAudio.src = `${dgeEffectiveArchiveBase()}${stotraData.metadata.filePrefix}${dgeAudioFileId(activeId)}%E2%80%8B${stotraData.metadata.fileExtension}`;
    currentAudio.load();
    // Resume the fallback URL only when playback was actually UNDERWAY or
    // explicitly requested (1 Sep 2026, project-lead report of shlokas
    // "automatically getting played" on desktop): loadShloka() sets the
    // src on every selection/jump, and when that first URL errors this
    // retry used to .play() unconditionally — turning a mere selection
    // into audible playback. window.dgePlayRequested is set by the
    // explicit play paths (playShloka/togglePlay) and cleared on
    // pause/selection, so an errored SELECTION now just readies the
    // fallback silently.
    if (window.dgePlayRequested) {
      currentAudio.play().then(() => {
        isPlaying = true;
        updatePlayUI();
      }).catch(()=>{});
    }
  });

  currentAudio.addEventListener('timeupdate', () => {
    const timeDisplay = document.getElementById('timeDisplay');
    if (timeDisplay) timeDisplay.innerText = `${formatTime(currentAudio.currentTime)} / ${formatTime(currentAudio.duration)}`;
    
    const enableAB = document.getElementById('enableAB');
    const loopA = document.getElementById('loopA');
    const loopB = document.getElementById('loopB');
    
    if (enableAB && enableAB.checked && loopB && loopA) { 
      const end = parseFloat(loopB.value);
      const start = parseFloat(loopA.value) || 0; 
      if (end && currentAudio.currentTime >= end) currentAudio.currentTime = start; 
    }

    if (!window._dgeSeekDragging) {
      const seekSlider = document.getElementById('seekSlider');
      if (seekSlider) seekSlider.value = currentAudio.currentTime;
      const seekSliderCurrent = document.getElementById('seekSliderCurrent');
      if (seekSliderCurrent) seekSliderCurrent.innerText = formatTime(currentAudio.currentTime);
    }

    if (typeof updateReadingCardSyncHighlight === 'function') updateReadingCardSyncHighlight();
  });

  currentAudio.addEventListener('ended', () => {
    const repeatInput = document.getElementById('repeatInput');
    const tRep = repeatInput ? (parseInt(repeatInput.value) || 1) : 1;
    
    if (++currentLoopCount < tRep) { 
      const loopA = document.getElementById('loopA');
      currentAudio.currentTime = loopA ? (parseFloat(loopA.value) || 0) : 0; 
      updateRepeatDisplay(); 
      currentAudio.play(); 
    } else { 
      currentLoopCount = 0; 
      updateRepeatDisplay(); 
      if (typeof currentFilter !== 'undefined' && currentFilter === 'none') { 
        isPlaying = false; 
        updatePlayUI(); 
        return; 
      } 
      playNextFiltered(); 
    }
  });
}

// UI Speed Controller Binding
document.addEventListener('DOMContentLoaded', () => {
    const speedInput = document.getElementById('speedInput');
    if (speedInput) {
        const savedSpeed = parseFloat(localStorage.getItem('app_playback_speed'));
        if (!isNaN(savedSpeed)) {
            speedInput.value = savedSpeed;
            const speedVal = document.getElementById('speedVal');
            if (speedVal) speedVal.innerText = savedSpeed.toFixed(1);
        }
        speedInput.addEventListener('input', (e) => { 
            const speedVal = document.getElementById('speedVal');
            if (speedVal) speedVal.innerText = parseFloat(e.target.value).toFixed(1); 
            if (currentAudio) currentAudio.playbackRate = e.target.value; 
            localStorage.setItem('app_playback_speed', e.target.value);
        });
    }
});

// ==========================================
// Approximate reading-along highlight
// ==========================================
// There's no per-word timestamp data for these recordings, so this is an
// ESTIMATE. Each word's on-screen time slice is weighted by its character
// length (a long compound gets proportionally more time than a short
// word like "na") rather than dividing time equally per word — equal
// division was visibly outrunning the audio on longer words. This is
// still an approximation, not true karaoke-style sync — real word-level
// sync would need timestamped audio data, which isn't available.
// 7 Sep 2026: the words are wrapped IN PLACE inside the active verse's own
// list card (#shloka-<id> .shloka-text) -- the separate reading card is
// gone. Only text nodes are touched, so footnote markers, search
// highlights, pada line breaks and intellisense spans in the card survive;
// renderList() rebuilds the card wholesale on script/theme changes, and
// updateReadingCardSyncHighlight() re-wraps lazily when it finds the
// active card unwrapped.
function dgeSyncTextEl(id) {
  const card = document.getElementById(`shloka-${id || activeId}`);
  return card ? card.querySelector('.shloka-text') : null;
}

function wrapReadingCardWordsForSync(id) {
  const el = dgeSyncTextEl(id);
  if (!el) return;
  if (!el.querySelector('.sync-word')) {
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, null);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    let wordIndex = 0;
    nodes.forEach(node => {
      if (!node.nodeValue || !node.nodeValue.trim()) return;
      if (node.parentNode && node.parentNode.closest && node.parentNode.closest('.dge-fn-marker, sup, .search-match')) return;
      const frag = document.createDocumentFragment();
      node.nodeValue.split(/(\s+)/).forEach(tok => {
        if (!tok) return;
        if (!tok.trim()) { frag.appendChild(document.createTextNode(tok)); return; }
        const sp = document.createElement('span');
        sp.className = 'sync-word'; sp.dataset.widx = String(wordIndex++); sp.textContent = tok;
        frag.appendChild(sp);
      });
      node.parentNode.replaceChild(frag, node);
    });
  }
  const words = Array.from(el.querySelectorAll('.sync-word'));
  const wordLengths = words.map(w => Math.max((w.textContent || '').length, 2)); // floor so short words still get a fair minimum
  window._dgeSyncWordCount = words.length;
  const totalWeight = wordLengths.reduce((a, b) => a + b, 0) || 1;
  let cumulative = 0;
  window._dgeSyncWordBoundaries = wordLengths.map(len => { cumulative += len; return cumulative / totalWeight; });
}

function updateReadingCardSyncHighlight() {
  if (!activeId || !currentAudio || isNaN(currentAudio.duration) || currentAudio.duration <= 0) return;
  const el = dgeSyncTextEl(activeId);
  if (!el) return;
  if (!el.querySelector('.sync-word')) wrapReadingCardWordsForSync(activeId);   // card was re-rendered since
  if (!window._dgeSyncWordCount || !window._dgeSyncWordBoundaries) return;

  const frac = Math.min(1, Math.max(0, currentAudio.currentTime / currentAudio.duration));
  const boundaries = window._dgeSyncWordBoundaries;
  let activeIdx = boundaries.findIndex(b => frac <= b);
  if (activeIdx === -1) activeIdx = boundaries.length - 1;

  const prev = el.querySelector('.sync-word.active');
  if (prev && parseInt(prev.dataset.widx, 10) === activeIdx) return;
  if (prev) prev.classList.remove('active');
  const next = el.querySelector(`.sync-word[data-widx="${activeIdx}"]`);
  if (next) next.classList.add('active');
}
window.wrapReadingCardWordsForSync = wrapReadingCardWordsForSync;
window.updateReadingCardSyncHighlight = updateReadingCardSyncHighlight;

// ==========================================
// Seek slider (scrubber) with adjustable precision
// ==========================================
const SEEK_PRECISIONS = [
  { step: 1, label: '1s' },
  { step: 0.1, label: '0.1s' },
  { step: 0.01, label: '10ms' }
];
window._dgeSeekPrecisionIdx = 0;
window._dgeSeekDragging = false;

window.toggleSeekPrecision = function() {
  window._dgeSeekPrecisionIdx = (window._dgeSeekPrecisionIdx + 1) % SEEK_PRECISIONS.length;
  const p = SEEK_PRECISIONS[window._dgeSeekPrecisionIdx];
  const seekSlider = document.getElementById('seekSlider');
  const btn = document.getElementById('seekPrecisionBtn');
  if (seekSlider) seekSlider.step = p.step;
  if (btn) btn.innerText = p.label;
};

window.onSeekSliderInput = function(value) {
  if (!currentAudio) return;
  currentAudio.currentTime = parseFloat(value);
  const seekSliderCurrent = document.getElementById('seekSliderCurrent');
  if (seekSliderCurrent) seekSliderCurrent.innerText = formatTime(currentAudio.currentTime);
};

document.addEventListener('DOMContentLoaded', () => {
  const seekSlider = document.getElementById('seekSlider');
  if (seekSlider) {
    ['pointerdown', 'touchstart'].forEach(evt => seekSlider.addEventListener(evt, () => { window._dgeSeekDragging = true; }));
    ['pointerup', 'touchend', 'change'].forEach(evt => seekSlider.addEventListener(evt, () => { window._dgeSeekDragging = false; }));
  }

  // Enter in the Start/End (loop A/B) boxes seeks + plays from that point,
  // instead of only taking effect once a snippet is saved.
  const loopA = document.getElementById('loopA');
  const loopB = document.getElementById('loopB');
  [loopA, loopB].forEach(input => {
    if (!input) return;
    input.addEventListener('keydown', (e) => {
      if (e.key !== 'Enter') return;
      e.preventDefault();
      if (!currentAudio || !activeId) return;
      const t = parseFloat(input.value);
      if (isNaN(t)) return;
      currentAudio.currentTime = Math.max(0, t);
      currentAudio.play().catch(() => {});
      input.blur();
    });
  });

  // Boot-time sync: CSS already defaults .bottom-player to hidden (see
  // dge/css/main.css), this just keeps the JS-driven class in agreement
  // with whatever AudioState actually is at load (idle, on a fresh visit).
  dgeUpdateBottomPlayerVisibility();
});

