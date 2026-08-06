import type { FieldCandidate } from '@amc/shared-types';

/**
 * KRW amount extraction. Amounts are integers in won (faceValueMinor) — never
 * floats. "1만원" style units are expanded; ambiguous bare numbers are ignored.
 */

const WON_PATTERNS: Array<{ regex: RegExp; scale: number; confidence: number }> = [
  // 10,000원 / 10000원 / ₩10,000
  { regex: /(?:₩\s*)([\d,]+)/g, scale: 1, confidence: 0.9 },
  { regex: /([\d,]+)\s*원/g, scale: 1, confidence: 0.9 },
  // 1만원 / 3만 원
  { regex: /(\d+(?:\.\d+)?)\s*만\s*원/g, scale: 10_000, confidence: 0.85 },
];

export function extractAmountCandidates(text: string): Array<FieldCandidate<number>> {
  const results: Array<FieldCandidate<number>> = [];
  for (const { regex, scale, confidence } of WON_PATTERNS) {
    regex.lastIndex = 0;
    let m: RegExpExecArray | null;
    while ((m = regex.exec(text)) !== null) {
      const raw = (m[1] ?? '').replace(/,/g, '');
      const numeric = Number(raw) * scale;
      if (Number.isFinite(numeric) && Number.isInteger(numeric) && numeric > 0) {
        results.push({ value: numeric, confidence });
      }
    }
  }
  return results;
}

/** The face value is usually the largest amount printed on a coupon. */
export function extractFaceValue(text: string): FieldCandidate<number> | null {
  const candidates = extractAmountCandidates(text);
  if (candidates.length === 0) return null;
  return candidates.reduce((best, c) => (c.value > best.value ? c : best));
}
