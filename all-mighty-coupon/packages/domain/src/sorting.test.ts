import { describe, expect, it } from 'vitest';
import { sortCoupons, type SortableCoupon } from './sorting';

function coupon(partial: Partial<SortableCoupon>): SortableCoupon {
  return {
    status: 'ACTIVE',
    expiresAt: null,
    createdAt: new Date('2026-08-01T00:00:00Z'),
    faceValueMinor: null,
    brandName: null,
    ...partial,
  };
}

describe('sortCoupons EXPIRATION_ASC (wallet default)', () => {
  it('puts the soonest expiration first and undated coupons last', () => {
    const a = coupon({ brandName: 'A', expiresAt: new Date('2026-08-20T00:00:00Z') });
    const b = coupon({ brandName: 'B', expiresAt: new Date('2026-08-08T00:00:00Z') });
    const c = coupon({ brandName: 'C', expiresAt: null });
    const sorted = sortCoupons([a, c, b], 'EXPIRATION_ASC');
    expect(sorted.map((x) => x.brandName)).toEqual(['B', 'A', 'C']);
  });

  it('breaks ties by newest registration', () => {
    const older = coupon({ brandName: 'older', createdAt: new Date('2026-08-01T00:00:00Z') });
    const newer = coupon({ brandName: 'newer', createdAt: new Date('2026-08-05T00:00:00Z') });
    const sorted = sortCoupons([older, newer], 'EXPIRATION_ASC');
    expect(sorted.map((x) => x.brandName)).toEqual(['newer', 'older']);
  });
});

describe('other sort modes', () => {
  const cheap = coupon({ brandName: 'cheap', faceValueMinor: 1000 });
  const rich = coupon({ brandName: 'rich', faceValueMinor: 50000 });
  const unknown = coupon({ brandName: 'unknown', faceValueMinor: null });

  it('VALUE_DESC orders by amount with unknown values last', () => {
    expect(sortCoupons([cheap, unknown, rich], 'VALUE_DESC').map((x) => x.brandName)).toEqual([
      'rich',
      'cheap',
      'unknown',
    ]);
  });

  it('BRAND_ASC orders alphabetically with null brands last', () => {
    const s = coupon({ brandName: '스타벅스' });
    const b = coupon({ brandName: 'BHC' });
    const n = coupon({ brandName: null });
    expect(sortCoupons([n, s, b], 'BRAND_ASC').map((x) => x.brandName)).toEqual([
      'BHC',
      '스타벅스',
      null,
    ]);
  });

  it('does not mutate the input array', () => {
    const input = [rich, cheap];
    sortCoupons(input, 'VALUE_DESC');
    expect(input.map((x) => x.brandName)).toEqual(['rich', 'cheap']);
  });
});
