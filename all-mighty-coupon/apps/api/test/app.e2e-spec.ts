import { INestApplication } from '@nestjs/common';
import { Test } from '@nestjs/testing';
import request from 'supertest';
import { AppModule } from '../src/app.module';
import { PrismaService } from '../src/prisma/prisma.service';

/**
 * Integration tests against the real dev database (docker compose postgres +
 * redis). They create their own rows, assert through the HTTP layer, and
 * clean up after themselves.
 */
describe('API integration', () => {
  let app: INestApplication;
  let prisma: PrismaService;
  const createdCouponIds: string[] = [];
  let testUserId: string;
  let token: string;

  beforeAll(async () => {
    const moduleRef = await Test.createTestingModule({ imports: [AppModule] }).compile();
    app = moduleRef.createNestApplication();
    await app.init();
    prisma = app.get(PrismaService);

    // Register (or re-login) the e2e user through the real auth API.
    const credentials = { email: 'e2e@allmightycoupon.local', password: 'e2e-password-1234' };
    const registered = await request(app.getHttpServer())
      .post('/v1/auth/register')
      .send(credentials);
    const auth =
      registered.status === 201
        ? registered
        : await request(app.getHttpServer()).post('/v1/auth/login').send(credentials).expect(200);
    token = auth.body.accessToken as string;
    testUserId = auth.body.user.id as string;

    const soon = await prisma.coupon.create({
      data: {
        userId: testUserId,
        brandName: 'E2E-소닉카페',
        productName: '통합테스트 라떼',
        status: 'EXPIRING_SOON',
        sourceType: 'MANUAL',
        requiresReview: false,
        expiresAt: new Date(Date.now() + 2 * 86_400_000),
        encryptedBarcode: 'e2e-encrypted-payload',
        barcodeHash: 'e2e-hash-value',
        recognitionData: { sampleData: true, source: 'e2e' },
      },
    });
    const later = await prisma.coupon.create({
      data: {
        userId: testUserId,
        brandName: 'E2E-소닉마트',
        productName: '통합테스트 금액권',
        status: 'ACTIVE',
        sourceType: 'MANUAL',
        requiresReview: false,
        expiresAt: new Date(Date.now() + 90 * 86_400_000),
        recognitionData: { sampleData: true, source: 'e2e' },
      },
    });
    createdCouponIds.push(soon.id, later.id);
  });

  afterAll(async () => {
    await prisma.scheduledNotification.deleteMany({
      where: { couponId: { in: createdCouponIds } },
    });
    await prisma.couponEvent.deleteMany({ where: { couponId: { in: createdCouponIds } } });
    await prisma.coupon.deleteMany({ where: { id: { in: createdCouponIds } } });
    await app.close();
  });

  it('GET /health reports database and redis as up', async () => {
    const res = await request(app.getHttpServer()).get('/health').expect(200);
    expect(res.body.status).toBe('ok');
    expect(res.body.components).toEqual({ database: 'up', redis: 'up' });
    expect(typeof res.body.checkedAt).toBe('string');
  });

  it('GET /v1/coupons lists coupons soonest-expiration-first without barcode material', async () => {
    const res = await request(app.getHttpServer())
      .get('/v1/coupons')
      .set('Authorization', `Bearer ${token}`)
      .expect(200);
    expect(res.body.total).toBeGreaterThanOrEqual(2);

    const ids = (res.body.items as Array<{ id: string }>).map((item) => item.id);
    const soonIndex = ids.indexOf(createdCouponIds[0] as string);
    const laterIndex = ids.indexOf(createdCouponIds[1] as string);
    expect(soonIndex).toBeGreaterThanOrEqual(0);
    expect(laterIndex).toBeGreaterThanOrEqual(0);
    expect(soonIndex).toBeLessThan(laterIndex);

    const serialized = JSON.stringify(res.body);
    expect(serialized).not.toContain('e2e-encrypted-payload');
    expect(serialized).not.toContain('e2e-hash-value');
  });

  it('GET /v1/coupons?status= filters by status and rejects bad values', async () => {
    const ok = await request(app.getHttpServer())
      .get('/v1/coupons')
      .set('Authorization', `Bearer ${token}`)
      .query({ status: 'EXPIRING_SOON' })
      .expect(200);
    expect(
      (ok.body.items as Array<{ status: string }>).every((c) => c.status === 'EXPIRING_SOON'),
    ).toBe(true);

    const bad = await request(app.getHttpServer())
      .get('/v1/coupons')
      .set('Authorization', `Bearer ${token}`)
      .query({ status: 'BANANA' })
      .expect(400);
    expect(bad.body.error.code).toBe('BAD_REQUEST');
    expect(typeof bad.body.error.message).toBe('string');
    expect(bad.body.error.requestId).toBeDefined();
  });

  it('returns the common error envelope for unknown routes', async () => {
    const res = await request(app.getHttpServer()).get('/nope').expect(404);
    expect(res.body.error.code).toBe('NOT_FOUND');
  });
});
