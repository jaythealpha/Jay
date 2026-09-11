// AI art-QR generation proxy (Vercel Serverless Function).
// Keeps REPLICATE_API_TOKEN server-side; the browser never sees it.
//
//   POST /api/art-qr        {content, prompt, scale}  → {id, status}   (starts a prediction)
//   GET  /api/art-qr?id=…                             → {status, output, detail}  (poll)
//
// Env vars (Vercel → Settings → Environment Variables):
//   REPLICATE_API_TOKEN   (required)  — from replicate.com/account/api-tokens
//   REPLICATE_MODEL       (optional)  — "owner/name" QR-ControlNet model.
//                                       default "zylim0702/qr_code_controlnet"
//   REPLICATE_VERSION     (optional)  — pin an exact version hash (skips lookup)
//   REPLICATE_CONTENT_FIELD (optional)— input field that receives the URL/text.
//                                       default "url"  (nateraw model uses "qr_code_content")
//   REPLICATE_SCALE_FIELD (optional)  — conditioning-scale field name.
//                                       default "qr_conditioning_scale"
//                                       (some models use "controlnet_conditioning_scale")
const RE = "https://api.replicate.com/v1";

// ---- server-side free-trial enforcement (optional) ---------------------------------------
// Enforced ONLY when a KV store is configured. Uses the Upstash Redis REST API, which
// Vercel KV exposes via KV_REST_API_URL + KV_REST_API_TOKEN (or UPSTASH_REDIS_REST_*).
// Without those env vars this is a no-op and the client-side counter remains the only limit.
//   AI_FREE_LIMIT        (default 3)  — free AI-art generations per IP
//   AI_LIMIT_WINDOW_SEC  (default 0)  — 0 = lifetime; else the counter resets after N seconds
//   LICENSE_VALIDATE_URL (optional)   — POST {license_key} → {valid:true|…}; a valid Pro key bypasses the limit
const KV_URL = process.env.KV_REST_API_URL || process.env.UPSTASH_REDIS_REST_URL || "";
const KV_TOK = process.env.KV_REST_API_TOKEN || process.env.UPSTASH_REDIS_REST_TOKEN || "";
async function kv(path) {
  if (!KV_URL || !KV_TOK) return null;                       // not configured → no enforcement
  try {
    const r = await fetch(KV_URL + "/" + path, { headers: { Authorization: "Bearer " + KV_TOK } });
    const d = await r.json();
    return (d && "result" in d) ? d.result : null;
  } catch (e) { return null; }
}
async function isProLicense(license) {
  const url = process.env.LICENSE_VALIDATE_URL;
  if (!license || !url) return false;
  try {
    const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ license_key: license }) });
    const d = await r.json();
    return !!(d && (d.valid === true || d.activated === true ||
      (d.license_key && d.license_key.status === "active")));
  } catch (e) { return false; }
}
function clientIp(req) {
  const xff = (req.headers["x-forwarded-for"] || "").split(",")[0].trim();
  return xff || (req.socket && req.socket.remoteAddress) || "anon";
}

export default async function handler(req, res) {
  const token = process.env.REPLICATE_API_TOKEN;
  if (!token) { res.status(503).json({ error: "no_token" }); return; }
  const H = { Authorization: "Bearer " + token, "Content-Type": "application/json" };
  try {
    if (req.method === "GET") {
      const id = (req.query && req.query.id) || "";
      if (!/^[\w-]+$/.test(id)) { res.status(400).json({ error: "missing_id" }); return; }
      const r = await fetch(RE + "/predictions/" + id, { headers: H });
      const d = await r.json();
      let output = null;
      if (d.status === "succeeded") {
        output = Array.isArray(d.output) ? d.output[d.output.length - 1] : d.output;
      }
      res.status(200).json({ status: d.status || "unknown", output, detail: d.error || null });
      return;
    }
    if (req.method !== "POST") { res.status(405).json({ error: "method" }); return; }

    const b = typeof req.body === "string" ? JSON.parse(req.body || "{}") : (req.body || {});
    const content = String(b.content || "").slice(0, 512);
    const prompt = String(b.prompt || "").slice(0, 600);
    if (!content || !prompt) { res.status(400).json({ error: "missing_params" }); return; }
    const scale = Math.min(3, Math.max(0.8, +b.scale || 1.5));

    // ---- gate: Pro licenses pass; everyone else is limited per IP (only when KV is set) ----
    const license = String(b.license || "").trim().toUpperCase().slice(0, 64);
    const pro = await isProLicense(license);
    if (!pro && KV_URL && KV_TOK) {
      const FREE = Math.max(0, parseInt(process.env.AI_FREE_LIMIT || "3", 10) || 0);
      const WIN = Math.max(0, parseInt(process.env.AI_LIMIT_WINDOW_SEC || "0", 10) || 0);
      const key = "aiq:" + clientIp(req);
      const n = await kv("incr/" + encodeURIComponent(key));   // null if KV unavailable
      if (n !== null) {
        if (WIN > 0 && n === 1) { await kv("expire/" + encodeURIComponent(key) + "/" + WIN); }
        if (n > FREE) {
          res.status(402).json({ error: "trial_exhausted", limit: FREE,
            detail: "AI 아트 무료 체험 " + FREE + "회를 모두 사용했습니다. Pro로 무제한 이용하세요." });
          return;
        }
      }
    }

    const model = process.env.REPLICATE_MODEL || "zylim0702/qr_code_controlnet";
    let version = process.env.REPLICATE_VERSION || "";

    // Community models are NOT reachable via /models/{owner}/{name}/predictions — we must
    // resolve the latest version hash and call /predictions with it.
    if (!version) {
      const mr = await fetch(RE + "/models/" + model, { headers: H });
      if (!mr.ok) {
        res.status(502).json({ error: "model_not_found",
          detail: "모델 '" + model + "' 조회 실패 (HTTP " + mr.status + "). Vercel 환경변수 REPLICATE_MODEL을 실존하는 QR ControlNet 모델로 지정하세요 (예: zylim0702/qr_code_controlnet)." });
        return;
      }
      const md = await mr.json();
      version = md && md.latest_version && md.latest_version.id;
      if (!version) {
        res.status(502).json({ error: "no_version", detail: "모델 '" + model + "'에 배포된 버전이 없습니다." });
        return;
      }
    }

    const contentField = process.env.REPLICATE_CONTENT_FIELD || "url";
    const scaleField = process.env.REPLICATE_SCALE_FIELD || "qr_conditioning_scale";
    const input = {
      prompt: prompt,
      negative_prompt: "ugly, disfigured, low quality, blurry, nsfw, text, watermark, deformed",
      num_inference_steps: 40,
      guidance_scale: 7.5,
      batch_size: 1
    };
    input[contentField] = content;
    input[scaleField] = scale;

    const r = await fetch(RE + "/predictions", {
      method: "POST", headers: H, body: JSON.stringify({ version, input })
    });
    const d = await r.json();
    if (!r.ok || !d.id) {
      res.status(502).json({ error: "replicate",
        detail: (d && (d.detail || d.title)) || ("HTTP " + r.status) });
      return;
    }
    res.status(200).json({ id: d.id, status: d.status });
  } catch (e) {
    res.status(500).json({ error: "server", detail: String((e && e.message) || e) });
  }
}
