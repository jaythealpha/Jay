// Action Key QR (Vercel Serverless Function) — see docs/action-qr-concept.md.
// A QR holds only https://<site>/a/<id>; this function stores the rules and decides what happens on each scan.
//
//   POST {op:"create", def}                       → {id, key}           (key = owner key, returned once; only its hash is stored)
//   POST {op:"update", id, key, def}              → {ok}
//   POST {op:"get", id, key}                      → {def}               (owner: full definition for editing)
//   POST {op:"onoff", id, key, on}                → {ok}                (remote disable / enable)
//   POST {op:"scan", id, key?, dev, ctx}          → {who, t, c, run:{ri, do:[…]}} | {need:"pass"|"loc", ri} | {off:true} | {none:true}
//   POST {op:"vault.add", id, key?, dev, ctx, ri, text?, data?}   → {ok}   (shared vault; allowed only if rule ri has vault.add scope "shared")
//   POST {op:"vault.list", id, key?, dev, ctx, ri} → {items:[{img?, text?, at}]}
//   GET  ?status=1                                → {blob, kv}
//   GET  ?stats=<id>&key=…                        → {kv, n}            (owner)
//
// Storage: Vercel Blob  aq/<id>/d-<time>.json  (rule definition; every save is a new file, older ones are deleted —
//          avoids stale CDN copies)   aq/<id>/v/<time>-<rand>.(webp|json)  (shared vault items)
//          Upstash KV (optional)  aq:<id>:n (scan counter)  aq:<id>:o (claimed by first-only)
// Env: BLOB_READ_WRITE_TOKEN (required), KV_REST_API_URL/TOKEN or UPSTASH_REDIS_REST_URL/TOKEN (counters).
import crypto from "crypto";

const BLOB_API = "https://blob.vercel-storage.com";
const KV_URL = process.env.KV_REST_API_URL || process.env.UPSTASH_REDIS_REST_URL || "";
const KV_TOK = process.env.KV_REST_API_TOKEN || process.env.UPSTASH_REDIS_REST_TOKEN || "";
const hasKV = () => !!(KV_URL && KV_TOK);
async function kv(path) {
  if (!hasKV()) return null;
  try { const r = await fetch(KV_URL + "/" + path, { headers: { Authorization: "Bearer " + KV_TOK } }); const d = await r.json(); return d && "result" in d ? d.result : null; }
  catch (e) { return null; }
}
const H = () => ({ authorization: "Bearer " + process.env.BLOB_READ_WRITE_TOKEN, "x-api-version": "9" });
async function blobPut(pathname, body, type) {
  const r = await fetch(BLOB_API + "/?" + new URLSearchParams({ pathname }), { method: "PUT", body,
    headers: { ...H(), "x-content-type": type, "x-add-random-suffix": "0", "x-allow-overwrite": "1", "x-cache-control-max-age": "60" } });
  const d = await r.json().catch(() => ({}));
  if (!r.ok || !d.url) throw new Error("blob_put " + r.status);
  return d.url;
}
async function blobList(prefix, limit = 1000) {
  const r = await fetch(BLOB_API + "/?" + new URLSearchParams({ prefix, limit: String(limit) }), { headers: H() });
  const d = await r.json().catch(() => ({}));
  return (d.blobs || []).map((b) => ({ url: b.url, path: b.pathname, at: b.uploadedAt }));
}
async function blobDel(urls) { if (!urls.length) return; await fetch(BLOB_API + "/delete", { method: "POST", headers: { ...H(), "content-type": "application/json" }, body: JSON.stringify({ urls }) }); }

const ID_RE = /^[a-z2-9]{10}$/;
const B32 = "abcdefghijkmnpqrstuvwxyz23456789";
function newId() { const b = crypto.randomBytes(10); let s = ""; for (let i = 0; i < 10; i++) s += B32[b[i] % 32]; return s; }
const sha = (s) => crypto.createHash("sha256").update(String(s)).digest("hex");
const ts = () => Date.now().toString(36).padStart(9, "0");

async function loadDef(id) {
  const list = (await blobList("aq/" + id + "/d-")).sort((a, b) => (a.path < b.path ? 1 : -1));
  if (!list.length) return null;
  const r = await fetch(list[0].url + "?v=" + Date.now(), { cache: "no-store" });
  return r.ok ? r.json() : null;
}
async function saveDef(id, def) {
  const old = await blobList("aq/" + id + "/d-");
  await blobPut("aq/" + id + "/d-" + ts() + ".json", JSON.stringify(def), "application/json");
  await blobDel(old.map((o) => o.url));
}

