/*
 * test-genie-asr-recorder-e2e.js — headless Playwright exercise of
 * admin/genie-asr-recorder.html against a real (fake-device) audio stream.
 *
 * Covers what the Node unit tests in this same directory structurally
 * cannot: the DOM/IndexedDB/getUserMedia half of the page. Uses Chromium's
 * --use-fake-device-for-media-stream, which emits a real (non-silent,
 * synthetic-tone) audio stream, so this verifies actual WAV bytes come out
 * of record -> stop -> encode, not just that the UI looks right.
 *
 * Every GitHub API call is intercepted (page.route) — this test never
 * touches the real genie-asr-audio-seed branch. That's deliberate: pushing
 * synthetic test audio to the real benchmark branch would pollute real
 * data. See this file's own comments for what's verified about the push
 * request shape, and see the manual verification note in this tool's PR
 * description for what to check by hand against the real branch instead.
 *
 *   NODE_PATH=/opt/node22/lib/node_modules node tools/genie_asr_recorder/test-genie-asr-recorder-e2e.js
 */
'use strict';
const { chromium } = require('playwright');
const path = require('path');
const http = require('http');
const fs = require('fs');

const ROOT = path.join(__dirname, '../..');
const PORT = 8934;

const MIME = { '.html': 'text/html', '.js': 'application/javascript', '.json': 'application/json',
  '.css': 'text/css', '.wav': 'audio/wav', '.md': 'text/plain' };

function serveStatic() {
  const server = http.createServer((req, res) => {
    const urlPath = decodeURIComponent(req.url.split('?')[0]);
    const filePath = path.join(ROOT, urlPath);
    fs.readFile(filePath, (err, data) => {
      if (err) { res.writeHead(404); res.end('not found: ' + urlPath); return; }
      res.writeHead(200, { 'Content-Type': MIME[path.extname(filePath)] || 'application/octet-stream' });
      res.end(data);
    });
  });
  return new Promise((resolve) => server.listen(PORT, '127.0.0.1', () => resolve(server)));
}

let failures = 0;
function check(name, cond, detail) {
  if (cond) console.log('  ok — ' + name);
  else { failures++; console.error('  FAIL — ' + name + (detail ? '\n    ' + detail : '')); }
}

