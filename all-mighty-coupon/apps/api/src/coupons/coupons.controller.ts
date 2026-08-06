import {
  BadRequestException,
  Body,
  Controller,
  Delete,
  Get,
  HttpCode,
  Param,
  Patch,
  Post,
  Query,
  UploadedFile,
  UseInterceptors,
} from '@nestjs/common';
import { FileInterceptor } from '@nestjs/platform-express';
import {
  ApiBearerAuth,
  ApiBody,
  ApiConsumes,
  ApiOperation,
  ApiQuery,
  ApiTags,
} from '@nestjs/swagger';
import { z } from 'zod';
import type { CouponDetailDto, CouponListResponseDto, CouponStatus } from '@amc/shared-types';
import { CurrentUser } from '../auth/current-user.decorator';
import type { AuthenticatedUser } from '../auth/jwt-auth.guard';
import { ZodValidationPipe } from '../common/pipes/zod-validation.pipe';
import { CouponsService, type BarcodeRevealDto, type EditCouponInput } from './coupons.service';

const editCouponSchema = z
  .object({
    brandName: z.string().min(1).max(100).nullable().optional(),
    productName: z.string().min(1).max(200).nullable().optional(),
    category: z.string().min(1).max(50).nullable().optional(),
    faceValueMinor: z.number().int().min(0).max(100_000_000).nullable().optional(),
    expiresAt: z
      .string()
      .regex(/^\d{4}-\d{2}-\d{2}$/, 'YYYY-MM-DD 형식이어야 합니다')
      .nullable()
      .optional(),
    usageLocationText: z.string().max(500).nullable().optional(),
    usageConditions: z.string().max(2000).nullable().optional(),
  })
  .strict();

@ApiTags('coupons')
@ApiBearerAuth()
@Controller('v1/coupons')
export class CouponsController {
  constructor(private readonly couponsService: CouponsService) {}

  @Get()
  @ApiOperation({ summary: 'List my coupons — search, filter, sort (default: expiration first)' })
  @ApiQuery({ name: 'status', required: false, description: 'Filter by coupon status' })
  @ApiQuery({ name: 'q', required: false, description: 'Search brand/product/category' })
  @ApiQuery({
    name: 'sort',
    required: false,
    description: 'EXPIRATION_ASC (default) | CREATED_DESC | VALUE_DESC | BRAND_ASC',
  })
  @ApiQuery({ name: 'limit', required: false, description: 'Max items (default 50, cap 100)' })
  async list(
    @CurrentUser() user: AuthenticatedUser,
    @Query('status') status?: string,
    @Query('q') q?: string,
    @Query('sort') sort?: string,
    @Query('limit') limit?: string,
  ): Promise<CouponListResponseDto> {
    const parsedLimit = limit !== undefined ? Number.parseInt(limit, 10) : undefined;
    return this.couponsService.list(user.id, {
      status,
      q,
      sort,
      limit: Number.isNaN(parsedLimit) ? undefined : parsedLimit,
    });
  }

  @Post()
  @ApiOperation({ summary: 'Register a coupon from an image; analysis runs async' })
  @ApiConsumes('multipart/form-data')
  @ApiBody({
    schema: {
      type: 'object',
      properties: {
        image: { type: 'string', format: 'binary' },
        sourceType: {
          type: 'string',
          enum: ['CAMERA', 'PHOTO_LIBRARY', 'SHARE_EXTENSION', 'FILE_UPLOAD', 'MANUAL'],
        },
      },
      required: ['image'],
    },
  })
  @UseInterceptors(FileInterceptor('image'))
  async create(
    @CurrentUser() user: AuthenticatedUser,
    @UploadedFile() file: Express.Multer.File | undefined,
    @Body('sourceType') sourceType?: string,
  ): Promise<{ id: string; status: CouponStatus }> {
    if (!file) {
      throw new BadRequestException('image 파일이 필요합니다.');
    }
    return this.couponsService.createFromImage(
      user.id,
      { buffer: file.buffer, mimetype: file.mimetype, size: file.size },
      sourceType,
    );
  }

  @Get(':id')
  @ApiOperation({ summary: 'Coupon detail with recognition confidences and signed asset URLs' })
  async detail(
    @CurrentUser() user: AuthenticatedUser,
    @Param('id') id: string,
  ): Promise<CouponDetailDto> {
    return this.couponsService.detail(user.id, id);
  }

  @Patch(':id')
  @ApiOperation({ summary: 'Edit coupon fields (Confirm-Do-Not-Type review flow)' })
  async edit(
    @CurrentUser() user: AuthenticatedUser,
    @Param('id') id: string,
    @Body(new ZodValidationPipe(editCouponSchema)) body: EditCouponInput,
  ): Promise<CouponDetailDto> {
    return this.couponsService.edit(user.id, id, body);
  }

  @Post(':id/confirm')
  @HttpCode(200)
  @ApiOperation({ summary: 'Confirm a NEEDS_REVIEW coupon as correct (→ ACTIVE)' })
  async confirm(
    @CurrentUser() user: AuthenticatedUser,
    @Param('id') id: string,
  ): Promise<CouponDetailDto> {
    return this.couponsService.confirm(user.id, id);
  }

  @Post(':id/redeem')
  @HttpCode(200)
  @ApiOperation({ summary: 'Mark as used (→ REDEEMED)' })
  async redeem(
    @CurrentUser() user: AuthenticatedUser,
    @Param('id') id: string,
  ): Promise<CouponDetailDto> {
    return this.couponsService.redeem(user.id, id);
  }

  @Post(':id/restore')
  @HttpCode(200)
  @ApiOperation({ summary: 'Undo redeem — status recomputed from the expiration date' })
  async restore(
    @CurrentUser() user: AuthenticatedUser,
    @Param('id') id: string,
  ): Promise<CouponDetailDto> {
    return this.couponsService.restore(user.id, id);
  }

  @Post(':id/archive')
  @HttpCode(200)
  @ApiOperation({ summary: 'Archive the coupon' })
  async archive(
    @CurrentUser() user: AuthenticatedUser,
    @Param('id') id: string,
  ): Promise<CouponDetailDto> {
    return this.couponsService.archive(user.id, id);
  }

  @Post(':id/unarchive')
  @HttpCode(200)
  @ApiOperation({ summary: 'Unarchive — status recomputed from the expiration date' })
  async unarchive(
    @CurrentUser() user: AuthenticatedUser,
    @Param('id') id: string,
  ): Promise<CouponDetailDto> {
    return this.couponsService.unarchive(user.id, id);
  }

  @Delete(':id')
  @HttpCode(204)
  @ApiOperation({ summary: 'Delete the coupon and its stored images' })
  async remove(@CurrentUser() user: AuthenticatedUser, @Param('id') id: string): Promise<void> {
    await this.couponsService.remove(user.id, id);
  }

  @Get(':id/barcode')
  @ApiOperation({ summary: 'Reveal the barcode for in-store display (audit-logged)' })
  async barcode(
    @CurrentUser() user: AuthenticatedUser,
    @Param('id') id: string,
  ): Promise<BarcodeRevealDto> {
    return this.couponsService.revealBarcode(user.id, id);
  }
}
