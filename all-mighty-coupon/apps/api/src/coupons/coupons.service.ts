import { BadRequestException, Injectable } from '@nestjs/common';
import { COUPON_STATUSES, type CouponListResponseDto, type CouponStatus } from '@amc/shared-types';
import { PrismaService } from '../prisma/prisma.service';
import { toCouponSummaryDto } from './coupon.mapper';

export interface ListCouponsQuery {
  status?: string;
  limit?: number;
}

const DEFAULT_LIMIT = 50;
const MAX_LIMIT = 100;

/**
 * Milestone 0 scope: coupons are listed without authentication and therefore
 * without a user filter — the dev database only holds seeded sample data.
 * AuthModule (Milestone 2) will scope every query to the requesting user.
 */
@Injectable()
export class CouponsService {
  constructor(private readonly prisma: PrismaService) {}

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

  private parseStatus(raw: string | undefined): CouponStatus | null {
    if (raw === undefined || raw === '') return null;
    if ((COUPON_STATUSES as readonly string[]).includes(raw)) {
      return raw as CouponStatus;
    }
    throw new BadRequestException(`지원하지 않는 상태 값입니다: ${raw}`);
  }
}
