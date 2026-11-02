// Shared helpers for the browser tests: a tiny static server for the repo root and a Chromium finder.
// Run any test with:  node tools/tests/<name>.test.mjs   (needs `playwright-core` resolvable, e.g. npm i -g playwright-core)
import http from 'http'; import fs from 'fs'; import path from 'path'; import { fileURLToPath } from 'url';
export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const TYPES = { '.html':'text/html; charset=utf-8', '.js':'text/javascript', '.mjs':'text/javascript', '.css':'text/css', '.webp':'image/webp', '.png':'image/png', '.jpg':'image/jpeg', '.svg':'image/svg+xml', '.json':'application/json', '.glb':'model/gltf-binary', '.wasm':'application/wasm' };
export function serve(port = 8099) {
  const srv = http.createServer((req, res) => {
    const p = path.join(ROOT, decodeURIComponent(req.url.split('?')[0].split('#')[0]));
    if (!p.startsWith(ROOT) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { res.writeHead(404); res.end(); return; }
    res.writeHead(200, { 'Content-Type': TYPES[path.extname(p)] || 'application/octet-stream' }); fs.createReadStream(p).pipe(res);
  });
  return new Promise((r) => srv.listen(port, () => r(srv)));
}
export function findChrome() {
  if (process.env.CHROME_PATH) return process.env.CHROME_PATH;
  for (const base of ['/opt/pw-browsers', path.join(process.env.HOME || '', '.cache/ms-playwright')]) {
    if (!fs.existsSync(base)) continue;
    for (const d of fs.readdirSync(base)) for (const sub of ['chrome-linux/chrome', 'chrome-linux64/chrome', 'chrome-mac/Chromium.app/Contents/MacOS/Chromium']) { const p = path.join(base, d, sub); if (fs.existsSync(p)) return p; }
  }
  return undefined;   // let playwright pick its default
}
export const enc = (o) => Buffer.from(JSON.stringify(o)).toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
let fails = 0;
export function check(label, ok, extra = '') { console.log((ok ? 'PASS ' : 'FAIL ') + label + (extra ? '  — ' + extra : '')); if (!ok) fails++; }
export function done() { console.log(fails ? `\n${fails} check(s) failed` : '\nall checks passed'); process.exit(fails ? 1 : 0); }
