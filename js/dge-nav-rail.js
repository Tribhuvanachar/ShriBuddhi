/* DGE UI Contract: sitewide global nav — collapsed edge tab + link sheet.
 *
 * One persistent way to jump to another corpus/tool without backing out
 * through the header menu (project lead's framing, 28 Aug 2026 — see
 * dge/DGE_UI_CONTRACT.md's "new formalized requirement" section for the
 * exact policy this implements).
 *
 * 1 Sep 2026 revision (project lead, from a live desktop screenshot): the
 * original desktop treatment — an ALWAYS-VISIBLE fixed rail of eight
 * labeled links down the right edge — read as a permanently open menu
 * ("always open… not collapsed… seems to be a duplicate") and overlapped
 * other floating chrome. The rail is gone entirely: every width now gets
 * the same small docked edge tab that mobile always had, opening the
 * link sheet on tap. The tab is also DRAGGABLE vertically (pointer drag,
 * position persisted per-device in localStorage) so it can be moved off
 * anything it happens to cover.
 *
 * Built as a self-contained custom element, deliberately independent of
 * modals.js/main.css/vyakarana-base.css's own token systems (same reasoning
 * the Ashtadhyayi retrofit used for its scoped CSS — see DGE_UI_CONTRACT.md
 * Part IV §1): it must render identically on dge/index.html
 * (tokens.css/main.css), the Vyakarana cluster (vyakarana-base.css) and
 * Guru Parampara (guru-parampara.css) alike, without requiring any of them
 * to load a shared stylesheet first. It reads --accent-red when the host
 * page defines it and falls back to a fixed value otherwise.
 *
 * Usage: <dge-nav-rail current="dhatu"></dge-nav-rail>, placed anywhere in
 * the body (position is fixed, so DOM location doesn't matter), after this
 * script tag. `current` is one of the ids in ITEMS below, or omitted.
 * Sheet is grouped (GROUPS): Read / Sanskrit tools / Experiments.
 */
