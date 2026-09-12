// js/config.js
// Maps to F-012: Preferences & Global Configuration
window.DGE_VERSIONS = window.DGE_VERSIONS || {};
window.DGE_VERSIONS['config.js'] = 'v6.3 (SCRIPT_OPTIONS: added Hindi/Marathi -- Devanagari aliases, see transliteration.js -- plus real Bengali/Odia transliteration targets. On top of v6.2\'s dasa_pada_text SHLOKA_EXTRA_FIELDS)';

const appConfig = {
  appName: "Bhagavata Digital Library",
  // The Mahabharata Kannada translation + Madhvacharya's Tatparya Nirnaya
  // excerpts interleaved in it carry no license anywhere (extracted from a
  // Pejawar Matha Android app's asset bundle) -- see core.js's
  // dgeVisibleCommentaries for the full reasoning. Default false: readers
  // do not see this content until licensing is confirmed one way or
  // another. A super-admin can flip this in Settings if that confirmation
  // ever comes through, or to review the actual text while chasing it down.
  showCopyrightGatedCommentaries: false,
  contactEmail: "sanatanavidyagurukulam@gmail.com",
  sarvamoolaProjectText: "Support the Sarvamoola Digitisation & Educational Project",
  geminiModel: "gemini-3.6-flash",
  secretPasskey: "SHRI108",
  // Project-wide default audio host. Every grantha's data.json still
  // stores its OWN full archiveBaseUrl (e.g.
  // "https://archive.org/download/svg_3bu1_pns/") — that per-grantha
  // identifier/folder is real per-text data and stays in JSON. This
  // value is only the well-known HOST PREFIX shared by every one of
  // those URLs today. dgeApplyAudioBaseUrlOverride() (below) swaps just
  // that shared prefix for whatever's currently effective, so switching
  // audio hosting for the whole site never requires editing a single
  // grantha JSON file — see dgeGetEffectiveAudioBaseUrl.
  audioBaseUrl: "https://archive.org/download/",
  // Kamadhenu ZeroGPU Space for "Generate this verse" (dge/js/kamadhenu.js). Empty = feature off.
  // Deploy with tools/kamadhenu/space/build_space.sh, then set "https://sarvamulaorg-kamadhenu.hf.space" (HF user SarvamulaOrg).
  kamadhenuSpaceUrl: "https://sarvamulaorg-kamadhenu.hf.space",   // live since 6 Sep 2026, 7:35 pm IST (ZeroGPU, PRO account)
  // Full ~1.65M-headword, 63-dictionary Kosha corpus, built and published
  // to the "dist" branch of the separate Tribhuvanachar/bhumandala-kosha-data
  // repo (too large for this repo's 1GB budget). Served over jsDelivr's
  // GitHub CDN, which mirrors the branch with permissive CORS. kosha.js
  // only ever fetches manifest.json plus small per-bucket/per-entry shards
  // on demand (never the whole corpus at once), so pointing this at the
  // full remote build doesn't add any real page-load cost.
  // PINNED to the dist branch's commit SHA (same discipline as
  // searchIndexBase): the dist branch is force-pushed on every corpus
  // build, and jsDelivr caches branch files per-file for ~12h, so "@dist"
  // can serve a NEW manifest with STALE buckets on some edges — which
  // breaks search entirely for those users. A SHA ref is immutable and
  // always internally consistent. After each kosha-data build, update
  // this SHA (git ls-remote <data-repo> dist) and bump config.js's ?v=.
  koshaDataBase: "https://cdn.jsdelivr.net/gh/Tribhuvanachar/bhumandala-kosha-data@54072a8d40d4907df588d722b3796afe06ec2568/data/koshas",
  // The enriched render tree (koshas_r) that dge/kosha2.html displays —
  // built by the same Action from tools/kosha_enrich.py; same SHA.
  koshaRenderBase: "https://cdn.jsdelivr.net/gh/Tribhuvanachar/bhumandala-kosha-data@54072a8d40d4907df588d722b3796afe06ec2568/data/koshas_r",
  // The Sanskrit WordNet lookup tree that js/intellisense.js reads for the
  // अर्थः section of the word popover, built by tools/build_wordnet.py and
  // published to this repo's own "wordnet-dist" branch — data only, no
  // history in common with main. Same reasoning as the koshas above, one
  // size down: 24 MB is small enough not to need its own repository and far
  // too large for a published site with about 1% of the GitHub Pages 1 GB
  // limit left. GitHub Pages serves only main, so a branch is enough to keep
  // it off the site while jsDelivr still serves it. Set this to '' to read a
  // local build from dge/data/_wordnet/ instead.
  wordnetDataBase: "https://cdn.jsdelivr.net/gh/Tribhuvanachar/bhumandala@66c7895fa7b1f30150ebbf74ea67abc28909e550/_wordnet",
  // The Kavya corpus js/kavya.js reads -- 24 works, 49 layers, 67,169
  // entries, 50 MB -- on this repo's "kavya-dist" branch for the same
  // reason. kavya.html carries the same URL as its own default, since it
  // does not load this file.
  kavyaDataBase: "https://cdn.jsdelivr.net/gh/Tribhuvanachar/bhumandala@75ef2103bc07770ccb861497c32636d706c09fa4",
  // The corpus-search index js/dge-search.js reads -- 983 granthas, 104,870
  // units. Rebuilding it with the extract_text fix (the one that made
  // every shloka-based grantha index its verses rather than nothing) took the
  // published site from 966 MB to 1,013 MB against a 1 GB Pages ceiling, so
  // the index moved to the "search-dist" branch and the site came back to
  // about 685 MB. window.DGE_SEARCH_INDEX was already the override the search
  // client looks for. search_index/backlinks stays on main -- it is 0.1 MB.
  // NOTE: this is pinned to a commit, not to @search-dist, so jsDelivr cannot
  // serve a half-written index -- which means reindex.yml publishing a new one
  // changes nothing for readers until this line is bumped to that commit. If a
  // freshly merged grantha browses but does not search, this is why.
  // 21 Aug 2026: re-ran reindex.yml from this branch to combine the
  // one-file-per-trigram + section-partitioned postings rewrite with main's
  // independent boundary-trigram ranking fix and the snippet() length
  // increase -- 998 granthas, 105,138 units, 59,557 trigrams. Verified live
  // over this exact commit before pinning: राम/कृष्ण/धर्म all return correct
  // 0.97-confidence hits, and section-scoped queries (itihasa, darshana)
  // return only that section's granthas.
  // 9 Sep 2026: re-ran reindex.yml to pick up content merged since 21 Aug
  // (Bhagavata Saroddhara among it) -- 1232 granthas. Confirmed by fetching
  // this exact manifest.json that all 6 of its layers (mula 371 units,
  // parishishta, 3 commentaries, upodghata) are present and populated;
  // could not confirm a live in-app query in this session's sandbox
  // (cdn.jsdelivr.net fetches from the headless browser were dropped by the
  // dev proxy, curl to the same URL was fine) -- worth a quick real-browser
  // check next time this file is touched.
  searchIndexBase: "https://cdn.jsdelivr.net/gh/Tribhuvanachar/bhumandala@838335f8152654c37ee1c256c36b6ff6aab3927f",
  // THE CORPUS SWITCH. Empty (the default, and what is live today) means
  // the reader fetches dge/data/<path>/data.json as a public static file,
  // exactly as it always has. Set it to the corpusFile function's base URL
  //   https://asia-south1-sarvamula-org.cloudfunctions.net/corpusFile
  // and every grantha read instead goes through the authenticated proxy:
  // the caller's Firebase ID token is sent, the function resolves their
  // stored role, applies the same shelf and gates the reader applies, and
  // streams the file from a PRIVATE bucket. That is the difference between
  // "the site does not show this text" and "this text cannot be fetched".
  //
  // Flipping this one string is the whole migration, and flipping it back
  // is the whole rollback — but only once the corpus has actually been
  // uploaded (tools/migrate_corpus_to_gcs.py) and CORPUS_BUCKET is set on
  // the function. See dge/CORPUS_PROXY.md for the order of operations.
  corpusBase: "",
  // ONE-TAP PDF. Empty (the default) means the book builder's only route is
  // Prepare -> the browser's own print dialog -> Save as PDF: free, no
  // account needed, and the same rendering engine. Set it to the renderBook
  // function's URL
  //   https://asia-south1-sarvamula-org.cloudfunctions.net/renderBook
  // and a second button appears that returns the finished .pdf file instead.
  // That needs the Blaze plan (it runs a real headless browser) and the
  // `book` capability granted to the reader's role — see dge/CORPUS_PROXY.md.
  bookPdfUrl: "",
  version: "v4.25"
};
window.appConfig = appConfig; // THIS LINE WAS MISSING — every "window.appConfig.X" read
// throughout the app was always undefined without it, silently falling back to hardcoded
// defaults no matter what was actually set above. Not a caching issue; a real, longstanding
// bug that just happened not to be visible until a config value diverged from its fallback.

