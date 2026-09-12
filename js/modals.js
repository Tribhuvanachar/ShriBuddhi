// DGE Module: modals.js
// Maps to F-012: ModalsUI

// Register Module Version
window.DGE_VERSIONS = window.DGE_VERSIONS || {};
window.DGE_VERSIONS['modals.js'] = 'v1.5 ("NEW" badges on recently-added Admin dropdown items)';

// A .drawer-left/.drawer-right modal-overlay (see main.css) needs to
// animate in via a show/hide class instead of a plain display:none<->flex
// snap, so its slide-in transition actually has something to transition
// from. Every other modal keeps the original display-toggle behaviour --
// this only branches for the two drawer classes.
function dgeIsDrawer(modal) {
  return modal.classList.contains('drawer-left') || modal.classList.contains('drawer-right');
}

function openModal(id) {
  const modal = document.getElementById(id);
  if (modal) {
    if (dgeIsDrawer(modal)) {
      modal.style.display = 'flex';
      void modal.offsetWidth; // force layout so .show's transition runs from the off-screen state
      modal.classList.add('show');
    } else {
      modal.style.display = 'flex';
    }
    document.body.classList.add('modal-open');
    if (window.DGE_DEV_LOG && window.DGE_DEV_LOG.recenterPill) window.DGE_DEV_LOG.recenterPill();
  }
}

function closeModal(id) {
  const modal = document.getElementById(id);
  if (modal) {
    if (dgeIsDrawer(modal)) {
      modal.classList.remove('show');
      // display:none only after the slide-out finishes, so it's visible while animating;
      // the timeout is a fallback in case transitionend doesn't fire (e.g. display changed mid-transition elsewhere).
      window.setTimeout(() => { if (!modal.classList.contains('show')) modal.style.display = 'none'; }, 320);
    } else {
      modal.style.display = 'none';
    }
    document.body.classList.remove('modal-open');
  }
}

// "NEW" badges on recently-added Admin dropdown items -- easy to forget a
// link like Audio Admin ever got added at all once it's just one more row
// among many. Each entry here shows its badge (with the blink animation
// already in css/main.css) until the user has opened this menu once WHILE
// it's visible; add a new {itemId, badgeId} pair whenever an admin-only
// feature ships, and remove it once it's no longer worth flagging.
const NEW_ADMIN_FEATURES = [
  { itemId: 'adminAudioManagerItem', badgeId: 'adminAudioManagerBadge' }
];
const NEW_FEATURES_SEEN_KEY = 'dge_admin_new_features_seen';
function markNewFeatureBadges() {
  let seen;
  try { seen = JSON.parse(localStorage.getItem(NEW_FEATURES_SEEN_KEY)) || []; } catch (e) { seen = []; }
  const seenSet = new Set(seen);
  let sawAnyNew = false;
  NEW_ADMIN_FEATURES.forEach(({ itemId, badgeId }) => {
    const item = document.getElementById(itemId);
    const badge = document.getElementById(badgeId);
    if (!item || !badge || item.style.display === 'none') return; // not unlocked for this user yet
    if (seenSet.has(itemId)) { badge.style.display = 'none'; return; }
    badge.style.display = 'inline-block';
    sawAnyNew = true;
    seenSet.add(itemId); // don't show again on a future page load, once they've had this one chance to notice it
  });
  if (sawAnyNew) {
    try { localStorage.setItem(NEW_FEATURES_SEEN_KEY, JSON.stringify(Array.from(seenSet))); } catch (e) { /* storage full — non-fatal, badge just repeats next time */ }
  }
}

function togglePopup(id) {
  // Close all other open popups first
  document.querySelectorAll('.popup').forEach(p => {
    if (p.id !== id) p.classList.remove('show');
  });

  // Toggle the requested popup
  const target = document.getElementById(id);
  if (target) {
    const isOpening = !target.classList.contains('show');
    target.classList.toggle('show');
    // Keeps the floating dev-log pill from ever sitting on top of a
    // popup that was just opened — see DGE_DEV_LOG.recenterPill in utils.js.
    if (isOpening && window.DGE_DEV_LOG && window.DGE_DEV_LOG.recenterPill) {
      window.DGE_DEV_LOG.recenterPill();
    }
    if (isOpening && id === 'adminToolsPopup') markNewFeatureBadges();
  }
}

