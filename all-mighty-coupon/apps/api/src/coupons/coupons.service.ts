import { BadRequestException, Injectable, Logger, NotFoundException } from '@nestjs/common';
import type { Coupon, CouponSourceType, Prisma } from '@prisma/client';
import {
  COUPON_SOURCE_TYPES,
  COUPON_STATUSES,
  type CouponDetailDto,
  type CouponListResponseDto,
  type CouponStatus,
} from '@amc/shared-types';
import { maskBarcode } from '@amc/barcode-utils';
import {
  canTransition,
  recomputeDateDrivenStatus,
  statusAfterRestore,
  transition,
  type TransitionTrigger,
} from '@amc/domain';
import { BarcodeCryptoService } from '../crypto/barcode-crypto.service';
import { CouponEventsService } from '../events/coupon-events.service';
import { NotificationSchedulerService } from '../notifications/notification-scheduler.service';
import { PrismaService } from '../prisma/prisma.service';
import { RecognitionQueueService } from '../recognition/recognition.queue';
import { StorageService } from '../storage/storage.service';
import { toCouponDetailDto } from './coupon-detail.mapper';
import { toCouponSummaryDto } from './coupon.mapper';

export const WALLET_SORTS = ['EXPIRATION_ASC', 'CREATED_DESC', 'VALUE_DESC', 'BRAND_ASC'] as const;
export type WalletSort = (typeof WALLET_SORTS)[number];

export interface ListCouponsQuery {
  status?: string;
  q?: string;
  sort?: string;
  limit?: number;
}

export interface UploadedImage {
  buffer: Buffer;
  mimetype: string;
  size: number;
}

export interface EditCouponInput {
  brandName?: string | null;
  productName?: string | null;
  category?: string | null;
  faceValueMinor?: number | null;
  expiresAt?: string | null;
  usageLocationText?: string | null;
  usageConditions?: string | null;
}

export interface BarcodeRevealDto {
  value: string;
  format: string | null;
}

const DEFAULT_LIMIT = 50;
const MAX_LIMIT = 100;
const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
const ALLOWED_MIME = new Map([
  ['image/jpeg', 'jpg'],
  ['image/png', 'png'],
  ['image/webp', 'webp'],
]);

const SORT_ORDER: Record<WalletSort, Prisma.CouponOrderByWithRelationInput[]> = {
  // Expiration First: soonest expiration on top, undated coupons last.
  EXPIRATION_ASC: [{ expiresAt: { sort: 'asc', nulls: 'last' } }, { createdAt: 'desc' }],
  CREATED_DESC: [{ createdAt: 'desc' }],
  VALUE_DESC: [{ faceValueMinor: { sort: 'desc', nulls: 'last' } }, { createdAt: 'desc' }],
  BRAND_ASC: [{ brandName: { sort: 'asc', nulls: 'last' } }, { createdAt: 'desc' }],
};

/** All operations are scoped to the authenticated user (Milestone 2). */
@Injectable()
export class CouponsService {
  private readonly logger = new Logger(CouponsService.name);

  constructor(
    private readonly prisma: PrismaService,
    private readonly storage: StorageService,
    private readonly recognitionQueue: RecognitionQueueService,
    private readonly events: CouponEventsService,
    private readonly barcodeCrypto: BarcodeCryptoService,
    private readonly notificationScheduler: NotificationSchedulerService,
  ) {}

  async list(userId: string, query: ListCouponsQuery): Promise<CouponListResponseDto> {
    const status = this.parseStatus(query.status);
    const sort = this.parseSort(query.sort);
    const limit = Math.min(query.limit ?? DEFAULT_LIMIT, MAX_LIMIT);
    const q = query.q?.trim();

    const where: Prisma.CouponWhereInput = {
      userId,
      ...(status ? { status } : {}),
      ...(q
        ? {
            OR: [
              { brandName: { contains: q, mode: 'insensitive' } },
              { productName: { contains: q, mode: 'insensitive' } },
              { category: { contains: q, mode: 'insensitive' } },
            ],
          }
        : {}),
    };

    const [rows, total] = await Promise.all([
      this.prisma.coupon.findMany({ where, orderBy: SORT_ORDER[sort], take: limit }),
      this.prisma.coupon.count({ where }),
    ]);

    return { items: rows.map(toCouponSummaryDto), total };
  }

