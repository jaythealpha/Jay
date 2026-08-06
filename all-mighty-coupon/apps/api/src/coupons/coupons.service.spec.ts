import { BadRequestException } from '@nestjs/common';
import type { Coupon } from '@prisma/client';
import { CouponsService } from './coupons.service';
import { toCouponSummaryDto } from './coupon.mapper';
import type { PrismaService } from '../prisma/prisma.service';
import type { StorageService } from '../storage/storage.service';
import type { RecognitionQueueService } from '../recognition/recognition.queue';
import type { CouponEventsService } from '../events/coupon-events.service';
import type { BarcodeCryptoService } from '../crypto/barcode-crypto.service';
import type { NotificationSchedulerService } from '../notifications/notification-scheduler.service';

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

interface Stubs {
  service: CouponsService;
  findManyCalls: unknown[];
  putCalls: unknown[];
  enqueued: string[];
  events: string[];
}

function serviceWith(rows: Coupon[]): Stubs {
  const findManyCalls: unknown[] = [];
  const putCalls: unknown[] = [];
  const enqueued: string[] = [];
  const events: string[] = [];

  const prismaStub = {
    coupon: {
      findMany: (args: unknown) => {
        findManyCalls.push(args);
        return Promise.resolve(rows);
      },
      count: () => Promise.resolve(rows.length),
      create: (args: { data: Record<string, unknown> }) =>
        Promise.resolve(sampleCoupon({ id: 'new-coupon', ...(args.data as Partial<Coupon>) })),
    },
    couponAsset: { create: () => Promise.resolve({}) },
    user: { upsert: () => Promise.resolve({ id: 'u1' }) },
  } as unknown as PrismaService;

  const storageStub = {
    putObject: (input: unknown) => {
      putCalls.push(input);
      return Promise.resolve();
    },
    getSignedUrl: () => Promise.resolve('https://signed.example/url'),
    getObject: () => Promise.resolve(Buffer.alloc(0)),
    ensureReady: () => Promise.resolve(),
  } as unknown as StorageService;

  const queueStub = {
    enqueue: (couponId: string) => {
      enqueued.push(couponId);
      return Promise.resolve();
    },
  } as unknown as RecognitionQueueService;

  const eventsStub = {
    record: (_couponId: string, type: string) => {
      events.push(type);
      return Promise.resolve();
    },
  } as unknown as CouponEventsService;

  return {
    service: new CouponsService(
      prismaStub,
      storageStub,
      queueStub,
      eventsStub,
      {
        encrypt: (v: string) => `enc(${v})`,
        decrypt: (v: string) => v,
      } as unknown as BarcodeCryptoService,
      {
        scheduleFor: () => Promise.resolve(0),
        cancelFor: () => Promise.resolve(),
        rescheduleFor: () => Promise.resolve(0),
      } as unknown as NotificationSchedulerService,
    ),
    findManyCalls,
    putCalls,
    enqueued,
    events,
  };
}

describe('CouponsService.list', () => {
  it('orders by expiration ascending with nulls last', async () => {
    const { service, findManyCalls } = serviceWith([sampleCoupon()]);
    await service.list('u1', {});
    expect(findManyCalls[0]).toMatchObject({
      orderBy: [{ expiresAt: { sort: 'asc', nulls: 'last' } }, { createdAt: 'desc' }],
    });
  });

  it('rejects unknown status filters as a user error', async () => {
    const { service } = serviceWith([]);
    await expect(service.list('u1', { status: 'NOT_A_STATUS' })).rejects.toThrow(
      BadRequestException,
    );
  });

  it('passes valid status filters through and caps the limit', async () => {
    const { service, findManyCalls } = serviceWith([]);
    await service.list('u1', { status: 'ACTIVE', limit: 5000 });
    expect(findManyCalls[0]).toMatchObject({
      where: { userId: 'u1', status: 'ACTIVE' },
      take: 100,
    });
  });
});

describe('CouponsService.createFromImage', () => {
  const image = { buffer: Buffer.from('fake'), mimetype: 'image/png', size: 4 };

  it('stores the original, records events, and enqueues recognition', async () => {
    const { service, putCalls, enqueued, events } = serviceWith([]);
    const result = await service.createFromImage('u1', image, 'PHOTO_LIBRARY');

    expect(result.status).toBe('PROCESSING');
    expect(putCalls).toHaveLength(1);
    expect(enqueued).toEqual([result.id]);
    expect(events).toEqual(['COUPON_CREATED', 'IMAGE_UPLOADED']);
  });

  it('rejects unsupported mime types before any storage write', async () => {
    const { service, putCalls } = serviceWith([]);
    await expect(
      service.createFromImage('u1', { ...image, mimetype: 'application/pdf' }),
    ).rejects.toThrow(BadRequestException);
    expect(putCalls).toHaveLength(0);
  });

  it('rejects oversized uploads', async () => {
    const { service } = serviceWith([]);
    await expect(
      service.createFromImage('u1', { ...image, size: 11 * 1024 * 1024 }),
    ).rejects.toThrow(BadRequestException);
  });

  it('rejects unknown source types', async () => {
    const { service } = serviceWith([]);
    await expect(service.createFromImage('u1', image, 'CARRIER_PIGEON')).rejects.toThrow(
      BadRequestException,
    );
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
