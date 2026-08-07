import { Body, Controller, Delete, Get, HttpCode, Param, Post, Query } from '@nestjs/common';
import { ApiBearerAuth, ApiOperation, ApiQuery, ApiTags } from '@nestjs/swagger';
import { z } from 'zod';
import type { ListingDto, MarketListResponseDto, OrderDto } from '@amc/shared-types';
import { CurrentUser } from '../auth/current-user.decorator';
import type { AuthenticatedUser } from '../auth/jwt-auth.guard';
import { ZodValidationPipe } from '../common/pipes/zod-validation.pipe';
import { MarketService } from './market.service';

const createListingSchema = z
  .object({
    couponId: z.string().min(1),
    priceMinor: z.number().int().min(1),
  })
  .strict();

type CreateListingBody = z.infer<typeof createListingSchema>;

@ApiTags('market')
@ApiBearerAuth()
@Controller('v1/market')
export class MarketController {
  constructor(private readonly marketService: MarketService) {}

  @Get('listings')
  @ApiOperation({ summary: 'Browse listings — soonest-expiring first, seller anonymous' })
  @ApiQuery({ name: 'q', required: false, description: 'Search brand/product/category' })
  @ApiQuery({ name: 'limit', required: false })
  async browse(
    @CurrentUser() user: AuthenticatedUser,
    @Query('q') q?: string,
    @Query('limit') limit?: string,
  ): Promise<MarketListResponseDto> {
    const parsedLimit = limit !== undefined ? Number.parseInt(limit, 10) : undefined;
    return this.marketService.browse(user.id, {
      q,
      limit: Number.isNaN(parsedLimit) ? undefined : parsedLimit,
    });
  }

  @Post('listings')
  @ApiOperation({ summary: 'List one of my coupons for sale (locks wallet actions)' })
  async create(
    @CurrentUser() user: AuthenticatedUser,
    @Body(new ZodValidationPipe(createListingSchema)) body: CreateListingBody,
  ): Promise<ListingDto> {
    return this.marketService.createListing(user.id, body.couponId, body.priceMinor);
  }

  @Delete('listings/:id')
  @HttpCode(204)
  @ApiOperation({ summary: 'Cancel my listing — the coupon returns to normal wallet use' })
  async cancel(@CurrentUser() user: AuthenticatedUser, @Param('id') id: string): Promise<void> {
    await this.marketService.cancelListing(user.id, id);
  }

  @Post('listings/:id/purchase')
  @HttpCode(200)
  @ApiOperation({ summary: 'Buy a listing (MOCK payment — no real money moves)' })
  async purchase(
    @CurrentUser() user: AuthenticatedUser,
    @Param('id') id: string,
  ): Promise<OrderDto> {
    return this.marketService.purchase(user.id, id);
  }

  @Get('orders')
  @ApiOperation({ summary: 'My purchase and sale history' })
  async orders(@CurrentUser() user: AuthenticatedUser): Promise<{ items: OrderDto[] }> {
    return this.marketService.myOrders(user.id);
  }
}
