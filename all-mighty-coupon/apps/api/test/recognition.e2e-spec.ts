import { INestApplication } from '@nestjs/common';
import { Test } from '@nestjs/testing';
import request from 'supertest';
import sharp from 'sharp';
import { AppModule } from '../src/app.module';
import { PrismaService } from '../src/prisma/prisma.service';
import { StorageService } from '../src/storage/storage.service';
import { MOCK_OCR_MARKER } from '../src/recognition/ocr/mock-ocr.provider';

jest.setTimeout(60_000);

/**
 * Full-pipeline integration test against real Postgres + Redis (+ storage
 * driver from env): upload → coupon created → job queued → worker runs →
 * fields extracted → status updated → events recorded.
 */
describe('Recognition pipeline (e2e)', () => {
  let app: INestApplication;
  let prisma: PrismaService;
  const createdCouponIds: string[] = [];

  let token: string;

  beforeAll(async () => {
    const moduleRef = await Test.createTestingModule({ imports: [AppModule] }).compile();
    app = moduleRef.createNestApplication();
    await app.init();
    prisma = app.get(PrismaService);
    await app.get(StorageService).ensureReady();

    const credentials = {
      email: 'e2e-recognition@allmightycoupon.local',
      password: 'e2e-password-1234',
    };
    const registered = await request(app.getHttpServer())
      .post('/v1/auth/register')
      .send(credentials);
    const auth =
      registered.status === 201
        ? registered
        : await request(app.getHttpServer()).post('/v1/auth/login').send(credentials).expect(200);
    token = auth.body.accessToken as string;
  });

  afterAll(async () => {
    await prisma.couponEvent.deleteMany({ where: { couponId: { in: createdCouponIds } } });
    await prisma.couponAsset.deleteMany({ where: { couponId: { in: createdCouponIds } } });
    await prisma.coupon.deleteMany({ where: { id: { in: createdCouponIds } } });
    await app.close();
  });

  async function makeCouponImage(mockText: string, barcodeValue?: string): Promise<Buffer> {
    let image = sharp({
      create: { width: 1200, height: 1000, channels: 3, background: '#ffffff' },
    });
    if (barcodeValue) {
      const { prepareZXingModule, writeBarcode } = await import('zxing-wasm/writer');
      const { readFile } = await import('node:fs/promises');
      const { dirname, join } = await import('node:path');
      const entry = require.resolve('zxing-wasm/writer');
      const wasmBinary = await readFile(
        join(dirname(entry), '..', '..', 'writer', 'zxing_writer.wasm'),
      );
      prepareZXingModule({ overrides: { wasmBinary: wasmBinary.buffer.slice(0) as ArrayBuffer } });
      const barcode = await writeBarcode(barcodeValue, { format: 'Code128', scale: 3 });
      const barcodePng = Buffer.from(await barcode.image!.arrayBuffer());
      image = sharp(
        await image
          .composite([{ input: barcodePng, top: 700, left: 100 }])
          .png()
          .toBuffer(),
      );
    }
    const png = await image.png().toBuffer();
    return Buffer.concat([png, Buffer.from(`${MOCK_OCR_MARKER}${mockText}`, 'utf8')]);
  }

  async function waitForProcessed(id: string): Promise<Record<string, unknown>> {
    const deadline = Date.now() + 30_000;
    for (;;) {
      const res = await request(app.getHttpServer())
        .get(`/v1/coupons/${id}`)
        .set('Authorization', `Bearer ${token}`)
        .expect(200);
      if (res.body.status !== 'PROCESSING') return res.body as Record<string, unknown>;
      if (Date.now() > deadline) throw new Error('recognition did not finish in time');
      await new Promise((resolve) => setTimeout(resolve, 500));
    }
  }

  const happyText = [
    '배스킨라빈스',
    '파인트 아이스크림 교환권 테스트',
    '유효기간 2027.03.31 까지',
    '금액 9,800원',
  ].join('\n');

  it('extracts fields, encrypts the barcode, and lands on ACTIVE', async () => {
    const upload = await request(app.getHttpServer())
      .post('/v1/coupons')
      .set('Authorization', `Bearer ${token}`)
      .field('sourceType', 'PHOTO_LIBRARY')
      .attach('image', await makeCouponImage(happyText, 'E2E-BARCODE-9999'), 'coupon.png')
      .expect(201);
    const couponId = upload.body.id as string;
    createdCouponIds.push(couponId);
    expect(upload.body.status).toBe('PROCESSING');

    const detail = await waitForProcessed(couponId);
    expect(detail.status).toBe('ACTIVE');
    expect(detail.brandName).toBe('배스킨라빈스');
    expect(detail.faceValueMinor).toBe(9800);
    expect(detail.expiresAt).toBe('2027-03-31T00:00:00.000Z');
    expect(detail.requiresReview).toBe(false);
    expect(detail.hasBarcode).toBe(true);
    expect(detail.barcodeType).toBe('Code128');

    // Privacy boundary: raw barcode value never leaves the server.
    expect(JSON.stringify(detail)).not.toContain('E2E-BARCODE-9999');

    // Derived assets exist alongside the untouched original.
    const assetTypes = (detail.assets as Array<{ type: string }>).map((a) => a.type).sort();
    expect(assetTypes).toEqual(['NORMALIZED', 'ORIGINAL', 'THUMBNAIL']);

    const events = await prisma.couponEvent.findMany({ where: { couponId } });
    const eventTypes = events.map((e) => e.type);
    for (const expected of [
      'COUPON_CREATED',
      'IMAGE_UPLOADED',
      'BARCODE_DETECTED',
      'OCR_COMPLETED',
      'COUPON_PARSED',
      'STATUS_CHANGED',
    ]) {
      expect(eventTypes).toContain(expected);
    }
    // Events must never contain the raw barcode either.
    expect(JSON.stringify(events)).not.toContain('E2E-BARCODE-9999');
  });

  it('flags duplicate barcodes instead of auto-deleting', async () => {
    const upload = await request(app.getHttpServer())
      .post('/v1/coupons')
      .set('Authorization', `Bearer ${token}`)
      .attach('image', await makeCouponImage(happyText, 'E2E-BARCODE-9999'), 'again.png')
      .expect(201);
    const couponId = upload.body.id as string;
    createdCouponIds.push(couponId);

    const detail = await waitForProcessed(couponId);
    const recognition = detail.recognition as { duplicateSuspects: string[] };
    expect(recognition.duplicateSuspects.length).toBeGreaterThanOrEqual(1);
    expect(recognition.duplicateSuspects).toContain(createdCouponIds[0]);
    // Both coupons still exist — duplicates are the user's call.
    expect(detail.status).not.toBe('INVALID');
  });

  it('routes low-confidence expiration to NEEDS_REVIEW, then edit + confirm → ACTIVE', async () => {
    // Bare date (no 유효기간 keyword) → confidence 0.7 < 0.95 → review.
    const reviewText = '스타벅스\n부정확한 스캔 결과 상품명\n2027.06.30\n금액 4,500원';
    const upload = await request(app.getHttpServer())
      .post('/v1/coupons')
      .set('Authorization', `Bearer ${token}`)
      .attach('image', await makeCouponImage(reviewText), 'review.png')
      .expect(201);
    const couponId = upload.body.id as string;
    createdCouponIds.push(couponId);

    const detail = await waitForProcessed(couponId);
    expect(detail.status).toBe('NEEDS_REVIEW');
    expect(detail.requiresReview).toBe(true);
    const recognition = detail.recognition as { confidences: { expiresAt: number | null } };
    expect(recognition.confidences.expiresAt).toBeLessThan(0.95);

    // User fixes the expiration (Confirm, Do Not Type: edit then confirm).
    const edited = await request(app.getHttpServer())
      .patch(`/v1/coupons/${couponId}`)
      .set('Authorization', `Bearer ${token}`)
      .send({ expiresAt: '2027-07-31', productName: '아이스 카페 아메리카노 Tall' })
      .expect(200);
    expect(edited.body.expiresAt).toBe('2027-07-31T00:00:00.000Z');
    expect(edited.body.status).toBe('NEEDS_REVIEW');

    const confirmed = await request(app.getHttpServer())
      .post(`/v1/coupons/${couponId}/confirm`)
      .set('Authorization', `Bearer ${token}`)
      .expect(200);
    expect(confirmed.body.status).toBe('ACTIVE');
    expect(confirmed.body.requiresReview).toBe(false);

    const events = await prisma.couponEvent.findMany({ where: { couponId } });
    const types = events.map((e) => e.type);
    expect(types).toContain('USER_EDITED');
    expect(types).toContain('USER_CONFIRMED');
  });

  it('marks non-coupon images as INVALID', async () => {
    // No barcode, and mock OCR returns text with no extractable fields.
    const upload = await request(app.getHttpServer())
      .post('/v1/coupons')
      .set('Authorization', `Bearer ${token}`)
      .attach('image', await makeCouponImage('그냥 풍경 사진입니다'), 'landscape.png')
      .expect(201);
    const couponId = upload.body.id as string;
    createdCouponIds.push(couponId);

    const detail = await waitForProcessed(couponId);
    expect(detail.status).toBe('INVALID');
  });

  it('rejects unsupported upload types with the common error envelope', async () => {
    const res = await request(app.getHttpServer())
      .post('/v1/coupons')
      .set('Authorization', `Bearer ${token}`)
      .attach('image', Buffer.from('%PDF-1.4 fake'), {
        filename: 'doc.pdf',
        contentType: 'application/pdf',
      })
      .expect(400);
    expect(res.body.error.code).toBe('BAD_REQUEST');
    expect(res.body.error.requestId).toBeDefined();
  });
});
