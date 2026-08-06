import { INestApplication } from '@nestjs/common';
import { Test } from '@nestjs/testing';
import request from 'supertest';
import { AppModule } from '../src/app.module';
import { NotificationDispatcherService } from '../src/notifications/notification-dispatcher.service';
import { NoopPushSender } from '../src/push/noop-push-sender';
import { PushSender } from '../src/push/push-sender';
import { PrismaService } from '../src/prisma/prisma.service';

/**
 * Milestone 4a/4c flows: push-device registration feeding the dispatcher's
 * push channel (Noop sender without FCM credentials), and the ops-token-
 * guarded admin stats API.
 */
describe('Push devices & Admin (e2e)', () => {
  let app: INestApplication;
  let prisma: PrismaService;
  let token: string;
  let userId: string;
  const created: string[] = [];
  const deviceToken = 'e2e-device-token-0123456789';

  beforeAll(async () => {
    const moduleRef = await Test.createTestingModule({ imports: [AppModule] }).compile();
    app = moduleRef.createNestApplication();
    await app.init();
    prisma = app.get(PrismaService);

    const credentials = { email: 'e2e-push@allmightycoupon.local', password: 'e2e-password-1234' };
    const registered = await request(app.getHttpServer())
      .post('/v1/auth/register')
      .send(credentials);
    const auth =
      registered.status === 201
        ? registered
        : await request(app.getHttpServer()).post('/v1/auth/login').send(credentials).expect(200);
    token = auth.body.accessToken as string;
    userId = auth.body.user.id as string;
  });

  afterAll(async () => {
    await prisma.pushDevice.deleteMany({ where: { userId } });
    await prisma.scheduledNotification.deleteMany({ where: { userId } });
    await prisma.couponEvent.deleteMany({ where: { couponId: { in: created } } });
    await prisma.coupon.deleteMany({ where: { id: { in: created } } });
    await app.close();
  });

  it('registers a device idempotently and pushes due reminders through the sender', async () => {
    await request(app.getHttpServer())
      .post('/v1/devices')
      .set('Authorization', `Bearer ${token}`)
      .send({ token: deviceToken, platform: 'ANDROID' })
      .expect(204);
    // Re-registration must not duplicate.
    await request(app.getHttpServer())
      .post('/v1/devices')
      .set('Authorization', `Bearer ${token}`)
      .send({ token: deviceToken, platform: 'ANDROID' })
      .expect(204);
    expect(await prisma.pushDevice.count({ where: { userId } })).toBe(1);

    const coupon = await prisma.coupon.create({
      data: {
        userId,
        brandName: '푸시테스트',
        productName: '아메리카노',
        status: 'EXPIRING_SOON',
        sourceType: 'MANUAL',
        requiresReview: false,
        expiresAt: new Date(Date.now() + 3 * 86_400_000),
        recognitionData: { sampleData: true, source: 'e2e-push' },
      },
    });
    created.push(coupon.id);
    await prisma.scheduledNotification.create({
      data: {
        couponId: coupon.id,
        userId,
        offsetDays: 3,
        fireAt: new Date(Date.now() - 60_000),
      },
    });

    const sender = app.get(PushSender);
    expect(sender).toBeInstanceOf(NoopPushSender); // no FCM credentials in tests
    const noop = sender as NoopPushSender;
    const before = noop.delivered.length;

    await app.get(NotificationDispatcherService).dispatchDue();

    const delivered = noop.delivered.slice(before);
    const mine = delivered.find((entry) => entry.body.includes('푸시테스트'));
    expect(mine).toBeDefined();
    expect(mine!.tokenCount).toBe(1);
    // The push record never carries the device token value.
    expect(JSON.stringify(delivered)).not.toContain(deviceToken);
  });

  it('unregisters the device', async () => {
    await request(app.getHttpServer())
      .delete('/v1/devices')
      .set('Authorization', `Bearer ${token}`)
      .send({ token: deviceToken })
      .expect(204);
    expect(await prisma.pushDevice.count({ where: { userId } })).toBe(0);
  });

  it('admin stats requires the ops token — user JWTs are not enough', async () => {
    await request(app.getHttpServer()).get('/v1/admin/stats').expect(401);
    await request(app.getHttpServer())
      .get('/v1/admin/stats')
      .set('Authorization', `Bearer ${token}`)
      .expect(401);
    await request(app.getHttpServer())
      .get('/v1/admin/stats')
      .set('x-admin-token', 'wrong-token-wrong-token-wrong')
      .expect(401);
  });

  it('admin stats returns counts only — no emails, no barcode material', async () => {
    const adminToken = process.env.ADMIN_API_TOKEN;
    expect(adminToken).toBeDefined();

    const res = await request(app.getHttpServer())
      .get('/v1/admin/stats')
      .set('x-admin-token', adminToken as string)
      .expect(200);

    expect(res.body.users).toBeGreaterThanOrEqual(1);
    expect(typeof res.body.couponsByStatus).toBe('object');
    expect(res.body.notifications).toHaveProperty('sent');
    expect(Array.isArray(res.body.recentEvents)).toBe(true);

    const serialized = JSON.stringify(res.body);
    expect(serialized).not.toContain('@allmightycoupon.local');
    expect(serialized).not.toContain('encryptedBarcode');
    expect(serialized).not.toContain('barcodeHash');
  });
});
