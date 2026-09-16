/**
 * Where puppeteer keeps the Chromium it downloads.
 *
 * The default is ~/.cache/puppeteer, which is OUTSIDE the function directory
 * — and the Cloud Functions buildpack ships this directory, not the build
 * machine's home. Left at the default, `npm install` downloads a browser at
 * build time, the build succeeds, and renderBook then fails at runtime with
 * "Could not find Chrome", which reads like a code bug and is not one.
 *
 * Putting the cache inside functions/ means the browser is part of the
 * deployed image. It also means the image is ~170 MB larger; that is the
 * price of server-side PDF and the reason puppeteer is an OPTIONAL
 * dependency — a deployment that does not want it can install with
 * --omit=optional and renderBook answers 503 instead of breaking anything.
 */
const { join } = require('path');

module.exports = {
  cacheDirectory: join(__dirname, '.puppeteer-cache')
};
