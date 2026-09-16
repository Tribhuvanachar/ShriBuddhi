// workflows-core.js — which GitHub Actions the admin panel may start, what
// each one accepts, and who is allowed to press it.
//
// Pure functions only: no Firebase, no network, no secrets. index.js is the
// shell that holds the token and makes the call; everything a mistake could
// cost lives here, where `node --test` can reach it (../tests/workflows-core.test.js).
//
// The central idea is the ALLOWLIST. The Function holds a token that can start
// workflows in this repository, so the question is never "what did the browser
// ask for" but "is that one of the five things this button is for". A caller
// cannot name a workflow file, cannot invent an input, and cannot reach a
// branch other than the one declared here. If a new workflow should be
// clickable, it is added below — deliberately, in a commit — and not before.
'use strict';

/** The branch every dispatch runs from. Not caller-supplied, on purpose:
 *  `ref` is arbitrary-code-execution by another name — a fork's branch pushed
 *  here would run its own workflow file with this repository's permissions. */
const REF = 'main';

class WorkflowError extends Error {
  /** @param code one of Firebase's HttpsError codes, so index.js can rethrow verbatim. */
  constructor(code, message) {
    super(message);
    this.name = 'WorkflowError';
    this.code = code;
  }
}

// --- The catalogue ----------------------------------------------------
// ../workflows.json, not a literal here: admin/workflows.html reads the same
// file, so the list the panel shows and the list this module will dispatch
// cannot drift apart. See that file's _readme for what each field means.
const WORKFLOWS = require('../workflows.json').workflows;

/** The catalogue as the panel needs it. Returned to any admin; there is
 *  nothing in it that is not already visible in .github/workflows/. */
function catalogue() {
  return WORKFLOWS.map((w) => ({
    id: w.id,
    file: w.file,
    name: w.name,
    blurb: w.blurb,
    writes: w.writes,
    minRole: minRoleFor(w),
    // Placement and provenance for the admin page's cards (see the
    // _readme in workflows.json). Descriptive only; nothing dispatches on them.
    group: w.group || null,
    site: w.site || null,
    url: w.url || null,
    feeds: w.feeds || null,
    importer: w.importer || null,
    source_ids: w.source_ids || null,
    inputs: w.inputs.map((i) => ({ ...i }))
  }));
}

function findWorkflow(id) {
  return WORKFLOWS.find((w) => w.id === id) || null;
}

/** Anything that rewrites text a reader will see is superadmin-only; the
 *  reporting and metadata jobs are open to either admin tier. An admin who
 *  can refresh a tracker but not republish the Raghuvaṃśa is the useful
 *  middle this project actually has people for. */
function minRoleFor(w) {
  return w.writes === 'corpus' ? 'superadmin' : 'admin';
}

const RANK = { basic: 0, admin: 1, superadmin: 2 };

/** Throws unless `role` is at least `need`. An unknown role ranks 0, so a
 *  role string this code has never heard of is refused rather than trusted. */
function assertRole(role, need) {
  const have = RANK[role] || 0;
  if (have < (RANK[need] || 0)) {
    throw new WorkflowError(
      'permission-denied',
      need === 'superadmin'
        ? 'That one republishes text the site serves, so it needs a super-admin.'
        : 'Running workflows needs an admin account.'
    );
  }
}

/**
 * Turns whatever the browser sent into the exact string map the GitHub API
 * takes — every declared input present, nothing else accepted.
 *
 * Every value goes over the wire as a string even when the workflow declares
 * it a boolean: `workflow_dispatch` inputs are strings in the REST API and
 * Actions coerces them by the declared type. Sending a real `false` is the
 * classic way to have a dispatch rejected with a type error.
 */
function buildInputs(w, raw) {
  const given = (raw && typeof raw === 'object') ? raw : {};

  const unknown = Object.keys(given).filter((k) => !w.inputs.some((i) => i.name === k));
  if (unknown.length) {
    throw new WorkflowError('invalid-argument', `${w.name} has no input called "${unknown[0]}".`);
  }

  const out = {};
  for (const spec of w.inputs) {
    const v = given[spec.name];
    if (spec.type === 'boolean') {
      out[spec.name] = (v === undefined ? !!spec.default : coerceBool(spec, v)) ? 'true' : 'false';
      continue;
    }
    const s = v === undefined ? String(spec.default ?? '') : String(v).trim();
    // A comma-separated id list, not free text: the length cap and the
    // character set keep a stray paragraph — or a newline-injected second
    // argument — out of a shell that will interpolate it.
    if (s.length > 200) {
      throw new WorkflowError('invalid-argument', `"${spec.label}" is too long (200 characters max).`);
    }
    if (s && !/^[A-Za-z0-9_,\-. ]+$/.test(s)) {
      throw new WorkflowError('invalid-argument', `"${spec.label}" may only contain letters, digits, dots, dashes, underscores and commas.`);
    }
    if (spec.required && !s) {
      throw new WorkflowError('invalid-argument', `"${spec.label}" cannot be blank.`);
    }
    out[spec.name] = s;
  }
  return out;
}

function coerceBool(spec, v) {
  if (typeof v === 'boolean') return v;
  const s = String(v).trim().toLowerCase();
  if (s === 'true' || s === '1' || s === 'yes') return true;
  if (s === 'false' || s === '0' || s === 'no') return false;
  throw new WorkflowError('invalid-argument', `"${spec.label}" must be yes or no.`);
}

/** How long one account must wait between dispatches. Not an abuse control —
 *  the callers are counted on one hand — but a double-click on a job that
 *  opens a pull request should not open two. */
const COOLDOWN_MS = 60 * 1000;

function checkCooldown(lastDispatchedAtMs, now) {
  if (!lastDispatchedAtMs) return;
  const waited = now - lastDispatchedAtMs;
  if (waited >= 0 && waited < COOLDOWN_MS) {
    const secs = Math.ceil((COOLDOWN_MS - waited) / 1000);
    throw new WorkflowError('resource-exhausted', `That was just started. Give it ${secs}s.`);
  }
}

/**
 * Reduces GitHub's /actions/runs payload to the one line the panel shows per
 * workflow: the newest run of each file we know about.
 *
 * GitHub returns runs newest-first, but says so rather than guaranteeing it,
 * so the newest is picked by date instead of by position.
 */
function latestRuns(payload) {
  const runs = (payload && Array.isArray(payload.workflow_runs)) ? payload.workflow_runs : [];
  const byFile = {};
  for (const r of runs) {
    const file = String(r.path || '').replace(/^\.github\/workflows\//, '');
    // Several cards can share one file (every "online source syncer" card is
    // check-sources.yml with a different `only`), so the newest run of a file
    // is reported under each card that runs it.
    const sharing = WORKFLOWS.filter((x) => x.file === file);
    if (!sharing.length) continue;
    const at = Date.parse(r.created_at || '') || 0;
    for (const w of sharing) {
      const seen = byFile[w.id];
      if (seen && seen._at >= at) continue;
      byFile[w.id] = {
        _at: at,
        id: r.id,
        status: r.status,                 // queued | in_progress | completed
        conclusion: r.conclusion || null, // success | failure | cancelled | …
        startedAt: r.created_at || null,
        url: r.html_url || null,
        by: (r.triggering_actor && r.triggering_actor.login) || null
      };
    }
  }
  for (const k of Object.keys(byFile)) delete byFile[k]._at;
  return byFile;
}

module.exports = {
  REF,
  WorkflowError,
  catalogue,
  findWorkflow,
  minRoleFor,
  assertRole,
  buildInputs,
  checkCooldown,
  latestRuns,
  COOLDOWN_MS
};
