// dge/js/role-access.js — role-based content gating (8 Sep 2026).
//
// UI-level only, by explicit project-lead decision: this hides gated
// taxonomy paths from the reader's own navigation/search for anyone whose
// role doesn't clear the gate. It does NOT stop a determined visitor who
// already knows (or guesses) the direct file path from fetching the raw
// data.json — the corpus files stay public static assets on Hosting,
// exactly like the pre-existing admin/config/library-overrides.json
// "hidden" list this extends. Real per-request enforcement would mean
// serving corpus text through an authenticated proxy instead of static
// files, which is a materially different (and more expensive) hosting
// architecture — out of scope until asked for.
//
// Source of truth is Firestore (see firestore.rules' `config/{docId}`
// block: public read, superadmin-only write) rather than a committed
// static file, unlike library-overrides.json — so a superadmin's edits
// in admin/access-control.html take effect for every visitor immediately,
// no export/commit/push/deploy cycle. This is intentional: the whole
// point of that admin page is a fast create-role -> grant-access -> test
// loop, and Firestore is already loaded on every page view (see
// user-auth.js's DOMContentLoaded handler, which loads the SDK
// unconditionally whenever AUTH_CONFIG.enabled is true, whether or not
// the visitor signs in) so reading two small config docs costs nothing
// beyond what's already paid.
window.DGE_VERSIONS = window.DGE_VERSIONS || {};
window.DGE_VERSIONS['role-access.js'] = 'v1.2 (10 Sep 2026: the first-superadmin explainer -- device passkey vs account role) \u00b7 v1.1 (go-live shelf + capabilities) \u00b7 v1.0 (Firestore-backed content gates + preview-as-role)';

// config/roles      -> { list: [{ id, label }, ...] }
// config/roleAccess  -> { gates: [{ prefix, allowRoles: [id, ...] }, ...] }
// Both documents are optional — an unconfigured deployment behaves exactly
// as before this file existed (no roles beyond AUTH_CONFIG.roles, no gates).
let dgeRoleAccessGates = [];   // [{ prefix, allowRoles }]
// { capability: [role id, ...] } -- what a role may DO, as opposed to what it
// may see. Same Firestore doc as the gates (config/roleAccess), same
// public-read/superadmin-write rule.
let dgeRoleCapabilities = {};
let dgeAllRoles = null;        // [{ id, label }] once loaded; null = not loaded yet
let dgeRoleAccessLoadPromise = null;

// The fixed tier every deployment ships with (AUTH_CONFIG.roles), plus the
// pseudo-role used for a visitor who hasn't signed in at all — distinct
// from 'basic' (a real, registered account) so a gate can require "signed
// in" without requiring any particular tier.
const DGE_ANONYMOUS_ROLE = 'anonymous';

function dgeFixedRoles() {
  const configured = (window.AUTH_CONFIG && Array.isArray(window.AUTH_CONFIG.roles)) ? window.AUTH_CONFIG.roles : ['basic'];
  return configured.map(id => ({ id, label: id.charAt(0).toUpperCase() + id.slice(1) }));
}

/**
 * Pure, testable gate matcher — no Firestore, no DOM. Longest matching
 * path-prefix wins, mirroring dgeIsHiddenPath's own walk in library.js so
 * the two behave identically for "does this path fall under that prefix".
 * A path with no configured gate is open to everyone (gates are opt-in
 * restrictions, same direction library-overrides.json's hidden list takes).
 */
window.dgeMatchRoleGate = function(path, gates) {
  if (!path || !Array.isArray(gates) || !gates.length) return null;
  const parts = String(path).split('/');
  let matched = null;
  for (let i = 1; i <= parts.length; i++) {
    const prefix = parts.slice(0, i).join('/');
    const g = gates.find(g => g && g.prefix === prefix);
    if (g) matched = g; // a longer (deeper) match overrides a shorter one
  }
  return matched;
};

/**
 * True when `role` is blocked from `path` by `gates`. Pure function, unit
 * tested directly (see dge/firebase/tests/role-access.test.js) without any
 * Firebase or browser globals.
 */
