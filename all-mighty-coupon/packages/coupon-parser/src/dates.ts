import type { FieldCandidate } from '@amc/shared-types';

/**
 * Date extraction from OCR text. Confidence policy: a date sitting next to an
 * expiration keyword ("유효기간", "까지", "~") is trusted more than a bare date.
 * We never fabricate a date — no match means null.
 */

const EXPIRATION_KEYWORDS = [
  '유효기간',
  '유효 기간',
  '사용기한',
  '만료',
  '까지',
  'valid until',
  'expires',
];

interface RawDateMatch {
  year: number;
  month: number;
  day: number;
  index: number;
  length: number;
}

const PATTERNS: Array<{ regex: RegExp; order: ['y', 'm', 'd'] }> = [
  // 2026-12-31 / 2026.12.31 / 2026/12/31
  { regex: /(\d{4})[.\-/]\s?(\d{1,2})[.\-/]\s?(\d{1,2})/g, order: ['y', 'm', 'd'] },
  // 2026년 12월 31일
  { regex: /(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일/g, order: ['y', 'm', 'd'] },
];

function isPlausibleDate(y: number, m: number, d: number): boolean {
  if (y < 2000 || y > 2100 || m < 1 || m > 12 || d < 1 || d > 31) return false;
  const candidate = new Date(Date.UTC(y, m - 1, d));
  return candidate.getUTCMonth() === m - 1 && candidate.getUTCDate() === d;
}

function findRawDates(text: string): RawDateMatch[] {
  const matches: RawDateMatch[] = [];
  for (const { regex } of PATTERNS) {
    regex.lastIndex = 0;
    let m: RegExpExecArray | null;
    while ((m = regex.exec(text)) !== null) {
      const year = Number(m[1]);
      const month = Number(m[2]);
      const day = Number(m[3]);
      if (isPlausibleDate(year, month, day)) {
        matches.push({ year, month, day, index: m.index, length: m[0].length });
      }
    }
  }
  return matches;
}

function toIsoDate({ year, month, day }: RawDateMatch): string {
  const mm = String(month).padStart(2, '0');
  const dd = String(day).padStart(2, '0');
  return `${year}-${mm}-${dd}`;
}

function hasExpirationContext(text: string, match: RawDateMatch): boolean {
  const windowStart = Math.max(0, match.index - 20);
  const windowEnd = Math.min(text.length, match.index + match.length + 10);
  const context = text.slice(windowStart, windowEnd).toLowerCase();
  if (EXPIRATION_KEYWORDS.some((k) => context.includes(k))) return true;
  // "~ 2026.12.31" range notation marks the right edge as the expiration.
  return /[~∼]\s*$/.test(text.slice(windowStart, match.index));
}

export function extractDateCandidates(text: string): Array<FieldCandidate<string>> {
  return findRawDates(text).map((match) => ({
    value: toIsoDate(match),
    confidence: hasExpirationContext(text, match) ? 0.96 : 0.7,
  }));
}

/**
 * Picks the expiration date: prefer keyword-anchored candidates; among equals
 * take the latest date (issue dates typically precede expiration dates).
 */
export function extractExpirationDate(text: string): FieldCandidate<string> | null {
  const candidates = extractDateCandidates(text);
  if (candidates.length === 0) return null;
  const best = [...candidates].sort(
    (a, b) => b.confidence - a.confidence || b.value.localeCompare(a.value),
  )[0];
  return best ?? null;
}
