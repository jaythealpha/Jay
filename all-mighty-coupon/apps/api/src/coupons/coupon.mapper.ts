import type { Coupon } from '@prisma/client';
import type { CouponSummaryDto } from '@amc/shared-types';

/**
 * DB row -> wire DTO. This mapping is the privacy boundary: encryptedBarcode,
 * barcodeHash, and full recognitionData deliberately never leave the server
 * through list/summary responses.
 */
export function toCouponSummaryDto(coupon: Coupon): CouponSummaryDto {
  return {
    id: coupon.id,
    brandName: coupon.brandName,
    productName: coupon.productName,
    category: coupon.category,
    faceValueMinor: coupon.faceValueMinor,
    currency: coupon.currency,
    status: coupon.status,
    expiresAt: coupon.expiresAt ? coupon.expiresAt.toISOString() : null,
    requiresReview: coupon.requiresReview,
    sourceType: coupon.sourceType,
    createdAt: coupon.createdAt.toISOString(),
    updatedAt: coupon.updatedAt.toISOString(),
  };
}
