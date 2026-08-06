import { Injectable } from '@nestjs/common';
import type { Coupon } from '@prisma/client';
import type { CouponSummaryDto } from '@amc/shared-types';
import { PrismaService } from '../prisma/prisma.service';
import { toCouponSummaryDto } from '../coupons/coupon.mapper';

export interface HomeSummaryDto {
  /** Soonest-expiring live coupons within 3 days. */
  expiringSoon: CouponSummaryDto[];
  /** Within 7 days plus high-value live coupons — "이번 주 사용하세요". */
  useThisWeek: CouponSummaryDto[];
  /** Latest registrations, max 5. */
  recent: CouponSummaryDto[];
  counts: {
    active: number;
    expiringSoon: number;
    redeemed: number;
    needsReview: number;
    total: number;
  };
  /** Sum of face values (KRW) across live (ACTIVE/EXPIRING_SOON) coupons. */
  totalValueMinor: number;
}

const DAY_MS = 86_400_000;
const HIGH_VALUE_MINOR = 20_000;
const LIVE_STATUSES = ['ACTIVE', 'EXPIRING_SOON'] as const;

/**
 * Home is not a plain list — it surfaces what the user should act on now
 * (Expiration First, spec §13).
 */
@Injectable()
export class HomeService {
  constructor(private readonly prisma: PrismaService) {}

  async summary(userId: string, now = new Date()): Promise<HomeSummaryDto> {
    const in3Days = new Date(now.getTime() + 3 * DAY_MS);
    const in7Days = new Date(now.getTime() + 7 * DAY_MS);

    const [expiringSoon, within7, highValue, recent, statusCounts, valueAggregate] =
      await Promise.all([
        this.prisma.coupon.findMany({
          where: {
            userId,
            status: { in: [...LIVE_STATUSES] },
            expiresAt: { gte: now, lte: in3Days },
          },
          orderBy: { expiresAt: 'asc' },
          take: 5,
        }),
        this.prisma.coupon.findMany({
          where: {
            userId,
            status: { in: [...LIVE_STATUSES] },
            expiresAt: { gte: now, lte: in7Days },
          },
          orderBy: { expiresAt: 'asc' },
          take: 5,
        }),
        this.prisma.coupon.findMany({
          where: {
            userId,
            status: { in: [...LIVE_STATUSES] },
            faceValueMinor: { gte: HIGH_VALUE_MINOR },
          },
          orderBy: { faceValueMinor: 'desc' },
          take: 5,
        }),
        this.prisma.coupon.findMany({
          where: { userId, status: { not: 'INVALID' } },
          orderBy: { createdAt: 'desc' },
          take: 5,
        }),
        this.prisma.coupon.groupBy({
          by: ['status'],
          where: { userId },
          _count: { _all: true },
        }),
        this.prisma.coupon.aggregate({
          where: { userId, status: { in: [...LIVE_STATUSES] } },
          _sum: { faceValueMinor: true },
        }),
      ]);

    const countFor = (status: string): number =>
      statusCounts.find((entry) => entry.status === status)?._count._all ?? 0;

    return {
      expiringSoon: expiringSoon.map(toCouponSummaryDto),
      useThisWeek: this.mergeUseThisWeek(within7, highValue).map(toCouponSummaryDto),
      recent: recent.map(toCouponSummaryDto),
      counts: {
        active: countFor('ACTIVE'),
        expiringSoon: countFor('EXPIRING_SOON'),
        redeemed: countFor('REDEEMED'),
        needsReview: countFor('NEEDS_REVIEW'),
        total: statusCounts.reduce((sum, entry) => sum + entry._count._all, 0),
      },
      totalValueMinor: valueAggregate._sum.faceValueMinor ?? 0,
    };
  }

  /** 7-day window first (soonest), then high-value extras, deduped, cap 5. */
  private mergeUseThisWeek(within7: Coupon[], highValue: Coupon[]): Coupon[] {
    const seen = new Set<string>();
    const merged: Coupon[] = [];
    for (const coupon of [...within7, ...highValue]) {
      if (seen.has(coupon.id)) continue;
      seen.add(coupon.id);
      merged.push(coupon);
      if (merged.length >= 5) break;
    }
    return merged;
  }
}
