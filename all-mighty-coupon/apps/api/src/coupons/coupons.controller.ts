import { Controller, Get, Query } from '@nestjs/common';
import { ApiOperation, ApiQuery, ApiTags } from '@nestjs/swagger';
import type { CouponListResponseDto } from '@amc/shared-types';
import { CouponsService } from './coupons.service';

@ApiTags('coupons')
@Controller('v1/coupons')
export class CouponsController {
  constructor(private readonly couponsService: CouponsService) {}

  @Get()
  @ApiOperation({ summary: 'List coupons, soonest expiration first' })
  @ApiQuery({ name: 'status', required: false, description: 'Filter by coupon status' })
  @ApiQuery({ name: 'limit', required: false, description: 'Max items (default 50, cap 100)' })
  async list(
    @Query('status') status?: string,
    @Query('limit') limit?: string,
  ): Promise<CouponListResponseDto> {
    const parsedLimit = limit !== undefined ? Number.parseInt(limit, 10) : undefined;
    return this.couponsService.list({
      status,
      limit: Number.isNaN(parsedLimit) ? undefined : parsedLimit,
    });
  }
}
