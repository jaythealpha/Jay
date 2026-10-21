// Image AR assets for AR Events (Vercel Serverless Function).
//
//   GET  /api/ar-asset?status=1                → {blob, ai}           (what is configured)
//   POST /api/ar-asset {op:"upload", data}     → {url}                (data URL → Vercel Blob)
//   POST /api/ar-asset {op:"cutout", url}      → {id}                 (background removal, Replicate)
//   POST /api/ar-asset {op:"model3d", url}     → {id}                 (image → 3D GLB, Replicate)
//   GET  /api/ar-asset?id=…&kind=cutout|model3d → {status, url?}      (poll; on success the result is
//                                                                      copied to Blob so it never expires)
//   POST /api/ar-asset {op:"save", cfg}        → {id}                 (event config → short link /event.html?e=id)
//   GET  /api/ar-asset?e=…                     → cfg JSON
//
// Env vars (Vercel → Settings → Environment Variables):
//   BLOB_READ_WRITE_TOKEN  (required) — added automatically when a Blob store is connected to the project
//   REPLICATE_API_TOKEN    (required for cutout / 3D)
//   AR_CUTOUT_MODEL        (optional) default "851-labs/background-remover"   (input field AR_CUTOUT_FIELD, default "image")
//   AR_3D_MODEL            (optional) default "firtoz/trellis"
//   AR_3D_INPUT            (optional) JSON input template for the 3D model; "{url}" is replaced by the image URL
//   AR_3D_DAILY_LIMIT      (optional, default 5) 3D generations per IP per day — enforced only when KV is configured
const BLOB_API = "https://blob.vercel-storage.com";
const RE = "https://api.replicate.com/v1";
const MAX_UPLOAD = 4 * 1024 * 1024;

const KV_URL = process.env.KV_REST_API_URL || process.env.UPSTASH_REDIS_REST_URL || "";
const KV_TOK = process.env.KV_REST_API_TOKEN || process.env.UPSTASH_REDIS_REST_TOKEN || "";
async function kv(path) {
  if (!KV_URL || !KV_TOK) return null;
  try { const r = await fetch(KV_URL + "/" + path, { headers: { Authorization: "Bearer " + KV_TOK } }); const d = await r.json(); return d && "result" in d ? d.result : null; }
  catch (e) { return null; }
}
function clientIp(req) { return (req.headers["x-forwarded-for"] || "").split(",")[0].trim() || "anon"; }

async function blobPut(pathname, body, contentType, random) {
  const token = process.env.BLOB_READ_WRITE_TOKEN;
  const r = await fetch(BLOB_API + "/?" + new URLSearchParams({ pathname }), {
    method: "PUT", body,
    headers: { authorization: "Bearer " + token, "x-api-version": "9", "x-content-type": contentType,
      "x-add-random-suffix": random ? "1" : "0", "x-cache-control-max-age": "31536000" }
  });
  const d = await r.json().catch(() => ({}));
  if (!r.ok || !d.url) throw new Error("blob_put " + r.status + " " + ((d.error && d.error.message) || ""));
  return d.url;
}
async function blobFind(prefix) {
  const token = process.env.BLOB_READ_WRITE_TOKEN;
  const r = await fetch(BLOB_API + "/?" + new URLSearchParams({ prefix, limit: "1" }), {
    headers: { authorization: "Bearer " + token, "x-api-version": "9" } });
  const d = await r.json().catch(() => ({}));
  return (d.blobs && d.blobs[0] && d.blobs[0].url) || null;
}
function rid(n) { const a = "abcdefghijkmnopqrstuvwxyz23456789"; let s = ""; for (let i = 0; i < n; i++) s += a[Math.floor(Math.random() * a.length)]; return s; }
const isOurBlob = (u) => /^https:\/\/[a-z0-9]+\.public\.blob\.vercel-storage\.com\//i.test(String(u || ""));

async function replicateVersion(model, H) {
  const mr = await fetch(RE + "/models/" + model, { headers: H });
  if (!mr.ok) throw new Error("model_not_found " + model);
  const md = await mr.json();
  const v = md && md.latest_version && md.latest_version.id;
  if (!v) throw new Error("no_version " + model);
  return v;
}
// find the first URL in any output shape (string, array, {model_file:…}, …), optionally by extension
function findUrl(o, ext) {
  if (!o) return null;
  if (typeof o === "string") return /^https?:\/\//.test(o) && (!ext || o.split("?")[0].toLowerCase().endsWith(ext)) ? o : null;
  if (Array.isArray(o)) { for (const x of o) { const u = findUrl(x, ext); if (u) return u; } return null; }
  if (typeof o === "object") { for (const k of Object.keys(o)) { const u = findUrl(o[k], ext); if (u) return u; } }
  return null;
}

