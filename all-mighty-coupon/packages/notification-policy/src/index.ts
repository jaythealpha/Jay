/**
 * Expiration-notification policy as pure domain logic (spec §16). Milestone 0
 * ships the policy + tests only; actual push delivery is a later milestone.
 *
 * Default touchpoints: 30 days, 7 days, 3 days before, and the morning of the
 * expiration day. Touchpoints already in the past are simply not scheduled.
 */

export const DEFAULT_OFFSETS_DAYS = [30, 7, 3, 0] as const;

/** Local-time hour at which reminder notifications fire. */
export const NOTIFY_HOUR_LOCAL = 9;

export interface PlannedNotification {
  /** Days before expiration (0 = expiration day). */
  offsetDays: number;
  /** UTC instant at which the notification should fire. */
  fireAt: Date;
}

function startOfLocalDay(instant: Date, timezoneOffsetMinutes: number): Date {
  const shifted = new Date(instant.getTime() + timezoneOffsetMinutes * 60_000);
  const dayStartShifted = Date.UTC(
    shifted.getUTCFullYear(),
    shifted.getUTCMonth(),
    shifted.getUTCDate(),
  );
  return new Date(dayStartShifted - timezoneOffsetMinutes * 60_000);
}

/**
 * Plans reminder instants for a coupon. Only future touchpoints are returned:
 * registering a coupon 5 days before expiry yields the 3-day and same-day
 * reminders, never a back-dated 30-day one.
 */
export function planExpirationNotifications(params: {
  expiresAt: Date;
  now: Date;
  timezoneOffsetMinutes?: number;
  offsetsDays?: readonly number[];
}): PlannedNotification[] {
  const { expiresAt, now } = params;
  const tz = params.timezoneOffsetMinutes ?? 0;
  const offsets = params.offsetsDays ?? DEFAULT_OFFSETS_DAYS;

  const expirationDayStart = startOfLocalDay(expiresAt, tz);
  return offsets
    .map((offsetDays) => ({
      offsetDays,
      fireAt: new Date(
        expirationDayStart.getTime() - offsetDays * 86_400_000 + NOTIFY_HOUR_LOCAL * 3_600_000,
      ),
    }))
    .filter((n) => n.fireAt.getTime() > now.getTime())
    .sort((a, b) => a.fireAt.getTime() - b.fireAt.getTime());
}

/** Coupon states whose pending expiration reminders must be cancelled. */
export function shouldCancelNotifications(
  status: 'REDEEMED' | 'ARCHIVED' | 'EXPIRED' | 'ACTIVE' | 'EXPIRING_SOON' | string,
  deleted = false,
): boolean {
  return deleted || status === 'REDEEMED' || status === 'ARCHIVED';
}

export interface NotificationMessageInput {
  brandName: string | null;
  productName: string | null;
  faceValueMinor: number | null;
  daysLeft: number;
}

/**
 * Message content rule: always name the brand and the product (or amount) and
 * the remaining time — "스타벅스 아메리카노 쿠폰이 3일 뒤 만료됩니다", never a
 * bare "쿠폰이 곧 만료됩니다".
 */
export function buildNotificationMessage(input: NotificationMessageInput): string {
  const brand = input.brandName ?? '등록된';
  const item =
    input.productName ??
    (input.faceValueMinor !== null ? `${input.faceValueMinor.toLocaleString('ko-KR')}원` : '');
  const subject = [brand, item, '쿠폰이'].filter((part) => part.length > 0).join(' ');
  if (input.daysLeft <= 0) {
    return `${subject} 오늘 만료됩니다.`;
  }
  return `${subject} ${input.daysLeft}일 뒤 만료됩니다.`;
}
