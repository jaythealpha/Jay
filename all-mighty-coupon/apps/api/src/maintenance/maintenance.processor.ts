import { InjectQueue, Processor, WorkerHost } from '@nestjs/bullmq';
import { Injectable, Logger, OnApplicationBootstrap } from '@nestjs/common';
import { Job, Queue } from 'bullmq';
import { NotificationDispatcherService } from '../notifications/notification-dispatcher.service';
import { StatusSweepService } from './status-sweep.service';

export const MAINTENANCE_QUEUE = 'coupon-maintenance';

export const JOB_STATUS_SWEEP = 'status-sweep';
export const JOB_DISPATCH_NOTIFICATIONS = 'dispatch-notifications';

/**
 * Registers the repeatable clock jobs at boot (idempotent — BullMQ dedupes by
 * name + repeat options) and runs one immediate sweep so a restarted server
 * catches up without waiting for the first tick.
 */
@Injectable()
export class MaintenanceScheduler implements OnApplicationBootstrap {
  private readonly logger = new Logger(MaintenanceScheduler.name);

  constructor(
    @InjectQueue(MAINTENANCE_QUEUE) private readonly queue: Queue,
    private readonly statusSweep: StatusSweepService,
    private readonly dispatcher: NotificationDispatcherService,
  ) {}

  async onApplicationBootstrap(): Promise<void> {
    await this.queue.add(
      JOB_STATUS_SWEEP,
      {},
      {
        repeat: { every: 10 * 60_000 },
        removeOnComplete: 20,
        removeOnFail: 50,
      },
    );
    await this.queue.add(
      JOB_DISPATCH_NOTIFICATIONS,
      {},
      {
        repeat: { every: 60_000 },
        removeOnComplete: 20,
        removeOnFail: 50,
      },
    );
    // Catch-up pass on boot.
    await this.statusSweep.sweep();
    await this.dispatcher.dispatchDue();
    this.logger.log('Maintenance jobs registered (sweep 10m, dispatch 1m)');
  }
}

@Processor(MAINTENANCE_QUEUE)
export class MaintenanceProcessor extends WorkerHost {
  constructor(
    private readonly statusSweep: StatusSweepService,
    private readonly dispatcher: NotificationDispatcherService,
  ) {
    super();
  }

  override async process(job: Job): Promise<void> {
    // Statuses move before reminders fire so messages reflect fresh state.
    if (job.name === JOB_STATUS_SWEEP) {
      await this.statusSweep.sweep();
    } else if (job.name === JOB_DISPATCH_NOTIFICATIONS) {
      await this.dispatcher.dispatchDue();
    }
  }
}
