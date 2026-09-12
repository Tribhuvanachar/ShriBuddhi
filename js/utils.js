window.DGE_VERSIONS = window.DGE_VERSIONS || {};
window.DGE_VERSIONS['utils.js'] = 'v2.5 (two themes + aliases for the removed ones; dgeInitAccordions for the Display sheet; reading-card minimize gone. v2.4: new window.dgeMakeFloatingDraggable(el, storageKey) -- shared drag-to-reposition + collapse-to-a-dot for position:fixed floating buttons, used by the कोश and global-search FABs)';

// 7 Sep 2026: two themes only, per the project lead ("is so many display
// themes required? keep only two"): Vandana (dark, the landing-page palette)
// and Traditional (light, cream with the classic red and gold). Minimal,
// Vibrant and Dark Glass are gone; a saved preference for one of them maps
// to the nearest survivor so nobody's page flips from light to dark.
window.DGE_THEMES = ['vandana', 'traditional'];
window.DGE_THEME_ALIASES = { minimal: 'traditional', vibrant: 'traditional', darkglass: 'vandana' };
window.DGE_THEME_META_COLORS = {
  vandana: '#0B0907',
  traditional: '#FFFDF9'
};

window.applyTheme = function(theme) {
  theme = window.DGE_THEME_ALIASES[theme] || theme;
  if (window.DGE_THEMES.indexOf(theme) === -1) theme = 'vandana';
  window.activeTheme = theme;

  window.DGE_THEMES.forEach(t => document.body.classList.remove('theme-' + t));
  document.body.classList.add('theme-' + theme);

  // 'dark-mode' is kept as an alias so the couple of legacy selectors that
  // still key off it (search highlight, commentary block tint) stay correct.
  document.body.classList.toggle('dark-mode', theme === 'vandana');

  // Mirrored onto <html> too, alongside body, so tokens.css's html.theme-X
  // rules (see dge/js/theme-guard.js, which sets this on <html> before
  // first paint) stay in sync on every later theme change, not just the
  // pre-paint one.
  window.DGE_THEMES.forEach(t => document.documentElement.classList.remove('theme-' + t));
  document.documentElement.classList.add('theme-' + theme);
  document.documentElement.classList.toggle('dark-mode', theme === 'vandana');

  document.querySelectorAll('#displayPopup .pop-item[data-theme]').forEach(el => {
    el.classList.toggle('active', el.dataset.theme === theme);
  });

  const meta = document.getElementById('themeColorMeta');
  if (meta) meta.setAttribute('content', window.DGE_THEME_META_COLORS[theme] || '#FFFDF9');
};

window.setTheme = function(theme, el) {
  window.applyTheme(theme);
  localStorage.setItem('app_theme', theme);
  // (see note in transliteration.js — Display popup stays open)
};

// Legacy aliases kept so nothing that still calls these (or a bookmarked
// console command) throws — they now just map onto the theme system.
window.applyDarkMode = function(isDark) {
  window.applyTheme(isDark ? 'vandana' : 'traditional');
};
window.toggleDarkMode = function() {
  window.setTheme(window.activeTheme === 'vandana' ? 'traditional' : 'vandana');
};

window.applyFontSize = function(px) {
  document.documentElement.style.setProperty('--font-multiplier', px + 'px');
  document.querySelectorAll('#displayPopup .pop-item[data-size]').forEach(el => {
    el.classList.toggle('active', parseInt(el.dataset.size, 10) === px);
  });
};