// Global click listener to close popups when tapping outside
document.addEventListener('click', (e) => {
  if (!e.target.closest('.popup-container') && !e.target.closest('.popup') && !e.target.closest('.top-actions')) {
    document.querySelectorAll('.popup').forEach(p => p.classList.remove('show'));
  }
});

// Tapping the dimmed backdrop of an off-canvas drawer closes it -- standard
// drawer behaviour everywhere this pattern is used. Only drawers get this:
// e.target === the overlay itself means the tap landed outside .modal-content
// (a tap inside it stops there, same as clicking real content in any modal).
document.addEventListener('click', (e) => {
  if (e.target.classList && e.target.classList.contains('modal-overlay') && dgeIsDrawer(e.target)) {
    // 7 Sep 2026: a pinned Library stays put when the tap lands outside it
    // (the lead: "when pinned, it should stick to its place even if clicked
    // outside of it"); only its own ❮ button closes it.
    if (e.target.id === 'libraryModal' && typeof window.dgeLibraryDocked === 'function' && window.dgeLibraryDocked()) return;
    closeModal(e.target.id);
  }
});

window.openAboutModal = function() {
  dgeRenderAboutIntro();
  const contribEl = document.getElementById('contributorsSection');
  if (contribEl) {
    const cfg = (typeof CONTRIBUTORS_CONFIG !== 'undefined') ? CONTRIBUTORS_CONFIG : null;
    const list = (cfg && cfg.enabled && Array.isArray(cfg.contributors)) ? cfg.contributors : [];
    if (list.length) {
      contribEl.innerHTML = `
        <div class="actions-section-label" style="margin-top:20px;">🙏 Contributors</div>
        <div style="display:flex; flex-direction:column; gap:6px;">
          ${list.map(c => `
            <div style="display:flex; justify-content:space-between; font-size:12px;">
              <span style="font-weight:700;">${c.name}</span>
              <span style="color:var(--muted-text);">${c.role || ''}</span>
            </div>`).join('')}
        </div>`;
    } else {
      contribEl.innerHTML = '';
    }
  }

  const sponsorsEl = document.getElementById('keySponsorsSection');
  if (sponsorsEl) {
    const sCfg = (typeof KEY_SPONSORS_CONFIG !== 'undefined') ? KEY_SPONSORS_CONFIG : null;
    const sList = (sCfg && sCfg.enabled && Array.isArray(sCfg.sponsors)) ? sCfg.sponsors : [];
    if (sList.length) {
      sponsorsEl.innerHTML = `
        <div class="actions-section-label" style="margin-top:20px;">💝 Key Sponsors</div>
        <div style="display:flex; flex-direction:column; gap:8px;">
          ${sList.map(s => `
            <div>
              <div style="font-size:12px; font-weight:700;">${s.name}</div>
              <div style="font-size:11px; color:var(--muted-text);">${s.contribution || ''}</div>
            </div>`).join('')}
        </div>`;
    } else {
      sponsorsEl.innerHTML = '';
    }
  }

  openModal('aboutModal');
  localStorage.setItem('has_seen_welcome', 'true');
};

// First-visit welcome — shows the same About modal automatically once,
// after the app has finished loading its data (so the title/content
// behind it isn't jarring). Never shows again after that unless the
// person clears site data.
document.addEventListener('DOMContentLoaded', () => {
  if (localStorage.getItem('has_seen_welcome') !== 'true') {
    setTimeout(() => {
      if (typeof stotraData !== 'undefined' && stotraData) window.openAboutModal();
    }, 900);
  }
});

// Reader redesign, section 13 ("remove wasted space" at the top of the
// page): the "💝 Support This Project" button used to sit inline in the
// header, above the search bar — one more thing between opening the page
// and reaching the text. It now surfaces inside the About panel instead
// (dgeRenderAboutIntro, below), reachable from the ☰ menu exactly as
// before, just no longer competing with title/search/text for the first
// screen's vertical space. Same SPONSOR_CONFIG.enabled admin gate as
// before — see dgeRenderAboutIntro for where this is actually rendered.