// kosha.js reads window.KOSHA_DATA_BASE synchronously the moment its own
// script tag runs, so this has to be set here (config.js loads first,
// no async fetch involved) rather than through the async
// data/config-overrides.json merge below -- that merge lands too late to
// affect a value kosha.js has already captured into a local var.
window.KOSHA_DATA_BASE = appConfig.koshaDataBase;

// intellisense.js carries the same URL as its own default, because it also
// runs on the four Vyakarana pages, and none of them load this file. This
// line is what lets the reader's copy be repointed from one place — at a
// dedicated data repo, say, if the WordNet ever grows the way the koshas did.
// PINNED TO A COMMIT, NOT A BRANCH, and that is deliberate. jsDelivr caches a
// @branch URL at the edge for 12 hours, so the first republish of the Kavya
// corpus left readers on the superseded build -- the one with GRETIL's
// romanised variant verses in it -- with nothing to show that anything had
// changed. A commit hash is immutable and served the moment it exists.
// Republishing therefore has a second step: bump the hash here and in
// js/kavya.js (and js/intellisense.js for the WordNet). Both publish
// workflows print the line to paste.
window.WORDNET_DATA_BASE = appConfig.wordnetDataBase;
window.KAVYA_DATA_BASE = appConfig.kavyaDataBase;
// Phase 7 of the mobile UI overhaul: a user-facing "Data source" override
// for the search index, the same idea as the pre-existing audio CDN
// override (see userAudioBaseUrlInput in ai.js), and one of the
// ashtadhyayi.com-inspired preferences the project lead asked to add.
// global-search.js reads window.DGE_SEARCH_INDEX exactly once, into a
// module-scope var, the moment its own script tag runs -- unlike the
// audio override (read fresh from localStorage at each actual use in
// audio.js), a saved override here has to already be in place before
// that capture happens. config.js runs first, so this is the one place
// it can be applied.
window.DGE_SEARCH_INDEX = (function () {
  try { return localStorage.getItem('search_index_base_override') || appConfig.searchIndexBase; }
  catch (e) { return appConfig.searchIndexBase; }
})();

