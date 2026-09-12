/* =========================================================================
   The guided walkthrough.

   A reader arriving for the first time has no way to discover that
   double-tapping a word explains it, that the number at the end of a verse
   lists its commentators, or that a half-remembered sūtra name typed into the
   search box will be identified. None of that announces itself, and a video
   would go stale the moment anything moved.

   So the page teaches itself: everything dims, one thing lights up, a card
   says what it is, and Next moves on.

   The steps are admin/content/tour.json — wording, order and what each one
   points at, all editable in place like the rest of the site's text.

   A step whose target is not on the page is skipped rather than shown
   pointing at nothing. That is not an edge case: admin/config/menu.json can
   switch a menu item off, and the admin controls do not exist at all for an
   ordinary reader, so the tour has to describe the site THIS person can see.
   ========================================================================= */
(function () {
  'use strict';

  window.DGE_VERSIONS = window.DGE_VERSIONS || {};
  window.DGE_VERSIONS['tour.js'] = 'v1.0 (guided walkthrough)';

  const SEEN_KEY = 'dge_tour_seen';
  const self = (document.currentScript && document.currentScript.src) || '';

  function contentUrl() {
    try { return new URL('../../admin/content/tour.json', self).href; }
    catch (e) { return '../admin/content/tour.json'; }
  }

  const esc = (s) => String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');

  let cfg = null;
  let steps = [];          // only those whose target is actually present
  let at = 0;
  let el = null;           // the overlay, while running

  function visible(node) {
    if (!node) return false;
    const r = node.getBoundingClientRect();
    if (!r.width && !r.height) return false;
    const cs = getComputedStyle(node);
    return cs.display !== 'none' && cs.visibility !== 'hidden';
  }

  function resolve(step) {
    if (!step.target) return null;              // a page-level step
    const node = document.querySelector(step.target);
    return visible(node) ? node : undefined;    // undefined = skip this step
  }

  function usable(all) {
    return all.filter(function (s) { return resolve(s) !== undefined; });
  }

  /* ------------------------------------------------------------ drawing -- */
  function draw() {
    const step = steps[at];
    const node = resolve(step);

    el.querySelector('.tour-title').innerHTML = esc(step.title || '');
    el.querySelector('.tour-body').innerHTML = esc(step.body || '');
    el.querySelector('.tour-count').textContent = (at + 1) + ' / ' + steps.length;
    el.querySelector('.tour-back').disabled = at === 0;
    el.querySelector('.tour-next').textContent = (at === steps.length - 1) ? 'Done' : 'Next';

    const hole = el.querySelector('.tour-hole');
    const card = el.querySelector('.tour-card');

    if (!node) {
      // No target: dim everything and centre the card.
      hole.style.display = 'none';
      card.className = 'tour-card tour-card-centre';
      card.style.top = card.style.left = card.style.width = '';
      return;
    }

    // Bring the target into view first, then measure — measuring before the
    // scroll settles puts the spotlight where the element used to be.
    node.scrollIntoView({ block: 'center', behavior: 'auto' });
    const r = node.getBoundingClientRect();
    const pad = 6;
    hole.style.display = 'block';
    hole.style.top = (r.top - pad) + 'px';
    hole.style.left = (r.left - pad) + 'px';
    hole.style.width = (r.width + pad * 2) + 'px';
    hole.style.height = (r.height + pad * 2) + 'px';

    // Below the target if there is room, above if not — unless the step says.
    const cardH = 190;
    const below = step.placement === 'bottom' ||
      (step.placement !== 'top' && r.bottom + cardH + 20 < window.innerHeight);
    card.className = 'tour-card';
    const w = Math.min(360, window.innerWidth - 24);
    card.style.width = w + 'px';
    card.style.left = Math.max(12, Math.min(r.left + r.width / 2 - w / 2,
                                            window.innerWidth - w - 12)) + 'px';
    card.style.top = below ? (r.bottom + 14) + 'px' : '';
    card.style.bottom = below ? '' : (window.innerHeight - r.top + 14) + 'px';
    if (below) card.style.bottom = '';
  }

  function go(n) {
    if (n < 0 || n >= steps.length) return;
    at = n;
    draw();
  }

  function finish() {
    try { localStorage.setItem(SEEN_KEY, '1'); } catch (e) {}
    if (el) { el.remove(); el = null; }
    document.body.classList.remove('tour-running');
    window.removeEventListener('resize', draw);
    document.removeEventListener('keydown', onKey);
  }

  function onKey(ev) {
    if (!el) return;
    if (ev.key === 'Escape') { ev.preventDefault(); finish(); }
    if (ev.key === 'ArrowRight' || ev.key === 'Enter') { ev.preventDefault(); next(); }
    if (ev.key === 'ArrowLeft') { ev.preventDefault(); go(at - 1); }
  }

  function next() {
    if (at === steps.length - 1) finish(); else go(at + 1);
  }

  function build() {
    el = document.createElement('div');
    el.className = 'tour';
    el.innerHTML =
      '<div class="tour-hole"></div>' +
      '<div class="tour-card">' +
        '<div class="tour-title"></div>' +
        '<p class="tour-body"></p>' +
        '<div class="tour-foot">' +
          '<span class="tour-count"></span>' +
          '<button class="tour-btn tour-skip">Skip</button>' +
          '<button class="tour-btn tour-back">Back</button>' +
          '<button class="tour-btn tour-next">Next</button>' +
        '</div>' +
      '</div>';
    document.body.appendChild(el);
    document.body.classList.add('tour-running');

    el.querySelector('.tour-skip').addEventListener('click', finish);
    el.querySelector('.tour-back').addEventListener('click', function () { go(at - 1); });
    el.querySelector('.tour-next').addEventListener('click', next);
    // Clicking the dim area advances; clicking the lit element does not, so a
    // stray tap on what is being explained never skips past the explanation.
    el.addEventListener('click', function (ev) {
      if (ev.target === el) next();
    });
    window.addEventListener('resize', draw);
    document.addEventListener('keydown', onKey);
  }

  /* --------------------------------------------------------------- api --- */
  window.dgeStartTour = function () {
    if (el) return;
    const load = cfg ? Promise.resolve(cfg)
      : fetch(contentUrl() + '?t=' + Date.now(), { cache: 'no-store' })
          .then(r => (r.ok ? r.json() : null));
    return load.then(function (doc) {
      if (!doc || !Array.isArray(doc.steps) || !doc.steps.length) {
        if (typeof window.showToast === 'function') {
          window.showToast('The walkthrough could not be loaded.');
        }
        return false;
      }
      cfg = doc;
      steps = usable(doc.steps);
      if (!steps.length) return false;
      at = 0;
      build();
      draw();
      return true;
    }).catch(function () { return false; });
  };

  window.dgeTourSeen = function () {
    try { return localStorage.getItem(SEEN_KEY) === '1'; } catch (e) { return true; }
  };

  /* -------------------------------------------------------------- boot --- */
  // Offered once, and only after the page has settled — starting a tour over a
  // half-rendered page would spotlight things that are about to move.
  //
  // It also has to wait its turn. The About panel opens itself on a first
  // visit, which is exactly when the tour wants to run, and a single delayed
  // check meant whichever won the race silenced the other for good. So this
  // waits for a clear screen, and gives up quietly rather than interrupting
  // someone who is evidently already reading something.
  function maybeAutoStart() {
    if (window.dgeTourSeen()) return;
    fetch(contentUrl() + '?t=' + Date.now(), { cache: 'no-store' })
      .then(r => (r.ok ? r.json() : null))
      .then(function (doc) {
        if (!doc || doc.autoStart === false) return;
        cfg = doc;
        let waited = 0;
        const tick = setInterval(function () {
          waited += 900;
          if (el) { clearInterval(tick); return; }        // already running
          // A reader who has just selected a word/phrase and is looking at
          // the selection tooltip (Shabda/Dhātu/Search Library/...) is just
          // as "busy" as one with a modal open -- confirmed live: without
          // this check, the tour's full-page dimmed backdrop could start
          // right under a pending tap on one of those buttons, silently
          // swallowing the click (the backdrop, not the button, is what
          // actually receives the pointerdown) with nothing on screen to
          // explain why the tap seemed to do nothing.
          const actionTooltip = document.getElementById('actionTooltip');
          const busy = document.querySelector('.modal-overlay[style*="flex"]') ||
            (actionTooltip && actionTooltip.style.display === 'flex');
          if (!busy) { clearInterval(tick); window.dgeStartTour(); return; }
          if (waited > 30000) clearInterval(tick);        // they are busy; leave them be
        }, 900);
      })
      .catch(function () {});
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', maybeAutoStart);
  } else {
    maybeAutoStart();
  }
})();
