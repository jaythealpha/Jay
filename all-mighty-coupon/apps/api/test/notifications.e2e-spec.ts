import { INestApplication } from '@nestjs/common';
import { Test } from '@nestjs/testing';
import request from 'supertest';
import { AppModule } from '../src/app.module';
import { NotificationDispatcherService } from '../src/notifications/notification-dispatcher.service';
import { StatusSweepService } from '../src/maintenance/status-sweep.service';
import { PrismaService } from '../src/prisma/prisma.service';

const DAY_MS = 86_400_000;

/**
 * Never Expire (M3) flows against the real stack: reminder scheduling on
 * edit/confirm, cancellation on redeem, dispatch to the in-app feed with the
 * brand+days message rule, snooze, automatic status sweep, and the
 * action-first home summary.
 */
describe('Notifications & Never Expire (e2e)', () => {
  let app: INestApplication;
  let prisma: PrismaService;
  let token: string;
  let userId: string;
  const created: string[] = [];

  beforeAll(async () => {
    const moduleRef = await Test.createTestingModule({ imports: [AppModule] }).compile();
    app = moduleRef.createNestApplication();
    await app.init();
    prisma = app.get(PrismaService);

    const credentials = {
      email: 'e2e-notify@allmightycoupon.local',
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
    userId = auth.body.user.id as string;
  });

  afterAll(async () => {
    await prisma.scheduledNotification.deleteMany({ where: { userId } });
    await prisma.couponEvent.deleteMany({ where: { couponId: { in: created } } });
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
        recognitionData: { sampleData: true, source: 'e2e-notify' },
        ...data,
      } as never,
    });
    created.push(coupon.id);
    return coupon.id;
  }

  async function pendingFor(couponId: string) {
    return prisma.scheduledNotification.findMany({
      where: { couponId, status: 'PENDING' },
      orderBy: { fireAt: 'asc' },
    });
  }

  it('editing the expiry plans only the remaining touchpoints (5 days → 3-day + day-of)', async () => {
    const id = await createCoupon({ brandName: '알림테스트' });
    const expiresAt = new Date(Date.now() + 5 * DAY_MS).toISOString().slice(0, 10);

    await request(app.getHttpServer())
      .patch(`/v1/coupons/${id}`)
      .set('Authorization', `Bearer ${token}`)
      .send({ expiresAt })
      .expect(200);

    const pending = await pendingFor(id);
    expect(pending.map((n) => n.offsetDays)).toEqual([3, 0]);

    const events = await prisma.couponEvent.findMany({ where: { couponId: id } });
    expect(events.map((e) => e.type)).toContain('NOTIFICATION_SCHEDULED');
  });

  it('redeem cancels pending reminders; restore re-plans them', async () => {
    const id = await createCoupon({
      brandName: '취소테스트',
      expiresAt: new Date(Date.now() + 40 * DAY_MS),
    });
    await request(app.getHttpServer())
      .patch(`/v1/coupons/${id}`)
      .set('Authorization', `Bearer ${token}`)
      .send({ productName: '리마인더용' })
      .expect(200);
    // Direct schedule via expiry edit:
    await request(app.getHttpServer())
      .patch(`/v1/coupons/${id}`)
      .set('Authorization', `Bearer ${token}`)
      .send({ expiresAt: new Date(Date.now() + 40 * DAY_MS).toISOString().slice(0, 10) })
      .expect(200);
    expect((await pendingFor(id)).length).toBeGreaterThan(0);

    await request(app.getHttpServer())
      .post(`/v1/coupons/${id}/redeem`)
      .set('Authorization', `Bearer ${token}`)
      .expect(200);
    expect(await pendingFor(id)).toHaveLength(0);

    await request(app.getHttpServer())
      .post(`/v1/coupons/${id}/restore`)
      .set('Authorization', `Bearer ${token}`)
      .expect(200);
    expect((await pendingFor(id)).length).toBeGreaterThan(0);
  });

  it('dispatches due reminders to the feed with brand + days message, supports snooze', async () => {
    const id = await createCoupon({
      brandName: '스타벅스',
      productName: '아메리카노',
      expiresAt: new Date(Date.now() + 3 * DAY_MS),
      status: 'EXPIRING_SOON',
    });
    await prisma.scheduledNotification.create({
      data: {
        couponId: id,
        userId,
        offsetDays: 3,
        fireAt: new Date(Date.now() - 60_000), // already due
      },
    });

    const sent = await app.get(NotificationDispatcherService).dispatchDue();
    expect(sent).toBeGreaterThanOrEqual(1);

    const feed = await request(app.getHttpServer())
      .get('/v1/notifications')
      .set('Authorization', `Bearer ${token}`)
      .expect(200);
    const item = (feed.body.items as Array<Record<string, string>>).find(
      (entry) => entry.couponId === id,
    );
    expect(item).toBeDefined();
    // Message rule (spec §16): brand + product + remaining days, never vague.
    expect(item!.message).toContain('스타벅스');
    expect(item!.message).toContain('아메리카노');
    expect(item!.message).toContain('3일 뒤 만료');

    const snoozed = await request(app.getHttpServer())
      .post(`/v1/notifications/${item!.id}/snooze`)
      .set('Authorization', `Bearer ${token}`)
      .expect(200);
    const fireAt = new Date(snoozed.body.fireAt as string).getTime();
    expect(fireAt).toBeGreaterThan(Date.now() + 23 * 3_600_000);
    expect((await pendingFor(id)).length).toBeGreaterThanOrEqual(1);
  });

  it('never delivers reminders for coupons redeemed after scheduling', async () => {
    const id = await createCoupon({
      brandName: '사용후알림테스트',
      status: 'REDEEMED',
      redeemedAt: new Date(),
      expiresAt: new Date(Date.now() + 2 * DAY_MS),
    });
    await prisma.scheduledNotification.create({
      data: { couponId: id, userId, offsetDays: 3, fireAt: new Date(Date.now() - 60_000) },
    });

    await app.get(NotificationDispatcherService).dispatchDue();

    const rows = await prisma.scheduledNotification.findMany({ where: { couponId: id } });
    expect(rows.every((row) => row.status === 'CANCELLED')).toBe(true);
  });

  it('status sweep expires and flags coupons automatically, never un-expires', async () => {
    const expired = await createCoupon({
      brandName: '스윕만료',
      expiresAt: new Date(Date.now() - 2 * DAY_MS),
    });
    const soon = await createCoupon({
      brandName: '스윕임박',
      expiresAt: new Date(Date.now() + 2 * DAY_MS),
    });
    const far = await createCoupon({
      brandName: '스윕여유',
      expiresAt: new Date(Date.now() + 60 * DAY_MS),
    });

    await app.get(StatusSweepService).sweep();

    const statuses = Object.fromEntries(
      (
        await prisma.coupon.findMany({
          where: { id: { in: [expired, soon, far] } },
          select: { id: true, status: true },
        })
      ).map((c) => [c.id, c.status]),
    );
    expect(statuses[expired]).toBe('EXPIRED');
    expect(statuses[soon]).toBe('EXPIRING_SOON');
    expect(statuses[far]).toBe('ACTIVE');

    const events = await prisma.couponEvent.findMany({ where: { couponId: expired } });
    expect(events.some((e) => e.type === 'STATUS_CHANGED')).toBe(true);

    // Running the sweep again never resurrects EXPIRED.
    await app.get(StatusSweepService).sweep();
    const after = await prisma.coupon.findUnique({ where: { id: expired } });
    expect(after?.status).toBe('EXPIRED');
  });

  it('GET /v1/home returns action-first sections and an honest summary', async () => {
    const res = await request(app.getHttpServer())
      .get('/v1/home')
      .set('Authorization', `Bearer ${token}`)
      .expect(200);

    const body = res.body as {
      expiringSoon: Array<{ brandName: string }>;
      useThisWeek: Array<{ brandName: string }>;
      recent: unknown[];
      counts: { total: number; expiringSoon: number };
      totalValueMinor: number;
    };

    // 스윕임박 (2 days out) must surface in both urgency sections.
    expect(body.expiringSoon.map((c) => c.brandName)).toContain('스윕임박');
    expect(body.useThisWeek.map((c) => c.brandName)).toContain('스윕임박');
    expect(body.recent.length).toBeGreaterThanOrEqual(1);
    expect(body.counts.total).toBeGreaterThanOrEqual(3);
    expect(body.counts.expiringSoon).toBeGreaterThanOrEqual(1);
    expect(typeof body.totalValueMinor).toBe('number');
  });
});
