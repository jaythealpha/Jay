import {
  BadRequestException,
  Body,
  Controller,
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
import { ApiBody, ApiConsumes, ApiOperation, ApiQuery, ApiTags } from '@nestjs/swagger';
import { z } from 'zod';
import type { CouponDetailDto, CouponListResponseDto, CouponStatus } from '@amc/shared-types';
import { ZodValidationPipe } from '../common/pipes/zod-validation.pipe';
import { CouponsService, type EditCouponInput } from './coupons.service';

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
    @UploadedFile() file: Express.Multer.File | undefined,
    @Body('sourceType') sourceType?: string,
  ): Promise<{ id: string; status: CouponStatus }> {
    if (!file) {
      throw new BadRequestException('image 파일이 필요합니다.');
    }
    return this.couponsService.createFromImage(
      { buffer: file.buffer, mimetype: file.mimetype, size: file.size },
      sourceType,
    );
  }

  @Get(':id')
  @ApiOperation({ summary: 'Coupon detail with recognition confidences and signed asset URLs' })
  async detail(@Param('id') id: string): Promise<CouponDetailDto> {
    return this.couponsService.detail(id);
  }

  @Patch(':id')
  @ApiOperation({ summary: 'Edit coupon fields (Confirm-Do-Not-Type review flow)' })
  async edit(
    @Param('id') id: string,
    @Body(new ZodValidationPipe(editCouponSchema)) body: EditCouponInput,
  ): Promise<CouponDetailDto> {
    return this.couponsService.edit(id, body);
  }

  @Post(':id/confirm')
  @HttpCode(200)
  @ApiOperation({ summary: 'Confirm a NEEDS_REVIEW coupon as correct (→ ACTIVE)' })
  async confirm(@Param('id') id: string): Promise<CouponDetailDto> {
    return this.couponsService.confirm(id);
  }
}
