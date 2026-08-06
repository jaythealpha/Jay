import type { CouponStatus } from '@amc/shared-types';

export interface SortableCoupon {
  status: CouponStatus;
  expiresAt: Date | null;
  createdAt: Date;
  faceValueMinor: number | null;
  brandName: string | null;
}

export type WalletSortMode = 'EXPIRATION_ASC' | 'CREATED_DESC' | 'VALUE_DESC' | 'BRAND_ASC';

/**
 * Default wallet order: soonest expiration first ("Expiration First"
 * principle). Coupons without an expiration sort after dated ones; ties fall
 * back to newest registration.
 */
export function compareByExpiration(a: SortableCoupon, b: SortableCoupon): number {
  if (a.expiresAt !== null && b.expiresAt !== null) {
    const diff = a.expiresAt.getTime() - b.expiresAt.getTime();
    if (diff !== 0) return diff;
  } else if (a.expiresAt !== null) {
    return -1;
  } else if (b.expiresAt !== null) {
    return 1;
  }
  return b.createdAt.getTime() - a.createdAt.getTime();
}

export function sortCoupons<T extends SortableCoupon>(
  coupons: readonly T[],
  mode: WalletSortMode,
): T[] {
  const copy = [...coupons];
  switch (mode) {
    case 'EXPIRATION_ASC':
      return copy.sort(compareByExpiration);
    case 'CREATED_DESC':
      return copy.sort((a, b) => b.createdAt.getTime() - a.createdAt.getTime());
    case 'VALUE_DESC':
      return copy.sort((a, b) => (b.faceValueMinor ?? -1) - (a.faceValueMinor ?? -1));
    case 'BRAND_ASC':
      return copy.sort((a, b) => (a.brandName ?? '￿').localeCompare(b.brandName ?? '￿'));
  }
}
