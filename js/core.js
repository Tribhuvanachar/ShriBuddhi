// DGE Module: core.js - Fixed Path Resolution
window.DGE_VERSIONS = window.DGE_VERSIONS || {};
window.DGE_VERSIONS['core.js'] = 'v3.23 (DGE_LEGACY_SLUGS: redirects for the 28 Aug 2026 Kamashastra/Upaveda consolidation and the Nirukta/Jyotisha leaf-folder fix. On top of v3.22\'s shastra/subhashita redirect)';

// Converts a library.json catalog path ("data/x/y/data.json", always
// repo-root-relative for GitHub API use) into a slug ("x/y") and a
// fetch-relative path ("data/x/y/data.json", relative to this index.html
// which itself lives inside ). Shared with library.js (the browser
// modal), so both always agree on the same slug for the same file.
// AI-generated-content convention, going forward: any commentary/field key
// an AI pipeline writes (tools/gemini_enrich.py, tools/gemini_summarize.py,
// or anything added later) MUST be prefixed "gemini_" or "ai_". This is the
// one place the reader checks to decide whether to show the small "AI"
// badge (see footnotes.css's .dge-ai-badge, used by render.js's commentary
// blocks) -- a prefix convention rather than a maintained list, so a new
// field added by a future pipeline is flagged automatically without
// anyone having to remember to register it here. Matches this project's
// "don't fabricate" rule (PROJECT_BRIEF.md): a reader should never mistake
// unreviewed AI output for a vetted commentary, and a maintained list is
// exactly the kind of thing that silently goes stale.
window.dgeIsAiGeneratedCommentaryKey = function(key) {
  return /^(gemini|ai)_/.test(String(key || ''));
};