// ---- definition validation (keeps stored JSON bounded and well-formed) ----
const CONDS = ["who", "first", "once", "count", "time", "hours", "days", "pass", "near"];
const ACTS = ["show", "link", "vault.add", "vault.show", "countdown", "focus.start", "focus.end", "wifi", "contact", "calendar"];
function clean(def, prevDef) {
  if (!def || typeof def !== "object") throw new Error("bad_def");
  const s = (v, n) => String(v == null ? "" : v).slice(0, n);
  const out = { v: 1, t: s(def.t, 60), c: s(def.c, 6).replace(/[^0-9a-f]/gi, "") || "111111", tpl: s(def.tpl, 20), on: def.on !== false, rules: [] };
  const rules = Array.isArray(def.rules) ? def.rules.slice(0, 12) : [];
  rules.forEach((r, ri) => {
    const ifs = (Array.isArray(r.if) ? r.if : []).slice(0, 6).filter((c) => c && CONDS.includes(c.k)).map((c) => {
      const o = { k: c.k };
      if (c.k === "who") o.v = c.v === "owner" ? "owner" : "visitor";
      if (c.k === "first") o.v = c.v === false ? false : true;
      if (c.k === "count") { o.from = Math.max(1, parseInt(c.from, 10) || 1); o.to = Math.max(o.from, parseInt(c.to, 10) || o.from); }
      if (c.k === "time") { o.from = s(c.from, 30); o.to = s(c.to, 30); }
      if (c.k === "hours") { o.from = Math.min(23, Math.max(0, parseInt(c.from, 10) || 0)); o.to = Math.min(24, Math.max(0, parseInt(c.to, 10) || 24)); }
      if (c.k === "days") o.v = (Array.isArray(c.v) ? c.v : []).map(Number).filter((d) => d >= 0 && d <= 6);
      if (c.k === "pass") {   // plain text is never stored: keep the old hash when the editor sends none
        const prev = prevDef && prevDef.rules && prevDef.rules[ri] && (prevDef.rules[ri].if || []).find((x) => x.k === "pass");
        o.h = c.p ? sha(s(c.p, 64).trim()) : (c.h && prev && prev.h === c.h ? c.h : "");
        if (!o.h) return null;
      }
      if (c.k === "near") { o.lat = +c.lat || 0; o.lng = +c.lng || 0; o.r = Math.min(5000, Math.max(30, parseInt(c.r, 10) || 150)); }
      return o;
    }).filter(Boolean);
    const dos = (Array.isArray(r.do) ? r.do : []).slice(0, 3).filter((a) => a && ACTS.includes(a.a)).map((a) => {
      const o = { a: a.a };
      ["title", "body", "url", "label", "msg", "ssid", "pw", "name", "tel", "email", "org", "place", "to", "start", "end", "img"].forEach((k) => { if (a[k] != null && a[k] !== "") o[k] = s(a[k], k === "body" ? 1000 : 300); });
      if (a.a === "vault.add" || a.a === "vault.show") o.scope = a.scope === "shared" ? "shared" : "device";
      if (a.a === "vault.show") o.mode = ["latest", "all", "random"].includes(a.mode) ? a.mode : "all";
      if (a.a === "focus.start") { o.min = Math.min(720, Math.max(1, parseInt(a.min, 10) || 30)); }
      if (a.img && !/^https:\/\/[a-z0-9]+\.public\.blob\.vercel-storage\.com\//i.test(a.img)) delete o.img;
      return o;
    });
    if (dos.length) out.rules.push({ if: ifs, do: dos });
  });
  return out;
}
// what a visitor/owner device may see: drop password hashes
function publicDo(dos) { return dos.map((a) => ({ ...a })); }

// ---- rule evaluation ----
function within(c, now) {   // "time": ISO strings (with offset) from the editor
  const a = c.from ? Date.parse(c.from) : -Infinity, b = c.to ? Date.parse(c.to) : Infinity;
  return now >= a && now < b;
}
function kstParts(now) { const d = new Date(now + 9 * 3600e3); return { h: d.getUTCHours(), dow: d.getUTCDay() }; }
function dist(a, b, c, d) { const R = 6371e3, r = Math.PI / 180, x = (c - a) * r, y = (d - b) * r, h = Math.sin(x / 2) ** 2 + Math.cos(a * r) * Math.cos(c * r) * Math.sin(y / 2) ** 2; return 2 * R * Math.asin(Math.sqrt(h)); }
async function evaluate(id, def, who, dev, ctx, { commit }) {
  const now = Date.now(), { h, dow } = kstParts(now);
  let n = null;   // scan number (only when KV and only on a real scan)
  if (commit && hasKV()) n = await kv("incr/" + encodeURIComponent("aq:" + id + ":n"));
  for (let ri = 0; ri < def.rules.length; ri++) {
    const r = def.rules[ri]; let ok = true, need = null;
    for (const c of r.if) {
      if (c.k === "who") ok = c.v === who;
      else if (c.k === "first") ok = c.v ? !ctx.seen : !!ctx.seen;
      else if (c.k === "time") ok = within(c, now);
      else if (c.k === "hours") ok = c.from <= c.to ? (h >= c.from && h < c.to) : (h >= c.from || h < c.to);
      else if (c.k === "days") ok = c.v.includes(dow);
      else if (c.k === "count") { if (n == null) { ok = false; if (!hasKV()) ctx._nokv = true; } else ok = n >= c.from && n <= c.to; }
      else if (c.k === "once") {
        if (!hasKV()) { ok = false; ctx._nokv = true; }
        else if (!commit) ok = (await kv("get/" + encodeURIComponent("aq:" + id + ":o"))) === dev;
        else { const set = await kv("set/" + encodeURIComponent("aq:" + id + ":o") + "/" + encodeURIComponent(dev) + "/NX"); ok = set === "OK" || (await kv("get/" + encodeURIComponent("aq:" + id + ":o"))) === dev; }
      }
      else if (c.k === "pass") { if (!ctx.pass) need = need || "pass"; else ok = sha(String(ctx.pass).trim()) === c.h; }
      else if (c.k === "near") { if (ctx.lat == null || ctx.lng == null) need = need || "loc"; else ok = dist(c.lat, c.lng, +ctx.lat, +ctx.lng) <= c.r + Math.min(200, +ctx.acc || 0); }
      if (!ok) break;
    }
    if (!ok) { if (ctx.pass && r.if.some((c) => c.k === "pass")) ctx._badpass = true; continue; }
    if (need) return { need, ri };
    return { run: { ri, do: publicDo(r.do) }, n, badpass: !!ctx._badpass, nokv: !!ctx._nokv };
  }
  return { none: true, n, nokv: !!ctx._nokv, badpass: !!ctx._badpass };
}

function body(req) { return typeof req.body === "string" ? JSON.parse(req.body || "{}") : (req.body || {}); }
const DEV_RE = /^[a-z0-9-]{8,40}$/i;

export default async function handler(req, res) {
  res.setHeader("Cache-Control", "no-store");
  try {
    if (!process.env.BLOB_READ_WRITE_TOKEN) { res.status(503).json({ error: "no_blob" }); return; }
    if (req.method === "GET") {
      const q = req.query || {};
      if (q.status) { res.status(200).json({ blob: true, kv: hasKV() }); return; }
      if (q.stats && ID_RE.test(String(q.stats))) {
        const def = await loadDef(q.stats);
        if (!def || sha(String(q.key || "")) !== def.owner) { res.status(403).json({ error: "owner_only" }); return; }
        const n = hasKV() ? parseInt(await kv("get/" + encodeURIComponent("aq:" + q.stats + ":n")) || "0", 10) : null;
        res.status(200).json({ kv: hasKV(), n }); return;
      }
      res.status(400).json({ error: "bad_request" }); return;
    }
    if (req.method !== "POST") { res.status(405).json({ error: "method" }); return; }
    const b = body(req); const id = String(b.id || "");

    if (b.op === "create") {
      const def = clean(b.def); const key = crypto.randomBytes(24).toString("base64url");
      let nid = newId(); for (let i = 0; i < 3 && (await blobList("aq/" + nid + "/d-", 1)).length; i++) nid = newId();
      def.owner = sha(key); def.at = Date.now();
      await saveDef(nid, def); res.status(200).json({ id: nid, key }); return;
    }
    if (!ID_RE.test(id)) { res.status(400).json({ error: "bad_id" }); return; }
    const def = await loadDef(id);
    if (!def) { res.status(404).json({ error: "not_found" }); return; }
    const isOwner = !!b.key && sha(String(b.key)) === def.owner;

    if (b.op === "get" || b.op === "update" || b.op === "onoff") {
      if (!isOwner) { res.status(403).json({ error: "owner_only" }); return; }
      if (b.op === "get") { res.status(200).json({ def: { ...def, owner: undefined } }); return; }
      const next = b.op === "update" ? clean(b.def, def) : { ...def, on: !!b.on };
      next.owner = def.owner; next.at = def.at; next.up = Date.now();
      if (b.op === "update" && b.def.on === undefined) next.on = def.on;
      await saveDef(id, next); res.status(200).json({ ok: true }); return;
    }

    const dev = String(b.dev || ""); if (!DEV_RE.test(dev)) { res.status(400).json({ error: "bad_device" }); return; }
    const ctx = b.ctx && typeof b.ctx === "object" ? { seen: !!b.ctx.seen, pass: b.ctx.pass ? String(b.ctx.pass).slice(0, 64) : "", lat: b.ctx.lat, lng: b.ctx.lng, acc: b.ctx.acc } : {};
    const who = isOwner ? "owner" : "visitor";
    const head = { who, t: def.t, c: def.c, kv: hasKV() };

    if (b.op === "scan") {
      if (def.on === false && !isOwner) { res.status(200).json({ ...head, off: true }); return; }
      const r = await evaluate(id, def, who, dev, ctx, { commit: !b.preview });
      res.status(200).json({ ...head, off: def.on === false, ...r }); return;
    }
    if (b.op === "vault.add" || b.op === "vault.list") {
      // re-check that the rule this device was given really allows the shared vault
      const r = await evaluate(id, def, who, dev, ctx, { commit: false });
      const want = b.op === "vault.add" ? "vault.add" : "vault.show";
      // listing is also allowed right after adding (the "open the box" button under vault.add)
      const allowed = r.run && r.run.ri === b.ri && r.run.do.some((a) => a.scope === "shared" && (a.a === want || (want === "vault.show" && a.a === "vault.add")));
      const viaOwner = isOwner && b.op === "vault.list";
      if (!allowed && !viaOwner) { res.status(403).json({ error: "not_allowed" }); return; }
      if (b.op === "vault.list") {
        const items = (await blobList("aq/" + id + "/v/", 200)).sort((x, y) => (x.path < y.path ? 1 : -1)).slice(0, 60);
        const out = await Promise.all(items.map(async (it) => {
          if (it.path.endsWith(".json")) { try { const j = await (await fetch(it.url)).json(); return { text: String(j.text || ""), at: j.at, img: j.img || undefined }; } catch (e) { return null; } }
          return null;
        }));
        res.status(200).json({ items: out.filter(Boolean) }); return;
      }
      if ((await blobList("aq/" + id + "/v/", 200)).length >= 180) { res.status(409).json({ error: "vault_full" }); return; }
      const text = String(b.text || "").slice(0, 500); let img;
      if (b.data) {
        const m = /^data:image\/(webp|jpeg|png);base64,([A-Za-z0-9+/=]+)$/.exec(String(b.data));
        if (!m) { res.status(400).json({ error: "bad_image" }); return; }
        const buf = Buffer.from(m[2], "base64"); if (buf.length > 1.5 * 1024 * 1024) { res.status(413).json({ error: "too_large" }); return; }
        img = await blobPut("aq/" + id + "/v/" + ts() + "-" + newId().slice(0, 5) + "." + (m[1] === "jpeg" ? "jpg" : m[1]), buf, "image/" + m[1]);
      }
      if (!text && !img) { res.status(400).json({ error: "empty" }); return; }
      await blobPut("aq/" + id + "/v/" + ts() + "-" + newId().slice(0, 5) + ".json", JSON.stringify({ text, img, at: Date.now() }), "application/json");
      res.status(200).json({ ok: true }); return;
    }
    res.status(400).json({ error: "bad_op" });
  } catch (e) {
    res.status(500).json({ error: "server", detail: String((e && e.message) || e) });
  }
}
