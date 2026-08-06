import type { FieldCandidate } from '@amc/shared-types';
import { extractAmountCandidates } from './amounts';
import { extractDateCandidates } from './dates';

/**
 * Product-name heuristic for OCR text: the product is usually the most
 * content-rich line that is not the brand, a date, an amount, a barcode
 * number, or boilerplate. Heuristics never exceed CONFIRM-level confidence —
 * the user always sees this value for review before it is trusted.
 */

const BOILERPLATE = [
  '유효기간',
  '사용기한',
  '교환처',
  '사용처',
  '주문번호',
  '쿠폰번호',
  '바코드',
  '결제금액',
  '잔액',
  '문의',
  '고객센터',
  '이용약관',
  '기프티콘',
  '모바일 상품권',
  '교환권',
];

function isMostlyDigits(line: string): boolean {
  const digits = line.replace(/\D/g, '').length;
  return line.length > 0 && digits / line.length > 0.5;
}

function stripKnown(line: string): string {
  let cleaned = line;
  for (const candidate of extractDateCandidates(line)) {
    cleaned = cleaned.replace(candidate.value, '');
  }
  return cleaned.trim();
}

export function extractProductName(
  text: string,
  brandName: string | null,
): FieldCandidate<string> | null {
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length >= 2 && line.length <= 60);

  const candidates = lines.filter((line) => {
    if (BOILERPLATE.some((word) => line.includes(word))) return false;
    if (isMostlyDigits(line)) return false;
    if (extractDateCandidates(line).length > 0) return false;
    if (extractAmountCandidates(line).length > 0) return false;
    if (brandName !== null && stripKnown(line).toLowerCase() === brandName.toLowerCase()) {
      return false;
    }
    return true;
  });

  if (candidates.length === 0) return null;

  // Prefer the longest remaining line — product descriptions carry the most
  // characters once metadata lines are filtered out.
  const best = candidates.reduce((a, b) => (b.length > a.length ? b : a));
  const startsNearTop = lines.indexOf(best) <= 2;
  return { value: best, confidence: startsNearTop ? 0.75 : 0.6 };
}
