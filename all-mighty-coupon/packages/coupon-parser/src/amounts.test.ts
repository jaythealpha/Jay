import { describe, expect, it } from 'vitest';
import { extractAmountCandidates, extractFaceValue } from './amounts';

describe('extractAmountCandidates', () => {
  it('parses comma-separated won amounts as integers', () => {
    expect(extractAmountCandidates('금액 10,000원')[0]?.value).toBe(10000);
    expect(extractAmountCandidates('₩5,500')[0]?.value).toBe(5500);
  });

  it('expands 만원 units', () => {
    expect(extractAmountCandidates('3만원 금액권')[0]?.value).toBe(30000);
  });

  it('ignores bare numbers without a currency marker', () => {
    expect(extractAmountCandidates('바코드 8801234567890')).toEqual([]);
  });
});

describe('extractFaceValue', () => {
  it('picks the largest printed amount as the face value', () => {
    const text = '결제금액 30,000원 (잔액 12,500원)';
    expect(extractFaceValue(text)?.value).toBe(30000);
  });

  it('returns null when nothing matches', () => {
    expect(extractFaceValue('아메리카노 1잔 교환권')).toBeNull();
  });
});
