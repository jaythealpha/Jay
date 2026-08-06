import { BadRequestException, Injectable, NotFoundException } from '@nestjs/common';
import type { Coupon, CouponSourceType } from '@prisma/client';
import {
  COUPON_SOURCE_TYPES,
  COUPON_STATUSES,
  type CouponDetailDto,
  type CouponListResponseDto,
  type CouponStatus,
} from '@amc/shared-types';
import { recomputeDateDrivenStatus, transition } from '@amc/domain';
import { CouponEventsService } from '../events/coupon-events.service';
import { PrismaService } from '../prisma/prisma.service';
import { RecognitionQueueService } from '../recognition/recognition.queue';
import { StorageService } from '../storage/storage.service';
import { toCouponDetailDto } from './coupon-detail.mapper';
import { toCouponSummaryDto } from './coupon.mapper';

export interface ListCouponsQuery {
  status?: string;
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

const DEFAULT_LIMIT = 50;
const MAX_LIMIT = 100;
const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
const ALLOWED_MIME = new Map([
  ['image/jpeg', 'jpg'],
  ['image/png', 'png'],
  ['image/webp', 'webp'],
]);

/**
 * Milestone 1 scope: still no authentication — every operation is scoped to
 * the local demo user. AuthModule (Milestone 2) replaces resolveDemoUser with
 * the requesting user.
 */
@Injectable()
export class CouponsService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly storage: StorageService,
    private readonly recognitionQueue: RecognitionQueueService,
    private readonly events: CouponEventsService,
  ) {}

  async list(query: ListCouponsQuery): Promise<CouponListResponseDto> {
    const status = this.parseStatus(query.status);
    const limit = Math.min(query.limit ?? DEFAULT_LIMIT, MAX_LIMIT);

    const where = status ? { status } : {};
    const [rows, total] = await Promise.all([
      // Expiration First: soonest expiration on top, undated coupons last.
      this.prisma.coupon.findMany({
        where,
        orderBy: [{ expiresAt: { sort: 'asc', nulls: 'last' } }, { createdAt: 'desc' }],
        take: limit,
      }),
      this.prisma.coupon.count({ where }),
    ]);

    return { items: rows.map(toCouponSummaryDto), total };
  }

  async createFromImage(
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

    const user = await this.resolveDemoUser();
    const coupon = await this.prisma.coupon.create({
      data: { userId: user.id, status: 'PROCESSING', sourceType, requiresReview: true },
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

  async detail(id: string): Promise<CouponDetailDto> {
    const coupon = await this.prisma.coupon.findUnique({
      where: { id },
      include: { assets: true },
    });
    if (!coupon) throw new NotFoundException('쿠폰을 찾을 수 없습니다.');

    const assets = await Promise.all(
      coupon.assets.map(async (asset) => ({
        asset,
        url: await this.storage.getSignedUrl(asset.storageKey),
      })),
    );
    return toCouponDetailDto(coupon, assets);
  }

  async edit(id: string, input: EditCouponInput): Promise<CouponDetailDto> {
    const coupon = await this.findOrThrow(id);

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
    return this.detailFrom(updated);
  }

  async confirm(id: string): Promise<CouponDetailDto> {
    const coupon = await this.findOrThrow(id);
    if (coupon.status !== 'NEEDS_REVIEW') {
      throw new BadRequestException('확인 대기 상태의 쿠폰만 확정할 수 있습니다.');
    }

    const confirmed = transition('NEEDS_REVIEW', 'ACTIVE', 'USER_CONFIRMED');
    const finalStatus = recomputeDateDrivenStatus(confirmed, coupon.expiresAt, new Date());

    const updated = await this.prisma.coupon.update({
      where: { id },
      data: { status: finalStatus, requiresReview: false },
    });
    await this.events.record(id, 'USER_CONFIRMED');
    await this.events.record(id, 'STATUS_CHANGED', { from: coupon.status, to: finalStatus });
    return this.detailFrom(updated);
  }

  private async detailFrom(coupon: Coupon): Promise<CouponDetailDto> {
    return this.detail(coupon.id);
  }

  private async findOrThrow(id: string): Promise<Coupon> {
    const coupon = await this.prisma.coupon.findUnique({ where: { id } });
    if (!coupon) throw new NotFoundException('쿠폰을 찾을 수 없습니다.');
    return coupon;
  }

  private async resolveDemoUser(): Promise<{ id: string }> {
    return this.prisma.user.upsert({
      where: { email: 'demo@allmightycoupon.local' },
      update: {},
      create: { email: 'demo@allmightycoupon.local' },
      select: { id: true },
    });
  }

  private parseStatus(raw: string | undefined): CouponStatus | null {
    if (raw === undefined || raw === '') return null;
    if ((COUPON_STATUSES as readonly string[]).includes(raw)) {
      return raw as CouponStatus;
    }
    throw new BadRequestException(`지원하지 않는 상태 값입니다: ${raw}`);
  }

  private parseSourceType(raw: string | undefined): CouponSourceType {
    if (raw === undefined || raw === '') return 'FILE_UPLOAD';
    if ((COUPON_SOURCE_TYPES as readonly string[]).includes(raw)) {
      return raw as CouponSourceType;
    }
    throw new BadRequestException(`지원하지 않는 등록 경로입니다: ${raw}`);
  }
}