// Local escape helper for the functions below — dgeModalsEsc (further down
// this file) does the same job but is defined after these, and hoisting a
// function declaration is more reliable here than relying on load order.
function dgeAboutEsc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// admin/content/home.json, fetched lazily and only once -- most visitors
// never open a profile panel, so this shouldn't cost a request at boot.
let dgeHomeContentPromise = null;
function dgeFetchHomeContent() {
  if (!dgeHomeContentPromise) {
    dgeHomeContentPromise = fetch('../admin/content/home.json?t=' + Date.now(), { cache: 'no-store' })
      .then(r => (r.ok ? r.json() : null))
      .catch(() => null);
  }
  return dgeHomeContentPromise;
}

// Same shape as home.json's panels{} (eyebrow/title/reverence/body/
// groups[]/closing/todo) that the landing page's own "Know More" sheet
// renders -- view-only here, since editing that file already happens
// there (or on the reader app's own reader.json-backed panels).
function dgeProfilePanelHtml(p) {
  let html = '';
  if (p.eyebrow) html += `<div style="font-size:11px; letter-spacing:.15em; text-transform:uppercase; color:var(--muted-text); margin-bottom:8px;">${dgeAboutEsc(p.eyebrow)}</div>`;
  if (p.reverence) html += `<div style="font-style:italic; font-size:13px; color:var(--muted-text); margin-bottom:16px;">${dgeAboutEsc(p.reverence)}</div>`;
  if (p.body) html += `<p style="font-size:13.5px; line-height:1.7; margin:0 0 16px;">${dgeAboutEsc(p.body)}</p>`;
  (p.groups || []).forEach(g => {
    if (g.heading) html += `<div style="margin:20px 0 10px; font-weight:700; font-size:13px; color:var(--accent-red);">${dgeAboutEsc(g.heading)}</div>`;
    (g.entries || []).forEach(e => {
      html += `<div style="margin-bottom:12px;"><b style="font-size:13px;">${dgeAboutEsc(e.name || '')}</b>`;
      if (e.note) html += `<div style="font-size:12.5px; color:var(--muted-text); line-height:1.55; margin-top:2px;">${dgeAboutEsc(e.note)}</div>`;
      if (e.also) html += `<div style="font-size:12px; color:var(--muted-text); font-style:italic; margin-top:2px;">${dgeAboutEsc(e.also)}</div>`;
      html += '</div>';
    });
    if (g.names && g.names.length) {
      html += `<div style="font-size:12.5px; color:var(--muted-text); margin-bottom:8px;">${g.names.map(n => dgeAboutEsc(n)).join(' · ')}</div>`;
    }
  });
  if (p.closing) html += `<p style="font-size:13px; font-style:italic; margin-top:18px; color:var(--muted-text);">${dgeAboutEsc(p.closing)}</p>`;
  if (p.todo) html += `<p style="font-size:12px; color:var(--muted-text); font-style:italic; margin-top:12px;">${dgeAboutEsc(p.todo)}</p>`;
  return html;
}

window.openProfilePanel = function(key) {
  const title = document.getElementById('profileSheetTitle');
  const body = document.getElementById('profileSheetBody');
  if (!title || !body) return;
  title.textContent = '';
  body.innerHTML = '<p style="color:var(--muted-text); font-size:13px;">Loading…</p>';
  window.openModal('profileSheetModal');
  dgeFetchHomeContent().then(function(cfg) {
    const p = cfg && cfg.panels && cfg.panels[key];
    if (!p) {
      body.innerHTML = '<p style="color:var(--muted-text); font-size:13px;">Could not load this page.</p>';
      return;
    }
    title.textContent = p.title || '';
    body.innerHTML = dgeProfilePanelHtml(p);
  });
};