export default async function handler(req, res) {
  const hasBlob = !!process.env.BLOB_READ_WRITE_TOKEN, rtoken = process.env.REPLICATE_API_TOKEN;
  const H = { Authorization: "Bearer " + rtoken, "Content-Type": "application/json" };
  try {
    if (req.method === "GET") {
      const q = req.query || {};
      if (q.status) { res.status(200).json({ blob: hasBlob, ai: !!rtoken }); return; }
      // TEMP self-test (removed after verification): blob put/read + start cutout / 3D on a sample image
      if (q.selftest === "ar-check-1021") {
        const out = { blob: hasBlob, ai: !!rtoken };
        const img = await fetch("https://" + req.headers.host + "/assets/logos/l077.webp");
        const buf = Buffer.from(await img.arrayBuffer());
        out.put = await blobPut("ar/selftest-" + rid(6) + ".webp", buf, "image/webp", false);
        out.read = (await fetch(out.put)).status;
        if (q.run) {
          const model = q.run === "3d" ? (process.env.AR_3D_MODEL || "firtoz/trellis") : (process.env.AR_CUTOUT_MODEL || "851-labs/background-remover");
          const input = q.run === "3d" ? JSON.parse(('{"images":["{url}"],"generate_model":true,"generate_color":false,"generate_normal":false,"save_gaussian_ply":false,"texture_size":1024,"mesh_simplify":0.95}').split("{url}").join(out.put)) : { image: out.put };
          const version = await replicateVersion(model, H);
          const r = await fetch(RE + "/predictions", { method: "POST", headers: H, body: JSON.stringify({ version, input }) });
          const d = await r.json(); out.pred = { ok: r.ok, id: d.id, status: d.status, detail: d.detail || d.title || null };
        }
        res.status(200).json(out); return;
      }
      if (!hasBlob) { res.status(503).json({ error: "no_blob" }); return; }
      if (q.e) {   // short-link event config
        const id = String(q.e); if (!/^[a-z0-9]{6,16}$/.test(id)) { res.status(400).json({ error: "bad_id" }); return; }
        const u = await blobFind("ev/" + id + ".json");
        if (!u) { res.status(404).json({ error: "not_found" }); return; }
        const cfg = await (await fetch(u)).json();
        res.setHeader("Cache-Control", "public, max-age=60, s-maxage=300");
        res.status(200).json(cfg); return;
      }
      const id = String(q.id || ""), kind = q.kind === "model3d" ? "model3d" : "cutout";
      if (!/^[\w-]+$/.test(id) || !rtoken) { res.status(400).json({ error: "missing_id" }); return; }
      const d = await (await fetch(RE + "/predictions/" + id, { headers: H })).json();
      if (d.status !== "succeeded") { res.status(200).json({ status: d.status || "unknown", detail: d.error || null }); return; }
      const out = kind === "model3d" ? (findUrl(d.output, ".glb") || findUrl(d.output)) : findUrl(d.output);
      if (!out) { res.status(200).json({ status: "failed", detail: "no_output" }); return; }
      const f = await fetch(out); const buf = Buffer.from(await f.arrayBuffer());
      const url = kind === "model3d"
        ? await blobPut("ar/m-" + rid(10) + ".glb", buf, "model/gltf-binary", false)
        : await blobPut("ar/c-" + rid(10) + ".png", buf, "image/png", false);
      res.status(200).json({ status: "succeeded", url }); return;
    }
    if (req.method !== "POST") { res.status(405).json({ error: "method" }); return; }
    if (!hasBlob) { res.status(503).json({ error: "no_blob" }); return; }
    const b = typeof req.body === "string" ? JSON.parse(req.body || "{}") : (req.body || {});

    if (b.op === "upload") {
      const m = /^data:(image\/(?:png|jpeg|webp));base64,([A-Za-z0-9+/=]+)$/.exec(String(b.data || ""));
      if (!m) { res.status(400).json({ error: "bad_image" }); return; }
      const buf = Buffer.from(m[2], "base64");
      if (buf.length > MAX_UPLOAD) { res.status(413).json({ error: "too_large" }); return; }
      const ext = m[1] === "image/png" ? "png" : m[1] === "image/webp" ? "webp" : "jpg";
      res.status(200).json({ url: await blobPut("ar/i-" + rid(10) + "." + ext, buf, m[1], false) }); return;
    }
    if (b.op === "save") {
      const cfg = b.cfg && typeof b.cfg === "object" ? b.cfg : null; const s = JSON.stringify(cfg || {});
      if (!cfg || s.length > 20000) { res.status(400).json({ error: "bad_cfg" }); return; }
      const id = rid(8); await blobPut("ev/" + id + ".json", s, "application/json", false);
      res.status(200).json({ id }); return;
    }
    if (b.op === "cutout" || b.op === "model3d") {
      if (!rtoken) { res.status(503).json({ error: "no_ai" }); return; }
      const url = String(b.url || ""); if (!isOurBlob(url)) { res.status(400).json({ error: "bad_url" }); return; }
      let model, input;
      if (b.op === "cutout") {
        model = process.env.AR_CUTOUT_MODEL || "851-labs/background-remover";
        input = { [process.env.AR_CUTOUT_FIELD || "image"]: url };
      } else {
        const lim = Math.max(1, parseInt(process.env.AR_3D_DAILY_LIMIT || "5", 10) || 5);
        const key = "ar3d:" + clientIp(req) + ":" + new Date().toISOString().slice(0, 10);
        const n = await kv("incr/" + encodeURIComponent(key));
        if (n !== null) { if (n === 1) await kv("expire/" + encodeURIComponent(key) + "/90000"); if (n > lim) { res.status(429).json({ error: "limit", limit: lim }); return; } }
        model = process.env.AR_3D_MODEL || "firtoz/trellis";
        const tpl = process.env.AR_3D_INPUT ||
          '{"images":["{url}"],"generate_model":true,"generate_color":false,"generate_normal":false,"save_gaussian_ply":false,"texture_size":1024,"mesh_simplify":0.95}';
        input = JSON.parse(tpl.split("{url}").join(url));
      }
      const version = await replicateVersion(model, H);
      const r = await fetch(RE + "/predictions", { method: "POST", headers: H, body: JSON.stringify({ version, input }) });
      const d = await r.json();
      if (!r.ok || !d.id) { res.status(502).json({ error: "replicate", detail: (d && (d.detail || d.title)) || ("HTTP " + r.status) }); return; }
      res.status(200).json({ id: d.id }); return;
    }
    res.status(400).json({ error: "bad_op" });
  } catch (e) {
    res.status(500).json({ error: "server", detail: String((e && e.message) || e) });
  }
}
