import { Injectable, Logger } from '@nestjs/common';
import { daysUntilExpiration } from '@amc/domain';
import { buildNotificationMessage } from '@amc/notification-policy';
import { CouponEventsService } from '../events/coupon-events.service';
import { PrismaService } from '../prisma/prisma.service';
import { PushSender } from '../push/push-sender';

/**
 * Delivers due reminders to both channels: the in-app feed (always) and push
 * devices via the configured PushSender (FCM when credentials exist, no-op
 * otherwise). Delivery double-checks eligibility so a reminder never fires
 * for a coupon that was redeemed/archived after scheduling.
 */
@Injectable()
export class NotificationDispatcherService {
  private readonly logger = new Logger(NotificationDispatcherService.name);

  constructor(
    private readonly prisma: PrismaService,
    private readonly events: CouponEventsService,
    private readonly pushSender: PushSender,
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
        channel: this.pushSender.channelName,
      });
      await this.pushTo(notification.userId, notification.id, coupon.id, message);
      sent += 1;
    }

    if (sent > 0) {
      this.logger.log(`Dispatched ${sent} expiration reminders`);
    }
    return sent;
  }

  private async pushTo(
    userId: string,
    notificationId: string,
    couponId: string,
    body: string,
  ): Promise<void> {
    const devices = await this.prisma.pushDevice.findMany({
      where: { userId },
      select: { token: true },
    });
    if (devices.length === 0) return;

    try {
      const result = await this.pushSender.send({
        tokens: devices.map((device) => device.token),
        title: '쿠폰 만료 알림',
        body,
        data: { couponId, notificationId },
      });
      if (result.invalidTokens.length > 0) {
        await this.prisma.pushDevice.deleteMany({
          where: { token: { in: result.invalidTokens } },
        });
      }
    } catch (error) {
      // Push is best-effort — the in-app feed already has the reminder, and a
      // provider outage must not fail the dispatch loop.
      this.logger.warn(`push delivery failed: ${(error as Error).message}`);
    }
  }
}