window.dgeLibraryPathToFetchPath = function(catalogPath) {
  return catalogPath.replace(/^dge\//, '');
};
window.dgeGranthaSlug = function(catalogPath) {
  return window.dgeLibraryPathToFetchPath(catalogPath).replace(/^data\//, '').replace(/\/data\.json$/, '');
};

// Forces a genuinely fresh reload — bypasses any browser/CDN caching of
// index.html, the JS files, and the content JSON, by navigating to a URL
// the browser has never seen before (same page, one changed query param).
// Only affects what gets fetched from GitHub; marks/notes/history/theme
// all live in localStorage and are completely unaffected.
// UI-discoverable alternative to manually typing ?pass=... into the URL —
// same validation, same effect, just reachable by tapping 🔑 instead of
// editing the address bar.
window.dgeShowAdminAccessPrompt = function() {
  const entered = prompt('Enter admin passkey:');
  if (!entered) return;
  const passkey = (window.appConfig && window.appConfig.secretPasskey) ? window.appConfig.secretPasskey : 'SHRI108';
  if (entered.toUpperCase() === passkey.toUpperCase()) {
    localStorage.setItem('acharyaAuthorized', 'true');
    if (typeof showToast === 'function') showToast('Admin access granted.');
    location.reload();
  } else {
    if (typeof showToast === 'function') showToast('Incorrect passkey.');
  }
};

// Explicit way to clear a granted access tier on this device, since it
// otherwise persists in localStorage indefinitely (by design, so the
// admin isn't re-prompted every visit) — without this there was no way
// to get back to the locked state short of clearing all site data.
window.dgeLogoutAdminAccess = function() {
  if (!confirm('Log out of Admin / Super Admin access on this device?')) return;
  localStorage.removeItem('acharyaAuthorized');
  localStorage.removeItem('is_superadmin');
  localStorage.removeItem('admin_root_path');
  if (typeof showToast === 'function') showToast('Access cleared.');
  location.reload();
};

window.dgeForceRefreshContent = function() {
  const url = new URL(window.location.href);
  url.searchParams.set('_refresh', Date.now());
  window.location.href = url.toString();
};

// Admin-editable text settings, saved by the Config Editor to a plain
// data file. Merged over the defaults from config.js at load, shallowly
// per top-level object — so the overrides file only ever needs to hold
// the fields actually changed, and anything absent falls back to the
// hardcoded default. config.js itself is never modified by the UI.
/* ---------------------------------------------------------------------- //
   Admin config lives outside  — see /admin/config/. These files used to
   sit in data/ and were fetched with a page-relative path, which only
   worked from pages one level deep. The path is now derived from this
   script's own URL (always <site>/js/), so it holds at any page depth
   and whether the site is served from a domain root or a project subpath.
   ---------------------------------------------------------------------- */
/* =========================================================================
   Links from before the taxonomy restructure.

   data/ was reorganised onto the taxonomy in DGE_Shastra_Taxonomy.md
   (see tools/restructure_taxonomy.py): "ancillary" turned out to be the
   Vedangas and became "vedanga", a lone "shankara_bhashya" moved under
   darshana/vedanta/advaita, and so on. Every ?path= link handed out before
   that names the old folder.

   GitHub Pages has no redirect layer, so without this a bookmark, a shared
   link or a search-engine result from before the move lands on "Not Yet
   Available" — the page looks broken rather than moved. Rewriting the prefix
   on the way in costs one pass over a 20-entry table and keeps every one of
   those links working.

   Longest source prefix wins, so the old ancillary/vyakarana is not shadowed
   by the old top-level vyakarana, which moved to the same place.

   Written out rather than derived: this table is the OLD names, and the only
   copy of them left in the codebase now that everything else has moved.
   ========================================================================= */
const DGE_LEGACY_SLUGS = {
  'ancillary/shiksha':      'vedanga/shiksha',
  'ancillary/pratishakhya': 'vedanga/shiksha/pratishakhya',
  'ancillary/vyakarana':    'vedanga/vyakarana',
  'ancillary/chandas':      'vedanga/chandas',
  'ancillary/nirukta':      'vedanga/nirukta',
  'ancillary/jyotisha':     'vedanga/jyotisha',
  'sutras/kalpa_sutras':    'vedanga/kalpa',
  'vyakarana':              'vedanga/vyakarana',
  // Resolution is a single pass, not a chain (see dgeUpgradeLegacySlug
  // below) -- every entry here must point straight at the CURRENT
  // location, never at an older name that itself needed upgrading.
  'sarvamoola_grantha':     'darshana/vedanta/dvaita/Anandamakaranda',
  // 9 Sep 2026 — Sumadhva Vijaya. The DvaitaVedanta extraction of this work
  // produced six tika folders and no mula, each "item" a whole sarga as one
  // wall of text with the verses it comments on buried inside it (the site
  // puts a whole sarga on one leaf; the importer assumes one leaf = one
  // verse). The same three commentaries now sit verse-by-verse on the
  // kavya_alankara copy, which has the better mula, so every one of those
  // paths lands on the real text instead. Exact slugs, not a prefix: there is
  // no tika_* folder on the other side to append.
  'darshana/vedanta/dvaita/DvaitaVedantaIn/later_acharyas/sumadhva_vijaya':
    'DvaitaVedanta/Itara/Kavya/sumadhva_vijaya/sarga_1',
  'darshana/vedanta/dvaita/DvaitaVedantaIn/later_acharyas/sumadhva_vijaya/tika_prakashika':
    'DvaitaVedanta/Itara/Kavya/sumadhva_vijaya/sarga_1',
  'darshana/vedanta/dvaita/DvaitaVedantaIn/later_acharyas/sumadhva_vijaya/tika_padarthadipikodbodhika':
    'DvaitaVedanta/Itara/Kavya/sumadhva_vijaya/sarga_1',
  'darshana/vedanta/dvaita/DvaitaVedantaIn/later_acharyas/sumadhva_vijaya/tika_mandopakarini':
    'DvaitaVedanta/Itara/Kavya/sumadhva_vijaya/sarga_1',
  'darshana/vedanta/dvaita/DvaitaVedantaIn/later_acharyas/sumadhva_vijaya/tika_shrichalarisheshacarya':
    'DvaitaVedanta/Itara/Kavya/sumadhva_vijaya/sarga_1',
  'darshana/vedanta/dvaita/DvaitaVedantaIn/later_acharyas/sumadhva_vijaya/tika_iti_shrimadvedangamuni':
    'DvaitaVedanta/Itara/Kavya/sumadhva_vijaya/sarga_1',
  'darshana/vedanta/dvaita/DvaitaVedantaIn/later_acharyas/sumadhva_vijaya/tika_iti_shrinarayanapanditacarya':
    'DvaitaVedanta/Itara/Kavya/sumadhva_vijaya/sarga_1',
  'shankara_bhashya':       'darshana/vedanta/advaita/shankara_bhashya',
  'itihasas':               'itihasa',
  'puranas':                'purana',
  'smritis':                'smriti_dharma/smriti',
  'dharmashastra':          'smriti_dharma/dharmashastra',
  'kavya':                  'kavya_alankara',
  'koshas':                 'kosha',
  'stotras':                'stotra',
  'pancharatra_agama':      'agama/vaishnava_agama/pancharatra',
  'dasakuta':               'DvaitaVedanta/Itara/DasaSahitya/dasakuta',
  'vyasakuta':              'DvaitaVedanta/Itara/DasaSahitya/vyasakuta',
  // 25 Aug 2026 Agama restructure. pancharatra/pashupata/shaiva_siddhanta
  // moved intact under new parents, so their sub-paths resolve exactly.
  // pratyabhijna/natha_sampradaya/shakta_agama were split across several
  // new parents (Kashmir Saivism, Shaiva Tantra, Vaishnava Agama...) --
  // no single target can route every sub-path correctly, so these land on
  // the closest new home rather than the exact leaf; see PENDING.md.
  'agama/pancharatra':      'agama/vaishnava_agama/pancharatra',
  'agama/pashupata':        'agama/shaiva_agama/pashupata',
  'agama/shaiva_siddhanta': 'agama/shaiva_agama/shaiva_siddhanta',
  'agama/pratyabhijna':     'agama/kashmir_shaivism',
  'agama/natha_sampradaya': 'agama/natha_hathayoga',
  'agama/shakta_agama':     'agama/shakta_tantra',
  // Pancharatra Ratnatraya/Pramukha/Anya regroup (25 Aug 2026) -- each
  // samhita's own sub-path (schema, items, etc.) is unaffected, only the
  // parent changed, so these resolve exactly like the moves above.
  'agama/vaishnava_agama/pancharatra/pancharatra_samhitas/sattvata_samhita':
    'agama/vaishnava_agama/pancharatra/pancharatra_samhitas/ratnatraya/sattvata_samhita',
  'agama/vaishnava_agama/pancharatra/pancharatra_samhitas/paushkara_samhita':
    'agama/vaishnava_agama/pancharatra/pancharatra_samhitas/ratnatraya/paushkara_samhita',
  'agama/vaishnava_agama/pancharatra/pancharatra_samhitas/jayakhya_samhita':
    'agama/vaishnava_agama/pancharatra/pancharatra_samhitas/ratnatraya/jayakhya_samhita',
  'agama/vaishnava_agama/pancharatra/pancharatra_samhitas/ahirbudhnya_samhita':
    'agama/vaishnava_agama/pancharatra/pancharatra_samhitas/pramukha_samhitas/ahirbudhnya_samhita',
  'agama/vaishnava_agama/pancharatra/pancharatra_samhitas/ishvara_samhita':
    'agama/vaishnava_agama/pancharatra/pancharatra_samhitas/pramukha_samhitas/ishvara_samhita',
  'agama/vaishnava_agama/pancharatra/pancharatra_samhitas/parama_samhita':
    'agama/vaishnava_agama/pancharatra/pancharatra_samhitas/pramukha_samhitas/parama_samhita',
  'agama/vaishnava_agama/pancharatra/pancharatra_samhitas/padma_samhita':
    'agama/vaishnava_agama/pancharatra/pancharatra_samhitas/pramukha_samhitas/padma_samhita',
  'agama/vaishnava_agama/pancharatra/pancharatra_samhitas/lakshmi_tantra':
    'agama/vaishnava_agama/pancharatra/pancharatra_samhitas/pramukha_samhitas/lakshmi_tantra',
  'agama/vaishnava_agama/pancharatra/pancharatra_samhitas/prakasha_samhita':
    'agama/vaishnava_agama/pancharatra/pancharatra_samhitas/pramukha_samhitas/prakasha_samhita',
  'agama/vaishnava_agama/pancharatra/pancharatra_samhitas/vishnu_samhita':
    'agama/vaishnava_agama/pancharatra/pancharatra_samhitas/pramukha_samhitas/vishnu_samhita',
  'agama/vaishnava_agama/pancharatra/pancharatra_samhitas/vishvaksena_samhita':
    'agama/vaishnava_agama/pancharatra/pancharatra_samhitas/pramukha_samhitas/vishvaksena_samhita',
  'agama/vaishnava_agama/pancharatra/pancharatra_samhitas/hayagriva_samhita':
    'agama/vaishnava_agama/pancharatra/pancharatra_samhitas/pramukha_samhitas/hayagriva_samhita',
  'agama/vaishnava_agama/pancharatra/pancharatra_samhitas/naradiya_samhita':
    'agama/vaishnava_agama/pancharatra/pancharatra_samhitas/anya_samhitas/naradiya_samhita',
  'agama/vaishnava_agama/pancharatra/pancharatra_samhitas/parashara_samhita':
    'agama/vaishnava_agama/pancharatra/pancharatra_samhitas/anya_samhitas/parashara_samhita',
  'agama/vaishnava_agama/pancharatra/pancharatra_samhitas/vasishtha_samhita':
    'agama/vaishnava_agama/pancharatra/pancharatra_samhitas/anya_samhitas/vasishtha_samhita',
  // 23 Aug 2026 restructure: dvaitavedanta/ (a separate top-level 895-item
  // tree) moved to sit alongside sarvamula under Vedanta/Dvaita, and
  // sarvamula itself was renamed SarvaMula for display-name consistency
  // with the same pass's other renames. stotra/pns became stotra/
  // PrahladaKrutaNarasimha for the same reason.
  'dvaitavedanta':                       'darshana/vedanta/dvaita/DvaitaVedantaIn',
  'darshana/vedanta/dvaita/sarvamula':   'darshana/vedanta/dvaita/Anandamakaranda',
  'stotra/pns':                          'DvaitaVedanta/Itara/Stotra/prahlada_kruta_narasimha',
  // 25 Aug 2026 Purana restructure: purana/<X> split into purana/maha_purana/
  // (the 18 traditional Mahapuranas, plus the Bhagavata-Madhva variant and
  // Vayu Purana, already present) and purana/upa_purana/ (was upapuranas).
  // Each work's own sub-path is unaffected, only the parent changed.
  'purana/bhagavata_purana':        'purana/maha_purana/bhagavata_purana',
  'purana/bhagavata_purana_madhva': 'purana/maha_purana/bhagavata_purana_madhva',
  'purana/brahma_purana':           'purana/maha_purana/brahma_purana',
  'purana/padma_purana':            'purana/maha_purana/padma_purana',
  'purana/vishnu_purana':           'purana/maha_purana/vishnu_purana',
  'purana/shiva_purana':            'purana/maha_purana/shiva_purana',
  'purana/narada_purana':           'purana/maha_purana/narada_purana',
  'purana/markandeya_purana':       'purana/maha_purana/markandeya_purana',
  'purana/agni_purana':             'purana/maha_purana/agni_purana',
  'purana/bhavishya_purana':        'purana/maha_purana/bhavishya_purana',
  'purana/brahmavaivarta_purana':   'purana/maha_purana/brahmavaivarta_purana',
  'purana/linga_purana':            'purana/maha_purana/linga_purana',
  'purana/varaha_purana':           'purana/maha_purana/varaha_purana',
  'purana/skanda_purana':           'purana/maha_purana/skanda_purana',
  'purana/vamana_purana':           'purana/maha_purana/vamana_purana',
  'purana/kurma_purana':            'purana/maha_purana/kurma_purana',
  'purana/matsya_purana':           'purana/maha_purana/matsya_purana',
  'purana/garuda_purana':           'purana/maha_purana/garuda_purana',
  'purana/brahmanda_purana':        'purana/maha_purana/brahmanda_purana',
  'purana/vayu_purana':             'purana/maha_purana/vayu_purana',
  'purana/upapuranas':              'purana/upa_purana',
  // 25 Aug 2026: top-level nitishastra/ (added 20 Aug) and shastra/niti_shastra/
  // (added 23 Aug, unaware the top-level one already existed) were two
  // independently-built, uncoordinated copies of the same section --
  // shastra/niti_shastra/hitopadesha/mula (718 DCS verses) duplicated
  // nitishastra/hitopadesha (5 GRETIL section-blocks) outright. Consolidated
  // onto shastra/niti_shastra/ (finer-grained, and matches artha_shastra's
  // existing home there); the GRETIL hitopadesha copy was dropped, not moved.
  'nitishastra/hitopadesha':        'shastra/niti_shastra/hitopadesha/mula',
  'nitishastra/chanakya_niti':      'shastra/niti_shastra/chanakya_niti',
  'nitishastra/chanakya_sutra':     'shastra/niti_shastra/chanakya_sutra',
  'nitishastra/kamandakiya_nitisara': 'shastra/niti_shastra/kamandakiya_nitisara',
  'nitishastra':                    'shastra/niti_shastra',

  // Subhashita placeholder moved from shastra/ directly to
  // shastra/niti_shastra/ (25 Aug 2026) -- wisdom-verse anthologies belong
  // alongside Chanakya Niti/Hitopadesha, not as a shastra/ sibling.
  'shastra/subhashita':              'shastra/niti_shastra/subhashita',

  // 28 Aug 2026: project lead's explicit correction reversed the 20 Aug
  // decision that put Kamashastra under upaveda/ -- it is not one of the
  // traditional four Upavedas in most classical enumerations (the common
  // list is Ayurveda/Dhanurveda/Gandharvaveda/Arthashastra or
  // Sthapatyaveda), so it moves to shastra/kama_shastra/ instead. That
  // move also surfaced an independently-added shastra/kama_shastra/mula
  // (DCS treebank Kamasutra) that duplicated upaveda/kamashastra/kamasutra
  // (GRETIL Kamasutra) outright -- same pattern as the nitishastra
  // duplication above, but this time BOTH digitizations were kept, side
  // by side under kamasutra/, rather than dropping either.
  'upaveda/kamashastra/kamasutra':    'shastra/kama_shastra/kamasutra/mula_gretil',
  'shastra/kama_shastra/mula':        'shastra/kama_shastra/kamasutra/mula_dcs',
  'upaveda/kamashastra/pancashayaka': 'shastra/kama_shastra/pancashayaka',
  'upaveda/kamashastra/smaradipika':  'shastra/kama_shastra/smaradipika',
  'upaveda/kamashastra':              'shastra/kama_shastra',

  // 28 Aug 2026: vedas/upaveda/ and the top-level upaveda/ turned out to be
  // two independently-built, uncoordinated copies of Upaveda content --
  // vedas/upaveda/ayurveda held the full Samhita/Rasashastra corpus plus a
  // real Dhanurveda text, upaveda/ayurveda held a smaller, differently-
  // scoped Nighantu/Madhava-Nidana set, with no overlapping filenames.
  // Merged onto the top-level upaveda/ (a sibling of vedanga/, not nested
  // under vedas/, matching how vedanga itself is organized) -- one prefix
  // entry covers every leaf under the old tree.
  'vedas/upaveda':                    'upaveda',

  // 28 Aug 2026: nirukta/ and jyotisha/ each held their one grantha
  // directly in the category folder (vedanga/nirukta/data.json) instead of
  // a named leaf folder the way every other vedanga category does. That
  // mismatch is what made the library tree (js/library.js's
  // dgeBuildTree) attach them as bare, unlabelled rows on vedanga/ itself
  // instead of their own labelled, counted category -- a leaf with no leaf
  // folder of its own gets grouped under its PARENT node instead. Given a
  // real leaf folder ("mula") like every sibling category has.
  'vedanga/nirukta':                  'vedanga/nirukta/mula',
  'vedanga/jyotisha':                 'vedanga/jyotisha/mula'
};

window.dgeUpgradeLegacySlug = function (slug) {
  if (!slug) return slug;
  let best = null;
  Object.keys(DGE_LEGACY_SLUGS).forEach(function (src) {
    if (slug === src || slug.indexOf(src + '/') === 0) {
      if (!best || src.length > best.length) best = src;
    }
  });
  if (!best) return slug;
  return DGE_LEGACY_SLUGS[best] + slug.slice(best.length);
};
const dgeUpgradeLegacySlug = window.dgeUpgradeLegacySlug;

window.dgeAdminConfigUrl = window.dgeAdminConfigUrl || function (name) {
  const self = (document.currentScript && document.currentScript.src) ||
               (window.DGE_SCRIPT_BASE || '');
  try { return new URL('../admin/config/' + name, self).href; }
  catch (e) { return '../admin/config/' + name; }   // fail soft, never throw
};

/* What's New and Coming Soon are content, not settings — admin/content/, not
   admin/config/. Loaded here so the Site Settings editor can fill its form
   from the same source the reader sees; modals.js re-fetches on open so a
   freshly published update reaches someone who already has the site loaded. */
window.dgeContentUrl = window.dgeContentUrl || function (name) {
  const self = (document.currentScript && document.currentScript.src) ||
               (window.DGE_SCRIPT_BASE || '');
  try { return new URL('../admin/content/' + name, self).href; }
  catch (e) { return '../admin/content/' + name; }
};

window.dgeWhatsNewPromise = fetch(window.dgeContentUrl('whats-new.json') + '?t=' + Date.now(),
                                  { cache: 'no-store' })
  .then(res => (res.ok ? res.json() : null))
  .catch(() => null)
  .then(wn => {
    // _readme is left in place: the Site Settings editor writes this file
    // back and preserves it from here, and nothing renders it — the panel
    // reads only enabled/updates/comingSoon.
    if (wn) window.WHATS_NEW_CONFIG = wn;
    return wn;
  });

/* The Support and About panels' text. These were constants in config.js; they
   are content, so they come from admin/content/reader.json. Everything that
   reads window.SPONSOR_CONFIG and friends is unchanged — the globals are set
   here instead of there, before the first render. */
window.dgeReaderContentPromise = fetch(window.dgeContentUrl('reader.json') + '?t=' + Date.now(),
                                       { cache: 'no-store' })
  .then(res => (res.ok ? res.json() : null))
  .catch(() => null)
  .then(rc => {
    if (!rc) {
      // Empty shapes rather than undefined: every reader of these does
      // `(cfg.list || [])`, and a panel with nothing in it is a better
      // failure than a page that throws on the way to drawing a verse.
      window.SPONSOR_CONFIG = window.SPONSOR_CONFIG || { enabled: false };
      window.CONTRIBUTORS_CONFIG = window.CONTRIBUTORS_CONFIG || { enabled: false, contributors: [] };
      window.KEY_SPONSORS_CONFIG = window.KEY_SPONSORS_CONFIG || { enabled: false, sponsors: [] };
      window.SITE_CONFIG = window.SITE_CONFIG || {};
      return null;
    }
    if (rc.SPONSOR_CONFIG) window.SPONSOR_CONFIG = rc.SPONSOR_CONFIG;
    if (rc.CONTRIBUTORS_CONFIG) window.CONTRIBUTORS_CONFIG = rc.CONTRIBUTORS_CONFIG;
    if (rc.KEY_SPONSORS_CONFIG) window.KEY_SPONSORS_CONFIG = rc.KEY_SPONSORS_CONFIG;
    // content-inline.js (loaded on this page via <body data-content-file=
    // "admin/content/reader.json">) stages every edit into window.SITE_CONFIG
    // by dotted path and expects the live page to already be reading off
    // that same object -- rc IS this file, so pointing SITE_CONFIG at it
    // directly means an edit to e.g. "SPONSOR_CONFIG.introText" lands on the
    // exact object window.SPONSOR_CONFIG already references, no copying.
    window.SITE_CONFIG = rc;
    return rc;
  });

window.dgeConfigOverridesPromise = Promise.all([
    window.dgeReaderContentPromise,
    fetch(window.dgeAdminConfigUrl('config-overrides.json') + '?t=' + Date.now(), { cache: 'no-store' })
      .then(res => res.ok ? res.json() : null)
      .catch(() => null)
  ])
  // Sequenced deliberately: reader.json REPLACES these globals, so an override
  // merged before it arrived would be thrown away with the object it landed on.
  .then(([, ov]) => {
    if (!ov) return null;
    const targets = {
      appConfig: window.appConfig,
      SPONSOR_CONFIG: window.SPONSOR_CONFIG,
      CONTRIBUTORS_CONFIG: window.CONTRIBUTORS_CONFIG,
      KEY_SPONSORS_CONFIG: window.KEY_SPONSORS_CONFIG
      // WHATS_NEW_CONFIG is not here: it is admin/content/whats-new.json now,
      // fetched fresh by modals.js rather than merged once at boot.
    };
    Object.keys(targets).forEach(k => {
      if (ov[k] && targets[k]) Object.assign(targets[k], ov[k]);
    });
    console.log(`[Config] Applied overrides for: ${Object.keys(ov).join(', ')}`);
    return ov;
  });

// Fetched once, shared with library.js so the browser modal doesn't need
// a second network round trip for the same file. Cache-busted with both
// cache:'no-store' AND a timestamp query param — without this, a browser
// (or GitHub Pages' CDN) can keep serving library.json from BEFORE your
// most recent content update indefinitely, making newly-added/newly-
// populated granthas silently invisible even though the real files are
// correctly on GitHub.
window.dgeLibraryCatalogPromise = fetch('data/library.json?t=' + Date.now(), { cache: 'no-store' })
  .then(res => res.ok ? res.json() : null)
  .catch(() => null);

// Opts this page OUT of the browser's back/forward cache (bfcache).
// Without this, navigating between granthas (a real page load to the
// same index.html with a different ?path=) can sometimes have the
// browser restore a frozen snapshot of the PREVIOUS page instead of
// actually re-running this script — which is exactly what an "Error"
// message from an earlier grantha still showing under a new URL means.
// An empty pagehide/unload listener is the standard, reliable way to
// disable bfcache eligibility across browsers.
window.addEventListener('pagehide', function () {});

// index.html is deliberately NOT cache-busted (browsers and the CDN may
// cache it), while every JS/CSS file is. That combination means a stale
// cached index.html can pair OLD markup with NEW scripts — which breaks
// things in confusing ways, because the scripts query elements the old
// HTML doesn't contain. This has caused real debugging detours, so rather
// than leaving it to be rediscovered each time, the HTML now stamps its
// own version and the JS checks it matches. Bump BOTH on any release that
// changes index.html's structure.
window.DGE_EXPECTED_HTML_VERSION = '4.68.0';
document.addEventListener('DOMContentLoaded', () => {
  const meta = document.querySelector('meta[name="dge-html-version"]');
  const actual = meta ? meta.getAttribute('content') : '(none)';
  if (actual !== window.DGE_EXPECTED_HTML_VERSION) {
    const msg = `Stale page detected: index.html is version ${actual} but the scripts expect ${window.DGE_EXPECTED_HTML_VERSION}. ` +
                `The browser is serving a cached index.html. Pull down to refresh, or clear this site's cache.`;
    console.error('[Version] ' + msg);
    const bar = document.createElement('div');
    bar.style.cssText = 'position:fixed; top:0; left:0; right:0; z-index:99999; background:#b3261e; color:#fff; ' +
      'font-size:12px; padding:10px 14px; text-align:center; line-height:1.4;';
    bar.innerHTML = 'Cached page detected — some features will misbehave.<br>' +
      '<b style="text-decoration:underline;">Tap here to reload</b>';
    // location.reload(true)'s "force" argument is a Netscape-era relic no
    // current browser honours — it behaves identically to a plain reload(),
    // which is exactly the reload that got the reader stuck on this stale
    // page in the first place (a normal reload can still be answered from
    // cache; that's the whole bug this banner exists to catch). Navigating
    // to a URL that has never been requested before — this same page plus a
    // cache-busting query param — has no existing cache entry to be
    // answered from, so it is guaranteed to reach the network.
    bar.onclick = () => {
      const url = new URL(location.href);
      url.searchParams.set('_dgev', Date.now().toString());
      location.href = url.toString();
    };
    document.body.appendChild(bar);
  }
});

// Every other module in this app (render, audio, markers, notes, search,
// filter, ai) reads grantha data in ONE shape: {metadata, shlokas: {n:
// {sa, commentaries}}, totalShlokas}, with n a plain sequential integer.
// That shape matches PNS exactly, but the newer vedic_text schema
// (Rigveda etc.) uses a different shape: {schema, default_author,
// items: [{id, samhita_patha, rishi, devata, ...}]}. Rather than teaching
// every one of those modules a second data shape, this adapts new-schema
// data into the SAME old shape right after fetching, once, here — so
// everything downstream keeps working completely unchanged.
// This is what was actually throwing "Cannot read properties of
// undefined (reading 'totalShlokas')": stotraData.metadata didn't exist
// at all for this schema family, since it was never being adapted.
// The transliteration library represents Vedic pitch accents using
// codepoints from the little-supported "Vedic Extensions" Unicode block
// (U+1CD0-U+1CFF, added far more recently and supported by very few
// fonts) instead of the standard udatta/anudatta marks that have been in
// the CORE Devanagari block since Unicode 1.1 (1993) and are supported
// by virtually every Devanagari font. That mismatch is what was
// rendering as stray quote-mark-like glyphs instead of proper accent
// marks — confirmed by checking the actual codepoints against real
// rendered output, not guessed. Remapped here, as early as possible, so
// every downstream use (display, copy, search, share) benefits uniformly.
function dgeToDevanagariDigits(s) {
  const map = { '0': '०', '1': '१', '2': '२', '3': '३', '4': '४', '5': '५', '6': '६', '7': '७', '8': '८', '9': '९' };
  return String(s).replace(/[0-9]/g, (d) => map[d]);
}

function dgeSanitizeVedicAccents(text) {
  if (!text) return text;
  return text
    .replace(/\u1CD3/g, '\u0951') // VEDIC SIGN NIHSHVASA (used for acute/udātta) -> DEVANAGARI STRESS SIGN UDATTA
    .replace(/\u1CD9/g, '\u0952') // VEDIC TONE ... INDEPENDENT SVARITA (used for grave) -> DEVANAGARI STRESS SIGN ANUDATTA
    // Siddhanta Kaumudi's own text carries internal cross-references to its
    // own serial rule numbering as raw "<{SK354}>" markers -- an unresolved
    // import-template artifact (1373 of them in that one file), not a
    // rendering choice. Reported live as "the 4th item's text is incorrect"
    // because that IS what a reader sees: bracket-and-number junk sitting
    // mid-sentence in an otherwise normal commentary. No authoritative
    // SK-number -> sutra concordance exists in this corpus to turn these
    // into real links (this data.json's own item order is Ashtadhyayi
    // adhyaya.pada.sutra order, not Siddhanta Kaumudi's own reordered
    // sequence, so the number can't be resolved from position either) --
    // rendered as the conventional Sanskrit-commentary parenthetical
    // citation abbreviation instead of either the raw template syntax or
    // silently deleting real cross-reference information.
    .replace(/<\{SK(\d+)\}>/g, (_, num) => '(सि.कौ.' + dgeToDevanagariDigits(num) + ')')
    // Four more leaked machine-tagging markers in the same file, found by
    // diffing this corpus's siddhanta_kaumudi text against the source
    // repo's own clean base file (github.com/drdhaval2785/siddhantakaumudi,
    // sk0.txt) -- same species of bug as the SK-ref case above (an
    // unresolved import-template artifact, not a scholarly variant), just
    // never caught because it uses different delimiter punctuation.
    // drdhaval2785's own readme documents "{$ {!verbnum verb!}+
    // verbmeaning$}" as HIS pipeline's internal tagging syntax for dhatu
    // (verbal root) citations, added mechanically by his step1.py when
    // producing the tagged sk1.txt from the clean sk0.txt -- this corpus's
    // import evidently pulled from that tagged file and never stripped the
    // tags. Confirmed against sk0.txt directly: the same passage there
    // (e.g. item 1.2.2's "उद्विजिष्यते" continuation) reads plain running
    // text with no braces/dollar-signs/bangs at all. `<<...>>` (quoting
    // another sutra's headword, paired with the already-handled SK-ref
    // number) and `<!...!>` (marking a vartika, paired with a following
    // "(वार्तिकम्)") are this repo's own -- not drdhaval2785's -- wrapper
    // conventions for the same underlying content, also never resolved at
    // render time; `<ऽ...ऽ>` (a single occurrence, item 4.1.1, quoting a
    // paribhasha maxim) is normalized to this same corpus's own established
    // bracket convention for that (see item 1.1.50's "[(परिभाषा - ) ...]").
    // A corpus-wide check after this fix (stripping all six known patterns)
    // found the bracket/brace/dollar/bang characters otherwise unused in
    // this file's Sanskrit prose except one genuine vocative "!" in an
    // example sentence -- confirming these six patterns account for
    // essentially all of it, not just the common cases.
    .replace(/\{!([^{}]*)!\}/g, '$1')
    .replace(/\{\$([\s\S]*?)\$\}/g, '$1')
    .replace(/<!([\s\S]*?)!>/g, '$1')
    .replace(/<<([^<>]*)>>/g, '$1')
    .replace(/<ऽ([^<>]*)ऽ>/g, '[(परिभाषा - )$1]')
    .replace(/<\{([^}]*)\}>/g, '$1');
}

// Copyright gate (Category 4 platform issue): the Mahabharata Kannada
// translation + Madhvacharya's own Tatparya Nirnaya excerpts interleaved in
// it (data/itihasa/mahabharata_kannada/, ~98,500 verses) were extracted
// from a Pejawar Matha Android app's asset bundle -- no license field
// anywhere, only a foreword/blessing as attribution, not a rights grant.
// This project's own standing rule (PROJECT_BRIEF.md) is "absence of a
// licence is not permission." "kannada" as a commentary key is unique to
// this one source across the whole corpus (checked: no other data.json
// uses it), so gating by key name alone is safe -- it cannot accidentally
// hide some unrelated, properly-licensed Kannada text elsewhere.
//
// Filtered here, at the single point every shloka's commentaries object is
// built, rather than in render.js -- render.js is not the only consumer
// (ai.js reads shloka.commentaries directly to feed AI features, and the
// availableCommentaries picker/search-scope dropdown are built from this
// same normalization pass), so gating downstream would need to be repeated
// at every call site with no guarantee of catching them all. The data
// itself is untouched on disk (reversible, no loss); this only decides
// what a NORMALIZED grantha object exposes to the rest of the app.
// window.appConfig.showCopyrightGatedCommentaries is the reader-facing
// toggle this backlog item asked for (default off/hidden) -- flipping it
// takes effect on the next grantha load (this function reruns whenever a
// grantha's data is (re)fetched), not instantly on an already-open page,
// which is an acceptable cost for what should be a rare, deliberate
// research toggle rather than a startup-time architecture change.
const DGE_COPYRIGHT_GATED_COMMENTARY_KEYS = { kannada: true };
function dgeVisibleCommentaries(commentaries) {
  if (!commentaries) return commentaries;
  if (window.appConfig && window.appConfig.showCopyrightGatedCommentaries) return commentaries;
  const out = {};
  Object.keys(commentaries).forEach((k) => {
    if (!DGE_COPYRIGHT_GATED_COMMENTARY_KEYS[k]) out[k] = commentaries[k];
  });
  return out;
}

// The GRETIL smriti imports carry the source edition's own page markers,
// transliterated wholesale into Devanagari -- "(\u0907,\u0967, \u092A\u094D. \u0969\u096D)" is "(I,1,
// p. 37)" -- 357 of them, every one confined to data/smriti_dharma
// (measured across the whole corpus before writing this, so the pattern
// can afford to be narrow: a parenthesis containing p+virama+dot and
// digits, the page abbreviation no verse ever contains). Stripped at
// render time so the stored data keeps mirroring its source.
function dgeStripEditionMarkers(text) {
  if (!text || text.indexOf('\u092A\u094D.') === -1) return text;
  return text.replace(/\s*\([^()]{0,40}\u092A\u094D\.\s*[\u0966-\u096F0-9]+[^()]{0,25}\)/g, '')
             .replace(/[ \t]+([\u0964\u0965])/g, ' $1').replace(/\s{2,}/g, ' ').trim();
}

// Combines bhagavata_ref {skandha,adhyaya,verse} with references[].{target,unit_id}
// into the existing ?path=&jumpVedicId=<unitId>#<verseNo> addressing; null if incomplete.
function dgeBuildBhagavataRefLink(bhagavataRef, references) {
  if (!bhagavataRef || bhagavataRef.skandha == null || bhagavataRef.adhyaya == null || bhagavataRef.verse == null) return null;
  const ref = Array.isArray(references) ? references.find(r => r && r.target && r.unit_id) : null;
  if (!ref) return null;
  const jumpVedicId = ref.unit_id + '#' + bhagavataRef.verse;
  const url = 'index.html?path=' + ref.target + '&jumpVedicId=' + encodeURIComponent(jumpVedicId);
  return { url, label: `भा. ${bhagavataRef.skandha}.${bhagavataRef.adhyaya}.${bhagavataRef.verse}` };
}

function dgeNormalizeGranthaData(data, granthaTitle) {
  if (!data) return data;
  if (data.shlokas) return data; // already the expected shape (e.g. PNS) -- nothing to do

  // Display labels for known translation/commentary source keys -- falls
  // back to a capitalized version of the key itself for anything not
  // listed here, so adding a new source later doesn't require touching
  // this function again.
  const KNOWN_COMMENTARY_LABELS = {
    narayana_vyakhya: 'श्री नारायणाचार्य व्याख्या',
    griffith: 'Griffith (1889 English Translation)',
    macdonell: 'Macdonell (English Translation)',
    oldenberg: 'Oldenberg (English Translation)',
    geldner: 'Geldner (German Translation)',
    grassmann: 'Grassmann (German Translation)',
    elizarenkova: 'Elizarenkova (Russian Translation)',
    // Traditional bhashya layers (see tools/sayana_smriti/). Unlike the six
    // above, these are commentary rather than translation -- Sayana is the
    // first traditional commentator to enter the Vedic corpus.
    sayana: 'सायणभाष्यम् — Sāyaṇa (Ṛgveda-bhāṣya)',
    // Sayana opens each sukta with a note on its viniyoga, rishi and chandas
    // that glosses no single mantra. It rides on the sukta's first mantra
    // under its own key so that mantra's commentary stays its own.
    sayana_sukta: 'सायणभाष्यम् — Sāyaṇa (introduction to the sūkta)',
    wilson: 'Wilson (English Translation, after Sāyaṇa)',
    artha: 'Translation',
    // Word-by-word Kannada anvaya-artha printed under each verse in the
    // Śrīpādarāja Maṭha (Muḷabāgilu) edition of Madhva's Jayantī Nirṇaya —
    // by Śrī Agrahāra Nārāyaṇa Tantri. A Kannada gloss, not a translation,
    // so it gets its own key/label (cf. narayana_vyakhya above).
    kannada_anvaya: 'ಅನ್ವಯಾರ್ಥ — Kannada anvaya (Agrahāra Nārāyaṇa Tantri)',
    // OCR'd from a published book (tools/link_english_commentary.py), not
    // hand-typed -- attributed to its actual translator like griffith/wilson
    // above, not a generic "English Translation" label.
    pavamanacharya_english: 'Huli V. Pavamanacharya (English Translation)',
    // Gemini-generated, unreviewed -- label says so explicitly rather than
    // implying scholarly authority, per this project's "don't fabricate"
    // rule (PROJECT_BRIEF.md): the reader should never mistake an AI
    // first-pass for a vetted commentary.
    gemini_padaccheda: 'AI Padaccheda (Gemini, unreviewed)',
    gemini_anvaya: 'AI Anvaya (Gemini, unreviewed)',
    gemini_summary: 'AI Summary (Gemini, unreviewed)'
  };

  // dasa_pada_text schema (see data/schemas.json): each item is one
  // Haridasa composition (pada/suladi/ugabhoga/...) with a nested
  // text{kannada, devanagari, iast, source_roman} object of stanzas->lines
  // per script, not a flat sanskrit_text string -- the shape-sniffing
  // branches below would see item.text as a truthy object and stringify it
  // wrong. Detected by data.schema directly rather than shape-sniffed,
  // since this is the one schema where the item shape alone (an object
  // with a "text" key) would otherwise collide with the generic branch's
  // own item.text string check below.
  if (data.schema === 'dasa_pada_text' && Array.isArray(data.items)) {
    const shlokas = {};
    let n = 0;
    let withMeaning = 0;
    data.items.forEach(item => {
      n++;
      const text = item.text || {};
      // Kannada is the source language; Devanagari/IAST are auto-
      // transliterated fallbacks for the rare item missing Kannada;
      // source_roman is the source site's own ad hoc romanization, tried
      // last since DGE didn't generate it.
      const stanzas = (text.kannada && text.kannada.length) ? text.kannada
        : (text.devanagari && text.devanagari.length) ? text.devanagari
        : (text.iast && text.iast.length) ? text.iast
        : (text.source_roman || []);
      // '/' between lines, '//' between stanzas -- render.js's shloka
      // renderer already turns a "/" run into <br> (mulaHtml's own
      // `.replace(/\s*\/\s*/g, '<br>')`), so this needs no new render code.
      const flat = stanzas.map(lines => (lines || []).join(' / ')).join(' // ');
      const commentaries = {};
      if (item.meaning) { commentaries.artha = item.meaning; withMeaning++; }
      shlokas[n] = {
        sa: dgeStripEditionMarkers(flat),
        vedicId: (item.title && (item.title.kn || item.title.latin)) || '',
        unitId: item.id || '',
        rishi: '', devata: '', chandas: '', padapatha: '',
        deity: item.deity || '',
        raga: item.raga || '',
        tala: item.tala || '',
        commentaries: commentaries,
        geminiEnrichment: null
      };
    });
    console.log(`[Data] Normalized "${granthaTitle || 'untitled'}" (dasa_pada_text): ` +
      `${n} composition(s), ${withMeaning} with a meaning/artha block`);
    return {
      metadata: {
        title: granthaTitle || data.schema || 'Untitled',
        author: data.default_author || '',
        totalShlokas: n,
        availableCommentaries: withMeaning ? { artha: 'Translation' } : {}
      },
      shlokas,
      totalShlokas: n
    };
  }

  // itihasa_purana_text schema (see data/schemas.json): each item is a
  // whole chapter (sarga/adhyaya/skandha) carrying its OWN nested shlokas[]
  // array, unlike vedic_text's items (each item IS one verse, handled by
  // the branch below). Detected by the first item actually having a
  // shlokas array rather than a direct sa/samhita_patha string. Flattened
  // here into the same sequential-integer-key shape every other module
  // assumes; the chapter's "reference" (e.g. "Bala Kanda, Sarga 3") rides
  // along in the existing generic 'vedicId' extra field rather than
  // needing a new one wired through render/audio/filter/etc.
  if (Array.isArray(data.items) && data.items.length && Array.isArray(data.items[0].shlokas)) {
    const shlokas = {};
    const availableCommentaries = {};
    let n = 0;
    let shlokasWithCommentaries = 0;
    data.items.forEach(chapter => {
      (chapter.shlokas || []).forEach(v => {
        n++;
        // shlokas[].bhashya[] is [{commentator, text, language, source}] per
        // schemas.json; artha is the plain translation. Both are folded into
        // the same flat 'commentaries' dict the branch below builds, so a
        // Manu shloka with Medhatithi displays exactly like a Rigveda mantra
        // with Sayana -- no renderer, filter or audio change needed.
        const commentaries = {};
        if (v.artha) {
          commentaries.artha = v.artha;
          availableCommentaries.artha = KNOWN_COMMENTARY_LABELS.artha || 'Translation';
        }
        (v.bhashya || []).forEach(b => {
          if (!b || !b.text) return;
          // Key derived from the commentator string rather than hard-coded,
          // so adding Kulluka or Govindaraja later needs no change here.
          // Fold IAST diacritics FIRST -- without this "Medhātithi (Manubhāṣya)"
          // slugs to "medh_tithi_manubh_ya", because every accented letter falls
          // outside [a-z0-9] and is treated as a separator. NFD strips the
          // combining marks; the explicit pairs below catch the precomposed
          // Indological letters (ṛ ṣ ṭ ḍ ṇ ṃ ḥ) that have no ASCII decomposition.
          const key = String(b.commentator || 'bhashya')
            .toLowerCase()
            .normalize('NFD').replace(/[̀-ͯ]/g, '')
            .replace(/[āàáâä]/g, 'a').replace(/[īìíîï]/g, 'i').replace(/[ūùúûü]/g, 'u')
            .replace(/[ṛṝ]/g, 'r').replace(/[ḷḹ]/g, 'l').replace(/[ṃṁ]/g, 'm')
            .replace(/[ḥ]/g, 'h').replace(/[ñṅṇ]/g, 'n').replace(/[śṣ]/g, 's')
            .replace(/[ṭ]/g, 't').replace(/[ḍ]/g, 'd')
            .replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '') || 'bhashya';
          // See dgeVisibleCommentaries's own comment: not currently exercised
          // by any real data in this shape (the actual gated content uses
          // the flat-items branch below), kept here defensively so a future
          // bhashya[] source naming a commentator this key would slugify to
          // "kannada" can't slip through un-gated.
          if (DGE_COPYRIGHT_GATED_COMMENTARY_KEYS[key] && !(window.appConfig && window.appConfig.showCopyrightGatedCommentaries)) return;
          commentaries[key] = b.text;
          availableCommentaries[key] = b.commentator || KNOWN_COMMENTARY_LABELS[key] ||
            (key.charAt(0).toUpperCase() + key.slice(1));
        });
        if (Object.keys(commentaries).length) shlokasWithCommentaries++;
        shlokas[n] = {
          sa: dgeStripEditionMarkers(dgeSanitizeVedicAccents(v.sanskrit_text || v.sa || '')),
          vedicId: chapter.reference ? (chapter.reference + (v.number != null ? ' · ' + v.number : '')) : '',
          unitId: chapter.id || '',
          unitNo: v.number != null ? String(v.number) : '',   // data-side indexes address nested verses as <chapter id>#<number>
          commentaries: commentaries,
          geminiEnrichment: v.gemini_enrichment || null
        };
      });
    });
    console.log(`[Data] Normalized "${granthaTitle || 'untitled'}" (itihasa_purana_text): ` +
      `${data.items.length} chapter(s), ${n} shloka(s) total, ` +
      `${shlokasWithCommentaries} with commentaries, ` +
      `commentary keys found: ${JSON.stringify(Object.keys(availableCommentaries))}`);
    return {
      metadata: {
        title: granthaTitle || data.schema || 'Untitled',
        author: data.default_author || '',
        totalShlokas: n,
        availableCommentaries: availableCommentaries
      },
      shlokas,
      totalShlokas: n
    };
  }

  if (Array.isArray(data.items)) {
    const shlokas = {};
    const availableCommentaries = {};
    let itemsWithCommentaries = 0;
    data.items.forEach((item, idx) => {
      // Sequential 1..N internal key -- every other module assumes plain
      // integer indices. The real Vedic reference (e.g. "1.1.01") is kept
      // as a visible field (see the 'vedicId' extra field in config.js)
      // rather than used as the internal key.
      const n = idx + 1;
      const commentaries = dgeVisibleCommentaries(
        (item.commentaries && typeof item.commentaries === 'object' && !Array.isArray(item.commentaries))
          ? item.commentaries
          : {}
      );
      if (Object.keys(commentaries).length) itemsWithCommentaries++;
      Object.keys(commentaries).forEach(key => {
        if (!availableCommentaries[key]) {
          availableCommentaries[key] = KNOWN_COMMENTARY_LABELS[key] || (key.charAt(0).toUpperCase() + key.slice(1));
        }
      });
      shlokas[n] = {
        // schemas.json declares a different primaryTextField per schema --
        // samhita_patha for vedic_text, sanskrit_text for generic and
        // several others (see its own "primaryTextField" entries) -- but
        // this branch only ever checked samhita_patha/sa. Any "generic"
        // schema import (importers/gretil_bulk.py's group_items(), used by
        // every sutra/vedanga entry in its registry) writes sanskrit_text,
        // so every one of those would have rendered a blank verse the
        // first time it was actually run. Caught before any such text
        // shipped, not after.
        // "text" too, for English-only items (e.g. the Ganguli Mahabharata
        // translation's own "generic" schema, {id, title, author, text},
        // no sanskrit_text field at all since there IS no Sanskrit line) --
        // found the same way as sanskrit_text above: confirmed live, 16
        // already-shipped translation_ganguli files (1,577 items) all
        // rendering blank against this exact gap.
        sa: dgeStripEditionMarkers(dgeSanitizeVedicAccents(item.samhita_patha || item.sanskrit_text || item.text || item.sa || '')),
        // Same importer's items carry a human-readable "reference" (e.g.
        // "Yāska — Nirukta, adhyaya 1") alongside the bare slug id --
        // prefer it, matching the itihasa_purana_text branch above which
        // already prefers chapter.reference over a raw id.
        vedicId: item.reference || item.id || '',
        // The item's raw id too (DV_6001, AV_C01_S01_I01, ...): deep links
        // built from data-side indexes (prayoga index, backlinks) address
        // units by this id, while vedicId above is the human-facing
        // reference string when one exists.
        unitId: item.id || '',
        // Traditional Ashtaka.Adhyaya.Varga.Rik reference — present only for
        // Rigveda Samhita data so far (see ashtaka_ref in the source data.json).
        ashtakaId: item.ashtaka_ref || '',
        rishi: item.rishi || '',
        devata: item.devata || '',
        chandas: item.chandas || '',
        padapatha: dgeSanitizeVedicAccents(item.pada_patha || ''),
        commentaries: commentaries,
        geminiEnrichment: item.gemini_enrichment || null,
        // Structural path (grantha > layer > adhyaya > pada > adhikarana >
        // topic > unit) captured per item by the DvaitaVedanta importer —
        // the section navigator (layer-stitch.js's dgeInitSectionNav)
        // groups on it. Absent everywhere else, and harmlessly null then.
        breadcrumb: Array.isArray(item.breadcrumb) ? item.breadcrumb : null,
        // Kṣetra / deity heading a verse falls under (Tīrthaprabandha:
        // "गङ्गा", "श्रीरङ्गम्", …). Drives the section navigator's
        // dropdown-and-filter; empty for texts that group by breadcrumb
        // structure alone. See layer-stitch.js dgeInitSectionNav.
        category: typeof item.category === 'string' ? item.category : '',
        // Sanitized source-site markup for this unit (DvaitaVedanta
        // importer, 1 Sep 2026): class="shloka" headers, lang="HI" spans,
        // h3 layer banners — render.js offers a styled "source view" per
        // card where this exists. Empty string everywhere else.
        sourceHtml: typeof item.source_html === 'string' ? item.source_html : '',
        // Optional outbound link to a related project page (Tīrthaprabandha
        // verses → the Tīrtha holy-places page, filtered to the kṣetra).
        // Empty for every other grantha; render.js shows a 📍 chip when set.
        tirthaLink: typeof item.tirtha_link === 'string' ? item.tirtha_link : '',
        // null for every grantha but Bhāgavata Sāroddhāra; render.js shows a 🔗 chip when set.
        bhagavataLink: dgeBuildBhagavataRefLink(item.bhagavata_ref, item.references)
      };
    });

    // Data-shape diagnostics — makes import problems visible in the dev
    // log instead of just silently rendering nothing. Especially useful
    // when a data file looks fine on GitHub but something upstream (a
    // stale cached copy, a schema mismatch, an import that didn't
    // actually include a field) means the app sees something different.
    console.log(`[Data] Normalized "${granthaTitle || 'untitled'}": ${data.items.length} item(s), ` +
      `${itemsWithCommentaries} with commentaries, ` +
      `commentary keys found: ${JSON.stringify(Object.keys(availableCommentaries))}`);
    if (data.items.length && !itemsWithCommentaries) {
      console.warn('[Data] No commentaries found on ANY item — if commentaries were expected, ' +
        'check that the uploaded data.json actually contains a "commentaries" object per item ' +
        '(not an empty array), and that you are not seeing a cached older copy of the file.');
    }

    return {
      metadata: {
        title: granthaTitle || data.schema || 'Untitled',
        author: data.default_author || '',
        totalShlokas: data.items.length,
        availableCommentaries: availableCommentaries
      },
      shlokas,
      totalShlokas: data.items.length
    };
  }

  return data; // unrecognized shape -- nothing safe to adapt, let it fail downstream with a clearer error than before at least
}

