import type { CouponStatus } from '@amc/shared-types';
import { DEFAULT_EXPIRING_SOON_DAYS, isExpired, isExpiringSoon } from './expiration';

/**
 * Status rules (see docs/architecture/DATA_MODEL.md):
 * - PROCESSING resolves to ACTIVE / NEEDS_REVIEW / INVALID after analysis.
 * - Date-driven statuses (EXPIRING_SOON, EXPIRED) are recomputed, never stored
 *   as user intent; the system never resurrects EXPIRED back to ACTIVE.
 * - REDEEMED can only return to ACTIVE through an explicit user restore.
 */

export type TransitionTrigger =
  | 'ANALYSIS_SUCCEEDED'
  | 'ANALYSIS_NEEDS_REVIEW'
  | 'ANALYSIS_FAILED'
  | 'USER_CONFIRMED'
  | 'USER_MARKED_REDEEMED'
  | 'USER_RESTORED'
  | 'USER_ARCHIVED'
  | 'USER_UNARCHIVED'
  | 'CLOCK_EXPIRING_SOON'
  | 'CLOCK_EXPIRED';

const ALLOWED: Record<TransitionTrigger, Array<{ from: CouponStatus; to: CouponStatus }>> = {
  ANALYSIS_SUCCEEDED: [{ from: 'PROCESSING', to: 'ACTIVE' }],
  ANALYSIS_NEEDS_REVIEW: [{ from: 'PROCESSING', to: 'NEEDS_REVIEW' }],
  ANALYSIS_FAILED: [{ from: 'PROCESSING', to: 'INVALID' }],
  USER_CONFIRMED: [{ from: 'NEEDS_REVIEW', to: 'ACTIVE' }],
  USER_MARKED_REDEEMED: [
    { from: 'ACTIVE', to: 'REDEEMED' },
    { from: 'EXPIRING_SOON', to: 'REDEEMED' },
    { from: 'NEEDS_REVIEW', to: 'REDEEMED' },
  ],
  USER_RESTORED: [{ from: 'REDEEMED', to: 'ACTIVE' }],
  USER_ARCHIVED: [
    { from: 'ACTIVE', to: 'ARCHIVED' },
    { from: 'EXPIRING_SOON', to: 'ARCHIVED' },
    { from: 'EXPIRED', to: 'ARCHIVED' },
    { from: 'REDEEMED', to: 'ARCHIVED' },
    { from: 'NEEDS_REVIEW', to: 'ARCHIVED' },
  ],
  USER_UNARCHIVED: [{ from: 'ARCHIVED', to: 'ACTIVE' }],
  CLOCK_EXPIRING_SOON: [{ from: 'ACTIVE', to: 'EXPIRING_SOON' }],
  CLOCK_EXPIRED: [
    { from: 'ACTIVE', to: 'EXPIRED' },
    { from: 'EXPIRING_SOON', to: 'EXPIRED' },
  ],
};

export function canTransition(
  from: CouponStatus,
  to: CouponStatus,
  trigger: TransitionTrigger,
): boolean {
  return ALLOWED[trigger].some((rule) => rule.from === from && rule.to === to);
}

export class InvalidTransitionError extends Error {
  constructor(
    readonly from: CouponStatus,
    readonly to: CouponStatus,
    readonly trigger: TransitionTrigger,
  ) {
    super(`Transition ${from} -> ${to} is not allowed for trigger ${trigger}`);
    this.name = 'InvalidTransitionError';
  }
}

export function transition(
  from: CouponStatus,
  to: CouponStatus,
  trigger: TransitionTrigger,
): CouponStatus {
  if (!canTransition(from, to, trigger)) {
    throw new InvalidTransitionError(from, to, trigger);
  }
  return to;
}

/**
 * Recompute the date-driven status. Statuses expressing user intent or
 * pipeline state (REDEEMED, ARCHIVED, INVALID, PROCESSING, NEEDS_REVIEW) are
 * left untouched; a null expiration keeps the coupon plainly ACTIVE.
 */
export function recomputeDateDrivenStatus(
  current: CouponStatus,
  expiresAt: Date | null,
  now: Date,
  timezoneOffsetMinutes = 0,
  expiringSoonDays = DEFAULT_EXPIRING_SOON_DAYS,
): CouponStatus {
  if (current !== 'ACTIVE' && current !== 'EXPIRING_SOON' && current !== 'EXPIRED') {
    return current;
  }
  if (current === 'EXPIRED') {
    // The system never un-expires a coupon on its own.
    return current;
  }
  if (expiresAt === null) {
    return 'ACTIVE';
  }
  if (isExpired(expiresAt, now, timezoneOffsetMinutes)) {
    return 'EXPIRED';
  }
  if (isExpiringSoon(expiresAt, now, timezoneOffsetMinutes, expiringSoonDays)) {
    return 'EXPIRING_SOON';
  }
  return 'ACTIVE';
}

/** Status a restored (un-redeemed) coupon should land in, given its dates. */
export function statusAfterRestore(
  expiresAt: Date | null,
  now: Date,
  timezoneOffsetMinutes = 0,
): CouponStatus {
  if (expiresAt !== null && isExpired(expiresAt, now, timezoneOffsetMinutes)) {
    return 'EXPIRED';
  }
  return recomputeDateDrivenStatus('ACTIVE', expiresAt, now, timezoneOffsetMinutes);
}
