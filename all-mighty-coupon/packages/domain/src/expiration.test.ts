import { describe, expect, it } from 'vitest';
import { daysUntilExpiration, isExpired, isExpiringSoon } from './expiration';

const KST = 9 * 60;

describe('daysUntilExpiration', () => {
  it('returns 0 when the coupon expires later the same day', () => {
    const now = new Date('2026-08-06T01:00:00Z');
    const expires = new Date('2026-08-06T23:59:59Z');
    expect(daysUntilExpiration(expires, now)).toBe(0);
  });

  it('returns whole-day differences across day boundaries', () => {
    const now = new Date('2026-08-06T23:00:00Z');
    const expires = new Date('2026-08-09T01:00:00Z');
    expect(daysUntilExpiration(expires, now)).toBe(3);
  });

  it('is negative once the expiration day has passed', () => {
    const now = new Date('2026-08-06T00:00:00Z');
    const expires = new Date('2026-08-05T23:59:59Z');
    expect(daysUntilExpiration(expires, now)).toBe(-1);
  });

  it('respects the user timezone when the boundary differs from UTC', () => {
    // 2026-08-06 23:30 UTC is already 2026-08-07 08:30 in KST.
    const now = new Date('2026-08-06T23:30:00Z');
    const expires = new Date('2026-08-07T10:00:00Z'); // KST 19:00 same day
    expect(daysUntilExpiration(expires, now, KST)).toBe(0);
    expect(daysUntilExpiration(expires, now, 0)).toBe(1);
  });
});

describe('isExpired', () => {
  it('does not treat "expires today" as expired', () => {
    const now = new Date('2026-08-06T10:00:00Z');
    expect(isExpired(new Date('2026-08-06T00:00:00Z'), now)).toBe(false);
    expect(isExpired(new Date('2026-08-05T00:00:00Z'), now)).toBe(true);
  });
});

describe('isExpiringSoon', () => {
  const now = new Date('2026-08-06T10:00:00Z');

  it('flags coupons inside the window, inclusive', () => {
    expect(isExpiringSoon(new Date('2026-08-06T12:00:00Z'), now)).toBe(true);
    expect(isExpiringSoon(new Date('2026-08-13T12:00:00Z'), now)).toBe(true);
  });

  it('excludes coupons beyond the window or already expired', () => {
    expect(isExpiringSoon(new Date('2026-08-14T12:00:00Z'), now)).toBe(false);
    expect(isExpiringSoon(new Date('2026-08-05T12:00:00Z'), now)).toBe(false);
  });

  it('supports a custom window', () => {
    expect(isExpiringSoon(new Date('2026-09-01T00:00:00Z'), now, 0, 30)).toBe(true);
  });
});
