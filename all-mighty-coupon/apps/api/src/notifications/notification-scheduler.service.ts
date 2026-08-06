import { Injectable } from '@nestjs/common';
import type { Coupon } from '@prisma/client';
import { planExpirationNotifications } from '@amc/notification-policy';
import { CouponEventsService } from '../events/coupon-events.service';
import { PrismaService } from '../prisma/prisma.service';

/**
 * Applies the pure notification policy (spec §16) to storage:
 * - schedule: only future touchpoints (30/7/3/day-of 09:00) become PENDING rows
 * - cancel: redeem/archive/delete voids every pending reminder
 * - reschedule: expiry changes cancel + re-plan
 */
@Injectable()
export class NotificationSchedulerService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly events: CouponEventsService,
  ) {}

  async scheduleFor(coupon: Coupon, now = new Date()): Promise<number> {
    await this.cancelFor(coupon.id);
    if (coupon.expiresAt === null) return 0;
    if (coupon.status !== 'ACTIVE' && coupon.status !== 'EXPIRING_SOON') return 0;

    const plan = planExpirationNotifications({ expiresAt: coupon.expiresAt, now });
    if (plan.length === 0) return 0;

    await this.prisma.scheduledNotification.createMany({
      data: plan.map((entry) => ({
        couponId: coupon.id,
        userId: coupon.userId,
        offsetDays: entry.offsetDays,
        fireAt: entry.fireAt,
      })),
    });
    await this.events.record(coupon.id, 'NOTIFICATION_SCHEDULED', {
      offsets: plan.map((entry) => entry.offsetDays),
    });
    return plan.length;
  }

  async cancelFor(couponId: string): Promise<void> {
    await this.prisma.scheduledNotification.updateMany({
      where: { couponId, status: 'PENDING' },
      data: { status: 'CANCELLED' },
    });
  }

  async rescheduleFor(coupon: Coupon, now = new Date()): Promise<number> {
    return this.scheduleFor(coupon, now);
  }
}