// About This Project's opening paragraph and "Designed By" line, and Our
// Story's full bio — admin/content/reader.json's `about`/`ourStory` keys.
// Rendered into these two functions (not baked into render.html) so a
// super admin's content-inline.js edit here actually has a data-edit path
// pointing somewhere: what "which file, which field" the edit tool's own
// ci-path label already shows the moment you click the text to change it.
function dgeRenderAboutIntro() {
  const cfg = window.SITE_CONFIG;
  const about = (cfg && cfg.about) || {};
  const intro = document.getElementById('aboutIntroSection');
  if (intro) {
    intro.innerHTML = `<p data-edit="about.intro" style="font-size:13px; line-height:1.6; margin:0 0 16px 0;">${dgeAboutEsc(about.intro || '')}</p>`;
  }
  const designed = document.getElementById('aboutDesignedBySection');
  if (designed) {
    const supportHtml = (typeof SPONSOR_CONFIG !== 'undefined' && SPONSOR_CONFIG && SPONSOR_CONFIG.enabled)
      ? `<button class="btn-sm" style="width:100%; margin-top:16px;" onclick="window.closeModal('aboutModal'); window.openSponsorModal();">💝 Support This Project</button>`
      : '';
    designed.innerHTML = `<div class="actions-section-label" style="margin-top:20px;">🕉️ Designed By</div>
      <p data-edit="about.designedBy" style="font-size:12px; color:var(--muted-text); margin:0;">${dgeAboutEsc(about.designedBy || '')}</p>
      ${supportHtml}`;
  }
}

// Why -> Beginning -> Growth -> How it's built -> Vision -> Founder ->
// Guru/Ācārya gratitude -> Our hope. Sarvamūla's own story first, in full;
// the founder gets a short closing mention with a link to his own, much
// more personal Gurus/Blessers/Inspirers material (home.json's
// `panels.tribhuvan`) via openProfilePanel() -- a same-page modal swap,
// not a navigation, so there is nothing to flash and no "Back" link that
// can send you somewhere other than back to what you were reading.
function dgeRenderOurStory() {
  const cfg = window.SITE_CONFIG;
  const story = (cfg && cfg.ourStory) || {};
  const el = document.getElementById('ourStorySection');
  if (!el) return;

  let html = `<div data-edit="ourStory.subtitle" style="text-align:center; font-size:13px; color:var(--muted-text); font-style:italic; margin:4px 0 22px;">${dgeAboutEsc(story.subtitle || '')}</div>`;

  (story.sections || []).forEach((sec, si) => {
    if (sec.heading) {
      html += `<h4 data-edit="ourStory.sections.${si}.heading" style="margin:26px 0 10px; font-size:14.5px; color:var(--accent-red);">${dgeAboutEsc(sec.heading)}</h4>`;
    }
    (sec.paragraphs || []).forEach((p, pi) => {
      html += `<p data-edit="ourStory.sections.${si}.paragraphs.${pi}" style="font-size:13.5px; line-height:1.7; margin:0 0 14px 0;">${dgeAboutEsc(p)}</p>`;
    });
  });

  const founder = story.founder || {};
  if (founder.heading) {
    html += `<h4 data-edit="ourStory.founder.heading" style="margin:26px 0 10px; font-size:14.5px; color:var(--accent-red);">${dgeAboutEsc(founder.heading)}</h4>`;
  }
  (founder.paragraphs || []).forEach((p, pi) => {
    html += `<p data-edit="ourStory.founder.paragraphs.${pi}" style="font-size:13.5px; line-height:1.7; margin:0 0 14px 0;">${dgeAboutEsc(p)}</p>`;
  });
  html += `<button class="btn-sm" style="width:100%; margin-bottom:16px;" onclick="window.closeModal('ourStoryModal'); window.openProfilePanel('${dgeAboutEsc(founder.meetFounderPanel || 'tribhuvan')}')">
      <span data-edit="ourStory.founder.meetFounderLabel">${dgeAboutEsc(founder.meetFounderLabel || 'Meet the Founder →')}</span>
    </button>`;
  if (founder.gratitude) {
    html += `<p data-edit="ourStory.founder.gratitude" style="font-size:13px; line-height:1.7; margin:0 0 8px 0; color:var(--muted-text);">${dgeAboutEsc(founder.gratitude)}</p>`;
  }
  if (founder.names) {
    html += `<p data-edit="ourStory.founder.names" style="font-size:13px; text-align:center; margin:0 0 20px 0;">${dgeAboutEsc(founder.names)}</p>`;
  }

  const hope = story.hope || {};
  if (hope.heading) {
    html += `<h4 data-edit="ourStory.hope.heading" style="margin:26px 0 10px; font-size:14.5px; color:var(--accent-red);">${dgeAboutEsc(hope.heading)}</h4>`;
  }
  (hope.lines || []).forEach((line, li) => {
    html += `<p data-edit="ourStory.hope.lines.${li}" style="font-size:13.5px; line-height:1.7; margin:0 0 10px 0; font-style:italic;">${dgeAboutEsc(line)}</p>`;
  });

  if (story.mantra) {
    html += `<p data-edit="ourStory.mantra" style="text-align:center; font-size:14px; font-weight:700; margin:22px 0 4px;">${dgeAboutEsc(story.mantra)}</p>`;
  }

  el.innerHTML = html;
}

