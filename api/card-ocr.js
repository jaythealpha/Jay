// AI precision business-card OCR (Vercel Serverless Function).
// Takes a card photo (data URL) and returns structured contact fields as JSON.
// Keeps the vision API key server-side; the browser never sees it.
//
//   POST /api/card-ocr   {image, back?, license?}  → {name,title,org,tel,email,url,address}
//
// It is a NO-OP (503 not_configured) until you set a vision provider below, so the app
// ships safely: the free client-side OCR (Tesseract.js) and manual entry always work.
//
// Env vars (Vercel → Settings → Environment Variables) — set ONE provider:
//   OPENAI_API_KEY        → uses OpenAI vision (model OPENAI_VISION_MODEL, default gpt-4o-mini)
//   ANTHROPIC_API_KEY     → uses Claude vision (model ANTHROPIC_VISION_MODEL, default claude-haiku-4-5-20251001)
//   GEMINI_API_KEY        → uses Gemini vision (model GEMINI_VISION_MODEL, default gemini-2.0-flash)
//
// Optional per-IP free-trial enforcement (shared with AI art — same 2-line KV pattern):
//   KV_REST_API_URL / KV_REST_API_TOKEN   (Vercel KV / Upstash Redis REST)
//   AI_FREE_LIMIT        (default 3)   — free precision reads per IP
//   AI_LIMIT_WINDOW_SEC  (default 0)   — 0 = lifetime; else reset after N seconds
//   LICENSE_VALIDATE_URL (optional)    — POST {license_key} → {valid:true}; a Pro key bypasses the limit

const KV_URL = process.env.KV_REST_API_URL || process.env.UPSTASH_REDIS_REST_URL || "";
const KV_TOK = process.env.KV_REST_API_TOKEN || process.env.UPSTASH_REDIS_REST_TOKEN || "";
async function kv(path) {
  if (!KV_URL || !KV_TOK) return null;
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

const PROMPT =
  "You are reading a business card. Return ONLY a compact JSON object with these keys " +
  "(empty string if a field is absent): name, title, org, tel, email, url, address. " +
  "Use the primary mobile/phone number for tel. Do not add commentary or code fences.";

function stripFence(s) {
  return String(s || "").replace(/```json/gi, "").replace(/```/g, "").trim();
}
function firstJson(s) {
  const t = stripFence(s);
  const i = t.indexOf("{"), j = t.lastIndexOf("}");
  if (i < 0 || j < i) return null;
  try { return JSON.parse(t.slice(i, j + 1)); } catch (e) { return null; }
}
function clean(o) {
  const out = {};
  ["name", "title", "org", "tel", "email", "url", "address"].forEach(function (k) {
    out[k] = typeof (o && o[k]) === "string" ? o[k].slice(0, 200).trim() : "";
  });
  return out;
}
// data URL "data:image/jpeg;base64,AAAA" → {media, b64}
function splitDataUrl(u) {
  const m = /^data:([\w/+.-]+);base64,(.+)$/i.exec(String(u || ""));
  return m ? { media: m[1], b64: m[2] } : null;
}

async function readOpenAI(img) {
  const key = process.env.OPENAI_API_KEY;
  const model = process.env.OPENAI_VISION_MODEL || "gpt-4o-mini";
  const r = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: { Authorization: "Bearer " + key, "Content-Type": "application/json" },
    body: JSON.stringify({
      model: model, temperature: 0, max_tokens: 400,
      messages: [{ role: "user", content: [
        { type: "text", text: PROMPT },
        { type: "image_url", image_url: { url: img } }
      ] }]
    })
  });
  const d = await r.json();
  if (!r.ok) throw new Error((d && d.error && d.error.message) || ("HTTP " + r.status));
  return firstJson(d.choices && d.choices[0] && d.choices[0].message && d.choices[0].message.content);
}
async function readAnthropic(img) {
  const key = process.env.ANTHROPIC_API_KEY;
  const model = process.env.ANTHROPIC_VISION_MODEL || "claude-haiku-4-5-20251001";
  const p = splitDataUrl(img);
  if (!p) throw new Error("bad_image");
  const r = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: { "x-api-key": key, "anthropic-version": "2023-06-01", "Content-Type": "application/json" },
    body: JSON.stringify({
      model: model, max_tokens: 400,
      messages: [{ role: "user", content: [
        { type: "image", source: { type: "base64", media_type: p.media, data: p.b64 } },
        { type: "text", text: PROMPT }
      ] }]
    })
  });
  const d = await r.json();
  if (!r.ok) throw new Error((d && d.error && d.error.message) || ("HTTP " + r.status));
  const txt = (d.content && d.content[0] && d.content[0].text) || "";
  return firstJson(txt);
}
async function readGemini(img) {
  const key = process.env.GEMINI_API_KEY;
  const model = process.env.GEMINI_VISION_MODEL || "gemini-2.0-flash";
  const p = splitDataUrl(img);
  if (!p) throw new Error("bad_image");
  const r = await fetch("https://generativelanguage.googleapis.com/v1beta/models/" +
    model + ":generateContent?key=" + encodeURIComponent(key), {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      contents: [{ parts: [
        { text: PROMPT },
        { inline_data: { mime_type: p.media, data: p.b64 } }
      ] }],
      generationConfig: { temperature: 0, maxOutputTokens: 400 }
    })
  });
  const d = await r.json();
  if (!r.ok) throw new Error((d && d.error && d.error.message) || ("HTTP " + r.status));
  const txt = d.candidates && d.candidates[0] && d.candidates[0].content &&
    d.candidates[0].content.parts && d.candidates[0].content.parts[0] &&
    d.candidates[0].content.parts[0].text;
  return firstJson(txt);
}