window.dgeIsRoleGatedPath = function(path, role, gates) {
  const gate = window.dgeMatchRoleGate(path, gates);
  if (!gate) return false;
  const allow = Array.isArray(gate.allowRoles) ? gate.allowRoles : [];
  return allow.indexOf(role || DGE_ANONYMOUS_ROLE) < 0;
};

/* --- The go-live shelf ---------------------------------------------------
 *
 * A gate says "this path is closed to these roles". The shelf says the
 * opposite and is the shape a launch actually needs: EVERYTHING is closed
 * except a named handful. Asked for directly, 10 Sep 2026, for the 17 Sep
 * go-live — Sumadhva Vijaya, Raghavendra Vijaya and Tīrtha Prabandha
 * visible, "rest must be hidden ... the DvaitaVedanta and SetuTila".
 *
 * Enumerating what to hide would have meant listing ~590 leaves and being
 * wrong the first time a grantha is added; a shelf is wrong in the safe
 * direction, because a text nobody remembered to list stays private rather
 * than going live by accident.
 *
 * TWO DIRECTIONS COUNT AS ON-SHELF, and both are needed for the tree to
 * work. A DESCENDANT of an allowed path is on the shelf (each sarga of
 * Sumadhva Vijaya). So is an ANCESTOR — SarvaMula and SarvaMula/kavya must
 * survive for the drawer to have anything to open, even though the rest of
 * SarvaMula does not.
 */
window.dgeMatchShelf = function(path, allow) {
  if (!Array.isArray(allow) || !allow.length) return true;   // no shelf configured = everything open
  const p = String(path || '');
  if (!p) return true;
  return allow.some(entry => {
    const a = String(entry || '');
    if (!a) return false;
    return p === a || p.indexOf(a + '/') === 0 || a.indexOf(p + '/') === 0;
  });
};

//: The shelf, once library.js has read library-overrides.json. Held here
//: rather than reached for through library.js so admin/access-control.html
//: — which never loads library.js — can still preview against it.
let dgeShelfConfig = null;
window.dgeSetShelfConfig = function(shelf) {
  dgeShelfConfig = (shelf && shelf.enabled && Array.isArray(shelf.allow) && shelf.allow.length) ? shelf : null;
};
window.dgeGetShelfConfig = function() { return dgeShelfConfig; };

/**
 * True when the shelf hides `path` from whoever is looking. Same bypass
 * rule as the role gates: a real admin sees everything, but an admin who
 * has switched into preview does NOT — seeing the shelf exactly as a
 * visitor sees it is the entire point of previewing.
 */
window.dgeIsOffShelf = function(path) {
  const shelf = dgeShelfConfig;
  if (!shelf) return false;
  const open = Array.isArray(shelf.openToRoles) ? shelf.openToRoles : [];
  const preview = window.dgeGetPreviewRole();
  if (!preview && typeof dgeIsAdmin === 'function' && dgeIsAdmin()) return false;
  const role = window.dgeEffectiveGatingRole();
  if (open.indexOf(role) >= 0) return false;
  return !window.dgeMatchShelf(path, shelf.allow);
};

// --- Firestore loading --------------------------------------------------

/**
 * Loads config/roles + config/roleAccess once and caches the result;
 * concurrent callers share one load. Safe to call before Firebase has
 * initialized (waits on dgeEnsureFirebaseSdk, same lazy-load promise
 * user-auth.js's other consumers share) and safe to call when accounts
 * are switched off entirely (AUTH_CONFIG.enabled false) — resolves to the
 * fixed roles with no gates, i.e. unchanged behavior.
 */