  async createFromImage(
    userId: string,
    image: UploadedImage,
    sourceTypeRaw?: string,
  ): Promise<{ id: string; status: CouponStatus }> {
    const extension = ALLOWED_MIME.get(image.mimetype);
    if (!extension) {
      throw new BadRequestException(
        `지원하지 않는 이미지 형식입니다 (jpeg/png/webp만 지원): ${image.mimetype}`,
      );
    }
    if (image.size > MAX_UPLOAD_BYTES) {
      throw new BadRequestException('이미지가 너무 큽니다 (최대 10MB).');
    }
    const sourceType = this.parseSourceType(sourceTypeRaw);

    const coupon = await this.prisma.coupon.create({
      data: { userId, status: 'PROCESSING', sourceType, requiresReview: true },
    });

    const storageKey = `coupons/${coupon.id}/original.${extension}`;
    await this.storage.putObject({
      key: storageKey,
      body: image.buffer,
      contentType: image.mimetype,
    });
    await this.prisma.couponAsset.create({
      data: { couponId: coupon.id, type: 'ORIGINAL', storageKey, mimeType: image.mimetype },
    });

    await this.events.record(coupon.id, 'COUPON_CREATED', { sourceType });
    await this.events.record(coupon.id, 'IMAGE_UPLOADED', {
      mimeType: image.mimetype,
      bytes: image.size,
    });
    await this.recognitionQueue.enqueue(coupon.id);

    return { id: coupon.id, status: 'PROCESSING' };
  }

  async detail(userId: string, id: string): Promise<CouponDetailDto> {
    const coupon = await this.prisma.coupon.findUnique({
      where: { id },
      include: { assets: true },
    });
    if (!coupon || coupon.userId !== userId) {
      throw new NotFoundException('쿠폰을 찾을 수 없습니다.');
    }

    const assets = await Promise.all(
      coupon.assets.map(async (asset) => ({
        asset,
        url: await this.storage.getSignedUrl(asset.storageKey),
      })),
    );
    return toCouponDetailDto(coupon, assets);
  }

  async edit(userId: string, id: string, input: EditCouponInput): Promise<CouponDetailDto> {
    const coupon = await this.findOwnedOrThrow(userId, id);

    const changedFields = Object.keys(input).filter(
      (key) => input[key as keyof EditCouponInput] !== undefined,
    );
    if (changedFields.length === 0) {
      throw new BadRequestException('수정할 필드가 없습니다.');
    }

    const expiresAt =
      input.expiresAt === undefined
        ? undefined
        : input.expiresAt === null
          ? null
          : new Date(`${input.expiresAt}T00:00:00.000Z`);

    // Editing the expiration re-derives date-driven status, but never
    // resurrects EXPIRED automatically — recomputeDateDrivenStatus enforces
    // that domain rule.
    const nextStatus =
      expiresAt === undefined
        ? coupon.status
        : recomputeDateDrivenStatus(coupon.status, expiresAt, new Date());

    const updated = await this.prisma.coupon.update({
      where: { id },
      data: {
        ...(input.brandName !== undefined ? { brandName: input.brandName } : {}),
        ...(input.productName !== undefined ? { productName: input.productName } : {}),
        ...(input.category !== undefined ? { category: input.category } : {}),
        ...(input.faceValueMinor !== undefined
          ? { faceValueMinor: input.faceValueMinor, currency: 'KRW' }
          : {}),
        ...(expiresAt !== undefined ? { expiresAt } : {}),
        ...(input.usageLocationText !== undefined
          ? { usageLocationText: input.usageLocationText }
          : {}),
        ...(input.usageConditions !== undefined ? { usageConditions: input.usageConditions } : {}),
        status: nextStatus,
      },
    });

    await this.events.record(id, 'USER_EDITED', { changedFields });
    if (nextStatus !== coupon.status) {
      await this.events.record(id, 'STATUS_CHANGED', { from: coupon.status, to: nextStatus });
    }
    if (expiresAt !== undefined) {
      // Expiry changed: cancel the old reminder plan and re-plan (spec §16).
      await this.notificationScheduler.rescheduleFor(updated);
    }
    return this.detail(userId, id);
  }