window.openOurStoryModal = function() {
  dgeRenderOurStory();
  window.openModal('ourStoryModal');
};

// menu.js's config-driven popup items only ever call a named window
// function with no arguments (item.action -> window.<action>()), so
// opening a specific modal by id from menu.json needs its own zero-arg
// wrapper rather than menu.json trying to pass openModal an argument.
window.dgeOpenOurStory = function() { window.openOurStoryModal(); };

// content-inline.js stages an edit into window.SITE_CONFIG and calls this
// (see js/content-inline.js) so the change appears in the real layout
// immediately rather than only after Publish + a refresh. Re-runs whichever
// of this page's own render functions actually draw from admin/content/
// reader.json; each one is cheap and safe to call even while its modal is
// closed, since they just repopulate an offscreen container.
window.dgeContentRerender = function() {
  dgeRenderAboutIntro();
  dgeRenderOurStory();
  const sponsorModal = document.getElementById('sponsorModal');
  if (sponsorModal && sponsorModal.style.display === 'flex' && typeof window.openSponsorModal === 'function') {
    window.openSponsorModal();
  }
};

window.openSponsorModal = function() {
  const body = document.getElementById('sponsorModalBody');
  if (!body || typeof SPONSOR_CONFIG === 'undefined' || !SPONSOR_CONFIG) return;
  const cfg = SPONSOR_CONFIG;
  const cur = cfg.currency || '₹';

  // data-edit names the path inside admin/content/reader.json, so a super
  // admin can correct this paragraph on the panel itself (content-inline.js).
  let html = `<p data-edit="SPONSOR_CONFIG.introText" style="font-size:13px; line-height:1.6; margin:0 0 18px 0;">${cfg.introText || ''}</p>`;

  html += `<div class="actions-section-label">📊 Recurring Expenses</div>`;
  html += `<div style="display:flex; flex-direction:column; gap:8px; margin-bottom:20px;">`;
  (cfg.recurringExpenses || []).forEach(e => {
    html += `
      <div style="display:flex; justify-content:space-between; align-items:center; padding:10px; border:1px solid var(--card-border); border-radius:var(--radius-sm);">
        <span style="font-size:12px; font-weight:600;">${e.label}</span>
        <span style="font-size:13px; font-weight:800; color:var(--accent-red); white-space:nowrap; margin-left:10px;">${cur}${e.amount.toLocaleString('en-IN')}<span style="font-size:10px; font-weight:600; color:var(--muted-text);">/${e.period}</span></span>
      </div>`;
  });
  html += `</div>`;

  html += `<div class="actions-section-label">🙏 Ways to Sponsor</div>`;
  html += `<div style="display:flex; flex-direction:column; gap:10px;">`;
  (cfg.sponsorCategories || []).filter(c => c.enabled !== false).forEach(c => {
    const subject = encodeURIComponent(`Sponsorship enquiry — ${c.label}`);
    const bodyText = encodeURIComponent(`I'd like to know more about sponsoring: ${c.label}`);
    const mailto = `mailto:${cfg.contactForSponsorship}?subject=${subject}&body=${bodyText}`;
    html += `
      <a href="${mailto}" style="display:block; padding:12px; border:1.5px solid var(--card-border); border-radius:var(--radius-sm); text-decoration:none; color:inherit;">
        <div style="font-weight:800; font-size:13px; margin-bottom:3px;">${c.icon} ${c.label}</div>
        <div style="font-size:11px; color:var(--muted-text); line-height:1.4;">${c.description}</div>
      </a>`;
  });
  html += `</div>`;

  html += `<p style="font-size:11px; color:var(--muted-text); margin-top:18px;">Tapping any option above opens an email to <strong>${cfg.contactForSponsorship}</strong> — there's no in-app payment yet, this just starts the conversation.</p>`;

  body.innerHTML = html;
  if (typeof openModal === 'function') openModal('sponsorModal');
};

