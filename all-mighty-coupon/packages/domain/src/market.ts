import type { CouponStatus } from '@amc/shared-types';
import { daysUntilExpiration } from './expiration';

/**
 * Market rules (Milestone 4). Pure policy — enforcement lives in the API.
 * Fees are integers in KRW like every other amount; no floats anywhere.
 */

export const MARKET_FEE_RATE = 0.05;
export const MARKET_MIN_FEE_MINOR = 100;
export const MIN_LISTING_PRICE_MINOR = 100;
export const MAX_LISTING_PRICE_MINOR = 10_000_000;
/** A coupon must survive at least this long for a buyer to use it. */
export const MIN_DAYS_LEFT_TO_LIST = 1;

export function calculateFeeMinor(priceMinor: number): number {
  return Math.max(MARKET_MIN_FEE_MINOR, Math.round(priceMinor * MARKET_FEE_RATE));
}

export type ListingRejection =
  | 'NOT_LIVE'
  | 'NEEDS_REVIEW'
  | 'NO_BARCODE'
  | 'NO_EXPIRY'
  | 'EXPIRES_TOO_SOON'
  | 'PRICE_OUT_OF_RANGE';

export interface ListableCoupon {
  status: CouponStatus;
  requiresReview: boolean;
  hasBarcode: boolean;
  expiresAt: Date | null;
}

/**
 * A coupon may be listed only when a buyer can actually use what they pay
 * for: live status, reviewed data, a stored barcode, and enough runway
 * before expiry.
 */
export function canListCoupon(
  coupon: ListableCoupon,
  priceMinor: number,
  now: Date,
): { ok: true } | { ok: false; reason: ListingRejection } {
  if (coupon.status !== 'ACTIVE' && coupon.status !== 'EXPIRING_SOON') {
    return { ok: false, reason: 'NOT_LIVE' };
  }
  if (coupon.requiresReview) {
    return { ok: false, reason: 'NEEDS_REVIEW' };
  }
  if (!coupon.hasBarcode) {
    return { ok: false, reason: 'NO_BARCODE' };
  }
  if (coupon.expiresAt === null) {
    return { ok: false, reason: 'NO_EXPIRY' };
  }
  if (daysUntilExpiration(coupon.expiresAt, now) < MIN_DAYS_LEFT_TO_LIST) {
    return { ok: false, reason: 'EXPIRES_TOO_SOON' };
  }
  if (
    !Number.isInteger(priceMinor) ||
    priceMinor < MIN_LISTING_PRICE_MINOR ||
    priceMinor > MAX_LISTING_PRICE_MINOR
  ) {
    return { ok: false, reason: 'PRICE_OUT_OF_RANGE' };
  }
  return { ok: true };
}

export const LISTING_REJECTION_MESSAGES: Record<ListingRejection, string> = {
  NOT_LIVE: '사용 가능 상태의 쿠폰만 판매할 수 있습니다.',
  NEEDS_REVIEW: '인식 결과 확인이 끝난 쿠폰만 판매할 수 있습니다.',
  NO_BARCODE: '바코드가 저장된 쿠폰만 판매할 수 있습니다.',
  NO_EXPIRY: '유효기간이 확인된 쿠폰만 판매할 수 있습니다.',
  EXPIRES_TOO_SOON: '유효기간이 하루 이상 남은 쿠폰만 판매할 수 있습니다.',
  PRICE_OUT_OF_RANGE: '판매 가격은 100원 이상 10,000,000원 이하의 정수여야 합니다.',
};