  async confirm(userId: string, id: string): Promise<CouponDetailDto> {
    const coupon = await this.findOwnedOrThrow(userId, id);
    if (coupon.status !== 'NEEDS_REVIEW') {
      throw new BadRequestException('확인 대기 상태의 쿠폰만 확정할 수 있습니다.');
    }

    const confirmed = transition('NEEDS_REVIEW', 'ACTIVE', 'USER_CONFIRMED');
    const finalStatus = recomputeDateDrivenStatus(confirmed, coupon.expiresAt, new Date());

    const confirmedCoupon = await this.prisma.coupon.update({
      where: { id },
      data: { status: finalStatus, requiresReview: false },
    });
    await this.notificationScheduler.scheduleFor(confirmedCoupon);
    await this.events.record(id, 'USER_CONFIRMED');
    await this.events.record(id, 'STATUS_CHANGED', { from: coupon.status, to: finalStatus });
    return this.detail(userId, id);
  }

  async redeem(userId: string, id: string): Promise<CouponDetailDto> {
    const coupon = await this.findOwnedOrThrow(userId, id);
    this.assertTransition(coupon.status, 'REDEEMED', 'USER_MARKED_REDEEMED', '사용 완료');

    await this.prisma.coupon.update({
      where: { id },
      data: { status: 'REDEEMED', redeemedAt: new Date() },
    });
    // Redeemed coupons never fire expiration reminders (spec §16).
    await this.notificationScheduler.cancelFor(id);
    await this.events.record(id, 'MARKED_REDEEMED');
    await this.events.record(id, 'STATUS_CHANGED', { from: coupon.status, to: 'REDEEMED' });
    return this.detail(userId, id);
  }

  async restore(userId: string, id: string): Promise<CouponDetailDto> {
    const coupon = await this.findOwnedOrThrow(userId, id);
    this.assertTransition(coupon.status, 'ACTIVE', 'USER_RESTORED', '사용 완료 취소');

    // Explicit user restore; final status still honors the expiration date
    // (an expired coupon restores to EXPIRED, never silently back to ACTIVE).
    const finalStatus = statusAfterRestore(coupon.expiresAt, new Date());
    const restored = await this.prisma.coupon.update({
      where: { id },
      data: { status: finalStatus, redeemedAt: null },
    });
    // Live again → reminders come back (scheduleFor no-ops for EXPIRED).
    await this.notificationScheduler.scheduleFor(restored);
    await this.events.record(id, 'RESTORED_TO_ACTIVE', { finalStatus });
    await this.events.record(id, 'STATUS_CHANGED', { from: coupon.status, to: finalStatus });
    return this.detail(userId, id);
  }

  async archive(userId: string, id: string): Promise<CouponDetailDto> {
    const coupon = await this.findOwnedOrThrow(userId, id);
    this.assertTransition(coupon.status, 'ARCHIVED', 'USER_ARCHIVED', '보관');

    await this.prisma.coupon.update({
      where: { id },
      data: { status: 'ARCHIVED', archivedAt: new Date() },
    });
    await this.notificationScheduler.cancelFor(id);
    await this.events.record(id, 'ARCHIVED');
    await this.events.record(id, 'STATUS_CHANGED', { from: coupon.status, to: 'ARCHIVED' });
    return this.detail(userId, id);
  }

