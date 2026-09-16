// Tests for the workflow buttons' allowlist and input handling.
//
// Weighted towards refusal. This module decides what a browser is allowed
// to make a token in a Cloud Function do to a GitHub repository, so the
// cases that matter are the ones where the answer is no: a workflow that is
// not on the list, an input that was not declared, a role that is not high
// enough for a job that republishes text people read.
'use strict';

const { test, describe } = require('node:test');
const assert = require('node:assert/strict');

const wf = require('../functions/lib/workflows-core');

function throwsWith(code, fn) {
  assert.throws(fn, (e) => e instanceof wf.WorkflowError && e.code === code);
}

describe('the catalogue', () => {
  test('lists exactly the workflows the panel offers', () => {
    assert.deepEqual(wf.catalogue().map((w) => w.id).sort(), [
      'check-sources', 'dhatu-lexicon', 'extract-setutila', 'import-advaitasharada',
      'import-anandamakaranda', 'import-ashtadhyayi', 'import-dasa-sahitya',
      'import-kavya', 'import-meghamala', 'kavya-tracker', 'ocr-review-merge', 'ocr-sarvam', 'publish-wordnet', 'reindex',
      'sync-advaitasharada', 'sync-anandamakaranda', 'sync-ashtadhyayi',
      'sync-dasa-sahitya', 'sync-dvaitavedanta', 'sync-dvaitavedanta-quick',
      'sync-kavya', 'sync-sarvamulavani', 'sync-setutila', 'sync-srivaishnavan'
    ]);
  });

  test('every source-sync card runs check-sources.yml with a fixed `only`', () => {
    for (const w of wf.catalogue().filter((x) => x.group === 'source-sync' && x.id.startsWith('sync-') && x.id !== 'sync-dvaitavedanta')) {
      assert.equal(w.file, 'check-sources.yml', w.id);
      const only = w.inputs.find((i) => i.name === 'only');
      assert.ok(only && only.fixed && only.default, w.id + ' must pin its source ids');
      assert.deepEqual(only.default.split(','), w.source_ids, w.id);
    }
  });

  test('a shared file reports its newest run under every card that runs it', () => {
    const out = wf.latestRuns({ workflow_runs: [
      { id: 1, path: '.github/workflows/check-sources.yml', status: 'completed', conclusion: 'success', created_at: '2026-09-09T05:00:00Z', html_url: 'u' }
    ] });
    assert.equal(out['check-sources'].id, 1);
    assert.equal(out['sync-setutila'].id, 1);
    assert.equal(out['sync-kavya'].id, 1);
  });

  test('names a real workflow file for each', () => {
    for (const w of wf.catalogue()) assert.match(w.file, /^[a-z-]+\.yml$/);
  });

  test('is a copy, so a caller cannot edit the list it was given', () => {
    const first = wf.catalogue();
    first[0].inputs.push({ name: 'evil', type: 'string' });
    assert.equal(wf.catalogue()[0].inputs.some((i) => i.name === 'evil'), false);
  });

  test('runs everything from main, never from a caller-named ref', () => {
    assert.equal(wf.REF, 'main');
  });
});

describe('findWorkflow', () => {
  test('finds one by id', () => {
    assert.equal(wf.findWorkflow('reindex').file, 'reindex.yml');
  });

  test('refuses a workflow file that exists but is not on the list', () => {
    assert.equal(wf.findWorkflow('ingest.yml'), null);
    assert.equal(wf.findWorkflow('darshanas'), null);
  });

  test('refuses path tricks', () => {
    assert.equal(wf.findWorkflow('../../../etc/passwd'), null);
    assert.equal(wf.findWorkflow(''), null);
  });
});

describe('assertRole', () => {
  test('a corpus-rewriting job needs a superadmin', () => {
    const kavya = wf.findWorkflow('import-kavya');
    assert.equal(wf.minRoleFor(kavya), 'superadmin');
    throwsWith('permission-denied', () => wf.assertRole('admin', 'superadmin'));
    wf.assertRole('superadmin', 'superadmin');
  });

  test('a reporting job is open to either admin tier', () => {
    assert.equal(wf.minRoleFor(wf.findWorkflow('check-sources')), 'admin');
    wf.assertRole('admin', 'admin');
    wf.assertRole('superadmin', 'admin');
  });

  test('a basic account runs nothing', () => {
    throwsWith('permission-denied', () => wf.assertRole('basic', 'admin'));
  });

  test('a role this code has never heard of ranks lowest, not highest', () => {
    throwsWith('permission-denied', () => wf.assertRole('owner', 'admin'));
    throwsWith('permission-denied', () => wf.assertRole(undefined, 'admin'));
  });
});