export default async function handler(req, res) {
  if (req.method !== "POST") { res.status(405).json({ error: "method" }); return; }

  // pick a configured provider; none → graceful no-op so the app still ships
  let provider = "";
  if (process.env.OPENAI_API_KEY) provider = "openai";
  else if (process.env.ANTHROPIC_API_KEY) provider = "anthropic";
  else if (process.env.GEMINI_API_KEY) provider = "gemini";
  if (!provider) { res.status(503).json({ error: "not_configured" }); return; }

  try {
    const b = typeof req.body === "string" ? JSON.parse(req.body || "{}") : (req.body || {});
    const image = String(b.image || "");
    if (!/^data:image\//i.test(image)) { res.status(400).json({ error: "missing_image" }); return; }

    // gate: Pro licenses pass; everyone else limited per IP (only when KV is set)
    const license = String(b.license || "").trim().toUpperCase().slice(0, 64);
    const pro = await isProLicense(license);
    if (!pro && KV_URL && KV_TOK) {
      const FREE = Math.max(0, parseInt(process.env.AI_FREE_LIMIT || "3", 10) || 0);
      const WIN = Math.max(0, parseInt(process.env.AI_LIMIT_WINDOW_SEC || "0", 10) || 0);
      const key = "aiq:" + clientIp(req);   // shared budget with AI art
      const n = await kv("incr/" + encodeURIComponent(key));
      if (n !== null) {
        if (WIN > 0 && n === 1) { await kv("expire/" + encodeURIComponent(key) + "/" + WIN); }
        if (n > FREE) {
          res.status(402).json({ error: "trial_exhausted", limit: FREE,
            detail: "AI 무료 체험 " + FREE + "회를 모두 사용했습니다. Pro로 무제한 이용하세요." });
          return;
        }
      }
    }

    let parsed = null;
    if (provider === "openai") parsed = await readOpenAI(image);
    else if (provider === "anthropic") parsed = await readAnthropic(image);
    else parsed = await readGemini(image);

    if (!parsed) { res.status(502).json({ error: "parse_failed", detail: "명함에서 정보를 추출하지 못했습니다." }); return; }
    res.status(200).json(clean(parsed));
  } catch (e) {
    res.status(500).json({ error: "server", detail: String((e && e.message) || e) });
  }
}
