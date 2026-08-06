import { Injectable } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';

export interface AdminStatsDto {
  users: number;
  pushDevices: number;
  couponsByStatus: Record<string, number>;
  notifications: { pending: number; sent: number; cancelled: number };
  /** Latest domain events — types and timestamps only, no payloads. */
  recentEvents: Array<{ type: string; couponId: string; createdAt: string }>;
  generatedAt: string;
}

/**
 * Read-only operations snapshot. Nothing sensitive crosses this boundary:
 * no emails, no barcode material, no event metadata (spec §17 — operators
 * cannot see raw barcodes either).
 */
@Injectable()
export class AdminService {
  constructor(private readonly prisma: PrismaService) {}

  async stats(): Promise<AdminStatsDto> {
    const [users, pushDevices, couponGroups, notificationGroups, recentEvents] = await Promise.all([
      this.prisma.user.count(),
      this.prisma.pushDevice.count(),
      this.prisma.coupon.groupBy({ by: ['status'], _count: { _all: true } }),
      this.prisma.scheduledNotification.groupBy({ by: ['status'], _count: { _all: true } }),
      this.prisma.couponEvent.findMany({
        orderBy: { createdAt: 'desc' },
        take: 20,
        select: { type: true, couponId: true, createdAt: true },
      }),
    ]);

    const notificationCount = (status: string): number =>
      notificationGroups.find((group) => group.status === status)?._count._all ?? 0;

    return {
      users,
      pushDevices,
      couponsByStatus: Object.fromEntries(
        couponGroups.map((group) => [group.status, group._count._all]),
      ),
      notifications: {
        pending: notificationCount('PENDING'),
        sent: notificationCount('SENT'),
        cancelled: notificationCount('CANCELLED'),
      },
      recentEvents: recentEvents.map((event) => ({
        type: event.type,
        couponId: event.couponId,
        createdAt: event.createdAt.toISOString(),
      })),
      generatedAt: new Date().toISOString(),
    };
  }
}
