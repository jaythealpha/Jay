import { Injectable, Logger } from '@nestjs/common';
import { daysUntilExpiration } from '@amc/domain';
import { buildNotificationMessage } from '@amc/notification-policy';
import { CouponEventsService } from '../events/coupon-events.service';
import { PrismaService } from '../prisma/prisma.service';

/**
 * Delivers due reminders. Milestone 3 channel: the in-app notification feed
 * (GET /v1/notifications) — the same rows become push payloads once FCM/APNs
 * integration lands. Delivery double-checks eligibility so a reminder never
 * fires for a coupon that was redeemed/archived after scheduling.
 */
@Injectable()
export class NotificationDispatcherService {
  private readonly logger = new Logger(NotificationDispatcherService.name);

  constructor(
    private readonly prisma: PrismaService,
    private readonly events: CouponEventsService,
  ) {}

  async dispatchDue(now = new Date()): Promise<number> {
    const due = await this.prisma.scheduledNotification.findMany({
      where: { status: 'PENDING', fireAt: { lte: now } },
      include: { coupon: true },
      take: 200,
      orderBy: { fireAt: 'asc' },
    });

    let sent = 0;
    for (const notification of due) {
      const coupon = notification.coupon;
      const ineligible = coupon.status === 'REDEEMED' || coupon.status === 'ARCHIVED';
      if (ineligible) {
        await this.prisma.scheduledNotification.update({
          where: { id: notification.id },
          data: { status: 'CANCELLED' },
        });
        continue;
      }

      const daysLeft = coupon.expiresAt ? daysUntilExpiration(coupon.expiresAt, now) : 0;
      const message = buildNotificationMessage({
        brandName: coupon.brandName,
        productName: coupon.productName,
        faceValueMinor: coupon.faceValueMinor,
        daysLeft: Math.max(0, daysLeft),
      });

      await this.prisma.scheduledNotification.update({
        where: { id: notification.id },
        data: { status: 'SENT', sentAt: now, message },
      });
      await this.events.record(coupon.id, 'NOTIFICATION_SENT', {
        offsetDays: notification.offsetDays,
      });
      sent += 1;
    }

    if (sent > 0) {
      this.logger.log(`Dispatched ${sent} expiration reminders`);
    }
    return sent;
  }
}
