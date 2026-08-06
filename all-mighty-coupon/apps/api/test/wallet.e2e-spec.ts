import { INestApplication } from '@nestjs/common';
import { Test } from '@nestjs/testing';
import request from 'supertest';
import { AppModule } from '../src/app.module';
import { PrismaService } from '../src/prisma/prisma.service';

/**
 * Wallet MVP flows against the real stack: auth boundary, user scoping,
 * search/sort, redeem → restore, archive, barcode reveal + audit, delete.
 */
describe('Wallet (e2e)', () => {
  let app: INestApplication;
  let prisma: PrismaService;
  let token: string;
  let userId: string;
  const created: string[] = [];

  async function authenticate(email: string): Promise<{ token: string; userId: string }> {
    const credentials = { email, password: 'e2e-password-1234' };
    const registered = await request(app.getHttpServer())
      .post('/v1/auth/register')
      .send(credentials);
    const auth =
      registered.status === 201
        ? registered
        : await request(app.getHttpServer()).post('/v1/auth/login').send(credentials).expect(200);
    return { token: auth.body.accessToken as string, userId: auth.body.user.id as string };
  }

  beforeAll(async () => {
    const moduleRef = await Test.createTestingModule({ imports: [AppModule] }).compile();
    app = moduleRef.createNestApplication();
    await app.init();
    prisma = app.get(PrismaService);
    ({ token, userId } = await authenticate('e2e-wallet@allmightycoupon.local'));
  });

  afterAll(async () => {
    await prisma.couponEvent.deleteMany({ where: { couponId: { in: created } } });
    await prisma.couponAsset.deleteMany({ where: { couponId: { in: created } } });
    await prisma.coupon.deleteMany({ where: { id: { in: created } } });
    await app.close();
  });

  async function createCoupon(data: Record<string, unknown>): Promise<string> {
    const coupon = await prisma.coupon.create({
      data: {
        userId,
        status: 'ACTIVE',
        sourceType: 'MANUAL',
        requiresReview: false,
        recognitionData: { sampleData: true, source: 'e2e-wallet' },
        ...data,
      } as never,
    });
    created.push(coupon.id);
    return coupon.id;
  }

  it('rejects unauthenticated coupon access with 401 envelope', async () => {
    const res = await request(app.getHttpServer()).get('/v1/coupons').expect(401);
    expect(res.body.error.code).toBe('UNAUTHORIZED');
  });

  it('rejects a wrong password with a generic message', async () => {
    const res = await request(app.getHttpServer())
      .post('/v1/auth/login')
      .send({ email: 'e2e-wallet@allmightycoupon.local', password: 'wrong-password-1' })
      .expect(401);
    expect(res.body.error.message).toBe('이메일 또는 비밀번호가 올바르지 않습니다.');
  });

  it('scopes coupons to their owner (foreign coupon → 404)', async () => {
    const couponId = await createCoupon({ brandName: '스코프테스트' });
    const other = await authenticate('e2e-wallet-other@allmightycoupon.local');
    await request(app.getHttpServer())
      .get(`/v1/coupons/${couponId}`)
      .set('Authorization', `Bearer ${other.token}`)
      .expect(404);
    await request(app.getHttpServer())
      .get(`/v1/coupons/${couponId}`)
      .set('Authorization', `Bearer ${token}`)
      .expect(200);
  });

  it('searches by brand/product and sorts by value', async () => {
    await createCoupon({ brandName: '검색카페', productName: '수박주스', faceValueMinor: 6000 });
    await createCoupon({ brandName: '검색마트', productName: '금액권', faceValueMinor: 50000 });

    const search = await request(app.getHttpServer())
      .get('/v1/coupons')
      .set('Authorization', `Bearer ${token}`)
      .query({ q: '수박' })
      .expect(200);
    expect(search.body.total).toBe(1);
    expect(search.body.items[0].productName).toBe('수박주스');

    const sorted = await request(app.getHttpServer())
      .get('/v1/coupons')
      .set('Authorization', `Bearer ${token}`)
      .query({ q: '검색', sort: 'VALUE_DESC' })
      .expect(200);
    expect(sorted.body.items[0].faceValueMinor).toBe(50000);

    await request(app.getHttpServer())
      .get('/v1/coupons')
      .set('Authorization', `Bearer ${token}`)
      .query({ sort: 'SIDEWAYS' })
      .expect(400);
  });

  it('redeem → restore recomputes status and records events', async () => {
    const id = await createCoupon({
      brandName: '사용테스트',
      expiresAt: new Date(Date.now() + 60 * 86_400_000),
    });

    const redeemed = await request(app.getHttpServer())
      .post(`/v1/coupons/${id}/redeem`)
      .set('Authorization', `Bearer ${token}`)
      .expect(200);
    expect(redeemed.body.status).toBe('REDEEMED');

    // Double-redeem is an invalid transition → user error, not a crash.
    await request(app.getHttpServer())
      .post(`/v1/coupons/${id}/redeem`)
      .set('Authorization', `Bearer ${token}`)
      .expect(400);

    const restored = await request(app.getHttpServer())
      .post(`/v1/coupons/${id}/restore`)
      .set('Authorization', `Bearer ${token}`)
      .expect(200);
    expect(restored.body.status).toBe('ACTIVE');

    const events = await prisma.couponEvent.findMany({ where: { couponId: id } });
    const types = events.map((e) => e.type);
    expect(types).toContain('MARKED_REDEEMED');
    expect(types).toContain('RESTORED_TO_ACTIVE');
  });

  it('restoring an expired redeemed coupon lands on EXPIRED, not ACTIVE', async () => {
    const id = await createCoupon({
      brandName: '만료복구테스트',
      status: 'REDEEMED',
      redeemedAt: new Date(),
      expiresAt: new Date(Date.now() - 5 * 86_400_000),
    });
    const restored = await request(app.getHttpServer())
      .post(`/v1/coupons/${id}/restore`)
      .set('Authorization', `Bearer ${token}`)
      .expect(200);
    expect(restored.body.status).toBe('EXPIRED');
  });

  it('archives and unarchives with date-driven recompute', async () => {
    const id = await createCoupon({
      brandName: '보관테스트',
      expiresAt: new Date(Date.now() + 3 * 86_400_000),
    });
    const archived = await request(app.getHttpServer())
      .post(`/v1/coupons/${id}/archive`)
      .set('Authorization', `Bearer ${token}`)
      .expect(200);
    expect(archived.body.status).toBe('ARCHIVED');

    const unarchived = await request(app.getHttpServer())
      .post(`/v1/coupons/${id}/unarchive`)
      .set('Authorization', `Bearer ${token}`)
      .expect(200);
    // 3 days out → straight into EXPIRING_SOON, not plain ACTIVE.
    expect(unarchived.body.status).toBe('EXPIRING_SOON');
  });

  it('reveals the barcode once decrypted and audit-logs the view', async () => {
    // Store a real encrypted payload through the crypto service used in prod.
    const { BarcodeCryptoService } = await import('../src/crypto/barcode-crypto.service');
    const crypto = new BarcodeCryptoService();
    const id = await createCoupon({
      brandName: '바코드테스트',
      barcodeType: 'Code128',
      encryptedBarcode: crypto.encrypt('WALLET-BARCODE-1234'),
    });

    const res = await request(app.getHttpServer())
      .get(`/v1/coupons/${id}/barcode`)
      .set('Authorization', `Bearer ${token}`)
      .expect(200);
    expect(res.body.value).toBe('WALLET-BARCODE-1234');
    expect(res.body.format).toBe('Code128');

    const events = await prisma.couponEvent.findMany({ where: { couponId: id } });
    const view = events.find((e) => e.type === 'BARCODE_VIEWED');
    expect(view).toBeDefined();
    // Audit metadata carries only the masked value.
    expect(JSON.stringify(view?.metadata)).not.toContain('WALLET-BARCODE-1234');
    expect(JSON.stringify(view?.metadata)).toContain('1234');
  });

  it('deletes a coupon and returns 404 afterwards', async () => {
    const id = await createCoupon({ brandName: '삭제테스트' });
    await request(app.getHttpServer())
      .delete(`/v1/coupons/${id}`)
      .set('Authorization', `Bearer ${token}`)
      .expect(204);
    await request(app.getHttpServer())
      .get(`/v1/coupons/${id}`)
      .set('Authorization', `Bearer ${token}`)
      .expect(404);
  });
});
