import { Controller, Get } from '@nestjs/common';
import { ApiBearerAuth, ApiOperation, ApiTags } from '@nestjs/swagger';
import { CurrentUser } from '../auth/current-user.decorator';
import type { AuthenticatedUser } from '../auth/jwt-auth.guard';
import { HomeService, type HomeSummaryDto } from './home.service';

@ApiTags('home')
@ApiBearerAuth()
@Controller('v1/home')
export class HomeController {
  constructor(private readonly homeService: HomeService) {}

  @Get()
  @ApiOperation({ summary: 'Action-first home: expiring soon, use this week, recent, summary' })
  async summary(@CurrentUser() user: AuthenticatedUser): Promise<HomeSummaryDto> {
    return this.homeService.summary(user.id);
  }
}
