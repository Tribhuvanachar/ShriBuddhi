// Tests for js/role-access.js — the client-side gate matcher behind
// admin/access-control.html and js/library.js's dgeIsHiddenPath.
//
// The matcher itself (dgeMatchRoleGate / dgeIsRoleGatedPath) is pure —
// no Firebase, no DOM — so it is exercised directly rather than through
// the heavier fake-env.js sandbox user-auth.test.js needs for its
// script-loading and Firestore-call assertions. What's covered here is
// exactly the logic that can be wrong on its own: prefix matching (not
// accidentally matching a sibling that merely shares characters),
// longest-prefix precedence, and the allow/deny default for a path with
// no gate at all vs. one that has a gate but doesn't list the role being
// checked.
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test, describe } = require('node:test');
const assert = require('node:assert/strict');

const ROLE_ACCESS_JS = path.resolve(__dirname, '../../js/role-access.js');

function loadRoleAccess({ authConfig } = {}) {
  const windowObj = {
    AUTH_CONFIG: authConfig !== undefined ? authConfig : {
      enabled: true,
      roles: ['basic', 'subscriber', 'sponsor', 'admin', 'superadmin', 'special']
    },
    DGE_VERSIONS: {}
  };
  const storageStub = () => {
    const m = new Map();
    return {
      getItem: (k) => (m.has(k) ? m.get(k) : null),
      setItem: (k, v) => { m.set(k, String(v)); },
      removeItem: (k) => { m.delete(k); }
    };
  };
  const sandbox = {
    window: windowObj,
    console: { log() {}, error() {}, warn() {} },
    localStorage: storageStub(),
    sessionStorage: storageStub(),
    Promise
  };
  // Same reasoning as fake-env.js's loadAuth: the script assigns to bare
  // `window.x`, so the sandbox's global object must resolve `window` to
  // the same object returned below, or assertions would check a copy the
  // script never touched.
  const context = vm.createContext(sandbox);
  vm.runInContext('var window = this.window;', context);
  vm.runInContext(fs.readFileSync(ROLE_ACCESS_JS, 'utf8'), context, { filename: 'role-access.js' });
  // Exposed alongside window's own exports so a test can drive
  // localStorage directly (e.g. simulating a superadmin device) without
  // reaching into the sandbox itself.
  windowObj.localStorage = sandbox.localStorage;
  windowObj.sessionStorage = sandbox.sessionStorage;
  return windowObj;
}

// Arrays/objects the script under test builds itself are constructed with
// the VM CONTEXT's own Array/Object constructors, not this file's -- two
// structurally-identical-but-different-realm values, which Node's assert
// module treats as unequal for some shapes (notably empty arrays). Copying
// through JSON round-trips it into a plain host-realm value before
// comparing, sidestepping the realm mismatch entirely.
const plain = (v) => JSON.parse(JSON.stringify(v));

describe('dgeMatchRoleGate — pure prefix matcher', () => {
  test('no gates configured -> no match', () => {
    const w = loadRoleAccess();
    assert.equal(w.dgeMatchRoleGate('a/b/c', []), null);
  });

  test('matches a gate on an ancestor prefix', () => {
    const w = loadRoleAccess();
    const gates = [{ prefix: 'a/b', allowRoles: ['admin'] }];
    assert.deepEqual(w.dgeMatchRoleGate('a/b/c', gates), gates[0]);
  });

  test('a path outside the gated prefix is unaffected', () => {
    const w = loadRoleAccess();
    const gates = [{ prefix: 'a/b', allowRoles: ['admin'] }];
    assert.equal(w.dgeMatchRoleGate('a/x/y', gates), null);
  });

  test('does not match a sibling that merely shares a string prefix', () => {
    // The walk is path-SEGMENT based (split on '/'), not a raw
    // startsWith() -- "darshana/vedanta" must not swallow
    // "darshana/vedantaOTHER", which starts with the same characters but
    // is a different folder entirely.
    const w = loadRoleAccess();
    const gates = [{ prefix: 'darshana/vedanta', allowRoles: [] }];
    assert.equal(w.dgeMatchRoleGate('darshana/vedantaOTHER/x', gates), null);
  });

  test('the longest matching prefix wins over a shorter ancestor gate', () => {
    const w = loadRoleAccess();
    const gates = [
      { prefix: 'a', allowRoles: ['admin'] },
      { prefix: 'a/b', allowRoles: ['sponsor'] }
    ];
    assert.deepEqual(w.dgeMatchRoleGate('a/b/c', gates), gates[1]);
  });

  test('a gate on the exact leaf path matches', () => {
    const w = loadRoleAccess();
    const gates = [{ prefix: 'a/b/c', allowRoles: ['sponsor'] }];
    assert.deepEqual(w.dgeMatchRoleGate('a/b/c', gates), gates[0]);
  });
});

