import type { CouponRecognitionResult } from '@amc/shared-types';

/**
 * Trust policy (spec §11):
 * - >= 0.90 auto-apply, 0.70–0.90 apply-but-confirm, < 0.70 needs review
 * - expiration date is critical: anything below 0.95 forces user review
 * - missing critical fields force review; unknown values stay null
 */

export const AUTO_APPLY_THRESHOLD = 0.9;
export const CONFIRM_THRESHOLD = 0.7;
export const EXPIRATION_TRUST_THRESHOLD = 0.95;

export type FieldReviewLevel = 'AUTO' | 'CONFIRM' | 'REVIEW';

export function fieldReviewLevel(confidence: number): FieldReviewLevel {
  if (confidence >= AUTO_APPLY_THRESHOLD) return 'AUTO';
  if (confidence >= CONFIRM_THRESHOLD) return 'CONFIRM';
  return 'REVIEW';
}

export function requiresReview(result: CouponRecognitionResult): boolean {
  if (result.expiresAt === null) return true;
  if (result.expiresAt.confidence < EXPIRATION_TRUST_THRESHOLD) return true;
  if (result.brand === null || fieldReviewLevel(result.brand.confidence) === 'REVIEW') return true;
  const hasValue = result.amountMinor !== null || result.productName !== null;
  if (!hasValue) return true;
  if (result.amountMinor !== null && fieldReviewLevel(result.amountMinor.confidence) === 'REVIEW') {
    return true;
  }
  return false;
}
