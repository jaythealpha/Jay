import { BullModule } from '@nestjs/bullmq';
import { Module } from '@nestjs/common';
import {
  MAINTENANCE_QUEUE,
  MaintenanceProcessor,
  MaintenanceScheduler,
} from './maintenance.processor';
import { StatusSweepService } from './status-sweep.service';

@Module({
  imports: [BullModule.registerQueue({ name: MAINTENANCE_QUEUE })],
  providers: [StatusSweepService, MaintenanceScheduler, MaintenanceProcessor],
  exports: [StatusSweepService],
})
export class MaintenanceModule {}
