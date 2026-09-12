// Headless runner for the DGE Chandas engine (dge/js/chandas.js).
// Reads a JSON array of Devanagari verse strings on stdin, writes a JSON array of
// DGEChandas.analyzeText() results on stdout. Only three browser globals are stubbed;
// the engine itself is loaded unmodified so results are identical to the website.
const fs = require("fs");
const path = require("path");
const ROOT = path.resolve(__dirname, "..", "..");
global.window = global;
global.document = { readyState: "complete", querySelector: () => null };
global.localStorage = { getItem: () => null };
global.fetch = () => Promise.resolve({
  json: () => Promise.resolve(JSON.parse(fs.readFileSync(path.join(ROOT, "dge/data/vedanga/chandas/data.json"), "utf8")))
});
eval(fs.readFileSync(path.join(ROOT, "dge/js/chandas.js"), "utf8"));
window.DGEChandas.loadDB("").then(() => {
  const verses = JSON.parse(fs.readFileSync(0, "utf8"));
  const out = verses.map(v => {
    try {
      const r = window.DGEChandas.analyzeText(v);
      const n = r.padas.length ? r.padas[0].aksharas : 0;
      r.jaati = window.DGEChandas.jaatiName(n);
      return r;
    } catch (e) { return { error: String(e) }; }
  });
  process.stdout.write(JSON.stringify(out));
});
