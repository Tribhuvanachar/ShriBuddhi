/* =========================================================================
   Edit a page's words on the page itself.

   Every page whose text now lives in admin/content/<page>.json can be edited
   where it is read: unlock super-admin, turn on Edit text, tap a sentence,
   change it, publish. The same shape as the reading page's shloka editor —
   nothing reaches GitHub on a keystroke; edits stage in memory, survive a
   refresh, and go up in one commit when a human confirms.

   A page opts in with two attributes and nothing else:

     <body data-content-file="admin/content/home.json">
     ...<h1 data-edit="brand.latin">…</h1>

   data-edit is a path into that JSON — "brand.latin", "sections.0.name",
   "panels.tribhuvan.groups.2.entries.0.note". The editor reads the current
   value from the file rather than from the DOM, so what you edit is the
   source text and not a transliterated or truncated rendering of it.

   Self-contained on purpose. The landing page loads no admin JavaScript at
   all — pulling in admin-editor.js (1,700 lines) to change one sentence
   would be absurd — so the sixty lines of GitHub API it needs are here,
   using the same PAT under the same localStorage key.
   ========================================================================= */
(function () {
  'use strict';

  window.DGE_VERSIONS = window.DGE_VERSIONS || {};
  window.DGE_VERSIONS['content-inline.js'] = 'v1.1 (wireDrag: fixed the laggy touch drag -- was calling getBoundingClientRect() on every single pointermove, forcing a synchronous layout flush on every one of a touch drag\'s many events; now measured once per drag and the style write is batched to one per animation frame)';

  const FILE = document.body && document.body.dataset.contentFile;
  if (!FILE) return;                       // page has not opted in

  const DRAFT_KEY = 'dgeContentInlineDraft:' + FILE;
  const self = (document.currentScript && document.currentScript.src) || '';

  function contentUrl() {
    // FILE is repo-relative; the page may sit at the root or inside dge/.
    try { return new URL('../../' + FILE, self).href; }
    catch (e) { return '/' + FILE; }
  }

  const esc = (s) => String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');

  let source = null;      // the file as published
  let draft = {};         // path -> new value, staged
  let editing = false;

  /* ---------------------------------------------------------- the JSON --- */
  function getPath(obj, path) {
    return path.split('.').reduce(function (o, k) {
      return (o == null) ? undefined : o[k];
    }, obj);
  }

  function setPath(obj, path, value) {
    const parts = path.split('.');
    let node = obj;
    for (let i = 0; i < parts.length - 1; i++) {
      const k = parts[i];
      if (node[k] == null) node[k] = /^\d+$/.test(parts[i + 1]) ? [] : {};
      node = node[k];
    }
    node[parts[parts.length - 1]] = value;
  }

  function loadSource() {
    return fetch(contentUrl() + '?t=' + Date.now(), { cache: 'no-store' })
      .then(r => (r.ok ? r.json() : null));
  }

  /* ----------------------------------------------------------- drafts ---- */
  function persist() {
    try { localStorage.setItem(DRAFT_KEY, JSON.stringify(draft)); } catch (e) {}
  }
  function restore() {
    try {
      const raw = localStorage.getItem(DRAFT_KEY);
      draft = raw ? JSON.parse(raw) : {};
    } catch (e) { draft = {}; }
  }
  function clearDraft() {
    draft = {};
    try { localStorage.removeItem(DRAFT_KEY); } catch (e) {}
  }

  /* --------------------------------------------------------- the token --- */
  function token() { return localStorage.getItem('github_admin_pat') || ''; }

  function repo() {
    const c = window.GITHUB_REPO_CONFIG ||
      { owner: 'Tribhuvanachar', repo: 'bhumandala', branch: 'main' };
    return c;
  }

  function b64(text) {
    // btoa() breaks on anything outside Latin-1, and this file is mostly
    // Devanagari — encode to UTF-8 bytes first.
    const bytes = new TextEncoder().encode(text);
    let binary = '';
    bytes.forEach(function (b) { binary += String.fromCharCode(b); });
    return btoa(binary);
  }

  function api(path, options) {
    const c = repo();
    const url = 'https://api.github.com/repos/' + c.owner + '/' + c.repo +
                '/contents/' + path;
    const headers = { 'Accept': 'application/vnd.github+json' };
    if (token()) headers.Authorization = 'token ' + token();
    return fetch(url + (options && options.method ? '' : '?ref=' + c.branch),
                 Object.assign({ headers: headers }, options || {}));
  }

  function publish() {
    if (!token()) {
      alert('No GitHub token saved on this device.\n\nOpen the library, unlock ' +
            'Super Admin, and add a personal access token under Repo Files — ' +
            'this page uses the same one.');
      return Promise.resolve(false);
    }
    // Re-read before writing: someone may have edited the file since this
    // page loaded, and blind-overwriting their change would be the worst
    // possible behaviour for a tool whose whole job is editing text.
    return loadSource().then(function (latest) {
      const out = JSON.parse(JSON.stringify(latest || source));
      Object.keys(draft).forEach(function (p) { setPath(out, p, draft[p]); });
      const text = JSON.stringify(out, null, 2) + '\n';
      return api(FILE).then(function (r) {
        return r.ok ? r.json() : null;
      }).then(function (existing) {
        const c = repo();
        return api(FILE, {
          method: 'PUT',
          body: JSON.stringify({
            message: 'Edit ' + FILE + ' in place',
            content: b64(text),
            branch: c.branch,
            sha: existing && existing.sha
          })
        });
      }).then(function (r) {
        if (!r.ok) return r.text().then(function (t) { throw new Error(r.status + ' ' + t.slice(0, 200)); });
        source = out;
        clearDraft();
        return true;
      });
    });
  }

  /* ------------------------------------------------------------- edit ---- */
  function currentValue(path) {
    return Object.prototype.hasOwnProperty.call(draft, path)
      ? draft[path] : getPath(source, path);
  }

  let closeOpen = null;   // the one editor currently open, if any

  function openEditor(el) {
    if (el.querySelector('.ci-box')) return;
    // One at a time. Two open textareas is two places the same page is being
    // changed, and the second one hides whether the first was saved.
    if (closeOpen) closeOpen();
    const path = el.getAttribute('data-edit');
    const value = currentValue(path);
    if (typeof value !== 'string') {
      alert('"' + path + '" is not a piece of text — it is ' +
            (value === undefined ? 'not in the file' : 'a ' + typeof value) +
            '. Edit it in ' + FILE + ' directly.');
      return;
    }

    const prev = el.innerHTML;
    const box = document.createElement('div');
    box.className = 'ci-box';
    const ta = document.createElement('textarea');
    ta.className = 'ci-input';
    ta.value = value;
    ta.rows = Math.min(14, Math.max(2, Math.ceil(value.length / 46)));
    const row = document.createElement('div');
    row.className = 'ci-row';
    row.innerHTML = '<span class="ci-path">' + esc(path) + '</span>' +
                    '<button class="ci-btn ci-save">Save</button>' +
                    '<button class="ci-btn ci-cancel">Cancel</button>';
    box.appendChild(ta); box.appendChild(row);
    el.innerHTML = '';
    el.appendChild(box);
    ta.focus();
    ta.setSelectionRange(ta.value.length, ta.value.length);

    const close = function () { el.innerHTML = prev; closeOpen = null; };
    closeOpen = close;
    row.querySelector('.ci-cancel').addEventListener('click', function (ev) {
      ev.stopPropagation(); close();
    });
    row.querySelector('.ci-save').addEventListener('click', function (ev) {
      ev.stopPropagation();
      const next = ta.value;
      if (next !== getPath(source, path)) { draft[path] = next; persist(); }
      else { delete draft[path]; persist(); }
      close();
      rerender();
      bar();
    });
    ta.addEventListener('keydown', function (ev) {
      if (ev.key === 'Escape') { ev.stopPropagation(); close(); }
      // Ctrl/Cmd+Enter saves, since Enter has to insert a line in a verse.
      if (ev.key === 'Enter' && (ev.metaKey || ev.ctrlKey)) {
        ev.preventDefault(); row.querySelector('.ci-save').click();
      }
    });
    ta.addEventListener('click', function (ev) { ev.stopPropagation(); });
  }

  /* The page draws itself from its own config object, so staged edits are
     applied there and the page asked to redraw — the reader sees the edit in
     place, in the real layout, rather than in a preview pane. */
  function rerender() {
    const target = window.SITE_CONFIG;
    if (target) Object.keys(draft).forEach(function (p) { setPath(target, p, draft[p]); });
    if (typeof window.dgeContentRerender === 'function') window.dgeContentRerender();
    if (editing) mark();
  }

  // data-edit-quiet once excluded sacred verse text (the vandana śloka, a
  // mantra) from click-to-edit entirely, so it wouldn't read as a form
  // field. 31 Aug 2026, project-lead report: "the actual śloka which
  // appears below the saint's photo … is not editable" — the exclusion
  // made the one line an editor most plausibly needs to correct the one
  // line the tool refused to touch. Quiet fields are now fully editable in
  // edit mode like everything else; the attribute is kept only so a future
  // styling pass could still render their outline more discreetly.
  var EDITABLE_SEL = '[data-edit]';

  function mark() {
    document.querySelectorAll(EDITABLE_SEL).forEach(function (el) {
      el.classList.toggle('ci-on', editing);
      el.classList.toggle('ci-dirty',
        editing && Object.prototype.hasOwnProperty.call(draft, el.getAttribute('data-edit')));
    });
  }

  /* -------------------------------------------------------------- bar ---- */
  // Collapsed by default: a slim tab on the left edge showing just "EDIT",
  // so the tool does not sit permanently over page content or the bottom
  // "Enter" button. A right arrow expands it into the full toolbar.
  let expanded = false;

  // dge/index.html already has a right-edge control rail (#dge-qa-tab /
  // #quickActionsPopup) -- on that page a "✎ Edit Page Text" row in the
  // popup is the entry point instead of a second always-on floating pill.
  // Pages with no rail (the landing page, home-panel.html) keep the
  // floating pill as their only way in -- see the boot section below.
  var hasRail = !!document.getElementById('dge-qa-tab');

  // Draggable position: which edge it's docked to, and how far down the
  // viewport (0-1, of the vertical center). Was fixed at left/50% with no
  // way to move it out from behind page content it happened to sit over
  // (e.g. the bottom Enter button on some viewport heights). Persisted per
  // device so it doesn't reset to center every visit.
  var POS_KEY = 'dge.ciBarPos';
  function loadPos() {
    try {
      var p = JSON.parse(localStorage.getItem(POS_KEY) || 'null');
      if (p && (p.side === 'left' || p.side === 'right') && typeof p.topFrac === 'number') return p;
    } catch (e) { /* fall through to default */ }
    return { side: 'left', topFrac: 0.5 };
  }
  function savePos(p) { try { localStorage.setItem(POS_KEY, JSON.stringify(p)); } catch (e) { /* ignore */ } }
  var pos = loadPos();

  function applyPos(el) {
    el.classList.toggle('ci-right', pos.side === 'right');
    var h = el.getBoundingClientRect().height || 60;
    var half = h / 2;
    var top = Math.min(Math.max(pos.topFrac * window.innerHeight, half + 4), window.innerHeight - half - 4);
    el.style.top = top + 'px';
    el.style.transform = 'none'; // the CSS translateY(-50%) default is only for pre-JS/no-saved-position paint
  }

  // Pointer-drag wiring, attached once per element (bar() itself can be
  // called many times per second while dirty-count updates). A short
  // movement threshold keeps a plain tap on the collapsed pill (which
  // toggles expand/collapse) from being swallowed as an accidental drag.
  function wireDrag(el) {
    var dragging = false, moved = false, justDragged = false, startX = 0, startY = 0, startTop = 0;
    // Measured once per drag (in pointerdown) rather than read fresh on
    // every single pointermove -- it was the actual cause of the reported
    // "laggy" touch drag. getBoundingClientRect() forces the browser to
    // flush layout synchronously, and immediately after every previous
    // pointermove had just written a new el.style.top, that flush was
    // real, unavoidable work — not free. On a phone, doing that on every
    // one of a touch drag's many pointermove events (far more than 60/sec
    // on some devices) is exactly what shows up as jank a finger can feel
    // trailing behind. The bar's height cannot change mid-drag (expand/
    // collapse is a separate action, never triggered while dragging), so
    // there is nothing to re-measure.
    var dragHeight = 0;
    // Also batches the actual style write to one per animation frame via
    // requestAnimationFrame, rather than one write (and the paint it can
    // trigger) per pointermove — a touchscreen can report move events
    // faster than the display refreshes, and only the latest position
    // before the next paint is ever going to be visible anyway.
    var rafPending = false, pendingDy = 0, pendingClientX = 0;
    // Movement is tracked via listeners on `document`, not on `el` itself,
    // and setPointerCapture is deliberately never used here. The collapsed
    // pill is only ~28px wide, so a normal-speed drag leaves its bounds
    // between one pointermove event and the next — an el-scoped listener
    // (without capture) would miss every event after the first, and
    // setPointerCapture, tried first, turned out to fix that at the cost of
    // a worse bug: it redirects the click that follows ANY pointerdown+
    // pointerup pair (moved or not) from its real target (e.g. the .ci-pill
    // button) to the capturing element, silently breaking the pill's own
    // click-to-expand handler on every plain tap, not just drags.
    // document-level tracking needs no capture at all: the actual target
    // element only matters for the click that follows, which document
    // listeners never touch.
    el.addEventListener('click', function (ev) {
      // A real drag still fires a native click on release (same element,
      // pointerdown+pointerup with no intervening navigation) — without
      // this it would also toggle expand/collapse as an unwanted side
      // effect of just repositioning the tool.
      if (justDragged) { ev.stopImmediatePropagation(); ev.preventDefault(); }
    }, true);
    el.addEventListener('pointerdown', function (ev) {
      if (ev.target.closest('button') && !ev.target.closest('.ci-pill')) return; // let toolbar buttons work untouched
      dragging = true; moved = false;
      startX = ev.clientX; startY = ev.clientY;
      var rect = el.getBoundingClientRect();
      startTop = rect.top; dragHeight = rect.height; // the only reads for the whole drag
      document.addEventListener('pointermove', onMove);
      document.addEventListener('pointerup', onUp);
      document.addEventListener('pointercancel', onUp);
    });
    function applyPendingMove() {
      rafPending = false;
      if (!dragging) return;
      var half = dragHeight / 2;
      var newTop = Math.min(Math.max(startTop + pendingDy, 4), window.innerHeight - dragHeight - 4);
      el.style.top = (newTop + half) + 'px';
      el.style.left = ''; el.style.right = '';
      // Live-preview which edge it would dock to on release, purely visual.
      el.classList.toggle('ci-right', pendingClientX > window.innerWidth / 2);
    }
    function onMove(ev) {
      if (!dragging) return;
      var dx = ev.clientX - startX, dy = ev.clientY - startY;
      if (!moved && Math.hypot(dx, dy) < 6) return; // still within click tolerance
      moved = true;
      el.classList.add('ci-dragging');
      pendingDy = dy; pendingClientX = ev.clientX;
      if (!rafPending) { rafPending = true; requestAnimationFrame(applyPendingMove); }
    }
    function onUp(ev) {
      if (!dragging) return;
      dragging = false;
      document.removeEventListener('pointermove', onMove);
      document.removeEventListener('pointerup', onUp);
      document.removeEventListener('pointercancel', onUp);
      el.classList.remove('ci-dragging');
      if (!moved) return; // a plain click/tap — let the pill's own click handler run
      moved = false;
      justDragged = true;
      setTimeout(function () { justDragged = false; }, 0); // cleared after this tick's click, if any, is swallowed
      // dragHeight is still accurate here -- nothing can have resized the
      // bar mid-drag -- so this is the one real read needed on release.
      var topCenter = el.getBoundingClientRect().top + dragHeight / 2;
      pos = {
        side: ev.clientX > window.innerWidth / 2 ? 'right' : 'left',
        topFrac: Math.min(Math.max(topCenter / window.innerHeight, 0), 1)
      };
      savePos(pos);
      applyPos(el);
    }
  }

  function bar() {
    let el = document.getElementById('ciBar');
    const n = Object.keys(draft).length;
    // Always present for a super-admin: the bar carries the only control that
    // turns editing on, so hiding it when nothing is staged left no way in.
    let isNew = false;
    if (!el) {
      el = document.createElement('div');
      el.id = 'ciBar';
      document.body.appendChild(el);
      document.body.classList.add('ci-active');
      isNew = true;
    }
    el.className = 'ci-bar ' + (expanded ? 'ci-expanded' : 'ci-collapsed') + (pos.side === 'right' ? ' ci-right' : '');
    if (isNew) wireDrag(el);

    if (!expanded) {
      el.innerHTML =
        '<button class="ci-pill" aria-expanded="false" aria-label="Open the edit tool">' +
          (n ? '<span class="ci-badge">' + n + '</span>' : '') +
          '<span class="ci-shine">EDIT</span>' +
          '<span class="ci-chevron" aria-hidden="true">' + (pos.side === 'right' ? '‹' : '›') + '</span>' +
        '</button>';
      el.querySelector('.ci-pill').addEventListener('click', function () {
        expanded = true; bar();
      });
      applyPos(el);
      return;
    }

    // The file name up front, always -- so "where does this text live" has
    // an answer on screen before an admin even clicks anything, rather than
    // only implicitly via the per-field ci-path label once editing starts.
    el.innerHTML =
      '<button class="ci-chevron-btn" aria-label="Collapse the edit tool">‹</button>' +
      '<span class="ci-file" title="Editing this file">' + esc(FILE) + '</span>' +
      '<span class="ci-count">' + (n ? n + ' unpublished edit' + (n === 1 ? '' : 's') +
        ' — in this browser only' : 'Click on the highlighted text to edit and save.') + '</span>' +
      (n ? '<button class="ci-btn ci-publish">Publish</button>' +
           '<button class="ci-btn ci-discard">Discard</button>' : '') +
      '<button class="ci-btn ci-done">' + (editing ? 'Done' : 'Edit text') + '</button>';

    el.querySelector('.ci-chevron-btn').addEventListener('click', function () {
      expanded = false; bar();
    });

    const pub = el.querySelector('.ci-publish');
    if (pub) pub.addEventListener('click', function () {
      pub.disabled = true; pub.textContent = 'Publishing…';
      publish().then(function (done) {
        if (done) {
          alert('Published. GitHub has the change now.\n\nThe live site is served ' +
                'through a CDN that can take a few minutes to catch up — if a ' +
                'refresh still shows the old text, that is the delay, not a ' +
                'failed save.');
          rerender(); bar();
        } else { pub.disabled = false; pub.textContent = 'Publish'; }
      }).catch(function (e) {
        alert('Could not publish: ' + e.message);
        pub.disabled = false; pub.textContent = 'Publish';
      });
    });
    const dis = el.querySelector('.ci-discard');
    if (dis) dis.addEventListener('click', function () {
      if (!confirm('Discard ' + n + ' unpublished edit(s)?')) return;
      clearDraft(); location.reload();
    });
    el.querySelector('.ci-done').addEventListener('click', function () {
      editing = !editing; mark(); bar();
    });
    applyPos(el);
  }

  document.addEventListener('click', function (ev) {
    if (!editing) return;
    const el = ev.target.closest && ev.target.closest(EDITABLE_SEL);
    if (!el || el.querySelector('.ci-box')) return;
    ev.preventDefault(); ev.stopPropagation();
    openEditor(el);
  }, true);

  /* -------------------------------------------------------------- boot --- */
  function allowed() {
    try { return localStorage.getItem('is_superadmin') === 'true'; }
    catch (e) { return false; }
  }

  window.dgeContentInlineReady = (function () {
    if (!allowed()) return Promise.resolve(false);
    restore();
    return loadSource().then(function (doc) {
      if (!doc) return false;
      source = doc;
      // Staged edits are already in the page's config from its own boot only
      // if it read them; apply them here so the page shows the draft.
      if (Object.keys(draft).length) rerender();
      // On a page with the control rail, bar() is deferred until the rail's
      // "Edit Page Text" row asks for it (see dgeToggleContentInlineBar)
      // instead of always showing the floating collapsed pill.
      if (!hasRail) bar();
      return true;
    }).catch(function () { return false; });
  })();

  // Called by the rail's pop-item. Not defined until dgeContentInlineReady
  // resolves true, same gate as the rest of this file's public surface.
  window.dgeToggleContentInlineBar = function () {
    if (!source) return; // not a super-admin, or still loading
    expanded = !expanded;
    bar();
  };
})();