describe('dgeIsRoleGatedPath — allow/deny', () => {
  test('a path with no configured gate is open to everyone, including anonymous', () => {
    const w = loadRoleAccess();
    assert.equal(w.dgeIsRoleGatedPath('open/path', 'anonymous', []), false);
  });

  test('a gated path blocks a role that is not on its allow list', () => {
    const w = loadRoleAccess();
    const gates = [{ prefix: 'gated', allowRoles: ['sponsor'] }];
    assert.equal(w.dgeIsRoleGatedPath('gated/x', 'basic', gates), true);
  });

  test('a gated path admits a role that is on its allow list', () => {
    const w = loadRoleAccess();
    const gates = [{ prefix: 'gated', allowRoles: ['sponsor'] }];
    assert.equal(w.dgeIsRoleGatedPath('gated/x', 'sponsor', gates), false);
  });

  test('a signed-out visitor (role null/undefined) is blocked from a gate that never listed "anonymous"', () => {
    const w = loadRoleAccess();
    const gates = [{ prefix: 'members-only', allowRoles: ['basic', 'sponsor'] }];
    assert.equal(w.dgeIsRoleGatedPath('members-only/x', null, gates), true);
    assert.equal(w.dgeIsRoleGatedPath('members-only/x', undefined, gates), true);
  });

  test('a gate can explicitly admit anonymous visitors', () => {
    const w = loadRoleAccess();
    const gates = [{ prefix: 'open-to-all', allowRoles: ['anonymous', 'basic'] }];
    assert.equal(w.dgeIsRoleGatedPath('open-to-all/x', 'anonymous', gates), false);
  });

  test('an empty allowRoles list blocks every role', () => {
    const w = loadRoleAccess();
    const gates = [{ prefix: 'locked', allowRoles: [] }];
    assert.equal(w.dgeIsRoleGatedPath('locked/x', 'superadmin', gates), true);
  });
});

describe('inert defaults when accounts are switched off', () => {
  test('dgeLoadRoleAccessConfig resolves to the fixed roles with no gates, no network calls', async () => {
    const w = loadRoleAccess({ authConfig: { enabled: false, roles: ['basic', 'admin'] } });
    await w.dgeLoadRoleAccessConfig();
    assert.deepEqual(plain(w.dgeAllRoleIds()), ['basic', 'admin']);
    assert.deepEqual(plain(w.dgeCurrentRoleGates()), []);
  });

  test('dgeIsHiddenByRoleGate is false for everything when there are no gates', () => {
    const w = loadRoleAccess({ authConfig: { enabled: false, roles: ['basic'] } });
    assert.equal(w.dgeIsHiddenByRoleGate('anything/at/all'), false);
  });
});

describe('preview-as-role — superadmin only', () => {
  test('setting a preview role is refused for a non-superadmin device', () => {
    const w = loadRoleAccess();
    w.dgeSetPreviewRole('basic');
    assert.equal(w.dgeGetPreviewRole(), null);
  });

  test('a superadmin device can set and read a preview role', () => {
    const w = loadRoleAccess();
    w.localStorage.setItem('is_superadmin', 'true');

    w.dgeSetPreviewRole('subscriber');
    assert.equal(w.dgeGetPreviewRole(), 'subscriber');
    w.dgeClearPreviewRole();
    assert.equal(w.dgeGetPreviewRole(), null);
  });
});

// --- The go-live shelf ---------------------------------------------------
//
// A gate closes a path to some roles. The shelf does the opposite and is
// the shape the 17 Sep 2026 launch needs: everything is closed except a
// named handful. The failure that matters is a shelf that accidentally
// opens something -- a whole section going public because a prefix matched
// one character too loosely -- so that is what these check hardest.

describe('dgeMatchShelf — the go-live allow-list', () => {
  const ALLOW = [
    'SarvaMula/kavya/sumadhva_vijaya',
    'SarvaMula/kavya/raghavendra_vijaya',
    'SarvaMula/kavya/tirtha_prabandha'
  ];

  test('no shelf configured -> everything is on it', () => {
    const w = loadRoleAccess();
    assert.equal(w.dgeMatchShelf('anything/at/all', []), true);
    assert.equal(w.dgeMatchShelf('anything/at/all', null), true);
  });

  test('an allowed path itself is on the shelf', () => {
    const w = loadRoleAccess();
    assert.equal(w.dgeMatchShelf('SarvaMula/kavya/sumadhva_vijaya', ALLOW), true);
  });

  test('a descendant of an allowed path is on the shelf', () => {
    // Each sarga has to render, not just the work.
    const w = loadRoleAccess();
    assert.equal(w.dgeMatchShelf('SarvaMula/kavya/sumadhva_vijaya/sarga_1', ALLOW), true);
  });

  test('an ancestor of an allowed path is on the shelf', () => {
    // Otherwise the drawer has no folder to open and the shelf shows nothing.
    const w = loadRoleAccess();
    assert.equal(w.dgeMatchShelf('SarvaMula', ALLOW), true);
    assert.equal(w.dgeMatchShelf('SarvaMula/kavya', ALLOW), true);
  });

  test('a sibling under an allowed ancestor is NOT on the shelf', () => {
    // The whole point: SarvaMula's own granthas stay private while the three
    // kāvyas under it go live.
    const w = loadRoleAccess();
    assert.equal(w.dgeMatchShelf('SarvaMula/sutra_prasthana/anuvyakhyana/mula', ALLOW), false);
    assert.equal(w.dgeMatchShelf('SarvaMula/kavya/something_else', ALLOW), false);
  });

  test('an unrelated section is NOT on the shelf', () => {
    const w = loadRoleAccess();
    ['darshana/vedanta/dvaita/DvaitaVedantaIn',
     'DvaitaVedanta/SarvaMula/mula_granthas/atharvana',
     'vedas/rigveda', 'DvaitaVedanta/Itara/DasaSahitya'].forEach(p => {
      assert.equal(w.dgeMatchShelf(p, ALLOW), false, p);
    });
  });

  test('a path that merely shares a prefix STRING is not on the shelf', () => {
    // 'SarvaMulaX' must not ride in on 'SarvaMula'. This is the bug that
    // would silently publish a section.
    const w = loadRoleAccess();
    assert.equal(w.dgeMatchShelf('SarvaMulaOther/kavya', ALLOW), false);
    assert.equal(w.dgeMatchShelf('SarvaMula/kavya/sumadhva_vijaya_notes', ALLOW), false);
  });
});

