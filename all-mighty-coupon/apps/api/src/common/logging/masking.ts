/**
 * Log-safety guard (spec §17): raw barcodes, coupon numbers, tokens, and full
 * emails must never reach logs, analytics, or error trackers. Everything that
 * gets logged as structured data passes through maskSensitive first.
 */

const SENSITIVE_KEY_PATTERN =
  /barcode(?!hash)|couponnumber|coupon_number|token|authorization|password|secret|apikey|api_key|cookie/i;

export const MASK = '[REDACTED]';

export function maskEmail(email: string): string {
  const atIndex = email.indexOf('@');
  if (atIndex <= 0) return MASK;
  const local = email.slice(0, atIndex);
  const visible = local.slice(0, Math.min(2, local.length));
  return `${visible}***@${email.slice(atIndex + 1)}`;
}

function isEmailKey(key: string): boolean {
  return /email/i.test(key);
}

export function maskSensitive(value: unknown, depth = 0): unknown {
  if (depth > 6) return MASK;
  if (Array.isArray(value)) {
    return value.map((item) => maskSensitive(item, depth + 1));
  }
  if (value !== null && typeof value === 'object') {
    const out: Record<string, unknown> = {};
    for (const [key, inner] of Object.entries(value as Record<string, unknown>)) {
      if (SENSITIVE_KEY_PATTERN.test(key)) {
        out[key] = MASK;
      } else if (isEmailKey(key) && typeof inner === 'string') {
        out[key] = maskEmail(inner);
      } else {
        out[key] = maskSensitive(inner, depth + 1);
      }
    }
    return out;
  }
  return value;
}
