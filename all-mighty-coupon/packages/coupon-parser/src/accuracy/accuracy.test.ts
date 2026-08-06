import { describe, expect, it } from 'vitest';
import { measureAccuracy } from './measure';

/**
 * Regression floor for parser accuracy on the curated dataset. Thresholds sit
 * below the current 100% so honest dataset growth (harder samples) doesn't
 * instantly break CI, while real regressions still do. NOTE: this measures
 * text-parsing accuracy on synthetic OCR text — not end-to-end image OCR.
 */
describe('parser accuracy on dataset', () => {
  const report = measureAccuracy();

  it('keeps brand accuracy at or above 90%', () => {
    expect(report.brand.accuracy).toBeGreaterThanOrEqual(0.9);
  });

  it('keeps expiration accuracy at or above 90%', () => {
    expect(report.expiresAt.accuracy).toBeGreaterThanOrEqual(0.9);
  });

  it('keeps amount accuracy at or above 90%', () => {
    expect(report.amountMinor.accuracy).toBeGreaterThanOrEqual(0.9);
  });

  it('never invents values for the non-coupon sample', () => {
    const failures = [
      ...report.brand.failures,
      ...report.expiresAt.failures,
      ...report.amountMinor.failures,
    ];
    expect(failures.filter((f) => f.id === 'not-a-coupon')).toEqual([]);
  });
});