describe('dgeIsOffShelf — who the shelf applies to', () => {
  const SHELF = { enabled: true, allow: ['SarvaMula/kavya/sumadhva_vijaya'], openToRoles: [] };

  test('an unconfigured or disabled shelf hides nothing', () => {
    const w = loadRoleAccess();
    w.dgeSetShelfConfig(null);
    assert.equal(w.dgeIsOffShelf('vedas/rigveda'), false);
    w.dgeSetShelfConfig({ enabled: false, allow: ['SarvaMula'] });
    assert.equal(w.dgeIsOffShelf('vedas/rigveda'), false);
    w.dgeSetShelfConfig({ enabled: true, allow: [] });
    assert.equal(w.dgeIsOffShelf('vedas/rigveda'), false);
  });

  test('an ordinary visitor is held to the shelf', () => {
    const w = loadRoleAccess();
    w.dgeSetShelfConfig(SHELF);
    assert.equal(w.dgeIsOffShelf('vedas/rigveda'), true);
    assert.equal(w.dgeIsOffShelf('SarvaMula/kavya/sumadhva_vijaya/sarga_1'), false);
  });

  test('a role named in openToRoles sees the whole library', () => {
    const w = loadRoleAccess();
    w.dgeSetShelfConfig({ enabled: true, allow: ['SarvaMula/kavya/sumadhva_vijaya'], openToRoles: ['scholar'] });
    w.dgeCurrentUserRole = 'scholar';
    assert.equal(w.dgeIsOffShelf('vedas/rigveda'), false);
    w.dgeCurrentUserRole = 'basic';
    assert.equal(w.dgeIsOffShelf('vedas/rigveda'), true);
  });

  test('a previewing superadmin IS held to the shelf', () => {
    // The reason preview exists: an admin has to be able to see the launch
    // exactly as a visitor sees it, shelf included.
    const w = loadRoleAccess();
    w.localStorage.setItem('is_superadmin', 'true');
    w.dgeSetShelfConfig(SHELF);
    w.dgeSetPreviewRole('basic');
    assert.equal(w.dgeIsOffShelf('vedas/rigveda'), true);
    w.dgeClearPreviewRole();
  });
});

// --- Capabilities: what a role may DO ------------------------------------
//
// Gates answer "may this person SEE this path". Capabilities answer "may
// this person copy text". The rule that matters is the default: an
// ungranted capability is CLOSED, which is how copy-guard.js already
// behaved before capabilities existed, so a deployment that never opens
// this panel keeps exactly its old behaviour.

describe('dgeRoleCan — copy and other granted capabilities', () => {
  test('with nothing configured, an ordinary visitor may not', () => {
    const w = loadRoleAccess();
    assert.equal(w.dgeRoleCan('copy'), false);
  });

  test('an admin device may, configured or not', () => {
    const w = loadRoleAccess();
    w.localStorage.setItem('acharyaAuthorized', 'true');
    assert.equal(w.dgeRoleCan('copy'), true);
  });

  test('a previewing superadmin is held to the previewed role', () => {
    const w = loadRoleAccess();
    w.localStorage.setItem('is_superadmin', 'true');
    assert.equal(w.dgeRoleCan('copy'), true);
    w.dgeSetPreviewRole('basic');
    assert.equal(w.dgeRoleCan('copy'), false, 'preview must not keep the admin bypass');
    w.dgeClearPreviewRole();
  });

  test('a capability is unknown until the config names it', () => {
    const w = loadRoleAccess();
    assert.deepEqual(plain(w.dgeRoleCapabilityRoles('copy')), []);
    assert.deepEqual(plain(w.dgeAllCapabilities()), {});
  });
});