(function () {
  "use strict";
  if (window.customElements && window.customElements.get("dge-nav-rail")) return;

  // 7 Sep 2026: grouped (the lead: "Chandas page missing... where can I see
  // the phitsutra, unadi sutra, linganushasana pages? Should we have some
  // Sanskrit Tools grouping"). Every vyakarana/*.html tool page now mounts
  // this rail too, so none of them is a dead end any more.
  var GROUPS = [
    { id: "read", label: "Read" },
    { id: "tools", label: "Sanskrit tools" },
    { id: "lab", label: "Experiments" }
  ];
  var ITEMS = [
    { id: "home", group: "read", label: "DGE Home", glyph: "⌂", href: "dge/index.html" },
    { id: "kavya", group: "read", label: "Kāvya", glyph: "का", href: "dge/kavya/index.html" },
    { id: "tirtha", group: "read", label: "Tīrtha", glyph: "ती", href: "dge/tirtha/index.html" },
    { id: "guru-parampara", group: "read", label: "Guru Paramparā", glyph: "गु", href: "dge/guru-parampara/index.html" },
    { id: "dasa-sahitya", group: "read", label: "Dāsa Sāhitya", glyph: "दा", href: "dge/dasa-sahitya/views/index.html" },
    { id: "dvaita-grantha-anukramani", group: "read", label: "Grantha Anukramaṇī", glyph: "द्वै", href: "dge/dvaita-grantha-anukramani/index.html" },
    // 10 Sep 2026: these four open their "choose a view" page rather than the
    // one old flat page. Three layouts each were built for all of them and
    // linked from nowhere -- the lead found only Guru Paramparā wired up.
    // Every chooser links back to its own classic page.
    { id: "ashtadhyayi", group: "tools", label: "Aṣṭādhyāyī", glyph: "अ", href: "dge/vyakarana/ashtadhyayi/index.html" },
    { id: "dhatu", group: "tools", label: "Dhātu", glyph: "ध", href: "dge/vyakarana/dhatu/index.html" },
    { id: "shabda", group: "tools", label: "Śabda", glyph: "श", href: "dge/vyakarana/shabda/index.html" },
    { id: "rupasiddhi", group: "tools", label: "Rūpasiddhi", glyph: "रू", href: "dge/vyakarana/rupasiddhi.html" },
    { id: "chandas", group: "tools", label: "Chandas", glyph: "छ", href: "dge/vyakarana/chandas.html" },
    { id: "unadi", group: "tools", label: "Uṇādi-sūtra", glyph: "उ", href: "dge/vyakarana/unadi.html" },
    { id: "phitsutra", group: "tools", label: "Phiṭ-sūtra", glyph: "फि", href: "dge/vyakarana/phitsutra.html" },
    { id: "linganushasana", group: "tools", label: "Liṅgānuśāsana", glyph: "लि", href: "dge/vyakarana/linganushasana.html" },
    { id: "ganapatha", group: "tools", label: "Gaṇapāṭha", glyph: "ग", href: "dge/vyakarana/ganapatha.html" },
    { id: "kamadhenu", group: "lab", label: "Kamadhenu trials", glyph: "🐄", href: "dge/kamadhenu.html" }
  ];

  // Per-device vertical position of the tab (px from viewport top). Absent
  // = the default bottom-docked spot (clear of dge/index.html's qa-tab).
  var POS_KEY = "dge.nrTabY";

  function siteRoot() {
    // Resolve relative to this script's own known location (dge/js/), not
    // the including page's location, so the same markup works unmodified
    // whether the host page is at site root, dge/, dge/vyakarana/, or
    // dge/guru-parampara/.
    var cur = document.currentScript;
    var src = cur && cur.getAttribute("src");
    if (!src) return "./";
    return new URL("../../", new URL(src, document.baseURI)).href;
  }

  var ROOT = siteRoot();

  var STYLE_ID = "dge-nav-rail-style";
  function ensureStyle() {
    if (document.getElementById(STYLE_ID)) return;
    var s = document.createElement("style");
    s.id = STYLE_ID;
    s.textContent =
      "dge-nav-rail{display:contents;}" +
      ".dge-nr-link{display:flex;align-items:center;gap:8px;padding:9px 16px;" +
      "text-decoration:none;color:#F3E7D4;font-size:13.5px;line-height:1.15;white-space:nowrap;" +
      "border-left:2px solid transparent;font-family:inherit;}" +
      ".dge-nr-link:hover{background:rgba(255,255,255,0.07);}" +
      ".dge-nr-link[aria-current=page]{border-left-color:var(--accent-red,#9A1B1B);" +
      "color:var(--accent-red,#E2664A);font-weight:600;cursor:default;}" +
      ".dge-nr-glyph{display:inline-flex;align-items:center;justify-content:center;" +
      "width:20px;height:20px;flex:none;font-size:13px;}" +
      ".dge-nr-tab{display:flex;position:fixed;right:0;bottom:calc(230px + env(safe-area-inset-bottom));" +
      "z-index:9190;width:26px;height:52px;border:none;border-radius:8px 0 0 8px;" +
      "background:var(--accent-red,#9A1B1B);color:#fff;font-size:15px;line-height:1;" +
      "box-shadow:-2px 2px 8px rgba(0,0,0,.25);cursor:pointer;touch-action:none;" +
      "align-items:center;justify-content:center;}" +
      ".dge-nr-tab.dragging{cursor:grabbing;opacity:.85;}" +
      ".dge-nr-sheet{display:none;position:fixed;right:8px;bottom:calc(286px + env(safe-area-inset-bottom));" +
      "z-index:9195;min-width:190px;max-height:min(70vh,480px);overflow-y:auto;" +
      "background:rgba(20,16,12,0.94);backdrop-filter:blur(8px);" +
      "-webkit-backdrop-filter:blur(8px);border:1px solid rgba(232,178,77,0.22);border-radius:10px;" +
      "padding:6px 0;box-shadow:0 8px 24px rgba(0,0,0,.35);}" +
      ".dge-nr-sheet.open{display:block;}" +
      ".dge-nr-group{padding:8px 16px 2px;font-size:10px;letter-spacing:.06em;text-transform:uppercase;" +
      "color:rgba(243,231,212,.55);}" +
      ".dge-nr-group+.dge-nr-group,.dge-nr-link+.dge-nr-group{margin-top:4px;border-top:1px solid rgba(232,178,77,0.16);padding-top:8px;}" +
      ".dge-nr-backdrop{display:none;position:fixed;inset:0;z-index:9192;background:transparent;}" +
      ".dge-nr-backdrop.open{display:block;}";
    document.head.appendChild(s);
  }

  function itemHTML(it, current) {
    var isCurrent = it.id === current;
    return (
      '<a class="dge-nr-link" href="' + ROOT + it.href + '"' +
      (isCurrent ? ' aria-current="page"' : "") +
      ' title="' + it.label + '" aria-label="Go to ' + it.label + '">' +
      '<span class="dge-nr-glyph" aria-hidden="true">' + it.glyph + "</span>" +
      "<span>" + it.label + "</span></a>"
    );
  }

  function clampY(y, tabH) {
    var max = (window.innerHeight || 600) - tabH - 8;
    return Math.max(8, Math.min(y, max));
  }

  function DgeNavRail() {
    return Reflect.construct(HTMLElement, [], DgeNavRail);
  }
  DgeNavRail.prototype = Object.create(HTMLElement.prototype);
  DgeNavRail.prototype.constructor = DgeNavRail;
  Object.setPrototypeOf(DgeNavRail, HTMLElement);

  DgeNavRail.prototype.connectedCallback = function () {
    ensureStyle();
    var current = this.getAttribute("current") || "";

    var tab = document.createElement("button");
    tab.type = "button";
    tab.className = "dge-nr-tab";
    tab.title = "Other DGE corpora and tools (drag to move)";
    tab.setAttribute("aria-label", "Open corpus and tool navigation");
    tab.setAttribute("aria-haspopup", "true");
    tab.setAttribute("aria-expanded", "false");
    tab.textContent = "⋯";

    var sheet = document.createElement("div");
    sheet.className = "dge-nr-sheet";
    sheet.setAttribute("role", "menu");
    sheet.innerHTML = GROUPS.map(function (g) {
      var items = ITEMS.filter(function (it) { return it.group === g.id; });
      return '<div class="dge-nr-group">' + g.label + "</div>" +
        items.map(function (it) { return itemHTML(it, current); }).join("");
    }).join("");

    var backdrop = document.createElement("div");
    backdrop.className = "dge-nr-backdrop";

    // Restore the dragged position (clamped, in case the viewport shrank
    // since it was saved).
    var savedY = null;
    try { savedY = parseInt(localStorage.getItem(POS_KEY), 10); } catch (e) { /* private mode */ }
    if (savedY !== null && !isNaN(savedY)) {
      tab.style.top = clampY(savedY, 52) + "px";
      tab.style.bottom = "auto";
    }

    function placeSheet() {
      // Anchor the sheet beside wherever the tab currently sits, kept
      // fully on-screen.
      var r = tab.getBoundingClientRect();
      sheet.style.bottom = "auto";
      var h = sheet.offsetHeight || 320;
      var top = Math.max(8, Math.min(r.top - h / 2, (window.innerHeight || 600) - h - 8));
      sheet.style.top = top + "px";
    }
    function closeSheet() {
      sheet.classList.remove("open");
      backdrop.classList.remove("open");
      tab.setAttribute("aria-expanded", "false");
    }
    function toggleSheet() {
      var open = sheet.classList.toggle("open");
      backdrop.classList.toggle("open", open);
      tab.setAttribute("aria-expanded", open ? "true" : "false");
      if (open) placeSheet();
    }
    backdrop.addEventListener("click", closeSheet);
    sheet.addEventListener("click", function (e) {
      if (e.target.closest("a")) closeSheet();
    });

    // Pointer drag: >6px of vertical movement is a drag (reposition +
    // persist); anything less on release is a tap (toggle the sheet).
    // A synthetic click that follows a real drag is swallowed so the
    // sheet doesn't pop open at the end of a move; keyboard activation
    // still comes through as a click with no preceding drag.
    var drag = null, suppressClick = false;
    tab.addEventListener("pointerdown", function (e) {
      if (e.button !== undefined && e.button !== 0) return;
      drag = { startY: e.clientY, startTop: tab.getBoundingClientRect().top, moved: false };
      try { tab.setPointerCapture(e.pointerId); } catch (err) { /* older engines */ }
    });
    tab.addEventListener("pointermove", function (e) {
      if (!drag) return;
      var dy = e.clientY - drag.startY;
      if (!drag.moved && Math.abs(dy) < 6) return;
      drag.moved = true;
      tab.classList.add("dragging");
      closeSheet();
      tab.style.top = clampY(drag.startTop + dy, tab.offsetHeight || 52) + "px";
      tab.style.bottom = "auto";
    });
    function endDrag() {
      if (!drag) return;
      if (drag.moved) {
        suppressClick = true;
        try { localStorage.setItem(POS_KEY, String(Math.round(tab.getBoundingClientRect().top))); } catch (e) { /* private mode */ }
      }
      tab.classList.remove("dragging");
      drag = null;
    }
    tab.addEventListener("pointerup", endDrag);
    tab.addEventListener("pointercancel", endDrag);
    tab.addEventListener("click", function () {
      if (suppressClick) { suppressClick = false; return; }
      toggleSheet();
    });

    this.appendChild(tab);
    this.appendChild(sheet);
    this.appendChild(backdrop);
  };

  window.customElements.define("dge-nav-rail", DgeNavRail);
})();
