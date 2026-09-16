// Tests for js/corpus-fetch.js — the client half of the corpus switch.
//
// Two things can go wrong here and only one of them is loud. The loud one is
// the proxy path fetching a URL the function does not recognise. The quiet
// one is the switch failing to be a switch: corpusBase unset must produce
// byte-for-byte the request the reader made before this file existed, or
// "flip it back" is not a rollback. Both are asserted below against a fake
// fetch that records what it was called with.
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test, describe } = require('node:test');
const assert = require('node:assert/strict');

const SRC = path.resolve(__dirname, '../../js/corpus-fetch.js');

function load({ corpusBase, kavyaBase, authEnabled = false, token = null } = {}) {
  const calls = [];
  const sandbox = {
    console,
    Headers: globalThis.Headers,
    URL: globalThis.URL,
    fetch: (url, init) => { calls.push({ url, init }); return Promise.resolve({ ok: true, url }); }
  };
  sandbox.window = {
    appConfig: corpusBase === undefined ? {} : { corpusBase },
    KAVYA_DATA_BASE: kavyaBase || '',
    AUTH_CONFIG: { enabled: authEnabled },
    DGE_VERSIONS: {}
  };
  if (token) {
    sandbox.firebase = {
      apps: [{}],
      auth: () => ({ currentUser: { getIdToken: async () => token } })
    };
    sandbox.window.dgeEnsureFirebaseSdk = async () => {};
  }
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync(SRC, 'utf8'), sandbox);
  return { w: sandbox.window, calls };
}

describe('the switch itself', () => {
  test('unset corpusBase means the proxy is off', () => {
    assert.equal(load().w.dgeCorpusProxyOn(), false);
    assert.equal(load({ corpusBase: '' }).w.dgeCorpusProxyOn(), false);
    assert.equal(load({ corpusBase: '   ' }).w.dgeCorpusProxyOn(), false);
  });

  test('a set corpusBase turns it on', () => {
    assert.equal(load({ corpusBase: 'https://x/corpusFile' }).w.dgeCorpusProxyOn(), true);
  });

  test('off, the request is exactly what the reader made before — same URL, same cache-buster', async () => {
    const { w, calls } = load();
    await w.dgeFetchCorpus('data/DvaitaVedanta/Itara/Kavya/sumadhva_vijaya/data.json');
    assert.equal(calls.length, 1);
    assert.match(calls[0].url, /^data\/DvaitaVedanta\/Itara\/Kavya\/sumadhva_vijaya\/data\.json\?t=\d+$/);
    assert.deepEqual(Object.keys(calls[0].init), [], 'no init options beyond the URL');
  });

  test('off, a URL that already has a query gets & rather than a second ?', async () => {
    const { w, calls } = load();
    await w.dgeFetchCorpus('data/x/data.json?v=2');
    assert.match(calls[0].url, /^data\/x\/data\.json\?v=2&t=\d+$/);
  });

  test('off with bust:false, nothing is appended at all', async () => {
    const { w, calls } = load();
    await w.dgeFetchCorpus('data/x/data.json', { bust: false });
    assert.equal(calls[0].url, 'data/x/data.json');
  });

  test('on, the request goes to the proxy with no cache-buster (the ETag does that job)', async () => {
    const { w, calls } = load({ corpusBase: 'https://asia-south1-p.cloudfunctions.net/corpusFile' });
    await w.dgeFetchCorpus('data/DvaitaVedanta/Itara/Kavya/sumadhva_vijaya/data.json');
    assert.equal(calls[0].url,
      'https://asia-south1-p.cloudfunctions.net/corpusFile/DvaitaVedanta/Itara/Kavya/sumadhva_vijaya/data.json');
    assert.ok(!/[?&]t=/.test(calls[0].url));
  });

  test('a trailing slash on corpusBase does not become a double slash', async () => {
    const { w, calls } = load({ corpusBase: 'https://x/corpusFile//' });
    await w.dgeFetchCorpus('data/a/data.json');
    assert.equal(calls[0].url, 'https://x/corpusFile/a/data.json');
  });
});

describe('the token', () => {
  test('signed out, no Authorization header — the public library still loads', async () => {
    const { w, calls } = load({ corpusBase: 'https://x/corpusFile', authEnabled: true });
    await w.dgeFetchCorpus('data/a/data.json');
    assert.equal(calls[0].init.headers.get('Authorization'), null);
  });

  test('accounts switched off entirely, no header and no wait on an SDK that is not there', async () => {
    const { w, calls } = load({ corpusBase: 'https://x/corpusFile', authEnabled: false, token: 'tok' });
    await w.dgeFetchCorpus('data/a/data.json');
    assert.equal(calls[0].init.headers.get('Authorization'), null);
  });

  test('signed in, the ID token rides along', async () => {
    const { w, calls } = load({ corpusBase: 'https://x/corpusFile', authEnabled: true, token: 'tok-123' });
    await w.dgeFetchCorpus('data/a/data.json');
    assert.equal(calls[0].init.headers.get('Authorization'), 'Bearer tok-123');
  });
});