// Globally configurable "Ask Acharya" query types. Edit this list to add,
// remove, rename, reorder, or temporarily disable (enabled:false) any of
// the buttons shown in the selection tooltip.
//
// `presets` are fixed-wording checkbox options (each has a stable `id` so
// per-device on/off overrides persist correctly even if labels change) —
// end users toggle these individually in ⚙️ Settings without being able
// to typo/break the wording. `customNotes` is a free-text box layered on
// top for anything not covered by the presets — editable, at the user's
// own risk, same as before.
// action: 'ask' calls window.askAcharya(event, id); 'bhashya' opens the
// Bhashya picker. style: 'row' groups buttons side-by-side; 'full' renders
// its own full-width button below a divider.
const ACHARYA_QUERY_TYPES = [
  {
    id: 'shloka', icon: '📜', label: 'Shloka', style: 'row', action: 'ask', enabled: true,
    presets: [
      { id: 'padachheda', label: 'Padachheda (word-by-word split)', default: true },
      { id: 'anvaya', label: 'Anvaya (prose word order)', default: true },
      { id: 'wordmeaning', label: 'Word Meaning', default: true },
      { id: 'bhavartha', label: "Bhavartha (overarching theme, per Sri Madhvacharya's Dvaita philosophy)", default: true },
      { id: 'chandas', label: 'Chandas / meter of this verse, if identifiable', default: true },
      { id: 'alankara', label: 'Alankara (figures of speech), if any are present', default: true },
      { id: 'citations', label: 'Citations & exact quotes for scriptural references (AI-generated — verify independently)', default: false }
    ],
    customNotes: ''
  },
  {
    id: 'grammar', icon: '⚙️', label: 'Word', style: 'row', action: 'ask', enabled: true,
    presets: [
      { id: 'wordmeaning', label: 'Word Meaning', default: true },
      { id: 'prakritipratyaya', label: 'Prakriti & Pratyaya', default: true },
      { id: 'dhatugana', label: 'Dhatu & Gana (if this is a verb form)', default: true },
      { id: 'vibhaktilinga', label: 'Vibhakti & Linga (if this is a noun form)', default: true },
      { id: 'sandhi', label: 'Sandhi split, if applicable', default: true },
      { id: 'samasa', label: 'Samasa Vigraha — Vigrahavakya & Samasta-pada if a compound', default: true }
    ],
    customNotes: ''
  },
  {
    id: 'bhashya', icon: '🔍', label: 'Bhashya', style: 'row', action: 'bhashya', enabled: true,
    // 'summary' | 'sentence' | 'word' — how deep the core breakdown goes
    depth: 'summary',
    presets: [
      { id: 'vyakarana', label: 'List grammatical (Vyakarana) aspects invoked, including relevant Ashtadhyayi sutras', default: true },
      { id: 'amarakosha_verse', label: 'Amarakosha deep-dive: the actual verse(s) for key terms, plus neighboring verses for context', default: false },
      { id: 'amarakosha_word', label: 'Word-by-word meaning for each word per Amarakosha', default: false },
      { id: 'parallels', label: 'Similar/parallel verses or expressions elsewhere (any author) — list them', default: true },
      { id: 'etymology_diff', label: 'Where commentators differ on etymology or interpretation, list the differences', default: true },
      { id: 'citations', label: 'Citations & exact quotes (AI-generated — verify independently)', default: true }
    ],
    customNotes: ''
  },
  {
    id: 'translate', icon: '✏️', label: 'Custom', style: 'full', action: 'ask', enabled: true,
    // No fixed presets — this is the open-ended slot. customNotes below IS
    // the entire instruction sent to Acharya for this button.
    presets: [],
    customNotes: 'Provide a natural translation into the selected language, plus a brief note on its philosophical significance per the Madhva Sampradaya (Dvaita philosophy).'
  }
];
window.ACHARYA_QUERY_TYPES = ACHARYA_QUERY_TYPES;

// Additional structured per-shloka fields, beyond the existing free-form
// commentaries — Padaccheda, Anvaya, etc. Purely additive and forward-
// looking: dataKey is what render.js looks for on each shloka object,
// either a plain top-level field (e.g. shloka.padaccheda) or a dotted
// path into a nested object (e.g. shloka.gemini_deep_analysis.bhavartha
// -- see dgeGetNestedField in render.js). If a given shloka's data
// doesn't have that field populated, that section simply doesn't render
// — nothing breaks for shlokas without this data yet. Toggle individual
// fields on/off in
// ⚙️ Settings → 🧩 Shloka Fields, or edit `enabled` here for the default.
// 23 Aug 2026: pratipadartha/tatparya/vyakarana/vrutta/alankara now point
// into gemini_deep_analysis (tools/gemini_deep_analysis.py's nested
// output -- a structured object, not a plain string per key like a
// commentary), not a flat shloka.<name> field. dataKey supports a dotted
// path (dgeGetNestedField in render.js resolves it); renderType tells
// render.js how to lay out that field's shape rather than assuming every
// field is a plain string:
//   'text'    a plain string (or an array of strings, joined)
//   'table'   an array of objects -- pratipadartha's word-by-word gloss
//   'list'    an array of objects rendered as a bulleted list -- alankara
//   'chandas' the {name, gana_structure, lakshana} object specifically
const SHLOKA_EXTRA_FIELDS = [
  { id: 'padaccheda', label: 'Padaccheda', icon: '🔤', dataKey: 'padaccheda', enabled: true },
  { id: 'anvaya', label: 'Anvaya', icon: '🔗', dataKey: 'anvaya', enabled: true },
  { id: 'pratipadartha', label: 'Pratipadartha', icon: '📖', dataKey: 'gemini_deep_analysis.pratipadartha', renderType: 'table', enabled: true },
  { id: 'tatparya', label: 'Tatparya', icon: '🎯', dataKey: 'gemini_deep_analysis.bhavartha', renderType: 'text', enabled: true },
  { id: 'vyakarana', label: 'Vyakarana', icon: '⚙️', dataKey: 'gemini_deep_analysis.vyakarana_vishesha', renderType: 'text', enabled: false },
  { id: 'vrutta', label: 'Vrutta (Meter)', icon: '🎼', dataKey: 'gemini_deep_analysis.chandas', renderType: 'chandas', enabled: true },
  { id: 'alankara', label: 'Alankara', icon: '✨', dataKey: 'gemini_deep_analysis.alankara', renderType: 'list', enabled: false },
  { id: 'samasa', label: 'Samasa Vishesha', icon: '🧩', dataKey: 'gemini_deep_analysis.samasa_vishesha', renderType: 'samasa', enabled: false },
  { id: 'crossReferences', label: 'Cross References', icon: '🔀', dataKey: 'crossReferences', enabled: true },
  // Vedic-content fields (see dgeNormalizeGranthaData in core.js, which is
  // what actually populates these dataKeys for vedic_text-schema granthas)
  { id: 'vedicId', label: 'Reference', icon: '📍', dataKey: 'vedicId', enabled: true },
  { id: 'rishi', label: 'Rishi', icon: '🧘', dataKey: 'rishi', enabled: true },
  { id: 'devata', label: 'Devata', icon: '🔥', dataKey: 'devata', enabled: true },
  { id: 'chandas', label: 'Chandas', icon: '🎵', dataKey: 'chandas', enabled: true },
  { id: 'padapatha', label: 'Padapatha', icon: '✂️', dataKey: 'padapatha', enabled: true },
  // dasa_pada_text fields (see dgeNormalizeGranthaData's dasa_pada_text
  // branch in core.js) -- kept separate from rishi/devata/chandas above
  // rather than reusing them, since those carry their own Vedic labels
  // ("Rishi", "Chandas" as meter) that would mislabel a Haridasa
  // composition's deity/raga/tala.
  { id: 'deity', label: 'Deity / Subject', icon: '🕉️', dataKey: 'deity', enabled: true },
  { id: 'raga', label: 'Raga', icon: '🎼', dataKey: 'raga', enabled: true },
  { id: 'tala', label: 'Tala', icon: '🥁', dataKey: 'tala', enabled: true }
];
window.SHLOKA_EXTRA_FIELDS = SHLOKA_EXTRA_FIELDS;