window.dgeLoadRoleAccessConfig = function() {
  if (dgeRoleAccessLoadPromise) return dgeRoleAccessLoadPromise;
  dgeRoleAccessLoadPromise = (async () => {
    if (!window.AUTH_CONFIG || !window.AUTH_CONFIG.enabled) {
      dgeAllRoles = dgeFixedRoles();
      dgeRoleAccessGates = [];
      return;
    }
    try {
      if (typeof window.dgeEnsureFirebaseSdk === 'function') await window.dgeEnsureFirebaseSdk();
      if (typeof firebase === 'undefined' || !firebase.apps || !firebase.apps.length) {
        dgeAllRoles = dgeFixedRoles();
        dgeRoleAccessGates = [];
        return;
      }
      const db = firebase.firestore();
      const [rolesSnap, gatesSnap] = await Promise.all([
        db.collection('config').doc('roles').get(),
        db.collection('config').doc('roleAccess').get()
      ]);
      const rolesDoc = rolesSnap.exists ? rolesSnap.data() : null;
      const gatesDoc = gatesSnap.exists ? gatesSnap.data() : null;
      // Fixed roles always appear even if the config/roles doc hasn't been
      // saved yet (or is missing one) -- it only ever ADDS custom roles on
      // top, never hides a role the deployment itself defines.
      const fixed = dgeFixedRoles();
      const custom = (rolesDoc && Array.isArray(rolesDoc.list)) ? rolesDoc.list.filter(r => r && r.id && !fixed.some(f => f.id === r.id)) : [];
      dgeAllRoles = fixed.concat(custom);
      dgeRoleAccessGates = (gatesDoc && Array.isArray(gatesDoc.gates)) ? gatesDoc.gates : [];
      dgeRoleCapabilities = (gatesDoc && gatesDoc.capabilities && typeof gatesDoc.capabilities === 'object') ? gatesDoc.capabilities : {};
    } catch (e) {
      console.error('[RoleAccess] Failed to load config/roles or config/roleAccess:', e);
      dgeAllRoles = dgeFixedRoles();
      dgeRoleAccessGates = [];
    }
  })();
  return dgeRoleAccessLoadPromise;
};

/** Every role id known to this deployment: fixed tiers + any custom ones. */
window.dgeAllRoleIds = function() {
  return (dgeAllRoles || dgeFixedRoles()).map(r => r.id);
};
window.dgeAllRoleDefs = function() {
  return (dgeAllRoles || dgeFixedRoles()).slice();
};
window.dgeFixedRoleIds = function() {
  return dgeFixedRoles().map(r => r.id);
};
/** The currently cached gate list -- call dgeLoadRoleAccessConfig() first. */
window.dgeCurrentRoleGates = function() {
  return dgeRoleAccessGates.slice();
};

/**
 * Writes config/roles + config/roleAccess. Firestore rules (see
 * firestore.rules' config/{docId} block) reject this unless the caller is
 * actually signed in with role 'superadmin' -- the client-side
 * is_superadmin flag that gates admin/access-control.html's own UI is
 * convenience only, exactly like every other admin passkey in this app;
 * this call is the real check, enforced server-side regardless of what
 * this function's caller believes about itself.
 */
window.dgeSaveRoleAccessConfig = async function(customRoles, gates, capabilities) {
  if (typeof firebase === 'undefined' || !firebase.apps || !firebase.apps.length) {
    throw new Error('Firebase is not initialized.');
  }
  const db = firebase.firestore();
  const fixed = dgeFixedRoles();
  const list = fixed.concat((Array.isArray(customRoles) ? customRoles : []).filter(r => r && r.id && !fixed.some(f => f.id === r.id)));
  const cleanGates = (Array.isArray(gates) ? gates : []).filter(g => g && g.prefix).map(g => ({
    prefix: String(g.prefix),
    allowRoles: Array.isArray(g.allowRoles) ? g.allowRoles.slice() : []
  }));
  await db.collection('config').doc('roles').set({ list, updatedAt: firebase.firestore.FieldValue.serverTimestamp() });
  const cleanCaps = {};
  Object.keys(capabilities || {}).forEach(k => {
    if (Array.isArray(capabilities[k])) cleanCaps[k] = capabilities[k].slice();
  });
  await db.collection('config').doc('roleAccess').set({
    gates: cleanGates, capabilities: cleanCaps,
    updatedAt: firebase.firestore.FieldValue.serverTimestamp()
  });
  dgeAllRoles = list;
  dgeRoleAccessGates = cleanGates;
  dgeRoleCapabilities = cleanCaps;
};

