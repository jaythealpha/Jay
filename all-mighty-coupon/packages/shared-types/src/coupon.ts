export const COUPON_STATUSES = [
  'PROCESSING',
  'NEEDS_REVIEW',
  'ACTIVE',
  'EXPIRING_SOON',
  'EXPIRED',
  'REDEEMED',
  'ARCHIVED',
  'INVALID',
] as const;
export type CouponStatus = (typeof COUPON_STATUSES)[number];

export const COUPON_SOURCE_TYPES = [
  'CAMERA',
  'PHOTO_LIBRARY',
  'SHARE_EXTENSION',
  'FILE_UPLOAD',
  'MANUAL',
] as const;
export type CouponSourceType = (typeof COUPON_SOURCE_TYPES)[number];

export const COUPON_ASSET_TYPES = ['ORIGINAL', 'NORMALIZED', 'THUMBNAIL', 'BARCODE_CROP'] as const;
export type CouponAssetType = (typeof COUPON_ASSET_TYPES)[number];

export const COUPON_EVENT_TYPES = [
  'COUPON_CREATED',
  'IMAGE_UPLOADED',
  'BARCODE_DETECTED',
  'OCR_COMPLETED',
  'COUPON_PARSED',
  'USER_CONFIRMED',
  'USER_EDITED',
  'STATUS_CHANGED',
  'NOTIFICATION_SCHEDULED',
  'NOTIFICATION_SENT',
  'BARCODE_VIEWED',
  'MARKED_REDEEMED',
  'RESTORED_TO_ACTIVE',
  'ARCHIVED',
  'DELETED',
] as const;
export type CouponEventType = (typeof COUPON_EVENT_TYPES)[number];

/**
 * Wire representation of a coupon as returned by the API.
 * Barcode payloads are intentionally absent: the raw value is sensitive and
 * only exposed through a dedicated, audited endpoint (post-Milestone 0).
 */
export interface CouponSummaryDto {
  id: string;
  brandName: string | null;
  productName: string | null;
  category: string | null;
  faceValueMinor: number | null;
  currency: string | null;
  status: CouponStatus;
  /** ISO-8601 UTC timestamp; clients convert to the user's timezone. */
  expiresAt: string | null;
  requiresReview: boolean;
  sourceType: CouponSourceType;
  createdAt: string;
  updatedAt: string;
}

export interface CouponListResponseDto {
  items: CouponSummaryDto[];
  total: number;
}

export interface CouponAssetDto {
  type: CouponAssetType;
  /** Short-lived signed URL — do not persist. */
  url: string;
  mimeType: string;
}

export interface CouponRecognitionSummaryDto {
  /** Per-field confidence in [0,1]; null when the field was not recognized. */
  confidences: {
    brand: number | null;
    productName: number | null;
    expiresAt: number | null;
    amountMinor: number | null;
    barcode: number | null;
  };
  /** IDs of same-user coupons sharing this barcode hash (never auto-deleted). */
  duplicateSuspects: string[];
  /** Present when the pipeline failed and the coupon needs manual entry. */
  error: string | null;
}

/**
 * Market wire types (Milestone 4). Seller identity never crosses the wire —
 * buyers see the coupon, the price, and nothing about who is selling.
 */
export interface MarketCouponDto {
  brandName: string | null;
  productName: string | null;
  category: string | null;
  faceValueMinor: number | null;
  /** ISO-8601 UTC. Always present — undated coupons cannot be listed. */
  expiresAt: string | null;
}

export interface ListingDto {
  id: string;
  priceMinor: number;
  feeMinor: number;
  status: 'LISTED' | 'SOLD' | 'CANCELLED';
  /** True when the requesting user is the seller. */
  mine: boolean;
  coupon: MarketCouponDto;
  createdAt: string;
}

export interface MarketListResponseDto {
  items: ListingDto[];
  total: number;
}

export interface OrderDto {
  id: string;
  role: 'BUYER' | 'SELLER';
  priceMinor: number;
  feeMinor: number;
  status: 'CREATED' | 'COMPLETED' | 'FAILED';
  coupon: MarketCouponDto;
  createdAt: string;
}

export interface CouponDetailDto extends CouponSummaryDto {
  usageLocationText: string | null;
  usageConditions: string | null;
  barcodeType: string | null;
  /** True when an (encrypted) barcode payload exists for this coupon. */
  hasBarcode: boolean;
  recognition: CouponRecognitionSummaryDto | null;
  assets: CouponAssetDto[];
}