// Local escape helper — config-editor.js has its own dgeEsc, but that's a
// separate file/closure and isn't reachable from here.
function dgeModalsEsc(s) {
  const d = document.createElement('div');
  d.textContent = s == null ? '' : String(s);
  return d.innerHTML;
}

// "What's New" is chronological by nature (sorted here, newest first,
// regardless of how the admin ordered them while editing) — entries
// missing a date sink to the bottom but keep their relative order among
// each other, rather than being scattered arbitrarily by a naive sort.
// "Coming Soon" has no date concept at all: its stored array order IS
// the display order, reordered manually in Site Settings to reflect
// actual priority.
function dgeSortUpdatesNewestFirst(updates) {
  return updates
    .map((u, i) => ({ u, i }))
    .sort((a, b) => {
      const ad = a.u.date, bd = b.u.date;
      if (ad && bd) return bd.localeCompare(ad);
      if (ad && !bd) return -1;
      if (!ad && bd) return 1;
      return a.i - b.i; // both undated — keep original relative order
    })
    .map(x => x.u);
}

/* Re-read on every open, uncached. This panel is the one part of the site
   whose whole purpose is to be current: baking it into a JS constant meant an
   update could only be published by changing code, and a visitor who left the
   tab open would never see it. */
window.openWhatsNewModal = function() {
  const url = (typeof window.dgeContentUrl === 'function')
    ? window.dgeContentUrl('whats-new.json') : 'admin/content/whats-new.json';
  fetch(url + '?t=' + Date.now(), { cache: 'no-store' })
    .then(r => (r.ok ? r.json() : null))
    .catch(() => null)
    .then(function (fresh) {
      if (fresh) window.WHATS_NEW_CONFIG = fresh;   // _readme kept, see core.js
      dgeRenderWhatsNew();
    });
};

function dgeRenderWhatsNew() {
  const body = document.getElementById('whatsNewBody');
  if (!body) return;
  const cfg = window.WHATS_NEW_CONFIG || null;

  if (!cfg || cfg.enabled === false ||
      (!(cfg.updates || []).length && !(cfg.comingSoon || []).length)) {
    body.innerHTML = `<p style="font-size:13px; color:var(--muted-text);">Nothing posted here yet — check back soon.</p>`;
    if (typeof openModal === 'function') openModal('whatsNewModal');
    return;
  }

  let html = '';

  if ((cfg.updates || []).length) {
    html += `<div class="actions-section-label">✨ What's New</div>`;
    html += `<div style="display:flex; flex-direction:column; gap:12px; margin-bottom:20px;">`;
    dgeSortUpdatesNewestFirst(cfg.updates).forEach(u => {
      html += `
        <div style="border-left:3px solid var(--accent-red); padding-left:10px;">
          ${u.date ? `<div style="font-size:10px; font-weight:700; color:var(--muted-text); text-transform:uppercase; margin-bottom:2px;">${dgeModalsEsc(u.date)}</div>` : ''}
          <div style="font-size:13px; font-weight:800; margin-bottom:2px;">${dgeModalsEsc(u.title)}</div>
          <div style="font-size:12px; color:var(--muted-text); line-height:1.5;">${dgeModalsEsc(u.description || '')}</div>
        </div>`;
    });
    html += `</div>`;
  }

  if ((cfg.comingSoon || []).length) {
    html += `<div class="actions-section-label">🔭 Coming Soon</div>`;
    html += `<div style="display:flex; flex-direction:column; gap:12px;">`;
    cfg.comingSoon.forEach(c => {
      html += `
        <div style="border-left:3px dashed var(--card-border); padding-left:10px;">
          <div style="font-size:13px; font-weight:800; margin-bottom:2px;">${dgeModalsEsc(c.title)}</div>
          <div style="font-size:12px; color:var(--muted-text); line-height:1.5;">${dgeModalsEsc(c.description || '')}</div>
        </div>`;
    });
    html += `</div>`;
  }

  body.innerHTML = html;
  if (typeof openModal === 'function') openModal('whatsNewModal');
}