/* --- The first superadmin -------------------------------------------------
 *
 * There are TWO separate ideas of "admin" in this app and they are easy to
 * mistake for one another — the lead did, 10 Sep 2026: "I am an admin
 * myself and have logged in as admin and superadmin, yet my account shows
 * I am a normal user."
 *
 *   Device access   the 🔑 Access passkeys (localStorage acharyaAuthorized /
 *                   is_superadmin). They decide what this BROWSER shows.
 *                   Nothing about them reaches Firestore.
 *
 *   Account role    users/<uid>.role in Firestore. It is what
 *                   firestore.rules actually enforces (callerRole()), so it
 *                   is the only thing that decides whether a write is
 *                   allowed — reading the user list, changing someone's
 *                   role, saving a content gate.
 *
 * A new account is created with role 'basic' and the rules forbid anyone
 * from changing their OWN role. That is deliberate — it is what stops a
 * visitor promoting themselves — but it means the very first superadmin
 * cannot be made from inside the app at all. It has to be set once, by
 * hand, in the Firebase console; after that the Manage Users screen
 * promotes everyone else.
 *
 * FIREBASE_SETUP.md §4 has always said so. What was missing is the app
 * saying so at the moment it matters: until now a passkey-holding admin
 * opening Manage Users just got "Missing or insufficient permissions" and
 * no way forward. This builds that explanation, with the person's own uid
 * in it, so the three places that can hit the wall all say the same thing.
 */
