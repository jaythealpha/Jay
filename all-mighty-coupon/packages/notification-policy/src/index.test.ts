import { describe, expect, it } from 'vitest';
import {
  buildNotificationMessage,
  planExpirationNotifications,
  shouldCancelNotifications,
} from './index';

const KST = 9 * 60;

describe('planExpirationNotifications', () => {
  it('plans 30/7/3/same-day reminders for a far-future expiration', () => {
    const plan = planExpirationNotifications({
      expiresAt: new Date('2026-12-31T00:00:00Z'),
      now: new Date('2026-08-06T00:00:00Z'),
    });
    expect(plan.map((n) => n.offsetDays)).toEqual([30, 7, 3, 0]);
  });

  it('keeps only remaining touchpoints when registered 5 days before expiry', () => {
    const plan = planExpirationNotifications({
      expiresAt: new Date('2026-08-11T12:00:00Z'),
      now: new Date('2026-08-06T12:00:00Z'),
    });
    expect(plan.map((n) => n.offsetDays)).toEqual([3, 0]);
  });

  it('fires at 09:00 in the user timezone', () => {
    const plan = planExpirationNotifications({
      expiresAt: new Date('2026-08-11T00:00:00Z'), // KST 2026-08-11 09:00
      now: new Date('2026-08-01T00:00:00Z'),
      timezoneOffsetMinutes: KST,
    });
    const sameDay = plan.find((n) => n.offsetDays === 0);
    // 09:00 KST on the expiration day == 00:00 UTC
    expect(sameDay?.fireAt.toISOString()).toBe('2026-08-11T00:00:00.000Z');
  });

  it('returns an empty plan when everything is already past', () => {
    const plan = planExpirationNotifications({
      expiresAt: new Date('2026-08-01T00:00:00Z'),
      now: new Date('2026-08-06T00:00:00Z'),
    });
    expect(plan).toEqual([]);
  });
});

describe('shouldCancelNotifications', () => {
  it('cancels on redeem, archive, or delete', () => {
    expect(shouldCancelNotifications('REDEEMED')).toBe(true);
    expect(shouldCancelNotifications('ARCHIVED')).toBe(true);
    expect(shouldCancelNotifications('ACTIVE', true)).toBe(true);
  });

  it('keeps reminders for live coupons', () => {
    expect(shouldCancelNotifications('ACTIVE')).toBe(false);
    expect(shouldCancelNotifications('EXPIRING_SOON')).toBe(false);
  });
});

describe('buildNotificationMessage', () => {
  it('names brand, product, and remaining days', () => {
    const message = buildNotificationMessage({
      brandName: '스타벅스',
      productName: '아메리카노',
      faceValueMinor: null,
      daysLeft: 3,
    });
    expect(message).toBe('스타벅스 아메리카노 쿠폰이 3일 뒤 만료됩니다.');
  });

  it('falls back to the amount when there is no product name', () => {
    const message = buildNotificationMessage({
      brandName: '이마트',
      productName: null,
      faceValueMinor: 30000,
      daysLeft: 7,
    });
    expect(message).toBe('이마트 30,000원 쿠폰이 7일 뒤 만료됩니다.');
  });

  it('uses same-day wording for day 0', () => {
    const message = buildNotificationMessage({
      brandName: '스타벅스',
      productName: '아메리카노',
      faceValueMinor: null,
      daysLeft: 0,
    });
    expect(message).toBe('스타벅스 아메리카노 쿠폰이 오늘 만료됩니다.');
  });
});
