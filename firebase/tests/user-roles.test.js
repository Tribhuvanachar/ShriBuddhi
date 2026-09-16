// Tests for js/user-roles.js's paste parser — the "Excel sheet" half of
// the lead's ask: export the user list, edit the role column in a
// spreadsheet, paste the column back.
//
// Only dgeParseRolePaste is exercised, because it is the only part that can
// be wrong on its own: everything else in that file is a Firestore write.
// What it has to survive is real clipboard content — a spreadsheet copy
// arrives tab-separated and usually carries the header row this tool itself
// exported, a hand-typed list arrives comma-separated, and either may hold
// columns (a display name, the OLD role, a timestamp) that must be ignored
// rather than mistaken for the answer.
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test, describe } = require('node:test');
const assert = require('node:assert/strict');

const USER_ROLES_JS = path.resolve(__dirname, '../../js/user-roles.js');

function loadUserRoles() {
  const windowObj = { DGE_VERSIONS: {}, AUTH_CONFIG: { enabled: true, roles: ['basic'] } };
  const sandbox = {
    window: windowObj,
    document: { createElement: () => ({ set textContent(v) { this.innerHTML = String(v); }, innerHTML: '' }) },
    console: { log() {}, error() {}, warn() {} },
    localStorage: { getItem: () => null, setItem() {}, removeItem() {} },
    Promise, URL, Blob: function () {}, TextEncoder
  };
  const context = vm.createContext(sandbox);
  vm.runInContext('var window = this.window;', context);
  vm.runInContext(fs.readFileSync(USER_ROLES_JS, 'utf8'), context, { filename: 'user-roles.js' });
  return windowObj;
}

// The arrays the script builds come from the VM CONTEXT's own Array, which
// node:assert treats as a different value from this file's — the same realm
// mismatch role-access.test.js documents. Round-trip through JSON first.
const plain = (v) => JSON.parse(JSON.stringify(v));

const ROLES = ['basic', 'subscriber', 'sponsor', 'scholar', 'admin', 'superadmin'];

describe('dgeParseRolePaste — header mode (the download-edit-upload round trip)', () => {
  test('columns are read by NAME, so a name and a role both apply', () => {
    const w = loadUserRoles();
    const rows = w.dgeParseRolePaste(
      'email,displayName,role,phone,lastLogin\n' +
      '"ravi@example.com","Ravi Kumar","scholar","","2026-09-10"\n', ROLES);
    assert.equal(rows.length, 1);
    assert.deepEqual(plain([rows[0].email, rows[0].name, rows[0].role]),
      ['ravi@example.com', 'Ravi Kumar', 'scholar']);
  });

  test('column ORDER does not matter', () => {
    const w = loadUserRoles();
    const rows = w.dgeParseRolePaste('role,email,displayName\nsponsor,sita@example.com,Sita', ROLES);
    assert.deepEqual(plain([rows[0].email, rows[0].name, rows[0].role]),
      ['sita@example.com', 'Sita', 'sponsor']);
  });

  test('a quoted name containing a comma survives the round trip', () => {
    // The reason CSV parsing is real rather than a .split(',').
    const w = loadUserRoles();
    const rows = w.dgeParseRolePaste('email,displayName,role\n"a@b.com","Rao, K. V.",scholar', ROLES);
    assert.equal(rows[0].name, 'Rao, K. V.');
  });

  test('a doubled quote inside a name is unescaped', () => {
    const w = loadUserRoles();
    const rows = w.dgeParseRolePaste('email,displayName\n"a@b.com","He said ""hi"""', ROLES);
    assert.equal(rows[0].name, 'He said "hi"');
  });

  test('a tab-separated sheet is read the same way', () => {
    const w = loadUserRoles();
    const rows = w.dgeParseRolePaste('email\tdisplayName\trole\nravi@example.com\tRavi\tscholar', ROLES);
    assert.deepEqual(plain([rows[0].email, rows[0].name, rows[0].role]), ['ravi@example.com', 'Ravi', 'scholar']);
  });

  test('an unknown role in the role column is reported, never applied', () => {
    const w = loadUserRoles();
    const rows = w.dgeParseRolePaste('email,role\nravi@example.com,archivist', ROLES);
    assert.equal(rows[0].role, null, 'a typo must surface as a failed row, not a silent write');
    assert.equal(rows[0].email, 'ravi@example.com');
  });

  test('an EMPTY role cell means "leave the role alone", not "clear it"', () => {
    // Someone editing only the name column must not wipe everyone's role.
    const w = loadUserRoles();
    const rows = w.dgeParseRolePaste('email,displayName,role\nravi@example.com,Ravi,', ROLES);
    assert.equal(rows[0].role, null);
    assert.equal(rows[0].name, 'Ravi');
  });

  test('the header row itself is never treated as a person', () => {
    const w = loadUserRoles();
    const rows = w.dgeParseRolePaste('email,displayName,role\nravi@example.com,Ravi,scholar', ROLES);
    assert.equal(rows.length, 1);
  });

  test('roles and emails are lowercased so a spreadsheet’s capitals still match', () => {
    const w = loadUserRoles();
    const rows = w.dgeParseRolePaste('Email,Role\nRavi@Example.COM,Scholar', ROLES);
    assert.deepEqual(plain([rows[0].email, rows[0].role]), ['ravi@example.com', 'scholar']);
  });
});

describe('dgeParseRolePaste — loose mode (a list somebody typed)', () => {
  test('email is matched by shape, not by column position', () => {
    const w = loadUserRoles();
    const rows = w.dgeParseRolePaste('scholar\tRavi\travi@example.com', ROLES);
    assert.deepEqual(plain([rows[0].email, rows[0].role]), ['ravi@example.com', 'scholar']);
  });

  test('a comma-separated hand-typed list works', () => {
    const w = loadUserRoles();
    const rows = w.dgeParseRolePaste('ravi@example.com, scholar', ROLES);
    assert.deepEqual(plain([rows[0].email, rows[0].role]), ['ravi@example.com', 'scholar']);
  });

  test('a trailing date column is not mistaken for the role', () => {
    const w = loadUserRoles();
    const rows = w.dgeParseRolePaste('ravi@example.com\tRavi\tscholar\t\t2026-09-10', ROLES);
    assert.equal(rows[0].role, 'scholar');
  });

  test('the rightmost known role wins, so an edited column beats the old one', () => {
    const w = loadUserRoles();
    const rows = w.dgeParseRolePaste('ravi@example.com\tRavi\tbasic\tscholar', ROLES);
    assert.equal(rows[0].role, 'scholar');
  });

  test('NO name is inferred without a header', () => {
    // Guessing which unlabelled cell is a person's name would overwrite real
    // data with a confident wrong answer.
    const w = loadUserRoles();
    const rows = w.dgeParseRolePaste('ravi@example.com\tRavi\tscholar', ROLES);
    assert.equal(rows[0].name, null);
  });

  test('blank lines and stray whitespace are skipped', () => {
    const w = loadUserRoles();
    assert.equal(w.dgeParseRolePaste('\n  \nravi@example.com\tscholar\n\n', ROLES).length, 1);
  });

  test('line numbers are kept so a failed row can be pointed at', () => {
    const w = loadUserRoles();
    const rows = w.dgeParseRolePaste('email,role\nravi@example.com,scholar', ROLES);
    assert.equal(rows[0].line, 2);
  });

  test('nothing at all parses to nothing', () => {
    const w = loadUserRoles();
    assert.equal(w.dgeParseRolePaste('', ROLES).length, 0);
    assert.equal(w.dgeParseRolePaste(null, ROLES).length, 0);
  });
});
