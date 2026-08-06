import type { Coupon, CouponAsset } from '@prisma/client';
import type {
  CouponAssetDto,
  CouponDetailDto,
  CouponRecognitionSummaryDto,
} from '@amc/shared-types';
import { toCouponSummaryDto } from './coupon.mapper';

interface StoredRecognitionData {
  confidences?: {
    brand?: number | null;
    productName?: number | null;
    expiresAt?: number | null;
    amountMinor?: number | null;
    barcode?: number | null;
  };
  duplicateSuspects?: string[];
  error?: string;
}

function toRecognitionSummary(raw: unknown): CouponRecognitionSummaryDto | null {
  if (raw === null || typeof raw !== 'object') return null;
  const data = raw as StoredRecognitionData;
  return {
    confidences: {
      brand: data.confidences?.brand ?? null,
      productName: data.confidences?.productName ?? null,
      expiresAt: data.confidences?.expiresAt ?? null,
      amountMinor: data.confidences?.amountMinor ?? null,
      barcode: data.confidences?.barcode ?? null,
    },
    duplicateSuspects: data.duplicateSuspects ?? [],
    error: data.error ?? null,
  };
}

/**
 * Detail DTO keeps the same privacy boundary as the summary: barcode payloads
 * and hashes never leave the server — only `hasBarcode` and the format.
 */
export function toCouponDetailDto(
  coupon: Coupon,
  assets: Array<{ asset: CouponAsset; url: string }>,
): CouponDetailDto {
  return {
    ...toCouponSummaryDto(coupon),
    usageLocationText: coupon.usageLocationText,
    usageConditions: coupon.usageConditions,
    barcodeType: coupon.barcodeType,
    hasBarcode: coupon.encryptedBarcode !== null,
    recognition: toRecognitionSummary(coupon.recognitionData),
    assets: assets.map(({ asset, url }): CouponAssetDto => ({
      type: asset.type,
      url,
      mimeType: asset.mimeType,
    })),
  };
}
