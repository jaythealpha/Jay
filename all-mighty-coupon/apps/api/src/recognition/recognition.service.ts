import { Injectable, Logger } from '@nestjs/common';
import type { Coupon, CouponStatus, Prisma } from '@prisma/client';
import { hashBarcode, maskBarcode } from '@amc/barcode-utils';
import {
  extractExpirationDate,
  extractFaceValue,
  extractProductName,
  matchBrand,
  requiresReview,
} from '@amc/coupon-parser';
import { recomputeDateDrivenStatus, transition } from '@amc/domain';
import type { CouponRecognitionResult } from '@amc/shared-types';
import { BarcodeCryptoService } from '../crypto/barcode-crypto.service';
import { CouponEventsService } from '../events/coupon-events.service';
import { NotificationSchedulerService } from '../notifications/notification-scheduler.service';
import { PrismaService } from '../prisma/prisma.service';
import { StorageService } from '../storage/storage.service';
import { BarcodeDetectorService } from './barcode/barcode-detector';
import { ImageProcessor, UnsupportedImageError } from './image/image-processor';
import { OcrProvider } from './ocr/ocr-provider';

export const PIPELINE_VERSION = 1;

/**
 * Recognition pipeline orchestrator (spec §10). Stages run in order; every
 * outcome is recorded as CouponEvents and the final state lands via the
 * domain transition rules. Unknown values stay null — never fabricated.
 */
@Injectable()
export class RecognitionService {
  private readonly logger = new Logger(RecognitionService.name);

  constructor(
    private readonly prisma: PrismaService,
    private readonly storage: StorageService,
    private readonly imageProcessor: ImageProcessor,
    private readonly barcodeDetector: BarcodeDetectorService,
    private readonly ocrProvider: OcrProvider,
    private readonly barcodeCrypto: BarcodeCryptoService,
    private readonly events: CouponEventsService,
    private readonly notificationScheduler: NotificationSchedulerService,
  ) {}

  async process(couponId: string): Promise<void> {
    const coupon = await this.prisma.coupon.findUnique({
      where: { id: couponId },
      include: { assets: { where: { type: 'ORIGINAL' } } },
    });
    // Idempotency: retried jobs skip coupons that already left PROCESSING.
    if (!coupon || coupon.status !== 'PROCESSING') return;

    const originalAsset = coupon.assets[0];
    if (!originalAsset) {
      await this.finishAs(coupon, 'INVALID', { error: 'no original image asset' });
      return;
    }

    try {
      await this.runPipeline(coupon, originalAsset.storageKey);
    } catch (error) {
      if (error instanceof UnsupportedImageError) {
        await this.finishAs(coupon, 'INVALID', { error: error.message });
        return;
      }
      // Unexpected failure: hand the coupon to the user for manual entry
      // instead of leaving it stuck in PROCESSING (error UX, spec §18).
      this.logger.error(`Recognition failed for coupon ${couponId}`, (error as Error).stack);
      await this.finishAs(coupon, 'NEEDS_REVIEW', { error: 'analysis_failed' });
    }
  }

