import type { CouponRecognitionResult } from '@amc/shared-types';
import { describe, expect, it } from 'vitest';
import { fieldReviewLevel, requiresReview } from './review-policy';

function result(partial: Partial<CouponRecognitionResult>): CouponRecognitionResult {
  return {
    brand: { value: '스타벅스', confidence: 0.95 },
    productName: { value: '아메리카노 Tall', confidence: 0.9 },
    expiresAt: { value: '2026-12-31', confidence: 0.96 },
    amountMinor: { value: 4500, confidence: 0.9 },
    barcodeValuePresent: true,
    barcodeConfidence: 0.99,
    usageConditions: null,
    ...partial,
  };
}

describe('fieldReviewLevel', () => {
  it('maps thresholds per the trust policy', () => {
    expect(fieldReviewLevel(0.95)).toBe('AUTO');
    expect(fieldReviewLevel(0.8)).toBe('CONFIRM');
    expect(fieldReviewLevel(0.5)).toBe('REVIEW');
  });
});

describe('requiresReview', () => {
  it('passes a fully confident result', () => {
    expect(requiresReview(result({}))).toBe(false);
  });

  it('forces review when the expiration confidence is below 0.95', () => {
    expect(requiresReview(result({ expiresAt: { value: '2026-12-31', confidence: 0.94 } }))).toBe(
      true,
    );
  });

  it('forces review when the expiration is missing entirely', () => {
    expect(requiresReview(result({ expiresAt: null }))).toBe(true);
  });

  it('forces review on unknown brand or low-confidence amount', () => {
    expect(requiresReview(result({ brand: null }))).toBe(true);
    expect(requiresReview(result({ amountMinor: { value: 4500, confidence: 0.5 } }))).toBe(true);
  });

  it('forces review when neither amount nor product name was recognized', () => {
    expect(requiresReview(result({ amountMinor: null, productName: null }))).toBe(true);
  });
});