// Applies the (possibly per-device overridden) feature flags — hides the
// theme/script picker buttons and the A-B/snippet tools section when
// their flag is off. Chip-level flags (favorite/status/doubt/notes/
// snippet-count) are read directly by render.js on every renderList() call
// instead, since those need to react per-card rather than as a one-time
// show/hide.
window.applyFeatureFlags = function() {
  const flags = (typeof dgeGetEffectiveFeatureFlags === 'function') ? dgeGetEffectiveFeatureFlags() : (window.FEATURE_FLAGS || {});

  const themeBtn = document.getElementById('activeThemeBtn');
  const themeWrap = themeBtn ? themeBtn.closest('div') : null;
  if (themeWrap) themeWrap.style.display = flags.showThemePicker ? '' : 'none';

  const scriptBtn = document.getElementById('activeScriptBtn');
  const scriptWrap = scriptBtn ? scriptBtn.closest('div') : null;
  if (scriptWrap) scriptWrap.style.display = flags.showScriptPicker ? '' : 'none';

  const abSection = document.getElementById('abSnippetToolsSection');
  if (abSection) abSection.style.display = flags.showSnippetTools ? '' : 'none';

  const speedRow = document.getElementById('speedControlRow');
  if (speedRow) speedRow.style.display = flags.showSpeedControl ? '' : 'none';

  const cacheBtn = document.getElementById('cacheBtn');
  if (cacheBtn) cacheBtn.style.display = flags.showPreloadButton ? '' : 'none';

  // Which scripts/languages show up in the 🔠 picker
  const scriptOptions = (typeof dgeGetEffectiveScriptOptions === 'function') ? dgeGetEffectiveScriptOptions() : (window.SCRIPT_OPTIONS || []);
  scriptOptions.forEach(opt => {
    const el = document.querySelector(`#displayPopup .pop-item[data-script][data-script="${opt.id}"]`);
    if (el) el.style.display = opt.enabled ? '' : 'none';
  });

  // renderList() rebuilds the cards, which is what applies the धातु/कोश word
  // marks and the धातुरूपाणि chip row: both are baked into the card's HTML
  // rather than toggled by a style rule, so switching either flag has to go
  // back through the renderer.
  if (typeof renderList === 'function') renderList();
};

window.setFontSize = function(px, el) {
  window.applyFontSize(px);
  localStorage.setItem('app_fontSize', String(px));
  // (see note in transliteration.js — Display popup stays open)
};

// 28 Aug 2026: real queue, not independent setTimeouts on the same element.
// The old version let a second showToast() call while one was still up
// reset the DOM text but not the FIRST call's own hide timer -- so a
// message could vanish mid-read, or two unrelated messages could visually
// collide, because there was never more than one timer's worth of "am I
// still the message that should be showing" tracked. Now only one toast is
// ever on screen; a call while one is up queues instead of racing it.
let dgeToastQueue = [];
let dgeToastTimer = null;
const DGE_TOAST_MS = 3000;
const DGE_TOAST_GAP_MS = 250; // brief gap so consecutive toasts read as separate, not one long flash

function dgeToastAdvance() {
  const toast = document.getElementById('toastMsg');
  if (!toast) return;
  if (!dgeToastQueue.length) {
    toast.classList.remove('show');
    dgeToastTimer = setTimeout(() => { toast.style.display = 'none'; }, 300);
    return;
  }
  const msg = dgeToastQueue.shift();
  toast.innerText = msg;
  toast.style.display = 'block';
  // Force a reflow so the .show transition re-triggers even if the toast
  // never fully hid between two queued messages.
  void toast.offsetWidth;
  toast.classList.add('show');
  dgeToastTimer = setTimeout(() => {
    toast.classList.remove('show');
    dgeToastTimer = setTimeout(dgeToastAdvance, DGE_TOAST_GAP_MS);
  }, DGE_TOAST_MS);
}

window.showToast = function(msg) {
  const toast = document.getElementById('toastMsg');
  if (!toast) return;
  dgeToastQueue.push(msg);
  const alreadyShowing = toast.style.display === 'block' && toast.classList.contains('show');
  if (!alreadyShowing) {
    clearTimeout(dgeToastTimer);
    dgeToastAdvance();
  }
};

// (7 Sep 2026: the sticky reading card and its minimize toggle are gone --
// the active verse is marked and read-along highlighted in its own list
// card instead; see audio.js.)

