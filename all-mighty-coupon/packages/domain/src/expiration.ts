/**
 * Expiration math lives here so every surface (API, workers, mobile parity
 * tests) computes "days left" identically. All inputs are UTC instants; the
 * user's timezone offset decides where the day boundary falls for them.
 */

export const DEFAULT_EXPIRING_SOON_DAYS = 7;

/** Calendar date (year/month/day) of an instant shifted by a timezone offset. */
function calendarDayIndex(instant: Date, timezoneOffsetMinutes: number): number {
  const shifted = new Date(instant.getTime() + timezoneOffsetMinutes * 60_000);
  return Math.floor(shifted.getTime() / 86_400_000);
}

/**
 * Whole calendar days from `now` until `expiresAt` in the user's timezone.
 * 0 = expires today, negative = already past.
 */
export function daysUntilExpiration(expiresAt: Date, now: Date, timezoneOffsetMinutes = 0): number {
  return (
    calendarDayIndex(expiresAt, timezoneOffsetMinutes) -
    calendarDayIndex(now, timezoneOffsetMinutes)
  );
}

export function isExpired(expiresAt: Date, now: Date, timezoneOffsetMinutes = 0): boolean {
  return daysUntilExpiration(expiresAt, now, timezoneOffsetMinutes) < 0;
}

export function isExpiringSoon(
  expiresAt: Date,
  now: Date,
  timezoneOffsetMinutes = 0,
  withinDays = DEFAULT_EXPIRING_SOON_DAYS,
): boolean {
  const days = daysUntilExpiration(expiresAt, now, timezoneOffsetMinutes);
  return days >= 0 && days <= withinDays;
}
