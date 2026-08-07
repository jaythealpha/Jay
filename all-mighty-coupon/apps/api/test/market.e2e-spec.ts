import { INestApplication } from '@nestjs/common';
import { Test } from '@nestjs/testing';
import request from 'supertest';
import { AppModule } from '../src/app.module';
import { BarcodeCryptoService } from '../src/crypto/barcode-crypto.service';
import { PrismaService } from '../src/prisma/prisma.service';

const DAY_MS = 86_400_000;

/**
 * Market (Milestone 4) flows against the real stack: listing eligibility,
 * wallet lock while listed, anonymous browsing, mock-paid purchase with
 * atomic ownership transfer, reminder hand-over, and order history.
 */
describe('Market (e2e)', () => {
  let app: INestApplication;
  let prisma: PrismaService;
  let crypto: BarcodeCryptoService;
  let seller: { token: string; userId: string };
  let buyer: { token: string; userId: string };
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
    crypto = new BarcodeCryptoService();
    seller = await authenticate('e2e-seller@allmightycoupon.local');
    buyer = await authenticate('e2e-buyer@allmightycoupon.local');
  });

  afterAll(async () => {
    await prisma.order.deleteMany({ where: { listing: { couponId: { in: created } } } });
    await prisma.listing.deleteMany({ where: { couponId: { in: created } } });
    await prisma.scheduledNotification.deleteMany({ where: { couponId: { in: created } } });
    await prisma.couponEvent.deleteMany({ where: { couponId: { in: created } } });
    await prisma.coupon.deleteMany({ where: { id: { in: created } } });
    await app.close();
  });

  async function sellableCoupon(overrides: Record<string, unknown> = {}): Promise<string> {
    const coupon = await prisma.coupon.create({
      data: {
        userId: seller.userId,
        brandName: '마켓테스트',
        productName: '아메리카노 교환권',
        faceValueMinor: 4500,
        status: 'ACTIVE',
        sourceType: 'MANUAL',
        requiresReview: false,
        expiresAt: new Date(Date.now() + 30 * DAY_MS),
        barcodeType: 'Code128',
        encryptedBarcode: crypto.encrypt('MARKET-BARCODE-7777'),
        recognitionData: { sampleData: true, source: 'e2e-market' },
        ...overrides,
      } as never,
    });
    created.push(coupon.id);
    return coupon.id;
  }

  it('rejects ineligible listings with the domain reason', async () => {
    const noBarcode = await sellableCoupon({ encryptedBarcode: null, barcodeType: null });
    const res = await request(app.getHttpServer())
      .post('/v1/market/listings')
      .set('Authorization', `Bearer ${seller.token}`)
      .send({ couponId: noBarcode, priceMinor: 3000 })
      .expect(400);
    expect(res.body.error.message).toContain('바코드');

    const expiresToday = await sellableCoupon({ expiresAt: new Date(Date.now() + 3_600_000) });
    await request(app.getHttpServer())
      .post('/v1/market/listings')
      .set('Authorization', `Bearer ${seller.token}`)
      .send({ couponId: expiresToday, priceMinor: 3000 })
      .expect(400);
  });

  it('lists a coupon, locks wallet actions, and prevents double-listing', async () => {
    const couponId = await sellableCoupon();
    const listing = await request(app.getHttpServer())
      .post('/v1/market/listings')
      .set('Authorization', `Bearer ${seller.token}`)
      .send({ couponId, priceMinor: 4000 })
      .expect(201);
    expect(listing.body.feeMinor).toBe(200); // 5% of 4000
    expect(listing.body.mine).toBe(true);

    // Wallet actions are locked while listed.
    await request(app.getHttpServer())
      .post(`/v1/coupons/${couponId}/redeem`)
      .set('Authorization', `Bearer ${seller.token}`)
      .expect(400);
    await request(app.getHttpServer())
      .delete(`/v1/coupons/${couponId}`)
      .set('Authorization', `Bearer ${seller.token}`)
      .expect(400);

    // No second live listing for the same coupon.
    await request(app.getHttpServer())
      .post('/v1/market/listings')
      .set('Authorization', `Bearer ${seller.token}`)
      .send({ couponId, priceMinor: 5000 })
      .expect(409);

    // Cancel unlocks the wallet again.
    await request(app.getHttpServer())
      .delete(`/v1/market/listings/${listing.body.id}`)
      .set('Authorization', `Bearer ${seller.token}`)
      .expect(204);
    await request(app.getHttpServer())
      .post(`/v1/coupons/${couponId}/redeem`)
      .set('Authorization', `Bearer ${seller.token}`)
      .expect(200);
  });

  it('browsing shows anonymous listings without barcode material', async () => {
    const couponId = await sellableCoupon({ brandName: '브라우즈카페' });
    await request(app.getHttpServer())
      .post('/v1/market/listings')
      .set('Authorization', `Bearer ${seller.token}`)
      .send({ couponId, priceMinor: 3500 })
      .expect(201);

    const res = await request(app.getHttpServer())
      .get('/v1/market/listings')
      .set('Authorization', `Bearer ${buyer.token}`)
      .query({ q: '브라우즈' })
      .expect(200);
    expect(res.body.total).toBe(1);
    const item = res.body.items[0];
    expect(item.coupon.brandName).toBe('브라우즈카페');
    expect(item.mine).toBe(false);

    const serialized = JSON.stringify(res.body);
    expect(serialized).not.toContain('sellerId');
    expect(serialized).not.toContain('@allmightycoupon.local');
    expect(serialized).not.toContain('MARKET-BARCODE-7777');
    expect(serialized).not.toContain('barcodeHash');
  });

  it('purchase transfers ownership, moves reminders, and blocks self-purchase', async () => {
    const couponId = await sellableCoupon({ brandName: '이전테스트' });
    const listing = await request(app.getHttpServer())
      .post('/v1/market/listings')
      .set('Authorization', `Bearer ${seller.token}`)
      .send({ couponId, priceMinor: 6000 })
      .expect(201);
    // Seller had a reminder plan before the sale.
    await prisma.scheduledNotification.create({
      data: {
        couponId,
        userId: seller.userId,
        offsetDays: 7,
        fireAt: new Date(Date.now() + 23 * DAY_MS),
      },
    });

    await request(app.getHttpServer())
      .post(`/v1/market/listings/${listing.body.id}/purchase`)
      .set('Authorization', `Bearer ${seller.token}`)
      .expect(400); // self-purchase blocked

    const order = await request(app.getHttpServer())
      .post(`/v1/market/listings/${listing.body.id}/purchase`)
      .set('Authorization', `Bearer ${buyer.token}`)
      .expect(200);
    expect(order.body.status).toBe('COMPLETED');
    expect(order.body.role).toBe('BUYER');

    // Ownership moved: buyer sees it, seller gets 404.
    await request(app.getHttpServer())
      .get(`/v1/coupons/${couponId}`)
      .set('Authorization', `Bearer ${buyer.token}`)
      .expect(200);
    await request(app.getHttpServer())
      .get(`/v1/coupons/${couponId}`)
      .set('Authorization', `Bearer ${seller.token}`)
      .expect(404);

    // Reminders follow the coupon: pending rows now belong to the buyer only.
    const pending = await prisma.scheduledNotification.findMany({
      where: { couponId, status: 'PENDING' },
    });
    expect(pending.length).toBeGreaterThan(0);
    expect(pending.every((row) => row.userId === buyer.userId)).toBe(true);

    // Sold listings cannot be bought again.
    await request(app.getHttpServer())
      .post(`/v1/market/listings/${listing.body.id}/purchase`)
      .set('Authorization', `Bearer ${buyer.token}`)
      .expect(404);

    // Ownership transfer is on the audit trail; payment ref is mock-tagged.
    const events = await prisma.couponEvent.findMany({ where: { couponId } });
    expect(events.map((event) => event.type)).toContain('OWNERSHIP_TRANSFERRED');
    const orderRow = await prisma.order.findUnique({ where: { id: order.body.id } });
    expect(orderRow?.paymentRef).toMatch(/^MOCK-/);

    // Both sides see the order in history with their own role.
    const buyerOrders = await request(app.getHttpServer())
      .get('/v1/market/orders')
      .set('Authorization', `Bearer ${buyer.token}`)
      .expect(200);
    expect(
      (buyerOrders.body.items as Array<{ id: string; role: string }>).find(
        (item) => item.id === order.body.id,
      )?.role,
    ).toBe('BUYER');
    const sellerOrders = await request(app.getHttpServer())
      .get('/v1/market/orders')
      .set('Authorization', `Bearer ${seller.token}`)
      .expect(200);
    expect(
      (sellerOrders.body.items as Array<{ id: string; role: string }>).find(
        (item) => item.id === order.body.id,
      )?.role,
    ).toBe('SELLER');
  });
});
