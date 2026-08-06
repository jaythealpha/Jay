import { Injectable, NotFoundException } from '@nestjs/common';

import { PrismaService } from '../prisma/prisma.service';

export interface NotificationDto {
  id: string;
  couponId: string;
  message: string;
  offsetDays: number;
  sentAt: string;
}

const DAY_MS = 86_400_000;

@Injectable()
export class NotificationsService {
  constructor(private readonly prisma: PrismaService) {}

  /** Sent reminders for the in-app feed, newest first. */
  async list(userId: string): Promise<{ items: NotificationDto[] }> {
    const rows = await this.prisma.scheduledNotification.findMany({
      where: { userId, status: 'SENT' },
      orderBy: { sentAt: 'desc' },
      take: 50,
    });
    return {
      items: rows.map((row) => ({
        id: row.id,
        couponId: row.couponId,
        message: row.message ?? '',
        offsetDays: row.offsetDays,
        sentAt: (row.sentAt ?? row.updatedAt).toISOString(),
      })),
    };
  }

  /** "하루 뒤 다시 알림": plans a fresh reminder 24h out for the same coupon. */
  async snooze(userId: string, id: string): Promise<{ fireAt: string }> {
    const notification = await this.prisma.scheduledNotification.findUnique({ where: { id } });
    if (!notification || notification.userId !== userId) {
      throw new NotFoundException('알림을 찾을 수 없습니다.');
    }
    const fireAt = new Date(Date.now() + DAY_MS);
    await this.prisma.scheduledNotification.create({
      data: {
        couponId: notification.couponId,
        userId,
        offsetDays: notification.offsetDays,
        fireAt,
      },
    });
    return { fireAt: fireAt.toISOString() };
  }
}