describe('dgeCorpusObjectPath — every shape the reader holds must land on one string', () => {
  const cases = [
    ['data/DvaitaVedanta/Itara/Kavya/sumadhva_vijaya/data.json', 'DvaitaVedanta/Itara/Kavya/sumadhva_vijaya/data.json'],
    ['data/DvaitaVedanta/Itara/Kavya/sumadhva_vijaya/data.json', 'DvaitaVedanta/Itara/Kavya/sumadhva_vijaya/data.json'],
    ['/data/upanishad/isha/data.json', 'upanishad/isha/data.json'],
    ['data/x/data.json?t=123', 'x/data.json'],
    ['data/x/data.json#frag', 'x/data.json']
  ];
  for (const [input, want] of cases) {
    test(JSON.stringify(input) + ' → ' + want, () => {
      assert.equal(load().w.dgeCorpusObjectPath(input), want);
    });
  }

  test('a kavyaDataBase CDN URL comes back to the same on-disk path', () => {
    const base = 'https://cdn.jsdelivr.net/gh/Owner/repo@abc123';
    const { w } = load({ kavyaBase: base });
    assert.equal(w.dgeCorpusObjectPath(base + '/data/kavya_alankara/tirtha_prabandha/data.json'),
      'kavya_alankara/tirtha_prabandha/data.json');
  });

  test('a CDN URL still resolves even when KAVYA_DATA_BASE is not the one it was built from', () => {
    // The commit pin in kavyaDataBase moves; a URL minted before a re-pin
    // must not stop resolving just because the prefix no longer matches.
    const { w } = load({ kavyaBase: 'https://cdn.jsdelivr.net/gh/Owner/repo@NEWSHA' });
    assert.equal(
      w.dgeCorpusObjectPath('https://cdn.jsdelivr.net/gh/Owner/repo@OLDSHA/data/kavya_alankara/x/data.json'),
      'kavya_alankara/x/data.json');
  });

  test('nothing in, nothing out — and dgeFetchCorpus refuses rather than fetching a junk URL', async () => {
    const { w, calls } = load({ corpusBase: 'https://x/corpusFile' });
    assert.equal(w.dgeCorpusObjectPath(''), '');
    assert.equal(w.dgeCorpusObjectPath(null), '');
    await assert.rejects(() => w.dgeFetchCorpus(''), /Not a corpus path/);
    assert.equal(calls.length, 0);
  });
});

describe('dgeCorpusObjectPath — "data/" is a segment, not a substring', () => {
  // The CDN form is …/gh/owner/repo@sha/data/x/y/data.json, so the derivation
  // keeps everything from "data/" on. Doing that by substring would truncate
  // any real folder whose name ENDS in "data" — and metadata/ is a plausible
  // folder name, which would quietly send the proxy after a different text.
  const w = () => {
    const fs = require('node:fs'), vm = require('node:vm');
    const sandbox = { console, Headers: globalThis.Headers, URL: globalThis.URL, fetch: () => {} };
    sandbox.window = { appConfig: {}, KAVYA_DATA_BASE: '', AUTH_CONFIG: { enabled: false }, DGE_VERSIONS: {} };
    sandbox.globalThis = sandbox;
    vm.createContext(sandbox);
    vm.runInContext(fs.readFileSync(require('node:path')
      .resolve(__dirname, '../../js/corpus-fetch.js'), 'utf8'), sandbox);
    return sandbox.window;
  };

  test('a folder ending in "data" is not mistaken for the corpus root', () => {
    assert.equal(w().dgeCorpusObjectPath('data/purana/metadata/x/data.json'), 'purana/metadata/x/data.json');
    assert.equal(w().dgeCorpusObjectPath('data/smriti/devadatta/data.json'), 'smriti/devadatta/data.json');
  });

  test('a CDN path with a data/ segment is cut at that segment', () => {
    assert.equal(
      w().dgeCorpusObjectPath('https://cdn.jsdelivr.net/gh/O/r@sha/data/upanishad/isha/data.json'),
      'upanishad/isha/data.json');
  });

  test('a CDN path with NO data/ segment keeps its whole path', () => {
    // kavyaDataBase points at a branch whose layout has no data/ level.
    assert.equal(
      w().dgeCorpusObjectPath('https://cdn.jsdelivr.net/gh/O/r@sha/DvaitaVedanta/Itara/Kavya/sumadhva_vijaya/sarga_01/data.json'),
      'DvaitaVedanta/Itara/Kavya/sumadhva_vijaya/sarga_01/data.json');
  });

  test('the FIRST data/ segment wins, so a grantha called data/ below it survives', () => {
    assert.equal(w().dgeCorpusObjectPath('data/a/data/b/data.json'), 'a/data/b/data.json');
  });
});
