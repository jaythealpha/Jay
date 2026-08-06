import { describe, expect, it } from 'vitest';
import { extractProductName } from './product-name';

describe('extractProductName', () => {
  const sample = [
    '스타벅스',
    '아이스 카페 아메리카노 Tall',
    '유효기간 2026.12.31',
    '금액 4,500원',
    '주문번호 1234-5678-9012',
  ].join('\n');

  it('picks the product line, skipping brand/date/amount/boilerplate', () => {
    const result = extractProductName(sample, '스타벅스');
    expect(result?.value).toBe('아이스 카페 아메리카노 Tall');
  });

  it('never exceeds confirm-level confidence (heuristics need review)', () => {
    const result = extractProductName(sample, '스타벅스');
    expect(result?.confidence).toBeLessThan(0.9);
  });

  it('returns null when only metadata lines exist', () => {
    expect(extractProductName('유효기간 2026.12.31\n금액 4,500원', null)).toBeNull();
  });

  it('ignores barcode-like digit lines', () => {
    const result = extractProductName('8801234567890\n파인트 아이스크림', null);
    expect(result?.value).toBe('파인트 아이스크림');
  });
});