// 7 Sep 2026: the Display sheet's sections (Layout, Genie Selection Mode,
// Reading Script, Reading Size, Reading View, Appearance) are accordions --
// each .popup-label becomes a header with a ▾/▴ arrow, its items fold
// away, and the header shows the current choice so a folded section still
// tells you what is set. The lead's ask: "can each of the menu items be
// made accordion drops with up and down arrows". Open state is remembered
// per section. The markup (ids, data-* attributes, .pop-item children) is
// untouched, so setScript/setFontSize/setTheme/... keep working.
window.dgeInitAccordions = function(rootSel, storageKey) {
  const root = document.querySelector(rootSel);
  if (!root || root.dataset.accordions === '1') return;
  root.dataset.accordions = '1';
  let open = {};
  try { open = JSON.parse(localStorage.getItem(storageKey) || '{}') || {}; } catch (e) { open = {}; }
  const labels = Array.from(root.querySelectorAll('.popup-label'));
  labels.forEach((label, idx) => {
    const key = (label.textContent || '').trim().toLowerCase().replace(/\s+/g, '-') || String(idx);
    const body = document.createElement('div');
    body.className = 'dge-acc-body';
    let n = label.nextSibling;
    while (n && !(n.nodeType === 1 && (n.tagName === 'HR' || n.classList.contains('popup-label')))) {
      const next = n.nextSibling; body.appendChild(n); n = next;
    }
    const wrap = document.createElement('div');
    wrap.className = 'dge-acc' + (open[key] ? ' open' : '');
    wrap.dataset.accKey = key;
    const head = document.createElement('button');
    head.type = 'button'; head.className = 'dge-acc-head';
    head.setAttribute('aria-expanded', open[key] ? 'true' : 'false');
    head.innerHTML = `<span class="dge-acc-title"></span><span class="dge-acc-current"></span><span class="dge-acc-arrow" aria-hidden="true"></span>`;
    head.querySelector('.dge-acc-title').textContent = (label.textContent || '').trim();
    label.parentNode.insertBefore(wrap, label);
    wrap.appendChild(head); wrap.appendChild(body);
    label.remove();
    head.addEventListener('click', (e) => {
      e.stopPropagation();
      const isOpen = wrap.classList.toggle('open');
      head.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
      open[key] = isOpen;
      try { localStorage.setItem(storageKey, JSON.stringify(open)); } catch (err) {}
    });
  });
  // Current-choice summary in each header (the active item's own label,
  // minus its trailing hint), refreshed whenever the sheet changes.
  const refresh = () => {
    root.querySelectorAll('.dge-acc').forEach(w => {
      const act = w.querySelector('.pop-item.active');
      const cur = w.querySelector('.dge-acc-current');
      if (!cur) return;
      if (!act) { cur.textContent = ''; return; }
      const clone = act.cloneNode(true);
      clone.querySelectorAll('span[style*="margin-left:auto"]').forEach(x => x.remove());
      cur.textContent = (clone.textContent || '').replace(/\s+/g, ' ').trim();
    });
  };
  refresh();
  new MutationObserver(refresh).observe(root, { subtree: true, attributes: true, attributeFilter: ['class'] });
};
document.addEventListener('DOMContentLoaded', () => { window.dgeInitAccordions('#displayPopup .popup-sheet-scroll', 'dge_display_acc'); });

// 7 Sep 2026: API-key / token inputs start life as type=text (.dge-secret,
// masked by CSS) and become real password fields only while focused. With
// four static type=password inputs in hidden modals, Chrome treated the page
// as a login form and offered "Use saved password?" on the search box.
document.addEventListener('focusin', function (e) {
  const el = e.target;
  if (el && el.classList && el.classList.contains('dge-secret') && el.type === 'text') el.type = 'password';
});
document.addEventListener('focusout', function (e) {
  const el = e.target;
  if (el && el.classList && el.classList.contains('dge-secret') && el.type === 'password') el.type = 'text';
});