window.dgeGetEffectiveShlokaFields = function() {
  try {
    const override = JSON.parse(localStorage.getItem('shloka_extra_fields_override') || 'null');
    if (override && typeof override === 'object') {
      return SHLOKA_EXTRA_FIELDS.map(f => ({ ...f, enabled: override[f.id] !== undefined ? override[f.id] : f.enabled }));
    }
  } catch (e) { /* fall through to defaults */ }
  return SHLOKA_EXTRA_FIELDS;
};

// Share-as-Image templates (js/screenshot.js). Each safeZone is the
// approximate empty area (in the template's own native pixel dimensions)
// where shloka text can sit without colliding with the artwork — these
// are estimates from visual inspection, not pixel-measured, so nudge them
// if text still overlaps a border/motif on a given template.
// hasBakedBranding: true means "सनातन विद्या गुरुकुल · 3BU1" is already
// drawn into the image itself — the code must NOT draw its own footer
// text on top of these, or it'll double up.
// Share-as-Image templates (js/screenshot.js) are now discovered LIVE from
// the actual images/ folder on GitHub — nothing here is a hardcoded file
// list. Upload a new file named "template-whatever.png/.jpg" directly on
// GitHub and it appears in the picker automatically, no code change
// needed. This section only holds:
//   - where to look (repo location)
//   - explicit exclusions (files matching the pattern that should NOT
//     be offered — e.g. a reference/working file)
//   - optional fine-tuned overrides (safe zone, baked-branding flag) for
//     specific templates. Anything discovered that ISN'T listed here
//     still works, just with a generic centered safe zone by default.
const GITHUB_REPO_CONFIG = { owner: 'Tribhuvanachar', repo: 'bhumandala', branch: 'main', imagesPath: 'dge/images' };
window.GITHUB_REPO_CONFIG = GITHUB_REPO_CONFIG;

// New-file extensions offered in the admin editor's "+ New File" button —
// deliberately a curated list, not every possible extension.
const ADMIN_NEW_FILE_EXTENSIONS = ['.js', '.json', '.html', '.css', '.md', '.txt', '.svg'];
window.ADMIN_NEW_FILE_EXTENSIONS = ADMIN_NEW_FILE_EXTENSIONS;

// Admin access levels — each superadmin URL code is bound to a specific
// root path it can NEVER navigate above, even by tapping "Up" repeatedly.
// An empty rootPath means the actual repository root (bhumandala) — no
// restriction at all. Requested directly by the project lead, 11 Sep 2026:
// the admin file manager was defaulting to (and capping "Up" at) dge/,
// hiding the rest of the repo (tools/, admin/, kamadhenu_dataset/, etc.)
// from the one account that needs to reach all of it.
const ADMIN_ACCESS_LEVELS = {
  '2': { rootPath: '', label: 'Bhumandala Repo Admin' }
};
window.ADMIN_ACCESS_LEVELS = ADMIN_ACCESS_LEVELS;

const SHARE_TEMPLATE_EXCLUDE = ['_collage-uncropped-reference'];
window.SHARE_TEMPLATE_EXCLUDE = SHARE_TEMPLATE_EXCLUDE;

const SHARE_TEMPLATE_OVERRIDES = {
  'template-01-jade-meander': { label: 'Jade Meander Border', safeZone: { x: 110, y: 180, w: 560, h: 780 } },
  'template-02-lotus-watercolor': { label: 'Lotus Watercolor', safeZone: { x: 110, y: 260, w: 560, h: 600 } },
  'template-03-temple-arch-dark': { label: 'Dark Temple Arch', safeZone: { x: 190, y: 300, w: 400, h: 640 } },
  'template-04-lotus-medallion': { label: 'Lotus Medallion', safeZone: { x: 130, y: 220, w: 520, h: 750 } },
  'template-05-parchment-diya': { label: 'Parchment + Diya', safeZone: { x: 110, y: 110, w: 800, h: 650 }, hasBakedBranding: true },
  'template-06-minimal-gold': { label: 'Minimal Gold', safeZone: { x: 110, y: 240, w: 800, h: 560 }, hasBakedBranding: true },
  'template-07-geometric-mihrab': { label: 'Geometric Mihrab', safeZone: { x: 300, y: 300, w: 430, h: 470 }, hasBakedBranding: true },
  'template-08-watercolor-river': { label: 'Watercolor River', safeZone: { x: 160, y: 160, w: 700, h: 440 }, hasBakedBranding: true },
  'template-09-stone-inscription': { label: 'Stone Inscription', safeZone: { x: 130, y: 190, w: 780, h: 580 }, hasBakedBranding: true }
};
window.SHARE_TEMPLATE_OVERRIDES = SHARE_TEMPLATE_OVERRIDES;

const PLAIN_TEMPLATE = { id: 'plain', filename: null, label: 'Plain (no template)', safeZone: { x: 90, y: 260, w: 900, h: 560 }, hasBakedBranding: false };

