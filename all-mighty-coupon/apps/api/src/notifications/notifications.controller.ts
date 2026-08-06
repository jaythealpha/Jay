import { Controller, Get, HttpCode, Param, Post } from '@nestjs/common';
import { ApiBearerAuth, ApiOperation, ApiTags } from '@nestjs/swagger';
import { CurrentUser } from '../auth/current-user.decorator';
import type { AuthenticatedUser } from '../auth/jwt-auth.guard';
import { NotificationsService, type NotificationDto } from './notifications.service';

@ApiTags('notifications')
@ApiBearerAuth()
@Controller('v1/notifications')
export class NotificationsController {
  constructor(private readonly notificationsService: NotificationsService) {}

  @Get()
  @ApiOperation({ summary: 'In-app expiration reminder feed (deep link via couponId)' })
  async list(@CurrentUser() user: AuthenticatedUser): Promise<{ items: NotificationDto[] }> {
    return this.notificationsService.list(user.id);
  }

  @Post(':id/snooze')
  @HttpCode(200)
  @ApiOperation({ summary: 'Remind again tomorrow (하루 뒤 다시 알림)' })
  async snooze(
    @CurrentUser() user: AuthenticatedUser,
    @Param('id') id: string,
  ): Promise<{ fireAt: string }> {
    return this.notificationsService.snooze(user.id, id);
  }
}
