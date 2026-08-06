import { Injectable } from '@nestjs/common';
import type { CouponEventType, Prisma } from '@prisma/client';
import { PrismaService } from '../prisma/prisma.service';

/**
 * Append-only domain event log. Metadata must already be privacy-safe —
 * callers never pass raw barcode values or full OCR text (spec §17).
 */
@Injectable()
export class CouponEventsService {
  constructor(private readonly prisma: PrismaService) {}

  async record(
    couponId: string,
    type: CouponEventType,
    metadata?: Prisma.InputJsonValue,
  ): Promise<void> {
    await this.prisma.couponEvent.create({
      data: { couponId, type, ...(metadata !== undefined ? { metadata } : {}) },
    });
  }
}