  private async runPipeline(coupon: Coupon, originalKey: string): Promise<void> {
    const original = await this.storage.getObject(originalKey);
    const processed = await this.imageProcessor.process(original);

    await this.saveDerivedAssets(coupon.id, processed.normalized, processed.thumbnail);

    // Barcode / QR detection — try the normalized image first, fall back to
    // the original bytes (some codes survive better without re-encoding).
    const barcode =
      (await this.barcodeDetector.detect(processed.normalized)) ??
      (await this.barcodeDetector.detect(original));
    if (barcode) {
      await this.events.record(coupon.id, 'BARCODE_DETECTED', {
        format: barcode.format,
        masked: maskBarcode(barcode.value),
      });
    }

    const ocr = await this.ocrProvider.recognize({ normalized: processed.normalized, original });
    await this.events.record(coupon.id, 'OCR_COMPLETED', {
      provider: this.ocrProvider.providerName,
      textLength: ocr.text.length,
    });

    const brand = matchBrand(ocr.text);
    const product = extractProductName(ocr.text, brand?.value ?? null);
    const expiry = extractExpirationDate(ocr.text);
    const amount = extractFaceValue(ocr.text);

    const recognition: CouponRecognitionResult = {
      brand,
      productName: product,
      expiresAt: expiry,
      amountMinor: amount,
      barcodeValuePresent: barcode !== null,
      barcodeConfidence: barcode?.confidence ?? null,
      usageConditions: null,
    };

    const barcodeHashValue = barcode ? hashBarcode(barcode.value) : null;
    const duplicateSuspects = barcodeHashValue
      ? await this.findDuplicateSuspects(coupon, barcodeHashValue)
      : [];

    const anySignal = barcode !== null || brand !== null || expiry !== null || amount !== null;
    const needsReview = requiresReview(recognition);
    const nextStatus: CouponStatus = !anySignal
      ? transition('PROCESSING', 'INVALID', 'ANALYSIS_FAILED')
      : needsReview
        ? transition('PROCESSING', 'NEEDS_REVIEW', 'ANALYSIS_NEEDS_REVIEW')
        : transition('PROCESSING', 'ACTIVE', 'ANALYSIS_SUCCEEDED');

    const expiresAt = expiry ? new Date(`${expiry.value}T00:00:00.000Z`) : null;
    const finalStatus =
      nextStatus === 'ACTIVE'
        ? recomputeDateDrivenStatus('ACTIVE', expiresAt, new Date())
        : nextStatus;

    const recognitionData: Prisma.InputJsonValue = {
      pipelineVersion: PIPELINE_VERSION,
      ocr: { provider: this.ocrProvider.providerName, textLength: ocr.text.length },
      confidences: {
        brand: brand?.confidence ?? null,
        productName: product?.confidence ?? null,
        expiresAt: expiry?.confidence ?? null,
        amountMinor: amount?.confidence ?? null,
        barcode: barcode?.confidence ?? null,
      },
      duplicateSuspects,
    };

    const updatedCoupon = await this.prisma.coupon.update({
      where: { id: coupon.id },
      data: {
        brandName: brand?.value ?? coupon.brandName,
        productName: product?.value ?? coupon.productName,
        faceValueMinor: amount?.value ?? coupon.faceValueMinor,
        currency: amount ? 'KRW' : coupon.currency,
        expiresAt: expiresAt ?? coupon.expiresAt,
        barcodeType: barcode?.format ?? coupon.barcodeType,
        encryptedBarcode: barcode
          ? this.barcodeCrypto.encrypt(barcode.value)
          : coupon.encryptedBarcode,
        barcodeHash: barcodeHashValue ?? coupon.barcodeHash,
        requiresReview: needsReview,
        recognitionData,
        status: finalStatus,
      },
    });

    await this.events.record(coupon.id, 'COUPON_PARSED', {
      fields: {
        brand: brand !== null,
        productName: product !== null,
        expiresAt: expiry !== null,
        amount: amount !== null,
        barcode: barcode !== null,
      },
      duplicateSuspectCount: duplicateSuspects.length,
    });
    await this.events.record(coupon.id, 'STATUS_CHANGED', {
      from: 'PROCESSING',
      to: finalStatus,
    });
    // Live coupons with a recognized expiry get their reminder plan now;
    // NEEDS_REVIEW coupons are scheduled after user confirmation instead.
    await this.notificationScheduler.scheduleFor(updatedCoupon);
  }

  private async saveDerivedAssets(
    couponId: string,
    normalized: Buffer,
    thumbnail: Buffer,
  ): Promise<void> {
    const entries = [
      { type: 'NORMALIZED' as const, key: `coupons/${couponId}/normalized.jpg`, body: normalized },
      { type: 'THUMBNAIL' as const, key: `coupons/${couponId}/thumbnail.jpg`, body: thumbnail },
    ];
    for (const entry of entries) {
      await this.storage.putObject({ key: entry.key, body: entry.body, contentType: 'image/jpeg' });
      await this.prisma.couponAsset.create({
        data: { couponId, type: entry.type, storageKey: entry.key, mimeType: 'image/jpeg' },
      });
    }
  }

  private async findDuplicateSuspects(coupon: Coupon, barcodeHashValue: string): Promise<string[]> {
    const rows = await this.prisma.coupon.findMany({
      where: {
        userId: coupon.userId,
        barcodeHash: barcodeHashValue,
        id: { not: coupon.id },
      },
      select: { id: true },
      take: 5,
    });
    return rows.map((row) => row.id);
  }

  private async finishAs(
    coupon: Coupon,
    status: 'INVALID' | 'NEEDS_REVIEW',
    detail: Record<string, string>,
  ): Promise<void> {
    await this.prisma.coupon.update({
      where: { id: coupon.id },
      data: {
        status,
        requiresReview: true,
        recognitionData: { pipelineVersion: PIPELINE_VERSION, ...detail },
      },
    });
    await this.events.record(coupon.id, 'STATUS_CHANGED', {
      from: 'PROCESSING',
      to: status,
      ...detail,
    });
  }
}
