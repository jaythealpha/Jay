import { BadRequestException } from '@nestjs/common';
import type { Coupon } from '@prisma/client';
import { CouponsService } from './coupons.service';
import { toCouponSummaryDto } from './coupon.mapper';
import type { PrismaService } from '../prisma/prisma.service';

function sampleCoupon(overrides: Partial<Coupon> = {}): Coupon {
  return {
    id: 'c1',
    userId: 'u1',
    brandName: '스타벅스',
    productName: '아메리카노 Tall',
    category: '카페',
    faceValueMinor: 4500,
    currency: 'KRW',
    status: 'ACTIVE',
    issuedAt: null,
    expiresAt: new Date('2026-12-31T00:00:00Z'),
    usageLocationText: null,
    usageConditions: null,
    barcodeType: null,
    encryptedBarcode: 'encrypted-secret',
    barcodeHash: 'hash123',
    sourceType: 'MANUAL',
    requiresReview: false,
    recognitionData: null,
    redeemedAt: null,
    archivedAt: null,
    createdAt: new Date('2026-08-01T00:00:00Z'),
    updatedAt: new Date('2026-08-01T00:00:00Z'),
    ...overrides,
  };
}

function serviceWith(rows: Coupon[]): { service: CouponsService; calls: unknown[] } {
  const calls: unknown[] = [];
  const prismaStub = {
    coupon: {
      findMany: (args: unknown) => {
        calls.push(args);
        return Promise.resolve(rows);
      },
      count: () => Promise.resolve(rows.length),
    },
  } as unknown as PrismaService;
  return { service: new CouponsService(prismaStub), calls };
}

describe('CouponsService.list', () => {
  it('orders by expiration ascending with nulls last', async () => {
    const { service, calls } = serviceWith([sampleCoupon()]);
    await service.list({});
    expect(calls[0]).toMatchObject({
      orderBy: [{ expiresAt: { sort: 'asc', nulls: 'last' } }, { createdAt: 'desc' }],
    });
  });

  it('rejects unknown status filters as a user error', async () => {
    const { service } = serviceWith([]);
    await expect(service.list({ status: 'NOT_A_STATUS' })).rejects.toThrow(BadRequestException);
  });

  it('passes valid status filters through and caps the limit', async () => {
    const { service, calls } = serviceWith([]);
    await service.list({ status: 'ACTIVE', limit: 5000 });
    expect(calls[0]).toMatchObject({ where: { status: 'ACTIVE' }, take: 100 });
  });
});

describe('toCouponSummaryDto', () => {
  it('never exposes barcode material in the wire DTO', () => {
    const dto = toCouponSummaryDto(sampleCoupon());
    const serialized = JSON.stringify(dto);
    expect(serialized).not.toContain('encrypted-secret');
    expect(serialized).not.toContain('hash123');
    expect(dto).not.toHaveProperty('encryptedBarcode');
    expect(dto).not.toHaveProperty('barcodeHash');
  });

  it('serializes dates as ISO-8601 UTC strings', () => {
    const dto = toCouponSummaryDto(sampleCoupon());
    expect(dto.expiresAt).toBe('2026-12-31T00:00:00.000Z');
    expect(dto.createdAt).toBe('2026-08-01T00:00:00.000Z');
  });
});
