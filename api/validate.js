// License-key validation endpoint (Vercel Serverless Function).
//   POST /api/validate   {license_key}  → {valid: boolean}
//
// Wire ONE Merchant-of-Record via env vars. Until you do, DEV keys of the form
// QRPRO-XXXX-XXXX pass, so the unlock flow stays testable end-to-end.
//
//   Polar:          POLAR_ACCESS_TOKEN  (+ optional POLAR_ORGANIZATION_ID)
//   Lemon Squeezy:  LEMONSQUEEZY_API_KEY   (validate endpoint is keyless, flag just enables it)
//   Any other MoR:  LICENSE_VALIDATE_URL   (POST {license_key} → {valid|activated|license_key.status})
//
// The browser calls this from PRO.validateUrl; it only ever sends the license key.
export default async function handler(req, res) {
  if (req.method !== "POST") { res.status(405).json({ valid: false, error: "method" }); return; }
  const b = typeof req.body === "string" ? JSON.parse(req.body || "{}") : (req.body || {});
  const key = String(b.license_key || b.key || "").trim();
  if (!key) { res.status(400).json({ valid: false, error: "missing_key" }); return; }

  try {
    // 1) Polar (https://polar.sh) — customer-portal license validation
    if (process.env.POLAR_ACCESS_TOKEN) {
      const r = await fetch("https://api.polar.sh/v1/customer-portal/license-keys/validate", {
        method: "POST",
        headers: { Authorization: "Bearer " + process.env.POLAR_ACCESS_TOKEN, "Content-Type": "application/json" },
        body: JSON.stringify({ key: key, organization_id: process.env.POLAR_ORGANIZATION_ID || undefined })
      });
      const d = await r.json().catch(() => ({}));
      const ok = r.ok && (d.status === "granted" || d.valid === true ||
        (d.license_key && d.license_key.status === "granted"));
      res.status(200).json({ valid: !!ok }); return;
    }

    // 2) Lemon Squeezy — public license validation (no auth needed on the validate call)
    if (process.env.LEMONSQUEEZY_API_KEY) {
      const r = await fetch("https://api.lemonsqueezy.com/v1/licenses/validate", {
        method: "POST",
        headers: { Accept: "application/json", "Content-Type": "application/x-www-form-urlencoded" },
        body: "license_key=" + encodeURIComponent(key)
      });
      const d = await r.json().catch(() => ({}));
      res.status(200).json({ valid: !!(d && d.valid === true) }); return;
    }

    // 3) Generic passthrough to any MoR license API
    if (process.env.LICENSE_VALIDATE_URL) {
      const r = await fetch(process.env.LICENSE_VALIDATE_URL, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ license_key: key })
      });
      const d = await r.json().catch(() => ({}));
      res.status(200).json({ valid: !!(d && (d.valid === true || d.activated === true ||
        (d.license_key && d.license_key.status === "active"))) }); return;
    }

    // 4) DEV fallback (no MoR configured) — accept the fixed format so the flow is testable
    res.status(200).json({ valid: /^QRPRO-[A-Z0-9]{4}-[A-Z0-9]{4}$/.test(key.toUpperCase()), dev: true });
  } catch (e) {
    res.status(200).json({ valid: false, error: "server", detail: String((e && e.message) || e) });
  }
}