describe('buildInputs', () => {
  const check = wf.findWorkflow('check-sources');
  const reindex = wf.findWorkflow('reindex');

  test('fills in every declared default when nothing is sent', () => {
    assert.deepEqual(wf.buildInputs(check, undefined), { only: '', remember: 'true' });
  });

  test('sends booleans as strings, which is what the REST API takes', () => {
    const out = wf.buildInputs(reindex, { open_pr: false, commentaries: true });
    assert.deepEqual(out, { open_pr: 'false', include_kavya: 'true', commentaries: 'true' });
    for (const v of Object.values(out)) assert.equal(typeof v, 'string');
  });

  test('accepts the strings a form sends for a checkbox', () => {
    assert.equal(wf.buildInputs(reindex, { open_pr: 'false' }).open_pr, 'false');
    assert.equal(wf.buildInputs(reindex, { open_pr: 'yes' }).open_pr, 'true');
  });

  test('refuses a boolean that is neither', () => {
    throwsWith('invalid-argument', () => wf.buildInputs(reindex, { open_pr: 'maybe' }));
  });

  test('refuses an input the workflow does not declare', () => {
    throwsWith('invalid-argument', () => wf.buildInputs(check, { only: 'gretil', ref: 'attacker-branch' }));
  });

  test('refuses a required input left blank', () => {
    throwsWith('invalid-argument', () => wf.buildInputs(wf.findWorkflow('import-kavya'), { works: '  ' }));
  });

  test('refuses shell metacharacters and newlines in a free-text input', () => {
    for (const bad of ['gretil; rm -rf /', 'a\nb', '$(whoami)', 'a`b`', "a'b"]) {
      throwsWith('invalid-argument', () => wf.buildInputs(check, { only: bad }));
    }
  });

  test('refuses an absurdly long value', () => {
    throwsWith('invalid-argument', () => wf.buildInputs(check, { only: 'a'.repeat(201) }));
  });

  test('accepts an ordinary comma-separated id list', () => {
    assert.equal(wf.buildInputs(check, { only: 'gretil,ambuda, sa-wikisource' }).only, 'gretil,ambuda, sa-wikisource');
  });

  test('probing, not importing, is what the Kāvya button does by default', () => {
    assert.equal(wf.buildInputs(wf.findWorkflow('import-kavya'), {}).probe_only, 'true');
  });
});

describe('checkCooldown', () => {
  const NOW = 1_000_000_000_000;

  test('allows a first dispatch', () => {
    wf.checkCooldown(null, NOW);
  });

  test('refuses a second one seconds later — a double click must not open two PRs', () => {
    throwsWith('resource-exhausted', () => wf.checkCooldown(NOW - 2000, NOW));
  });

  test('allows one after the cooldown', () => {
    wf.checkCooldown(NOW - wf.COOLDOWN_MS - 1, NOW);
  });

  test('ignores a timestamp from the future rather than locking the button', () => {
    wf.checkCooldown(NOW + 60_000, NOW);
  });
});

describe('latestRuns', () => {
  const run = (path, over = {}) => Object.assign({
    id: 1, path: `.github/workflows/${path}`, status: 'completed', conclusion: 'success',
    created_at: '2026-08-19T10:00:00Z', html_url: 'https://github.com/x/y/actions/runs/1',
    triggering_actor: { login: 'someone' }
  }, over);

  test('keeps the newest run of each known workflow', () => {
    const out = wf.latestRuns({ workflow_runs: [
      run('reindex.yml', { id: 1, created_at: '2026-08-01T00:00:00Z' }),
      run('reindex.yml', { id: 2, created_at: '2026-08-19T00:00:00Z' }),
      run('check-sources.yml', { id: 3 })
    ] });
    assert.equal(out.reindex.id, 2);
    assert.equal(out['check-sources'].id, 3);
  });

  test('picks by date, not by the order GitHub happened to return', () => {
    const out = wf.latestRuns({ workflow_runs: [
      run('reindex.yml', { id: 9, created_at: '2026-08-19T00:00:00Z' }),
      run('reindex.yml', { id: 8, created_at: '2026-08-01T00:00:00Z' })
    ] });
    assert.equal(out.reindex.id, 9);
  });

  test('ignores runs of workflows the panel does not offer', () => {
    assert.deepEqual(wf.latestRuns({ workflow_runs: [run('ingest.yml')] }), {});
  });

  test('survives a payload with nothing in it', () => {
    assert.deepEqual(wf.latestRuns(null), {});
    assert.deepEqual(wf.latestRuns({}), {});
    assert.deepEqual(wf.latestRuns({ workflow_runs: 'not an array' }), {});
  });

  test('reports an in-flight run as running, with no conclusion', () => {
    const out = wf.latestRuns({ workflow_runs: [run('kavya-tracker.yml', { status: 'in_progress', conclusion: null })] });
    assert.equal(out['kavya-tracker'].status, 'in_progress');
    assert.equal(out['kavya-tracker'].conclusion, null);
  });
});
