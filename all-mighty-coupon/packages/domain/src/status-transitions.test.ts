import { describe, expect, it } from 'vitest';
import {
  canTransition,
  InvalidTransitionError,
  recomputeDateDrivenStatus,
  statusAfterRestore,
  transition,
} from './status-transitions';

describe('transition rules', () => {
  it('resolves PROCESSING to ACTIVE or NEEDS_REVIEW after analysis', () => {
    expect(canTransition('PROCESSING', 'ACTIVE', 'ANALYSIS_SUCCEEDED')).toBe(true);
    expect(canTransition('PROCESSING', 'NEEDS_REVIEW', 'ANALYSIS_NEEDS_REVIEW')).toBe(true);
    expect(canTransition('PROCESSING', 'INVALID', 'ANALYSIS_FAILED')).toBe(true);
  });

  it('allows explicit user restore from REDEEMED only', () => {
    expect(canTransition('REDEEMED', 'ACTIVE', 'USER_RESTORED')).toBe(true);
    expect(canTransition('EXPIRED', 'ACTIVE', 'USER_RESTORED')).toBe(false);
  });

  it('never lets the clock un-expire a coupon', () => {
    expect(canTransition('EXPIRED', 'ACTIVE', 'CLOCK_EXPIRING_SOON')).toBe(false);
    expect(canTransition('EXPIRED', 'EXPIRING_SOON', 'CLOCK_EXPIRING_SOON')).toBe(false);
  });

  it('throws a typed error on invalid transitions', () => {
    expect(() => transition('EXPIRED', 'ACTIVE', 'USER_RESTORED')).toThrow(InvalidTransitionError);
    expect(transition('ACTIVE', 'REDEEMED', 'USER_MARKED_REDEEMED')).toBe('REDEEMED');
  });
});

describe('recomputeDateDrivenStatus', () => {
  const now = new Date('2026-08-06T10:00:00Z');

  it('moves ACTIVE into EXPIRING_SOON inside the window', () => {
    const soon = new Date('2026-08-09T00:00:00Z');
    expect(recomputeDateDrivenStatus('ACTIVE', soon, now)).toBe('EXPIRING_SOON');
  });

  it('moves ACTIVE and EXPIRING_SOON into EXPIRED after the date', () => {
    const past = new Date('2026-08-01T00:00:00Z');
    expect(recomputeDateDrivenStatus('ACTIVE', past, now)).toBe('EXPIRED');
    expect(recomputeDateDrivenStatus('EXPIRING_SOON', past, now)).toBe('EXPIRED');
  });

  it('returns EXPIRING_SOON back to ACTIVE when the date moves out', () => {
    const far = new Date('2026-12-31T00:00:00Z');
    expect(recomputeDateDrivenStatus('EXPIRING_SOON', far, now)).toBe('ACTIVE');
  });

  it('leaves user-intent and pipeline statuses untouched', () => {
    const past = new Date('2026-08-01T00:00:00Z');
    for (const status of [
      'REDEEMED',
      'ARCHIVED',
      'INVALID',
      'PROCESSING',
      'NEEDS_REVIEW',
    ] as const) {
      expect(recomputeDateDrivenStatus(status, past, now)).toBe(status);
    }
  });

  it('never resurrects EXPIRED automatically', () => {
    const future = new Date('2026-12-31T00:00:00Z');
    expect(recomputeDateDrivenStatus('EXPIRED', future, now)).toBe('EXPIRED');
  });

  it('treats missing expiration as plainly ACTIVE', () => {
    expect(recomputeDateDrivenStatus('ACTIVE', null, now)).toBe('ACTIVE');
  });
});

describe('statusAfterRestore', () => {
  const now = new Date('2026-08-06T10:00:00Z');

  it('restores to EXPIRED when the date already passed', () => {
    expect(statusAfterRestore(new Date('2026-08-01T00:00:00Z'), now)).toBe('EXPIRED');
  });

  it('restores to EXPIRING_SOON or ACTIVE based on the date', () => {
    expect(statusAfterRestore(new Date('2026-08-09T00:00:00Z'), now)).toBe('EXPIRING_SOON');
    expect(statusAfterRestore(new Date('2026-12-31T00:00:00Z'), now)).toBe('ACTIVE');
    expect(statusAfterRestore(null, now)).toBe('ACTIVE');
  });
});