(async () => {
  const server = await serveStatic();
  const browser = await chromium.launch({
    args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream']
  });
  const page = await browser.newPage();
  page.on('dialog', (d) => d.accept());

  // Fake GitHub API entirely — this test must never reach the real repo/branch.
  const pushedRequests = [];
  await page.route('https://api.github.com/**', async (route) => {
    const req = route.request();
    if (req.method() === 'GET' && req.url().includes('/git/trees/genie-asr-audio-seed')) {
      // Mirrors the REAL genie-asr-audio-seed tree as of this test being
      // written (verified with `git ls-tree -r origin/genie-asr-audio-seed`):
      // 62 of 76 items present under the <category>/<id>.wav convention —
      // every item in categories 01-13 except 01_english_002/003, which the
      // real branch holds under non-conventional filenames instead
      // (sumadhwa_test.wav / sumadhwa_16k.m4a) and so don't count as
      // present by this page's (deliberately strict, path-exact) check.
      const NOT_YET_UNDER_CONVENTION = ['01_english_002', '01_english_003'];
      const manifest = JSON.parse(fs.readFileSync(path.join(ROOT, 'genie_asr_benchmark/manifests/manifest.json'), 'utf8'));
      const tree = manifest
        .filter((m) => !m.category.match(/^1[456]_/) && !NOT_YET_UNDER_CONVENTION.includes(m.id))
        .map((m) => ({ path: 'genie_asr_benchmark/audio/' + m.category + '/' + m.id + '.wav', type: 'blob', sha: 'fakesha_' + m.id, size: 1000 }));
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ tree: tree }) });
      return;
    }
    if (req.method() === 'PUT' && req.url().includes('/contents/')) {
      pushedRequests.push({ url: req.url(), method: req.method(), headers: req.headers(), body: JSON.parse(req.postData()) });
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ content: { sha: 'newfakesha' } }) });
      return;
    }
    route.continue();
  });

  console.log('Gate behavior');
  // Pre-seed the vandana pass flag so vandana-guard.js (unrelated to this
  // tool) doesn't bounce a fresh navigation back to the site root.
  await page.addInitScript(() => sessionStorage.setItem('dge_vandana_passed', '1'));
  await page.goto('http://127.0.0.1:' + PORT + '/admin/genie-asr-recorder.html');

  check('gate is visible before any key is entered', await page.locator('#gate').isVisible());
  check('app is hidden before the gate is passed', !(await page.locator('#main').isVisible()));

  await page.fill('#gk', 'wrongkey');
  await page.click('#gbtn');
  await page.waitForTimeout(300);
  check('wrong key is rejected (placeholder updates, gate stays up)',
    (await page.locator('#gk').getAttribute('placeholder')) === 'wrong — try again' && await page.locator('#gate').isVisible());

  await page.fill('#gk', 'genieasr'); // keys are compared case-insensitively, trimmed
  await page.click('#gbtn');
  await page.waitForLoadState('load'); // the correct-key path does location.reload()
  await page.waitForSelector('#main', { state: 'visible', timeout: 5000 });
  check('right key admits (gate hidden, app visible)',
    !(await page.locator('#gate').isVisible()) && await page.locator('#main').isVisible());

  console.log('Manifest rendering');
  await page.waitForFunction(() => document.querySelectorAll('.item').length > 0, { timeout: 10000 });
  const catCount = await page.locator('.catgroup').count();
  const itemCount = await page.locator('.item').count();
  check('renders all 16 categories', catCount === 16, 'got ' + catCount);
  check('renders all 76 items', itemCount === 76, 'got ' + itemCount);

  const counterText = await page.locator('#counter').textContent();
  check('status counter reflects the real branch\'s current state (62 in repo)', counterText.includes('62 / 76'), counterText);

  const firstNewItemBadge = await page.locator('.item[data-id="14_grammar_tools_001"] .badge').textContent();
  check('an item with no audio yet shows "not recorded"', firstNewItemBadge.includes('not recorded'), firstNewItemBadge);

  console.log('Record -> stop -> WAV-encode pipeline (fake audio device)');
  await page.click('#micBtn');
  await page.waitForFunction(() => document.querySelector('#micBtn').disabled === true, { timeout: 5000 });
  check('microphone enabled', true);

  const targetId = '14_grammar_tools_001';
  const card = page.locator('.item[data-id="' + targetId + '"]');
  await card.locator('[data-act="record"]').click();
  await page.waitForTimeout(1200); // ~1.2s of fake tone
  await card.locator('[data-act="stop"]').click();
  await page.waitForFunction(
    (id) => {
      const el = document.querySelector('.item[data-id="' + id + '"] .item-status');
      return el && el.textContent.includes('Saved locally');
    },
    targetId,
    { timeout: 5000 }
  );
  check('recording saved locally', true);

  const wavCheck = await page.evaluate((id) => {
    return new Promise((resolve, reject) => {
      const req = indexedDB.open('dge_genie_asr_recorder_v1', 1);
      req.onsuccess = () => {
        const db = req.result;
        const getReq = db.transaction('clips', 'readonly').objectStore('clips').get(id);
        getReq.onsuccess = async () => {
          const clip = getReq.result;
          if (!clip || !clip.blob) return resolve({ ok: false, reason: 'no clip in IndexedDB' });
          const buf = await clip.blob.arrayBuffer();
          const bytes = new Uint8Array(buf);
          const view = new DataView(buf);
          const str = (off, len) => String.fromCharCode(...bytes.slice(off, off + len));
          resolve({
            ok: true,
            byteLength: buf.byteLength,
            riff: str(0, 4),
            wave: str(8, 4),
            dataTag: str(36, 4),
            sampleRate: view.getUint32(24, true),
            bitsPerSample: view.getUint16(34, true),
            channels: view.getUint16(22, true)
          });
        };
        getReq.onerror = () => reject(getReq.error);
      };
      req.onerror = () => reject(req.error);
    });
  }, targetId);
  check('IndexedDB holds a real WAV blob (RIFF/WAVE header)', wavCheck.ok && wavCheck.riff === 'RIFF' && wavCheck.wave === 'WAVE', JSON.stringify(wavCheck));
  check('WAV is 16kHz mono 16-bit', wavCheck.sampleRate === 16000 && wavCheck.channels === 1 && wavCheck.bitsPerSample === 16, JSON.stringify(wavCheck));
  check('WAV has real audio data bytes (fake device is not silent)', wavCheck.byteLength > 44 + 1000, 'byteLength=' + wavCheck.byteLength);

  const badgeAfterRecord = await card.locator('.badge').textContent();
  check('badge shows "recorded here, not pushed" (ground truth still says absent)', badgeAfterRecord.includes('not pushed'), badgeAfterRecord);

  console.log('Push request construction (mocked network — never hits the real branch)');
  await page.fill('#ghToken', 'ghp_faketesttoken');
  await card.locator('[data-act="push"]').click();
  await page.waitForFunction(
    (id) => {
      const el = document.querySelector('.item[data-id="' + id + '"] .item-status');
      return el && el.textContent.includes('Pushed');
    },
    targetId,
    { timeout: 5000 }
  );
  check('exactly one push request was made', pushedRequests.length === 1, 'got ' + pushedRequests.length);
  if (pushedRequests.length) {
    const r = pushedRequests[0];
    check('pushed to the correct repo/path', r.url === 'https://api.github.com/repos/Tribhuvanachar/bhumandala/contents/genie_asr_benchmark/audio/14_grammar_tools/14_grammar_tools_001.wav', r.url);
    check('pushed to genie-asr-audio-seed, not main', r.body.branch === 'genie-asr-audio-seed', r.body.branch);
    check('commit message names the item', typeof r.body.message === 'string' && r.body.message.includes(targetId), r.body.message);
    check('content is base64 (decodes back to a RIFF header)', Buffer.from(r.body.content, 'base64').slice(0, 4).toString() === 'RIFF');
    check('no sha sent for a brand-new file', r.body.sha === undefined);
    check('Authorization header carries the pasted token', r.headers['authorization'] === 'token ghp_faketesttoken', r.headers['authorization']);
  }

  const badgeAfterPush = await card.locator('.badge').textContent();
  check('badge flips to "in repo" after a successful push', badgeAfterPush.includes('in repo'), badgeAfterPush);

  console.log('Offline ZIP fallback');
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.click('#zipBtn')
  ]);
  check('ZIP download fires with the expected filename', download.suggestedFilename() === 'genie_asr_benchmark_recordings.zip', download.suggestedFilename());

  await browser.close();
  server.close();

  console.log();
  if (failures) { console.error(failures + ' check(s) FAILED'); process.exit(1); }
  console.log('All E2E checks passed.');
})().catch((e) => { console.error('E2E script crashed:', e); process.exit(1); });