function dgeLabelFromFilename(id) {
  return id.replace(/^template-\d+-/, '').replace(/[-_]/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

// Live-discovers templates via GitHub's public (unauthenticated, CORS-
// enabled) Contents API, caching the result for an hour so repeat visits
// don't hit GitHub's rate limit or slow the page down. Falls back to
// whatever was last successfully cached — or just "Plain" — if the API
// call fails (offline, rate-limited, etc.), so this never breaks sharing.
window.dgeDiscoverShareTemplates = async function(forceRefresh) {
  const CACHE_KEY = 'share_templates_cache_v2';
  const CACHE_TTL_MS = 60 * 60 * 1000;

  if (!forceRefresh) {
    try {
      const cached = JSON.parse(localStorage.getItem(CACHE_KEY) || 'null');
      if (cached && (Date.now() - cached.fetchedAt) < CACHE_TTL_MS && Array.isArray(cached.templates)) {
        return cached.templates;
      }
    } catch (e) { /* fall through to a live fetch */ }
  }

  const { owner, repo, branch, imagesPath } = GITHUB_REPO_CONFIG;
  const url = `https://api.github.com/repos/${owner}/${repo}/contents/${imagesPath}?ref=${branch}`;
  const excludeSet = new Set(SHARE_TEMPLATE_EXCLUDE);

  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error('GitHub API returned ' + res.status);
    const files = await res.json();

    const templates = [PLAIN_TEMPLATE];
    files
      .filter(f => f.type === 'file' && /^template.*\.(png|jpe?g)$/i.test(f.name))
      .forEach(f => {
        const id = f.name.replace(/\.(png|jpe?g)$/i, '');
        if (excludeSet.has(id)) return;
        const o = SHARE_TEMPLATE_OVERRIDES[id] || {};
        templates.push({
          id,
          filename: f.name,
          label: o.label || dgeLabelFromFilename(id),
          safeZone: o.safeZone || { x: 110, y: 220, w: 800, h: 600 },
          hasBakedBranding: !!o.hasBakedBranding
        });
      });

    localStorage.setItem(CACHE_KEY, JSON.stringify({ fetchedAt: Date.now(), templates }));
    return templates;
  } catch (e) {
    console.warn('Live template discovery failed, using last known list:', e);
    try {
      const cached = JSON.parse(localStorage.getItem(CACHE_KEY) || 'null');
      if (cached && Array.isArray(cached.templates) && cached.templates.length) return cached.templates;
    } catch (e2) { /* ignore */ }
    return [PLAIN_TEMPLATE];
  }
};

window.dgeGetSelectedShareTemplate = async function() {
  const id = localStorage.getItem('default_share_template') || 'plain';
  const templates = await window.dgeDiscoverShareTemplates();
  return templates.find(t => t.id === id) || templates[0] || PLAIN_TEMPLATE;
};

// Admin-only: whether Acharya may be instructed that it's allowed to
// include a plain external hyperlink when it's confident one exists (e.g.
// a well-known text repository). NOT exposed in the end-user Feature
// Visibility panel — AI-generated URLs can be hallucinated, so this is a
// deliberate admin call, made here in config.js only.
window.AI_ALLOW_EXTERNAL_LINKS = false;

// Sponsor / Ongoing Expenses — admin-configured only. Edit this directly
// in config.js (via GitHub, or the admin editor once built) to update
// amounts/categories — this is NOT an end-user setting. Purely
// informational for now (no payment processing exists yet — that needs
// auth + a backend, which is a later phase); each category links to a
// pre-filled contact email.
/* The Support and About panels' text — SPONSOR_CONFIG, CONTRIBUTORS_CONFIG and
   KEY_SPONSORS_CONFIG — now live in admin/content/reader.json, loaded by
   core.js before the first render and editable in place on the page. They are
   content rather than settings: a sentence about what the project spends
   should not need a code change, and a constant here could only be changed by
   one. Anything that reads window.SPONSOR_CONFIG still works; it is set from
   the file instead of from here. */

// What's New / Coming Soon — admin-configured only, same pattern as
// CONTRIBUTORS_CONFIG. "updates" are rendered newest-first by date
// (missing dates sink to the bottom, keeping their stored order among
// themselves); "coming soon" has no date concept at all, so its stored
// array order IS the display order — reorder those manually to reflect
// priority. Empty by default — nothing invented; add real entries as
// features actually ship or get planned.
/* What's New and Coming Soon now live in admin/content/whats-new.json, read
   by dge/js/modals.js each time the panel opens. Publishing an update should
   not need a code change, and a constant here could only be updated by one. */

// Multi-provider AI configuration. Each provider is only used if the person
// has saved a key for it (via the ⚙️ Settings). Model names are left
// user-editable rather than hardcoded, since exact current API model
// strings change over time and get out of date fast.
const AI_PROVIDERS = {
  gemini: { label: 'Gemini', defaultModel: appConfig.geminiModel },
  openai: { label: 'ChatGPT (OpenAI)', defaultModel: '' },
  claude: { label: 'Claude (Anthropic)', defaultModel: '' }
};
window.AI_PROVIDERS = AI_PROVIDERS;

// Globally configurable feature visibility. Controls which per-shloka
// indicators/controls and top-bar tools are shown. Can be overridden per
// device via ⚙️ → 🎛️ Feature Visibility (saved to localStorage), which
// layers on top of these shipped defaults the same way ACHARYA_QUERY_TYPES
// and AI_PROVIDERS overrides work.
const FEATURE_FLAGS = {
  showFavorite: true,
  showStatus: true,
  showDoubt: true,
  showNotes: true,
  showSnippetTools: true, // saved snippets + A-B repeat tools in 🛠 Tools
  showThemePicker: true,
  showScriptPicker: true,
  showPreloadButton: true, // "📥 Preload All Audio" button in 🛠 Tools
  showSpeedControl: true,  // playback speed slider in 🛠 Tools
  showDhatuChips: true,    // धातुरूपाणि chip row under a verse (render.js)
  // REVOKED 10 Sep 2026 by the project lead, and the reasoning is right: a
  // lexical match is not evidence of a reference. One Sanskrit surface form
  // can be a noun, a verb form, a kṛdanta, half of a sandhi join, and an
  // entry in a dictionary all at once — तन्त्राणि and भावः are ordinary words
  // that happen to sit in the dhātu data — so colouring every word that
  // appears in a list told a reader something that was not true.
  // The machinery stays (highlight-words.js is unchanged and still serves the
  // word tools' script conversion); only the automatic marking is off. What
  // replaces it is context-first detection: tools/reference_detect.py finds
  // the places a commentary is visibly CITING something, validates each
  // against the authoritative list, and reference-links.js marks only those
  // (flag showReferenceLinks below).
  showWordMarks: false,    // धातु/कोश background marks on words (highlight-words.js)
  // सन्दर्भाः — धातु/कोश/सूत्र citations in a commentary, detected from
  // context at build time (tools/build_references.py -> _references/<slug>.json)
  // and marked by reference-links.js. This is the flag the old lexical
  // marking should have been: turning it off leaves the text plain, turning it
  // on adds only claims that survived a citation frame AND a lookup in the
  // dhātupāṭha / sūtrapāṭha / kośa registry.
  showReferenceLinks: true,
  showPratikaLinks: true,  // प्रतीक links between a commentary and the verse (pratika.js)
  // सन्धिच्छेदः marks on commentary prose (commentary-sandhi.js +
  // _commentary_sandhi/<slug>.json). Built only for the granthas asked
  // for; a grantha with no file simply shows no marks.
  showCommentarySandhi: true,
  showPadaccheda: true     // पदच्छेदः chip on a verse (render.js + _padaccheda/)
};
window.FEATURE_FLAGS = FEATURE_FLAGS;

/* ---------------------------------------------------------------------------
   Word tools (the 🕉️ Genie row on a selection). One registry so the set can
   be configured instead of edited: the buttons used to be hand-written markup
   in index.html, which meant "hide Samasa" was a code change.

   `powered` is the load-bearing field:
     own      — this project's own precomputed data (Vidyut-derived, shipped
                in dge/data). Free to run, works offline, no third party.
     gemini   — a paid Gemini call on the project lead's prepaid credits.
                Hidden from ordinary readers; see dgeGetEffectiveWordActions.
     external — a live third-party service (dharmamitra.org). Off by default:
                it sends the reader's selection off-site.

   Precedence, matching every other configurable in this file: shipped default
   < global admin (appConfig.wordActions, via admin/config/config-overrides.json)
   < per-device (localStorage 'word_actions_override', ⚙️ → 🎛️).
   --------------------------------------------------------------------------- */
const WORD_ACTIONS = [
  { id: 'shabda', icon: '🔤', label: 'Shabda', handler: 'dgeOpenShabdaForSelection',
    wordOnly: true, powered: 'own', enabled: true,
    title: 'Declension table and dictionary results for this word' },
  { id: 'dhatu', icon: '📚', label: 'Dhātu', handler: 'dgeOpenDhatuForSelection',
    wordOnly: true, powered: 'own', enabled: true,
    title: 'Find the root this form comes from and show its derivation' },
  // Sandhi was hidden on 9 Sep 2026 -- "not working properly locally" -- and
  // it genuinely was not: the only split index was CDN-hosted, so a local
  // checkout had no data to answer with. dge/data/_sandhi_local (built by
  // tools/build_sandhi_split_index.py from sanskrit_parser's Sandhi.split_all,
  // validated against this repo's own word lists) ships in the repo, so it
  // now answers offline. Back on, and still switchable off by an admin or on
  // one device like everything else here.
  { id: 'sandhi', icon: '🔗', label: 'Sandhi', handler: 'dgeOpenVidyutSandhiForSelection',
    wordOnly: true, powered: 'own', enabled: true,
    title: 'Split this word at its sandhi boundary; verb halves link to their root' },
  { id: 'samasa', icon: '🧩', label: 'Samasa', handler: 'askAcharya', arg: 'samasa',
    wordOnly: true, powered: 'gemini', enabled: false,
    title: 'Samasa Vigraha for this word' },
  { id: 'searchLibrary', icon: '🔍', label: 'Search Library', handler: 'dgeOpenCorpusSearchForSelection',
    wordOnly: false, powered: 'own', enabled: true,
    title: 'Find every other place this word or phrase appears in the library' },
  { id: 'sandhiLive', icon: '🔗', label: 'Sandhi (Live)', handler: 'dgeOpenSandhiForSelection',
    wordOnly: true, powered: 'external', enabled: false,
    title: 'Live sandhi split via a third-party service' },
  // Copy, 10 Sep 2026. The lead's report: right-clicking a word offered no way
  // to copy it -- only the Genie sheet opened. It genuinely was missing: this
  // row is built from WORD_ACTIONS and Copy was never in it, even though
  // contextual-actions.js's own comment claimed not to duplicate "the
  // Shabda/Dhatu/Sandhi/Copy/Ask-Acharya buttons above".
  //
  // `requiresCapability` is new and is what makes these two different from
  // every other entry: copy is granted per ROLE (role-access.js's dgeRoleCan),
  // so an admin can decide who may take text out. An admin always may; with
  // nothing configured, nobody else does -- which is exactly the behaviour
  // copy-guard.js already had.
  { id: 'copyWord', icon: '📋', label: 'Copy', handler: 'dgeCopySelectionText',
    wordOnly: false, powered: 'own', enabled: true, requiresCapability: 'copy',
    title: 'Copy the selected word or phrase' },
  { id: 'copySentence', icon: '📄', label: 'Copy sentence', handler: 'dgeCopySentenceAroundSelection',
    wordOnly: false, powered: 'own', enabled: true, requiresCapability: 'copy',
    title: 'Copy the whole sentence this word sits in' }
];
window.WORD_ACTIONS = WORD_ACTIONS;

// True when this viewer may spend the project's Gemini credits. Ordinary
// readers never see a paid action at all -- the lead's ask, 9 Sep 2026:
// "hide the Gemini API options from normal users and restrict them to
// features powered by project-owned APIs."
window.dgeAiFeaturesAllowed = function () {
  try {
    return localStorage.getItem('acharyaAuthorized') === 'true' ||
           localStorage.getItem('is_superadmin') === 'true';
  } catch (e) { return false; }
};

window.dgeGetEffectiveWordActions = function () {
  let global = {}, local = {};
  try { global = (window.appConfig && window.appConfig.wordActions) || {}; } catch (e) {}
  try { local = JSON.parse(localStorage.getItem('word_actions_override') || 'null') || {}; } catch (e) {}
  const aiOk = window.dgeAiFeaturesAllowed();
  return WORD_ACTIONS
    .map(function (a) {
      const enabled = local[a.id] !== undefined ? local[a.id]
                    : global[a.id] !== undefined ? global[a.id]
                    : a.enabled;
      return Object.assign({}, a, { enabled: enabled });
    })
    .filter(function (a) {
      if (!a.enabled) return false;
      if (a.powered === 'gemini' && !aiOk) return false;
      // A capability-gated tool needs the grant as well as the switch. No
      // role-access.js on this page (the standalone grammar pages) means no
      // capability system, so those tools simply don't offer it.
      if (a.requiresCapability) {
        return typeof window.dgeRoleCan === 'function' && window.dgeRoleCan(a.requiresCapability);
      }
      return true;
    });
};

// Which scripts/languages appear in the 🔠 script selector, and in what
// order. Remove an entry (or set enabled:false) to hide it from the
// picker without touching any transliteration code — it still works if
// selected via a saved preference, this only affects what's offered.
// 'hindi' and 'marathi' are Devanagari-script languages -- same glyphs as
// 'devanagari' itself, so they're offered as separate, friendlier-labeled
// entries rather than a genuinely distinct transliteration target (a
// Marathi/Hindi reader may not think to reach for "Sanskrit" to read the
// same script they already read daily). transliteration.js's
// applyTransliteration() and dgeToActiveScript() both special-case these
// two ids to a no-op, alongside 'devanagari' itself -- there is no
// Sanscript scheme literally named "hindi"/"marathi" to pass through.
const SCRIPT_OPTIONS = [
  { id: 'devanagari', label: 'Sanskrit', enabled: true },
  { id: 'hindi', label: 'Hindi', enabled: true },
  { id: 'marathi', label: 'Marathi', enabled: true },
  { id: 'iast', label: 'English', enabled: true },
  { id: 'kannada', label: 'Kannada', enabled: true },
  { id: 'telugu', label: 'Telugu', enabled: true },
  { id: 'tamil', label: 'Tamil', enabled: true },
  { id: 'malayalam', label: 'Malayalam', enabled: true },
  { id: 'bengali', label: 'Bengali', enabled: true },
  { id: 'oriya', label: 'Odia', enabled: true }
];
window.SCRIPT_OPTIONS = SCRIPT_OPTIONS;

window.dgeGetEffectiveScriptOptions = function() {
  try {
    const override = JSON.parse(localStorage.getItem('script_options_override') || 'null');
    if (override && typeof override === 'object') {
      return SCRIPT_OPTIONS.map(opt => ({ ...opt, enabled: override[opt.id] !== undefined ? override[opt.id] : opt.enabled }));
    }
  } catch (e) { /* fall through to defaults */ }
  return SCRIPT_OPTIONS;
};

window.dgeGetEffectiveFeatureFlags = function() {
  try {
    const override = JSON.parse(localStorage.getItem('feature_flags_override') || 'null');
    if (override && typeof override === 'object') {
      return Object.assign({}, FEATURE_FLAGS, override);
    }
  } catch (e) { /* fall through to defaults */ }
  return FEATURE_FLAGS;
};

// Configurable Audio Source. Precedence: end-user local override
// (localStorage, this device only) > super-admin-configured global
// default (appConfig.audioBaseUrl, via config-overrides.json — same
// mechanism as every other appConfig field) > the hardcoded fallback.
window.dgeGetEffectiveAudioBaseUrl = function() {
  try {
    const override = localStorage.getItem('audio_base_url_override');
    if (override && override.trim()) return override.trim();
  } catch (e) { /* fall through to the configured default */ }
  return (window.appConfig && window.appConfig.audioBaseUrl) || 'https://archive.org/download/';
};

// The host prefix actually baked into every existing grantha's stored
// archiveBaseUrl today. NOT the same thing as the current default above
// (that can itself be changed by a super-admin) — this is specifically
// what needs to be recognized-and-stripped from OLD data so it can be
// replaced with whatever's effective NOW, without ever touching the
// JSON files themselves.
const AUDIO_LEGACY_DEFAULT_BASE = 'https://archive.org/download/';

// Rewrites one grantha's stored archiveBaseUrl to use the currently
// effective host, preserving everything after the recognized default
// prefix (the per-grantha identifier folder) untouched. A grantha whose
// stored URL does NOT start with the recognized default (someone already
// pointed it at a fully custom host on purpose) is left exactly as-is —
// this only ever substitutes the common, known prefix, never guesses.
window.dgeApplyAudioBaseUrlOverride = function(rawBaseUrl) {
  if (!rawBaseUrl || typeof rawBaseUrl !== 'string' || !rawBaseUrl.startsWith(AUDIO_LEGACY_DEFAULT_BASE)) return rawBaseUrl;
  const effective = window.dgeGetEffectiveAudioBaseUrl();
  return effective + rawBaseUrl.slice(AUDIO_LEGACY_DEFAULT_BASE.length);
};

// Quick Search abbreviations — type e.g. "rv1.1.3" in the Library's quick
// jump box to go straight to a specific verse anywhere in the library,
// not just search within whichever text is currently open. Each entry
// maps a case-insensitive prefix to a specific populated grantha (or, for
// a multi-file text like the Rigveda, a per-mandala path template) and
// how to read the number(s) that follow.
//
// Deliberately NOT wired up for texts that don't exist yet (Gita,
// Bhagavata Purana, etc. are still 0% populated per library.json) —
// pointing an abbreviation at empty content would silently land on "Not
// Yet Available", which is worse than not offering the shortcut at all.
// Add an entry here once a grantha is actually populated; resolve()
// receives the dot-separated numeric parts already split out.
const QUICK_SEARCH_ABBREVIATIONS = [
  {
    prefix: 'rv',
    label: 'Rigveda',
    example: 'rv1.1.3 → Maṇḍala 1, Sūkta 1, Mantra 3',
    // Each maṇḍala is its own grantha/data.json, and every mantra's own
    // "id" field is already "mandala.sukta.mantra" (confirmed against
    // real data — no padding, e.g. "1.1.1" not "1.1.01") — no separate
    // lookup table needed, just a reverse scan for that id at load time
    // (see dgeResolveQuickJumpTarget in core.js).
    // 7 Sep 2026: any depth is a valid target, not only the full triple --
    // "rv1.1" (a sūkta) opens that sūkta's first mantra and "rv1" (a
    // maṇḍala) its first mantra, because a partial id is a prefix of the
    // mantra ids under it (core.js dgeResolveQuickJumpTarget matches a
    // dotted prefix when no exact id exists). Reported live: "rv1.1" + Enter
    // used to be rejected here and the reader stayed where it was.
    resolve: function(parts) {
      if (parts.length < 1 || parts.length > 3 || parts.some(p => !/^\d+$/.test(p))) return null;
      const mandala = parseInt(parts[0], 10);
      if (!mandala || mandala < 1 || mandala > 10) return null;
      const mm = String(mandala).padStart(2, '0');
      const granthaPath = `vedas/rigveda/shakala_shakha/samhita/mandala_${mm}`;
      if (parts.length === 1) return { granthaPath, shlokaNumber: 1 };
      return { granthaPath, vedicId: parts.map(p => String(parseInt(p, 10))).join('.') };
    }
  },
  {
    prefix: 'pns',
    label: 'Prahlādakṛta Nṛsiṁha Stotra',
    example: 'pns5 → Shloka 5',
    resolve: function(parts) {
      if (parts.length !== 1 || !/^\d+$/.test(parts[0])) return null;
      const n = parseInt(parts[0], 10);
      if (!n) return null;
      return { granthaPath: 'DvaitaVedanta/Itara/Stotra/prahlada_kruta_narasimha', shlokaNumber: n };
    }
  }
];
window.QUICK_SEARCH_ABBREVIATIONS = QUICK_SEARCH_ABBREVIATIONS;

// Parses "rv1.1.3", "pns 5", "RV 1.1.3" etc. into a jump target, or
// returns null if it doesn't match any known abbreviation — callers
// should treat null as "not a quick-search query", not as an error.
window.dgeParseQuickSearchQuery = function(text) {
  // 7 Sep 2026: js/shortcuts.js is the one grammar (rv, av, avp, ts, vs, sv, smv, rgv, pns, bhp, mbh, rm, hv…);
  // the table below is kept as the fallback when that file is not loaded.
  if (window.DGEShortcuts && window.DGEShortcuts.parse) {
    const r = window.DGEShortcuts.parse(text);
    if (r) return r;
  }
  const m = String(text || '').trim().match(/^([a-zA-Z]+)\s*([\d.]+)$/);
  if (!m) return null;
  const prefixInput = m[1].toLowerCase();
  const parts = m[2].split('.').filter(p => p !== '');
  const entry = QUICK_SEARCH_ABBREVIATIONS.find(e => e.prefix.toLowerCase() === prefixInput);
  if (!entry) return null;
  const resolved = entry.resolve(parts);
  return resolved ? Object.assign({ label: entry.label }, resolved) : null;
};

// ---------------------------------------------------------------
// User Accounts & Roles (Firebase) — see FIREBASE_SETUP.md for the
// console steps that have to happen outside this codebase before any of
// this does anything. Nothing here is live until FIREBASE_CONFIG below
// is replaced with real values AND AUTH_CONFIG.enabled is set true.
// ---------------------------------------------------------------

// Placeholder — replace every value with your own Firebase project's
// config (Project Settings → General → "Your apps" → SDK setup and
// configuration → Config, in the Firebase console). These values are NOT
// secret — Firebase's own docs are explicit that this object is safe to
// ship in client code, since access control is enforced by Firestore
// security rules (see dge/firebase/firestore.rules), not by hiding this.
// Project "sarvamula-org", created by the lead 6 Sep 2026 (web app config pasted from the Firebase
// console). The same three identifiers also live in the GitHub secrets FIREBASE_API_KEY /
// FIREBASE_AUTH_DOMAIN / FIREBASE_PROJECT_ID for the hosting-deploy workflow; they are public
// identifiers, not credentials (see the note above), so keeping them here is correct.
const FIREBASE_CONFIG = {
  apiKey: "AIzaSyC_mvK6f4CS91B51iEvx2B6wlk_9A-lVCw",
  authDomain: "sarvamula-org.firebaseapp.com",
  projectId: "sarvamula-org",
  storageBucket: "sarvamula-org.firebasestorage.app",
  messagingSenderId: "1005094356690",
  appId: "1:1005094356690:web:f2e196c0ad9bc299b14f0b",
  measurementId: "G-YB411NKZLE"
};
window.FIREBASE_CONFIG = FIREBASE_CONFIG;

// Master switches — deliberately OFF by default so this entire feature
// stays inert (no Firebase network calls, no Account button shown) on
// any deployment that hasn't gone through the FIREBASE_SETUP.md steps.
const AUTH_CONFIG = {
  // Flipped true 6 Sep 2026 (FIREBASE_CONFIG holds the sarvamula-org project). Sign-in works only once
  // the console steps in FIREBASE_SETUP.md §3 are done: Google provider enabled, Firestore created in
  // production mode with dge/firebase/firestore.rules published.
  enabled: true,

  // Google Sign-In: free at any volume, no billing plan needed at all.
  enableGoogleSignIn: true,

  // Phone/SMS OTP: real per-message cost, and requires Firebase's paid
  // Blaze plan regardless of which provider actually sends the SMS. Off
  // by default on purpose — flip on only once you've accepted that cost
  // and picked a provider below.
  enablePhoneAuth: false,

  // Which channel carries the one-time code. All three are built; they
  // differ in cost, in what has to be set up, and in what the user sees.
  //
  // 'firebase' — Firebase's own SMS. Zero backend code (Google's infra
  //   handles send+verify client-side), and the fastest to turn on, but
  //   the most expensive per code: roughly $0.01 (~₹0.85) per
  //   verification in India. Note that Firebase's free allowance here is
  //   about 10 SMS per DAY, not the 10,000/month figure that circulates
  //   online — assume you are paying from the first real user.
  // 'whatsapp' — Meta WhatsApp Cloud API through our own Cloud Functions
  //   (dge/firebase/functions). Authentication templates run about
  //   ₹0.145 per message in India, so roughly 6x cheaper than the line
  //   above, and the code arrives with a one-tap "copy" button. Needs a
  //   Meta Business account and an approved template — see
  //   FIREBASE_SETUP.md §7.
  // 'msg91' — India SMS gateway through the same Cloud Functions.
  //   Comparable to WhatsApp on price (~₹0.15) and reaches people who
  //   do not use WhatsApp; needs an MSG91 account and DLT registration.
  //
  // 'whatsapp' and 'msg91' share one backend and one client code path —
  // switching between them is this one string plus the OTP_PROVIDER
  // value on the deployed functions.
  phoneOtpProvider: 'firebase',

  // Region the Cloud Functions are deployed to. Must match the
  // setGlobalOptions region in dge/firebase/functions/index.js, or every
  // callable request lands on a URL that does not exist.
  functionsRegion: 'asia-south1',

  // Shows the "send me updates on WhatsApp" consent checkbox on the
  // account screen, and is what the scheduled broadcast function's
  // audience is drawn from. Independent of phoneOtpProvider: you can
  // sign people in by SMS and still message them on WhatsApp, or use
  // WhatsApp for codes and never broadcast at all.
  enableWhatsappBroadcasts: false,

  // Applied to a user's Firestore profile on first sign-in. Changing
  // this later does NOT retroactively change existing users' roles.
  defaultRole: 'basic',

  // The full set of assignable roles, in the order they should list in
  // the Manage Users admin UI. "special" is a deliberately generic top
  // slot for a one-off grant (a specific person's exception) rather than
  // a defined tier with its own rules — same spirit as "Other" options
  // elsewhere in this app.
  roles: ['basic', 'subscriber', 'sponsor', 'admin', 'superadmin', 'special']
};
window.AUTH_CONFIG = AUTH_CONFIG;

// Note: All dynamic state variables (stotraData, activeId, marks, notes, etc.)
// and URL parameter parsing have been successfully migrated to js/state.js to 
// maintain strict separation of concerns.
