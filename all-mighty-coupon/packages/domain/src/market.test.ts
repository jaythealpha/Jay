import { describe, expect, it } from 'vitest';
import { calculateFeeMinor, canListCoupon, type ListableCoupon } from './market';

const now = new Date('2026-08-07T00:00:00Z');

function listable(partial: Partial<ListableCoupon> = {}): ListableCoupon {
  return {
    status: 'ACTIVE',
    requiresReview: false,
    hasBarcode: true,
    expiresAt: new Date('2026-12-31T00:00:00Z'),
    ...partial,
  };
}

describe('calculateFeeMinor', () => {
  it('takes 5% as an integer with a 100-won floor', () => {
    expect(calculateFeeMinor(10_000)).toBe(500);
    expect(calculateFeeMinor(23_000)).toBe(1150);
    expect(calculateFeeMinor(500)).toBe(100); // 5% = 25 → floor applies
    expect(calculateFeeMinor(100)).toBe(100);
  });
});

describe('canListCoupon', () => {
  it('accepts a live, reviewed coupon with barcode and runway', () => {
    expect(canListCoupon(listable(), 5000, now)).toEqual({ ok: true });
    expect(canListCoupon(listable({ status: 'EXPIRING_SOON' }), 5000, now)).toEqual({ ok: true });
  });

  it('rejects non-live statuses', () => {
    for (const status of [
      'REDEEMED',
      'EXPIRED',
      'ARCHIVED',
      'NEEDS_REVIEW',
      'PROCESSING',
    ] as const) {
      const result = canListCoupon(listable({ status }), 5000, now);
      expect(result.ok).toBe(false);
    }
  });

  it('rejects unreviewed data, missing barcode, and missing expiry', () => {
    expect(canListCoupon(listable({ requiresReview: true }), 5000, now)).toEqual({
      ok: false,
      reason: 'NEEDS_REVIEW',
    });
    expect(canListCoupon(listable({ hasBarcode: false }), 5000, now)).toEqual({
      ok: false,
      reason: 'NO_BARCODE',
    });
    expect(canListCoupon(listable({ expiresAt: null }), 5000, now)).toEqual({
      ok: false,
      reason: 'NO_EXPIRY',
    });
  });

  it('rejects coupons expiring today or earlier (buyer needs runway)', () => {
    expect(
      canListCoupon(listable({ expiresAt: new Date('2026-08-07T23:00:00Z') }), 5000, now),
    ).toEqual({ ok: false, reason: 'EXPIRES_TOO_SOON' });
    expect(
      canListCoupon(listable({ expiresAt: new Date('2026-08-08T01:00:00Z') }), 5000, now),
    ).toEqual({ ok: true });
  });

  it('rejects out-of-range or non-integer prices', () => {
    expect(canListCoupon(listable(), 50, now)).toEqual({ ok: false, reason: 'PRICE_OUT_OF_RANGE' });
    expect(canListCoupon(listable(), 10_000_001, now)).toEqual({
      ok: false,
      reason: 'PRICE_OUT_OF_RANGE',
    });
    expect(canListCoupon(listable(), 1234.5, now)).toEqual({
      ok: false,
      reason: 'PRICE_OUT_OF_RANGE',
    });
  });
});
