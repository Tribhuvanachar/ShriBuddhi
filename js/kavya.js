/* DGE — Kavya reader.
 * Reads data/kavya_alankara/_index.json, then fetches each layer's data.json
 * on demand.  No libraries, no build step, no sharding.
 *
 * URL state:  kavya.html#<work_id>/<unit_id>      e.g. #raghuvamsha/1
 * Prefs (localStorage, key dge.kavya.v2): theme, script, font size, mode,
 * and the open/closed layer set per work.
 */
(function () {
  "use strict";

  // The corpus is 50 MB and lives on this repo's own "kavya-dist" branch,
  // not in the site: GitHub Pages publishes main and nothing else, and the
  // published site has about 1% of the 1 GB Pages limit left. jsDelivr
  // serves any branch, which is what the kosa corpus and the Sanskrit
  // WordNet already do. config.js sets window.KAVYA_DATA_BASE from
  // appConfig for the reader; this page does not load config.js, so the
  // same URL is the default here. Set it to "data" to read a local build.
  var CDN = "https://cdn.jsdelivr.net/gh/Tribhuvanachar/bhumandala@75ef2103bc07770ccb861497c32636d706c09fa4";
  var DATA_BASE = window.KAVYA_DATA_BASE || CDN;
  var INDEX_URL = DATA_BASE + "/kavya_alankara/_index.json";
  var PREF_KEY = "dge.kavya.v2";

  var S = {                       // session state
    index: null,
    work: null,
    unitId: null,
    layers: {},                   // layer_id -> parsed data.json
    open: {},                     // layer_id -> bool (current work)
    mode: "read",
    script: "deva",
    prefs: {}
  };

  /* ------------------------------------------------------------------ *
   * Transliteration: Devanagari -> IAST / Kannada
   * ------------------------------------------------------------------ */
  var VOWELS = {
    "अ":"a","आ":"ā","इ":"i","ई":"ī","उ":"u","ऊ":"ū","ऋ":"ṛ","ॠ":"ṝ",
    "ऌ":"ḷ","ॡ":"ḹ","ए":"e","ऐ":"ai","ओ":"o","औ":"au"
  };
  var MATRAS = {
    "ा":"ā","ि":"i","ी":"ī","ु":"u","ू":"ū","ृ":"ṛ","ॄ":"ṝ","ॢ":"ḷ",
    "ॣ":"ḹ","े":"e","ै":"ai","ो":"o","ौ":"au"
  };
  var CONS = {
    "क":"k","ख":"kh","ग":"g","घ":"gh","ङ":"ṅ",
    "च":"c","छ":"ch","ज":"j","झ":"jh","ञ":"ñ",
    "ट":"ṭ","ठ":"ṭh","ड":"ḍ","ढ":"ḍh","ण":"ṇ",
    "त":"t","थ":"th","द":"d","ध":"dh","न":"n",
    "प":"p","फ":"ph","ब":"b","भ":"bh","म":"m",
    "य":"y","र":"r","ल":"l","व":"v","ळ":"ḻ",
    "श":"ś","ष":"ṣ","स":"s","ह":"h"
  };
  var SIGNS = { "ं":"ṃ", "ः":"ḥ", "ँ":"m̐", "ऽ":"'" };
  var DIGITS = "०१२३४५६७८९";

  function toIAST(s) {
    if (!s) return "";
    var out = "", i = 0;
    while (i < s.length) {
      var ch = s[i];
      if (CONS[ch]) {
        out += CONS[ch];
        var nx = s[i + 1];
        if (nx === "्") { i += 2; continue; }
        if (MATRAS[nx]) { out += MATRAS[nx]; i += 2; continue; }
        out += "a"; i += 1; continue;
      }
      if (VOWELS[ch]) { out += VOWELS[ch]; i += 1; continue; }
      if (SIGNS[ch]) { out += SIGNS[ch]; i += 1; continue; }
      if (DIGITS.indexOf(ch) >= 0) { out += DIGITS.indexOf(ch); i += 1; continue; }
      if (ch === "।") { out += "|"; i += 1; continue; }
      if (ch === "॥") { out += "||"; i += 1; continue; }
      if (ch === "्") { i += 1; continue; }
      out += ch; i += 1;
    }
    return out;
  }

  /* Devanagari and Kannada are code-point aligned across the Sanskrit
   * repertoire (offset 0x380).  These few Devanagari points have no Kannada
   * counterpart, so they are left as-is rather than emitting a hole. */
  var NO_KANNADA = { "ऍ":1,"ऎ":1,"ऑ":1,"ऒ":1,"ॅ":1,"ॆ":1,"ॉ":1,"ॊ":1,
                     "ऩ":1,"ऱ":1,"ऴ":1,"क़":1,"ख़":1,"ग़":1,"ज़":1,"ड़":1,
                     "ढ़":1,"फ़":1,"य़":1,"ॐ":1,"।":1,"॥":1,"ऽ":1 };
  function toKannada(s) {
    if (!s) return "";
    var out = "";
    for (var i = 0; i < s.length; i++) {
      var ch = s[i], c = s.charCodeAt(i);
      if (NO_KANNADA[ch] || c < 0x0900 || c > 0x097f) { out += ch; continue; }
      out += String.fromCharCode(c + 0x380);
    }
    return out;
  }

  function tr(s, lang) {
    if (!s) return "";
    if (lang && lang !== "sa") return s;          // English/Hindi pass through
    if (S.script === "iast") return toIAST(s);
    if (S.script === "kn") return toKannada(s);
    return s;
  }
  function trNum(s) {
    if (S.script === "deva") {
      return String(s).replace(/[0-9]/g, function (d) { return DIGITS[+d]; });
    }
    return String(s);
  }

  /* ------------------------------------------------------------------ *
   * Prefs
   * ------------------------------------------------------------------ */
  function loadPrefs() {
    try { S.prefs = JSON.parse(localStorage.getItem(PREF_KEY) || "{}"); }
    catch (e) { S.prefs = {}; }
    S.script = S.prefs.script || "deva";
    S.mode = S.prefs.mode || "read";
    document.documentElement.dataset.theme = S.prefs.theme || "light";
    if (S.prefs.fs) document.documentElement.style.setProperty("--fs", S.prefs.fs);
  }
  function savePrefs() {
    S.prefs.script = S.script;
    S.prefs.mode = S.mode;
    S.prefs.theme = document.documentElement.dataset.theme;
    S.prefs.layers = S.prefs.layers || {};
    if (S.work) S.prefs.layers[S.work.id] = S.open;
    try { localStorage.setItem(PREF_KEY, JSON.stringify(S.prefs)); } catch (e) {}
  }

  /* ------------------------------------------------------------------ *
   * Data
   * ------------------------------------------------------------------ */
  function getJSON(url) {
    return fetch(url, { cache: "no-cache" }).then(function (r) {
      if (!r.ok) throw new Error(url + " -> " + r.status);
      return r.json();
    });
  }

  function loadLayer(layer) {
    if (S.layers[layer.id]) return Promise.resolve(S.layers[layer.id]);
    var url = DATA_BASE.replace(/\/$/, "") + "/" +
              layer.path.replace(/^data\//, "");
    return getJSON(url).then(function (d) { S.layers[layer.id] = d; return d; });
  }

  function unitOf(layerData, unitId) {
    if (!layerData) return null;
    var items = layerData.items || [];
    for (var i = 0; i < items.length; i++) {
      if (String(items[i].id) === String(unitId)) return items[i];
    }
    return null;
  }

  /* ------------------------------------------------------------------ *
   * Rendering
   * ------------------------------------------------------------------ */
  var $ = function (sel, root) { return (root || document).querySelector(sel); };
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  function layerLabel(l) {
    return tr(l.name_sa, "sa") || l.name_iast || l.name_en || l.id;
  }

  function groupWorks() {
    var groups = { shravya: [], drishya: [], kavyashastra: [], other: [] };
    (S.index.works || []).forEach(function (w) {
      var g = (w.genre_path || [])[1];
      (groups[g] ? groups[g] : groups.other).push(w);
    });
    return groups;
  }

  function renderWorkPicker() {
    var sel = $("#workSel");
    sel.innerHTML = "";
    var groups = groupWorks();
    var labels = {
      shravya: "श्रव्यकाव्यानि · Śravya",
      drishya: "दृश्यकाव्यानि · Dṛśya",
      kavyashastra: "काव्यशास्त्रम् · Poetics",
      other: "अन्यानि · Other"
    };
    Object.keys(labels).forEach(function (g) {
      if (!groups[g].length) return;
      var og = document.createElement("optgroup");
      og.label = labels[g];
      groups[g].forEach(function (w) {
        var o = document.createElement("option");
        o.value = w.id;
        o.textContent = (w.name_sa || w.id) +
          (w.author ? "  — " + w.author : "");
        og.appendChild(o);
      });
      sel.appendChild(og);
    });
    if (S.work) sel.value = S.work.id;
  }

  function renderUnitPicker() {
    var sel = $("#unitSel");
    sel.innerHTML = "";
    (S.work.units || []).forEach(function (u) {
      var o = document.createElement("option");
      o.value = u.id;
      o.textContent = trNum(u.id) + (u.name_sa ? " · " + tr(u.name_sa) : "") +
        "  (" + trNum(u.n) + ")";
      sel.appendChild(o);
    });
    sel.value = S.unitId;
  }

  function renderLayerBar() {
    var bar = $("#layerBar");
    bar.innerHTML = "";
    (S.work.layers || []).forEach(function (l) {
      if (l.id === "mula") return;                 // mula is always shown
      var b = el("button", "chip" + (l.ai_generated ? " ai" : ""));
      b.type = "button";
      b.setAttribute("aria-pressed", S.open[l.id] ? "true" : "false");
      b.appendChild(document.createTextNode(
        (l.ai_generated ? "✦ " : "") + layerLabel(l)));
      var n = el("span", "n", "· " + trNum((l.counts || {}).shlokas || 0));
      b.appendChild(n);
      b.addEventListener("click", function () {
        S.open[l.id] = !S.open[l.id];
        b.setAttribute("aria-pressed", S.open[l.id] ? "true" : "false");
        savePrefs();
        /* The layer's data.json is fetched on demand, so a newly enabled
           chip must load before the re-render or it renders as nothing. */
        ensureLayersLoaded().then(renderVerses);
      });
      bar.appendChild(b);
    });
  }

  function padacchedaNode(pc) {
    var box = el("div", "pc");
    (pc || []).forEach(function (w) {
      var a = el("a");
      // Was "kosha.html?w=..." -- that page has never existed (Kosha is a
      // modal inside the reader, window.dgeOpenKosha(), not a standalone
      // page), so every padaccheda word here was a dead link. shabda.html's
      // own ?q= deep link (shabda.js's boot()) pre-fills its search with
      // exactly this lemma, which is a real, working lookup.
      a.href = "../vyakarana/shabda.html?q=" + encodeURIComponent(
        (w.p && w.p[0] && w.p[0].lemma) || w.w);
      a.appendChild(el("span", "w", tr(w.w)));
      if (w.e) a.appendChild(el("span", "g", w.e));
      var m = (w.p || []).map(function (p) {
        return p.case_number || (p.lakara ? p.lakara + " " + (p.person || "") : "");
      }).filter(Boolean).join(" ");
      if (m) a.appendChild(el("span", "m", m));
      box.appendChild(a);
    });
    return box;
  }

  function layerBody(l, sh) {
    if (l.id === "padaccheda" && sh.padaccheda) return padacchedaNode(sh.padaccheda);
    if (sh.bhashya && sh.bhashya.length) {
      var wrap = el("div");
      sh.bhashya.forEach(function (b) {
        var d = el("div", "body", tr(b.text, l.language));
        wrap.appendChild(d);
      });
      return wrap;
    }
    return el("div", "body", tr(sh.artha || sh.sanskrit_text || "", l.language));
  }

  function renderVerses() {
    var host = $("#verses");
    host.innerHTML = "";
    host.className = S.mode === "compare" ? "compare" : "";

    var mulaLayer = (S.work.layers || []).filter(function (l) {
      return l.id === "mula";
    })[0] || (S.work.layers || [])[0];
    var mulaData = S.layers[mulaLayer.id];
    var item = unitOf(mulaData, S.unitId);
    if (!item) {
      host.appendChild(el("div", "empty", "…"));
      return;
    }
    var active = (S.work.layers || []).filter(function (l) {
      return l.id !== mulaLayer.id && S.open[l.id] && S.layers[l.id];
    });
    document.documentElement.style.setProperty(
      "--cols", String(Math.min(Math.max(active.length, 1), 3)));

    item.shlokas.forEach(function (sh) {
      var card = el("article", "verse");
      var head = el("div", "head");
      head.appendChild(el("span", "ref", trNum(sh.id)));
      var meta = el("div", "meta");
      if (sh.chandas) {
        // the metre tag opens the analyzer with this very verse prefilled
        var chLink = el("a", "chandas-link", tr(sh.chandas));
        chLink.href = "../vyakarana/chandas.html?q=" + encodeURIComponent(sh.sanskrit_text || "");
        chLink.title = "छन्दोविश्लेषणम् — laghu/guru breakdown of this verse";
        meta.appendChild(chLink);
      }
      if (sh.kind === "prose") meta.appendChild(el("span", null, "गद्यम्"));
      head.appendChild(meta);
      card.appendChild(head);

      if (sh.speaker) card.appendChild(el("div", "speaker", tr(sh.speaker)));
      card.appendChild(el("div", "mula",
        tr(sh.sanskrit_text || sh.artha || "")));

      var layersBox = el("div", "layers");
      active.forEach(function (l) {
        var lsh = null;
        var li = unitOf(S.layers[l.id], S.unitId);
        if (li) {
          for (var i = 0; i < li.shlokas.length; i++) {
            if (li.shlokas[i].id === sh.id) { lsh = li.shlokas[i]; break; }
          }
        }
        if (!lsh) return;
        var det = el("details", "layer" + (l.language !== "sa" ?
          " lang-" + l.language : ""));
        /* Attested layers open by default; AI-generated ones start closed so
           the attested text is what the reader meets first. */
        det.open = S.mode === "compare" ? true : !l.ai_generated;
        var sum = el("summary");
        sum.appendChild(document.createTextNode(layerLabel(l)));
        if (l.commentator) {
          sum.appendChild(el("span", "badge", tr(l.commentator)));
        }
        if (l.ai_generated) sum.appendChild(el("span", "badge ai", "✦ AI"));
        det.appendChild(sum);
        det.appendChild(layerBody(l, lsh));
        layersBox.appendChild(det);
      });
      card.appendChild(layersBox);
      host.appendChild(card);
    });

    var notes = (S.work.layers || []).filter(function (l) {
      return l.id === mulaLayer.id || S.open[l.id];
    }).map(function (l) {
      var s = l.source || {};
      return layerLabel(l) + ": " + (s.repo || s.url || "—") +
             (l.license ? " · " + l.license.split(".")[0] : "");
    });
    if (notes.length) {
      var n = el("div", "srcnote", "स्रोतांसि — " + notes.join("  |  "));
      host.appendChild(n);
    }
    $("#unitNow").textContent = trNum(S.unitId) + " / " +
      trNum((S.work.units || []).length);
  }

  function ensureLayersLoaded() {
    var need = (S.work.layers || []).filter(function (l) {
      return l.id === "mula" || S.open[l.id];
    });
    return Promise.all(need.map(function (l) {
      return loadLayer(l).catch(function (e) {
        console.warn("layer failed", l.id, e);
        return null;
      });
    }));
  }

  /* ------------------------------------------------------------------ *
   * Navigation
   * ------------------------------------------------------------------ */
  function setHash() {
    var h = "#" + S.work.id + "/" + S.unitId;
    if (location.hash !== h) history.replaceState(null, "", h);
  }

  function selectWork(workId, unitId) {
    var w = (S.index.works || []).filter(function (x) { return x.id === workId; })[0];
    if (!w) w = (S.index.works || [])[0];
    if (!w) return Promise.resolve();
    S.work = w;
    S.layers = {};
    var saved = (S.prefs.layers || {})[w.id];
    if (saved) {
      S.open = saved;
    } else {
      S.open = {};
      /* Sensible default: the first commentary plus the English rendering. */
      var firstTika = w.layers.filter(function (l) {
        return l.layer_kind === "tika" || l.layer_kind === "tippani";
      })[0];
      if (firstTika) S.open[firstTika.id] = true;
      if (w.layers.some(function (l) { return l.id === "translation_en"; })) {
        S.open.translation_en = true;
      }
    }
    var units = w.units || [];
    S.unitId = unitId && units.some(function (u) { return String(u.id) === String(unitId); })
      ? String(unitId) : (units[0] ? String(units[0].id) : "1");
    renderWorkPicker();
    renderUnitPicker();
    renderLayerBar();
    setHash();
    savePrefs();
    return ensureLayersLoaded().then(renderVerses);
  }

  function step(delta) {
    var units = (S.work.units || []).map(function (u) { return String(u.id); });
    var i = units.indexOf(String(S.unitId));
    if (i < 0) return;
    var j = i + delta;
    if (j < 0 || j >= units.length) return;
    S.unitId = units[j];
    $("#unitSel").value = S.unitId;
    setHash();
    ensureLayersLoaded().then(function () {
      renderVerses();
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  }

  function parseHash() {
    var m = (location.hash || "").replace(/^#/, "").split("/");
    return { work: m[0] || null, unit: m[1] || null };
  }

  /* ------------------------------------------------------------------ *
   * Wiring
   * ------------------------------------------------------------------ */
  function wire() {
    $("#workSel").addEventListener("change", function () {
      selectWork(this.value, null);
    });
    $("#unitSel").addEventListener("change", function () {
      S.unitId = this.value;
      setHash();
      ensureLayersLoaded().then(renderVerses);
    });
    $("#prev").addEventListener("click", function () { step(-1); });
    $("#next").addEventListener("click", function () { step(1); });

    document.querySelectorAll("[data-script]").forEach(function (b) {
      b.addEventListener("click", function () {
        S.script = b.dataset.script;
        document.querySelectorAll("[data-script]").forEach(function (x) {
          x.setAttribute("aria-pressed", x === b ? "true" : "false");
        });
        savePrefs();
        renderUnitPicker();
        renderLayerBar();
        renderVerses();
      });
      b.setAttribute("aria-pressed", b.dataset.script === S.script ? "true" : "false");
    });

    document.querySelectorAll("[data-mode]").forEach(function (b) {
      b.addEventListener("click", function () {
        S.mode = b.dataset.mode;
        document.querySelectorAll("[data-mode]").forEach(function (x) {
          x.setAttribute("aria-pressed", x === b ? "true" : "false");
        });
        savePrefs();
        renderVerses();
      });
      b.setAttribute("aria-pressed", b.dataset.mode === S.mode ? "true" : "false");
    });

    $("#theme").addEventListener("click", function () {
      var d = document.documentElement;
      d.dataset.theme = d.dataset.theme === "dark" ? "light" : "dark";
      savePrefs();
    });
    $("#bigger").addEventListener("click", function () { bumpFont(1); });
    $("#smaller").addEventListener("click", function () { bumpFont(-1); });

    $("#jumpForm").addEventListener("submit", function (ev) {
      ev.preventDefault();
      var v = $("#jumpInput").value.trim();
      if (!v) return;
      var unit = v.split(".")[0];
      if ((S.work.units || []).some(function (u) { return String(u.id) === unit; })) {
        S.unitId = unit;
        $("#unitSel").value = unit;
        setHash();
        ensureLayersLoaded().then(function () {
          renderVerses();
          var target = document.querySelector('.verse .ref');
          var all = document.querySelectorAll(".verse");
          for (var i = 0; i < all.length; i++) {
            if (all[i].querySelector(".ref").textContent === trNum(v)) {
              all[i].scrollIntoView({ behavior: "smooth", block: "center" });
              all[i].style.outline = "2px solid var(--accent)";
              break;
            }
          }
        });
      }
    });

    document.addEventListener("keydown", function (ev) {
      if (/input|select|textarea/i.test((ev.target.tagName || ""))) return;
      if (ev.key === "ArrowLeft") step(-1);
      if (ev.key === "ArrowRight") step(1);
      if (ev.key === "/") { ev.preventDefault(); $("#jumpInput").focus(); }
    });

    window.addEventListener("hashchange", function () {
      var h = parseHash();
      if (h.work && (h.work !== S.work.id || h.unit !== S.unitId)) {
        selectWork(h.work, h.unit);
      }
    });
  }

  function bumpFont(dir) {
    var cur = parseFloat(
      getComputedStyle(document.documentElement).getPropertyValue("--fs")) || 1.06;
    var next = Math.min(1.6, Math.max(0.86, cur + dir * 0.06)).toFixed(2) + "rem";
    document.documentElement.style.setProperty("--fs", next);
    S.prefs.fs = next;
    savePrefs();
  }

  function boot() {
    loadPrefs();
    getJSON(INDEX_URL).then(function (idx) {
      S.index = idx;
      if (!idx.works || !idx.works.length) {
        $("#verses").appendChild(el("div", "empty",
          "काव्यसञ्चयः रिक्तः — run tools/kavya/build_kavya_index.py"));
        return;
      }
      $("#totals").textContent = idx.totals.works + " works · " +
        idx.totals.layers + " layers · " +
        idx.totals.entries.toLocaleString() + " entries";
      var h = parseHash();
      wire();
      return selectWork(h.work, h.unit);
    }).catch(function (e) {
      $("#verses").appendChild(el("div", "empty", "index load failed: " + e.message));
      console.error(e);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else { boot(); }

  window.DGE_KAVYA = S;                       // for console debugging
  window.DGE_KAVYA_TR = { toIAST: toIAST, toKannada: toKannada };
})();
