import { Global, Module } from '@nestjs/common';
import { NotificationDispatcherService } from './notification-dispatcher.service';
import { NotificationSchedulerService } from './notification-scheduler.service';
import { NotificationsController } from './notifications.controller';
import { NotificationsService } from './notifications.service';

@Global()
@Module({
  controllers: [NotificationsController],
  providers: [NotificationSchedulerService, NotificationDispatcherService, NotificationsService],
  exports: [NotificationSchedulerService, NotificationDispatcherService],
})
export class NotificationsModule {}
