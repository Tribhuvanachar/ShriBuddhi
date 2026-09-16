/**
 * corpus-access.js — may this person read this grantha?
 *
 * THE POINT OF THIS FILE. Every gate in the reader so far has been UI-level:
 * dgeIsHiddenPath keeps a text out of the drawer, global-search keeps it out
 * of results, core.js refuses a direct ?path= link — but the data.json itself
 * is a public static file, so any of it can be read by anyone who knows the
 * URL. This module is the same decision made somewhere a visitor cannot
 * bypass: on the server, before a byte of a gated text is sent.
 *
 * It is deliberately PURE — no Firestore, no network, no Express. The caller
 * fetches the role and the config and hands them in, so the rule itself can
 * be unit tested exhaustively, which is the only way to be confident about a
 * function whose job is saying no.
 *
 * It mirrors js/role-access.js exactly, and it has to: if the two ever
 * disagree the reader shows a text the server then refuses, or worse, hides
 * one the server would have served. The shared cases are covered by tests on
 * both sides.
 */

'use strict';

const ANONYMOUS = 'anonymous';

/**
 * Is `path` on the published shelf?
 *
 * Both directions count, as in role-access.js: a DESCENDANT of an allowed
 * path is on the shelf (each sarga of a work), and so is an ANCESTOR (the
 * folders above it, or the drawer has nothing to open). Comparison is on
 * segment boundaries so "SarvaMulaOther" cannot ride in on "SarvaMula" —
 * that is the bug that would silently publish a whole section.
 */
function matchShelf(path, allow) {
  if (!Array.isArray(allow) || !allow.length) return true;   // no shelf = everything open
  const p = String(path || '');
  if (!p) return true;
  return allow.some((entry) => {
    const a = String(entry || '');
    if (!a) return false;
    return p === a || p.indexOf(a + '/') === 0 || a.indexOf(p + '/') === 0;
  });
}

/** The gate covering `path`, longest (deepest) prefix winning. */
function matchGate(path, gates) {
  if (!path || !Array.isArray(gates) || !gates.length) return null;
  const parts = String(path).split('/');
  let matched = null;
  for (let i = 1; i <= parts.length; i++) {
    const prefix = parts.slice(0, i).join('/');
    const g = gates.find((x) => x && x.prefix === prefix);
    if (g) matched = g;
  }
  return matched;
}

/**
 * The whole decision.
 *
 *   path    the grantha's DISPLAY path (post-`moves`), which is what both the
 *           shelf and the gates are written in.
 *   role    the caller's stored role, or null/undefined for a signed-out visitor.
 *   config  { shelf: {enabled, allow, openToRoles}, gates: [...] }
 *
 * Returns { allowed, reason } — the reason is logged, never sent to the
 * caller, because "denied by the gate on darshana/…/SetuTila" tells someone
 * probing the API exactly what exists and where.
 */
function decide(path, role, config) {
  const cfg = config || {};
  const effectiveRole = role || ANONYMOUS;

  // An admin sees everything. Note this is the STORED role, not a client
  // claim: the caller resolves it from users/<uid> before calling in.
  if (effectiveRole === 'admin' || effectiveRole === 'superadmin') {
    return { allowed: true, reason: 'admin' };
  }

  const shelf = cfg.shelf;
  if (shelf && shelf.enabled && Array.isArray(shelf.allow) && shelf.allow.length) {
    const open = Array.isArray(shelf.openToRoles) ? shelf.openToRoles : [];
    if (open.indexOf(effectiveRole) < 0 && !matchShelf(path, shelf.allow)) {
      return { allowed: false, reason: 'off-shelf' };
    }
  }

  const gate = matchGate(path, cfg.gates);
  if (gate) {
    const allow = Array.isArray(gate.allowRoles) ? gate.allowRoles : [];
    if (allow.indexOf(effectiveRole) < 0) {
      return { allowed: false, reason: 'gate:' + gate.prefix };
    }
  }

  return { allowed: true, reason: 'open' };
}

/**
 * Turn a request path into the corpus object it names, or null.
 *
 * Hostile input is the whole job here. Everything that is not exactly
 * `<segment>/<segment>/…/data.json` is refused rather than cleaned up:
 * traversal (`..`), absolute paths, backslashes, encoded separators, NUL,
 * and anything that is not a data.json. Sanitising a bad path invites the
 * next encoding that slips through; refusing it does not.
 */
function objectNameFor(rawPath) {
  let p = String(rawPath || '');
  if (!p) return null;
  try { p = decodeURIComponent(p); } catch (e) { return null; }
  if (p.indexOf('\0') >= 0 || p.indexOf('\\') >= 0) return null;
  p = p.replace(/^\/+/, '');
  if (!p.endsWith('/data.json')) return null;
  const parts = p.split('/');
  if (parts.some((s) => !s || s === '.' || s === '..')) return null;
  if (!parts.every((s) => /^[A-Za-z0-9._-]+$/.test(s))) return null;
  return p;
}

/** The display path (for the gate decision) from an object name. */
function displayPathFor(objectName, moves) {
  const slug = String(objectName || '').replace(/\/data\.json$/, '');
  const m = moves && typeof moves === 'object' ? moves : {};
  let best = null;
  Object.keys(m).forEach((src) => {
    if (slug === src || slug.indexOf(src + '/') === 0) {
      if (!best || src.length > best.length) best = src;
    }
  });
  if (!best) return slug;
  const dest = m[best];
  const rel = slug.slice(best.length).replace(/^\//, '');
  return dest ? (rel ? dest + '/' + rel : dest) : rel;
}

/**
 * Fold the two config sources into the one shape `decide` wants.
 *
 *   overrides   config/library-overrides.json, which owns the shelf
 *               and the `moves` that turn an on-disk path into a display one.
 *   roleAccess  Firestore's config/roleAccess, which owns the gates, because
 *               a superadmin edits those live in admin/access-control.html
 *               and they must take effect without a deploy.
 *
 * Either may be missing. A missing shelf means no shelf (everything open) —
 * the same thing the reader does, and the only honest default, since the
 * alternative would be a function that refuses the entire library whenever a
 * config read hiccups.
 */
function configFrom(overrides, roleAccess) {
  const o = overrides && typeof overrides === 'object' ? overrides : {};
  const ra = roleAccess && typeof roleAccess === 'object' ? roleAccess : {};
  const shelf = o.shelf && typeof o.shelf === 'object' ? o.shelf : null;
  const gates = Array.isArray(ra.gates) ? ra.gates.filter((g) => g && typeof g.prefix === 'string') : [];
  const moves = o.moves && typeof o.moves === 'object' ? o.moves : {};
  return { shelf, gates, moves };
}

module.exports = { ANONYMOUS, matchShelf, matchGate, decide, objectNameFor, displayPathFor, configFrom };