document.addEventListener('DOMContentLoaded', () => {
  // 1. INITIALIZE GLOBAL DOM ELEMENTS
  window.els = {
    playBtn: document.getElementById('playBtn'),
    speedInput: document.getElementById('speedInput'),
    speedVal: document.getElementById('speedVal'),
    trackLabel: document.getElementById('trackLabel'),
    timeDisplay: document.getElementById('timeDisplay'),
    repeatCounter: document.getElementById('repeatCounter'),
    filterBtn: document.getElementById('filterBtn'),
    searchInput: document.getElementById('searchInput'),
    clearSearchBtn: document.getElementById('clearSearchBtn'),
    repeatInput: document.getElementById('repeatInput'),
    cacheBtn: document.getElementById('cacheBtn'),
    listEl: document.getElementById('shlokaList'),
    loopA: document.getElementById('loopA'),
    loopB: document.getElementById('loopB'),
    enableAB: document.getElementById('enableAB'),
    autoABToggle: document.getElementById('autoABToggle'),
    searchScope: document.getElementById('searchScopeBtn'),
    navContainer: document.getElementById('searchNavigator')
  };

  // 2. PARSE URL PARAMETERS
  const urlParams = new URLSearchParams(window.location.search);

  // Global short-URL abbreviations (js/text-abbreviations.js, loaded before
  // this file, is the one place these are configured) — ?SMV=1.1 means the
  // same as ?path=DvaitaVedanta/Itara/Kavya/sumadhva_vijaya/sarga_1&jumpShloka=1, just
  // short enough to type or share. Resolved to plain path/jumpShloka values
  // BEFORE those are read below, so everything downstream — including the
  // legacy-slug upgrade and the namespace logic — behaves exactly as if the
  // reader had typed the long form themselves.
  let abbrevPath = null, abbrevShloka = null, abbrevVedicId = null;
  // 7 Sep 2026: the one-token short URL — ?rv1.1.3, ?smv1.5, ?bhp10.14.8 (js/shortcuts.js is the grammar; the
  // landing page forwards such a query here). Resolved to path + jump exactly like the long form below, and the
  // short form is kept in the address bar (history.replaceState) so the URL people copy stays short.
  const dgeShortcut = (window.DGEShortcuts && window.DGEShortcuts.fromSearch) ? window.DGEShortcuts.fromSearch(window.location.search) : null;
  if (dgeShortcut) {
    abbrevPath = dgeShortcut.granthaPath;
    if (dgeShortcut.vedicId) abbrevVedicId = dgeShortcut.vedicId;
    else if (dgeShortcut.shlokaNumber) abbrevShloka = String(dgeShortcut.shlokaNumber);
    try { history.replaceState(null, '', window.location.pathname + '?' + dgeShortcut.shortcut + window.location.hash); } catch (e) { /* ignore */ }
  }
  const DGE_ABBR = window.DGE_TEXT_ABBREVIATIONS || {};
  for (const key of Object.keys(DGE_ABBR)) {
    if (!urlParams.has(key)) continue;
    const raw = urlParams.get(key) || '';
    const cfg = DGE_ABBR[key];
    if (cfg.path.indexOf('{ch}') !== -1) {
      const parts = raw.split('.');
      if (parts[0]) { abbrevPath = cfg.path.replace('{ch}', parts[0]); if (parts[1]) abbrevShloka = parts[1]; }
    } else {
      abbrevPath = cfg.path;
      if (raw) abbrevShloka = raw;
    }
    break; // first matching abbreviation wins — a URL isn't expected to carry two
  }

  const explicitPath = urlParams.get('path') || abbrevPath; // new general addressing, e.g. "vedas/rigveda/mandala_01"
  const explicitCode = urlParams.get('code'); // legacy addressing — always resolves under stotras/, unchanged behaviour

  // Quick Search jump target (see dgeQuickJump in library.js) — resolved
  // against this grantha's actual shlokas object once it's loaded and
  // normalized, at the end of initApp() below.
  const jumpVedicId = urlParams.get('jumpVedicId') || abbrevVedicId;
  const jumpShloka = urlParams.get('jumpShloka') || abbrevShloka;
  window._dgeJumpTarget = jumpVedicId ? { vedicId: jumpVedicId } : (jumpShloka ? { shlokaNumber: parseInt(jumpShloka, 10) } : null);

  // ?hl= — the word/phrase a reader just searched for (global-search.js's
  // go(), and library.js's own quick-jump), in Devanagari. Reported live:
  // arriving from a search result never showed WHERE the searched word
  // actually was on the landing page. dgeHighlightQueryOnLoad() (below,
  // run once content is rendered) does that highlighting; kept as a
  // separate global rather than folded into _dgeJumpTarget since a plain
  // in-grantha search (no shloka jump at all) can still carry one.
  window._dgeHighlightQuery = urlParams.get('hl') || null;

  const providedPass = urlParams.get('pass');
  const passkey = (window.appConfig && window.appConfig.secretPasskey) ? window.appConfig.secretPasskey : 'SHRI108';

  if (providedPass && providedPass.toUpperCase() === passkey.toUpperCase()) {
    localStorage.setItem('acharyaAuthorized', 'true');
  }

  // 3. RESOLVE WHICH GRANTHA TO LOAD
  // Any single-level "stotra/<code>" address — whether reached via the
  // legacy ?code=<code> param, no params at all (defaults to pns), OR the
  // newer ?path=stotra/<code> form — has ALWAYS used just <code> as its
  // storage/cache namespace; that convention predates the library catalog
  // entirely. This must hold regardless of how the page was reached: the
  // Library browser itself links to PNS via ?path=stotra/pns, and if
  // that used a different namespace it would silently orphan existing
  // users' marks/notes/audio-cache under a key they'd never see again —
  // not actual data loss (nothing is deleted), but functionally
  // indistinguishable from it. Only deeper category paths (vedas/...,
  // purana/..., darshana/..., etc.) use the full slug as the
  // namespace, since collision risk there is real (many granthas share a
  // generic last folder segment like "mula").
  // The Kavya corpus is 50 MB and lives on the kavya-dist branch, not in the
  // site, so a grantha under kavya_alankara/ is fetched from the CDN the Kavya
  // reader already uses. Everything else is read from beside the app as before.
  // Without this, a corpus-search hit on a kavya verse would open a reader that
  // asks for a file the site does not have.
  function dgeGranthaFetchUrl(s) {
    if (/^kavya_alankara\//.test(s) && window.KAVYA_DATA_BASE) {
      return `${String(window.KAVYA_DATA_BASE).replace(/\/+$/, '')}/${s}/data.json`;
    }
    return `data/${s}/data.json`;
  }

  // Single named default rather than a bare 'pns' literal repeated at every
  // call site -- the one thing every no-param page load actually needs a
  // hardcoded answer for, kept in exactly one place.
  const DGE_DEFAULT_STOTRA_SLUG = 'PrahladaKrutaNarasimha';

  const slug = dgeUpgradeLegacySlug(explicitPath
    ? explicitPath.replace(/^\/+|\/+$/g, '')
    : `stotra/${explicitCode || DGE_DEFAULT_STOTRA_SLUG}`);
  window.dgeCurrentSlug = slug;
  if (typeof window.dgeApplySeoCanonical === 'function') window.dgeApplySeoCanonical(slug);

  const stotrasDirectChild = slug.match(/^stotra\/([^/]+)$/);

  // 23 Aug 2026: stotra/pns was renamed DvaitaVedanta/Itara/Stotra/prahlada_kruta_narasimha for
  // display-name consistency (see DGE_LEGACY_SLUGS above), but this text's
  // localStorage/audio-cache namespace has always been the bare folder
  // name (see the comment at dgeGranthaFetchUrl above this block). Without
  // this map, every existing reader's saved progress/notes/bookmarks/audio
  // cache on this stotra would silently stop being found -- not deleted,
  // just orphaned under a key the app no longer looks at. Add an entry
  // here, not a rename in state.js, whenever a grantha's slug changes.
  const STOTRA_CODE_CONTINUITY = { PrahladaKrutaNarasimha: 'pns' };

  const rawStotraCode = stotrasDirectChild ? stotrasDirectChild[1] : slug.replace(/\//g, '__');
  window.stotraCode = STOTRA_CODE_CONTINUITY[rawStotraCode] || rawStotraCode;
  window.currentGranthaSlug = slug;
  window.jsonFileName = dgeGranthaFetchUrl(slug); // overwritten below if the catalog has a more specific real path
  window.AUDIO_CACHE_NAME = `narasimha-audio-${window.stotraCode}`;

  // 4. RESOLVE VIA THE LIBRARY CATALOG, THEN FETCH THE GRANTHA DATASET
  // Wait on the config overrides too, so any customised text is already
  // in place before the first render rather than racing it.
  Promise.all([window.dgeLibraryCatalogPromise, window.dgeConfigOverridesPromise])
    .then(([library]) => {
    let entry = null;
    if (library && Array.isArray(library.granthas)) {
      entry = library.granthas.find(g => window.dgeGranthaSlug(g.path) === slug);
    }
    if (entry) {
      window.jsonFileName = window.dgeLibraryPathToFetchPath(entry.path);
    }

    if (entry && entry.populated === false) {
      const titleEl = document.getElementById('stotraTitle');
      const cardEl = document.getElementById('shlokaList');
      if (titleEl) titleEl.innerText = 'Not Yet Available';
      if (cardEl) cardEl.innerText = "This text hasn't been added to the library yet — check back soon.";
      // Still say WHERE this empty slot sits. Landing on a bare "Not Yet
      // Available" with no lineage leaves a reader who followed a search hit
      // with nothing to orient by and no way back into the taxonomy.
      if (typeof window.dgeRenderStitchChrome === 'function') window.dgeRenderStitchChrome();
      return;
    }

    // Admin-only content (entry.hidden, see the 23 Aug 2026 restructure --
    // e.g. darshana/vedanta/dvaita/DvaitaVedantaIn/*) reached by a direct
    // ?path= link rather than the nav, which already excludes it. Refuses
    // to fetch/render for anyone not signed in as admin. Not real access
    // control -- the underlying data.json is still a public static file on
    // GitHub Pages, same caveat as admin-gate.js -- but the app itself
    // won't show it.
    if (entry && entry.hidden) {
      const isAdmin = localStorage.getItem('acharyaAuthorized') === 'true' ||
                       localStorage.getItem('is_superadmin') === 'true';
      if (!isAdmin) {
        const titleEl = document.getElementById('stotraTitle');
        const cardEl = document.getElementById('shlokaList');
        if (titleEl) titleEl.innerText = 'Restricted';
        if (cardEl) cardEl.innerText = 'This section is not available.';
        return;
      }
    }

    // The go-live shelf, on a DIRECT link. dgeIsHiddenPath keeps an
    // off-shelf grantha out of the drawer and global-search keeps it out of
    // results, but neither covers a bookmark, an old share link or a search
    // engine's cached URL -- and a launch where "hidden" means "hidden
    // unless you already have the link" is not the thing that was asked
    // for. Same honest caveat as every other gate in this app: the
    // data.json is a public static file, so this stops the SITE showing it,
    // not the file existing. The shelf is written in display paths, so the
    // catalog entry's own display path is what gets judged -- and an admin
    // (not previewing) passes, exactly as everywhere else.
    if (typeof window.dgeIsOffShelf === 'function' && entry) {
      const shelfPath = (typeof window.dgeEffectiveDisplayPath === 'function')
        ? window.dgeEffectiveDisplayPath(slug) : slug;
      if (window.dgeIsOffShelf(shelfPath)) {
        const titleEl = document.getElementById('stotraTitle');
        const cardEl = document.getElementById('shlokaList');
        if (titleEl) titleEl.innerText = 'Not Available Yet';
        if (cardEl) cardEl.innerText = 'This text is not part of the published library yet.';
        if (typeof window.dgeRenderStitchChrome === 'function') window.dgeRenderStitchChrome();
        return;
      }
    }

    function fetchGranthaData(attempt) {
      // The timestamp query param alone already guarantees a fresh fetch
      // (it's a URL the browser has never cached) — cache:'no-store' on
      // top of that is stricter still and, for large files like a full
      // Rigveda maṇḍala (2MB+) on a mobile connection, gives zero
      // tolerance for an ordinary transient network hiccup. One retry
      // covers exactly that case without needing to know the real cause.
      // Through corpus-fetch.js, which is the corpusBase switch: unset, it
      // is the same static fetch with the same cache-buster this line always
      // did; set, it is a token-authenticated read from the corpusFile
      // proxy. The fallback keeps a page that forgot to load the module
      // working exactly as before rather than failing to open a grantha.
      const corpusFetch = (typeof window.dgeFetchCorpus === 'function')
        ? window.dgeFetchCorpus(window.jsonFileName)
        : fetch(window.jsonFileName + '?t=' + Date.now());
      return Promise.resolve(corpusFetch)
        .then(res => {
          if (!res.ok) throw new Error(`Could not find dataset at ${window.jsonFileName} (HTTP ${res.status})`);
          return res.json();
        })
        .catch(err => {
          if (attempt < 1) {
            console.warn(`Grantha fetch failed, retrying once: ${err.message}`);
            return fetchGranthaData(attempt + 1);
          }
          throw err;
        });
    }

    fetchGranthaData(0)
      .then(async data => {
        // Logged BEFORE normalization so the raw file shape is visible —
        // if this doesn't match what you just uploaded, the problem is
        // the fetch (stale cache, wrong path), not the rendering.
        console.log(`[Data] Fetched ${window.jsonFileName} — top-level keys: ${JSON.stringify(Object.keys(data || {}))}`);
        if (data && Array.isArray(data.items) && data.items.length) {
          const first = data.items[0];
          console.log(`[Data] First item keys: ${JSON.stringify(Object.keys(first))}, ` +
            `commentaries type: ${Array.isArray(first.commentaries) ? 'ARRAY (empty placeholder — not readable as commentaries)' : typeof first.commentaries}`);
        }
        // Only the plain {metadata, shlokas:{n:{...}}} shape round-trips
        // losslessly back to its own file on disk — anything that needed
        // dgeNormalizeGranthaData to flatten it (itihasa_purana_text's
        // per-chapter nesting, vedic_text's items array) can't be saved
        // back through content-editor.js without real denormalization
        // logic that doesn't exist yet. Recorded before normalization
        // overwrites `data`, so the editor can gate on it honestly.
        window.stotraDataEditable = !!(data && data.shlokas);
        // A layer-folder catalog title reads "ऋग्भाष्यम् — mula"; the reader
        // header should carry the work's name. Only the mula suffix is
        // stripped — a tika layer opened standalone keeps its explicit
        // "<grantha> — tika_<name>" title, which is the honest label there.
        window.stotraData = dgeNormalizeGranthaData(data,
          entry ? String(entry.title || '').replace(/\s*—\s*mula$/, '') : null);
        // Sibling-layer stitching (layer-stitch.js, see
        // MULTI_LAYER_READER_ARCHITECTURE.md): must run BEFORE
        // initApp() so the commentary picker chrome is built from the
        // already-extended availableCommentaries. Awaited because it may
        // need the layer manifest fetch to resolve; a grantha with no
        // manifest entry returns immediately.
        if (typeof dgeApplyLayerStitching === 'function') {
          await dgeApplyLayerStitching(slug);
        }
        initApp();
        // Cross-page taxonomy-breadcrumb deep link (?libraryPath=<path>,
        // see library.js's dgeOpenLibraryToPath): opens the Library browser
        // already drilled to that node. Independent of whatever grantha
        // ?path=/the no-param default resolved above -- the reader
        // underneath loads exactly as it would if the reader had opened the
        // Library manually while already reading something.
        if (urlParams.get('libraryPath') && typeof window.dgeOpenLibraryToPath === 'function') {
          window.dgeOpenLibraryToPath(urlParams.get('libraryPath'));
        }
        // The stitcher may have auto-selected the grantha's primary layer
        // (भाष्यम्/सुधा — see layer-stitch.js) so the page opens with real
        // text; the fetch+merge+re-render for it starts here, after the
        // first (spine-only) render is already on screen.
        if (typeof dgeEnsureStitchedLayers === 'function') dgeEnsureStitchedLayers();
        // Must run AFTER initApp() (which sets the is-authorized class
        // used to gate the content editor) but re-renders if it actually
        // restores a draft, since initApp() already rendered once with
        // the unedited data.
        if (typeof dgeRestoreContentDraftIfAny === 'function' && dgeRestoreContentDraftIfAny()) {
          if (typeof renderList === 'function') renderList();
        }
        // 7 Sep 2026: dhātu occurrences for this grantha (tools/build_dhatu_prayoga_index.py,
        // by_grantha/<slug>.json) — verse cards show the attested dhātu forms as
        // chips linking to prakriya.html; the dhātu pages link back here. One
        // small fetch per grantha; absent = no chips.
        try {
          const slugForHits = window.dgeGranthaSlug(window.jsonFileName.startsWith('') ? window.jsonFileName : '' + window.jsonFileName);
          fetch('data/vedanga/vyakarana/dhatu_prayoga/by_grantha/' + slugForHits.replace(/\//g, '__') + '.json', { cache: 'force-cache' })
            .then(r => (r.ok ? r.json() : null)).then(h => { window.dgeDhatuHits = h || null; if (h && typeof renderList === 'function') renderList(); })
            .catch(() => { window.dgeDhatuHits = null; });
        } catch (e) { window.dgeDhatuHits = null; }
        // पदच्छेदः for this grantha (tools/build_padaccheda.py,
        // _padaccheda/<slug>.json): which written tokens are two or more words
        // joined by sandhi, and what they are. One small fetch per grantha;
        // absent = the verse simply has no पदच्छेदः chip.
        try {
          const pcSlug = window.dgeGranthaSlug(window.jsonFileName.startsWith('') ? window.jsonFileName : '' + window.jsonFileName);
          fetch('data/_padaccheda/' + pcSlug.replace(/\//g, '__') + '.json', { cache: 'force-cache' })
            .then(r => (r.ok ? r.json() : null))
            .then(d => { window.dgePadaccheda = d || null; if (d && typeof renderList === 'function') renderList(); })
            .catch(() => { window.dgePadaccheda = null; });
        } catch (e) { window.dgePadaccheda = null; }
        // सन्दर्भाः for this grantha (tools/build_references.py,
        // _references/<slug>.json): where a commentary is CITING a धातु, a
        // कोश or a सूत्र, decided from context at build time and validated
        // against the authoritative list. One small fetch per grantha;
        // absent = the commentary simply carries no citation marks. This is
        // what replaced the old generic word marking, which coloured any word
        // present in a database whether or not it was a reference.
        try {
          const refSlug = window.dgeGranthaSlug(window.jsonFileName.startsWith('') ? window.jsonFileName : '' + window.jsonFileName);
          fetch('data/_references/' + refSlug.replace(/\//g, '__') + '.json', { cache: 'force-cache' })
            .then(r => (r.ok ? r.json() : null))
            .then(d => { window.dgeReferences = d || null; if (d && typeof renderList === 'function') renderList(); })
            .catch(() => { window.dgeReferences = null; });
        } catch (e) { window.dgeReferences = null; }
        // सन्धिच्छेदः inside the commentary (tools/build_padaccheda.py
        // --commentary, _commentary_sandhi/<slug>.json): which written
        // commentary tokens are two words joined by sandhi. Built per grantha
        // on request rather than corpus-wide; absent = no marks.
        try {
          const csSlug = window.dgeGranthaSlug(window.jsonFileName.startsWith('') ? window.jsonFileName : '' + window.jsonFileName);
          fetch('data/_commentary_sandhi/' + csSlug.replace(/\//g, '__') + '.json', { cache: 'force-cache' })
            .then(r => (r.ok ? r.json() : null))
            .then(d => { window.dgeCommentarySandhi = d || null; if (d && typeof renderList === 'function') renderList(); })
            .catch(() => { window.dgeCommentarySandhi = null; });
        } catch (e) { window.dgeCommentarySandhi = null; }
        if (typeof dgeMountContentEditorControls === 'function') dgeMountContentEditorControls();
      })
      .catch(err => {
        console.error("DGE Fetch Error:", err);
        const titleEl = document.getElementById('stotraTitle');
        const cardEl = document.getElementById('shlokaList');
        if (titleEl) titleEl.innerText = "Data Not Found";
        if (cardEl) cardEl.innerText = `Error: Please ensure ${window.jsonFileName} is available in the repository.`;
      });
  });
});

// Commentary/bhashya display is opt-in and hidden by default
// (selectedCommentaries starts empty, see state.js) -- a reader who
// never notices the small 💬 "Commentary Options" icon in the top bar can
// read an entire Stotra or Veda text and never discover real bhashya
// content sits right there for it.
//
// This used to be a one-shot toast. The lead's verdict on it (9 Sep 2026):
// it "disappears too quickly and should point to the exact place to click".
// A message that is gone before it is read, pointing at an icon rather than
// at something tappable, is worse than none -- so the standing bar above the
// verses (render.js dgeRenderCommentaryBar) carries the signal instead, and
// carries the switches with it. This is now only the first-visit nudge that
// draws the eye to that bar, and it is still gated per grantha via nsKey so
// it never nags on a text the reader has already been shown it for.
function dgeNoticeCommentaryAvailable() {
  const available = window.stotraData && window.stotraData.metadata && window.stotraData.metadata.availableCommentaries;
  if (!available || !Object.keys(available).length) return;
  const seenKey = (typeof nsKey === 'function') ? nsKey('commentaryNoticeSeen') : null;
  if (!seenKey || localStorage.getItem(seenKey) === 'true') return;
  localStorage.setItem(seenKey, 'true');
  const bar = document.getElementById('commentaryAvailableBar');
  if (!bar) return;
  bar.classList.add('dge-cbar-nudge');
  setTimeout(() => bar.classList.remove('dge-cbar-nudge'), 6000);
}

function initApp() {
  window.dgeListPage = 0; // fresh grantha starts list-mode pagination (see render.js) on its own page 1
  if (typeof loadPersistedState === 'function') loadPersistedState();
  if (typeof restorePrefs === 'function') restorePrefs();
  if (typeof initAuthAndBranding === 'function') initAuthAndBranding();
  if (typeof applyFeatureFlags === 'function') applyFeatureFlags();

  window.renderStotraChrome();
  if (typeof window.dgeInitChapterNav === 'function') window.dgeInitChapterNav();

  const cacheBtn = document.getElementById('cacheBtn');
  const cacheKey = window.nsKey ? window.nsKey('allCached') : `narasimha_allCached_${window.stotraCode}`;
  if (cacheBtn && localStorage.getItem(cacheKey) === 'true') {
    cacheBtn.innerText = `✅ All Cached`;
    cacheBtn.dataset.cached = "true";
    cacheBtn.style.background = "#e8f5e9"; 
    cacheBtn.style.color = "#2e7d32"; 
    cacheBtn.style.borderColor = "#c8e6c9";
  }

  // Pass control to the rendering pipeline
  if (typeof renderList === 'function') renderList();

  dgeNoticeCommentaryAvailable();

  if (typeof dgeRestoreLastVerse === 'function') dgeRestoreLastVerse();

  // A Quick Search jump (see dgeQuickJump in library.js) takes priority
  // over restoring the last-viewed verse above — the user explicitly
  // asked to go somewhere specific, so that intent wins.
  const hadJumpTarget = !!window._dgeJumpTarget;
  if (window._dgeJumpTarget) dgeResolveQuickJumpTarget(window._dgeJumpTarget);
  window._dgeJumpTarget = null;

  if (window._dgeHighlightQuery) dgeHighlightQueryOnLoad(window._dgeHighlightQuery, 0, hadJumpTarget);
}

// Reported live: a reader who opened a search result (global-search.js's
// go(), now passing ?hl=) or a Quick Search word match landed on the right
// PAGE but the word they searched for was "not highlighted anywhere" --
// nothing on screen actually confirmed the match was real or showed where
// it was. Marks every .dge-word span whose own text contains the query (or,
// for a multi-word phrase, any one of its words -- matching
// global-search.js's own highlightSnippet() substring rule, since a
// .dge-word span carries attached punctuation and dgeWrapWordsForTap()
// never strips it) with .dge-search-hit, then scrolls the first hit into
// view. jumpShloka (handled by dgeResolveQuickJumpTarget just above, if
// present) already scrolled to the right VERSE; this only needs to find
// the word within whatever is now on screen -- so it runs after that, and
// retries once, shortly, in case that jump is still mid-render (a chapter
// switch is not synchronous the way a same-chapter scroll is).
function dgeHighlightQueryOnLoad(query, attempt, hadJumpTarget) {
  attempt = attempt || 0;
  const words = String(query).trim().split(/\s+/).filter(w => w.length >= 2);
  if (!words.length) return;
  const spans = document.querySelectorAll('.dge-word');
  let hits = [];
  spans.forEach(span => {
    const txt = (span.textContent || '').normalize('NFC');
    if (words.some(w => txt.indexOf(w.normalize('NFC')) !== -1)) {
      span.classList.add('dge-search-hit');
      hits.push(span);
    }
  });
  if (!hits.length) {
    if (attempt < 3) setTimeout(() => dgeHighlightQueryOnLoad(query, attempt + 1, hadJumpTarget), 400);
    return;
  }
  // Only auto-scroll when nothing else already did (a jumpShloka target
  // scrolled to its own verse card already; jumping again to the word
  // within it would just fight that scroll for no benefit since the verse
  // is already on screen).
  if (!hadJumpTarget) {
    try { hits[0].scrollIntoView({ block: 'center', behavior: 'smooth' }); } catch (e) {}
  }
}
window.dgeHighlightQueryOnLoad = dgeHighlightQueryOnLoad;

// SEO canonical (7 Sep 2026, tools/seo): the interactive reader is one URL family (?path=…&jumpShloka=…, ?rv1.1.3)
// over content that also exists as static pages (/veda/rigveda/samhita/mandala-1/…). Once those pages are
// served (admin/config/seo.json canonicalLive), the reader points <link rel="canonical"> at the grantha's page so
// search engines index the crawlable copy and treat every reader URL as a view of it.
window.dgeApplySeoCanonical = async function (slug) {
  try {
    const cfg = await fetch('../admin/config/seo.json', { cache: 'no-store' }).then(r => r.ok ? r.json() : null).catch(() => null);
    if (!cfg || !cfg.canonicalLive) return;
    const map = await fetch('data/seo_urls.json').then(r => r.ok ? r.json() : null).catch(() => null);
    const hit = map && map.granthas && map.granthas[slug];
    if (!hit) return;
    let link = document.querySelector('link[rel="canonical"]');
    if (!link) { link = document.createElement('link'); link.rel = 'canonical'; document.head.appendChild(link); }
    link.href = (cfg.siteOrigin || '').replace(/\/$/, '') + (cfg.sitePrefix || '') + hit.url;
  } catch (e) { /* ignore */ }
};

// Keeps the address bar on the verse being read (7 Sep 2026, the lead: "share the current shloka, bookmark it,
// browser history"): the SHORT form when js/shortcuts.js has a key for this grantha (?rv1.1.3), otherwise
// ?path=…&jumpShloka=N. replaceState, so Back still leaves the text; a reload or a bookmark lands on the verse,
// and with it the list page that holds it (loadShloka turns to that page). Also what Share/Copy link use.
window.dgeCanonicalUrl = function (id) {
  const slug = window.dgeCurrentSlug;
  if (!slug || !window.stotraData || !window.stotraData.shlokas) return window.location.href;
  const sh = id ? window.stotraData.shlokas[id] : null;
  const base = window.location.pathname;
  if (window.DGEShortcuts && sh) return window.DGEShortcuts.canonical(base, slug, sh, id);
  const q = '?path=' + (/^[a-z0-9_\/]+$/i.test(slug) ? slug : encodeURIComponent(slug)) + (id ? '&jumpShloka=' + id : '');
  return base + q;
};
window.dgeSyncUrl = function (id) {
  try {
    const url = window.dgeCanonicalUrl(id);
    if (url && url !== window.location.pathname + window.location.search) history.replaceState(null, '', url + window.location.hash);
  } catch (e) { /* ignore */ }
};

// Turns a { vedicId } or { shlokaNumber } target into an actual internal
// shloka key and jumps there via loadShloka() — select, scroll, update the
// reading card, but never start audio (see the comment at the call).
function dgeResolveQuickJumpTarget(target) {
  if (!stotraData || !stotraData.shlokas) return;

  let targetId = null;
  if (target.shlokaNumber && stotraData.shlokas[target.shlokaNumber]) {
    targetId = target.shlokaNumber;
  } else if (target.vedicId) {
    // Reverse scan by normalized value (parseInt each dot-segment, then
    // rejoin) so "1.1.3" matches regardless of how either side pads its
    // numbers — real data has no padding today, but this doesn't assume
    // that stays true forever. Guarded to dotted-numeric strings only: a
    // chapter-based vedicId (itihasa/purana schemas set this to something
    // like "Skandha 10, Adhyaya 14 · 8", not a dotted number) has no digits
    // at its start, so blindly parseInt-ing it collapsed EVERY such shloka
    // to the same "NaN" key — every non-Vedic chapter-based grantha's
    // jumpVedicId target silently matched the first shloka in the array
    // instead of the one actually named. Non-numeric vedicIds now compare
    // as plain trimmed strings instead.
    const DOTTED_NUMERIC = /^[\d.]+$/;
    const normalize = s => {
      s = String(s).trim();
      return DOTTED_NUMERIC.test(s) ? s.split('.').map(p => parseInt(p, 10)).join('.') : s;
    };
    const wanted = normalize(target.vedicId);
    const keys = Object.keys(stotraData.shlokas);
    targetId = keys.find(k => {
      const vid = stotraData.shlokas[k].vedicId;
      return vid && normalize(vid) === wanted;
    });
    // A PARTIAL dotted id names a group, not a verse ("1.1" is Ṛgveda
    // sūkta 1.1; "3" is adhyāya 3): land on its first verse, i.e. the first
    // shloka whose id continues the prefix. (7 Sep 2026: "rv1.1" used to
    // resolve to nothing and leave the reader on its last-read verse.)
    if (!targetId && DOTTED_NUMERIC.test(wanted)) {
      targetId = keys.find(k => {
        const vid = stotraData.shlokas[k].vedicId;
        return vid && normalize(vid).indexOf(wanted + '.') === 0;
      });
    }
    // Data-side unit ids (DV_6001 ...) aren't dotted numbers and aren't the
    // display reference -- match them exactly against the id each shloka
    // now carries. For a nested grantha this lands on the chapter's first
    // shloka, which is the honest resolution of a chapter-level id.
    // "<unit id>#<n>" (7 Sep 2026, short URLs such as bhp10.14.8 → adhyaya_14#8) names the n-th verse INSIDE
    // that unit: the data indexes nested verses exactly this way (unitNo, see dgeNormalizeGranthaData).
    if (!targetId) {
      const hash = String(target.vedicId).indexOf('#');
      const unitWanted = hash >= 0 ? String(target.vedicId).slice(0, hash) : String(target.vedicId);
      const verseWanted = hash >= 0 ? String(target.vedicId).slice(hash + 1) : null;
      const inUnit = keys.filter(k => stotraData.shlokas[k].unitId === unitWanted);
      if (inUnit.length) {
        targetId = (verseWanted && inUnit.find(k => String(stotraData.shlokas[k].unitNo) === verseWanted))
          || (verseWanted && /^\d+$/.test(verseWanted) && inUnit[parseInt(verseWanted, 10) - 1])
          || inUnit[0];
      }
    }
  }

  // loadShloka, NOT playShloka (1 Sep 2026, project-lead report): arriving
  // at a verse — quick jump, a search result, a deep link — should select
  // and scroll to it, never start its audio. playShloka here made every
  // such arrival auto-play on desktop (mobile browsers block that autoplay,
  // which is why it read as a desktop-only bug). Audio starts only from an
  // explicit ▶.
  if (targetId && typeof loadShloka === 'function') {
    loadShloka(parseInt(targetId, 10));
  } else if (typeof showToast === 'function') {
    showToast('Could not find that verse in this text.');
  }
}

// Renders every piece of "chrome" (title, commentary list, search-scope
// options) that depends on the currently selected transliteration script.
// Called once on initial load, and again whenever the script changes, so
// the header title stays in sync instead of only updating on page refresh.
window.renderStotraChrome = function() {
  if (!(window.stotraData && window.stotraData.metadata)) return;

  const activeScript = window.activeScript || 'devanagari';
  const doTranslit = (text) => typeof applyTransliteration === 'function' ? applyTransliteration(text, activeScript) : text;

  const titleEl = document.getElementById('stotraTitle');
  if (titleEl) {
    titleEl.innerHTML = doTranslit(window.stotraData.metadata.title);
  }

  const rangeStart = document.getElementById('rangeStart');
  const rangeEnd = document.getElementById('rangeEnd');
  if (rangeStart) rangeStart.max = window.stotraData.metadata.totalShlokas || 43;
  if (rangeEnd) rangeEnd.max = window.stotraData.metadata.totalShlokas || 43;

  const dynamicList = document.getElementById('commentaryDynamicList');
  const searchScopeDynamicList = document.getElementById('searchScopeDynamicList');

  if (dynamicList && searchScopeDynamicList && window.stotraData.metadata.availableCommentaries) {
    dynamicList.innerHTML = '';
    searchScopeDynamicList.innerHTML = '';

    Object.entries(window.stotraData.metadata.availableCommentaries).forEach(([key, name]) => {
      const transName = doTranslit(name);
      // .filter-checkbox-item -- same ☐/☑ multi-select convention filter.js's
      // mark-criteria checkboxes already use, so any number can be checked
      // at once (see window.dgeToggleCommentarySelection in render.js).
      dynamicList.innerHTML += `<div class="filter-checkbox-item" data-ckey="${key}" onclick="window.dgeToggleCommentarySelection('${key}')">${transName}</div>`;
      searchScopeDynamicList.innerHTML += `<div class="pop-item" data-scope="${key}" onclick="window.setSearchScope('${key}', '${transName} Only', this)">${transName} Only</div>`;
    });
    // renderStotraChrome() re-runs on every script change (see its own doc
    // comment above), rebuilding this list from scratch -- resync the
    // checkmarks against the existing selection so switching script/theme
    // never silently drops what was already chosen.
    if (typeof dgeSyncCommentaryPopupState === 'function') dgeSyncCommentaryPopupState();
  }

  // Re-labels the Prev/Next Sarga/Chapter/Maṇḍala nav (library.js) in the
  // new script -- the prev/next slugs themselves don't change, only their
  // displayed labels, so this just re-renders rather than recomputing.
  if (typeof window.dgeRenderChapterNav === 'function') window.dgeRenderChapterNav();

  // Lineage strip / standalone-layer banner + section navigator labels
  // (layer-stitch.js) — same script-change re-render contract as the rest
  // of the chrome this function owns.
  if (typeof window.dgeRenderStitchChrome === 'function') window.dgeRenderStitchChrome();
  if (typeof window.dgeInitSectionNav === 'function') window.dgeInitSectionNav();
  // Async (it waits on the library catalogue) and deliberately not awaited:
  // the volume picker is navigation chrome, not part of the text.
  if (typeof window.dgeInitVolumeNav === 'function') window.dgeInitVolumeNav();
};

function initAuthAndBranding() {
  const isAuthorized = localStorage.getItem('acharyaAuthorized') === 'true';
  const isSuperadmin = localStorage.getItem('is_superadmin') === 'true';
  if (isAuthorized) document.body.classList.add('is-authorized');

  // The 🛡️ menu holds both plain-admin (AI keys) and super-admin (repo,
  // config, convert) entries, so it shows for either tier — the
  // super-admin-only items inside stay hidden until that gate passes.
  if (isAuthorized || isSuperadmin) {
    const at = document.getElementById('adminToolsBtn');
    if (at) at.style.display = 'flex';
  }

  // Visible feedback for which access tier (if any) is currently unlocked
  // on this device — previously the only sign was extra icons quietly
  // appearing elsewhere, with no indication in the Access menu itself of
  // what state you were already in.
  const keyBtn = document.getElementById('accessKeyBtn');
  const adminItem = document.getElementById('adminAccessItem');
  const superItem = document.getElementById('superAdminAccessItem');
  const logoutItem = document.getElementById('logoutAccessItem');
  if (keyBtn) keyBtn.innerHTML = (isAuthorized || isSuperadmin) ? '🔓 <span class="btn-top-label">Access</span>' : '🔑 <span class="btn-top-label">Access</span>';
  if (adminItem) {
    adminItem.innerHTML = isAuthorized ? '🔓 Admin Access <span style="margin-left:auto; font-size:10px; color:var(--accent-red); font-weight:800;">ACTIVE</span>' : '🔒 Admin Access';
    adminItem.classList.toggle('active', isAuthorized);
  }
  if (superItem) {
    superItem.innerHTML = isSuperadmin ? '🔓 Super Admin Access <span style="margin-left:auto; font-size:10px; color:var(--accent-red); font-weight:800;">ACTIVE</span>' : '🔒 Super Admin Access';
    superItem.classList.toggle('active', isSuperadmin);
  }

  // content-inline.js's "Edit Page Text" row in the Quick Actions rail --
  // same tier check as its own allowed() gate, kept in sync here since the
  // popup markup lives in this page's own HTML rather than being built by
  // content-inline.js itself.
  const ciEditItem = document.getElementById('ciEditPopItem');
  if (ciEditItem) ciEditItem.style.display = isSuperadmin ? 'flex' : 'none';
  if (logoutItem) logoutItem.style.display = (isAuthorized || isSuperadmin) ? 'flex' : 'none';

  // (7 Sep 2026: the "DESIGNED BY" credit line under the title is gone for
  // good, with its appConfig keys -- the project lead's ask.)

  const emailDisplay = document.getElementById('contactEmailDisplay');
  const contactEmail = (window.appConfig && window.appConfig.contactEmail) ? window.appConfig.contactEmail : 'sanatanavidyagurukulam@gmail.com';
  if(emailDisplay) emailDisplay.innerText = contactEmail;
  
  const emailLink = document.getElementById('configEmailLink');
  if(emailLink) {
      emailLink.href = `mailto:${contactEmail}`;
      emailLink.innerText = contactEmail;
  }

  const aboutEmailLink = document.getElementById('aboutContactEmail');
  if(aboutEmailLink) {
      aboutEmailLink.href = `mailto:${contactEmail}`;
      aboutEmailLink.innerText = contactEmail;
  }
}

function restorePrefs() {
  const savedTheme = localStorage.getItem('app_theme');
  if (savedTheme && typeof applyTheme === 'function') {
    applyTheme(savedTheme);
  } else if (typeof applyTheme === 'function') {
    // One-time migration: honor a previously saved plain dark-mode flag.
    applyTheme('vandana');   // the default; the legacy app_darkMode flag also landed on a dark theme
  }

  const savedFont = parseInt(localStorage.getItem('app_fontSize'), 10);
  if (!isNaN(savedFont) && typeof applyFontSize === 'function') applyFontSize(savedFont);

  const savedScript = localStorage.getItem('app_script');
  if (savedScript && typeof applyScript === 'function') applyScript(savedScript);

  // 7 Sep 2026: ?layout=app|scholar (the thin entry pages app.html and
  // reader.html carry it) presets and remembers the layout; otherwise
  // the saved preference applies. The layout itself stays one body class.
  const urlLayout = new URLSearchParams(window.location.search).get('layout');
  const savedLayoutMode = (urlLayout === 'app' || urlLayout === 'scholar') ? urlLayout : localStorage.getItem('app_layoutMode');
  if (savedLayoutMode && typeof window.dgeSetLayoutMode === 'function') window.dgeSetLayoutMode(savedLayoutMode);

  if (localStorage.getItem('app_wakeLock') === '1' && typeof window.dgeSetScreenWakeLock === 'function') window.dgeSetScreenWakeLock(true);

  const savedViewMode = localStorage.getItem('app_viewMode');
  // The list view is paged (render.js dgeListPageSize(), 25 cards a page by
  // default, adjustable from the page bar), so a 2000-mantra Ṛgveda maṇḍala
  // is as cheap to open as a 43-verse stotra and the reader's own saved
  // preference is honoured for every grantha. (Until 7 Sep 2026 anything over
  // 150 verses was forced into single view; the lead asked for the Vedas as
  // a paged list instead.)
  window.viewMode = savedViewMode === 'single' ? 'single' : 'list';
  // The Display sheet's "Reading View" accordion shows the active row in its
  // header; mark the effective mode so it never reads blank (7 Sep 2026).
  document.querySelectorAll('#displayPopup .pop-item[data-viewmode]').forEach(el => {
    el.classList.toggle('active', el.dataset.viewmode === window.viewMode);
  });
  if (window.viewMode === 'single') {
    const lastVerseKey = typeof nsKey === 'function' ? nsKey('lastVerse') : null;
    const savedLastVerse = lastVerseKey ? parseInt(localStorage.getItem(lastVerseKey), 10) : NaN;
    window.currentReadingId = !isNaN(savedLastVerse) ? savedLastVerse : 1;
  }
}
