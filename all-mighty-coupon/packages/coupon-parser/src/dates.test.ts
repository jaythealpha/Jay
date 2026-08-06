import { describe, expect, it } from 'vitest';
import { extractDateCandidates, extractExpirationDate } from './dates';

describe('extractDateCandidates', () => {
  it('parses common Korean date formats', () => {
    expect(extractDateCandidates('2026-12-31').map((c) => c.value)).toEqual(['2026-12-31']);
    expect(extractDateCandidates('2026.12.31').map((c) => c.value)).toEqual(['2026-12-31']);
    expect(extractDateCandidates('2026년 1월 5일').map((c) => c.value)).toEqual(['2026-01-05']);
  });

  it('rejects implausible dates', () => {
    expect(extractDateCandidates('2026-13-01')).toEqual([]);
    expect(extractDateCandidates('2026-02-30')).toEqual([]);
  });

  it('gives higher confidence to keyword-anchored dates', () => {
    const anchored = extractDateCandidates('유효기간: 2026.12.31')[0];
    const bare = extractDateCandidates('발행 2026.12.31 매장')[0];
    expect(anchored?.confidence).toBeGreaterThanOrEqual(0.95);
    expect(bare?.confidence).toBeLessThan(0.95);
  });
});

describe('extractExpirationDate', () => {
  it('prefers the keyword-anchored date over an earlier issue date', () => {
    const text = '발행일 2026.01.02 / 유효기간 2026.12.31 까지';
    expect(extractExpirationDate(text)?.value).toBe('2026-12-31');
  });

  it('understands range notation "~ date"', () => {
    const result = extractExpirationDate('사용기간 2026.01.01 ~ 2026.06.30');
    expect(result?.value).toBe('2026-06-30');
  });

  it('returns null instead of guessing when no date exists', () => {
    expect(extractExpirationDate('아메리카노 Tall 1잔')).toBeNull();
  });
});