// --- DYNAMIC DEV LOGGER WITH COPY / MINIMIZE / CLOSE ---
(function initDevLogger() {
    const urlParams = new URLSearchParams(window.location.search);
    const isDev = urlParams.get('dev') === 'true' || localStorage.getItem('is_superadmin') === 'true';
    
    const legacyLog = document.getElementById('mobileDebugLog');
    if (legacyLog) legacyLog.remove();

    if (!isDev) return;

    const EXPANDED_HEIGHT = 180;

    // Small helper: makes targetEl repositionable anywhere on screen by
    // dragging handleEl, remembering the chosen position across reloads.
    // Pointer Events cover touch and mouse with the same code.
    function makeDraggable(handleEl, targetEl, storageKey) {
        let dragging = false, startX = 0, startY = 0, startLeft = 0, startTop = 0;

        try {
            const saved = JSON.parse(localStorage.getItem(storageKey) || 'null');
            if (saved) {
                targetEl.style.left = saved.left + 'px';
                targetEl.style.top = saved.top + 'px';
                targetEl.style.right = 'auto';
                targetEl.style.bottom = 'auto';
            }
        } catch (e) { /* ignore, use default position */ }

        handleEl.style.cursor = 'move';
        handleEl.style.touchAction = 'none';

        handleEl.addEventListener('pointerdown', (e) => {
            dragging = true;
            startX = e.clientX;
            startY = e.clientY;
            const rect = targetEl.getBoundingClientRect();
            startLeft = rect.left;
            startTop = rect.top;
            handleEl.setPointerCapture(e.pointerId);
        });

        handleEl.addEventListener('pointermove', (e) => {
            if (!dragging) return;
            let newLeft = startLeft + (e.clientX - startX);
            let newTop = startTop + (e.clientY - startY);
            // Keep at least 40px of the panel reachable on-screen either way.
            newLeft = Math.max(-targetEl.offsetWidth + 40, Math.min(newLeft, window.innerWidth - 40));
            newTop = Math.max(0, Math.min(newTop, window.innerHeight - 40));
            targetEl.style.left = newLeft + 'px';
            targetEl.style.top = newTop + 'px';
            targetEl.style.right = 'auto';
            targetEl.style.bottom = 'auto';
        });

        handleEl.addEventListener('pointerup', () => {
            if (!dragging) return;
            dragging = false;
            try {
                const rect = targetEl.getBoundingClientRect();
                localStorage.setItem(storageKey, JSON.stringify({ left: rect.left, top: rect.top }));
            } catch (e) { /* ignore */ }
        });
    }

    const dgeLog = document.createElement('div');
    dgeLog.id = 'dgeMobileLogContainer';
    dgeLog.style.cssText = 'display: none; position: fixed; right: 10px; top: 70px; width: min(320px, 90vw); background: rgba(0,0,0,0.95); color: #0f0; font-family: monospace; font-size: 11px; z-index: 999999; max-height: ' + EXPANDED_HEIGHT + 'px; overflow-y: auto; box-sizing: border-box; border: 2px solid #0f0; border-radius: 8px; touch-action: pan-y; overscroll-behavior: contain; pointer-events: auto; transition: max-height 0.15s ease;';

    // Header bar: title + Minimize + Close (always visible, even when minimized)
    const header = document.createElement('div');
    header.style.cssText = 'display: flex; align-items: center; justify-content: space-between; gap: 6px; padding: 6px 8px; background: rgba(0,0,0,0.95); position: sticky; top: 0; border-bottom: 1px solid rgba(0,255,0,0.3); z-index: 2;';

    const title = document.createElement('strong');
    title.innerText = '📱 DGE Dev Logger';
    title.style.cssText = 'flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;';

    // Dedicated drag handle — a separate small element with NO click
    // behavior at all, so there's no ambiguity between "tap" and "drag"
    // to get wrong (that ambiguity on the header itself, even after
    // excluding button taps, was still unreliable).
    const dragHandle = document.createElement('span');
    dragHandle.innerText = '✥';
    dragHandle.title = 'Drag to move';
    dragHandle.style.cssText = 'flex-shrink: 0; padding: 2px 8px; font-size: 14px; touch-action: none; cursor: move;';

    const btnRowStyle = 'background: #333; color: #fff; border: 1px solid #0f0; padding: 5px 10px; font-size: 11px; font-weight: bold; border-radius: 6px; cursor: pointer; flex-shrink: 0; touch-action: manipulation;';

    const copyBtn = document.createElement('button');
    copyBtn.innerText = '📋 Copy';
    copyBtn.style.cssText = btnRowStyle;

    const fullscreenBtn = document.createElement('button');
    fullscreenBtn.innerText = '⛶ Full';
    fullscreenBtn.style.cssText = btnRowStyle;

    const minimizeBtn = document.createElement('button');
    minimizeBtn.innerText = '▁ Min';
    minimizeBtn.style.cssText = btnRowStyle;

    const closeBtn = document.createElement('button');
    closeBtn.innerText = '✕';
    closeBtn.style.cssText = btnRowStyle + ' border-color:#ff5555;';

    header.appendChild(dragHandle);
    header.appendChild(title);
    header.appendChild(copyBtn);
    header.appendChild(fullscreenBtn);
    header.appendChild(minimizeBtn);
    header.appendChild(closeBtn);

    // Small reopen tab shown after closing
    const reopenBtn = document.createElement('button');
    reopenBtn.id = 'dgeLogReopenBtn';
    reopenBtn.innerText = '🐞 Logs';
    reopenBtn.style.cssText = 'display:block; position: fixed; top: 8px; background: #111; color: #0f0; border: 1px solid #0f0; padding: 6px 10px; font-size: 11px; font-weight: bold; border-radius: 20px; z-index: 999999; cursor: pointer;';

    // Docked just under the Library button (left edge, below the top bar)
    // rather than top-center — centering put it right on top of the
    // commentary selector and other action-row popups, which is what a
    // reader mistook for the tool being broken; and since 7 Sep 2026 the
    // search row occupies the bar to the right of the Library button, so
    // the pill hangs below the bar instead of beside the title.
    // Recentered on every popup open (see togglePopup in modals.js) — manual
    // drags are honoured until the next popup open snaps it back. Pages with
    // no top-bar title fall back to the old top-center placement.
    function dgeRecenterLogPill() {
        const titleEl = document.querySelector('.top-bar-title');
        const titleRect = titleEl && titleEl.getBoundingClientRect();
        if (titleRect && titleRect.width) {
            reopenBtn.style.left = Math.max(4, titleRect.left) + 'px';
            reopenBtn.style.top = Math.round(titleRect.bottom + 12) + 'px';
        } else {
            reopenBtn.style.left = Math.max(8, (window.innerWidth - reopenBtn.offsetWidth) / 2) + 'px';
            reopenBtn.style.top = '8px';
        }
        reopenBtn.style.right = 'auto';
        reopenBtn.style.bottom = 'auto';
        try {
            const r = reopenBtn.getBoundingClientRect();
            localStorage.setItem('dgeLogReopenPos_v3', JSON.stringify({ left: r.left, top: r.top }));
        } catch (e) { /* ignore */ }
    }

    // Text container to isolate content for copying
    const logTextContainer = document.createElement('div');
    logTextContainer.style.cssText = 'padding: 8px; user-select: text; -webkit-user-select: text;';

    copyBtn.onclick = () => {
        const textToCopy = logTextContainer.innerText;
        if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(textToCopy).then(() => {
                copyBtn.innerText = '✅ Copied!';
                setTimeout(() => copyBtn.innerText = '📋 Copy', 2000);
            });
        } else {
            // Fallback for older mobile browsers
            const textArea = document.createElement("textarea");
            textArea.value = textToCopy;
            textArea.style.position = "fixed";
            textArea.style.left = "-999999px";
            document.body.appendChild(textArea);
            textArea.select();
            try {
                document.execCommand('copy');
                copyBtn.innerText = '✅ Copied!';
                setTimeout(() => copyBtn.innerText = '📋 Copy', 2000);
            } catch (err) {
                console.error("Copy fallback failed", err);
            }
            textArea.remove();
        }
    };

    let isMinimized = false;
    function setMinimized(min) {
        isMinimized = min;
        logTextContainer.style.display = min ? 'none' : 'block';
        dgeLog.style.maxHeight = min ? 'auto' : EXPANDED_HEIGHT + 'px';
        dgeLog.style.overflowY = min ? 'visible' : 'auto';
        dgeLog.style.width = min ? 'auto' : 'min(320px, 90vw)';
        // Copy/Full aren't meaningful without the log actually open, and
        // hiding them (not just shrinking via width:auto, which alone
        // barely helps with 4 buttons' worth of content still in the row)
        // is what actually makes the collapsed footprint small.
        copyBtn.style.display = min ? 'none' : 'inline-block';
        fullscreenBtn.style.display = min ? 'none' : 'inline-block';
        minimizeBtn.innerText = min ? '▔ Max' : '▁ Min';
    }
    minimizeBtn.onclick = () => setMinimized(!isMinimized);
    // Start collapsed AND narrow so it doesn't dominate the screen on
    // load — previously it kept the full expanded width even while
    // "minimized", which is why it still looked like it was in the way.
    setMinimized(true);

    let isFullscreen = false;
    let preFullscreenStyle = '';
    fullscreenBtn.onclick = () => {
        isFullscreen = !isFullscreen;
        if (isFullscreen) {
            preFullscreenStyle = dgeLog.style.cssText;
            dgeLog.style.cssText = 'display: block; position: fixed; left: 8px; right: 8px; top: 8px; bottom: 8px; width: auto; background: rgba(0,0,0,0.97); color: #0f0; font-family: monospace; font-size: 12px; z-index: 999999; max-height: none; overflow-y: auto; box-sizing: border-box; border: 2px solid #0f0; border-radius: 8px;';
            if (isMinimized) setMinimized(false);
            fullscreenBtn.innerText = '⛶ Exit';
        } else {
            dgeLog.style.cssText = preFullscreenStyle;
            fullscreenBtn.innerText = '⛶ Full';
        }
    };

    closeBtn.onclick = () => {
        dgeLog.style.display = 'none';
        reopenBtn.style.display = 'block';
    };
    reopenBtn.onclick = () => {
        dgeLog.style.display = 'block';
        reopenBtn.style.display = 'none';
    };

    dgeLog.appendChild(header);
    dgeLog.appendChild(logTextContainer);
    document.body.appendChild(dgeLog);
    document.body.appendChild(reopenBtn);

    // Floats anywhere on screen now instead of being docked full-width to
    // the bottom — drag via the dedicated ✥ handle (or the small pill
    // when minimized to reopen-tab form), position remembered across
    // reloads.
    makeDraggable(dragHandle, dgeLog, 'dgeLogPanelPos_v3');
    makeDraggable(reopenBtn, reopenBtn, 'dgeLogReopenPos_v3');
    // Overrides whatever makeDraggable just restored from a stale saved
    // position — the pill always starts centered on a fresh load; a saved
    // off-center spot from dragging earlier in THIS session is only
    // meaningful until the next popup open snaps it back anyway.
    dgeRecenterLogPill();

    const oldLog = console.log;
    const oldWarn = console.warn;
    const oldErr = console.error;

    // JSON.stringify on a genuine Error object produces "{}" — its
    // message/stack are non-enumerable own properties, so they get
    // silently dropped, hiding the actual reason behind every error this
    // panel shows. Extracting .message explicitly for Error objects (and
    // falling back to normal string/JSON handling for everything else)
    // fixes that for all three console overrides below.
    function dgeFormatLogArg(a) {
        if (a instanceof Error) return a.message || String(a);
        return typeof a === 'object' ? JSON.stringify(a) : String(a);
    }

    console.log = function(...args) {
        oldLog(...args);
        const msg = args.map(dgeFormatLogArg).join(' ');
        logTextContainer.innerHTML += `<span style="color:#0f0;">> ${msg}</span><br>`;
        dgeLog.scrollTop = dgeLog.scrollHeight;
    };

    console.warn = function(...args) {
        oldWarn(...args);
        const msg = args.map(dgeFormatLogArg).join(' ');
        logTextContainer.innerHTML += `<span style="color:#ffcc00;">> [WARN] ${msg}</span><br>`;
        dgeLog.scrollTop = dgeLog.scrollHeight;
    };

    console.error = function(...args) {
        oldErr(...args);
        const msg = args.map(dgeFormatLogArg).join(' ');
        logTextContainer.innerHTML += `<span style="color:#ff5555;">> [ERR] ${msg}</span><br>`;
        dgeLog.scrollTop = dgeLog.scrollHeight;
    };
    
    window.onerror = function(msg, url, line) {
        console.error(`Uncaught Error: ${msg} (Line ${line})`);
    };

    // Several features added recently (Ask Acharya, snippet download/share,
    // audio caching) are async functions. A thrown error inside one of
    // those becomes an unhandled promise rejection, which window.onerror
    // does NOT catch — only this listener does.
    window.addEventListener('unhandledrejection', (event) => {
        const reason = event.reason;
        const msg = (reason && reason.message) ? reason.message : String(reason);
        console.error(`Unhandled Promise Rejection: ${msg}`);
    });

    // Public API so other modules (e.g. dev.js) can feed content into THIS
    // single log panel instead of creating their own separate overlay.
    window.DGE_DEV_LOG = {
        appendHTML: function(html) {
            logTextContainer.innerHTML += html;
            dgeLog.scrollTop = dgeLog.scrollHeight;
        },
        // Called from togglePopup() (modals.js) whenever any dropdown/popup
        // opens, so the pill can never end up sitting on top of it.
        recenterPill: dgeRecenterLogPill
    };

})();

