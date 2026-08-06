import { Injectable, Logger } from '@nestjs/common';
import { recomputeDateDrivenStatus } from '@amc/domain';
import { CouponEventsService } from '../events/coupon-events.service';
import { PrismaService } from '../prisma/prisma.service';

/**
 * Periodic date-driven status recompute (spec §8): ACTIVE ⇄ EXPIRING_SOON and
 * → EXPIRED move automatically as the clock advances; nothing is ever
 * un-expired here. Runs on the maintenance queue and once at boot.
 */
@Injectable()
export class StatusSweepService {
  private readonly logger = new Logger(StatusSweepService.name);

  constructor(
    private readonly prisma: PrismaService,
    private readonly events: CouponEventsService,
  ) {}

  async sweep(now = new Date()): Promise<number> {
    const candidates = await this.prisma.coupon.findMany({
      where: { status: { in: ['ACTIVE', 'EXPIRING_SOON'] }, expiresAt: { not: null } },
      select: { id: true, status: true, expiresAt: true },
      take: 1000,
    });

    let changed = 0;
    for (const coupon of candidates) {
      const next = recomputeDateDrivenStatus(coupon.status, coupon.expiresAt, now);
      if (next === coupon.status) continue;
      await this.prisma.coupon.update({ where: { id: coupon.id }, data: { status: next } });
      await this.events.record(coupon.id, 'STATUS_CHANGED', {
        from: coupon.status,
        to: next,
        source: 'status-sweep',
      });
      changed += 1;
    }

    if (changed > 0) {
      this.logger.log(`Status sweep updated ${changed} coupons`);
    }
    return changed;
  }
}
