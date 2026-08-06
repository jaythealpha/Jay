import { describe, expect, it } from 'vitest';
import { matchBrand } from './brands';

describe('matchBrand', () => {
  it('matches the canonical Korean name with high confidence', () => {
    const result = matchBrand('스타벅스 아메리카노 Tall');
    expect(result?.value).toBe('스타벅스');
    expect(result?.confidence).toBeGreaterThanOrEqual(0.9);
  });

  it('matches aliases case- and space-insensitively', () => {
    expect(matchBrand('STARBUCKS COFFEE Americano')?.value).toBe('스타벅스');
    expect(matchBrand('a twosome place cake')?.value).toBe('투썸플레이스');
  });

  it('returns null instead of guessing for unknown brands', () => {
    expect(matchBrand('동네 반찬가게 5000원 쿠폰')).toBeNull();
  });
});