  async unarchive(userId: string, id: string): Promise<CouponDetailDto> {
    const coupon = await this.findOwnedOrThrow(userId, id);
    this.assertTransition(coupon.status, 'ACTIVE', 'USER_UNARCHIVED', '보관 해제');

    const finalStatus = recomputeDateDrivenStatus('ACTIVE', coupon.expiresAt, new Date());
    const unarchived = await this.prisma.coupon.update({
      where: { id },
      data: { status: finalStatus, archivedAt: null },
    });
    await this.notificationScheduler.scheduleFor(unarchived);
    await this.events.record(id, 'STATUS_CHANGED', { from: coupon.status, to: finalStatus });
    return this.detail(userId, id);
  }

  async remove(userId: string, id: string): Promise<void> {
    const coupon = await this.findOwnedOrThrow(userId, id);
    const assets = await this.prisma.couponAsset.findMany({ where: { couponId: id } });

    // The DELETED event is recorded before the hard delete so the action is
    // at least visible in logs; rows (including events) are then removed.
    await this.events.record(id, 'DELETED', { status: coupon.status });
    await this.prisma.scheduledNotification.deleteMany({ where: { couponId: id } });
    await this.prisma.couponEvent.deleteMany({ where: { couponId: id } });
    await this.prisma.couponAsset.deleteMany({ where: { couponId: id } });
    await this.prisma.coupon.delete({ where: { id } });

    for (const asset of assets) {
      try {
        await this.storage.deleteObject(asset.storageKey);
      } catch (error) {
        // Orphaned objects are preferable to a failed user-facing delete;
        // they are cleaned up by a later storage sweep.
        this.logger.warn(`Failed to delete storage object ${asset.storageKey}: ${String(error)}`);
      }
    }
  }

  /**
   * Reveals the decrypted barcode for in-store display. Every reveal is
   * audit-logged (BARCODE_VIEWED) with a masked value only (ADR-0005).
   */
  async revealBarcode(userId: string, id: string): Promise<BarcodeRevealDto> {
    const coupon = await this.findOwnedOrThrow(userId, id);
    if (!coupon.encryptedBarcode) {
      throw new NotFoundException('이 쿠폰에는 저장된 바코드가 없습니다.');
    }
    const value = this.barcodeCrypto.decrypt(coupon.encryptedBarcode);
    await this.events.record(id, 'BARCODE_VIEWED', { masked: maskBarcode(value) });
    return { value, format: coupon.barcodeType };
  }

  private assertTransition(
    from: Coupon['status'],
    to: CouponStatus,
    trigger: TransitionTrigger,
    actionLabel: string,
  ): void {
    if (!canTransition(from, to, trigger)) {
      throw new BadRequestException(
        `현재 상태(${from})에서는 ${actionLabel} 처리를 할 수 없습니다.`,
      );
    }
  }

  private async findOwnedOrThrow(userId: string, id: string): Promise<Coupon> {
    const coupon = await this.prisma.coupon.findUnique({ where: { id } });
    // Same 404 for "missing" and "not yours" — no existence oracle.
    if (!coupon || coupon.userId !== userId) {
      throw new NotFoundException('쿠폰을 찾을 수 없습니다.');
    }
    return coupon;
  }

  private parseStatus(raw: string | undefined): CouponStatus | null {
    if (raw === undefined || raw === '') return null;
    if ((COUPON_STATUSES as readonly string[]).includes(raw)) {
      return raw as CouponStatus;
    }
    throw new BadRequestException(`지원하지 않는 상태 값입니다: ${raw}`);
  }

  private parseSort(raw: string | undefined): WalletSort {
    if (raw === undefined || raw === '') return 'EXPIRATION_ASC';
    if ((WALLET_SORTS as readonly string[]).includes(raw)) {
      return raw as WalletSort;
    }
    throw new BadRequestException(`지원하지 않는 정렬 값입니다: ${raw}`);
  }

  private parseSourceType(raw: string | undefined): CouponSourceType {
    if (raw === undefined || raw === '') return 'FILE_UPLOAD';
    if ((COUPON_SOURCE_TYPES as readonly string[]).includes(raw)) {
      return raw as CouponSourceType;
    }
    throw new BadRequestException(`지원하지 않는 등록 경로입니다: ${raw}`);
  }
}