// Shared drag-to-reposition + collapse-to-a-dot behaviour for every
// position:fixed floating action button (कोश, global search 🔎) -- was
// each independently a plain fixed-position button with no way to move it
// out from behind content it happened to land on, and no way to shrink it
// out of the way on a small screen. One shared implementation so a fix to
// the drag logic (see content-inline.js's own wireDrag, which this mirrors
// for its document-level pointer tracking and click-vs-drag threshold)
// benefits every floating button at once instead of drifting between
// separately-maintained copies.
window.dgeMakeFloatingDraggable = function (el, storageKey) {
    var POS_KEY = 'dge.fabPos.' + storageKey;
    var COLLAPSE_KEY = 'dge.fabCollapsed.' + storageKey;

    function loadPos() {
        try {
            var p = JSON.parse(localStorage.getItem(POS_KEY) || 'null');
            if (p && typeof p.xFrac === 'number' && typeof p.yFrac === 'number') return p;
        } catch (e) { /* fall through to default (the button's own CSS position) */ }
        return null;
    }
    function savePos(p) { try { localStorage.setItem(POS_KEY, JSON.stringify(p)); } catch (e) { /* ignore */ } }
    function loadCollapsed() { try { return localStorage.getItem(COLLAPSE_KEY) === '1'; } catch (e) { return false; } }
    function saveCollapsed(v) { try { localStorage.setItem(COLLAPSE_KEY, v ? '1' : '0'); } catch (e) { /* ignore */ } }

    function clampToViewport(left, top) {
        var r = el.getBoundingClientRect();
        var w = r.width || 56, h = r.height || 56;
        return {
            left: Math.min(Math.max(left, 4), window.innerWidth - w - 4),
            top: Math.min(Math.max(top, 4), window.innerHeight - h - 4)
        };
    }

    var pos = loadPos();
    if (pos) {
        var abs = clampToViewport(pos.xFrac * window.innerWidth, pos.yFrac * window.innerHeight);
        el.style.left = abs.left + 'px'; el.style.top = abs.top + 'px';
        el.style.right = 'auto'; el.style.bottom = 'auto';
    }
    el.style.position = 'fixed';

    // A small always-present corner handle collapses the button to a dot at
    // its current position -- deliberately a separate element from the fab
    // itself (rather than, say, a long-press on the fab) so it never
    // conflicts with the fab's own click-to-open behaviour or the drag
    // threshold below.
    var collapseBtn = document.createElement('span');
    collapseBtn.textContent = '−';
    collapseBtn.title = 'Collapse';
    collapseBtn.setAttribute('aria-label', 'Collapse');
    collapseBtn.style.cssText = 'position:absolute; top:-6px; right:-6px; width:18px; height:18px; ' +
        'line-height:17px; text-align:center; border-radius:50%; background:var(--card-bg,#fff); ' +
        'color:var(--text-primary,#333); font-size:14px; font-weight:700; box-shadow:0 1px 4px rgba(0,0,0,.35); ' +
        'cursor:pointer; z-index:1;';
    el.appendChild(collapseBtn);

    function setCollapsed(v) {
        el.classList.toggle('dge-fab-collapsed', v);
        el.style.transform = v ? 'scale(0.42)' : '';
        el.style.opacity = v ? '0.5' : '';
        collapseBtn.style.display = v ? 'none' : '';
        saveCollapsed(v);
    }
    setCollapsed(loadCollapsed());
    collapseBtn.addEventListener('click', function (ev) {
        ev.stopPropagation(); ev.preventDefault();
        setCollapsed(true);
    });

    // Dragging and collapse-state interact: while collapsed, a tap anywhere
    // on the (now tiny) button should re-expand it rather than triggering
    // whatever the button's own click handler normally does -- opening
    // Kosha/search on a button the reader deliberately shrank out of the
    // way would be a worse surprise than just needing a second tap.
    var dragging = false, moved = false, justDragged = false, startX = 0, startY = 0, startLeft = 0, startTop = 0;
    el.addEventListener('click', function (ev) {
        if (el.classList.contains('dge-fab-collapsed')) {
            ev.stopImmediatePropagation(); ev.preventDefault();
            setCollapsed(false);
            return;
        }
        if (justDragged) { ev.stopImmediatePropagation(); ev.preventDefault(); }
    }, true);
    el.addEventListener('pointerdown', function (ev) {
        if (ev.target === collapseBtn) return;
        dragging = true; moved = false;
        startX = ev.clientX; startY = ev.clientY;
        var r = el.getBoundingClientRect();
        startLeft = r.left; startTop = r.top;
        document.addEventListener('pointermove', onMove);
        document.addEventListener('pointerup', onUp);
        document.addEventListener('pointercancel', onUp);
    });
    function onMove(ev) {
        if (!dragging) return;
        var dx = ev.clientX - startX, dy = ev.clientY - startY;
        if (!moved && Math.hypot(dx, dy) < 6) return; // still within click/tap tolerance
        moved = true;
        var clamped = clampToViewport(startLeft + dx, startTop + dy);
        el.style.left = clamped.left + 'px'; el.style.top = clamped.top + 'px';
        el.style.right = 'auto'; el.style.bottom = 'auto';
    }
    function onUp() {
        if (!dragging) return;
        dragging = false;
        document.removeEventListener('pointermove', onMove);
        document.removeEventListener('pointerup', onUp);
        document.removeEventListener('pointercancel', onUp);
        if (!moved) return; // a plain tap -- let the button's own click handler run
        moved = false;
        justDragged = true;
        setTimeout(function () { justDragged = false; }, 0); // cleared after this tick's click, if any, is swallowed
        var r = el.getBoundingClientRect();
        savePos({ xFrac: r.left / window.innerWidth, yFrac: r.top / window.innerHeight });
    }
    // A saved position from a wider/taller viewport (rotated phone, resized
    // window) could otherwise sit off-screen or under the notch.
    window.addEventListener('resize', function () {
        var r = el.getBoundingClientRect();
        var clamped = clampToViewport(r.left, r.top);
        if (clamped.left !== r.left || clamped.top !== r.top) {
            el.style.left = clamped.left + 'px'; el.style.top = clamped.top + 'px';
        }
    });
};

