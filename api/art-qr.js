// AI art-QR generation proxy (Vercel Serverless Function).
// Keeps REPLICATE_API_TOKEN server-side; the browser never sees it.
//
//   POST /api/art-qr        {content, prompt, scale}  → {id, status}   (starts a prediction)
//   GET  /api/art-qr?id=…                             → {status, output, detail}  (poll)
//
// Env vars (Vercel → Settings → Environment Variables):
//   REPLICATE_API_TOKEN  (required)  — from replicate.com/account/api-tokens
//   REPLICATE_MODEL      (optional)  — "owner/name" of a QR-ControlNet model,
//                                      default "nateraw/qrcode-stable-diffusion"
//   REPLICATE_VERSION    (optional)  — pin an exact version hash instead
export default async function handler(req, res) {
  const token = process.env.REPLICATE_API_TOKEN;
  if (!token) { res.status(503).json({ error: "no_token" }); return; }
  const H = { Authorization: "Bearer " + token, "Content-Type": "application/json" };
  try {
    if (req.method === "GET") {
      const id = (req.query && req.query.id) || "";
      if (!/^[\w-]+$/.test(id)) { res.status(400).json({ error: "missing_id" }); return; }
      const r = await fetch("https://api.replicate.com/v1/predictions/" + id, { headers: H });
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
    const scale = Math.min(2, Math.max(0.8, +b.scale || 1.3));

    const model = process.env.REPLICATE_MODEL || "nateraw/qrcode-stable-diffusion";
    const version = process.env.REPLICATE_VERSION || "";
    const input = {
      qr_code_content: content,
      prompt: prompt,
      negative_prompt: "ugly, disfigured, low quality, blurry, nsfw, text, watermark",
      num_inference_steps: 30,
      guidance_scale: 7.5,
      controlnet_conditioning_scale: scale,
      batch_size: 1
    };
    const endpoint = version
      ? "https://api.replicate.com/v1/predictions"
      : "https://api.replicate.com/v1/models/" + model + "/predictions";
    const body = version ? { version, input } : { input };
    const r = await fetch(endpoint, { method: "POST", headers: H, body: JSON.stringify(body) });
    const d = await r.json();
    if (!r.ok || !d.id) {
      res.status(502).json({ error: "replicate", detail: (d && (d.detail || d.title)) || ("HTTP " + r.status) });
      return;
    }
    res.status(200).json({ id: d.id, status: d.status });
  } catch (e) {
    res.status(500).json({ error: "server", detail: String((e && e.message) || e) });
  }
}