window.dgeSuperadminBootstrapHtml = function(opts) {
  const o = opts || {};
  const uid = o.uid || '';
  const project = o.projectId || (window.FIREBASE_CONFIG && window.FIREBASE_CONFIG.projectId) || '';
  const esc = (v) => String(v == null ? '' : v).replace(/[&<>"]/g, c => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  // Deep link straight to this person's own profile document, so the fix is
  // a click and one field rather than a hunt through a collection.
  const docUrl = (project && uid)
    ? 'https://console.firebase.google.com/project/' + encodeURIComponent(project) +
      '/firestore/databases/-default-/data/~2Fusers~2F' + encodeURIComponent(uid)
    : (project ? 'https://console.firebase.google.com/project/' + encodeURIComponent(project) + '/firestore/data' : '');
  return '' +
    '<div style="border:1px solid var(--card-border,#666); border-radius:8px; padding:12px; font-size:13px; line-height:1.5;">' +
    '<div style="font-weight:700; margin-bottom:6px;">Your account role is not <code>superadmin</code> yet</div>' +
    '<p style="margin:0 0 8px;">The 🔑 Access passkeys unlock this <b>browser</b>. Firestore enforces the ' +
    '<b>account</b> role instead, and a new account starts as <code>basic</code>. The rules deliberately ' +
    'stop anyone changing their own role, so the first superadmin is set once by hand.</p>' +
    (uid ? '<p style="margin:0 0 8px;">Your account id:<br><code style="user-select:all; word-break:break-all;">' + esc(uid) + '</code> ' +
      '<button type="button" class="btn-sm" onclick="window.dgeCopyUid(\'' + esc(uid) + '\', this)">Copy</button></p>' : '') +
    '<ol style="margin:0 0 8px; padding-left:18px;">' +
    (docUrl ? '<li>Open <a href="' + esc(docUrl) + '" target="_blank" rel="noopener" ' +
              'style="color:var(--accent-gold,#B9821F); font-weight:700; text-decoration:underline;">' +
              'your profile document in the Firebase console ↗</a></li>'
            : '<li>Open the Firebase console → Firestore Database → <code>users</code></li>') +
    '<li>Change the <code>role</code> field from <code>basic</code> to <code>superadmin</code></li>' +
    '<li>Come back and reload this page</li></ol>' +
    '<p style="margin:0 0 10px; opacity:.75;">From then on every other role is granted from 👥 Manage Users — this is a one-time step. ' +
    'See FIREBASE_SETUP.md §4.</p>' +
    // The shortcut, when the deployment has a bootstrap allowlist configured
    // (firestore.rules bootstrapUids / bootstrapEmails). The button does not
    // know whether this account is on that list -- nothing client-side can
    // know that without duplicating the list into public JS, which would
    // defeat keeping it in the rules. So it simply TRIES the write: allowed
    // for a listed account, refused for everyone else, and the refusal is
    // the same message they are already reading.
    '<button type="button" class="btn-sm" onclick="window.dgeClaimSuperadmin(this)">Try claiming super admin</button>' +
    '<div id="dgeClaimResult" style="margin-top:8px;"></div>' +
    '<p style="margin:8px 0 0; font-size:11px; opacity:.6;">Works only once an allowlist is configured and deployed ' +
    '(firestore.rules → <code>bootstrapUids</code>). Otherwise use the console steps above.</p></div>';
};

/**
 * Attempt the one-time self-promotion the bootstrap rule allows. Writes
 * ONLY the role field, because that is all the rule permits — anything else
 * in the same write is rejected outright by its hasOnly(['role']).
 */
window.dgeClaimSuperadmin = async function(btn) {
  const out = document.getElementById('dgeClaimResult');
  const say = (msg, ok) => { if (out) out.innerHTML = '<span style="color:' + (ok ? 'inherit' : 'var(--accent-red,#c00)') + ';">' + msg + '</span>'; };
  const user = (window.firebase && firebase.auth && firebase.auth().currentUser) || window.dgeCurrentUser;
  if (!user || !user.uid) { say('Sign in first.', false); return; }
  if (btn) { btn.disabled = true; btn.textContent = 'Claiming…'; }
  try {
    await firebase.firestore().collection('users').doc(user.uid).update({ role: 'superadmin' });
    say('Done — reloading…', true);
    if (typeof location !== 'undefined' && location.reload) setTimeout(() => location.reload(), 700);
  } catch (e) {
    if (btn) { btn.disabled = false; btn.textContent = 'Try claiming super admin'; }
    say(window.dgeIsPermissionError(e)
      ? 'Refused — this account is not on the bootstrap allowlist. Use the console steps above, or add it to firestore.rules and deploy.'
      : 'Failed: ' + String((e && e.message) || e), false);
  }
};

window.dgeCopyUid = function(uid, btn) {
  const done = () => { if (btn) { const t = btn.textContent; btn.textContent = 'Copied'; setTimeout(() => { btn.textContent = t; }, 1500); } };
  try {
    if (navigator.clipboard && window.isSecureContext) { navigator.clipboard.writeText(uid).then(done).catch(done); return; }
  } catch (e) { /* fall through */ }
  const ta = document.createElement('textarea');
  ta.value = uid; ta.style.position = 'fixed'; ta.style.left = '-9999px';
  document.body.appendChild(ta); ta.select();
  try { document.execCommand('copy'); } catch (e) { /* ignore */ }
  ta.remove(); done();
};

/** True when a Firestore error is the rules refusing, not a network fault. */
window.dgeIsPermissionError = function(e) {
  const code = (e && (e.code || e.name)) || '';
  const msg = String((e && e.message) || e || '');
  return code === 'permission-denied' || /insufficient permission|permission-denied|PERMISSION_DENIED/i.test(msg);
};

/* --- Capabilities: what a role may DO ------------------------------------
 *
 * Gates answer "may this person SEE this path". Capabilities answer "may
 * this person copy text" -- a different question with the same
 * grant-by-role shape, so it rides in the same Firestore document rather
 * than growing a second config surface.
 *
 * COPY, specifically. copy-guard.js used to allow copying to admins and
 * nobody else, which meant a scholar the lead trusted had no way to take a
 * word into their own notes. The lead's choice, 10 Sep 2026: copy is
 * granted per role, "so I decide per person". An UNCONFIGURED capability
 * is closed to everyone but an admin -- the same direction the shelf
 * takes, and the same direction copy-guard already took.
 */
window.dgeRoleCapabilityRoles = function(cap) {
  const v = dgeRoleCapabilities[cap];
  return Array.isArray(v) ? v.slice() : [];
};
window.dgeAllCapabilities = function() { return Object.assign({}, dgeRoleCapabilities); };

window.dgeRoleCan = function(cap) {
  const preview = window.dgeGetPreviewRole();
  // A real admin can do everything; a previewing one is held to the role
  // they picked, which is the whole point of previewing.
  if (!preview && typeof dgeIsAdmin === 'function' && dgeIsAdmin()) return true;
  if (!preview) {
    try {
      if (localStorage.getItem('acharyaAuthorized') === 'true' ||
          localStorage.getItem('is_superadmin') === 'true') return true;
    } catch (e) { /* private mode */ }
  }
  const allowed = dgeRoleCapabilities[cap];
  if (!Array.isArray(allowed) || !allowed.length) return false;
  return allowed.indexOf(window.dgeEffectiveGatingRole()) >= 0;
};

// --- Preview-as-role (superadmin testing) -------------------------------
//
// The "test it in a cycle" ask: a superadmin can simulate any role's view
// of the reader without a second real account. Session-scoped (one tab,
// cleared on close) and gated on the REAL role, not the previewed one, so
// previewing 'basic' can never itself grant more than the actual
// signed-in account already has, and a person who is not actually a
// superadmin cannot grant themselves a preview by poking sessionStorage —
// dgeIsHiddenByRoleGate below reads the real role first and only consults
// the preview when that real check already passed.
const DGE_PREVIEW_ROLE_KEY = 'dge.previewRole';
const DGE_PREVIEW_STASH_KEY = 'dge.previewStash';
const DGE_PREVIEW_ADMIN_FLAGS = ['acharyaAuthorized', 'is_superadmin'];


// Deliberately reads localStorage directly rather than calling the
// library.js-defined dgeIsSuperAdmin() -- this file is loaded on
// admin/access-control.html too, which never loads library.js, and this
// check has to work there without depending on script load order across
// files that otherwise have nothing to do with each other.
function dgeRoleAccessIsSuperAdmin() {
  try {
    if (localStorage.getItem('is_superadmin') === 'true') return true;
    // While a preview is running the real admin flags are parked (see
    // dgeEnterPreview below), so the live flag is deliberately absent. The
    // stash is what says this device is really a superadmin -- without
    // consulting it, entering preview would immediately lock the previewer
    // out of their own exit.
    const stash = JSON.parse(localStorage.getItem(DGE_PREVIEW_STASH_KEY) || 'null');
    return !!(stash && stash.is_superadmin === 'true');
  } catch (e) { return false; }
}

/* --- "View as a general user" -------------------------------------------
 *
 * The ask, 10 Sep 2026: "I as a developer cum admin am viewing all the
 * options available, at the same time I want to simply switch over to a
 * general user mode who would not see any of those special features or
 * options."
 *
 * Setting a preview role alone was never enough for that. It changed the
 * CONTENT gates and nothing else, so an admin previewing 'basic' still saw
 * the 🛡️ Admin Tools menu, the Gemini word tools, the admin-only search
 * hits, the pending-leaves toggle and their own copy permissions -- i.e.
 * still not what a visitor sees.
 *
 * WHAT MAKES IT TOTAL. Nine different files decide "is this an admin?" by
 * reading the same two localStorage flags directly. Rather than route nine
 * call sites through a new helper -- and miss the tenth that gets written
 * next month -- entering preview PARKS those flags and exiting puts them
 * back. Every admin check in the app, including ones nobody remembers,
 * then answers "no" on its own.
 *
 * SURVIVING A CLOSED TAB. The preview role lives in sessionStorage (one
 * tab, gone on close) but the stash has to be in localStorage or a crash
 * mid-preview would take an admin's own access with it. So the stash is
 * restored automatically whenever it exists with no live preview beside it,
 * which is exactly the state a closed-and-reopened tab leaves behind.
 */
function dgePreviewStashAdminFlags() {
  try {
    if (localStorage.getItem(DGE_PREVIEW_STASH_KEY)) return;   // already parked
    const stash = {};
    DGE_PREVIEW_ADMIN_FLAGS.forEach(k => { stash[k] = localStorage.getItem(k); });
    localStorage.setItem(DGE_PREVIEW_STASH_KEY, JSON.stringify(stash));
    DGE_PREVIEW_ADMIN_FLAGS.forEach(k => localStorage.removeItem(k));
  } catch (e) { /* private mode: preview still gates content, just not chrome */ }
}

function dgePreviewRestoreAdminFlags() {
  try {
    const raw = localStorage.getItem(DGE_PREVIEW_STASH_KEY);
    if (!raw) return;
    const stash = JSON.parse(raw) || {};
    DGE_PREVIEW_ADMIN_FLAGS.forEach(k => {
      if (stash[k] == null) localStorage.removeItem(k);
      else localStorage.setItem(k, stash[k]);
    });
    localStorage.removeItem(DGE_PREVIEW_STASH_KEY);
  } catch (e) { /* ignore */ }
}
window.dgePreviewRestoreAdminFlags = dgePreviewRestoreAdminFlags;

/**
 * Enter/leave the preview. Both reload, deliberately: a dozen modules read
 * the admin flags once at boot, and re-deriving every one of them in place
 * would be a far larger change than starting the page again.
 */
window.dgeEnterPreview = function(role) {
  if (!dgeRoleAccessIsSuperAdmin()) { if (typeof showToast === 'function') showToast('Super admin access required.'); return; }
  dgePreviewStashAdminFlags();
  try { sessionStorage.setItem(DGE_PREVIEW_ROLE_KEY, role || DGE_ANONYMOUS_ROLE); } catch (e) {}
  if (typeof location !== 'undefined' && location.reload) location.reload();
};
window.dgeExitPreview = function() {
  try { sessionStorage.removeItem(DGE_PREVIEW_ROLE_KEY); } catch (e) {}
  dgePreviewRestoreAdminFlags();
  if (typeof location !== 'undefined' && location.reload) location.reload();
};

window.dgeSetPreviewRole = function(role) {
  if (!dgeRoleAccessIsSuperAdmin()) { if (typeof showToast === 'function') showToast('Super admin access required.'); return; }
  try { sessionStorage.setItem(DGE_PREVIEW_ROLE_KEY, role || ''); } catch (e) { /* private mode etc. */ }
};
window.dgeClearPreviewRole = function() {
  try { sessionStorage.removeItem(DGE_PREVIEW_ROLE_KEY); } catch (e) { /* ignore */ }
};
window.dgeGetPreviewRole = function() {
  if (!dgeRoleAccessIsSuperAdmin()) return null; // a stale flag from a former superadmin session never leaks a preview to anyone else
  try { return sessionStorage.getItem(DGE_PREVIEW_ROLE_KEY) || null; } catch (e) { return null; }
};

// --- The actual gate check library.js hooks into ------------------------

/**
 * Effective role for gating purposes: the preview role while one is set
 * (superadmin only, see above), else the real signed-in role, else the
 * anonymous pseudo-tier for a signed-out visitor.
 */
window.dgeEffectiveGatingRole = function() {
  const preview = window.dgeGetPreviewRole();
  if (preview) return preview;
  return window.dgeCurrentUserRole || DGE_ANONYMOUS_ROLE;
};

/**
 * The single call library.js's dgeIsHiddenPath makes. A real admin or
 * superadmin (not previewing) always passes -- the same bypass
 * dgeIsAdminOnlyGrantha already gives them elsewhere, so curating a gate
 * can never accidentally lock its own author out of the content they're
 * configuring. Previewing deliberately does NOT bypass: that's the whole
 * point of the preview, so a superadmin can see exactly what the role
 * they're testing would see.
 */
window.dgeIsHiddenByRoleGate = function(path) {
  const preview = window.dgeGetPreviewRole();
  if (preview) return window.dgeIsRoleGatedPath(path, preview, dgeRoleAccessGates);
  if (typeof dgeIsAdmin === 'function' && dgeIsAdmin()) return false;
  return window.dgeIsRoleGatedPath(path, window.dgeEffectiveGatingRole(), dgeRoleAccessGates);
};