// Phase 4 of the mobile UI overhaul: distraction-free full screen reading
// (see main.css's body.dge-immersive rules). A plain class toggle plus one
// persistent exit button -- session-only on purpose, not persisted to
// localStorage, so a reload never silently drops a returning reader into
// a chrome-free screen they didn't ask for this time.
window.dgeToggleImmersiveMode = function (force) {
    var enable = (typeof force === 'boolean') ? force : !document.body.classList.contains('dge-immersive');
    if (enable) {
        // "Full Screen Reading" is only reachable from inside the Display
        // sheet, so entering immersive mode ALWAYS starts with at least
        // one popup open. Actually closing it (not just CSS-hiding it
        // behind body.dge-immersive's chrome rules) matters for two
        // reasons: a .popup-sheet's :has(.show) backdrop dimmer (see
        // main.css) is driven purely by the .show class, so a hidden-but-
        // still-.show sheet would leave that dark backdrop rendering over
        // the "clean" immersive view; and without this, exiting immersive
        // mode would silently leave the sheet/drawer sitting open again,
        // right where it was tapped from.
        document.querySelectorAll('.popup.show').forEach(function (p) { p.classList.remove('show'); });
        document.querySelectorAll('.modal-overlay.show').forEach(function (m) {
            if (typeof closeModal === 'function') closeModal(m.id); else m.style.display = 'none';
        });
    }
    document.body.classList.toggle('dge-immersive', enable);
};

