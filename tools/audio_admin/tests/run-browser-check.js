const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));
  await page.goto('file://' + path.resolve(__dirname, 'browser-check.html'));
  await page.waitForFunction(() => document.title === 'PASS' || document.title === 'FAIL', { timeout: 120000 });
  const out = await page.textContent('#out');
  const title = await page.title();
  await browser.close();
  console.log(out);
  if (errors.length) { console.error('page errors:', errors); process.exit(1); }
  console.log(title === 'PASS' ? 'browser check: PASS' : 'browser check: FAIL');
  process.exit(title === 'PASS' ? 0 : 1);
})();
