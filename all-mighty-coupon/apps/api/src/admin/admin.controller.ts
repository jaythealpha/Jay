import { Controller, Get, UseGuards } from '@nestjs/common';
import { ApiHeader, ApiOperation, ApiTags } from '@nestjs/swagger';
import { Public } from '../auth/public.decorator';
import { AdminGuard } from './admin.guard';
import { AdminService, type AdminStatsDto } from './admin.service';

@ApiTags('admin')
@ApiHeader({ name: 'x-admin-token', description: 'Operator token (ADMIN_API_TOKEN)' })
// @Public skips the user-JWT guard; AdminGuard enforces the ops token instead.
@Public()
@UseGuards(AdminGuard)
@Controller('v1/admin')
export class AdminController {
  constructor(private readonly adminService: AdminService) {}

  @Get('stats')
  @ApiOperation({ summary: 'Operations snapshot — counts only, no user/coupon payloads' })
  async stats(): Promise<AdminStatsDto> {
    return this.adminService.stats();
  }
}