// Phase 7 of the mobile UI overhaul: Screen Wake Lock, one of the
// ashtadhyayi.com-inspired preferences the project lead asked to add. A
// plain manual preference (like ashtadhyayi's own "Preferences" toggle),
// not tied to audio play/pause state -- reading without audio playing is
// just as real a use case, and keeping this independent of audio.js's
// playback logic avoids adding a new failure mode to that already-
// intricate code path. Browsers release the lock whenever the tab loses
// visibility (backgrounding, screen lock, app switch), which is not the
// user turning the preference off -- so it's silently re-acquired on
// visibilitychange whenever the preference is still on, exactly the way
// every wake-lock guide describes handling this.
window.dgeWakeLockSentinel = null;
window.dgeSetScreenWakeLock = function (enable) {
    localStorage.setItem('app_wakeLock', enable ? '1' : '0');
    document.querySelectorAll('.pop-item[data-wakelock]').forEach(function (el) {
        el.classList.toggle('active', (el.dataset.wakelock === '1') === !!enable);
    });
    if (!enable) {
        if (window.dgeWakeLockSentinel) { window.dgeWakeLockSentinel.release().catch(function () {}); window.dgeWakeLockSentinel = null; }
        return;
    }
    if (!('wakeLock' in navigator)) return; // unsupported browser -- preference is saved, just has no visible effect here
    navigator.wakeLock.request('screen').then(function (sentinel) {
        window.dgeWakeLockSentinel = sentinel;
        sentinel.addEventListener('release', function () { if (window.dgeWakeLockSentinel === sentinel) window.dgeWakeLockSentinel = null; });
    }).catch(function () { /* denied or unsupported in this context -- non-fatal, reading still works */ });
};
document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'visible' && localStorage.getItem('app_wakeLock') === '1' && !window.dgeWakeLockSentinel) {
        window.dgeSetScreenWakeLock(true);
    }
});

console.log("[Init] utils.js loaded successfully.");
