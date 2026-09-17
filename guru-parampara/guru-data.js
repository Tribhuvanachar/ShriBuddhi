/* guru-data.js — ONE central data layer for every Guru Parampara view
   (guru1 / guru2 / guru3 and the admin editor's preview).

   Canonical store: guru-parampara/data/parampara.json (215 nodes; the
   split people/mathas/places.json are GENERATED from it by
   tools/build_guru_parampara_entities.py — never hand-edit those).

   A superadmin with a pending admin draft (localStorage guru_admin_draft,
   written by admin/guru.html) sees the draft overlaid, so edits can be
   previewed in every layout before the exported JSON is committed. */
(function () {
  'use strict';
  window.DGE_VERSIONS = window.DGE_VERSIONS || {};
  window.DGE_VERSIONS['guru-data.js'] =
    'v1.0 (central parampara adapter: canonical nodes + matha palette + succession orders + gps links + admin-draft overlay for superadmins)';

  // stable colours for every matha key in matha_labels (fallback hashes hue)
  var PALETTE = {
    mula: '#8a7a68', core: '#b3541e', lay: '#7d7d7d',
    uttaradi: '#2a6f97', vyasaraja: '#3d8b5a', raghavendra: '#c25b32',
    sripadaraja: '#7a4a9a', haridasa: '#c9a227',
    kashi: '#3d887d', gokarna: '#5f9e8f',
    palimaru: '#a15d82', adamaru: '#b27638', krishnapura: '#596f98',
    puttige: '#8b7040', shirur: '#4d858f', sode: '#a25d49',
    kaniyooru: '#6c7c47', pejawara: '#795a8e', peripheral: '#888'
  };
  var UDUPI_ASHTA = ['palimaru', 'adamaru', 'krishnapura', 'puttige',
                     'shirur', 'sode', 'kaniyooru', 'pejawara'];

  function colorOf(matha) {
    if (PALETTE[matha]) return PALETTE[matha];
    var h = 0; String(matha).split('').forEach(function (c) { h = (h * 31 + c.charCodeAt(0)) % 360; });
    return 'hsl(' + h + ',45%,50%)';
  }

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c];
    });
  }

  var cache = null;
  function load() {
    if (cache) return cache;
    cache = Promise.all([
      fetch('data/parampara.json').then(function (r) { return r.json(); }),
      fetch('data/places.json').then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; }),
      // The द्वैतवेदान्तग्रन्थानुक्रमणी catalogue's works for these ācāryas,
      // keyed by this file's own node ids (tools/sync_dvaita_crosslinks.py).
      // Optional: an older checkout without it just shows no extra works.
      fetch('../../data/catalogs/author_works_index.json').then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; })
    ]).then(function (res) {
      var d = res[0], placesDoc = res[1], worksDoc = res[2];
      var nodes = (d.nodes || []).map(function (n) { return Object.assign({}, n); });

      // superadmin draft overlay (admin/guru.html) — preview before commit
      var draft = null;
      try {
        var sa = localStorage.getItem('is_superadmin') === 'true' || localStorage.getItem('dge.admin.ok') === '1';
        if (sa) draft = JSON.parse(localStorage.getItem('guru_admin_draft') || 'null');
      } catch (e) {}
      var draftBadge = {};
      if (draft && draft.nodes) {
        var byIdTmp = {};
        nodes.forEach(function (n, i) { byIdTmp[n.id] = i; });
        Object.keys(draft.nodes).forEach(function (id) {
          var dn = draft.nodes[id];
          if (byIdTmp[id] !== undefined) nodes[byIdTmp[id]] = Object.assign({}, nodes[byIdTmp[id]], dn);
          else nodes.push(Object.assign({ id: id }, dn));
          draftBadge[id] = 1;
        });
        (draft.deleted || []).forEach(function (id) {
          nodes = nodes.filter(function (n) { return n.id !== id; });
        });
      }

      // Catalogued works, attached as their own field rather than merged
      // into n.works: those are hand-written English summaries, these are
      // the bibliography's own Devanagari titles with the mula each
      // commentary was written on, and a reader should be able to tell
      // which is which.
      var catWorks = (worksDoc && worksDoc.byPerson) || {};
      nodes.forEach(function (n) {
        var entry = catWorks[n.id];
        if (entry) {
          n.catalogueWorks = entry.works || [];
          n.catalogueWorksMeta = {
            count: entry.count, digitised: entry.digitisedCount,
            canonical: entry.canonical, iast: entry.iast, matchedVia: entry.matchedVia
          };
        }
      });

      var byId = {}, children = {};
      nodes.forEach(function (n) { byId[n.id] = n; });
      nodes.forEach(function (n) {
        if (n.guru && byId[n.guru]) (children[n.guru] = children[n.guru] || []).push(n.id);
      });

      // node id -> gps + place label, via places.json people lists
      var geo = {};
      var places = (placesDoc && placesDoc.places) || placesDoc || [];
      (Array.isArray(places) ? places : Object.values(places)).forEach(function (p) {
        (p.people || []).forEach(function (pid) {
          if (!geo[pid]) geo[pid] = { label: p.label, gps: p.gps || null };
        });
      });

      function succession(matha) {
        var keys = matha === 'udupi' ? UDUPI_ASHTA : [matha];
        var set = nodes.filter(function (n) { return keys.indexOf(n.matha) >= 0; });
        var ids = {}; set.forEach(function (n) { ids[n.id] = 1; });
        var indeg = {}; set.forEach(function (n) { indeg[n.id] = 0; });
        set.forEach(function (n) { if (n.guru && ids[n.guru]) indeg[n.id]++; });
        var q = set.filter(function (n) { return indeg[n.id] === 0; }).map(function (n) { return n.id; });
        var order = [];
        while (q.length) {
          var id = q.shift(); order.push(id);
          (children[id] || []).forEach(function (c) {
            if (ids[c] && --indeg[c] === 0) q.push(c);
          });
        }
        set.forEach(function (n) { if (order.indexOf(n.id) < 0) order.push(n.id); });
        return order;
      }

      function centuryOf(n) {
        if (n.b == null && n.d == null) return 'timeless';
        var y = (n.b != null ? n.b : n.d);
        return Math.floor(y / 100) * 100;
      }

      function mapsLink(id) {
        // node-level gps (set through admin/guru.html) wins; the generated
        // places.json geo is the fallback once places are geocoded
        var n = byId[id];
        var gps = (n && n.gps) || (geo[id] && geo[id].gps) || null;
        if (!gps) return null;
        var ll = Array.isArray(gps) ? gps.join(',')
          : String(gps.lat) + ',' + (gps.lng != null ? gps.lng : gps.lon);
        return 'https://www.google.com/maps/search/?api=1&query=' + encodeURIComponent(ll);
      }

      return {
        nodes: nodes, byId: byId, children: children,
        mathaLabels: d.matha_labels || {},
        images: d.brindavana_images || {},
        meta: d.meta || {},
        geo: geo, mapsLink: mapsLink,
        succession: succession, centuryOf: centuryOf,
        colorOf: colorOf, esc: esc,
        udupiAshta: UDUPI_ASHTA,
        draftIds: draftBadge,
        hasDraft: !!(draft && draft.nodes && Object.keys(draft.nodes).length)
      };
    });
    return cache;
  }

  // Rich biography panel for a saint node's `bio` object (see
  // archive/retired-importers-2026-09.zip → tools/guru_harvest/enrich_jagannatha_v.py for the shape). Returns '' when
  // the node has no bio, so every detail view can append it unconditionally.
  // Prose fields (summary/origin/anecdote text/verse note) are curated repo
  // content and may carry light inline HTML (<b>, <i>, <a>) — rendered as-is,
  // the same trust model the reader uses for commentary/legal content; the
  // verse scripts, titles and source URLs are escaped.
  function bioHtml(node) {
    var b = node && node.bio;
    if (!b) return '';
    var h = '<div class="guru-bio">';
    if (b.image) {
      h += '<div class="guru-bio-photo"><img loading="lazy" alt="' + esc(node.name || '') +
           '" src="' + esc(b.image) + '"></div>';
    }
    if (b.dhyana && b.dhyana.deva) {
      h += '<div class="guru-bio-dhyana"><div class="gb-verse-deva">' +
           esc(b.dhyana.deva).replace(/\n/g, '<br>') + '</div>' +
           (b.dhyana.note ? '<div class="gb-verse-note">' + b.dhyana.note + '</div>' : '') +
           '</div>';
    }
    if (b.summary) h += '<p class="guru-bio-summary">' + b.summary + '</p>';
    if (b.origin) h += '<p class="guru-bio-origin"><span class="gb-h">Origin</span> ' + b.origin + '</p>';
    if (b.anecdotes && b.anecdotes.length) {
      h += '<div class="guru-bio-block"><div class="gb-h">Life & anecdotes</div>';
      b.anecdotes.forEach(function (a) {
        h += '<div class="gb-anecdote"><b>' + esc(a.title || '') + '.</b> ' + (a.text || '') + '</div>';
      });
      h += '</div>';
    }
    if (b.verses && b.verses.length) {
      h += '<div class="guru-bio-block"><div class="gb-h">Verses</div>';
      b.verses.forEach(function (v) {
        h += '<div class="gb-verse">';
        if (v.deva) h += '<div class="gb-verse-deva">' + esc(v.deva).replace(/\n/g, '<br>') + '</div>';
        if (v.iast) h += '<div class="gb-verse-iast">' + esc(v.iast) + '</div>';
        if (v.note) h += '<div class="gb-verse-note">' + v.note + '</div>';
        h += '</div>';
      });
      h += '</div>';
    }
    if (b.refs && b.refs.length) {
      h += '<div class="guru-bio-refs"><span class="gb-h">Sources</span> ' +
           b.refs.map(function (r) {
             return '<a href="' + esc(r.url) + '" target="_blank" rel="noopener">' +
                    esc(r.label || r.url) + ' ↗</a>';
           }).join(' · ') + '</div>';
    }
    return h + '</div>';
  }

  // Bio-panel styling injected once — the three layouts each use their own
  // inline <style> and their own theme variables, so this self-contained
  // block (with var() fallbacks) keeps the panel consistent across all of
  // them without editing three stylesheets.
  function ensureBioCss() {
    if (document.getElementById('dge-guru-bio-css')) return;
    var st = document.createElement('style');
    st.id = 'dge-guru-bio-css';
    st.textContent =
      '.guru-bio{margin-top:12px;padding-top:12px;border-top:1px dashed var(--line,#d9cdb8)}' +
      '.guru-bio-photo{float:right;width:132px;margin:0 0 10px 14px}' +
      '.guru-bio-photo img{width:100%;border-radius:12px;border:1px solid var(--line,#d9cdb8);box-shadow:0 2px 10px rgba(0,0,0,.18)}' +
      '.guru-bio .gb-h{display:inline-block;font-size:11px;font-weight:700;letter-spacing:.5px;text-transform:uppercase;color:var(--gold,#b8860b);margin-right:6px}' +
      '.guru-bio-dhyana{margin:4px 0 10px;padding:8px 12px;border-left:3px solid var(--gold,#b8860b);background:var(--panel2,rgba(184,134,11,.08));border-radius:0 10px 10px 0}' +
      '.guru-bio .gb-verse-deva{font-family:"Noto Sans Devanagari","Siddhanta",serif;font-size:1.06em;line-height:1.7}' +
      '.guru-bio .gb-verse-iast{font-style:italic;opacity:.85;margin-top:2px}' +
      '.guru-bio .gb-verse-note{font-size:.86em;opacity:.75;margin-top:3px}' +
      '.guru-bio-summary,.guru-bio-origin{margin:8px 0;line-height:1.6}' +
      '.guru-bio-block{margin:11px 0}.guru-bio-block .gb-h{display:block;margin-bottom:5px}' +
      '.guru-bio .gb-anecdote{margin:6px 0;line-height:1.55}' +
      '.guru-bio .gb-verse{margin:8px 0;padding:6px 10px;background:var(--panel2,rgba(0,0,0,.03));border-radius:8px}' +
      '.guru-bio-refs{margin-top:12px;font-size:.86em}' +
      '.guru-bio-refs a{color:var(--gold,#b8860b);text-decoration:none}.guru-bio-refs a:hover{text-decoration:underline}' +
      '@media(max-width:520px){.guru-bio-photo{float:none;width:100%;max-width:200px;margin:0 auto 10px;display:block}}';
    (document.head || document.documentElement).appendChild(st);
  }
  ensureBioCss();

  window.DGE_GURU = { load: load, colorOf: colorOf, esc: esc, bioHtml: bioHtml, UDUPI_ASHTA: UDUPI_ASHTA };
})();
