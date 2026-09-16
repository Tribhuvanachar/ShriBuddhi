// Tests for dgeAdminMoveTreeEntries in js/admin-editor.js — the planner
// behind a one-commit move in the Repo Files admin.
//
// This function decides which blobs land where and which moves are refused.
// It is the whole correctness of the operation, so it is exercised directly
// rather than through a GitHub round trip.
//
// The case that matters most is test_blob_shas_are_reused: a git move must
// never fetch or upload content. If an entry ever carried anything but the
// ORIGINAL blob's sha, the move would be re-uploading files — which is
// exactly the slowness this replaced.
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test, describe } = require('node:test');
const assert = require('node:assert/strict');

function loadPlanner() {
  const windowObj = {};
  const sandbox = { window: windowObj, console, document: { addEventListener() {} }, localStorage: null };
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  // Only the one function is needed; running the whole file would drag in a
  // browser's worth of globals for no gain.
  const src = fs.readFileSync(path.resolve(__dirname, '../../js/admin-editor.js'), 'utf8');
  const start = src.indexOf('window.dgeAdminMoveTreeEntries = function');
  const end = src.indexOf('\n};', start) + 3;
  assert.ok(start > 0 && end > start, 'dgeAdminMoveTreeEntries not found');
  vm.runInContext(src.slice(start, end), sandbox);
  return windowObj.dgeAdminMoveTreeEntries;
}

const plan = loadPlanner();

const TREE = [
  { type: 'blob', path: 'a/one.json', sha: 'sha1', mode: '100644' },
  { type: 'blob', path: 'a/deep/two.json', sha: 'sha2', mode: '100644' },
  { type: 'blob', path: 'a/run.sh', sha: 'sha3', mode: '100755' },
  { type: 'blob', path: 'ab/other.json', sha: 'sha4', mode: '100644' },
  { type: 'blob', path: 'b/keep.json', sha: 'sha5', mode: '100644' },
];

function byPath(entries) {
  const m = {};
  entries.forEach(e => { (m[e.path] = m[e.path] || []).push(e); });
  return m;
}

describe('a folder move', () => {
  test('every descendant is re-pointed and the old path cleared', () => {
    const r = plan(TREE, 'a', 'z');
    assert.equal(r.blocked.length, 0);
    assert.equal(r.moved, 3);
    const m = byPath(r.entries);
    assert.equal(m['z/one.json'][0].sha, 'sha1');
    assert.equal(m['z/deep/two.json'][0].sha, 'sha2');
    assert.equal(m['a/one.json'][0].sha, null);
    assert.equal(m['a/deep/two.json'][0].sha, null);
  });

  test('blob shas are reused — a move never re-uploads content', () => {
    const r = plan(TREE, 'a', 'z');
    const created = r.entries.filter(e => e.sha !== null);
    assert.equal(created.map(e => e.sha).sort().join(','), 'sha1,sha2,sha3');
    created.forEach(e => assert.ok(!('content' in e), 'no entry may carry content'));
  });

  test('the file mode is carried over, not assumed', () => {
    // An executable that came back as 100644 would be quietly broken.
    const r = plan(TREE, 'a', 'z');
    assert.equal(byPath(r.entries)['z/run.sh'][0].mode, '100755');
  });

  test('a sibling whose name merely starts the same is left alone', () => {
    // 'ab/other.json' starts with 'a' — a naive startsWith would drag it in.
    const r = plan(TREE, 'a', 'z');
    const touched = r.entries.map(e => e.path);
    assert.ok(!touched.some(p => p.startsWith('ab/')), touched.join(','));
    assert.ok(!touched.includes('b/keep.json'));
  });

  test('a single file moves by the same path', () => {
    const r = plan(TREE, 'b/keep.json', 'c/kept.json');
    assert.equal(r.moved, 1);
    const m = byPath(r.entries);
    assert.equal(m['c/kept.json'][0].sha, 'sha5');
    assert.equal(m['b/keep.json'][0].sha, null);
  });

  test('a deep rename keeps the structure under it', () => {
    const r = plan(TREE, 'a/deep', 'a/shallow');
    assert.equal(r.moved, 1);
    assert.equal(byPath(r.entries)['a/shallow/two.json'][0].sha, 'sha2');
  });
});

describe('what it refuses', () => {
  test('a source with nothing under it', () => {
    assert.match(plan(TREE, 'nowhere', 'z').blocked[0], /nothing at/);
  });

  test('moving a folder into itself', () => {
    // Would build a tree containing its own parent and lose the rest.
    assert.match(plan(TREE, 'a', 'a/inner').blocked[0], /inside itself/);
  });

  test('a no-op move', () => {
    assert.match(plan(TREE, 'a', 'a').blocked[0], /same path/);
  });

  test('a destination that already holds a file', () => {
    const r = plan(TREE, 'b/keep.json', 'a/one.json');
    assert.match(r.blocked[0], /already exists/);
  });

  test('a submodule, which has no blob to re-point', () => {
    const withSub = TREE.concat([{ type: 'commit', path: 'a/vendor', sha: 'subsha' }]);
    assert.match(plan(withSub, 'a', 'z').blocked[0], /submodule/);
  });

  test('an empty or missing tree does not throw', () => {
    assert.ok(plan([], 'a', 'z').blocked.length);
    assert.ok(plan(null, 'a', 'z').blocked.length);
  });
});

describe('the shape the GitHub API needs', () => {
  test('two entries per moved file: the new path and the cleared old one', () => {
    const r = plan(TREE, 'a', 'z');
    assert.equal(r.entries.length, r.moved * 2);
  });

  test('every entry is a well-formed tree entry', () => {
    plan(TREE, 'a', 'z').entries.forEach(e => {
      assert.equal(e.type, 'blob');
      assert.match(e.mode, /^\d{6}$/);
      assert.equal(typeof e.path, 'string');
      assert.ok(e.sha === null || typeof e.sha === 'string');
    });
  });

  test('a 177-file move is still one tree, not 177 requests', () => {
    // The rename that prompted this: 177 files, ~531 API calls and ~354
    // commits before; one tree and one commit now.
    const big = [];
    for (let i = 0; i < 177; i++) {
      big.push({ type: 'blob', path: `src/f${i}/data.json`, sha: 's' + i, mode: '100644' });
    }
    const r = plan(big, 'src', 'dst');
    assert.equal(r.moved, 177);
    assert.equal(r.entries.length, 354);
    assert.equal(r.blocked.length, 0);
  });
});
