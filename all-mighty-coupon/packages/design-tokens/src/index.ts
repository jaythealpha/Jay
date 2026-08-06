/**
 * Design tokens shared between admin web and (manually mirrored) Flutter theme.
 * Direction: trustworthy, fast, tidy — no gradients, no gamification (spec §20).
 * Status colors are always paired with an icon + label in UI; color alone
 * never carries meaning (accessibility, spec §19).
 */

export const colors = {
  primary: '#1B5E4A',
  primaryLight: '#E4F2ED',
  textPrimary: '#1A1D1C',
  textSecondary: '#5A6360',
  surface: '#FFFFFF',
  background: '#F6F8F7',
  border: '#DCE3E0',
  statusActive: '#1B5E4A',
  statusExpiringSoon: '#B45309',
  statusExpired: '#8A8F8D',
  statusRedeemed: '#4B5563',
  statusNeedsReview: '#1D4ED8',
  danger: '#B3261E',
} as const;

export const spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
} as const;

export const typography = {
  fontFamilyKorean: "'Pretendard', 'Noto Sans KR', sans-serif",
  /** Minimum touch target in logical pixels (44pt rule). */
  minTouchTarget: 44,
} as const;

export const radii = {
  card: 12,
  button: 10,
} as const;