// Structured, machine-parseable feedback report — same "open the visitor's
// own email app" pattern as sendTypoReport below (no backend on a static
// site to receive anything else), but with a fixed subject TAG and a
// strict key:value body instead of free text. The tag is what lets a
// future scheduled process tell "one of our own auto-generated reports"
// apart from an ordinary email in the same inbox and safely ignore
// everything else — see PENDING.md's automated-triage design note for
// the full reasoning (only CONTENT corrections matching this exact shape
// are ever eligible for unattended handling; anything else, including any
// request that reads as changing behavior rather than fixing a data gap,
// is routed to a human-reviewed GitHub issue instead, never auto-merged).
window.DGE_FEEDBACK_TAG = '[DGE-CONTENT-GAP]';
window.dgeReportMissingForm = function(surface, context) {
  const email = (typeof appConfig !== 'undefined' && appConfig.contactEmail) ? appConfig.contactEmail : 'sanatanavidyagurukulam@gmail.com';
  const subject = encodeURIComponent(`${window.DGE_FEEDBACK_TAG} missing-form — ${surface}`);
  const lines = [
    `Type: missing-form`,
    `Surface: ${surface}`,
    `Context: ${context || '(unspecified)'}`,
    `Page: ${window.location.href}`,
    `Timestamp: ${new Date().toISOString()}`,
    ``,
    `(Auto-filled by the DGE word-tool's "report this as missing" link —`,
    ` edit this body if you want to add more detail, but keep the`,
    ` Type/Surface/Context/Page lines above intact so it can still be`,
    ` matched automatically.)`
  ];
  window.location.href = `mailto:${email}?subject=${subject}&body=${encodeURIComponent(lines.join('\n'))}`;
};

window.sendTypoReport = function() {
  const shlokaEl = document.getElementById('reportTypoShloka');
  const detailsEl = document.getElementById('reportTypoDetails');
  const shloka = shlokaEl && shlokaEl.value ? shlokaEl.value.trim() : '(not specified)';
  const details = detailsEl && detailsEl.value ? detailsEl.value.trim() : '';

  if (!details) {
    if (typeof showToast === 'function') showToast('Please describe the issue first.');
    return;
  }

  const title = (typeof stotraData !== 'undefined' && stotraData && stotraData.metadata) ? stotraData.metadata.title : document.title;
  const email = (typeof appConfig !== 'undefined' && appConfig.contactEmail) ? appConfig.contactEmail : 'sanatanavidyagurukulam@gmail.com';
  const subject = encodeURIComponent(`DGE Issue Report — ${title} — Shloka ${shloka}`);
  const body = encodeURIComponent(`Text: ${title}\nShloka: ${shloka}\nPage: ${window.location.href}\n\nIssue:\n${details}`);

  window.location.href = `mailto:${email}?subject=${subject}&body=${body}`;
};

// Contact Us — same mailto pattern as sendTypoReport above: no backend on
// a static site to actually receive a POST, so this opens the visitor's
// own email app with everything pre-filled instead of pretending to
// submit a form that goes nowhere.
window.sendContactMessage = function() {
  const nameEl = document.getElementById('contactName');
  const emailEl = document.getElementById('contactEmail');
  const phoneEl = document.getElementById('contactPhone');
  const subjectEl = document.getElementById('contactSubject');
  const messageEl = document.getElementById('contactMessage');
  const name = nameEl && nameEl.value ? nameEl.value.trim() : '';
  const fromEmail = emailEl && emailEl.value ? emailEl.value.trim() : '';
  const phone = phoneEl && phoneEl.value ? phoneEl.value.trim() : '';
  const subjectText = subjectEl && subjectEl.value ? subjectEl.value.trim() : '';
  const message = messageEl && messageEl.value ? messageEl.value.trim() : '';

  if (!message) {
    if (typeof showToast === 'function') showToast('Please write a message first.');
    return;
  }

  const toEmail = (typeof appConfig !== 'undefined' && appConfig.contactEmail) ? appConfig.contactEmail : 'sanatanavidyagurukulam@gmail.com';
  const subject = encodeURIComponent(subjectText || `DGE Contact — ${name || 'website visitor'}`);
  const bodyLines = [
    `Name: ${name || '(not given)'}`,
    `Reply-to email: ${fromEmail || '(not given)'}`,
    `Phone: ${phone || '(not given)'}`,
    '',
    message
  ];
  const body = encodeURIComponent(bodyLines.join('\n'));
  window.location.href = `mailto:${toEmail}?subject=${subject}&body=${body}`;
};
